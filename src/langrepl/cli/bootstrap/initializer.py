from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING, cast

from langchain_core.runnables import RunnableConfig

from langrepl.agents.context import AgentContext
from langrepl.agents.factory import AgentFactory
from langrepl.agents.state import AgentState
from langrepl.checkpointer.base import BaseCheckpointer
from langrepl.checkpointer.factory import CheckpointerFactory
from langrepl.cli.bootstrap.timer import timer
from langrepl.configs import (
    AgentConfig,
    BatchAgentConfig,
    BatchCheckpointerConfig,
    BatchLLMConfig,
    BatchSubAgentConfig,
    CheckpointerConfig,
    ConfigRegistry,
    LLMConfig,
    MCPConfig,
)
from langrepl.core.constants import (
    CONFIG_CHECKPOINTS_URL_FILE_NAME,
    CONFIG_MCP_CACHE_DIR,
    CONFIG_SKILLS_DIR,
)
from langrepl.core.settings import settings
from langrepl.llms.factory import LLMFactory
from langrepl.mcp.factory import MCPFactory
from langrepl.sandboxes.factory import SandboxFactory
from langrepl.skills.factory import SkillFactory
from langrepl.tools.factory import ToolFactory

if TYPE_CHECKING:
    from langchain_core.tools import BaseTool
    from langgraph.graph.state import CompiledStateGraph

    from langrepl.skills.factory import Skill


class Initializer:
    """Centralized service for initializing and managing agent resources."""

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

        # Registry cache per working_dir
        self._registries: dict[Path, ConfigRegistry] = {}

    def get_registry(self, working_dir: Path) -> ConfigRegistry:
        """Get or create a ConfigRegistry for the given working directory."""
        if working_dir not in self._registries:
            self._registries[working_dir] = ConfigRegistry(working_dir)
        return self._registries[working_dir]

    async def load_llms_config(self, working_dir: Path) -> BatchLLMConfig:
        """Load LLMs configuration."""
        return await self.get_registry(working_dir).load_llms()

    async def load_llm_config(self, model: str, working_dir: Path) -> LLMConfig:
        """Load LLM configuration by name."""
        return await self.get_registry(working_dir).get_llm(model)

    async def load_checkpointers_config(
        self, working_dir: Path
    ) -> BatchCheckpointerConfig:
        """Load checkpointers configuration."""
        return await self.get_registry(working_dir).load_checkpointers()

    async def load_subagents_config(self, working_dir: Path) -> BatchSubAgentConfig:
        """Load subagents configuration."""
        return await self.get_registry(working_dir).load_subagents()

    async def load_agents_config(self, working_dir: Path) -> BatchAgentConfig:
        """Load agents configuration with resolved subagent references."""
        return await self.get_registry(working_dir).load_agents()

    async def load_agent_config(
        self, agent: str | None, working_dir: Path
    ) -> AgentConfig:
        """Load agent configuration by name."""
        return await self.get_registry(working_dir).get_agent(agent)

    async def load_mcp_config(self, working_dir: Path) -> MCPConfig:
        """Get MCP configuration."""
        return await self.get_registry(working_dir).load_mcp()

    async def save_mcp_config(self, mcp_config: MCPConfig, working_dir: Path) -> None:
        """Save MCP configuration."""
        await self.get_registry(working_dir).save_mcp(mcp_config)

    async def update_agent_llm(
        self, agent_name: str, new_llm_name: str, working_dir: Path
    ) -> None:
        """Update a specific agent's LLM in the config file."""
        await self.get_registry(working_dir).update_agent_llm(agent_name, new_llm_name)

    async def update_subagent_llm(
        self, subagent_name: str, new_llm_name: str, working_dir: Path
    ) -> None:
        """Update a specific subagent's LLM in the config file."""
        await self.get_registry(working_dir).update_subagent_llm(
            subagent_name, new_llm_name
        )

    async def update_default_agent(self, agent_name: str, working_dir: Path) -> None:
        """Update which agent is marked as default in the config file."""
        await self.get_registry(working_dir).update_default_agent(agent_name)

    async def load_user_memory(self, working_dir: Path) -> str:
        """Load user memory from project-specific memory file."""
        return await self.get_registry(working_dir).load_user_memory()

    @asynccontextmanager
    async def get_checkpointer(
        self, agent: str, working_dir: Path
    ) -> AsyncIterator[BaseCheckpointer]:
        """Get checkpointer for agent."""
        agent_config = await self.load_agent_config(agent, working_dir)
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
        registry = self.get_registry(working_dir)

        with timer("Load configs"):
            if model:
                agent_config, llm_config, mcp_config = await asyncio.gather(
                    registry.get_agent(agent),
                    registry.get_llm(model),
                    registry.load_mcp(),
                )
            else:
                agent_config, mcp_config = await asyncio.gather(
                    registry.get_agent(agent),
                    registry.load_mcp(),
                )
                llm_config = None

        with timer("Create checkpointer"):
            checkpointer_ctx = self.checkpointer_factory.create(
                cast(CheckpointerConfig, agent_config.checkpointer),
                str(working_dir / CONFIG_CHECKPOINTS_URL_FILE_NAME),
            )

        sandbox_bindings = None
        if agent_config.sandboxes:
            with timer("Build sandbox bindings"):
                sandbox_bindings = self.sandbox_factory.build_bindings(
                    agent_config.sandboxes, working_dir
                )

        with timer("Create MCP client"):
            mcp_client = await self.mcp_factory.create(
                config=mcp_config,
                cache_dir=working_dir / CONFIG_MCP_CACHE_DIR,
                sandbox_bindings=sandbox_bindings,
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
                    sandbox_bindings=sandbox_bindings,
                )

            self.cached_llm_tools = getattr(compiled_graph, "_llm_tools", [])
            self.cached_tools_in_catalog = getattr(
                compiled_graph, "_tools_in_catalog", []
            )
            self.cached_agent_skills = getattr(compiled_graph, "_agent_skills", [])
            yield compiled_graph

    async def get_threads(self, agent: str, working_dir: Path) -> list[dict]:
        """Get all conversation threads with metadata.

        Args:
            agent: Name of the agent
            working_dir: Working directory path

        Returns:
            List of thread dictionaries with thread_id, last_message, timestamp
        """
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
