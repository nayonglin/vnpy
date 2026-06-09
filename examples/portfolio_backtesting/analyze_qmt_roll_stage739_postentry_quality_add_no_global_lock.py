from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path

import pandas as pd

import analyze_qmt_roll_stage513_stage208_exact_position_margin_audit as s513
import analyze_qmt_roll_stage660_stage653_multiperiod_live_audit as s660
import analyze_qmt_roll_stage707_recovery_all_cases_multiperiod as s707
import analyze_qmt_roll_stage738_postentry_quality_add_real_ac as s738


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

MODEL_TAG = "stage739_postentry_quality_add_no_global_lock_v1"
OUTPUT_PREFIX = "qmt_roll_stage739_postentry_quality_add_no_global_lock"
LINE_ID = "futures_trend_winner_trade_forensics"

CANDIDATES: tuple[dict[str, str], ...] = (
    {
        "variant": "stage526_200k_force95_to80_post1_body60_qadd05_no_global_lock_stage739",
        "label": "C1 post1 body60 qadd0.5 no global add lock",
        "feature": "post1_body60_ratio_ge50",
    },
    {
        "variant": "stage526_200k_force95_to80_post1_directional_close_strength_qadd05_no_global_lock_stage739",
        "label": "C2 post1 directional close strength qadd0.5 no global add lock",
        "feature": "post1_avg_directional_close_strength_ge60",
    },
)
CANDIDATE_VARIANTS = tuple(item["variant"] for item in CANDIDATES)

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
COST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cost_stress_{MODEL_TAG}.csv"
COMPARISON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_comparison_{MODEL_TAG}.csv"
CURVES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv"
ANNUAL_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_annual_{MODEL_TAG}.csv"
MONTHLY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_monthly_{MODEL_TAG}.csv"
CHECKS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_checks_{MODEL_TAG}.csv"
ENTRY_RISK_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_risk_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"


def _patch_stage738_globals() -> None:
    s738.MODEL_TAG = MODEL_TAG
    s738.OUTPUT_PREFIX = OUTPUT_PREFIX
    s738.LINE_ID = LINE_ID
    s738.CANDIDATES = CANDIDATES
    s738.CANDIDATE_VARIANTS = CANDIDATE_VARIANTS
    s738.SUMMARY_PATH = SUMMARY_PATH
    s738.COST_PATH = COST_PATH
    s738.COMPARISON_PATH = COMPARISON_PATH
    s738.CURVES_PATH = CURVES_PATH
    s738.ANNUAL_PATH = ANNUAL_PATH
    s738.MONTHLY_PATH = MONTHLY_PATH
    s738.CHECKS_PATH = CHECKS_PATH
    s738.ENTRY_RISK_PATH = ENTRY_RISK_PATH
    s738.DECISION_PATH = DECISION_PATH
    s738.REPORT_PATH = REPORT_PATH
    s738.CHART_PATH = CHART_PATH


def _candidate_spec(metadata: dict, candidate: dict[str, str]):
    base = s660._official_spec(metadata)
    capital = replace(
        base.capital,
        variant=candidate["variant"],
        label=candidate["label"],
        note=(
            "Official Stage372 unchanged; post-entry quality confirmation layer uses floor(base_volume * 0.5). "
            "Unlike Stage738, the post-quality layer does not trigger the original global add-position profit lock."
        ),
    )
    overrides = {
        **base.overrides,
        "enable_post_entry_quality_add": True,
        "post_entry_quality_add_feature": candidate["feature"],
        "post_entry_quality_add_volume_multiplier": 0.5,
        "post_entry_quality_add_max_layers": 1,
        "post_entry_quality_add_use_day_extreme_stop": True,
        "post_entry_quality_add_triggers_add_profit_lock": False,
        "post_entry_quality_add_body_pct_min": 0.60,
        "post_entry_quality_add_body_ratio_min": 0.50,
        "post_entry_quality_add_directional_close_strength_min": 0.60,
        "post_entry_quality_add_short_wick_ratio_min": 0.50,
        "post_entry_quality_add_long_wick_ratio_max": 0.20,
        "post_entry_quality_add_adverse_wick_pct_max": 0.25,
        "streak_risk_multipliers": "1.0,1.0,1.0,0.1",
    }
    return replace(
        base,
        capital=capital,
        overrides=overrides,
        profile=f"official_stage372_post_entry_quality_add_no_global_lock_{candidate['feature']}_stage739",
    )


def main() -> None:
    _patch_stage738_globals()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    metadata = s513._metadata()
    base_spec = s660._official_spec(metadata)
    specs = [base_spec] + [_candidate_spec(metadata, item) for item in CANDIDATES]

    summary_rows = []
    cost_rows = []
    curve_frames = []
    entry_risk_frames = []
    for window_name, window_label, window_group, start, end in s707.WINDOWS:
        start_ts = pd.Timestamp(start)
        end_ts = pd.Timestamp(end)
        for spec in specs:
            print(f"[stage739] running {window_name} {spec.capital.variant}", flush=True)
            frame, forced_events, entry_risk = s738._run_independent_window(
                spec=spec,
                metadata=metadata,
                analysis_start=start_ts,
                analysis_end=end_ts,
            )
            if not entry_risk.empty:
                entry_risk["window_name"] = window_name
                entry_risk_frames.append(entry_risk)
            row, curve, costs = s738._metric_row_with_counts(
                frame,
                spec=spec,
                window_name=window_name,
                window_label=window_label,
                window_group=window_group,
                forced_events=forced_events,
            )
            summary_rows.append(row)
            curve_frames.append(curve)
            cost_rows.extend(costs)

    summary = pd.DataFrame(summary_rows)
    curves = pd.concat(curve_frames, ignore_index=True, sort=False)
    cost = pd.DataFrame(cost_rows)
    comparison = s738._comparison(summary, cost)
    annual, monthly = s738._annual_monthly(curves)
    checks = s738._check_rows(summary, comparison)
    decision = s738._decision(summary, comparison, checks)

    s738._plot(curves)
    s738._write_report(summary, comparison, cost, annual, checks, decision)

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    cost.to_csv(COST_PATH, index=False, encoding="utf-8-sig")
    comparison.to_csv(COMPARISON_PATH, index=False, encoding="utf-8-sig")
    curves.to_csv(CURVES_PATH, index=False, encoding="utf-8-sig")
    annual.to_csv(ANNUAL_PATH, index=False, encoding="utf-8-sig")
    monthly.to_csv(MONTHLY_PATH, index=False, encoding="utf-8-sig")
    checks.to_csv(CHECKS_PATH, index=False, encoding="utf-8-sig")
    if entry_risk_frames:
        pd.concat(entry_risk_frames, ignore_index=True, sort=False).to_csv(
            ENTRY_RISK_PATH,
            index=False,
            encoding="utf-8-sig",
        )
    DECISION_PATH.write_text(json.dumps(s738._json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(s738._json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
