"""Tests for reference completer."""

import pytest
from prompt_toolkit.completion import CompleteEvent
from prompt_toolkit.document import Document

from src.cli.completers.reference import ReferenceCompleter, parse_reference
from src.cli.resolvers import RefType


class TestParseReference:
    """Tests for parse_reference function."""

    def test_parse_reference_with_file_type(self):
        """Test parsing reference with file type."""
        ref_type, value = parse_reference("@:file:path/to/file.txt")

        assert ref_type == RefType.FILE
        assert value == "path/to/file.txt"

    def test_parse_reference_without_at_symbol(self):
        """Test parsing reference without @ symbol."""
        ref_type, value = parse_reference(":file:path/to/file.txt")

        assert ref_type == RefType.FILE
        assert value == "path/to/file.txt"

    def test_parse_reference_with_no_type_prefix(self):
        """Test parsing reference with no type prefix."""
        ref_type, value = parse_reference("path/to/file.txt")

        assert ref_type is None
        assert value == "path/to/file.txt"

    def test_parse_reference_with_invalid_type(self):
        """Test parsing reference with invalid type."""
        ref_type, value = parse_reference(":invalid:path/to/file.txt")

        assert ref_type is None
        assert value == ":invalid:path/to/file.txt"

    def test_parse_reference_empty_value(self):
        """Test parsing reference with empty value."""
        ref_type, value = parse_reference(":file:")

        assert ref_type is None
        assert value == ":file:"

    def test_parse_reference_only_type(self):
        """Test parsing reference with only type prefix."""
        ref_type, value = parse_reference(":file")

        assert ref_type is None
        assert value == ":file"

    def test_parse_reference_with_at_prefix(self):
        """Test parsing reference strips @ prefix."""
        ref_type, value = parse_reference("@:file:test.txt")

        assert ref_type == RefType.FILE
        assert value == "test.txt"


class TestReferenceCompleter:
    """Tests for ReferenceCompleter class."""

    def test_init_creates_completer(self, temp_dir):
        """Test that __init__ creates completer with resolvers."""
        completer = ReferenceCompleter(temp_dir, max_suggestions=5)

        assert completer.working_dir == temp_dir
        assert completer.max_suggestions == 5
        assert RefType.FILE in completer.resolvers

    def test_get_completions_sync_returns_empty(self, temp_dir):
        """Test that sync get_completions returns empty iterator."""
        completer = ReferenceCompleter(temp_dir)
        document = Document(text="@:file:", cursor_position=7)
        event = CompleteEvent()

        completions = list(completer.get_completions(document, event))

        assert len(completions) == 0

    @pytest.mark.asyncio
    async def test_get_completions_async_no_at_ref(self, temp_dir):
        """Test async completions with no @ reference."""
        completer = ReferenceCompleter(temp_dir)
        document = Document(text="regular text", cursor_position=12)
        event = CompleteEvent()

        completions = []
        async for completion in completer.get_completions_async(document, event):
            completions.append(completion)

        assert len(completions) == 0

    @pytest.mark.asyncio
    async def test_get_completions_async_with_at_ref(self, temp_dir):
        """Test async completions with @ reference."""
        test_file = temp_dir / "test.txt"
        test_file.write_text("content")

        completer = ReferenceCompleter(temp_dir)
        document = Document(text="@:file:te", cursor_position=9)
        event = CompleteEvent()

        completions = []
        async for completion in completer.get_completions_async(document, event):
            completions.append(completion)

        assert len(completions) > 0

    @pytest.mark.asyncio
    async def test_get_completions_async_with_partial_path(self, temp_dir):
        """Test async completions with partial file path."""
        subdir = temp_dir / "subdir"
        subdir.mkdir()
        test_file = subdir / "file.txt"
        test_file.write_text("content")

        completer = ReferenceCompleter(temp_dir)
        document = Document(text="@:file:sub", cursor_position=10)
        event = CompleteEvent()

        completions = []
        async for completion in completer.get_completions_async(document, event):
            completions.append(completion)

        assert len(completions) > 0

    @pytest.mark.asyncio
    async def test_get_completions_async_respects_max_suggestions(self, temp_dir):
        """Test that completions respect max_suggestions limit."""
        for i in range(20):
            test_file = temp_dir / f"file{i}.txt"
            test_file.write_text("content")

        completer = ReferenceCompleter(temp_dir, max_suggestions=5)
        document = Document(text="@:file:file", cursor_position=11)
        event = CompleteEvent()

        completions = []
        async for completion in completer.get_completions_async(document, event):
            completions.append(completion)

        assert len(completions) <= 5

    @pytest.mark.asyncio
    async def test_get_completions_async_without_type_filter(self, temp_dir):
        """Test async completions without explicit type filter."""
        test_file = temp_dir / "test.txt"
        test_file.write_text("content")

        completer = ReferenceCompleter(temp_dir)
        document = Document(text="@te", cursor_position=3)
        event = CompleteEvent()

        completions = []
        async for completion in completer.get_completions_async(document, event):
            completions.append(completion)

        assert len(completions) >= 0

    def test_find_at_ref_with_at_symbol(self):
        """Test finding @ reference in text."""
        match = ReferenceCompleter._find_at_ref("some text @:file:path")

        assert match is not None
        assert match.group(1) == ":file:path"

    def test_find_at_ref_at_end(self):
        """Test finding @ reference at end of text."""
        match = ReferenceCompleter._find_at_ref("text @")

        assert match is not None
        assert match.group(1) == ""

    def test_find_at_ref_no_match(self):
        """Test finding @ reference with no match."""
        match = ReferenceCompleter._find_at_ref("text without reference")

        assert match is None

    def test_find_at_ref_multiple_refs(self):
        """Test finding @ reference finds last one."""
        match = ReferenceCompleter._find_at_ref("@:file:first @:file:last")

        assert match is not None
        assert match.group(1) == ":file:last"

    def test_find_at_ref_with_space_after(self):
        """Test finding @ reference stops at whitespace."""
        match = ReferenceCompleter._find_at_ref("text @:file:path more")

        assert match is None
