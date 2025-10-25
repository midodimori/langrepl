"""Rich styles and formatting utilities with theme support."""

from rich.console import Console

from src.cli.theme.base import BaseTheme


class ThemedConsole:
    """Console wrapper with configurable theme."""

    def __init__(self, console_theme: BaseTheme):
        self.console = Console(
            theme=console_theme.rich_theme,
            force_terminal=True,
            color_system="truecolor",
        )

    def print(self, *args, style: str = "default", **kwargs):
        """Print with theme-aware styling."""
        self.console.print(*args, style=style, **kwargs)

    def print_error(self, content: str):
        """Print error message."""
        self.console.print(f"[error]✗[/error] {content}")

    def print_success(self, content: str):
        """Print success message."""
        self.console.print(f"[success]✓[/success] {content}")

    def clear(self):
        """Clear the console."""
        self.console.clear()

    def capture(self):
        """Capture console output for measuring rendered lines."""
        return self.console.capture()

    @property
    def width(self):
        """Get console width."""
        return self.console.width
