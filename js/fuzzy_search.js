/*
 * Unscharfe Suche über die Transkriptionen (Volltext, Buchsuche, Seite, Register).
 *
 * Zwei Schichten, beide im Browser:
 *
 * 1. Normalisierung. Dieselben Regeln wie scripts/normalize_orthography.py
 *    (NFD, Nasalstrich aufgelöst, Diakritika getilgt, ſ→s, v→u, j→i), dazu
 *    Kleinschreibung und zwei reine Suchfaltungen (ß→ss, y→i). Jeder
 *    normalisierte Buchstabe weiss, aus welcher Stelle des Originals er stammt,
 *    damit ein Treffer im Original markiert werden kann. tests/test_fuzzy_search_js.py
 *    prüft die Schicht gegen die Python-Fassung auf echten Korpuszeilen.
 *
 * 2. Levenshtein-Teilstringsuche (Sellers 1980): das Suchmuster darf irgendwo im
 *    Text mit bis zu k Abweichungen (Ersetzung, Einfügung, Auslassung) stehen.
 *    Die dynamische Programmierung führt den Anfang der besten Ausrichtung mit,
 *    so dass der Treffer als Spanne zurückkommt, nicht nur als Ja/Nein.
 *    Bei k > 0 muss ein Treffer an einem Wortanfang beginnen und darf frei enden
 *    («gott» trifft «gottes», «gotz», «got»), sonst träfe ein kurzes Muster mit
 *    zwei Abweichungen fast jede Zeile. Bei k = 0 bleibt es die alte
 *    Teilstringsuche, nur auf normalisiertem Text.
 *
 * Kein Abhängigkeiten; als Skript im Browser (window.FuzzySearch) und unter Node
 * (require) nutzbar, damit die Tests ohne Browser laufen.
 */
