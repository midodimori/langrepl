"""Version and features utilities."""

import importlib.metadata
import importlib.resources
from pathlib import Path

import httpx
import yaml


def get_version() -> str:
    """Get package version (hybrid: installed package -> pyproject.toml)."""
    try:
        return importlib.metadata.version("langrepl")
    except importlib.metadata.PackageNotFoundError:
        try:
            import tomllib

            root = Path(__file__).parent.parent.parent
            with open(root / "pyproject.toml", "rb") as f:
                return tomllib.load(f)["project"]["version"]
        except Exception:
            return "unknown"


def get_latest_features() -> list[str]:
    """Get latest features for current minor version."""
    try:
        features_yaml = (
            importlib.resources.files("resources")
            .joinpath("features/notes.yml")
            .read_text()
        )
        data = yaml.safe_load(features_yaml)
        version = get_version()
        minor_version = ".".join(version.split(".")[:2]) + ".x"
        features = data.get("features_by_version", {}).get(minor_version, [])
        max_display = data.get("max_display", 4)
        return features[:max_display]
    except Exception:
        return []


def check_for_updates() -> tuple[str, str] | None:
    """Check PyPI for latest version and return upgrade message if newer version exists."""
    try:
        current_version = get_version()
        if current_version == "unknown":
            return None

        # Fetch latest version from PyPI
        response = httpx.get(
            "https://pypi.org/pypi/langrepl/json", timeout=2.0, follow_redirects=True
        )
        if response.status_code != 200:
            return None

        latest_version = response.json()["info"]["version"]

        # Compare versions using tuple comparison for semver
        def parse_version(v: str) -> tuple[int, ...]:
            return tuple(int(x) for x in v.split("."))

        if parse_version(latest_version) > parse_version(current_version):
            upgrade_command = "uv tool install langrepl --upgrade"
            return latest_version, upgrade_command

        return None
    except Exception:
        return None
