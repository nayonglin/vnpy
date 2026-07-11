from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pandas as pd


ROOT_DIR = Path(__file__).resolve().parents[4]
LINE_ID = "futures_trend_rebuilt_c9_15w_v2_optimization"
STAGE_ID = "stage131_c9_event_targeted_option_acquisition_manifest"
MODEL_TAG = f"{STAGE_ID}_v1"
OUTPUT_PREFIX = f"rebuilt_c9_v2_{STAGE_ID}"

BACKTEST_OUTPUTS = ROOT_DIR / "examples" / "portfolio_backtesting" / "backtest_outputs"
SOURCE_PREFIX = "qmt_roll_stage847_stage830_c4_stop_retry_engine"
SOURCE_TAG = "stage847_stage830_c4_stop_retry_engine_v1"
SOURCE_PATHS = {
    "closed_lots": BACKTEST_OUTPUTS / f"{SOURCE_PREFIX}_closed_lots_{SOURCE_TAG}.csv",
    "trades": BACKTEST_OUTPUTS / f"{SOURCE_PREFIX}_trades_{SOURCE_TAG}.csv",
    "entry_risk": BACKTEST_OUTPUTS / f"{SOURCE_PREFIX}_entry_risk_{SOURCE_TAG}.csv",
    "trading_calendar": BACKTEST_OUTPUTS / f"{SOURCE_PREFIX}_curve_{SOURCE_TAG}.csv",
}
SOURCE_HASHES = {
    "closed_lots": "1bc2771d40fd3f5f1f7c240ab259b1d39e65265cf44d5eb82dc0f742b29581a2",
    "trades": "59acf2887778eb5d943f7db70c6bf479b4db4a412f96022338ca6b106bd46c48",
    "entry_risk": "4224a8fb0482cb67ef330c481b0e19df02b82e903df9bfade163bd9b0affa9b7",
    "trading_calendar": "199926a5dac7e21c0381dfd807675235e07cf650429fa0295e2e2705d94cc56d",
}
EXPECTED = {
    "closed_lot_count": 405,
    "trade_count": 793,
    "open_trade_count": 388,
    "entry_risk_count": 367,
    "calendar_row_count": 8148,
    "calendar_date_count": 2037,
    "contract_count": 238,
    "query_event_count": 365,
    "entry_date_count": 332,
    "product_count": 19,
    "direct_link_count": 360,
    "retry_link_count": 23,
    "fallback_mismatch_count": 5,
    "existing_stop_count": 373,
    "recovered_stop_count": 32,
    "existing_risk_count": 373,
    "recovered_risk_count": 32,
}

SUPPORTED_EXCHANGES = {"CFFEX", "SHFE", "DCE", "CZCE", "INE", "GFEX"}
BASE_REQUIRED_COLUMNS = [
    "lot_id",
    "open_trade_id",
    "vt_symbol",
    "direction",
    "entry_date",
    "exit_date",
    "entry_price",
    "volume",
    "size",
]
TRADE_REQUIRED_COLUMNS = [
    "trade_id",
    "datetime",
    "date",
    "vt_symbol",
    "direction",
    "offset",
    "price",
    "volume",
]
RISK_REQUIRED_COLUMNS = [
    "entry_index",
    "datetime",
    "date",
    "contract_vt_symbol",
    "direction",
    "volume",
    "stop_price",
    "stop_distance",
    "risk_per_contract",
    "actual_risk_amount",
    "target_risk_amount",
]
SOURCE_USECOLS = {
    "closed_lots": BASE_REQUIRED_COLUMNS + ["product", "holding_calendar_days", "stop_distance", "risk_amount"],
    "trades": TRADE_REQUIRED_COLUMNS,
    "entry_risk": RISK_REQUIRED_COLUMNS + ["risk_multiplier", "selected_volume", "size"],
    "trading_calendar": ["date"],
}

LINE_ROOT = ROOT_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_ROOT / "outputs" / STAGE_ID
PREDECL_PATH = (
    LINE_ROOT
    / "stages"
    / "20260711_1308_stage131_c9_event_targeted_option_acquisition_manifest_predecl.md"
)
TEST_PATH = ROOT_DIR / "tests" / "test_rebuilt_c9_v2_stage131_c9_event_targeted_option_acquisition_manifest.py"
TOOL_PATH = Path(__file__).resolve()


def _out(kind: str, suffix: str = "csv") -> Path:
    return OUTPUT_DIR / f"{OUTPUT_PREFIX}_{kind}_{MODEL_TAG}.{suffix}"


SOURCE_INVENTORY_PATH = _out("source_inventory")
SOURCE_AUDIT_PATH = _out("source_audit")
ENTRY_RISK_LINKS_PATH = _out("entry_risk_links")
ENTRY_RISK_LINK_AUDIT_PATH = _out("entry_risk_link_audit")
ENRICHED_LOTS_PATH = _out("enriched_lots")
QUERY_EVENTS_PATH = _out("query_events")
REQUIREMENTS_PATH = _out("acquisition_requirements")
MANIFEST_AUDIT_PATH = _out("manifest_audit")
YEAR_SUMMARY_PATH = _out("entry_year_summary")
PRODUCT_SUMMARY_PATH = _out("product_summary")
DATA_CONTRACT_PATH = _out("data_contract")
DECISION_PATH = _out("decision", "json")
LINEAGE_PATH = _out("lineage", "json")
REPORT_PATH = _out("report", "md")
MANIFEST_PATH = _out("manifest")
MANIFEST_CHECKSUM_PATH = _out("manifest_sha256", "txt")


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        result = float(value)
        return None if math.isnan(result) or math.isinf(result) else result
    if isinstance(value, (pd.Timestamp,)):
        return value.isoformat()
    if value is None or (not isinstance(value, (str, bool)) and pd.isna(value)):
        return None
    return value


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_无记录_"
    view = frame.head(max_rows).copy() if max_rows is not None else frame.copy()
    return view.to_markdown(index=False, floatfmt=".4f")


