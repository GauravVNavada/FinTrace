from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, cast
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Header, HTTPException, Query, UploadFile, status
from fastapi.responses import JSONResponse, Response

from app.api.deps import get_actor_context
from app.controls.schemas import ActorContext, Capability
from app.core.config import get_settings
from app.financial_exception_investigations.service import (
    FinancialExceptionConflict,
    FinancialExceptionInvestigationService,
    FinancialExceptionNotFound,
)
from app.financial_investigation_patterns.schemas import FinancialInvestigationPatternResponse
from app.financial_investigation_patterns.service import FinancialInvestigationPatternService
from app.financial_investigations.demo_service import DemoDataService
from app.financial_investigations.files import (
    UploadValidationError,
    inspect_upload,
    remove_upload,
    store_upload,
)
from app.financial_investigations.schemas import (
    DemoDataRequest,
    DemoDataResponse,
    FinancialInvestigationCreate,
    FinancialInvestigationResponse,
    SourceFileResponse,
)
from app.financial_investigations.service import (
    FinancialInvestigationConflict,
    FinancialInvestigationNotFound,
    FinancialInvestigationService,
    SourceFileNotFound,
)
from app.investigations.provider import get_configured_ai_client
from app.investigations.schemas import InvestigationResponse
from app.normalization.schemas import DatasetVersionResponse, NormalizedRecordResponse
from app.normalization.service import (
    DatasetVersionNotFound,
    NormalizationBlocked,
    NormalizationConflict,
    NormalizationService,
)
from app.reconciliation.schemas import (
    ReconciliationResultResponse,
    ReconciliationRunRequest,
    ReconciliationRunResponse,
)
from app.reconciliation.service import (
    ReconciliationBlocked,
    ReconciliationConflict,
    ReconciliationNotFound,
    ReconciliationService,
)
from app.relationship_discovery.schemas import RelationshipDecision, RelationshipResponse
from app.relationship_discovery.service import (
    RelationshipConflict,
    RelationshipDiscoveryService,
    RelationshipNotFound,
)
from app.repositories.contracts import WorkflowRepository
from app.repositories.factory import get_repository
from app.source_analysis.provider import SourceAnalysisProviderUnavailable
from app.source_analysis.schemas import (
    MappingConfirmationResponse,
    MappingEdit,
    MappingResponse,
    SourceAnalysisResponse,
    SourceTypeUpdate,
)
from app.source_analysis.service import (
    MappingConfirmationRequired,
    MappingConflict,
    SourceAnalysisNotFound,
    SourceAnalysisService,
)

router = APIRouter()
service = FinancialInvestigationService(cast(WorkflowRepository, get_repository()))
analysis_service = SourceAnalysisService(cast(WorkflowRepository, get_repository()))
relationship_service = RelationshipDiscoveryService(cast(WorkflowRepository, get_repository()))
normalization_service = NormalizationService(cast(WorkflowRepository, get_repository()))
reconciliation_service = ReconciliationService(cast(WorkflowRepository, get_repository()))
_settings = get_settings()
financial_exception_service = FinancialExceptionInvestigationService(
    cast(WorkflowRepository, get_repository()),
    get_configured_ai_client(_settings),
)
pattern_service = FinancialInvestigationPatternService(cast(WorkflowRepository, get_repository()))
demo_data_service = DemoDataService(cast(WorkflowRepository, get_repository()))


