import pytest

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
    async def test_create_with_disabled_servers(
        self, mock_mcp_config, mock_mcp_server_config
    ):
        mock_mcp_server_config.enabled = False
        mock_mcp_config.servers = {"test_server": mock_mcp_server_config}

        factory = MCPFactory()
        client = await factory.create(mock_mcp_config)

        assert len(client.connections) == 0

    @pytest.mark.asyncio
    async def test_create_with_enabled_servers(
        self, mock_mcp_config, mock_mcp_server_config
    ):
        mock_mcp_server_config.enabled = True
        mock_mcp_config.servers = {"test_server": mock_mcp_server_config}

        factory = MCPFactory()
        client = await factory.create(mock_mcp_config)

        assert len(client.connections) == 1
        assert "test_server" in client.connections

    @pytest.mark.asyncio
    async def test_caching(self, mock_mcp_config, mock_mcp_server_config):
        mock_mcp_server_config.enabled = True
        mock_mcp_config.servers = {"test_server": mock_mcp_server_config}

        factory = MCPFactory()
        client1 = await factory.create(mock_mcp_config)
        client2 = await factory.create(mock_mcp_config)

        assert client1 is client2

    @pytest.mark.asyncio
    async def test_cache_invalidated_on_config_change(
        self, mock_mcp_config, mock_mcp_server_config
    ):
        mock_mcp_server_config.enabled = True
        mock_mcp_server_config.headers = {"Authorization": "token1"}
        mock_mcp_config.servers = {"test_server": mock_mcp_server_config}

        factory = MCPFactory()
        client1 = await factory.create(mock_mcp_config)

        mock_mcp_config.servers["test_server"].headers = {"Authorization": "token2"}
        client2 = await factory.create(mock_mcp_config)

        assert client1 is not client2
