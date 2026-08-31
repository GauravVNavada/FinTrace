from dataclasses import dataclass
from time import perf_counter
from typing import Any

from app.reconciliation.engine import ReconciliationResult, reconcile_dataset


@dataclass(frozen=True, slots=True)
class EvaluationReport:
    lifecycles: int
    auto_reconciled: int
    exceptions: int
    ambiguous: int
    match_rate: float
    match_precision: float
    exception_recall: float
    throughput_per_second: float
    unresolved_exceptions: int


def _ratio(numerator: int, denominator: int) -> float:
    return round(numerator / denominator * 100, 2) if denominator else 0.0


def evaluate_dataset(dataset: Any) -> tuple[EvaluationReport, list[ReconciliationResult]]:
    started = perf_counter()
    results = reconcile_dataset(dataset)
    duration = max(perf_counter() - started, 0.000001)
    truth_by_order = {item["order_id"]: item for item in dataset.ground_truth}
    matched = [
        result for result in results if result.status in {"RECONCILED", "RECONCILED_WITH_VARIANCE"}
    ]
    actual_exceptions = [
        item for item in dataset.ground_truth if item["expected_status"] == "EXCEPTION"
    ]
    detected_exceptions = [result for result in results if result.status == "EXCEPTION"]
    correct_matches = sum(
        1
        for result in matched
        if truth_by_order[result.order_id]["expected_status"]
        in {"RECONCILED", "RECONCILED_WITH_VARIANCE"}
    )
    correct_exceptions = sum(
        1
        for result in detected_exceptions
        if truth_by_order[result.order_id]["expected_status"] == "EXCEPTION"
    )
    return EvaluationReport(
        lifecycles=len(results),
        auto_reconciled=len(matched),
        exceptions=len(detected_exceptions),
        ambiguous=sum(result.status == "AMBIGUOUS" for result in results),
        match_rate=_ratio(len(matched), len(results)),
        match_precision=_ratio(correct_matches, len(matched)),
        exception_recall=_ratio(correct_exceptions, len(actual_exceptions)),
        throughput_per_second=round(len(results) / duration, 2),
        unresolved_exceptions=sum(
            result.status in {"EXCEPTION", "AMBIGUOUS"} for result in results
        ),
    ), results
