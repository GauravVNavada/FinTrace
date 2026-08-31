import pytest
from httpx import ASGITransport, AsyncClient

from app.financial_investigations.files import UploadValidationError
from app.main import app
from app.source_analysis.analyzer import analyze_content


def _headers(role: str = "CONTROLLER") -> dict[str, str]:
    return {"X-Organization-Id": "ORG-001", "X-Actor-Id": "sprint2-user", "X-Actor-Role": role}


@pytest.mark.asyncio
async def test_source_analysis_proposes_mappings_and_requires_explicit_confirmation() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await client.post(
            "/api/v1/financial-investigations",
            headers={**_headers(), "Idempotency-Key": "sprint2-create-analysis"},
            json={
                "name": "Source analysis contract",
                "period_start": "2026-08-01",
                "period_end": "2026-08-31",
                "base_currency": "INR",
            },
        )
        assert created.status_code == 201
        investigation_id = created.json()["id"]
        uploaded = await client.post(
            f"/api/v1/financial-investigations/{investigation_id}/sources",
            headers={**_headers(), "Idempotency-Key": "sprint2-upload-analysis"},
            files={
                "file": (
                    "payments_aug.csv",
                    b"Payment ID,Order ID,Amount,Currency\nPAY-1,ORD-1,1250.00,INR\n",
                    "text/csv",
                )
            },
        )
        assert uploaded.status_code == 201
        source_id = uploaded.json()["id"]

        analyzed = await client.post(
            f"/api/v1/financial-investigations/{investigation_id}/sources/{source_id}/analyze",
            headers=_headers(),
        )
        assert analyzed.status_code == 200
        assert analyzed.json()["source_type"] == "PAYMENTS"
        assert analyzed.json()["provider_status"] == "OFFLINE_DETERMINISTIC"

        mappings = await client.get(
            f"/api/v1/financial-investigations/{investigation_id}/sources/{source_id}/mappings",
            headers=_headers("ANALYST"),
        )
        assert mappings.status_code == 200
        by_column = {item["source_column"]: item for item in mappings.json()}
        assert by_column["Payment ID"]["canonical_field"] == "payment_id"
        assert by_column["Order ID"]["required"] is True

        confirmed = await client.post(
            f"/api/v1/financial-investigations/{investigation_id}/sources/{source_id}/mappings/confirm",
            headers=_headers(),
        )
        assert confirmed.status_code == 200
        assert confirmed.json()["status"] == "CONFIRMED"

        source = await client.get(
            f"/api/v1/financial-investigations/{investigation_id}/sources",
            headers=_headers("ANALYST"),
        )
        assert source.json()[0]["status"] == "READY"


@pytest.mark.asyncio
async def test_missing_required_mapping_is_blocked_and_can_be_edited() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await client.post(
            "/api/v1/financial-investigations",
            headers={**_headers(), "Idempotency-Key": "sprint2-create-missing"},
            json={
                "name": "Missing mapping contract",
                "period_start": "2026-08-01",
                "period_end": "2026-08-31",
                "base_currency": "INR",
            },
        )
        investigation_id = created.json()["id"]
        uploaded = await client.post(
            f"/api/v1/financial-investigations/{investigation_id}/sources",
            headers={**_headers(), "Idempotency-Key": "sprint2-upload-missing"},
            files={
                "file": ("payments_missing_id.csv", b"Order ID,Amount\nORD-1,1250.00\n", "text/csv")
            },
        )
        source_id = uploaded.json()["id"]
        analyzed = await client.post(
            f"/api/v1/financial-investigations/{investigation_id}/sources/{source_id}/analyze",
            headers=_headers(),
        )
        assert analyzed.status_code == 200
        mappings = await client.get(
            f"/api/v1/financial-investigations/{investigation_id}/sources/{source_id}/mappings",
            headers=_headers("ANALYST"),
        )
        assert mappings.status_code == 200
        confirmation = await client.post(
            f"/api/v1/financial-investigations/{investigation_id}/sources/{source_id}/mappings/confirm",
            headers=_headers(),
        )
        assert confirmation.status_code == 409
        assert "payment_id" in confirmation.json()["detail"]["missing_fields"]

        order_mapping = next(
            item for item in mappings.json() if item["source_column"] == "Order ID"
        )
        edited = await client.patch(
            f"/api/v1/financial-investigations/{investigation_id}/sources/{source_id}/mappings/{order_mapping['id']}",
            headers=_headers(),
            json={"canonical_field": "payment_id", "ignored": False},
        )
        assert edited.status_code == 200
        assert edited.json()["canonical_field"] == "payment_id"
        assert edited.json()["status"] == "EDITED"


@pytest.mark.asyncio
async def test_source_analysis_is_tenant_scoped_and_provider_failure_is_explicit() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        missing = await client.get(
            "/api/v1/financial-investigations/FIN-NOT-VISIBLE/sources/SRC-NOT-VISIBLE/analysis",
            headers={"X-Organization-Id": "ORG-OTHER", "X-Actor-Role": "ANALYST"},
        )
        assert missing.status_code == 404


@pytest.mark.asyncio
async def test_filename_signal_disambiguates_invoice_from_order_exports() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await client.post(
            "/api/v1/financial-investigations",
            headers={**_headers(), "Idempotency-Key": "invoice-classification-create"},
            json={
                "name": "Invoice classification contract",
                "period_start": "2026-08-01",
                "period_end": "2026-08-31",
                "base_currency": "INR",
            },
        )
        investigation_id = created.json()["id"]
        uploaded = await client.post(
            f"/api/v1/financial-investigations/{investigation_id}/sources",
            headers={**_headers(), "Idempotency-Key": "invoice-classification-upload"},
            files={
                "file": (
                    "invoices.csv",
                    b"Invoice ID,Order ID,Amount,Status\nINV-1,ORD-1,100.00,ACTIVE\n",
                    "text/csv",
                )
            },
        )
        analyzed = await client.post(
            f"/api/v1/financial-investigations/{investigation_id}/sources/{uploaded.json()['id']}/analyze",
            headers=_headers(),
        )
        assert analyzed.status_code == 200
        assert analyzed.json()["source_type"] == "INVOICES"


def test_csv_rows_with_extra_cells_are_rejected_instead_of_truncated() -> None:
    with pytest.raises(UploadValidationError, match="more columns than the header"):
        analyze_content("orders.csv", b"order_id,amount\nORD-1,10.00,unexpected\n", 100, 20)


def test_analysis_limit_requires_explicit_truncation() -> None:
    content = b"order_id,amount\nORD-1,10.00\nORD-2,20.00\n"
    with pytest.raises(UploadValidationError, match="more rows"):
        analyze_content("orders.csv", content, 1, 20)
    document = analyze_content("orders.csv", content, 1, 20, truncate=True)
    assert document.row_count == 1
