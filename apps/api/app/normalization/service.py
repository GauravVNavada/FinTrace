import json
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from hashlib import sha256
from uuid import uuid4

from app.controls.schemas import ActorContext
from app.core.config import get_settings
from app.financial_investigations.files import read_upload
from app.financial_investigations.schemas import SourceType
from app.normalization.schemas import DatasetVersionResponse, NormalizedRecordResponse
from app.repositories.contracts import WorkflowRepository
from app.source_analysis.analyzer import analyze_content


class NormalizationBlocked(ValueError):
    def __init__(self, reasons: list[str]) -> None:
        self.reasons = reasons
        summary = "; ".join(reasons[:3])
        if len(reasons) > 3:
            summary += f"; and {len(reasons) - 3} additional row issues. Correct the source format and upload the corrected file."
        super().__init__("Normalization requires review: " + summary)


class DatasetVersionNotFound(LookupError):
    pass


class NormalizationConflict(ValueError):
    pass


_MONEY_FIELDS = {
    "amount": "amount_minor",
    "gross_amount": "gross_minor",
    "fee_amount": "fees_minor",
    "gateway_fee_amount": "gateway_fee_minor",
    "tax_amount": "tax_minor",
    "net_amount": "net_minor",
    "unit_cost": "unit_cost_minor",
    "inventory_value": "inventory_value_minor",
}

_PRIMARY_SOURCE_RECORD_FIELDS = {
    SourceType.SALES.value: "order_id",
    SourceType.ORDERS.value: "order_id",
    SourceType.PAYMENTS.value: "payment_id",
    SourceType.SETTLEMENTS.value: "settlement_id",
    SourceType.REFUNDS.value: "refund_id",
    SourceType.INVOICES.value: "invoice_id",
    SourceType.INVENTORY_MOVEMENTS.value: "movement_id",
    SourceType.EMPLOYEE_ACTIONS.value: "action_id",
}


def _canonical_field(source_type: str, field: str) -> str:
    if field == "amount" and source_type == "INVOICES":
        return "gross_minor"
    return _MONEY_FIELDS.get(field, field)


def _minor_units(value: str, field: str) -> int:
    try:
        amount = Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if not amount.is_finite():
            raise InvalidOperation
        return int(amount * 100)
    except (InvalidOperation, ValueError) as error:
        raise ValueError(f"malformed monetary value for {field}") from error


def _primary_source_record_id(source_type: str, values: dict[str, str | int | None]) -> str | None:
    primary_field = _PRIMARY_SOURCE_RECORD_FIELDS.get(source_type)
    if primary_field is None:
        return None
    value = values.get(primary_field)
    return str(value) if value not in (None, "") else None


