"""Agent configuration classes."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import yaml
from packaging import version as pkg_version
from pydantic import BaseModel, Field, model_validator

from langrepl.configs.base import VersionedConfig
from langrepl.configs.checkpointer import BatchCheckpointerConfig, CheckpointerConfig
from langrepl.configs.llm import BatchLLMConfig, LLMConfig
from langrepl.configs.sandbox import AgentSandboxConfig, BatchSandboxConfig
from langrepl.configs.utils import (
    _load_dir_items,
    _load_single_file,
    _validate_no_duplicates,
    load_prompt_content,
)
from langrepl.core.constants import AGENT_CONFIG_VERSION

logger = logging.getLogger(__name__)


class CompressionConfig(BaseModel):
    auto_compress_enabled: bool = Field(
        default=True, description="Enable automatic compression"
    )
    auto_compress_threshold: float = Field(
        default=0.8,
        description="Trigger compression at this context usage ratio (0.0-1.0)",
    )
    llm: LLMConfig | None = Field(
        default=None,
        description="LLM to use for summarization (defaults to agent's main llm)",
    )
    prompt: str | list[str] | None = Field(
        default_factory=lambda: [
            "prompts/shared/general_compression.md",
            "prompts/suffixes/environments.md",
        ],
        description="Prompt template(s) to use when summarizing conversation history",
    )
    messages_to_keep: int = Field(
        default=0,
        description=(
            "Number of most recent non-system messages to preserve verbatim when"
            " compressing conversation history"
        ),
        ge=0,
    )


class ToolsConfig(BaseModel):
    patterns: list[str] = Field(
        default_factory=list, description="Tool reference patterns"
    )
    use_catalog: bool = Field(
        default=False,
        description="Use tool catalog to reduce token usage (wraps impl/mcp tools)",
    )
    output_max_tokens: int | None = Field(
        default=None,
        description="Maximum tokens per tool output. Larger outputs stored in virtual filesystem.",
    )


class SkillsConfig(BaseModel):
    patterns: list[str] = Field(
        default_factory=list, description="Skill reference patterns"
    )
    use_catalog: bool = Field(
        default=False,
        description="Use skill catalog to reduce token usage",
    )


class BaseAgentConfig(VersionedConfig):
    """Base configuration shared between agents and subagents."""

    version: str = Field(
        default=AGENT_CONFIG_VERSION, description="Config schema version"
    )
    name: str = Field(default="Unknown", description="The name of the agent")
    prompt: str | list[str] = Field(
        default="",
        description="The prompt to use for the agent (single file path or list of file paths)",
    )
    llm: LLMConfig = Field(description="The LLM to use for the agent")
    tools: ToolsConfig | None = Field(default=None, description="Tool configuration")
    skills: SkillsConfig | None = Field(
        default=None, description="Skills configuration"
    )
    description: str = Field(
        default="",
        description="Description of the agent",
    )
    recursion_limit: int = Field(
        default=25, description="Maximum number of execution steps"
    )

    @classmethod
    def get_latest_version(cls) -> str:
        return AGENT_CONFIG_VERSION

    @staticmethod
    def _copy_missing_prompts(prompt_paths: list[str]) -> None:
        """Copy missing prompt files from defaults (sync, called during migration)."""
        try:
            import shutil
            from importlib.resources import files

            from langrepl.core.constants import CONFIG_DIR_NAME

            template_dir = Path(str(files("resources") / "configs" / "default"))

            for prompt_path in prompt_paths:
                template_file = template_dir / prompt_path
                if not template_file.exists():
                    continue

                target_file = Path.cwd() / CONFIG_DIR_NAME / prompt_path
                if not target_file.exists():
                    target_file.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(template_file, target_file)
                    logger.warning(f"Copying missing prompt file: {prompt_path}")
        except Exception as e:
            logger.debug(f"Failed to copy prompt files: {e}")

    @staticmethod
    def _copy_missing_sandbox_profiles() -> None:
        """Copy missing sandbox profile files from defaults (sync, called during migration)."""
        try:
            import shutil
            from importlib.resources import files

            from langrepl.core.constants import CONFIG_SANDBOXES_DIR, PLATFORM

            platform_suffix = "macos" if PLATFORM == "Darwin" else "linux"

            template_dir = Path(str(files("resources") / "configs" / "default"))
            template_sandbox_dir = template_dir / "sandboxes"

            if not template_sandbox_dir.exists():
                return

            for template_file in template_sandbox_dir.glob(f"*-{platform_suffix}.yml"):
                target_file = Path.cwd() / CONFIG_SANDBOXES_DIR / template_file.name
                if not target_file.exists():
                    target_file.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(template_file, target_file)
                    logger.warning(
                        f"Copying missing sandbox profile: {template_file.name}"
                    )
        except Exception as e:
            logger.debug(f"Failed to copy sandbox profiles: {e}")

    @classmethod
    def migrate(cls, data: dict, from_version: str) -> dict:
        """Migrate config data from older version."""
        from_ver = pkg_version.parse(from_version)

        # Migrate 1.x -> 2.0.0: tools: list[str] -> tools: ToolsConfig
        if from_ver < pkg_version.parse("2.0.0"):
            tool_output_max_tokens = data.pop("tool_output_max_tokens", None)

            if "tools" in data and isinstance(data["tools"], list):
                data["tools"] = {
                    "patterns": data["tools"],
                    "use_catalog": False,
                    "output_max_tokens": tool_output_max_tokens,
                }
            elif "tools" in data and isinstance(data["tools"], dict):
                if (
                    "output_max_tokens" not in data["tools"]
                    and tool_output_max_tokens is not None
                ):
                    data["tools"]["output_max_tokens"] = tool_output_max_tokens
            elif (
                "tools" in data
                and data["tools"] is None
                and tool_output_max_tokens is not None
            ):
                data["tools"] = {
                    "patterns": [],
                    "use_catalog": False,
                    "output_max_tokens": tool_output_max_tokens,
                }
            elif "tools" not in data and tool_output_max_tokens is not None:
                data["tools"] = {
                    "patterns": [],
                    "use_catalog": False,
                    "output_max_tokens": tool_output_max_tokens,
                }

        # Migrate 2.0.0 -> 2.1.0: add skills: SkillsConfig
        if from_ver < pkg_version.parse("2.1.0"):
            if "skills" not in data:
                data["skills"] = {
                    "patterns": [],
                    "use_catalog": False,
                }

        # Migrate 2.1.0 -> 2.2.0: rename compression_llm->llm and add prompt/messages_to_keep
        if from_ver < pkg_version.parse("2.2.0") and (
            compression := data.get("compression")
        ):
            if isinstance(compression, dict):
                if "compression_llm" in compression and "llm" not in compression:
                    compression["llm"] = compression.pop("compression_llm")

                compression.setdefault("messages_to_keep", 0)
                default_prompts = [
                    "prompts/shared/general_compression.md",
                    "prompts/suffixes/environments.md",
                ]
                compression.setdefault("prompt", default_prompts)

                cls._copy_missing_prompts(default_prompts)

        # Migrate 2.2.0 -> 2.2.1: copy default sandbox profiles if missing
        if from_ver < pkg_version.parse("2.2.1"):
            cls._copy_missing_sandbox_profiles()

        return data


class AgentConfig(BaseAgentConfig):
    """Configuration for main agents."""

    checkpointer: CheckpointerConfig | None = Field(
        default=None,
        description="The checkpointer configuration",
    )
    default: bool = Field(
        default=False, description="Whether this is the default agent"
    )
    subagents: list[SubAgentConfig] | None = Field(
        default=None, description="List of resolved subagent configurations"
    )
    sandboxes: AgentSandboxConfig | None = Field(
        default=None,
        description="Sandbox configuration for this agent",
    )
    compression: CompressionConfig | None = Field(
        default=None, description="Compression configuration for context management"
    )


# Forward reference for AgentConfig.subagents
class SubAgentConfig(BaseAgentConfig):
    """Configuration for subagents (no checkpointer, no default, no compression)."""


# Update forward reference
AgentConfig.model_rebuild()


class BaseBatchConfig(BaseModel):
    """Base class for batch configurations with shared functionality."""


class BatchAgentConfig(BaseBatchConfig):
    """Batch configuration for main agents."""

    agents: list[AgentConfig] = Field(description="The agents to use for the graph")

    @property
    def agent_names(self) -> list[str]:
        return [agent.name for agent in self.agents]

    def get_agent_config(self, agent_name: str | None) -> AgentConfig | None:
        """Get main agent config by name, or default agent if name is None."""
        if agent_name is None:
            return self.get_default_agent()
        return next((a for a in self.agents if a.name == agent_name), None)

    def get_default_agent(self) -> AgentConfig | None:
        """Get the default agent.

        Returns:
            The agent marked as default, or the first agent if none marked, or None.
        """
        if not self.agents:
            return None
        default = next((a for a in self.agents if a.default), None)
        return default or self.agents[0]

    @model_validator(mode="after")
    def validate_default_agent(self) -> BatchAgentConfig:
        """Ensure exactly one default agent when there's only one agent, and at most one default otherwise."""
        if not self.agents:
            return self

        defaults = [a for a in self.agents if a.default]

        if len(self.agents) == 1 and not self.agents[0].default:
            raise ValueError(
                f"Agent '{self.agents[0].name}' must be marked as default=true "
                "when it is the only agent in the configuration."
            )

        if len(defaults) > 1:
            raise ValueError(
                f"Multiple agents marked as default: {[a.name for a in defaults]}. "
                "Only one agent can be marked as default."
            )

        return self

    @staticmethod
    async def update_agent_llm(
        file_path: Path,
        agent_name: str,
        new_llm_name: str,
        dir_path: Path | None = None,
    ) -> None:
        if dir_path and dir_path.exists():
            agent_file = dir_path / f"{agent_name}.yml"
            if agent_file.exists():
                yaml_content = await asyncio.to_thread(agent_file.read_text)
                data = yaml.safe_load(yaml_content)
                data["llm"] = new_llm_name
                yaml_str = yaml.dump(data, default_flow_style=False, sort_keys=False)
                await asyncio.to_thread(agent_file.write_text, yaml_str)
                return

        if file_path.exists():
            yaml_content = await asyncio.to_thread(file_path.read_text)
            data = yaml.safe_load(yaml_content)
            agents: list[dict] = data.get("agents", [])
            for agent in agents:
                if agent.get("name") == agent_name:
                    agent["llm"] = new_llm_name
                    break
            yaml_str = yaml.dump(data, default_flow_style=False, sort_keys=False)
            await asyncio.to_thread(file_path.write_text, yaml_str)

    @staticmethod
    async def update_default_agent(
        file_path: Path, agent_name: str, dir_path: Path | None = None
    ) -> None:
        if dir_path and dir_path.exists():
            agent_files = await asyncio.to_thread(list, dir_path.glob("*.yml"))
            for agent_file in agent_files:
                yaml_content = await asyncio.to_thread(agent_file.read_text)
                data = yaml.safe_load(yaml_content)
                is_target = data.get("name") == agent_name
                data["default"] = is_target
                yaml_str = yaml.dump(data, default_flow_style=False, sort_keys=False)
                await asyncio.to_thread(agent_file.write_text, yaml_str)

        if file_path.exists():
            yaml_content = await asyncio.to_thread(file_path.read_text)
            data = yaml.safe_load(yaml_content)
            agents: list[dict] = data.get("agents", [])
            for agent in agents:
                agent["default"] = agent.get("name") == agent_name
            yaml_str = yaml.dump(data, default_flow_style=False, sort_keys=False)
            await asyncio.to_thread(file_path.write_text, yaml_str)

    @classmethod
    async def from_yaml(
        cls,
        file_path: Path | None = None,
        dir_path: Path | None = None,
        batch_llm_config: BatchLLMConfig | None = None,
        batch_checkpointer_config: BatchCheckpointerConfig | None = None,
        batch_subagent_config: BatchSubAgentConfig | None = None,
        batch_sandbox_config: BatchSandboxConfig | None = None,
    ) -> BatchAgentConfig:
        """Load agent configurations from YAML files."""
        agents = []
        prompt_base_path = None

        if file_path and file_path.exists():
            agents.extend(await _load_single_file(file_path, "agents", AgentConfig))
            prompt_base_path = file_path.parent

        if dir_path and dir_path.exists():
            agents.extend(
                await _load_dir_items(
                    dir_path,
                    key="name",
                    config_type="Agent",
                    config_class=AgentConfig,
                )
            )
            prompt_base_path = dir_path.parent

        if not agents:
            raise ValueError("No agents found in YAML file")

        _validate_no_duplicates(agents, key="name", config_type="Agent")

        validated_agents: list[AgentConfig] = []
        for agent in agents:
            if prompt_content := agent.get("prompt", ""):
                agent["prompt"] = await load_prompt_content(
                    prompt_base_path or Path(), prompt_content
                )

            if batch_llm_config and isinstance(agent.get("llm"), str):
                llm_name = agent["llm"]
                resolved_llm = batch_llm_config.get_llm_config(llm_name)
                if not resolved_llm:
                    raise ValueError(
                        f"LLM '{llm_name}' not found. Available: {batch_llm_config.llm_names}"
                    )
                agent["llm"] = resolved_llm

            if batch_checkpointer_config and isinstance(agent.get("checkpointer"), str):
                checkpointer_name = agent["checkpointer"]
                resolved_checkpointer = (
                    batch_checkpointer_config.get_checkpointer_config(checkpointer_name)
                )
                if not resolved_checkpointer:
                    raise ValueError(
                        f"Checkpointer '{checkpointer_name}' not found. Available: {batch_checkpointer_config.checkpointer_names}"
                    )
                agent["checkpointer"] = resolved_checkpointer

            if batch_subagent_config and isinstance(agent.get("subagents"), list):
                subagent_names = agent["subagents"]
                resolved_subagents = []
                for subagent_name in subagent_names:
                    resolved_subagent = batch_subagent_config.get_subagent_config(
                        subagent_name
                    )
                    if not resolved_subagent:
                        raise ValueError(
                            f"For agent '{agent['name']}': subagent '{subagent_name}' not found. Available: {batch_subagent_config.subagent_names}"
                        )
                    resolved_subagents.append(resolved_subagent)
                agent["subagents"] = resolved_subagents

            if batch_sandbox_config and isinstance(agent.get("sandboxes"), dict):
                sandboxes_dict = agent["sandboxes"]
                if profiles := sandboxes_dict.get("profiles"):
                    for profile in profiles:
                        sandbox_ref = profile.get("sandbox")
                        if sandbox_ref and isinstance(sandbox_ref, str):
                            resolved_sandbox = batch_sandbox_config.get_sandbox_config(
                                sandbox_ref
                            )
                            if not resolved_sandbox:
                                raise ValueError(
                                    f"For agent '{agent['name']}': sandbox '{sandbox_ref}' not found. Available: {batch_sandbox_config.sandbox_names}"
                                )
                            profile["sandbox"] = resolved_sandbox

            if agent.get("compression"):
                compression = agent["compression"]
                if isinstance(compression, dict):
                    if batch_llm_config and isinstance(compression.get("llm"), str):
                        compression_llm_name = compression["llm"]
                        resolved_compression_llm = batch_llm_config.get_llm_config(
                            compression_llm_name
                        )
                        if not resolved_compression_llm:
                            raise ValueError(
                                f"Compression LLM '{compression_llm_name}' not found. Available: {batch_llm_config.llm_names}"
                            )
                        compression["llm"] = resolved_compression_llm
                    elif compression.get("llm") is None:
                        compression["llm"] = agent["llm"]

                    if prompt_content := compression.get("prompt"):
                        compression["prompt"] = await load_prompt_content(
                            prompt_base_path or Path(), prompt_content
                        )
                    else:
                        compression["prompt"] = None

            validated_agents.append(AgentConfig.model_validate(agent))

        return cls.model_validate({"agents": validated_agents})


