from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import io
import json
from pathlib import Path
from typing import Any
import zipfile

import numpy as np
import pandas as pd

from stage038_candidate_pit_feature_matrix_audit import (
    ConditionSpec,
    build_purged_time_splits,
    summarize_condition_oos,
)


LINE_ID = "futures_trend_rebuilt_c9_15w_optimization"
STAGE = "Stage048"
MODEL_TAG = "stage048_cftc_cot_mapping_audit_v1"
OUTPUT_PREFIX = "rebuilt_c9_stage048_cftc_cot_mapping_audit"

START_YEAR = 2020
END_YEAR = 2026
ROLLING_WEEKS = 156
MIN_ROLLING_WEEKS = 52
MAX_SIGNAL_AGE_DAYS = 45
N_SPLITS = 4
EMBARGO_DAYS = 20

TOOLS_DIR = Path(__file__).resolve().parent
LINE_DIR = TOOLS_DIR.parent
REPO_ROOT = LINE_DIR.parents[2]
OUTPUT_DIR = LINE_DIR / "outputs" / "stage048_cftc_cot_mapping_audit"
STAGES_DIR = LINE_DIR / "stages"

BACKTEST_OUTPUTS = REPO_ROOT / "examples" / "portfolio_backtesting" / "backtest_outputs"
CFTC_CACHE_DIR = BACKTEST_OUTPUTS / "external_cftc_cot_cache"

STAGE038_OUTPUT_DIR = LINE_DIR / "outputs" / "stage038_candidate_pit_feature_matrix_audit"
STAGE038_PREFIX = "rebuilt_c9_stage038_candidate_pit_feature_matrix_audit"
STAGE038_TAG = "stage038_candidate_pit_feature_matrix_audit_v1"
STAGE038_FEATURE_MATRIX_PATH = STAGE038_OUTPUT_DIR / f"{STAGE038_PREFIX}_feature_matrix_{STAGE038_TAG}.csv"

SIGNALS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_signals_{MODEL_TAG}.csv"
SOURCE_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_source_summary_{MODEL_TAG}.csv"
JOINED_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_joined_feature_matrix_{MODEL_TAG}.csv"
CONDITION_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_condition_oos_summary_{MODEL_TAG}.csv"
FEATURE_COVERAGE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_feature_coverage_{MODEL_TAG}.csv"
PRODUCT_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_summary_{MODEL_TAG}.csv"
STATE_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_state_summary_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


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


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        number = float(value)
        return None if np.isnan(number) or np.isinf(number) else number
    if isinstance(value, (pd.Timestamp, datetime)):
        if pd.isna(value):
            return None
        return value.isoformat()
    if pd.isna(value):
        return None
    return value


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_无数据_"
    shown = frame.head(max_rows).copy() if max_rows is not None else frame.copy()
    for column in shown.columns:
        if pd.api.types.is_float_dtype(shown[column]):
            shown[column] = shown[column].map(lambda value: f"{value:.4f}" if pd.notna(value) else "")
    return shown.to_markdown(index=False)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if np.isfinite(number) else default


def _safe_div(num: float, den: float) -> float:
    return float(num) / float(den) if abs(float(den)) > 1e-12 else np.nan


def _product_key(value: Any) -> str:
    return str(value).strip().lower()


def _direction_key(value: Any) -> str:
    return str(value).strip().lower()


def _signal_state(score: float) -> str:
    if not np.isfinite(score):
        return "cot_missing"
    if score <= -0.25:
        return "cot_headwind"
    if score >= 0.25:
        return "cot_supportive"
    return "cot_neutral"


def _rolling_zscore(series: pd.Series, *, rolling_weeks: int, min_rolling_weeks: int) -> pd.Series:
    mean = series.rolling(rolling_weeks, min_periods=min_rolling_weeks).mean()
    std = series.rolling(rolling_weeks, min_periods=min_rolling_weeks).std().replace(0.0, np.nan)
    return ((series - mean) / std).replace([np.inf, -np.inf], np.nan)


