from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime
import json
import os
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm
import numpy as np
import pandas as pd

import analyze_qmt_roll_stage513_stage208_exact_position_margin_audit as s513
import analyze_qmt_roll_stage650_stage526_200k_capital_reality_check as s650
import analyze_qmt_roll_stage772_am40_80_120_oi_monthly as s772


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

MODEL_TAG = "stage777_am41_oi08_monthly_v1"
OUTPUT_PREFIX = "qmt_roll_stage777_am41_oi08_monthly"
LINE_ID = "futures_trend_2019_data_extension"

ANALYSIS_END = pd.Timestamp("2026-05-29")
MONTH_STARTS = tuple(pd.date_range("2018-01-01", "2026-05-01", freq="MS"))
MAX_WORKERS = max(1, min(6, int(os.environ.get("STAGE777_MAX_WORKERS", "6"))))

CANDIDATE_VARIANT = "stage777_500k_am41_oi_confirm_r080_monthly"
CANDIDATE_LABEL = "Stage777 AM41 OI confirm restores 0.80 risk"

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
COST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cost_stress_{MODEL_TAG}.csv"
CURVES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv"
PROFILE_AGG_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_profile_aggregate_{MODEL_TAG}.csv"
PHASE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_phase_summary_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
RETURN_HEATMAP_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_return_heatmap_{MODEL_TAG}.png"
DD_HEATMAP_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_dd_heatmap_{MODEL_TAG}.png"
EQUITY_CURVES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_equity_curves_selected_{MODEL_TAG}.png"


def _json_safe(value: Any) -> Any:
    return s650._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s650._md_table(frame, max_rows=max_rows)


def _rewrite_outputs(row: dict[str, Any], costs: list[dict[str, Any]], curve: pd.DataFrame) -> tuple[dict[str, Any], list[dict[str, Any]], pd.DataFrame]:
    row = dict(row)
    row.update(
        {
            "variant": CANDIDATE_VARIANT,
            "label": CANDIDATE_LABEL,
            "profile": "stage777_am41_oi08",
            "source_name": "stage777_am41_oi08_monthly",
            "oi_mode": "oi_restore",
            "am_label": "am40",
            "declared_am_size": 41,
            "note": "Post-rollover-fix monthly starts for AM41 with OI price confirmation restoring effective risk from 0.40 to 0.80.",
        }
    )
    for cost in costs:
        cost.update(
            {
                "variant": CANDIDATE_VARIANT,
                "label": CANDIDATE_LABEL,
                "profile": "stage777_am41_oi08",
                "source_name": "stage777_am41_oi08_monthly",
                "oi_mode": "oi_restore",
                "am_label": "am40",
                "declared_am_size": 41,
            }
        )
    frame = curve.copy()
    frame["variant"] = CANDIDATE_VARIANT
    frame["label"] = CANDIDATE_LABEL
    frame["profile"] = "stage777_am41_oi08"
    frame["source_name"] = "stage777_am41_oi08_monthly"
    frame["oi_mode"] = "oi_restore"
    frame["am_label"] = "am40"
    frame["declared_am_size"] = 41
    return row, costs, frame


def _run_one(task: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]], pd.DataFrame]:
    try:
        row, costs, curve = s772._run_one(task)
    except RuntimeError as exc:
        if "empty daily result" not in str(exc):
            raise
        return _flat_no_trade_result(task)
    return _rewrite_outputs(row, costs, curve)


