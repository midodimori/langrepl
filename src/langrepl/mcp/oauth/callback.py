"""Local HTTP server for OAuth callback handling."""

from __future__ import annotations

import asyncio
import socket
from urllib.parse import parse_qs, urlparse

from langrepl.core.logging import get_logger

logger = get_logger(__name__)


class OAuthCallbackServer:
    """Minimal HTTP server to receive OAuth authorization callbacks.

    Listens on localhost for a single OAuth callback, extracts the
    authorization code and state, then shuts down automatically.
    """

    def __init__(self, port_range: tuple[int, int] = (18080, 18099)) -> None:
        self._port_range = port_range
        self._port: int | None = None
        self._server: asyncio.Server | None = None
        self._result: asyncio.Future[tuple[str, str | None]] | None = None

    @property
    def port(self) -> int:
        """Get the port the server is listening on."""
        if self._port is None:
            raise RuntimeError("Server not started")
        return self._port

    @property
    def is_running(self) -> bool:
        """Check if the server is currently running."""
        return self._server is not None

    @property
    def redirect_uri(self) -> str:
        """Get the redirect URI for OAuth configuration."""
        return f"http://localhost:{self.port}/oauth/callback"

    def get_possible_redirect_uris(self) -> list[str]:
        """Get all possible redirect URIs for the port range."""
        return [
            f"http://localhost:{port}/oauth/callback"
            for port in range(self._port_range[0], self._port_range[1] + 1)
        ]

    async def start(self) -> int:
        """Start the callback server on an available port.

        Returns:
            The port number the server is listening on.
        """
        self._result = asyncio.get_running_loop().create_future()

        for port in range(self._port_range[0], self._port_range[1] + 1):
            try:
                self._server = await asyncio.start_server(
                    self._handle_connection,
                    host="127.0.0.1",
                    port=port,
                    family=socket.AF_INET,
                )
                self._port = port
                logger.debug("OAuth callback server started on port %d", port)
                return port
            except OSError:
                continue

        raise RuntimeError(
            f"Could not bind to any port in range {self._port_range[0]}-{self._port_range[1]}"
        )

    async def wait_for_callback(self) -> tuple[str, str | None]:
        """Wait for the OAuth callback and return (code, state).

        Returns:
            Tuple of (authorization_code, state).
            State may be None if not provided by the OAuth server.
        """
        if self._result is None:
            raise RuntimeError("Server not started")
        return await self._result

    async def stop(self) -> None:
        """Stop the callback server."""
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
            self._port = None
            logger.debug("OAuth callback server stopped")

    async def _handle_connection(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        """Handle incoming HTTP connection."""
        try:
            # Read the HTTP request
            request_line = await reader.readline()
            if not request_line:
                return

            # Consume the rest of the headers
            while True:
                header = await reader.readline()
                if not header or header == b"\r\n":
                    break

            # Parse request line: GET /oauth/callback?code=...&state=... HTTP/1.1
            parts = request_line.decode("utf-8").strip().split(" ")
            if len(parts) < 2:
                return

            method, path = parts[0], parts[1]
            if method != "GET":
                await self._send_response(writer, 405, "Method Not Allowed")
                return

            # Parse the URL and query parameters
            parsed = urlparse(path)
            if not parsed.path.endswith("/oauth/callback"):
                await self._send_response(writer, 404, "Not Found")
                return

            query = parse_qs(parsed.query)
            code = query.get("code", [None])[0]
            state = query.get("state", [None])[0]
            error = query.get("error", [None])[0]

            if error:
                error_desc = query.get("error_description", [error])[0]
                await self._send_response(
                    writer,
                    400,
                    f"<h1>Authentication Failed</h1><p>{error_desc}</p>",
                    content_type="text/html",
                )
                if self._result and not self._result.done():
                    self._result.set_exception(
                        RuntimeError(f"OAuth error: {error_desc}")
                    )
                return

            if not code:
                await self._send_response(
                    writer,
                    400,
                    "<h1>Missing Authorization Code</h1>",
                    content_type="text/html",
                )
                return

            # Success response
            await self._send_response(
                writer,
                200,
                "<h1>Authentication Successful</h1>"
                "<p>You can close this window and return to the terminal.</p>",
                content_type="text/html",
            )

            # Set the result
            if self._result and not self._result.done():
                self._result.set_result((code, state))

        except Exception as e:
            logger.error("Error handling OAuth callback: %s", e)
            if self._result and not self._result.done():
                self._result.set_exception(e)
        finally:
            writer.close()
            await writer.wait_closed()

    async def _send_response(
        self,
        writer: asyncio.StreamWriter,
        status: int,
        body: str,
        content_type: str = "text/plain",
    ) -> None:
        """Send an HTTP response."""
        status_text = {
            200: "OK",
            400: "Bad Request",
            404: "Not Found",
            405: "Method Not Allowed",
        }
        response = (
            f"HTTP/1.1 {status} {status_text.get(status, 'Unknown')}\r\n"
            f"Content-Type: {content_type}\r\n"
            f"Content-Length: {len(body)}\r\n"
            "Connection: close\r\n"
            "\r\n"
            f"{body}"
        )
        writer.write(response.encode("utf-8"))
        await writer.drain()
