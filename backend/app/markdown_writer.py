"""Markdown writer for AI-readable Freshdesk ticket exports."""

from __future__ import annotations

import html
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

TICKET_SUMMARY_FIELDS = [
    "status",
    "priority",
    "type",
    "source",
    "requester_id",
    "responder_id",
    "group_id",
    "company_id",
    "created_at",
    "updated_at",
    "due_by",
    "fr_due_by",
]
TICKET_EMAIL_FIELDS = [
    "to_emails",
    "cc_emails",
    "reply_cc_emails",
    "fwd_emails",
    "ticket_cc_emails",
    "ticket_bcc_emails",
    "support_email",
]
CONVERSATION_SUMMARY_FIELDS = [
    "id",
    "created_at",
    "updated_at",
    "incoming",
    "private",
    "category",
    "source",
    "from_email",
    "to_emails",
    "cc_emails",
    "bcc_emails",
    "user_id",
    "support_email",
]
TICKET_MARKDOWN_KEYS = {
    "id",
    "subject",
    "description",
    "description_text",
    "structured_description",
    "attachments",
    "custom_fields",
    "email_config_id",
    "tags",
    *TICKET_SUMMARY_FIELDS,
    *TICKET_EMAIL_FIELDS,
}
CONVERSATION_MARKDOWN_KEYS = {
    "ticket_id",
    "email_config_id",
    "body",
    "body_text",
    "structured_body",
    "attachments",
    *CONVERSATION_SUMMARY_FIELDS,
}


