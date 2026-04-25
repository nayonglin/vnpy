from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

import analyze_qmt_roll_ai_product_suitability_walkforward as base
from analyze_qmt_roll_ai_product_suitability_market_walkforward import (
    _load_contract_bars,
    add_market_features,
)
from main_contract_mapping import load_mapping_df


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

MODEL_TAG: str = "product_suitability_full_market_wf_v1"
SOURCE_PREFIX: str = "qmt_roll_selection_long015_volref30_corr_full_market_floor35_formal"
OUTPUT_PREFIX: str = "qmt_roll_ai_product_suitability_full_market_walkforward"

POSITION_CHANGES_PATH: Path = OUTPUT_DIR / f"{SOURCE_PREFIX}_position_changes_2020_2026_04.csv"
ENTRY_SNAPSHOTS_PATH: Path = OUTPUT_DIR / f"{SOURCE_PREFIX}_entry_candidate_snapshots_2020_2026_04.csv"

PRODUCT_DAILY_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_{MODEL_TAG}.csv"
MARKET_DAILY_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_market_daily_{MODEL_TAG}.csv"
FEATURED_DAILY_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_featured_daily_{MODEL_TAG}.csv"
SAMPLES_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_samples_{MODEL_TAG}.csv"
PREDICTIONS_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_predictions_{MODEL_TAG}.csv"
WINDOW_METRICS_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_window_metrics_{MODEL_TAG}.csv"
BUCKET_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_bucket_analysis_{MODEL_TAG}.csv"
TOP_PRODUCTS_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_top_products_{MODEL_TAG}.csv"
COEFFICIENT_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_coefficients_{MODEL_TAG}.csv"
SUMMARY_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.json"
REPORT_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


def build_full_market_daily(base_daily: pd.DataFrame) -> pd.DataFrame:
    dates = pd.DatetimeIndex(sorted(base_daily["date"].unique()))
    products = sorted(base_daily["product_vt_symbol"].dropna().astype(str).unique())
    start = dates.min() - pd.Timedelta(days=220)
    end = dates.max() + pd.Timedelta(days=5)

    mapping = load_mapping_df()
    mapping["date"] = pd.to_datetime(mapping["date"])
    mapping = mapping[
        (mapping["continuous_symbol_vt"].isin(products))
        & (mapping["date"] >= start)
        & (mapping["date"] <= end)
        & (mapping["main_contract_vt"].astype(str) != "")
    ].copy()
    mapping.rename(columns={"continuous_symbol_vt": "product_vt_symbol"}, inplace=True)

    contract_bars = _load_contract_bars(
        mapping["main_contract_vt"].dropna().astype(str).unique().tolist(),
        start,
        end,
    )
    market = mapping[["date", "product_vt_symbol", "main_contract_vt"]].merge(
        contract_bars,
        on=["date", "main_contract_vt"],
        how="left",
    )
    index = pd.MultiIndex.from_product([dates, products], names=["date", "product_vt_symbol"])
    market = market.set_index(["date", "product_vt_symbol"]).reindex(index).reset_index()
    market.sort_values(["product_vt_symbol", "date"], inplace=True)
    for column in ["open", "high", "low", "close"]:
        market[column] = market.groupby("product_vt_symbol")[column].ffill()
    market[["volume", "open_interest"]] = market[["volume", "open_interest"]].fillna(0.0)
    market["main_contract_vt"] = market["main_contract_vt"].fillna("")
    return add_market_features(market)


def to_markdown_table(df: pd.DataFrame) -> str:
    if df.empty:
        return "_empty_"
    view = df.copy()
    for column in view.columns:
        if pd.api.types.is_float_dtype(view[column]):
            view[column] = view[column].map(lambda value: f"{value:.4f}")
    header = "| " + " | ".join(view.columns) + " |"
    separator = "| " + " | ".join(["---"] * len(view.columns)) + " |"
    rows = ["| " + " | ".join(map(str, row)) + " |" for row in view.to_numpy()]
    return "\n".join([header, separator, *rows])


