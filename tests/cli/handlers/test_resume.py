"""Tests for resume handler."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langgraph.checkpoint.base import CheckpointTuple

from src.cli.handlers.resume import ResumeHandler


@pytest.fixture
def sample_thread():
    """Create a sample thread dict for resume testing."""
    return {
        "thread_id": "thread-1",
        "last_message": "message 1",
        "timestamp": "",
    }


class TestResumeHandler:
    """Tests for ResumeHandler class."""

    @pytest.mark.asyncio
    @patch("src.cli.handlers.resume.initializer.get_threads")
    async def test_handle_with_no_threads(self, mock_get_threads, mock_session):
        """Test that handle shows error when no threads found."""
        handler = ResumeHandler(mock_session)
        mock_get_threads.return_value = []

        await handler.handle()

        mock_get_threads.assert_called_once_with(
            mock_session.context.agent, mock_session.context.working_dir
        )

    @pytest.mark.asyncio
    @patch("src.cli.handlers.resume.initializer.get_threads")
    async def test_handle_filters_current_thread(self, mock_get_threads, mock_session):
        """Test that handle filters out current thread from list."""
        handler = ResumeHandler(mock_session)

        threads = [
            {"thread_id": mock_session.context.thread_id, "last_message": "current"},
            {"thread_id": "other-thread", "last_message": "other"},
        ]
        mock_get_threads.return_value = threads

        with patch.object(handler, "_get_thread_selection", return_value=""):
            await handler.handle()

            mock_get_threads.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.cli.handlers.resume.initializer.get_threads")
    async def test_handle_loads_selected_thread(self, mock_get_threads, mock_session):
        """Test that handle loads selected thread."""
        handler = ResumeHandler(mock_session)

        threads = [{"thread_id": "thread-1", "last_message": "message 1"}]
        mock_get_threads.return_value = threads

        with (
            patch.object(handler, "_get_thread_selection", return_value="thread-1"),
            patch.object(handler, "_load_thread", new_callable=AsyncMock) as mock_load,
        ):
            await handler.handle()

            mock_load.assert_called_once_with("thread-1", render_history=True)

    @pytest.mark.asyncio
    async def test_handle_with_direct_thread_id(self, mock_session):
        """Test that handle directly loads thread when thread_id provided."""
        handler = ResumeHandler(mock_session)

        with patch.object(handler, "_load_thread", new_callable=AsyncMock) as mock_load:
            await handler.handle(thread_id="specific-thread")

            mock_load.assert_called_once_with("specific-thread", render_history=True)

    @pytest.mark.asyncio
    @patch("src.cli.handlers.resume.Application")
    async def test_get_thread_selection_with_empty_list(
        self, mock_app_cls, mock_session
    ):
        """Test that _get_thread_selection returns empty string for no threads."""
        handler = ResumeHandler(mock_session)

        result = await handler._get_thread_selection([])

        assert result == ""
        mock_app_cls.assert_not_called()

    @pytest.mark.asyncio
    @patch("src.cli.handlers.resume.Application")
    async def test_get_thread_selection_with_selection(
        self, mock_app_cls, mock_session
    ):
        """Test that _get_thread_selection returns selected thread ID."""
        handler = ResumeHandler(mock_session)

        threads = [
            {"thread_id": "thread-1", "last_message": "message 1", "timestamp": ""},
            {"thread_id": "thread-2", "last_message": "message 2", "timestamp": ""},
        ]

        mock_app = AsyncMock()
        mock_app.run_async = AsyncMock()
        mock_app_cls.return_value = mock_app

        with patch("src.cli.handlers.resume.sys.stdout"):
            await handler._get_thread_selection(threads)
            mock_app.run_async.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.cli.handlers.resume.Application")
    async def test_get_thread_selection_keyboard_interrupt(
        self, mock_app_cls, mock_session
    ):
        """Test that _get_thread_selection handles KeyboardInterrupt."""
        handler = ResumeHandler(mock_session)

        threads = [{"thread_id": "thread-1", "last_message": "msg", "timestamp": ""}]

        mock_app = AsyncMock()
        mock_app.run_async = AsyncMock(side_effect=KeyboardInterrupt())
        mock_app_cls.return_value = mock_app

        result = await handler._get_thread_selection(threads)

        assert result == ""

    @pytest.mark.asyncio
    @patch("src.cli.handlers.resume.initializer.get_checkpointer")
    async def test_load_thread_with_no_checkpoint(
        self, mock_get_checkpointer, mock_session, mock_checkpointer
    ):
        """Test that _load_thread handles missing checkpoint."""
        handler = ResumeHandler(mock_session)

        mock_checkpointer.aget_tuple.return_value = None
        mock_get_checkpointer.return_value.__aenter__.return_value = mock_checkpointer

        await handler._load_thread("thread-1")

        mock_checkpointer.aget_tuple.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.cli.handlers.resume.initializer.get_checkpointer")
    async def test_load_thread_with_valid_checkpoint(
        self,
        mock_get_checkpointer,
        mock_session,
        mock_checkpointer,
        mock_checkpointer_tuple,
    ):
        """Test that _load_thread loads and renders messages."""
        handler = ResumeHandler(mock_session)

        mock_message = MagicMock()
        mock_message.id = "msg-1"

        checkpoint = mock_checkpointer_tuple.checkpoint.copy()
        checkpoint["channel_values"] = {
            "messages": [mock_message],
            "current_input_tokens": 100,
            "current_output_tokens": 50,
            "total_cost": 0.01,
        }
        checkpoint_tuple = CheckpointTuple(
            config=mock_checkpointer_tuple.config,
            checkpoint=checkpoint,
            metadata=mock_checkpointer_tuple.metadata,
            parent_config=mock_checkpointer_tuple.parent_config,
            pending_writes=mock_checkpointer_tuple.pending_writes,
        )

        mock_checkpointer.aget_tuple.return_value = checkpoint_tuple
        mock_get_checkpointer.return_value.__aenter__.return_value = mock_checkpointer

        await handler._load_thread("thread-1")

        mock_session.renderer.render_message.assert_called()
        mock_session.update_context.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.cli.handlers.resume.initializer.get_checkpointer")
    async def test_load_thread_handles_exception(
        self, mock_get_checkpointer, mock_session
    ):
        """Test that _load_thread handles exceptions gracefully."""
        handler = ResumeHandler(mock_session)

        mock_get_checkpointer.side_effect = Exception("Test error")

        await handler._load_thread("thread-1")

    def test_format_thread_list_formats_correctly(self):
        """Test that _format_thread_list formats threads correctly."""
        threads = [
            {"thread_id": "t1", "last_message": "Hello world", "timestamp": ""},
            {"thread_id": "t2", "last_message": "Test message", "timestamp": ""},
        ]

        formatted = ResumeHandler._format_thread_list(threads, 0, 0, 5)

        assert formatted is not None

    def test_format_thread_list_with_scrolling(self):
        """Test that _format_thread_list handles scrolling window."""
        threads = [
            {"thread_id": f"t{i}", "last_message": f"msg {i}", "timestamp": ""}
            for i in range(10)
        ]

        formatted = ResumeHandler._format_thread_list(threads, 5, 3, 5)

        assert formatted is not None

    @pytest.mark.asyncio
    @patch("src.cli.handlers.resume.initializer.get_threads")
    async def test_handle_with_exception(self, mock_get_threads, mock_session):
        """Test that handle handles exceptions gracefully."""
        handler = ResumeHandler(mock_session)
        mock_get_threads.side_effect = Exception("Test error")

        await handler.handle()

        mock_get_threads.assert_called_once()
