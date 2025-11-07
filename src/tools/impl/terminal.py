import re

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
    """
    Transform a shell command for approval display by keeping only the first two words of each sub-command and preserving shell operators.
    
    Returns:
        str: Transformed command string suitable for use in an approval UI; shell operators (&&, ||, ;, |) are preserved and spaced.
    """
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
    """
    Format the tool's `command` argument with theme color markup for display.
    
    Parameters:
        args (dict): Mapping of tool arguments; expects a `"command"` key whose value is the command string to render.
        config (dict): Rendering configuration (unused by this implementation but accepted for compatibility).
    
    Returns:
        str: The command string wrapped with theme tool color markup (e.g., "[<color>]<command>[/<color>]").
    """
    command = args.get("command", "")
    return f"[{theme.tool_color}]{command}[/{theme.tool_color}]"


@tool
async def run_command(
    command: str,
    runtime: ToolRuntime[AgentContext],
) -> str:
    """
    Execute a shell command using bash in the agent's working directory.
    
    Parameters:
        command (str): The shell command to run.
        runtime (ToolRuntime[AgentContext]): Runtime whose context.working_dir is used as the command's working directory.
    
    Returns:
        str: The combined stdout and stderr output if any, joined by a newline; otherwise the string "Command completed successfully".
    
    Raises:
        ToolException: If the process exits with a status other than 0 or 1, containing stderr.
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
    Retrieve a tree view of a directory's structure including hidden files (excluding the .git directory).
    
    Parameters:
        dir_path (str): Path to the directory to inspect; resolved against the tool runtime's working directory if relative.
    
    Returns:
        ToolMessage: Message whose `content` is the directory tree output, `name` is the tool name, `tool_call_id` is taken from the runtime, and `short_content` is a brief summary.
    
    Raises:
        ToolException: If the underlying shell command exits with a status other than 0 or 1; the exception message contains stderr.
    """
    context: AgentContext = runtime.context
    working_dir = str(context.working_dir)

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