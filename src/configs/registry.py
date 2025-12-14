"""Centralized configuration registry with caching."""

import shutil
from importlib.resources import files
from pathlib import Path
from typing import Any

from src.core.constants import (
    CONFIG_APPROVAL_FILE_NAME,
    CONFIG_CHECKPOINTS_URL_FILE_NAME,
    CONFIG_DIR_NAME,
)

__all__ = ["ConfigRegistry"]


class ConfigRegistry:
    """Centralized config loading with caching. Ensures config dir exists on init."""

    def __init__(self, working_dir: Path):
        self.working_dir = working_dir
        self._cache: dict[str, Any] = {}
        self._ensure_config_dir()

    def _ensure_config_dir(self) -> None:
        """Create .langrepl dir and copy defaults if needed (sync)."""
        target_config_dir = self.working_dir / CONFIG_DIR_NAME
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

        # Add .langrepl to git exclude
        git_info_exclude = self.working_dir / ".git" / "info" / "exclude"
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

    # ─────────────────────────────────────────────
    # Batch loaders (all items)
    # ─────────────────────────────────────────────

    async def agents(self) -> "BatchAgentConfig":
        """Get all agent configurations."""
        from src.configs.agent import BatchAgentConfig

        return await self._get_or_load("agents", BatchAgentConfig.from_yaml)

    async def llms(self) -> "BatchLLMConfig":
        """Get all LLM configurations."""
        from src.configs.llm import BatchLLMConfig

        return await self._get_or_load("llms", BatchLLMConfig.from_yaml)

    async def sandboxes(self) -> "BatchSandboxConfig":
        """Get all sandbox configurations."""
        from src.configs.sandbox import BatchSandboxConfig

        return await self._get_or_load("sandboxes", BatchSandboxConfig.from_yaml)

    async def checkpointers(self) -> "BatchCheckpointerConfig":
        """Get all checkpointer configurations."""
        from src.configs.checkpointer import BatchCheckpointerConfig

        return await self._get_or_load(
            "checkpointers", BatchCheckpointerConfig.from_yaml
        )

    async def mcp(self) -> "MCPConfig":
        """Get MCP configuration."""
        from src.configs.mcp import MCPConfig

        return await self._get_or_load("mcp", MCPConfig.from_json)

    # ─────────────────────────────────────────────
    # Single-item accessors (with validation)
    # ─────────────────────────────────────────────

    async def agent(self, name: str | None = None) -> "AgentConfig":
        """Get agent by name, or default if None.

        Raises:
            ValueError: If agent not found
        """
        batch = await self.agents()
        config = batch.get_agent_config(name)
        if not config:
            raise ValueError(
                f"Agent '{name}' not found. Available: {batch.agent_names}"
            )
        return config

    async def llm(self, alias: str) -> "LLMConfig":
        """Get LLM config by alias.

        Raises:
            ValueError: If LLM not found
        """
        batch = await self.llms()
        config = batch.get_llm_config(alias)
        if not config:
            raise ValueError(f"LLM '{alias}' not found. Available: {batch.llm_names}")
        return config

    async def sandbox(self, name: str) -> "SandboxConfig":
        """Get sandbox config by name.

        Raises:
            ValueError: If sandbox not found
        """
        batch = await self.sandboxes()
        config = batch.get_sandbox_config(name)
        if not config:
            raise ValueError(
                f"Sandbox '{name}' not found. Available: {batch.sandbox_names}"
            )
        return config

    async def checkpointer(self, name: str) -> "CheckpointerConfig":
        """Get checkpointer config by type name.

        Raises:
            ValueError: If checkpointer not found
        """
        batch = await self.checkpointers()
        config = batch.get_checkpointer_config(name)
        if not config:
            raise ValueError(
                f"Checkpointer '{name}' not found. Available: {batch.checkpointer_names}"
            )
        return config

    # ─────────────────────────────────────────────
    # Cache management
    # ─────────────────────────────────────────────

    def invalidate(self, key: str | None = None) -> None:
        """Clear cache (all or specific key)."""
        if key:
            self._cache.pop(key, None)
        else:
            self._cache.clear()

    async def _get_or_load(self, key: str, loader) -> Any:
        """Get from cache or load using the provided loader."""
        if key not in self._cache:
            self._cache[key] = await loader(self.working_dir)
        return self._cache[key]


# Type hints for IDE support (imports would cause circular dependencies)
if False:  # TYPE_CHECKING
    from src.configs.agent import AgentConfig, BatchAgentConfig
    from src.configs.checkpointer import BatchCheckpointerConfig, CheckpointerConfig
    from src.configs.llm import BatchLLMConfig, LLMConfig
    from src.configs.mcp import MCPConfig
    from src.configs.sandbox import BatchSandboxConfig, SandboxConfig
