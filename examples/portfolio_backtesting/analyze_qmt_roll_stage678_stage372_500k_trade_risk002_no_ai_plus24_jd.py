from __future__ import annotations

from dataclasses import replace

import analyze_qmt_roll_stage674_stage372_500k_trade_risk001_ni_ag_sc_p as s674


MODEL_TAG = "stage678_stage372_500k_trade_risk002_no_ai_plus24_jd_v1"
OUTPUT_PREFIX = "qmt_roll_stage678_stage372_500k_trade_risk002_no_ai_plus24_jd"

EXTRA_PRODUCTS = ("ni.SHFE", "ag.SHFE", "sc.INE", "p.DCE", "jd.DCE")
NO_AI_PLUS24_STRATEGY = "stage678_stage372_500k_trade_risk002_no_ai_plus24_jd_entry_filter"
NO_AI_SCORE_TYPE = "stage678_no_ai_product_pool_filter_disabled_plus24_jd"


def _configure_stage678() -> None:
    s674.MODEL_TAG = MODEL_TAG
    s674.OUTPUT_PREFIX = OUTPUT_PREFIX
    s674.STAGE_NAME = "Stage390"
    s674.SCRIPT_STAGE = "Stage678"
    s674.REPORT_TITLE = "# Stage678 50万 单笔交易风险资金2% + plus24 鸡蛋 no-AI 选品审计"
    s674.RUNNER_REPORT_TITLE = "# Stage678 50万 单笔风险2% plus24 鸡蛋 no-AI 选品审计"
    s674.RISK_COMPARE_NAME = "no_ai_plus24_jd_risk002_maxpos4_vs_risk004_maxpos4"
    s674.MAXPOS_COMPARE_NAME = "no_ai_plus24_jd_risk002_maxpos24_vs_risk002_maxpos4"
    s674.DECISION_WATCH_NAME = "stage372_500k_trade_risk002_no_ai_plus24_jd_watch_not_auto_promote"
    s674.DECISION_REJECT_NAME = "stage372_500k_trade_risk002_no_ai_plus24_jd_rejected"

    s674.EXTRA_PRODUCTS = EXTRA_PRODUCTS
    s674.TARGET_TRADE_RISK_RATIO = 0.02
    s674.PLUS_COMBO_STRATEGY = NO_AI_PLUS24_STRATEGY
    s674.SOURCE_LABEL = "stage678_500k_trade_risk002_no_ai_plus24_jd"
    s674.SCORE_TYPE = NO_AI_SCORE_TYPE
    s674.BASE_VARIANT = "stage372_500k_trade_risk004_no_ai_plus24_jd_maxpos4"
    s674.TARGET_VARIANT = "stage372_500k_trade_risk002_no_ai_plus24_jd_maxpos4"
    s674.TARGET_NO_MAXPOS_VARIANT = "stage372_500k_trade_risk002_no_ai_plus24_jd_maxpos24"

    s674.GENERATED_DIR = s674.OUTPUT_DIR / "stage678_generated_inputs"
    s674.UNIVERSE_PLUS_PATH = s674.GENERATED_DIR / f"{OUTPUT_PREFIX}_plus24_jd_universe_{MODEL_TAG}.csv"
    s674.HIST_ELIGIBILITY_PLUS_PATH = (
        s674.GENERATED_DIR / f"{OUTPUT_PREFIX}_historical_unused_eligibility_{MODEL_TAG}.csv"
    )
    s674.LATEST_ELIGIBILITY_PLUS_PATH = (
        s674.GENERATED_DIR / f"{OUTPUT_PREFIX}_latest_unused_eligibility_{MODEL_TAG}.csv"
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


def _no_ai_plus_combo_500k_spec(metadata):
    official = s674.s667.s666.s660._official_spec(metadata)
    overrides = {
        **official.overrides,
        "product_universe_csv_path": str(s674.UNIVERSE_PLUS_PATH),
        "enable_ai_product_pool_filter": False,
        "ai_product_pool_eligibility_path": "",
        "ai_product_pool_strategy": "",
    }
    capital = replace(
        official.capital,
        note=(
            "Stage678: disable the AI product pool filter entirely; all products in the plus24 universe "
            "are eligible subject only to the core trend logic, risk sizing, and maxpos constraints."
        ),
    )
    return replace(official, capital=capital, overrides=overrides, profile="stage678_no_ai_plus24_jd")


def main() -> None:
    _configure_stage678()
    original_plus_spec = s674.s667._plus_combo_500k_spec
    try:
        s674.s667._plus_combo_500k_spec = _no_ai_plus_combo_500k_spec
        s674.main()
    finally:
        s674.s667._plus_combo_500k_spec = original_plus_spec


if __name__ == "__main__":
    main()
