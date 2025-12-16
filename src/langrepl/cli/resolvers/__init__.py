"""Reference resolvers for @ syntax."""

from langrepl.cli.resolvers.base import RefType, Resolver
from langrepl.cli.resolvers.file import FileResolver
from langrepl.cli.resolvers.image import ImageResolver

__all__ = ["FileResolver", "ImageResolver", "RefType", "Resolver"]
