"""Middleware for handling return_direct behavior in tools."""

from typing import Any

from langchain.agents.middleware import AgentMiddleware, hook_config
from langchain_core.messages import ToolMessage
from langgraph.runtime import Runtime

from src.agents.context import AgentContext
from src.agents.state import AgentState


class ReturnDirectMiddleware(AgentMiddleware[AgentState, AgentContext]):
    """Middleware to handle return_direct behavior for tools.

    Checks for:
    1. Tools with return_direct=True attribute
    2. ToolMessages with return_direct=True attribute (e.g., denied actions)
    """

    @hook_config(can_jump_to=["end"])
    async def abefore_model(
        self, state: AgentState, runtime: Runtime[AgentContext]
    ) -> dict[str, Any] | None:
        messages = state.get("messages", [])

        # Check recent tool messages for return_direct
        for msg in reversed(messages):
            if isinstance(msg, ToolMessage):
                if getattr(msg, "return_direct", False):
                    return {"jump_to": "end"}
            elif not isinstance(msg, ToolMessage):
                break

        return None
