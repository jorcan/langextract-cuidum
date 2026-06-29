"""Entity extraction using google/langextract's provider infrastructure
(OpenAI provider -> Hermes API Server -> DeepSeek v4 Flash)
but parsing the flat JSON output ourselves."""

import json
import logging
import os
import time
from typing import Any

from langextract.langextract.core import data as lx_data
from langextract.langextract.providers import load_builtins_once, load_plugins_once
from langextract.langextract.providers.openai import OpenAILanguageModel

from src.config import Config
from src.db import format_call_for_extraction
from src.models import (
    CallEntities,
    CallMetadata,
    ExtractionResult,
    EXTRACTION_PROMPT,
)

logger = logging.getLogger(__name__)

HERMES_API_URL = "http://127.0.0.1:8642/v1"

# Read API key from env or credentials file
def _get_hermes_api_key() -> str:
    """Get Hermes API key from env or use stored key."""
    key = os.environ.get("API_SERVER_KEY", "")
    if key:
        return key
    try:
        with open(os.path.expanduser("~/.hermes/credentials.env")) as f:
            for line in f:
                if "API_SERVER_KEY=" in line and "***" not in line:
                    parts = line.split("=", 1)
                    return parts[1].strip().strip("\"'")
    except Exception:
        pass
    # Fallback — key stored at setup time
    return "ht-jorge-a78e45a5aba14dc6"


def _build_prompt(call: dict[str, Any], config: Config) -> str:
    """Build the full prompt with instructions and examples."""
    text_block = format_call_for_extraction(call, max_chars=config.max_char_buffer)
    
    prompt = EXTRACTION_PROMPT + "\n\n"
    
    from src.models import EXTRACTION_EXAMPLES
    for i, ex in enumerate(EXTRACTION_EXAMPLES, 1):
        prompt += f"--- EJEMPLO {i} ---\n"
        prompt += f"Transcripción:\n{ex['text'][:300]}...\n\n"
        prompt += "Extracción:\n"
        prompt += json.dumps(ex["entities"], ensure_ascii=False, indent=2)
        prompt += "\n\n"
    
    prompt += "--- LLAMADA A EXTRAER ---\n"
    prompt += text_block + "\n\n"
    prompt += "Responde ÚNICAMENTE con el JSON de las entidades extraídas (el schema completo, con null para campos sin información):"
    
    return prompt


def _clean_json_response(raw: str) -> str:
    """Clean the LLM response to extract valid JSON."""
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
    if raw.endswith("```"):
        raw = raw.rsplit("```", 1)[0].strip()
    return raw


def _coerce_values(data: dict) -> dict:
    """Coerce string values to proper types for the Pydantic schema."""
    # List fields that may come as string representations
    list_fields = [
        "temas_clave", "patologias_secundarias", "alergias_intolerancias",
        "necesidades_no_cubiertas", "servicios_extra_solicitados",
        "menciona_competidores", "incidencias_repetitivas",
        "barreras_logisticas", "problemas_material_equipamiento",
        "menciona_competidores_lista", "discrepancia_datos_odoo",
        "personas_mencionadas", "documentos_mencionados",
    ]
    
    # Float fields
    float_fields = ["satisfaccion_general", "churn_risk_score", "baja_probabilidad_inferida", "duracion_llamada_minutos"]
    
    # Int fields
    int_fields = ["ventana_abandono_estimada_dias"]
    
    # Boolean fields
    bool_fields = [
        "menciona_baja", "menciona_queja", "necesita_rehabilitacion",
        "riesgo_ulceras", "negociacion_tarifa", "ampliacion_horas_interes",
        "reduccion_horas_riesgo", "soledad_aislamiento", "agradecimiento_cliente",
        "empatia_gestor", "solicitudes_ultima_hora", "deseo_cambio_cuidadora",
        "downgrade_risk", "upsell_opportunity", "anomalia_comportamiento",
        "mejora_salud_implica_baja", "amenaza_reclamacion_legal",
    ]

    # String fields that LLM sometimes returns as bool — coerce back
    string_coerce_fields = ["rotacion_cuidadoras_explicita"]
    
    for field in list_fields:
        if field in data and isinstance(data[field], str):
            val = data[field].strip()
            if val.startswith("[") and val.endswith("]"):
                try:
                    data[field] = json.loads(val.replace("'", '"'))
                except (json.JSONDecodeError, TypeError):
                    data[field] = []
            elif val.lower() in ("none", "null", "", "no_mencionado", "ninguno"):
                data[field] = None
    
    for field in float_fields:
        if field in data and isinstance(data[field], (int, float, str)):
            try:
                data[field] = float(data[field])
            except (ValueError, TypeError):
                data[field] = None
    
    for field in int_fields:
        if field in data and isinstance(data[field], (int, float, str)):
            try:
                data[field] = int(float(data[field]))
            except (ValueError, TypeError):
                data[field] = None
    
    for field in bool_fields:
        if field in data:
            if isinstance(data[field], str):
                v = data[field].strip().lower()
                if v in ("true", "sí", "si"):
                    data[field] = True
                elif v in ("false", "no"):
                    data[field] = False
                else:
                    data[field] = None
    
    # String fields that LLM sometimes returns as bool — coerce back
    string_coerce_fields = ["rotacion_cuidadoras_explicita"]
    for field in string_coerce_fields:
        if field in data and isinstance(data[field], bool):
            data[field] = "si" if data[field] else "no"
    
    return data


