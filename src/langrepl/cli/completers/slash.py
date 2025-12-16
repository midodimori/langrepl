"""Slash command completer."""

from collections.abc import AsyncGenerator, Iterable

from prompt_toolkit.completion import CompleteEvent, Completion, WordCompleter
from prompt_toolkit.document import Document


class SlashCommandCompleter(WordCompleter):
    """Auto-completer for slash commands."""

    def __init__(self, commands: list[str]):
        super().__init__(commands, ignore_case=True, sentence=True)

    def get_completions(
        self, document: Document, complete_event: CompleteEvent
    ) -> Iterable[Completion]:
        """Get completions for slash commands (sync)."""
        yield from super().get_completions(document, complete_event)

    async def get_completions_async(
        self, document: Document, complete_event: CompleteEvent
    ) -> AsyncGenerator[Completion]:
        """Get completions for slash commands (async)."""
        for completion in self.get_completions(document, complete_event):
            yield completion
