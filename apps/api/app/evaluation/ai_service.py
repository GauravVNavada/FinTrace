from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from statistics import median
from time import perf_counter
from typing import Any
from uuid import uuid4

from app.core.config import get_settings
from app.domain.lifecycle import CanonicalLifecycle
from app.domain.schemas import ExceptionStatus, ExceptionSummary, ExceptionType, Severity
from app.evaluation.schemas import AIEvaluationReportResponse, AIEvaluationResponse
from app.investigations.provider import get_configured_ai_client
from app.investigations.service import InvestigationService


class AIEvaluationService:
    def __init__(self, repository: Any) -> None:
        self._repository = repository

    def run(self, organization_id: str, idempotency_key: str) -> AIEvaluationResponse:
        if not idempotency_key or len(idempotency_key) > 128:
            raise ValueError("Idempotency-Key must be between 1 and 128 characters")
        settings = get_settings()
        provider = get_configured_ai_client(settings)
        investigator = InvestigationService(self._repository, provider)
        cases = _cases(organization_id)
        durations: list[int] = []
        statuses: list[str] = []
        root_correct = 0
        support_correct = 0
        escalation_correct = 0
        cited = 0
        verified = 0
        invalid = 0
        failures = 0
        calls = 0
        for case in cases:
            started = perf_counter()
            try:
                result = investigator.investigate_lifecycle(
                    organization_id, case["exception"], case["lifecycle"]
                )
                status = str(result.status)
                statuses.append(status)
                durations.append(max(result.latency_ms, int((perf_counter() - started) * 1000)))
                calls += len(result.tool_calls)
                if result.status == "FAILED":
                    failures += 1
                if result.status != "FAILED":
                    if case["expected_root"] and result.root_cause_code == case["expected_root"]:
                        root_correct += 1
                    if (result.status == "SUPPORTED") == case["expected_supported"]:
                        support_correct += 1
                    if (result.status == "UNRESOLVED") == (not case["expected_supported"]):
                        escalation_correct += 1
                claims = len(result.supporting_evidence) + len(result.contradictory_evidence) + len(result.rejected_evidence)
                cited += claims
                verified += claims - len(result.rejected_evidence)
                invalid += len(result.rejected_evidence)
            except (KeyError, RuntimeError, TypeError, ValueError):
                failures += 1
                statuses.append("FAILED")
                durations.append(max(0, int((perf_counter() - started) * 1000)))
        resolvable = sum(1 for case in cases if case["expected_root"])
        report = AIEvaluationReportResponse(
            cases=len(cases),
            root_cause_accuracy=_percent(root_correct, resolvable),
            resolution_correctness=_percent(support_correct, len(cases)),
            escalation_accuracy=_percent(escalation_correct, len(cases)),
            evidence_citation_validity=_percent(verified, cited),
            unsupported_claim_rate=_percent(invalid, cited),
            structured_output_validity=_percent(sum(status != "FAILED" for status in statuses), len(cases)),
            average_tool_calls=round(calls / len(cases), 2) if cases else 0,
            p50_latency_ms=float(median(durations)) if durations else 0,
            p95_latency_ms=float(_percentile(durations, 0.95)) if durations else 0,
            provider_failure_rate=_percent(failures, len(cases)),
        )
        response = AIEvaluationResponse(
            evaluation_id=f"AIEVAL-{uuid4().hex[:12].upper()}",
            organization_id=organization_id,
            provider=getattr(provider, "provider", "unknown"),
            model=getattr(provider, "model", "unknown"),
            report=report,
            created_at=datetime.now(UTC),
        )
        body = {
            **response.model_dump(mode="json"),
            "evaluation_kind": "AI_INVESTIGATION",
            "idempotency_key": idempotency_key,
        }
        self._repository.save_evaluation(organization_id, body)
        return response

    def latest(self, organization_id: str) -> AIEvaluationResponse | None:
        data = self._repository.get_latest_ai_evaluation(organization_id)
        return AIEvaluationResponse.model_validate(data) if data else None


def _percent(numerator: int, denominator: int) -> float:
    return round(numerator / denominator * 100, 2) if denominator else 0.0


def _percentile(values: list[int], quantile: float) -> int:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, max(0, int((len(ordered) - 1) * quantile)))]


def _base(order_id: str, amount: int = 10000) -> CanonicalLifecycle:
    return CanonicalLifecycle(
        order={"organization_id": "ORG-EVAL", "order_id": order_id, "amount_minor": amount, "status": "COMPLETED"},
        payments=({"payment_id": f"PAY-{order_id}", "order_id": order_id, "amount_minor": amount, "status": "CAPTURED", "gateway_fee_minor": 180},),
        settlements=({"settlement_id": f"SET-{order_id}", "payment_id": f"PAY-{order_id}", "gross_minor": amount, "fees_minor": 180, "tax_minor": 32, "net_minor": amount - 212, "status": "RECEIVED"},),
        invoices=({"invoice_id": f"INV-{order_id}", "order_id": order_id, "amount_minor": amount, "status": "ACTIVE"},),
        refunds=(), inventory_movements=(), employee_actions=(),
    )


def _case(organization_id: str, number: int, exception_type: ExceptionType, lifecycle: CanonicalLifecycle, root: str | None, supported: bool) -> dict[str, Any]:
    return {
        "lifecycle": lifecycle,
        "expected_root": root,
        "expected_supported": supported,
        "exception": ExceptionSummary(
            id=f"AI-EVAL-{number:02d}", organization_id=organization_id,
            order_id=str(lifecycle.order["order_id"]), type=exception_type,
            severity=Severity.HIGH, status=ExceptionStatus.OPEN,
            financial_exposure=Decimal(100), currency="INR",
            detected_at=datetime.now(UTC), rules_triggered=[exception_type.value],
        ),
    }


def _cases(organization_id: str) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for number in range(1, 4):
        lifecycle = _base(f"AIE{number:03d}")
        cases.append(_case(organization_id, number, ExceptionType.MISSING_SETTLEMENT, replace(lifecycle, settlements=()), "SETTLEMENT_MISSING", False))
    for number in range(4, 7):
        lifecycle = _base(f"AIE{number:03d}")
        refund = {"refund_id": f"RF-{number:03d}", "payment_id": f"PAY-AIE{number:03d}", "amount_minor": 10000, "status": "PROCESSED"}
        cases.append(_case(organization_id, number, ExceptionType.REFUND_WITHOUT_INVENTORY_RETURN, replace(lifecycle, refunds=(refund,)), "INCOMPLETE_REFUND_WORKFLOW", True))
    for number in range(7, 10):
        lifecycle = _base(f"AIE{number:03d}", 12000)
        invoice = {"invoice_id": f"INV-AIE{number:03d}", "order_id": f"AIE{number:03d}", "amount_minor": 9000, "status": "ACTIVE"}
        cases.append(_case(organization_id, number, ExceptionType.ERP_AMOUNT_MISMATCH, replace(lifecycle, invoices=(invoice,)), "ERP_AMOUNT_MISMATCH", True))
    return cases
