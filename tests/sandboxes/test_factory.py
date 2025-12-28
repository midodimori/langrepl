"""Tests for sandbox factory."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from langrepl.configs.sandbox import (
    AgentSandboxConfig,
    FilesystemConfig,
    NetworkConfig,
    SandboxConfig,
    SandboxOS,
    SandboxProfileBinding,
    SandboxType,
)
from langrepl.sandboxes.factory import SandboxFactory

IS_MACOS = sys.platform == "darwin"
IS_LINUX = sys.platform == "linux"


def _create_config(name: str) -> SandboxConfig:
    """Create a sandbox config for current platform."""
    if IS_MACOS:
        return SandboxConfig(
            name=name,
            type=SandboxType.SEATBELT,
            os=SandboxOS.MACOS,
            filesystem=FilesystemConfig(read=["."], write=["."]),
            network=NetworkConfig(remote=["*"]),
        )
    return SandboxConfig(
        name=name,
        type=SandboxType.BUBBLEWRAP,
        os=SandboxOS.LINUX,
        filesystem=FilesystemConfig(read=["."], write=["."]),
        network=NetworkConfig(remote=["*"]),
    )


class TestSandboxFactory:
    """Tests for SandboxFactory."""

    @pytest.mark.skipif(not (IS_MACOS or IS_LINUX), reason="Requires macOS or Linux")
    def test_backend_caching(self, temp_dir: Path):
        """Same config+working_dir should return cached backend."""
        factory = SandboxFactory()
        config = _create_config("cached-test")

        backend1 = factory.create_backend(config, temp_dir)
        backend2 = factory.create_backend(config, temp_dir)

        assert backend1 is backend2

    @pytest.mark.skipif(not (IS_MACOS or IS_LINUX), reason="Requires macOS or Linux")
    def test_backend_caching_different_dir(self, temp_dir: Path):
        """Different working_dir should create new backend."""
        factory = SandboxFactory()
        config = _create_config("different-dir-test")
        other_dir = temp_dir / "other"
        other_dir.mkdir()

        backend1 = factory.create_backend(config, temp_dir)
        backend2 = factory.create_backend(config, other_dir)

        assert backend1 is not backend2

    def test_unknown_sandbox_type(self, temp_dir: Path):
        """Unknown sandbox type should raise ValueError."""
        factory = SandboxFactory()

        # Create a config with mocked invalid type
        config = MagicMock()
        config.name = "invalid"
        config.type = "unknown_type"
        config.validate_current_os = MagicMock()

        with pytest.raises(ValueError) as exc_info:
            factory.create_backend(config, temp_dir)

        assert "Unknown sandbox type" in str(exc_info.value)

    def test_build_bindings_disabled(self, temp_dir: Path):
        """Disabled agent config should return empty bindings."""
        factory = SandboxFactory()
        agent_config = AgentSandboxConfig(enabled=False, profiles=[])

        bindings = factory.build_bindings(agent_config, temp_dir)

        assert bindings == []

    @pytest.mark.skipif(not (IS_MACOS or IS_LINUX), reason="Requires macOS or Linux")
    def test_build_bindings_none_sandbox(self, temp_dir: Path):
        """Profile with sandbox=None should produce backend=None."""
        factory = SandboxFactory()
        agent_config = AgentSandboxConfig(
            enabled=True,
            profiles=[
                SandboxProfileBinding(
                    sandbox=None,
                    patterns=["langrepl.tools.internal.*"],
                ),
            ],
        )

        bindings = factory.build_bindings(agent_config, temp_dir)

        assert len(bindings) == 1
        assert bindings[0].backend is None
        assert bindings[0].patterns == ["langrepl.tools.internal.*"]

    @pytest.mark.skipif(not (IS_MACOS or IS_LINUX), reason="Requires macOS or Linux")
    def test_build_bindings_with_sandbox(self, temp_dir: Path):
        """Profile with sandbox config should create backend."""
        factory = SandboxFactory()
        config = _create_config("binding-test")
        agent_config = AgentSandboxConfig(
            enabled=True,
            profiles=[
                SandboxProfileBinding(
                    sandbox=config,
                    patterns=["langrepl.tools.impl.*"],
                ),
            ],
        )

        bindings = factory.build_bindings(agent_config, temp_dir)

        assert len(bindings) == 1
        assert bindings[0].backend is not None
        assert bindings[0].backend.name == "binding-test"