@router.post("", response_model=FinancialInvestigationResponse, status_code=status.HTTP_201_CREATED)
def create_investigation(
    payload: FinancialInvestigationCreate,
    context: Annotated[ActorContext, Depends(get_actor_context)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> FinancialInvestigationResponse:
    _require(context, Capability.FINANCIAL_INVESTIGATION_WRITE)
    if idempotency_key is None:
        raise HTTPException(
            status_code=422,
            detail={"code": "INVALID_REQUEST", "message": "Idempotency-Key is required"},
        )
    try:
        return service.create(context, payload, idempotency_key)
    except FinancialInvestigationConflict as error:
        raise HTTPException(
            status_code=409, detail={"code": "IDEMPOTENCY_CONFLICT", "message": str(error)}
        ) from error
    except ValueError as error:
        raise HTTPException(
            status_code=422, detail={"code": "INVALID_REQUEST", "message": str(error)}
        ) from error


@router.get("", response_model=list[FinancialInvestigationResponse])
def list_investigations(
    context: Annotated[ActorContext, Depends(get_actor_context)],
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
) -> list[FinancialInvestigationResponse]:
    _require(context, Capability.FINANCIAL_INVESTIGATION_READ)
    return service.list_all(context.organization_id, limit)


@router.get("/{investigation_id}", response_model=FinancialInvestigationResponse)
def get_investigation(
    investigation_id: str, context: Annotated[ActorContext, Depends(get_actor_context)]
) -> FinancialInvestigationResponse:
    _require(context, Capability.FINANCIAL_INVESTIGATION_READ)
    try:
        return service.get(context.organization_id, investigation_id)
    except FinancialInvestigationNotFound as error:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "RESOURCE_NOT_FOUND",
                "message": "Financial investigation does not exist",
            },
        ) from error


@router.post(
    "/{investigation_id}/sources",
    response_model=SourceFileResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_source(
    investigation_id: str,
    context: Annotated[ActorContext, Depends(get_actor_context)],
    file: Annotated[UploadFile, File(...)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> SourceFileResponse:
    _require(context, Capability.FINANCIAL_INVESTIGATION_WRITE)
    if idempotency_key is None:
        raise HTTPException(
            status_code=422,
            detail={"code": "INVALID_REQUEST", "message": "Idempotency-Key is required"},
        )
    try:
        content = await _read_upload_limited(file, get_settings().max_upload_bytes)
        inspection = inspect_upload(file.filename, file.content_type, content)
        replay = service.replay_source_if_present(
            context, investigation_id, inspection.sha256, idempotency_key
        )
        if replay is not None:
            return replay
        storage_reference = store_upload(content, inspection)
        try:
            source_file_id = f"SRC-{uuid4().hex[:12].upper()}"
            result = service.add_source(
                context,
                investigation_id,
                {
                    "id": source_file_id,
                    "original_filename": Path(file.filename or "upload").name,
                    "storage_reference": storage_reference,
                    "mime_type": inspection.mime_type,
                    "size_bytes": inspection.size_bytes,
                    "row_count": inspection.row_count,
                    "column_count": inspection.column_count,
                    "status": "UPLOADED",
                    "created_at": datetime.now(UTC),
                    "sha256": inspection.sha256,
                },
                idempotency_key,
            )
            if result.id != source_file_id:
                remove_upload(storage_reference)
            return result
        except Exception:
            remove_upload(storage_reference)
            raise
    except (UploadValidationError, ValueError) as error:
        raise HTTPException(
            status_code=422, detail={"code": "INVALID_REQUEST", "message": str(error)}
        ) from error
    except FinancialInvestigationNotFound as error:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "RESOURCE_NOT_FOUND",
                "message": "Financial investigation does not exist",
            },
        ) from error
    finally:
        await file.close()


async def _read_upload_limited(file: UploadFile, max_bytes: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while chunk := await file.read(1024 * 1024):
        total += len(chunk)
        if total > max_bytes:
            raise UploadValidationError(f"The uploaded file exceeds the {max_bytes} byte limit")
        chunks.append(chunk)
    return b"".join(chunks)


@router.get("/{investigation_id}/sources", response_model=list[SourceFileResponse])
def list_sources(
    investigation_id: str,
    context: Annotated[ActorContext, Depends(get_actor_context)],
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
) -> list[SourceFileResponse]:
    _require(context, Capability.FINANCIAL_INVESTIGATION_READ)
    try:
        return service.list_sources(context.organization_id, investigation_id, limit)
    except FinancialInvestigationNotFound as error:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "RESOURCE_NOT_FOUND",
                "message": "Financial investigation does not exist",
            },
        ) from error


