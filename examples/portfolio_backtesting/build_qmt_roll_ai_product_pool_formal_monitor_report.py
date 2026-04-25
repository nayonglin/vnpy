from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

FORMAL_PREFIX: str = "qmt_roll_selection_long015_volref30_corr_ai_top8_product_pool_formal"
BASELINE_PREFIX: str = "qmt_roll_selection_long015_volref30_corr_formal_floor35"
OUTPUT_PREFIX: str = "qmt_roll_ai_product_pool_formal_monitor"
MODEL_TAG: str = "ai_top8_formal_monitor_v1"

SNAPSHOT_PATH: Path = OUTPUT_DIR / f"{FORMAL_PREFIX}_entry_candidate_snapshots_2020_2026_04.csv"
PRODUCT_DAILY_PATH: Path = OUTPUT_DIR / "qmt_roll_ai_product_suitability_walkforward_daily_product_suitability_wf_v1.csv"
PREDICTIONS_PATH: Path = OUTPUT_DIR / "qmt_roll_ai_product_suitability_market_walkforward_predictions_product_suitability_market_wf_v2.csv"
FORMAL_SUMMARY_PATH: Path = OUTPUT_DIR / "qmt_roll_selection_long015_volref30_corr_ai_product_pool_formal_summary.json"

LATEST_POOL_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_latest_pool_{MODEL_TAG}.csv"
BLOCKED_EVENTS_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_blocked_events_{MODEL_TAG}.csv"
BLOCKED_BY_YEAR_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_blocked_by_year_{MODEL_TAG}.csv"
BLOCKED_BY_PRODUCT_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_blocked_by_product_{MODEL_TAG}.csv"
BLOCKED_BY_SIGNAL_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_blocked_by_signal_{MODEL_TAG}.csv"
REVIEW_TEMPLATE_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_review_template_{MODEL_TAG}.csv"
SUMMARY_JSON_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.json"
REPORT_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

AI_SCORE_COLUMN: str = "predicted_product_suitability_probability"
SIMPLE_SCORE_COLUMN: str = "simple_trend_suitability_score"
FUTURE_WINDOWS: tuple[int, ...] = (20, 60)
TOP_N: int = 8
MISSED_TREND_60D_NET_PNL_THRESHOLD: float = 50_000.0
MISSED_TREND_60D_RUNUP_THRESHOLD: float = 100_000.0
AVOIDED_LOSS_60D_NET_PNL_THRESHOLD: float = -50_000.0
BORDERLINE_RANK_MAX: int = 12


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if pd.isna(result) or math.isinf(result):
        return default
    return result


def _safe_int(value: object, default: int = 0) -> int:
    try:
        if pd.isna(value):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def load_snapshots() -> pd.DataFrame:
    if not SNAPSHOT_PATH.exists():
        raise FileNotFoundError(f"missing candidate snapshots: {SNAPSHOT_PATH}")

    df = pd.read_csv(SNAPSHOT_PATH)
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    df["ai_product_pool_signal_date"] = pd.to_datetime(df["ai_product_pool_signal_date"], errors="coerce").dt.normalize()
    numeric_columns = [
        "selected_volume",
        "selection_pairwise_score",
        "selection_pairwise_rank",
        "ai_product_pool_score",
        "ai_product_pool_rank",
        "ai_product_pool_top_n",
        "is_opened",
    ]
    for column in numeric_columns:
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce").fillna(0.0)
    return df.sort_values(["date", "candidate_index"]).reset_index(drop=True)


def load_product_daily() -> pd.DataFrame:
    if not PRODUCT_DAILY_PATH.exists():
        raise FileNotFoundError(f"missing product daily: {PRODUCT_DAILY_PATH}")

    df = pd.read_csv(PRODUCT_DAILY_PATH)
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    numeric_columns = [
        "net_pnl",
        "total_pnl",
        "slippage",
        "commission",
        "trade_count",
        "opened_count",
        "selected_volume_sum",
        "abs_end_pos",
    ]
    for column in numeric_columns:
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce").fillna(0.0)
    return df.sort_values(["product_vt_symbol", "date"]).reset_index(drop=True)


