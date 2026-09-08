"""Tests for core.validators — deterministic business validators (Gate 3)."""
import pytest
from datetime import date

from core.schema import FieldSpec
from core.validators import VALIDATORS, validate_field


class TestDni:
    @pytest.mark.parametrize("dni", ["45892147V", "12345678Z", "00000000T", "11111111H"])
    def test_valid_dnis(self, dni):
        assert VALIDATORS["dni"](dni) is True

    @pytest.mark.parametrize("dni", ["45892147K", "45892147L", "1234567A", "123456789A", "ABC", "", "4589214k", "11111111X"])
    def test_invalid_dnis(self, dni):
        assert VALIDATORS["dni"](dni) is False


class TestNie:
    def test_valid_nie(self):
        # X1234567L → 0 1234567 → 1234567 % 23 = 19 → 'L'
        assert VALIDATORS["nie"]("X1234567L") is True

    @pytest.mark.parametrize("nie", ["X1234567K", "Y1234567B", "Z1234567Z", "X1234567", "12345678Z", ""])
    def test_invalid_nies(self, nie):
        assert VALIDATORS["nie"](nie) is False


class TestPhoneEs:
    @pytest.mark.parametrize("phone", ["34612345678", "612345678", "+34 612 345 678", "912345678"])
    def test_valid_phones(self, phone):
        assert VALIDATORS["phone_es"](phone) is True

    @pytest.mark.parametrize("phone", ["123", "abc", "", "9999999999999", "34612"])
    def test_invalid_phones(self, phone):
        assert VALIDATORS["phone_es"](phone) is False


class TestEmail:
    @pytest.mark.parametrize("email", ["a@b.com", "maria.garcia@cuidum.com", "x@y.io"])
    def test_valid_emails(self, email):
        assert VALIDATORS["email"](email) is True

    @pytest.mark.parametrize("email", ["a@b", "@b.com", "a b@c.com", "", "sin-arroba.com"])
    def test_invalid_emails(self, email):
        assert VALIDATORS["email"](email) is False


class TestDate:
    def test_valid_date(self):
        assert VALIDATORS["date"]("15/08/2026", {"fmt": "%d/%m/%Y"}) is True

    def test_impossible_date_fails(self):
        # 30 de febrero no existe
        assert VALIDATORS["date"]("30/02/2024", {"fmt": "%d/%m/%Y"}) is False

    @pytest.mark.parametrize("raw", ["31/02/2026", "2026-13-01", "abc", ""])
    def test_invalid_dates(self, raw):
        assert VALIDATORS["date"](raw, {"fmt": "%d/%m/%Y"}) is False

    def test_default_fmt_iso(self):
        assert VALIDATORS["date"]("2026-09-08") is True


class TestValidateField:
    def _spec(self, validator, config=None):
        return FieldSpec(name="campo", type="string", validator=validator,
                         validator_config=config)

    def test_ok_single_validator(self):
        ok, passed = validate_field(self._spec("dni"), "45892147V")
        assert ok is True and passed == ["dni"]

    def test_fail_dni(self):
        ok, passed = validate_field(self._spec("dni"), "45892147K")
        assert ok is False and passed == []

    def test_no_validator_passes(self):
        ok, passed = validate_field(FieldSpec(name="c", type="string"), "cualquier cosa")
        assert ok is True and passed == []

    def test_none_value_skips(self):
        ok, passed = validate_field(self._spec("dni"), None)
        assert ok is True and passed == []

    def test_unknown_validator_raises(self):
        with pytest.raises(KeyError):
            validate_field(self._spec("no_existe"), "x")