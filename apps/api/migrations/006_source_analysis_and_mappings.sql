-- Sprint 2: bounded source analysis and explicit schema mapping proposals.

CREATE TABLE source_analyses (
  id VARCHAR(128) PRIMARY KEY,
  organization_id UUID NOT NULL,
  financial_investigation_id UUID NOT NULL,
  source_file_id VARCHAR(128) NOT NULL,
  headers JSONB NOT NULL,
  sample_rows JSONB NOT NULL,
  column_profiles JSONB NOT NULL,
  source_type VARCHAR(64) NOT NULL CHECK (source_type IN ('SALES', 'ORDERS', 'PAYMENTS', 'SETTLEMENTS', 'REFUNDS', 'INVOICES', 'INVENTORY_MOVEMENTS', 'EMPLOYEE_ACTIONS', 'UNKNOWN')),
  classification_confidence NUMERIC(5,4) NOT NULL CHECK (classification_confidence >= 0 AND classification_confidence <= 1),
  reasoning_summary VARCHAR(500) NOT NULL,
  provider_status VARCHAR(64) NOT NULL,
  analyzed_at TIMESTAMPTZ NOT NULL,
  UNIQUE (organization_id, source_file_id),
  CONSTRAINT fk_source_analysis_file_org FOREIGN KEY (organization_id, source_file_id)
    REFERENCES source_files (organization_id, source_file_id) ON DELETE CASCADE,
  CONSTRAINT fk_source_analysis_investigation_org FOREIGN KEY (organization_id, financial_investigation_id)
    REFERENCES financial_investigations (organization_id, id) ON DELETE CASCADE
);

CREATE TABLE source_mappings (
  id VARCHAR(128) PRIMARY KEY,
  organization_id UUID NOT NULL,
  financial_investigation_id UUID NOT NULL,
  source_file_id VARCHAR(128) NOT NULL,
  source_column VARCHAR(200) NOT NULL,
  canonical_field VARCHAR(100),
  confidence NUMERIC(5,4) NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
  required BOOLEAN NOT NULL,
  inferred_type VARCHAR(32) NOT NULL,
  ignored BOOLEAN NOT NULL DEFAULT false,
  status VARCHAR(32) NOT NULL CHECK (status IN ('PROPOSED', 'EDITED', 'CONFIRMED')),
  updated_at TIMESTAMPTZ NOT NULL,
  UNIQUE (organization_id, source_file_id, source_column),
  UNIQUE (organization_id, id),
  CONSTRAINT fk_source_mapping_file_org FOREIGN KEY (organization_id, source_file_id)
    REFERENCES source_files (organization_id, source_file_id) ON DELETE CASCADE,
  CONSTRAINT fk_source_mapping_investigation_org FOREIGN KEY (organization_id, financial_investigation_id)
    REFERENCES financial_investigations (organization_id, id) ON DELETE CASCADE
);

CREATE INDEX idx_source_analyses_investigation
  ON source_analyses (organization_id, financial_investigation_id, analyzed_at DESC);
CREATE INDEX idx_source_mappings_file
  ON source_mappings (organization_id, source_file_id, updated_at DESC);
