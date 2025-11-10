"""Tests for completer router."""

import pytest
from prompt_toolkit.completion import CompleteEvent
from prompt_toolkit.document import Document

from src.cli.completers.router import CompleterRouter


class TestCompleterRouter:
    """Tests for CompleterRouter class."""

    def test_init_creates_router(self, temp_dir):
        """Test that __init__ creates router with completers."""
        commands = ["/help", "/resume"]
        router = CompleterRouter(commands, temp_dir, max_suggestions=5)

        assert router.slash_completer is not None
        assert router.reference_completer is not None

    def test_get_completions_sync_returns_empty(self, temp_dir):
        """Test that sync get_completions returns empty iterator."""
        commands = ["/help"]
        router = CompleterRouter(commands, temp_dir)
        document = Document(text="/h", cursor_position=2)
        event = CompleteEvent()

        completions = list(router.get_completions(document, event))

        assert len(completions) == 0

    @pytest.mark.asyncio
    async def test_get_completions_async_routes_to_slash(self, temp_dir):
        """Test async completions routes to slash completer."""
        commands = ["/help", "/resume"]
        router = CompleterRouter(commands, temp_dir)
        document = Document(text="/h", cursor_position=2)
        event = CompleteEvent()

        completions = []
        async for completion in router.get_completions_async(document, event):
            completions.append(completion)

        assert len(completions) == 1
        assert completions[0].text == "/help"

    @pytest.mark.asyncio
    async def test_get_completions_async_routes_to_reference(self, temp_dir):
        """Test async completions routes to reference completer."""
        test_file = temp_dir / "test.txt"
        test_file.write_text("content")

        commands = ["/help"]
        router = CompleterRouter(commands, temp_dir)
        document = Document(text="@:file:te", cursor_position=9)
        event = CompleteEvent()

        completions = []
        async for completion in router.get_completions_async(document, event):
            completions.append(completion)

        assert len(completions) > 0

    @pytest.mark.asyncio
    async def test_get_completions_async_with_leading_whitespace(self, temp_dir):
        """Test async completions with leading whitespace routes to slash but gets no results."""
        commands = ["/help", "/resume"]
        router = CompleterRouter(commands, temp_dir)
        document = Document(text="  /h", cursor_position=4)
        event = CompleteEvent()

        completions = []
        async for completion in router.get_completions_async(document, event):
            completions.append(completion)

        assert len(completions) == 0

    @pytest.mark.asyncio
    async def test_get_completions_async_non_slash_routes_to_reference(self, temp_dir):
        """Test async completions routes non-slash to reference."""
        commands = ["/help"]
        router = CompleterRouter(commands, temp_dir)
        document = Document(text="regular text", cursor_position=12)
        event = CompleteEvent()

        completions = []
        async for completion in router.get_completions_async(document, event):
            completions.append(completion)

        assert len(completions) == 0

    @pytest.mark.asyncio
    async def test_get_completions_async_empty_text(self, temp_dir):
        """Test async completions with empty text."""
        commands = ["/help"]
        router = CompleterRouter(commands, temp_dir)
        document = Document(text="", cursor_position=0)
        event = CompleteEvent()

        completions = []
        async for completion in router.get_completions_async(document, event):
            completions.append(completion)

        assert len(completions) == 0
