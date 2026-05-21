import json
import zipfile
from pathlib import Path
from typing import Any

import pytest

from app.exporter import write_export
from app.schemas import ExportRequest, FilterCondition, RateLimitInfo


class FakeResult:
    def __init__(self, data: Any):
        self.data = data
        self.rate_limit = RateLimitInfo(raw={})


class FakeClient:
    domain = "example"

    def __init__(self) -> None:
        self.detail_calls: list[int] = []
        self.conversation_calls: list[int] = []

    async def search_tickets(self, query: str, page: int = 1) -> FakeResult:
        assert query == "status:2"
        return FakeResult({"total": 2, "results": [{"id": 10}, {"id": 20}]})

    async def ticket(self, ticket_id: int) -> FakeResult:
        self.detail_calls.append(ticket_id)
        return FakeResult(
            {
                "id": ticket_id,
                "subject": f"Ticket {ticket_id}",
                "status": 2,
                "description": "<div>ignored html duplicate</div>",
                "description_text": "Useful ticket description",
                "custom_fields": {"cf_category": "Hardware", "cf_empty": None},
                "attachments": [],
                "extra_context": {"asset": "Laptop"},
            }
        )

    async def conversations(self, ticket_id: int) -> FakeResult:
        self.conversation_calls.append(ticket_id)
        return FakeResult(
            [
                {
                    "id": ticket_id * 100,
                    "body": "<div>ignored conversation html</div>",
                    "body_text": "hello",
                    "attachments": [],
                    "private": False,
                }
            ]
        )


class FakeExclusionClient(FakeClient):
    async def ticket(self, ticket_id: int) -> FakeResult:
        self.detail_calls.append(ticket_id)
        return FakeResult(
            {
                "id": ticket_id,
                "subject": f"Ticket {ticket_id}",
                "status": 5 if ticket_id == 20 else 2,
                "attachments": [],
            }
        )


class FakeCappedExclusionClient(FakeExclusionClient):
    async def search_tickets(self, query: str, page: int = 1) -> FakeResult:
        assert query == "status:2"
        if page == 1:
            return FakeResult({"total": 300, "results": [{"id": 10}, {"id": 20}]})
        return FakeResult({"total": 300, "results": []})


@pytest.mark.asyncio
async def test_markdown_export_writes_compact_ai_readable_ticket_context(tmp_path: Path) -> None:
    client = FakeClient()
    result = await write_export(
        client,
        ExportRequest(raw_query="status:2", export_format="md"),
        tmp_path,
    )

    assert result["count"] == 2
    assert client.detail_calls == [10, 20]
    assert client.conversation_calls == [10, 20]

    content = Path(result["md_path"]).read_text(encoding="utf-8")
    assert "## Ticket 10: Ticket 10" in content
    assert "Useful ticket description" in content
    assert "hello" in content
    assert "cf_category: Hardware" in content
    assert '"extra_context":{"asset":"Laptop"}' in content
    assert "Ticket payload" not in content
    assert "Conversation payloads" not in content
    assert "ignored html duplicate" not in content
    assert '"attachments": []' not in content

    manifest = json.loads(Path(result["manifest_path"]).read_text(encoding="utf-8"))
    assert manifest["count"] == 2
    assert manifest["query"] == "status:2"


@pytest.mark.asyncio
async def test_xlsx_export_writes_workbook_with_ticket_and_conversation_sheets(tmp_path: Path) -> None:
    result = await write_export(
        FakeClient(),
        ExportRequest(raw_query="status:2", export_format="xlsx"),
        tmp_path,
    )

    assert result["md_path"] is None
    assert result["xlsx_path"]

    with zipfile.ZipFile(result["xlsx_path"]) as workbook:
        names = set(workbook.namelist())
        tickets_sheet = workbook.read("xl/worksheets/sheet1.xml").decode("utf-8")
        conversations_sheet = workbook.read("xl/worksheets/sheet2.xml").decode("utf-8")

    assert "xl/workbook.xml" in names
    assert "ticket_json" in tickets_sheet
    assert "conversations_json" in tickets_sheet
    assert "conversation_json" in conversations_sheet


@pytest.mark.asyncio
async def test_export_applies_is_not_filters_after_discovery(tmp_path: Path) -> None:
    client = FakeExclusionClient()
    result = await write_export(
        client,
        ExportRequest(
            raw_query="status:2",
            filters=[FilterCondition(field="status", operator="neq", value="5", type="number")],
        ),
        tmp_path,
    )

    assert result["count"] == 1
    assert client.detail_calls == [10, 20]
    assert client.conversation_calls == [10]


@pytest.mark.asyncio
async def test_export_with_is_not_can_continue_without_date_range_at_cap(tmp_path: Path) -> None:
    client = FakeCappedExclusionClient()
    result = await write_export(
        client,
        ExportRequest(
            raw_query="status:2",
            filters=[FilterCondition(field="status", operator="neq", value="5", type="number")],
        ),
        tmp_path,
    )

    assert result["count"] == 1
    assert "API-reachable" in " ".join(result["warnings"])
