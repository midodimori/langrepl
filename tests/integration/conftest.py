import pytest


def pytest_collection_modifyitems(config, items):
    """Auto-apply integration marker to all tests in integration directory."""
    for item in items:
        if "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)


@pytest.fixture
def create_test_graph():
    """Factory fixture for creating test graphs with tools."""

    def _create(tools: list):
        """Create a simple graph with tools for testing.

        Args:
            tools: List of tools to include in the graph

        Returns:
            Compiled LangGraph application
        """
        from langgraph.checkpoint.memory import MemorySaver
        from langgraph.graph import StateGraph
        from langgraph.prebuilt import ToolNode

        from langrepl.agents.context import AgentContext
        from langrepl.agents.state import AgentState

        graph = StateGraph(AgentState, context_schema=AgentContext)

        # Add tool node with error handling
        tool_node = ToolNode(tools, handle_tool_errors=True)
        graph.add_node("tools", tool_node)

        # Simple flow: START -> tools -> END
        graph.set_entry_point("tools")
        graph.set_finish_point("tools")

        checkpointer = MemorySaver()
        return graph.compile(checkpointer=checkpointer)

    return _create
