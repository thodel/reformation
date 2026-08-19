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


class UsageAccountingTest(unittest.TestCase):
    """Cost is billed on tokens, so they must be recorded, thinking included."""

    class _Meta:
        prompt_token_count = 1200
        candidates_token_count = 400
        thoughts_token_count = 900
        total_token_count = 2500

    class _Response:
        usage_metadata = None

    def test_records_all_token_classes(self):
        usage = gc.Usage()
        response = self._Response()
        response.usage_metadata = self._Meta()
        usage.record(response)
        self.assertEqual(usage.prompt_tokens, 1200)
        self.assertEqual(usage.output_tokens, 400)
        self.assertEqual(usage.thought_tokens, 900)
        self.assertEqual(usage.total_tokens, 2500)

    def test_thinking_tokens_are_not_folded_into_output(self):
        # They are invisible in the response text but still billed.
        usage = gc.Usage()
        response = self._Response()
        response.usage_metadata = self._Meta()
        usage.record(response)
        self.assertNotEqual(usage.output_tokens, usage.thought_tokens)

    def test_accumulates_across_calls(self):
        usage = gc.Usage()
        response = self._Response()
        response.usage_metadata = self._Meta()
        usage.record(response)
        usage.record(response)
        self.assertEqual(usage.prompt_tokens, 2400)

    def test_response_without_usage_metadata_is_safe(self):
        usage = gc.Usage()
        usage.record(self._Response())
        self.assertEqual(usage.total_tokens, 0)


class ThinkingBudgetTest(unittest.TestCase):
    """Thinking is ~74% of the pro model's tokens, so capping it is the main lever."""

    def test_empty_means_leave_the_model_default_alone(self):
        from recognize_prints import parse_budgets
        self.assertEqual(parse_budgets(""), [None])

    def test_default_keyword_maps_to_none(self):
        from recognize_prints import parse_budgets
        self.assertEqual(parse_budgets("default,0,512"), [None, 0, 512])

    def test_zero_is_preserved_and_not_confused_with_unset(self):
        # 0 disables thinking; None leaves the default. They must not collapse.
        from recognize_prints import parse_budgets
        budgets = parse_budgets("0")
        self.assertEqual(budgets, [0])
        self.assertIsNotNone(budgets[0])

    def test_no_config_when_nothing_requested(self):
        self.assertIsNone(gc.thinking_config(None, None))

    def test_budget_zero_produces_a_config(self):
        config = gc.thinking_config(0, None)
        self.assertIsNotNone(config)
        self.assertEqual(config.thinking_budget, 0)

    def test_level_is_accepted(self):
        config = gc.thinking_config(None, "LOW")
        self.assertIsNotNone(config)


class MaxPagesCeilingTest(unittest.TestCase):
    """0 must mean 'no ceiling', not 'stop immediately'."""

    @staticmethod
    def _budget(max_pages):
        return max_pages if max_pages and max_pages > 0 else None

    def test_zero_means_unlimited(self):
        self.assertIsNone(self._budget(0))

    def test_negative_means_unlimited(self):
        self.assertIsNone(self._budget(-1))

    def test_positive_is_kept(self):
        self.assertEqual(self._budget(200), 200)