@router.post(
    "/{investigation_id}/demo-data",
    response_model=DemoDataResponse,
    status_code=status.HTTP_201_CREATED,
)
def generate_demo_data(
    investigation_id: str,
    payload: DemoDataRequest,
    context: Annotated[ActorContext, Depends(get_actor_context)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> DemoDataResponse:
    _require(context, Capability.FINANCIAL_INVESTIGATION_WRITE)
    if idempotency_key is None:
        raise HTTPException(
            status_code=422,
            detail={"code": "INVALID_REQUEST", "message": "Idempotency-Key is required"},
        )
    try:
        return demo_data_service.generate(context, investigation_id, payload, idempotency_key)
    except FinancialInvestigationConflict as error:
        raise HTTPException(
            status_code=409, detail={"code": "IDEMPOTENCY_CONFLICT", "message": str(error)}
        ) from error
    except FinancialInvestigationNotFound as error:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "RESOURCE_NOT_FOUND",
                "message": "Financial investigation does not exist",
            },
        ) from error
    except ValueError as error:
        raise HTTPException(
            status_code=422, detail={"code": "INVALID_REQUEST", "message": str(error)}
        ) from error


@router.delete(
    "/{investigation_id}/sources/{source_file_id}", status_code=status.HTTP_204_NO_CONTENT
)
def delete_source(
    investigation_id: str,
    source_file_id: str,
    context: Annotated[ActorContext, Depends(get_actor_context)],
) -> Response:
    _require(context, Capability.FINANCIAL_INVESTIGATION_WRITE)
    try:
        storage_reference = service.delete_source(context, investigation_id, source_file_id)
        remove_upload(storage_reference)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except FinancialInvestigationNotFound as error:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "RESOURCE_NOT_FOUND",
                "message": "Financial investigation does not exist",
            },
        ) from error
    except SourceFileNotFound as error:
        raise HTTPException(
            status_code=404,
            detail={"code": "RESOURCE_NOT_FOUND", "message": "Source file does not exist"},
        ) from error


@router.post(
    "/{investigation_id}/sources/{source_file_id}/analyze", response_model=SourceAnalysisResponse
)
def analyze_source(
    investigation_id: str,
    source_file_id: str,
    context: Annotated[ActorContext, Depends(get_actor_context)],
) -> SourceAnalysisResponse:
    _require(context, Capability.FINANCIAL_INVESTIGATION_WRITE)
    try:
        return analysis_service.analyze(context, investigation_id, source_file_id)
    except SourceAnalysisNotFound as error:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "RESOURCE_NOT_FOUND",
                "message": "Source file or analysis does not exist",
            },
        ) from error
    except SourceAnalysisProviderUnavailable as error:
        raise HTTPException(
            status_code=503, detail={"code": "PROVIDER_UNAVAILABLE", "message": str(error)}
        ) from error
    except UploadValidationError as error:
        raise HTTPException(
            status_code=422, detail={"code": "INVALID_SOURCE", "message": str(error)}
        ) from error


@router.get(
    "/{investigation_id}/sources/{source_file_id}/analysis", response_model=SourceAnalysisResponse
)
def get_source_analysis(
    investigation_id: str,
    source_file_id: str,
    context: Annotated[ActorContext, Depends(get_actor_context)],
) -> SourceAnalysisResponse:
    _require(context, Capability.FINANCIAL_INVESTIGATION_READ)
    try:
        return analysis_service.get_analysis(
            context.organization_id, investigation_id, source_file_id
        )
    except SourceAnalysisNotFound as error:
        raise HTTPException(
            status_code=404,
            detail={"code": "RESOURCE_NOT_FOUND", "message": "Source analysis does not exist"},
        ) from error


