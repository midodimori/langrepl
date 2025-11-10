"""Reference completer for @ references."""

import re
from collections.abc import AsyncGenerator, Iterable
from pathlib import Path

from prompt_toolkit.completion import CompleteEvent, Completer, Completion
from prompt_toolkit.document import Document

from src.cli.resolvers import FileResolver, ImageResolver, RefType


def parse_reference(ref: str) -> tuple[RefType | None, str]:
    """Parse typed reference into type and value.

    Args:
        ref: Reference string (e.g., "@:file:path" or ":file:path" or "path")

    Returns:
        Tuple of (RefType, value) or (None, original) if no type prefix
    """
    content = ref.lstrip("@")

    if content.startswith(":"):
        parts = content[1:].split(":", 1)
        if len(parts) == 2 and parts[1]:
            type_str, value = parts
            try:
                return RefType(type_str), value
            except ValueError:
                pass

    return None, content


class ReferenceCompleter(Completer):
    """Completer for @ references."""

    def __init__(
        self,
        working_dir: Path,
        max_suggestions: int = 10,
    ):
        """Initialize reference completer."""
        self.max_suggestions = max_suggestions
        self.working_dir = working_dir

        self.resolvers = {
            RefType.FILE: FileResolver(),
            RefType.IMAGE: ImageResolver(),
        }

    def get_completions(
        self, document: Document, complete_event: CompleteEvent
    ) -> Iterable[Completion]:
        """Sync stub - completions are async only."""
        return iter([])

    async def get_completions_async(
        self, document: Document, complete_event: CompleteEvent
    ) -> AsyncGenerator[Completion]:
        """Get completions asynchronously."""
        text = document.text_before_cursor

        if at_match := self._find_at_ref(text):
            async for completion in self._complete_ref(at_match.group(1), document):
                yield completion

    @staticmethod
    def _find_at_ref(text: str) -> re.Match[str] | None:
        """Find last @ reference before cursor."""
        pattern = r"@([^\s]*)$"
        return re.search(pattern, text)

    async def _complete_ref(
        self, fragment: str, document: Document
    ) -> AsyncGenerator[Completion]:
        """Get reference completions."""
        text_before = document.text_before_cursor
        at_pos = text_before.rfind("@")
        start_position = at_pos - len(text_before)

        ctx = {"start_position": start_position, "working_dir": str(self.working_dir)}

        completions: list[Completion] = []
        type_filter, ref_fragment = parse_reference(fragment)
        if type_filter and (resolver := self.resolvers.get(type_filter, None)):
            completions = await resolver.complete(
                ref_fragment, ctx, self.max_suggestions
            )
        else:
            for resolver in self.resolvers.values():
                result = await resolver.complete(
                    ref_fragment, ctx, self.max_suggestions - len(completions)
                )
                completions.extend(result)
                if len(completions) >= self.max_suggestions:
                    break

        for completion in completions:
            yield completion
