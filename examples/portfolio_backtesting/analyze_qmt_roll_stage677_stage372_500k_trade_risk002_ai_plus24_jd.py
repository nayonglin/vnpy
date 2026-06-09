from __future__ import annotations

import analyze_qmt_roll_stage674_stage372_500k_trade_risk001_ni_ag_sc_p as s674
import analyze_qmt_roll_stage676_stage372_500k_trade_risk002_ai_plus23 as s676


MODEL_TAG = "stage677_stage372_500k_trade_risk002_ai_plus24_jd_v1"
OUTPUT_PREFIX = "qmt_roll_stage677_stage372_500k_trade_risk002_ai_plus24_jd"

EXTRA_PRODUCTS = ("ni.SHFE", "ag.SHFE", "sc.INE", "p.DCE", "jd.DCE")
AI_PLUS24_STRATEGY = "stage677_stage372_500k_trade_risk002_ai_plus24_jd_entry_filter"
AI_PLUS24_SCORE_TYPE = "stage677_full_market_ai_probability_plus24_jd"
AI_PLUS24_FU_SCORE_TYPE = "stage677_ai_top8_plus_fixed_fu_satellite"


def _configure_stage677() -> None:
    s676.MODEL_TAG = MODEL_TAG
    s676.OUTPUT_PREFIX = OUTPUT_PREFIX
    s676.AI_PLUS23_STRATEGY = AI_PLUS24_STRATEGY
    s676.AI_PLUS23_SCORE_TYPE = AI_PLUS24_SCORE_TYPE
    s676.AI_PLUS23_FU_SCORE_TYPE = AI_PLUS24_FU_SCORE_TYPE
    s676._configure_stage676()

    s674.MODEL_TAG = MODEL_TAG
    s674.OUTPUT_PREFIX = OUTPUT_PREFIX
    s674.STAGE_NAME = "Stage389"
    s674.SCRIPT_STAGE = "Stage677"
    s674.REPORT_TITLE = "# Stage677 50万 单笔交易风险资金2% + plus24 鸡蛋 AI选品审计"
    s674.RUNNER_REPORT_TITLE = "# Stage677 50万 单笔风险2% plus24 鸡蛋 AI选品审计"
    s674.RISK_COMPARE_NAME = "ai_plus24_jd_risk002_maxpos4_vs_risk004_maxpos4"
    s674.MAXPOS_COMPARE_NAME = "ai_plus24_jd_risk002_maxpos24_vs_risk002_maxpos4"
    s674.DECISION_WATCH_NAME = "stage372_500k_trade_risk002_ai_plus24_jd_watch_not_auto_promote"
    s674.DECISION_REJECT_NAME = "stage372_500k_trade_risk002_ai_plus24_jd_rejected"

    s674.EXTRA_PRODUCTS = EXTRA_PRODUCTS
    s674.TARGET_TRADE_RISK_RATIO = 0.02
    s674.PLUS_COMBO_STRATEGY = AI_PLUS24_STRATEGY
    s674.SOURCE_LABEL = "stage677_500k_trade_risk002_ai_plus24_jd"
    s674.SCORE_TYPE = AI_PLUS24_SCORE_TYPE
    s674.BASE_VARIANT = "stage372_500k_trade_risk004_ai_plus24_jd_maxpos4"
    s674.TARGET_VARIANT = "stage372_500k_trade_risk002_ai_plus24_jd_maxpos4"
    s674.TARGET_NO_MAXPOS_VARIANT = "stage372_500k_trade_risk002_ai_plus24_jd_maxpos24"

    s674.GENERATED_DIR = s674.OUTPUT_DIR / "stage677_generated_inputs"
    s674.UNIVERSE_PLUS_PATH = s674.GENERATED_DIR / f"{OUTPUT_PREFIX}_plus24_jd_universe_{MODEL_TAG}.csv"
    s674.HIST_ELIGIBILITY_PLUS_PATH = (
        s674.GENERATED_DIR / f"{OUTPUT_PREFIX}_historical_ai_plus24_jd_eligibility_{MODEL_TAG}.csv"
    )
    s674.LATEST_ELIGIBILITY_PLUS_PATH = (
        s674.GENERATED_DIR / f"{OUTPUT_PREFIX}_latest_ai_plus24_jd_eligibility_{MODEL_TAG}.csv"
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
    _configure_stage677()
    original_prepare = s674.s667._prepare_inputs
    try:
        s674.s667._prepare_inputs = s676._prepare_inputs_ai_plus23
        s674.main()
    finally:
        s674.s667._prepare_inputs = original_prepare


if __name__ == "__main__":
    main()
