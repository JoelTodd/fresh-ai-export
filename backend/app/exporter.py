"""Export pipeline orchestration for Freshdesk ticket searches."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from .export_discovery import ExportAccumulator, discover_ticket_ids, search_results, search_total
from .freshdesk import FreshdeskClient
from .markdown_writer import write_markdown_export
from .post_filter import exclusion_conditions, is_excluded
from .query import build_query
from .schemas import ExportRequest, FilterCondition
from .xlsx_writer import write_xlsx_export

EXPORT_FETCH_CONCURRENCY = 6


def utc_now() -> datetime:
    return datetime.now(tz=UTC)


def iso_now() -> str:
    return utc_now().isoformat().replace("+00:00", "Z")


async def write_export(
    client: FreshdeskClient,
    request: ExportRequest,
    export_dir: Path,
) -> dict[str, Any]:
    """Write an export plus a manifest and return paths for the API response."""
    export_dir.mkdir(parents=True, exist_ok=True)
    query = build_query(request.filters, request.raw_query)
    exclusions = exclusion_conditions(request.filters)
    accumulator = ExportAccumulator()
    if exclusions:
        accumulator.warnings.append(
            "'Is not' filters were applied after Freshdesk returned matching tickets."
        )
    ticket_ids = await discover_ticket_ids(client, request, query, accumulator)

    stamp = utc_now().strftime("%Y%m%dT%H%M%SZ")
    export_id = f"freshdesk-{client.domain}-{stamp}-{uuid4().hex[:8]}"
    xlsx_path = export_dir / f"{export_id}.xlsx"
    md_path = export_dir / f"{export_id}.md"
    manifest_path = export_dir / f"{export_id}.manifest.json"
    exported_at = iso_now()

    semaphore = asyncio.Semaphore(EXPORT_FETCH_CONCURRENCY)
    records = [
        record
        for record in await asyncio.gather(
            *(
                fetch_export_record(
                    client,
                    ticket_id,
                    query,
                    exported_at,
                    exclusions,
                    accumulator,
                    semaphore,
                )
                for ticket_id in ticket_ids
            )
        )
        if record is not None
    ]

    if request.export_format == "xlsx":
        write_xlsx_export(xlsx_path, records)
    else:
        write_markdown_export(md_path, records)

    manifest = {
        "schema_version": "1.0",
        "exported_at": exported_at,
        "freshdesk_domain": client.domain,
        "query": query,
        "filters": [filter_condition.model_dump() for filter_condition in request.filters],
        "count": len(records),
        "format": request.export_format,
        "xlsx_file": str(xlsx_path) if request.export_format == "xlsx" else None,
        "md_file": str(md_path) if request.export_format == "md" else None,
        "warnings": accumulator.warnings,
        "incomplete_windows": accumulator.incomplete_windows,
        "rate_limits": [rate.model_dump() for rate in accumulator.rate_limits],
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    return {
        "query": query,
        "count": len(records),
        "xlsx_path": str(xlsx_path) if request.export_format == "xlsx" else None,
        "md_path": str(md_path) if request.export_format == "md" else None,
        "manifest_path": str(manifest_path),
        "warnings": manifest["warnings"],
        "incomplete_windows": accumulator.incomplete_windows,
    }


async def fetch_export_record(
    client: FreshdeskClient,
    ticket_id: int,
    query: str,
    exported_at: str,
    exclusions: list[FilterCondition],
    accumulator: ExportAccumulator,
    semaphore: asyncio.Semaphore,
) -> dict[str, Any] | None:
    async with semaphore:
        ticket_result = await client.ticket(ticket_id)
        accumulator.add_rate(ticket_result.rate_limit)
        if is_excluded(ticket_result.data, exclusions):
            return None
        conversations_result = await client.conversations(ticket_id)
        accumulator.add_rate(conversations_result.rate_limit)
        conversations = conversations_result.data if isinstance(conversations_result.data, list) else []
        return {
            "schema_version": "1.0",
            "exported_at": exported_at,
            "freshdesk_domain": client.domain,
            "query": query,
            "ticket": ticket_result.data,
            "conversations": conversations,
            "warnings": [],
        }
