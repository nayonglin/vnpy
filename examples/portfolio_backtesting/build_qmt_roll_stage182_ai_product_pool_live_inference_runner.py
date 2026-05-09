from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

import analyze_qmt_roll_ai_product_suitability_walkforward as suitability
from analyze_qmt_roll_ai_product_suitability_walkforward import (
    DATE_COLUMN,
    FUTURE_HORIZON_DAYS,
    MODEL_TAG as SOURCE_MODEL_TAG,
    PROBABILITY_COLUMN,
    SIMPLE_SCORE_COLUMN,
    add_rolling_features,
    add_simple_score,
    build_monthly_samples,
    build_product_daily,
    score_model,
    train_model,
)
from run_qmt_roll_selection_long015_volref30_corr_fu_candidate_robustness_backtest import (
    AI_SATELLITE_POST_SIGNAL_STRATEGY_NAME,
    FU_PRODUCT,
)
from qmt_roll_official_stage78_config import build_official_stage78_paths


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

MODEL_TAG: str = "stage182_ai_product_pool_live_inference_v1"
OUTPUT_PREFIX: str = "qmt_roll_stage182_ai_product_pool_live_inference"

LIVE_POOL_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_latest_pool_{MODEL_TAG}.csv"
LIVE_ELIGIBILITY_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_eligibility_{MODEL_TAG}.csv"
COMBINED_ELIGIBILITY_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_combined_stage78_eligibility_{MODEL_TAG}.csv"
SUMMARY_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.json"
REPORT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DEFAULT_SOURCE_PREFIX: str = "qmt_roll_selection_long015_volref30_corr_formal_floor35"


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if pd.isna(result):
        return default
    return result


def _last_completed_month_eval_date(daily_dates: pd.Series) -> pd.Timestamp:
    dates = pd.to_datetime(daily_dates).dropna().drop_duplicates().sort_values()
    if dates.empty:
        raise ValueError("no product daily dates available")
    max_date = pd.Timestamp(dates.iloc[-1]).normalize()
    month_start = pd.Timestamp(year=max_date.year, month=max_date.month, day=1)
    completed = dates[dates < month_start]
    if completed.empty:
        raise ValueError(f"no completed month before source max date {max_date.date().isoformat()}")
    latest_month = pd.Timestamp(completed.iloc[-1]).to_period("M")
    month_dates = completed[completed.dt.to_period("M") == latest_month]
    return pd.Timestamp(month_dates.iloc[-1]).normalize()


def _resolve_eval_date(daily: pd.DataFrame, eval_date: str, allow_incomplete_month: bool) -> pd.Timestamp:
    dates = pd.to_datetime(daily["date"]).dropna().drop_duplicates().sort_values()
    if dates.empty:
        raise ValueError("no product daily dates available")

    if eval_date:
        requested = pd.Timestamp(eval_date).normalize()
        available = dates[dates <= requested]
        if available.empty:
            raise ValueError(f"no product daily date <= requested eval date {requested.date().isoformat()}")
        resolved = pd.Timestamp(available.iloc[-1]).normalize()
    elif allow_incomplete_month:
        resolved = pd.Timestamp(dates.iloc[-1]).normalize()
    else:
        resolved = _last_completed_month_eval_date(dates)

    if not allow_incomplete_month:
        max_date = pd.Timestamp(dates.iloc[-1]).normalize()
        if resolved.to_period("M") == max_date.to_period("M") and resolved != _last_completed_month_eval_date(dates):
            raise ValueError(
                "resolved eval date is in an incomplete source month; pass --allow-incomplete-month to force it"
            )
    return resolved


def _training_label_cutoff(daily_dates: pd.Series, eval_date: pd.Timestamp) -> pd.Timestamp:
    dates = pd.to_datetime(daily_dates).dropna().drop_duplicates().sort_values().reset_index(drop=True)
    if dates.empty:
        raise ValueError("no product daily dates available")
    eval_index_values = dates[dates <= eval_date]
    if eval_index_values.empty:
        raise ValueError(f"eval date {eval_date.date().isoformat()} is before all source dates")
    eval_index = int(eval_index_values.index[-1])
    cutoff_index = max(0, eval_index - int(FUTURE_HORIZON_DAYS))
    return pd.Timestamp(dates.iloc[cutoff_index]).normalize()


def _build_live_feature_rows(featured: pd.DataFrame, eval_date: pd.Timestamp) -> pd.DataFrame:
    rows = featured[pd.to_datetime(featured["date"]).dt.normalize() == eval_date].copy()
    if rows.empty:
        raise ValueError(f"no feature rows for eval date {eval_date.date().isoformat()}")
    rows.rename(columns={"date": DATE_COLUMN}, inplace=True)
    rows = add_simple_score(rows)
    rows.sort_values("product_vt_symbol", inplace=True)
    rows.reset_index(drop=True, inplace=True)
    return rows


