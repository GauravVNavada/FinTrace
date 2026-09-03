from __future__ import annotations

import csv
import io
from collections.abc import Iterable
from decimal import Decimal
from typing import Any

from app.financial_investigations.schemas import DemoDataRequest
from app.simulator.generator import GeneratorConfig, generate_dataset

_MONEY_FIELDS = {
    "amount_minor",
    "gross_minor",
    "fees_minor",
    "tax_minor",
    "net_minor",
    "gateway_fee_minor",
}
_SOURCE_HEADERS: dict[str, tuple[str, ...]] = {
    "orders": ("order_id", "store", "amount", "status", "created_at"),
    "payments": ("GatewayTxn", "ReceiptNumber", "PaidValue", "GatewayReference", "gateway_fee", "status", "CreatedWhen"),
    "settlements": (
        "SettlementRef",
        "GatewayReference",
        "GrossPaid",
        "ProcessingFee",
        "tax",
        "NetSettled",
        "BookedAt",
        "status",
    ),
    "invoices": ("InvoiceNumber", "ReceiptNumber", "InvoiceTotal", "status", "CreatedWhen"),
    "refunds": ("ReturnId", "GatewayReference", "RefundedAmount", "status", "CreatedWhen"),
    "inventory_movements": (
        "InventoryMovementId",
        "ReceiptNumber",
        "sku",
        "quantity",
        "MovementType",
        "OccurredAt",
    ),
    "employee_actions": (
        "EmployeeActionId",
        "EntityType",
        "EntityId",
        "UserId",
        "action",
        "OccurredAt",
    ),
}


def build_source_files(
    payload: DemoDataRequest,
    organization_id: str,
    scenarios: Iterable[str],
) -> list[tuple[str, bytes]]:
    dataset = generate_dataset(
        GeneratorConfig(
            orders=payload.orders,
            seed=payload.seed,
            anomaly_rate=payload.anomaly_rate,
            organization_id=organization_id,
            scenario_types=tuple(scenarios),
            preset=payload.preset,
        )
    )
    return [
        (f"{source_type}.csv", _to_csv(source_type, rows))
        for source_type, rows in dataset.records.items()
        if rows
    ]


def _to_csv(source_type: str, rows: list[dict[str, Any]]) -> bytes:
    headers = _SOURCE_HEADERS[source_type]
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=headers, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({header: _value(source_type, header, row) for header in headers})
    return output.getvalue().encode("utf-8")


def _value(source_type: str, header: str, row: dict[str, Any]) -> Any:
    field_by_header = {
        "GatewayTxn": "payment_id",
        "ReceiptNumber": "order_id",
        "PaidValue": "amount_minor",
        "GatewayReference": "gateway_reference" if source_type == "payments" else "payment_id",
        "CreatedWhen": "captured_at" if source_type == "payments" else "created_at" if source_type == "invoices" else "processed_at",
        "SettlementRef": "settlement_id",
        "GrossPaid": "gross_minor",
        "ProcessingFee": "fees_minor",
        "NetSettled": "net_minor",
        "BookedAt": "settled_at",
        "InvoiceNumber": "invoice_id",
        "InvoiceTotal": "gross_minor",
        "ReturnId": "refund_id",
        "RefundedAmount": "amount_minor",
        "InventoryMovementId": "movement_id",
        "MovementType": "movement_type",
        "OccurredAt": "occurred_at",
        "EmployeeActionId": "action_id",
        "EntityType": "entity_type",
        "EntityId": "entity_id",
        "UserId": "employee_id",
        "amount": "amount_minor",
        "gateway_fee": "gateway_fee_minor",
        "gross": "gross_minor",
        "fee": "fees_minor",
        "tax": "tax_minor",
        "net": "net_minor",
    }
    field = (
        "gross_minor"
        if source_type == "invoices" and header == "amount"
        else field_by_header.get(header, header)
    )
    value = row.get(field, "")
    if field in _MONEY_FIELDS and value not in (None, ""):
        return format(Decimal(int(value)) / Decimal(100), ".2f")
    return value
