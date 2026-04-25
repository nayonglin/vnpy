from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from analyze_qmt_roll_ai_product_suitability_walkforward import product_from_contract


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

MODEL_TAG: str = "full_market_product_toxicity_v1"
OUTPUT_PREFIX: str = "qmt_roll_full_market_product_toxicity"

UNIVERSE_PATH: Path = OUTPUT_DIR / "qmt_roll_full_market_tradable_universe_eligible_full_market_tradable_universe_v1.csv"
PRODUCT_FEATURES_PATH: Path = (
    OUTPUT_DIR / "qmt_roll_ai_product_suitability_full_market_walkforward_samples_product_suitability_full_market_wf_v1.csv"
)
POSITION_CHANGES_PATH: Path = (
    OUTPUT_DIR / "qmt_roll_selection_long015_volref30_corr_full_market_floor35_formal_position_changes_2020_2026_04.csv"
)
SHADOW_PRODUCT_PATH: Path = (
    OUTPUT_DIR
    / "qmt_roll_ai_product_pool_full_market_shadow_portfolio_product_attribution_ai_product_pool_full_market_shadow_v1.csv"
)
SHADOW_PRODUCT_YEAR_PATH: Path = (
    OUTPUT_DIR
    / "qmt_roll_ai_product_pool_full_market_shadow_portfolio_product_year_attribution_ai_product_pool_full_market_shadow_v1.csv"
)

TOXICITY_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_products_{MODEL_TAG}.csv"
SUMMARY_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.json"
REPORT_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


NUMERIC_FEATURE_COLUMNS: tuple[str, ...] = (
    "market_trend_efficiency_60d",
    "market_trend_efficiency_120d",
    "market_realized_vol_60d",
    "market_range_pct_mean_60d",
    "market_volume_ratio_60d",
    "market_open_interest_change_60d",
    "candidate_day_mean_120d",
    "trade_day_mean_120d",
    "opened_day_mean_120d",
    "avg_pairwise_score_mean_120d",
    "best_pairwise_rank_mean_120d",
)


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if pd.isna(result) or math.isinf(result):
        return default
    return result


def _percentile_rank(series: pd.Series, *, higher_is_risk: bool) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce").fillna(0.0)
    rank = numeric.rank(pct=True, method="average")
    return rank if higher_is_risk else 1.0 - rank


def _load_position_attribution() -> pd.DataFrame:
    if not POSITION_CHANGES_PATH.exists():
        raise FileNotFoundError(POSITION_CHANGES_PATH)

    columns = ["date", "vt_symbol", "net_pnl", "trade_count", "slippage"]
    df = pd.read_csv(POSITION_CHANGES_PATH, usecols=columns)
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    df["product_vt_symbol"] = df["vt_symbol"].map(product_from_contract)
    for column in ("net_pnl", "trade_count", "slippage"):
        df[column] = pd.to_numeric(df[column], errors="coerce").fillna(0.0)

    daily = (
        df.groupby(["product_vt_symbol", "date"], as_index=False)
        .agg(net_pnl=("net_pnl", "sum"), trade_count=("trade_count", "sum"), slippage=("slippage", "sum"))
        .sort_values(["product_vt_symbol", "date"])
    )

    rows: list[dict[str, Any]] = []
    for product, group in daily.groupby("product_vt_symbol", sort=False):
        group = group.copy()
        group["equity"] = group["net_pnl"].cumsum()
        group["highlevel"] = group["equity"].cummax()
        group["drawdown"] = group["equity"] - group["highlevel"]
        rows.append(
            {
                "product_vt_symbol": product,
                "full_net_pnl": float(group["net_pnl"].sum()),
                "full_trade_count": int(round(float(group["trade_count"].sum()))),
                "full_slippage": float(group["slippage"].sum()),
                "full_pnl_per_trade": _safe_float(group["net_pnl"].sum() / group["trade_count"].sum())
                if float(group["trade_count"].sum()) > 0
                else 0.0,
                "full_product_max_drawdown": float(group["drawdown"].min()),
                "full_active_days": int((group["net_pnl"] != 0.0).sum()),
            }
        )
    return pd.DataFrame(rows)


