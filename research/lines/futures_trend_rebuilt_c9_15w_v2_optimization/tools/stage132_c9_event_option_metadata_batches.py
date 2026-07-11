from __future__ import annotations

from contextlib import contextmanager
from datetime import date, datetime
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import re
import signal
import sys
import time
from typing import Any, Callable, Mapping, Sequence
import uuid
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
from vnpy.trader.setting import SETTINGS


ROOT_DIR = Path(__file__).resolve().parents[4]
LINE_ID = "futures_trend_rebuilt_c9_15w_v2_optimization"
STAGE = "Stage132"
STAGE_ID = "stage132_c9_event_option_metadata_batches"
MODEL_TAG = f"{STAGE_ID}_v1"
OUTPUT_PREFIX = f"rebuilt_c9_v2_{STAGE_ID}"

LINE_ROOT = ROOT_DIR / "research" / "lines" / LINE_ID
STAGE131_OUTPUT_DIR = LINE_ROOT / "outputs" / "stage131_c9_event_targeted_option_acquisition_manifest"
SOURCE_QUERY_EVENTS_PATH = STAGE131_OUTPUT_DIR / (
    "rebuilt_c9_v2_stage131_c9_event_targeted_option_acquisition_manifest_"
    "query_events_stage131_c9_event_targeted_option_acquisition_manifest_v1.csv"
)
SOURCE_QUERY_EVENTS_SHA256 = "7abf7a0414238517349e383a6ef7282b5f8d16921686ddc1edb6f2e70e5cc77a"
SOURCE_STAGE131_MANIFEST_SHA256 = "63184047a307e0e5e9ce1406fa8ddb614fff4635ad22885fd936d63dcfea9f1c"
EXPECTED_EVENT_COUNT = 365
BATCH_SIZE = 10
EXPECTED_BATCH_COUNT = 37

CANARY_EVENT_IDS = (
    "3734ac5af36029dd053580b4fad920d86d52b0b75a004451933639740e6a7707",
    "b13e8f7de7837203b0d80c8e01c30290633b2f8bfb97038e8c0e28ec84069a91",
    "69989dc6767a65b044ea3e1144ced85e993f684e427aa3d647add80da79f58a9",
    "183c0046ccaa1726d6b1145c4b31f9c947a6f9b8d8d59465021fb5eff84a00af",
    "00a1c59abb9ac9f1c27af02916c2b8ed12ea05ca0f73d8396ddee9b98dc9dec7",
    "00be208c04f58cb91a64725106c79807fccf30b64c276ac88778df32d1271fa2",
    "014a6683b4ac65ea3ede26ddc94657263b42f749b3a724afcd80c8114a8b5793",
    "0152ff95a1dd4cd827a5f30b04a427e27f6bea6eecca567f84a06c6500a4b311",
    "01616f42cee547655a1fc0e8a690d110a413e5b7efb5564dcee115f02132238c",
    "0168ddc1fecf2a42778e6a163eec0b3056c536ac02c79b7543f6e0e7897f1529",
)

SOURCE_REQUIRED_COLUMNS = [
    "event_id",
    "vt_symbol",
    "tqsdk_underlying",
    "product_vt_symbol",
    "entry_date",
    "query_start",
    "query_end",
    "query_expired_as_of_entry",
]
FORBIDDEN_SOURCE_COLUMNS = {
    "realized_pnl",
    "r_multiple",
    "winner",
    "mfe",
    "mae",
    "entry_period_2022",
    "account_equity",
    "net_pnl",
}
NORMALIZED_COLUMNS = [
    "option_symbol",
    "underlying_symbol",
    "option_class",
    "expire_datetime",
    "last_exercise_datetime",
    "strike_price",
    "expired",
    "volume_multiple",
    "price_tick",
]
CACHEABLE_TERMINALS = {
    "extracted",
    "empty_chain",
    "underlying_not_in_option_catalog",
}
ALL_TERMINALS = CACHEABLE_TERMINALS | {
    "authentication_failed",
    "timeout",
    "query_failed",
    "integrity_failed",
}
ATTEMPT_INVENTORY_COLUMNS = [
    "event_id",
    "attempt_name",
    "attempt_integrity_pass",
    "cacheable",
    "terminal_status",
    "query_symbol_count",
    "untouched_row_count",
    "normalized_row_count",
    "elapsed_seconds",
    "network_called",
    "blocking_reason",
    "attempt_path",
    "attempt_manifest_sha256",
    "producer_tool_sha256",
    "producer_test_sha256",
    "producer_predecl_sha256",
]

OUTPUT_DIR = LINE_ROOT / "outputs" / STAGE_ID
ATTEMPTS_ROOT = OUTPUT_DIR / "event_attempts"
PREDECL_PATH = LINE_ROOT / "stages" / "20260711_1430_stage132_c9_event_option_metadata_batches_predecl.md"
TOOL_PATH = Path(__file__).resolve()
TEST_PATH = ROOT_DIR / "tests" / "test_rebuilt_c9_v2_stage132_c9_event_option_metadata_batches.py"

ATTEMPT_REQUEST_NAME = "request.json"
ATTEMPT_SYMBOLS_NAME = "option_symbols.json"
UNTOUCHED_METADATA_NAME = "untouched_metadata.csv"
UNTOUCHED_SCHEMA_NAME = "untouched_schema.json"
NORMALIZED_METADATA_NAME = "normalized_metadata.csv"
ATTEMPT_STATUS_NAME = "status.json"
ATTEMPT_MANIFEST_NAME = "manifest.csv"
ATTEMPT_CHECKSUM_NAME = "manifest.sha256"


def _out(kind: str, suffix: str = "csv") -> Path:
    return OUTPUT_DIR / f"{OUTPUT_PREFIX}_{kind}_{MODEL_TAG}.{suffix}"


BATCH_PLAN_PATH = _out("batch_plan")
SOURCE_AUDIT_PATH = _out("source_audit")
ATTEMPT_INVENTORY_PATH = _out("attempt_inventory")
EVENT_STATUS_PATH = _out("event_terminal_status")
YEAR_COVERAGE_PATH = _out("coverage_by_year")
PRODUCT_COVERAGE_PATH = _out("coverage_by_product")
EXCHANGE_COVERAGE_PATH = _out("coverage_by_exchange")
DECISION_PATH = _out("decision", "json")
LINEAGE_PATH = _out("lineage", "json")
REPORT_PATH = _out("report", "md")
ROOT_MANIFEST_PATH = _out("manifest")
ROOT_CHECKSUM_PATH = _out("manifest_sha256", "txt")

RUN_MODE = os.getenv("STAGE132_RUN_MODE", "plan").strip().lower()
ENABLE_NETWORK = os.getenv("STAGE132_ENABLE_NETWORK", "0").strip() == "1"
FORCE_CANARY_RETRY = os.getenv("STAGE132_FORCE_CANARY_RETRY", "0").strip() == "1"
MAX_SECONDS_PER_EVENT = int(os.getenv("STAGE132_MAX_SECONDS_PER_EVENT", "60"))
CHINA_TZ = ZoneInfo("Asia/Shanghai")


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
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        result = float(value)
        return None if math.isnan(result) or math.isinf(result) else result
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, (pd.Timestamp, datetime, date)):
        return pd.Timestamp(value).isoformat()
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return value


