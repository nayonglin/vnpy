from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


LINE_ID = "futures_trend_c9_minrisk_highquality"
STAGE = "Stage081"
MODEL_TAG = "stage081_noise_floor_stop_distance_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage081_c9_minrisk_noise_floor_stop_distance_audit"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
TOOL_DIR = SCRIPT_PATH.parent
EXAMPLE_DIR = REPO_DIR / "examples" / "portfolio_backtesting"
for item in [str(TOOL_DIR), str(EXAMPLE_DIR)]:
    if item not in sys.path:
        sys.path.insert(0, item)

import stage008_no_follow_reduce_true_engine as s008
from main_contract_mapping import build_daily_mapping
from qmt_roll_official_live_config import OFFICIAL_LIVE_ALIAS, OFFICIAL_LIVE_VERSION


LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage081_noise_floor_stop_distance_audit"

FEATURES_IN = (
    LINE_DIR
    / "outputs"
    / "stage024_preentry_risk_granularity_forensics"
    / "qmt_roll_stage024_c9_minrisk_preentry_risk_granularity_forensics_features_"
    "stage024_preentry_risk_granularity_forensics_v1.csv"
)
OFFICIAL_CURVE_IN = (
    LINE_DIR
    / "outputs"
    / "stage010_authoritative_minute_coverage_audit"
    / "qmt_roll_stage010_c9_minrisk_authoritative_minute_coverage_audit_official_curve_"
    "stage010_authoritative_minute_coverage_audit_v1.csv"
)
OFFICIAL_SUMMARY_IN = (
    LINE_DIR
    / "outputs"
    / "stage010_authoritative_minute_coverage_audit"
    / "qmt_roll_stage010_c9_minrisk_authoritative_minute_coverage_audit_summary_"
    "stage010_authoritative_minute_coverage_audit_v1.csv"
)

FEATURES_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_features_{MODEL_TAG}.csv"
SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
BUCKET_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_bucket_summary_{MODEL_TAG}.csv"
YEAR_MATRIX_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_bucket_year_matrix_{MODEL_TAG}.csv"
CONTRIBUTION_CURVE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_contribution_curve_{MODEL_TAG}.csv"
DAILY_NOISE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_noise_{MODEL_TAG}.csv"
ATLAS_MANIFEST_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_atlas_manifest_{MODEL_TAG}.csv"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_noise_floor_chart_{MODEL_TAG}.png"
SCATTER_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_noise_ratio_scatter_{MODEL_TAG}.png"
HEATMAP_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_bucket_year_heatmap_{MODEL_TAG}.png"
ATLAS_TEMPLATE = OUTPUT_DIR / f"{OUTPUT_PREFIX}_atlas_page{{page:03d}}_{MODEL_TAG}.png"

START = pd.Timestamp("2018-01-01")
END = pd.Timestamp("2026-06-15")
CAPITAL = 150_000.0
NOISE_LOOKBACK_DAYS = 20
NOISE_MIN_PERIODS = 10
UNDER_FLOOR_RATIO = 1.0
MAX_ATLAS_ROWS = 16
ATLAS_BARS = 120
PER_PAGE = 4


def _json_safe(value: Any) -> Any:
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        if np.isnan(value) or np.isinf(value):
            return None
        return float(value)
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value


def _read_required_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise RuntimeError(f"missing required input: {path}")
    return pd.read_csv(path, encoding="utf-8-sig")


def _safe_float(value: Any, default: float = np.nan) -> float:
    try:
        if pd.isna(value):
            return default
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if np.isfinite(number) else default


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_empty_"
    data = frame.copy()
    if max_rows is not None:
        data = data.head(max_rows)
    display = data.copy()
    for column in display.columns:
        if pd.api.types.is_float_dtype(display[column]):
            display[column] = display[column].map(lambda value: "" if pd.isna(value) else f"{value:.4f}")
    headers = [str(column) for column in display.columns]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for _, row in display.iterrows():
        lines.append("| " + " | ".join(str(row[column]) for column in display.columns) + " |")
    return "\n".join(lines)


def _prepare_features() -> pd.DataFrame:
    data = _read_required_csv(FEATURES_IN)
    required = [
        "lot_id",
        "vt_symbol",
        "product",
        "direction",
        "entry_date",
        "exit_date",
        "entry_price",
        "realized_pnl",
        "risk_amount",
        "r_multiple",
        "volume",
        "size",
        "stop_distance",
        "entry_risk_distance_pct",
        "selected_volume",
        "target_risk_amount",
        "big_winner",
        "exit_reason",
        "stage861_covered",
    ]
    missing = [column for column in required if column not in data.columns]
    if missing:
        raise RuntimeError(f"missing required columns in features: {missing}")

    keep = required + [
        column
        for column in [
            "risk_multiplier",
            "loss_streak",
            "ai_product_pool_rank",
            "portfolio_drawdown_pct",
            "first_30m_directional_r",
            "first_30m_mfe_r",
            "first_30m_mae_r",
            "entry_day_mfe_r",
            "entry_day_mae_r",
            "entry_open_gap_r",
            "first_bar_directional_r",
            "tag_entry_or_first_aligned",
            "preentry_system_stress",
            "prev_broker10_margin_to_equity_pct",
            "prev_rolling20_ann_vol_pct",
        ]
        if column in data.columns
    ]
    data = data[keep].copy()
    data["entry_date"] = pd.to_datetime(data["entry_date"], errors="coerce").dt.normalize()
    data["exit_date"] = pd.to_datetime(data["exit_date"], errors="coerce").dt.normalize()
    data = data.dropna(subset=["entry_date", "exit_date", "vt_symbol", "entry_price"]).reset_index(drop=True)
    for column in [
        "entry_price",
        "realized_pnl",
        "risk_amount",
        "r_multiple",
        "volume",
        "size",
        "stop_distance",
        "entry_risk_distance_pct",
        "selected_volume",
        "target_risk_amount",
        "stage861_covered",
    ]:
        data[column] = pd.to_numeric(data[column], errors="coerce")
    data["entry_year"] = data["entry_date"].dt.year
    data["product_key"] = data["product"].fillna(data["vt_symbol"]).astype(str)
    data["positive_pnl"] = data["realized_pnl"].where(data["realized_pnl"] > 0.0, 0.0)
    data["negative_pnl"] = data["realized_pnl"].where(data["realized_pnl"] < 0.0, 0.0)
    return data


