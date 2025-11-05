"""Reference resolvers for @ syntax."""

from src.cli.resolvers.base import RefType, Resolver
from src.cli.resolvers.file import FileResolver

__all__ = ["FileResolver", "RefType", "Resolver"]
