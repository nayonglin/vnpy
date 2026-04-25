from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from analyze_qmt_roll_ai_product_suitability_walkforward import PROBABILITY_COLUMN, SIMPLE_SCORE_COLUMN


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

MODEL_TAG: str = "full_market_structural_prefilter_v1"
OUTPUT_PREFIX: str = "qmt_roll_full_market_structural_prefilter"

FULL_MARKET_UNIVERSE_PATH: Path = (
    OUTPUT_DIR / "qmt_roll_full_market_tradable_universe_eligible_full_market_tradable_universe_v1.csv"
)
PRODUCT_FEATURES_PATH: Path = (
    OUTPUT_DIR / "qmt_roll_ai_product_suitability_full_market_walkforward_samples_product_suitability_full_market_wf_v1.csv"
)
PREDICTIONS_PATH: Path = (
    OUTPUT_DIR / "qmt_roll_ai_product_suitability_full_market_walkforward_predictions_product_suitability_full_market_wf_v1.csv"
)

AUDIT_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_audit_{MODEL_TAG}.csv"
ELIGIBLE_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_eligible_{MODEL_TAG}.csv"
ELIGIBILITY_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_ai_eligibility_{MODEL_TAG}.csv"
SUMMARY_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.json"
REPORT_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

MIN_NEW_RECENT_MEDIAN_VOLUME: float = 50_000.0
MAX_NEW_MARGIN_PER_CONTRACT: float = 45_000.0
MIN_NEW_TREND_EFFICIENCY_60D: float = 0.09
MIN_NEW_REALIZED_VOL_60D: float = 0.10
MIN_NEW_RANGE_PCT_60D: float = 0.018
AI_TOP_N: int = 8


FEATURE_COLUMNS: tuple[str, ...] = (
    "market_trend_efficiency_60d",
    "market_trend_efficiency_120d",
    "market_realized_vol_60d",
    "market_range_pct_mean_60d",
    "market_volume_ratio_60d",
    "market_open_interest_change_60d",
)


def _load_structural_features() -> pd.DataFrame:
    if not PRODUCT_FEATURES_PATH.exists():
        raise FileNotFoundError(PRODUCT_FEATURES_PATH)

    df = pd.read_csv(PRODUCT_FEATURES_PATH, usecols=lambda column: column in {"product_vt_symbol", *FEATURE_COLUMNS})
    for column in FEATURE_COLUMNS:
        df[column] = pd.to_numeric(df[column], errors="coerce").fillna(0.0)
    return (
        df.groupby("product_vt_symbol")
        .agg(
            market_trend_efficiency_60d_median=("market_trend_efficiency_60d", "median"),
            market_trend_efficiency_120d_median=("market_trend_efficiency_120d", "median"),
            market_realized_vol_60d_median=("market_realized_vol_60d", "median"),
            market_range_pct_mean_60d_median=("market_range_pct_mean_60d", "median"),
            market_volume_ratio_60d_median=("market_volume_ratio_60d", "median"),
            market_open_interest_change_60d_median=("market_open_interest_change_60d", "median"),
        )
        .reset_index()
    )


def _new_product_reject_reasons(row: pd.Series) -> str:
    reasons: list[str] = []
    if float(row["recent_median_volume"]) < MIN_NEW_RECENT_MEDIAN_VOLUME:
        reasons.append("low_recent_volume")
    if float(row["estimated_margin_per_contract"]) > MAX_NEW_MARGIN_PER_CONTRACT:
        reasons.append("one_contract_margin_too_high_for_new_product")
    if float(row["market_trend_efficiency_60d_median"]) < MIN_NEW_TREND_EFFICIENCY_60D:
        reasons.append("weak_60d_trend_efficiency")
    if float(row["market_realized_vol_60d_median"]) < MIN_NEW_REALIZED_VOL_60D:
        reasons.append("low_60d_realized_volatility")
    if float(row["market_range_pct_mean_60d_median"]) < MIN_NEW_RANGE_PCT_60D:
        reasons.append("low_60d_range")
    return ",".join(reasons)