@router.get(
    "/{investigation_id}/sources/{source_file_id}/mappings", response_model=list[MappingResponse]
)
def list_source_mappings(
    investigation_id: str,
    source_file_id: str,
    context: Annotated[ActorContext, Depends(get_actor_context)],
) -> list[MappingResponse]:
    _require(context, Capability.FINANCIAL_INVESTIGATION_READ)
    try:
        return analysis_service.list_mappings(
            context.organization_id, investigation_id, source_file_id
        )
    except SourceAnalysisNotFound as error:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "RESOURCE_NOT_FOUND",
                "message": "Source analysis or mappings do not exist",
            },
        ) from error


@router.patch(
    "/{investigation_id}/sources/{source_file_id}/mappings/{mapping_id}",
    response_model=MappingResponse,
)
def edit_source_mapping(
    investigation_id: str,
    source_file_id: str,
    mapping_id: str,
    payload: MappingEdit,
    context: Annotated[ActorContext, Depends(get_actor_context)],
) -> MappingResponse:
    _require(context, Capability.FINANCIAL_INVESTIGATION_WRITE)
    try:
        return analysis_service.update_mapping(
            context, investigation_id, source_file_id, mapping_id, payload
        )
    except SourceAnalysisNotFound as error:
        raise HTTPException(
            status_code=404,
            detail={"code": "RESOURCE_NOT_FOUND", "message": "Mapping does not exist"},
        ) from error
    except MappingConflict as error:
        raise HTTPException(
            status_code=409, detail={"code": "MAPPING_CONFLICT", "message": str(error)}
        ) from error


@router.post(
    "/{investigation_id}/sources/{source_file_id}/mappings/confirm",
    response_model=MappingConfirmationResponse,
)
def confirm_source_mappings(
    investigation_id: str,
    source_file_id: str,
    context: Annotated[ActorContext, Depends(get_actor_context)],
) -> MappingConfirmationResponse:
    _require(context, Capability.FINANCIAL_INVESTIGATION_WRITE)
    try:
        return analysis_service.confirm_mappings(context, investigation_id, source_file_id)
    except SourceAnalysisNotFound as error:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "RESOURCE_NOT_FOUND",
                "message": "Source analysis or mappings do not exist",
            },
        ) from error
    except MappingConfirmationRequired as error:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "MAPPING_CONFIRMATION_REQUIRED",
                "message": str(error),
                "missing_fields": error.missing_fields,
            },
        ) from error


@router.patch(
    "/{investigation_id}/sources/{source_file_id}/classification",
    response_model=SourceAnalysisResponse,
)
def update_source_classification(
    investigation_id: str,
    source_file_id: str,
    payload: SourceTypeUpdate,
    context: Annotated[ActorContext, Depends(get_actor_context)],
) -> SourceAnalysisResponse:
    _require(context, Capability.FINANCIAL_INVESTIGATION_WRITE)
    try:
        return analysis_service.update_classification(
            context, investigation_id, source_file_id, payload
        )
    except SourceAnalysisNotFound as error:
        raise HTTPException(
            status_code=404,
            detail={"code": "RESOURCE_NOT_FOUND", "message": "Source analysis does not exist"},
        ) from error
    except MappingConflict as error:
        raise HTTPException(
            status_code=409, detail={"code": "MAPPING_CONFLICT", "message": str(error)}
        ) from error


@router.post(
    "/{investigation_id}/relationships/discover", response_model=list[RelationshipResponse]
)
def discover_relationships(
    investigation_id: str, context: Annotated[ActorContext, Depends(get_actor_context)]
) -> list[RelationshipResponse]:
    _require(context, Capability.FINANCIAL_INVESTIGATION_WRITE)
    return relationship_service.discover(context, investigation_id)


@router.get("/{investigation_id}/relationships", response_model=list[RelationshipResponse])
def list_relationships(
    investigation_id: str, context: Annotated[ActorContext, Depends(get_actor_context)]
) -> list[RelationshipResponse]:
    _require(context, Capability.FINANCIAL_INVESTIGATION_READ)
    return relationship_service.list(context.organization_id, investigation_id)


