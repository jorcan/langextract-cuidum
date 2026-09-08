"""Tests for core.extractor — extract_entities orchestration (mocked provider)."""
import json

import pytest

from core.schema import FieldSpec
from core.extractor import extract_entities, ExtractionDoc, Evidence


class FakeOutput:
    def __init__(self, raw):
        self.output = raw


class FakeProvider:
    def __init__(self, raw_json):
        self.raw_json = raw_json
        self.prompts = []

    def infer(self, prompts):
        self.prompts = list(prompts)
        return [[FakeOutput(self.raw_json)]]


FIELDS = [
    FieldSpec(name="nombre_cuidador", type="string", description="Nombre del cuidador"),
    FieldSpec(name="dni_cuidador", type="string", validator="dni"),
    FieldSpec(name="parentesco", type="literal", allowed=["hija", "hijo", "externa", "no_mencionado"]),
    FieldSpec(name="vive_con_paciente", type="bool"),
]

TEXT = "Cliente: Soy María, mi hija cuida de mí. Su DNI es 45892147V y vive conmigo."


def _llm_ok():
    return json.dumps({
        "nombre_cuidador": "María",
        "dni_cuidador": "45892147V",
        "parentesco": "hija",
        "vive_con_paciente": "si",
        "__quote__": {
            "nombre_cuidador": "Soy María",
            "dni_cuidador": "45892147V",
            "parentesco": "mi hija cuida",
            "vive_con_paciente": "vive conmigo",
        },
    })


class TestExtractEntities:
    def test_happy_path_all_ok(self):
        doc = extract_entities(TEXT, FIELDS, provider=FakeProvider(_llm_ok()))
        ev = {e.field_name: e for e in doc.extractions}
        assert ev["nombre_cuidador"].value == "María"
        assert ev["nombre_cuidador"].status == "ok"
        assert ev["dni_cuidador"].value == "45892147V"
        assert "dni" in ev["dni_cuidador"].validated_by
        assert ev["vive_con_paciente"].value is True
        assert doc.missing_fields == []

    def test_not_found_fields(self):
        raw = json.dumps({"nombre_cuidador": None, "dni_cuidador": None,
                          "parentesco": "no_mencionado", "vive_con_paciente": None,
                          "__quote__": {"parentesco": "no lo sé"}})
        doc = extract_entities(TEXT, FIELDS, provider=FakeProvider(raw))
        ev = {e.field_name: e for e in doc.extractions}
        assert ev["nombre_cuidador"].status == "not_found"
        assert ev["vive_con_paciente"].status == "not_found"
        assert doc.missing_fields == ["nombre_cuidador", "dni_cuidador", "vive_con_paciente"]

    def test_grounding_fail_when_quote_absent(self):
        raw = json.dumps({"nombre_cuidador": "Carlos", "dni_cuidador": None,
                          "parentesco": "hija", "vive_con_paciente": None,
                          "__quote__": {"nombre_cuidador": "soy Carlos Mendoza", "parentesco": "hija"}})
        doc = extract_entities(TEXT, FIELDS, provider=FakeProvider(raw))
        ev = {e.field_name: e for e in doc.extractions}
        assert ev["nombre_cuidador"].status == "grounding_fail"

    def test_validator_fail(self):
        # DNI inválido por módulo 23, con cita LITERAL presente en el texto
        text_v = "Cliente: Soy María, mi hija cuida de mí. Su DNI es 45892147K y vive conmigo."
        raw = json.dumps({"nombre_cuidador": "María", "dni_cuidador": "45892147K",
                          "parentesco": "hija", "vive_con_paciente": "si",
                          "__quote__": {"nombre_cuidador": "Soy María", "dni_cuidador": "45892147K",
                                        "parentesco": "mi hija", "vive_con_paciente": "vive conmigo"}})
        doc = extract_entities(text_v, FIELDS, provider=FakeProvider(raw))
        ev = {e.field_name: e for e in doc.extractions}
        # OJO: el valor tiene cita → grounding ok → el validador lo rechaza
        assert ev["dni_cuidador"].status == "validator_fail"

    def test_existing_data_excluded_from_prompt_and_output(self):
        provider = FakeProvider(_llm_ok())
        doc = extract_entities(TEXT, FIELDS, provider=provider,
                               existing_data={"nombre_cuidador": "María"})
        # campo conocido no aparece en extractos
        assert all(e.field_name != "nombre_cuidador" for e in doc.extractions)
        # y el prompt no pide extraerlo
        assert "Campos a extraer" in provider.prompts[0]
        extract_section = provider.prompts[0].split("Campos a extraer")[1]
        assert "nombre_cuidador" not in extract_section

    def test_no_quote_key_uses_value_find(self):
        raw = json.dumps({"nombre_cuidador": "María", "dni_cuidador": "45892147V",
                          "parentesco": "hija", "vive_con_paciente": "si"})  # sin __quote__
        doc = extract_entities(TEXT, FIELDS, provider=FakeProvider(raw))
        ev = {e.field_name: e for e in doc.extractions}
        assert ev["nombre_cuidador"].status == "ok"
        assert ev["nombre_cuidador"].start_char == TEXT.find("María")

    def test_format_returns_json_ready(self):
        doc = extract_entities(TEXT, FIELDS, provider=FakeProvider(_llm_ok()))
        d = doc.format()
        assert set(d.keys()) >= {"extractions", "missing_fields", "flat"}
        assert d["flat"]["nombre_cuidador"] == "María"
        assert isinstance(d["extractions"], list)

    def test_evidence_is_pydantic(self):
        doc = extract_entities(TEXT, FIELDS, provider=FakeProvider(_llm_ok()))
        assert all(isinstance(e, Evidence) for e in doc.extractions)
        assert isinstance(doc, ExtractionDoc)

    def test_literal_coerced_and_grounded(self):
        doc = extract_entities(TEXT, FIELDS, provider=FakeProvider(_llm_ok()))
        ev = {e.field_name: e for e in doc.extractions}
        assert ev["parentesco"].value == "hija"

    def test_prompt_sent_to_provider(self):
        provider = FakeProvider(_llm_ok())
        extract_entities(TEXT, FIELDS, provider=provider)
        assert TEXT in provider.prompts[0]

    def test_non_dict_quote_tolerated(self):
        """__quote__ inválido (int/string) no debe romper la extracción."""
        raw = json.dumps({"nombre_cuidador": "María", "dni_cuidador": "45892147V",
                          "parentesco": "hija", "vive_con_paciente": "si",
                          "__quote__": 42})  # quote inválida -> se ignora, grounding offline
        doc = extract_entities(TEXT, FIELDS, provider=FakeProvider(raw))
        ev = {e.field_name: e for e in doc.extractions}
        # sin quotes: grounding offline con value.find -> sigue siendo ok
        assert ev["nombre_cuidador"].status == "ok"
        assert ev["dni_cuidador"].status == "ok"