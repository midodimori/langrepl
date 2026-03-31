"""AG-UI agent service — LangreplAGUIAgent subclass and context builder."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from ag_ui_langgraph import LangGraphAgent
from langchain_core.runnables import RunnableConfig
from langgraph.graph.state import CompiledStateGraph
from langgraph.runtime import Runtime

from langrepl.agents.context import AgentContext
from langrepl.cli.bootstrap.initializer import initializer
from langrepl.configs import ApprovalMode
from langrepl.core.constants import OS_VERSION, PLATFORM

logger = logging.getLogger(__name__)


class LangreplAGUIAgent(LangGraphAgent):
    """AG-UI agent with AgentContext injection and MCP serialization safety."""

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
            logger.debug("Event serialization fallback: %s", exc)
            # Clear problematic raw_event data and retry
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
