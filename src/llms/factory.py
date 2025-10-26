import httpx
from botocore.config import Config
from langchain_anthropic import ChatAnthropic
from langchain_aws import ChatBedrock
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_deepseek import ChatDeepSeek
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from src.core.config import LLMConfig, LLMProvider
from src.core.settings import LLMSettings
from src.llms.wrappers.zhipuai import ChatZhipuAI
from src.utils.rate_limiter import TokenBucketLimiter


class LLMFactory:
    def __init__(self, llm_settings: LLMSettings):
        self.llm_settings = llm_settings
        self._proxy_dict = self._get_proxy_dict()
        self._bedrock_config = self._create_bedrock_config()
        self._ollama_kwargs = self._get_ollama_kwargs()
        self.http_client, self.http_async_client = self._create_http_clients()
        self._llm_cache: dict[int, BaseChatModel] = {}

    def _get_proxy_dict(self):
        http_proxy = self.llm_settings.http_proxy.get_secret_value()
        https_proxy = self.llm_settings.https_proxy.get_secret_value()
        return {k: v for k, v in [("http", http_proxy), ("https", https_proxy)] if v}

    def _create_http_clients(self):
        if not self._proxy_dict:
            return None, None

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

        proxy = self._proxy_dict.get("https") or self._proxy_dict.get("http")
        return httpx.Client(proxy=proxy), httpx.AsyncClient(proxy=proxy)

    def _get_ollama_kwargs(self):
        if not self._proxy_dict:
            return {}
        return {
            "client_kwargs": {
                "proxies": {f"{k}://": v for k, v in self._proxy_dict.items()}
            }
        }

    def _create_bedrock_config(self):
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
            kwargs = {
                "api_key": self.llm_settings.openai_api_key,
                "model": config.model,
                "max_completion_tokens": config.max_tokens,
                "temperature": config.temperature,
                "streaming": config.streaming,
                "rate_limiter": limiter,
                "http_client": self.http_client,
                "http_async_client": self.http_async_client,
            }

            if config.extended_reasoning:
                kwargs["reasoning"] = config.extended_reasoning
                kwargs["output_version"] = "responses/v1"

            llm = ChatOpenAI(**kwargs)
        elif config.provider == LLMProvider.ANTHROPIC:
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
            llm = ChatOllama(
                base_url=self.llm_settings.ollama_base_url,
                model=config.model,
                num_predict=config.max_tokens,
                temperature=config.temperature,
                disable_streaming=not config.streaming,
                rate_limiter=limiter,
                **self._ollama_kwargs,
            )
        elif config.provider == LLMProvider.LMSTUDIO:
            llm = ChatOpenAI(
                base_url=self.llm_settings.lmstudio_base_url,
                model=config.model,
                max_completion_tokens=config.max_tokens,
                temperature=config.temperature,
                streaming=config.streaming,
                api_key=SecretStr("SOME_KEY"),
                rate_limiter=limiter,
                http_client=self.http_client,
                http_async_client=self.http_async_client,
            )
        elif config.provider == LLMProvider.BEDROCK:
            kwargs = {
                "aws_access_key_id": self.llm_settings.aws_access_key_id,
                "aws_secret_access_key": self.llm_settings.aws_secret_access_key,
                "aws_session_token": self.llm_settings.aws_session_token,
                "model": config.model,
                "max_tokens": config.max_tokens,
                "temperature": config.temperature,
                "streaming": config.streaming,
                "rate_limiter": limiter,
                "config": self._bedrock_config,
            }

            if config.extended_reasoning:
                kwargs["model_kwargs"] = {"thinking": config.extended_reasoning}

            llm = ChatBedrock(**kwargs)
        elif config.provider == LLMProvider.DEEPSEEK:
            llm = ChatDeepSeek(
                api_key=self.llm_settings.deepseek_api_key,
                model=config.model,
                max_tokens=config.max_tokens,
                temperature=config.temperature,
                streaming=config.streaming,
                rate_limiter=limiter,
                http_client=self.http_client,
                http_async_client=self.http_async_client,
            )
        elif config.provider == LLMProvider.ZHIPUAI:
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
