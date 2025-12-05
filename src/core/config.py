import asyncio
import json
import logging
import re
from enum import Enum
from pathlib import Path
from typing import Any, cast

import aiofiles
import yaml
from packaging import version as pkg_version
from pydantic import BaseModel, Field, model_validator

from src.core.constants import (
    AGENT_CONFIG_VERSION,
    CHECKPOINTER_CONFIG_VERSION,
    LLM_CONFIG_VERSION,
)
from src.utils.render import render_templates

logger = logging.getLogger(__name__)


def _migrate_items(
    items: list[dict], config_class: type["VersionedConfig"], file_path: Path
) -> tuple[list[dict], bool]:
    """Migrate config items to latest version.

    Returns:
        Tuple of (migrated_items, needs_save)
    """
    migrated_items: list[dict] = []
    needs_save = False
    latest_version = config_class.get_latest_version()

    for item in items:
        current_version = item.get("version", "0.0.0")

        if pkg_version.parse(current_version) < pkg_version.parse(latest_version):
            migrated_item = config_class.migrate(item, current_version)
            migrated_item["version"] = latest_version
            migrated_items.append(migrated_item)
            needs_save = True
        else:
            migrated_items.append(item)

    if needs_save:
        logger.warning(
            f"Migrating {config_class.__name__} to version {latest_version}: {file_path}"
        )

    return migrated_items, needs_save


async def _atomic_write(file_path: Path, content: str) -> None:
    """Write content to file atomically using temp file and replace."""
    temp_file = file_path.with_suffix(".tmp")
    try:
        await asyncio.to_thread(temp_file.write_text, content)
        await asyncio.to_thread(temp_file.replace, file_path)
    except Exception:
        if temp_file.exists():
            await asyncio.to_thread(temp_file.unlink)
        raise


def _validate_no_duplicates(items: list[dict], key: str, config_type: str) -> None:
    """Validate no duplicate keys in config items."""
    seen = set()
    for idx, item in enumerate(items):
        if key not in item:
            raise ValueError(
                f"Config item at index {idx} missing required key '{key}': {item}"
            )
        value = item[key]
        if value in seen:
            raise ValueError(
                f"Duplicate {config_type.lower()} '{key}': '{value}'. "
                f"Each {config_type.lower()} must have a unique {key}."
            )
        seen.add(value)


async def _load_dir_items(
    dir_path: Path,
    key: str | None = None,
    config_type: str | None = None,
    config_class: type["VersionedConfig"] | None = None,
) -> list[dict]:
    """Load and migrate config items from directory."""
    if not dir_path.exists():
        return []

    items: list[dict] = []
    yml_files = await asyncio.to_thread(lambda: sorted(dir_path.glob("*.yml")))
    for yml_file in yml_files:
        content = await asyncio.to_thread(yml_file.read_text)
        data = yaml.safe_load(content)

        is_list = isinstance(data, list)
        file_items = data if is_list else [data] if isinstance(data, dict) else []

        if config_class:
            migrated_items, needs_save = _migrate_items(
                file_items, config_class, yml_file
            )

            if needs_save:
                save_data = migrated_items if is_list else migrated_items[0]
                yaml_str = yaml.dump(
                    save_data, default_flow_style=False, sort_keys=False
                )
                await _atomic_write(yml_file, yaml_str)

            file_items = migrated_items

        if key and config_type:
            for item in file_items:
                if (item_key := item.get(key)) and item_key != yml_file.stem:
                    raise ValueError(
                        f"{config_type} file '{yml_file.name}' has {key}='{item_key}' "
                        f"but filename is '{yml_file.stem}'. Rename file to '{item_key}.yml'."
                    )

        items.extend(file_items)

    return items


async def _load_single_file(
    file_path: Path, key: str, config_class: type["VersionedConfig"]
) -> list[dict]:
    """Load and migrate config items from single file."""
    yaml_content = await asyncio.to_thread(file_path.read_text)
    data = yaml.safe_load(yaml_content)
    items = data.get(key, []) if isinstance(data, dict) else []

    migrated_items, needs_save = _migrate_items(items, config_class, file_path)

    if needs_save:
        data[key] = migrated_items
        yaml_str = yaml.dump(data, default_flow_style=False, sort_keys=False)
        await _atomic_write(file_path, yaml_str)

    return migrated_items


async def load_prompt_content(
    base_path: Path, prompt: str | list[str] | None
) -> str | None:
    """Load and concatenate prompt content from one or more files.

    Args:
        base_path: Base directory containing prompt files
        prompt: Single file path, list of file paths, or already-loaded content

    Returns:
        Concatenated prompt content with double newline separators, or None
    """
    if not prompt:
        return None

    if isinstance(prompt, str):
        prompt_path = base_path / prompt
        if prompt_path.exists() and prompt_path.is_file():
            return await asyncio.to_thread(prompt_path.read_text)
        return prompt

    if isinstance(prompt, list):
        contents = []
        for prompt_file in prompt:
            prompt_path = base_path / prompt_file
            if prompt_path.exists() and prompt_path.is_file():
                content = await asyncio.to_thread(prompt_path.read_text)
                contents.append(content)
            else:
                contents.append(prompt_file)
        return "\n\n".join(contents)

    return str(prompt)


