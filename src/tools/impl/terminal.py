import re
from typing import Annotated

from langchain_core.messages import ToolMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import InjectedToolCallId, ToolException

from src.cli.theme import theme
from src.core.logging import get_logger
from src.tools.impl import execute_bash_command
from src.tools.wrapper import approval_tool, create_field_transformer
from src.utils.path import resolve_path

logger = get_logger(__name__)


def _transform_command_for_approval(command: str) -> str:
    """Extract first 2 words from each sub-command while preserving shell operators."""
    parts = re.split(r"(&&|\|\||;|\|)", command)
    result = []
    for i, part in enumerate(parts):
        part = part.strip()
        if not part:
            continue
        if part in ("&&", "||", ";", "|"):
            result.append(f" {part} ")
        else:
            words = part.split()
            result.append(" ".join(words[:2]) if len(words) >= 2 else words[0])
    return "".join(result).strip()


def _render_command_args(args: dict, config: RunnableConfig) -> str:
    """Render command arguments with syntax highlighting."""
    command = args.get("command", "")
    return f"[{theme.tool_color}]{command}[/{theme.tool_color}]"


@approval_tool(
    format_args_fn=create_field_transformer(
        {"command": _transform_command_for_approval}
    ),
    render_args_fn=_render_command_args,
)
async def run_command(
    config: RunnableConfig,
    tool_call_id: Annotated[str, InjectedToolCallId],
    command: str,
) -> str:
    """
    Use this tool to execute terminal commands. Project files should be checked first to understand
    available commands and project structure before running unfamiliar operations.

    Args:
        command (str): The command to execute
    """
    working_dir = config.get("configurable", {}).get("working_dir")
    status, stdout, stderr = await execute_bash_command(
        ["bash", "-c", command], cwd=working_dir
    )
    if status not in (0, 1):
        raise ToolException(stderr)

    # Combine stdout and stderr, as many commands write useful output to stderr
    output_parts = []
    if stdout.strip():
        output_parts.append(stdout.strip())
    if stderr.strip():
        output_parts.append(stderr.strip())

    return "\n".join(output_parts) if output_parts else "Command completed successfully"


@approval_tool(name_only=True, always_approve=True)
async def get_directory_structure(
    config: RunnableConfig,
    tool_call_id: Annotated[str, InjectedToolCallId],
    dir_path: str,
) -> ToolMessage:
    """
    Use this tool to get a tree view of a directory structure showing all files and folders, highly recommended before running file operations.

    Args:
        dir_path (str): Path to the directory (relative to working directory or absolute)
    """
    working_dir = config.get("configurable", {}).get("working_dir")
    if not working_dir:
        raise ToolException("Working directory is not configured.")

    resolved_path = resolve_path(working_dir, dir_path)
    absolute_dir_path = str(resolved_path)

    cmd = [
        "bash",
        "-c",
        f"cd {absolute_dir_path} && rg --files --hidden --ignore --glob '!.git/' | tree --fromfile -a",
    ]
    status, stdout, stderr = await execute_bash_command(cmd, cwd=working_dir)
    if status not in (0, 1):
        raise ToolException(stderr)

    short_content = f"Retrieved directory tree for {absolute_dir_path}"

    return ToolMessage(
        name=get_directory_structure.name,
        content=stdout,
        tool_call_id=tool_call_id,
        short_content=short_content,
    )


# Export all tools for the factory
TERMINAL_TOOLS = [run_command, get_directory_structure]
