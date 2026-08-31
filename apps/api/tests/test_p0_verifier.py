from app.domain.schemas import ExceptionType
from app.investigations.schemas import (
    EvidenceItem,
    EvidenceSource,
    InvestigationCandidate,
    InvestigationStatus,
)
from app.investigations.verifier import verify_candidate
from app.repositories.demo import demo_repository


def _candidate(item: EvidenceItem) -> InvestigationCandidate:
    return InvestigationCandidate(
        status=InvestigationStatus.SUPPORTED,
        root_cause_code="ERP_AMOUNT_MISMATCH",
        summary="The invoice amount is inconsistent.",
        supporting_evidence=[item],
        recommended_action_code=None,
        requires_human_review=True,
    )


def test_fact_verifier_rejects_existing_record_with_wrong_status() -> None:
    lifecycle = demo_repository.lifecycle("ORG-001", "ORD-2041")
    result = verify_candidate(
        _candidate(
            EvidenceItem(
                source=EvidenceSource.REFUND,
                record_id="RFND-2991",
                field="status",
                operator="equals",
                expected_value="COMPLETED",
                fact="Refund completed.",
            )
        ),
        ExceptionType.ERP_AMOUNT_MISMATCH,
        lifecycle,
    )
    assert result.candidate.status == InvestigationStatus.UNRESOLVED
    assert len(result.rejected_evidence) == 1
    assert "status" in result.issues[0]


def test_fact_verifier_rejects_nonexistent_record() -> None:
    lifecycle = demo_repository.lifecycle("ORG-001", "ORD-2041")
    result = verify_candidate(
        _candidate(
            EvidenceItem(
                source=EvidenceSource.PAYMENT,
                record_id="PAY-NOT-REAL",
                field="status",
                operator="exists",
                fact="Payment exists.",
            )
        ),
        ExceptionType.ERP_AMOUNT_MISMATCH,
        lifecycle,
    )
    assert result.candidate.status == InvestigationStatus.UNRESOLVED
    assert "does not exist" in result.issues[0]
