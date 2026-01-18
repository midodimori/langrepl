"""Todo handler for displaying current task list."""

from langchain_core.runnables import RunnableConfig

from langrepl.cli.bootstrap.initializer import initializer
from langrepl.cli.theme import console
from langrepl.core.logging import get_logger
from langrepl.tools.internal.todo import format_todos

logger = get_logger(__name__)


class TodoHandler:
    """Handles todo list display."""

    def __init__(self, session) -> None:
        """Initialize with reference to CLI session."""
        self.session = session

    async def handle(self, max_items: int = 10) -> None:
        """Show current todo list."""
        try:
            async with initializer.get_checkpointer(
                self.session.context.agent, self.session.context.working_dir
            ) as checkpointer:
                config = RunnableConfig(
                    configurable={"thread_id": self.session.context.thread_id}
                )
                latest_checkpoint = await checkpointer.aget_tuple(config)

                if not latest_checkpoint or not latest_checkpoint.checkpoint:
                    console.print_error("No todos currently")
                    console.print("")
                    return

                channel_values = latest_checkpoint.checkpoint.get("channel_values", {})
                todos = channel_values.get("todos")

                if not todos:
                    console.print_error("No todos currently")
                    console.print("")
                    return

                formatted = format_todos(
                    todos,
                    max_items=max_items,
                    max_completed=max_items,
                    show_completed_indicator=False,
                )
                indented = "\n".join(f"  {line}" for line in formatted.split("\n"))
                console.print(indented, markup=True)
                console.print("")

        except Exception as e:
            console.print_error(f"Error displaying todos: {e}")
            console.print("")
            logger.debug("Todo display error", exc_info=True)
