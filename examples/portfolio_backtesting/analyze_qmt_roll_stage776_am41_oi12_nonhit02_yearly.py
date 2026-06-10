from __future__ import annotations

from dataclasses import replace
from datetime import datetime
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import analyze_qmt_roll_stage513_stage208_exact_position_margin_audit as s513
import analyze_qmt_roll_stage650_stage526_200k_capital_reality_check as s650
import analyze_qmt_roll_stage653_stage526_200k_forced_margin_deleverage as s653
import analyze_qmt_roll_stage748_half_risk_no_streak_500k as s748
import analyze_qmt_roll_stage772_am40_80_120_oi_monthly as s772


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

MODEL_TAG = "stage776_am41_oi12_nonhit02_yearly_v1"
OUTPUT_PREFIX = "qmt_roll_stage776_am41_oi12_nonhit02_yearly"
LINE_ID = "futures_trend_2019_data_extension"

ANALYSIS_END = pd.Timestamp("2026-05-29")
YEAR_STARTS = tuple(pd.date_range("2018-01-01", "2026-01-01", freq="YS"))

BASE_NONHIT_RISK = 0.20
OI_HIT_RISK = 1.20
OI_INTERNAL_MULTIPLIER = OI_HIT_RISK / BASE_NONHIT_RISK

CANDIDATE_VARIANT = "stage776_500k_am41_oi_hit_r120_nonhit_r020_no_streak"

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
COST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cost_stress_{MODEL_TAG}.csv"
CURVES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv"
PROFILE_AGG_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_profile_aggregate_{MODEL_TAG}.csv"
COMPARISON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_comparison_vs_stage775_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
RETURN_CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_return_by_start_year_{MODEL_TAG}.png"
EQUITY_CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_equity_curves_{MODEL_TAG}.png"

STAGE775_SUMMARY_PATH = (
    OUTPUT_DIR
    / "qmt_roll_stage775_am40_80_120_oi_yearly_rollover_fix_summary_stage775_am40_80_120_oi_yearly_rollover_fix_v1.csv"
)
STAGE775_CURVES_PATH = (
    OUTPUT_DIR
    / "qmt_roll_stage775_am40_80_120_oi_yearly_rollover_fix_curves_stage775_am40_80_120_oi_yearly_rollover_fix_v1.csv"
)


def _json_safe(value: Any) -> Any:
    return s650._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s650._md_table(frame, max_rows=max_rows)


def _profile_spec(metadata: dict[str, Any]) -> dict[str, Any]:
    base = s748._candidate_500k_spec(metadata)
    capital = replace(
        base.capital,
        variant=CANDIDATE_VARIANT,
        label="Stage776 AM41 OI hit 1.20 risk, non-hit 0.20 risk",
        risk_multiplier=BASE_NONHIT_RISK,
        note=(
            "Stage775 AM41 research gate with Stage748 no-streak 500k shell. "
            "Base/non-OI risk is 0.20 formal risk; if latest completed daily OI rises and price aligns "
            "with trade direction, internal risk multiplier lifts 0.20 to 1.20."
        ),
    )
    overrides = {
        **base.overrides,
        "array_manager_size_floor": 40,
        "research_exact_array_manager_size": 41,
        "enable_oi_price_confirm_risk_restore": True,
        "oi_price_confirm_risk_restore_multiplier": OI_INTERNAL_MULTIPLIER,
        "oi_price_confirm_risk_restore_entry_contexts": "flat_entry,reverse_entry,rollover_reopen",
        "oi_price_confirm_risk_restore_require_recent_sum_ratio": False,
    }
    spec = replace(base, capital=capital, overrides=overrides, profile="stage776_am41_oi12_nonhit02")
    return {
        "profile": "stage776_am41_oi12_nonhit02",
        "oi_mode": "oi_split_1p2_0p2",
        "am_label": "am40",
        "declared_am_size": 41,
        "strategy_cls": s772.QmtRollPortfolioStrategyExactAm,
        "spec": spec,
        "note": "AM41 exact research gate; OI-hit risk=1.20, non-hit risk=0.20.",
    }


