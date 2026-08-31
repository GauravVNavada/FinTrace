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
    "payments": ("payment_id", "order_id", "amount", "gateway_fee", "status", "captured_at"),
    "settlements": (
        "settlement_id",
        "payment_id",
        "gross",
        "fee",
        "tax",
        "net",
        "settled_at",
        "status",
    ),
    "invoices": ("invoice_id", "order_id", "amount", "status", "created_at"),
    "refunds": ("refund_id", "payment_id", "amount", "status", "processed_at"),
    "inventory_movements": (
        "movement_id",
        "order_id",
        "sku",
        "quantity",
        "movement_type",
        "occurred_at",
    ),
    "employee_actions": (
        "action_id",
        "entity_type",
        "entity_id",
        "employee_id",
        "action",
        "occurred_at",
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
