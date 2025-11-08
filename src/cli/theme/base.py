"""Base theme classes and protocols for the CLI theme system."""

from typing import Protocol

from rich.theme import Theme


class BaseTheme(Protocol):
    """Protocol defining the interface for all themes.

    Themes must provide:
    - rich_theme: Rich Theme instance with semantic styles
    - Semantic color accessors for direct use in formatting

    The semantic colors should match common UI needs like success, error,
    prompts, etc. Each theme can define these with their own color palette.
    """

    # Rich theme for console styling
    rich_theme: Theme

    # Semantic colors for direct formatting
    # Text colors
    @property
    def primary_text(self) -> str:
        """Primary text color."""
        ...

    @property
    def secondary_text(self) -> str:
        """Secondary/muted text color."""
        ...

    @property
    def muted_text(self) -> str:
        """Muted/dim text color."""
        ...

    # Background colors
    @property
    def background(self) -> str:
        """Primary background color."""
        ...

    @property
    def background_light(self) -> str:
        """Lighter background color."""
        ...

    # Semantic colors
    @property
    def success_color(self) -> str:
        """Success/positive action color."""
        ...

    @property
    def error_color(self) -> str:
        """Error/negative action color."""
        ...

    @property
    def warning_color(self) -> str:
        """Warning/caution color."""
        ...

    @property
    def info_color(self) -> str:
        """Info/neutral message color."""
        ...

    # UI element colors
    @property
    def prompt_color(self) -> str:
        """Prompt symbol color."""
        ...

    @property
    def accent_color(self) -> str:
        """Accent/highlight color."""
        ...

    @property
    def indicator_color(self) -> str:
        """Tool-related elements color."""
        ...

    @property
    def command_color(self) -> str:
        """Command-related elements color."""
        ...

    # Code/diff colors
    @property
    def addition_color(self) -> str:
        """Color for additions in diffs."""
        ...

    @property
    def deletion_color(self) -> str:
        """Color for deletions in diffs."""
        ...

    @property
    def context_color(self) -> str:
        """Color for context lines in diffs."""
        ...

    # Approval mode colors
    @property
    def approval_semi_active(self) -> str:
        """Color for semi-active approval mode."""
        ...

    @property
    def approval_active(self) -> str:
        """Color for active approval mode."""
        ...

    @property
    def approval_aggressive(self) -> str:
        """Color for aggressive approval mode."""
        ...

    # Interactive UI colors
    @property
    def selection_color(self) -> str:
        """Color for selected items in menus/lists."""
        ...

    @property
    def spinner_color(self) -> str:
        """Color for loading spinners and progress indicators."""
        ...
