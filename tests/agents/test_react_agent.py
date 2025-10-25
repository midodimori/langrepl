from unittest.mock import Mock

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from src.agents.react_agent import (
    _get_prompt_runnable,
    _validate_chat_history,
)


class TestValidateChatHistory:
    def test_valid_history_with_tool_results(self):
        messages = [
            HumanMessage(content="test"),
            AIMessage(
                content="", tool_calls=[{"id": "call_123", "name": "tool1", "args": {}}]
            ),
            ToolMessage(content="result", tool_call_id="call_123"),
        ]
        _validate_chat_history(messages)

    def test_invalid_history_missing_tool_result(self):
        messages = [
            HumanMessage(content="test"),
            AIMessage(
                content="", tool_calls=[{"id": "call_123", "name": "tool1", "args": {}}]
            ),
        ]

        with pytest.raises(ValueError, match="do not have a corresponding ToolMessage"):
            _validate_chat_history(messages)

    def test_empty_history(self):
        _validate_chat_history([])

    def test_no_tool_calls(self):
        messages = [HumanMessage(content="test"), AIMessage(content="response")]
        _validate_chat_history(messages)

    def test_multiple_tool_calls_all_resolved(self):
        messages = [
            HumanMessage(content="test"),
            AIMessage(
                content="",
                tool_calls=[
                    {"id": "call_1", "name": "tool1", "args": {}},
                    {"id": "call_2", "name": "tool2", "args": {}},
                ],
            ),
            ToolMessage(content="result1", tool_call_id="call_1"),
            ToolMessage(content="result2", tool_call_id="call_2"),
        ]
        _validate_chat_history(messages)

    def test_multiple_tool_calls_partial_resolution(self):
        messages = [
            HumanMessage(content="test"),
            AIMessage(
                content="",
                tool_calls=[
                    {"id": "call_1", "name": "tool1", "args": {}},
                    {"id": "call_2", "name": "tool2", "args": {}},
                ],
            ),
            ToolMessage(content="result1", tool_call_id="call_1"),
        ]

        with pytest.raises(ValueError, match="do not have a corresponding ToolMessage"):
            _validate_chat_history(messages)


class TestGetPromptRunnable:
    def test_with_system_message(self):
        from langchain_core.messages import SystemMessage

        prompt = SystemMessage(content="You are a helpful assistant")
        runnable = _get_prompt_runnable(prompt)

        assert runnable is not None
        assert runnable.name == "Prompt"

    def test_runnable_prepends_system_message(self):
        from langchain_core.messages import SystemMessage

        prompt = SystemMessage(content="System prompt")
        runnable = _get_prompt_runnable(prompt)

        mock_state = Mock()
        mock_state.messages = [HumanMessage(content="User message")]

        result = runnable.invoke(mock_state)

        assert len(result) == 2
        assert result[0].type == "system"
        assert result[0].content == "System prompt"
        assert result[1].type == "human"
