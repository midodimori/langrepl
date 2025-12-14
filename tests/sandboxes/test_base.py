"""Tests for sandbox injectors."""

import pytest

from src.configs import SandboxConfig, SandboxPermission, SandboxType
from src.sandboxes.injectors import DockerNetworkInjector, PackageOfflineInjector


class TestDockerNetworkInjector:
    """Tests for DockerNetworkInjector."""

    @pytest.fixture
    def injector(self):
        return DockerNetworkInjector()

    @pytest.fixture
    def config_no_network(self):
        return SandboxConfig(
            name="test",
            type=SandboxType.SEATBELT,
            permissions=[SandboxPermission.FILESYSTEM],
        )

    @pytest.fixture
    def config_with_network(self):
        return SandboxConfig(
            name="test",
            type=SandboxType.SEATBELT,
            permissions=[SandboxPermission.NETWORK],
        )

    def test_should_apply_docker_run_no_network(self, injector, config_no_network):
        """Applies to docker run when sandbox denies network."""
        assert injector.should_apply(
            "docker", ["run", "-i", "image"], config_no_network
        )

    def test_should_not_apply_with_network_permission(
        self, injector, config_with_network
    ):
        """Does not apply when sandbox grants network."""
        assert not injector.should_apply(
            "docker", ["run", "-i", "image"], config_with_network
        )

    def test_should_not_apply_non_docker(self, injector, config_no_network):
        """Does not apply to non-docker commands."""
        assert not injector.should_apply(
            "podman", ["run", "-i", "image"], config_no_network
        )

    def test_should_not_apply_docker_build(self, injector, config_no_network):
        """Does not apply to docker build."""
        assert not injector.should_apply("docker", ["build", "."], config_no_network)

    @pytest.mark.asyncio
    async def test_injects_network_none(self, injector, config_no_network):
        """Injects --network none after run."""
        cmd, args, ok = await injector.apply(
            "test", "docker", ["run", "-i", "image"], config_no_network
        )
        assert ok
        assert args == ["run", "--network", "none", "-i", "image"]

    @pytest.mark.asyncio
    async def test_skips_if_network_already_set(self, injector, config_no_network):
        """Does not inject if --network already present."""
        cmd, args, ok = await injector.apply(
            "test", "docker", ["run", "--network", "host", "image"], config_no_network
        )
        assert ok
        assert args == ["run", "--network", "host", "image"]

    @pytest.mark.asyncio
    async def test_skips_if_net_already_set(self, injector, config_no_network):
        """Does not inject if --net already present."""
        cmd, args, ok = await injector.apply(
            "test", "docker", ["run", "--net", "bridge", "image"], config_no_network
        )
        assert ok
        assert args == ["run", "--net", "bridge", "image"]


class TestPackageOfflineInjector:
    """Tests for PackageOfflineInjector."""

    @pytest.fixture
    def injector(self):
        return PackageOfflineInjector()

    @pytest.fixture
    def config_no_network(self):
        return SandboxConfig(
            name="test",
            type=SandboxType.SEATBELT,
            permissions=[SandboxPermission.FILESYSTEM],
        )

    @pytest.fixture
    def config_with_network(self):
        return SandboxConfig(
            name="test",
            type=SandboxType.SEATBELT,
            permissions=[SandboxPermission.NETWORK],
        )

    def test_should_apply_npx_no_network(self, injector, config_no_network):
        """Applies to npx when sandbox denies network."""
        assert injector.should_apply("npx", ["@mcp/server"], config_no_network)

    def test_should_apply_uvx_no_network(self, injector, config_no_network):
        """Applies to uvx when sandbox denies network."""
        assert injector.should_apply("uvx", ["ruff"], config_no_network)

    def test_should_not_apply_with_network(self, injector, config_with_network):
        """Does not apply when sandbox grants network."""
        assert not injector.should_apply("npx", ["@mcp/server"], config_with_network)

    def test_should_not_apply_non_package_manager(self, injector, config_no_network):
        """Does not apply to non-package-manager commands."""
        assert not injector.should_apply("node", ["server.js"], config_no_network)


class TestPathEscaping:
    """Tests for path escaping in seatbelt profiles."""

    def test_escape_newlines_in_path(self):
        """Newlines in paths are removed."""
        from src.sandboxes.impl.seatbelt import _escape_seatbelt_path

        result = _escape_seatbelt_path("/path/with\nnewline")
        assert "\n" not in result
        assert result == "/path/withnewline"

    def test_escape_carriage_return_in_path(self):
        """Carriage returns in paths are removed."""
        from src.sandboxes.impl.seatbelt import _escape_seatbelt_path

        result = _escape_seatbelt_path("/path/with\rcarriage")
        assert "\r" not in result

    def test_escape_quotes_in_path(self):
        """Quotes in paths are escaped."""
        from src.sandboxes.impl.seatbelt import _escape_seatbelt_path

        result = _escape_seatbelt_path('/path/with"quote')
        assert '\\"' in result

    def test_escape_backslash_in_path(self):
        """Backslashes in paths are escaped."""
        from src.sandboxes.impl.seatbelt import _escape_seatbelt_path

        result = _escape_seatbelt_path("/path/with\\backslash")
        assert "\\\\" in result
