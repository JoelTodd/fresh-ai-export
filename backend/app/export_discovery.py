"""Ticket ID discovery for Freshdesk exports."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from .freshdesk import FreshdeskClient
from .post_filter import exclusion_conditions
from .query import append_date_window
from .schemas import ExportRequest, RateLimitInfo
from .windows import DateWindow, dedupe_ticket_ids, parse_datetime, parse_export_end, split_window

SEARCH_CAP = 300
PER_PAGE = 30


@dataclass
class ExportAccumulator:
    """Cross-call state that is reported in the final manifest."""

    rate_limits: list[RateLimitInfo] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    incomplete_windows: list[dict[str, Any]] = field(default_factory=list)

    def add_rate(self, rate_limit: RateLimitInfo) -> None:
        if rate_limit.raw:
            self.rate_limits.append(rate_limit)


def search_total(payload: dict[str, Any]) -> int:
    return int(payload.get("total") or 0)


def search_results(payload: dict[str, Any]) -> list[dict[str, Any]]:
    results = payload.get("results") or []
    return results if isinstance(results, list) else []


async def fetch_search_pages(
    client: FreshdeskClient,
    query: str,
    total: int,
    accumulator: ExportAccumulator,
    first_page_results: list[dict[str, Any]] | None = None,
) -> list[int]:
    ids: list[int] = []
    # Freshdesk search is capped at ten 30-ticket pages, even when `total`
    # reports more matches.
    pages = min(10, max(1, (total + PER_PAGE - 1) // PER_PAGE))
    if first_page_results is not None:
        ids.extend(int(ticket["id"]) for ticket in first_page_results if ticket.get("id") is not None)
        first_page = 2
    else:
        first_page = 1
    results = await asyncio.gather(
        *(client.search_tickets(query, page=page) for page in range(first_page, pages + 1))
    )
    for result in results:
        accumulator.add_rate(result.rate_limit)
        ids.extend(int(ticket["id"]) for ticket in search_results(result.data) if ticket.get("id") is not None)
    return ids


async def discover_ids_for_window(
    client: FreshdeskClient,
    base_query: str,
    split_field: str,
    window: DateWindow,
    accumulator: ExportAccumulator,
) -> list[int]:
    """Split oversized searches until Freshdesk can expose the window's IDs."""
    query = append_date_window(
        base_query,
        split_field,
        window.start.isoformat().replace("+00:00", "Z"),
        window.end.isoformat().replace("+00:00", "Z"),
    )
    first = await client.search_tickets(query, page=1)
    accumulator.add_rate(first.rate_limit)
    total = search_total(first.data)
    if total >= SEARCH_CAP and not window.is_daily_or_smaller:
        left, right = split_window(window)
        return [
            *await discover_ids_for_window(client, base_query, split_field, left, accumulator),
            *await discover_ids_for_window(client, base_query, split_field, right, accumulator),
        ]
    if total >= SEARCH_CAP:
        manifest_window = window.to_manifest(total=total, incomplete=True)
        accumulator.incomplete_windows.append(manifest_window)
        accumulator.warnings.append(
            f"{split_field} window {manifest_window['start']} to {manifest_window['end']} hit Freshdesk's 300-result cap."
        )
    return await fetch_search_pages(client, query, total, accumulator, search_results(first.data))


async def discover_ticket_ids(
    client: FreshdeskClient,
    request: ExportRequest,
    query: str,
    accumulator: ExportAccumulator,
) -> list[int]:
    """Discover every ticket ID the export can fetch without silent truncation."""
    first = await client.search_tickets(query, page=1)
    accumulator.add_rate(first.rate_limit)
    total = search_total(first.data)
    if total < SEARCH_CAP:
        return dedupe_ticket_ids(
            await fetch_search_pages(client, query, total, accumulator, search_results(first.data))
        )

    if not request.date_start or not request.date_end:
        if exclusion_conditions(request.filters):
            accumulator.warnings.append(
                "Freshdesk reported 300 or more matches before 'is not' filters were applied. Exported the API-reachable matches only; add a date range for a complete split export."
            )
            return dedupe_ticket_ids(
                await fetch_search_pages(client, query, total, accumulator, search_results(first.data))
            )
        raise ValueError(
            "This query reports 300 or more matches. Choose a date range so the export can split safely."
        )

    window = DateWindow(parse_datetime(request.date_start), parse_export_end(request.date_end))
    if window.end <= window.start:
        raise ValueError("Export date range end must be after start.")
    ids = await discover_ids_for_window(client, query, request.split_field, window, accumulator)
    return dedupe_ticket_ids(ids)
