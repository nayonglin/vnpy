from __future__ import annotations

from datetime import datetime
import hashlib
import importlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import time
from typing import Any, Mapping
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
from vnpy.trader.setting import SETTINGS


PROJECT_DIR = Path(__file__).resolve().parents[4]
LINE_ID = "futures_trend_rebuilt_c9_15w_v2_optimization"
STAGE = "Stage130"
STAGE_ID = "stage130_tqsdk_expired_option_chain_probe"
MODEL_TAG = f"{STAGE_ID}_v1"
OUTPUT_PREFIX = f"rebuilt_c9_v2_{STAGE_ID}"

LINE_DIR = PROJECT_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / STAGE_ID
TEST_PATH = PROJECT_DIR / "tests/test_rebuilt_c9_v2_stage130_tqsdk_expired_option_chain_probe.py"
PREDECL_PATH = LINE_DIR / "stages/20260711_1152_stage130_tqsdk_expired_option_chain_probe_predecl.md"

UNDERLYING_SYMBOL = "DCE.m2209"
PROBE_START = pd.Timestamp("2022-03-09")
PROBE_END = pd.Timestamp("2022-03-11")
OPTION_QUERY_EXPIRED_AS_OF_BACKTEST = False
ENABLE_NETWORK_PROBE = os.getenv("STAGE130_ENABLE_NETWORK_PROBE", "0").strip() == "1"
MAX_NETWORK_SECONDS = int(os.getenv("STAGE130_MAX_NETWORK_SECONDS", "120"))
CHINA_TZ = ZoneInfo("Asia/Shanghai")

MODULE_AUDIT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_module_audit_{MODEL_TAG}.csv"
CREDENTIAL_AUDIT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_credential_audit_{MODEL_TAG}.csv"
METADATA_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_option_metadata_{MODEL_TAG}.csv"
SELECTED_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_selected_call_put_{MODEL_TAG}.csv"
BARS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_probe_bars_{MODEL_TAG}.csv"
RAW_BARS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_raw_probe_bars_{MODEL_TAG}.csv"
STATUS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_probe_status_{MODEL_TAG}.csv"
FILTER_AUDIT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_filter_audit_{MODEL_TAG}.csv"
METADATA_AUDIT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_metadata_audit_{MODEL_TAG}.csv"
BARS_AUDIT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_bars_audit_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
LINEAGE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_lineage_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
MANIFEST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_manifest_{MODEL_TAG}.csv"

SOURCE_LINKS = {
    "tqsdk_github": "https://github.com/shinnytech/tqsdk-python",
    "tqapi_options": "https://tqsdk-python.readthedocs.io/en/stable/reference/tqsdk.api.html",
    "data_downloader": "https://tqsdk-python.readthedocs.io/en/latest/reference/tqsdk.tools.download.html",
    "option_examples": "https://tqsdk-python.readthedocs.io/en/stable/demo/option_base.html",
}


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        number = float(value)
        return None if math.isnan(number) or math.isinf(number) else number
    if isinstance(value, (pd.Timestamp, datetime)):
        return "" if pd.isna(value) else value.isoformat()
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verified_raw_hashes(
    files: Mapping[str, tuple[Path, int]],
) -> tuple[int, dict[str, dict[str, Any]]]:
    records: dict[str, dict[str, Any]] = {}
    for name, (path, rows) in files.items():
        exists = path.exists() and path.is_file()
        verified = bool(exists and int(rows) > 0 and path.stat().st_size > 0)
        records[name] = {
            "path": str(path),
            "rows": int(rows),
            "bytes": path.stat().st_size if exists else 0,
            "sha256": _sha256(path) if verified else "",
            "verified": verified,
        }
    return int(sum(bool(record["verified"]) for record in records.values())), records


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_无记录_"
    data = frame.head(max_rows).copy() if max_rows else frame.copy()
    return data.to_markdown(index=False)


