"""Best-effort lookup hydration for Freshdesk ID-backed fields."""

from __future__ import annotations

import asyncio
from typing import Any, Awaitable

from .schemas import FieldChoice
from .freshdesk import FreshdeskClient, FreshdeskError


def compact_label(*parts: Any) -> str:
    return " ".join(str(part).strip() for part in parts if part not in {None, ""}).strip()


def agent_label(agent: dict[str, Any]) -> str:
    contact = agent.get("contact") if isinstance(agent.get("contact"), dict) else {}
    return (
        compact_label(contact.get("name"))
        or compact_label(agent.get("name"))
        or compact_label(contact.get("email"))
        or f"Agent {agent.get('id')}"
    )


def named_choice(item: dict[str, Any], fallback: str) -> FieldChoice | None:
    item_id = item.get("id")
    if item_id is None:
        return None
    label = compact_label(item.get("name")) or f"{fallback} {item_id}"
    return FieldChoice(label=label, value=item_id)


def contact_choice(item: dict[str, Any]) -> FieldChoice | None:
    item_id = item.get("id")
    if item_id is None:
        return None
    label = compact_label(item.get("name")) or compact_label(item.get("email")) or f"Requester {item_id}"
    return FieldChoice(label=label, value=item_id)


def agent_choice(item: dict[str, Any]) -> FieldChoice | None:
    item_id = item.get("id")
    if item_id is None:
        return None
    return FieldChoice(label=agent_label(item), value=item_id)


def tag_choice(item: Any) -> FieldChoice | None:
    if isinstance(item, str):
        label = item.strip()
        return FieldChoice(label=label, value=label) if label else None
    if isinstance(item, dict):
        label = compact_label(item.get("name")) or compact_label(item.get("tag"))
        return FieldChoice(label=label, value=label) if label else None
    return None


async def safe_lookup(call: Awaitable[Any]) -> list[dict[str, Any]]:
    """Return an empty choice list when optional lookup endpoints are unavailable."""
    try:
        result = await call
    except FreshdeskError:
        return []
    return result.data if isinstance(result.data, list) else []


def dedupe_choices(choices: list[FieldChoice]) -> list[FieldChoice]:
    seen: set[str] = set()
    deduped: list[FieldChoice] = []
    for choice in sorted(choices, key=lambda item: item.label.casefold()):
        key = str(choice.value)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(choice)
    return deduped


async def fetch_lookup_choices(client: FreshdeskClient) -> dict[str, list[FieldChoice]]:
    agents, groups, tags = await asyncio.gather(
        safe_lookup(client.agents()),
        safe_lookup(client.groups()),
        safe_lookup(client.tags()),
    )

    agent_choices = dedupe_choices(
        [choice for item in agents if (choice := agent_choice(item)) is not None]
    )
    group_choices = dedupe_choices(
        [choice for item in groups if (choice := named_choice(item, "Group")) is not None]
    )
    tag_choices = dedupe_choices(
        [choice for item in tags if (choice := tag_choice(item)) is not None]
    )

    return {
        "agent_id": agent_choices,
        "responder_id": agent_choices,
        "group_id": group_choices,
        "tag": tag_choices,
    }
