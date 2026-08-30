from app.simulator.generator import GeneratorConfig, generate_dataset


def test_generator_is_reproducible() -> None:
    config = GeneratorConfig(orders=50, seed=42, anomaly_rate=0.3)
    first = generate_dataset(config)
    second = generate_dataset(config)
    assert first.records == second.records
    assert first.ground_truth == second.ground_truth


def test_generator_produces_correlated_lifecycle() -> None:
    dataset = generate_dataset(GeneratorConfig(orders=10, seed=7, anomaly_rate=0))
    lifecycle = dataset.lifecycle_store().get_by_order("ORG-001", "ORD-10000")
    assert lifecycle.order["order_id"] == "ORD-10000"
    assert lifecycle.payments[0]["order_id"] == lifecycle.order["order_id"]
    assert lifecycle.settlements[0]["payment_id"] == lifecycle.payments[0]["payment_id"]


def test_lifecycle_store_does_not_cross_tenant_scope() -> None:
    dataset = generate_dataset(GeneratorConfig(orders=1, seed=42, anomaly_rate=0))
    store = dataset.lifecycle_store()
    try:
        store.get_by_order("ORG-OTHER", "ORD-10000")
    except LookupError:
        pass
    else:
        raise AssertionError("cross-tenant lifecycle access must not return data")
