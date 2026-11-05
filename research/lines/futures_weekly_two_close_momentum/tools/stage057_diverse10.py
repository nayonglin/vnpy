"""Select one product per declared category using return correlation alone."""
import argparse
from itertools import combinations, product
import json
from pathlib import Path

import numpy as np
import pandas as pd

import stage056_random10_touch as parent

LINE = parent.LINE
DESIGN = LINE / "stages/20261105_1304_stage057_diverse10_design.md"
LIMIT = 0.60
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


def returns(market):
    products, calendar, weeks, _, rows, by_epoch, mains, _, _ = market
    daily = pd.DataFrame(np.nan, index=pd.Index(calendar, name="date"), columns=products)
    evidence = []
    for index, day in enumerate(calendar[1:], start=1):
        previous_day = calendar[index - 1]
        for symbol in products:
            contract = mains.get((day, symbol))
            current = rows.get((day, contract))
            previous = by_epoch.get((previous_day, current.contract_epoch_id)) if current else None
            if previous is None:
                continue
            if (current.close <= 0 or previous.close <= 0 or current.volume <= 0 or previous.volume <= 0
                    or current.contract_epoch_id != previous.contract_epoch_id):
                raise ValueError(f"invalid same-contract return: {symbol}/{day}")
            value = np.log(current.close / previous.close)
            daily.at[day, symbol] = value
            evidence.append(dict(date=day, previous_day=previous_day, product=symbol, contract=contract,
                                 epoch=current.contract_epoch_id, close=current.close,
                                 previous_close=previous.close, log_return=value))
    weekly_rows = []
    for dates in weeks:
        if dates[-1] > calendar[-1]:
            continue
        # The global week also includes any preceding history needed to establish completeness.
        complete = daily.reindex(dates)
        values = complete.sum(min_count=len(dates))
        weekly_rows.append(dict(date=dates[-1], **values.to_dict()))
    weekly = pd.DataFrame(weekly_rows).set_index("date")
    return daily, weekly, pd.DataFrame(evidence)


def pair_statistics(daily, weekly):
    rows = []
    for left, right in combinations(daily.columns, 2):
        row = dict(left=left, right=right)
        eligible, correlations = True, []
        for name, (length, minimum) in WINDOWS.items():
            sample = (weekly if name.startswith("weekly") else daily).iloc[-length:]
            paired = sample[[left, right]].dropna()
            coefficient = paired[left].corr(paired[right])
            row[name + "_corr"] = coefficient
            row[name + "_n"] = len(paired)
            eligible = eligible and len(paired) >= minimum and np.isfinite(coefficient)
            correlations.append(abs(coefficient))
        entire = daily[[left, right]].dropna()
        row["full_daily_corr"] = entire[left].corr(entire[right])
        row["full_daily_n"] = len(entire)
        rolling = weekly[left].rolling(52, min_periods=52).corr(weekly[right]).dropna().abs()
        row["rolling52_abs_p95"] = rolling.quantile(0.95)
        row["rolling52_abs_max"] = rolling.max()
        row["rolling52_n"] = len(rolling)
        row["score"] = max(correlations) if eligible else np.nan
        row["sufficient_history"] = eligible
        row["allowed"] = eligible and max(correlations) < LIMIT
        rows.append(row)
    return pd.DataFrame(rows)


def candidates(pairs):
    lookup = {tuple(sorted((row.left, row.right))): row for row in pairs.itertuples(index=False)}
    result = []
    for chosen in product(*CATEGORIES.values()):
        values = [lookup[tuple(sorted(pair))] for pair in combinations(chosen, 2)]
        maximum = max(value.score for value in values)
        result.append(dict(
            products=json.dumps(sorted(chosen)), allowed=all(value.allowed for value in values),
            max_correlation=maximum, mean_pair_score=float(np.mean([value.score for value in values])),
            violating_pairs=sum(not value.allowed for value in values),
        ))
    return pd.DataFrame(result).sort_values(["max_correlation", "mean_pair_score", "products"])


def run(output):
    _, frozen, market = parent.frozen_market()
    assigned = [symbol for values in CATEGORIES.values() for symbol in values]
    if len(assigned) != len(set(assigned)) or set(assigned) != set(market[0]):
        raise ValueError("categories must partition the parent universe")
    daily, weekly, evidence = returns(market)
    pairs = pair_statistics(daily, weekly)
    choices = candidates(pairs)
    output.mkdir(parents=True)
    daily.to_csv(output / "daily_log_returns.csv")
    weekly.to_csv(output / "weekly_log_returns.csv")
    evidence.to_csv(output / "return_evidence.csv", index=False)
    pairs.to_csv(output / "pairwise.csv", index=False)
    choices.to_csv(output / "candidates.csv", index=False)
    valid = choices.loc[choices.allowed]
    selected = json.loads(valid.iloc[0].products) if not valid.empty else []
    selected_pairs = pairs.loc[pairs.left.isin(selected) & pairs.right.isin(selected)]
    selected_pairs.to_csv(output / "selected_pairs.csv", index=False)
    category_selection = {key: next((p for p in values if p in selected), None)
                          for key, values in CATEGORIES.items()}
    if selected and (len(selected) != 10 or len(selected_pairs) != 45 or not selected_pairs.allowed.all()):
        raise ValueError("selected universe violates the declared constraints")
    receipt = dict(
        schema="stage057_diverse10_correlation_selection_v1", cutoff=frozen["cutoff"],
        categories=CATEGORIES, selected_by_category=category_selection, selected=selected,
        selection_rule="one_per_category; all_abs_correlations_lt_0.60; minimax_then_mean_then_lexicographic",
        windows=WINDOWS, correlation_limit=LIMIT,
        attempted_combinations=len(choices), eligible_combinations=len(valid),
        status="SELECTED_FOR_RESEARCH" if selected else "NO_FEASIBLE_SELECTION",
        maximum_pair_score=float(valid.iloc[0].max_correlation) if selected else None,
        mean_pair_score=float(valid.iloc[0].mean_pair_score) if selected else None,
        data_windows={
            name: dict(first=sample.index[0], last=sample.index[-1], observations=len(sample))
            for name, (length, _) in WINDOWS.items()
            for sample in [(weekly if name.startswith("weekly") else daily).iloc[-length:]]
        },
        design_sha256=parent.base.portfolio.sha(DESIGN),
        entrypoint_sha256=parent.base.portfolio.sha(Path(__file__)),
        loader_sha256=parent.base.portfolio.sha(Path(parent.__file__)),
        stage055_manifest_sha256=parent.prior.read_json(parent.FROZEN)["stage055_manifest_sha256"],
        market_sha256=frozen["market_sha256"],
    )
    (output / "selection.json").write_text(json.dumps(receipt, indent=2, ensure_ascii=False, allow_nan=False) + "\n")
    parent.base.write_checksums(output, (p for p in output.rglob("*") if p.is_file()))
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    if selected:
        print(selected_pairs.sort_values("score", ascending=False).head(10).to_string(index=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    run(parser.parse_args().output)
