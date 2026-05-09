from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from build_qmt_roll_stage182_ai_product_pool_live_inference_runner import (
    _build_combined_eligibility,
    _build_live_eligibility,
    _build_live_feature_rows,
    _configure_source_paths,
    _resolve_eval_date,
    _safe_float,
    _to_markdown_table,
    _training_label_cutoff,
)
from analyze_qmt_roll_ai_product_suitability_walkforward import (
    DATE_COLUMN,
    MODEL_TAG as SOURCE_MODEL_TAG,
    PROBABILITY_COLUMN,
    SIMPLE_SCORE_COLUMN,
    add_rolling_features,
    build_monthly_samples,
    build_product_daily,
    score_model,
    train_model,
)
from run_qmt_roll_selection_long015_volref30_corr_fu_candidate_robustness_backtest import (
    AI_SATELLITE_POST_SIGNAL_STRATEGY_NAME,
)


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

MODEL_TAG: str = "stage189_ai_product_pool_backfill_multimonth_v1"
OUTPUT_PREFIX: str = "qmt_roll_stage189_ai_product_pool_backfill_multimonth"
DEFAULT_SOURCE_PREFIX: str = "qmt_roll_stage183_ai_source_floor35"

LIVE_POOL_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_pool_{MODEL_TAG}.csv"
LIVE_ELIGIBILITY_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_eligibility_{MODEL_TAG}.csv"
COMBINED_ELIGIBILITY_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_combined_stage78_eligibility_{MODEL_TAG}.csv"
SUMMARY_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.json"
REPORT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


def _parse_eval_dates(text: str) -> list[str]:
    values = [item.strip() for item in str(text or "").split(",") if item.strip()]
    if not values:
        raise ValueError("at least one eval date is required")
    return values


