from __future__ import annotations

from datetime import datetime
import json
import math
from pathlib import Path
import re
import sqlite3
from typing import Any
import warnings

import numpy as np
import pandas as pd

from stage038_candidate_pit_feature_matrix_audit import (
    ConditionSpec,
    build_purged_time_splits,
    summarize_condition_oos,
)
from stage049_contract_oi_migration_audit import (
    DEFAULT_DB_PATH,
    OBJECTIVE_ENTRY_END,
    OBJECTIVE_ENTRY_START,
    OBJECTIVE_PRODUCTS,
    SOURCE_START,
    _normalise_contract_vt,
    _product_key,
    contract_product_vt_symbol,
)


LINE_ID = "futures_trend_rebuilt_c9_15w_optimization"
STAGE = "Stage073"
MODEL_TAG = "stage073_term_structure_pit_audit_v1"
STAGE_SLUG = "stage073_term_structure_pit_audit"
OUTPUT_PREFIX = "rebuilt_c9_stage073_term_structure_pit_audit"

MAX_FEATURE_AGE_DAYS = 10
N_SPLITS = 4
EMBARGO_DAYS = 20
MIN_PERCENTILE_HISTORY = 60

TOOLS_DIR = Path(__file__).resolve().parent
LINE_DIR = TOOLS_DIR.parent
REPO_ROOT = LINE_DIR.parents[2]
OUTPUT_DIR = LINE_DIR / "outputs" / STAGE_SLUG
STAGES_DIR = LINE_DIR / "stages"

STAGE038_OUTPUT_DIR = LINE_DIR / "outputs" / "stage038_candidate_pit_feature_matrix_audit"
STAGE038_PREFIX = "rebuilt_c9_stage038_candidate_pit_feature_matrix_audit"
STAGE038_TAG = "stage038_candidate_pit_feature_matrix_audit_v1"
STAGE038_FEATURE_MATRIX_PATH = STAGE038_OUTPUT_DIR / f"{STAGE038_PREFIX}_feature_matrix_{STAGE038_TAG}.csv"

SNAPSHOTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_snapshots_{MODEL_TAG}.csv"
JOINED_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_joined_feature_matrix_{MODEL_TAG}.csv"
CONDITION_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_condition_oos_summary_{MODEL_TAG}.csv"
FEATURE_COVERAGE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_feature_coverage_{MODEL_TAG}.csv"
PRODUCT_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_summary_{MODEL_TAG}.csv"
SOURCE_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_source_summary_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


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
        return None if math.isnan(number) or math.isinf(number) else number
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


def _read_csv(path: Path, **kwargs: Any) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path, encoding="utf-8-sig", **kwargs)


def _num(frame: pd.DataFrame, column: str, default: float = np.nan) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype="float64")
    return pd.to_numeric(frame[column], errors="coerce")


def _to_bool(values: pd.Series | Any, index: pd.Index | None = None) -> pd.Series:
    if isinstance(values, pd.Series):
        series = values.copy()
    else:
        series = pd.Series(values, index=index)
    if series.empty:
        return series.astype(bool)
    if pd.api.types.is_bool_dtype(series):
        return series.fillna(False)
    if pd.api.types.is_numeric_dtype(series):
        return pd.to_numeric(series, errors="coerce").fillna(0).ne(0)
    text = series.fillna("").astype(str).str.strip().str.lower()
    return text.isin({"1", "1.0", "true", "yes", "y", "pass", "passed", "opened"})


def _safe_div(num: float, den: float) -> float:
    return float(num) / float(den) if abs(float(den)) > 1e-12 else np.nan


def infer_contract_maturity(symbol: Any, exchange: Any, feature_date: Any) -> pd.Timestamp | pd.NaT:
    """Infer contract delivery month from Chinese futures contract code.

    CZCE old-style contracts often use 3 digits, e.g. MA905 means 2019-05 near
    a 2019 feature date, while FG101 means 2021-01 near a 2020 feature date.
    The date argument is only used to choose the plausible decade.
    """
    del exchange
    text = str(symbol).strip()
    match = re.search(r"(\d+)", text)
    if not match:
        return pd.NaT
    digits = match.group(1)
    feature_ts = pd.Timestamp(feature_date).normalize()
    if pd.isna(feature_ts):
        return pd.NaT

    if len(digits) >= 4:
        code = digits[-4:]
        year = 2000 + int(code[:2])
        month = int(code[2:])
    elif len(digits) == 3:
        year_digit = int(digits[0])
        month = int(digits[1:])
        candidates = [2010 + year_digit, 2020 + year_digit, 2030 + year_digit]
        year = min(candidates, key=lambda item: (abs(item - feature_ts.year), item < feature_ts.year))
    else:
        return pd.NaT

    if month < 1 or month > 12:
        return pd.NaT
    return pd.Timestamp(year=year, month=month, day=1)


