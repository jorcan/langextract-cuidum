#!/usr/bin/env python3
"""Export CSV de revisiones pendientes/aprobadas de hermes_partner_fill.

Columnas: call_id, partner_id, campo, valor_propuesto, cita_literal,
start_char, end_char, consenso, validadores, motivo, estado_revision.

Uso:
  python scripts/export_review.py --status pending       # CSV de pendientes
  python scripts/export_review.py --status approved
  python scripts/export_review.py --all
"""
import argparse
import csv
import os
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--status", default="pending", help="pending|approved|rejected|all")
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)

    from dotenv import load_dotenv
    load_dotenv()
    import psycopg2

    conn = psycopg2.connect(os.environ["N8N_DB_URL"])
    cur = conn.cursor()

    status_filter = "" if args.status == "all" else "WHERE review_status = %s"
    params = () if args.status == "all" else (args.status,)
    cur.execute(f"""
        SELECT call_id, partner_id, extracted_data::text, evidence::text,
               consensus_status, validators_passed::text, review_status,
               duration_seconds, create_date
        FROM hermes_partner_fill
        {status_filter}
        ORDER BY created_at DESC
    """, params)
    rows = cur.fetchall()
    cur.close(); conn.close()

    import json
    out_path = args.out or str(ROOT / "data/output" /
                              f"review_{args.status}_{datetime.now():%Y%m%d_%H%M%S}.csv")
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["call_id", "partner_id", "campo", "valor_propuesto", "cita_literal",
                    "start_char", "end_char", "consenso", "validadores", "motivo",
                    "estado_revision"])
        for (call_id, partner_id, ext_json, ev_json, consensus,
             val_json, review_status, duration, created) in rows:
            extracted = json.loads(ext_json or "{}")
            evidence = json.loads(ev_json or "{}")
            validators = json.loads(val_json or "{}")
            for campo in sorted(set(extracted) | set(evidence)):
                valor = extracted.get(campo)
                ev = evidence.get(campo) or {}
                if ev.get("status") == "not_found" and valor is None:
                    continue  # no aporta nada a la revisión
                motivo = ""
                if ev.get("status") == "grounding_fail":
                    motivo = "sin cita literal verificable"
                elif ev.get("status") == "validator_fail":
                    motivo = "validador determinista rechaza"
                elif ev.get("review") == "corrected":
                    motivo = f"corregido manualmente: {ev.get('fix')}"
                w.writerow([call_id, partner_id, campo, valor,
                            (ev.get("quote") or ""), ev.get("start"),
                            ev.get("end"), consensus,
                            ",".join(validators.get(campo, []) or []),
                            motivo, review_status])

    print(f"Export {args.status}: {len(rows)} filas origen -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())