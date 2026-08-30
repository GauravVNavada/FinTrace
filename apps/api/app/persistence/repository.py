from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from app.domain.lifecycle import CanonicalLifecycle, LifecycleNotFoundError
from app.domain.schemas import (
    DashboardSummary,
    ExceptionStatus,
    ExceptionSummary,
    ExceptionType,
    Severity,
)
from app.persistence.connection import connection


class PostgresRepository:
    """Organization-scoped PostgreSQL repository for canonical read paths."""

    def __init__(self, database_url: str) -> None:
        self._database_url = database_url

    def _organization_uuid(self, conn: Any, organization_id: str) -> UUID | None:
        row = conn.execute(
            "SELECT id FROM organizations WHERE external_id = %s",
            (organization_id,),
        ).fetchone()
        return row["id"] if row else None

    def dashboard_summary(self, organization_id: str) -> DashboardSummary:
        with connection(self._database_url) as conn:
            org_uuid = self._organization_uuid(conn, organization_id)
            if org_uuid is None:
                return DashboardSummary(
                    organization_id=organization_id,
                    reconciliation_run_id="",
                    lifecycle_count=0,
                    auto_reconciled_count=0,
                    exception_count=0,
                    open_exposure=Decimal(0),
                    requires_review_count=0,
                    generated_at=datetime.now(UTC),
                )
            run = conn.execute(
                """
                SELECT run_key, lifecycle_count
                FROM reconciliation_runs
                WHERE organization_id = %s
                ORDER BY completed_at DESC NULLS LAST, started_at DESC
                LIMIT 1
                """,
                (org_uuid,),
            ).fetchone()
            exception_row = conn.execute(
                """
                SELECT count(*) AS exception_count,
                       coalesce(sum(financial_exposure_minor), 0) AS exposure,
                       count(*) FILTER (WHERE status IN ('OPEN', 'IN_REVIEW', 'ESCALATED')) AS review_count
                FROM exceptions
                WHERE organization_id = %s AND status <> 'RESOLVED'
                """,
                (org_uuid,),
            ).fetchone()
            return DashboardSummary(
                organization_id=organization_id,
                reconciliation_run_id=str(run["run_key"]) if run else "",
                lifecycle_count=int(run["lifecycle_count"]) if run else 0,
                auto_reconciled_count=0,
                exception_count=int(exception_row["exception_count"]),
                open_exposure=Decimal(int(exception_row["exposure"])) / Decimal(100),
                requires_review_count=int(exception_row["review_count"]),
                generated_at=datetime.now(UTC),
            )

    def list_exceptions(self, organization_id: str) -> list[ExceptionSummary]:
        with connection(self._database_url) as conn:
            org_uuid = self._organization_uuid(conn, organization_id)
            if org_uuid is None:
                return []
            rows = conn.execute(
                """
                SELECT source_exception_id, organization_id, o.source_order_id, exception_type,
                       severity, status, financial_exposure_minor, currency, detected_at,
                       rules_triggered
                FROM exceptions e
                JOIN orders o ON o.id = e.order_id AND o.organization_id = e.organization_id
                WHERE e.organization_id = %s
                ORDER BY e.detected_at DESC
                """,
                (org_uuid,),
            ).fetchall()
            return [self._exception(row, organization_id) for row in rows]

    def get_exception(self, organization_id: str, exception_id: str) -> ExceptionSummary | None:
        return next((item for item in self.list_exceptions(organization_id) if item.id == exception_id), None)

    def related_exceptions(self, organization_id: str, order_id: str) -> list[ExceptionSummary]:
        return [item for item in self.list_exceptions(organization_id) if item.order_id == order_id]

    def lifecycle(self, organization_id: str, order_id: str) -> CanonicalLifecycle:
        with connection(self._database_url) as conn:
            org_uuid = self._organization_uuid(conn, organization_id)
            if org_uuid is None:
                raise LifecycleNotFoundError(order_id)
            order = conn.execute(
                """
                SELECT source_order_id AS order_id, organization_id, store_code AS store,
                       amount_minor, status, created_at
                FROM orders
                WHERE organization_id = %s AND source_order_id = %s
                """,
                (org_uuid, order_id),
            ).fetchone()
            if order is None:
                raise LifecycleNotFoundError(order_id)
            order["organization_id"] = organization_id
            payments = self._rows(conn, """
                SELECT p.source_payment_id AS payment_id, o.source_order_id AS order_id,
                       p.organization_id, p.amount_minor, p.status, p.gateway_fee_minor,
                       p.captured_at
                FROM payments p JOIN orders o ON o.id = p.order_id
                WHERE p.organization_id = %s AND o.source_order_id = %s
            """, (org_uuid, order_id), organization_id)
            payment_ids = [row["payment_id"] for row in payments]
            settlements = self._rows(conn, """
                SELECT s.source_settlement_id AS settlement_id, s.organization_id,
                       p.source_payment_id AS payment_id, s.gross_minor, s.fees_minor,
                       s.tax_minor, s.net_minor, s.settled_at, s.status
                FROM settlements s JOIN payments p ON p.id = s.payment_id
                WHERE s.organization_id = %s AND p.source_payment_id = ANY(%s)
            """, (org_uuid, payment_ids), organization_id)
            refunds = self._rows(conn, """
                SELECT r.source_refund_id AS refund_id, r.organization_id,
                       p.source_payment_id AS payment_id, r.amount_minor, r.status, r.processed_at
                FROM refunds r JOIN payments p ON p.id = r.payment_id
                WHERE r.organization_id = %s AND p.source_payment_id = ANY(%s)
            """, (org_uuid, payment_ids), organization_id)
            invoices = self._rows(conn, """
                SELECT i.source_invoice_id AS invoice_id, i.organization_id,
                       o.source_order_id AS order_id, i.gross_minor, i.status, i.created_at
                FROM invoices i JOIN orders o ON o.id = i.order_id
                WHERE i.organization_id = %s AND o.source_order_id = %s
            """, (org_uuid, order_id), organization_id)
            inventory = self._rows(conn, """
                SELECT m.source_movement_id AS movement_id, m.organization_id,
                       o.source_order_id AS order_id, m.sku, m.quantity, m.movement_type,
                       m.occurred_at
                FROM inventory_movements m JOIN orders o ON o.id = m.order_id
                WHERE m.organization_id = %s AND o.source_order_id = %s
            """, (org_uuid, order_id), organization_id)
            actions = self._rows(conn, """
                SELECT a.source_action_id AS action_id, a.organization_id, a.entity_type,
                       a.entity_id, a.employee_id, a.action, a.occurred_at
                FROM employee_actions a
                WHERE a.organization_id = %s AND a.entity_id = %s
            """, (org_uuid, order_id), organization_id)
            return CanonicalLifecycle(
                order=order,
                payments=tuple(payments),
                settlements=tuple(settlements),
                invoices=tuple(invoices),
                refunds=tuple(refunds),
                inventory_movements=tuple(inventory),
                employee_actions=tuple(actions),
            )

    def list_lifecycles(self, organization_id: str) -> list[CanonicalLifecycle]:
        with connection(self._database_url) as conn:
            org_uuid = self._organization_uuid(conn, organization_id)
            if org_uuid is None:
                return []
            order_ids = conn.execute(
                "SELECT source_order_id FROM orders WHERE organization_id = %s ORDER BY created_at",
                (org_uuid,),
            ).fetchall()
        return [self.lifecycle(organization_id, row["source_order_id"]) for row in order_ids]

    def record_audit_event(
        self,
        organization_id: str,
        event_type: str,
        resource_id: str,
        actor_id: str = "system",
        correlation_id: str | None = None,
    ) -> None:
        with connection(self._database_url) as conn:
            org_uuid = self._organization_uuid(conn, organization_id)
            if org_uuid is None:
                return
            conn.execute(
                """
                INSERT INTO audit_events
                  (organization_id, actor_type, actor_id, action, resource_type, resource_id, correlation_id)
                VALUES (%s, 'USER', %s, %s, 'FINTRACE_RESOURCE', %s, %s)
                """,
                (org_uuid, actor_id, event_type, resource_id, correlation_id or resource_id),
            )

    def audit_events(self, organization_id: str, resource_id: str) -> list[dict[str, str]]:
        return self._audit_query(organization_id, "resource_id = %s", (resource_id,))

    def audit_events_for_organization(self, organization_id: str) -> list[dict[str, str]]:
        return self._audit_query(organization_id, "TRUE", ())

    def _audit_query(self, organization_id: str, predicate: str, params: tuple[Any, ...]) -> list[dict[str, str]]:
        with connection(self._database_url) as conn:
            org_uuid = self._organization_uuid(conn, organization_id)
            if org_uuid is None:
                return []
            rows = conn.execute(
                f"""
                SELECT id::text AS event_id, actor_id, action, resource_id,
                       correlation_id, created_at::text AS created_at
                FROM audit_events
                WHERE organization_id = %s AND {predicate}
                ORDER BY created_at DESC
                """,
                (org_uuid, *params),
            ).fetchall()
            return [
                {
                    "event_id": str(row["event_id"]),
                    "organization_id": organization_id,
                    "actor_id": str(row["actor_id"]),
                    "action": str(row["action"]),
                    "resource_id": str(row["resource_id"] or ""),
                    "correlation_id": str(row["correlation_id"]),
                    "created_at": str(row["created_at"]),
                }
                for row in rows
            ]

    @staticmethod
    def _rows(conn: Any, query: str, params: tuple[Any, ...], organization_id: str) -> list[dict[str, Any]]:
        rows = conn.execute(query, params).fetchall()
        for row in rows:
            row["organization_id"] = organization_id
        return rows

    @staticmethod
    def _exception(row: dict[str, Any], organization_id: str) -> ExceptionSummary:
        rules = row["rules_triggered"] if isinstance(row["rules_triggered"], list) else []
        return ExceptionSummary(
            id=str(row["source_exception_id"]),
            organization_id=organization_id,
            order_id=str(row["source_order_id"]),
            type=ExceptionType(str(row["exception_type"])),
            severity=Severity(str(row["severity"])),
            status=ExceptionStatus(str(row["status"])),
            financial_exposure=Decimal(int(row["financial_exposure_minor"])) / Decimal(100),
            currency=str(row["currency"]),
            detected_at=row["detected_at"],
            rules_triggered=[str(rule) for rule in rules],
        )