def _run_one(profile: dict[str, Any], start: pd.Timestamp, metadata: dict[str, Any], base_c3_overrides: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]], pd.DataFrame]:
    frame, forced_events = s772._run_engine(
        profile=profile,
        start=start,
        metadata=metadata,
        base_c3_overrides=base_c3_overrides,
    )
    spec = profile["spec"]
    row, curve, costs = s748._metric_row(
        frame,
        spec=spec,
        window_name=f"ystart_{start.strftime('%Y')}",
        window_label=f"{start.strftime('%Y')} independent start to {ANALYSIS_END.date()}",
        window_group="yearly_start",
        forced_events=forced_events,
    )
    row = s772._metric_common(row)
    row.update(
        {
            "source_name": "stage776_am41_oi12_nonhit02_yearly",
            "profile": profile["profile"],
            "oi_mode": profile["oi_mode"],
            "am_label": profile["am_label"],
            "declared_am_size": profile["declared_am_size"],
            "note": profile["note"],
            "requested_start_month": start.strftime("%Y-%m"),
            "start_month": start.strftime("%Y-%m"),
            "nonhit_effective_risk_multiplier": BASE_NONHIT_RISK,
            "oi_hit_effective_risk_multiplier": OI_HIT_RISK,
            "oi_internal_multiplier": OI_INTERNAL_MULTIPLIER,
        }
    )

    curve = s772._curve_common(curve)
    curve["source_name"] = "stage776_am41_oi12_nonhit02_yearly"
    curve["profile"] = profile["profile"]
    curve["oi_mode"] = profile["oi_mode"]
    curve["am_label"] = profile["am_label"]
    curve["declared_am_size"] = profile["declared_am_size"]
    curve["requested_start_month"] = start.strftime("%Y-%m")
    curve["start_month"] = start.strftime("%Y-%m")
    curve["start_year"] = start.year

    for cost in costs:
        cost.update(
            {
                "source_name": "stage776_am41_oi12_nonhit02_yearly",
                "profile": profile["profile"],
                "oi_mode": profile["oi_mode"],
                "am_label": profile["am_label"],
                "declared_am_size": profile["declared_am_size"],
                "requested_start_month": start.strftime("%Y-%m"),
                "start_month": start.strftime("%Y-%m"),
                "nonhit_effective_risk_multiplier": BASE_NONHIT_RISK,
                "oi_hit_effective_risk_multiplier": OI_HIT_RISK,
                "oi_internal_multiplier": OI_INTERNAL_MULTIPLIER,
            }
        )
    return row, costs, curve