def audit_tqsdk_credentials(
    *, settings: Mapping[str, Any] | None = None, env: Mapping[str, str] | None = None
) -> dict[str, Any]:
    source_settings = SETTINGS if settings is None else settings
    source_env = os.environ if env is None else env
    env_keys = (
        "TQSDK_ACCOUNT",
        "TQSDK_PASSWORD",
        "TQSDK_USER",
        "TQSDK_PASS",
        "TQ_USERNAME",
        "TQ_PASSWORD",
        "TQ_USER",
        "TQAUTH_USER",
        "TQAUTH_PASSWORD",
    )
    present_keys = [key for key in env_keys if str(source_env.get(key, "")).strip()]
    return {
        "settings_datafeed_username_present": bool(
            str(source_settings.get("datafeed.username", "")).strip()
        ),
        "settings_datafeed_password_present": bool(
            str(source_settings.get("datafeed.password", "")).strip()
        ),
        "environment_tqsdk_key_count": len(present_keys),
        "environment_tqsdk_keys_present": ",".join(present_keys),
        "credential_values_redacted": True,
    }


def inspect_tqsdk_module() -> dict[str, Any]:
    result: dict[str, Any] = {
        "module_importable": False,
        "module_version": "",
        "module_file": "",
        "has_tqapi": False,
        "has_tqauth": False,
        "has_tqsim": False,
        "has_tqbacktest": False,
        "import_error_type": "",
        "import_error": "",
    }
    try:
        module = importlib.import_module("tqsdk")
        result["module_importable"] = True
        result["module_file"] = str(getattr(module, "__file__", ""))
        try:
            result["module_version"] = importlib.metadata.version("tqsdk")
        except importlib.metadata.PackageNotFoundError:
            result["module_version"] = str(getattr(module, "__version__", ""))
        for attr in ("TqApi", "TqAuth", "TqSim", "TqBacktest"):
            result[f"has_{attr.lower()}"] = hasattr(module, attr)
    except Exception as exc:
        result["import_error_type"] = type(exc).__name__
        result["import_error"] = repr(exc)
    return result


def _normalize_option_class(value: Any) -> str:
    text = str(value or "").strip().upper()
    return {"C": "CALL", "P": "PUT"}.get(text, text)


def normalize_option_metadata(frame: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "option_symbol",
        "underlying_symbol",
        "option_class",
        "expire_datetime",
        "strike_price",
        "expired",
    ]
    if frame.empty:
        return pd.DataFrame(columns=columns)
    data = frame.copy()
    if "instrument_id" in data.columns and "option_symbol" not in data.columns:
        data = data.rename(columns={"instrument_id": "option_symbol"})
    for column in columns:
        if column not in data.columns:
            data[column] = np.nan
    data["option_symbol"] = data["option_symbol"].astype(str)
    data["underlying_symbol"] = data["underlying_symbol"].astype(str)
    data["option_class"] = data["option_class"].map(_normalize_option_class)
    data["strike_price"] = pd.to_numeric(data["strike_price"], errors="coerce")
    expiry_source = data["expire_datetime"]
    expiry = pd.to_datetime(expiry_source, errors="coerce")
    if not pd.api.types.is_datetime64_any_dtype(expiry_source.dtype):
        expiry_numeric = pd.to_numeric(expiry_source, errors="coerce")
        numeric_mask = expiry_numeric.notna()
        if numeric_mask.any():
            expiry.loc[numeric_mask] = pd.to_datetime(
                expiry_numeric.loc[numeric_mask], unit="s", errors="coerce", utc=True
            ).dt.tz_convert(CHINA_TZ).dt.tz_localize(None)
    data["expire_datetime"] = expiry
    return data[columns].sort_values(
        ["expire_datetime", "strike_price", "option_class", "option_symbol"]
    ).reset_index(drop=True)


def select_same_expiry_call_put(
    metadata: pd.DataFrame, *, underlying_symbol: str, reference_price: float
) -> pd.DataFrame:
    data = normalize_option_metadata(metadata)
    data = data[
        data["underlying_symbol"].eq(str(underlying_symbol))
        & data["option_class"].isin(["CALL", "PUT"])
        & data["expire_datetime"].notna()
        & data["strike_price"].notna()
        & data["option_symbol"].ne("")
    ].copy()
    if data.empty:
        return data
    for _, expiry_group in data.groupby("expire_datetime", sort=True):
        calls = expiry_group[expiry_group["option_class"].eq("CALL")]
        puts = expiry_group[expiry_group["option_class"].eq("PUT")]
        common_strikes = sorted(
            set(calls["strike_price"].astype(float))
            & set(puts["strike_price"].astype(float))
        )
        if not common_strikes:
            continue
        strike = min(common_strikes, key=lambda item: (abs(item - reference_price), item))
        selected = pd.concat(
            [
                calls[calls["strike_price"].eq(strike)].head(1),
                puts[puts["strike_price"].eq(strike)].head(1),
            ],
            ignore_index=True,
        )
        if len(selected) == 2:
            return selected.reset_index(drop=True)
    return data.iloc[0:0].copy()


