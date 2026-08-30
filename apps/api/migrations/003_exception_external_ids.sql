-- Add stable public exception identifiers used by API contracts and source adapters.
ALTER TABLE exceptions ADD COLUMN IF NOT EXISTS source_exception_id VARCHAR(128);
CREATE UNIQUE INDEX IF NOT EXISTS idx_exceptions_org_source_id
  ON exceptions (organization_id, source_exception_id)
  WHERE source_exception_id IS NOT NULL;
