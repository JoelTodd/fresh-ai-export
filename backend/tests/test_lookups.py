import pytest

from app.lookups import fetch_lookup_choices
from app.schemas import RateLimitInfo


class FakeResult:
    def __init__(self, data):
        self.data = data
        self.rate_limit = RateLimitInfo(raw={})


class FakeClient:
    async def agents(self):
        return FakeResult(
            [
                {"id": 2, "contact": {"name": "Grace Hopper", "email": "grace@example.com"}},
                {"id": 1, "contact": {"email": "ada@example.com"}, "name": "Ada Lovelace"},
            ]
        )

    async def groups(self):
        return FakeResult([{"id": 10, "name": "Support"}])

    async def tags(self):
        return FakeResult(["billing", {"name": "vip"}])


@pytest.mark.asyncio
async def test_fetch_lookup_choices_maps_standard_id_fields() -> None:
    choices = await fetch_lookup_choices(FakeClient())

    assert [(choice.label, choice.value) for choice in choices["agent_id"]] == [
        ("Ada Lovelace", 1),
        ("Grace Hopper", 2),
    ]
    assert choices["responder_id"] == choices["agent_id"]
    assert choices["group_id"][0].label == "Support"
    assert [(choice.label, choice.value) for choice in choices["tag"]] == [
        ("billing", "billing"),
        ("vip", "vip"),
    ]