def _build_live_eligibility(scored: pd.DataFrame, eval_date: pd.Timestamp) -> pd.DataFrame:
    ranked = scored.sort_values(
        [PROBABILITY_COLUMN, SIMPLE_SCORE_COLUMN, "product_vt_symbol"],
        ascending=[False, False, True],
    ).reset_index(drop=True)
    ranked["ai_rank"] = range(1, len(ranked) + 1)
    top8 = ranked.head(8).copy()

    rows: list[dict[str, Any]] = []
    for row in top8.itertuples(index=False):
        rows.append(
            {
                "strategy": AI_SATELLITE_POST_SIGNAL_STRATEGY_NAME,
                "score_type": "stage182_live_monthly_ai_probability",
                "eval_date": eval_date.date().isoformat(),
                "product_vt_symbol": str(row.product_vt_symbol),
                "score": _safe_float(getattr(row, PROBABILITY_COLUMN)),
                "score_rank": int(getattr(row, "ai_rank")),
                "top_n": 9,
            }
        )

    selected_products = {str(row["product_vt_symbol"]) for row in rows}
    if FU_PRODUCT not in selected_products:
        min_score = min((_safe_float(row["score"]) for row in rows), default=0.0)
        rows.append(
            {
                "strategy": AI_SATELLITE_POST_SIGNAL_STRATEGY_NAME,
                "score_type": "stage182_live_fixed_fu_satellite",
                "eval_date": eval_date.date().isoformat(),
                "product_vt_symbol": FU_PRODUCT,
                "score": min_score - 1e-6,
                "score_rank": 9,
                "top_n": 9,
            }
        )

    result = pd.DataFrame(rows)
    result.sort_values(["eval_date", "score_rank", "product_vt_symbol"], inplace=True)
    result.reset_index(drop=True, inplace=True)
    return result


def _build_combined_eligibility(live_eligibility: pd.DataFrame) -> tuple[pd.DataFrame, Path]:
    _, official_eligibility_path = build_official_stage78_paths()
    official = pd.read_csv(official_eligibility_path)
    eval_dates = set(live_eligibility["eval_date"].astype(str))
    strategy = str(AI_SATELLITE_POST_SIGNAL_STRATEGY_NAME)
    keep = ~(
        official["strategy"].astype(str).eq(strategy)
        & official["eval_date"].astype(str).isin(eval_dates)
    )
    combined = pd.concat([official[keep].copy(), live_eligibility.copy()], ignore_index=True)
    combined.sort_values(["eval_date", "score_rank", "product_vt_symbol"], inplace=True)
    combined.reset_index(drop=True, inplace=True)
    return combined, official_eligibility_path


def _to_markdown_table(df: pd.DataFrame, columns: list[str]) -> str:
    if df.empty:
        return "_empty_"
    view = df[columns].copy()
    for column in view.columns:
        if pd.api.types.is_float_dtype(view[column]):
            view[column] = view[column].map(lambda value: f"{float(value):.6f}")
    header = "| " + " | ".join(view.columns) + " |"
    separator = "| " + " | ".join(["---"] * len(view.columns)) + " |"
    rows = ["| " + " | ".join(map(str, row)) + " |" for row in view.to_numpy()]
    return "\n".join([header, separator, *rows])


def _configure_source_paths(source_prefix: str) -> dict[str, str]:
    position_changes = OUTPUT_DIR / f"{source_prefix}_position_changes_2020_2026_04.csv"
    entry_snapshots = OUTPUT_DIR / f"{source_prefix}_entry_candidate_snapshots_2020_2026_04.csv"
    if not position_changes.exists():
        raise FileNotFoundError(f"missing source position changes: {position_changes}")
    if not entry_snapshots.exists():
        raise FileNotFoundError(f"missing source entry snapshots: {entry_snapshots}")
    suitability.POSITION_CHANGES_PATH = position_changes
    suitability.ENTRY_SNAPSHOTS_PATH = entry_snapshots
    return {
        "source_prefix": source_prefix,
        "position_changes": str(position_changes),
        "entry_snapshots": str(entry_snapshots),
    }


