"""Verify the new July 2015 pair and the complete Stage041 half-year grid."""
from bisect import bisect_left
from collections import defaultdict
from datetime import date
from functools import lru_cache
import json
from pathlib import Path

import pandas as pd

from stage040_s19_without_gold_audit import (
    ADMITTED, CAPITAL, FULL, HISTORY, LINE, OUT, TARGET, audit_book, cents,
    check_manifest, compare_other_products, load_json, near, physical_prices, read_csv, sha,
)

CURRENT = LINE / "outputs/stage041_complete_halfyear_20261104"
PREVIOUS_AUDIT = LINE / "reviews/stage040_s19_without_gold_audit.json"
PREVIOUS_AUDIT_SHA = "a668436d84a9a7aac00d5f74aaad1b7dc1d52f0cc83c92736ac9fdeba90d63ef"
ADDED = "2015-07-01"
STARTS = [f"{year}-{month}-01" for year in range(2015, 2027) for month in ("01", "07")]


def signal_checker(mapping, calendar):
    days = sorted(set(calendar) | set(pd.read_csv(ADMITTED / "forward_calendar.csv").date))
    week_buckets = defaultdict(list)
    for day in days:
        week_buckets[date.fromisoformat(day).isocalendar()[:2]].append(day)
    weeks = list(week_buckets.values())
    week_index = {day: index for index, week in enumerate(weeks) for day in week}
    following = dict(zip(calendar, calendar[1:]))
    previous = dict(zip(calendar[1:], calendar))
    mains = {(row.date, row.continuous_symbol_vt): row.main_contract_vt for row in mapping.itertuples(index=False)}
    source = pd.read_csv(ADMITTED / "physical_epoch_daily.csv",
                         usecols=["date", "contract_epoch_id", "open", "high", "low", "close"])
    prices = {(row.date, row.contract_epoch_id): tuple(map(cents, (row.open, row.high, row.low, row.close)))
              for row in source.itertuples(index=False)}
    assert len(prices) == len(source)

    @lru_cache(None)
    def week_bar(epoch, index):
        if index < 0:
            return None
        bars = [prices.get((day, epoch)) for day in weeks[index]]
        if None in bars:
            return None
        return bars[0][0], max(bar[1] for bar in bars), min(bar[2] for bar in bars), bars[-1][3]

    def guard_start(epoch):
        delivery = epoch.split(".")[-1]
        first = f"{delivery[:4]}-{delivery[4:]}-01"
        return days[bisect_left(days, first) - 5]

    def check(folder):
        signals = read_csv(folder, "signals")
        fills = read_csv(folder, "fills")
        signal_index = {}
        for sig in signals.itertuples(index=False):
            index = week_index[sig.date]
            assert weeks[index][-1] == sig.date
            current, prior = (week_bar(sig.epoch, number) for number in (index, index - 1))
            assert (cents(sig.close), cents(sig.prior_close)) == (current[3], prior[3])
            key = sig.date, sig.product, sig.action
            assert key not in signal_index
            signal_index[key] = sig
            if sig.action.startswith("open_"):
                older = week_bar(sig.epoch, index - 2)
                direction = 1 if sig.action == "open_long" else -1
                assert direction * current[3] > direction * prior[3] > direction * older[3]
                assert cents(float(sig.older_close)) == older[3]
                assert all(direction * (bar[3] - bar[0]) > 0 for bar in (current, prior))
                assert cents(sig.stop) == current[2 if direction == 1 else 1]
                assert sig.contract == mains[sig.date, sig.product]
                bars = [week_bar(sig.epoch, index - offset) for offset in range(21)]
                if all(bars):
                    assert not all(direction * (current[3] - bars[offset][3]) < 0 for offset in (5, 10, 20))
                if direction == 1 and all(bars[:5]):
                    assert not all(left[3] > right[3] for left, right in zip(bars[:4], bars[1:5]))
            elif sig.action == "close_long":
                assert current[3] <= prior[2] == cents(sig.stop)
            else:
                assert sig.action == "close_short" and current[3] >= prior[1] == cents(sig.stop)

        last_fill = None
        reversals = 0
        for fill in fills.itertuples(index=False):
            if fill.reason in ("entry", "weekly_stop"):
                directions = {1: "long", -1: "short"}
                action = ("open_" + directions[fill.side] if fill.reason == "entry"
                          else "close_" + directions[-fill.side])
                sig = signal_index[fill.signal_day, fill.product, action]
                assert (fill.epoch, fill.contract, cents(float(fill.stop))) == (sig.epoch, sig.contract, cents(sig.stop))
                if fill.reason == "entry":
                    assert fill.date == following[fill.signal_day] and fill.date < guard_start(fill.epoch)
                    assert not fill.one_price
                    if last_fill and (last_fill.date, last_fill.product) == (fill.date, fill.product):
                        assert (last_fill.reason, last_fill.signal_day, last_fill.side) == (
                            "weekly_stop", fill.signal_day, fill.side)
                        reversals += 1
                else:
                    assert fill.date >= following[fill.signal_day]
            elif fill.reason == "delivery_guard_exit":
                assert fill.date >= fill.signal_day == guard_start(fill.epoch)
            else:
                assert fill.reason in ("roll_open", "roll_close")
                assert fill.signal_day == previous[fill.date] and fill.date < guard_start(fill.epoch)
                if fill.reason == "roll_open":
                    assert (fill.date, fill.product, fill.cycle, -fill.side, "roll_close") == (
                        last_fill.date, last_fill.product, last_fill.cycle, last_fill.side, last_fill.reason)
                    assert fill.contract == mains[fill.signal_day, fill.product] and not fill.one_price
                    prev = week_bar(fill.epoch, week_index[fill.date] - 1)
                    assert cents(float(fill.stop)) == prev[2 if fill.side == 1 else 1]
            last_fill = fill
        return dict(signals=len(signals), fills=len(fills), same_day_reversals=reversals)

    return check


