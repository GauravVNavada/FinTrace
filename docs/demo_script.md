# FinTrace Demo Script

**Status:** Local release walkthrough for the completed Sprints 0–7 synthetic product path · 2026-08-31

## Demo modes

The walkthrough demonstrates a fresh synthetic financial investigation. The web flow supports source generation or upload, bounded analysis, mapping edits, explicit confirmation, relationship decisions, immutable dataset normalization, deterministic reconciliation, uploaded-result evidence investigation, advisory patterns, evaluation, and audit. The legacy `/exceptions` queue is a separate seeded compatibility workflow; uploaded investigation results remain in their owning workspace.

## Reproduce the dataset and benchmark

From the repository root in PowerShell:

```powershell
.\scripts\demo.ps1
```

The script generates a seed-42 synthetic dataset and prints the deterministic reconciliation benchmark. It writes only to the ignored `apps/api/data/generated/demo` directory. Benchmark numbers are measured at runtime and must not be copied into product claims without recording the command and environment.

## Start the product

Terminal 1:

```powershell
cd apps/api
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8001
```

Terminal 2:

```powershell
pnpm --filter @fintrace/web dev -- --port 3002
```

Open `http://localhost:3000`.

## Five-minute walkthrough

1. Open **Investigations → Create a financial investigation**, enter a name, period, and currency, then create the workspace.
2. On **Sources**, choose **Generate and attach** with a bounded order count, seed, anomaly rate, and scenario set. The generator creates separate source exports through the same upload boundary; it is disabled after sources are attached.
3. Analyze each source. Review the detected type and required mappings, edit/ignore fields when necessary, and confirm mappings explicitly.
4. Open relationship review, inspect deterministic overlap evidence, and accept only the proposed joins you want to use.
5. Normalize and reconcile. Confirm the persisted run shows lifecycle count, reconciled count, exceptions, ambiguous outcomes, and potential exposure.
6. Investigate an uploaded exception. Confirm the bounded read-only evidence trace, structured root cause, cited evidence, evidence score, missing evidence, and human-review requirement. An unresolved result is valid and must not be forced into a conclusion.
7. Open **Patterns**, **Runs/Evaluations**, and **Audit** to verify the current investigation signals, measured synthetic benchmark, and append-only events.
8. Open the seeded **Exceptions** compatibility queue only when demonstrating the separate legacy exception-control workflow. Use an Analyst or `ORG-OTHER` context against the API to demonstrate capability and tenant denial.

## Honest limitations

- The demo adapter is process-local by design; PostgreSQL mode provides durable source workflow, reconciliation, investigation, evaluation, idempotency, controls, and audit records.
- Development actor and organization headers are accepted only in `AUTH_MODE=development`; set `AUTH_MODE=required` to use verified bearer claims.
- The default provider is deterministic `stub` and is labelled offline. A live OpenAI-compatible provider is opt-in through configuration; this local walkthrough does not claim an external call unless credentials and an endpoint are supplied.
- Uploaded investigations do not expose hidden labels or pretend to report AI accuracy; the public evaluation screen measures deterministic reconciliation on generated data. A labeled uploaded-dataset evaluation contract is a separate product extension.
- All records are synthetic and no real financial or personal information is included.
