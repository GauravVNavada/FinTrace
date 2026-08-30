from dataclasses import dataclass, field
from decimal import Decimal
from hashlib import sha1

from app.domain.lifecycle import CanonicalLifecycle
from app.patterns.schemas import PatternResponse
from app.reconciliation.engine import reconcile_lifecycle
from app.repositories.demo import DemoRepository


@dataclass(slots=True)
class _PatternGroup:
    exception_type: str
    location: str
    workflow: str
    exposure_minor: int = 0
    order_ids: list[str] = field(default_factory=list)
    severities: list[str] = field(default_factory=list)


class PatternNotFoundError(LookupError):
    pass


class PatternService:
    def __init__(self, repository: DemoRepository) -> None:
        self._repository = repository

    def list(self, organization_id: str, limit: int = 20) -> list[PatternResponse]:
        groups: dict[tuple[str, str, str], _PatternGroup] = {}
        for lifecycle in self._repository.list_lifecycles(organization_id):
            result = reconcile_lifecycle(lifecycle)
            if result.status not in {"EXCEPTION", "AMBIGUOUS"} or result.exception_type is None:
                continue
            location = str(lifecycle.order.get("store", "Unknown"))
            workflow = self._workflow(lifecycle)
            key = (result.exception_type, location, workflow)
            group = groups.setdefault(key, _PatternGroup(result.exception_type, location, workflow))
            group.exposure_minor += result.exposure_minor
            group.order_ids.append(str(lifecycle.order["order_id"]))
            group.severities.append(result.severity)
        patterns = [self._to_response(group) for group in groups.values() if len(group.order_ids) >= 2]
        patterns.sort(key=lambda item: (-item.occurrence_count, -item.associated_exposure, item.pattern_id))
        return patterns[:limit]

    def get(self, organization_id: str, pattern_id: str) -> PatternResponse:
        for pattern in self.list(organization_id, limit=100):
            if pattern.pattern_id == pattern_id:
                return pattern
        raise PatternNotFoundError(pattern_id)

    @staticmethod
    def _workflow(lifecycle: CanonicalLifecycle) -> str:
        if any(action.get("action") == "MANUAL_REFUND_APPROVED" for action in lifecycle.employee_actions):
            return "Manual POS refund"
        return "Standard workflow"

    @staticmethod
    def _to_response(group: _PatternGroup) -> PatternResponse:
        assert group.order_ids is not None
        assert group.severities is not None
        pattern_id = f"PAT-{sha1(f'{group.exception_type}|{group.location}|{group.workflow}'.encode()).hexdigest()[:8].upper()}"
        title, recommendation = {
            "REFUND_WITHOUT_INVENTORY_RETURN": (
                "Refund handoff without inventory disposition",
                "Require inventory disposition before a physical-goods refund reaches COMPLETE.",
            ),
            "ERP_INVOICE_MISSING": (
                "ERP invoice creation gap",
                "Retry ERP invoice creation after the sync window and alert on the next failure.",
            ),
            "DUPLICATE_PAYMENT": (
                "Duplicate payment capture candidates",
                "Enforce gateway event idempotency on the capture reference.",
            ),
            "AMBIGUOUS_ASSOCIATION": (
                "Ambiguous payment association",
                "Require a stronger source reference before payment matching.",
            ),
        }.get((group.exception_type), (f"Recurring {group.exception_type.lower().replace('_', ' ')}", "Review the shared workflow control."))
        severity_rank = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}
        severity = max(group.severities, key=lambda value: severity_rank.get(value, 0))
        return PatternResponse(
            pattern_id=pattern_id,
            exception_type=group.exception_type,
            title=title,
            occurrence_count=len(group.order_ids),
            associated_exposure=Decimal(group.exposure_minor) / Decimal(100),
            currency="INR",
            location=group.location,
            workflow=group.workflow,
            observation=f"{len(group.order_ids)} incidents share the same exception, location, and workflow attributes.",
            prevention_recommendation=recommendation,
            severity=severity,
            member_order_ids=group.order_ids[:100],
        )
