"""Freshdesk API client and normalization helpers."""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from typing import Any

import httpx

from .query import wrap_query
from .rate_limit import extract_rate_limit, retry_after_seconds
from .schemas import RateLimitInfo


class FreshdeskError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None, rate_limit: RateLimitInfo | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.rate_limit = rate_limit


@dataclass
class FreshdeskResult:
    data: Any
    rate_limit: RateLimitInfo


def normalize_domain(domain: str) -> str:
    """Accept common user input forms and keep only the Freshdesk subdomain."""
    clean = domain.strip().lower()
    clean = re.sub(r"^https?://", "", clean)
    clean = clean.removesuffix("/")
    clean = clean.removesuffix(".freshdesk.com")
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", clean):
        raise ValueError("Enter the Freshdesk subdomain only, for example 'acme'.")
    return clean


class FreshdeskClient:
    def __init__(
        self,
        domain: str,
        api_key: str,
        *,
        timeout: float = 30.0,
        transport: httpx.AsyncBaseTransport | None = None,
        sleep=asyncio.sleep,
    ) -> None:
        self.domain = normalize_domain(domain)
        self.api_key = api_key
        self.base_url = f"https://{self.domain}.freshdesk.com/api/v2"
        self._transport = transport
        self._timeout = timeout
        self._sleep = sleep
        self._client: httpx.AsyncClient | None = None

    def http_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                auth=(self.api_key, "X"),
                timeout=self._timeout,
                transport=self._transport,
            )
        return self._client

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        retries: int = 3,
    ) -> FreshdeskResult:
        url = f"{self.base_url}{path}"
        client = self.http_client()
        attempt = 0
        while True:
            response = await client.request(method, url, params=params)
            rate_limit = extract_rate_limit(response.headers)

            if response.status_code == 429 and attempt < retries:
                # Freshdesk can return either numeric or HTTP-date
                # Retry-After values; normalize both before sleeping.
                await self._sleep(min(retry_after_seconds(response.headers.get("Retry-After")), 60.0))
                attempt += 1
                continue

            if 500 <= response.status_code <= 599 and attempt < retries:
                await self._sleep(min(2**attempt, 10.0))
                attempt += 1
                continue

            if response.is_error:
                detail = response.text[:300] or response.reason_phrase
                raise FreshdeskError(detail, response.status_code, rate_limit)

            if not response.content:
                data: Any = None
            else:
                data = response.json()
            return FreshdeskResult(data=data, rate_limit=rate_limit)

    async def test_connection(self) -> FreshdeskResult:
        return await self.request("GET", "/tickets", params={"per_page": 1})

    async def ticket_fields(self) -> FreshdeskResult:
        """Use admin metadata when permitted, then fall back to ticket fields."""
        try:
            return await self.request("GET", "/admin/ticket_fields")
        except FreshdeskError as error:
            if error.status_code not in {403, 404}:
                raise
        return await self.request("GET", "/ticket_fields")

    async def list_all(
        self,
        path: str,
        *,
        per_page: int = 100,
        max_pages: int = 10,
    ) -> FreshdeskResult:
        items: list[Any] = []
        last_rate_limit = RateLimitInfo()
        for page in range(1, max_pages + 1):
            result = await self.request(
                "GET",
                path,
                params={"per_page": per_page, "page": page},
            )
            last_rate_limit = result.rate_limit
            if not isinstance(result.data, list) or not result.data:
                break
            items.extend(result.data)
            if len(result.data) < per_page:
                break
        return FreshdeskResult(data=items, rate_limit=last_rate_limit)

    async def agents(self) -> FreshdeskResult:
        return await self.list_all("/agents")

    async def groups(self) -> FreshdeskResult:
        """Use the admin groups endpoint when the account exposes it."""
        try:
            return await self.list_all("/admin/groups")
        except FreshdeskError as error:
            if error.status_code not in {403, 404}:
                raise
        return await self.list_all("/groups")

    async def companies(self) -> FreshdeskResult:
        return await self.list_all("/companies")

    async def products(self) -> FreshdeskResult:
        return await self.list_all("/products")

    async def contacts(self) -> FreshdeskResult:
        return await self.list_all("/contacts")

    async def tags(self) -> FreshdeskResult:
        return await self.list_all("/tags")

    async def search_tickets(self, query: str, page: int = 1) -> FreshdeskResult:
        return await self.request(
            "GET",
            "/search/tickets",
            params={"query": wrap_query(query), "page": page},
        )

    async def ticket(self, ticket_id: int) -> FreshdeskResult:
        return await self.request("GET", f"/tickets/{ticket_id}")

    async def conversations(self, ticket_id: int) -> FreshdeskResult:
        return await self.request("GET", f"/tickets/{ticket_id}/conversations")
