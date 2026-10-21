"""Offline .25%/.5%/1% chart from completed685 and accepted682 delivery.

Only the two new .5% daily books and small saved visualization tables are read.
The prior four accounts are reused from accepted682, never audited or replayed
again. A normal browser button exports PNG; --register-png binds the download.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import struct


LINE = Path(__file__).resolve().parents[1]
HELPER_PATH = Path(__file__).with_name("stage682_plot_onepct_comparison.py")
HELPER_SHA = "ae51911348d1a3d7ca3a0e3e715a3b6e169af2e5b94d77929728979af45740f6"
if hashlib.sha256(HELPER_PATH.read_bytes()).hexdigest() != HELPER_SHA:
    raise ValueError("accepted682 helper source changed")
_spec = importlib.util.spec_from_file_location("delivery687_accepted682", HELPER_PATH)
_helper = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_helper)
binding, document, table = _helper.binding, _helper.document, _helper.table
read_bound, write_json, write_csv = _helper.read_bound, _helper.write_json, _helper.write_csv
finite, close, drawdowns = _helper.finite, _helper.close, _helper.drawdowns

INITIAL = 1_000_000.0
START, END = "2015-01-05", "2026-10-16"
COSTS = ("base", "stress")
RISKS = ("risk025", "risk050", "risk100")
KEYS = tuple(risk + "_" + cost for risk in RISKS for cost in COSTS)
OLD_KEYS = tuple(risk + "_" + cost for risk in ("risk025", "risk100") for cost in COSTS)
PLOT_KEYS = tuple(risk + "_" + cost for cost in COSTS for risk in RISKS)
WIDE_FIELDS = ["date"] + [key + "_" + metric for key in KEYS for metric in ("equity", "drawdown_pct")]
ARM = "VOLUNTARY_RESELECT"
CHART_ID = "common52_halfpct_comparison"
HTML_NAME = "equity_curve_halfpct_comparison.html"
PNG_NAME = "equity_curve_halfpct_comparison.png"
WIDTH, HEIGHT = 1600, 1200
RISK_LABELS = {"risk025": "0.25%", "risk050": "0.5%", "risk100": "1%"}
LABELS = {risk + "_" + cost: RISK_LABELS[risk] + ("｜基础" if cost == "base" else "｜压力")
          for risk in RISKS for cost in COSTS}
COLORS = {"risk025_base": "#73a7d4", "risk050_base": "#2c75b6", "risk100_base": "#163c6b",
          "risk025_stress": "#d9b07c", "risk050_stress": "#c5742a", "risk100_stress": "#8b421b"}
DASHES = {"risk025": "dash", "risk050": "solid", "risk100": "dot"}
ANNUAL_NUMERIC_FIELDS = {"starting_equity", "ending_equity", "cash_growth", "return_pct", "max_drawdown_pct"}


def read_candidate(account):
    cost = account["cost"]
    name = "all_2015_halfpct_" + cost
    if (cost not in COSTS or account.get("account_id") != name
            or account.get("window") != "all_2015" or account.get("arm") != ARM):
        raise ValueError("fixed685 account identity differs")
    summary = document(account["summary"])
    if (summary.get("cost") != cost or summary.get("account_id", name) != name
            or summary.get("arm", ARM) != ARM or summary.get("window", "all_2015") != "all_2015"):
        raise ValueError("half-percent summary identity differs")
    for field in ("execution_unknown", "any_historical_stale"):
        if type(summary.get(field)) is not bool:
            raise ValueError("actual candidate boolean disclosure required: " + field)
    fields, rows = table(account["ledgers"]["daily"])
    if not rows or not {"date", "equity"}.issubset(fields):
        raise ValueError("empty or malformed685 daily")
    dates = [row["date"] for row in rows]
    if (any(date.fromisoformat(day).isoformat() != day for day in dates)
            or dates != sorted(set(dates)) or dates[0] != START or dates[-1] != END):
        raise ValueError("fixed685 daily dates differ")
    equity = [finite(row["equity"], name + " equity") for row in rows]
    dd = drawdowns(equity)
    close(equity[-1], summary["ending_equity"], name + " ending equity")
    close(min([0.0] + dd), summary["max_drawdown_pct"], name + " drawdown", atol=1e-7)
    close((equity[-1] / INITIAL - 1) * 100, summary["total_return_pct"], name + " total return")
    if "initial_capital" in summary:
        close(summary["initial_capital"], INITIAL, name + " initial capital")
    return dict(account_id=name, risk="risk050", cost=cost, dates=dates, equity=equity,
                drawdown_pct=dd, summary=summary)


def protocol_for(manifest):
    protocol = document(manifest["protocol"])
    if (protocol.get("schema") != "stage684_single_risk_halfpct_protocol_v1"
            or protocol.get("status") != "frozen_before_halfpct_candidate_outcomes"):
        raise ValueError("fixed684 protocol required")
    change, fixed, window = protocol["change"], protocol["fixed"], protocol["window"]
    if change.get("parameter") != "SINGLE_RISK" or change.get("other_parameters_changed") is not False:
        raise ValueError("only authorized single risk change required")
    close(change["old"], 0.0025, "684 original single risk", atol=0)
    close(change["new"], 0.005, "684 new single risk", atol=0)
    for key, value in (("TOTAL_RISK", 0.02), ("MARGIN_CAP", 0.25), ("MARGIN_BUFFER", 1.1)):
        close(fixed[key], value, "684 fixed " + key, atol=0)
    close(window["initial_equity"], INITIAL, "684 initial capital", atol=0)
    if (window.get("first_actual_source_day") != START or window.get("end") != END
            or window.get("continuous") is not True or protocol["limits"].get("new_fit") != 0
            or protocol["limits"].get("new_cash") != 2 or protocol["limits"].get("risk_grid_scan") is not False):
        raise ValueError("fixed684 window/budget differs")
    if manifest["input_bindings"]["baseline_manifest"] != protocol["inputs"]["baseline_manifest"]:
        raise ValueError("685 did not use the frozen675 reference")
    plot = protocol["plot_contract"]
    if (plot.get("wide_fields") != WIDE_FIELDS or plot.get("include_all_prior_arms") is not True
            or plot.get("new_financial_runs") != 0 or plot.get("annual_rows") != 6 * len(range(2015, 2027))
            or plot.get("daily_rows") != window["source_days"]):
        raise ValueError("684 six-account visual contract differs")
    effect = document(manifest["parameter_effectiveness_receipt"])
    for key, value in (("SINGLE_RISK", 0.005), ("TOTAL_RISK", 0.02), ("MARGIN_CAP", 0.25),
                       ("MARGIN_BUFFER", 1.1), ("initial_stop_N", 0.25)):
        close(effect["effective"][key], value, "actual effective " + key, atol=0)
    if effect.get("old_globals_unchanged") is not True:
        raise ValueError("685 did not preserve original globals")
    return protocol


def prior_accounts(prior_path, protocol):
    prior_binding = binding(prior_path)
    prior = document(prior_binding)
    if (prior.get("schema") != "stage682_onepct_comparison_delivery_v1"
            or prior.get("status") != "completed_browser_png_registered"
            or set(prior.get("accounts", {})) != set(OLD_KEYS)
            or prior.get("source_start") != START or prior.get("source_end") != END
            or prior.get("full_daily_frequency") is not True or prior.get("continuous_cash") is not True
            or prior.get("no_mixed_start_splice") is not True):
        raise ValueError("accepted completed682 four-account visual delivery required")
    close(prior["initial_capital"], INITIAL, "682 initial capital", atol=0)
    close(prior["total_risk_cap"], 0.02, "682 total risk cap", atol=0)
    for expected in (protocol["inputs"]["baseline_manifest"], protocol["references"]["onepct_manifest"]):
        if expected not in prior["source_bindings"]:
            raise ValueError("682 source manifest does not match frozen684 reference")
    fields, rows = table(prior["artifacts"]["daily_csv"])
    expected_fields = ["date"] + [key + "_" + metric for key in OLD_KEYS for metric in ("equity", "drawdown_pct")]
    if fields != expected_fields or not rows:
        raise ValueError("accepted682 visual table schema differs")
    dates = [row["date"] for row in rows]
    if dates != sorted(set(dates)) or dates[0] != START or dates[-1] != END:
        raise ValueError("accepted682 visual dates differ")
    accounts = {}
    for key in OLD_KEYS:
        saved = prior["accounts"][key]
        risk, cost = key.split("_")
        expected_name = ("all_2015_" if risk == "risk025" else "all_2015_onepct_") + cost
        if saved.get("account_id") != expected_name or saved.get("daily_rows") != len(rows):
            raise ValueError("accepted682 account metadata differs")
        for field in ("execution_unknown", "any_historical_stale"):
            if type(saved.get(field)) is not bool:
                raise ValueError("accepted682 actual disclosure missing")
        equity = [finite(row[key + "_equity"], key + " saved equity") for row in rows]
        dd = [finite(row[key + "_drawdown_pct"], key + " saved drawdown") for row in rows]
        close(equity[-1], saved["ending_equity"], key + " saved visual ending equity")
        close(min([0.0] + dd), saved["max_drawdown_pct"], key + " saved visual drawdown")
        accounts[key] = dict(account_id=expected_name, risk=risk, cost=cost, dates=dates,
                             equity=equity, drawdown_pct=dd, summary=saved)
    annual_fields, annual_rows = _helper.validate_annual(prior["artifacts"]["annual_csv"], accounts, OLD_KEYS)
    return accounts, annual_fields, annual_rows, prior, prior_binding


def validate_candidate_curve(item, accounts):
    fields, rows = table(item)
    keys = tuple(risk + "_" + cost for risk in ("risk025", "risk050") for cost in COSTS)
    expected = ["date"] + [key + "_" + metric for key in keys for metric in ("equity", "drawdown_pct")]
    if fields != expected or [r["date"] for r in rows] != accounts[KEYS[0]]["dates"]:
        raise ValueError("685 four-curve schema/dates differ")
    for key in keys:
        for row, equity, dd in zip(rows, accounts[key]["equity"], accounts[key]["drawdown_pct"]):
            close(row[key + "_equity"], equity, key + " saved curve equity")
            close(row[key + "_drawdown_pct"], dd, key + " saved curve drawdown", atol=1e-7)


def combine_annual(candidate_binding, accounts, old_fields, old_rows):
    candidate_keys = tuple(risk + "_" + cost for risk in ("risk025", "risk050") for cost in COSTS)
    fields, rows = _helper.validate_annual(candidate_binding, accounts, candidate_keys)
    if fields != old_fields:
        raise ValueError("685 and accepted682 annual columns differ")
    baseline_names = {accounts["risk025_" + cost]["account_id"] for cost in COSTS}
    old_base = {(row["account"], row["year"]): row for row in old_rows if row["account"] in baseline_names}
    copied_base = {(row["account"], row["year"]): row for row in rows if row["account"] in baseline_names}
    if set(old_base) != set(copied_base):
        raise ValueError("685 annual baseline identities differ from accepted682")
    changed = 0
    for key, expected in old_base.items():
        actual = copied_base[key]
        for column in fields:
            left, right = actual[column], expected[column]
            if left == right:
                continue
            if column not in ANNUAL_NUMERIC_FIELDS:
                raise ValueError("annual baseline identity changed: " + column)
            a, b = finite(left, column), finite(right, column)
            if a != b or math.copysign(1, a) != math.copysign(1, b):
                raise ValueError("annual baseline numeric value changed: " + column)
            changed += 1
    candidate_names = {accounts["risk050_" + cost]["account_id"] for cost in COSTS}
    combined = old_rows + [row for row in rows if row["account"] in candidate_names]
    order = {accounts[key]["account_id"]: index for index, key in enumerate(KEYS)}
    combined.sort(key=lambda row: (order[row["account"]], row["year"]))
    return fields, combined, changed


def figure_for(accounts):
    from plotly import graph_objects as go
    from plotly.subplots import make_subplots

    figure = make_subplots(rows=3, cols=1, shared_xaxes=True, row_heights=[0.36, 0.36, 0.28],
        vertical_spacing=0.085, subplot_titles=["基础成本｜三种风险的连续账户权益", "压力成本｜三种风险的连续账户权益", "六账户回撤｜含初始资金峰值"])
    for key in PLOT_KEYS:
        account = accounts[key]
        style = dict(color=COLORS[key], width=2.5 if account["risk"] == "risk050" else 1.8,
                     dash=DASHES[account["risk"]])
        label = LABELS[key] + f"｜期末 {account['equity'][-1] / 10_000:,.2f} 万"
        figure.add_trace(go.Scatter(x=account["dates"], y=[v / 10_000 for v in account["equity"]],
            name=label, legendgroup=key, mode="lines", line=style,
            hovertemplate=LABELS[key] + "：%{y:,.2f} 万元<extra></extra>"),
            row=1 if account["cost"] == "base" else 2, col=1)
        figure.add_trace(go.Scatter(x=account["dates"], y=account["drawdown_pct"],
            name=LABELS[key] + "回撤", legendgroup=key, showlegend=False, mode="lines", line=style,
            hovertemplate=LABELS[key] + "回撤：%{y:.2f}%<extra></extra>"), row=3, col=1)
    for row in (1, 2):
        figure.add_hline(y=100.0, line=dict(color="#8a98a9", width=1, dash="dot"), row=row, col=1)
    figure.add_hline(y=0, line=dict(color="#8a98a9", width=1), row=3, col=1)
    unknown = "；".join(LABELS[key] + (" 是" if accounts[key]["summary"]["execution_unknown"] else " 否") for key in KEYS)
    stale = "；".join(LABELS[key] + (" 是" if accounts[key]["summary"]["any_historical_stale"] else " 否") for key in KEYS)
    figure.update_layout(template="plotly_white", width=WIDTH, height=HEIGHT,
        title=dict(text="COMMON52＋K｜单品种风险 0.25% / 0.5% / 1% 连续资金对照"
            + f"<br><sup>{START}—{END} · 初始 100 万元 · 总风险上限 2% 不变</sup>"
            + "<br><sup>execution_unknown：" + unknown + "</sup>",
            x=0.055, y=0.975, xanchor="left", yanchor="top", font=dict(size=24, color="#173148")),
        font=dict(family="PingFang SC, Microsoft YaHei, Noto Sans CJK SC, Arial, sans-serif", size=13, color="#30455a"),
        paper_bgcolor="#f7f9fc", plot_bgcolor="#ffffff", hovermode="x unified",
        margin=dict(l=100, r=55, t=230, b=135),
        legend=dict(orientation="h", entrywidthmode="fraction", entrywidth=1 / 3,
                    x=0, y=1.065, xanchor="left", yanchor="bottom", font=dict(size=13)),
        annotations=list(figure.layout.annotations) + [
            dict(x=0, y=-0.09, xref="paper", yref="paper", xanchor="left", showarrow=False,
                text="全日频、同起点、资金连续。虚线 0.25%，实线 0.5%，点线 1%；基础为蓝色，压力为棕色。",
                font=dict(size=12, color="#65768a")),
            dict(x=0, y=-0.13, xref="paper", yref="paper", xanchor="left", showarrow=False,
                text="研究回放；历史陈旧估值：" + stale + "。不代表实盘成交或加注资格。",
                font=dict(size=12, color="#65768a")),
        ])
    figure.update_xaxes(range=[START, END], showgrid=False, ticks="outside", tickformat="%Y", dtick="M12")
    for row in (1, 2):
        figure.update_xaxes(showticklabels=False, row=row, col=1)
        figure.update_yaxes(title_text="账户权益（万元）", tickformat=",.0f", gridcolor="#e5ebf1", row=row, col=1)
    figure.update_xaxes(showticklabels=True, row=3, col=1)
    figure.update_yaxes(title_text="回撤（%）", ticksuffix="%", tickformat=".0f", rangemode="tozero",
                       gridcolor="#e5ebf1", row=3, col=1)
    return figure


def create_html(figure):
    from plotly import io as pio
    config = dict(responsive=True, displaylogo=False, scrollZoom=False,
        toImageButtonOptions=dict(format="png", filename=PNG_NAME[:-4], width=WIDTH, height=HEIGHT, scale=1))
    plot = pio.to_html(figure, full_html=False, include_plotlyjs=True, config=config,
                       div_id=CHART_ID, default_width="100%", default_height="1150px")
    return """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>COMMON52＋K｜0.25% / 0.5% / 1% 风险对照</title><style>
