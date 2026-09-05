import pytest
from unittest.mock import MagicMock
from httpx import ASGITransport, AsyncClient

from app.domain.lifecycle import CanonicalLifecycle
from app.domain.schemas import ExceptionStatus, ExceptionSummary, ExceptionType, Severity
from app.investigations.provider import AgentDecision, StubAIClient, UnavailableAIClient
from app.investigations.service import InvestigationService
from app.financial_exception_investigations.service import FinancialExceptionInvestigationService
from app.controls.schemas import ActorContext
from app.investigations.schemas import InvestigationResponse
from app.investigations.tools import EvidenceToolRegistry
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
    response = await client.get(
        "/api/v1/ai/provider-health", headers={"X-Organization-Id": "ORG-001"}
    )

    assert response.status_code == 200
    assert response.json()["status"] == "CONNECTED"
    assert response.json()["provider"] == "stub"
    assert response.json()["detail"] == "TEST FIXTURE / NON-LIVE"
    assert response.json()["overall_status"] == "AVAILABLE"
    assert response.json()["active_provider"] == "stub"
    assert response.json()["providers"][0]["provider"] == "stub"


@pytest.mark.asyncio
async def test_provider_health_requires_authentication(client: AsyncClient) -> None:
    response = await client.get("/api/v1/ai/provider-health")

    assert response.status_code == 401


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


def test_evidence_tools_read_actual_status_and_accept_external_ids() -> None:
    lifecycle = CanonicalLifecycle(
        order={"order_id": "100234", "amount_minor": 10000},
        payments=({"payment_id": "pay-1", "status": "FAILED", "amount_minor": 10000},),
        settlements=(),
        invoices=(),
        refunds=(),
        inventory_movements=(),
        employee_actions=(),
    )

    result = EvidenceToolRegistry(demo_repository).invoke("get_payment", "org-1", lifecycle)

    assert result.call.evidence[0].expected_value == "FAILED"
    assert result.call.evidence[0].fact == "Payment status is FAILED."


@pytest.mark.parametrize("cite_candidates", [True, False])
@pytest.mark.parametrize("malformed_first", [True, False])
def test_early_final_provider_receives_candidate_evidence_and_cannot_pass_uncited(cite_candidates, malformed_first):
    class EarlyFinal:
        calls = 0
        def next_step(self, exception, findings, evidence, trace, available_tools):
            self.calls += 1
            if malformed_first and self.calls == 1:
                return AgentDecision("final", candidate={"status": "UNRESOLVED", "summary": "x" * 1001})
            if malformed_first:
                assert any(item["code"] == "RESPONSE_FORMAT_CORRECTION" for item in findings)
            assert {call["name"] for call in trace} >= {
                "get_order", "get_payments_for_order", "get_settlements_for_order",
                "get_invoice_for_order", "get_refunds_for_order",
            }
            assert any(item.record_id == "SET-A" and item.expected_value == "PAY-A" for item in evidence)
            assert any(item.source.value == "invoice" and item.operator == "missing" for item in evidence)
            return AgentDecision("final", candidate={
                "status": "UNRESOLVED", "root_cause_code": None,
                "summary": "PAY-A links to SET-A. PAY-B has no settlement linkage in this dataset; the capture association remains uncertain.",
                "supporting_evidence": [item.model_dump(mode="json") for item in evidence] if cite_candidates else [],
                "missing_evidence": ["Request gateway references for PAY-A and PAY-B to distinguish separate captures from a retry."],
                "requires_human_review": True,
            })
    lifecycle = CanonicalLifecycle(
        order={"order_id": "ORD-A", "amount_minor": 10000},
        payments=({"payment_id": "PAY-A", "amount_minor": 10000}, {"payment_id": "PAY-B", "amount_minor": 10000}),
        settlements=({"settlement_id": "SET-A", "payment_id": "PAY-A"},),
        invoices=(), refunds=(), inventory_movements=(), employee_actions=(),
    )
    exception = ExceptionSummary(
        id="EXC-A", organization_id="ORG-001", order_id="ORD-A",
        type=ExceptionType.AMBIGUOUS_ASSOCIATION, severity=Severity.HIGH,
        status=ExceptionStatus.OPEN, financial_exposure=100, currency="INR",
        detected_at="2026-08-31T00:00:00+00:00",
    )
    result = InvestigationService(demo_repository, EarlyFinal()).investigate_lifecycle("ORG-001", exception, lifecycle)
    assert result.status == "UNRESOLVED"
    assert result.verifier_passed is cite_candidates
    assert len(result.tool_calls) == 5
    assert all(call.provider == "deterministic-evidence-collection" for call in result.tool_calls)


