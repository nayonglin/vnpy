"""Two bounded fixture contracts for the independent Stage124 EMA limit model."""
from datetime import date, timedelta
import hashlib
import importlib
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from stage027_ordered_state import OrderedSetupMachine


def observations(day="2026-01-06", next_day="2026-01-07", **changes):
    result = dict(product="rb.SHFE", contract="rb2605.SHFE", day=day,
                  next_day=next_day, high=101.0, low=99.0, tick=1.0,
                  weekly_ready=True, weekly_direction=1, weekly_asof="2026-01-02",
                  fi_ready=True, fi2=-1.0, eligible=True, position_open=False,
                  native_signal=None)
    result.update(changes)
    return result


def quote(day="2026-01-06", contract="rb2605.SHFE", direction=1):
    return dict(asof=day, contract=contract, ready=True, direction=direction,
                limit_price=97.0 if direction == 1 else 103.0, execution_tick=1.0)


class EmaLimitModelTests(unittest.TestCase):
    def model(self):
        self.assertIsNotNone(importlib.util.find_spec("stage127_ema_limit_model"),
                             "missing independent EMA feature/state component")
        return importlib.import_module("stage127_ema_limit_model")

    def test_formula_source_and_future_poison(self):
        # Break caught: shortened warmup, zero-inclusive mean, future leakage,
        # gap compression, wrong tick direction, or hash-then-reopen source IO.
        model = self.model()
        days = [(date(2025, 1, 1) + timedelta(days=i)).isoformat() for i in range(80)]
        rows = [dict(date=day, vt_symbol="rb2605.SHFE", open=100, high=100,
                     low=100, close=100, volume=20) for day in days]
        for index, value in ((12, 98), (20, 96)):
            rows[index]["low"] = value
        for index, value in ((15, 106), (30, 108)):
            rows[index]["high"] = value
        header = "date,vt_symbol,open,high,low,close,volume\n"
        content = header + "".join(
            ",".join(str(row[key]) for key in header.strip().split(",")) + "\n"
            for row in rows)
        digest = hashlib.sha256(content.encode()).hexdigest()
        qualified = frozenset((row["vt_symbol"], row["date"]) for row in rows)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tiny.csv"
            path.write_text(content)
            original_read = Path.read_bytes
            reads = []

            def read_and_replace(target):
                data = original_read(target)
                if target == path:
                    reads.append(target)
                    target.write_text("replaced after the one byte read")
                return data

            with patch.object(Path, "read_bytes", new=read_and_replace):
                bound, bindings = model.load_bound_daily_csv(
                    path, sha256=digest, qualified_keys=qualified, qualifier_sha256="a" * 64)
            self.assertEqual(reads, [path])
            self.assertEqual(bound[0]["close"], 100.0)
            with self.assertRaisesRegex(ValueError, "sha256"):
                model.load_bound_daily_csv(path, sha256=digest, qualified_keys=qualified,
                                           qualifier_sha256="a" * 64)
            features = model.build_ema_rows(bound, days, source_bindings=bindings)
            self.assertFalse(features[36]["ready"])
            feature = features[37]
            self.assertTrue(feature["ready"])
            self.assertEqual((feature["ema"], feature["ema_prev"]), (100.0, 100.0))
            self.assertEqual(feature["valid_ema_count"], 26)
            self.assertEqual(feature["segment_start"], days[0])
            self.assertEqual((feature["positive_down_count"], feature["mean_down"]), (2, 3.0))
            self.assertEqual((feature["positive_up_count"], feature["mean_up"]), (2, 7.0))
            long = model.limit_quote(feature, direction=1, execution_tick=0.4)
            short = model.limit_quote(feature, direction=-1, execution_tick=0.4)
            self.assertEqual((long["limit_price"], short["limit_price"]), (96.8, 107.2))
            self.assertEqual(long["source_bindings"]["source_sha256"], digest)
            poisoned = [dict(row) for row in bound]
            for row in poisoned[38:]:
                row.update(open=1e9, high=1e9, low=1e9, close=1e9)
            self.assertEqual(features[37], model.build_ema_rows(
                poisoned, days, source_bindings=bindings)[37])
            self.assertEqual(features[:38], model.build_ema_rows(
                bound[:38], days, source_bindings=bindings))
            gap = model.build_ema_rows(bound[:38] + bound[39:], days,
                                       source_bindings=bindings)
            by_day = {row["asof"]: row for row in gap}
            self.assertFalse(by_day[days[75]]["ready"])
            self.assertTrue(by_day[days[76]]["ready"])
            self.assertEqual(by_day[days[76]]["segment_start"], days[39])
            invalid = [dict(row) for row in bound]
            invalid[38]["close"] = float("nan")
            invalid_features = model.build_ema_rows(invalid, days, source_bindings=bindings)
            self.assertFalse(invalid_features[75]["ready"])
            self.assertTrue(invalid_features[76]["ready"])
            seeded = [dict(row, open=i + 1, high=i + 1, low=i + 1, close=i + 1)
                      for i, row in enumerate(bound[:14])]
            seed = model.build_ema_rows(seeded, days, source_bindings=bindings)
            self.assertIsNone(seed[11]["ema"])
            self.assertEqual((seed[12]["ema"], seed[13]["ema"]), (7.0, 8.0))
            self.assertIsNone(model.limit_quote(features[36], direction=1, execution_tick=1))
            self.assertIsNone(model.limit_quote(dict(feature, mean_down=None,
                                                    positive_down_count=0),
                                               direction=1, execution_tick=1))
            for tick in (None, 0, float("nan")):
                self.assertIsNone(model.limit_quote(feature, direction=1, execution_tick=tick))
            with self.assertRaisesRegex(ValueError, "duplicate"):
                model.build_ema_rows(bound + bound[:1], days, source_bindings=bindings)
            with self.assertRaisesRegex(ValueError, "source"):
                model.build_ema_rows(bound, days,
                                     source_bindings=dict(bindings, source_sha256="b" * 64))
            path.write_text(content)
            with self.assertRaisesRegex(ValueError, "unqualified"):
                model.load_bound_daily_csv(path, sha256=digest,
                    qualified_keys=qualified - {(rows[0]["vt_symbol"], rows[0]["date"])},
                    qualifier_sha256="a" * 64)
            mixed_content = content + "".join(
                f"{day},rb2610.SHFE,1000,1000,1000,1000,20\n" for day in days[:38])
            path.write_text(mixed_content)
            mixed, mixed_bindings = model.load_bound_daily_csv(
                path, sha256=hashlib.sha256(mixed_content.encode()).hexdigest(),
                qualified_keys=qualified | frozenset(("rb2610.SHFE", day) for day in days[:38]),
                qualifier_sha256="a" * 64)
            own = [row for row in model.build_ema_rows(mixed, days, source_bindings=mixed_bindings)
                   if row["contract"] == "rb2610.SHFE"]
            self.assertEqual(own[37]["ema"], 1000.0)
            self.assertEqual(own[37]["positive_down_count"], 0)
            self.assertIsNone(model.limit_quote(own[37], direction=1, execution_tick=1))
            carry = content.replace("rb2605.SHFE", "rb9999.SHFE")
            path.write_text(carry)
            with self.assertRaisesRegex(ValueError, "real_contract"):
                model.load_bound_daily_csv(path, sha256=hashlib.sha256(carry.encode()).hexdigest(),
                    qualified_keys=frozenset(("rb9999.SHFE", day) for day in days),
                    qualifier_sha256="a" * 64)

    def test_state_epoch_unknown_and_identity(self):
        # Break caught: EMA unknown consumes setup, DAY survives expiration,
        # stale epoch quotes leak, a fill consumes twice, or old B IDs escape.
        model = self.model()
        machine = model.EmaLimitSetupMachine()
        first = machine.on_close(observations(), None)
        self.assertIsNotNone(first["setup_id"])
        self.assertIsNone(first["intent"])
        day2 = observations("2026-01-07", "2026-01-08", fi2=1)
        second = machine.on_close(day2, quote("2026-01-07"))
        intent = second["intent"]
        self.assertEqual(second["setup_id"], first["setup_id"])
        self.assertEqual(intent["order_type"], "limit")
        self.assertEqual(intent["trigger"], intent["limit_price"])
        self.assertEqual(intent["mechanism_id"], model.MECHANISM_ID)
        self.assertIsNone(intent["native_signal"])
        self.assertEqual((intent["signal_day"], intent["execution_day"]),
                         ("2026-01-07", "2026-01-08"))
        old = OrderedSetupMachine("B_TS").on_close(**observations())
        for key in ("epoch_id", "setup_id", "intent_id"):
            self.assertTrue(intent[key].startswith(model.MECHANISM_ID))
            self.assertNotEqual(intent[key], old["intent"][key])
        self.assertNotIn("B_TS", str(intent))
        with self.assertRaisesRegex(ValueError, "outside_execution_day"):
            machine.on_fill(intent["intent_id"], "2026-01-09")
        third = machine.on_close(observations("2026-01-08", "2026-01-09", fi2=1),
                                 quote("2026-01-08"))
        self.assertEqual(third["setup_id"], first["setup_id"])
        self.assertNotEqual(third["intent"]["intent_id"], intent["intent_id"])
        with self.assertRaisesRegex(ValueError, "expired_intent"):
            machine.on_fill(intent["intent_id"], "2026-01-08")
        receipt = machine.on_fill(third["intent"]["intent_id"], "2026-01-09")
        self.assertTrue(receipt["consumed"])
        with self.assertRaisesRegex(ValueError, "expired_intent"):
            machine.on_fill(third["intent"]["intent_id"], "2026-01-09")
        after = machine.on_close(observations("2026-01-09", "2026-01-12", fi2=1),
                                 quote("2026-01-09"))
        self.assertIsNone(after["intent"])
        epoch = model.EmaLimitSetupMachine()
        prepared = epoch.on_close(observations(), quote())
        changed = epoch.on_close(observations("2026-01-07", "2026-01-08",
                         contract="rb2610.SHFE", fi2=1), None)
        self.assertIsNone(changed["setup_id"])
        self.assertEqual(changed["cancel_reason"], "epoch_changed")
        with self.assertRaises(ValueError):
            epoch.on_fill(prepared["intent"]["intent_id"], "2026-01-07")
        with self.assertRaisesRegex(ValueError, "quote_contract"):
            epoch.on_close(observations("2026-01-08", "2026-01-09",
                         contract="rb2610.SHFE"), quote("2026-01-08"))
        restarted = epoch.on_close(observations("2026-01-08", "2026-01-09",
                         contract="rb2610.SHFE"), quote("2026-01-08", "rb2610.SHFE"))
        self.assertNotEqual(restarted["intent"]["epoch_id"], prepared["intent"]["epoch_id"])
        cancelled = epoch.cancel("rb.SHFE", "2026-01-09", "target_real_bar_missing")
        self.assertIsNone(cancelled["setup_id"])
        self.assertIsNone(cancelled["intent"])
        for changes in ({"weekly_ready": False}, {"fi_ready": False},
                        {"eligible": False}, {"position_open": True},
                        {"weekly_direction": 0}, {"weekly_direction": -1, "fi2": -1}):
            isolated = model.EmaLimitSetupMachine()
            isolated.on_close(observations(), None)
            supplied_quote = (None if changes.get("weekly_direction") == -1
                              else quote("2026-01-07"))
            try:
                result = isolated.on_close(observations("2026-01-07", "2026-01-08", **changes),
                                           supplied_quote)
            except ValueError as exc:
                self.fail(f"weekly/FI/eligibility restriction must clear preparation: {exc}")
            self.assertIsNone(result["setup_id"])
            self.assertIsNone(result["intent"])
            self.assertFalse(result["baseline_fallback"])
        with self.assertRaisesRegex(ValueError, "native_signal"):
            model.EmaLimitSetupMachine().on_close(observations(native_signal="long_case1a"), quote())


if __name__ == "__main__":
    unittest.main()
