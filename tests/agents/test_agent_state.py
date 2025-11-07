from src.agents.state import add_reducer, file_reducer, replace_reducer, sum_reducer


class TestFileReducer:
    def test_both_none(self):
        result = file_reducer(None, None)
        assert result == {}

    def test_left_none(self):
        right = {"file1": "content1"}
        result = file_reducer(None, right)
        assert result == {"file1": "content1"}

    def test_right_none(self):
        left = {"file1": "content1"}
        result = file_reducer(left, None)
        assert result == {"file1": "content1"}

    def test_merge_non_overlapping(self):
        left = {"file1": "content1"}
        right = {"file2": "content2"}
        result = file_reducer(left, right)
        assert result == {"file1": "content1", "file2": "content2"}

    def test_merge_overlapping(self):
        left = {"file1": "content1", "file2": "old"}
        right = {"file2": "new", "file3": "content3"}
        result = file_reducer(left, right)
        assert result == {"file1": "content1", "file2": "new", "file3": "content3"}

    def test_empty_dicts(self):
        result = file_reducer({}, {})
        assert result == {}

    def test_left_empty(self):
        right = {"file1": "content1"}
        result = file_reducer({}, right)
        assert result == {"file1": "content1"}

    def test_right_empty(self):
        left = {"file1": "content1"}
        result = file_reducer(left, {})
        assert result == {"file1": "content1"}

    def test_does_not_mutate_inputs(self):
        left = {"file1": "content1"}
        right = {"file2": "content2"}
        left_copy = left.copy()
        right_copy = right.copy()

        result = file_reducer(left, right)

        assert left == left_copy
        assert right == right_copy
        assert result == {"file1": "content1", "file2": "content2"}


class TestAddReducer:
    def test_both_values(self):
        assert add_reducer(10, 20) == 30

    def test_left_none(self):
        assert add_reducer(None, 20) == 20

    def test_right_none(self):
        assert add_reducer(10, None) == 10

    def test_both_none(self):
        assert add_reducer(None, None) == 0

    def test_zero_values(self):
        assert add_reducer(0, 0) == 0

    def test_mixed_zero_and_value(self):
        assert add_reducer(0, 5) == 5
        assert add_reducer(5, 0) == 5


class TestReplaceReducer:
    def test_both_values(self):
        """Replace should use right value, ignoring left."""
        assert replace_reducer(10, 20) == 20

    def test_left_none(self):
        """When left is None, use right value."""
        assert replace_reducer(None, 20) == 20

    def test_right_none(self):
        """When right is None, preserve left value."""
        assert replace_reducer(10, None) == 10

    def test_both_none(self):
        """When both are None, return 0."""
        assert replace_reducer(None, None) == 0

    def test_zero_values(self):
        """Replace with zero should work."""
        assert replace_reducer(100, 0) == 0

    def test_cumulative_token_scenario(self):
        """Simulates cumulative input tokens from LLM providers.

        Unlike add_reducer which would accumulate (6307 + 6322 = 12629),
        replace_reducer correctly uses just the latest cumulative value.
        """
        state_tokens = 6307  # After turn 1
        new_tokens = 6322  # Turn 2 (already includes turn 1's context)

        result = replace_reducer(state_tokens, new_tokens)
        assert result == 6322  # Should be 6322, not 12629


class TestSumReducer:
    def test_both_values(self):
        assert sum_reducer(10.5, 20.3) == 30.8

    def test_left_none(self):
        assert sum_reducer(None, 20.5) == 20.5

    def test_right_none(self):
        assert sum_reducer(10.5, None) == 10.5

    def test_both_none(self):
        assert sum_reducer(None, None) == 0.0

    def test_zero_values(self):
        assert sum_reducer(0.0, 0.0) == 0.0

    def test_mixed_zero_and_value(self):
        assert sum_reducer(0.0, 5.5) == 5.5
        assert sum_reducer(5.5, 0.0) == 5.5

    def test_precision(self):
        result = sum_reducer(0.1, 0.2)
        assert abs(result - 0.3) < 1e-10
