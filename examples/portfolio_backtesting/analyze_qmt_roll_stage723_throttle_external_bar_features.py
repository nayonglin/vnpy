from __future__ import annotations

from datetime import datetime
import json
import math
from pathlib import Path
import sqlite3
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = PROJECT_DIR.parents[1]
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
DATABASE_PATH = PROJECT_ROOT / ".vntrader" / "database.db"

MODEL_TAG = "stage723_throttle_external_bar_features_v1"
OUTPUT_PREFIX = "qmt_roll_stage723_throttle_external_bar_features"
LINE_ID = "futures_trend_winner_trade_forensics"

SOURCE_STAGE716_PATH = (
    OUTPUT_DIR
    / "qmt_roll_stage716_official_throttle_quality_readonly_labeled_candidates_"
    "stage716_official_throttle_quality_readonly_v1.csv"
)

ENRICHED_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_enriched_candidates_{MODEL_TAG}.csv"
FEATURE_METRICS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_feature_metrics_{MODEL_TAG}.csv"
YEAR_DETAIL_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_year_detail_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

MIN_RELIABLE_ROWS = 30
MIN_RELIABLE_YEARS = 4
MIN_RELIABLE_PRODUCTS = 6
MAX_DOMINANT_PRODUCT_SHARE = 0.35
MIN_GOOD_LIFT_PP = 10.0
MAX_BAD_RATE_PCT = 60.0
MIN_GOOD_YEARS = 4
MIN_POSITIVE_SCORE_YEARS = 4

