"""Relate fixed, signal-time weekly OHLC shapes to frozen S44 outcomes."""
import json
from pathlib import Path

import numpy as np
import pandas as pd

from stage005_trade_recap import LINE, STAGE025_S44_2022, load, verify

OUT = LINE / "outputs/stage029_s44_weekly_shapes_v1"
BASE = LINE / "outputs" / STAGE025_S44_2022.run
FILTER = LINE / "outputs/stage028_s44_week_range_overlap_v1"
FILTER_SHA = "52f97e5f694596ccee29b1299dcf381141cc218265e3bfcf088989506bd40ccd"
OHLC = ["open", "high", "low", "close"]

RULES = {
    "strong_close": "信号收于方向四分位，实体占振幅至少二分之一",
    "paired_strong_close": "两根确认周均为大实体，且均收于方向四分位",
    "narrow_body": "信号周实体不超过全振幅三分之一",
    "support_wick": "前确认周逆势端影线至少等于实体，且信号收盘突破前周",
    "rejection_wick": "信号周顺势端影线至少为实体两倍",
    "low_overlap": "两根确认周重叠小于较短振幅的一半",
    "high_overlap": "两根确认周重叠至少为较短振幅的一半",
    "disjoint_ranges": "信号周整个区间越过前周方向端",
    "outside_week": "信号周高低区间完整包住前周且至少一端越过",
    "inside_week": "信号周高低区间完全在前周范围内且至少一端收窄",
    "higher_high_low": "信号周高低点均顺势移动",
    "break_1w": "信号收盘越过前一周的方向极值",
    "break_3w": "信号收盘越过前三周的方向极值",
    "break_6w": "信号收盘越过前六周的方向极值",
    "paired_break": "两根确认周各自收盘越过其前一周方向极值",
    "failed_break": "信号周越过前周方向极值但收回区间",
    "range_expansion": "信号振幅达到前周两倍，且收于方向四分位",
    "range_compression": "信号振幅至多为前周一半",
    "inside_breakout": "前确认周位于再前一周区间内，信号收盘越过母 K",
    "sweep_then_break": "前确认周先扫过再前一周逆势极值再收回，信号收盘越过前周方向端",
    "compression_break": "前三周振幅逐周缩小，信号收盘越过前三周极值",
    "direction_gap": "信号周开盘越过前周方向极值",
}


def shape_margins(bars):
    """Scores use the signal range as scale. Positive scores indicate a match."""
    current, prev, older = bars[-1], bars[-2], bars[-3]
    opening, high, low, close = current
    prev_open, prev_high, prev_low, prev_close = prev
    _, older_high, older_low, _ = older
    span, prev_span = high - low, prev_high - prev_low
    body, prev_body = close - opening, prev_close - prev_open
    overlap = max(0, min(high, prev_high) - max(low, prev_low)) / min(span, prev_span)
    strong = min((body - span / 2) / span, (close - low) / span - 0.75)
    prev_strong = min((prev_body - prev_span / 2) / prev_span, (prev_close - prev_low) / prev_span - 0.75)
    break_prior = (close - prev_high) / span
    prior3 = bars[-4:-1]
    prior6 = bars[-7:-1]
    break3 = (close - np.max(prior3[:, 1])) / span
    break6 = (close - np.max(prior6[:, 1])) / span
    prior_inside = min(prev_low - older_low, older_high - prev_high)
    spans = prior3[:, 1] - prior3[:, 2]
    values = {
        "strong_close": (strong, strong >= 0),
        "paired_strong_close": (min(strong, prev_strong), strong >= 0 and prev_strong >= 0),
        "narrow_body": (1 / 3 - body / span, 3 * body <= span),
        "support_wick": (min((prev_open - prev_low - prev_body) / prev_span, break_prior),
                         prev_open - prev_low >= prev_body and close > prev_high),
        "rejection_wick": ((high - close - 2 * body) / span, high - close >= 2 * body),
        "low_overlap": (0.5 - overlap, overlap < 0.5),
        "high_overlap": (overlap - 0.5, overlap >= 0.5),
        "disjoint_ranges": ((low - prev_high) / span, low > prev_high),
        "outside_week": (min(high - prev_high, prev_low - low) / span,
                         high >= prev_high and low <= prev_low and (high > prev_high or low < prev_low)),
        "inside_week": (min(prev_high - high, low - prev_low) / span,
                        high <= prev_high and low >= prev_low and (high < prev_high or low > prev_low)),
        "higher_high_low": (min(high - prev_high, low - prev_low) / span, high > prev_high and low > prev_low),
        "break_1w": (break_prior, break_prior > 0),
        "break_3w": (break3, break3 > 0),
        "break_6w": (break6, break6 > 0),
        "paired_break": (np.minimum(break_prior, (prev_close - older_high) / span),
                         break_prior > 0 and prev_close > older_high),
        "failed_break": (min(high - prev_high, prev_high - close) / span, high > prev_high and close <= prev_high),
        "range_expansion": (min((span - 2 * prev_span) / span, (close - low) / span - 0.75),
                            span >= 2 * prev_span and (close - low) >= 0.75 * span),
        "range_compression": ((prev_span / 2 - span) / prev_span, 2 * span <= prev_span),
        "inside_breakout": (np.minimum(prior_inside / span, (close - older_high) / span),
                            prior_inside >= 0 and (prev_low > older_low or prev_high < older_high) and close > older_high),
        "sweep_then_break": (np.min([(older_low - prev_low) / span, (prev_close - older_low) / span, break_prior]),
                             prev_low < older_low < prev_close and break_prior > 0),
        "compression_break": (np.min([(spans[0] - spans[1]) / span, (spans[1] - spans[2]) / span, break3]),
                              spans[0] > spans[1] > spans[2] and break3 > 0),
        "direction_gap": ((opening - prev_high) / span, opening > prev_high),
    }
    return ({key: bool(match) if np.isfinite(score) else None for key, (score, match) in values.items()},
            {key: float(score) if np.isfinite(score) else None for key, (score, _) in values.items()})


