-- Prevent repeated attachment of identical bytes within one investigation.
-- Legacy rows may have a NULL hash; the application checks their stored bytes
-- once when a matching upload arrives.

ALTER TABLE source_files
  ADD COLUMN IF NOT EXISTS content_sha256 CHAR(64);

CREATE INDEX IF NOT EXISTS idx_source_files_investigation_content_sha256
  ON source_files (organization_id, financial_investigation_id, content_sha256)
  WHERE content_sha256 IS NOT NULL;
