from app.fields import build_filter_fields
from app.schemas import FieldChoice


def test_dynamic_filter_generation_from_ticket_fields() -> None:
    fields = build_filter_fields(
        [
            {
                "name": "status",
                "label": "Ticket Status",
                "type": "default_status",
                "choices": {"Open": 2, "Pending": 3},
            },
            {
                "name": "cf_product_line",
                "label": "Product Line",
                "type": "dropdown",
                "choices": ["Core", "Enterprise"],
                "required_for_agents": True,
                "regexp_for_validation": None,
            },
        ]
    )

    by_name = {field.name: field for field in fields}

    assert by_name["status"].label == "Ticket Status"
    assert by_name["status"].choices[0].label == "Open"
    assert by_name["cf_product_line"].source == "custom"
    assert by_name["cf_product_line"].search_key == "cf_product_line"
    assert by_name["cf_product_line"].choices[1].value == "Enterprise"
    assert by_name["cf_product_line"].required is True
    assert by_name["cf_product_line"].operators == ["eq", "neq"]


def test_choice_maps_use_human_labels_for_numeric_keys() -> None:
    fields = build_filter_fields(
        [
            {
                "name": "status",
                "label": "Status",
                "type": "default_status",
                "choices": {"2": "Open", "3": "Pending"},
            },
            {
                "name": "cf_region",
                "label": "Region",
                "type": "custom_dropdown",
                "choices": {"30": "North", "10": "South"},
            },
        ]
    )
    by_name = {field.name: field for field in fields}

    assert [(choice.label, choice.value) for choice in by_name["status"].choices[:2]] == [
        ("Open", 2),
        ("Pending", 3),
    ]
    assert [(choice.label, choice.value) for choice in by_name["cf_region"].choices] == [
        ("South", 10),
        ("North", 30),
    ]


def test_deleted_and_inactive_custom_fields_and_choices_are_hidden() -> None:
    fields = build_filter_fields(
        [
            {
                "name": "cf_old_field",
                "label": "Old field",
                "type": "custom_dropdown",
                "active": False,
                "choices": [{"value": "Old", "position": 1}],
            },
            {
                "name": "cf_current_field",
                "label": "Current field",
                "type": "custom_dropdown",
                "choices": [
                    {"value": "Current", "position": 2},
                    {"value": "Removed", "position": 1, "deleted": True},
                ],
            },
        ]
    )
    by_name = {field.name: field for field in fields}

    assert "cf_old_field" not in by_name
    assert [choice.label for choice in by_name["cf_current_field"].choices] == ["Current"]


def test_status_gets_default_freshdesk_choices_when_metadata_is_sparse() -> None:
    fields = build_filter_fields(
        [
            {
                "name": "status",
                "label": "Status",
                "type": "default_status",
                "choices": {"8": "Waiting on customer"},
            }
        ]
    )
    status = {field.name: field for field in fields}["status"]

    assert ("Open", 2) in [(choice.label, choice.value) for choice in status.choices]
    assert ("Waiting on customer", 8) in [(choice.label, choice.value) for choice in status.choices]


def test_standard_fallbacks_are_present_without_metadata() -> None:
    fields = build_filter_fields([])
    names = {field.name for field in fields}

    assert {"status", "priority", "group_id", "agent_id", "created_at", "updated_at"} <= names
    assert {"requester_id", "company_id", "product_id", "responder_id"}.isdisjoint(names)


def test_lookup_choices_hydrate_id_backed_fields() -> None:
    fields = build_filter_fields(
        [],
        {
            "agent_id": [
                FieldChoice(label="Ada Lovelace", value=42),
            ],
            "group_id": [
                FieldChoice(label="Support", value=100),
            ],
        },
    )
    by_name = {field.name: field for field in fields}

    assert by_name["agent_id"].type == "number"
    assert by_name["agent_id"].choices[0].label == "Ada Lovelace"
    assert by_name["agent_id"].choices[0].value == 42
    assert by_name["agent_id"].operators == ["eq", "neq"]
    assert by_name["group_id"].choices[0].label == "Support"


def test_lookup_choices_hydrate_agent_metadata_aliases() -> None:
    fields = build_filter_fields(
        [
            {
                "name": "agents",
                "label": "Agents",
                "type": "default_agent",
            }
        ],
        {
            "agent_id": [
                FieldChoice(label="Ada Lovelace", value=42),
            ],
        },
    )
    by_name = {field.name: field for field in fields}

    assert by_name["agents"].search_key == "agent_id"
    assert by_name["agents"].type == "number"
    assert by_name["agents"].choices[0].label == "Ada Lovelace"
    assert by_name["agents"].choices[0].value == 42


def test_id_backed_metadata_choices_keep_only_numeric_values() -> None:
    fields = build_filter_fields(
        [
            {
                "name": "agents",
                "label": "Agents",
                "type": "default_agent",
                "choices": ["Ada Lovelace", {"label": "Grace Hopper", "value": "42"}],
            }
        ]
    )
    agents = {field.search_key: field for field in fields}["agent_id"]

    assert [(choice.label, choice.value) for choice in agents.choices] == [("Grace Hopper", 42)]


def test_standard_numeric_fields_keep_numeric_type_after_metadata_merge() -> None:
    fields = build_filter_fields(
        [
            {
                "name": "agents",
                "label": "Agent",
                "type": "dropdown",
                "choices": [{"label": "Joel Todd", "value": "103147792207"}],
            },
            {
                "name": "status",
                "label": "Status",
                "type": "dropdown",
                "choices": ["['Closed', 'This ticket has been Closed']"],
            },
        ]
    )
    by_search_key = {field.search_key: field for field in fields}

    assert by_search_key["agent_id"].type == "number"
    assert by_search_key["agent_id"].choices[0].value == 103147792207
    assert by_search_key["status"].type == "number"
    assert [(choice.label, choice.value) for choice in by_search_key["status"].choices] == [
        ("Open", 2),
        ("Pending", 3),
        ("Resolved", 4),
        ("Closed", 5),
    ]
