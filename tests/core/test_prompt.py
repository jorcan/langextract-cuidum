"""Tests for core.prompt — prompt generation from FieldSpec list."""
import pytest

from core.schema import FieldSpec
from core.prompt import build_prompt


def _fields():
    return [
        FieldSpec(name="nombre_cuidador", type="string",
                  description="Nombre completo del cuidador/a principal que menciona el interlocutor"),
        FieldSpec(name="parentesco", type="literal",
                  description="Parentesco del cuidador con el paciente",
                  allowed=["hija", "hijo", "externa", "no_mencionado"]),
    ]


TEXT = "Operador: ¿Quién la cuida? Cliente: Mi hija María, vive conmigo."


class TestBuildPrompt:
    def test_contains_field_descriptions(self):
        p = build_prompt(TEXT, _fields(), examples=[], existing_data={})
        assert "nombre_cuidador" in p
        assert "Nombre completo del cuidador/a principal" in p
        assert "parentesco" in p

    def test_contains_allowed_values_for_literal(self):
        p = build_prompt(TEXT, _fields(), examples=[], existing_data={})
        assert "hija" in p and "hijo" in p and "externa" in p and "no_mencionado" in p

    def test_includes_existing_data_section(self):
        p = build_prompt(TEXT, _fields(), examples=[],
                         existing_data={"nombre_cuidador": "María"})
        assert "Datos ya conocidos" in p or "ya conocidos" in p

    def test_excludes_existing_fields_from_extraction_instructions(self):
        existing = {"nombre_cuidador": "María"}
        p = build_prompt(TEXT, _fields(), examples=[], existing_data=existing)
        # El campo conocido NO debe aparecer como campo a extraer en la sección de campos
        extract_section = p.split("Campos a extraer")[1] if "Campos a extraer" in p else p
        assert "nombre_cuidador" not in extract_section
        assert "parentesco" in extract_section

    def test_includes_example_blocks(self):
        examples = [
            {"text": "Cliente: Cuida mi madre una señora externa desde hace un año.",
             "extractions": {"parentesco": "externa"}},
        ]
        p = build_prompt(TEXT, _fields(), examples=examples, existing_data={})
        assert "EJEMPLO 1" in p
        assert "externa" in p

    def test_truncates_example_text_to_300_chars(self):
        long_text = "X" * 450
        examples = [{"text": long_text, "extractions": {"parentesco": "externa"}}]
        p = build_prompt(TEXT, _fields(), examples=examples, existing_data={})
        # La línea de transcripción del ejemplo debe ser 300 X + "..."
        line = next(l for l in p.splitlines() if set(l.strip()) == {"X"} and l.strip())
        assert len(line) == 300 + 3  # "..."

    def test_instructs_flat_json_only(self):
        p = build_prompt(TEXT, _fields(), examples=[], existing_data={})
        assert "JSON" in p and "null" in p

    def test_instructs_literal_quote_citation(self):
        p = build_prompt(TEXT, _fields(), examples=[], existing_data={})
        assert "quote" in p or "cita" in p.lower()

    def test_without_examples_ok(self):
        p = build_prompt(TEXT, _fields(), examples=None, existing_data={})
        assert "EJEMPLO" not in p

    def test_empty_existing_data_ok(self):
        p = build_prompt(TEXT, _fields(), examples=[], existing_data=None)
        assert "Campos a extraer" in p

    def test_transcription_included(self):
        p = build_prompt(TEXT, _fields(), examples=[], existing_data={})
        assert TEXT in p