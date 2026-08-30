import pytest
from httpx import ASGITransport, AsyncClient

from app.investigations.provider import UnavailableAIClient
from app.investigations.service import InvestigationService
from app.main import app
from app.repositories.demo import demo_repository


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as test_client:
        yield test_client


@pytest.mark.asyncio
async def test_flagship_investigation_is_cited_and_idempotent(client: AsyncClient) -> None:
    headers = {"X-Organization-Id": "ORG-001", "Idempotency-Key": "sprint3-flagship-001"}
    first = await client.post("/api/v1/exceptions/EXC-1042/investigations", headers=headers)
    second = await client.post("/api/v1/exceptions/EXC-1042/investigations", headers=headers)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json()
    payload = first.json()
    assert payload["status"] == "SUPPORTED"
    assert payload["root_cause_code"] == "INCOMPLETE_REFUND_WORKFLOW"
    assert payload["recommended_action_code"] == "REQUEST_INVENTORY_VERIFICATION"
    assert payload["evidence_score"] == 70
    assert {item["record_id"] for item in payload["supporting_evidence"] if item["record_id"]} >= {"RFND-2991", "INV-4012"}
    assert len(payload["tool_calls"]) == 6
    assert {event["event_type"] for event in demo_repository.audit_events("ORG-001", "EXC-1042")} >= {
        "INVESTIGATION_STARTED",
    }

    detail = await client.get(f"/api/v1/investigations/{payload['investigation_id']}", headers=headers)
    calls = await client.get(f"/api/v1/investigations/{payload['investigation_id']}/tool-calls", headers=headers)
    assert detail.status_code == 200
    assert calls.status_code == 200
    assert calls.json()[4]["name"] == "get_inventory_movements"


@pytest.mark.asyncio
async def test_investigation_requires_tenant_and_idempotency(client: AsyncClient) -> None:
    no_tenant = await client.post("/api/v1/exceptions/EXC-1042/investigations")
    no_key = await client.post("/api/v1/exceptions/EXC-1042/investigations", headers={"X-Organization-Id": "ORG-001"})
    other_tenant = await client.post(
        "/api/v1/exceptions/EXC-1042/investigations",
        headers={"X-Organization-Id": "ORG-OTHER", "Idempotency-Key": "sprint3-other-001"},
    )

    assert no_tenant.status_code == 401
    assert no_key.status_code == 422
    assert other_tenant.status_code == 404


def test_provider_failure_is_safe() -> None:
    service = InvestigationService(demo_repository, UnavailableAIClient())
    result = service.start("ORG-001", "EXC-1042", "sprint3-provider-failure-001")

    assert result.status == "FAILED"
    assert result.requires_human_review is True
    assert result.recommended_action_code is None
    assert result.evidence_score == 0


class InvalidProvider:
    def __init__(self):
        self.calls = 0

    def investigate(self, exception, evidence):
        self.calls += 1
        return {"status": "SUPPORTED", "root_cause_code": "NOT_A_CONTROLLED_CODE"}


def test_invalid_provider_result_becomes_unresolved() -> None:
    provider = InvalidProvider()
    service = InvestigationService(demo_repository, provider)
    result = service.start("ORG-001", "EXC-1042", "sprint3-invalid-provider-001")

    assert result.status == "UNRESOLVED"
    assert result.requires_human_review is True
    assert result.recommended_action_code is None
    assert provider.calls == 2
