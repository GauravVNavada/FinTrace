import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


def headers(role: str = "CONTROLLER", key: str | None = None) -> dict[str, str]:
    result = {"X-Organization-Id": "ORG-RECON", "X-Actor-Id": "reconciler", "X-Actor-Role": role}
    if key:
        result["Idempotency-Key"] = key
    return result


async def confirm(client: AsyncClient, investigation_id: str, source_id: str) -> None:
    await client.post(
        f"/api/v1/financial-investigations/{investigation_id}/sources/{source_id}/analyze",
        headers=headers(key=f"recon-analyze-{source_id}"),
    )
    mappings = await client.get(
        f"/api/v1/financial-investigations/{investigation_id}/sources/{source_id}/mappings",
        headers=headers("ANALYST"),
    )
    assert mappings.status_code == 200
    for mapping in mappings.json():
        if mapping["required"]:
            edited = await client.patch(
                f"/api/v1/financial-investigations/{investigation_id}/sources/{source_id}/mappings/{mapping['id']}",
                headers=headers(key=f"recon-mapping-{mapping['id']}"),
                json={"canonical_field": mapping["canonical_field"], "ignored": False},
            )
            assert edited.status_code == 200
    confirmed = await client.post(
        f"/api/v1/financial-investigations/{investigation_id}/sources/{source_id}/mappings/confirm",
        headers=headers(key=f"recon-confirm-{source_id}"),
    )
    assert confirmed.status_code == 200


@pytest.mark.asyncio
async def test_reconciliation_run_uses_immutable_normalized_dataset_and_persists_results():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await client.post(
            "/api/v1/financial-investigations",
            headers=headers(key="recon-create"),
            json={
                "name": "Reconciliation run",
                "period_start": "2026-08-01",
                "period_end": "2026-08-31",
                "base_currency": "INR",
            },
        )
        investigation_id = created.json()["id"]
        orders = await client.post(
            f"/api/v1/financial-investigations/{investigation_id}/sources",
            headers=headers(key="recon-orders"),
            files={
                "file": (
                    "orders.csv",
                    b"Order ID,Amount,Status\nORD-1,100.00,COMPLETED\nORD-2,200.00,COMPLETED\n",
                    "text/csv",
                )
            },
        )
        payments = await client.post(
            f"/api/v1/financial-investigations/{investigation_id}/sources",
            headers=headers(key="recon-payments"),
            files={
                "file": (
                    "payments.csv",
                    b"Payment ID,Order ID,Amount,Status\nPAY-1,ORD-1,100.00,CAPTURED\nPAY-2,ORD-2,200.00,CAPTURED\n",
                    "text/csv",
                )
            },
        )
        await confirm(client, investigation_id, orders.json()["id"])
        await confirm(client, investigation_id, payments.json()["id"])
        normalized = await client.post(
            f"/api/v1/financial-investigations/{investigation_id}/dataset-versions/normalize",
            headers=headers(key="recon-normalize"),
        )
        assert normalized.status_code == 200
        assert normalized.json()["record_count"] == 4
        run = await client.post(
            f"/api/v1/financial-investigations/{investigation_id}/reconciliation-runs",
            headers=headers(key="recon-run"),
            json={},
        )
        assert run.status_code == 200, run.text
        assert run.json()["lifecycle_count"] == 2
        assert run.json()["exception_count"] == 2
        assert run.json()["open_exposure_minor"] == 30000
        detail = await client.get(
            f"/api/v1/financial-investigations/{investigation_id}", headers=headers("ANALYST")
        )
        assert detail.status_code == 200
        assert detail.json()["status"] == "RECONCILED"
        results = await client.get(
            f"/api/v1/financial-investigations/{investigation_id}/reconciliation-runs/{run.json()['id']}/results",
            headers=headers("ANALYST"),
        )
        assert results.status_code == 200
        assert results.json()[0]["exception_type"] == "MISSING_SETTLEMENT"
        patterns = await client.get(
            f"/api/v1/financial-investigations/{investigation_id}/patterns",
            headers=headers("ANALYST"),
        )
        assert patterns.status_code == 200
        assert patterns.json()[0]["occurrence_count"] == 2
        assert patterns.json()[0]["advisory"] is True
        investigation = await client.post(
            f"/api/v1/financial-investigations/{investigation_id}/reconciliation-runs/{run.json()['id']}/results/{results.json()[0]['id']}/investigate",
            headers=headers(key="recon-exception-investigation"),
        )
        assert investigation.status_code == 200
        assert investigation.json()["status"] == "UNRESOLVED"
        assert investigation.json()["requires_human_review"] is True
        retrieved = await client.get(
            f"/api/v1/financial-investigations/{investigation_id}/reconciliation-runs/{run.json()['id']}/results/{results.json()[0]['id']}/investigation",
            headers=headers("ANALYST"),
        )
        assert retrieved.status_code == 200
        assert retrieved.json()["investigation_id"] == investigation.json()["investigation_id"]
        replay = await client.post(
            f"/api/v1/financial-investigations/{investigation_id}/reconciliation-runs/{run.json()['id']}/results/{results.json()[0]['id']}/investigate",
            headers=headers(key="recon-exception-investigation-replay"),
        )
        assert replay.status_code == 200
        assert replay.json() == investigation.json()
        review = await client.post(
            f"/api/v1/financial-investigations/{investigation_id}/reconciliation-runs/{run.json()['id']}/results/{results.json()[0]['id']}/resolution-request",
            headers=headers(key="recon-review-request"),
            json={"action_code": "REQUEST_SETTLEMENT_REVIEW"},
        )
        assert review.status_code == 200
        assert review.json()["status"] == "PENDING_APPROVAL"
        approval = await client.post(
            f"/api/v1/approvals/{review.json()['request_id']}/approve",
            headers={**headers(key="recon-review-approval"), "X-Actor-Id": "independent-approver"},
        )
        assert approval.status_code == 200
        assert approval.json()["request_status"] == "APPROVED"
