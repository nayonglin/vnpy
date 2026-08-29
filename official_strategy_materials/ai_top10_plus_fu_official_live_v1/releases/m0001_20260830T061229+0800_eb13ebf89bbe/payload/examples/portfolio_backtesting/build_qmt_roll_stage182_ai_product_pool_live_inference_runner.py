from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
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
from qmt_roll_official_ai_pool_policy import (
    OFFICIAL_AI_FIXED_PRODUCT,
    OFFICIAL_AI_PRODUCT_POOL_STRATEGY,
    OFFICIAL_AI_RANKED_PRODUCT_COUNT,
    OFFICIAL_AI_TOTAL_PRODUCT_COUNT,
)


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
ELIGIBILITY_COLUMNS: list[str] = [
    "strategy",
    "score_type",
    "eval_date",
    "product_vt_symbol",
    "score",
    "score_rank",
    "top_n",
]
PRESERVED_COMBINED_SCORE_TYPE_PREFIXES: tuple[str, ...] = (
    "stage182_",
    "stage174_recovered_",
)


def _build_output_paths(output_dir: Path) -> dict[str, Path]:
    root = output_dir.expanduser().resolve(strict=False)
    return {
        "live_pool": root / LIVE_POOL_PATH.name,
        "live_eligibility": root / LIVE_ELIGIBILITY_PATH.name,
        "combined_eligibility": root / COMBINED_ELIGIBILITY_PATH.name,
        "summary": root / SUMMARY_PATH.name,
        "report": root / REPORT_PATH.name,
    }


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
    ranked_non_fixed = ranked[
        ~ranked["product_vt_symbol"].astype(str).eq(OFFICIAL_AI_FIXED_PRODUCT)
    ].copy()
    selected = ranked_non_fixed.head(OFFICIAL_AI_RANKED_PRODUCT_COUNT).copy()
    if len(selected) != OFFICIAL_AI_RANKED_PRODUCT_COUNT:
        raise ValueError("not enough non-fixed products for official Top10 AI pool")

    rows: list[dict[str, Any]] = []
    for rank, row in enumerate(selected.itertuples(index=False), start=1):
        rows.append(
            {
                "strategy": OFFICIAL_AI_PRODUCT_POOL_STRATEGY,
                "score_type": "stage182_live_monthly_ai_probability",
                "eval_date": eval_date.date().isoformat(),
                "product_vt_symbol": str(row.product_vt_symbol),
                "score": _safe_float(getattr(row, PROBABILITY_COLUMN)),
                "score_rank": rank,
                "top_n": OFFICIAL_AI_TOTAL_PRODUCT_COUNT,
            }
        )

    min_score = min((_safe_float(row["score"]) for row in rows), default=0.0)
    rows.append(
        {
            "strategy": OFFICIAL_AI_PRODUCT_POOL_STRATEGY,
            "score_type": "stage182_live_fixed_fu_satellite",
            "eval_date": eval_date.date().isoformat(),
            "product_vt_symbol": OFFICIAL_AI_FIXED_PRODUCT,
            "score": min_score - 1e-6,
            "score_rank": OFFICIAL_AI_TOTAL_PRODUCT_COUNT,
            "top_n": OFFICIAL_AI_TOTAL_PRODUCT_COUNT,
        }
    )

    result = pd.DataFrame(rows)
    result.sort_values(["eval_date", "score_rank", "product_vt_symbol"], inplace=True)
    result.reset_index(drop=True, inplace=True)
    return result


def _build_published_live_pool(
    scored_pool: pd.DataFrame,
    live_eligibility: pd.DataFrame,
) -> pd.DataFrame:
    """Build the exact decision rows consumed by formal reporting."""
    selected = live_eligibility[
        ["strategy", "eval_date", "product_vt_symbol", "score", "score_rank", "score_type"]
    ].copy()
    feature_rows = scored_pool.drop(
        columns=[
            "strategy",
            "eval_date",
            "ai_rank",
            "selection_role",
            "source_score_type",
        ],
        errors="ignore",
    ).copy()
    published = selected.merge(
        feature_rows,
        on="product_vt_symbol",
        how="left",
        validate="one_to_one",
    )
    model_ranks = scored_pool.set_index("product_vt_symbol").get("ai_rank")
    if model_ranks is not None:
        published["model_ai_rank"] = pd.to_numeric(
            published["product_vt_symbol"].map(model_ranks),
            errors="coerce",
        )
    published[PROBABILITY_COLUMN] = pd.to_numeric(published["score"], errors="raise")
    published["ai_rank"] = pd.to_numeric(published["score_rank"], errors="raise").astype(int)
    published["selection_role"] = published["product_vt_symbol"].map(
        lambda value: "fixed_fu" if str(value) == OFFICIAL_AI_FIXED_PRODUCT else "model_ranked"
    )
    published["source_score_type"] = published["score_type"].astype(str)
    published.drop(columns=["score", "score_rank", "score_type"], inplace=True)
    leading = [
        "strategy",
        "eval_date",
        "product_vt_symbol",
        PROBABILITY_COLUMN,
        "ai_rank",
        "selection_role",
        "source_score_type",
    ]
    trailing = [column for column in published.columns if column not in leading]
    published.sort_values(["ai_rank", "product_vt_symbol"], inplace=True)
    published.reset_index(drop=True, inplace=True)
    return published.loc[:, [*leading, *trailing]]


