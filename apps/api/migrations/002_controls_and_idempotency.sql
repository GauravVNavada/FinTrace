-- Sprint 4: approval controls, idempotency records, and durable audit relationships.
-- Apply after 001_initial_schema.sql. Startup must never execute migrations.

CREATE TABLE organization_members (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID NOT NULL REFERENCES organizations(id),
  actor_id VARCHAR(128) NOT NULL,
  role VARCHAR(32) NOT NULL CHECK (role IN ('ANALYST', 'FINANCE_MANAGER', 'CONTROLLER', 'AUDITOR')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (organization_id, actor_id)
);

CREATE TABLE idempotency_keys (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID NOT NULL REFERENCES organizations(id),
  actor_id VARCHAR(128) NOT NULL,
  idempotency_key VARCHAR(128) NOT NULL,
  request_hash CHAR(64) NOT NULL,
  response_status INTEGER NOT NULL CHECK (response_status BETWEEN 200 AND 599),
  response_body JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  expires_at TIMESTAMPTZ,
  UNIQUE (organization_id, idempotency_key)
);

CREATE TABLE approval_requests (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID NOT NULL REFERENCES organizations(id),
  exception_id UUID NOT NULL,
  action_code VARCHAR(64) NOT NULL,
  status VARCHAR(32) NOT NULL CHECK (status IN ('PENDING_APPROVAL', 'APPROVED', 'REJECTED')),
  financial_exposure_minor BIGINT NOT NULL CHECK (financial_exposure_minor >= 0),
  currency CHAR(3) NOT NULL DEFAULT 'INR',
  required_capability VARCHAR(64) NOT NULL,
  required_approvals SMALLINT NOT NULL CHECK (required_approvals BETWEEN 1 AND 2),
  approvals_received SMALLINT NOT NULL DEFAULT 0 CHECK (approvals_received BETWEEN 0 AND 2),
  requester_actor_id VARCHAR(128) NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (organization_id, id),
  CONSTRAINT fk_approval_request_exception_org FOREIGN KEY (organization_id, exception_id)
    REFERENCES exceptions (organization_id, id)
);

CREATE TABLE approval_decisions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID NOT NULL REFERENCES organizations(id),
  approval_request_id UUID NOT NULL,
  actor_id VARCHAR(128) NOT NULL,
  decision VARCHAR(16) NOT NULL CHECK (decision IN ('APPROVED', 'REJECTED')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (organization_id, approval_request_id, actor_id),
  CONSTRAINT fk_approval_decision_request_org FOREIGN KEY (organization_id, approval_request_id)
    REFERENCES approval_requests (organization_id, id)
);

CREATE INDEX idx_idempotency_org_created ON idempotency_keys (organization_id, created_at DESC);
CREATE INDEX idx_approval_requests_org_status ON approval_requests (organization_id, status, created_at DESC);
CREATE INDEX idx_approval_decisions_org_request ON approval_decisions (organization_id, approval_request_id, created_at ASC);
