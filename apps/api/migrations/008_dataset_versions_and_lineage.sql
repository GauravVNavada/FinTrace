-- Sprint 4: immutable normalized dataset snapshots with source lineage.
CREATE TABLE dataset_versions (
  id VARCHAR(128) PRIMARY KEY,
  organization_id UUID NOT NULL,
  financial_investigation_id UUID NOT NULL,
  version_no INTEGER NOT NULL CHECK (version_no > 0),
  status VARCHAR(32) NOT NULL CHECK (status IN ('READY', 'FAILED')),
  record_count INTEGER NOT NULL CHECK (record_count >= 0),
  source_count INTEGER NOT NULL CHECK (source_count >= 0),
  created_at TIMESTAMPTZ NOT NULL,
  UNIQUE (organization_id, financial_investigation_id, version_no),
  CONSTRAINT uq_dataset_versions_org_id UNIQUE (organization_id, id),
  CONSTRAINT fk_dataset_version_investigation_org FOREIGN KEY (organization_id, financial_investigation_id)
    REFERENCES financial_investigations (organization_id, id) ON DELETE CASCADE
);
CREATE TABLE normalized_records (
  id VARCHAR(128) PRIMARY KEY,
  organization_id UUID NOT NULL,
  dataset_version_id VARCHAR(128) NOT NULL,
  source_file_id VARCHAR(128) NOT NULL,
  source_row_number INTEGER NOT NULL CHECK (source_row_number > 1),
  source_record_id VARCHAR(200),
  source_type VARCHAR(64) NOT NULL,
  values JSONB NOT NULL,
  lineage JSONB NOT NULL,
  UNIQUE (organization_id, dataset_version_id, source_file_id, source_row_number),
  CONSTRAINT fk_normalized_dataset_org FOREIGN KEY (organization_id, dataset_version_id)
    REFERENCES dataset_versions (organization_id, id) ON DELETE CASCADE
);
CREATE INDEX idx_dataset_versions_investigation ON dataset_versions (organization_id, financial_investigation_id, version_no DESC);
CREATE INDEX idx_normalized_records_dataset ON normalized_records (organization_id, dataset_version_id);
