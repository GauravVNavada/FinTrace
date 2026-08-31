-- Persist approval requests for reconciliation results produced by uploaded investigations.
ALTER TABLE approval_requests ALTER COLUMN exception_id DROP NOT NULL;
ALTER TABLE approval_requests ADD COLUMN IF NOT EXISTS financial_reconciliation_result_id VARCHAR(128);

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_approval_request_result_org') THEN
    ALTER TABLE approval_requests ADD CONSTRAINT fk_approval_request_result_org
      FOREIGN KEY (organization_id, financial_reconciliation_result_id)
      REFERENCES financial_reconciliation_results (organization_id, id);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_approval_request_one_subject') THEN
    ALTER TABLE approval_requests ADD CONSTRAINT ck_approval_request_one_subject
      CHECK ((exception_id IS NOT NULL) <> (financial_reconciliation_result_id IS NOT NULL));
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_approval_requests_result
  ON approval_requests (organization_id, financial_reconciliation_result_id)
  WHERE financial_reconciliation_result_id IS NOT NULL;
