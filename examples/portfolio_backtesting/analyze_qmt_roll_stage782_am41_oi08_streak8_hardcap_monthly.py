from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import replace
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
import analyze_qmt_roll_stage757_c50_oi_confirm_risk_restore as s757
import analyze_qmt_roll_stage772_am40_80_120_oi_monthly as s772
import analyze_qmt_roll_stage777_am41_oi08_monthly as s777
import analyze_qmt_roll_stage781_am41_oi08_streak8_monthly as s781


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

MODEL_TAG = "stage782_am41_oi08_streak8_hardcap_monthly_v1"
OUTPUT_PREFIX = "qmt_roll_stage782_am41_oi08_streak8_hardcap_monthly"
LINE_ID = "futures_trend_2019_data_extension"

ANALYSIS_END = pd.Timestamp("2026-05-29")
MONTH_STARTS = tuple(pd.date_range("2018-01-01", "2026-05-01", freq="MS"))
MAX_WORKERS = max(1, min(6, int(os.environ.get("STAGE782_MAX_WORKERS", "6"))))

CANDIDATE_VARIANT = "stage782_500k_am41_oi08_streak8_hardcap_monthly"
CANDIDATE_LABEL = "Stage782 AM41 OI0.8 with hard loss-streak floor after >7 losses"
STREAK8_MULTIPLIERS = "1.0,1.0,1.0,1.0,1.0,1.0,1.0,1.0,0.1"

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
COST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cost_stress_{MODEL_TAG}.csv"
CURVES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv"
PROFILE_AGG_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_profile_aggregate_{MODEL_TAG}.csv"
PHASE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_phase_summary_{MODEL_TAG}.csv"
COMPARISON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_comparison_vs_stage777_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
RETURN_HEATMAP_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_return_heatmap_{MODEL_TAG}.png"
DD_HEATMAP_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_dd_heatmap_{MODEL_TAG}.png"
DELTA_HEATMAP_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_delta_vs_stage777_heatmap_{MODEL_TAG}.png"
EQUITY_CURVES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_equity_curves_selected_{MODEL_TAG}.png"

PROFILE_NAME = "stage782_am41_oi08_streak8_hardcap"

_WORKER_METADATA: dict[str, Any] | None = None
_WORKER_PROFILE: dict[str, Any] | None = None


class QmtRollPortfolioStrategyExactAmStreak8HardCap(s772.QmtRollPortfolioStrategyExactAm):
    """Research-only wrapper: loss-streak floor has final priority over OI restore."""

    def _oi_price_confirm_risk_restore_fields(
        self,
        *,
        history: pd.DataFrame,
        direction: str,
        entry_context: str,
        base_multiplier: float,
    ) -> dict[str, Any]:
        fields = super()._oi_price_confirm_risk_restore_fields(
            history=history,
            direction=direction,
            entry_context=entry_context,
            base_multiplier=base_multiplier,
        )
        base = max(0.0, float(base_multiplier or 0.0))
        if base < 1.0 - 1e-12 and int(fields.get("oi_price_confirm_passed") or 0) == 1:
            fields["oi_price_confirm_risk_restore_effective_multiplier"] = base
            fields["oi_price_confirm_risk_restore_applied"] = 0
            fields["oi_price_confirm_risk_restore_reason"] = "streak_floor_blocks_oi_restore"
        return fields


def _json_safe(value: Any) -> Any:
    return s650._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s650._md_table(frame, max_rows=max_rows)


