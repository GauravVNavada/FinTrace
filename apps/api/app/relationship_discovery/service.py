from collections import Counter
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from typing import Any

from app.controls.schemas import ActorContext
from app.core.config import get_settings
from app.financial_investigations.files import read_upload
from app.relationship_discovery.schemas import (
    RelationshipDecision,
    RelationshipResponse,
    RelationshipStatus,
)
from app.repositories.contracts import WorkflowRepository
from app.source_analysis.analyzer import analyze_content


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
        profiles = {
            source_id: _profile_source(self._repository, context.organization_id, investigation_id, source_id, mappings[source_id])
            for source_id in analyses
        }
        proposals: list[dict[str, object]] = []
        for index, source in enumerate(sources):
            left_id = str(source["id"])
            left_fields = {
                str(item["canonical_field"])
                for item in mappings[left_id]
                if item.get("status") == "CONFIRMED"
                and item.get("canonical_field")
                and not item.get("ignored")
            }
            for target in sources[index + 1 :]:
                right_id = str(target["id"])
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
                    profile = _relationship_profile(
                        profiles[left_id], profiles[right_id], joins[0]
                    )
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
                            "evidence_summary": _evidence_summary(joins[0], profile),
                            "confidence": profile["confidence"],
                            "confidence_label": profile["confidence_label"],
                            "left_columns": profile["left_columns"],
                            "right_columns": profile["right_columns"],
                            "value_overlap_percent": profile["value_overlap_percent"],
                            "duplicate_key_rate_percent": profile["duplicate_key_rate_percent"],
                            "cardinality": profile["cardinality"],
                            "type_compatibility": profile["type_compatibility"],
                            "temporal_consistency_percent": profile["temporal_consistency_percent"],
                            "amount_agreement_percent": profile["amount_agreement_percent"],
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


def _profile_source(
    repository: WorkflowRepository,
    organization_id: str,
    investigation_id: str,
    source_id: str,
    mappings: list[dict[str, Any]],
) -> dict[str, Any]:
    source = repository.get_source_file_internal(organization_id, investigation_id, source_id)
    if source is None:
        return {"rows": [], "mapping": {}, "profiles": {}}
    filename, content = read_upload(str(source["storage_reference"]))
    document = analyze_content(
        filename,
        content,
        max_rows=get_settings().max_upload_rows,
        max_columns=get_settings().max_upload_columns,
        truncate=True,
    )
    confirmed = {
        str(item["source_column"]): str(item["canonical_field"])
        for item in mappings
        if item.get("status") == "CONFIRMED"
        and item.get("canonical_field")
        and not item.get("ignored")
    }
    rows = [dict(zip(document.headers, raw, strict=True)) for raw in document.rows]
    return {
        "rows": rows,
        "mapping": confirmed,
        "profiles": {profile.name: profile.inferred_type.value for profile in document.profiles},
    }


def _relationship_profile(left: dict[str, Any], right: dict[str, Any], join_field: str) -> dict[str, Any]:
    left_columns = [column for column, canonical in left["mapping"].items() if canonical == join_field]
    right_columns = [column for column, canonical in right["mapping"].items() if canonical == join_field]
    left_column = left_columns[0] if left_columns else join_field
    right_column = right_columns[0] if right_columns else join_field
    left_values = [_norm(row.get(left_column)) for row in left["rows"] if _norm(row.get(left_column))]
    right_values = [_norm(row.get(right_column)) for row in right["rows"] if _norm(row.get(right_column))]
    left_set, right_set = set(left_values), set(right_values)
    overlap = (len(left_set & right_set) / len(left_set) * 100) if left_set else 0.0
    left_counts, right_counts = Counter(left_values), Counter(right_values)
    duplicate_rate = (
        (len(left_values) - len(left_counts)) / len(left_values) * 100
        if left_values
        else 0.0
    )
    cardinality = _cardinality(left_counts, right_counts)
    type_compatibility = (
        "COMPATIBLE"
        if left["profiles"].get(left_column) == right["profiles"].get(right_column)
        or {left["profiles"].get(left_column), right["profiles"].get(right_column)} <= {"STRING", "INTEGER"}
        else "REVIEW"
    )
    temporal = _temporal_consistency(left, right, left_values, right_values, join_field)
    amount = _amount_agreement(left, right, left_values, right_values)
    confidence = min(
        0.99,
        max(
            0.0,
            0.55
            + overlap / 100 * 0.3
            + (temporal if temporal is not None else 100) / 100 * 0.1
            + (amount if amount is not None else 100) / 100 * 0.05
            + (0.05 if type_compatibility == "COMPATIBLE" else 0),
        ),
    )
    if cardinality == "N:N" or overlap < 80 or type_compatibility == "REVIEW":
        label = "LOW"
    elif confidence >= 0.9:
        label = "HIGH"
    else:
        label = "MEDIUM"
    return {
        "left_columns": left_columns,
        "right_columns": right_columns,
        "value_overlap_percent": round(overlap, 2),
        "duplicate_key_rate_percent": round(duplicate_rate, 2),
        "cardinality": cardinality,
        "type_compatibility": type_compatibility,
        "temporal_consistency_percent": round(temporal, 2) if temporal is not None else None,
        "amount_agreement_percent": round(amount, 2) if amount is not None else None,
        "confidence": round(confidence, 4),
        "confidence_label": label,
    }