def load_cftc_raw(
    cache_dir: Path = CFTC_CACHE_DIR,
    *,
    start_year: int = START_YEAR,
    end_year: int = END_YEAR,
) -> pd.DataFrame:
    use_columns = [
        "Market_and_Exchange_Names",
        "Report_Date_as_YYYY-MM-DD",
        "Open_Interest_All",
        "Prod_Merc_Positions_Long_All",
        "Prod_Merc_Positions_Short_All",
        "M_Money_Positions_Long_All",
        "M_Money_Positions_Short_All",
        "Change_in_M_Money_Long_All",
        "Change_in_M_Money_Short_All",
    ]
    frames: list[pd.DataFrame] = []
    for year in range(start_year, end_year + 1):
        zip_path = cache_dir / f"fut_disagg_txt_{year}.zip"
        if not zip_path.exists() or zip_path.stat().st_size <= 0:
            raise FileNotFoundError(f"missing CFTC cache zip: {zip_path}")
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
    return raw.sort_values(["Market_and_Exchange_Names", "Report_Date_as_YYYY-MM-DD"]).reset_index(drop=True)


def build_cot_feature_table(
    raw: pd.DataFrame,
    *,
    rolling_weeks: int = ROLLING_WEEKS,
    min_rolling_weeks: int = MIN_ROLLING_WEEKS,
) -> pd.DataFrame:
    frame = raw.copy()
    frame["Report_Date_as_YYYY-MM-DD"] = pd.to_datetime(frame["Report_Date_as_YYYY-MM-DD"], errors="coerce")
    numeric_columns = [
        "Open_Interest_All",
        "Prod_Merc_Positions_Long_All",
        "Prod_Merc_Positions_Short_All",
        "M_Money_Positions_Long_All",
        "M_Money_Positions_Short_All",
        "Change_in_M_Money_Long_All",
        "Change_in_M_Money_Short_All",
    ]
    for column in numeric_columns:
        frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(0.0)

    open_interest = frame["Open_Interest_All"].replace(0.0, np.nan)
    frame["producer_net_oi"] = (
        frame["Prod_Merc_Positions_Long_All"] - frame["Prod_Merc_Positions_Short_All"]
    ) / open_interest
    frame["managed_money_net_oi"] = (
        frame["M_Money_Positions_Long_All"] - frame["M_Money_Positions_Short_All"]
    ) / open_interest
    frame["managed_money_flow_oi"] = (
        frame["Change_in_M_Money_Long_All"] - frame["Change_in_M_Money_Short_All"]
    ) / open_interest

    chunks: list[pd.DataFrame] = []
    for _, group in frame.groupby("Market_and_Exchange_Names", sort=False):
        group = group.sort_values("Report_Date_as_YYYY-MM-DD").copy()
        group["producer_net_z"] = _rolling_zscore(
            group["producer_net_oi"],
            rolling_weeks=rolling_weeks,
            min_rolling_weeks=min_rolling_weeks,
        )
        group["managed_money_net_z"] = _rolling_zscore(
            group["managed_money_net_oi"],
            rolling_weeks=rolling_weeks,
            min_rolling_weeks=min_rolling_weeks,
        )
        group["managed_money_flow_z"] = _rolling_zscore(
            group["managed_money_flow_oi"],
            rolling_weeks=rolling_weeks,
            min_rolling_weeks=min_rolling_weeks,
        )
        chunks.append(group)
    features = pd.concat(chunks, ignore_index=True)
    features["managed_money_net_component"] = (features["managed_money_net_z"].clip(-2.0, 2.0) / 2.0).fillna(0.0)
    features["managed_money_flow_component"] = (features["managed_money_flow_z"].clip(-2.0, 2.0) / 2.0).fillna(0.0)
    features["cot_directional_component"] = (
        0.35 * features["managed_money_net_component"] + 0.65 * features["managed_money_flow_component"]
    ).clip(-1.0, 1.0)
    # COT reports are dated Tuesday and generally released Friday US time.
    # Saturday 08:00 China time is the conservative daily-join availability point.
    features["available_datetime"] = features["Report_Date_as_YYYY-MM-DD"] + pd.Timedelta(days=4, hours=8)
    return features.sort_values(["Market_and_Exchange_Names", "available_datetime"]).reset_index(drop=True)


