from __future__ import annotations

import pandas as pd

import analyze_qmt_roll_stage674_stage372_500k_trade_risk001_ni_ag_sc_p as s674
from analyze_qmt_roll_ai_product_suitability_full_market_walkforward import PREDICTIONS_OUTPUT_PATH
from analyze_qmt_roll_ai_product_suitability_walkforward import PROBABILITY_COLUMN, SIMPLE_SCORE_COLUMN


MODEL_TAG = "stage676_stage372_500k_trade_risk002_ai_plus23_v1"
OUTPUT_PREFIX = "qmt_roll_stage676_stage372_500k_trade_risk002_ai_plus23"

TOP_N_AI = 8
FU_PRODUCT = "fu.SHFE"
AI_PLUS23_STRATEGY = "stage676_stage372_500k_trade_risk002_ai_plus23_entry_filter"
AI_PLUS23_SCORE_TYPE = "stage676_full_market_ai_probability_plus23"
AI_PLUS23_FU_SCORE_TYPE = "stage676_ai_top8_plus_fixed_fu_satellite"


def _configure_stage676() -> None:
    s674.MODEL_TAG = MODEL_TAG
    s674.OUTPUT_PREFIX = OUTPUT_PREFIX
    s674.STAGE_NAME = "Stage388"
    s674.SCRIPT_STAGE = "Stage676"
    s674.REPORT_TITLE = "# Stage676 50万 单笔交易风险资金2% + plus23 AI选品审计"
    s674.RUNNER_REPORT_TITLE = "# Stage676 50万 单笔风险2% plus23 AI选品审计"
    s674.RISK_COMPARE_NAME = "ai_plus23_risk002_maxpos4_vs_risk004_maxpos4"
    s674.MAXPOS_COMPARE_NAME = "ai_plus23_risk002_maxpos23_vs_risk002_maxpos4"
    s674.DECISION_WATCH_NAME = "stage372_500k_trade_risk002_ai_plus23_watch_not_auto_promote"
    s674.DECISION_REJECT_NAME = "stage372_500k_trade_risk002_ai_plus23_rejected"

    s674.TARGET_TRADE_RISK_RATIO = 0.02
    s674.PLUS_COMBO_STRATEGY = AI_PLUS23_STRATEGY
    s674.SOURCE_LABEL = "stage676_500k_trade_risk002_ai_plus23"
    s674.SCORE_TYPE = AI_PLUS23_SCORE_TYPE
    s674.BASE_VARIANT = "stage372_500k_trade_risk004_ai_plus23_maxpos4"
    s674.TARGET_VARIANT = "stage372_500k_trade_risk002_ai_plus23_maxpos4"
    s674.TARGET_NO_MAXPOS_VARIANT = "stage372_500k_trade_risk002_ai_plus23_maxpos23"

    s674.GENERATED_DIR = s674.OUTPUT_DIR / "stage676_generated_inputs"
    s674.UNIVERSE_PLUS_PATH = s674.GENERATED_DIR / f"{OUTPUT_PREFIX}_plus23_universe_{MODEL_TAG}.csv"
    s674.HIST_ELIGIBILITY_PLUS_PATH = (
        s674.GENERATED_DIR / f"{OUTPUT_PREFIX}_historical_ai_plus23_eligibility_{MODEL_TAG}.csv"
    )
    # There is no same-universe full-market live inference after 2026-02-27 yet.
    # Reuse the historical timeline for the YTD runner and keep the report caveat explicit.
    s674.LATEST_ELIGIBILITY_PLUS_PATH = (
        s674.GENERATED_DIR / f"{OUTPUT_PREFIX}_latest_ai_plus23_eligibility_{MODEL_TAG}.csv"
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


def _write_ai_plus23_universe(symbols: list[str]) -> None:
    s674.GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    rows = []
    for symbol in sorted(symbols):
        product, exchange = symbol.split(".", 1)
        rows.append(
            {
                "product_vt_symbol": symbol,
                "product": product,
                "exchange": exchange,
                "eligible": 1,
                "source": "stage676_stage372_plus23_ai_ranked",
            }
        )
    pd.DataFrame(rows).to_csv(s674.UNIVERSE_PLUS_PATH, index=False, encoding="utf-8-sig")


def _write_ai_plus23_eligibility(symbols: list[str], target_path) -> pd.DataFrame:
    predictions = pd.read_csv(
        PREDICTIONS_OUTPUT_PATH,
        usecols=["eval_date", "product_vt_symbol", PROBABILITY_COLUMN, SIMPLE_SCORE_COLUMN],
    )
    predictions["eval_date"] = pd.to_datetime(predictions["eval_date"], errors="coerce").dt.strftime("%Y-%m-%d")
    predictions = predictions[predictions["product_vt_symbol"].astype(str).isin(set(symbols))].copy()
    if predictions.empty:
        raise RuntimeError("no full-market AI prediction rows for plus23 universe")

    rows = []
    for eval_date, group in predictions.groupby("eval_date", sort=True):
        ranked = group.sort_values(
            [PROBABILITY_COLUMN, SIMPLE_SCORE_COLUMN, "product_vt_symbol"],
            ascending=[False, False, True],
        ).reset_index(drop=True)
        ranked["score_rank"] = range(1, len(ranked) + 1)
        selected = ranked.head(TOP_N_AI).copy()
        top_n = TOP_N_AI
        for row in selected.itertuples(index=False):
            rows.append(
                {
                    "strategy": AI_PLUS23_STRATEGY,
                    "score_type": AI_PLUS23_SCORE_TYPE,
                    "eval_date": str(eval_date),
                    "product_vt_symbol": str(row.product_vt_symbol),
                    "score": float(getattr(row, PROBABILITY_COLUMN)),
                    "score_rank": int(getattr(row, "score_rank")),
                    "top_n": top_n,
                }
            )
        selected_products = set(selected["product_vt_symbol"].astype(str))
        if FU_PRODUCT in set(symbols) and FU_PRODUCT not in selected_products:
            min_score = float(selected[PROBABILITY_COLUMN].min()) if not selected.empty else 0.0
            rows.append(
                {
                    "strategy": AI_PLUS23_STRATEGY,
                    "score_type": AI_PLUS23_FU_SCORE_TYPE,
                    "eval_date": str(eval_date),
                    "product_vt_symbol": FU_PRODUCT,
                    "score": min_score - 1e-6,
                    "score_rank": top_n + 1,
                    "top_n": top_n + 1,
                }
            )

    eligibility = pd.DataFrame(rows).sort_values(["eval_date", "score_rank", "product_vt_symbol"])
    target_path.parent.mkdir(parents=True, exist_ok=True)
    eligibility.to_csv(target_path, index=False, encoding="utf-8-sig")
    return eligibility


def _prepare_inputs_ai_plus23() -> dict[str, object]:
    base_symbols = s674.s667.s666._official_symbols()
    plus_symbols = sorted(set(base_symbols) | set(s674.EXTRA_PRODUCTS))
    _write_ai_plus23_universe(plus_symbols)
    eligibility = _write_ai_plus23_eligibility(plus_symbols, s674.HIST_ELIGIBILITY_PLUS_PATH)
    eligibility.to_csv(s674.LATEST_ELIGIBILITY_PLUS_PATH, index=False, encoding="utf-8-sig")
    return {
        "base_symbols": base_symbols,
        "plus_symbols": plus_symbols,
        "historical_eligibility_source": str(PREDICTIONS_OUTPUT_PATH),
        "latest_eligibility_source": str(PREDICTIONS_OUTPUT_PATH),
        "base_metadata": s674.s667.s666.build_contract_metadata(supported_symbols=base_symbols),
        "plus_metadata": s674.s667.s666.build_contract_metadata(supported_symbols=plus_symbols),
        "ai_plus23_eval_date_min": str(eligibility["eval_date"].min()),
        "ai_plus23_eval_date_max": str(eligibility["eval_date"].max()),
        "ai_plus23_eval_dates": int(eligibility["eval_date"].nunique()),
    }


def main() -> None:
    _configure_stage676()
    original_prepare = s674.s667._prepare_inputs
    try:
        s674.s667._prepare_inputs = _prepare_inputs_ai_plus23
        s674.main()
    finally:
        s674.s667._prepare_inputs = original_prepare


if __name__ == "__main__":
    main()
