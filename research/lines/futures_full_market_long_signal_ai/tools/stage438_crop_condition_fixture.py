"""Small synthetic boundaries; never opens an archived USDA body."""
import importlib.util
from pathlib import Path
import unittest

MODULE = Path(__file__).with_name("stage438_crop_condition_extract.py")


def table(crop="Corn", week="August 25, 2024", values="4 8 21 52 15",
          previous="4 8 19 54 15", coverage=True):
    lines = [f"{crop} Condition - Selected States: Week Ending {week}"]
    if coverage:
        lines.append("[These 18 States planted 92% of the 2023 corn acreage]")
    lines.extend([
        "------------------------------------------------------------",
        "State : Very poor : Poor : Fair : Good : Excellent",
        "------------------------------------------------------------",
        f"18 States ......: {values}",
        f"Previous week ..: {previous}",
        "Previous year ..: 4 8 26 49 13",
        "------------------------------------------------------------",
        "- Represents zero.",
    ])
    return "\n".join(lines)


def report(release="August 26, 2024", **kwargs):
    return (f"Crop Progress\n\nReleased {release}, by the National Agricultural Statistics Service\n\n"
            + table(**kwargs)
            + "\n\nRevision Policy: Estimates are released after 4:00 pm ET.\n"
              "These estimates are subject to revision the following week.\n")


