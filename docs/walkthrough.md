# FinTrace walkthrough

Follow [local development](local-development.md) to start PostgreSQL, the API on port 8001, and the web application on port 3002. Configure a live Groq key server-side. Keep credentials out of source control. Continue with the local Controller identity; this login is disabled outside development.

## Run a monthly close

1. Choose **Closes → Start a new close**. Enter a name and calendar-month dates.
2. Select all seven CSV/XLSX files in the corresponding folder under [systhantic data](../systhantic%20data/README.md). March 2026 is covered by the live browser acceptance test.
3. Wait for **All files understood**. Recognized valid mappings are accepted automatically; genuinely missing or ambiguous fields remain reviewable.
4. Choose **Run close**. March's packaged inputs produce 515 accounted-for records across 80 lifecycles: 77 reconciled, two needing decisions, and one needing evidence.
5. Open an inventory finding to inspect the order, refund, sale movement, and return evidence. Choose **Investigate evidence** for the configured live provider's cited assessment and evidence-confidence score.
6. Inspect the ambiguous payment finding. The system preserves ambiguity when references are insufficient; a fluent answer is not proof that a payment is correct.
7. Open Attention for remaining work. Consequential actions require role checks and human approval. AI cannot mutate financial state.
8. Return to Home: it displays the latest non-stale run across closes. A new empty close does not replace those results.

## Validation

Run API tests from `apps/api` with `.venv/Scripts/python.exe -m pytest -q`. Run the real browser workflow from the repository root with `FINTRACE_LIVE_E2E=1` set in the environment and `pnpm exec playwright test --workers=1`. Live tests require running services and a reachable configured provider, consume provider quota, and create a new synthetic close without deleting existing ones.

See [release cleanup](release-cleanup.md) and [final validation](final-validation.md) for scope and deployment boundaries. Monthly files contain intentional business mismatches.
