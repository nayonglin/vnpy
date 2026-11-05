"""Replay the user-approved Stage058 ten-product universe at 24 independent starts."""
import argparse
import json
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go

import stage056_random10_touch as study

LINE = study.LINE
SELECTION = LINE / "outputs/stage058_diverse10_20261103"
SELECTION_SHA = "6608ae55e4fdf9aadd9302077951efefbaa297f0762988eefef6024b2824dd3f"
AUDIT = LINE / "reviews/stage058_diverse10_audit.json"
AUDIT_SHA = "51bdd13cf78574792416de372528388d7a0d6b430e119010da817462a58562b1"
STUDY_SHA = "149c099aa9c336cf82dd0414a62b99ec38cc7a181f7fb991643350f87fbe725c"
DESIGN = LINE / "stages/20261105_1315_stage059_diverse10_halfyear_design.md"


def report(output, selected):
    metrics = pd.read_csv(output / "window_metrics.csv")
    table = metrics.loc[metrics.group.eq("D10"), [
        "calendar_start", "equity", "return_pct", "max_dd_pct", "sharpe", "closed_cycles",
        "fills", "win_rate_pct", "slippage", "commission", "deficit_days", "blocked_total",
    ]].rename(columns={
        "calendar_start": "起点", "equity": "期末权益（元）", "return_pct": "累计收益（%）",
        "max_dd_pct": "最大回撤（%）", "sharpe": "Sharpe", "closed_cycles": "完整交易数",
        "fills": "成交笔数", "win_rate_pct": "胜率（%）", "slippage": "滑点（元）",
        "commission": "手续费（元）", "deficit_days": "资金缺口天数", "blocked_total": "资金拒单数",
    })
    comparison = metrics.pivot(index="calendar_start", columns="group",
                               values=["return_pct", "max_dd_pct", "closed_cycles"])
    comparison.to_csv(output / "paired_comparison.csv")
    figure = go.Figure()
    for arm, folder in (("原21品种", study.BASELINE / "2015-01-01"),
                        ("精选10品种", output / "D10/2015-01-01")):
        daily = pd.read_csv(folder / "daily.csv")
        figure.add_scatter(x=daily.date, y=daily.equity / 10000, name=arm, mode="lines")
    figure.update_layout(template="plotly_white", title="2015年起账户权益", yaxis_title="万元",
                         height=500, hovermode="x unified")
    page = f"""<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<title>精选十品种逐半年回测</title><style>
body{{font-family:system-ui,sans-serif;color:#203047;margin:28px;line-height:1.6}}
table{{border-collapse:collapse;white-space:nowrap;font-size:14px;width:100%}}
th,td{{padding:8px;border:1px solid #d7deea;text-align:right}}th{{background:#edf2f8}}
tbody tr:nth-child(even){{background:#f7f9fc}}.scroll{{overflow:auto;margin:20px 0}}
</style><h1>精选十品种逐半年回测</h1>
<p>初始资金15万元，固定一手，周K入场，全品种触价止损。24个起点独立空仓启动，统一截止2026-11-04。</p>
<p>冻结品种 {', '.join(selected)}。</p>
<p>名单按当前相关性选出，历史回测存在选池前视偏差。触价用日OHLC代理，计滑点、零手续费。
新开资金不足拒单，已有仓位波动仍可能产生资金缺口。上市前数据不补造。</p>
{figure.to_html(full_html=False, include_plotlyjs=True, config={'responsive': True})}
<h2>十品种全部24个起点</h2><div class="scroll">{table.to_html(index=False, float_format=lambda x:f'{x:,.2f}')}</div>
<h2>与原21品种同日起点比较</h2><div class="scroll">{comparison.to_html(float_format=lambda x:f'{x:,.2f}')}</div>
<p>完整交易为开仓到最终平仓的一个周期。成交笔数还包含换月各次成交及未结束仓位的开仓成交。</p>
<p>收益为各起点至共同截止日的累计收益。</p></html>"""
    (output / "comparison.html").write_text(page)


def run(output):
    study.base.verify_manifest(SELECTION, SELECTION_SHA)
    if (study.base.portfolio.sha(AUDIT) != AUDIT_SHA
            or study.base.portfolio.sha(Path(study.__file__)) != STUDY_SHA):
        raise ValueError("approved selection audit or replay adapter changed")
    selection = study.prior.read_json(SELECTION / "selection.json")
    selected = selection["selected"]
    if (len(selected) != 10 or len(set(selected)) != 10
            or selection["status"] != "SELECTED_FOR_RESEARCH"):
        raise ValueError("invalid approved ten-product universe")
    _, frozen, market = study.frozen_market()
    final_symbol = market[6].get((study.base.TARGET, "ni.SHFE"))
    if final_symbol != "ni2612.SHFE" or (study.base.TARGET, final_symbol) not in market[4]:
        raise ValueError("admitted nickel final-day main contract unavailable")
    if not set(selected).issubset(set(market[0]) | {"ni.SHFE"}):
        raise ValueError("selection changed beyond approved products")
    output.mkdir(parents=True)
    engine, reconstruct = study.parent.build_engine()
    start = study.prior.STARTS[0]
    study.replay(output / "validation_s21", start, market, engine, reconstruct)
    for name in ("daily.csv", "fills.csv", "cycles.csv", "signals.csv", "terminal.json", "touch_stops.csv",
                 "risk_sizing.csv", "opening_funding.csv", "inputs.json", "summary.json"):
        if (output / "validation_s21" / name).read_bytes() != (study.BASELINE / start / name).read_bytes():
            raise ValueError(f"S21 control replay changed: {name}")
    print("S21 control byte match PASS; admitted nickel tail available", flush=True)

    reference = pd.read_csv(study.BASELINE / "window_metrics.csv", keep_default_na=False)
    rows = []
    for row in reference.to_dict("records"):
        metrics = {key.removeprefix("all_touch_"): value for key, value in row.items()
                   if key.startswith("all_touch_")}
        rows.append(dict(group="S21", calendar_start=row["calendar_start"],
                         **{key: row[key] for key in ("first_session", "last_session", "days")}, **metrics))
    subset = (selected, *market[1:])
    for start in study.prior.STARTS:
        folder = output / "D10" / start
        metrics = study.replay(folder, start, subset, engine, reconstruct)
        terminal = study.prior.read_json(folder / "terminal.json")
        if any((study.base.TARGET, position["epoch"]) not in market[5]
               for position in terminal["positions"].values()):
            raise ValueError(f"final-day held-contract coverage missing: {start}")
        rows.append(dict(group="D10", calendar_start=start, **metrics))
        print(start, metrics["equity"], metrics["return_pct"], metrics["max_dd_pct"],
              metrics["closed_cycles"], metrics["fills"], flush=True)
    design = dict(parent_products=market[0], groups={"D10": selected}, starts=study.prior.STARTS)
    study.write_analysis(output, design, rows)
    report(output, selected)
    receipt = dict(
        schema="stage059_approved_diverse10_halfyear_v1", selected=selected, starts=study.prior.STARTS,
        capital=study.base.CAPITAL, cutoff=study.base.TARGET, attempted_runs=24, completed_runs=24,
        unknown_runs=0, control_validation_runs=1, stage058_manifest_sha256=SELECTION_SHA,
        stage058_audit_sha256=AUDIT_SHA, stage056_entrypoint_sha256=STUDY_SHA,
        stage055_manifest_sha256=study.prior.read_json(study.FROZEN)["stage055_manifest_sha256"],
        stage055_entrypoint_sha256=frozen["entrypoint_sha256"],
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
