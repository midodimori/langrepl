"""Tests for chat command handler."""

from pathlib import Path
from unittest.mock import patch

import pytest

from src.cli.bootstrap.chat import handle_chat_command


class TestHandleChatCommand:
    """Tests for handle_chat_command function."""

    @pytest.mark.asyncio
    async def test_handle_chat_command_creates_context(
        self, mock_app_args, patch_chat_dependencies
    ):
        """Test that handle_chat_command creates a context."""
        result = await handle_chat_command(mock_app_args)
        assert result == 0

    @pytest.mark.asyncio
    async def test_handle_chat_command_starts_session(
        self, mock_app_args, patch_chat_dependencies
    ):
        """Test that handle_chat_command starts a CLI session."""
        result = await handle_chat_command(mock_app_args)

        patch_chat_dependencies["session"].start.assert_called_once()
        assert result == 0

    @pytest.mark.asyncio
    async def test_handle_chat_command_with_resume_flag(
        self, mock_app_args, patch_chat_dependencies, mock_context
    ):
        """Test that handle_chat_command handles resume flag in interactive mode."""
        mock_app_args.resume = True

        result = await handle_chat_command(mock_app_args)

        patch_chat_dependencies[
            "session"
        ].command_dispatcher.resume_handler.handle.assert_called_once_with(
            mock_context.thread_id
        )
        assert result == 0

    @pytest.mark.asyncio
    async def test_handle_chat_command_enables_timer(
        self, mock_app_args, patch_chat_dependencies
    ):
        """Test that handle_chat_command enables timer when requested."""
        mock_app_args.timer = True

        result = await handle_chat_command(mock_app_args)

        patch_chat_dependencies["enable_timer"].assert_called_once()
        assert result == 0

    @pytest.mark.asyncio
    async def test_handle_chat_command_handles_reload_loop(
        self, mock_app_args, patch_chat_dependencies
    ):
        """Test that handle_chat_command handles reload loop."""
        call_count = 0
        session = patch_chat_dependencies["session"]

        def side_effect(*_args, **_kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                session.needs_reload = True
            else:
                session.needs_reload = False

        session.start.side_effect = side_effect

        result = await handle_chat_command(mock_app_args)

        assert session.start.call_count == 2
        assert result == 0

    @pytest.mark.asyncio
    async def test_handle_chat_command_shows_welcome_on_first_start(
        self, mock_app_args, patch_chat_dependencies
    ):
        """Test that handle_chat_command shows welcome message on first start."""
        await handle_chat_command(mock_app_args)

        patch_chat_dependencies["session"].start.assert_called_once_with(
            show_welcome=True
        )

    @pytest.mark.asyncio
    async def test_handle_chat_command_hides_welcome_on_resume(
        self, mock_app_args, patch_chat_dependencies
    ):
        """Test that handle_chat_command hides welcome when resuming."""
        mock_app_args.resume = True

        await handle_chat_command(mock_app_args)

        patch_chat_dependencies["session"].start.assert_called_once_with(
            show_welcome=False
        )

    @pytest.mark.asyncio
    async def test_handle_chat_command_handles_keyboard_interrupt(
        self, mock_app_args, patch_chat_dependencies
    ):
        """Test that handle_chat_command handles KeyboardInterrupt gracefully."""
        patch_chat_dependencies["session"].start.side_effect = KeyboardInterrupt()

        result = await handle_chat_command(mock_app_args)

        assert result == 0

    @pytest.mark.asyncio
    async def test_handle_chat_command_handles_exception(
        self, mock_app_args, patch_chat_dependencies
    ):
        """Test that handle_chat_command handles exceptions and returns error code."""
        patch_chat_dependencies["session"].start.side_effect = Exception("Test error")

        result = await handle_chat_command(mock_app_args)

        assert result == 1

    @pytest.mark.asyncio
    async def test_handle_chat_command_uses_path_object(
        self, mock_app_args, patch_chat_dependencies
    ):
        """Test that handle_chat_command converts working_dir to Path."""
        await handle_chat_command(mock_app_args)

        call_args = patch_chat_dependencies["context_create"].call_args
        assert isinstance(call_args[1]["working_dir"], Path)

    @pytest.mark.asyncio
    async def test_handle_chat_command_one_shot_mode(
        self, mock_app_args, patch_chat_dependencies
    ):
        """Test that handle_chat_command sends a single message in one-shot mode."""
        mock_app_args.message = "test message"

        result = await handle_chat_command(mock_app_args)

        patch_chat_dependencies["session"].send.assert_called_once_with("test message")
        patch_chat_dependencies["session"].start.assert_not_called()
        assert result == 0

    @pytest.mark.asyncio
    async def test_handle_chat_command_one_shot_mode_with_resume(
        self, mock_app_args, patch_chat_dependencies, mock_context
    ):
        """Test that handle_chat_command handles resume in one-shot mode without rendering history."""
        mock_app_args.message = "test message"
        mock_app_args.resume = True

        result = await handle_chat_command(mock_app_args)

        patch_chat_dependencies[
            "session"
        ].command_dispatcher.resume_handler.handle.assert_called_once_with(
            mock_context.thread_id, render_history=False
        )
        patch_chat_dependencies["session"].send.assert_called_once_with("test message")
        patch_chat_dependencies["session"].start.assert_not_called()
        assert result == 0


@pytest.fixture
def patch_chat_dependencies(mock_context, mock_session):
    """Patch Context.create and Session for chat tests."""
    with (
        patch(
            "src.cli.bootstrap.chat.Context.create", return_value=mock_context
        ) as mock_create,
        patch(
            "src.cli.bootstrap.chat.Session", return_value=mock_session
        ) as mock_session_cls,
        patch("src.cli.bootstrap.chat.enable_timer") as mock_enable_timer,
    ):
        yield {
            "context_create": mock_create,
            "session_cls": mock_session_cls,
            "session": mock_session,
            "enable_timer": mock_enable_timer,
        }
