# FinTrace Security Design

## Final local validation — 2026-09-05

See [final-validation.md](final-validation.md) for tested behavior and explicit remaining production limitations. Inventory investigations precollect bounded read-only evidence and allow one verification-correction turn, never bypassing the verifier. Failed verification remains unresolved and can be retried with a new idempotency key. Uploaded lifecycle reads are authenticated tenant/run/result scoped. Development authentication remains local-demo-only; no financial execution integration is implied.

**Status:** MVP security baseline plus tenant-integrity and replay hardening · 2026-09-03

## File-ingestion security requirements

The Sprint 1 upload boundary enforces an allowlisted extension/content policy for CSV and XLSX, maximum request and extracted-row/column limits, safe generated storage names, organization/investigation ownership checks, malformed/empty file rejection, temporary-storage cleanup, and bounded parsing. Original filenames are display metadata only. Spreadsheet formulas must not be exported back as executable formulas, and uploaded cell text must be treated as untrusted data for both UI rendering and AI prompts. Classification, mapping, and AI use are not performed in Sprint 1.

## 1. Threat model

### Assets

- Financial amounts, payment and settlement references.
- Operational records including inventory and employee action metadata.
- Organization membership and approval authority.
- Investigation results and immutable audit history.
- Provider credentials and database credentials.

### Trust boundaries

```text
Browser -> API authentication boundary
API -> organization-scoped repository
API -> AI provider boundary
Source records -> untrusted data boundary
API -> database transaction boundary
API -> audit log boundary
```

### Attacker capabilities considered

- Authenticated analyst attempting to access another organization.
- Authenticated analyst attempting to approve beyond role or threshold.
- Malicious source-record text attempting prompt injection.
- Unauthenticated client sending malformed or replayed requests.
- Provider returning malformed, unsupported, or overreaching output.

## 2. Required controls

### Authentication

The API verifies HS256 bearer claims (`sub`, `organization_id`, `role`, `iss`, `aud`, `iat`, and `exp`) when a bearer token is provided. Staging and production force `AUTH_MODE=required` and reject header-only tenant/actor context; a strong non-default signing secret is required. Production should place the signing key behind a secret manager and add issuer-side revocation/key rotation.

### Authorization

Authorization must be checked at the service/repository boundary for the final resource access. The route guard alone is insufficient. Approval endpoints must evaluate capability, amount threshold, exception type, current state, and idempotency key inside one transaction.

### Tenant isolation

Every business table has `organization_id`. Repositories require organization scope. Unique constraints and indexes should include organization context where identifiers are not globally unique. Tool calls receive the same context and cannot query arbitrary SQL.

### Input validation

Use typed request schemas, bounded pagination, enum allowlists, maximum search lengths, and strict identifier formats. Reject unknown fields on write models where mass assignment could cause impact.

### AI safety

Tool results are delimited as data. Source-record text is never treated as instructions. Tools are read-only, allowlisted, parameter validated, rate bounded, and logged. AI output is schema-validated and independently verified before display. No model output can directly execute a financial action.

### Web and API hardening

- Restrict CORS to configured origins.
- Use secure, HttpOnly, SameSite cookies for browser sessions.
- Add CSP, HSTS, frame-ancestors, Referrer-Policy, and content-type protection in deployment.
- Apply rate limits to authentication, investigation, and write endpoints.
- Return stable errors without stack traces or secrets.
- Set request, connection, and provider timeouts.

The API also emits content-type, frame, referrer, and permissions headers on every response, with HSTS enabled in production. Source workflow writes reserve a tenant-scoped request-hash lease before work; expired pending leases are reclaimable, while a key reused for a different operation is rejected.

## 3. Data protection

All current records are synthetic. A production implementation must classify PII and financial data, encrypt transport and storage, redact logs, define retention/deletion rules, and restrict support access. Secrets live in environment/secret-manager configuration only.

## 4. Security verification checklist

- [x] Authenticated request claims are verified when bearer authentication is used; required mode rejects header-only context.
- [x] Object-level tenant filter is present on every repository query; the demo adapter also returns no seeded data for unknown tenants.
- [x] Approval thresholds are tested server-side.
- [x] Replay with the same idempotency key is harmless.
- [x] Pending idempotency work has a bounded recovery lease in demo and PostgreSQL adapters.
- [x] Parent/child financial records enforce organization-consistent foreign keys in migration 014.
- [x] Security response headers are emitted by the API middleware.
- [x] Prompt-injection fixture has no effect.
- [x] Malformed model output becomes a safe failure.
- [x] Logs contain IDs and outcomes, not source payloads or secrets.
- [x] Dependency audit and secret scan run in CI. Package audits and Gitleaks are configured.
