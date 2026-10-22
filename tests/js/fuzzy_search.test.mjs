// node --test tests/js   (tests/test_fuzzy_search_js.py ruft das aus pytest auf)
import test from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const F = require("../../js/fuzzy_search.js");

const esc = (s) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

test("Normalisierung folgt normalize_orthography.py", () => {
  const n = (s) => F.normalizeText(s, { searchFold: false });
  assert.equal(n("vnd"), "und");
  assert.equal(n("Jnn"), "inn");
  assert.equal(n("baſs"), "bass");
  assert.equal(n("goͤtlich"), "gotlich");
  assert.equal(n("zuͦ"), "zu");
  assert.equal(n("zů"), "zu"); // vorkomponiert wie im Druck
  assert.equal(n("vñ"), "und"); // Nasalstrich als Wort: vnd, nicht vnn
  assert.equal(n("vn̄d"), "und");
  assert.equal(n("dañ"), "dann");
  assert.equal(n("kom̃en"), "kommen");
  assert.equal(n("Chriſtū"), "christum"); // u + Strich am Wortende -> um
  assert.equal(n("meinūg"), "meinung"); // u + Strich vor Konsonant -> un
  assert.equal(n("habē"), "haben");
  assert.equal(n("a   b\tc"), "a b c");
});

test("Suchfaltungen nur in der Suchschicht", () => {
  assert.equal(F.normalizeText("Schlußred zweyung"), "schlussred zweiung");
  assert.equal(F.normalizeText("Schlußred zweyung", { searchFold: false }), "schlußred zweyung");
});

test("Positionskarte zeigt auf den Ursprung im Original", () => {
  const t = "zuͦ Schlußred";
  const { norm, map } = F.normalize(t);
  assert.equal(norm, "zu schlussred");
  // ß liefert zwei s, beide zeigen auf das ß
  const i = norm.indexOf("ss");
  assert.equal(t[map[i]], "ß");
  assert.equal(map[i], map[i + 1]);
  const spans = F.toOriginal(map, [{ start: 0, end: 2, dist: 0 }], t.length);
  assert.equal(t.slice(spans[0].start, spans[0].end), "zuͦ"); // das kombinierende Zeichen gehört dazu
});

test("Exakte Suche (k=0) ist Teilstringsuche auf normalisiertem Text", () => {
  const p = F.compile("nad", "0");
  const r = F.matchText("Gnad vnnd fried", p);
  assert.deepEqual(r.spans.map((s) => [s.start, s.end, s.dist]), [[1, 4, 0]]);
  assert.equal(F.matchText("Gnad vnnd fried", F.compile("und", "0")), null); // «und» steht nicht in «unnd»
  assert.equal(F.matchText("Gnad vnnd fried", F.compile("und", "1")).dist, 1); // mit einer Abweichung schon
});

test("Unscharfe Suche beginnt am Wortanfang und endet frei", () => {
  const t = "got gottes gotz spott";
  const p = F.compile("gott", "1");
  const r = F.matchText(t, p);
  const words = r.spans.map((s) => t.slice(s.start, s.end));
  assert.deepEqual(words, ["got", "gott", "gotz"]); // spott: kein Wortanfang
  assert.deepEqual(r.spans.map((s) => s.dist), [1, 0, 1]);
});

test("Die kleinere Distanz schlägt den längeren Treffer", () => {
  const t = "gottes";
  const r = F.matchText(t, F.compile("got", "1"));
  assert.deepEqual(r.spans.map((s) => [t.slice(s.start, s.end), s.dist]), [["got", 0]]);
});

test("Abweichungen: Ersetzung, Einfügung, Auslassung", () => {
  const p = F.compile("disputation", "2");
  for (const w of ["disputacion", "disputatio", "dispuotation", "Disputationn"]) {
    const r = F.matchText(`die ${w} zuͦ bern`, p);
    assert.ok(r, w);
    assert.ok(r.dist <= 2, `${w}: ${r && r.dist}`);
  }
  assert.equal(F.matchText("die deputation zu bern", F.compile("disputation", "1")), null);
});

test("Mehrwortmuster über Leerzeichen hinweg", () => {
  const t = "Die erste Schlußred / vnd derselben gruͤnd";
  const r = F.matchText(t, F.compile("ersten schlussreden", "auto"));
  assert.ok(r);
  assert.equal(t.slice(r.spans[0].start, r.spans[0].end), "erste Schlußred");
});

test("Wirksame Distanz: automatisch nach Länge, nie mehr als die halbe Länge", () => {
  assert.equal(F.effectiveDistance("auto", 3), 0);
  assert.equal(F.effectiveDistance("auto", 4), 1);
  assert.equal(F.effectiveDistance("auto", 8), 2);
  assert.equal(F.effectiveDistance("auto", 11), 3);
  assert.equal(F.effectiveDistance("auto", 14), 4);
  assert.equal(F.effectiveDistance("5", 14), 5);
  assert.equal(F.effectiveDistance("5", 4), 1); // Kappe
  assert.equal(F.effectiveDistance("3", 2), 0);
  assert.equal(F.compile("ab", "5").k, 0);
});

test("Hervorhebung escaped das Original und kennzeichnet unscharfe Treffer", () => {
  const t = "a <b> gotz";
  const r = F.matchText(t, F.compile("gott", "1"));
  const html = F.highlight(t, r.spans, esc, "hl", "fz");
  assert.equal(html, 'a &lt;b&gt; <mark class="hl fz">gotz</mark>');
  const exact = F.matchText("gott", F.compile("gott", "1"));
  assert.equal(F.highlight("gott", exact.spans, esc, "hl", "fz"), '<mark class="hl">gott</mark>');
});

test("prepareLines lässt Überschrift und Leerzeilen weg", () => {
  const lines = F.prepareLines("# Seite 20\n\ndent\n  Die erste Schlußred  \n");
  assert.deepEqual(lines.map((l) => l.text), ["Seite 20", "dent", "Die erste Schlußred"]);
  assert.equal(lines[2].norm, "die erste schlussred");
});

test("describe nennt die wirksame Einstellung", () => {
  assert.equal(F.describe(F.compile("got", "auto")), "genau");
  assert.equal(F.describe(F.compile("gott", "auto")), "unscharf, bis 1 Abweichung (automatisch)");
  assert.equal(F.describe(F.compile("disputation", "2")), "unscharf, bis 2 Abweichungen");
});
