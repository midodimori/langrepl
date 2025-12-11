"""Tests for package cache detection utilities."""

from unittest.mock import AsyncMock, patch

import pytest

from src.utils.package_cache import (
    PackageInfo,
    _extract_docker_image,
    _extract_npx_package,
    _extract_uvx_package,
    cache_package,
    check_package_cached,
    detect_package_manager,
    is_docker_image_cached,
    is_npx_package_cached,
    is_uvx_package_cached,
)


class TestExtractNpxPackage:
    def test_simple_package(self):
        assert _extract_npx_package(["npx", "prettier"]) == "prettier"

    def test_scoped_package(self):
        assert (
            _extract_npx_package(["npx", "@anthropic/mcp-server"])
            == "@anthropic/mcp-server"
        )

    def test_with_y_flag(self):
        assert _extract_npx_package(["npx", "-y", "@scope/pkg"]) == "@scope/pkg"

    def test_in_sh_command(self):
        assert (
            _extract_npx_package(["sh", "-c", "npx -y @brave/brave-search 2>/dev/null"])
            == "@brave/brave-search"
        )

    def test_no_npx(self):
        assert _extract_npx_package(["node", "index.js"]) is None

    def test_empty_args(self):
        assert _extract_npx_package([]) is None


class TestExtractUvxPackage:
    def test_simple_package(self):
        assert _extract_uvx_package(["uvx", "ruff"]) == "ruff"

    def test_package_with_extras(self):
        assert (
            _extract_uvx_package(["uvx", "mypackage[extra1,extra2]"])
            == "mypackage[extra1,extra2]"
        )

    def test_no_uvx(self):
        assert _extract_uvx_package(["uv", "run", "script.py"]) is None

    def test_empty_args(self):
        assert _extract_uvx_package([]) is None


class TestExtractDockerImage:
    def test_simple_image(self):
        assert _extract_docker_image(["docker", "run", "alpine"]) == "alpine"

    def test_image_with_tag(self):
        assert (
            _extract_docker_image(["docker", "run", "nginx:latest"]) == "nginx:latest"
        )

    def test_with_flags(self):
        assert (
            _extract_docker_image(["docker", "run", "-it", "--rm", "ubuntu:22.04"])
            == "ubuntu:22.04"
        )

    def test_registry_image(self):
        assert (
            _extract_docker_image(["docker", "run", "ghcr.io/owner/image:v1"])
            == "ghcr.io/owner/image:v1"
        )

    def test_no_docker_run(self):
        assert _extract_docker_image(["docker", "build", "."]) is None

    def test_empty_args(self):
        assert _extract_docker_image([]) is None


class TestDetectPackageManager:
    def test_detect_npx(self):
        result = detect_package_manager("npx", ["@scope/package"])
        assert result is not None
        assert result.manager == "npx"
        assert result.package == "@scope/package"

    def test_detect_npx_via_sh(self):
        result = detect_package_manager("sh", ["-c", "npx -y @test/pkg 2>/dev/null"])
        assert result is not None
        assert result.manager == "npx"
        assert result.package == "@test/pkg"

    def test_detect_uvx(self):
        result = detect_package_manager("uvx", ["ruff"])
        assert result is not None
        assert result.manager == "uvx"
        assert result.package == "ruff"

    def test_detect_docker(self):
        result = detect_package_manager("docker", ["run", "-it", "alpine"])
        assert result is not None
        assert result.manager == "docker"
        assert result.package == "alpine"

    def test_no_package_manager(self):
        result = detect_package_manager("node", ["server.js"])
        assert result is None

    def test_python_command(self):
        result = detect_package_manager("python", ["-m", "http.server"])
        assert result is None


class TestIsNpxPackageCached:
    @pytest.mark.asyncio
    async def test_cached_package(self):
        with patch("src.utils.package_cache.shutil.which", return_value="/usr/bin/npx"):
            with patch(
                "src.utils.package_cache.execute_bash_command", new_callable=AsyncMock
            ) as mock_exec:
                mock_exec.return_value = (0, "help output", "")
                result = await is_npx_package_cached("@test/package")
                assert result is True

    @pytest.mark.asyncio
    async def test_uncached_package(self):
        with patch("src.utils.package_cache.shutil.which", return_value="/usr/bin/npx"):
            with patch(
                "src.utils.package_cache.execute_bash_command", new_callable=AsyncMock
            ) as mock_exec:
                mock_exec.return_value = (1, "", "npm error code ENOTCACHED")
                result = await is_npx_package_cached("@test/package")
                assert result is False

    @pytest.mark.asyncio
    async def test_npx_not_available(self):
        with patch("src.utils.package_cache.shutil.which", return_value=None):
            result = await is_npx_package_cached("@test/package")
            assert result is False


class TestIsUvxPackageCached:
    @pytest.mark.asyncio
    async def test_cached_package(self):
        with patch("src.utils.package_cache.shutil.which", return_value="/usr/bin/uvx"):
            with patch(
                "src.utils.package_cache.execute_bash_command", new_callable=AsyncMock
            ) as mock_exec:
                mock_exec.return_value = (0, "help output", "")
                result = await is_uvx_package_cached("ruff")
                assert result is True

    @pytest.mark.asyncio
    async def test_uncached_package(self):
        with patch("src.utils.package_cache.shutil.which", return_value="/usr/bin/uvx"):
            with patch(
                "src.utils.package_cache.execute_bash_command", new_callable=AsyncMock
            ) as mock_exec:
                mock_exec.return_value = (
                    1,
                    "",
                    "Packages were unavailable because the network was disabled",
                )
                result = await is_uvx_package_cached("ruff")
                assert result is False

    @pytest.mark.asyncio
    async def test_uvx_not_available(self):
        with patch("src.utils.package_cache.shutil.which", return_value=None):
            result = await is_uvx_package_cached("ruff")
            assert result is False


