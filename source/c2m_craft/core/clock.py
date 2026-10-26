"""Logical clock.

The repository is reproducible: nothing reads the wall clock.  The "current"
time is a configured logical instant (``as_of`` in config/site.json) advanced by
an explicit number of minutes.  Two runs of the same scenario therefore emit
byte-identical timestamps.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

TS_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def parse_ts(value: str) -> datetime:
    """Parse an RFC 3339 UTC timestamp (``2026-10-23T00:00:00Z``)."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError("timestamp must be a non-empty string")
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def fmt_ts(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime(TS_FORMAT)


def add_minutes(value: str, minutes: float) -> str:
    return fmt_ts(parse_ts(value) + timedelta(minutes=minutes))


def add_days(value: str, days: float) -> str:
    return fmt_ts(parse_ts(value) + timedelta(days=days))


class LogicalClock:
    """A monotonic logical clock rooted at a configured instant."""

    def __init__(self, start: str) -> None:
        self.start = fmt_ts(parse_ts(start))
        self._minutes = 0.0

    @property
    def now(self) -> str:
        return add_minutes(self.start, self._minutes)

    def advance(self, minutes: float = 1.0) -> str:
        self._minutes += float(minutes)
        return self.now

    def at(self, minutes: float) -> str:
        return add_minutes(self.start, minutes)

    def reset(self) -> None:
        self._minutes = 0.0

    @property
    def offset_minutes(self) -> float:
        return self._minutes

    def restore(self, minutes: float) -> None:
        self._minutes = float(minutes)

    def snapshot(self) -> dict:
        return {"start": self.start, "offset_minutes": self._minutes, "now": self.now}
