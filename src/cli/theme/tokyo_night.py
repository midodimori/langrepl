"""Tokyo Night theme colors and palette for the terminal CLI."""

from dataclasses import dataclass

from rich.style import Style
from rich.theme import Theme

from src.cli.theme.base import BaseTheme
from src.cli.theme.registry import register_theme


@dataclass
class TokyoNightColors:
    """Tokyo Night color scheme definition."""

    # Dark colors
    deep_blue: str = "#1a1b26"
    dark_blue: str = "#24283b"
    navy: str = "#1f2335"
    slate: str = "#292e42"

    # Light colors
    light_blue_white: str = "#c0caf5"
    muted_blue: str = "#9aa5ce"
    blue_gray: str = "#565f89"
    dark_gray: str = "#414868"

    # Bright colors
    bright_blue: str = "#7aa2f7"
    cyan: str = "#7dcfff"
    purple: str = "#bb9af7"
    teal: str = "#8be4e1"
    yellow: str = "#e4e38b"
    pink: str = "#e48be4"
    orange: str = "#ff9e64"
    sky_blue: str = "#89ddff"
    steel_blue: str = "#364a82"


@register_theme("tokyo-night")
class TokyoNightTheme(BaseTheme):
    """Tokyo Night theme implementation."""

    def __init__(self):
        self.colors = TokyoNightColors()
        self.rich_theme = self._create_rich_theme()

    def _create_rich_theme(self) -> Theme:
        """Create Rich Theme with Tokyo Night colors."""
        c = self.colors
        return Theme(
            {
                # Basic text styles
                "default": Style(color=c.light_blue_white),
                "primary": Style(color=c.light_blue_white),
                "secondary": Style(color=c.muted_blue),
                "muted": Style(color=c.blue_gray),
                "disabled": Style(color=c.dark_gray),
                # Accent styles
                "accent": Style(color=c.bright_blue, bold=True),
                "accent.primary": Style(color=c.bright_blue),
                "accent.secondary": Style(color=c.cyan),
                "accent.tertiary": Style(color=c.purple),
                # Semantic styles
                "success": Style(color=c.teal),
                "warning": Style(color=c.yellow),
                "error": Style(color=c.pink),
                "info": Style(color=c.bright_blue),
                # UI element styles
                "border": Style(color=c.dark_gray),
                "prompt": Style(color=c.bright_blue, bold=True),
                "command": Style(color=c.purple),
                "option": Style(color=c.cyan),
                "indicator": Style(color=c.teal),
                # Code syntax highlighting
                "code": Style(color=c.teal, bold=False),
                "code.keyword": Style(color=c.purple, bold=True),
                "code.string": Style(color=c.teal),
                "code.number": Style(color=c.orange),
                "code.comment": Style(color=c.blue_gray, italic=True),
                "code.operator": Style(color=c.sky_blue),
                # Markdown specific styles
                "markdown.code": Style(color=c.purple, bold=True),
                # Special elements
                "timestamp": Style(color=c.blue_gray, italic=True),
            }
        )

    # Semantic color accessors for BaseTheme protocol
    @property
    def primary_text(self) -> str:
        return self.colors.light_blue_white

    @property
    def secondary_text(self) -> str:
        return self.colors.muted_blue

    @property
    def muted_text(self) -> str:
        return self.colors.blue_gray

    @property
    def background(self) -> str:
        return self.colors.deep_blue

    @property
    def background_light(self) -> str:
        return self.colors.dark_blue

    @property
    def success_color(self) -> str:
        return self.colors.teal

    @property
    def error_color(self) -> str:
        return self.colors.pink

    @property
    def warning_color(self) -> str:
        return self.colors.yellow

    @property
    def info_color(self) -> str:
        return self.colors.bright_blue

    @property
    def prompt_color(self) -> str:
        return self.colors.bright_blue

    @property
    def accent_color(self) -> str:
        return self.colors.cyan

    @property
    def indicator_color(self) -> str:
        return self.colors.teal

    @property
    def command_color(self) -> str:
        return self.colors.purple

    @property
    def addition_color(self) -> str:
        return self.colors.teal

    @property
    def deletion_color(self) -> str:
        return self.colors.pink

    @property
    def context_color(self) -> str:
        return self.colors.muted_blue

    @property
    def approval_semi_active(self) -> str:
        return self.colors.bright_blue

    @property
    def approval_active(self) -> str:
        return self.colors.yellow

    @property
    def approval_aggressive(self) -> str:
        return self.colors.purple

    @property
    def selection_color(self) -> str:
        return self.colors.teal

    @property
    def spinner_color(self) -> str:
        return self.colors.teal
