from __future__ import annotations

import ast
from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
from io import StringIO
import json
import math
from numbers import Integral, Real
import os
from pathlib import Path
import re
import shutil
import signal
import tempfile
import time
from typing import Any, Callable, Mapping
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd


ROOT_DIR = Path(__file__).resolve().parents[4]
LINE_ID = "futures_trend_rebuilt_c9_15w_v2_optimization"
STAGE_ID = "stage133_c9_2022_extracted_event_market_data_readiness"
LINE_ROOT = ROOT_DIR / "research" / "lines" / LINE_ID
STAGE131_OUTPUT_DIR = (
    LINE_ROOT / "outputs" / "stage131_c9_event_targeted_option_acquisition_manifest"
)
STAGE132_OUTPUT_DIR = LINE_ROOT / "outputs" / "stage132_c9_event_option_metadata_batches"
STAGE132_ATTEMPTS_ROOT = STAGE132_OUTPUT_DIR / "event_attempts"

TERMINAL_STATUS_PATH = STAGE132_OUTPUT_DIR / (
    "rebuilt_c9_v2_stage132_c9_event_option_metadata_batches_"
    "event_terminal_status_stage132_c9_event_option_metadata_batches_v1.csv"
)
ACQUISITION_REQUIREMENTS_PATH = STAGE131_OUTPUT_DIR / (
    "rebuilt_c9_v2_stage131_c9_event_targeted_option_acquisition_manifest_"
    "acquisition_requirements_stage131_c9_event_targeted_option_acquisition_manifest_v1.csv"
)
ENTRY_RISK_LINKS_PATH = STAGE131_OUTPUT_DIR / (
    "rebuilt_c9_v2_stage131_c9_event_targeted_option_acquisition_manifest_"
    "entry_risk_links_stage131_c9_event_targeted_option_acquisition_manifest_v1.csv"
)

TERMINAL_STATUS_SHA256 = "c8361cbfb38007fda953730bdfff2a868a765b4ab114422ab853b963917f4b05"
ACQUISITION_REQUIREMENTS_SHA256 = "13a01cd1a7b88d6b66fabc137cad73f19b01a9a0a6e335edbe1fe68f5f6089bf"
ENTRY_RISK_LINKS_SHA256 = "22e397ffe8a3c00e5da1614db12deecc134b7c884edaecd25297a845a2891e7e"

STAGE132_METADATA_COVERED_EVENT_COUNT = 123
STAGE132_TOTAL_EVENT_COUNT = 365
STAGE132_METADATA_COVERAGE_RATIO = (
    STAGE132_METADATA_COVERED_EVENT_COUNT / STAGE132_TOTAL_EVENT_COUNT
)
STAGE132_2022_COVERED_EVENT_COUNT = 11
STAGE132_2022_TOTAL_EVENT_COUNT = 48
STAGE132_2022_CORE_RISK_COVERAGE_RATIO = 0.26461965

CORE_WINDOW_START = pd.Timestamp("2022-03-09")
CORE_WINDOW_END = pd.Timestamp("2022-06-29")
CHINA_TZ = ZoneInfo("Asia/Shanghai")

OUTPUT_DIR = LINE_ROOT / "outputs" / STAGE_ID
ATTEMPTS_ROOT = OUTPUT_DIR / "event_attempts"
TOOL_PATH = Path(__file__).resolve()
TEST_PATH = (
    ROOT_DIR
    / "tests"
    / "test_rebuilt_c9_v2_stage133_c9_2022_extracted_event_market_data_readiness.py"
)
PREDECL_PATH = LINE_ROOT / "stages" / (
    "20260711_1611_stage133_c9_2022_extracted_event_market_data_readiness_predecl.md"
)
IMPLEMENTATION_PLAN_PATH = LINE_ROOT / "stages" / (
    "20260711_1613_stage133_c9_2022_extracted_event_market_data_readiness_implementation_plan.md"
)

ATTEMPT_REQUEST_NAME = "request.json"
ATTEMPT_STATUS_NAME = "status.json"
ATTEMPT_SCHEMA_NAME = "schema.json"
SELECTION_CANDIDATES_NAME = "selection_candidates.csv"
SELECTION_AUDIT_NAME = "selection_audit.json"
RAW_UNDERLYING_MINUTE_NAME = "raw_underlying_minute.csv"
RAW_OPTION_MINUTE_NAME = "raw_option_minute.csv"
RAW_OPTION_TICK_NAME = "raw_option_tick.csv"
NORMALIZED_UNDERLYING_MINUTE_NAME = "normalized_underlying_minute.csv"
NORMALIZED_OPTION_MINUTE_NAME = "normalized_option_minute.csv"
NORMALIZED_OPTION_TICK_NAME = "normalized_option_tick.csv"
ATTEMPT_MANIFEST_NAME = "manifest.csv"
ATTEMPT_CHECKSUM_NAME = "manifest.sha256"

BASE_EVIDENCE_FILES = (
    ATTEMPT_REQUEST_NAME,
    ATTEMPT_STATUS_NAME,
    SELECTION_CANDIDATES_NAME,
    SELECTION_AUDIT_NAME,
)

EXTRACTED_DATA_FILES = (
    RAW_UNDERLYING_MINUTE_NAME,
    RAW_OPTION_MINUTE_NAME,
    RAW_OPTION_TICK_NAME,
    NORMALIZED_UNDERLYING_MINUTE_NAME,
    NORMALIZED_OPTION_MINUTE_NAME,
    NORMALIZED_OPTION_TICK_NAME,
    ATTEMPT_SCHEMA_NAME,
)
DATA_EVIDENCE_TERMINALS = {"extracted", "integrity_failed"}
ALL_TERMINALS = {
    "extracted",
    "authentication_failed",
    "timeout",
    "query_failed",
    "integrity_failed",
}

EXPECTED_EVENT_IDS = (
    "2424ec63fd31887211f99761200188b2ad2a0afb482997c9d8ad65a4081f3d39",
    "9df8755883c082095fd03b87ab99734546df9b375453c82e1f2088871f20db98",
    "d90db2cbffbbe58a48be41bdeb736aa0056f404709d2bb47230eab9a25805cb8",
    "bb6d3275a518d933758ae3dfec300685616b6f48ae86c11e5d61e41c7e40c9c3",
)
EXPECTED_OPTION_SYMBOLS = (
    "CZCE.MA209C2700",
    "SHFE.au2206P400",
    "CZCE.MA209C2700",
    "CZCE.MA209P2900",
)
EXPECTED_METADATA_SHA256 = {
    EXPECTED_EVENT_IDS[0]: "8abaab130972e6c137132372e9243b4661ea0e1a2abdd9532af336ea1e7285a8",
    EXPECTED_EVENT_IDS[1]: "505f55ee5cb479082f6b3737f91470d12b35f2439ed75cdba3c6d16a6908a038",
    EXPECTED_EVENT_IDS[2]: "7d552cb7f365101991f45753c4c5011927743f47b67e67756fce9a949e5fd03f",
    EXPECTED_EVENT_IDS[3]: "caf2e7c60d5ee08307fdd78b273f6fa98197a3f75d8590a02ddaab47f5666538",
}


class IntegrityError(RuntimeError):
    pass


