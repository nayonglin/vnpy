from __future__ import annotations

from datetime import datetime
import json
import math
from pathlib import Path
import re
import sqlite3
from typing import Any

import numpy as np
import pandas as pd

from stage038_candidate_pit_feature_matrix_audit import (
    ConditionSpec,
    build_purged_time_splits,
    summarize_condition_oos,
)


LINE_ID = "futures_trend_rebuilt_c9_15w_optimization"
STAGE = "Stage049"
MODEL_TAG = "stage049_contract_oi_migration_audit_v1"
OUTPUT_PREFIX = "rebuilt_c9_stage049_contract_oi_migration_audit"

OBJECTIVE_ENTRY_START = pd.Timestamp("2020-01-01")
OBJECTIVE_ENTRY_END = pd.Timestamp("2026-06-30")
SOURCE_START = pd.Timestamp("2019-12-01")
MAX_FEATURE_AGE_DAYS = 10
N_SPLITS = 4
EMBARGO_DAYS = 20

TOOLS_DIR = Path(__file__).resolve().parent
LINE_DIR = TOOLS_DIR.parent
REPO_ROOT = LINE_DIR.parents[2]
OUTPUT_DIR = LINE_DIR / "outputs" / "stage049_contract_oi_migration_audit"
STAGES_DIR = LINE_DIR / "stages"

BACKTEST_OUTPUTS = REPO_ROOT / "examples" / "portfolio_backtesting" / "backtest_outputs"
DEFAULT_DB_PATH = REPO_ROOT / ".vntrader" / "database.db"
MAIN_MAPPING_PATH = BACKTEST_OUTPUTS / "tqsdk_all_futures_main_contract_mapping_2010_2026_04.csv"

STAGE038_OUTPUT_DIR = LINE_DIR / "outputs" / "stage038_candidate_pit_feature_matrix_audit"
STAGE038_PREFIX = "rebuilt_c9_stage038_candidate_pit_feature_matrix_audit"
STAGE038_TAG = "stage038_candidate_pit_feature_matrix_audit_v1"
STAGE038_FEATURE_MATRIX_PATH = STAGE038_OUTPUT_DIR / f"{STAGE038_PREFIX}_feature_matrix_{STAGE038_TAG}.csv"

SNAPSHOTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_contract_oi_snapshots_{MODEL_TAG}.csv"
JOINED_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_joined_feature_matrix_{MODEL_TAG}.csv"
CONDITION_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_condition_oos_summary_{MODEL_TAG}.csv"
FEATURE_COVERAGE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_feature_coverage_{MODEL_TAG}.csv"
PRODUCT_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_summary_{MODEL_TAG}.csv"
SOURCE_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_source_summary_{MODEL_TAG}.csv"
STATE_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_state_summary_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

OBJECTIVE_PRODUCTS = (
    "AP.CZCE",
    "CF.CZCE",
    "FG.CZCE",
    "MA.CZCE",
    "OI.CZCE",
    "SA.CZCE",
    "SH.CZCE",
    "SM.CZCE",
    "jd.DCE",
    "jm.DCE",
    "si.GFEX",
    "fu.SHFE",
    "rb.SHFE",
    "ru.SHFE",
    "sp.SHFE",
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


def _safe_div(num: float, den: float) -> float:
    return float(num) / float(den) if abs(float(den)) > 1e-12 else np.nan


def _read_csv(path: Path, **kwargs: Any) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path, encoding="utf-8-sig", **kwargs)


def _product_key(value: Any) -> str:
    return str(value).strip().lower()


def _contract_key(value: Any) -> str:
    return str(value).strip().lower()


def _normalise_exchange(value: Any) -> str:
    return str(value).strip().upper()


def _product_display(product: str, exchange: str) -> str:
    exchange = _normalise_exchange(exchange)
    if exchange == "CZCE":
        product = product.upper()
    else:
        product = product.lower()
    return f"{product}.{exchange}"


def contract_product_vt_symbol(vt_symbol: Any) -> str:
    """Return product vt symbol from a concrete contract vt symbol."""
    text = str(vt_symbol).strip()
    if "." not in text:
        return text
    symbol, exchange = text.split(".", 1)
    product = re.sub(r"\d+", "", symbol)
    return _product_display(product, exchange)


def _normalise_contract_vt(symbol: Any, exchange: Any | None = None) -> str:
    text = str(symbol).strip()
    if "." in text:
        contract, ex = text.split(".", 1)
        return f"{contract}.{_normalise_exchange(ex)}"
    if exchange is None:
        return text
    return f"{text}.{_normalise_exchange(exchange)}"


def _normalise_product_vt(product: Any, exchange: Any | None = None) -> str:
    text = str(product).strip()
    if "." in text:
        symbol, ex = text.split(".", 1)
        return _product_display(symbol, ex)
    if exchange is None:
        return text
    return _product_display(text, str(exchange))


def _has_contract_month(symbol: Any) -> bool:
    return bool(re.search(r"\d", str(symbol)))


