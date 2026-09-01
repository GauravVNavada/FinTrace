-- Provider-health and live investigation failure diagnostics.

ALTER TABLE financial_exception_investigations
  ADD COLUMN IF NOT EXISTS provider_error_category VARCHAR(100),
  ADD COLUMN IF NOT EXISTS provider_retryable BOOLEAN,
  ADD COLUMN IF NOT EXISTS failure_stage VARCHAR(100),
  ADD COLUMN IF NOT EXISTS failure_iteration SMALLINT,
  ADD COLUMN IF NOT EXISTS failure_detail VARCHAR(500);

ALTER TABLE financial_exception_investigation_tool_calls
  ADD COLUMN IF NOT EXISTS provider VARCHAR(64) NOT NULL DEFAULT 'unknown',
  ADD COLUMN IF NOT EXISTS model VARCHAR(128) NOT NULL DEFAULT 'unknown';
