"""Four source-schema fixtures; synthetic values do not certify SGX prices."""
import unittest

from stage526_sgx_month_source import normalize_report


SECTION = "SGX TSI IRON ORE 62% DERIVATIVES"


def page(rows, date="Wednesday, January 09, 2019", extra=""):
    return (
        f"<p>Statistics<br>( As at {date}, 8pm SG Time )</p>"
        f"<table><tr><th>{SECTION}</th><th>SWAPS / FUTURES PRICES</th></tr>"
        "<tr><th>Contract Month</th><th>DSP (US$)</th><th>Prev DSP (US$)</th></tr>"
        + rows + "</table>" + extra
    ).encode()


def normalized(body, requested="2019-01-09"):
    return normalize_report(body, requested, "synthetic-sha", "metadata-not-first-publish")


class SourceFixtures(unittest.TestCase):
    def test_exact_section_all_months_only_without_grade_or_aggregate_leakage(self):
        # A wrong table selector or period filter would leak a different grade/aggregate.
        body = page(
            "<tr><td>Jan-19</td><td>71.10</td><td>70.00</td></tr>"
            "<tr><td>Feb-19</td><td>72.20</td><td>71.00</td></tr>"
            "<tr><td>Jan-20</td><td>74.30</td><td>73.00</td></tr>"
            "<tr><td>Q1 19</td><td>999</td><td>998</td></tr>"
            "<tr><td>Cal 20</td><td>997</td><td>996</td></tr>",
            extra="<table><tr><th>SGX MB IRON ORE 58% DERIVATIVES</th></tr>"
                  "<tr><td>Feb-19</td><td>555</td><td>554</td></tr></table>",
        )
        result = normalized(body)
        self.assertEqual(result["date_status"], "ok")
        self.assertEqual([r["contract_month_literal"] for r in result["rows"]],
                         ["Jan-19", "Feb-19", "Jan-20"])
        self.assertEqual([r["contract_yyyy_mm"] for r in result["rows"]],
                         ["2019-01", "2019-02", "2020-01"])
        self.assertEqual([r["dsp_raw"] for r in result["rows"]], ["71.10", "72.20", "74.30"])
        self.assertNotIn("symbol", result["rows"][0])

    def test_as_at_date_mismatch_is_separate_and_eight_pm_is_not_seventeen_thirty(self):
        # Ignoring date mismatch or hardcoding a later-era 17:30 clock would fail.
        body = page("<tr><td>Feb-19</td><td>72</td><td>71</td></tr>",
                    date="Thursday, January 10, 2019")
        result = normalized(body)
        self.assertEqual(result["date_status"], "source_date_mismatch")
        row = result["rows"][0]
        self.assertEqual(row["source_header_date"], "2019-01-10")
        self.assertEqual(row["source_as_at_time_reconstructed_if_explicit"],
                         "2019-01-10T20:00:00+08:00")
        self.assertEqual(row["http_last_modified_metadata_not_first_publish"],
                         "metadata-not-first-publish")

    def test_missing_nonfinite_invalid_and_true_zero_preserve_raw_without_imputation(self):
        # Coercing dash/NaN to zero or dropping raw strings would hide source uncertainty.
        body = page("<tr><td>Jan-19</td><td>-</td><td>1,000.00</td></tr>"
                    "<tr><td>Feb-19</td><td>NaN</td><td>inf</td></tr>"
                    "<tr><td>Mar-19</td><td>0</td><td>bad</td></tr>")
        rows = normalized(body)["rows"]
        self.assertEqual([r["dsp_numeric_if_finite"] for r in rows], [None, None, 0.0])
        self.assertEqual([r["prev_dsp_numeric_if_finite"] for r in rows], [1000.0, None, None])
        self.assertEqual([r["dsp_raw"] for r in rows], ["-", "NaN", "0"])
        self.assertEqual([r["value_status"] for r in rows],
                         ["dsp=missing;prev=finite", "dsp=nonfinite;prev=nonfinite",
                          "dsp=finite;prev=invalid"])

    def test_duplicate_months_remain_visible_and_fail_closed_in_date_status(self):
        # Silently merging or picking one of conflicting monthly rows would fail.
        body = page("<tr><td>Feb-19</td><td>72</td><td>71</td></tr>"
                    "<tr><td>Feb-19</td><td>73</td><td>71</td></tr>")
        result = normalized(body)
        self.assertEqual(result["date_status"], "duplicate_month_rows")
        self.assertEqual([r["dsp_raw"] for r in result["rows"]], ["72", "73"])
        self.assertEqual(result["duplicate_months"], ["Feb-19"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
