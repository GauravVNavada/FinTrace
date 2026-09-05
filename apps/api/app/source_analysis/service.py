from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from app.controls.schemas import ActorContext
from app.core.config import get_settings
from app.financial_investigations.files import read_upload
from app.financial_investigations.schemas import SourceType
from app.repositories.contracts import WorkflowRepository
from app.source_analysis.analyzer import analyze_content
from app.source_analysis.provider import (
    CANONICAL_ALIASES,
    REQUIRED_FIELDS,
    OfflineSourceAnalysisProvider,
    SourceAnalysisProviderUnavailable,
)
from app.source_analysis.schemas import (
    MappingConfirmationResponse,
    MappingEdit,
    MappingResponse,
    MappingStatus,
    SourceAnalysisResponse,
    SourceTypeUpdate,
)


class SourceAnalysisNotFound(LookupError):
    pass


class MappingConfirmationRequired(ValueError):
    def __init__(self, missing_fields: list[str]) -> None:
        self.missing_fields = missing_fields
        super().__init__(f"Required mappings need review: {', '.join(missing_fields)}")


class MappingConflict(ValueError):
    pass


class SourceAnalysisService:
    def __init__(self, repository: WorkflowRepository) -> None:
        self._repository = repository

    def analyze(
        self,
        context: ActorContext,
        investigation_id: str,
        source_file_id: str,
        idempotency_key: str,
        provider_name: str | None = None,
    ) -> SourceAnalysisResponse:
        if not idempotency_key or len(idempotency_key) > 128:
            raise ValueError("Idempotency-Key must be between 1 and 128 characters")
        source = self._repository.get_source_file_internal(
            context.organization_id, investigation_id, source_file_id
        )
        if source is None:
            raise SourceAnalysisNotFound(source_file_id)
        request_hash = self._request_hash(investigation_id, source_file_id)
        previous = self._repository.get_idempotency(context.organization_id, idempotency_key)
        if previous is not None:
            self._validate_idempotency(previous, request_hash)
            if int(previous.get("response_status", 425)) == 425:
                raise MappingConflict("An identical source analysis is already in progress")
            return SourceAnalysisResponse.model_validate(previous["response_body"])
        reserved = self._repository.reserve_idempotency(
            context.organization_id, context.actor_id, idempotency_key, request_hash
        )
        if reserved is not None:
            self._validate_idempotency(reserved, request_hash)
            if int(reserved.get("response_status", 425)) == 425:
                raise MappingConflict("An identical source analysis is already in progress")
            return SourceAnalysisResponse.model_validate(reserved["response_body"])
        if source.get("status") == "READY":
            existing_analysis = self._repository.get_source_analysis(
                context.organization_id, investigation_id, source_file_id
            )
            if existing_analysis is not None:
                result = SourceAnalysisResponse.model_validate(existing_analysis)
                self._repository.complete_idempotency(
                    context.organization_id, idempotency_key, 200, result.model_dump(mode="json")
                )
                return result
        settings = get_settings()
        try:
            self._repository.update_source_analysis_state(
                context.organization_id,
                investigation_id,
                source_file_id,
                "ANALYZING",
                "UNKNOWN",
                0,
            )
            filename, content = read_upload(str(source["storage_reference"]))
            document = analyze_content(
                filename,
                content,
                max_rows=min(settings.max_upload_rows, 2_000),
                max_columns=settings.max_upload_columns,
                truncate=True,
            )
            # Source classification and canonical mapping are deterministic data
            # preparation, not an AI investigation. Keeping this path offline
            # prevents a provider-specific structured-output failure from
            # blocking otherwise valid CSV/XLSX uploads. The configured live
            # provider remains available to the exception investigation service.
            provider = OfflineSourceAnalysisProvider()
            classification = provider.classify(str(source["original_filename"]), document)
            mappings = provider.propose_mappings(classification.source_type, document)
            mapping_records = self._mapping_records(
                context.organization_id,
                investigation_id,
                source_file_id,
                classification.source_type,
                document,
                mappings,
            )
            now = datetime.now(UTC)
            response_data = {
                "id": f"ANL-{uuid4().hex[:12].upper()}",
                "organization_id": context.organization_id,
                "financial_investigation_id": investigation_id,
                "source_file_id": source_file_id,
                "headers": document.headers,
                "sample_rows": document.sample_rows,
                "columns": [profile.model_dump(mode="json") for profile in document.profiles],
                "source_type": classification.source_type,
                "classification_confidence": classification.confidence,
                "reasoning_summary": classification.reasoning_summary,
                "provider_status": classification.provider_status,
                "provider": getattr(provider, "provider", classification.provider),
                "model": getattr(provider, "model", classification.model),
                "analyzed_at": now,
            }
            analysis = SourceAnalysisResponse.model_validate(
                self._repository.save_source_analysis(
                    context.organization_id,
                    investigation_id,
                    source_file_id,
                    response_data,
                )
            )
            self._repository.save_source_mappings(
                context.organization_id,
                investigation_id,
                source_file_id,
                mapping_records,
            )
            self._repository.update_source_analysis_state(
                context.organization_id,
                investigation_id,
                source_file_id,
                "MAPPING_REQUIRED",
                classification.source_type.value,
                classification.confidence,
            )
            self._repository.record_audit_event(
                context.organization_id,
                "SOURCE_ANALYZED",
                source_file_id,
                context.actor_id,
            )
            self._repository.complete_idempotency(
                context.organization_id,
                idempotency_key,
                200,
                analysis.model_dump(mode="json"),
            )
            return analysis
        except SourceAnalysisProviderUnavailable:
            self._repository.update_source_analysis_state(
                context.organization_id,
                investigation_id,
                source_file_id,
                "FAILED",
                "UNKNOWN",
                0,
            )
            self._repository.record_audit_event(
                context.organization_id,
                "SOURCE_ANALYSIS_FAILED",
                source_file_id,
                context.actor_id,
            )
            self._repository.release_idempotency(context.organization_id, idempotency_key)
            raise
        except Exception:
            self._repository.update_source_analysis_state(
                context.organization_id,
                investigation_id,
                source_file_id,
                "FAILED",
                "UNKNOWN",
                0,
            )
            self._repository.release_idempotency(context.organization_id, idempotency_key)
            raise

    def get_analysis(
        self, organization_id: str, investigation_id: str, source_file_id: str
    ) -> SourceAnalysisResponse:
        result = self._repository.get_source_analysis(
            organization_id, investigation_id, source_file_id
        )
        if result is None:
            raise SourceAnalysisNotFound(source_file_id)
        return SourceAnalysisResponse.model_validate(result)

    def list_mappings(
        self, organization_id: str, investigation_id: str, source_file_id: str
    ) -> list[MappingResponse]:
        self.get_analysis(organization_id, investigation_id, source_file_id)
        return [
            MappingResponse.model_validate(item)
            for item in self._repository.list_source_mappings(
                organization_id, investigation_id, source_file_id
            )
        ]

    def update_mapping(
        self,
        context: ActorContext,
        investigation_id: str,
        source_file_id: str,
        mapping_id: str,
        payload: MappingEdit,
        idempotency_key: str,
    ) -> MappingResponse:
        analysis = self.get_analysis(context.organization_id, investigation_id, source_file_id)
        mapping = next(
            (
                item
                for item in self._repository.list_source_mappings(
                    context.organization_id, investigation_id, source_file_id
                )
                if str(item["id"]) == mapping_id
            ),
            None,
        )
        if mapping is None:
            raise SourceAnalysisNotFound(mapping_id)
        if mapping.get("status") == MappingStatus.CONFIRMED:
            raise MappingConflict(
                "Confirmed mappings cannot be edited; re-analyze the source to create a new proposal"
            )
        if payload.canonical_field is not None:
            allowed_fields = set(CANONICAL_ALIASES.get(analysis.source_type, {}).values())
            if payload.canonical_field not in allowed_fields:
                raise MappingConflict(
                    "The selected canonical field is not valid for this source type"
                )
        request_hash = self._request_hash(
            investigation_id,
            source_file_id,
            mapping_id,
            payload.model_dump(mode="json"),
        )
        replay = self._reserve_or_replay(context, idempotency_key, request_hash)
        if replay is not None:
            return MappingResponse.model_validate(replay)
        try:
            updated = self._repository.update_source_mapping(
                context.organization_id,
                investigation_id,
                source_file_id,
                mapping_id,
                {
                    "canonical_field": payload.canonical_field,
                    "ignored": payload.ignored,
                    "updated_at": datetime.now(UTC),
                },
            )
            if updated is None:
                raise SourceAnalysisNotFound(mapping_id)
            self._repository.record_audit_event(
                context.organization_id, "SOURCE_MAPPING_EDITED", mapping_id, context.actor_id
            )
            response = MappingResponse.model_validate(updated)
            self._repository.complete_idempotency(
                context.organization_id, idempotency_key, 200, response.model_dump(mode="json")
            )
            return response
        except Exception:
            self._repository.release_idempotency(context.organization_id, idempotency_key)
            raise

    def confirm_mappings(
        self, context: ActorContext, investigation_id: str, source_file_id: str, idempotency_key: str
    ) -> MappingConfirmationResponse:
        analysis = self.get_analysis(context.organization_id, investigation_id, source_file_id)
        if analysis.source_type == SourceType.UNKNOWN:
            raise MappingConfirmationRequired(["source_type"])
        mappings = self._repository.list_source_mappings(
            context.organization_id, investigation_id, source_file_id
        )
        mapped_fields = {
            str(item["canonical_field"])
            for item in mappings
            if item.get("canonical_field") and not item.get("ignored")
        }
        missing = sorted(REQUIRED_FIELDS[analysis.source_type] - mapped_fields)
        if missing:
            raise MappingConfirmationRequired(missing)
        request_hash = self._request_hash(investigation_id, source_file_id, "confirm")
        replay = self._reserve_or_replay(context, idempotency_key, request_hash)
        if replay is not None:
            return MappingConfirmationResponse.model_validate(replay)
        try:
            result = self._repository.confirm_source_mappings(
                context.organization_id, investigation_id, source_file_id
            )
            if result is None or not result.get("valid"):
                raise MappingConfirmationRequired(
                    [str(item) for item in (result or {}).get("missing_fields", [])]
                )
            sources = self._repository.list_source_files(context.organization_id, investigation_id)
            if sources and all(item.get("status") == "READY" for item in sources):
                self._repository.update_financial_investigation_status(
                    context.organization_id, investigation_id, "RELATIONSHIP_REVIEW"
                )
            self._repository.record_audit_event(
                context.organization_id, "SOURCE_MAPPINGS_CONFIRMED", source_file_id, context.actor_id
            )
            response = MappingConfirmationResponse(
                financial_investigation_id=investigation_id,
                source_file_id=source_file_id,
                status=MappingStatus.CONFIRMED,
                confirmed_mapping_count=int(result["confirmed_mapping_count"]),
                ignored_column_count=int(result["ignored_column_count"]),
            )
            self._repository.complete_idempotency(
                context.organization_id, idempotency_key, 200, response.model_dump(mode="json")
            )
            return response
        except Exception:
            self._repository.release_idempotency(context.organization_id, idempotency_key)
            raise

    def update_classification(
        self,
        context: ActorContext,
        investigation_id: str,
        source_file_id: str,
        payload: SourceTypeUpdate,
        idempotency_key: str,
    ) -> SourceAnalysisResponse:
        analysis = self.get_analysis(context.organization_id, investigation_id, source_file_id)
        if payload.source_type == SourceType.UNKNOWN:
            raise MappingConflict("A confirmed source must use a supported source type")
        request_hash = self._request_hash(
            investigation_id, source_file_id, "classification", payload.model_dump(mode="json")
        )
        replay = self._reserve_or_replay(context, idempotency_key, request_hash)
        if replay is not None:
            return SourceAnalysisResponse.model_validate(replay)
        try:
            self._repository.update_source_analysis_state(
                context.organization_id,
                investigation_id,
                source_file_id,
                "MAPPING_REQUIRED",
                payload.source_type.value,
                analysis.classification_confidence,
            )
            updated = {
                **analysis.model_dump(mode="python"),
                "source_type": payload.source_type,
            }
            saved = self._repository.save_source_analysis(
                context.organization_id,
                investigation_id,
                source_file_id,
                updated,
            )
            self._repository.record_audit_event(
                context.organization_id,
                "SOURCE_CLASSIFICATION_UPDATED",
                source_file_id,
                context.actor_id,
            )
            response = SourceAnalysisResponse.model_validate(saved)
            self._repository.complete_idempotency(
                context.organization_id, idempotency_key, 200, response.model_dump(mode="json")
            )
            return response
        except Exception:
            self._repository.release_idempotency(context.organization_id, idempotency_key)
            raise

    def _reserve_or_replay(
        self, context: ActorContext, idempotency_key: str, request_hash: str
    ) -> dict[str, Any] | None:
        if not idempotency_key or len(idempotency_key) > 128:
            raise ValueError("Idempotency-Key must be between 1 and 128 characters")
        previous = self._repository.get_idempotency(context.organization_id, idempotency_key)
        if previous is not None:
            self._validate_idempotency(previous, request_hash)
            if int(previous.get("response_status", 425)) == 425:
                raise MappingConflict("An identical source operation is already in progress")
            return dict(previous["response_body"])
        reserved = self._repository.reserve_idempotency(
            context.organization_id, context.actor_id, idempotency_key, request_hash
        )
        if reserved is not None:
            self._validate_idempotency(reserved, request_hash)
            if int(reserved.get("response_status", 425)) == 425:
                raise MappingConflict("An identical source operation is already in progress")
            return dict(reserved["response_body"])
        return None

    @staticmethod
    def _validate_idempotency(record: dict[str, Any], request_hash: str) -> None:
        if record.get("request_hash") != request_hash:
            raise MappingConflict("Idempotency-Key was already used for another source operation")

    @staticmethod
    def _request_hash(*parts: object) -> str:
        return hashlib.sha256(
            json.dumps(parts, sort_keys=True, separators=(",", ":"), default=str).encode()
        ).hexdigest()

    @staticmethod
    def _mapping_records(
        organization_id: str,
        investigation_id: str,
        source_file_id: str,
        source_type: SourceType,
        document: Any,
        proposals: list[Any],
    ) -> list[dict[str, object]]:
        profiles = {profile.name: profile for profile in document.profiles}
        allowed_fields = set(CANONICAL_ALIASES.get(source_type, {}).values())
        required_fields = REQUIRED_FIELDS.get(source_type, frozenset())
        now = datetime.now(UTC)
        records: list[dict[str, object]] = []
        for proposal in proposals:
            if proposal.source_column not in profiles:
                raise SourceAnalysisProviderUnavailable(
                    "AI mapping returned a column that is not present in the source"
                )
            if not 0 <= float(proposal.confidence) <= 1:
                raise SourceAnalysisProviderUnavailable(
                    "AI mapping returned an invalid confidence"
                )
            canonical = (
                proposal.canonical_field if proposal.canonical_field in allowed_fields else None
            )
            records.append(
                {
                    "id": f"MAP-{uuid4().hex[:12].upper()}",
                    "organization_id": organization_id,
                    "financial_investigation_id": investigation_id,
                    "source_file_id": source_file_id,
                    "source_column": proposal.source_column,
                    "canonical_field": canonical,
                    "confidence": max(0.0, min(float(proposal.confidence), 1.0)),
                    "required": canonical in required_fields,
                    "inferred_type": profiles[proposal.source_column].inferred_type,
                    "ignored": bool(proposal.ignored or canonical is None),
                    "status": MappingStatus.PROPOSED,
                    "updated_at": now,
                }
            )
        return records