def _candidate_profile(metadata: dict[str, Any]) -> dict[str, Any]:
    base = s757._candidate_spec(metadata)
    capital = replace(
        base.capital,
        variant=CANDIDATE_VARIANT,
        label=CANDIDATE_LABEL,
        note=(
            "Stage777 AM41/OI0.8 logic, with loss-streak throttle restored after strictly more than "
            "seven consecutive losing lots. Unlike Stage781, OI restore cannot bypass the 0.1 floor."
        ),
    )
    overrides = {
        **base.overrides,
        "array_manager_size_floor": 40,
        "research_exact_array_manager_size": 41,
        "streak_risk_multipliers": STREAK8_MULTIPLIERS,
        "enable_streak_entry_structure_risk_recovery": False,
        "enable_recovery_sleeve": False,
    }
    spec = replace(base, capital=capital, overrides=overrides, profile=PROFILE_NAME)
    return {
        "profile": PROFILE_NAME,
        "oi_mode": "oi_restore",
        "am_label": "am40",
        "declared_am_size": 41,
        "strategy_cls": QmtRollPortfolioStrategyExactAmStreak8HardCap,
        "spec": spec,
        "note": "Research-only AM41 plus OI0.8; hard loss-streak floor starts at loss_streak >= 8.",
    }


def _rewrite_outputs(
    row: dict[str, Any],
    costs: list[dict[str, Any]],
    curve: pd.DataFrame,
) -> tuple[dict[str, Any], list[dict[str, Any]], pd.DataFrame]:
    row = dict(row)
    row.update(
        {
            "variant": CANDIDATE_VARIANT,
            "label": CANDIDATE_LABEL,
            "profile": PROFILE_NAME,
            "source_name": "stage782_am41_oi08_streak8_hardcap_monthly",
            "oi_mode": "oi_restore",
            "am_label": "am40",
            "declared_am_size": 41,
            "streak_risk_multipliers": STREAK8_MULTIPLIERS,
            "note": "Stage777 plus hard loss-streak floor after loss_streak >= 8.",
        }
    )
    for cost in costs:
        cost.update(
            {
                "variant": CANDIDATE_VARIANT,
                "label": CANDIDATE_LABEL,
                "profile": PROFILE_NAME,
                "source_name": "stage782_am41_oi08_streak8_hardcap_monthly",
                "oi_mode": "oi_restore",
                "am_label": "am40",
                "declared_am_size": 41,
            }
        )
    frame = curve.copy()
    frame["variant"] = CANDIDATE_VARIANT
    frame["label"] = CANDIDATE_LABEL
    frame["profile"] = PROFILE_NAME
    frame["source_name"] = "stage782_am41_oi08_streak8_hardcap_monthly"
    frame["oi_mode"] = "oi_restore"
    frame["am_label"] = "am40"
    frame["declared_am_size"] = 41
    return row, costs, frame


def _run_one(task: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]], pd.DataFrame]:
    global _WORKER_METADATA, _WORKER_PROFILE
    if _WORKER_METADATA is None:
        _WORKER_METADATA = s513._metadata()
        _WORKER_PROFILE = _candidate_profile(_WORKER_METADATA)
    metadata = _WORKER_METADATA
    profile = _WORKER_PROFILE
    if profile is None:
        raise RuntimeError("missing worker profile")
    start = pd.Timestamp(task["start"])
    try:
        frame, forced_events = s772._run_engine(
            profile=profile,
            start=start,
            metadata=metadata,
            base_c3_overrides=dict(task["base_c3_overrides"]),
        )
    except RuntimeError as exc:
        if "empty daily result" not in str(exc):
            raise
        row, costs, curve = s781._flat_no_trade_result(task)
        return _rewrite_outputs(row, costs, curve)
    spec = profile["spec"]
    row, curve, costs = s772.s748._metric_row(
        frame,
        spec=spec,
        window_name=s772._window_name(start),
        window_label=s772._window_label(start),
        window_group="monthly_start",
        forced_events=forced_events,
    )
    row = s772._metric_common(row)
    row["requested_start_month"] = start.strftime("%Y-%m")
    row["start_month"] = start.strftime("%Y-%m")
    curve = s772._curve_common(curve)
    curve["requested_start_month"] = start.strftime("%Y-%m")
    curve["start_month"] = start.strftime("%Y-%m")
    for cost in costs:
        cost["requested_start_month"] = start.strftime("%Y-%m")
        cost["start_month"] = start.strftime("%Y-%m")
    return _rewrite_outputs(row, costs, curve)


