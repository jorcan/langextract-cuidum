#!/usr/bin/env python3
"""
LangExtract-Cuidum Pipeline
===========================
Extract structured entities from Odoo crm_phonecall transcriptions
using DeepSeek LLM, and store results as structured profiles.

Usage:
    python scripts/run_pipeline.py                         # Run with defaults
    python scripts/run_pipeline.py --mode validate          # Validate schema only
    python scripts/run_pipeline.py --mode extract --count 10  # Extract 10 calls
    python scripts/run_pipeline.py --mode batch --count 1000  # Full batch
    python scripts/run_pipeline.py --mode sample            # Use sample data
"""

import argparse
import json
import logging
import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import Config
from src.db import (
    get_calls_needing_extraction,
    load_sample_calls,
)
from src.extractors import (
    extract_batch,
    results_to_jsonl,
)
from src.models import (
    CallEntities,
    EXTRACTION_PROMPT,
    EXTRACTION_EXAMPLES,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("pipeline")


def cmd_validate(config: Config):
    """FASE 1: Validate the extraction schema with dry-run."""
    print("\n" + "=" * 70)
    print("  📋 FASE 1 — VALIDACIÓN DEL SCHEMA DE EXTRACCIÓN")
    print("=" * 70)

    print(f"\n  Schema version: {config.schema_version}")
    print(f"  Provider: {config.llm_provider}")
    print(f"  Model: {config.llm_model}")

    # Show schema fields
    print("\n  📊 Entidades a extraer:")
    for name, field in CallEntities.model_fields.items():
        desc = field.description or ""
        print(f"     • {name}: {desc[:80]}")

    # Show prompt structure
    print(f"\n  📝 Prompt: {len(EXTRACTION_PROMPT)} chars")
    print(f"  📚 Examples: {len(EXTRACTION_EXAMPLES)} few-shot pairs")

    # Load samples
    samples = load_sample_calls()
    print(f"\n  📞 Muestras disponibles: {len(samples)} llamadas")

    if samples:
        desc = samples[0].get("description", "")
        print(f"  📄 Ejemplo de transcripción ({len(desc)} chars):")
        print(f"     {desc[:150]}...")

    print("\n  ✅ Schema validado. Listo para extracción.\n")


def cmd_extract(config: Config, count: int, use_sample: bool = False):
    """FASE 2: Run the extraction pipeline."""
    print("\n" + "=" * 70)
    print("  🔬 PIPELINE DE EXTRACCIÓN")
    print("=" * 70)

    # Check API key
    if not config.deepseek_api_available:
        logger.error(
            "DeepSeek API key not found. Set %s environment variable.",
            config.deepseek_api_key_env,
        )
        print(f"\n  ❌ API key no encontrada. Exporta {config.deepseek_api_key_env}=tu_key")
        return

    # Load calls
    if use_sample:
        calls = load_sample_calls()
        source = "sample data"
    else:
        # Try loading sample as fallback for now (DB direct query via MCP)
        calls = load_sample_calls()
        source = "sample data (MCP direct query coming in Phase 2)"

    print(f"\n  📞 Cargadas {len(calls)} llamadas desde {source}")
    print(f"  🤖 Modelo: {config.llm_model} via {config.llm_provider}")
    print(f"  ⚡ Workers: {config.max_workers}")
    print(f"  📏 Max chars: {config.max_char_buffer}")

    # Limit count
    calls = calls[:count]
    print(f"  🎯 Procesando: {len(calls)} llamadas")

    # Run extraction
    t0 = time.time()
    results = extract_batch(calls, config)
    elapsed = time.time() - t0

    # Report
    print(f"\n" + "=" * 70)
    print(f"  📊 RESULTADOS")
    print("=" * 70)
    print(f"     Procesadas: {len(calls)}")
    print(f"     Extraídas:  {len(results)}")
    print(f"     Tiempo:     {elapsed:.1f}s")
    print(f"     Promedio:   {elapsed/max(len(calls),1):.2f}s/llamada")

    # Save results
    output_dir = Path(__file__).resolve().parent.parent / "data" / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")

    jsonl_path = output_dir / f"extractions_{timestamp}.jsonl"
    results_to_jsonl(results, str(jsonl_path))

    # Save human-readable summary
    summary_path = output_dir / f"summary_{timestamp}.md"
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write(f"# LangExtract-Cuidum — Summary\n\n")
        f.write(f"**Date:** {time.strftime('%Y-%m-%d %H:%M')}\n")
        f.write(f"**Model:** {config.llm_model}\n")
        f.write(f"**Calls processed:** {len(calls)}\n")
        f.write(f"**Successful:** {len(results)}\n\n")
        f.write("## Extraction Results\n\n")
        for r in results:
            f.write(f"### Call #{r.call.call_id}\n")
            f.write(f"- **Sentimiento:** {r.entities.sentimiento}\n")
            f.write(f"- **Problema:** {r.entities.problema_reportado}\n")
            f.write(f"- **Urgencia:** {r.entities.urgencia}\n")
            f.write(f"- **Intención:** {r.entities.intencion_futura}\n")
            f.write(f"- **Queja:** {r.entities.menciona_queja}\n")
            f.write(f"- **Baja:** {r.entities.menciona_baja}\n")
            f.write(f"- **Tono:** {r.entities.tono_conversacion}\n")
            f.write(f"- **Resolución:** {r.entities.resolucion}\n\n")

    print(f"\n  💾 Resultados guardados en:\n     📄 {jsonl_path}\n     📄 {summary_path}")


def cmd_analyze(config: Config):
    """Analyze existing extraction results for insights."""
    output_dir = Path(__file__).resolve().parent.parent / "data" / "output"
    if not output_dir.exists():
        print("No output directory found. Run extraction first.")
        return

    jsonl_files = sorted(output_dir.glob("extractions_*.jsonl"))
    if not jsonl_files:
        print("No extraction results found.")
        return

    latest = jsonl_files[-1]
    print(f"\n📊 Analizando: {latest.name}\n")

    results = []
    with open(latest) as f:
        for line in f:
            results.append(json.loads(line))

    if not results:
        print("No results to analyze.")
        return

    # Aggregations
    sentimientos = {}
    urgencias = {}
    bajas = 0
    quejas = 0
    total = len(results)

    for r in results:
        ent = r.get("entities", {})
        s = ent.get("sentimiento")
        sentimientos[s] = sentimientos.get(s, 0) + 1

        u = ent.get("urgencia")
        urgencias[u] = urgencias.get(u, 0) + 1

        if ent.get("menciona_baja"):
            bajas += 1
        if ent.get("menciona_queja"):
            quejas += 1

    print(f" Total: {total} llamadas extraídas")
    print(f"\n Sentimiento:")
    for s, c in sorted(sentimientos.items(), key=lambda x: -x[1]):
        print(f"   {s}: {c} ({c/total*100:.0f}%)")
    print(f"\n Urgencia:")
    for u, c in sorted(urgencias.items(), key=lambda x: -x[1]):
        print(f"   {u}: {c} ({c/total*100:.0f}%)")
    print(f"\n Mencionan baja: {bajas} ({bajas/total*100:.0f}%)")
    print(f" Mencionan queja: {quejas} ({quejas/total*100:.0f}%)")


def main():
    parser = argparse.ArgumentParser(
        description="LangExtract-Cuidum Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--mode", "-m",
        choices=["validate", "extract", "batch", "analyze", "sample"],
        default="validate",
        help="Pipeline mode (default: validate)",
    )
    parser.add_argument(
        "--count", "-n",
        type=int,
        default=10,
        help="Number of calls to process (default: 10)",
    )
    parser.add_argument(
        "--config", "-c",
        default="config.yaml",
        help="Configuration file path",
    )

    args = parser.parse_args()
    config = Config(args.config)

    if args.mode == "validate":
        cmd_validate(config)
    elif args.mode == "extract":
        cmd_extract(config, args.count, use_sample=False)
    elif args.mode == "batch":
        cmd_extract(config, args.count, use_sample=False)
    elif args.mode == "sample":
        cmd_extract(config, args.count, use_sample=True)
    elif args.mode == "analyze":
        cmd_analyze(config)

    return 0


if __name__ == "__main__":
    sys.exit(main())
