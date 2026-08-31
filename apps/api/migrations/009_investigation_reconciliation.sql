-- Sprint 4: deterministic reconciliation runs scoped to an immutable dataset version.
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'uq_dataset_versions_org_id'
  ) THEN
    ALTER TABLE dataset_versions
      ADD CONSTRAINT uq_dataset_versions_org_id UNIQUE (organization_id, id);
  END IF;
END $$;

CREATE TABLE financial_reconciliation_runs (
  id VARCHAR(128) PRIMARY KEY,
  organization_id UUID NOT NULL,
  financial_investigation_id UUID NOT NULL,
  dataset_version_id VARCHAR(128) NOT NULL,
  status VARCHAR(32) NOT NULL CHECK (status IN ('COMPLETED', 'FAILED')),
  lifecycle_count INTEGER NOT NULL CHECK (lifecycle_count >= 0),
  reconciled_count INTEGER NOT NULL CHECK (reconciled_count >= 0),
  exception_count INTEGER NOT NULL CHECK (exception_count >= 0),
  ambiguous_count INTEGER NOT NULL CHECK (ambiguous_count >= 0),
  open_exposure_minor BIGINT NOT NULL CHECK (open_exposure_minor >= 0),
  started_at TIMESTAMPTZ NOT NULL,
  completed_at TIMESTAMPTZ,
  CONSTRAINT uq_fin_recon_runs_org_id UNIQUE (organization_id, id),
  CONSTRAINT fk_fin_recon_run_investigation_org FOREIGN KEY (organization_id, financial_investigation_id)
    REFERENCES financial_investigations (organization_id, id) ON DELETE CASCADE,
  CONSTRAINT fk_fin_recon_run_dataset_org FOREIGN KEY (organization_id, dataset_version_id)
    REFERENCES dataset_versions (organization_id, id) ON DELETE CASCADE
);

CREATE TABLE financial_reconciliation_results (
  id VARCHAR(128) PRIMARY KEY,
  organization_id UUID NOT NULL,
  run_id VARCHAR(128) NOT NULL,
  order_id VARCHAR(200) NOT NULL,
  status VARCHAR(32) NOT NULL,
  exception_type VARCHAR(128),
  severity VARCHAR(32) NOT NULL,
  exposure_minor BIGINT NOT NULL CHECK (exposure_minor >= 0),
  findings JSONB NOT NULL,
  UNIQUE (organization_id, run_id, order_id),
  CONSTRAINT uq_fin_recon_results_org_id UNIQUE (organization_id, id),
  CONSTRAINT fk_fin_recon_result_run_org FOREIGN KEY (organization_id, run_id)
    REFERENCES financial_reconciliation_runs (organization_id, id) ON DELETE CASCADE
);

CREATE INDEX idx_fin_recon_runs_investigation
  ON financial_reconciliation_runs (organization_id, financial_investigation_id, started_at DESC);
CREATE INDEX idx_fin_recon_results_run
  ON financial_reconciliation_results (organization_id, run_id, order_id);
