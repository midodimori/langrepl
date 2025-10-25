"""Theme registry for managing and loading themes."""

from collections.abc import Callable

from src.cli.theme.base import BaseTheme

# Global registry mapping theme names to theme classes
_THEME_REGISTRY: dict[str, Callable[[], BaseTheme]] = {}


def register_theme(name: str):
    """Decorator to register a theme class in the registry.

    Usage:
        @register_theme("my-theme")
        class MyTheme:
            ...

    Args:
        name: Theme name (used in configuration)

    Returns:
        Decorator function
    """

    def decorator(theme_class: type[BaseTheme]) -> type[BaseTheme]:
        _THEME_REGISTRY[name] = theme_class
        return theme_class

    return decorator


def get_theme(name: str) -> BaseTheme:
    """Get a theme instance by name.

    Args:
        name: Theme name from configuration

    Returns:
        Theme instance

    Raises:
        ValueError: If theme name is not registered
    """
    if name not in _THEME_REGISTRY:
        available = ", ".join(sorted(_THEME_REGISTRY.keys()))
        raise ValueError(
            f"Theme '{name}' not found. Available themes: {available or 'none'}"
        )

    theme_class = _THEME_REGISTRY[name]
    return theme_class()
