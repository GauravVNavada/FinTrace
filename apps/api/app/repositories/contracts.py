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


def as_json_record(record: dict[str, Any]) -> dict[str, Any]:
    """Return a detached record so repository callers cannot mutate storage state."""
    return dict(record)
