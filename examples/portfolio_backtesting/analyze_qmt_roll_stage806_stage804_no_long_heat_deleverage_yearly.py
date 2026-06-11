from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import replace
import json
import os
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import analyze_qmt_roll_stage513_stage208_exact_position_margin_audit as s513
import analyze_qmt_roll_stage650_stage526_200k_capital_reality_check as s650
import analyze_qmt_roll_stage772_am40_80_120_oi_monthly as s772
import analyze_qmt_roll_stage778_stage777_2022_drawdown_forensics as s778
import analyze_qmt_roll_stage800_stage777_long_lower_high_block_yearly as s800
import analyze_qmt_roll_stage804_stage777_long_tighter_initial_stop_yearly as s804


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

MODEL_TAG = "stage806_stage804_no_long_heat_deleverage_yearly_v1"
OUTPUT_PREFIX = "qmt_roll_stage806_stage804_no_long_heat_deleverage_yearly"
LINE_ID = "futures_trend_2019_data_extension"

YEAR_STARTS = s800.YEAR_STARTS
MAX_WORKERS = max(1, min(4, int(os.environ.get("STAGE806_MAX_WORKERS", "4"))))

VARIANT = "stage806_stage804_500k_am41_oi08_old_ai_long_tighter_stop_no_long_heat_delev_yearly"
LABEL = "Stage806 Stage804 no long risk-cluster heat deleverage yearly"

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
CURVES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv"
ADJUSTMENTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_stop_adjustments_{MODEL_TAG}.csv"
COMPARISON_STAGE804_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_comparison_vs_stage804_{MODEL_TAG}.csv"
COMPARISON_STAGE777_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_comparison_vs_stage777_{MODEL_TAG}.csv"
AGG_STAGE804_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_aggregate_vs_stage804_{MODEL_TAG}.csv"
AGG_STAGE777_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_aggregate_vs_stage777_{MODEL_TAG}.csv"
WINDOW_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_2025_july_window_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
RETURN_BAR_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_return_delta_vs_stage804_bar_{MODEL_TAG}.png"
DD_BAR_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_dd_delta_vs_stage804_bar_{MODEL_TAG}.png"
EQUITY_CURVES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_equity_curves_{MODEL_TAG}.png"


class QmtRollPortfolioStrategyLongTighterNoLongHeatDeleverage(
    s804.QmtRollPortfolioStrategyLongTighterInitialStop
):
    """Research-only wrapper: keep Stage804, but skip risk-cluster heat deleverage for long positions."""

    disable_long_risk_cluster_heat_deleverage: bool = True
    parameters = [
        *s804.QmtRollPortfolioStrategyLongTighterInitialStop.parameters,
        "disable_long_risk_cluster_heat_deleverage",
    ]

    def _process_risk_cluster_heat_deleverage(self, state: Any, bar: Any) -> str:
        direction_text = str(getattr(state, "direction", "") or "").lower()
        if bool(self.disable_long_risk_cluster_heat_deleverage) and (
            direction_text == "long" or direction_text.endswith(".long")
        ):
            return ""
        return super()._process_risk_cluster_heat_deleverage(state, bar)


def _json_safe(value: Any) -> Any:
    return s650._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s650._md_table(frame, max_rows=max_rows)


def _year_start_text(start: pd.Timestamp) -> str:
    return pd.Timestamp(start).strftime("%Y-%m")


def _profile(metadata: dict[str, Any], start: pd.Timestamp) -> dict[str, Any]:
    base = s804._profile(metadata, start)
    spec = base["spec"]
    start_text = _year_start_text(start)
    capital = replace(
        spec.capital,
        variant=f"{VARIANT}_{start_text.replace('-', '_')}",
        label=f"{LABEL} {start_text}",
        note=(
            f"{spec.capital.note} | Stage806 yearly validation. Keeps Stage804 long tighter initial stop, "
            "but disables risk-cluster heat deleverage for long positions only."
        ),
    )
    overrides = {
        **spec.overrides,
        "long_tighter_initial_stop": True,
        "disable_long_risk_cluster_heat_deleverage": True,
    }
    candidate = dict(base)
    candidate["profile"] = "stage806_stage804_no_long_heat_deleverage"
    candidate["strategy_cls"] = QmtRollPortfolioStrategyLongTighterNoLongHeatDeleverage
    candidate["spec"] = replace(spec, capital=capital, overrides=overrides, profile=candidate["profile"])
    candidate["note"] = (
        "Stage804 with long-side risk_cluster_heat_deleverage disabled; short heat deleverage and all "
        "AM41/OI/AI/risk settings unchanged."
    )
    return candidate


