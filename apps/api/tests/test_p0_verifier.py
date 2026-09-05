from app.domain.schemas import ExceptionType
from app.investigations.schemas import (
    EvidenceItem,
    EvidenceSource,
    InvestigationCandidate,
    InvestigationStatus,
)
from app.investigations.verifier import verify_candidate
from app.repositories.sample import sample_repository


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
    lifecycle = sample_repository.lifecycle("ORG-001", "ORD-2041")
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
    lifecycle = sample_repository.lifecycle("ORG-001", "ORD-2041")
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


def test_fact_verifier_accepts_backend_provenance_for_missing_settlement() -> None:
    lifecycle = sample_repository.lifecycle("ORG-001", "ORD-2041")
    lifecycle = lifecycle.__class__(
        order=lifecycle.order,
        payments=lifecycle.payments,
        settlements=(),
        invoices=lifecycle.invoices,
        refunds=lifecycle.refunds,
        inventory_movements=lifecycle.inventory_movements,
        employee_actions=lifecycle.employee_actions,
    )
    result = verify_candidate(
        _candidate(
            EvidenceItem(
                source=EvidenceSource.SETTLEMENT,
                record_id=None,
                field="settlement_id",
                operator="missing",
                expected_value=None,
                fact="No settlement record exists for the scoped payment.",
            )
        ),
        ExceptionType.ERP_AMOUNT_MISMATCH,
        lifecycle,
    )
    assert result.rejected_evidence == []
    assert result.issues == []
    assert result.candidate.supporting_evidence[0].verified is True


def test_fact_verifier_accepts_cited_inventory_value_mismatch():
    lifecycle = sample_repository.lifecycle("ORG-001", "ORD-2041")
    lifecycle = lifecycle.__class__(
        order=lifecycle.order,
        payments=lifecycle.payments,
        settlements=lifecycle.settlements,
        invoices=lifecycle.invoices,
        refunds=lifecycle.refunds,
        inventory_movements=(
            {"movement_id": "MOV-SALE", "movement_type": "SALE", "quantity": 1, "unit_cost_minor": 2400, "inventory_value_minor": 2400},
            {"movement_id": "MOV-RETURN", "movement_type": "RETURN", "quantity": 1, "unit_cost_minor": 2500, "inventory_value_minor": 2500},
        ),
        employee_actions=lifecycle.employee_actions,
    )
    candidate = InvestigationCandidate(
        status=InvestigationStatus.SUPPORTED,
        root_cause_code="INVENTORY_VALUE_MISMATCH",
        summary="The return value differs from the sold inventory cost value.",
        supporting_evidence=[
            EvidenceItem(source=EvidenceSource.ORDER, record_id="ORD-2041", field="amount_minor", operator="exists", fact="Order exists."),
            EvidenceItem(source=EvidenceSource.REFUND, record_id="RFND-2991", field="amount_minor", operator="exists", fact="Refund exists."),
            EvidenceItem(source=EvidenceSource.INVENTORY, record_id="MOV-SALE", field="movement_type", operator="equals", expected_value="SALE", fact="Sale movement exists."),
            EvidenceItem(source=EvidenceSource.INVENTORY, record_id="MOV-SALE", field="inventory_value_minor", operator="equals", expected_value=2400, fact="Sale value is 2400."),
            EvidenceItem(source=EvidenceSource.INVENTORY, record_id="MOV-RETURN", field="movement_type", operator="equals", expected_value="RETURN", fact="Return movement exists."),
            EvidenceItem(source=EvidenceSource.INVENTORY, record_id="MOV-RETURN", field="inventory_value_minor", operator="equals", expected_value=2500, fact="Return value is 2500."),
        ],
        requires_human_review=True,
    )
    result = verify_candidate(candidate, ExceptionType.INVENTORY_VALUE_MISMATCH, lifecycle)
    assert result.issues == []
    assert result.candidate.status == InvestigationStatus.SUPPORTED


def test_fact_verifier_rejects_inventory_value_claim_without_sale_or_return_evidence():
    lifecycle = sample_repository.lifecycle("ORG-001", "ORD-2041")
    candidate = InvestigationCandidate(
        status=InvestigationStatus.SUPPORTED,
        root_cause_code="INVENTORY_VALUE_MISMATCH",
        summary="The return value differs from the sold inventory cost value.",
        supporting_evidence=[
            EvidenceItem(source=EvidenceSource.ORDER, record_id="ORD-2041", field="amount_minor", operator="exists", fact="Order exists."),
            EvidenceItem(source=EvidenceSource.REFUND, record_id="RFND-2991", field="amount_minor", operator="exists", fact="Refund exists."),
        ],
        requires_human_review=True,
    )
    result = verify_candidate(candidate, ExceptionType.INVENTORY_VALUE_MISMATCH, lifecycle)
    assert result.candidate.status == InvestigationStatus.UNRESOLVED
    assert "SALE evidence" in result.issues[0]
