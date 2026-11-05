"""Change only S21 initial capital to RMB 200,000 at 24 independent starts."""
import argparse
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go

import stage056_random10_touch as study

LINE = study.LINE
CAPITAL = 200_000
ARM = "S21_20w"
STUDY_SHA = "149c099aa9c336cf82dd0414a62b99ec38cc7a181f7fb991643350f87fbe725c"
DESIGN = LINE / "stages/20261105_1322_stage060_s21_200k_design.md"


def replay(folder, start, market, engine, reconstruct):
    engine["START"] = start
    with redirect_stdout(StringIO()):
        engine["run"](folder, week_body_filter=True, reverse_after_stop=True,
                      block_four_up=True, delivery_guard=True, market_loader=lambda: market)
    inputs = study.prior.read_json(folder / "inputs.json")
    inputs["fixed_one_margin_gate"] = study.parent.gold.parent.GATE
    inputs["all_products_stop_rule"] = study.parent.RULE
    expected = {**study.prior.read_json(study.BASELINE / start / "inputs.json"), "initial": CAPITAL}
    if inputs != expected:
        raise ValueError(f"configuration changed beyond initial capital: {start}")
    (folder / "inputs.json").write_text(json.dumps(inputs, indent=2) + "\n")
    daily = pd.read_csv(folder / "daily.csv")
    fills = pd.read_csv(folder / "fills.csv")
    stops = pd.read_csv(folder / "touch_stops.csv")
    opening = reconstruct(daily, fills, market)
    opening.to_csv(folder / "opening_funding.csv", index=False)
    if (daily.date.tolist() != [day for day in market[1] if day >= start]
            or daily.cash.iat[0] != CAPITAL or daily.positions.iat[0] != 0
            or daily.date.iat[-1] != study.base.TARGET or not fills.volume.eq(1).all()
            or not fills["product"].isin(market[0]).all()
            or study.parent.gold.parent.opening_checks(fills, opening) != (0, 0)
            or fills.reason.eq("weekly_stop").any() or stops.one_price.any()
            or not (stops.anchor_day.lt(stops.trigger_day) & stops.trigger_day.le(stops.date)).all()
            or not stops.trigger_day.lt(stops.date).equals(stops.reason.eq(study.parent.DELAYED))):
        raise ValueError(f"calendar, sizing, funding or stop violation: {start}")
    columns = ["date", "product", "contract", "epoch", "cycle", "price", "stop", "reason", "one_price"]
    stop_fills = fills.loc[fills.reason.isin((study.parent.OPEN_GAP, study.parent.INTRADAY, study.parent.DELAYED))]
    pd.testing.assert_frame_equal(stops[columns], stop_fills[columns].reset_index(drop=True),
                                  check_dtype=False, rtol=0, atol=1e-8)
    sizing = pd.read_csv(folder / "risk_sizing.csv")
    admitted = sizing.executed_lots.eq(1)
    required = (sizing.margin_per_lot + sizing.entry_cost_per_lot).round(8)
    if not admitted.equals(sizing.free_cash.ge(required)) or not sizing.requested_lots.eq(1).all():
        raise ValueError(f"opening margin decision incorrect: {start}")
    summary = study.prior.read_json(folder / "summary.json")
    metrics = study.prior.funding_metrics(folder, daily, opening, summary)
    summary["days_margin_above_equity"] = metrics["close_deficit_days"]
    (folder / "summary.json").write_text(json.dumps(summary, indent=2, allow_nan=False) + "\n")
    terminal = study.prior.read_json(folder / "terminal.json")
    if any((study.base.TARGET, position["epoch"]) not in market[5]
           for position in terminal["positions"].values()):
        raise ValueError(f"final-day holding has no physical price: {start}")
    gaps = pd.read_csv(folder / "gaps.csv")
    return dict(
        first_session=daily.date.iat[0], last_session=daily.date.iat[-1], days=len(daily), **metrics,
        stop_count=len(stops), open_gap_count=int(stops.reason.eq(study.parent.OPEN_GAP).sum()),
        intraday_count=int(stops.reason.eq(study.parent.INTRADAY).sum()),
        delayed_count=int(stops.reason.eq(study.parent.DELAYED).sum()),
        locked_count=int(gaps.reason.eq("touch_trigger_one_price").sum()),
        missing_bars=int(gaps.reason.eq("touch_stop_day_unavailable").sum()),
        blocked_total=int((~admitted).sum()),
    )


