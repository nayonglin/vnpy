"""Offline four-account comparison of completed675 and completed680 books.

This delivery reads only bound small manifests, daily books and summaries. It
does not train, select or replay a cash account. The browser button exports a
standard Plotly PNG; --register-png binds that browser download to the receipt.
"""
from __future__ import annotations

import argparse
import csv
from datetime import date, datetime, timezone
import gzip
import hashlib
import io
import json
import math
from pathlib import Path
import struct


LINE = Path(__file__).resolve().parents[1]
INITIAL = 1_000_000.0
START, END = "2015-01-05", "2026-10-16"
COSTS = ("base", "stress")
RISKS = ("risk025", "risk100")
KEYS = tuple(risk + "_" + cost for risk in RISKS for cost in COSTS)
ARM = "VOLUNTARY_RESELECT"
CHART_ID = "common52_onepct_comparison"
HTML_NAME = "equity_curve_onepct_comparison.html"
PNG_NAME = "equity_curve_onepct_comparison.png"
WIDTH, HEIGHT = 1600, 1100
LABELS = {"risk025_base": "0.25%｜基础", "risk025_stress": "0.25%｜压力",
          "risk100_base": "1%｜基础", "risk100_stress": "1%｜压力"}
COLORS = {"risk025_base": "#438d95", "risk025_stress": "#c48b3f",
          "risk100_base": "#2461be", "risk100_stress": "#c84e4e"}


def binding(path):
    path = Path(path).resolve()
    data = path.read_bytes()
    return dict(path=str(path), bytes=len(data), sha256=hashlib.sha256(data).hexdigest())


def read_bound(item):
    path = Path(item["path"]).resolve()
    data = path.read_bytes()
    if len(data) != item["bytes"] or hashlib.sha256(data).hexdigest() != item["sha256"]:
        raise ValueError("bound plotting input changed: " + str(path))
    return data


def document(item):
    return json.loads(read_bound(item))


def table(item):
    data = read_bound(item)
    if str(item["path"]).endswith(".gz"):
        data = gzip.decompress(data)
    reader = csv.DictReader(io.StringIO(data.decode("utf-8-sig"), newline=""))
    if not reader.fieldnames:
        raise ValueError("empty CSV header: " + item["path"])
    return list(reader.fieldnames), list(reader)


def write_json(path, value):
    with Path(path).open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        stream.write("\n")


