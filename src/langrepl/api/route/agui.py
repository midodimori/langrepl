"""AG-UI FastAPI app factory with multi-agent endpoints and discovery."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from ag_ui_langgraph import add_langgraph_fastapi_endpoint
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
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
        app.state.working_dir = wd

        logger.info("AG-UI server ready with %d agent(s)", len(agent_list))

        yield

        logger.info("Shutting down AG-UI server...")
        for cleanup in cleanups:
            await cleanup()
        logger.info("Cleanup complete")

    agui_app = FastAPI(title="Langrepl AG-UI Server", lifespan=lifespan)
    agui_app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @agui_app.get("/agents")
    async def list_agents():
        """List available agents with default flag."""
        return JSONResponse(content=agui_app.state.agent_list)

    @agui_app.get("/threads/{thread_id}/messages")
    async def get_thread_messages(thread_id: str, agent: str | None = None):
        """Get messages for a specific thread."""
        from langchain_core.runnables import RunnableConfig

        wd = agui_app.state.working_dir
        agents_to_try = (
            [agent] if agent else [a["name"] for a in agui_app.state.agent_list]
        )

        for agent_name in agents_to_try:
            try:
                async with initializer.get_checkpointer(agent_name, wd) as checkpointer:
                    checkpoint = await checkpointer.aget_tuple(
                        config=RunnableConfig(configurable={"thread_id": thread_id})
                    )
                    if not checkpoint or not checkpoint.checkpoint:
                        continue
                    messages = checkpoint.checkpoint.get("channel_values", {}).get(
                        "messages", []
                    )
                    if not messages:
                        continue
                    result = []
                    for msg in messages:
                        role = getattr(msg, "type", "unknown")
                        if role == "human":
                            role = "user"
                        elif role == "ai":
                            role = "assistant"
                        elif role == "tool":
                            continue
                        content = getattr(msg, "content", "")
                        if isinstance(content, list):
                            content = " ".join(
                                (
                                    item.get("text", "")
                                    if isinstance(item, dict)
                                    else str(item)
                                )
                                for item in content
                            )
                        msg_id = getattr(msg, "id", None) or ""
                        result.append(
                            {"id": msg_id, "role": role, "content": str(content)}
                        )
                    return JSONResponse(content=result)
            except Exception:
                continue
        return JSONResponse(content=[])

    @agui_app.get("/threads")
    async def list_threads(agent: str | None = None):
        """List saved conversation threads."""
        wd = agui_app.state.working_dir
        agents_to_query = (
            [agent] if agent else [a["name"] for a in agui_app.state.agent_list]
        )
        all_threads = []
        for agent_name in agents_to_query:
            threads = await initializer.get_threads(agent_name, wd)
            for t in threads:
                t["agent"] = agent_name
            all_threads.extend(threads)
        all_threads.sort(key=lambda t: t.get("timestamp", ""), reverse=True)
        return JSONResponse(content=all_threads)

    return agui_app
