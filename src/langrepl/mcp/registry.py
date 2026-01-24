"""MCP tool registry for filtering and module mapping."""

from __future__ import annotations

from langrepl.core.logging import get_logger

logger = get_logger(__name__)


class MCPRegistry:
    """Filters tools and builds module mapping for pattern matching."""

    def __init__(self, filters: dict[str, dict] | None = None) -> None:
        self._filters = filters or {}
        self._registered: set[tuple[str, str]] = set()
        self._map: dict[str, str] = {}

    def allowed(self, name: str, server: str) -> bool:
        """Check if tool passes include/exclude filters."""
        f = self._filters.get(server)
        if not f:
            return True

        include = f.get("include", [])
        exclude = f.get("exclude", [])

        if include and exclude:
            raise ValueError(f"Both include/exclude set for {server}")
        if include:
            return name in include
        if exclude:
            return name not in exclude
        return True

    def register(self, name: str, server: str) -> bool:
        """Register tool. Returns True if newly registered, False if already exists."""
        key = (server, name)
        if key in self._registered:
            return False
        self._registered.add(key)
        self._map[f"{server}__{name}"] = server
        return True

    @property
    def module_map(self) -> dict[str, str]:
        return self._map