class VersionedConfig(BaseModel):
    """Base class for versioned configs with migration support."""

    @classmethod
    def get_latest_version(cls) -> str:
        """Return latest version for this config type. Must be overridden by subclasses."""
        raise NotImplementedError(f"{cls.__name__} must implement get_latest_version()")

    @classmethod
    def migrate(cls, data: dict, from_version: str) -> dict:
        """Migrate config data from older version."""
        return data


class LLMProvider(str, Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    OLLAMA = "ollama"
    LMSTUDIO = "lmstudio"
    BEDROCK = "bedrock"
    DEEPSEEK = "deepseek"
    ZHIPUAI = "zhipuai"


class CheckpointerProvider(str, Enum):
    SQLITE = "sqlite"
    MEMORY = "memory"


class ApprovalMode(str, Enum):
    """Tool approval mode for interactive sessions."""

    SEMI_ACTIVE = "semi-active"  # No effect (default)
    ACTIVE = "active"  # Bypass all approval rules except "always_deny"
    AGGRESSIVE = "aggressive"  # Bypass all approval rules


class RateConfig(BaseModel):
    requests_per_second: float = Field(
        description="The maximum number of requests per second"
    )
    input_tokens_per_second: float = Field(
        description="The maximum number of input tokens per second"
    )
    output_tokens_per_second: float = Field(
        description="The maximum number of output tokens per second"
    )
    check_every_n_seconds: float = Field(
        description="The interval in seconds to check the rate limit"
    )
    max_bucket_size: int = Field(
        description="The maximum number of requests that can be stored in the bucket"
    )


class LLMConfig(VersionedConfig):
    version: str = Field(
        default=LLM_CONFIG_VERSION, description="Config schema version"
    )
    provider: LLMProvider = Field(description="The provider of the LLM")
    model: str = Field(description="The model to use")
    alias: str = Field(default="", description="Display alias for the model")
    max_tokens: int = Field(description="The maximum number of tokens to generate")
    temperature: float = Field(description="The temperature to use")
    streaming: bool = Field(default=True, description="Whether to stream the response")
    rate_config: RateConfig | None = Field(
        default=None, description="The rate config to use"
    )
    context_window: int | None = Field(
        default=None, description="Context window size in tokens"
    )
    input_cost_per_mtok: float | None = Field(
        default=None, description="Input token cost per million tokens"
    )
    output_cost_per_mtok: float | None = Field(
        default=None, description="Output token cost per million tokens"
    )
    extended_reasoning: dict[str, Any] | None = Field(
        default=None,
        description="Extended reasoning/thinking configuration (provider-agnostic)",
    )

    @classmethod
    def get_latest_version(cls) -> str:
        return LLM_CONFIG_VERSION

    @model_validator(mode="after")
    def set_alias_default(self) -> "LLMConfig":
        """Set alias to model name if not provided."""
        if not self.alias:
            self.alias = self.model
        return self


class CheckpointerConfig(VersionedConfig):
    version: str = Field(
        default=CHECKPOINTER_CONFIG_VERSION, description="Config schema version"
    )
    type: CheckpointerProvider = Field(description="The checkpointer type")

    @classmethod
    def get_latest_version(cls) -> str:
        return CHECKPOINTER_CONFIG_VERSION


class MCPServerConfig(VersionedConfig):
    command: str | None = Field(
        default=None, description="The command to execute the server"
    )
    url: str | None = Field(default=None, description="The URL of the server")
    headers: dict[str, str] | None = Field(
        default=None, description="Headers for the server connection"
    )
    args: list[str] = Field(
        default_factory=list, description="Arguments for the server command"
    )
    transport: str = Field(default="stdio", description="Transport protocol")
    env: dict[str, str] = Field(
        default_factory=dict, description="Environment variables"
    )
    include: list[str] = Field(default_factory=list, description="Tools to include")
    exclude: list[str] = Field(default_factory=list, description="Tools to exclude")
    enabled: bool = Field(default=True, description="Whether the server is enabled")
    repair_command: list[str] | None = Field(
        default=None,
        description="Command list to run if server initialization fails",
    )


class MCPConfig(BaseModel):
    servers: dict[str, MCPServerConfig] = Field(
        default_factory=dict, description="MCP server configurations"
    )

    @classmethod
    async def from_json(
        cls, path: Path, context: dict[str, Any] | None = None
    ) -> "MCPConfig":
        """Load MCP configuration from JSON file with template rendering.

        Args:
            path: Path to the entrypoints.json file
            context: Context variables for template rendering

        Returns:
            MCPConfig instance with rendered configuration
        """
        if not path.exists():
            return cls()
        context = context or {}
        async with aiofiles.open(path) as f:
            config_content = await f.read()

        config: dict[str, Any] = json.loads(config_content)
        rendered_config: dict = cast(dict, render_templates(config, context))
        mcp_servers = rendered_config.get("mcpServers", {})

        # Convert to our format
        servers = {}
        for name, server_config in mcp_servers.items():
            servers[name] = MCPServerConfig(**server_config)

        return cls(servers=servers)

    def to_json(self, path: Path):
        """Save MCP configuration to JSON file."""
        # Convert to mcpServers format
        mcp_servers = {}
        for name, server_config in self.servers.items():
            mcp_servers[name] = server_config.model_dump()

        config = {"mcpServers": mcp_servers}

        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(config, f, indent=2)


class BatchLLMConfig(BaseModel):
    llms: list[LLMConfig] = Field(description="The LLMs configurations")

    @property
    def llm_names(self) -> list[str]:
        return [llm.alias for llm in self.llms]

    def get_llm_config(self, llm_name: str) -> LLMConfig | None:
        return next((llm for llm in self.llms if llm.alias == llm_name), None)

    @classmethod
    async def from_yaml(
        cls,
        file_path: Path | None = None,
        dir_path: Path | None = None,
    ) -> "BatchLLMConfig":
        llms = []

        if file_path and file_path.exists():
            llms.extend(await _load_single_file(file_path, "llms", LLMConfig))

        if dir_path:
            llms.extend(await _load_dir_items(dir_path, config_class=LLMConfig))

        _validate_no_duplicates(llms, key="alias", config_type="LLM")
        return cls.model_validate({"llms": llms})


class BatchCheckpointerConfig(BaseModel):
    checkpointers: list[CheckpointerConfig] = Field(
        description="The checkpointer configurations"
    )

    @property
    def checkpointer_names(self) -> list[str]:
        return [cp.type for cp in self.checkpointers]

    def get_checkpointer_config(
        self, checkpointer_name: str
    ) -> CheckpointerConfig | None:
        return next(
            (cp for cp in self.checkpointers if cp.type == checkpointer_name), None
        )

    @classmethod
    async def from_yaml(
        cls,
        file_path: Path | None = None,
        dir_path: Path | None = None,
    ) -> "BatchCheckpointerConfig":
        checkpointers = []

        if file_path and file_path.exists():
            checkpointers.extend(
                await _load_single_file(file_path, "checkpointers", CheckpointerConfig)
            )

        if dir_path:
            checkpointers.extend(
                await _load_dir_items(
                    dir_path,
                    key="type",
                    config_type="Checkpointer",
                    config_class=CheckpointerConfig,
                )
            )

        _validate_no_duplicates(checkpointers, key="type", config_type="Checkpointer")
        return cls.model_validate({"checkpointers": checkpointers})


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

            from src.core.constants import CONFIG_DIR_NAME

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

                # Copy missing prompt files
                cls._copy_missing_prompts(default_prompts)

        return data


class SubAgentConfig(BaseAgentConfig):
    """Configuration for subagents (no checkpointer, no default, no compression)."""


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
    compression: CompressionConfig | None = Field(
        default=None, description="Compression configuration for context management"
    )


class BaseBatchConfig(BaseModel):
    """Base class for batch configurations with shared functionality."""


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
    ) -> "BatchSubAgentConfig":
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
    def validate_default_agent(self) -> "BatchAgentConfig":
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
    ):
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
    ):
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
    ) -> "BatchAgentConfig":
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
                            f"For agent '{agent["name"]}': subagent '{subagent_name}' not found. Available: {batch_subagent_config.subagent_names}"
                        )
                    resolved_subagents.append(resolved_subagent)
                agent["subagents"] = resolved_subagents

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


