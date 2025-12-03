#!/usr/bin/env python3
"""Sync pyproject.toml dependency versions with uv.lock locked versions."""

import argparse
import re
import subprocess
import sys
import tomllib
from pathlib import Path

import tomlkit
from packaging.version import parse


def run_command(cmd: list[str]) -> None:
    """Run a command and exit on failure."""
    print(f"Running: {' '.join(cmd)}")
    subprocess.run(cmd, capture_output=False, check=True)


def parse_uv_lock(lock_file: Path) -> dict[str, str]:
    """Parse uv.lock and extract package versions."""
    with open(lock_file, "rb") as f:
        data = tomllib.load(f)

    packages = data.get("package", []) if isinstance(data, dict) else []
    versions = {
        pkg.get("name"): pkg.get("version")
        for pkg in packages
        if isinstance(pkg, dict) and pkg.get("name") and pkg.get("version")
    }

    return versions


def process_dependencies(
    dependencies: list[str], locked_versions: dict[str, str], section_name: str
) -> tuple[list[str], int]:
    """Process a list of dependencies and return updated versions."""
    updated = []
    updated_count = 0

    print(f"\n{section_name}:")
    for dep in dependencies:
        # Parse dependency string: "package>=version" or "package[extra]>=version"
        match = re.match(r"^([a-zA-Z0-9_-]+)(\[[^\]]+\])?(>=|==|~=|!=|<|>)(.+)$", dep)
        if not match:
            updated.append(dep)
            continue

        pkg_name = match.group(1)
        extra = match.group(2) or ""
        operator = match.group(3)
        old_version = match.group(4)

        # Get locked version
        locked_version = locked_versions.get(pkg_name)
        if not locked_version:
            print(
                f"  ⚠️  {pkg_name}: not found in lock file, keeping {operator}{old_version}"
            )
            updated.append(dep)
            continue

        # Update version if different
        if parse(locked_version) != parse(old_version):
            new_dep = f"{pkg_name}{extra}{operator}{locked_version}"
            updated.append(new_dep)
            updated_count += 1
            print(f"  ✓ {pkg_name}: {old_version} → {locked_version}")
        else:
            updated.append(dep)
            print(f"  = {pkg_name}: {old_version} (no change)")

    return updated, updated_count


def update_pyproject_versions(
    pyproject_file: Path, locked_versions: dict[str, str], *, dry_run: bool = False
) -> None:
    """Update pyproject.toml dependency versions to match locked versions."""
    doc = tomlkit.parse(pyproject_file.read_text())

    project_table = doc.get("project") or tomlkit.table()
    dep_groups_table = doc.get("dependency-groups") or tomlkit.table()

    dependencies = list(project_table.get("dependencies", []))
    total_updated_count = 0

    if dependencies:
        updated, updated_count = process_dependencies(
            [str(d) for d in dependencies], locked_versions, "dependencies"
        )
        project_table["dependencies"] = tomlkit.array(updated, multiline=True)
        total_updated_count += updated_count

    for group_name, deps in dep_groups_table.items():
        dep_list = list(deps) if deps else []
        updated, updated_count = process_dependencies(
            [str(d) for d in dep_list],
            locked_versions,
            f"dependency-groups.{group_name}",
        )
        dep_groups_table[group_name] = tomlkit.array(updated, multiline=True)
        total_updated_count += updated_count

    if not dependencies and len(dep_groups_table) == 0:
        print("No dependencies found in pyproject.toml")
        return

    doc["project"] = project_table
    doc["dependency-groups"] = dep_groups_table

    if dry_run:
        print("\n🛈 Dry run: pyproject.toml not written")
    else:
        pyproject_file.write_text(tomlkit.dumps(doc))
        print(f"\n✅ Updated {total_updated_count} package versions in pyproject.toml")
        return

    print(
        f"\n✅ (dry run) {total_updated_count} package versions would be updated in pyproject.toml"
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Sync pyproject.toml dependency versions with uv.lock locked versions."
    )
    parser.add_argument(
        "--no-upgrade",
        action="store_true",
        help="Skip running `uv lock --upgrade` before syncing versions.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview version changes without modifying files or syncing the environment.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None):
    """Main entry point."""
    args = parse_args(argv)

    project_root = Path(__file__).parent.parent
    pyproject_file = project_root / "pyproject.toml"
    lock_file = project_root / "uv.lock"

    if not pyproject_file.exists():
        print(f"Error: {pyproject_file} not found")
        sys.exit(1)

    print("=" * 60)
    print("Syncing dependency versions with locked versions")
    print("=" * 60)
    if args.dry_run:
        print("Dry run enabled: no files will be modified, no sync will run.")

    # Step 1: Upgrade lock file
    print("\n[1/4] Upgrading lock file...")
    if args.dry_run:
        print("Skipping lock upgrade (dry run)")
    elif args.no_upgrade:
        print("Skipping lock upgrade (--no-upgrade provided)")
    else:
        run_command(["uv", "lock", "--upgrade"])

    if not lock_file.exists():
        if args.dry_run:
            print("Warning: uv.lock not found; exiting dry run.")
            return
        print(
            "Error: uv.lock not found. Run `uv lock` (or remove --no-upgrade) to generate it."
        )
        sys.exit(1)

    # Step 2: Parse locked versions
    print("\n[2/4] Parsing locked versions...")
    locked_versions = parse_uv_lock(lock_file)
    print(f"Found {len(locked_versions)} packages in lock file")

    # Step 3: Update pyproject.toml
    print("\n[3/4] Updating pyproject.toml...")
    update_pyproject_versions(pyproject_file, locked_versions, dry_run=args.dry_run)

    # Step 4: Sync environment
    print("\n[4/4] Syncing environment...")
    if args.dry_run:
        print("Skipping environment sync (dry run)")
    else:
        run_command(["uv", "sync"])

    print("\n" + "=" * 60)
    print("✅ Version sync complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
