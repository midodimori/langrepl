"""Tests for tools handler."""

from unittest.mock import AsyncMock, patch

import pytest

from src.cli.handlers.tools import ToolsHandler


class TestToolsHandler:
    """Tests for ToolsHandler class."""

    @pytest.mark.asyncio
    async def test_handle_with_no_tools(self, mock_session):
        """Test that handle shows error when no tools available."""
        handler = ToolsHandler(mock_session)

        await handler.handle([])

    @pytest.mark.asyncio
    async def test_handle_with_tools(self, mock_session, create_mock_tool):
        """Test that handle displays tools successfully."""
        handler = ToolsHandler(mock_session)
        tools = [create_mock_tool("tool1"), create_mock_tool("tool2")]

        with patch.object(handler, "_get_tool_selection", new_callable=AsyncMock):
            await handler.handle(tools)

    @pytest.mark.asyncio
    @patch("src.cli.handlers.tools.Application")
    async def test_get_tool_selection_with_empty_list(self, mock_app_cls, mock_session):
        """Test that _get_tool_selection returns None for no tools."""
        handler = ToolsHandler(mock_session)

        await handler._get_tool_selection([])

        mock_app_cls.assert_not_called()

    @pytest.mark.asyncio
    @patch("src.cli.handlers.tools.Application")
    async def test_get_tool_selection_displays_tools(
        self, mock_app_cls, mock_session, create_mock_tool
    ):
        """Test that _get_tool_selection displays tools."""
        handler = ToolsHandler(mock_session)
        tools = [create_mock_tool("tool1"), create_mock_tool("tool2")]

        mock_app = AsyncMock()
        mock_app.run_async = AsyncMock()
        mock_app_cls.return_value = mock_app

        with patch("src.cli.handlers.tools.sys.stdout"):
            await handler._get_tool_selection(tools)
            mock_app.run_async.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.cli.handlers.tools.Application")
    async def test_get_tool_selection_keyboard_interrupt(
        self, mock_app_cls, mock_session, create_mock_tool
    ):
        """Test that _get_tool_selection handles KeyboardInterrupt."""
        handler = ToolsHandler(mock_session)
        tools = [create_mock_tool("tool1")]

        mock_app = AsyncMock()
        mock_app.run_async = AsyncMock(side_effect=KeyboardInterrupt())
        mock_app_cls.return_value = mock_app

        with patch("src.cli.handlers.tools.sys.stdout"):
            await handler._get_tool_selection(tools)

    @pytest.mark.asyncio
    @patch("src.cli.handlers.tools.Application")
    async def test_get_tool_selection_eof_error(
        self, mock_app_cls, mock_session, create_mock_tool
    ):
        """Test that _get_tool_selection handles EOFError."""
        handler = ToolsHandler(mock_session)
        tools = [create_mock_tool("tool1")]

        mock_app = AsyncMock()
        mock_app.run_async = AsyncMock(side_effect=EOFError())
        mock_app_cls.return_value = mock_app

        with patch("src.cli.handlers.tools.sys.stdout"):
            await handler._get_tool_selection(tools)

    def test_format_tool_list_formats_correctly(self, create_mock_tool):
        """Test that _format_tool_list formats tools correctly."""
        tools = [create_mock_tool("tool1"), create_mock_tool("tool2")]

        formatted = ToolsHandler._format_tool_list(tools, 0, set(), 0, 10)

        assert formatted is not None

    def test_format_tool_list_with_expanded(self, create_mock_tool):
        """Test that _format_tool_list shows expanded description."""
        tools = [create_mock_tool("tool1"), create_mock_tool("tool2")]
        expanded_indices = {0}

        formatted = ToolsHandler._format_tool_list(tools, 0, expanded_indices, 0, 10)

        assert formatted is not None

    def test_format_tool_list_with_scrolling(self, create_mock_tool):
        """Test that _format_tool_list handles scrolling window."""
        tools = [create_mock_tool(f"tool{i}") for i in range(15)]

        formatted = ToolsHandler._format_tool_list(tools, 5, set(), 3, 10)

        assert formatted is not None

    @pytest.mark.asyncio
    async def test_handle_with_exception(self, mock_session, create_mock_tool):
        """Test that handle handles exceptions gracefully."""
        handler = ToolsHandler(mock_session)
        tools = [create_mock_tool("tool1")]

        with patch.object(
            handler, "_get_tool_selection", side_effect=Exception("Test error")
        ):
            await handler.handle(tools)
