from collections import defaultdict
from typing import Any

from app.domain.lifecycle import CanonicalLifecycle


class LifecycleConstructionError(ValueError):
    """Raised when normalized records cannot form an unambiguous lifecycle."""


_COLLECTIONS = {
    "PAYMENTS": "payments",
    "PAYMENT": "payments",
    "SETTLEMENTS": "settlements",
    "SETTLEMENT": "settlements",
    "INVOICES": "invoices",
    "INVOICE": "invoices",
    "REFUNDS": "refunds",
    "REFUND": "refunds",
    "INVENTORY_MOVEMENTS": "inventory_movements",
    "INVENTORY_MOVEMENT": "inventory_movements",
    "EMPLOYEE_ACTIONS": "employee_actions",
    "EMPLOYEE_ACTION": "employee_actions",
}


def _canonical_values(record: dict[str, Any], organization_id: str) -> dict[str, Any]:
    values = {str(key): value for key, value in dict(record.get("values", {})).items()}
    converted: dict[str, Any] = {"organization_id": organization_id}
    for key, value in values.items():
        if value in (None, ""):
            converted[key] = value
        elif key.endswith("_minor"):
            try:
                converted[key] = int(value)
            except (TypeError, ValueError) as error:
                raise LifecycleConstructionError(
                    f"{key} is not an integer minor-unit value"
                ) from error
        else:
            converted[key] = value
    # Retain an internal immutable source-row marker so reconciliation can prove
    # that every normalized record was consumed without exposing it as finance data.
    converted["__normalized_record_id"] = str(record.get("id", ""))
    return converted


def construct_lifecycles(
    organization_id: str, records: list[dict[str, Any]]
) -> list[CanonicalLifecycle]:
    """Construct lifecycles without guessing missing or ambiguous relationships."""
    by_order: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    payment_keyed: dict[str, list[dict[str, Any]]] = defaultdict(list)
    order_keyed_actions: dict[str, list[dict[str, Any]]] = defaultdict(list)
    refund_keyed_actions: dict[str, list[dict[str, Any]]] = defaultdict(list)
    keyed_records: set[int] = set()
    for record in records:
        values = _canonical_values(record, organization_id)
        source_type = str(record.get("source_type", "")).upper()
        order_id = values.get("order_id")
        collection = (
            "orders"
            if source_type in {"ORDER", "ORDERS", "SALES"}
            else _COLLECTIONS.get(source_type)
        )
        if collection and order_id:
            by_order[str(order_id)][collection].append(values)
        elif collection in {"settlements", "refunds"} and values.get("payment_id"):
            payment_keyed[str(values["payment_id"])].append(values)
            keyed_records.add(id(values))
        elif collection == "employee_actions" and values.get("entity_id"):
            entity_type = str(values.get("entity_type", "")).upper()
            if entity_type in {"REFUND", "REFUNDS"}:
                refund_keyed_actions[str(values["entity_id"])].append(values)
            else:
                order_keyed_actions[str(values["entity_id"])].append(values)
            keyed_records.add(id(values))
        elif collection is None:
            raise LifecycleConstructionError(
                f"{record.get('source_type', 'UNKNOWN')} is not a supported canonical source type"
            )
        else:
            raise LifecycleConstructionError(f"{source_type} row has no canonical relationship key")

    if not by_order:
        raise LifecycleConstructionError("The normalized dataset contains no order-bearing records")

    lifecycles: list[CanonicalLifecycle] = []
    attached_keyed_records: set[int] = set()
    for order_id, grouped in by_order.items():
        orders = grouped.get("orders", [])
        if len(orders) != 1:
            raise LifecycleConstructionError(
                f"{order_id} has {len(orders)} order records; exactly one is required"
            )
        invoices = grouped.get("invoices", [])
        if len(invoices) > 1:
            active = [item for item in invoices if item.get("status") == "ACTIVE"]
            reversals = [item for item in invoices if item.get("status") == "REVERSED"]
            if len(active) == 1 and len(active) + len(reversals) == len(invoices):
                # A refund commonly emits a second ERP row that reverses the
                # original invoice. Keep both rows for accounting completeness,
                # while putting the active sale invoice first for reconciliation.
                invoices = active + reversals
            else:
                raise LifecycleConstructionError(
                    f"{order_id} has {len(invoices)} invoice records; at most one active invoice is supported"
                )
        payments = grouped.get("payments", [])
        payment_ids = {item.get("payment_id") for item in payments}
        settlements = [
            item for item in grouped.get("settlements", []) if item.get("payment_id") in payment_ids
        ]
        refunds = [
            item for item in grouped.get("refunds", []) if item.get("payment_id") in payment_ids
        ]
        for payment_id in payment_ids:
            keyed = payment_keyed.get(str(payment_id), [])
            settlements.extend(item for item in keyed if item.get("settlement_id"))
            refunds.extend(item for item in keyed if item.get("refund_id"))
            attached_keyed_records.update(id(item) for item in keyed)
        employee_actions = list(grouped.get("employee_actions", []))
        keyed_actions = order_keyed_actions.get(order_id, [])
        employee_actions.extend(keyed_actions)
        refund_ids = {str(item.get("refund_id")) for item in refunds if item.get("refund_id")}
        refund_actions = [
            action
            for refund_id in refund_ids
            for action in refund_keyed_actions.get(refund_id, [])
        ]
        employee_actions.extend(refund_actions)
        attached_keyed_records.update(id(item) for item in keyed_actions)
        attached_keyed_records.update(id(item) for item in refund_actions)
        lifecycles.append(
            CanonicalLifecycle(
                order=orders[0],
                payments=tuple(payments),
                settlements=tuple(settlements),
                invoices=tuple(invoices),
                refunds=tuple(refunds),
                inventory_movements=tuple(grouped.get("inventory_movements", [])),
                employee_actions=tuple(employee_actions),
            )
        )
    if attached_keyed_records != keyed_records:
        raise LifecycleConstructionError(
            "One or more settlement, refund, or employee-action records could not be associated with an order"
        )
    return lifecycles
