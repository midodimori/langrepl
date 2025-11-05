from unittest.mock import Mock

import pytest
from langchain_core.messages import HumanMessage

from src.agents.react_agent import (
    _get_prompt_runnable,
    _validate_chat_history,
)


class TestValidateChatHistory:
    def test_valid_history_with_tool_results(self, tool_call_messages):
        _validate_chat_history(tool_call_messages["single_resolved"])

    def test_invalid_history_missing_tool_result(self, tool_call_messages):
        with pytest.raises(ValueError, match="do not have a corresponding ToolMessage"):
            _validate_chat_history(tool_call_messages["single_unresolved"])

    def test_empty_history(self):
        _validate_chat_history([])

    def test_no_tool_calls(self, sample_messages):
        _validate_chat_history(sample_messages)

    def test_multiple_tool_calls_all_resolved(self, tool_call_messages):
        _validate_chat_history(tool_call_messages["multiple_resolved"])

    def test_multiple_tool_calls_partial_resolution(self, tool_call_messages):
        with pytest.raises(ValueError, match="do not have a corresponding ToolMessage"):
            _validate_chat_history(tool_call_messages["multiple_partial"])


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
