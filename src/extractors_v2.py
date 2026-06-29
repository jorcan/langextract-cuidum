"""
Extractor v2 — Schema reducido con Literal types para consistencia.

Usa google/langextract's provider infrastructure pero con prompts mucho
más cortos y tipos Literal para forzar valores consistentes.
"""

import json
import logging
import os
import time
from typing import Any

from langextract.langextract.providers.openai import OpenAILanguageModel

from src.config import Config
from src.db import format_call_for_extraction
from src.models_v2 import (
    TriageExtraction,
    PartnerProfileExtraction,
    TriageResult,
    ProfileResult,
    ExtractionMetadata,
)

logger = logging.getLogger(__name__)

HERMES_API_URL = "http://127.0.0.1:8642/v1"

TRIAGE_SYSTEM_PROMPT = """Eres un asistente que extrae información estructurada de transcripciones de llamadas de atención al cliente de una empresa de cuidado de personas mayores.

Extrae ÚNICAMENTE estos campos con los valores EXACTOS indicados. No inventes valores que no estén en las opciones.

CAMPO: urgencia → "rutinario" o "urgente"
CAMPO: menciona_baja → true o false (¿quiere darse de baja?)
CAMPO: menciona_queja → true o false (¿se queja del servicio?)
CAMPO: menciona_competidores → true o false (¿nombra otras empresas?)
CAMPO: upsell_opportunity → true o false (¿quiere más servicios?)
CAMPO: intencion_futura → "renovar", "cancelar", "esperar", "evaluando", "no_mencionada"
CAMPO: sentimiento_general → "positivo", "neutral", "negativo", "preocupado", "agradecido"
CAMPO: necesidad_especifica → texto libre describiendo lo que necesita (o null)
CAMPO: churn_risk_score → número de 0.0 a 1.0

Responde SOLO con el JSON, sin explicaciones."""

PROFILE_SYSTEM_PROMPT = """Eres un asistente que extrae información de transcripciones de llamadas de una empresa de cuidado de personas mayores.

Usa EXACTAMENTE estos valores para cada campo. No uses sinónimos ni variantes.

CAMPO: urgencia → "rutinario" o "urgente"
CAMPO: menciona_baja → true o false
CAMPO: menciona_queja → true o false  
CAMPO: menciona_competidores → true o false
CAMPO: upsell_opportunity → true o false
CAMPO: intencion_futura → "renovar", "cancelar", "esperar", "evaluando", "no_mencionada"
CAMPO: sentimiento_general → "positivo", "neutral", "negativo", "preocupado", "agradecido"
CAMPO: necesidad_especifica → texto libre (null si no aplica)
CAMPO: churn_risk_score → 0.0 a 1.0
CAMPO: quien_llama → "familiar", "paciente", "cuidadora", "gestor", "otro"
CAMPO: relacion_llamante_paciente → texto breve (o null)
CAMPO: patologia_principal → texto breve (o null)
CAMPO: fase_ciclo_cliente → "prospeccion", "captacion", "onboarding", "estable", "riesgo", "fuga", "no_aplica"
CAMPO: intencion_permanencia → "seguro", "evaluando", "temporal", "no_mencionada"
CAMPO: ampliacion_horas_interes → true o false
CAMPO: agradecimiento_cliente → true o false

Responde SOLO con el JSON."""


def _get_hermes_api_key() -> str:
    key = os.environ.get("API_SERVER_KEY", "")
    if key:
        return key
    return "ht-jorge-a78e45a5aba14dc6"


