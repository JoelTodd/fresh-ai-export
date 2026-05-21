"""Date-window helpers used to work around Freshdesk search result caps."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Iterable


@dataclass(frozen=True)
class DateWindow:
    start: datetime
    end: datetime

    @property
    def is_daily_or_smaller(self) -> bool:
        return self.end - self.start <= timedelta(days=1)

    def to_manifest(self, total: int | None = None, incomplete: bool = False) -> dict[str, object]:
        payload: dict[str, object] = {
            "start": self.start.isoformat().replace("+00:00", "Z"),
            "end": self.end.isoformat().replace("+00:00", "Z"),
            "incomplete": incomplete,
        }
        if total is not None:
            payload["total"] = total
        return payload


def parse_datetime(value: str) -> datetime:
    """Parse user/date-input values into timezone-aware UTC datetimes."""
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    if "T" not in normalized:
        normalized = normalized + "T00:00:00+00:00"
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def parse_export_end(value: str) -> datetime:
    """Treat date-input end dates as inclusive calendar days."""
    parsed = parse_datetime(value)
    if "T" not in value.strip():
        return parsed + timedelta(days=1)
    return parsed


def split_window(window: DateWindow) -> tuple[DateWindow, DateWindow]:
    midpoint = window.start + (window.end - window.start) / 2
    return DateWindow(window.start, midpoint), DateWindow(midpoint, window.end)


def dedupe_ticket_ids(ids: Iterable[int]) -> list[int]:
    seen: set[int] = set()
    deduped: list[int] = []
    for ticket_id in ids:
        if ticket_id in seen:
            continue
        seen.add(ticket_id)
        deduped.append(ticket_id)
    return deduped