def _product_from_vt(vt_symbol: Any) -> str:
    text = str(vt_symbol or "")
    if "." not in text:
        return ""
    symbol, exchange = text.rsplit(".", 1)
    match = re.match(r"([A-Za-z]+)", symbol)
    return f"{match.group(1) if match else symbol}.{exchange}"


def to_tqsdk_underlying(vt_symbol: str) -> str:
    text = str(vt_symbol or "").strip()
    if text.count(".") != 1:
        raise ValueError(f"invalid vt_symbol: {text!r}")
    symbol, exchange = text.rsplit(".", 1)
    if not symbol or exchange not in SUPPORTED_EXCHANGES:
        raise ValueError(f"unsupported vt_symbol: {text!r}")
    return f"{exchange}.{symbol}"


def event_id_for(vt_symbol: str, entry_date: Any) -> str:
    date_text = pd.Timestamp(entry_date).normalize().date().isoformat()
    return hashlib.sha256(f"{vt_symbol}|{date_text}".encode("utf-8")).hexdigest()


def audit_source_lots(frame: pd.DataFrame) -> dict[str, Any]:
    missing_columns = sorted(set(BASE_REQUIRED_COLUMNS) - set(frame.columns))
    if missing_columns:
        return {
            "source_row_count": int(len(frame)),
            "missing_column_count": len(missing_columns),
            "missing_columns": "|".join(missing_columns),
            "missing_required_value_count": 0,
            "duplicate_lot_id_count": 0,
            "invalid_entry_date_count": 0,
            "invalid_exit_date_count": 0,
            "exit_before_entry_count": 0,
            "invalid_direction_count": 0,
            "invalid_vt_symbol_count": 0,
            "nonpositive_entry_price_count": 0,
            "nonpositive_volume_count": 0,
            "nonpositive_size_count": 0,
            "source_audit_pass": False,
        }

    data = frame.copy()
    entry = pd.to_datetime(data["entry_date"], errors="coerce").dt.normalize()
    exit_ = pd.to_datetime(data["exit_date"], errors="coerce").dt.normalize()
    required = data[BASE_REQUIRED_COLUMNS].copy()
    empty_strings = required.select_dtypes(include="object").apply(lambda col: col.astype(str).str.strip().eq(""))
    missing_values = int(required.isna().sum().sum() + empty_strings.sum().sum())
    invalid_vt = 0
    for symbol in data["vt_symbol"]:
        try:
            to_tqsdk_underlying(str(symbol))
        except ValueError:
            invalid_vt += 1
    numeric = {
        column: pd.to_numeric(data[column], errors="coerce")
        for column in ("entry_price", "volume", "size")
    }
    result = {
        "source_row_count": int(len(data)),
        "missing_column_count": 0,
        "missing_columns": "",
        "missing_required_value_count": missing_values,
        "duplicate_lot_id_count": int(data.duplicated("lot_id", keep=False).sum()),
        "invalid_entry_date_count": int(entry.isna().sum()),
        "invalid_exit_date_count": int(exit_.isna().sum()),
        "exit_before_entry_count": int((exit_ < entry).fillna(False).sum()),
        "invalid_direction_count": int((~data["direction"].astype(str).str.lower().isin(["long", "short"])).sum()),
        "invalid_vt_symbol_count": int(invalid_vt),
        "nonpositive_entry_price_count": int((numeric["entry_price"].isna() | numeric["entry_price"].le(0)).sum()),
        "nonpositive_volume_count": int((numeric["volume"].isna() | numeric["volume"].le(0)).sum()),
        "nonpositive_size_count": int((numeric["size"].isna() | numeric["size"].le(0)).sum()),
    }
    result["source_audit_pass"] = not any(
        int(result[key])
        for key in result
        if key.endswith("_count") and key not in {"source_row_count"}
    )
    return result


def load_frozen_sources() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    inventory_rows: list[dict[str, Any]] = []
    frames: dict[str, pd.DataFrame] = {}
    for name, path in SOURCE_PATHS.items():
        if not path.is_file():
            raise FileNotFoundError(path)
        actual_hash = file_sha256(path)
        if actual_hash != SOURCE_HASHES[name]:
            raise ValueError(f"{name} SHA256 mismatch: {actual_hash}")
        frame = pd.read_csv(path, usecols=SOURCE_USECOLS[name])
        frames[name] = frame
        inventory_rows.append(
            {
                "source_name": name,
                "path": str(path),
                "rows": int(len(frame)),
                "bytes": path.stat().st_size,
                "sha256": actual_hash,
                "expected_sha256": SOURCE_HASHES[name],
                "hash_match": True,
            }
        )
    return (
        frames["closed_lots"],
        frames["trades"],
        frames["entry_risk"],
        frames["trading_calendar"],
        pd.DataFrame(inventory_rows),
    )


