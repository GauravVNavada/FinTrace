import base64
import hashlib
import hmac
import json
import time

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import get_settings
from app.main import app


def _token(*, organization_id: str = "ORG-001", role: str = "CONTROLLER", actor: str = "signed-actor") -> str:
    settings = get_settings()
    header = {"alg": "HS256", "typ": "JWT"}
    claims = {
        "sub": actor,
        "organization_id": organization_id,
        "role": role,
        "iss": settings.auth_issuer,
        "aud": settings.auth_audience,
        "iat": int(time.time()),
        "exp": int(time.time()) + 300,
    }

    def encode(value: dict[str, object]) -> str:
        return base64.urlsafe_b64encode(json.dumps(value, separators=(",", ":")).encode()).decode().rstrip("=")

    signing_input = f"{encode(header)}.{encode(claims)}"
    signature = hmac.new(settings.auth_secret.encode(), signing_input.encode(), hashlib.sha256).digest()
    return f"{signing_input}.{base64.urlsafe_b64encode(signature).decode().rstrip('=')}"


@pytest.mark.asyncio
async def test_signed_bearer_claims_resolve_tenant_and_actor() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/dashboard/summary", headers={"Authorization": f"Bearer {_token()}"})

    assert response.status_code == 200
    assert response.json()["organization_id"] == "ORG-001"


@pytest.mark.asyncio
async def test_invalid_bearer_signature_is_rejected() -> None:
    token_parts = _token().split(".")
    token_parts[2] = ("a" if token_parts[2][0] != "a" else "b") + token_parts[2][1:]
    token = ".".join(token_parts)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/dashboard/summary", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_bearer_tenant_cannot_be_overridden_by_header() -> None:
    headers = {"Authorization": f"Bearer {_token(organization_id='ORG-001')}", "X-Organization-Id": "ORG-OTHER"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/dashboard/summary", headers=headers)

    assert response.status_code == 403
