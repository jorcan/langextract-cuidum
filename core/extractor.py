"""Generic entity extractor — composes all core gates into one call.

extract_entities(text, fields, examples, existing_data, provider)
  -> ExtractionDoc (evidence per field with grounding + validators)
"""
import json
import logging
import re
from typing import Any, Optional

from pydantic import BaseModel, Field

from core.coerce import coerce_value
from core.grounding import grounding as grounding_check
from core.prompt import build_prompt
from core.schema import FieldSpec
from core.validators import validate_field

logger = logging.getLogger(__name__)

_STATUS_OK = "ok"
_STATUS_NOT_FOUND = "not_found"
_STATUS_GROUNDING_FAIL = "grounding_fail"
_STATUS_VALIDATOR_FAIL = "validator_fail"


def _clean_json_response(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
    if raw.endswith("```"):
        raw = raw.rsplit("```", 1)[0].strip()
    return raw


class Evidence(BaseModel):
    field_name: str
    value: Any = None
    verbatim_quote: Optional[str] = None
    start_char: Optional[int] = None
    end_char: Optional[int] = None
    status: str = _STATUS_OK
    validated_by: list[str] = Field(default_factory=list)


class ExtractionDoc(BaseModel):
    extracted_fields: list[Evidence] = Field(default_factory=list)

    @property
    def extractions(self) -> list[Evidence]:
        """Alias de compatibilidad: los tests y la API usan .extractions."""
        return self.extracted_fields

    @property
    def missing_fields(self) -> list[str]:
        return [e.field_name for e in self.extracted_fields if e.status == _STATUS_NOT_FOUND]

    @property
    def ok_fields(self) -> list[Evidence]:
        return [e for e in self.extracted_fields if e.status == _STATUS_OK]

    def format(self) -> dict[str, Any]:
        return {
            "extractions": [e.model_dump() for e in self.extracted_fields],
            "missing_fields": self.missing_fields,
            "flat": {e.field_name: e.value for e in self.ok_fields},
        }


def _to_python_literal(value: Any) -> Any:
    """Convert JSON-deserialized values from the LLM (already Python objects)."""
    return value


def extract_entities(
    text: str,
    fields: list[FieldSpec],
    examples: Optional[list[dict[str, Any]]] = None,
    existing_data: Optional[dict[str, Any]] = None,
    provider: Any = None,
    temperature: float = 0.05,
) -> ExtractionDoc:
    """Extract entities from `text` with full validation pipeline.

    `provider` is any object with .infer([prompt]) -> [[{output: str}]].
    """
    fields = fields or []
    existing_data = existing_data or {}
    if provider is None:
        raise ValueError("provider requerido (p.ej. make_provider('hermes-api'))")

    prompt = build_prompt(text, fields, examples=examples, existing_data=existing_data)

    try:
        results = list(provider.infer([prompt]))
    except Exception as e:
        logger.error("Provider error: %s", e)
        return ExtractionDoc()

    if not results or not results[0]:
        logger.warning("Empty provider response")
        return ExtractionDoc()

    raw = results[0][0].output
    if not raw:
        logger.warning("Empty output text")
        return ExtractionDoc()

    try:
        data = json.loads(_clean_json_response(raw))
    except json.JSONDecodeError as e:
        logger.error("JSON parse error: %s", e)
        return ExtractionDoc()

    if not isinstance(data, dict):
        logger.error("LLM output no es objeto JSON")
        return ExtractionDoc()

    quotes = data.pop("__quote__", {}) or {}

    evidence_list: list[Evidence] = []
    for spec in fields:
        name = spec.name
        if name in existing_data:
            continue  # dato ya conocido: no se re-extrae

        raw_value = data.get(name)
        value = coerce_value(spec, raw_value) if raw_value is not None else None
        if value is None:
            evidence_list.append(Evidence(field_name=name, value=None, status=_STATUS_NOT_FOUND))
            continue

        quote = quotes.get(name)
        g_status, start, end = grounding_check(
            name, value, quote, None, None, text
        )
        if g_status != "ok":
            status = _STATUS_GROUNDING_FAIL if g_status == "fail" else _STATUS_NOT_FOUND
            evidence_list.append(Evidence(
                field_name=name, value=value, status=status,
                verbatim_quote=quote, start_char=start, end_char=end,
            ))
            continue

        ok_v, passed = validate_field(spec, value)
        if not ok_v:
            evidence_list.append(Evidence(
                field_name=name, value=value, status=_STATUS_VALIDATOR_FAIL,
                verbatim_quote=quote, start_char=start, end_char=end,
            ))
            continue

        evidence_list.append(Evidence(
            field_name=name, value=value, status=_STATUS_OK,
            verbatim_quote=quote, start_char=start, end_char=end,
            validated_by=["grounding"] + passed,
        ))

    return ExtractionDoc(extracted_fields=evidence_list)