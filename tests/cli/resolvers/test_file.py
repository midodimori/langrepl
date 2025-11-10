"""Tests for FileResolver."""

from pathlib import Path
from shlex import quote
from unittest.mock import patch

import pytest

from src.cli.resolvers.file import FileResolver


class TestFileResolverGetFiles:
    """Tests for FileResolver._get_files method."""

    @pytest.mark.asyncio
    @patch("src.cli.resolvers.file.execute_bash_command")
    async def test_get_files_with_git(self, mock_exec, temp_dir):
        """Test getting files using git."""
        mock_exec.return_value = (0, "file1.py\nfile2.py\nfile3.py\n", "")

        files = await FileResolver._get_files(temp_dir)

        assert files == ["file1.py", "file2.py", "file3.py"]
        assert "git ls-files" in mock_exec.call_args[0][0][2]

    @pytest.mark.asyncio
    @patch("src.cli.resolvers.file.execute_bash_command")
    async def test_get_files_git_fails_fallback_to_fd(self, mock_exec, temp_dir):
        """Test fallback to fd when git fails."""
        mock_exec.side_effect = [
            (1, "", "not a git repository"),
            (0, "file1.py\nfile2.py\n", ""),
        ]

        files = await FileResolver._get_files(temp_dir)

        assert files == ["file1.py", "file2.py"]
        assert mock_exec.call_count == 2
        assert "fd --type f" in mock_exec.call_args_list[1][0][0][2]

    @pytest.mark.asyncio
    @patch("src.cli.resolvers.file.execute_bash_command")
    async def test_get_files_both_commands_fail(self, mock_exec, temp_dir):
        """Test when both git and fd fail."""
        mock_exec.side_effect = [
            (1, "", "not a git repository"),
            (1, "", "fd not found"),
        ]

        files = await FileResolver._get_files(temp_dir)

        assert files == []

    @pytest.mark.asyncio
    @patch("src.cli.resolvers.file.execute_bash_command")
    async def test_get_files_filters_empty_lines(self, mock_exec, temp_dir):
        """Test that empty lines are filtered out."""
        mock_exec.return_value = (0, "file1.py\n\nfile2.py\n\n", "")

        files = await FileResolver._get_files(temp_dir)

        assert files == ["file1.py", "file2.py"]

    @pytest.mark.asyncio
    @patch("src.cli.resolvers.file.execute_bash_command")
    async def test_get_files_pattern_escaping(self, mock_exec, temp_dir):
        """Test that pattern is properly quoted for shell safety."""
        mock_exec.return_value = (0, "test.py\n", "")

        await FileResolver._get_files(temp_dir, pattern="$(malicious)")

        call_args = mock_exec.call_args[0][0][2]
        assert quote("$(malicious)") in call_args


class TestFileResolverGetDirectories:
    """Tests for FileResolver._get_directories method."""

    @pytest.mark.asyncio
    @patch("src.cli.resolvers.file.execute_bash_command")
    async def test_get_directories_filters_dot(self, mock_exec, temp_dir):
        """Test that current directory (.) is filtered out."""
        mock_exec.return_value = (0, ".\nsrc\ntests\n", "")

        dirs = await FileResolver._get_directories(temp_dir)

        assert "." not in dirs
        assert dirs == ["src", "tests"]

    @pytest.mark.asyncio
    @patch("src.cli.resolvers.file.execute_bash_command")
    async def test_get_directories_git_fails_fallback_to_fd(self, mock_exec, temp_dir):
        """Test fallback to fd when git fails."""
        mock_exec.side_effect = [
            (1, "", "not a git repository"),
            (0, "src\ntests\n", ""),
        ]

        dirs = await FileResolver._get_directories(temp_dir)

        assert dirs == ["src", "tests"]
        assert mock_exec.call_count == 2
        assert "fd --type d" in mock_exec.call_args_list[1][0][0][2]


