import csv

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.simulator.generator import GeneratorConfig, generate_dataset, write_dataset


@pytest.mark.asyncio
async def test_sprint1_vertical_slice(tmp_path) -> None:
    dataset = generate_dataset(GeneratorConfig(orders=50, seed=42, anomaly_rate=0.3))
    output_dir = write_dataset(dataset, tmp_path / "generated")

    with (output_dir / "orders.csv").open(newline="", encoding="utf-8") as file:
        order_rows = list(csv.DictReader(file))
    with (output_dir / "ground_truth.json").open(encoding="utf-8") as file:
        ground_truth = file.read()

    assert len(order_rows) == 50
    assert '"order_id": "ORD-10000"' in ground_truth

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/api/v1/lifecycles/ORD-10000", headers={"X-Organization-Id": "ORG-001"}
        )
    assert response.status_code == 200
    assert response.json()["order"]["order_id"] == "ORD-10000"
