"""Tests for sandbox profile cache."""

from __future__ import annotations

from pathlib import Path

import pytest

from langrepl.sandboxes.cache import ProfileCache


@pytest.fixture
def cache(temp_dir: Path) -> ProfileCache:
    """Create a profile cache with temp directory."""
    return ProfileCache(temp_dir)


class TestProfileCache:
    """Tests for ProfileCache hash and path generation."""

    def test_hash_stability(self, cache: ProfileCache, temp_dir: Path):
        """Same inputs should produce the same hash."""
        config_dict = {"key": "value", "nested": {"a": 1}}

        hash1 = cache._compute_hash("test-config", temp_dir, config_dict)
        hash2 = cache._compute_hash("test-config", temp_dir, config_dict)

        assert hash1 == hash2
        assert len(hash1) == 16  # SHA256 truncated to 16 chars

    def test_hash_sensitivity_name(self, cache: ProfileCache, temp_dir: Path):
        """Different config name should produce different hash."""
        config_dict = {"key": "value"}

        hash1 = cache._compute_hash("config-one", temp_dir, config_dict)
        hash2 = cache._compute_hash("config-two", temp_dir, config_dict)

        assert hash1 != hash2

    def test_hash_sensitivity_working_dir(self, cache: ProfileCache, temp_dir: Path):
        """Different working_dir should produce different hash."""
        config_dict = {"key": "value"}
        other_dir = temp_dir / "other"
        other_dir.mkdir()

        hash1 = cache._compute_hash("test-config", temp_dir, config_dict)
        hash2 = cache._compute_hash("test-config", other_dir, config_dict)

        assert hash1 != hash2

    def test_hash_sensitivity_config(self, cache: ProfileCache, temp_dir: Path):
        """Different config dict should produce different hash."""
        config1 = {"key": "value1"}
        config2 = {"key": "value2"}

        hash1 = cache._compute_hash("test-config", temp_dir, config1)
        hash2 = cache._compute_hash("test-config", temp_dir, config2)

        assert hash1 != hash2

    def test_path_format(self, cache: ProfileCache, temp_dir: Path):
        """Cache path should follow format: {name}_{hash}{suffix}."""
        config_dict = {"key": "value"}

        path = cache.get_path("my-config", temp_dir, config_dict, suffix=".sb")

        assert path.parent == temp_dir
        assert path.name.startswith("my-config_")
        assert path.name.endswith(".sb")
        # Format: my-config_{16-char-hash}.sb
        assert len(path.stem) == len("my-config_") + 16

    def test_path_different_suffix(self, cache: ProfileCache, temp_dir: Path):
        """Different suffix should be reflected in path."""
        config_dict = {"key": "value"}

        sb_path = cache.get_path("config", temp_dir, config_dict, suffix=".sb")
        bpf_path = cache.get_path("config", temp_dir, config_dict, suffix=".bpf")

        assert sb_path.suffix == ".sb"
        assert bpf_path.suffix == ".bpf"
        # Same hash, different suffix
        assert sb_path.stem == bpf_path.stem