class ToolApprovalRule(BaseModel):
    """Rule for approving/denying specific tool calls"""

    name: str
    args: dict[str, Any] | None = None

    def matches_call(self, tool_name: str, tool_args: dict[str, Any]) -> bool:
        """Check if this rule matches a specific tool call"""
        if self.name != tool_name:
            return False

        # If no args specified, match any call to this tool
        if not self.args:
            return True

        # Check argument matches (exact or regex)
        for key, expected_value in self.args.items():
            if key not in tool_args:
                return False

            actual_value = str(tool_args[key])
            expected_str = str(expected_value)

            # Try exact match first (safer and more intuitive)
            if actual_value == expected_str:
                continue

            try:
                pattern = re.compile(expected_str)
                if pattern.fullmatch(actual_value):
                    continue
            except re.error:
                # Not a valid regex, already failed exact match above
                pass

            # No match found
            return False

        return True


class ToolApprovalConfig(BaseModel):
    """Configuration for tool approvals and denials"""

    always_allow: list[ToolApprovalRule] = Field(default_factory=list)
    always_deny: list[ToolApprovalRule] = Field(default_factory=list)

    @classmethod
    def from_json_file(cls, file_path: Path) -> "ToolApprovalConfig":
        """Load configuration from JSON file"""
        if not file_path.exists():
            return cls()

        try:
            with open(file_path) as f:
                content = f.read()
            return cls.model_validate_json(content)
        except Exception:
            return cls()

    def save_to_json_file(self, file_path: Path):
        """Save configuration to JSON file"""
        file_path.parent.mkdir(exist_ok=True)
        with open(file_path, "w") as f:
            f.write(self.model_dump_json(indent=2))
