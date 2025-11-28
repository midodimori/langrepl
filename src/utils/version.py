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
    """Get latest features across versions up to max_display limit."""
    try:
        features_yaml = (
            importlib.resources.files("resources")
            .joinpath("features/notes.yml")
            .read_text()
        )
        data = yaml.safe_load(features_yaml)
        version = get_version()
        current_minor = ".".join(version.split(".")[:2])
        max_display = data.get("max_display", 4)

        all_features = []
        features_by_version = data.get("features_by_version", {})

        # Extract version numbers and sort descending
        version_keys = sorted(
            features_by_version.keys(),
            key=lambda v: tuple(int(x) for x in v.replace(".x", ".0").split(".")),
            reverse=True,
        )

        # Start from current version and collect features
        for version_key in version_keys:
            version_minor = version_key.replace(".x", "")
            if tuple(int(x) for x in version_minor.split(".")) <= tuple(
                int(x) for x in current_minor.split(".")
            ):
                version_features = features_by_version[version_key]
                all_features.extend(version_features)
                if len(all_features) >= max_display:
                    break

        return all_features[:max_display]
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
