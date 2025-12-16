"""Cost calculation utilities for token usage tracking."""


def calculate_cost(
    input_tokens: int,
    output_tokens: int,
    input_cost_per_mtok: float,
    output_cost_per_mtok: float,
) -> float:
    """Calculate the cost for a single API call.

    Args:
        input_tokens: Number of input tokens used
        output_tokens: Number of output tokens used
        input_cost_per_mtok: Cost per million input tokens
        output_cost_per_mtok: Cost per million output tokens

    Returns:
        Total cost in dollars
    """
    input_cost = (input_tokens / 1_000_000) * input_cost_per_mtok
    output_cost = (output_tokens / 1_000_000) * output_cost_per_mtok
    return input_cost + output_cost


def calculate_context_percentage(current_tokens: int, context_window: int) -> float:
    """Calculate the percentage of context window used.

    Args:
        current_tokens: Current number of tokens in context
        context_window: Maximum context window size

    Returns:
        Percentage of context window used (0-100)
    """
    if context_window <= 0:
        return 0.0
    return (current_tokens / context_window) * 100


def format_tokens(tokens: int) -> str:
    """Format token count for display.

    Args:
        tokens: Number of tokens

    Returns:
        Formatted string (e.g., "123K", "1.2M")
    """
    if tokens >= 1_000_000:
        return f"{tokens / 1_000_000:.1f}M"
    elif tokens >= 1_000:
        return f"{tokens / 1_000:.0f}K"
    else:
        return str(tokens)


def format_cost(cost: float) -> str:
    """Format cost for display.

    Args:
        cost: Cost in dollars

    Returns:
        Formatted string (e.g., "$1.23", "$0.05")
    """
    return f"${cost:.2f}"
