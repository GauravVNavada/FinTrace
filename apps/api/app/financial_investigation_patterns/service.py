from collections import defaultdict
from hashlib import sha256
from typing import Any

from app.financial_investigation_patterns.schemas import FinancialInvestigationPatternResponse
from app.repositories.contracts import WorkflowRepository


class FinancialInvestigationPatternService:
    def __init__(self, repository: WorkflowRepository) -> None:
        self._repository = repository

    def list(
        self, organization_id: str, investigation_id: str
    ) -> list[FinancialInvestigationPatternResponse]:
        run = self._repository.latest_reconciliation_run(organization_id, investigation_id)
        if run is None:
            return []
        results = self._repository.list_reconciliation_results(
            organization_id, investigation_id, str(run["id"])
        )
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for result in results:
            if result.get("status") in {"EXCEPTION", "AMBIGUOUS"} and result.get("exception_type"):
                grouped[str(result["exception_type"])].append(result)
        patterns: list[FinancialInvestigationPatternResponse] = []
        for exception_type, members in grouped.items():
            if len(members) < 2:
                continue
            order_ids = [str(item["order_id"]) for item in members]
            patterns.append(
                FinancialInvestigationPatternResponse(
                    pattern_id="FIP-"
                    + sha256(f"{investigation_id}:{exception_type}".encode())
                    .hexdigest()[:12]
                    .upper(),
                    financial_investigation_id=investigation_id,
                    exception_type=exception_type,
                    occurrence_count=len(members),
                    associated_exposure_minor=sum(
                        int(item.get("exposure_minor", 0)) for item in members
                    ),
                    member_order_ids=order_ids,
                    observation="Repeated deterministic exception type in this run; this signal is advisory and does not prove a common root cause.",
                )
            )
        return sorted(patterns, key=lambda item: (-item.occurrence_count, item.exception_type))
