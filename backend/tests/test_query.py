from app.query import QueryError, append_date_window, build_query, encode_query, wrap_query
from app.schemas import FilterCondition


def test_query_builder_wraps_and_validates_length() -> None:
    query = build_query(
        [
            FilterCondition(field="status", operator="eq", value=2, type="number"),
            FilterCondition(field="created_at", operator="between", value="2026-01-01", value_to="2026-02-01"),
        ]
    )

    assert query == "status:2 AND created_at:>'2026-01-01' AND created_at:<'2026-02-01'"
    assert wrap_query(query) == '"status:2 AND created_at:>\'2026-01-01\' AND created_at:<\'2026-02-01\'"'


def test_custom_field_query_generation() -> None:
    query = build_query(
        [FilterCondition(field="cf_order_reference", operator="eq", value="ABC-123", type="text")]
    )

    assert query == "cf_order_reference:'ABC-123'"


def test_id_backed_dropdown_values_are_not_quoted() -> None:
    query = build_query(
        [FilterCondition(field="agent_id", operator="eq", value="42", type="number")]
    )

    assert query == "agent_id:42"


def test_numeric_filters_reject_non_numeric_values_locally() -> None:
    try:
        build_query([FilterCondition(field="agent_id", operator="eq", value="Ada Lovelace", type="number")])
    except QueryError as error:
        assert "positive integer" in str(error)
    else:
        raise AssertionError("Expected QueryError")


def test_not_equal_query_generation_uses_is_not_operator() -> None:
    query = build_query(
        [FilterCondition(field="status", operator="neq", value=5, type="number")]
    )

    assert query == "created_at:>'1970-01-01'"


def test_not_equal_with_finite_choices_expands_to_positive_options() -> None:
    query = build_query(
        [
            FilterCondition(
                field="status",
                operator="neq",
                value=5,
                type="number",
                choices=[2, 3, 4, 5],
            )
        ]
    )

    assert query == "(status:2 OR status:3 OR status:4)"


def test_not_equal_is_applied_after_positive_search_terms() -> None:
    query = build_query(
        [
            FilterCondition(field="priority", operator="eq", value=4, type="number"),
            FilterCondition(field="status", operator="neq", value=5, type="number"),
        ]
    )

    assert query == "priority:4"


def test_query_encoding_uses_wrapped_query() -> None:
    encoded = encode_query("status:2 AND tag:'vip'")

    assert encoded == "query=%22status%3A2+AND+tag%3A%27vip%27%22"


def test_date_windows_use_freshdesk_date_format() -> None:
    query = append_date_window(
        "agent_id:103147792207",
        "created_at",
        "2025-09-06T00:00:00+00:00",
        "2026-05-13T00:00:00+00:00",
    )

    assert query == "(agent_id:103147792207) AND created_at:>'2025-09-06' AND created_at:<'2026-05-13'"


def test_query_length_limit_counts_wrapping_quotes() -> None:
    too_long = "x" * 511

    try:
        wrap_query(too_long)
    except QueryError as error:
        assert "limit is 512" in str(error)
    else:
        raise AssertionError("Expected QueryError")
