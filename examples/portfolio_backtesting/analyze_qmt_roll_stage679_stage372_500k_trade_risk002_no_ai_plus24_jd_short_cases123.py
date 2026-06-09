from __future__ import annotations

import analyze_qmt_roll_stage674_stage372_500k_trade_risk001_ni_ag_sc_p as s674
import analyze_qmt_roll_stage678_stage372_500k_trade_risk002_no_ai_plus24_jd as s678
from qmt_roll_portfolio_strategy import QmtRollPortfolioStrategy


MODEL_TAG = "stage679_stage372_500k_trade_risk002_no_ai_plus24_jd_short_cases123_v1"
OUTPUT_PREFIX = "qmt_roll_stage679_stage372_500k_trade_risk002_no_ai_plus24_jd_short_cases123"

ALLOWED_SHORT_SIGNALS = frozenset({"short_case1a", "short_case2", "short_case3"})


def _configure_stage679() -> None:
    s678._configure_stage678()

    s674.MODEL_TAG = MODEL_TAG
    s674.OUTPUT_PREFIX = OUTPUT_PREFIX
    s674.STAGE_NAME = "Stage391"
    s674.SCRIPT_STAGE = "Stage679"
    s674.REPORT_TITLE = "# Stage679 50万 单笔交易风险资金2% + plus24 鸡蛋 no-AI 放宽空头case审计"
    s674.RUNNER_REPORT_TITLE = "# Stage679 50万 单笔风险2% plus24 鸡蛋 no-AI short_case1/2/3审计"
    s674.RISK_COMPARE_NAME = "no_ai_plus24_jd_short_cases123_risk002_maxpos4_vs_risk004_maxpos4"
    s674.MAXPOS_COMPARE_NAME = "no_ai_plus24_jd_short_cases123_risk002_maxpos24_vs_risk002_maxpos4"
    s674.DECISION_WATCH_NAME = "stage372_500k_trade_risk002_no_ai_plus24_jd_short_cases123_watch_not_auto_promote"
    s674.DECISION_REJECT_NAME = "stage372_500k_trade_risk002_no_ai_plus24_jd_short_cases123_rejected"

    s674.TARGET_TRADE_RISK_RATIO = 0.02
    s674.PLUS_COMBO_STRATEGY = "stage679_stage372_500k_trade_risk002_no_ai_plus24_jd_short_cases123_entry_filter"
    s674.SOURCE_LABEL = "stage679_500k_trade_risk002_no_ai_plus24_jd_short_cases123"
    s674.SCORE_TYPE = "stage679_no_ai_short_case1a_2_3_enabled_plus24_jd"
    s674.BASE_VARIANT = "stage372_500k_trade_risk004_no_ai_plus24_jd_short_cases123_maxpos4"
    s674.TARGET_VARIANT = "stage372_500k_trade_risk002_no_ai_plus24_jd_short_cases123_maxpos4"
    s674.TARGET_NO_MAXPOS_VARIANT = "stage372_500k_trade_risk002_no_ai_plus24_jd_short_cases123_maxpos24"

    s674.GENERATED_DIR = s674.OUTPUT_DIR / "stage679_generated_inputs"
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


def _allow_short_cases123(self: QmtRollPortfolioStrategy, signal: str) -> bool:
    return signal in ALLOWED_SHORT_SIGNALS


def main() -> None:
    _configure_stage679()
    original_plus_spec = s674.s667._plus_combo_500k_spec
    original_can_open_short_signal = QmtRollPortfolioStrategy._can_open_short_signal
    try:
        s674.s667._plus_combo_500k_spec = s678._no_ai_plus_combo_500k_spec
        QmtRollPortfolioStrategy._can_open_short_signal = _allow_short_cases123
        s674.main()
    finally:
        s674.s667._plus_combo_500k_spec = original_plus_spec
        QmtRollPortfolioStrategy._can_open_short_signal = original_can_open_short_signal


if __name__ == "__main__":
    main()
