from dataclasses import dataclass
from datetime import datetime
from typing import Any

from psycopg.types.json import Json

from app.persistence.connection import connection
from app.reconciliation.engine import reconcile_dataset
from app.simulator.generator import GeneratorConfig, generate_dataset


@dataclass(frozen=True, slots=True)
class SeedResult:
    organization_id: str
    run_key: str
    lifecycle_count: int
    exception_count: int
    skipped: bool


def seed_database(database_url: str, config: GeneratorConfig) -> SeedResult:
    dataset = generate_dataset(config)
    run_key = f"seed-{config.seed}-{config.orders}-{config.anomaly_rate:.4f}"
    results = reconcile_dataset(dataset)
    with connection(database_url) as conn:
        organization = conn.execute(
            """
            INSERT INTO organizations (external_id, name)
            VALUES (%s, %s)
            ON CONFLICT (external_id) DO UPDATE SET name = EXCLUDED.name
            RETURNING id
            """,
            (config.organization_id, f"FinTrace Demo {config.organization_id}"),
        ).fetchone()
        organization_uuid = organization["id"]
        existing_run = conn.execute(
            "SELECT id FROM reconciliation_runs WHERE organization_id = %s AND run_key = %s",
            (organization_uuid, run_key),
        ).fetchone()
        if existing_run is not None:
            exception_count = conn.execute(
                "SELECT count(*) AS count FROM exceptions WHERE reconciliation_run_id = %s",
                (existing_run["id"],),
            ).fetchone()["count"]
            return SeedResult(config.organization_id, run_key, config.orders, int(exception_count), True)

        run = conn.execute(
            """
            INSERT INTO reconciliation_runs
              (organization_id, run_key, seed, lifecycle_count, status, completed_at)
            VALUES (%s, %s, %s, %s, 'COMPLETED', now())
            RETURNING id
            """,
            (organization_uuid, run_key, config.seed, config.orders),
        ).fetchone()
        order_ids: dict[str, Any] = {}
        payment_ids: dict[str, Any] = {}
        for row in dataset.records["orders"]:
            order_ids[str(row["order_id"])] = _insert_order(conn, organization_uuid, row)
        for row in dataset.records["payments"]:
            payment_ids[str(row["payment_id"])] = _insert_payment(
                conn, organization_uuid, row, order_ids[str(row["order_id"])]
            )
        for row in dataset.records["settlements"]:
            _insert_settlement(conn, organization_uuid, row, payment_ids[str(row["payment_id"])])
        for row in dataset.records["invoices"]:
            _insert_invoice(conn, organization_uuid, row, order_ids[str(row["order_id"])])
        for row in dataset.records["refunds"]:
            _insert_refund(conn, organization_uuid, row, payment_ids[str(row["payment_id"])])
        for row in dataset.records["inventory_movements"]:
            _insert_inventory(conn, organization_uuid, row, order_ids[str(row["order_id"])])
        for row in dataset.records["employee_actions"]:
            _insert_employee_action(conn, organization_uuid, row)

        exception_count = 0
        for result in results:
            if result.status not in {"EXCEPTION", "AMBIGUOUS"}:
                continue
            order_uuid = order_ids[result.order_id]
            exception_id = f"EXC-{result.order_id.removeprefix('ORD-')}"
            conn.execute(
                """
                INSERT INTO exceptions
                  (organization_id, reconciliation_run_id, order_id, source_exception_id,
                   exception_type, severity, status, financial_exposure_minor, rules_triggered)
                VALUES (%s, %s, %s, %s, %s, %s, 'OPEN', %s, %s)
                """,
                (
                    organization_uuid,
                    run["id"],
                    order_uuid,
                    exception_id,
                    result.exception_type,
                    result.severity,
                    result.exposure_minor,
                    Json([finding.code for finding in result.findings]),
                ),
            )
            exception_count += 1
        return SeedResult(config.organization_id, run_key, config.orders, exception_count, False)


def _insert_order(conn: Any, organization_uuid: Any, row: dict[str, Any]) -> Any:
    return conn.execute(
        """
        INSERT INTO orders (organization_id, source_order_id, store_code, amount_minor, status, created_at)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (organization_id, source_order_id) DO UPDATE SET amount_minor = EXCLUDED.amount_minor
        RETURNING id
        """,
        (organization_uuid, row["order_id"], row["store"], row["amount_minor"], row["status"], _date(row["created_at"])),
    ).fetchone()["id"]


def _insert_payment(conn: Any, organization_uuid: Any, row: dict[str, Any], order_uuid: Any) -> Any:
    return conn.execute(
        """
        INSERT INTO payments
          (organization_id, source_payment_id, order_id, amount_minor, gateway_fee_minor, status, captured_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (organization_id, source_payment_id) DO UPDATE SET amount_minor = EXCLUDED.amount_minor
        RETURNING id
        """,
        (organization_uuid, row["payment_id"], order_uuid, row["amount_minor"], row["gateway_fee_minor"], row["status"], _date(row["captured_at"])),
    ).fetchone()["id"]


def _insert_settlement(conn: Any, organization_uuid: Any, row: dict[str, Any], payment_uuid: Any) -> None:
    conn.execute(
        """
        INSERT INTO settlements
          (organization_id, source_settlement_id, payment_id, gross_minor, fees_minor, tax_minor, net_minor, settled_at, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (organization_uuid, row["settlement_id"], payment_uuid, row["gross_minor"], row["fees_minor"], row["tax_minor"], row["net_minor"], _date(row["settled_at"]), row["status"]),
    )


def _insert_invoice(conn: Any, organization_uuid: Any, row: dict[str, Any], order_uuid: Any) -> None:
    conn.execute(
        """
        INSERT INTO invoices
          (organization_id, source_invoice_id, order_id, gross_minor, status, created_at)
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        (organization_uuid, row["invoice_id"], order_uuid, row["gross_minor"], row["status"], _date(row["created_at"])),
    )


def _insert_refund(conn: Any, organization_uuid: Any, row: dict[str, Any], payment_uuid: Any) -> None:
    conn.execute(
        """
        INSERT INTO refunds
          (organization_id, source_refund_id, payment_id, amount_minor, status, processed_at)
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        (organization_uuid, row["refund_id"], payment_uuid, row["amount_minor"], row["status"], _date(row["processed_at"])),
    )


def _insert_inventory(conn: Any, organization_uuid: Any, row: dict[str, Any], order_uuid: Any) -> None:
    conn.execute(
        """
        INSERT INTO inventory_movements
          (organization_id, source_movement_id, order_id, sku, quantity, movement_type, occurred_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
        (organization_uuid, row["movement_id"], order_uuid, row["sku"], row["quantity"], row["movement_type"], _date(row["occurred_at"])),
    )


def _insert_employee_action(conn: Any, organization_uuid: Any, row: dict[str, Any]) -> None:
    conn.execute(
        """
        INSERT INTO employee_actions
          (organization_id, source_action_id, entity_type, entity_id, employee_id, action, occurred_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
        (organization_uuid, row["action_id"], row["entity_type"], row["entity_id"], row["employee_id"], row["action"], _date(row["occurred_at"])),
    )


def _date(value: str) -> datetime:
    return datetime.fromisoformat(value)