def load_predictions() -> pd.DataFrame:
    if not PREDICTIONS_PATH.exists():
        raise FileNotFoundError(f"missing AI product predictions: {PREDICTIONS_PATH}")

    df = pd.read_csv(PREDICTIONS_PATH)
    df["eval_date"] = pd.to_datetime(df["eval_date"]).dt.normalize()
    for column in [AI_SCORE_COLUMN, SIMPLE_SCORE_COLUMN, "future_net_pnl_60d"]:
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce").fillna(0.0)

    df = df.sort_values(["eval_date", AI_SCORE_COLUMN], ascending=[True, False]).copy()
    df["ai_rank"] = df.groupby("eval_date")[AI_SCORE_COLUMN].rank(method="first", ascending=False).astype(int)
    df["allowed_top8"] = df["ai_rank"] <= TOP_N
    return df.reset_index(drop=True)


def load_formal_summary() -> dict[str, Any]:
    if not FORMAL_SUMMARY_PATH.exists():
        return {}
    return json.loads(FORMAL_SUMMARY_PATH.read_text(encoding="utf-8"))


def latest_pool(predictions: pd.DataFrame) -> pd.DataFrame:
    latest_eval_date = predictions["eval_date"].max()
    columns = [
        "eval_date",
        "product_vt_symbol",
        "ai_rank",
        "allowed_top8",
        AI_SCORE_COLUMN,
        SIMPLE_SCORE_COLUMN,
    ]
    return predictions[predictions["eval_date"] == latest_eval_date][columns].sort_values("ai_rank").reset_index(drop=True)


def prediction_rank_lookup(predictions: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "eval_date",
        "product_vt_symbol",
        "ai_rank",
        "allowed_top8",
        AI_SCORE_COLUMN,
        SIMPLE_SCORE_COLUMN,
    ]
    return predictions[columns].copy()


def future_path_stats(product_daily: pd.DataFrame, product: str, date: pd.Timestamp, window: int) -> dict[str, float]:
    product_rows = product_daily[product_daily["product_vt_symbol"] == product]
    future = product_rows[product_rows["date"] > date].head(window).copy()
    if future.empty:
        return {
            f"fwd{window}_available_days": 0.0,
            f"fwd{window}_net_pnl": 0.0,
            f"fwd{window}_max_runup": 0.0,
            f"fwd{window}_max_drawdown": 0.0,
            f"fwd{window}_positive_day_rate": 0.0,
            f"fwd{window}_trade_count": 0.0,
            f"fwd{window}_slippage": 0.0,
            f"fwd{window}_opened_count": 0.0,
        }

    net_pnl = future["net_pnl"].to_numpy(dtype=float)
    cumulative = np.cumsum(net_pnl)
    positive_rate = float((future["net_pnl"] > 0.0).mean())
    return {
        f"fwd{window}_available_days": float(len(future)),
        f"fwd{window}_net_pnl": float(future["net_pnl"].sum()),
        f"fwd{window}_max_runup": float(cumulative.max()) if len(cumulative) else 0.0,
        f"fwd{window}_max_drawdown": float(cumulative.min()) if len(cumulative) else 0.0,
        f"fwd{window}_positive_day_rate": positive_rate,
        f"fwd{window}_trade_count": float(future["trade_count"].sum()) if "trade_count" in future else 0.0,
        f"fwd{window}_slippage": float(future["slippage"].sum()) if "slippage" in future else 0.0,
        f"fwd{window}_opened_count": float(future["opened_count"].sum()) if "opened_count" in future else 0.0,
    }


