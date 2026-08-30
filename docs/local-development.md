# FinTrace Local Development

## Prerequisites

- Node.js 20+
- pnpm 9+
- Python 3.12+ for `apps/api`
- PostgreSQL 16+ for the persistent phase

## JavaScript workspace

```bash
pnpm install --ignore-scripts
pnpm dev
pnpm typecheck
pnpm build
```

`pnpm install --ignore-scripts` is safe for the current UI foundation because no native build step is required by application code. Review and approve dependency build scripts explicitly when the API/database phase adds one.

After a normal dependency installation, the root `prepare` script installs Husky hooks. If hooks are missing in a local checkout, run `pnpm prepare` once. Do not bypass hooks for normal changes; use a documented exception only when a release or emergency workflow requires it.

## API service

```bash
cd apps/api
python -m venv .venv
# Windows: .venv\\Scripts\\Activate.ps1
pip install -e ".[dev]"
copy .env.example .env
uvicorn app.main:app --reload --port 8000
```

The current scaffold exposes `/health`, dashboard/exception/lifecycle reads, investigation routes, controls/audit routes, and analytics routes. Development requests require `X-Organization-Id`; this is intentionally temporary and must be replaced with verified authentication claims before deployment. `AI_PROVIDER=stub` is the safe deterministic default; no external provider is called locally.

Open the web app at `http://localhost:3000` or `http://127.0.0.1:3000`. The development API default allows both loopback origins; production deployments must set an explicit `ALLOWED_ORIGINS` value.

## Environment rules

- Never commit `.env` files.
- Keep client-exposed variables limited to public configuration.
- Do not put service-role credentials in `apps/web`.
- Use separate development/test databases.

## Database phase

PostgreSQL migrations are defined in `apps/api/migrations/001_initial_schema.sql` and `002_controls_and_idempotency.sql`, but are not applied locally until PostgreSQL is provisioned. Application startup must not mutate schema. Migrations run explicitly in CI/deployment.

## Troubleshooting

- If Next build output is stale, stop the dev server and rerun the build; do not delete source files.
- If API imports fail, activate the `apps/api/.venv` environment and install the editable package.
- If the dashboard shows demo data, that is expected until the API adapter phase is complete.
