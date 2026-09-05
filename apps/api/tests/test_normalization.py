from io import BytesIO
from uuid import uuid4

import openpyxl
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.normalization.service import _primary_source_record_id


def headers(role="CONTROLLER", key=None):
    result = {"X-Organization-Id": "ORG-NORM", "X-Actor-Id": "normalizer", "X-Actor-Role": role}
    if key:
        result["Idempotency-Key"] = key
    return result


async def _prepare_source(client, filename: str, content: bytes, prefix: str) -> tuple[str, str]:
    investigation = await client.post(
        "/api/v1/financial-investigations",
        headers=headers(key=f"{prefix}-create-{uuid4().hex}"),
        json={
            "name": f"{prefix} normalization",
            "period_start": "2026-08-01",
            "period_end": "2026-08-31",
            "base_currency": "INR",
        },
    )
    assert investigation.status_code == 201
    investigation_id = investigation.json()["id"]
    upload = await client.post(
        f"/api/v1/financial-investigations/{investigation_id}/sources",
        headers=headers(key=f"{prefix}-upload-{uuid4().hex}"),
        files={"file": (filename, content, "text/csv")},
    )
    assert upload.status_code == 201
    source_id = upload.json()["id"]
    analyzed = await client.post(
        f"/api/v1/financial-investigations/{investigation_id}/sources/{source_id}/analyze",
        headers=headers(key=f"{prefix}-analyze-{uuid4().hex}"),
    )
    assert analyzed.status_code == 200
    mappings = await client.get(
        f"/api/v1/financial-investigations/{investigation_id}/sources/{source_id}/mappings",
        headers=headers("ANALYST"),
    )
    assert mappings.status_code == 200
    for mapping in mappings.json():
        if mapping["required"]:
            edited = await client.patch(
                f"/api/v1/financial-investigations/{investigation_id}/sources/{source_id}/mappings/{mapping['id']}",
                headers=headers(key=f"{prefix}-mapping-{uuid4().hex}"),
                json={
                    "canonical_field": mapping["canonical_field"],
                    "ignored": False,
                },
            )
            assert edited.status_code == 200
    confirmed = await client.post(
        f"/api/v1/financial-investigations/{investigation_id}/sources/{source_id}/mappings/confirm",
        headers=headers(key=f"{prefix}-confirm-{uuid4().hex}"),
    )
    assert confirmed.status_code == 200
    return investigation_id, source_id


@pytest.mark.parametrize(
    ("source_type", "expected_id"),
    [
        ("ORDERS", "ORD-1"),
        ("PAYMENTS", "PAY-1"),
        ("SETTLEMENTS", "SET-1"),
        ("REFUNDS", "REF-1"),
        ("INVOICES", "INV-1"),
        ("INVENTORY_MOVEMENTS", "MOV-1"),
        ("EMPLOYEE_ACTIONS", "ACT-1"),
    ],
)
def test_primary_source_record_id_is_source_type_specific(source_type, expected_id):
    values = {
        "order_id": "ORD-1",
        "payment_id": "PAY-1",
        "settlement_id": "SET-1",
        "refund_id": "REF-1",
        "invoice_id": "INV-1",
        "movement_id": "MOV-1",
        "action_id": "ACT-1",
    }
    assert _primary_source_record_id(source_type, values) == expected_id


