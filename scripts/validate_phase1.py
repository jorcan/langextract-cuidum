#!/usr/bin/env python3
"""
Phase 1 validator — uses the local Hermes API server for LLM inference
so no API key is needed (Hermes handles the provider auth internally).

Usage:
    python scripts/validate_phase1.py [--count 5]
"""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.db import load_sample_calls, format_call_for_extraction
from src.models import (
    CallEntities,
    CallMetadata,
    ExtractionResult,
    EXTRACTION_PROMPT,
    EXTRACTION_EXAMPLES,
)

HERMES_API_URL = "http://127.0.0.1:8642"
API_KEY = "ht-jorge-a78e45a5aba14dc6"  # ~/.hermes/credentials.env


def call_hermes_llm(system_prompt: str, user_text: str, model: str = "deepseek-v4-flash") -> str | None:
    """Call the local Hermes API server for LLM inference."""
    import urllib.request
    import urllib.error

    payload = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text},
        ],
        "temperature": 0.1,
        "max_tokens": 4096,
    }).encode()

    req = urllib.request.Request(
        f"{HERMES_API_URL}/v1/chat/completions",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {API_KEY}",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read())
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"  ❌ LLM call failed: {e}")
        return None


def run_prompt(call_text: str, example_text: str, example_answer: str) -> dict | None:
    """Run one extraction using prompt + 1 few-shot example."""
    prompt = f"""{EXTRACTION_PROMPT}

Ejemplo:
{example_text}

Respuesta esperada:
{json.dumps(example_answer, ensure_ascii=False, indent=2)}

Ahora extrae la siguiente llamada:

{call_text}

Responde ÚNICAMENTE con el JSON de las entidades extraídas:"""

    raw = call_hermes_llm(EXTRACTION_PROMPT, f"""
Ejemplo:
{example_text}

Respuesta esperada:
{json.dumps(example_answer, ensure_ascii=False, indent=2)}

Ahora extrae la siguiente llamada:

{call_text}

Responde ÚNICAMENTE con el JSON de las entidades extraídas:
""")

    if not raw:
        return None

    # Clean response (remove markdown fences if present)
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
    if raw.endswith("```"):
        raw = raw.rsplit("```", 1)[0].strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"  ❌ JSON parse error: {e}")
        print(f"  Raw response: {raw[:300]}")
        return None


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", "-n", type=int, default=5)
    args = parser.parse_args()

    print("=" * 70)
    print("  🔬 FASE 1 — VALIDACIÓN DE EXTRACCIÓN CON DATOS REALES")
    print("  Usando Hermes API Server como backend LLM")
    print("=" * 70)

    # Load calls
    calls = load_sample_calls()[:args.count]
    if not calls:
        print("❌ No sample calls found.")
        return 1

    print(f"\n📞 Cargadas {len(calls)} llamadas de muestra")

    # Test extraction on each call
    example = EXTRACTION_EXAMPLES[0]

    results = []
    for i, call in enumerate(calls, 1):
        call_id = call.get("id")
        text = format_call_for_extraction(call, max_chars=2000)
        
        print(f"\n{'='*50}")
        print(f"  [{i}/{len(calls)}] Call #{call_id}")
        print(f"  Resumen: {(call.get('name') or '')[:80]}")
        print(f"  Transcripción: {len(text)} chars")
        print(f"{'='*50}")

        t0 = time.time()
        data = run_prompt(text, example["text"], example["entities"])
        elapsed = time.time() - t0

        if data:
            try:
                entities = CallEntities(**data)
                results.append({
                    "call_id": call_id,
                    "entities": entities.model_dump(),
                    "time": round(elapsed, 1),
                })
                
                print(f"\n  ✅ Extraído en {elapsed:.1f}s")
                print(f"     Sentimiento: {entities.sentimiento}")
                print(f"     Problema:    {entities.problema_reportado}")
                print(f"     Urgencia:    {entities.urgencia}")
                print(f"     Baja:        {'⚠️ SÍ' if entities.menciona_baja else 'No'}")
                print(f"     Queja:       {'⚠️ SÍ' if entities.menciona_queja else 'No'}")
                print(f"     Intención:   {entities.intencion_futura}")
                print(f"     Tono:        {entities.tono_conversacion}")
                print(f"     Resolución:  {entities.resolucion}")
                if entities.temas_clave:
                    print(f"     Temas:       {', '.join(entities.temas_clave)}")
            except Exception as e:
                print(f"\n  ⚠️  Datos extraídos no válidos para schema: {e}")
                print(f"     Datos: {json.dumps(data, ensure_ascii=False)[:200]}")
        else:
            print(f"\n  ❌ Falló extracción")

    # Summary
    print(f"\n{'='*70}")
    print(f"  📊 RESUMEN FASE 1")
    print(f"{'='*70}")
    print(f"  Llamadas procesadas: {len(calls)}")
    print(f"  Extracciones exitosas: {len(results)}")
    
    if results:
        sentimientos = {}
        urgencias = {}
        bajas = 0
        quejas = 0
        for r in results:
            e = r["entities"]
            s = e.get("sentimiento", "?")
            sentimientos[s] = sentimientos.get(s, 0) + 1
            u = e.get("urgencia", "?")
            urgencias[u] = urgencias.get(u, 0) + 1
            if e.get("menciona_baja"):
                bajas += 1
            if e.get("menciona_queja"):
                quejas += 1
        
        print(f"\n  Sentimiento: {sentimientos}")
        print(f"  Urgencia: {urgencias}")
        print(f"  Mencionan baja: {bajas}")
        print(f"  Mencionan queja: {quejas}")

    # Save results
    output_dir = Path(__file__).resolve().parent.parent / "data" / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    
    with open(output_dir / f"phase1_validation_{timestamp}.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print(f"\n  💾 Resultados guardados en data/output/phase1_validation_{timestamp}.json")
    
    print(f"\n  ✅ FASE 1 COMPLETADA")
    print(f"  Próximo paso: escalar a batch completo (FASE 2)")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
