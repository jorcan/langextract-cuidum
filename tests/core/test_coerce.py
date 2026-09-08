"""Tests for core.coerce — declarative value coercion driven by FieldSpec.type."""
import pytest

from core.schema import FieldSpec
from core.coerce import coerce_value, coerce_all


def fs(name, type_, **kw):
    return FieldSpec(name=name, type=type_, **kw)


class TestCoerceBool:
    @pytest.mark.parametrize("raw", ["true", "True", "TRUE", "sí", "si", "Sí", 1, 1.0, True])
    def test_true_values(self, raw):
        assert coerce_value(fs("campo", "bool"), raw) is True

    @pytest.mark.parametrize("raw", ["false", "False", "no", "No", 0, 0.0, False])
    def test_false_values(self, raw):
        assert coerce_value(fs("campo", "bool"), raw) is False

    @pytest.mark.parametrize("raw", ["quizas", "tal vez", None, 42])
    def test_invalid_becomes_none(self, raw):
        assert coerce_value(fs("campo", "bool"), raw) is None


class TestCoerceInt:
    @pytest.mark.parametrize("raw,exp", [("7", 7), (7, 7), (7.0, 7), ("12.0", 12)])
    def test_int_coercion(self, raw, exp):
        assert coerce_value(fs("campo", "int"), raw) == exp

    @pytest.mark.parametrize("raw", ["abc", "7,5", None, "7.9"])
    def test_invalid_becomes_none(self, raw):
        assert coerce_value(fs("campo", "int"), raw) is None


class TestCoerceFloat:
    @pytest.mark.parametrize("raw,exp", [("3.5", 3.5), (3, 3.0), ("3,5", 3.5), (2.75, 2.75)])
    def test_float_coercion(self, raw, exp):
        assert coerce_value(fs("campo", "float"), raw) == exp

    def test_invalid_becomes_none(self):
        assert coerce_value(fs("campo", "float"), "abc") is None


class TestCoerceList:
    def test_python_list_string(self):
        assert coerce_value(fs("campo", "list"), "['a', 'b']") == ["a", "b"]

    def test_json_array_string(self):
        assert coerce_value(fs("campo", "list"), '["a", "b"]') == ["a", "b"]

    def test_real_list_passthrough(self):
        assert coerce_value(fs("campo", "list"), ["a"]) == ["a"]

    @pytest.mark.parametrize("raw", ["ninguno", "none", "null", "no_mencionado", "no mencionado"])
    def test_empty_sentinels_to_none(self, raw):
        assert coerce_value(fs("campo", "list"), raw) is None

    def test_garbage_becomes_empty_list(self):
        assert coerce_value(fs("campo", "list"), "esto no es una lista") == []


class TestCoerceLiteral:
    ALLOWED = ["hija", "hijo", "externa", "no_mencionado"]

    def test_exact_match(self):
        assert coerce_value(fs("p", "literal", allowed=self.ALLOWED), "hija") == "hija"

    def test_case_and_space_insensitive(self):
        assert coerce_value(fs("p", "literal", allowed=self.ALLOWED), "  Hija ") == "hija"

    def test_prefix_match(self):
        # Caso real del proyecto 102: "neutral_informativo" → "neutral"
        assert coerce_value(fs("p", "literal", allowed=["neutral", "negativo"]), "neutral_informativo") == "neutral"

    def test_accent_insensitive(self):
        assert coerce_value(fs("p", "literal", allowed=["conyuge"]), "cónyuge") == "conyuge"

    def test_no_match_becomes_none(self):
        assert coerce_value(fs("p", "literal", allowed=self.ALLOWED), "prima") is None


class TestCoerceString:
    def test_string_passthrough(self):
        assert coerce_value(fs("c", "string"), "Hola") == "Hola"

    @pytest.mark.parametrize("raw,exp", [(True, "si"), (False, "no")])
    def test_unexpected_bool_to_si_no(self, raw, exp):
        assert coerce_value(fs("c", "string"), raw) == exp

    def test_nullish_to_none(self):
        assert coerce_value(fs("c", "string"), None) is None


class TestCoerceAll:
    def test_knows_fields_not_names(self):
        """Cualquier schema nuevo se coercea por su tipo — sin listas de nombres."""
        fields = [
            fs("algo_novedoso_a", "bool"),
            fs("algo_novedoso_b", "int"),
        ]
        out = coerce_all(fields, {"algo_novedoso_a": "si", "algo_novedoso_b": "7"})
        assert out == {"algo_novedoso_a": True, "algo_novedoso_b": 7}

    def test_ignores_unknown_keys(self):
        out = coerce_all([fs("a", "bool")], {"a": "si", "fantasma": "x"})
        assert out == {"a": True, "fantasma": "x"}