from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from app.domain.lifecycle import CanonicalLifecycle, LifecycleNotFoundError
from app.domain.schemas import (
    DashboardSummary,
    ExceptionStatus,
    ExceptionSummary,
    ExceptionType,
    Severity,
)
from app.simulator.generator import GeneratorConfig, generate_dataset


class DemoRepository:
    """Temporary read-only adapter used until the PostgreSQL repository is wired.

    The production repository must take organization scope as an explicit argument
    and apply it to every query. This adapter exists only to make the API boundary
    executable without claiming persistence is complete.
    """

    def __init__(self) -> None:
        self._dataset = generate_dataset(GeneratorConfig(orders=1000, seed=42, anomaly_rate=0.30))
        self._audit_events: list[dict[str, str]] = []
        self._flagship_lifecycle = CanonicalLifecycle(
            order={
                "organization_id": "ORG-001",
                "order_id": "ORD-2041",
                "store": "BLR-01",
                "amount_minor": 1874000,
                "status": "COMPLETED",
                "created_at": "2026-08-20T09:00:00+00:00",
            },
            payments=(
                {
                    "organization_id": "ORG-001",
                    "payment_id": "PAY-8271",
                    "order_id": "ORD-2041",
                    "amount_minor": 1874000,
                    "status": "CAPTURED",
                    "gateway_fee_minor": 33732,
                    "captured_at": "2026-08-20T09:02:00+00:00",
                },
            ),
            settlements=(
                {
                    "organization_id": "ORG-001",
                    "settlement_id": "SET-5521",
                    "payment_id": "PAY-8271",
                    "gross_minor": 1874000,
                    "fees_minor": 33732,
                    "tax_minor": 6072,
                    "net_minor": 1830196,
                    "settled_at": "2026-08-22T09:00:00+00:00",
                    "status": "RECEIVED",
                },
            ),
            invoices=(
                {
                    "organization_id": "ORG-001",
                    "invoice_id": "INV-4012",
                    "order_id": "ORD-2041",
                    "gross_minor": 1874000,
                    "status": "ACTIVE",
                    "created_at": "2026-08-20T09:04:00+00:00",
                },
            ),
            refunds=(
                {
                    "organization_id": "ORG-001",
                    "refund_id": "RFND-2991",
                    "payment_id": "PAY-8271",
                    "amount_minor": 1874000,
                    "status": "PROCESSED",
                    "processed_at": "2026-08-20T11:00:00+00:00",
                },
            ),
            inventory_movements=(
                {
                    "organization_id": "ORG-001",
                    "movement_id": "MOV-7012",
                    "order_id": "ORD-2041",
                    "sku": "SKU-441",
                    "quantity": 1,
                    "movement_type": "SALE",
                    "occurred_at": "2026-08-20T09:05:00+00:00",
                },
            ),
            employee_actions=(
                {
                    "organization_id": "ORG-001",
                    "action_id": "ACT-7021",
                    "entity_type": "ORDER",
                    "entity_id": "ORD-2041",
                    "employee_id": "EMP-44",
                    "action": "MANUAL_REFUND_APPROVED",
                    "occurred_at": "2026-08-20T10:45:00+00:00",
                },
            ),
        )

    def dashboard_summary(self, organization_id: str) -> DashboardSummary:
        return DashboardSummary(
            organization_id=organization_id,
            reconciliation_run_id="RUN-024",
            lifecycle_count=1000,
            auto_reconciled_count=867,
            exception_count=133,
            open_exposure=Decimal(482390),
            requires_review_count=17,
            generated_at=datetime.now(UTC),
        )

    def list_exceptions(self, organization_id: str) -> list[ExceptionSummary]:
        return [
            ExceptionSummary(
                id="EXC-1042",
                organization_id=organization_id,
                order_id="ORD-2041",
                type=ExceptionType.REFUND_WITHOUT_INVENTORY_RETURN,
                severity=Severity.HIGH,
                status=ExceptionStatus.OPEN,
                financial_exposure=Decimal(18740),
                currency="INR",
                detected_at=datetime.now(UTC),
                rules_triggered=["REFUND_EXISTS", "INVENTORY_RETURN_MISSING", "ERP_REVERSAL_MISSING"],
            )
        ]

    def lifecycle(self, organization_id: str, order_id: str):
        if order_id == self._flagship_lifecycle.order["order_id"]:
            if organization_id != self._flagship_lifecycle.order["organization_id"]:
                raise LifecycleNotFoundError(order_id)
            return self._flagship_lifecycle
        return self._dataset.lifecycle_store().get_by_order(organization_id, order_id)

    def list_lifecycles(self, organization_id: str) -> list[CanonicalLifecycle]:
        if organization_id != "ORG-001":
            return []
        lifecycles: list[CanonicalLifecycle] = []
        for order in self._dataset.records["orders"]:
            order_id = str(order["order_id"])
            if order_id == self._flagship_lifecycle.order["order_id"]:
                lifecycles.append(self._flagship_lifecycle)
            else:
                lifecycles.append(self._dataset.lifecycle_store().get_by_order(organization_id, order_id))
        return lifecycles

    def get_exception(self, organization_id: str, exception_id: str) -> ExceptionSummary | None:
        if organization_id != "ORG-001" or exception_id != "EXC-1042":
            return None
        return self.list_exceptions(organization_id)[0]

    def record_audit_event(
        self,
        organization_id: str,
        event_type: str,
        resource_id: str,
        actor_id: str = "system",
        correlation_id: str | None = None,
    ) -> None:
        self._audit_events.append(
            {
                "event_id": f"AUD-{uuid4().hex[:12].upper()}",
                "organization_id": organization_id,
                "event_type": event_type,
                "action": event_type,
                "resource_id": resource_id,
                "actor_id": actor_id,
                "correlation_id": correlation_id or resource_id,
                "created_at": datetime.now(UTC).isoformat(),
            }
        )

    def audit_events(self, organization_id: str, resource_id: str) -> list[dict[str, str]]:
        return [
            event
            for event in self._audit_events
            if event["organization_id"] == organization_id and event["resource_id"] == resource_id
        ]

    def audit_events_for_organization(self, organization_id: str) -> list[dict[str, str]]:
        return [event for event in self._audit_events if event["organization_id"] == organization_id]

    def related_exceptions(self, organization_id: str, order_id: str) -> list[ExceptionSummary]:
        return [item for item in self.list_exceptions(organization_id) if item.order_id == order_id]


demo_repository = DemoRepository()
