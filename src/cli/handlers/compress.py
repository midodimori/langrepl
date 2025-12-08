"""Compression handling for chat sessions."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import cast

from langchain_core.runnables import RunnableConfig

from src.agents.context import AgentContext
from src.cli.bootstrap.initializer import initializer
from src.cli.theme import console, theme
from src.core.config import CompressionConfig
from src.core.constants import OS_VERSION, PLATFORM
from src.core.logging import get_logger
from src.utils.compression import calculate_message_tokens, compress_messages
from src.utils.cost import format_tokens

logger = get_logger(__name__)


class CompressionHandler:
    """Handles conversation history compression."""

    def __init__(self, session) -> None:
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
            prompt_str = compression_config.prompt

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

                compression_llm_config = compression_config.llm or agent_config.llm
                compression_llm = initializer.llm_factory.create(compression_llm_config)
                now = datetime.now(timezone.utc).astimezone()
                user_memory = await initializer.load_user_memory(ctx.working_dir)
                agent_context = AgentContext(
                    approval_mode=ctx.approval_mode,
                    working_dir=ctx.working_dir,
                    platform=PLATFORM,
                    os_version=OS_VERSION,
                    current_date_time_zoned=now.strftime("%Y-%m-%d %H:%M:%S %Z"),
                    user_memory=user_memory,
                    input_cost_per_mtok=ctx.input_cost_per_mtok,
                    output_cost_per_mtok=ctx.output_cost_per_mtok,
                    tool_output_max_tokens=ctx.tool_output_max_tokens,
                )

                original_count = len(messages)
                original_tokens = calculate_message_tokens(messages, compression_llm)

                with console.console.status(
                    f"[{theme.spinner_color}]Compressing {original_count} messages ({format_tokens(original_tokens)} tokens)..."
                ):
                    compressed_messages = await compress_messages(
                        messages,
                        compression_llm,
                        messages_to_keep=compression_config.messages_to_keep,
                        prompt=cast(str, prompt_str),
                        prompt_vars=agent_context.template_vars,
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
