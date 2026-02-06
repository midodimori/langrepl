import re
import shlex

from langchain.tools import ToolRuntime, tool
from langchain_core.messages import ToolMessage
from langchain_core.tools import ToolException

from langrepl.agents.context import AgentContext
from langrepl.cli.theme import theme
from langrepl.core.logging import get_logger
from langrepl.middlewares.approval import create_field_transformer
from langrepl.utils.bash import execute_bash_command
from langrepl.utils.path import resolve_path

logger = get_logger(__name__)


_CHAIN_OPS = re.compile(r"\s*(&&|\|\||;|\|)\s*")
_SUBST_DOLLAR = re.compile(r"\$\(([^()]*(?:\([^()]*\)[^()]*)*)\)")
_SUBST_BACKTICK = re.compile(r"`([^`]+)`")


def _extract_command_parts(command: str) -> list[str]:
    """Extract all command parts including nested $(...) and `...` substitutions."""
    parts = []
    for seg in _CHAIN_OPS.split(command):
        seg = seg.strip()
        if not seg or seg in ("&&", "||", ";", "|"):
            continue
        parts.append(seg)
        for pattern in (_SUBST_DOLLAR, _SUBST_BACKTICK):
            for m in pattern.finditer(seg):
                parts.extend(_extract_command_parts(m.group(1)))
    return parts


def _first_n_words(cmd: str, n: int = 3) -> str:
    """Extract first n words from a command, handling shell quoting."""
    try:
        words = shlex.split(cmd, posix=True)[:n]
    except ValueError:
        words = cmd.split()[:n]
    return " ".join(words)


def _transform_command_for_approval(command: str) -> str:
    """Transform command to first 3 words of each part for pattern matching."""
    parts = [_first_n_words(p) for p in _extract_command_parts(command) if p]
    return " && ".join(parts) if parts else command


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
    if status != 0:
        error_msg = (
            stderr.strip()
            if stderr.strip()
            else f"Command failed with exit code {status}"
        )
        raise ToolException(error_msg)

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
