"""Tests for MCP handler."""

from unittest.mock import AsyncMock, patch

import pytest

from src.cli.handlers.mcp import MCPHandler
from src.core.config import MCPConfig


class TestMCPHandler:
    """Tests for MCPHandler class."""

    @pytest.mark.asyncio
    @patch("src.cli.handlers.mcp.initializer.load_mcp_config")
    async def test_handle_with_no_servers(
        self, mock_load_mcp, mock_session, mock_mcp_config
    ):
        """Test that handle shows error when no MCP servers configured."""
        handler = MCPHandler(mock_session)
        mock_load_mcp.return_value = mock_mcp_config

        await handler.handle()

        mock_load_mcp.assert_called_once_with(mock_session.context.working_dir)

    @pytest.mark.asyncio
    @patch("src.cli.handlers.mcp.initializer.save_mcp_config")
    @patch("src.cli.handlers.mcp.initializer.load_mcp_config")
    async def test_handle_with_servers_and_modifications(
        self, mock_load_mcp, mock_save_mcp, mock_session, mock_mcp_server_config
    ):
        """Test that handle saves changes when modifications are made."""
        handler = MCPHandler(mock_session)

        mcp_config = MCPConfig(servers={"server1": mock_mcp_server_config})
        mock_load_mcp.return_value = mcp_config

        with patch.object(handler, "_get_mcp_selection", return_value=True):
            await handler.handle()

            mock_save_mcp.assert_called_once_with(
                mcp_config, mock_session.context.working_dir
            )
            assert mock_session.needs_reload is True
            assert mock_session.running is False

    @pytest.mark.asyncio
    @patch("src.cli.handlers.mcp.initializer.load_mcp_config")
    async def test_handle_with_no_modifications(
        self, mock_load_mcp, mock_session, mock_mcp_server_config
    ):
        """Test that handle does not save when no modifications made."""
        handler = MCPHandler(mock_session)

        mcp_config = MCPConfig(servers={"server1": mock_mcp_server_config})
        mock_load_mcp.return_value = mcp_config

        with patch.object(handler, "_get_mcp_selection", return_value=False):
            await handler.handle()

            assert mock_session.needs_reload is False

    @pytest.mark.asyncio
    @patch("src.cli.handlers.mcp.Application")
    async def test_get_mcp_selection_with_empty_servers(
        self, mock_app_cls, mock_session
    ):
        """Test that _get_mcp_selection returns False for no servers."""
        handler = MCPHandler(mock_session)

        result = await handler._get_mcp_selection({})

        assert result is False
        mock_app_cls.assert_not_called()

    @pytest.mark.asyncio
    @patch("src.cli.handlers.mcp.Application")
    async def test_get_mcp_selection_displays_servers(
        self, mock_app_cls, mock_session, mock_mcp_server_config
    ):
        """Test that _get_mcp_selection displays servers."""
        handler = MCPHandler(mock_session)
        mcp_servers = {"server1": mock_mcp_server_config}

        mock_app = AsyncMock()
        mock_app.run_async = AsyncMock()
        mock_app_cls.return_value = mock_app

        with patch("src.cli.handlers.mcp.sys.stdout"):
            await handler._get_mcp_selection(mcp_servers)
            mock_app.run_async.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.cli.handlers.mcp.Application")
    async def test_get_mcp_selection_keyboard_interrupt(
        self, mock_app_cls, mock_session, mock_mcp_server_config
    ):
        """Test that _get_mcp_selection handles KeyboardInterrupt."""
        handler = MCPHandler(mock_session)
        mcp_servers = {"server1": mock_mcp_server_config}

        mock_app = AsyncMock()
        mock_app.run_async = AsyncMock(side_effect=KeyboardInterrupt())
        mock_app_cls.return_value = mock_app

        with patch("src.cli.handlers.mcp.sys.stdout"):
            result = await handler._get_mcp_selection(mcp_servers)

            assert result is False

    @pytest.mark.asyncio
    @patch("src.cli.handlers.mcp.Application")
    async def test_get_mcp_selection_eof_error(
        self, mock_app_cls, mock_session, mock_mcp_server_config
    ):
        """Test that _get_mcp_selection handles EOFError."""
        handler = MCPHandler(mock_session)
        mcp_servers = {"server1": mock_mcp_server_config}

        mock_app = AsyncMock()
        mock_app.run_async = AsyncMock(side_effect=EOFError())
        mock_app_cls.return_value = mock_app

        with patch("src.cli.handlers.mcp.sys.stdout"):
            result = await handler._get_mcp_selection(mcp_servers)

            assert result is False

    def test_format_server_list_formats_correctly(self, mock_mcp_server_config):
        """Test that _format_server_list formats servers correctly."""
        mock_server_disabled = mock_mcp_server_config.model_copy(
            update={"enabled": False}
        )

        mcp_servers = {
            "server1": mock_mcp_server_config,
            "server2": mock_server_disabled,
        }
        server_names = ["server1", "server2"]

        formatted = MCPHandler._format_server_list(mcp_servers, server_names, 0)

        assert formatted is not None

    @pytest.mark.asyncio
    @patch("src.cli.handlers.mcp.initializer.load_mcp_config")
    async def test_handle_with_exception(self, mock_load_mcp, mock_session):
        """Test that handle handles exceptions gracefully."""
        handler = MCPHandler(mock_session)
        mock_load_mcp.side_effect = Exception("Test error")

        await handler.handle()

        mock_load_mcp.assert_called_once()
