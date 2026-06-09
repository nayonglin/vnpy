from __future__ import annotations

import analyze_qmt_roll_stage672_stage372_500k_risk005_ni_ag_sc_p_no_maxpos as s672


def _configure() -> None:
    s672.MODEL_TAG = "stage673_stage372_500k_risk001_ni_ag_sc_p_no_maxpos_v1"
    s672.OUTPUT_PREFIX = "qmt_roll_stage673_stage372_500k_risk001_ni_ag_sc_p_no_maxpos"
    s672.RISK_MULTIPLIER = 0.01
    s672.PLUS_COMBO_STRATEGY = "stage673_stage372_500k_risk001_plus_ni_ag_sc_p_no_maxpos_entry_filter"
    s672.SOURCE_LABEL = "stage673_500k_risk001_plus_ni_ag_sc_p_no_maxpos"
    s672.SCORE_TYPE = "stage673_fixed_add_four_ni_ag_sc_p_no_maxpos"
    s672.STAGE_NAME = "Stage385"
    s672.SCRIPT_STAGE = "Stage673"
    s672.RISK_LABEL = "risk001"
    s672.REPORT_TITLE = "# Stage673 50万 risk0.01 加 ni/ag/sc/p 后放宽持仓限制审计"
    s672.CHART_TITLE = "Stage673 500k risk001 + ni/ag/sc/p maxpos4 vs maxpos23"
    s672.REJECT_DECISION = "stage372_500k_risk001_plus_four_no_maxpos_rejected"
    s672.WATCH_DECISION = "stage372_500k_risk001_plus_four_no_maxpos_watch_not_auto_promote"
    s672.PASS_DECISION = "stage372_500k_risk001_plus_four_no_maxpos_passes_first_gate"

    s672.BASE_VARIANT = "stage372_500k_risk001_plus_ni_ag_sc_p_maxpos4"
    s672.CANDIDATE_VARIANT = "stage372_500k_risk001_plus_ni_ag_sc_p_maxpos23"

    s672.GENERATED_DIR = s672.OUTPUT_DIR / "stage673_generated_inputs"
    s672.UNIVERSE_PLUS_PATH = (
        s672.GENERATED_DIR / f"{s672.OUTPUT_PREFIX}_plus_ni_ag_sc_p_universe_{s672.MODEL_TAG}.csv"
    )
    s672.HIST_ELIGIBILITY_PLUS_PATH = (
        s672.GENERATED_DIR / f"{s672.OUTPUT_PREFIX}_historical_plus_ni_ag_sc_p_eligibility_{s672.MODEL_TAG}.csv"
    )
    s672.LATEST_ELIGIBILITY_PLUS_PATH = (
        s672.GENERATED_DIR / f"{s672.OUTPUT_PREFIX}_latest_plus_ni_ag_sc_p_eligibility_{s672.MODEL_TAG}.csv"
    )

    s672.SUMMARY_PATH = s672.OUTPUT_DIR / f"{s672.OUTPUT_PREFIX}_summary_{s672.MODEL_TAG}.csv"
    s672.COST_PATH = s672.OUTPUT_DIR / f"{s672.OUTPUT_PREFIX}_cost_stress_{s672.MODEL_TAG}.csv"
    s672.COMPARISON_PATH = s672.OUTPUT_DIR / f"{s672.OUTPUT_PREFIX}_comparison_{s672.MODEL_TAG}.csv"
    s672.ROLLING_PATH = s672.OUTPUT_DIR / f"{s672.OUTPUT_PREFIX}_rolling_{s672.MODEL_TAG}.csv"
    s672.ANNUAL_PATH = s672.OUTPUT_DIR / f"{s672.OUTPUT_PREFIX}_annual_{s672.MODEL_TAG}.csv"
    s672.MONTHLY_PATH = s672.OUTPUT_DIR / f"{s672.OUTPUT_PREFIX}_monthly_{s672.MODEL_TAG}.csv"
    s672.MARGIN_PATH = s672.OUTPUT_DIR / f"{s672.OUTPUT_PREFIX}_margin_usage_{s672.MODEL_TAG}.csv"
    s672.CURVES_PATH = s672.OUTPUT_DIR / f"{s672.OUTPUT_PREFIX}_curves_{s672.MODEL_TAG}.csv"
    s672.ACTIVITY_PATH = s672.OUTPUT_DIR / f"{s672.OUTPUT_PREFIX}_extra_activity_{s672.MODEL_TAG}.csv"
    s672.CHECKS_PATH = s672.OUTPUT_DIR / f"{s672.OUTPUT_PREFIX}_checks_{s672.MODEL_TAG}.csv"
    s672.REPORT_PATH = s672.OUTPUT_DIR / f"{s672.OUTPUT_PREFIX}_report_{s672.MODEL_TAG}.md"
    s672.CHART_PATH = s672.OUTPUT_DIR / f"{s672.OUTPUT_PREFIX}_chart_{s672.MODEL_TAG}.png"
    s672.DECISION_PATH = s672.OUTPUT_DIR / f"{s672.OUTPUT_PREFIX}_decision_{s672.MODEL_TAG}.json"


def main() -> None:
    _configure()
    s672.main()


if __name__ == "__main__":
    main()
