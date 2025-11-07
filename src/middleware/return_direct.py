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
        """
        Check recent messages for a tool-initiated return_direct signal and request jumping to the end if found.
        
        Scans the state's messages in reverse order and, if it encounters a ToolMessage with a truthy `return_direct` attribute, returns a control directive to jump to "end". Scanning stops when a non-ToolMessage is encountered.
        
        Parameters:
            state (AgentState): Agent state mapping containing a "messages" sequence.
            runtime (Runtime[AgentContext]): Execution runtime context (unused by this hook).
        
        Returns:
            dict[str, Any] | None: `{"jump_to": "end"}` if a qualifying ToolMessage is found, `None` otherwise.
        """
        messages = state.get("messages", [])

        # Check recent tool messages for return_direct
        for msg in reversed(messages):
            if isinstance(msg, ToolMessage):
                if getattr(msg, "return_direct", False):
                    return {"jump_to": "end"}
            elif not isinstance(msg, ToolMessage):
                break

        return None