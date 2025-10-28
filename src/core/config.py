import asyncio
import json
import re
from enum import Enum
from pathlib import Path
from typing import Any, cast

import aiofiles
import yaml
from pydantic import BaseModel, Field, model_validator

from src.utils.render import render_templates


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


class LLMConfig(BaseModel):
    provider: LLMProvider = Field(description="The provider of the LLM")
    model: str = Field(description="The model to use")
    alias: str = Field(default="", description="Display alias for the model")
    max_tokens: int = Field(description="The maximum number of tokens to generate")
    temperature: float = Field(description="The temperature to use")
    streaming: bool = Field(default=False, description="Whether to stream the response")
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

    @model_validator(mode="after")
    def set_alias_default(self) -> "LLMConfig":
        """Set alias to model name if not provided."""
        if not self.alias:
            self.alias = self.model
        return self


class CheckpointerConfig(BaseModel):
    type: CheckpointerProvider = Field(description="The checkpointer type")
    max_connections: int = Field(default=10, description="Maximum database connections")


class MCPServerConfig(BaseModel):
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
    async def from_yaml(cls, path: Path) -> "BatchLLMConfig":
        yaml_content = await asyncio.to_thread(path.read_text)
        data = yaml.unsafe_load(yaml_content)
        return cls(**data)


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
    async def from_yaml(cls, path: Path) -> "BatchCheckpointerConfig":
        yaml_content = await asyncio.to_thread(path.read_text)
        data = yaml.unsafe_load(yaml_content)
        return cls(**data)


class CompressionConfig(BaseModel):
    auto_compress_enabled: bool = Field(
        default=True, description="Enable automatic compression"
    )
    auto_compress_threshold: float = Field(
        default=0.8,
        description="Trigger compression at this context usage ratio (0.0-1.0)",
    )
    compression_llm: LLMConfig | None = Field(
        default=None,
        description="LLM to use for summarization (defaults to agent's main llm)",
    )


class AgentConfig(BaseModel):
    name: str = Field(default="Unknown", description="The name of the agent")
    prompt: str | list[str] = Field(
        default="",
        description="The prompt to use for the agent (single file path or list of file paths)",
    )
    llm: LLMConfig = Field(description="The LLM to use for the agent")
    checkpointer: CheckpointerConfig | None = Field(
        default=None,
        description="The checkpointer configuration (optional for subagents)",
    )
    default: bool = Field(
        default=False, description="Whether this is the default agent"
    )
    recursion_limit: int = Field(
        default=25, description="Maximum number of execution steps"
    )
    tools: list[str] | None = Field(default=None, description="Tool references")
    description: str = Field(
        default="",
        description="Description of the agent (used for subagents in task tool)",
    )
    subagents: list["AgentConfig"] | None = Field(
        default=None, description="List of resolved subagent configurations"
    )
    compression: CompressionConfig | None = Field(
        default=None, description="Compression configuration for context management"
    )
    tool_output_max_tokens: int | None = Field(
        default=None,
        description="Maximum tokens per tool output. Larger outputs stored in virtual filesystem.",
    )