def _metric_from_combined(
    profile: dict[str, Any],
    combined: pd.DataFrame,
    start: pd.Timestamp,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    return s804._metric_from_combined(profile, combined, start)


def _run_one(start_text: str) -> tuple[dict[str, Any], pd.DataFrame, pd.DataFrame]:
    start = pd.Timestamp(start_text).normalize()
    metadata = s513._metadata()
    profile = _profile(metadata, start)
    base_c3_overrides = dict(s513._c3_overrides(pd.Timestamp("2018-01-01").to_pydatetime()))
    combined, frames = s778._run_profile(
        profile=profile,
        start=start,
        metadata=metadata,
        base_c3_overrides=base_c3_overrides,
    )
    summary, curve = _metric_from_combined(profile, combined, start)
    trade_events = frames.get("trade_events", pd.DataFrame()).copy()
    if trade_events.empty or "reason" not in trade_events.columns:
        adjustments = pd.DataFrame()
        long_heat_exit_count = 0
        short_heat_exit_count = 0
    else:
        reason = trade_events["reason"].astype(str)
        offset = trade_events.get("offset", pd.Series("", index=trade_events.index)).astype(str)
        adjustments = trade_events[reason.eq("long_tighter_initial_stop_adjust")].copy()
        long_heat_exit_count = int((reason.eq("long_risk_cluster_heat_deleverage") & offset.eq("Close")).sum())
        short_heat_exit_count = int((reason.eq("short_risk_cluster_heat_deleverage") & offset.eq("Close")).sum())
    adjustments["requested_start_month"] = _year_start_text(start)
    adjustments["start_month"] = _year_start_text(start)
    row = summary.iloc[0].to_dict()
    row["long_tighter_stop_adjust_count"] = int(len(adjustments))
    row["long_heat_deleverage_exit_count"] = long_heat_exit_count
    row["short_heat_deleverage_exit_count"] = short_heat_exit_count
    if not adjustments.empty:
        row["median_new_stop_distance_pct"] = float(
            pd.to_numeric(adjustments["new_stop_distance_pct"], errors="coerce").median() * 100
        )
        row["median_old_stop_distance_pct"] = float(
            pd.to_numeric(adjustments["old_stop_distance_pct"], errors="coerce").median() * 100
        )
    else:
        row["median_new_stop_distance_pct"] = np.nan
        row["median_old_stop_distance_pct"] = np.nan
    return row, curve, adjustments


def _load_stage804_yearly() -> tuple[pd.DataFrame, pd.DataFrame]:
    summary = pd.read_csv(s804.SUMMARY_PATH)
    summary["start_month"] = summary["start_month"].astype(str)
    curves = pd.read_csv(s804.CURVES_PATH, parse_dates=["date"])
    curves["start_month"] = curves["start_month"].astype(str)
    return (
        summary.sort_values("start_month").reset_index(drop=True),
        curves.sort_values(["start_month", "date"]).reset_index(drop=True),
    )


def _comparison(candidate: pd.DataFrame, base: pd.DataFrame) -> pd.DataFrame:
    comparison = s800._comparison(candidate, base)
    adjust_map = (
        candidate.set_index("start_month")["long_tighter_stop_adjust_count"].to_dict()
        if "long_tighter_stop_adjust_count" in candidate.columns
        else {}
    )
    long_heat_map = (
        candidate.set_index("start_month")["long_heat_deleverage_exit_count"].to_dict()
        if "long_heat_deleverage_exit_count" in candidate.columns
        else {}
    )
    short_heat_map = (
        candidate.set_index("start_month")["short_heat_deleverage_exit_count"].to_dict()
        if "short_heat_deleverage_exit_count" in candidate.columns
        else {}
    )
    comparison["long_tighter_stop_adjust_count"] = (
        comparison["start_month"].map(adjust_map).fillna(0).astype(int)
    )
    comparison["long_heat_deleverage_exit_count"] = (
        comparison["start_month"].map(long_heat_map).fillna(0).astype(int)
    )
    comparison["short_heat_deleverage_exit_count"] = (
        comparison["start_month"].map(short_heat_map).fillna(0).astype(int)
    )
    return comparison


def _aggregate(comparison: pd.DataFrame) -> pd.DataFrame:
    frame = comparison.copy()
    frame["lower_high_block_count"] = frame.get("long_tighter_stop_adjust_count", 0)
    agg = s800._aggregate(frame)
    agg.rename(columns={"total_blocked_long_signals": "total_long_tighter_stop_adjustments"}, inplace=True)
    agg["total_long_heat_deleverage_exits"] = int(frame.get("long_heat_deleverage_exit_count", 0).sum())
    agg["total_short_heat_deleverage_exits"] = int(frame.get("short_heat_deleverage_exit_count", 0).sum())
    return agg


def _plot_delta_bars(comparison: pd.DataFrame) -> None:
    frame = comparison.copy()
    x = np.arange(len(frame))

    fig, ax = plt.subplots(figsize=(13, 5))
    colors = np.where(frame["total_return_pct_delta"].ge(0), "#16a34a", "#dc2626")
    ax.bar(x, frame["total_return_pct_delta"], color=colors, alpha=0.82)
    ax.axhline(0, color="#111827", linewidth=1)
    ax.set_xticks(x)
    ax.set_xticklabels(frame["start_month"], rotation=30, ha="right")
    ax.set_title("Stage806 yearly starts: return delta vs Stage804")
    ax.set_ylabel("Return delta (pp)")
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(RETURN_BAR_PATH, dpi=180)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(13, 5))
    colors = np.where(frame["max_dd_pct_delta"].ge(0), "#16a34a", "#dc2626")
    ax.bar(x, frame["max_dd_pct_delta"], color=colors, alpha=0.82)
    ax.axhline(0, color="#111827", linewidth=1)
    ax.set_xticks(x)
    ax.set_xticklabels(frame["start_month"], rotation=30, ha="right")
    ax.set_title("Stage806 yearly starts: max drawdown delta vs Stage804")
    ax.set_ylabel("Max DD delta (pp, higher is better)")
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(DD_BAR_PATH, dpi=180)
    plt.close(fig)


