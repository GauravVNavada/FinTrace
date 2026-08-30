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

PostgreSQL migrations are defined in `apps/api/migrations/001_initial_schema.sql`, `002_controls_and_idempotency.sql`, and `003_exception_external_ids.sql`. If Docker is available, start the database with `docker compose up -d postgres`, then run `fintrace-migrate` and `fintrace-seed` from `apps/api`. Set `STORAGE_BACKEND=postgres` before starting Uvicorn to exercise the database repository. Application startup must not mutate schema; migrations run explicitly in CI/deployment.

The repository includes `compose.yaml` for a local PostgreSQL 16 instance. This workstation does not currently have Docker installed, so the database-backed path is implemented but its live migration/seed check remains environment-dependent.

## Troubleshooting

- If Next build output is stale, stop the dev server and rerun the build; do not delete source files.
- If API imports fail, activate the `apps/api/.venv` environment and install the editable package.
- If `STORAGE_BACKEND=demo`, the dashboard and remaining static screens show deterministic demo data by design. The PostgreSQL repository path currently covers canonical API reads; replacing the remaining frontend demo adapter is tracked separately in `docs/phase_scope.md`.