def build_prefilter_universe() -> tuple[pd.DataFrame, pd.DataFrame]:
    if not FULL_MARKET_UNIVERSE_PATH.exists():
        raise FileNotFoundError(FULL_MARKET_UNIVERSE_PATH)

    universe = pd.read_csv(FULL_MARKET_UNIVERSE_PATH)
    features = _load_structural_features()
    audit = universe.merge(features, on="product_vt_symbol", how="left")
    numeric_columns = [
        "is_static_strategy_product",
        "recent_median_volume",
        "estimated_margin_per_contract",
        "market_trend_efficiency_60d_median",
        "market_realized_vol_60d_median",
        "market_range_pct_mean_60d_median",
    ]
    for column in numeric_columns:
        audit[column] = pd.to_numeric(audit[column], errors="coerce").fillna(0.0)

    audit["structural_prefilter_reject_reason"] = ""
    audit["structural_prefilter_kept"] = 0

    static_mask = audit["is_static_strategy_product"] == 1
    audit.loc[static_mask, "structural_prefilter_kept"] = 1
    audit.loc[static_mask, "structural_prefilter_reject_reason"] = "static_strategy_product_retained"

    new_mask = ~static_mask
    for index, row in audit.loc[new_mask].iterrows():
        reasons = _new_product_reject_reasons(row)
        if reasons:
            audit.at[index, "structural_prefilter_reject_reason"] = reasons
        else:
            audit.at[index, "structural_prefilter_kept"] = 1
            audit.at[index, "structural_prefilter_reject_reason"] = "new_product_structural_pass"

    eligible = audit[audit["structural_prefilter_kept"] == 1].copy()
    eligible.sort_values(["exchange", "product_vt_symbol"], inplace=True)
    audit.sort_values(
        ["structural_prefilter_kept", "is_static_strategy_product", "recent_median_volume", "product_vt_symbol"],
        ascending=[False, False, False, True],
        inplace=True,
    )
    return audit.reset_index(drop=True), eligible.reset_index(drop=True)


def build_ai_eligibility(eligible: pd.DataFrame) -> pd.DataFrame:
    if not PREDICTIONS_PATH.exists():
        raise FileNotFoundError(PREDICTIONS_PATH)

    predictions = pd.read_csv(PREDICTIONS_PATH)
    predictions["eval_date"] = pd.to_datetime(predictions["eval_date"]).dt.normalize()
    predictions = predictions[predictions["product_vt_symbol"].isin(set(eligible["product_vt_symbol"].astype(str)))].copy()
    for column in (PROBABILITY_COLUMN, SIMPLE_SCORE_COLUMN):
        predictions[column] = pd.to_numeric(predictions[column], errors="coerce").fillna(0.0)

    specs = (
        ("ai_structural_top8_entry_filter", "ai_probability", PROBABILITY_COLUMN),
        ("simple_structural_top8_entry_filter", "simple_score", SIMPLE_SCORE_COLUMN),
    )
    rows: list[dict[str, Any]] = []
    for strategy, score_type, score_column in specs:
        ranked = predictions.sort_values(["eval_date", score_column], ascending=[True, False]).copy()
        ranked["score_rank"] = ranked.groupby("eval_date")[score_column].rank(method="first", ascending=False)
        selected = ranked[ranked["score_rank"] <= AI_TOP_N].copy()
        for record in selected.itertuples(index=False):
            rows.append(
                {
                    "strategy": strategy,
                    "score_type": score_type,
                    "eval_date": pd.Timestamp(record.eval_date).date().isoformat(),
                    "product_vt_symbol": str(record.product_vt_symbol),
                    "score": float(getattr(record, score_column)),
                    "score_rank": int(record.score_rank),
                    "top_n": AI_TOP_N,
                }
            )
    eligibility = pd.DataFrame(rows)
    eligibility.sort_values(["strategy", "eval_date", "score_rank"], inplace=True)
    return eligibility.reset_index(drop=True)