def _load_shadow_attribution() -> tuple[pd.DataFrame, pd.DataFrame]:
    if not SHADOW_PRODUCT_PATH.exists():
        raise FileNotFoundError(SHADOW_PRODUCT_PATH)
    if not SHADOW_PRODUCT_YEAR_PATH.exists():
        raise FileNotFoundError(SHADOW_PRODUCT_YEAR_PATH)

    product = pd.read_csv(SHADOW_PRODUCT_PATH)
    product = product[product["strategy"].astype(str) == "baseline_all_products"].copy()
    product.rename(
        columns={
            "original_net_pnl": "eval_net_pnl",
            "original_trade_count": "eval_trade_count",
            "original_slippage": "eval_slippage",
        },
        inplace=True,
    )
    keep_columns = [
        "product_vt_symbol",
        "eval_net_pnl",
        "eval_trade_count",
        "eval_slippage",
        "new_entry_rows",
    ]
    product = product[keep_columns].copy()

    year = pd.read_csv(SHADOW_PRODUCT_YEAR_PATH)
    year = year[year["strategy"].astype(str) == "baseline_all_products"].copy()
    yearly = (
        year.groupby("product_vt_symbol")
        .agg(
            eval_years=("year", "nunique"),
            eval_positive_years=("net_pnl", lambda values: int((pd.to_numeric(values, errors="coerce") > 0).sum())),
            eval_worst_year=("net_pnl", "min"),
            eval_best_year=("net_pnl", "max"),
        )
        .reset_index()
    )
    return product, yearly


def _load_structural_features() -> pd.DataFrame:
    if not PRODUCT_FEATURES_PATH.exists():
        raise FileNotFoundError(PRODUCT_FEATURES_PATH)

    df = pd.read_csv(PRODUCT_FEATURES_PATH, usecols=lambda column: column in {"product_vt_symbol", *NUMERIC_FEATURE_COLUMNS})
    for column in NUMERIC_FEATURE_COLUMNS:
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
            candidate_day_mean_120d_median=("candidate_day_mean_120d", "median"),
            trade_day_mean_120d_median=("trade_day_mean_120d", "median"),
            opened_day_mean_120d_median=("opened_day_mean_120d", "median"),
            avg_pairwise_score_mean_120d_median=("avg_pairwise_score_mean_120d", "median"),
            best_pairwise_rank_mean_120d_median=("best_pairwise_rank_mean_120d", "median"),
        )
        .reset_index()
    )


def build_toxicity_table() -> pd.DataFrame:
    if not UNIVERSE_PATH.exists():
        raise FileNotFoundError(UNIVERSE_PATH)

    universe = pd.read_csv(UNIVERSE_PATH)
    position = _load_position_attribution()
    shadow_product, shadow_year = _load_shadow_attribution()
    features = _load_structural_features()

    table = (
        universe.merge(position, on="product_vt_symbol", how="left")
        .merge(shadow_product, on="product_vt_symbol", how="left")
        .merge(shadow_year, on="product_vt_symbol", how="left")
        .merge(features, on="product_vt_symbol", how="left")
    )

    numeric_columns = [
        "full_net_pnl",
        "full_trade_count",
        "full_slippage",
        "full_pnl_per_trade",
        "full_product_max_drawdown",
        "eval_net_pnl",
        "eval_trade_count",
        "eval_slippage",
        "eval_positive_years",
        "eval_worst_year",
        "recent_median_volume",
        "estimated_margin_per_contract",
        "recent_bar_coverage_ratio",
        "market_trend_efficiency_60d_median",
        "market_trend_efficiency_120d_median",
        "market_realized_vol_60d_median",
        "market_range_pct_mean_60d_median",
    ]
    for column in numeric_columns:
        if column in table.columns:
            table[column] = pd.to_numeric(table[column], errors="coerce").fillna(0.0)

    table["new_product_flag"] = (pd.to_numeric(table["is_static_strategy_product"], errors="coerce").fillna(0) == 0).astype(int)
    table["eval_pnl_per_trade"] = np.where(
        table["eval_trade_count"] > 0,
        table["eval_net_pnl"] / table["eval_trade_count"],
        0.0,
    )

    table["performance_toxicity_score"] = (
        _percentile_rank(table["full_net_pnl"], higher_is_risk=False) * 0.35
        + _percentile_rank(table["eval_net_pnl"], higher_is_risk=False) * 0.35
        + _percentile_rank(table["full_product_max_drawdown"], higher_is_risk=False) * 0.20
        + _percentile_rank(table["full_slippage"], higher_is_risk=True) * 0.10
    )
    table["structural_fragility_score"] = (
        _percentile_rank(table["recent_median_volume"], higher_is_risk=False) * 0.25
        + _percentile_rank(table["estimated_margin_per_contract"], higher_is_risk=True) * 0.20
        + _percentile_rank(table["recent_bar_coverage_ratio"], higher_is_risk=False) * 0.20
        + _percentile_rank(table["market_trend_efficiency_60d_median"], higher_is_risk=False) * 0.20
        + _percentile_rank(table["market_range_pct_mean_60d_median"], higher_is_risk=False) * 0.15
    )
    table["toxicity_bucket"] = pd.cut(
        table["performance_toxicity_score"],
        bins=[-0.01, 0.33, 0.66, 1.01],
        labels=["low", "medium", "high"],
    ).astype(str)

    table.sort_values(
        ["performance_toxicity_score", "structural_fragility_score", "full_net_pnl"],
        ascending=[False, False, True],
        inplace=True,
    )
    table.reset_index(drop=True, inplace=True)
    return table


