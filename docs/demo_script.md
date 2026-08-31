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

1. Configure `AI_PROVIDER=gemini`, `AI_MODEL`, and a server-side Gemini key in `.env` (never commit it). Open **Investigations → Create a financial investigation**, enter a name, period, and currency, then create the workspace.
2. On **Sources**, choose **Generate and attach** with a bounded order count, seed, anomaly rate, and scenario set. The generator creates separate source exports through the same upload boundary; it is disabled after sources are attached.
3. Analyze each source. Confirm the screen identifies **Gemini · model · Live provider**, review the inferred type and unfamiliar-header mappings, edit/ignore fields when necessary, and confirm mappings explicitly. The UI discloses that bounded sample values may be sent to Gemini.
4. Open relationship review, inspect overlap, cardinality, duplicate-key, temporal, type, and amount evidence, and accept only reviewed joins.
5. Normalize and reconcile. Confirm the persisted run shows `records_consumed = records_expected` and a believable mix of reconciled, variance, exception, and ambiguous outcomes.
6. Open an exception from this investigation, then run AI investigation. Confirm the actual iterative read-only tool trace, verified supporting evidence, contradictory/missing evidence, root cause, recommendation, and latency. An unresolved result is valid and must not be forced into a conclusion.
7. Open **Evaluations** and run both **RECONCILIATION** and **AI INVESTIGATION**. Confirm the provider/model and measured metrics are distinct. Open **Audit** to verify append-only events and tool-call history.
8. The seeded **Exceptions** route is compatibility-only and is not the primary demo story.

## Honest limitations

- The demo adapter is process-local by design; PostgreSQL mode provides durable source workflow, reconciliation, investigation, evaluation, idempotency, controls, and audit records.
- Development actor and organization headers are accepted only in `AUTH_MODE=development`; set `AUTH_MODE=required` to use verified bearer claims.
- Gemini is the configured default in `.env.example`, but credentials are never committed. When Gemini is unavailable, source analysis/investigation returns an explicit unavailable status; no stub fallback is presented as AI.
- The AI evaluation cases are independently authored controlled fixtures. They are not the reconciliation generator’s hidden labels and should not be read as production prevalence.
- All records are synthetic and no real financial or personal information is included.
