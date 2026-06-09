from __future__ import annotations

import analyze_qmt_roll_stage674_stage372_500k_trade_risk001_ni_ag_sc_p as s674


MODEL_TAG = "stage675_stage372_500k_trade_risk002_ni_ag_sc_p_v1"
OUTPUT_PREFIX = "qmt_roll_stage675_stage372_500k_trade_risk002_ni_ag_sc_p"


def _configure_stage675() -> None:
    s674.MODEL_TAG = MODEL_TAG
    s674.OUTPUT_PREFIX = OUTPUT_PREFIX
    s674.STAGE_NAME = "Stage387"
    s674.SCRIPT_STAGE = "Stage675"
    s674.REPORT_TITLE = "# Stage675 50万 单笔交易风险资金2% + ni/ag/sc/p 审计"
    s674.RUNNER_REPORT_TITLE = "# Stage675 50万 单笔风险2% 加 ni/ag/sc/p 审计"
    s674.RISK_COMPARE_NAME = "risk002_maxpos4_vs_risk004_maxpos4"
    s674.MAXPOS_COMPARE_NAME = "risk002_maxpos23_vs_risk002_maxpos4"
    s674.DECISION_WATCH_NAME = "stage372_500k_trade_risk002_plus_four_watch_not_auto_promote"
    s674.DECISION_REJECT_NAME = "stage372_500k_trade_risk002_plus_four_rejected"

    s674.TARGET_TRADE_RISK_RATIO = 0.02
    s674.PLUS_COMBO_STRATEGY = "stage675_stage372_500k_trade_risk002_plus_ni_ag_sc_p_entry_filter"
    s674.SOURCE_LABEL = "stage675_500k_trade_risk002_plus_ni_ag_sc_p"
    s674.SCORE_TYPE = "stage675_fixed_add_four_ni_ag_sc_p_trade_risk002"
    s674.TARGET_VARIANT = "stage372_500k_trade_risk002_plus_ni_ag_sc_p_maxpos4"
    s674.TARGET_NO_MAXPOS_VARIANT = "stage372_500k_trade_risk002_plus_ni_ag_sc_p_maxpos23"

    s674.GENERATED_DIR = s674.OUTPUT_DIR / "stage675_generated_inputs"
    s674.UNIVERSE_PLUS_PATH = (
        s674.GENERATED_DIR / f"{OUTPUT_PREFIX}_plus_ni_ag_sc_p_universe_{MODEL_TAG}.csv"
    )
    s674.HIST_ELIGIBILITY_PLUS_PATH = (
        s674.GENERATED_DIR / f"{OUTPUT_PREFIX}_historical_plus_ni_ag_sc_p_eligibility_{MODEL_TAG}.csv"
    )
    s674.LATEST_ELIGIBILITY_PLUS_PATH = (
        s674.GENERATED_DIR / f"{OUTPUT_PREFIX}_latest_plus_ni_ag_sc_p_eligibility_{MODEL_TAG}.csv"
    )

    s674.SUMMARY_PATH = s674.OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
    s674.COST_PATH = s674.OUTPUT_DIR / f"{OUTPUT_PREFIX}_cost_stress_{MODEL_TAG}.csv"
    s674.COMPARISON_PATH = s674.OUTPUT_DIR / f"{OUTPUT_PREFIX}_comparison_{MODEL_TAG}.csv"
    s674.ROLLING_PATH = s674.OUTPUT_DIR / f"{OUTPUT_PREFIX}_rolling_{MODEL_TAG}.csv"
    s674.ANNUAL_PATH = s674.OUTPUT_DIR / f"{OUTPUT_PREFIX}_annual_{MODEL_TAG}.csv"
    s674.MONTHLY_PATH = s674.OUTPUT_DIR / f"{OUTPUT_PREFIX}_monthly_{MODEL_TAG}.csv"
    s674.MARGIN_PATH = s674.OUTPUT_DIR / f"{OUTPUT_PREFIX}_margin_usage_{MODEL_TAG}.csv"
    s674.CURVES_PATH = s674.OUTPUT_DIR / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv"
    s674.ACTIVITY_PATH = s674.OUTPUT_DIR / f"{OUTPUT_PREFIX}_extra_activity_{MODEL_TAG}.csv"
    s674.CHECKS_PATH = s674.OUTPUT_DIR / f"{OUTPUT_PREFIX}_checks_{MODEL_TAG}.csv"
    s674.REPORT_PATH = s674.OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
    s674.DECISION_PATH = s674.OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"


def main() -> None:
    _configure_stage675()
    s674.main()


if __name__ == "__main__":
    main()
