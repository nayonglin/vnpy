from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import io
import json
from pathlib import Path
from typing import Any
import zipfile

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


LINE_ID = "futures_trend_c9_minrisk_highquality"
STAGE = "Stage256"
MODEL_TAG = "stage256_cftc_cot_cross_market_context_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage256_c9_minrisk_cftc_cot_cross_market_context_audit"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage256_cftc_cot_cross_market_context_audit"
CFTC_CACHE_DIR = REPO_DIR / "examples" / "portfolio_backtesting" / "backtest_outputs" / "external_cftc_cot_cache"

STAGE239_DIR = LINE_DIR / "outputs" / "stage239_read_only_universal_signal_quality_audit"
STAGE239_PREFIX = "qmt_roll_stage239_c9_minrisk_read_only_universal_signal_quality_audit"
STAGE239_TAG = "stage239_read_only_universal_signal_quality_audit_v1"
STAGE239_JOINED_IN = STAGE239_DIR / f"{STAGE239_PREFIX}_joined_signal_label_audit_{STAGE239_TAG}.csv"

STAGE251_DIR = LINE_DIR / "outputs" / "stage251_dd30_account_floor_true_engine"
STAGE251_PREFIX = "qmt_roll_stage251_c9_minrisk_dd30_account_floor_true_engine"
STAGE251_TAG = "stage251_dd30_account_floor_true_engine_v1"
STAGE251_CLOSED_LOTS_IN = STAGE251_DIR / f"{STAGE251_PREFIX}_closed_lots_{STAGE251_TAG}.csv"
STAGE251_CURVE_IN = STAGE251_DIR / f"{STAGE251_PREFIX}_curve_{STAGE251_TAG}.csv"
STAGE251_SUMMARY_IN = STAGE251_DIR / f"{STAGE251_PREFIX}_summary_{STAGE251_TAG}.csv"

SIGNALS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cot_signals_{MODEL_TAG}.csv"
SOURCE_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_source_summary_{MODEL_TAG}.csv"
JOINED_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_joined_entry_audit_{MODEL_TAG}.csv"
STATE_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_state_summary_{MODEL_TAG}.csv"
COVERAGE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_coverage_{MODEL_TAG}.csv"
SPLIT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_split_stability_{MODEL_TAG}.csv"
GATE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_promotion_gate_{MODEL_TAG}.csv"
SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_cot_coverage_{MODEL_TAG}.png"
STATE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_state_rate_chart_{MODEL_TAG}.png"
COVERAGE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_coverage_heatmap_{MODEL_TAG}.png"
SPLIT_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_split_stability_heatmap_{MODEL_TAG}.png"
GATE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_promotion_gate_chart_{MODEL_TAG}.png"

START_YEAR = 2020
END_YEAR = 2026
ROLLING_WEEKS = 156
MIN_ROLLING_WEEKS = 52
MAX_SIGNAL_AGE_DAYS = 45


@dataclass(frozen=True)
class ProductCotMapping:
    product_vt_symbol: str
    cftc_market_name: str
    source_name: str
    mapping_type: str
    confidence: float


PRODUCT_COT_MAPPINGS: tuple[ProductCotMapping, ...] = (
    ProductCotMapping("CF.CZCE", "COTTON NO. 2 - ICE FUTURES U.S.", "CFTC COT Cotton No.2", "direct_global_proxy", 0.70),
    ProductCotMapping("OI.CZCE", "SOYBEAN OIL - CHICAGO BOARD OF TRADE", "CFTC COT Soybean Oil", "oilseed_proxy", 0.60),
    ProductCotMapping("lh.DCE", "LEAN HOGS - CHICAGO MERCANTILE EXCHANGE", "CFTC COT Lean Hogs", "direct_global_proxy", 0.70),
    ProductCotMapping("lc.GFEX", "LITHIUM HYDROXIDE  - COMMODITY EXCHANGE INC.", "CFTC COT Lithium Hydroxide", "new_market_proxy", 0.45),
    ProductCotMapping("au.SHFE", "GOLD - COMMODITY EXCHANGE INC.", "CFTC COT Gold", "direct_global_proxy", 0.75),
    ProductCotMapping("cu.SHFE", "COPPER- #1 - COMMODITY EXCHANGE INC.", "CFTC COT Copper", "direct_global_proxy", 0.75),
    ProductCotMapping("fu.SHFE", "FUEL OIL-3% USGC/3.5% FOB RDAM - ICE FUTURES ENERGY DIV", "CFTC COT Fuel Oil", "energy_proxy", 0.50),
    ProductCotMapping("hc.SHFE", "STEEL-HRC - COMMODITY EXCHANGE INC.", "CFTC COT HRC Steel", "steel_proxy", 0.55),
    ProductCotMapping("rb.SHFE", "STEEL-HRC - COMMODITY EXCHANGE INC.", "CFTC COT HRC Steel", "steel_proxy", 0.55),
)


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise RuntimeError(f"missing required input: {path}")
    return pd.read_csv(path, encoding="utf-8-sig")


