from io import BytesIO

import pytest
from httpx import ASGITransport, AsyncClient
from openpyxl import Workbook

from app.main import app
from app.repositories.factory import get_demo_repository


def _headers(role: str = "CONTROLLER", key: str = "test-financial-investigation") -> dict[str, str]:
    return {
        "X-Organization-Id": "ORG-001",
        "X-Actor-Id": "sprint1-user",
        "X-Actor-Role": role,
        "Idempotency-Key": key,
    }


@pytest.mark.asyncio
async def test_financial_investigation_upload_persists_metadata_and_audit() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await client.post(
            "/api/v1/financial-investigations",
            headers=_headers(key="create-sprint1-upload"),
            json={
                "name": "August Revenue Integrity Review",
                "description": "Sprint 1 upload contract",
                "period_start": "2026-08-01",
                "period_end": "2026-08-31",
                "base_currency": "inr",
            },
        )
        assert created.status_code == 201
        investigation_id = created.json()["id"]
        assert created.json()["status"] == "DRAFT"
        assert created.json()["base_currency"] == "INR"

        csv_content = (
            b"Receipt No,Store Code,Final Total\nORD-1,BLR-01,1250.00\nORD-2,BLR-02,900.00\n"
        )
        upload_headers = _headers(key="upload-sprint1-csv")
        upload = await client.post(
            f"/api/v1/financial-investigations/{investigation_id}/sources",
            headers=upload_headers,
            files={"file": ("sales_aug.csv", csv_content, "text/csv")},
        )
        assert upload.status_code == 201
        assert upload.json()["original_filename"] == "sales_aug.csv"
        assert upload.json()["row_count"] == 2
        assert upload.json()["column_count"] == 3
        source_id = upload.json()["id"]

        replay = await client.post(
            f"/api/v1/financial-investigations/{investigation_id}/sources",
            headers=upload_headers,
            files={"file": ("sales_aug.csv", csv_content, "text/csv")},
        )
        assert replay.status_code == 201
        assert replay.json()["id"] == source_id

        replacement_content = (
            b"Receipt No,Store Code,Final Total\nORD-1,BLR-01,1250.00\nORD-2,BLR-02,901.00\n"
        )
        replacement = await client.post(
            f"/api/v1/financial-investigations/{investigation_id}/sources",
            headers=_headers(key="upload-sprint1-csv-new-key"),
            files={"file": ("sales_aug.csv", replacement_content, "text/csv")},
        )
        assert replacement.status_code == 201
        replacement_id = replacement.json()["id"]
        assert replacement_id != source_id
        assert replacement.json()["deduplicated"] is False

        get_demo_repository()._source_files[("ORG-001", replacement_id)]["status"] = "READY"
        reupload = await client.post(
            f"/api/v1/financial-investigations/{investigation_id}/sources",
            headers=_headers(key="upload-sprint1-csv-ready-new-key"),
            files={"file": ("renamed_sales_aug.csv", replacement_content, "text/csv")},
        )
        assert reupload.status_code == 201
        assert reupload.json()["id"] == replacement_id
        assert reupload.json()["deduplicated"] is True

        refreshed = await client.get(
            f"/api/v1/financial-investigations/{investigation_id}",
            headers={"X-Organization-Id": "ORG-001", "X-Actor-Role": "ANALYST"},
        )
        assert refreshed.status_code == 200
        assert refreshed.json()["source_file_count"] == 1
        assert refreshed.json()["status"] == "SOURCES_UPLOADED"
        sources = await client.get(
            f"/api/v1/financial-investigations/{investigation_id}/sources",
            headers={"X-Organization-Id": "ORG-001", "X-Actor-Role": "ANALYST"},
        )
        assert sources.status_code == 200
        assert [item["id"] for item in sources.json()] == [replacement_id]

        audit = await client.get(
            "/api/v1/audit-events",
            headers={"X-Organization-Id": "ORG-001", "X-Actor-Role": "CONTROLLER"},
        )
        assert audit.status_code == 200
        assert {event["action"] for event in audit.json()} >= {
            "FINANCIAL_INVESTIGATION_CREATED",
            "SOURCE_FILE_UPLOADED",
        }

        deleted = await client.delete(
            f"/api/v1/financial-investigations/{investigation_id}/sources/{replacement_id}",
            headers={"X-Organization-Id": "ORG-001", "X-Actor-Role": "CONTROLLER", "Idempotency-Key": "delete-sprint1-upload"},
        )
        assert deleted.status_code == 204
        after_delete = await client.get(
            f"/api/v1/financial-investigations/{investigation_id}",
            headers={"X-Organization-Id": "ORG-001", "X-Actor-Role": "ANALYST"},
        )
        assert after_delete.json()["source_file_count"] == 0
        assert after_delete.json()["status"] == "DRAFT"
        audit_after_delete = await client.get(
            "/api/v1/audit-events",
            headers={"X-Organization-Id": "ORG-001", "X-Actor-Role": "CONTROLLER"},
        )
        assert "SOURCE_FILE_DELETED" in {event["action"] for event in audit_after_delete.json()}


