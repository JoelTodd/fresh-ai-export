from datetime import timedelta

from app.windows import DateWindow, dedupe_ticket_ids, parse_datetime, parse_export_end, split_window


def test_date_window_splitting() -> None:
    window = DateWindow(parse_datetime("2026-01-01"), parse_datetime("2026-01-05"))
    left, right = split_window(window)

    assert left.start == window.start
    assert left.end == right.start
    assert right.end == window.end
    assert left.end - left.start == timedelta(days=2)


def test_deduplication_preserves_first_seen_order() -> None:
    assert dedupe_ticket_ids([3, 1, 3, 2, 1]) == [3, 1, 2]


def test_export_end_date_is_inclusive_for_date_inputs() -> None:
    assert parse_export_end("2026-05-12") - parse_datetime("2026-05-12") == timedelta(days=1)