def _flat_no_trade_result(task: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]], pd.DataFrame]:
    start = pd.Timestamp(task["start"]).normalize()
    capital = 500_000.0
    row: dict[str, Any] = {
        "variant": CANDIDATE_VARIANT,
        "label": CANDIDATE_LABEL,
        "profile": "stage777_am41_oi08",
        "window_name": s772._window_name(start),
        "window_label": s772._window_label(start),
        "window_group": "monthly_start",
        "analysis_start": start.date().isoformat(),
        "analysis_end": ANALYSIS_END.date().isoformat(),
        "account_capital": capital,
        "c3_capital": capital,
        "risk_multiplier": 0.40,
        "trading_days": 0,
        "end_equity": capital,
        "total_return_pct": 0.0,
        "cagr_pct": 0.0,
        "max_dd_pct": 0.0,
        "ulcer_pct": 0.0,
        "sharpe": 0.0,
        "min_equity": capital,
        "max_broker10_margin_to_equity_pct": 0.0,
        "p95_broker10_margin_to_equity_pct": 0.0,
        "days_over_100pct": 0,
        "days_over_90pct": 0,
        "days_equity_below_zero": 0,
        "total_slippage": 0.0,
        "total_trade_count": 0.0,
        "nonzero_daily_win_rate_pct": 0.0,
        "forced_margin_deleverage_count": 0,
        "forced_margin_deleverage_closed_volume": 0.0,
        "dd30_pass": 1,
        "dd40_pass": 1,
        "broker10_100_pass": 1,
        "account_survival_pass": 1,
        "deployable_pass": 1,
        "source_name": "stage777_am41_oi08_monthly",
        "rebased_end_equity": capital,
        "rebased_total_return_pct": 0.0,
        "rebased_cagr_pct": 0.0,
        "rebased_max_dd_pct": 0.0,
        "rebased_sharpe": 0.0,
        "rebased_min_equity": capital,
        "max_broker10_margin_to_rebased_equity_pct": 0.0,
        "p95_broker10_margin_to_rebased_equity_pct": 0.0,
        "nav_end": 1.0,
        "oi_mode": "oi_restore",
        "am_label": "am40",
        "declared_am_size": 41,
        "note": "No daily result/no trade short window; treated as flat capital for monthly-start audit.",
        "requested_start_month": start.strftime("%Y-%m"),
        "start_month": start.strftime("%Y-%m"),
    }
    costs: list[dict[str, Any]] = []
    for multiplier in (1.0, 2.0, 3.0):
        costs.append(
            {
                "variant": CANDIDATE_VARIANT,
                "label": CANDIDATE_LABEL,
                "window_name": s772._window_name(start),
                "cost_multiplier": multiplier,
                "account_capital": capital,
                "end_equity": capital,
                "total_return_pct": 0.0,
                "max_dd_pct": 0.0,
                "sharpe": 0.0,
                "max_broker10_margin_to_equity_pct": 0.0,
                "days_over_100pct": 0,
                "account_survival_pass": 1,
                "deployable_pass": 1,
                "source_name": "stage777_am41_oi08_monthly",
                "profile": "stage777_am41_oi08",
                "oi_mode": "oi_restore",
                "am_label": "am40",
                "declared_am_size": 41,
                "requested_start_month": start.strftime("%Y-%m"),
                "start_month": start.strftime("%Y-%m"),
            }
        )
    curve = pd.DataFrame(
        [
            {
                "date": start,
                "variant": CANDIDATE_VARIANT,
                "label": CANDIDATE_LABEL,
                "window_name": s772._window_name(start),
                "window_label": s772._window_label(start),
                "window_group": "monthly_start",
                "account_capital": capital,
                "account_equity": capital,
                "nav": 1.0,
                "drawdown_pct": 0.0,
                "broker10_margin_to_equity_pct": 0.0,
                "net_pnl": 0.0,
                "trade_count": 0,
                "total_slippage": 0.0,
                "source_name": "stage777_am41_oi08_monthly",
                "rebased_equity": capital,
                "rebased_nav": 1.0,
                "broker10_margin_to_rebased_equity_pct": 0.0,
                "profile": "stage777_am41_oi08",
                "oi_mode": "oi_restore",
                "am_label": "am40",
                "declared_am_size": 41,
                "requested_start_month": start.strftime("%Y-%m"),
                "start_month": start.strftime("%Y-%m"),
            }
        ]
    )
    return row, costs, curve


def _run_all() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    metadata = s513._metadata()
    base_c3_overrides = dict(s513._c3_overrides(MONTH_STARTS[0].to_pydatetime()))
    tasks = [
        {
            "profile": "oi_restore_am40",
            "start": start.strftime("%Y-%m-%d"),
            "base_c3_overrides": base_c3_overrides,
        }
        for start in MONTH_STARTS
    ]
    # Force metadata load before worker fork so missing data errors surface early.
    if not metadata:
        raise RuntimeError("empty metadata")

    rows: list[dict[str, Any]] = []
    cost_rows: list[dict[str, Any]] = []
    curves: list[pd.DataFrame] = []
    print(f"[stage777] launching {len(tasks)} monthly runs workers={MAX_WORKERS}", flush=True)
    if MAX_WORKERS == 1:
        for idx, task in enumerate(tasks, start=1):
            print(f"[stage777] running {idx}/{len(tasks)} {task['start']}", flush=True)
            row, costs, curve = _run_one(task)
            rows.append(row)
            cost_rows.extend(costs)
            curves.append(curve)
    else:
        with ProcessPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_map = {executor.submit(_run_one, task): task for task in tasks}
            for idx, future in enumerate(as_completed(future_map), start=1):
                task = future_map[future]
                row, costs, curve = future.result()
                rows.append(row)
                cost_rows.extend(costs)
                curves.append(curve)
                print(f"[stage777] completed {idx}/{len(tasks)} {task['start']}", flush=True)

    summary = (
        s772._add_month_fields(pd.DataFrame(rows))
        .sort_values("start_month")
        .reset_index(drop=True)
    )
    cost = (
        pd.DataFrame(cost_rows)
        .sort_values(["start_month", "cost_multiplier"])
        .reset_index(drop=True)
    )
    curves_all = (
        pd.concat(curves, ignore_index=True, sort=False)
        .sort_values(["start_month", "date"])
        .reset_index(drop=True)
    )
    return summary, cost, curves_all