def _plot_equity_curves(
    base_curves: pd.DataFrame,
    stage804_curves: pd.DataFrame,
    candidate_curves: pd.DataFrame,
) -> None:
    fig, axes = plt.subplots(3, 3, figsize=(18, 12), sharex=False)
    axes = axes.ravel()
    starts = sorted(candidate_curves["start_month"].dropna().astype(str).unique())
    for ax, start_month in zip(axes, starts, strict=False):
        base = base_curves[base_curves["start_month"].astype(str).eq(start_month)].copy()
        stage804 = stage804_curves[stage804_curves["start_month"].astype(str).eq(start_month)].copy()
        cand = candidate_curves[candidate_curves["start_month"].astype(str).eq(start_month)].copy()
        if not base.empty:
            ax.plot(base["date"], base["rebased_equity"] / 1_000_000, label="A Stage777", linewidth=1.1)
        if not stage804.empty:
            ax.plot(stage804["date"], stage804["rebased_equity"] / 1_000_000, label="B Stage804", linewidth=1.1)
        if not cand.empty:
            ax.plot(cand["date"], cand["rebased_equity"] / 1_000_000, label="C Stage806", linewidth=1.2)
        ax.axhline(0.5, color="#9aa3af", linestyle="--", linewidth=0.8)
        ax.set_title(start_month)
        ax.grid(alpha=0.22)
        ax.tick_params(axis="x", labelrotation=25, labelsize=8)
        ax.tick_params(axis="y", labelsize=8)
    for ax in axes[len(starts) :]:
        ax.axis("off")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=3)
    fig.suptitle("Stage806 yearly equity curves: Stage777 vs Stage804 vs no-long-heat-deleverage", y=0.995)
    fig.tight_layout(rect=[0, 0, 1, 0.965])
    fig.savefig(EQUITY_CURVES_PATH, dpi=170)
    plt.close(fig)


def _window_pnl(curves: pd.DataFrame, arm: str) -> pd.DataFrame:
    window_start = pd.Timestamp("2025-06-16")
    window_end = pd.Timestamp("2025-07-25")
    rows: list[dict[str, Any]] = []
    frame = curves.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame["start_month"] = frame["start_month"].astype(str)
    for start_month, group in frame.groupby("start_month", sort=True):
        win = group[(group["date"] >= window_start) & (group["date"] <= window_end)].copy()
        if win.empty:
            continue
        equity = pd.to_numeric(win["rebased_equity"], errors="coerce")
        pnl = float(equity.iloc[-1] - equity.iloc[0])
        rows.append(
            {
                "arm": arm,
                "start_month": start_month,
                "window_start": str(window_start.date()),
                "window_end": str(window_end.date()),
                "window_start_equity": float(equity.iloc[0]),
                "window_end_equity": float(equity.iloc[-1]),
                "window_pnl": pnl,
                "window_return_pct": pnl / float(equity.iloc[0]) * 100 if float(equity.iloc[0]) else np.nan,
            }
        )
    return pd.DataFrame(rows)


