import csv
import json
import random
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from app.domain.lifecycle import LifecycleStore

SCENARIOS = (
    "NORMAL",
    "SETTLEMENT_TIMING",
    "SETTLEMENT_FEE_VARIANCE",
    "MISSING_INVOICE",
    "INVOICE_AMOUNT_MISMATCH",
    "MISSING_SETTLEMENT",
    "DUPLICATE_PAYMENT",
    "REFUND_INVENTORY_MISSING",
    "REFUND_ERP_REVERSAL_MISSING",
    "PARTIAL_REFUND_MISMATCH",
    "MANUAL_WORKFLOW_ANOMALY",
    "AMBIGUOUS_PAYMENT",
)
FLAGSHIP_FINANCE_REVIEW = "FLAGSHIP_FINANCE_REVIEW"


@dataclass(frozen=True, slots=True)
class GeneratorConfig:
    orders: int = 1000
    seed: int = 42
    anomaly_rate: float = 0.30
    organization_id: str = "ORG-001"
    scenario_types: tuple[str, ...] = ()
    preset: str | None = None


@dataclass(frozen=True, slots=True)
class GeneratedDataset:
    records: dict[str, list[dict[str, Any]]]
    ground_truth: list[dict[str, Any]]
    seed: int

    def lifecycle_store(self) -> LifecycleStore:
        return LifecycleStore(self.records)


def _money(value: Decimal) -> int:
    return int(value * 100)


