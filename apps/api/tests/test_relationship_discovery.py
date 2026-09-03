import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


def headers(role="CONTROLLER", key=None):
    result = {
        "X-Organization-Id": "ORG-REL",
        "X-Actor-Id": "relationship-user",
        "X-Actor-Role": role,
    }
    if key:
        result["Idempotency-Key"] = key
    return result


@pytest.mark.asyncio
async def test_relationship_discovery_requires_confirmed_mappings_and_is_reviewable():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await client.post(
            "/api/v1/financial-investigations",
            headers=headers(key="rel-create"),
            json={
                "name": "Relationship review",
                "period_start": "2026-08-01",
                "period_end": "2026-08-31",
                "base_currency": "INR",
            },
        )
        investigation_id = created.json()["id"]
        source_ids = []
        for key, filename, body in [
            ("rel-orders", "orders.csv", b"Order ID,Amount\nORD-1,100\n"),
            ("rel-payments", "payments.csv", b"Payment ID,Order ID,Amount\nPAY-1,ORD-1,100\n"),
        ]:
            uploaded = await client.post(
                f"/api/v1/financial-investigations/{investigation_id}/sources",
                headers=headers(key=key),
                files={"file": (filename, body, "text/csv")},
            )
            source_id = uploaded.json()["id"]
            source_ids.append(source_id)
            analyzed = await client.post(
                f"/api/v1/financial-investigations/{investigation_id}/sources/{source_id}/analyze",
                headers=headers(key=f"rel-analyze-{key}"),
            )
            assert analyzed.status_code == 200
            mappings = (
                await client.get(
                    f"/api/v1/financial-investigations/{investigation_id}/sources/{source_id}/mappings",
                    headers=headers("ANALYST"),
                )
            ).json()
            for mapping in mappings:
                if mapping["required"]:
                    assert (
                        await client.patch(
                            f"/api/v1/financial-investigations/{investigation_id}/sources/{source_id}/mappings/{mapping['id']}",
                            headers=headers(key=f"rel-mapping-{mapping['id']}"),
                            json={"canonical_field": mapping["canonical_field"], "ignored": False},
                        )
                    ).status_code == 200
            assert (
                await client.post(
                    f"/api/v1/financial-investigations/{investigation_id}/sources/{source_id}/mappings/confirm",
                    headers=headers(key=f"rel-confirm-{key}"),
                )
            ).status_code == 200
        discovered = await client.post(
            f"/api/v1/financial-investigations/{investigation_id}/relationships/discover",
            headers=headers(key="rel-discover"),
        )
        assert discovered.status_code == 200
        assert discovered.json()[0]["status"] == "PROPOSED"
        assert "order_id" in discovered.json()[0]["join_fields"]
        replayed_discovery = await client.post(
            f"/api/v1/financial-investigations/{investigation_id}/relationships/discover",
            headers=headers(key="rel-discover"),
        )
        assert replayed_discovery.status_code == 200
        assert replayed_discovery.json() == discovered.json()
        relationship_id = discovered.json()[0]["id"]
        accepted = await client.patch(
            f"/api/v1/financial-investigations/{investigation_id}/relationships/{relationship_id}",
            headers=headers(key="rel-accept"),
            json={"status": "ACCEPTED"},
        )
        assert accepted.status_code == 200
        assert accepted.json()["status"] == "ACCEPTED"
        replayed_acceptance = await client.patch(
            f"/api/v1/financial-investigations/{investigation_id}/relationships/{relationship_id}",
            headers=headers(key="rel-accept"),
            json={"status": "ACCEPTED"},
        )
        assert replayed_acceptance.status_code == 200
        assert replayed_acceptance.json() == accepted.json()
