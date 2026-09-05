# Repository cleanup and validation

## Preserved behavior

Automatic high-confidence intake, per-file error recovery, successful-upload deduplication, integer-minor-unit normalization, deterministic matching, evidence-backed investigation, and the existing close/results experience remain in place. No financial records or original external source files are deleted or reseeded.

## Home

Home selects the organization’s most recently started non-stale reconciliation run, not the newest-created close. A newly created empty close cannot replace completed results. Failed runs remain visible as requiring review. Selection refreshes on window focus and every 30 seconds. Explicit close links still select their named close. With no run, Home says “Not run yet”; it does not imply readiness.

## Structure and naming

- `systhantic data/` contains eight calendar-month folders with seven inputs each and a SHA-256 manifest. The original external collection is unchanged.
- Automated monthly intake and live March tests use repository-relative inputs.
- Local role login is `/api/v1/auth/local-login`; source-generation adapters use `sample` naming. The compatibility workspace route is `/review-workspace`.
- Migration 012 has a neutral filename. Existing installations adopt the known checksum-approved revision as ledger metadata only; its SQL is not rerun. Unknown checksums remain a hard error. SQL files use LF line endings for stable checksums.
- Terminology cleanup applies to maintained source and documentation, not immutable Git history, installed dependencies, or pre-existing database audit records.

## Validation

Validated on 2026-09-05:

- API: **138 passed, 3 skipped**. The skipped suite requires a separate PostgreSQL test database; the live browser test exercised the running PostgreSQL-backed API. All eight packaged periods passed upload → mapping → normalization → reconciliation.
- Browser: **3 passed**, including two fixture regression paths and real March upload, identical-file deduplication, reconciliation, three live Groq investigations, citation verification, and latest-run Home. Fixture tests also put a newer empty close before the close with results.
- Production Next.js build, semantic UI architecture checks, and web loader regression passed.
- Existing database migration command reported **0 migrations applied**; migration 012 was adopted without rerunning its SQL.
- All 56 packaged input files match their originals by SHA-256.

Final rebuilt-application validation close: `FIN-59FC490F4D97` (all three browser tests passed again). March produced 515/515 accounted-for records, 77 reconciled lifecycles, 2 needing decisions, 1 needing evidence, and ₹11,896 potential exposure. Home displayed those same values. [Home screenshot](e2e-screenshots/home-latest-run.png).

The accidental root `--help` generated-hook directory and `debug.log` were moved to `C:/Users/USER/AppData/Local/Temp/fintrace-cleanup-74921060e1f44a1f9301012bcf6a378a` for recovery. Dependencies, current builds, financial data, and original monthly exports were retained.

This is a locally validated release cleanup, not a claim that development authentication or local database credentials are suitable for public deployment. Production deployment still requires the controls described in security and deployment documentation.
