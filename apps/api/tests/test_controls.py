from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from unittest.mock import Mock

import pytest
from httpx import ASGITransport, AsyncClient

from app.controls.policy import approval_plan
from app.controls.schemas import ActionCode, ActorContext, Role
from app.controls.service import ControlsService, ControlStateError
from app.domain.schemas import ExceptionStatus, ExceptionSummary, ExceptionType, Severity
from app.main import app
from app.repositories.demo import demo_repository


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as test_client:
        yield test_client


def _headers(role: str = "ANALYST", actor: str = "analyst-001", key: str = "controls-test-001") -> dict[str, str]:
    return {"X-Organization-Id": "ORG-001", "X-Actor-Role": role, "X-Actor-Id": actor, "Idempotency-Key": key}


@pytest.mark.asyncio
async def test_resolution_request_is_authorized_idempotent_and_approvable(client: AsyncClient) -> None:
    request = await client.post(
        "/api/v1/exceptions/EXC-1042/resolution-request",
        headers=_headers(key="controls-request-001"),
        json={"action_code": "REQUEST_INVENTORY_VERIFICATION"},
    )
    replay = await client.post(
        "/api/v1/exceptions/EXC-1042/resolution-request",
        headers=_headers(key="controls-request-001"),
        json={"action_code": "REQUEST_INVENTORY_VERIFICATION"},
    )

    assert request.status_code == 200
    assert replay.status_code == 200
    assert request.json() == replay.json()
    payload = request.json()
    assert payload["status"] == "PENDING_APPROVAL"
    assert payload["required_capability"] == "resolution.approve.high"
    assert payload["required_approvals"] == 1

    analyst_approval = await client.post(
        f"/api/v1/approvals/{payload['request_id']}/approve",
        headers=_headers(key="controls-analyst-approval-001"),
    )
    manager_approval = await client.post(
        f"/api/v1/approvals/{payload['request_id']}/approve",
        headers=_headers(role="FINANCE_MANAGER", actor="manager-001", key="controls-manager-approval-001"),
    )
    controller_approval = await client.post(
        f"/api/v1/approvals/{payload['request_id']}/approve",
        headers=_headers(role="CONTROLLER", actor="controller-001", key="controls-controller-approval-001"),
    )
    controller_replay = await client.post(
        f"/api/v1/approvals/{payload['request_id']}/approve",
        headers=_headers(role="CONTROLLER", actor="controller-001", key="controls-controller-approval-001"),
    )

    assert analyst_approval.status_code == 403
    assert manager_approval.status_code == 403
    assert controller_approval.status_code == 200
    assert controller_approval.json()["request_status"] == "APPROVED"
    assert controller_replay.json() == controller_approval.json()


@pytest.mark.asyncio
async def test_resolution_request_rejects_unauthorized_action_and_key_conflict(client: AsyncClient) -> None:
    unauthorized_action = await client.post(
        "/api/v1/exceptions/EXC-1042/resolution-request",
        headers=_headers(key="controls-invalid-action-001"),
        json={"action_code": "REQUEST_ERP_INVOICE_CORRECTION"},
    )
    first = await client.post(
        "/api/v1/exceptions/EXC-1042/resolution-request",
        headers=_headers(key="controls-conflict-001"),
        json={"action_code": "REQUEST_INVENTORY_VERIFICATION"},
    )
    conflict = await client.post(
        "/api/v1/exceptions/EXC-1042/resolution-request",
        headers=_headers(key="controls-conflict-001"),
        json={"action_code": "REQUEST_REFUND_REVIEW"},
    )

    assert unauthorized_action.status_code == 403
    assert first.status_code == 200
    assert conflict.status_code == 409


@pytest.mark.asyncio
async def test_rejection_is_simulated_and_does_not_change_exception_state(client: AsyncClient) -> None:
    request = await client.post(
        "/api/v1/exceptions/EXC-1042/resolution-request",
        headers=_headers(key="controls-rejection-request-001"),
        json={"action_code": "REQUEST_INVENTORY_VERIFICATION"},
    )
    request_id = request.json()["request_id"]
    rejection = await client.post(
        f"/api/v1/approvals/{request_id}/reject",
        headers=_headers(role="CONTROLLER", actor="rejecting-controller", key="controls-rejection-001"),
    )
    after_rejection = await client.post(
        f"/api/v1/approvals/{request_id}/approve",
        headers=_headers(role="CONTROLLER", actor="other-controller", key="controls-after-rejection-001"),
    )

    assert rejection.status_code == 200
    assert rejection.json()["request_status"] == "REJECTED"
    assert after_rejection.status_code == 409
    assert demo_repository.get_exception("ORG-001", "EXC-1042").status == ExceptionStatus.OPEN


