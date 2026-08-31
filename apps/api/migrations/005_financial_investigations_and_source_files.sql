-- Sprint 1: top-level financial investigations and safe source metadata.
-- File bytes are stored outside PostgreSQL; storage_reference is a generated server key.

CREATE TABLE financial_investigations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID NOT NULL REFERENCES organizations(id),
  source_investigation_id VARCHAR(128) NOT NULL,
  name VARCHAR(200) NOT NULL,
  description VARCHAR(2000),
  period_start DATE NOT NULL,
  period_end DATE NOT NULL,
  base_currency CHAR(3) NOT NULL,
  status VARCHAR(32) NOT NULL CHECK (status IN ('DRAFT', 'SOURCES_UPLOADED', 'MAPPING_REQUIRED', 'RELATIONSHIP_REVIEW', 'READY_TO_BUILD', 'PROCESSING', 'RECONCILED', 'FAILED')),
  created_by VARCHAR(128) NOT NULL,
  created_at TIMESTAMPTZ NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL,
  UNIQUE (organization_id, id),
  UNIQUE (organization_id, source_investigation_id),
  CHECK (period_end >= period_start)
);

CREATE TABLE source_files (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID NOT NULL REFERENCES organizations(id),
  financial_investigation_id UUID NOT NULL,
  source_file_id VARCHAR(128) NOT NULL,
  original_filename VARCHAR(512) NOT NULL,
  storage_reference VARCHAR(512) NOT NULL,
  mime_type VARCHAR(128) NOT NULL,
  size_bytes BIGINT NOT NULL CHECK (size_bytes > 0),
  row_count INTEGER CHECK (row_count IS NULL OR row_count >= 0),
  column_count INTEGER CHECK (column_count IS NULL OR column_count >= 0),
  status VARCHAR(32) NOT NULL CHECK (status IN ('UPLOADED', 'ANALYZING', 'MAPPING_REQUIRED', 'READY', 'FAILED')),
  detected_source_type VARCHAR(64),
  classification_confidence NUMERIC(5,4) CHECK (classification_confidence IS NULL OR (classification_confidence >= 0 AND classification_confidence <= 1)),
  created_at TIMESTAMPTZ NOT NULL,
  UNIQUE (organization_id, source_file_id),
  CONSTRAINT fk_source_file_investigation_org FOREIGN KEY (organization_id, financial_investigation_id)
    REFERENCES financial_investigations (organization_id, id)
);

CREATE INDEX idx_financial_investigations_org_created
  ON financial_investigations (organization_id, created_at DESC);
CREATE INDEX idx_source_files_investigation_created
  ON source_files (organization_id, financial_investigation_id, created_at DESC);
