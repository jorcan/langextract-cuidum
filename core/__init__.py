"""langextract-cuidum core — entity extraction engine, domain-agnostic.

Public API (contrato congelado):
- FieldSpec, build_dynamic_model            (core.schema)
- extract_entities, ExtractionDoc, Evidence (core.extractor)
- build_prompt                              (core.prompt)
- make_provider                             (core.providers)
- VALIDATORS, validate_field                (core.validators)
- evaluate_consensus, run_dual              (core.consensus)
"""
from core.schema import FieldSpec, build_dynamic_model
from core.extractor import ExtractionDoc, Evidence, extract_entities
from core.prompt import build_prompt
from core.providers import make_provider
from core.validators import VALIDATORS, validate_field

__all__ = [
    "FieldSpec", "build_dynamic_model",
    "extract_entities", "ExtractionDoc", "Evidence",
    "build_prompt", "make_provider",
    "VALIDATORS", "validate_field",
]