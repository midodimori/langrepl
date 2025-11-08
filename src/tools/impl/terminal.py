import re
import shlex

from langchain.tools import ToolRuntime, tool
from langchain_core.messages import ToolMessage
from langchain_core.tools import ToolException

from src.agents.context import AgentContext
from src.cli.theme import theme
from src.core.logging import get_logger
from src.middleware.approval import create_field_transformer
from src.utils.bash import execute_bash_command
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


def _render_command_args(args: dict, config: dict) -> str:
    """Render command arguments with syntax highlighting."""
    command = args.get("command", "")
    return f"[{theme.indicator_color}]{command}[/{theme.indicator_color}]"


@tool
async def run_command(
    command: str,
    runtime: ToolRuntime[AgentContext],
) -> str:
    """
    Use this tool to execute terminal commands. Project files should be checked first to understand
    available commands and project structure before running unfamiliar operations.

    Args:
        command: The command to execute
    """
    context: AgentContext = runtime.context
    status, stdout, stderr = await execute_bash_command(
        ["bash", "-c", command], cwd=str(context.working_dir)
    )
    if status not in (0, 1):
        raise ToolException(stderr)

    output_parts = []
    if stdout.strip():
        output_parts.append(stdout.strip())
    if stderr.strip():
        output_parts.append(stderr.strip())

    return "\n".join(output_parts) if output_parts else "Command completed successfully"


run_command.metadata = {
    "approval_config": {
        "format_args_fn": create_field_transformer(
            {"command": _transform_command_for_approval}
        ),
        "render_args_fn": _render_command_args,
    }
}


@tool
async def get_directory_structure(
    dir_path: str,
    runtime: ToolRuntime[AgentContext],
) -> ToolMessage:
    """
    Use this tool to get a tree view of a directory structure showing all files and folders, highly recommended before running file operations.

    Args:
        dir_path: Path to the directory (relative to working directory or absolute)
    """
    context: AgentContext = runtime.context
    working_dir = str(context.working_dir)

    resolved_path = resolve_path(working_dir, dir_path)
    absolute_dir_path = str(resolved_path)

    safe_dir = shlex.quote(absolute_dir_path)
    cmd = [
        "bash",
        "-c",
        f"cd {safe_dir} && rg --files --hidden --ignore --glob '!.git/' | tree --fromfile -a",
    ]
    status, stdout, stderr = await execute_bash_command(cmd, cwd=working_dir)
    if status not in (0, 1):
        raise ToolException(stderr)

    short_content = f"Retrieved directory tree for {absolute_dir_path}"

    return ToolMessage(
        name=get_directory_structure.name,
        content=stdout,
        tool_call_id=runtime.tool_call_id,
        short_content=short_content,
    )


get_directory_structure.metadata = {
    "approval_config": {
        "name_only": True,
        "always_approve": True,
    }
}


TERMINAL_TOOLS = [run_command, get_directory_structure]
