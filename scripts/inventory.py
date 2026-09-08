#!/usr/bin/env python3
"""Inventario de campos 'cuidador/contacto' en res_partner (Cuidum prod).

End-to-end en un solo run: DSN -> information_schema -> tasas de vacíos
-> data/output/inventory_<ts>.md (para congelar data/schemas/partner_fill.json).
"""
import datetime
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path.home() / "repos/langextract-cuidum"
sys.path.insert(0, str(ROOT))


def get_dsn() -> str:
    env = Path.home() / "postgres-mcp-server/.env"
    for line in env.read_text().splitlines():
        if line.startswith("DB_CUIDUM="):
            return line.split("=", 1)[1].strip().split("  #")[0].strip()
    raise SystemExit("DB_CUIDUM no encontrada en ~/postgres-mcp-server/.env")


def psql(sql: str) -> str:
    return subprocess.run(
        ["psql", get_dsn(), "-A", "-t", "-F", "\x1f", "-c", sql],
        capture_output=True, text=True, check=True,
    ).stdout


def main():
    # 1. Columnas candidatas (bloque persona cuidador + contacto + familia)
    cols_sql = """
    SELECT a.attname AS column_name, t.typname AS data_type, d.description AS comment
    FROM pg_catalog.pg_attribute a
    JOIN pg_catalog.pg_class c ON c.oid = a.attrelid AND c.relname='res_partner' AND c.relkind='r'
    JOIN pg_catalog.pg_type t ON t.oid = a.atttypid
    LEFT JOIN pg_catalog.pg_description d ON d.objoid = a.attrelid AND d.objsubid = a.attnum
    WHERE (a.attname ILIKE '%cuidador%' OR a.attname ILIKE '%cuidad%'
           OR a.attname ILIKE '%persona_cuidar%' OR a.attname ILIKE '%contacto%'
           OR a.attname ILIKE 'phone%' OR a.attname ILIKE 'mobile%'
           OR (a.attname LIKE 'x\\_%' AND (
               a.attname ILIKE '%nombre%' OR a.attname ILIKE '%apellido%'
               OR a.attname ILIKE '%dni%' OR a.attname ILIKE '%parentesco%'
               OR a.attname ILIKE '%conviv%' OR a.attname ILIKE '%cuidad%'
               OR a.attname ILIKE '%tel%' OR a.attname ILIKE '%familia%')))
    ORDER BY a.attname;
    """
    cols = []
    for line in psql(cols_sql).splitlines():
        if not line.strip():
            continue
        parts = line.split("\x1f")
        cols.append((parts[0], parts[1], parts[2] if len(parts) > 2 else ""))

    if not cols:
        print("No se encontraron columnas candidatas.")
        return

    # 2. Partners con >=1 llamada transcrita (denominador de negocio)
    base_sql = """
    SELECT count(DISTINCT cp.partner_id)
    FROM crm_phonecall cp
    WHERE cp.partner_id IS NOT NULL
      AND cp.description IS NOT NULL AND cp.description != ''
      AND length(cp.description) > 50;
    """
    n_partners = psql(base_sql).strip()
    try:
        n_partners = int(n_partners or 0)
    except ValueError:
        n_partners = 0

    # 3. Vacíos por columna (solo entre partners con llamada transcrita)
    rows = []
    for col, dtype, comment in cols:
        # Para texto, '' cuenta como vacío; para otros tipos solo NULL
        if dtype in ("character varying", "text", "character"):
            count_expr = f"count(nullif(rp.{col},''))"
        else:
            count_expr = f"count(rp.{col})"
        sql = f"""
        SELECT count(*) AS total,
               {count_expr} AS con_valor
        FROM res_partner rp
        WHERE rp.id IN (
            SELECT DISTINCT cp.partner_id
            FROM crm_phonecall cp
            WHERE cp.partner_id IS NOT NULL
              AND cp.description IS NOT NULL AND cp.description != ''
              AND length(cp.description) > 50);
        """
        try:
            out = psql(sql).strip()
            parts = out.split("\x1f")
            total = int(parts[0]); con_valor = int(parts[1])
            vacios = total - con_valor
            pct = (vacios / total * 100.0) if total else 0.0
            rows.append((col, dtype, comment, total, con_valor, vacios, pct))
        except subprocess.CalledProcessError as e:
            rows.append((col, dtype, comment, -1, -1, -1, -1.0))
            print(f"  (error en {col}: {e.stderr.strip()[:80]})", file=sys.stderr)

    # 4. Reporte
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = ROOT / "data" / "output"
    out_dir.mkdir(parents=True, exist_ok=True)
    md = [
        f"# Inventario campos res_partner (cuidador/contacto/familia) — {ts}",
        "",
        f"Partners con ≥1 llamada transcrita (denominador): **{n_partners}**",
        "",
        "| columna | tipo | descripción | partners | con valor | vacíos | % vacíos |",
        "|---|---|---|---|---|---|---|",
    ]
    for col, dtype, comment, total, con, vac, pct in sorted(rows, key=lambda r: -r[6]):
        md.append(f"| {col} | {dtype} | {comment or ''} | {total} | {con} | {vac} | {pct:.1f}% |")
    md += ["", "_Generado automáticamente por scripts/inventory.py_"]

    path = out_dir / f"inventory_{ts}.md"
    path.write_text("\n".join(md), encoding="utf-8")
    print(f"Inventario: {len(rows)} columnas -> {path}")
    print(f"{'col':<30} {'tipo':<14} {'vacíos %':>8}  descripción")
    for col, dtype, comment, total, con, vac, pct in sorted(rows, key=lambda r: -r[6]):
        print(f"{col:<30} {dtype:<14} {pct:>7.1f}%  {comment or ''}")


if __name__ == "__main__":
    main()