@dataclass(frozen=True)
class FetchPayload:
    terminal_status: str
    underlying_minute: pd.DataFrame
    option_minute: pd.DataFrame
    option_tick: pd.DataFrame
    audit: dict[str, Any]
    message: str
    elapsed_seconds: float
    network_called: bool


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_csv(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    frame.columns = [str(column).lstrip("\ufeff") for column in frame.columns]
    return frame


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes"}


def select_probe_option(
    metadata: pd.DataFrame,
    *,
    option_class: str,
    entry_price: float,
    entry_date: pd.Timestamp,
) -> dict[str, Any]:
    candidates = build_selection_candidates(
        metadata,
        option_class=option_class,
        entry_price=entry_price,
        entry_date=entry_date,
    )
    return candidates.iloc[0].drop(labels=["rank", "distance_to_entry", "selected"]).to_dict()


def build_selection_candidates(
    metadata: pd.DataFrame,
    *,
    option_class: str,
    entry_price: float,
    entry_date: pd.Timestamp,
) -> pd.DataFrame:
    required = {"option_symbol", "option_class", "expire_datetime", "strike_price"}
    missing = sorted(required - set(metadata.columns))
    if missing:
        raise IntegrityError(f"metadata missing columns: {missing}")

    data = metadata.copy()
    data["_expiry"] = pd.to_datetime(data["expire_datetime"], errors="coerce")
    data["_strike"] = pd.to_numeric(data["strike_price"], errors="coerce")
    cutoff = pd.Timestamp(entry_date).normalize() + pd.Timedelta(days=1)
    data = data[
        data["option_class"].astype(str).str.upper().eq(str(option_class).upper())
        & data["_expiry"].ge(cutoff)
        & data["_strike"].notna()
        & np.isfinite(data["_strike"])
    ].copy()
    if data.empty:
        raise IntegrityError("no unexpired option in required protection class")

    first_expiry = data["_expiry"].min()
    data = data[data["_expiry"].eq(first_expiry)].copy()
    data["_distance"] = (data["_strike"] - float(entry_price)).abs()
    ranked = data.sort_values(
        ["_distance", "_strike", "option_symbol"], kind="mergesort"
    ).reset_index(drop=True)
    ranked["rank"] = np.arange(1, len(ranked) + 1, dtype=int)
    ranked["selected"] = ranked["rank"].eq(1)
    ranked["distance_to_entry"] = ranked["_distance"]
    ranked["strike_price"] = ranked["_strike"]
    ranked["expire_datetime"] = ranked["_expiry"].map(
        lambda value: value.isoformat()
    )
    columns = [
        "rank",
        "option_symbol",
        "option_class",
        "expire_datetime",
        "strike_price",
        "distance_to_entry",
        "selected",
    ]
    if "underlying_symbol" in ranked.columns:
        columns.insert(2, "underlying_symbol")
    return ranked[columns].copy()


def _verify_hash(path: Path, expected: str, label: str) -> None:
    if not path.is_file():
        raise IntegrityError(f"{label} missing: {path}")
    actual = file_sha256(path)
    if actual != expected:
        raise IntegrityError(f"{label} sha256 mismatch: {actual} != {expected}")


def load_frozen_probe_plan(
    *, expected_terminal_sha256: str = TERMINAL_STATUS_SHA256
) -> pd.DataFrame:
    _verify_hash(TERMINAL_STATUS_PATH, expected_terminal_sha256, "terminal status")
    _verify_hash(
        ACQUISITION_REQUIREMENTS_PATH,
        ACQUISITION_REQUIREMENTS_SHA256,
        "acquisition requirements",
    )
    _verify_hash(ENTRY_RISK_LINKS_PATH, ENTRY_RISK_LINKS_SHA256, "entry risk links")

    terminal = _read_csv(TERMINAL_STATUS_PATH)
    terminal["entry_date"] = pd.to_datetime(terminal["entry_date"], errors="coerce")
    selected_events = terminal[
        terminal["entry_date"].between(CORE_WINDOW_START, CORE_WINDOW_END)
        & terminal["terminal_status"].eq("extracted")
        & terminal["cacheable"].map(_as_bool)
    ].copy()
    selected_events = selected_events.sort_values(
        ["entry_date", "event_id"], kind="mergesort"
    ).reset_index(drop=True)
    if tuple(selected_events["event_id"]) != EXPECTED_EVENT_IDS:
        raise IntegrityError("extracted core-window event set drift")

    requirements = _read_csv(ACQUISITION_REQUIREMENTS_PATH)
    requirements = requirements[requirements["event_id"].isin(EXPECTED_EVENT_IDS)].copy()
    if len(requirements) != 6:
        raise IntegrityError(f"expected 6 frozen lots, got {len(requirements)}")

    plan_rows: list[dict[str, Any]] = []
    for event in selected_events.to_dict("records"):
        event_id = str(event["event_id"])
        lots = requirements[requirements["event_id"].eq(event_id)].copy()
        directions = sorted(lots["direction"].dropna().astype(str).str.lower().unique())
        classes = sorted(lots["protection_option_class"].dropna().astype(str).str.upper().unique())
        entry_prices = pd.to_numeric(lots["entry_price"], errors="coerce").dropna().unique()
        if len(directions) != 1 or len(classes) != 1 or len(entry_prices) != 1:
            raise IntegrityError(f"ambiguous direction/class/entry for {event_id}")
        expected_class = "PUT" if directions[0] == "long" else "CALL" if directions[0] == "short" else ""
        if classes[0] != expected_class:
            raise IntegrityError(f"protection class mismatch for {event_id}")

        attempt_path = Path(str(event["attempt_path"])).resolve()
        expected_attempt_root = (STAGE132_ATTEMPTS_ROOT / event_id).resolve()
        if expected_attempt_root not in attempt_path.parents:
            raise IntegrityError(f"metadata attempt escaped event root for {event_id}")
        metadata_path = attempt_path / "normalized_metadata.csv"
        expected_metadata_sha = EXPECTED_METADATA_SHA256[event_id]
        _verify_hash(metadata_path, expected_metadata_sha, f"metadata {event_id}")
        metadata = _read_csv(metadata_path)
        selected = select_probe_option(
            metadata,
            option_class=expected_class,
            entry_price=float(entry_prices[0]),
            entry_date=pd.Timestamp(event["entry_date"]),
        )
        entry_date = pd.Timestamp(event["entry_date"]).normalize()
        plan_rows.append(
            {
                "event_id": event_id,
                "vt_symbol": str(event["vt_symbol"]),
                "tqsdk_underlying": str(event["tqsdk_underlying"]),
                "entry_date": entry_date.date().isoformat(),
                "direction": directions[0],
                "protection_option_class": expected_class,
                "entry_price": float(entry_prices[0]),
                "lot_count": int(len(lots)),
                "option_symbol": str(selected["option_symbol"]),
                "option_strike": float(selected["strike_price"]),
                "option_expire_datetime": str(selected["expire_datetime"]),
                "metadata_path": str(metadata_path),
                "metadata_sha256": expected_metadata_sha,
                "session_start": (
                    entry_date - pd.Timedelta(days=1) + pd.Timedelta(hours=20)
                ).strftime("%Y-%m-%d %H:%M:%S"),
                "session_end": (entry_date + pd.Timedelta(hours=16)).strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
            }
        )

    plan = pd.DataFrame(plan_rows)
    audit = audit_probe_plan(plan)
    if not audit["probe_plan_audit_pass"]:
        raise IntegrityError(f"probe plan audit failed: {audit}")
    return plan


def audit_probe_plan(plan: pd.DataFrame) -> dict[str, Any]:
    event_ids = tuple(plan.get("event_id", pd.Series(dtype=str)).astype(str))
    option_symbols = tuple(plan.get("option_symbol", pd.Series(dtype=str)).astype(str))
    event_count = int(len(plan))
    lot_count = int(pd.to_numeric(plan.get("lot_count"), errors="coerce").sum())
    unique_event_count = int(plan.get("event_id", pd.Series(dtype=str)).nunique())
    mapping_errors = 0
    for row in plan.to_dict("records"):
        expected = "PUT" if row.get("direction") == "long" else "CALL"
        if row.get("protection_option_class") != expected:
            mapping_errors += 1
    passed = bool(
        event_count == 4
        and unique_event_count == 4
        and lot_count == 6
        and event_ids == EXPECTED_EVENT_IDS
        and option_symbols == EXPECTED_OPTION_SYMBOLS
        and mapping_errors == 0
    )
    return {
        "event_count": event_count,
        "unique_event_count": unique_event_count,
        "lot_count": lot_count,
        "direction_class_mapping_error_count": mapping_errors,
        "expected_event_set_match": event_ids == EXPECTED_EVENT_IDS,
        "expected_option_symbols_match": option_symbols == EXPECTED_OPTION_SYMBOLS,
        "probe_plan_audit_pass": passed,
    }


def _china_timestamp(value: Any) -> pd.Timestamp:
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is None:
        return timestamp.tz_localize(CHINA_TZ)
    return timestamp.tz_convert(CHINA_TZ)


def _parse_market_datetime(value: Any) -> pd.Timestamp:
    if pd.isna(value):
        return pd.NaT
    if isinstance(value, (pd.Timestamp,)):
        timestamp = value
    else:
        if isinstance(value, Integral):
            numeric: int | float = int(value)
        elif isinstance(value, Real):
            numeric = float(value)
        elif re.fullmatch(r"[+-]?\d+", str(value).strip()):
            numeric = int(str(value).strip())
        else:
            timestamp = pd.to_datetime(value, errors="coerce", utc=True)
            numeric = None
        if numeric is not None:
            magnitude = abs(numeric)
            if magnitude >= 1e17:
                unit = "ns"
            elif magnitude >= 1e14:
                unit = "us"
            elif magnitude >= 1e11:
                unit = "ms"
            else:
                unit = "s"
            timestamp = pd.to_datetime(numeric, unit=unit, errors="coerce", utc=True)
    if pd.isna(timestamp):
        return pd.NaT
    timestamp = pd.Timestamp(timestamp)
    if timestamp.tzinfo is None:
        timestamp = timestamp.tz_localize("UTC")
    return timestamp.tz_convert(CHINA_TZ)


def normalize_market_frame(
    frame: pd.DataFrame, start: Any, end: Any
) -> pd.DataFrame:
    if "datetime" not in frame.columns:
        raise IntegrityError("market frame missing datetime")
    normalized = frame.copy(deep=True)
    parsed = normalized["datetime"].map(_parse_market_datetime)
    parsed = pd.Series(
        pd.DatetimeIndex(parsed), index=normalized.index, name="datetime_beijing"
    )
    start_ts = _china_timestamp(start)
    end_ts = _china_timestamp(end)
    if end_ts < start_ts:
        raise IntegrityError("session end precedes start")
    normalized["datetime_beijing"] = parsed
    normalized["in_session_window"] = (
        parsed.notna() & parsed.ge(start_ts) & parsed.le(end_ts)
    )
    return normalized


def _missing_columns(frame: pd.DataFrame, required: set[str]) -> list[str]:
    return sorted(required - set(frame.columns))


def _populated_without_datetime(frame: pd.DataFrame) -> int:
    source_columns = [
        column
        for column in frame.columns
        if column not in {"datetime", "datetime_beijing", "in_session_window"}
    ]
    if not source_columns:
        return 0
    populated = frame[source_columns].notna().any(axis=1)
    return int((frame["datetime_beijing"].isna() & populated).sum())


def _minute_audit(frame: pd.DataFrame, prefix: str, start: Any, end: Any) -> dict[str, Any]:
    required = {
        "datetime",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "open_oi",
        "close_oi",
    }
    missing = _missing_columns(frame, required)
    if missing:
        return {
            f"{prefix}_raw_row_count": int(len(frame)),
            f"{prefix}_session_row_count": 0,
            f"{prefix}_missing_columns": "|".join(missing),
            f"{prefix}_malformed_datetime_count": 0,
            f"{prefix}_duplicate_timestamp_count": 0,
            f"{prefix}_ohlc_missing_count": 0,
            f"{prefix}_ohlc_relation_error_count": 0,
            f"{prefix}_negative_volume_count": 0,
            f"{prefix}_negative_oi_count": 0,
            f"{prefix}_infinite_numeric_count": 0,
            f"{prefix}_integrity_pass": False,
            f"_{prefix}_normalized": None,
        }
    normalized = normalize_market_frame(frame, start, end)
    session = normalized[normalized["in_session_window"]].copy()
    for column in ("open", "high", "low", "close", "volume", "open_oi", "close_oi"):
        session[column] = pd.to_numeric(session[column], errors="coerce")
    duplicate = int(session.duplicated(["datetime_beijing"], keep=False).sum())
    missing_ohlc = int(session[["open", "high", "low", "close"]].isna().any(axis=1).sum())
    relation_error = int(
        (
            session["high"].lt(session[["open", "low", "close"]].max(axis=1))
            | session["low"].gt(session[["open", "high", "close"]].min(axis=1))
        ).sum()
    )
    negative_volume = int(session["volume"].lt(0).sum())
    negative_oi = int(session[["open_oi", "close_oi"]].lt(0).sum().sum())
    infinite_numeric = int(
        np.isinf(
            session[
                ["open", "high", "low", "close", "volume", "open_oi", "close_oi"]
            ].to_numpy(dtype=float)
        ).sum()
    )
    malformed_datetime = _populated_without_datetime(normalized)
    integrity = bool(
        not missing
        and malformed_datetime == 0
        and duplicate == 0
        and missing_ohlc == 0
        and relation_error == 0
        and negative_volume == 0
        and negative_oi == 0
        and infinite_numeric == 0
    )
    return {
        f"{prefix}_raw_row_count": int(len(frame)),
        f"{prefix}_session_row_count": int(len(session)),
        f"{prefix}_outside_session_row_count": int(
            normalized["datetime_beijing"].notna().sum() - len(session)
        ),
        f"{prefix}_padding_row_count": int(
            normalized.drop(columns=["datetime_beijing", "in_session_window"])
            .isna()
            .all(axis=1)
            .sum()
        ),
        f"{prefix}_missing_columns": "",
        f"{prefix}_malformed_datetime_count": malformed_datetime,
        f"{prefix}_duplicate_timestamp_count": duplicate,
        f"{prefix}_ohlc_missing_count": missing_ohlc,
        f"{prefix}_ohlc_relation_error_count": relation_error,
        f"{prefix}_negative_volume_count": negative_volume,
        f"{prefix}_negative_oi_count": negative_oi,
        f"{prefix}_infinite_numeric_count": infinite_numeric,
        f"{prefix}_first_session_datetime": (
            session["datetime_beijing"].min().isoformat() if len(session) else ""
        ),
        f"{prefix}_last_session_datetime": (
            session["datetime_beijing"].max().isoformat() if len(session) else ""
        ),
        f"{prefix}_integrity_pass": integrity,
        f"_{prefix}_normalized": normalized,
    }


def _tick_audit(frame: pd.DataFrame, start: Any, end: Any) -> dict[str, Any]:
    required = {
        "datetime",
        "last_price",
        "ask_price1",
        "ask_volume1",
        "bid_price1",
        "bid_volume1",
        "volume",
        "open_interest",
    }
    missing = _missing_columns(frame, required)
    if missing:
        return {
            "tick_raw_row_count": int(len(frame)),
            "tick_session_row_count": 0,
            "tick_missing_columns": "|".join(missing),
            "tick_malformed_datetime_count": 0,
            "tick_duplicate_timestamp_count": 0,
            "tick_negative_quote_volume_count": 0,
            "tick_negative_volume_count": 0,
            "tick_negative_oi_count": 0,
            "tick_crossed_spread_count": 0,
            "tick_infinite_numeric_count": 0,
            "tick_cumulative_volume_decrease_count": 0,
            "tick_integrity_pass": False,
            "_tick_normalized": None,
            "_tick_session": pd.DataFrame(),
        }
    normalized = normalize_market_frame(frame, start, end)
    session = normalized[normalized["in_session_window"]].copy()
    numeric_columns = [
        "last_price",
        "ask_price1",
        "ask_volume1",
        "bid_price1",
        "bid_volume1",
        "volume",
        "open_interest",
    ]
    for column in numeric_columns:
        session[column] = pd.to_numeric(session[column], errors="coerce")
    session = session.sort_values("datetime_beijing", kind="mergesort").reset_index(
        drop=True
    )
    duplicate = int(session.duplicated(["datetime_beijing"], keep=False).sum())
    malformed_datetime = _populated_without_datetime(normalized)
    negative_quote_volume = int(
        session[["ask_volume1", "bid_volume1"]].lt(0).sum().sum()
    )
    negative_volume = int(session["volume"].lt(0).sum())
    negative_oi = int(session["open_interest"].lt(0).sum())
    infinite_numeric = int(
        np.isinf(session[numeric_columns].to_numpy(dtype=float)).sum()
    )
    finite_volume = session.loc[
        np.isfinite(session["volume"].to_numpy(dtype=float)), "volume"
    ]
    cumulative_volume_decrease = int(finite_volume.diff().lt(0).sum())
    positive_bid_ask = session["bid_price1"].gt(0) & session["ask_price1"].gt(0)
    crossed = int(
        (positive_bid_ask & session["ask_price1"].lt(session["bid_price1"])).sum()
    )
    integrity = bool(
        not missing
        and malformed_datetime == 0
        and duplicate == 0
        and negative_quote_volume == 0
        and negative_volume == 0
        and negative_oi == 0
        and crossed == 0
        and infinite_numeric == 0
        and cumulative_volume_decrease == 0
    )
    return {
        "tick_raw_row_count": int(len(frame)),
        "tick_session_row_count": int(len(session)),
        "tick_outside_session_row_count": int(
            normalized["datetime_beijing"].notna().sum() - len(session)
        ),
        "tick_padding_row_count": int(
            normalized.drop(columns=["datetime_beijing", "in_session_window"])
            .isna()
            .all(axis=1)
            .sum()
        ),
        "tick_missing_columns": "",
        "tick_malformed_datetime_count": malformed_datetime,
        "tick_duplicate_timestamp_count": duplicate,
        "tick_negative_quote_volume_count": negative_quote_volume,
        "tick_negative_volume_count": negative_volume,
        "tick_negative_oi_count": negative_oi,
        "tick_crossed_spread_count": crossed,
        "tick_infinite_numeric_count": infinite_numeric,
        "tick_cumulative_volume_decrease_count": cumulative_volume_decrease,
        "tick_first_session_datetime": (
            session["datetime_beijing"].min().isoformat() if len(session) else ""
        ),
        "tick_last_session_datetime": (
            session["datetime_beijing"].max().isoformat() if len(session) else ""
        ),
        "tick_integrity_pass": integrity,
        "_tick_normalized": normalized,
        "_tick_session": session,
    }


def _finite_or_nan(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return float("nan")
    return number if math.isfinite(number) else float("nan")


def audit_event_market_data(
    underlying_minute: pd.DataFrame,
    option_minute: pd.DataFrame,
    option_tick: pd.DataFrame,
    start: Any,
    end: Any,
) -> dict[str, Any]:
    underlying_audit = _minute_audit(
        underlying_minute, "underlying_minute", start, end
    )
    option_audit = _minute_audit(option_minute, "option_minute", start, end)
    tick_audit = _tick_audit(option_tick, start, end)

    option_normalized = option_audit.pop("_option_minute_normalized")
    underlying_audit.pop("_underlying_minute_normalized")
    tick_audit.pop("_tick_normalized")
    tick_session = tick_audit.pop("_tick_session")
    option_session = (
        option_normalized[option_normalized["in_session_window"]].copy()
        if isinstance(option_normalized, pd.DataFrame)
        else pd.DataFrame()
    )
    if not option_session.empty:
        for column in ("close", "volume", "open_oi", "close_oi"):
            option_session[column] = pd.to_numeric(option_session[column], errors="coerce")

    premium_observed = bool(
        not option_session.empty
        and (
            np.isfinite(option_session["close"].to_numpy(dtype=float))
            & option_session["close"].gt(0).to_numpy()
        ).any()
    )
    oi_observed = bool(
        not option_session.empty
        and (
            (
                np.isfinite(option_session["open_oi"].to_numpy(dtype=float))
                & option_session["open_oi"].ge(0).to_numpy()
            ).any()
            or (
                np.isfinite(option_session["close_oi"].to_numpy(dtype=float))
                & option_session["close_oi"].ge(0).to_numpy()
            ).any()
        )
    )
    tick_price_observed = bool(
        not tick_session.empty
        and (
            np.isfinite(tick_session["last_price"].to_numpy(dtype=float))
            & tick_session["last_price"].gt(0).to_numpy()
        ).any()
    )
    two_sided = (
        np.isfinite(
            tick_session[
                ["bid_price1", "ask_price1", "bid_volume1", "ask_volume1"]
            ].to_numpy(dtype=float)
        ).all(axis=1)
        & tick_session["bid_price1"].gt(0)
        & tick_session["ask_price1"].gt(0)
        & tick_session["ask_price1"].ge(tick_session["bid_price1"])
        & tick_session["bid_volume1"].ge(0)
        & tick_session["ask_volume1"].ge(0)
        if not tick_session.empty
        else pd.Series(dtype=bool)
    )
    two_sided_spread_observed = bool(two_sided.any())

    tick_volume = (
        pd.to_numeric(tick_session["volume"], errors="coerce")
        .dropna()
        if not tick_session.empty
        else pd.Series(dtype=float)
    )
    tick_volume_first = _finite_or_nan(tick_volume.iloc[0]) if len(tick_volume) else float("nan")
    tick_volume_last = _finite_or_nan(tick_volume.iloc[-1]) if len(tick_volume) else float("nan")
    tick_volume_change = (
        tick_volume_last - tick_volume_first
        if math.isfinite(tick_volume_first) and math.isfinite(tick_volume_last)
        else float("nan")
    )
    positive_trade_observed = bool(
        (
            not option_session.empty
            and (
                np.isfinite(option_session["volume"].to_numpy(dtype=float))
                & option_session["volume"].gt(0).to_numpy()
            ).any()
        )
        or (math.isfinite(tick_volume_change) and tick_volume_change > 0)
    )
    market_data_integrity_pass = bool(
        underlying_audit["underlying_minute_integrity_pass"]
        and option_audit["option_minute_integrity_pass"]
        and tick_audit["tick_integrity_pass"]
    )
    all_fields_observed = bool(
        premium_observed
        and oi_observed
        and tick_price_observed
        and two_sided_spread_observed
        and positive_trade_observed
        and market_data_integrity_pass
    )
    return {
        **underlying_audit,
        **option_audit,
        **tick_audit,
        "premium_observed": premium_observed,
        "oi_observed": oi_observed,
        "tick_price_observed": tick_price_observed,
        "two_sided_spread_observed": two_sided_spread_observed,
        "positive_trade_observed": positive_trade_observed,
        "tick_volume_first": tick_volume_first,
        "tick_volume_last": tick_volume_last,
        "tick_volume_change": tick_volume_change,
        "all_fields_observed": all_fields_observed,
        "market_data_integrity_pass": market_data_integrity_pass,
    }


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if hasattr(value, "item"):
        return _json_safe(value.item())
    if pd.isna(value):
        return None
    return value


def _redact_message(value: Any, secrets: list[str] | tuple[str, ...]) -> str:
    message = str(value)
    for secret in secrets:
        if secret:
            message = message.replace(secret, "<redacted>")
    return message


def _atomic_write_bytes(path: Path, payload: bytes) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_bytes(payload)
    os.replace(temporary, path)


def _write_json(path: Path, payload: Any) -> None:
    encoded = (
        json.dumps(_json_safe(payload), ensure_ascii=False, indent=2, sort_keys=True)
        + "\n"
    ).encode("utf-8")
    _atomic_write_bytes(path, encoded)


def _csv_bytes(frame: pd.DataFrame) -> bytes:
    buffer = StringIO()
    frame.to_csv(buffer, index=False, lineterminator="\n")
    return buffer.getvalue().encode("utf-8-sig")


def _write_csv(path: Path, frame: pd.DataFrame) -> None:
    _atomic_write_bytes(path, _csv_bytes(frame))


def _serialize_normalized(frame: pd.DataFrame, start: Any, end: Any) -> pd.DataFrame:
    normalized = normalize_market_frame(frame, start, end)
    serialized = normalized.copy()
    serialized["datetime_beijing"] = serialized["datetime_beijing"].map(
        lambda value: value.isoformat() if pd.notna(value) else ""
    )
    return serialized


def _selection_evidence(
    event: Mapping[str, Any]
) -> tuple[pd.DataFrame, dict[str, Any]]:
    metadata_path = Path(str(event["metadata_path"]))
    expected_metadata_sha = str(event["metadata_sha256"])
    _verify_hash(metadata_path, expected_metadata_sha, "selection metadata")
    metadata = _read_csv(metadata_path)
    candidates = build_selection_candidates(
        metadata,
        option_class=str(event["protection_option_class"]),
        entry_price=float(event["entry_price"]),
        entry_date=pd.Timestamp(event["entry_date"]),
    )
    if candidates.empty or not bool(candidates.iloc[0]["selected"]):
        raise IntegrityError("selection candidate rank one missing")
    selected = candidates.iloc[0]
    if str(selected["option_symbol"]) != str(event["option_symbol"]):
        raise IntegrityError("selection candidate symbol drift")
    if float(selected["strike_price"]) != float(event["option_strike"]):
        raise IntegrityError("selection candidate strike drift")
    if str(selected["expire_datetime"]) != str(event["option_expire_datetime"]):
        raise IntegrityError("selection candidate expiry drift")
    candidates_sha = hashlib.sha256(_csv_bytes(candidates)).hexdigest()
    audit = {
        "event_id": str(event["event_id"]),
        "metadata_path": str(metadata_path),
        "metadata_sha256": expected_metadata_sha,
        "terminal_status_source_sha256": TERMINAL_STATUS_SHA256,
        "acquisition_requirements_source_sha256": ACQUISITION_REQUIREMENTS_SHA256,
        "entry_risk_links_source_sha256": ENTRY_RISK_LINKS_SHA256,
        "direction": str(event["direction"]),
        "protection_option_class": str(event["protection_option_class"]),
        "entry_date": str(event["entry_date"]),
        "entry_price": float(event["entry_price"]),
        "selection_rule": (
            "first_expiry_then_sort(abs(strike-entry_price),strike,option_symbol)"
        ),
        "candidate_count": int(len(candidates)),
        "selection_candidates_sha256": candidates_sha,
        "selected_rank": int(selected["rank"]),
        "selected_option_symbol": str(selected["option_symbol"]),
        "selected_strike": float(selected["strike_price"]),
        "selected_expire_datetime": str(selected["expire_datetime"]),
        "selection_audit_pass": True,
    }
    return candidates, audit


def _attempt_manifest(path: Path) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for file_path in sorted(path.iterdir(), key=lambda item: item.name):
        if not file_path.is_file() or file_path.name in {
            ATTEMPT_MANIFEST_NAME,
            ATTEMPT_CHECKSUM_NAME,
        }:
            continue
        rows.append(
            {
                "file": file_path.name,
                "bytes": file_path.stat().st_size,
                "sha256": file_sha256(file_path),
            }
        )
    return pd.DataFrame(rows, columns=["file", "bytes", "sha256"])


def _next_attempt_number(event_dir: Path) -> int:
    numbers: list[int] = []
    for path in event_dir.glob("attempt_*"):
        try:
            numbers.append(int(path.name.split("_", 1)[1]))
        except (IndexError, ValueError):
            continue
    return max(numbers, default=0) + 1


def publish_attempt(
    event: dict[str, Any],
    payload: FetchPayload,
    attempts_root: Path,
    lineage: dict[str, str],
    *,
    secrets: list[str] | tuple[str, ...] = (),
) -> Path:
    if payload.terminal_status not in ALL_TERMINALS:
        raise IntegrityError(f"unknown terminal status: {payload.terminal_status}")
    if payload.terminal_status == "extracted" and not payload.audit.get(
        "market_data_integrity_pass", False
    ):
        raise IntegrityError("extracted payload failed market-data integrity")

    event_id = str(event["event_id"])
    event_dir = attempts_root / event_id
    event_dir.mkdir(parents=True, exist_ok=True)
    attempt_number = _next_attempt_number(event_dir)
    final_dir = event_dir / f"attempt_{attempt_number:04d}"
    temporary_dir = Path(tempfile.mkdtemp(prefix=".tmp_attempt_", dir=event_dir))
    try:
        run_id = str(event.get("_run_id", f"direct-{event_id[:12]}"))
        run_mode = str(event.get("_run_mode", "direct"))
        run_selection_event_ids = [
            str(value)
            for value in event.get("_run_selection_event_ids", [event_id])
        ]
        run_fetch_ordinal = int(event.get("_run_fetch_ordinal", 1))
        run_fetch_total = int(
            event.get("_run_fetch_total", len(run_selection_event_ids))
        )
        selection_candidates, selection_audit = _selection_evidence(event)
        _write_csv(
            temporary_dir / SELECTION_CANDIDATES_NAME, selection_candidates
        )
        _write_json(temporary_dir / SELECTION_AUDIT_NAME, selection_audit)
        request = {
            "event_id": event_id,
            "vt_symbol": str(event["vt_symbol"]),
            "tqsdk_underlying": str(event["tqsdk_underlying"]),
            "entry_date": str(event["entry_date"]),
            "direction": str(event["direction"]),
            "protection_option_class": str(event["protection_option_class"]),
            "entry_price": float(event["entry_price"]),
            "option_symbol": str(event["option_symbol"]),
            "option_strike": float(event["option_strike"]),
            "option_expire_datetime": str(event["option_expire_datetime"]),
            "metadata_path": str(event["metadata_path"]),
            "metadata_sha256": str(event["metadata_sha256"]),
            "session_start": str(event["session_start"]),
            "session_end": str(event["session_end"]),
            "terminal_status_source_sha256": TERMINAL_STATUS_SHA256,
            "acquisition_requirements_source_sha256": ACQUISITION_REQUIREMENTS_SHA256,
            "entry_risk_links_source_sha256": ENTRY_RISK_LINKS_SHA256,
            "selection_rule": selection_audit["selection_rule"],
            "selection_candidate_count": selection_audit["candidate_count"],
            "selection_candidates_sha256": selection_audit[
                "selection_candidates_sha256"
            ],
            "minute_duration_seconds": 60,
            "minute_data_length": 2000,
            "tick_data_length": 5000,
            "network_called": bool(payload.network_called),
            "run_id": run_id,
            "run_mode": run_mode,
            "run_selection_event_ids": run_selection_event_ids,
            "run_fetch_ordinal": run_fetch_ordinal,
            "run_fetch_total": run_fetch_total,
            **lineage,
        }
        status = {
            "event_id": event_id,
            "terminal_status": payload.terminal_status,
            "message": _redact_message(payload.message, secrets),
            "elapsed_seconds": float(payload.elapsed_seconds),
            "network_called": bool(payload.network_called),
            "run_id": run_id,
            "run_mode": run_mode,
            "run_selection_event_ids": run_selection_event_ids,
            "run_fetch_ordinal": run_fetch_ordinal,
            "run_fetch_total": run_fetch_total,
            "raw_underlying_minute_rows": int(len(payload.underlying_minute)),
            "raw_option_minute_rows": int(len(payload.option_minute)),
            "raw_option_tick_rows": int(len(payload.option_tick)),
            "audit": payload.audit,
        }
        _write_json(temporary_dir / ATTEMPT_REQUEST_NAME, request)
        _write_json(temporary_dir / ATTEMPT_STATUS_NAME, status)

        has_market_data_evidence = bool(
            payload.terminal_status in DATA_EVIDENCE_TERMINALS
            and (
                len(payload.underlying_minute)
                or len(payload.option_minute)
                or len(payload.option_tick)
            )
        )
        if payload.terminal_status == "extracted" or has_market_data_evidence:
            raw_frames = {
                RAW_UNDERLYING_MINUTE_NAME: payload.underlying_minute,
                RAW_OPTION_MINUTE_NAME: payload.option_minute,
                RAW_OPTION_TICK_NAME: payload.option_tick,
            }
            normalized_frames = {
                NORMALIZED_UNDERLYING_MINUTE_NAME: _serialize_normalized(
                    payload.underlying_minute,
                    event["session_start"],
                    event["session_end"],
                ),
                NORMALIZED_OPTION_MINUTE_NAME: _serialize_normalized(
                    payload.option_minute,
                    event["session_start"],
                    event["session_end"],
                ),
                NORMALIZED_OPTION_TICK_NAME: _serialize_normalized(
                    payload.option_tick,
                    event["session_start"],
                    event["session_end"],
                ),
            }
            for name, frame in {**raw_frames, **normalized_frames}.items():
                _write_csv(temporary_dir / name, frame)
            schema = {
                "raw": {
                    name: {
                        "columns": list(frame.columns),
                        "dtypes": {column: str(dtype) for column, dtype in frame.dtypes.items()},
                    }
                    for name, frame in raw_frames.items()
                },
                "normalized": {
                    name: {
                        "columns": list(frame.columns),
                        "dtypes": {column: str(dtype) for column, dtype in frame.dtypes.items()},
                    }
                    for name, frame in normalized_frames.items()
                },
            }
            _write_json(temporary_dir / ATTEMPT_SCHEMA_NAME, schema)

        manifest = _attempt_manifest(temporary_dir)
        _write_csv(temporary_dir / ATTEMPT_MANIFEST_NAME, manifest)
        checksum = (
            f"{file_sha256(temporary_dir / ATTEMPT_MANIFEST_NAME)}  "
            f"{ATTEMPT_MANIFEST_NAME}\n"
        ).encode("ascii")
        _atomic_write_bytes(temporary_dir / ATTEMPT_CHECKSUM_NAME, checksum)

        for secret in secrets:
            if secret and any(
                secret.encode("utf-8") in path.read_bytes()
                for path in temporary_dir.iterdir()
                if path.is_file()
            ):
                raise IntegrityError("credential literal found in attempt output")
        validation = validate_attempt_dir(temporary_dir, event, lineage)
        if not validation["attempt_integrity_pass"]:
            raise IntegrityError(validation["blocking_reason"])
        os.replace(temporary_dir, final_dir)
        return final_dir
    except Exception:
        if temporary_dir.exists():
            shutil.rmtree(temporary_dir)
        raise


def _validate_manifest(path: Path) -> list[str]:
    errors: list[str] = []
    manifest_path = path / ATTEMPT_MANIFEST_NAME
    checksum_path = path / ATTEMPT_CHECKSUM_NAME
    if not manifest_path.is_file() or not checksum_path.is_file():
        return ["attempt manifest or detached checksum missing"]
    expected_checksum = (
        f"{file_sha256(manifest_path)}  {ATTEMPT_MANIFEST_NAME}\n"
    )
    if checksum_path.read_text(encoding="ascii") != expected_checksum:
        errors.append("detached manifest checksum mismatch")
    try:
        manifest = _read_csv(manifest_path)
    except Exception as exc:
        return errors + [f"manifest unreadable: {exc}"]
    if list(manifest.columns) != ["file", "bytes", "sha256"]:
        errors.append("manifest schema mismatch")
        return errors
    if manifest["file"].duplicated().any():
        errors.append("manifest duplicate file")
    if manifest["file"].isin([ATTEMPT_MANIFEST_NAME, ATTEMPT_CHECKSUM_NAME]).any():
        errors.append("manifest includes itself or checksum")
    expected_files = sorted(
        item.name
        for item in path.iterdir()
        if item.is_file()
        and item.name not in {ATTEMPT_MANIFEST_NAME, ATTEMPT_CHECKSUM_NAME}
    )
    if sorted(manifest["file"].astype(str).tolist()) != expected_files:
        errors.append("manifest file set mismatch")
    for row in manifest.to_dict("records"):
        file_path = path / str(row["file"])
        if not file_path.is_file():
            errors.append(f"manifested file missing: {row['file']}")
            continue
        if int(row["bytes"]) != file_path.stat().st_size:
            errors.append(f"manifest bytes mismatch: {row['file']}")
        if str(row["sha256"]) != file_sha256(file_path):
            errors.append(f"manifest sha mismatch: {row['file']}")
    return errors


def validate_attempt_dir(
    path: Path, event: dict[str, Any], lineage: dict[str, str]
) -> dict[str, Any]:
    errors = _validate_manifest(path)
    request_path = path / ATTEMPT_REQUEST_NAME
    status_path = path / ATTEMPT_STATUS_NAME
    if not request_path.is_file() or not status_path.is_file():
        errors.append("request or status missing")
        return {
            "attempt_integrity_pass": False,
            "cacheable": False,
            "terminal_status": "missing",
            "blocking_reason": "; ".join(errors),
        }
    try:
        request = json.loads(request_path.read_text(encoding="utf-8"))
        status = json.loads(status_path.read_text(encoding="utf-8"))
    except Exception as exc:
        errors.append(f"request/status unreadable: {exc}")
        request, status = {}, {}

    missing_base_files = [
        name for name in BASE_EVIDENCE_FILES if not (path / name).is_file()
    ]
    if missing_base_files:
        errors.append(f"base evidence files missing: {missing_base_files}")
    identity_keys = (
        "event_id",
        "vt_symbol",
        "tqsdk_underlying",
        "entry_date",
        "direction",
        "protection_option_class",
        "entry_price",
        "option_symbol",
        "option_strike",
        "option_expire_datetime",
        "metadata_path",
        "metadata_sha256",
        "session_start",
        "session_end",
    )
    for key in identity_keys:
        if _json_safe(request.get(key)) != _json_safe(event.get(key)):
            errors.append(f"request identity mismatch: {key}")
    source_hashes = {
        "terminal_status_source_sha256": TERMINAL_STATUS_SHA256,
        "acquisition_requirements_source_sha256": ACQUISITION_REQUIREMENTS_SHA256,
        "entry_risk_links_source_sha256": ENTRY_RISK_LINKS_SHA256,
    }
    for key, expected in source_hashes.items():
        if request.get(key) != expected:
            errors.append(f"upstream source lineage mismatch: {key}")
    for key, expected in lineage.items():
        if request.get(key) != expected:
            errors.append(f"producer lineage mismatch: {key}")
    terminal = str(status.get("terminal_status", "missing"))
    if terminal not in ALL_TERMINALS:
        errors.append(f"invalid terminal status: {terminal}")
    if str(status.get("event_id")) != str(event.get("event_id")):
        errors.append("status event identity mismatch")
    execution_keys = (
        "run_id",
        "run_mode",
        "run_selection_event_ids",
        "run_fetch_ordinal",
        "run_fetch_total",
    )
    for key in execution_keys:
        if request.get(key) != status.get(key):
            errors.append(f"request/status execution mismatch: {key}")
    run_mode = str(request.get("run_mode", ""))
    run_selection = request.get("run_selection_event_ids", [])
    run_ordinal = request.get("run_fetch_ordinal")
    run_total = request.get("run_fetch_total")
    if run_mode not in {"direct", "canary", "remaining"}:
        errors.append("invalid run_mode")
    if not isinstance(run_selection, list) or not all(
        isinstance(value, str) for value in run_selection
    ):
        errors.append("invalid run_selection_event_ids")
        run_selection = []
    if run_total != len(run_selection) or not isinstance(run_ordinal, int):
        errors.append("run fetch cardinality mismatch")
    elif not (1 <= run_ordinal <= run_total):
        errors.append("run fetch ordinal out of range")
    elif run_selection[run_ordinal - 1] != str(event.get("event_id")):
        errors.append("run fetch ordinal event mismatch")
    if run_mode == "canary" and run_selection != [EXPECTED_EVENT_IDS[0]]:
        errors.append("canary run selection mismatch")
    if run_mode == "remaining" and any(
        value not in EXPECTED_EVENT_IDS[1:] for value in run_selection
    ):
        errors.append("remaining run selection mismatch")

    if not missing_base_files:
        try:
            expected_candidates, expected_selection_audit = _selection_evidence(event)
            if (path / SELECTION_CANDIDATES_NAME).read_bytes() != _csv_bytes(
                expected_candidates
            ):
                errors.append("selection candidates recompute mismatch")
            persisted_selection_audit = json.loads(
                (path / SELECTION_AUDIT_NAME).read_text(encoding="utf-8")
            )
            if persisted_selection_audit != _json_safe(expected_selection_audit):
                errors.append("selection audit recompute mismatch")
            if request.get("selection_candidates_sha256") != expected_selection_audit[
                "selection_candidates_sha256"
            ]:
                errors.append("request selection candidates sha mismatch")
            if request.get("selection_candidate_count") != expected_selection_audit[
                "candidate_count"
            ]:
                errors.append("request selection candidate count mismatch")
            if request.get("selection_rule") != expected_selection_audit[
                "selection_rule"
            ]:
                errors.append("request selection rule mismatch")
        except Exception as exc:
            errors.append(f"selection evidence validation failed: {exc}")

    has_evidence_files = any((path / name).exists() for name in EXTRACTED_DATA_FILES)
    if terminal == "extracted" or (
        terminal == "integrity_failed" and has_evidence_files
    ):
        missing = [name for name in EXTRACTED_DATA_FILES if not (path / name).is_file()]
        if missing:
            errors.append(f"extracted data files missing: {missing}")
        else:
            try:
                raw_frames = {
                    RAW_UNDERLYING_MINUTE_NAME: _read_csv(
                        path / RAW_UNDERLYING_MINUTE_NAME
                    ),
                    RAW_OPTION_MINUTE_NAME: _read_csv(path / RAW_OPTION_MINUTE_NAME),
                    RAW_OPTION_TICK_NAME: _read_csv(path / RAW_OPTION_TICK_NAME),
                }
                expected_normalized = {
                    NORMALIZED_UNDERLYING_MINUTE_NAME: _serialize_normalized(
                        raw_frames[RAW_UNDERLYING_MINUTE_NAME],
                        event["session_start"],
                        event["session_end"],
                    ),
                    NORMALIZED_OPTION_MINUTE_NAME: _serialize_normalized(
                        raw_frames[RAW_OPTION_MINUTE_NAME],
                        event["session_start"],
                        event["session_end"],
                    ),
                    NORMALIZED_OPTION_TICK_NAME: _serialize_normalized(
                        raw_frames[RAW_OPTION_TICK_NAME],
                        event["session_start"],
                        event["session_end"],
                    ),
                }
                for name, frame in expected_normalized.items():
                    if (path / name).read_bytes() != _csv_bytes(frame):
                        errors.append(f"normalized recompute mismatch: {name}")
                recomputed_audit = audit_event_market_data(
                    raw_frames[RAW_UNDERLYING_MINUTE_NAME],
                    raw_frames[RAW_OPTION_MINUTE_NAME],
                    raw_frames[RAW_OPTION_TICK_NAME],
                    event["session_start"],
                    event["session_end"],
                )
                persisted_audit = status.get("audit", {})
                for key in (
                    "market_data_integrity_pass",
                    "premium_observed",
                    "oi_observed",
                    "tick_price_observed",
                    "two_sided_spread_observed",
                    "positive_trade_observed",
                    "all_fields_observed",
                ):
                    if persisted_audit.get(key) != _json_safe(recomputed_audit.get(key)):
                        errors.append(f"persisted audit mismatch: {key}")
                if terminal == "extracted" and not recomputed_audit[
                    "market_data_integrity_pass"
                ]:
                    errors.append("recomputed market-data integrity failed")
            except Exception as exc:
                errors.append(f"extracted data validation failed: {exc}")
    elif has_evidence_files:
        errors.append("non-extracted attempt contains market data files")

    passed = not errors
    return {
        "attempt_integrity_pass": passed,
        "cacheable": bool(passed and terminal == "extracted"),
        "terminal_status": terminal,
        "blocking_reason": "; ".join(errors),
        "attempt_manifest_sha256": (
            file_sha256(path / ATTEMPT_MANIFEST_NAME)
            if (path / ATTEMPT_MANIFEST_NAME).is_file()
            else ""
        ),
    }


class EventTimeoutError(TimeoutError):
    pass


@contextmanager
def _wall_clock_timeout(seconds: float):
    if seconds <= 0 or not hasattr(signal, "SIGALRM"):
        yield
        return

    def handler(_signum: int, _frame: Any) -> None:
        raise EventTimeoutError(f"event exceeded {seconds:.3f}s")

    previous_handler = signal.signal(signal.SIGALRM, handler)
    signal.setitimer(signal.ITIMER_REAL, float(seconds))
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0.0)
        signal.signal(signal.SIGALRM, previous_handler)


def _credentials() -> tuple[str, str]:
    from vnpy.trader.setting import SETTINGS

    return (
        str(SETTINGS.get("datafeed.username", "")).strip(),
        str(SETTINGS.get("datafeed.password", "")).strip(),
    )


def _is_authentication_error(message: str) -> bool:
    return bool(
        re.search(
            r"(?i)(auth|authentication|permission|unauthorized|username|password|登录|认证|权限|用户名|密码)",
            str(message),
        )
    )


def fetch_event_network(
    event: Mapping[str, Any], max_seconds: int = 180
) -> FetchPayload:
    username, password = _credentials()
    started = time.time()
    if not username or not password:
        return FetchPayload(
            terminal_status="authentication_failed",
            underlying_minute=pd.DataFrame(),
            option_minute=pd.DataFrame(),
            option_tick=pd.DataFrame(),
            audit={},
            message="TqSdk credentials missing",
            elapsed_seconds=time.time() - started,
            network_called=False,
        )

    api = None
    underlying_minute = pd.DataFrame()
    option_minute = pd.DataFrame()
    option_tick = pd.DataFrame()
    audit: dict[str, Any] = {}
    terminal = "query_failed"
    message = ""
    deadline = started + max_seconds
    try:
        from tqsdk import BacktestFinished, TqApi, TqAuth, TqBacktest, TqSim

        with _wall_clock_timeout(max_seconds):
            try:
                start_dt = _china_timestamp(event["session_start"]).tz_localize(None)
                end_dt = _china_timestamp(event["session_end"]).tz_localize(None)
                api = TqApi(
                    TqSim(),
                    backtest=TqBacktest(
                        start_dt=start_dt.to_pydatetime(),
                        end_dt=end_dt.to_pydatetime(),
                    ),
                    auth=TqAuth(username, password),
                    disable_print=True,
                )
                underlying_serial = api.get_kline_serial(
                    str(event["tqsdk_underlying"]),
                    duration_seconds=60,
                    data_length=2000,
                )
                option_serial = api.get_kline_serial(
                    str(event["option_symbol"]),
                    duration_seconds=60,
                    data_length=2000,
                )
                tick_serial = api.get_tick_serial(
                    str(event["option_symbol"]), data_length=5000
                )
                while True:
                    try:
                        api.wait_update(deadline=time.time() + 1.0)
                    except BacktestFinished:
                        break
                underlying_minute = pd.DataFrame(underlying_serial).copy(deep=True)
                option_minute = pd.DataFrame(option_serial).copy(deep=True)
                option_tick = pd.DataFrame(tick_serial).copy(deep=True)
                audit = audit_event_market_data(
                    underlying_minute,
                    option_minute,
                    option_tick,
                    event["session_start"],
                    event["session_end"],
                )
                terminal = (
                    "extracted"
                    if audit["market_data_integrity_pass"]
                    else "integrity_failed"
                )
            finally:
                if api is not None:
                    remaining = deadline - time.time()
                    if remaining <= 0:
                        raise EventTimeoutError(
                            f"event exceeded {max_seconds}s before api.close"
                        )
                    with _wall_clock_timeout(remaining):
                        api.close()
                    api = None
    except EventTimeoutError as exc:
        terminal = "timeout"
        message = _redact_message(exc, [username, password])
    except Exception as exc:
        message = _redact_message(exc, [username, password])
        terminal = (
            "authentication_failed"
            if _is_authentication_error(message)
            else "query_failed"
        )
    return FetchPayload(
        terminal_status=terminal,
        underlying_minute=underlying_minute,
        option_minute=option_minute,
        option_tick=option_tick,
        audit=audit,
        message=message,
        elapsed_seconds=time.time() - started,
        network_called=True,
    )


def current_lineage() -> dict[str, str]:
    paths = {
        "tool_sha256": TOOL_PATH,
        "test_sha256": TEST_PATH,
        "predecl_sha256": PREDECL_PATH,
        "plan_sha256": IMPLEMENTATION_PLAN_PATH,
    }
    for label, path in paths.items():
        if not path.is_file():
            raise IntegrityError(f"producer lineage file missing: {label}={path}")
    return {label: file_sha256(path) for label, path in paths.items()}


def _inventory_attempts(
    plan: pd.DataFrame, attempts_root: Path, lineage: dict[str, str]
) -> pd.DataFrame:
    event_lookup = {
        str(row["event_id"]): row for row in plan.to_dict("records")
    }
    rows: list[dict[str, Any]] = []
    for event_id, event in event_lookup.items():
        event_dir = attempts_root / event_id
        for path in sorted(event_dir.glob("attempt_*")) if event_dir.is_dir() else []:
            try:
                validation = validate_attempt_dir(path, event, lineage)
            except Exception as exc:
                validation = {
                    "attempt_integrity_pass": False,
                    "cacheable": False,
                    "terminal_status": "integrity_failed",
                    "blocking_reason": f"validator raised: {exc}",
                    "attempt_manifest_sha256": "",
                }
            rows.append(
                {
                    "event_id": event_id,
                    "attempt_name": path.name,
                    "attempt_integrity_pass": bool(
                        validation["attempt_integrity_pass"]
                    ),
                    "cacheable": bool(validation["cacheable"]),
                    "terminal_status": str(validation["terminal_status"]),
                    "blocking_reason": str(validation["blocking_reason"]),
                    "attempt_manifest_sha256": str(
                        validation.get("attempt_manifest_sha256", "")
                    ),
                    "attempt_path": str(path),
                }
            )
    return pd.DataFrame(
        rows,
        columns=[
            "event_id",
            "attempt_name",
            "attempt_integrity_pass",
            "cacheable",
            "terminal_status",
            "blocking_reason",
            "attempt_manifest_sha256",
            "attempt_path",
        ],
    )


def _latest_cacheable_attempts(inventory: pd.DataFrame) -> dict[str, Path]:
    if inventory.empty:
        return {}
    cacheable = inventory[inventory["cacheable"]].copy()
    if cacheable.empty:
        return {}
    cacheable = cacheable.sort_values(
        ["event_id", "attempt_name"], kind="mergesort"
    )
    latest = cacheable.groupby("event_id", sort=False).tail(1)
    return {
        str(row["event_id"]): Path(str(row["attempt_path"]))
        for row in latest.to_dict("records")
    }


def _event_status(
    plan: pd.DataFrame, inventory: pd.DataFrame
) -> pd.DataFrame:
    cacheable = _latest_cacheable_attempts(inventory)
    rows: list[dict[str, Any]] = []
    for event in plan.to_dict("records"):
        event_id = str(event["event_id"])
        attempts = (
            inventory[inventory["event_id"].eq(event_id)].sort_values("attempt_name")
            if not inventory.empty
            else pd.DataFrame()
        )
        attempt_path = cacheable.get(event_id)
        if attempt_path is not None:
            terminal = "extracted"
            is_cacheable = True
            blocking_reason = ""
            status = json.loads(
                (attempt_path / ATTEMPT_STATUS_NAME).read_text(encoding="utf-8")
            )
            audit = status.get("audit", {})
        elif len(attempts):
            latest = attempts.iloc[-1]
            terminal = str(latest["terminal_status"])
            is_cacheable = False
            blocking_reason = str(latest["blocking_reason"])
            audit = {}
            attempt_path = Path(str(latest["attempt_path"]))
        else:
            terminal = "missing"
            is_cacheable = False
            blocking_reason = "no attempt"
            audit = {}
            attempt_path = None
        rows.append(
            {
                **event,
                "attempt_count": int(len(attempts)),
                "terminal_status": terminal,
                "cacheable": is_cacheable,
                "attempt_path": str(attempt_path) if attempt_path else "",
                "blocking_reason": blocking_reason,
                "premium_observed": bool(audit.get("premium_observed", False)),
                "oi_observed": bool(audit.get("oi_observed", False)),
                "tick_price_observed": bool(
                    audit.get("tick_price_observed", False)
                ),
                "two_sided_spread_observed": bool(
                    audit.get("two_sided_spread_observed", False)
                ),
                "positive_trade_observed": bool(
                    audit.get("positive_trade_observed", False)
                ),
                "all_fields_observed": bool(
                    audit.get("all_fields_observed", False)
                ),
                "underlying_minute_session_rows": int(
                    audit.get("underlying_minute_session_row_count", 0)
                ),
                "option_minute_session_rows": int(
                    audit.get("option_minute_session_row_count", 0)
                ),
                "tick_session_rows": int(audit.get("tick_session_row_count", 0)),
                "tick_volume_change": audit.get("tick_volume_change"),
            }
        )
    return pd.DataFrame(rows)


def audit_code_isolation() -> dict[str, Any]:
    tree = ast.parse(TOOL_PATH.read_text(encoding="utf-8"))
    forbidden_calls = {
        "insert_order",
        "cancel_order",
        "get_account",
        "get_position",
        "TargetPosTask",
        "sendmail",
    }
    forbidden_import_roots = {"vnpy_ctp", "smtplib"}
    call_hits: list[str] = []
    import_hits: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute):
                name = node.func.attr
            elif isinstance(node.func, ast.Name):
                name = node.func.id
            else:
                name = ""
            if name in forbidden_calls:
                call_hits.append(name)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [alias.name for alias in node.names]
            if isinstance(node, ast.ImportFrom) and node.module:
                names.append(node.module)
            for name in names:
                if name.split(".", 1)[0] in forbidden_import_roots:
                    import_hits.append(name)
    return {
        "forbidden_call_hits": sorted(call_hits),
        "forbidden_import_hits": sorted(import_hits),
        "order_ctp_mail_live_isolation_pass": not call_hits and not import_hits,
    }