def _build_one_eval_date(
    featured: pd.DataFrame,
    samples: pd.DataFrame,
    feature_columns: list[str],
    daily_dates: pd.Series,
    eval_date: pd.Timestamp,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    label_cutoff = _training_label_cutoff(daily_dates, eval_date)
    train_df = samples[pd.to_datetime(samples[DATE_COLUMN]).dt.normalize() <= label_cutoff].copy()
    if train_df.empty:
        raise RuntimeError(f"no training rows on or before label cutoff {label_cutoff.date().isoformat()}")
    if train_df[DATE_COLUMN].nunique() < 12:
        raise RuntimeError(f"too few training months for eval date {eval_date.date().isoformat()}")
    if train_df["target_future_top_half_60d"].nunique() < 2:
        raise RuntimeError(f"training target has fewer than two classes for eval date {eval_date.date().isoformat()}")

    model = train_model(train_df, feature_columns)
    live_rows = _build_live_feature_rows(featured, eval_date)
    live_rows[PROBABILITY_COLUMN] = score_model(model, live_rows, feature_columns)
    live_pool = live_rows.sort_values(
        [PROBABILITY_COLUMN, SIMPLE_SCORE_COLUMN, "product_vt_symbol"],
        ascending=[False, False, True],
    ).copy()
    live_pool["ai_rank"] = range(1, len(live_pool) + 1)
    live_pool["eval_date"] = eval_date.date().isoformat()

    live_eligibility = _build_live_eligibility(live_pool, eval_date)
    audit = {
        "eval_date": eval_date.date().isoformat(),
        "training_label_cutoff": label_cutoff.date().isoformat(),
        "train_rows": int(len(train_df)),
        "train_months": int(train_df[DATE_COLUMN].nunique()),
        "live_rows": int(len(live_pool)),
        "selected_products": live_eligibility["product_vt_symbol"].astype(str).tolist(),
    }
    return live_pool, live_eligibility, audit


def _build_report(summary: dict[str, Any], pool: pd.DataFrame, eligibility: pd.DataFrame) -> str:
    ranking_columns = ["eval_date", "ai_rank", "product_vt_symbol", PROBABILITY_COLUMN, SIMPLE_SCORE_COLUMN]
    eligibility_columns = ["eval_date", "product_vt_symbol", "score", "score_rank", "top_n", "score_type"]
    lines = [
        "# Stage189 AI Product Pool Backfill Multimonth",
        "",
        f"- Generated at: `{summary['generated_at']}`",
        f"- Source max date: `{summary['source_max_date']}`",
        f"- Source prefix: `{summary['source_paths']['source_prefix']}`",
        f"- Eval dates: `{', '.join(summary['eval_dates'])}`",
        f"- Strategy: `{AI_SATELLITE_POST_SIGNAL_STRATEGY_NAME}`",
        "",
        "## Safety",
        "",
        "- This stage does not overwrite the official Stage78 eligibility file.",
        "- Each eval date trains only on labels whose future horizon is complete before that eval date.",
        "- This is an input-timeline repair for shadow/backtest, not a new strategy.",
        "",
        "## Eval Audits",
        "",
        "| eval_date | training_label_cutoff | train_rows | train_months | selected_products |",
        "| --- | --- | ---: | ---: | --- |",
    ]
    for item in summary["eval_audits"]:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(item["eval_date"]),
                    str(item["training_label_cutoff"]),
                    f"{int(item['train_rows'])}",
                    f"{int(item['train_months'])}",
                    ", ".join(item["selected_products"]),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Live Ranking",
            "",
            _to_markdown_table(pool[ranking_columns].head(40), ranking_columns),
            "",
            "## Eligibility Written",
            "",
            _to_markdown_table(eligibility, eligibility_columns),
            "",
            "## Outputs",
            "",
            "| artifact | path |",
            "| --- | --- |",
        ]
    )
    lines.extend(f"| {key} | `{value}` |" for key, value in summary["outputs"].items())
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill multiple monthly AI pools without overwriting Stage182 outputs.")
    parser.add_argument("--eval-dates", default="2026-03-31,2026-04-30", help="Comma-separated eval dates.")
    parser.add_argument("--source-prefix", default=DEFAULT_SOURCE_PREFIX)
    parser.add_argument(
        "--allow-incomplete-month",
        action="store_true",
        help="Allow eval dates in incomplete source month. Intended for diagnostics only.",
    )
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    source_paths = _configure_source_paths(str(args.source_prefix))
    requested_eval_dates = _parse_eval_dates(str(args.eval_dates))

    daily = build_product_daily()
    source_max_date = pd.Timestamp(daily["date"].max()).normalize()
    featured = add_rolling_features(daily)
    samples, feature_columns = build_monthly_samples(featured)

    pool_frames: list[pd.DataFrame] = []
    eligibility_frames: list[pd.DataFrame] = []
    eval_audits: list[dict[str, Any]] = []
    resolved_eval_dates: list[str] = []
    for requested in requested_eval_dates:
        eval_date = _resolve_eval_date(daily, requested, bool(args.allow_incomplete_month))
        eval_text = eval_date.date().isoformat()
        if eval_text in resolved_eval_dates:
            continue
        pool, eligibility, audit = _build_one_eval_date(
            featured=featured,
            samples=samples,
            feature_columns=feature_columns,
            daily_dates=daily["date"],
            eval_date=eval_date,
        )
        pool_frames.append(pool)
        eligibility_frames.append(eligibility)
        eval_audits.append(audit)
        resolved_eval_dates.append(eval_text)

    live_pool = pd.concat(pool_frames, ignore_index=True)
    live_eligibility = pd.concat(eligibility_frames, ignore_index=True)
    live_eligibility.sort_values(["eval_date", "score_rank", "product_vt_symbol"], inplace=True)
    live_eligibility.reset_index(drop=True, inplace=True)
    combined, official_eligibility_path = _build_combined_eligibility(live_eligibility)

    live_pool.to_csv(LIVE_POOL_PATH, index=False, encoding="utf-8-sig")
    live_eligibility.to_csv(LIVE_ELIGIBILITY_PATH, index=False, encoding="utf-8-sig")
    combined.to_csv(COMBINED_ELIGIBILITY_PATH, index=False, encoding="utf-8-sig")

    summary: dict[str, Any] = {
        "model_tag": MODEL_TAG,
        "source_model_tag": SOURCE_MODEL_TAG,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "eval_dates": resolved_eval_dates,
        "source_max_date": source_max_date.date().isoformat(),
        "source_paths": source_paths,
        "official_eligibility_path": str(official_eligibility_path),
        "feature_count": int(len(feature_columns)),
        "eval_audits": eval_audits,
        "combined_eval_date_min": str(combined["eval_date"].min()),
        "combined_eval_date_max": str(combined["eval_date"].max()),
        "combined_unique_eval_dates": int(pd.to_datetime(combined["eval_date"]).nunique()),
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
            "is_strategy_change": False,
        },
    }
    SUMMARY_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_PATH.write_text(_build_report(summary, live_pool, live_eligibility), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"report: {REPORT_PATH}")


if __name__ == "__main__":
    main()