def _run_all() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    metadata = s513._metadata()
    if not metadata:
        raise RuntimeError("empty metadata")
    base_c3_overrides = dict(s513._c3_overrides(MONTH_STARTS[0].to_pydatetime()))
    tasks = [{"start": start.strftime("%Y-%m-%d"), "base_c3_overrides": base_c3_overrides} for start in MONTH_STARTS]

    rows: list[dict[str, Any]] = []
    cost_rows: list[dict[str, Any]] = []
    curves: list[pd.DataFrame] = []
    print(f"[stage782] launching {len(tasks)} monthly runs workers={MAX_WORKERS}", flush=True)
    if MAX_WORKERS == 1:
        for idx, task in enumerate(tasks, start=1):
            print(f"[stage782] running {idx}/{len(tasks)} {task['start']}", flush=True)
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
                print(f"[stage782] completed {idx}/{len(tasks)} {task['start']}", flush=True)

    summary = s772._add_month_fields(pd.DataFrame(rows)).sort_values("start_month").reset_index(drop=True)
    cost = pd.DataFrame(cost_rows).sort_values(["start_month", "cost_multiplier"]).reset_index(drop=True)
    curves_all = pd.concat(curves, ignore_index=True, sort=False).sort_values(["start_month", "date"]).reset_index(drop=True)
    return summary, cost, curves_all


def _profile_aggregate(summary: pd.DataFrame, cost: pd.DataFrame) -> pd.DataFrame:
    frame = s781._profile_aggregate(summary, cost)
    frame["profile"] = PROFILE_NAME
    return frame


def _phase_summary(summary: pd.DataFrame) -> pd.DataFrame:
    return s781._phase_summary(summary)


def _comparison_vs_stage777(summary: pd.DataFrame) -> pd.DataFrame:
    base = pd.read_csv(s777.SUMMARY_PATH, encoding="utf-8-sig")
    base["start_month"] = base["start_month"].astype(str)
    candidate = summary.copy()
    merged = base.merge(candidate, on="start_month", suffixes=("_stage777", "_stage782"), how="inner")
    merged["return_delta_pct"] = (
        pd.to_numeric(merged["rebased_total_return_pct_stage782"], errors="coerce")
        - pd.to_numeric(merged["rebased_total_return_pct_stage777"], errors="coerce")
    )
    merged["dd_delta_pp"] = (
        pd.to_numeric(merged["rebased_max_dd_pct_stage782"], errors="coerce")
        - pd.to_numeric(merged["rebased_max_dd_pct_stage777"], errors="coerce")
    )
    merged["sharpe_delta"] = (
        pd.to_numeric(merged["rebased_sharpe_stage782"], errors="coerce")
        - pd.to_numeric(merged["rebased_sharpe_stage777"], errors="coerce")
    )
    merged["trade_count_delta"] = (
        pd.to_numeric(merged["total_trade_count_stage782"], errors="coerce")
        - pd.to_numeric(merged["total_trade_count_stage777"], errors="coerce")
    )
    merged["candidate_return_win"] = (merged["return_delta_pct"] > 0.0).astype(int)
    merged["candidate_dd_win"] = (merged["dd_delta_pp"] > 0.0).astype(int)
    merged["candidate_both_win"] = (merged["candidate_return_win"].eq(1) & merged["candidate_dd_win"].eq(1)).astype(int)
    return merged.sort_values("start_month").reset_index(drop=True)


def _comparison_aggregate(comparison: pd.DataFrame) -> pd.DataFrame:
    return s781._comparison_aggregate(comparison)


