import pytest
from httpx import ASGITransport, AsyncClient

from app.financial_investigations.files import UploadValidationError
from app.financial_investigations.schemas import SourceType
from app.main import app
from app.source_analysis.analyzer import analyze_content
from app.source_analysis.provider import (
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
