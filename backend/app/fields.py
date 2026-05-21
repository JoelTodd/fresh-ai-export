"""Translate Freshdesk ticket-field metadata into UI filter definitions.

Freshdesk accounts can expose standard fields, custom fields, and choices in
several shapes. This module normalizes those variants into a small schema the
React builder can render consistently.
"""

from __future__ import annotations

from typing import Any

from .schemas import FieldChoice, FilterField

STATUS_CHOICES = [
    FieldChoice(label="Open", value=2),
    FieldChoice(label="Pending", value=3),
    FieldChoice(label="Resolved", value=4),
    FieldChoice(label="Closed", value=5),
]

PRIORITY_CHOICES = [
    FieldChoice(label="Low", value=1),
    FieldChoice(label="Medium", value=2),
    FieldChoice(label="High", value=3),
    FieldChoice(label="Urgent", value=4),
]

SEARCHABLE_STANDARD_KEYS = {
    "agent_id",
    "created_at",
    "due_by",
    "fr_due_by",
    "group_id",
    "priority",
    "status",
    "tag",
    "type",
    "updated_at",
}

NUMERIC_STANDARD_KEYS = {
    "agent_id",
    "group_id",
    "priority",
    "status",
}

LOOKUP_ALIASES: dict[str, tuple[str, ...]] = {
    "agent_id": ("agent", "agents", "responder", "responder_id"),
    "responder_id": ("agent", "agents", "agent_id", "responder"),
    "group_id": ("group", "groups"),
    "company_id": ("company", "companies"),
    "product_id": ("product", "products"),
    "requester_id": ("requester", "requesters", "contact", "contacts"),
    "tag": ("tags",),
}

SEARCH_KEY_ALIASES: dict[str, str] = {
    "agent": "agent_id",
    "agents": "agent_id",
    "responder": "responder_id",
    "group": "group_id",
    "groups": "group_id",
    "company": "company_id",
    "companies": "company_id",
    "product": "product_id",
    "products": "product_id",
    "requester": "requester_id",
    "requesters": "requester_id",
    "contact": "requester_id",
    "contacts": "requester_id",
    "tags": "tag",
}

LOOKUP_VALUE_TYPES: dict[str, str] = {
    "agent_id": "number",
    "responder_id": "number",
    "group_id": "number",
    "company_id": "number",
    "product_id": "number",
    "requester_id": "number",
    "tag": "text",
}


STANDARD_FIELDS: list[FilterField] = [
    FilterField(
        name="status",
        search_key="status",
        label="Status",
        type="number",
        source="standard",
        choices=STATUS_CHOICES,
        operators=["eq", "neq"],
    ),
    FilterField(
        name="priority",
        search_key="priority",
        label="Priority",
        type="number",
        source="standard",
        choices=PRIORITY_CHOICES,
        operators=["eq", "neq"],
    ),
    FilterField(
        name="group_id",
        search_key="group_id",
        label="Group",
        type="number",
        source="standard",
        operators=["eq", "neq"],
    ),
    FilterField(
        name="agent_id",
        search_key="agent_id",
        label="Agent",
        type="number",
        source="standard",
        operators=["eq", "neq"],
    ),
    FilterField(
        name="tag",
        search_key="tag",
        label="Tag",
        type="text",
        source="standard",
        operators=["eq", "neq"],
    ),
    FilterField(
        name="type",
        search_key="type",
        label="Type",
        type="text",
        source="standard",
        operators=["eq", "neq"],
    ),
    FilterField(
        name="created_at",
        search_key="created_at",
        label="Created at",
        type="date",
        source="standard",
        operators=["eq", "neq", "gt", "lt", "between"],
    ),
    FilterField(
        name="updated_at",
        search_key="updated_at",
        label="Updated at",
        type="date",
        source="standard",
        operators=["eq", "neq", "gt", "lt", "between"],
    ),
    FilterField(
        name="due_by",
        search_key="due_by",
        label="Due by",
        type="date",
        source="standard",
        operators=["eq", "neq", "gt", "lt", "between"],
    ),
    FilterField(
        name="fr_due_by",
        search_key="fr_due_by",
        label="First response due by",
        type="date",
        source="standard",
        operators=["eq", "neq", "gt", "lt", "between"],
    ),
]


