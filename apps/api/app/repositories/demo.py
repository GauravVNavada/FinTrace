from datetime import UTC, datetime
from decimal import Decimal
from threading import RLock
from typing import cast
from uuid import uuid4

from app.core.request_context import current_request_id
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
        self.supports_workflow_persistence = True
        self._dataset = generate_dataset(GeneratorConfig(orders=1000, seed=42, anomaly_rate=0.30))
        self._audit_events: list[dict[str, str]] = []
        self._idempotency: dict[tuple[str, str], dict[str, object]] = {}
        self._idempotency_lock = RLock()
        self._investigations: dict[tuple[str, str], dict[str, object]] = {}
        self._evaluations: dict[str, dict[str, object]] = {}
        self._resolution_requests: dict[tuple[str, str], dict[str, object]] = {}
        self._approval_decisions: dict[tuple[str, str], list[dict[str, str]]] = {}
        self._financial_investigations: dict[tuple[str, str], dict[str, object]] = {}
        self._source_files: dict[tuple[str, str], dict[str, object]] = {}
        self._source_analyses: dict[tuple[str, str], dict[str, object]] = {}
        self._source_mappings: dict[tuple[str, str], list[dict[str, object]]] = {}
        self._relationship_proposals: dict[tuple[str, str], list[dict[str, object]]] = {}
        self._dataset_versions: dict[tuple[str, str], list[dict[str, object]]] = {}
        self._normalized_records: dict[str, list[dict[str, object]]] = {}
        self._reconciliation_runs: dict[tuple[str, str], list[dict[str, object]]] = {}
        self._reconciliation_results: dict[str, list[dict[str, object]]] = {}
        self._financial_exception_investigations: dict[tuple[str, str], dict[str, object]] = {}
        self._financial_exception_investigation_tool_calls: dict[str, list[dict[str, object]]] = {}
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

    def list_exceptions(self, organization_id: str, limit: int = 100) -> list[ExceptionSummary]:
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
                rules_triggered=[
                    "REFUND_EXISTS",
                    "INVENTORY_RETURN_MISSING",
                    "ERP_REVERSAL_MISSING",
                ],
            )
        ][:limit]

    def lifecycle(self, organization_id: str, order_id: str):
        if order_id == self._flagship_lifecycle.order["order_id"]:
            if organization_id != self._flagship_lifecycle.order["organization_id"]:
                raise LifecycleNotFoundError(order_id)
            return self._flagship_lifecycle
        return self._dataset.lifecycle_store().get_by_order(organization_id, order_id)

    def list_lifecycles(self, organization_id: str, limit: int = 1000) -> list[CanonicalLifecycle]:
        if organization_id != "ORG-001":
            return []
        lifecycles: list[CanonicalLifecycle] = []
        for order in self._dataset.records["orders"][:limit]:
            order_id = str(order["order_id"])
            if order_id == self._flagship_lifecycle.order["order_id"]:
                lifecycles.append(self._flagship_lifecycle)
            else:
                lifecycles.append(
                    self._dataset.lifecycle_store().get_by_order(organization_id, order_id)
                )
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
                "correlation_id": correlation_id or current_request_id() or resource_id,
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
        return [
            event for event in self._audit_events if event["organization_id"] == organization_id
        ]

    def related_exceptions(self, organization_id: str, order_id: str) -> list[ExceptionSummary]:
        return [item for item in self.list_exceptions(organization_id) if item.order_id == order_id]

    def create_financial_investigation(
        self, organization_id: str, data: dict[str, object]
    ) -> dict[str, object]:
        record = {**data, "organization_id": organization_id, "source_file_count": 0}
        self._financial_investigations[(organization_id, str(data["id"]))] = record
        return dict(record)

    def list_financial_investigations(
        self, organization_id: str, limit: int = 100
    ) -> list[dict[str, object]]:
        records = [
            record
            for (org, _), record in self._financial_investigations.items()
            if org == organization_id
        ]
        return [
            dict(record)
            for record in sorted(records, key=lambda item: str(item["created_at"]), reverse=True)[
                :limit
            ]
        ]

    def get_financial_investigation(
        self, organization_id: str, investigation_id: str
    ) -> dict[str, object] | None:
        record = self._financial_investigations.get((organization_id, investigation_id))
        return dict(record) if record else None

    def update_financial_investigation_status(
        self, organization_id: str, investigation_id: str, status: str
    ) -> None:
        record = self._financial_investigations.get((organization_id, investigation_id))
        if record is not None:
            record["status"] = status
            record["updated_at"] = datetime.now(UTC)

    def add_source_file(
        self, organization_id: str, investigation_id: str, data: dict[str, object]
    ) -> dict[str, object]:
        investigation = self._financial_investigations.get((organization_id, investigation_id))
        if investigation is None:
            return {}
        record = {
            **data,
            "organization_id": organization_id,
            "financial_investigation_id": investigation_id,
        }
        self._source_files[(organization_id, str(data["id"]))] = record
        investigation["source_file_count"] = (
            cast(int, investigation.get("source_file_count", 0)) + 1
        )
        if investigation.get("status") == "DRAFT":
            investigation["status"] = "SOURCES_UPLOADED"
        return _public_source_file(record)

    def list_source_files(
        self, organization_id: str, investigation_id: str, limit: int = 100
    ) -> list[dict[str, object]]:
        records = [
            record
            for (org, _), record in self._source_files.items()
            if org == organization_id
            and record.get("financial_investigation_id") == investigation_id
        ]
        return [
            _public_source_file(record)
            for record in sorted(records, key=lambda item: str(item["created_at"]), reverse=True)[
                :limit
            ]
        ]

    def delete_source_file(
        self, organization_id: str, investigation_id: str, source_file_id: str
    ) -> dict[str, object] | None:
        record = self._source_files.get((organization_id, source_file_id))
        if record is None or record.get("financial_investigation_id") != investigation_id:
            return None
        del self._source_files[(organization_id, source_file_id)]
        investigation = self._financial_investigations.get((organization_id, investigation_id))
        if investigation is not None:
            investigation["source_file_count"] = max(
                cast(int, investigation.get("source_file_count", 1)) - 1, 0
            )
            if investigation["source_file_count"] == 0:
                investigation["status"] = "DRAFT"
        return dict(record)

    def get_source_file_internal(
        self, organization_id: str, investigation_id: str, source_file_id: str
    ) -> dict[str, object] | None:
        record = self._source_files.get((organization_id, source_file_id))
        if record is None or record.get("financial_investigation_id") != investigation_id:
            return None
        return dict(record)

    def update_source_analysis_state(
        self,
        organization_id: str,
        investigation_id: str,
        source_file_id: str,
        status: str,
        detected_source_type: str,
        classification_confidence: float,
    ) -> None:
        record = self._source_files.get((organization_id, source_file_id))
        if record is None or record.get("financial_investigation_id") != investigation_id:
            return
        record.update(
            {
                "status": status,
                "detected_source_type": detected_source_type,
                "classification_confidence": classification_confidence,
            }
        )
        investigation = self._financial_investigations.get((organization_id, investigation_id))
        if investigation is not None:
            investigation["status"] = (
                "MAPPING_REQUIRED" if status == "MAPPING_REQUIRED" else investigation.get("status")
            )

    def save_source_analysis(
        self,
        organization_id: str,
        investigation_id: str,
        source_file_id: str,
        data: dict[str, object],
    ) -> dict[str, object]:
        record = {
            **data,
            "organization_id": organization_id,
            "financial_investigation_id": investigation_id,
            "source_file_id": source_file_id,
        }
        self._source_analyses[(organization_id, source_file_id)] = record
        return dict(record)

    def get_source_analysis(
        self, organization_id: str, investigation_id: str, source_file_id: str
    ) -> dict[str, object] | None:
        record = self._source_analyses.get((organization_id, source_file_id))
        if record is None or record.get("financial_investigation_id") != investigation_id:
            return None
        return dict(record)

    def list_source_mappings(
        self, organization_id: str, investigation_id: str, source_file_id: str
    ) -> list[dict[str, object]]:
        mappings = self._source_mappings.get((organization_id, source_file_id), [])
        return [
            dict(item)
            for item in mappings
            if item.get("financial_investigation_id") == investigation_id
        ]

    def save_source_mappings(
        self,
        organization_id: str,
        investigation_id: str,
        source_file_id: str,
        mappings: list[dict[str, object]],
    ) -> list[dict[str, object]]:
        records = [
            {
                **mapping,
                "organization_id": organization_id,
                "financial_investigation_id": investigation_id,
                "source_file_id": source_file_id,
            }
            for mapping in mappings
        ]
        self._source_mappings[(organization_id, source_file_id)] = records
        return [dict(item) for item in records]

    def update_source_mapping(
        self,
        organization_id: str,
        investigation_id: str,
        source_file_id: str,
        mapping_id: str,
        data: dict[str, object],
    ) -> dict[str, object] | None:
        mappings = self._source_mappings.get((organization_id, source_file_id), [])
        for mapping in mappings:
            if (
                mapping.get("financial_investigation_id") == investigation_id
                and mapping.get("id") == mapping_id
            ):
                mapping.update(data)
                mapping["status"] = "EDITED"
                return dict(mapping)
        return None

    def confirm_source_mappings(
        self, organization_id: str, investigation_id: str, source_file_id: str
    ) -> dict[str, object] | None:
        mappings = self.list_source_mappings(organization_id, investigation_id, source_file_id)
        if not mappings:
            return None
        missing = [
            item
            for item in mappings
            if item.get("required") and (item.get("ignored") or not item.get("canonical_field"))
        ]
        if missing:
            return {
                "valid": False,
                "missing_fields": [str(item.get("source_column")) for item in missing],
            }
        now = datetime.now(UTC)
        for mapping in self._source_mappings[(organization_id, source_file_id)]:
            mapping["status"] = "CONFIRMED"
            mapping["updated_at"] = now
        source = self._source_files.get((organization_id, source_file_id))
        if source is not None:
            source["status"] = "READY"
        if all(
            item.get("status") == "READY"
            for item in self._source_files.values()
            if item.get("financial_investigation_id") == investigation_id
            and item.get("organization_id") == organization_id
        ):
            self.update_financial_investigation_status(
                organization_id, investigation_id, "RELATIONSHIP_REVIEW"
            )
        return {
            "valid": True,
            "confirmed_mapping_count": len(mappings),
            "ignored_column_count": sum(1 for item in mappings if item.get("ignored")),
        }

    def list_relationship_proposals(
        self, organization_id: str, investigation_id: str
    ) -> list[dict[str, object]]:
        return [
            dict(item)
            for item in self._relationship_proposals.get((organization_id, investigation_id), [])
        ]

    def save_relationship_proposals(
        self, organization_id: str, investigation_id: str, proposals: list[dict[str, object]]
    ) -> list[dict[str, object]]:
        existing = {
            str(item["id"]): item
            for item in self._relationship_proposals.get((organization_id, investigation_id), [])
        }
        records = []
        for proposal in proposals:
            old = existing.get(str(proposal["id"]))
            records.append(
                {
                    **proposal,
                    "status": old.get("status", proposal["status"]) if old else proposal["status"],
                }
            )
        self._relationship_proposals[(organization_id, investigation_id)] = records
        return [dict(item) for item in records]

    def update_relationship_proposal(
        self, organization_id: str, investigation_id: str, relationship_id: str, status: str
    ) -> dict[str, object] | None:
        for item in self._relationship_proposals.get((organization_id, investigation_id), []):
            if item["id"] == relationship_id:
                item["status"] = status
                item["updated_at"] = datetime.now(UTC)
                return dict(item)
        return None

    def next_dataset_version(self, organization_id: str, investigation_id: str) -> int:
        return len(self._dataset_versions.get((organization_id, investigation_id), [])) + 1

    def save_dataset_version(
        self, organization_id: str, version: dict[str, object], records: list[dict[str, object]]
    ) -> dict[str, object]:
        self._dataset_versions.setdefault(
            (organization_id, str(version["financial_investigation_id"])), []
        ).append(dict(version))
        self._normalized_records[str(version["id"])] = [
            {**record, "organization_id": organization_id, "dataset_version_id": version["id"]}
            for record in records
        ]
        return dict(version)

    def latest_dataset_version(
        self, organization_id: str, investigation_id: str
    ) -> dict[str, object] | None:
        versions = self._dataset_versions.get((organization_id, investigation_id), [])
        return dict(versions[-1]) if versions else None

    def list_dataset_versions(
        self, organization_id: str, investigation_id: str
    ) -> list[dict[str, object]]:
        return [
            dict(item)
            for item in self._dataset_versions.get((organization_id, investigation_id), [])
        ]

    def list_normalized_records(
        self,
        organization_id: str,
        investigation_id: str,
        dataset_version_id: str,
        limit: int = 1000,
    ) -> list[dict[str, object]]:
        version = next(
            (
                item
                for item in self._dataset_versions.get((organization_id, investigation_id), [])
                if item["id"] == dataset_version_id
            ),
            None,
        )
        if version is None:
            return []
        return [dict(item) for item in self._normalized_records.get(dataset_version_id, [])[:limit]]

    def save_reconciliation_run(
        self, organization_id: str, run: dict[str, object], results: list[dict[str, object]]
    ) -> dict[str, object]:
        key = (organization_id, str(run["financial_investigation_id"]))
        self._reconciliation_runs.setdefault(key, []).append(dict(run))
        self._reconciliation_results[str(run["id"])] = [dict(item) for item in results]
        return dict(run)

    def latest_reconciliation_run(
        self, organization_id: str, investigation_id: str
    ) -> dict[str, object] | None:
        runs = self._reconciliation_runs.get((organization_id, investigation_id), [])
        return dict(runs[-1]) if runs else None

    def list_reconciliation_results(
        self, organization_id: str, investigation_id: str, run_id: str, limit: int = 1000
    ) -> list[dict[str, object]]:
        run = next(
            (
                item
                for item in self._reconciliation_runs.get((organization_id, investigation_id), [])
                if item["id"] == run_id
            ),
            None,
        )
        if run is None:
            return []
        return [dict(item) for item in self._reconciliation_results.get(run_id, [])[:limit]]

    def get_reconciliation_result(
        self, organization_id: str, investigation_id: str, run_id: str, result_id: str
    ) -> dict[str, object] | None:
        return next(
            (
                item
                for item in self.list_reconciliation_results(
                    organization_id, investigation_id, run_id
                )
                if item["id"] == result_id
            ),
            None,
        )

    def save_financial_exception_investigation(
        self,
        organization_id: str,
        investigation_id: str,
        result_id: str,
        response: dict[str, object],
    ) -> dict[str, object]:
        record = {
            "organization_id": organization_id,
            "financial_investigation_id": investigation_id,
            "reconciliation_result_id": result_id,
            **response,
        }
        self._financial_exception_investigations[(organization_id, result_id)] = record
        return dict(response)

    def get_financial_exception_investigation(
        self, organization_id: str, investigation_id: str, result_id: str
    ) -> dict[str, object] | None:
        result = self._financial_exception_investigations.get((organization_id, result_id))
        if result is None or result.get("financial_investigation_id") != investigation_id:
            return None
        return {
            key: value
            for key, value in result.items()
            if key
            not in {"organization_id", "financial_investigation_id", "reconciliation_result_id"}
        }

    def save_financial_exception_investigation_tool_calls(
        self, organization_id: str, investigation_id: str, tool_calls: list[dict[str, object]]
    ) -> None:
        del organization_id
        self._financial_exception_investigation_tool_calls[investigation_id] = [
            dict(item) for item in tool_calls
        ]

    def get_financial_exception_investigation_tool_calls(
        self, organization_id: str, investigation_id: str
    ) -> list[dict[str, object]]:
        del organization_id
        return [
            dict(item)
            for item in self._financial_exception_investigation_tool_calls.get(investigation_id, [])
        ]

    def get_idempotency(
        self, organization_id: str, idempotency_key: str
    ) -> dict[str, object] | None:
        record = self._idempotency.get((organization_id, idempotency_key))
        return dict(record) if record else None

    def put_idempotency(
        self,
        organization_id: str,
        actor_id: str,
        idempotency_key: str,
        request_hash: str,
        response_status: int,
        response_body: dict[str, object],
    ) -> None:
        self._idempotency.setdefault(
            (organization_id, idempotency_key),
            {
                "actor_id": actor_id,
                "request_hash": request_hash,
                "response_status": response_status,
                "response_body": dict(response_body),
            },
        )

    def reserve_idempotency(
        self, organization_id: str, actor_id: str, idempotency_key: str, request_hash: str
    ) -> dict[str, object] | None:
        with self._idempotency_lock:
            key = (organization_id, idempotency_key)
            existing = self._idempotency.get(key)
            if existing is not None:
                return dict(existing)
            self._idempotency[key] = {
                "actor_id": actor_id,
                "request_hash": request_hash,
                "response_status": 425,
                "response_body": {"status": "PENDING"},
            }
            return None

    def complete_idempotency(
        self,
        organization_id: str,
        idempotency_key: str,
        response_status: int,
        response_body: dict[str, object],
    ) -> None:
        with self._idempotency_lock:
            record = self._idempotency.get((organization_id, idempotency_key))
            if record is not None:
                record.update(
                    {"response_status": response_status, "response_body": dict(response_body)}
                )

    def release_idempotency(self, organization_id: str, idempotency_key: str) -> None:
        with self._idempotency_lock:
            record = self._idempotency.get((organization_id, idempotency_key))
            if record is not None and record.get("response_status") == 425:
                del self._idempotency[(organization_id, idempotency_key)]

    def save_investigation(self, organization_id: str, response: dict[str, object]) -> None:
        key = (organization_id, str(response["investigation_id"]))
        self._investigations[key] = dict(response)

    def get_investigation(
        self, organization_id: str, investigation_id: str
    ) -> dict[str, object] | None:
        response = self._investigations.get((organization_id, investigation_id))
        return dict(response) if response else None

    def get_investigation_tool_calls(
        self, organization_id: str, investigation_id: str
    ) -> list[dict[str, object]]:
        response = self.get_investigation(organization_id, investigation_id)
        return (
            list(cast(list[dict[str, object]], response.get("tool_calls", []))) if response else []
        )

    def save_evaluation(self, organization_id: str, response: dict[str, object]) -> None:
        key = f"{organization_id}:ai" if response.get("evaluation_kind") == "AI_INVESTIGATION" else organization_id
        self._evaluations[key] = dict(response)

    def get_latest_evaluation(self, organization_id: str) -> dict[str, object] | None:
        response = self._evaluations.get(organization_id)
        return dict(response) if response and response.get("evaluation_kind") != "AI_INVESTIGATION" else None

    def get_latest_ai_evaluation(self, organization_id: str) -> dict[str, object] | None:
        response = self._evaluations.get(f"{organization_id}:ai")
        return dict(response) if response else None

    def save_resolution_request(self, organization_id: str, response: dict[str, object]) -> None:
        self._resolution_requests[(organization_id, str(response["request_id"]))] = {
            **response,
            "approver_ids": [],
        }

    def get_resolution_request(
        self, organization_id: str, request_id: str
    ) -> dict[str, object] | None:
        response = self._resolution_requests.get((organization_id, request_id))
        return dict(response) if response else None

    def update_resolution_request(self, organization_id: str, response: dict[str, object]) -> None:
        current = self._resolution_requests.get((organization_id, str(response["request_id"])), {})
        self._resolution_requests[(organization_id, str(response["request_id"]))] = {
            **response,
            "approver_ids": list(cast(list[str], current.get("approver_ids", []))),
        }

    def save_approval_decision(
        self,
        organization_id: str,
        request_id: str,
        actor_id: str,
        decision: str,
        approval_id: str,
        decided_at: str,
    ) -> bool:
        key = (organization_id, request_id)
        request = self._resolution_requests.get(key)
        if request is None:
            return False
        approver_ids = list(cast(list[str], request.get("approver_ids", [])))
        if actor_id in approver_ids:
            return False
        approver_ids.append(actor_id)
        request["approver_ids"] = approver_ids
        self._approval_decisions.setdefault(key, []).append(
            {
                "actor_id": actor_id,
                "decision": decision,
                "approval_id": approval_id,
                "decided_at": decided_at,
            }
        )
        return True


demo_repository = DemoRepository()


def _public_source_file(record: dict[str, object]) -> dict[str, object]:
    return {
        key: value for key, value in record.items() if key not in {"storage_reference", "sha256"}
    }