@pytest.mark.asyncio
async def test_payments_allow_multiple_rows_per_order_and_preserve_primary_lineage():
    payment_csv = (
        b"Payment ID,Order ID,Amount,Status\n"
        b"PAY-1,ORD-1,100.00,CAPTURED\n"
        b"PAY-2,ORD-1,50.00,CAPTURED\n"
        b"PAY-3,ORD-2,75.00,CAPTURED\n"
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        investigation_id, source_id = await _prepare_source(
            client, "payments.csv", payment_csv, "payment-primary"
        )
        normalized = await client.post(
            f"/api/v1/financial-investigations/{investigation_id}/dataset-versions/normalize",
            headers=headers(key=f"payment-primary-normalize-{uuid4().hex}"),
        )
        assert normalized.status_code == 200, normalized.text
        records = await client.get(
            f"/api/v1/financial-investigations/{investigation_id}/dataset-versions/{normalized.json()['id']}/records",
            headers=headers("ANALYST"),
        )
        assert records.status_code == 200
        assert [record["source_record_id"] for record in records.json()] == [
            "PAY-1",
            "PAY-2",
            "PAY-3",
        ]
        assert records.json()[1]["lineage"]["payment_id"] == {
            "source_file_id": source_id,
            "source_row_number": 3,
            "source_column": "Payment ID",
            "source_record_id": "PAY-2",
        }


@pytest.mark.asyncio
async def test_payments_reject_duplicate_payment_id_even_when_orders_differ():
    payment_csv = (
        b"Payment ID,Order ID,Amount,Status\n"
        b"PAY-1,ORD-1,100.00,CAPTURED\n"
        b"PAY-1,ORD-2,50.00,CAPTURED\n"
    )
    async with AsyncClient(transport=ASGITransport(app), base_url="http://test") as client:
        investigation_id, _ = await _prepare_source(
            client, "payments_duplicate.csv", payment_csv, "payment-duplicate"
        )
        normalized = await client.post(
            f"/api/v1/financial-investigations/{investigation_id}/dataset-versions/normalize",
            headers=headers(key=f"payment-duplicate-normalize-{uuid4().hex}"),
        )
        assert normalized.status_code == 409
        assert "duplicate source record ID PAY-1" in normalized.json()["detail"]["message"]


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
            headers=headers(key="norm-analyze"),
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
                    headers=headers(key=f"norm-mapping-{mapping['id']}"),
                    json={"canonical_field": mapping["canonical_field"], "ignored": False},
                )
        assert (
            await client.post(
                f"/api/v1/financial-investigations/{investigation_id}/sources/{source_id}/mappings/confirm",
                headers=headers(key="norm-confirm"),
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


@pytest.mark.asyncio
async def test_normalization_converts_inventory_valuation_to_minor_units():
    inventory_csv = (
        b"MovementRef,ReceiptNo,Movement,Units,SKU,UnitCost,InventoryValue,OccurredAt\n"
        b"MOV-1,ORD-1,SALE,2,SKU-1,24.00,48.00,2026-08-01T08:00:00+00:00\n"
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        investigation_id, _ = await _prepare_source(
            client, "inventory.csv", inventory_csv, "inventory-valuation"
        )
        normalized = await client.post(
            f"/api/v1/financial-investigations/{investigation_id}/dataset-versions/normalize",
            headers=headers(key=f"inventory-valuation-normalize-{uuid4().hex}"),
        )
        assert normalized.status_code == 200, normalized.text
        records = await client.get(
            f"/api/v1/financial-investigations/{investigation_id}/dataset-versions/{normalized.json()['id']}/records",
            headers=headers("ANALYST"),
        )
        values = records.json()[0]["values"]
        assert values["unit_cost_minor"] == 2400
        assert values["inventory_value_minor"] == 4800


@pytest.mark.asyncio
async def test_normalization_converts_excel_serial_vendor_payment_timestamps():
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.append(["PaymentRef", "OrderRef", "AmountPaid", "PaidAt", "Status"])
    sheet.append(["PAY-1", "ORD-1", 100.00, 46058.51736111111, "CAPTURED"])
    output = BytesIO()
    workbook.save(output)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        investigation_id, _ = await _prepare_source(
            client, "PaymentGateway_Feb.xlsx", output.getvalue(), "excel-payment-timestamp"
        )
        normalized = await client.post(
            f"/api/v1/financial-investigations/{investigation_id}/dataset-versions/normalize",
            headers=headers(key=f"excel-payment-timestamp-normalize-{uuid4().hex}"),
        )

        assert normalized.status_code == 200, normalized.text
        records = await client.get(
            f"/api/v1/financial-investigations/{investigation_id}/dataset-versions/{normalized.json()['id']}/records",
            headers=headers("ANALYST"),
        )
        assert records.status_code == 200
        assert records.json()[0]["values"]["captured_at"].startswith("2026-")
        assert records.json()[0]["values"]["captured_at"].endswith("+00:00")
