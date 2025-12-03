"""Middleware to repair unfinished tool calls after interruptions."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import AIMessage, RemoveMessage, ToolMessage
from langgraph.graph.message import REMOVE_ALL_MESSAGES

from src.agents.context import AgentContext
from src.agents.state import AgentState
from src.core.logging import get_logger
from src.utils.render import create_tool_message

if TYPE_CHECKING:
    from langgraph.runtime import Runtime

logger = get_logger(__name__)


class PendingToolResultMiddleware(AgentMiddleware[AgentState, AgentContext]):
    """Inject error ToolMessages for tool calls that never returned."""

    state_schema = AgentState

    async def abefore_agent(
        self, state: AgentState, runtime: Runtime[AgentContext]
    ) -> dict[str, Any] | None:
        messages = state.get("messages", [])
        if not messages:
            return None

        last_ai_index = None
        for idx in range(len(messages) - 1, -1, -1):
            if isinstance(messages[idx], AIMessage):
                last_ai_index = idx
                break

        if last_ai_index is None:
            return None

        last_ai = messages[last_ai_index]
        tool_calls = getattr(last_ai, "tool_calls", None) or []
        if not tool_calls:
            return None

        expected_tool_call_ids = {
            call.get("id") for call in tool_calls if call.get("id")
        }
        if not expected_tool_call_ids:
            return None

        existing_results: dict[str, tuple[int, ToolMessage]] = {}
        for idx in range(last_ai_index + 1, len(messages)):
            msg = messages[idx]
            if (
                isinstance(msg, ToolMessage)
                and msg.tool_call_id in expected_tool_call_ids
            ):
                existing_results[msg.tool_call_id] = (idx, msg)

        missing_call_ids = expected_tool_call_ids - existing_results.keys()

        injected_lookup = {
            call["id"]: create_tool_message(
                result="Interrupted.",
                tool_name=call.get("name") or "unknown_tool",
                tool_call_id=call["id"],
                is_error=True,
            )
            for call in tool_calls
            if call.get("id") in missing_call_ids
        }

        if not injected_lookup and not existing_results:
            return None

        needs_repair = any(
            any(
                not isinstance(messages[check_idx], (AIMessage, ToolMessage))
                for check_idx in range(last_ai_index + 1, idx)
            )
            for idx, _ in existing_results.values()
        )

        if not injected_lookup and not needs_repair:
            return None

        repaired = list(messages[: last_ai_index + 1])

        for call in tool_calls:
            call_id = call.get("id")
            if call_id in existing_results:
                repaired.append(existing_results[call_id][1])
            elif call_id in injected_lookup:
                repaired.append(injected_lookup[call_id])

        existing_result_indices = {idx for idx, _ in existing_results.values()}
        repaired.extend(
            messages[idx]
            for idx in range(last_ai_index + 1, len(messages))
            if idx not in existing_result_indices
        )

        logger.debug(
            "Repaired tool results: %d moved, %d interrupted",
            len(existing_results),
            len(injected_lookup),
        )
        return {"messages": [RemoveMessage(id=REMOVE_ALL_MESSAGES), *repaired]}