def build_blocked_events(
    snapshots: pd.DataFrame,
    product_daily: pd.DataFrame,
    predictions: pd.DataFrame,
) -> pd.DataFrame:
    blocked = snapshots[snapshots["skip_reason"] == "ai_product_pool_blocked"].copy()
    if blocked.empty:
        return blocked

    ranks = prediction_rank_lookup(predictions).rename(columns={"eval_date": "ai_product_pool_signal_date"})
    blocked = blocked.merge(ranks, on=["ai_product_pool_signal_date", "product_vt_symbol"], how="left")
    blocked["model_ai_rank"] = blocked["ai_rank"].fillna(0).map(_safe_int)
    blocked["model_ai_score"] = blocked[AI_SCORE_COLUMN].fillna(0.0).map(_safe_float)
    blocked["model_simple_score"] = blocked[SIMPLE_SCORE_COLUMN].fillna(0.0).map(_safe_float)
    blocked["model_allowed_top8"] = blocked["allowed_top8"].fillna(False).astype(bool)
    blocked["borderline_rank_9_to_12"] = blocked["model_ai_rank"].between(TOP_N + 1, BORDERLINE_RANK_MAX)

    counts = blocked.groupby(["ai_product_pool_signal_date", "product_vt_symbol"]).cumcount() + 1
    blocked["repeat_block_count_in_signal_product"] = counts.astype(int)

    future_rows: list[dict[str, float]] = []
    for row in blocked.itertuples(index=False):
        payload: dict[str, float] = {}
        for window in FUTURE_WINDOWS:
            payload.update(future_path_stats(product_daily, str(row.product_vt_symbol), pd.Timestamp(row.date), window))
        future_rows.append(payload)
    future_df = pd.DataFrame(future_rows, index=blocked.index)
    blocked = pd.concat([blocked, future_df], axis=1)

    blocked["missed_trend_event_60d"] = (
        (blocked["fwd60_available_days"] >= min(40, FUTURE_WINDOWS[-1]))
        & (
            (blocked["fwd60_net_pnl"] >= MISSED_TREND_60D_NET_PNL_THRESHOLD)
            | (blocked["fwd60_max_runup"] >= MISSED_TREND_60D_RUNUP_THRESHOLD)
        )
    )
    blocked["avoided_loss_event_60d"] = (
        (blocked["fwd60_available_days"] >= min(40, FUTURE_WINDOWS[-1]))
        & (blocked["fwd60_net_pnl"] <= AVOIDED_LOSS_60D_NET_PNL_THRESHOLD)
    )

    output_columns = [
        "date",
        "product_vt_symbol",
        "contract_vt_symbol",
        "direction",
        "signal",
        "candidate_status",
        "skip_reason",
        "selected_volume",
        "selection_pairwise_score",
        "selection_pairwise_rank",
        "ai_product_pool_signal_date",
        "model_ai_rank",
        "model_ai_score",
        "model_simple_score",
        "model_allowed_top8",
        "borderline_rank_9_to_12",
        "repeat_block_count_in_signal_product",
        "missed_trend_event_60d",
        "avoided_loss_event_60d",
    ]
    for window in FUTURE_WINDOWS:
        output_columns.extend(
            [
                f"fwd{window}_available_days",
                f"fwd{window}_net_pnl",
                f"fwd{window}_max_runup",
                f"fwd{window}_max_drawdown",
                f"fwd{window}_positive_day_rate",
                f"fwd{window}_trade_count",
                f"fwd{window}_slippage",
                f"fwd{window}_opened_count",
            ]
        )
    return blocked[output_columns].sort_values(["date", "product_vt_symbol"]).reset_index(drop=True)


