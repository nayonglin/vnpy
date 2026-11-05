"""Independently reconstruct Stage057 return statistics and category-constrained selection."""
import argparse
from collections import defaultdict
from datetime import date, datetime
from itertools import combinations, product
import json
from math import fsum, isfinite, log, nan, sqrt
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from stage048_s26_full_audit import TAIL_CERT, extend_raw_market
from stage040_s19_without_gold_audit import check_manifest, load_json, sha

LINE = Path(__file__).resolve().parents[1]
RESULT = LINE / "outputs/stage057_diverse10_20261104"
PARENT = LINE / "outputs/stage055_s21_all_touch_halfyear_20261104"
CATEGORIES = {
    "贵金属": ["au.SHFE"],
    "有色金属": ["cu.SHFE"],
    "黑色产业链": ["jm.DCE", "SM.CZCE", "rb.SHFE", "hc.SHFE", "ss.SHFE"],
    "能源": ["fu.SHFE"],
    "化工及工业材料": ["MA.CZCE", "FG.CZCE", "SA.CZCE", "SH.CZCE", "lc.GFEX", "si.GFEX"],
    "油脂": ["OI.CZCE", "p.DCE"],
    "纺织": ["CF.CZCE"],
    "畜牧": ["lh.DCE"],
    "果品": ["AP.CZCE"],
    "林业及天然材料": ["ru.SHFE", "sp.SHFE"],
}
WINDOWS = {"daily_252": (252, 180), "daily_756": (756, 500), "weekly_156": (156, 100)}
LIMIT = 0.60


def correlation(left, right):
    pairs = [(a, b) for a, b in zip(left, right) if isfinite(a) and isfinite(b)]
    count = len(pairs)
    if count < 2:
        return nan, count
    x, y = zip(*pairs)
    mean_x, mean_y = fsum(x) / count, fsum(y) / count
    dx = [value - mean_x for value in x]
    dy = [value - mean_y for value in y]
    denominator = sqrt(fsum(value * value for value in dx) * fsum(value * value for value in dy))
    if denominator == 0:
        return nan, count
    return fsum(a * b for a, b in zip(dx, dy)) / denominator, count


def quantile(values, probability):
    if not values:
        return nan
    ordered = sorted(values)
    location = probability * (len(ordered) - 1)
    lower = int(location)
    fraction = location - lower
    return ordered[lower] * (1 - fraction) + ordered[min(lower + 1, len(ordered) - 1)] * fraction


def compare_frame(expected, actual, label, tolerance=1e-12):
    pd.testing.assert_frame_equal(
        expected, actual, check_dtype=False, check_exact=False,
        rtol=0, atol=tolerance, obj=label,
    )


def independent_returns(products, market):
    calendar, guard_calendar, mains, symbols, by_epoch, _ = market
    calendar = [day for day in calendar if day >= "2014-01-01"]
    daily = pd.DataFrame(nan, index=pd.Index(calendar, name="date"), columns=products)
    evidence = []
    roll_days = 0
    for index in range(1, len(calendar)):
        day, previous_day = calendar[index], calendar[index - 1]
        for product_name in products:
            native = mains.get((day, product_name))
            current = symbols.get((day, native))
            if current is None:
                continue
            previous = by_epoch.get((previous_day, current.epoch))
            if previous is None:
                continue
            assert previous.epoch == current.epoch and previous.close > 0 and current.close > 0
            value = log(current.close / previous.close)
            daily.at[day, product_name] = value
            evidence.append({
                "date": day, "previous_day": previous_day, "product": product_name,
                "contract": current.symbol, "epoch": current.epoch,
                "close": current.close / 100, "previous_close": previous.close / 100,
                "log_return": value,
            })
            roll_days += native != mains.get((previous_day, product_name))
    calendar_weeks = defaultdict(list)
    for day in guard_calendar:
        if day >= calendar[0]:
            calendar_weeks[date.fromisoformat(day).isocalendar()[:2]].append(day)
    endpoints, weekly_values = [], []
    for days in calendar_weeks.values():
        if days[-1] > calendar[-1]:
            continue
        assert set(days) <= set(calendar)
        rows = daily.loc[days]
        values = {}
        for name in products:
            observations = rows[name].tolist()
            values[name] = fsum(observations) if all(isfinite(x) for x in observations) else nan
        endpoints.append(days[-1])
        weekly_values.append(values)
    weekly = pd.DataFrame(weekly_values, index=pd.Index(endpoints, name="date"), columns=products)
    return daily, weekly, pd.DataFrame(evidence), roll_days


