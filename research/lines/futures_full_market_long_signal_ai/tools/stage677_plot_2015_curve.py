"""Offline Plotly delivery of completed675 books; no fit, cash or source query.

Create HTML and plain CSV only after the fixed675 actual manifest is complete.
The page's accessible button uses Plotly.downloadImage in the normal browser.
Register that downloaded PNG with --register-png; no raster library is needed.
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
START = "2015-01-01"
END = "2026-10-16"
COSTS = ("base", "stress")
ARM = "VOLUNTARY_RESELECT"
CHART_ID = "common52_2015_equity_drawdown"
HTML_NAME = "equity_curve_2015.html"
PNG_NAME = "equity_curve_2015.png"
WIDTH, HEIGHT = 1600, 1000


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


def drawdowns(equities, initial=INITIAL):
    """Keep the initial deposit in the peak, including a first-day loss."""
    peak = float(initial)
    result = []
    for value in equities:
        equity = finite(value, "daily equity")
        peak = max(peak, equity)
        result.append((equity / peak - 1.0) * 100.0)
    return result


def read_account(account):
    cost = account["cost"]
    if (account.get("account_id") != "all_2015_" + cost or account.get("window") != "all_2015"
            or account.get("arm") != ARM):
        raise ValueError("fixed675 account identity differs")
    summary = document(account["summary"])
    if summary.get("cost") != cost:
        raise ValueError("account summary cost differs")
    _, rows = table(account["ledgers"]["daily"])
    if not rows:
        raise ValueError("empty675 daily book")
    dates = [row["date"] for row in rows]
    for day in dates:
        if date.fromisoformat(day).isoformat() != day:
            raise ValueError("noncanonical source date")
    if dates != sorted(set(dates)) or not START <= dates[0] < "2015-02-01" or dates[-1] != END:
        raise ValueError("fixed daily scope/order differs")
    equity = [finite(row["equity"], cost + " equity") for row in rows]
    dd = drawdowns(equity)
    close(equity[-1], summary["ending_equity"], cost + " ending equity")
    close(min([0.0] + dd), summary["max_drawdown_pct"], cost + " drawdown", atol=1e-7)
    if "initial_capital" in summary:
        close(summary["initial_capital"], INITIAL, cost + " initial capital")
    if "total_return_pct" in summary:
        close((equity[-1] / INITIAL - 1.0) * 100.0, summary["total_return_pct"], cost + " total return")
    return dict(account_id=account["account_id"], cost=cost, dates=dates, equity=equity,
                drawdown_pct=dd, summary=summary)


def validate_wide_curve(item, accounts):
    fields, rows = table(item)
    expected = ["date", "base_equity", "base_drawdown_pct", "stress_equity", "stress_drawdown_pct"]
    if not set(expected).issubset(fields) or [row["date"] for row in rows] != accounts["base"]["dates"]:
        raise ValueError("675 wide curve schema/dates differ")
    for cost in COSTS:
        for row, equity, dd in zip(rows, accounts[cost]["equity"], accounts[cost]["drawdown_pct"]):
            close(row[cost + "_equity"], equity, cost + " curve equity")
            close(row[cost + "_drawdown_pct"], dd, cost + " curve drawdown", atol=1e-7)
    return fields, rows


def figure_for(accounts):
    # Import plotting only at rendering time; importing this module is inert.
    from plotly import graph_objects as go
    from plotly.subplots import make_subplots

    figure = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.69, 0.31],
                           vertical_spacing=0.11)
    colors = dict(base="#007f87", stress="#dc6b20")
    labels = dict(base="基础成本", stress="压力成本")
    for cost in COSTS:
        account = accounts[cost]
        final_wan = account["equity"][-1] / 10_000.0
        label = f"{labels[cost]}｜期末 {final_wan:,.2f} 万元"
        figure.add_trace(go.Scatter(x=account["dates"], y=[v / 10_000.0 for v in account["equity"]],
            name=label, legendgroup=cost, mode="lines", line=dict(color=colors[cost], width=2),
            hovertemplate=f"{labels[cost]}：%{{y:,.2f}} 万元<extra></extra>"), row=1, col=1)
        figure.add_trace(go.Scatter(x=account["dates"], y=account["drawdown_pct"],
            name=labels[cost] + "回撤", legendgroup=cost, showlegend=False, mode="lines",
            line=dict(color=colors[cost], width=1.5),
            hovertemplate=f"{labels[cost]}回撤：%{{y:.2f}}%<extra></extra>"), row=2, col=1)
    figure.add_hline(y=100.0, line=dict(color="#8a98a9", width=1, dash="dot"), row=1, col=1)
    figure.add_hline(y=0, line=dict(color="#8a98a9", width=1), row=2, col=1)
    for cutoff in ("2020-01-01", "2023-01-01"):
        figure.add_shape(type="line", x0=cutoff, x1=cutoff, y0=0, y1=1, xref="x", yref="paper",
                         line=dict(color="#aeb8c5", width=1, dash="dot"), layer="below")
        figure.add_annotation(x=cutoff, y=1.025, xref="x", yref="paper", text=cutoff[:4] + " 模型更新",
                              showarrow=False, font=dict(size=12, color="#69798b"))
    for cost in COSTS:
        if any(key not in accounts[cost]["summary"] for key in ("execution_unknown", "any_historical_stale")):
            raise ValueError("missing actual execution/stale disclosure")
    unknown = "；".join(labels[c] + (" 是" if accounts[c]["summary"]["execution_unknown"] else " 否") for c in COSTS)
    stale = "；".join(labels[c] + (" 是" if accounts[c]["summary"].get("any_historical_stale") else " 否") for c in COSTS)
    note = "研究回放；执行未知：" + unknown + "。历史陈旧估值：" + stale + "。不代表实盘成交。"
    figure.update_layout(template="plotly_white", width=WIDTH, height=HEIGHT,
        title=dict(text="COMMON52＋K｜2015 起连续资金曲线"
                   + f"<br><sup>2015 首个源交易日至 {END} · 初始资金 100 万元 · 基础 / 压力成本</sup>",
                   x=0.05, y=0.975, xanchor="left", yanchor="top", font=dict(size=25, color="#173148")),
        font=dict(family="PingFang SC, Microsoft YaHei, Noto Sans CJK SC, Arial, sans-serif", size=13, color="#30455a"),
        paper_bgcolor="#f7f9fc", plot_bgcolor="#ffffff", hovermode="x unified",
        margin=dict(l=100, r=55, t=145, b=125),
        legend=dict(orientation="h", x=0, y=1.085, xanchor="left", yanchor="bottom", font=dict(size=14)),
        annotations=list(figure.layout.annotations) + [
            dict(x=0, y=-0.115, xref="paper", yref="paper", xanchor="left", showarrow=False,
                 text="2020 / 2023 竖线仅标记模型更新，账户资金连续；回撤含初始 100 万元峰值。",
                 font=dict(size=12, color="#65768a")),
            dict(x=0, y=-0.145, xref="paper", yref="paper", xanchor="left", showarrow=False,
                 text=note, font=dict(size=12, color="#65768a")),
        ])
    figure.update_xaxes(range=[START, END], showgrid=False, ticks="outside", tickformat="%Y", dtick="M12")
    figure.update_xaxes(showticklabels=False, row=1, col=1)
    figure.update_xaxes(showticklabels=True, row=2, col=1)
    figure.update_yaxes(title_text="账户权益（万元）", tickformat=",.0f", gridcolor="#e5ebf1", row=1, col=1)
    figure.update_yaxes(title_text="回撤（%）", ticksuffix="%", tickformat=".0f", rangemode="tozero",
                         gridcolor="#e5ebf1", row=2, col=1)
    return figure


def create_html(figure):
    from plotly import io as pio
    config = dict(responsive=True, displaylogo=False, scrollZoom=False,
                  toImageButtonOptions=dict(format="png", filename="equity_curve_2015", width=WIDTH, height=HEIGHT, scale=1))
    plot = pio.to_html(figure, full_html=False, include_plotlyjs=True, config=config,
                       div_id=CHART_ID, default_width="100%", default_height="850px")
    return """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>COMMON52＋K｜2015起资金曲线</title><style>
