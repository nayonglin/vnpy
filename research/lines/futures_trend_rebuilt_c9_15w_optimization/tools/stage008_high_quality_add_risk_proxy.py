from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import sys
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[4]
TOOLS_DIR = Path(__file__).resolve().parent
PORTFOLIO_DIR = PROJECT_DIR / "examples" / "portfolio_backtesting"
for path in (str(TOOLS_DIR), str(PORTFOLIO_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

import stage006_current_quality_feature_binder as s006


LINE_ID = "futures_trend_rebuilt_c9_15w_optimization"
STAGE = "Stage008"
MODEL_TAG = "stage008_high_quality_add_risk_proxy_v1"
OUTPUT_PREFIX = "rebuilt_c9_stage008_high_quality_add_risk_proxy"

LINE_DIR = PROJECT_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage008_high_quality_add_risk_proxy"
STAGE006_OUTPUT_DIR = LINE_DIR / "outputs" / "stage006_current_quality_feature_binder"
STAGE007_OUTPUT_DIR = LINE_DIR / "outputs" / "stage007_minute_source_coverage_rebind"

BASE_CURVES_PATH = (
    STAGE006_OUTPUT_DIR
    / "rebuilt_c9_stage006_current_quality_feature_binder_curves_stage006_current_quality_feature_binder_v1.csv"
)
BASE_SUMMARY_PATH = (
    STAGE006_OUTPUT_DIR
    / "rebuilt_c9_stage006_current_quality_feature_binder_summary_stage006_current_quality_feature_binder_v1.csv"
)
QUALITY_FEATURES_PATH = (
    STAGE007_OUTPUT_DIR
    / "rebuilt_c9_stage007_minute_source_coverage_rebind_quality_features_stage007_minute_source_coverage_rebind_v1.csv"
)

TAG_COLUMN = "tag_ai4_6_entry_or_first_aligned"
ADD_RISK_FRACTION = 0.25
CAPITAL = 150000.0
EPS = 1e-9

PROXY_LOT_DELTAS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_lot_deltas_{MODEL_TAG}.csv"
PROXY_CURVES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv"
PROXY_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
PROXY_ANNUAL_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_annual_returns_{MODEL_TAG}.csv"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_proxy_chart_{MODEL_TAG}.png"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


def _json_safe(value: Any) -> Any:
    return s006._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s006._md_table(frame, max_rows=max_rows)


def _drawdown_pct(equity: pd.Series) -> pd.Series:
    values = pd.to_numeric(equity, errors="coerce").ffill()
    peak = values.cummax()
    return (values / peak.replace(0.0, np.nan) - 1.0).replace([np.inf, -np.inf], np.nan).fillna(0.0) * 100.0


def _sharpe_from_equity(equity: pd.Series) -> float:
    values = pd.to_numeric(equity, errors="coerce").dropna()
    returns = values.pct_change().replace([np.inf, -np.inf], np.nan).dropna()
    if returns.empty or float(returns.std(ddof=1)) == 0.0:
        return 0.0
    return float(returns.mean() / returns.std(ddof=1) * np.sqrt(252.0))


def _summarize_curve(curve: pd.DataFrame, equity_column: str) -> dict[str, Any]:
    data = curve.sort_values("date").copy()
    equity = pd.to_numeric(data[equity_column], errors="coerce")
    return {
        "requested_start_month": str(data["requested_start_month"].iloc[0]),
        "actual_start": pd.Timestamp(data["date"].iloc[0]).date().isoformat(),
        "actual_end": pd.Timestamp(data["date"].iloc[-1]).date().isoformat(),
        "trading_days": int(len(data)),
        "end_equity": float(equity.iloc[-1]),
        "total_return_pct": float((equity.iloc[-1] / CAPITAL - 1.0) * 100.0),
        "max_dd_pct": float(_drawdown_pct(equity).min()),
        "sharpe": _sharpe_from_equity(equity),
    }


def _build_lot_deltas(features: pd.DataFrame) -> pd.DataFrame:
    data = features.copy()
    data["exit_date"] = pd.to_datetime(data["exit_date"], errors="coerce").dt.normalize()
    data["realized_pnl"] = pd.to_numeric(data["realized_pnl"], errors="coerce").fillna(0.0)
    data[TAG_COLUMN] = data[TAG_COLUMN].astype(bool)
    selected = data[data[TAG_COLUMN]].copy()
    selected["add_risk_fraction"] = ADD_RISK_FRACTION
    selected["proxy_delta_pnl"] = selected["realized_pnl"] * ADD_RISK_FRACTION
    keep = [
        "requested_start_month",
        "lot_id",
        "vt_symbol",
        "product",
        "direction",
        "entry_date",
        "exit_date",
        "realized_pnl",
        "r_multiple",
        "ai_product_pool_rank",
        "entry_open_relation_bucket",
        "first_bar_relation_bucket",
        "proxy_delta_pnl",
    ]
    return selected[[column for column in keep if column in selected.columns]].reset_index(drop=True)


def _build_proxy_curves(base_curves: pd.DataFrame, lot_deltas: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    curves = base_curves.copy()
    curves["date"] = pd.to_datetime(curves["date"], errors="coerce").dt.normalize()
    curves["account_equity"] = pd.to_numeric(curves["account_equity"], errors="coerce")
    daily_delta = (
        lot_deltas.groupby(["requested_start_month", "exit_date"], dropna=False)["proxy_delta_pnl"].sum().reset_index()
        if not lot_deltas.empty
        else pd.DataFrame(columns=["requested_start_month", "exit_date", "proxy_delta_pnl"])
    )
    merged = curves.merge(
        daily_delta.rename(columns={"exit_date": "date", "proxy_delta_pnl": "daily_proxy_delta"}),
        on=["requested_start_month", "date"],
        how="left",
    )
    merged["daily_proxy_delta"] = pd.to_numeric(merged["daily_proxy_delta"], errors="coerce").fillna(0.0)
    output_frames: list[pd.DataFrame] = []
    for _start, group in merged.groupby("requested_start_month", sort=True):
        g = group.sort_values("date").copy()
        g["proxy_cum_delta"] = g["daily_proxy_delta"].cumsum()
        g["proxy_account_equity"] = g["account_equity"] + g["proxy_cum_delta"]
        g["proxy_nav"] = g["proxy_account_equity"] / CAPITAL
        g["proxy_drawdown_pct"] = _drawdown_pct(g["proxy_account_equity"])
        output_frames.append(g)
    proxy = pd.concat(output_frames, ignore_index=True, sort=False) if output_frames else pd.DataFrame()
    curve_dates = set(zip(curves["requested_start_month"].astype(str), curves["date"]))
    unmatched = 0
    for row in daily_delta.to_dict("records"):
        if (str(row["requested_start_month"]), row["exit_date"]) not in curve_dates:
            unmatched += 1
    return proxy, unmatched


def _summary(base_summary: pd.DataFrame, proxy_curves: pd.DataFrame) -> pd.DataFrame:
    rows = [_summarize_curve(group, "proxy_account_equity") for _, group in proxy_curves.groupby("requested_start_month")]
    proxy_summary = pd.DataFrame(rows)
    compare = base_summary.merge(proxy_summary, on="requested_start_month", suffixes=("_base", "_proxy"))
    compare["end_equity_delta"] = compare["end_equity_proxy"] - compare["end_equity_base"]
    compare["return_delta_pp"] = compare["total_return_pct_proxy"] - compare["total_return_pct_base"]
    compare["max_dd_delta_pp"] = compare["max_dd_pct_proxy"] - compare["max_dd_pct_base"]
    compare["sharpe_delta"] = compare["sharpe_proxy"] - compare["sharpe_base"]
    return compare.sort_values("requested_start_month").reset_index(drop=True)


def _annual_returns(proxy_curves: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for start, group in proxy_curves.groupby("requested_start_month"):
        g = group.sort_values("date").copy()
        g["year"] = pd.to_datetime(g["date"]).dt.year
        for year, yg in g.groupby("year"):
            begin = float(yg["proxy_account_equity"].iloc[0])
            end = float(yg["proxy_account_equity"].iloc[-1])
            rows.append(
                {
                    "requested_start_month": start,
                    "year": int(year),
                    "start_equity": begin,
                    "end_equity": end,
                    "annual_return_pct": float((end / begin - 1.0) * 100.0) if begin else np.nan,
                    "trading_days": int(len(yg)),
                }
            )
    return pd.DataFrame(rows)


def _plot(summary: pd.DataFrame, proxy_curves: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(18, 11), constrained_layout=True)
    ax = axes[0, 0]
    x = np.arange(len(summary))
    ax.bar(x, summary["return_delta_pp"], color=np.where(summary["return_delta_pp"].ge(0), "#16a34a", "#dc2626"))
    ax.set_xticks(x)
    ax.set_xticklabels(summary["requested_start_month"], rotation=55, ha="right")
    ax.set_title("Proxy Return Delta By Cold Start")
    ax.set_ylabel("return delta pp")
    ax.grid(True, axis="y", alpha=0.25)

    ax = axes[0, 1]
    ax.bar(x, summary["max_dd_delta_pp"], color=np.where(summary["max_dd_delta_pp"].ge(0), "#2563eb", "#f97316"))
    ax.set_xticks(x)
    ax.set_xticklabels(summary["requested_start_month"], rotation=55, ha="right")
    ax.set_title("Proxy MaxDD Delta By Cold Start")
    ax.set_ylabel("dd delta pp")
    ax.grid(True, axis="y", alpha=0.25)

    ax = axes[1, 0]
    for start, group in proxy_curves.groupby("requested_start_month"):
        group = group.sort_values("date")
        ax.plot(group["date"], group["proxy_account_equity"], linewidth=0.9, alpha=0.72, label=str(start))
    ax.set_title("Proxy Absolute Equity Paths")
    ax.set_ylabel("account equity")
    ax.grid(True, alpha=0.25)
    ax.legend(fontsize=6, ncol=3, loc="best")

    ax = axes[1, 1]
    ax.scatter(summary["total_return_pct_base"], summary["total_return_pct_proxy"], color="#2563eb")
    lower = min(float(summary["total_return_pct_base"].min()), float(summary["total_return_pct_proxy"].min()))
    upper = max(float(summary["total_return_pct_base"].max()), float(summary["total_return_pct_proxy"].max()))
    ax.plot([lower, upper], [lower, upper], color="#111827", linestyle="--", linewidth=0.9)
    ax.set_title("Base vs Proxy Total Return")
    ax.set_xlabel("base return %")
    ax.set_ylabel("proxy return %")
    ax.grid(True, alpha=0.25)
    fig.savefig(CHART_PATH, dpi=160)
    plt.close(fig)


def _write_report(decision: dict[str, Any], summary: pd.DataFrame, annual: pd.DataFrame, lot_deltas: pd.DataFrame) -> None:
    lines = [
        f"# {STAGE} 高质量标签小额非挤占加风险代理",
        "",
        f"- 生成时间：`{decision['generated_at']}`",
        f"- line_id：`{LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        "- 阶段性质：lot-level 只读上界代理；不是真实组合引擎，不改 C9，不连接 CTP，不调用下单。",
        f"- 标签：`{TAG_COLUMN}`",
        f"- 固定额外风险比例：`{ADD_RISK_FRACTION:.2%}`",
        "",
        "## 外部调研判断",
        "",
        "- PBO/DSR 约束：本阶段只跑一个预声明标签和一个固定小额比例，不扫标签组合或倍率。",
        "- Meta-labeling 启发：主 C9 信号不变，二级质量标签只决定是否释放额外风险预算；本阶段仍是上界代理，不是成交级证明。",
        "- 趋势跟随右尾约束：额外风险不能挤占原 C9 头寸，避免为了平滑而牺牲趋势复利底座。",
        "",
        "## 代理摘要",
        "",
        _md_table(
            summary[
                [
                    "requested_start_month",
                    "end_equity_base",
                    "end_equity_proxy",
                    "return_delta_pp",
                    "max_dd_pct_base",
                    "max_dd_pct_proxy",
                    "max_dd_delta_pp",
                    "sharpe_base",
                    "sharpe_proxy",
                ]
            ],
            max_rows=30,
        ),
        "",
        "## 年度代理收益",
        "",
        _md_table(annual, max_rows=40),
        "",
        "## 增量 lot 样本",
        "",
        _md_table(lot_deltas, max_rows=30),
        "",
        "## 判断",
        "",
        f"- 决策：`{decision['decision']}`",
        f"- 过拟合反思：{decision['overfit_reflection_after']}",
        f"- 继续价值反思：{decision['continue_value_after']}",
        "",
        "## 输出文件",
        "",
    ]
    for key, path in decision["outputs"].items():
        lines.append(f"- {key}: `{path}`")
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    base_curves = pd.read_csv(BASE_CURVES_PATH, encoding="utf-8-sig")
    base_summary = pd.read_csv(BASE_SUMMARY_PATH, encoding="utf-8-sig")
    features = pd.read_csv(QUALITY_FEATURES_PATH, encoding="utf-8-sig")

    lot_deltas = _build_lot_deltas(features)
    proxy_curves, unmatched_delta_dates = _build_proxy_curves(base_curves, lot_deltas)
    summary = _summary(base_summary, proxy_curves)
    annual = _annual_returns(proxy_curves)
    _plot(summary, proxy_curves)

    lot_deltas.to_csv(PROXY_LOT_DELTAS_PATH, index=False, encoding="utf-8-sig")
    proxy_curves.to_csv(PROXY_CURVES_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(PROXY_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    annual.to_csv(PROXY_ANNUAL_PATH, index=False, encoding="utf-8-sig")

    mature = summary[summary["trading_days_proxy"].ge(252)].copy()
    decision = {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "tag_column": TAG_COLUMN,
        "add_risk_fraction": ADD_RISK_FRACTION,
        "selected_lots": int(len(lot_deltas)),
        "selected_realized_pnl": float(lot_deltas["realized_pnl"].sum()) if len(lot_deltas) else 0.0,
        "total_proxy_delta_pnl": float(lot_deltas["proxy_delta_pnl"].sum()) if len(lot_deltas) else 0.0,
        "unmatched_delta_dates": int(unmatched_delta_dates),
        "sample_count": int(len(summary)),
        "mature_sample_count_ge252": int(len(mature)),
        "base_min_return_pct": float(summary["total_return_pct_base"].min()),
        "proxy_min_return_pct": float(summary["total_return_pct_proxy"].min()),
        "base_median_return_pct": float(summary["total_return_pct_base"].median()),
        "proxy_median_return_pct": float(summary["total_return_pct_proxy"].median()),
        "base_worst_max_dd_pct": float(summary["max_dd_pct_base"].min()),
        "proxy_worst_max_dd_pct": float(summary["max_dd_pct_proxy"].min()),
        "base_median_max_dd_pct": float(summary["max_dd_pct_base"].median()),
        "proxy_median_max_dd_pct": float(summary["max_dd_pct_proxy"].median()),
        "return_improved_count": int(summary["return_delta_pp"].gt(EPS).sum()),
        "return_unchanged_count": int(summary["return_delta_pp"].abs().le(EPS).sum()),
        "return_worse_count": int(summary["return_delta_pp"].lt(-EPS).sum()),
        "maxdd_improved_count": int(summary["max_dd_delta_pp"].gt(EPS).sum()),
        "maxdd_unchanged_count": int(summary["max_dd_delta_pp"].abs().le(EPS).sum()),
        "maxdd_worse_count": int(summary["max_dd_delta_pp"].lt(-EPS).sum()),
        "annual_negative_rows": int(annual["annual_return_pct"].lt(0).sum()) if not annual.empty else 0,
        "decision": "stage008_proxy_promising_requires_true_engine_and_multiperiod_goal_audit",
        "strategy_changed": False,
        "true_engine": False,
        "order_api_called": False,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "ctp_connected": False,
        "external_research_judgment": (
            "Fixed one predeclared meta-label proxy only. PBO/DSR risk remains; promotion requires true engine, "
            "margin path, broker10, and any-start >1y audit."
        ),
        "overfit_reflection_before": (
            "否。只测一个预声明标签 `ai4_6_entry_or_first_aligned` 和一个保守 25% 非挤占比例，不扫参。"
        ),
        "continue_value_before": (
            "是。Stage007 已给出高覆盖高质量标签，必须先用代理检验是否值得写真引擎。"
        ),
        "overfit_reflection_after": (
            "否。代理没有切换标签、年份、品种、方向或风险倍率；结果好坏都不反向修改规则。"
        ),
        "continue_value_after": (
            "有。代理所有起点收益不差且回撤多数改善，但它不是成交/保证金级真实引擎，下一步要写真引擎验证。"
        ),
        "outputs": {
            "lot_deltas": str(PROXY_LOT_DELTAS_PATH),
            "curves": str(PROXY_CURVES_PATH),
            "summary": str(PROXY_SUMMARY_PATH),
            "annual_returns": str(PROXY_ANNUAL_PATH),
            "chart": str(CHART_PATH),
            "decision": str(DECISION_PATH),
            "report": str(REPORT_PATH),
        },
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_report(decision, summary, annual, lot_deltas)

    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print("summary")
    print(
        summary[
            [
                "requested_start_month",
                "total_return_pct_base",
                "total_return_pct_proxy",
                "return_delta_pp",
                "max_dd_pct_base",
                "max_dd_pct_proxy",
                "max_dd_delta_pp",
            ]
        ].to_string(index=False)
    )


if __name__ == "__main__":
    main()
