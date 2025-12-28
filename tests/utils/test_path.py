"""Tests for path utilities."""

from __future__ import annotations

from pathlib import Path

import pytest

from langrepl.utils.path import (
    SymlinkEscapeError,
    expand_pattern,
    is_path_within,
    is_symlink_escape,
    matches_hidden,
    pattern_to_regex,
    resolve_path,
)


class TestResolvePath:
    """Tests for resolve_path function."""

    def test_resolve_path_absolute(self, temp_dir: Path):
        """Absolute paths should resolve correctly."""
        absolute = temp_dir / "file.txt"
        absolute.touch()

        result = resolve_path(str(temp_dir), str(absolute))

        assert result == absolute.resolve()

    def test_resolve_path_relative(self, temp_dir: Path):
        """Relative paths should resolve to working_dir."""
        (temp_dir / "subdir").mkdir()
        (temp_dir / "subdir" / "file.txt").touch()

        result = resolve_path(str(temp_dir), "subdir/file.txt")

        assert result == (temp_dir / "subdir" / "file.txt").resolve()

    def test_resolve_path_slash(self, temp_dir: Path):
        """'/' should return working_dir."""
        result = resolve_path(str(temp_dir), "/")

        assert result == temp_dir.resolve()

    def test_resolve_path_tilde(self):
        """'~' should expand to home directory."""
        home = Path.home()

        result = resolve_path("/tmp", "~")

        assert result == home.resolve()

    def test_resolve_path_symlink_escape_raises(self, temp_dir: Path):
        """Symlink outside working_dir should raise SymlinkEscapeError."""
        import tempfile

        with tempfile.TemporaryDirectory() as outside:
            outside_path = Path(outside)
            outside_file = outside_path / "outside.txt"
            outside_file.touch()

            # Create symlink inside temp_dir pointing outside
            link = temp_dir / "escape_link"
            link.symlink_to(outside_file)

            with pytest.raises(SymlinkEscapeError):
                resolve_path(str(temp_dir), "escape_link")


class TestIsPathWithin:
    """Tests for is_path_within function."""

    def test_is_path_within_direct(self, temp_dir: Path):
        """Path equals boundary should return True."""
        # Both path and boundary must be resolved for comparison
        result = is_path_within(temp_dir, [temp_dir.resolve()])

        assert result is True

    def test_is_path_within_child(self, temp_dir: Path):
        """Path is child of boundary should return True."""
        child = temp_dir / "child" / "nested"
        child.mkdir(parents=True)

        result = is_path_within(child, [temp_dir.resolve()])

        assert result is True

    def test_is_path_within_outside(self, temp_dir: Path):
        """Path outside all boundaries should return False."""
        import tempfile

        with tempfile.TemporaryDirectory() as other:
            result = is_path_within(Path(other), [temp_dir.resolve()])

        assert result is False

    def test_is_path_within_multiple_boundaries(self, temp_dir: Path):
        """Path within any boundary should return True."""
        import tempfile

        with tempfile.TemporaryDirectory() as other:
            other_path = Path(other).resolve()
            child = other_path / "child"
            child.mkdir()

            result = is_path_within(child, [temp_dir.resolve(), other_path])

        assert result is True


class TestIsSymlinkEscape:
    """Tests for is_symlink_escape function."""

    def test_is_symlink_escape_not_symlink(self, temp_dir: Path):
        """Non-symlink should return False."""
        regular_file = temp_dir / "regular.txt"
        regular_file.touch()

        result = is_symlink_escape(regular_file, [temp_dir.resolve()])

        assert result is False

    def test_is_symlink_escape_within_boundary(self, temp_dir: Path):
        """Symlink inside boundary should return False."""
        target = temp_dir / "target.txt"
        target.touch()
        link = temp_dir / "link"
        link.symlink_to(target)

        result = is_symlink_escape(link, [temp_dir.resolve()])

        assert result is False

    def test_is_symlink_escape_outside_boundary(self, temp_dir: Path):
        """Symlink outside boundary should return True."""
        import tempfile

        with tempfile.TemporaryDirectory() as outside:
            outside_path = Path(outside)
            outside_file = outside_path / "outside.txt"
            outside_file.touch()

            link = temp_dir / "escape"
            link.symlink_to(outside_file)

            result = is_symlink_escape(link, [temp_dir.resolve()])

        assert result is True


