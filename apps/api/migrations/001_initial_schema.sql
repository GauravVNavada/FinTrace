CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TYPE reconciliation_status AS ENUM ('RECONCILED', 'RECONCILED_WITH_VARIANCE', 'EXCEPTION', 'AMBIGUOUS', 'PENDING');
CREATE TYPE exception_severity AS ENUM ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL');
CREATE TYPE exception_status AS ENUM ('OPEN', 'IN_REVIEW', 'RESOLVED', 'ESCALATED');

CREATE TABLE organizations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  external_id VARCHAR(64) NOT NULL UNIQUE,
  name VARCHAR(200) NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE orders (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID NOT NULL REFERENCES organizations(id),
  source_order_id VARCHAR(64) NOT NULL,
  store_code VARCHAR(64) NOT NULL,
  amount_minor BIGINT NOT NULL CHECK (amount_minor >= 0),
  currency CHAR(3) NOT NULL DEFAULT 'INR',
  status VARCHAR(32) NOT NULL,
  created_at TIMESTAMPTZ NOT NULL,
  UNIQUE (organization_id, source_order_id)
);

CREATE TABLE payments (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID NOT NULL REFERENCES organizations(id),
  source_payment_id VARCHAR(64) NOT NULL,
  order_id UUID NOT NULL REFERENCES orders(id),
  amount_minor BIGINT NOT NULL CHECK (amount_minor >= 0),
  gateway_fee_minor BIGINT NOT NULL DEFAULT 0 CHECK (gateway_fee_minor >= 0),
  status VARCHAR(32) NOT NULL,
  captured_at TIMESTAMPTZ,
  UNIQUE (organization_id, source_payment_id)
);

CREATE TABLE settlements (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID NOT NULL REFERENCES organizations(id),
  source_settlement_id VARCHAR(64) NOT NULL,
  payment_id UUID NOT NULL REFERENCES payments(id),
  gross_minor BIGINT NOT NULL CHECK (gross_minor >= 0),
  fees_minor BIGINT NOT NULL DEFAULT 0 CHECK (fees_minor >= 0),
  tax_minor BIGINT NOT NULL DEFAULT 0 CHECK (tax_minor >= 0),
  net_minor BIGINT NOT NULL CHECK (net_minor >= 0),
  settled_at TIMESTAMPTZ,
  status VARCHAR(32) NOT NULL,
  UNIQUE (organization_id, source_settlement_id)
);

CREATE TABLE invoices (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID NOT NULL REFERENCES organizations(id),
  source_invoice_id VARCHAR(64) NOT NULL,
  order_id UUID NOT NULL REFERENCES orders(id),
  gross_minor BIGINT NOT NULL CHECK (gross_minor >= 0),
  currency CHAR(3) NOT NULL DEFAULT 'INR',
  status VARCHAR(32) NOT NULL,
  created_at TIMESTAMPTZ NOT NULL,
  UNIQUE (organization_id, source_invoice_id)
);

CREATE TABLE refunds (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID NOT NULL REFERENCES organizations(id),
  source_refund_id VARCHAR(64) NOT NULL,
  payment_id UUID NOT NULL REFERENCES payments(id),
  amount_minor BIGINT NOT NULL CHECK (amount_minor > 0),
  status VARCHAR(32) NOT NULL,
  processed_at TIMESTAMPTZ,
  UNIQUE (organization_id, source_refund_id)
);

CREATE TABLE inventory_movements (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID NOT NULL REFERENCES organizations(id),
  source_movement_id VARCHAR(64) NOT NULL,
  order_id UUID NOT NULL REFERENCES orders(id),
  sku VARCHAR(128) NOT NULL,
  quantity INTEGER NOT NULL CHECK (quantity > 0),
  movement_type VARCHAR(32) NOT NULL,
  occurred_at TIMESTAMPTZ NOT NULL,
  UNIQUE (organization_id, source_movement_id)
);

CREATE TABLE employee_actions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID NOT NULL REFERENCES organizations(id),
  source_action_id VARCHAR(64) NOT NULL,
  entity_type VARCHAR(32) NOT NULL,
  entity_id VARCHAR(64) NOT NULL,
  employee_id VARCHAR(64) NOT NULL,
  action VARCHAR(64) NOT NULL,
  occurred_at TIMESTAMPTZ NOT NULL,
  UNIQUE (organization_id, source_action_id)
);

CREATE TABLE reconciliation_runs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID NOT NULL REFERENCES organizations(id),
  run_key VARCHAR(128) NOT NULL,
  seed INTEGER,
  lifecycle_count INTEGER NOT NULL DEFAULT 0 CHECK (lifecycle_count >= 0),
  status VARCHAR(32) NOT NULL,
  started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  completed_at TIMESTAMPTZ,
  UNIQUE (organization_id, run_key)
);

CREATE TABLE exceptions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID NOT NULL REFERENCES organizations(id),
  reconciliation_run_id UUID NOT NULL REFERENCES reconciliation_runs(id),
  order_id UUID NOT NULL REFERENCES orders(id),
  exception_type VARCHAR(64) NOT NULL,
  severity exception_severity NOT NULL,
  status exception_status NOT NULL DEFAULT 'OPEN',
  financial_exposure_minor BIGINT NOT NULL DEFAULT 0 CHECK (financial_exposure_minor >= 0),
  currency CHAR(3) NOT NULL DEFAULT 'INR',
  detected_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  rules_triggered JSONB NOT NULL DEFAULT '[]'::jsonb,
  UNIQUE (organization_id, reconciliation_run_id, order_id, exception_type),
  UNIQUE (organization_id, id)
);

CREATE TABLE audit_events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID NOT NULL REFERENCES organizations(id),
  actor_type VARCHAR(32) NOT NULL,
  actor_id VARCHAR(128) NOT NULL,
  action VARCHAR(64) NOT NULL,
  resource_type VARCHAR(64),
  resource_id VARCHAR(128),
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  correlation_id VARCHAR(128) NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_orders_org_created ON orders (organization_id, created_at DESC);
CREATE INDEX idx_payments_org_order ON payments (organization_id, order_id);
CREATE INDEX idx_settlements_org_payment ON settlements (organization_id, payment_id);
CREATE INDEX idx_invoices_org_order ON invoices (organization_id, order_id);
CREATE INDEX idx_refunds_org_payment ON refunds (organization_id, payment_id);
CREATE INDEX idx_inventory_org_order ON inventory_movements (organization_id, order_id);
CREATE INDEX idx_exceptions_org_status_detected ON exceptions (organization_id, status, detected_at DESC);
CREATE INDEX idx_audit_org_resource_created ON audit_events (organization_id, resource_type, resource_id, created_at DESC);
