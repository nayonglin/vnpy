"""Read-only trade-shape attribution on the frozen Stage025 S44 episodes."""
from pathlib import Path
import json

import numpy as np
import pandas as pd

from stage005_trade_recap import LINE, STAGE025_S44_2022, load

OUT = LINE / "outputs/stage027_s44_2022_loss_forensics_v1"
RUN = LINE / "outputs" / STAGE025_S44_2022.run
OHLC = ["open", "high", "low", "close"]
RULES = {
    "no_3w_break": "收盘未越过前三周方向极值",
    "two_bars_overlap": "两根确认周K重叠至少一半短振幅",
    "weak_close": "信号周收在其方向区间下半部",
    "rejection_wick": "信号周逆向影线至少为实体两倍",
    "slow_slopes_adverse": "MA10和MA20斜率均与开仓方向相反",
    "ma20_price_and_slope_adverse": "价格在MA20不利侧且MA20反向",
    "ma10_whipsaw": "过去八周至少三次穿越MA10",
    "short_four_down": "空单已连续四次周收盘下跌",
}


def flag(condition, known=True):
    return bool(condition) if known else None


def extract():
    inputs, _, cycles, fills, _, market, mapping = load(RUN, STAGE025_S44_2022)
    calendar = pd.DataFrame({"date": sorted(mapping.loc[mapping.date.ge("2014-01-01"), "date"].unique())})
    calendar["week"] = calendar.date.dt.to_period("W-SUN")
    weeks = calendar.groupby("week").date.agg(["max", "size"])
    week_index = dict(zip(weeks["max"], range(len(weeks))))
    joined = market.merge(calendar, on="date", how="inner", validate="many_to_one").sort_values("date")
    bars = joined.groupby(["contract_epoch_id", "week"]).agg(
        open=("open", "first"), high=("high", "max"), low=("low", "min"), close=("close", "last"),
        count=("date", "size"),
    ).reset_index()
    bars = bars.merge(weeks["size"], left_on="week", right_index=True, validate="many_to_one")
    by_epoch = {
        key: group.loc[group["count"].eq(group["size"])].set_index("week")[OHLC].reindex(weeks.index)
        for key, group in bars.groupby("contract_epoch_id", sort=False)
    }
    keys = ["date", "product", "epoch", "action"]
    signals = pd.read_csv(RUN / "signals.csv").set_index(keys, verify_integrity=True)
    slopes = pd.read_csv(RUN / "entry_filter.csv").set_index(keys, verify_integrity=True)
    entries = fills.loc[fills.reason.eq("entry")].set_index("cycle", verify_integrity=True)
    exits = fills.loc[fills.reason.isin(["weekly_stop", "delivery_guard_exit"])].set_index("cycle", verify_integrity=True)
    closed = cycles.loc[cycles.exit_day.ne("")]
    recap = pd.read_csv(STAGE025_S44_2022.destination / "chart_manifest.csv").set_index("open_trade_id", verify_integrity=True)
    records, panels = [], []
    for cycle in closed.itertuples(index=False):
        first, last = entries.loc[cycle.cycle], exits.loc[cycle.cycle]
        side = int(cycle.direction)
        date = first.signal_day
        assert date < first.date and first.side == side and last.date == cycle.exit_day
        key = date, cycle.product, first.epoch, "open_long" if side == 1 else "open_short"
        signal, slope = signals.loc[key], slopes.loc[key]
        index = week_index[pd.Timestamp(date)]
        frame = by_epoch[first.epoch].iloc[:index + 1]
        week, prior, older = (frame.iloc[-i] for i in (1, 2, 3))
        assert tuple(frame.close.iloc[-3:]) == (signal.older_close, signal.prior_close, signal.close)
        assert first.stop == str(float(signal.stop)) or float(first.stop) == signal.stop
        assert side * (week.close - prior.close) > 0 and side * (prior.close - older.close) > 0
        assert side * (week.close - week.open) > 0 and side * (prior.close - prior.open) > 0
        assert (week.low if side == 1 else week.high) == signal.stop
        span = week.high - week.low
        previous_span = prior.high - prior.low
        body = side * (week.close - week.open)
        wick = week.high - week.close if side == 1 else week.close - week.low
        pos = 1 - wick / span
        overlap = max(0, min(week.high, prior.high) - max(week.low, prior.low)) / min(span, previous_span)
        previous3 = frame.iloc[-4:-1]
        bound = previous3.high.max() if side == 1 else previous3.low.min()
        bound_known = len(previous3) == 3 and previous3.close.notna().all()
        known_slopes = slope.status != "incomplete"
        ma = {period: frame.close.rolling(period).mean() for period in (5, 10, 20)}
        if known_slopes:
            assert slope.status == "allowed"
            for period, series in ma.items():
                assert np.isclose(series.iloc[-1] - series.iloc[-2], slope[f"ma{period}_slope"])
        else:
            assert pd.isna(slope.ma20_slope)
        ma20 = ma[20].iloc[-1]
        signed_delta = (frame.close - ma[10]).iloc[-8:].to_numpy()
        nonzero = signed_delta[signed_delta != 0]
        cross_count = int((np.sign(nonzero[1:]) != np.sign(nonzero[:-1])).sum()) if len(signed_delta) == 8 and np.isfinite(signed_delta).all() else None
        four_known = len(frame) >= 5 and frame.close.iloc[-5:].notna().all()
        last4_diffs = np.diff(frame.close.iloc[-5:])
        y = first.date[:4]
        pnl = float(cycle.net_pnl)
        records.append(dict(
            cycle=cycle.cycle, product=cycle.product, contract=first.contract, direction="long" if side == 1 else "short",
            signal_date=date, entry_date=first.date, exit_date=last.date, exit_reason=last.reason,
            entry_year=int(y), net_pnl=pnl, signal_open=week.open, signal_high=week.high, signal_low=week.low,
            signal_close=week.close, initial_stop=float(first.stop), prior_open=prior.open, prior_high=prior.high,
            prior_low=prior.low, prior_close=prior.close, older_close=older.close,
            directional_close_position=pos, adverse_wick_body=wick / body, overlap_shorter_range=overlap,
            directional_3w_break_distance=side * (week.close - bound) if bound_known else None,
            ma5_slope=slope.ma5_slope, ma10_slope=slope.ma10_slope, ma20_slope=slope.ma20_slope,
            ma20=ma20, ma10_crosses_8w=cross_count,
            no_3w_break=flag(side * (week.close - bound) <= 0, bound_known),
            two_bars_overlap=flag(overlap >= 0.5), weak_close=flag(pos < 0.5),
            rejection_wick=flag(wick >= 2 * body),
            slow_slopes_adverse=flag(side * slope.ma10_slope < 0 and side * slope.ma20_slope < 0, known_slopes),
            ma20_price_and_slope_adverse=flag(side * (week.close - ma20) < 0 and side * slope.ma20_slope < 0, known_slopes),
            ma10_whipsaw=flag(cross_count is not None and cross_count >= 3, cross_count is not None),
            short_four_down=flag(side == -1 and np.all(last4_diffs < 0), side == 1 or four_known),
        ))
        if y == "2022" and pnl < 0:
            match = recap.loc[cycle.cycle]
            assert match.realized_pnl == pnl and match.entry_date == first.date and match.exit_date == last.date
            view = frame.tail(14).assign(**{f"ma{k}": v for k, v in ma.items()})
            panels.append(dict(cycle=cycle.cycle, contract=first.contract, side=side, signal=date, pnl=pnl,
                               bars=json.loads(view.to_json(orient="records"))))
    table = pd.DataFrame(records)
    assert len(table) == 3484 and len(panels) == 206
    assert table.loc[table.entry_year.eq(2022), "net_pnl"].sum() == -42365
    table.to_csv(OUT / "trade_features.csv", index=False)
    (OUT / "chart_inputs.json").write_text(json.dumps(panels, ensure_ascii=False))
    groups = []
    for segment, match in {
        "2015–2021": table.entry_year.lt(2022), "2022": table.entry_year.eq(2022),
        "2023–2026": table.entry_year.gt(2022), **{
            str(y): table.entry_year.eq(y) for y in range(2015, 2027) if y != 2022
        },
    }.items():
        for side in ("all", "long", "short"):
            sub = table.loc[match & (table.direction.eq(side) if side != "all" else True)]
            for rule, description in RULES.items():
                valid = sub.loc[sub[rule].notna()]
                blocked = valid.loc[valid[rule].eq(True)]
                groups.append(dict(
                    period=segment, direction=side, rule=rule, description=description, total=len(sub),
                    eligible=len(valid), unknown=len(sub)-len(valid), loss_all=int(sub.net_pnl.lt(0).sum()),
                    win_all=int(sub.net_pnl.gt(0).sum()), loss_eligible=int(valid.net_pnl.lt(0).sum()),
                    win_eligible=int(valid.net_pnl.gt(0).sum()), selected=len(blocked),
                    loss_selected=int(blocked.net_pnl.lt(0).sum()), win_selected=int(blocked.net_pnl.gt(0).sum()),
                    gross_loss=float(blocked.loc[blocked.net_pnl.lt(0), "net_pnl"].sum()),
                    gross_profit=float(blocked.loc[blocked.net_pnl.gt(0), "net_pnl"].sum()),
                    selected_net_pnl=float(blocked.net_pnl.sum()),
                ))
    pd.DataFrame(groups).to_csv(OUT / "filter_attribution.csv", index=False)


if __name__ == "__main__":
    extract()