class BatchAgentConfig(BaseModel):
    agents: list[AgentConfig] = Field(description="The agents to use for the graph")

    @property
    def agent_names(self) -> list[str]:
        return [agent.name for agent in self.agents]

    def get_agent_config(self, agent_name: str | None) -> AgentConfig | None:
        """Get agent config by name, or default agent if name is None."""
        if agent_name is None:
            return self.get_default_agent()
        return next((agent for agent in self.agents if agent.name == agent_name), None)

    def get_default_agent(self) -> AgentConfig | None:
        """Get the default agent.

        Returns:
            The agent marked as default, or the first agent if none marked, or None if no agents.
        """
        default = next((a for a in self.agents if a.default), None)
        if default:
            return default
        return self.agents[0] if self.agents else None

    @model_validator(mode="after")
    def validate_default_agent(self) -> "BatchAgentConfig":
        """Ensure exactly one default agent when there's only one agent, and at most one default otherwise."""
        defaults = [a for a in self.agents if a.default]

        # If only one agent exists, it must be marked as default
        if len(self.agents) == 1 and not self.agents[0].default:
            raise ValueError(
                f"Agent '{self.agents[0].name}' must be marked as default=true "
                "when it is the only agent in the configuration."
            )

        # Ensure at most one agent is marked as default
        if len(defaults) > 1:
            raise ValueError(
                f"Multiple agents marked as default: {[a.name for a in defaults]}. "
                "Only one agent can be marked as default."
            )

        return self

    @staticmethod
    async def update_agent_llm(path: Path, agent_name: str, new_llm_name: str):
        """Update a specific agent's LLM in the YAML file without modifying other fields."""
        yaml_content = await asyncio.to_thread(path.read_text)
        data = yaml.unsafe_load(yaml_content)

        agents: list[dict] = data.get("agents", [])
        for agent in agents:
            if agent.get("name") == agent_name:
                agent["llm"] = new_llm_name
                break

        with open(path, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)

    @staticmethod
    async def update_default_agent(path: Path, agent_name: str):
        """Update which agent is marked as default in the YAML file."""
        yaml_content = await asyncio.to_thread(path.read_text)
        data = yaml.unsafe_load(yaml_content)

        agents: list[dict] = data.get("agents", [])
        for agent in agents:
            agent["default"] = agent.get("name") == agent_name

        with open(path, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)

    @classmethod
    async def from_yaml(
        cls,
        path: Path,
        batch_llm_config: BatchLLMConfig | None = None,
        batch_checkpointer_config: BatchCheckpointerConfig | None = None,
        batch_subagent_config: "BatchAgentConfig | None" = None,
    ) -> "BatchAgentConfig":
        yaml_content = await asyncio.to_thread(path.read_text)
        data = yaml.unsafe_load(yaml_content)

        agents: list[dict] = data.get("agents", [])
        if not agents:
            raise ValueError("No agents found in YAML file")

        for agent in agents:
            if prompt_content := agent.get("prompt", ""):
                agent["prompt"] = await cls._load_prompt_content(
                    path.parent, prompt_content
                )

            # Resolve LLM by name if string reference
            if batch_llm_config and isinstance(agent.get("llm"), str):
                llm_name = agent["llm"]
                resolved_llm = batch_llm_config.get_llm_config(llm_name)
                if not resolved_llm:
                    raise ValueError(
                        f"LLM '{llm_name}' not found. Available: {batch_llm_config.llm_names}"
                    )
                agent["llm"] = resolved_llm

            # Resolve checkpointer by name if string reference
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

            # Resolve subagents by name if list of string references
            if batch_subagent_config and isinstance(agent.get("subagents"), list):
                subagent_names = agent["subagents"]
                resolved_subagents = []
                for subagent_name in subagent_names:
                    resolved_subagent = batch_subagent_config.get_agent_config(
                        subagent_name
                    )
                    if not resolved_subagent:
                        raise ValueError(
                            f"Subagent '{subagent_name}' not found. Available: {batch_subagent_config.agent_names}"
                        )
                    resolved_subagents.append(resolved_subagent)
                agent["subagents"] = resolved_subagents

            # Resolve compression LLM if specified, or default to agent's main LLM
            if agent.get("compression"):
                compression = agent["compression"]
                if isinstance(compression.get("compression_llm"), str):
                    compression_llm_name = compression["compression_llm"]
                    if batch_llm_config:
                        resolved_compression_llm = batch_llm_config.get_llm_config(
                            compression_llm_name
                        )
                        if not resolved_compression_llm:
                            raise ValueError(
                                f"Compression LLM '{compression_llm_name}' not found. Available: {batch_llm_config.llm_names}"
                            )
                        compression["compression_llm"] = resolved_compression_llm
                elif compression.get("compression_llm") is None:
                    # Default to agent's main LLM
                    compression["compression_llm"] = agent["llm"]

        return cls(**data)

    @staticmethod
    async def _load_prompt_content(base_path: Path, prompt: str | list[str]) -> str:
        """Load and concatenate prompt content from one or more files.

        Args:
            base_path: Base directory containing prompt files
            prompt: Single file path or list of file paths relative to base_path

        Returns:
            Concatenated prompt content with double newline separators
        """
        # Handle single prompt path
        if isinstance(prompt, str):
            prompt_path = base_path / prompt
            if prompt_path.exists() and prompt_path.is_file():
                return await asyncio.to_thread(prompt_path.read_text)
            return prompt

        # Handle list of prompt paths
        contents = []
        for prompt_file in prompt:
            prompt_path = base_path / prompt_file
            if prompt_path.exists() and prompt_path.is_file():
                content = await asyncio.to_thread(prompt_path.read_text)
                contents.append(content)
            else:
                # If path doesn't exist, treat as literal string
                contents.append(prompt_file)

        # Join with double newlines for clear separation
        return "\n\n".join(contents)


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