def _norm(value: Any) -> str:
    return str(value).strip().casefold() if value not in (None, "") else ""


def _cardinality(left: Counter[str], right: Counter[str]) -> str:
    left_many = any(count > 1 for count in left.values())
    right_many = any(count > 1 for count in right.values())
    if left_many and right_many:
        return "N:N"
    if right_many:
        return "1:N"
    if left_many:
        return "N:1"
    return "1:1"


def _temporal_consistency(
    left: dict[str, Any], right: dict[str, Any], left_values: list[str], right_values: list[str], join_field: str
) -> float | None:
    del left_values, right_values, join_field
    left_time = next((column for column, canonical in left["mapping"].items() if canonical in {"created_at", "occurred_at", "processed_at"}), None)
    right_time = next((column for column, canonical in right["mapping"].items() if canonical in {"created_at", "captured_at", "settled_at", "processed_at", "occurred_at"}), None)
    if not left_time or not right_time:
        return None
    left_dates = [_parse_time(row.get(left_time)) for row in left["rows"]]
    right_dates = [_parse_time(row.get(right_time)) for row in right["rows"]]
    valid = sum(item is not None for item in left_dates + right_dates)
    return valid / max(len(left_dates) + len(right_dates), 1) * 100


def _parse_time(value: Any) -> object | None:
    if not value:
        return None
    try:
        from datetime import datetime

        parsed = datetime.fromisoformat(str(value))
        return parsed if parsed.tzinfo else None
    except ValueError:
        return None


def _amount_agreement(
    left: dict[str, Any], right: dict[str, Any], left_values: list[str], right_values: list[str]
) -> float | None:
    del left_values, right_values
    left_amount = next((column for column, canonical in left["mapping"].items() if canonical in {"amount", "gross_amount", "net_amount"}), None)
    right_amount = next((column for column, canonical in right["mapping"].items() if canonical in {"amount", "gross_amount", "net_amount"}), None)
    if not left_amount or not right_amount:
        return None
    left_by_key = {
        _norm(row.get(next((c for c, f in left["mapping"].items() if f == "order_id"), ""))): row
        for row in left["rows"]
    }
    right_by_key = {
        _norm(row.get(next((c for c, f in right["mapping"].items() if f == "order_id"), ""))): row
        for row in right["rows"]
    }
    matches = 0
    total = 0
    for key in set(left_by_key) & set(right_by_key):
        try:
            if abs(Decimal(str(left_by_key[key].get(left_amount))) - Decimal(str(right_by_key[key].get(right_amount)))) <= Decimal("0.01"):
                matches += 1
            total += 1
        except (InvalidOperation, TypeError):
            continue
    return matches / total * 100 if total else None


def _evidence_summary(join_field: str, profile: dict[str, Any]) -> str:
    optional = []
    if profile["temporal_consistency_percent"] is not None:
        optional.append(f"Temporal consistency {profile['temporal_consistency_percent']:.1f}%")
    if profile["amount_agreement_percent"] is not None:
        optional.append(f"amount agreement {profile['amount_agreement_percent']:.1f}%")
    suffix = "; ".join(optional)
    return (
        f"Join on {join_field}: {profile['value_overlap_percent']:.1f}% value overlap; "
        f"{profile['cardinality']} cardinality; "
        f"{profile['duplicate_key_rate_percent']:.1f}% duplicate-key rate; "
        f"types {profile['type_compatibility']}"
        + (f"; {suffix}" if suffix else "")
        + "."
    )
