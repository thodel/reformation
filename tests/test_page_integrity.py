#!/usr/bin/env python3
"""Static checks on index.html for faults the unit tests cannot see.

Three defects reached the published site during this work. Every one passed
`node --check` and the whole unit suite, because each produced syntactically
valid JavaScript and valid HTML; only loading the page in a browser found them:

  * A range-based edit deleted the DOMContentLoaded block, so both page inputs
    and both Enter handlers stopped working while the arrows still did.
  * An edit added a call to highlightDisputationTab without the function, so
    cold-loading any disputation URL threw a ReferenceError.
  * Concordance links were nested inside an anchor, which HTML forbids; the
    parser hoisted them out and every link silently vanished.

These check for that shape of fault directly. They are not a substitute for
loading the page, but they are cheap and they run on every push.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "index.html"


def page() -> str:
    return HTML.read_text(encoding="utf-8")


def inline_script() -> str:
    blocks = re.findall(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", page(), re.S)
    return max(blocks, key=len) if blocks else ""


def code_only(script: str) -> str:
    """Script with comments and string bodies blanked out.

    German prose in a comment ends up looking like a call - "unsicher (0.72)"
    reads as a call to `unsicher` - so the scan has to see code only.
    """
    script = re.sub(r"/\*.*?\*/", " ", script, flags=re.S)
    script = re.sub(r"(?m)^\s*//.*$", " ", script)
    script = re.sub(r"(?<![:\w])//[^\n]*", " ", script)
    script = re.sub(r"`(?:[^`\\]|\\.)*`", "``", script)
    script = re.sub(r"'(?:[^'\\\n]|\\.)*'", "''", script)
    script = re.sub(r'"(?:[^"\\\n]|\\.)*"', '""', script)
    return script


# Globals the page legitimately calls without defining them here.
KNOWN_GLOBALS = {
    "OpenSeadragon", "fetch", "setTimeout", "clearTimeout", "setInterval",
    "parseInt", "parseFloat", "isNaN", "encodeURIComponent", "decodeURIComponent",
    "JSON", "Math", "Object", "Array", "String", "Number", "Boolean", "Date",
    "Promise", "Map", "Set", "RegExp", "Error", "TypeError", "console", "window",
    "document", "location", "history", "navigator", "URL", "AbortController",
    "KeyboardEvent", "Event", "CustomEvent", "requestAnimationFrame", "alert",
    "structuredClone", "queueMicrotask", "TextDecoder", "Intl", "sendPrompt",
}


class UndefinedCallTest(unittest.TestCase):
    """A call to a function that does not exist is valid syntax and fatal at runtime."""

    def test_every_called_function_is_defined(self):
        script = code_only(inline_script())
        defined = set(re.findall(r"function\s+([A-Za-z_$][\w$]*)\s*\(", script))
        defined |= set(re.findall(r"(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?\(", script))
        defined |= set(re.findall(r"(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?function", script))
        defined |= set(re.findall(r"(?:const|let|var)\s+([A-Za-z_$][\w$]*)", script))

        keywords = {"if", "for", "while", "switch", "catch", "return", "function",
                    "async", "await", "typeof", "new", "delete", "void", "case",
                    "do", "else", "try", "throw", "in", "of", "instanceof"}
        called = {n for n in re.findall(r"(?<![.\w$])([a-z][A-Za-z0-9_$]{3,})\s*\(", script)
                  if n not in keywords}
        # Calls written into onclick attributes are just as fatal.
        for attr in re.findall(r'on\w+="([^"]+)"', page()):
            called |= set(re.findall(r"(?<![.\w$])([a-z][A-Za-z0-9_$]{3,})\s*\(", attr))

        missing = sorted(called - defined - KNOWN_GLOBALS)
        self.assertEqual(missing, [], f"called but never defined: {missing}")


class NestedAnchorTest(unittest.TestCase):
    """HTML forbids an anchor inside an anchor; the parser drops the inner one."""

    def test_no_anchor_is_built_inside_another_anchor(self):
        script = inline_script()
        # Template literals that open an <a and close </a> containing a second <a
        for block in re.findall(r"`([^`]*<a\b[^`]*)`", script, re.S):
            opens = len(re.findall(r"<a\b", block))
            closes = len(re.findall(r"</a>", block))
            if opens >= 2 and closes >= 1:
                # Two anchors in one literal is only safe if they are siblings.
                first_close = block.find("</a>")
                second_open = block.find("<a", block.find("<a") + 1)
                self.assertGreater(
                    first_close, -1,
                    f"template opens two anchors without closing the first: {block[:120]}")
                self.assertLess(
                    first_close, second_open,
                    f"anchor nested inside another anchor: {block[:120]}")


class ListenerRegistrationTest(unittest.TestCase):
    """The inputs are wired in one block; deleting it breaks them silently."""

    def test_page_inputs_have_handlers(self):
        script = inline_script()
        for element_id, handler in [
            ("disputation-page-input", "goToDisputationPage"),
            ("page-input", "goToPredigtenPage"),
        ]:
            self.assertIn(element_id, script, element_id)
            self.assertIn(handler, script, handler)
            # the id must be fetched and the handler attached in the same region
            idx = script.find(element_id)
            region = script[idx: idx + 600]
            self.assertIn("addEventListener", region, f"{element_id} has no listener attached")
            self.assertIn(handler, region, f"{element_id} is not wired to {handler}")

    def test_enter_triggers_the_searches(self):
        script = inline_script()
        for handler in ("triggerBookSearch", "triggerGlobalSearch"):
            self.assertIn(handler, script)


class ElementReferenceTest(unittest.TestCase):
    """An id fetched in script but absent from the markup is a dead branch."""

    def test_ids_used_by_script_exist_in_the_markup(self):
        html, script = page(), inline_script()
        ids_in_markup = set(re.findall(r'id="([^"]+)"', html))
        used = set(re.findall(r'getElementById\("([^"]+)"\)', script))
        used |= set(re.findall(r"getElementById\('([^']+)'\)", script))
        # Ids built at runtime with a template are out of scope for this check.
        missing = sorted(i for i in used - ids_in_markup if "${" not in i)
        self.assertEqual(missing, [], f"script reads ids absent from the page: {missing}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
