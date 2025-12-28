"""Integration tests for sandbox policy boundaries."""

from __future__ import annotations

import os
import shlex
import socket
import sys
import tempfile
import threading
from collections.abc import Iterable
from pathlib import Path

import pytest

import langrepl
from langrepl.agents.context import AgentContext
from langrepl.configs import ApprovalMode
from langrepl.configs.sandbox import (
    FilesystemConfig,
    NetworkConfig,
    SandboxConfig,
    SandboxOS,
    SandboxType,
)
from langrepl.core.constants import PLATFORM
from langrepl.sandboxes.factory import SandboxFactory

TOOL_MODULE = "langrepl.tools.impl.terminal"
TOOL_NAME = "run_command"


def _sandbox_type() -> tuple[SandboxType, SandboxOS]:
    if PLATFORM == "Darwin":
        return SandboxType.SEATBELT, SandboxOS.MACOS
    if PLATFORM == "Linux":
        return SandboxType.BUBBLEWRAP, SandboxOS.LINUX
    pytest.skip(f"Unsupported platform: {PLATFORM}")


def _sandbox_config(
    name: str,
    read: Iterable[str],
    write: Iterable[str],
    hidden: Iterable[str] | None = None,
    remote: Iterable[str] | None = None,
    local: Iterable[str] | None = None,
) -> SandboxConfig:
    sandbox_type, sandbox_os = _sandbox_type()
    return SandboxConfig(
        name=name,
        type=sandbox_type,
        os=sandbox_os,
        filesystem=FilesystemConfig(
            read=list(read),
            write=list(write),
            hidden=list(hidden or []),
        ),
        network=NetworkConfig(
            remote=list(remote or []),
            local=list(local or []),
        ),
    )


def _base_read_paths(include_dot: bool = True) -> list[str]:
    package_root = Path(langrepl.__file__).resolve().parent
    package_src = package_root.parent
    read_paths = [
        str(Path(sys.executable).parent),
        str(Path(sys.prefix)),
        str(Path(sys.base_prefix)),
        str(Path(sys.base_exec_prefix)),
        str(package_root),
        str(package_src),
        "/usr",
        "/System",
        "/Library",
        "/lib",
        "/lib64",
        "/opt",
        "/bin",
    ]
    if include_dot:
        read_paths.append(".")
    return read_paths


def _runtime(working_dir: Path) -> dict[str, object]:
    context = AgentContext(
        approval_mode=ApprovalMode.AGGRESSIVE, working_dir=working_dir
    )
    return {
        "tool_call_id": "test_call",
        "state": {"messages": []},
        "context": context.model_dump(mode="json"),
        "config": {"configurable": {}},
    }


async def _run_command(backend, working_dir: Path, command: str) -> dict:
    return await backend.execute(
        TOOL_MODULE, TOOL_NAME, {"command": command}, tool_runtime=_runtime(working_dir)
    )


def _backend(config: SandboxConfig, working_dir: Path):
    factory = SandboxFactory()
    try:
        return factory.create_backend(config, working_dir)
    except RuntimeError as exc:
        pytest.skip(str(exc))


def _python_command(script: str) -> str:
    return f"{shlex.quote(sys.executable)} -c {shlex.quote(script)}"


def _read_script(path: Path) -> str:
    return (
        "import sys\n"
        f"p={str(path)!r}\n"
        "try:\n"
        "    open(p, 'rb').read()\n"
        "except Exception as e:\n"
        "    print(e)\n"
        "    sys.exit(2)\n"
    )


def _write_script(path: Path, content: str = "ok") -> str:
    return (
        "import sys\n"
        f"p={str(path)!r}\n"
        f"data={content!r}\n"
        "try:\n"
        "    with open(p, 'w', encoding='utf-8') as f:\n"
        "        f.write(data)\n"
        "except Exception as e:\n"
        "    print(e)\n"
        "    sys.exit(2)\n"
    )


def _start_tcp_server() -> tuple[socket.socket, int, threading.Event]:
    ready = threading.Event()

    def _serve(sock: socket.socket) -> None:
        ready.set()
        conn, _ = sock.accept()
        with conn:
            conn.recv(16)
            conn.sendall(b"ok")

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    port = server.getsockname()[1]

    thread = threading.Thread(target=_serve, args=(server,), daemon=True)
    thread.start()
    ready.wait(timeout=2)
    return server, port, ready