def build_report(summary: dict[str, Any], bucket_df: pd.DataFrame, top_overall_df: pd.DataFrame) -> str:
    ai_metrics = summary.get("ai_prediction_metrics", {})
    simple_metrics = summary.get("simple_score_metrics_on_ai_test_period", {})
    lines = [
        "# Full-Market Product Suitability Walk-Forward",
        "",
        "## Current Judgement",
        "",
        f"- Source strategy: `{SOURCE_PREFIX}`",
        f"- Candidate universe: full-market tradable pool from the formal baseline path.",
        f"- Target: next `{base.FUTURE_HORIZON_DAYS}` trading days product net contribution top half.",
        f"- Products: `{summary.get('coverage', {}).get('products', 0)}`",
        f"- AI AUC: `{ai_metrics.get('roc_auc', 0.0):.4f}`",
        f"- AI monthly rank IC: `{ai_metrics.get('mean_rank_ic_by_month', 0.0):.4f}`",
        f"- Simple score monthly rank IC: `{simple_metrics.get('mean_rank_ic_by_month', 0.0):.4f}`",
        "",
        "## Top Product Summary",
        "",
        to_markdown_table(top_overall_df),
        "",
        "## AI Buckets",
        "",
        to_markdown_table(bucket_df[bucket_df["score_type"] == "ai_probability"] if not bucket_df.empty else bucket_df),
        "",
        "## Design Boundary",
        "",
        "- This is still a walk-forward ranking study, not an executable portfolio result.",
        "- It intentionally keeps the previous model form and split rules unchanged.",
        "- Any trading use must pass shadow filtering and then formal backtest.",
    ]
    return "\n".join(lines)


