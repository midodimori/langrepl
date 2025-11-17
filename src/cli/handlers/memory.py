"""Memory handling for user preferences and context."""

import subprocess

from src.cli.theme import console
from src.core.constants import CONFIG_MEMORY_FILE_NAME
from src.core.logging import get_logger
from src.core.settings import settings

logger = get_logger(__name__)


class MemoryHandler:
    """Handles user memory operations."""

    def __init__(self, session):
        """Initialize with reference to CLI session."""
        self.session = session

    async def handle(self) -> None:
        """Open memory file in editor."""
        try:
            memory_path = self.session.context.working_dir / CONFIG_MEMORY_FILE_NAME

            # Ensure .langrepl directory exists
            memory_path.parent.mkdir(parents=True, exist_ok=True)

            # Get editor from settings
            editor = settings.cli.editor

            # Open file in editor (editor will create file on save)
            try:
                subprocess.run([editor, str(memory_path)], check=True)
                # Reload graph to apply memory changes
                self.session.needs_reload = True
                self.session.running = False
            except subprocess.CalledProcessError as e:
                console.print_error(f"Editor exited with error: {e}")
                console.print("")
            except FileNotFoundError:
                console.print_error(
                    f"Editor '{editor}' not found. Install it or set CLI__EDITOR in .env"
                )
                console.print("")

        except Exception as e:
            console.print_error(f"Error opening memory file: {e}")
            console.print("")
            logger.debug("Memory handler error", exc_info=True)