def extract():
    _, _, cycles, fills, _, market, mapping = load(BASE, STAGE025_S44_2022)
    verify(FILTER / "SHA256SUMS", FILTER_SHA)
    hashes = dict((filename, digest) for digest, filename in
                  (line.split(maxsplit=1) for line in (FILTER / "SHA256SUMS").read_text().splitlines()))
    for filename in ("cycles.csv", "fills.csv", "signals.csv", "inputs.json", "summary.json"):
        path = f"overlap50/{filename}"
        verify(FILTER / path, hashes[path])
    candidate = FILTER / "overlap50"
    assert json.loads((candidate / "inputs.json").read_text())["inputs_sha256"] == json.loads((BASE / "inputs.json").read_text())["inputs_sha256"]
    calendar = pd.DataFrame({"date": sorted(mapping.loc[mapping.date.ge("2014-01-01"), "date"].unique())})
    calendar["week"] = calendar.date.dt.to_period("W-SUN")
    weeks = calendar.groupby("week").date.agg(["max", "size"])
    week_index = dict(zip(weeks["max"], range(len(weeks))))
    source = market.merge(calendar, on="date", how="inner", validate="many_to_one").sort_values("date")
    bars = source.groupby(["contract_epoch_id", "week"]).agg(
        open=("open", "first"), high=("high", "max"), low=("low", "min"), close=("close", "last"),
        count=("date", "size"),
    ).reset_index().merge(weeks["size"], left_on="week", right_index=True, validate="many_to_one")
    by_epoch = {
        key: group.loc[group["count"].eq(group["size"])].set_index("week")[OHLC].reindex(weeks.index).to_numpy()
        for key, group in bars.groupby("contract_epoch_id", sort=False)
    }
    records, atlas = [], []
    for name, run, ledger, trades in (
        ("S44", BASE, cycles, fills),
        ("Overlap50", candidate, pd.read_csv(candidate / "cycles.csv", keep_default_na=False),
         pd.read_csv(candidate / "fills.csv", keep_default_na=False)),
    ):
        entries = trades.loc[trades.reason.eq("entry")].set_index("cycle", verify_integrity=True)
        closed = ledger.loc[ledger.exit_day.ne("")]
        signals = pd.read_csv(run / "signals.csv").set_index(["date", "product", "epoch", "action"], verify_integrity=True)
        assert len(closed) == (3484 if name == "S44" else 2347)
        for row in closed.itertuples(index=False):
            fill = entries.loc[row.cycle]
            side = int(row.direction)
            signal = signals.loc[fill.signal_day, row.product, fill.epoch, "open_long" if side == 1 else "open_short"]
            index = week_index[pd.Timestamp(fill.signal_day)]
            assert index >= 9 and fill.signal_day < fill.date == row.entry_day
            raw = by_epoch[fill.epoch][index-9:index+1]
            assert tuple(raw[-3:, 3]) == (signal.older_close, signal.prior_close, signal.close)
            assert raw[-1, 2 if side == 1 else 1] == float(fill.stop)
            oriented = raw if side == 1 else -raw[:, [0, 2, 1, 3]]
            matches, margins = shape_margins(oriented)
            trade = dict(arm=name, cycle=int(row.cycle), product=row.product, contract=fill.contract,
                         direction="多" if side == 1 else "空", signal=fill.signal_day,
                         entry=row.entry_day, exit=row.exit_day, pnl=float(row.net_pnl))
            records.append({**trade, **matches})
            atlas.append({**trade, "rules": [k for k, v in matches.items() if v], "margins": margins,
                          "bars": np.where(np.isfinite(oriented), oriented, None).tolist()})
    return pd.DataFrame(records), atlas


