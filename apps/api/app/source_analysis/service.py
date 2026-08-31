from __future__ import annotations

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
    SourceAnalysisProviderUnavailable,
    get_source_analysis_provider,
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
        self, context: ActorContext, investigation_id: str, source_file_id: str
    ) -> SourceAnalysisResponse:
        source = self._repository.get_source_file_internal(
            context.organization_id, investigation_id, source_file_id
        )
        if source is None:
            raise SourceAnalysisNotFound(source_file_id)
        settings = get_settings()
        self._repository.update_source_analysis_state(
            context.organization_id,
            investigation_id,
            source_file_id,
            "ANALYZING",
            "UNKNOWN",
            0,
        )
        try:
            filename, content = read_upload(str(source["storage_reference"]))
            document = analyze_content(
                filename,
                content,
                max_rows=min(settings.max_upload_rows, 2_000),
                max_columns=settings.max_upload_columns,
                truncate=True,
            )
            provider = get_source_analysis_provider(
                settings.ai_provider,
                settings.configured_ai_api_keys,
                settings.ai_base_url,
                settings.ai_model,
                settings.ai_timeout_seconds,
                settings.ai_fallback_provider,
                settings.configured_ai_fallback_api_keys,
                settings.ai_fallback_base_url,
                settings.ai_fallback_model,
            )
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
        return MappingResponse.model_validate(updated)

    def confirm_mappings(
        self, context: ActorContext, investigation_id: str, source_file_id: str
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
        return MappingConfirmationResponse(
            financial_investigation_id=investigation_id,
            source_file_id=source_file_id,
            status=MappingStatus.CONFIRMED,
            confirmed_mapping_count=int(result["confirmed_mapping_count"]),
            ignored_column_count=int(result["ignored_column_count"]),
        )

    def update_classification(
        self,
        context: ActorContext,
        investigation_id: str,
        source_file_id: str,
        payload: SourceTypeUpdate,
    ) -> SourceAnalysisResponse:
        analysis = self.get_analysis(context.organization_id, investigation_id, source_file_id)
        if payload.source_type == SourceType.UNKNOWN:
            raise MappingConflict("A confirmed source must use a supported source type")
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
        return SourceAnalysisResponse.model_validate(saved)

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
