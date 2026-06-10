from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime
import json
import os
from pathlib import Path
from typing import Any

import pandas as pd

import analyze_qmt_roll_stage513_stage208_exact_position_margin_audit as s513
import analyze_qmt_roll_stage650_stage526_200k_capital_reality_check as s650
import analyze_qmt_roll_stage772_am40_80_120_oi_monthly as s772


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

MODEL_TAG = "stage773_am40_80_120_oi_yearly_v1"
OUTPUT_PREFIX = "qmt_roll_stage773_am40_80_120_oi_yearly"
LINE_ID = "futures_trend_2019_data_extension"

ANALYSIS_END = s772.ANALYSIS_END
YEAR_STARTS = tuple(pd.date_range("2018-01-01", "2026-01-01", freq="YS"))
MAX_WORKERS = max(1, min(6, int(os.environ.get("STAGE773_MAX_WORKERS", "6"))))

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
COST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cost_stress_{MODEL_TAG}.csv"
CURVES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv"
PROFILE_AGG_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_profile_aggregate_{MODEL_TAG}.csv"
COMPARISON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_comparison_vs_am120_{MODEL_TAG}.csv"
PHASE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_phase_summary_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
RETURN_HEATMAP_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_return_heatmaps_{MODEL_TAG}.png"
DD_HEATMAP_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_dd_heatmaps_{MODEL_TAG}.png"
COMPARISON_CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_comparison_chart_{MODEL_TAG}.png"


def _json_safe(value: Any) -> Any:
    return s650._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s650._md_table(frame, max_rows=max_rows)


def _run_all_yearly() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    metadata = s513._metadata()
    profiles = s772._profile_specs(metadata)
    base_c3_overrides = dict(s513._c3_overrides(YEAR_STARTS[0].to_pydatetime()))
    tasks = [
        {
            "profile": profile["profile"],
            "start": start.strftime("%Y-%m-%d"),
            "base_c3_overrides": base_c3_overrides,
        }
        for profile in profiles
        for start in YEAR_STARTS
    ]

    rows: list[dict[str, Any]] = []
    cost_rows: list[dict[str, Any]] = []
    curves: list[pd.DataFrame] = []
    print(f"[stage773] launching {len(tasks)} yearly runs workers={MAX_WORKERS}", flush=True)
    if MAX_WORKERS == 1:
        for idx, task in enumerate(tasks, start=1):
            print(f"[stage773] running {idx}/{len(tasks)} {task['profile']} {task['start']}", flush=True)
            row, costs, curve = s772._run_one(task)
            rows.append(row)
            cost_rows.extend(costs)
            curves.append(curve)
    else:
        with ProcessPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_map = {executor.submit(s772._run_one, task): task for task in tasks}
            for idx, future in enumerate(as_completed(future_map), start=1):
                task = future_map[future]
                row, costs, curve = future.result()
                rows.append(row)
                cost_rows.extend(costs)
                curves.append(curve)
                print(f"[stage773] completed {idx}/{len(tasks)} {task['profile']} {task['start']}", flush=True)

    summary = (
        s772._add_month_fields(pd.DataFrame(rows))
        .sort_values(["oi_mode", "am_label", "start_month"])
        .reset_index(drop=True)
    )
    cost = (
        pd.DataFrame(cost_rows)
        .sort_values(["oi_mode", "am_label", "start_month", "cost_multiplier"])
        .reset_index(drop=True)
    )
    curves_all = (
        pd.concat(curves, ignore_index=True, sort=False)
        .sort_values(["oi_mode", "am_label", "start_month", "date"])
        .reset_index(drop=True)
    )
    return summary, cost, curves_all


def _build_decision(profile_agg: pd.DataFrame, comparison: pd.DataFrame) -> dict[str, Any]:
    old_month_starts = s772.MONTH_STARTS
    try:
        s772.MONTH_STARTS = YEAR_STARTS
        decision = s772._build_decision(profile_agg, comparison)
    finally:
        s772.MONTH_STARTS = old_month_starts
    decision.pop("monthly_start_count_per_profile", None)
    decision.update(
        {
            "stage": "Stage773",
            "line_id": LINE_ID,
            "model_tag": MODEL_TAG,
            "start_frequency": "yearly",
            "yearly_start_count_per_profile": len(YEAR_STARTS),
            "profile_count": 6,
            "outputs": {
                "summary": str(SUMMARY_PATH),
                "cost": str(COST_PATH),
                "curves": str(CURVES_PATH),
                "profile_aggregate": str(PROFILE_AGG_PATH),
                "comparison_vs_am120": str(COMPARISON_PATH),
                "phase_summary": str(PHASE_PATH),
                "return_heatmap": str(RETURN_HEATMAP_PATH),
                "dd_heatmap": str(DD_HEATMAP_PATH),
                "comparison_chart": str(COMPARISON_CHART_PATH),
                "report": str(REPORT_PATH),
            },
            "generated_at": datetime.now().isoformat(timespec="seconds"),
        }
    )
    return decision


def _write_report(profile_agg: pd.DataFrame, comparison: pd.DataFrame, phase: pd.DataFrame, decision: dict[str, Any]) -> None:
    lines = [
        "# Stage773 AM40/80/120 × OI 年度启动验证",
        "",
        f"- line_id：`{LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        f"- 起点：`{YEAR_STARTS[0].strftime('%Y-%m')}` 到 `{YEAR_STARTS[-1].strftime('%Y-%m')}`；终点 `{ANALYSIS_END.date()}`。",
        "- 六组：无OI/有OI × AM120/AM80/AM40。AM40 为研究专用 AM=41。",
        "",
        "## Profile Aggregate",
        "",
        _md_table(profile_agg, max_rows=80),
        "",
        "## Comparison Vs AM120",
        "",
        _md_table(comparison, max_rows=40),
        "",
        "## Phase Summary",
        "",
        _md_table(phase, max_rows=80),
        "",
        "## Decision",
        "",
        f"- 决策：`{decision['decision']}`",
        f"- 过拟合判断：`{decision['overfit_judgment']}`",
        f"- 继续价值：`{decision['continue_value']}`",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    summary, cost, curves = _run_all_yearly()
    profile_agg = s772._profile_aggregate(summary, cost)
    comparison = s772._comparison_vs_am120(summary)
    phase = s772._phase_summary(summary)
    decision = _build_decision(profile_agg, comparison)

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    cost.to_csv(COST_PATH, index=False, encoding="utf-8-sig")
    curves.to_csv(CURVES_PATH, index=False, encoding="utf-8-sig")
    profile_agg.to_csv(PROFILE_AGG_PATH, index=False, encoding="utf-8-sig")
    comparison.to_csv(COMPARISON_PATH, index=False, encoding="utf-8-sig")
    phase.to_csv(PHASE_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    s772._plot_heatmaps(summary, "rebased_total_return_pct", RETURN_HEATMAP_PATH, "Stage773 Yearly Start Return %", "RdYlGn", 0.0)
    s772._plot_heatmaps(summary, "rebased_max_dd_pct", DD_HEATMAP_PATH, "Stage773 Yearly Start Max DD %", "RdYlGn", -40.0)
    s772._plot_comparison(comparison, COMPARISON_CHART_PATH)
    _write_report(profile_agg, comparison, phase, decision)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
