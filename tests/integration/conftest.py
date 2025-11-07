import pytest


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

        from src.agents.context import AgentContext
        from src.agents.state import AgentState

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