def load_contract_daily_bars(
    db_path: Path = DEFAULT_DB_PATH,
    *,
    start: pd.Timestamp = SOURCE_START,
    end: pd.Timestamp = OBJECTIVE_ENTRY_END,
    product_keys: set[str] | None = None,
) -> pd.DataFrame:
    if not db_path.exists():
        raise FileNotFoundError(db_path)
    query = """
        SELECT symbol, exchange, datetime, open_interest
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
    frame["contract_vt_symbol"] = [
        _normalise_contract_vt(symbol, exchange) for symbol, exchange in zip(frame["symbol"], frame["exchange"])
    ]
    frame["product_vt_symbol"] = frame["contract_vt_symbol"].map(contract_product_vt_symbol)
    frame["product_key"] = frame["product_vt_symbol"].map(_product_key)
    frame = frame[frame["symbol"].map(_has_contract_month)].copy()
    frame = frame[frame["open_interest"].notna() & frame["open_interest"].gt(0)].copy()
    if product_keys is not None:
        frame = frame[frame["product_key"].isin(product_keys)].copy()
    return frame.sort_values(["product_key", "feature_date", "contract_vt_symbol"]).reset_index(drop=True)


def load_main_contract_mapping(
    mapping_path: Path = MAIN_MAPPING_PATH,
    *,
    start: pd.Timestamp = SOURCE_START,
    end: pd.Timestamp = OBJECTIVE_ENTRY_END,
    product_keys: set[str] | None = None,
) -> pd.DataFrame:
    raw = _read_csv(mapping_path)
    frame = raw.copy()
    frame["feature_date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    if "continuous_symbol_vt" in frame.columns:
        frame["product_vt_symbol"] = frame["continuous_symbol_vt"].map(lambda value: _normalise_product_vt(value))
    else:
        frame["product_vt_symbol"] = [
            _normalise_product_vt(product, exchange) for product, exchange in zip(frame["product"], frame["exchange"])
        ]
    frame["product_key"] = frame["product_vt_symbol"].map(_product_key)
    frame["main_contract_vt"] = frame["main_contract_vt"].fillna("").map(
        lambda value: _normalise_contract_vt(value) if str(value).strip() else ""
    )
    frame = frame[frame["feature_date"].between(start, end)].copy()
    if product_keys is not None:
        frame = frame[frame["product_key"].isin(product_keys)].copy()
    return frame[
        ["feature_date", "product_vt_symbol", "product_key", "main_contract_vt"]
    ].sort_values(["product_key", "feature_date"]).reset_index(drop=True)


def _mapping_change_table(mapping: pd.DataFrame) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    for _, group in mapping.groupby("product_key", sort=False):
        group = group.sort_values("feature_date").copy()
        prev_main = group["main_contract_vt"].shift(1).fillna("")
        group["mapping_main_changed_today"] = (
            group["main_contract_vt"].ne("")
            & prev_main.ne("")
            & group["main_contract_vt"].ne(prev_main)
        )
        days_since: list[int] = []
        current_days = 0
        first = True
        for changed in group["mapping_main_changed_today"].astype(bool):
            if first or changed:
                current_days = 0
                first = False
            else:
                current_days += 1
            days_since.append(current_days)
        group["days_since_mapping_main_change"] = days_since
        rows.append(group)
    if not rows:
        return mapping.copy()
    return pd.concat(rows, ignore_index=True)


def build_contract_oi_snapshots(bars: pd.DataFrame, mapping: pd.DataFrame) -> pd.DataFrame:
    if bars.empty:
        return pd.DataFrame()

    frame = bars.copy()
    if "feature_date" not in frame.columns:
        frame["feature_date"] = pd.to_datetime(frame["datetime"], errors="coerce").dt.normalize()
    else:
        frame["feature_date"] = pd.to_datetime(frame["feature_date"], errors="coerce").dt.normalize()
    if "contract_vt_symbol" not in frame.columns:
        frame["contract_vt_symbol"] = [
            _normalise_contract_vt(symbol, exchange) for symbol, exchange in zip(frame["symbol"], frame["exchange"])
        ]
    else:
        frame["contract_vt_symbol"] = frame["contract_vt_symbol"].map(_normalise_contract_vt)
    if "product_vt_symbol" not in frame.columns:
        frame["product_vt_symbol"] = frame["contract_vt_symbol"].map(contract_product_vt_symbol)
    else:
        frame["product_vt_symbol"] = frame["product_vt_symbol"].map(_normalise_product_vt)
    frame["product_key"] = frame["product_vt_symbol"].map(_product_key)
    frame["contract_key"] = frame["contract_vt_symbol"].map(_contract_key)
    frame["open_interest"] = pd.to_numeric(frame["open_interest"], errors="coerce")
    frame = frame[frame["feature_date"].notna() & frame["open_interest"].gt(0)].copy()
    frame = frame[frame["contract_vt_symbol"].map(_has_contract_month)].copy()
    if frame.empty:
        return pd.DataFrame()

    mapping_frame = mapping.copy()
    if not mapping_frame.empty:
        if "feature_date" not in mapping_frame.columns:
            mapping_frame["feature_date"] = pd.to_datetime(mapping_frame["date"], errors="coerce").dt.normalize()
        else:
            mapping_frame["feature_date"] = pd.to_datetime(mapping_frame["feature_date"], errors="coerce").dt.normalize()
        if "product_vt_symbol" not in mapping_frame.columns:
            if "continuous_symbol_vt" in mapping_frame.columns:
                mapping_frame["product_vt_symbol"] = mapping_frame["continuous_symbol_vt"].map(_normalise_product_vt)
            else:
                mapping_frame["product_vt_symbol"] = [
                    _normalise_product_vt(product, exchange)
                    for product, exchange in zip(mapping_frame["product"], mapping_frame["exchange"])
                ]
        else:
            mapping_frame["product_vt_symbol"] = mapping_frame["product_vt_symbol"].map(_normalise_product_vt)
        mapping_frame["product_key"] = mapping_frame["product_vt_symbol"].map(_product_key)
        mapping_frame["main_contract_vt"] = mapping_frame["main_contract_vt"].fillna("").map(
            lambda value: _normalise_contract_vt(value) if str(value).strip() else ""
        )
        mapping_frame = _mapping_change_table(
            mapping_frame[["feature_date", "product_vt_symbol", "product_key", "main_contract_vt"]].copy()
        )
    else:
        mapping_frame = pd.DataFrame(
            columns=[
                "feature_date",
                "product_vt_symbol",
                "product_key",
                "main_contract_vt",
                "mapping_main_changed_today",
                "days_since_mapping_main_change",
            ]
        )

    daily = (
        frame.groupby(["product_key", "product_vt_symbol", "feature_date", "contract_vt_symbol", "contract_key"], dropna=False)
        .agg(contract_open_interest=("open_interest", "sum"))
        .reset_index()
    )
    daily["product_total_oi"] = daily.groupby(["product_key", "feature_date"])["contract_open_interest"].transform("sum")
    daily["contract_oi_share"] = daily["contract_open_interest"] / daily["product_total_oi"].replace(0.0, np.nan)
    daily = daily.sort_values(
        ["product_key", "feature_date", "contract_open_interest", "contract_vt_symbol"],
        ascending=[True, True, False, True],
    ).reset_index(drop=True)
    daily["oi_rank"] = daily.groupby(["product_key", "feature_date"]).cumcount() + 1
    daily["contract_count"] = daily.groupby(["product_key", "feature_date"])["contract_vt_symbol"].transform("nunique")

    ranked = daily[["product_key", "feature_date", "oi_rank", "contract_vt_symbol", "contract_oi_share"]].copy()
    top1 = ranked[ranked["oi_rank"].eq(1)].rename(
        columns={"contract_vt_symbol": "top1_contract_vt", "contract_oi_share": "top1_oi_share"}
    )
    top2 = ranked[ranked["oi_rank"].eq(2)].rename(
        columns={"contract_vt_symbol": "top2_contract_vt", "contract_oi_share": "top2_oi_share"}
    )
    daily = daily.merge(top1[["product_key", "feature_date", "top1_contract_vt", "top1_oi_share"]], on=["product_key", "feature_date"], how="left")
    daily = daily.merge(top2[["product_key", "feature_date", "top2_contract_vt", "top2_oi_share"]], on=["product_key", "feature_date"], how="left")
    daily["top2_oi_share"] = daily["top2_oi_share"].fillna(0.0)
    daily["top2_cumulative_oi_share"] = daily["top1_oi_share"].fillna(0.0) + daily["top2_oi_share"].fillna(0.0)

    daily = daily.merge(
        mapping_frame[
            [
                "product_key",
                "feature_date",
                "main_contract_vt",
                "mapping_main_changed_today",
                "days_since_mapping_main_change",
            ]
        ],
        on=["product_key", "feature_date"],
        how="left",
    )
    daily["main_contract_vt"] = daily["main_contract_vt"].fillna("")
    daily["mapping_main_changed_today"] = daily["mapping_main_changed_today"].map(
        lambda value: bool(value) if pd.notna(value) else False
    ).astype(bool)
    daily["days_since_mapping_main_change"] = pd.to_numeric(
        daily["days_since_mapping_main_change"], errors="coerce"
    )
    daily["contract_is_mapping_main"] = daily["contract_vt_symbol"].eq(daily["main_contract_vt"])
    daily["contract_is_top1_oi"] = daily["oi_rank"].eq(1)
    daily["contract_is_top2_oi"] = daily["oi_rank"].le(2)

    main_share = (
        daily[daily["contract_is_mapping_main"]]
        .set_index(["product_key", "feature_date"])["contract_oi_share"]
        .rename("mapping_main_oi_share")
    )
    daily = daily.join(main_share, on=["product_key", "feature_date"])
    daily["mapping_main_oi_share"] = daily["mapping_main_oi_share"].fillna(0.0)
    daily["asof_date"] = daily["feature_date"] + pd.Timedelta(days=1)
    return daily.sort_values(["product_key", "feature_date", "oi_rank", "contract_vt_symbol"]).reset_index(drop=True)


def attach_contract_oi_features(
    entries: pd.DataFrame,
    snapshots: pd.DataFrame,
    *,
    max_feature_age_days: int = MAX_FEATURE_AGE_DAYS,
) -> pd.DataFrame:
    result = entries.copy()
    result["entry_date"] = pd.to_datetime(result["entry_date"], errors="coerce").dt.normalize()
    if "product_vt_symbol" in result.columns:
        result["contract_oi_product_key"] = result["product_vt_symbol"].map(_product_key)
    elif "product" in result.columns:
        result["contract_oi_product_key"] = result["product"].map(_product_key)
    else:
        result["contract_oi_product_key"] = ""
    result["contract_oi_contract_vt"] = result.get("vt_symbol", pd.Series("", index=result.index)).map(
        _normalise_contract_vt
    )
    result["contract_oi_contract_key"] = result["contract_oi_contract_vt"].map(_contract_key)

    defaults: dict[str, Any] = {
        "contract_oi_feature_date": pd.NaT,
        "contract_oi_asof_date": pd.NaT,
        "contract_oi_matched": False,
        "contract_open_interest": np.nan,
        "product_total_oi": np.nan,
        "contract_oi_share": np.nan,
        "contract_oi_rank": np.nan,
        "contract_count": np.nan,
        "top1_contract_vt": "",
        "top1_oi_share": np.nan,
        "top2_contract_vt": "",
        "top2_oi_share": np.nan,
        "top2_cumulative_oi_share": np.nan,
        "main_contract_vt": "",
        "mapping_main_oi_share": np.nan,
        "contract_is_mapping_main": False,
        "contract_is_top1_oi": False,
        "contract_is_top2_oi": False,
        "mapping_main_changed_today": False,
        "days_since_mapping_main_change": np.nan,
        "contract_oi_feature_age_days": np.nan,
    }
    for column, value in defaults.items():
        result[column] = value
    if result.empty or snapshots.empty:
        return result

    features = snapshots.copy()
    features["asof_date"] = pd.to_datetime(features["asof_date"], errors="coerce").dt.normalize()
    features["feature_date"] = pd.to_datetime(features["feature_date"], errors="coerce").dt.normalize()
    features["product_key"] = features["product_key"].map(_product_key)
    features["contract_key"] = features["contract_vt_symbol"].map(_contract_key)
    features = features.dropna(subset=["asof_date"]).sort_values(["product_key", "contract_key", "asof_date"])

    value_columns = [
        "feature_date",
        "asof_date",
        "contract_open_interest",
        "product_total_oi",
        "contract_oi_share",
        "oi_rank",
        "contract_count",
        "top1_contract_vt",
        "top1_oi_share",
        "top2_contract_vt",
        "top2_oi_share",
        "top2_cumulative_oi_share",
        "main_contract_vt",
        "mapping_main_oi_share",
        "contract_is_mapping_main",
        "contract_is_top1_oi",
        "contract_is_top2_oi",
        "mapping_main_changed_today",
        "days_since_mapping_main_change",
    ]

    for key, row_index in result.groupby(["contract_oi_product_key", "contract_oi_contract_key"], dropna=False).groups.items():
        product_key, contract_key = key
        feature_group = features[
            features["product_key"].eq(product_key) & features["contract_key"].eq(contract_key)
        ].sort_values("asof_date")
        if feature_group.empty:
            continue
        entry_group = result.loc[row_index].sort_values("entry_date")
        attached = pd.merge_asof(
            entry_group[["entry_date"]].reset_index(),
            feature_group[value_columns],
            left_on="entry_date",
            right_on="asof_date",
            direction="backward",
            tolerance=pd.Timedelta(days=max_feature_age_days),
        ).set_index("index")
        matched = attached["asof_date"].notna()
        if not matched.any():
            continue
        matched_index = attached.index[matched]
        result.loc[matched_index, "contract_oi_feature_date"] = attached.loc[matched, "feature_date"]
        result.loc[matched_index, "contract_oi_asof_date"] = attached.loc[matched, "asof_date"]
        result.loc[matched_index, "contract_oi_matched"] = True
        result.loc[matched_index, "contract_open_interest"] = attached.loc[matched, "contract_open_interest"]
        result.loc[matched_index, "product_total_oi"] = attached.loc[matched, "product_total_oi"]
        result.loc[matched_index, "contract_oi_share"] = attached.loc[matched, "contract_oi_share"]
        result.loc[matched_index, "contract_oi_rank"] = attached.loc[matched, "oi_rank"]
        result.loc[matched_index, "contract_count"] = attached.loc[matched, "contract_count"]
        result.loc[matched_index, "top1_contract_vt"] = attached.loc[matched, "top1_contract_vt"].fillna("")
        result.loc[matched_index, "top1_oi_share"] = attached.loc[matched, "top1_oi_share"]
        result.loc[matched_index, "top2_contract_vt"] = attached.loc[matched, "top2_contract_vt"].fillna("")
        result.loc[matched_index, "top2_oi_share"] = attached.loc[matched, "top2_oi_share"]
        result.loc[matched_index, "top2_cumulative_oi_share"] = attached.loc[matched, "top2_cumulative_oi_share"]
        result.loc[matched_index, "main_contract_vt"] = attached.loc[matched, "main_contract_vt"].fillna("")
        result.loc[matched_index, "mapping_main_oi_share"] = attached.loc[matched, "mapping_main_oi_share"]
        for column in [
            "contract_is_mapping_main",
            "contract_is_top1_oi",
            "contract_is_top2_oi",
            "mapping_main_changed_today",
        ]:
            bool_values = attached.loc[matched, column].map(lambda value: bool(value) if pd.notna(value) else False)
            result.loc[matched_index, column] = bool_values.astype(bool)
        result.loc[matched_index, "days_since_mapping_main_change"] = attached.loc[
            matched, "days_since_mapping_main_change"
        ]
        result.loc[matched_index, "contract_oi_feature_age_days"] = (
            attached.loc[matched, "entry_date"] - attached.loc[matched, "asof_date"]
        ).dt.days
    result["contract_oi_state"] = np.select(
        [
            ~result["contract_oi_matched"].astype(bool),
            result["contract_is_mapping_main"].astype(bool),
            result["contract_is_top1_oi"].astype(bool),
            result["contract_is_top2_oi"].astype(bool),
        ],
        [
            "oi_missing",
            "mapping_main",
            "oi_top1_non_mapping",
            "oi_top2_non_mapping",
        ],
        default="oi_tail_contract",
    )
    return result


def _build_condition_specs(matrix: pd.DataFrame) -> list[ConditionSpec]:
    matched = matrix["contract_oi_matched"].astype(bool)
    share = pd.to_numeric(matrix["contract_oi_share"], errors="coerce")
    rank = pd.to_numeric(matrix["contract_oi_rank"], errors="coerce")
    top1 = matched & rank.eq(1)
    top2 = matched & rank.le(2)
    mapping_main = matched & matrix["contract_is_mapping_main"].astype(bool)
    mapping_main_share = pd.to_numeric(matrix["mapping_main_oi_share"], errors="coerce")
    concentrated_top2 = matched & pd.to_numeric(matrix["top2_cumulative_oi_share"], errors="coerce").ge(0.70)
    strong_contract_share = matched & share.ge(0.50)
    medium_contract_share = matched & share.ge(0.33)
    recent_roll = matched & pd.to_numeric(matrix["days_since_mapping_main_change"], errors="coerce").between(0, 5)
    tail_contract = matched & rank.ge(3)

    matrix["contract_oi_top1"] = top1
    matrix["contract_oi_top2"] = top2
    matrix["contract_oi_mapping_main"] = mapping_main
    matrix["contract_oi_share_ge50"] = strong_contract_share
    matrix["contract_oi_share_ge33"] = medium_contract_share
    matrix["contract_oi_top2_concentration_ge70"] = concentrated_top2
    matrix["mapping_main_oi_share_ge40"] = matched & mapping_main_share.ge(0.40)
    matrix["mapping_main_changed_recent_5d"] = recent_roll
    matrix["contract_oi_tail_rank_ge3"] = tail_contract
    return [
        ConditionSpec("contract_oi_matched", "逐合约 OI 点时化命中；覆盖基线", "contract_oi", False, matched),
        ConditionSpec("contract_oi_top1", "开仓合约为上一可见日 OI 第一", "contract_oi", True, top1),
        ConditionSpec("contract_oi_top2", "开仓合约为上一可见日 OI 前二", "contract_oi", True, top2),
        ConditionSpec("contract_oi_mapping_main", "开仓合约与主力映射一致", "contract_oi", True, mapping_main),
        ConditionSpec("contract_oi_share_ge50", "开仓合约 OI 占比 >= 50%", "contract_oi", True, strong_contract_share),
        ConditionSpec("contract_oi_share_ge33", "开仓合约 OI 占比 >= 33%", "contract_oi", True, medium_contract_share),
        ConditionSpec(
            "contract_oi_top2_concentration_ge70",
            "品种 OI 前二合约占比 >= 70%",
            "contract_oi",
            True,
            concentrated_top2,
        ),
        ConditionSpec("mapping_main_oi_share_ge40", "映射主力合约 OI 占比 >= 40%", "contract_oi", True, matched & mapping_main_share.ge(0.40)),
        ConditionSpec(
            "mapping_main_changed_recent_5d",
            "主力映射最近 5 个交易日发生变化；只读换月风险提示",
            "contract_roll_risk",
            False,
            recent_roll,
        ),
        ConditionSpec(
            "contract_oi_tail_rank_ge3",
            "开仓合约 OI 排名 >=3；只读尾部合约风险提示",
            "contract_roll_risk",
            False,
            tail_contract,
        ),
    ]


def _feature_coverage(matrix: pd.DataFrame) -> pd.DataFrame:
    rows = []
    columns = [
        "contract_oi_matched",
        "contract_oi_feature_date",
        "contract_oi_share",
        "contract_oi_rank",
        "contract_oi_mapping_main",
        "contract_oi_top1",
        "contract_oi_top2",
        "contract_oi_share_ge50",
        "contract_oi_share_ge33",
        "contract_oi_top2_concentration_ge70",
        "mapping_main_oi_share_ge40",
        "mapping_main_changed_recent_5d",
        "contract_oi_tail_rank_ge3",
    ]
    for column in columns:
        if column not in matrix.columns:
            rows.append({"feature": column, "present": False, "non_null_count": 0, "active_count": 0, "coverage_pct": 0.0})
            continue
        values = matrix[column]
        non_null = int(values.notna().sum())
        if pd.api.types.is_bool_dtype(values):
            active = int(values.fillna(False).sum())
        elif column == "contract_oi_feature_date":
            active = non_null
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
            matched_count=("contract_oi_matched", "sum"),
            mapping_main_count=("contract_oi_mapping_main", "sum"),
            top1_count=("contract_oi_top1", "sum"),
            tail_rank_ge3_count=("contract_oi_tail_rank_ge3", "sum"),
            feature_start=("contract_oi_feature_date", "min"),
            feature_end=("contract_oi_feature_date", "max"),
            pnl_sum=("realized_pnl", "sum"),
            pnl_mean=("realized_pnl", "mean"),
            win_rate_pct=("realized_pnl", lambda values: float((pd.to_numeric(values, errors="coerce").fillna(0.0) > 0).mean() * 100.0)),
        )
        .reset_index()
    )
    grouped["matched_pct"] = grouped["matched_count"] / grouped["entry_count"] * 100.0
    grouped["mapping_main_pct"] = grouped["mapping_main_count"] / grouped["entry_count"] * 100.0
    grouped["top1_pct"] = grouped["top1_count"] / grouped["entry_count"] * 100.0
    grouped["tail_rank_ge3_pct"] = grouped["tail_rank_ge3_count"] / grouped["entry_count"] * 100.0
    return grouped.sort_values(["matched_pct", "entry_count"], ascending=[True, False]).reset_index(drop=True)


def _state_summary(matrix: pd.DataFrame) -> pd.DataFrame:
    if matrix.empty:
        return pd.DataFrame()
    grouped = (
        matrix.groupby("contract_oi_state", dropna=False)
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
    return grouped.sort_values("entry_count", ascending=False).reset_index(drop=True)


def _source_summary(entries: pd.DataFrame, snapshots: pd.DataFrame, mapping: pd.DataFrame) -> pd.DataFrame:
    objective = {_product_key(item): item for item in OBJECTIVE_PRODUCTS}
    for product in entries.get("product_vt_symbol", pd.Series(dtype=str)).dropna().astype(str).unique():
        objective[_product_key(product)] = _normalise_product_vt(product)
    rows = []
    snapshot_group = (
        snapshots.groupby("product_key", dropna=False)
        if not snapshots.empty
        else {}
    )
    mapping_group = mapping.groupby("product_key", dropna=False) if not mapping.empty else {}
    for key, product in sorted(objective.items()):
        if not snapshots.empty and key in snapshot_group.groups:
            snap = snapshots.loc[snapshot_group.groups[key]]
            contract_count = int(snap["contract_vt_symbol"].nunique())
            snapshot_rows = int(len(snap))
            oi_start = snap["feature_date"].min()
            oi_end = snap["feature_date"].max()
        else:
            contract_count = 0
            snapshot_rows = 0
            oi_start = pd.NaT
            oi_end = pd.NaT
        if not mapping.empty and key in mapping_group.groups:
            maps = mapping.loc[mapping_group.groups[key]]
            mapping_rows = int(len(maps))
            mapping_start = maps["feature_date"].min()
            mapping_end = maps["feature_date"].max()
        else:
            mapping_rows = 0
            mapping_start = pd.NaT
            mapping_end = pd.NaT
        rows.append(
            {
                "product_vt_symbol": product,
                "product_key": key,
                "contract_count": contract_count,
                "snapshot_rows": snapshot_rows,
                "oi_feature_start": oi_start.date().isoformat() if pd.notna(oi_start) else "",
                "oi_feature_end": oi_end.date().isoformat() if pd.notna(oi_end) else "",
                "mapping_rows": mapping_rows,
                "mapping_start": mapping_start.date().isoformat() if pd.notna(mapping_start) else "",
                "mapping_end": mapping_end.date().isoformat() if pd.notna(mapping_end) else "",
                "covers_entry_end_tminus1": bool(pd.notna(oi_end) and pd.Timestamp(oi_end) >= OBJECTIVE_ENTRY_END - pd.Timedelta(days=1)),
                "mapping_covers_entry_end": bool(pd.notna(mapping_end) and pd.Timestamp(mapping_end) >= OBJECTIVE_ENTRY_END),
            }
        )
    return pd.DataFrame(rows)


def _decision(matrix: pd.DataFrame, condition_summary: pd.DataFrame, source_summary: pd.DataFrame) -> dict[str, Any]:
    stable = condition_summary[condition_summary["stable_oos_candidate"].astype(bool)].copy()
    matched_count = int(matrix["contract_oi_matched"].sum()) if "contract_oi_matched" in matrix.columns else 0
    matched_rate = _safe_div(matched_count, len(matrix))
    source_gap_products = source_summary[
        ~source_summary["covers_entry_end_tminus1"].astype(bool)
    ]["product_vt_symbol"].tolist()
    if not stable.empty and matched_rate >= 0.90 and not source_gap_products:
        decision = "stage049_contract_oi_migration_candidate_requires_proxy_engine"
        next_stage = "freeze_one_contract_oi_condition_proxy_then_true_engine_ab"
    elif not stable.empty and matched_rate >= 0.90:
        decision = "stage049_contract_oi_migration_candidate_but_source_gap_keep_readonly"
        next_stage = "fix_contract_oi_source_gap_before_proxy_engine"
    else:
        decision = "stage049_contract_oi_migration_no_stable_candidate_or_coverage_gap_keep_readonly"
        next_stage = "do_not_trade_oi_migration_rule_yet_continue_domestic_pit_source_search"
    return {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "line_id": LINE_ID,
        "decision": decision,
        "next_stage": next_stage,
        "entry_count": int(len(matrix)),
        "matched_count": matched_count,
        "matched_rate": matched_rate,
        "stable_conditions": stable["condition"].head(10).tolist(),
        "source_gap_products": source_gap_products,
        "db_path": str(DEFAULT_DB_PATH),
        "mapping_path": str(MAIN_MAPPING_PATH),
        "stage038_feature_matrix_path": str(STAGE038_FEATURE_MATRIX_PATH),
        "strategy_changed": False,
        "true_engine": False,
        "ab_triggered": False,
        "ctp_connected": False,
        "order_api_called": False,
        "objective_completion_proven": False,
        "external_research_judgment": (
            "CME documents open interest as end-of-day outstanding futures contracts and Pace of the Roll as the "
            "daily progression of OI across contract months; pysystemtrade and Databento documentation both treat "
            "contract-month roll rules as a separate continuous-futures construction problem. Therefore this stage "
            "audits point-in-time contract OI migration and mapping consistency, not a direct alpha rule."
        ),
        "overfit_reflection_before": (
            "否。Stage049 不扫收益阈值，只用固定的逐合约 OI 占比、排名、主力映射一致性做点时审计。"
        ),
        "continue_value_before": (
            "有。C9 当前损益质量问题可能来自换月/合约流动性细节；这是比外盘 COT 更贴近国内成交路径的可复验信息源。"
        ),
        "overfit_reflection_after": (
            "否。本阶段只报告固定条件的 OOS 表现和数据覆盖；任何后续按本表反复调 0.33/0.50/0.70 阈值都会变成过拟合。"
        ),
        "continue_value_after": (
            "有条件。若稳定候选非空且数据覆盖完整，下一步只能冻结一个低自由度 proxy 进 true engine；若覆盖或 OOS 不足则继续找更强 PIT 信息源。"
        ),
        "outputs": {
            "snapshots": str(SNAPSHOTS_PATH),
            "joined": str(JOINED_PATH),
            "condition_summary": str(CONDITION_SUMMARY_PATH),
            "feature_coverage": str(FEATURE_COVERAGE_PATH),
            "product_summary": str(PRODUCT_SUMMARY_PATH),
            "source_summary": str(SOURCE_SUMMARY_PATH),
            "state_summary": str(STATE_SUMMARY_PATH),
            "decision": str(DECISION_PATH),
            "report": str(REPORT_PATH),
        },
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
    report = f"""# Stage049 - 逐合约 OI 迁移与主力映射 PIT 审计

