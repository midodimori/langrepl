"""AG-UI agent service — LangreplAGUIAgent subclass and context builder."""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

import ag_ui_langgraph.agent as _agui_agent_mod
from ag_ui.core import (
    CustomEvent,
    EventType,
    ReasoningMessageStartEvent,
)
from ag_ui_langgraph import LangGraphAgent
from ag_ui_langgraph.types import LangGraphEventTypes
from pydantic import model_validator


# Fix ag-ui-langgraph bug: passes role="assistant" but ag-ui-protocol requires "reasoning"
class _FixedReasoningMessageStartEvent(ReasoningMessageStartEvent):
    @model_validator(mode="before")
    @classmethod
    def _fix_role(cls, data: dict) -> dict:
        if isinstance(data, dict) and data.get("role") == "assistant":
            data["role"] = "reasoning"
        return data


_agui_agent_mod.ReasoningMessageStartEvent = _FixedReasoningMessageStartEvent
from langchain_core.runnables import RunnableConfig
from langgraph.graph.state import CompiledStateGraph
from langgraph.runtime import Runtime

from langrepl.agents.context import AgentContext
from langrepl.cli.bootstrap.initializer import initializer
from langrepl.configs import ApprovalMode
from langrepl.core.constants import OS_VERSION, PLATFORM

logger = logging.getLogger(__name__)


class LangreplAGUIAgent(LangGraphAgent):
    """AG-UI agent with AgentContext injection, MCP safety, and interrupt fix."""

    def __init__(
        self,
        *,
        name: str,
        graph: CompiledStateGraph,
        working_dir: Path,
        approval_mode: ApprovalMode = ApprovalMode.SEMI_ACTIVE,
        description: str | None = None,
        config: RunnableConfig | dict | None = None,
    ) -> None:
        super().__init__(name=name, graph=graph, description=description, config=config)
        self.working_dir = working_dir
        self.approval_mode = approval_mode

    async def run(self, input) -> AsyncGenerator[str]:
        """Override to fix ag-ui-langgraph bugs and bridge reasoning to CopilotKit.

        - Buffers RUN_FINISHED, checks all tasks for missed interrupts
        - Converts REASONING_* events to STATE_DELTA (CopilotKit has no reasoning support)
        """
        saw_interrupt = False
        buffered_run_finished = None
        reasoning_state: dict | None = None

        async for event in super().run(input):
            event_type = getattr(event, "type", None)

            # Track if parent already emitted an interrupt
            if event_type == EventType.CUSTOM:
                if (
                    hasattr(event, "name")
                    and event.name == LangGraphEventTypes.OnInterrupt.value
                ):
                    saw_interrupt = True

            # Buffer RUN_FINISHED — we may need to inject interrupt events before it
            if event_type == EventType.RUN_FINISHED:
                buffered_run_finished = event
                continue

            # Bridge reasoning events into STATE_SNAPSHOT for CopilotKit
            # (CopilotKit has no REASONING_* support)
            if event_type == EventType.REASONING_MESSAGE_CONTENT:
                text = reasoning_state["text"] if reasoning_state else ""
                text += getattr(event, "delta", "")
                reasoning_state = {"text": text, "active": True}
            elif event_type in (
                EventType.REASONING_MESSAGE_END,
                EventType.REASONING_END,
            ):
                if reasoning_state:
                    reasoning_state["active"] = False

            # Inject reasoning into library's STATE_SNAPSHOT events
            if event_type == EventType.STATE_SNAPSHOT and reasoning_state:
                snapshot = getattr(event, "snapshot", None)
                if isinstance(snapshot, dict):
                    snapshot["reasoning"] = reasoning_state

            yield event

        # Check tasks for missed interrupts before emitting RUN_FINISHED.
        # Upstream only checks tasks[0] — emit interrupts from remaining tasks.
        # When saw_interrupt is True, parent already handled tasks[0], so skip it.
        if buffered_run_finished:
            thread_id = input.thread_id
            config = {"configurable": {"thread_id": thread_id}}
            try:
                state = await self.graph.aget_state(config)
                if state.tasks:
                    tasks_to_check = state.tasks[1:] if saw_interrupt else state.tasks
                    for task in tasks_to_check:
                        for intr in task.interrupts:
                            value = intr.value
                            if hasattr(value, "model_dump"):
                                value = value.model_dump()
                            logger.debug("Emitting missed interrupt: %s", value)
                            yield self._dispatch_event(
                                CustomEvent(
                                    type=EventType.CUSTOM,
                                    name=LangGraphEventTypes.OnInterrupt.value,
                                    value=(
                                        json.dumps(value)
                                        if not isinstance(value, str)
                                        else value
                                    ),
                                )
                            )
            except Exception:
                logger.debug("Failed to check for missed interrupts", exc_info=True)

        if buffered_run_finished:
            yield buffered_run_finished

    def get_stream_kwargs(
        self,
        input: Any,
        subgraphs: bool = False,
        version: Literal["v1", "v2"] = "v2",
        config: RunnableConfig | None = None,
        context: dict[str, Any] | None = None,
        fork: Any | None = None,
    ):
        """Override to inject AgentContext via __pregel_runtime."""
        kwargs = super().get_stream_kwargs(
            input=input,
            subgraphs=subgraphs,
            version=version,
            config=config,
            context=context,
            fork=fork,
        )

        cfg = kwargs.get("config") or {}
        configurable = cfg.get("configurable", {})

        agent_context = build_agent_context(
            working_dir=self.working_dir,
            approval_mode=self.approval_mode,
        )
        configurable["__pregel_runtime"] = Runtime(context=agent_context)
        cfg["configurable"] = configurable
        kwargs["config"] = cfg

        return kwargs

    def _dispatch_event(self, event):
        """Override to catch MCP tool serialization errors."""
        try:
            return super()._dispatch_event(event)
        except (TypeError, ValueError) as exc:
            logger.warning(
                "Event serialization fallback for %s: %s",
                getattr(event, "type", "unknown"),
                exc,
            )
            if hasattr(event, "raw_event"):
                event.raw_event = None
            if hasattr(event, "event"):
                event.event = str(event.event) if event.event is not None else None
            return event


def build_agent_context(
    *,
    working_dir: Path,
    approval_mode: ApprovalMode = ApprovalMode.SEMI_ACTIVE,
) -> AgentContext:
    """Build AgentContext from server configuration."""
    now = datetime.now(timezone.utc).astimezone()
    return AgentContext(
        approval_mode=approval_mode,
        working_dir=working_dir,
        platform=PLATFORM,
        os_version=OS_VERSION,
        current_date_time_zoned=now.strftime("%Y-%m-%d %H:%M:%S %Z"),
        tool_catalog=initializer.cached_tools_in_catalog,
        skill_catalog=initializer.cached_agent_skills,
    )