def _profile_aggregate(summary: pd.DataFrame, cost: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for bucket, frame in [
        ("all", summary),
        ("mature_63d", summary[summary["mature_63d"].eq(1)]),
        ("mature_126d", summary[summary["mature_126d"].eq(1)]),
        ("mature_252d", summary[summary["mature_252d"].eq(1)]),
    ]:
        returns = pd.to_numeric(frame["rebased_total_return_pct"], errors="coerce")
        dds = pd.to_numeric(frame["rebased_max_dd_pct"], errors="coerce")
        sharpes = pd.to_numeric(frame["rebased_sharpe"], errors="coerce")
        rows.append(
            {
                "profile": "stage777_am41_oi08",
                "bucket": bucket,
                "start_count": int(len(frame)),
                "positive_count": int(frame["positive_return"].sum()) if len(frame) else 0,
                "positive_rate_pct": float(frame["positive_return"].mean() * 100.0) if len(frame) else 0.0,
                "median_return_pct": float(returns.median()) if len(frame) else 0.0,
                "p10_return_pct": float(returns.quantile(0.10)) if len(frame) else 0.0,
                "min_return_pct": float(returns.min()) if len(frame) else 0.0,
                "median_dd_pct": float(dds.median()) if len(frame) else 0.0,
                "worst_dd_pct": float(dds.min()) if len(frame) else 0.0,
                "dd30_fail_count": int((dds < -30.0).sum()) if len(frame) else 0,
                "dd40_fail_count": int(frame["dd40_fail"].sum()) if len(frame) else 0,
                "dd50_fail_count": int(frame["dd50_fail"].sum()) if len(frame) else 0,
                "median_sharpe": float(sharpes.median()) if len(frame) else 0.0,
                "trade_count_median": float(pd.to_numeric(frame["total_trade_count"], errors="coerce").median()) if len(frame) else 0.0,
                "trade_count_sum": float(pd.to_numeric(frame["total_trade_count"], errors="coerce").sum()) if len(frame) else 0.0,
            }
        )

    cost_view = cost[cost["cost_multiplier"].isin([2.0, 3.0])].copy()
    if not cost_view.empty:
        cost_view["dd40_fail"] = (pd.to_numeric(cost_view["max_dd_pct"], errors="coerce") < -40.0).astype(int)
        for multiplier, frame in cost_view.groupby("cost_multiplier", sort=True):
            rows.append(
                {
                    "profile": "stage777_am41_oi08",
                    "bucket": f"cost_{multiplier}x_all",
                    "start_count": int(summary.shape[0]),
                    "median_return_pct": float(pd.to_numeric(frame["total_return_pct"], errors="coerce").median()),
                    "dd40_fail_count": int(frame["dd40_fail"].sum()),
                }
            )
    return pd.DataFrame(rows)


def _phase_summary(summary: pd.DataFrame) -> pd.DataFrame:
    frame = summary.copy()
    frame["start_phase"] = pd.cut(
        pd.to_numeric(frame["start_year"], errors="coerce"),
        bins=[2017, 2019, 2021, 2023, 2025, 2026],
        labels=["2018-2019", "2020-2021", "2022-2023", "2024-2025", "2026"],
        include_lowest=True,
    ).astype(str)
    rows: list[dict[str, Any]] = []
    for phase, group in frame.groupby("start_phase", sort=True):
        rows.append(
            {
                "start_phase": phase,
                "start_count": int(len(group)),
                "mature_252d_count": int(group["mature_252d"].sum()),
                "positive_count": int(group["positive_return"].sum()),
                "median_return_pct": float(pd.to_numeric(group["rebased_total_return_pct"], errors="coerce").median()),
                "p10_return_pct": float(pd.to_numeric(group["rebased_total_return_pct"], errors="coerce").quantile(0.10)),
                "min_return_pct": float(pd.to_numeric(group["rebased_total_return_pct"], errors="coerce").min()),
                "median_dd_pct": float(pd.to_numeric(group["rebased_max_dd_pct"], errors="coerce").median()),
                "worst_dd_pct": float(pd.to_numeric(group["rebased_max_dd_pct"], errors="coerce").min()),
                "dd40_fail_count": int(group["dd40_fail"].sum()),
            }
        )
    return pd.DataFrame(rows)


def _plot_heatmap(summary: pd.DataFrame, value_column: str, path: Path, title: str, cmap: str, vcenter: float) -> None:
    pivot = summary.pivot_table(index="start_year", columns="start_month_num", values=value_column, aggfunc="first")
    values = pd.to_numeric(summary[value_column], errors="coerce")
    if value_column == "rebased_total_return_pct":
        vmin, vmax = -100.0, max(400.0, float(np.nanpercentile(values, 90)))
    else:
        vmin, vmax = float(np.nanpercentile(values, 5)), float(np.nanpercentile(values, 95))
    norm = TwoSlopeNorm(vcenter=vcenter, vmin=min(vmin, vcenter - 1e-6), vmax=max(vmax, vcenter + 1e-6))
    fig, ax = plt.subplots(figsize=(16, 6.8))
    im = ax.imshow(pivot.to_numpy(dtype=float), aspect="auto", cmap=cmap, norm=norm)
    ax.set_title(title)
    ax.set_xlabel("Start month")
    ax.set_ylabel("Start year")
    ax.set_xticks(range(12))
    ax.set_xticklabels(range(1, 13))
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels([str(int(item)) for item in pivot.index])
    for i, year in enumerate(pivot.index):
        for j, month in enumerate(pivot.columns):
            value = pivot.loc[year, month]
            if pd.notna(value):
                ax.text(j, i, f"{value:.0f}", ha="center", va="center", fontsize=8, color="#111827")
    fig.colorbar(im, ax=ax, shrink=0.85)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def _plot_selected_equity_curves(curves: pd.DataFrame, summary: pd.DataFrame) -> None:
    selected = set()
    for month in ["2018-01", "2019-01", "2020-01", "2021-01", "2022-01", "2023-01", "2024-01", "2025-01", "2026-01"]:
        selected.add(month)
    for _, row in summary.nsmallest(3, "rebased_total_return_pct").iterrows():
        selected.add(str(row["start_month"]))
    for _, row in summary.nlargest(3, "rebased_total_return_pct").iterrows():
        selected.add(str(row["start_month"]))
    data = curves[curves["start_month"].astype(str).isin(sorted(selected))].copy()
    fig, ax = plt.subplots(figsize=(16, 8))
    colors = plt.cm.tab20.colors
    for idx, (start_month, group) in enumerate(data.groupby("start_month", sort=True)):
        group = group.sort_values("date")
        ax.plot(
            pd.to_datetime(group["date"]),
            pd.to_numeric(group["account_equity"], errors="coerce") / 1_000_000,
            label=start_month,
            color=colors[idx % len(colors)],
            linewidth=1.6,
            alpha=0.9,
        )
    ax.axhline(0.5, color="#9ca3af", linestyle="--", linewidth=1)
    ax.set_title("Stage777 selected monthly-start equity curves")
    ax.set_xlabel("Date")
    ax.set_ylabel("Account equity")
    ax.yaxis.set_major_formatter(lambda x, pos: f"{x:.1f}M")
    ax.grid(alpha=0.25)
    ax.legend(ncol=4, fontsize=8)
    fig.tight_layout()
    fig.savefig(EQUITY_CURVES_PATH, dpi=180)
    plt.close(fig)


def _build_decision(profile_agg: pd.DataFrame, phase: pd.DataFrame) -> dict[str, Any]:
    mature = profile_agg[profile_agg["bucket"].eq("mature_252d")].iloc[0]
    hard_fail: list[str] = []
    watch: list[str] = []
    if int(mature["dd40_fail_count"]) > 0:
        hard_fail.append("mature_dd40_fail_exists")
    if float(mature["positive_rate_pct"]) < 100.0:
        hard_fail.append("mature_not_all_positive")
    if float(mature["p10_return_pct"]) < 50.0:
        watch.append("mature_p10_return_below_50pct")
    if float(mature["worst_dd_pct"]) < -45.0:
        hard_fail.append("mature_worst_dd_below_45")
    decision = "am41_oi08_monthly_not_promoted" if hard_fail else "am41_oi08_monthly_candidate_watch"
    return {
        "stage": "Stage777",
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "decision": decision,
        "hard_fail_checks": hard_fail,
        "watch_checks": watch,
        "analysis_start_first": MONTH_STARTS[0].date().isoformat(),
        "analysis_start_last": MONTH_STARTS[-1].date().isoformat(),
        "analysis_end": ANALYSIS_END.date().isoformat(),
        "monthly_start_count": len(MONTH_STARTS),
        "change": {
            "official_config_changed": False,
            "ctp_connected": False,
            "order_api_called": False,
            "am_gate": "research_exact_am41",
            "base_effective_risk_multiplier": 0.40,
            "oi_hit_effective_risk_multiplier": 0.80,
            "streak_risk_multipliers": "1.0,1.0,1.0,1.0",
            "enable_recovery_sleeve": False,
            "causal_timing": "latest_completed_daily_bar",
        },
        "profile_aggregate": profile_agg.to_dict("records"),
        "phase_summary": phase.to_dict("records"),
        "outputs": {
            "summary": str(SUMMARY_PATH),
            "cost": str(COST_PATH),
            "curves": str(CURVES_PATH),
            "profile_aggregate": str(PROFILE_AGG_PATH),
            "phase": str(PHASE_PATH),
            "return_heatmap": str(RETURN_HEATMAP_PATH),
            "dd_heatmap": str(DD_HEATMAP_PATH),
            "equity_curves": str(EQUITY_CURVES_PATH),
            "report": str(REPORT_PATH),
        },
        "overfit_judgment": (
            "medium: OI confirmation is a plausible trend-confirmation feature, but prior yearly tests show "
            "right-tail amplification and drawdown pressure; monthly starts are required before any promotion."
        ),
        "continue_value": (
            "yes for validation; no decimal scanning unless monthly starts improve both return and drawdown."
        ),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }


def _write_report(profile_agg: pd.DataFrame, phase: pd.DataFrame, decision: dict[str, Any]) -> None:
    lines = [
        "# Stage777 AM41 命中 OI 恢复到 0.80 逐月启动验证",
        "",
        f"- line_id：`{LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        f"- 起点：`{MONTH_STARTS[0].strftime('%Y-%m')}` 到 `{MONTH_STARTS[-1].strftime('%Y-%m')}`；终点 `{ANALYSIS_END.date()}`。",
        "- 口径：AM41 研究门槛；基础等效风险 `0.40`；命中 `OI上升 + 价格沿方向` 后恢复到 `0.80`。",
        "",
        "## Profile Aggregate",
        "",
        _md_table(profile_agg, max_rows=20),
        "",
        "## Phase Summary",
        "",
        _md_table(phase, max_rows=20),
        "",
        "## Decision",
        "",
        f"- 决策：`{decision['decision']}`",
        f"- hard_fail：`{decision['hard_fail_checks']}`",
        f"- watch：`{decision['watch_checks']}`",
        f"- 过拟合判断：{decision['overfit_judgment']}",
        f"- 继续价值：{decision['continue_value']}",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    summary, cost, curves = _run_all()
    profile_agg = _profile_aggregate(summary, cost)
    phase = _phase_summary(summary)
    decision = _build_decision(profile_agg, phase)

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    cost.to_csv(COST_PATH, index=False, encoding="utf-8-sig")
    curves.to_csv(CURVES_PATH, index=False, encoding="utf-8-sig")
    profile_agg.to_csv(PROFILE_AGG_PATH, index=False, encoding="utf-8-sig")
    phase.to_csv(PHASE_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _plot_heatmap(summary, "rebased_total_return_pct", RETURN_HEATMAP_PATH, "Stage777 AM41 OI0.8 return % by monthly start", "RdYlGn", 0.0)
    _plot_heatmap(summary, "rebased_max_dd_pct", DD_HEATMAP_PATH, "Stage777 AM41 OI0.8 max DD % by monthly start", "RdYlGn", -40.0)
    _plot_selected_equity_curves(curves, summary)
    _write_report(profile_agg, phase, decision)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
