from langrepl.cli.theme import tokyo_night  # noqa: F401
from langrepl.cli.theme.console import ThemedConsole
from langrepl.cli.theme.registry import get_theme
from langrepl.core.settings import settings

theme = get_theme(settings.cli.theme)
console = ThemedConsole(theme)
