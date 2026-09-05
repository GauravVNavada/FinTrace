from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from app.controls.schemas import ActorContext
from app.financial_investigations.files import read_upload, remove_upload
from app.financial_investigations.schemas import (
    FinancialInvestigationCreate,
    FinancialInvestigationResponse,
    SourceFileResponse,
)
from app.repositories.contracts import WorkflowRepository


class FinancialInvestigationNotFound(LookupError):
    pass


class SourceFileNotFound(LookupError):
    pass


class FinancialInvestigationConflict(ValueError):
    pass


class FinancialInvestigationService:
    def __init__(self, repository: WorkflowRepository) -> None:
        self._repository = repository

    def create(
        self, context: ActorContext, payload: FinancialInvestigationCreate, idempotency_key: str
    ) -> FinancialInvestigationResponse:
        body = payload.model_dump(mode="json")
        request_hash = _request_hash(body)
        replay = self._replay(context, idempotency_key, request_hash)
        if replay is not None:
            return FinancialInvestigationResponse.model_validate(replay)
        existing = self._repository.reserve_idempotency(
            context.organization_id, context.actor_id, idempotency_key, request_hash
        )
        if existing is not None:
            return self._resolve_reserved(existing, request_hash)
        now = datetime.now(UTC)
        try:
            response = self._repository.create_financial_investigation(
                context.organization_id,
                {
                    "id": f"FIN-{uuid4().hex[:12].upper()}",
                    **body,
                    "status": "DRAFT",
                    "created_by": context.actor_id,
                    "created_at": now,
                    "updated_at": now,
                },
            )
        except Exception:
            self._repository.release_idempotency(context.organization_id, idempotency_key)
            raise
        if not response:
            self._repository.release_idempotency(context.organization_id, idempotency_key)
            raise ValueError("Unable to create financial investigation")
        result = FinancialInvestigationResponse.model_validate(response)
        self._repository.complete_idempotency(
            context.organization_id, idempotency_key, 200, result.model_dump(mode="json")
        )
        self._repository.record_audit_event(
            context.organization_id, "FINANCIAL_INVESTIGATION_CREATED", result.id, context.actor_id
        )
        return result

    def list_all(
        self, organization_id: str, limit: int = 100
    ) -> list[FinancialInvestigationResponse]:
        return [
            FinancialInvestigationResponse.model_validate(item)
            for item in self._repository.list_financial_investigations(organization_id, limit)
        ]

    def get(self, organization_id: str, investigation_id: str) -> FinancialInvestigationResponse:
        result = self._repository.get_financial_investigation(organization_id, investigation_id)
        if result is None:
            raise FinancialInvestigationNotFound(investigation_id)
        return FinancialInvestigationResponse.model_validate(result)

    def list_sources(
        self, organization_id: str, investigation_id: str, limit: int = 100
    ) -> list[SourceFileResponse]:
        self.get(organization_id, investigation_id)
        return [
            SourceFileResponse.model_validate(item)
            for item in self._repository.list_source_files(organization_id, investigation_id, limit)
        ]

    def replay_source_if_present(
        self, context: ActorContext, investigation_id: str, sha256: str, idempotency_key: str
    ) -> SourceFileResponse | None:
        self.get(context.organization_id, investigation_id)
        replay = self._replay(
            context,
            idempotency_key,
            _request_hash({"investigation_id": investigation_id, "sha256": sha256}),
        )
        return SourceFileResponse.model_validate(replay) if replay is not None else None

    def add_source(
        self,
        context: ActorContext,
        investigation_id: str,
        data: dict[str, Any],
        idempotency_key: str,
    ) -> SourceFileResponse:
        self.get(context.organization_id, investigation_id)
        request_hash = _request_hash(
            {"investigation_id": investigation_id, "sha256": data["sha256"]}
        )
        replay = self._replay(context, idempotency_key, request_hash)
        if replay is not None:
            return SourceFileResponse.model_validate(replay)
        reserved = self._repository.reserve_idempotency(
            context.organization_id, context.actor_id, idempotency_key, request_hash
        )
        if reserved is not None:
            if reserved.get("request_hash") != request_hash:
                raise FinancialInvestigationConflict(
                    "Idempotency-Key was already used for another request"
                )
            if int(reserved.get("response_status", 425)) == 425:
                raise FinancialInvestigationConflict(
                    "An identical source upload is already in progress"
                )
            return SourceFileResponse.model_validate(reserved["response_body"])
        same_name_sources = self._find_sources_by_filename(
            context.organization_id, investigation_id, str(data["original_filename"])
        )
        successful = next(
            (source for source in same_name_sources if source.status.value == "READY"),
            None,
        )
        if successful is not None:
            self._remove_unready_sources(
                context, investigation_id, same_name_sources, keep_id=successful.id
            )
            result = successful.model_copy(update={"deduplicated": True})
            self._repository.complete_idempotency(
                context.organization_id, idempotency_key, 200, result.model_dump(mode="json")
            )
            self._repository.record_audit_event(
                context.organization_id,
                "SOURCE_FILE_UPLOAD_DEDUPLICATED",
                result.id,
                context.actor_id,
            )
            return result
        existing = self._find_existing_source(
            context.organization_id, investigation_id, str(data["sha256"])
        )
        if existing is not None and existing.status.value == "READY":
            self._remove_unready_sources(
                context, investigation_id, same_name_sources, keep_id=existing.id
            )
            result = existing.model_copy(update={"deduplicated": True})
            self._repository.complete_idempotency(
                context.organization_id, idempotency_key, 200, result.model_dump(mode="json")
            )
            self._repository.record_audit_event(
                context.organization_id,
                "SOURCE_FILE_UPLOAD_DEDUPLICATED",
                result.id,
                context.actor_id,
            )
            return result
        replaceable = list(same_name_sources)
        if existing is not None and existing.id not in {source.id for source in replaceable}:
            replaceable.append(existing)
        self._remove_unready_sources(context, investigation_id, replaceable)
        try:
            response = self._repository.add_source_file(
                context.organization_id, investigation_id, data
            )
        except Exception:
            self._repository.release_idempotency(context.organization_id, idempotency_key)
            raise
        if not response:
            self._repository.release_idempotency(context.organization_id, idempotency_key)
            raise FinancialInvestigationNotFound(investigation_id)
        result = SourceFileResponse.model_validate(response)
        is_deduplicated = result.id != str(data["id"])
        result = result.model_copy(update={"deduplicated": is_deduplicated})
        self._repository.complete_idempotency(
            context.organization_id, idempotency_key, 200, result.model_dump(mode="json")
        )
        self._repository.record_audit_event(
            context.organization_id,
            "SOURCE_FILE_UPLOAD_DEDUPLICATED" if is_deduplicated else "SOURCE_FILE_UPLOADED",
            result.id,
            context.actor_id,
        )
        return result

    def _find_sources_by_filename(
        self, organization_id: str, investigation_id: str, filename: str
    ) -> list[SourceFileResponse]:
        normalized = _normalize_filename(filename)
        return [
            SourceFileResponse.model_validate(source)
            for source in self._repository.list_source_files(
                organization_id, investigation_id, limit=1000
            )
            if _normalize_filename(str(source["original_filename"])) == normalized
        ]

    def _remove_unready_sources(
        self,
        context: ActorContext,
        investigation_id: str,
        sources: list[SourceFileResponse],
        keep_id: str | None = None,
    ) -> None:
        for source in sources:
            if source.id == keep_id or source.status.value == "READY":
                continue
            deleted = self._repository.delete_source_file(
                context.organization_id, investigation_id, source.id
            )
            if deleted is None:
                continue
            try:
                remove_upload(str(deleted["storage_reference"]))
            except OSError:
                pass
            self._repository.record_audit_event(
                context.organization_id,
                "SOURCE_FILE_REPLACED",
                source.id,
                context.actor_id,
            )

    def _find_existing_source(
        self, organization_id: str, investigation_id: str, content_sha256: str
    ) -> SourceFileResponse | None:
        """Find identical bytes already attached to this investigation.

        The persisted hash is the fast path. Older source rows predate the hash
        column, so their server-side files are checked once as a compatibility
        fallback; browser filenames are intentionally not used as identity.
        """
        for source in self._repository.list_source_files(organization_id, investigation_id):
            internal = self._repository.get_source_file_internal(
                organization_id, investigation_id, str(source["id"])
            )
            if internal is None:
                continue
            stored_hash = internal.get("content_sha256") or internal.get("sha256")
            if stored_hash == content_sha256:
                return SourceFileResponse.model_validate(source)
            if stored_hash or not internal.get("storage_reference"):
                continue
            try:
                _, content = read_upload(str(internal["storage_reference"]))
            except (OSError, ValueError):
                continue
            if hashlib.sha256(content).hexdigest() == content_sha256:
                return SourceFileResponse.model_validate(source)
        return None

    def delete_source(
        self, context: ActorContext, investigation_id: str, source_file_id: str, idempotency_key: str
    ) -> str:
        self.get(context.organization_id, investigation_id)
        request_hash = _request_hash(
            {"operation": "delete_source", "investigation_id": investigation_id, "source_file_id": source_file_id}
        )
        replay = self._replay(context, idempotency_key, request_hash)
        if replay is not None:
            return str(replay["storage_reference"])
        reserved = self._repository.reserve_idempotency(
            context.organization_id, context.actor_id, idempotency_key, request_hash
        )
        if reserved is not None:
            if reserved.get("request_hash") != request_hash:
                raise FinancialInvestigationConflict(
                    "Idempotency-Key was already used for another request"
                )
            if int(reserved.get("response_status", 425)) == 425:
                raise FinancialInvestigationConflict("An identical source deletion is already in progress")
            body = reserved.get("response_body")
            if not isinstance(body, dict) or "storage_reference" not in body:
                raise FinancialInvestigationConflict("The previous source deletion response is invalid")
            return str(body["storage_reference"])
        try:
            result = self._repository.delete_source_file(
                context.organization_id, investigation_id, source_file_id
            )
            if result is None:
                raise SourceFileNotFound(source_file_id)
            self._repository.record_audit_event(
                context.organization_id, "SOURCE_FILE_DELETED", source_file_id, context.actor_id
            )
            body = {"storage_reference": str(result["storage_reference"])}
            self._repository.complete_idempotency(
                context.organization_id, idempotency_key, 200, body
            )
            return body["storage_reference"]
        except Exception:
            self._repository.release_idempotency(context.organization_id, idempotency_key)
            raise

    def _replay(self, context: ActorContext, key: str, request_hash: str) -> dict[str, Any] | None:
        if not key or len(key) > 128:
            raise ValueError("Idempotency-Key must be between 1 and 128 characters")
        record = self._repository.get_idempotency(context.organization_id, key)
        if record is None:
            return None
        if record.get("request_hash") != request_hash:
            raise FinancialInvestigationConflict(
                "Idempotency-Key was already used for another request"
            )
        if int(record.get("response_status", 425)) == 425:
            raise FinancialInvestigationConflict("An identical request is already in progress")
        response = record.get("response_body")
        return dict(response) if isinstance(response, dict) else None

    @staticmethod
    def _resolve_reserved(
        record: dict[str, Any], request_hash: str
    ) -> FinancialInvestigationResponse:
        if record.get("request_hash") != request_hash:
            raise FinancialInvestigationConflict(
                "Idempotency-Key was already used for another request"
            )
        if int(record.get("response_status", 425)) == 425:
            raise FinancialInvestigationConflict("An identical request is already in progress")
        return FinancialInvestigationResponse.model_validate(record["response_body"])


def _request_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _normalize_filename(filename: str) -> str:
    return filename.strip().casefold()
