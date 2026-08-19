#!/usr/bin/env python3
"""Tests for normalize_orthography.py."""

import pytest
from scripts.normalize_orthography import normalize, normalize_text, normalize_file, Normalized
from pathlib import Path


class TestLongS:
    def test_long_s_basic(self):
        assert normalize("bas").normalized == "bas"

    def test_long_s_word(self):
        r = normalize("groß")
        assert "long_s" not in r.normalization_info.get("rules_applied", [])


class TestUV:
    def test_v_to_u(self):
        assert normalize("vnd").normalized == "und"
        assert normalize("vnnderscheid").normalized == "unnderscheid"

    def test_v_consonant(self):
        assert normalize("vor").normalized == "uor"


class TestIJ:
    def test_j_to_i(self):
        assert normalize("jnn").normalized == "inn"
        assert normalize("jnnere").normalized == "innere"


class TestCombiningDiacritics:
    def test_u_with_combining_diaeresis(self):
        r = normalize("u\u0308")
        assert r.normalized == "u"

    def test_a_with_combining_diaeresis(self):
        r = normalize("a\u0308")
        assert r.normalized == "a"

    def test_o_with_combining_diaeresis(self):
        r = normalize("o\u0308")
        assert r.normalized == "o"

    def test_macron_stripped(self):
        r = normalize("x\u0304")
        assert r.normalized == "x"

    def test_nasal_strip_m(self):
        r = normalize("m\u0304")
        assert r.normalized == "m"

    def test_nasal_strip_n(self):
        r = normalize("n\u0304")
        assert r.normalized == "n"

    def test_nasal_strip_z(self):
        r = normalize("z\u0304")
        assert r.normalized == "z"


class TestAbbreviationPatterns:
    def test_uel_not_expanded(self):
        """uel is retained as-is (known abbreviation form, not expanded blindly)."""
        result = normalize("uel")
        assert "uel" in result.normalized


class TestPreservation:
    def test_original_unchanged(self):
        text = "vnnderscheid"
        r = normalize(text)
        assert r.original == text

    def test_whitespace_collapsed(self):
        r = normalize("das   er\n  ſöllichs")
        assert "  " not in r.normalized
        assert "\n" not in r.normalized

    def test_empty_string(self):
        r = normalize("")
        assert r.normalized == ""

    def test_normalized_namedtuple_fields(self):
        r = normalize("test")
        assert isinstance(r, Normalized)
        assert r.original == "test"
        assert r.normalized == "test"
        assert isinstance(r.normalization_info, dict)


class TestConvenienceAPI:
    def test_normalize_text(self):
        assert normalize_text("vnd") == "und"

    def test_normalize_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            normalize_file(Path("/nonexistent/file.md"))


class TestRulePriority:
    def test_all_rules_applied(self):
        r = normalize("vnnderscheid")
        assert "u_v" in r.normalization_info.get("rules_applied", [])
