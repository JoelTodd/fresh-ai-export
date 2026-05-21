"""Dependency-light XLSX writer for ticket export records.

The portable desktop build ships a small runtime, so this module writes the
minimal OpenXML package directly instead of depending on a workbook library.
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape


def flatten_ticket_for_workbook(record: dict[str, Any]) -> dict[str, Any]:
    ticket = record["ticket"]
    conversations = record["conversations"]
    custom_fields = ticket.get("custom_fields") if isinstance(ticket.get("custom_fields"), dict) else {}
    attachment_count = len(ticket.get("attachments") or [])
    conversation_attachment_count = sum(len(conversation.get("attachments") or []) for conversation in conversations)
    row: dict[str, Any] = {
        "id": ticket.get("id"),
        "subject": ticket.get("subject"),
        "status": ticket.get("status"),
        "priority": ticket.get("priority"),
        "requester_id": ticket.get("requester_id"),
        "responder_id": ticket.get("responder_id"),
        "group_id": ticket.get("group_id"),
        "company_id": ticket.get("company_id"),
        "type": ticket.get("type"),
        "created_at": ticket.get("created_at"),
        "updated_at": ticket.get("updated_at"),
        "tags": "|".join(str(tag) for tag in ticket.get("tags") or []),
        "description_text": ticket.get("description_text") or ticket.get("description"),
        "conversations_count": len(conversations),
        "ticket_attachments_count": attachment_count,
        "conversation_attachments_count": conversation_attachment_count,
        "ticket_json": json.dumps(ticket, ensure_ascii=False, sort_keys=True),
        "conversations_json": json.dumps(conversations, ensure_ascii=False, sort_keys=True),
    }
    for key, value in sorted(custom_fields.items()):
        row[f"custom_fields.{key}"] = value
    return row


def cell(value: Any) -> str:
    text = "" if value is None else str(value)
    text = "".join(char for char in text if char in "\t\n\r" or ord(char) >= 32)
    return f"<c t=\"inlineStr\"><is><t xml:space=\"preserve\">{escape(text)}</t></is></c>"


def sheet_xml(rows: list[list[Any]]) -> str:
    rendered_rows = []
    for index, row in enumerate(rows, start=1):
        rendered_rows.append(f"<row r=\"{index}\">{''.join(cell(value) for value in row)}</row>")
    return (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<worksheet xmlns=\"http://schemas.openxmlformats.org/spreadsheetml/2006/main\">"
        "<sheetData>"
        f"{''.join(rendered_rows)}"
        "</sheetData></worksheet>"
    )


def write_xlsx_export(path: Path, records: list[dict[str, Any]]) -> None:
    """Write ticket, conversation, and metadata sheets as one XLSX package."""
    ticket_rows = [flatten_ticket_for_workbook(record) for record in records]
    fieldnames: list[str] = []
    for row in ticket_rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    tickets_sheet = [fieldnames or ["id"], *[[row.get(field) for field in fieldnames] for row in ticket_rows]]

    conversation_rows: list[list[Any]] = [["ticket_id", "conversation_index", "conversation_json"]]
    for record in records:
        ticket_id = record["ticket"].get("id")
        for index, conversation in enumerate(record["conversations"], start=1):
            conversation_rows.append(
                [ticket_id, index, json.dumps(conversation, ensure_ascii=False, sort_keys=True)]
            )

    metadata_rows = [
        ["schema_version", "1.0"],
        ["exported_at", records[0]["exported_at"] if records else ""],
        ["freshdesk_domain", records[0]["freshdesk_domain"] if records else ""],
        ["query", records[0]["query"] if records else ""],
        ["count", len(records)],
    ]

    workbook_xml = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<workbook xmlns=\"http://schemas.openxmlformats.org/spreadsheetml/2006/main\" "
        "xmlns:r=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships\">"
        "<sheets>"
        "<sheet name=\"Tickets\" sheetId=\"1\" r:id=\"rId1\"/>"
        "<sheet name=\"Conversations\" sheetId=\"2\" r:id=\"rId2\"/>"
        "<sheet name=\"Metadata\" sheetId=\"3\" r:id=\"rId3\"/>"
        "</sheets></workbook>"
    )
    workbook_rels = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\">"
        "<Relationship Id=\"rId1\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet\" Target=\"worksheets/sheet1.xml\"/>"
        "<Relationship Id=\"rId2\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet\" Target=\"worksheets/sheet2.xml\"/>"
        "<Relationship Id=\"rId3\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet\" Target=\"worksheets/sheet3.xml\"/>"
        "</Relationships>"
    )
    package_rels = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\">"
        "<Relationship Id=\"rId1\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument\" Target=\"xl/workbook.xml\"/>"
        "</Relationships>"
    )
    content_types = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<Types xmlns=\"http://schemas.openxmlformats.org/package/2006/content-types\">"
        "<Default Extension=\"rels\" ContentType=\"application/vnd.openxmlformats-package.relationships+xml\"/>"
        "<Default Extension=\"xml\" ContentType=\"application/xml\"/>"
        "<Override PartName=\"/xl/workbook.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml\"/>"
        "<Override PartName=\"/xl/worksheets/sheet1.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml\"/>"
        "<Override PartName=\"/xl/worksheets/sheet2.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml\"/>"
        "<Override PartName=\"/xl/worksheets/sheet3.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml\"/>"
        "</Types>"
    )

    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", package_rels)
        archive.writestr("xl/workbook.xml", workbook_xml)
        archive.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        archive.writestr("xl/worksheets/sheet1.xml", sheet_xml(tickets_sheet))
        archive.writestr("xl/worksheets/sheet2.xml", sheet_xml(conversation_rows))
        archive.writestr("xl/worksheets/sheet3.xml", sheet_xml(metadata_rows))