def main() -> None:
    if not POSITION_CHANGES_PATH.exists():
        raise FileNotFoundError(f"missing full-market position changes: {POSITION_CHANGES_PATH}")
    if not ENTRY_SNAPSHOTS_PATH.exists():
        raise FileNotFoundError(f"missing full-market entry snapshots: {ENTRY_SNAPSHOTS_PATH}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    base.POSITION_CHANGES_PATH = POSITION_CHANGES_PATH
    base.ENTRY_SNAPSHOTS_PATH = ENTRY_SNAPSHOTS_PATH
    base.PRODUCT_DAILY_OUTPUT_PATH = PRODUCT_DAILY_OUTPUT_PATH

    product_daily = base.build_product_daily()
    system_featured_daily = base.add_rolling_features(product_daily)
    market_daily = build_full_market_daily(product_daily)
    market_feature_columns = [column for column in market_daily.columns if column.startswith("market_")]
    featured_daily = system_featured_daily.merge(
        market_daily[["date", "product_vt_symbol", "main_contract_vt"] + market_feature_columns],
        on=["date", "product_vt_symbol"],
        how="left",
    )
    featured_daily[market_feature_columns] = featured_daily[market_feature_columns].fillna(0.0)

    samples, feature_columns = base.build_monthly_samples(featured_daily)
    predictions, window_metrics, coefficients = base.run_walk_forward(samples, feature_columns)
    if predictions.empty:
        raise RuntimeError("full-market walk-forward produced no prediction rows")
    predictions[base.SIMPLE_SCORE_PERCENTILE_COLUMN] = predictions.groupby(base.DATE_COLUMN)[
        base.SIMPLE_SCORE_COLUMN
    ].rank(method="average", pct=True)

    prediction_columns = [
        base.DATE_COLUMN,
        "product_vt_symbol",
        "window_id",
        base.PROBABILITY_COLUMN,
        base.SIMPLE_SCORE_COLUMN,
        base.SIMPLE_SCORE_PERCENTILE_COLUMN,
        f"future_net_pnl_{base.FUTURE_HORIZON_DAYS}d",
        "future_rank_pct_60d",
        "future_rank_centered_60d",
        base.TARGET_COLUMN,
        base.WEIGHT_COLUMN,
    ] + feature_columns
    prediction_columns = list(dict.fromkeys(column for column in prediction_columns if column in predictions.columns))
    predictions = predictions[prediction_columns].copy()

    ai_metrics = base.compute_binary_metrics(predictions, base.PROBABILITY_COLUMN)
    simple_metrics = base.compute_binary_metrics(predictions, base.SIMPLE_SCORE_PERCENTILE_COLUMN)
    ai_top_df = base.summarize_top_products(predictions, base.PROBABILITY_COLUMN, "ai_probability")
    simple_top_df = base.summarize_top_products(predictions, base.SIMPLE_SCORE_COLUMN, "simple_score")
    top_products_df = pd.concat([ai_top_df, simple_top_df], ignore_index=True)
    top_overall = [
        {"score_type": "ai_probability", **base.summarize_top_overall(ai_top_df)},
        {"score_type": "simple_score", **base.summarize_top_overall(simple_top_df)},
    ]
    top_overall_df = pd.DataFrame(top_overall)
    bucket_df = pd.concat(
        [
            base.build_bucket_analysis(predictions, base.PROBABILITY_COLUMN, "ai_probability"),
            base.build_bucket_analysis(predictions, base.SIMPLE_SCORE_COLUMN, "simple_score"),
        ],
        ignore_index=True,
    )

    summary: dict[str, Any] = {
        "model_tag": MODEL_TAG,
        "source_prefix": SOURCE_PREFIX,
        "source_paths": {
            "position_changes": str(POSITION_CHANGES_PATH),
            "entry_snapshots": str(ENTRY_SNAPSHOTS_PATH),
        },
        "target_definition": {
            "future_horizon_days": base.FUTURE_HORIZON_DAYS,
            "target_column": base.TARGET_COLUMN,
            "target_rule": "future product net contribution ranks in top half of same monthly cross-section",
            "weight_column": base.WEIGHT_COLUMN,
        },
        "walk_forward": {
            "train_window_days": base.TRAIN_WINDOW_DAYS,
            "test_window_days": base.TEST_WINDOW_DAYS,
            "step_days": base.STEP_DAYS,
            "min_train_rows": base.MIN_TRAIN_ROWS,
            "min_test_rows": base.MIN_TEST_ROWS,
            "window_count": int(window_metrics["window_id"].nunique()) if not window_metrics.empty else 0,
        },
        "coverage": {
            "sample_rows": int(len(samples)),
            "prediction_rows": int(len(predictions)),
            "eval_months": int(samples[base.DATE_COLUMN].nunique()),
            "prediction_months": int(predictions[base.DATE_COLUMN].nunique()),
            "products": int(samples["product_vt_symbol"].nunique()),
            "feature_count": int(len(feature_columns)),
        },
        "market_feature_count": int(len([column for column in feature_columns if column.startswith("market_")])),
        "model": {
            "type": "logistic_regression",
            "regularization_c": base.LOGISTIC_C,
            "random_state": base.RANDOM_STATE,
        },
        "ai_prediction_metrics": ai_metrics,
        "simple_score_metrics_on_ai_test_period": {
            "score_column": base.SIMPLE_SCORE_PERCENTILE_COLUMN,
            **simple_metrics,
        },
        "top_product_summary": top_overall,
        "artifacts": {
            "product_daily_csv": str(PRODUCT_DAILY_OUTPUT_PATH),
            "market_daily_csv": str(MARKET_DAILY_OUTPUT_PATH),
            "featured_daily_csv": str(FEATURED_DAILY_OUTPUT_PATH),
            "samples_csv": str(SAMPLES_OUTPUT_PATH),
            "predictions_csv": str(PREDICTIONS_OUTPUT_PATH),
            "window_metrics_csv": str(WINDOW_METRICS_OUTPUT_PATH),
            "bucket_analysis_csv": str(BUCKET_OUTPUT_PATH),
            "top_products_csv": str(TOP_PRODUCTS_OUTPUT_PATH),
            "coefficients_csv": str(COEFFICIENT_OUTPUT_PATH),
            "summary_json": str(SUMMARY_OUTPUT_PATH),
            "report_md": str(REPORT_OUTPUT_PATH),
        },
        "design_judgement": (
            "The full-market baseline is intentionally used as a stress label source. "
            "A valid product-pool filter must reject weak products out-of-sample before any formal trading use."
        ),
    }

    product_daily.to_csv(PRODUCT_DAILY_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    market_daily.to_csv(MARKET_DAILY_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    featured_daily.to_csv(FEATURED_DAILY_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    samples.to_csv(SAMPLES_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    predictions.to_csv(PREDICTIONS_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    window_metrics.to_csv(WINDOW_METRICS_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    bucket_df.to_csv(BUCKET_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    top_products_df.to_csv(TOP_PRODUCTS_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    coefficients.to_csv(COEFFICIENT_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    SUMMARY_OUTPUT_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_OUTPUT_PATH.write_text(build_report(summary, bucket_df, top_overall_df), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