def audit_option_metadata(
    selected: pd.DataFrame, *, underlying_symbol: str
) -> dict[str, Any]:
    required = [
        "option_symbol",
        "underlying_symbol",
        "option_class",
        "expire_datetime",
        "strike_price",
    ]
    if selected.empty:
        return {
            "metadata_rows": 0,
            "call_count": 0,
            "put_count": 0,
            "missing_required_count": 0,
            "same_underlying": False,
            "same_expiry": False,
            "same_strike": False,
            "metadata_audit_pass": False,
        }
    data = selected.copy()
    for column in required:
        if column not in data.columns:
            data[column] = np.nan
    missing = int(data[required].isna().sum().sum())
    classes = data["option_class"].map(_normalize_option_class)
    same_underlying = bool(
        data["underlying_symbol"].astype(str).eq(underlying_symbol).all()
    )
    same_expiry = bool(data["expire_datetime"].nunique(dropna=False) == 1)
    same_strike = bool(data["strike_price"].nunique(dropna=False) == 1)
    call_count = int(classes.eq("CALL").sum())
    put_count = int(classes.eq("PUT").sum())
    passed = bool(
        len(data) == 2
        and call_count == 1
        and put_count == 1
        and missing == 0
        and same_underlying
        and same_expiry
        and same_strike
    )
    return {
        "metadata_rows": int(len(data)),
        "call_count": call_count,
        "put_count": put_count,
        "missing_required_count": missing,
        "same_underlying": same_underlying,
        "same_expiry": same_expiry,
        "same_strike": same_strike,
        "metadata_audit_pass": passed,
    }


def audit_option_bars(
    bars: pd.DataFrame,
    *,
    expected_symbols: set[str],
    start: Any,
    end: Any,
) -> dict[str, Any]:
    if bars.empty:
        return {
            "bar_rows": 0,
            "expected_symbol_count": len(expected_symbols),
            "observed_symbol_count": 0,
            "missing_symbol_count": len(expected_symbols),
            "outside_window_count": 0,
            "duplicate_key_count": 0,
            "ohlc_missing_count": 0,
            "ohlc_relation_error_count": 0,
            "negative_volume_count": 0,
            "bars_audit_pass": False,
        }
    data = bars.copy()
    data["datetime"] = pd.to_datetime(data["datetime"], errors="coerce")
    for column in ("open", "high", "low", "close", "volume"):
        data[column] = pd.to_numeric(data.get(column), errors="coerce")
    start_ts = pd.Timestamp(start).normalize()
    end_ts = pd.Timestamp(end).normalize() + pd.Timedelta(days=1) - pd.Timedelta(microseconds=1)
    outside = int(
        (data["datetime"].isna() | data["datetime"].lt(start_ts) | data["datetime"].gt(end_ts)).sum()
    )
    duplicate = int(data.duplicated(["symbol", "datetime"], keep=False).sum())
    missing = int(data[["open", "high", "low", "close"]].isna().any(axis=1).sum())
    relation_error = int(
        (
            data["high"].lt(data[["open", "low", "close"]].max(axis=1))
            | data["low"].gt(data[["open", "high", "close"]].min(axis=1))
        ).sum()
    )
    negative_volume = int(data["volume"].lt(0).sum())
    observed = set(data["symbol"].dropna().astype(str))
    missing_symbols = expected_symbols - observed
    passed = bool(
        len(data) > 0
        and not missing_symbols
        and outside == 0
        and duplicate == 0
        and missing == 0
        and relation_error == 0
        and negative_volume == 0
    )
    return {
        "bar_rows": int(len(data)),
        "expected_symbol_count": len(expected_symbols),
        "observed_symbol_count": len(observed),
        "missing_symbol_count": len(missing_symbols),
        "outside_window_count": outside,
        "duplicate_key_count": duplicate,
        "ohlc_missing_count": missing,
        "ohlc_relation_error_count": relation_error,
        "negative_volume_count": negative_volume,
        "bars_audit_pass": passed,
    }


