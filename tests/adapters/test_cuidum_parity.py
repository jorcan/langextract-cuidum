"""Paridad entre el core genérico (FIELDS_102) y el schema legacy CallEntities."""
import json

from src.models import CallEntities  # legacy (migración en curso)
from core.schema import build_dynamic_model
from core.extractor import extract_entities
from adapters.cuidum.schema_102 import FIELDS_102, CallEntities102


class FakeOutput:
    def __init__(self, raw):
        self.output = raw


class FakeProvider:
    def __init__(self, raw):
        self.raw = raw

    def infer(self, prompts):
        return [[FakeOutput(self.raw)]]


def test_field_set_parity():
    legacy_names = set(CallEntities.model_fields)
    core_names = {f.name for f in FIELDS_102}
    assert legacy_names == core_names, (
        f"Faltan: {legacy_names - core_names} | Sobran: {core_names - legacy_names}")


def test_description_parity():
    legacy = {n: i.description for n, i in CallEntities.model_fields.items()}
    for f in FIELDS_102:
        assert legacy[f.name] == f.description, f"descripción distinta en {f.name}"


def test_type_distribution():
    from collections import Counter
    dist = Counter(f.type for f in FIELDS_102)
    assert dist["string"] == 69
    assert dist["list"] == 11
    assert dist["bool"] == 17
    assert dist["float"] == 4
    assert dist["int"] == 1


def test_both_models_accept_legacy_output():
    """Un output típico del LLM legacy debe parsear en ambos modelos."""
    out = {
        "problema_reportado": "La cuidadora llegó tarde",
        "quien_llama": "hija",
        "menciona_baja": False,
        "sentimiento_general": "preocupado",
        "temas_clave": ["horarios", "sustitución"],
    }
    CallEntities(**out)
    CallEntities102(**out)


def test_dynamic_model_accepts_empty():
    m = CallEntities102()
    assert len(m.model_fields) == 102


def test_core_extracts_with_fields_102_and_parses_in_legacy():
    """El core genérico extrae usando FIELDS_102 y su salida parsea en CallEntities."""
    text = "Cliente: soy María Pérez, vivo con mi madre en Madrid. Carmen es mi hija y la cuida."
    raw = json.dumps({
        "quien_llama": "familiar",
        "ubicacion_servicio": "Madrid",
        "menciona_baja": None,
        "quien_cuida_mencionado": None,
        "__quote__": {
            "quien_llama": "Cliente: soy María Pérez",
            "ubicacion_servicio": "Madrid",
        },
    })
    doc = extract_entities(text, FIELDS_102, provider=FakeProvider(raw))
    flat = doc.format()["flat"]
    assert flat["quien_llama"] == "familiar"
    assert flat["ubicacion_servicio"] == "Madrid"
    # El flat del core debe ser parseable por el modelo legacy (paridad de contrato)
    legacy_parsed = CallEntities(**flat)
    assert legacy_parsed.quien_llama == "familiar"


def test_quien_llama_grounded_with_citation():
    text = "Cliente: soy María Pérez, en Madrid."
    raw = json.dumps({"quien_llama": "familiar",
                      "__quote__": {"quien_llama": "Cliente: soy María Pérez"}})
    doc = extract_entities(text, FIELDS_102, provider=FakeProvider(raw))
    ev = {e.field_name: e for e in doc.extractions}
    assert ev["quien_llama"].status == "ok"
    assert ev["quien_llama"].verbatim_quote == "Cliente: soy María Pérez"