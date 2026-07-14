from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
import argparse
import hashlib
from io import StringIO
import json
import math
import os
from pathlib import Path
import re
import shutil
import signal
import tempfile
import time
from typing import Any, Callable, Iterable

import numpy as np
import pandas as pd


ROOT_DIR = Path(__file__).resolve().parents[4]
LINE_ID = "futures_trend_l1_topbook_entry_quality"
STAGE_ID = "stage001_l1_tick_canary"
LINE_DIR = ROOT_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / STAGE_ID
EVENTS_PATH = (
    ROOT_DIR
    / "research"
    / "lines"
    / "futures_trend_rebuilt_c9_15w_v2_optimization"
    / "outputs"
    / "stage131_c9_event_targeted_option_acquisition_manifest"
    / "rebuilt_c9_v2_stage131_c9_event_targeted_option_acquisition_manifest_"
    "query_events_stage131_c9_event_targeted_option_acquisition_manifest_v1.csv"
)
CURVE_PATH = (
    ROOT_DIR
    / "examples"
    / "portfolio_backtesting"
    / "backtest_outputs"
    / "qmt_roll_stage847_stage830_c4_stop_retry_engine_curve_"
    "stage847_stage830_c4_stop_retry_engine_v1.csv"
)

EXPECTED_EVENTS_SHA256 = "7abf7a0414238517349e383a6ef7282b5f8d16921686ddc1edb6f2e70e5cc77a"
EXPECTED_CURVE_SHA256 = "199926a5dac7e21c0381dfd807675235e07cf650429fa0295e2e2705d94cc56d"
EXPECTED_EVENT_COUNT = 365
EXPECTED_CURVE_ROW_COUNT = 8148
EXPECTED_GLOBAL_TRADE_DATE_COUNT = 2037
EXPECTED_CANARY_EVENT_IDS = (
    "c9d8cc37564746be6fce19b99454a0c7702e948eb104a1bed021917c1deb11d8",
    "3734ac5af36029dd053580b4fad920d86d52b0b75a004451933639740e6a7707",
    "29ede6ecdb2e9d11a8589f5e75e23ce85383a82f443a2aae921aa6cc47e2a86e",
    "ef3db8174af7c2e79e5efa9e2802cdca0d9be4815df62bc4d05b708a3531f64b",
    "3ccfc87846f99285bc390406eda7f2e6ae98a08766532f57611ab5346a4bed6b",
    "15db549474e419e487d048e915f2e66a8076f72fc6cf2b1828c39f40d0deb97e",
    "3ee5a592e505cc585f5c8024df1d87112ca89ba25c42879c21fdf6fb4603e808",
    "b13e8f7de7837203b0d80c8e01c30290633b2f8bfb97038e8c0e28ec84069a91",
    "154555ae9567e9af613d4be0795b7107894247df34eefe5bef178c3afde011a8",
    "69989dc6767a65b044ea3e1144ced85e993f684e427aa3d647add80da79f58a9",
    "d3be75d75eeb8315d4b8b09e005f1c9afd9a53567df0b19a7d7ed59728509dd6",
    "183c0046ccaa1726d6b1145c4b31f9c947a6f9b8d8d59465021fb5eff84a00af",
)
NIGHT_SESSION_PRODUCTS = {
    "au.SHFE",
    "cu.SHFE",
    "rb.SHFE",
    "hc.SHFE",
    "fu.SHFE",
    "ru.SHFE",
    "sp.SHFE",
    "MA.CZCE",
    "OI.CZCE",
    "CF.CZCE",
    "FG.CZCE",
    "SA.CZCE",
    "SM.CZCE",
    "jm.DCE",
}
REQUIRED_TICK_COLUMNS = {
    "datetime",
    "symbol",
    "last_price",
    "ask_price1",
    "ask_volume1",
    "bid_price1",
    "bid_volume1",
    "volume",
    "open_interest",
}
TERMINAL_STATUSES = {
    "extracted",
    "integrity_failed",
    "empty",
    "authentication_or_permission_failed",
    "timeout",
    "query_failed",
}


class IntegrityError(RuntimeError):
    pass


class QueryTimeout(TimeoutError):
    pass


@dataclass(frozen=True)
class FetchResult:
    terminal_status: str
    frame: pd.DataFrame
    message: str
    elapsed_seconds: float
    network_called: bool


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, (np.integer, int)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        number = float(value)
        return number if math.isfinite(number) else None
    if value is None:
        return None
    try:
        return None if pd.isna(value) else value
    except (TypeError, ValueError):
        return value


def _atomic_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_bytes(payload)
    os.replace(temporary, path)


def _atomic_json(path: Path, payload: Any) -> None:
    encoded = (
        json.dumps(_json_safe(payload), ensure_ascii=False, indent=2, sort_keys=True)
        + "\n"
    ).encode("utf-8")
    _atomic_bytes(path, encoded)