def path_comparison(output):
    result = []
    for start in study.prior.STARTS:
        old, new = study.BASELINE / start, output / ARM / start
        same_fills = (old / "fills.csv").read_bytes() == (new / "fills.csv").read_bytes()
        old_daily, new_daily = pd.read_csv(old / "daily.csv"), pd.read_csv(new / "daily.csv")
        if same_fills:
            np.testing.assert_allclose(new_daily.equity - old_daily.equity, CAPITAL - study.base.CAPITAL,
                                       rtol=0, atol=1e-7)
            for key in ("net_pnl", "margin", "cumulative_slippage", "cumulative_commission", "positions"):
                np.testing.assert_allclose(new_daily[key], old_daily[key], rtol=0, atol=1e-7)
        old_summary, new_summary = (study.prior.read_json(p / "summary.json") for p in (old, new))
        result.append(dict(calendar_start=start, same_fills=same_fills,
                           net_pnl_delta=new_summary["net_pnl"] - old_summary["net_pnl"],
                           equity_delta=new_summary["equity"] - old_summary["equity"],
                           return_pct_delta=new_summary["return_pct"] - old_summary["return_pct"],
                           max_dd_pct_delta=new_summary["max_dd_pct"] - old_summary["max_dd_pct"]))
    pd.DataFrame(result).to_csv(output / "path_comparison.csv", index=False)


def report(output):
    metrics = pd.read_csv(output / "window_metrics.csv")
    selected = metrics.loc[metrics.group.eq(ARM), [
        "calendar_start", "equity", "net_pnl", "return_pct", "max_dd_pct", "sharpe", "closed_cycles",
        "fills", "win_rate_pct", "deficit_days", "blocked_total",
    ]].rename(columns={
        "calendar_start": "起点", "equity": "期末权益（元）", "net_pnl": "净损益（元）",
        "return_pct": "累计收益（%）", "max_dd_pct": "最大回撤（%）", "sharpe": "Sharpe",
        "closed_cycles": "完整交易数", "fills": "成交笔数", "win_rate_pct": "胜率（%）",
        "deficit_days": "资金缺口天数", "blocked_total": "资金拒单数",
    })
    paired = metrics.pivot(index="calendar_start", columns="group",
                           values=["net_pnl", "return_pct", "max_dd_pct", "closed_cycles", "deficit_days"])
    paired.to_csv(output / "paired_comparison.csv")
    figure = go.Figure()
    for name, folder, initial in (("原15万元", study.BASELINE / "2015-01-01", study.base.CAPITAL),
                                  ("20万元", output / ARM / "2015-01-01", CAPITAL)):
        daily = pd.read_csv(folder / "daily.csv")
        figure.add_scatter(x=daily.date, y=daily.equity / initial, name=name, mode="lines")
    figure.update_layout(template="plotly_white", title="2015年起账户净值", yaxis_title="净值",
                         height=500, hovermode="x unified")
    page = f"""<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>21品种20万元逐半年回测</title>
<style>body{{font-family:system-ui,sans-serif;margin:28px;color:#203047;line-height:1.6}}
table{{border-collapse:collapse;white-space:nowrap;font-size:14px;width:100%}}
th,td{{padding:8px;border:1px solid #d7deea;text-align:right}}th{{background:#edf2f8}}
.scroll{{overflow:auto;margin:20px 0}}</style><h1>21品种 · 20万元逐半年回测</h1>
<p>固定一手，全品种触价止损，24个独立空仓起点，统一截止2026-11-04。唯一参数变化为初始资金15万至20万元。</p>
<p>收益率分母按各自本金计算。保证金门槛可能改变可成交请求，因此同时比较净损益与交易路径。</p>
{figure.to_html(full_html=False, include_plotlyjs=True, config={'responsive': True})}
<h2>20万元版全部24个起点</h2><div class="scroll">{selected.to_html(index=False, float_format=lambda v:f'{v:,.2f}')}</div>
<h2>与15万元版同起点对比</h2><div class="scroll">{paired.to_html(float_format=lambda v:f'{v:,.2f}')}</div>
<p>历史触价使用日OHLC代理，计滑点，手续费为零。已有仓位波动可能产生资金缺口，新开资金不足会拒单。
重叠起点和原策略/品种池的历史选择偏差保留。完整交易为开仓至最终平仓，成交笔数包含换月各次成交。</p></html>"""
    (output / "comparison.html").write_text(page)


