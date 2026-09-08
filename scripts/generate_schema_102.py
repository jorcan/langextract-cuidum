"""Genera adapters/cuidum/schema_102.py y data/examples/cuidum-102.json
desde el modelo legacy src.models.CallEntities (paridad por construcción).
"""
import json
import re
import sys
from pathlib import Path
from typing import Literal, get_origin, get_args

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.models import CallEntities, EXTRACTION_EXAMPLES  # noqa: E402

TYPE_MAP = {bool: "bool", int: "int", float: "float"}


def to_fieldspec(name, info, desc=None):
    ann = info.annotation
    origin = get_origin(ann)
    desc = desc or (info.description or "")
    if origin is Literal:
        ftype, allowed = "literal", list(get_args(ann))
    elif ann in TYPE_MAP:
        ftype, allowed = TYPE_MAP[ann], None
    elif ann is str:
        ftype, allowed = "string", None
    elif ann is list or origin is list:
        ftype, allowed = "list", None
    elif ann is type(None) or str(ann).startswith("typing.Optional"):
        inner = get_args(ann)[0]
        return to_fieldspec(name, type("I", (), {"annotation": inner, "description": desc})(), desc)
    else:
        ftype, allowed = "string", None  # fallback conservador

    spec = {"name": name, "type": ftype, "description": desc}
    if allowed:
        spec["allowed"] = allowed
    return spec


fields = []
for name, info in CallEntities.model_fields.items():
    fields.append(to_fieldspec(name, info))

# Escribir schema_102.py
out = []
out.append('"""Schema Cuidum 102 entidades (generado desde src.models.CallEntities).')
out.append("")
out.append("NO editar a mano: regenerar con scripts/generate_schema_102.py")
out.append('"""')
out.append("from core.schema import FieldSpec, build_dynamic_model")
out.append("")
out.append(f"FIELDS_102: list[FieldSpec] = [")
for f in fields:
    parts = [f"FieldSpec(name={f['name']!r}, type={f['type']!r}"]
    if f.get("description"):
        parts.append(f"description={f['description']!r}")
    if f.get("allowed"):
        parts.append(f"allowed={f['allowed']!r}")
    parts.append(")")
    out.append("    " + ", ".join(parts) + ",")
out.append("]")
out.append("")
out.append('CallEntities102 = build_dynamic_model(FIELDS_102, "CallEntities102")')
out.append("")

Path("/home/ubuntu/repos/langextract-cuidum/adapters/cuidum/schema_102.py").write_text(
    "\n".join(out), encoding="utf-8")

# Escribir ejemplos en data/examples/cuidum-102.json
examples = []
for ex in EXTRACTION_EXAMPLES:
    examples.append({"text": ex["text"], "extractions": ex["entities"]})
ex_path = Path("/home/ubuntu/repos/langextract-cuidum/data/examples/cuidum-102.json")
ex_path.parent.mkdir(parents=True, exist_ok=True)
ex_path.write_text(json.dumps(examples, ensure_ascii=False, indent=2), encoding="utf-8")

print(f"FIELDS_102: {len(fields)} campos")
from collections import Counter
print("por tipo:", dict(Counter(f["type"] for f in fields)))
print("ejemplos:", len(examples))
print("escrito:", "adapters/cuidum/schema_102.py, data/examples/cuidum-102.json")