"""Tests for terminal tool command extraction and transformation."""

from langrepl.tools.impl.terminal import (
    _extract_command_parts,
    _transform_command_for_approval,
)


class TestExtractCommandParts:
    def test_simple_command(self):
        assert _extract_command_parts("ls -la") == ["ls -la"]

    def test_chained_commands_and(self):
        result = _extract_command_parts("cmd1 && cmd2")
        assert result == ["cmd1", "cmd2"]

    def test_chained_commands_or(self):
        result = _extract_command_parts("cmd1 || cmd2")
        assert result == ["cmd1", "cmd2"]

    def test_chained_commands_semicolon(self):
        result = _extract_command_parts("cmd1 ; cmd2")
        assert result == ["cmd1", "cmd2"]

    def test_chained_commands_pipe(self):
        result = _extract_command_parts("cmd1 | cmd2")
        assert result == ["cmd1", "cmd2"]

    def test_multiple_operators(self):
        result = _extract_command_parts("cmd1 && cmd2 || cmd3")
        assert result == ["cmd1", "cmd2", "cmd3"]

    def test_command_substitution_dollar_paren(self):
        result = _extract_command_parts("echo $(rm -rf /)")
        assert "echo $(rm -rf /)" in result
        assert "rm -rf /" in result

    def test_command_substitution_backticks(self):
        result = _extract_command_parts("echo `rm -rf /`")
        assert "echo `rm -rf /`" in result
        assert "rm -rf /" in result

    def test_nested_substitution(self):
        result = _extract_command_parts("echo $(cat $(ls))")
        assert "echo $(cat $(ls))" in result
        assert "cat $(ls)" in result
        assert "ls" in result

    def test_chained_with_substitution(self):
        result = _extract_command_parts("npm install && echo $(rm -rf /tmp)")
        assert "npm install" in result
        assert "echo $(rm -rf /tmp)" in result
        assert "rm -rf /tmp" in result

    def test_empty_command(self):
        assert _extract_command_parts("") == []

    def test_only_operators(self):
        assert _extract_command_parts("&& ||") == []


class TestTransformCommandForApproval:
    def test_simple_command(self):
        result = _transform_command_for_approval("ls -la /tmp")
        assert result == "ls -la /tmp"

    def test_long_command_truncated_to_3_words(self):
        result = _transform_command_for_approval("git commit -m 'long message here'")
        assert result == "git commit -m"

    def test_single_word_command(self):
        result = _transform_command_for_approval("pwd")
        assert result == "pwd"

    def test_chained_commands(self):
        result = _transform_command_for_approval("npm install && rm -rf /tmp")
        assert "npm install" in result
        assert "rm -rf" in result

    def test_command_substitution(self):
        result = _transform_command_for_approval("echo $(rm -rf /)")
        # Should contain rm -rf from the extracted substitution
        assert "rm -rf" in result

    def test_backtick_substitution(self):
        result = _transform_command_for_approval("echo `rm -rf /`")
        # Should contain rm -rf from the extracted substitution
        assert "rm -rf" in result

    def test_complex_chained_with_substitution(self):
        result = _transform_command_for_approval(
            "echo $(rm -rf /tmp) && git push origin"
        )
        assert "rm -rf" in result
        assert "git push" in result

    def test_preserves_quoted_arguments(self):
        result = _transform_command_for_approval('git commit -m "test message"')
        assert result == "git commit -m"

    def test_empty_command(self):
        result = _transform_command_for_approval("")
        assert result == ""
