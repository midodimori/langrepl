"""Middleware for tracking token usage and calculating costs."""

from typing import Any

from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import AIMessage
from langgraph.runtime import Runtime

from src.agents.context import AgentContext
from src.agents.state import AgentState
from src.core.logging import get_logger
from src.utils.cost import calculate_cost

logger = get_logger(__name__)


class TokenCostMiddleware(AgentMiddleware[AgentState, AgentContext]):
    """Middleware to track token usage and calculate costs.

    Extracts usage metadata from model responses and updates state with:
    - current_input_tokens: Input tokens for this call
    - current_output_tokens: Output tokens for this call
    - total_cost: Cost for this call (if pricing is available)
    """

    state_schema = AgentState

    async def aafter_model(
        self, state: AgentState, runtime: Runtime[AgentContext]
    ) -> dict[str, Any] | None:
        """Extract usage metadata and calculate cost after model call."""
        messages = state.get("messages", [])
        if not messages:
            return None

        latest_message = messages[-1]
        if not isinstance(latest_message, AIMessage):
            return None

        usage_metadata = getattr(latest_message, "usage_metadata", None)
        if not usage_metadata:
            return None

        input_tokens = usage_metadata.get("input_tokens", 0)
        output_tokens = usage_metadata.get("output_tokens", 0)

        update: dict[str, Any] = {
            "current_input_tokens": input_tokens,
            "current_output_tokens": output_tokens,
        }

        context: AgentContext = runtime.context
        input_cost = context.input_cost_per_mtok
        output_cost = context.output_cost_per_mtok

        if input_cost is not None and output_cost is not None:
            call_cost = calculate_cost(
                input_tokens,
                output_tokens,
                input_cost,
                output_cost,
            )
            update["total_cost"] = call_cost
            logger.debug(
                f"Token usage: {input_tokens} in, {output_tokens} out. Cost: ${call_cost:.4f}"
            )

        return update
