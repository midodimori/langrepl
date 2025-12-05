"""Context compression utilities for managing conversation history."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, cast

import tiktoken
from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, merge_content

from src.utils.render import render_templates

if TYPE_CHECKING:
    from langchain_core.language_models import BaseChatModel


def calculate_message_tokens(
    messages: Sequence[AnyMessage],
    llm: BaseChatModel,
) -> int:
    """Calculate token count using the LLM's tokenizer with fallback support.

    Args:
        messages: List of messages to count
        llm: Language model to use for token counting

    Returns:
        Token count

    Notes:
        Falls back to tiktoken cl100k_base encoding if model doesn't support
        token counting. Final fallback uses character-based estimation (4 chars per token).
    """
    try:
        cleaned_messages = [
            msg.model_copy(update={"content": msg.text}) for msg in messages
        ]
        return llm.get_num_tokens_from_messages(list(cleaned_messages))
    except (NotImplementedError, ImportError):
        # Fallback to tiktoken with cl100k_base encoding (used by GPT-4, GPT-3.5-turbo)
        try:
            encoding = tiktoken.get_encoding("cl100k_base")
            # Extract text content from messages using .text() method
            content = " ".join(msg.text for msg in messages)
            return len(encoding.encode(content))
        except Exception:
            # Final fallback: estimate using character count
            content = " ".join(msg.text for msg in messages)
            return len(content) // 4


def should_auto_compress(
    current_tokens: int,
    context_window: int | None,
    threshold: float,
) -> bool:
    """Check if auto-compression should be triggered.

    Args:
        current_tokens: Current token count in context
        context_window: Maximum context window size
        threshold: Threshold percentage (0.0-1.0)

    Returns:
        True if compression should be triggered
    """
    if context_window is None or context_window <= 0:
        return False

    usage_ratio = current_tokens / context_window
    return usage_ratio >= threshold


async def compress_messages(
    messages: Sequence[AnyMessage],
    compression_llm: BaseChatModel,
    messages_to_keep: int = 0,
    prompt: str | None = None,
    prompt_vars: dict[str, Any] | None = None,
) -> list[AnyMessage]:
    """Compress message history into a single summary.

    Strategy:
    - Preserve system messages (always first)
    - Summarize all other messages using LLM

    Args:
        messages: Full message history
        compression_llm: LLM to use for summarization
        messages_to_keep: Number of recent messages to preserve verbatim (default: 0)
        prompt: Custom prompt template for summarization
        prompt_vars: Additional variables for prompt template rendering

    Returns:
        Compressed message list with system messages + summary
    """
    if not messages:
        return []

    system_messages: list[AnyMessage] = []
    other_messages: list[AnyMessage] = []

    for msg in messages:
        if msg.type == "system":
            system_messages.append(msg)
        else:
            other_messages.append(msg)

    if not other_messages:
        return list(messages)

    keep_count = max(messages_to_keep, 0)
    preserved_tail: list[AnyMessage] = []
    summarize_candidates = list(other_messages)

    if keep_count:
        preserved_tail = summarize_candidates[-keep_count:]
        summarize_candidates = summarize_candidates[:-keep_count]

    if not summarize_candidates:
        return system_messages + preserved_tail

    summary_message = await _summarize_messages(
        summarize_candidates,
        compression_llm,
        prompt=prompt,
        prompt_vars=prompt_vars,
    )

    compressed: list[AnyMessage] = [*system_messages, summary_message, *preserved_tail]

    return compressed


async def _summarize_messages(
    messages: Sequence[AnyMessage],
    compression_llm: BaseChatModel,
    prompt: str | None = None,
    prompt_vars: dict[str, Any] | None = None,
) -> AIMessage:
    """Summarize a list of messages using LLM.

    Args:
        messages: Messages to summarize
        compression_llm: LLM to use for summarization

    Returns:
        Summary message
    """
    conversation_text = _format_messages_for_summary(messages)
    prompt_template = prompt or "Summarize the conversation.\n\n{conversation}"
    if "{conversation}" not in prompt_template:
        prompt_template = (
            f"{prompt_template}\n\nConversation:\n{{conversation}}\n\n"
            "Provide a concise summary (2-4 paragraphs):"
        )
    render_context = {**(prompt_vars or {}), "conversation": conversation_text}
    rendered_prompt = str(render_templates(prompt_template, render_context))

    response = await compression_llm.ainvoke([HumanMessage(content=rendered_prompt)])
    ai_response = cast(AIMessage, response)
    ai_response.content = merge_content(
        "# Previous conversation summary\n\n", ai_response.content
    )
    ai_response.name = "compression_summary"
    return ai_response


def _format_messages_for_summary(messages: Sequence[AnyMessage]) -> str:
    """Format messages into readable text for summarization.

    Args:
        messages: Messages to format

    Returns:
        Formatted conversation text
    """
    lines = []

    for msg in messages:
        role = msg.type.capitalize()
        content = str(msg.text)
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            tool_calls_str = ", ".join(tc["name"] for tc in msg.tool_calls)
            content += f" [Tool calls: {tool_calls_str}]"

        lines.append(f"{role}: {content}")

    return "\n".join(lines)