def _month_gap(left: pd.Timestamp, right: pd.Timestamp) -> int:
    return int((right.year - left.year) * 12 + right.month - left.month)


def _expanding_percentile(values: pd.Series, min_history: int = MIN_PERCENTILE_HISTORY) -> pd.Series:
    numeric = pd.to_numeric(values, errors="coerce").astype(float)
    output = pd.Series(np.nan, index=numeric.index, dtype="float64")
    history: list[float] = []
    for idx, value in numeric.items():
        if pd.notna(value) and len(history) >= min_history:
            hist = np.asarray(history, dtype="float64")
            output.loc[idx] = float((np.sum(hist < value) + 0.5 * np.sum(hist == value)) / len(hist))
        if pd.notna(value):
            history.append(float(value))
    return output


def load_contract_daily_bars_with_close(
    db_path: Path = DEFAULT_DB_PATH,
    *,
    start: pd.Timestamp = SOURCE_START,
    end: pd.Timestamp = OBJECTIVE_ENTRY_END,
    product_keys: set[str] | None = None,
) -> pd.DataFrame:
    if not db_path.exists():
        raise FileNotFoundError(db_path)
    query = """
        SELECT symbol, exchange, datetime, open_interest, close_price
        FROM dbbardata
        WHERE interval = 'd'
          AND datetime >= ?
          AND datetime <= ?
    """
    with sqlite3.connect(db_path) as connection:
        frame = pd.read_sql_query(
            query,
            connection,
            params=(
                start.strftime("%Y-%m-%d 00:00:00"),
                end.strftime("%Y-%m-%d 23:59:59"),
            ),
        )
    if frame.empty:
        return frame
    frame["feature_date"] = pd.to_datetime(frame["datetime"], errors="coerce").dt.normalize()
    frame["open_interest"] = pd.to_numeric(frame["open_interest"], errors="coerce")
    frame["close_price"] = pd.to_numeric(frame["close_price"], errors="coerce")
    frame["contract_vt_symbol"] = [
        _normalise_contract_vt(symbol, exchange) for symbol, exchange in zip(frame["symbol"], frame["exchange"])
    ]
    frame["product_vt_symbol"] = frame["contract_vt_symbol"].map(contract_product_vt_symbol)
    frame["product_key"] = frame["product_vt_symbol"].map(_product_key)
    frame["contract_maturity"] = [
        infer_contract_maturity(symbol, exchange, feature_date)
        for symbol, exchange, feature_date in zip(frame["symbol"], frame["exchange"], frame["feature_date"])
    ]
    frame = frame[frame["symbol"].astype(str).str.contains(r"\d", regex=True)].copy()
    frame = frame[frame["open_interest"].notna() & frame["open_interest"].gt(0)].copy()
    frame = frame[frame["close_price"].notna() & frame["close_price"].gt(0)].copy()
    frame = frame[frame["contract_maturity"].notna()].copy()
    if product_keys is not None:
        frame = frame[frame["product_key"].isin(product_keys)].copy()
    return frame.sort_values(["product_key", "feature_date", "contract_maturity", "contract_vt_symbol"]).reset_index(drop=True)