def _csv_bytes(frame: pd.DataFrame) -> bytes:
    buffer = StringIO()
    frame.to_csv(buffer, index=False, lineterminator="\n")
    return buffer.getvalue().encode("utf-8")


def _atomic_csv(path: Path, frame: pd.DataFrame) -> None:
    _atomic_bytes(path, _csv_bytes(frame))


def redact_message(value: Any, secrets: Iterable[str]) -> str:
    message = str(value)
    for secret in secrets:
        if secret:
            message = message.replace(str(secret), "<redacted>")
    return message


def select_canary_events(
    events: pd.DataFrame,
    *,
    night_products: set[str] = NIGHT_SESSION_PRODUCTS,
) -> pd.DataFrame:
    required = {
        "event_id",
        "entry_date",
        "product_vt_symbol",
        "vt_symbol",
        "tqsdk_underlying",
    }
    missing = sorted(required - set(events.columns))
    if missing:
        raise IntegrityError(f"events missing columns: {missing}")
    data = events.copy()
    data["entry_date"] = pd.to_datetime(data["entry_date"], errors="raise").dt.normalize()
    data["event_id"] = data["event_id"].astype(str)
    data["exchange"] = data["product_vt_symbol"].astype(str).str.rsplit(".", n=1).str[-1]
    data["has_night_session"] = data["product_vt_symbol"].astype(str).isin(night_products)
    data.sort_values(
        ["exchange", "has_night_session", "entry_date", "event_id"],
        inplace=True,
        kind="mergesort",
    )
    rows: list[dict[str, Any]] = []
    for (exchange, has_night), group in data.groupby(
        ["exchange", "has_night_session"], sort=True, dropna=False
    ):
        ordered = group.sort_values(["entry_date", "event_id"], kind="mergesort")
        boundaries = (("earliest", ordered.iloc[0]), ("latest", ordered.iloc[-1]))
        seen: set[str] = set()
        for boundary, item in boundaries:
            event_id = str(item["event_id"])
            if event_id in seen:
                continue
            seen.add(event_id)
            row = item.to_dict()
            row.update(
                {
                    "exchange": str(exchange),
                    "has_night_session": bool(has_night),
                    "boundary": boundary,
                }
            )
            rows.append(row)
    selected = pd.DataFrame(rows)
    if selected.empty:
        return selected
    selected["_boundary_order"] = selected["boundary"].map({"earliest": 0, "latest": 1})
    selected.sort_values(
        ["exchange", "has_night_session", "_boundary_order", "entry_date", "event_id"],
        inplace=True,
        kind="mergesort",
    )
    selected.drop(columns="_boundary_order", inplace=True)
    selected.reset_index(drop=True, inplace=True)
    return selected


def compute_session_window(
    *,
    entry_date: Any,
    has_night_session: bool,
    global_trade_dates: pd.DatetimeIndex | Iterable[Any],
) -> dict[str, str]:
    entry = pd.Timestamp(entry_date).normalize()
    dates = pd.DatetimeIndex(pd.to_datetime(list(global_trade_dates), errors="raise")).normalize()
    dates = pd.DatetimeIndex(sorted(dates.unique()))
    if has_night_session:
        previous = dates[dates < entry]
        if previous.empty:
            raise IntegrityError(f"no previous global trade date for {entry.date()}")
        base = pd.Timestamp(previous[-1])
        start = base + pd.Timedelta(hours=20, minutes=59)
        session_open = base + pd.Timedelta(hours=21)
        end = base + pd.Timedelta(hours=21, minutes=5)
    else:
        base = entry
        start = base + pd.Timedelta(hours=8, minutes=59)
        session_open = base + pd.Timedelta(hours=9)
        end = base + pd.Timedelta(hours=9, minutes=5)
    return {
        "session_start": start.strftime("%Y-%m-%d %H:%M:%S"),
        "session_open": session_open.strftime("%Y-%m-%d %H:%M:%S"),
        "session_end": end.strftime("%Y-%m-%d %H:%M:%S"),
    }


