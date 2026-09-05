-- P0 release contract: complete input accounting, exposure categories,
-- provider metadata, and first-class uploaded investigation traces.

ALTER TABLE financial_reconciliation_runs
  ADD COLUMN IF NOT EXISTS records_expected INTEGER NOT NULL DEFAULT 0 CHECK (records_expected >= 0),
  ADD COLUMN IF NOT EXISTS records_loaded INTEGER NOT NULL DEFAULT 0 CHECK (records_loaded >= 0),
  ADD COLUMN IF NOT EXISTS records_consumed INTEGER NOT NULL DEFAULT 0 CHECK (records_consumed >= 0),
  ADD COLUMN IF NOT EXISTS orphan_record_count INTEGER NOT NULL DEFAULT 0 CHECK (orphan_record_count >= 0),
  ADD COLUMN IF NOT EXISTS rejected_record_count INTEGER NOT NULL DEFAULT 0 CHECK (rejected_record_count >= 0),
  ADD COLUMN IF NOT EXISTS failure_reason VARCHAR(500),
  ADD COLUMN IF NOT EXISTS is_stale BOOLEAN NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS stale_reason VARCHAR(500);

ALTER TABLE financial_reconciliation_runs
  DROP CONSTRAINT IF EXISTS financial_reconciliation_runs_status_check;
ALTER TABLE financial_reconciliation_runs
  ADD CONSTRAINT financial_reconciliation_runs_status_check
  CHECK (status IN ('COMPLETED', 'FAILED', 'INCOMPLETE'));

ALTER TABLE financial_reconciliation_results
  ADD COLUMN IF NOT EXISTS exposure_category VARCHAR(32) NOT NULL DEFAULT 'DATA_QUALITY';

ALTER TABLE source_analyses
  ADD COLUMN IF NOT EXISTS provider VARCHAR(64) NOT NULL DEFAULT 'offline-deterministic',
  ADD COLUMN IF NOT EXISTS model VARCHAR(128) NOT NULL DEFAULT 'none';

ALTER TABLE relationship_proposals
  ADD COLUMN IF NOT EXISTS confidence_label VARCHAR(16) NOT NULL DEFAULT 'LOW',
  ADD COLUMN IF NOT EXISTS left_columns JSONB NOT NULL DEFAULT '[]'::jsonb,
  ADD COLUMN IF NOT EXISTS right_columns JSONB NOT NULL DEFAULT '[]'::jsonb,
  ADD COLUMN IF NOT EXISTS value_overlap_percent NUMERIC(6,2) NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS duplicate_key_rate_percent NUMERIC(6,2) NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS cardinality VARCHAR(16) NOT NULL DEFAULT 'UNKNOWN',
  ADD COLUMN IF NOT EXISTS type_compatibility VARCHAR(16) NOT NULL DEFAULT 'UNKNOWN',
  ADD COLUMN IF NOT EXISTS temporal_consistency_percent NUMERIC(6,2),
  ADD COLUMN IF NOT EXISTS amount_agreement_percent NUMERIC(6,2);

ALTER TABLE financial_exception_investigations
  ADD COLUMN IF NOT EXISTS provider VARCHAR(64),
  ADD COLUMN IF NOT EXISTS model VARCHAR(128),
  ADD COLUMN IF NOT EXISTS prompt_version VARCHAR(64),
  ADD COLUMN IF NOT EXISTS started_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS completed_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS latency_ms INTEGER,
  ADD COLUMN IF NOT EXISTS verifier_passed BOOLEAN NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS verifier_issues JSONB NOT NULL DEFAULT '[]'::jsonb;

-- Preserve old financial rows, but keep them out of the active sample state until rerun
-- through complete input accounting. This annotates history; it does not rewrite results.
UPDATE financial_reconciliation_runs rr
   SET is_stale = true,
       stale_reason = COALESCE(rr.stale_reason,
         'Legacy run predates complete input accounting; rerun this investigation before using it as sample state.')
 WHERE rr.status = 'COMPLETED'
   AND rr.records_expected = 0;

CREATE TABLE IF NOT EXISTS financial_exception_investigation_tool_calls (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID NOT NULL REFERENCES organizations(id),
  financial_exception_investigation_id VARCHAR(128) NOT NULL,
  sequence_no SMALLINT NOT NULL CHECK (sequence_no > 0),
  name VARCHAR(100) NOT NULL,
  arguments JSONB NOT NULL DEFAULT '{}'::jsonb,
  result_record_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
  result_summary VARCHAR(500) NOT NULL,
  duration_ms INTEGER NOT NULL CHECK (duration_ms >= 0),
  status VARCHAR(30) NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (organization_id, financial_exception_investigation_id, sequence_no),
  CONSTRAINT fk_fin_exc_tool_call_org FOREIGN KEY (organization_id, financial_exception_investigation_id)
    REFERENCES financial_exception_investigations (organization_id, id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_fin_exc_tool_calls_investigation
  ON financial_exception_investigation_tool_calls
    (organization_id, financial_exception_investigation_id, sequence_no);
