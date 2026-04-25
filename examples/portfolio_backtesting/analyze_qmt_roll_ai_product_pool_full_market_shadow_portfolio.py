from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

import analyze_qmt_roll_ai_product_pool_shadow_portfolio as shadow
from analyze_qmt_roll_ai_product_suitability_full_market_walkforward import (
    PREDICTIONS_OUTPUT_PATH,
    PRODUCT_DAILY_OUTPUT_PATH,
    SOURCE_PREFIX,
)
from analyze_qmt_roll_ai_product_suitability_walkforward import PROBABILITY_COLUMN, SIMPLE_SCORE_COLUMN


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

MODEL_TAG: str = "ai_product_pool_full_market_shadow_v1"
OUTPUT_PREFIX: str = "qmt_roll_ai_product_pool_full_market_shadow_portfolio"

POSITION_CHANGES_PATH: Path = OUTPUT_DIR / f"{SOURCE_PREFIX}_position_changes_2020_2026_04.csv"
OFFICIAL_DAILY_PATH: Path = OUTPUT_DIR / f"{SOURCE_PREFIX}_daily.csv"

DAILY_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_{MODEL_TAG}.csv"
SUMMARY_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
YEARLY_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_yearly_{MODEL_TAG}.csv"
PRODUCT_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_attribution_{MODEL_TAG}.csv"
PRODUCT_YEAR_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_year_attribution_{MODEL_TAG}.csv"
ELIGIBILITY_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_eligibility_{MODEL_TAG}.csv"
SUMMARY_JSON_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.json"
REPORT_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


@dataclass(frozen=True)
class PoolSpec:
    strategy: str
    score_type: str
    score_column: str
    top_n: int | None
    description: str


POOL_SPECS: tuple[PoolSpec, ...] = (
    PoolSpec(
        strategy="baseline_all_products",
        score_type="baseline",
        score_column="",
        top_n=None,
        description="No product-pool filter, same frozen full-market formal position path over the AI evaluation period.",
    ),
    PoolSpec(
        strategy="ai_top8_entry_filter",
        score_type="ai_probability",
        score_column=PROBABILITY_COLUMN,
        top_n=8,
        description="Use full-market AI probabilities, allow only top 8 products for new entries.",
    ),
    PoolSpec(
        strategy="ai_top12_entry_filter",
        score_type="ai_probability",
        score_column=PROBABILITY_COLUMN,
        top_n=12,
        description="Use full-market AI probabilities, allow only top 12 products for new entries.",
    ),
    PoolSpec(
        strategy="simple_top8_entry_filter",
        score_type="simple_score",
        score_column=SIMPLE_SCORE_COLUMN,
        top_n=8,
        description="Use transparent simple suitability score, allow only top 8 products for new entries.",
    ),
)