class BatchSubAgentConfig(BaseBatchConfig):
    """Batch configuration for subagents."""

    subagents: list[SubAgentConfig] = Field(description="The subagents in this batch")

    @property
    def subagent_names(self) -> list[str]:
        return [subagent.name for subagent in self.subagents]

    def get_subagent_config(self, subagent_name: str) -> SubAgentConfig | None:
        """Get subagent config by name."""
        return next((s for s in self.subagents if s.name == subagent_name), None)

    @classmethod
    async def from_yaml(
        cls,
        file_path: Path | None = None,
        dir_path: Path | None = None,
        batch_llm_config: BatchLLMConfig | None = None,
    ) -> BatchSubAgentConfig:
        """Load subagent configurations from YAML files."""
        subagents = []
        prompt_base_path = None

        if file_path and file_path.exists():
            subagents.extend(
                await _load_single_file(file_path, "agents", SubAgentConfig)
            )
            prompt_base_path = file_path.parent

        if dir_path and dir_path.exists():
            subagents.extend(
                await _load_dir_items(
                    dir_path,
                    key="name",
                    config_type="SubAgent",
                    config_class=SubAgentConfig,
                )
            )
            prompt_base_path = dir_path.parent

        if not subagents:
            raise ValueError("No subagents found in YAML file")

        _validate_no_duplicates(subagents, key="name", config_type="SubAgent")

        validated_subagents: list[SubAgentConfig] = []
        for subagent in subagents:
            if prompt_content := subagent.get("prompt", ""):
                subagent["prompt"] = await load_prompt_content(
                    prompt_base_path or Path(), prompt_content
                )

            if batch_llm_config and isinstance(subagent.get("llm"), str):
                llm_name = subagent["llm"]
                resolved_llm = batch_llm_config.get_llm_config(llm_name)
                if not resolved_llm:
                    raise ValueError(
                        f"LLM '{llm_name}' not found. Available: {batch_llm_config.llm_names}"
                    )
                subagent["llm"] = resolved_llm

            validated_subagents.append(SubAgentConfig.model_validate(subagent))

        return cls.model_validate({"subagents": validated_subagents})