def write_csv(path, fields, rows):
    with Path(path).open("x", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def finite(value, label):
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("nonfinite " + label)
    return result


def close(actual, expected, label, atol=1e-6):
    if not math.isclose(finite(actual, label), finite(expected, label), rel_tol=1e-12, abs_tol=atol):
        raise ValueError("plotting arithmetic differs: " + label)


def drawdowns(equities):
    """Keep the original million in every account's peak, including day one."""
    peak = INITIAL
    result = []
    for value in equities:
        equity = finite(value, "daily equity")
        peak = max(peak, equity)
        result.append((equity / peak - 1.0) * 100.0)
    return result


def read_account(account, risk):
    cost = account["cost"]
    expected_id = ("all_2015_" if risk == "risk025" else "all_2015_onepct_") + cost
    if (cost not in COSTS or account.get("account_id") != expected_id
            or account.get("window") != "all_2015" or account.get("arm") != ARM):
        raise ValueError("fixed account identity differs: " + expected_id)
    summary = document(account["summary"])
    if (summary.get("cost") != cost or summary.get("account_id", expected_id) != expected_id
            or summary.get("arm", ARM) != ARM or summary.get("window", "all_2015") != "all_2015"):
        raise ValueError("account summary identity differs: " + expected_id)
    for key in ("execution_unknown", "any_historical_stale"):
        if type(summary.get(key)) is not bool:
            raise ValueError("actual boolean disclosure required: " + expected_id + " " + key)
    fields, rows = table(account["ledgers"]["daily"])
    if not rows or not {"date", "equity"}.issubset(fields):
        raise ValueError("empty or malformed daily book: " + expected_id)
    dates = [row["date"] for row in rows]
    for day in dates:
        if date.fromisoformat(day).isoformat() != day:
            raise ValueError("noncanonical source date")
    if dates != sorted(set(dates)) or dates[0] != START or dates[-1] != END:
        raise ValueError("fixed daily scope/order differs: " + expected_id)
    equity = [finite(row["equity"], expected_id + " equity") for row in rows]
    dd = drawdowns(equity)
    close(equity[-1], summary["ending_equity"], expected_id + " ending equity")
    close(min([0.0] + dd), summary["max_drawdown_pct"], expected_id + " drawdown", atol=1e-7)
    close((equity[-1] / INITIAL - 1.0) * 100.0, summary["total_return_pct"], expected_id + " total return")
    if "initial_capital" in summary:
        close(summary["initial_capital"], INITIAL, expected_id + " initial capital")
    return dict(account_id=expected_id, risk=risk, cost=cost, dates=dates, equity=equity,
                drawdown_pct=dd, summary=summary)


def validate_curve(item, accounts, four_accounts):
    fields, rows = table(item)
    keys = KEYS if four_accounts else tuple("risk025_" + cost for cost in COSTS)
    expected = ["date"]
    for key in keys:
        prefix = key if four_accounts else accounts[key]["cost"]
        expected.extend([prefix + "_equity", prefix + "_drawdown_pct"])
    if not set(expected).issubset(fields) or [row["date"] for row in rows] != accounts[keys[0]]["dates"]:
        raise ValueError("wide curve schema/dates differ")
    for key in keys:
        prefix = key if four_accounts else accounts[key]["cost"]
        for row, equity, dd in zip(rows, accounts[key]["equity"], accounts[key]["drawdown_pct"]):
            close(row[prefix + "_equity"], equity, key + " wide equity")
            close(row[prefix + "_drawdown_pct"], dd, key + " wide drawdown", atol=1e-7)
    return fields, rows


def validate_annual(item, accounts, keys):
    fields, rows = table(item)
    ids = {accounts[key]["account_id"] for key in keys}
    if not rows or not {"account", "year"}.issubset(fields) or {r["account"] for r in rows} != ids:
        raise ValueError("annual table missing fixed account")
    row_keys = [(r["account"], r["year"]) for r in rows]
    if len(set(row_keys)) != len(row_keys):
        raise ValueError("duplicate annual account-year")
    for key in keys:
        account = accounts[key]
        if ({r["year"] for r in rows if r["account"] == account["account_id"]}
                != {day[:4] for day in account["dates"]}):
            raise ValueError("annual table and daily years differ: " + key)
    return fields, rows


def figure_for(accounts):
    from plotly import graph_objects as go
    from plotly.subplots import make_subplots

    figure = make_subplots(rows=3, cols=1, shared_xaxes=True, row_heights=[0.36, 0.36, 0.28],
        vertical_spacing=0.085, subplot_titles=["基础成本｜连续账户权益", "压力成本｜连续账户权益", "四账户回撤｜含初始资金峰值"])
    for key in KEYS:
        account = accounts[key]
        style = dict(color=COLORS[key], width=2.1 if account["risk"] == "risk100" else 1.8,
                     dash="solid" if account["risk"] == "risk100" else "dash")
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
    figure.add_hline(y=0.0, line=dict(color="#8a98a9", width=1), row=3, col=1)
    unknown = "；".join(LABELS[key] + (" 是" if accounts[key]["summary"]["execution_unknown"] else " 否") for key in KEYS)
    stale = "；".join(LABELS[key] + (" 是" if accounts[key]["summary"]["any_historical_stale"] else " 否") for key in KEYS)
    figure.update_layout(template="plotly_white", width=WIDTH, height=HEIGHT,
        title=dict(text="COMMON52＋K｜单品种风险 0.25% 与 1% 连续资金对照"
            + f"<br><sup>{START}—{END} · 初始 100 万元 · 总风险上限 2% 不变</sup>"
            + "<br><sup>execution_unknown：" + unknown + "</sup>",
            x=0.055, y=0.985, xanchor="left", yanchor="top", font=dict(size=24, color="#173148")),
        font=dict(family="PingFang SC, Microsoft YaHei, Noto Sans CJK SC, Arial, sans-serif", size=13, color="#30455a"),
        paper_bgcolor="#f7f9fc", plot_bgcolor="#ffffff", hovermode="x unified",
        margin=dict(l=100, r=55, t=200, b=125),
        legend=dict(orientation="h", x=0, y=1.075, xanchor="left", yanchor="bottom", font=dict(size=13)),
        annotations=list(figure.layout.annotations) + [
            dict(x=0, y=-0.10, xref="paper", yref="paper", xanchor="left", showarrow=False,
                text="全日频、共同起点；2015 / 2020 / 2023 仅模型更新，资金连续。虚线 0.25%，实线 1%。",
                font=dict(size=12, color="#65768a")),
            dict(x=0, y=-0.13, xref="paper", yref="paper", xanchor="left", showarrow=False,
                text="研究回放；历史陈旧估值：" + stale + "。不代表实盘成交或加注资格。",
                font=dict(size=12, color="#65768a")),
        ])
    figure.update_xaxes(range=[START, END], showgrid=False, ticks="outside", tickformat="%Y", dtick="M12")
    figure.update_xaxes(showticklabels=False, row=1, col=1)
    figure.update_xaxes(showticklabels=False, row=2, col=1)
    figure.update_xaxes(showticklabels=True, row=3, col=1)
    for row in (1, 2):
        figure.update_yaxes(title_text="账户权益（万元）", tickformat=",.0f", gridcolor="#e5ebf1", row=row, col=1)
    figure.update_yaxes(title_text="回撤（%）", ticksuffix="%", tickformat=".0f", rangemode="tozero",
                       gridcolor="#e5ebf1", row=3, col=1)
    return figure


def create_html(figure):
    from plotly import io as pio
    config = dict(responsive=True, displaylogo=False, scrollZoom=False,
        toImageButtonOptions=dict(format="png", filename=PNG_NAME[:-4], width=WIDTH, height=HEIGHT, scale=1))
    plot = pio.to_html(figure, full_html=False, include_plotlyjs=True, config=config,
        div_id=CHART_ID, default_width="100%", default_height="1050px")
    return """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>COMMON52＋K｜0.25% 与 1% 风险对照</title><style>
body{margin:0;background:#f7f9fc;color:#30455a;font-family:"PingFang SC","Microsoft YaHei",Arial,sans-serif}
main{max-width:1600px;margin:0 auto;padding:18px 18px 10px}.actions{display:flex;align-items:center;gap:16px;padding:0 22px}
button{padding:11px 20px;border:0;border-radius:8px;background:#2461be;color:white;font-size:15px;cursor:pointer}
button:focus-visible{outline:3px solid #e7953f;outline-offset:3px}button:disabled{opacity:.6}#export-status{font-size:13px;color:#65768a}
.js-plotly-plot{width:100%!important}footer{padding:0 22px 16px;font-size:12px;color:#65768a;line-height:1.7}
@media(max-width:700px){main{padding:12px 0}.actions{gap:9px;padding:0 15px}button{padding:10px 14px}}
</style></head><body><main><div class="actions"><button id="download-png" type="button">下载资金曲线PNG</button>
<span id="export-status" role="status" aria-live="polite">离线交互图 · 完整日频 · PNG 1600 × 1100</span></div>
""" + plot + """
<footer>完整数据：<a href="equity_and_drawdown.csv" download>四账户逐日权益与回撤 CSV</a> · <a href="annual_comparison.csv" download>四账户年度对照 CSV</a>。
基础和压力成本分别对照，账户都从2015-01-05以100万元连续起算，未拼接不同起点。总风险上限仍为2%，单品种风险是唯一授权变更。</footer>
</main><script>
const button=document.getElementById('download-png');
button.addEventListener('click',async()=>{
 button.disabled=true;const status=document.getElementById('export-status');status.textContent='正在生成PNG…';
 try{await Plotly.downloadImage(document.getElementById('""" + CHART_ID + """'),{format:'png',width:1600,height:1100,filename:'""" + PNG_NAME[:-4] + """'});
 status.textContent='PNG已交给浏览器下载 · 1600 × 1100';}
 catch(error){status.textContent='PNG导出失败：'+error.message;}finally{button.disabled=false;}
});
</script></body></html>\n"""


def validate_protocol(manifest):
    protocol = document(manifest["protocol"])
    if (protocol.get("schema") != "stage679_single_risk_onepct_protocol_v1"
            or protocol.get("status") != "frozen_before_candidate_outcomes"):
        raise ValueError("fixed frozen679 protocol required")
    change, fixed, window = protocol["change"], protocol["fixed"], protocol["window"]
    if change.get("parameter") != "SINGLE_RISK" or change.get("other_parameters_changed") is not False:
        raise ValueError("only authorized single risk change required")
    close(change["old"], 0.0025, "protocol old single risk", atol=0.0)
    close(change["new"], 0.01, "protocol new single risk", atol=0.0)
    for key, value in (("TOTAL_RISK", 0.02), ("MARGIN_CAP", 0.25), ("MARGIN_BUFFER", 1.1)):
        close(fixed[key], value, "protocol fixed " + key, atol=0.0)
    close(window["initial_equity"], INITIAL, "protocol initial capital", atol=0.0)
    if (window.get("first_actual_source_day") != START or window.get("end") != END
            or window.get("continuous") is not True or protocol["limits"].get("new_fit") != 0
            or protocol["limits"].get("new_cash") != 2 or protocol["limits"].get("risk_grid_scan") is not False):
        raise ValueError("fixed679 window/budget differs")
    expected_baseline = protocol["inputs"]["baseline_manifest"]
    actual_baseline = manifest["input_bindings"]["baseline_manifest"]
    if actual_baseline != expected_baseline:
        raise ValueError("680 baseline is not the frozen679 baseline")
    effectiveness = document(manifest["parameter_effectiveness_receipt"])
    for key, value in (("SINGLE_RISK", 0.01), ("TOTAL_RISK", 0.02), ("MARGIN_CAP", 0.25),
                       ("MARGIN_BUFFER", 1.1), ("initial_stop_N", 0.25)):
        close(effectiveness["effective"][key], value, "actual effective " + key, atol=0.0)
    if effectiveness.get("old_globals_unchanged") is not True:
        raise ValueError("680 must preserve accepted original risk globals")
    return protocol


def plot_completed(manifest_path, output):
    # The completed680 schema and fixed679 risk guard are checked before any
    # ledger is read. Neither missing nor partial actual output is chartable.
    manifest_path, output = Path(manifest_path).resolve(), Path(output).resolve()
    source = binding(manifest_path)
    manifest = document(source)
    if (manifest.get("schema") != "stage680_single_risk_onepct_v1" or manifest.get("status") != "completed"
            or manifest.get("mode") != "actual" or manifest.get("actual_fit_calls_completed") != 0
            or manifest.get("new_cash_accounts") != 2):
        raise ValueError("completed fixed680 manifest required")
    terminal = document(manifest["terminal"])
    if terminal.get("status") != "completed" or terminal.get("exit_code") != 0:
        raise ValueError("successful680 actual terminal required")
    protocol = validate_protocol(manifest)
    baseline_binding = manifest["input_bindings"]["baseline_manifest"]
    baseline = document(baseline_binding)
    if (baseline.get("schema") != "stage675_common52_2015_extension_v1" or baseline.get("status") != "completed"
            or baseline.get("mode") != "actual" or baseline.get("actual_fit_calls_completed") != 1
            or baseline.get("new_cash_accounts") != 2):
        raise ValueError("completed fixed675 baseline manifest required")
    old_terminal = document(baseline["terminal"])
    if old_terminal.get("status") != "completed" or old_terminal.get("exit_code") != 0:
        raise ValueError("successful675 baseline terminal required")
    accounts = {}
    for risk, origin in (("risk025", baseline), ("risk100", manifest)):
        specs = origin["accounts"]
        if len(specs) != 2 or {a["cost"] for a in specs} != set(COSTS):
            raise ValueError("exact two fixed cost accounts required: " + risk)
        for spec in specs:
            account = read_account(spec, risk)
            accounts[risk + "_" + spec["cost"]] = account
    if any(accounts[key]["dates"] != accounts[KEYS[0]]["dates"] for key in KEYS):
        raise ValueError("four account dates differ; cannot compare different starts")
    if len(accounts[KEYS[0]]["dates"]) != protocol["window"]["source_days"]:
        raise ValueError("daily row count differs from frozen679 source window")
    validate_curve(baseline["curve_data"], accounts, four_accounts=False)
    curve_fields, curve_rows = validate_curve(manifest["curve_data"], accounts, four_accounts=True)
    old_annual_fields, old_annual_rows = validate_annual(baseline["annual_slices"], accounts, KEYS[:2])
    annual_fields, annual_rows = validate_annual(manifest["annual_slices"], accounts, KEYS)
    if not set(old_annual_fields).issubset(annual_fields):
        raise ValueError("680 annual table lost675 source fields")
    lookup = {(r["account"], r["year"]): r for r in annual_rows}
    for old in old_annual_rows:
        current = lookup[(old["account"], old["year"])]
        for field in old_annual_fields:
            if current[field] == old[field]:
                continue
            # 680 legitimately writes the combined table through pandas.
            # Compare numerical values, since a CSV float representation may
            # change on that one read/write without changing the source value.
            try:
                left, right = float(current[field]), float(old[field])
            except ValueError:
                raise ValueError("680 annual baseline differs from675 source: " + field) from None
            close(left, right, "annual baseline " + field, atol=1e-8)
    figure = figure_for(accounts)
    html = create_html(figure)
    output.mkdir(parents=True, exist_ok=False)
    write_csv(output / "equity_and_drawdown.csv", curve_fields, curve_rows)
    write_csv(output / "annual_comparison.csv", annual_fields, annual_rows)
    html_path = output / HTML_NAME
    with html_path.open("x", encoding="utf-8") as stream:
        stream.write(html)
    import plotly
    inputs = [source, manifest["protocol"], manifest["parameter_effectiveness_receipt"],
              manifest["terminal"], baseline_binding, baseline["terminal"],
              manifest["curve_data"], baseline["curve_data"], manifest["annual_slices"], baseline["annual_slices"]]
    for origin in (baseline, manifest):
        for account in origin["accounts"]:
            inputs.extend([account["summary"], account["ledgers"]["daily"]])
    receipt = dict(schema="stage682_onepct_comparison_delivery_v1", status="html_csv_completed_png_pending",
        created_at=datetime.now(timezone.utc).isoformat(), role="cache_or_visualization",
        source_code=binding(__file__), source_bindings=inputs,
        source_start=START, source_end=END, initial_capital=INITIAL, single_risk_comparison=[0.0025, 0.01],
        total_risk_cap=0.02, drawdown_includes_initial_capital_peak=True,
        full_daily_frequency=True, downsampled=False, plotly_version=plotly.__version__, chart_id=CHART_ID,
        continuous_cash=True, no_mixed_start_splice=True,
        artifacts={"html": binding(html_path), "daily_csv": binding(output / "equity_and_drawdown.csv"),
                   "annual_csv": binding(output / "annual_comparison.csv")},
        accounts={key:dict(account_id=accounts[key]["account_id"], daily_rows=len(accounts[key]["dates"]),
            ending_equity=accounts[key]["equity"][-1], max_drawdown_pct=min([0.0] + accounts[key]["drawdown_pct"]),
            total_return_pct=accounts[key]["summary"]["total_return_pct"],
            execution_unknown=accounts[key]["summary"]["execution_unknown"],
            any_historical_stale=accounts[key]["summary"]["any_historical_stale"]) for key in KEYS},
        png_export=dict(status="pending_browser_download", button_label="下载资金曲线PNG", filename=PNG_NAME,
                        width=WIDTH, height=HEIGHT, api="Plotly.downloadImage", manual_visual_review_required=True),
        checks=dict(completed_actual=True, equal_unique_ordered_dates=True, final_equity_matches=True,
            initial_peak_drawdown_matches=True, four_wide_curves_match_daily=True,
            frozen679_risk_scope_checked=True, actual_effective_risks_checked=True,
            annual_baseline_values_match=True,
            complete_account_years=True, offline_plotly_js_embedded=True),
        model_fits=0, strategy_replays=0, cash_accounts=0, sql_queries=0, downloads=0,
        production_qualified=False, increased_betting_qualified=False)
    write_json(output / "plot_manifest.json", receipt)
    return dict(status=receipt["status"], html=binding(html_path), manifest=binding(output / "plot_manifest.json"))


def register_png(output, source_png):
    output, source_png = Path(output).resolve(), Path(source_png).resolve()
    manifest_path = output / "plot_manifest.json"
    receipt = json.loads(manifest_path.read_text())
    if receipt.get("schema") != "stage682_onepct_comparison_delivery_v1" or "png" in receipt["artifacts"]:
        raise ValueError("exact682 delivery with no registered PNG required")
    for item in receipt["artifacts"].values():
        read_bound(item)
    data = source_png.read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
        raise ValueError("browser export is not PNG")
    width, height = struct.unpack(">II", data[16:24])
    if (width, height) != (WIDTH, HEIGHT):
        raise ValueError("browser PNG dimensions differ from fixed plot")
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
    replacement.replace(manifest_path)
    return dict(status=receipt["status"], png=receipt["artifacts"]["png"], manifest=binding(manifest_path))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, help="Completed680 actual manifest with bound675 baseline")
    parser.add_argument("--output", type=Path, default=LINE / "outputs/stage682_onepct_comparison_delivery")
    parser.add_argument("--register-png", type=Path, help="Register the PNG downloaded by the HTML button")
    args = parser.parse_args()
    if args.register_png:
        if args.manifest:
            parser.error("PNG registration does not take a source manifest")
        result = register_png(args.output, args.register_png)
    else:
        if not args.manifest:
            parser.error("--manifest required for chart delivery")
        result = plot_completed(args.manifest, args.output)
    print(json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
