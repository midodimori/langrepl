"""Tests for replay handler."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.base import CheckpointTuple

from src.cli.handlers.replay import ReplayHandler


@pytest.fixture
def sample_replay_message():
    """Create a sample message dict for replay testing."""
    return {
        "text": "Hello",
        "reference_mapping": {},
        "all_messages_before": [],
        "channel_values": {},
        "checkpoint_id": "cp1",
    }


class TestReplayHandler:
    """Tests for ReplayHandler class."""

    @pytest.mark.asyncio
    async def test_handle_with_no_messages(self, mock_session):
        """Test that handle shows error when no messages found."""
        handler = ReplayHandler(mock_session)

        with patch.object(handler, "_get_human_messages", return_value=[]):
            await handler.handle()

    @pytest.mark.asyncio
    async def test_handle_with_messages(
        self, mock_session, sample_replay_message, mock_checkpointer
    ):
        """Test that handle displays messages and allows selection."""
        handler = ReplayHandler(mock_session)
        human_messages = [sample_replay_message]

        with (
            patch.object(handler, "_get_human_messages", return_value=human_messages),
            patch.object(
                handler, "_get_message_selection", return_value=0
            ) as mock_get_selection,
            patch.object(
                handler, "_replay_from_message", return_value="cp1"
            ) as mock_replay,
            patch(
                "src.cli.handlers.replay.initializer.get_checkpointer"
            ) as mock_get_checkpointer,
            patch("src.cli.handlers.replay.delete_checkpoints_after") as mock_delete,
        ):
            mock_get_checkpointer.return_value.__aenter__.return_value = (
                mock_checkpointer
            )

            await handler.handle()

            mock_get_selection.assert_called_once_with(human_messages)
            mock_replay.assert_called_once_with(human_messages, 0)
            mock_delete.assert_called_once()
            assert mock_session.prefilled_text == "Hello"

    @pytest.mark.asyncio
    async def test_handle_with_cancelled_selection(
        self, mock_session, sample_replay_message
    ):
        """Test that handle returns when selection is cancelled."""
        handler = ReplayHandler(mock_session)
        human_messages = [sample_replay_message]

        with (
            patch.object(handler, "_get_human_messages", return_value=human_messages),
            patch.object(handler, "_get_message_selection", return_value=None),
        ):
            await handler.handle()

            assert mock_session.prefilled_text == ""

    @pytest.mark.asyncio
    @patch("src.cli.handlers.replay.initializer.get_checkpointer")
    @patch("src.cli.handlers.replay.get_checkpoint_history")
    async def test_get_human_messages_returns_messages(
        self,
        mock_get_history,
        mock_get_checkpointer,
        mock_session,
        mock_checkpointer,
        mock_checkpointer_tuple,
    ):
        """Test that _get_human_messages extracts human messages correctly."""
        handler = ReplayHandler(mock_session)

        human_msg = HumanMessage(content="Hello", id="msg1")

        checkpoint = mock_checkpointer_tuple.checkpoint.copy()
        checkpoint["channel_values"] = {"messages": [human_msg]}
        checkpoint_tuple = CheckpointTuple(
            config=mock_checkpointer_tuple.config,
            checkpoint=checkpoint,
            metadata=mock_checkpointer_tuple.metadata,
            parent_config=mock_checkpointer_tuple.parent_config,
            pending_writes=mock_checkpointer_tuple.pending_writes,
        )

        mock_checkpointer.aget_tuple.return_value = checkpoint_tuple
        mock_get_checkpointer.return_value.__aenter__.return_value = mock_checkpointer
        mock_get_history.return_value = [checkpoint_tuple]

        result = await handler._get_human_messages()

        assert len(result) > 0

    @pytest.mark.asyncio
    @patch("src.cli.handlers.replay.initializer.get_checkpointer")
    async def test_get_human_messages_with_no_checkpoint(
        self, mock_get_checkpointer, mock_session, mock_checkpointer
    ):
        """Test that _get_human_messages handles missing checkpoint."""
        handler = ReplayHandler(mock_session)

        mock_checkpointer.aget_tuple.return_value = None
        mock_get_checkpointer.return_value.__aenter__.return_value = mock_checkpointer

        result = await handler._get_human_messages()

        assert result == []

    @pytest.mark.asyncio
    @patch("src.cli.handlers.replay.Application")
    async def test_get_message_selection_with_empty_list(
        self, mock_app_cls, mock_session
    ):
        """Test that _get_message_selection returns None for no messages."""
        handler = ReplayHandler(mock_session)

        result = await handler._get_message_selection([])

        assert result is None
        mock_app_cls.assert_not_called()

    @pytest.mark.asyncio
    @patch("src.cli.handlers.replay.Application")
    async def test_get_message_selection_with_selection(
        self, mock_app_cls, mock_session, sample_replay_message
    ):
        """Test that _get_message_selection returns selected index."""
        handler = ReplayHandler(mock_session)
        messages = [sample_replay_message]

        mock_app = AsyncMock()
        mock_app.run_async = AsyncMock()
        mock_app_cls.return_value = mock_app

        with patch("src.cli.handlers.replay.sys.stdout"):
            await handler._get_message_selection(messages)
            mock_app.run_async.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.cli.handlers.replay.Application")
    async def test_get_message_selection_keyboard_interrupt(
        self, mock_app_cls, mock_session, sample_replay_message
    ):
        """Test that _get_message_selection handles KeyboardInterrupt."""
        handler = ReplayHandler(mock_session)
        messages = [sample_replay_message]

        mock_app = AsyncMock()
        mock_app.run_async = AsyncMock(side_effect=KeyboardInterrupt())
        mock_app_cls.return_value = mock_app

        result = await handler._get_message_selection(messages)

        assert result is None

    def test_format_message_list_formats_correctly(self):
        """Test that _format_message_list formats messages correctly."""
        messages = [
            {
                "text": "Hello world",
                "reference_mapping": {},
                "all_messages_before": [],
                "channel_values": {},
                "checkpoint_id": "cp1",
            }
        ]

        formatted = ReplayHandler._format_message_list(messages, 0, 0, 5)

        assert formatted is not None

    def test_format_message_list_with_scrolling(self):
        """Test that _format_message_list handles scrolling window."""
        messages = [
            {
                "text": f"Message {i}",
                "reference_mapping": {},
                "all_messages_before": [],
                "channel_values": {},
                "checkpoint_id": f"cp{i}",
            }
            for i in range(10)
        ]

        formatted = ReplayHandler._format_message_list(messages, 5, 3, 5)

        assert formatted is not None

    @pytest.mark.asyncio
    @patch("src.cli.handlers.replay.console.clear")
    async def test_replay_from_message_clears_and_renders(
        self, mock_clear, mock_session
    ):
        """Test that _replay_from_message clears screen and renders messages."""
        handler = ReplayHandler(mock_session)

        mock_msg = MagicMock()
        mock_msg.id = "msg1"

        messages = [
            {
                "text": "Hello",
                "reference_mapping": {},
                "all_messages_before": [mock_msg],
                "channel_values": {
                    "current_input_tokens": 100,
                    "current_output_tokens": 50,
                    "total_cost": 0.01,
                },
                "checkpoint_id": "cp1",
            }
        ]

        result = await handler._replay_from_message(messages, 0)

        assert result == "cp1"
        mock_clear.assert_called_once()
        mock_session.renderer.render_message.assert_called()
        mock_session.update_context.assert_called_once()

    @pytest.mark.asyncio
    async def test_replay_from_message_handles_exception(self, mock_session):
        """Test that _replay_from_message handles exceptions gracefully."""
        handler = ReplayHandler(mock_session)

        messages: list[dict] = [
            {
                "text": "Hello",
                "reference_mapping": {},
                "all_messages_before": None,
                "channel_values": {},
                "checkpoint_id": "cp1",
            }
        ]

        with patch(
            "src.cli.handlers.replay.console.clear", side_effect=Exception("Test error")
        ):
            result = await handler._replay_from_message(messages, 0)

            assert result is None

    @pytest.mark.asyncio
    async def test_handle_with_exception(self, mock_session):
        """Test that handle handles exceptions gracefully."""
        handler = ReplayHandler(mock_session)

        with patch.object(
            handler, "_get_human_messages", side_effect=Exception("Test error")
        ):
            await handler.handle()