@router.patch(
    "/{investigation_id}/relationships/{relationship_id}", response_model=RelationshipResponse
)
def decide_relationship(
    investigation_id: str,
    relationship_id: str,
    payload: RelationshipDecision,
    context: Annotated[ActorContext, Depends(get_actor_context)],
) -> RelationshipResponse:
    _require(context, Capability.FINANCIAL_INVESTIGATION_WRITE)
    try:
        return relationship_service.decide(context, investigation_id, relationship_id, payload)
    except RelationshipNotFound as error:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "RESOURCE_NOT_FOUND",
                "message": "Relationship proposal does not exist",
            },
        ) from error
    except RelationshipConflict as error:
        raise HTTPException(
            status_code=409, detail={"code": "INVALID_STATE", "message": str(error)}
        ) from error


@router.post(
    "/{investigation_id}/dataset-versions/normalize", response_model=DatasetVersionResponse
)
def normalize_dataset(
    investigation_id: str,
    context: Annotated[ActorContext, Depends(get_actor_context)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> DatasetVersionResponse:
    _require(context, Capability.FINANCIAL_INVESTIGATION_WRITE)
    if idempotency_key is None:
        raise HTTPException(
            status_code=422,
            detail={"code": "INVALID_REQUEST", "message": "Idempotency-Key is required"},
        )
    try:
        return normalization_service.normalize(context, investigation_id, idempotency_key)
    except NormalizationBlocked as error:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "NORMALIZATION_BLOCKED",
                "message": str(error),
                "reasons": error.reasons,
            },
        ) from error
    except NormalizationConflict as error:
        raise HTTPException(
            status_code=409, detail={"code": "IDEMPOTENCY_CONFLICT", "message": str(error)}
        ) from error


@router.get("/{investigation_id}/dataset-versions/latest", response_model=DatasetVersionResponse)
def latest_dataset(
    investigation_id: str, context: Annotated[ActorContext, Depends(get_actor_context)]
) -> DatasetVersionResponse:
    _require(context, Capability.FINANCIAL_INVESTIGATION_READ)
    try:
        return normalization_service.latest(context.organization_id, investigation_id)
    except DatasetVersionNotFound as error:
        raise HTTPException(
            status_code=404,
            detail={"code": "RESOURCE_NOT_FOUND", "message": "No normalized dataset exists"},
        ) from error


@router.get(
    "/{investigation_id}/dataset-versions/{dataset_version_id}/records",
    response_model=list[NormalizedRecordResponse],
)
def normalized_records(
    investigation_id: str,
    dataset_version_id: str,
    context: Annotated[ActorContext, Depends(get_actor_context)],
    limit: Annotated[int, Query(ge=1, le=10000)] = 1000,
) -> list[NormalizedRecordResponse]:
    _require(context, Capability.FINANCIAL_INVESTIGATION_READ)
    return normalization_service.records(
        context.organization_id, investigation_id, dataset_version_id, limit
    )