def summarize(trades):
    periods = {
        "发现": trades.entry.lt("2022-01-01") & trades.exit.lt("2022-01-01"),
        "2022": trades.entry.str.startswith("2022"),
        "2023–2024": trades.entry.between("2023-01-01", "2024-12-31"),
        "2025–2026": trades.entry.ge("2025-01-01"),
        "核验": trades.entry.ge("2023-01-01"),
        "全期": trades.entry.ne(""),
    }
    output = []
    for arm in trades.arm.unique():
        for phase, mask in periods.items():
            for direction in ("全部", "多", "空"):
                frame = trades.loc[trades.arm.eq(arm) & mask & (trades.direction.eq(direction) if direction != "全部" else True)]
                for rule in RULES:
                    selected = frame.loc[frame[rule].eq(True)]
                    other = frame.loc[frame[rule].eq(False)]
                    wins = selected.pnl.gt(0)
                    win_rate = wins.mean()
                    baseline = other.pnl.gt(0).mean()
                    output.append(dict(arm=arm, phase=phase, direction=direction, rule=rule, description=RULES[rule],
                                       total=len(frame), total_win_rate=frame.pnl.gt(0).mean(), matches=len(selected),
                                       wins=int(wins.sum()), win_rate=win_rate, nonmatches=len(other),
                                       unknown=len(frame)-len(selected)-len(other), nonmatch_win_rate=baseline,
                                       lift=win_rate-baseline, pnl=selected.pnl.sum(), average_pnl=selected.pnl.mean()))
    return pd.DataFrame(output)


def confidence(trades):
    validation = trades.loc[trades.arm.eq("S44") & trades.entry.ge("2023-01-01")].copy()
    validation["month"] = validation.entry.str[:7]
    months = sorted(validation.month.unique())
    rng = np.random.default_rng(20261104)
    weights = rng.multinomial(len(months), np.full(len(months), 1/len(months)), size=20000)
    rows = []
    alpha = 0.05 / (2 * len(RULES))
    for rule in RULES:
        cells = []
        for positive in (True, False):
            subset = validation.loc[validation[rule].eq(positive)]
            counts = subset.groupby("month").size().reindex(months, fill_value=0).to_numpy()
            wins = subset.loc[subset.pnl.gt(0)].groupby("month").size().reindex(months, fill_value=0).to_numpy()
            numerator, denominator = weights @ wins, weights @ counts
            cells.append(np.divide(numerator, denominator, out=np.full(len(weights), np.nan), where=denominator > 0))
        deltas = cells[0] - cells[1]
        low, high = np.nanquantile(deltas, [alpha, 1-alpha])
        rows.append(dict(rule=rule, lower=float(low), upper=float(high), months=len(months)))
    return pd.DataFrame(rows)


def main():
    OUT.mkdir(parents=True, exist_ok=False)
    trades, atlas = extract()
    stats = summarize(trades)
    bounds = confidence(trades)
    trades.to_csv(OUT / "trade_shapes.csv", index=False, encoding="utf-8-sig")
    stats.to_csv(OUT / "shape_stats.csv", index=False, encoding="utf-8-sig")
    bounds.to_csv(OUT / "validation_intervals.csv", index=False, encoding="utf-8-sig")
    (OUT / "atlas_data.json").write_text(json.dumps(atlas, ensure_ascii=False, allow_nan=False, separators=(",", ":")))
    print(f"Complete episodes: {len(trades)}. Shapes: {len(RULES)}")


if __name__ == "__main__":
    main()
