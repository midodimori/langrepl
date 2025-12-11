"""Tests for SandboxFactory - edge cases."""

from unittest.mock import patch

import pytest

from src.core.config import SandboxConfig, SandboxPermission, SandboxType
from src.sandboxes.factory import SandboxFactory


class TestSandboxFactory:
    """Tests for edge cases in sandbox factory."""

    def test_raises_for_unknown_type(self, temp_dir):
        """Raises ValueError for unknown sandbox type."""
        config = SandboxConfig(
            name="test",
            type=SandboxType.SEATBELT,
            permissions=[],
        )
        # Manually override to simulate unknown type
        config.type = "unknown"  # type: ignore

        with pytest.raises(ValueError, match="Unknown sandbox type"):
            SandboxFactory.create(config, temp_dir)

    @patch(
        "src.sandboxes.impl.seatbelt.SeatbeltSandbox.is_available",
        return_value=True,
    )
    def test_config_permissions_preserved(self, mock_available, temp_dir):
        """Permissions from config are accessible on created sandbox."""
        config = SandboxConfig(
            name="restricted",
            type=SandboxType.SEATBELT,
            permissions=[SandboxPermission.NETWORK],
        )

        sandbox = SandboxFactory.create(config, temp_dir)

        assert sandbox.config.has_permission(SandboxPermission.NETWORK) is True
        assert sandbox.config.has_permission(SandboxPermission.FILESYSTEM) is False

    @patch(
        "src.sandboxes.impl.seatbelt.SeatbeltSandbox.is_available",
        return_value=True,
    )
    def test_empty_permissions_preserved(self, mock_available, temp_dir):
        """Empty permissions list creates fully restricted sandbox."""
        config = SandboxConfig(
            name="locked",
            type=SandboxType.SEATBELT,
            permissions=[],
        )

        sandbox = SandboxFactory.create(config, temp_dir)

        assert sandbox.config.has_permission(SandboxPermission.NETWORK) is False
        assert sandbox.config.has_permission(SandboxPermission.FILESYSTEM) is False

    def test_raises_when_seatbelt_unavailable(self, temp_dir):
        """Raises RuntimeError when seatbelt sandbox is not available."""
        config = SandboxConfig(
            name="test",
            type=SandboxType.SEATBELT,
            permissions=[],
        )

        with patch(
            "src.sandboxes.impl.seatbelt.SeatbeltSandbox.is_available",
            return_value=False,
        ):
            with pytest.raises(RuntimeError, match="Seatbelt sandbox is not available"):
                SandboxFactory.create(config, temp_dir)

    def test_raises_when_bubblewrap_unavailable(self, temp_dir):
        """Raises RuntimeError when bubblewrap sandbox is not available."""
        config = SandboxConfig(
            name="test",
            type=SandboxType.BUBBLEWRAP,
            permissions=[],
        )

        with patch(
            "src.sandboxes.impl.bubblewrap.BubblewrapSandbox.is_available",
            return_value=False,
        ):
            with pytest.raises(
                RuntimeError, match="Bubblewrap sandbox is not available"
            ):
                SandboxFactory.create(config, temp_dir)
