from typing import Any, Protocol

from app.domain.schemas import ExceptionSummary
from app.investigations.schemas import EvidenceItem


class ProviderUnavailable(RuntimeError):
    """The configured investigation provider cannot safely answer."""


class AIClient(Protocol):
    def investigate(self, exception: ExceptionSummary, evidence: list[EvidenceItem]) -> Any:
        ...


class StubAIClient:
    """Deterministic provider adapter used until a real provider is configured."""

    def investigate(self, exception: ExceptionSummary, evidence: list[EvidenceItem]) -> dict[str, Any]:
        if exception.type.value == "REFUND_WITHOUT_INVENTORY_RETURN":
            return {
                "status": "SUPPORTED",
                "root_cause_code": "INCOMPLETE_REFUND_WORKFLOW",
                "summary": "Refund completed but the downstream inventory return was not recorded.",
                "supporting_evidence": [item.model_dump(mode="json") for item in evidence if item.source.value in {"order", "payment", "invoice", "refund", "inventory", "employee_action"}],
                "contradictory_evidence": [],
                "missing_evidence": ["Physical goods receipt confirmation unavailable"],
                "recommended_action_code": "REQUEST_INVENTORY_VERIFICATION",
                "requires_human_review": True,
            }
        return {
            "status": "UNRESOLVED",
            "root_cause_code": "UNKNOWN",
            "summary": "The available evidence does not support a bounded root-cause conclusion.",
            "supporting_evidence": [item.model_dump(mode="json") for item in evidence[:5]],
            "contradictory_evidence": [],
            "missing_evidence": ["Exception-specific evidence is incomplete"],
            "recommended_action_code": "REQUEST_MANUAL_REVIEW",
            "requires_human_review": True,
        }


class UnavailableAIClient:
    def investigate(self, exception: ExceptionSummary, evidence: list[EvidenceItem]) -> Any:
        raise ProviderUnavailable("investigation provider is unavailable")


def get_ai_client(provider_name: str) -> AIClient:
    if provider_name.lower() == "stub":
        return StubAIClient()
    return UnavailableAIClient()
