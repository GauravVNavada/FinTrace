from dataclasses import dataclass
from typing import Any


class LifecycleNotFoundError(LookupError):
    """The requested lifecycle is not visible in the current organization scope."""


@dataclass(frozen=True, slots=True)
class CanonicalLifecycle:
    order: dict[str, Any]
    payments: tuple[dict[str, Any], ...]
    settlements: tuple[dict[str, Any], ...]
    invoices: tuple[dict[str, Any], ...]
    refunds: tuple[dict[str, Any], ...]
    inventory_movements: tuple[dict[str, Any], ...]
    employee_actions: tuple[dict[str, Any], ...]


class LifecycleStore:
    """Read-only in-memory lifecycle store used by the simulator and API tests."""

    def __init__(self, records: dict[str, list[dict[str, Any]]]) -> None:
        self._records = records

    def get_by_order(self, organization_id: str, order_id: str) -> CanonicalLifecycle:
        orders = [
            item
            for item in self._records.get("orders", [])
            if item.get("organization_id") == organization_id and item.get("order_id") == order_id
        ]
        if len(orders) != 1:
            raise LifecycleNotFoundError(order_id)

        def related(name: str, foreign_key: str = "order_id") -> tuple[dict[str, Any], ...]:
            return tuple(
                item
                for item in self._records.get(name, [])
                if item.get("organization_id") == organization_id
                and item.get(foreign_key) == order_id
            )

        payments = related("payments")
        payment_ids = {item.get("payment_id") for item in payments}
        settlements = tuple(
            item
            for item in self._records.get("settlements", [])
            if item.get("organization_id") == organization_id
            and item.get("payment_id") in payment_ids
        )
        refunds = tuple(
            item
            for item in self._records.get("refunds", [])
            if item.get("organization_id") == organization_id
            and item.get("payment_id") in payment_ids
        )
        return CanonicalLifecycle(
            order=orders[0],
            payments=payments,
            settlements=settlements,
            invoices=related("invoices"),
            refunds=refunds,
            inventory_movements=related("inventory_movements"),
            employee_actions=tuple(item for item in self._records.get("employee_actions", [])
                if item.get("organization_id") == organization_id and (
                    item.get("order_id") == order_id or
                    (item.get("entity_type") == "ORDER" and item.get("entity_id") == order_id) or
                    (item.get("entity_type") == "REFUND" and item.get("entity_id") in {refund.get("refund_id") for refund in refunds})
                )),
        )
