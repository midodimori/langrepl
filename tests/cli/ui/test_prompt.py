"""Tests for InteractivePrompt critical logic."""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.key_binding import KeyPressEvent
from prompt_toolkit.keys import Keys

from src.cli.ui.prompt import InteractivePrompt


class TestInteractivePromptCtrlCBehavior:
    """Tests for Ctrl-C state machine and double-press detection."""

    @pytest.fixture
    def prompt(self, mock_context, mock_prompt_session):
        """Create an InteractivePrompt for testing."""
        prompt = InteractivePrompt(mock_context, ["/help"])
        prompt.prompt_session = mock_prompt_session
        return prompt

    def test_ctrl_c_clears_text_when_buffer_has_content(self, prompt):
        """Test that Ctrl-C clears buffer when it has content and resets state."""
        kb = prompt._create_key_bindings()
        buffer = MagicMock(spec=Buffer)
        buffer.text = "some text to clear"
        buffer.delete_before_cursor = MagicMock()

        event = MagicMock(spec=KeyPressEvent)
        event.current_buffer = buffer
        event.app = MagicMock()

        prompt._last_ctrl_c_time = time.time()
        prompt._show_quit_message = True

        handler = kb.get_bindings_for_keys((Keys.ControlC,))[0].handler
        handler(event)

        buffer.delete_before_cursor.assert_called_once_with(len(buffer.text))
        assert prompt._last_ctrl_c_time is None
        assert prompt._show_quit_message is False

    @pytest.mark.asyncio
    async def test_ctrl_c_first_press_on_empty_buffer_sets_timer(self, prompt):
        """Test that first Ctrl-C on empty buffer sets timer and shows message."""
        kb = prompt._create_key_bindings()
        buffer = MagicMock(spec=Buffer)
        buffer.text = ""

        event = MagicMock(spec=KeyPressEvent)
        event.current_buffer = buffer
        event.app = MagicMock()

        assert prompt._last_ctrl_c_time is None
        assert prompt._show_quit_message is False

        handler = kb.get_bindings_for_keys((Keys.ControlC,))[0].handler
        handler(event)

        assert prompt._last_ctrl_c_time is not None
        assert prompt._show_quit_message is True

    @pytest.mark.asyncio
    async def test_ctrl_c_double_press_within_timeout_raises_interrupt(self, prompt):
        """Test that double Ctrl-C within timeout window raises KeyboardInterrupt."""
        kb = prompt._create_key_bindings()
        buffer = MagicMock(spec=Buffer)
        buffer.text = ""

        event = MagicMock(spec=KeyPressEvent)
        event.current_buffer = buffer
        event.app = MagicMock()

        handler = kb.get_bindings_for_keys((Keys.ControlC,))[0].handler

        handler(event)
        prompt._last_ctrl_c_time = time.time()

        with pytest.raises(KeyboardInterrupt):
            handler(event)

    @pytest.mark.asyncio
    async def test_ctrl_c_press_after_timeout_resets_timer(self, prompt):
        """Test that Ctrl-C after timeout expires resets the timer instead of quitting."""
        kb = prompt._create_key_bindings()
        buffer = MagicMock(spec=Buffer)
        buffer.text = ""

        event = MagicMock(spec=KeyPressEvent)
        event.current_buffer = buffer
        event.app = MagicMock()

        handler = kb.get_bindings_for_keys((Keys.ControlC,))[0].handler

        old_time = time.time() - 1.0
        prompt._last_ctrl_c_time = old_time

        handler(event)

        assert prompt._last_ctrl_c_time > old_time
        assert prompt._show_quit_message is True

    @pytest.mark.asyncio
    async def test_schedule_hide_message_clears_state_after_timeout(self, prompt):
        """Test that quit message and timer are cleared after timeout."""
        app = MagicMock()
        app.invalidate = MagicMock()

        prompt._show_quit_message = True
        prompt._last_ctrl_c_time = time.time()

        prompt._schedule_hide_message(app)

        await asyncio.sleep(0.6)

        assert prompt._show_quit_message is False
        assert prompt._last_ctrl_c_time is None
        app.invalidate.assert_called()


