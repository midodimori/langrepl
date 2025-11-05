import pytest
from pydantic import SecretStr

from src.core.config import LLMProvider, RateConfig
from src.llms.factory import LLMFactory


class TestLLMFactoryCreateLimiter:
    def test_create_limiter_with_rate_config(self, mock_llm_config):
        config = mock_llm_config.model_copy(
            update={
                "rate_config": RateConfig(
                    requests_per_second=10.0,
                    input_tokens_per_second=1000.0,
                    output_tokens_per_second=500.0,
                    check_every_n_seconds=0.1,
                    max_bucket_size=5,
                )
            }
        )

        limiter = LLMFactory._create_limiter(config)

        assert limiter is not None
        assert limiter.requests_per_second == 10.0
        assert limiter.input_tokens_per_second == 1000.0
        assert limiter.output_tokens_per_second == 500.0

    def test_create_limiter_without_rate_config(self, mock_llm_config):
        config = mock_llm_config.model_copy(update={"rate_config": None})

        limiter = LLMFactory._create_limiter(config)

        assert limiter is None


class TestLLMFactoryGetProxyDict:
    def test_no_proxies(self, mock_llm_settings):
        factory = LLMFactory(mock_llm_settings)

        proxies = factory._get_proxy_dict()

        assert proxies == {}

    def test_http_proxy_only(self, mock_llm_settings):
        settings = mock_llm_settings.model_copy(
            update={"http_proxy": SecretStr("http://proxy.example.com:8080")}
        )
        factory = LLMFactory(settings)

        proxies = factory._get_proxy_dict()

        assert proxies == {"http": "http://proxy.example.com:8080"}

    def test_https_proxy_only(self, mock_llm_settings):
        settings = mock_llm_settings.model_copy(
            update={"https_proxy": SecretStr("https://proxy.example.com:8443")}
        )
        factory = LLMFactory(settings)

        proxies = factory._get_proxy_dict()

        assert proxies == {"https": "https://proxy.example.com:8443"}

    def test_both_proxies(self, mock_llm_settings):
        settings = mock_llm_settings.model_copy(
            update={
                "http_proxy": SecretStr("http://proxy.example.com:8080"),
                "https_proxy": SecretStr("https://proxy.example.com:8443"),
            }
        )
        factory = LLMFactory(settings)

        proxies = factory._get_proxy_dict()

        assert proxies == {
            "http": "http://proxy.example.com:8080",
            "https": "https://proxy.example.com:8443",
        }


class TestLLMFactoryCreateHttpClients:
    def test_no_proxies_returns_none(self, mock_llm_settings):
        factory = LLMFactory(mock_llm_settings)

        sync_client, async_client = factory._create_http_clients()

        assert sync_client is None
        assert async_client is None

    def test_with_proxies_creates_clients(self, mock_llm_settings):
        settings = mock_llm_settings.model_copy(
            update={
                "http_proxy": SecretStr("http://proxy.example.com:8080"),
                "https_proxy": SecretStr("https://proxy.example.com:8443"),
            }
        )
        factory = LLMFactory(settings)

        sync_client, async_client = factory._create_http_clients()

        assert sync_client is not None
        assert async_client is not None


class TestLLMFactoryCreate:
    def test_create_openai_model(self, mock_llm_settings, mock_llm_config):
        settings = mock_llm_settings.model_copy(
            update={"openai_api_key": SecretStr("test-key")}
        )
        factory = LLMFactory(settings)

        config = mock_llm_config.model_copy(
            update={
                "provider": LLMProvider.OPENAI,
                "model": "gpt-4",
                "max_tokens": 1000,
                "temperature": 0.7,
            }
        )

        model = factory.create(config)

        assert model is not None
        assert model.__class__.__name__ == "ChatOpenAI"

    def test_create_anthropic_model(self, mock_llm_settings, mock_llm_config):
        settings = mock_llm_settings.model_copy(
            update={"anthropic_api_key": SecretStr("test-key")}
        )
        factory = LLMFactory(settings)

        config = mock_llm_config.model_copy(
            update={
                "provider": LLMProvider.ANTHROPIC,
                "model": "claude-3-opus-20240229",
                "max_tokens": 1000,
                "temperature": 0.7,
            }
        )

        model = factory.create(config)

        assert model is not None
        assert model.__class__.__name__ == "ChatAnthropic"

    def test_create_google_model(self, mock_llm_settings, mock_llm_config):
        settings = mock_llm_settings.model_copy(
            update={"google_api_key": SecretStr("test-key")}
        )
        factory = LLMFactory(settings)

        config = mock_llm_config.model_copy(
            update={
                "provider": LLMProvider.GOOGLE,
                "model": "gemini-pro",
                "max_tokens": 1000,
                "temperature": 0.7,
            }
        )

        model = factory.create(config)

        assert model is not None
        assert model.__class__.__name__ == "ChatGoogleGenerativeAI"

    def test_create_unknown_provider_raises_error(
        self, mock_llm_settings, mock_llm_config
    ):
        factory = LLMFactory(mock_llm_settings)

        config = mock_llm_config.model_copy(
            update={
                "provider": LLMProvider.OPENAI,
                "model": "test-model",
                "max_tokens": 1000,
                "temperature": 0.7,
            }
        )

        config.provider = "unknown_provider"  # type: ignore[assignment]

        with pytest.raises(ValueError, match="Unknown LLM provider"):
            factory.create(config)
