# FinTrace Demo Script

**Status:** Sprint 5 release evidence · 2026-08-30

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
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

Terminal 2:

```powershell
pnpm dev
```

Open `http://localhost:3000`.

## Five-minute walkthrough

1. Open Overview and explain that matching, exposure, severity, and approval policy are deterministic.
2. Open `EXC-1042` and inspect the lifecycle records, missing inventory/ERP events, and rule findings.
3. Trigger the bounded investigation. Confirm cited evidence, server-computed score, read-only tool calls, and human-review requirement.
4. Request `REQUEST_INVENTORY_VERIFICATION` with an Analyst context, then approve with a Controller context. Confirm the approval is simulated and the exception source state is unchanged.
5. Open Patterns and Evaluation to show deterministic recurrence signals and benchmark output. Open Audit to show organization-scoped control events.
6. Use the API with `ORG-OTHER` or an Analyst approval header to demonstrate tenant and capability denial.

## Honest limitations

- The demo adapter is process-local by design; the documented full path uses Docker PostgreSQL for durable controls, investigations, evaluations, idempotency, and audit records.
- Development actor and organization headers are accepted only in `AUTH_MODE=development`; set `AUTH_MODE=required` to use verified bearer claims.
- The default provider is deterministic `stub`; no external AI provider is contacted.
- All records are synthetic and no real financial or personal information is included.
