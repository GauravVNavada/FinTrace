-- Store optional inventory cost-basis values for lifecycle reconciliation.
-- Existing imports remain valid when an inventory export has no valuation columns.

ALTER TABLE inventory_movements
  ADD COLUMN IF NOT EXISTS unit_cost_minor BIGINT
    CHECK (unit_cost_minor IS NULL OR unit_cost_minor >= 0),
  ADD COLUMN IF NOT EXISTS inventory_value_minor BIGINT
    CHECK (inventory_value_minor IS NULL OR inventory_value_minor >= 0);
