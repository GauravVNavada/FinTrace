-- Sprint 3: deterministic relationship proposals requiring explicit review.
CREATE TABLE relationship_proposals (
  id VARCHAR(128) PRIMARY KEY,
  organization_id UUID NOT NULL,
  financial_investigation_id UUID NOT NULL,
  source_file_id VARCHAR(128) NOT NULL,
  target_source_file_id VARCHAR(128) NOT NULL,
  join_fields JSONB NOT NULL,
  evidence_summary VARCHAR(500) NOT NULL,
  confidence NUMERIC(5,4) NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
  status VARCHAR(16) NOT NULL CHECK (status IN ('PROPOSED', 'ACCEPTED', 'REJECTED', 'EDITED')),
  updated_at TIMESTAMPTZ NOT NULL,
  UNIQUE (organization_id, financial_investigation_id, source_file_id, target_source_file_id),
  CONSTRAINT fk_relationship_investigation_org FOREIGN KEY (organization_id, financial_investigation_id)
    REFERENCES financial_investigations (organization_id, id) ON DELETE CASCADE
);
CREATE INDEX idx_relationship_proposals_investigation
  ON relationship_proposals (organization_id, financial_investigation_id, updated_at DESC);