class NormalizationService:
    def __init__(self, repository: WorkflowRepository) -> None:
        self._repository = repository

    def normalize(
        self, context: ActorContext, investigation_id: str, idempotency_key: str
    ) -> DatasetVersionResponse:
        settings = get_settings()
        if not idempotency_key or len(idempotency_key) > 128:
            raise ValueError("Idempotency-Key must be between 1 and 128 characters")
        request_hash = sha256(
            json.dumps({"investigation_id": investigation_id}, sort_keys=True).encode()
        ).hexdigest()
        previous = self._repository.get_idempotency(context.organization_id, idempotency_key)
        if previous is not None:
            if previous.get("request_hash") != request_hash:
                raise NormalizationConflict(
                    "Idempotency-Key was already used for another normalization request"
                )
            if int(previous.get("response_status", 425)) == 425:
                raise NormalizationConflict(
                    "An identical normalization request is already in progress"
                )
            return DatasetVersionResponse.model_validate(previous["response_body"])
        sources = self._repository.list_source_files(context.organization_id, investigation_id)
        if not sources:
            raise NormalizationBlocked(["At least one source file is required"])
        reasons: list[str] = []
        relationships = self._repository.list_relationship_proposals(
            context.organization_id, investigation_id
        )
        unresolved_relationships = [
            item["id"] for item in relationships if item.get("status") == "PROPOSED"
        ]
        if unresolved_relationships:
            reasons.append(
                "Relationship proposals require an explicit decision: "
                + ", ".join(map(str, unresolved_relationships))
            )
        prepared: list[tuple[dict[str, object], dict[str, object], list[dict[str, object]]]] = []
        for source in sources:
            source_id = str(source["id"])
            internal_source = self._repository.get_source_file_internal(
                context.organization_id, investigation_id, source_id
            )
            if internal_source is None:
                reasons.append(f"{source_id} is not available in this investigation")
                continue
            analysis = self._repository.get_source_analysis(
                context.organization_id, investigation_id, source_id
            )
            mappings = self._repository.list_source_mappings(
                context.organization_id, investigation_id, source_id
            )
            if not analysis or any(item.get("status") != "CONFIRMED" for item in mappings):
                reasons.append(f"{source_id} mappings are not confirmed")
                continue
            if str(analysis.get("source_type")) == SourceType.UNKNOWN.value:
                reasons.append(f"{source_id} has no supported source classification")
                continue
            filename, content = read_upload(str(internal_source["storage_reference"]))
            document = analyze_content(
                filename,
                content,
                max_rows=settings.max_upload_rows,
                max_columns=settings.max_upload_columns,
            )
            mapping_by_column = {
                str(item["source_column"]): item
                for item in mappings
                if not item.get("ignored") and item.get("canonical_field")
            }
            source_type = str(analysis["source_type"])
            rows: list[dict[str, object]] = []
            seen_source_ids: set[str] = set()
            for row_index, raw_row in enumerate(document.rows, start=2):
                row = dict(
                    zip(
                        document.headers,
                        [None if value is None else str(value) for value in raw_row],
                        strict=True,
                    )
                )
                values: dict[str, str | int | None] = {}
                lineage: dict[str, dict[str, str | int | None]] = {}
                for column, value in row.items():
                    mapping = mapping_by_column.get(column)
                    if mapping:
                        mapped_field = str(mapping["canonical_field"])
                        field = _canonical_field(source_type, mapped_field)
                        try:
                            normalized_value: str | int | None = (
                                _minor_units(value, mapped_field)
                                if mapped_field in _MONEY_FIELDS and value
                                else (
                                    value.strip().upper()
                                    if mapped_field in {"status", "currency"} and value
                                    else (
                                        value.strip() if field.endswith("_id") and value else value
                                    )
                                )
                            )
                        except ValueError:
                            reasons.append(
                                f"{source_id} row {row_index} has malformed monetary value for {mapped_field}"
                            )
                            normalized_value = value
                        values[field] = normalized_value
                        lineage[field] = {
                            "source_file_id": source_id,
                            "source_row_number": row_index,
                            "source_column": column,
                            "source_record_id": value if field.endswith("_id") else None,
                        }
                source_record_id = _primary_source_record_id(source_type, values)
                if source_record_id is not None:
                    if source_record_id in seen_source_ids:
                        reasons.append(
                            f"{source_id} contains duplicate source record ID {source_record_id}"
                        )
                    seen_source_ids.add(source_record_id)
                for field, field_value in values.items():
                    if field_value in (None, ""):
                        continue
                    if field.endswith(("_at", "_date")) and isinstance(field_value, str):
                        try:
                            parsed = datetime.fromisoformat(field_value)
                            if field.endswith("_at") and (
                                parsed.tzinfo is None or parsed.utcoffset() is None
                            ):
                                reasons.append(
                                    f"{source_id} row {row_index} has a timezone-naive timestamp for {field}"
                                )
                        except ValueError:
                            reasons.append(
                                f"{source_id} row {row_index} has malformed timestamp/date for {field}"
                            )
                rows.append(
                    {
                        "id": f"NREC-{uuid4().hex[:12].upper()}",
                        "source_file_id": source_id,
                        "source_row_number": row_index,
                        "source_record_id": source_record_id,
                        "source_type": str(analysis["source_type"]),
                        "values": values,
                        "lineage": lineage,
                    }
                )
            prepared.append((source, analysis, rows))
        if reasons:
            raise NormalizationBlocked(reasons)
        existing = self._repository.reserve_idempotency(
            context.organization_id, context.actor_id, idempotency_key, request_hash
        )
        if existing is not None:
            if existing.get("request_hash") != request_hash:
                raise NormalizationConflict(
                    "Idempotency-Key was already used for another normalization request"
                )
            if int(existing.get("response_status", 425)) == 425:
                raise NormalizationConflict(
                    "An identical normalization request is already in progress"
                )
            return DatasetVersionResponse.model_validate(existing["response_body"])
        version_no = self._repository.next_dataset_version(
            context.organization_id, investigation_id
        )
        version = {
            "id": f"DS-{uuid4().hex[:12].upper()}",
            "organization_id": context.organization_id,
            "financial_investigation_id": investigation_id,
            "version_no": version_no,
            "status": "READY",
            "record_count": sum(len(rows) for _, _, rows in prepared),
            "source_count": len(prepared),
            "created_at": datetime.now(UTC),
        }
        try:
            saved = self._repository.save_dataset_version(
                context.organization_id, version, [row for _, _, rows in prepared for row in rows]
            )
        except Exception:
            self._repository.release_idempotency(context.organization_id, idempotency_key)
            raise
        response = DatasetVersionResponse.model_validate(saved)
        self._repository.complete_idempotency(
            context.organization_id, idempotency_key, 200, response.model_dump(mode="json")
        )
        self._repository.record_audit_event(
            context.organization_id, "DATASET_VERSION_CREATED", str(saved["id"]), context.actor_id
        )
        self._repository.update_financial_investigation_status(
            context.organization_id, investigation_id, "PROCESSING"
        )
        return response

    def latest(self, organization_id: str, investigation_id: str) -> DatasetVersionResponse:
        result = self._repository.latest_dataset_version(organization_id, investigation_id)
        if result is None:
            raise DatasetVersionNotFound(investigation_id)
        return DatasetVersionResponse.model_validate(result)

    def records(
        self,
        organization_id: str,
        investigation_id: str,
        dataset_version_id: str,
        limit: int = 1000,
    ) -> list[NormalizedRecordResponse]:
        response_fields = set(NormalizedRecordResponse.model_fields)
        return [
            NormalizedRecordResponse.model_validate(
                {key: value for key, value in item.items() if key in response_fields}
            )
            for item in self._repository.list_normalized_records(
                organization_id, investigation_id, dataset_version_id, limit
            )
        ]