def _normalized_trade_frames(
    trades: pd.DataFrame, entry_risk: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    missing_trade = sorted(set(TRADE_REQUIRED_COLUMNS) - set(trades.columns))
    missing_risk = sorted(set(RISK_REQUIRED_COLUMNS) - set(entry_risk.columns))
    if missing_trade or missing_risk:
        raise ValueError(f"missing trade/risk columns: trades={missing_trade}, risk={missing_risk}")
    all_trades = trades.copy()
    all_trades["trade_datetime"] = pd.to_datetime(all_trades["datetime"], errors="coerce", utc=True)
    all_trades["trade_date"] = pd.to_datetime(all_trades["date"], errors="coerce").dt.normalize()
    raw_direction = all_trades["direction"].astype(str).str.lower()
    all_trades["position_direction_key"] = np.where(
        all_trades["offset"].astype(str).eq("Open"),
        raw_direction,
        raw_direction.map({"long": "short", "short": "long"}),
    )
    all_trades.sort_values(["trade_datetime", "vt_symbol", "trade_id"], inplace=True)

    open_trades = all_trades[all_trades["offset"].astype(str).eq("Open")].copy()
    open_trades["open_trade_id"] = open_trades["trade_id"].astype(str)
    open_trades["direction_key"] = open_trades["direction"].astype(str).str.lower()
    open_trades["volume_key"] = pd.to_numeric(open_trades["volume"], errors="coerce").round(8)
    open_trades.sort_values(["trade_datetime", "vt_symbol", "open_trade_id"], inplace=True)

    risks = entry_risk.copy()
    risks["risk_datetime"] = pd.to_datetime(risks["datetime"], errors="coerce", utc=True)
    risks["risk_date"] = pd.to_datetime(risks["date"], errors="coerce").dt.normalize()
    risks["direction_key"] = risks["direction"].astype(str).str.lower()
    risks["volume_key"] = pd.to_numeric(risks["volume"], errors="coerce").round(8)
    risks["entry_index"] = pd.to_numeric(risks["entry_index"], errors="raise").astype(int)
    risks.sort_values(["risk_datetime", "contract_vt_symbol", "entry_index"], inplace=True)
    return all_trades.reset_index(drop=True), open_trades.reset_index(drop=True), risks.reset_index(drop=True)


def _link_row(trade: Mapping[str, Any], risk: Mapping[str, Any], method: str) -> dict[str, Any]:
    return {
        "open_trade_id": str(trade["open_trade_id"]),
        "vt_symbol": str(trade["vt_symbol"]),
        "direction": str(trade["direction_key"]),
        "trade_datetime": trade["trade_datetime"],
        "trade_date": trade["trade_date"],
        "trade_price": float(trade["price"]),
        "trade_volume": float(trade["volume_key"]),
        "entry_risk_index": int(risk["entry_index"]),
        "entry_risk_datetime": risk["risk_datetime"],
        "entry_risk_date": risk["risk_date"],
        "entry_risk_volume": float(risk["volume_key"]),
        "original_stop_price": float(risk["stop_price"]),
        "original_stop_distance": float(risk["stop_distance"]),
        "entry_risk_per_contract": pd.to_numeric(
            pd.Series([risk.get("risk_per_contract")]), errors="coerce"
        ).iloc[0],
        "entry_risk_actual_risk_amount": pd.to_numeric(
            pd.Series([risk.get("actual_risk_amount")]), errors="coerce"
        ).iloc[0],
        "entry_risk_target_risk_amount": pd.to_numeric(
            pd.Series([risk.get("target_risk_amount")]), errors="coerce"
        ).iloc[0],
        "entry_risk_multiplier": pd.to_numeric(pd.Series([risk.get("risk_multiplier")]), errors="coerce").iloc[0],
        "entry_risk_selected_volume": pd.to_numeric(pd.Series([risk.get("selected_volume")]), errors="coerce").iloc[0],
        "entry_risk_size": pd.to_numeric(pd.Series([risk.get("size")]), errors="coerce").iloc[0],
        "risk_link_method": method,
    }


LINK_COLUMNS = list(
    _link_row(
        {
            "open_trade_id": "",
            "vt_symbol": "",
            "direction_key": "",
            "trade_datetime": pd.NaT,
            "trade_date": pd.NaT,
            "price": np.nan,
            "volume_key": np.nan,
        },
        {
            "entry_index": -1,
            "risk_datetime": pd.NaT,
            "risk_date": pd.NaT,
            "volume_key": np.nan,
            "stop_price": np.nan,
            "stop_distance": np.nan,
        },
        "",
    )
)


def build_entry_risk_links(
    trades: pd.DataFrame,
    entry_risk: pd.DataFrame,
    trading_dates: pd.Series,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    all_trades, open_trades, risks = _normalized_trade_frames(trades, entry_risk)
    calendar = pd.Series(pd.to_datetime(trading_dates, format="mixed", errors="coerce")).dropna().dt.normalize()
    calendar = pd.Series(sorted(calendar.unique()))
    next_trading_date = {
        pd.Timestamp(value): pd.Timestamp(calendar.iloc[index + 1])
        for index, value in enumerate(calendar.iloc[:-1])
    }
    risks["next_trading_date"] = risks["risk_date"].map(next_trading_date)
    links: dict[str, dict[str, Any]] = {}
    used_risk_indexes: set[int] = set()

    risk_groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in risks.to_dict("records"):
        key = (str(row["contract_vt_symbol"]), str(row["direction_key"]))
        risk_groups.setdefault(key, []).append(row)

    ambiguous_direct_count = 0
    for trade in open_trades.to_dict("records"):
        key = (str(trade["vt_symbol"]), str(trade["direction_key"]))
        eligible = [
            risk
            for risk in risk_groups.get(key, [])
            if int(risk["entry_index"]) not in used_risk_indexes
            and float(risk["volume_key"]) == float(trade["volume_key"])
            and risk["next_trading_date"] == trade["trade_date"]
        ]
        if not eligible:
            continue
        first = eligible[0]
        if sum(risk["risk_datetime"] == first["risk_datetime"] for risk in eligible) > 1:
            ambiguous_direct_count += 1
            continue
        risk_index = int(first["entry_index"])
        links[str(trade["open_trade_id"])] = _link_row(
            trade, first, "direct_exact_volume_next_trade_date"
        )
        used_risk_indexes.add(risk_index)

    records = open_trades.to_dict("records")
    retry_without_intervening_close_count = 0
    for trade in records:
        trade_id = str(trade["open_trade_id"])
        if trade_id in links:
            continue
        prior = [
            candidate
            for candidate in records
            if candidate["vt_symbol"] == trade["vt_symbol"]
            and candidate["direction_key"] == trade["direction_key"]
            and candidate["trade_date"] == trade["trade_date"]
            and candidate["trade_datetime"] < trade["trade_datetime"]
            and str(candidate["open_trade_id"]) in links
        ]
        if not prior:
            continue
        prior_trade = max(prior, key=lambda item: item["trade_datetime"])
        intervening_close = all_trades[
            all_trades["vt_symbol"].astype(str).eq(str(trade["vt_symbol"]))
            & all_trades["offset"].astype(str).eq("Close")
            & all_trades["position_direction_key"].eq(str(trade["direction_key"]))
            & all_trades["trade_datetime"].gt(prior_trade["trade_datetime"])
            & all_trades["trade_datetime"].lt(trade["trade_datetime"])
        ]
        if intervening_close.empty:
            retry_without_intervening_close_count += 1
            continue
        inherited = links[str(prior_trade["open_trade_id"])]
        risk = risks[risks["entry_index"].eq(inherited["entry_risk_index"])].iloc[0].to_dict()
        links[trade_id] = _link_row(trade, risk, "intraday_retry_inherit")

    ambiguous_count = 0
    non_next_trading_date_candidate_count = 0
    for trade in records:
        trade_id = str(trade["open_trade_id"])
        if trade_id in links:
            continue
        same_key_prior = risks[
            risks["contract_vt_symbol"].astype(str).eq(str(trade["vt_symbol"]))
            & risks["direction_key"].eq(str(trade["direction_key"]))
            & risks["risk_datetime"].le(trade["trade_datetime"])
            & ~risks["entry_index"].isin(used_risk_indexes)
        ].copy()
        candidates = same_key_prior[
            same_key_prior["next_trading_date"].eq(trade["trade_date"])
        ].copy()
        if candidates.empty:
            if not same_key_prior.empty:
                non_next_trading_date_candidate_count += 1
            continue
        if len(candidates) != 1:
            ambiguous_count += 1
            continue
        top = candidates.iloc[0]
        if float(top["volume_key"]) == float(trade["volume_key"]):
            ambiguous_count += 1
            continue
        method = "fallback_next_trade_date_volume_mismatch"
        links[trade_id] = _link_row(trade, top.to_dict(), method)
        used_risk_indexes.add(int(top["entry_index"]))

    link_frame = pd.DataFrame(list(links.values()), columns=LINK_COLUMNS)
    if not link_frame.empty:
        link_frame = link_frame.sort_values(
            ["trade_datetime", "vt_symbol", "open_trade_id"]
        ).reset_index(drop=True)
    method_counts = link_frame.get("risk_link_method", pd.Series(dtype=str)).value_counts().to_dict()
    invalid_stop = int(
        (
            pd.to_numeric(link_frame.get("original_stop_price"), errors="coerce").isna()
            | pd.to_numeric(link_frame.get("original_stop_price"), errors="coerce").le(0)
        ).sum()
    )
    invalid_risk_per_contract = int(
        (
            pd.to_numeric(link_frame.get("entry_risk_per_contract"), errors="coerce").isna()
            | pd.to_numeric(link_frame.get("entry_risk_per_contract"), errors="coerce").le(0)
        ).sum()
    )
    duplicate_trade = int(link_frame.duplicated("open_trade_id", keep=False).sum())
    audit = {
        "open_trade_count": int(len(open_trades)),
        "linked_open_trade_count": int(len(link_frame)),
        "unmatched_open_trade_count": int(len(open_trades) - len(link_frame)),
        "ambiguous_direct_count": int(ambiguous_direct_count),
        "ambiguous_fallback_count": int(ambiguous_count),
        "non_next_trading_date_candidate_count": int(non_next_trading_date_candidate_count),
        "retry_without_intervening_close_count": int(retry_without_intervening_close_count),
        "duplicate_open_trade_link_count": duplicate_trade,
        "invalid_stop_price_count": invalid_stop,
        "invalid_risk_per_contract_count": invalid_risk_per_contract,
        "direct_exact_volume_next_trade_date_count": int(
            method_counts.get("direct_exact_volume_next_trade_date", 0)
        ),
        "intraday_retry_inherit_count": int(method_counts.get("intraday_retry_inherit", 0)),
        "fallback_next_trade_date_volume_mismatch_count": int(
            method_counts.get("fallback_next_trade_date_volume_mismatch", 0)
        ),
        "calendar_date_count": int(len(calendar)),
    }
    audit["entry_risk_link_audit_pass"] = bool(
        len(open_trades) > 0
        and len(link_frame) == len(open_trades)
        and ambiguous_direct_count == 0
        and ambiguous_count == 0
        and non_next_trading_date_candidate_count == 0
        and duplicate_trade == 0
        and invalid_stop == 0
        and invalid_risk_per_contract == 0
    )
    return link_frame, audit


def enrich_lots_with_entry_risk(lots: pd.DataFrame, links: pd.DataFrame) -> pd.DataFrame:
    data = lots.copy()
    data["open_trade_id"] = data["open_trade_id"].astype(str)
    link_data = links.copy()
    link_data["open_trade_id"] = link_data["open_trade_id"].astype(str)
    if link_data.duplicated("open_trade_id").any():
        raise ValueError("duplicate open_trade_id in entry-risk links")
    keep = [
        "open_trade_id",
        "entry_risk_index",
        "entry_risk_datetime",
        "entry_risk_date",
        "entry_risk_volume",
        "original_stop_price",
        "original_stop_distance",
        "entry_risk_per_contract",
        "entry_risk_actual_risk_amount",
        "entry_risk_target_risk_amount",
        "entry_risk_multiplier",
        "entry_risk_selected_volume",
        "entry_risk_size",
        "risk_link_method",
    ]
    data = data.merge(link_data[keep], on="open_trade_id", how="left", validate="many_to_one")
    data["entry_date"] = pd.to_datetime(data["entry_date"], errors="coerce").dt.normalize()
    data["exit_date"] = pd.to_datetime(data["exit_date"], errors="coerce").dt.normalize()
    for column in (
        "entry_price",
        "volume",
        "size",
        "risk_amount",
        "original_stop_price",
        "original_stop_distance",
        "entry_risk_per_contract",
    ):
        data[column] = pd.to_numeric(data[column], errors="coerce")
    data["recovered_original_risk_amount"] = data["entry_risk_per_contract"] * data["volume"]
    data["fill_to_original_stop_cash_distance"] = (
        (data["entry_price"] - data["original_stop_price"]).abs()
        * data["size"]
        * data["volume"]
    )
    data["entry_crossed_original_stop"] = (
        (data["direction"].astype(str).str.lower().eq("long") & data["original_stop_price"].ge(data["entry_price"]))
        | (data["direction"].astype(str).str.lower().eq("short") & data["original_stop_price"].le(data["entry_price"]))
    )
    if "stop_distance" in data.columns:
        existing = pd.to_numeric(data["stop_distance"], errors="coerce")
        data["existing_stop_distance_diff"] = (existing - data["original_stop_distance"]).abs()
    else:
        data["existing_stop_distance_diff"] = np.nan
    data["existing_risk_amount_diff"] = (
        data["risk_amount"] - data["recovered_original_risk_amount"]
    ).abs()
    return data


def sanitize_enriched_lots(lots: pd.DataFrame) -> pd.DataFrame:
    allowed = [
        "lot_id",
        "open_trade_id",
        "vt_symbol",
        "product",
        "direction",
        "entry_date",
        "exit_date",
        "holding_calendar_days",
        "entry_price",
        "volume",
        "size",
        "stop_distance",
        "entry_risk_index",
        "entry_risk_datetime",
        "entry_risk_date",
        "entry_risk_volume",
        "original_stop_price",
        "original_stop_distance",
        "risk_amount",
        "entry_risk_per_contract",
        "entry_risk_actual_risk_amount",
        "entry_risk_target_risk_amount",
        "entry_risk_multiplier",
        "entry_risk_selected_volume",
        "entry_risk_size",
        "risk_link_method",
        "recovered_original_risk_amount",
        "fill_to_original_stop_cash_distance",
        "entry_crossed_original_stop",
        "existing_stop_distance_diff",
        "existing_risk_amount_diff",
    ]
    return lots[[column for column in allowed if column in lots.columns]].copy()


def _risk_series(data: pd.DataFrame) -> pd.Series:
    if "recovered_original_risk_amount" in data.columns:
        return pd.to_numeric(data["recovered_original_risk_amount"], errors="coerce").fillna(0.0)
    return pd.to_numeric(data.get("risk_amount", pd.Series(0.0, index=data.index)), errors="coerce").fillna(0.0)


def build_query_events(lots: pd.DataFrame) -> pd.DataFrame:
    data = lots.copy()
    data["entry_date"] = pd.to_datetime(data["entry_date"], errors="raise").dt.normalize()
    data["exit_date"] = pd.to_datetime(data["exit_date"], errors="raise").dt.normalize()
    data["risk_for_manifest"] = _risk_series(data)
    rows: list[dict[str, Any]] = []
    for (vt_symbol, entry_date), group in data.groupby(["vt_symbol", "entry_date"], sort=True):
        lot_ids = sorted(group["lot_id"].astype(str), key=lambda value: (len(value), value))
        directions = sorted(group["direction"].astype(str).str.lower().unique())
        rows.append(
            {
                "event_id": event_id_for(str(vt_symbol), entry_date),
                "vt_symbol": str(vt_symbol),
                "tqsdk_underlying": to_tqsdk_underlying(str(vt_symbol)),
                "product_vt_symbol": _product_from_vt(vt_symbol),
                "entry_date": entry_date,
                "query_start": entry_date,
                "query_end": entry_date + pd.Timedelta(hours=23, minutes=59, seconds=59),
                "query_expired_as_of_entry": False,
                "lot_count": int(len(group)),
                "lot_ids": "|".join(lot_ids),
                "direction_count": len(directions),
                "directions": "|".join(directions),
                "total_volume": float(pd.to_numeric(group["volume"], errors="coerce").sum()),
                "total_original_risk_amount": float(group["risk_for_manifest"].sum()),
                "first_exit_date": group["exit_date"].min(),
                "last_exit_date": group["exit_date"].max(),
                "metadata_query_method": "TqApi.query_options",
                "historical_context": "TqBacktest(entry_date)",
                "metadata_query_scope": "same_underlying_active_as_of_entry",
            }
        )
    return pd.DataFrame(rows).sort_values(["entry_date", "vt_symbol"]).reset_index(drop=True)


def build_acquisition_requirements(lots: pd.DataFrame, events: pd.DataFrame) -> pd.DataFrame:
    data = lots.copy()
    data["entry_date"] = pd.to_datetime(data["entry_date"], errors="raise").dt.normalize()
    data["exit_date"] = pd.to_datetime(data["exit_date"], errors="raise").dt.normalize()
    if "original_stop_price" not in data.columns:
        raise ValueError("original_stop_price is required")
    event_keys = events[["event_id", "vt_symbol", "entry_date", "tqsdk_underlying"]].copy()
    data = data.merge(event_keys, on=["vt_symbol", "entry_date"], how="left", validate="many_to_one")
    data["direction"] = data["direction"].astype(str).str.lower()
    data["protection_option_class"] = data["direction"].map({"long": "PUT", "short": "CALL"})
    data["stop_price_anchor"] = pd.to_numeric(data["original_stop_price"], errors="coerce")
    data["risk_for_manifest"] = _risk_series(data)
    for column, default in (
        ("risk_link_method", "provided"),
        ("entry_risk_index", np.nan),
        ("entry_crossed_original_stop", False),
    ):
        if column not in data.columns:
            data[column] = default
    requirements = pd.DataFrame(
        {
            "event_id": data["event_id"],
            "lot_id": data["lot_id"].astype(str),
            "open_trade_id": data["open_trade_id"].astype(str),
            "vt_symbol": data["vt_symbol"].astype(str),
            "tqsdk_underlying": data["tqsdk_underlying"],
            "product_vt_symbol": data["vt_symbol"].map(_product_from_vt),
            "direction": data["direction"],
            "protection_option_class": data["protection_option_class"],
            "entry_date": data["entry_date"],
            "exit_date": data["exit_date"],
            "entry_price": pd.to_numeric(data["entry_price"], errors="coerce"),
            "stop_price_anchor": data["stop_price_anchor"],
            "stop_anchor_source": "entry_risk.stop_price",
            "entry_crossed_original_stop": data["entry_crossed_original_stop"].astype(bool),
            "volume": pd.to_numeric(data["volume"], errors="coerce"),
            "size": pd.to_numeric(data["size"], errors="coerce"),
            "original_risk_amount_for_coverage": data["risk_for_manifest"],
            "entry_risk_index": data["entry_risk_index"],
            "risk_link_method": data["risk_link_method"],
            "metadata_query_expired_as_of_entry": False,
            "metadata_raw_required": True,
            "metadata_normalized_required": True,
            "premium_and_liquidity_not_yet_acquired": True,
        }
    )
    return requirements.sort_values(["entry_date", "vt_symbol", "lot_id"]).reset_index(drop=True)


def audit_manifest(
    lots: pd.DataFrame, events: pd.DataFrame, requirements: pd.DataFrame
) -> dict[str, Any]:
    lot_ids = lots["lot_id"].astype(str)
    requirement_ids = requirements["lot_id"].astype(str)
    event_ids = set(events["event_id"].astype(str))
    missing_lots = set(lot_ids) - set(requirement_ids)
    extra_lots = set(requirement_ids) - set(lot_ids)
    duplicate_mapping = int(requirements.duplicated("lot_id", keep=False).sum())

    recalculated_events = events.apply(
        lambda row: event_id_for(str(row["vt_symbol"]), row["entry_date"]), axis=1
    )
    event_id_mismatch = int((recalculated_events != events["event_id"].astype(str)).sum())
    tqsdk_mismatch = int(
        (
            events.apply(lambda row: to_tqsdk_underlying(str(row["vt_symbol"])), axis=1)
            != events["tqsdk_underlying"].astype(str)
        ).sum()
    )
    option_class_expected = requirements["direction"].map({"long": "PUT", "short": "CALL"})
    option_class_error = int((option_class_expected != requirements["protection_option_class"]).sum())
    expected_stops = lots[["lot_id", "original_stop_price"]].copy()
    expected_stops["lot_id"] = expected_stops["lot_id"].astype(str)
    stop_check = requirements[["lot_id", "stop_price_anchor"]].merge(
        expected_stops, on="lot_id", how="left", validate="many_to_one"
    )
    stop_anchor_error = int(
        (~np.isclose(
            pd.to_numeric(stop_check["stop_price_anchor"], errors="coerce"),
            pd.to_numeric(stop_check["original_stop_price"], errors="coerce"),
            equal_nan=False,
        )).sum()
    )
    invalid_event_reference = int((~requirements["event_id"].astype(str).isin(event_ids)).sum())
    expired_flag_error = int(requirements["metadata_query_expired_as_of_entry"].astype(bool).sum())
    forbidden = {"realized_pnl", "winner", "r_multiple", "exit_efficiency", "entry_period_2022"}
    forbidden_count = len(forbidden & (set(events.columns) | set(requirements.columns)))

    event_rollup = requirements.groupby("event_id", as_index=False).agg(
        requirement_lot_count=("lot_id", "size"),
        requirement_total_volume=("volume", "sum"),
        requirement_total_original_risk=("original_risk_amount_for_coverage", "sum"),
    )
    event_check = events.merge(event_rollup, on="event_id", how="left", validate="one_to_one")
    event_count_error = int((event_check["lot_count"] != event_check["requirement_lot_count"]).sum())
    event_volume_error = int((~np.isclose(event_check["total_volume"], event_check["requirement_total_volume"])).sum())
    event_risk_error = int(
        (~np.isclose(
            event_check["total_original_risk_amount"],
            event_check["requirement_total_original_risk"],
        )).sum()
    )
    result = {
        "source_lot_count": int(len(lots)),
        "query_event_count": int(len(events)),
        "requirement_count": int(len(requirements)),
        "mapped_lot_count": int(requirement_ids.nunique()),
        "missing_lot_mapping_count": len(missing_lots),
        "extra_lot_mapping_count": len(extra_lots),
        "duplicate_lot_mapping_count": duplicate_mapping,
        "duplicate_event_id_count": int(events.duplicated("event_id", keep=False).sum()),
        "event_id_mismatch_count": event_id_mismatch,
        "tqsdk_underlying_mismatch_count": tqsdk_mismatch,
        "invalid_event_reference_count": invalid_event_reference,
        "protection_option_class_error_count": option_class_error,
        "stop_anchor_error_count": stop_anchor_error,
        "expired_true_error_count": expired_flag_error,
        "forbidden_selection_column_count": forbidden_count,
        "event_lot_count_reconciliation_error_count": event_count_error,
        "event_volume_reconciliation_error_count": event_volume_error,
        "event_risk_reconciliation_error_count": event_risk_error,
    }
    result["manifest_audit_pass"] = not any(
        int(result[key])
        for key in result
        if key.endswith("_count") and key not in {
            "source_lot_count",
            "query_event_count",
            "requirement_count",
            "mapped_lot_count",
        }
    )
    return result


def _data_contract() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "dataset": "event_query_status",
                "required_fields": "event_id,query_timestamp,underlying,status,message,elapsed_seconds",
                "hard_gate": "one terminal status per frozen event; no silent drops",
            },
            {
                "dataset": "untouched_option_metadata",
                "required_fields": "all API source fields plus raw epoch and source payload hash",
                "hard_gate": "raw bytes preserved before normalization; credential values absent",
            },
            {
                "dataset": "normalized_option_metadata",
                "required_fields": "option_symbol,underlying_symbol,option_class,expire_datetime,last_exercise_datetime,strike_price,expired,volume_multiple,price_tick",
                "hard_gate": "active as of entry; same underlying; normalized from hashed raw only",
            },
            {
                "dataset": "premium_liquidity",
                "required_fields": "underlying and option daily OHLCV OI; entry/exit minute OHLCV; bid/ask when historically available",
                "hard_gate": "no current quote backfill; before/after-window counts disclosed; executable price evidence required before A/B",
            },
        ]
    )


