"""Verbatim span grounding — the zero-tolerance gate for hallucinated values.

Gate 1 of the reliability strategy: a value is only trusted if a literal
quote of it exists in the source text, ideally at the char offsets the LLM
claimed. Case/accent-insensitive comparison is allowed for EXISTENCE, but
returned offsets always point at real characters in the raw text.
"""
import unicodedata
from typing import Any, Optional

_STATUS_OK = "ok"
_STATUS_NOT_FOUND = "not_found"
_STATUS_FAIL = "fail"


def _norm_char(ch: str) -> str:
    n = unicodedata.normalize("NFKD", ch)
    return "".join(c for c in n if not unicodedata.combining(c)).lower()


def _norm(s: str) -> str:
    return "".join(_norm_char(c) for c in s)


def _find_aligned(raw_text: str, needle: str) -> int:
    """Find needle (already normalized) in raw_text, returning a REAL raw index."""
    needle = _norm(needle)
    if not needle:
        return -1
    pairs = []
    for i, ch in enumerate(raw_text):
        n = _norm_char(ch)
        if n:
            pairs.append((i, n))
    norm_str = "".join(p for _, p in pairs)
    idx = norm_str.find(needle)
    if idx == -1:
        return -1
    return pairs[idx][0]


def _find(raw_text: str, needle: str) -> int:
    """Strict find first, then case/accent-insensitive fallback. Returns -1."""
    idx = raw_text.find(needle)
    if idx != -1:
        return idx
    return _find_aligned(raw_text, needle)


def grounding(
    field_name: str,
    value: Any,
    quote: Optional[str],
    start_char: Optional[int],
    end_char: Optional[int],
    raw_text: str,
) -> tuple[str, Optional[int], Optional[int]]:
    """Verifica anclaje de un valor extraído.

    Returns (status, start, end):
      - "ok"        valor anclado a una cita real (offsets válidos)
      - "not_found" value is None — el campo no aparece, no es un fallo
      - "fail"      la cita/valor NO está en el texto o los offsets mienten
    """
    if value is None:
        return _STATUS_NOT_FOUND, None, None

    quote_was_none = quote is None
    quote = (quote or "").strip()

    # 1. Sin cita: intentar anclar el valor directamente
    if quote == "":
        if quote_was_none:
            idx = _find(raw_text, str(value))
            if idx == -1:
                return _STATUS_FAIL, None, None
            return _STATUS_OK, idx, idx + len(str(value))
        # Cita vacía dada por el LLM → señal de valor no anclado → fail (tolerancia cero)
        return _STATUS_FAIL, None, None

    # 2. Con cita: debe existir en el texto (si no, alucinación directa)
    if _find(raw_text, quote) == -1:
        return _STATUS_FAIL, None, None

    # 3. Si el LLM dio offsets, deben cuadrar con la cita (igualdad normalizada)
    if start_char is not None and end_char is not None:
        if 0 <= start_char < end_char <= len(raw_text):
            fragment = raw_text[start_char:end_char]
            if fragment == quote or _norm(fragment) == _norm(quote):
                return _STATUS_OK, start_char, end_char
            return _STATUS_FAIL, start_char, end_char

    # 4. Sin offsets válidos: localizar la cita (índice real alineado)
    idx = raw_text.find(quote)
    if idx == -1:
        idx = _find_aligned(raw_text, quote)
    if idx == -1:
        return _STATUS_FAIL, None, None
    return _STATUS_OK, idx, idx + len(quote)