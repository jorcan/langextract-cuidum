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

    # 2. Run extraction
    print(f"\n  🤖 Iniciando extracción con {config.llm_model}...")
    t0 = time.time()
    results = []
    errors = 0

    for i, call in enumerate(calls, 1):
        try:
            result = extract_single_call(call, config)
            if result:
                results.append(result)
                non_null = sum(1 for v in result.entities.model_dump().values() if v is not None)
                print(f"  ✅ [{i}/{len(calls)}] Call #{call['id']} — {non_null}/102 campos")
            else:
                errors += 1
                print(f"  ⚠️  [{i}/{len(calls)}] Call #{call['id']} — Sin resultado")
        except Exception as e:
            errors += 1
            print(f"  ❌ [{i}/{len(calls)}] Call #{call['id']} — Error: {e}")

    elapsed = time.time() - t0
    print(f"\n  📊 Extracción: {len(results)} OK, {errors} errores en {elapsed:.1f}s")
    print(f"     Promedio: {elapsed/max(len(calls),1):.2f}s/llamada")

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

    # 4. Save to PostgreSQL (n8n_odoo)
    print(f"\n  🗄️  Guardando en n8n_odoo.hermes_langextract_cuidum...")
    t0 = time.time()
    saved = 0
    pg_errors = 0

    for r in results:
        try:
            save_extraction_to_pg(
                call_id=r.call.call_id,
                partner_id=r.call.partner_id,
                extraction_data=r.entities.model_dump(),
                schema_version=r.schema_version,
                raw_text_preview=r.raw_text_preview,
                confidence=r.confidence,
            )
            saved += 1
        except Exception as e:
            logger.error("Error saving call %s to PG: %s", r.call.call_id, e)
            pg_errors += 1

    pg_elapsed = time.time() - t0
    print(f"     {saved} registros guardados, {pg_errors} errores ({pg_elapsed:.1f}s)")

    # 5. Summary
    print("\n" + "=" * 70)
    print("  📋 RESUMEN FASE 2")
    print("=" * 70)
    print(f"     Partners procesados: {len(results)}")
    print(f"     Tabla destino:       n8n_odoo.hermes_langextract_cuidum")
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
