import time

import pytest

from src.utils.rate_limiter import TokenBucketLimiter


class TestTokenBucketLimiter:
    def test_initialization(self):
        limiter = TokenBucketLimiter(
            requests_per_second=10.0,
            input_tokens_per_second=1000.0,
            output_tokens_per_second=500.0,
            check_every_n_seconds=0.1,
            max_bucket_size=5,
        )

        assert limiter.requests_per_second == 10.0
        assert limiter.input_tokens_per_second == 1000.0
        assert limiter.output_tokens_per_second == 500.0
        assert limiter.max_bucket_size == 5
        assert limiter.request_bucket == 5.0

    def test_consume_with_available_tokens(self):
        limiter = TokenBucketLimiter(
            requests_per_second=10.0,
            input_tokens_per_second=1000.0,
            output_tokens_per_second=500.0,
        )

        result = limiter._consume(input_tokens=100, output_tokens=50)
        assert result is True

    def test_consume_without_enough_tokens(self):
        limiter = TokenBucketLimiter(
            requests_per_second=10.0,
            input_tokens_per_second=1000.0,
            output_tokens_per_second=500.0,
            max_bucket_size=1,
        )

        limiter._consume(input_tokens=100)
        result = limiter._consume(input_tokens=10000)
        assert result is False

    def test_bucket_refill_over_time(self):
        limiter = TokenBucketLimiter(
            requests_per_second=10.0,
            input_tokens_per_second=1000.0,
            output_tokens_per_second=500.0,
            max_bucket_size=5,
        )

        initial_bucket = limiter.request_bucket
        time.sleep(0.2)
        limiter._update_buckets()

        assert limiter.request_bucket >= initial_bucket

    def test_bucket_does_not_exceed_max(self):
        limiter = TokenBucketLimiter(
            requests_per_second=1000.0,
            input_tokens_per_second=100000.0,
            output_tokens_per_second=50000.0,
            max_bucket_size=5,
        )

        time.sleep(0.1)
        limiter._update_buckets()

        assert limiter.request_bucket <= limiter.max_bucket_size
        assert limiter.input_token_bucket <= limiter.max_bucket_size * 100
        assert limiter.output_token_bucket <= limiter.max_bucket_size * 100

    def test_acquire_non_blocking_with_tokens(self):
        limiter = TokenBucketLimiter(
            requests_per_second=10.0,
            input_tokens_per_second=1000.0,
            output_tokens_per_second=500.0,
        )

        result = limiter.acquire(blocking=False)
        assert result is True

    def test_acquire_non_blocking_without_tokens(self):
        limiter = TokenBucketLimiter(
            requests_per_second=10.0,
            input_tokens_per_second=1000.0,
            output_tokens_per_second=500.0,
            max_bucket_size=1,
        )

        limiter._consume(input_tokens=100)
        result = limiter.acquire(blocking=False)
        assert result is False

    @pytest.mark.asyncio
    async def test_aacquire_non_blocking(self):
        limiter = TokenBucketLimiter(
            requests_per_second=10.0,
            input_tokens_per_second=1000.0,
            output_tokens_per_second=500.0,
        )

        result = await limiter.aacquire(blocking=False)
        assert result is True

    def test_multiple_consumes_deplete_bucket(self):
        limiter = TokenBucketLimiter(
            requests_per_second=10.0,
            input_tokens_per_second=1000.0,
            output_tokens_per_second=500.0,
            max_bucket_size=3,
        )

        assert limiter._consume() is True
        assert limiter._consume() is True
        assert limiter._consume() is True
        assert limiter._consume() is False

    def test_thread_safety(self):
        limiter = TokenBucketLimiter(
            requests_per_second=100.0,
            input_tokens_per_second=10000.0,
            output_tokens_per_second=5000.0,
            max_bucket_size=10,
        )

        import threading

        results = []

        def consume_tokens():
            result = limiter._consume(input_tokens=100)
            results.append(result)

        threads = [threading.Thread(target=consume_tokens) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        successful = sum(results)
        assert successful <= 10
