import os

import pytest
from httpx import ASGITransport, AsyncClient

pytestmark = pytest.mark.skipif(
    not os.environ.get("FINTRACE_TEST_DATABASE_URL"),
    reason="set FINTRACE_TEST_DATABASE_URL to run the PostgreSQL integration suite",
)


@pytest.mark.asyncio
async def test_postgres_api_vertical_slice() -> None:
    from app.main import app

    headers = {
        "X-Organization-Id": "ORG-001",
        "X-Actor-Id": "integration-controller",
        "X-Actor-Role": "CONTROLLER",
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        ready = await client.get("/ready")
        summary = await client.get("/api/v1/dashboard/summary", headers=headers)
        exceptions = await client.get("/api/v1/exceptions", headers=headers)
        investigation = await client.post(
            "/api/v1/exceptions/EXC-10000/investigations",
            headers={**headers, "Idempotency-Key": "postgres-integration-investigation"},
        )
        loaded = await client.get(
            f"/api/v1/investigations/{investigation.json()['investigation_id']}", headers=headers
        )

    assert ready.json() == {"status": "ready", "storage_backend": "postgres"}
    assert summary.json()["lifecycle_count"] >= 1
    assert len(exceptions.json()) >= 1
    assert investigation.status_code == 200
    assert loaded.json()["investigation_id"] == investigation.json()["investigation_id"]
