from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from app.domain.lifecycle import CanonicalLifecycle
from app.domain.schemas import ExceptionType
from app.investigations.schemas import (
    EvidenceItem,
    InvestigationCandidate,
    InvestigationStatus,
    RecommendationCode,
    RootCauseCode,
)


@dataclass(frozen=True, slots=True)
class VerificationResult:
    candidate: InvestigationCandidate
    evidence_score: int
    issues: list[str]
    rejected_evidence: list[EvidenceItem]


def verify_candidate(
    candidate: InvestigationCandidate,
    exception_type: ExceptionType,
    lifecycle: CanonicalLifecycle,
) -> VerificationResult:
    issues: list[str] = []
    verified_supporting = []
    verified_contradictory = []
    rejected_evidence = []
    for item in candidate.supporting_evidence:
        verified, issue = _verify_evidence(item, lifecycle)
        if verified:
            verified_supporting.append(item.model_copy(update={"verified": True}))
        else:
            rejected_evidence.append(item.model_copy(update={"verified": False, "verification_issue": issue}))
            issues.append(issue)
    for item in candidate.contradictory_evidence:
        verified, issue = _verify_evidence(item, lifecycle)
        if verified:
            verified_contradictory.append(item.model_copy(update={"verified": True}))
        else:
            rejected_evidence.append(item.model_copy(update={"verified": False, "verification_issue": issue}))
            issues.append(issue)
    candidate = candidate.model_copy(
        update={
            "supporting_evidence": verified_supporting,
            "contradictory_evidence": verified_contradictory,
        }
    )
    issues.extend(_compatibility_issues(candidate, exception_type, lifecycle))
    if candidate.status == InvestigationStatus.SUPPORTED and not candidate.supporting_evidence:
        issues.append("Supported results require supporting evidence.")

    score = _evidence_score(candidate, exception_type, lifecycle, issues)
    if issues:
        candidate = candidate.model_copy(
            update={
                "status": InvestigationStatus.UNRESOLVED,
                "summary": "Investigation is unresolved because the evidence did not pass deterministic verification.",
                "recommended_action_code": None,
                "requires_human_review": True,
                "missing_evidence": [*candidate.missing_evidence, *issues],
            }
        )
    return VerificationResult(
        candidate=candidate, evidence_score=score, issues=issues, rejected_evidence=rejected_evidence
    )


def _rows_for_source(lifecycle: CanonicalLifecycle, source: str) -> list[dict[str, Any]]:
    rows: dict[str, list[dict[str, Any]]] = {
        "order": [lifecycle.order],
        "payment": list(lifecycle.payments),
        "settlement": list(lifecycle.settlements),
        "invoice": list(lifecycle.invoices),
        "refund": list(lifecycle.refunds),
        "inventory": list(lifecycle.inventory_movements),
        "employee_action": list(lifecycle.employee_actions),
    }
    return rows.get(source, [])


def _verify_evidence(item: Any, lifecycle: CanonicalLifecycle) -> tuple[bool, str]:
    rows = _rows_for_source(lifecycle, item.source.value)
    if item.record_id is None:
        if item.operator != "missing" or not item.field:
            return False, f"Evidence for {item.source.value} is missing a record_id."
        if item.expected_value is None:
            exists = any(row.get(item.field) is not None for row in rows)
        else:
            exists = any(
                _normal_value(row.get(item.field)) == _normal_value(item.expected_value)
                for row in rows
            )
        return (
            (not exists, f"Claimed {item.source.value}.{item.field}={item.expected_value!r} is present, but the scoped data contradicts it.")
            if exists
            else (True, "")
        )
    matching = [row for row in rows if _record_id_for_source(row, item.source.value) == item.record_id]
    if not matching:
        return False, f"Cited {item.source.value} record {item.record_id} does not exist in the scoped lifecycle."
    if item.operator is None:
        return True, ""
    if not item.field:
        return False, f"Cited {item.source.value} record {item.record_id} has no field for verification."
    actual = matching[0].get(item.field)
    if _compare(actual, item.operator, item.expected_value):
        return True, ""
    return False, (
        f"Cited {item.source.value} record {item.record_id} has {item.field}={actual!r}, "
        f"not {item.operator} {item.expected_value!r}."
    )


def _record_id_for_source(row: dict[str, Any], source: str) -> str | None:
    key = {
        "order": "order_id",
        "payment": "payment_id",
        "settlement": "settlement_id",
        "invoice": "invoice_id",
        "refund": "refund_id",
        "inventory": "movement_id",
        "employee_action": "action_id",
    }.get(source)
    value = row.get(key) if key else None
    return str(value) if value is not None else None


def _compare(actual: Any, operator: str | None, expected: Any) -> bool:
    if operator == "exists":
        return actual is not None
    if operator == "missing":
        return actual is None or str(actual) != str(expected)
    if actual is None:
        return False
    if operator == "equals":
        return _normal_value(actual) == _normal_value(expected)
    if operator == "not_equals":
        return _normal_value(actual) != _normal_value(expected)
    try:
        left = Decimal(str(actual))
        right = Decimal(str(expected))
    except (InvalidOperation, ValueError):
        return False
    if operator == "greater_than":
        return left > right
    if operator == "less_than":
        return left < right
    return False


def _normal_value(value: Any) -> Any:
    if isinstance(value, bool):
        return value
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return str(value).casefold()


