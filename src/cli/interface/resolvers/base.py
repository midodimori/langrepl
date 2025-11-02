"""Base classes for reference resolvers."""

from abc import ABC, abstractmethod
from enum import Enum

from prompt_toolkit.completion import Completion


class RefType(str, Enum):
    """Reference types."""

    FILE = "file"


class Resolver(ABC):
    """Abstract base for reference resolvers."""

    type: RefType

    @abstractmethod
    def resolve(self, ref: str, ctx: dict) -> str:
        """Resolve reference to final value."""

    @abstractmethod
    async def complete(self, fragment: str, ctx: dict, limit: int) -> list[Completion]:
        """Get completions for fragment."""
