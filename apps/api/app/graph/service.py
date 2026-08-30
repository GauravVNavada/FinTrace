from typing import Any

from app.domain.lifecycle import CanonicalLifecycle, LifecycleNotFoundError
from app.domain.schemas import ExceptionType
from app.graph.schemas import GraphEdge, GraphNode, GraphNodeState, LifecycleGraph
from app.repositories.demo import DemoRepository


class GraphNotFoundError(LookupError):
    pass


class LifecycleGraphService:
    def __init__(self, repository: DemoRepository) -> None:
        self._repository = repository

    def build(self, organization_id: str, exception_id: str) -> LifecycleGraph:
        exception = self._repository.get_exception(organization_id, exception_id)
        if exception is None:
            raise GraphNotFoundError(exception_id)
        try:
            lifecycle = self._repository.lifecycle(organization_id, exception.order_id)
        except LifecycleNotFoundError as error:
            raise GraphNotFoundError(exception_id) from error
        nodes, edges = self._nodes_and_edges(lifecycle, exception.type, exception.rules_triggered)
        return LifecycleGraph(exception_id=exception.id, organization_id=organization_id, nodes=nodes, edges=edges)

    @staticmethod
    def _nodes_and_edges(
        lifecycle: CanonicalLifecycle,
        exception_type: ExceptionType,
        rules_triggered: list[str],
    ) -> tuple[list[GraphNode], list[GraphEdge]]:
        nodes: list[GraphNode] = []
        edges: list[GraphEdge] = []

        def add_node(record: dict[str, Any], entity_type: str, id_key: str, label: str | None = None) -> str:
            record_id = str(record[id_key])
            nodes.append(
                GraphNode(
                    id=record_id,
                    entity_type=entity_type,
                    label=label or record_id,
                    state=GraphNodeState.CONFIRMED,
                    amount_minor=int(record["amount_minor"]) if record.get("amount_minor") is not None else None,
                )
            )
            return record_id

        order_id = add_node(lifecycle.order, "ORDER", "order_id", "Order")
        for payment in lifecycle.payments:
            payment_id = add_node(payment, "PAYMENT", "payment_id", "Payment")
            edges.append(GraphEdge(source=order_id, target=payment_id, relationship="ORDER_HAS_PAYMENT"))
        for settlement in lifecycle.settlements:
            settlement_id = add_node(settlement, "SETTLEMENT", "settlement_id", "Settlement")
            payment_id = str(settlement["payment_id"])
            edges.append(GraphEdge(source=payment_id, target=settlement_id, relationship="PAYMENT_HAS_SETTLEMENT"))
        for invoice in lifecycle.invoices:
            invoice_id = add_node(invoice, "INVOICE", "invoice_id", "Invoice")
            edges.append(GraphEdge(source=order_id, target=invoice_id, relationship="ORDER_HAS_INVOICE"))
        for refund in lifecycle.refunds:
            refund_id = add_node(refund, "REFUND", "refund_id", "Refund")
            edges.append(GraphEdge(source=str(refund["payment_id"]), target=refund_id, relationship="PAYMENT_HAS_REFUND"))
        for movement in lifecycle.inventory_movements:
            movement_id = add_node(movement, "INVENTORY", "movement_id", "Inventory movement")
            edges.append(GraphEdge(source=order_id, target=movement_id, relationship="ORDER_HAS_INVENTORY_MOVEMENT"))
        for action in lifecycle.employee_actions:
            action_id = add_node(action, "EMPLOYEE_ACTION", "action_id", "Employee action")
            edges.append(GraphEdge(source=order_id, target=action_id, relationship="ORDER_HAS_EMPLOYEE_ACTION"))

        missing: list[tuple[str, str, str]] = []
        if exception_type == ExceptionType.REFUND_WITHOUT_INVENTORY_RETURN:
            missing.append(("MISSING-INVENTORY-RETURN", "INVENTORY", "Expected inventory return"))
        if exception_type == ExceptionType.REFUND_WITHOUT_ERP_REVERSAL or "ERP_REVERSAL_MISSING" in rules_triggered:
            missing.append(("MISSING-ERP-REVERSAL", "ERP_REVERSAL", "Expected ERP reversal"))
        for missing_id, entity_type, label in missing:
            nodes.append(GraphNode(id=missing_id, entity_type=entity_type, label=label, state=GraphNodeState.MISSING))
            edges.append(GraphEdge(source=order_id, target=missing_id, relationship="ORDER_EXPECTS_MISSING_EVENT"))
        return nodes, edges
