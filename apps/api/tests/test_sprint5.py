import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as test_client:
        yield test_client


def _headers(role: str = "CONTROLLER", key: str = "sprint5-001") -> dict[str, str]:
    return {
        "X-Organization-Id": "ORG-001",
        "X-Actor-Role": role,
        "X-Actor-Id": "sprint5-user",
        "Idempotency-Key": key,
    }


@pytest.mark.asyncio
async def test_flagship_graph_is_derived_and_tenant_scoped(client: AsyncClient) -> None:
    response = await client.get(
        "/api/v1/exceptions/EXC-1042/graph",
        headers={"X-Organization-Id": "ORG-001", "X-Actor-Role": "ANALYST"},
    )
    cross_tenant = await client.get(
        "/api/v1/exceptions/EXC-1042/graph",
        headers={"X-Organization-Id": "ORG-OTHER", "X-Actor-Role": "ANALYST"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["nodes"]) == 9
    assert {node["id"] for node in payload["nodes"] if node["state"] == "MISSING"} == {
        "MISSING-INVENTORY-RETURN",
        "MISSING-ERP-REVERSAL",
    }
    assert any(edge["relationship"] == "PAYMENT_HAS_REFUND" for edge in payload["edges"])
    assert cross_tenant.status_code == 404


@pytest.mark.asyncio
async def test_patterns_are_deterministic_and_capability_gated(client: AsyncClient) -> None:
    analyst = await client.get(
        "/api/v1/patterns", headers={"X-Organization-Id": "ORG-001", "X-Actor-Role": "ANALYST"}
    )
    first = await client.get("/api/v1/patterns?limit=5", headers=_headers(key="sprint5-patterns-a"))
    second = await client.get(
        "/api/v1/patterns?limit=5", headers=_headers(key="sprint5-patterns-b")
    )

    assert analyst.status_code == 403
    assert first.status_code == 200
    assert first.json() == second.json()
    assert len(first.json()) == 5
    assert first.json()[0]["occurrence_count"] >= 2
    detail = await client.get(
        f"/api/v1/patterns/{first.json()[0]['pattern_id']}",
        headers={"X-Organization-Id": "ORG-001", "X-Actor-Role": "CONTROLLER"},
    )
    assert detail.status_code == 200


@pytest.mark.asyncio
async def test_evaluation_report_is_idempotent_and_hidden_labels_stay_internal(
    client: AsyncClient,
) -> None:
    headers = _headers(key="sprint5-evaluation-001")
    body = {"orders": 50, "seed": 42, "anomaly_rate": 0.3}
    first = await client.post("/api/v1/evaluation/run", headers=headers, json=body)
    replay = await client.post("/api/v1/evaluation/run", headers=headers, json=body)
    latest = await client.get(
        "/api/v1/evaluation/latest",
        headers={"X-Organization-Id": "ORG-001", "X-Actor-Role": "CONTROLLER"},
    )
    analyst = await client.get(
        "/api/v1/evaluation/latest",
        headers={"X-Organization-Id": "ORG-001", "X-Actor-Role": "ANALYST"},
    )

    assert first.status_code == 200
    assert replay.status_code == 200
    assert first.json() == replay.json()
    assert first.json()["report"]["lifecycles"] == 50
    assert "ground_truth" not in first.text
    assert latest.status_code == 200
    assert latest.json()["evaluation_id"] == first.json()["evaluation_id"]
    assert analyst.status_code == 403
