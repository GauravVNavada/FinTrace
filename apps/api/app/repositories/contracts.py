from typing import Any, Protocol

from app.domain.lifecycle import CanonicalLifecycle
from app.domain.schemas import DashboardSummary, ExceptionSummary


class LifecycleRepository(Protocol):
    """Repository contract shared by demo and PostgreSQL implementations."""

    def dashboard_summary(self, organization_id: str) -> DashboardSummary: ...

    def list_exceptions(self, organization_id: str) -> list[ExceptionSummary]: ...

    def lifecycle(self, organization_id: str, order_id: str) -> CanonicalLifecycle: ...

    def list_lifecycles(self, organization_id: str) -> list[CanonicalLifecycle]: ...

    def get_exception(self, organization_id: str, exception_id: str) -> ExceptionSummary | None: ...

    def record_audit_event(
        self,
        organization_id: str,
        event_type: str,
        resource_id: str,
        actor_id: str = "system",
        correlation_id: str | None = None,
    ) -> None: ...

    def audit_events(self, organization_id: str, resource_id: str) -> list[dict[str, str]]: ...

    def audit_events_for_organization(self, organization_id: str) -> list[dict[str, str]]: ...

    def related_exceptions(self, organization_id: str, order_id: str) -> list[ExceptionSummary]: ...


class WorkflowRepository(LifecycleRepository, Protocol):
    """Durable workflow contract shared by the demo and PostgreSQL stores."""

    supports_workflow_persistence: bool

    def get_idempotency(self, organization_id: str, idempotency_key: str) -> dict[str, Any] | None: ...

    def put_idempotency(
        self,
        organization_id: str,
        actor_id: str,
        idempotency_key: str,
        request_hash: str,
        response_status: int,
        response_body: dict[str, Any],
    ) -> None: ...

    def save_investigation(self, organization_id: str, response: dict[str, Any]) -> None: ...

    def get_investigation(self, organization_id: str, investigation_id: str) -> dict[str, Any] | None: ...

    def get_investigation_tool_calls(self, organization_id: str, investigation_id: str) -> list[dict[str, Any]]: ...

    def save_evaluation(self, organization_id: str, response: dict[str, Any]) -> None: ...

    def get_latest_evaluation(self, organization_id: str) -> dict[str, Any] | None: ...

    def save_resolution_request(self, organization_id: str, response: dict[str, Any]) -> None: ...

    def get_resolution_request(self, organization_id: str, request_id: str) -> dict[str, Any] | None: ...

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


def as_json_record(record: dict[str, Any]) -> dict[str, Any]:
    """Return a detached record so repository callers cannot mutate storage state."""
    return dict(record)
