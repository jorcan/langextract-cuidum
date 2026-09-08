"""CLI del extractor genérico.

Uso:
  python scripts/extract_cli.py --schema partner-fill --mode schema
  python scripts/extract_cli.py --schema cuidum-102 --mode dry-run --limit 5
  python scripts/extract_cli.py --schema partner-fill --mode extract --limit 1 \
      --provider-a hermes-api --provider-b openrouter-gemma4 --examples data/examples/cuidum-102.json

Schemas: 'partner-fill' | 'cuidum-102' | /ruta/a/schema.json
"""
import argparse
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("extract_cli")


def resolve_schema(ref: str) -> tuple[list, dict]:
    """Resuelve 'partner-fill' | 'cuidum-102' | ruta JSON -> (fields, targets)."""
    from adapters.cuidum import partner_fill
    if ref == "partner-fill":
        return partner_fill.load_partner_fill_schema()
    if ref == "cuidum-102":
        from adapters.cuidum.schema_102 import FIELDS_102
        return FIELDS_102, {}
    p = Path(ref)
    if p.exists():
        return partner_fill.load_schema_file(p)
    raise ValueError(f"Schema desconocido: {ref}")


def _load_examples(path: str | None) -> list[dict]:
    if not path:
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Extractor de entidades genérico (core)")
    ap.add_argument("--schema", default="partner-fill", help="partner-fill | cuidum-102 | ruta JSON")
    ap.add_argument("--mode", choices=["schema", "dry-run", "extract"], default="schema")
    ap.add_argument("--limit", type=int, default=10)
    ap.add_argument("--provider-a", default="hermes-api")
    ap.add_argument("--provider-b", default=None, help="openrouter-gemma4 para consenso dual")
    ap.add_argument("--examples", default=None, help="ruta a JSON de ejemplos few-shot")
    ap.add_argument("--existing", default=None, help="ruta a JSON con datos ya conocidos")
    ap.add_argument("--out", default=None, help="fichero JSONL de salida (mode extract)")
    args = ap.parse_args(argv)

    fields, targets = resolve_schema(args.schema)
    examples = _load_examples(args.examples or _default_examples(args.schema))

    if args.mode == "schema":
        print(f"Schema '{args.schema}': {len(fields)} campos")
        for f in fields:
            extra = f" [{', '.join(f.allowed)}]" if f.allowed else ""
            val = f" (validador: {f.validator})" if f.validator else ""
            col = f" -> {targets.get(f.name)}" if targets.get(f.name) else ""
            print(f"  - {f.name} ({f.type}){extra}{val}{col}")
        return 0

    if args.mode == "dry-run":
        return _dry_run(args, fields, targets)

    return _extract(args, fields, targets, examples)


def _default_examples(schema: str) -> str | None:
    if schema == "cuidum-102":
        p = Path(__file__).resolve().parent.parent / "data" / "examples" / "cuidum-102.json"
        return str(p) if p.exists() else None
    return None


def _load_candidates(limit: int, fields=None, targets=None):
    from adapters.cuidum import partner_fill
    from adapters.cuidum.phonecalls import _get_cuidum_conn
    if fields is None or targets is None:
        fields, targets = partner_fill.load_partner_fill_schema()
    conn = _get_cuidum_conn()
    try:
        return partner_fill.fetch_candidates(conn, fields, targets, limit=limit)
    finally:
        conn.close()


def _existing_data(path: str | None) -> dict:
    if not path:
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _dry_run(args, fields, targets) -> int:
    logger.info("dry-run: contando candidatos (sin llamadas LLM)...")
    candidates = _load_candidates(args.limit, fields, targets)
    cols = [t for t in targets.values() if t]
    print(f"Candidatos (duration>=30s, {', '.join(cols)} vacíos): {len(candidates)}")
    for c in candidates[:5]:
        print(f"  call #{c['call_id']} partner {c['partner_id']} dur={c['duration']}s "
              f"desc={len(c['description'] or '')} chars")
    return 0


def _extract(args, fields, targets, examples) -> int:
    from core.extractor import extract_entities
    from core.providers import make_provider
    candidates = _load_candidates(args.limit, fields, targets)
    existing = _existing_data(args.existing)

    provider_a = make_provider(args.provider_a)
    provider_b = make_provider(args.provider_b) if args.provider_b else None

    out_path = args.out or (Path(__file__).resolve().parent.parent /
                            "data" / "output" / "extract_cli.jsonl")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    import time
    t0 = time.time()
    saved = 0
    with open(out_path, "w", encoding="utf-8") as f:
        for i, cand in enumerate(candidates, 1):
            text = cand.get("description") or ""
            doc = extract_entities(text, fields, examples=examples,
                                   existing_data=existing, provider=provider_a)
            rec = {"call_id": cand["call_id"], "partner_id": cand.get("partner_id"),
                   "doc": doc.format()}
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            saved += 1
            ok = len(doc.ok_fields)
            print(f"  [{i}/{len(candidates)}] call #{cand['call_id']} — {ok} campos ok")
    print(f"OK: {saved} extracciones en {time.time()-t0:.1f}s -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())