from app.post_filter import apply_exclusions, is_excluded
from app.schemas import FilterCondition


def test_is_not_filter_excludes_matching_numeric_values() -> None:
    exclusions = [FilterCondition(field="status", operator="neq", value="5", type="number")]
    tickets = [
        {"id": 1, "status": 2},
        {"id": 2, "status": 5},
    ]

    assert [ticket["id"] for ticket in apply_exclusions(tickets, exclusions)] == [1]


def test_agent_id_exclusion_matches_ticket_responder_id() -> None:
    ticket = {"id": 1, "responder_id": 42}
    exclusions = [FilterCondition(field="agent_id", operator="neq", value="42", type="number")]

    assert is_excluded(ticket, exclusions) is True


def test_tag_exclusion_matches_values_inside_tag_lists() -> None:
    ticket = {"id": 1, "tags": ["billing", "vip"]}
    exclusions = [FilterCondition(field="tags", operator="neq", value="vip", type="text")]

    assert is_excluded(ticket, exclusions) is True
