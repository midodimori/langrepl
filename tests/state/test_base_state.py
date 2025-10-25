from src.state.base import file_reducer


class TestFileReducer:
    def test_both_none(self):
        result = file_reducer(None, None)
        assert result is None

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