def generate_dataset(config: GeneratorConfig | None = None) -> GeneratedDataset:
    config = config or GeneratorConfig()
    if config.orders < 1:
        raise ValueError("orders must be positive")
    if not 0 <= config.anomaly_rate <= 1:
        raise ValueError("anomaly_rate must be between 0 and 1")

    rng = random.Random(config.seed)
    records: dict[str, list[dict[str, Any]]] = {
        name: []
        for name in (
            "orders",
            "payments",
            "settlements",
            "invoices",
            "refunds",
            "inventory_movements",
            "employee_actions",
        )
    }
    ground_truth: list[dict[str, Any]] = []
    base_time = datetime(2026, 8, 1, 8, 0, tzinfo=UTC)
    anomaly_scenarios = config.scenario_types or SCENARIOS[1:]
    if config.preset not in (None, FLAGSHIP_FINANCE_REVIEW):
        raise ValueError(f"unsupported generator preset: {config.preset}")
    invalid_scenarios = set(anomaly_scenarios) - set(SCENARIOS[1:])
    if invalid_scenarios:
        raise ValueError("unsupported scenario types: " + ", ".join(sorted(invalid_scenarios)))
    amount_options: tuple[str, ...] = (
        "1290",
        "2490",
        "3490",
        "4500",
        "8340",
        "12990",
        "18740",
        "22400",
    )

    for index in range(config.orders):
        order_id = f"ORD-{10000 + index}"
        payment_id = f"PAY-{20000 + index}"
        amount = Decimal(rng.choice(amount_options))
        created_at = base_time + timedelta(minutes=index * 7)
        forced_flagship = {
            5: "MISSING_SETTLEMENT",
            15: "REFUND_INVENTORY_MISSING",
            25: "AMBIGUOUS_PAYMENT",
            35: "SETTLEMENT_FEE_VARIANCE",
            45: "SETTLEMENT_TIMING",
        }
        scenario = (
            forced_flagship.get(index)
            if config.preset == FLAGSHIP_FINANCE_REVIEW
            else None
        ) or (rng.choice(anomaly_scenarios) if rng.random() < config.anomaly_rate else "NORMAL")
        order: dict[str, Any] = {
            "organization_id": config.organization_id,
            "order_id": order_id,
            "store": rng.choice(["BLR-01", "BLR-03", "MYS-02", "HYD-04"]),
            "amount_minor": _money(amount),
            "status": "COMPLETED",
            "created_at": created_at.isoformat(),
        }
        payment: dict[str, Any] = {
            "organization_id": config.organization_id,
            "payment_id": payment_id,
            "order_id": order_id,
            "gateway_reference": f"GTW-{500000 + index}",
            "amount_minor": _money(amount),
            "status": "CAPTURED",
            "gateway_fee_minor": _money(amount * Decimal("0.018")),
            "captured_at": (created_at + timedelta(minutes=2)).isoformat(),
        }
        fee = Decimal(payment["gateway_fee_minor"]) / 100
        settlement: dict[str, Any] | None = {
            "organization_id": config.organization_id,
            "settlement_id": f"SET-{30000 + index}",
            "payment_id": payment_id,
            "gross_minor": _money(amount),
            "fees_minor": _money(fee),
            "tax_minor": _money(fee * Decimal("0.18")),
            "net_minor": _money(amount - fee - fee * Decimal("0.18")),
            "settled_at": (created_at + timedelta(days=2)).isoformat(),
            "status": "RECEIVED",
        }
        invoice: dict[str, Any] | None = {
            "organization_id": config.organization_id,
            "invoice_id": f"INV-{40000 + index}",
            "order_id": order_id,
            "gross_minor": _money(amount),
            "status": "ACTIVE",
            "created_at": (created_at + timedelta(minutes=4)).isoformat(),
        }
        inventory: dict[str, Any] = {
            "organization_id": config.organization_id,
            "movement_id": f"MOV-{50000 + index}",
            "order_id": order_id,
            "sku": f"SKU-{rng.randint(100, 999)}",
            "quantity": 1,
            "movement_type": "SALE",
            "occurred_at": (created_at + timedelta(minutes=5)).isoformat(),
        }
        employee: dict[str, Any] = {
            "organization_id": config.organization_id,
            "action_id": f"ACT-{60000 + index}",
            "entity_type": "ORDER",
            "entity_id": order_id,
            "employee_id": f"EMP-{rng.randint(10, 99)}",
            "action": "ORDER_CONFIRMED",
            "occurred_at": (created_at + timedelta(minutes=3)).isoformat(),
        }
        refunds: list[dict[str, Any]] = []

        if scenario.startswith("REFUND_") or scenario in {
            "PARTIAL_REFUND_MISMATCH",
            "MANUAL_WORKFLOW_ANOMALY",
        }:
            refund_amount = (
                amount if scenario != "PARTIAL_REFUND_MISMATCH" else amount * Decimal("0.4")
            )
            refunds.append(
                {
                    "organization_id": config.organization_id,
                    "refund_id": f"RFND-{70000 + index}",
                    "payment_id": payment_id,
                    "amount_minor": _money(refund_amount),
                    "status": "PROCESSED",
                    "processed_at": (created_at + timedelta(hours=2)).isoformat(),
                }
            )
            if scenario == "REFUND_ERP_REVERSAL_MISSING":
                inventory["movement_type"] = "RETURN"
            if scenario == "MANUAL_WORKFLOW_ANOMALY":
                employee["action"] = "MANUAL_REFUND_APPROVED"
        if scenario == "MISSING_INVOICE":
            invoice = None
        elif scenario == "INVOICE_AMOUNT_MISMATCH":
            assert invoice is not None
            invoice["gross_minor"] += 450000
        elif scenario == "MISSING_SETTLEMENT":
            settlement = None
        elif scenario == "SETTLEMENT_TIMING":
            assert settlement is not None
            settlement["settled_at"] = (created_at + timedelta(days=5)).isoformat()
        elif scenario == "SETTLEMENT_FEE_VARIANCE":
            assert settlement is not None
            settlement["fees_minor"] += 500
            settlement["net_minor"] -= 500
        elif scenario == "DUPLICATE_PAYMENT":
            records["payments"].append(
                {
                    **payment,
                    "payment_id": f"PAY-DUP-{index}",
                    "captured_at": (created_at + timedelta(minutes=3)).isoformat(),
                }
            )
        elif scenario == "AMBIGUOUS_PAYMENT":
            records["payments"].append(
                {
                    **payment,
                    "payment_id": f"PAY-AMB-{index}",
                    "captured_at": (created_at + timedelta(minutes=3)).isoformat(),
                }
            )

        records["orders"].append(order)
        records["payments"].append(payment)
        if settlement is not None:
            records["settlements"].append(settlement)
        if invoice is not None:
            records["invoices"].append(invoice)
        records["inventory_movements"].append(inventory)
        records["employee_actions"].append(employee)
        records["refunds"].extend(refunds)
        ground_truth.append(
            {
                "organization_id": config.organization_id,
                "order_id": order_id,
                "expected_status": "RECONCILED"
                if scenario == "NORMAL"
                else "RECONCILED_WITH_VARIANCE"
                if scenario in {"SETTLEMENT_TIMING", "SETTLEMENT_FEE_VARIANCE"}
                else "EXCEPTION"
                if scenario != "AMBIGUOUS_PAYMENT"
                else "AMBIGUOUS",
                "exception_type": None if scenario == "NORMAL" else scenario,
                "severity": "LOW"
                if scenario in {"SETTLEMENT_TIMING", "SETTLEMENT_FEE_VARIANCE"}
                else "HIGH"
                if scenario
                in {"DUPLICATE_PAYMENT", "REFUND_INVENTORY_MISSING", "REFUND_ERP_REVERSAL_MISSING"}
                else "MEDIUM",
            }
        )

    return GeneratedDataset(records=records, ground_truth=ground_truth, seed=config.seed)


def write_dataset(dataset: GeneratedDataset, output_dir: str | Path) -> Path:
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    for record_type, rows in dataset.records.items():
        if not rows:
            continue
        target = destination / f"{record_type}.csv"
        fieldnames = sorted({key for row in rows for key in row})
        with target.open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
    with (destination / "ground_truth.json").open("w", encoding="utf-8") as file:
        json.dump({"seed": dataset.seed, "records": dataset.ground_truth}, file, indent=2)
    return destination
