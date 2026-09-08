"""langextract-cuidum core — entity extraction engine, domain-agnostic.

Public API (contrato congelado):
- FieldSpec, build_dynamic_model        (core.schema)
- extract_entities, ExtractionDoc, Evidence  (core.extractor — Task 7)
- make_provider, run_dual               (core.providers / core.consensus)
- VALIDATORS, validate_field            (core.validators — Task 6)
"""