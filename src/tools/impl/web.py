import os
from urllib.parse import urlparse

import trafilatura
import trafilatura.downloads
from langchain.tools import ToolRuntime, tool
from langchain_core.messages import ToolMessage

from src.agents.context import AgentContext
from src.cli.theme import theme
from src.core.settings import settings
from src.middleware.approval import create_field_transformer


def _extract_host_from_url(url: str) -> str:
    """Extract the host/domain from a URL for approval matching."""
    try:
        return urlparse(url).netloc
    except Exception:
        return url


def _render_url_args(args: dict, config: dict) -> str:
    """Render URL arguments with syntax highlighting."""
    url = args.get("url", "")
    return f"[{theme.indicator_color}]{url}[/{theme.indicator_color}]"


@tool
async def fetch_web_content(
    url: str,
    runtime: ToolRuntime[AgentContext],
) -> ToolMessage | str:
    """
    Use this tool to fetch the main content of a webpage and return it as markdown.

    Args:
        url: The URL of the webpage to fetch
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
        tool_call_id=runtime.tool_call_id,
        short_content=short_content,
    )


fetch_web_content.metadata = {
    "approval_config": {
        "format_args_fn": create_field_transformer({"url": _extract_host_from_url}),
        "render_args_fn": _render_url_args,
    }
}


WEB_TOOLS = [
    fetch_web_content,
]
