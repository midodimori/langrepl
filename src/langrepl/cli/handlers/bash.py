"""Bash command execution dispatcher."""

from langrepl.cli.theme import console, theme
from langrepl.core.logging import get_logger
from langrepl.utils.bash import execute_bash_command

logger = get_logger(__name__)


class BashDispatcher:
    """Handles bash command execution."""

    def __init__(self, session) -> None:
        """Initialize with reference to CLI session."""
        self.session = session

    async def dispatch(self, command: str) -> None:
        """Execute bash command and display output."""
        try:
            if not command.strip():
                return

            working_dir = str(self.session.context.working_dir)

            with console.console.status(
                f"[{theme.spinner_color}]Running...[/{theme.spinner_color}]"
            ) as status:
                returncode, stdout, stderr = await execute_bash_command(
                    ["bash", "-c", command], cwd=working_dir
                )
                status.stop()

            if stdout:
                console.console.print(stdout.rstrip())

            if stderr:
                console.print_error(stderr.rstrip())

            if returncode != 0:
                console.print_error(f"Command exited with code {returncode}")

            console.print("")

        except ValueError as e:
            console.print_error(f"Invalid command syntax: {e}")
            console.print("")
        except Exception as e:
            console.print_error(f"Error executing command: {e}")
            console.print("")
            logger.debug("Bash handler error", exc_info=True)
