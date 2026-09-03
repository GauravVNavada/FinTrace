import re
from dataclasses import dataclass
from time import monotonic
from typing import Any

from app.domain.lifecycle import CanonicalLifecycle
from app.investigations.schemas import EvidenceItem, EvidenceOperator, EvidenceSource, ToolCall
from app.repositories.contracts import LifecycleRepository

# IDs are external identifiers from uploaded systems.  They may be lowercase,
# digit-leading, or shorter than the demo's ORD-/PAY- convention, but must stay
# bounded and single-token so they are safe to cite and verify.
_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,99}$")


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
            evidence = _record_evidence(EvidenceSource.ORDER, lifecycle.order, order_id)
            target = order_id
        elif name == "get_payment":
            payment_id = self._single_payment_id(lifecycle)
            values = (lifecycle.payments[0],)
            evidence = _record_evidence(EvidenceSource.PAYMENT, lifecycle.payments[0], payment_id)
            target = payment_id
        elif name == "get_payments_for_order":
            values = lifecycle.payments
            evidence = [fact
                for item in values
                for fact in _record_evidence(EvidenceSource.PAYMENT, item, str(item["payment_id"]))
            ]
            target = order_id
        elif name == "get_settlement":
            if len(lifecycle.settlements) != 1:
                raise ValueError("settlement relationship is not singular")
            settlement_id = str(lifecycle.settlements[0]["settlement_id"])
            _validate_id(settlement_id, "settlement_id")
            values = (lifecycle.settlements[0],)
            evidence = _record_evidence(EvidenceSource.SETTLEMENT, lifecycle.settlements[0], settlement_id)
            target = settlement_id
        elif name == "get_settlements_for_payment":
            payment_id = self._single_payment_id(lifecycle)
            values = lifecycle.settlements
            evidence = [fact
                for item in values
                for fact in _record_evidence(EvidenceSource.SETTLEMENT, item, str(item["settlement_id"]))
            ]
            if not values:
                evidence.append(
                    EvidenceItem(
                        source=EvidenceSource.SETTLEMENT,
                        record_id=None,
                        fact="No settlement record exists for the scoped payment.",
                        field="settlement_id",
                        operator=EvidenceOperator.MISSING,
                        expected_value=None,
                    )
                )
            target = payment_id
        elif name == "get_settlements_for_order":
            values = lifecycle.settlements
            evidence = [fact
                for item in values
                for fact in _record_evidence(EvidenceSource.SETTLEMENT, item, str(item["settlement_id"]))
            ]
            if not values:
                evidence.append(
                    EvidenceItem(
                        source=EvidenceSource.SETTLEMENT,
                        record_id=None,
                        fact="No settlement record exists for the scoped order.",
                        field="settlement_id",
                        operator=EvidenceOperator.MISSING,
                        expected_value=None,
                    )
                )
            target = order_id
        elif name == "get_refunds_for_payment":
            payment_id = self._single_payment_id(lifecycle)
            values = lifecycle.refunds
            evidence = [fact
                for item in values
                for fact in _record_evidence(EvidenceSource.REFUND, item, str(item["refund_id"]))
            ]
            target = payment_id
        elif name == "get_refunds_for_order":
            values = lifecycle.refunds
            evidence = [fact
                for item in values
                for fact in _record_evidence(EvidenceSource.REFUND, item, str(item["refund_id"]))
            ]
            target = order_id
        elif name == "get_invoice_for_order":
            values = lifecycle.invoices
            evidence = [fact
                for item in values
                for fact in _record_evidence(EvidenceSource.INVOICE, item, str(item["invoice_id"]))
            ]
            target = order_id
        elif name == "get_inventory_movements":
            values = lifecycle.inventory_movements
            returns = [item for item in values if item.get("movement_type") == "RETURN"]
            evidence = [fact
                for item in returns
                for fact in _record_evidence(EvidenceSource.INVENTORY, item, str(item["movement_id"]))
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
            evidence = [fact
                for item in values
                for fact in _record_evidence(EvidenceSource.EMPLOYEE_ACTION, item, str(item["action_id"]))
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
    record_id: str | None,
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


def _status_evidence(
    source: EvidenceSource, record: dict[str, Any], record_id: str
) -> EvidenceItem:
    """Create a status claim from the record, never from a lifecycle assumption."""
    status = record.get("status")
    label = source.value.replace("_", " ").title()
    if status is None:
        return _evidence(
            source,
            record_id,
            "status",
            EvidenceOperator.EXISTS,
            None,
            f"{label} record exists but has no status value.",
        )
    return _evidence(
        source,
        record_id,
        "status",
        EvidenceOperator.EQUALS,
        str(status),
        f"{label} status is {status}.",
    )


def _record_evidence(source: EvidenceSource, record: dict[str, Any], record_id: str) -> list[EvidenceItem]:
    """Return a small, source-specific fact set instead of exposing the full source row."""
    label = source.value.replace("_", " ").title()
    field_specs: dict[EvidenceSource, tuple[tuple[str, str], ...]] = {
        EvidenceSource.ORDER: (("amount_minor", "amount_minor"), ("created_at", "created_at"), ("status", "status")),
        EvidenceSource.PAYMENT: (("order_id", "order_id"), ("amount_minor", "amount_minor"), ("captured_at", "captured_at"), ("status", "status"), ("gateway_reference", "gateway_reference")),
        EvidenceSource.SETTLEMENT: (("payment_id", "payment_id"), ("gross_minor", "gross_minor"), ("fees_minor", "fees_minor"), ("tax_minor", "tax_minor"), ("net_minor", "net_minor"), ("settled_at", "settled_at"), ("status", "status")),
        EvidenceSource.INVOICE: (("order_id", "order_id"), ("gross_minor", "gross_minor"), ("created_at", "created_at"), ("status", "status")),
        EvidenceSource.REFUND: (("payment_id", "payment_id"), ("amount_minor", "amount_minor"), ("processed_at", "processed_at"), ("status", "status")),
        EvidenceSource.INVENTORY: (("order_id", "order_id"), ("movement_type", "movement_type"), ("quantity", "quantity"), ("occurred_at", "occurred_at")),
        EvidenceSource.EMPLOYEE_ACTION: (("entity_id", "entity_id"), ("employee_id", "employee_id"), ("action", "action"), ("occurred_at", "occurred_at")),
    }
    facts: list[EvidenceItem] = []
    for source_field, display_field in field_specs[source]:
        value = record.get(source_field)
        if value in (None, ""):
            continue
        expected = str(value) if not isinstance(value, (str, int, float, bool)) else value
        facts.append(_evidence(source, record_id, display_field, "equals", expected, f"{label} {display_field} is {value}."))
    if not facts:
        facts.append(_evidence(source, record_id, None, "exists", None, f"{label} record exists."))
    facts.sort(key=lambda item: 0 if item.field == "status" else 1)
    return facts


def _result_summary(name: str, values: tuple[dict[str, Any], ...]) -> str:
    if not values:
        return f"{name}: no records located"
    return f"{name}: {len(values)} record(s) returned"
