"""Utilities for detecting cached package manager packages."""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass

from src.core.logging import get_logger
from src.utils.bash import execute_bash_command

logger = get_logger(__name__)


@dataclass
class PackageInfo:
    """Information about a package manager command."""

    manager: str
    package: str
    is_cached: bool | None = None


def _extract_npx_package(args: list[str]) -> str | None:
    """Extract package name from npx command args, skipping flags."""
    full_cmd = " ".join(args)
    # Skip short flags (-y) and long flags (--yes, --ignore-existing)
    pattern = r"npx\s+(?:-[\w]+\s+|--[\w-]+(?:=\S+)?\s+)*(@[\w/-]+[\w.-]*|[\w-]+)"
    match = re.search(pattern, full_cmd)
    return match.group(1) if match else None


def _extract_uvx_package(args: list[str]) -> str | None:
    """Extract package name from uvx command args, skipping flags."""
    full_cmd = " ".join(args)
    # Skip all flags (--offline, --no-progress, --python=3.12, etc.)
    pattern = r"uvx\s+(?:--[\w-]+(?:=\S+)?\s+)*([\w-]+(?:\[[\w,]+\])?)"
    match = re.search(pattern, full_cmd)
    return match.group(1) if match else None


def _extract_docker_image(args: list[str]) -> str | None:
    """Extract image name from docker run command args.

    Handles patterns like:
    - docker run image:tag
    - docker run -it image:tag
    - docker run --rm image:tag cmd
    """
    full_cmd = " ".join(args)

    docker_run_pattern = (
        r"docker\s+run\s+(?:(?:-\w+|--[\w-]+(?:=\S+)?)\s+)*([\w./-]+(?::[\w.-]+)?)"
    )
    match = re.search(docker_run_pattern, full_cmd)
    if match:
        return match.group(1)
    return None


def detect_package_manager(command: str, args: list[str]) -> PackageInfo | None:
    """Detect if a command uses a package manager that requires network.

    Returns PackageInfo if a package manager is detected, None otherwise.
    """
    full_cmd = " ".join([command] + args)

    if "npx" in full_cmd:
        package = _extract_npx_package([command] + args)
        if package:
            return PackageInfo(manager="npx", package=package)

    if "uvx" in full_cmd:
        package = _extract_uvx_package([command] + args)
        if package:
            return PackageInfo(manager="uvx", package=package)

    if "docker run" in full_cmd:
        image = _extract_docker_image([command] + args)
        if image:
            return PackageInfo(manager="docker", package=image)

    return None


async def is_npx_package_cached(package: str) -> bool:
    """Check if an npx package is cached locally.

    Uses `npx --offline` to verify the package is available without network.
    """
    if not shutil.which("npx"):
        return False

    returncode, _, stderr = await execute_bash_command(
        ["npx", "--offline", package, "--help"],
        timeout=10,
    )

    if returncode == 0:
        return True

    if "ENOTCACHED" in stderr:
        return False

    # returncode != 0 and not a known "not cached" error - treat as not cached
    return False


async def is_uvx_package_cached(package: str) -> bool:
    """Check if a uvx package is cached locally.

    Uses `uvx --offline` to verify the package is available without network.
    """
    if not shutil.which("uvx"):
        return False

    returncode, _, stderr = await execute_bash_command(
        ["uvx", "--offline", package, "--help"],
        timeout=10,
    )

    if returncode == 0:
        return True

    if "unavailable because the network was disabled" in stderr:
        return False

    # returncode != 0 and not a known "not cached" error - treat as not cached
    return False


async def is_docker_image_cached(image: str) -> bool:
    """Check if a docker image is available locally.

    Uses `docker image inspect` to verify the image exists locally.
    """
    if not shutil.which("docker"):
        return False

    returncode, _, _ = await execute_bash_command(
        ["docker", "image", "inspect", image],
        timeout=10,
    )

    return returncode == 0


async def check_package_cached(info: PackageInfo) -> bool:
    """Check if a package is cached based on its manager type."""
    if info.manager == "npx":
        return await is_npx_package_cached(info.package)
    if info.manager == "uvx":
        return await is_uvx_package_cached(info.package)
    if info.manager == "docker":
        return await is_docker_image_cached(info.package)
    return True


async def cache_package(info: PackageInfo) -> bool:
    """Download/cache a package for offline use.

    Returns True if caching succeeded, False otherwise.
    """
    if info.manager == "npx":
        return await _cache_npx_package(info.package)
    if info.manager == "uvx":
        return await _cache_uvx_package(info.package)
    if info.manager == "docker":
        return await _cache_docker_image(info.package)
    return True


async def _cache_npx_package(package: str) -> bool:
    """Cache an npx package by running it once with network access."""
    if not shutil.which("npx"):
        return False

    logger.info(f"Caching npx package '{package}' for offline use...")
    returncode, _, stderr = await execute_bash_command(
        ["npx", "-y", package, "--help"],
        timeout=120,
    )

    if returncode == 0:
        logger.info(f"Successfully cached npx package '{package}'")
        return True

    logger.warning(f"Failed to cache npx package '{package}': {stderr}")
    return False


async def _cache_uvx_package(package: str) -> bool:
    """Cache a uvx package by running it once with network access."""
    if not shutil.which("uvx"):
        return False

    logger.info(f"Caching uvx package '{package}' for offline use...")
    returncode, _, stderr = await execute_bash_command(
        ["uvx", package, "--help"],
        timeout=120,
    )

    if returncode == 0:
        logger.info(f"Successfully cached uvx package '{package}'")
        return True

    logger.warning(f"Failed to cache uvx package '{package}': {stderr}")
    return False


async def _cache_docker_image(image: str) -> bool:
    """Cache a docker image by pulling it."""
    if not shutil.which("docker"):
        return False

    logger.info(f"Pulling docker image '{image}' for offline use...")
    returncode, _, stderr = await execute_bash_command(
        ["docker", "pull", image],
        timeout=300,
    )

    if returncode == 0:
        logger.info(f"Successfully pulled docker image '{image}'")
        return True

    logger.warning(f"Failed to pull docker image '{image}': {stderr}")
    return False
