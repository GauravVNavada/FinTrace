from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict

from app.api.deps import create_signed_token
from app.controls.schemas import Role
from app.core.config import get_settings

router = APIRouter()


class SampleLoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Role


class SampleLoginResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    access_token: str
    token_type: str = "bearer"
    expires_in: int
    organization_id: str
    actor_id: str
    role: Role
    display_name: str


_IDENTITIES = {
    Role.AUDITOR: ("sample-auditor", "Sample auditor"),
    Role.ANALYST: ("sample-analyst", "Anika Rao"),
    Role.FINANCE_MANAGER: ("sample-finance-manager", "Rohan Shah"),
    Role.CONTROLLER: ("sample-controller", "Gaurav"),
}


@router.post("/local-login", response_model=SampleLoginResponse)
def sample_login(payload: SampleLoginRequest) -> SampleLoginResponse:
    settings = get_settings()
    if settings.auth_mode != "development":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "SAMPLE_LOGIN_DISABLED", "message": "Sample login is disabled."},
        )
    actor_id, display_name = _IDENTITIES[payload.role]
    expires_in = 3600
    return SampleLoginResponse(
        access_token=create_signed_token(
            organization_id="ORG-001",
            actor_id=actor_id,
            role=payload.role.value,
            expires_in=expires_in,
        ),
        expires_in=expires_in,
        organization_id="ORG-001",
        actor_id=actor_id,
        role=payload.role,
        display_name=display_name,
    )