@pytest.mark.asyncio
async def test_sandbox_read_write_allowlist(temp_dir: Path):
    allowed_file = temp_dir / "allowed.txt"
    allowed_file.write_text("hello", encoding="utf-8")

    with tempfile.TemporaryDirectory() as other_tmp:
        denied_file = Path(other_tmp) / "denied.txt"
        denied_file.write_text("nope", encoding="utf-8")

        config = _sandbox_config(
            name="allowlist-test",
            read=_base_read_paths(include_dot=True),
            write=["."],
        )
        backend = _backend(config, temp_dir)

        read_ok = await _run_command(
            backend, temp_dir, _python_command(_read_script(allowed_file))
        )
        assert read_ok["success"]

        read_denied = await _run_command(
            backend, temp_dir, _python_command(_read_script(denied_file))
        )
        assert not read_denied["success"]

        write_ok = await _run_command(
            backend, temp_dir, _python_command(_write_script(temp_dir / "write.txt"))
        )
        assert write_ok["success"]

        write_denied = await _run_command(
            backend, temp_dir, _python_command(_write_script(denied_file))
        )
        assert not write_denied["success"]


@pytest.mark.asyncio
async def test_sandbox_working_dir_requires_dot(temp_dir: Path):
    target = temp_dir / "wd.txt"
    target.write_text("hi", encoding="utf-8")

    config = _sandbox_config(
        name="no-dot",
        read=_base_read_paths(include_dot=False) + [os.getcwd()],
        write=[],
    )
    backend = _backend(config, temp_dir)

    result = await _run_command(
        backend, temp_dir, _python_command(_read_script(target))
    )
    assert not result["success"]


@pytest.mark.asyncio
async def test_sandbox_hidden_overrides_allow(temp_dir: Path):
    secret = temp_dir / "secret.txt"
    secret.write_text("shh", encoding="utf-8")

    config = _sandbox_config(
        name="hidden-test",
        read=_base_read_paths(include_dot=True),
        write=["."],
        hidden=["**/secret.txt"],
    )
    backend = _backend(config, temp_dir)

    result = await _run_command(
        backend, temp_dir, _python_command(_read_script(secret))
    )
    assert not result["success"]


@pytest.mark.asyncio
async def test_sandbox_symlink_escape_blocked(temp_dir: Path):
    with tempfile.TemporaryDirectory() as other_tmp:
        outside_dir = Path(other_tmp)
        outside_file = outside_dir / "outside.txt"
        outside_file.write_text("nope", encoding="utf-8")

        link_path = temp_dir / "link"
        if link_path.exists() or link_path.is_symlink():
            link_path.unlink()
        link_path.symlink_to(outside_dir, target_is_directory=True)

        config = _sandbox_config(
            name="symlink-test",
            read=_base_read_paths(include_dot=False) + [str(link_path), os.getcwd()],
            write=[],
        )
        backend = _backend(config, temp_dir)

        result = await _run_command(
            backend, temp_dir, _python_command(_read_script(link_path / "outside.txt"))
        )
        assert not result["success"]


@pytest.mark.asyncio
async def test_sandbox_exec_requires_read(temp_dir: Path):
    allowed_script = temp_dir / "allowed.sh"
    allowed_script.write_text("#!/bin/sh\necho ok\n", encoding="utf-8")
    allowed_script.chmod(0o755)

    with tempfile.TemporaryDirectory() as other_tmp:
        denied_script = Path(other_tmp) / "denied.sh"
        denied_script.write_text("#!/bin/sh\necho nope\n", encoding="utf-8")
        denied_script.chmod(0o755)

        config = _sandbox_config(
            name="exec-test",
            read=_base_read_paths(include_dot=True),
            write=["."],
        )
        backend = _backend(config, temp_dir)

        ok = await _run_command(backend, temp_dir, shlex.quote(str(allowed_script)))
        assert ok["success"]

        denied = await _run_command(backend, temp_dir, shlex.quote(str(denied_script)))
        assert not denied["success"]


