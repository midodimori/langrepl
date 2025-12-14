from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING, cast

from langchain_core.runnables import RunnableConfig

from src.agents.context import AgentContext
from src.agents.factory import AgentFactory
from src.agents.state import AgentState
from src.checkpointer.base import BaseCheckpointer
from src.checkpointer.factory import CheckpointerFactory
from src.cli.bootstrap.timer import timer
from src.configs import (
    CheckpointerConfig,
    ConfigRegistry,
)
from src.core.constants import (
    CONFIG_CHECKPOINTS_URL_FILE_NAME,
    CONFIG_MCP_CACHE_DIR,
    CONFIG_MEMORY_FILE_NAME,
    CONFIG_SKILLS_DIR,
)
from src.core.settings import settings
from src.llms.factory import LLMFactory
from src.mcp.factory import MCPFactory
from src.sandboxes import Sandbox, SandboxFactory
from src.skills.factory import SkillFactory
from src.tools.factory import ToolFactory

if TYPE_CHECKING:
    from langchain_core.tools import BaseTool
    from langgraph.graph.state import CompiledStateGraph

    from src.skills.factory import Skill


class Initializer:
    """Centralized service"""

    def __init__(self):
        self.tool_factory = ToolFactory()
        self.skill_factory = SkillFactory()
        self.llm_factory = LLMFactory(settings.llm)
        self.mcp_factory = MCPFactory()
        self.checkpointer_factory = CheckpointerFactory()
        self.sandbox_factory = SandboxFactory()
        self.agent_factory = AgentFactory(
            tool_factory=self.tool_factory,
            llm_factory=self.llm_factory,
            skill_factory=self.skill_factory,
        )
        self.cached_llm_tools: list[BaseTool] = []
        self.cached_tools_in_catalog: list[BaseTool] = []
        self.cached_agent_skills: list[Skill] = []
        self.cached_sandbox_executor: Sandbox | None = None

    @staticmethod
    async def load_user_memory(working_dir: Path) -> str:
        """Load user memory from project-specific memory file."""
        memory_path = working_dir / CONFIG_MEMORY_FILE_NAME
        if memory_path.exists():
            content = await asyncio.to_thread(memory_path.read_text)
            content = content.strip()
            if content:
                return f"<user-memory>\n{content}\n</user-memory>"
        return ""

    @asynccontextmanager
    async def get_checkpointer(
        self, agent: str, working_dir: Path
    ) -> AsyncIterator[BaseCheckpointer]:
        """Get checkpointer for agent."""
        registry = ConfigRegistry(working_dir)
        agent_config = await registry.agent(agent)
        async with self.checkpointer_factory.create(
            cast(CheckpointerConfig, agent_config.checkpointer),
            str(working_dir / CONFIG_CHECKPOINTS_URL_FILE_NAME),
        ) as checkpointer:
            yield checkpointer

    @asynccontextmanager
    async def get_graph(
        self,
        agent: str | None,
        model: str | None,
        working_dir: Path,
    ) -> AsyncIterator[CompiledStateGraph]:
        """Get compiled graph for agent."""
        with timer("Load configs"):
            registry = ConfigRegistry(working_dir)
            agent_config, mcp_config = await asyncio.gather(
                registry.agent(agent),
                registry.mcp(),
            )

            llm_config = None
            if model:
                llm_config = await registry.llm(model)

        with timer("Create checkpointer"):
            checkpointer_ctx = self.checkpointer_factory.create(
                cast(CheckpointerConfig, agent_config.checkpointer),
                str(working_dir / CONFIG_CHECKPOINTS_URL_FILE_NAME),
            )

        with timer("Create sandbox executor"):
            sandbox_executor = (
                self.sandbox_factory.create(agent_config.sandbox, working_dir)
                if agent_config.sandbox
                else None
            )

        try:
            with timer("Create MCP client"):
                mcp_client = await self.mcp_factory.create(
                    mcp_config,
                    working_dir / CONFIG_MCP_CACHE_DIR,
                    sandbox_executor=sandbox_executor,
                )

            async with checkpointer_ctx as checkpointer:
                with timer("Create and compile graph"):
                    compiled_graph = await self.agent_factory.create(
                        config=agent_config,
                        state_schema=AgentState,
                        context_schema=AgentContext,
                        checkpointer=checkpointer,
                        mcp_client=mcp_client,
                        llm_config=llm_config,
                        skills_dir=working_dir / CONFIG_SKILLS_DIR,
                    )

                self.cached_llm_tools = getattr(compiled_graph, "_llm_tools", [])
                self.cached_tools_in_catalog = getattr(
                    compiled_graph, "_tools_in_catalog", []
                )
                self.cached_agent_skills = getattr(compiled_graph, "_agent_skills", [])
                self.cached_sandbox_executor = sandbox_executor
                yield compiled_graph
        finally:
            if sandbox_executor:
                sandbox_executor.cleanup()

    async def get_threads(self, agent: str, working_dir: Path) -> list[dict]:
        """Get all conversation threads with metadata."""
        async with self.get_checkpointer(agent, working_dir) as checkpointer:
            try:
                thread_ids = await checkpointer.get_threads()

                threads = {}
                for thread_id in thread_ids:
                    try:
                        checkpoint_tuple = await checkpointer.aget_tuple(
                            config=RunnableConfig(configurable={"thread_id": thread_id})
                        )

                        if not checkpoint_tuple or not checkpoint_tuple.checkpoint:
                            continue

                        messages = checkpoint_tuple.checkpoint.get(
                            "channel_values", {}
                        ).get("messages", [])

                        if not messages:
                            continue

                        last_msg = messages[-1]
                        msg_text = getattr(last_msg, "short_content", None) or getattr(
                            last_msg, "text", "No content"
                        )
                        if isinstance(msg_text, list):
                            msg_text = " ".join(str(item) for item in msg_text)

                        threads[thread_id] = {
                            "thread_id": thread_id,
                            "last_message": str(msg_text)[:100],
                            "timestamp": checkpoint_tuple.checkpoint.get("ts", ""),
                        }

                    except Exception:
                        continue

                # Sort threads by timestamp (latest first)
                thread_list = list(threads.values())
                thread_list.sort(key=lambda t: t.get("timestamp", 0), reverse=True)
                return thread_list
            except Exception:
                return []


initializer = Initializer()
