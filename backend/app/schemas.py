"""Pydantic contracts for the local API and React client.

These models are intentionally small and explicit. They document the JSON shape
crossing the frontend/backend boundary and keep the route handlers focused on
Freshdesk behavior rather than request parsing.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ConnectionRequest(BaseModel):
    domain: str
    api_key: str = Field(min_length=1)


class RateLimitInfo(BaseModel):
    """Freshdesk rate-limit headers surfaced to users and export manifests."""

    limit: str | None = None
    remaining: str | None = None
    used_current_request: str | None = None
    reset: str | None = None
    retry_after: str | None = None
    raw: dict[str, str] = Field(default_factory=dict)


class ConnectionResponse(BaseModel):
    ok: bool
    domain: str
    rate_limit: RateLimitInfo | None = None
    message: str


class FieldChoice(BaseModel):
    label: str
    value: Any


class FilterField(BaseModel):
    """UI-ready description of a Freshdesk ticket field that can be searched."""

    name: str
    search_key: str
    label: str
    type: str
    source: Literal["standard", "freshdesk", "custom"]
    choices: list[FieldChoice] = Field(default_factory=list)
    operators: list[str] = Field(default_factory=list)
    required: bool = False
    validation: dict[str, Any] = Field(default_factory=dict)


class FilterCondition(BaseModel):
    """One query-builder row submitted by the UI."""

    field: str
    operator: str = "eq"
    value: Any = None
    value_to: Any = None
    type: str | None = None
    choices: list[Any] = Field(default_factory=list)


class QueryRequest(BaseModel):
    filters: list[FilterCondition] = Field(default_factory=list)
    raw_query: str | None = None


class PreviewRequest(QueryRequest):
    page: int = Field(default=1, ge=1, le=10)


class PreviewResponse(BaseModel):
    query: str
    wrapped_query: str
    encoded_query: str
    total: int
    page: int
    tickets: list[dict[str, Any]]
    rate_limit: RateLimitInfo | None = None
    warnings: list[str] = Field(default_factory=list)


class ExportRequest(QueryRequest):
    """Export options that affect discovery and file writing."""

    export_format: Literal["xlsx", "md"] = "xlsx"
    split_field: Literal["created_at", "updated_at"] = "created_at"
    date_start: str | None = None
    date_end: str | None = None


class ExportResponse(BaseModel):
    query: str
    count: int
    xlsx_path: str | None = None
    md_path: str | None = None
    manifest_path: str
    warnings: list[str] = Field(default_factory=list)
    incomplete_windows: list[dict[str, Any]] = Field(default_factory=list)
