"""App-side filtering for operators Freshdesk search cannot express."""

from __future__ import annotations

from typing import Any

from .query import NEGATIVE_OPERATORS, can_expand_negative_condition
from .schemas import FilterCondition

FIELD_VALUE_ALIASES: dict[str, tuple[str, ...]] = {
    "agent_id": ("agent_id", "responder_id"),
    "tag": ("tag", "tags"),
    "tags": ("tag", "tags"),
}


def exclusion_conditions(filters: list[FilterCondition]) -> list[FilterCondition]:
    return [
        condition
        for condition in filters
        if condition.operator in NEGATIVE_OPERATORS and not can_expand_negative_condition(condition)
    ]


def ticket_field_value(ticket: dict[str, Any], field: str) -> Any:
    if field.startswith("cf_"):
        custom_fields = ticket.get("custom_fields") if isinstance(ticket.get("custom_fields"), dict) else {}
        return custom_fields.get(field)
    for key in FIELD_VALUE_ALIASES.get(field, (field,)):
        if key in ticket:
            return ticket.get(key)
    return None


def values_equal(actual: Any, expected: Any, field_type: str | None = None) -> bool:
    if isinstance(actual, list):
        return any(values_equal(item, expected, field_type) for item in actual)
    if expected is None or str(expected).casefold() == "null":
        return actual is None or actual == ""
    if field_type in {"number", "integer", "decimal"}:
        try:
            return float(actual) == float(expected)
        except (TypeError, ValueError):
            return False
    if isinstance(actual, bool):
        return str(actual).lower() == str(expected).lower()
    return str(actual) == str(expected)


def is_excluded(ticket: dict[str, Any], exclusions: list[FilterCondition]) -> bool:
    return any(
        values_equal(ticket_field_value(ticket, condition.field), condition.value, condition.type)
        for condition in exclusions
    )


def apply_exclusions(
    tickets: list[dict[str, Any]],
    exclusions: list[FilterCondition],
) -> list[dict[str, Any]]:
    if not exclusions:
        return tickets
    return [ticket for ticket in tickets if not is_excluded(ticket, exclusions)]