def audit():
    previous_size, current_size = check_manifest(OUT), check_manifest(CURRENT)
    receipt = load_json(CURRENT / "receipt.json")
    previous_receipt = load_json(OUT / "receipt.json")
    assert receipt["stage040_manifest_sha256"] == sha(OUT / "SHA256SUMS")
    assert sha(PREVIOUS_AUDIT) == PREVIOUS_AUDIT_SHA
    assert load_json(PREVIOUS_AUDIT)["manifest_sha256"] == receipt["stage040_manifest_sha256"]
    assert receipt["design_sha256"] == sha(LINE / "stages/20261104_1818_stage041_complete_halfyear_design.md")
    assert receipt["entrypoint_sha256"] == sha(LINE / "tools/stage041_complete_halfyear.py")
    assert (receipt["capital"], receipt["cutoff"], receipt["completed_pairs"], receipt["unknown_pairs"]) == (
        CAPITAL, TARGET, 24, 0)
    assert receipt["starts"] == STARTS and receipt["newly_replayed"] == [ADDED]
    assert {path.name for path in CURRENT.iterdir() if path.is_dir()} == {ADDED}
    assert {path.name for path in (CURRENT / ADDED).iterdir()} == {"s19", "no_gold"}
    reused = read_csv(OUT, "window_metrics").set_index("calendar_start", verify_integrity=True)
    combined = read_csv(CURRENT, "window_metrics").set_index("calendar_start", verify_integrity=True)
    assert combined.index.tolist() == STARTS
    assert reused.index.tolist() == receipt["reused"] == [start for start in STARTS if start != ADDED]
    pd.testing.assert_frame_equal(combined.drop(index=ADDED), reused, check_exact=False, rtol=0, atol=1e-10)
    pins = previous_receipt["market_sha256"] | previous_receipt["source_sha256"]
    assert all(sha(Path(path)) == digest for path, digest in pins.items())

    mapping = pd.read_csv(ADMITTED / "mapping.csv", usecols=["date", "continuous_symbol_vt", "main_contract_vt"])
    calendar = sorted(set(mapping.date)) + [TARGET]
    prices = physical_prices()
    settings = load_json(HISTORY / "stage003_D_20261103_attempt01/contract_settings.json")
    check_signals = signal_checker(mapping, calendar)
    full, without = CURRENT / ADDED / "s19", CURRENT / ADDED / "no_gold"
    config = {**load_json(FULL / "inputs.json"), "start": ADDED}
    assert load_json(full / "inputs.json") == config
    assert load_json(without / "inputs.json") == {**config, "products": previous_receipt["products"]}
    event_comparisons = compare_other_products(full, without)
    control, control_counts, control_daily, gold = audit_book(full, ADDED, calendar, prices, settings)
    candidate, candidate_counts, candidate_daily, absent = audit_book(without, ADDED, calendar, prices, settings)
    near(absent, 0)
    near(control_daily.equity - candidate_daily.equity, gold[:, 0])
    near(control_daily.margin - candidate_daily.margin, gold[:, 1])
    near(control["gold_net_pnl"], gold[-1, 0])

    row = combined.loc[ADDED]
    assert (row.first_session, row.last_session, row.days) == (ADDED, TARGET, len(control_daily))
    for prefix, expected in (("s19", control), ("no_gold", candidate)):
        for key, value in expected.items():
            if isinstance(value, str):
                assert row[f"{prefix}_{key}"] == value
            else:
                near(row[f"{prefix}_{key}"], value)
    totals = {label: int((combined[f"{label}_deficit_days"] > 0).sum()) for label in ("s19", "no_gold")}
    result = dict(
        verdict="PASS_WITH_LIMITATIONS", pairs=24, new_pairs=1, reused_pairs=23, unknown_pairs=0,
        current_manifest_sha256=sha(CURRENT / "SHA256SUMS"), current_manifest_entries=current_size,
        previous_manifest_entries=previous_size, previous_audit_sha256=PREVIOUS_AUDIT_SHA,
        pinned_inputs=len(pins), unchanged_non_gold_rows=event_comparisons, deficit_pairs=totals,
        new_window_counts=dict(s19=control_counts, no_gold=candidate_counts),
        new_window_signal_checks=dict(s19=check_signals(full), no_gold=check_signals(without)),
        new_window_gold_net_pnl=control["gold_net_pnl"],
        limitations=["Overlapping historical windows", "Static margin and zero commission",
                     "Theoretical fills continue after capital shortfalls",
                     "Previous paired Sharpe outputs in windows with nonpositive equity retain Stage040 limitations"],
    )
    destination = Path(__file__).with_suffix(".json")
    with destination.open("x") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    print(result)


if __name__ == "__main__":
    audit()
