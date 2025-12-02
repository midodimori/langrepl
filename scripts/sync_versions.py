#!/usr/bin/env python3
"""Sync pyproject.toml dependency versions with uv.lock locked versions."""

import re
import subprocess
import sys
from pathlib import Path

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # Python < 3.11


def run_command(cmd: list[str]) -> None:
    """Run a command and exit on failure."""
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=False)
    if result.returncode != 0:
        sys.exit(result.returncode)


def parse_uv_lock(lock_file: Path) -> dict[str, str]:
    """Parse uv.lock and extract package versions."""
    versions = {}
    with open(lock_file) as f:
        content = f.read()

    # Match package blocks: [[package]]
    # Extract name and version from each block
    pattern = r'\[\[package\]\]\s+name\s*=\s*"([^"]+)"\s+version\s*=\s*"([^"]+)"'
    for match in re.finditer(pattern, content):
        name, version = match.groups()
        versions[name] = version

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
        if locked_version != old_version:
            new_dep = f"{pkg_name}{extra}>={locked_version}"
            updated.append(new_dep)
            updated_count += 1
            print(f"  ✓ {pkg_name}: {old_version} → {locked_version}")
        else:
            updated.append(dep)
            print(f"  = {pkg_name}: {old_version} (no change)")

    return updated, updated_count


def update_pyproject_versions(
    pyproject_file: Path, locked_versions: dict[str, str]
) -> None:
    """Update pyproject.toml dependency versions to match locked versions."""
    with open(pyproject_file, "rb") as f:
        data = tomllib.load(f)

    # Get main dependencies
    dependencies = data.get("project", {}).get("dependencies", [])

    # Get dev dependencies
    dev_dependencies = data.get("dependency-groups", {}).get("dev", [])

    if not dependencies and not dev_dependencies:
        print("No dependencies found in pyproject.toml")
        return

    # Process main dependencies
    updated = []
    total_updated_count = 0

    if dependencies:
        updated, updated_count = process_dependencies(
            dependencies, locked_versions, "dependencies"
        )
        total_updated_count += updated_count

    # Process dev dependencies
    dev_updated = []
    if dev_dependencies:
        dev_updated, dev_updated_count = process_dependencies(
            dev_dependencies, locked_versions, "dependency-groups.dev"
        )
        total_updated_count += dev_updated_count

    # Read the original file and update dependencies line by line
    with open(pyproject_file) as f:
        lines = f.readlines()

    # Create mappings of old deps to new deps for easy lookup
    dep_map = {}
    if dependencies:
        for old_dep, new_dep in zip(dependencies, updated):
            dep_map[old_dep] = new_dep

    if dev_dependencies:
        for old_dep, new_dep in zip(dev_dependencies, dev_updated):
            dep_map[old_dep] = new_dep

    # Update lines
    new_lines = []
    in_section = None  # Track which section we're in: 'dependencies' or 'dev'

    for line in lines:
        # Check if we're entering main dependencies section
        if re.match(r"^dependencies\s*=\s*\[", line):
            in_section = "dependencies"
            new_lines.append(line)
            continue

        # Check if we're entering dev dependencies section
        if re.match(r"^dev\s*=\s*\[", line):
            in_section = "dev"
            new_lines.append(line)
            continue

        # Check if we're exiting any dependency section
        if in_section and line.strip() == "]":
            in_section = None
            new_lines.append(line)
            continue

        # If we're in a dependency section, replace the line
        if in_section:
            # Extract the dependency string from the line
            match = re.search(r'"([^"]+)"', line)
            if match:
                old_dep = match.group(1)
                if old_dep in dep_map:
                    # Get indentation from original line
                    indent_match = re.match(r"^(\s+)", line)
                    indent = indent_match.group(1) if indent_match else "    "
                    # Check if there's a trailing comma
                    has_comma = "," in line
                    comma = "," if has_comma else ""
                    # Reconstruct the line with new dependency
                    new_line = f'{indent}"{dep_map[old_dep]}"{comma}\n'
                    new_lines.append(new_line)
                else:
                    new_lines.append(line)
            else:
                new_lines.append(line)
        else:
            new_lines.append(line)

    # Write back
    with open(pyproject_file, "w") as f:
        f.writelines(new_lines)

    print(f"\n✅ Updated {total_updated_count} package versions in pyproject.toml")


def main():
    """Main entry point."""
    project_root = Path(__file__).parent.parent
    pyproject_file = project_root / "pyproject.toml"
    lock_file = project_root / "uv.lock"

    if not pyproject_file.exists():
        print(f"Error: {pyproject_file} not found")
        sys.exit(1)

    print("=" * 60)
    print("Syncing dependency versions with locked versions")
    print("=" * 60)

    # Step 1: Upgrade lock file
    print("\n[1/4] Upgrading lock file...")
    run_command(["uv", "lock", "--upgrade"])

    # Step 2: Parse locked versions
    print("\n[2/4] Parsing locked versions...")
    locked_versions = parse_uv_lock(lock_file)
    print(f"Found {len(locked_versions)} packages in lock file")

    # Step 3: Update pyproject.toml
    print("\n[3/4] Updating pyproject.toml...")
    update_pyproject_versions(pyproject_file, locked_versions)

    # Step 4: Sync environment
    print("\n[4/4] Syncing environment...")
    run_command(["uv", "sync"])

    print("\n" + "=" * 60)
    print("✅ Version sync complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
