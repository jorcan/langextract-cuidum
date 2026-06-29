#!/usr/bin/env python3
"""
Fase 2: Batch extraction for 100 most recent partners.
Fetches calls from Cuidum DB → runs LLM extraction → saves to n8n_odoo.

Usage:
    cd ~/repos/langextract-cuidum && source .venv/bin/activate
    python3 scripts/batch_extract.py --limit 100
"""

import argparse
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import Config
from src.db import (
    fetch_calls_for_latest_partners,
    format_call_for_extraction,
    save_extraction_to_pg,
)
from src.extractors import extract_single_call, results_to_jsonl
from src.models import ExtractionResult

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("batch_extract")


def main():
    parser = argparse.ArgumentParser(description="Fase 2: Batch extraction → PostgreSQL")
    parser.add_argument("--limit", "-n", type=int, default=100, help="Number of partners (default: 100)")
    parser.add_argument("--config", "-c", default="config.yaml", help="Config file")
    parser.add_argument("--dry-run", action="store_true", help="Fetch only, don't extract")
    args = parser.parse_args()

    config = Config(args.config)

    print("=" * 70)
    print(f"  🔬 FASE 2 — EXTRACCIÓN BATCH ({args.limit} partners más recientes)")
    print("=" * 70)

    # 1. Fetch calls
    print(f"\n  📞 Conectando a Cuidum DB...")
    t0 = time.time()
    calls = fetch_calls_for_latest_partners(limit=args.limit)
    elapsed = time.time() - t0
    print(f"     {len(calls)} llamadas cargadas ({elapsed:.1f}s)")

    if not calls:
        print("  ❌ No se encontraron llamadas.")
        return 1

    # Show sample
    c = calls[0]
    desc_preview = (c.get("description") or "")[:120]
    print(f"     Primera: Call #{c['id']}, Partner #{c['partner_id']}, fecha {c.get('create_date')}")
    print(f"     Preview: {desc_preview}...")

    if args.dry_run:
        print("\n  ✅ Dry-run completado. Extracción no ejecutada.")
        return 0

    # 2. Run extraction (parallel with 20 workers) + save to DB on the fly
    print(f"\n  🤖 Iniciando extracción con {config.llm_model} (20 workers paralelos)...")
    t0 = time.time()
    results = [None] * len(calls)
    errors = 0
    pg_saved = 0
    pg_errors = 0

    from concurrent.futures import ThreadPoolExecutor, as_completed

    def process_one(i, call):
        try:
            result = extract_single_call(call, config)
            if result:
                save_extraction_to_pg(
                    call_id=result.call.call_id,
                    partner_id=result.call.partner_id,
                    extraction_data=result.entities.model_dump(),
                    schema_version=result.schema_version,
                    raw_text_preview=result.raw_text_preview,
                    confidence=result.confidence,
                )
                return i, result, None, True
            return i, None, "Sin resultado", False
        except Exception as e:
            return i, None, str(e), False

    with ThreadPoolExecutor(max_workers=20) as pool:
        futures = [pool.submit(process_one, i, call) for i, call in enumerate(calls)]
        for f in as_completed(futures):
            i, result, err, pg_ok = f.result()
            if result:
                results[i] = result
                non_null = sum(1 for v in result.entities.model_dump().values() if v is not None)
                print(f"  ✅ [{i+1}/{len(calls)}] Call #{calls[i]['id']} — {non_null}/102 campos")
                if pg_ok:
                    pg_saved += 1
            else:
                errors += 1
                if "ValidationError" in (err or ""):
                    pg_errors += 1  # count schema errors
                print(f"  ❌ [{i+1}/{len(calls)}] Call #{calls[i]['id']} — {err or 'Sin resultado'}")

    # Filter out None results
    results = [r for r in results if r is not None]

    elapsed = time.time() - t0
    print(f"\n  📊 Extracción: {len(results)} OK, {errors} errores en {elapsed:.1f}s")
    print(f"     Promedio: {elapsed/max(len(calls),1):.2f}s/llamada")
    print(f"  🗄️  PG: {pg_saved} guardados, {pg_errors} errores de schema")

    if not results:
        print("  ❌ No hay resultados para guardar.")
        return 1

    # 3. Save to JSONL (local backup)
    output_dir = Path(__file__).resolve().parent.parent / "data" / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")

    jsonl_path = output_dir / f"batch_{args.limit}_{timestamp}.jsonl"
    results_to_jsonl(results, str(jsonl_path))
    print(f"\n  💾 Backup local: {jsonl_path}")

    # 4. Summary
    print("\n" + "=" * 70)
    print("  📋 RESUMEN FASE 2")
    print("=" * 70)
    print(f"     Partners procesados: {len(results)}")
    print(f"     Tabla destino:       n8n_odoo.hermes_langextract_cuidum")
    print(f"     Guardados en PG:     {pg_saved}")
    print(f"     Backup JSONL:        {jsonl_path}")

    # Show a few entity highlights
    if results:
        print("\n  Muestra de datos extraídos (primer resultado):")
        entities = results[0].entities.model_dump()
        highlights = {k: v for k, v in entities.items() if v is not None}
        for k, v in list(highlights.items())[:15]:
            val = str(v)[:80]
            print(f"     {k}: {val}")

    print(f"\n  ✅ Fase 2 completada.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