- 记录时间：`{datetime.now().strftime('%Y-%m-%dT%H:%M')}`
- line_id：`{LINE_ID}`
- model_tag：`{MODEL_TAG}`
- 决策：`{decision['decision']}`

## 外部调研与判断

- CME 将 open interest 定义为日终未平仓合约数量，并明确其可用于观察市场参与和趋势强度。
- CME Pace of the Roll 资料把合约月之间的 OI 迁移作为每日 roll 进程来观察，说明“在哪个合约上交易”本身是独立问题。
- pysystemtrade 和 Databento 都把连续期货构造、合约 roll rule 与策略信号分开处理；因此本阶段只做逐合约 OI 迁移和主力映射一致性的点时审计，不直接写交易规则。

## 口径

- OI 数据：`{DEFAULT_DB_PATH}` 的 `dbbardata` 日线逐合约 `open_interest`。
- 主力映射：`{MAIN_MAPPING_PATH}`。
- 样本：Stage038 opened flat-entry 聚合矩阵 `{STAGE038_FEATURE_MATRIX_PATH}`。
- 点时规则：`feature_date` 的 OI 到 `feature_date + 1 天` 才可见；当天开仓不能偷看当天 OI。
- 最大特征年龄：`{MAX_FEATURE_AGE_DAYS}` 天。
- 本阶段只读审计；不改 C9/15w 配置，不跑 true engine，不连接 CTP/SimNow，不调用 order API。

