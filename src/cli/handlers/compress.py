"""Compression handling for chat sessions."""

import uuid

from langchain_core.runnables import RunnableConfig

from src.cli.bootstrap.initializer import initializer
from src.cli.theme import console, theme
from src.core.config import CompressionConfig
from src.core.logging import get_logger
from src.utils.compression import calculate_message_tokens, compress_messages
from src.utils.cost import format_tokens

logger = get_logger(__name__)


class CompressionHandler:
    """Handles conversation history compression."""

    def __init__(self, session):
        """Initialize with reference to CLI session."""
        self.session = session

    async def handle(self) -> None:
        """Compress current conversation history and create new thread."""
        try:
            ctx = self.session.context
            config_data = await initializer.load_agents_config(ctx.working_dir)
            agent_config = config_data.get_agent_config(ctx.agent)

            if not agent_config:
                console.print_error(f"Agent '{ctx.agent}' not found")
                console.print("")
                return

            compression_config = agent_config.compression or CompressionConfig()

            async with initializer.get_checkpointer(
                ctx.agent, ctx.working_dir
            ) as checkpointer:
                config = RunnableConfig(configurable={"thread_id": ctx.thread_id})

                latest_checkpoint = await checkpointer.aget_tuple(config)
                if not latest_checkpoint or not latest_checkpoint.checkpoint:
                    console.print_error("No conversation history found to compress")
                    console.print("")
                    return

                channel_values = latest_checkpoint.checkpoint.get("channel_values", {})
                messages = channel_values.get("messages", [])

                if not messages:
                    console.print_error("No messages found in conversation history")
                    console.print("")
                    return

                compression_llm_config = (
                    compression_config.compression_llm or agent_config.llm
                )
                compression_llm = initializer.llm_factory.create(compression_llm_config)

                original_count = len(messages)
                original_tokens = calculate_message_tokens(messages, compression_llm)

                with console.console.status(
                    f"[{theme.spinner_color}]Compressing {original_count} messages ({format_tokens(original_tokens)} tokens)..."
                ):
                    compressed_messages = await compress_messages(
                        messages,
                        compression_llm,
                    )

                    compressed_tokens = calculate_message_tokens(
                        compressed_messages, compression_llm
                    )

                new_thread_id = str(uuid.uuid4())

                new_config = RunnableConfig(
                    configurable={
                        "thread_id": new_thread_id,
                        "checkpoint_ns": "",
                    }
                )

                await self.session.graph.aupdate_state(
                    new_config, {"messages": compressed_messages}
                )

                # Update context first
                self.session.update_context(
                    thread_id=new_thread_id,
                    current_input_tokens=compressed_tokens,
                    current_output_tokens=0,
                    total_cost=0.0,
                )

                # Render the compressed messages
                for message in compressed_messages:
                    self.session.renderer.render_message(message)

        except Exception as e:
            console.print_error(f"Error compressing conversation: {e}")
            console.print("")
            logger.debug("Compression error", exc_info=True)
