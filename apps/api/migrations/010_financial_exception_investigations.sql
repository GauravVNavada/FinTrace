-- Sprint 5: bounded investigation results for uploaded reconciliation exceptions.
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'uq_fin_recon_results_org_id'
  ) THEN
    ALTER TABLE financial_reconciliation_results
      ADD CONSTRAINT uq_fin_recon_results_org_id UNIQUE (organization_id, id);
  END IF;
END $$;

CREATE TABLE financial_exception_investigations (
  id VARCHAR(128) PRIMARY KEY,
  organization_id UUID NOT NULL,
  financial_investigation_id UUID NOT NULL,
  reconciliation_result_id VARCHAR(128) NOT NULL,
  status VARCHAR(32) NOT NULL CHECK (status IN ('SUPPORTED', 'UNRESOLVED', 'FAILED')),
  response JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL,
  UNIQUE (organization_id, id),
  UNIQUE (organization_id, reconciliation_result_id),
  CONSTRAINT fk_fin_exc_investigation_org FOREIGN KEY (organization_id, financial_investigation_id)
    REFERENCES financial_investigations (organization_id, id) ON DELETE CASCADE,
  CONSTRAINT fk_fin_exc_result_org FOREIGN KEY (organization_id, reconciliation_result_id)
    REFERENCES financial_reconciliation_results (organization_id, id) ON DELETE CASCADE
);

CREATE INDEX idx_fin_exc_investigations_investigation
  ON financial_exception_investigations (organization_id, financial_investigation_id, created_at DESC);