def _plot_delta_heatmap(comparison: pd.DataFrame) -> None:
    data = comparison.copy()
    data["start_year"] = pd.to_datetime(data["start_month"] + "-01", errors="coerce").dt.year
    data["start_month_num"] = pd.to_datetime(data["start_month"] + "-01", errors="coerce").dt.month
    fig, axes = plt.subplots(1, 2, figsize=(18, 6.8), constrained_layout=True)
    for ax, column, title in [
        (axes[0], "return_delta_pct", "Stage782 - Stage777 return delta pp"),
        (axes[1], "dd_delta_pp", "Stage782 - Stage777 max DD delta pp"),
    ]:
        pivot = data.pivot_table(index="start_year", columns="start_month_num", values=column, aggfunc="first")
        values = pd.to_numeric(data[column], errors="coerce")
        vmax = max(abs(float(np.nanpercentile(values, 5))), abs(float(np.nanpercentile(values, 95))), 1.0)
        norm = TwoSlopeNorm(vcenter=0.0, vmin=-vmax, vmax=vmax)
        im = ax.imshow(pivot.to_numpy(dtype=float), aspect="auto", cmap="RdYlGn", norm=norm)
        ax.set_title(title)
        ax.set_xticks(range(12))
        ax.set_xticklabels(range(1, 13))
        ax.set_yticks(range(len(pivot.index)))
        ax.set_yticklabels([str(int(item)) for item in pivot.index])
        for i, year in enumerate(pivot.index):
            for j, month in enumerate(pivot.columns):
                value = pivot.loc[year, month]
                if pd.notna(value):
                    ax.text(j, i, f"{value:.0f}", ha="center", va="center", fontsize=7, color="#111827")
        fig.colorbar(im, ax=ax, shrink=0.85)
    fig.savefig(DELTA_HEATMAP_PATH, dpi=180)
    plt.close(fig)


def _plot_selected_equity_curves(curves: pd.DataFrame, summary: pd.DataFrame) -> None:
    selected = {"2018-01", "2019-01", "2020-01", "2021-01", "2022-01", "2023-01", "2024-01", "2025-01", "2026-01"}
    for _, row in summary.nsmallest(3, "rebased_total_return_pct").iterrows():
        selected.add(str(row["start_month"]))
    for _, row in summary.nlargest(3, "rebased_total_return_pct").iterrows():
        selected.add(str(row["start_month"]))
    data = curves[curves["start_month"].astype(str).isin(sorted(selected))].copy()
    fig, ax = plt.subplots(figsize=(16, 8))
    colors = plt.cm.tab20.colors
    for idx, (start_month, group) in enumerate(data.groupby("start_month", sort=True)):
        group = group.sort_values("date")
        ax.plot(pd.to_datetime(group["date"]), pd.to_numeric(group["account_equity"], errors="coerce") / 1_000_000, label=start_month, color=colors[idx % len(colors)], linewidth=1.6, alpha=0.9)
    ax.axhline(0.5, color="#9ca3af", linestyle="--", linewidth=1)
    ax.set_title("Stage782 selected monthly-start equity curves")
    ax.set_xlabel("Date")
    ax.set_ylabel("Account equity")
    ax.yaxis.set_major_formatter(lambda x, pos: f"{x:.1f}M")
    ax.grid(alpha=0.25)
    ax.legend(ncol=4, fontsize=8)
    fig.tight_layout()
    fig.savefig(EQUITY_CURVES_PATH, dpi=180)
    plt.close(fig)


