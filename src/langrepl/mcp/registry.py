"""MCP tool registry with filtering and deduplication."""

from __future__ import annotations

from langrepl.core.logging import get_logger

logger = get_logger(__name__)


class MCPRegistry:
    """Filters tools and prevents cross-server duplicates."""

    def __init__(self, filters: dict[str, dict] | None = None) -> None:
        self._filters = filters or {}
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
        """Register tool name. Returns False if duplicate from another server."""
        existing = self._map.get(name)
        if existing and existing != server:
            logger.warning(
                "Skipping %s from %s; already from %s",
                name,
                server,
                existing,
            )
            return False

        self._map.setdefault(name, server)
        return True

    @property
    def module_map(self) -> dict[str, str]:
        return self._map