def filter_probe_bars(
    bars: pd.DataFrame, *, start: Any, end: Any
) -> tuple[pd.DataFrame, dict[str, Any]]:
    if bars.empty:
        return bars.copy(), {
            "raw_bar_rows": 0,
            "raw_outside_window_count": 0,
            "raw_duplicate_key_count": 0,
            "filtered_bar_rows": 0,
        }
    data = bars.copy()
    data["datetime"] = pd.to_datetime(data["datetime"], errors="coerce")
    start_ts = pd.Timestamp(start).normalize()
    end_ts = pd.Timestamp(end).normalize() + pd.Timedelta(days=1) - pd.Timedelta(microseconds=1)
    inside = data["datetime"].notna() & data["datetime"].between(start_ts, end_ts)
    raw_duplicate_count = int(
        data.duplicated(["symbol", "datetime"], keep=False).sum()
    )
    filtered = (
        data[inside]
        .drop_duplicates(["symbol", "datetime"], keep="first")
        .sort_values(["symbol", "datetime"])
        .reset_index(drop=True)
    )
    return filtered, {
        "raw_bar_rows": int(len(data)),
        "raw_outside_window_count": int((~inside).sum()),
        "raw_duplicate_key_count": raw_duplicate_count,
        "filtered_bar_rows": int(len(filtered)),
    }


def classify_probe_readiness(
    *,
    module_audit: Mapping[str, Any],
    credential_audit: Mapping[str, Any],
    metadata_audit: Mapping[str, Any],
    bars_audit: Mapping[str, Any],
    network_enabled: bool,
    raw_hash_count: int,
) -> dict[str, Any]:
    module_ready = bool(module_audit.get("module_importable")) and all(
        bool(module_audit.get(key))
        for key in ("has_tqapi", "has_tqauth", "has_tqsim", "has_tqbacktest")
    )
    credentials_ready = bool(
        credential_audit.get("settings_datafeed_username_present")
    ) and bool(credential_audit.get("settings_datafeed_password_present"))
    metadata_ready = bool(metadata_audit.get("metadata_audit_pass"))
    bars_ready = bool(bars_audit.get("bars_audit_pass"))
    ready = bool(
        module_ready
        and credentials_ready
        and network_enabled
        and metadata_ready
        and bars_ready
        and raw_hash_count >= 2
    )
    return {
        "module_ready": module_ready,
        "credentials_ready": credentials_ready,
        "network_probe_enabled": bool(network_enabled),
        "metadata_ready": metadata_ready,
        "bars_ready": bars_ready,
        "raw_hash_count": int(raw_hash_count),
        "decision": (
            "stage130_tqsdk_expired_option_chain_ready_for_acquisition_manifest"
            if ready
            else "stage130_tqsdk_expired_option_chain_not_ready_close"
        ),
        "ready_for_acquisition_manifest": ready,
    }


def _normalize_tqsdk_datetime(value: Any) -> pd.Timestamp:
    ts = pd.to_datetime(value, unit="ns", errors="coerce", utc=True)
    if pd.isna(ts):
        return pd.NaT
    return ts.tz_convert(CHINA_TZ).tz_localize(None)


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float("nan")


def _redact_message(value: Any, secrets: list[str]) -> str:
    text = repr(value)
    for secret in secrets:
        if secret:
            text = text.replace(secret, "<redacted>")
    return text


def _collect_kline_rows(symbol: str, frame: pd.DataFrame) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if frame.empty:
        return rows
    for _, item in frame.iterrows():
        bar_dt = _normalize_tqsdk_datetime(item.get("datetime"))
        if pd.isna(bar_dt):
            continue
        rows.append(
            {
                "symbol": symbol,
                "datetime": bar_dt,
                "bar_id": int(_safe_float(item.get("id", -1))),
                "open": _safe_float(item.get("open")),
                "high": _safe_float(item.get("high")),
                "low": _safe_float(item.get("low")),
                "close": _safe_float(item.get("close")),
                "volume": _safe_float(item.get("volume")),
                "open_oi": _safe_float(item.get("open_oi")),
                "close_oi": _safe_float(item.get("close_oi")),
            }
        )
    return rows


