import re
from dataclasses import dataclass
from time import monotonic
from typing import Any

from app.domain.lifecycle import CanonicalLifecycle
from app.investigations.schemas import EvidenceItem, EvidenceOperator, EvidenceSource, ToolCall
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
        arguments: dict[str, Any] | None = None,
    ) -> ToolResult:
        _validate_id(organization_id, "organization_id")
        order_id = str(lifecycle.order["order_id"])
        _validate_id(order_id, "order_id")
        if arguments is not None and not isinstance(arguments, dict):
            raise ValueError("tool arguments must be an object")
        if arguments and set(arguments) - {"order_id", "payment_id", "entity_id"}:
            raise ValueError("tool arguments contain unsupported fields")
        started = monotonic()
        values: tuple[dict[str, Any], ...]
        evidence: list[EvidenceItem]

        if name == "get_order":
            values = (lifecycle.order,)
            evidence = [
                _evidence(EvidenceSource.ORDER, order_id, "status", "exists", None,
                    "Order record exists in the scoped lifecycle.")
            ]
            target = order_id
        elif name == "get_payment":
            payment_id = self._single_payment_id(lifecycle)
            values = (lifecycle.payments[0],)
            evidence = [
                _evidence(EvidenceSource.PAYMENT, payment_id, "status", "equals", "CAPTURED",
                    "Payment status is CAPTURED.")
            ]
            target = payment_id
        elif name == "get_payments_for_order":
            values = lifecycle.payments
            evidence = [
                _evidence(EvidenceSource.PAYMENT, str(item["payment_id"]), "status", "equals",
                    "CAPTURED", "Payment status is CAPTURED.")
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
                _evidence(EvidenceSource.SETTLEMENT, settlement_id, "status", "equals", "RECEIVED",
                    "Settlement status is RECEIVED.")
            ]
            target = settlement_id
        elif name == "get_settlements_for_payment":
            payment_id = self._single_payment_id(lifecycle)
            values = lifecycle.settlements
            evidence = [
                _evidence(EvidenceSource.SETTLEMENT, str(item["settlement_id"]), "status", "equals",
                    "RECEIVED", "Settlement status is RECEIVED.")
                for item in values
            ]
            target = payment_id
        elif name == "get_settlements_for_order":
            values = lifecycle.settlements
            evidence = [
                _evidence(EvidenceSource.SETTLEMENT, str(item["settlement_id"]), "status", "equals",
                    "RECEIVED", "Settlement status is RECEIVED.")
                for item in values
            ]
            target = order_id
        elif name == "get_refunds_for_payment":
            payment_id = self._single_payment_id(lifecycle)
            values = lifecycle.refunds
            evidence = [
                _evidence(EvidenceSource.REFUND, str(item["refund_id"]), "status", "equals",
                    "PROCESSED", "Refund status is PROCESSED.")
                for item in values
            ]
            target = payment_id
        elif name == "get_refunds_for_order":
            values = lifecycle.refunds
            evidence = [
                _evidence(EvidenceSource.REFUND, str(item["refund_id"]), "status", "equals",
                    "PROCESSED", "Refund status is PROCESSED.")
                for item in values
            ]
            target = order_id
        elif name == "get_invoice_for_order":
            values = lifecycle.invoices
            evidence = [
                _evidence(EvidenceSource.INVOICE, str(item["invoice_id"]), "status", "equals", "ACTIVE",
                    "Invoice status is ACTIVE.")
                for item in values
            ]
            target = order_id
        elif name == "get_inventory_movements":
            values = lifecycle.inventory_movements
            returns = [item for item in values if item.get("movement_type") == "RETURN"]
            evidence = [
                _evidence(EvidenceSource.INVENTORY, str(item["movement_id"]), "movement_type",
                    "equals", "RETURN", "Inventory movement type is RETURN.")
                for item in returns
            ]
            if not returns:
                evidence.append(
                    EvidenceItem(
                        source=EvidenceSource.INVENTORY,
                        record_id=None,
                        fact="No inventory RETURN movement exists.",
                        field="movement_type",
                        operator=EvidenceOperator.MISSING,
                        expected_value="RETURN",
                    )
                )
            target = order_id
        elif name == "get_employee_action_logs":
            values = lifecycle.employee_actions
            evidence = [
                    _evidence(EvidenceSource.EMPLOYEE_ACTION, str(item["action_id"]), "action_id",
                        "exists", None, "Employee action record exists.")
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
                sequence_no=0,
                arguments=arguments or {},
                result_record_ids=[
                    str(item.get(key))
                    for item in values
                    for key in ("order_id", "payment_id", "settlement_id", "invoice_id", "refund_id", "movement_id", "action_id")
                    if item.get(key) is not None
                ],
                result_summary=_result_summary(name, values),
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


def _evidence(
    source: EvidenceSource,
    record_id: str,
    field: str | None,
    operator: EvidenceOperator | str,
    expected_value: str | float | bool | None,
    fact: str,
) -> EvidenceItem:
    return EvidenceItem(
        source=source,
        record_id=record_id,
        field=field,
        operator=EvidenceOperator(operator),
        expected_value=expected_value,
        fact=fact,
    )


def _result_summary(name: str, values: tuple[dict[str, Any], ...]) -> str:
    if not values:
        return f"{name}: no records located"
    return f"{name}: {len(values)} record(s) returned"
