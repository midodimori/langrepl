"""Tests for PendingToolResultMiddleware."""

from unittest.mock import AsyncMock

import pytest
from langchain_core.messages import AIMessage, HumanMessage, RemoveMessage, ToolMessage

from src.agents.state import AgentState
from src.middleware.pending_tool_result import PendingToolResultMiddleware


@pytest.fixture
def middleware():
    return PendingToolResultMiddleware()


@pytest.fixture
def mock_runtime(agent_context):
    runtime = AsyncMock()
    runtime.context = agent_context
    return runtime


@pytest.mark.asyncio
async def test_no_messages(middleware, mock_runtime):
    state = AgentState(
        messages=[],
        todos=None,
        files=None,
        current_input_tokens=None,
        current_output_tokens=None,
        total_cost=None,
    )
    result = await middleware.abefore_agent(state, mock_runtime)
    assert result is None


@pytest.mark.asyncio
async def test_no_ai_message(middleware, mock_runtime):
    state = AgentState(
        messages=[HumanMessage(content="hello")],
        todos=None,
        files=None,
        current_input_tokens=None,
        current_output_tokens=None,
        total_cost=None,
    )
    result = await middleware.abefore_agent(state, mock_runtime)
    assert result is None


@pytest.mark.asyncio
async def test_ai_message_without_tool_calls(middleware, mock_runtime):
    state = AgentState(
        messages=[
            HumanMessage(content="hello"),
            AIMessage(content="response"),
        ],
        todos=None,
        files=None,
        current_input_tokens=None,
        current_output_tokens=None,
        total_cost=None,
    )
    result = await middleware.abefore_agent(state, mock_runtime)
    assert result is None


@pytest.mark.asyncio
async def test_inject_interrupted_for_missing_tool_result(middleware, mock_runtime):
    state = AgentState(
        messages=[
            HumanMessage(content="hello"),
            AIMessage(
                content="calling tool",
                tool_calls=[{"id": "call_1", "name": "test_tool", "args": {}}],
            ),
        ],
        todos=None,
        files=None,
        current_input_tokens=None,
        current_output_tokens=None,
        total_cost=None,
    )
    result = await middleware.abefore_agent(state, mock_runtime)
    assert result is not None
    messages = result["messages"]
    assert isinstance(messages[0], RemoveMessage)
    assert len(messages) == 4
    assert isinstance(messages[1], HumanMessage)
    assert messages[1].content == "hello"
    assert isinstance(messages[2], AIMessage)
    assert messages[2].content == "calling tool"
    assert len(messages[2].tool_calls) == 1
    tool_call = messages[2].tool_calls[0]
    assert tool_call.get("id") == "call_1"
    assert tool_call.get("name") == "test_tool"
    assert tool_call.get("args") == {}
    assert isinstance(messages[3], ToolMessage)
    assert messages[3].tool_call_id == "call_1"
    assert messages[3].content == "Interrupted."


@pytest.mark.asyncio
async def test_move_tool_result_after_human_message(middleware, mock_runtime):
    state = AgentState(
        messages=[
            AIMessage(
                content="calling tool",
                tool_calls=[{"id": "call_1", "name": "test_tool", "args": {}}],
            ),
            HumanMessage(content="interrupt"),
            ToolMessage(content="result", tool_call_id="call_1"),
        ],
        todos=None,
        files=None,
        current_input_tokens=None,
        current_output_tokens=None,
        total_cost=None,
    )
    result = await middleware.abefore_agent(state, mock_runtime)
    assert result is not None
    messages = result["messages"]
    assert isinstance(messages[0], RemoveMessage)
    assert len(messages) == 4
    assert isinstance(messages[1], AIMessage)
    assert isinstance(messages[2], ToolMessage)
    assert messages[2].tool_call_id == "call_1"
    assert isinstance(messages[3], HumanMessage)


@pytest.mark.asyncio
async def test_multiple_tool_calls_mixed_results(middleware, mock_runtime):
    state = AgentState(
        messages=[
            AIMessage(
                content="calling tools",
                tool_calls=[
                    {"id": "call_1", "name": "tool_1", "args": {}},
                    {"id": "call_2", "name": "tool_2", "args": {}},
                ],
            ),
            HumanMessage(content="interrupt"),
            ToolMessage(content="result_1", tool_call_id="call_1"),
        ],
        todos=None,
        files=None,
        current_input_tokens=None,
        current_output_tokens=None,
        total_cost=None,
    )
    result = await middleware.abefore_agent(state, mock_runtime)
    assert result is not None
    messages = result["messages"]
    assert isinstance(messages[0], RemoveMessage)
    assert len(messages) == 5
    assert isinstance(messages[1], AIMessage)
    assert isinstance(messages[2], ToolMessage)
    assert messages[2].tool_call_id == "call_1"
    assert isinstance(messages[3], ToolMessage)
    assert messages[3].tool_call_id == "call_2"
    assert messages[3].content == "Interrupted."
    assert isinstance(messages[4], HumanMessage)


@pytest.mark.asyncio
async def test_tool_results_in_correct_position(middleware, mock_runtime):
    state = AgentState(
        messages=[
            AIMessage(
                content="calling tool",
                tool_calls=[{"id": "call_1", "name": "test_tool", "args": {}}],
            ),
            ToolMessage(content="result", tool_call_id="call_1"),
            HumanMessage(content="next message"),
        ],
        todos=None,
        files=None,
        current_input_tokens=None,
        current_output_tokens=None,
        total_cost=None,
    )
    result = await middleware.abefore_agent(state, mock_runtime)
    assert result is None


@pytest.mark.asyncio
async def test_multiple_tool_results_correct_order(middleware, mock_runtime):
    state = AgentState(
        messages=[
            AIMessage(
                content="calling tools",
                tool_calls=[
                    {"id": "call_1", "name": "tool_1", "args": {}},
                    {"id": "call_2", "name": "tool_2", "args": {}},
                ],
            ),
            HumanMessage(content="interrupt"),
            ToolMessage(content="result_2", tool_call_id="call_2"),
            ToolMessage(content="result_1", tool_call_id="call_1"),
        ],
        todos=None,
        files=None,
        current_input_tokens=None,
        current_output_tokens=None,
        total_cost=None,
    )
    result = await middleware.abefore_agent(state, mock_runtime)
    assert result is not None
    messages = result["messages"]
    assert isinstance(messages[0], RemoveMessage)
    assert len(messages) == 5
    assert isinstance(messages[1], AIMessage)
    assert isinstance(messages[2], ToolMessage)
    assert messages[2].tool_call_id == "call_1"
    assert messages[2].content == "result_1"
    assert isinstance(messages[3], ToolMessage)
    assert messages[3].tool_call_id == "call_2"
    assert messages[3].content == "result_2"
    assert isinstance(messages[4], HumanMessage)