@router.post("/{investigation_id}/reconciliation-runs", response_model=ReconciliationRunResponse)
def run_reconciliation(
    investigation_id: str,
    payload: ReconciliationRunRequest,
    context: Annotated[ActorContext, Depends(get_actor_context)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> ReconciliationRunResponse:
    _require(context, Capability.FINANCIAL_INVESTIGATION_WRITE)
    if idempotency_key is None:
        raise HTTPException(
            status_code=422,
            detail={"code": "INVALID_REQUEST", "message": "Idempotency-Key is required"},
        )
    try:
        return reconciliation_service.run(
            context, investigation_id, payload.dataset_version_id, idempotency_key
        )
    except ReconciliationNotFound as error:
        raise HTTPException(
            status_code=404, detail={"code": "RESOURCE_NOT_FOUND", "message": str(error)}
        ) from error
    except ReconciliationBlocked as error:
        raise HTTPException(
            status_code=409, detail={"code": "RECONCILIATION_BLOCKED", "message": str(error)}
        ) from error
    except ReconciliationConflict as error:
        raise HTTPException(
            status_code=409, detail={"code": "IDEMPOTENCY_CONFLICT", "message": str(error)}
        ) from error


@router.get(
    "/{investigation_id}/reconciliation-runs/latest", response_model=ReconciliationRunResponse
)
def latest_reconciliation(
    investigation_id: str, context: Annotated[ActorContext, Depends(get_actor_context)]
) -> ReconciliationRunResponse:
    _require(context, Capability.FINANCIAL_INVESTIGATION_READ)
    try:
        return reconciliation_service.latest(context.organization_id, investigation_id)
    except ReconciliationNotFound as error:
        raise HTTPException(
            status_code=404,
            detail={"code": "RESOURCE_NOT_FOUND", "message": "No reconciliation run exists"},
        ) from error


@router.get(
    "/{investigation_id}/reconciliation-runs/{run_id}/results",
    response_model=list[ReconciliationResultResponse],
)
def reconciliation_results(
    investigation_id: str,
    run_id: str,
    context: Annotated[ActorContext, Depends(get_actor_context)],
    limit: Annotated[int, Query(ge=1, le=10000)] = 1000,
) -> list[ReconciliationResultResponse]:
    _require(context, Capability.FINANCIAL_INVESTIGATION_READ)
    return reconciliation_service.results(context.organization_id, investigation_id, run_id, limit)


@router.post(
    "/{investigation_id}/reconciliation-runs/{run_id}/results/{result_id}/investigate",
    response_model=InvestigationResponse,
)
def investigate_financial_exception(
    investigation_id: str,
    run_id: str,
    result_id: str,
    context: Annotated[ActorContext, Depends(get_actor_context)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> InvestigationResponse | JSONResponse:
    _require(context, Capability.EXCEPTION_INVESTIGATE)
    if idempotency_key is None:
        raise HTTPException(
            status_code=422,
            detail={"code": "INVALID_REQUEST", "message": "Idempotency-Key is required"},
        )
    try:
        response = financial_exception_service.investigate(
            context, investigation_id, run_id, result_id, idempotency_key
        )
        if response.status == "FAILED":
            return JSONResponse(status_code=503, content=response.model_dump(mode="json"))
        return response
    except FinancialExceptionNotFound as error:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "RESOURCE_NOT_FOUND",
                "message": "Reconciliation exception does not exist",
            },
        ) from error
    except FinancialExceptionConflict as error:
        raise HTTPException(
            status_code=409, detail={"code": "IDEMPOTENCY_CONFLICT", "message": str(error)}
        ) from error


@router.get(
    "/{investigation_id}/reconciliation-runs/{run_id}/results/{result_id}/investigation",
    response_model=InvestigationResponse,
)
def get_financial_exception_investigation(
    investigation_id: str,
    run_id: str,
    result_id: str,
    context: Annotated[ActorContext, Depends(get_actor_context)],
) -> InvestigationResponse:
    _require(context, Capability.EXCEPTION_INVESTIGATE)
    try:
        return financial_exception_service.get(
            context.organization_id, investigation_id, run_id, result_id
        )
    except FinancialExceptionNotFound as error:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "RESOURCE_NOT_FOUND",
                "message": "Uploaded exception investigation does not exist",
            },
        ) from error


@router.get(
    "/{investigation_id}/patterns", response_model=list[FinancialInvestigationPatternResponse]
)
def financial_investigation_patterns(
    investigation_id: str, context: Annotated[ActorContext, Depends(get_actor_context)]
) -> list[FinancialInvestigationPatternResponse]:
    _require(context, Capability.FINANCIAL_INVESTIGATION_READ)
    return pattern_service.list(context.organization_id, investigation_id)


def _require(context: ActorContext, capability: Capability) -> None:
    if capability not in context.capabilities:
        raise HTTPException(
            status_code=403, detail={"code": "FORBIDDEN", "message": "Capability is required"}
        )
