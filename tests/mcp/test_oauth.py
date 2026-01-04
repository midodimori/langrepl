"""Tests for MCP OAuth module - critical paths only."""

import asyncio
import stat
from pathlib import Path

import pytest
from mcp.shared.auth import OAuthToken

from langrepl.mcp.oauth.callback import OAuthCallbackServer
from langrepl.mcp.oauth.storage import FileTokenStorage


class TestOAuthCallbackServer:
    @pytest.mark.asyncio
    async def test_callback_receives_code_and_state(self):
        """Test HTTP callback correctly parses authorization code and state."""
        server = OAuthCallbackServer(port_range=(19030, 19035))
        port = await server.start()

        async def send_callback():
            await asyncio.sleep(0.05)
            reader, writer = await asyncio.open_connection("127.0.0.1", port)
            request = "GET /oauth/callback?code=test_code&state=test_state HTTP/1.1\r\nHost: localhost\r\n\r\n"
            writer.write(request.encode())
            await writer.drain()
            await reader.read(1024)
            writer.close()
            await writer.wait_closed()

        try:
            callback_task = asyncio.create_task(send_callback())
            code, state = await asyncio.wait_for(
                server.wait_for_callback(), timeout=2.0
            )
            await callback_task
            assert code == "test_code"
            assert state == "test_state"
        finally:
            await server.stop()

    @pytest.mark.asyncio
    async def test_callback_handles_error_response(self):
        """Test OAuth error responses are properly propagated."""
        server = OAuthCallbackServer(port_range=(19040, 19045))
        port = await server.start()

        async def send_error_callback():
            await asyncio.sleep(0.05)
            reader, writer = await asyncio.open_connection("127.0.0.1", port)
            request = "GET /oauth/callback?error=access_denied&error_description=User+denied HTTP/1.1\r\nHost: localhost\r\n\r\n"
            writer.write(request.encode())
            await writer.drain()
            await reader.read(1024)
            writer.close()
            await writer.wait_closed()

        try:
            callback_task = asyncio.create_task(send_error_callback())
            with pytest.raises(RuntimeError, match="OAuth error"):
                await asyncio.wait_for(server.wait_for_callback(), timeout=2.0)
            await callback_task
        finally:
            await server.stop()


class TestFileTokenStorage:
    @pytest.mark.asyncio
    async def test_token_file_has_restrictive_permissions(self, tmp_path: Path):
        """Test token files are created with 600 permissions (security-critical)."""
        storage = FileTokenStorage(tmp_path, "test_server")
        token = OAuthToken(access_token="secret", token_type="Bearer")

        await storage.set_tokens(token)

        token_path = tmp_path / "test_server" / "tokens.json"
        mode = token_path.stat().st_mode
        assert mode & 0o777 == stat.S_IRUSR | stat.S_IWUSR  # 0o600
