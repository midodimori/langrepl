"""AG-UI FastAPI app factory with multi-agent endpoints and discovery."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from ag_ui_langgraph import add_langgraph_fastapi_endpoint
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from langrepl.api.service.agui import LangreplAGUIAgent
from langrepl.cli.bootstrap.initializer import initializer
from langrepl.configs import ApprovalMode
from langrepl.core.logging import get_logger

logger = get_logger(__name__)


def create_app(
    working_dir: str,
    agent: str | None = None,
    model: str | None = None,
    approval_mode: str = ApprovalMode.SEMI_ACTIVE.value,
) -> FastAPI:
    """Create AG-UI FastAPI app with agent endpoints."""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        wd = Path(working_dir)
        mode = ApprovalMode(approval_mode)

        registry = initializer.get_registry(wd)
        await registry.ensure_config_dir()

        agents_config = await registry.load_agents()
        agent_names = [agent] if agent else agents_config.agent_names

        logger.info("Loading agents: %s", agent_names)

        cleanups = []
        agent_list = []

        for name in agent_names:
            model_override = model if agent else None
            graph, cleanup = await initializer.create_graph(name, model_override, wd)
            cleanups.append(cleanup)

            agui_agent = LangreplAGUIAgent(
                name=name,
                graph=graph,
                working_dir=wd,
                approval_mode=mode,
            )

            add_langgraph_fastapi_endpoint(app, agui_agent, f"/agent/{name}")

            agent_cfg = agents_config.get_agent_config(name)
            is_default = agent_cfg.default if agent_cfg else False
            agent_list.append({"name": name, "default": is_default})
            logger.info("Registered agent: %s at /agent/%s", name, name)

        app.state.agent_list = agent_list

        logger.info("AG-UI server ready with %d agent(s)", len(agent_list))

        yield

        logger.info("Shutting down AG-UI server...")
        for cleanup in cleanups:
            await cleanup()
        logger.info("Cleanup complete")

    agui_app = FastAPI(title="Langrepl AG-UI Server", lifespan=lifespan)

    @agui_app.get("/agents")
    async def list_agents():
        """List available agents with default flag."""
        return JSONResponse(content=agui_app.state.agent_list)

    return agui_app
