"""Tests for interrupt handler."""

from unittest.mock import MagicMock, patch

import pytest
from langgraph.types import Interrupt

from src.cli.handlers.interrupts import InterruptHandler
from src.tools.wrapper import InterruptPayload


class TestInterruptHandler:
    """Tests for InterruptHandler class."""

    @pytest.mark.asyncio
    async def test_handle_returns_none_for_empty_interrupt_data(self):
        """Test that handle returns None for empty interrupt data."""
        handler = InterruptHandler()

        result = await handler.handle([])

        assert result is None

    @pytest.mark.asyncio
    @patch("src.cli.handlers.interrupts.PromptSession")
    async def test_handle_with_valid_choice(
        self, mock_prompt_session_cls, mock_prompt_session
    ):
        """Test that handle returns user's valid choice."""
        handler = InterruptHandler()

        payload = InterruptPayload(
            question="Choose an option:", options=["allow", "deny", "skip"]
        )
        interrupt = Interrupt(value=payload)

        mock_prompt_session.prompt_async.return_value = "allow"
        mock_prompt_session_cls.return_value = mock_prompt_session

        result = await handler.handle([interrupt])

        assert result == "allow"

    @pytest.mark.asyncio
    @patch("src.cli.handlers.interrupts.PromptSession")
    async def test_handle_with_partial_match(
        self, mock_prompt_session_cls, mock_prompt_session
    ):
        """Test that handle accepts partial matches."""
        handler = InterruptHandler()

        payload = InterruptPayload(
            question="Choose an option:", options=["allow", "deny"]
        )
        interrupt = Interrupt(value=payload)

        mock_prompt_session.prompt_async.return_value = "al"
        mock_prompt_session_cls.return_value = mock_prompt_session

        result = await handler.handle([interrupt])

        assert result == "allow"

    @pytest.mark.asyncio
    @patch("src.cli.handlers.interrupts.PromptSession")
    async def test_handle_with_case_insensitive_match(
        self, mock_prompt_session_cls, mock_prompt_session
    ):
        """Test that handle is case-insensitive."""
        handler = InterruptHandler()

        payload = InterruptPayload(
            question="Choose an option:", options=["Allow", "Deny"]
        )
        interrupt = Interrupt(value=payload)

        mock_prompt_session.prompt_async.return_value = "allow"
        mock_prompt_session_cls.return_value = mock_prompt_session

        result = await handler.handle([interrupt])

        assert result == "Allow"

    @pytest.mark.asyncio
    @patch("src.cli.handlers.interrupts.PromptSession")
    async def test_handle_with_empty_input_reprompts(
        self, mock_prompt_session_cls, mock_prompt_session
    ):
        """Test that handle re-prompts on empty input."""
        handler = InterruptHandler()

        payload = InterruptPayload(
            question="Choose an option:", options=["allow", "deny"]
        )
        interrupt = Interrupt(value=payload)

        mock_prompt_session.prompt_async.side_effect = ["", "  ", "allow"]
        mock_prompt_session_cls.return_value = mock_prompt_session

        result = await handler.handle([interrupt])

        assert result == "allow"
        assert mock_prompt_session.prompt_async.call_count == 3

    @pytest.mark.asyncio
    @patch("src.cli.handlers.interrupts.PromptSession")
    async def test_handle_with_invalid_choice_reprompts(
        self, mock_prompt_session_cls, mock_prompt_session
    ):
        """Test that handle re-prompts on invalid choice."""
        handler = InterruptHandler()

        payload = InterruptPayload(
            question="Choose an option:", options=["allow", "deny"]
        )
        interrupt = Interrupt(value=payload)

        mock_prompt_session.prompt_async.side_effect = ["invalid", "allow"]
        mock_prompt_session_cls.return_value = mock_prompt_session

        result = await handler.handle([interrupt])

        assert result == "allow"
        assert mock_prompt_session.prompt_async.call_count == 2

    @pytest.mark.asyncio
    @patch("src.cli.handlers.interrupts.PromptSession")
    async def test_handle_with_ambiguous_choice_reprompts(
        self, mock_prompt_session_cls, mock_prompt_session
    ):
        """Test that handle re-prompts on ambiguous partial match."""
        handler = InterruptHandler()

        payload = InterruptPayload(
            question="Choose an option:", options=["allow", "always allow"]
        )
        interrupt = Interrupt(value=payload)

        mock_prompt_session.prompt_async.side_effect = ["al", "allow"]
        mock_prompt_session_cls.return_value = mock_prompt_session

        result = await handler.handle([interrupt])

        assert result == "allow"
        assert mock_prompt_session.prompt_async.call_count == 2

    @pytest.mark.asyncio
    @patch("src.cli.handlers.interrupts.PromptSession")
    async def test_handle_with_keyboard_interrupt(
        self, mock_prompt_session_cls, mock_prompt_session
    ):
        """Test that handle returns empty string on KeyboardInterrupt."""
        handler = InterruptHandler()

        payload = InterruptPayload(
            question="Choose an option:", options=["allow", "deny"]
        )
        interrupt = Interrupt(value=payload)

        mock_prompt_session.prompt_async.side_effect = KeyboardInterrupt()
        mock_prompt_session_cls.return_value = mock_prompt_session

        result = await handler.handle([interrupt])

        assert result == ""

    @pytest.mark.asyncio
    @patch("src.cli.handlers.interrupts.PromptSession")
    async def test_handle_with_eof_error(
        self, mock_prompt_session_cls, mock_prompt_session
    ):
        """Test that handle returns empty string on EOFError."""
        handler = InterruptHandler()

        payload = InterruptPayload(
            question="Choose an option:", options=["allow", "deny"]
        )
        interrupt = Interrupt(value=payload)

        mock_prompt_session.prompt_async.side_effect = EOFError()
        mock_prompt_session_cls.return_value = mock_prompt_session

        result = await handler.handle([interrupt])

        assert result == ""

    @pytest.mark.asyncio
    async def test_handle_with_exception_returns_none(self):
        """Test that handle returns None on exception."""
        handler = InterruptHandler()

        interrupt = MagicMock()
        interrupt.value = None

        result = await handler.handle([interrupt])

        assert result is None
