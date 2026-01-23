from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import urlparse

import httpx
from botocore.config import Config
from pydantic import SecretStr

from langrepl.configs import LLMConfig, LLMProvider
from langrepl.core.settings import LLMSettings
from langrepl.utils.rate_limiter import TokenBucketLimiter

if TYPE_CHECKING:
    from langchain_core.language_models.chat_models import BaseChatModel

_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


class LLMFactory:
    def __init__(self, llm_settings: LLMSettings):
        self.llm_settings = llm_settings
        self._proxy_dict = self._get_proxy_dict()
        self._proxy = self._proxy_dict.get("https") or self._proxy_dict.get("http")
        self._llm_cache: dict[int, BaseChatModel] = {}

    def _get_proxy_dict(self):
        http_proxy = self.llm_settings.http_proxy.get_secret_value()
        https_proxy = self.llm_settings.https_proxy.get_secret_value()
        return {k: v for k, v in [("http", http_proxy), ("https", https_proxy)] if v}

    @staticmethod
    def _is_local_url(url: str) -> bool:
        return urlparse(url).hostname in _LOCAL_HOSTS

    def _get_http_clients(self, base_url: str | None = None):
        if not self._proxy_dict or (base_url and self._is_local_url(base_url)):
            return None, None

        # Use per-scheme mounts when http and https proxies differ
        if (
            len(self._proxy_dict) == 2
            and self._proxy_dict["http"] != self._proxy_dict["https"]
        ):
            sync_mounts = {
                f"{k}://": httpx.HTTPTransport(proxy=v)
                for k, v in self._proxy_dict.items()
            }
            async_mounts = {
                f"{k}://": httpx.AsyncHTTPTransport(proxy=v)
                for k, v in self._proxy_dict.items()
            }
            return httpx.Client(mounts=sync_mounts), httpx.AsyncClient(
                mounts=async_mounts
            )

        return httpx.Client(proxy=self._proxy), httpx.AsyncClient(proxy=self._proxy)

    def _get_ollama_kwargs(self, base_url: str):
        if not self._proxy_dict or self._is_local_url(base_url):
            return {}

        # Use per-scheme proxies when http and https differ
        if (
            len(self._proxy_dict) == 2
            and self._proxy_dict["http"] != self._proxy_dict["https"]
        ):
            return {
                "client_kwargs": {
                    "proxies": {f"{k}://": v for k, v in self._proxy_dict.items()}
                }
            }

        return {"client_kwargs": {"proxy": self._proxy}}

    def _get_bedrock_config(self):
        return Config(proxies=self._proxy_dict) if self._proxy_dict else None

    @staticmethod
    def _create_limiter(config: LLMConfig):
        return (
            TokenBucketLimiter(
                requests_per_second=config.rate_config.requests_per_second,
                input_tokens_per_second=config.rate_config.input_tokens_per_second,
                output_tokens_per_second=config.rate_config.output_tokens_per_second,
                check_every_n_seconds=config.rate_config.check_every_n_seconds,
                max_bucket_size=config.rate_config.max_bucket_size,
            )
            if config.rate_config
            else None
        )

    @staticmethod
    def _get_config_hash(config: LLMConfig) -> int:
        return hash(
            (
                config.provider,
                config.model,
                config.temperature,
                config.max_tokens,
                config.streaming,
                str(config.extended_reasoning) if config.extended_reasoning else None,
            )
        )

    def create(self, config: LLMConfig) -> BaseChatModel:
        config_hash = self._get_config_hash(config)
        if config_hash in self._llm_cache:
            return self._llm_cache[config_hash]

        limiter = self._create_limiter(config)
        llm: BaseChatModel

        if config.provider == LLMProvider.OPENAI:
            from langchain_openai import ChatOpenAI

            http_client, http_async_client = self._get_http_clients()
            kwargs = {
                "api_key": self.llm_settings.openai_api_key,
                "model": config.model,
                "max_completion_tokens": config.max_tokens,
                "temperature": config.temperature,
                "streaming": config.streaming,
                "rate_limiter": limiter,
                "http_client": http_client,
                "http_async_client": http_async_client,
            }

            if config.extended_reasoning:
                kwargs["reasoning"] = config.extended_reasoning
                kwargs["output_version"] = "responses/v1"

            llm = ChatOpenAI(**kwargs)
        elif config.provider == LLMProvider.ANTHROPIC:
            from langchain_anthropic import ChatAnthropic

            kwargs = {
                "api_key": self.llm_settings.anthropic_api_key,
                "model_name": config.model,
                "max_tokens_to_sample": config.max_tokens,
                "temperature": config.temperature,
                "streaming": config.streaming,
                "rate_limiter": limiter,
                "timeout": None,
                "stop": None,
            }

            if config.extended_reasoning:
                kwargs["thinking"] = config.extended_reasoning

            llm = ChatAnthropic(**kwargs)
        elif config.provider == LLMProvider.GOOGLE:
            from langchain_google_genai import ChatGoogleGenerativeAI

            kwargs = {
                "api_key": self.llm_settings.google_api_key.get_secret_value(),
                "model": config.model,
                "max_tokens": config.max_tokens,
                "temperature": config.temperature,
                "disable_streaming": not config.streaming,
                "rate_limiter": limiter,
            }

            if config.extended_reasoning:
                kwargs.update(config.extended_reasoning)

            llm = ChatGoogleGenerativeAI(**kwargs)
        elif config.provider == LLMProvider.OLLAMA:
            from langchain_ollama import ChatOllama

            base_url = self.llm_settings.ollama_base_url
            llm = ChatOllama(
                base_url=base_url,
                model=config.model,
                num_predict=config.max_tokens,
                temperature=config.temperature,
                disable_streaming=not config.streaming,
                rate_limiter=limiter,
                **self._get_ollama_kwargs(base_url),
            )
        elif config.provider == LLMProvider.LMSTUDIO:
            from langchain_openai import ChatOpenAI

            base_url = self.llm_settings.lmstudio_base_url
            http_client, http_async_client = self._get_http_clients(base_url)
            llm = ChatOpenAI(
                base_url=base_url,
                model=config.model,
                max_completion_tokens=config.max_tokens,
                temperature=config.temperature,
                streaming=config.streaming,
                api_key=SecretStr("SOME_KEY"),
                rate_limiter=limiter,
                http_client=http_client,
                http_async_client=http_async_client,
            )
        elif config.provider == LLMProvider.BEDROCK:
            from langchain_aws import ChatBedrock

            kwargs = {
                "aws_access_key_id": self.llm_settings.aws_access_key_id,
                "aws_secret_access_key": self.llm_settings.aws_secret_access_key,
                "aws_session_token": self.llm_settings.aws_session_token,
                "model": config.model,
                "max_tokens": config.max_tokens,
                "temperature": config.temperature,
                "streaming": config.streaming,
                "rate_limiter": limiter,
                "config": self._get_bedrock_config(),
            }

            if config.extended_reasoning:
                kwargs["model_kwargs"] = {"thinking": config.extended_reasoning}

            llm = ChatBedrock(**kwargs)
        elif config.provider == LLMProvider.DEEPSEEK:
            from langchain_deepseek import ChatDeepSeek

            http_client, http_async_client = self._get_http_clients()
            llm = ChatDeepSeek(
                api_key=self.llm_settings.deepseek_api_key,
                model=config.model,
                max_tokens=config.max_tokens,
                temperature=config.temperature,
                streaming=config.streaming,
                rate_limiter=limiter,
                http_client=http_client,
                http_async_client=http_async_client,
            )
        elif config.provider == LLMProvider.ZHIPUAI:
            from langrepl.llms.wrappers.zhipuai import ChatZhipuAI

            kwargs = {
                "api_key": self.llm_settings.zhipuai_api_key.get_secret_value(),
                "model": config.model,
                "max_tokens": config.max_tokens,
                "temperature": config.temperature,
                "streaming": config.streaming,
                "rate_limiter": limiter,
            }

            if config.extended_reasoning:
                kwargs["thinking"] = config.extended_reasoning

            llm = ChatZhipuAI(**kwargs)
        else:
            raise ValueError(f"Unknown LLM provider: {config.provider}")

        self._llm_cache[config_hash] = llm
        return llm
