from __future__ import annotations

from dataclasses import replace
from datetime import datetime
import json
from pathlib import Path
from typing import Any

import pandas as pd

import analyze_qmt_roll_stage707_recovery_all_cases_multiperiod as s707
import analyze_qmt_roll_stage660_stage653_multiperiod_live_audit as s660
import analyze_qmt_roll_stage650_stage526_200k_capital_reality_check as s650
import analyze_qmt_roll_stage653_stage526_200k_forced_margin_deleverage as s653


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

MODEL_TAG = "stage709_recovery_all_cases_dd15_multiperiod_v1"
OUTPUT_PREFIX = "qmt_roll_stage709_recovery_all_cases_dd15_multiperiod"
LINE_ID = "futures_trend_drawdown30_preserve_return"

BASE_VARIANT = s707.BASE_VARIANT
CANDIDATE_VARIANT = "stage526_200k_force95_to80_recovery_sleeve_r080_pc25_maxpos4_recovery_all_cases_dd15_stage709"
RECOVERY_SIGNALS = s707.RECOVERY_SIGNALS
MAX_RECOVERY_DRAWDOWN = 0.15

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
COST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cost_stress_{MODEL_TAG}.csv"
COMPARISON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_comparison_{MODEL_TAG}.csv"
CURVES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv"
ANNUAL_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_annual_{MODEL_TAG}.csv"
MONTHLY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_monthly_{MODEL_TAG}.csv"
CHECKS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_checks_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"


def _json_safe(value: Any) -> Any:
    return s650._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s650._md_table(frame, max_rows=max_rows)


def _reconfigure_stage707_helpers() -> None:
    s707.MODEL_TAG = MODEL_TAG
    s707.OUTPUT_PREFIX = OUTPUT_PREFIX
    s707.CANDIDATE_VARIANT = CANDIDATE_VARIANT
    s707.RECOVERY_SIGNALS = RECOVERY_SIGNALS
    s707.SUMMARY_PATH = SUMMARY_PATH
    s707.COST_PATH = COST_PATH
    s707.COMPARISON_PATH = COMPARISON_PATH
    s707.CURVES_PATH = CURVES_PATH
    s707.ANNUAL_PATH = ANNUAL_PATH
    s707.MONTHLY_PATH = MONTHLY_PATH
    s707.CHECKS_PATH = CHECKS_PATH
    s707.DECISION_PATH = DECISION_PATH
    s707.REPORT_PATH = REPORT_PATH
    s707.CHART_PATH = CHART_PATH


def _candidate_spec(metadata: dict[str, Any]) -> s653.ForcedVariant:
    base = s660._official_spec(metadata)
    capital = replace(
        base.capital,
        variant=CANDIDATE_VARIANT,
        label="Stage709 recovery all cases only above -15pct DD",
        note=(
            "Official Stage372 unchanged except clean-book recovery lift is allowed for all native trend entry "
            "cases only when account drawdown is not deeper than 15%."
        ),
    )
    overrides = {
        **base.overrides,
        "enable_streak_entry_structure_risk_recovery": True,
        "streak_entry_structure_recovery_signals": RECOVERY_SIGNALS,
        "streak_entry_structure_recovery_min_multiplier": 1.0,
        "streak_entry_structure_recovery_require_flat_portfolio": True,
        "streak_entry_structure_recovery_max_same_direction_corr": 0.30,
        "streak_entry_structure_recovery_require_rsi_confirmation": False,
        "streak_entry_structure_recovery_max_portfolio_drawdown_pct": MAX_RECOVERY_DRAWDOWN,
        "streak_risk_multipliers": "1.0,1.0,1.0,0.1",
    }
    return replace(base, capital=capital, overrides=overrides, profile="official_stage372_recovery_all_cases_dd15_stage709")


