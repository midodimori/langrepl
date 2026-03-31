"""AG-UI FastAPI app with lifespan and endpoint wiring."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

from ag_ui_langgraph import add_langgraph_fastapi_endpoint
from fastapi import FastAPI

from langrepl.api.service.agui import LangreplAGUIAgent
from langrepl.cli.bootstrap.initializer import initializer
from langrepl.configs import ApprovalMode
from langrepl.core.logging import get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize graph on startup, cleanup on shutdown."""
    agent_name = os.getenv("LANGREPL_AGENT")
    model = os.getenv("LANGREPL_MODEL")
    working_dir_str = os.getenv("LANGREPL_WORKING_DIR")
    approval_mode_str = os.getenv(
        "LANGREPL_APPROVAL_MODE", ApprovalMode.SEMI_ACTIVE.value
    )

    if not working_dir_str:
        raise ValueError("LANGREPL_WORKING_DIR environment variable is required")

    working_dir = Path(working_dir_str)
    approval_mode = ApprovalMode(approval_mode_str)

    logger.info("Initializing AG-UI server for agent=%s, model=%s", agent_name, model)

    graph, cleanup = await initializer.create_graph(agent_name, model, working_dir)

    agui_agent = LangreplAGUIAgent(
        name=agent_name or "default",
        graph=graph,
        working_dir=working_dir,
        approval_mode=approval_mode,
    )

    add_langgraph_fastapi_endpoint(app, agui_agent, "/agent")

    app.state.cleanup = cleanup

    logger.info("AG-UI server ready")

    yield

    logger.info("Shutting down AG-UI server...")
    await cleanup()
    logger.info("Cleanup complete")


app = FastAPI(title="Langrepl AG-UI Server", lifespan=lifespan)