class TestFileResolverResolve:
    """Tests for FileResolver.resolve method."""

    def test_resolve_relative_path(self, temp_dir):
        """Test resolving relative path."""
        resolver = FileResolver()
        ctx = {"working_dir": str(temp_dir)}

        result = resolver.resolve("test.py", ctx)

        expected = str((temp_dir / "test.py").resolve())
        assert result == expected

    def test_resolve_nested_relative_path(self, temp_dir):
        """Test resolving nested relative path."""
        resolver = FileResolver()
        ctx = {"working_dir": str(temp_dir)}

        result = resolver.resolve("src/test.py", ctx)

        expected = str((temp_dir / "src" / "test.py").resolve())
        assert result == expected

    def test_resolve_absolute_path(self, temp_dir):
        """Test resolving absolute path."""
        resolver = FileResolver()
        ctx = {"working_dir": str(temp_dir)}
        absolute_path = "/tmp/test.py"

        result = resolver.resolve(absolute_path, ctx)

        assert result == str(Path(absolute_path).resolve())

    def test_resolve_root_slash(self, temp_dir):
        """Test resolving root slash returns working directory."""
        resolver = FileResolver()
        ctx = {"working_dir": str(temp_dir)}

        result = resolver.resolve("/", ctx)

        assert result == str(temp_dir.resolve())

    def test_resolve_parent_directory_reference(self, temp_dir):
        """Test resolving parent directory reference."""
        resolver = FileResolver()
        ctx = {"working_dir": str(temp_dir)}

        result = resolver.resolve("../test.py", ctx)

        expected = str((temp_dir / ".." / "test.py").resolve())
        assert result == expected

    def test_resolve_with_invalid_working_dir_returns_original(self):
        """Test resolve returns original ref when path resolution fails."""
        resolver = FileResolver()
        ctx = {"working_dir": ""}

        with patch("src.cli.resolvers.file.resolve_path") as mock_resolve:
            mock_resolve.side_effect = Exception("Invalid path")
            result = resolver.resolve("test.py", ctx)

        assert result == "test.py"


class TestFileResolverComplete:
    """Tests for FileResolver.complete method."""

    @pytest.mark.asyncio
    @patch("src.cli.resolvers.file.execute_bash_command")
    async def test_complete_returns_files_and_directories(self, mock_exec, temp_dir):
        """Test complete returns both files and directories."""
        resolver = FileResolver()
        ctx = {"working_dir": str(temp_dir), "start_position": 0}

        mock_exec.side_effect = [
            (0, "file1.py\nfile2.py\n", ""),
            (0, "src\ntests\n", ""),
        ]

        completions = await resolver.complete("", ctx, limit=10)

        assert len(completions) == 4
        completion_texts = [c.text for c in completions]
        assert "@:file:file1.py" in completion_texts
        assert "@:file:file2.py" in completion_texts
        assert "@:file:src" in completion_texts
        assert "@:file:tests" in completion_texts

    @pytest.mark.asyncio
    @patch("src.cli.resolvers.file.execute_bash_command")
    async def test_complete_directories_have_trailing_slash_in_display(
        self, mock_exec, temp_dir
    ):
        """Test directories have trailing slash in display text."""
        resolver = FileResolver()
        ctx = {"working_dir": str(temp_dir), "start_position": 0}

        mock_exec.side_effect = [
            (0, "file.py\n", ""),
            (0, "src\n", ""),
        ]

        completions = await resolver.complete("", ctx, limit=10)

        dir_completion = next(c for c in completions if "src" in c.text)
        file_completion = next(c for c in completions if "file.py" in c.text)

        assert "@:file:src/" in str(dir_completion.display)
        assert dir_completion.text == "@:file:src"
        assert "@:file:file.py" in str(file_completion.display)
        assert file_completion.text == "@:file:file.py"

    @pytest.mark.asyncio
    @patch("src.cli.resolvers.file.execute_bash_command")
    async def test_complete_sorts_directories_before_files_in_same_parent(
        self, mock_exec, temp_dir
    ):
        """Test directories appear before files in same parent directory."""
        resolver = FileResolver()
        ctx = {"working_dir": str(temp_dir), "start_position": 0}

        mock_exec.side_effect = [
            (0, "src/file.py\nroot.py\n", ""),
            (0, "src\n", ""),
        ]

        completions = await resolver.complete("", ctx, limit=10)

        completion_texts = [c.text for c in completions]
        src_dir_index = completion_texts.index("@:file:src")
        root_file_index = completion_texts.index("@:file:root.py")
        src_file_index = completion_texts.index("@:file:src/file.py")

        assert src_dir_index < root_file_index < src_file_index

    @pytest.mark.asyncio
    @patch("src.cli.resolvers.file.execute_bash_command")
    async def test_complete_handles_exception_gracefully(self, mock_exec, temp_dir):
        """Test complete returns empty list when bash command raises exception."""
        resolver = FileResolver()
        ctx = {"working_dir": str(temp_dir), "start_position": 0}

        mock_exec.side_effect = Exception("Command failed")

        completions = await resolver.complete("", ctx, limit=10)

        assert completions == []

    @pytest.mark.asyncio
    @patch("src.cli.resolvers.file.execute_bash_command")
    async def test_complete_with_empty_results(self, mock_exec, temp_dir):
        """Test complete with no files or directories found."""
        resolver = FileResolver()
        ctx = {"working_dir": str(temp_dir), "start_position": 0}

        mock_exec.side_effect = [
            (0, "", ""),
            (0, "", ""),
        ]

        completions = await resolver.complete("nonexistent", ctx, limit=10)

        assert completions == []
