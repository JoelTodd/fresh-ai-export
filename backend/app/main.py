"""FastAPI entrypoint for the local Freshdesk exporter service.

The backend is intentionally state-light: it keeps Freshdesk credentials in memory
for the current desktop/browser session and writes export artifacts to disk only
after the user explicitly starts an export.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Annotated
from uuid import uuid4

from fastapi import Cookie, FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware

from .config import EXPORT_DIR, FRONTEND_ORIGINS, SESSION_COOKIE_NAME
from .exporter import search_results, search_total, write_export
from .fields import build_filter_fields
from .freshdesk import FreshdeskClient, FreshdeskError, normalize_domain
from .lookups import fetch_lookup_choices
from .post_filter import apply_exclusions, exclusion_conditions
from .query import QueryError, build_query, encode_query, wrap_query
from .schemas import (
    ConnectionRequest,
    ConnectionResponse,
    ExportRequest,
    ExportResponse,
    PreviewRequest,
    PreviewResponse,
    QueryRequest,
    RateLimitInfo,
)


@dataclass
class FreshdeskSession:
    domain: str
    api_key: str
    fields_cache: dict[str, object] | None = None


SESSIONS: dict[str, FreshdeskSession] = {}
"""Process-local session registry keyed by the HTTP-only session cookie.

This is deliberate for the local desktop use case: restarting the backend clears
credentials instead of persisting API keys to disk.
"""

app = FastAPI(title="Freshdesk Local Exporter")
app.add_middleware(
    CORSMiddleware,
    allow_origins=FRONTEND_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def client_from_session(session_id: str | None) -> FreshdeskClient:
    """Build a Freshdesk client from the current browser/WebView2 session cookie."""
    session = session_from_cookie(session_id)
    return FreshdeskClient(session.domain, session.api_key)


def session_from_cookie(session_id: str | None) -> FreshdeskSession:
    if not session_id or session_id not in SESSIONS:
        raise HTTPException(status_code=401, detail="Connect to Freshdesk first.")
    return SESSIONS[session_id]


def raise_freshdesk(error: FreshdeskError) -> None:
    """Expose Freshdesk failures without dropping useful rate-limit context."""
    raise HTTPException(
        status_code=error.status_code or 502,
        detail={
            "message": str(error),
            "rate_limit": error.rate_limit.model_dump() if error.rate_limit else None,
        },
    )


async def filtered_preview_results(
    client: FreshdeskClient,
    query: str,
    page: int,
    exclusions: list,
) -> tuple[list[dict[str, object]], int, RateLimitInfo | None]:
    """Apply app-side exclusions before slicing the requested preview page."""
    first = await client.search_tickets(query, page=1)
    rate_limit = first.rate_limit
    total = search_total(first.data)
    if not exclusions:
        return search_results(first.data), total, rate_limit

    pages = min(10, max(1, (total + 29) // 30))
    results = search_results(first.data)
    for result in await asyncio.gather(
        *(client.search_tickets(query, page=page_number) for page_number in range(2, pages + 1))
    ):
        results.extend(search_results(result.data))

    filtered = apply_exclusions(results, exclusions)
    start = (page - 1) * 30
    end = start + 30
    return filtered[start:end], len(filtered), rate_limit


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"ok": "true"}


@app.post("/api/connect", response_model=ConnectionResponse)
async def connect(payload: ConnectionRequest, response: Response) -> ConnectionResponse:
    client: FreshdeskClient | None = None
    try:
        domain = normalize_domain(payload.domain)
        client = FreshdeskClient(domain, payload.api_key)
        result = await client.test_connection()
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except FreshdeskError as error:
        raise_freshdesk(error)
    finally:
        if client is not None:
            await client.aclose()

    session_id = uuid4().hex
    SESSIONS[session_id] = FreshdeskSession(domain=domain, api_key=payload.api_key)
    # The cookie stores only an opaque session ID. The API key remains in the
    # backend process memory and is cleared when the process exits.
    response.set_cookie(
        SESSION_COOKIE_NAME,
        session_id,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=60 * 60 * 8,
    )
    return ConnectionResponse(
        ok=True,
        domain=domain,
        rate_limit=result.rate_limit,
        message="Connected to Freshdesk.",
    )


@app.get("/api/connection")
async def connection(
    session_id: Annotated[str | None, Cookie(alias=SESSION_COOKIE_NAME)] = None,
) -> dict[str, str | bool | None]:
    session = SESSIONS.get(session_id or "")
    return {"connected": bool(session), "domain": session.domain if session else None}


@app.get("/api/fields")
async def fields(
    session_id: Annotated[str | None, Cookie(alias=SESSION_COOKIE_NAME)] = None,
    refresh: bool = False,
) -> dict[str, object]:
    session = session_from_cookie(session_id)
    if session.fields_cache is not None and not refresh:
        return session.fields_cache
    client = FreshdeskClient(session.domain, session.api_key)
    try:
        result = await client.ticket_fields()
        lookup_choices = await fetch_lookup_choices(client)
    except FreshdeskError as error:
        raise_freshdesk(error)
    finally:
        await client.aclose()
    raw_fields = result.data if isinstance(result.data, list) else []
    session.fields_cache = {
        "fields": [field.model_dump() for field in build_filter_fields(raw_fields, lookup_choices)],
        "rate_limit": result.rate_limit.model_dump(),
    }
    return session.fields_cache


@app.post("/api/query")
async def query(payload: QueryRequest) -> dict[str, str]:
    try:
        generated = build_query(payload.filters, payload.raw_query)
        return {
            "query": generated,
            "wrapped_query": wrap_query(generated),
            "encoded_query": encode_query(generated),
        }
    except QueryError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.post("/api/preview", response_model=PreviewResponse)
async def preview(
    payload: PreviewRequest,
    session_id: Annotated[str | None, Cookie(alias=SESSION_COOKIE_NAME)] = None,
) -> PreviewResponse:
    client = client_from_session(session_id)
    try:
        generated = build_query(payload.filters, payload.raw_query)
        exclusions = exclusion_conditions(payload.filters)
        tickets, total, rate_limit = await filtered_preview_results(
            client,
            generated,
            payload.page,
            exclusions,
        )
    except QueryError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except FreshdeskError as error:
        raise_freshdesk(error)
    finally:
        await client.aclose()

    warnings: list[str] = []
    if exclusions:
        warnings.append("'Is not' filters were applied after Freshdesk returned matching tickets.")
    if total >= 300:
        warnings.append(
            "Freshdesk reports 300 or more matches; export will need date-window splitting to avoid silent truncation."
        )
    return PreviewResponse(
        query=generated,
        wrapped_query=wrap_query(generated),
        encoded_query=encode_query(generated),
        total=total,
        page=payload.page,
        tickets=tickets,
        rate_limit=rate_limit,
        warnings=warnings,
    )


@app.post("/api/export", response_model=ExportResponse)
async def export(
    payload: ExportRequest,
    session_id: Annotated[str | None, Cookie(alias=SESSION_COOKIE_NAME)] = None,
) -> ExportResponse:
    client = client_from_session(session_id)
    try:
        result = await write_export(client, payload, EXPORT_DIR)
    except QueryError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except FreshdeskError as error:
        raise_freshdesk(error)
    finally:
        await client.aclose()
    return ExportResponse(**result)
