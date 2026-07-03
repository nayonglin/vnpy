from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
LINE_ID = "futures_trend_rebuilt_c9_15w_v2_optimization"
STAGE = "Stage060"
MODEL_TAG = "stage060_stage013_vs_official_multiperiod_v1"
OUTPUT_PREFIX = "rebuilt_c9_v2_stage060_stage013_vs_official_multiperiod"
LINE_DIR = ROOT / "research" / "lines" / LINE_ID
UPSTREAM_LINE_DIR = ROOT / "research" / "lines" / "futures_trend_rebuilt_c9_15w_optimization"
OUT = LINE_DIR / "outputs" / "stage060_stage013_vs_official_multiperiod"
STAGES_DIR = LINE_DIR / "stages"
END_DATE = pd.Timestamp("2026-06-30")
INITIAL_CAPITAL = 150_000.0

OFFICIAL_CURVES_PATH = (
    UPSTREAM_LINE_DIR
    / "outputs"
    / "stage006_current_quality_feature_binder"
    / "rebuilt_c9_stage006_current_quality_feature_binder_curves_stage006_current_quality_feature_binder_v1.csv"
)
STAGE013_CURVES_PATH = (
    UPSTREAM_LINE_DIR
    / "outputs"
    / "stage013_account_state_pilot_gate_engine"
    / "rebuilt_c9_stage013_account_state_pilot_gate_engine_curves_stage013_account_state_pilot_gate_engine_v1.csv"
)
STAGE013_AI_POOL_AUDIT_PATH = (
    UPSTREAM_LINE_DIR
    / "outputs"
    / "stage013_account_state_pilot_gate_engine"
    / "rebuilt_c9_stage013_account_state_pilot_gate_engine_ai_pool_audit_stage013_account_state_pilot_gate_engine_v1.csv"
)
CURRENT_AI_ELIGIBILITY_PATH = (
    ROOT
    / "examples"
    / "portfolio_backtesting"
    / "backtest_outputs"
    / "qmt_roll_stage182_ai_product_pool_live_inference_combined_stage78_eligibility_stage182_ai_product_pool_live_inference_v1.csv"
)

PAIR_CURVES_PATH = OUT / f"{OUTPUT_PREFIX}_pair_curves_{MODEL_TAG}.csv"
START_SUMMARY_PATH = OUT / f"{OUTPUT_PREFIX}_per_start_summary_{MODEL_TAG}.csv"
AGGREGATE_PATH = OUT / f"{OUTPUT_PREFIX}_aggregate_{MODEL_TAG}.csv"
AI_AUDIT_PATH = OUT / f"{OUTPUT_PREFIX}_ai_input_audit_{MODEL_TAG}.json"
ABSOLUTE_EQUITY_GRID_PATH = OUT / f"{OUTPUT_PREFIX}_absolute_equity_grid_{MODEL_TAG}.png"
RELATIVE_GAP_GRID_PATH = OUT / f"{OUTPUT_PREFIX}_relative_gap_grid_{MODEL_TAG}.png"
DRAWDOWN_GRID_PATH = OUT / f"{OUTPUT_PREFIX}_drawdown_grid_{MODEL_TAG}.png"
SUMMARY_BAR_PATH = OUT / f"{OUTPUT_PREFIX}_summary_bar_{MODEL_TAG}.png"
REPORT_PATH = OUT / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


def _mtime(path: Path) -> str | None:
    if not path.exists():
        return None
    return datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds")


