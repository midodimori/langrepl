"""Rate limiter utilities for API providers with token-based limits."""

import threading
import time
from collections import deque
from typing import Any

from langchain_core.messages import BaseMessage
from langchain_core.rate_limiters import BaseRateLimiter
from langchain_core.runnables.config import RunnableConfig

from src.core.logging import get_logger

logger = get_logger(__name__)


class TokenBucketLimiter(BaseRateLimiter):
    """Token bucket rate limiter that tracks both request counts and token usage.

    This implements a token bucket algorithm for rate limiting that tracks:
    1. Number of requests per second
    2. Number of input tokens per second
    3. Number of output tokens per second

    It can be used with LangChain's ChatAnthropic to enforce all three limits.
    """

    def __init__(
        self,
        requests_per_second: float,
        input_tokens_per_second: float,
        output_tokens_per_second: float,
        check_every_n_seconds: float = 0.05,
        max_bucket_size: int = 10,
    ):
        """Initialize the token bucket rate limiter.

        Args:
            requests_per_second: Maximum number of requests per second
            input_tokens_per_second: Maximum number of input tokens per second
            output_tokens_per_second: Maximum number of output tokens per second
            check_every_n_seconds: How often to check the bucket (smaller = smoother)
            max_bucket_size: Maximum number of requests that can be stored in the bucket
        """
        # Initialize the parent class
        super().__init__()

        self.requests_per_second = requests_per_second
        self.input_tokens_per_second = input_tokens_per_second
        self.output_tokens_per_second = output_tokens_per_second
        self.check_every_n_seconds = check_every_n_seconds
        self.max_bucket_size = max_bucket_size

        # Initialize buckets
        self.request_bucket: float = float(self.max_bucket_size)
        self.input_token_bucket: float = float(
            self.max_bucket_size * 100
        )  # Allow more token burst
        self.output_token_bucket: float = float(
            self.max_bucket_size * 100
        )  # Allow more token burst

        # Track last update time
        self.last_update_time = time.time()

        # Add a lock for thread safety
        self._consume_lock = threading.Lock()

        # Track recent token usage for better logging
        self.recent_requests: deque[float] = deque(maxlen=10)  # Track last 10 requests
        self.recent_input_tokens: deque[int] = deque(
            maxlen=10
        )  # Track last 10 input token counts
        self.recent_output_tokens: deque[int] = deque(
            maxlen=10
        )  # Track last 10 output token counts

        logger.info(
            f"Initialized TokenBucketLimiter with limits: "
            f"{self.requests_per_second*60:.1f} requests/min, "
            f"{self.input_tokens_per_second*60:.1f} input tokens/min, "
            f"{self.output_tokens_per_second*60:.1f} output tokens/min"
        )

    def _update_buckets(self) -> None:
        """Update the token buckets based on elapsed time."""
        current_time = time.time()
        elapsed = current_time - self.last_update_time
        self.last_update_time = current_time

        # Add tokens to buckets based on elapsed time
        self.request_bucket = min(
            self.max_bucket_size,
            self.request_bucket + elapsed * self.requests_per_second,
        )

        self.input_token_bucket = min(
            self.max_bucket_size * 100,
            self.input_token_bucket + elapsed * self.input_tokens_per_second,
        )

        self.output_token_bucket = min(
            self.max_bucket_size * 100,
            self.output_token_bucket + elapsed * self.output_tokens_per_second,
        )

    def _consume(self, input_tokens: int = 0, output_tokens: int = 0) -> bool:
        """Try to consume tokens from the buckets.

        Args:
            input_tokens: Number of input tokens to consume
            output_tokens: Number of output tokens to consume

        Returns:
            True if tokens were successfully consumed, False otherwise
        """
        with self._consume_lock:
            current_time = time.time()
            elapsed = current_time - self.last_update_time

            # Calculate what the bucket values would be after refill
            potential_request_bucket = min(
                self.max_bucket_size,
                self.request_bucket + elapsed * self.requests_per_second,
            )
            potential_input_bucket = min(
                self.max_bucket_size * 100,
                self.input_token_bucket + elapsed * self.input_tokens_per_second,
            )
            potential_output_bucket = min(
                self.max_bucket_size * 100,
                self.output_token_bucket + elapsed * self.output_tokens_per_second,
            )

            # Check if we have enough tokens in all buckets
            if (
                potential_request_bucket >= 1
                and potential_input_bucket >= input_tokens
                and (output_tokens == 0 or potential_output_bucket >= output_tokens)
            ):
                # Update buckets and timestamp atomically
                self.last_update_time = current_time
                self.request_bucket = potential_request_bucket - 1
                self.input_token_bucket = potential_input_bucket
                self.output_token_bucket = potential_output_bucket

                if input_tokens > 0:
                    self.input_token_bucket -= input_tokens
                    self.recent_input_tokens.append(input_tokens)

                if output_tokens > 0:
                    self.output_token_bucket -= output_tokens
                    self.recent_output_tokens.append(output_tokens)

                self.recent_requests.append(1)

                # Log current usage if this is a significant request
                if input_tokens > 500 or output_tokens > 500:
                    avg_input = sum(self.recent_input_tokens) / max(
                        len(self.recent_input_tokens), 1
                    )
                    logger.info(
                        f"Rate usage: {sum(self.recent_requests)}/{len(self.recent_requests)} reqs, "
                        f"avg {avg_input:.1f} input tokens/req"
                    )
                return True

            return False

    def acquire(self, *, blocking: bool = True) -> bool:
        """Attempt to acquire tokens from the rate limiter.

        This method blocks until the required tokens are available if `blocking`
        is set to True.

        Args:
            blocking: If True, the method will block until the tokens are available.
                If False, the method will return immediately with the result of
                the attempt. Defaults to True.

        Returns:
           True if the tokens were successfully acquired, False otherwise.
        """
        # Estimate tokens based on the current message context
        # This is a simplified approach - in practice, we'd need to access the messages
        # For now, we'll just track request count and rely on the __call__ method for token tracking

        if not blocking:
            return self._consume()

        while not self._consume():
            time.sleep(self.check_every_n_seconds)
        return True

    async def aacquire(self, *, blocking: bool = True) -> bool:
        """Attempt to acquire tokens from the rate limiter (async version).

        This method blocks until the required tokens are available if `blocking`
        is set to True.

        Args:
            blocking: If True, the method will block until the tokens are available.
                If False, the method will return immediately with the result of
                the attempt. Defaults to True.

        Returns:
           True if the tokens were successfully acquired, False otherwise.
        """
        if not blocking:
            return self._consume()

        import asyncio

        while not self._consume():
            await asyncio.sleep(self.check_every_n_seconds)
        return True

    def __call__(
        self,
        llm: Any,
        messages: list[BaseMessage],
        config: RunnableConfig | None = None,
        **kwargs: Any,
    ) -> Any:
        """Rate limit the LLM call based on both request and token counts.

        This method is called by LangChain before making an LLM API call.
        """
        # Estimate input tokens - this is approximate and model-specific
        # For Anthropic, a rough estimate is 1 token u2248 4 characters
        input_text = "\n".join([str(msg.content) for msg in messages])
        estimated_input_tokens = len(input_text) // 4

        # Wait for tokens to be available
        if estimated_input_tokens > 0:
            # Use the blocking version to wait for tokens
            while not self._consume(input_tokens=estimated_input_tokens):
                time.sleep(self.check_every_n_seconds)

        # Make the actual call
        result = llm._call(messages, config=config, **kwargs)

        # For streaming responses, we don't track output tokens here
        # For non-streaming, we could estimate output tokens and consume them

        return result

    async def _acall(
        self,
        llm: Any,
        messages: list[BaseMessage],
        config: RunnableConfig | None = None,
        **kwargs: Any,
    ) -> Any:
        """Async version of the rate limiter."""
        # Estimate input tokens
        input_text = "\n".join([str(msg.content) for msg in messages])
        estimated_input_tokens = len(input_text) // 4

        # Wait for tokens to be available
        import asyncio

        if estimated_input_tokens > 0:
            # Use the blocking version to wait for tokens
            while not self._consume(input_tokens=estimated_input_tokens):
                await asyncio.sleep(self.check_every_n_seconds)

        # Make the actual async call
        result = await llm._acall(messages, config=config, **kwargs)

        return result
