import base64
import hashlib
import hmac
import json
import time
from io import BytesIO
from typing import Self
from urllib.error import HTTPError

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import Settings, get_settings
from app.investigations.provider import (
    AgentDecision,
    FailoverAIClient,
    GeminiProvider,
    GroqProvider,
    OpenAICompatibleAIClient,
    ProviderFailureInfo,
    ProviderUnavailable,
    get_ai_client,
)
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


@pytest.mark.asyncio
async def test_demo_login_preserves_role_capabilities_and_exception_detail_access() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        analyst_login = await client.post(
            "/api/v1/auth/demo-login", json={"role": "ANALYST"}
        )
        controller_login = await client.post(
            "/api/v1/auth/demo-login", json={"role": "CONTROLLER"}
        )

        analyst_headers = {"Authorization": f"Bearer {analyst_login.json()['access_token']}"}
        controller_headers = {
            "Authorization": f"Bearer {controller_login.json()['access_token']}"
        }
        exception = await client.get(
            "/api/v1/exceptions/EXC-1042", headers=analyst_headers
        )
        audit = await client.get("/api/v1/audit-events", headers=analyst_headers)
        controller_audit = await client.get(
            "/api/v1/audit-events", headers=controller_headers
        )

    assert analyst_login.status_code == 200
    assert analyst_login.json()["role"] == "ANALYST"
    assert controller_login.status_code == 200
    assert controller_login.json()["role"] == "CONTROLLER"
    assert exception.status_code == 200
    assert audit.status_code == 403
    assert controller_audit.status_code == 200


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
        gemini_api_key="gemini-direct",
        gemini_api_key_1="gemini-key-1",
        gemini_api_key_2="gemini-key-2",
        groq_api_key="groq-direct",
        groq_api_key_1="groq-key-1",
        groq_api_key_2="groq-key-2",
        ai_fallback_provider="groq",
    )
    assert settings.configured_ai_api_keys == ("gemini-direct", "gemini-key-1", "gemini-key-2")
    assert settings.configured_ai_fallback_api_keys == ("groq-direct", "groq-key-1", "groq-key-2")
    assert isinstance(get_ai_client("gemini", settings.configured_ai_api_keys), GeminiProvider)
    assert isinstance(get_ai_client("groq", "groq-key"), GroqProvider)
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


def test_provider_health_classifies_malformed_success_response(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeResponse:
        def __enter__(self) -> Self:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self) -> bytes:
            return b'{"choices":[{"message":{"role":"assistant"}}]}'

    monkeypatch.setattr("app.investigations.provider.request.urlopen", lambda *args, **kwargs: FakeResponse())
    client = OpenAICompatibleAIClient("key", "https://provider.test/v1", "model", 1)

    result = client.health_check()

    assert result.status == "UNAVAILABLE"
    assert result.error_category == "invalid_response"
    assert result.retryable is False


def test_provider_health_requires_structured_tool_capability(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeResponse:
        def __enter__(self) -> Self:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self) -> bytes:
            return b'{"choices":[{"message":{"tool_calls":[{"function":{"name":"fintrace_health_probe","arguments":"{}"}}]}}]}'

    monkeypatch.setattr("app.investigations.provider.request.urlopen", lambda *args, **kwargs: FakeResponse())
    client = OpenAICompatibleAIClient("key", "https://provider.test/v1", "model", 1)

    result = client.health_check()

    assert result.status == "CONNECTED"
    assert result.overall_status == "AVAILABLE"


def test_provider_health_classifies_forbidden_response(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*args: object, **kwargs: object) -> None:
        raise HTTPError("https://provider.test", 403, "Forbidden", {}, None)

    monkeypatch.setattr("app.investigations.provider.request.urlopen", forbidden)
    client = OpenAICompatibleAIClient("key", "https://provider.test/v1", "model", 1)

    result = client.health_check()

    assert result.status == "UNAVAILABLE"
    assert result.error_category == "forbidden"
    assert result.retryable is False


def test_provider_health_preserves_quota_diagnostic_without_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def rate_limited(*args: object, **kwargs: object) -> None:
        raise HTTPError(
            "https://provider.test",
            429,
            "Too Many Requests",
            {},
            BytesIO(
                b'{"error":{"code":429,"status":"RESOURCE_EXHAUSTED",'
                b'"message":"quota exceeded", "details":[{"violations":['
                b'{"quotaMetric":"generate_content_free_tier_requests",'
                b'"quotaId":"GenerateRequestsPerDayPerProject-FreeTier",'
                b'"quotaValue":"20"}],"retryDelay":"43s"}]}}'
            ),
        )

    monkeypatch.setattr("app.investigations.provider.request.urlopen", rate_limited)
    client = OpenAICompatibleAIClient("key", "https://provider.test/v1", "model", 1)

    result = client.health_check()

    assert result.error_category == "quota_exhausted"
    assert "GenerateRequestsPerDayPerModel-FreeTier" not in (result.detail or "")
    assert "GenerateRequestsPerDayPerProject-FreeTier" in (result.detail or "")
    assert "key" not in (result.detail or "")
    assert result.retryable is False


def test_provider_specific_keys_never_cross_provider_slots() -> None:
    settings = Settings(
        _env_file=None,
        ai_provider="gemini",
        gemini_api_key="gemini-secret",
        groq_api_key="groq-secret",
        ai_fallback_provider="groq",
    )

    assert settings.configured_ai_api_keys == ("gemini-secret",)
    assert settings.configured_ai_fallback_api_keys == ("groq-secret",)

    groq_settings = Settings(
        _env_file=None,
        ai_provider="groq",
        ai_model="ignored-generic-model",
        groq_model="configured-groq-model",
        groq_api_key="groq-secret",
    )
    assert groq_settings.resolved_ai_model == "configured-groq-model"
    assert groq_settings.resolved_ai_base_url == "https://api.groq.com/openai/v1"


def test_failover_only_uses_fallback_for_retryable_provider_failures() -> None:
    class FailingProvider:
        provider = "gemini"
        model = "gemini-model"

        def __init__(self, category: str, retryable: bool) -> None:
            self.error = ProviderUnavailable(
                "provider failure",
                info=ProviderFailureInfo(category, retryable),
            )

        def next_step(self, *args: object, **kwargs: object) -> AgentDecision:
            raise self.error

    class FallbackProvider:
        provider = "groq"
        model = "groq-model"
        calls = 0

        def next_step(self, *args: object, **kwargs: object) -> AgentDecision:
            self.calls += 1
            return AgentDecision("final", candidate={
                "status": "UNRESOLVED",
                "summary": "manual review",
                "requires_human_review": True,
            })

    fallback = FallbackProvider()
    retryable = FailoverAIClient((FailingProvider("rate_limited", True), fallback))
    decision = retryable.next_step(None, [], [], [], [])
    assert decision.action == "final"
    assert retryable.provider == "groq"
    assert retryable.fallback_used is True
    assert retryable.fallback_reason == "rate_limited"

    fallback.calls = 0
    non_retryable = FailoverAIClient((FailingProvider("forbidden", False), fallback))
    with pytest.raises(ProviderUnavailable):
        non_retryable.next_step(None, [], [], [], [])
    assert fallback.calls == 0
