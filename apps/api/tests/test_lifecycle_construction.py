import pytest

from app.lifecycle_construction.service import LifecycleConstructionError, construct_lifecycles


def test_payment_keyed_settlement_and_refund_are_attached_without_order_id():
    records = [
        {"source_type": "ORDERS", "values": {"order_id": "ORD-1", "amount_minor": 10000}},
        {
            "source_type": "PAYMENTS",
            "values": {
                "payment_id": "PAY-1",
                "order_id": "ORD-1",
                "amount_minor": 10000,
                "gateway_fee_minor": 100,
            },
        },
        {
            "source_type": "SETTLEMENTS",
            "values": {
                "settlement_id": "SET-1",
                "payment_id": "PAY-1",
                "fees_minor": 100,
                "settled_at": "2026-08-03T00:00:00+00:00",
            },
        },
        {
            "source_type": "REFUNDS",
            "values": {"refund_id": "REF-1", "payment_id": "PAY-1", "amount_minor": 10000},
        },
    ]
    lifecycle = construct_lifecycles("ORG-001", records)[0]
    assert lifecycle.settlements[0]["settlement_id"] == "SET-1"
    assert lifecycle.refunds[0]["refund_id"] == "REF-1"


def test_duplicate_order_records_are_rejected_instead_of_merged():
    records = [
        {"source_type": "ORDERS", "values": {"order_id": "ORD-1", "amount_minor": 10000}},
        {"source_type": "ORDERS", "values": {"order_id": "ORD-1", "amount_minor": 10000}},
    ]
    with pytest.raises(LifecycleConstructionError, match="exactly one"):
        construct_lifecycles("ORG-001", records)


def test_unassociated_records_are_rejected_instead_of_ignored():
    records = [
        {"source_type": "ORDERS", "values": {"order_id": "ORD-1", "amount_minor": 10000}},
        {"source_type": "PAYMENTS", "values": {"payment_id": "PAY-1", "amount_minor": 10000}},
    ]
    with pytest.raises(LifecycleConstructionError, match="relationship key"):
        construct_lifecycles("ORG-001", records)


def test_duplicate_invoice_records_are_rejected_instead_of_ignoring_the_second_invoice():
    records = [
        {"source_type": "ORDERS", "values": {"order_id": "ORD-1", "amount_minor": 10000}},
        {
            "source_type": "INVOICES",
            "values": {"invoice_id": "INV-1", "order_id": "ORD-1", "gross_minor": 10000},
        },
        {
            "source_type": "INVOICES",
            "values": {"invoice_id": "INV-2", "order_id": "ORD-1", "gross_minor": 10000},
        },
    ]
    with pytest.raises(LifecycleConstructionError, match="invoice records"):
        construct_lifecycles("ORG-001", records)