def build_term_structure_snapshots(bars: pd.DataFrame) -> pd.DataFrame:
    frame = bars.copy()
    if frame.empty:
        return pd.DataFrame()
    if "feature_date" not in frame.columns:
        frame["feature_date"] = pd.to_datetime(frame["datetime"], errors="coerce").dt.normalize()
    frame["open_interest"] = pd.to_numeric(frame["open_interest"], errors="coerce")
    frame["close_price"] = pd.to_numeric(frame["close_price"], errors="coerce")
    if "contract_vt_symbol" not in frame.columns:
        frame["contract_vt_symbol"] = [
            _normalise_contract_vt(symbol, exchange) for symbol, exchange in zip(frame["symbol"], frame["exchange"])
        ]
    if "product_vt_symbol" not in frame.columns:
        frame["product_vt_symbol"] = frame["contract_vt_symbol"].map(contract_product_vt_symbol)
    if "product_key" not in frame.columns:
        frame["product_key"] = frame["product_vt_symbol"].map(_product_key)
    if "contract_maturity" not in frame.columns:
        frame["contract_maturity"] = [
            infer_contract_maturity(symbol, exchange, feature_date)
            for symbol, exchange, feature_date in zip(frame["symbol"], frame["exchange"], frame["feature_date"])
        ]
    frame = frame[
        frame["feature_date"].notna()
        & frame["contract_maturity"].notna()
        & frame["open_interest"].gt(0)
        & frame["close_price"].gt(0)
    ].copy()

    rows: list[dict[str, Any]] = []
    for (product_key, feature_date), group in frame.groupby(["product_key", "feature_date"], sort=True):
        product_group = group.sort_values(["contract_maturity", "contract_vt_symbol"]).drop_duplicates(
            "contract_vt_symbol", keep="last"
        )
        if len(product_group) < 2:
            continue
        front = product_group.iloc[0]
        next_contract = product_group.iloc[1]
        front_close = float(front["close_price"])
        next_close = float(next_contract["close_price"])
        total_oi = float(product_group["open_interest"].sum())
        front_maturity = pd.Timestamp(front["contract_maturity"])
        next_maturity = pd.Timestamp(next_contract["contract_maturity"])
        backwardation_pct = (front_close / next_close - 1.0) * 100.0
        rows.append(
            {
                "product_vt_symbol": front["product_vt_symbol"],
                "product_key": product_key,
                "term_structure_feature_date": pd.Timestamp(feature_date),
                "term_structure_asof_date": pd.Timestamp(feature_date) + pd.Timedelta(days=1),
                "front_contract_vt_symbol": front["contract_vt_symbol"],
                "next_contract_vt_symbol": next_contract["contract_vt_symbol"],
                "front_contract_maturity": front_maturity,
                "next_contract_maturity": next_maturity,
                "term_structure_month_gap": _month_gap(front_maturity, next_maturity),
                "front_close": front_close,
                "next_close": next_close,
                "front_open_interest": float(front["open_interest"]),
                "next_open_interest": float(next_contract["open_interest"]),
                "term_structure_total_open_interest": total_oi,
                "front_open_interest_share": _safe_div(float(front["open_interest"]), total_oi),
                "next_open_interest_share": _safe_div(float(next_contract["open_interest"]), total_oi),
                "term_structure_backwardation_pct": backwardation_pct,
                "term_structure_contract_count": int(len(product_group)),
            }
        )
    snapshots = pd.DataFrame(rows)
    if snapshots.empty:
        return snapshots
    snapshots = snapshots.sort_values(["product_key", "term_structure_feature_date"]).reset_index(drop=True)
    pctile_parts: list[pd.DataFrame] = []
    for _, group in snapshots.groupby("product_key", sort=False):
        part = group.copy()
        part["term_structure_backwardation_prior_pctile"] = _expanding_percentile(
            part["term_structure_backwardation_pct"], min_history=MIN_PERCENTILE_HISTORY
        )
        pctile_parts.append(part)
    return pd.concat(pctile_parts, ignore_index=True).sort_values(
        ["product_key", "term_structure_feature_date"]
    ).reset_index(drop=True)


