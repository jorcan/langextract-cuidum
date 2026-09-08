"""Persistencia HITL del caso partner-fill (tabla hermes_partner_fill en n8n_odoo)."""
import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


def save_review_result(
    conn,
    call_id: int,
    partner_id: int,
    duration_seconds: float | None,
    create_date: str | None,
    missing_fields: list[str],
    extracted_data: dict[str, Any],
    evidence: dict[str, Any],
    consensus_status: str,
    validators_passed: dict[str, list[str]],
    schema_version: str = "partner_fill_0.2.0",
) -> int:
    """INSERT ... ON CONFLICT (call_id) DO UPDATE — idempotente por llamada."""
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO hermes_partner_fill
            (call_id, partner_id, duration_seconds, create_date, schema_version,
             missing_fields, extracted_data, evidence, consensus_status, validators_passed)
        VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb, %s, %s::jsonb)
        ON CONFLICT (call_id)
        DO UPDATE SET
            extracted_data = EXCLUDED.extracted_data,
            evidence = EXCLUDED.evidence,
            consensus_status = EXCLUDED.consensus_status,
            validators_passed = EXCLUDED.validators_passed,
            missing_fields = EXCLUDED.missing_fields,
            created_at = NOW()
        RETURNING id
    """, (
        call_id, partner_id, duration_seconds, create_date, schema_version,
        json.dumps(missing_fields, ensure_ascii=False),
        json.dumps(extracted_data, ensure_ascii=False),
        json.dumps(evidence, ensure_ascii=False),
        consensus_status,
        json.dumps(validators_passed, ensure_ascii=False),
    ))
    row_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    return row_id


def next_pending_call(conn, limit: int = 1) -> list[dict[str, Any]]:
    """Siguientes llamadas SIN procesar (no tienen fila aun) o pendientes de revisión."""
    cur = conn.cursor()
    cur.execute("""
        SELECT p.id, p.partner_id, p.call_id
        FROM hermes_partner_fill p
        WHERE p.review_status = 'pending'
        ORDER BY p.created_at ASC
        LIMIT %s
    """, (limit,))
    rows = [dict(zip(["row_id", "partner_id", "call_id"], r)) for r in cur.fetchall()]
    cur.close()
    return rows