import pytest
from pydantic import SecretStr

from src.core.config import MCPConfig, MCPServerConfig
from src.core.settings import settings
from src.mcp.factory import MCPFactory


class TestMCPFactory:
    @pytest.mark.asyncio
    async def test_create_with_no_servers(self):
        factory = MCPFactory()
        config = MCPConfig(servers={})

        client = await factory.create(config)

        assert client is not None
        assert client.connections is not None
        assert len(client.connections) == 0

    @pytest.mark.asyncio
    async def test_create_with_disabled_server(self):
        factory = MCPFactory()

        server_config = MCPServerConfig(
            command="python",
            args=["-m", "server"],
            transport="stdio",
            enabled=False,
        )

        config = MCPConfig(servers={"test_server": server_config})

        client = await factory.create(config)

        assert client.connections is not None
        assert len(client.connections) == 0

    @pytest.mark.asyncio
    async def test_create_with_enabled_stdio_server(self):
        factory = MCPFactory()

        server_config = MCPServerConfig(
            command="python",
            args=["-m", "server"],
            transport="stdio",
            enabled=True,
        )

        config = MCPConfig(servers={"test_server": server_config})

        client = await factory.create(config)

        assert client.connections is not None
        assert "test_server" in client.connections

    @pytest.mark.asyncio
    async def test_proxy_injection_into_env(self):
        factory = MCPFactory()

        server_config = MCPServerConfig(
            command="python",
            args=["-m", "server"],
            transport="stdio",
            env={},
            enabled=True,
        )

        config = MCPConfig(servers={"test_server": server_config})

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
    async def test_tool_filters_extracted(self):
        factory = MCPFactory()

        server_config = MCPServerConfig(
            command="python",
            args=["-m", "server"],
            transport="stdio",
            include=["tool1", "tool2"],
            exclude=[],
            enabled=True,
        )

        config = MCPConfig(servers={"test_server": server_config})

        client = await factory.create(config)

        assert client._tool_filters is not None
        assert "test_server" in client._tool_filters
        assert client._tool_filters["test_server"]["include"] == ["tool1", "tool2"]
