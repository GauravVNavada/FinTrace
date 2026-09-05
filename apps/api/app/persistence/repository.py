from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from psycopg.types.json import Json

from app.core.config import get_settings
from app.core.request_context import current_request_id
from app.domain.lifecycle import CanonicalLifecycle, LifecycleNotFoundError
from app.domain.schemas import (
    DashboardSummary,
    ExceptionStatus,
    ExceptionSummary,
    ExceptionType,
    Severity,
)
from app.persistence.connection import connection


class PostgresRepository:
    """Organization-scoped PostgreSQL repository for canonical read paths."""

    def __init__(self, database_url: str) -> None:
        self._database_url = database_url
        self.supports_workflow_persistence = True

    def _organization_uuid(self, conn: Any, organization_id: str) -> UUID | None:
        row = conn.execute(
            "SELECT id FROM organizations WHERE external_id = %s",
            (organization_id,),
        ).fetchone()
        return row["id"] if row else None

    def dashboard_summary(self, organization_id: str) -> DashboardSummary:
        with connection(self._database_url) as conn:
            org_uuid = self._organization_uuid(conn, organization_id)
            if org_uuid is None:
                return DashboardSummary(
                    organization_id=organization_id,
                    reconciliation_run_id="",
                    lifecycle_count=0,
                    auto_reconciled_count=0,
                    exception_count=0,
                    open_exposure=Decimal(0),
                    requires_review_count=0,
                    generated_at=datetime.now(UTC),
                )
            run = conn.execute(
                """
                SELECT run_key, lifecycle_count
                FROM reconciliation_runs
                WHERE organization_id = %s
                ORDER BY completed_at DESC NULLS LAST, started_at DESC
                LIMIT 1
                """,
                (org_uuid,),
            ).fetchone()
            exception_row = conn.execute(
                """
                SELECT count(*) AS exception_count,
                       coalesce(sum(financial_exposure_minor), 0) AS exposure,
                       count(*) FILTER (WHERE status IN ('OPEN', 'IN_REVIEW', 'ESCALATED')) AS review_count
                FROM exceptions
                WHERE organization_id = %s AND status <> 'RESOLVED'
                """,
                (org_uuid,),
            ).fetchone()
            return DashboardSummary(
                organization_id=organization_id,
                reconciliation_run_id=str(run["run_key"]) if run else "",
                lifecycle_count=int(run["lifecycle_count"]) if run else 0,
                auto_reconciled_count=max(
                    (int(run["lifecycle_count"]) if run else 0)
                    - int(exception_row["exception_count"]),
                    0,
                ),
                exception_count=int(exception_row["exception_count"]),
                open_exposure=Decimal(int(exception_row["exposure"])) / Decimal(100),
                requires_review_count=int(exception_row["review_count"]),
                generated_at=datetime.now(UTC),
            )

    def list_exceptions(self, organization_id: str, limit: int = 100) -> list[ExceptionSummary]:
        with connection(self._database_url) as conn:
            org_uuid = self._organization_uuid(conn, organization_id)
            if org_uuid is None:
                return []
            rows = conn.execute(
                """
                SELECT source_exception_id, e.organization_id, o.source_order_id, exception_type,
                       e.severity, e.status, e.financial_exposure_minor, e.currency, e.detected_at,
                       e.rules_triggered
                FROM exceptions e
                JOIN orders o ON o.id = e.order_id AND o.organization_id = e.organization_id
                WHERE e.organization_id = %s
                ORDER BY CASE e.severity WHEN 'CRITICAL' THEN 0 WHEN 'HIGH' THEN 1 WHEN 'MEDIUM' THEN 2 ELSE 3 END, e.detected_at DESC
                LIMIT %s
                """,
                (org_uuid, min(max(limit, 1), 1000)),
            ).fetchall()
            return [self._exception(row, organization_id) for row in rows]

    def get_exception(self, organization_id: str, exception_id: str) -> ExceptionSummary | None:
        with connection(self._database_url) as conn:
            org_uuid = self._organization_uuid(conn, organization_id)
            if org_uuid is None:
                return None
            row = conn.execute(
                """
                SELECT source_exception_id, e.organization_id, o.source_order_id, exception_type,
                       e.severity, e.status, e.financial_exposure_minor, e.currency, e.detected_at,
                       e.rules_triggered
                FROM exceptions e
                JOIN orders o ON o.id = e.order_id AND o.organization_id = e.organization_id
                WHERE e.organization_id = %s AND e.source_exception_id = %s
                """,
                (org_uuid, exception_id),
            ).fetchone()
            return self._exception(row, organization_id) if row else None

    def related_exceptions(self, organization_id: str, order_id: str) -> list[ExceptionSummary]:
        return [item for item in self.list_exceptions(organization_id) if item.order_id == order_id]

    def create_financial_investigation(
        self, organization_id: str, data: dict[str, Any]
    ) -> dict[str, Any]:
        with connection(self._database_url) as conn:
            org_uuid = self._organization_uuid(conn, organization_id)
            if org_uuid is None:
                raise ValueError("Organization does not exist")
            conn.execute(
                """
                INSERT INTO financial_investigations
                  (organization_id, source_investigation_id, name, description,
                   period_start, period_end, base_currency, status, created_by,
                   created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    org_uuid,
                    data["id"],
                    data["name"],
                    data["description"],
                    data["period_start"],
                    data["period_end"],
                    data["base_currency"],
                    data["status"],
                    data["created_by"],
                    data["created_at"],
                    data["updated_at"],
                ),
            )
        return self.get_financial_investigation(organization_id, str(data["id"])) or {}

    def list_financial_investigations(
        self, organization_id: str, limit: int = 100
    ) -> list[dict[str, Any]]:
        with connection(self._database_url) as conn:
            org_uuid = self._organization_uuid(conn, organization_id)
            if org_uuid is None:
                return []
            rows = conn.execute(
                """
                SELECT fi.source_investigation_id AS id, fi.organization_id::text AS organization_id,
                       fi.name, fi.description, fi.period_start, fi.period_end,
                       fi.base_currency, fi.status, fi.created_by,
                       fi.created_at, fi.updated_at, count(sf.id) AS source_file_count
                FROM financial_investigations fi
                LEFT JOIN source_files sf
                  ON sf.financial_investigation_id = fi.id
                 AND sf.organization_id = fi.organization_id
                WHERE fi.organization_id = %s
                GROUP BY fi.id
                ORDER BY fi.created_at DESC
                LIMIT %s
                """,
                (org_uuid, min(max(limit, 1), 1000)),
            ).fetchall()
            return [self._public_organization(row, organization_id) for row in rows]

    def get_financial_investigation(
        self, organization_id: str, investigation_id: str
    ) -> dict[str, Any] | None:
        with connection(self._database_url) as conn:
            org_uuid = self._organization_uuid(conn, organization_id)
            if org_uuid is None:
                return None
            row = conn.execute(
                """
                SELECT fi.source_investigation_id AS id, fi.organization_id::text AS organization_id,
                       fi.name, fi.description, fi.period_start, fi.period_end,
                       fi.base_currency, fi.status, fi.created_by,
                       fi.created_at, fi.updated_at, count(sf.id) AS source_file_count
                FROM financial_investigations fi
                LEFT JOIN source_files sf
                  ON sf.financial_investigation_id = fi.id
                 AND sf.organization_id = fi.organization_id
                WHERE fi.organization_id = %s AND fi.source_investigation_id = %s
                GROUP BY fi.id
                """,
                (org_uuid, investigation_id),
            ).fetchone()
            return self._public_organization(row, organization_id) if row else None

    def update_financial_investigation_status(
        self, organization_id: str, investigation_id: str, status: str
    ) -> None:
        with connection(self._database_url) as conn:
            org_uuid = self._organization_uuid(conn, organization_id)
            conn.execute(
                "UPDATE financial_investigations SET status = %s, updated_at = now() WHERE organization_id = %s AND source_investigation_id = %s",
                (status, org_uuid, investigation_id),
            )

    def add_source_file(
        self, organization_id: str, investigation_id: str, data: dict[str, Any]
    ) -> dict[str, Any]:
        with connection(self._database_url) as conn:
            org_uuid = self._organization_uuid(conn, organization_id)
            if org_uuid is None:
                return {}
            investigation = conn.execute(
                "SELECT id FROM financial_investigations WHERE organization_id = %s AND source_investigation_id = %s FOR UPDATE",
                (org_uuid, investigation_id),
            ).fetchone()
            if investigation is None:
                return {}
            existing = conn.execute(
                """
                SELECT sf.source_file_id AS id, sf.organization_id::text AS organization_id,
                       fi.source_investigation_id AS financial_investigation_id,
                       sf.original_filename, sf.mime_type, sf.size_bytes,
                       sf.row_count, sf.column_count, sf.status,
                       sf.detected_source_type, sf.classification_confidence,
                       sf.created_at
                FROM source_files sf
                JOIN financial_investigations fi
                  ON fi.id = sf.financial_investigation_id
                 AND fi.organization_id = sf.organization_id
                WHERE sf.organization_id = %s
                  AND sf.financial_investigation_id = %s
                  AND sf.content_sha256 = %s
                ORDER BY sf.created_at ASC
                LIMIT 1
                """,
                (org_uuid, investigation["id"], data["sha256"]),
            ).fetchone()
            if existing is not None:
                return self._public_organization(existing, organization_id)
            conn.execute(
                """
                INSERT INTO source_files
                  (organization_id, financial_investigation_id, source_file_id,
                   original_filename, storage_reference, mime_type, size_bytes,
                   row_count, column_count, status, content_sha256, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    org_uuid,
                    investigation["id"],
                    data["id"],
                    data["original_filename"],
                    data["storage_reference"],
                    data["mime_type"],
                    data["size_bytes"],
                    data["row_count"],
                    data["column_count"],
                    data["status"],
                    data["sha256"],
                    data["created_at"],
                ),
            )
            conn.execute(
                "UPDATE financial_investigations SET status = 'SOURCES_UPLOADED', updated_at = %s WHERE id = %s AND status = 'DRAFT'",
                (data["created_at"], investigation["id"]),
            )
        return next(
            (
                item
                for item in self.list_source_files(organization_id, investigation_id)
                if item["id"] == data["id"]
            ),
            {},
        )

    def list_source_files(
        self, organization_id: str, investigation_id: str, limit: int = 100
    ) -> list[dict[str, Any]]:
        with connection(self._database_url) as conn:
            org_uuid = self._organization_uuid(conn, organization_id)
            if org_uuid is None:
                return []
            rows = conn.execute(
                """
                SELECT sf.source_file_id AS id, sf.organization_id::text AS organization_id,
                       fi.source_investigation_id AS financial_investigation_id,
                       sf.original_filename, sf.mime_type, sf.size_bytes,
                       sf.row_count, sf.column_count, sf.status,
                       sf.detected_source_type, sf.classification_confidence,
                       sf.created_at
                FROM source_files sf
                JOIN financial_investigations fi
                  ON fi.id = sf.financial_investigation_id
                 AND fi.organization_id = sf.organization_id
                WHERE sf.organization_id = %s AND fi.source_investigation_id = %s
                ORDER BY sf.created_at DESC
                LIMIT %s
                """,
                (org_uuid, investigation_id, min(max(limit, 1), 1000)),
            ).fetchall()
            return [self._public_organization(row, organization_id) for row in rows]

    def delete_source_file(
        self, organization_id: str, investigation_id: str, source_file_id: str
    ) -> dict[str, Any] | None:
        with connection(self._database_url) as conn:
            org_uuid = self._organization_uuid(conn, organization_id)
            if org_uuid is None:
                return None
            row = conn.execute(
                """
                DELETE FROM source_files sf
                USING financial_investigations fi
                WHERE sf.financial_investigation_id = fi.id
                  AND sf.organization_id = fi.organization_id
                  AND sf.organization_id = %s
                  AND fi.source_investigation_id = %s
                  AND sf.source_file_id = %s
                RETURNING sf.storage_reference
                """,
                (org_uuid, investigation_id, source_file_id),
            ).fetchone()
            if row is None:
                return None
            remaining = conn.execute(
                """
                SELECT count(*) AS count FROM source_files sf
                JOIN financial_investigations fi ON fi.id = sf.financial_investigation_id
                WHERE sf.organization_id = %s AND fi.source_investigation_id = %s
                """,
                (org_uuid, investigation_id),
            ).fetchone()
            if int(remaining["count"]) == 0:
                conn.execute(
                    """
                    UPDATE financial_investigations SET status = 'DRAFT', updated_at = now()
                    WHERE organization_id = %s AND source_investigation_id = %s
                    """,
                    (org_uuid, investigation_id),
                )
            return {"storage_reference": row["storage_reference"]}

    def get_source_file_internal(
        self, organization_id: str, investigation_id: str, source_file_id: str
    ) -> dict[str, Any] | None:
        with connection(self._database_url) as conn:
            org_uuid = self._organization_uuid(conn, organization_id)
            if org_uuid is None:
                return None
            row = conn.execute(
                """
                SELECT sf.source_file_id AS id, sf.organization_id::text AS organization_id,
                       fi.source_investigation_id AS financial_investigation_id,
                       sf.original_filename, sf.storage_reference, sf.mime_type,
                       sf.size_bytes, sf.row_count, sf.column_count, sf.status,
                       sf.detected_source_type, sf.classification_confidence,
                       sf.content_sha256, sf.created_at
                FROM source_files sf
                JOIN financial_investigations fi
                  ON fi.id = sf.financial_investigation_id
                 AND fi.organization_id = sf.organization_id
                WHERE sf.organization_id = %s
                  AND fi.source_investigation_id = %s
                  AND sf.source_file_id = %s
                """,
                (org_uuid, investigation_id, source_file_id),
            ).fetchone()
            return self._public_organization(row, organization_id) if row else None

    def update_source_analysis_state(
        self,
        organization_id: str,
        investigation_id: str,
        source_file_id: str,
        status: str,
        detected_source_type: str,
        classification_confidence: float,
    ) -> None:
        with connection(self._database_url) as conn:
            org_uuid = self._organization_uuid(conn, organization_id)
            if org_uuid is None:
                return
            conn.execute(
                """
                UPDATE source_files sf
                   SET status = %s, detected_source_type = %s,
                       classification_confidence = %s
                FROM financial_investigations fi
                WHERE sf.financial_investigation_id = fi.id
                  AND sf.organization_id = fi.organization_id
                  AND sf.organization_id = %s
                  AND fi.source_investigation_id = %s
                  AND sf.source_file_id = %s
                """,
                (
                    status,
                    detected_source_type,
                    classification_confidence,
                    org_uuid,
                    investigation_id,
                    source_file_id,
                ),
            )
            conn.execute(
                """
                UPDATE financial_investigations
                   SET status = 'MAPPING_REQUIRED', updated_at = now()
                WHERE organization_id = %s
                  AND source_investigation_id = %s
                  AND status IN ('SOURCES_UPLOADED', 'MAPPING_REQUIRED')
                """,
                (org_uuid, investigation_id),
            )

    def save_source_analysis(
        self,
        organization_id: str,
        investigation_id: str,
        source_file_id: str,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        with connection(self._database_url) as conn:
            org_uuid = self._organization_uuid(conn, organization_id)
            if org_uuid is None:
                return {}
            investigation = conn.execute(
                "SELECT id FROM financial_investigations WHERE organization_id = %s AND source_investigation_id = %s",
                (org_uuid, investigation_id),
            ).fetchone()
            source = conn.execute(
                "SELECT id FROM source_files WHERE organization_id = %s AND source_file_id = %s",
                (org_uuid, source_file_id),
            ).fetchone()
            if investigation is None or source is None:
                return {}
            conn.execute(
                """
                INSERT INTO source_analyses
                  (id, organization_id, financial_investigation_id, source_file_id,
                   headers, sample_rows, column_profiles, source_type,
                   classification_confidence, reasoning_summary, provider_status,
                   provider, model, analyzed_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (organization_id, source_file_id) DO UPDATE SET
                  id = EXCLUDED.id, headers = EXCLUDED.headers,
                  sample_rows = EXCLUDED.sample_rows, column_profiles = EXCLUDED.column_profiles,
                  source_type = EXCLUDED.source_type,
                  classification_confidence = EXCLUDED.classification_confidence,
                  reasoning_summary = EXCLUDED.reasoning_summary,
                  provider_status = EXCLUDED.provider_status,
                  provider = EXCLUDED.provider, model = EXCLUDED.model,
                  analyzed_at = EXCLUDED.analyzed_at
                """,
                (
                    data["id"],
                    org_uuid,
                    investigation["id"],
                    source_file_id,
                    Json(data["headers"]),
                    Json(data["sample_rows"]),
                    Json(data["columns"]),
                    data["source_type"],
                    data["classification_confidence"],
                    data["reasoning_summary"],
                    data["provider_status"],
                    data.get("provider", "offline-deterministic"),
                    data.get("model", "none"),
                    data["analyzed_at"],
                ),
            )
        return self.get_source_analysis(organization_id, investigation_id, source_file_id) or {}

    def get_source_analysis(
        self, organization_id: str, investigation_id: str, source_file_id: str
    ) -> dict[str, Any] | None:
        with connection(self._database_url) as conn:
            org_uuid = self._organization_uuid(conn, organization_id)
            if org_uuid is None:
                return None
            row = conn.execute(
                """
                SELECT sa.id, sa.organization_id::text AS organization_id,
                       fi.source_investigation_id AS financial_investigation_id,
                       sa.source_file_id, sa.headers, sa.sample_rows,
                       sa.column_profiles AS columns, sa.source_type,
                       sa.classification_confidence, sa.reasoning_summary,
                       sa.provider_status, sa.provider, sa.model, sa.analyzed_at
                FROM source_analyses sa
                JOIN financial_investigations fi
                  ON fi.id = sa.financial_investigation_id
                 AND fi.organization_id = sa.organization_id
                WHERE sa.organization_id = %s
                  AND fi.source_investigation_id = %s
                  AND sa.source_file_id = %s
                """,
                (org_uuid, investigation_id, source_file_id),
            ).fetchone()
            return self._public_organization(row, organization_id) if row else None

    def list_source_mappings(
        self, organization_id: str, investigation_id: str, source_file_id: str
    ) -> list[dict[str, Any]]:
        with connection(self._database_url) as conn:
            org_uuid = self._organization_uuid(conn, organization_id)
            if org_uuid is None:
                return []
            rows = conn.execute(
                """
                SELECT sm.id, sm.organization_id::text AS organization_id,
                       fi.source_investigation_id AS financial_investigation_id,
                       sm.source_file_id, sm.source_column, sm.canonical_field,
                       sm.confidence, sm.required, sm.inferred_type, sm.ignored,
                       sm.status, sm.updated_at
                FROM source_mappings sm
                JOIN financial_investigations fi
                  ON fi.id = sm.financial_investigation_id
                 AND fi.organization_id = sm.organization_id
                WHERE sm.organization_id = %s
                  AND fi.source_investigation_id = %s
                  AND sm.source_file_id = %s
                ORDER BY sm.source_column
                """,
                (org_uuid, investigation_id, source_file_id),
            ).fetchall()
            return [self._public_organization(row, organization_id) for row in rows]

    def save_source_mappings(
        self,
        organization_id: str,
        investigation_id: str,
        source_file_id: str,
        mappings: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        with connection(self._database_url) as conn:
            org_uuid = self._organization_uuid(conn, organization_id)
            if org_uuid is None:
                return []
            investigation = conn.execute(
                "SELECT id FROM financial_investigations WHERE organization_id = %s AND source_investigation_id = %s",
                (org_uuid, investigation_id),
            ).fetchone()
            if investigation is None:
                return []
            conn.execute(
                "DELETE FROM source_mappings WHERE organization_id = %s AND source_file_id = %s",
                (org_uuid, source_file_id),
            )
            for mapping in mappings:
                conn.execute(
                    """
                    INSERT INTO source_mappings
                      (id, organization_id, financial_investigation_id, source_file_id,
                       source_column, canonical_field, confidence, required,
                       inferred_type, ignored, status, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        mapping["id"],
                        org_uuid,
                        investigation["id"],
                        source_file_id,
                        mapping["source_column"],
                        mapping["canonical_field"],
                        mapping["confidence"],
                        mapping["required"],
                        mapping["inferred_type"],
                        mapping["ignored"],
                        mapping["status"],
                        mapping["updated_at"],
                    ),
                )
        return self.list_source_mappings(organization_id, investigation_id, source_file_id)

    def update_source_mapping(
        self,
        organization_id: str,
        investigation_id: str,
        source_file_id: str,
        mapping_id: str,
        data: dict[str, Any],
    ) -> dict[str, Any] | None:
        with connection(self._database_url) as conn:
            org_uuid = self._organization_uuid(conn, organization_id)
            if org_uuid is None:
                return None
            set_parts = ["status = 'EDITED'", "updated_at = %s"]
            params: list[Any] = [data["updated_at"]]
            if "canonical_field" in data:
                set_parts.append("canonical_field = %s")
                params.append(data["canonical_field"])
            if "ignored" in data:
                set_parts.append("ignored = %s")
                params.append(data["ignored"])
            params.extend([org_uuid, investigation_id, source_file_id, mapping_id])
            conn.execute(
                f"""
                UPDATE source_mappings sm SET {", ".join(set_parts)}
                FROM financial_investigations fi
                WHERE sm.financial_investigation_id = fi.id
                  AND sm.organization_id = fi.organization_id
                  AND sm.organization_id = %s
                  AND fi.source_investigation_id = %s
                  AND sm.source_file_id = %s
                  AND sm.id = %s
                """,
                tuple(params),
            )
        return next(
            (
                item
                for item in self.list_source_mappings(
                    organization_id, investigation_id, source_file_id
                )
                if item["id"] == mapping_id
            ),
            None,
        )

    def confirm_source_mappings(
        self, organization_id: str, investigation_id: str, source_file_id: str
    ) -> dict[str, Any] | None:
        with connection(self._database_url) as conn:
            org_uuid = self._organization_uuid(conn, organization_id)
            if org_uuid is None:
                return None
            mappings = self.list_source_mappings(organization_id, investigation_id, source_file_id)
            if not mappings:
                return None
            missing = [
                item
                for item in mappings
                if item["required"] and (item["ignored"] or not item["canonical_field"])
            ]
            if missing:
                return {
                    "valid": False,
                    "missing_fields": [str(item["source_column"]) for item in missing],
                }
            conn.execute(
                """
                UPDATE source_mappings SET status = 'CONFIRMED', updated_at = now()
                WHERE organization_id = %s AND source_file_id = %s
                """,
                (org_uuid, source_file_id),
            )
            conn.execute(
                """
                UPDATE source_files SET status = 'READY'
                WHERE organization_id = %s AND source_file_id = %s
                """,
                (org_uuid, source_file_id),
            )
            conn.execute(
                """
                UPDATE financial_investigations fi SET status = 'RELATIONSHIP_REVIEW', updated_at = now()
                WHERE fi.organization_id = %s AND fi.source_investigation_id = %s
                  AND NOT EXISTS (
                    SELECT 1 FROM source_files sf
                    WHERE sf.organization_id = fi.organization_id
                      AND sf.financial_investigation_id = fi.id
                      AND sf.status <> 'READY'
                  )
                """,
                (org_uuid, investigation_id),
            )
            return {
                "valid": True,
                "confirmed_mapping_count": len(mappings),
                "ignored_column_count": sum(1 for item in mappings if item["ignored"]),
            }

    def list_relationship_proposals(
        self, organization_id: str, investigation_id: str
    ) -> list[dict[str, Any]]:
        with connection(self._database_url) as conn:
            org_uuid = self._organization_uuid(conn, organization_id)
            if org_uuid is None:
                return []
            rows = conn.execute(
                """SELECT rp.id, rp.organization_id::text AS organization_id, fi.source_investigation_id AS financial_investigation_id, rp.source_file_id, rp.target_source_file_id, rp.join_fields, rp.evidence_summary, rp.confidence, rp.status, rp.confidence_label, rp.left_columns, rp.right_columns, rp.value_overlap_percent, rp.duplicate_key_rate_percent, rp.cardinality, rp.type_compatibility, rp.temporal_consistency_percent, rp.amount_agreement_percent, rp.updated_at FROM relationship_proposals rp JOIN financial_investigations fi ON fi.id = rp.financial_investigation_id AND fi.organization_id = rp.organization_id WHERE rp.organization_id = %s AND fi.source_investigation_id = %s ORDER BY rp.updated_at DESC""",
                (org_uuid, investigation_id),
            ).fetchall()
            return [self._public_organization(row, organization_id) for row in rows]

    def save_relationship_proposals(
        self, organization_id: str, investigation_id: str, proposals: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        with connection(self._database_url) as conn:
            org_uuid = self._organization_uuid(conn, organization_id)
            investigation = (
                conn.execute(
                    "SELECT id FROM financial_investigations WHERE organization_id = %s AND source_investigation_id = %s",
                    (org_uuid, investigation_id),
                ).fetchone()
                if org_uuid
                else None
            )
            if investigation is None:
                return []
            for proposal in proposals:
                conn.execute(
                    """INSERT INTO relationship_proposals (id, organization_id, financial_investigation_id, source_file_id, target_source_file_id, join_fields, evidence_summary, confidence, status, confidence_label, left_columns, right_columns, value_overlap_percent, duplicate_key_rate_percent, cardinality, type_compatibility, temporal_consistency_percent, amount_agreement_percent, updated_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (organization_id, financial_investigation_id, source_file_id, target_source_file_id) DO UPDATE SET join_fields = EXCLUDED.join_fields, evidence_summary = EXCLUDED.evidence_summary, confidence = EXCLUDED.confidence, confidence_label = EXCLUDED.confidence_label, left_columns = EXCLUDED.left_columns, right_columns = EXCLUDED.right_columns, value_overlap_percent = EXCLUDED.value_overlap_percent, duplicate_key_rate_percent = EXCLUDED.duplicate_key_rate_percent, cardinality = EXCLUDED.cardinality, type_compatibility = EXCLUDED.type_compatibility, temporal_consistency_percent = EXCLUDED.temporal_consistency_percent, amount_agreement_percent = EXCLUDED.amount_agreement_percent, updated_at = EXCLUDED.updated_at""",
                    (
                        proposal["id"],
                        org_uuid,
                        investigation["id"],
                        proposal["source_file_id"],
                        proposal["target_source_file_id"],
                        Json(proposal["join_fields"]),
                        proposal["evidence_summary"],
                        proposal["confidence"],
                        proposal["status"],
                        proposal.get("confidence_label", "LOW"),
                        Json(proposal.get("left_columns", [])),
                        Json(proposal.get("right_columns", [])),
                        proposal.get("value_overlap_percent", 0),
                        proposal.get("duplicate_key_rate_percent", 0),
                        proposal.get("cardinality", "UNKNOWN"),
                        proposal.get("type_compatibility", "UNKNOWN"),
                        proposal.get("temporal_consistency_percent"),
                        proposal.get("amount_agreement_percent"),
                        proposal["updated_at"],
                    ),
                )
        return self.list_relationship_proposals(organization_id, investigation_id)

    def update_relationship_proposal(
        self, organization_id: str, investigation_id: str, relationship_id: str, status: str
    ) -> dict[str, Any] | None:
        with connection(self._database_url) as conn:
            org_uuid = self._organization_uuid(conn, organization_id)
            conn.execute(
                """UPDATE relationship_proposals rp SET status = %s, updated_at = now() FROM financial_investigations fi WHERE rp.financial_investigation_id = fi.id AND rp.organization_id = fi.organization_id AND rp.organization_id = %s AND fi.source_investigation_id = %s AND rp.id = %s""",
                (status, org_uuid, investigation_id, relationship_id),
            )
        return next(
            (
                item
                for item in self.list_relationship_proposals(organization_id, investigation_id)
                if item["id"] == relationship_id
            ),
            None,
        )

    def next_dataset_version(self, organization_id: str, investigation_id: str) -> int:
        with connection(self._database_url) as conn:
            org_uuid = self._organization_uuid(conn, organization_id)
            row = conn.execute(
                "SELECT COALESCE(MAX(dv.version_no), 0) + 1 AS next_version FROM dataset_versions dv JOIN financial_investigations fi ON fi.id = dv.financial_investigation_id AND fi.organization_id = dv.organization_id WHERE dv.organization_id = %s AND fi.source_investigation_id = %s",
                (org_uuid, investigation_id),
            ).fetchone()
            return int(row["next_version"])

    def save_dataset_version(
        self, organization_id: str, version: dict[str, Any], records: list[dict[str, Any]]
    ) -> dict[str, Any]:
        with connection(self._database_url) as conn:
            org_uuid = self._organization_uuid(conn, organization_id)
            investigation = conn.execute(
                "SELECT id FROM financial_investigations WHERE organization_id = %s AND source_investigation_id = %s",
                (org_uuid, version["financial_investigation_id"]),
            ).fetchone()
            conn.execute(
                "INSERT INTO dataset_versions (id, organization_id, financial_investigation_id, version_no, status, record_count, source_count, created_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    version["id"],
                    org_uuid,
                    investigation["id"],
                    version["version_no"],
                    version["status"],
                    version["record_count"],
                    version["source_count"],
                    version["created_at"],
                ),
            )
            for record in records:
                conn.execute(
                    "INSERT INTO normalized_records (id, organization_id, dataset_version_id, source_file_id, source_row_number, source_record_id, source_type, values, lineage) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (
                        record["id"],
                        org_uuid,
                        version["id"],
                        record["source_file_id"],
                        record["source_row_number"],
                        record["source_record_id"],
                        record["source_type"],
                        Json(record["values"]),
                        Json(record["lineage"]),
                    ),
                )
        return (
            self.latest_dataset_version(organization_id, str(version["financial_investigation_id"]))
            or {}
        )

    def latest_dataset_version(
        self, organization_id: str, investigation_id: str
    ) -> dict[str, Any] | None:
        with connection(self._database_url) as conn:
            org_uuid = self._organization_uuid(conn, organization_id)
            row = conn.execute(
                "SELECT dv.id, dv.organization_id::text AS organization_id, fi.source_investigation_id AS financial_investigation_id, dv.version_no, dv.status, dv.record_count, dv.source_count, dv.created_at FROM dataset_versions dv JOIN financial_investigations fi ON fi.id = dv.financial_investigation_id AND fi.organization_id = dv.organization_id WHERE dv.organization_id = %s AND fi.source_investigation_id = %s ORDER BY dv.version_no DESC LIMIT 1",
                (org_uuid, investigation_id),
            ).fetchone()
            return self._public_organization(row, organization_id) if row else None

    def list_dataset_versions(
        self, organization_id: str, investigation_id: str
    ) -> list[dict[str, Any]]:
        with connection(self._database_url) as conn:
            org_uuid = self._organization_uuid(conn, organization_id)
            rows = conn.execute(
                "SELECT dv.id, dv.organization_id::text AS organization_id, fi.source_investigation_id AS financial_investigation_id, dv.version_no, dv.status, dv.record_count, dv.source_count, dv.created_at FROM dataset_versions dv JOIN financial_investigations fi ON fi.id = dv.financial_investigation_id AND fi.organization_id = dv.organization_id WHERE dv.organization_id = %s AND fi.source_investigation_id = %s ORDER BY dv.version_no DESC",
                (org_uuid, investigation_id),
            ).fetchall()
            return [self._public_organization(row, organization_id) for row in rows]

    def list_normalized_records(
        self,
        organization_id: str,
        investigation_id: str,
        dataset_version_id: str,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        with connection(self._database_url) as conn:
            org_uuid = self._organization_uuid(conn, organization_id)
            rows = conn.execute(
                "SELECT nr.id, nr.source_file_id, nr.source_row_number, nr.source_record_id, nr.source_type, nr.values, nr.lineage FROM normalized_records nr JOIN dataset_versions dv ON dv.id = nr.dataset_version_id AND dv.organization_id = nr.organization_id JOIN financial_investigations fi ON fi.id = dv.financial_investigation_id AND fi.organization_id = dv.organization_id WHERE nr.organization_id = %s AND fi.source_investigation_id = %s AND nr.dataset_version_id = %s ORDER BY nr.source_file_id, nr.source_row_number LIMIT %s",
                (org_uuid, investigation_id, dataset_version_id, max(limit, 1)),
            ).fetchall()
            return [self._public_organization(row, organization_id) for row in rows]

    def save_reconciliation_run(
        self, organization_id: str, run: dict[str, Any], results: list[dict[str, Any]]
    ) -> dict[str, Any]:
        with connection(self._database_url) as conn:
            org_uuid = self._organization_uuid(conn, organization_id)
            investigation = conn.execute(
                "SELECT id FROM financial_investigations WHERE organization_id = %s AND source_investigation_id = %s",
                (org_uuid, run["financial_investigation_id"]),
            ).fetchone()
            if investigation is None:
                return {}
            conn.execute(
                "INSERT INTO financial_reconciliation_runs (id, organization_id, financial_investigation_id, dataset_version_id, status, records_expected, records_loaded, records_consumed, orphan_record_count, rejected_record_count, failure_reason, lifecycle_count, reconciled_count, exception_count, ambiguous_count, open_exposure_minor, started_at, completed_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    run["id"],
                    org_uuid,
                    investigation["id"],
                    run["dataset_version_id"],
                    run["status"],
                    run.get("records_expected", 0),
                    run.get("records_loaded", 0),
                    run.get("records_consumed", 0),
                    run.get("orphan_record_count", 0),
                    run.get("rejected_record_count", 0),
                    run.get("failure_reason"),
                    run["lifecycle_count"],
                    run["reconciled_count"],
                    run["exception_count"],
                    run["ambiguous_count"],
                    run["open_exposure_minor"],
                    run["started_at"],
                    run["completed_at"],
                ),
            )
            for result in results:
                conn.execute(
                    "INSERT INTO financial_reconciliation_results (id, organization_id, run_id, order_id, status, exception_type, severity, exposure_minor, exposure_category, findings) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (
                        result["id"],
                        org_uuid,
                        run["id"],
                        result["order_id"],
                        result["status"],
                        result["exception_type"],
                        result["severity"],
                        result["exposure_minor"],
                        result.get("exposure_category", "DATA_QUALITY"),
                        Json(result["findings"]),
                    ),
                )
        return (
            self.latest_reconciliation_run(organization_id, str(run["financial_investigation_id"]))
            or {}
        )

    def latest_workspace_run(self, organization_id: str) -> dict[str, Any] | None:
        with connection(self._database_url) as conn:
            org_uuid = self._organization_uuid(conn, organization_id)
            row = conn.execute(
                "SELECT fi.source_investigation_id FROM financial_reconciliation_runs rr JOIN financial_investigations fi ON fi.id = rr.financial_investigation_id AND fi.organization_id = rr.organization_id WHERE rr.organization_id = %s AND rr.is_stale = false ORDER BY rr.started_at DESC, rr.id DESC LIMIT 1",
                (org_uuid,),
            ).fetchone()
        return self.latest_reconciliation_run(organization_id, str(row["source_investigation_id"])) if row else None

    def latest_reconciliation_run(
        self, organization_id: str, investigation_id: str
    ) -> dict[str, Any] | None:
        with connection(self._database_url) as conn:
            org_uuid = self._organization_uuid(conn, organization_id)
            row = conn.execute(
                "SELECT rr.id, rr.organization_id::text AS organization_id, fi.source_investigation_id AS financial_investigation_id, rr.dataset_version_id, rr.status, rr.records_expected, rr.records_loaded, rr.records_consumed, rr.orphan_record_count, rr.rejected_record_count, rr.failure_reason, rr.is_stale, rr.stale_reason, rr.lifecycle_count, rr.reconciled_count, rr.exception_count, rr.ambiguous_count, rr.open_exposure_minor, rr.started_at, rr.completed_at FROM financial_reconciliation_runs rr JOIN financial_investigations fi ON fi.id = rr.financial_investigation_id AND fi.organization_id = rr.organization_id WHERE rr.organization_id = %s AND fi.source_investigation_id = %s AND rr.is_stale = false ORDER BY rr.started_at DESC LIMIT 1",
                (org_uuid, investigation_id),
            ).fetchone()
            return self._public_organization(row, organization_id) if row else None

    def list_reconciliation_results(
        self, organization_id: str, investigation_id: str, run_id: str, limit: int = 1000
    ) -> list[dict[str, Any]]:
        with connection(self._database_url) as conn:
            org_uuid = self._organization_uuid(conn, organization_id)
            rows = conn.execute(
                "SELECT r.id, r.run_id, r.order_id, r.status, r.exception_type, r.severity, r.exposure_minor, r.exposure_category, r.findings FROM financial_reconciliation_results r JOIN financial_reconciliation_runs rr ON rr.id = r.run_id AND rr.organization_id = r.organization_id JOIN financial_investigations fi ON fi.id = rr.financial_investigation_id AND fi.organization_id = rr.organization_id WHERE r.organization_id = %s AND fi.source_investigation_id = %s AND r.run_id = %s ORDER BY r.order_id LIMIT %s",
                (org_uuid, investigation_id, run_id, min(max(limit, 1), 10000)),
            ).fetchall()
            return [self._public_organization(row, organization_id) for row in rows]

    def get_reconciliation_result(
        self, organization_id: str, investigation_id: str, run_id: str, result_id: str
    ) -> dict[str, Any] | None:
        with connection(self._database_url) as conn:
            org_uuid = self._organization_uuid(conn, organization_id)
            if org_uuid is None:
                return None
            row = conn.execute(
                """
                SELECT r.id, r.run_id, r.order_id, r.status, r.exception_type, r.severity,
                       r.exposure_minor, r.exposure_category, r.findings
                FROM financial_reconciliation_results r
                JOIN financial_reconciliation_runs rr
                  ON rr.id = r.run_id AND rr.organization_id = r.organization_id
                JOIN financial_investigations fi
                  ON fi.id = rr.financial_investigation_id
                 AND fi.organization_id = rr.organization_id
                WHERE r.organization_id = %s
                  AND fi.source_investigation_id = %s
                  AND r.run_id = %s
                  AND r.id = %s
                """,
                (org_uuid, investigation_id, run_id, result_id),
            ).fetchone()
            return self._public_organization(row, organization_id) if row else None

    def save_financial_exception_investigation(
        self, organization_id: str, investigation_id: str, result_id: str, response: dict[str, Any]
    ) -> dict[str, Any]:
        with connection(self._database_url) as conn:
            org_uuid = self._organization_uuid(conn, organization_id)
            investigation = conn.execute(
                "SELECT id FROM financial_investigations WHERE organization_id = %s AND source_investigation_id = %s",
                (org_uuid, investigation_id),
            ).fetchone()
            if investigation is None:
                return {}
            conn.execute(
                "INSERT INTO financial_exception_investigations (id, organization_id, financial_investigation_id, reconciliation_result_id, status, response, provider, model, prompt_version, started_at, completed_at, latency_ms, verifier_passed, verifier_issues, provider_error_category, provider_retryable, failure_stage, failure_iteration, failure_detail, created_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (organization_id, reconciliation_result_id) DO UPDATE SET status = EXCLUDED.status, response = EXCLUDED.response, provider = EXCLUDED.provider, model = EXCLUDED.model, prompt_version = EXCLUDED.prompt_version, started_at = EXCLUDED.started_at, completed_at = EXCLUDED.completed_at, latency_ms = EXCLUDED.latency_ms, verifier_passed = EXCLUDED.verifier_passed, verifier_issues = EXCLUDED.verifier_issues, provider_error_category = EXCLUDED.provider_error_category, provider_retryable = EXCLUDED.provider_retryable, failure_stage = EXCLUDED.failure_stage, failure_iteration = EXCLUDED.failure_iteration, failure_detail = EXCLUDED.failure_detail",
                (
                    response["investigation_id"],
                    org_uuid,
                    investigation["id"],
                    result_id,
                    response["status"],
                    Json(response),
                    response.get("provider"),
                    response.get("model"),
                    response.get("prompt_version"),
                    response.get("started_at"),
                    response.get("completed_at"),
                    response.get("latency_ms", 0),
                    response.get("verifier_passed", False),
                    Json(response.get("verifier_issues", [])),
                    response.get("provider_error_category"),
                    response.get("provider_retryable"),
                    response.get("failure_stage"),
                    response.get("failure_iteration"),
                    response.get("failure_detail"),
                    response["created_at"],
                ),
            )
        return dict(response)

    def get_financial_exception_investigation(
        self, organization_id: str, investigation_id: str, result_id: str
    ) -> dict[str, Any] | None:
        with connection(self._database_url) as conn:
            org_uuid = self._organization_uuid(conn, organization_id)
            row = conn.execute(
                "SELECT fei.response FROM financial_exception_investigations fei JOIN financial_investigations fi ON fi.id = fei.financial_investigation_id AND fi.organization_id = fei.organization_id WHERE fei.organization_id = %s AND fi.source_investigation_id = %s AND fei.reconciliation_result_id = %s",
                (org_uuid, investigation_id, result_id),
            ).fetchone()
            return dict(row["response"]) if row and isinstance(row["response"], dict) else None

    def save_financial_exception_investigation_tool_calls(
        self, organization_id: str, investigation_id: str, tool_calls: list[dict[str, Any]]
    ) -> None:
        with connection(self._database_url) as conn:
            org_uuid = self._organization_uuid(conn, organization_id)
            if org_uuid is None:
                return
            conn.execute(
                "DELETE FROM financial_exception_investigation_tool_calls WHERE organization_id = %s AND financial_exception_investigation_id = %s",
                (org_uuid, investigation_id),
            )
            for call in tool_calls:
                conn.execute(
                    "INSERT INTO financial_exception_investigation_tool_calls (organization_id, financial_exception_investigation_id, sequence_no, name, arguments, result_record_ids, result_summary, duration_ms, status, provider, model) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (
                        org_uuid,
                        investigation_id,
                        call.get("sequence_no", 0),
                        call["name"],
                        Json(call.get("arguments", {})),
                        Json(call.get("result_record_ids", [])),
                        call.get("result_summary", ""),
                        call.get("duration_ms", 0),
                        call.get("status", "UNKNOWN"),
                        call.get("provider", "unknown"),
                        call.get("model", "unknown"),
                    ),
                )

    def save_financial_exception_investigation_with_tool_calls(
        self,
        organization_id: str,
        investigation_id: str,
        result_id: str,
        response: dict[str, Any],
        tool_calls: list[dict[str, Any]],
    ) -> dict[str, Any]:
        with connection(self._database_url) as conn:
            org_uuid = self._organization_uuid(conn, organization_id)
            investigation = conn.execute(
                "SELECT id FROM financial_investigations WHERE organization_id = %s AND source_investigation_id = %s",
                (org_uuid, investigation_id),
            ).fetchone()
            if investigation is None:
                return {}
            conn.execute(
                "INSERT INTO financial_exception_investigations (id, organization_id, financial_investigation_id, reconciliation_result_id, status, response, provider, model, prompt_version, started_at, completed_at, latency_ms, verifier_passed, verifier_issues, provider_error_category, provider_retryable, failure_stage, failure_iteration, failure_detail, created_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (organization_id, reconciliation_result_id) DO UPDATE SET status = EXCLUDED.status, response = EXCLUDED.response, provider = EXCLUDED.provider, model = EXCLUDED.model, prompt_version = EXCLUDED.prompt_version, started_at = EXCLUDED.started_at, completed_at = EXCLUDED.completed_at, latency_ms = EXCLUDED.latency_ms, verifier_passed = EXCLUDED.verifier_passed, verifier_issues = EXCLUDED.verifier_issues, provider_error_category = EXCLUDED.provider_error_category, provider_retryable = EXCLUDED.provider_retryable, failure_stage = EXCLUDED.failure_stage, failure_iteration = EXCLUDED.failure_iteration, failure_detail = EXCLUDED.failure_detail",
                (
                    response["investigation_id"], org_uuid, investigation["id"], result_id,
                    response["status"], Json(response), response.get("provider"), response.get("model"),
                    response.get("prompt_version"), response.get("started_at"), response.get("completed_at"),
                    response.get("latency_ms", 0), response.get("verifier_passed", False),
                    Json(response.get("verifier_issues", [])), response.get("provider_error_category"),
                    response.get("provider_retryable"), response.get("failure_stage"),
                    response.get("failure_iteration"), response.get("failure_detail"), response["created_at"],
                ),
            )
            conn.execute(
                "DELETE FROM financial_exception_investigation_tool_calls WHERE organization_id = %s AND financial_exception_investigation_id = %s",
                (org_uuid, response["investigation_id"]),
            )
            for call in tool_calls:
                conn.execute(
                    "INSERT INTO financial_exception_investigation_tool_calls (organization_id, financial_exception_investigation_id, sequence_no, name, arguments, result_record_ids, result_summary, duration_ms, status, provider, model) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (
                        org_uuid, response["investigation_id"], call.get("sequence_no", 0), call["name"],
                        Json(call.get("arguments", {})), Json(call.get("result_record_ids", [])),
                        call.get("result_summary", ""), call.get("duration_ms", 0), call.get("status", "UNKNOWN"),
                        call.get("provider", "unknown"), call.get("model", "unknown"),
                    ),
                )
        return dict(response)

    def get_financial_exception_investigation_tool_calls(
        self, organization_id: str, investigation_id: str
    ) -> list[dict[str, Any]]:
        with connection(self._database_url) as conn:
            org_uuid = self._organization_uuid(conn, organization_id)
            if org_uuid is None:
                return []
            rows = conn.execute(
                "SELECT sequence_no, name, arguments, result_record_ids, result_summary, duration_ms, status, provider, model FROM financial_exception_investigation_tool_calls WHERE organization_id = %s AND financial_exception_investigation_id = %s ORDER BY sequence_no",
                (org_uuid, investigation_id),
            ).fetchall()
            return [dict(row) for row in rows]

    def lifecycle(self, organization_id: str, order_id: str) -> CanonicalLifecycle:
        with connection(self._database_url) as conn:
            org_uuid = self._organization_uuid(conn, organization_id)
            if org_uuid is None:
                raise LifecycleNotFoundError(order_id)
            order = conn.execute(
                """
                SELECT source_order_id AS order_id, organization_id, store_code AS store,
                       amount_minor, status, created_at
                FROM orders
                WHERE organization_id = %s AND source_order_id = %s
                """,
                (org_uuid, order_id),
            ).fetchone()
            if order is None:
                raise LifecycleNotFoundError(order_id)
            order["organization_id"] = organization_id
            payments = self._rows(
                conn,
                """
                SELECT p.source_payment_id AS payment_id, o.source_order_id AS order_id,
                       p.organization_id, p.amount_minor, p.status, p.gateway_fee_minor,
                       p.captured_at
                FROM payments p JOIN orders o ON o.id = p.order_id AND o.organization_id = p.organization_id
                WHERE p.organization_id = %s AND o.source_order_id = %s
            """,
                (org_uuid, order_id),
                organization_id,
            )
            payment_ids = [row["payment_id"] for row in payments]
            settlements = self._rows(
                conn,
                """
                SELECT s.source_settlement_id AS settlement_id, s.organization_id,
                       p.source_payment_id AS payment_id, s.gross_minor, s.fees_minor,
                       s.tax_minor, s.net_minor, s.settled_at, s.status
                FROM settlements s JOIN payments p ON p.id = s.payment_id AND p.organization_id = s.organization_id
                WHERE s.organization_id = %s AND p.source_payment_id = ANY(%s)
            """,
                (org_uuid, payment_ids),
                organization_id,
            )
            refunds = self._rows(
                conn,
                """
                SELECT r.source_refund_id AS refund_id, r.organization_id,
                       p.source_payment_id AS payment_id, r.amount_minor, r.status, r.processed_at
                FROM refunds r JOIN payments p ON p.id = r.payment_id AND p.organization_id = r.organization_id
                WHERE r.organization_id = %s AND p.source_payment_id = ANY(%s)
            """,
                (org_uuid, payment_ids),
                organization_id,
            )
            invoices = self._rows(
                conn,
                """
                SELECT i.source_invoice_id AS invoice_id, i.organization_id,
                       o.source_order_id AS order_id, i.gross_minor, i.status, i.created_at
                FROM invoices i JOIN orders o ON o.id = i.order_id AND o.organization_id = i.organization_id
                WHERE i.organization_id = %s AND o.source_order_id = %s
            """,
                (org_uuid, order_id),
                organization_id,
            )
            inventory = self._rows(
                conn,
                """
                SELECT m.source_movement_id AS movement_id, m.organization_id,
                       o.source_order_id AS order_id, m.sku, m.quantity, m.movement_type,
                       m.unit_cost_minor, m.inventory_value_minor, m.occurred_at
                FROM inventory_movements m JOIN orders o ON o.id = m.order_id AND o.organization_id = m.organization_id
                WHERE m.organization_id = %s AND o.source_order_id = %s
            """,
                (org_uuid, order_id),
                organization_id,
            )
            actions = self._rows(
                conn,
                """
                SELECT a.source_action_id AS action_id, a.organization_id, a.entity_type,
                       a.entity_id, a.employee_id, a.action, a.occurred_at
                FROM employee_actions a
                WHERE a.organization_id = %s AND a.entity_id = %s
            """,
                (org_uuid, order_id),
                organization_id,
            )
            return CanonicalLifecycle(
                order=order,
                payments=tuple(payments),
                settlements=tuple(settlements),
                invoices=tuple(invoices),
                refunds=tuple(refunds),
                inventory_movements=tuple(inventory),
                employee_actions=tuple(actions),
            )

    def list_lifecycles(self, organization_id: str, limit: int = 1000) -> list[CanonicalLifecycle]:
        with connection(self._database_url) as conn:
            org_uuid = self._organization_uuid(conn, organization_id)
            if org_uuid is None:
                return []
            orders = conn.execute(
                "SELECT id, source_order_id AS order_id, organization_id, store_code AS store, amount_minor, status, created_at FROM orders WHERE organization_id = %s ORDER BY created_at LIMIT %s",
                (org_uuid, min(max(limit, 1), 10000)),
            ).fetchall()
            if not orders:
                return []
            order_ids = [row["order_id"] for row in orders]
            payments = self._rows(
                conn,
                """
                SELECT p.source_payment_id AS payment_id, o.source_order_id AS order_id,
                       p.amount_minor, p.status, p.gateway_fee_minor, p.captured_at
                FROM payments p JOIN orders o ON o.id = p.order_id AND o.organization_id = p.organization_id
                WHERE p.organization_id = %s AND o.source_order_id = ANY(%s)
            """,
                (org_uuid, order_ids),
                organization_id,
            )
            payment_ids = [row["payment_id"] for row in payments]
            settlements = self._rows(
                conn,
                """
                SELECT s.source_settlement_id AS settlement_id, p.source_payment_id AS payment_id,
                       s.gross_minor, s.fees_minor, s.tax_minor, s.net_minor, s.settled_at, s.status
                FROM settlements s JOIN payments p ON p.id = s.payment_id AND p.organization_id = s.organization_id
                WHERE s.organization_id = %s AND p.source_payment_id = ANY(%s)
            """,
                (org_uuid, payment_ids),
                organization_id,
            )
            refunds = self._rows(
                conn,
                """
                SELECT r.source_refund_id AS refund_id, p.source_payment_id AS payment_id,
                       r.amount_minor, r.status, r.processed_at
                FROM refunds r JOIN payments p ON p.id = r.payment_id AND p.organization_id = r.organization_id
                WHERE r.organization_id = %s AND p.source_payment_id = ANY(%s)
            """,
                (org_uuid, payment_ids),
                organization_id,
            )
            invoices = self._rows(
                conn,
                """
                SELECT i.source_invoice_id AS invoice_id, o.source_order_id AS order_id,
                       i.gross_minor, i.status, i.created_at
                FROM invoices i JOIN orders o ON o.id = i.order_id AND o.organization_id = i.organization_id
                WHERE i.organization_id = %s AND o.source_order_id = ANY(%s)
            """,
                (org_uuid, order_ids),
                organization_id,
            )
            inventory = self._rows(
                conn,
                """
                SELECT m.source_movement_id AS movement_id, o.source_order_id AS order_id,
                       m.sku, m.quantity, m.movement_type, m.unit_cost_minor,
                       m.inventory_value_minor, m.occurred_at
                FROM inventory_movements m JOIN orders o ON o.id = m.order_id AND o.organization_id = m.organization_id
                WHERE m.organization_id = %s AND o.source_order_id = ANY(%s)
            """,
                (org_uuid, order_ids),
                organization_id,
            )
            actions = self._rows(
                conn,
                """
                SELECT a.source_action_id AS action_id, a.entity_type, a.entity_id,
                       a.employee_id, a.action, a.occurred_at
                FROM employee_actions a
                WHERE a.organization_id = %s AND a.entity_id = ANY(%s)
            """,
                (org_uuid, order_ids),
                organization_id,
            )
            payments_by_order: dict[str, list[dict[str, Any]]] = {}
            for row in payments:
                payments_by_order.setdefault(str(row["order_id"]), []).append(row)
            settlements_by_payment: dict[str, list[dict[str, Any]]] = {}
            for row in settlements:
                settlements_by_payment.setdefault(str(row["payment_id"]), []).append(row)
            refunds_by_payment: dict[str, list[dict[str, Any]]] = {}
            for row in refunds:
                refunds_by_payment.setdefault(str(row["payment_id"]), []).append(row)
            invoices_by_order: dict[str, list[dict[str, Any]]] = {}
            inventory_by_order: dict[str, list[dict[str, Any]]] = {}
            actions_by_order: dict[str, list[dict[str, Any]]] = {}
            for row in invoices:
                invoices_by_order.setdefault(str(row["order_id"]), []).append(row)
            for row in inventory:
                inventory_by_order.setdefault(str(row["order_id"]), []).append(row)
            for row in actions:
                actions_by_order.setdefault(str(row["entity_id"]), []).append(row)
            lifecycles: list[CanonicalLifecycle] = []
            for order in orders:
                order_id = str(order["order_id"])
                order_payments = payments_by_order.get(order_id, [])
                lifecycles.append(
                    CanonicalLifecycle(
                        order={key: value for key, value in order.items() if key != "id"}
                        | {"organization_id": organization_id},
                        payments=tuple(order_payments),
                        settlements=tuple(
                            item
                            for payment in order_payments
                            for item in settlements_by_payment.get(str(payment["payment_id"]), [])
                        ),
                        invoices=tuple(invoices_by_order.get(order_id, [])),
                        refunds=tuple(
                            item
                            for payment in order_payments
                            for item in refunds_by_payment.get(str(payment["payment_id"]), [])
                        ),
                        inventory_movements=tuple(inventory_by_order.get(order_id, [])),
                        employee_actions=tuple(actions_by_order.get(order_id, [])),
                    )
                )
            return lifecycles

    def record_audit_event(
        self,
        organization_id: str,
        event_type: str,
        resource_id: str,
        actor_id: str = "system",
        correlation_id: str | None = None,
    ) -> None:
        with connection(self._database_url) as conn:
            org_uuid = self._organization_uuid(conn, organization_id)
            if org_uuid is None:
                return
            conn.execute(
                """
                INSERT INTO audit_events
                  (organization_id, actor_type, actor_id, action, resource_type, resource_id, correlation_id)
                VALUES (%s, 'USER', %s, %s, 'FINTRACE_RESOURCE', %s, %s)
                """,
                (
                    org_uuid,
                    actor_id,
                    event_type,
                    resource_id,
                    correlation_id or current_request_id() or resource_id,
                ),
            )

    def audit_events(self, organization_id: str, resource_id: str, limit: int = 200) -> list[dict[str, str]]:
        return self._audit_query(organization_id, "resource_id = %s", (resource_id,), limit)

    def audit_events_for_organization(self, organization_id: str, limit: int = 200) -> list[dict[str, str]]:
        return self._audit_query(organization_id, "TRUE", (), limit)

    def _audit_query(
        self, organization_id: str, predicate: str, params: tuple[Any, ...], limit: int = 200
    ) -> list[dict[str, str]]:
        with connection(self._database_url) as conn:
            org_uuid = self._organization_uuid(conn, organization_id)
            if org_uuid is None:
                return []
            rows = conn.execute(
                f"""
                SELECT id::text AS event_id, actor_id, action, resource_id,
                       correlation_id, created_at
                FROM audit_events
                WHERE organization_id = %s AND {predicate}
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (org_uuid, *params, min(max(limit, 1), 500)),
            ).fetchall()
            return [
                {
                    "event_id": str(row["event_id"]),
                    "organization_id": organization_id,
                    "actor_id": str(row["actor_id"]),
                    "action": str(row["action"]),
                    "resource_id": str(row["resource_id"] or ""),
                    "correlation_id": str(row["correlation_id"]),
                    "created_at": row["created_at"].isoformat()
                    if hasattr(row["created_at"], "isoformat")
                    else str(row["created_at"]),
                }
                for row in rows
            ]

    def get_idempotency(self, organization_id: str, idempotency_key: str) -> dict[str, Any] | None:
        with connection(self._database_url) as conn:
            org_uuid = self._organization_uuid(conn, organization_id)
            if org_uuid is None:
                return None
            row = conn.execute(
                """
                SELECT actor_id, request_hash, response_status, response_body
                FROM idempotency_keys
                WHERE organization_id = %s AND idempotency_key = %s
                """,
                (org_uuid, idempotency_key),
            ).fetchone()
            return dict(row) if row else None

    def put_idempotency(
        self,
        organization_id: str,
        actor_id: str,
        idempotency_key: str,
        request_hash: str,
        response_status: int,
        response_body: dict[str, Any],
    ) -> None:
        with connection(self._database_url) as conn:
            org_uuid = self._organization_uuid(conn, organization_id)
            if org_uuid is None:
                return
            conn.execute(
                """
                INSERT INTO idempotency_keys
                  (organization_id, actor_id, idempotency_key, request_hash, response_status, response_body)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (organization_id, idempotency_key) DO NOTHING
                """,
                (
                    org_uuid,
                    actor_id,
                    idempotency_key,
                    request_hash,
                    response_status,
                    Json(response_body),
                ),
            )

    def reserve_idempotency(
        self, organization_id: str, actor_id: str, idempotency_key: str, request_hash: str
    ) -> dict[str, Any] | None:
        with connection(self._database_url) as conn:
            org_uuid = self._organization_uuid(conn, organization_id)
            if org_uuid is None:
                return None
            lease_seconds = get_settings().idempotency_lease_seconds
            reclaimed = conn.execute(
                """
                UPDATE idempotency_keys
                SET actor_id = %s, request_hash = %s, response_status = 425,
                    response_body = %s,
                    expires_at = now() + make_interval(secs => %s)
                WHERE organization_id = %s AND idempotency_key = %s
                  AND response_status = 425
                  AND (expires_at IS NULL OR expires_at <= now())
                RETURNING id
                """,
                (actor_id, request_hash, Json({"status": "PENDING"}), lease_seconds, org_uuid, idempotency_key),
            ).fetchone()
            if reclaimed is not None:
                return None
            inserted = conn.execute(
                """
                INSERT INTO idempotency_keys
                  (organization_id, actor_id, idempotency_key, request_hash, response_status, response_body, expires_at)
                VALUES (%s, %s, %s, %s, 425, %s, now() + make_interval(secs => %s))
                ON CONFLICT (organization_id, idempotency_key) DO NOTHING
                RETURNING actor_id
                """,
                (org_uuid, actor_id, idempotency_key, request_hash, Json({"status": "PENDING"}), lease_seconds),
            ).fetchone()
            if inserted is not None:
                return None
            row = conn.execute(
                "SELECT actor_id, request_hash, response_status, response_body FROM idempotency_keys WHERE organization_id = %s AND idempotency_key = %s",
                (org_uuid, idempotency_key),
            ).fetchone()
            return dict(row) if row else None

    def complete_idempotency(
        self,
        organization_id: str,
        idempotency_key: str,
        response_status: int,
        response_body: dict[str, Any],
    ) -> None:
        with connection(self._database_url) as conn:
            org_uuid = self._organization_uuid(conn, organization_id)
            if org_uuid is not None:
                conn.execute(
                    "UPDATE idempotency_keys SET response_status = %s, response_body = %s WHERE organization_id = %s AND idempotency_key = %s AND response_status = 425",
                    (response_status, Json(response_body), org_uuid, idempotency_key),
                )

    def release_idempotency(self, organization_id: str, idempotency_key: str) -> None:
        with connection(self._database_url) as conn:
            org_uuid = self._organization_uuid(conn, organization_id)
            if org_uuid is not None:
                conn.execute(
                    "DELETE FROM idempotency_keys WHERE organization_id = %s AND idempotency_key = %s AND response_status = 425",
                    (org_uuid, idempotency_key),
                )

    def save_investigation(self, organization_id: str, response: dict[str, Any]) -> None:
        with connection(self._database_url) as conn:
            org_uuid = self._organization_uuid(conn, organization_id)
            if org_uuid is None:
                return
            exception = conn.execute(
                "SELECT id FROM exceptions WHERE organization_id = %s AND source_exception_id = %s",
                (org_uuid, response["exception_id"]),
            ).fetchone()
            uploaded_result = conn.execute(
                "SELECT id FROM financial_reconciliation_results WHERE organization_id = %s AND id = %s",
                (org_uuid, response["exception_id"]),
            ).fetchone()
            if exception is None and uploaded_result is None:
                return
            conn.execute(
                """
                INSERT INTO investigations
                  (organization_id, source_investigation_id, exception_id, status, response, created_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (organization_id, source_investigation_id) DO UPDATE
                  SET status = EXCLUDED.status, response = EXCLUDED.response
                """,
                (
                    org_uuid,
                    response["investigation_id"],
                    exception["id"],
                    response["status"],
                    Json(response),
                    response["created_at"],
                ),
            )
            investigation = conn.execute(
                "SELECT id FROM investigations WHERE organization_id = %s AND source_investigation_id = %s",
                (org_uuid, response["investigation_id"]),
            ).fetchone()
            conn.execute(
                "DELETE FROM investigation_tool_calls WHERE organization_id = %s AND investigation_id = %s",
                (org_uuid, investigation["id"]),
            )
            for sequence_no, call in enumerate(response.get("tool_calls", []), start=1):
                conn.execute(
                    """
                    INSERT INTO investigation_tool_calls
                      (organization_id, investigation_id, sequence_no, name, payload)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (org_uuid, investigation["id"], sequence_no, call["name"], Json(call)),
                )

    def get_investigation(
        self, organization_id: str, investigation_id: str
    ) -> dict[str, Any] | None:
        with connection(self._database_url) as conn:
            org_uuid = self._organization_uuid(conn, organization_id)
            if org_uuid is None:
                return None
            row = conn.execute(
                "SELECT response FROM investigations WHERE organization_id = %s AND source_investigation_id = %s",
                (org_uuid, investigation_id),
            ).fetchone()
            return dict(row["response"]) if row else None

    def get_investigation_tool_calls(
        self, organization_id: str, investigation_id: str
    ) -> list[dict[str, Any]]:
        with connection(self._database_url) as conn:
            org_uuid = self._organization_uuid(conn, organization_id)
            if org_uuid is None:
                return []
            rows = conn.execute(
                """
                SELECT tc.payload
                FROM investigation_tool_calls tc
                JOIN investigations i ON i.id = tc.investigation_id AND i.organization_id = tc.organization_id
                WHERE tc.organization_id = %s AND i.source_investigation_id = %s
                ORDER BY tc.sequence_no
                """,
                (org_uuid, investigation_id),
            ).fetchall()
            return [dict(row["payload"]) for row in rows]

    def save_evaluation(self, organization_id: str, response: dict[str, Any]) -> None:
        with connection(self._database_url) as conn:
            org_uuid = self._organization_uuid(conn, organization_id)
            if org_uuid is None:
                return
            conn.execute(
                """
                INSERT INTO evaluation_runs
                  (organization_id, source_evaluation_id, response, created_at)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (organization_id, source_evaluation_id) DO UPDATE SET response = EXCLUDED.response
                """,
                (org_uuid, response["evaluation_id"], Json(response), response["created_at"]),
            )

    def get_latest_evaluation(self, organization_id: str) -> dict[str, Any] | None:
        with connection(self._database_url) as conn:
            org_uuid = self._organization_uuid(conn, organization_id)
            if org_uuid is None:
                return None
            row = conn.execute(
                """
                SELECT response FROM evaluation_runs
                WHERE organization_id = %s
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (org_uuid,),
            ).fetchone()
            return dict(row["response"]) if row else None

    def get_latest_ai_evaluation(self, organization_id: str) -> dict[str, Any] | None:
        with connection(self._database_url) as conn:
            org_uuid = self._organization_uuid(conn, organization_id)
            if org_uuid is None:
                return None
            row = conn.execute(
                "SELECT response FROM evaluation_runs WHERE organization_id = %s AND response->>'evaluation_kind' = 'AI_INVESTIGATION' ORDER BY created_at DESC LIMIT 1",
                (org_uuid,),
            ).fetchone()
            return dict(row["response"]) if row else None

    def save_resolution_request(self, organization_id: str, response: dict[str, Any]) -> None:
        with connection(self._database_url) as conn:
            org_uuid = self._organization_uuid(conn, organization_id)
            if org_uuid is None:
                return
            exception = conn.execute(
                "SELECT id FROM exceptions WHERE organization_id = %s AND source_exception_id = %s",
                (org_uuid, response["exception_id"]),
            ).fetchone()
            uploaded_result = conn.execute(
                "SELECT id FROM financial_reconciliation_results WHERE organization_id = %s AND id = %s",
                (org_uuid, response["exception_id"]),
            ).fetchone()
            if exception is None and uploaded_result is None:
                return
            exposure_minor = int(Decimal(str(response["financial_exposure"])) * 100)
            conn.execute(
                """
                INSERT INTO approval_requests
                  (organization_id, source_request_id, exception_id, financial_reconciliation_result_id, action_code, status,
                   financial_exposure_minor, currency, required_capability, required_approvals,
                   approvals_received, requester_actor_id, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT DO NOTHING
                """,
                (
                    org_uuid,
                    response["request_id"],
                    exception["id"] if exception else None,
                    uploaded_result["id"] if uploaded_result else None,
                    response["action_code"],
                    response["status"],
                    exposure_minor,
                    response["currency"],
                    response["required_capability"],
                    response["required_approvals"],
                    response["approvals_received"],
                    response["requester_id"],
                    response["created_at"],
                    response["created_at"],
                ),
            )

    def get_resolution_request(
        self, organization_id: str, request_id: str
    ) -> dict[str, Any] | None:
        with connection(self._database_url) as conn:
            org_uuid = self._organization_uuid(conn, organization_id)
            if org_uuid is None:
                return None
            row = conn.execute(
                """
                SELECT ar.source_request_id, e.source_exception_id, ar.financial_reconciliation_result_id, ar.action_code, ar.status,
                       ar.financial_exposure_minor, ar.currency, ar.required_capability,
                       ar.required_approvals, ar.approvals_received, ar.requester_actor_id, ar.created_at
                FROM approval_requests ar
                LEFT JOIN exceptions e ON e.id = ar.exception_id AND e.organization_id = ar.organization_id
                WHERE ar.organization_id = %s AND ar.source_request_id = %s
                """,
                (org_uuid, request_id),
            ).fetchone()
            if row is None:
                return None
            decisions = conn.execute(
                "SELECT actor_id FROM approval_decisions ad JOIN approval_requests ar ON ar.id = ad.approval_request_id AND ar.organization_id = ad.organization_id WHERE ad.organization_id = %s AND ar.source_request_id = %s ORDER BY ad.created_at",
                (org_uuid, request_id),
            ).fetchall()
            return {
                "request_id": row["source_request_id"],
                "exception_id": row["source_exception_id"]
                or row["financial_reconciliation_result_id"],
                "action_code": row["action_code"],
                "status": row["status"],
                "financial_exposure": Decimal(int(row["financial_exposure_minor"])) / Decimal(100),
                "currency": row["currency"],
                "required_capability": row["required_capability"],
                "required_approvals": row["required_approvals"],
                "approvals_received": row["approvals_received"],
                "requester_id": row["requester_actor_id"],
                "created_at": row["created_at"],
                "approver_ids": [str(decision["actor_id"]) for decision in decisions],
            }

    def update_resolution_request(self, organization_id: str, response: dict[str, Any]) -> None:
        with connection(self._database_url) as conn:
            org_uuid = self._organization_uuid(conn, organization_id)
            if org_uuid is None:
                return
            conn.execute(
                "UPDATE approval_requests SET status = %s, approvals_received = %s, updated_at = now() WHERE organization_id = %s AND source_request_id = %s",
                (
                    response["status"],
                    response["approvals_received"],
                    org_uuid,
                    response["request_id"],
                ),
            )

    def save_approval_decision(
        self,
        organization_id: str,
        request_id: str,
        actor_id: str,
        decision: str,
        approval_id: str,
        decided_at: str,
    ) -> bool:
        with connection(self._database_url) as conn:
            org_uuid = self._organization_uuid(conn, organization_id)
            if org_uuid is None:
                return False
            request = conn.execute(
                "SELECT id FROM approval_requests WHERE organization_id = %s AND source_request_id = %s FOR UPDATE",
                (org_uuid, request_id),
            ).fetchone()
            if request is None:
                return False
            inserted = conn.execute(
                """
                INSERT INTO approval_decisions
                  (organization_id, approval_request_id, source_approval_id, actor_id, decision, created_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (organization_id, approval_request_id, actor_id) DO NOTHING
                RETURNING id
                """,
                (org_uuid, request["id"], approval_id, actor_id, decision, decided_at),
            ).fetchone()
            return inserted is not None

    def apply_approval_decision(
        self,
        organization_id: str,
        request_id: str,
        actor_id: str,
        decision: str,
        approval_id: str,
        decided_at: str,
    ) -> dict[str, Any] | None:
        """Insert a decision and derive request state under one row lock."""
        with connection(self._database_url) as conn:
            org_uuid = self._organization_uuid(conn, organization_id)
            if org_uuid is None:
                return None
            request = conn.execute(
                """
                SELECT id, status, required_approvals
                FROM approval_requests
                WHERE organization_id = %s AND source_request_id = %s
                FOR UPDATE
                """,
                (org_uuid, request_id),
            ).fetchone()
            if request is None:
                return None
            if request["status"] != "PENDING_APPROVAL":
                return {"applied": False, "reason": "not_pending"}
            inserted = conn.execute(
                """
                INSERT INTO approval_decisions
                  (organization_id, approval_request_id, source_approval_id, actor_id, decision, created_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (organization_id, approval_request_id, actor_id) DO NOTHING
                RETURNING id
                """,
                (org_uuid, request["id"], approval_id, actor_id, decision, decided_at),
            ).fetchone()
            if inserted is None:
                return {"applied": False, "reason": "duplicate"}
            counts = conn.execute(
                """
                SELECT COUNT(*) FILTER (WHERE decision = 'APPROVED') AS approvals_received
                FROM approval_decisions
                WHERE organization_id = %s AND approval_request_id = %s
                """,
                (org_uuid, request["id"]),
            ).fetchone()
            approvals_received = int(counts["approvals_received"])
            updated_status = (
                "REJECTED"
                if decision == "REJECTED"
                else (
                    "APPROVED"
                    if approvals_received >= int(request["required_approvals"])
                    else "PENDING_APPROVAL"
                )
            )
            conn.execute(
                """
                UPDATE approval_requests
                SET status = %s, approvals_received = %s, updated_at = now()
                WHERE organization_id = %s AND id = %s
                """,
                (updated_status, approvals_received, org_uuid, request["id"]),
            )
            return {
                "applied": True,
                "status": updated_status,
                "approvals_received": approvals_received,
            }

    @staticmethod
    def _public_organization(row: Any, organization_id: str) -> dict[str, Any]:
        result = dict(row)
        if "organization_id" in result:
            result["organization_id"] = organization_id
        return result

    @staticmethod
    def _rows(
        conn: Any, query: str, params: tuple[Any, ...], organization_id: str
    ) -> list[dict[str, Any]]:
        rows = conn.execute(query, params).fetchall()
        for row in rows:
            row["organization_id"] = organization_id
        return rows

    @staticmethod
    def _exception(row: dict[str, Any], organization_id: str) -> ExceptionSummary:
        rules = row["rules_triggered"] if isinstance(row["rules_triggered"], list) else []
        return ExceptionSummary(
            id=str(row["source_exception_id"]),
            organization_id=organization_id,
            order_id=str(row["source_order_id"]),
            type=ExceptionType(str(row["exception_type"])),
            severity=Severity(str(row["severity"])),
            status=ExceptionStatus(str(row["status"])),
            financial_exposure=Decimal(int(row["financial_exposure_minor"])) / Decimal(100),
            currency=str(row["currency"]),
            detected_at=row["detected_at"],
            rules_triggered=[str(rule) for rule in rules],
        )
