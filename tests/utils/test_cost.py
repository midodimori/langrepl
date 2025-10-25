from src.utils.cost import (
    calculate_context_percentage,
    calculate_cost,
    format_cost,
    format_tokens,
)


class TestCalculateCost:
    def test_basic_calculation(self):
        result = calculate_cost(
            input_tokens=1_000_000,
            output_tokens=1_000_000,
            input_cost_per_mtok=3.0,
            output_cost_per_mtok=15.0,
        )
        assert result == 18.0

    def test_zero_tokens(self):
        result = calculate_cost(
            input_tokens=0,
            output_tokens=0,
            input_cost_per_mtok=3.0,
            output_cost_per_mtok=15.0,
        )
        assert result == 0.0

    def test_only_input_tokens(self):
        result = calculate_cost(
            input_tokens=500_000,
            output_tokens=0,
            input_cost_per_mtok=3.0,
            output_cost_per_mtok=15.0,
        )
        assert result == 1.5

    def test_only_output_tokens(self):
        result = calculate_cost(
            input_tokens=0,
            output_tokens=100_000,
            input_cost_per_mtok=3.0,
            output_cost_per_mtok=15.0,
        )
        assert result == 1.5

    def test_fractional_tokens(self):
        result = calculate_cost(
            input_tokens=1234,
            output_tokens=5678,
            input_cost_per_mtok=3.0,
            output_cost_per_mtok=15.0,
        )
        expected = (1234 / 1_000_000) * 3.0 + (5678 / 1_000_000) * 15.0
        assert abs(result - expected) < 0.0001


class TestCalculateContextPercentage:
    def test_basic_calculation(self):
        result = calculate_context_percentage(50_000, 100_000)
        assert result == 50.0

    def test_full_context(self):
        result = calculate_context_percentage(100_000, 100_000)
        assert result == 100.0

    def test_empty_context(self):
        result = calculate_context_percentage(0, 100_000)
        assert result == 0.0

    def test_zero_context_window(self):
        result = calculate_context_percentage(1000, 0)
        assert result == 0.0

    def test_negative_context_window(self):
        result = calculate_context_percentage(1000, -100)
        assert result == 0.0

    def test_over_context_limit(self):
        result = calculate_context_percentage(150_000, 100_000)
        assert result == 150.0


class TestFormatTokens:
    def test_format_small_number(self):
        assert format_tokens(999) == "999"

    def test_format_thousands(self):
        assert format_tokens(1_000) == "1K"
        assert format_tokens(1_500) == "2K"
        assert format_tokens(999_999) == "1000K"

    def test_format_millions(self):
        assert format_tokens(1_000_000) == "1.0M"
        assert format_tokens(1_500_000) == "1.5M"
        assert format_tokens(2_345_678) == "2.3M"

    def test_format_zero(self):
        assert format_tokens(0) == "0"


class TestFormatCost:
    def test_format_basic(self):
        assert format_cost(1.23) == "$1.23"

    def test_format_zero(self):
        assert format_cost(0.0) == "$0.00"

    def test_format_small_amount(self):
        assert format_cost(0.05) == "$0.05"

    def test_format_large_amount(self):
        assert format_cost(123.456) == "$123.46"

    def test_format_rounds_correctly(self):
        assert format_cost(1.234) == "$1.23"
        assert format_cost(1.235) == "$1.24"
