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
    """
    Render the `url` entry from `args` wrapped in theme color markup for display.
    
    Parameters:
        args (dict): A mapping expected to contain the "url" key with the URL string to render.
        config (dict): Rendering configuration (not used by this implementation).
    
    Returns:
        highlighted_url (str): The URL wrapped in the theme's color markup (e.g., "[color]url[/color]").
    """
    url = args.get("url", "")
    return f"[{theme.tool_color}]{url}[/{theme.tool_color}]"


@tool
async def fetch_web_content(
    url: str,
    runtime: ToolRuntime[AgentContext],
) -> ToolMessage | str:
    """
    Fetches a webpage's main content and returns it as Markdown.
    
    Parameters:
        url (str): The URL of the webpage to fetch.
        runtime (ToolRuntime[AgentContext]): Tool runtime used to supply tool call metadata (e.g., `tool_call_id`).
    
    Returns:
        ToolMessage: A message containing the extracted Markdown content and metadata on success.
        str: An error message if no main content could be extracted from the URL.
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