def aggregate_blocked_by_year(blocked: pd.DataFrame) -> pd.DataFrame:
    if blocked.empty:
        return pd.DataFrame()
    df = blocked.copy()
    df["year"] = df["date"].dt.year
    return (
        df.groupby("year")
        .agg(
            blocked_count=("product_vt_symbol", "size"),
            unique_blocked_products=("product_vt_symbol", "nunique"),
            borderline_rank_count=("borderline_rank_9_to_12", "sum"),
            missed_trend_event_60d_count=("missed_trend_event_60d", "sum"),
            avoided_loss_event_60d_count=("avoided_loss_event_60d", "sum"),
            fwd20_net_pnl_mean=("fwd20_net_pnl", "mean"),
            fwd60_net_pnl_mean=("fwd60_net_pnl", "mean"),
            fwd60_net_pnl_median=("fwd60_net_pnl", "median"),
            fwd60_positive_event_rate=("fwd60_net_pnl", lambda series: float((series > 0.0).mean())),
            fwd60_max_runup_max=("fwd60_max_runup", "max"),
            fwd60_max_drawdown_min=("fwd60_max_drawdown", "min"),
        )
        .reset_index()
        .sort_values("year")
    )


def aggregate_blocked_by_product(blocked: pd.DataFrame) -> pd.DataFrame:
    if blocked.empty:
        return pd.DataFrame()
    return (
        blocked.groupby("product_vt_symbol")
        .agg(
            blocked_count=("product_vt_symbol", "size"),
            first_block_date=("date", "min"),
            last_block_date=("date", "max"),
            mean_ai_rank=("model_ai_rank", "mean"),
            borderline_rank_count=("borderline_rank_9_to_12", "sum"),
            missed_trend_event_60d_count=("missed_trend_event_60d", "sum"),
            avoided_loss_event_60d_count=("avoided_loss_event_60d", "sum"),
            fwd20_net_pnl_mean=("fwd20_net_pnl", "mean"),
            fwd60_net_pnl_mean=("fwd60_net_pnl", "mean"),
            fwd60_net_pnl_median=("fwd60_net_pnl", "median"),
            fwd60_positive_event_rate=("fwd60_net_pnl", lambda series: float((series > 0.0).mean())),
            fwd60_max_runup_max=("fwd60_max_runup", "max"),
            fwd60_max_drawdown_min=("fwd60_max_drawdown", "min"),
        )
        .reset_index()
        .sort_values(["missed_trend_event_60d_count", "fwd60_max_runup_max", "blocked_count"], ascending=[False, False, False])
    )


def aggregate_blocked_by_signal(blocked: pd.DataFrame) -> pd.DataFrame:
    if blocked.empty:
        return pd.DataFrame()
    return (
        blocked.groupby("ai_product_pool_signal_date")
        .agg(
            blocked_count=("product_vt_symbol", "size"),
            unique_blocked_products=("product_vt_symbol", "nunique"),
            borderline_rank_count=("borderline_rank_9_to_12", "sum"),
            missed_trend_event_60d_count=("missed_trend_event_60d", "sum"),
            avoided_loss_event_60d_count=("avoided_loss_event_60d", "sum"),
            fwd60_net_pnl_mean=("fwd60_net_pnl", "mean"),
            fwd60_max_runup_max=("fwd60_max_runup", "max"),
            fwd60_max_drawdown_min=("fwd60_max_drawdown", "min"),
        )
        .reset_index()
        .sort_values("ai_product_pool_signal_date")
    )


def build_review_template(pool: pd.DataFrame) -> pd.DataFrame:
    review = pool.copy()
    review["manual_review_status"] = np.where(review["allowed_top8"], "keep_allowed", "monitor_only")
    review["manual_override_allowed"] = False
    review["override_reason"] = ""
    review["future_path_watch_required"] = np.where(review["allowed_top8"], False, review["ai_rank"].between(TOP_N + 1, BORDERLINE_RANK_MAX))
    review["review_note"] = ""
    return review


def to_markdown_table(df: pd.DataFrame, max_rows: int = 20) -> str:
    if df.empty:
        return "_empty_"

    view = df.head(max_rows).copy()
    for column in view.columns:
        if pd.api.types.is_datetime64_any_dtype(view[column]):
            view[column] = view[column].dt.strftime("%Y-%m-%d")
        elif pd.api.types.is_bool_dtype(view[column]):
            view[column] = view[column].map(lambda value: "1" if value else "0")
        elif pd.api.types.is_float_dtype(view[column]):
            view[column] = view[column].map(lambda value: f"{value:.4f}")
    header = "| " + " | ".join(view.columns) + " |"
    separator = "| " + " | ".join(["---"] * len(view.columns)) + " |"
    rows = ["| " + " | ".join(map(str, row)) + " |" for row in view.to_numpy()]
    return "\n".join([header, separator, *rows])