body{margin:0;background:#f7f9fc;color:#30455a;font-family:"PingFang SC","Microsoft YaHei",Arial,sans-serif}
main{max-width:1600px;margin:0 auto;padding:18px 18px 10px}.actions{display:flex;align-items:center;gap:16px;padding:0 22px}
button{padding:11px 20px;border:0;border-radius:8px;background:#2c75b6;color:white;font-size:15px;cursor:pointer}
button:focus-visible{outline:3px solid #e7953f;outline-offset:3px}button:disabled{opacity:.6}#export-status{font-size:13px;color:#65768a}
.js-plotly-plot{width:100%!important}footer{padding:0 22px 16px;font-size:12px;color:#65768a;line-height:1.7}
@media(max-width:700px){main{padding:12px 0}.actions{gap:9px;padding:0 15px}button{padding:10px 14px}}
</style></head><body><main><div class="actions"><button id="download-png" type="button">下载资金曲线PNG</button>
<span id="export-status" role="status" aria-live="polite">离线交互图 · 六账户完整日频 · PNG 1600 × 1200</span></div>
""" + plot + """
<footer>完整数据：<a href="equity_and_drawdown.csv" download>三风险六账户逐日权益与回撤 CSV</a> · <a href="annual_comparison.csv" download>六账户年度对照 CSV</a>。
全部账户从2015-01-05以100万元连续起算；2015 / 2020 / 2023为模型更新，资金未重启。总风险上限仍为2%。
0.5%为观察既有历史结果后的用户指定单点追加；同史对照不能确定最佳风险比例。</footer>
</main><script>
const button=document.getElementById('download-png');
button.addEventListener('click',async()=>{
 button.disabled=true;const status=document.getElementById('export-status');status.textContent='正在生成PNG…';
 try{await Plotly.downloadImage(document.getElementById('""" + CHART_ID + """'),{format:'png',width:1600,height:1200,filename:'""" + PNG_NAME[:-4] + """'});
 status.textContent='PNG已交给浏览器下载 · 1600 × 1200';}
 catch(error){status.textContent='PNG导出失败：'+error.message;}finally{button.disabled=false;}
});
</script></body></html>\n"""


def plot_completed(manifest_path, prior_path, output):
    manifest_path, output = Path(manifest_path).resolve(), Path(output).resolve()
    source = binding(manifest_path)
    manifest = document(source)
    if (manifest.get("schema") != "stage685_single_risk_halfpct_v1" or manifest.get("status") != "completed"
            or manifest.get("mode") != "actual" or manifest.get("actual_fit_calls_completed") != 0
            or manifest.get("new_cash_accounts") != 2):
        raise ValueError("completed fixed685 actual manifest required")
    terminal = document(manifest["terminal"])
    if terminal.get("status") != "completed" or terminal.get("exit_code") != 0:
        raise ValueError("successful685 actual terminal required")
    protocol = protocol_for(manifest)
    accounts, old_fields, old_rows, prior, prior_binding = prior_accounts(prior_path, protocol)
    specs = manifest["accounts"]
    if len(specs) != 2 or {a["cost"] for a in specs} != set(COSTS):
        raise ValueError("exact two685 candidate accounts required")
    for spec in specs:
        accounts["risk050_" + spec["cost"]] = read_candidate(spec)
    if (any(accounts[key]["dates"] != accounts[KEYS[0]]["dates"] for key in KEYS)
            or len(accounts[KEYS[0]]["dates"]) != protocol["window"]["source_days"]):
        raise ValueError("six account dates differ; no mixed-start splice allowed")
    validate_candidate_curve(manifest["curve_data"], accounts)
    annual_fields, annual_rows, changed = combine_annual(manifest["annual_slices"], accounts, old_fields, old_rows)
    if len(annual_rows) != protocol["plot_contract"]["annual_rows"]:
        raise ValueError("six-account annual row count differs from684 contract")
    curve_rows = []
    for index, day in enumerate(accounts[KEYS[0]]["dates"]):
        row = {"date": day}
        for key in KEYS:
            for metric in ("equity", "drawdown_pct"):
                row[key + "_" + metric] = accounts[key][metric][index]
        curve_rows.append(row)
    figure = figure_for(accounts)
    html = create_html(figure)
    output.mkdir(parents=True, exist_ok=False)
    write_csv(output / "equity_and_drawdown.csv", WIDE_FIELDS, curve_rows)
    write_csv(output / "annual_comparison.csv", annual_fields, annual_rows)
    html_path = output / HTML_NAME
    with html_path.open("x", encoding="utf-8") as stream:
        stream.write(html)
    import plotly
    inputs = [source, manifest["protocol"], manifest["terminal"], manifest["parameter_effectiveness_receipt"],
              manifest["curve_data"], manifest["annual_slices"], prior_binding,
              prior["artifacts"]["daily_csv"], prior["artifacts"]["annual_csv"], binding(HELPER_PATH)]
    for spec in specs:
        inputs.extend([spec["summary"], spec["ledgers"]["daily"]])
    inner_height = HEIGHT - figure.layout.margin.t - figure.layout.margin.b
    receipt = dict(schema="stage687_halfpct_comparison_delivery_v1", status="html_csv_completed_png_pending",
        created_at=datetime.now(timezone.utc).isoformat(), role="cache_or_visualization",
        source_code=binding(__file__), source_bindings=inputs,
        old_manifest_references=[protocol["inputs"]["baseline_manifest"], protocol["references"]["onepct_manifest"]],
        old_four_accounts_source="accepted682 visualization; no old ledger re-audit",
        source_start=START, source_end=END, initial_capital=INITIAL, single_risk_comparison=[0.0025, 0.005, 0.01],
        total_risk_cap=0.02, drawdown_includes_initial_capital_peak=True,
        full_daily_frequency=True, downsampled=False, plotly_version=plotly.__version__, chart_id=CHART_ID,
        continuous_cash=True, no_mixed_start_splice=True, annual_rows=len(annual_rows),
        annual_old_baseline_float_representation_only_cells=changed,
        artifacts={"html": binding(html_path), "daily_csv": binding(output / "equity_and_drawdown.csv"),
                   "annual_csv": binding(output / "annual_comparison.csv")},
        accounts={key:dict(account_id=accounts[key]["account_id"], daily_rows=len(accounts[key]["dates"]),
            ending_equity=accounts[key]["equity"][-1], max_drawdown_pct=min([0.0] + accounts[key]["drawdown_pct"]),
            total_return_pct=accounts[key]["summary"]["total_return_pct"],
            execution_unknown=accounts[key]["summary"]["execution_unknown"],
            any_historical_stale=accounts[key]["summary"]["any_historical_stale"]) for key in KEYS},
        png_export=dict(status="pending_browser_download", button_label="下载资金曲线PNG", filename=PNG_NAME,
                        width=WIDTH, height=HEIGHT, api="Plotly.downloadImage", manual_visual_review_required=True),
        layout=dict(title_anchor_top_px=(1 - figure.layout.title.y) * HEIGHT,
                    last_note_center_from_bottom_px=figure.layout.margin.b + figure.layout.annotations[-1].y * inner_height),
        checks=dict(completed685_actual=True, frozen684_risk_scope=True, actual_halfpct_effective=True,
            accepted682_source_matches684=True, equal_unique_ordered_dates=True, no_old_ledger_reaudit=True,
            old_annual_float_values_exact=True, old_annual_identity_exact=True,
            candidate_curves_match_daily=True, complete_account_years=True, offline_plotly_js_embedded=True),
        model_fits=0, strategy_replays=0, cash_accounts=0, sql_queries=0, downloads=0,
        production_qualified=False, increased_betting_qualified=False)
    write_json(output / "plot_manifest.json", receipt)
    return dict(status=receipt["status"], html=binding(html_path), manifest=binding(output / "plot_manifest.json"))


def register_png(output, source_png):
    output, source_png = Path(output).resolve(), Path(source_png).resolve()
    path = output / "plot_manifest.json"
    receipt = json.loads(path.read_text())
    if receipt.get("schema") != "stage687_halfpct_comparison_delivery_v1" or "png" in receipt["artifacts"]:
        raise ValueError("exact687 delivery with no registered PNG required")
    for item in receipt["artifacts"].values():
        read_bound(item)
    data = source_png.read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
        raise ValueError("browser export is not PNG")
    width, height = struct.unpack(">II", data[16:24])
    if (width, height) != (WIDTH, HEIGHT):
        raise ValueError("browser PNG dimensions differ from687 fixed plot")
    target = output / PNG_NAME
    if source_png != target:
        with target.open("xb") as stream:
            stream.write(data)
    receipt["artifacts"]["png"] = binding(target)
    receipt["png_export"].update(status="browser_download_registered", width=width, height=height)
    receipt["status"] = "completed_browser_png_registered"
    receipt["png_registered_at"] = datetime.now(timezone.utc).isoformat()
    replacement = output / "plot_manifest.json.tmp"
    write_json(replacement, receipt)
    replacement.replace(path)
    return dict(status=receipt["status"], png=receipt["artifacts"]["png"], manifest=binding(path))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, help="Completed685 half-percent actual manifest")
    parser.add_argument("--prior-delivery", type=Path,
                        default=LINE / "outputs/stage682_onepct_comparison_delivery/plot_manifest.json")
    parser.add_argument("--output", type=Path, default=LINE / "outputs/stage687_halfpct_comparison_delivery")
    parser.add_argument("--register-png", type=Path, help="Register PNG downloaded by the HTML button")
    args = parser.parse_args()
    if args.register_png:
        if args.manifest:
            parser.error("PNG registration does not take a source manifest")
        result = register_png(args.output, args.register_png)
    else:
        if not args.manifest:
            parser.error("--manifest required for chart delivery")
        result = plot_completed(args.manifest, args.prior_delivery, args.output)
    print(json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
