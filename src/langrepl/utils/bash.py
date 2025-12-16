import asyncio


async def execute_bash_command(
    command: list[str], cwd: str | None = None, timeout: int | None = None
) -> tuple[int, str, str]:
    process = None
    try:
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
        )
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
        return (
            process.returncode or 0,
            stdout.decode("utf-8", errors="replace"),
            stderr.decode("utf-8", errors="replace"),
        )

    except TimeoutError:
        if process and process.returncode is None:
            process.kill()
            await process.wait()
        return -1, "", "Command timed out"
    except Exception as e:
        return -1, "", str(e)