def _daily_noise_from_minutes(
    minute_bars: pd.DataFrame,
    source_symbol_by_contract: dict[str, str],
    daily_mapping: dict[str, dict[str, str]],
) -> pd.DataFrame:
    data = minute_bars.copy()
    data["bar_datetime"] = pd.to_datetime(data["bar_datetime"], errors="coerce")
    data["bar_date"] = pd.to_datetime(data["bar_date"], errors="coerce").dt.normalize()
    for column in ["high", "low", "close", "volume"]:
        data[column] = pd.to_numeric(data[column], errors="coerce")
    data = data.dropna(subset=["vt_symbol", "bar_date", "high", "low", "close"])
    daily = (
        data.groupby(["vt_symbol", "bar_date"], as_index=False)
        .agg(
            day_high=("high", "max"),
            day_low=("low", "min"),
            day_close=("close", "last"),
            minute_bars=("close", "size"),
            day_volume=("volume", "sum"),
        )
        .sort_values(["vt_symbol", "bar_date"])
        .reset_index(drop=True)
    )
    daily["product_vt_symbol"] = daily["vt_symbol"].map(source_symbol_by_contract).fillna(daily["vt_symbol"])

    mapping_rows: list[dict[str, str]] = []
    for date_text, product_map in daily_mapping.items():
        for product_vt_symbol, main_contract_vt in product_map.items():
            mapping_rows.append(
                {
                    "bar_date": pd.Timestamp(date_text).normalize(),
                    "product_vt_symbol": str(product_vt_symbol),
                    "main_contract_vt": str(main_contract_vt),
                }
            )
    mapping = pd.DataFrame(mapping_rows)
    if mapping.empty:
        daily["main_contract_vt"] = ""
    else:
        daily = daily.merge(mapping, on=["product_vt_symbol", "bar_date"], how="left")
        daily["main_contract_vt"] = daily["main_contract_vt"].fillna("")
    daily["mapping_main_match"] = daily["vt_symbol"].eq(daily["main_contract_vt"])

    daily = daily.sort_values(
        [
            "product_vt_symbol",
            "bar_date",
            "mapping_main_match",
            "day_volume",
            "minute_bars",
            "vt_symbol",
        ],
        ascending=[True, True, False, False, False, True],
    )
    product_daily = daily.drop_duplicates(subset=["product_vt_symbol", "bar_date"], keep="first").copy()
    product_daily = product_daily.sort_values(["product_vt_symbol", "bar_date"]).reset_index(drop=True)
    product_daily["noise_source_contract"] = product_daily["vt_symbol"]
    product_daily["noise_source_mapping_match"] = product_daily["mapping_main_match"].astype(int)

    product_daily["prev_close"] = product_daily.groupby("product_vt_symbol")["day_close"].shift(1)
    high_low = product_daily["day_high"] - product_daily["day_low"]
    high_prev = (product_daily["day_high"] - product_daily["prev_close"]).abs()
    low_prev = (product_daily["day_low"] - product_daily["prev_close"]).abs()
    product_daily["true_range"] = pd.concat([high_low, high_prev, low_prev], axis=1).max(axis=1)
    product_daily["day_range"] = high_low

    def _rolling_prior(series: pd.Series) -> pd.Series:
        return series.shift(1).rolling(NOISE_LOOKBACK_DAYS, min_periods=NOISE_MIN_PERIODS).median()

    product_daily["prior20_median_true_range"] = (
        product_daily.groupby("product_vt_symbol", group_keys=False)["true_range"].apply(_rolling_prior)
    )
    product_daily["prior20_median_day_range"] = (
        product_daily.groupby("product_vt_symbol", group_keys=False)["day_range"].apply(_rolling_prior)
    )
    return product_daily