## 数据源覆盖

{_md_table(source_summary)}

## 特征覆盖

{_md_table(feature_coverage)}

## 状态摘要

{_md_table(state_summary)}

## 条件 OOS 摘要

{_md_table(condition_summary, max_rows=20)}

## 品种摘要

{_md_table(product_summary.head(30))}

## 判断

- 命中：`{decision['matched_count']}/{decision['entry_count']}`，命中率 `{decision['matched_rate']:.4%}`。
- 稳定 OOS 候选：`{decision['stable_conditions']}`。
- 数据缺口品种：`{decision['source_gap_products']}`。
- 若稳定候选为空或数据源覆盖不足，不允许把逐合约 OI 迁移直接接入 AI 选品、开仓过滤或加风险。

## 输出

- snapshots：`{SNAPSHOTS_PATH}`
- joined：`{JOINED_PATH}`
- condition_summary：`{CONDITION_SUMMARY_PATH}`
- feature_coverage：`{FEATURE_COVERAGE_PATH}`
- product_summary：`{PRODUCT_SUMMARY_PATH}`
- source_summary：`{SOURCE_SUMMARY_PATH}`
- state_summary：`{STATE_SUMMARY_PATH}`
- decision：`{DECISION_PATH}`
- report：`{REPORT_PATH}`
- stage_record：`{stage_record_path}`