def is_disabled(raw: dict[str, Any]) -> bool:
    return (
        raw.get("deleted") is True
        or raw.get("archived") is True
        or raw.get("active") is False
        or raw.get("visible") is False
    )


def is_number_like(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        return True
    if isinstance(value, str):
        return value.strip().isdigit()
    return False


def normalize_choice_value(value: Any) -> Any:
    if isinstance(value, str) and value.strip().isdigit():
        return int(value)
    return value


def is_positive_integer_value(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return value > 0
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip()) > 0
    return False


def numeric_choices_only(choices: list[FieldChoice]) -> list[FieldChoice]:
    return [choice for choice in choices if is_positive_integer_value(choice.value)]


def sort_choices(choices: list[tuple[int | None, FieldChoice]]) -> list[FieldChoice]:
    return [
        choice
        for _, choice in sorted(
            choices,
            key=lambda item: (
                item[0] is None,
                item[0] if item[0] is not None else 0,
                item[1].label.casefold(),
            ),
        )
    ]


def merge_choice_fallbacks(
    freshdesk_choices: list[FieldChoice],
    fallback_choices: list[FieldChoice],
) -> list[FieldChoice]:
    if not freshdesk_choices:
        return fallback_choices
    by_value = {str(choice.value): choice for choice in freshdesk_choices}
    for fallback in fallback_choices:
        by_value.setdefault(str(fallback.value), fallback)
    return list(by_value.values())


def normalize_choices(raw: Any) -> list[FieldChoice]:
    """Normalize Freshdesk's list/dict choice variants into label/value pairs."""
    if not raw:
        return []
    if isinstance(raw, dict):
        choices: list[tuple[int | None, FieldChoice]] = []
        for key, value in raw.items():
            if isinstance(value, dict):
                if is_disabled(value):
                    continue
                label = value.get("label") or value.get("name") or value.get("value") or key
                choice_value = value.get("value", key)
                position = value.get("position")
            elif is_number_like(key) and not is_number_like(value):
                label = value
                choice_value = key
                position = int(key) if str(key).isdigit() else None
            else:
                label = key
                choice_value = value
                position = int(value) if is_number_like(value) else None
            choices.append(
                (
                    position if isinstance(position, int) else None,
                    FieldChoice(label=str(label), value=normalize_choice_value(choice_value)),
                )
            )
        return sort_choices(choices)
    if isinstance(raw, list):
        choices: list[tuple[int | None, FieldChoice]] = []
        for item in raw:
            if isinstance(item, dict):
                if is_disabled(item):
                    continue
                label = item.get("label") or item.get("name") or item.get("value")
                value = item.get("value", label)
                position = item.get("position")
                choices.append(
                    (
                        position if isinstance(position, int) else None,
                        FieldChoice(label=str(label), value=normalize_choice_value(value)),
                    )
                )
            else:
                choices.append((None, FieldChoice(label=str(item), value=normalize_choice_value(item))))
        return sort_choices(choices)
    return [FieldChoice(label=str(raw), value=raw)]


def infer_type(field: dict[str, Any]) -> str:
    raw_type = str(field.get("type") or field.get("field_type") or "text").lower()
    if raw_type in {"date", "datetime", "custom_date"}:
        return "date"
    if raw_type in {"number", "decimal", "integer", "lookup", "dependent_field", "custom_number"}:
        return "number"
    if raw_type in {"checkbox", "boolean", "custom_checkbox"}:
        return "boolean"
    if raw_type in {"dropdown", "nested_field", "multi_select_dropdown", "custom_dropdown"}:
        return "choice"
    return "text"


def operators_for(field_type: str, has_choices: bool) -> list[str]:
    if field_type == "date":
        return ["eq", "neq", "gt", "lt", "between"]
    return ["eq", "neq"]


def is_custom_field(field: dict[str, Any], name: str) -> bool:
    return (
        name.startswith("cf_")
        or bool(field.get("custom_field"))
        or field.get("default") is False
        or field.get("type") == "custom_field"
    )


def field_from_metadata(field: dict[str, Any]) -> FilterField | None:
    """Return a UI-safe filter field, or None for disabled metadata."""
    if is_disabled(field):
        return None
    name = str(field.get("name") or "").strip()
    if not name:
        return None
    search_key = SEARCH_KEY_ALIASES.get(name, name)
    field_type = infer_type(field)
    choices = normalize_choices(field.get("choices"))
    source = "custom" if is_custom_field(field, name) else "freshdesk"
    label = str(field.get("label") or field.get("label_for_customers") or name)
    validation = {
        key: value
        for key, value in field.items()
        if key
        in {
            "required_for_agents",
            "required_for_closure",
            "required_for_customers",
            "regexp_for_validation",
            "customers_can_edit",
            "displayed_to_customers",
            "position",
        }
        and value is not None
    }
    return FilterField(
        name=name,
        search_key=search_key,
        label=label,
        type=field_type,
        source=source,
        choices=choices,
        operators=operators_for(field_type, bool(choices)),
        required=bool(field.get("required_for_agents") or field.get("required_for_closure")),
        validation=validation,
    )


def apply_lookup_choices(
    fields: list[FilterField],
    lookup_choices: dict[str, list[FieldChoice]] | None,
) -> list[FilterField]:
    """Replace opaque ID fields with human-readable choices when lookups exist."""
    if not lookup_choices:
        return fields
    hydrated: list[FilterField] = []
    for field in fields:
        canonical_key = SEARCH_KEY_ALIASES.get(field.search_key, field.search_key)
        lookup_keys = (
            field.name,
            field.search_key,
            *LOOKUP_ALIASES.get(field.name, ()),
            *LOOKUP_ALIASES.get(field.search_key, ()),
            *(
                key
                for key, aliases in LOOKUP_ALIASES.items()
                if field.name in aliases or field.search_key in aliases
            ),
        )
        choices = next((lookup_choices[key] for key in lookup_keys if lookup_choices.get(key)), None)
        if choices:
            hydrated.append(
                field.model_copy(
                    update={
                        "choices": choices,
                        "type": LOOKUP_VALUE_TYPES.get(canonical_key, field.type),
                        "operators": field.operators if field.operators else ["eq"],
                    }
                )
            )
        else:
            hydrated.append(field)
    return hydrated


def build_filter_fields(
    ticket_fields: list[dict[str, Any]],
    lookup_choices: dict[str, list[FieldChoice]] | None = None,
) -> list[FilterField]:
    discovered = [
        field
        for raw in ticket_fields
        if (field := field_from_metadata(raw))
        and (field.source == "custom" or field.search_key in SEARCHABLE_STANDARD_KEYS)
    ]
    by_search_key = {field.search_key: field for field in discovered}
    fields: list[FilterField] = []
    for standard in STANDARD_FIELDS:
        discovered_standard = by_search_key.pop(standard.search_key, None)
        if discovered_standard:
            choices = merge_choice_fallbacks(discovered_standard.choices, standard.choices)
            if standard.search_key in NUMERIC_STANDARD_KEYS:
                choices = numeric_choices_only(choices)
                if not choices:
                    choices = standard.choices
            fields.append(
                discovered_standard.model_copy(
                    update={
                        "choices": choices,
                        "type": standard.type,
                        "operators": discovered_standard.operators or standard.operators,
                    }
                )
            )
        else:
            fields.append(standard)
    fields.extend(
        sorted(by_search_key.values(), key=lambda item: (item.source != "custom", item.label.lower()))
    )
    return apply_lookup_choices(fields, lookup_choices)
