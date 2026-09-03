from typing import Any, Protocol

from app.domain.lifecycle import CanonicalLifecycle
from app.domain.schemas import DashboardSummary, ExceptionSummary


class LifecycleRepository(Protocol):
    """Repository contract shared by demo and PostgreSQL implementations."""

    def dashboard_summary(self, organization_id: str) -> DashboardSummary: ...

    def list_exceptions(self, organization_id: str, limit: int = 100) -> list[ExceptionSummary]: ...

    def lifecycle(self, organization_id: str, order_id: str) -> CanonicalLifecycle: ...

    def list_lifecycles(
        self, organization_id: str, limit: int = 1000
    ) -> list[CanonicalLifecycle]: ...

    def get_exception(self, organization_id: str, exception_id: str) -> ExceptionSummary | None: ...

    def record_audit_event(
        self,
        organization_id: str,
        event_type: str,
        resource_id: str,
        actor_id: str = "system",
        correlation_id: str | None = None,
    ) -> None: ...

    def audit_events(
        self, organization_id: str, resource_id: str, limit: int = 200
    ) -> list[dict[str, str]]: ...

    def audit_events_for_organization(
        self, organization_id: str, limit: int = 200
    ) -> list[dict[str, str]]: ...

    def related_exceptions(self, organization_id: str, order_id: str) -> list[ExceptionSummary]: ...


