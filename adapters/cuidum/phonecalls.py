"""Phonecall data access for Cuidum Odoo — the ONLY place that knows
crm_phonecall / res_partner / n8n_odoo. Migrated from src/db (legacy).
"""
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

SAMPLE_DATA_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "data" / "samples" / "raw_calls.json"
)


# ── Connection helpers ──────────────────────────────────────────────

def _get_cuidum_conn():
    dsn = os.environ.get("CUIDUM_DB_URL")
    if not dsn:
        raise ValueError("CUIDUM_DB_URL not set. Create a .env file.")
    return psycopg2.connect(dsn)


def _get_n8n_conn():
    dsn = os.environ.get("N8N_DB_URL")
    if not dsn:
        raise ValueError("N8N_DB_URL not set. Create a .env file.")
    return psycopg2.connect(dsn)


# ── Fetch calls from Cuidum DB ──────────────────────────────────────

def fetch_calls_for_latest_partners(
    limit: int = 100,
    skip_empty: bool = True,
) -> list[dict[str, Any]]:
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
    cur.close(); conn.close()
    logger.info("Fetched %d calls (latest partners) from Cuidum DB", len(rows))
    return rows


def fetch_calls_raw(limit: int = 100, skip_empty: bool = True) -> list[dict[str, Any]]:
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
    cur.close(); conn.close()
    logger.info("Fetched %d raw calls from Cuidum DB", len(rows))
    return rows


# ── Fetch by id + partner context (Odoo selection real) ─────────────

def fetch_call_by_id(call_id: int) -> dict[str, Any] | None:
    """Una llamada concreta de crm_phonecall (la transcripción vive en description).

    Incluye clave/subclave resueltas a su nombre legible (m2o a
    crm_phonecall_clave / crm_phonecall_subclave).
    """
    conn = _get_cuidum_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT cp.id, cp.name, cp.description, cp.partner_id,
               cp.clave, cp.subclave, cp.duration, cp.state, cp.create_date,
               ck.nombre_clave, ck.codigo_clave,
               sk.nombre_subclave, sk.codigo_subclave
        FROM crm_phonecall cp
        LEFT JOIN crm_phonecall_clave ck ON ck.id = cp.clave
        LEFT JOIN crm_phonecall_subclave sk ON sk.id = cp.subclave
        WHERE cp.id = %s
    """, (call_id,))
    row = cur.fetchone()
    cur.close(); conn.close()
    if not row:
        return None
    return dict(row)


def fetch_partner_selection_context(partner_id: int) -> dict[str, Any]:
    """Contexto estructurado del partner para guiar la extracción.

    Devuelve:
      - partner: fila básica (name, email, mobile, phone, x_partner_type…)
      - selections: {campo: {"valor_actual": code|None, "label_actual": str|None,
                             "opciones": [{"value": code, "label": label}, …]}}
        SOLO para campos ttype='selection' de res.partner (los x_* de Cuidum).
      - vocabulario_odoo: lista plana "code — label" para el prompt
    """
    conn = _get_cuidum_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("""
        SELECT id, name, email, mobile, phone, x_partner_type, x_sexo,
               x_nivel_formativo, x_donde_nos_conocio, x_valoracion_cuidadora,
               x_tipo_comunicacion, x_cuidador_estrella, x_visado,
               x_encuesta_superada, x_afiliado_descripcion, x_relacion_familiar
        FROM res_partner WHERE id = %s
    """, (partner_id,))
    partner = cur.fetchone()
    if not partner:
        cur.close(); conn.close()
        return {"partner": None, "selections": {}, "vocabulario_odoo": []}

    # Campos selection del modelo res.partner
    cur.execute("""
        SELECT f.id, f.name
        FROM ir_model_fields f
        WHERE f.model = 'res.partner' AND f.ttype = 'selection'
        ORDER BY f.name
    """)
    sel_fields = cur.fetchall()

    selections: dict[str, dict] = {}
    vocabulario: list[str] = []
    for sf in sel_fields:
        fname = sf["name"]
        cur.execute("""
            SELECT s.value, s.name
            FROM ir_model_fields_selection s
            WHERE s.field_id = %s
            ORDER BY s.sequence
        """, (sf["id"],))
        opts = []
        for o in cur.fetchall():
            label = o["name"].get("es_ES") or o["name"].get("en_US") or o["value"]
            opts.append({"value": o["value"], "label": label})
        if not opts:
            continue
        valor_actual = partner.get(fname)
        label_actual = next((o["label"] for o in opts if o["value"] == valor_actual), None)
        selections[fname] = {
            "valor_actual": valor_actual,
            "label_actual": label_actual,
            "opciones": opts,
        }
        vocabulario.append(
                    fname + ": " + ", ".join(
                        f"{o['value']} ({o['label']})" for o in opts
                    )
                )

    cur.close(); conn.close()
    return {
        "partner": dict(partner),
        "selections": selections,
        "vocabulario_odoo": vocabulario,
    }


# ── Save results to n8n_odoo ────────────────────────────────────────

def save_extraction_to_pg(
    call_id: int,
    partner_id: int | None,
    extraction_data: dict[str, Any],
    schema_version: str = "2.0.0",
    raw_text_preview: str | None = None,
    confidence: float = 1.0,
) -> int:
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
    """, (call_id, partner_id, json.dumps(extraction_data, ensure_ascii=False),
          schema_version, raw_text_preview[:500] if raw_text_preview else None, confidence))
    row_id = cur.fetchone()[0]
    conn.commit(); cur.close(); conn.close()
    return row_id


def save_batch_to_pg(results: list[dict[str, Any]]) -> tuple[int, int]:
    saved = errors = 0
    for r in results:
        try:
            save_extraction_to_pg(
                call_id=r["call_id"], partner_id=r.get("partner_id"),
                extraction_data=r.get("entities", r),
                schema_version=r.get("schema_version", "2.0.0"),
                raw_text_preview=r.get("raw_text_preview"), confidence=r.get("confidence", 1.0),
            )
            saved += 1
        except Exception as e:
            logger.error("Error saving call %s: %s", r.get("call_id"), e)
            errors += 1
    logger.info("Batch saved: %d OK, %d errors", saved, errors)
    return saved, errors


# ── Legacy sample data loader ───────────────────────────────────────

def load_sample_calls(path: str | Path | None = None) -> list[dict[str, Any]]:
    path = Path(path or SAMPLE_DATA_PATH)
    if not path.exists():
        logger.warning("Sample data file not found: %s", path)
        return []
    with open(path) as f:
        return json.load(f)


def format_call_for_extraction(call: dict[str, Any], max_chars: int = 3000) -> str:
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