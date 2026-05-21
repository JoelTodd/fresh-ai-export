"""Freshdesk search query construction and validation."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from urllib.parse import urlencode

from .schemas import FilterCondition

MAX_WRAPPED_QUERY_LENGTH = 512
BROAD_SEARCH_QUERY = "created_at:>'1970-01-01'"
NEGATIVE_OPERATORS = {"neq", "not", "is_not"}


class QueryError(ValueError):
    pass


def strip_wrapping_quotes(query: str) -> str:
    query = query.strip()
    if len(query) >= 2 and query[0] == '"' and query[-1] == '"':
        return query[1:-1].strip()
    return query


def wrap_query(query: str) -> str:
    """Apply Freshdesk's required wrapping quotes and enforce its length limit."""
    clean = strip_wrapping_quotes(query)
    if not clean:
        raise QueryError("Freshdesk query cannot be empty.")
    wrapped = f'"{clean}"'
    if len(wrapped) > MAX_WRAPPED_QUERY_LENGTH:
        raise QueryError(
            f"Freshdesk search query is {len(wrapped)} characters wrapped; limit is 512."
        )
    return wrapped


def encode_query(query: str) -> str:
    return urlencode({"query": wrap_query(query)})


def _needs_quotes(value: Any, field_type: str | None) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float)) and field_type not in {"date", "datetime"}:
        return False
    if isinstance(value, str) and field_type in {"number", "integer", "decimal"}:
        return not value.strip().isdigit()
    return True


def format_value(value: Any, field_type: str | None = None) -> str:
    if value is None or value == "":
        raise QueryError("Filter value cannot be empty.")
    if isinstance(value, list):
        return ",".join(format_value(item, field_type) for item in value)
    if isinstance(value, bool):
        return "true" if value else "false"
    if field_type in {"number", "integer", "decimal"}:
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return str(value)
        if isinstance(value, str) and value.strip().isdigit():
            return str(int(value.strip()))
        raise QueryError("Numeric filters must use a positive integer value.")
    if _needs_quotes(value, field_type):
        escaped = str(value).replace("\\", "\\\\").replace("'", "\\'")
        return f"'{escaped}'"
    return str(value)


def condition_to_query(condition: FilterCondition) -> str:
    field = condition.field.strip()
    if not field:
        raise QueryError("Filter field cannot be empty.")
    operator = condition.operator
    field_type = condition.type

    if operator in {"eq", "is"}:
        return f"{field}:{format_value(condition.value, field_type)}"
    if operator in {"neq", "not", "is_not"}:
        expanded = expanded_negative_condition(condition)
        if expanded:
            return expanded
        raise QueryError("'is not' filters must be applied after Freshdesk search.")
    if operator == "contains":
        return f"{field}:{format_value(condition.value, field_type)}"
    if operator == "in":
        values = condition.value if isinstance(condition.value, list) else [condition.value]
        parts = [f"{field}:{format_value(item, field_type)}" for item in values if item not in {None, ""}]
        if not parts:
            raise QueryError("At least one value is required for an IN filter.")
        return "(" + " OR ".join(parts) + ")"
    if operator in {"after", "gte"}:
        return f"{field}:>{format_value(condition.value, field_type or 'date')}"
    if operator in {"before", "lte"}:
        return f"{field}:<{format_value(condition.value, field_type or 'date')}"
    if operator == "between":
        return (
            f"{field}:>{format_value(condition.value, field_type or 'date')} AND "
            f"{field}:<{format_value(condition.value_to, field_type or 'date')}"
        )
    raise QueryError(f"Unsupported operator: {operator}")


def expanded_negative_condition(condition: FilterCondition) -> str | None:
    """Represent finite-choice 'is not' filters as a positive OR query."""
    if condition.operator not in NEGATIVE_OPERATORS or not condition.choices:
        return None
    field = condition.field.strip()
    if not field:
        raise QueryError("Filter field cannot be empty.")
    alternatives = [
        choice
        for choice in condition.choices
        if choice not in {None, ""} and str(choice) != str(condition.value)
    ]
    if not alternatives:
        return None
    return condition_to_query(
        FilterCondition(
            field=field,
            operator="in",
            value=alternatives,
            type=condition.type,
        )
    )


def can_expand_negative_condition(condition: FilterCondition) -> bool:
    return expanded_negative_condition(condition) is not None


def build_query(filters: list[FilterCondition], raw_query: str | None = None) -> str:
    raw = strip_wrapping_quotes(raw_query or "")
    searchable_filters = [
        condition
        for condition in filters
        if condition.operator not in NEGATIVE_OPERATORS or can_expand_negative_condition(condition)
    ]
    has_negative_filters = len(searchable_filters) != len(filters)
    parts = [condition_to_query(condition) for condition in searchable_filters]
    if raw:
        parts.append(f"({raw})" if parts else raw)
    if not parts and has_negative_filters:
        # Freshdesk cannot search on an open-ended negative condition. Start
        # from a broad positive query so the backend can filter records after.
        parts.append(BROAD_SEARCH_QUERY)
    query = " AND ".join(parts).strip()
    wrap_query(query)
    return query


def freshdesk_date(value: str) -> str:
    clean = value.strip()
    if "T" not in clean:
        return clean[:10]
    normalized = clean.replace("Z", "+00:00")
    return datetime.fromisoformat(normalized).date().isoformat()


def append_date_window(query: str, split_field: str, start_iso: str, end_iso: str) -> str:
    """Add an exclusive date window around an already-built search query."""
    window = (
        f"{split_field}:>{format_value(freshdesk_date(start_iso), 'date')} AND "
        f"{split_field}:<{format_value(freshdesk_date(end_iso), 'date')}"
    )
    return build_query([], f"({query}) AND {window}")