def _run_all() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    metadata = s513._metadata()
    profile = _profile_spec(metadata)
    base_c3_overrides = dict(s513._c3_overrides(YEAR_STARTS[0].to_pydatetime()))

    rows: list[dict[str, Any]] = []
    cost_rows: list[dict[str, Any]] = []
    curves: list[pd.DataFrame] = []
    original_end = s653.s517.END_DT
    try:
        s653.s517.END_DT = ANALYSIS_END.to_pydatetime()
        print(f"[stage776] launching {len(YEAR_STARTS)} yearly AM41 OI split runs", flush=True)
        for idx, start in enumerate(YEAR_STARTS, start=1):
            print(f"[stage776] running {idx}/{len(YEAR_STARTS)} start={start.date()}", flush=True)
            row, costs, curve = _run_one(profile, start, metadata, base_c3_overrides)
            rows.append(row)
            cost_rows.extend(costs)
            curves.append(curve)
    finally:
        s653.s517.END_DT = original_end

    summary = (
        s772._add_month_fields(pd.DataFrame(rows))
        .sort_values(["start_month"])
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
    for bucket, frame in [("all", summary), ("mature_252d", summary[summary["mature_252d"].eq(1)])]:
        returns = pd.to_numeric(frame["rebased_total_return_pct"], errors="coerce")
        dds = pd.to_numeric(frame["rebased_max_dd_pct"], errors="coerce")
        sharpes = pd.to_numeric(frame["rebased_sharpe"], errors="coerce")
        rows.append(
            {
                "profile": "stage776_am41_oi12_nonhit02",
                "bucket": bucket,
                "start_count": int(len(frame)),
                "positive_count": int(frame["positive_return"].sum()) if len(frame) else 0,
                "positive_rate_pct": float(frame["positive_return"].mean() * 100.0) if len(frame) else 0.0,
                "median_return_pct": float(returns.median()) if len(frame) else 0.0,
                "p10_return_pct": float(returns.quantile(0.10)) if len(frame) else 0.0,
                "min_return_pct": float(returns.min()) if len(frame) else 0.0,
                "median_dd_pct": float(dds.median()) if len(frame) else 0.0,
                "worst_dd_pct": float(dds.min()) if len(frame) else 0.0,
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
                    "profile": "stage776_am41_oi12_nonhit02",
                    "bucket": f"cost_{multiplier}x_all",
                    "start_count": int(summary.shape[0]),
                    "median_return_pct": float(pd.to_numeric(frame["total_return_pct"], errors="coerce").median()),
                    "dd40_fail_count": int(frame["dd40_fail"].sum()),
                }
            )
    return pd.DataFrame(rows)


def _load_stage775_summary() -> pd.DataFrame:
    if not STAGE775_SUMMARY_PATH.exists():
        raise FileNotFoundError(f"missing Stage775 summary: {STAGE775_SUMMARY_PATH}")
    base = pd.read_csv(STAGE775_SUMMARY_PATH, encoding="utf-8-sig")
    return base[base["am_label"].astype(str).eq("am40")].copy()


def _comparison_vs_stage775(summary: pd.DataFrame) -> pd.DataFrame:
    base = _load_stage775_summary()
    rows: list[dict[str, Any]] = []
    for baseline_oi_mode, baseline_label in [
        ("no_oi", "Stage775 no-OI AM41 r0.40"),
        ("oi_restore", "Stage775 OI AM41 r0.40->0.80"),
    ]:
        baseline = base[base["oi_mode"].astype(str).eq(baseline_oi_mode)].copy()
        merged = baseline.merge(summary, on="start_month", suffixes=("_base", "_candidate"), how="inner")
        merged["return_delta_pct"] = (
            pd.to_numeric(merged["rebased_total_return_pct_candidate"], errors="coerce")
            - pd.to_numeric(merged["rebased_total_return_pct_base"], errors="coerce")
        )
        merged["dd_delta_pp"] = (
            pd.to_numeric(merged["rebased_max_dd_pct_candidate"], errors="coerce")
            - pd.to_numeric(merged["rebased_max_dd_pct_base"], errors="coerce")
        )
        merged["sharpe_delta"] = (
            pd.to_numeric(merged["rebased_sharpe_candidate"], errors="coerce")
            - pd.to_numeric(merged["rebased_sharpe_base"], errors="coerce")
        )
        for bucket, frame in [("all", merged), ("mature_252d", merged[merged["mature_252d_base"].eq(1)])]:
            rows.append(
                {
                    "baseline": baseline_label,
                    "baseline_oi_mode": baseline_oi_mode,
                    "bucket": bucket,
                    "start_count": int(len(frame)),
                    "return_win_count": int((frame["return_delta_pct"] > 0.0).sum()) if len(frame) else 0,
                    "return_win_rate_pct": float((frame["return_delta_pct"] > 0.0).mean() * 100.0) if len(frame) else 0.0,
                    "dd_win_count": int((frame["dd_delta_pp"] > 0.0).sum()) if len(frame) else 0,
                    "dd_win_rate_pct": float((frame["dd_delta_pp"] > 0.0).mean() * 100.0) if len(frame) else 0.0,
                    "median_return_delta_pct": float(frame["return_delta_pct"].median()) if len(frame) else 0.0,
                    "p10_return_delta_pct": float(frame["return_delta_pct"].quantile(0.10)) if len(frame) else 0.0,
                    "min_return_delta_pct": float(frame["return_delta_pct"].min()) if len(frame) else 0.0,
                    "median_dd_delta_pp": float(frame["dd_delta_pp"].median()) if len(frame) else 0.0,
                    "worst_dd_delta_pp": float(frame["dd_delta_pp"].min()) if len(frame) else 0.0,
                    "median_sharpe_delta": float(frame["sharpe_delta"].median()) if len(frame) else 0.0,
                }
            )
    return pd.DataFrame(rows)


def _plot_return_chart(summary: pd.DataFrame) -> None:
    base = _load_stage775_summary()
    base = base[base["oi_mode"].isin(["no_oi", "oi_restore"])].copy()
    plot_rows = []
    for _, row in base.iterrows():
        plot_rows.append(
            {
                "start_year": int(row["start_year"]),
                "series": "Stage775 no-OI AM41 r0.40" if row["oi_mode"] == "no_oi" else "Stage775 OI AM41 r0.40->0.80",
                "return": float(row["rebased_total_return_pct"]),
            }
        )
    for _, row in summary.iterrows():
        plot_rows.append(
            {
                "start_year": int(row["start_year"]),
                "series": "Stage776 OI split r0.20->1.20",
                "return": float(row["rebased_total_return_pct"]),
            }
        )
    data = pd.DataFrame(plot_rows)
    pivot = data.pivot_table(index="start_year", columns="series", values="return", aggfunc="first")
    series_order = ["Stage775 no-OI AM41 r0.40", "Stage775 OI AM41 r0.40->0.80", "Stage776 OI split r0.20->1.20"]
    pivot = pivot[series_order]

    x = np.arange(len(pivot.index))
    width = 0.26
    fig, ax = plt.subplots(figsize=(15, 7))
    colors = ["#2563eb", "#f97316", "#059669"]
    for i, series in enumerate(series_order):
        ax.bar(x + (i - 1) * width, pivot[series], width=width, label=series, color=colors[i], alpha=0.88)
    ax.axhline(0.0, color="#111827", linewidth=1)
    ax.set_title("Stage776 AM41 OI split: final return by start year")
    ax.set_ylabel("Total return %")
    ax.set_xlabel("Start year")
    ax.set_xticks(x)
    ax.set_xticklabels([str(int(year)) for year in pivot.index])
    ax.grid(axis="y", alpha=0.25)
    ax.legend()
    fig.tight_layout()
    fig.savefig(RETURN_CHART_PATH, dpi=180)
    plt.close(fig)


def _plot_equity_curves(curves: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(16, 8))
    cmap = plt.cm.tab10
    for idx, (start_month, group) in enumerate(curves.groupby("start_month", sort=True)):
        group = group.sort_values("date")
        ax.plot(
            pd.to_datetime(group["date"]),
            pd.to_numeric(group["account_equity"], errors="coerce") / 1_000_000,
            label=str(start_month)[:4],
            color=cmap(idx % 10),
            linewidth=1.6,
            alpha=0.9,
        )
    ax.axhline(0.5, color="#9ca3af", linestyle="--", linewidth=1)
    ax.set_title("Stage776 AM41 OI split equity curves by yearly start")
    ax.set_ylabel("Account equity")
    ax.set_xlabel("Date")
    ax.yaxis.set_major_formatter(lambda x, pos: f"{x:.1f}M")
    ax.grid(alpha=0.25)
    ax.legend(title="Start year", ncol=9, loc="upper left")
    fig.tight_layout()
    fig.savefig(EQUITY_CHART_PATH, dpi=180)
    plt.close(fig)


def _build_decision(profile_agg: pd.DataFrame, comparison: pd.DataFrame) -> dict[str, Any]:
    mature = profile_agg[profile_agg["bucket"].eq("mature_252d")].iloc[0]
    vs_no_oi = comparison[
        comparison["baseline_oi_mode"].eq("no_oi") & comparison["bucket"].eq("mature_252d")
    ].iloc[0]
    hard_fail: list[str] = []
    watch: list[str] = []
    if float(mature["worst_dd_pct"]) < -40.0:
        hard_fail.append("mature_worst_dd40_fail")
    if int(mature["positive_count"]) < int(mature["start_count"]):
        watch.append("mature_not_all_positive")
    if float(vs_no_oi["return_win_rate_pct"]) < 50.0:
        hard_fail.append("does_not_beat_stage775_no_oi_am41_in_most_mature_starts")
    if float(vs_no_oi["median_dd_delta_pp"]) < -3.0:
        hard_fail.append("median_dd_worse_than_stage775_no_oi_by_more_than_3pp")
    decision = "am41_oi_split_not_promoted" if hard_fail else "am41_oi_split_candidate_watch"
    return {
        "stage": "Stage776",
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "decision": decision,
        "hard_fail_checks": hard_fail,
        "watch_checks": watch,
        "analysis_start_first": YEAR_STARTS[0].date().isoformat(),
        "analysis_start_last": YEAR_STARTS[-1].date().isoformat(),
        "analysis_end": ANALYSIS_END.date().isoformat(),
        "change": {
            "official_config_changed": False,
            "ctp_connected": False,
            "order_api_called": False,
            "am_gate": "research_exact_am41",
            "base_non_oi_effective_risk_multiplier": BASE_NONHIT_RISK,
            "oi_hit_effective_risk_multiplier": OI_HIT_RISK,
            "oi_internal_multiplier": OI_INTERNAL_MULTIPLIER,
            "streak_risk_multipliers": "1.0,1.0,1.0,1.0",
            "enable_recovery_sleeve": False,
            "causal_timing": "latest_completed_daily_bar",
        },
        "profile_aggregate": profile_agg.to_dict("records"),
        "comparison": comparison.to_dict("records"),
        "outputs": {
            "summary": str(SUMMARY_PATH),
            "cost": str(COST_PATH),
            "curves": str(CURVES_PATH),
            "profile_aggregate": str(PROFILE_AGG_PATH),
            "comparison": str(COMPARISON_PATH),
            "return_chart": str(RETURN_CHART_PATH),
            "equity_chart": str(EQUITY_CHART_PATH),
            "report": str(REPORT_PATH),
        },
        "overfit_judgment": (
            "medium/high: 1.20 vs 0.20 is a strong risk split and OI single-factor timing has already shown "
            "right-tail amplification with drawdown risk; yearly starts are only a first screen."
        ),
        "continue_value": (
            "yes if it improves AM41 without worse drawdown; otherwise keep as a rejected risk-router shape and avoid "
            "scanning nearby OI risk decimals."
        ),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }


def _write_report(profile_agg: pd.DataFrame, comparison: pd.DataFrame, decision: dict[str, Any]) -> None:
    lines = [
        "# Stage776 AM41 OI 1.20 / non-OI 0.20 年度启动验证",
        "",
        f"- line_id：`{LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        f"- 起点：`{YEAR_STARTS[0].strftime('%Y-%m')}` 到 `{YEAR_STARTS[-1].strftime('%Y-%m')}`；终点 `{ANALYSIS_END.date()}`。",
        "- 口径：AM41 研究门槛；未命中 OI 确认为 `0.20` 风险；命中 `OI上升 + 价格沿方向` 后提升到 `1.20` 风险。",
        "- 对照：Stage775 修复残仓后的 `no_oi/am41` 与 `oi_restore/am41`。",
        "",
        "## Profile Aggregate",
        "",
        _md_table(profile_agg, max_rows=20),
        "",
        "## Comparison Vs Stage775",
        "",
        _md_table(comparison, max_rows=20),
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
    comparison = _comparison_vs_stage775(summary)
    decision = _build_decision(profile_agg, comparison)

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    cost.to_csv(COST_PATH, index=False, encoding="utf-8-sig")
    curves.to_csv(CURVES_PATH, index=False, encoding="utf-8-sig")
    profile_agg.to_csv(PROFILE_AGG_PATH, index=False, encoding="utf-8-sig")
    comparison.to_csv(COMPARISON_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _plot_return_chart(summary)
    _plot_equity_curves(curves)
    _write_report(profile_agg, comparison, decision)

    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
