import pytest
from pydantic import SecretStr

from langrepl.configs import LLMProvider, RateConfig
from langrepl.llms.factory import LLMFactory


class TestLLMFactoryCreateLimiter:
    def test_with_rate_config(self, mock_llm_config):
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

    def test_without_rate_config(self, mock_llm_config):
        config = mock_llm_config.model_copy(update={"rate_config": None})

        limiter = LLMFactory._create_limiter(config)

        assert limiter is None


class TestLLMFactoryGetHttpClients:
    def test_local_url_skips_proxy(self, mock_llm_settings):
        settings = mock_llm_settings.model_copy(
            update={"https_proxy": SecretStr("https://proxy.example.com:8443")}
        )
        factory = LLMFactory(settings)

        sync_client, async_client = factory._get_http_clients("http://localhost:1234")

        assert sync_client is None
        assert async_client is None

    def test_remote_url_uses_proxy(self, mock_llm_settings):
        settings = mock_llm_settings.model_copy(
            update={"https_proxy": SecretStr("https://proxy.example.com:8443")}
        )
        factory = LLMFactory(settings)

        sync_client, async_client = factory._get_http_clients("http://remote:1234")

        assert sync_client is not None
        assert async_client is not None


class TestLLMFactoryCreate:
    @pytest.mark.parametrize(
        ("provider", "api_key_field", "expected_class"),
        [
            (LLMProvider.OPENAI, "openai_api_key", "ChatOpenAI"),
            (LLMProvider.ANTHROPIC, "anthropic_api_key", "ChatAnthropic"),
            (LLMProvider.GOOGLE, "google_api_key", "ChatGoogleGenerativeAI"),
        ],
    )
    def test_create_model(
        self,
        mock_llm_settings,
        mock_llm_config,
        provider,
        api_key_field,
        expected_class,
    ):
        settings = mock_llm_settings.model_copy(
            update={api_key_field: SecretStr("test-key")}
        )
        config = mock_llm_config.model_copy(update={"provider": provider})

        model = LLMFactory(settings).create(config)

        assert model.__class__.__name__ == expected_class

    def test_unknown_provider_raises_error(self, mock_llm_settings, mock_llm_config):
        config = mock_llm_config.model_copy(update={"provider": LLMProvider.OPENAI})
        config.provider = "unknown"  # type: ignore[assignment]

        with pytest.raises(ValueError, match="Unknown LLM provider"):
            LLMFactory(mock_llm_settings).create(config)
