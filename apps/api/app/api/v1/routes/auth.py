from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict

from app.api.deps import create_signed_token
from app.controls.schemas import Role
from app.core.config import get_settings

router = APIRouter()


class DemoLoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Role


class DemoLoginResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    access_token: str
    token_type: str = "bearer"
    expires_in: int
    organization_id: str
    actor_id: str
    role: Role
    display_name: str


_IDENTITIES = {
    Role.ANALYST: ("demo-analyst", "Anika Rao"),
    Role.FINANCE_MANAGER: ("demo-finance-manager", "Rohan Shah"),
    Role.CONTROLLER: ("demo-controller", "Priya Menon"),
}


@router.post("/demo-login", response_model=DemoLoginResponse)
def demo_login(payload: DemoLoginRequest) -> DemoLoginResponse:
    settings = get_settings()
    if settings.auth_mode != "development":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "DEMO_LOGIN_DISABLED", "message": "Demo login is disabled."},
        )
    actor_id, display_name = _IDENTITIES[payload.role]
    expires_in = 3600
    return DemoLoginResponse(
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
