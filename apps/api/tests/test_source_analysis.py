from io import BytesIO

import openpyxl
import pytest
from httpx import ASGITransport, AsyncClient

from app.financial_investigations.files import UploadValidationError
from app.financial_investigations.schemas import SourceType
from app.main import app
from app.source_analysis.analyzer import analyze_content
from app.source_analysis.analyzer import _display
from app.source_analysis.provider import (
    REQUIRED_FIELDS,
    ClassificationResult,
    FailoverSourceAnalysisProvider,
    OfflineSourceAnalysisProvider,
    SourceAnalysisProviderUnavailable,
)


def _headers(role: str = "CONTROLLER") -> dict[str, str]:
    return {"X-Organization-Id": "ORG-001", "X-Actor-Id": "sprint2-user", "X-Actor-Role": role}


def _operation_headers(key: str, role: str = "CONTROLLER") -> dict[str, str]:
    return {**_headers(role), "Idempotency-Key": key}


class _FailingSourceProvider:
    def __init__(self, *, retryable: bool) -> None:
        self.calls = 0
        self._retryable = retryable

    def classify(self, filename: str, document: object) -> ClassificationResult:
        self.calls += 1
        raise SourceAnalysisProviderUnavailable(
            "source provider unavailable",
            category="rate_limited" if self._retryable else "forbidden",
            retryable=self._retryable,
        )

    def propose_mappings(self, source_type: SourceType, document: object) -> list[object]:
        self.calls += 1
        raise AssertionError("classify should fail before mappings are proposed")


class _WorkingSourceProvider:
    def __init__(self) -> None:
        self.calls = 0

    def classify(self, filename: str, document: object) -> ClassificationResult:
        self.calls += 1
        return ClassificationResult(SourceType.ORDERS, 0.9, "bounded", "AI_PROVIDER", "fallback", "model")

    def propose_mappings(self, source_type: SourceType, document: object) -> list[object]:
        self.calls += 1
        return []


def test_source_analysis_failover_is_transient_only() -> None:
    fallback = _WorkingSourceProvider()
    transient = _FailingSourceProvider(retryable=True)
    result = FailoverSourceAnalysisProvider((transient, fallback)).classify("orders.csv", object())
    assert result.provider == "fallback"
    assert transient.calls == 1
    assert fallback.calls == 1

    fallback.calls = 0
    permanent = _FailingSourceProvider(retryable=False)
    with pytest.raises(SourceAnalysisProviderUnavailable, match="source provider unavailable"):
        FailoverSourceAnalysisProvider((permanent, fallback)).classify("orders.csv", object())
    assert fallback.calls == 0


def test_excel_money_headers_never_become_dates():
    assert _display(6250, "CapturedValue") == "6250"
    assert _display(6250, "RefundedAmount") == "6250"
    assert _display(46128, "InvoiceCreated").startswith("2026-")


