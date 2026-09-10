"""Regression: literal fields must tolerate non-string LLM output (int/bool codes)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from core.schema import FieldSpec
from core.coerce import coerce_value


def test_literal_accepts_int_code():
    spec = FieldSpec(name="nivel_formativo", type="literal", allowed=["00", "10", "20", "30"])
    assert coerce_value(spec, 20) == "20"
    assert coerce_value(spec, "20") == "20"


def test_literal_accepts_bool_for_01_code():
    spec = FieldSpec(name="x_cuidador_estrella", type="literal", allowed=["0", "1"])
    assert coerce_value(spec, True) == "1"
    assert coerce_value(spec, False) == "0"


def test_literal_rejects_unrelated_number():
    spec = FieldSpec(name="nivel_formativo", type="literal", allowed=["00", "10", "20", "30"])
    assert coerce_value(spec, 99) is None