def run_network_probe(
    *, username: str, password: str, max_seconds: int
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    from tqsdk import BacktestFinished, TqApi, TqAuth, TqBacktest, TqSim

    started = time.time()
    metadata = pd.DataFrame()
    selected = pd.DataFrame()
    raw_bars = pd.DataFrame()
    bars = pd.DataFrame()
    api = None
    status: dict[str, Any] = {
        "underlying_symbol": UNDERLYING_SYMBOL,
        "probe_start": PROBE_START.date().isoformat(),
        "probe_end": PROBE_END.date().isoformat(),
        "status": "unknown",
        "query_expired_as_of_backtest": OPTION_QUERY_EXPIRED_AS_OF_BACKTEST,
        "query_option_count": 0,
        "metadata_rows": 0,
        "selected_rows": 0,
        "bar_rows": 0,
        "elapsed_seconds": 0.0,
        "message": "",
    }
    secrets = [username, password]
    try:
        api = TqApi(
            TqSim(),
            backtest=TqBacktest(
                start_dt=PROBE_START.to_pydatetime(),
                end_dt=(PROBE_END + pd.Timedelta(hours=23, minutes=59)).to_pydatetime(),
            ),
            auth=TqAuth(username, password),
        )
        option_symbols = list(
            api.query_options(
                UNDERLYING_SYMBOL,
                expired=OPTION_QUERY_EXPIRED_AS_OF_BACKTEST,
            )
        )
        status["query_option_count"] = len(option_symbols)
        if not option_symbols:
            status["status"] = "empty_active_option_query_at_backtest_timestamp"
            return metadata, selected, raw_bars, bars, status

        metadata_ref = api.query_symbol_info(option_symbols)
        metadata = normalize_option_metadata(pd.DataFrame(metadata_ref).copy())
        status["metadata_rows"] = len(metadata)
        reference_price = float(
            pd.to_numeric(metadata["strike_price"], errors="coerce").median()
        )
        selected = select_same_expiry_call_put(
            metadata,
            underlying_symbol=UNDERLYING_SYMBOL,
            reference_price=reference_price,
        )
        status["selected_rows"] = len(selected)
        if len(selected) != 2:
            status["status"] = "no_same_expiry_call_put_pair"
            return metadata, selected, raw_bars, bars, status

        symbols = [UNDERLYING_SYMBOL] + selected["option_symbol"].astype(str).tolist()
        kline_frames = {
            symbol: api.get_kline_serial(symbol, duration_seconds=86_400, data_length=20)
            for symbol in symbols
        }
        while True:
            if time.time() - started > max_seconds:
                status["status"] = "timeout"
                status["message"] = f"timeout_after_{max_seconds}s"
                break
            try:
                api.wait_update(deadline=time.time() + 1.0)
            except BacktestFinished:
                status["status"] = "extracted"
                break
        bar_rows: list[dict[str, Any]] = []
        for symbol, frame in kline_frames.items():
            bar_rows.extend(_collect_kline_rows(symbol, frame))
        raw_bars = pd.DataFrame(bar_rows)
        bars, filter_audit = filter_probe_bars(
            raw_bars,
            start=PROBE_START,
            end=PROBE_END,
        )
        status.update(filter_audit)
        status["bar_rows"] = len(bars)
        if status["status"] == "unknown":
            status["status"] = "extracted" if len(bars) else "empty_bars"
    except Exception as exc:
        status["status"] = "failed"
        status["message"] = _redact_message(exc, secrets)
    finally:
        if api is not None:
            api.close()
        status["elapsed_seconds"] = round(time.time() - started, 2)
    return metadata, selected, raw_bars, bars, status


def _manifest() -> pd.DataFrame:
    rows = []
    for path in sorted(OUTPUT_DIR.iterdir()):
        if not path.is_file() or path == MANIFEST_PATH:
            continue
        rows.append(
            {"file": path.name, "bytes": path.stat().st_size, "sha256": _sha256(path)}
        )
    return pd.DataFrame(rows)


def _write_report(
    *,
    decision: dict[str, Any],
    status: pd.DataFrame,
    metadata_audit: pd.DataFrame,
    bars_audit: pd.DataFrame,
    selected: pd.DataFrame,
) -> None:
    REPORT_PATH.write_text(
        f"""# Stage130 TqSdk 2022 过期期权链数据探针

- 生成时间：`{decision['generated_at']}`
- 决策：`{decision['decision']}`
- 固定标的/窗口：`{UNDERLYING_SYMBOL}` / `{PROBE_START.date()} -> {PROBE_END.date()}`
- 本阶段只验证历史期权链数据，不回测收益、不修改策略、不连接 CTP、不调用订单 API。

## Probe Status

{_md_table(status)}

## Selected CALL/PUT

{_md_table(selected)}

## Metadata Audit

{_md_table(metadata_audit)}

## Bars Audit

{_md_table(bars_audit)}

## 判断

- 过拟合：否；没有收益标签、策略参数或结果后切换品种/窗口。
- 继续价值：{'有，下一步只允许完整 acquisition manifest。' if decision['ready_for_acquisition_manifest'] else '无，按预声明关闭期权路线，不换端点救援。'}
- 成功下载不代表保护性期权有效；后续仍需完整 PIT、premium、流动性和三锚点真实 A/B。
""",
        encoding="utf-8",
    )


def run() -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    module_audit = inspect_tqsdk_module()
    credential_audit = audit_tqsdk_credentials()
    metadata = pd.DataFrame()
    selected = pd.DataFrame()
    raw_bars = pd.DataFrame()
    bars = pd.DataFrame()
    status_dict: dict[str, Any] = {
        "underlying_symbol": UNDERLYING_SYMBOL,
        "probe_start": PROBE_START.date().isoformat(),
        "probe_end": PROBE_END.date().isoformat(),
        "status": "network_disabled",
        "query_expired_as_of_backtest": OPTION_QUERY_EXPIRED_AS_OF_BACKTEST,
        "query_option_count": 0,
        "metadata_rows": 0,
        "selected_rows": 0,
        "bar_rows": 0,
        "elapsed_seconds": 0.0,
        "message": "",
    }
    credentials_ready = bool(
        credential_audit["settings_datafeed_username_present"]
        and credential_audit["settings_datafeed_password_present"]
    )
    if ENABLE_NETWORK_PROBE and module_audit["module_importable"] and credentials_ready:
        metadata, selected, raw_bars, bars, status_dict = run_network_probe(
            username=str(SETTINGS.get("datafeed.username", "")).strip(),
            password=str(SETTINGS.get("datafeed.password", "")).strip(),
            max_seconds=MAX_NETWORK_SECONDS,
        )

    metadata.to_csv(METADATA_PATH, index=False, encoding="utf-8-sig")
    selected.to_csv(SELECTED_PATH, index=False, encoding="utf-8-sig")
    raw_bars.to_csv(RAW_BARS_PATH, index=False, encoding="utf-8-sig")
    bars.to_csv(BARS_PATH, index=False, encoding="utf-8-sig")
    pd.DataFrame([status_dict]).to_csv(STATUS_PATH, index=False, encoding="utf-8-sig")
    pd.DataFrame([module_audit]).to_csv(MODULE_AUDIT_PATH, index=False, encoding="utf-8-sig")
    pd.DataFrame([credential_audit]).to_csv(
        CREDENTIAL_AUDIT_PATH, index=False, encoding="utf-8-sig"
    )
    filter_audit = {
        key: int(status_dict.get(key, 0) or 0)
        for key in (
            "raw_bar_rows",
            "raw_outside_window_count",
            "raw_duplicate_key_count",
            "filtered_bar_rows",
        )
    }
    pd.DataFrame([filter_audit]).to_csv(
        FILTER_AUDIT_PATH, index=False, encoding="utf-8-sig"
    )

    metadata_audit = audit_option_metadata(
        selected, underlying_symbol=UNDERLYING_SYMBOL
    )
    expected_symbols = {UNDERLYING_SYMBOL} | set(
        selected.get("option_symbol", pd.Series(dtype=str)).astype(str)
    )
    bars_audit = audit_option_bars(
        bars,
        expected_symbols=expected_symbols,
        start=PROBE_START,
        end=PROBE_END,
    )
    raw_hash_count, raw_hash_records = verified_raw_hashes(
        {
            "metadata": (METADATA_PATH, len(metadata)),
            "raw_bars": (RAW_BARS_PATH, len(raw_bars)),
            "filtered_bars": (BARS_PATH, len(bars)),
        }
    )
    readiness = classify_probe_readiness(
        module_audit=module_audit,
        credential_audit=credential_audit,
        metadata_audit=metadata_audit,
        bars_audit=bars_audit,
        network_enabled=ENABLE_NETWORK_PROBE,
        raw_hash_count=raw_hash_count,
    )
    generated_at = datetime.now().replace(microsecond=0).isoformat()
    decision = {
        "stage": STAGE,
        "stage_id": STAGE_ID,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": generated_at,
        "underlying_symbol": UNDERLYING_SYMBOL,
        "probe_start": PROBE_START.date().isoformat(),
        "probe_end": PROBE_END.date().isoformat(),
        **readiness,
        "probe_status": status_dict.get("status", ""),
        "query_expired_as_of_backtest": OPTION_QUERY_EXPIRED_AS_OF_BACKTEST,
        "query_option_count": int(status_dict.get("query_option_count", 0)),
        "metadata_rows": int(len(metadata)),
        "selected_rows": int(len(selected)),
        "bar_rows": int(len(bars)),
        "metadata_audit": metadata_audit,
        "bars_audit": bars_audit,
        "filter_audit": filter_audit,
        "raw_hash_records": raw_hash_records,
        "strategy_rule_created": False,
        "true_engine_run": False,
        "formal_ab_triggered": False,
        "official_live_strategy_changed": False,
        "order_api_called": False,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "ctp_connected": False,
        "overfit_before": "否；固定单标的单窗口数据权限探针，无收益参数。",
        "overfit_after": "待独立审查；不得把下载成功解释成策略有效。",
        "continue_value_before": "有；期权保护层是现有失败路线之外的正交结构。",
        "continue_value_after": (
            "有；只允许进入完整 acquisition manifest。"
            if readiness["ready_for_acquisition_manifest"]
            else "无；按预声明关闭，不换端点、品种或窗口救援。"
        ),
        "source_links": SOURCE_LINKS,
    }
    metadata_audit_frame = pd.DataFrame([metadata_audit])
    bars_audit_frame = pd.DataFrame([bars_audit])
    metadata_audit_frame.to_csv(METADATA_AUDIT_PATH, index=False, encoding="utf-8-sig")
    bars_audit_frame.to_csv(BARS_AUDIT_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(
        json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    lineage = {
        "stage": STAGE,
        "tool": {"path": str(Path(__file__).resolve()), "sha256": _sha256(Path(__file__).resolve())},
        "test": {"path": str(TEST_PATH), "sha256": _sha256(TEST_PATH)},
        "predecl": {"path": str(PREDECL_PATH), "sha256": _sha256(PREDECL_PATH)},
        "generated_at": generated_at,
        "query_context": {
            "sdk_version": module_audit.get("module_version", ""),
            "underlying_symbol": UNDERLYING_SYMBOL,
            "backtest_start": PROBE_START.date().isoformat(),
            "backtest_end": PROBE_END.date().isoformat(),
            "query_method": "TqApi.query_options",
            "query_expired_as_of_backtest": OPTION_QUERY_EXPIRED_AS_OF_BACKTEST,
            "metadata_method": "TqApi.query_symbol_info",
            "bar_method": "TqApi.get_kline_serial",
            "bar_duration_seconds": 86_400,
        },
        "raw_files": raw_hash_records,
        "credential_values_persisted": False,
        "history_database_snapshot_complete": False,
    }
    LINEAGE_PATH.write_text(
        json.dumps(_json_safe(lineage), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    _write_report(
        decision=decision,
        status=pd.DataFrame([status_dict]),
        metadata_audit=metadata_audit_frame,
        bars_audit=bars_audit_frame,
        selected=selected,
    )
    _manifest().to_csv(MANIFEST_PATH, index=False, encoding="utf-8-sig")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    return decision


if __name__ == "__main__":
    run()
