-- Tenant integrity and replay-safe workflow hardening.
-- Apply after 013_provider_health_diagnostics.sql. Startup must never execute migrations.

ALTER TABLE orders
  ADD CONSTRAINT uq_orders_org_id UNIQUE (organization_id, id);

ALTER TABLE payments
  ADD CONSTRAINT uq_payments_org_id UNIQUE (organization_id, id);

ALTER TABLE payments
  DROP CONSTRAINT IF EXISTS payments_order_id_fkey,
  ADD CONSTRAINT fk_payments_order_org FOREIGN KEY (organization_id, order_id)
    REFERENCES orders (organization_id, id);

ALTER TABLE settlements
  DROP CONSTRAINT IF EXISTS settlements_payment_id_fkey,
  ADD CONSTRAINT fk_settlements_payment_org FOREIGN KEY (organization_id, payment_id)
    REFERENCES payments (organization_id, id);

ALTER TABLE invoices
  DROP CONSTRAINT IF EXISTS invoices_order_id_fkey,
  ADD CONSTRAINT fk_invoices_order_org FOREIGN KEY (organization_id, order_id)
    REFERENCES orders (organization_id, id);

ALTER TABLE refunds
  DROP CONSTRAINT IF EXISTS refunds_payment_id_fkey,
  ADD CONSTRAINT fk_refunds_payment_org FOREIGN KEY (organization_id, payment_id)
    REFERENCES payments (organization_id, id);

ALTER TABLE inventory_movements
  DROP CONSTRAINT IF EXISTS inventory_movements_order_id_fkey,
  ADD CONSTRAINT fk_inventory_order_org FOREIGN KEY (organization_id, order_id)
    REFERENCES orders (organization_id, id);

CREATE INDEX IF NOT EXISTS idx_audit_events_org_created
  ON audit_events (organization_id, created_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_fin_recon_results_org_id
  ON financial_reconciliation_results (organization_id, id);
