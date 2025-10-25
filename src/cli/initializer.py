import asyncio
import platform
import shutil
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from importlib.resources import files
from pathlib import Path
from typing import cast

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph.state import CompiledStateGraph

from src.agents.factory import AgentFactory, GraphFactory
from src.checkpointer.factory import CheckpointerFactory
from src.cli.timer import timer
from src.core.config import (
    AgentConfig,
    BatchAgentConfig,
    BatchCheckpointerConfig,
    BatchLLMConfig,
    CheckpointerConfig,
    LLMConfig,
    MCPConfig,
)
from src.core.constants import (
    CONFIG_AGENTS_FILE_NAME,
    CONFIG_APPROVAL_FILE_NAME,
    CONFIG_CHECKPOINTERS_FILE_NAME,
    CONFIG_CHECKPOINTS_URL_FILE_NAME,
    CONFIG_DIR_NAME,
    CONFIG_LLMS_FILE_NAME,
    CONFIG_MCP_FILE_NAME,
    CONFIG_MEMORY_FILE_NAME,
    CONFIG_SUBAGENTS_FILE_NAME,
)
from src.core.settings import settings
from src.llms.factory import LLMFactory
from src.mcp.factory import MCPFactory
from src.state.base import BaseState
from src.tools.factory import ToolFactory


