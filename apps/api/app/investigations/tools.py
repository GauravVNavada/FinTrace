import re
from dataclasses import dataclass
from time import monotonic
from typing import Any

from app.domain.lifecycle import CanonicalLifecycle
from app.investigations.schemas import EvidenceItem, EvidenceSource, ToolCall
from app.repositories.contracts import LifecycleRepository

_ID_PATTERN = re.compile(r"^[A-Z][A-Z0-9-]{2,99}$")


@dataclass(frozen=True, slots=True)
class ToolResult:
    call: ToolCall
    values: tuple[dict[str, Any], ...]


def _validate_id(value: str, field_name: str) -> None:
    if not _ID_PATTERN.fullmatch(value):
        raise ValueError(f"invalid {field_name}")


class EvidenceToolRegistry:
    """Named, read-only evidence tools with explicit organization scope."""

    def __init__(self, repository: LifecycleRepository) -> None:
        self._repository = repository

    def invoke(
        self,
        name: str,
        organization_id: str,
        lifecycle: CanonicalLifecycle,
        entity_id: str | None = None,
    ) -> ToolResult:
        _validate_id(organization_id, "organization_id")
        order_id = str(lifecycle.order["order_id"])
        _validate_id(order_id, "order_id")
        started = monotonic()
        values: tuple[dict[str, Any], ...]
        evidence: list[EvidenceItem]

        if name == "get_order":
            values = (lifecycle.order,)
            evidence = [
                EvidenceItem(
                    source=EvidenceSource.ORDER, record_id=order_id, fact="Completed order exists."
                )
            ]
            target = order_id
        elif name == "get_payment":
            payment_id = self._single_payment_id(lifecycle)
            values = (lifecycle.payments[0],)
            evidence = [
                EvidenceItem(
                    source=EvidenceSource.PAYMENT,
                    record_id=payment_id,
                    fact="Captured payment is linked to the order.",
                )
            ]
            target = payment_id
        elif name == "get_payments_for_order":
            values = lifecycle.payments
            evidence = [
                EvidenceItem(
                    source=EvidenceSource.PAYMENT,
                    record_id=str(item["payment_id"]),
                    fact="Captured payment is linked to the order.",
                )
                for item in values
            ]
            target = order_id
        elif name == "get_settlement":
            if len(lifecycle.settlements) != 1:
                raise ValueError("settlement relationship is not singular")
            settlement_id = str(lifecycle.settlements[0]["settlement_id"])
            _validate_id(settlement_id, "settlement_id")
            values = (lifecycle.settlements[0],)
            evidence = [
                EvidenceItem(
                    source=EvidenceSource.SETTLEMENT,
                    record_id=settlement_id,
                    fact="Settlement is linked to the payment.",
                )
            ]
            target = settlement_id
        elif name == "get_settlements_for_payment":
            payment_id = self._single_payment_id(lifecycle)
            values = lifecycle.settlements
            evidence = [
                EvidenceItem(
                    source=EvidenceSource.SETTLEMENT,
                    record_id=str(item["settlement_id"]),
                    fact="Settlement is linked to the payment.",
                )
                for item in values
            ]
            target = payment_id
        elif name == "get_settlements_for_order":
            values = lifecycle.settlements
            evidence = [
                EvidenceItem(
                    source=EvidenceSource.SETTLEMENT,
                    record_id=str(item["settlement_id"]),
                    fact="Settlement is linked to the order.",
                )
                for item in values
            ]
            target = order_id
        elif name == "get_refunds_for_payment":
            payment_id = self._single_payment_id(lifecycle)
            values = lifecycle.refunds
            evidence = [
                EvidenceItem(
                    source=EvidenceSource.REFUND,
                    record_id=str(item["refund_id"]),
                    fact="Refund is processed.",
                )
                for item in values
            ]
            target = payment_id
        elif name == "get_refunds_for_order":
            values = lifecycle.refunds
            evidence = [
                EvidenceItem(
                    source=EvidenceSource.REFUND,
                    record_id=str(item["refund_id"]),
                    fact="Refund is processed against the order.",
                )
                for item in values
            ]
            target = order_id
        elif name == "get_invoice_for_order":
            values = lifecycle.invoices
            evidence = [
                EvidenceItem(
                    source=EvidenceSource.INVOICE,
                    record_id=str(item["invoice_id"]),
                    fact="ERP invoice is active and linked to the order.",
                )
                for item in values
            ]
            target = order_id
        elif name == "get_inventory_movements":
            values = lifecycle.inventory_movements
            returns = [item for item in values if item.get("movement_type") == "RETURN"]
            evidence = [
                EvidenceItem(
                    source=EvidenceSource.INVENTORY,
                    record_id=str(item["movement_id"]),
                    fact="Inventory return movement exists.",
                )
                for item in returns
            ]
            if not returns:
                evidence.append(
                    EvidenceItem(
                        source=EvidenceSource.INVENTORY,
                        record_id=None,
                        fact="No inventory RETURN movement exists.",
                    )
                )
            target = order_id
        elif name == "get_employee_action_logs":
            values = lifecycle.employee_actions
            evidence = [
                EvidenceItem(
                    source=EvidenceSource.EMPLOYEE_ACTION,
                    record_id=str(item["action_id"]),
                    fact="Employee action was recorded.",
                )
                for item in values
            ]
            target = order_id
        elif name == "get_related_exceptions":
            related = self._repository.related_exceptions(organization_id, order_id)
            values = tuple(item.model_dump(mode="json") for item in related)
            evidence = []
            target = order_id
        elif name == "get_exception_history":
            history_id = entity_id or order_id
            _validate_id(history_id, "entity_id")
            values = tuple(self._repository.audit_events(organization_id, history_id))
            evidence = []
            target = history_id
        else:
            raise ValueError("tool is not allowlisted")

        duration_ms = max(0, int((monotonic() - started) * 1000))
        return ToolResult(
            call=ToolCall(
                name=name,
                target=target,
                status="SUCCEEDED",
                duration_ms=duration_ms,
                evidence=evidence,
            ),
            values=values,
        )

    @staticmethod
    def _single_payment_id(lifecycle: CanonicalLifecycle) -> str:
        if len(lifecycle.payments) != 1:
            raise ValueError("payment relationship is not singular")
        payment_id = str(lifecycle.payments[0]["payment_id"])
        _validate_id(payment_id, "payment_id")
        return payment_id