@pytest.mark.asyncio
async def test_sandbox_network_allowlist(temp_dir: Path):
    server, port, _ = _start_tcp_server()
    script = (
        "import socket, sys\n"
        f"addr=('127.0.0.1',{port})\n"
        "try:\n"
        "    s=socket.socket()\n"
        "    s.settimeout(2)\n"
        "    s.connect(addr)\n"
        "    s.sendall(b'ping')\n"
        "    data=s.recv(2)\n"
        "    s.close()\n"
        "    print(data.decode())\n"
        "except Exception as e:\n"
        "    print(e)\n"
        "    sys.exit(2)\n"
    )
    try:
        allow_config = _sandbox_config(
            name="net-allow",
            read=_base_read_paths(include_dot=True),
            write=["."],
            remote=["*"],
        )
        allow_backend = _backend(allow_config, temp_dir)
        allow_result = await _run_command(
            allow_backend, temp_dir, _python_command(script)
        )
        assert allow_result["success"]

        deny_config = _sandbox_config(
            name="net-deny",
            read=_base_read_paths(include_dot=True),
            write=["."],
            remote=[],
        )
        deny_backend = _backend(deny_config, temp_dir)
        deny_result = await _run_command(
            deny_backend, temp_dir, _python_command(script)
        )
        assert not deny_result["success"]
    finally:
        server.close()


@pytest.mark.asyncio
async def test_sandbox_hidden_absolute_path(temp_dir: Path):
    """Hidden absolute path should block access."""
    secret_dir = temp_dir / ".secret"
    secret_dir.mkdir()
    secret_file = secret_dir / "data.txt"
    secret_file.write_text("secret", encoding="utf-8")

    # Use resolved path for hidden - Seatbelt operates on resolved paths
    config = _sandbox_config(
        name="hidden-absolute",
        read=_base_read_paths(include_dot=True),
        write=["."],
        hidden=[str(secret_dir.resolve())],
    )
    backend = _backend(config, temp_dir)

    result = await _run_command(
        backend, temp_dir, _python_command(_read_script(secret_file))
    )
    assert not result["success"]


@pytest.mark.asyncio
async def test_sandbox_write_to_readonly_blocked(temp_dir: Path):
    """Writing to a read-only configured path should fail."""
    readonly_dir = temp_dir / "readonly"
    readonly_dir.mkdir()

    config = _sandbox_config(
        name="readonly-test",
        read=_base_read_paths(include_dot=True),
        write=[],  # No write access
    )
    backend = _backend(config, temp_dir)

    target = readonly_dir / "file.txt"
    result = await _run_command(
        backend, temp_dir, _python_command(_write_script(target))
    )
    assert not result["success"]


@pytest.mark.asyncio
async def test_sandbox_timeout_kills_process(temp_dir: Path):
    """Long-running process should be killed after timeout."""
    sleep_script = "import time; time.sleep(30); print('done')"

    config = _sandbox_config(
        name="timeout-test",
        read=_base_read_paths(include_dot=True),
        write=["."],
    )
    backend = _backend(config, temp_dir)

    result = await backend.execute(
        TOOL_MODULE,
        TOOL_NAME,
        {"command": _python_command(sleep_script)},
        timeout=2.0,
        tool_runtime=_runtime(temp_dir),
    )

    assert not result["success"]
    assert "timed out" in result.get("error", "").lower()


@pytest.mark.asyncio
async def test_sandbox_env_isolation(temp_dir: Path):
    """Sensitive env vars should not leak to sandbox."""
    os.environ["TEST_SECRET_KEY"] = "super_secret_value"
    try:
        check_env_script = (
            "import os,sys\n"
            "val=os.environ.get('TEST_SECRET_KEY','')\n"
            "if val:\n"
            "    print(f'LEAKED:{val}')\n"
            "    sys.exit(2)\n"
            "print('OK')\n"
        )

        config = _sandbox_config(
            name="env-isolation",
            read=_base_read_paths(include_dot=True),
            write=["."],
        )
        backend = _backend(config, temp_dir)

        result = await _run_command(
            backend, temp_dir, _python_command(check_env_script)
        )
        assert result["success"]
    finally:
        del os.environ["TEST_SECRET_KEY"]


@pytest.mark.asyncio
async def test_sandbox_worker_module_validation(temp_dir: Path):
    """Only langrepl.tools.* modules should be loadable."""
    config = _sandbox_config(
        name="module-validation",
        read=_base_read_paths(include_dot=True),
        write=["."],
    )
    backend = _backend(config, temp_dir)

    result = await backend.execute(
        module_path="os.path",
        tool_name="join",
        args={},
        tool_runtime=_runtime(temp_dir),
    )

    assert not result["success"]
    assert "not in allowed prefix" in result.get("error", "").lower()
