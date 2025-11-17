"""Graph visualization for LangGraph agents."""

import tempfile
import webbrowser
from pathlib import Path

from src.cli.theme import console
from src.core.logging import get_logger

logger = get_logger(__name__)


class GraphHandler:
    """Handles graph visualization operations."""

    def __init__(self, session):
        """Initialize with reference to CLI session."""
        self.session = session

    async def handle(self, open_browser: bool = False) -> None:
        """Render and display the current LangGraph graph.

        Args:
            open_browser: If True, render as PNG and open in browser.
                         If False (default), render as Mermaid text in terminal.
        """
        if not self.session.graph:
            console.print_error(
                "No graph available. Please start a conversation first."
            )
            console.print("")
            return

        try:
            # Try to get the drawable graph
            drawable_graph = self.session.graph.get_graph()

            if open_browser:
                # Try to render PNG and open in browser
                success = await self._try_render_png(drawable_graph)
                if not success:
                    console.print_error(
                        "Failed to render PNG. Falling back to terminal output."
                    )
                    console.print("")
                    self.session.renderer.render_graph(drawable_graph)
            else:
                # Default: render in terminal
                self.session.renderer.render_graph(drawable_graph)

        except Exception as e:
            console.print_error(f"Error rendering graph: {e}")
            console.print("")
            logger.debug("Graph rendering error", exc_info=True)

    async def _try_render_png(self, drawable_graph) -> bool:
        """Try to render graph as PNG and open in browser.

        Args:
            drawable_graph: The drawable graph from get_graph()

        Returns:
            True if successful, False otherwise
        """
        try:
            # Try to generate PNG using draw_mermaid_png()
            png_data = drawable_graph.draw_mermaid_png()

            # Save to temporary file
            with tempfile.NamedTemporaryFile(
                mode="wb", suffix=".png", delete=False
            ) as f:
                f.write(png_data)
                temp_path = f.name

            # Try to open in default image viewer
            temp_file = Path(temp_path)

            # Create an HTML wrapper for better viewing
            html_path = temp_file.with_suffix(".html")
            html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>LangGraph Visualization - {self.session.context.agent}</title>
    <style>
        body {{
            margin: 0;
            padding: 20px;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            background-color: #1e1e1e;
        }}
        img {{
            max-width: 100%;
            height: auto;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
        }}
    </style>
</head>
<body>
    <img src="file://{temp_file.absolute()}" alt="LangGraph Visualization">
</body>
</html>
"""
            html_path.write_text(html_content)

            # Open in browser
            webbrowser.open(f"file://{html_path.absolute()}")

            console.print_success("Graph visualization opened in browser")
            console.print(f"[muted]PNG saved to: {temp_file}[/muted]", markup=True)
            console.print("")
            return True

        except ImportError as e:
            logger.debug(f"PNG rendering failed due to missing dependency: {e}")
            return False
        except Exception as e:
            logger.debug(f"PNG rendering failed: {e}")
            return False
