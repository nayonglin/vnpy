from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

MODEL_TAG = "stage791_stage777_old_ai_yearly_curves_v1"
OUTPUT_PREFIX = "qmt_roll_stage791_stage777_old_ai_yearly_curves"

SOURCE_TAG = "stage777_am41_oi08_monthly_v1"
SOURCE_PREFIX = "qmt_roll_stage777_am41_oi08_monthly"
SOURCE_SUMMARY_PATH = OUTPUT_DIR / f"{SOURCE_PREFIX}_summary_{SOURCE_TAG}.csv"
SOURCE_CURVES_PATH = OUTPUT_DIR / f"{SOURCE_PREFIX}_curves_{SOURCE_TAG}.csv"

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
CURVES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv"
AGGREGATE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_aggregate_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
GRID_CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_equity_grid_{MODEL_TAG}.png"
EQUITY_OVERLAY_CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_equity_overlay_{MODEL_TAG}.png"
NAV_OVERLAY_CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_nav_overlay_{MODEL_TAG}.png"


def _json_safe(value: Any) -> Any:
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (pd.Timestamp,)):
        return value.strftime("%Y-%m-%d")
    if pd.isna(value):
        return None
    return value


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if max_rows is not None:
        frame = frame.head(max_rows)
    if frame.empty:
        return "(empty)"
    return frame.to_markdown(index=False)


def _fmt_millions(value: float) -> str:
    return f"{value / 1_000_000:.2f}M"


def _load_yearly() -> tuple[pd.DataFrame, pd.DataFrame]:
    if not SOURCE_SUMMARY_PATH.exists():
        raise FileNotFoundError(SOURCE_SUMMARY_PATH)
    if not SOURCE_CURVES_PATH.exists():
        raise FileNotFoundError(SOURCE_CURVES_PATH)

    summary = pd.read_csv(SOURCE_SUMMARY_PATH)
    summary["start_month"] = summary["start_month"].astype(str)
    yearly_summary = (
        summary[summary["start_month"].str.endswith("-01")]
        .copy()
        .sort_values("start_month")
        .reset_index(drop=True)
    )
    if yearly_summary.empty:
        raise RuntimeError("no January starts found in Stage777 monthly summary")

    keep_months = set(yearly_summary["start_month"])
    curves = pd.read_csv(SOURCE_CURVES_PATH, parse_dates=["date"])
    curves["start_month"] = curves["start_month"].astype(str)
    yearly_curves = (
        curves[curves["start_month"].isin(keep_months)]
        .copy()
        .sort_values(["start_month", "date"])
        .reset_index(drop=True)
    )
    if yearly_curves.empty:
        raise RuntimeError("no January starts found in Stage777 monthly curves")

    yearly_summary["stage"] = "stage791"
    yearly_summary["ai_teacher_pool"] = "old_official_ai_teacher"
    yearly_summary["line_note"] = (
        "Extracted annual starts from Stage777 monthly output. "
        "Target logic remains Stage777 AM41 + OI confirm 0.40->0.80 with the old inherited official AI pool."
    )
    yearly_curves["stage"] = "stage791"
    yearly_curves["ai_teacher_pool"] = "old_official_ai_teacher"
    return yearly_summary, yearly_curves


