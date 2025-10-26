"""LangGraph Server CLI integration."""

import asyncio
import json
import os
import subprocess
from pathlib import Path

import httpx
from langgraph.graph.state import CompiledStateGraph

from src.cli.initializer import initializer
from src.cli.theme import console
from src.core.constants import CONFIG_LANGGRAPH_FILE_NAME
from src.core.settings import settings

LANGREPL_ROOT = Path(__file__).parent.parent.parent.parent.resolve()


async def get_graph() -> CompiledStateGraph:
    """Get compiled graph for LangGraph Server.

    This function is referenced in langgraph.json and called by the LangGraph CLI.
    It reads agent and model from environment variables set by the CLI wrapper.

    Note: langgraph dev uses in-memory checkpointing by design. Your configured
    checkpointer is ignored. Threads are ephemeral and shared across all dev
    server instances. Use regular CLI mode (lg) for persistent threads.

    Environment Variables:
        LANGREPL_AGENT: Agent name (required)
        LANGREPL_MODEL: Model name (optional)
        LANGREPL_WORKING_DIR: Working directory path (required)

    Returns:
        CompiledStateGraph: The compiled graph ready for server execution
    """
    agent = os.getenv("LANGREPL_AGENT")
    model = os.getenv("LANGREPL_MODEL")
    working_dir_str = os.getenv("LANGREPL_WORKING_DIR")

    if not working_dir_str:
        raise ValueError("LANGREPL_WORKING_DIR environment variable is required")

    working_dir = Path(working_dir_str)

    async with initializer.get_graph(agent, model, working_dir) as graph:
        return graph


def generate_langgraph_json(working_dir: Path) -> None:
    """Generate langgraph.json configuration file.

    Args:
        working_dir: Working directory where config will be created
    """

    config = {
        "dependencies": [str(LANGREPL_ROOT)],
        "graphs": {"agent": "src/cli/core/server.py:get_graph"},
    }

    # Add env reference if .env file exists
    env_file = working_dir / ".env"
    if env_file.exists():
        config["env"] = ".env"

    # Write to .langrepl/langgraph.json
    langgraph_json_path = working_dir / CONFIG_LANGGRAPH_FILE_NAME
    langgraph_json_path.parent.mkdir(parents=True, exist_ok=True)

    with open(langgraph_json_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)


async def _wait_for_server_ready(
    client: httpx.AsyncClient, server_url: str, timeout_seconds: int = 30
) -> bool:
    """Wait for LangGraph server to be ready.

    Args:
        client: HTTP client
        server_url: The server URL
        timeout_seconds: Maximum time to wait in seconds

    Returns:
        True if server is ready, False otherwise
    """
    for _ in range(timeout_seconds * 2):
        try:
            if (await client.get(f"{server_url}/ok")).status_code == 200:
                return True
        except httpx.HTTPError:
            pass
        await asyncio.sleep(0.5)
    return False


async def _set_assistant_version(
    client: httpx.AsyncClient, server_url: str, assistant: dict
) -> None:
    """Set assistant version as latest.

    Args:
        client: HTTP client
        server_url: The server URL
        assistant: Assistant data with assistant_id and version
    """
    await client.post(
        f"{server_url}/assistants/{assistant['assistant_id']}/latest",
        json={"version": assistant["version"]},
        timeout=10.0,
    )


async def _upsert_assistant(
    client: httpx.AsyncClient, server_url: str, name: str, config: dict
) -> tuple[dict | None, bool]:
    """Create or update assistant.

    Args:
        client: HTTP client
        server_url: The server URL
        name: Assistant name
        config: Assistant configuration

    Returns:
        Tuple of (assistant data, was_updated)
    """
    assistant_id = None
    try:
        # Search for existing assistant
        search_response = await client.post(
            f"{server_url}/assistants/search",
            json={"query": {"name": name}},
            timeout=10.0,
        )

        if search_response.status_code == 200:
            results = search_response.json()
            if results:
                assistant_id = results[0]["assistant_id"]

        # Update or create
        if assistant_id:
            response = await client.patch(
                f"{server_url}/assistants/{assistant_id}",
                json=config,
                timeout=10.0,
            )
            was_updated = True
        else:
            response = await client.post(
                f"{server_url}/assistants", json=config, timeout=10.0
            )
            was_updated = False

        if response.status_code == 200:
            assistant = response.json()
            await _set_assistant_version(client, server_url, assistant)
            return assistant, was_updated

    except httpx.HTTPError as e:
        action = "update" if assistant_id else "create"
        console.print_error(f"Failed to {action} assistant: {e}")

    return None, False


async def handle_server_command(args) -> int:
    """Handle server mode command.

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0 for success, 1 for error)
    """
    try:
        working_dir = Path(args.working_dir)

        # Load agent config to get LLM costs
        agent_config = await initializer.load_agent_config(args.agent, working_dir)
        llm_config = (
            agent_config.llm
            if not args.model
            else await initializer.load_llm_config(args.model, working_dir)
        )

        # Generate langgraph.json
        generate_langgraph_json(working_dir)

        # Prepare environment variables
        env = os.environ.copy()
        env["LANGREPL_WORKING_DIR"] = str(working_dir)
        if args.agent:
            env["LANGREPL_AGENT"] = args.agent
        if args.model:
            env["LANGREPL_MODEL"] = args.model

        # Ensure langgraph_api is ignored in git (local-only, not committed)
        git_info_exclude = Path(working_dir) / ".git" / "info" / "exclude"
        if git_info_exclude.parent.exists():
            try:
                existing_content = ""
                if git_info_exclude.exists():
                    existing_content = git_info_exclude.read_text()

                ignore_pattern = f".langgraph_api/"
                if ignore_pattern not in existing_content:
                    with git_info_exclude.open("a") as f:
                        f.write(
                            f"\n# Langgraph Server configuration\n{ignore_pattern}\n"
                        )
            except Exception:
                pass

        # Start server in background
        console.print("Starting LangGraph development server...")
        config_path = working_dir / CONFIG_LANGGRAPH_FILE_NAME

        process = subprocess.Popen(
            ["uv", "run", "langgraph", "dev", "--config", str(config_path)],
            cwd=LANGREPL_ROOT,
            env=env,
        )

        server_url = settings.server.langgraph_server_url

        async with httpx.AsyncClient() as client:
            # Wait for server to be ready
            if not await _wait_for_server_ready(client, server_url):
                console.print_error("Server failed to start within timeout")
                process.kill()
                return 1

            console.print(f"Server is ready at {server_url}")

            # Create or update assistant
            assistant_name = f"{args.agent or agent_config.name} Assistant"
            assistant_config = {
                "graph_id": "agent",
                "config": {
                    "configurable": {
                        "approval_mode": args.approval_mode,
                        "working_dir": str(working_dir),
                        "input_cost_per_mtok": (
                            llm_config.input_cost_per_mtok if llm_config else None
                        ),
                        "output_cost_per_mtok": (
                            llm_config.output_cost_per_mtok if llm_config else None
                        ),
                    }
                },
                "name": assistant_name,
            }

            assistant, was_updated = await _upsert_assistant(
                client, server_url, assistant_name, assistant_config
            )

            if assistant:
                action = "Updated" if was_updated else "Created"
                console.print(
                    f"{action} assistant: {assistant['name']} "
                    f"(ID: {assistant['assistant_id']}, Version: {assistant['version']})"
                )

        # Wait for process to complete
        return process.wait()

    except Exception as e:
        console.print_error(f"Error starting server: {e}")
        return 1
