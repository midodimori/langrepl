import pytest
from pydantic import SecretStr

from src.core.settings import settings
from src.mcp.factory import MCPFactory


class TestMCPFactory:
    @pytest.mark.asyncio
    async def test_create_with_no_servers(self, mock_mcp_config):
        factory = MCPFactory()

        client = await factory.create(mock_mcp_config)

        assert client is not None
        assert client.connections is not None
        assert len(client.connections) == 0

    @pytest.mark.asyncio
    async def test_create_with_disabled_server(
        self, mock_mcp_server_config, mock_mcp_config
    ):
        factory = MCPFactory()

        server_config = mock_mcp_server_config.model_copy(update={"enabled": False})
        config = mock_mcp_config.model_copy(
            update={"servers": {"test_server": server_config}}
        )

        client = await factory.create(config)

        assert client.connections is not None
        assert len(client.connections) == 0

    @pytest.mark.asyncio
    async def test_create_with_enabled_stdio_server(
        self, mock_mcp_server_config, mock_mcp_config
    ):
        factory = MCPFactory()

        config = mock_mcp_config.model_copy(
            update={"servers": {"test_server": mock_mcp_server_config}}
        )

        client = await factory.create(config)

        assert client.connections is not None
        assert "test_server" in client.connections

    @pytest.mark.asyncio
    async def test_proxy_injection_into_env(
        self, mock_mcp_server_config, mock_mcp_config
    ):
        factory = MCPFactory()

        server_config = mock_mcp_server_config.model_copy(update={"env": {}})
        config = mock_mcp_config.model_copy(
            update={"servers": {"test_server": server_config}}
        )

        original_http_proxy = settings.llm.http_proxy
        original_https_proxy = settings.llm.https_proxy

        settings.llm.http_proxy = SecretStr("http://proxy.example.com")
        settings.llm.https_proxy = SecretStr("https://proxy.example.com")

        try:
            client = await factory.create(config)

            assert client.connections is not None
            assert "test_server" in client.connections
        finally:
            settings.llm.http_proxy = original_http_proxy
            settings.llm.https_proxy = original_https_proxy

    @pytest.mark.asyncio
    async def test_tool_filters_extracted(
        self, mock_mcp_server_config, mock_mcp_config
    ):
        factory = MCPFactory()

        server_config = mock_mcp_server_config.model_copy(
            update={"include": ["tool1", "tool2"], "exclude": []}
        )
        config = mock_mcp_config.model_copy(
            update={"servers": {"test_server": server_config}}
        )

        client = await factory.create(config)

        assert client._tool_filters is not None
        assert "test_server" in client._tool_filters
        assert client._tool_filters["test_server"]["include"] == ["tool1", "tool2"]