def run(output):
    if study.base.portfolio.sha(Path(study.__file__)) != STUDY_SHA:
        raise ValueError("frozen study adapter changed")
    _, frozen, market = study.frozen_market()
    output.mkdir(parents=True)
    engine, reconstruct = study.parent.build_engine()
    start = study.prior.STARTS[0]
    study.replay(output / "validation_s21", start, market, engine, reconstruct)
    for name in ("daily.csv", "fills.csv", "cycles.csv", "signals.csv", "terminal.json", "touch_stops.csv",
                 "risk_sizing.csv", "opening_funding.csv", "inputs.json", "summary.json"):
        if (output / "validation_s21" / name).read_bytes() != (study.BASELINE / start / name).read_bytes():
            raise ValueError(f"15w control changed: {name}")
    if reconstruct.__globals__ is study.base.reconstruct_opening.__globals__:
        raise ValueError("capital override must use an isolated reconstruction namespace")
    engine["INITIAL"] = CAPITAL
    reconstruct.__globals__["CAPITAL"] = CAPITAL
    print("15w control PASS; isolated initial capital set to", CAPITAL, flush=True)
    rows = []
    for row in pd.read_csv(study.BASELINE / "window_metrics.csv", keep_default_na=False).to_dict("records"):
        metrics = {key.removeprefix("all_touch_"): value for key, value in row.items()
                   if key.startswith("all_touch_")}
        rows.append(dict(group="S21", calendar_start=row["calendar_start"],
                         **{key: row[key] for key in ("first_session", "last_session", "days")}, **metrics))
    for start in study.prior.STARTS:
        metrics = replay(output / ARM / start, start, market, engine, reconstruct)
        rows.append(dict(group=ARM, calendar_start=start, **metrics))
        print(start, metrics["equity"], metrics["return_pct"], metrics["max_dd_pct"],
              metrics["closed_cycles"], metrics["fills"], metrics["blocked_total"], flush=True)
    study.write_analysis(output, dict(parent_products=market[0], groups={ARM: market[0]},
                                     starts=study.prior.STARTS), rows)
    path_comparison(output)
    report(output)
    receipt = dict(
        schema="stage060_s21_200k_halfyear_v1", capital=CAPITAL, baseline_capital=study.base.CAPITAL,
        products=market[0], starts=study.prior.STARTS, cutoff=study.base.TARGET,
        attempted_runs=24, completed_runs=24, unknown_runs=0, control_validation_runs=1,
        stage055_manifest_sha256=study.prior.read_json(study.FROZEN)["stage055_manifest_sha256"],
        stage056_entrypoint_sha256=STUDY_SHA, stage055_entrypoint_sha256=frozen["entrypoint_sha256"],
        stage054_entrypoint_sha256=frozen["stage054_entrypoint_sha256"],
        stage052_entrypoint_sha256=frozen["stage052_entrypoint_sha256"], engine_sha256=frozen["engine_sha256"],
        market_sha256=frozen["market_sha256"], gate=frozen["gate"],
        all_products_stop_rule=frozen["all_products_stop_rule"],
        design_sha256=study.base.portfolio.sha(DESIGN),
        entrypoint_sha256=study.base.portfolio.sha(Path(__file__)),
    )
    (output / "receipt.json").write_text(json.dumps(receipt, indent=2, allow_nan=False) + "\n")
    study.base.write_checksums(output, (p for p in output.rglob("*") if p.is_file()))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    run(parser.parse_args().output)
