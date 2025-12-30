from unittest.mock import MagicMock

import pytest

from langrepl.configs import MCPServerConfig
from langrepl.mcp.factory import MCPFactory
from langrepl.sandboxes.backends.base import SandboxBackend, SandboxBinding


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

    @pytest.mark.asyncio
    async def test_server_blocked_when_no_sandbox_match(
        self, mock_mcp_config, mock_mcp_server_config
    ):
        mock_mcp_config.servers = {"test_server": mock_mcp_server_config}
        bindings = [
            SandboxBinding(
                patterns=["mcp:other:*"], backend=MagicMock(spec=SandboxBackend)
            )
        ]

        factory = MCPFactory()
        client = await factory.create(mock_mcp_config, sandbox_bindings=bindings)

        assert "test_server" not in client.connections

    @pytest.mark.asyncio
    async def test_server_blocked_when_multiple_matches(
        self, mock_mcp_config, mock_mcp_server_config
    ):
        mock_mcp_config.servers = {"test_server": mock_mcp_server_config}
        bindings = [
            SandboxBinding(
                patterns=["mcp:test_server:*"], backend=MagicMock(spec=SandboxBackend)
            ),
            SandboxBinding(
                patterns=["mcp:*:*"], backend=MagicMock(spec=SandboxBackend)
            ),
        ]

        factory = MCPFactory()
        client = await factory.create(mock_mcp_config, sandbox_bindings=bindings)

        assert "test_server" not in client.connections

    @pytest.mark.asyncio
    async def test_http_server_blocked_when_sandbox_assigned(self, mock_mcp_config):
        http_server = MCPServerConfig(
            url="http://localhost:8080",
            transport="streamable_http",
            enabled=True,
        )
        mock_mcp_config.servers = {"http_server": http_server}
        bindings = [
            SandboxBinding(
                patterns=["mcp:http_server:*"], backend=MagicMock(spec=SandboxBackend)
            )
        ]

        factory = MCPFactory()
        client = await factory.create(mock_mcp_config, sandbox_bindings=bindings)

        assert "http_server" not in client.connections

    @pytest.mark.asyncio
    async def test_http_server_allowed_when_bypass(self, mock_mcp_config):
        http_server = MCPServerConfig(
            url="http://localhost:8080",
            transport="streamable_http",
            enabled=True,
        )
        mock_mcp_config.servers = {"http_server": http_server}
        bindings = [SandboxBinding(patterns=["mcp:http_server:*"], backend=None)]

        factory = MCPFactory()
        client = await factory.create(mock_mcp_config, sandbox_bindings=bindings)

        assert "http_server" in client.connections

    @pytest.mark.asyncio
    async def test_negative_pattern_excludes_server(
        self, mock_mcp_config, mock_mcp_server_config
    ):
        mock_mcp_config.servers = {
            "server1": mock_mcp_server_config,
            "server2": MCPServerConfig(
                command="python", args=["-m", "other"], transport="stdio", enabled=True
            ),
        }
        bindings = [
            SandboxBinding(patterns=["mcp:*:*", "!mcp:server1:*"], backend=None)
        ]

        factory = MCPFactory()
        client = await factory.create(mock_mcp_config, sandbox_bindings=bindings)

        assert "server1" not in client.connections
        assert "server2" in client.connections
