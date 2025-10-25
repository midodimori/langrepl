import os
from typing import Annotated
from urllib.parse import urlparse

import trafilatura
import trafilatura.downloads
from langchain_core.messages import ToolMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import InjectedToolCallId

from src.cli.theme import theme
from src.core.settings import settings
from src.tools.wrapper import approval_tool, create_field_transformer


def _extract_host_from_url(url: str) -> str:
    """Extract the host/domain from a URL for approval matching."""
    try:
        return urlparse(url).netloc
    except Exception:
        return url


def _render_url_args(args: dict, config: RunnableConfig) -> str:
    """Render URL arguments with syntax highlighting."""
    url = args.get("url", "")
    return f"[{theme.tool_color}]{url}[/{theme.tool_color}]"


@approval_tool(
    format_args_fn=create_field_transformer({"url": _extract_host_from_url}),
    render_args_fn=_render_url_args,
)
async def fetch_web_content(
    config: RunnableConfig,
    tool_call_id: Annotated[str, InjectedToolCallId],
    url: Annotated[str, "The URL of the webpage to fetch."],
) -> ToolMessage | str:
    """
    Use this tool to fetch the main content of a webpage and return it as markdown.

    Args:
        url (str): The URL of the webpage to fetch
    """
    http_proxy = settings.llm.http_proxy.get_secret_value()
    https_proxy = settings.llm.https_proxy.get_secret_value()

    if http_proxy:
        os.environ["http_proxy"] = http_proxy
        trafilatura.downloads.PROXY_URL = http_proxy
    if https_proxy:
        os.environ["https_proxy"] = https_proxy

    downloaded = trafilatura.fetch_url(url)

    content = trafilatura.extract(downloaded, output_format="markdown")
    if not content:
        return f"No main content could be extracted from {url}"

    domain = urlparse(url).netloc
    short_content = f"Fetched content from {domain}"

    return ToolMessage(
        name=fetch_web_content.name,
        content=content,
        tool_call_id=tool_call_id,
        short_content=short_content,
    )


# Export all tools for the factory
WEB_TOOLS = [
    fetch_web_content,
]
