"""The TEI export must stay valid TEI, and must keep saying what it is.

The schema check is the point of this file: a hand-checked "looks like TEI"
export is worth little to the repositories and corpus tools the format exists
to reach. tei_all.rng is fetched once and cached, because a test that silently
skips when the network is down is a test that reports success for an export
nobody validated - so a missing cache is a skip with a visible reason, never a
pass.

The first run of this suite found five real errors that eyeballing had missed:
<idno> after <imprint> (it must precede it), and @ref on <person> (TEI has no
such attribute there - the authority link is an <idno>).
"""

from __future__ import annotations

import os
import subprocess
import sys
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TEI_DIR = ROOT / "docs" / "tei"
SCHEMA_URL = "https://tei-c.org/release/xml/tei/custom/schema/relaxng/tei_all.rng"
SCHEMA_CACHE = Path(os.environ.get("TEI_SCHEMA_CACHE",
                                   ROOT / ".cache" / "tei_all.rng"))

TEI_NS = "http://www.tei-c.org/ns/1.0"

lxml = pytest.importorskip("lxml.etree", reason="lxml wird für die TEI-Validierung benötigt")


def exported_files() -> list[Path]:
    return sorted(TEI_DIR.glob("*.xml"))


@pytest.fixture(scope="session")
def schema():
    if not SCHEMA_CACHE.exists():
        SCHEMA_CACHE.parent.mkdir(parents=True, exist_ok=True)
        try:
            urllib.request.urlretrieve(SCHEMA_URL, SCHEMA_CACHE)
        except Exception as exc:  # noqa: BLE001 - offline is a skip, not a pass
            pytest.skip(f"tei_all.rng nicht abrufbar und nicht im Cache: {exc}")
    return lxml.RelaxNG(lxml.parse(str(SCHEMA_CACHE)))


def test_export_runs(tmp_path):
    """The exporter itself must work; a stale docs/tei/ would hide a breakage."""
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "export_tei.py"),
         "--witnesses", "a_v_1444_cyro", "--skip-apparatus"],
        capture_output=True, text=True, cwd=ROOT)
    assert result.returncode == 0, result.stderr
    assert (TEI_DIR / "a_v_1444_cyro.xml").exists()


@pytest.mark.skipif(not exported_files(), reason="docs/tei/ ist leer")
@pytest.mark.parametrize("path", exported_files(), ids=lambda p: p.name)
def test_valid_tei_p5(path, schema):
    doc = lxml.parse(str(path))
    assert schema.validate(doc), (
        f"{path.name} ist kein gültiges TEI P5: "
        + "; ".join(f"Zeile {e.line}: {e.message}" for e in list(schema.error_log)[:3]))


@pytest.mark.skipif(not exported_files(), reason="docs/tei/ ist leer")
@pytest.mark.parametrize("path", exported_files(), ids=lambda p: p.name)
def test_states_that_the_text_is_not_edited(path):
    """The caveat has to travel with the file.

    A TEI document is made to be harvested away from the website, and the
    website is where every other "maschinell erkannt, nicht ediert" notice
    lives. If it is not in the header, the next reader has no way to know.
    """
    text = path.read_text(encoding="utf-8")
    assert "nicht ediert" in text, f"{path.name} nennt den Erkennungsvorbehalt nicht"


@pytest.mark.skipif(not exported_files(), reason="docs/tei/ ist leer")
@pytest.mark.parametrize("path", exported_files(), ids=lambda p: p.name)
def test_states_rights_and_holder(path):
    text = path.read_text(encoding="utf-8")
    assert "publicdomain/mark/1.0" in text, f"{path.name} nennt die Rechteangabe nicht"


def test_witness_documents_carry_sigil_and_pages():
    witness = TEI_DIR / "druck_1528.xml"
    if not witness.exists():
        pytest.skip("Export noch nicht erzeugt")
    doc = lxml.parse(str(witness))
    root = doc.getroot()
    assert root.get("{http://www.w3.org/XML/1998/namespace}id") == "D1"
    pages = doc.findall(f".//{{{TEI_NS}}}pb")
    assert len(pages) > 400, f"nur {len(pages)} Seiten im Basiszeugen"
    # Page numbers must be the edition's own, so a citation from the website
    # and a reference into the TEI point at the same page.
    assert pages[0].get("n") == "1"


def test_register_links_to_hls():
    register = TEI_DIR / "register.xml"
    if not register.exists():
        pytest.skip("Export noch nicht erzeugt")
    doc = lxml.parse(str(register))
    idnos = [e.text for e in doc.findall(f".//{{{TEI_NS}}}idno")
             if e.get("type") == "HLS"]
    # Only a minority of the register is identified against HLS - 13 of 107
    # when this was written. The test guards that the linking survives the
    # export at all, not a coverage level the data does not have.
    assert len(idnos) >= 10, f"nur {len(idnos)} HLS-Verknüpfungen"
    assert all(i and i.startswith("https://hls-dhs-dss.ch/") for i in idnos)