body{margin:0;background:#f7f9fc;color:#30455a;font-family:"PingFang SC","Microsoft YaHei",Arial,sans-serif}
main{max-width:1600px;margin:0 auto;padding:18px 18px 10px}.actions{display:flex;align-items:center;gap:16px;padding:0 22px}
button{padding:11px 20px;border:0;border-radius:8px;background:#007f87;color:white;font-size:15px;cursor:pointer}
button:focus-visible{outline:3px solid #e7953f;outline-offset:3px}button:disabled{opacity:.6}#export-status{font-size:13px;color:#65768a}
.js-plotly-plot{width:100%!important}footer{padding:0 22px 16px;font-size:12px;color:#65768a;line-height:1.7}
@media(max-width:700px){main{padding:12px 0}.actions{gap:9px;padding:0 15px}button{padding:10px 14px}}
</style></head><body><main><div class="actions"><button id="download-png" type="button">下载资金曲线PNG</button>
<span id="export-status" role="status" aria-live="polite">离线交互图 · 完整日频 · PNG 1600 × 1000</span></div>
""" + plot + """
<footer>原始数据：<a href="equity_and_drawdown.csv" download>资金与回撤 CSV</a> · <a href="annual_slices.csv" download>年度数据 CSV</a>。
模型在 2015 / 2020 / 2023 三段更新，账户从2015起连续运行。图示为已完成研究账户，执行未知状态见图内说明。</footer>
</main><script>
const button=document.getElementById('download-png');
button.addEventListener('click',async()=>{
 button.disabled=true;const status=document.getElementById('export-status');status.textContent='正在生成PNG…';
 try{await Plotly.downloadImage(document.getElementById('""" + CHART_ID + """'),{format:'png',width:1600,height:1000,filename:'equity_curve_2015'});
 status.textContent='PNG已交给浏览器下载 · 1600 × 1000';}
 catch(error){status.textContent='PNG导出失败：'+error.message;}finally{button.disabled=false;}
});
</script></body></html>\n"""


def plot_completed(manifest_path, output):
    manifest_path, output = Path(manifest_path).resolve(), Path(output).resolve()
    source = binding(manifest_path)
    manifest = document(source)
    if (manifest.get("schema") != "stage675_common52_2015_extension_v1" or manifest.get("status") != "completed"
            or manifest.get("mode") != "actual" or manifest.get("actual_fit_calls_completed") != 1
            or manifest.get("new_cash_accounts") != 2):
        raise ValueError("completed fixed675 manifest required")
    terminal = document(manifest["terminal"])
    if terminal.get("status") != "completed" or terminal.get("exit_code") != 0:
        raise ValueError("successful675 actual terminal required")
    account_specs = manifest["accounts"]
    if len(account_specs) != 2 or {a["cost"] for a in account_specs} != set(COSTS):
        raise ValueError("exact two fixed cost accounts required")
    accounts = {a["cost"]: read_account(a) for a in account_specs}
    if accounts["base"]["dates"] != accounts["stress"]["dates"]:
        raise ValueError("base/stress dates differ")
    curve_fields, curve_rows = validate_wide_curve(manifest["curve_data"], accounts)
    annual_fields, annual_rows = table(manifest["annual_slices"])
    ids = {a["account_id"] for a in account_specs}
    if not annual_rows or {r["account"] for r in annual_rows} != ids:
        raise ValueError("annual table missing fixed675 account")
    keys = [(r["account"], r["year"]) for r in annual_rows]
    if len(set(keys)) != len(keys):
        raise ValueError("duplicate annual account-year")
    for cost in COSTS:
        actual_years = {r["year"] for r in annual_rows if r["account"] == accounts[cost]["account_id"]}
        if actual_years != {day[:4] for day in accounts[cost]["dates"]}:
            raise ValueError("annual table and daily years differ")
    # Freeze visual source before writing, without loading labels, scores or bars.
    figure = figure_for(accounts)
    html = create_html(figure)
    output.mkdir(parents=True, exist_ok=False)
    write_csv(output / "equity_and_drawdown.csv", curve_fields, curve_rows)
    write_csv(output / "annual_slices.csv", annual_fields, annual_rows)
    html_path = output / HTML_NAME
    with html_path.open("x", encoding="utf-8") as stream:
        stream.write(html)
    import plotly
    inputs = [source, manifest["terminal"], manifest["curve_data"], manifest["annual_slices"]]
    for account in account_specs:
        inputs.extend([account["summary"], account["ledgers"]["daily"]])
    receipt = dict(schema="stage677_2015_equity_delivery_v1", status="html_csv_completed_png_pending",
        created_at=datetime.now(timezone.utc).isoformat(), role="cache_or_visualization",
        source_code=binding(__file__), source_bindings=inputs,
        source_start=accounts["base"]["dates"][0], requested_start=START, source_end=END,
        initial_capital=INITIAL, drawdown_includes_initial_capital_peak=True,
        full_daily_frequency=True, downsampled=False, plotly_version=plotly.__version__,
        chart_id=CHART_ID, model_update_dates=["2020-01-01", "2023-01-01"], continuous_cash=True,
        artifacts={"html": binding(html_path), "daily_csv": binding(output / "equity_and_drawdown.csv"),
                   "annual_csv": binding(output / "annual_slices.csv")},
        accounts={c:dict(account_id=accounts[c]["account_id"], daily_rows=len(accounts[c]["dates"]),
                        ending_equity=accounts[c]["equity"][-1], max_drawdown_pct=min([0.0]+accounts[c]["drawdown_pct"]),
                        execution_unknown=accounts[c]["summary"]["execution_unknown"],
                        any_historical_stale=accounts[c]["summary"].get("any_historical_stale")) for c in COSTS},
        png_export=dict(status="pending_browser_download", button_label="下载资金曲线PNG", filename=PNG_NAME,
                        width=WIDTH, height=HEIGHT, api="Plotly.downloadImage", manual_visual_review_required=True),
        checks=dict(completed_actual=True, equal_unique_ordered_dates=True, final_equity_matches=True,
                    initial_peak_drawdown_matches=True, wide_curve_matches_daily=True, offline_plotly_js_embedded=True),
        model_fits=0, strategy_replays=0, cash_accounts=0, sql_queries=0, downloads=0,
        production_qualified=False, increased_betting_qualified=False)
    write_json(output / "plot_manifest.json", receipt)
    return dict(status=receipt["status"], html=binding(html_path), manifest=binding(output / "plot_manifest.json"))


def register_png(output, source_png):
    output, source_png = Path(output).resolve(), Path(source_png).resolve()
    manifest_path = output / "plot_manifest.json"
    receipt = json.loads(manifest_path.read_text())
    if receipt.get("schema") != "stage677_2015_equity_delivery_v1" or "png" in receipt["artifacts"]:
        raise ValueError("exact677 delivery with no registered PNG required")
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
    parser.add_argument("--manifest", type=Path, help="Completed675 actual manifest")
    parser.add_argument("--output", type=Path, default=LINE / "outputs/stage677_2015_equity_delivery")
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
