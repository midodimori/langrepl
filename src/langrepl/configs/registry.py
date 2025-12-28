"""Central registry for loading, saving, and caching configurations."""

from __future__ import annotations

import asyncio
import shutil
from importlib.resources import files
from pathlib import Path

from langrepl.configs.agent import (
    AgentConfig,
    BatchAgentConfig,
    BatchSubAgentConfig,
    SubAgentConfig,
)
from langrepl.configs.approval import ToolApprovalConfig
from langrepl.configs.checkpointer import BatchCheckpointerConfig, CheckpointerConfig
from langrepl.configs.llm import BatchLLMConfig, LLMConfig
from langrepl.configs.mcp import MCPConfig
from langrepl.configs.sandbox import BatchSandboxConfig, SandboxConfig
from langrepl.core.constants import (
    CONFIG_AGENTS_DIR,
    CONFIG_AGENTS_FILE_NAME,
    CONFIG_APPROVAL_FILE_NAME,
    CONFIG_CHECKPOINTERS_DIR,
    CONFIG_CHECKPOINTERS_FILE_NAME,
    CONFIG_CHECKPOINTS_URL_FILE_NAME,
    CONFIG_DIR_NAME,
    CONFIG_LLMS_DIR,
    CONFIG_LLMS_FILE_NAME,
    CONFIG_MCP_FILE_NAME,
    CONFIG_MEMORY_FILE_NAME,
    CONFIG_SANDBOXES_DIR,
    CONFIG_SUBAGENTS_DIR,
    CONFIG_SUBAGENTS_FILE_NAME,
)