@pytest.mark.asyncio
async def test_audit_read_is_capability_gated(client: AsyncClient) -> None:
    await client.post(
        "/api/v1/exceptions/EXC-1042/resolution-request",
        headers=_headers(key="audit-request-001"),
        json={"action_code": "REQUEST_INVENTORY_VERIFICATION"},
    )
    analyst = await client.get("/api/v1/audit-events", headers=_headers())
    controller = await client.get(
        "/api/v1/audit-events",
        headers=_headers(role="CONTROLLER", actor="audit-controller", key="audit-read-001"),
    )

    assert analyst.status_code == 403
    assert controller.status_code == 200
    assert controller.json()
    assert {event["organization_id"] for event in controller.json()} == {"ORG-001"}


def test_policy_requires_secondary_controller_for_high_value_exception() -> None:
    exception = ExceptionSummary(
        id="EXC-HIGH-001",
        organization_id="ORG-001",
        order_id="ORD-2041",
        type=ExceptionType.REFUND_WITHOUT_INVENTORY_RETURN,
        severity=Severity.CRITICAL,
        status=ExceptionStatus.OPEN,
        financial_exposure=Decimal("100000.01"),
        currency="INR",
        detected_at="2026-08-30T00:00:00+00:00",
        rules_triggered=[],
    )

    plan = approval_plan(exception)
    assert plan.required_capability.value == "resolution.approve.high"
    assert plan.required_approvals == 2


def test_concurrent_duplicate_approval_cannot_apply_twice() -> None:
    service = ControlsService(demo_repository)
    analyst = ActorContext(organization_id="ORG-001", actor_id="concurrent-requester", role=Role.ANALYST)
    controller = ActorContext(organization_id="ORG-001", actor_id="concurrent-controller", role=Role.CONTROLLER)
    request = service.request_resolution(analyst, "EXC-1042", ActionCode.REQUEST_INVENTORY_VERIFICATION, "concurrent-request-001")

    def approve(key: str):
        try:
            return service.approve(controller, request.request_id, key)
        except ControlStateError:
            return "state-error"

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(approve, ["concurrent-approval-a", "concurrent-approval-b"]))

    assert sum(outcome != "state-error" for outcome in outcomes) == 1
    assert sum(outcome == "state-error" for outcome in outcomes) == 1


def test_high_value_request_requires_two_distinct_controller_approvals() -> None:
    repository = Mock()
    repository.get_exception.return_value = ExceptionSummary(
        id="EXC-HIGH-001",
        organization_id="ORG-001",
        order_id="ORD-2041",
        type=ExceptionType.REFUND_WITHOUT_INVENTORY_RETURN,
        severity=Severity.CRITICAL,
        status=ExceptionStatus.OPEN,
        financial_exposure=Decimal("100000.01"),
        currency="INR",
        detected_at="2026-08-30T00:00:00+00:00",
        rules_triggered=[],
    )
    service = ControlsService(repository)
    requester = ActorContext(organization_id="ORG-001", actor_id="high-requester", role=Role.ANALYST)
    first_controller = ActorContext(organization_id="ORG-001", actor_id="controller-001", role=Role.CONTROLLER)
    second_controller = ActorContext(organization_id="ORG-001", actor_id="controller-002", role=Role.CONTROLLER)

    request = service.request_resolution(requester, "EXC-HIGH-001", ActionCode.REQUEST_INVENTORY_VERIFICATION, "high-request-001")
    first = service.approve(first_controller, request.request_id, "high-approval-001")
    second = service.approve(second_controller, request.request_id, "high-approval-002")

    assert request.required_approvals == 2
    assert first.request_status == "PENDING_APPROVAL"
    assert second.request_status == "APPROVED"
    assert second.approvals_received == 2
