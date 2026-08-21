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
        assert r.normalized == "xn"   # #21: expanded, not stripped

    def test_nasal_strip_m(self):
        r = normalize("m\u0304")
        assert r.normalized == "mm"   # #21: m + bar -> mm (kom̃en -> kommen)

    def test_nasal_strip_n(self):
        r = normalize("n\u0304")
        assert r.normalized == "nn"   # #21: n + bar -> nn (dañ -> dann)

    def test_nasal_strip_z(self):
        r = normalize("z\u0304")
        assert r.normalized == "zn"   # #21: expanded, not stripped


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


class TestUnicodeEquivalence:
    """The corpus spells the same letter two ways.

    Transkribus writes u + U+0366 (combining latin small letter o); druck_1528
    writes precomposed U+016F. Both must normalise to the same string, or the
    print collation reports thousands of variants that are pure encoding noise.
    """

    def test_combining_and_precomposed_agree(self):
        pairs = [
            ("z" + "u" + "ͦ", "zů"),            # zuͦ / zů
            ("geh" + "o" + "ͤ" + "rend", "gehörend"),  # gehoͤrend / gehörend
            ("f" + "u" + "ͣ" + "r", "fûr"),            # fuͣr / fûr
        ]
        for combining, precomposed in pairs:
            assert normalize(combining).normalized == normalize(precomposed).normalized

    def test_precomposed_diacritics_are_folded(self):
        # 6,654 of these appear in the corpus and were previously untouched.
        assert normalize("ü").normalized == "u"
        assert normalize("å").normalized == "a"
        assert normalize("ö").normalized == "o"
        assert normalize("ä").normalized == "a"

    def test_precomposed_macron_and_tilde_are_reached(self):
        # #21: the nasal bar is resolved, so an abbreviation and its written-out
        # form agree instead of differing by the letter that was abbreviated.
        assert normalize("ſchadē").normalized == "schaden"
        assert normalize("gemeñ").normalized == "gemenn"
        assert normalize("ẽ").normalized == "en"

    def test_output_carries_no_combining_marks(self):
        import unicodedata
        for sample in ["zuͦ", "gehoͤrend", "ſchadē", "gemeñ", "fuͣrgeben"]:
            out = normalize(sample).normalized
            assert not any(unicodedata.combining(c) for c in out), sample

    def test_original_is_preserved_unchanged(self):
        source = "z" + "u" + "ͦ"
        assert normalize(source).original == source


class TestNasalBarExpansion:
    """#21: the nasal bar is resolved, not dropped.

    Dropping it made an abbreviation disagree with its written-out form -
    "schadē" against "schaden" - which is a variant the edition never had.
    Resolution follows the carrier, as attested in the corpus.
    """

    def test_abbreviation_matches_the_written_form(self):
        for short, full in [("schadē", "schaden"), ("habē", "haben"),
                            ("dañ", "dann"), ("kom̃en", "kommen"),
                            ("Chriſtū", "Christum"), ("zũ", "zum"), ("võ", "von")]:
            assert normalize(short).normalized.lower() == normalize(full).normalized.lower(), short

    def test_vnd_is_not_doubled(self):
        """vñ is the period's ampersand: it stands for vnd, never vnn.

        At 350 occurrences it is the most common abbreviated form in the
        corpus, so a generic n-doubling rule would corrupt it more than any
        other word.
        """
        assert normalize("vñ").normalized.lower() == normalize("vnd").normalized.lower()
        assert normalize("vn̄").normalized.lower() == normalize("vnd").normalized.lower()
        assert "nn" not in normalize("vñ").normalized.lower()

    def test_u_takes_m_finally_and_n_before_a_consonant(self):
        assert normalize("Chriſtū").normalized.lower().endswith("um")
        assert normalize("meinūg").normalized.lower() == normalize("meinung").normalized.lower()

    def test_text_without_a_nasal_bar_is_untouched(self):
        # rules_applied is absent when nothing fired, so read it defensively.
        result = normalize("gemeine kilch")
        assert result.normalized == "gemeine kilch"
        assert "nasal_expanded" not in result.normalization_info.get("rules_applied", [])

    def test_the_ring_still_folds_after_expansion(self):
        # The expansion must not recompose: a precomposed ů would then survive
        # the fold that only looks for combining marks.
        assert normalize("nůn̄dte").normalized.lower() == "nunndte"