def _reason_counts(audit: pd.DataFrame) -> dict[str, int]:
    counts: dict[str, int] = {}
    rejected = audit[audit["structural_prefilter_kept"] == 0]
    for value in rejected["structural_prefilter_reject_reason"].fillna("").astype(str):
        for reason in value.split(","):
            if reason:
                counts[reason] = counts.get(reason, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def build_summary(audit: pd.DataFrame, eligible: pd.DataFrame, eligibility: pd.DataFrame) -> dict[str, Any]:
    new_kept = eligible[eligible["is_static_strategy_product"] == 0]["product_vt_symbol"].astype(str).tolist()
    return {
        "model_tag": MODEL_TAG,
        "design_boundary": (
            "Two-stage filter: keep the previously validated static 18 products, and admit new full-market products "
            "only when they pass structural trend, volatility, liquidity and contract-affordability rules. "
            "No historical PnL threshold is used for product admission."
        ),
        "parameters": {
            "min_new_recent_median_volume": MIN_NEW_RECENT_MEDIAN_VOLUME,
            "max_new_margin_per_contract": MAX_NEW_MARGIN_PER_CONTRACT,
            "min_new_trend_efficiency_60d": MIN_NEW_TREND_EFFICIENCY_60D,
            "min_new_realized_vol_60d": MIN_NEW_REALIZED_VOL_60D,
            "min_new_range_pct_60d": MIN_NEW_RANGE_PCT_60D,
            "ai_top_n": AI_TOP_N,
        },
        "coverage": {
            "full_market_eligible_products": int(len(audit)),
            "structural_prefilter_products": int(len(eligible)),
            "static_products_retained": int((eligible["is_static_strategy_product"] == 1).sum()),
            "new_products_admitted": int((eligible["is_static_strategy_product"] == 0).sum()),
            "ai_eligibility_rows": int(len(eligibility)),
        },
        "new_products_admitted": new_kept,
        "reject_reason_counts": _reason_counts(audit),
        "artifacts": {
            "audit_csv": str(AUDIT_OUTPUT_PATH),
            "eligible_csv": str(ELIGIBLE_OUTPUT_PATH),
            "ai_eligibility_csv": str(ELIGIBILITY_OUTPUT_PATH),
            "summary_json": str(SUMMARY_OUTPUT_PATH),
            "report_md": str(REPORT_OUTPUT_PATH),
        },
    }


def _table(df: pd.DataFrame, columns: list[str], max_rows: int = 50) -> str:
    if df.empty:
        return "_empty_"
    view = df[columns].head(max_rows).copy()
    for column in view.columns:
        if pd.api.types.is_float_dtype(view[column]):
            view[column] = view[column].map(lambda value: f"{value:.4f}")
    header = "| " + " | ".join(view.columns) + " |"
    sep = "| " + " | ".join(["---"] * len(view.columns)) + " |"
    rows = ["| " + " | ".join(map(str, row)) + " |" for row in view.to_numpy()]
    return "\n".join([header, sep, *rows])


def build_report(audit: pd.DataFrame, eligible: pd.DataFrame, summary: dict[str, Any]) -> str:
    columns = [
        "product_vt_symbol",
        "is_static_strategy_product",
        "recent_median_volume",
        "estimated_margin_per_contract",
        "market_trend_efficiency_60d_median",
        "market_realized_vol_60d_median",
        "market_range_pct_mean_60d_median",
        "structural_prefilter_reject_reason",
    ]
    rejected_new = audit[
        (audit["is_static_strategy_product"] == 0) & (audit["structural_prefilter_kept"] == 0)
    ].copy()
    lines = [
        "# Full-Market Structural Prefilter Universe",
        "",
        "## Judgement",
        "",
        "- This is not a TopN search. The filter admits new products only when their market structure resembles trend-following terrain.",
        "- The original 18 products remain retained because they are the validated production baseline, not because every product has positive standalone PnL.",
        "- AI ranking is recomputed only inside this structurally cleaner universe.",
        "",
        "## Coverage",
        "",
        json.dumps(summary["coverage"], ensure_ascii=False, indent=2),
        "",
        "## Parameters",
        "",
        json.dumps(summary["parameters"], ensure_ascii=False, indent=2),
        "",
        "## Kept Products",
        "",
        _table(eligible, columns, max_rows=80),
        "",
        "## Rejected New Products",
        "",
        _table(rejected_new, columns, max_rows=80),
    ]
    return "\n".join(lines)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    audit, eligible = build_prefilter_universe()
    eligibility = build_ai_eligibility(eligible)
    summary = build_summary(audit, eligible, eligibility)

    audit.to_csv(AUDIT_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    eligible.to_csv(ELIGIBLE_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    eligibility.to_csv(ELIGIBILITY_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    SUMMARY_OUTPUT_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_OUTPUT_PATH.write_text(build_report(audit, eligible, summary), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
