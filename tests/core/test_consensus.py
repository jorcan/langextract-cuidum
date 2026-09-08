"""Tests for core.consensus — dual-model consensus (Gate 2)."""
import pytest

from core.schema import FieldSpec
from core.consensus import evaluate_consensus, normalize

CRITICAL = ["dni_cuidador", "telefono_cuidador"]


def _ev(field, value, quote=None, status="ok"):
    from core.extractor import Evidence
    return Evidence(field_name=field, value=value, verbatim_quote=quote, status=status)


def _docs(a_pairs, b_pairs):
    """Build two ExtractionDocs from list of (field, value, quote, status) tuples."""
    from core.extractor import ExtractionDoc
    return (ExtractionDoc(extracted_fields=[_ev(*p) for p in a_pairs]),
            ExtractionDoc(extracted_fields=[_ev(*p) for p in b_pairs]))


class TestNormalize:
    @pytest.mark.parametrize("raw,exp", [
        ("  HOLA ", "hola"),
        ("Cónyuge", "conyuge"),
        ("María José", "maria jose"),
        (None, None),
        (123, "123"),
        (True, "true"),
        ("Mi   hija", "mi hija"),
    ])
    def test_normalize(self, raw, exp):
        assert normalize(raw) == exp


class TestEvaluateConsensus:
    def test_identical_ok(self):
        da, db = _docs(
            [("nombre", "María", "Soy María"), ("telefono_cuidador", "34612345678", "34612345678")],
            [("nombre", "María", "Soy María"), ("telefono_cuidador", "34612345678", "34612345678")],
        )
        verdict, payload, mismatched = evaluate_consensus(da, db, CRITICAL)
        assert verdict == "auto_ok"
        assert payload["nombre"] == "María"
        assert mismatched == []

    def test_both_none_not_found(self):
        da, db = _docs(
            [("nombre", None), ("telefono_cuidador", None)],
            [("nombre", None), ("telefono_cuidador", None)],
        )
        verdict, payload, _ = evaluate_consensus(da, db, CRITICAL)
        assert verdict == "not_found"
        assert payload["nombre"] is None

    def test_discrepancy_critical_review(self):
        da, db = _docs(
            [("telefono_cuidador", "34612345678", "34612345678")],
            [("telefono_cuidador", "34699999999", "34699999999")],
        )
        verdict, payload, mismatched = evaluate_consensus(da, db, CRITICAL)
        assert verdict == "review"
        assert "telefono_cuidador" in mismatched
        assert isinstance(payload["telefono_cuidador"], dict)  # {a, b}

    def test_a_value_b_none_review(self):
        da, db = _docs(
            [("nombre", "María", "Soy María")],
            [("nombre", None)],
        )
        verdict, _, mismatched = evaluate_consensus(da, db, CRITICAL)
        assert verdict == "review"
        assert "nombre" in mismatched

    def test_b_grounding_fail_review(self):
        da, db = _docs(
            [("telefono_cuidador", "34612345678", "34612345678")],
            [("telefono_cuidador", "34612345678", "34612345678", "grounding_fail")],
        )
        verdict, _, mismatched = evaluate_consensus(da, db, CRITICAL)
        assert verdict == "review"

    def test_single_model_critical_to_review(self):
        da = _docs([("telefono_cuidador", "34612345678", "34612345678")], [])[0]
        verdict, payload, _ = evaluate_consensus(da, None, CRITICAL)
        assert verdict == "review"
        # El crítico conserva el valor propuesto (a) para revisión humana
        assert payload["telefono_cuidador"]["a"] == "34612345678"

    def test_single_model_noncritical_ok(self):
        doc = _docs([("nombre", "María", "Soy María")], [])[0]
        verdict, payload, _ = evaluate_consensus(doc, None, CRITICAL)
        # Honesto: un solo modelo = verificable, pero NO es doble consenso
        assert verdict == "single_model"
        assert payload["nombre"] == "María"

    def test_different_field_sets_review(self):
        da, db = _docs(
            [("nombre", "María", "Soy María"), ("apellido", "García", "García")],
            [("nombre", "María", "Soy María")],
        )
        verdict, _, mismatched = evaluate_consensus(da, db, CRITICAL)
        assert verdict == "review"
        assert "apellido" in mismatched

    def test_quote_kept_from_a(self):
        da, db = _docs(
            [("nombre", "María", "Soy María", "ok")],
            [("nombre", "María", "soy maria", "ok")],
        )
        verdict, payload, _ = evaluate_consensus(da, db, CRITICAL)
        assert verdict == "auto_ok"
        assert payload["nombre"] == "María"


class TestRunDual:
    def test_runs_both_providers(self):
        from core.consensus import run_dual

        class FakeProviderSeq:
            """Devuelve una respuesta distinta por llamada (A y B)."""
            def __init__(self, raws):
                self.raws = raws
                self.calls = 0

            def infer(self, prompts):
                raw = self.raws[self.calls % len(self.raws)]
                self.calls += 1
                return [[type("O", (), {"output": raw})()]]

        import json
        ok = json.dumps({"nombre": "María", "__quote__": {"nombre": "Soy María"}})
        provider_a = FakeProviderSeq([ok])
        provider_b = FakeProviderSeq([ok])
        fields = [FieldSpec(name="nombre", type="string")]
        verdict, doc_a, doc_b = run_dual("Soy María y vivo en Madrid.", fields,
                                         provider_a=provider_a, provider_b=provider_b,
                                         critical_fields=[])
        assert provider_a.calls == 1 and provider_b.calls == 1
        assert verdict == "auto_ok"
        assert doc_a.ok_fields and doc_b.ok_fields