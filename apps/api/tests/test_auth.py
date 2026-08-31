import base64
import hashlib
import hmac
import json
import time
from typing import Self
from urllib.error import HTTPError

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import Settings, get_settings
from app.investigations.provider import FailoverAIClient, OpenAICompatibleAIClient, get_ai_client
from app.main import app


def _token(
    *, organization_id: str = "ORG-001", role: str = "CONTROLLER", actor: str = "signed-actor"
) -> str:
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
        return (
            base64.urlsafe_b64encode(json.dumps(value, separators=(",", ":")).encode())
            .decode()
            .rstrip("=")
        )

    signing_input = f"{encode(header)}.{encode(claims)}"
    signature = hmac.new(
        settings.auth_secret.encode(), signing_input.encode(), hashlib.sha256
    ).digest()
    return f"{signing_input}.{base64.urlsafe_b64encode(signature).decode().rstrip('=')}"


@pytest.mark.asyncio
async def test_signed_bearer_claims_resolve_tenant_and_actor() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/api/v1/dashboard/summary", headers={"Authorization": f"Bearer {_token()}"}
        )

    assert response.status_code == 200
    assert response.json()["organization_id"] == "ORG-001"


@pytest.mark.asyncio
async def test_request_id_is_returned_and_safe_values_are_preserved() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/health",
            headers={"X-Request-Id": "qa-run-001"},
        )
    assert response.status_code == 200
    assert response.headers["X-Request-Id"] == "qa-run-001"


@pytest.mark.asyncio
async def test_invalid_bearer_signature_is_rejected() -> None:
    token_parts = _token().split(".")
    token_parts[2] = ("a" if token_parts[2][0] != "a" else "b") + token_parts[2][1:]
    token = ".".join(token_parts)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/api/v1/dashboard/summary", headers={"Authorization": f"Bearer {token}"}
        )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_bearer_tenant_cannot_be_overridden_by_header() -> None:
    headers = {
        "Authorization": f"Bearer {_token(organization_id='ORG-001')}",
        "X-Organization-Id": "ORG-OTHER",
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/dashboard/summary", headers=headers)

    assert response.status_code == 403


def test_required_auth_rejects_default_or_short_secret() -> None:
    with pytest.raises(ValueError, match="AUTH_SECRET"):
        Settings(auth_mode="required", auth_secret="fintrace-development-only-secret")
    with pytest.raises(ValueError, match="AUTH_SECRET"):
        Settings(auth_mode="required", auth_secret="too-short")


def test_non_development_rejects_offline_ai_provider() -> None:
    with pytest.raises(ValueError, match="AUTH_MODE|required|live AI provider"):
        Settings(app_env="production", ai_provider="stub", ai_api_key="")


def test_non_development_requires_required_auth_mode() -> None:
    with pytest.raises(ValueError, match="AUTH_MODE=required"):
        Settings(
            app_env="production", auth_mode="development", ai_provider="openai", ai_api_key="x" * 32
        )


def test_auth_mode_is_normalized_before_release_validation() -> None:
    settings = Settings(
        app_env="production",
        auth_mode="REQUIRED",
        auth_secret="x" * 32,
        ai_provider="openai",
        ai_api_key="x" * 32,
    )
    assert settings.auth_mode == "required"


def test_provider_key_slots_select_first_configured_key_and_support_aliases() -> None:
    settings = Settings(
        ai_provider="gemini",
        gemini_api_key_1="gemini-key-1",
        gemini_api_key_2="gemini-key-2",
        groq_api_key_1="groq-key-1",
        groq_api_key_2="groq-key-2",
        ai_fallback_provider="groq",
    )
    assert settings.ai_api_key == "gemini-key-1"
    assert settings.configured_ai_api_keys == ("gemini-key-1", "gemini-key-2")
    assert settings.configured_ai_fallback_api_keys == ("groq-key-1", "groq-key-2")
    assert isinstance(get_ai_client("gemini", settings.ai_api_key), OpenAICompatibleAIClient)
    assert isinstance(get_ai_client("groq", "groq-key"), OpenAICompatibleAIClient)
    assert isinstance(
        get_ai_client(
            "gemini",
            settings.configured_ai_api_keys,
            fallback_provider_name=settings.ai_fallback_provider,
            fallback_api_key=settings.configured_ai_fallback_api_keys,
        ),
        FailoverAIClient,
    )


def test_provider_retries_next_key_after_rate_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeResponse:
        def __enter__(self) -> Self:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self) -> bytes:
            return b'{"choices":[{"message":{"content":"{\\"ok\\":true}"}}]}'

    calls: list[str] = []

    def fake_urlopen(request_object: object, timeout: float) -> FakeResponse:
        del timeout
        key = request_object.headers["Authorization"]
        calls.append(key)
        if len(calls) == 1:
            raise HTTPError("https://provider.test", 429, "rate limited", {}, None)
        return FakeResponse()

    monkeypatch.setattr("app.investigations.provider.request.urlopen", fake_urlopen)
    client = OpenAICompatibleAIClient(
        ("first-key", "second-key"), "https://provider.test/v1", "model", 1
    )

    assert client._chat("test", {}) == {"ok": True}
    assert calls == ["Bearer first-key", "Bearer second-key"]
