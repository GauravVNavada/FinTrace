-- Durable investigation, evaluation, and approval workflow state.
-- Apply after 003_exception_external_ids.sql. Startup must never execute migrations.

CREATE TABLE investigations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID NOT NULL REFERENCES organizations(id),
  source_investigation_id VARCHAR(128) NOT NULL,
  exception_id UUID NOT NULL,
  status VARCHAR(32) NOT NULL CHECK (status IN ('SUPPORTED', 'UNRESOLVED', 'FAILED')),
  response JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL,
  UNIQUE (organization_id, id),
  UNIQUE (organization_id, source_investigation_id),
  CONSTRAINT fk_investigation_exception_org FOREIGN KEY (organization_id, exception_id)
    REFERENCES exceptions (organization_id, id)
);

CREATE TABLE investigation_tool_calls (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID NOT NULL REFERENCES organizations(id),
  investigation_id UUID NOT NULL,
  sequence_no SMALLINT NOT NULL CHECK (sequence_no > 0),
  name VARCHAR(100) NOT NULL,
  payload JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (organization_id, investigation_id, sequence_no),
  CONSTRAINT fk_tool_call_investigation_org FOREIGN KEY (organization_id, investigation_id)
    REFERENCES investigations (organization_id, id)
);

CREATE TABLE evaluation_runs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID NOT NULL REFERENCES organizations(id),
  source_evaluation_id VARCHAR(128) NOT NULL,
  response JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL,
  UNIQUE (organization_id, source_evaluation_id)
);

ALTER TABLE approval_requests ADD COLUMN IF NOT EXISTS source_request_id VARCHAR(128);
CREATE UNIQUE INDEX IF NOT EXISTS idx_approval_requests_org_source_id
  ON approval_requests (organization_id, source_request_id)
  WHERE source_request_id IS NOT NULL;

ALTER TABLE approval_decisions ADD COLUMN IF NOT EXISTS source_approval_id VARCHAR(128);
CREATE UNIQUE INDEX IF NOT EXISTS idx_approval_decisions_org_source_id
  ON approval_decisions (organization_id, source_approval_id)
  WHERE source_approval_id IS NOT NULL;

CREATE INDEX idx_investigations_org_exception_created
  ON investigations (organization_id, exception_id, created_at DESC);
CREATE INDEX idx_evaluation_runs_org_created
  ON evaluation_runs (organization_id, created_at DESC);
