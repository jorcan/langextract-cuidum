"""Database connection and query helpers for Odoo PostgreSQL."""

import json
import logging
import os
from pathlib import Path
from typing import Any
from dotenv import load_dotenv

import psycopg2
import psycopg2.extras

logger = logging.getLogger(__name__)

load_dotenv()

# Local fallback: load sample data when no DB available
SAMPLE_DATA_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "data" / "samples" / "raw_calls.json"
)

# ── Connection helpers ──────────────────────────────────────────────

def _get_cuidum_conn():
    """Get connection to Cuidum Odoo DB (read-only, source of transcriptions)."""
    dsn = os.environ.get("CUIDUM_DB_URL")
    if not dsn:
        raise ValueError("CUIDUM_DB_URL not set. Create a .env file.")
    return psycopg2.connect(dsn)


def _get_n8n_conn():
    """Get connection to n8n_odoo DB (read-write, destination for results)."""
    dsn = os.environ.get("N8N_DB_URL")
    if not dsn:
        raise ValueError("N8N_DB_URL not set. Create a .env file.")
    return psycopg2.connect(dsn)


# ── Fetch calls from Cuidum DB ──────────────────────────────────────

def fetch_calls_for_latest_partners(
    limit: int = 100,
    skip_empty: bool = True,
) -> list[dict[str, Any]]:
    """Fetch calls for the most recently created partners with transcriptions.

    Gets one call per partner, prioritizing the most recent partners
    who have at least one phonecall with a non-empty description.
    """
    conn = _get_cuidum_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    empty_filter = "AND cp.description IS NOT NULL AND cp.description != ''" if skip_empty else ""

    query = f"""
    WITH ranked_calls AS (
        SELECT cp.id, cp.name, cp.description, cp.partner_id,
               cp.clave, cp.subclave, cp.create_date, cp.duration, cp.state,
               ROW_NUMBER() OVER (PARTITION BY cp.partner_id ORDER BY cp.create_date DESC) AS rn
        FROM crm_phonecall cp
        WHERE cp.partner_id IS NOT NULL
          {empty_filter}
    )
    SELECT rc.id, rc.name, rc.description, rc.partner_id,
           rc.clave, rc.subclave, rc.create_date, rc.duration, rc.state
    FROM ranked_calls rc
    JOIN res_partner rp ON rp.id = rc.partner_id
    WHERE rc.rn = 1
    ORDER BY rp.create_date DESC
    LIMIT %s
    """
    cur.execute(query, (limit,))
    rows = [dict(r) for r in cur.fetchall()]
    cur.close()
    conn.close()
    logger.info("Fetched %d calls (latest partners) from Cuidum DB", len(rows))
    return rows


def fetch_calls_raw(limit: int = 100, skip_empty: bool = True) -> list[dict[str, Any]]:
    """Fetch most recent calls with transcriptions (no partner dedup)."""
    conn = _get_cuidum_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    empty_filter = "AND description IS NOT NULL AND description != ''" if skip_empty else ""
    query = f"""
    SELECT id, name, description, partner_id, clave, subclave,
           create_date, duration, state
    FROM crm_phonecall
    WHERE partner_id IS NOT NULL {empty_filter}
    ORDER BY create_date DESC
    LIMIT %s
    """
    cur.execute(query, (limit,))
    rows = [dict(r) for r in cur.fetchall()]
    cur.close()
    conn.close()
    logger.info("Fetched %d raw calls from Cuidum DB", len(rows))
    return rows


# ── Save results to n8n_odoo ───────────────────────────────────────

def save_extraction_to_pg(
    call_id: int,
    partner_id: int | None,
    extraction_data: dict[str, Any],
    schema_version: str = "2.0.0",
    raw_text_preview: str | None = None,
    confidence: float = 1.0,
) -> int:
    """Save a single extraction result to hermes_langextract_cuidum table.

    Uses INSERT ... ON CONFLICT to update if the call_id already exists.
    Returns the row id.
    """
    conn = _get_n8n_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO hermes_langextract_cuidum
            (call_id, partner_id, extraction_data, schema_version, raw_text_preview, confidence)
        VALUES (%s, %s, %s::jsonb, %s, %s, %s)
        ON CONFLICT (call_id)
        DO UPDATE SET
            extraction_data = EXCLUDED.extraction_data,
            schema_version = EXCLUDED.schema_version,
            raw_text_preview = EXCLUDED.raw_text_preview,
            confidence = EXCLUDED.confidence,
            extracted_at = NOW()
        RETURNING id
    """, (
        call_id,
        partner_id,
        json.dumps(extraction_data, ensure_ascii=False),
        schema_version,
        raw_text_preview[:500] if raw_text_preview else None,
        confidence,
    ))
    row_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()
    return row_id


def save_batch_to_pg(results: list[dict[str, Any]]) -> tuple[int, int]:
    """Save multiple extraction results. Returns (saved_count, error_count)."""
    saved = 0
    errors = 0
    for r in results:
        try:
            save_extraction_to_pg(
                call_id=r["call_id"],
                partner_id=r.get("partner_id"),
                extraction_data=r.get("entities", r),
                schema_version=r.get("schema_version", "2.0.0"),
                raw_text_preview=r.get("raw_text_preview"),
                confidence=r.get("confidence", 1.0),
            )
            saved += 1
        except Exception as e:
            logger.error("Error saving call %s: %s", r.get("call_id"), e)
            errors += 1
    logger.info("Batch saved: %d OK, %d errors", saved, errors)
    return saved, errors


# ── Legacy sample data loader ───────────────────────────────────────

def load_sample_calls(path: str | Path | None = None) -> list[dict[str, Any]]:
    """Load call records from a local JSON file (sample data or cached)."""
    path = Path(path or SAMPLE_DATA_PATH)
    if not path.exists():
        logger.warning("Sample data file not found: %s", path)
        return []
    with open(path) as f:
        return json.load(f)


def format_call_for_extraction(call: dict[str, Any], max_chars: int = 3000) -> str:
    """Format a phonecall record into a text block for LLM extraction."""
    name = call.get("name") or "(sin resumen)"
    description = call.get("description") or "(sin transcripción)"

    if len(description) > max_chars:
        description = description[:max_chars] + "..."

    lines = [
        f"=== LLAMADA #{call.get('id')} ===",
        f"Resumen: {name.strip()}",
        f"Fecha: {call.get('create_date', 'desconocida')}",
        f"Clave/Subclave: {call.get('clave')}/{call.get('subclave')}",
        "",
        "Transcripción:",
        description.strip(),
    ]
    return "\n".join(lines)


def get_calls_needing_extraction(
    calls: list[dict[str, Any]],
    already_done: set[int] | None = None,
    skip_empty: bool = True,
) -> list[dict[str, Any]]:
    """Filter calls that need processing."""
    already_done = already_done or set()
    result = []
    for c in calls:
        cid = c.get("id")
        if cid in already_done:
            continue
        desc = c.get("description") or ""
        if skip_empty and not desc.strip():
            continue
        result.append(c)
    return result