def _record_ids(lifecycle: CanonicalLifecycle) -> set[str]:
    keys = (
        "order_id",
        "payment_id",
        "settlement_id",
        "invoice_id",
        "refund_id",
        "movement_id",
        "action_id",
    )
    return {
        str(value)
        for rows in (
            lifecycle.order,
            *lifecycle.payments,
            *lifecycle.settlements,
            *lifecycle.invoices,
            *lifecycle.refunds,
            *lifecycle.inventory_movements,
            *lifecycle.employee_actions,
        )
        for key in keys
        if (value := rows.get(key)) is not None
    }


def _compatibility_issues(
    candidate: InvestigationCandidate, exception_type: ExceptionType, lifecycle: CanonicalLifecycle
) -> list[str]:
    if exception_type == ExceptionType.AMBIGUOUS_ASSOCIATION and candidate.status == InvestigationStatus.SUPPORTED:
        return ["Ambiguous associations cannot be marked SUPPORTED without a unique relationship."]
    if candidate.root_cause_code is None:
        return (
            ["A root-cause code is required for verification."]
            if candidate.status == InvestigationStatus.SUPPORTED
            else []
        )
    expected = {
        ExceptionType.REFUND_WITHOUT_INVENTORY_RETURN: {
            RootCauseCode.INCOMPLETE_REFUND_WORKFLOW,
            RootCauseCode.INVENTORY_REVERSAL_MISSING,
        },
        ExceptionType.REFUND_WITHOUT_ERP_REVERSAL: {RootCauseCode.ERP_REVERSAL_MISSING},
        ExceptionType.DUPLICATE_PAYMENT: {
            RootCauseCode.DUPLICATE_PAYMENT,
            RootCauseCode.AMBIGUOUS_ASSOCIATION,
        },
        ExceptionType.MISSING_SETTLEMENT: {RootCauseCode.SETTLEMENT_MISSING},
        ExceptionType.ERP_INVOICE_MISSING: {RootCauseCode.ERP_INVOICE_MISSING},
        ExceptionType.ERP_AMOUNT_MISMATCH: {RootCauseCode.ERP_AMOUNT_MISMATCH},
        ExceptionType.PAYMENT_FEE_MISSING: {
            RootCauseCode.PAYMENT_FEE_MISSING,
            RootCauseCode.DATA_QUALITY_ERROR,
        },
        ExceptionType.SETTLEMENT_FEE_MISSING: {
            RootCauseCode.SETTLEMENT_FEE_MISSING,
            RootCauseCode.DATA_QUALITY_ERROR,
        },
    }
    if exception_type in expected and candidate.root_cause_code not in expected[exception_type]:
        return ["Root-cause code is not compatible with the deterministic exception type."]
    if candidate.recommended_action_code is not None and not _action_allowed(
        candidate.recommended_action_code, candidate.root_cause_code
    ):
        return ["Recommendation is not allowed for the selected root-cause code."]
    if candidate.root_cause_code in {
        RootCauseCode.INCOMPLETE_REFUND_WORKFLOW,
        RootCauseCode.INVENTORY_REVERSAL_MISSING,
    }:
        has_refund = any(item.source.value == "refund" for item in candidate.supporting_evidence)
        has_missing_return = any(
            item.source.value == "inventory" and item.record_id is None
            for item in candidate.supporting_evidence
        )
        if not has_refund or not has_missing_return:
            return [
                "Refund workflow conclusions require refund evidence and an explicit missing-return finding."
            ]
    return []


def _action_allowed(action: RecommendationCode, root_cause: RootCauseCode | None) -> bool:
    allowed = {
        RootCauseCode.INCOMPLETE_REFUND_WORKFLOW: RecommendationCode.REQUEST_INVENTORY_VERIFICATION,
        RootCauseCode.INVENTORY_REVERSAL_MISSING: RecommendationCode.REQUEST_INVENTORY_VERIFICATION,
        RootCauseCode.ERP_REVERSAL_MISSING: RecommendationCode.REQUEST_ERP_REVERSAL_REVIEW,
        RootCauseCode.DUPLICATE_PAYMENT: RecommendationCode.REQUEST_PAYMENT_REVIEW,
        RootCauseCode.AMBIGUOUS_ASSOCIATION: RecommendationCode.REQUEST_MANUAL_REVIEW,
    }
    return root_cause not in allowed or allowed[root_cause] == action


def _evidence_score(
    candidate: InvestigationCandidate,
    exception_type: ExceptionType,
    lifecycle: CanonicalLifecycle,
    issues: list[str],
) -> int:
    sources = {item.source.value for item in candidate.supporting_evidence}
    score = (
        25
        if any(
            item.source.value == "order" and item.record_id
            for item in candidate.supporting_evidence
        )
        else 0
    )
    score += sum(
        {
            "payment": 15,
            "settlement": 15,
            "invoice": 10,
            "refund": 10,
            "inventory": 10,
            "employee_action": 5,
        }.get(source, 0)
        for source in sources
    )
    if candidate.root_cause_code is not None and not issues:
        score += 10
    if candidate.contradictory_evidence:
        score -= 25
    if candidate.missing_evidence:
        score -= 15
    score -= 25 if exception_type.value == "AMBIGUOUS_ASSOCIATION" else 0
    return max(0, min(100, score))
