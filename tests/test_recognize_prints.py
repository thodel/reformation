#!/usr/bin/env python3
"""Tests for print recognition helpers and the Gemini output sanitiser."""
from __future__ import annotations
import json, sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import erara  # noqa: E402
import gemini_client as gc  # noqa: E402
from recognize_prints import split_models, split_sizes  # noqa: E402


class CliParsingTest(unittest.TestCase):
    def test_sizes_split_on_semicolon_not_comma(self):
        # !2000,2000 contains a comma, so comma-splitting would shred it.
        self.assertEqual(split_sizes("!1500,1500;!2500,2500"), ["!1500,1500", "!2500,2500"])

    def test_single_size(self):
        self.assertEqual(split_sizes("full"), ["full"])

    def test_models_split_on_comma(self):
        self.assertEqual(split_models("a,b"), ["a", "b"])

    def test_blank_entries_dropped(self):
        self.assertEqual(split_sizes("full;;"), ["full"])
        self.assertEqual(split_models("a,,b"), ["a", "b"])


class ScaffoldingTest(unittest.TestCase):
    def test_strips_leading_announcement(self):
        self.assertEqual(gc.strip_scaffolding("Hier ist die Transkription:\n\nEcht"), "Echt")

    def test_strips_code_fences(self):
        self.assertEqual(gc.strip_scaffolding("```\nEcht\n```"), "Echt")
        self.assertEqual(gc.strip_scaffolding("```text\nEcht\n```"), "Echt")

    def test_strips_opener_before_announcement(self):
        self.assertEqual(gc.strip_scaffolding("Absolut! Hier folgt der erkannte Text:\nEcht"), "Echt")

    def test_keeps_prose_that_merely_resembles_scaffolding(self):
        prose = "gerne von ihm verstanden habe"
        self.assertEqual(gc.strip_scaffolding(prose), prose)

    def test_keeps_body_text_untouched(self):
        body = "by dem thisch der predicanten\nvill gelerter lutt"
        self.assertEqual(gc.strip_scaffolding(body), body)

    def test_handles_empty_response(self):
        self.assertEqual(gc.strip_scaffolding(""), "")
        self.assertEqual(gc.strip_scaffolding(None), "")


class RetryClassificationTest(unittest.TestCase):
    def test_rate_limit_and_server_errors_are_retryable(self):
        for message in ["429 Too Many Requests", "503 Service Unavailable",
                        "deadline exceeded", "model is overloaded"]:
            self.assertTrue(gc.is_retryable(Exception(message)), message)

    def test_client_errors_are_not_retryable(self):
        for message in ["401 Unauthorized", "invalid api key", "404 model not found"]:
            self.assertFalse(gc.is_retryable(Exception(message)), message)


class ManifestParsingTest(unittest.TestCase):
    def test_extracts_pages_and_builds_image_urls(self):
        manifest = {"sequences": [{"canvases": [
            {"@id": "c1", "label": "1", "images": [
                {"resource": {"service": {"@id": "https://e.example/i3f/v20/111"}}}]},
            {"@id": "c2", "label": "2", "images": [
                {"resource": {"service": {"@id": "https://e.example/i3f/v20/222"}}}]},
        ]}]}
        pages = erara.pages_from_manifest(manifest)
        self.assertEqual([p.page_nr for p in pages], [1, 2])
        self.assertEqual(pages[0].image_url("!1500,1500"),
                         "https://e.example/i3f/v20/111/full/!1500,1500/0/default.jpg")

    def test_canvases_without_an_image_service_are_skipped(self):
        manifest = {"sequences": [{"canvases": [
            {"@id": "c1", "images": []},
            {"@id": "c2", "images": [{"resource": {}}]},
            {"@id": "c3", "images": [{"resource": {"service": {"@id": "https://e/1"}}}]},
        ]}]}
        self.assertEqual(len(erara.pages_from_manifest(manifest)), 1)

    def test_empty_manifest(self):
        self.assertEqual(erara.pages_from_manifest({}), [])

    def test_skipped_witnesses_are_excluded(self):
        import tempfile
        payload = {"witnesses": [{"key": "a", "skip": True}, {"key": "b"}]}
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            json.dump(payload, fh)
            path = Path(fh.name)
        self.assertEqual([w["key"] for w in erara.load_witnesses(path)], ["b"])


if __name__ == "__main__":
    unittest.main(verbosity=2)


class TransientNetworkRetryTest(unittest.TestCase):
    """Failures observed in the 2026-08-19 sample run that must be retried.

    Two of sixteen pro-preview pages died with "RemoteProtocolError: Server
    disconnected" after ~257s. The original token list did not match that, so
    the page was abandoned on the first attempt instead of retried.
    """

    def test_server_disconnect_is_retryable(self):
        self.assertTrue(gc.is_retryable(Exception("RemoteProtocolError: Server disconnected")))

    def test_other_transport_faults_are_retryable(self):
        for message in ["Connection reset by peer", "Connection aborted",
                        "IncompleteRead(0 bytes read)", "Broken pipe"]:
            self.assertTrue(gc.is_retryable(Exception(message)), message)

    def test_auth_and_missing_model_are_still_not_retryable(self):
        # gemini-2.5-pro returns this; retrying it would waste the whole run.
        self.assertFalse(gc.is_retryable(Exception("404 NOT_FOUND model not found")))
        self.assertFalse(gc.is_retryable(Exception("401 Unauthorized")))


class DefaultModelTest(unittest.TestCase):
    def test_default_is_not_the_model_that_404s(self):
        self.assertNotEqual(gc.DEFAULT_MODEL, "gemini-2.5-pro")
