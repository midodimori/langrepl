"""LLM configuration classes."""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, model_validator

from langrepl.configs.base import VersionedConfig
from langrepl.configs.utils import (
    _load_dir_items,
    _load_single_file,
    _validate_no_duplicates,
)
from langrepl.core.constants import LLM_CONFIG_VERSION


class LLMProvider(str, Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    OLLAMA = "ollama"
    LMSTUDIO = "lmstudio"
    BEDROCK = "bedrock"
    DEEPSEEK = "deepseek"
    ZHIPUAI = "zhipuai"


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
    def set_alias_default(self) -> LLMConfig:
        """Set alias to model name if not provided."""
        if not self.alias:
            self.alias = self.model
        return self


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
    ) -> BatchLLMConfig:
        llms = []

        if file_path and file_path.exists():
            llms.extend(await _load_single_file(file_path, "llms", LLMConfig))

        if dir_path:
            llms.extend(await _load_dir_items(dir_path, config_class=LLMConfig))

        _validate_no_duplicates(llms, key="alias", config_type="LLM")
        return cls.model_validate({"llms": llms})
