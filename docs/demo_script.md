# FinTrace Demo Script

**Status:** Local release walkthrough for the completed Sprints 0–7 synthetic product path · 2026-08-31

## Demo modes

The controller walkthrough uses one canonical PostgreSQL-backed investigation: the validated August close from `C:\Users\USER\Desktop\FinTrace_Independent_Test_Data`. It contains 90 lifecycles and 544 normalized source records. The web flow presents that same close across Home, Closes, Results, Attention, case detail, and Audit. The legacy `/exceptions` queue is a separate seeded compatibility workflow and is not part of the recording story. `Judge Demo · Controller` is a clearly labelled local review identity that uses the normal API RBAC checks to expose judging surfaces.

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

1. Configure `STORAGE_BACKEND=postgres`, `AI_PROVIDER=groq`, `AI_MODEL=openai/gpt-oss-120b`, and `GROQ_API_KEY` in the API `.env` (never commit credentials). Open the product and choose **Judge Demo · Controller**.
2. Open **Closes** and select the canonical August close. Home should show `544 / 544` records accounted for, `71` reconciled, `5` expected variance, `12` explained, `2` needs evidence, and `₹59,293` potential exposure.
3. Show **Data**, then **Results**. Normal setup remains compact; only uncertain mappings or connections open review.
4. Open the explained missing-settlement case. Show **What happened**, the `EXPECTED BUT MISSING` settlement lifecycle state, verified evidence, **How FinTrace established this**, and the payment-operations follow-up. Do not start another investigation.
5. Open the ambiguous payment case. Show both candidate payments, `AMBIGUOUS` lifecycle states, `NEEDS EVIDENCE`, and the request for a unique transaction reference. Do not guess or request a controller decision.
6. Open **Attention**. Every row must be actionable and use `NEEDS EVIDENCE`, `NEEDS DECISION`, or `APPROVAL REQUIRED`; explained findings stay out.
7. Open **Audit** briefly to verify the persisted investigation trace and follow-up event.

For the recording, use the prepared canonical August close from the Closes screen. Do not use the synthetic `Launch Flagship Demo` workspace because its metrics are not the canonical recording dataset.

## Honest limitations

- The demo adapter is process-local by design; PostgreSQL mode provides durable source workflow, reconciliation, investigation, evaluation, idempotency, controls, and audit records.
- Development actor and organization headers are accepted only in `AUTH_MODE=development`; set `AUTH_MODE=required` to use verified bearer claims.
- Gemini is the configured default in `.env.example`, but credentials are never committed. Provider health distinguishes connected, unavailable, and not configured states. When Gemini is unavailable, source analysis/investigation returns an explicit unavailable/`FAILED` status; no stub fallback is presented as AI.
- The AI evaluation cases are independently authored controlled fixtures. They are not the reconciliation generator’s hidden labels and should not be read as production prevalence.
- All records are synthetic and no real financial or personal information is included.