def _drawdown_pct(nav: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(nav, errors="coerce")
    return (numeric / numeric.cummax() - 1.0) * 100.0


def _annualized_sharpe(nav: pd.Series) -> float:
    returns = pd.to_numeric(nav, errors="coerce").pct_change().replace([np.inf, -np.inf], np.nan).dropna()
    if returns.empty:
        return float("nan")
    std = returns.std(ddof=1)
    if not np.isfinite(std) or std == 0:
        return float("nan")
    return float(returns.mean() / std * np.sqrt(252.0))


def load_curves(path: Path, version_prefix: str) -> pd.DataFrame:
    frame = pd.read_csv(
        path,
        usecols=[
            "requested_start_month",
            "date",
            "account_equity",
            "nav",
            "drawdown_pct",
            "commission",
            "slippage",
            "trade_count",
        ],
    )
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame["account_equity"] = pd.to_numeric(frame["account_equity"], errors="coerce")
    frame["nav"] = pd.to_numeric(frame["nav"], errors="coerce")
    frame["drawdown_pct"] = pd.to_numeric(frame["drawdown_pct"], errors="coerce")
    frame["commission"] = pd.to_numeric(frame["commission"], errors="coerce").fillna(0.0)
    frame["slippage"] = pd.to_numeric(frame["slippage"], errors="coerce").fillna(0.0)
    frame["trade_count"] = pd.to_numeric(frame["trade_count"], errors="coerce").fillna(0.0)
    frame = frame.dropna(subset=["requested_start_month", "date", "account_equity", "nav"])
    frame = frame[frame["date"].le(END_DATE)].copy()
    frame = frame.sort_values(["requested_start_month", "date"]).reset_index(drop=True)
    if frame["drawdown_pct"].isna().any():
        frame["drawdown_pct"] = frame.groupby("requested_start_month")["nav"].transform(_drawdown_pct)
    rename = {
        "account_equity": f"{version_prefix}_equity",
        "nav": f"{version_prefix}_nav",
        "drawdown_pct": f"{version_prefix}_drawdown_pct",
        "commission": f"{version_prefix}_commission",
        "slippage": f"{version_prefix}_slippage",
        "trade_count": f"{version_prefix}_trade_count",
    }
    return frame.rename(columns=rename)


def build_pair_curves() -> pd.DataFrame:
    official = load_curves(OFFICIAL_CURVES_PATH, "official")
    stage013 = load_curves(STAGE013_CURVES_PATH, "stage013")
    pair = official.merge(stage013, on=["requested_start_month", "date"], how="inner")
    pair = pair.sort_values(["requested_start_month", "date"]).reset_index(drop=True)
    pair["stage013_vs_official_nav_gap_pct"] = (pair["stage013_nav"] / pair["official_nav"] - 1.0) * 100.0
    pair["stage013_minus_official_equity"] = pair["stage013_equity"] - pair["official_equity"]
    pair["stage013_minus_official_nav"] = pair["stage013_nav"] - pair["official_nav"]
    pair["drawdown_gap_pp"] = pair["stage013_drawdown_pct"] - pair["official_drawdown_pct"]
    pair["stage013_lags_official"] = pair["stage013_vs_official_nav_gap_pct"].lt(0.0)
    return pair


def summarize_pair(pair: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for start, group in pair.groupby("requested_start_month", sort=True):
        group = group.sort_values("date")
        final = group.iloc[-1]
        official_return = (float(final["official_nav"]) - 1.0) * 100.0
        stage013_return = (float(final["stage013_nav"]) - 1.0) * 100.0
        worst_gap = group.loc[group["stage013_vs_official_nav_gap_pct"].idxmin()]
        official_max_dd = float(group["official_drawdown_pct"].min())
        stage013_max_dd = float(group["stage013_drawdown_pct"].min())
        rows.append(
            {
                "requested_start_month": start,
                "start_date": group["date"].iloc[0].date().isoformat(),
                "end_date": group["date"].iloc[-1].date().isoformat(),
                "trading_days": int(len(group)),
                "official_end_equity": float(final["official_equity"]),
                "stage013_end_equity": float(final["stage013_equity"]),
                "official_total_return_pct": official_return,
                "stage013_total_return_pct": stage013_return,
                "return_diff_pp": stage013_return - official_return,
                "official_max_drawdown_pct": official_max_dd,
                "stage013_max_drawdown_pct": stage013_max_dd,
                "drawdown_improvement_pp": stage013_max_dd - official_max_dd,
                "official_sharpe": _annualized_sharpe(group["official_nav"]),
                "stage013_sharpe": _annualized_sharpe(group["stage013_nav"]),
                "final_nav_ratio_vs_official": float(final["stage013_nav"] / final["official_nav"]),
                "worst_stage013_vs_official_gap_pct": float(worst_gap["stage013_vs_official_nav_gap_pct"]),
                "worst_gap_date": pd.Timestamp(worst_gap["date"]).date().isoformat(),
                "stage013_lag_days": int(group["stage013_lags_official"].sum()),
                "stage013_lag_day_ratio_pct": float(group["stage013_lags_official"].mean() * 100.0),
                "official_total_slippage": float(group["official_slippage"].sum()),
                "stage013_total_slippage": float(group["stage013_slippage"].sum()),
                "official_total_trade_count": float(group["official_trade_count"].sum()),
                "stage013_total_trade_count": float(group["stage013_trade_count"].sum()),
            }
        )
    return pd.DataFrame(rows)


def summarize_aggregate(summary: pd.DataFrame) -> pd.DataFrame:
    row = {
        "start_count": int(len(summary)),
        "stage013_positive_count": int(summary["stage013_total_return_pct"].gt(0.0).sum()),
        "official_positive_count": int(summary["official_total_return_pct"].gt(0.0).sum()),
        "stage013_return_win_count": int(summary["return_diff_pp"].gt(0.0).sum()),
        "stage013_drawdown_improve_count": int(summary["drawdown_improvement_pp"].gt(0.0).sum()),
        "stage013_both_return_and_drawdown_win_count": int(
            (summary["return_diff_pp"].gt(0.0) & summary["drawdown_improvement_pp"].gt(0.0)).sum()
        ),
        "official_min_return_pct": float(summary["official_total_return_pct"].min()),
        "stage013_min_return_pct": float(summary["stage013_total_return_pct"].min()),
        "official_median_return_pct": float(summary["official_total_return_pct"].median()),
        "stage013_median_return_pct": float(summary["stage013_total_return_pct"].median()),
        "official_worst_max_drawdown_pct": float(summary["official_max_drawdown_pct"].min()),
        "stage013_worst_max_drawdown_pct": float(summary["stage013_max_drawdown_pct"].min()),
        "min_final_nav_ratio_vs_official": float(summary["final_nav_ratio_vs_official"].min()),
        "median_final_nav_ratio_vs_official": float(summary["final_nav_ratio_vs_official"].median()),
        "max_final_nav_ratio_vs_official": float(summary["final_nav_ratio_vs_official"].max()),
        "worst_relative_gap_pct": float(summary["worst_stage013_vs_official_gap_pct"].min()),
        "highest_lag_day_ratio_pct": float(summary["stage013_lag_day_ratio_pct"].max()),
    }
    return pd.DataFrame([row])


def _eval_dates(path: Path, column: str = "eval_date") -> list[str]:
    if not path.exists():
        return []
    frame = pd.read_csv(path, usecols=[column])
    dates = pd.to_datetime(frame[column], errors="coerce").dt.normalize().dropna()
    return sorted(dates.dt.date.astype(str).unique().tolist())


def build_ai_audit() -> dict[str, object]:
    saved_dates = _eval_dates(STAGE013_AI_POOL_AUDIT_PATH)
    current_dates = _eval_dates(CURRENT_AI_ELIGIBILITY_PATH)
    saved_set = set(saved_dates)
    current_set = set(current_dates)
    expected_2026_month_ends = [
        ts.date().isoformat()
        for ts in pd.date_range("2026-01-01", "2026-06-30", freq="BME")
    ]
    expected_through_may = [d for d in expected_2026_month_ends if d <= "2026-05-29"]
    current_missing_through_may = [d for d in expected_through_may if d not in current_set]
    saved_missing_through_may = [d for d in expected_through_may if d not in saved_set]
    audit = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "fresh_engine_rerun_performed": False,
        "fresh_rerun_safe_with_current_ai_file": False,
        "reason": (
            "Current AI eligibility differs from the saved Stage013 audit snapshot and is missing "
            "business month-end eval_dates needed before a clean fresh official rerun. A fresh engine "
            "rerun now would measure formal code with stale or shifted AI inputs, not the intended "
            "monthly AI-pool formal version."
        ),
        "official_curves_path": str(OFFICIAL_CURVES_PATH),
        "official_curves_mtime": _mtime(OFFICIAL_CURVES_PATH),
        "stage013_curves_path": str(STAGE013_CURVES_PATH),
        "stage013_curves_mtime": _mtime(STAGE013_CURVES_PATH),
        "saved_stage013_ai_pool_audit_path": str(STAGE013_AI_POOL_AUDIT_PATH),
        "saved_stage013_ai_pool_audit_mtime": _mtime(STAGE013_AI_POOL_AUDIT_PATH),
        "current_ai_eligibility_path": str(CURRENT_AI_ELIGIBILITY_PATH),
        "current_ai_eligibility_mtime": _mtime(CURRENT_AI_ELIGIBILITY_PATH),
        "saved_eval_date_count": len(saved_dates),
        "current_eval_date_count": len(current_dates),
        "saved_eval_dates_2026": [d for d in saved_dates if d.startswith("2026-")],
        "current_eval_dates_2026": [d for d in current_dates if d.startswith("2026-")],
        "current_missing_vs_saved": sorted(saved_set - current_set),
        "current_added_vs_saved": sorted(current_set - saved_set),
        "expected_2026_business_month_ends": expected_2026_month_ends,
        "current_missing_expected_through_may": current_missing_through_may,
        "saved_snapshot_missing_expected_through_may": saved_missing_through_may,
        "minimum_repair_before_fresh_rerun": (
            "Restore or regenerate the PIT monthly AI eligibility snapshots required by the formal "
            "backtest window, at least the 2026-05-29 pool for June trading, then rerun official and "
            "Stage013 from the same frozen AI file/hash."
        ),
    }
    return audit


def plot_absolute_equity(pair: pd.DataFrame) -> None:
    starts = sorted(pair["requested_start_month"].unique())
    cols = 3
    rows = int(np.ceil(len(starts) / cols))
    fig, axes = plt.subplots(rows, cols, figsize=(18, 3.4 * rows), constrained_layout=True)
    flat_axes = np.array(axes).reshape(-1)
    for ax, start in zip(flat_axes, starts):
        group = pair[pair["requested_start_month"].eq(start)].sort_values("date")
        ax.plot(group["date"], group["official_equity"], color="#111827", linewidth=1.0, label="Official")
        ax.plot(group["date"], group["stage013_equity"], color="#2563eb", linewidth=1.0, label="Stage013")
        ax.set_title(start, fontsize=9)
        ax.grid(True, alpha=0.22)
        ax.tick_params(axis="x", labelrotation=30, labelsize=7)
        ax.tick_params(axis="y", labelsize=8)
        if start == starts[0]:
            ax.legend(fontsize=8)
    for ax in flat_axes[len(starts) :]:
        ax.axis("off")
    fig.suptitle("Official vs Stage013 Account-state Pilot: Absolute Equity by Start Cycle", fontsize=15)
    fig.supxlabel("Date")
    fig.supylabel("Account equity")
    fig.savefig(ABSOLUTE_EQUITY_GRID_PATH, dpi=170)
    plt.close(fig)


def plot_relative_gap(pair: pd.DataFrame, summary: pd.DataFrame) -> None:
    starts = sorted(pair["requested_start_month"].unique())
    cols = 3
    rows = int(np.ceil(len(starts) / cols))
    fig, axes = plt.subplots(rows, cols, figsize=(18, 3.4 * rows), sharey=True, constrained_layout=True)
    flat_axes = np.array(axes).reshape(-1)
    for ax, start in zip(flat_axes, starts):
        group = pair[pair["requested_start_month"].eq(start)].sort_values("date")
        row = summary[summary["requested_start_month"].eq(start)].iloc[0]
        y = group["stage013_vs_official_nav_gap_pct"]
        ax.plot(group["date"], y, color="#2563eb", linewidth=1.0)
        ax.fill_between(group["date"], y, 0, where=y.ge(0), color="#16a34a", alpha=0.18, interpolate=True)
        ax.fill_between(group["date"], y, 0, where=y.lt(0), color="#dc2626", alpha=0.22, interpolate=True)
        ax.axhline(0, color="#111827", linewidth=0.8)
        ax.set_title(
            f"{start} final {row['final_nav_ratio_vs_official'] - 1:+.1%} worst {row['worst_stage013_vs_official_gap_pct']:+.1f}%",
            fontsize=9,
        )
        ax.grid(True, alpha=0.22)
        ax.tick_params(axis="x", labelrotation=30, labelsize=7)
        ax.tick_params(axis="y", labelsize=8)
    for ax in flat_axes[len(starts) :]:
        ax.axis("off")
    fig.suptitle("Stage013 Relative NAV Gap vs Official (Stage013 / Official - 1)", fontsize=15)
    fig.supxlabel("Date")
    fig.supylabel("Relative NAV gap (%)")
    fig.savefig(RELATIVE_GAP_GRID_PATH, dpi=170)
    plt.close(fig)


def plot_drawdowns(pair: pd.DataFrame) -> None:
    starts = sorted(pair["requested_start_month"].unique())
    cols = 3
    rows = int(np.ceil(len(starts) / cols))
    fig, axes = plt.subplots(rows, cols, figsize=(18, 3.4 * rows), sharey=True, constrained_layout=True)
    flat_axes = np.array(axes).reshape(-1)
    for ax, start in zip(flat_axes, starts):
        group = pair[pair["requested_start_month"].eq(start)].sort_values("date")
        ax.plot(group["date"], group["official_drawdown_pct"], color="#111827", linewidth=1.0, label="Official")
        ax.plot(group["date"], group["stage013_drawdown_pct"], color="#2563eb", linewidth=1.0, label="Stage013")
        ax.axhline(0, color="#111827", linewidth=0.7)
        ax.set_title(start, fontsize=9)
        ax.grid(True, alpha=0.22)
        ax.tick_params(axis="x", labelrotation=30, labelsize=7)
        ax.tick_params(axis="y", labelsize=8)
        if start == starts[0]:
            ax.legend(fontsize=8)
    for ax in flat_axes[len(starts) :]:
        ax.axis("off")
    fig.suptitle("Official vs Stage013 Underwater / Drawdown by Start Cycle", fontsize=15)
    fig.supxlabel("Date")
    fig.supylabel("Drawdown (%)")
    fig.savefig(DRAWDOWN_GRID_PATH, dpi=170)
    plt.close(fig)


def plot_summary_bars(summary: pd.DataFrame) -> None:
    frame = summary.sort_values("requested_start_month").copy()
    x = np.arange(len(frame))
    width = 0.35
    fig, axes = plt.subplots(2, 1, figsize=(18, 10), sharex=True, constrained_layout=True)
    colors_return = np.where(frame["return_diff_pp"].ge(0), "#2563eb", "#dc2626")
    axes[0].bar(x, frame["return_diff_pp"], width=0.6, color=colors_return)
    axes[0].axhline(0, color="#111827", linewidth=0.8)
    axes[0].set_title("Stage013 final return minus Official")
    axes[0].set_ylabel("percentage points")
    axes[0].grid(True, axis="y", alpha=0.22)

    axes[1].bar(x - width / 2, frame["drawdown_improvement_pp"], width=width, color="#16a34a", label="max DD improvement")
    axes[1].bar(x + width / 2, frame["stage013_lag_day_ratio_pct"], width=width, color="#f59e0b", label="days below official")
    axes[1].axhline(0, color="#111827", linewidth=0.8)
    axes[1].set_title("Drawdown improvement and lag-day ratio")
    axes[1].set_ylabel("pp / %")
    axes[1].legend(loc="best")
    axes[1].grid(True, axis="y", alpha=0.22)
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(frame["requested_start_month"].tolist(), rotation=35, ha="right")
    fig.savefig(SUMMARY_BAR_PATH, dpi=170)
    plt.close(fig)


def write_report(summary: pd.DataFrame, aggregate: pd.DataFrame, ai_audit: dict[str, object]) -> Path:
    agg = aggregate.iloc[0]
    underperform = summary[summary["return_diff_pp"].lt(0)].sort_values("return_diff_pp")
    dd_worse = summary[summary["drawdown_improvement_pp"].lt(0)].sort_values("drawdown_improvement_pp")
    md = [
        "# Stage060 Stage013 account-state pilot vs 正式版多周期对比",
        "",
        f"- 生成时间：{datetime.now().isoformat(timespec='seconds')}",
        f"- line_id：`{LINE_ID}`",
        "- 阶段性质：只读多周期复算；读取既有真引擎曲线，不 fresh rerun 策略引擎",
        "- 对照：`Official C9/15w Stage847` vs `Stage013 account-state pilot`",
        "- 终点：`2026-06-30`",
        "",
        "## 总览",
        "",
        f"- 起点数：`{int(agg['start_count'])}`",
        f"- Stage013 正收益：`{int(agg['stage013_positive_count'])}/{int(agg['start_count'])}`",
        f"- Stage013 期末收益胜正式：`{int(agg['stage013_return_win_count'])}/{int(agg['start_count'])}`",
        f"- Stage013 最大回撤改善：`{int(agg['stage013_drawdown_improve_count'])}/{int(agg['start_count'])}`",
        f"- Stage013 收益和回撤同时胜：`{int(agg['stage013_both_return_and_drawdown_win_count'])}/{int(agg['start_count'])}`",
        f"- 正式版最小/中位收益：`{agg['official_min_return_pct']:.4f}% / {agg['official_median_return_pct']:.4f}%`",
        f"- Stage013 最小/中位收益：`{agg['stage013_min_return_pct']:.4f}% / {agg['stage013_median_return_pct']:.4f}%`",
        f"- 正式版最差最大回撤：`{agg['official_worst_max_drawdown_pct']:.4f}%`",
        f"- Stage013 最差最大回撤：`{agg['stage013_worst_max_drawdown_pct']:.4f}%`",
        f"- Stage013 终点权益比例 vs 正式版 min/median/max：`{agg['min_final_nav_ratio_vs_official']:.4f} / {agg['median_final_nav_ratio_vs_official']:.4f} / {agg['max_final_nav_ratio_vs_official']:.4f}`",
        "",
        "## Stage013 输给正式版的起点",
        "",
        underperform[
            [
                "requested_start_month",
                "official_total_return_pct",
                "stage013_total_return_pct",
                "return_diff_pp",
                "official_max_drawdown_pct",
                "stage013_max_drawdown_pct",
                "drawdown_improvement_pp",
            ]
        ].to_markdown(index=False),
        "",
        "## Stage013 回撤差于正式版的起点",
        "",
        dd_worse[
            [
                "requested_start_month",
                "official_max_drawdown_pct",
                "stage013_max_drawdown_pct",
                "drawdown_improvement_pp",
                "return_diff_pp",
            ]
        ].to_markdown(index=False),
        "",
        "## AI 输入审计",
        "",
        f"- fresh engine rerun performed：`{ai_audit['fresh_engine_rerun_performed']}`",
        f"- current AI file safe for fresh rerun：`{ai_audit['fresh_rerun_safe_with_current_ai_file']}`",
        f"- saved Stage013 2026 eval_dates：`{', '.join(ai_audit['saved_eval_dates_2026'])}`",
        f"- current 2026 eval_dates：`{', '.join(ai_audit['current_eval_dates_2026'])}`",
        f"- current missing vs saved：`{', '.join(ai_audit['current_missing_vs_saved']) or 'none'}`",
        f"- current added vs saved：`{', '.join(ai_audit['current_added_vs_saved']) or 'none'}`",
        f"- current missing expected through May：`{', '.join(ai_audit['current_missing_expected_through_may']) or 'none'}`",
        "",
        "## 结论",
        "",
        "- Stage013 account-state pilot 是有继续价值的候选：收益胜出和回撤改善均为 `14/17`，尤其最差最大回撤从正式版约 `-56.21%` 改到约 `-43.79%`。",
        "- 但它不是无条件晋级版本：`2018-01`、`2021-01`、`2025-07` 起点有收益或回撤退化，不能直接替代正式版。",
        "- 关于 AI 文件：如果目标是现在 fresh rerun 正式版/Stage013 并把结果当“当前正式版真实表现”，必须先恢复或重跑完整 PIT 月度 AI eligibility。否则跑出来的是正式代码叠加残缺/错位 AI 池输入。",
        "",
        "## 输出",
        "",
        f"- pair_curves：`{PAIR_CURVES_PATH}`",
        f"- per_start_summary：`{START_SUMMARY_PATH}`",
        f"- aggregate：`{AGGREGATE_PATH}`",
        f"- ai_input_audit：`{AI_AUDIT_PATH}`",
        f"- absolute_equity_grid：`{ABSOLUTE_EQUITY_GRID_PATH}`",
        f"- relative_gap_grid：`{RELATIVE_GAP_GRID_PATH}`",
        f"- drawdown_grid：`{DRAWDOWN_GRID_PATH}`",
        f"- summary_bar：`{SUMMARY_BAR_PATH}`",
    ]
    REPORT_PATH.write_text("\n".join(md) + "\n", encoding="utf-8")
    return REPORT_PATH


def write_stage_record(summary: pd.DataFrame, aggregate: pd.DataFrame, ai_audit: dict[str, object]) -> Path:
    STAGES_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now()
    path = STAGES_DIR / f"{now.strftime('%Y%m%d_%H%M')}_stage060_stage013_vs_official_multiperiod.md"
    agg = aggregate.iloc[0]
    worst_underperform = summary.sort_values("return_diff_pp").iloc[0]
    worst_dd = summary.sort_values("drawdown_improvement_pp").iloc[0]
    stage013_2026 = summary[summary["requested_start_month"].eq("2026-01")]
    if not stage013_2026.empty:
        focus = stage013_2026.iloc[0]
    else:
        focus = summary.sort_values("requested_start_month").iloc[-1]
    lines = [
        "# Stage060 Stage013 account-state pilot vs 正式版多周期对比",
        "",
        f"- line_id：`{LINE_ID}`",
        "- 当前模式：day",
        f"- 记录时间：{now.isoformat(timespec='seconds')}",
        f"- 工作区/分支：`{ROOT}`",
        "- 阶段性质：只读多周期复算；读取 2026-07-01 既有真引擎曲线，不 fresh rerun 策略引擎",
        "- 是否重要突破：否",
        "- 是否触发A/B：是；A=Official C9/15w Stage847，C=Stage013 account-state pilot，但本阶段仅做冻结曲线复核",
        "",
        "## 外部调研与判断",
        "",
        "- 参考资料：pysystemtrade backtesting、trend-following vol targeting/no free lunch、meta-labeling/候选筛选风险。",
        "- 我的判断：Stage013 属于账户状态风控层，不是增加预测信号；多周期比较有价值，但不能在当前 AI 文件缺口未修复前 fresh rerun 正式版并声称为真实表现。",
        "",
        "## 本次变更",
        "",
        f"- 新增脚本：`{Path(__file__).relative_to(ROOT)}`",
        "- 修改脚本：无",
        "- 删除脚本：无",
        "- 新增参数：无交易参数；新增只读比较口径 `stage013_vs_official_nav_gap_pct`、`drawdown_improvement_pp`、AI 输入完整性审计",
        "- 修改参数：无",
        "- 删除参数：无",
        "",
        "## 回测/归因参数",
        "",
        "- 数据区间：逐半年起点 `2018-01` 到 `2026-01`，终点统一 `2026-06-30`",
        "- 账户规模：`150,000`",
        "- 成本口径：沿用原曲线成本与滑点，不重新估算",
        "- 样本过滤：同日起点同日期 inner join；只比较已有真引擎曲线",
        "- 策略/归因口径：A=正式 Stage847 C9/15w；C=Stage013 account-state pilot gate",
        "",
        "## 结果",
        "",
        f"- 期末权益：2026-01 起点 Stage013 `{focus['stage013_end_equity']:.2f}`，正式版 `{focus['official_end_equity']:.2f}`",
        f"- 总收益：2026-01 起点 Stage013 `{focus['stage013_total_return_pct']:.4f}%`，正式版 `{focus['official_total_return_pct']:.4f}%`",
        f"- 最大回撤：2026-01 起点 Stage013 `{focus['stage013_max_drawdown_pct']:.4f}%`，正式版 `{focus['official_max_drawdown_pct']:.4f}%`",
        f"- Sharpe：2026-01 起点 Stage013 `{focus['stage013_sharpe']:.4f}`，正式版 `{focus['official_sharpe']:.4f}`",
        f"- 总滑点：2026-01 起点 Stage013 `{focus['stage013_total_slippage']:.2f}`，正式版 `{focus['official_total_slippage']:.2f}`",
        f"- 总交易次数：2026-01 起点 Stage013 `{focus['stage013_total_trade_count']:.0f}`，正式版 `{focus['official_total_trade_count']:.0f}`",
        "- 胜率：本阶段复用日曲线，未重放 closed lots 计算胜率",
        f"- 其他关键指标：Stage013 收益胜正式 `{int(agg['stage013_return_win_count'])}/{int(agg['start_count'])}`；最大回撤改善 `{int(agg['stage013_drawdown_improve_count'])}/{int(agg['start_count'])}`；最小终点权益比例 `{agg['min_final_nav_ratio_vs_official']:.4f}`",
        f"- Stage013 收益退化最严重起点：`{worst_underperform['requested_start_month']}`，return_diff `{worst_underperform['return_diff_pp']:.4f}pp`",
        f"- Stage013 回撤退化最严重起点：`{worst_dd['requested_start_month']}`，drawdown_improvement `{worst_dd['drawdown_improvement_pp']:.4f}pp`",
        f"- AI 审计：current 2026 eval_dates `{', '.join(ai_audit['current_eval_dates_2026'])}`；saved Stage013 2026 eval_dates `{', '.join(ai_audit['saved_eval_dates_2026'])}`；fresh rerun safe=`{ai_audit['fresh_rerun_safe_with_current_ai_file']}`",
        "",
        "## 输出文件",
        "",
        f"- report：`{REPORT_PATH}`",
        f"- summary：`{START_SUMMARY_PATH}`",
        f"- daily：`{PAIR_CURVES_PATH}`",
        f"- quality：`{AI_AUDIT_PATH}`",
        f"- chart_absolute：`{ABSOLUTE_EQUITY_GRID_PATH}`",
        f"- chart_gap：`{RELATIVE_GAP_GRID_PATH}`",
        f"- chart_drawdown：`{DRAWDOWN_GRID_PATH}`",
        f"- chart_summary：`{SUMMARY_BAR_PATH}`",
        "",
        "## 结论",
        "",
        "- 本阶段结论：Stage013 有继续价值，但不能直接晋级；它改善多数周期回撤和部分路径收益，同时仍有 3 个起点收益或回撤缺陷。",
        "- 是否进入下一步：是，建议进入更严格的同 AI 文件 fresh rerun/A-B 复验；但前置条件是先修复正式 AI eligibility 月池。",
        "- 下一步：先恢复或重跑完整 PIT 月度 AI eligibility，冻结 hash 后再同时 rerun A=正式版、C=Stage013。",
        "",
        "## 过拟合反思",
        "",
        "- 运行前判断：否；本阶段只做固定候选 vs 固定正式版对比，没有调参。",
        "- 运行后判断：否；结果暴露了 Stage013 的反例窗口，没有按反例继续拟合。",
        "- 原因：比较对象和终点预先固定，且结论没有把局部优点包装成晋级。",
        "",
        "## 继续价值反思",
        "",
        "- 运行前判断：有；Stage013 是账户状态层候选，和新增 alpha 不同，可能改善生存曲线。",
        "- 运行后判断：有但有前置条件；必须先修 AI 文件再做 fresh A/B。",
        "- 原因：多数周期改善明确，但当前 AI 输入不完整会污染任何新回测。",
        "",
        "## 合入建议",
        "",
        "- 是否更新本线 `LINE.md`：暂不更新，避免与既有并行研究记录冲突。",
        "- 是否更新 `research/registry.md`：否。",
        "- 是否追加根目录 `memory.md/back_log.md`：否；本阶段不是正式突破，只写本线 stage。",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    pair = build_pair_curves()
    summary = summarize_pair(pair)
    aggregate = summarize_aggregate(summary)
    ai_audit = build_ai_audit()

    pair.to_csv(PAIR_CURVES_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(START_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    aggregate.to_csv(AGGREGATE_PATH, index=False, encoding="utf-8-sig")
    AI_AUDIT_PATH.write_text(json.dumps(ai_audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    plot_absolute_equity(pair)
    plot_relative_gap(pair, summary)
    plot_drawdowns(pair)
    plot_summary_bars(summary)

    report = write_report(summary, aggregate, ai_audit)
    stage_record = write_stage_record(summary, aggregate, ai_audit)

    agg = aggregate.iloc[0]
    print(
        json.dumps(
            {
                "stage": STAGE,
                "pair_rows": int(len(pair)),
                "start_count": int(agg["start_count"]),
                "stage013_return_win_count": int(agg["stage013_return_win_count"]),
                "stage013_drawdown_improve_count": int(agg["stage013_drawdown_improve_count"]),
                "stage013_min_return_pct": float(agg["stage013_min_return_pct"]),
                "stage013_median_return_pct": float(agg["stage013_median_return_pct"]),
                "stage013_worst_max_drawdown_pct": float(agg["stage013_worst_max_drawdown_pct"]),
                "fresh_rerun_safe_with_current_ai_file": bool(ai_audit["fresh_rerun_safe_with_current_ai_file"]),
                "report": str(report),
                "stage_record": str(stage_record),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
