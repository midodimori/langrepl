"""Base classes for versioned configurations."""

from pydantic import BaseModel


class VersionedConfig(BaseModel):
    """Base class for versioned configs with migration support."""

    @classmethod
    def get_latest_version(cls) -> str:
        """Return latest version for this config type. Must be overridden by subclasses."""
        raise NotImplementedError(f"{cls.__name__} must implement get_latest_version()")

    @classmethod
    def migrate(cls, data: dict, from_version: str) -> dict:
        """Migrate config data from older version."""
        return data