class PlainTextHTMLParser(HTMLParser):
    """Keep readable line breaks while reducing Freshdesk HTML to plain text."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in {"br", "div", "p", "tr", "li", "blockquote", "hr"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"div", "p", "tr", "li", "blockquote"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        self.parts.append(data)

    def text(self) -> str:
        return "".join(self.parts)


def is_empty_markdown_value(value: Any) -> bool:
    return value is None or value is False or value == "" or value == [] or value == {}


def normalize_markdown_text(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    text = html.unescape(value).replace("\r\n", "\n").replace("\r", "\n").replace("\xa0", " ")
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.split("\n")]
    normalized: list[str] = []
    previous_blank = True
    for line in lines:
        if line:
            normalized.append(line)
            previous_blank = False
        elif not previous_blank:
            normalized.append("")
            previous_blank = True
    return "\n".join(normalized).strip()


def html_to_text(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    parser = PlainTextHTMLParser()
    parser.feed(value)
    parser.close()
    return normalize_markdown_text(parser.text())


def preferred_text(payload: dict[str, Any], text_key: str, html_key: str) -> str:
    text = normalize_markdown_text(payload.get(text_key))
    if text:
        return text
    return html_to_text(payload.get(html_key))


def compact_for_markdown(value: Any, skip_keys: set[str] | None = None) -> Any:
    skip_keys = skip_keys or set()
    if isinstance(value, dict):
        compacted = {
            key: compact_for_markdown(item, skip_keys)
            for key, item in sorted(value.items())
            if key not in skip_keys
        }
        return {
            key: item
            for key, item in compacted.items()
            if not is_empty_markdown_value(item)
        }
    if isinstance(value, list):
        compacted_list = [compact_for_markdown(item, skip_keys) for item in value]
        return [item for item in compacted_list if not is_empty_markdown_value(item)]
    return value


def markdown_scalar(value: Any) -> str:
    if isinstance(value, list):
        return ", ".join(markdown_scalar(item) for item in value if not is_empty_markdown_value(item))
    if isinstance(value, dict):
        return json.dumps(compact_for_markdown(value), ensure_ascii=False, sort_keys=True)
    return str(value)


def markdown_bullet(label: str, value: Any) -> str | None:
    if is_empty_markdown_value(value):
        return None
    text = markdown_scalar(value).replace("\n", "<br>").replace("|", "\\|")
    return f"- {label}: {text}"


def markdown_bullets(payload: dict[str, Any], fields: list[str]) -> list[str]:
    bullets: list[str] = []
    for field in fields:
        bullet = markdown_bullet(field, payload.get(field))
        if bullet:
            bullets.append(bullet)
    return bullets


def markdown_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def append_json_section(parts: list[str], title: str, value: Any) -> None:
    if is_empty_markdown_value(value):
        return
    parts.extend([title, "", "```json", markdown_json(value), "```", ""])


def append_attachment_section(parts: list[str], title: str, attachments: Any) -> None:
    compacted = compact_for_markdown(attachments)
    if not isinstance(compacted, list) or not compacted:
        return
    parts.extend([title, ""])
    for index, attachment in enumerate(compacted, start=1):
        if isinstance(attachment, dict):
            name = attachment.get("name") or attachment.get("file_name") or attachment.get("attachment_url") or f"Attachment {index}"
            details = markdown_json(attachment)
            parts.append(f"- {name}: `{details}`")
        else:
            parts.append(f"- {markdown_scalar(attachment)}")
    parts.append("")


def append_custom_fields(parts: list[str], custom_fields: Any) -> None:
    compacted = compact_for_markdown(custom_fields)
    if not isinstance(compacted, dict) or not compacted:
        return
    parts.extend(["### Custom fields", ""])
    for key, value in compacted.items():
        parts.append(f"- {key}: {markdown_scalar(value)}")
    parts.append("")


def append_conversation(parts: list[str], conversation: dict[str, Any], index: int) -> None:
    created_at = conversation.get("created_at") or "unknown time"
    direction = "incoming" if conversation.get("incoming") else "outgoing"
    visibility = "private note" if conversation.get("private") else "public reply"
    parts.extend([f"#### {index}. {created_at} - {direction}, {visibility}", ""])
    metadata = markdown_bullets(conversation, CONVERSATION_SUMMARY_FIELDS)
    if metadata:
        parts.extend(metadata)
        parts.append("")
    text = preferred_text(conversation, "body_text", "body")
    if text:
        parts.extend([text, ""])
    append_attachment_section(parts, "Attachments", conversation.get("attachments"))
    additional = compact_for_markdown(conversation, CONVERSATION_MARKDOWN_KEYS)
    append_json_section(parts, "Additional conversation data", additional)


def write_markdown_export(path: Path, records: list[dict[str, Any]]) -> None:
    parts = [
        "# Freshdesk ticket export",
        "",
        "This file is optimized for AI ingestion. Descriptions and conversations are rendered as readable text; empty fields and redundant raw HTML are omitted. Non-empty fields not shown elsewhere are preserved as compact JSON.",
        "",
        f"Record count: {len(records)}",
        "",
    ]
    for index, record in enumerate(records, start=1):
        ticket = record["ticket"]
        ticket_id = ticket.get("id", f"index-{index}") if isinstance(ticket, dict) else f"index-{index}"
        subject = ticket.get("subject") if isinstance(ticket, dict) else None
        title = f"## Ticket {ticket_id}"
        if subject:
            title = f"{title}: {normalize_markdown_text(subject)}"
        metadata = {
            key: value
            for key, value in record.items()
            if key not in {"ticket", "conversations"} and not is_empty_markdown_value(value)
        }
        conversations = record["conversations"] if isinstance(record.get("conversations"), list) else []
        parts.extend([title, "", "### Key fields", ""])
        parts.extend(markdown_bullets(ticket, TICKET_SUMMARY_FIELDS + TICKET_EMAIL_FIELDS))
        tags = markdown_bullet("tags", ticket.get("tags"))
        if tags:
            parts.append(tags)
        parts.append("")

        description = preferred_text(ticket, "description_text", "description")
        if description:
            parts.extend(["### Description", "", description, ""])

        append_custom_fields(parts, ticket.get("custom_fields"))
        append_attachment_section(parts, "### Ticket attachments", ticket.get("attachments"))

        additional_ticket = compact_for_markdown(ticket, TICKET_MARKDOWN_KEYS)
        append_json_section(parts, "### Additional ticket data", additional_ticket)
        append_json_section(parts, "### Export metadata", metadata)

        parts.extend([f"### Conversations ({len(conversations)})", ""])
        for conversation_index, conversation in enumerate(conversations, start=1):
            if isinstance(conversation, dict):
                append_conversation(parts, conversation, conversation_index)
            else:
                parts.extend([f"#### {conversation_index}. Conversation", "", markdown_json(conversation), ""])
    path.write_text("\n".join(parts), encoding="utf-8")
