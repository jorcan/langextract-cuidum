"""Tests for core.schema — FieldSpec + dynamic Pydantic model builder."""
import pytest
from pydantic import ValidationError

# core/ aún no existe al escribir el test — los imports fallan hasta Task 1 impl
from core.schema import FieldSpec, build_dynamic_model


def _base_fields():
    return [
        FieldSpec(name="nombre_cuidador", type="string", description="Nombre del cuidador/a principal"),
        FieldSpec(name="telefono_cuidador", type="string", validator="phone_es"),
        FieldSpec(name="parentesco", type="literal", allowed=["hija", "hijo", "externa", "no_mencionado"]),
        FieldSpec(name="vive_con_paciente", type="bool"),
        FieldSpec(name="num_horas", type="int"),
        FieldSpec(name="coste_hora", type="float"),
        FieldSpec(name="etiquetas", type="list"),
    ]


# ── FieldSpec validation ────────────────────────────────────────────

class TestFieldSpec:
    @pytest.mark.parametrize("bad_type", ["texto", "", "String", "obj"])
    def test_rejects_unknown_type(self, bad_type):
        with pytest.raises(ValidationError):
            FieldSpec(name="campo", type=bad_type)

    def test_requires_allowed_for_literal(self):
        with pytest.raises(ValidationError):
            FieldSpec(name="parentesco", type="literal")

    def test_accepts_allowed_for_literal(self):
        fs = FieldSpec(name="parentesco", type="literal", allowed=["a", "b"])
        assert fs.allowed == ["a", "b"]

    @pytest.mark.parametrize("bad_name", ["Nombre", "1campo", "campo-dash", "campo con espacio", ""])
    def test_rejects_bad_field_names(self, bad_name):
        with pytest.raises(ValidationError):
            FieldSpec(name=bad_name, type="string")

    def test_accepts_valid_names(self):
        for n in ["a", "nombre_cuidador", "_x", "x1"]:
            assert FieldSpec(name=n, type="string").name == n

    def test_defaults(self):
        fs = FieldSpec(name="campo", type="bool")
        assert fs.description == ""
        assert fs.allowed is None
        assert fs.validator is None


# ── build_dynamic_model ─────────────────────────────────────────────

class TestBuildDynamicModel:
    def test_creates_model_with_all_fields(self):
        Model = build_dynamic_model(_base_fields())
        m = Model.model_fields
        for name in ["nombre_cuidador", "telefono_cuidador", "parentesco",
                     "vive_con_paciente", "num_horas", "coste_hora", "etiquetas"]:
            assert name in m, f"campo {name} ausente"

    def test_all_fields_optional(self):
        Model = build_dynamic_model(_base_fields())
        for name in Model.model_fields:
            assert Model.model_fields[name].is_required() is False, f"{name} no es opcional"

    def test_instantiate_with_literal_value_ok(self):
        Model = build_dynamic_model(_base_fields())
        m = Model(parentesco="hija", nombre_cuidador=None)
        assert m.parentesco == "hija"
        assert m.nombre_cuidador is None

    def test_instantiate_with_invalid_literal_rejected(self):
        Model = build_dynamic_model(_base_fields())
        with pytest.raises(ValidationError):
            Model(parentesco="otra_cosa")

    def test_instantiate_with_bool_and_types(self):
        Model = build_dynamic_model(_base_fields())
        m = Model(vive_con_paciente=True, num_horas=8, coste_hora=12.5, etiquetas=["a"])
        assert m.num_horas == 8
        assert m.coste_hora == 12.5

    def test_model_accepts_empty(self):
        Model = build_dynamic_model(_base_fields())
        m = Model()
        assert all(getattr(m, f) is None for f in Model.model_fields)

    def test_literal_without_allowed_raises_at_build_time(self):
        with pytest.raises(ValueError):
            build_dynamic_model([FieldSpec(name="x", type="literal", allowed=None)])