from typing import cast
from unittest.mock import AsyncMock, Mock

import pytest
from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, SystemMessage

from src.utils.compression import (
    calculate_message_tokens,
    compress_messages,
    should_auto_compress,
)


class TestShouldAutoCompress:
    def test_should_compress_at_threshold(self):
        result = should_auto_compress(
            current_tokens=80, context_window=100, threshold=0.8
        )
        assert result is True

    def test_should_compress_above_threshold(self):
        result = should_auto_compress(
            current_tokens=90, context_window=100, threshold=0.8
        )
        assert result is True

    def test_should_not_compress_below_threshold(self):
        result = should_auto_compress(
            current_tokens=70, context_window=100, threshold=0.8
        )
        assert result is False

    def test_no_context_window(self):
        result = should_auto_compress(
            current_tokens=1000, context_window=None, threshold=0.8
        )
        assert result is False

    def test_zero_context_window(self):
        result = should_auto_compress(
            current_tokens=1000, context_window=0, threshold=0.8
        )
        assert result is False

    def test_negative_context_window(self):
        result = should_auto_compress(
            current_tokens=1000, context_window=-100, threshold=0.8
        )
        assert result is False

    def test_exact_threshold(self):
        result = should_auto_compress(
            current_tokens=800, context_window=1000, threshold=0.8
        )
        assert result is True

    def test_high_threshold(self):
        result = should_auto_compress(
            current_tokens=95, context_window=100, threshold=0.95
        )
        assert result is True


class TestCalculateMessageTokens:
    def test_calculate_tokens(self):
        mock_llm = Mock()
        mock_llm.get_num_tokens_from_messages.return_value = 42

        messages = [HumanMessage(content="test")]
        result = calculate_message_tokens(messages, mock_llm)

        assert result == 42
        mock_llm.get_num_tokens_from_messages.assert_called_once()


class TestCompressMessages:
    @pytest.mark.asyncio
    async def test_empty_messages(self):
        mock_llm = AsyncMock()
        result = await compress_messages([], mock_llm)
        assert result == []

    @pytest.mark.asyncio
    async def test_only_system_messages(self):
        mock_llm = AsyncMock()
        messages = [
            SystemMessage(content="You are a helpful assistant"),
            SystemMessage(content="Follow these rules"),
        ]
        result = await compress_messages(messages, mock_llm)
        assert result == messages

    @pytest.mark.asyncio
    async def test_compress_with_system_and_other_messages(self):
        mock_llm = AsyncMock()
        mock_response = AIMessage(content="Summary of conversation")
        mock_llm.ainvoke.return_value = mock_response

        messages = cast(
            list[AnyMessage],
            [
                SystemMessage(content="System prompt"),
                HumanMessage(content="Hello"),
                AIMessage(content="Hi there"),
            ],
        )

        result = await compress_messages(messages, mock_llm)

        assert len(result) == 2
        assert result[0].type == "system"
        assert result[1].type == "ai"
        assert "Previous conversation summary" in result[1].content
        assert result[1].name == "compression_summary"

    @pytest.mark.asyncio
    async def test_preserves_all_system_messages(self):
        mock_llm = AsyncMock()
        mock_response = AIMessage(content="Summary")
        mock_llm.ainvoke.return_value = mock_response

        messages = cast(
            list[AnyMessage],
            [
                SystemMessage(content="System 1"),
                SystemMessage(content="System 2"),
                HumanMessage(content="User message"),
            ],
        )

        result = await compress_messages(messages, mock_llm)

        system_messages = [msg for msg in result if msg.type == "system"]
        assert len(system_messages) == 2
        assert system_messages[0].content == "System 1"
        assert system_messages[1].content == "System 2"