class TestIsDockerImageCached:
    @pytest.mark.asyncio
    async def test_cached_image(self):
        with patch(
            "src.utils.package_cache.shutil.which", return_value="/usr/bin/docker"
        ):
            with patch(
                "src.utils.package_cache.execute_bash_command", new_callable=AsyncMock
            ) as mock_exec:
                mock_exec.return_value = (0, "[{}]", "")
                result = await is_docker_image_cached("alpine:latest")
                assert result is True

    @pytest.mark.asyncio
    async def test_uncached_image(self):
        with patch(
            "src.utils.package_cache.shutil.which", return_value="/usr/bin/docker"
        ):
            with patch(
                "src.utils.package_cache.execute_bash_command", new_callable=AsyncMock
            ) as mock_exec:
                mock_exec.return_value = (1, "", "No such image")
                result = await is_docker_image_cached("nonexistent:latest")
                assert result is False

    @pytest.mark.asyncio
    async def test_docker_not_available(self):
        with patch("src.utils.package_cache.shutil.which", return_value=None):
            result = await is_docker_image_cached("alpine")
            assert result is False


class TestCheckPackageCached:
    @pytest.mark.asyncio
    async def test_check_npx_package(self):
        with patch(
            "src.utils.package_cache.is_npx_package_cached", new_callable=AsyncMock
        ) as mock_check:
            mock_check.return_value = True
            info = PackageInfo(manager="npx", package="@test/pkg")
            result = await check_package_cached(info)
            assert result is True
            mock_check.assert_called_once_with("@test/pkg")

    @pytest.mark.asyncio
    async def test_check_uvx_package(self):
        with patch(
            "src.utils.package_cache.is_uvx_package_cached", new_callable=AsyncMock
        ) as mock_check:
            mock_check.return_value = False
            info = PackageInfo(manager="uvx", package="ruff")
            result = await check_package_cached(info)
            assert result is False
            mock_check.assert_called_once_with("ruff")

    @pytest.mark.asyncio
    async def test_check_docker_package(self):
        with patch(
            "src.utils.package_cache.is_docker_image_cached", new_callable=AsyncMock
        ) as mock_check:
            mock_check.return_value = True
            info = PackageInfo(manager="docker", package="alpine:latest")
            result = await check_package_cached(info)
            assert result is True
            mock_check.assert_called_once_with("alpine:latest")

    @pytest.mark.asyncio
    async def test_unknown_manager_returns_true(self):
        info = PackageInfo(manager="unknown", package="pkg")
        result = await check_package_cached(info)
        assert result is True


class TestCachePackage:
    @pytest.mark.asyncio
    async def test_cache_npx_package_success(self):
        with patch("src.utils.package_cache.shutil.which", return_value="/usr/bin/npx"):
            with patch(
                "src.utils.package_cache.execute_bash_command", new_callable=AsyncMock
            ) as mock_exec:
                mock_exec.return_value = (0, "output", "")
                info = PackageInfo(manager="npx", package="@test/pkg")
                result = await cache_package(info)
                assert result is True
                mock_exec.assert_called_once()
                call_args = mock_exec.call_args[0][0]
                assert call_args == ["npx", "-y", "@test/pkg", "--help"]

    @pytest.mark.asyncio
    async def test_cache_npx_package_failure(self):
        with patch("src.utils.package_cache.shutil.which", return_value="/usr/bin/npx"):
            with patch(
                "src.utils.package_cache.execute_bash_command", new_callable=AsyncMock
            ) as mock_exec:
                mock_exec.return_value = (1, "", "Error downloading")
                info = PackageInfo(manager="npx", package="@test/pkg")
                result = await cache_package(info)
                assert result is False

    @pytest.mark.asyncio
    async def test_cache_uvx_package_success(self):
        with patch("src.utils.package_cache.shutil.which", return_value="/usr/bin/uvx"):
            with patch(
                "src.utils.package_cache.execute_bash_command", new_callable=AsyncMock
            ) as mock_exec:
                mock_exec.return_value = (0, "output", "")
                info = PackageInfo(manager="uvx", package="ruff")
                result = await cache_package(info)
                assert result is True
                mock_exec.assert_called_once()
                call_args = mock_exec.call_args[0][0]
                assert call_args == ["uvx", "ruff", "--help"]

    @pytest.mark.asyncio
    async def test_cache_docker_image_success(self):
        with patch(
            "src.utils.package_cache.shutil.which", return_value="/usr/bin/docker"
        ):
            with patch(
                "src.utils.package_cache.execute_bash_command", new_callable=AsyncMock
            ) as mock_exec:
                mock_exec.return_value = (0, "Pulled", "")
                info = PackageInfo(manager="docker", package="alpine:latest")
                result = await cache_package(info)
                assert result is True
                mock_exec.assert_called_once()
                call_args = mock_exec.call_args[0][0]
                assert call_args == ["docker", "pull", "alpine:latest"]

    @pytest.mark.asyncio
    async def test_cache_unknown_manager_returns_true(self):
        info = PackageInfo(manager="unknown", package="pkg")
        result = await cache_package(info)
        assert result is True

    @pytest.mark.asyncio
    async def test_cache_npx_not_available(self):
        with patch("src.utils.package_cache.shutil.which", return_value=None):
            info = PackageInfo(manager="npx", package="@test/pkg")
            result = await cache_package(info)
            assert result is False