def _write_csv(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, encoding="utf-8-sig")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_json_safe(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


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
        number = float(value)
        return number if np.isfinite(number) else None
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if pd.isna(value):
        return None
    return value


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if pd.isna(value):
            return default
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if np.isfinite(number) else default


def _safe_div(num: float, den: float) -> float:
    return float(num) / float(den) if abs(float(den)) > 1e-12 else np.nan


def _product_key(product: Any, exchange: Any) -> str:
    product_text = str(product)
    if "." in product_text:
        return product_text
    exchange_text = str(exchange)
    return f"{product_text}.{exchange_text}" if exchange_text and exchange_text != "nan" else product_text


def _load_cftc_raw() -> pd.DataFrame:
    use_columns = [
        "Market_and_Exchange_Names",
        "Report_Date_as_YYYY-MM-DD",
        "Open_Interest_All",
        "M_Money_Positions_Long_All",
        "M_Money_Positions_Short_All",
        "Change_in_M_Money_Long_All",
        "Change_in_M_Money_Short_All",
    ]
    frames: list[pd.DataFrame] = []
    for year in range(START_YEAR, END_YEAR + 1):
        zip_path = CFTC_CACHE_DIR / f"fut_disagg_txt_{year}.zip"
        if not zip_path.exists() or zip_path.stat().st_size <= 0:
            raise RuntimeError(f"missing CFTC cache zip: {zip_path}")
        with zipfile.ZipFile(zip_path) as archive:
            member = archive.namelist()[0]
            payload = archive.read(member)
        frame = pd.read_csv(io.BytesIO(payload), usecols=use_columns, low_memory=False)
        frame["source_year"] = year
        frame["source_zip"] = str(zip_path)
        frames.append(frame)
    raw = pd.concat(frames, ignore_index=True)
    raw["Report_Date_as_YYYY-MM-DD"] = pd.to_datetime(raw["Report_Date_as_YYYY-MM-DD"], errors="coerce")
    raw = raw[raw["Report_Date_as_YYYY-MM-DD"].notna()].copy()
    for column in use_columns[2:]:
        raw[column] = pd.to_numeric(raw[column], errors="coerce").fillna(0.0)
    raw.sort_values(["Market_and_Exchange_Names", "Report_Date_as_YYYY-MM-DD"], inplace=True)
    raw.reset_index(drop=True, inplace=True)
    return raw


def _rolling_zscore(series: pd.Series) -> pd.Series:
    mean = series.rolling(ROLLING_WEEKS, min_periods=MIN_ROLLING_WEEKS).mean()
    std = series.rolling(ROLLING_WEEKS, min_periods=MIN_ROLLING_WEEKS).std().replace(0.0, np.nan)
    return ((series - mean) / std).replace([np.inf, -np.inf], np.nan)


def _build_cot_features(raw: pd.DataFrame) -> pd.DataFrame:
    frame = raw.copy()
    oi = frame["Open_Interest_All"].replace(0.0, np.nan)
    frame["managed_money_net_oi"] = (frame["M_Money_Positions_Long_All"] - frame["M_Money_Positions_Short_All"]) / oi
    frame["managed_money_flow_oi"] = (frame["Change_in_M_Money_Long_All"] - frame["Change_in_M_Money_Short_All"]) / oi
    chunks: list[pd.DataFrame] = []
    for _, group in frame.groupby("Market_and_Exchange_Names", sort=False):
        group = group.sort_values("Report_Date_as_YYYY-MM-DD").copy()
        group["managed_money_net_z"] = _rolling_zscore(group["managed_money_net_oi"])
        group["managed_money_flow_z"] = _rolling_zscore(group["managed_money_flow_oi"])
        chunks.append(group)
    features = pd.concat(chunks, ignore_index=True)
    features["managed_money_net_component"] = (features["managed_money_net_z"].clip(-2.0, 2.0) / 2.0).fillna(0.0)
    features["managed_money_flow_component"] = (features["managed_money_flow_z"].clip(-2.0, 2.0) / 2.0).fillna(0.0)
    features["cot_directional_component"] = (
        0.35 * features["managed_money_net_component"] + 0.65 * features["managed_money_flow_component"]
    ).clip(-1.0, 1.0)
    features["available_datetime"] = features["Report_Date_as_YYYY-MM-DD"] + pd.Timedelta(days=4, hours=8)
    return features


def _build_signals(features: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    signal_rows: list[dict[str, Any]] = []
    source_rows: list[dict[str, Any]] = []
    markets = set(features["Market_and_Exchange_Names"].astype(str))
    for mapping in PRODUCT_COT_MAPPINGS:
        market = features[features["Market_and_Exchange_Names"].astype(str).eq(mapping.cftc_market_name)].copy()
        source_rows.append(
            {
                "product_vt_symbol": mapping.product_vt_symbol,
                "cftc_market_name": mapping.cftc_market_name,
                "source_name": mapping.source_name,
                "mapping_type": mapping.mapping_type,
                "confidence": mapping.confidence,
                "market_available": int(mapping.cftc_market_name in markets),
                "raw_rows": int(len(market)),
                "signal_start": str(market["available_datetime"].min()) if not market.empty else "",
                "signal_end": str(market["available_datetime"].max()) if not market.empty else "",
            }
        )
        if market.empty:
            continue
        for _, row in market.iterrows():
            for direction, sign in [("long", 1.0), ("short", -1.0)]:
                quality = float(np.clip(sign * _safe_float(row["cot_directional_component"]), -1.0, 1.0))
                signal_rows.append(
                    {
                        "product_vt_symbol": mapping.product_vt_symbol,
                        "direction": direction,
                        "available_datetime": row["available_datetime"],
                        "report_date": row["Report_Date_as_YYYY-MM-DD"],
                        "source_name": mapping.source_name,
                        "cftc_market_name": mapping.cftc_market_name,
                        "mapping_type": mapping.mapping_type,
                        "mapping_confidence": mapping.confidence,
                        "managed_money_net_oi": row["managed_money_net_oi"],
                        "managed_money_flow_oi": row["managed_money_flow_oi"],
                        "managed_money_net_z": row["managed_money_net_z"],
                        "managed_money_flow_z": row["managed_money_flow_z"],
                        "cot_directional_component": row["cot_directional_component"],
                        "cot_external_quality_score": quality,
                        "signal_state": _signal_state(quality),
                    }
                )
    signals = pd.DataFrame(signal_rows)
    if not signals.empty:
        signals.sort_values(["product_vt_symbol", "direction", "available_datetime"], inplace=True)
        signals.reset_index(drop=True, inplace=True)
    return signals, pd.DataFrame(source_rows)


def _signal_state(score: float) -> str:
    if not np.isfinite(score):
        return "cot_missing"
    if score <= -0.25:
        return "cot_headwind"
    if score >= 0.25:
        return "cot_supportive"
    return "cot_neutral"


def _load_stage239_rows() -> pd.DataFrame:
    rows = _read_csv(STAGE239_JOINED_IN)
    required = {
        "candidate_index",
        "official_open_trade_id",
        "direction",
        "decision_ts",
        "official_open_date",
        "exchange",
        "product",
        "vt_symbol",
        "risk_bad_label",
        "right_tail_visual",
        "bottom_loss_visual",
        "decision_year",
    }
    missing = sorted(required.difference(rows.columns))
    if missing:
        raise RuntimeError(f"Stage239 joined rows missing columns: {missing}")
    rows["decision_ts"] = pd.to_datetime(rows["decision_ts"], errors="coerce")
    rows["official_open_date"] = pd.to_datetime(rows["official_open_date"], errors="coerce").dt.normalize()
    rows["product_vt_symbol"] = rows.apply(lambda r: _product_key(r["product"], r["exchange"]), axis=1)
    rows["direction"] = rows["direction"].astype(str)

    closed = _read_csv(STAGE251_CLOSED_LOTS_IN)
    pnl = (
        closed.groupby("open_trade_id", dropna=False)
        .agg(order_realized_pnl=("realized_pnl", "sum"), closed_lot_rows=("lot_id", "count"))
        .reset_index()
        .rename(columns={"open_trade_id": "official_open_trade_id"})
    )
    rows = rows.merge(pnl, on="official_open_trade_id", how="left")
    rows["order_realized_pnl"] = pd.to_numeric(rows["order_realized_pnl"], errors="coerce").fillna(0.0)
    rows["closed_lot_rows"] = pd.to_numeric(rows["closed_lot_rows"], errors="coerce").fillna(0).astype(int)
    return rows


def _join_signals(rows: pd.DataFrame, signals: pd.DataFrame) -> pd.DataFrame:
    mapping_by_product = {mapping.product_vt_symbol: mapping for mapping in PRODUCT_COT_MAPPINGS}
    joined_parts: list[pd.DataFrame] = []
    for (product, direction), group in rows.groupby(["product_vt_symbol", "direction"], dropna=False):
        group = group.sort_values("decision_ts").copy()
        signal_group = signals[
            signals["product_vt_symbol"].astype(str).eq(str(product)) & signals["direction"].astype(str).eq(str(direction))
        ].sort_values("available_datetime")
        if signal_group.empty:
            group["cot_matched"] = 0
            group["cot_match_reason"] = "product_not_mapped" if product not in mapping_by_product else "no_cot_signal_for_product"
            for column in [
                "available_datetime",
                "report_date",
                "source_name",
                "cftc_market_name",
                "mapping_type",
                "mapping_confidence",
                "cot_external_quality_score",
                "signal_state",
            ]:
                group[column] = np.nan
            joined_parts.append(group)
            continue
        merged = pd.merge_asof(
            group,
            signal_group,
            left_on="decision_ts",
            right_on="available_datetime",
            direction="backward",
            tolerance=pd.Timedelta(days=MAX_SIGNAL_AGE_DAYS),
        )
        merged["cot_matched"] = merged["available_datetime"].notna().astype(int)
        merged["cot_match_reason"] = np.where(
            merged["cot_matched"].eq(1),
            "matched_lagged_cot",
            "mapped_but_no_signal_within_lag_window",
        )
        joined_parts.append(merged)
    joined = pd.concat(joined_parts, ignore_index=True)
    product_base = joined["product_vt_symbol"] if "product_vt_symbol" in joined.columns else pd.Series(index=joined.index, dtype=object)
    if "product_vt_symbol_x" in joined.columns:
        product_base = product_base.combine_first(joined["product_vt_symbol_x"])
    joined["entry_product_vt_symbol"] = product_base
    joined["cot_product_vt_symbol"] = joined["product_vt_symbol_y"] if "product_vt_symbol_y" in joined.columns else np.nan
    joined["product_vt_symbol"] = joined["entry_product_vt_symbol"]
    direction_base = joined["direction"] if "direction" in joined.columns else pd.Series(index=joined.index, dtype=object)
    if "direction_x" in joined.columns:
        direction_base = direction_base.combine_first(joined["direction_x"])
    joined["entry_direction"] = direction_base
    joined["cot_signal_direction"] = joined["direction_y"] if "direction_y" in joined.columns else np.nan
    joined["direction"] = joined["entry_direction"]
    joined["cot_audit_group"] = np.where(joined["cot_matched"].eq(1), joined["signal_state"].astype(str), "cot_missing_or_unmapped")
    joined["cot_signal_age_days"] = (
        (joined["decision_ts"] - pd.to_datetime(joined["available_datetime"], errors="coerce")).dt.total_seconds() / 86400.0
    )
    return joined.sort_values("candidate_index").reset_index(drop=True)


def _state_summary(joined: pd.DataFrame) -> pd.DataFrame:
    total_pnl = float(joined["order_realized_pnl"].sum())
    total_rt = int(joined["right_tail_visual"].sum())
    total_bl = int(joined["bottom_loss_visual"].sum())
    grouped = (
        joined.groupby("cot_audit_group", dropna=False)
        .agg(
            order_count=("candidate_index", "count"),
            product_count=("product_vt_symbol", "nunique"),
            year_count=("decision_year", "nunique"),
            pnl_sum=("order_realized_pnl", "sum"),
            pnl_mean=("order_realized_pnl", "mean"),
            pnl_min=("order_realized_pnl", "min"),
            pnl_max=("order_realized_pnl", "max"),
            risk_bad_count=("risk_bad_label", "sum"),
            right_tail_count=("right_tail_visual", "sum"),
            bottom_loss_count=("bottom_loss_visual", "sum"),
            matched_count=("cot_matched", "sum"),
            avg_signal_age_days=("cot_signal_age_days", "mean"),
            avg_mapping_confidence=("mapping_confidence", "mean"),
            avg_cot_quality=("cot_external_quality_score", "mean"),
        )
        .reset_index()
    )
    grouped["risk_bad_rate"] = grouped["risk_bad_count"] / grouped["order_count"]
    grouped["right_tail_rate"] = grouped["right_tail_count"] / grouped["order_count"]
    grouped["bottom_loss_rate"] = grouped["bottom_loss_count"] / grouped["order_count"]
    grouped["pnl_share"] = grouped["pnl_sum"] / total_pnl if abs(total_pnl) > 1e-12 else np.nan
    grouped["right_tail_capture_rate"] = grouped["right_tail_count"] / total_rt if total_rt else np.nan
    grouped["bottom_loss_capture_rate"] = grouped["bottom_loss_count"] / total_bl if total_bl else np.nan
    grouped["pnl_sign_conflict"] = (grouped["pnl_min"].lt(0) & grouped["pnl_max"].gt(0)).astype(int)
    order = pd.CategoricalDtype(["cot_headwind", "cot_neutral", "cot_supportive", "cot_missing_or_unmapped"], ordered=True)
    grouped["cot_audit_group"] = grouped["cot_audit_group"].astype(order)
    return grouped.sort_values("cot_audit_group").reset_index(drop=True)


def _coverage(joined: pd.DataFrame) -> pd.DataFrame:
    coverage = (
        joined.groupby(["product_vt_symbol", "exchange", "decision_year"], dropna=False)
        .agg(
            order_count=("candidate_index", "count"),
            matched_count=("cot_matched", "sum"),
            right_tail_count=("right_tail_visual", "sum"),
            bottom_loss_count=("bottom_loss_visual", "sum"),
            pnl_sum=("order_realized_pnl", "sum"),
        )
        .reset_index()
    )
    coverage["matched_rate"] = coverage["matched_count"] / coverage["order_count"]
    coverage["product_mapped"] = coverage["product_vt_symbol"].isin({m.product_vt_symbol for m in PRODUCT_COT_MAPPINGS}).astype(int)
    return coverage


def _split_stability(joined: pd.DataFrame) -> pd.DataFrame:
    records: list[dict[str, Any]] = []
    for split_type, column in [("year", "decision_year"), ("exchange", "exchange"), ("direction", "direction")]:
        for split_value, group in joined[joined["cot_matched"].eq(1)].groupby(column, dropna=False):
            if len(group) < 8:
                continue
            supportive = group[group["cot_audit_group"].eq("cot_supportive")]
            non_support = group[~group["cot_audit_group"].eq("cot_supportive")]
            if len(supportive) < 3 or len(non_support) < 3:
                records.append(
                    {
                        "split_type": split_type,
                        "split_value": split_value,
                        "split_row_count": int(len(group)),
                        "supportive_count": int(len(supportive)),
                        "non_support_count": int(len(non_support)),
                        "valid_for_stability": 0,
                        "split_pass": 0,
                        "block_reason": "insufficient_supportive_or_non_support_count",
                    }
                )
                continue
            sup_risk = _safe_div(supportive["risk_bad_label"].sum(), len(supportive))
            ns_risk = _safe_div(non_support["risk_bad_label"].sum(), len(non_support))
            sup_tail = _safe_div(supportive["right_tail_visual"].sum(), len(supportive))
            ns_tail = _safe_div(non_support["right_tail_visual"].sum(), len(non_support))
            sup_bottom = _safe_div(supportive["bottom_loss_visual"].sum(), len(supportive))
            ns_bottom = _safe_div(non_support["bottom_loss_visual"].sum(), len(non_support))
            sup_pnl = _safe_div(supportive["order_realized_pnl"].sum(), len(supportive))
            ns_pnl = _safe_div(non_support["order_realized_pnl"].sum(), len(non_support))
            risk_diff = sup_risk - ns_risk
            tail_diff = sup_tail - ns_tail
            bottom_diff = sup_bottom - ns_bottom
            pnl_diff = sup_pnl - ns_pnl
            split_pass = int(risk_diff <= -0.05 and tail_diff >= 0.0 and bottom_diff <= 0.0 and pnl_diff >= 0.0)
            records.append(
                {
                    "split_type": split_type,
                    "split_value": split_value,
                    "split_row_count": int(len(group)),
                    "supportive_count": int(len(supportive)),
                    "non_support_count": int(len(non_support)),
                    "valid_for_stability": 1,
                    "supportive_risk_bad_rate": sup_risk,
                    "non_support_risk_bad_rate": ns_risk,
                    "risk_bad_rate_diff": risk_diff,
                    "supportive_right_tail_rate": sup_tail,
                    "non_support_right_tail_rate": ns_tail,
                    "right_tail_rate_diff": tail_diff,
                    "supportive_bottom_loss_rate": sup_bottom,
                    "non_support_bottom_loss_rate": ns_bottom,
                    "bottom_loss_rate_diff": bottom_diff,
                    "supportive_pnl_per_order": sup_pnl,
                    "non_support_pnl_per_order": ns_pnl,
                    "pnl_per_order_diff": pnl_diff,
                    "split_pass": split_pass,
                    "block_reason": "" if split_pass else "supportive_not_lower_risk_with_tail_pnl_preserved",
                }
            )
    return pd.DataFrame(records)


def _promotion_gate(joined: pd.DataFrame, state_summary: pd.DataFrame, split: pd.DataFrame) -> pd.DataFrame:
    matched = joined[joined["cot_matched"].eq(1)]
    supportive = joined[joined["cot_audit_group"].eq("cot_supportive")]
    non_support = matched[~matched["cot_audit_group"].eq("cot_supportive")]
    direct = matched[matched["mapping_type"].astype(str).eq("direct_global_proxy")]
    total_rt = int(joined["right_tail_visual"].sum())
    total_bl = int(joined["bottom_loss_visual"].sum())

    matched_rate = _safe_div(len(matched), len(joined))
    direct_rate = _safe_div(len(direct), len(matched)) if len(matched) else np.nan
    sup_risk = _safe_div(supportive["risk_bad_label"].sum(), len(supportive)) if len(supportive) else np.nan
    ns_risk = _safe_div(non_support["risk_bad_label"].sum(), len(non_support)) if len(non_support) else np.nan
    risk_reduction = ns_risk - sup_risk if np.isfinite(sup_risk) and np.isfinite(ns_risk) else np.nan
    sup_tail_capture = _safe_div(supportive["right_tail_visual"].sum(), total_rt) if total_rt else np.nan
    sup_bottom_capture = _safe_div(supportive["bottom_loss_visual"].sum(), total_bl) if total_bl else np.nan
    sup_row = state_summary[state_summary["cot_audit_group"].astype(str).eq("cot_supportive")]
    pnl_sign_conflict = int(sup_row["pnl_sign_conflict"].iloc[0]) if not sup_row.empty else 1
    valid_split = split[split["valid_for_stability"].eq(1)] if not split.empty else pd.DataFrame()
    split_pass_share = _safe_div(valid_split["split_pass"].sum(), len(valid_split)) if len(valid_split) else np.nan

    gates = [
        {
            "gate_id": "matched_coverage_ge60pct",
            "evidence_value": matched_rate,
            "pass_for_true_engine": int(np.isfinite(matched_rate) and matched_rate >= 0.60),
            "judgment": "pass" if np.isfinite(matched_rate) and matched_rate >= 0.60 else "fail_low_c9_product_mapping_coverage",
        },
        {
            "gate_id": "direct_mapping_share_ge50pct",
            "evidence_value": direct_rate,
            "pass_for_true_engine": int(np.isfinite(direct_rate) and direct_rate >= 0.50),
            "judgment": "pass" if np.isfinite(direct_rate) and direct_rate >= 0.50 else "fail_too_many_proxy_mappings",
        },
        {
            "gate_id": "supportive_sample_min30",
            "evidence_value": len(supportive),
            "pass_for_true_engine": int(len(supportive) >= 30),
            "judgment": "pass" if len(supportive) >= 30 else "fail_supportive_sample_too_small",
        },
        {
            "gate_id": "supportive_risk_reduction_5pp",
            "evidence_value": risk_reduction,
            "pass_for_true_engine": int(np.isfinite(risk_reduction) and risk_reduction >= 0.05),
            "judgment": "pass" if np.isfinite(risk_reduction) and risk_reduction >= 0.05 else "fail_no_material_risk_reduction",
        },
        {
            "gate_id": "supportive_right_tail_capture_40pct",
            "evidence_value": sup_tail_capture,
            "pass_for_true_engine": int(np.isfinite(sup_tail_capture) and sup_tail_capture >= 0.40),
            "judgment": "pass" if np.isfinite(sup_tail_capture) and sup_tail_capture >= 0.40 else "fail_right_tail_not_preserved",
        },
        {
            "gate_id": "supportive_bottom_loss_capture_le25pct",
            "evidence_value": sup_bottom_capture,
            "pass_for_true_engine": int(np.isfinite(sup_bottom_capture) and sup_bottom_capture <= 0.25),
            "judgment": "pass" if np.isfinite(sup_bottom_capture) and sup_bottom_capture <= 0.25 else "fail_bottom_loss_contaminated",
        },
        {
            "gate_id": "no_supportive_pnl_sign_conflict",
            "evidence_value": pnl_sign_conflict,
            "pass_for_true_engine": int(pnl_sign_conflict == 0),
            "judgment": "pass" if pnl_sign_conflict == 0 else "fail_mixed_pnl_state",
        },
        {
            "gate_id": "split_stability_60pct",
            "evidence_value": split_pass_share,
            "pass_for_true_engine": int(np.isfinite(split_pass_share) and split_pass_share >= 0.60),
            "judgment": "pass" if np.isfinite(split_pass_share) and split_pass_share >= 0.60 else "fail_cross_split_instability",
        },
        {
            "gate_id": "no_rule_no_engine_isolation",
            "evidence_value": 0,
            "pass_for_true_engine": 1,
            "judgment": "technical_pass",
        },
    ]
    gate = pd.DataFrame(gates)
    gate["strategy_feature_usable"] = 0
    return gate


def _summary(joined: pd.DataFrame, state_summary: pd.DataFrame, split: pd.DataFrame, gate: pd.DataFrame) -> pd.DataFrame:
    official = _read_csv(STAGE251_SUMMARY_IN)
    official_row = official[official["arm"].astype(str).eq("A_official_stage847_c9_15w")].iloc[0].to_dict()
    matched = joined[joined["cot_matched"].eq(1)]
    supportive = joined[joined["cot_audit_group"].eq("cot_supportive")]
    non_support = matched[~matched["cot_audit_group"].eq("cot_supportive")]
    total_rt = int(joined["right_tail_visual"].sum())
    total_bl = int(joined["bottom_loss_visual"].sum())
    valid_split = split[split["valid_for_stability"].eq(1)] if not split.empty else pd.DataFrame()
    gate_pass_count = int(gate["pass_for_true_engine"].sum())
    decision = (
        "stage256_cftc_cot_context_preflight_passes_true_engine_required"
        if gate_pass_count == len(gate)
        else "stage256_cftc_cot_context_low_coverage_tail_conflict_no_rule"
    )
    return pd.DataFrame(
        [
            {
                "stage": STAGE,
                "model_tag": MODEL_TAG,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "line_id": LINE_ID,
                "decision": decision,
                "stage_nature": "read_only_cftc_cot_cross_market_context_audit",
                "official_config_changed": 0,
                "strategy_rule_created": 0,
                "true_engine_run": 0,
                "ab_triggered": 0,
                "order_api_called": 0,
                "ctp_or_simnow_connected": 0,
                "cot_start_year": START_YEAR,
                "cot_end_year": END_YEAR,
                "rolling_weeks": ROLLING_WEEKS,
                "min_rolling_weeks": MIN_ROLLING_WEEKS,
                "max_signal_age_days": MAX_SIGNAL_AGE_DAYS,
                "entry_order_count": int(len(joined)),
                "mapped_matched_order_count": int(len(matched)),
                "matched_coverage_rate": _safe_div(len(matched), len(joined)),
                "supportive_order_count": int(len(supportive)),
                "supportive_risk_bad_rate": _safe_div(supportive["risk_bad_label"].sum(), len(supportive)) if len(supportive) else np.nan,
                "non_support_risk_bad_rate": _safe_div(non_support["risk_bad_label"].sum(), len(non_support)) if len(non_support) else np.nan,
                "supportive_risk_reduction_vs_non_support": (
                    _safe_div(non_support["risk_bad_label"].sum(), len(non_support))
                    - _safe_div(supportive["risk_bad_label"].sum(), len(supportive))
                    if len(supportive) and len(non_support)
                    else np.nan
                ),
                "supportive_right_tail_count": int(supportive["right_tail_visual"].sum()),
                "supportive_right_tail_capture_rate": _safe_div(supportive["right_tail_visual"].sum(), total_rt) if total_rt else np.nan,
                "supportive_bottom_loss_count": int(supportive["bottom_loss_visual"].sum()),
                "supportive_bottom_loss_capture_rate": _safe_div(supportive["bottom_loss_visual"].sum(), total_bl) if total_bl else np.nan,
                "supportive_pnl_sum": float(supportive["order_realized_pnl"].sum()) if len(supportive) else 0.0,
                "valid_split_count": int(len(valid_split)),
                "split_pass_count": int(valid_split["split_pass"].sum()) if len(valid_split) else 0,
                "promotion_gate_count": int(len(gate)),
                "promotion_gate_pass_count": gate_pass_count,
                "strategy_feature_usable": 0,
                "objective_completion_proven": 0,
                "official_end_equity": _safe_float(official_row.get("end_equity"), np.nan),
                "official_total_return_pct": _safe_float(official_row.get("total_return_pct"), np.nan),
                "official_max_dd_pct": _safe_float(official_row.get("max_dd_pct"), np.nan),
                "official_sharpe": _safe_float(official_row.get("sharpe"), np.nan),
                "official_total_slippage": _safe_float(official_row.get("total_slippage"), np.nan),
                "official_total_trade_count": _safe_float(official_row.get("total_trade_count"), np.nan),
                "official_win_rate_pct": _safe_float(official_row.get("nonzero_daily_win_rate_pct"), np.nan),
                "official_broker10_peak_pct": _safe_float(official_row.get("max_broker10_margin_to_equity_pct"), np.nan),
                "visual_file_count": 5,
            }
        ]
    )


def _plot_official_path(curve: pd.DataFrame, joined: pd.DataFrame) -> None:
    curve = curve[curve["arm"].astype(str).eq("A_official_stage847_c9_15w")].copy()
    curve["date"] = pd.to_datetime(curve["date"], errors="coerce").dt.normalize()
    curve = curve.sort_values("date")
    points = joined[["official_open_date", "cot_audit_group"]].merge(
        curve[["date", "account_equity"]], left_on="official_open_date", right_on="date", how="left"
    )
    fig, axes = plt.subplots(3, 1, figsize=(15, 10), sharex=True, gridspec_kw={"height_ratios": [2.0, 1.0, 1.0]})
    axes[0].plot(curve["date"], curve["account_equity"], color="#0f172a", linewidth=1.2)
    colors = {
        "cot_supportive": "#16a34a",
        "cot_neutral": "#64748b",
        "cot_headwind": "#dc2626",
        "cot_missing_or_unmapped": "#cbd5e1",
    }
    for group_name, group in points.groupby("cot_audit_group"):
        axes[0].scatter(group["official_open_date"], group["account_equity"], s=20, alpha=0.75, color=colors.get(group_name, "#64748b"), label=group_name)
    axes[1].plot(curve["date"], curve["drawdown_pct"], color="#dc2626", linewidth=1.0)
    daily = joined.groupby(["official_open_date", "cot_audit_group"]).size().unstack(fill_value=0)
    for group_name in ["cot_supportive", "cot_neutral", "cot_headwind", "cot_missing_or_unmapped"]:
        if group_name in daily.columns:
            axes[2].bar(daily.index, daily[group_name], bottom=daily[[c for c in daily.columns if c < group_name]].sum(axis=1) if False else None, color=colors[group_name], alpha=0.8, label=group_name)
    axes[0].set_title("Stage256 official path with lagged CFTC COT context markers")
    axes[0].set_ylabel("equity")
    axes[1].set_ylabel("drawdown %")
    axes[2].set_ylabel("entry count")
    for ax in axes:
        ax.grid(True, alpha=0.25)
    axes[0].legend(fontsize=8, ncol=2)
    axes[2].legend(fontsize=8, ncol=2)
    fig.tight_layout()
    fig.savefig(PATH_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_state_rates(state_summary: pd.DataFrame) -> None:
    data = state_summary.copy()
    data["group"] = data["cot_audit_group"].astype(str)
    x = np.arange(len(data))
    width = 0.24
    fig, axes = plt.subplots(2, 1, figsize=(11.5, 7.2), sharex=True)
    axes[0].bar(x - width, data["risk_bad_rate"], width=width, label="risk_bad", color="#dc2626")
    axes[0].bar(x, data["right_tail_rate"], width=width, label="right_tail", color="#16a34a")
    axes[0].bar(x + width, data["bottom_loss_rate"], width=width, label="bottom_loss", color="#f97316")
    axes[0].set_ylabel("rate")
    axes[0].legend()
    axes[0].grid(True, axis="y", alpha=0.25)
    axes[1].bar(x, data["pnl_sum"], color=["#16a34a" if g == "cot_supportive" else "#dc2626" if g == "cot_headwind" else "#64748b" for g in data["group"]])
    axes[1].axhline(0, color="#111827", linewidth=0.8)
    axes[1].set_ylabel("PnL sum")
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(data["group"], rotation=15, ha="right")
    axes[1].grid(True, axis="y", alpha=0.25)
    axes[0].set_title("Stage256 COT state rates and contribution")
    fig.tight_layout()
    fig.savefig(STATE_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_coverage(coverage: pd.DataFrame) -> None:
    pivot = coverage.pivot_table(index="product_vt_symbol", columns="decision_year", values="matched_rate", aggfunc="mean").fillna(0.0)
    fig, ax = plt.subplots(figsize=(12, max(5, 0.32 * len(pivot))))
    im = ax.imshow(pivot.to_numpy(), aspect="auto", cmap="RdYlGn", vmin=0.0, vmax=1.0)
    ax.set_xticks(np.arange(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns)
    ax.set_yticks(np.arange(len(pivot.index)))
    ax.set_yticklabels(pivot.index, fontsize=8)
    for i in range(pivot.shape[0]):
        for j in range(pivot.shape[1]):
            ax.text(j, i, f"{pivot.iat[i, j]:.0%}", ha="center", va="center", fontsize=7)
    ax.set_title("Stage256 lagged COT match rate by product-year")
    fig.colorbar(im, ax=ax, fraction=0.035, pad=0.02)
    fig.tight_layout()
    fig.savefig(COVERAGE_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_split(split: pd.DataFrame) -> None:
    if split.empty:
        return
    valid = split[split["valid_for_stability"].eq(1)].copy()
    if valid.empty:
        valid = split.copy()
        for col in ["risk_bad_rate_diff", "right_tail_rate_diff", "bottom_loss_rate_diff", "pnl_per_order_diff"]:
            if col not in valid.columns:
                valid[col] = np.nan
    valid["label"] = valid["split_type"].astype(str) + ":" + valid["split_value"].astype(str)
    metrics = ["risk_bad_rate_diff", "right_tail_rate_diff", "bottom_loss_rate_diff", "pnl_per_order_diff"]
    matrix = valid.set_index("label")[metrics].astype(float).fillna(0.0)
    limit = max(1e-9, abs(matrix.min().min()), abs(matrix.max().max()))
    fig, ax = plt.subplots(figsize=(10.5, max(4.5, 0.38 * len(matrix))))
    im = ax.imshow(matrix.to_numpy(), aspect="auto", cmap="RdYlGn", vmin=-limit, vmax=limit)
    ax.set_xticks(np.arange(len(metrics)))
    ax.set_xticklabels(metrics, rotation=20, ha="right")
    ax.set_yticks(np.arange(len(matrix.index)))
    ax.set_yticklabels(matrix.index, fontsize=8)
    for i in range(matrix.shape[0]):
        for j in range(matrix.shape[1]):
            value = matrix.iat[i, j]
            text = f"{value:.2f}" if "pnl" not in metrics[j] else f"{value/1000:.0f}k"
            ax.text(j, i, text, ha="center", va="center", fontsize=7)
    ax.set_title("Stage256 COT supportive minus non-supportive by split")
    fig.colorbar(im, ax=ax, fraction=0.035, pad=0.02)
    fig.tight_layout()
    fig.savefig(SPLIT_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_gate(gate: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(12.5, 5.5))
    colors = ["#16a34a" if int(v) else "#dc2626" for v in gate["pass_for_true_engine"]]
    x = np.arange(len(gate))
    ax.bar(x, gate["pass_for_true_engine"].astype(int), color=colors)
    ax.set_ylim(0, 1.2)
    ax.set_xticks(x)
    ax.set_xticklabels(gate["gate_id"], rotation=35, ha="right", fontsize=8)
    ax.set_ylabel("pass")
    ax.set_title("Stage256 COT promotion gate")
    for idx, row in gate.iterrows():
        ax.text(idx, 1.05, row["judgment"], rotation=90, ha="center", va="bottom", fontsize=7)
    ax.grid(True, axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(GATE_CHART_OUT, dpi=160)
    plt.close(fig)


def _write_report(summary: pd.Series, source_summary: pd.DataFrame, state_summary: pd.DataFrame, gate: pd.DataFrame) -> None:
    report = f"""# Stage256 CFTC COT Cross-Market Context Audit

- line_id: `{LINE_ID}`
- created_at: `{summary["created_at"]}`
- decision: `{summary["decision"]}`
- nature: read-only COT mapping/lag/quality audit; no strategy rule, no true engine, no A/B, no official config change, no CTP/order API

## External Research Judgment

CFTC COT is official weekly positioning data. It can be point-in-time if Tuesday reports are only made available after Friday release, but it is a broad cross-market context source, not a precise minute-entry signal. For domestic futures, mapping confidence and lag must be treated as hard gates.

## Key Metrics

- entry rows: `{summary["entry_order_count"]}`
- matched lagged COT rows: `{summary["mapped_matched_order_count"]}`
- matched coverage: `{summary["matched_coverage_rate"]:.4f}`
- supportive rows: `{summary["supportive_order_count"]}`
- supportive risk_bad_rate: `{summary["supportive_risk_bad_rate"]:.4f}`
- non-support risk_bad_rate: `{summary["non_support_risk_bad_rate"]:.4f}`
- supportive right-tail capture: `{summary["supportive_right_tail_capture_rate"]:.4f}`
- supportive bottom-loss capture: `{summary["supportive_bottom_loss_capture_rate"]:.4f}`
- gate pass: `{summary["promotion_gate_pass_count"]}/{summary["promotion_gate_count"]}`

## Source Summary

{source_summary.to_markdown(index=False)}

## State Summary

{state_summary.to_markdown(index=False)}

## Promotion Gate

{gate.to_markdown(index=False)}
"""
    _write_text(REPORT_OUT, report)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    raw = _load_cftc_raw()
    features = _build_cot_features(raw)
    signals, source_summary = _build_signals(features)
    rows = _load_stage239_rows()
    joined = _join_signals(rows, signals)
    state_summary = _state_summary(joined)
    coverage = _coverage(joined)
    split = _split_stability(joined)
    gate = _promotion_gate(joined, state_summary, split)
    summary = _summary(joined, state_summary, split, gate)

    _write_csv(signals, SIGNALS_OUT)
    _write_csv(source_summary, SOURCE_SUMMARY_OUT)
    _write_csv(joined, JOINED_OUT)
    _write_csv(state_summary, STATE_SUMMARY_OUT)
    _write_csv(coverage, COVERAGE_OUT)
    _write_csv(split, SPLIT_OUT)
    _write_csv(gate, GATE_OUT)
    _write_csv(summary, SUMMARY_OUT)
    _write_json(DECISION_OUT, summary.iloc[0].to_dict())
    _write_report(summary.iloc[0], source_summary, state_summary, gate)

    _plot_official_path(_read_csv(STAGE251_CURVE_IN), joined)
    _plot_state_rates(state_summary)
    _plot_coverage(coverage)
    _plot_split(split)
    _plot_gate(gate)


if __name__ == "__main__":
    main()
