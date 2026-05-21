import httpx
import pytest

from app.freshdesk import FreshdeskClient, normalize_domain


async def no_sleep(_: float) -> None:
    return None


def test_normalize_domain_accepts_subdomain_or_full_host() -> None:
    assert normalize_domain("Acme") == "acme"
    assert normalize_domain("https://acme.freshdesk.com/") == "acme"


@pytest.mark.asyncio
async def test_429_retry_after_handling() -> None:
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(429, headers={"Retry-After": "0"})
        return httpx.Response(200, json={"ok": True}, headers={"X-RateLimit-Remaining": "99"})

    client = FreshdeskClient("example", "key", transport=httpx.MockTransport(handler), sleep=no_sleep)
    result = await client.request("GET", "/tickets")

    assert calls == 2
    assert result.data == {"ok": True}
    assert result.rate_limit.remaining == "99"


@pytest.mark.asyncio
async def test_5xx_retry_handling() -> None:
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls < 3:
            return httpx.Response(500, text="temporary")
        return httpx.Response(200, json=[])

    client = FreshdeskClient("example", "key", transport=httpx.MockTransport(handler), sleep=no_sleep)
    result = await client.ticket_fields()

    assert calls == 3
    assert result.data == []


@pytest.mark.asyncio
async def test_search_call_sends_wrapped_encoded_query() -> None:
    seen_url = ""

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal seen_url
        seen_url = str(request.url)
        assert request.url.params["query"] == '"status:2"'
        assert request.url.params["page"] == "3"
        return httpx.Response(200, json={"total": 0, "results": []})

    client = FreshdeskClient("example", "key", transport=httpx.MockTransport(handler), sleep=no_sleep)
    await client.search_tickets("status:2", page=3)

    assert "query=%22status%3A2%22" in seen_url
