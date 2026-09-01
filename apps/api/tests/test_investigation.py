import pytest
from httpx import ASGITransport, AsyncClient

from app.domain.lifecycle import CanonicalLifecycle
from app.domain.schemas import ExceptionStatus, ExceptionSummary, ExceptionType, Severity
from app.investigations.provider import StubAIClient, UnavailableAIClient
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
    assert {item["record_id"] for item in payload["supporting_evidence"] if item["record_id"]} >= {
        "RFND-2991",
        "INV-4012",
    }
    assert len(payload["tool_calls"]) == 6
    assert {
        event["event_type"] for event in demo_repository.audit_events("ORG-001", "EXC-1042")
    } >= {
        "INVESTIGATION_STARTED",
    }

    detail = await client.get(
        f"/api/v1/investigations/{payload['investigation_id']}", headers=headers
    )
    calls = await client.get(
        f"/api/v1/investigations/{payload['investigation_id']}/tool-calls", headers=headers
    )
    assert detail.status_code == 200
    assert calls.status_code == 200
    assert calls.json()[4]["name"] == "get_inventory_movements"


@pytest.mark.asyncio
async def test_investigation_requires_tenant_and_idempotency(client: AsyncClient) -> None:
    no_tenant = await client.post("/api/v1/exceptions/EXC-1042/investigations")
    no_key = await client.post(
        "/api/v1/exceptions/EXC-1042/investigations", headers={"X-Organization-Id": "ORG-001"}
    )
    other_tenant = await client.post(
        "/api/v1/exceptions/EXC-1042/investigations",
        headers={"X-Organization-Id": "ORG-OTHER", "Idempotency-Key": "sprint3-other-001"},
    )

    assert no_tenant.status_code == 401
    assert no_key.status_code == 422
    assert other_tenant.status_code == 404


@pytest.mark.asyncio
async def test_provider_health_is_visible_before_investigation(client: AsyncClient) -> None:
    response = await client.get("/api/v1/ai/provider-health")

    assert response.status_code == 200
    assert response.json()["status"] == "CONNECTED"
    assert response.json()["provider"] == "stub"
    assert response.json()["detail"] == "TEST FIXTURE / NON-LIVE"
    assert response.json()["overall_status"] == "AVAILABLE"
    assert response.json()["active_provider"] == "stub"
    assert response.json()["providers"][0]["provider"] == "stub"


def test_provider_failure_is_safe() -> None:
    service = InvestigationService(demo_repository, UnavailableAIClient())
    result = service.start("ORG-001", "EXC-1042", "sprint3-provider-failure-001")

    assert result.status == "FAILED"
    assert result.requires_human_review is True
    assert result.recommended_action_code is None
    assert result.evidence_score == 0
    assert result.originally_requested_provider == "unavailable"
    assert result.actual_provider_used == "unavailable"
    assert result.fallback_used is False


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


def test_ambiguous_payment_relationship_is_unresolved_not_provider_failure() -> None:
    exception = ExceptionSummary(
        id="RRES-AMB-001",
        organization_id="ORG-001",
        order_id="ORD-AMB-001",
        type=ExceptionType.AMBIGUOUS_ASSOCIATION,
        severity=Severity.HIGH,
        status=ExceptionStatus.OPEN,
        financial_exposure=100,
        currency="INR",
        detected_at="2026-08-31T00:00:00+00:00",
    )
    lifecycle = CanonicalLifecycle(
        order={"order_id": "ORD-AMB-001", "amount_minor": 10000},
        payments=(
            {"payment_id": "PAY-AMB-001", "amount_minor": 10000},
            {"payment_id": "PAY-AMB-002", "amount_minor": 10000},
        ),
        settlements=(),
        invoices=(),
        refunds=(),
        inventory_movements=(),
        employee_actions=(),
    )
    result = InvestigationService(demo_repository, StubAIClient()).investigate_lifecycle(
        "ORG-001", exception, lifecycle
    )

    assert result.status == "UNRESOLVED"
    assert result.root_cause_code in {"AMBIGUOUS_ASSOCIATION", "UNKNOWN"}
    assert result.requires_human_review is True
    assert all(call.status == "SUCCEEDED" for call in result.tool_calls)
    assert {call.name for call in result.tool_calls} == {
        "get_order",
        "get_payments_for_order",
        "get_invoice_for_order",
        "get_settlements_for_order",
        "get_refunds_for_order",
    }
