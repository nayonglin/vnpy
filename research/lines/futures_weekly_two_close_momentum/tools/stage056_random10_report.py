"""Readable comparison of the frozen Stage056 random-product sensitivity replay."""
import html
import json
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go

import stage056_random10_touch as replay

LINE = replay.LINE
RESULT = LINE / "outputs/stage056_random10_touch_halfyear_20261104"
OUTPUT = LINE / "outputs/stage056_random10_comparison_v1"
NAMES = {
    "AP": "苹果", "CF": "棉花", "FG": "玻璃", "MA": "甲醇", "OI": "菜油",
    "SA": "纯碱", "SH": "烧碱", "SM": "锰硅", "au": "黄金", "cu": "铜",
    "fu": "燃油", "hc": "热卷", "jm": "焦煤", "lc": "碳酸锂", "lh": "生猪",
    "p": "棕榈油", "rb": "螺纹钢", "ru": "橡胶", "si": "工业硅", "sp": "纸浆", "ss": "不锈钢",
}


def main():
    metrics = pd.read_csv(RESULT / "window_metrics.csv")
    summary = pd.read_csv(RESULT / "group_summary.csv")
    concentration = pd.read_csv(RESULT / "concentration.csv")
    design = replay.prior.read_json(replay.FROZEN)
    receipt = replay.prior.read_json(RESULT / "receipt.json")
    if not (len(metrics) == 120 and receipt["completed_runs"] == receipt["attempted_runs"] == 96
            and receipt["unknown_runs"] == 0):
        raise ValueError("incomplete sensitivity experiment")
    OUTPUT.mkdir(parents=True)
    groups = "".join(
        f"<p><strong>{group}</strong>　" + "、".join(NAMES[p.split('.')[0]] for p in products) + "</p>"
        for group, products in design["groups"].items()
    )
    fig = go.Figure()
    start = design["starts"][0]
    for group in ("S21", *design["groups"]):
        folder = replay.BASELINE / start if group == "S21" else RESULT / group / start
        daily = pd.read_csv(folder / "daily.csv")
        fig.add_scatter(x=daily.date, y=daily.equity / 10000, name=group, mode="lines")
    fig.update_layout(template="plotly_white", title="2015 年起独立回测的账户权益", yaxis_title="万元",
                      xaxis_title="交易日", height=520, hovermode="x unified")
    full = summary[["group", "full_equity", "full_return_pct", "full_max_dd_pct", "full_sharpe",
                    "full_closed_cycles", "full_fills", "full_win_rate_pct"]].rename(columns={
        "group": "组别", "full_equity": "期末权益（元）", "full_return_pct": "累计收益（%）",
        "full_max_dd_pct": "最大回撤（%）", "full_sharpe": "Sharpe", "full_closed_cycles": "完整交易数",
        "full_fills": "成交笔数", "full_win_rate_pct": "胜率（%）",
    })
    windows = metrics[["calendar_start", "group", "equity", "return_pct", "max_dd_pct", "sharpe",
                       "closed_cycles", "fills", "win_rate_pct", "slippage", "commission",
                       "blocked_total", "deficit_days"]].sort_values(["calendar_start", "group"])
    windows = windows.rename(columns={
        "calendar_start": "起点", "group": "组别", "equity": "期末权益（元）", "return_pct": "收益（%）",
        "max_dd_pct": "最大回撤（%）", "sharpe": "Sharpe", "closed_cycles": "完整交易数", "fills": "成交笔数",
        "win_rate_pct": "胜率（%）", "slippage": "滑点（元）", "commission": "手续费（元）",
        "blocked_total": "资金拒单数", "deficit_days": "资金缺口天数",
    })
    positive = concentration.loc[concentration.calendar_start.eq(start), [
        "group", "largest_product", "largest_product_pnl", "top1_positive_share_pct",
        "top3_positive_share_pct", "profitable_products", "traded_products",
    ]].rename(columns={
        "group": "组别", "largest_product": "最大贡献品种", "largest_product_pnl": "该品种净损益（元）",
        "top1_positive_share_pct": "最大品种占正贡献（%）", "top3_positive_share_pct": "前三占正贡献（%）",
        "profitable_products": "盈利品种数", "traded_products": "交易品种数",
    })
    page = f"""<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<title>Stage056 四组随机十品种对比</title>
<style>body{{font-family:system-ui,sans-serif;color:#203047;margin:28px;line-height:1.6}}
table{{border-collapse:collapse;font-size:14px;white-space:nowrap;width:100%}}
th,td{{padding:7px 10px;border:1px solid #d7deea;text-align:right}}th{{background:#edf2f8}}
tbody tr:nth-child(even){{background:#f7f9fc}}.scroll{{overflow:auto;margin:16px 0}}h2{{margin-top:36px}}
a{{color:#145ba7}}</style><h1>四组随机十品种 · 全品种触价止损</h1>
<p>150,000 元初始资金，固定一手，周 K 入场，触价止损。每个起点空仓独立运行至 2026-11-04。
种子 20261105，四组各十品种，组内无放回，组间允许重叠。96 次回放完成。</p>
{groups}
<p>组间交集为 4 至 7 个品种，四组共有棕榈油、橡胶和不锈钢，铜与热卷未被抽到。
早期未上市品种等待实际行情，可交易数可能少于十个。四组与重叠起点存在统计依赖。</p>
<div>{fig.to_html(full_html=False, include_plotlyjs=True, config={'responsive': True})}</div>
<h2>2015 年起全期结果</h2><div class="scroll">{full.to_html(index=False, float_format=lambda v: f'{v:,.2f}')}</div>
<h2>全期逐品种集中度</h2><p>正贡献占比的分母为所有盈利品种损益合计。包含期末持仓按收盘价计的损益。</p>
<div class="scroll">{positive.to_html(index=False, float_format=lambda v: f'{v:,.2f}')}</div>
<h2>全部 24 起点与五组结果</h2><p>完整交易数按开仓到最终平仓计算。成交笔数包括换月的各次成交。
收益为起点至终点的累计收益。</p><div class="scroll">{windows.to_html(index=False, float_format=lambda v: f'{v:,.2f}')}</div>
<p>历史触价采用日 OHLC 模拟，滑点已计，手续费为零。新开保证金不足会拒单，已有持仓波动仍可能产生缺口。
固定一手下各品种风险金额不同。四组结果只支持当前母池、策略和历史范围的敏感性判断。</p>
<p>外部调研采用跨市场检验思路，并保留日线成交限制。
<a href="https://www.aqr.com/insights/research/journal-article/a-century-of-evidence-on-trend-following-investing">AQR 趋势研究</a> ·
<a href="https://github.com/QuantConnect/Lean/blob/master/Common/Orders/Fills/FillModel.cs">LEAN 成交源码</a></p>
<p>父结果清单 SHA256 {html.escape(receipt['stage055_manifest_sha256'])}</p></html>"""
    (OUTPUT / "index.html").write_text(page)
    report_receipt = dict(result_manifest_sha256=replay.base.portfolio.sha(RESULT / "SHA256SUMS"),
                          report_script_sha256=replay.base.portfolio.sha(Path(__file__)),
                          html_sha256=replay.base.portfolio.sha(OUTPUT / "index.html"), rows=len(metrics))
    (OUTPUT / "receipt.json").write_text(json.dumps(report_receipt, indent=2) + "\n")
    print(OUTPUT / "index.html")


if __name__ == "__main__":
    main()
