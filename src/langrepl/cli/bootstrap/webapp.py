"""FastAPI app with custom lifespan for LangGraph server resource management."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import FastAPI

from langrepl.cli.bootstrap.initializer import initializer
from langrepl.core.logging import get_logger

if TYPE_CHECKING:
    pass


logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage graph lifecycle: initialize on startup, cleanup on shutdown.

    This lifespan handler ensures MCP sessions and checkpointer connections
    stay alive for the entire server duration, preventing premature cleanup.
    """
    # Read environment variables set by server handler
    agent = os.getenv("LANGREPL_AGENT")
    model = os.getenv("LANGREPL_MODEL")
    working_dir_str = os.getenv("LANGREPL_WORKING_DIR")

    if not working_dir_str:
        raise ValueError("LANGREPL_WORKING_DIR environment variable is required")

    working_dir = Path(working_dir_str)

    logger.info(f"Initializing graph for agent={agent}, model={model}")

    # Use create_graph (NOT get_graph) to avoid auto-cleanup
    graph, cleanup = await initializer.create_graph(agent, model, working_dir)

    # Store in app.state for access by get_graph()
    app.state.graph = graph
    app.state.cleanup = cleanup

    logger.info("Graph initialized, MCP sessions active")

    yield  # Server runs here

    # Shutdown: cleanup resources
    logger.info("Shutting down, cleaning up resources...")
    await cleanup()
    logger.info("Cleanup complete")


# FastAPI app with custom lifespan
app = FastAPI(lifespan=lifespan)
