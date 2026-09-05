# Final March validation — 5 September 2026

**Sample-ready tested close:** [March 2026 Final Validation](http://localhost:3002/investigations/FIN-5A9FFF5BD2BD/reconciliation). The local web and API servers are running.

## Recorded browser steps

1. Log in as controller and create March 1–31, 2026 close — [screenshot](e2e-screenshots/march-01-created.png).
2. Select all seven original March files, including XLSX exports. Wait for all files understood — [screenshot](e2e-screenshots/march-02-uploaded.png).
3. Upload the same files again: still seven sources. Run close: all 515 records accounted for — [results](e2e-screenshots/march-03-results.png).
4. Open MAR-ORD-0036 and run live investigation. The missing payment linkage remains unresolved — [AI evidence](e2e-screenshots/march-04-live-ai.png).
5. Open MAR-ORD-0010. Inspect refund and sold inventory cost; run Groq investigation for the absent return — [missing return](e2e-screenshots/march-05-inventory.png).
6. Open MAR-ORD-0013. Compare sale quantity 2 with return quantity 1; run Groq investigation and verify provider, SUPPORTED status and verifier success — [quantity investigation](e2e-screenshots/march-06-quantity-ai.png).

Final browser run: **3 passed in 39.6s**, including the two offline UI regression cases and one real live March journey. A further web-loader regression passed. The final production build and UI architecture checks passed. Screenshots are preserved here independently of the test runner’s temporary output directory.

## What was corrected

- Expanded source-scoped aliases across January–August. Complete specialist signatures now outrank filename fragments without reclassifying incomplete payments as healthy sales.
- Fixed Excel conversion at the root: `CapturedValue` and `RefundedAmount` were being interpreted as dates. Timestamp aliases such as `InvoiceCreated` now convert Excel serials without touching money.
- Upload batches continue after per-file failures, refresh the list, and disable Run close until the entire batch is ready. Manual recovery can select any source column and any valid field. A same-name file with changed content is rejected explicitly; successful originals are preserved.
- Added tenant/run/result-scoped lifecycle retrieval from normalized uploaded records. Removed exposure-as-order/payment substitutions. Sale and return inventory show SKU, quantity, cost and value.
- Added payment amount/status/currency and settlement gross/net controls; multiple settlements/refunds require review. Ambiguity no longer depends on `PAY-AMB` ID prefixes. Inventory missing-return exposure uses available cost, not refund sales value; unknown valuation is not invented.
- Open deterministic exceptions now appear as Needs decision, not automatically Explained. Home and global Attention no longer hardwire an August close.
- Corrected evaluation scenario-name comparisons and employee-action joins. Fixed auditor sample login.
- Inventory AI now retrieves order, refund, inventory and invoice evidence before synthesis. One bounded correction turn may repair rejected citations; the same verifier remains mandatory. A failed verification can be explicitly retried. No fixture is represented as live AI.

## Verification

- API regression suite: **136 passed, 3 skipped** (environment-dependent tests).
- All eight real monthly export directories: seven CSV/XLSX files each passed upload, automatic mapping, confirmation, normalization and reconciliation through the API. Tests do not read ground truth as engine input. Tenant-isolation checks cover the new lifecycle endpoint.
- Production Next.js build/type checking and UI architecture checks passed.
- Two browser fixture tests cover controller navigation, ambiguous evidence, explicit non-live provider labeling, retry, attention and audit.
- A real Chromium browser test uses the running PostgreSQL API and live Groq: login → create March close → upload all seven exports → repeat upload with no duplicate sources → Run close → inspect results → investigate ambiguity → investigate missing return → investigate quantity mismatch. Screenshots accompany each major step. A headed Chromium launch was unavailable (`spawn UNKNOWN`); real headless Chromium completed the browser workflow.
- Evaluation on the deterministic 500-order/seed-42 benchmark reports 100% match precision and exception precision/recall after label/join/rounding corrections. This is synthetic benchmark coverage, **not measured production accuracy**. Financial resolution safety was not measured by this benchmark.

## March sample facts

The March exports contain **515 records, 80 lifecycles: 77 reconciled, 2 needing a decision, 1 needing evidence**.

| Order | Finding | What the evidence establishes |
|---|---|---|
| MAR-ORD-0010 | Missing inventory return | A full ₹6,250 refund exists but no return movement; sold inventory cost at risk is ₹1,812.50. Live Groq produced a supported, verified assessment. |
| MAR-ORD-0013 | Inventory quantity mismatch | Two units sold, one returned; cost difference ₹1,433.50. Live Groq produced a supported assessment after the evidence collection correction. |
| MAR-ORD-0036 | Ambiguous payment association | Two ₹8,650 payment candidates, only one linked settlement. The AI must remain unresolved; an external gateway reference is needed. |

Confidence is the existing deterministic **evidence coverage score**, not the probability that a narrative is correct. It can vary with the provider’s selected citations. SUPPORTED means the cited conclusion passed current verification; it does not approve a refund or other financial action.

## Scope and remaining audit limitations

This pass fixes the reproduced intake, misleading evidence display, observed reconciliation gaps and local sample blockers. It is **not a claim that every item in the supplied adversarial audit is closed**.

- Arbitrary unknown/malformed/ambiguous exports may still require review. Silently accepting them would be unsafe.
- Development authentication/sample roles are for a trusted local machine. Production requires required-mode signed identity, non-default secret, deployment security review and real identity provisioning.
- Large-dataset performance, background AI jobs, complete pagination above the current bounded 10,000-result fetch, stale-run invalidation and orphan-record quarantine remain production work. Incomplete lifecycle construction fails closed instead of declaring a clean close.
- Multi-SKU/partial-return allocation, full settlement/refund allocation and production accounting policies need broader contracts and benchmark coverage; multiple settlements/refunds are flagged for review.
- Approval requests are local workflow records, not real payment execution. No production bank/ERP writeback or multi-person approval deployment was exercised.
- Citation field verification is not a proof of every sentence in free-form provider text. External events absent from the uploaded dataset remain unknown. Groq outages/rate limits cannot be permanently eliminated; failures must remain explicit and retryable where appropriate.

No existing close or original user export was deleted to obtain these results. Browser validation created separate March test closes.
