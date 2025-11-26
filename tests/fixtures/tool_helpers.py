"""Reusable test helpers for tool integration tests."""

from typing import Any

from langchain_core.messages import AIMessage, HumanMessage


def make_tool_call(tool_name: str, call_id: str = "call_1", **kwargs: Any) -> dict:
    """Create a tool call message state.

    Args:
        tool_name: Name of the tool to call
        call_id: Tool call ID (default: "call_1")
        **kwargs: Tool arguments as keyword arguments

    Returns:
        Message state dict with tool call

    Example:
        >>> make_tool_call("read_file", file_path="test.txt", limit=100)
        >>> make_tool_call("edit_file", edits=[...], file_path="foo.py")
    """
    return {
        "messages": [
            HumanMessage(content="Execute tool"),
            AIMessage(
                content="",
                tool_calls=[{"id": call_id, "name": tool_name, "args": kwargs}],
            ),
        ]
    }


async def run_tool(
    app,
    tool_call_state: dict,
    agent_context=None,
    thread_id: str = "test",
    **config_kwargs: Any,
) -> Any:
    """Execute a tool call through the agent graph.

    Args:
        app: Agent graph application
        tool_call_state: Tool call message state (from make_tool_call)
        agent_context: Agent context fixture (optional, for context-based tests)
        thread_id: Thread ID for the conversation (default: "test")
        **config_kwargs: Additional config values (working_dir, approval_mode, etc.)

    Returns:
        Agent execution result

    Example:
        >>> await run_tool(app, state, agent_context)  # With context
        >>> await run_tool(app, state, working_dir=str(tmp), approval_mode="aggressive")  # With kwargs
    """
    config = {"configurable": {"thread_id": thread_id, **config_kwargs}}

    if agent_context is not None:
        return await app.ainvoke(tool_call_state, config=config, context=agent_context)
    else:
        return await app.ainvoke(tool_call_state, config=config)