class TestInteractivePromptKeyBindings:
    """Tests for key binding behaviors."""

    @pytest.fixture
    def prompt(self, mock_context, mock_prompt_session):
        """Create an InteractivePrompt for testing."""
        prompt = InteractivePrompt(mock_context, ["/help", "/quit"])
        prompt.prompt_session = mock_prompt_session
        return prompt

    def test_ctrl_j_inserts_newline(self, prompt):
        """Test that Ctrl-J inserts a newline for multiline input."""
        kb = prompt._create_key_bindings()
        buffer = Buffer()
        buffer.text = "line1"
        buffer.cursor_position = len(buffer.text)

        event = MagicMock(spec=KeyPressEvent)
        event.current_buffer = buffer

        handler = kb.get_bindings_for_keys(("c-j",))[0].handler
        handler(event)

        assert "\n" in buffer.text

    def test_backtab_triggers_mode_change_callback(self, prompt):
        """Test that Shift-Tab triggers approval mode change callback."""
        kb = prompt._create_key_bindings()
        callback = MagicMock()
        prompt.set_mode_change_callback(callback)

        event = MagicMock(spec=KeyPressEvent)

        handler = kb.get_bindings_for_keys(("s-tab",))[0].handler
        handler(event)

        callback.assert_called_once()

    def test_backtab_does_nothing_without_callback(self, prompt):
        """Test that Shift-Tab is safe when no callback is set."""
        kb = prompt._create_key_bindings()
        prompt.mode_change_callback = None

        event = MagicMock(spec=KeyPressEvent)

        handler = kb.get_bindings_for_keys(("s-tab",))[0].handler
        handler(event)


class TestInteractivePromptInputHandling:
    """Tests for async input handling edge cases."""

    @pytest.fixture
    def prompt(self, mock_context, mock_prompt_session):
        """Create an InteractivePrompt for testing."""
        prompt = InteractivePrompt(mock_context, ["/help"])
        prompt.prompt_session = mock_prompt_session
        return prompt

    @pytest.mark.asyncio
    async def test_get_input_handles_keyboard_interrupt(self, prompt):
        """Test that get_input propagates KeyboardInterrupt for clean exit."""
        with patch.object(
            prompt.prompt_session, "prompt_async", new_callable=AsyncMock
        ) as mock_prompt:
            mock_prompt.side_effect = KeyboardInterrupt()
            with pytest.raises(KeyboardInterrupt):
                await prompt.get_input()

    @pytest.mark.asyncio
    async def test_get_input_handles_eof_error(self, prompt):
        """Test that get_input propagates EOFError for clean exit."""
        with patch.object(
            prompt.prompt_session, "prompt_async", new_callable=AsyncMock
        ) as mock_prompt:
            mock_prompt.side_effect = EOFError()
            with pytest.raises(EOFError):
                await prompt.get_input()

    @pytest.mark.asyncio
    async def test_get_input_uses_prefilled_text_and_clears_it(self, prompt):
        """Test that prefilled text is used once and then cleared."""
        mock_cli_session = MagicMock()
        mock_cli_session.prefilled_text = "prefilled content"
        prompt.session = mock_cli_session

        with patch.object(
            prompt.prompt_session, "prompt_async", new_callable=AsyncMock
        ) as mock_prompt:
            mock_prompt.return_value = "prefilled content"
            await prompt.get_input()

            call_kwargs = mock_prompt.call_args[1]
            assert call_kwargs["default"] == "prefilled content"
            assert mock_cli_session.prefilled_text is None

    @pytest.mark.asyncio
    async def test_get_input_identifies_commands_correctly(self, prompt):
        """Test command detection logic for slash commands."""
        with patch.object(
            prompt.prompt_session, "prompt_async", new_callable=AsyncMock
        ) as mock_prompt:
            mock_prompt.return_value = "/help"
            content, is_command = await prompt.get_input()
            assert is_command is True

            mock_prompt.return_value = "  /resume  "
            content, is_command = await prompt.get_input()
            assert is_command is True
            assert content == "/resume"

            mock_prompt.return_value = "not a command"
            content, is_command = await prompt.get_input()
            assert is_command is False

    @pytest.mark.asyncio
    async def test_get_input_treats_absolute_paths_as_content(self, prompt):
        """Test that absolute file paths are NOT treated as commands."""
        with patch.object(
            prompt.prompt_session, "prompt_async", new_callable=AsyncMock
        ) as mock_prompt:
            # Absolute path should not be a command
            mock_prompt.return_value = "/Users/name/image.png"
            content, is_command = await prompt.get_input()
            assert is_command is False
            assert content == "/Users/name/image.png"

            # Multiple slashes = file path
            mock_prompt.return_value = "/home/user/Downloads/file.jpg"
            content, is_command = await prompt.get_input()
            assert is_command is False

            # Path with spaces in message
            mock_prompt.return_value = "/path/to/image.png describe this"
            content, is_command = await prompt.get_input()
            assert is_command is False

    @pytest.mark.asyncio
    async def test_get_input_unknown_commands_detected(self, prompt):
        """Test that unknown single-word commands are still treated as commands."""
        with patch.object(
            prompt.prompt_session, "prompt_async", new_callable=AsyncMock
        ) as mock_prompt:
            # Unknown command (no slashes after first)
            mock_prompt.return_value = "/unknown"
            content, is_command = await prompt.get_input()
            assert is_command is True

            # Known command with args
            mock_prompt.return_value = "/help something"
            content, is_command = await prompt.get_input()
            assert is_command is True
