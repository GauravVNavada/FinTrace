import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


def headers(role="CONTROLLER", key=None):
    result = {"X-Organization-Id": "ORG-NORM", "X-Actor-Id": "normalizer", "X-Actor-Role": role}
    if key:
        result["Idempotency-Key"] = key
    return result


@pytest.mark.asyncio
async def test_normalization_preserves_source_lineage_and_blocks_unconfirmed_sources():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await client.post(
            "/api/v1/financial-investigations",
            headers=headers(key="norm-create"),
            json={
                "name": "Normalization",
                "period_start": "2026-08-01",
                "period_end": "2026-08-31",
                "base_currency": "INR",
            },
        )
        investigation_id = created.json()["id"]
        upload = await client.post(
            f"/api/v1/financial-investigations/{investigation_id}/sources",
            headers=headers(key="norm-upload"),
            files={"file": ("orders.csv", b"Order ID,Amount\nORD-1,100\nORD-2,200\n", "text/csv")},
        )
        source_id = upload.json()["id"]
        blocked = await client.post(
            f"/api/v1/financial-investigations/{investigation_id}/dataset-versions/normalize",
            headers=headers(key="norm-blocked"),
        )
        assert blocked.status_code == 409
        await client.post(
            f"/api/v1/financial-investigations/{investigation_id}/sources/{source_id}/analyze",
            headers=headers(),
        )
        mappings = (
            await client.get(
                f"/api/v1/financial-investigations/{investigation_id}/sources/{source_id}/mappings",
                headers=headers("ANALYST"),
            )
        ).json()
        for mapping in mappings:
            if mapping["required"]:
                await client.patch(
                    f"/api/v1/financial-investigations/{investigation_id}/sources/{source_id}/mappings/{mapping['id']}",
                    headers=headers(),
                    json={"canonical_field": mapping["canonical_field"], "ignored": False},
                )
        assert (
            await client.post(
                f"/api/v1/financial-investigations/{investigation_id}/sources/{source_id}/mappings/confirm",
                headers=headers(),
            )
        ).status_code == 200
        normalized = await client.post(
            f"/api/v1/financial-investigations/{investigation_id}/dataset-versions/normalize",
            headers=headers(key="norm-normalize"),
        )
        assert normalized.status_code == 200
        assert normalized.json()["record_count"] == 2
        records = await client.get(
            f"/api/v1/financial-investigations/{investigation_id}/dataset-versions/{normalized.json()['id']}/records",
            headers=headers("ANALYST"),
        )
        assert records.status_code == 200
        assert records.json()[0]["lineage"]["order_id"]["source_file_id"] == source_id
        assert records.json()[0]["lineage"]["order_id"]["source_row_number"] == 2
        replay = await client.post(
            f"/api/v1/financial-investigations/{investigation_id}/dataset-versions/normalize",
            headers=headers(key="norm-normalize"),
        )
        assert replay.status_code == 200
        assert replay.json() == normalized.json()
