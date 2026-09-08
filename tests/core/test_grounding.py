"""Tests for core.grounding — verbatim quote grounding with char offsets."""
import pytest

from core.grounding import grounding

TEXT = "Operador: ¿Y quién la cuida? Cliente: Mi hija María, vive conmigo. Su DNI es 45892147K."


class TestGrounding:
    def test_exact_quote_with_offsets_ok(self):
        q = "Mi hija María"
        s = TEXT.find(q)
        status, start, end = grounding("nombre", "María", q, s, s + len(q), TEXT)
        assert status == "ok"
        assert TEXT[start:end] == q

    def test_quote_present_without_offsets_ok(self):
        status, start, end = grounding("nombre", "María", "Mi hija María", None, None, TEXT)
        assert status == "ok"
        assert start is not None and end is not None

    def test_quote_absent_fails(self):
        status, _, _ = grounding("nombre", "Carlos", "soy Carlos Mendoza", 0, 10, TEXT)
        assert status == "fail"

    def test_wrong_offsets_fail(self):
        q = "Mi hija María"
        s = TEXT.find(q)
        # offsets apuntan a otra parte del texto
        status, _, _ = grounding("nombre", "María", q, s + 5, s + 5 + len(q), TEXT)
        assert status == "fail"

    def test_case_accent_insensitive_match(self):
        status, start, end = grounding("nombre", "María", "mi hija maría", None, None, TEXT)
        assert status == "ok"
        assert TEXT[start:end].strip() == "Mi hija María"

    def test_value_none_is_not_found_not_fail(self):
        status, start, end = grounding("nombre", None, None, None, None, TEXT)
        assert status == "not_found"
        assert start is None and end is None

    def test_no_quote_uses_value_find(self):
        # Sin cita del LLM: buscamos el valor literal en el texto
        status, start, end = grounding("dni", "45892147K", None, None, None, TEXT)
        assert status == "ok"
        assert TEXT[start:end] == "45892147K"

    def test_no_quote_value_not_in_text_fails(self):
        status, _, _ = grounding("dni", "11111111X", None, None, None, TEXT)
        assert status == "fail"

    def test_derived_value_spelled_out_fails(self):
        # Teléfono normalizado que en el audio se deletrea ("seis doce...") → sin cita → fail
        text = "Mi teléfono es seis doce tres cuatro cinco seis siete"
        status, _, _ = grounding("telefono", "3461234567", None, None, None, text)
        assert status == "fail"

    def test_empty_quote_fails(self):
        status, _, _ = grounding("nombre", "María", "  ", 0, 0, TEXT)
        assert status == "fail"

    def test_offsets_without_quote_uses_value(self):
        v = "45892147K"
        s = TEXT.find(v)
        status, start, end = grounding("dni", v, None, s, s + len(v), TEXT)
        assert status == "ok"
        assert start == s and end == s + len(v)