import pytest


@pytest.fixture
def create_test_graph():
    """Factory fixture for creating test graphs with tools."""

    def _create(tools: list):
        """
        Create and compile a simple StateGraph containing a ToolNode preconfigured for testing.
        
        Parameters:
            tools (list): Sequence of tool definitions (callables or tool descriptors accepted by ToolNode) to include in the graph.
        
        Returns:
            compiled_graph: The compiled LangGraph application ready for execution, compiled using an in-memory checkpointer.
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