def _aggregate(summary: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for group_name, frame in (
        ("all_year_starts", summary),
        ("mature_252d_year_starts", summary[summary["mature_252d"].astype(int) == 1]),
    ):
        rows.append(
            {
                "group": group_name,
                "n": int(len(frame)),
                "positive_count": int(frame["positive_return"].astype(int).sum()),
                "positive_rate_pct": round(float(frame["positive_return"].astype(int).mean() * 100), 4)
                if len(frame)
                else np.nan,
                "median_return_pct": round(float(frame["rebased_total_return_pct"].median()), 4)
                if len(frame)
                else np.nan,
                "p10_return_pct": round(float(frame["rebased_total_return_pct"].quantile(0.10)), 4)
                if len(frame)
                else np.nan,
                "min_return_pct": round(float(frame["rebased_total_return_pct"].min()), 4) if len(frame) else np.nan,
                "median_max_dd_pct": round(float(frame["rebased_max_dd_pct"].median()), 4) if len(frame) else np.nan,
                "worst_max_dd_pct": round(float(frame["rebased_max_dd_pct"].min()), 4) if len(frame) else np.nan,
                "dd40_fail_count": int(frame["dd40_fail"].astype(int).sum()) if len(frame) else 0,
                "dd50_fail_count": int(frame["dd50_fail"].astype(int).sum()) if len(frame) else 0,
                "median_sharpe": round(float(frame["rebased_sharpe"].median()), 4) if len(frame) else np.nan,
                "total_trades": int(frame["total_trade_count"].sum()) if len(frame) else 0,
                "total_slippage": round(float(frame["total_slippage"].sum()), 2) if len(frame) else 0.0,
            }
        )
    return pd.DataFrame(rows)


def _plot_grid(summary: pd.DataFrame, curves: pd.DataFrame) -> None:
    months = summary["start_month"].tolist()
    fig, axes = plt.subplots(3, 3, figsize=(22, 12), sharex=False, sharey=False)
    axes_flat = axes.ravel()
    for ax, start_month in zip(axes_flat, months, strict=False):
        row = summary[summary["start_month"] == start_month].iloc[0]
        frame = curves[curves["start_month"] == start_month]
        ax.plot(frame["date"], frame["rebased_equity"], color="#1f77b4", linewidth=1.6)
        ax.axhline(row["account_capital"], color="#9aa3af", linestyle="--", linewidth=1.0)
        ax.set_title(
            f"{start_month}: ret {row['rebased_total_return_pct']:.0f}% | "
            f"DD {row['rebased_max_dd_pct']:.1f}% | trades {row['total_trade_count']:.0f}",
            fontsize=10,
        )
        ax.grid(True, alpha=0.22)
        ax.tick_params(axis="x", labelrotation=20)
        ax.yaxis.set_major_formatter(lambda x, _pos: _fmt_millions(x))
    for ax in axes_flat[len(months) :]:
        ax.axis("off")
    fig.suptitle("Stage777 Old Official AI Teacher: Annual Start Equity Curves", fontsize=16)
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    fig.savefig(GRID_CHART_PATH, dpi=180)
    plt.close(fig)


def _plot_overlay(summary: pd.DataFrame, curves: pd.DataFrame, *, nav: bool) -> None:
    fig, ax = plt.subplots(figsize=(20, 8))
    colors = plt.cm.viridis(np.linspace(0.08, 0.92, len(summary)))
    y_col = "rebased_nav" if nav else "rebased_equity"
    for color, (_, row) in zip(colors, summary.iterrows(), strict=False):
        frame = curves[curves["start_month"] == row["start_month"]]
        label = f"{row['start_month']} ({row['rebased_total_return_pct']:.0f}%)"
        ax.plot(frame["date"], frame[y_col], linewidth=1.5, color=color, label=label)
    if nav:
        ax.axhline(1.0, color="#9aa3af", linestyle="--", linewidth=1.1)
        ax.set_ylabel("NAV")
        title = "Stage777 Old Official AI Teacher: Annual Start NAV Curves"
        out_path = NAV_OVERLAY_CHART_PATH
    else:
        ax.axhline(float(summary["account_capital"].iloc[0]), color="#9aa3af", linestyle="--", linewidth=1.1)
        ax.yaxis.set_major_formatter(lambda x, _pos: _fmt_millions(x))
        ax.set_ylabel("Rebased account equity")
        title = "Stage777 Old Official AI Teacher: Annual Start Equity Curves"
        out_path = EQUITY_OVERLAY_CHART_PATH
    ax.set_title(title, fontsize=16)
    ax.set_xlabel("Date")
    ax.grid(True, alpha=0.25)
    ax.legend(ncol=3, fontsize=9, frameon=True)
    fig.tight_layout()
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def _write_report(summary: pd.DataFrame, aggregate: pd.DataFrame) -> None:
    cols = [
        "start_month",
        "rebased_end_equity",
        "rebased_total_return_pct",
        "rebased_max_dd_pct",
        "rebased_sharpe",
        "total_trade_count",
        "total_slippage",
        "nonzero_daily_win_rate_pct",
    ]
    display = summary[cols].copy()
    for col in [
        "rebased_end_equity",
        "rebased_total_return_pct",
        "rebased_max_dd_pct",
        "rebased_sharpe",
        "total_trade_count",
        "total_slippage",
        "nonzero_daily_win_rate_pct",
    ]:
        display[col] = display[col].map(lambda x: round(float(x), 4))

    text = "\n".join(
        [
            "# Stage791 Stage777 Old AI Teacher Yearly Curves",
            "",
            "本阶段不新增策略参数，不重跑策略逻辑；只从 Stage777 逐月启动结果中抽取年度启动样本并绘图。",
            "",
            "口径：Stage777 AM41、基础 risk_multiplier=0.40、命中 `OI上升 + 价格沿方向` 恢复到 0.80、继承旧正式 AI 品种池。",
            "",
            "## Aggregate",
            "",
            _md_table(aggregate),
            "",
            "## Annual Starts",
            "",
            _md_table(display),
            "",
            "## Charts",
            "",
            f"- {GRID_CHART_PATH}",
            f"- {EQUITY_OVERLAY_CHART_PATH}",
            f"- {NAV_OVERLAY_CHART_PATH}",
            "",
            "## Decision",
            "",
            "旧 AI 老师池在 Stage777 年度起点上保留了很强右尾，但 2018-2021 起点回撤接近 -49%，不能单独作为低回撤正式替代。",
        ]
    )
    REPORT_PATH.write_text(text + "\n", encoding="utf-8")


def main() -> None:
    summary, curves = _load_yearly()
    aggregate = _aggregate(summary)

    summary.to_csv(SUMMARY_PATH, index=False)
    curves.to_csv(CURVES_PATH, index=False)
    aggregate.to_csv(AGGREGATE_PATH, index=False)

    _plot_grid(summary, curves)
    _plot_overlay(summary, curves, nav=False)
    _plot_overlay(summary, curves, nav=True)
    _write_report(summary, aggregate)

    decision = {
        "stage": "stage791",
        "source": str(SOURCE_SUMMARY_PATH),
        "decision": "old_ai_teacher_yearly_reference_only_not_new_promotion",
        "overfit_risk": "low_for_this_extraction_no_new_parameter",
        "continued_value": "yes_as_reference_baseline_for_new_teacher_ai_pool_research",
        "outputs": {
            "summary": str(SUMMARY_PATH),
            "curves": str(CURVES_PATH),
            "aggregate": str(AGGREGATE_PATH),
            "grid_chart": str(GRID_CHART_PATH),
            "equity_overlay_chart": str(EQUITY_OVERLAY_CHART_PATH),
            "nav_overlay_chart": str(NAV_OVERLAY_CHART_PATH),
            "report": str(REPORT_PATH),
        },
        "aggregate": aggregate.to_dict(orient="records"),
    }
    DECISION_PATH.write_text(json.dumps(decision, ensure_ascii=False, indent=2, default=_json_safe) + "\n", encoding="utf-8")

    print(_md_table(summary[["start_month", "rebased_total_return_pct", "rebased_max_dd_pct", "rebased_sharpe", "total_trade_count"]]))
    print("\nAggregate:")
    print(_md_table(aggregate))
    print(f"\nWrote {GRID_CHART_PATH}")
    print(f"Wrote {EQUITY_OVERLAY_CHART_PATH}")
    print(f"Wrote {NAV_OVERLAY_CHART_PATH}")


if __name__ == "__main__":
    main()