def build_report(summary: dict[str, Any], live_pool: pd.DataFrame, live_eligibility: pd.DataFrame) -> str:
    live_columns = [
        "ai_rank",
        "product_vt_symbol",
        PROBABILITY_COLUMN,
        SIMPLE_SCORE_COLUMN,
    ]
    eligibility_columns = [
        "eval_date",
        "product_vt_symbol",
        "score",
        "score_rank",
        "top_n",
        "score_type",
    ]
    return "\n".join(
        [
            "# Stage182 AI Product Pool Live Inference",
            "",
            f"- Generated at: `{summary['generated_at']}`",
            f"- Eval date: `{summary['eval_date']}`",
            f"- Source max date: `{summary['source_max_date']}`",
            f"- Source prefix: `{summary['source_paths']['source_prefix']}`",
            f"- Training label cutoff: `{summary['training_label_cutoff']}`",
            f"- Train rows: `{summary['train_rows']}`",
            f"- Feature count: `{summary['feature_count']}`",
            f"- Live rows: `{summary['live_rows']}`",
            f"- Strategy: `{AI_SATELLITE_POST_SIGNAL_STRATEGY_NAME}`",
            "",
            "## Leakage Boundary",
            "",
            (
                f"Training rows are restricted to eval dates on or before `{summary['training_label_cutoff']}`. "
                f"The live pool for `{summary['eval_date']}` is scored from features available at that date and "
                "is not used to train itself."
            ),
            "",
            "## Live Ranking",
            "",
            _to_markdown_table(live_pool.head(18), live_columns),
            "",
            "## Eligibility Written",
            "",
            _to_markdown_table(live_eligibility, eligibility_columns),
            "",
            "## Next Use",
            "",
            "Review this file first. Do not overwrite the official Stage78 eligibility file automatically.",
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Stage182 monthly live AI product pool inference runner.")
    parser.add_argument("--eval-date", default="", help="Requested eval date. Defaults to latest completed month.")
    parser.add_argument(
        "--source-prefix",
        default=DEFAULT_SOURCE_PREFIX,
        help="Artifact prefix for AI source position_changes and entry_candidate_snapshots.",
    )
    parser.add_argument(
        "--allow-incomplete-month",
        action="store_true",
        help="Allow scoring on the latest available date even if its calendar month is incomplete.",
    )
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    source_paths = _configure_source_paths(str(args.source_prefix))

    daily = build_product_daily()
    source_max_date = pd.Timestamp(daily["date"].max()).normalize()
    eval_date = _resolve_eval_date(daily, str(args.eval_date or ""), bool(args.allow_incomplete_month))
    label_cutoff = _training_label_cutoff(daily["date"], eval_date)

    featured = add_rolling_features(daily)
    samples, feature_columns = build_monthly_samples(featured)
    train_df = samples[pd.to_datetime(samples[DATE_COLUMN]).dt.normalize() <= label_cutoff].copy()
    if train_df.empty:
        raise RuntimeError(f"no training rows on or before label cutoff {label_cutoff.date().isoformat()}")
    if train_df[DATE_COLUMN].nunique() < 12:
        raise RuntimeError("too few training months for live inference")
    if train_df["target_future_top_half_60d"].nunique() < 2:
        raise RuntimeError("training target has fewer than two classes")

    model = train_model(train_df, feature_columns)
    live_rows = _build_live_feature_rows(featured, eval_date)
    live_rows[PROBABILITY_COLUMN] = score_model(model, live_rows, feature_columns)
    live_pool = live_rows.sort_values(
        [PROBABILITY_COLUMN, SIMPLE_SCORE_COLUMN, "product_vt_symbol"],
        ascending=[False, False, True],
    ).copy()
    live_pool["ai_rank"] = range(1, len(live_pool) + 1)

    live_eligibility = _build_live_eligibility(live_pool, eval_date)
    combined, official_eligibility_path = _build_combined_eligibility(live_eligibility)

    live_pool.to_csv(LIVE_POOL_PATH, index=False, encoding="utf-8-sig")
    live_eligibility.to_csv(LIVE_ELIGIBILITY_PATH, index=False, encoding="utf-8-sig")
    combined.to_csv(COMBINED_ELIGIBILITY_PATH, index=False, encoding="utf-8-sig")

    summary: dict[str, Any] = {
        "model_tag": MODEL_TAG,
        "source_model_tag": SOURCE_MODEL_TAG,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "eval_date": eval_date.date().isoformat(),
        "source_max_date": source_max_date.date().isoformat(),
        "training_label_cutoff": label_cutoff.date().isoformat(),
        "future_horizon_days": int(FUTURE_HORIZON_DAYS),
        "train_rows": int(len(train_df)),
        "train_months": int(train_df[DATE_COLUMN].nunique()),
        "feature_count": int(len(feature_columns)),
        "live_rows": int(len(live_pool)),
        "source_paths": source_paths,
        "official_eligibility_path": str(official_eligibility_path),
        "outputs": {
            "live_pool": str(LIVE_POOL_PATH),
            "live_eligibility": str(LIVE_ELIGIBILITY_PATH),
            "combined_eligibility": str(COMBINED_ELIGIBILITY_PATH),
            "summary": str(SUMMARY_PATH),
            "report": str(REPORT_PATH),
        },
        "safety": {
            "overwrites_official_stage78_eligibility": False,
            "uses_future_label_for_eval_date": False,
            "real_order_enabled": False,
        },
    }
    SUMMARY_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_PATH.write_text(build_report(summary, live_pool, live_eligibility), encoding="utf-8")

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"report: {REPORT_PATH}")


if __name__ == "__main__":
    main()
