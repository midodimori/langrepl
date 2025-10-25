from src.cli.theme import tokyo_night  # noqa: F401
from src.cli.theme.console import ThemedConsole
from src.cli.theme.registry import get_theme
from src.core.settings import settings

theme = get_theme(settings.cli.theme)
console = ThemedConsole(theme)