@pytest.mark.asyncio
async def test_source_delete_requires_idempotency_key() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.delete(
            "/api/v1/financial-investigations/FIN-NOT-REAL/sources/SRC-NOT-REAL",
            headers={"X-Organization-Id": "ORG-001", "X-Actor-Role": "CONTROLLER"},
        )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "INVALID_REQUEST"


@pytest.mark.asyncio
async def test_financial_investigation_upload_supports_xlsx_and_rejects_unsafe_files() -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["Order ID", "Amount"])
    sheet.append(["ORD-1", 100])
    output = BytesIO()
    workbook.save(output)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await client.post(
            "/api/v1/financial-investigations",
            headers=_headers(key="create-sprint1-xlsx"),
            json={
                "name": "XLSX Validation Review",
                "period_start": "2026-08-01",
                "period_end": "2026-08-31",
                "base_currency": "INR",
            },
        )
        investigation_id = created.json()["id"]
        xlsx = await client.post(
            f"/api/v1/financial-investigations/{investigation_id}/sources",
            headers=_headers(key="upload-sprint1-xlsx"),
            files={"file": ("orders.xlsx", output.getvalue(), "application/octet-stream")},
        )
        assert xlsx.status_code == 201
        assert xlsx.json()["row_count"] == 1
        assert xlsx.json()["column_count"] == 2

        unsafe = await client.post(
            f"/api/v1/financial-investigations/{investigation_id}/sources",
            headers=_headers(key="upload-sprint1-unsafe"),
            files={"file": ("orders.xls", b"not allowed", "application/octet-stream")},
        )
        assert unsafe.status_code == 422


@pytest.mark.asyncio
async def test_financial_investigation_is_tenant_scoped_and_cors_enabled() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        forbidden = await client.get(
            "/api/v1/financial-investigations",
            headers={"X-Organization-Id": "ORG-OTHER", "X-Actor-Role": "ANALYST"},
        )
        assert forbidden.status_code == 200
        assert forbidden.json() == []
        preflight = await client.options(
            "/api/v1/financial-investigations",
            headers={
                "Origin": "http://127.0.0.1:3002",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type,idempotency-key,x-organization-id,x-actor-id,x-actor-role",
            },
        )
        assert preflight.status_code == 200
        assert preflight.headers["access-control-allow-origin"] == "http://127.0.0.1:3002"


@pytest.mark.asyncio
async def test_demo_data_generation_uses_upload_pipeline_and_is_idempotent() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await client.post(
            "/api/v1/financial-investigations",
            headers=_headers(key="demo-data-create"),
            json={
                "name": "Fresh synthetic demo review",
                "period_start": "2026-08-01",
                "period_end": "2026-08-31",
                "base_currency": "INR",
            },
        )
        assert created.status_code == 201
        investigation_id = created.json()["id"]

        request = {
            "orders": 6,
            "seed": 7,
            "anomaly_rate": 0,
            "scenario_types": ["MISSING_SETTLEMENT"],
        }
        generation_headers = _headers(key="demo-data-generate")
        generated = await client.post(
            f"/api/v1/financial-investigations/{investigation_id}/demo-data",
            headers=generation_headers,
            json=request,
        )
        assert generated.status_code == 201, generated.text
        assert generated.json()["orders"] == 6
        assert generated.json()["scenario_types"] == ["MISSING_SETTLEMENT"]
        assert {source["original_filename"] for source in generated.json()["sources"]} == {
            "orders.csv",
            "payments.csv",
            "settlements.csv",
            "invoices.csv",
            "inventory_movements.csv",
            "employee_actions.csv",
        }

        replay = await client.post(
            f"/api/v1/financial-investigations/{investigation_id}/demo-data",
            headers=generation_headers,
            json=request,
        )
        assert replay.status_code == 201
        assert replay.json() == generated.json()

        conflict = await client.post(
            f"/api/v1/financial-investigations/{investigation_id}/demo-data",
            headers=generation_headers,
            json={**request, "seed": 8},
        )
        assert conflict.status_code == 409

        sources = await client.get(
            f"/api/v1/financial-investigations/{investigation_id}/sources",
            headers={"X-Organization-Id": "ORG-001", "X-Actor-Role": "ANALYST"},
        )
        assert sources.status_code == 200
        assert len(sources.json()) == 6
        audit = await client.get(
            "/api/v1/audit-events",
            headers={"X-Organization-Id": "ORG-001", "X-Actor-Role": "CONTROLLER"},
        )
        assert "DEMO_DATA_GENERATED" in {event["action"] for event in audit.json()}