def _credential_literal_hits(root: Path, secrets: tuple[str, str]) -> int:
    encoded = [secret.encode("utf-8") for secret in secrets if secret]
    if not encoded or not root.exists():
        return 0
    hits = 0
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        payload = path.read_bytes()
        hits += sum(secret in payload for secret in encoded)
    return int(hits)


def _root_paths(output_dir: Path) -> dict[str, Path]:
    prefix = "rebuilt_c9_v2_stage133_c9_2022_extracted_event_market_data_readiness"
    tag = "stage133_c9_2022_extracted_event_market_data_readiness_v1"
    return {
        "plan": output_dir / f"{prefix}_probe_plan_{tag}.csv",
        "inventory": output_dir / f"{prefix}_attempt_inventory_{tag}.csv",
        "status": output_dir / f"{prefix}_event_status_{tag}.csv",
        "decision": output_dir / f"{prefix}_decision_{tag}.json",
        "lineage": output_dir / f"{prefix}_lineage_{tag}.json",
        "report": output_dir / f"{prefix}_report_{tag}.md",
        "manifest": output_dir / f"{prefix}_manifest_{tag}.csv",
        "checksum": output_dir / f"{prefix}_manifest_sha256_{tag}.txt",
    }


def _write_root_outputs(
    output_dir: Path,
    plan: pd.DataFrame,
    inventory: pd.DataFrame,
    event_status: pd.DataFrame,
    decision: dict[str, Any],
    lineage: dict[str, str],
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = _root_paths(output_dir)
    _write_csv(paths["plan"], plan)
    _write_csv(paths["inventory"], inventory)
    _write_csv(paths["status"], event_status)
    _write_json(paths["decision"], decision)
    _write_json(
        paths["lineage"],
        {
            **lineage,
            "terminal_status_sha256": TERMINAL_STATUS_SHA256,
            "acquisition_requirements_sha256": ACQUISITION_REQUIREMENTS_SHA256,
            "entry_risk_links_sha256": ENTRY_RISK_LINKS_SHA256,
            "metadata_sha256": EXPECTED_METADATA_SHA256,
        },
    )
    report = "\n".join(
        [
            "# Stage133 C9 2022 已覆盖事件行情可读性",
            "",
            f"- decision: `{decision['decision']}`",
            f"- cacheable events: `{decision['cacheable_event_count']}/4`",
            f"- all fields observed: `{decision['all_fields_observed_event_count']}/4`",
            f"- credential literal hits: `{decision['credential_literal_hit_count']}`",
            "- Stage133 的 4/4 只代表 vendor-extracted 子集，不代表 C9 事件全集。",
            "- Stage132 全集 metadata 覆盖仍为 `123/365=33.698630%`，覆盖硬失败不变。",
            "- Stage132 2022 覆盖仍为 `11/48`；核心窗口原风险覆盖仅 `26.461965%`。",
            "- 核心缺口 `fu/jm/FG/SM/hc` 在该窗口 extracted 仍为 0。",
            "- full premium acquisition: `false`",
            "- option strategy A/B: `false`",
            "- live: `false`",
            "",
            "本报告只验证固定四事件的数据字段可读性，不是期权保护收益或可成交性结论。",
            "",
        ]
    )
    _atomic_write_bytes(paths["report"], report.encode("utf-8"))
    manifest = pd.DataFrame(
        [
            {
                "file": path.name,
                "bytes": path.stat().st_size,
                "sha256": file_sha256(path),
            }
            for key, path in sorted(paths.items())
            if key not in {"manifest", "checksum"} and path.is_file()
        ]
    )
    _write_csv(paths["manifest"], manifest)
    checksum = (
        f"{file_sha256(paths['manifest'])}  {paths['manifest'].name}\n"
    ).encode("ascii")
    _atomic_write_bytes(paths["checksum"], checksum)


def run(
    *,
    run_mode: str = "plan",
    enable_network: bool = False,
    fetcher: Callable[[Mapping[str, Any], int], FetchPayload] = fetch_event_network,
    output_dir: Path = OUTPUT_DIR,
) -> dict[str, Any]:
    mode = str(run_mode).strip().lower()
    if mode not in {"plan", "canary", "remaining"}:
        raise IntegrityError(f"unsupported run mode: {mode}")
    plan = load_frozen_probe_plan()
    plan_audit = audit_probe_plan(plan)
    if not plan_audit["probe_plan_audit_pass"]:
        raise IntegrityError("frozen probe plan failed audit")
    lineage = current_lineage()
    attempts_root = output_dir / "event_attempts"
    inventory_before = _inventory_attempts(plan, attempts_root, lineage)
    cacheable_before = _latest_cacheable_attempts(inventory_before)
    canary_id = EXPECTED_EVENT_IDS[0]
    if mode == "remaining" and canary_id not in cacheable_before:
        raise IntegrityError("remaining mode requires a valid fixed canary cache")

    if mode == "plan":
        selection = plan.iloc[0:0]
    elif mode == "canary":
        selection = (
            plan.iloc[0:0]
            if canary_id in cacheable_before
            else plan[plan["event_id"].eq(canary_id)]
        )
    else:
        selection = plan.iloc[1:]
        selection = selection[~selection["event_id"].isin(cacheable_before)]
    if len(selection) and not enable_network:
        raise IntegrityError(f"{mode} mode requires STAGE133_ENABLE_NETWORK=1")

    secrets = _credentials()
    network_fetch_count = 0
    run_selection_event_ids = selection["event_id"].astype(str).tolist()
    run_id = hashlib.sha256(
        (
            f"{lineage['tool_sha256']}|{lineage['test_sha256']}|{mode}|"
            f"{'|'.join(run_selection_event_ids)}|{time.time_ns()}"
        ).encode("utf-8")
    ).hexdigest()[:24]
    for ordinal, event in enumerate(selection.to_dict("records"), start=1):
        execution_event = {
            **event,
            "_run_id": run_id,
            "_run_mode": mode,
            "_run_selection_event_ids": run_selection_event_ids,
            "_run_fetch_ordinal": ordinal,
            "_run_fetch_total": len(run_selection_event_ids),
        }
        payload = fetcher(execution_event, 180)
        network_fetch_count += 1
        publish_attempt(
            execution_event,
            payload,
            attempts_root,
            lineage,
            secrets=list(secrets),
        )
        if payload.terminal_status == "authentication_failed":
            break

    inventory = _inventory_attempts(plan, attempts_root, lineage)
    event_status = _event_status(plan, inventory)
    cacheable_count = int(event_status["cacheable"].sum())
    all_fields_count = int(event_status["all_fields_observed"].sum())
    canary_pass = bool(
        event_status.loc[event_status["event_id"].eq(canary_id), "cacheable"].all()
    )
    if cacheable_count == 4 and all_fields_count == 4:
        decision_label = "stage133_data_readiness_observed_all_four_no_strategy_inference"
    elif cacheable_count == 4:
        decision_label = "stage133_data_readiness_observed_partial_fields_no_strategy_inference"
    else:
        decision_label = "stage133_data_readiness_incomplete_no_strategy_inference"
    isolation = audit_code_isolation()
    credential_hits = _credential_literal_hits(output_dir, secrets)
    decision = {
        "stage": "Stage133",
        "run_mode": mode,
        "run_id": run_id,
        "run_selection_event_ids": run_selection_event_ids,
        "decision": decision_label,
        "network_fetch_count": network_fetch_count,
        "event_count": 4,
        "cacheable_event_count": cacheable_count,
        "all_fields_observed_event_count": all_fields_count,
        "canary_pass": canary_pass,
        "probe_plan_audit": plan_audit,
        "credential_literal_hit_count": credential_hits,
        "stage132_metadata_covered_event_count": STAGE132_METADATA_COVERED_EVENT_COUNT,
        "stage132_total_event_count": STAGE132_TOTAL_EVENT_COUNT,
        "stage132_metadata_coverage_ratio": STAGE132_METADATA_COVERAGE_RATIO,
        "stage132_2022_covered_event_count": STAGE132_2022_COVERED_EVENT_COUNT,
        "stage132_2022_total_event_count": STAGE132_2022_TOTAL_EVENT_COUNT,
        "stage132_2022_core_risk_coverage_ratio": STAGE132_2022_CORE_RISK_COVERAGE_RATIO,
        "stage132_coverage_hard_fail": True,
        **isolation,
        "ready_for_full_premium_acquisition": False,
        "ready_for_option_strategy_ab": False,
        "ready_for_live": False,
        "strategy_trade_count": 0,
    }
    _write_root_outputs(
        output_dir,
        plan,
        inventory,
        event_status,
        decision,
        lineage,
    )
    final_credential_hits = _credential_literal_hits(output_dir, secrets)
    if final_credential_hits:
        raise IntegrityError(
            f"credential literal found in Stage133 outputs: {final_credential_hits}"
        )
    return decision


def main() -> dict[str, Any]:
    decision = run(
        run_mode=os.getenv("STAGE133_RUN_MODE", "plan"),
        enable_network=os.getenv("STAGE133_ENABLE_NETWORK", "0").strip() == "1",
    )
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2, sort_keys=True))
    return decision


if __name__ == "__main__":
    main()
