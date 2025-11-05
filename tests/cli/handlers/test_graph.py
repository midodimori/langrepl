"""Tests for graph handler."""

from unittest.mock import MagicMock, patch

import pytest

from src.cli.handlers.graph import GraphHandler


@pytest.fixture
def mock_drawable_graph():
    """Create a mock drawable graph object."""
    drawable = MagicMock()
    drawable.draw_mermaid_png.return_value = b"PNG data"
    return drawable


class TestGraphHandler:
    """Tests for GraphHandler class."""

    @pytest.mark.asyncio
    @patch("src.cli.handlers.graph.console")
    async def test_handle_with_no_graph(self, mock_console, mock_session):
        """Test that handle shows error when no graph available."""
        handler = GraphHandler(mock_session)
        mock_session.graph = None

        await handler.handle()

        mock_console.print_error.assert_called_once_with(
            "No graph available. Please start a conversation first."
        )

    @pytest.mark.asyncio
    async def test_handle_renders_terminal_output(
        self, mock_session, mock_drawable_graph
    ):
        """Test that handle renders graph in terminal by default."""
        handler = GraphHandler(mock_session)
        mock_session.graph.get_graph.return_value = mock_drawable_graph

        await handler.handle(open_browser=False)

        mock_session.renderer.render_graph.assert_called_once_with(mock_drawable_graph)

    @pytest.mark.asyncio
    async def test_handle_renders_png_successfully(
        self, mock_session, mock_drawable_graph
    ):
        """Test that handle renders PNG and opens browser when requested."""
        handler = GraphHandler(mock_session)
        mock_session.graph.get_graph.return_value = mock_drawable_graph

        with patch.object(
            handler, "_try_render_png", return_value=True
        ) as mock_render_png:
            await handler.handle(open_browser=True)

            mock_render_png.assert_called_once_with(mock_drawable_graph)
            mock_session.renderer.render_graph.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_falls_back_to_terminal_on_png_failure(
        self, mock_session, mock_drawable_graph
    ):
        """Test that handle falls back to terminal when PNG rendering fails."""
        handler = GraphHandler(mock_session)
        mock_session.graph.get_graph.return_value = mock_drawable_graph

        with patch.object(
            handler, "_try_render_png", return_value=False
        ) as mock_render_png:
            await handler.handle(open_browser=True)

            mock_render_png.assert_called_once_with(mock_drawable_graph)
            mock_session.renderer.render_graph.assert_called_once_with(
                mock_drawable_graph
            )

    @pytest.mark.asyncio
    @patch("src.cli.handlers.graph.console")
    async def test_handle_with_exception(self, mock_console, mock_session):
        """Test that handle handles exceptions gracefully."""
        handler = GraphHandler(mock_session)

        mock_session.graph.get_graph.side_effect = Exception("Test error")

        await handler.handle()

        mock_console.print_error.assert_called_once()
        error_message = mock_console.print_error.call_args[0][0]
        assert "Test error" in error_message

    @pytest.mark.asyncio
    @patch("src.cli.handlers.graph.webbrowser.open")
    @patch("src.cli.handlers.graph.tempfile.NamedTemporaryFile")
    async def test_try_render_png_success(
        self, mock_tempfile, mock_webbrowser, mock_session, mock_drawable_graph
    ):
        """Test that _try_render_png renders and opens PNG successfully."""
        handler = GraphHandler(mock_session)

        mock_temp = MagicMock()
        mock_temp.name = "/tmp/test.png"
        mock_temp.__enter__.return_value = mock_temp
        mock_tempfile.return_value = mock_temp

        with patch("src.cli.handlers.graph.Path") as mock_path_cls:
            mock_path = MagicMock()
            mock_html_path = MagicMock()
            mock_html_path.absolute.return_value = "/tmp/test.html"
            mock_path.with_suffix.return_value = mock_html_path
            mock_path.absolute.return_value = "/tmp/test.png"
            mock_path_cls.return_value = mock_path

            result = await handler._try_render_png(mock_drawable_graph)

            assert result is True
            mock_drawable_graph.draw_mermaid_png.assert_called_once()
            mock_webbrowser.assert_called_once()

    @pytest.mark.asyncio
    async def test_try_render_png_import_error(self, mock_session, mock_drawable_graph):
        """Test that _try_render_png handles ImportError gracefully."""
        handler = GraphHandler(mock_session)
        mock_drawable_graph.draw_mermaid_png.side_effect = ImportError("Missing lib")

        result = await handler._try_render_png(mock_drawable_graph)

        assert result is False

    @pytest.mark.asyncio
    async def test_try_render_png_general_exception(
        self, mock_session, mock_drawable_graph
    ):
        """Test that _try_render_png handles general exceptions gracefully."""
        handler = GraphHandler(mock_session)
        mock_drawable_graph.draw_mermaid_png.side_effect = Exception("Test error")

        result = await handler._try_render_png(mock_drawable_graph)

        assert result is False