def _build_decision(profile_agg: pd.DataFrame, phase: pd.DataFrame, comparison_agg: pd.DataFrame) -> dict[str, Any]:
    mature = profile_agg[profile_agg["bucket"].eq("mature_252d")].iloc[0]
    comp_mature = comparison_agg[comparison_agg["bucket"].eq("mature_252d")].iloc[0]
    hard_fail: list[str] = []
    watch: list[str] = []
    if int(mature["dd40_fail_count"]) > 0:
        hard_fail.append("mature_dd40_fail_exists")
    if float(mature["worst_dd_pct"]) < -45.0:
        hard_fail.append("mature_worst_dd_below_45")
    if float(comp_mature["return_win_rate_pct"]) < 45.0:
        hard_fail.append("return_win_rate_vs_stage777_lt45pct")
    if float(comp_mature["median_return_delta_pct"]) < -25.0:
        hard_fail.append("median_return_delta_vs_stage777_lt_minus25pp")
    if float(comp_mature["dd_win_rate_pct"]) < 55.0:
        watch.append("dd_win_rate_vs_stage777_below55pct")
    decision = "am41_oi08_streak8_hardcap_monthly_not_promoted" if hard_fail else "am41_oi08_streak8_hardcap_monthly_candidate_watch"
    return {
        "stage": "Stage782",
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
            "base_version": "Stage777 AM41 OI0.8 monthly",
            "am_gate": "research_exact_am41",
            "base_effective_risk_multiplier": 0.40,
            "oi_hit_effective_risk_multiplier": 0.80,
            "streak_risk_multipliers_before": "1.0,1.0,1.0,1.0",
            "streak_risk_multipliers_after": STREAK8_MULTIPLIERS,
            "loss_streak_floor_starts_at": 8,
            "oi_restore_blocked_when_streak_floor_active": True,
            "enable_recovery_sleeve": False,
            "causal_timing": "latest_completed_daily_bar",
        },
        "profile_aggregate": profile_agg.to_dict("records"),
        "phase_summary": phase.to_dict("records"),
        "comparison_vs_stage777": comparison_agg.to_dict("records"),
        "outputs": {
            "summary": str(SUMMARY_PATH),
            "cost": str(COST_PATH),
            "curves": str(CURVES_PATH),
            "profile_aggregate": str(PROFILE_AGG_PATH),
            "phase": str(PHASE_PATH),
            "comparison": str(COMPARISON_PATH),
            "return_heatmap": str(RETURN_HEATMAP_PATH),
            "dd_heatmap": str(DD_HEATMAP_PATH),
            "delta_heatmap": str(DELTA_HEATMAP_PATH),
            "equity_curves": str(EQUITY_CURVES_PATH),
            "report": str(REPORT_PATH),
        },
        "overfit_judgment": "medium: threshold 8 is derived from the 2022 loss cluster, so only broad monthly-start improvement can justify further work.",
        "continue_value": "yes for this hard-cap validation; no threshold rescue if it fails robustness.",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }


def _write_report(profile_agg: pd.DataFrame, phase: pd.DataFrame, comparison_agg: pd.DataFrame, decision: dict[str, Any]) -> None:
    lines = [
        "# Stage782 AM41 OI0.8 + 连败超过7笔后硬缩仓",
        "",
        f"- line_id：`{LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        f"- 起点：`{MONTH_STARTS[0].strftime('%Y-%m')}` 到 `{MONTH_STARTS[-1].strftime('%Y-%m')}`；终点 `{ANALYSIS_END.date()}`。",
        "- 口径：Stage777 AM41/OI0.8；基础等效风险 `0.40`；命中 OI 后 `0.80`；`loss_streak >= 8` 后进入 `0.1`，且 OI 不能豁免。",
        "",
        "## Profile Aggregate",
        "",
        _md_table(profile_agg, max_rows=20),
        "",
        "## Comparison vs Stage777",
        "",
        _md_table(comparison_agg, max_rows=20),
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
    comparison = _comparison_vs_stage777(summary)
    comparison_agg = _comparison_aggregate(comparison)
    decision = _build_decision(profile_agg, phase, comparison_agg)

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    cost.to_csv(COST_PATH, index=False, encoding="utf-8-sig")
    curves.to_csv(CURVES_PATH, index=False, encoding="utf-8-sig")
    profile_agg.to_csv(PROFILE_AGG_PATH, index=False, encoding="utf-8-sig")
    phase.to_csv(PHASE_PATH, index=False, encoding="utf-8-sig")
    comparison.to_csv(COMPARISON_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    s781._plot_heatmap(summary, "rebased_total_return_pct", RETURN_HEATMAP_PATH, "Stage782 AM41 OI0.8 hard streak8 return % by monthly start", "RdYlGn", 0.0)
    s781._plot_heatmap(summary, "rebased_max_dd_pct", DD_HEATMAP_PATH, "Stage782 AM41 OI0.8 hard streak8 max DD % by monthly start", "RdYlGn", -40.0)
    _plot_delta_heatmap(comparison)
    _plot_selected_equity_curves(curves, summary)
    _write_report(profile_agg, phase, comparison_agg, decision)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
