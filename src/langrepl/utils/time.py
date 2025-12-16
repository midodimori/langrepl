"""Time utility functions."""

from datetime import datetime, timezone


def format_relative_time(timestamp: str | datetime | float | int) -> str:
    """Format timestamp as relative time (e.g., '2 minutes ago', '1 hour ago').

    Args:
        timestamp: Timestamp as string, datetime object, or numeric timestamp

    Returns:
        Formatted relative time string
    """
    try:
        # Convert timestamp to UTC datetime for consistent comparison
        if isinstance(timestamp, str):
            # Try to parse ISO format first, then fall back to float
            try:
                # Handle different ISO format variations
                timestamp_str = timestamp
                if timestamp_str.endswith("Z"):
                    # Replace Z with +00:00 only if no timezone already present
                    if (
                        "+00:00" not in timestamp_str
                        and timestamp_str.count("+") == 0
                        and timestamp_str.count("-") <= 2
                    ):
                        timestamp_str = timestamp_str.replace("Z", "+00:00")
                    else:
                        timestamp_str = timestamp_str.rstrip("Z")

                dt = datetime.fromisoformat(timestamp_str)
                # Convert to UTC if timezone-aware
                if dt.tzinfo is not None:
                    dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
            except ValueError:
                # Try parsing as float timestamp (assumed to be UTC)
                dt = datetime.fromtimestamp(float(timestamp), tz=timezone.utc).replace(
                    tzinfo=None
                )
        elif isinstance(timestamp, (int, float)):
            # Unix timestamps are in UTC
            dt = datetime.fromtimestamp(timestamp, tz=timezone.utc).replace(tzinfo=None)
        elif isinstance(timestamp, datetime):
            dt = timestamp
            # Convert to UTC if timezone-aware
            if dt.tzinfo is not None:
                dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        else:
            return "unknown"

        # Calculate time difference using UTC now
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        diff = now - dt
        total_seconds = int(diff.total_seconds())

        # Handle future timestamps
        if total_seconds < 0:
            return "in the future"

        # Format based on time elapsed
        if total_seconds < 60:
            return f"{total_seconds} second{'s' if total_seconds != 1 else ''} ago"
        elif total_seconds < 3600:  # Less than 1 hour
            minutes = total_seconds // 60
            return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
        elif total_seconds < 86400:  # Less than 1 day
            hours = total_seconds // 3600
            return f"{hours} hour{'s' if hours != 1 else ''} ago"
        elif total_seconds < 2592000:  # Less than 30 days
            days = total_seconds // 86400
            return f"{days} day{'s' if days != 1 else ''} ago"
        elif total_seconds < 31536000:  # Less than 1 year
            months = total_seconds // 2592000
            return f"{months} month{'s' if months != 1 else ''} ago"
        else:
            years = total_seconds // 31536000
            return f"{years} year{'s' if years != 1 else ''} ago"

    except Exception:
        return "unknown"