def _write_report(
    summary: pd.DataFrame,
    comparison: pd.DataFrame,
    cost: pd.DataFrame,
    annual: pd.DataFrame,
    checks: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    key_cols = [
        "window_name",
        "return_retention_pct",
        "base_total_return_pct",
        "candidate_total_return_pct",
        "base_max_dd_pct",
        "candidate_max_dd_pct",
        "delta_max_dd_pct",
        "base_sharpe",
        "candidate_sharpe",
        "delta_sharpe",
    ]
    lines = [
        "# Stage423 / Script709 Recovery All Cases With DD15 Gate",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        f"- line_id：`{LINE_ID}`",
        "- A：当前正式 Stage372/20w，`case1a` 恢复规则。",
        "- C：保持 `streak_risk_multipliers=1,1,1,0.1`，把 clean-book recovery lift 扩到所有原生趋势入场 case，但仅在账户回撤不超过 `15%` 时允许恢复。",
        "- 不修改正式配置、不连接 CTP、不调用下单。",
        "",
        "## Checks",
        "",
        _md_table(checks),
        "",
        "## Comparison",
        "",
        _md_table(comparison[key_cols], max_rows=40),
        "",
        "## Summary",
        "",
        _md_table(summary, max_rows=90),
        "",
        "## Cost Stress",
        "",
        _md_table(cost, max_rows=140),
        "",
        "## Annual Full Path",
        "",
        _md_table(annual, max_rows=80),
        "",
        "## Decision",
        "",
        f"- 决策：`{decision['decision']}`",
        f"- hard_fail_checks：`{', '.join(decision['hard_fail_checks']) or '无'}`",
        f"- watch_checks：`{', '.join(decision['watch_checks']) or '无'}`",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _decision(summary: pd.DataFrame, comparison: pd.DataFrame, cost: pd.DataFrame, checks: pd.DataFrame) -> dict[str, Any]:
    base_decision = s707._decision(summary, comparison, cost, checks)
    base_decision["stage"] = "Stage423"
    base_decision["script_stage"] = "Stage709"
    base_decision["model_tag"] = MODEL_TAG
    base_decision["candidate"] = CANDIDATE_VARIANT
    change = dict(base_decision.get("change", {}))
    change.update(
        {
            "candidate_hypothesis": (
                "Allow clean-book recovery across native trend entry cases, but keep the hard 0.1 defense "
                "during deeper account drawdowns. This preserves right-tail recovery only when the account "
                "is not already in a severe drawdown."
            ),
            "recovery_max_portfolio_drawdown_pct": MAX_RECOVERY_DRAWDOWN,
            "streak_risk_multipliers_after": "1.0,1.0,1.0,0.1",
            "official_config_changed": False,
            "ctp_connected": False,
            "order_api_called": False,
        }
    )
    base_decision["change"] = change
    hard_fail = list(base_decision.get("hard_fail_checks", []))
    base_decision["decision"] = (
        "recovery_all_cases_dd15_next_validation" if not hard_fail else "recovery_all_cases_dd15_not_promoted"
    )
    return base_decision


def main() -> None:
    _reconfigure_stage707_helpers()
    metadata = s707.s513._metadata()
    specs = [s660._official_spec(metadata), _candidate_spec(metadata)]

    summary_rows: list[dict[str, Any]] = []
    cost_rows: list[dict[str, Any]] = []
    curve_frames: list[pd.DataFrame] = []
    for window_name, window_label, window_group, start, end in s707.WINDOWS:
        start_ts = pd.Timestamp(start)
        end_ts = pd.Timestamp(end)
        for spec in specs:
            print(f"[stage709] running {window_name} {spec.capital.variant}", flush=True)
            frame, forced_events = s660._run_independent_window(
                spec=spec,
                metadata=metadata,
                analysis_start=start_ts,
                analysis_end=end_ts,
            )
            row, curve, costs = s707._metric_row(
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
    comparison = s707._comparison(summary, cost)
    annual, monthly = s707._annual_monthly(curves)
    checks = s707._check_rows(summary, comparison, cost)
    decision = _decision(summary, comparison, cost, checks)

    s707._plot(curves)
    _write_report(summary, comparison, cost, annual, checks, decision)

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    cost.to_csv(COST_PATH, index=False, encoding="utf-8-sig")
    comparison.to_csv(COMPARISON_PATH, index=False, encoding="utf-8-sig")
    curves.to_csv(CURVES_PATH, index=False, encoding="utf-8-sig")
    annual.to_csv(ANNUAL_PATH, index=False, encoding="utf-8-sig")
    monthly.to_csv(MONTHLY_PATH, index=False, encoding="utf-8-sig")
    checks.to_csv(CHECKS_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
