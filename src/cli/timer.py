"""Performance timer for CLI startup phases."""

import time

from src.cli.theme import console


class _Timer:
    """Context manager for timing code blocks."""

    def __init__(self, phase_name: str, enabled: bool):
        self.phase_name = phase_name
        self.enabled = enabled

    def __enter__(self):
        if self.enabled:
            self._start = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.enabled:
            elapsed = time.perf_counter() - self._start
            console.console.print(
                f"[dim]⏱  {self.phase_name}:[/dim] [cyan]{elapsed:.3f}s[/cyan]"
            )


_enabled = False


def enable_timer():
    """Enable the startup performance timer."""
    global _enabled
    _enabled = True


def timer(phase_name: str):
    """Time a code block. Only prints if timer is enabled."""
    return _Timer(phase_name, _enabled)
