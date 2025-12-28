"""Tests for sandbox configuration validation."""

from __future__ import annotations

import sys

import pytest
from pydantic import ValidationError

from langrepl.configs.sandbox import (
    BatchSandboxConfig,
    SandboxConfig,
    SandboxOS,
    SandboxType,
)

IS_MACOS = sys.platform == "darwin"
IS_LINUX = sys.platform == "linux"


class TestSandboxConfigValidation:
    """Test sandbox config OS compatibility validation."""

    def test_seatbelt_requires_macos(self):
        """Seatbelt sandbox type requires os: macos."""
        with pytest.raises(ValidationError) as exc_info:
            SandboxConfig(
                name="invalid",
                type=SandboxType.SEATBELT,
                os=SandboxOS.LINUX,
            )
        assert "seatbelt sandbox type requires os: macos" in str(exc_info.value)

    def test_bubblewrap_requires_linux(self):
        """Bubblewrap sandbox type requires os: linux."""
        with pytest.raises(ValidationError) as exc_info:
            SandboxConfig(
                name="invalid",
                type=SandboxType.BUBBLEWRAP,
                os=SandboxOS.MACOS,
            )
        assert "bubblewrap sandbox type requires os: linux" in str(exc_info.value)

    @pytest.mark.skipif(not IS_MACOS, reason="macOS only")
    def test_validate_current_os_macos_mismatch(self):
        """validate_current_os raises on macOS when config is linux."""
        config = SandboxConfig(
            name="linux-config",
            type=SandboxType.BUBBLEWRAP,
            os=SandboxOS.LINUX,
        )
        with pytest.raises(RuntimeError) as exc_info:
            config.validate_current_os()
        assert "requires linux" in str(exc_info.value)
        assert "running on macos" in str(exc_info.value)

    @pytest.mark.skipif(not IS_LINUX, reason="Linux only")
    def test_validate_current_os_linux_mismatch(self):
        """validate_current_os raises on Linux when config is macos."""
        config = SandboxConfig(
            name="macos-config",
            type=SandboxType.SEATBELT,
            os=SandboxOS.MACOS,
        )
        with pytest.raises(RuntimeError) as exc_info:
            config.validate_current_os()
        assert "requires macos" in str(exc_info.value)
        assert "running on linux" in str(exc_info.value)


class TestBatchSandboxConfig:
    """Test BatchSandboxConfig operations."""

    def test_get_sandbox_config_found(self):
        """get_sandbox_config returns matching config by name."""
        config1 = SandboxConfig(
            name="config-one",
            type=SandboxType.SEATBELT,
            os=SandboxOS.MACOS,
        )
        config2 = SandboxConfig(
            name="config-two",
            type=SandboxType.BUBBLEWRAP,
            os=SandboxOS.LINUX,
        )
        batch = BatchSandboxConfig(sandboxes=[config1, config2])

        result = batch.get_sandbox_config("config-two")

        assert result is not None
        assert result.name == "config-two"
        assert result.type == SandboxType.BUBBLEWRAP

    def test_get_sandbox_config_not_found(self):
        """get_sandbox_config returns None for non-existent name."""
        config = SandboxConfig(
            name="existing",
            type=SandboxType.SEATBELT,
            os=SandboxOS.MACOS,
        )
        batch = BatchSandboxConfig(sandboxes=[config])

        result = batch.get_sandbox_config("non-existent")

        assert result is None
