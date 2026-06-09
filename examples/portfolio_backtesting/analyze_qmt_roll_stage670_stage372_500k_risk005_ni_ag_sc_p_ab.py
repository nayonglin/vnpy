from __future__ import annotations

from pathlib import Path

import analyze_qmt_roll_stage667_stage372_500k_risk005_ni_ag_ab as s667


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

MODEL_TAG = "stage670_stage372_500k_risk005_ni_ag_sc_p_ab_v1"
OUTPUT_PREFIX = "qmt_roll_stage670_stage372_500k_risk005_ni_ag_sc_p_ab"
EXTRA_PRODUCTS = ("ni.SHFE", "ag.SHFE", "sc.INE", "p.DCE")
PLUS_COMBO_STRATEGY = "stage670_stage372_500k_risk005_plus_ni_ag_sc_p_entry_filter"
VARIANT_BASE = "stage372_500k_risk005_no_ni_ag_sc_p"
VARIANT_PLUS_COMBO = "stage372_500k_risk005_plus_ni_ag_sc_p"

GENERATED_DIR = OUTPUT_DIR / "stage670_generated_inputs"


def _configure() -> None:
    s667.MODEL_TAG = MODEL_TAG
    s667.OUTPUT_PREFIX = OUTPUT_PREFIX
    s667.EXTRA_PRODUCTS = EXTRA_PRODUCTS
    s667.PLUS_COMBO_STRATEGY = PLUS_COMBO_STRATEGY
    s667.SOURCE_LABEL = "stage670_500k_risk005_plus_ni_ag_sc_p_fixed_add_four"
    s667.SCORE_TYPE = "stage670_fixed_add_four_ni_ag_sc_p"
    s667.STAGE_NAME = "Stage382"
    s667.SCRIPT_STAGE = "Stage670"
    s667.REPORT_TITLE = "# Stage670 50万 risk0.05 同时加 ni/ag/sc/p 多周期审计"
    s667.REJECT_DECISION = "plus_ni_ag_sc_p_rejected"
    s667.WATCH_DECISION = "plus_ni_ag_sc_p_watch_not_auto_promote"
    s667.PASS_DECISION = "plus_ni_ag_sc_p_passes_first_gate"
    s667.VARIANT_BASE = VARIANT_BASE
    s667.VARIANT_PLUS_COMBO = VARIANT_PLUS_COMBO
    s667.GENERATED_DIR = GENERATED_DIR
    s667.UNIVERSE_PLUS_COMBO_PATH = GENERATED_DIR / f"{OUTPUT_PREFIX}_plus_ni_ag_sc_p_universe_{MODEL_TAG}.csv"
    s667.HIST_ELIGIBILITY_PLUS_COMBO_PATH = GENERATED_DIR / f"{OUTPUT_PREFIX}_historical_plus_ni_ag_sc_p_eligibility_{MODEL_TAG}.csv"
    s667.LATEST_ELIGIBILITY_PLUS_COMBO_PATH = GENERATED_DIR / f"{OUTPUT_PREFIX}_latest_plus_ni_ag_sc_p_eligibility_{MODEL_TAG}.csv"
    s667.SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
    s667.COST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cost_stress_{MODEL_TAG}.csv"
    s667.COMPARISON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_comparison_{MODEL_TAG}.csv"
    s667.ROLLING_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_rolling_{MODEL_TAG}.csv"
    s667.ANNUAL_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_annual_{MODEL_TAG}.csv"
    s667.MONTHLY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_monthly_{MODEL_TAG}.csv"
    s667.CURVES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv"
    s667.EXTRA_ACTIVITY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_extra_activity_{MODEL_TAG}.csv"
    s667.CHECKS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_checks_{MODEL_TAG}.csv"
    s667.DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
    s667.REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
    s667.CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"


def main() -> None:
    _configure()
    s667.main()


if __name__ == "__main__":
    main()
