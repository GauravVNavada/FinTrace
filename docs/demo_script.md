# FinTrace Demo Script

**Status:** Local release walkthrough for the completed Sprints 0–7 synthetic product path · 2026-08-31

## Demo modes

The walkthrough demonstrates a fresh synthetic financial investigation. Use `Launch Flagship Demo` to create or resume the prepared workspace and open its live overview, or use a fresh investigation for manual source generation/upload. The web flow supports source generation or upload, bounded analysis, mapping edits, explicit confirmation, relationship decisions, immutable dataset normalization, deterministic reconciliation, uploaded-result evidence investigation, advisory patterns, evaluation, and audit. The legacy `/exceptions` queue is a separate seeded compatibility workflow; uploaded investigation results remain in their owning workspace. `Judge Demo · Controller` is a clearly labelled local review identity that uses the normal API RBAC checks to expose judging surfaces.

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

Open `http://localhost:3002`.

## Five-minute walkthrough

1. Configure `STORAGE_BACKEND=postgres`, `AI_PROVIDER=gemini`, `AI_MODEL=gemini-2.5-flash-lite`, and `GEMINI_API_KEY` in the API `.env` (never commit credentials). Open the product and choose **Judge Demo · Controller**. The signed demo identity uses the normal API RBAC path.
2. On **Sources**, choose **Generate and attach** with a bounded order count, seed, anomaly rate, and scenario set. The generator creates separate source exports through the same upload boundary; it is disabled after sources are attached.
3. Before starting AI work, confirm the investigation screen reports **Gemini connected** from the provider-health check. If it reports unavailable or not configured, fix the provider configuration before continuing. Analyze each source, confirm the screen identifies **Gemini · model · Live provider**, review the inferred type and unfamiliar-header mappings, edit/ignore fields when necessary, and confirm mappings explicitly. The UI discloses that bounded sample values may be sent to Gemini.
4. Open relationship review, inspect overlap, cardinality, duplicate-key, temporal, type, and amount evidence, and accept only reviewed joins.
5. Normalize and reconcile. Confirm the persisted run shows `records_consumed = records_expected` and a believable mix of reconciled, variance, exception, and ambiguous outcomes.
6. Open an exception from this investigation, then run AI investigation. Confirm the actual iterative read-only tool trace, verified supporting evidence, contradictory/missing evidence, root cause, recommendation, and latency. An unresolved result is valid and must not be forced into a conclusion.
7. Open **Evaluations** and run both **RECONCILIATION** and **AI INVESTIGATION**. Confirm the provider/model and measured metrics are distinct. Open **Audit** to verify append-only events and tool-call history.
8. The seeded `/exceptions` route is compatibility-only and is not the primary demo story.

For the recording, use **Launch Flagship Demo** from the empty Overview state. It creates/resumes the reproducible PostgreSQL-backed `FLAGSHIP_FINANCE_REVIEW` workspace, performs the real source-to-reconciliation workflow, and does not spend live AI quota until an exception is explicitly investigated.

## Honest limitations

- The demo adapter is process-local by design; PostgreSQL mode provides durable source workflow, reconciliation, investigation, evaluation, idempotency, controls, and audit records.
- Development actor and organization headers are accepted only in `AUTH_MODE=development`; set `AUTH_MODE=required` to use verified bearer claims.
- Gemini is the configured default in `.env.example`, but credentials are never committed. Provider health distinguishes connected, unavailable, and not configured states. When Gemini is unavailable, source analysis/investigation returns an explicit unavailable/`FAILED` status; no stub fallback is presented as AI.
- The AI evaluation cases are independently authored controlled fixtures. They are not the reconciliation generator’s hidden labels and should not be read as production prevalence.
- All records are synthetic and no real financial or personal information is included.
