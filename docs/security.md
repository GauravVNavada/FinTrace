# FinTrace Security Design

**Status:** MVP security baseline · 2026-08-30

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

The current API scaffold requires an organization context header for development only. Before deployment, replace it with verified session claims including subject, organization, role, issuer, audience, expiry, and revocation behavior. Never treat a browser-provided organization header as authentication.

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

## 3. Data protection

All current records are synthetic. A production implementation must classify PII and financial data, encrypt transport and storage, redact logs, define retention/deletion rules, and restrict support access. Secrets live in environment/secret-manager configuration only.

## 4. Security verification checklist

- [ ] Authenticated request claims are verified.
- [ ] Object-level tenant filter is present on every repository query.
- [x] Approval thresholds are tested server-side.
- [x] Replay with the same idempotency key is harmless.
- [x] Prompt-injection fixture has no effect.
- [x] Malformed model output becomes a safe failure.
- [x] Logs contain IDs and outcomes, not source payloads or secrets.
- [ ] Dependency audit and secret scan run in CI.
