import os

from dotenv import load_dotenv
from pydantic import BaseModel, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.core.constants import (
    DEFAULT_THEME,
)

load_dotenv(".env")

if os.getenv("SUPPRESS_GRPC_WARNINGS", "true").lower() == "true":
    os.environ["GRPC_VERBOSITY"] = "NONE"


class LLMSettings(BaseModel):
    openai_api_key: SecretStr = Field(
        default=SecretStr("dummy"), description="The OpenAI API key"
    )
    anthropic_api_key: SecretStr = Field(
        default=SecretStr("dummy"), description="The Anthropic API key"
    )
    google_api_key: SecretStr = Field(
        default=SecretStr("dummy"), description="The Google API key"
    )
    ollama_base_url: str = Field(
        default="http://localhost:11434", description="The Ollama API base URL"
    )
    deepseek_api_key: SecretStr = Field(
        default=SecretStr("dummy"), description="The DeepSeek API key"
    )
    zhipuai_api_key: SecretStr = Field(
        default=SecretStr("dummy"), description="The Zhipu AI API key"
    )
    lmstudio_base_url: str = Field(
        default="http://localhost:1234/v1", description="The LMStudio API base URL"
    )
    aws_access_key_id: SecretStr = Field(
        default=SecretStr(os.getenv("AWS_ACCESS_KEY_ID", "")),
        description="The AWS Access Key ID",
    )
    aws_secret_access_key: SecretStr = Field(
        default=SecretStr(os.getenv("AWS_SECRET_ACCESS_KEY", "")),
        description="The AWS Secret Access Key",
    )
    aws_session_token: SecretStr = Field(
        default=SecretStr(os.getenv("AWS_SESSION_TOKEN", "")),
        description="The AWS Session Token",
    )
    http_proxy: SecretStr = Field(
        default=SecretStr(os.getenv("HTTP_PROXY", os.getenv("http_proxy", ""))),
        description="HTTP proxy URL",
    )
    https_proxy: SecretStr = Field(
        default=SecretStr(os.getenv("HTTPS_PROXY", os.getenv("https_proxy", ""))),
        description="HTTPS proxy URL",
    )


class ToolSettings(BaseModel):
    # Grep settings
    max_columns: int = Field(
        default=1500, description="The maximum number of columns to show"
    )
    context_lines: int = Field(
        default=2, description="The number of context lines to show"
    )
    search_limit: int = Field(default=25, description="The number of results to show")

    def model_dump(self, hide_secret_str: bool = True, *args, **kwargs):
        dump = super().model_dump(*args, **kwargs)
        if hide_secret_str:
            return dump
        else:
            return dump | {
                key: value.get_secret_value()
                for key, value in dump.items()
                if isinstance(value, SecretStr)
            }


class CLISettings(BaseModel):
    """CLI-specific settings."""

    # Appearance settings
    theme: str = Field(default=DEFAULT_THEME, description="UI theme")
    prompt_style: str = Field(default="❯ ", description="Prompt style")

    # Behavior settings
    enable_word_wrap: bool = Field(default=True, description="Enable word wrap")
    editor: str = Field(
        default="nano", description="Default text editor for /memory command"
    )

    # Autocomplete settings
    max_autocomplete_suggestions: int = Field(
        default=10, description="Maximum number of autocomplete suggestions to show"
    )


class ServerSettings(BaseModel):
    """LangGraph server settings."""

    langgraph_server_url: str = Field(
        default="http://localhost:2024", description="LangGraph server URL"
    )


class Settings(BaseSettings):
    log_level: str = Field(default="INFO", description="The log level")
    log_file: str = Field(default="app.log", description="The log file")
    suppress_grpc_warnings: bool = Field(
        default=True, description="Suppress gRPC warnings"
    )
    llm: LLMSettings = Field(
        default_factory=LLMSettings, description="The LLM settings"
    )
    tool_settings: ToolSettings = Field(
        default_factory=ToolSettings, description="The tool settings"
    )
    cli: CLISettings = Field(
        default_factory=CLISettings, description="The CLI settings"
    )
    server: ServerSettings = Field(
        default_factory=ServerSettings, description="The server settings"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_nested_delimiter="__",
        case_sensitive=False,
        extra="allow",
        frozen=True,
        env_file_encoding="utf-8",
    )


settings = Settings()
