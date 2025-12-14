"""Command injectors for sandbox network isolation."""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.configs import SandboxConfig, SandboxPermission
from src.core.logging import get_logger
from src.utils.package_cache import (
    cache_package,
    check_package_cached,
    detect_package_manager,
)

logger = get_logger(__name__)


class CommandInjector(ABC):
    """Base class for command injectors."""

    @abstractmethod
    def should_apply(
        self, command: str, args: list[str], config: SandboxConfig
    ) -> bool:
        """Check if this injector should apply."""

    @abstractmethod
    async def apply(
        self, name: str, command: str, args: list[str], config: SandboxConfig
    ) -> tuple[str, list[str], bool]:
        """Apply injection. Returns (command, args, success)."""


class DockerNetworkInjector(CommandInjector):
    """Injects --network none for Docker containers."""

    def should_apply(
        self, command: str, args: list[str], config: SandboxConfig
    ) -> bool:
        return (
            command == "docker"
            and "run" in args
            and SandboxPermission.NETWORK not in config.permissions
        )

    async def apply(
        self, name: str, command: str, args: list[str], config: SandboxConfig
    ) -> tuple[str, list[str], bool]:
        if "--network" in args or "--net" in args:
            return command, args, True

        args = list(args)
        run_idx = args.index("run")
        args.insert(run_idx + 1, "--network")
        args.insert(run_idx + 2, "none")
        return command, args, True


class PackageOfflineInjector(CommandInjector):
    """Caches packages and injects --offline for npx/uvx."""

    def should_apply(
        self, command: str, args: list[str], config: SandboxConfig
    ) -> bool:
        return (
            SandboxPermission.NETWORK not in config.permissions
            and detect_package_manager(command, args) is not None
        )

    async def apply(
        self, name: str, command: str, args: list[str], config: SandboxConfig
    ) -> tuple[str, list[str], bool]:
        pkg = detect_package_manager(command, args)
        if not pkg:
            return command, args, True

        if not await check_package_cached(pkg):
            logger.info(f"Caching '{pkg.package}' for sandbox...")
            if not await cache_package(pkg):
                logger.warning(f"Blocking MCP '{name}': cache failed")
                return command, args, False

        if pkg.manager in ("npx", "uvx"):
            args = list(args)
            if "--offline" not in args:
                args.insert(0, "--offline")

        return command, args, True


INJECTORS: list[CommandInjector] = [
    DockerNetworkInjector(),
    PackageOfflineInjector(),
]
