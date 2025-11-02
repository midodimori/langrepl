"""Tests for slash command completer."""

from prompt_toolkit.completion import CompleteEvent
from prompt_toolkit.document import Document

from src.cli.completers.slash import SlashCommandCompleter


class TestSlashCommandCompleter:
    """Tests for SlashCommandCompleter class."""

    def test_init_creates_completer(self):
        """Test that __init__ creates completer with commands."""
        commands = ["/help", "/resume", "/compress"]
        completer = SlashCommandCompleter(commands)

        assert completer is not None

    def test_get_completions_with_slash_prefix(self):
        """Test completions when input starts with slash."""
        commands = ["/help", "/resume", "/compress"]
        completer = SlashCommandCompleter(commands)
        document = Document(text="/h", cursor_position=2)
        event = CompleteEvent()

        completions = list(completer.get_completions(document, event))

        assert len(completions) == 1
        assert completions[0].text == "/help"

    def test_get_completions_multiple_matches(self):
        """Test completions with multiple matching commands."""
        commands = ["/help", "/history", "/hello"]
        completer = SlashCommandCompleter(commands)
        document = Document(text="/h", cursor_position=2)
        event = CompleteEvent()

        completions = list(completer.get_completions(document, event))

        assert len(completions) == 3
        completion_texts = {c.text for c in completions}
        assert completion_texts == {"/help", "/history", "/hello"}

    def test_get_completions_exact_match(self):
        """Test completions with exact match."""
        commands = ["/help", "/resume"]
        completer = SlashCommandCompleter(commands)
        document = Document(text="/help", cursor_position=5)
        event = CompleteEvent()

        completions = list(completer.get_completions(document, event))

        assert len(completions) == 1
        assert completions[0].text == "/help"

    def test_get_completions_no_match(self):
        """Test completions with no matching commands."""
        commands = ["/help", "/resume"]
        completer = SlashCommandCompleter(commands)
        document = Document(text="/xyz", cursor_position=4)
        event = CompleteEvent()

        completions = list(completer.get_completions(document, event))

        assert len(completions) == 0

    def test_get_completions_case_insensitive(self):
        """Test that completions are case insensitive."""
        commands = ["/help", "/resume"]
        completer = SlashCommandCompleter(commands)
        document = Document(text="/H", cursor_position=2)
        event = CompleteEvent()

        completions = list(completer.get_completions(document, event))

        assert len(completions) == 1
        assert completions[0].text == "/help"

    def test_get_completions_with_partial_word(self):
        """Test completions with partial command word."""
        commands = ["/compress", "/complete"]
        completer = SlashCommandCompleter(commands)
        document = Document(text="/comp", cursor_position=5)
        event = CompleteEvent()

        completions = list(completer.get_completions(document, event))

        assert len(completions) == 2
        completion_texts = {c.text for c in completions}
        assert completion_texts == {"/compress", "/complete"}

    def test_get_completions_empty_input(self):
        """Test completions with empty input after slash."""
        commands = ["/help", "/resume", "/compress"]
        completer = SlashCommandCompleter(commands)
        document = Document(text="/", cursor_position=1)
        event = CompleteEvent()

        completions = list(completer.get_completions(document, event))

        assert len(completions) == 3

    def test_get_completions_with_arguments(self):
        """Test completions handle commands with arguments."""
        commands = ["/help", "/resume"]
        completer = SlashCommandCompleter(commands)
        document = Document(text="/help arg", cursor_position=9)
        event = CompleteEvent()

        completions = list(completer.get_completions(document, event))

        assert len(completions) == 0
