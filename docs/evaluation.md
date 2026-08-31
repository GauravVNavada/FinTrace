# FinTrace Evaluation Methodology

**Status:** deterministic synthetic benchmark implemented; uploaded-dataset AI scoring intentionally gated on labels · 2026-08-31

## Evaluation boundary

`EvaluationRun` is a benchmark execution and is not a `ReconciliationRun` or an `ExceptionInvestigation`. The current API measures deterministic reconciliation over fresh synthetic data with hidden labels held inside the evaluator. Uploaded investigations do not accept ground-truth labels, so the product does not report fabricated root-cause or AI-accuracy metrics for them. A future labeled evaluation contract must be introduced before such metrics are exposed.

## Purpose

The evaluator measures deterministic reconciliation against hidden synthetic ground truth. It does not use an AI provider and does not expose ground-truth labels through the normal API.

## Benchmark command

```powershell
& .\apps\api\.venv\Scripts\fintrace-evaluate.exe `
  --orders 1000 `
  --seed 42 `
  --anomaly-rate 0.30
```

## Metrics

- **Match rate:** lifecycles with `RECONCILED` or `RECONCILED_WITH_VARIANCE` divided by total lifecycles.
- **Match precision:** correctly matched lifecycles divided by lifecycles classified as matched.
- **Exception recall:** actual labeled exceptions detected divided by all actual labeled exceptions.
- **Throughput:** reconciled lifecycles per second, excluding future AI/provider latency.
- **Unresolved exceptions:** `EXCEPTION` plus `AMBIGUOUS` results requiring review.

## Interpretation rules

Fee variance and late settlement are valid reconciliation variances, not automatically financial loss. Duplicate and ambiguous payments must not be auto-matched. Unknown evidence is retained as unresolved. Benchmark output must be recorded with seed, record count, version, and command; example numbers in documentation are not production claims.

## Sprint 2 acceptance

The deterministic engine must produce one result per lifecycle, preserve integer minor-unit arithmetic, distinguish known variance from exceptions, and emit the metrics above without AI or a database connection.

## API report and release evidence

The API exposes `POST /api/v1/evaluation/run` and `GET /api/v1/evaluation/latest` for the Evaluations screen. The request is bounded to 1–10,000 orders, accepts a reproducible seed and anomaly rate, requires `Idempotency-Key`, and returns only the public report metrics. Hidden labels remain inside the evaluator and are never serialized into the API response.

The supported local release walkthrough is [`docs/demo_script.md`](demo_script.md), backed by [`scripts/demo.ps1`](../scripts/demo.ps1). It generates canonical demo artifacts and runs the evaluator with the same seed. Example output is evidence from that local run only; it is not a production accuracy claim. The evaluation API is idempotent and persists public reports when `STORAGE_BACKEND=postgres`; the local demo adapter keeps the same contract in process for isolated tests.
