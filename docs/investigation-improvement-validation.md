# Investigation improvement validation — 2026-09-05

## Follow-up: provider response recovery

The affected persisted cases showed `invalid_response / investigation_final` (ORD-20003) and Groq HTTP 400 `Failed to generate JSON` (FEB-ORD-0013). These were response-format failures, not evidence of a network outage. Failed results with tool calls were also cached instead of retried.

The fix uses final JSON synthesis after mandatory ambiguity retrieval, a 5,000-token output budget with a 12-citation instruction, one bounded JSON regeneration and one schema correction. Failed persisted assessments are retryable with new request keys regardless of lookup count. Existing IDs and same-key replay are preserved. Response validation failures have a distinct user-facing message.

Both actual persisted cases were retried through the running API with live Groq `openai/gpt-oss-120b` and saved successfully: `FIN-591BF1714F6A / RRES-804F938E4E23` and `FIN-78471A08C26C / RRES-601C903B08C2`. Both returned UNRESOLVED with `verifier_passed=true` and no failure detail. This is successful investigation with residual payment ambiguity.

Follow-up API suite: 124 passed, 3 skipped. Production build passed. Chromium tests passed for both fresh investigation and retry of a failed assessment with completed tool calls (2 tests, explicitly labeled fixtures). External provider availability and quotas remain outside the application's control; recovery is bounded rather than an unlimited retry loop.

The reported assessment repeated ambiguity without collecting evidence. The production provider could finalize with zero tools, while the UI hid citations and used a generic payment failure heading for every unresolved result.

The updated ambiguity path collects order, candidate payments, invoices, settlements and refunds before synthesis. Groq receives those field facts and instructions to compare actual candidates. The verifier requires order, each candidate and settlement linkage/absence citations. The UI displays the assessment, citations, specific missing evidence and provider identity. Lookup details remain expandable. Zero-lookup stored results can be explicitly refreshed with a new idempotency key, preserving the persisted investigation ID.

## Verification

- API suite: 120 passed, 3 skipped, including legacy refresh and replay behavior.
- Web TypeScript check: passed.
- Production web build: passed.
- Chromium golden path: passed (1 test). This browser check uses explicitly labeled API fixtures and checks navigation, investigation rendering, citations, review request and audit. Screenshot: [investigation result](../test-results/redesign-ambiguous-case.png). The fixture browser run is separate from the real Groq smoke below.
- Live smoke: Groq / openai/gpt-oss-120b, synthetic in-memory lifecycle, no database writes. Five baseline lookups preceded synthesis. The first attempt revealed abbreviated provider citations; the prompt was tightened to require complete field predicates. The subsequent response passed verification with 14 citations.
- The live response identified PAY-A and PAY-B, equal supplied amounts and different capture times, and SET-A linked to PAY-A. It requested candidate gateway logs and settlement evidence. It remained UNRESOLVED and did not select a payment.

The live smoke checks provider synthesis and source-field verification, not the user's persisted February upload. The verifier checks structured fields and required evidence coverage; it does not prove every free-text hypothesis. Ambiguity intentionally remains unresolved when the distinguishing evidence is absent.
