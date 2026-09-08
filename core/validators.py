"""Deterministic business validators — Gate 3 of the zero-tolerance strategy.

Registry consulted by name from FieldSpec.validator. Every validator takes
(value, config=None) and returns bool. validate_field() applies the spec's
validator and returns (ok, passed_list).
"""
import re
from datetime import datetime
from typing import Any, Callable, Optional

import phonenumbers

TABLA_DNI = "TRWAGMYFPDXBNJZSQVHLCKE"


def _validate_dni(dni: str, config: Optional[dict] = None) -> bool:
    m = re.fullmatch(r"(\d{8})([A-Z])", (dni or "").strip().upper())
    if not m:
        return False
    numero, letra = int(m.group(1)), m.group(2)
    return TABLA_DNI[numero % 23] == letra


def _validate_nie(nie: str, config: Optional[dict] = None) -> bool:
    m = re.fullmatch(r"([XYZ])(\d{7})([A-Z])", (nie or "").strip().upper())
    if not m:
        return False
    prefijo = {"X": "0", "Y": "1", "Z": "2"}[m.group(1)]
    numero = int(prefijo + m.group(2))
    return TABLA_DNI[numero % 23] == m.group(3)


def _validate_phone_es(phone: str, config: Optional[dict] = None) -> bool:
    try:
        p = phonenumbers.parse(phone, "ES")
    except phonenumbers.NumberParseException:
        return False
    return phonenumbers.is_valid_number(p)


_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _validate_email(email: str, config: Optional[dict] = None) -> bool:
    return bool(_EMAIL_RE.match((email or "").strip()))


def _validate_date(raw: str, config: Optional[dict] = None) -> bool:
    fmt = (config or {}).get("fmt", "%Y-%m-%d")
    try:
        datetime.strptime((raw or "").strip(), fmt)  # 30/02/2024 -> ValueError
        return True
    except ValueError:
        return False


VALIDATORS: dict[str, Callable[[Any, Optional[dict]], bool]] = {
    "dni": _validate_dni,
    "nie": _validate_nie,
    "phone_es": _validate_phone_es,
    "email": _validate_email,
    "date": _validate_date,
}


def validate_field(spec: Any, value: Any) -> tuple[bool, list[str]]:
    """Apply the spec's validator. Returns (ok, [validator_names_passed]).

    - No validator declared -> ok (grounding is still required upstream).
    - value is None -> ok (absent data is not a validation failure).
    """
    if value is None or not spec.validator:
        return True, []
    validator = VALIDATORS[spec.validator]  # KeyError si nombre desconocido
    if validator(value, spec.validator_config):
        return True, [spec.validator]
    return False, []