def build_cot_signals(
    features: pd.DataFrame,
    mappings: tuple[ProductCotMapping, ...] = PRODUCT_COT_MAPPINGS,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows: list[dict[str, Any]] = []
    source_rows: list[dict[str, Any]] = []
    available_markets = set(features["Market_and_Exchange_Names"].astype(str).unique())
    for mapping in mappings:
        market = features[features["Market_and_Exchange_Names"].astype(str).eq(mapping.cftc_market_name)].copy()
        source_rows.append(
            {
                "product_vt_symbol": mapping.product_vt_symbol,
                "product_key": _product_key(mapping.product_vt_symbol),
                "cftc_market_name": mapping.cftc_market_name,
                "source_name": mapping.source_name,
                "mapping_type": mapping.mapping_type,
                "confidence": float(mapping.confidence),
                "market_available": int(mapping.cftc_market_name in available_markets),
                "raw_rows": int(len(market)),
                "signal_start": str(market["available_datetime"].min()) if not market.empty else "",
                "signal_end": str(market["available_datetime"].max()) if not market.empty else "",
            }
        )
        if market.empty:
            continue
        for _, row in market.iterrows():
            for direction, sign in (("long", 1.0), ("short", -1.0)):
                score = float(np.clip(sign * _safe_float(row.get("cot_directional_component")), -1.0, 1.0))
                rows.append(
                    {
                        "product_vt_symbol": mapping.product_vt_symbol,
                        "product_key": _product_key(mapping.product_vt_symbol),
                        "direction": direction,
                        "direction_key": direction,
                        "available_datetime": pd.Timestamp(row["available_datetime"]),
                        "report_date": pd.Timestamp(row["Report_Date_as_YYYY-MM-DD"]),
                        "source_name": mapping.source_name,
                        "cftc_market_name": mapping.cftc_market_name,
                        "mapping_type": mapping.mapping_type,
                        "mapping_confidence": float(mapping.confidence),
                        "producer_net_oi": row.get("producer_net_oi", np.nan),
                        "producer_net_z": row.get("producer_net_z", np.nan),
                        "managed_money_net_oi": row.get("managed_money_net_oi", np.nan),
                        "managed_money_flow_oi": row.get("managed_money_flow_oi", np.nan),
                        "managed_money_net_z": row.get("managed_money_net_z", np.nan),
                        "managed_money_flow_z": row.get("managed_money_flow_z", np.nan),
                        "cot_directional_component": row.get("cot_directional_component", np.nan),
                        "cot_external_quality_score": score,
                        "cot_signal_state": _signal_state(score),
                    }
                )
    signals = pd.DataFrame(rows)
    if not signals.empty:
        signals = signals.sort_values(["product_key", "direction_key", "available_datetime"]).reset_index(drop=True)
    return signals, pd.DataFrame(source_rows)


def attach_lagged_cot_features(
    entries: pd.DataFrame,
    signals: pd.DataFrame,
    *,
    max_signal_age_days: int = MAX_SIGNAL_AGE_DAYS,
) -> pd.DataFrame:
    result = entries.copy()
    result["entry_datetime"] = pd.to_datetime(result["entry_date"], errors="coerce")
    if "product_vt_symbol" in result.columns:
        product_source = result["product_vt_symbol"]
    elif "product" in result.columns:
        product_source = result["product"]
    else:
        product_source = pd.Series("", index=result.index)
    result["cot_product_key"] = product_source.map(_product_key)
    result["cot_direction_key"] = result.get("direction", pd.Series("", index=result.index)).map(_direction_key)

    output_columns = {
        "cot_available_datetime": pd.NaT,
        "cot_report_date": pd.NaT,
        "cot_source_name": "",
        "cot_cftc_market_name": "",
        "cot_mapping_type": "",
        "cot_mapping_confidence": np.nan,
        "cot_producer_net_oi": np.nan,
        "cot_producer_net_z": np.nan,
        "cot_managed_money_net_oi": np.nan,
        "cot_managed_money_flow_oi": np.nan,
        "cot_managed_money_net_z": np.nan,
        "cot_managed_money_flow_z": np.nan,
        "cot_directional_component": np.nan,
        "cot_external_quality_score": np.nan,
        "cot_signal_state": "cot_missing",
        "cot_signal_age_days": np.nan,
        "cot_matched": False,
    }
    for column, value in output_columns.items():
        result[column] = value
    result["cot_audit_group"] = "cot_missing_or_unmapped"

    if result.empty or signals.empty:
        return result

    signal_columns = [
        "available_datetime",
        "report_date",
        "source_name",
        "cftc_market_name",
        "mapping_type",
        "mapping_confidence",
        "producer_net_oi",
        "producer_net_z",
        "managed_money_net_oi",
        "managed_money_flow_oi",
        "managed_money_net_z",
        "managed_money_flow_z",
        "cot_directional_component",
        "cot_external_quality_score",
        "cot_signal_state",
    ]
    usable = signals.copy()
    usable["available_datetime"] = pd.to_datetime(usable["available_datetime"], errors="coerce")
    usable = usable.dropna(subset=["available_datetime"]).sort_values(["product_key", "direction_key", "available_datetime"])

    for key, group_index in result.groupby(["cot_product_key", "cot_direction_key"], dropna=False).groups.items():
        product_key, direction_key = key
        product_signals = usable[
            usable["product_key"].eq(product_key) & usable["direction_key"].eq(direction_key)
        ].sort_values("available_datetime")
        if product_signals.empty:
            continue
        entry_group = result.loc[group_index].sort_values("entry_datetime")
        attached = pd.merge_asof(
            entry_group[["entry_datetime"]].reset_index(),
            product_signals[signal_columns],
            left_on="entry_datetime",
            right_on="available_datetime",
            direction="backward",
            tolerance=pd.Timedelta(days=max_signal_age_days),
        ).set_index("index")
        matched = attached["available_datetime"].notna()
        if not matched.any():
            continue
        matched_index = attached.index[matched]
        result.loc[matched_index, "cot_available_datetime"] = attached.loc[matched, "available_datetime"]
        result.loc[matched_index, "cot_report_date"] = attached.loc[matched, "report_date"]
        result.loc[matched_index, "cot_source_name"] = attached.loc[matched, "source_name"].fillna("")
        result.loc[matched_index, "cot_cftc_market_name"] = attached.loc[matched, "cftc_market_name"].fillna("")
        result.loc[matched_index, "cot_mapping_type"] = attached.loc[matched, "mapping_type"].fillna("")
        result.loc[matched_index, "cot_mapping_confidence"] = attached.loc[matched, "mapping_confidence"]
        result.loc[matched_index, "cot_producer_net_oi"] = attached.loc[matched, "producer_net_oi"]
        result.loc[matched_index, "cot_producer_net_z"] = attached.loc[matched, "producer_net_z"]
        result.loc[matched_index, "cot_managed_money_net_oi"] = attached.loc[matched, "managed_money_net_oi"]
        result.loc[matched_index, "cot_managed_money_flow_oi"] = attached.loc[matched, "managed_money_flow_oi"]
        result.loc[matched_index, "cot_managed_money_net_z"] = attached.loc[matched, "managed_money_net_z"]
        result.loc[matched_index, "cot_managed_money_flow_z"] = attached.loc[matched, "managed_money_flow_z"]
        result.loc[matched_index, "cot_directional_component"] = attached.loc[matched, "cot_directional_component"]
        result.loc[matched_index, "cot_external_quality_score"] = attached.loc[matched, "cot_external_quality_score"]
        result.loc[matched_index, "cot_signal_state"] = attached.loc[matched, "cot_signal_state"].fillna("cot_missing")
        result.loc[matched_index, "cot_signal_age_days"] = (
            attached.loc[matched, "entry_datetime"] - attached.loc[matched, "available_datetime"]
        ).dt.total_seconds() / 86400.0
        result.loc[matched_index, "cot_matched"] = True
    result["cot_audit_group"] = np.where(result["cot_matched"], result["cot_signal_state"], "cot_missing_or_unmapped")
    return result


def _build_condition_specs(matrix: pd.DataFrame) -> list[ConditionSpec]:
    cot_matched = matrix["cot_matched"].astype(bool)
    quality = pd.to_numeric(matrix["cot_external_quality_score"], errors="coerce")
    supportive = quality.ge(0.25)
    headwind = quality.le(-0.25)
    strong_support = quality.ge(0.50)
    direct_mapping = matrix["cot_mapping_type"].astype(str).eq("direct_global_proxy") & cot_matched
    supportive_direct = supportive & direct_mapping
    matrix["cot_supportive"] = supportive
    matrix["cot_headwind"] = headwind
    matrix["cot_strong_support"] = strong_support
    matrix["cot_direct_mapping"] = direct_mapping
    matrix["cot_supportive_direct"] = supportive_direct
    return [
        ConditionSpec("cot_matched", "COT 在 45 天内点时化命中；覆盖基线", "cftc_cot", False, cot_matched),
        ConditionSpec("cot_supportive", "COT managed-money 方向一致分数 >= 0.25", "cftc_cot", True, supportive),
        ConditionSpec("cot_strong_support", "COT managed-money 方向一致分数 >= 0.50", "cftc_cot", True, strong_support),
        ConditionSpec("cot_direct_mapping", "仅直接/较强跨市场映射品种", "cftc_cot", True, direct_mapping),
        ConditionSpec("cot_supportive_direct", "COT supportive 且 direct mapping", "cftc_cot", True, supportive_direct),
        ConditionSpec("cot_headwind", "COT managed-money 方向一致分数 <= -0.25；只读风险提示", "cftc_cot", False, headwind),
    ]


def _feature_coverage(matrix: pd.DataFrame) -> pd.DataFrame:
    rows = []
    columns = [
        "cot_matched",
        "cot_available_datetime",
        "cot_external_quality_score",
        "cot_supportive",
        "cot_strong_support",
        "cot_direct_mapping",
        "cot_supportive_direct",
        "cot_headwind",
    ]
    for column in columns:
        if column not in matrix.columns:
            rows.append({"feature": column, "present": False, "non_null_count": 0, "active_count": 0, "coverage_pct": 0.0})
            continue
        values = matrix[column]
        non_null = int(values.notna().sum())
        if pd.api.types.is_bool_dtype(values):
            active = int(values.fillna(False).sum())
        else:
            active = non_null
        rows.append(
            {
                "feature": column,
                "present": True,
                "non_null_count": non_null,
                "active_count": active,
                "coverage_pct": float(active / len(matrix) * 100.0) if len(matrix) else 0.0,
            }
        )
    return pd.DataFrame(rows)


def _product_summary(matrix: pd.DataFrame) -> pd.DataFrame:
    if matrix.empty:
        return pd.DataFrame()
    grouped = (
        matrix.groupby("product_vt_symbol", dropna=False)
        .agg(
            entry_count=("realized_pnl", "size"),
            matched_count=("cot_matched", "sum"),
            supportive_count=("cot_supportive", "sum"),
            headwind_count=("cot_headwind", "sum"),
            pnl_sum=("realized_pnl", "sum"),
            pnl_mean=("realized_pnl", "mean"),
            win_rate_pct=("realized_pnl", lambda values: float((pd.to_numeric(values, errors="coerce").fillna(0.0) > 0).mean() * 100.0)),
        )
        .reset_index()
    )
    grouped["matched_pct"] = grouped["matched_count"] / grouped["entry_count"] * 100.0
    grouped["supportive_pct"] = grouped["supportive_count"] / grouped["entry_count"] * 100.0
    return grouped.sort_values(["matched_pct", "entry_count"], ascending=[True, False]).reset_index(drop=True)


def _state_summary(matrix: pd.DataFrame) -> pd.DataFrame:
    if matrix.empty:
        return pd.DataFrame()
    grouped = (
        matrix.groupby("cot_audit_group", dropna=False)
        .agg(
            entry_count=("realized_pnl", "size"),
            product_count=("product_vt_symbol", "nunique"),
            year_count=("entry_year", "nunique"),
            pnl_sum=("realized_pnl", "sum"),
            pnl_mean=("realized_pnl", "mean"),
            win_count=("winner", "sum"),
            big_winner_count=("big_winner", "sum"),
            min_pnl=("realized_pnl", "min"),
            max_pnl=("realized_pnl", "max"),
        )
        .reset_index()
    )
    grouped["win_rate_pct"] = grouped["win_count"] / grouped["entry_count"] * 100.0
    grouped["big_winner_rate_pct"] = grouped["big_winner_count"] / grouped["entry_count"] * 100.0
    grouped["pnl_sign_conflict"] = (grouped["min_pnl"].lt(0) & grouped["max_pnl"].gt(0)).astype(int)
    order = pd.CategoricalDtype(["cot_headwind", "cot_neutral", "cot_supportive", "cot_missing_or_unmapped"], ordered=True)
    grouped["cot_audit_group"] = grouped["cot_audit_group"].astype(order)
    return grouped.sort_values("cot_audit_group").reset_index(drop=True)


def _decision(matrix: pd.DataFrame, condition_summary: pd.DataFrame) -> dict[str, Any]:
    stable = condition_summary[condition_summary["stable_oos_candidate"].astype(bool)].copy()
    matched_count = int(matrix["cot_matched"].sum()) if "cot_matched" in matrix.columns else 0
    matched_rate = _safe_div(matched_count, len(matrix))
    supportive_count = int(matrix["cot_supportive"].sum()) if "cot_supportive" in matrix.columns else 0
    if not stable.empty and matched_rate >= 0.60:
        decision = "stage048_cftc_cot_candidate_requires_proxy_engine"
        next_stage = "freeze_one_cot_condition_proxy_engine_before_ab"
    else:
        decision = "stage048_cftc_cot_low_coverage_no_stable_oos_keep_readonly"
        next_stage = "stop_cot_rule_search_turn_to_domestic_pit_sources"
    return {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "line_id": LINE_ID,
        "decision": decision,
        "next_stage": next_stage,
        "entry_count": int(len(matrix)),
        "cot_matched_count": matched_count,
        "cot_matched_rate": matched_rate,
        "cot_supportive_count": supportive_count,
        "stable_conditions": stable["condition"].head(10).tolist(),
        "strategy_changed": False,
        "true_engine": False,
        "ab_triggered": False,
        "ctp_connected": False,
        "order_api_called": False,
        "objective_completion_proven": False,
    }


def _write_report(
    *,
    source_summary: pd.DataFrame,
    feature_coverage: pd.DataFrame,
    condition_summary: pd.DataFrame,
    product_summary: pd.DataFrame,
    state_summary: pd.DataFrame,
    decision: dict[str, Any],
    stage_record_path: Path,
) -> None:
    report = f"""# Stage048 - CFTC COT 跨市场映射资格审计

- 记录时间：`{datetime.now().strftime('%Y-%m-%dT%H:%M')}`
- line_id：`{LINE_ID}`
- model_tag：`{MODEL_TAG}`
- 决策：`{decision['decision']}`

## 外部调研与判断

- CFTC COT 是官方周频持仓报告，能提供交易商类别和 open interest 的公开背景，但报告日和发布时间有天然滞后。
- GitHub `cot_reports` 这类库说明该数据适合标准化下载和研究，但不能解决中国商品期货映射问题。
- 旧线 Stage014/Stage256 已显示 COT 在第78/旧 C9 上样本外排序失败；本阶段只在重建线复验，不把它当策略优化参数。

## 口径

- COT 数据：`{START_YEAR}` 至 `{END_YEAR}` 本地 `external_cftc_cot_cache/fut_disagg_txt_*.zip`。
- 映射：沿用旧线冻结映射 `CF/OI/lh/lc/au/cu/fu/hc/rb`，不根据本次结果改品种。
- 可用时间：报告日后第 4 天 08:00 中国时间；只允许 `available_datetime <= entry_datetime`。
- 匹配窗口：最近 `{MAX_SIGNAL_AGE_DAYS}` 天内一条 COT 信号。
- 公式：`0.35 * managed_money_net_z + 0.65 * managed_money_flow_z`，`{ROLLING_WEEKS}` 周滚动、最低 `{MIN_ROLLING_WEEKS}` 周历史。
- 本阶段只读审计；不改官方配置、不运行 true engine、不连接 CTP/SimNow、不调用 order API。

## 覆盖

{_md_table(feature_coverage)}

## COT Source Summary

{_md_table(source_summary)}

## 状态摘要

{_md_table(state_summary)}

## 条件 OOS 摘要

{_md_table(condition_summary, max_rows=20)}

## 覆盖薄弱产品

{_md_table(product_summary.head(25))}

## 判断

- COT 命中：`{decision['cot_matched_count']}/{decision['entry_count']}`，命中率 `{decision['cot_matched_rate']:.4%}`。
- supportive 样本：`{decision['cot_supportive_count']}`。
- 稳定 OOS 候选：`{decision['stable_conditions']}`。
- 若没有稳定 OOS 候选或覆盖低于 60%，COT 只能保留为外盘温度背景，不能进入 AI 选品、开仓过滤或加减仓。

## 输出

- signals：`{SIGNALS_PATH}`
- source_summary：`{SOURCE_SUMMARY_PATH}`
- joined：`{JOINED_PATH}`
- condition_summary：`{CONDITION_SUMMARY_PATH}`
- feature_coverage：`{FEATURE_COVERAGE_PATH}`
- product_summary：`{PRODUCT_SUMMARY_PATH}`
- state_summary：`{STATE_SUMMARY_PATH}`
- decision：`{DECISION_PATH}`
- report：`{REPORT_PATH}`
- stage_record：`{stage_record_path}`

## 反思

- 运行前过拟合反思：否。使用旧线冻结映射、窗口、阈值和发布滞后，只做复验。
- 运行后过拟合反思：否。无论结果好坏，本阶段不调整 COT 映射、窗口、权重、阈值或品种。
- 运行前继续价值反思：有。COT 是仓库里已有的官方外生源，必须在重建线明确排除或确认。
- 运行后继续价值反思：`{decision['next_stage']}`。
"""
    REPORT_PATH.write_text(report, encoding="utf-8")
    stage_record_path.write_text(report, encoding="utf-8")


def run() -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    STAGES_DIR.mkdir(parents=True, exist_ok=True)

    raw = load_cftc_raw()
    features = build_cot_feature_table(raw)
    signals, source_summary = build_cot_signals(features)

    matrix = pd.read_csv(STAGE038_FEATURE_MATRIX_PATH, encoding="utf-8-sig")
    matrix = attach_lagged_cot_features(matrix, signals)
    conditions = _build_condition_specs(matrix)
    splits = build_purged_time_splits(matrix, date_column="entry_date", n_splits=N_SPLITS, embargo_days=EMBARGO_DAYS)
    condition_summary = summarize_condition_oos(matrix, splits, conditions)
    feature_coverage = _feature_coverage(matrix)
    product_summary = _product_summary(matrix)
    state_summary = _state_summary(matrix)
    decision = _decision(matrix, condition_summary)

    signals.to_csv(SIGNALS_PATH, index=False, encoding="utf-8-sig")
    source_summary.to_csv(SOURCE_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    matrix.to_csv(JOINED_PATH, index=False, encoding="utf-8-sig")
    condition_summary.to_csv(CONDITION_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    feature_coverage.to_csv(FEATURE_COVERAGE_PATH, index=False, encoding="utf-8-sig")
    product_summary.to_csv(PRODUCT_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    state_summary.to_csv(STATE_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    stage_record_path = STAGES_DIR / f"{datetime.now().strftime('%Y%m%d_%H%M')}_stage048_cftc_cot_mapping_audit.md"
    _write_report(
        source_summary=source_summary,
        feature_coverage=feature_coverage,
        condition_summary=condition_summary,
        product_summary=product_summary,
        state_summary=state_summary,
        decision=decision,
        stage_record_path=stage_record_path,
    )
    decision["stage_record_path"] = str(stage_record_path)
    return decision


if __name__ == "__main__":
    print(json.dumps(_json_safe(run()), ensure_ascii=False, indent=2))
