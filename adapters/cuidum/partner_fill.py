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


def load_schema_file(path: str | Path) -> tuple[list[FieldSpec], dict[str, str | None]]:
    """Carga un schema JSON. Devuelve (fields, targets).

    - `targets` mapea nombre lógico -> columna destino en res_partner
      (None = sin columna, solo evidencia). El schema puede venir sin
      sección targets (None para todos).
    """
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict):
        targets = data.get("targets") or {}
        data = data.get("fields", data)
    else:
        targets = {}
    fields = [FieldSpec(**f) for f in data]
    return fields, targets


def load_partner_fill_schema() -> tuple[list[FieldSpec], dict[str, str | None]]:
    return load_schema_file(PARTNER_FILL_JSON)


def target_columns(fields: list[FieldSpec], targets: dict[str, str | None]) -> list[str]:
    """Columnas reales de res_partner a comprobar para 'campo vacío'."""
    return [t for f in fields if (t := targets.get(f.name))]


def fetch_candidates_query(
    fields: list[FieldSpec],
    targets: dict[str, str | None] | None = None,
    min_duration: float = 30.0,
    min_chars: int = 100,
) -> tuple[str, dict[str, Any]]:
    """SQL para partners con ≥1 columna objetivo vacía y ≥1 llamada transcrita
    (duration >= 30, descripción no vacía). Una llamada por partner (la más
    reciente). Devuelve (sql, params)."""
    targets = targets or {}
    columns = target_columns(fields, targets)
    if not columns:
        raise ValueError("No hay columnas destino (targets) para el filtro de candidatos")
    missing_cond = " OR ".join(
        f"c.{c} IS NULL OR c.{c} = ''" for c in columns
    )
    alias_cols = ", ".join(
        f"rp.{c} AS {c}" for c in columns
    )
    sql = f"""
    WITH ranked AS (
        SELECT cp.id AS call_id, cp.partner_id, cp.description, cp.duration,
               cp.clave, cp.subclave, cp.create_date, cp.name, {alias_cols},
               ROW_NUMBER() OVER (PARTITION BY cp.partner_id
                                  ORDER BY cp.create_date DESC) AS rn
        FROM crm_phonecall cp
        JOIN res_partner rp ON rp.id = cp.partner_id
        WHERE cp.partner_id IS NOT NULL
          AND cp.description IS NOT NULL
          AND length(cp.description) > %(min_chars)s
          AND cp.duration >= %(min_dur)s
    )
    SELECT * FROM ranked AS c
    WHERE c.rn = 1 AND ({missing_cond})
    ORDER BY c.create_date DESC
    LIMIT %(limit)s
    """
    return sql, {"min_chars": min_chars, "min_dur": min_duration, "limit": 1}


def fetch_candidates(conn, fields: list[FieldSpec], targets: dict[str, str | None],
                     limit: int = 200, min_duration: float = 30.0,
                     min_chars: int = 100) -> list[dict]:
    import psycopg2.extras
    sql, params = fetch_candidates_query(fields, targets, min_duration, min_chars)
    params["limit"] = limit
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(sql, params)
    rows = [dict(r) for r in cur.fetchall()]
    cur.close()
    return rows