def build_eligibility(predictions: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for spec in POOL_SPECS:
        if spec.top_n is None:
            continue
        ranked = predictions.sort_values(["eval_date", spec.score_column], ascending=[True, False]).copy()
        ranked["score_rank"] = ranked.groupby("eval_date")[spec.score_column].rank(method="first", ascending=False)
        selected = ranked[ranked["score_rank"] <= spec.top_n].copy()
        for _, row in selected.iterrows():
            rows.append(
                {
                    "strategy": spec.strategy,
                    "score_type": spec.score_type,
                    "eval_date": row["eval_date"],
                    "product_vt_symbol": row["product_vt_symbol"],
                    "score": shadow._safe_float(row[spec.score_column]),
                    "score_rank": int(row["score_rank"]),
                    "top_n": int(spec.top_n),
                }
            )
    return pd.DataFrame(rows).sort_values(["strategy", "eval_date", "score_rank"]).reset_index(drop=True)


def main() -> None:
    if not POSITION_CHANGES_PATH.exists():
        raise FileNotFoundError(f"missing full-market position changes: {POSITION_CHANGES_PATH}")
    if not OFFICIAL_DAILY_PATH.exists():
        raise FileNotFoundError(f"missing full-market official daily: {OFFICIAL_DAILY_PATH}")
    if not PREDICTIONS_OUTPUT_PATH.exists():
        raise FileNotFoundError(f"missing full-market predictions: {PREDICTIONS_OUTPUT_PATH}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    shadow.POSITION_CHANGES_PATH = POSITION_CHANGES_PATH
    shadow.OFFICIAL_DAILY_PATH = OFFICIAL_DAILY_PATH
    shadow.MARKET_PREDICTIONS_PATH = PREDICTIONS_OUTPUT_PATH

    position_changes = shadow.load_position_changes()
    official_daily = shadow.load_official_daily()
    predictions = shadow.load_predictions()
    eligibility = build_eligibility(predictions)
    signal_lookup = shadow.build_signal_lookup(eligibility)

    eval_dates = sorted(pd.Timestamp(date) for date in predictions["eval_date"].unique())
    if not eval_dates:
        raise RuntimeError("no prediction eval dates")
    first_eval_date = min(eval_dates)
    all_dates = pd.Series(sorted(position_changes["date"].unique()))
    valid_dates = all_dates[all_dates > first_eval_date]
    if valid_dates.empty:
        raise RuntimeError("no dates after first prediction eval date")
    evaluation_start = pd.Timestamp(valid_dates.iloc[0])

    date_signal = pd.DataFrame({"date": valid_dates})
    date_signal["signal_date"] = shadow.latest_signal_dates(date_signal["date"], eval_dates)
    signal_date_by_date = {
        pd.Timestamp(row.date): pd.Timestamp(row.signal_date)
        for row in date_signal.itertuples(index=False)
        if not pd.isna(row.signal_date)
    }

    official_eval = official_daily[official_daily["date"] >= evaluation_start].copy()
    if official_eval.empty:
        raise RuntimeError("official daily has no evaluation rows")
    initial_balance = float(official_eval.iloc[0]["balance"] - official_eval.iloc[0]["net_pnl"])

    spec_by_strategy = {spec.strategy: spec for spec in POOL_SPECS}
    strategy_frames: list[pd.DataFrame] = []
    for spec in POOL_SPECS:
        strategy_frames.append(
            shadow.build_shadow_rows(
                position_changes=position_changes,
                strategy=spec.strategy,
                evaluation_start=evaluation_start,
                signal_date_by_date=signal_date_by_date,
                signal_lookup=signal_lookup,
            )
        )
    strategy_rows = pd.concat(strategy_frames, ignore_index=True)
    daily = shadow.calculate_daily(strategy_rows, initial_balance)
    summary = shadow.calculate_summary(daily, initial_balance, spec_by_strategy)
    yearly = shadow.calculate_yearly(daily)
    product = shadow.calculate_product_attribution(strategy_rows)
    product_year = shadow.calculate_product_year_attribution(strategy_rows)

    daily.to_csv(DAILY_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    yearly.to_csv(YEARLY_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    product.to_csv(PRODUCT_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    product_year.to_csv(PRODUCT_YEAR_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    eligibility.to_csv(ELIGIBILITY_OUTPUT_PATH, index=False, encoding="utf-8-sig")

    payload: dict[str, Any] = {
        "model_tag": MODEL_TAG,
        "source_prefix": SOURCE_PREFIX,
        "design_boundary": (
            "Entry-filter shadow portfolio from frozen full-market position-change attribution; not an executable "
            "vn.py backtest because sizing and replacement trades are not recomputed."
        ),
        "source_paths": {
            "position_changes": str(POSITION_CHANGES_PATH),
            "official_daily": str(OFFICIAL_DAILY_PATH),
            "full_market_predictions": str(PREDICTIONS_OUTPUT_PATH),
            "product_daily": str(PRODUCT_DAILY_OUTPUT_PATH),
        },
        "parameters": {
            "first_prediction_eval_date": first_eval_date.date().isoformat(),
            "evaluation_start": evaluation_start.date().isoformat(),
            "signal_effective_rule": "latest eval_date strictly earlier than trade date",
            "legacy_position_rule": "positions already open at evaluation_start are kept until original exit",
            "trading_days_per_year": shadow.TRADING_DAYS_PER_YEAR,
            "initial_balance": initial_balance,
            "pool_specs": [spec.__dict__ for spec in POOL_SPECS],
        },
        "summary": summary.to_dict(orient="records"),
        "artifacts": {
            "daily_csv": str(DAILY_OUTPUT_PATH),
            "summary_csv": str(SUMMARY_OUTPUT_PATH),
            "yearly_csv": str(YEARLY_OUTPUT_PATH),
            "product_attribution_csv": str(PRODUCT_OUTPUT_PATH),
            "product_year_attribution_csv": str(PRODUCT_YEAR_OUTPUT_PATH),
            "eligibility_csv": str(ELIGIBILITY_OUTPUT_PATH),
            "summary_json": str(SUMMARY_JSON_OUTPUT_PATH),
            "report_md": str(REPORT_OUTPUT_PATH),
        },
        "judgement": (
            "Full-market expansion should remain blocked unless an AI pool improves the frozen attribution path "
            "and then survives executable formal backtest."
        ),
    }
    SUMMARY_JSON_OUTPUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_OUTPUT_PATH.write_text(shadow.build_report(summary, yearly), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