class CropConditionBoundaries(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not MODULE.exists():
            cls.parser = None
            return
        spec = importlib.util.spec_from_file_location("stage438_extract", MODULE)
        cls.parser = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.parser)

    def parse(self, text, release="2024-08-26"):
        self.assertIsNotNone(self.parser, "bounded extractor implementation is missing")
        return self.parser.parse_report(text, release, {"path": "synthetic", "sha256": "0" * 64, "bytes": 1})

    def test_original_five_values_and_coverage_missing_are_not_imputed(self):
        # A parser that drops the first category, uses a state row, or requires coverage must fail.
        row = self.parse(report(coverage=False))["rows"][0]
        self.assertEqual(row["current"]["status"], "known")
        self.assertEqual(row["current"]["five_categories"], [4, 8, 21, 52, 15])
        self.assertEqual(row["current"]["good_plus_excellent"], 67)
        self.assertEqual(row["current"]["line_number"], 9)
        self.assertEqual(row["coverage"]["status"], "unknown:not_printed")
        zero = self.parse(report(values="- 8 21 52 19"))["rows"][0]
        self.assertEqual(zero["current"]["five_categories"], [0, 8, 21, 52, 19])
        undefined = self.parse(report(values="- 8 21 52 19").replace("- Represents zero.", ""))["rows"][0]
        self.assertIsNone(undefined["current"]["good_plus_excellent"])

    def test_missing_table_and_bad_five_values_preserve_unknown_rows(self):
        # Dropping an absent crop or coercing NA/bad sums into a value must fail.
        parsed = self.parse(report())
        self.assertEqual(len(parsed["rows"]), 2)
        self.assertIn("condition_table_missing", parsed["rows"][1]["unknown_reasons"])
        for values in ("4 8 (NA) 52 15", "4 8 20 52 15", "4 8 21 52 15 0"):
            row = self.parse(report(values=values))["rows"][0]
            self.assertEqual(row["current"]["status"], "unknown")
            self.assertIsNone(row["current"]["good_plus_excellent"])

    def test_release_date_or_duplicate_title_conflict_does_not_become_known(self):
        # Falling back to metadata or accepting one of two tables must fail.
        row = self.parse(report(), "2024-08-27")["rows"][0]
        self.assertIn("body_metadata_release_disagreement", row["unknown_reasons"])
        duplicate = self.parse(report() + "\n" + table())["rows"][0]
        self.assertIn("condition_table_not_unique", duplicate["unknown_reasons"])
        self.assertEqual(len(duplicate["table_candidates"]), 2)

    def test_adjacent_change_uses_previous_original_and_exposes_revision(self):
        # Using same-report previous week would produce -2, rather than -3.
        first = self.parse(report(release="August 19, 2024", week="August 18, 2024",
                                  values="4 8 18 54 16"), "2024-08-19")
        second = self.parse(report(), "2024-08-26")
        self.parser.link_adjacent([first, second])
        row = second["rows"][0]
        self.assertEqual(row["adjacent_change"]["value_pp"], -3)
        self.assertEqual(row["revision_diagnostic"]["printed_previous_minus_original_GE_pp"], -1)
        self.assertTrue(row["revision_diagnostic"]["five_categories_differ"])

    def test_missing_immediate_report_non7_and_cross_year_never_bridge(self):
        # Skipping a missing report or treating seven days across years as eligible must fail.
        first = self.parse(report(release="August 19, 2024", week="August 18, 2024"), "2024-08-19")
        missing = self.parse("Released August 26, 2024, by NASS\n", "2024-08-26")
        last = self.parse(report(release="September 3, 2024", week="September 1, 2024"), "2024-09-03")
        self.parser.link_adjacent([first, missing, last])
        self.assertIsNone(last["rows"][0]["adjacent_change"]["value_pp"])
        self.assertEqual(last["rows"][0]["adjacent_change"]["previous_metadata_release_date"], "2024-08-26")
        self.parser.link_adjacent([first, last])
        self.assertIn("reference_gap_not_7_days", last["rows"][0]["adjacent_change"]["unknown_reasons"])
        dec = self.parse(report(release="December 26, 2023", week="December 25, 2023"), "2023-12-26")
        jan = self.parse(report(release="January 2, 2024", week="January 1, 2024"), "2024-01-02")
        self.parser.link_adjacent([dec, jan])
        self.assertIn("reference_year_boundary", jan["rows"][0]["adjacent_change"]["unknown_reasons"])

    def test_same_release_versions_do_not_choose_an_arbitrary_predecessor(self):
        # Sorting tied releases by input order or path would create a fabricated change.
        first = self.parse(report(release="August 19, 2024", week="August 18, 2024"), "2024-08-19")
        first_version2 = self.parse(report(release="August 19, 2024", week="August 18, 2024",
                                           values="4 8 18 54 16"), "2024-08-19")
        following = self.parse(report(), "2024-08-26")
        self.parser.link_adjacent([first, first_version2, following])
        self.assertIn("ambiguous_current_release_order", first_version2["rows"][0]["adjacent_change"]["unknown_reasons"])
        self.assertIn("ambiguous_previous_release_order", following["rows"][0]["adjacent_change"]["unknown_reasons"])
        self.assertIsNone(following["rows"][0]["adjacent_change"]["value_pp"])
        self.assertIsNone(following["rows"][0]["adjacent_change"]["previous_source"])

    def test_printed_previous_date_must_bind_and_same_GE_can_hide_revision(self):
        # Ignoring a printed date mismatch, or comparing only GE, would miss these two breaks.
        first = self.parse(report(release="August 19, 2024", week="August 18, 2024",
                                  values="4 8 18 54 16"), "2024-08-19")
        same_ge = self.parse(report(previous="3 9 18 54 16"), "2024-08-26")
        self.parser.link_adjacent([first, same_ge])
        self.assertTrue(same_ge["rows"][0]["revision_diagnostic"]["five_categories_differ"])
        self.assertEqual(same_ge["rows"][0]["revision_diagnostic"]["printed_previous_minus_original_GE_pp"], 0)
        wrong_date = self.parse(report().replace("Previous week ..:", "Previous week (August 17, 2024) ..:"))
        self.parser.link_adjacent([first, wrong_date])
        self.assertEqual(wrong_date["rows"][0]["printed_previous_week"]["explicit_reference_date"], "2024-08-17")
        self.assertIn("printed_previous_date_disagrees_with_previous_original_reference", wrong_date["rows"][0]["revision_diagnostic"]["unknown_reasons"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
