from datetime import datetime, timedelta, timezone

from src.utils.time import format_relative_time


class TestFormatRelativeTime:
    def test_seconds_ago(self):
        now = datetime.now(timezone.utc)
        past = now - timedelta(seconds=30)
        result = format_relative_time(past)
        assert "30 seconds ago" in result

    def test_one_second_ago(self):
        now = datetime.now(timezone.utc)
        past = now - timedelta(seconds=1)
        result = format_relative_time(past)
        assert result == "1 second ago"

    def test_minutes_ago(self):
        now = datetime.now(timezone.utc)
        past = now - timedelta(minutes=15)
        result = format_relative_time(past)
        assert "15 minutes ago" in result

    def test_one_minute_ago(self):
        now = datetime.now(timezone.utc)
        past = now - timedelta(minutes=1)
        result = format_relative_time(past)
        assert result == "1 minute ago"

    def test_hours_ago(self):
        now = datetime.now(timezone.utc)
        past = now - timedelta(hours=3)
        result = format_relative_time(past)
        assert "3 hours ago" in result

    def test_one_hour_ago(self):
        now = datetime.now(timezone.utc)
        past = now - timedelta(hours=1)
        result = format_relative_time(past)
        assert result == "1 hour ago"

    def test_days_ago(self):
        now = datetime.now(timezone.utc)
        past = now - timedelta(days=5)
        result = format_relative_time(past)
        assert "5 days ago" in result

    def test_one_day_ago(self):
        now = datetime.now(timezone.utc)
        past = now - timedelta(days=1)
        result = format_relative_time(past)
        assert result == "1 day ago"

    def test_months_ago(self):
        now = datetime.now(timezone.utc)
        past = now - timedelta(days=60)
        result = format_relative_time(past)
        assert "month" in result

    def test_years_ago(self):
        now = datetime.now(timezone.utc)
        past = now - timedelta(days=400)
        result = format_relative_time(past)
        assert "year" in result

    def test_future_timestamp(self):
        now = datetime.now(timezone.utc)
        future = now + timedelta(hours=1)
        result = format_relative_time(future)
        assert result == "in the future"

    def test_iso_string_format(self):
        iso_string = "2024-01-01T12:00:00Z"
        result = format_relative_time(iso_string)
        assert result != "unknown"

    def test_unix_timestamp(self):
        now = datetime.now(timezone.utc)
        past_timestamp = (now - timedelta(minutes=30)).timestamp()
        result = format_relative_time(past_timestamp)
        assert "30 minutes ago" in result

    def test_invalid_input(self):
        result = format_relative_time("not a valid timestamp")
        assert result == "unknown"

    def test_timezone_aware_datetime(self):
        past = datetime.now(timezone.utc) - timedelta(minutes=10)
        result = format_relative_time(past)
        assert "10 minutes ago" in result

    def test_timezone_naive_datetime(self):
        past = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=5)
        result = format_relative_time(past)
        assert "minute" in result
