"""AG-UI agent service — LangreplAGUIAgent subclass and context builder."""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from ag_ui.core import CustomEvent, EventType
from ag_ui_langgraph import LangGraphAgent
from ag_ui_langgraph.types import LangGraphEventTypes
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
        """Override to fix ag-ui-langgraph bug: only tasks[0] checked for interrupts.

        Buffers RUN_FINISHED, checks all tasks for missed interrupts,
        emits them BEFORE RUN_FINISHED so CopilotKit receives them.
        """
        saw_interrupt = False
        buffered_run_finished = None

        async for event in super().run(input):
            # Track if parent already emitted an interrupt
            if hasattr(event, "type") and event.type == EventType.CUSTOM:
                if (
                    hasattr(event, "name")
                    and event.name == LangGraphEventTypes.OnInterrupt.value
                ):
                    saw_interrupt = True

            # Buffer RUN_FINISHED — we may need to inject interrupt events before it
            if hasattr(event, "type") and event.type == EventType.RUN_FINISHED:
                buffered_run_finished = event
                continue

            yield event

        # Check all tasks for missed interrupts before emitting RUN_FINISHED
        if not saw_interrupt and buffered_run_finished:
            thread_id = input.thread_id
            config = {"configurable": {"thread_id": thread_id}}
            try:
                state = await self.graph.aget_state(config)
                if state.tasks:
                    for task in state.tasks:
                        for intr in task.interrupts:
                            value = intr.value
                            if hasattr(value, "model_dump"):
                                value = value.model_dump()
                            logger.info("Emitting missed interrupt: %s", value)
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
