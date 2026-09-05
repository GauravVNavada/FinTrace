import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as test_client:
        yield test_client


async def test_health(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "strict-origin-when-cross-origin"


async def test_readiness_reports_sample_backend(client: AsyncClient) -> None:
    response = await client.get("/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready", "storage_backend": "sample"}


async def test_dashboard_requires_tenant_context(client: AsyncClient) -> None:
    response = await client.get("/api/v1/dashboard/summary")
    assert response.status_code == 401


async def test_dashboard_is_organization_scoped(client: AsyncClient) -> None:
    response = await client.get(
        "/api/v1/dashboard/summary", headers={"X-Organization-Id": "ORG-001"}
    )
    assert response.status_code == 200
    assert response.json()["organization_id"] == "ORG-001"


async def test_sample_adapter_does_not_project_flagship_data_into_other_tenant(
    client: AsyncClient,
) -> None:
    dashboard = await client.get(
        "/api/v1/dashboard/summary", headers={"X-Organization-Id": "ORG-OTHER"}
    )
    exceptions = await client.get(
        "/api/v1/exceptions", headers={"X-Organization-Id": "ORG-OTHER"}
    )

    assert dashboard.status_code == 200
    assert dashboard.json()["lifecycle_count"] == 0
    assert dashboard.json()["exception_count"] == 0
    assert exceptions.status_code == 200
    assert exceptions.json() == []


async def test_lifecycle_is_returned_for_scoped_order(client: AsyncClient) -> None:
    response = await client.get(
        "/api/v1/lifecycles/ORD-10000", headers={"X-Organization-Id": "ORG-001"}
    )
    assert response.status_code == 200
    assert response.json()["order"]["order_id"] == "ORD-10000"


async def test_lifecycle_cannot_cross_tenant_scope(client: AsyncClient) -> None:
    response = await client.get(
        "/api/v1/lifecycles/ORD-10000", headers={"X-Organization-Id": "ORG-OTHER"}
    )
    assert response.status_code == 404