class ConfigRegistry:
    """Central registry for loading, saving, and caching all configurations."""

    def __init__(self, working_dir: Path):
        self.working_dir = working_dir
        self.config_dir = working_dir / CONFIG_DIR_NAME

        # Lazy-loaded caches
        self._llms: BatchLLMConfig | None = None
        self._checkpointers: BatchCheckpointerConfig | None = None
        self._agents: BatchAgentConfig | None = None
        self._subagents: BatchSubAgentConfig | None = None
        self._sandboxes: BatchSandboxConfig | None = None
        self._mcp: MCPConfig | None = None
        self._approval: ToolApprovalConfig | None = None

    # === Setup ===

    async def ensure_config_dir(self) -> None:
        """Ensure config directory exists, copy from template if needed."""
        if not self.config_dir.exists():
            template_config_dir = Path(str(files("resources") / "configs" / "default"))

            await asyncio.to_thread(
                shutil.copytree,
                template_config_dir,
                self.config_dir,
                ignore=shutil.ignore_patterns(
                    CONFIG_CHECKPOINTS_URL_FILE_NAME.name.replace(".db", ".*"),
                    CONFIG_APPROVAL_FILE_NAME.name,
                ),
            )

        # Ensure CONFIG_DIR_NAME is ignored in git (local-only, not committed)
        git_info_exclude = self.working_dir / ".git" / "info" / "exclude"
        if git_info_exclude.parent.exists():
            try:
                existing_content = ""
                if git_info_exclude.exists():
                    existing_content = await asyncio.to_thread(
                        git_info_exclude.read_text
                    )

                ignore_pattern = f"{CONFIG_DIR_NAME}/"
                if ignore_pattern not in existing_content:

                    def write_exclude():
                        with git_info_exclude.open("a") as f:
                            f.write(f"\n# Langrepl configuration\n{ignore_pattern}\n")

                    await asyncio.to_thread(write_exclude)
            except Exception:
                pass

    # === LLM configs ===

    async def load_llms(self, force_reload: bool = False) -> BatchLLMConfig:
        """Load all LLM configs (cached)."""
        if self._llms is None or force_reload:
            await self.ensure_config_dir()
            self._llms = await BatchLLMConfig.from_yaml(
                file_path=self.working_dir / CONFIG_LLMS_FILE_NAME,
                dir_path=self.working_dir / CONFIG_LLMS_DIR,
            )
        return self._llms

    async def get_llm(self, alias: str) -> LLMConfig:
        """Get single LLM by alias."""
        llms = await self.load_llms()
        llm = llms.get_llm_config(alias)
        if llm:
            return llm
        raise ValueError(f"LLM '{alias}' not found. Available: {llms.llm_names}")

    # === Checkpointer configs ===

    async def load_checkpointers(
        self, force_reload: bool = False
    ) -> BatchCheckpointerConfig:
        """Load all checkpointer configs (cached)."""
        if self._checkpointers is None or force_reload:
            await self.ensure_config_dir()
            self._checkpointers = await BatchCheckpointerConfig.from_yaml(
                file_path=self.working_dir / CONFIG_CHECKPOINTERS_FILE_NAME,
                dir_path=self.working_dir / CONFIG_CHECKPOINTERS_DIR,
            )
        return self._checkpointers

    async def get_checkpointer(self, name: str) -> CheckpointerConfig | None:
        """Get single checkpointer by type name."""
        checkpointers = await self.load_checkpointers()
        return checkpointers.get_checkpointer_config(name)

    # === SubAgent configs ===

    async def load_subagents(self, force_reload: bool = False) -> BatchSubAgentConfig:
        """Load all subagent configs (cached)."""
        if self._subagents is None or force_reload:
            await self.ensure_config_dir()

            llm_config = None
            if (self.working_dir / CONFIG_LLMS_FILE_NAME).exists() or (
                self.working_dir / CONFIG_LLMS_DIR
            ).exists():
                llm_config = await self.load_llms()

            self._subagents = await BatchSubAgentConfig.from_yaml(
                file_path=self.working_dir / CONFIG_SUBAGENTS_FILE_NAME,
                dir_path=self.working_dir / CONFIG_SUBAGENTS_DIR,
                batch_llm_config=llm_config,
            )
        return self._subagents

    async def get_subagent(self, name: str) -> SubAgentConfig | None:
        """Get single subagent by name."""
        subagents = await self.load_subagents()
        return subagents.get_subagent_config(name)

    # === Sandbox configs ===

    async def load_sandboxes(self, force_reload: bool = False) -> BatchSandboxConfig:
        """Load all sandbox configs (cached)."""
        if self._sandboxes is None or force_reload:
            await self.ensure_config_dir()
            self._sandboxes = await BatchSandboxConfig.from_yaml(
                dir_path=self.working_dir / CONFIG_SANDBOXES_DIR,
            )
        return self._sandboxes

    async def get_sandbox(self, name: str) -> SandboxConfig:
        """Get single sandbox by name."""
        sandboxes = await self.load_sandboxes()
        sandbox = sandboxes.get_sandbox_config(name)
        if sandbox:
            return sandbox
        raise ValueError(
            f"Sandbox '{name}' not found. Available: {sandboxes.sandbox_names}"
        )

    # === Agent configs ===

    async def load_agents(self, force_reload: bool = False) -> BatchAgentConfig:
        """Load all agent configs with resolved references (cached)."""
        if self._agents is None or force_reload:
            await self.ensure_config_dir()

            llm_config = None
            checkpointer_config = None

            if (self.working_dir / CONFIG_LLMS_FILE_NAME).exists() or (
                self.working_dir / CONFIG_LLMS_DIR
            ).exists():
                llm_config = await self.load_llms()

            if (self.working_dir / CONFIG_CHECKPOINTERS_FILE_NAME).exists() or (
                self.working_dir / CONFIG_CHECKPOINTERS_DIR
            ).exists():
                checkpointer_config = await self.load_checkpointers()

            subagents_config = None
            if (self.working_dir / CONFIG_SUBAGENTS_FILE_NAME).exists() or (
                self.working_dir / CONFIG_SUBAGENTS_DIR
            ).exists():
                subagents_config = await self.load_subagents()

            sandboxes_config = None
            if (self.working_dir / CONFIG_SANDBOXES_DIR).exists():
                sandboxes_config = await self.load_sandboxes()

            self._agents = await BatchAgentConfig.from_yaml(
                file_path=self.working_dir / CONFIG_AGENTS_FILE_NAME,
                dir_path=self.working_dir / CONFIG_AGENTS_DIR,
                batch_llm_config=llm_config,
                batch_checkpointer_config=checkpointer_config,
                batch_subagent_config=subagents_config,
                batch_sandbox_config=sandboxes_config,
            )
        return self._agents

    async def get_agent(self, name: str | None = None) -> AgentConfig:
        """Get single agent by name, or default agent if name is None."""
        agents = await self.load_agents()
        agent = agents.get_agent_config(name)
        if agent:
            return agent
        raise ValueError(f"Agent '{name}' not found. Available: {agents.agent_names}")

    # === MCP config ===

    async def load_mcp(self, force_reload: bool = False) -> MCPConfig:
        """Load MCP server config (cached)."""
        if self._mcp is None or force_reload:
            self._mcp = await MCPConfig.from_json(
                self.working_dir / CONFIG_MCP_FILE_NAME
            )
        return self._mcp

    async def save_mcp(self, config: MCPConfig) -> None:
        """Save MCP config to file."""
        config.to_json(self.working_dir / CONFIG_MCP_FILE_NAME)
        self._mcp = config

    # === Approval config ===

    def load_approval(self, force_reload: bool = False) -> ToolApprovalConfig:
        """Load tool approval config (cached)."""
        if self._approval is None or force_reload:
            self._approval = ToolApprovalConfig.from_json_file(
                self.working_dir / CONFIG_APPROVAL_FILE_NAME
            )
        return self._approval

    def save_approval(self, config: ToolApprovalConfig) -> None:
        """Save approval config to file."""
        config.save_to_json_file(self.working_dir / CONFIG_APPROVAL_FILE_NAME)
        self._approval = config

    # === User memory ===

    async def load_user_memory(self) -> str:
        """Load user memory from project-specific memory file.

        Returns:
            Formatted user memory string for prompt injection, or empty string if no memory
        """
        memory_path = self.working_dir / CONFIG_MEMORY_FILE_NAME
        if memory_path.exists():
            content = await asyncio.to_thread(memory_path.read_text)
            content = content.strip()
            if content:
                return f"<user-memory>\n{content}\n</user-memory>"
        return ""

    # === Update operations ===

    async def update_agent_llm(self, agent_name: str, llm_alias: str) -> None:
        """Update an agent's LLM reference and persist."""
        await BatchAgentConfig.update_agent_llm(
            file_path=self.working_dir / CONFIG_AGENTS_FILE_NAME,
            agent_name=agent_name,
            new_llm_name=llm_alias,
            dir_path=self.working_dir / CONFIG_AGENTS_DIR,
        )
        self._agents = None  # Invalidate cache

    async def update_subagent_llm(self, subagent_name: str, llm_alias: str) -> None:
        """Update a subagent's LLM reference and persist."""
        await BatchAgentConfig.update_agent_llm(
            file_path=self.working_dir / CONFIG_SUBAGENTS_FILE_NAME,
            agent_name=subagent_name,
            new_llm_name=llm_alias,
            dir_path=self.working_dir / CONFIG_SUBAGENTS_DIR,
        )
        self._subagents = None  # Invalidate cache

    async def update_default_agent(self, agent_name: str) -> None:
        """Set the default agent and persist."""
        await BatchAgentConfig.update_default_agent(
            file_path=self.working_dir / CONFIG_AGENTS_FILE_NAME,
            agent_name=agent_name,
            dir_path=self.working_dir / CONFIG_AGENTS_DIR,
        )
        self._agents = None  # Invalidate cache

    # === Cache management ===

    def invalidate_cache(self) -> None:
        """Clear all cached configs."""
        self._llms = None
        self._checkpointers = None
        self._agents = None
        self._subagents = None
        self._sandboxes = None
        self._mcp = None
        self._approval = None