def _write_json(payload: Mapping[str, Any] | Sequence[Any], path: Path) -> None:
    path.write_text(
        json.dumps(_json_safe(payload), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _write_csv(frame: pd.DataFrame, path: Path) -> None:
    frame.to_csv(path, index=False, encoding="utf-8-sig")


def _atomic_write_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.parent / f".{path.name}.tmp_{os.getpid()}_{uuid.uuid4().hex}"
    temp.write_bytes(payload)
    if temp.stat().st_dev != path.parent.stat().st_dev:
        raise RuntimeError(f"cross-device atomic publish blocked: {temp} -> {path}")
    os.replace(temp, path)


def _atomic_write_json(payload: Mapping[str, Any] | Sequence[Any], path: Path) -> None:
    data = json.dumps(_json_safe(payload), ensure_ascii=False, indent=2).encode("utf-8") + b"\n"
    _atomic_write_bytes(path, data)


def _atomic_write_csv(frame: pd.DataFrame, path: Path) -> None:
    data = frame.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
    _atomic_write_bytes(path, data)


def event_id_for(vt_symbol: str, entry_date: Any) -> str:
    day = pd.Timestamp(entry_date).strftime("%Y-%m-%d")
    return hashlib.sha256(f"{vt_symbol}|{day}".encode("utf-8")).hexdigest()


def _as_bool(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, (int, np.integer, float, np.floating)) and not pd.isna(value):
        if float(value) in (0.0, 1.0):
            return bool(int(value))
    text = str(value).strip().lower()
    if text in {"false", "f", "0", "no", "n"}:
        return False
    if text in {"true", "t", "1", "yes", "y"}:
        return True
    return None


def _to_tqsdk_underlying(vt_symbol: str) -> str:
    text = str(vt_symbol)
    if text.count(".") != 1:
        return ""
    symbol, exchange = text.rsplit(".", 1)
    return f"{exchange}.{symbol}" if symbol and exchange else ""


def audit_frozen_events(frame: pd.DataFrame) -> dict[str, Any]:
    missing_columns = [column for column in SOURCE_REQUIRED_COLUMNS if column not in frame.columns]
    result: dict[str, Any] = {
        "source_row_count": int(len(frame)),
        "missing_column_count": len(missing_columns),
        "missing_columns": "|".join(missing_columns),
        "forbidden_column_count": len(FORBIDDEN_SOURCE_COLUMNS & set(frame.columns)),
    }
    if missing_columns:
        result["source_audit_pass"] = False
        return result

    data = frame.copy()
    entry = pd.to_datetime(data["entry_date"], errors="coerce").dt.normalize()
    start = pd.to_datetime(data["query_start"], errors="coerce")
    end = pd.to_datetime(data["query_end"], errors="coerce")
    expected_ids = [
        event_id_for(str(symbol), day)
        if not pd.isna(day)
        else ""
        for symbol, day in zip(data["vt_symbol"], entry)
    ]
    expected_tq = data["vt_symbol"].astype(str).map(_to_tqsdk_underlying)
    expired_values = data["query_expired_as_of_entry"].map(_as_bool)
    result.update(
        {
            "duplicate_event_id_count": int(data.duplicated("event_id", keep=False).sum()),
            "invalid_entry_date_count": int(entry.isna().sum()),
            "invalid_query_start_count": int(start.isna().sum()),
            "invalid_query_end_count": int(end.isna().sum()),
            "event_id_mismatch_count": int(
                (data["event_id"].astype(str) != pd.Series(expected_ids, index=data.index)).sum()
            ),
            "tqsdk_underlying_mismatch_count": int(
                (data["tqsdk_underlying"].astype(str) != expected_tq).sum()
            ),
            "query_start_day_mismatch_count": int(
                (start.dt.normalize() != entry).fillna(True).sum()
            ),
            "query_end_day_mismatch_count": int(
                (end.dt.normalize() != entry).fillna(True).sum()
            ),
            "query_end_clock_mismatch_count": int(
                (
                    end.dt.strftime("%H:%M:%S").fillna("")
                    != "23:59:59"
                ).sum()
            ),
            "expired_not_false_count": int(
                sum(value is not False for value in expired_values)
            ),
        }
    )
    error_keys = [
        key
        for key in result
        if key.endswith("_count") and key != "source_row_count"
    ]
    result["source_audit_pass"] = bool(
        len(data) > 0 and not any(int(result[key]) for key in error_keys)
    )
    return result


def load_frozen_events(
    *,
    path: Path = SOURCE_QUERY_EVENTS_PATH,
    expected_sha256: str = SOURCE_QUERY_EVENTS_SHA256,
    expected_rows: int = EXPECTED_EVENT_COUNT,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    if not path.is_file():
        raise FileNotFoundError(path)
    actual_sha = file_sha256(path)
    if actual_sha != expected_sha256:
        raise ValueError(f"query event source hash drift: {actual_sha} != {expected_sha256}")
    frame = pd.read_csv(path)
    if len(frame) != expected_rows:
        raise ValueError(f"query event row drift: {len(frame)} != {expected_rows}")
    audit = audit_frozen_events(frame)
    audit["source_path"] = str(path)
    audit["source_sha256"] = actual_sha
    audit["expected_rows"] = int(expected_rows)
    if not audit["source_audit_pass"]:
        raise ValueError(f"query event source audit failed: {audit}")
    frame = frame.copy()
    frame["entry_date"] = pd.to_datetime(frame["entry_date"], errors="raise").dt.strftime("%Y-%m-%d")
    return frame, audit


def _mechanical_canary(events: pd.DataFrame) -> pd.DataFrame:
    data = events.copy()
    data["entry_ts"] = pd.to_datetime(data["entry_date"], errors="raise")
    data["exchange"] = data["tqsdk_underlying"].astype(str).str.split(".").str[0]
    newest_by_exchange = (
        data.sort_values(["exchange", "entry_ts", "event_id"])
        .groupby("exchange", as_index=False)
        .tail(1)
        .sort_values("exchange")
    )
    remaining_count = BATCH_SIZE - len(newest_by_exchange)
    if remaining_count < 0:
        raise ValueError("exchange count exceeds canary batch size")
    remainder = (
        data[~data["event_id"].isin(newest_by_exchange["event_id"])]
        .sort_values("event_id")
        .head(remaining_count)
    )
    return pd.concat([newest_by_exchange, remainder], ignore_index=True)


def build_batch_plan(events: pd.DataFrame) -> pd.DataFrame:
    canary = _mechanical_canary(events)
    actual_ids = tuple(canary["event_id"].astype(str))
    if actual_ids != CANARY_EVENT_IDS:
        raise ValueError(f"canary drift: {actual_ids}")
    remainder = events[~events["event_id"].isin(CANARY_EVENT_IDS)].sort_values("event_id")
    ordered = pd.concat(
        [
            events.set_index("event_id").loc[list(CANARY_EVENT_IDS)].reset_index(),
            remainder,
        ],
        ignore_index=True,
    )
    ordered["plan_index"] = np.arange(len(ordered), dtype=int)
    ordered["batch_index"] = ordered["plan_index"] // BATCH_SIZE
    ordered["batch_number"] = ordered["batch_index"] + 1
    ordered["is_canary"] = ordered["plan_index"].lt(BATCH_SIZE)
    if ordered["batch_index"].nunique() != EXPECTED_BATCH_COUNT:
        raise ValueError("batch count drift")
    return ordered


def _normalize_option_class(value: Any) -> str:
    text = str(value or "").strip().upper()
    if text in {"CALL", "C", "1", "看涨"}:
        return "CALL"
    if text in {"PUT", "P", "2", "看跌"}:
        return "PUT"
    return text


def _normalize_timestamp_value(value: Any) -> pd.Timestamp:
    if value is None:
        return pd.NaT
    try:
        if pd.isna(value):
            return pd.NaT
    except (TypeError, ValueError):
        pass
    if isinstance(value, (pd.Timestamp, datetime, date, np.datetime64)):
        result = pd.Timestamp(value)
        if result.tzinfo is not None:
            result = result.tz_convert(CHINA_TZ).tz_localize(None)
        return result
    numeric: float | None = None
    if isinstance(value, (int, float, np.integer, np.floating)):
        numeric = float(value)
    elif re.fullmatch(r"[-+]?\d+(?:\.\d+)?", str(value).strip()):
        numeric = float(str(value).strip())
    if numeric is not None and math.isfinite(numeric):
        magnitude = abs(numeric)
        if magnitude >= 1e17:
            unit = "ns"
        elif magnitude >= 1e14:
            unit = "us"
        elif magnitude >= 1e11:
            unit = "ms"
        else:
            unit = "s"
        result = pd.to_datetime(numeric, unit=unit, errors="coerce", utc=True)
        if pd.isna(result):
            return pd.NaT
        return result.tz_convert(CHINA_TZ).tz_localize(None)
    result = pd.to_datetime(value, errors="coerce")
    if pd.isna(result):
        return pd.NaT
    result = pd.Timestamp(result)
    if result.tzinfo is not None:
        result = result.tz_convert(CHINA_TZ).tz_localize(None)
    return result


def _column(frame: pd.DataFrame, names: Sequence[str], default: Any = np.nan) -> pd.Series:
    for name in names:
        if name in frame.columns:
            return frame[name].copy()
    return pd.Series([default] * len(frame), index=frame.index)


def normalize_option_metadata(untouched: pd.DataFrame) -> pd.DataFrame:
    if untouched.empty:
        return pd.DataFrame(columns=NORMALIZED_COLUMNS)
    data = pd.DataFrame(index=untouched.index)
    data["option_symbol"] = _column(
        untouched, ["option_symbol", "instrument_id", "symbol"]
    ).astype(str)
    data["underlying_symbol"] = _column(
        untouched, ["underlying_symbol", "underlying"]
    ).astype(str)
    data["option_class"] = _column(
        untouched, ["option_class", "call_or_put"]
    ).map(_normalize_option_class)
    data["expire_datetime"] = _column(
        untouched, ["expire_datetime", "expiry_datetime", "expire_date"]
    ).map(_normalize_timestamp_value)
    data["last_exercise_datetime"] = _column(
        untouched,
        ["last_exercise_datetime", "exercise_datetime", "expire_datetime"],
    ).map(_normalize_timestamp_value)
    data["strike_price"] = pd.to_numeric(
        _column(untouched, ["strike_price", "strike"]), errors="coerce"
    )
    data["expired"] = _column(untouched, ["expired"], False).map(_as_bool)
    data["volume_multiple"] = pd.to_numeric(
        _column(untouched, ["volume_multiple", "contract_multiplier"]),
        errors="coerce",
    )
    data["price_tick"] = pd.to_numeric(
        _column(untouched, ["price_tick"]), errors="coerce"
    )
    return data[NORMALIZED_COLUMNS].reset_index(drop=True)


def audit_extracted_metadata(
    symbols: Sequence[str],
    untouched: pd.DataFrame,
    normalized: pd.DataFrame,
    *,
    requested_underlying: str,
) -> dict[str, Any]:
    symbol_list = [str(symbol) for symbol in symbols]
    normalized_symbols = normalized.get(
        "option_symbol", pd.Series(dtype=str)
    ).astype(str)
    expected_set = set(symbol_list)
    observed_set = set(normalized_symbols)
    classes = normalized.get("option_class", pd.Series(dtype=str)).astype(str)
    underlying = normalized.get("underlying_symbol", pd.Series(dtype=str)).astype(str)
    strike = pd.to_numeric(normalized.get("strike_price"), errors="coerce")
    expiry = pd.to_datetime(normalized.get("expire_datetime"), errors="coerce")
    last_exercise = pd.to_datetime(
        normalized.get("last_exercise_datetime"), errors="coerce"
    )
    volume_multiple = pd.to_numeric(normalized.get("volume_multiple"), errors="coerce")
    price_tick = pd.to_numeric(normalized.get("price_tick"), errors="coerce")
    expired = normalized.get("expired", pd.Series(index=normalized.index, dtype=object)).map(_as_bool)
    result = {
        "query_symbol_count": len(symbol_list),
        "query_symbol_duplicate_count": len(symbol_list) - len(expected_set),
        "untouched_row_count": int(len(untouched)),
        "normalized_row_count": int(len(normalized)),
        "row_count_mismatch_count": int(len(untouched) != len(normalized)),
        "symbol_set_missing_count": len(expected_set - observed_set),
        "symbol_set_extra_count": len(observed_set - expected_set),
        "duplicate_option_symbol_count": int(normalized_symbols.duplicated(keep=False).sum()),
        "missing_option_symbol_count": int(normalized_symbols.isin(["", "nan", "None"]).sum()),
        "wrong_underlying_count": int((underlying != requested_underlying).sum()),
        "invalid_option_class_count": int((~classes.isin(["CALL", "PUT"])).sum()),
        "invalid_strike_count": int((strike.isna() | strike.le(0)).sum()),
        "invalid_expiry_count": int(expiry.isna().sum()),
        "invalid_last_exercise_count": int(last_exercise.isna().sum()),
        "expired_true_or_unknown_count": int(sum(value is not False for value in expired)),
        "invalid_volume_multiple_count": int(
            (volume_multiple.isna() | volume_multiple.le(0)).sum()
        ),
        "invalid_price_tick_count": int((price_tick.isna() | price_tick.le(0)).sum()),
    }
    error_keys = [
        key
        for key in result
        if key.endswith("_count")
        and key not in {"query_symbol_count", "untouched_row_count", "normalized_row_count"}
    ]
    result["integrity_pass"] = bool(
        len(symbol_list) > 0
        and len(untouched) > 0
        and len(normalized) > 0
        and not any(int(result[key]) for key in error_keys)
    )
    return result


def compare_normalized_metadata(
    persisted: pd.DataFrame, recomputed: pd.DataFrame
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "normalized_column_mismatch_count": int(
            list(persisted.columns) != NORMALIZED_COLUMNS
            or list(recomputed.columns) != NORMALIZED_COLUMNS
        ),
        "normalized_row_count_mismatch_count": int(len(persisted) != len(recomputed)),
    }
    total_mismatch = 0
    per_column: dict[str, int] = {}
    if result["normalized_column_mismatch_count"] or result["normalized_row_count_mismatch_count"]:
        total_mismatch = max(len(persisted), len(recomputed), 1)
    else:
        for column in NORMALIZED_COLUMNS:
            if column in {"expire_datetime", "last_exercise_datetime"}:
                left = pd.to_datetime(persisted[column], errors="coerce")
                right = pd.to_datetime(recomputed[column], errors="coerce")
                equal = left.eq(right) | (left.isna() & right.isna())
            elif column in {"strike_price", "volume_multiple", "price_tick"}:
                left = pd.to_numeric(persisted[column], errors="coerce").to_numpy(dtype=float)
                right = pd.to_numeric(recomputed[column], errors="coerce").to_numpy(dtype=float)
                equal = pd.Series(
                    np.isclose(left, right, rtol=0.0, atol=0.0, equal_nan=True),
                    index=persisted.index,
                )
            elif column == "expired":
                left = persisted[column].map(_as_bool)
                right = recomputed[column].map(_as_bool)
                equal = left.eq(right) | (left.isna() & right.isna())
            else:
                left = persisted[column].astype(str)
                right = recomputed[column].astype(str)
                equal = left.eq(right)
            mismatch = int((~equal).sum())
            per_column[column] = mismatch
            total_mismatch += mismatch
    result["normalized_value_mismatch_count"] = total_mismatch
    result["normalized_value_mismatch_by_column"] = per_column
    result["normalized_recompute_pass"] = bool(
        result["normalized_column_mismatch_count"] == 0
        and result["normalized_row_count_mismatch_count"] == 0
        and total_mismatch == 0
    )
    return result


def is_cacheable_terminal(status: str) -> bool:
    return str(status) in CACHEABLE_TERMINALS


def redact_message(message: Any, secrets: Sequence[str] = ()) -> str:
    text = str(message or "")
    for secret in sorted({str(item) for item in secrets if str(item)}, key=len, reverse=True):
        text = text.replace(secret, "[REDACTED]")
    text = re.sub(
        r"(?i)\b(username|user|password|passwd|pwd|token|secret)\s*[:=]\s*[^\s,;]+",
        lambda match: f"{match.group(1)}=[REDACTED]",
        text,
    )
    return text[:2000]


def make_attempt_status(
    *,
    terminal_status: str,
    event: Mapping[str, Any],
    symbols: Sequence[str],
    untouched: pd.DataFrame,
    normalized: pd.DataFrame,
    audit: Mapping[str, Any],
    elapsed_seconds: float,
    message: str = "",
    network_called: bool = False,
) -> dict[str, Any]:
    if terminal_status not in ALL_TERMINALS:
        raise ValueError(f"invalid terminal status: {terminal_status}")
    symbols_payload = json.dumps(list(symbols), ensure_ascii=False, separators=(",", ":"))
    return {
        "stage": STAGE,
        "event_id": str(event["event_id"]),
        "vt_symbol": str(event["vt_symbol"]),
        "tqsdk_underlying": str(event["tqsdk_underlying"]),
        "entry_date": str(event["entry_date"]),
        "query_start": str(event["query_start"]),
        "query_end": str(event["query_end"]),
        "terminal_status": terminal_status,
        "cacheable_terminal": is_cacheable_terminal(terminal_status),
        "query_symbol_count": len(symbols),
        "query_symbols_sha256": hashlib.sha256(symbols_payload.encode("utf-8")).hexdigest(),
        "untouched_row_count": int(len(untouched)),
        "normalized_row_count": int(len(normalized)),
        "metadata_integrity_pass": bool(
            audit.get(
                "integrity_pass",
                terminal_status
                in {"empty_chain", "underlying_not_in_option_catalog"},
            )
        ),
        "metadata_audit": dict(audit),
        "elapsed_seconds": round(float(elapsed_seconds), 4),
        "message": redact_message(message),
        "network_called": bool(network_called),
        "credential_values_persisted": False,
        "order_api_called_count": 0,
        "ctp_connected": False,
        "official_live_strategy_changed": False,
        "completed_at": datetime.now().replace(microsecond=0).isoformat(),
    }


def build_output_manifest(
    directory: Path,
    *,
    excluded_names: set[str] | None = None,
) -> pd.DataFrame:
    excluded = excluded_names or set()
    rows = []
    for path in sorted(directory.iterdir()):
        if not path.is_file() or path.name in excluded:
            continue
        rows.append(
            {
                "file": path.name,
                "bytes": path.stat().st_size,
                "sha256": file_sha256(path),
            }
        )
    return pd.DataFrame(rows, columns=["file", "bytes", "sha256"])


def detached_checksum_line(path: Path) -> str:
    return f"{file_sha256(path)}  {path.name}\n"


def _validate_file_manifest(
    directory: Path,
    manifest_name: str,
    checksum_name: str,
) -> tuple[bool, str]:
    manifest_path = directory / manifest_name
    checksum_path = directory / checksum_name
    if not manifest_path.is_file() or not checksum_path.is_file():
        return False, "manifest_or_checksum_missing"
    try:
        manifest = pd.read_csv(manifest_path)
    except Exception as exc:
        return False, f"manifest_parse_failed:{type(exc).__name__}"
    if set(manifest.columns) != {"file", "bytes", "sha256"}:
        return False, "manifest_schema_invalid"
    actual_scope = {
        path.name
        for path in directory.iterdir()
        if path.is_file() and path.name not in {manifest_name, checksum_name}
    }
    if set(manifest["file"].astype(str)) != actual_scope:
        return False, "manifest_scope_mismatch"
    for row in manifest.itertuples(index=False):
        path = directory / str(row.file)
        if not path.is_file():
            return False, f"manifest_file_missing:{row.file}"
        if path.stat().st_size != int(row.bytes):
            return False, f"manifest_bytes_mismatch:{row.file}"
        if file_sha256(path) != str(row.sha256):
            return False, f"manifest_hash_mismatch:{row.file}"
    expected_checksum = detached_checksum_line(manifest_path)
    if checksum_path.read_text(encoding="ascii") != expected_checksum:
        return False, "detached_checksum_mismatch"
    return True, ""


def _valid_sha256(value: Any) -> bool:
    return bool(re.fullmatch(r"[0-9a-f]{64}", str(value or "")))


def _audit_attempt_identity(
    request: Mapping[str, Any],
    status: Mapping[str, Any],
    *,
    event_dir_name: str,
    expected_source_sha256: str | None,
) -> tuple[bool, str]:
    event_id = str(request.get("event_id", ""))
    vt_symbol = str(request.get("vt_symbol", ""))
    entry_date = str(request.get("entry_date", ""))
    query_start = pd.to_datetime(request.get("query_start"), errors="coerce")
    query_end = pd.to_datetime(request.get("query_end"), errors="coerce")
    entry = pd.to_datetime(entry_date, errors="coerce")
    checks = {
        "event_id_path": event_id == event_dir_name,
        "event_id_formula": bool(
            event_id
            and vt_symbol
            and not pd.isna(entry)
            and event_id == event_id_for(vt_symbol, entry)
        ),
        "tqsdk_underlying": str(request.get("tqsdk_underlying", ""))
        == _to_tqsdk_underlying(vt_symbol),
        "query_expired": request.get("query_options", {}).get("expired") is False,
        "query_start": bool(
            not pd.isna(query_start)
            and not pd.isna(entry)
            and query_start.normalize() == entry.normalize()
            and query_start.strftime("%H:%M:%S") == "00:00:00"
        ),
        "query_end": bool(
            not pd.isna(query_end)
            and not pd.isna(entry)
            and query_end.normalize() == entry.normalize()
            and query_end.strftime("%H:%M:%S") == "23:59:59"
        ),
        "status_event": str(status.get("event_id", "")) == event_id,
        "status_symbol": str(status.get("vt_symbol", "")) == vt_symbol,
        "status_underlying": str(status.get("tqsdk_underlying", ""))
        == str(request.get("tqsdk_underlying", "")),
        "status_entry": str(status.get("entry_date", "")) == entry_date,
        "status_start": str(status.get("query_start", ""))
        == str(request.get("query_start", "")),
        "status_end": str(status.get("query_end", ""))
        == str(request.get("query_end", "")),
        "source_sha_format": _valid_sha256(request.get("source_query_events_sha256")),
        "source_sha_expected": bool(
            expected_source_sha256 is None
            or request.get("source_query_events_sha256") == expected_source_sha256
        ),
        "stage131_manifest": request.get("stage131_manifest_sha256")
        == SOURCE_STAGE131_MANIFEST_SHA256,
        "tool_sha": _valid_sha256(request.get("tool_sha256")),
        "test_sha": _valid_sha256(request.get("test_sha256")),
        "predecl_sha": _valid_sha256(request.get("predecl_sha256")),
    }
    failed = [name for name, passed in checks.items() if not passed]
    return not failed, "|".join(failed)


def validate_attempt_dir(
    attempt_dir: Path,
    *,
    expected_source_sha256: str | None = None,
) -> dict[str, Any]:
    required = {
        ATTEMPT_REQUEST_NAME,
        ATTEMPT_SYMBOLS_NAME,
        ATTEMPT_STATUS_NAME,
        ATTEMPT_MANIFEST_NAME,
        ATTEMPT_CHECKSUM_NAME,
    }
    missing = sorted(name for name in required if not (attempt_dir / name).is_file())
    if missing:
        return {
            "attempt_integrity_pass": False,
            "cacheable": False,
            "terminal_status": "missing",
            "blocking_reason": f"missing:{'|'.join(missing)}",
        }
    manifest_ok, manifest_reason = _validate_file_manifest(
        attempt_dir, ATTEMPT_MANIFEST_NAME, ATTEMPT_CHECKSUM_NAME
    )
    try:
        request = json.loads((attempt_dir / ATTEMPT_REQUEST_NAME).read_text(encoding="utf-8"))
        status = json.loads((attempt_dir / ATTEMPT_STATUS_NAME).read_text(encoding="utf-8"))
        symbols = json.loads((attempt_dir / ATTEMPT_SYMBOLS_NAME).read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "attempt_integrity_pass": False,
            "cacheable": False,
            "terminal_status": "missing",
            "blocking_reason": f"json_parse_failed:{type(exc).__name__}",
        }
    terminal = str(status.get("terminal_status", "missing"))
    event_id = str(status.get("event_id", ""))
    semantic_reason = ""
    identity_ok, identity_reason = _audit_attempt_identity(
        request,
        status,
        event_dir_name=attempt_dir.parent.name,
        expected_source_sha256=expected_source_sha256,
    )
    semantic_ok = bool(
        terminal in ALL_TERMINALS
        and isinstance(symbols, list)
        and identity_ok
        and int(status.get("query_symbol_count", -1)) == len(symbols)
        and bool(status.get("cacheable_terminal", False))
        == is_cacheable_terminal(terminal)
    )
    if not semantic_ok:
        semantic_reason = f"attempt_identity_or_status_semantics_invalid:{identity_reason}"
    if terminal == "extracted":
        metadata_files_ready = all(
            (attempt_dir / name).is_file()
            for name in (
                UNTOUCHED_METADATA_NAME,
                UNTOUCHED_SCHEMA_NAME,
                NORMALIZED_METADATA_NAME,
            )
        )
        normalized_comparison: dict[str, Any] = {}
        if metadata_files_ready:
            try:
                untouched = pd.read_csv(attempt_dir / UNTOUCHED_METADATA_NAME)
                normalized = pd.read_csv(attempt_dir / NORMALIZED_METADATA_NAME)
                schema = json.loads(
                    (attempt_dir / UNTOUCHED_SCHEMA_NAME).read_text(encoding="utf-8")
                )
                recomputed = audit_extracted_metadata(
                    symbols,
                    untouched,
                    normalized,
                    requested_underlying=str(request.get("tqsdk_underlying", "")),
                )
                normalized_recomputed = normalize_option_metadata(untouched)
                normalized_comparison = compare_normalized_metadata(
                    normalized,
                    normalized_recomputed,
                )
                metadata_semantics_ok = bool(
                    recomputed["integrity_pass"]
                    and normalized_comparison["normalized_recompute_pass"]
                    and schema.get("columns") == [str(column) for column in untouched.columns]
                    and int(status.get("untouched_row_count", -1)) == len(untouched)
                    and int(status.get("normalized_row_count", -1)) == len(normalized)
                    and bool(status.get("metadata_integrity_pass", False))
                )
            except Exception:
                metadata_semantics_ok = False
        else:
            metadata_semantics_ok = False
        semantic_ok = bool(semantic_ok and len(symbols) > 0 and metadata_semantics_ok)
        if not metadata_semantics_ok:
            semantic_reason = (
                "normalized_recompute_mismatch"
                if metadata_files_ready
                and not normalized_comparison.get("normalized_recompute_pass", False)
                else "metadata_semantics_recompute_failed"
            )
    elif terminal == "empty_chain":
        unexpected_metadata = any(
            (attempt_dir / name).exists()
            for name in (
                UNTOUCHED_METADATA_NAME,
                UNTOUCHED_SCHEMA_NAME,
                NORMALIZED_METADATA_NAME,
            )
        )
        semantic_ok = bool(
            semantic_ok
            and len(symbols) == 0
            and not unexpected_metadata
            and int(status.get("untouched_row_count", -1)) == 0
            and int(status.get("normalized_row_count", -1)) == 0
            and bool(status.get("metadata_integrity_pass", False))
        )
        if unexpected_metadata:
            semantic_reason = "empty_chain_contains_metadata_files"
    elif terminal == "underlying_not_in_option_catalog":
        unexpected_metadata = any(
            (attempt_dir / name).exists()
            for name in (
                UNTOUCHED_METADATA_NAME,
                UNTOUCHED_SCHEMA_NAME,
                NORMALIZED_METADATA_NAME,
            )
        )
        exact_proof = (
            classify_query_exception(
                str(status.get("message", "")),
                requested_underlying=str(request.get("tqsdk_underlying", "")),
            )
            == "underlying_not_in_option_catalog"
        )
        semantic_ok = bool(
            semantic_ok
            and exact_proof
            and len(symbols) == 0
            and not unexpected_metadata
            and int(status.get("untouched_row_count", -1)) == 0
            and int(status.get("normalized_row_count", -1)) == 0
            and bool(status.get("metadata_integrity_pass", False))
        )
        if not exact_proof:
            semantic_reason = "catalog_missing_exact_proof_absent"
    integrity = bool(manifest_ok and semantic_ok)
    return {
        "attempt_integrity_pass": integrity,
        "cacheable": bool(integrity and is_cacheable_terminal(terminal)),
        "terminal_status": terminal,
        "event_id": event_id,
        "query_symbol_count": int(status.get("query_symbol_count", 0) or 0),
        "untouched_row_count": int(status.get("untouched_row_count", 0) or 0),
        "normalized_row_count": int(status.get("normalized_row_count", 0) or 0),
        "elapsed_seconds": float(status.get("elapsed_seconds", 0.0) or 0.0),
        "network_called": bool(status.get("network_called", False)),
        "blocking_reason": "" if integrity else (manifest_reason or semantic_reason or "attempt_semantics_invalid"),
        "attempt_path": str(attempt_dir),
        "producer_tool_sha256": str(request.get("tool_sha256", "")),
        "producer_test_sha256": str(request.get("test_sha256", "")),
        "producer_predecl_sha256": str(request.get("predecl_sha256", "")),
    }


def _next_attempt_number(event_dir: Path) -> int:
    numbers = []
    for path in event_dir.glob("attempt_*"):
        if not path.is_dir():
            continue
        match = re.fullmatch(r"attempt_(\d{4})", path.name)
        if match:
            numbers.append(int(match.group(1)))
    return max(numbers, default=0) + 1


def _sdk_version() -> str:
    try:
        return importlib.metadata.version("tqsdk")
    except importlib.metadata.PackageNotFoundError:
        return "not-installed"


def publish_attempt(
    *,
    attempts_root: Path,
    event: Mapping[str, Any],
    source_sha256: str,
    symbols: Sequence[str],
    untouched: pd.DataFrame,
    normalized: pd.DataFrame,
    status: Mapping[str, Any],
) -> Path:
    event_id = str(event["event_id"])
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", event_id):
        raise ValueError(f"unsafe event_id: {event_id!r}")
    event_dir = attempts_root / event_id
    event_dir.mkdir(parents=True, exist_ok=True)
    attempt_number = _next_attempt_number(event_dir)
    attempt_name = f"attempt_{attempt_number:04d}"
    final_dir = event_dir / attempt_name
    temp_dir = event_dir / f".tmp_{attempt_name}_{os.getpid()}_{uuid.uuid4().hex}"
    temp_dir.mkdir()
    try:
        request = {
            "stage": STAGE,
            "event_id": event_id,
            "vt_symbol": str(event["vt_symbol"]),
            "tqsdk_underlying": str(event["tqsdk_underlying"]),
            "product_vt_symbol": str(event.get("product_vt_symbol", "")),
            "entry_date": str(event["entry_date"]),
            "query_start": str(event["query_start"]),
            "query_end": str(event["query_end"]),
            "query_options": {"expired": False},
            "source_query_events_sha256": source_sha256,
            "stage131_manifest_sha256": SOURCE_STAGE131_MANIFEST_SHA256,
            "tool_sha256": file_sha256(TOOL_PATH),
            "test_sha256": file_sha256(TEST_PATH),
            "predecl_sha256": file_sha256(PREDECL_PATH),
            "tqsdk_version": _sdk_version(),
            "python_version": sys.version.split()[0],
            "credential_values_persisted": False,
            "attempt_number": attempt_number,
            "started_at": datetime.now().replace(microsecond=0).isoformat(),
        }
        _write_json(request, temp_dir / ATTEMPT_REQUEST_NAME)
        _write_json(list(symbols), temp_dir / ATTEMPT_SYMBOLS_NAME)
        if not untouched.empty:
            _write_csv(untouched, temp_dir / UNTOUCHED_METADATA_NAME)
            _write_json(
                {
                    "columns": [str(column) for column in untouched.columns],
                    "dtypes": {
                        str(column): str(dtype)
                        for column, dtype in untouched.dtypes.items()
                    },
                },
                temp_dir / UNTOUCHED_SCHEMA_NAME,
            )
            _write_csv(normalized, temp_dir / NORMALIZED_METADATA_NAME)
        status_payload = dict(status)
        status_payload["attempt_number"] = attempt_number
        _write_json(status_payload, temp_dir / ATTEMPT_STATUS_NAME)
        manifest = build_output_manifest(
            temp_dir,
            excluded_names={ATTEMPT_MANIFEST_NAME, ATTEMPT_CHECKSUM_NAME},
        )
        _write_csv(manifest, temp_dir / ATTEMPT_MANIFEST_NAME)
        (temp_dir / ATTEMPT_CHECKSUM_NAME).write_text(
            detached_checksum_line(temp_dir / ATTEMPT_MANIFEST_NAME),
            encoding="ascii",
        )
        validation = validate_attempt_dir(
            temp_dir, expected_source_sha256=source_sha256
        )
        if not validation["attempt_integrity_pass"]:
            raise RuntimeError(f"attempt publish validation failed: {validation}")
        if temp_dir.stat().st_dev != event_dir.stat().st_dev:
            raise RuntimeError("cross-device attempt publish blocked")
        os.replace(temp_dir, final_dir)
    except Exception:
        if temp_dir.exists():
            quarantine = event_dir / f".quarantine_{attempt_name}_{uuid.uuid4().hex}"
            os.replace(temp_dir, quarantine)
        raise
    return final_dir


def find_cacheable_attempt(
    attempts_root: Path,
    event_id: str,
    *,
    expected_source_sha256: str | None = None,
) -> Path | None:
    event_dir = attempts_root / str(event_id)
    if not event_dir.is_dir():
        return None
    for attempt_dir in sorted(event_dir.glob("attempt_*"), reverse=True):
        validation = validate_attempt_dir(
            attempt_dir, expected_source_sha256=expected_source_sha256
        )
        if validation["cacheable"]:
            return attempt_dir
    return None


def inventory_attempts(
    attempts_root: Path,
    *,
    expected_source_sha256: str | None = None,
) -> pd.DataFrame:
    rows = []
    if not attempts_root.is_dir():
        return pd.DataFrame(columns=ATTEMPT_INVENTORY_COLUMNS)
    for event_dir in sorted(attempts_root.iterdir()):
        if not event_dir.is_dir():
            continue
        for attempt_dir in sorted(event_dir.glob("attempt_*")):
            validation = validate_attempt_dir(
                attempt_dir, expected_source_sha256=expected_source_sha256
            )
            rows.append(
                {
                    "event_id": event_dir.name,
                    "attempt_name": attempt_dir.name,
                    **validation,
                    "attempt_manifest_sha256": (
                        file_sha256(attempt_dir / ATTEMPT_MANIFEST_NAME)
                        if (attempt_dir / ATTEMPT_MANIFEST_NAME).is_file()
                        else ""
                    ),
                }
            )
    return pd.DataFrame(rows, columns=ATTEMPT_INVENTORY_COLUMNS)


def build_event_terminal_status(
    plan: pd.DataFrame, attempt_inventory: pd.DataFrame
) -> pd.DataFrame:
    attempts_by_event: dict[str, pd.DataFrame] = {}
    if not attempt_inventory.empty:
        attempts_by_event = {
            str(event_id): group.sort_values("attempt_name")
            for event_id, group in attempt_inventory.groupby("event_id")
        }
    rows = []
    for event in plan.itertuples(index=False):
        event_id = str(event.event_id)
        group = attempts_by_event.get(event_id)
        selected: Mapping[str, Any] = {}
        if group is not None and not group.empty:
            cacheable = group[group["cacheable"].astype(bool)]
            selected_row = (
                cacheable.iloc[-1]
                if not cacheable.empty
                else group.iloc[-1]
            )
            selected = selected_row.to_dict()
        rows.append(
            {
                "event_id": event_id,
                "vt_symbol": str(event.vt_symbol),
                "tqsdk_underlying": str(event.tqsdk_underlying),
                "product_vt_symbol": str(event.product_vt_symbol),
                "entry_date": str(event.entry_date),
                "exchange": str(event.tqsdk_underlying).split(".", 1)[0],
                "batch_index": int(event.batch_index),
                "batch_number": int(event.batch_number),
                "is_canary": bool(event.is_canary),
                "terminal_status": str(selected.get("terminal_status", "missing")),
                "cacheable": bool(selected.get("cacheable", False)),
                "attempt_path": str(selected.get("attempt_path", "")),
                "attempt_integrity_pass": bool(
                    selected.get("attempt_integrity_pass", False)
                ),
                "query_symbol_count": int(selected.get("query_symbol_count", 0) or 0),
                "untouched_row_count": int(selected.get("untouched_row_count", 0) or 0),
                "normalized_row_count": int(selected.get("normalized_row_count", 0) or 0),
                "elapsed_seconds": float(selected.get("elapsed_seconds", 0.0) or 0.0),
                "blocking_reason": str(selected.get("blocking_reason", "")),
            }
        )
    return pd.DataFrame(rows)


def audit_canary(event_status: pd.DataFrame) -> dict[str, Any]:
    canary = event_status[event_status["is_canary"].astype(bool)].copy()
    cacheable_canary = canary[canary["cacheable"].astype(bool)]
    status_counts = cacheable_canary["terminal_status"].value_counts().to_dict()
    result = {
        "canary_event_count": int(len(canary)),
        "canary_cacheable_count": int(canary["cacheable"].astype(bool).sum()),
        "canary_extracted_count": int(status_counts.get("extracted", 0)),
        "canary_empty_chain_count": int(status_counts.get("empty_chain", 0)),
        "canary_catalog_missing_count": int(
            status_counts.get("underlying_not_in_option_catalog", 0)
        ),
        "canary_failed_count": int(
            len(canary) - len(cacheable_canary)
        ),
        "canary_integrity_failure_count": int(
            (~canary["attempt_integrity_pass"].astype(bool)).sum()
        ),
    }
    result["canary_gate_pass"] = bool(
        result["canary_event_count"] == BATCH_SIZE
        and result["canary_cacheable_count"] == BATCH_SIZE
        and result["canary_extracted_count"] >= 1
        and result["canary_failed_count"] == 0
        and result["canary_integrity_failure_count"] == 0
    )
    return result


class EventTimeoutError(TimeoutError):
    pass


@contextmanager
def _wall_clock_timeout(seconds: int):
    if seconds <= 0 or not hasattr(signal, "SIGALRM"):
        yield
        return

    def handler(_signum: int, _frame: Any) -> None:
        raise EventTimeoutError(f"event exceeded {seconds}s")

    previous_handler = signal.signal(signal.SIGALRM, handler)
    signal.setitimer(signal.ITIMER_REAL, float(seconds))
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0.0)
        signal.signal(signal.SIGALRM, previous_handler)


def _credentials() -> tuple[str, str]:
    return (
        str(SETTINGS.get("datafeed.username", "")).strip(),
        str(SETTINGS.get("datafeed.password", "")).strip(),
    )


def _authentication_error(message: str) -> bool:
    return bool(
        re.search(
            r"(?i)(auth|authentication|permission|unauthorized|username|password|登录|认证|权限|用户名|密码)",
            message,
        )
    )


def _catalog_missing_error(message: str) -> bool:
    text = str(message or "")
    return bool(
        "failed to execute graphql operation" in text.lower()
        and "instrument_id" in text
        and "contains non-existent instrument" in text.lower()
    )


def _catalog_missing_instruments(message: str) -> list[str]:
    return re.findall(
        r"non-existent instrument:\s*([^\]\s,;]+)",
        str(message or ""),
        flags=re.IGNORECASE,
    )


def classify_query_exception(
    message: str,
    *,
    requested_underlying: str | None = None,
) -> str:
    instruments = _catalog_missing_instruments(message)
    catalog_matches_request = bool(
        _catalog_missing_error(message)
        and (
            requested_underlying is None
            or instruments == [str(requested_underlying)]
        )
    )
    if catalog_matches_request:
        return "underlying_not_in_option_catalog"
    if _authentication_error(message):
        return "authentication_failed"
    return "query_failed"


FetchResult = tuple[
    str,
    list[str],
    pd.DataFrame,
    pd.DataFrame,
    dict[str, Any],
    str,
    float,
]


def fetch_option_metadata_network(
    event: Mapping[str, Any], max_seconds: int
) -> FetchResult:
    username, password = _credentials()
    started = time.time()
    if not username or not password:
        return (
            "authentication_failed",
            [],
            pd.DataFrame(),
            pd.DataFrame(columns=NORMALIZED_COLUMNS),
            {},
            "TqSdk credentials missing",
            time.time() - started,
        )
    api = None
    symbols: list[str] = []
    untouched = pd.DataFrame()
    normalized = pd.DataFrame(columns=NORMALIZED_COLUMNS)
    audit: dict[str, Any] = {}
    terminal = "query_failed"
    message = ""
    try:
        from tqsdk import TqApi, TqAuth, TqBacktest, TqSim

        with _wall_clock_timeout(max_seconds):
            try:
                start_dt = pd.Timestamp(event["query_start"]).to_pydatetime()
                end_dt = pd.Timestamp(event["query_end"]).to_pydatetime()
                api = TqApi(
                    TqSim(),
                    backtest=TqBacktest(start_dt=start_dt, end_dt=end_dt),
                    auth=TqAuth(username, password),
                    disable_print=True,
                )
                symbols = [
                    str(symbol)
                    for symbol in api.query_options(
                        str(event["tqsdk_underlying"]), expired=False
                    )
                ]
                if not symbols:
                    terminal = "empty_chain"
                else:
                    untouched = pd.DataFrame(api.query_symbol_info(symbols)).copy()
                    normalized = normalize_option_metadata(untouched)
                    audit = audit_extracted_metadata(
                        symbols,
                        untouched,
                        normalized,
                        requested_underlying=str(event["tqsdk_underlying"]),
                    )
                    terminal = (
                        "extracted" if audit["integrity_pass"] else "integrity_failed"
                    )
            finally:
                if api is not None:
                    api.close()
                    api = None
    except EventTimeoutError as exc:
        terminal = "timeout"
        message = redact_message(exc, [username, password])
    except Exception as exc:
        message = redact_message(exc, [username, password])
        terminal = classify_query_exception(
            message,
            requested_underlying=str(event["tqsdk_underlying"]),
        )
    return terminal, symbols, untouched, normalized, audit, message, time.time() - started


def run_event_selection(
    selection: pd.DataFrame,
    *,
    attempts_root: Path,
    source_sha256: str,
    fetcher: Callable[[Mapping[str, Any], int], FetchResult],
    max_seconds: int,
    force_retry: bool = False,
) -> dict[str, Any]:
    new_attempt_count = 0
    cached_skip_count = 0
    auth_stop = False
    for row in selection.itertuples(index=False):
        event = row._asdict()
        event_id = str(event["event_id"])
        if not force_retry and find_cacheable_attempt(
            attempts_root,
            event_id,
            expected_source_sha256=source_sha256,
        ) is not None:
            cached_skip_count += 1
            continue
        terminal, symbols, untouched, normalized, audit, message, elapsed = fetcher(
            event, max_seconds
        )
        if terminal == "extracted" and not audit.get("integrity_pass"):
            terminal = "integrity_failed"
        status = make_attempt_status(
            terminal_status=terminal,
            event=event,
            symbols=symbols,
            untouched=untouched,
            normalized=normalized,
            audit=audit,
            elapsed_seconds=elapsed,
            message=message,
            network_called=True,
        )
        publish_attempt(
            attempts_root=attempts_root,
            event=event,
            source_sha256=source_sha256,
            symbols=symbols,
            untouched=untouched,
            normalized=normalized,
            status=status,
        )
        new_attempt_count += 1
        if terminal == "authentication_failed":
            auth_stop = True
            break
    return {
        "new_attempt_count": new_attempt_count,
        "cached_skip_count": cached_skip_count,
        "authentication_stop": auth_stop,
        "force_retry": bool(force_retry),
    }


def _coverage_summary(event_status: pd.DataFrame, group_column: str) -> pd.DataFrame:
    data = event_status.copy()
    rows = []
    for value, group in data.groupby(group_column, dropna=False):
        cacheable_group = group[group["cacheable"].astype(bool)]
        counts = cacheable_group["terminal_status"].value_counts().to_dict()
        rows.append(
            {
                group_column: value,
                "event_count": int(len(group)),
                "cacheable_count": int(group["cacheable"].astype(bool).sum()),
                "extracted_count": int(counts.get("extracted", 0)),
                "empty_chain_count": int(counts.get("empty_chain", 0)),
                "catalog_missing_count": int(
                    counts.get("underlying_not_in_option_catalog", 0)
                ),
                "failed_or_missing_count": int(
                    len(group) - len(cacheable_group)
                ),
                "metadata_row_count": int(
                    cacheable_group["normalized_row_count"].sum()
                ),
                "metadata_coverage_ratio": float(
                    counts.get("extracted", 0) / len(group)
                ),
            }
        )
    return pd.DataFrame(rows)


def summarize_terminal_statuses(
    event_status: pd.DataFrame,
    *,
    denominator: int,
) -> dict[str, Any]:
    cacheable = event_status[event_status["cacheable"].astype(bool)]
    counts = cacheable["terminal_status"].value_counts().to_dict()
    cacheable_count = int(len(cacheable))
    extracted_count = int(counts.get("extracted", 0))
    return {
        "cacheable_event_count": cacheable_count,
        "extracted_event_count": extracted_count,
        "empty_chain_event_count": int(counts.get("empty_chain", 0)),
        "catalog_missing_event_count": int(
            counts.get("underlying_not_in_option_catalog", 0)
        ),
        "failed_or_missing_event_count": int(
            denominator - cacheable_count
        ),
        "request_ledger_completion_ratio": float(cacheable_count / denominator),
        "metadata_coverage_ratio": float(extracted_count / denominator),
    }


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_无记录_"
    view = frame.head(max_rows).copy() if max_rows else frame.copy()
    return view.to_markdown(index=False)


def _write_root_outputs(
    *,
    plan: pd.DataFrame,
    source_audit: Mapping[str, Any],
    attempt_inventory: pd.DataFrame,
    event_status: pd.DataFrame,
    decision: Mapping[str, Any],
) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    year_status = event_status.assign(
        entry_year=pd.to_datetime(event_status["entry_date"]).dt.year
    )
    year_coverage = _coverage_summary(year_status, "entry_year")
    product_coverage = _coverage_summary(event_status, "product_vt_symbol")
    exchange_coverage = _coverage_summary(event_status, "exchange")
    _atomic_write_csv(plan, BATCH_PLAN_PATH)
    _atomic_write_csv(pd.DataFrame([source_audit]), SOURCE_AUDIT_PATH)
    _atomic_write_csv(attempt_inventory, ATTEMPT_INVENTORY_PATH)
    _atomic_write_csv(event_status, EVENT_STATUS_PATH)
    _atomic_write_csv(year_coverage, YEAR_COVERAGE_PATH)
    _atomic_write_csv(product_coverage, PRODUCT_COVERAGE_PATH)
    _atomic_write_csv(exchange_coverage, EXCHANGE_COVERAGE_PATH)
    _atomic_write_json(decision, DECISION_PATH)
    lineage = {
        "stage": STAGE,
        "tool": {"path": str(TOOL_PATH), "sha256": file_sha256(TOOL_PATH)},
        "test": {"path": str(TEST_PATH), "sha256": file_sha256(TEST_PATH)},
        "predecl": {"path": str(PREDECL_PATH), "sha256": file_sha256(PREDECL_PATH)},
        "source_query_events": {
            "path": str(SOURCE_QUERY_EVENTS_PATH),
            "sha256": SOURCE_QUERY_EVENTS_SHA256,
            "rows": EXPECTED_EVENT_COUNT,
        },
        "stage131_manifest_sha256": SOURCE_STAGE131_MANIFEST_SHA256,
        "event_attempt_manifests": (
            attempt_inventory[
                [
                    "event_id",
                    "attempt_name",
                    "attempt_manifest_sha256",
                    "producer_tool_sha256",
                    "producer_test_sha256",
                    "producer_predecl_sha256",
                ]
            ].to_dict("records")
            if not attempt_inventory.empty
            else []
        ),
    }
    _atomic_write_json(lineage, LINEAGE_PATH)
    canary = dict(decision.get("canary_audit", {}))
    report = "\n".join(
        [
            "# Stage132 当前 C9 真实事件期权 metadata 原子分批采集",
            "",
            f"- 决策：`{decision['decision']}`",
            f"- 运行模式/网络：`{decision['run_mode']}` / `{decision['network_enabled']}`",
            f"- 事件/缓存完成：`{decision['event_count']}/{decision['cacheable_event_count']}`",
            f"- extracted/empty/catalog-missing/failure-or-missing：`{decision['extracted_event_count']}/{decision['empty_chain_event_count']}/{decision['catalog_missing_event_count']}/{decision['failed_or_missing_event_count']}`",
            f"- request-ledger completion / metadata coverage：`{decision['request_ledger_completion_ratio']:.6f}/{decision['metadata_coverage_ratio']:.6f}`（固定分母 365）",
            f"- canary gate：`{canary.get('canary_gate_pass', False)}`",
            "- 本阶段只采 metadata；未获取 premium/bar、未选 strike/DTE、未回测、未改实盘。",
            "",
            "## Canary Audit",
            "",
            _md_table(pd.DataFrame([canary])),
            "",
            "## Coverage by Year",
            "",
            _md_table(year_coverage),
            "",
            "## Coverage by Exchange",
            "",
            _md_table(exchange_coverage),
            "",
            "## 边界",
            "",
            "- empty_chain 不等于交易所级未上市结论，必须后续结合产品上市日期审计。",
            "- metadata complete 也不等于 premium、流动性、分钟可成交或保护策略有效。",
            "- `ready_for_option_strategy_ab=false` 固定不变。",
        ]
    ) + "\n"
    _atomic_write_bytes(REPORT_PATH, report.encode("utf-8"))
    manifest = build_output_manifest(
        OUTPUT_DIR,
        excluded_names={ROOT_MANIFEST_PATH.name, ROOT_CHECKSUM_PATH.name},
    )
    _atomic_write_csv(manifest, ROOT_MANIFEST_PATH)
    _atomic_write_bytes(
        ROOT_CHECKSUM_PATH,
        detached_checksum_line(ROOT_MANIFEST_PATH).encode("ascii"),
    )


def main() -> dict[str, Any]:
    if RUN_MODE not in {"plan", "canary", "remaining", "all"}:
        raise ValueError(f"invalid STAGE132_RUN_MODE: {RUN_MODE}")
    events, source_audit = load_frozen_events()
    plan = build_batch_plan(events)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    before_inventory = inventory_attempts(
        ATTEMPTS_ROOT, expected_source_sha256=SOURCE_QUERY_EVENTS_SHA256
    )
    before_status = build_event_terminal_status(plan, before_inventory)
    before_canary = audit_canary(before_status)
    username, password = _credentials()
    credentials_ready = bool(username and password)
    run_audit = {
        "new_attempt_count": 0,
        "cached_skip_count": 0,
        "authentication_stop": False,
    }
    network_permitted = bool(ENABLE_NETWORK and RUN_MODE != "plan" and credentials_ready)

    if network_permitted:
        if RUN_MODE == "canary":
            selection = plan[plan["is_canary"].astype(bool)]
            run_audit = run_event_selection(
                selection,
                attempts_root=ATTEMPTS_ROOT,
                source_sha256=SOURCE_QUERY_EVENTS_SHA256,
                fetcher=fetch_option_metadata_network,
                max_seconds=MAX_SECONDS_PER_EVENT,
                force_retry=FORCE_CANARY_RETRY,
            )
        elif RUN_MODE == "remaining":
            if not before_canary["canary_gate_pass"]:
                run_audit["blocked_reason"] = "canary_gate_not_passed"
            else:
                selection = plan[~plan["is_canary"].astype(bool)]
                run_audit = run_event_selection(
                    selection,
                    attempts_root=ATTEMPTS_ROOT,
                    source_sha256=SOURCE_QUERY_EVENTS_SHA256,
                    fetcher=fetch_option_metadata_network,
                    max_seconds=MAX_SECONDS_PER_EVENT,
                )
        elif RUN_MODE == "all":
            canary_selection = plan[plan["is_canary"].astype(bool)]
            run_audit = run_event_selection(
                canary_selection,
                attempts_root=ATTEMPTS_ROOT,
                source_sha256=SOURCE_QUERY_EVENTS_SHA256,
                fetcher=fetch_option_metadata_network,
                max_seconds=MAX_SECONDS_PER_EVENT,
                force_retry=FORCE_CANARY_RETRY,
            )
            mid_inventory = inventory_attempts(
                ATTEMPTS_ROOT,
                expected_source_sha256=SOURCE_QUERY_EVENTS_SHA256,
            )
            mid_status = build_event_terminal_status(plan, mid_inventory)
            if audit_canary(mid_status)["canary_gate_pass"]:
                remaining_audit = run_event_selection(
                    plan[~plan["is_canary"].astype(bool)],
                    attempts_root=ATTEMPTS_ROOT,
                    source_sha256=SOURCE_QUERY_EVENTS_SHA256,
                    fetcher=fetch_option_metadata_network,
                    max_seconds=MAX_SECONDS_PER_EVENT,
                )
                run_audit = {
                    "new_attempt_count": int(run_audit["new_attempt_count"])
                    + int(remaining_audit["new_attempt_count"]),
                    "cached_skip_count": int(run_audit["cached_skip_count"])
                    + int(remaining_audit["cached_skip_count"]),
                    "authentication_stop": bool(
                        run_audit["authentication_stop"]
                        or remaining_audit["authentication_stop"]
                    ),
                }
            else:
                run_audit["blocked_reason"] = "canary_gate_not_passed"

    attempt_inventory = inventory_attempts(
        ATTEMPTS_ROOT, expected_source_sha256=SOURCE_QUERY_EVENTS_SHA256
    )
    event_status = build_event_terminal_status(plan, attempt_inventory)
    canary_audit = audit_canary(event_status)
    terminal_summary = summarize_terminal_statuses(
        event_status, denominator=EXPECTED_EVENT_COUNT
    )
    cacheable_count = int(terminal_summary["cacheable_event_count"])
    complete = cacheable_count == EXPECTED_EVENT_COUNT
    if RUN_MODE == "plan":
        decision_name = "stage132_plan_ready_for_canary"
    elif RUN_MODE == "canary":
        decision_name = (
            "stage132_canary_ready_for_independent_review"
            if canary_audit["canary_gate_pass"]
            else "stage132_canary_failed_close"
        )
    else:
        decision_name = (
            "stage132_metadata_batches_complete_ready_for_coverage_review"
            if complete
            else "stage132_metadata_batches_incomplete_close"
        )
    if RUN_MODE != "plan" and not network_permitted and not complete:
        decision_name = "stage132_network_not_permitted_close"

    decision = {
        "stage": STAGE,
        "stage_id": STAGE_ID,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().replace(microsecond=0).isoformat(),
        "decision": decision_name,
        "run_mode": RUN_MODE,
        "network_enabled": bool(ENABLE_NETWORK),
        "network_permitted": network_permitted,
        "force_canary_retry": bool(FORCE_CANARY_RETRY),
        "credentials_ready": credentials_ready,
        "tqsdk_version": _sdk_version(),
        "source_audit": source_audit,
        "run_audit": run_audit,
        "canary_audit": canary_audit,
        "event_count": int(len(event_status)),
        **terminal_summary,
        "request_ledger_complete": complete,
        "metadata_acquisition_complete": complete,
        "ready_for_metadata_coverage_review": complete,
        "ready_for_premium_acquisition": False,
        "ready_for_option_strategy_ab": False,
        "premium_or_bars_downloaded": False,
        "strategy_rule_created": False,
        "true_engine_run": False,
        "order_api_called_count": 0,
        "ctp_connected": False,
        "official_live_strategy_changed": False,
        "credential_values_persisted": False,
        "outcome_columns_read": False,
        "overfit_before": "否；事件全集与 canary 在 metadata 返回前冻结，不读取收益结果。",
        "overfit_after": "待独立审查；metadata 覆盖不得解释为保护策略有效。",
        "continue_value_before": "有；逐事件 metadata 是真实 premium/流动性审计的必要前置。",
        "continue_value_after": (
            "有；进入独立覆盖审查。" if complete else "有条件；先解决 canary/缺失终态，不删事件救覆盖。"
        ),
    }
    _write_root_outputs(
        plan=plan,
        source_audit=source_audit,
        attempt_inventory=attempt_inventory,
        event_status=event_status,
        decision=decision,
    )
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    return decision


if __name__ == "__main__":
    main()
