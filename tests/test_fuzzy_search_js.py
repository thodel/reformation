#!/usr/bin/env python3
"""Tests for js/fuzzy_search.js, the fuzzy search in the viewer.

Two parts. The Node tests in tests/js/ cover the matcher itself. The cross-check
here feeds real corpus lines through both normalisers and requires the JavaScript
port to agree with scripts/normalize_orthography.py, so that a rule changed on
one side fails here instead of silently making the search disagree with the
collation. Both parts need node on PATH (GitHub's runners have it); without it
they are skipped, not passed.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from scripts.normalize_orthography import normalize_text

ROOT = Path(__file__).resolve().parents[1]
NODE = shutil.which("node")

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")

# Deterministic sample: every 40th line of three witnesses with different
# conventions (Transkribus combining marks, precomposed print, later print).
SAMPLE_DIRS = [
    "data/disputation/a_v_1447_schlussredaktion/transcriptions",
    "data/disputation/druck_1528/transcriptions",
    "data/prints/druck_1608_zuerich/transcriptions",
]


def test_node_suite_passes():
    files = sorted(str(p) for p in (ROOT / "tests" / "js").glob("*.test.mjs"))
    assert files, "no Node test files found"
    result = subprocess.run(
        [NODE, "--test", *files],
        capture_output=True, text=True, cwd=ROOT,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def _sample_lines(every: int = 40, per_dir: int = 150) -> list[str]:
    lines: list[str] = []
    for rel in SAMPLE_DIRS:
        taken = 0
        for path in sorted((ROOT / rel).glob("page_*.md")):
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                lines.append(line)
                if len(lines) % every == 0:
                    taken += 1
            if taken >= per_dir:
                break
    return lines[::every]


def _js_normalize(lines: list[str]) -> list[str]:
    script = (
        "const F=require(process.argv[1]);let s='';"
        "process.stdin.on('data',d=>s+=d).on('end',()=>{"
        "const out=JSON.parse(s).map(l=>F.normalizeText(l,{searchFold:false}));"
        "process.stdout.write(JSON.stringify(out));});"
    )
    result = subprocess.run(
        [NODE, "-e", script, str(ROOT / "js" / "fuzzy_search.js")],
        input=json.dumps(lines), capture_output=True, text=True, check=True,
    )
    return json.loads(result.stdout)


def test_js_normalisation_matches_python_on_corpus_lines():
    lines = _sample_lines()
    assert len(lines) > 200, "sample too small to mean anything"
    js = _js_normalize(lines)
    expected = [normalize_text(line.lower()) for line in lines]
    mismatches = [
        (line, got, want) for line, got, want in zip(lines, js, expected) if got != want
    ]
    assert not mismatches, "\n".join(
        f"{line!r}\n  js: {got!r}\n  py: {want!r}" for line, got, want in mismatches[:10]
    )


def test_js_normalisation_matches_python_on_edge_cases():
    cases = [
        "vñ", "vn̄d", "dañ", "kom̃en", "Chriſtū", "meinūg", "habē", "võ", "zů", "zuͦ",
        "goͤtlich", "Jnn", "nůn̄dte", "x̄", "a  b", "ü ö ä", "/ Virgel /", "",
    ]
    js = _js_normalize(cases)
    for case, got in zip(cases, js):
        assert got == normalize_text(case.lower()), case