def load_frozen_plan(
    events_path: Path = EVENTS_PATH,
    curve_path: Path = CURVE_PATH,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    events_hash = sha256_file(events_path)
    curve_hash = sha256_file(curve_path)
    events = pd.read_csv(events_path)
    curve = pd.read_csv(curve_path)
    if "date" not in curve.columns:
        raise IntegrityError("curve missing date")
    global_dates = pd.DatetimeIndex(
        pd.to_datetime(curve["date"], format="mixed", errors="raise").dt.normalize().unique()
    )
    audit = {
        "events_path": str(events_path),
        "events_sha256": events_hash,
        "events_hash_ok": events_hash == EXPECTED_EVENTS_SHA256,
        "event_row_count": int(len(events)),
        "event_row_count_ok": len(events) == EXPECTED_EVENT_COUNT,
        "unique_event_count": int(events["event_id"].astype(str).nunique()),
        "curve_path": str(curve_path),
        "curve_sha256": curve_hash,
        "curve_hash_ok": curve_hash == EXPECTED_CURVE_SHA256,
        "curve_row_count": int(len(curve)),
        "curve_row_count_ok": len(curve) == EXPECTED_CURVE_ROW_COUNT,
        "global_trade_date_count": int(len(global_dates)),
        "global_trade_date_count_ok": len(global_dates) == EXPECTED_GLOBAL_TRADE_DATE_COUNT,
    }
    selected = select_canary_events(events)
    actual_ids = tuple(selected["event_id"].astype(str))
    audit.update(
        {
            "canary_event_count": int(len(selected)),
            "canary_event_ids_match": actual_ids == EXPECTED_CANARY_EVENT_IDS,
            "canary_group_count": int(
                selected[["exchange", "has_night_session"]].drop_duplicates().shape[0]
            ),
        }
    )
    audit["frozen_plan_pass"] = bool(
        audit["events_hash_ok"]
        and audit["event_row_count_ok"]
        and audit["unique_event_count"] == EXPECTED_EVENT_COUNT
        and audit["curve_hash_ok"]
        and audit["curve_row_count_ok"]
        and audit["global_trade_date_count_ok"]
        and audit["canary_event_count"] == 12
        and audit["canary_event_ids_match"]
        and audit["canary_group_count"] == 6
    )
    if not audit["frozen_plan_pass"]:
        raise IntegrityError(f"frozen plan audit failed: {audit}")
    windows = [
        compute_session_window(
            entry_date=row["entry_date"],
            has_night_session=bool(row["has_night_session"]),
            global_trade_dates=global_dates,
        )
        for row in selected.to_dict("records")
    ]
    for column in ("session_start", "session_open", "session_end"):
        selected[column] = [window[column] for window in windows]
    selected["entry_date"] = selected["entry_date"].dt.date.astype(str)
    selected["events_sha256"] = events_hash
    selected["curve_sha256"] = curve_hash
    return selected, audit


def _exact_ns(value: Any) -> tuple[int | None, bool]:
    if isinstance(value, (bool, np.bool_)):
        return None, False
    if isinstance(value, (float, np.floating)):
        return None, True
    if isinstance(value, (int, np.integer)):
        return int(value), False
    text = str(value).strip()
    if re.fullmatch(r"[+-]?\d+", text):
        return int(text), False
    return None, False


def _beijing_timestamp(value: Any) -> pd.Timestamp:
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is None:
        return timestamp.tz_localize("Asia/Shanghai")
    return timestamp.tz_convert("Asia/Shanghai")


def normalize_tick_frame(
    frame: pd.DataFrame,
    *,
    start: Any,
    end: Any,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    if "datetime" not in frame.columns:
        raise IntegrityError("tick frame missing datetime")
    start_ts = _beijing_timestamp(start)
    end_ts = _beijing_timestamp(end)
    if end_ts < start_ts:
        raise IntegrityError("request end precedes start")
    datetime_ns: list[int | None] = []
    timestamps: list[pd.Timestamp] = []
    float_count = 0
    malformed = 0
    for value in frame["datetime"].tolist():
        parsed_ns, was_float = _exact_ns(value)
        float_count += int(was_float)
        if parsed_ns is None or parsed_ns <= 0:
            datetime_ns.append(None)
            timestamps.append(pd.NaT)
            malformed += 1
            continue
        try:
            timestamp = pd.to_datetime(parsed_ns, unit="ns", utc=True).tz_convert(
                "Asia/Shanghai"
            )
        except (ValueError, OverflowError, TypeError):
            datetime_ns.append(None)
            timestamps.append(pd.NaT)
            malformed += 1
            continue
        datetime_ns.append(parsed_ns)
        timestamps.append(timestamp)
    normalized = frame.copy(deep=True)
    normalized["datetime_ns"] = pd.array(datetime_ns, dtype="Int64")
    normalized["datetime_beijing"] = pd.Series(
        pd.array(timestamps, dtype="datetime64[ns, Asia/Shanghai]"),
        index=normalized.index,
    )
    normalized["in_request_window"] = (
        normalized["datetime_beijing"].notna()
        & normalized["datetime_beijing"].ge(start_ts)
        & normalized["datetime_beijing"].le(end_ts)
    )
    return normalized, {
        "float_datetime_count": int(float_count),
        "malformed_datetime_count": int(malformed),
        "parsed_datetime_count": int(len(frame) - malformed),
    }


def audit_tick_frame(
    frame: pd.DataFrame,
    *,
    requested_symbol: str,
    start: Any,
    end: Any,
    session_open: Any,
) -> tuple[dict[str, Any], pd.DataFrame]:
    missing = sorted(REQUIRED_TICK_COLUMNS - set(frame.columns))
    if "datetime" in frame.columns:
        normalized, parse_audit = normalize_tick_frame(frame, start=start, end=end)
    else:
        normalized = frame.copy()
        parse_audit = {
            "float_datetime_count": 0,
            "malformed_datetime_count": int(len(frame)),
            "parsed_datetime_count": 0,
        }
    default = {
        "raw_row_count": int(len(frame)),
        "missing_columns": "|".join(missing),
        **parse_audit,
        "outside_window_count": 0,
        "symbol_mismatch_count": 0,
        "duplicate_key_row_count": 0,
        "crossed_spread_count": 0,
        "negative_price_count": 0,
        "negative_size_count": 0,
        "negative_volume_count": 0,
        "negative_open_interest_count": 0,
        "infinite_numeric_count": 0,
        "cumulative_volume_rollback_count": 0,
        "valid_l1_within_60s_count": 0,
        "tick_integrity_pass": False,
    }
    if missing:
        return default, normalized

    parsed = normalized["datetime_beijing"].notna()
    in_window = normalized["in_request_window"].astype(bool)
    default["outside_window_count"] = int((parsed & ~in_window).sum())
    symbols = normalized["symbol"].fillna("").astype(str)
    default["symbol_mismatch_count"] = int(symbols.ne(str(requested_symbol)).sum())

    numeric_columns = [
        "last_price",
        "ask_price1",
        "ask_volume1",
        "bid_price1",
        "bid_volume1",
        "volume",
        "open_interest",
    ]
    numeric = normalized[numeric_columns].apply(pd.to_numeric, errors="coerce")
    for column in numeric_columns:
        normalized[column] = numeric[column]
    finite = np.isfinite(numeric.to_numpy(dtype=float))
    default["infinite_numeric_count"] = int(
        np.isinf(numeric.to_numpy(dtype=float)).sum()
    )
    default["negative_price_count"] = int(
        numeric[["ask_price1", "bid_price1"]].lt(0).sum().sum()
    )
    default["negative_size_count"] = int(
        numeric[["ask_volume1", "bid_volume1"]].lt(0).sum().sum()
    )
    default["negative_volume_count"] = int(numeric["volume"].lt(0).sum())
    default["negative_open_interest_count"] = int(
        numeric["open_interest"].lt(0).sum()
    )
    positive_quotes = numeric["bid_price1"].gt(0) & numeric["ask_price1"].gt(0)
    default["crossed_spread_count"] = int(
        (positive_quotes & numeric["ask_price1"].lt(numeric["bid_price1"])).sum()
    )

    key_columns = ["datetime_ns"]
    if "id" in normalized.columns:
        key_columns.append("id")
    key_columns.append("symbol")
    duplicate_scope = normalized[in_window & parsed]
    default["duplicate_key_row_count"] = int(
        duplicate_scope.duplicated(key_columns, keep=False).sum()
    )

    order_columns = ["datetime_ns"] + (["id"] if "id" in normalized.columns else [])
    ordered = normalized[in_window & parsed].sort_values(order_columns, kind="mergesort")
    finite_volume = pd.to_numeric(ordered["volume"], errors="coerce")
    finite_volume = finite_volume[np.isfinite(finite_volume.to_numpy(dtype=float))]
    default["cumulative_volume_rollback_count"] = int(finite_volume.diff().lt(0).sum())

    open_ts = _beijing_timestamp(session_open)
    deadline = open_ts + pd.Timedelta(seconds=60)
    valid_l1 = (
        in_window
        & normalized["datetime_beijing"].ge(open_ts)
        & normalized["datetime_beijing"].le(deadline)
        & symbols.eq(str(requested_symbol))
        & numeric["bid_price1"].gt(0)
        & numeric["ask_price1"].gt(0)
        & numeric["ask_price1"].ge(numeric["bid_price1"])
        & numeric["bid_volume1"].ge(0)
        & numeric["ask_volume1"].ge(0)
        & np.isfinite(
            numeric[["bid_price1", "ask_price1", "bid_volume1", "ask_volume1"]]
            .to_numpy(dtype=float)
        ).all(axis=1)
    )
    default["valid_l1_within_60s_count"] = int(valid_l1.sum())
    default["first_tick_beijing"] = (
        normalized.loc[in_window, "datetime_beijing"].min().isoformat()
        if in_window.any()
        else ""
    )
    default["last_tick_beijing"] = (
        normalized.loc[in_window, "datetime_beijing"].max().isoformat()
        if in_window.any()
        else ""
    )
    default["tick_integrity_pass"] = bool(
        len(frame) > 0
        and not missing
        and default["float_datetime_count"] == 0
        and default["malformed_datetime_count"] == 0
        and default["outside_window_count"] == 0
        and default["symbol_mismatch_count"] == 0
        and default["duplicate_key_row_count"] == 0
        and default["crossed_spread_count"] == 0
        and default["negative_price_count"] == 0
        and default["negative_size_count"] == 0
        and default["negative_volume_count"] == 0
        and default["negative_open_interest_count"] == 0
        and default["infinite_numeric_count"] == 0
        and default["cumulative_volume_rollback_count"] == 0
        and default["valid_l1_within_60s_count"] >= 1
    )
    default["all_numeric_value_count"] = int(finite.size)
    return default, normalized


def _next_attempt_dir(event_root: Path) -> tuple[int, Path]:
    numbers: list[int] = []
    for path in event_root.glob("attempt_*"):
        try:
            numbers.append(int(path.name.split("_", 1)[1]))
        except (IndexError, ValueError):
            continue
    number = max(numbers, default=0) + 1
    return number, event_root / f"attempt_{number:04d}"


def _manifest_frame(directory: Path) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for path in sorted(directory.iterdir(), key=lambda item: item.name):
        if not path.is_file() or path.name in {"manifest.csv", "manifest.sha256"}:
            continue
        rows.append(
            {
                "file": path.name,
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    return pd.DataFrame(rows, columns=["file", "bytes", "sha256"])


def _serialized_normalized(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    if "datetime_beijing" in result.columns:
        result["datetime_beijing"] = result["datetime_beijing"].map(
            lambda value: value.isoformat() if pd.notna(value) else ""
        )
    return result


def scan_credential_literals(directory: Path, secrets: Iterable[str]) -> int:
    encoded = [str(secret).encode("utf-8") for secret in secrets if secret]
    hits = 0
    for path in directory.rglob("*"):
        if not path.is_file():
            continue
        payload = path.read_bytes()
        hits += sum(payload.count(secret) for secret in encoded)
    return int(hits)


def publish_attempt(
    event: dict[str, Any],
    *,
    result: FetchResult,
    audit: dict[str, Any],
    normalized: pd.DataFrame,
    attempts_root: Path,
    secrets: Iterable[str],
    run_id: str,
) -> Path:
    if result.terminal_status not in TERMINAL_STATUSES:
        raise IntegrityError(f"unknown terminal status: {result.terminal_status}")
    event_id = str(event["event_id"])
    event_root = attempts_root / event_id
    event_root.mkdir(parents=True, exist_ok=True)
    attempt_number, final_dir = _next_attempt_dir(event_root)
    temporary_dir = Path(tempfile.mkdtemp(prefix=".tmp_attempt_", dir=event_root))
    try:
        request = {
            key: _json_safe(event.get(key))
            for key in (
                "event_id",
                "exchange",
                "has_night_session",
                "boundary",
                "entry_date",
                "product_vt_symbol",
                "vt_symbol",
                "tqsdk_underlying",
                "session_start",
                "session_open",
                "session_end",
                "events_sha256",
                "curve_sha256",
            )
        }
        request.update(
            {
                "method": "TqApi.get_tick_data_series",
                "read_only_history_query": True,
                "credential_values_persisted": False,
                "network_called": bool(result.network_called),
                "run_id": run_id,
                "attempt_number": attempt_number,
                "producer_path": str(Path(__file__).resolve()),
                "producer_sha256": sha256_file(Path(__file__).resolve()),
            }
        )
        status = {
            "event_id": event_id,
            "terminal_status": result.terminal_status,
            "message": redact_message(result.message, secrets),
            "elapsed_seconds": float(result.elapsed_seconds),
            "network_called": bool(result.network_called),
            "raw_row_count": int(len(result.frame)),
            "tick_integrity_pass": bool(audit.get("tick_integrity_pass", False)),
            "credential_values_persisted": False,
            "run_id": run_id,
            "attempt_number": attempt_number,
        }
        _atomic_json(temporary_dir / "request.json", request)
        _atomic_json(temporary_dir / "status.json", status)
        _atomic_json(temporary_dir / "audit.json", audit)
        if len(result.frame) or result.terminal_status in {"extracted", "integrity_failed"}:
            _atomic_csv(temporary_dir / "raw_tick.csv", result.frame)
            _atomic_csv(
                temporary_dir / "normalized_tick.csv",
                _serialized_normalized(normalized),
            )
            schema = {
                "raw_columns": list(result.frame.columns),
                "raw_dtypes": {column: str(dtype) for column, dtype in result.frame.dtypes.items()},
                "normalized_columns": list(normalized.columns),
                "normalized_dtypes": {
                    column: str(dtype) for column, dtype in normalized.dtypes.items()
                },
                "raw_datetime_dtype": str(result.frame["datetime"].dtype)
                if "datetime" in result.frame.columns
                else "missing",
                "raw_datetime_float_forbidden": True,
            }
            _atomic_json(temporary_dir / "schema.json", schema)
        manifest = _manifest_frame(temporary_dir)
        _atomic_csv(temporary_dir / "manifest.csv", manifest)
        manifest_hash = sha256_file(temporary_dir / "manifest.csv")
        _atomic_bytes(
            temporary_dir / "manifest.sha256",
            f"{manifest_hash}  manifest.csv\n".encode("ascii"),
        )
        if scan_credential_literals(temporary_dir, secrets):
            raise IntegrityError("credential literal found in attempt output")
        if final_dir.exists():
            raise IntegrityError(f"attempt path already exists: {final_dir}")
        os.replace(temporary_dir, final_dir)
        return final_dir
    except Exception:
        if temporary_dir.exists():
            shutil.rmtree(temporary_dir)
        raise


def _empty_audit(frame: pd.DataFrame) -> tuple[dict[str, Any], pd.DataFrame]:
    return (
        {
            "raw_row_count": int(len(frame)),
            "missing_columns": "|".join(sorted(REQUIRED_TICK_COLUMNS)),
            "float_datetime_count": 0,
            "malformed_datetime_count": 0,
            "parsed_datetime_count": 0,
            "outside_window_count": 0,
            "symbol_mismatch_count": 0,
            "duplicate_key_row_count": 0,
            "crossed_spread_count": 0,
            "negative_price_count": 0,
            "negative_size_count": 0,
            "negative_volume_count": 0,
            "negative_open_interest_count": 0,
            "infinite_numeric_count": 0,
            "cumulative_volume_rollback_count": 0,
            "valid_l1_within_60s_count": 0,
            "tick_integrity_pass": False,
        },
        frame.copy(),
    )


def execute_plan(
    plan: pd.DataFrame,
    *,
    fetcher: Callable[[dict[str, Any]], FetchResult],
    attempts_root: Path,
    secrets: Iterable[str],
    run_id: str,
) -> pd.DataFrame:
    secret_values = list(secrets)
    rows: list[dict[str, Any]] = []
    for ordinal, event in enumerate(plan.to_dict("records"), start=1):
        started = time.monotonic()
        try:
            result = fetcher(event)
        except Exception as exc:
            result = FetchResult(
                terminal_status="query_failed",
                frame=pd.DataFrame(),
                message=redact_message(exc, secret_values),
                elapsed_seconds=time.monotonic() - started,
                network_called=False,
            )
        if result.terminal_status == "extracted":
            if result.frame.empty:
                result = FetchResult(
                    terminal_status="empty",
                    frame=result.frame,
                    message=result.message or "empty tick frame",
                    elapsed_seconds=result.elapsed_seconds,
                    network_called=result.network_called,
                )
                audit, normalized = _empty_audit(result.frame)
            else:
                audit, normalized = audit_tick_frame(
                    result.frame,
                    requested_symbol=str(event["tqsdk_underlying"]),
                    start=event["session_start"],
                    end=event["session_end"],
                    session_open=event["session_open"],
                )
                if not audit["tick_integrity_pass"]:
                    result = FetchResult(
                        terminal_status="integrity_failed",
                        frame=result.frame,
                        message="tick integrity hard gate failed",
                        elapsed_seconds=result.elapsed_seconds,
                        network_called=result.network_called,
                    )
        elif not result.frame.empty:
            audit, normalized = audit_tick_frame(
                result.frame,
                requested_symbol=str(event["tqsdk_underlying"]),
                start=event["session_start"],
                end=event["session_end"],
                session_open=event["session_open"],
            )
        else:
            audit, normalized = _empty_audit(result.frame)
        attempt_path = publish_attempt(
            event,
            result=result,
            audit=audit,
            normalized=normalized,
            attempts_root=attempts_root,
            secrets=secret_values,
            run_id=run_id,
        )
        rows.append(
            {
                "run_id": run_id,
                "run_ordinal": ordinal,
                "event_id": str(event["event_id"]),
                "exchange": str(event["exchange"]),
                "has_night_session": bool(event["has_night_session"]),
                "boundary": str(event["boundary"]),
                "entry_date": str(event["entry_date"]),
                "vt_symbol": str(event["vt_symbol"]),
                "tqsdk_underlying": str(event["tqsdk_underlying"]),
                "terminal_status": result.terminal_status,
                "raw_row_count": int(len(result.frame)),
                "valid_l1_within_60s_count": int(
                    audit.get("valid_l1_within_60s_count", 0)
                ),
                "tick_integrity_pass": bool(audit.get("tick_integrity_pass", False)),
                "network_called": bool(result.network_called),
                "elapsed_seconds": float(result.elapsed_seconds),
                "attempt_path": str(attempt_path),
                "attempt_manifest_sha256": sha256_file(attempt_path / "manifest.csv"),
            }
        )
    return pd.DataFrame(rows)


def build_decision(plan: pd.DataFrame, ledger: pd.DataFrame) -> dict[str, Any]:
    planned_ids = plan.get("event_id", pd.Series(dtype=str)).astype(str).tolist()
    ledger_ids = ledger.get("event_id", pd.Series(dtype=str)).astype(str).tolist()
    passed = (
        ledger.get("terminal_status", pd.Series(dtype=str)).astype(str).eq("extracted")
        & ledger.get("tick_integrity_pass", pd.Series(dtype=bool)).astype(bool)
    )
    exact_identity = bool(
        len(planned_ids) == len(ledger_ids)
        and planned_ids == ledger_ids
        and len(set(ledger_ids)) == len(ledger_ids)
    )
    hard_gate = bool(
        len(planned_ids) == 12
        and exact_identity
        and int(passed.sum()) == 12
    )
    return {
        "decision": (
            "ALLOW_STAGE002_FULL_EVENT_ACQUISITION_PREDECL_ONLY"
            if hard_gate
            else "CLOSE_LINE_L1_TICK_COVERAGE_INELIGIBLE"
        ),
        "denominator_event_count": int(len(planned_ids)),
        "observed_terminal_event_count": int(len(ledger_ids)),
        "unique_terminal_event_count": int(len(set(ledger_ids))),
        "exact_plan_identity_match": exact_identity,
        "passed_event_count": int(passed.sum()),
        "failed_event_count": int(len(planned_ids) - passed.sum()),
        "coverage_ratio": float(passed.sum() / len(planned_ids)) if planned_ids else 0.0,
        "hard_gate_pass": hard_gate,
        "ready_for_feature": False,
        "ready_for_backtest": False,
        "ready_for_live": False,
        "backtest_executed": False,
        "trade_count": 0,
    }


@contextmanager
def _wall_clock_timeout(seconds: int):
    if seconds <= 0 or not hasattr(signal, "SIGALRM"):
        yield
        return
    previous_handler = signal.getsignal(signal.SIGALRM)
    previous_timer = signal.setitimer(signal.ITIMER_REAL, float(seconds))

    def _raise_timeout(_signum: int, _frame: Any) -> None:
        raise QueryTimeout(f"query timeout after {seconds}s")

    signal.signal(signal.SIGALRM, _raise_timeout)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, *previous_timer)
        signal.signal(signal.SIGALRM, previous_handler)


def fetch_tqsdk_tick(
    event: dict[str, Any],
    *,
    username: str,
    password: str,
    max_seconds: int,
) -> FetchResult:
    from tqsdk import TqApi, TqAuth

    started = time.monotonic()
    api = None
    secrets = [username, password]
    try:
        with _wall_clock_timeout(max_seconds):
            api = TqApi(auth=TqAuth(username, password), disable_print=True)
            frame = api.get_tick_data_series(
                symbol=str(event["tqsdk_underlying"]),
                start_dt=pd.Timestamp(event["session_start"]).to_pydatetime(),
                end_dt=pd.Timestamp(event["session_end"]).to_pydatetime(),
            )
            frame = pd.DataFrame(frame).copy(deep=True)
        return FetchResult(
            terminal_status="extracted",
            frame=frame,
            message="history query returned",
            elapsed_seconds=time.monotonic() - started,
            network_called=True,
        )
    except QueryTimeout as exc:
        return FetchResult(
            terminal_status="timeout",
            frame=pd.DataFrame(),
            message=redact_message(exc, secrets),
            elapsed_seconds=time.monotonic() - started,
            network_called=True,
        )
    except Exception as exc:
        message = redact_message(exc, secrets)
        lowered = message.lower()
        status = (
            "authentication_or_permission_failed"
            if any(
                token in lowered
                for token in (
                    "auth",
                    "login",
                    "password",
                    "permission",
                    "professional",
                    "专业版",
                    "权限",
                    "用户",
                    "账户",
                )
            )
            else "query_failed"
        )
        return FetchResult(
            terminal_status=status,
            frame=pd.DataFrame(),
            message=message,
            elapsed_seconds=time.monotonic() - started,
            network_called=True,
        )
    finally:
        if api is not None:
            try:
                api.close()
            except Exception:
                pass


def _credentials() -> tuple[str, str]:
    from vnpy.trader.setting import SETTINGS

    username = str(SETTINGS.get("datafeed.username", ""))
    password = str(SETTINGS.get("datafeed.password", ""))
    if not username or not password:
        raise RuntimeError("TqSdk credentials are missing in vn.py SETTINGS")
    return username, password


def _root_manifest(output_dir: Path) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for path in sorted(output_dir.iterdir(), key=lambda item: item.name):
        if not path.is_file() or path.name in {"manifest.csv", "manifest.sha256"}:
            continue
        rows.append(
            {"file": path.name, "bytes": path.stat().st_size, "sha256": sha256_file(path)}
        )
    return pd.DataFrame(rows, columns=["file", "bytes", "sha256"])


def _report(decision: dict[str, Any], ledger: pd.DataFrame, plan_audit: dict[str, Any]) -> str:
    failures = ledger[~ledger["tick_integrity_pass"].astype(bool)].copy()
    failure_table = (
        failures[
            [
                "entry_date",
                "vt_symbol",
                "terminal_status",
                "raw_row_count",
                "valid_l1_within_60s_count",
            ]
        ].to_markdown(index=False)
        if not failures.empty
        else "_无失败事件_"
    )
    return f"""# Stage001 L1 历史 Tick Canary 结果

- 决策：`{decision['decision']}`
- 固定分母：`{decision['denominator_event_count']}`
- 通过：`{decision['passed_event_count']}`
- 覆盖率：`{decision['coverage_ratio']:.2%}`
- 事件源 SHA 合格：`{plan_audit['events_hash_ok']}`
- 交易日源 SHA 合格：`{plan_audit['curve_hash_ok']}`
- 特征/回测/实盘 ready：`False / False / False`
- 本阶段未运行收益回测，交易次数：`0`

## 未通过事件

{failure_table}

## 机械边界

- 仅当固定12事件全部通过真实 L1、窗口、纳秒、symbol、重复键与累计量审计，才允许下一阶段全事件采集预声明。
- 放行也不代表特征有效，不允许直接改策略、跑实盘或声称改善收益回撤。
"""


def run(*, output_dir: Path = OUTPUT_DIR, max_seconds: int = 120) -> dict[str, Any]:
    plan, plan_audit = load_frozen_plan()
    output_dir.mkdir(parents=True, exist_ok=True)
    run_id = pd.Timestamp.now(tz="Asia/Shanghai").strftime("%Y%m%dT%H%M%S%z")
    try:
        username, password = _credentials()

        def fetcher(event: dict[str, Any]) -> FetchResult:
            return fetch_tqsdk_tick(
                event,
                username=username,
                password=password,
                max_seconds=max_seconds,
            )

        secrets = [username, password]
    except Exception as exc:
        message = str(exc)

        def fetcher(_event: dict[str, Any]) -> FetchResult:
            return FetchResult(
                terminal_status="authentication_or_permission_failed",
                frame=pd.DataFrame(),
                message=message,
                elapsed_seconds=0.0,
                network_called=False,
            )

        secrets = []

    ledger = execute_plan(
        plan,
        fetcher=fetcher,
        attempts_root=output_dir / "attempts",
        secrets=secrets,
        run_id=run_id,
    )
    decision = build_decision(plan, ledger)
    decision.update(
        {
            "run_id": run_id,
            "generated_at": pd.Timestamp.now(tz="Asia/Shanghai").isoformat(),
            "plan_audit": plan_audit,
            "producer_sha256": sha256_file(Path(__file__).resolve()),
            "credential_literal_hits": 0,
        }
    )
    plan_path = output_dir / "frozen_canary_plan.csv"
    ledger_path = output_dir / "terminal_ledger.csv"
    decision_path = output_dir / "decision.json"
    report_path = output_dir / "report.md"
    _atomic_csv(plan_path, plan)
    _atomic_json(output_dir / "plan_audit.json", plan_audit)
    _atomic_csv(ledger_path, ledger)
    _atomic_json(decision_path, decision)
    _atomic_bytes(report_path, _report(decision, ledger, plan_audit).encode("utf-8"))
    root_manifest = _root_manifest(output_dir)
    _atomic_csv(output_dir / "manifest.csv", root_manifest)
    manifest_hash = sha256_file(output_dir / "manifest.csv")
    _atomic_bytes(
        output_dir / "manifest.sha256",
        f"{manifest_hash}  manifest.csv\n".encode("ascii"),
    )
    credential_hits = scan_credential_literals(output_dir, secrets)
    if credential_hits:
        raise IntegrityError(f"credential literal found in output: {credential_hits}")
    return decision


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    parser.add_argument("--max-seconds", type=int, default=120)
    arguments = parser.parse_args()
    decision = run(output_dir=arguments.output_dir, max_seconds=arguments.max_seconds)
    print(
        json.dumps(
            {
                "decision": decision["decision"],
                "passed_event_count": decision["passed_event_count"],
                "denominator_event_count": decision["denominator_event_count"],
                "coverage_ratio": decision["coverage_ratio"],
                "run_id": decision["run_id"],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