def _write_report(
    comparison_stage804: pd.DataFrame,
    comparison_stage777: pd.DataFrame,
    aggregate_stage804: pd.DataFrame,
    aggregate_stage777: pd.DataFrame,
    window: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    lines = [
        "# Stage806 Stage804关闭多头risk_cluster_heat_deleverage 年度起点回测",
        "",
        f"- line_id：`{LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        "- A：`official_candidate_stage777_50w_am41_oi08_old_ai_v1` 年度起点缓存。",
        "- B：Stage804，即 A + 多头更紧初始止损。",
        "- C：Stage806，即 B + 只关闭 `long_risk_cluster_heat_deleverage`；空头热度去杠杆保留。",
        "- 保持不变：50万、AM41、基础风险 `0.40`、OI命中恢复 `0.80`、旧正式AI池、maxpos4、关闭连败缩放和 recovery sleeve。",
        "",
        "## Aggregate vs Stage804",
        "",
        _md_table(aggregate_stage804, max_rows=10),
        "",
        "## Aggregate vs Stage777",
        "",
        _md_table(aggregate_stage777, max_rows=10),
        "",
        "## Yearly Comparison vs Stage804",
        "",
        _md_table(
            comparison_stage804[
                [
                    "start_month",
                    "total_return_pct_base",
                    "total_return_pct_candidate",
                    "total_return_pct_delta",
                    "max_dd_pct_base",
                    "max_dd_pct_candidate",
                    "max_dd_pct_delta",
                    "sharpe_base",
                    "sharpe_candidate",
                    "sharpe_delta",
                    "total_trade_count_base",
                    "total_trade_count_candidate",
                    "long_heat_deleverage_exit_count",
                    "short_heat_deleverage_exit_count",
                ]
            ],
            max_rows=20,
        ),
        "",
        "## 2025-06-16 to 2025-07-25 Window",
        "",
        _md_table(window, max_rows=40),
        "",
        "## Decision",
        "",
        f"- 决策：`{decision['decision']}`",
        f"- 判断：{decision['judgment']}",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    base_summary, base_curves = s800._load_base_yearly()
    stage804_summary, stage804_curves = _load_stage804_yearly()
    tasks = [start.strftime("%Y-%m-%d") for start in YEAR_STARTS]
    rows: list[dict[str, Any]] = []
    curves: list[pd.DataFrame] = []
    adjustments: list[pd.DataFrame] = []

    print(f"[stage806] launching {len(tasks)} yearly runs workers={MAX_WORKERS}", flush=True)
    if MAX_WORKERS == 1:
        for idx, task in enumerate(tasks, start=1):
            print(f"[stage806] running {idx}/{len(tasks)} {task}", flush=True)
            row, curve, adjustment = _run_one(task)
            rows.append(row)
            curves.append(curve)
            adjustments.append(adjustment)
    else:
        with ProcessPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_map = {executor.submit(_run_one, task): task for task in tasks}
            for idx, future in enumerate(as_completed(future_map), start=1):
                task = future_map[future]
                row, curve, adjustment = future.result()
                rows.append(row)
                curves.append(curve)
                adjustments.append(adjustment)
                print(f"[stage806] completed {idx}/{len(tasks)} {task}", flush=True)

    candidate_summary = s772._add_month_fields(pd.DataFrame(rows)).sort_values("start_month").reset_index(drop=True)
    candidate_curves = (
        pd.concat(curves, ignore_index=True, sort=False).sort_values(["start_month", "date"]).reset_index(drop=True)
    )
    stop_adjustments = (
        pd.concat(adjustments, ignore_index=True, sort=False)
        if adjustments
        else pd.DataFrame(columns=["start_month", "reason"])
    )
    comparison_stage804 = _comparison(candidate_summary, stage804_summary).sort_values("start_month").reset_index(drop=True)
    comparison_stage777 = _comparison(candidate_summary, base_summary).sort_values("start_month").reset_index(drop=True)
    aggregate_stage804 = _aggregate(comparison_stage804)
    aggregate_stage777 = _aggregate(comparison_stage777)
    window = pd.concat(
        [
            _window_pnl(base_curves, "A Stage777"),
            _window_pnl(stage804_curves, "B Stage804"),
            _window_pnl(candidate_curves, "C Stage806"),
        ],
        ignore_index=True,
        sort=False,
    ).sort_values(["start_month", "arm"])

    candidate_summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    candidate_curves.to_csv(CURVES_PATH, index=False, encoding="utf-8-sig")
    stop_adjustments.to_csv(ADJUSTMENTS_PATH, index=False, encoding="utf-8-sig")
    comparison_stage804.to_csv(COMPARISON_STAGE804_PATH, index=False, encoding="utf-8-sig")
    comparison_stage777.to_csv(COMPARISON_STAGE777_PATH, index=False, encoding="utf-8-sig")
    aggregate_stage804.to_csv(AGG_STAGE804_PATH, index=False, encoding="utf-8-sig")
    aggregate_stage777.to_csv(AGG_STAGE777_PATH, index=False, encoding="utf-8-sig")
    window.to_csv(WINDOW_PATH, index=False, encoding="utf-8-sig")
    _plot_delta_bars(comparison_stage804)
    _plot_equity_curves(base_curves, stage804_curves, candidate_curves)

    mature804 = aggregate_stage804[aggregate_stage804["bucket"].eq("mature_ex_2026")].iloc[0].to_dict()
    mature777 = aggregate_stage777[aggregate_stage777["bucket"].eq("mature_ex_2026")].iloc[0].to_dict()
    all804 = aggregate_stage804[aggregate_stage804["bucket"].eq("all")].iloc[0].to_dict()
    decision_label = (
        "stage806_no_long_heat_deleverage_yearly_watch"
        if int(mature804["candidate_return_win_count"]) >= 5
        and int(mature804["candidate_dd50_fail_count"]) <= int(mature804["base_dd50_fail_count"]) + 1
        and float(mature804["median_return_delta_pp"]) >= 0
        else "stage806_no_long_heat_deleverage_yearly_not_promoted"
    )
    decision = {
        "stage": "Stage806",
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "base": "Stage804 yearly starts and Stage777 official candidate cache",
        "candidate": "Stage804 + disable long risk_cluster_heat_deleverage",
        "change": {
            "disable_long_risk_cluster_heat_deleverage": True,
            "short_risk_cluster_heat_deleverage": "unchanged",
            "long_tighter_initial_stop": True,
        },
        "decision": decision_label,
        "judgment": (
            "This tests whether Stage804's missed right-tail is caused by a structural coupling between tighter long "
            "risk sizing and long-side cluster heat deleverage. It should not be promoted if drawdown failures expand "
            "materially even when returns improve."
        ),
        "aggregate_vs_stage804_all": all804,
        "aggregate_vs_stage804_mature_ex_2026": mature804,
        "aggregate_vs_stage777_mature_ex_2026": mature777,
        "outputs": {
            "summary": str(SUMMARY_PATH),
            "curves": str(CURVES_PATH),
            "stop_adjustments": str(ADJUSTMENTS_PATH),
            "comparison_vs_stage804": str(COMPARISON_STAGE804_PATH),
            "comparison_vs_stage777": str(COMPARISON_STAGE777_PATH),
            "aggregate_vs_stage804": str(AGG_STAGE804_PATH),
            "aggregate_vs_stage777": str(AGG_STAGE777_PATH),
            "window": str(WINDOW_PATH),
            "return_bar": str(RETURN_BAR_PATH),
            "dd_bar": str(DD_BAR_PATH),
            "equity_curves": str(EQUITY_CURVES_PATH),
            "report": str(REPORT_PATH),
        },
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_report(
        comparison_stage804=comparison_stage804,
        comparison_stage777=comparison_stage777,
        aggregate_stage804=aggregate_stage804,
        aggregate_stage777=aggregate_stage777,
        window=window,
        decision=decision,
    )
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print("aggregate_vs_stage804")
    print(aggregate_stage804.to_string(index=False))
    print("aggregate_vs_stage777")
    print(aggregate_stage777.to_string(index=False))
    print("comparison_vs_stage804")
    print(
        comparison_stage804[
            [
                "start_month",
                "total_return_pct_base",
                "total_return_pct_candidate",
                "total_return_pct_delta",
                "max_dd_pct_base",
                "max_dd_pct_candidate",
                "max_dd_pct_delta",
                "sharpe_base",
                "sharpe_candidate",
                "sharpe_delta",
                "total_trade_count_base",
                "total_trade_count_candidate",
                "long_heat_deleverage_exit_count",
                "short_heat_deleverage_exit_count",
            ]
        ].to_string(index=False)
    )


if __name__ == "__main__":
    main()
