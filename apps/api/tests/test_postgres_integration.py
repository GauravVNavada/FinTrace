import os
from uuid import uuid4

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
        assert exceptions.status_code == 200 and exceptions.json()
        exception_id = exceptions.json()[0]["id"]
        investigation = await client.post(
            f"/api/v1/exceptions/{exception_id}/investigations",
            headers={
                **headers,
                "Idempotency-Key": f"postgres-integration-investigation-{uuid4().hex}",
            },
        )
        assert investigation.status_code == 200, investigation.text
        loaded = await client.get(
            f"/api/v1/investigations/{investigation.json()['investigation_id']}", headers=headers
        )

    assert ready.json() == {"status": "ready", "storage_backend": "postgres"}
    assert summary.json()["lifecycle_count"] >= 1
    assert len(exceptions.json()) >= 1
    assert investigation.status_code == 200
    assert loaded.json()["investigation_id"] == investigation.json()["investigation_id"]


@pytest.mark.asyncio
async def test_postgres_financial_investigation_source_slice() -> None:
    from app.main import app

    suffix = uuid4().hex[:10]
    headers = {
        "X-Organization-Id": "ORG-001",
        "X-Actor-Id": "integration-controller",
        "X-Actor-Role": "CONTROLLER",
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await client.post(
            "/api/v1/financial-investigations",
            headers={**headers, "Idempotency-Key": f"postgres-create-{suffix}"},
            json={
                "name": f"Postgres source slice {suffix}",
                "period_start": "2026-08-01",
                "period_end": "2026-08-31",
                "base_currency": "INR",
            },
        )
        assert created.status_code == 201
        investigation_id = created.json()["id"]
        uploaded = await client.post(
            f"/api/v1/financial-investigations/{investigation_id}/sources",
            headers={**headers, "Idempotency-Key": f"postgres-upload-{suffix}"},
            files={"file": ("orders.csv", b"order_id,amount\nORD-1,100.00\n", "text/csv")},
        )
        assert uploaded.status_code == 201
        assert uploaded.json()["row_count"] == 1
        source_id = uploaded.json()["id"]
        refreshed = await client.get(
            f"/api/v1/financial-investigations/{investigation_id}", headers=headers
        )
        assert refreshed.json()["status"] == "SOURCES_UPLOADED"
        assert refreshed.json()["source_file_count"] == 1
        deleted = await client.delete(
            f"/api/v1/financial-investigations/{investigation_id}/sources/{source_id}",
            headers=headers,
        )
        assert deleted.status_code == 204


@pytest.mark.asyncio
async def test_postgres_reconciliation_and_uploaded_investigation_slice() -> None:
    from app.main import app

    suffix = uuid4().hex[:10]
    headers = {
        "X-Organization-Id": "ORG-001",
        "X-Actor-Id": "integration-controller",
        "X-Actor-Role": "CONTROLLER",
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await client.post(
            "/api/v1/financial-investigations",
            headers={**headers, "Idempotency-Key": f"postgres-recon-create-{suffix}"},
            json={
                "name": f"Postgres reconciliation {suffix}",
                "period_start": "2026-08-01",
                "period_end": "2026-08-31",
                "base_currency": "INR",
            },
        )
        investigation_id = created.json()["id"]
        source_ids: list[str] = []
        for filename, content, key in (
            ("orders.csv", b"Order ID,Amount,Status\nORD-PG-1,100.00,COMPLETED\n", "orders"),
            (
                "payments.csv",
                b"Payment ID,Order ID,Amount,Status\nPAY-PG-1,ORD-PG-1,100.00,CAPTURED\n",
                "payments",
            ),
        ):
            uploaded = await client.post(
                f"/api/v1/financial-investigations/{investigation_id}/sources",
                headers={**headers, "Idempotency-Key": f"postgres-recon-upload-{key}-{suffix}"},
                files={"file": (filename, content, "text/csv")},
            )
            assert uploaded.status_code == 201
            source_id = uploaded.json()["id"]
            source_ids.append(source_id)
            assert (
                await client.post(
                    f"/api/v1/financial-investigations/{investigation_id}/sources/{source_id}/analyze",
                    headers=headers,
                )
            ).status_code == 200
            mappings = await client.get(
                f"/api/v1/financial-investigations/{investigation_id}/sources/{source_id}/mappings",
                headers=headers,
            )
            for mapping in mappings.json():
                if mapping["required"]:
                    assert (
                        await client.patch(
                            f"/api/v1/financial-investigations/{investigation_id}/sources/{source_id}/mappings/{mapping['id']}",
                            headers=headers,
                            json={"canonical_field": mapping["canonical_field"], "ignored": False},
                        )
                    ).status_code == 200
            assert (
                await client.post(
                    f"/api/v1/financial-investigations/{investigation_id}/sources/{source_id}/mappings/confirm",
                    headers=headers,
                )
            ).status_code == 200
        normalized = await client.post(
            f"/api/v1/financial-investigations/{investigation_id}/dataset-versions/normalize",
            headers={**headers, "Idempotency-Key": f"postgres-recon-normalize-{suffix}"},
        )
        assert normalized.status_code == 200
        run = await client.post(
            f"/api/v1/financial-investigations/{investigation_id}/reconciliation-runs",
            headers={**headers, "Idempotency-Key": f"postgres-recon-run-{suffix}"},
            json={},
        )
        assert run.status_code == 200
        results = await client.get(
            f"/api/v1/financial-investigations/{investigation_id}/reconciliation-runs/{run.json()['id']}/results",
            headers=headers,
        )
        assert (
            results.status_code == 200
            and results.json()[0]["exception_type"] == "MISSING_SETTLEMENT"
        )
        review = await client.post(
            f"/api/v1/financial-investigations/{investigation_id}/reconciliation-runs/{run.json()['id']}/results/{results.json()[0]['id']}/resolution-request",
            headers={**headers, "Idempotency-Key": f"postgres-review-{suffix}"},
            json={"action_code": "REQUEST_SETTLEMENT_REVIEW"},
        )
        assert review.status_code == 200, review.text
        approval = await client.post(
            f"/api/v1/approvals/{review.json()['request_id']}/approve",
            headers={**headers, "Idempotency-Key": f"postgres-approval-{suffix}"},
        )
        assert approval.status_code == 200, approval.text
        investigated = await client.post(
            f"/api/v1/financial-investigations/{investigation_id}/reconciliation-runs/{run.json()['id']}/results/{results.json()[0]['id']}/investigate",
            headers={**headers, "Idempotency-Key": f"postgres-recon-investigate-{suffix}"},
        )
        assert investigated.status_code == 200
        assert investigated.json()["status"] == "UNRESOLVED"
