"""Tests for replay handler."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.base import CheckpointTuple

from src.checkpointer.base import HumanMessageEntry
from src.cli.handlers.replay import ReplayHandler


@pytest.fixture
def sample_replay_message():
    """Create a sample HumanMessageEntry for replay testing."""
    from src.checkpointer.base import HumanMessageEntry

    return HumanMessageEntry(
        text="Hello",
        reference_mapping={},
        messages_before_count=0,
        checkpoint_id="cp1",
        input_tokens=None,
        output_tokens=None,
        total_cost=None,
    )


class TestReplayHandler:
    """Tests for ReplayHandler class."""

    @pytest.mark.asyncio
    async def test_handle_with_no_messages(self, mock_session):
        """Test that handle shows error when no messages found."""
        handler = ReplayHandler(mock_session)

        with patch.object(
            handler, "_get_human_messages", AsyncMock(return_value=([], []))
        ):
            await handler.handle()

    @pytest.mark.asyncio
    async def test_handle_with_messages(
        self, mock_session, sample_replay_message, mock_checkpointer
    ):
        """Test that handle displays messages and allows selection."""
        handler = ReplayHandler(mock_session)
        human_messages = [sample_replay_message]

        # Mock the delete_after method on the checkpointer
        mock_checkpointer.delete_after = AsyncMock(return_value=1)

        with (
            patch.object(
                handler,
                "_get_human_messages",
                AsyncMock(return_value=(human_messages, [])),
            ),
            patch.object(
                handler, "_get_message_selection", AsyncMock(return_value=0)
            ) as mock_get_selection,
            patch.object(
                handler, "_replay_from_message", AsyncMock(return_value="cp1")
            ) as mock_replay,
            patch(
                "src.cli.handlers.replay.initializer.get_checkpointer"
            ) as mock_get_checkpointer,
        ):
            mock_get_checkpointer.return_value.__aenter__.return_value = (
                mock_checkpointer
            )

            await handler.handle()

            mock_get_selection.assert_called_once_with(human_messages)
            mock_replay.assert_called_once_with(human_messages, [], 0)
            mock_checkpointer.delete_after.assert_called_once()
            assert mock_session.prefilled_text == "Hello"

    @pytest.mark.asyncio
    async def test_handle_with_cancelled_selection(
        self, mock_session, sample_replay_message
    ):
        """Test that handle returns when selection is cancelled."""
        handler = ReplayHandler(mock_session)
        human_messages = [sample_replay_message]

        with (
            patch.object(
                handler,
                "_get_human_messages",
                AsyncMock(return_value=(human_messages, [])),
            ),
            patch.object(
                handler, "_get_message_selection", AsyncMock(return_value=None)
            ),
        ):
            await handler.handle()

            assert mock_session.prefilled_text == ""

    @pytest.mark.asyncio
    @patch("src.cli.handlers.replay.initializer.get_checkpointer")
    async def test_get_human_messages_returns_messages(
        self,
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

        from src.checkpointer.base import HumanMessageEntry

        mock_checkpointer.aget_tuple.return_value = checkpoint_tuple
        mock_checkpointer.get_human_messages = AsyncMock(
            return_value=(
                [
                    HumanMessageEntry(
                        text="Hello",
                        reference_mapping={},
                        messages_before_count=0,
                        checkpoint_id=checkpoint_tuple.checkpoint.get("id"),
                        input_tokens=None,
                        output_tokens=None,
                        total_cost=None,
                    )
                ],
                [human_msg],
            )
        )
        mock_get_checkpointer.return_value.__aenter__.return_value = mock_checkpointer

        human_messages, all_messages = await handler._get_human_messages()

        assert len(human_messages) > 0
        assert len(all_messages) > 0

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

        assert result == ([], [])

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
        from src.checkpointer.base import HumanMessageEntry

        messages = [
            HumanMessageEntry(
                text="Hello world",
                reference_mapping={},
                messages_before_count=0,
                checkpoint_id="cp1",
            )
        ]

        formatted = ReplayHandler._format_message_list(messages, 0, 0, 5)

        assert formatted is not None

    def test_format_message_list_with_scrolling(self):
        """Test that _format_message_list handles scrolling window."""
        from src.checkpointer.base import HumanMessageEntry

        messages = [
            HumanMessageEntry(
                text=f"Message {i}",
                reference_mapping={},
                messages_before_count=0,
                checkpoint_id=f"cp{i}",
            )
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
        from src.checkpointer.base import HumanMessageEntry

        handler = ReplayHandler(mock_session)

        mock_msg = MagicMock()
        mock_msg.id = "msg1"

        all_messages = [mock_msg]
        messages = [
            HumanMessageEntry(
                text="Hello",
                reference_mapping={},
                messages_before_count=1,
                checkpoint_id="cp1",
                input_tokens=100,
                output_tokens=50,
                total_cost=0.01,
            )
        ]

        result = await handler._replay_from_message(messages, all_messages, 0)

        assert result == "cp1"
        mock_clear.assert_called_once()
        mock_session.renderer.render_message.assert_called()

    @pytest.mark.asyncio
    async def test_replay_from_message_handles_exception(self, mock_session):
        """Test that _replay_from_message propagates exceptions."""
        handler = ReplayHandler(mock_session)

        messages = [
            HumanMessageEntry(
                text="Hello",
                reference_mapping={},
                messages_before_count=0,
                checkpoint_id="cp1",
            )
        ]
        all_messages: list = []

        with (
            patch(
                "src.cli.handlers.replay.console.clear",
                side_effect=Exception("Test error"),
            ),
            pytest.raises(Exception, match="Test error"),
        ):
            await handler._replay_from_message(messages, all_messages, 0)

    @pytest.mark.asyncio
    async def test_handle_with_replay_failure_does_not_delete(
        self, mock_session, sample_replay_message, mock_checkpointer
    ):
        """Test that handle does not delete checkpoints when replay fails."""
        handler = ReplayHandler(mock_session)
        human_messages = [sample_replay_message]

        # Mock the delete_after method on the checkpointer
        mock_checkpointer.delete_after = AsyncMock(return_value=1)

        with (
            patch.object(
                handler,
                "_get_human_messages",
                AsyncMock(return_value=(human_messages, [])),
            ),
            patch.object(handler, "_get_message_selection", AsyncMock(return_value=0)),
            patch.object(
                handler,
                "_replay_from_message",
                AsyncMock(side_effect=Exception("Replay failed")),
            ) as mock_replay,
            patch(
                "src.cli.handlers.replay.initializer.get_checkpointer"
            ) as mock_get_checkpointer,
        ):
            mock_get_checkpointer.return_value.__aenter__.return_value = (
                mock_checkpointer
            )

            await handler.handle()

            mock_replay.assert_called_once_with(human_messages, [], 0)
            # Critical: delete_after should NOT be called when replay raises exception
            mock_checkpointer.delete_after.assert_not_called()
            # Prefilled text should not be set
            assert mock_session.prefilled_text == ""

    @pytest.mark.asyncio
    async def test_handle_first_message_replay(self, mock_session, mock_checkpointer):
        """Test replaying from the first message deletes all checkpoints."""
        handler = ReplayHandler(mock_session)

        # First message has no checkpoint_id (None)
        first_message = HumanMessageEntry(
            text="First message",
            reference_mapping={},
            messages_before_count=0,  # No messages before first
            checkpoint_id=None,  # Key: None means delete all
            input_tokens=100,
            output_tokens=200,
            total_cost=0.01,
        )

        mock_checkpointer.delete_after = AsyncMock(return_value=4)

        with (
            patch.object(
                handler,
                "_get_human_messages",
                AsyncMock(return_value=([first_message], [])),
            ),
            patch.object(handler, "_get_message_selection", AsyncMock(return_value=0)),
            patch(
                "src.cli.handlers.replay.initializer.get_checkpointer"
            ) as mock_get_checkpointer,
        ):
            mock_get_checkpointer.return_value.__aenter__.return_value = (
                mock_checkpointer
            )

            await handler.handle()

            # Verify delete_after was called with None (delete all)
            mock_checkpointer.delete_after.assert_called_once_with(
                mock_session.context.thread_id, None
            )

            # Verify message is prefilled
            assert mock_session.prefilled_text == "First message"
            assert mock_session.prefilled_reference_mapping == {}

    @pytest.mark.asyncio
    async def test_handle_with_exception(self, mock_session):
        """Test that handle handles exceptions gracefully."""
        handler = ReplayHandler(mock_session)

        with patch.object(
            handler, "_get_human_messages", side_effect=Exception("Test error")
        ):
            await handler.handle()
