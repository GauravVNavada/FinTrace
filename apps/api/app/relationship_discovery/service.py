from datetime import UTC, datetime
from hashlib import sha256

from app.controls.schemas import ActorContext
from app.relationship_discovery.schemas import (
    RelationshipDecision,
    RelationshipResponse,
    RelationshipStatus,
)
from app.repositories.contracts import WorkflowRepository


class RelationshipNotFound(LookupError):
    pass


class RelationshipConflict(ValueError):
    pass


class RelationshipDiscoveryService:
    def __init__(self, repository: WorkflowRepository) -> None:
        self._repository = repository

    def discover(self, context: ActorContext, investigation_id: str) -> list[RelationshipResponse]:
        sources = self._repository.list_source_files(context.organization_id, investigation_id)
        analyses = {
            str(source["id"]): self._repository.get_source_analysis(
                context.organization_id, investigation_id, str(source["id"])
            )
            for source in sources
        }
        mappings = {
            source_id: self._repository.list_source_mappings(
                context.organization_id, investigation_id, source_id
            )
            for source_id in analyses
        }
        proposals: list[dict[str, object]] = []
        for index, source in enumerate(sources):
            left_id = str(source["id"])
            left_type = (analyses[left_id] or {}).get("source_type")
            left_fields = {
                str(item["canonical_field"])
                for item in mappings[left_id]
                if item.get("status") == "CONFIRMED"
                and item.get("canonical_field")
                and not item.get("ignored")
            }
            for target in sources[index + 1 :]:
                right_id = str(target["id"])
                right_type = (analyses[right_id] or {}).get("source_type")
                right_fields = {
                    str(item["canonical_field"])
                    for item in mappings[right_id]
                    if item.get("status") == "CONFIRMED"
                    and item.get("canonical_field")
                    and not item.get("ignored")
                }
                joins = sorted(
                    left_fields
                    & right_fields
                    & {"order_id", "payment_id", "invoice_id", "refund_id", "settlement_id"}
                )
                if joins:
                    proposals.append(
                        {
                            "id": "REL-"
                            + sha256(f"{investigation_id}:{left_id}:{right_id}".encode())
                            .hexdigest()[:12]
                            .upper(),
                            "organization_id": context.organization_id,
                            "financial_investigation_id": investigation_id,
                            "source_file_id": left_id,
                            "target_source_file_id": right_id,
                            "join_fields": joins,
                            "evidence_summary": f"Confirmed mappings overlap on {', '.join(joins)} ({left_type} to {right_type}).",
                            "confidence": min(0.65 + 0.1 * len(joins), 0.95),
                            "status": RelationshipStatus.PROPOSED,
                            "updated_at": datetime.now(UTC),
                        }
                    )
        result = [
            RelationshipResponse.model_validate(item)
            for item in self._repository.save_relationship_proposals(
                context.organization_id, investigation_id, proposals
            )
        ]
        self._repository.update_financial_investigation_status(
            context.organization_id, investigation_id, "RELATIONSHIP_REVIEW"
        )
        return result

    def list(self, organization_id: str, investigation_id: str) -> list[RelationshipResponse]:
        return [
            RelationshipResponse.model_validate(item)
            for item in self._repository.list_relationship_proposals(
                organization_id, investigation_id
            )
        ]

    def decide(
        self,
        context: ActorContext,
        investigation_id: str,
        relationship_id: str,
        payload: RelationshipDecision,
    ) -> RelationshipResponse:
        current = next(
            (
                item
                for item in self._repository.list_relationship_proposals(
                    context.organization_id, investigation_id
                )
                if item["id"] == relationship_id
            ),
            None,
        )
        if current is None:
            raise RelationshipNotFound(relationship_id)
        if current["status"] != RelationshipStatus.PROPOSED:
            raise RelationshipConflict("Only proposed relationships can be decided")
        updated = self._repository.update_relationship_proposal(
            context.organization_id, investigation_id, relationship_id, payload.status.value
        )
        if updated is None:
            raise RelationshipNotFound(relationship_id)
        self._repository.record_audit_event(
            context.organization_id,
            f"RELATIONSHIP_{payload.status.value}",
            relationship_id,
            context.actor_id,
        )
        if not any(
            item.get("status") == RelationshipStatus.PROPOSED
            for item in self._repository.list_relationship_proposals(
                context.organization_id, investigation_id
            )
        ):
            self._repository.update_financial_investigation_status(
                context.organization_id, investigation_id, "READY_TO_BUILD"
            )
        return RelationshipResponse.model_validate(updated)