def test_empty_settlement_lookup_returns_verifiable_missing_evidence() -> None:
    lifecycle = CanonicalLifecycle(
        order={"order_id": "ORD-EMPTY-001", "amount_minor": 10000},
        payments=({"payment_id": "PAY-EMPTY-001", "order_id": "ORD-EMPTY-001"},),
        settlements=(),
        invoices=(),
        refunds=(),
        inventory_movements=(),
        employee_actions=(),
    )

    result = EvidenceToolRegistry(demo_repository).invoke(
        "get_settlements_for_payment", "org-1", lifecycle
    )

    assert result.call.evidence[0].source.value == "settlement"
    assert result.call.evidence[0].record_id is None
    assert result.call.evidence[0].operator.value == "missing"
    assert result.call.evidence[0].expected_value is None


@pytest.mark.parametrize("previous_failed", [False, True])
def test_legacy_refresh_preserves_identity_and_same_key_replays(monkeypatch, previous_failed):
    from app.financial_exception_investigations import service as module
    old = InvestigationResponse(
        investigation_id="INV-OLD", exception_id="RES-OLD", status="UNRESOLVED",
        summary="Old assessment", missing_evidence=["reference"], evidence_score=0,
        created_at="2026-08-31T00:00:00Z",
    )
    if previous_failed:
        from app.investigations.schemas import ToolCall, InvestigationStatus
        old = old.model_copy(update={"status": InvestigationStatus.FAILED, "tool_calls": [ToolCall(
            name="get_order", target="ORD-OLD", status="SUCCEEDED", duration_ms=0,
        )]})
    repository = MagicMock()
    repository.get_idempotency.return_value = None
    repository.get_financial_exception_investigation.return_value = old.model_dump(mode="json")
    repository.get_reconciliation_result.return_value = {"order_id": "ORD-OLD", "exception_type": "AMBIGUOUS_ASSOCIATION"}
    repository.latest_reconciliation_run.return_value = {"id": "RUN-OLD", "dataset_version_id": "DS-OLD"}
    repository.get_financial_investigation.return_value = {"base_currency": "INR"}
    repository.list_dataset_versions.return_value = []
    repository.reserve_idempotency.return_value = None
    lifecycle = CanonicalLifecycle(order={"order_id": "ORD-OLD"}, payments=(), settlements=(), invoices=(), refunds=(), inventory_movements=(), employee_actions=())
    monkeypatch.setattr(module, "construct_lifecycles", lambda *args: [lifecycle])
    service = FinancialExceptionInvestigationService(repository, StubAIClient())
    service._investigator = MagicMock()
    service._investigator.investigate_lifecycle.return_value = old.model_copy(update={"investigation_id": "INV-NEW", "summary": "Refreshed"})
    context = ActorContext(organization_id="ORG-001", actor_id="controller", role="CONTROLLER")
    refreshed = service.investigate(context, "FIN-OLD", "RUN-OLD", "RES-OLD", "refresh-key")
    assert refreshed.investigation_id == "INV-OLD"
    assert refreshed.summary == "Refreshed"
    repository.save_financial_exception_investigation_with_tool_calls.assert_called_once()
    stored = repository.complete_idempotency.call_args.args
    repository.get_idempotency.return_value = {"request_hash": repository.reserve_idempotency.call_args.args[3], "response_status": 200, "response_body": stored[3]}
    assert service.investigate(context, "FIN-OLD", "RUN-OLD", "RES-OLD", "refresh-key") == refreshed
    service._investigator.investigate_lifecycle.assert_called_once()


def test_inventory_tool_returns_sale_and_return_valuation_evidence():
    lifecycle = CanonicalLifecycle(
        order={"order_id": "ORD-INVENTORY-001", "amount_minor": 10000},
        payments=(), settlements=(), invoices=(), refunds=(),
        inventory_movements=(
            {"movement_id": "MOV-SALE", "order_id": "ORD-INVENTORY-001", "movement_type": "SALE", "sku": "SKU-1", "quantity": 1, "unit_cost_minor": 2400, "inventory_value_minor": 2400},
            {"movement_id": "MOV-RETURN", "order_id": "ORD-INVENTORY-001", "movement_type": "RETURN", "sku": "SKU-1", "quantity": 1, "unit_cost_minor": 2500, "inventory_value_minor": 2500},
        ),
        employee_actions=(),
    )
    result = EvidenceToolRegistry(demo_repository).invoke(
        "get_inventory_movements", "org-1", lifecycle
    )
    fields = {item.field for item in result.call.evidence}
    assert {"movement_type", "quantity", "unit_cost_minor", "inventory_value_minor"} <= fields
    assert {"MOV-SALE", "MOV-RETURN"} <= set(result.call.result_record_ids)