class Initializer:
    """Centralized service"""

    def __init__(self):
        # Core factories
        self.agent_factory = AgentFactory()
        self.tool_factory = ToolFactory()
        self.llm_factory = LLMFactory(settings.llm)
        self.mcp_factory = MCPFactory()
        self.checkpointer_factory = CheckpointerFactory()
        self.graph_factory = GraphFactory(
            agent_factory=self.agent_factory,
            tool_factory=self.tool_factory,
            mcp_factory=self.mcp_factory,
            llm_factory=self.llm_factory,
        )
        # Cached tools
        self.cached_tools: list[BaseTool] = []

    @staticmethod
    def _ensure_config_dir(working_dir: Path):
        """Ensure config directory exists, copy from template if needed."""
        target_config_dir = Path(working_dir) / CONFIG_DIR_NAME
        if not target_config_dir.exists():
            template_config_dir = Path(str(files("resources") / "configs" / "default"))

            shutil.copytree(
                template_config_dir,
                target_config_dir,
                ignore=shutil.ignore_patterns(
                    CONFIG_CHECKPOINTS_URL_FILE_NAME.name.replace(".db", ".*"),
                    CONFIG_APPROVAL_FILE_NAME.name,
                ),
            )

        # Ensure CONFIG_DIR_NAME is ignored in git (local-only, not committed)
        git_info_exclude = Path(working_dir) / ".git" / "info" / "exclude"
        if git_info_exclude.parent.exists():
            try:
                existing_content = ""
                if git_info_exclude.exists():
                    existing_content = git_info_exclude.read_text()

                ignore_pattern = f"{CONFIG_DIR_NAME}/"
                if ignore_pattern not in existing_content:
                    with git_info_exclude.open("a") as f:
                        f.write(f"\n# Langrepl configuration\n{ignore_pattern}\n")
            except Exception:
                pass

    async def load_llms_config(self, working_dir: Path) -> BatchLLMConfig:
        """Load LLMs configuration."""
        self._ensure_config_dir(working_dir)
        target_llms_config_path = Path(working_dir) / CONFIG_LLMS_FILE_NAME
        return await BatchLLMConfig.from_yaml(target_llms_config_path)

    async def load_llm_config(self, model: str, working_dir: Path) -> LLMConfig:
        """Load LLM configuration by name."""
        llm_configs = await self.load_llms_config(working_dir)
        llm = llm_configs.get_llm_config(model)
        if llm:
            return llm
        else:
            raise ValueError(
                f"LLM '{model}' not found. Available: {llm_configs.llm_names}"
            )

    async def load_checkpointers_config(
        self, working_dir: Path
    ) -> BatchCheckpointerConfig:
        """Load checkpointers configuration."""
        self._ensure_config_dir(working_dir)
        target_checkpointers_config_path = (
            Path(working_dir) / CONFIG_CHECKPOINTERS_FILE_NAME
        )
        return await BatchCheckpointerConfig.from_yaml(target_checkpointers_config_path)

    async def load_agents_config(self, working_dir: Path) -> BatchAgentConfig:
        """Load agents configuration with resolved subagent references."""
        self._ensure_config_dir(working_dir)
        target_agents_config_path = Path(working_dir) / CONFIG_AGENTS_FILE_NAME

        # Load LLM and checkpointer configs if they exist
        llm_config = None
        checkpointer_config = None
        if (Path(working_dir) / CONFIG_LLMS_FILE_NAME).exists():
            llm_config = await self.load_llms_config(working_dir)
        if (Path(working_dir) / CONFIG_CHECKPOINTERS_FILE_NAME).exists():
            checkpointer_config = await self.load_checkpointers_config(working_dir)

        # Load subagents config if it exists
        subagents_config = None
        target_subagents_config_path = Path(working_dir) / CONFIG_SUBAGENTS_FILE_NAME
        if target_subagents_config_path.exists():
            subagents_config = await BatchAgentConfig.from_yaml(
                target_subagents_config_path, llm_config, None, None
            )

        return await BatchAgentConfig.from_yaml(
            target_agents_config_path, llm_config, checkpointer_config, subagents_config
        )

    async def load_agent_config(
        self, agent: str | None, working_dir: Path
    ) -> AgentConfig:
        """Load agent configuration by name."""
        agent_configs = await self.load_agents_config(working_dir)
        agent_config = agent_configs.get_agent_config(agent)
        if agent_config:
            return agent_config
        else:
            raise ValueError(
                f"Agent '{agent}' not found. Available: {agent_configs.agent_names}"
            )

    @staticmethod
    async def load_mcp_config(working_dir: Path) -> MCPConfig:
        """Get MCP configuration."""
        return await MCPConfig.from_json(Path(working_dir) / CONFIG_MCP_FILE_NAME)

    @staticmethod
    async def save_mcp_config(mcp_config: MCPConfig, working_dir: Path):
        """Save MCP configuration."""
        mcp_config.to_json(Path(working_dir) / CONFIG_MCP_FILE_NAME)

    @staticmethod
    async def update_agent_llm(agent_name: str, new_llm_name: str, working_dir: Path):
        """Update a specific agent's LLM in the config file."""
        target_agents_config_path = Path(working_dir) / CONFIG_AGENTS_FILE_NAME
        await BatchAgentConfig.update_agent_llm(
            target_agents_config_path, agent_name, new_llm_name
        )

    @staticmethod
    async def load_user_memory(working_dir: Path) -> str:
        """Load user memory from project-specific memory file.

        Args:
            working_dir: Project working directory

        Returns:
            Formatted user memory string for prompt injection, or empty string if no memory
        """
        memory_path = working_dir / CONFIG_MEMORY_FILE_NAME
        if memory_path.exists():
            content = memory_path.read_text().strip()
            if content:
                return f"<user-memory>\n{content}\n</user-memory>"
        return ""

    @asynccontextmanager
    async def get_checkpointer(
        self, agent: str, working_dir: Path
    ) -> AsyncIterator[BaseCheckpointSaver]:
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
        with timer("Load configs"):
            if model:
                agent_config, llm_config, mcp_config = await asyncio.gather(
                    self.load_agent_config(agent, working_dir),
                    self.load_llm_config(model, working_dir),
                    self.load_mcp_config(working_dir),
                )
            else:
                agent_config, mcp_config = await asyncio.gather(
                    self.load_agent_config(agent, working_dir),
                    self.load_mcp_config(working_dir),
                )
                llm_config = None

        # Generate environment context for prompt template rendering
        now = datetime.now(timezone.utc).astimezone()
        user_memory = await self.load_user_memory(working_dir)
        template_context = {
            "working_dir": str(working_dir),
            "platform": platform.system(),
            "os_version": platform.version(),
            "current_date_time_zoned": now.strftime("%Y-%m-%d %H:%M:%S %Z"),
            "user_memory": user_memory,
        }

        with timer("Create checkpointer"):
            checkpointer_ctx = self.checkpointer_factory.create(
                cast(CheckpointerConfig, agent_config.checkpointer),
                str(working_dir / CONFIG_CHECKPOINTS_URL_FILE_NAME),
            )

        async with checkpointer_ctx as checkpointer:
            with timer("Create graph"):
                graph = await self.graph_factory.create(
                    agent_config, BaseState, mcp_config, llm_config, template_context
                )

            with timer("Compile graph"):
                # Cache tools from graph
                self.cached_tools = getattr(graph, "_tools", [])
                compiled_graph = graph.compile(checkpointer=checkpointer)

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
                # First pass: collect unique thread_ids
                thread_ids = set()
                async for checkpoint in checkpointer.alist(config=None):
                    thread_id = checkpoint.config.get("configurable", {}).get(
                        "thread_id"
                    )
                    if thread_id:
                        thread_ids.add(thread_id)

                # Second pass: get the latest checkpoint for each thread using aget_tuple
                threads = {}
                for thread_id in thread_ids:
                    try:
                        checkpoint_tuple = await checkpointer.aget_tuple(
                            config=RunnableConfig(configurable={"thread_id": thread_id})
                        )

                        if checkpoint_tuple and checkpoint_tuple.checkpoint:
                            messages = checkpoint_tuple.checkpoint.get(
                                "channel_values", {}
                            ).get("messages", [])
                            if messages:
                                threads[thread_id] = {
                                    "thread_id": thread_id,
                                    "last_message": messages[-1].text[:100],
                                    "timestamp": checkpoint_tuple.checkpoint.get(
                                        "ts", ""
                                    ),
                                }
                    except Exception:
                        # Skip threads that can't be retrieved
                        continue

                # Sort threads by timestamp (latest first)
                thread_list = list(threads.values())
                thread_list.sort(key=lambda t: t.get("timestamp", 0), reverse=True)
                return thread_list
            except Exception:
                # Return an empty list if there's an error
                return []


initializer = Initializer()