def independent_pairs(daily, weekly):
    rows = []
    for left, right in combinations(daily.columns, 2):
        row = {"left": left, "right": right}
        eligible = True
        scores = []
        for name, (length, minimum) in WINDOWS.items():
            sample = weekly.iloc[-length:] if name.startswith("weekly") else daily.iloc[-length:]
            value, count = correlation(sample[left], sample[right])
            row[name + "_corr"], row[name + "_n"] = value, count
            scores.append(abs(value))
            eligible &= count >= minimum and isfinite(value)
        row["full_daily_corr"], row["full_daily_n"] = correlation(daily[left], daily[right])
        rolling = []
        x, y = weekly[left].tolist(), weekly[right].tolist()
        for end in range(52, len(weekly) + 1):
            value, count = correlation(x[end - 52:end], y[end - 52:end])
            if count == 52 and isfinite(value):
                rolling.append(abs(value))
        row.update(
            rolling52_abs_p95=quantile(rolling, 0.95),
            rolling52_abs_max=max(rolling, default=nan), rolling52_n=len(rolling),
            score=max(scores) if eligible else nan,
            sufficient_history=eligible, allowed=eligible and max(scores) < LIMIT,
        )
        rows.append(row)
    return pd.DataFrame(rows)


def independent_candidates(pairs):
    lookup = {tuple(sorted((row.left, row.right))): row for row in pairs.itertuples(index=False)}
    rows = []
    for choice in product(*CATEGORIES.values()):
        links = [lookup[tuple(sorted(pair))] for pair in combinations(choice, 2)]
        assert len(links) == 45
        rows.append({
            "products": json.dumps(sorted(choice)),
            "allowed": all(link.allowed for link in links),
            "max_correlation": max(link.score for link in links),
            "mean_pair_score": fsum(link.score for link in links) / len(links),
            "violating_pairs": sum(not link.allowed for link in links),
        })
    return pd.DataFrame(rows).sort_values(
        ["max_correlation", "mean_pair_score", "products"], kind="stable",
    ).reset_index(drop=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--certificate", type=Path)
    arguments = parser.parse_args()
    entries = check_manifest(RESULT)
    parent_entries = check_manifest(PARENT)
    receipt = load_json(RESULT / "selection.json")
    parent = load_json(PARENT / "receipt.json")
    assert receipt["stage055_manifest_sha256"] == sha(PARENT / "SHA256SUMS")
    assert receipt["design_sha256"] == sha(LINE / "stages/20261105_1304_stage057_diverse10_design.md")
    assert receipt["entrypoint_sha256"] == sha(LINE / "tools/stage057_diverse10.py")
    assert receipt["loader_sha256"] == sha(LINE / "tools/stage056_random10_touch.py")
    assert receipt["market_sha256"] == parent["market_sha256"]
    pins = receipt["market_sha256"] | load_json(PARENT / "2015-01-01/inputs.json")["source_sha256"]
    assert len(pins) == 42 and all(sha(Path(path)) == digest for path, digest in pins.items())
    products = parent["products"]
    classification = [item for values in CATEGORIES.values() for item in values]
    assert set(classification) == set(products) and len(classification) == len(set(classification)) == 21
    assert receipt["categories"] == CATEGORIES and receipt["windows"] == {k: list(v) for k, v in WINDOWS.items()}
    assert receipt["correlation_limit"] == LIMIT and receipt["cutoff"] == parent["cutoff"]
    market = extend_raw_market(load_json(TAIL_CERT))
    daily, weekly, evidence, switch_days = independent_returns(products, market)
    for filename, expected in (
        ("daily_log_returns.csv", daily), ("weekly_log_returns.csv", weekly),
    ):
        actual = pd.read_csv(RESULT / filename, index_col="date")
        compare_frame(expected, actual, filename)
    observed_evidence = pd.read_csv(RESULT / "return_evidence.csv")
    compare_frame(evidence, observed_evidence, "every same-epoch daily return")
    pairs = independent_pairs(daily, weekly)
    observed_pairs = pd.read_csv(RESULT / "pairwise.csv")
    compare_frame(pairs, observed_pairs, "all 210 pairs and three windows plus diagnostics", tolerance=1e-10)
    assert len(pairs) == 210
    choices = independent_candidates(pairs)
    observed_choices = pd.read_csv(RESULT / "candidates.csv")
    compare_frame(choices, observed_choices, "all 120 candidate sets")
    assert len(choices) == len(set(choices.products)) == receipt["attempted_combinations"] == 120
    valid = choices.loc[choices.allowed]
    selected = json.loads(valid.iloc[0].products) if not valid.empty else []
    assert receipt["eligible_combinations"] == len(valid) and receipt["selected"] == selected
    assert receipt["status"] == ("SELECTED_FOR_RESEARCH" if selected else "NO_FEASIBLE_SELECTION")
    expected_by_category = {
        name: next((item for item in values if item in selected), None)
        for name, values in CATEGORIES.items()
    }
    assert receipt["selected_by_category"] == expected_by_category
    chosen_links = pairs.loc[pairs.left.isin(selected) & pairs.right.isin(selected)]
    compare_frame(chosen_links.reset_index(drop=True), pd.read_csv(RESULT / "selected_pairs.csv"),
                  "selected pair table", tolerance=1e-10)
    for name, (length, _) in WINDOWS.items():
        sample = weekly.iloc[-length:] if name.startswith("weekly") else daily.iloc[-length:]
        assert receipt["data_windows"][name] == {
            "first": sample.index[0], "last": sample.index[-1], "observations": len(sample),
        }
    if selected:
        assert len(selected) == 10 and len(chosen_links) == 45 and chosen_links.allowed.all()
        assert abs(receipt["maximum_pair_score"] - valid.iloc[0].max_correlation) < 1e-12
        assert abs(receipt["mean_pair_score"] - valid.iloc[0].mean_pair_score) < 1e-12
    else:
        assert receipt["maximum_pair_score"] is None and receipt["mean_pair_score"] is None
    mandatory = {values[0] for values in CATEGORIES.values() if len(values) == 1}
    conflicts = pairs.loc[pairs.left.isin(mandatory) & pairs.right.isin(mandatory) & ~pairs.allowed]
    certificate = {
        "schema": "stage057_independent_diverse10_selection_audit_v1",
        "verdict": "PASS_WITH_LIMITATIONS",
        "selection_status": receipt["status"],
        "audited_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"),
        "audit_script_sha256": sha(Path(__file__)),
        "result_manifest_sha256": sha(RESULT / "SHA256SUMS"),
        "checked_manifests": {RESULT.name: entries, PARENT.name: parent_entries}, "input_hashes": len(pins),
        "financial_replays": 0,
        "independent_method": "Integer-cent physical raw market; math.log same-epoch close ratios; full-week fsum; centered fsum Pearson and independent rolling quantiles.",
        "return_rows": {"daily_matrix": len(daily), "weekly_matrix": len(weekly), "daily_evidence": len(evidence)},
        "matrix_products": len(products), "main_switch_returns_checked": switch_days,
        "pair_statistics": len(pairs), "candidate_combinations": len(choices),
        "eligible_combinations": len(valid), "selected": selected,
        "all_pairs_have_sufficient_history": bool(pairs.sufficient_history.all()),
        "mandatory_conflicts": conflicts.to_dict("records"),
        "best_rejected_diagnostic": json.loads(choices.head(1).to_json(orient="records")) if valid.empty else [],
        "limitations": [
            "The ten categories are author-defined risk buckets within this selected 21-product pool, with heterogeneous economic drivers.",
            "The fixed pool does not cover all futures markets or missing grain and crude-oil categories.",
            "Threshold 0.60 and observation windows are research choices. Historical correlations can change in stress.",
            "Current-market correlation selection has no historical point-in-time or out-of-sample qualification.",
            "Low correlation of descriptive price returns does not constrain one-lot risk, margin, strategy PnL correlation or funding paths.",
        ],
    }
    print(json.dumps(certificate, ensure_ascii=False, indent=2), flush=True)
    if arguments.certificate:
        with arguments.certificate.open("x") as file:
            json.dump(certificate, file, ensure_ascii=False, indent=2, allow_nan=False)
            file.write("\n")


if __name__ == "__main__":
    main()