(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  root.FuzzySearch = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  const LETTER = /\p{L}/u;
  const MARK = /\p{M}/u;
  const WORD_CHAR = /[\p{L}\p{N}]/u;
  const NASAL_MARKS = new Set(["̄", "̃"]); // Makron, Tilde
  // Buchstabenklasse der Python-Regeln für «vñ» (auf NFD-Text, also faktisch ASCII).
  const PY_LETTER = /[A-Za-zÄÖÜäöü]/;
  const PY_CARRIER = /[A-Za-z]/;

  // --- Normalisierung ------------------------------------------------------

  // Ein Cluster ist ein Grundbuchstabe mit seinen kombinierenden Zeichen, mit
  // Anfang und Ende im Originaltext. Transkribus schreibt u + U+0366, der Druck
  // ů: nach NFD sind beide derselbe Cluster.
  function clusters(text) {
    const out = [];
    for (let i = 0; i < text.length; ) {
      const cp = text.codePointAt(i);
      const len = cp > 0xffff ? 2 : 1;
      const nfd = text.slice(i, i + len).normalize("NFD");
      const base = String.fromCodePoint(nfd.codePointAt(0));
      const marks = Array.from(nfd.slice(base.length));
      if (MARK.test(base)) {
        // Alleinstehendes kombinierendes Zeichen: gehört zum Buchstaben davor.
        if (out.length) { out[out.length - 1].marks.push(base, ...marks); out[out.length - 1].end = i + len; }
      } else {
        out.push({ start: i, end: i + len, base: base.toLowerCase(), marks });
      }
      i += len;
    }
    return out;
  }

  function lastNfdChar(cluster) {
    if (!cluster) return "";
    return cluster.marks.length ? cluster.marks[cluster.marks.length - 1] : cluster.base;
  }

  // Nasalstrich aufgelöst wie in resolve_nasal_bar(): nach dem Träger, wie er im
  // Korpus belegt ist. Gibt den Ersatz für den Grundbuchstaben zurück.
  function expandNasal(cl, c) {
    const b = cl[c].base;
    const prev = cl[c - 1];
    const next = cl[c + 1];
    const nextBase = next ? next.base : "";
    if (b === "n" && prev && prev.base === "v" && prev.marks.length === 0
        && !PY_LETTER.test(lastNfdChar(cl[c - 2]))) {
      if (nextBase === "d") return "n"; // vn̄d → vnd
      if (!PY_LETTER.test(nextBase)) return "nd"; // vñ als Wort → vnd
    }
    if (b === "n") return "nn";
    if (b === "m") return "mm";
    if (b === "u") return LETTER.test(nextBase) ? "un" : "um";
    return b + "n";
  }

  const FOLD = { "ſ": "s", "v": "u", "j": "i" };
  const SEARCH_FOLD = { "ß": "ss", "y": "i" };

  /**
   * Normalisiert `text`; `map[i]` ist die Stelle im Original, aus der das
   * normalisierte Zeichen i stammt. Whitespace wird zu einem Leerzeichen
   * zusammengezogen; Anfang und Ende bleiben, wie sie sind (Zeilen werden
   * vom Aufrufer getrimmt).
   */
  function normalize(text, opts) {
    const searchFold = !opts || opts.searchFold !== false;
    const cl = clusters(String(text || ""));
    let norm = "";
    const map = [];
    let lastSpace = false;
    for (let c = 0; c < cl.length; c++) {
      const k = cl[c];
      if (/\s/.test(k.base)) {
        if (!lastSpace) { norm += " "; map.push(k.start); }
        lastSpace = true;
        continue;
      }
      lastSpace = false;
      let piece = k.base;
      if (PY_CARRIER.test(piece) && k.marks.some((m) => NASAL_MARKS.has(m))) piece = expandNasal(cl, c);
      let out = "";
      for (const ch of piece) {
        let f = FOLD[ch] || ch;
        if (searchFold && SEARCH_FOLD[f]) f = SEARCH_FOLD[f];
        out += f;
      }
      for (const ch of out) { norm += ch; map.push(k.start); }
    }
    return { norm, map };
  }

  function normalizeText(text, opts) { return normalize(text, opts).norm; }

  // --- Levenshtein-Teilstringsuche ----------------------------------------

  const INF = 1 << 20;

  /**
   * Alle Stellen in `norm`, an denen `pattern` mit höchstens `k` Abweichungen
   * steht, als nicht überlappende Spannen {start, end, dist} in den Koordinaten
   * von `norm`. `anchored`: der Treffer muss an einem Wortanfang beginnen.
   */
  function search(norm, pattern, k, anchored) {
    const m = pattern.length;
    const n = norm.length;
    if (!m || !n) return [];
    let prevD = new Int32Array(m + 1);
    let prevS = new Int32Array(m + 1);
    let curD = new Int32Array(m + 1);
    let curS = new Int32Array(m + 1);
    for (let i = 0; i <= m; i++) { prevD[i] = i; prevS[i] = 0; }
    const cands = [];
    for (let j = 1; j <= n; j++) {
      const tj = norm.charCodeAt(j - 1);
      // Spalte j: Text bis Index j verbraucht; D[0] = 0 heisst «Treffer beginnt bei j».
      const boundary = !anchored || !WORD_CHAR.test(norm[j - 1]);
      curD[0] = boundary ? 0 : INF;
      curS[0] = j;
      for (let i = 1; i <= m; i++) {
        let d = prevD[i - 1] + (pattern.charCodeAt(i - 1) === tj ? 0 : 1);
        let s = prevS[i - 1];
        const del = curD[i - 1] + 1; // Musterzeichen ohne Gegenstück
        if (del < d) { d = del; s = curS[i - 1]; }
        const ins = prevD[i] + 1; // Textzeichen zu viel
        if (ins < d) { d = ins; s = prevS[i]; }
        curD[i] = d;
        curS[i] = s;
      }
      // Ein Treffer beginnt und endet nie mit einem Leerzeichen: «gott» gegen
      // «got » wäre sonst eine Ersetzung t→Leerzeichen und gleich gut wie «got».
      if (curD[m] <= k && curS[m] < j && norm[j - 1] !== " " && norm[curS[m]] !== " ") {
        cands.push({ start: curS[m], end: j, dist: curD[m] });
      }
      const tD = prevD; prevD = curD; curD = tD;
      const tS = prevS; prevS = curS; curS = tS;
    }
    // Von überlappenden Kandidaten bleibt der mit der kleinsten Distanz. Bei
    // Gleichstand: lieber einer, der auf einem Wortzeichen endet («erste
    // schlussred» vor «erste schlussred /»), dann der, dessen Länge dem Muster
    // am nächsten kommt («gott» in «gotz» ist gotz, nicht got), sonst der frühere.
    const out = [];
    let best = null;
    const endsOnWord = (c) => (WORD_CHAR.test(norm[c.end - 1]) ? 0 : 1);
    const offLength = (c) => Math.abs((c.end - c.start) - m);
    const better = (c, b) => c.dist !== b.dist ? c.dist < b.dist
      : endsOnWord(c) !== endsOnWord(b) ? endsOnWord(c) < endsOnWord(b)
      : offLength(c) < offLength(b);
    for (const c of cands) {
      if (best && c.start < best.end) {
        if (better(c, best)) best = c;
      } else {
        if (best) out.push(best);
        best = c;
      }
    }
    if (best) out.push(best);
    return out;
  }

  /** Spannen aus `search` zurück ins Original: [{start, end, dist}] in Originalindizes. */
  function toOriginal(map, matches, originalLength) {
    return matches.map((mt) => {
      const lastOrigin = map[mt.end - 1];
      let e = mt.end;
      while (e < map.length && map[e] === lastOrigin) e++;
      return { start: map[mt.start], end: e < map.length ? map[e] : originalLength, dist: mt.dist };
    });
  }

  // --- Unschärfe -----------------------------------------------------------

  const LEVELS = ["auto", "0", "1", "2", "3", "4", "5"];

  /** Automatische Unschärfe nach Länge des normalisierten Musters. */
  function autoDistance(len) {
    if (len <= 3) return 0;
    if (len <= 5) return 1;
    if (len <= 8) return 2;
    if (len <= 12) return 3;
    return 4;
  }

  /**
   * Wirksame Distanz für ein Muster der Länge `len` bei Einstellung `setting`
   * ("auto" oder eine Zahl). Nie mehr als die Hälfte des Musters: darüber
   * träfe jedes Wort.
   */
  function effectiveDistance(setting, len) {
    const want = setting === "auto" || setting === undefined || setting === null
      ? autoDistance(len)
      : Math.max(0, parseInt(setting, 10) || 0);
    return Math.max(0, Math.min(want, Math.floor((len - 1) / 2)));
  }

  /** Ein vorbereitetes Suchmuster: normalisiert, mit wirksamer Distanz. */
  function compile(query, setting) {
    const norm = normalizeText(query).trim();
    const k = effectiveDistance(setting, norm.length);
    return { raw: String(query || ""), norm, k, anchored: k > 0, setting: setting || "auto" };
  }

  /** Treffer eines kompilierten Musters in `norm`, oder [] . */
  function find(pattern, norm) {
    if (!pattern.norm) return [];
    return search(norm, pattern.norm, pattern.k, pattern.anchored);
  }

  /**
   * Treffer im Originaltext: {spans: [{start,end,dist}], dist} oder null.
   * Für Filter und die Hervorhebung auf der Seite.
   */
  function matchText(text, pattern) {
    const { norm, map } = normalize(text);
    const ms = find(pattern, norm);
    if (!ms.length) return null;
    const spans = toOriginal(map, ms, String(text).length);
    return { spans, dist: Math.min(...spans.map((s) => s.dist)) };
  }

  /** Zeilen einer Transkriptionsseite, vorbereitet für die Suche. */
  function prepareLines(text) {
    return String(text || "").split("\n")
      .map((l) => l.replace(/^#+\s+/, "").trim())
      .filter((l) => l)
      .map((l) => ({ text: l, norm: normalizeText(l) }));
  }

  /**
   * HTML der Zeile mit markierten Spannen. `escape` ist die HTML-Escape-Funktion
   * des Aufrufers; eine Spanne mit dist > 0 erhält zusätzlich `fuzzyClass`.
   */
  function highlight(text, spans, escape, cls, fuzzyClass) {
    let html = "";
    let pos = 0;
    for (const s of spans) {
      if (s.start < pos) continue;
      html += escape(text.slice(pos, s.start));
      const c = s.dist > 0 && fuzzyClass ? `${cls} ${fuzzyClass}` : cls;
      html += `<mark class="${c}">${escape(text.slice(s.start, s.end))}</mark>`;
      pos = s.end;
    }
    return html + escape(text.slice(pos));
  }

  /** Lesbare Beschreibung der Einstellung für die Statuszeile. */
  function describe(pattern) {
    if (!pattern.norm) return "";
    if (pattern.k === 0) return pattern.setting === "auto" ? "genau" : "genau (0 Abweichungen)";
    const n = pattern.k === 1 ? "1 Abweichung" : `${pattern.k} Abweichungen`;
    return pattern.setting === "auto" ? `unscharf, bis ${n} (automatisch)` : `unscharf, bis ${n}`;
  }

  return {
    LEVELS, normalize, normalizeText, search, toOriginal, autoDistance, effectiveDistance,
    compile, find, matchText, prepareLines, highlight, describe,
  };
});