def _align_eligibility_schema(frame: pd.DataFrame) -> pd.DataFrame:
    aligned = frame.copy()
    for column in ELIGIBILITY_COLUMNS:
        if column not in aligned.columns:
            aligned[column] = ""
    aligned = aligned.loc[:, ELIGIBILITY_COLUMNS].copy()
    eval_dates = pd.to_datetime(aligned["eval_date"], errors="coerce")
    if eval_dates.isna().any():
        raise RuntimeError("stage182_eligibility_eval_date_invalid")
    aligned["eval_date"] = eval_dates.dt.date.astype(str)
    aligned["strategy"] = aligned["strategy"].astype(str)
    aligned["product_vt_symbol"] = aligned["product_vt_symbol"].astype(str).str.strip()
    if aligned["product_vt_symbol"].eq("").any():
        raise RuntimeError("stage182_eligibility_product_empty")
    for column in ("score", "score_rank", "top_n"):
        aligned[column] = pd.to_numeric(aligned[column], errors="coerce")
    numeric = aligned[["score", "score_rank", "top_n"]].to_numpy(dtype=float)
    if not np.isfinite(numeric).all():
        raise RuntimeError("stage182_eligibility_numeric_invalid")
    rank_values = aligned[["score_rank", "top_n"]].to_numpy(dtype=float)
    if not np.equal(rank_values, np.floor(rank_values)).all():
        raise RuntimeError("stage182_eligibility_rank_or_top_n_not_integer")
    aligned["score_rank"] = aligned["score_rank"].astype(int)
    aligned["top_n"] = aligned["top_n"].astype(int)
    return aligned


def _preservable_combined_snapshot_mask(frame: pd.DataFrame) -> pd.Series:
    score_type = frame["score_type"].astype(str)
    return score_type.map(
        lambda value: any(value.startswith(prefix) for prefix in PRESERVED_COMBINED_SCORE_TYPE_PREFIXES)
    )


def _build_combined_eligibility(
    live_eligibility: pd.DataFrame,
    *,
    seed_combined_eligibility_path: Path | None = None,
) -> tuple[pd.DataFrame, Path, dict[str, Any]]:
    if seed_combined_eligibility_path is None:
        raise RuntimeError("stage182_immutable_seed_combined_eligibility_required")
    seed_path = Path(seed_combined_eligibility_path).expanduser().resolve(strict=True)
    official_eligibility_path = seed_path
    official = pd.DataFrame(columns=ELIGIBILITY_COLUMNS)
    existing = _align_eligibility_schema(
        pd.read_csv(seed_path, encoding="utf-8-sig")
    )
    live = _align_eligibility_schema(live_eligibility)
    eval_dates = set(live_eligibility["eval_date"].astype(str))
    strategy = OFFICIAL_AI_PRODUCT_POOL_STRATEGY

    existing_strategy = existing[
        existing["strategy"].astype(str).eq(strategy)
        & _preservable_combined_snapshot_mask(existing)
    ].copy()
    preserved = existing_strategy[~existing_strategy["eval_date"].astype(str).isin(eval_dates)].copy()
    preserved_eval_dates = set(preserved["eval_date"].astype(str))
    official_keep = ~(
        official["strategy"].astype(str).eq(strategy)
        & official["eval_date"].astype(str).isin(eval_dates | preserved_eval_dates)
    )
    combined = pd.concat([official[official_keep].copy(), preserved, live], ignore_index=True)
    combined.sort_values(["eval_date", "score_rank", "product_vt_symbol"], inplace=True)
    combined.reset_index(drop=True, inplace=True)
    audit = {
        "official_rows": int(len(official)),
        "seed_combined_eligibility_path": str(seed_path),
        "existing_combined_rows": int(len(existing)),
        "preserved_live_snapshot_rows": int(len(preserved)),
        "preserved_live_snapshot_eval_dates": sorted(preserved_eval_dates),
        "current_live_eval_dates": sorted(eval_dates),
        "combined_rows": int(len(combined)),
        "combined_eval_date_count": int(combined["eval_date"].nunique()),
    }
    return combined, official_eligibility_path, audit


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


