"""OAuth provider factory for MCP servers."""

from __future__ import annotations

import webbrowser
from pathlib import Path

from mcp.client.auth import OAuthClientProvider
from mcp.shared.auth import OAuthClientMetadata
from pydantic import AnyUrl

from langrepl.core.logging import get_logger
from langrepl.mcp.oauth.callback import OAuthCallbackServer
from langrepl.mcp.oauth.storage import FileTokenStorage

logger = get_logger(__name__)


async def create_oauth_provider(
    server_name: str,
    server_url: str,
    oauth_dir: Path,
    client_name: str = "langrepl",
) -> OAuthClientProvider:
    """Create an OAuthClientProvider for an MCP server.

    The provider is lazy - it only triggers the OAuth flow when the
    server returns a 401 Unauthorized response.

    Args:
        server_name: Name of the MCP server (used for token storage directory).
        server_url: URL of the MCP server.
        oauth_dir: Base directory for OAuth token storage.
        client_name: Client name for OAuth registration.

    Returns:
        Configured OAuthClientProvider instance.
    """
    storage = FileTokenStorage(oauth_dir, server_name)
    callback_server = OAuthCallbackServer()

    # Register all possible redirect URIs to handle port fallback
    client_metadata = OAuthClientMetadata(
        client_name=client_name,
        redirect_uris=[
            AnyUrl(uri) for uri in callback_server.get_possible_redirect_uris()
        ],
        grant_types=["authorization_code", "refresh_token"],
        response_types=["code"],
    )

    async def redirect_handler(authorization_url: str) -> None:
        """Open authorization URL in browser."""
        if not callback_server.is_running:
            logger.info("Starting OAuth callback server...")
            await callback_server.start()
        logger.info("Opening browser for OAuth authentication...")
        try:
            opened = webbrowser.open(authorization_url)
            if not opened:
                logger.warning(
                    "Could not open browser automatically. "
                    "Please open this URL manually:\n%s",
                    authorization_url,
                )
        except Exception as e:
            logger.warning(
                "Failed to open browser: %s\n" "Please open this URL manually:\n%s",
                e,
                authorization_url,
            )

    async def callback_handler() -> tuple[str, str | None]:
        """Wait for OAuth callback and return (code, state)."""
        try:
            return await callback_server.wait_for_callback()
        finally:
            await callback_server.stop()

    return OAuthClientProvider(
        server_url=server_url,
        client_metadata=client_metadata,
        storage=storage,
        redirect_handler=redirect_handler,
        callback_handler=callback_handler,
        timeout=300.0,
    )
