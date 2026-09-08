"""Caso de uso: rellenar campos maestros vacíos del partner (bloque cuidador)
desde crm_phonecall. Adapter específico; el core es agnóstico.
"""
import json
import logging
from pathlib import Path
from typing import Any, Optional

from core.schema import FieldSpec, build_dynamic_model

logger = logging.getLogger(__name__)

SCHEMA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "schemas"
PARTNER_FILL_JSON = SCHEMA_DIR / "partner_fill.json"


def load_schema_file(path: str | Path) -> list[FieldSpec]:
    """Carga un schema en JSON (formato: {fields: [...]}) y devuelve FieldSpecs."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict):
        data = data.get("fields", data)
    return [FieldSpec(**f) for f in data]


def load_partner_fill_schema() -> list[FieldSpec]:
    return load_schema_file(PARTNER_FILL_JSON)


def fetch_candidates_query(
    fields: list[FieldSpec],
    min_duration: float = 30.0,
    min_chars: int = 100,
) -> tuple[str, dict[str, Any]]:
    """SQL para partners con ≥1 campo objetivo vacío y ≥1 llamada transcrita
    (duration >= 30, descripción no vacía). Una llamada por partner (la más
    reciente). Devuelve (sql, params)."""
    missing_cond = " OR ".join(
        f"rp.{f.name} IS NULL OR rp.{f.name} = ''" for f in fields
    )
    cols = ", ".join(f"rp.{f.name}" for f in fields)
    sql = f"""
    WITH ranked AS (
        SELECT cp.id AS call_id, cp.partner_id, cp.description, cp.duration,
               cp.clave, cp.subclave, cp.create_date, cp.name, {cols},
               ROW_NUMBER() OVER (PARTITION BY cp.partner_id
                                  ORDER BY cp.create_date DESC) AS rn
        FROM crm_phonecall cp
        JOIN res_partner rp ON rp.id = cp.partner_id
        WHERE cp.partner_id IS NOT NULL
          AND cp.description IS NOT NULL
          AND length(cp.description) > %(min_chars)s
          AND cp.duration >= %(min_dur)s
    )
    SELECT * FROM ranked
    WHERE rn = 1 AND ({missing_cond})
    ORDER BY create_date DESC
    LIMIT %(limit)s
    """
    return sql, {"min_chars": min_chars, "min_dur": min_duration, "limit": 1}


def fetch_candidates(conn, fields: list[FieldSpec], limit: int = 200,
                     min_duration: float = 30.0, min_chars: int = 100) -> list[dict]:
    import psycopg2.extras
    sql, params = fetch_candidates_query(fields, min_duration, min_chars)
    params["limit"] = limit
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(sql, params)
    rows = [dict(r) for r in cur.fetchall()]
    cur.close()
    return rows