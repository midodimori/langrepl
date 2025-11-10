"""File reference resolver."""

from pathlib import Path
from shlex import quote

from prompt_toolkit.completion import Completion

from src.cli.resolvers.base import RefType, Resolver
from src.utils.bash import execute_bash_command
from src.utils.path import resolve_path


class FileResolver(Resolver):
    """Resolves file references."""

    type = RefType.FILE

    @staticmethod
    async def _get_files(
        working_dir: Path, limit: int | None = None, pattern: str = ""
    ) -> list[str]:
        """Get list of files (tracked and untracked) using git or fd."""
        head = f"head -n {limit}" if limit else "cat"

        safe_pattern = quote(pattern) if pattern else ""
        commands = [
            (
                f"(git ls-files && git ls-files -o --exclude-standard) | grep -i {safe_pattern} | {head}"
                if pattern
                else f"(git ls-files && git ls-files -o --exclude-standard) | {head}"
            ),
            (
                f"fd --type f -i {safe_pattern} | {head}"
                if pattern
                else f"fd --type f | {head}"
            ),
        ]

        for base_cmd in commands:
            cmd = ["sh", "-c", base_cmd]
            return_code, stdout, _ = await execute_bash_command(
                cmd, cwd=str(working_dir), timeout=1
            )
            if return_code == 0 and stdout:
                return [f for f in stdout.strip().split("\n") if f]

        return []

    @staticmethod
    async def _get_directories(
        working_dir: Path, limit: int | None = None, pattern: str = ""
    ) -> list[str]:
        """Get list of directories using git or fd."""
        head = f"head -n {limit}" if limit else "cat"

        safe_pattern = quote(pattern) if pattern else ""
        commands = [
            (
                f"(git ls-files -z && git ls-files -o --exclude-standard -z) | xargs -0 -n1 dirname | sort -u | grep -i {safe_pattern} | {head}"
                if pattern
                else f"(git ls-files -z && git ls-files -o --exclude-standard -z) | xargs -0 -n1 dirname | sort -u | {head}"
            ),
            (
                f"fd --type d -i -0 {safe_pattern} | tr '\\0' '\\n' | {head}"
                if pattern
                else f"fd --type d -0 | tr '\\0' '\\n' | {head}"
            ),
        ]

        for base_cmd in commands:
            cmd = ["sh", "-c", base_cmd]
            return_code, stdout, _ = await execute_bash_command(
                cmd, cwd=str(working_dir), timeout=1
            )
            if return_code == 0 and stdout:
                return [f for f in stdout.strip().split("\n") if f and f != "."]

        return []

    def resolve(self, ref: str, ctx: dict) -> str:
        """Resolve file reference to an absolute path."""
        working_dir = ctx.get("working_dir", "")
        try:
            resolved = resolve_path(str(working_dir), ref)
            return str(resolved)
        except Exception:
            return ref

    async def complete(self, fragment: str, ctx: dict, limit: int) -> list[Completion]:
        """Get file completions."""
        completions: list[Completion] = []
        working_dir = Path(ctx.get("working_dir", ""))

        try:
            files = await self._get_files(working_dir, limit=limit, pattern=fragment)
            directories = await self._get_directories(
                working_dir, limit=limit, pattern=fragment
            )

            directory_set = set(directories)

            def sort_key(path: str):
                parent = str(Path(path).parent) if "/" in path else ""
                return parent, path not in directory_set, path

            all_candidates = sorted(files + directories, key=sort_key)
            start_position = ctx.get("start_position", 0)

            for candidate in all_candidates:
                is_dir = candidate in directory_set
                display_text = f"@:file:{candidate}{'/' if is_dir else ''}"
                completion_text = f"@:file:{candidate}"

                completions.append(
                    Completion(
                        completion_text,
                        start_position=start_position,
                        display=display_text,
                        style=(
                            "class:dir-completion"
                            if is_dir
                            else "class:file-completion"
                        ),
                    )
                )

        except Exception:
            pass

        return completions