def attach_term_structure_features(
    entries: pd.DataFrame,
    snapshots: pd.DataFrame,
    *,
    max_feature_age_days: int = MAX_FEATURE_AGE_DAYS,
) -> pd.DataFrame:
    result = entries.copy()
    if result.empty:
        return result
    result["_stage073_row_id"] = np.arange(len(result))
    result["entry_date"] = pd.to_datetime(result["entry_date"], errors="coerce").dt.normalize()
    if "product_vt_symbol" not in result.columns:
        if "vt_symbol" not in result.columns:
            raise KeyError("entries must contain product_vt_symbol or vt_symbol")
        result["product_vt_symbol"] = result["vt_symbol"].map(contract_product_vt_symbol)
    result["product_key"] = result["product_vt_symbol"].map(_product_key)

    feature_columns = [
        "term_structure_feature_date",
        "term_structure_asof_date",
        "front_contract_vt_symbol",
        "next_contract_vt_symbol",
        "front_contract_maturity",
        "next_contract_maturity",
        "term_structure_month_gap",
        "front_close",
        "next_close",
        "front_open_interest",
        "next_open_interest",
        "term_structure_total_open_interest",
        "front_open_interest_share",
        "next_open_interest_share",
        "term_structure_backwardation_pct",
        "term_structure_contract_count",
        "term_structure_backwardation_prior_pctile",
    ]
    for column in feature_columns:
        if column not in result.columns:
            result[column] = np.nan
    result["term_structure_matched"] = False

    if snapshots.empty:
        return result.drop(columns=["_stage073_row_id"])

    snap = snapshots.copy()
    snap["term_structure_asof_date"] = pd.to_datetime(snap["term_structure_asof_date"], errors="coerce").dt.normalize()
    snap["term_structure_feature_date"] = pd.to_datetime(
        snap["term_structure_feature_date"], errors="coerce"
    ).dt.normalize()
    snap["product_key"] = snap["product_vt_symbol"].map(_product_key)
    snap = snap.dropna(subset=["product_key", "term_structure_asof_date"]).sort_values(
        ["product_key", "term_structure_asof_date"]
    )

    attached_parts: list[pd.DataFrame] = []
    for product_key, left_group in result.groupby("product_key", sort=False):
        right_group = snap[snap["product_key"].eq(product_key)].copy()
        left_sorted = left_group.sort_values("entry_date")
        if right_group.empty:
            attached_parts.append(left_group)
            continue
        merged = pd.merge_asof(
            left_sorted,
            right_group[["product_key", *feature_columns]].sort_values("term_structure_asof_date"),
            left_on="entry_date",
            right_on="term_structure_asof_date",
            direction="backward",
            suffixes=("", "_stage073_feature"),
        )
        for column in feature_columns:
            feature_column = f"{column}_stage073_feature"
            if feature_column in merged.columns:
                merged[column] = merged[feature_column]
                merged = merged.drop(columns=[feature_column])
        attached_parts.append(merged)

    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            category=FutureWarning,
            message="The behavior of DataFrame concatenation with empty or all-NA entries is deprecated.*",
        )
        attached = pd.concat(attached_parts, ignore_index=True).sort_values("_stage073_row_id")
    age = (
        pd.to_datetime(attached["entry_date"], errors="coerce").dt.normalize()
        - pd.to_datetime(attached["term_structure_asof_date"], errors="coerce").dt.normalize()
    ).dt.days
    attached["term_structure_feature_age_days"] = age
    matched = age.notna() & age.ge(0) & age.le(max_feature_age_days)
    attached["term_structure_matched"] = matched.fillna(False).astype(bool)

    spread = pd.to_numeric(attached["term_structure_backwardation_pct"], errors="coerce")
    pctile = pd.to_numeric(attached["term_structure_backwardation_prior_pctile"], errors="coerce")
    direction = attached.get("direction", "").fillna("").astype(str).str.lower()
    long_aligned = direction.eq("long") & spread.gt(0)
    short_aligned = direction.eq("short") & spread.lt(0)
    long_extreme = direction.eq("long") & pctile.ge(0.8)
    short_extreme = direction.eq("short") & pctile.le(0.2)
    attached["term_structure_directional_carry_aligned"] = (
        attached["term_structure_matched"] & (long_aligned | short_aligned)
    )
    attached["term_structure_directional_carry_misaligned"] = (
        attached["term_structure_matched"] & (direction.isin(["long", "short"]) & ~(long_aligned | short_aligned))
    )
    attached["term_structure_directional_carry_extreme_aligned"] = (
        attached["term_structure_matched"] & (long_extreme | short_extreme)
    )
    stale_mask = ~attached["term_structure_matched"]
    stale_clear_columns = [
        "term_structure_feature_date",
        "term_structure_asof_date",
        "term_structure_feature_age_days",
        "term_structure_backwardation_pct",
        "term_structure_backwardation_prior_pctile",
    ]
    for column in stale_clear_columns:
        attached.loc[stale_mask, column] = np.nan
    return attached.drop(columns=["_stage073_row_id"])