EXTERNAL_FEATURES = [
    "bar_source_bucket",
    "product_signed_ret20_bucket",
    "product_signed_ret60_bucket",
    "product_directional_edge60_bucket",
    "product_oi_change20_bucket",
    "product_oi_change60_bucket",
    "product_directional_oi_confirm20",
    "product_directional_oi_confirm60",
    "product_volume_z60_bucket",
    "product_volume_ratio20_60_bucket",
    "product_atr_rank120_bucket",
    "product_range_z60_bucket",
    "product_breakout_quality_bucket",
    "contract_days_to_end_bucket",
    "contract_life_pct_bucket",
    "contract_oi_change20_bucket",
    "contract_oi_peak_ratio60_bucket",
    "contract_volume_ratio20_60_bucket",
    "external_conviction_bucket",
    "external_no_conviction_bucket",
    "external_roll_liquidity_bucket",
]


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, tuple):
        return [_json_safe(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        if np.isnan(value) or np.isinf(value):
            return None
        return float(value)
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    if pd.isna(value):
        return None
    return value


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_empty_"
    data = frame.head(max_rows).copy() if max_rows is not None else frame.copy()
    for column in data.columns:
        if pd.api.types.is_float_dtype(data[column]):
            data[column] = data[column].map(lambda value: "" if pd.isna(value) else f"{value:.4f}")
    data = data.fillna("")
    headers = [str(column) for column in data.columns]
    rows = [[str(value) for value in row] for row in data.to_numpy()]
    widths = [len(header) for header in headers]
    for row in rows:
        widths = [max(width, len(cell)) for width, cell in zip(widths, row)]
    line = "| " + " | ".join(header.ljust(width) for header, width in zip(headers, widths)) + " |"
    sep = "| " + " | ".join("-" * width for width in widths) + " |"
    body = ["| " + " | ".join(cell.ljust(width) for cell, width in zip(row, widths)) + " |" for row in rows]
    return "\n".join([line, sep, *body])


def _truthy(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip().str.lower().isin({"true", "1", "1.0", "yes", "y"})


def _parse_vt(vt_symbol: str) -> tuple[str, str] | None:
    if not isinstance(vt_symbol, str) or "." not in vt_symbol:
        return None
    symbol, exchange = vt_symbol.split(".", 1)
    return symbol, exchange


def _load_actionable() -> pd.DataFrame:
    if not SOURCE_STAGE716_PATH.exists():
        raise FileNotFoundError(SOURCE_STAGE716_PATH)
    data = pd.read_csv(SOURCE_STAGE716_PATH, encoding="utf-8-sig")
    actionable_flag = _truthy(data["actionable_throttle"])
    numeric_columns = [
        "h40_barrier_good",
        "h40_barrier_bad",
        "h40_mfe_r",
        "h40_mae_r",
        "h40_path_score_r",
        "h40_days_observed",
        "year",
    ]
    for column in numeric_columns:
        if column in data.columns:
            data[column] = pd.to_numeric(data[column], errors="coerce")
    actionable = data[
        actionable_flag & data["h40_label_status"].astype(str).eq("ok")
    ].copy()
    actionable["year"] = actionable["year"].astype(int)
    actionable["date"] = pd.to_datetime(actionable["date"]).dt.normalize()
    return actionable.reset_index(drop=True)


def _load_bar_frame(vt_symbols: list[str]) -> pd.DataFrame:
    if not DATABASE_PATH.exists():
        raise FileNotFoundError(DATABASE_PATH)
    rows: list[pd.DataFrame] = []
    with sqlite3.connect(DATABASE_PATH) as con:
        for vt_symbol in sorted(set(vt_symbols)):
            parsed = _parse_vt(vt_symbol)
            if parsed is None:
                continue
            symbol, exchange = parsed
            query = """
                SELECT
                    symbol || '.' || exchange AS vt_symbol,
                    datetime AS date,
                    open_price,
                    high_price,
                    low_price,
                    close_price,
                    volume,
                    turnover,
                    open_interest
                FROM dbbardata
                WHERE symbol = ? AND exchange = ? AND interval = 'd'
                ORDER BY datetime
            """
            frame = pd.read_sql_query(query, con, params=(symbol, exchange))
            if frame.empty:
                continue
            rows.append(frame)
    if not rows:
        return pd.DataFrame()
    data = pd.concat(rows, ignore_index=True)
    data["date"] = pd.to_datetime(data["date"]).dt.normalize()
    numeric_columns = ["open_price", "high_price", "low_price", "close_price", "volume", "turnover", "open_interest"]
    for column in numeric_columns:
        data[column] = pd.to_numeric(data[column], errors="coerce")
    return data.drop_duplicates(subset=["vt_symbol", "date"]).sort_values(["vt_symbol", "date"])


def _load_overview(vt_symbols: list[str]) -> pd.DataFrame:
    with sqlite3.connect(DATABASE_PATH) as con:
        overview = pd.read_sql_query(
            """
            SELECT
                symbol || '.' || exchange AS vt_symbol,
                start,
                end,
                count
            FROM dbbaroverview
            WHERE interval = 'd'
            """,
            con,
        )
    overview = overview[overview["vt_symbol"].isin(set(vt_symbols))].copy()
    overview["start"] = pd.to_datetime(overview["start"]).dt.normalize()
    overview["end"] = pd.to_datetime(overview["end"]).dt.normalize()
    return overview.drop_duplicates(subset=["vt_symbol"])


def _add_rolling_features(bars: pd.DataFrame) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for vt_symbol, group in bars.groupby("vt_symbol"):
        df = group.sort_values("date").copy()
        close = df["close_price"].replace(0.0, np.nan)
        high = df["high_price"]
        low = df["low_price"]
        prev_close = close.shift(1)
        true_range = pd.concat(
            [
                (high - low).abs(),
                (high - prev_close).abs(),
                (low - prev_close).abs(),
            ],
            axis=1,
        ).max(axis=1)
        range_pct = (high - low) / close
        atr14_pct = true_range.rolling(14, min_periods=8).mean() / close
        df["ret20"] = close / close.shift(20) - 1.0
        df["ret60"] = close / close.shift(60) - 1.0
        high60 = high.rolling(60, min_periods=30).max()
        low60 = low.rolling(60, min_periods=30).min()
        df["close_pos60"] = (close - low60) / (high60 - low60)
        df["range_pct"] = range_pct
        df["range_z60"] = (range_pct - range_pct.rolling(60, min_periods=30).mean()) / range_pct.rolling(
            60, min_periods=30
        ).std(ddof=0)
        df["atr14_pct"] = atr14_pct
        df["atr_rank120"] = atr14_pct.rolling(120, min_periods=60).rank(pct=True)
        vol_log = np.log1p(df["volume"].clip(lower=0.0))
        df["volume_z60"] = (vol_log - vol_log.rolling(60, min_periods=30).mean()) / vol_log.rolling(
            60, min_periods=30
        ).std(ddof=0)
        df["volume_ratio20_60"] = df["volume"].rolling(20, min_periods=10).mean() / df["volume"].rolling(
            60, min_periods=30
        ).mean()
        oi = df["open_interest"].replace(0.0, np.nan)
        df["oi_change20"] = oi / oi.shift(20) - 1.0
        df["oi_change60"] = oi / oi.shift(60) - 1.0
        df["oi_peak_ratio60"] = oi / oi.rolling(60, min_periods=30).max()
        df["bar_index"] = np.arange(len(df))
        frames.append(df)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def _asof_row(features: pd.DataFrame, vt_symbol: str, date: pd.Timestamp) -> pd.Series | None:
    group = features[features["vt_symbol"].eq(vt_symbol)]
    if group.empty:
        return None
    eligible = group[group["date"].le(date)]
    if eligible.empty:
        return None
    return eligible.iloc[-1]


def _bucket_signed_ret(value: float, *, medium: float = 0.05, strong: float = 0.15) -> str:
    if pd.isna(value):
        return "missing"
    if value >= strong:
        return "signed_ret_strong_pos"
    if value >= medium:
        return "signed_ret_mild_pos"
    if value > -medium:
        return "signed_ret_flat"
    return "signed_ret_neg"


def _bucket_change(value: float) -> str:
    if pd.isna(value):
        return "missing"
    if value >= 0.10:
        return "up_10p_plus"
    if value >= 0.02:
        return "up_2_10p"
    if value > -0.02:
        return "flat_pm2p"
    if value > -0.10:
        return "down_2_10p"
    return "down_10p_plus"


def _bucket_z(value: float) -> str:
    if pd.isna(value):
        return "missing"
    if value >= 1.0:
        return "high_z"
    if value <= -1.0:
        return "low_z"
    return "mid_z"


def _bucket_ratio(value: float) -> str:
    if pd.isna(value):
        return "missing"
    if value >= 1.25:
        return "ratio_high"
    if value <= 0.75:
        return "ratio_low"
    return "ratio_mid"


def _bucket_rank(value: float) -> str:
    if pd.isna(value):
        return "missing"
    if value <= 0.33:
        return "rank_low"
    if value >= 0.67:
        return "rank_high"
    return "rank_mid"


def _bucket_days_to_end(value: float) -> str:
    if pd.isna(value):
        return "missing"
    if value < 20:
        return "roll_late_lt20d"
    if value < 60:
        return "roll_mid_20_60d"
    return "roll_ok_ge60d"


def _bucket_life_pct(value: float) -> str:
    if pd.isna(value):
        return "missing"
    if value < 0.25:
        return "life_early"
    if value > 0.75:
        return "life_late"
    return "life_mid"


def _bucket_edge(direction: str, close_pos60: float) -> str:
    if pd.isna(close_pos60):
        return "missing"
    if direction == "long":
        if close_pos60 >= 0.80:
            return "directional_edge"
        if close_pos60 <= 0.20:
            return "counter_edge"
        return "range_middle"
    if direction == "short":
        if close_pos60 <= 0.20:
            return "directional_edge"
        if close_pos60 >= 0.80:
            return "counter_edge"
        return "range_middle"
    return "missing"


def _enrich_candidates(candidates: pd.DataFrame, bars: pd.DataFrame, overview: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    overview_map = overview.set_index("vt_symbol").to_dict(orient="index")
    for row in candidates.itertuples(index=False):
        date = pd.Timestamp(row.date).normalize()
        direction = str(row.direction)
        product_vt = str(row.product_vt_symbol)
        contract_vt = str(row.contract_vt_symbol)
        product_bar = _asof_row(bars, product_vt, date)
        contract_bar = _asof_row(bars, contract_vt, date)
        source_bar = product_bar if product_bar is not None else contract_bar
        source_name = "product" if product_bar is not None else "contract_fallback" if contract_bar is not None else "missing"

        record = row._asdict()
        record["bar_source_bucket"] = source_name
        for prefix, bar in [("product", source_bar), ("contract", contract_bar)]:
            signed_ret20 = np.nan
            signed_ret60 = np.nan
            if bar is not None:
                sign = 1.0 if direction == "long" else -1.0 if direction == "short" else np.nan
                signed_ret20 = sign * float(bar.get("ret20", np.nan))
                signed_ret60 = sign * float(bar.get("ret60", np.nan))
                record[f"{prefix}_signed_ret20"] = signed_ret20
                record[f"{prefix}_signed_ret60"] = signed_ret60
                record[f"{prefix}_close_pos60"] = float(bar.get("close_pos60", np.nan))
                record[f"{prefix}_volume_z60"] = float(bar.get("volume_z60", np.nan))
                record[f"{prefix}_volume_ratio20_60"] = float(bar.get("volume_ratio20_60", np.nan))
                record[f"{prefix}_oi_change20"] = float(bar.get("oi_change20", np.nan))
                record[f"{prefix}_oi_change60"] = float(bar.get("oi_change60", np.nan))
                record[f"{prefix}_oi_peak_ratio60"] = float(bar.get("oi_peak_ratio60", np.nan))
                record[f"{prefix}_range_z60"] = float(bar.get("range_z60", np.nan))
                record[f"{prefix}_atr_rank120"] = float(bar.get("atr_rank120", np.nan))
            else:
                for name in [
                    "signed_ret20",
                    "signed_ret60",
                    "close_pos60",
                    "volume_z60",
                    "volume_ratio20_60",
                    "oi_change20",
                    "oi_change60",
                    "oi_peak_ratio60",
                    "range_z60",
                    "atr_rank120",
                ]:
                    record[f"{prefix}_{name}"] = np.nan
            record[f"{prefix}_signed_ret20_bucket"] = _bucket_signed_ret(signed_ret20)
            record[f"{prefix}_signed_ret60_bucket"] = _bucket_signed_ret(signed_ret60)
            record[f"{prefix}_oi_change20_bucket"] = _bucket_change(record[f"{prefix}_oi_change20"])
            record[f"{prefix}_oi_change60_bucket"] = _bucket_change(record[f"{prefix}_oi_change60"])
            record[f"{prefix}_volume_z60_bucket"] = _bucket_z(record[f"{prefix}_volume_z60"])
            record[f"{prefix}_volume_ratio20_60_bucket"] = _bucket_ratio(record[f"{prefix}_volume_ratio20_60"])
            record[f"{prefix}_atr_rank120_bucket"] = _bucket_rank(record[f"{prefix}_atr_rank120"])
            record[f"{prefix}_range_z60_bucket"] = _bucket_z(record[f"{prefix}_range_z60"])
            record[f"{prefix}_directional_edge60_bucket"] = _bucket_edge(direction, record[f"{prefix}_close_pos60"])
            oi_confirm20 = bool(
                not pd.isna(record[f"{prefix}_signed_ret20"])
                and record[f"{prefix}_signed_ret20"] > 0.0
                and not pd.isna(record[f"{prefix}_oi_change20"])
                and record[f"{prefix}_oi_change20"] > 0.0
            )
            oi_confirm60 = bool(
                not pd.isna(record[f"{prefix}_signed_ret60"])
                and record[f"{prefix}_signed_ret60"] > 0.0
                and not pd.isna(record[f"{prefix}_oi_change60"])
                and record[f"{prefix}_oi_change60"] > 0.0
            )
            record[f"{prefix}_directional_oi_confirm20"] = "oi_confirm" if oi_confirm20 else "oi_not_confirm"
            record[f"{prefix}_directional_oi_confirm60"] = "oi_confirm" if oi_confirm60 else "oi_not_confirm"

        contract_info = overview_map.get(contract_vt, {})
        start = contract_info.get("start")
        end = contract_info.get("end")
        if isinstance(start, pd.Timestamp) and isinstance(end, pd.Timestamp):
            life_days = max((end - start).days, 1)
            days_since_start = (date - start).days
            days_to_end = (end - date).days
            life_pct = days_since_start / life_days
        else:
            days_to_end = np.nan
            life_pct = np.nan
        record["contract_days_to_end"] = days_to_end
        record["contract_life_pct"] = life_pct
        record["contract_days_to_end_bucket"] = _bucket_days_to_end(days_to_end)
        record["contract_life_pct_bucket"] = _bucket_life_pct(life_pct)

        edge = record["product_directional_edge60_bucket"]
        vol_ok = record["product_volume_z60_bucket"] in {"mid_z", "high_z"}
        oi_ok = record["product_directional_oi_confirm20"] == "oi_confirm"
        record["product_breakout_quality_bucket"] = (
            "edge_with_volume_oi" if edge == "directional_edge" and vol_ok and oi_ok
            else "edge_no_full_confirm" if edge == "directional_edge"
            else "not_directional_edge"
        )
        record["external_conviction_bucket"] = (
            "conviction_yes"
            if edge == "directional_edge"
            and vol_ok
            and oi_ok
            and record["contract_days_to_end_bucket"] != "roll_late_lt20d"
            else "conviction_no"
        )
        record["external_no_conviction_bucket"] = (
            "no_conviction_yes"
            if edge == "directional_edge" and not (vol_ok and oi_ok)
            else "no_conviction_no"
        )
        record["external_roll_liquidity_bucket"] = (
            "roll_liquidity_ok"
            if record["contract_days_to_end_bucket"] == "roll_ok_ge60d"
            and record["contract_volume_ratio20_60_bucket"] != "ratio_low"
            else "roll_liquidity_weak"
        )
        rows.append(record)
    return pd.DataFrame(rows)


def _dominant_share(group: pd.DataFrame) -> tuple[str, float]:
    share = group["product"].value_counts(normalize=True)
    if share.empty:
        return "", np.nan
    return str(share.index[0]), float(share.iloc[0])


def _feature_rows(data: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    baseline_good = float(data["h40_barrier_good"].mean())
    baseline_bad = float(data["h40_barrier_bad"].mean())
    baseline_score = float(data["h40_path_score_r"].mean())
    rows: list[dict[str, Any]] = []
    year_rows: list[dict[str, Any]] = []
    for feature in EXTERNAL_FEATURES:
        if feature not in data.columns:
            continue
        for value, group in data.groupby(feature, dropna=False):
            label = "missing" if pd.isna(value) or str(value) == "" else str(value)
            if label in {"missing", "nan", ""} or len(group) < 5:
                continue
            dominant_product, dominant_product_share = _dominant_share(group)
            year_stats = group.groupby("year").agg(
                rows=("candidate_index", "count"),
                good_rate=("h40_barrier_good", "mean"),
                bad_rate=("h40_barrier_bad", "mean"),
                avg_score=("h40_path_score_r", "mean"),
            )
            row = {
                "feature": feature,
                "feature_value": label,
                "rows": int(len(group)),
                "good_rate_pct": float(group["h40_barrier_good"].mean() * 100.0),
                "bad_rate_pct": float(group["h40_barrier_bad"].mean() * 100.0),
                "good_lift_pp": float((group["h40_barrier_good"].mean() - baseline_good) * 100.0),
                "bad_lift_pp": float((group["h40_barrier_bad"].mean() - baseline_bad) * 100.0),
                "avg_path_score_r": float(group["h40_path_score_r"].mean()),
                "score_lift_r": float(group["h40_path_score_r"].mean() - baseline_score),
                "years": int(len(year_stats)),
                "years_good_ge_base": int((year_stats["good_rate"] >= baseline_good).sum()),
                "years_score_positive": int((year_stats["avg_score"] > 0.0).sum()),
                "product_count": int(group["product"].nunique()),
                "dominant_product": dominant_product,
                "dominant_product_share_pct": float(dominant_product_share * 100.0),
                "baseline_good_rate_pct": baseline_good * 100.0,
                "baseline_bad_rate_pct": baseline_bad * 100.0,
                "baseline_path_score_r": baseline_score,
            }
            rows.append(row)
            for year, year_group in group.groupby("year"):
                year_rows.append(
                    {
                        "feature": feature,
                        "feature_value": label,
                        "year": int(year),
                        "rows": int(len(year_group)),
                        "good_rate_pct": float(year_group["h40_barrier_good"].mean() * 100.0),
                        "bad_rate_pct": float(year_group["h40_barrier_bad"].mean() * 100.0),
                        "avg_path_score_r": float(year_group["h40_path_score_r"].mean()),
                    }
                )
    metrics = pd.DataFrame(rows)
    metrics["fail_reasons"] = metrics.apply(_fail_reasons, axis=1)
    metrics["passes_reliability_gate"] = metrics["fail_reasons"].eq("")
    metrics["screen_score"] = (
        metrics["good_lift_pp"]
        - np.maximum(metrics["bad_lift_pp"], 0.0)
        + np.minimum(metrics["avg_path_score_r"], 20.0)
        + metrics["years_good_ge_base"] * 2.0
        + np.minimum(metrics["rows"], 40.0) / 4.0
    )
    metrics["classification"] = np.select(
        [
            metrics["passes_reliability_gate"],
            (metrics["good_lift_pp"] >= MIN_GOOD_LIFT_PP) & (metrics["rows"] >= 12),
        ],
        ["reliable_external_exemption_candidate", "watch_only_external_sample_or_stability_gap"],
        default="not_reliable",
    )
    metrics = metrics.sort_values(
        ["passes_reliability_gate", "screen_score", "good_lift_pp", "rows"],
        ascending=[False, False, False, False],
    ).reset_index(drop=True)
    return metrics, pd.DataFrame(year_rows)


def _fail_reasons(row: pd.Series) -> str:
    reasons: list[str] = []
    if int(row["rows"]) < MIN_RELIABLE_ROWS:
        reasons.append(f"rows<{MIN_RELIABLE_ROWS}")
    if int(row["years"]) < MIN_RELIABLE_YEARS:
        reasons.append(f"years<{MIN_RELIABLE_YEARS}")
    if int(row["product_count"]) < MIN_RELIABLE_PRODUCTS:
        reasons.append(f"products<{MIN_RELIABLE_PRODUCTS}")
    if float(row["dominant_product_share_pct"]) > MAX_DOMINANT_PRODUCT_SHARE * 100.0:
        reasons.append(f"dominant_product_share>{MAX_DOMINANT_PRODUCT_SHARE * 100:.0f}%")
    if float(row["good_lift_pp"]) < MIN_GOOD_LIFT_PP:
        reasons.append(f"good_lift<{MIN_GOOD_LIFT_PP:.0f}pp")
    if float(row["bad_rate_pct"]) > MAX_BAD_RATE_PCT:
        reasons.append(f"bad_rate>{MAX_BAD_RATE_PCT:.0f}%")
    if int(row["years_good_ge_base"]) < MIN_GOOD_YEARS:
        reasons.append(f"good_years<{MIN_GOOD_YEARS}")
    if int(row["years_score_positive"]) < MIN_POSITIVE_SCORE_YEARS:
        reasons.append(f"positive_score_years<{MIN_POSITIVE_SCORE_YEARS}")
    return "; ".join(reasons)


def _coverage_summary(enriched: pd.DataFrame) -> dict[str, Any]:
    product_rows = enriched["bar_source_bucket"].astype(str).eq("product")
    fallback_rows = enriched["bar_source_bucket"].astype(str).eq("contract_fallback")
    missing_rows = enriched["bar_source_bucket"].astype(str).eq("missing")
    return {
        "candidate_rows": int(len(enriched)),
        "product_bar_rows": int(product_rows.sum()),
        "contract_fallback_rows": int(fallback_rows.sum()),
        "missing_bar_rows": int(missing_rows.sum()),
        "product_bar_coverage_pct": float(product_rows.mean() * 100.0),
        "any_bar_coverage_pct": float((~missing_rows).mean() * 100.0),
        "nonmissing_product_oi_change20_pct": float(enriched["product_oi_change20"].notna().mean() * 100.0),
        "nonmissing_contract_oi_change20_pct": float(enriched["contract_oi_change20"].notna().mean() * 100.0),
    }


def _plot(metrics: pd.DataFrame) -> None:
    plt.rcParams["font.family"] = "DejaVu Sans"
    top = metrics.head(14).copy()
    fig, axes = plt.subplots(1, 2, figsize=(16, 6))
    colors = [
        "#2f855a" if passed else "#dd6b20" if "watch" in classification else "#718096"
        for passed, classification in zip(top["passes_reliability_gate"], top["classification"])
    ]
    axes[0].barh(top["feature"] + "=" + top["feature_value"], top["good_lift_pp"], color=colors)
    axes[0].axvline(MIN_GOOD_LIFT_PP, color="#2f855a", linestyle="--", linewidth=1.0, label="required +10pp")
    axes[0].axvline(0.0, color="#4a5568", linewidth=0.8)
    axes[0].set_title("External bar features: H40 good lift")
    axes[0].set_xlabel("good lift (pp)")
    axes[0].invert_yaxis()
    axes[0].legend()
    axes[1].scatter(metrics["rows"], metrics["good_rate_pct"], s=45, alpha=0.65, color="#2b6cb0")
    axes[1].axhline(float(metrics["baseline_good_rate_pct"].iloc[0]), color="#4a5568", linestyle="--", label="baseline")
    axes[1].axvline(MIN_RELIABLE_ROWS, color="#2f855a", linestyle="--", label="required rows")
    axes[1].set_title("Feature support vs good rate")
    axes[1].set_xlabel("rows")
    axes[1].set_ylabel("H40 good rate (%)")
    axes[1].legend()
    fig.suptitle("Stage723 External Bar Feature Audit", fontsize=15)
    fig.tight_layout(rect=[0, 0.02, 1, 0.94])
    CHART_PATH.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(CHART_PATH, dpi=180)
    plt.close(fig)


def _build_report(enriched: pd.DataFrame, metrics: pd.DataFrame, decision: dict[str, Any]) -> str:
    columns = [
        "feature",
        "feature_value",
        "rows",
        "good_rate_pct",
        "bad_rate_pct",
        "good_lift_pp",
        "avg_path_score_r",
        "years",
        "years_good_ge_base",
        "product_count",
        "dominant_product_share_pct",
        "classification",
        "fail_reasons",
    ]
    lines = [
        "# Stage723 Throttle External Bar Features",
        "",
        f"- line_id: `{LINE_ID}`",
        f"- generated_at: `{decision['generated_at']}`",
        f"- source: `{SOURCE_STAGE716_PATH}`",
        f"- database: `{DATABASE_PATH}`",
        f"- actionable_h40_rows: `{len(enriched)}`",
        f"- initial_gate_candidate_count: `{decision['initial_gate_candidate_count']}`",
        f"- decision: `{decision['decision']}`",
        "",
        "## Coverage",
        "",
        _md_table(pd.DataFrame([decision["coverage"]]), max_rows=None),
        "",
        "## Gate",
        "",
        f"- rows >= `{MIN_RELIABLE_ROWS}`",
        f"- years >= `{MIN_RELIABLE_YEARS}`",
        f"- products >= `{MIN_RELIABLE_PRODUCTS}`",
        f"- dominant product share <= `{MAX_DOMINANT_PRODUCT_SHARE * 100:.0f}%`",
        f"- H40 +2R good lift >= `{MIN_GOOD_LIFT_PP:.0f}pp`",
        f"- H40 -1R bad rate <= `{MAX_BAD_RATE_PCT:.0f}%`",
        f"- good years >= `{MIN_GOOD_YEARS}` and positive-score years >= `{MIN_POSITIVE_SCORE_YEARS}`",
        "",
        "## Top External Features",
        "",
        _md_table(metrics[columns], max_rows=25),
        "",
        "## Interpretation",
        "",
        "- These features are computed from daily bar volume/open interest/volatility/roll-phase data, not from product names or red-box windows.",
        "- An initial-gate feature is only a research candidate; it still requires a later A/C backtest before touching the official strategy.",
        "- If no feature survives actual strategy replay, current evidence still supports keeping the 0.1 floor without a historical-data exemption.",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    actionable = _load_actionable()
    vt_symbols = sorted(
        set(actionable["contract_vt_symbol"].dropna().astype(str))
        | set(actionable["product_vt_symbol"].dropna().astype(str))
    )
    bars = _add_rolling_features(_load_bar_frame(vt_symbols))
    overview = _load_overview(actionable["contract_vt_symbol"].dropna().astype(str).tolist())
    enriched = _enrich_candidates(actionable, bars, overview)
    metrics, year_detail = _feature_rows(enriched)
    initial_gate = metrics[metrics["passes_reliability_gate"]]
    has_initial_gate = not initial_gate.empty
    decision = {
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source": str(SOURCE_STAGE716_PATH),
        "database": str(DATABASE_PATH),
        "actionable_h40_rows": int(len(enriched)),
        "coverage": _coverage_summary(enriched),
        "initial_gate_candidate_count": int(len(initial_gate)),
        "initial_gate_candidates": initial_gate[
            ["feature", "feature_value", "rows", "good_rate_pct", "good_lift_pp"]
        ].to_dict(
            orient="records"
        ),
        "top_watch_features": metrics.head(8)[
            ["feature", "feature_value", "rows", "good_rate_pct", "good_lift_pp", "fail_reasons"]
        ].to_dict(orient="records"),
        "decision": (
            "external_bar_initial_gate_candidate_requires_strategy_ab_validation"
            if has_initial_gate
            else "no_external_bar_initial_gate_candidate_found"
        ),
        "next_step": (
            "Run a predeclared A/C strategy replay for the initial-gate candidate before any official-rule change."
            if has_initial_gate
            else "Do not implement an exemption from these daily bar features. Continue only via forward watch or truly "
            "orthogonal data such as intraday order-flow/term-structure sources."
        ),
    }
    enriched.to_csv(ENRICHED_PATH, index=False, encoding="utf-8-sig")
    metrics.to_csv(FEATURE_METRICS_PATH, index=False, encoding="utf-8-sig")
    year_detail.to_csv(YEAR_DETAIL_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _plot(metrics)
    REPORT_PATH.write_text(_build_report(enriched, metrics, decision), encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
