# FinTrace Local Development

## Prerequisites

- Node.js 24+
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
uvicorn app.main:app --reload --port 8001
```

The current scaffold exposes `/health`, dashboard/exception/lifecycle reads, investigation routes, controls/audit routes, and analytics routes. Development requests require `X-Organization-Id`; this is intentionally temporary and must be replaced with verified authentication claims before deployment. `AI_PROVIDER=stub` is the safe deterministic default; no external provider is called locally.

Open the web app at `http://localhost:3000`, `http://127.0.0.1:3000`, `http://localhost:3002`, or `http://127.0.0.1:3002`. The development API default allows these loopback origins; production deployments must set an explicit `ALLOWED_ORIGINS` value. The web client defaults to `http://127.0.0.1:8001` for the local API.

## Environment rules

- Never commit `.env` files.
- Keep client-exposed variables limited to public configuration.
- Do not put service-role credentials in `apps/web`.
- Use separate development/test databases.

## Database phase

PostgreSQL migrations are defined in `apps/api/migrations/001_initial_schema.sql` through `004_workflow_persistence.sql`. Start the database with `docker compose up -d postgres`, then run `fintrace-migrate` and `fintrace-seed` from `apps/api`. The Compose database is published on host port `55432` to avoid colliding with a local PostgreSQL installation; use `postgresql://fintrace:fintrace@localhost:55432/fintrace`. Set `STORAGE_BACKEND=postgres` before starting Uvicorn to exercise durable workflow state. Application startup must not mutate schema; migrations run explicitly in CI/deployment.

The repository includes `compose.yaml` for a local PostgreSQL 16 instance. The Docker-backed migration, seed, readiness, canonical reads, investigation replay, evaluation replay, approval, and audit smoke checks have been run locally.

## Troubleshooting

- If Next build output is stale, stop the dev server and rerun the build; do not delete source files.
- Do not run `pnpm dev` and `pnpm build` concurrently for `apps/web`; both use `.next`, and the production build can replace the dev stylesheet manifest. If the UI appears as unstyled HTML after a build, stop and restart the web dev server.
- If API imports fail, activate the `apps/api/.venv` environment and install the editable package.
- If `STORAGE_BACKEND=demo`, isolated local screens use deterministic demo data by design. For the full local path, run PostgreSQL and point `NEXT_PUBLIC_API_BASE_URL` at the API port.
