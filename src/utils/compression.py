"""Context compression utilities for managing conversation history."""

from collections.abc import Sequence
from typing import cast

import tiktoken
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, AnyMessage, HumanMessage


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
) -> list[AnyMessage]:
    """Compress message history into a single summary.

    Strategy:
    - Preserve system messages (always first)
    - Summarize all other messages using LLM

    Args:
        messages: Full message history
        compression_llm: LLM to use for summarization

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

    summary_content = await _summarize_messages(other_messages, compression_llm)

    summary_message = AIMessage(
        content=f"[Previous conversation summary]\n{summary_content}",
        name="compression_summary",
    )

    compressed: list[AnyMessage] = system_messages + [summary_message]

    return compressed


async def _summarize_messages(
    messages: Sequence[AnyMessage],
    compression_llm: BaseChatModel,
) -> str:
    """Summarize a list of messages using LLM.

    Args:
        messages: Messages to summarize
        compression_llm: LLM to use for summarization

    Returns:
        Summary text
    """
    conversation_text = _format_messages_for_summary(messages)

    summarization_prompt = f"""Summarize the following conversation history concisely, preserving key information, decisions, and context that would be important for continuing the conversation. Focus on:
- Main topics discussed
- Important facts or data mentioned
- Decisions made or conclusions reached
- Technical details or specifications
- User preferences or requirements

Conversation:
{conversation_text}

Provide a concise summary (2-4 paragraphs):"""

    response = await compression_llm.ainvoke(
        [HumanMessage(content=summarization_prompt)]
    )
    ai_response = cast(AIMessage, response)
    return ai_response.text.strip()


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

        content = msg.content if isinstance(msg.content, str) else str(msg.content)

        if hasattr(msg, "tool_calls") and msg.tool_calls:
            tool_calls_str = ", ".join(tc["name"] for tc in msg.tool_calls)
            content += f" [Tool calls: {tool_calls_str}]"

        lines.append(f"{role}: {content}")

    return "\n".join(lines)