def _configure_source_paths(
    source_prefix: str,
    source_dir: Path = OUTPUT_DIR,
) -> dict[str, str]:
    root = source_dir.expanduser().resolve(strict=False)
    position_changes = root / f"{source_prefix}_position_changes_2020_2026_04.csv"
    entry_snapshots = root / f"{source_prefix}_entry_candidate_snapshots_2020_2026_04.csv"
    if not position_changes.exists():
        raise FileNotFoundError(f"missing source position changes: {position_changes}")
    if not entry_snapshots.exists():
        raise FileNotFoundError(f"missing source entry snapshots: {entry_snapshots}")
    suitability.POSITION_CHANGES_PATH = position_changes
    suitability.ENTRY_SNAPSHOTS_PATH = entry_snapshots
    return {
        "source_prefix": source_prefix,
        "source_dir": str(root),
        "position_changes": str(position_changes),
        "entry_candidate_snapshots": str(entry_snapshots),
    }


def _source_file_identity(path: Path) -> dict[str, int | str]:
    source = path.expanduser().resolve(strict=True)
    before = source.stat()
    digest = hashlib.sha256()
    with source.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    after = source.stat()
    if before.st_size != after.st_size or before.st_mtime_ns != after.st_mtime_ns:
        raise RuntimeError(f"source file changed while hashing: {source}")
    return {
        "size": int(after.st_size),
        "mtime_ns": int(after.st_mtime_ns),
        "sha256": digest.hexdigest(),
    }


def _collect_source_identities(
    source_paths: dict[str, str],
) -> dict[str, dict[str, int | str]]:
    return {
        name: _source_file_identity(Path(source_paths[name]))
        for name in ("position_changes", "entry_candidate_snapshots")
    }


def _assert_source_identities_unchanged(
    source_paths: dict[str, str],
    expected: dict[str, dict[str, int | str]],
) -> None:
    actual = _collect_source_identities(source_paths)
    if actual != expected:
        raise RuntimeError("Stage182 source files changed during inference")


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
            f"- Strategy: `{OFFICIAL_AI_PRODUCT_POOL_STRATEGY}`",
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
        "--source-dir",
        type=Path,
        default=OUTPUT_DIR,
        help="Directory containing Stage183 source artifacts.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=OUTPUT_DIR,
        help="Directory for Stage182 candidate outputs.",
    )
    parser.add_argument(
        "--seed-combined-eligibility",
        type=Path,
        required=True,
        help=(
            "Immutable active-material combined eligibility used as the only "
            "official-history seed for a production candidate."
        ),
    )
    parser.add_argument(
        "--allow-incomplete-month",
        action="store_true",
        help="Allow scoring on the latest available date even if its calendar month is incomplete.",
    )
    args = parser.parse_args()

    output_paths = _build_output_paths(args.output_dir)
    output_paths["summary"].parent.mkdir(parents=True, exist_ok=True)
    source_paths = _configure_source_paths(
        str(args.source_prefix),
        source_dir=args.source_dir,
    )
    source_identities = _collect_source_identities(source_paths)

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
    published_live_pool = _build_published_live_pool(live_pool, live_eligibility)
    combined, official_eligibility_path, combined_audit = _build_combined_eligibility(
        live_eligibility,
        seed_combined_eligibility_path=args.seed_combined_eligibility,
    )

    _assert_source_identities_unchanged(source_paths, source_identities)

    published_live_pool.to_csv(output_paths["live_pool"], index=False, encoding="utf-8-sig")
    live_eligibility.to_csv(output_paths["live_eligibility"], index=False, encoding="utf-8-sig")
    combined.to_csv(output_paths["combined_eligibility"], index=False, encoding="utf-8-sig")

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
        "live_rows": int(len(published_live_pool)),
        "scored_product_rows": int(len(live_pool)),
        "source_paths": source_paths,
        "source_identities": source_identities,
        "official_eligibility_path": str(official_eligibility_path),
        "combined_eligibility_audit": combined_audit,
        "outputs": {key: str(path) for key, path in output_paths.items()},
        "safety": {
            "overwrites_official_stage78_eligibility": False,
            "uses_future_label_for_eval_date": False,
            "real_order_enabled": False,
        },
    }
    output_paths["summary"].write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    output_paths["report"].write_text(
        build_report(summary, published_live_pool, live_eligibility),
        encoding="utf-8",
    )

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"report: {output_paths['report']}")


if __name__ == "__main__":
    main()
