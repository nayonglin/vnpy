import contextlib
import csv
from datetime import date, timedelta
import io
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from run_weekly_portfolio import run


class WeeklyReversalTest(unittest.TestCase):
    def replay(self, *, enabled=True, mirror=False, prior_bullish=True, missing_exit=False,
               one_price=False, two_close_entry=None, four_up_case=False, block_four_up=False,
               slope_case=False, ma10_20_only=False, long_only=False,
               block_week_range_overlap=False):
        product, symbol, epoch = "cu.SHFE", "cu1509.SHFE", "SHFE.CU.201509"
        candles = [
            (111, 112, 109, 110), (109, 110, 104, 105), (104, 106, 99, 100),
            (100 if prior_bullish else 104, 105, 99, 103), (103, 113, 102, 112),
            (111, 115, 109, 113), (114, 118, 113, 116), (116, 120, 115, 119),
            (119, 122, 117, 121), (121, 125, 120, 124),
        ]
        if one_price:
            candles[5] = (113, 113, 113, 113)
        options = {}
        if two_close_entry is not None:
            candles[0] = (111, 112, 99, 102)
            options["two_close_entry"] = two_close_entry
        if four_up_case:
            candles[3] = (100, 115, 99, 103)
            candles[4] = (103, 115, 102, 112)
            candles[8] = (119, 122, 117, 119)
            candles.extend([(124, 127, 123, 126), (126, 129, 125, 128)])
        if block_four_up:
            options["block_four_up"] = True
        prefix_weeks = 0
        if slope_case:
            prefix = [(120, 121, 119, 120)] * 15 + [(109, 110, 108, 109)]
            prefix_weeks = len(prefix)
            candles = prefix + candles
        if ma10_20_only:
            options["ma10_20_only"] = True
        if long_only:
            options["long_only"] = True
            if mirror:
                candles.extend([(124, 125, 120, 121), (121, 122, 117, 118), (118, 119, 116, 117)])
            else:
                candles.extend([(124, 127, 123, 126), (126, 127, 115, 116), (116, 120, 115, 119),
                                (119, 126, 118, 125), (125, 127, 124, 126)])
        start = date(2015, 1, 9)
        dates = [(start + timedelta(weeks=i)).isoformat() for i in range(len(candles))]
        weeks = [[day] for day in dates]
        if missing_exit:
            weeks[5].insert(0, (date.fromisoformat(dates[5]) - timedelta(days=2)).isoformat())
        days = [day for week in weeks for day in week]
        week_index = {day: i for i, week in enumerate(weeks) for day in week}
        rows = {}
        for day, (opening, high, low, close) in zip(dates, candles):
            if mirror:
                opening, high, low, close = 220 - opening, 220 - low, 220 - high, 220 - close
            rows[day, symbol] = SimpleNamespace(
                vt_symbol=symbol, contract_epoch_id=epoch, contract_yyyymm="201509",
                open=opening, high=high, low=low, close=close,
            )
        epochs = {(day, epoch): bar for (day, _), bar in rows.items()}
        mains = {(day, product): symbol for day in days}
        specs = {
            "sizes": {symbol: 5}, "slippages": {symbol: 1}, "rates": {symbol: 0},
            "margin_ratios": {symbol: 0.1},
        }
        market = ([product], days, weeks, week_index, rows, epochs, mains, specs, {})
        with tempfile.TemporaryDirectory() as tmp, patch("run_weekly_portfolio.load_market", return_value=market):
            output = Path(tmp) / "replay"
            with contextlib.redirect_stdout(io.StringIO()):
                run(output, ma_filter=slope_case, week_body_filter=True, reverse_after_stop=enabled,
                    block_week_range_overlap=block_week_range_overlap, **options)
            with (output / "fills.csv").open() as source:
                fills = list(csv.DictReader(source))
        return dates[prefix_weeks:], fills

    def test_stop_executes_before_one_lot_reversal_for_both_directions(self):
        for mirror in (False, True):
            with self.subTest(mirror=mirror):
                dates, fills = self.replay(mirror=mirror)
                legs = [f for f in fills if f["date"] == dates[5]]
                self.assertEqual([f["reason"] for f in legs], ["weekly_stop", "entry"])
                self.assertEqual([int(f["side"]) for f in legs], [-1 if mirror else 1] * 2)
                self.assertEqual([f["signal_day"] for f in legs], [dates[4]] * 2)
                self.assertEqual(legs[1]["volume"], "1")
                self.assertEqual(float(legs[1]["stop"]), 118 if mirror else 102)
                self.assertNotEqual(legs[0]["cycle"], legs[1]["cycle"])

    def test_disabled_or_opposite_body_rejected_only_closes(self):
        for options in ({"enabled": False}, {"prior_bullish": False}):
            with self.subTest(options=options):
                dates, fills = self.replay(**options)
                self.assertEqual([f["reason"] for f in fills if f["date"] == dates[5]], ["weekly_stop"])

    def test_exact_half_range_overlap_blocks_reversal_but_keeps_stop(self):
        for mirror in (False, True):
            with self.subTest(mirror=mirror):
                dates, fills = self.replay(mirror=mirror, block_week_range_overlap=True)
                self.assertEqual([f["reason"] for f in fills if f["date"] == dates[3]], ["entry"])
                self.assertEqual([f["reason"] for f in fills if f["date"] == dates[5]], ["weekly_stop"])

    def test_missing_first_exit_open_drops_linked_entry_but_keeps_stop_pending(self):
        dates, fills = self.replay(missing_exit=True)
        self.assertEqual([f["reason"] for f in fills if f["date"] == dates[5]], ["weekly_stop"])

    def test_one_price_exit_preserves_close_without_reversal_fill(self):
        dates, fills = self.replay(one_price=True)
        self.assertEqual([f["reason"] for f in fills if f["date"] == dates[5]], ["weekly_stop"])

    def test_four_up_blocks_new_long_but_preserves_stop_and_short_reversal(self):
        for block, mirror, four_up, close_index, expected in (
            (False, False, True, 7, ["weekly_stop", "entry"]),
            (True, False, True, 7, ["weekly_stop"]),
            (True, True, True, 7, ["weekly_stop", "entry"]),
            (True, False, False, 5, ["weekly_stop", "entry"]),
        ):
            with self.subTest(block=block, mirror=mirror, four_up=four_up):
                dates, fills = self.replay(mirror=mirror, four_up_case=four_up, block_four_up=block)
                actual = [f["reason"] for f in fills if f["date"] == dates[close_index]]
                self.assertEqual(actual, expected)
                if block and not mirror and four_up:
                    longs = [f["date"] for f in fills if f["reason"] == "entry" and f["side"] == "1"]
                    self.assertEqual(longs, [dates[11]])

    def test_ma10_and_ma20_veto_reversal_despite_opposite_ma5(self):
        for mirror in (False, True):
            for two_slopes in (False, True):
                with self.subTest(mirror=mirror, two_slopes=two_slopes):
                    dates, fills = self.replay(
                        mirror=mirror, slope_case=True, ma10_20_only=two_slopes,
                    )
                    legs = [f["reason"] for f in fills if f["date"] == dates[5]]
                    self.assertEqual(legs, ["weekly_stop"] if two_slopes else ["weekly_stop", "entry"])

    def test_two_closes_admit_entry_despite_earlier_move_in_opposite_direction(self):
        for mirror in (False, True):
            with self.subTest(mirror=mirror):
                dates, fills = self.replay(mirror=mirror, two_close_entry=True)
                first = fills[0]
                self.assertEqual(first["reason"], "entry")
                self.assertEqual(first["signal_day"], dates[2])
                self.assertEqual(first["date"], dates[3])
                self.assertEqual(int(first["side"]), 1 if mirror else -1)

    def test_long_only_blocks_short_entries_and_preserves_long_stop(self):
        dates, fills = self.replay(long_only=True)
        self.assertEqual([(f["date"], f["side"]) for f in fills if f["reason"] == "entry"],
                         [(dates[5], "1"), (dates[14], "1")])
        dates, fills = self.replay(long_only=True, mirror=True)
        self.assertEqual([f["reason"] for f in fills if f["date"] == dates[5]], ["weekly_stop"])
        self.assertEqual([(f["date"], f["side"]) for f in fills if f["reason"] == "entry"],
                         [(dates[3], "1"), (dates[12], "1")])


if __name__ == "__main__":
    unittest.main()
