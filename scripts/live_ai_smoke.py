"""Explicit live-provider smoke test for the FinTrace demo configuration.

This script is intentionally opt-in and never prints credentials or provider payloads.
It performs one health probe per configured provider, one source-analysis request, and
one complete investigation against the deterministic flagship exception.
"""

from __future__ import annotations

import os
import sys
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API_ROOT = ROOT / "apps" / "api"
sys.path.insert(0, str(API_ROOT))

from app.core.config import get_settings
from app.domain.schemas import ExceptionType
from app.investigations.provider import (
    get_configured_ai_client,
    provider_health_report,
)
from app.investigations.service import InvestigationService
from app.repositories.demo import demo_repository
from app.source_analysis.analyzer import analyze_content
from app.source_analysis.provider import OfflineSourceAnalysisProvider


def main() -> int:
    if os.environ.get("RUN_LIVE_AI_TESTS") != "1":
        print("Live AI smoke is disabled. Set RUN_LIVE_AI_TESTS=1 to run it.")
        return 2

    # Settings loads the app-local .env relative to the current working directory.
    # Make the documented repository-root invocation use the same configuration as
    # the API process instead of accidentally reading a different root-level env.
    os.chdir(API_ROOT)
    settings = get_settings()
    client = get_configured_ai_client(settings)
    health = provider_health_report(client)
    provider_summary = ",".join(
        f"{item.provider}:{item.model}:{item.status}:{item.error_category or 'none'}"
        for item in health.providers
    )
    print(
        f"health overall_status={health.overall_status} "
        f"active_provider={health.active_provider or 'none'} providers={provider_summary}"
    )
    primary = health.providers[0] if health.providers else None
    if primary is None or primary.status != "CONNECTED":
        print("Stopping after isolated primary-provider health failure.")
        return 1

    document = analyze_content(
        "orders.csv",
        b"order_id,total,status\nORD-LIVE-001,100.00,COMPLETED\n",
        max_rows=20,
        max_columns=20,
        truncate=True,
    )
    # Source classification/mapping is deterministic ingestion preparation in the
    # application. Keep this explicitly labelled so it cannot be mistaken for a
    # live AI finding.
    source_provider = OfflineSourceAnalysisProvider()
    classification = source_provider.classify("orders.csv", document)
    mappings = source_provider.propose_mappings(classification.source_type, document)
    print(
        f"source_analysis provider={classification.provider} model={classification.model} "
        f"source_type={classification.source_type.value} mappings={len(mappings)} "
        "mode=deterministic_ingestion_prep"
    )

    exception = demo_repository.get_exception("ORG-001", "EXC-1042")
    if exception is None:
        print("Flagship exception was not found in the deterministic demo repository.")
        return 1
    lifecycle = demo_repository.lifecycle("ORG-001", exception.order_id)
    investigator = InvestigationService(demo_repository, client)
    result = investigator.investigate_lifecycle("ORG-001", exception, lifecycle)
    print(
        f"investigation status={result.status} provider={result.actual_provider_used} "
        f"model={result.model_used} fallback_used={result.fallback_used} "
        f"fallback_reason={result.fallback_reason or 'none'} "
        f"tool_calls={','.join(call.name for call in result.tool_calls)} "
        f"verifier_passed={result.verifier_passed} root_cause={result.root_cause_code or 'none'}"
    )
    inventory_lifecycle = replace(
        lifecycle,
        inventory_movements=(
            {
                "organization_id": "ORG-001",
                "movement_id": "MOV-LIVE-SALE",
                "order_id": exception.order_id,
                "sku": "SKU-LIVE",
                "quantity": 1,
                "movement_type": "SALE",
                "unit_cost_minor": 2400,
                "inventory_value_minor": 2400,
            },
            {
                "organization_id": "ORG-001",
                "movement_id": "MOV-LIVE-RETURN",
                "order_id": exception.order_id,
                "sku": "SKU-LIVE",
                "quantity": 1,
                "movement_type": "RETURN",
                "unit_cost_minor": 2500,
                "inventory_value_minor": 2500,
            },
        ),
    )
    inventory_exception = exception.model_copy(
        update={
            "id": "EXC-LIVE-INVENTORY",
            "type": ExceptionType.INVENTORY_VALUE_MISMATCH,
            "financial_exposure": Decimal(100),
            "rules_triggered": [ExceptionType.INVENTORY_VALUE_MISMATCH.value],
        }
    )
    inventory_result = investigator.investigate_lifecycle(
        "ORG-001", inventory_exception, inventory_lifecycle
    )
    print(
        f"inventory_investigation status={inventory_result.status} "
        f"provider={inventory_result.actual_provider_used} model={inventory_result.model_used} "
        f"verifier_passed={inventory_result.verifier_passed} "
        f"root_cause={inventory_result.root_cause_code or 'none'} "
        f"cited_inventory={sum(call.name == 'get_inventory_movements' for call in inventory_result.tool_calls)}"
    )
    return 0 if (
        result.status in {"SUPPORTED", "UNRESOLVED"}
        and result.verifier_passed
        and inventory_result.status == "SUPPORTED"
        and inventory_result.verifier_passed
        and inventory_result.actual_provider_used == "groq"
    ) else 1


if __name__ == "__main__":
    raise SystemExit(main())
