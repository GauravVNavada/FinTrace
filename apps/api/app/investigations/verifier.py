from dataclasses import dataclass

from app.domain.lifecycle import CanonicalLifecycle
from app.domain.schemas import ExceptionType
from app.investigations.schemas import (
    InvestigationCandidate,
    InvestigationStatus,
    RecommendationCode,
    RootCauseCode,
)


@dataclass(frozen=True, slots=True)
class VerificationResult:
    candidate: InvestigationCandidate
    evidence_score: int


def verify_candidate(
    candidate: InvestigationCandidate,
    exception_type: ExceptionType,
    lifecycle: CanonicalLifecycle,
) -> VerificationResult:
    valid_ids = _record_ids(lifecycle)
    cited_ids = {
        item.record_id
        for item in candidate.supporting_evidence + candidate.contradictory_evidence
        if item.record_id
    }
    issues = (
        ["A cited record does not exist in the scoped lifecycle."]
        if not cited_ids.issubset(valid_ids)
        else []
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
    return VerificationResult(candidate=candidate, evidence_score=score)


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
