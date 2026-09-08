"""Tests del CLI y del caso partner-fill (schema + query candidatos)."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from scripts.extract_cli import resolve_schema, main
from adapters.cuidum.partner_fill import (
    load_partner_fill_schema, fetch_candidates_query
)
from core.schema import build_dynamic_model


class TestResolveSchema:
    def test_partner_fill(self):
        fields, targets = resolve_schema("partner-fill")
        names = {f.name for f in fields}
        assert {"nombre_cuidador", "telefono_cuidador", "dni_cuidador",
                "parentesco_cuidador", "vive_con_paciente"} <= names
        assert any(f.validator == "phone_es" for f in fields)
        assert any(f.validator == "dni" for f in fields)
        # Mapeo a columnas reales (inventario 2026-09-08)
        assert targets["parentesco_cuidador"] == "x_relacion_familiar"
        assert targets["telefono_contacto"] == "mobile"
        assert targets["email_contacto"] == "email"
        assert targets["nombre_cuidador"] is None  # sin columna -> solo evidencia

    def test_partner_fill_validates_with_build_dynamic_model(self):
        fields, _ = load_partner_fill_schema()
        Model = build_dynamic_model(fields)
        m = Model(nombre_cuidador="María", parentesco_cuidador="hija")
        assert m.parentesco_cuidador == "hija"
        with pytest.raises(Exception):
            Model(parentesco_cuidador="prima")  # no está en allowed

    def test_cuidum_102(self):
        fields, targets = resolve_schema("cuidum-102")
        assert len(fields) == 102
        assert targets == {}

    def test_unknown_raises(self):
        with pytest.raises(ValueError):
            resolve_schema("no-existe")

    def test_json_path(self, tmp_path):
        j = tmp_path / "s.json"
        j.write_text('{"fields": [{"name": "a", "type": "string"}]}', encoding="utf-8")
        fields, targets = resolve_schema(str(j))
        assert [f.name for f in fields] == ["a"]
        assert targets == {}


class TestCandidatesQuery:
    def test_sql_has_duration_filter_and_dedup(self):
        fields, targets = load_partner_fill_schema()
        sql, params = fetch_candidates_query(fields, targets, min_duration=30, min_chars=100)
        assert "cp.duration >= %(min_dur)s" in sql
        assert "length(cp.description) > %(min_chars)s" in sql
        assert "ROW_NUMBER() OVER (PARTITION BY cp.partner_id" in sql
        assert "WHERE rn = 1" in sql or "c.rn = 1" in sql
        assert "c.x_relacion_familiar IS NULL OR c.x_relacion_familiar = ''" in sql
        assert "c.mobile IS NULL OR c.mobile = ''" in sql
        assert params["min_dur"] == 30 and params["min_chars"] == 100

    def test_sql_includes_target_columns(self):
        fields, targets = load_partner_fill_schema()
        sql, _ = fetch_candidates_query(fields, targets)
        assert "rp.x_relacion_familiar" in sql
        assert "rp.email" in sql
        # los campos sin columna destino NO entran en el filtro
        assert "rp.nombre_cuidador" not in sql

    def test_no_targets_raises(self):
        fields, _ = load_partner_fill_schema()
        with pytest.raises(ValueError):
            fetch_candidates_query(fields, {})


class TestCli:
    def test_mode_schema(self, capsys):
        code = main(["--schema", "partner-fill", "--mode", "schema"])
        out = capsys.readouterr().out
        assert code == 0
        assert "Schema 'partner-fill':" in out
        assert "- nombre_cuidador" in out

    def test_mode_schema_102(self, capsys):
        code = main(["--schema", "cuidum-102", "--mode", "schema"])
        out = capsys.readouterr().out
        assert code == 0
        assert "102 campos" in out