"""Meaningful boundary checks for the evidence audit, using synthetic facts."""
import importlib.util
from pathlib import Path
import unittest

SCRIPT = Path(__file__).parents[1] / "scripts" / "audit_evidence.py"
spec = importlib.util.spec_from_file_location("audit_evidence", SCRIPT)
audit_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit_module)


def fact(**changes):
    row = {
        "id": "mine_stock", "publisher": "Original survey", "origin": "survey_a",
        "event_key": "jm_mine_stock_20261106", "url": "https://example.org/report",
        "claim": "Synthetic mine inventory increased", "axis": "inventory",
        "relevance": "direct", "role": "driver", "evidence_type": "fact",
        "access": "public_full", "published_at": "2026-11-06T10:00:00+08:00",
        "observed_at": "2026-11-06", "max_age_days": 14,
    }
    row.update(changes)
    return row


def bundle(*rows):
    return {"commodity": "JM", "as_of": "2026-11-08T16:00:00+08:00",
            "timezone": "Asia/Shanghai", "required_axes": ["supply", "demand", "inventory", "pricing"],
            "evidence": list(rows)}


class EvidenceAuditTests(unittest.TestCase):
    def test_fresh_direct_fact_is_kept_without_generating_a_direction(self):
        result = audit_module.audit_bundle(bundle(fact()))
        self.assertEqual(result["eligible_ids"], ["mine_stock"])
        self.assertEqual(result["status"], "manual_synthesis_required")
        self.assertNotIn("direction", result)
        self.assertEqual(result["missing_axes"], ["supply", "demand", "pricing"])

    def test_future_publication_is_excluded_even_for_an_older_observation(self):
        result = audit_module.audit_bundle(bundle(fact(published_at="2026-11-09T08:00:00+08:00")))
        self.assertEqual(result["eligible_ids"], [])
        self.assertIn("published_after_cutoff", result["rows"][0]["reasons"])

    def test_date_only_publication_is_available_next_local_day(self):
        data = bundle(fact(published_at="2026-11-08"))
        result = audit_module.audit_bundle(data)
        self.assertEqual(result["eligible_ids"], [])
        data["as_of"] = "2026-11-09T00:00:00+08:00"
        result = audit_module.audit_bundle(data)
        self.assertEqual(result["eligible_ids"], ["mine_stock"])
        self.assertIn("date_only_publication_conservative", result["rows"][0]["warnings"])

    def test_recent_article_does_not_refresh_an_old_statistic(self):
        result = audit_module.audit_bundle(bundle(fact(observed_at="2025-11-07")))
        self.assertIn("stale_observation", result["rows"][0]["reasons"])
        self.assertEqual(result["eligible_ids"], [])

    def test_proxy_only_bundle_cannot_unlock_a_whole_product_direction(self):
        result = audit_module.audit_bundle(bundle(fact(relevance="proxy", axis="demand")))
        self.assertEqual(result["status"], "insufficient_current_direct_evidence")
        self.assertEqual(result["direct_driver_count"], 0)

    def test_rumor_and_search_snippet_cannot_be_admitted_as_facts(self):
        rows = [fact(evidence_type="rumor"), fact(id="snippet", event_key="other", access="search_snippet")]
        result = audit_module.audit_bundle(bundle(*rows))
        self.assertEqual(result["eligible_ids"], [])
        self.assertIn("not_verified_fact", result["rows"][0]["reasons"])
        self.assertIn("not_publicly_read", result["rows"][1]["reasons"])

    def test_readable_public_excerpt_is_retained_with_a_scope_warning(self):
        result = audit_module.audit_bundle(bundle(fact(access="public_excerpt")))
        self.assertEqual(result["eligible_ids"], ["mine_stock"])
        self.assertIn("public_excerpt_only", result["rows"][0]["warnings"])

    def test_attributed_reprints_of_one_fact_do_not_add_votes(self):
        result = audit_module.audit_bundle(bundle(fact(), fact(id="reprint", publisher="Reprinter", url="https://example.net/copy")))
        self.assertEqual(result["eligible_ids"], ["mine_stock"])
        self.assertEqual(result["rows"][1]["duplicate_of"], "mine_stock")
        self.assertEqual(result["direct_origins"], ["survey_a"])

    def test_different_samples_are_preserved_instead_of_forced_to_agree(self):
        other = fact(id="other", origin="survey_b", event_key="jm_stock_sample_b", claim="Synthetic inventory decreased")
        result = audit_module.audit_bundle(bundle(fact(), other))
        self.assertEqual(result["eligible_ids"], ["mine_stock", "other"])
        self.assertEqual(result["direct_origins"], ["survey_a", "survey_b"])

    def test_later_vendor_availability_blocks_an_earlier_publication(self):
        result = audit_module.audit_bundle(bundle(fact(available_at="2026-11-09T09:00:00+08:00")))
        self.assertIn("available_after_cutoff", result["rows"][0]["reasons"])

    def test_unknown_or_timezone_free_publication_is_not_silently_localized(self):
        for value in (None, "2026-11-06T10:00:00"):
            with self.subTest(value=value):
                result = audit_module.audit_bundle(bundle(fact(published_at=value)))
                self.assertIn("unknown_or_invalid_publication", result["rows"][0]["reasons"])

    def test_future_observation_cannot_be_reported_as_realized_data(self):
        result = audit_module.audit_bundle(bundle(fact(observed_at="2026-11-09")))
        self.assertIn("future_observation", result["rows"][0]["reasons"])

    def test_same_day_observation_after_exact_publication_is_excluded(self):
        row = fact(published_at="2026-11-06T08:00:00+08:00", observed_at="2026-11-06T23:00:00+08:00")
        result = audit_module.audit_bundle(bundle(row))
        self.assertIn("observation_after_publication", result["rows"][0]["reasons"])

    def test_date_only_overseas_source_uses_its_own_local_day(self):
        row = fact(published_at="2026-11-08", observed_at="2026-11-08", source_timezone="America/New_York")
        data = bundle(row)
        data["as_of"] = "2026-11-09T01:00:00+08:00"
        result = audit_module.audit_bundle(data)
        self.assertEqual(result["eligible_ids"], [])
        data["as_of"] = "2026-11-09T13:00:00+08:00"
        self.assertEqual(audit_module.audit_bundle(data)["eligible_ids"], ["mine_stock"])

    def test_malformed_axis_list_is_a_validation_error(self):
        data = bundle(fact())
        data["required_axes"] = [{}]
        with self.assertRaises(ValueError):
            audit_module.audit_bundle(data)

    def test_duplicate_ids_and_boolean_freshness_are_schema_errors(self):
        for data in (bundle(fact(), fact()), bundle(fact(max_age_days=True))):
            with self.subTest(data=data):
                with self.assertRaises(ValueError):
                    audit_module.audit_bundle(data)

    def test_structural_context_cannot_unlock_a_current_direction(self):
        result = audit_module.audit_bundle(bundle(fact(role="context", max_age_days=366)))
        self.assertEqual(result["status"], "insufficient_current_direct_evidence")

    def test_historical_date_filter_is_not_a_pit_certificate(self):
        data = bundle(fact())
        data["mode"] = "historical"
        result = audit_module.audit_bundle(data)
        self.assertIs(result["historical_pit_certified"], False)


if __name__ == "__main__":
    unittest.main()