## 反思

- 运行前过拟合反思：{decision['overfit_reflection_before']}
- 运行后过拟合反思：{decision['overfit_reflection_after']}
- 运行前继续价值反思：{decision['continue_value_before']}
- 运行后继续价值反思：{decision['continue_value_after']}
"""
    REPORT_PATH.write_text(report, encoding="utf-8")


def _write_stage_record(decision: dict[str, Any], condition_summary: pd.DataFrame, source_summary: pd.DataFrame) -> Path:
    timestamp = datetime.now()
    stage_path = STAGES_DIR / f"{timestamp:%Y%m%d_%H%M}_stage049_contract_oi_migration_audit.md"
    stable = condition_summary[condition_summary["stable_oos_candidate"].astype(bool)].copy()
    lines = [
        "# Stage049 - 逐合约 OI 迁移与主力映射 PIT 审计",
        "",
        f"- 记录时间：`{timestamp.isoformat(timespec='minutes')}`",
        f"- line_id：`{LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        "- 是否重要突破版本：`否`",
        f"- 决策：`{decision['decision']}`",
        "",
        "## 本次版本变更",
        "",
        f"- 新增脚本：`research/lines/{LINE_ID}/tools/stage049_contract_oi_migration_audit.py`",
        f"- 新增测试：`tests/test_rebuilt_c9_stage049_contract_oi_migration.py`",
        f"- 新增参数：`MAX_FEATURE_AGE_DAYS={MAX_FEATURE_AGE_DAYS}`、`EMBARGO_DAYS={EMBARGO_DAYS}`、`N_SPLITS={N_SPLITS}`。",
        "- 修改参数：无，官方 C9/15w 配置未改。",
        "- 删除参数：无。",
        "- 新增回测结果：无，本阶段不是收益回测，只做逐合约 OI 点时审计。",
        "- 本阶段不连接 CTP，不调用订单 API，不触发 A/B。",
        "",
        "## 调研和判断结论",
        "",
        "- CME OI / Pace of the Roll 资料支持把逐合约 OI 迁移作为换月和流动性质量信息；pysystemtrade/Databento 资料提示 roll rule 应与 alpha 信号隔离。",
        "- 因此 Stage049 不训练模型、不扫阈值，只判断现有 opened flat-entry 样本在逐合约 OI 迁移上的 OOS 稳定性。",
        "",
        "## 审计结果",
        "",
        f"- entry_count：`{decision['entry_count']}`",
        f"- matched：`{decision['matched_count']}`，matched_rate：`{decision['matched_rate']:.4%}`",
        f"- stable_conditions：`{', '.join(decision['stable_conditions']) if decision['stable_conditions'] else '无'}`",
        f"- source_gap_products：`{', '.join(decision['source_gap_products']) if decision['source_gap_products'] else '无'}`",
        "",
        "## 条件摘要",
        "",
        _md_table(
            condition_summary[
                [
                    "condition",
                    "candidate_eligible",
                    "count",
                    "total_pnl",
                    "mean_pnl_lift_vs_base",
                    "win_rate_lift_pp",
                    "oos_positive_fold_count",
                    "oos_test_fold_count",
                    "oos_min_fold_pnl",
                    "stable_oos_candidate",
                ]
            ],
            max_rows=20,
        ),
        "",
        "## 数据源覆盖",
        "",
        _md_table(source_summary, max_rows=30),
        "",
        "## 输出",
        "",
        f"- snapshots：`{SNAPSHOTS_PATH}`",
        f"- joined：`{JOINED_PATH}`",
        f"- condition_summary：`{CONDITION_SUMMARY_PATH}`",
        f"- feature_coverage：`{FEATURE_COVERAGE_PATH}`",
        f"- product_summary：`{PRODUCT_SUMMARY_PATH}`",
        f"- source_summary：`{SOURCE_SUMMARY_PATH}`",
        f"- state_summary：`{STATE_SUMMARY_PATH}`",
        f"- decision：`{DECISION_PATH}`",
        f"- report：`{REPORT_PATH}`",
        "",
        "## 反思",
        "",
        f"- 运行前过拟合反思：{decision['overfit_reflection_before']}",
        f"- 运行后过拟合反思：{decision['overfit_reflection_after']}",
        f"- 运行前继续价值反思：{decision['continue_value_before']}",
        f"- 运行后继续价值反思：{decision['continue_value_after']}",
        "",
        "## 后续规划和 TODO",
        "",
        f"- 下一步：`{decision['next_stage']}`。",
        "- 如果稳定候选存在，下一步只能冻结一个低自由度 proxy 进入 true engine，不允许继续扫 OI 阈值。",
        "- 如果覆盖或 OOS 不足，继续找国内 PIT 信息源或修复数据源缺口，不把本阶段条件接入实盘。",
    ]
    stage_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return stage_path


def run() -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    STAGES_DIR.mkdir(parents=True, exist_ok=True)
    entries = _read_csv(STAGE038_FEATURE_MATRIX_PATH)
    entries["entry_date"] = pd.to_datetime(entries["entry_date"], errors="coerce").dt.normalize()
    entry_products = set(entries.get("product_vt_symbol", pd.Series(dtype=str)).dropna().map(_product_key))
    objective_products = {_product_key(item) for item in OBJECTIVE_PRODUCTS}
    product_keys = entry_products | objective_products

    bars = load_contract_daily_bars(
        DEFAULT_DB_PATH,
        start=SOURCE_START,
        end=OBJECTIVE_ENTRY_END,
        product_keys=product_keys,
    )
    mapping = load_main_contract_mapping(
        MAIN_MAPPING_PATH,
        start=SOURCE_START,
        end=OBJECTIVE_ENTRY_END,
        product_keys=product_keys,
    )
    snapshots = build_contract_oi_snapshots(bars, mapping)
    matrix = attach_contract_oi_features(entries, snapshots)
    conditions = _build_condition_specs(matrix)
    splits = build_purged_time_splits(matrix, date_column="entry_date", n_splits=N_SPLITS, embargo_days=EMBARGO_DAYS)
    condition_summary = summarize_condition_oos(matrix, splits, conditions)
    feature_coverage = _feature_coverage(matrix)
    product_summary = _product_summary(matrix)
    source_summary = _source_summary(entries, snapshots, mapping)
    state_summary = _state_summary(matrix)
    decision = _decision(matrix, condition_summary, source_summary)

    snapshots.to_csv(SNAPSHOTS_PATH, index=False, encoding="utf-8-sig")
    matrix.to_csv(JOINED_PATH, index=False, encoding="utf-8-sig")
    condition_summary.to_csv(CONDITION_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    feature_coverage.to_csv(FEATURE_COVERAGE_PATH, index=False, encoding="utf-8-sig")
    product_summary.to_csv(PRODUCT_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    source_summary.to_csv(SOURCE_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    state_summary.to_csv(STATE_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    stage_record = _write_stage_record(decision, condition_summary, source_summary)
    _write_report(
        source_summary=source_summary,
        feature_coverage=feature_coverage,
        condition_summary=condition_summary,
        product_summary=product_summary,
        state_summary=state_summary,
        decision=decision,
        stage_record_path=stage_record,
    )
    decision["stage_record_path"] = str(stage_record)
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return decision


def main() -> None:
    decision = run()
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