def _attach_noise(features: pd.DataFrame, daily: pd.DataFrame) -> pd.DataFrame:
    merged = features.merge(
        daily[
            [
                "product_vt_symbol",
                "bar_date",
                "noise_source_contract",
                "noise_source_mapping_match",
                "minute_bars",
                "day_volume",
                "day_range",
                "true_range",
                "prior20_median_true_range",
                "prior20_median_day_range",
            ]
        ],
        left_on=["product_key", "entry_date"],
        right_on=["product_vt_symbol", "bar_date"],
        how="left",
    )
    merged["noise_ready"] = (
        merged["prior20_median_true_range"].gt(0)
        & merged["stop_distance"].gt(0)
        & merged["entry_price"].gt(0)
        & merged["size"].gt(0)
    )
    merged["stop_to_noise_ratio"] = np.where(
        merged["noise_ready"],
        merged["stop_distance"] / merged["prior20_median_true_range"],
        np.nan,
    )
    merged["noise_floor_distance"] = merged["prior20_median_true_range"]
    merged["noise_floor_pct"] = merged["noise_floor_distance"] / merged["entry_price"]
    merged["noise_floor_gap"] = merged["noise_floor_distance"] - merged["stop_distance"]
    merged["under_noise_floor"] = merged["noise_ready"] & merged["stop_to_noise_ratio"].lt(UNDER_FLOOR_RATIO)
    floor_risk_per_contract = merged["noise_floor_distance"] * merged["size"]
    merged["noise_floor_risk_per_contract"] = floor_risk_per_contract
    merged["noise_floor_cash_risk_if_same_volume"] = floor_risk_per_contract * merged["volume"]
    merged["noise_floor_preserve_risk_volume"] = np.floor(
        merged["risk_amount"] / floor_risk_per_contract.replace(0.0, np.nan)
    )
    merged["noise_floor_preserve_risk_volume"] = merged["noise_floor_preserve_risk_volume"].replace(
        [np.inf, -np.inf], np.nan
    )
    merged["noise_floor_min1_cash_risk_ratio"] = floor_risk_per_contract / merged["risk_amount"].replace(0.0, np.nan)
    merged["noise_floor_feasible_min1"] = merged["noise_floor_preserve_risk_volume"].ge(1)

    labels = ["ratio_lt0_5", "ratio_0_5_1", "ratio_1_2", "ratio_ge2"]
    merged["noise_ratio_bucket"] = pd.cut(
        merged["stop_to_noise_ratio"],
        bins=[-np.inf, 0.5, 1.0, 2.0, np.inf],
        labels=labels,
        include_lowest=True,
    ).astype(object)
    merged.loc[~merged["noise_ready"], "noise_ratio_bucket"] = "missing"
    merged["noise_ratio_bucket"] = merged["noise_ratio_bucket"].astype(str)
    merged["noise_floor_state"] = np.where(
        ~merged["noise_ready"],
        "missing_noise",
        np.where(merged["under_noise_floor"], "under_noise_floor", "adequate_or_wide_stop"),
    )
    return merged