def _table(df: pd.DataFrame, columns: list[str], max_rows: int = 20) -> str:
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


def build_summary(table: pd.DataFrame) -> dict[str, Any]:
    by_static = (
        table.groupby("is_static_strategy_product")
        .agg(
            products=("product_vt_symbol", "count"),
            full_net_pnl=("full_net_pnl", "sum"),
            full_trade_count=("full_trade_count", "sum"),
            eval_net_pnl=("eval_net_pnl", "sum"),
            eval_trade_count=("eval_trade_count", "sum"),
            median_structural_fragility=("structural_fragility_score", "median"),
        )
        .reset_index()
        .to_dict(orient="records")
    )
    return {
        "model_tag": MODEL_TAG,
        "source_paths": {
            "universe": str(UNIVERSE_PATH),
            "product_features": str(PRODUCT_FEATURES_PATH),
            "position_changes": str(POSITION_CHANGES_PATH),
            "shadow_product": str(SHADOW_PRODUCT_PATH),
            "shadow_product_year": str(SHADOW_PRODUCT_YEAR_PATH),
        },
        "coverage": {
            "products": int(len(table)),
            "static_products": int((table["is_static_strategy_product"] == 1).sum()),
            "new_products": int((table["is_static_strategy_product"] == 0).sum()),
            "high_toxicity_products": int((table["toxicity_bucket"] == "high").sum()),
        },
        "static_vs_new": by_static,
        "worst_products": table.head(15).to_dict(orient="records"),
        "artifacts": {
            "toxicity_csv": str(TOXICITY_OUTPUT_PATH),
            "summary_json": str(SUMMARY_OUTPUT_PATH),
            "report_md": str(REPORT_OUTPUT_PATH),
        },
        "judgement": (
            "Performance toxicity is diagnostic only. Structural prefiltering must not select products by historical PnL."
        ),
    }


def build_report(table: pd.DataFrame, summary: dict[str, Any]) -> str:
    columns = [
        "product_vt_symbol",
        "is_static_strategy_product",
        "full_net_pnl",
        "eval_net_pnl",
        "full_trade_count",
        "eval_positive_years",
        "full_product_max_drawdown",
        "recent_median_volume",
        "estimated_margin_per_contract",
        "market_trend_efficiency_60d_median",
        "market_range_pct_mean_60d_median",
        "performance_toxicity_score",
        "structural_fragility_score",
    ]
    high_new = table[(table["is_static_strategy_product"] == 0) & (table["toxicity_bucket"] == "high")].copy()
    lines = [
        "# Full-Market Product Toxicity Attribution",
        "",
        "## Judgement",
        "",
        "- This report explains why the raw full-market expansion failed.",
        "- Historical PnL is used for diagnosis, not for selecting the next tradable universe.",
        "- New products must pass structural filters before AI ranking is allowed to operate on them.",
        "",
        "## Static Vs New Products",
        "",
        json.dumps(summary["static_vs_new"], ensure_ascii=False, indent=2),
        "",
        "## Worst Products",
        "",
        _table(table, columns, max_rows=20),
        "",
        "## High-Toxicity New Products",
        "",
        _table(high_new, columns, max_rows=20),
    ]
    return "\n".join(lines)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    table = build_toxicity_table()
    summary = build_summary(table)
    table.to_csv(TOXICITY_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    SUMMARY_OUTPUT_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_OUTPUT_PATH.write_text(build_report(table, summary), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