def _write_csv(frame: pd.DataFrame, path: Path) -> None:
    frame.to_csv(path, index=False, encoding="utf-8-sig")


def _write_json(payload: Mapping[str, Any], path: Path) -> None:
    path.write_text(json.dumps(_json_safe(payload), ensure_ascii=False, indent=2), encoding="utf-8")


def build_output_manifest(
    output_dir: Path,
    excluded_paths: set[Path] | None = None,
) -> pd.DataFrame:
    excluded = {Path(path) for path in (excluded_paths or set())}
    rows = []
    for path in sorted(output_dir.iterdir()):
        if not path.is_file() or path in excluded:
            continue
        rows.append({"file": path.name, "bytes": path.stat().st_size, "sha256": file_sha256(path)})
    return pd.DataFrame(rows)


def detached_checksum_line(path: Path) -> str:
    return f"{file_sha256(path)}  {path.name}\n"


def _manifest() -> pd.DataFrame:
    return build_output_manifest(
        OUTPUT_DIR,
        excluded_paths={MANIFEST_PATH, MANIFEST_CHECKSUM_PATH},
    )


def main() -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    lots, trades, entry_risk, calendar_source, inventory = load_frozen_sources()
    if "date" not in calendar_source.columns:
        raise ValueError("trading calendar source missing date")
    source_audit = audit_source_lots(lots)
    links, link_audit = build_entry_risk_links(trades, entry_risk, calendar_source["date"])
    enriched = enrich_lots_with_entry_risk(lots, links)
    events = build_query_events(enriched)
    requirements = build_acquisition_requirements(enriched, events)
    manifest_audit = audit_manifest(enriched, events, requirements)

    existing_stop = pd.to_numeric(enriched.get("stop_distance"), errors="coerce")
    existing_diff = pd.to_numeric(enriched.get("existing_stop_distance_diff"), errors="coerce")
    recovered_stop_count = int((existing_stop.isna() & enriched["original_stop_price"].notna()).sum())
    existing_stop_max_diff = float(existing_diff[existing_stop.notna()].max())
    existing_risk = pd.to_numeric(enriched["risk_amount"], errors="coerce")
    recovered_risk = pd.to_numeric(enriched["recovered_original_risk_amount"], errors="coerce")
    existing_risk_diff = pd.to_numeric(enriched["existing_risk_amount_diff"], errors="coerce")
    recovered_risk_count = int((existing_risk.isna() & recovered_risk.notna()).sum())
    existing_risk_max_diff = float(existing_risk_diff[existing_risk.notna()].max())
    product_count = int(enriched["vt_symbol"].map(_product_from_vt).nunique())
    exact_counts = {
        "closed_lot_count": int(len(lots)),
        "trade_count": int(len(trades)),
        "open_trade_count": int(trades["offset"].astype(str).eq("Open").sum()),
        "entry_risk_count": int(len(entry_risk)),
        "calendar_row_count": int(len(calendar_source)),
        "calendar_date_count": int(
            pd.to_datetime(calendar_source["date"], format="mixed", errors="raise").dt.normalize().nunique()
        ),
        "contract_count": int(enriched["vt_symbol"].nunique()),
        "query_event_count": int(len(events)),
        "entry_date_count": int(pd.to_datetime(enriched["entry_date"]).dt.normalize().nunique()),
        "product_count": product_count,
        "direct_link_count": int(link_audit["direct_exact_volume_next_trade_date_count"]),
        "retry_link_count": int(link_audit["intraday_retry_inherit_count"]),
        "fallback_mismatch_count": int(link_audit["fallback_next_trade_date_volume_mismatch_count"]),
        "existing_stop_count": int(existing_stop.notna().sum()),
        "recovered_stop_count": recovered_stop_count,
        "existing_risk_count": int(existing_risk.notna().sum()),
        "recovered_risk_count": recovered_risk_count,
    }
    count_mismatches = {
        key: {"expected": EXPECTED[key], "actual": value}
        for key, value in exact_counts.items()
        if EXPECTED[key] != value
    }
    source_hashes_ready = bool(inventory["hash_match"].all())
    ready = bool(
        source_hashes_ready
        and source_audit["source_audit_pass"]
        and link_audit["entry_risk_link_audit_pass"]
        and manifest_audit["manifest_audit_pass"]
        and not count_mismatches
        and existing_stop_max_diff == 0.0
        and existing_risk_max_diff <= 1e-8
        and recovered_risk.notna().all()
        and recovered_risk.gt(0).all()
    )
    decision = {
        "stage": "Stage131",
        "stage_id": STAGE_ID,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "decision": (
            "stage131_event_targeted_option_acquisition_manifest_ready_for_metadata_batches"
            if ready
            else "stage131_event_targeted_option_acquisition_manifest_not_ready_close"
        ),
        "ready_for_metadata_batches": ready,
        "ready_for_option_strategy_ab": False,
        "source_hashes_ready": source_hashes_ready,
        "source_audit": source_audit,
        "entry_risk_link_audit": link_audit,
        "manifest_audit": manifest_audit,
        "exact_counts": exact_counts,
        "count_mismatches": count_mismatches,
        "existing_stop_distance_max_abs_diff": existing_stop_max_diff,
        "existing_risk_amount_max_abs_diff": existing_risk_max_diff,
        "recovered_original_risk_amount_min": float(recovered_risk.min()),
        "entry_crossed_original_stop_count": int(enriched["entry_crossed_original_stop"].sum()),
        "network_called": False,
        "tqsdk_imported": False,
        "metadata_downloaded": False,
        "premium_downloaded": False,
        "strategy_rule_created": False,
        "true_engine_run": False,
        "order_api_called_count": 0,
        "ctp_connected": False,
        "credential_values_accessed": False,
        "outcome_columns_read": False,
        "outcome_columns_persisted": False,
        "manifest_detached_checksum_required": True,
        "manifest_detached_checksum_path": str(MANIFEST_CHECKSUM_PATH),
        "official_live_strategy_changed": False,
        "overfit_before": "否；冻结全量基准事件，不读取结果标签。",
        "overfit_after": "待独立审查；不得把 manifest ready 解释成期权有效。",
        "continue_value_before": "有；把 Stage130 单点能力转成完整可执行请求边界。",
        "continue_value_after": (
            "有；只允许进入冻结 metadata batches。" if ready else "无；按预声明关闭，不删事件救清单。"
        ),
    }

    year_summary = (
        requirements.assign(entry_year=pd.to_datetime(requirements["entry_date"]).dt.year)
        .groupby("entry_year", as_index=False)
        .agg(
            lot_count=("lot_id", "size"),
            query_event_count=("event_id", "nunique"),
            contract_count=("vt_symbol", "nunique"),
            product_count=("product_vt_symbol", "nunique"),
            total_volume=("volume", "sum"),
            total_original_risk_amount=("original_risk_amount_for_coverage", "sum"),
            crossed_stop_count=("entry_crossed_original_stop", "sum"),
        )
    )
    product_summary = (
        requirements.groupby("product_vt_symbol", as_index=False)
        .agg(
            lot_count=("lot_id", "size"),
            query_event_count=("event_id", "nunique"),
            contract_count=("vt_symbol", "nunique"),
            first_entry_date=("entry_date", "min"),
            last_entry_date=("entry_date", "max"),
            total_volume=("volume", "sum"),
            total_original_risk_amount=("original_risk_amount_for_coverage", "sum"),
        )
        .sort_values("product_vt_symbol")
    )
    data_contract = _data_contract()

    _write_csv(inventory, SOURCE_INVENTORY_PATH)
    _write_csv(pd.DataFrame([source_audit]), SOURCE_AUDIT_PATH)
    _write_csv(links, ENTRY_RISK_LINKS_PATH)
    _write_csv(pd.DataFrame([link_audit]), ENTRY_RISK_LINK_AUDIT_PATH)
    _write_csv(sanitize_enriched_lots(enriched), ENRICHED_LOTS_PATH)
    _write_csv(events, QUERY_EVENTS_PATH)
    _write_csv(requirements, REQUIREMENTS_PATH)
    _write_csv(pd.DataFrame([manifest_audit]), MANIFEST_AUDIT_PATH)
    _write_csv(year_summary, YEAR_SUMMARY_PATH)
    _write_csv(product_summary, PRODUCT_SUMMARY_PATH)
    _write_csv(data_contract, DATA_CONTRACT_PATH)
    _write_json(decision, DECISION_PATH)

    lineage = {
        "stage": "Stage131",
        "tool": {"path": str(TOOL_PATH), "sha256": file_sha256(TOOL_PATH)},
        "test": {"path": str(TEST_PATH), "sha256": file_sha256(TEST_PATH)},
        "predecl": {"path": str(PREDECL_PATH), "sha256": file_sha256(PREDECL_PATH)},
        "sources": {
            row.source_name: {
                "path": row.path,
                "rows": int(row.rows),
                "bytes": int(row.bytes),
                "sha256": row.sha256,
            }
            for row in inventory.itertuples(index=False)
        },
        "history_database_snapshot_complete": False,
        "metadata_not_downloaded": True,
        "premium_not_downloaded": True,
    }
    _write_json(lineage, LINEAGE_PATH)

    report_lines = [
        "# Stage131 当前 C9 真实事件定向期权采集清单",
        "",
        f"- 决策：`{decision['decision']}`",
        "- 本阶段只生成 acquisition manifest，不联网、不下载期权、不回测收益。",
        f"- 冻结 lots/open trades/query events：`{len(lots)}/{exact_counts['open_trade_count']}/{len(events)}`",
        f"- entry-risk 关联：`{len(links)}/{exact_counts['open_trade_count']}`；缺失 stop 恢复 `{recovered_stop_count}`。",
        f"- 原风险金额：已有 `{int(existing_risk.notna().sum())}` 条最大差 `{existing_risk_max_diff:.3g}`，缺失恢复 `{recovered_risk_count}` 条；coverage 权重使用 risk_per_contract × lot volume。",
        f"- 原止损已被成交价跨越：`{decision['entry_crossed_original_stop_count']}` 条，保留原 stop_price，不反推。",
        "",
        "## Source Audit",
        "",
        _md_table(pd.DataFrame([source_audit])),
        "",
        "## Entry-Risk Link Audit",
        "",
        _md_table(pd.DataFrame([link_audit])),
        "",
        "## Manifest Audit",
        "",
        _md_table(pd.DataFrame([manifest_audit])),
        "",
        "## Entry-Year Summary",
        "",
        _md_table(year_summary),
        "",
        "## Product Summary",
        "",
        _md_table(product_summary),
        "",
        "## Data Contract",
        "",
        _md_table(data_contract),
        "",
        "## 边界",
        "",
        "- `ready_for_metadata_batches` 只表示 365 个历史查询请求已经冻结且账本闭合。",
        "- 当前没有 option metadata、premium、成交量/OI 或分钟成交覆盖，`ready_for_option_strategy_ab=false`。",
        "- Stage131 输出不持久化 realized_pnl、R、winner、MFE/MAE 或 2022 结果标签。",
        "- 四个冻结源均按 usecols 白名单读取；资金曲线只读 date，closed lots 不解析收益标签。",
        "- 过拟合：否；全量事件无结果筛选。继续价值：仅限按冻结清单分批获取 metadata。",
    ]
    REPORT_PATH.write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    _write_csv(_manifest(), MANIFEST_PATH)
    MANIFEST_CHECKSUM_PATH.write_text(
        detached_checksum_line(MANIFEST_PATH),
        encoding="ascii",
    )
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    return decision


if __name__ == "__main__":
    main()