class WorkflowRepository(LifecycleRepository, Protocol):
    """Durable workflow contract shared by the demo and PostgreSQL stores."""

    supports_workflow_persistence: bool

    def create_financial_investigation(
        self, organization_id: str, data: dict[str, Any]
    ) -> dict[str, Any]: ...

    def list_financial_investigations(
        self, organization_id: str, limit: int = 100
    ) -> list[dict[str, Any]]: ...

    def get_financial_investigation(
        self, organization_id: str, investigation_id: str
    ) -> dict[str, Any] | None: ...

    def update_financial_investigation_status(
        self, organization_id: str, investigation_id: str, status: str
    ) -> None: ...

    def add_source_file(
        self, organization_id: str, investigation_id: str, data: dict[str, Any]
    ) -> dict[str, Any]: ...

    def list_source_files(
        self, organization_id: str, investigation_id: str, limit: int = 100
    ) -> list[dict[str, Any]]: ...

    def delete_source_file(
        self, organization_id: str, investigation_id: str, source_file_id: str
    ) -> dict[str, Any] | None: ...

    def get_source_file_internal(
        self, organization_id: str, investigation_id: str, source_file_id: str
    ) -> dict[str, Any] | None: ...

    def update_source_analysis_state(
        self,
        organization_id: str,
        investigation_id: str,
        source_file_id: str,
        status: str,
        detected_source_type: str,
        classification_confidence: float,
    ) -> None: ...

    def save_source_analysis(
        self, organization_id: str, investigation_id: str, source_file_id: str, data: dict[str, Any]
    ) -> dict[str, Any]: ...

    def get_source_analysis(
        self, organization_id: str, investigation_id: str, source_file_id: str
    ) -> dict[str, Any] | None: ...

    def list_source_mappings(
        self, organization_id: str, investigation_id: str, source_file_id: str
    ) -> list[dict[str, Any]]: ...

    def save_source_mappings(
        self,
        organization_id: str,
        investigation_id: str,
        source_file_id: str,
        mappings: list[dict[str, Any]],
    ) -> list[dict[str, Any]]: ...

    def update_source_mapping(
        self,
        organization_id: str,
        investigation_id: str,
        source_file_id: str,
        mapping_id: str,
        data: dict[str, Any],
    ) -> dict[str, Any] | None: ...

    def confirm_source_mappings(
        self, organization_id: str, investigation_id: str, source_file_id: str
    ) -> dict[str, Any] | None: ...

    def list_relationship_proposals(
        self, organization_id: str, investigation_id: str
    ) -> list[dict[str, Any]]: ...

    def save_relationship_proposals(
        self, organization_id: str, investigation_id: str, proposals: list[dict[str, Any]]
    ) -> list[dict[str, Any]]: ...

    def update_relationship_proposal(
        self, organization_id: str, investigation_id: str, relationship_id: str, status: str
    ) -> dict[str, Any] | None: ...

    def next_dataset_version(self, organization_id: str, investigation_id: str) -> int: ...

    def save_dataset_version(
        self, organization_id: str, version: dict[str, Any], records: list[dict[str, Any]]
    ) -> dict[str, Any]: ...

    def latest_dataset_version(
        self, organization_id: str, investigation_id: str
    ) -> dict[str, Any] | None: ...

    def list_dataset_versions(
        self, organization_id: str, investigation_id: str
    ) -> list[dict[str, Any]]: ...

    def list_normalized_records(
        self,
        organization_id: str,
        investigation_id: str,
        dataset_version_id: str,
        limit: int = 1000,
    ) -> list[dict[str, Any]]: ...

    def save_reconciliation_run(
        self, organization_id: str, run: dict[str, Any], results: list[dict[str, Any]]
    ) -> dict[str, Any]: ...

    def latest_reconciliation_run(
        self, organization_id: str, investigation_id: str
    ) -> dict[str, Any] | None: ...

    def list_reconciliation_results(
        self, organization_id: str, investigation_id: str, run_id: str, limit: int = 1000
    ) -> list[dict[str, Any]]: ...

    def get_reconciliation_result(
        self, organization_id: str, investigation_id: str, run_id: str, result_id: str
    ) -> dict[str, Any] | None: ...

    def save_financial_exception_investigation(
        self, organization_id: str, investigation_id: str, result_id: str, response: dict[str, Any]
    ) -> dict[str, Any]: ...

    def get_financial_exception_investigation(
        self, organization_id: str, investigation_id: str, result_id: str
    ) -> dict[str, Any] | None: ...

    def save_financial_exception_investigation_tool_calls(
        self, organization_id: str, investigation_id: str, tool_calls: list[dict[str, Any]]
    ) -> None: ...

    def save_financial_exception_investigation_with_tool_calls(
        self,
        organization_id: str,
        investigation_id: str,
        result_id: str,
        response: dict[str, Any],
        tool_calls: list[dict[str, Any]],
    ) -> dict[str, Any]: ...

    def get_financial_exception_investigation_tool_calls(
        self, organization_id: str, investigation_id: str
    ) -> list[dict[str, Any]]: ...

    def get_idempotency(
        self, organization_id: str, idempotency_key: str
    ) -> dict[str, Any] | None: ...

    def put_idempotency(
        self,
        organization_id: str,
        actor_id: str,
        idempotency_key: str,
        request_hash: str,
        response_status: int,
        response_body: dict[str, Any],
    ) -> None: ...

    def reserve_idempotency(
        self,
        organization_id: str,
        actor_id: str,
        idempotency_key: str,
        request_hash: str,
    ) -> dict[str, Any] | None: ...

    def complete_idempotency(
        self,
        organization_id: str,
        idempotency_key: str,
        response_status: int,
        response_body: dict[str, Any],
    ) -> None: ...

    def release_idempotency(self, organization_id: str, idempotency_key: str) -> None: ...

    def save_investigation(self, organization_id: str, response: dict[str, Any]) -> None: ...

    def get_investigation(
        self, organization_id: str, investigation_id: str
    ) -> dict[str, Any] | None: ...

    def get_investigation_tool_calls(
        self, organization_id: str, investigation_id: str
    ) -> list[dict[str, Any]]: ...

    def save_evaluation(self, organization_id: str, response: dict[str, Any]) -> None: ...

    def get_latest_evaluation(self, organization_id: str) -> dict[str, Any] | None: ...

    def get_latest_ai_evaluation(self, organization_id: str) -> dict[str, Any] | None: ...

    def save_resolution_request(self, organization_id: str, response: dict[str, Any]) -> None: ...

    def get_resolution_request(
        self, organization_id: str, request_id: str
    ) -> dict[str, Any] | None: ...

    def update_resolution_request(self, organization_id: str, response: dict[str, Any]) -> None: ...

    def save_approval_decision(
        self,
        organization_id: str,
        request_id: str,
        actor_id: str,
        decision: str,
        approval_id: str,
        decided_at: str,
    ) -> bool: ...

    def apply_approval_decision(
        self,
        organization_id: str,
        request_id: str,
        actor_id: str,
        decision: str,
        approval_id: str,
        decided_at: str,
    ) -> dict[str, Any] | None: ...


def as_json_record(record: dict[str, Any]) -> dict[str, Any]:
    """Return a detached record so repository callers cannot mutate storage state."""
    return dict(record)