def _bucket_summary(features: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for family, column in [
        ("floor_state", "noise_floor_state"),
        ("ratio_bucket", "noise_ratio_bucket"),
    ]:
        for bucket, group in features.groupby(column, dropna=False):
            lots = len(group)
            pnl = float(group["realized_pnl"].sum())
            pos = float(group["positive_pnl"].sum())
            neg = float(group["negative_pnl"].sum())
            rows.append(
                {
                    "family": family,
                    "bucket": str(bucket),
                    "lots": lots,
                    "products": int(group["product_key"].nunique()),
                    "entry_years": int(group["entry_year"].nunique()),
                    "net_pnl": pnl,
                    "positive_pnl": pos,
                    "negative_pnl": neg,
                    "win_rate_pct": float(group["realized_pnl"].gt(0).mean() * 100.0) if lots else np.nan,
                    "avg_r_multiple": float(group["r_multiple"].mean()) if lots else np.nan,
                    "median_stop_to_noise_ratio": float(group["stop_to_noise_ratio"].median()) if lots else np.nan,
                    "big_winner_lots": int(pd.to_numeric(group["big_winner"], errors="coerce").fillna(0).gt(0).sum()),
                    "feasible_min1_lots": int(group["noise_floor_feasible_min1"].fillna(False).sum()),
                }
            )
    return pd.DataFrame(rows).sort_values(["family", "bucket"]).reset_index(drop=True)


def _year_matrix(features: pd.DataFrame) -> pd.DataFrame:
    grouped = (
        features.groupby(["entry_year", "noise_ratio_bucket"], as_index=False)
        .agg(
            lots=("lot_id", "count"),
            net_pnl=("realized_pnl", "sum"),
            positive_pnl=("positive_pnl", "sum"),
            negative_pnl=("negative_pnl", "sum"),
            big_winner_lots=("big_winner", lambda s: int(pd.to_numeric(s, errors="coerce").fillna(0).gt(0).sum())),
        )
        .sort_values(["entry_year", "noise_ratio_bucket"])
        .reset_index(drop=True)
    )
    return grouped


def _contribution_curve(features: pd.DataFrame, official_curve: pd.DataFrame) -> pd.DataFrame:
    curve = official_curve.copy()
    curve["date"] = pd.to_datetime(curve["date"], errors="coerce").dt.normalize()
    curve = curve.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    records = features.copy()
    records["date"] = records["exit_date"]
    records["under_noise_floor_pnl"] = np.where(records["under_noise_floor"], records["realized_pnl"], 0.0)
    records["adequate_or_wide_stop_pnl"] = np.where(
        records["noise_ready"] & ~records["under_noise_floor"], records["realized_pnl"], 0.0
    )
    records["missing_noise_pnl"] = np.where(~records["noise_ready"], records["realized_pnl"], 0.0)
    daily = (
        records.groupby("date", as_index=False)[
            ["realized_pnl", "under_noise_floor_pnl", "adequate_or_wide_stop_pnl", "missing_noise_pnl"]
        ]
        .sum()
        .rename(columns={"realized_pnl": "closed_lot_realized_pnl"})
    )
    out = curve.merge(daily, on="date", how="left")
    for column in ["closed_lot_realized_pnl", "under_noise_floor_pnl", "adequate_or_wide_stop_pnl", "missing_noise_pnl"]:
        out[column] = out[column].fillna(0.0)
        out[f"cumulative_{column}"] = out[column].cumsum()
    return out


def _summary(features: pd.DataFrame, official_summary: pd.DataFrame) -> pd.DataFrame:
    official = official_summary.copy()
    numeric_cols = [
        "end_equity",
        "total_return_pct",
        "max_dd_pct",
        "sharpe",
        "total_slippage",
        "total_trade_count",
        "nonzero_daily_win_rate_pct",
        "max_broker10_margin_to_equity_pct",
        "days_over_100pct",
    ]
    for col in numeric_cols:
        if col in official.columns:
            official[col] = pd.to_numeric(official[col], errors="coerce")
    base = official.iloc[0].to_dict() if len(official) else {}
    ready = features[features["noise_ready"]]
    under = features[features["under_noise_floor"]]
    adequate = features[features["noise_ready"] & ~features["under_noise_floor"]]
    missing = features[~features["noise_ready"]]
    total_pnl = float(features["realized_pnl"].sum())
    under_pnl = float(under["realized_pnl"].sum())
    adequate_pnl = float(adequate["realized_pnl"].sum())
    return pd.DataFrame(
        [
            {
                "stage": STAGE,
                "official_live_version": OFFICIAL_LIVE_VERSION,
                "official_live_alias": OFFICIAL_LIVE_ALIAS,
                "end_equity": _safe_float(base.get("end_equity")),
                "total_return_pct": _safe_float(base.get("total_return_pct")),
                "max_dd_pct": _safe_float(base.get("max_dd_pct")),
                "sharpe": _safe_float(base.get("sharpe")),
                "total_slippage": _safe_float(base.get("total_slippage")),
                "total_trade_count": _safe_float(base.get("total_trade_count")),
                "win_rate_pct": _safe_float(base.get("nonzero_daily_win_rate_pct")),
                "max_broker10_margin_to_equity_pct": _safe_float(base.get("max_broker10_margin_to_equity_pct")),
                "days_over_100pct": _safe_float(base.get("days_over_100pct")),
                "closed_lots": int(len(features)),
                "noise_ready_lots": int(len(ready)),
                "noise_ready_rate_pct": float(len(ready) / max(len(features), 1) * 100.0),
                "under_noise_floor_lots": int(len(under)),
                "under_noise_floor_rate_pct": float(len(under) / max(len(ready), 1) * 100.0),
                "adequate_or_wide_lots": int(len(adequate)),
                "missing_noise_lots": int(len(missing)),
                "closed_lot_total_pnl": total_pnl,
                "under_noise_floor_net_pnl": under_pnl,
                "adequate_or_wide_net_pnl": adequate_pnl,
                "under_noise_floor_pnl_share_pct": under_pnl / total_pnl * 100.0 if total_pnl else np.nan,
                "under_noise_floor_positive_pnl": float(under["positive_pnl"].sum()),
                "under_noise_floor_negative_pnl": float(under["negative_pnl"].sum()),
                "under_noise_floor_big_winner_lots": int(
                    pd.to_numeric(under["big_winner"], errors="coerce").fillna(0).gt(0).sum()
                ),
                "under_noise_floor_products": int(under["product_key"].nunique()),
                "under_noise_floor_years": int(under["entry_year"].nunique()),
                "under_noise_floor_feasible_min1_lots": int(under["noise_floor_feasible_min1"].fillna(False).sum()),
            }
        ]
    )


def _decision(summary: pd.DataFrame, bucket_summary: pd.DataFrame, year_matrix: pd.DataFrame) -> dict[str, Any]:
    row = summary.iloc[0].to_dict()
    ready_rate = _safe_float(row.get("noise_ready_rate_pct"), 0.0)
    under_pnl = _safe_float(row.get("under_noise_floor_net_pnl"), 0.0)
    under_lots = int(_safe_float(row.get("under_noise_floor_lots"), 0.0))
    under_years = int(_safe_float(row.get("under_noise_floor_years"), 0.0))
    under_big = int(_safe_float(row.get("under_noise_floor_big_winner_lots"), 0.0))
    under_pos = _safe_float(row.get("under_noise_floor_positive_pnl"), 0.0)
    under_neg_abs = abs(_safe_float(row.get("under_noise_floor_negative_pnl"), 0.0))
    under_year = year_matrix[year_matrix["noise_ratio_bucket"].isin(["ratio_lt0_5", "ratio_0_5_1"])].copy()
    negative_years = int((under_year.groupby("entry_year")["net_pnl"].sum() < 0.0).sum()) if not under_year.empty else 0

    if ready_rate < 90.0:
        if under_lots >= 30 and (under_pnl >= 0.0 or under_big > 0):
            label = "stage081_data_not_ready_and_underfloor_contains_right_tail_no_rule"
            main = "noise_floor_coverage_insufficient_and_under_floor_not_bad_signal"
        else:
            label = "stage081_noise_floor_data_not_ready_no_rule"
            main = "noise_floor_coverage_insufficient"
    elif under_lots < 30 or under_years < 5:
        label = "stage081_under_noise_floor_too_sparse_no_rule"
        main = "under_floor_sample_too_sparse"
    elif under_pnl >= 0.0 or under_pos > under_neg_abs or under_big > 0:
        label = "stage081_under_noise_floor_contains_right_tail_no_rule"
        main = "under_floor_not_bad_signal"
    elif negative_years < max(4, under_years // 2):
        label = "stage081_under_noise_floor_year_instability_no_rule"
        main = "under_floor_year_instability"
    else:
        label = "stage081_noise_floor_promising_readonly_needs_frozen_true_engine"
        main = "under_floor_potential_risk_geometry_candidate"

    return {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "official_live_alias": OFFICIAL_LIVE_ALIAS,
        "stage_type": "readonly_preflight_audit",
        "candidate_rule_tested": False,
        "ab_triggered": False,
        "lookback_days": NOISE_LOOKBACK_DAYS,
        "min_periods": NOISE_MIN_PERIODS,
        "under_floor_ratio": UNDER_FLOOR_RATIO,
        "decision": label,
        "main_conclusion": main,
        "pass_flags": {
            "noise_ready_rate_ge90": bool(ready_rate >= 90.0),
            "under_floor_sample_broad": bool(under_lots >= 30 and under_years >= 5),
            "under_floor_net_negative": bool(under_pnl < 0.0),
            "under_floor_positive_not_dominant": bool(under_pos <= under_neg_abs),
            "under_floor_has_no_big_winner": bool(under_big == 0),
            "under_floor_negative_years_sufficient": bool(negative_years >= max(4, under_years // 2)),
        },
        "summary": row,
        "external_research_judgment": (
            "Trend-following position-sizing literature supports volatility-aware risk budgets, and drawdown sizing "
            "literature supports controlling tail risk through sizing rather than post-entry curve fitting. Stage081 "
            "therefore audits stop distance versus prior realized noise only as a preflight; it does not trade the "
            "bucket or tune a threshold."
        ),
        "overfit_reflection_before": (
            "No: this is a single read-only diagnostic anchored in prior 20-session true range, a conventional "
            "volatility/noise concept. It does not branch by product, year, direction, final PnL, exact mismatch, or "
            "Tq tick transform status."
        ),
        "continue_value_before": (
            "Yes: after Stage080 closed the same-source tick route, risk geometry is one of the few remaining "
            "first-principles directions that might reduce whipsaw without hard-deleting trend right tails."
        ),
        "overfit_reflection_after": "",
        "continue_value_after": "",
        "order_api_called": False,
        "ctp_connected": False,
        "outputs": {
            "features": str(FEATURES_OUT),
            "summary": str(SUMMARY_OUT),
            "bucket_summary": str(BUCKET_SUMMARY_OUT),
            "year_matrix": str(YEAR_MATRIX_OUT),
            "contribution_curve": str(CONTRIBUTION_CURVE_OUT),
            "daily_noise": str(DAILY_NOISE_OUT),
            "path_chart": str(PATH_CHART_OUT),
            "scatter": str(SCATTER_OUT),
            "heatmap": str(HEATMAP_OUT),
            "atlas_manifest": str(ATLAS_MANIFEST_OUT),
            "report": str(REPORT_OUT),
            "decision": str(DECISION_OUT),
        },
    }


def _plot_path(curve: pd.DataFrame) -> None:
    data = curve.copy()
    data["date"] = pd.to_datetime(data["date"], errors="coerce")
    fig, axes = plt.subplots(4, 1, figsize=(14, 12), sharex=True)
    axes[0].plot(data["date"], data["account_equity"], color="#111827", linewidth=1.3, label="official equity")
    axes[0].set_title("Stage081 Official Path With Noise-Floor Contribution Overlay")
    axes[0].set_ylabel("Equity")
    axes[0].legend(loc="upper left")

    axes[1].plot(data["date"], data["drawdown_pct"], color="#dc2626", linewidth=1.0, label="official drawdown %")
    axes[1].axhline(-45.0827, color="#7f1d1d", linewidth=0.8, linestyle="--", alpha=0.65)
    axes[1].set_ylabel("Drawdown %")
    axes[1].legend(loc="lower left")

    axes[2].plot(
        data["date"],
        data["broker10_margin_to_equity_pct"],
        color="#7c3aed",
        linewidth=1.0,
        label="broker10 margin/equity %",
    )
    axes[2].axhline(100.0, color="#991b1b", linewidth=0.8, linestyle="--", alpha=0.75)
    axes[2].set_ylabel("Broker10 %")
    axes[2].legend(loc="upper left")

    axes[3].plot(
        data["date"],
        data["cumulative_under_noise_floor_pnl"],
        color="#ea580c",
        linewidth=1.1,
        label="cum pnl: stop < prior20 median TR",
    )
    axes[3].plot(
        data["date"],
        data["cumulative_adequate_or_wide_stop_pnl"],
        color="#0f766e",
        linewidth=1.1,
        label="cum pnl: stop >= prior20 median TR",
    )
    axes[3].plot(
        data["date"],
        data["cumulative_missing_noise_pnl"],
        color="#64748b",
        linewidth=0.9,
        label="cum pnl: noise missing",
    )
    axes[3].axhline(0.0, color="#6b7280", linewidth=0.8)
    axes[3].set_ylabel("Closed-lot PnL")
    axes[3].legend(loc="upper left", ncol=2)
    for ax in axes:
        ax.grid(True, alpha=0.22)
    fig.tight_layout()
    fig.savefig(PATH_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_scatter(features: pd.DataFrame) -> None:
    data = features[features["noise_ready"]].copy()
    if data.empty:
        return
    data["plot_ratio"] = data["stop_to_noise_ratio"].clip(lower=0.05, upper=5.0)
    colors = np.where(data["under_noise_floor"], "#ea580c", "#0f766e")
    sizes = np.where(pd.to_numeric(data["big_winner"], errors="coerce").fillna(0).gt(0), 62, 24)
    fig, axes = plt.subplots(1, 2, figsize=(14, 5.8))
    axes[0].scatter(data["plot_ratio"], data["realized_pnl"], c=colors, s=sizes, alpha=0.72, edgecolors="none")
    axes[0].axvline(1.0, color="#111827", linestyle="--", linewidth=0.9)
    axes[0].axhline(0.0, color="#6b7280", linewidth=0.8)
    axes[0].set_xscale("log")
    axes[0].set_xlabel("stop_distance / prior20 median true range")
    axes[0].set_ylabel("realized pnl")
    axes[0].set_title("PnL vs Stop-To-Noise Ratio")
    axes[0].grid(True, alpha=0.2)

    axes[1].scatter(data["plot_ratio"], data["r_multiple"], c=colors, s=sizes, alpha=0.72, edgecolors="none")
    axes[1].axvline(1.0, color="#111827", linestyle="--", linewidth=0.9)
    axes[1].axhline(0.0, color="#6b7280", linewidth=0.8)
    axes[1].set_xscale("log")
    axes[1].set_xlabel("stop_distance / prior20 median true range")
    axes[1].set_ylabel("R multiple")
    axes[1].set_title("R Multiple vs Stop-To-Noise Ratio")
    axes[1].grid(True, alpha=0.2)
    fig.tight_layout()
    fig.savefig(SCATTER_OUT, dpi=160)
    plt.close(fig)


def _plot_heatmap(year_matrix: pd.DataFrame) -> None:
    if year_matrix.empty:
        return
    pivot = year_matrix.pivot_table(
        index="entry_year",
        columns="noise_ratio_bucket",
        values="net_pnl",
        aggfunc="sum",
        fill_value=0.0,
    )
    order = ["ratio_lt0_5", "ratio_0_5_1", "ratio_1_2", "ratio_ge2", "missing"]
    pivot = pivot[[column for column in order if column in pivot.columns]]
    fig, ax = plt.subplots(figsize=(12, 6.5))
    matrix = pivot.to_numpy(dtype="float64")
    limit = np.nanmax(np.abs(matrix)) if matrix.size else 1.0
    im = ax.imshow(matrix, cmap="RdYlGn", aspect="auto", vmin=-limit, vmax=limit)
    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns, rotation=30, ha="right")
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels([str(item) for item in pivot.index])
    ax.set_title("Stage081 Net PnL By Entry Year And Stop-To-Noise Bucket")
    for i in range(matrix.shape[0]):
        for j in range(matrix.shape[1]):
            ax.text(j, i, f"{matrix[i, j]/10000:.0f}w", ha="center", va="center", fontsize=8, color="#111827")
    fig.colorbar(im, ax=ax, fraction=0.025, pad=0.02, label="net pnl")
    fig.tight_layout()
    fig.savefig(HEATMAP_OUT, dpi=160)
    plt.close(fig)


def _minute_map(minute_bars: pd.DataFrame) -> dict[tuple[str, pd.Timestamp], pd.DataFrame]:
    data = minute_bars.copy()
    data["bar_datetime"] = pd.to_datetime(data["bar_datetime"], errors="coerce")
    data["bar_date"] = pd.to_datetime(data["bar_date"], errors="coerce").dt.normalize()
    for column in ["open", "high", "low", "close"]:
        data[column] = pd.to_numeric(data[column], errors="coerce")
    out: dict[tuple[str, pd.Timestamp], pd.DataFrame] = {}
    for key, group in data.dropna(subset=["vt_symbol", "bar_date", "bar_datetime"]).groupby(["vt_symbol", "bar_date"]):
        out[(str(key[0]), pd.Timestamp(key[1]).normalize())] = group.sort_values("bar_datetime").reset_index(drop=True)
    return out


def _atlas_rows(features: pd.DataFrame) -> pd.DataFrame:
    ready = features[features["noise_ready"]].copy()
    under = ready[ready["under_noise_floor"]].copy()
    adequate = ready[~ready["under_noise_floor"]].copy()
    chunks = [
        under.sort_values("realized_pnl", ascending=True).head(4).assign(stage081_atlas_group="under_floor_losers"),
        under.sort_values("realized_pnl", ascending=False).head(4).assign(stage081_atlas_group="under_floor_winners"),
        adequate.sort_values("realized_pnl", ascending=True).head(4).assign(stage081_atlas_group="adequate_losers"),
        adequate.sort_values("realized_pnl", ascending=False).head(4).assign(stage081_atlas_group="adequate_winners"),
    ]
    rows = pd.concat(chunks, ignore_index=True, sort=False)
    rows = rows.drop_duplicates(subset=["vt_symbol", "entry_date", "direction", "entry_price"]).head(MAX_ATLAS_ROWS)
    return rows.reset_index(drop=True)


def _plot_atlas(features: pd.DataFrame, minute_bars: pd.DataFrame) -> tuple[list[Path], pd.DataFrame]:
    rows = _atlas_rows(features)
    minute_by_key = _minute_map(minute_bars)
    manifest_rows: list[dict[str, Any]] = []
    paths: list[Path] = []
    if rows.empty:
        return paths, pd.DataFrame()

    page_count = int(np.ceil(len(rows) / PER_PAGE))
    for page in range(page_count):
        subset = rows.iloc[page * PER_PAGE : (page + 1) * PER_PAGE].reset_index(drop=True)
        fig, axes = plt.subplots(len(subset), 1, figsize=(13, 3.6 * len(subset)), squeeze=False)
        for row_idx, row in subset.iterrows():
            ax = axes[row_idx][0]
            key = (str(row["vt_symbol"]), pd.Timestamp(row["entry_date"]).normalize())
            day = minute_by_key.get(key, pd.DataFrame()).copy()
            if not day.empty:
                day = day.head(ATLAS_BARS)
                x = pd.to_datetime(day["bar_datetime"], errors="coerce")
                ax.plot(x, day["close"], color="#111827", linewidth=1.1, label="close")
                ax.fill_between(x, day["low"], day["high"], color="#94a3b8", alpha=0.20, linewidth=0)
            entry = _safe_float(row.get("entry_price"))
            stop_distance = _safe_float(row.get("stop_distance"))
            floor_distance = _safe_float(row.get("noise_floor_distance"))
            sign = 1.0 if str(row.get("direction")) == "long" else -1.0
            official_stop = entry - sign * stop_distance if np.isfinite(entry) and np.isfinite(stop_distance) else np.nan
            floor_stop = entry - sign * floor_distance if np.isfinite(entry) and np.isfinite(floor_distance) else np.nan
            if np.isfinite(entry):
                ax.axhline(entry, color="#2563eb", linewidth=0.9, label="entry")
            if np.isfinite(official_stop):
                ax.axhline(official_stop, color="#dc2626", linewidth=0.9, linestyle="--", label="official stop")
            if np.isfinite(floor_stop):
                ax.axhline(floor_stop, color="#f59e0b", linewidth=0.9, linestyle=":", label="noise floor stop")
            title = (
                f"{row.get('stage081_atlas_group')} | {row.get('vt_symbol')} {row.get('direction')} "
                f"{pd.Timestamp(row.get('entry_date')).date()} | pnl={_safe_float(row.get('realized_pnl')):,.0f} "
                f"ratio={_safe_float(row.get('stop_to_noise_ratio')):.2f}"
            )
            ax.set_title(title, fontsize=10)
            ax.grid(True, alpha=0.22)
            ax.legend(loc="upper left", fontsize=8, ncol=4)
            manifest_rows.append(
                {
                    "page": page + 1,
                    "row": row_idx + 1,
                    "lot_id": row.get("lot_id"),
                    "vt_symbol": row.get("vt_symbol"),
                    "entry_date": pd.Timestamp(row.get("entry_date")).date().isoformat(),
                    "direction": row.get("direction"),
                    "atlas_group": row.get("stage081_atlas_group"),
                    "realized_pnl": _safe_float(row.get("realized_pnl")),
                    "stop_to_noise_ratio": _safe_float(row.get("stop_to_noise_ratio")),
                    "under_noise_floor": bool(row.get("under_noise_floor")),
                    "minute_rows_plotted": int(len(day)) if not day.empty else 0,
                }
            )
        fig.tight_layout()
        path = Path(str(ATLAS_TEMPLATE).format(page=page + 1))
        fig.savefig(path, dpi=150)
        plt.close(fig)
        paths.append(path)
    return paths, pd.DataFrame(manifest_rows)


def _write_report(
    summary: pd.DataFrame,
    bucket_summary: pd.DataFrame,
    year_matrix: pd.DataFrame,
    decision: dict[str, Any],
    atlas_paths: list[Path],
) -> None:
    view_cols = [
        "end_equity",
        "total_return_pct",
        "max_dd_pct",
        "sharpe",
        "total_slippage",
        "total_trade_count",
        "win_rate_pct",
        "max_broker10_margin_to_equity_pct",
        "closed_lots",
        "noise_ready_lots",
        "under_noise_floor_lots",
        "under_noise_floor_net_pnl",
        "under_noise_floor_positive_pnl",
        "under_noise_floor_negative_pnl",
        "under_noise_floor_big_winner_lots",
    ]
    lines = [
        "# Stage081 噪声地板止损距离只读审计",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M')}`",
        f"- line_id：`{LINE_ID}`",
        f"- 当前官方正式版本：`{OFFICIAL_LIVE_VERSION}` / `{OFFICIAL_LIVE_ALIAS}`",
        "- 阶段性质：只读 preflight；不改正式配置、不连接 CTP、不调用订单 API、不触发 A/B。",
        "- 预声明口径：对每个 official closed lot，用 Stage861 分钟聚合出同合约 entry 前 `20` 个交易日 true range 的中位数；若 `official stop_distance < prior20 median true range`，记为 `under_noise_floor`。",
        "- 重要边界：这不是交易规则，只判断“止损是否贴近噪声”这一风险几何方向是否值得写真引擎。",
        "",
        "## 外部调研与判断",
        "",
        "- 趋势跟随仓位研究支持波动目标/风险预算比固定手数更适合穿越周期；drawdown sizing 文献支持用尾部风险预算控制回撤。",
        "- vn.py stop/order 语义要求如果未来写真引擎，必须明确 stop 修改与成交/重试事件顺序；本阶段暂不改变事件语义。",
        "- 我的判断：Stage080 后不能继续依赖 Tq tick 同源微观状态；若继续分钟进出场，应该优先看“风险距离是否低于可见噪声”这种普世几何问题，而不是切历史坏样本。",
        "",
        "## Summary",
        "",
        _md_table(summary[view_cols], max_rows=5),
        "",
        "## Bucket Summary",
        "",
        _md_table(bucket_summary, max_rows=20),
        "",
        "## Year Matrix",
        "",
        _md_table(year_matrix, max_rows=40),
        "",
        "## Visual Outputs",
        "",
        f"- official path + contribution：`{PATH_CHART_OUT}`",
        f"- noise ratio scatter：`{SCATTER_OUT}`",
        f"- bucket/year heatmap：`{HEATMAP_OUT}`",
        *[f"- minute atlas：`{path}`" for path in atlas_paths],
        "",
        "## Decision",
        "",
        f"- 决策：`{decision['decision']}`",
        f"- 主结论：`{decision['main_conclusion']}`",
        f"- 过拟合反思：`{decision['overfit_reflection_after']}`",
        f"- 继续价值：`{decision['continue_value_after']}`",
    ]
    REPORT_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print("[stage081] loading Stage024 features and official curve", flush=True)
    features = _prepare_features()
    official_curve = _read_required_csv(OFFICIAL_CURVE_IN)
    official_summary = _read_required_csv(OFFICIAL_SUMMARY_IN)

    metadata = s008.s513._metadata()
    source_symbol_by_contract = {str(k): str(v) for k, v in metadata["source_symbol_by_contract"].items()}
    features["product_key"] = features["vt_symbol"].map(source_symbol_by_contract).fillna(features["product_key"])
    vt_symbols = set(str(item) for item in metadata["vt_symbols"])
    print(f"[stage081] loading Stage861 full minute bars for {len(vt_symbols)} metadata contracts", flush=True)
    minute_bars = s008.s928._load_stage861_full_minute_bars(vt_symbols)
    daily_mapping = build_daily_mapping(supported_symbols=metadata["product_symbols"])
    daily_noise = _daily_noise_from_minutes(
        minute_bars,
        source_symbol_by_contract=source_symbol_by_contract,
        daily_mapping=daily_mapping,
    )
    enriched = _attach_noise(features, daily_noise)

    summary = _summary(enriched, official_summary)
    bucket_summary = _bucket_summary(enriched)
    year_matrix = _year_matrix(enriched)
    contribution_curve = _contribution_curve(enriched, official_curve)
    decision = _decision(summary, bucket_summary, year_matrix)
    if decision["decision"] == "stage081_noise_floor_promising_readonly_needs_frozen_true_engine":
        decision["overfit_reflection_after"] = (
            "No: the read-only evidence is not a fitted parameter search. However, before any true engine this must be "
            "frozen as one rule, and any pass would require multi-start and cost-stress verification."
        )
        decision["continue_value_after"] = (
            "Yes: next step is a single frozen true engine that widens too-tight initial stop to the prior20 median "
            "true-range floor while reducing volume to preserve cash risk; no threshold rescue."
        )
    else:
        decision["overfit_reflection_after"] = (
            "No: this stage only tested one conventional prior20 noise floor diagnostic and did not optimize buckets. "
            "Turning the displayed buckets into filters after seeing the chart would be overfitting."
        )
        decision["continue_value_after"] = (
            "No for direct noise-floor bucket trading if it contains right-tail PnL or lacks year stability; keep it as "
            "risk geometry attribution unless a separate frozen engine hypothesis is justified."
        )

    print("[stage081] plotting visuals", flush=True)
    _plot_path(contribution_curve)
    _plot_scatter(enriched)
    _plot_heatmap(year_matrix)
    atlas_paths, atlas_manifest = _plot_atlas(enriched, minute_bars)

    enriched.to_csv(FEATURES_OUT, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_OUT, index=False, encoding="utf-8-sig")
    bucket_summary.to_csv(BUCKET_SUMMARY_OUT, index=False, encoding="utf-8-sig")
    year_matrix.to_csv(YEAR_MATRIX_OUT, index=False, encoding="utf-8-sig")
    contribution_curve.to_csv(CONTRIBUTION_CURVE_OUT, index=False, encoding="utf-8-sig")
    daily_noise.to_csv(DAILY_NOISE_OUT, index=False, encoding="utf-8-sig")
    atlas_manifest.to_csv(ATLAS_MANIFEST_OUT, index=False, encoding="utf-8-sig")
    _write_report(summary, bucket_summary, year_matrix, decision, atlas_paths)
    DECISION_OUT.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"[stage081] decision={decision['decision']}", flush=True)
    print(f"[stage081] summary={SUMMARY_OUT}", flush=True)
    print(f"[stage081] path_chart={PATH_CHART_OUT}", flush=True)


if __name__ == "__main__":
    main()
