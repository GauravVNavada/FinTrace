"""Acceptance test against the exported sample files, never hidden truth labels."""
import calendar
from pathlib import Path
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

PACK = Path(__file__).resolve().parents[3] / "systhantic data"


@pytest.mark.asyncio
@pytest.mark.parametrize("month", range(1, 9))
async def test_month_upload_to_reconciliation(month):
    folder = PACK / f"{calendar.month_name[month]}_2026"
    assert folder.exists(), "Repository synthetic export pack is required"
    def headers():
        return {"X-Organization-Id": f"ORG-MONTH-TEST-{month}", "X-Actor-Id": "acceptance",
                "X-Actor-Role": "CONTROLLER", "Idempotency-Key": uuid4().hex}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await client.post("/api/v1/financial-investigations", headers=headers(), json={
            "name": f"{folder.name} intake acceptance", "period_start": f"2026-{month:02}-01",
            "period_end": f"2026-{month:02}-{calendar.monthrange(2026, month)[1]}", "base_currency": "INR"})
        assert created.status_code == 201, created.text
        base = f"/api/v1/financial-investigations/{created.json()['id']}"
        files = sorted(p for p in folder.iterdir() if p.suffix.lower() in {".csv", ".xlsx"})
        assert len(files) == 7
        for path in files:
            uploaded = await client.post(base + "/sources", headers=headers(), files={"file": (path.name, path.read_bytes(), "text/csv" if path.suffix == ".csv" else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
            assert uploaded.status_code == 201, (path.name, uploaded.text)
            source = base + f"/sources/{uploaded.json()['id']}"
            analyzed = await client.post(source + "/analyze", headers=headers())
            assert analyzed.status_code == 200, (path.name, analyzed.text)
            assert analyzed.json()["classification_confidence"] >= .9, (path.name, analyzed.json())
            confirmed = await client.post(source + "/mappings/confirm", headers=headers())
            assert confirmed.status_code == 200, (path.name, confirmed.text)
        normalized = await client.post(base + "/dataset-versions/normalize", headers=headers())
        assert normalized.status_code in (200, 201), normalized.text
        reconciled = await client.post(base + "/reconciliation-runs", headers=headers(), json={"dataset_version_id": normalized.json()["id"]})
        assert reconciled.status_code in (200, 201), reconciled.text
        run = reconciled.json()
        assert run["status"] == "COMPLETED", run
        assert run["records_expected"] == run["records_consumed"], run
        assert run["ambiguous_count"] >= 1, run
        assert 1 <= run["exception_count"] + run["ambiguous_count"] <= 3, run
        results = await client.get(base + f"/reconciliation-runs/{run['id']}/results", headers=headers())
        result = results.json()[0]
        evidence_url = base + f"/reconciliation-runs/{run['id']}/results/{result['id']}/lifecycle"
        evidence = await client.get(evidence_url, headers=headers())
        assert evidence.status_code == 200, evidence.text
        assert evidence.json()["order"]["order_id"] == result["order_id"]
        assert evidence.json()["payments"]
        denied = await client.get(evidence_url, headers={**headers(), "X-Organization-Id": "ORG-OUTSIDE"})
        assert denied.status_code == 404
