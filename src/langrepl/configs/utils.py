"""Utility functions for config loading and persistence."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

if TYPE_CHECKING:
    from langrepl.configs.base import VersionedConfig

logger = logging.getLogger(__name__)


def _migrate_items(
    items: list[dict], config_class: type[VersionedConfig], file_path: Path
) -> tuple[list[dict], bool]:
    """Migrate config items to latest version.

    Returns:
        Tuple of (migrated_items, needs_save)
    """
    from packaging import version as pkg_version

    migrated_items: list[dict] = []
    needs_save = False
    latest_version = config_class.get_latest_version()

    for item in items:
        current_version = item.get("version", "0.0.0")

        if pkg_version.parse(current_version) < pkg_version.parse(latest_version):
            migrated_item = config_class.migrate(item, current_version)
            migrated_item["version"] = latest_version
            migrated_items.append(migrated_item)
            needs_save = True
        else:
            migrated_items.append(item)

    if needs_save:
        logger.warning(
            f"Migrating {config_class.__name__} to version {latest_version}: {file_path}"
        )

    return migrated_items, needs_save


async def _atomic_write(file_path: Path, content: str) -> None:
    """Write content to file atomically using temp file and replace."""
    temp_file = file_path.with_suffix(".tmp")
    try:
        await asyncio.to_thread(temp_file.write_text, content)
        await asyncio.to_thread(temp_file.replace, file_path)
    except Exception:
        if temp_file.exists():
            await asyncio.to_thread(temp_file.unlink)
        raise


def _validate_no_duplicates(items: list[dict], key: str, config_type: str) -> None:
    """Validate no duplicate keys in config items."""
    seen = set()
    for idx, item in enumerate(items):
        if key not in item:
            raise ValueError(
                f"Config item at index {idx} missing required key '{key}': {item}"
            )
        value = item[key]
        if value in seen:
            raise ValueError(
                f"Duplicate {config_type.lower()} '{key}': '{value}'. "
                f"Each {config_type.lower()} must have a unique {key}."
            )
        seen.add(value)


async def _load_dir_items(
    dir_path: Path,
    key: str | None = None,
    config_type: str | None = None,
    config_class: type[VersionedConfig] | None = None,
) -> list[dict]:
    """Load and migrate config items from directory."""
    if not dir_path.exists():
        return []

    items: list[dict] = []
    yml_files = await asyncio.to_thread(lambda: sorted(dir_path.glob("*.yml")))
    for yml_file in yml_files:
        content = await asyncio.to_thread(yml_file.read_text)
        data = yaml.safe_load(content)

        is_list = isinstance(data, list)
        file_items = data if is_list else [data] if isinstance(data, dict) else []

        if config_class:
            migrated_items, needs_save = _migrate_items(
                file_items, config_class, yml_file
            )

            if needs_save:
                save_data = migrated_items if is_list else migrated_items[0]
                yaml_str = yaml.dump(
                    save_data, default_flow_style=False, sort_keys=False
                )
                await _atomic_write(yml_file, yaml_str)

            file_items = migrated_items

        if key and config_type:
            for item in file_items:
                if (item_key := item.get(key)) and item_key != yml_file.stem:
                    raise ValueError(
                        f"{config_type} file '{yml_file.name}' has {key}='{item_key}' "
                        f"but filename is '{yml_file.stem}'. Rename file to '{item_key}.yml'."
                    )

        items.extend(file_items)

    return items


async def _load_single_file(
    file_path: Path, key: str, config_class: type[VersionedConfig]
) -> list[dict]:
    """Load and migrate config items from single file."""
    yaml_content = await asyncio.to_thread(file_path.read_text)
    data = yaml.safe_load(yaml_content)
    items = data.get(key, []) if isinstance(data, dict) else []

    migrated_items, needs_save = _migrate_items(items, config_class, file_path)

    if needs_save:
        data[key] = migrated_items
        yaml_str = yaml.dump(data, default_flow_style=False, sort_keys=False)
        await _atomic_write(file_path, yaml_str)

    return migrated_items


async def load_prompt_content(
    base_path: Path, prompt: str | list[str] | None
) -> str | None:
    """Load and concatenate prompt content from one or more files.

    Args:
        base_path: Base directory containing prompt files
        prompt: Single file path, list of file paths, or already-loaded content

    Returns:
        Concatenated prompt content with double newline separators, or None
    """
    if not prompt:
        return None

    if isinstance(prompt, str):
        prompt_path = base_path / prompt
        if prompt_path.exists() and prompt_path.is_file():
            return await asyncio.to_thread(prompt_path.read_text)
        return prompt

    if isinstance(prompt, list):
        contents = []
        for prompt_file in prompt:
            prompt_path = base_path / prompt_file
            if prompt_path.exists() and prompt_path.is_file():
                content = await asyncio.to_thread(prompt_path.read_text)
                contents.append(content)
            else:
                contents.append(prompt_file)
        return "\n\n".join(contents)

    return str(prompt)
