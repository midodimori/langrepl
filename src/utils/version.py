"""Version and features utilities."""

import importlib.metadata
import importlib.resources
from pathlib import Path

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
