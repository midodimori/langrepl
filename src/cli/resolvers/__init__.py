"""Reference resolvers for @ syntax."""

from src.cli.resolvers.base import RefType, Resolver
from src.cli.resolvers.file import FileResolver
from src.cli.resolvers.image import ImageResolver

__all__ = ["FileResolver", "ImageResolver", "RefType", "Resolver"]
