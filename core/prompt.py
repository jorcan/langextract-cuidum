"""Prompt builder for the generic entity extractor.

Turns (fields, examples, existing_data, text) into a single instruction
prompt that asks the LLM for a FLAT JSON with per-field __quote__ citations.

Domain-agnostic: speaks only of "TEXTO" and "campos".
"""
import json
from typing import Any, Optional

from core.schema import FieldSpec

_EXAMPLE_MAX_CHARS = 300


def _describe_field(spec: FieldSpec) -> str:
    line = f"- {spec.name} ({spec.type})"
    if spec.description:
        line += f": {spec.description}"
    if spec.allowed:
        line += f" — valores permitidos: {', '.join(spec.allowed)}"
    if spec.validator:
        line += f" — validación: {spec.validator}"
    return line


def _field_instructions(fields: list[FieldSpec], existing_data: dict[str, Any]) -> str:
    to_extract = [f for f in fields if f.name not in existing_data]
    if not to_extract:
        return "NO hay campos que extraer: todos están ya en los datos conocidos."
    header = "Campos a extraer:\n"
    return header + "\n".join(_describe_field(f) for f in to_extract)


def _existing_section(existing_data: dict[str, Any]) -> str:
    if not existing_data:
        return ""
    lines = [f"  {k}: {v}" for k, v in existing_data.items()]
    return ("Datos ya conocidos (NO extraer estos campos, NO los repitas en la salida):\n"
            + "\n".join(lines) + "\n")


def _examples_section(examples: Optional[list[dict[str, Any]]]) -> str:
    if not examples:
        return ""
    blocks = []
    for i, ex in enumerate(examples, 1):
        text = ex.get("text", "")
        if len(text) > _EXAMPLE_MAX_CHARS:
            text = text[:_EXAMPLE_MAX_CHARS] + "..."
        extractions = json.dumps(ex.get("extractions", {}), ensure_ascii=False, indent=2)
        blocks.append(f"--- EJEMPLO {i} ---\nTranscripción:\n{text}\n\nExtracción:\n{extractions}\n")
    return "\n".join(blocks) + "\n"


def build_prompt(
    text: str,
    fields: list[FieldSpec],
    examples: Optional[list[dict[str, Any]]] = None,
    existing_data: Optional[dict[str, Any]] = None,
) -> str:
    """Construye el prompt de extracción completo."""
    fields = fields or []
    existing_data = existing_data or {}
    examples = examples or []

    instructions = (
        "Eres un extractor de datos. Del TEXTO proporcionado, extrae SOLO lo que se dice de "
        "forma explícita. Reglas:\n"
        "1. Para cada campo relleno incluye la clave __quote__ con la cita TEXTUAL LITERAL "
        "copiada carácter a carácter del texto (sin corregir ortografía ni puntuación).\n"
        "2. Si un campo NO aparece en el texto, devuelve null. PROHIBIDO inventar o inferir "
        "valores que no estén escritos.\n"
        "3. Normaliza formatos (teléfonos a dígitos con prefijo, DNIs a mayúsculas), pero "
        "siempre respaldado por la cita literal en __quote__.\n"
        "4. Responde ÚNICAMENTE con un JSON plano, sin markdown ni texto adicional.\n"
    )

    parts = [
        instructions,
        "===",
        _existing_section(existing_data),
        _field_instructions(fields, existing_data),
        "",
        _examples_section(examples),
        "--- TEXTO A PROCESAR ---",
        text,
        "",
        'Respuesta: {"campo": valor|null, "__quote__": {"campo": "cita literal", ...}}',
    ]
    return "\n".join(parts)