def extract_triage(call: dict[str, Any], config: Config) -> TriageResult | None:
    """Pipeline A: extracción rápida de 9 entidades para triage."""
    call_id = call.get("id")
    partner_id = call.get("partner_id")

    text_block = format_call_for_extraction(call, max_chars=config.max_char_buffer)
    prompt = TRIAGE_SYSTEM_PROMPT + "\n\n--- LLAMADA ---\n" + text_block + "\n\n--- JSON ---\n"

    try:
        model = OpenAILanguageModel(
            model_id="gpt-4o-mini",
            api_key=_get_hermes_api_key(),
            base_url=HERMES_API_URL,
            temperature=0.05,  # Baja temperatura para consistencia
            max_workers=1,
        )
        results = list(model.infer([prompt]))
        if not results or not results[0]:
            return None

        raw = results[0][0].output.strip()
        # Clean markdown code fences
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
        if raw.endswith("```"):
            raw = raw.rsplit("```", 1)[0].strip()

        data = json.loads(raw)

        # Coerce literal fields that LLM might get slightly wrong
        _coerce_literals(data)

        entities = TriageExtraction(**data)

        return TriageResult(
            call=ExtractionMetadata(
                call_id=call_id,
                partner_id=partner_id,
                call_date=str(call.get("create_date", "")),
            ),
            entities=entities,
        )
    except Exception as e:
        logger.warning("Triage error call %s: %s", call_id, e)
        return None


def extract_profile(call: dict[str, Any], config: Config) -> ProfileResult | None:
    """Pipeline B: extracción completa de 16 entidades."""
    call_id = call.get("id")
    partner_id = call.get("partner_id")

    text_block = format_call_for_extraction(call, max_chars=config.max_char_buffer)
    prompt = PROFILE_SYSTEM_PROMPT + "\n\n--- LLAMADA ---\n" + text_block + "\n\n--- JSON ---\n"

    try:
        model = OpenAILanguageModel(
            model_id="gpt-4o-mini",
            api_key=_get_hermes_api_key(),
            base_url=HERMES_API_URL,
            temperature=0.05,
            max_workers=1,
        )
        results = list(model.infer([prompt]))
        if not results or not results[0]:
            return None

        raw = results[0][0].output.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
        if raw.endswith("```"):
            raw = raw.rsplit("```", 1)[0].strip()

        data = json.loads(raw)
        _coerce_literals(data)

        entities = PartnerProfileExtraction(**data)

        return ProfileResult(
            call=ExtractionMetadata(
                call_id=call_id,
                partner_id=partner_id,
                call_date=str(call.get("create_date", "")),
            ),
            entities=entities,
        )
    except Exception as e:
        logger.warning("Profile error call %s: %s", call_id, e)
        return None


LITERAL_MAP = {
    "urgencia": ["rutinario", "urgente"],
    "intencion_futura": ["renovar", "cancelar", "esperar", "evaluando", "no_mencionada"],
    "sentimiento_general": ["positivo", "neutral", "negativo", "preocupado", "agradecido"],
    "quien_llama": ["familiar", "paciente", "cuidadora", "gestor", "otro"],
    "fase_ciclo_cliente": ["prospeccion", "captacion", "onboarding", "estable", "riesgo", "fuga", "no_aplica"],
    "intencion_permanencia": ["seguro", "evaluando", "temporal", "no_mencionada"],
}


def _coerce_literals(data: dict):
    """Normalize literal values that the LLM might spell slightly differently."""
    for field, valid_values in LITERAL_MAP.items():
        if field in data and isinstance(data[field], str):
            val = data[field].strip().lower()
            # Direct match?
            if val in valid_values:
                data[field] = val
                continue
            # Fuzzy: find closest match
            for v in valid_values:
                if val == v[:len(val)] or v == val[:len(v)]:
                    data[field] = v
                    break
            else:
                # Try common mappings
                if val in ("urgente", "urgencia"):
                    data[field] = "urgente" if field == "urgencia" else data[field]
                if val in ("si", "sí", "true", "verdadero"):
                    data[field] = "si"
                if val in ("no", "false", "falso"):
                    data[field] = "no"


def extract_triage_batch(
    calls: list[dict[str, Any]],
    config: Config,
    max_workers: int = 20,
) -> list[TriageResult]:
    """Batch triage extraction en paralelo."""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    results = []
    errors = 0
    t0 = time.time()

    def process(call):
        return extract_triage(call, config)

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = [pool.submit(process, call) for call in calls]
        for f in as_completed(futures):
            result = f.result()
            if result:
                results.append(result)

    elapsed = time.time() - t0
    logger.info("Triage batch: %d ok, llamadas en %.1fs", len(results), elapsed)
    return results