def build_report(
    *,
    pool: pd.DataFrame,
    blocked: pd.DataFrame,
    by_year: pd.DataFrame,
    by_product: pd.DataFrame,
    formal_summary: dict[str, Any],
) -> str:
    top_pool = pool[pool["allowed_top8"]].copy()
    top_pool = top_pool[
        [
            "eval_date",
            "product_vt_symbol",
            "ai_rank",
            AI_SCORE_COLUMN,
            SIMPLE_SCORE_COLUMN,
        ]
    ]
    top_missed = blocked.sort_values(["missed_trend_event_60d", "fwd60_max_runup", "fwd60_net_pnl"], ascending=False)[
        [
            "date",
            "product_vt_symbol",
            "direction",
            "ai_product_pool_signal_date",
            "model_ai_rank",
            "borderline_rank_9_to_12",
            "fwd20_net_pnl",
            "fwd60_net_pnl",
            "fwd60_max_runup",
            "fwd60_max_drawdown",
            "missed_trend_event_60d",
            "avoided_loss_event_60d",
        ]
    ]
    product_view = by_product[
        [
            "product_vt_symbol",
            "blocked_count",
            "mean_ai_rank",
            "borderline_rank_count",
            "missed_trend_event_60d_count",
            "avoided_loss_event_60d_count",
            "fwd60_net_pnl_mean",
            "fwd60_max_runup_max",
            "fwd60_max_drawdown_min",
        ]
    ]

    experiments = formal_summary.get("experiments", [])
    metrics = experiments[0] if experiments else formal_summary.get("statistics", formal_summary)
    lines = [
        "# AI Product Pool Formal Monitor",
        "",
        "## Scope",
        "",
        f"- Formal strategy prefix: `{FORMAL_PREFIX}`",
        f"- Baseline product attribution prefix: `{BASELINE_PREFIX}`",
        f"- Rule frozen: AI Top `{TOP_N}` entry filter.",
        f"- Missed trend label: `fwd60_net_pnl >= {MISSED_TREND_60D_NET_PNL_THRESHOLD:,.0f}` or `fwd60_max_runup >= {MISSED_TREND_60D_RUNUP_THRESHOLD:,.0f}`.",
        f"- Avoided loss label: `fwd60_net_pnl <= {AVOIDED_LOSS_60D_NET_PNL_THRESHOLD:,.0f}`.",
        "",
        "## Current Formal Candidate",
        "",
        f"- End balance: `{_safe_float(metrics.get('end_balance')):,.0f}`",
        f"- Total return: `{_safe_float(metrics.get('total_return_pct')):.2f}%`",
        f"- Max drawdown: `{_safe_float(metrics.get('max_dd_percent')):.2f}%`",
        f"- Sharpe: `{_safe_float(metrics.get('sharpe_ratio')):.4f}`",
        f"- Total slippage: `{_safe_float(metrics.get('total_slippage')):,.0f}`",
        f"- Total trades: `{_safe_float(metrics.get('total_trade_count')):,.0f}`",
        "",
        "## Latest Pool",
        "",
        to_markdown_table(top_pool, max_rows=TOP_N),
        "",
        "## Blocked Event Summary By Year",
        "",
        to_markdown_table(by_year),
        "",
        "## Blocked Product Risk Ranking",
        "",
        to_markdown_table(product_view),
        "",
        "## Highest Missed-Trend Risk Events",
        "",
        to_markdown_table(top_missed, max_rows=25),
        "",
        "## Governance Judgement",
        "",
        "- This report is a monitor, not a new optimization layer.",
        "- Event forward PnL is an overlapping path label and must not be summed as hypothetical portfolio profit.",
        "- Borderline blocked products with repeated candidates deserve manual review, but a single event is not enough to override the filter.",
        "- If future live logs show rising repeated blocks in rank 9-12 products, add a review process before changing the model.",
    ]
    return "\n".join(lines)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    snapshots = load_snapshots()
    product_daily = load_product_daily()
    predictions = load_predictions()
    formal_summary = load_formal_summary()

    pool = latest_pool(predictions)
    blocked = build_blocked_events(snapshots, product_daily, predictions)
    by_year = aggregate_blocked_by_year(blocked)
    by_product = aggregate_blocked_by_product(blocked)
    by_signal = aggregate_blocked_by_signal(blocked)
    review_template = build_review_template(pool)

    pool.to_csv(LATEST_POOL_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    blocked.to_csv(BLOCKED_EVENTS_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    by_year.to_csv(BLOCKED_BY_YEAR_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    by_product.to_csv(BLOCKED_BY_PRODUCT_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    by_signal.to_csv(BLOCKED_BY_SIGNAL_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    review_template.to_csv(REVIEW_TEMPLATE_OUTPUT_PATH, index=False, encoding="utf-8-sig")

    latest_allowed_products = pool[pool["allowed_top8"]]["product_vt_symbol"].astype(str).tolist()
    summary = {
        "model_tag": MODEL_TAG,
        "formal_prefix": FORMAL_PREFIX,
        "baseline_prefix_for_forward_path": BASELINE_PREFIX,
        "latest_eval_date": pool["eval_date"].max().date().isoformat() if not pool.empty else "",
        "top_n": TOP_N,
        "latest_allowed_products": latest_allowed_products,
        "blocked_event_count": int(len(blocked)),
        "borderline_blocked_event_count": int(blocked["borderline_rank_9_to_12"].sum()) if not blocked.empty else 0,
        "missed_trend_event_60d_count": int(blocked["missed_trend_event_60d"].sum()) if not blocked.empty else 0,
        "avoided_loss_event_60d_count": int(blocked["avoided_loss_event_60d"].sum()) if not blocked.empty else 0,
        "thresholds": {
            "missed_trend_60d_net_pnl": MISSED_TREND_60D_NET_PNL_THRESHOLD,
            "missed_trend_60d_max_runup": MISSED_TREND_60D_RUNUP_THRESHOLD,
            "avoided_loss_60d_net_pnl": AVOIDED_LOSS_60D_NET_PNL_THRESHOLD,
            "borderline_rank_max": BORDERLINE_RANK_MAX,
        },
        "blocked_by_year": by_year.to_dict(orient="records"),
        "blocked_by_product_top10": by_product.head(10).to_dict(orient="records"),
        "formal_summary_source": str(FORMAL_SUMMARY_PATH),
        "artifacts": {
            "latest_pool_csv": str(LATEST_POOL_OUTPUT_PATH),
            "blocked_events_csv": str(BLOCKED_EVENTS_OUTPUT_PATH),
            "blocked_by_year_csv": str(BLOCKED_BY_YEAR_OUTPUT_PATH),
            "blocked_by_product_csv": str(BLOCKED_BY_PRODUCT_OUTPUT_PATH),
            "blocked_by_signal_csv": str(BLOCKED_BY_SIGNAL_OUTPUT_PATH),
            "review_template_csv": str(REVIEW_TEMPLATE_OUTPUT_PATH),
            "summary_json": str(SUMMARY_JSON_OUTPUT_PATH),
            "report_md": str(REPORT_OUTPUT_PATH),
        },
        "judgement": (
            "Freeze AI Top8 as a product-terrain entry filter. Monitor blocked rank 9-12 repeated candidates "
            "and future missed-trend labels before any override or parameter change."
        ),
    }
    SUMMARY_JSON_OUTPUT_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    REPORT_OUTPUT_PATH.write_text(
        build_report(
            pool=pool,
            blocked=blocked,
            by_year=by_year,
            by_product=by_product,
            formal_summary=formal_summary,
        ),
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