def build_term_structure_conditions(matrix: pd.DataFrame) -> list[ConditionSpec]:
    matched = _to_bool(matrix.get("term_structure_matched", False), index=matrix.index)
    aligned = _to_bool(matrix.get("term_structure_directional_carry_aligned", False), index=matrix.index)
    misaligned = _to_bool(matrix.get("term_structure_directional_carry_misaligned", False), index=matrix.index)
    extreme_aligned = _to_bool(
        matrix.get("term_structure_directional_carry_extreme_aligned", False), index=matrix.index
    )
    spread = _num(matrix, "term_structure_backwardation_pct")
    pctile = _num(matrix, "term_structure_backwardation_prior_pctile")
    ai_rank_1_9 = _to_bool(matrix.get("ai_rank_1_9", False), index=matrix.index)
    oi_confirmed = _to_bool(matrix.get("oi_confirmed", False), index=matrix.index)
    account_clean = _to_bool(matrix.get("account_clean", False), index=matrix.index)
    full_market_top8 = _to_bool(matrix.get("full_market_ai_top8", False), index=matrix.index)
    selected_volume_gt1 = _to_bool(matrix.get("selected_volume_gt1", False), index=matrix.index)

    return [
        ConditionSpec(
            "term_structure_matched",
            "逐合约 front/next 期限结构特征可 T+1 匹配",
            "term_structure",
            False,
            matched,
        ),
        ConditionSpec(
            "term_backwardation_positive",
            "front/next backwardation > 0",
            "term_structure",
            True,
            matched & spread.gt(0),
        ),
        ConditionSpec(
            "term_contango_negative",
            "front/next backwardation < 0，即 contango",
            "term_structure",
            True,
            matched & spread.lt(0),
        ),
        ConditionSpec(
            "directional_carry_aligned",
            "long 配 backwardation 或 short 配 contango",
            "term_structure",
            True,
            aligned,
        ),
        ConditionSpec(
            "directional_carry_misaligned",
            "方向与期限结构 carry 逆风",
            "term_structure",
            True,
            misaligned,
        ),
        ConditionSpec(
            "directional_carry_extreme_aligned",
            "方向顺风且 product 内 prior percentile 达极端",
            "term_structure",
            True,
            extreme_aligned,
        ),
        ConditionSpec(
            "term_backwardation_prior_p80",
            "backwardation prior percentile >= 0.8",
            "term_structure",
            True,
            matched & pctile.ge(0.8),
        ),
        ConditionSpec(
            "term_backwardation_prior_p20",
            "backwardation prior percentile <= 0.2",
            "term_structure",
            True,
            matched & pctile.le(0.2),
        ),
        ConditionSpec(
            "ai_rank_1_9_and_directional_carry_aligned",
            "Stage182 AI rank 1-9 且期限结构顺风",
            "ai_term_structure",
            True,
            ai_rank_1_9 & aligned,
        ),
        ConditionSpec(
            "ai_oi_account_and_directional_carry_aligned",
            "AI rank 1-9 + OI确认 + 账户干净 + 期限结构顺风",
            "ai_oi_account_term_structure",
            True,
            ai_rank_1_9 & oi_confirmed & account_clean & aligned,
        ),
        ConditionSpec(
            "full_market_ai_top8_and_directional_carry_aligned",
            "full-market AI top8 且期限结构顺风",
            "full_market_term_structure",
            True,
            full_market_top8 & aligned,
        ),
        ConditionSpec(
            "volume_gt1_and_directional_carry_aligned",
            "当前真实手数 > 1 且期限结构顺风",
            "current_budget_term_structure",
            True,
            selected_volume_gt1 & aligned,
        ),
    ]


