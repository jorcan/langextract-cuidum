#!/usr/bin/env python3
"""PILOTO 1-en-1 (decisión de Jorge): extracción dual A/B + revisión humana
campo a campo. NUNCA avanza sin aprobación. Requiere TTY (guarda anti-hang).

Uso:
  python scripts/pilot_one_by_one.py                     # siguiente candidato
  python scripts/pilot_one_by_one.py --call-id 123       # reprocesar llamada
  python scripts/pilot_one_by_one.py --provider-b hermes-api   # B degradado
"""
import argparse
import json
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("pilot")


def _load_pair():
    from adapters.cuidum.partner_fill import load_partner_fill_schema
    return load_partner_fill_schema()


def _fetch_candidate(conn_cuidum, fields, targets, exclude: set[int], call_id=None):
    from adapters.cuidum.partner_fill import fetch_candidates
    if call_id is not None:
        # fetch por id directamente (para reprocesar una llamada concreta)
        cur = conn_cuidum.cursor()
        cur.execute(
            "SELECT id AS call_id, partner_id, description, duration, create_date, name "
            "FROM crm_phonecall WHERE id = %s", (call_id,))
        row = cur.fetchone()
        cur.close()
        return (dict(zip(["call_id", "partner_id", "description", "duration",
                          "create_date", "name"], row)) if row else None)
    rows = fetch_candidates(conn_cuidum, fields, targets, limit=50)
    return next((r for r in rows if r["call_id"] not in exclude), None)


def _ask(prompt_txt: str, choices: str) -> str:
    while True:
        ans = input(f"{prompt_txt} [{choices}] > ").strip().lower()
        if ans in choices:
            return ans
        if ans == "":
            return choices[0]
        print("  opción no válida")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--call-id", type=int, default=None)
    ap.add_argument("--provider-a", default="hermes-api")
    ap.add_argument("--provider-b", default="openrouter-gemma4",
                    help="B vacío = modo single-model (críticos a revisión)")
    ap.add_argument("--examples", default=None)
    args = ap.parse_args(argv)

    if not sys.stdin.isatty():
        print("PILOTO requiere terminal interactiva (TTY). Aborta.", file=sys.stderr)
        return 2

    from adapters.cuidum.partner_fill import load_schema_file
    from adapters.cuidum.phonecalls import _get_cuidum_conn, _get_n8n_conn
    from adapters.cuidum.review import save_review_result, next_pending_call
    from core.consensus import run_dual
    from core.providers import make_provider

    fields, targets = _load_pair()
    critical = [f.name for f in fields if f.validator or f.type == "bool"]

    conn_c = _get_cuidum_conn()
    conn_n = _get_n8n_conn()
    try:
        # 1. Siguiente candidato sin procesar
        done = {r["call_id"] for r in next_pending_call(conn_n, limit=500)}
        cand = _fetch_candidate(conn_c, fields, targets, done, args.call_id)
        if cand is None:
            print("No hay candidatos pendientes. Fin del piloto por hoy.")
            return 0

        text = cand.get("description") or ""
        print("\n" + "=" * 72)
        print(f"LLAMADA #{cand['call_id']} | partner {cand['partner_id']} | "
              f"dur {cand.get('duration')}s")
        print("=" * 72)
        print(text[:2500] + ("..." if len(text) > 2500 else ""))

        # 2. Extracción dual
        provider_a = make_provider(args.provider_a)
        provider_b = make_provider(args.provider_b) if args.provider_b else None
        examples = json.load(open(args.examples, encoding="utf-8")) if args.examples else None
        verdict, doc_a, doc_b = run_dual(
            text, fields, provider_a=provider_a, provider_b=provider_b,
            critical_fields=critical, examples=examples,
        )
        print(f"\n>>> CONSENSO: {verdict}")

        # 3. Ensamblar payload + evidencia
        extracted, evidence, validators = {}, {}, {}
        for e in doc_a.extractions:
            if e.status == "ok":
                extracted[e.field_name] = e.value
            evidence[e.field_name] = {
                "value": e.value, "quote": e.verbatim_quote,
                "start": e.start_char, "end": e.end_char, "status": e.status,
            }
            validators[e.field_name] = e.validated_by

        save_review_result(conn_n, cand["call_id"], cand["partner_id"],
                           cand.get("duration"), str(cand.get("create_date")),
                           doc_a.missing_fields, extracted, evidence, verdict,
                           validators)

        # 4. Revisión humana campo a campo
        decisions = {}
        for e in doc_a.extractions:
            if e.status == "not_found":
                continue
            print("\n" + "-" * 60)
            print(f"  CAMPO: {e.field_name}  [estado: {e.status}]")
            if e.value:
                print(f"  VALOR: {e.value}")
            if e.verbatim_quote:
                print(f"  CITA : {e.verbatim_quote!r}  (offsets {e.start_char}:{e.end_char})")
            if e.status != "ok":
                print("  ⚠️  No anclado/validado automáticamente")
            d = _ask("  ¿aprobar (a), corregir (c), descartar (d)?", "acd")
            decisions[e.field_name] = d
            if d == "c":
                decisions[e.field_name + "_fix"] = input("  Valor corregido: ").strip()

        # 5. Cierre de la revisión
        bad = [f for f, d in decisions.items() if f.endswith("_fix") or d == "d"]
        print("\n" + "=" * 60)
        if bad:
            print(f"Rechazado/descartado: {bad}")
        app_name = "pilot-1-1"
        cur = conn_n.cursor()
        cur.execute("""
            UPDATE hermes_partner_fill
            SET review_status = %s, reviewed_by = %s, reviewed_at = NOW()
            WHERE call_id = %s
        """, ("rejected" if bad else "approved", app_name, cand["call_id"]))
        conn_n.commit()
        cur.close()
        # Persistir decisiones por campo en evidence
        cur = conn_n.cursor()
        cur.execute("SELECT evidence::text FROM hermes_partner_fill WHERE call_id = %s",
                    (cand["call_id"],))
        ev = json.loads(cur.fetchone()[0] or "{}")
        for f, d in decisions.items():
            if f.endswith("_fix"):
                ev[f[:-4]] = {**ev.get(f[:-4], {}), "review": "corrected", "fix": d}
            else:
                ev[f] = {**ev.get(f, {}), "review": d}
        cur.execute("UPDATE hermes_partner_fill SET evidence = %s::jsonb WHERE call_id = %s",
                    (json.dumps(ev, ensure_ascii=False), cand["call_id"]))
        conn_n.commit()
        cur.close()
        print(f"Guardado. Próximo candidato con: python scripts/pilot_one_by_one.py")
        return 0
    finally:
        conn_c.close()
        conn_n.close()


if __name__ == "__main__":
    raise SystemExit(main())