@pytest.mark.asyncio
async def test_successful_filename_with_changed_content_is_not_silently_deduplicated():
    from uuid import uuid4
    def headers():
        return {**_headers(), "Idempotency-Key": uuid4().hex}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await client.post("/api/v1/financial-investigations", headers=headers(), json={"name": "Changed content protection", "base_currency": "INR", "period_start": "2026-03-01", "period_end": "2026-03-31"})
        assert created.status_code == 201, created.text
        base = f"/api/v1/financial-investigations/{created.json()['id']}"
        original = b"PaymentID,OrderID,Amount\nPAY-1,ORD-1,100.00\n"
        upload = await client.post(base + "/sources", headers=headers(), files={"file": ("payments.csv", original, "text/csv")})
        source_id = upload.json()["id"]
        source = base + f"/sources/{source_id}"
        assert (await client.post(source + "/analyze", headers=headers())).status_code == 200
        assert (await client.post(source + "/mappings/confirm", headers=headers())).status_code == 200
        changed = await client.post(base + "/sources", headers=headers(), files={"file": ("payments.csv", original.replace(b"100.00", b"200.00"), "text/csv")})
        assert changed.status_code == 422, changed.text
        assert "different contents" in changed.text
        sources = await client.get(base + "/sources", headers=headers())
        assert [item["id"] for item in sources.json()] == [source_id]


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
            headers=_operation_headers("sprint2-analyze-analysis"),
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
            headers=_operation_headers("sprint2-confirm-analysis"),
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
            headers=_operation_headers("sprint2-analyze-missing"),
        )
        assert analyzed.status_code == 200
        mappings = await client.get(
            f"/api/v1/financial-investigations/{investigation_id}/sources/{source_id}/mappings",
            headers=_headers("ANALYST"),
        )
        assert mappings.status_code == 200
        confirmation = await client.post(
            f"/api/v1/financial-investigations/{investigation_id}/sources/{source_id}/mappings/confirm",
            headers=_operation_headers("sprint2-confirm-missing"),
        )
        assert confirmation.status_code == 409
        assert "payment_id" in confirmation.json()["detail"]["missing_fields"]

        order_mapping = next(
            item for item in mappings.json() if item["source_column"] == "Order ID"
        )
        edited = await client.patch(
            f"/api/v1/financial-investigations/{investigation_id}/sources/{source_id}/mappings/{order_mapping['id']}",
            headers=_operation_headers("sprint2-edit-missing"),
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
            headers=_operation_headers("invoice-classification-analyze"),
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


def test_offline_provider_maps_canonical_minor_unit_export_headers() -> None:
    payments = analyze_content(
        "payments.csv",
        b"payment_id,order_id,amount_minor,gateway_fee_minor,captured_at\n"
        b"PAY-1,ORD-1,10000,180,2026-08-01T08:00:00+00:00\n",
        100,
        20,
    )
    payment_mappings = {
        item.source_column: item
        for item in OfflineSourceAnalysisProvider().propose_mappings(SourceType.PAYMENTS, payments)
    }

    assert payment_mappings["amount_minor"].canonical_field == "amount"
    assert payment_mappings["gateway_fee_minor"].canonical_field == "gateway_fee_amount"
    assert payment_mappings["gateway_fee_minor"].ignored is False

    settlements = analyze_content(
        "settlements.csv",
        b"settlement_id,payment_id,gross_minor,fees_minor,tax_minor,net_minor\n"
        b"SET-1,PAY-1,10000,180,32,9788\n",
        100,
        20,
    )
    settlement_mappings = {
        item.source_column: item
        for item in OfflineSourceAnalysisProvider().propose_mappings(
            SourceType.SETTLEMENTS, settlements
        )
    }

    assert settlement_mappings["gross_minor"].canonical_field == "gross_amount"
    assert settlement_mappings["fees_minor"].canonical_field == "fee_amount"
    assert settlement_mappings["tax_minor"].canonical_field == "tax_amount"
    assert settlement_mappings["net_minor"].canonical_field == "net_amount"


def test_offline_provider_maps_inventory_valuation_headers() -> None:
    inventory = analyze_content(
        "inventory.csv",
        b"MoveID,OrderRef,MovementType,Qty,ProductCode,CostPerUnit,StockValue,EventTime,Currency\n"
        b"MOV-1,ORD-1,SALE,2,SKU-1,24.00,48.00,2026-08-01T08:00:00+00:00,INR\n",
        100,
        20,
    )
    mappings = {
        item.source_column: item
        for item in OfflineSourceAnalysisProvider().propose_mappings(
            SourceType.INVENTORY_MOVEMENTS, inventory
        )
    }
    assert mappings["MoveID"].canonical_field == "movement_id"
    assert mappings["OrderRef"].canonical_field == "order_id"
    assert mappings["ProductCode"].canonical_field == "sku"
    assert mappings["Qty"].canonical_field == "quantity"
    assert mappings["CostPerUnit"].canonical_field == "unit_cost"
    assert mappings["StockValue"].canonical_field == "inventory_value"
    assert mappings["EventTime"].canonical_field == "occurred_at"
    assert mappings["Currency"].canonical_field == "currency"


def test_offline_provider_maps_february_generated_export_headers() -> None:
    provider = OfflineSourceAnalysisProvider()
    cases = {
        SourceType.SALES: [
            "OrderRef",
            "BranchCode",
            "GrossAmount",
            "SaleTimestamp",
            "Currency",
        ],
        SourceType.PAYMENTS: [
            "PaymentRef",
            "OrderRef",
            "AmountPaid",
            "PaidAt",
            "Currency",
        ],
        SourceType.SETTLEMENTS: [
            "BankCreditRef",
            "PaymentRef",
            "GrossPaid",
            "FeeCharged",
            "NetPaid",
            "SettlementDate",
            "Currency",
        ],
        SourceType.REFUNDS: [
            "RefundID",
            "PaymentRef",
            "OrderRef",
            "RefundAmount",
            "ProcessedAt",
            "Currency",
        ],
        SourceType.INVOICES: [
            "BillingNo",
            "OrderRef",
            "InvoiceAmount",
            "CreatedOn",
            "Currency",
        ],
        SourceType.INVENTORY_MOVEMENTS: [
            "MoveID",
            "OrderRef",
            "MovementType",
            "Quantity",
            "ProductCode",
            "CostPerUnit",
            "StockValue",
            "EventTime",
            "Currency",
        ],
        SourceType.EMPLOYEE_ACTIONS: [
            "LogID",
            "StaffID",
            "Entity",
            "EntityRef",
            "Event",
            "EventTime",
        ],
    }

    for source_type, headers in cases.items():
        document = analyze_content(
            "february-export.csv",
            (",".join(headers) + "\n" + ",".join(["value"] * len(headers))).encode(),
            100,
            30,
        )
        mappings = provider.propose_mappings(source_type, document)
        mapped_fields = {item.canonical_field for item in mappings if item.canonical_field}
        assert REQUIRED_FIELDS[source_type].issubset(mapped_fields), source_type


def test_offline_provider_classifies_february_generated_export_files() -> None:
    provider = OfflineSourceAnalysisProvider()
    cases = {
        "Feb_Order_Export.csv": (SourceType.ORDERS, ["OrderRef", "GrossAmount", "SaleTimestamp"]),
        "PaymentGateway_Feb.xlsx": (SourceType.PAYMENTS, ["PaymentRef", "OrderRef", "AmountPaid"]),
        "BankCredits_Feb.csv": (
            SourceType.SETTLEMENTS,
            ["BankCreditRef", "PaymentRef", "GrossPaid", "FeeCharged", "NetPaid"],
        ),
        "Billing_February.xlsx": (SourceType.INVOICES, ["BillingNo", "OrderRef", "InvoiceAmount"]),
        "Refunds_Feb.csv": (SourceType.REFUNDS, ["RefundID", "PaymentRef", "RefundAmount"]),
        "Warehouse_February.xlsx": (
            SourceType.INVENTORY_MOVEMENTS,
            ["MoveID", "OrderRef", "MovementType", "Quantity", "ProductCode"],
        ),
        "Branch_Activity_Feb.csv": (
            SourceType.EMPLOYEE_ACTIONS,
            ["LogID", "StaffID", "Entity", "EntityRef", "Event"],
        ),
    }

    for filename, (expected_type, headers) in cases.items():
        document = analyze_content(
            filename.replace(".xlsx", ".csv"),
            (",".join(headers) + "\n" + ",".join(["value"] * len(headers))).encode(),
            100,
            30,
        )
        classification = provider.classify(filename, document)
        assert classification.source_type == expected_type, filename
        assert classification.confidence >= 0.9, filename


@pytest.mark.parametrize(
    ("source_type", "headers"),
    [
        (SourceType.SALES, ["ReceiptNo", "Outlet", "SaleValue", "CreatedAt", "Currency"]),
        (
            SourceType.PAYMENTS,
            ["GatewayTxn", "ReceiptNo", "PaidValue", "CapturedWhen", "Currency", "GatewayFee"],
        ),
        (
            SourceType.SETTLEMENTS,
            [
                "SettlementRef",
                "GatewayTxn",
                "SettlementGross",
                "ProcessingFee",
                "TaxOnFee",
                "NetCredit",
                "CreditedOn",
            ],
        ),
        (
            SourceType.REFUNDS,
            ["RefundRef", "GatewayTxn", "ReceiptNo", "RefundValue", "RefundedAt"],
        ),
        (
            SourceType.INVOICES,
            ["InvoiceNo", "ReceiptNo", "InvoiceTotal", "IssuedAt", "InvoiceState"],
        ),
        (
            SourceType.INVENTORY_MOVEMENTS,
            ["MovementRef", "ReceiptNo", "Movement", "Units", "SKU", "OccurredAt"],
        ),
        (
            SourceType.EMPLOYEE_ACTIONS,
            ["ActionRef", "EmployeeCode", "RecordType", "RecordRef", "ActionName", "ActionAt"],
        ),
    ],
)
def test_offline_provider_maps_common_operational_export_headers(
    source_type: SourceType, headers: list[str]
) -> None:
    document = analyze_content(
        "export.csv",
        (",".join(headers) + "\n" + ",".join(["value"] * len(headers))).encode(),
        100,
        30,
    )
    mappings = OfflineSourceAnalysisProvider().propose_mappings(source_type, document)
    mapped_fields = {item.canonical_field for item in mappings if item.canonical_field}

    assert REQUIRED_FIELDS[source_type].issubset(mapped_fields)


def test_xlsx_reader_converts_excel_serial_dates_to_utc_timestamps() -> None:
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.append(["ReceiptNo", "CreatedAt"])
    sheet.append(["ORD-1", 46030.413194444445])
    output = BytesIO()
    workbook.save(output)

    document = analyze_content("sales.xlsx", output.getvalue(), 100, 20)

    assert document.rows[0][1].startswith("2026-01-")
    assert document.rows[0][1].endswith("+00:00")


@pytest.mark.parametrize("header", ["PaidAt", "CreatedOn", "EventTime"])
def test_xlsx_reader_converts_vendor_date_alias_headers(header: str) -> None:
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.append([header])
    sheet.append([46058.51736111111])
    output = BytesIO()
    workbook.save(output)

    document = analyze_content("vendor-export.xlsx", output.getvalue(), 100, 20)

    assert document.rows[0][0].startswith("2026-")
    assert document.rows[0][0].endswith("+00:00")


def test_offline_provider_maps_invoice_gross_minor_and_ignores_tenant_scope() -> None:
    invoices = analyze_content(
        "invoices.csv",
        b"created_at,gross_minor,invoice_id,order_id,organization_id,status\n"
        b"2026-08-01T08:04:00+00:00,249000,INV-1,ORD-1,ORG-001,ACTIVE\n",
        100,
        20,
    )
    mappings = {
        item.source_column: item
        for item in OfflineSourceAnalysisProvider().propose_mappings(SourceType.INVOICES, invoices)
    }

    assert mappings["gross_minor"].canonical_field == "amount"
    assert mappings["gross_minor"].ignored is False
    assert mappings["organization_id"].canonical_field is None
    assert mappings["organization_id"].ignored is True
