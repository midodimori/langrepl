from fnmatch import fnmatch

from langrepl.utils.patterns import matches_patterns


class TestMatchesPatterns:
    def test_matches_positive(self):
        assert matches_patterns(["foo", "bar"], lambda p: p == "foo") is True

    def test_no_match(self):
        assert matches_patterns(["foo", "bar"], lambda p: p == "baz") is False

    def test_excluded_by_negative(self):
        assert matches_patterns(["*", "!foo"], lambda p: fnmatch("foo", p)) is False

    def test_not_excluded(self):
        assert matches_patterns(["*", "!foo"], lambda p: fnmatch("bar", p)) is True

    def test_only_negatives_matches_nothing(self):
        assert matches_patterns(["!foo"], lambda p: True) is False

    def test_empty_patterns_matches_nothing(self):
        assert matches_patterns([], lambda p: True) is False

    def test_wildcard_with_negative(self):
        assert (
            matches_patterns(
                ["file_*", "!file_write"], lambda p: fnmatch("file_read", p)
            )
            is True
        )
        assert (
            matches_patterns(
                ["file_*", "!file_write"], lambda p: fnmatch("file_write", p)
            )
            is False
        )