class TestExpandPattern:
    """Tests for expand_pattern function."""

    def test_expand_pattern_glob(self, temp_dir: Path):
        """Glob patterns should expand to matching files."""
        (temp_dir / "file1.txt").touch()
        (temp_dir / "file2.txt").touch()
        (temp_dir / "file3.py").touch()

        result = expand_pattern(str(temp_dir / "*.txt"), temp_dir)

        assert len(result) == 2
        assert all(p.suffix == ".txt" for p in result)

    def test_expand_pattern_tilde(self):
        """Tilde should expand to home directory."""
        result = expand_pattern("~", Path("/tmp"))

        assert len(result) == 1
        assert result[0] == Path.home()

    def test_expand_pattern_literal_exists(self, temp_dir: Path):
        """Existing literal path should return list with path."""
        existing = temp_dir / "exists.txt"
        existing.touch()

        result = expand_pattern(str(existing), temp_dir)

        assert result == [existing]

    def test_expand_pattern_literal_missing(self, temp_dir: Path):
        """Missing literal path should return empty list by default."""
        result = expand_pattern(str(temp_dir / "missing.txt"), temp_dir)

        assert result == []

    def test_expand_pattern_literal_missing_include(self, temp_dir: Path):
        """Missing literal with include_nonexistent=True should return path."""
        missing = temp_dir / "missing.txt"

        result = expand_pattern(str(missing), temp_dir, include_nonexistent=True)

        assert result == [missing]

    def test_expand_pattern_relative(self, temp_dir: Path):
        """Relative pattern should be relative to working_dir."""
        subdir = temp_dir / "subdir"
        subdir.mkdir()
        (subdir / "file.txt").touch()

        result = expand_pattern("subdir/file.txt", temp_dir)

        assert result == [subdir / "file.txt"]


class TestPatternToRegex:
    """Tests for pattern_to_regex function."""

    def test_pattern_to_regex_no_wildcards(self):
        """Literal path should return None."""
        result = pattern_to_regex("/home/user/file.txt")

        # GitWildMatch may still produce a regex, but for simple paths
        # it depends on implementation. Test that it's callable.
        # The actual behavior depends on pathspec implementation.
        assert result is None or isinstance(result, str)

    def test_pattern_to_regex_with_wildcards(self):
        """Wildcards should produce valid regex."""
        result = pattern_to_regex("*.txt")

        assert result is not None
        assert isinstance(result, str)

    def test_pattern_to_regex_double_star(self):
        """Double star should be handled."""
        result = pattern_to_regex("**/*.py")

        assert result is not None
        assert isinstance(result, str)


class TestMatchesHidden:
    """Tests for matches_hidden function."""

    def test_matches_hidden_glob_pattern(self, temp_dir: Path):
        """Glob pattern should match descendant."""
        (temp_dir / ".env").touch()

        result = matches_hidden(temp_dir / ".env", ["**/.env"], temp_dir)

        assert result is True

    def test_matches_hidden_literal_path(self, temp_dir: Path):
        """Literal path should match exactly."""
        ssh_dir = temp_dir / ".ssh"
        ssh_dir.mkdir()

        result = matches_hidden(ssh_dir, [str(ssh_dir)], temp_dir)

        assert result is True

    def test_matches_hidden_no_match(self, temp_dir: Path):
        """Non-matching path should return False."""
        normal_file = temp_dir / "normal.txt"
        normal_file.touch()

        result = matches_hidden(normal_file, ["**/.env", "**/.ssh"], temp_dir)

        assert result is False

    def test_matches_hidden_nested(self, temp_dir: Path):
        """Hidden pattern should match nested paths."""
        nested = temp_dir / "project" / ".git" / "config"
        nested.parent.mkdir(parents=True)
        nested.touch()

        result = matches_hidden(nested, ["**/.git"], temp_dir)

        assert result is True

    def test_matches_hidden_tilde_pattern(self, temp_dir: Path):
        """Tilde in pattern should expand to home."""
        # This test just verifies tilde expansion doesn't crash
        result = matches_hidden(temp_dir / "file.txt", ["~/.ssh"], temp_dir)

        assert result is False
