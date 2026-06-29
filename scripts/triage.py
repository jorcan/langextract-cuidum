#!/usr/bin/env python3
"""
Triage Pipeline A — Extracción rápida para alertas en tiempo real.
9 entidades clave. Coste ~$0.001/llamada.

Usage:
    cd ~/repos/langextract-cuidum && source .venv/bin/activate
    python3 scripts/triage.py --count 100              # Batch de 100
    python3 scripts/triage.py --call-id 6564235        # Una llamada específica
    python3 scripts/triage.py --watch                  # Modo escucha (cada N minutos)
"""

import argparse
import json
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import Config
from src.db import fetch_calls_for_latest_partners, save_extraction_to_pg
from src.extractors_v2 import extract_triage, extract_triage_batch

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("triage")


def main():
    parser = argparse.ArgumentParser(description="Pipeline A — Triage en tiempo real")
    parser.add_argument("--count", "-n", type=int, default=100)
    parser.add_argument("--call-id", type=int, help="Procesar una llamada específica")
    parser.add_argument("--workers", "-w", type=int, default=20)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    config = Config()

    print("=" * 60)
    print("  🚀 PIPELINE A — TRIAGE (9 entidades)")
    print("=" * 60)
    print(f"  Workers: {args.workers} | Coste estimado: ~$0.001/llamada")

    if args.call_id:
        # Fetch single call
        calls = fetch_calls_for_latest_partners(limit=1)
        calls = [c for c in calls if c["id"] == args.call_id]
        if not calls:
            print(f"  ❌ Call #{args.call_id} no encontrada")
            return 1
        print(f"\n  📞 Procesando llamada #{args.call_id}...")
        result = extract_triage(calls[0], config)
        if result:
            print(f"\n  ✅ Resultado:")
            for k, v in result.entities.model_dump().items():
                print(f"     {k}: {v}")
            if not args.dry_run:
                row_id = save_extraction_to_pg(
                    call_id=result.call.call_id,
                    partner_id=result.call.partner_id,
                    extraction_data=result.entities.model_dump(),
                    schema_version=result.schema_version,
                )
                print(f"\n  💾 Guardado en PostgreSQL (id={row_id})")
        else:
            print(f"  ❌ Error extrayendo llamada #{args.call_id}")
        return 0

    # Batch mode
    print(f"\n  📞 Cargando {args.count} partners...")
    t0 = time.time()
    calls = fetch_calls_for_latest_partners(limit=args.count)
    print(f"     {len(calls)} llamadas ({time.time()-t0:.1f}s)")

    if args.dry_run:
        print(f"\n  ✅ Dry-run. Listo para extraer {len(calls)} llamadas.")
        return 0

    print(f"\n  🤖 Extrayendo con {args.workers} workers...")
    t0 = time.time()
    results = extract_triage_batch(calls, config, max_workers=args.workers)
    elapsed = time.time() - t0

    print(f"\n  📊 Resultados:")
    print(f"     Procesadas: {len(calls)}")
    print(f"     Extraídas:  {len(results)}")
    print(f"     Tiempo:     {elapsed:.1f}s ({elapsed/max(len(results),1):.2f}s/llamada)")

    # Save to PG
    saved = 0
    for r in results:
        try:
            save_extraction_to_pg(
                call_id=r.call.call_id,
                partner_id=r.call.partner_id,
                extraction_data=r.entities.model_dump(),
                schema_version=r.schema_version,
            )
            saved += 1
        except Exception as e:
            logger.error("Error guardando call %s: %s", r.call.call_id, e)

    print(f"     Guardados en PG: {saved}")

    # Summary stats
    if results:
        bajas = sum(1 for r in results if r.entities.menciona_baja)
        quejas = sum(1 for r in results if r.entities.menciona_queja)
        upsell = sum(1 for r in results if r.entities.upsell_opportunity)
        churn_alto = sum(1 for r in results if r.entities.churn_risk_score > 0.5)
        urgentes = sum(1 for r in results if r.entities.urgencia == "urgente")
        positivos = sum(1 for r in results if r.entities.sentimiento_general in ("positivo", "agradecido"))
        
        print(f"\n  📈 Resumen de señales:")
        print(f"     Urgentes:  {urgentes} ({urgentes/len(results)*100:.0f}%)")
        print(f"     Mencionan baja:   {bajas} ({bajas/len(results)*100:.0f}%)")
        print(f"     Mencionan queja:  {quejas} ({quejas/len(results)*100:.0f}%)")
        print(f"     Upsell:           {upsell} ({upsell/len(results)*100:.0f}%)")
        print(f"     Churn alto:       {churn_alto} ({churn_alto/len(results)*100:.0f}%)")
        print(f"     Sentimiento positivo: {positivos} ({positivos/len(results)*100:.0f}%)")

        # Alertas para gestores
        print(f"\n  🚨 Alertas generadas:")
        for r in results:
            if r.entities.churn_risk_score > 0.5:
                print(f"     🔴 CHURN ALTO: Partner #{r.call.partner_id} (risk={r.entities.churn_risk_score:.2f})")
            if r.entities.menciona_baja:
                print(f"     🔴 BAJA: Partner #{r.call.partner_id}")
            if r.entities.menciona_competidores:
                print(f"     🟡 COMPETIDOR: Partner #{r.call.partner_id}")

    print(f"\n  ✅ Triage completado.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