def extract_single_call(
    call: dict[str, Any],
    config: Config,
) -> ExtractionResult | None:
    """Extract entities using OpenAI provider + Hermes API, parsing flat JSON."""
    call_id = call.get("id")
    partner_id = call.get("partner_id")
    
    try:
        prompt = _build_prompt(call, config)
        
        # Use langextract's OpenAI provider pointed at Hermes API Server
        model = OpenAILanguageModel(
            model_id="gpt-4o-mini",
            api_key=_get_hermes_api_key(),
            base_url=HERMES_API_URL,
            temperature=config.llm_temperature,
            max_workers=1,
        )
        
        # Get raw text output via langextract's provider infrastructure
        results = list(model.infer([prompt]))
        
        if not results or not results[0]:
            logger.warning("Empty response for call %s", call_id)
            return None
        
        raw = results[0][0].output
        if not raw:
            logger.warning("No output text for call %s", call_id)
            return None
        
        raw = _clean_json_response(raw)
        data = json.loads(raw)
        data = _coerce_values(data)
        
        # Validate against Pydantic schema
        entities = CallEntities(**data)
        
        return ExtractionResult(
            call=CallMetadata(
                call_id=call_id,
                partner_id=partner_id,
                call_date=str(call.get("create_date", "")),
                clave=call.get("clave"),
                subclave=call.get("subclave"),
            ),
            entities=entities,
            confidence=1.0,
            schema_version="2.0.0",
            raw_text_preview=prompt[:200],
        )
    
    except json.JSONDecodeError as e:
        logger.error("JSON parse error for call %s: %s", call_id, e)
    except Exception as e:
        logger.error("Extraction error for call %s: %s (%s)", call_id, type(e).__name__, e)
    
    return None


def extract_batch(
    calls: list[dict[str, Any]],
    config: Config,
    show_progress: bool = True,
) -> list[ExtractionResult]:
    """Extract entities from a batch using langextract's provider infrastructure."""
    if not calls:
        return []
    
    results = []
    errors = 0
    t0 = time.time()
    
    for i, call in enumerate(calls, 1):
        result = extract_single_call(call, config)
        if result:
            results.append(result)
            if show_progress:
                non_null = sum(1 for v in result.entities.model_dump().values() if v is not None)
                print(f"  ✅ [{i}/{len(calls)}] Call #{call.get('id')} — {non_null}/102 campos")
        else:
            errors += 1
            if show_progress:
                print(f"  ❌ [{i}/{len(calls)}] Call #{call.get('id')} — Falló")
    
    elapsed = time.time() - t0
    logger.info("Batch: %d ok, %d errors in %.1fs", len(results), errors, elapsed)
    return results


def results_to_jsonl(results: list[ExtractionResult], output_path: str) -> None:
    """Save extraction results to JSONL."""
    with open(output_path, "w", encoding="utf-8") as f:
        for r in results:
            f.write(r.model_dump_json(ensure_ascii=False, exclude={"raw_text_preview"}) + "\n")
    logger.info("Saved %d results to %s", len(results), output_path)
