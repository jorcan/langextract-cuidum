"""Declarative value coercion driven by FieldSpec.type.

Replaces the legacy hardcoded field-name lists (_coerce_values in src/)
with type-driven rules: any new schema is coerced correctly by declaring
its fields, with zero code changes.
"""
import json
import re
import unicodedata
from typing import Any

from core.schema import FieldSpec

_NULLISH = {"", "none", "null", "ninguno", "no_mencionado", "no mencionado", "n/a", "na"}


def _strip_accents(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if not unicodedata.combining(c))


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", _strip_accents(s.strip().lower()))


def coerce_value(spec: FieldSpec, value: Any) -> Any:
    """Coerce a raw LLM value according to spec.type. Returns None on garbage."""
    if value is None:
        return None

    t = spec.type

    if t == "string":
        if isinstance(value, bool):
            return "si" if value else "no"
        return value if isinstance(value, str) else str(value)

    if t == "bool":
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)) and value in (0, 1):
            return value == 1
        if isinstance(value, str):
            v = _norm(value)
            if v in ("true", "si", "sí", "1"):
                return True
            if v in ("false", "no", "0"):
                return False
        return None

    if t == "int":
        if isinstance(value, str):
            s = value.strip()
            # Solo enteros (o "7.0"): fracciones reales ("7.9") → None, sin truncado silencioso
            if re.fullmatch(r"-?\d+\.0+", s):
                s = s.split(".")[0]
            if not re.fullmatch(r"-?\d+", s):
                return None
            value = s
        try:
            return int(float(value))
        except (ValueError, TypeError):
            return None

    if t == "float":
        if isinstance(value, str):
            value = value.strip().replace(",", ".")
        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    if t == "list":
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            v = value.strip()
            if _norm(v) in _NULLISH:
                return None
            if v.startswith("[") and v.endswith("]"):
                try:
                    parsed = json.loads(v.replace("'", '"'))
                    return parsed if isinstance(parsed, list) else []
                except (json.JSONDecodeError, TypeError):
                    return []
            return []
        return None

    if t == "literal":
        if not spec.allowed:
            return None
        v = _norm(value)
        if v in spec.allowed:
            return v
        # Prefijo-match (id. del skill): "neutral_informativo" → "neutral"
        for allowed in spec.allowed:
            if v.startswith(allowed) or (len(v) >= 3 and allowed.startswith(v)):
                return allowed
        return None

    return None  # pragma: no cover


def coerce_all(fields: list[FieldSpec], data: dict[str, Any]) -> dict[str, Any]:
    """Coerce every known field in data; unknown keys pass through untouched."""
    by_name = {f.name: f for f in fields}
    out = dict(data)
    for name, spec in by_name.items():
        if name in out:
            out[name] = coerce_value(spec, out[name])
    return out