def feature_coverage(matrix: pd.DataFrame, snapshots: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    columns = [
        "term_structure_matched",
        "term_structure_backwardation_pct",
        "term_structure_backwardation_prior_pctile",
        "term_structure_directional_carry_aligned",
        "term_structure_directional_carry_extreme_aligned",
    ]
    for column in columns:
        values = matrix[column] if column in matrix.columns else pd.Series(dtype=float)
        if values.empty:
            non_null = 0
            active = 0
        elif pd.api.types.is_bool_dtype(values):
            non_null = int(values.notna().sum())
            active = int(values.fillna(False).sum())
        else:
            non_null = int(values.notna().sum())
            active = non_null
        rows.append(
            {
                "feature": column,
                "present": column in matrix.columns,
                "non_null_count": non_null,
                "active_count": active,
                "coverage_pct": float(non_null / len(matrix) * 100.0) if len(matrix) else 0.0,
            }
        )
    product_snapshot = (
        snapshots.groupby("product_vt_symbol", dropna=False)
        .agg(
            snapshot_count=("term_structure_feature_date", "size"),
            first_snapshot=("term_structure_feature_date", "min"),
            last_snapshot=("term_structure_feature_date", "max"),
            median_contract_count=("term_structure_contract_count", "median"),
            pctile_ready_count=("term_structure_backwardation_prior_pctile", lambda s: int(s.notna().sum())),
        )
        .reset_index()
        if not snapshots.empty
        else pd.DataFrame()
    )
    rows.append(
        {
            "feature": "snapshot_product_count",
            "present": True,
            "non_null_count": int(product_snapshot["product_vt_symbol"].nunique()) if not product_snapshot.empty else 0,
            "active_count": int(product_snapshot["product_vt_symbol"].nunique()) if not product_snapshot.empty else 0,
            "coverage_pct": np.nan,
        }
    )
    return pd.DataFrame(rows)


def product_summary(matrix: pd.DataFrame) -> pd.DataFrame:
    if matrix.empty:
        return pd.DataFrame()
    frame = matrix.copy()
    frame["realized_pnl"] = _num(frame, "realized_pnl", 0.0).fillna(0.0)
    frame["term_structure_matched"] = _to_bool(frame.get("term_structure_matched", False), index=frame.index)
    frame["term_structure_directional_carry_aligned"] = _to_bool(
        frame.get("term_structure_directional_carry_aligned", False), index=frame.index
    )
    grouped = frame.groupby("product_vt_symbol", dropna=False)
    rows: list[dict[str, Any]] = []
    for product, group in grouped:
        matched = group[group["term_structure_matched"]]
        aligned = group[group["term_structure_directional_carry_aligned"]]
        rows.append(
            {
                "product_vt_symbol": product,
                "row_count": int(len(group)),
                "matched_count": int(len(matched)),
                "matched_coverage_pct": float(len(matched) / len(group) * 100.0) if len(group) else 0.0,
                "aligned_count": int(len(aligned)),
                "aligned_coverage_pct": float(len(aligned) / len(group) * 100.0) if len(group) else 0.0,
                "base_pnl": float(group["realized_pnl"].sum()),
                "matched_pnl": float(matched["realized_pnl"].sum()) if len(matched) else 0.0,
                "aligned_pnl": float(aligned["realized_pnl"].sum()) if len(aligned) else 0.0,
                "aligned_mean_pnl": float(aligned["realized_pnl"].mean()) if len(aligned) else np.nan,
                "base_mean_pnl": float(group["realized_pnl"].mean()) if len(group) else np.nan,
            }
        )
    return pd.DataFrame(rows).sort_values(["aligned_mean_pnl", "aligned_count"], ascending=[False, False]).reset_index(
        drop=True
    )


def source_summary(matrix: pd.DataFrame) -> pd.DataFrame:
    if matrix.empty or "requested_start_month" not in matrix.columns:
        return pd.DataFrame()
    frame = matrix.copy()
    frame["realized_pnl"] = _num(frame, "realized_pnl", 0.0).fillna(0.0)
    frame["term_structure_directional_carry_aligned"] = _to_bool(
        frame.get("term_structure_directional_carry_aligned", False), index=frame.index
    )
    rows = []
    for source, group in frame.groupby("requested_start_month", sort=True):
        aligned = group[group["term_structure_directional_carry_aligned"]]
        rows.append(
            {
                "requested_start_month": source,
                "row_count": int(len(group)),
                "aligned_count": int(len(aligned)),
                "base_pnl": float(group["realized_pnl"].sum()),
                "aligned_pnl": float(aligned["realized_pnl"].sum()) if len(aligned) else 0.0,
                "aligned_mean_pnl": float(aligned["realized_pnl"].mean()) if len(aligned) else np.nan,
            }
        )
    return pd.DataFrame(rows)


def decide(
    matrix: pd.DataFrame,
    snapshots: pd.DataFrame,
    condition_summary: pd.DataFrame,
    coverage: pd.DataFrame,
) -> dict[str, Any]:
    stable = (
        condition_summary[condition_summary["stable_oos_candidate"].astype(bool)].copy()
        if not condition_summary.empty and "stable_oos_candidate" in condition_summary.columns
        else pd.DataFrame()
    )
    matched = _to_bool(matrix.get("term_structure_matched", False), index=matrix.index)
    aligned = _to_bool(matrix.get("term_structure_directional_carry_aligned", False), index=matrix.index)
    base_pnl = float(_num(matrix, "realized_pnl", 0.0).fillna(0.0).sum()) if len(matrix) else 0.0
    aligned_pnl = float(_num(matrix.loc[aligned], "realized_pnl", 0.0).fillna(0.0).sum()) if aligned.any() else 0.0
    if stable.empty:
        decision = "stage073_term_structure_no_stable_oos_candidate_keep_readonly"
        next_stage = "继续寻找真正新PIT信息源；不要扫front/next阈值、percentile或month_gap救参"
    else:
        decision = "stage073_term_structure_has_candidate_needs_low_degree_proxy"
        next_stage = "Stage074 只冻结 top stable 条件做低自由度 proxy，不扫参"
    top_stable = stable.head(5).to_dict(orient="records") if not stable.empty else []
    return {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "decision": decision,
        "next_stage": next_stage,
        "objective_products": list(OBJECTIVE_PRODUCTS),
        "matrix_rows": int(len(matrix)),
        "snapshot_rows": int(len(snapshots)),
        "snapshot_products": int(snapshots["product_vt_symbol"].nunique()) if not snapshots.empty else 0,
        "matched_rows": int(matched.sum()),
        "matched_coverage_pct": float(matched.mean() * 100.0) if len(matched) else 0.0,
        "aligned_rows": int(aligned.sum()),
        "aligned_coverage_pct": float(aligned.mean() * 100.0) if len(aligned) else 0.0,
        "base_pnl": base_pnl,
        "aligned_pnl": aligned_pnl,
        "stable_candidate_count": int(len(stable)),
        "top_stable_candidates": top_stable,
        "coverage": coverage.to_dict(orient="records"),
        "overfit_reflection_start": "否；本阶段先验证独立PIT信息源和可见性，不围绕坏窗口调参。",
        "overfit_reflection_end": "若只拿 stable 条件做固定低自由度 proxy 才不是过拟合；若继续扫分位、月差、品种则会过拟合。",
        "continue_value_start": "有；现有内部同源特征已低覆盖或证伪，期限结构是商品期货特有的新信息维度。",
        "continue_value_end": "取决于是否出现稳定OOS候选；无稳定候选则只保留数据资产，停止救参。",
    }


def write_report(
    *,
    decision: dict[str, Any],
    condition_summary: pd.DataFrame,
    coverage: pd.DataFrame,
    products: pd.DataFrame,
    sources: pd.DataFrame,
) -> str:
    stable = condition_summary[condition_summary["stable_oos_candidate"].astype(bool)].copy() if not condition_summary.empty else pd.DataFrame()
    lines = [
        f"# {STAGE} term structure PIT audit",
        "",
        "## 结论",
        "",
        f"- 决策：`{decision['decision']}`",
        f"- 下一步：{decision['next_stage']}",
        f"- 样本行数：`{decision['matrix_rows']}`；期限结构快照：`{decision['snapshot_rows']}`；覆盖品种：`{decision['snapshot_products']}`",
        f"- 匹配覆盖：`{decision['matched_coverage_pct']:.4f}%`；方向顺风覆盖：`{decision['aligned_coverage_pct']:.4f}%`",
        f"- 全样本 PnL：`{decision['base_pnl']:.2f}`；方向顺风子样本 PnL：`{decision['aligned_pnl']:.2f}`",
        f"- 稳定 OOS 候选数：`{decision['stable_candidate_count']}`",
        "",
        "## 外部调研判断",
        "",
        "- Quantpedia、CME、Wharton carry paper 与 basis-momentum 研究都支持商品期限结构/roll yield/carry 可能含有预测信息。",
        "- 本阶段不复制外部策略，只验证本地逐合约 close/open_interest 能否在 T+1 口径构造 front/next backwardation 特征。",
        "",
        "## 过拟合与继续价值反思",
        "",
        f"- 开始是否过拟合：{decision['overfit_reflection_start']}",
        f"- 结束是否过拟合：{decision['overfit_reflection_end']}",
        f"- 开始是否值得继续：{decision['continue_value_start']}",
        f"- 结束是否值得继续：{decision['continue_value_end']}",
        "",
        "## Stable OOS 候选",
        "",
        _md_table(stable.head(20)),
        "",
        "## 条件 OOS 摘要 Top 20",
        "",
        _md_table(condition_summary.head(20)),
        "",
        "## 覆盖率",
        "",
        _md_table(coverage),
        "",
        "## 产品摘要",
        "",
        _md_table(products.head(20)),
        "",
        "## 起点摘要",
        "",
        _md_table(sources.head(20)),
        "",
        "## 输出",
        "",
        f"- snapshots：`{SNAPSHOTS_PATH}`",
        f"- joined feature matrix：`{JOINED_PATH}`",
        f"- condition summary：`{CONDITION_SUMMARY_PATH}`",
        f"- decision：`{DECISION_PATH}`",
    ]
    return "\n".join(lines) + "\n"


def write_stage_record(report: str, decision: dict[str, Any]) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    path = STAGES_DIR / f"{timestamp}_stage073_term_structure_pit_audit.md"
    body = [
        f"# {STAGE} 期限结构 PIT 审计",
        "",
        f"- 记录时间：{datetime.now().strftime('%Y-%m-%d %H:%M CST')}",
        f"- line_id：`{LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        f"- 是否重要突破版本：{'是' if decision['stable_candidate_count'] else '否'}",
        "- 新增参数：front/next 期限结构、backwardation_pct、product 内 prior percentile、directional_carry_aligned",
        "- 修改参数：无",
        "- 删除参数：无",
        "",
        report,
    ]
    path.write_text("\n".join(body), encoding="utf-8")
    return path


def main() -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    STAGES_DIR.mkdir(parents=True, exist_ok=True)
    objective_product_keys = {_product_key(item) for item in OBJECTIVE_PRODUCTS}
    matrix = _read_csv(STAGE038_FEATURE_MATRIX_PATH, parse_dates=["entry_date", "exit_date"])
    bars = load_contract_daily_bars_with_close(product_keys=objective_product_keys)
    snapshots = build_term_structure_snapshots(bars)
    joined = attach_term_structure_features(matrix, snapshots, max_feature_age_days=MAX_FEATURE_AGE_DAYS)
    splits = build_purged_time_splits(joined, date_column="entry_date", n_splits=N_SPLITS, embargo_days=EMBARGO_DAYS)
    conditions = build_term_structure_conditions(joined)
    condition_summary = summarize_condition_oos(joined, splits, conditions, min_count=60, min_test_folds=3)
    coverage = feature_coverage(joined, snapshots)
    products = product_summary(joined)
    sources = source_summary(joined)
    decision = decide(joined, snapshots, condition_summary, coverage)
    report = write_report(
        decision=decision,
        condition_summary=condition_summary,
        coverage=coverage,
        products=products,
        sources=sources,
    )
    stage_path = write_stage_record(report, decision)
    decision["stage_record_path"] = str(stage_path)

    snapshots.to_csv(SNAPSHOTS_PATH, index=False, encoding="utf-8-sig")
    joined.to_csv(JOINED_PATH, index=False, encoding="utf-8-sig")
    condition_summary.to_csv(CONDITION_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    coverage.to_csv(FEATURE_COVERAGE_PATH, index=False, encoding="utf-8-sig")
    products.to_csv(PRODUCT_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    sources.to_csv(SOURCE_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_PATH.write_text(report, encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    return decision


if __name__ == "__main__":
    main()
