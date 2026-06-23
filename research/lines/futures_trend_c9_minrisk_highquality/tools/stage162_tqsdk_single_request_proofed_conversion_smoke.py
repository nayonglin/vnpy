from __future__ import annotations

from datetime import datetime, timedelta
import hashlib
import json
import logging
import os
from pathlib import Path
import time
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


LINE_ID = "futures_trend_c9_minrisk_highquality"
STAGE = "Stage162"
MODEL_TAG = "stage162_tqsdk_single_request_proofed_conversion_smoke_v1"
OUTPUT_PREFIX = "qmt_roll_stage162_c9_minrisk_tqsdk_single_request_proofed_conversion_smoke"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage162_tqsdk_single_request_proofed_conversion_smoke"

CURVE_IN = (
    LINE_DIR
    / "outputs"
    / "stage045_event_time_field_sync_audit"
    / "qmt_roll_stage045_c9_minrisk_event_time_field_sync_audit_semantic_curve_"
    "stage045_event_time_field_sync_audit_v1.csv"
)
STAGE152_DIR = LINE_DIR / "outputs" / "stage152_authoritative_minute_ohlcv_manifest"
STAGE152_PREFIX = "qmt_roll_stage152_c9_minrisk_authoritative_minute_ohlcv_manifest"
STAGE152_TAG = "stage152_authoritative_minute_ohlcv_manifest_v1"
STAGE152_REQUEST_TEMPLATE_IN = STAGE152_DIR / f"{STAGE152_PREFIX}_request_manifest_template_{STAGE152_TAG}.csv"
STAGE160_SUMMARY_IN = (
    LINE_DIR
    / "outputs"
    / "stage160_authoritative_minute_arrival_monitor"
    / "qmt_roll_stage160_c9_minrisk_authoritative_minute_arrival_monitor_summary_"
    "stage160_authoritative_minute_arrival_monitor_v1.csv"
)

SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
SELECTED_REQUEST_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_selected_request_{MODEL_TAG}.csv"
FETCH_STATUS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_fetch_status_{MODEL_TAG}.csv"
RAW_SAMPLE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_raw_bars_sample_{MODEL_TAG}.csv"
NORMALIZED_SAMPLE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_normalized_bars_sample_{MODEL_TAG}.csv"
DELIVERY_AUDIT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_delivery_audit_{MODEL_TAG}.csv"
GATE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gate_status_{MODEL_TAG}.csv"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_conversion_status_{MODEL_TAG}.png"
KLINE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_selected_request_kline_{MODEL_TAG}.png"
VOLUME_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_selected_request_volume_oi_{MODEL_TAG}.png"
DELIVERY_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_delivery_matrix_{MODEL_TAG}.png"
GATE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gate_status_matrix_{MODEL_TAG}.png"

MAX_SECONDS = int(os.getenv("STAGE162_MAX_SECONDS", "120"))
WRITE_INCOMING = os.getenv("STAGE162_WRITE_INCOMING", "1").strip() != "0"
MIN_NORMALIZED_ROWS = int(os.getenv("STAGE162_MIN_NORMALIZED_ROWS", "10"))
DATA_LENGTH = int(os.getenv("STAGE162_DATA_LENGTH", "1000"))


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, Path):
        return str(value)
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
        return pd.Timestamp(value).strftime("%Y-%m-%d %H:%M:%S")
    return value


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size <= 4:
        return pd.DataFrame()
    return pd.read_csv(path, encoding="utf-8-sig")


def _write_csv(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, encoding="utf-8-sig")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_json_safe(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_empty_"
    data = frame.head(max_rows).copy() if max_rows is not None else frame.copy()
    for column in data.columns:
        if pd.api.types.is_float_dtype(data[column]):
            data[column] = data[column].map(lambda value: "" if pd.isna(value) else f"{value:.6f}")
        else:
            data[column] = data[column].map(
                lambda value: "" if pd.isna(value) else str(value).replace("|", "\\|").replace("\n", "<br>")
            )
    lines = [
        "| " + " | ".join(str(column) for column in data.columns) + " |",
        "| " + " | ".join(["---"] * len(data.columns)) + " |",
    ]
    for _, row in data.iterrows():
        lines.append("| " + " | ".join(str(row[column]) for column in data.columns) + " |")
    return "\n".join(lines)


def _row(path: Path) -> dict[str, Any]:
    frame = _read_csv(path)
    return frame.iloc[0].to_dict() if not frame.empty else {}


def _num(row: dict[str, Any], key: str, default: float = 0.0) -> float:
    value = row.get(key, default)
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if np.isnan(number) or np.isinf(number):
        return default
    return number


def _load_curve() -> pd.DataFrame:
    curve = _read_csv(CURVE_IN)
    if curve.empty:
        raise RuntimeError(f"missing curve input: {CURVE_IN}")
    curve["date"] = pd.to_datetime(curve["date"], errors="coerce").dt.normalize()
    for column in ["account_equity", "drawdown_pct", "broker10_margin_to_equity_pct"]:
        curve[column] = pd.to_numeric(curve[column], errors="coerce")
    return curve[curve["date"].notna()].sort_values("date").reset_index(drop=True)


def _baseline_metrics(curve: pd.DataFrame) -> dict[str, float]:
    stage160 = _row(STAGE160_SUMMARY_IN)
    if stage160:
        return {
            "end_equity": _num(stage160, "end_equity", np.nan),
            "total_return_pct": _num(stage160, "total_return_pct", np.nan),
            "max_drawdown_pct": _num(stage160, "max_drawdown_pct", np.nan),
            "sharpe": _num(stage160, "sharpe", np.nan),
            "total_slippage": _num(stage160, "total_slippage", np.nan),
            "total_trade_count": _num(stage160, "total_trade_count", np.nan),
            "closed_lot_win_rate_pct": _num(stage160, "closed_lot_win_rate_pct", np.nan),
            "max_broker10_margin_to_equity_pct": _num(stage160, "max_broker10_margin_to_equity_pct", np.nan),
        }
    first_equity = float(curve["account_equity"].dropna().iloc[0])
    end_equity = float(curve["account_equity"].dropna().iloc[-1])
    return {
        "end_equity": end_equity,
        "total_return_pct": (end_equity / first_equity - 1.0) * 100.0,
        "max_drawdown_pct": float(curve["drawdown_pct"].min()),
        "sharpe": np.nan,
        "total_slippage": np.nan,
        "total_trade_count": np.nan,
        "closed_lot_win_rate_pct": np.nan,
        "max_broker10_margin_to_equity_pct": float(curve["broker10_margin_to_equity_pct"].max()),
    }


def _resolve_path(path_text: Any) -> Path:
    path = Path(str(path_text))
    return path if path.is_absolute() else (REPO_DIR / path)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _schema_hash(columns: list[str]) -> str:
    return hashlib.sha256(json.dumps(columns, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def _split_vt(vt_symbol: str) -> tuple[str, str]:
    symbol, exchange = str(vt_symbol).split(".", 1)
    return symbol, exchange


def _to_tq_symbol(vt_symbol: str) -> str:
    symbol, exchange = _split_vt(vt_symbol)
    return f"{exchange}.{symbol}"


def _select_request(manifest: pd.DataFrame) -> pd.Series:
    request_id = os.getenv("STAGE162_REQUEST_ID", "").strip()
    data = manifest.copy()
    if request_id:
        hit = data[data["request_id"].astype(str).eq(request_id)]
        if hit.empty:
            raise RuntimeError(f"STAGE162_REQUEST_ID not found in Stage152 manifest: {request_id}")
        return hit.iloc[0]
    data["request_date_dt"] = pd.to_datetime(data["request_date"], errors="coerce")
    data["priority_score_num"] = pd.to_numeric(data["priority_score"], errors="coerce").fillna(0)
    return data.sort_values(["request_date_dt", "priority_score_num", "request_id"], ascending=[False, False, True]).iloc[0]


def _normalize_tqsdk_datetime(value: Any) -> pd.Timestamp:
    from vnpy.trader.utility import ZoneInfo

    ts = pd.to_datetime(value, unit="ns", errors="coerce", utc=True)
    if pd.isna(ts):
        return pd.NaT
    return ts.tz_convert(ZoneInfo("Asia/Shanghai")).tz_localize(None)


def _credentials() -> dict[str, Any]:
    try:
        from vnpy.trader.setting import SETTINGS
    except Exception as exc:
        return {"username": "", "password": "", "username_present": 0, "password_present": 0, "error": repr(exc)[:300]}
    username = str(SETTINGS.get("datafeed.username", "") or "")
    password = str(SETTINGS.get("datafeed.password", "") or "")
    return {
        "username": username,
        "password": password,
        "username_present": int(bool(username)),
        "password_present": int(bool(password)),
        "username_len": len(username),
        "password_len": len(password),
        "error": "",
    }


def _extract_tqsdk_minutes(row: pd.Series, credential: dict[str, Any]) -> tuple[dict[str, Any], pd.DataFrame]:
    request_id = str(row["request_id"])
    vt_symbol = str(row["vt_symbol"])
    tq_symbol = _to_tq_symbol(vt_symbol)
    request_start = pd.Timestamp(row["request_start_ts"])
    request_end = pd.Timestamp(row["request_end_ts"])
    start_dt = request_start - timedelta(hours=1)
    end_dt = request_end + timedelta(hours=1)
    status: dict[str, Any] = {
        "request_id": request_id,
        "vt_symbol": vt_symbol,
        "tq_symbol": tq_symbol,
        "request_start_ts": request_start.strftime("%Y-%m-%d %H:%M:%S"),
        "request_end_ts": request_end.strftime("%Y-%m-%d %H:%M:%S"),
        "query_start_ts": start_dt.strftime("%Y-%m-%d %H:%M:%S"),
        "query_end_ts": end_dt.strftime("%Y-%m-%d %H:%M:%S"),
        "credential_present": int(credential["username_present"] and credential["password_present"]),
        "credential_username_len": int(credential.get("username_len", 0)),
        "credential_password_len": int(credential.get("password_len", 0)),
        "tqsdk_import_ok": 0,
        "fetch_status": "not_started",
        "raw_row_count": 0,
        "normalized_row_count": 0,
        "positive_volume_row_count": 0,
        "elapsed_seconds": 0.0,
        "message": "",
    }
    if not status["credential_present"]:
        status["fetch_status"] = "missing_credentials"
        status["message"] = credential.get("error", "") or "vnpy SETTINGS datafeed credentials missing"
        return status, pd.DataFrame()
    try:
        from tqsdk import BacktestFinished, TqApi, TqAuth, TqBacktest, TqSim
    except Exception as exc:
        status["fetch_status"] = "import_failed"
        status["message"] = repr(exc)[:500]
        return status, pd.DataFrame()

    status["tqsdk_import_ok"] = 1
    logging.getLogger().setLevel(logging.WARNING)
    logging.getLogger("tqsdk").setLevel(logging.WARNING)
    api = None
    rows: list[dict[str, Any]] = []
    seen_ids: set[int] = set()
    started = time.time()
    try:
        api = TqApi(
            TqSim(),
            backtest=TqBacktest(start_dt=start_dt.to_pydatetime(), end_dt=end_dt.to_pydatetime()),
            auth=TqAuth(str(credential["username"]), str(credential["password"])),
            disable_print=True,
        )
        klines = api.get_kline_serial(tq_symbol, duration_seconds=60, data_length=DATA_LENGTH)
        while True:
            if time.time() - started > MAX_SECONDS:
                status["fetch_status"] = "timeout"
                status["message"] = f"timeout_after_{MAX_SECONDS}s"
                break
            api.wait_update()
            if not api.is_changing(klines.iloc[-1], "datetime"):
                continue
            bar = klines.iloc[-1].to_dict()
            bar_id = int(bar.get("id", -1))
            if bar_id in seen_ids:
                continue
            seen_ids.add(bar_id)
            bar_dt = _normalize_tqsdk_datetime(bar.get("datetime"))
            if pd.isna(bar_dt):
                continue
            rows.append(
                {
                    "request_id": request_id,
                    "exchange": str(row["exchange"]),
                    "vt_symbol": vt_symbol,
                    "tq_symbol": tq_symbol,
                    "bar_datetime": pd.Timestamp(bar_dt).strftime("%Y-%m-%d %H:%M:%S"),
                    "bar_id": bar_id,
                    "open": float(bar.get("open", np.nan)),
                    "high": float(bar.get("high", np.nan)),
                    "low": float(bar.get("low", np.nan)),
                    "close": float(bar.get("close", np.nan)),
                    "volume": float(bar.get("volume", np.nan)),
                    "amount": float(bar.get("amount", np.nan)),
                    "open_oi": float(bar.get("open_oi", np.nan)),
                    "close_oi": float(bar.get("close_oi", np.nan)),
                    "source_method": "tqsdk_backtest_get_kline_serial_1m",
                }
            )
    except BacktestFinished:
        status["fetch_status"] = "extracted"
    except Exception as exc:
        status["fetch_status"] = "failed"
        status["message"] = repr(exc)[:500]
    finally:
        if api is not None:
            api.close()
    raw = pd.DataFrame(rows)
    if not raw.empty:
        raw["bar_datetime"] = pd.to_datetime(raw["bar_datetime"], errors="coerce")
        raw = raw.dropna(subset=["bar_datetime"])
        raw = raw.drop_duplicates(["vt_symbol", "bar_datetime"]).sort_values(["vt_symbol", "bar_datetime"]).reset_index(drop=True)
    if status["fetch_status"] == "not_started":
        status["fetch_status"] = "extracted" if not raw.empty else "empty"
    mask = pd.Series(False, index=raw.index)
    if not raw.empty:
        mask = raw["bar_datetime"].ge(request_start) & raw["bar_datetime"].le(request_end)
    status["raw_row_count"] = int(len(raw))
    status["normalized_row_count"] = int(mask.sum())
    status["positive_volume_row_count"] = int(pd.to_numeric(raw.loc[mask, "volume"], errors="coerce").fillna(0).gt(0).sum()) if not raw.empty else 0
    status["elapsed_seconds"] = round(time.time() - started, 2)
    return status, raw


def _normalized_bars(row: pd.Series, raw: pd.DataFrame) -> pd.DataFrame:
    if raw.empty:
        return pd.DataFrame()
    request_start = pd.Timestamp(row["request_start_ts"])
    request_end = pd.Timestamp(row["request_end_ts"])
    data = raw[(raw["bar_datetime"].ge(request_start)) & (raw["bar_datetime"].le(request_end))].copy()
    if data.empty:
        return pd.DataFrame()
    data["bar_start_ts"] = pd.to_datetime(data["bar_datetime"], errors="coerce")
    data["bar_end_ts"] = data["bar_start_ts"] + pd.Timedelta(minutes=1)
    normalized = pd.DataFrame(
        {
            "exchange": str(row["exchange"]),
            "vt_symbol": str(row["vt_symbol"]),
            "bar_start_ts": data["bar_start_ts"].dt.strftime("%Y-%m-%d %H:%M:%S"),
            "bar_end_ts": data["bar_end_ts"].dt.strftime("%Y-%m-%d %H:%M:%S"),
            "open": pd.to_numeric(data["open"], errors="coerce"),
            "high": pd.to_numeric(data["high"], errors="coerce"),
            "low": pd.to_numeric(data["low"], errors="coerce"),
            "close": pd.to_numeric(data["close"], errors="coerce"),
            "volume": pd.to_numeric(data["volume"], errors="coerce").fillna(0.0),
            "turnover": pd.to_numeric(data["amount"], errors="coerce"),
            "open_interest": pd.to_numeric(data["close_oi"], errors="coerce"),
            "source_bar_id": pd.to_numeric(data["bar_id"], errors="coerce").astype("Int64"),
            "source_method": "tqsdk_backtest_get_kline_serial_1m",
        }
    )
    return normalized.dropna(subset=["bar_start_ts", "open", "high", "low", "close"]).reset_index(drop=True)


def _write_delivery(row: pd.Series, raw: pd.DataFrame, normalized: pd.DataFrame, status: dict[str, Any]) -> tuple[pd.DataFrame, dict[str, Any]]:
    raw_path = _resolve_path(row["expected_raw_file"])
    normalized_path = _resolve_path(row["expected_normalized_file"])
    proof_path = _resolve_path(row["expected_proof_file"])
    delivery = {
        "request_id": str(row["request_id"]),
        "write_incoming_enabled": int(WRITE_INCOMING),
        "raw_path": str(raw_path.relative_to(REPO_DIR)),
        "normalized_path": str(normalized_path.relative_to(REPO_DIR)),
        "proof_path": str(proof_path.relative_to(REPO_DIR)),
        "raw_written": 0,
        "normalized_written": 0,
        "proof_written": 0,
        "expected_files_written": 0,
        "write_blocker": "",
        "raw_sha256": "",
        "schema_hash": "",
    }
    ready_to_write = (
        WRITE_INCOMING
        and not raw.empty
        and not normalized.empty
        and len(normalized) >= MIN_NORMALIZED_ROWS
        and status.get("positive_volume_row_count", 0) > 0
    )
    if not ready_to_write:
        delivery["write_blocker"] = "not_enough_real_tqsdk_rows_or_write_disabled"
        return pd.DataFrame([delivery]), delivery
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    normalized_path.parent.mkdir(parents=True, exist_ok=True)
    proof_path.parent.mkdir(parents=True, exist_ok=True)
    raw.to_csv(raw_path, index=False, encoding="utf-8-sig", compression={"method": "zstd", "level": 3})
    normalized.to_parquet(normalized_path, index=False)
    raw_sha = _sha256(raw_path)
    schema_columns = list(normalized.columns)
    schema_hash = _schema_hash(schema_columns)
    proof = {
        "request_id": str(row["request_id"]),
        "vendor_name": "TqSdk",
        "vendor_license": "local vnpy datafeed entitlement used for historical backtest query",
        "dataset_id": "tqsdk_backtest_get_kline_serial_1m",
        "query_params": {
            "tq_symbol": _to_tq_symbol(str(row["vt_symbol"])),
            "duration_seconds": 60,
            "data_length": DATA_LENGTH,
            "query_start_ts": status["query_start_ts"],
            "query_end_ts": status["query_end_ts"],
            "selected_request_policy": "latest_request_date_then_priority_score_not_pnl",
        },
        "raw_file": str(raw_path.relative_to(REPO_DIR)),
        "raw_sha256": raw_sha,
        "schema_hash": schema_hash,
        "exchange": str(row["exchange"]),
        "vt_symbol": str(row["vt_symbol"]),
        "request_start_ts": str(row["request_start_ts"]),
        "request_end_ts": str(row["request_end_ts"]),
        "timezone": "Asia/Shanghai",
        "session_calendar": f"{row['exchange']} exchange trading calendar from vendor query",
        "no_trade_bar_policy": "vendor emits traded interval bars; validator must require positive volume in covered windows",
        "synthetic_or_adjusted_flag": False,
        "normalization": {
            "bar_start_ts": "TqSdk kline datetime converted from UTC ns to Asia/Shanghai",
            "bar_end_ts": "bar_start_ts plus 60 seconds",
            "open_interest": "close_oi from TqSdk 1m kline",
        },
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    _write_json(proof_path, proof)
    delivery.update(
        {
            "raw_written": int(raw_path.exists()),
            "normalized_written": int(normalized_path.exists()),
            "proof_written": int(proof_path.exists()),
            "expected_files_written": int(raw_path.exists()) + int(normalized_path.exists()) + int(proof_path.exists()),
            "raw_sha256": raw_sha,
            "schema_hash": schema_hash,
        }
    )
    return pd.DataFrame([delivery]), delivery


def _gate_status(summary: dict[str, Any]) -> pd.DataFrame:
    rows = [
        ("request_selected", summary["selected_request_count"], 1, "contract_hard"),
        ("credentials_present", summary["credential_present"], 1, "source_hard"),
        ("tqsdk_import_ok", summary["tqsdk_import_ok"], 1, "source_hard"),
        ("tqsdk_fetch_succeeded", summary["tqsdk_fetch_succeeded"], 1, "source_hard"),
        ("normalized_rows_min", summary["normalized_row_count"], MIN_NORMALIZED_ROWS, "data_hard"),
        ("positive_volume_rows", summary["positive_volume_row_count"], 1, "data_hard"),
        ("expected_files_written", summary["expected_files_written"], 3, "delivery_hard"),
        ("stage153_full_package_ready", summary["stage153_full_package_ready"], 0, "strategy_hard"),
        ("strategy_rule_created", summary["strategy_rule_created"], 0, "strategy_hard"),
        ("true_engine_run", summary["true_engine_run"], 0, "strategy_hard"),
        ("order_api_called", summary["order_api_called"], 0, "safety_hard"),
    ]
    return pd.DataFrame(
        [
            {
                "gate_id": gate_id,
                "observed": int(observed),
                "required": int(required),
                "pass_now": int(int(observed) >= int(required)) if required > 0 else int(int(observed) == 0),
                "severity": severity,
            }
            for gate_id, observed, required, severity in rows
        ]
    )


def _write_report(summary: dict[str, Any], selected: pd.DataFrame, fetch_status: pd.DataFrame, delivery: pd.DataFrame, gate: pd.DataFrame) -> None:
    REPORT_OUT.parent.mkdir(parents=True, exist_ok=True)
    text = "\n".join(
        [
            "# Stage162 TqSdk Single Request Proofed Conversion",
            "",
            f"- model_tag: `{MODEL_TAG}`",
            f"- decision: `{summary['decision']}`",
            "- Scope: one-request data delivery probe for Stage152 authoritative minute package.",
            "- Hard lock: no strategy rule, no true engine, no A/B, no CTP, no order API, no official config change.",
            "",
            "## Summary",
            "",
            _md_table(pd.DataFrame([summary])),
            "",
            "## Selected Request",
            "",
            _md_table(selected),
            "",
            "## Fetch Status",
            "",
            _md_table(fetch_status),
            "",
            "## Delivery Audit",
            "",
            _md_table(delivery),
            "",
            "## Gate Status",
            "",
            _md_table(gate),
            "",
            "## Next",
            "",
            "- If this probe wrote all three expected files, rerun Stage160 then Stage153 to validate the one delivered request while the full package remains blocked.",
            "- If this probe failed, stop trying strategy work and wait for an authorized Stage152 delivery or credentials/source repair.",
            "",
        ]
    )
    REPORT_OUT.write_text(text, encoding="utf-8")


def _plot_path(curve: pd.DataFrame, summary: dict[str, Any]) -> None:
    fig, axes = plt.subplots(3, 1, figsize=(15, 11), sharex=True)
    axes[0].plot(curve["date"], curve["account_equity"], color="#1f77b4", linewidth=1.8)
    axes[0].set_title("Official Path With Stage162 Conversion Status")
    axes[0].set_ylabel("Equity")
    axes[0].grid(alpha=0.25)
    axes[0].text(
        0.01,
        0.95,
        f"request={summary['request_id']} | rows={summary['normalized_row_count']} | files={summary['expected_files_written']}/3",
        transform=axes[0].transAxes,
        va="top",
        fontsize=10,
        bbox={"facecolor": "white", "edgecolor": "#cccccc", "alpha": 0.9},
    )
    axes[1].plot(curve["date"], curve["drawdown_pct"], color="#d62728", linewidth=1.3)
    axes[1].axhline(-30, color="#888888", linestyle="--", linewidth=0.9)
    axes[1].set_ylabel("Drawdown %")
    axes[1].grid(alpha=0.25)
    axes[2].plot(curve["date"], curve["broker10_margin_to_equity_pct"], color="#9467bd", linewidth=1.2)
    axes[2].axhline(100, color="#888888", linestyle="--", linewidth=0.9)
    axes[2].set_ylabel("Broker10 %")
    axes[2].grid(alpha=0.25)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(PATH_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_kline(normalized: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(13, 6))
    if normalized.empty:
        ax.text(0.5, 0.5, "No normalized bars", ha="center", va="center")
        ax.axis("off")
    else:
        data = normalized.copy()
        data["bar_start_ts"] = pd.to_datetime(data["bar_start_ts"], errors="coerce")
        ax.plot(data["bar_start_ts"], data["close"], color="#1f77b4", linewidth=1.5, label="close")
        ax.fill_between(data["bar_start_ts"], data["low"], data["high"], color="#aec7e8", alpha=0.35, label="low-high")
        ax.set_title("Selected Request 1m Price Path")
        ax.set_ylabel("Price")
        ax.legend()
        ax.grid(alpha=0.25)
        fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(KLINE_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_volume(normalized: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 1, figsize=(13, 7), sharex=True)
    if normalized.empty:
        axes[0].text(0.5, 0.5, "No normalized bars", ha="center", va="center")
        axes[0].axis("off")
        axes[1].axis("off")
    else:
        data = normalized.copy()
        data["bar_start_ts"] = pd.to_datetime(data["bar_start_ts"], errors="coerce")
        axes[0].bar(data["bar_start_ts"], data["volume"], width=0.0007, color="#2ca02c")
        axes[0].set_ylabel("Volume")
        axes[0].set_title("Volume And Open Interest")
        axes[0].grid(alpha=0.25)
        axes[1].plot(data["bar_start_ts"], data["open_interest"], color="#ff7f0e", linewidth=1.2)
        axes[1].set_ylabel("Open Interest")
        axes[1].grid(alpha=0.25)
        fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(VOLUME_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_delivery(delivery: pd.DataFrame) -> None:
    cols = ["raw_written", "normalized_written", "proof_written"]
    matrix = delivery[cols].to_numpy(dtype=float) if not delivery.empty else np.zeros((1, len(cols)))
    fig, ax = plt.subplots(figsize=(9, 3.8))
    ax.imshow(matrix, aspect="auto", cmap=plt.get_cmap("RdYlGn"), vmin=0, vmax=1)
    ax.set_xticks(np.arange(len(cols)))
    ax.set_xticklabels(cols, rotation=20, ha="right")
    ax.set_yticks([0])
    ax.set_yticklabels(["selected_request"])
    ax.set_title("Stage162 Expected File Delivery Matrix")
    for col_idx, value in enumerate(matrix[0]):
        ax.text(col_idx, 0, int(value), ha="center", va="center", fontsize=12)
    fig.tight_layout()
    fig.savefig(DELIVERY_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_gate(gate: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(13, 7))
    matrix = gate[["pass_now"]].to_numpy(dtype=float)
    ax.imshow(matrix, aspect="auto", cmap=plt.get_cmap("RdYlGn"), vmin=0, vmax=1)
    ax.set_yticks(np.arange(len(gate)))
    ax.set_yticklabels(gate["gate_id"].tolist())
    ax.set_xticks([0])
    ax.set_xticklabels(["pass_now"])
    ax.set_title("Stage162 Gate Status Matrix")
    for row_idx, row in gate.iterrows():
        ax.text(0, row_idx, f"{int(row['observed'])}/{int(row['required'])}", ha="center", va="center", color="black", fontsize=9)
    fig.tight_layout()
    fig.savefig(GATE_CHART_OUT, dpi=170)
    plt.close(fig)


def main() -> None:
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    curve = _load_curve()
    metrics = _baseline_metrics(curve)
    manifest = _read_csv(STAGE152_REQUEST_TEMPLATE_IN)
    if manifest.empty:
        raise RuntimeError(f"missing Stage152 request manifest: {STAGE152_REQUEST_TEMPLATE_IN}")
    selected = _select_request(manifest)
    selected_frame = pd.DataFrame([selected.drop(labels=[label for label in ["request_date_dt", "priority_score_num"] if label in selected.index]).to_dict()])
    credential = _credentials()
    fetch_status, raw = _extract_tqsdk_minutes(selected, credential)
    normalized = _normalized_bars(selected, raw)
    delivery, delivery_row = _write_delivery(selected, raw, normalized, fetch_status)

    tqsdk_fetch_succeeded = int(fetch_status["fetch_status"] in {"extracted", "timeout"} and len(normalized) >= MIN_NORMALIZED_ROWS)
    decision = (
        "stage162_tqsdk_single_request_delivery_written_run_stage160_153_no_rule"
        if int(delivery_row["expected_files_written"]) == 3
        else "stage162_tqsdk_single_request_delivery_not_ready_no_rule"
    )
    summary: dict[str, Any] = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "created_at": created_at,
        "line_id": LINE_ID,
        "decision": decision,
        "next_best_action": "rerun_stage160_then_stage153" if int(delivery_row["expected_files_written"]) == 3 else "repair_tqsdk_source_or_wait_authorized_stage152_package",
        "request_id": str(selected["request_id"]),
        "selected_request_count": 1,
        "selection_policy": "latest_request_date_then_priority_score_not_pnl",
        "vt_symbol": str(selected["vt_symbol"]),
        "exchange": str(selected["exchange"]),
        "request_start_ts": str(selected["request_start_ts"]),
        "request_end_ts": str(selected["request_end_ts"]),
        "credential_present": int(fetch_status["credential_present"]),
        "tqsdk_import_ok": int(fetch_status["tqsdk_import_ok"]),
        "fetch_status": str(fetch_status["fetch_status"]),
        "tqsdk_fetch_succeeded": tqsdk_fetch_succeeded,
        "raw_row_count": int(fetch_status["raw_row_count"]),
        "normalized_row_count": int(len(normalized)),
        "positive_volume_row_count": int(fetch_status["positive_volume_row_count"]),
        "write_incoming_enabled": int(WRITE_INCOMING),
        "expected_files_written": int(delivery_row["expected_files_written"]),
        "raw_written": int(delivery_row["raw_written"]),
        "normalized_written": int(delivery_row["normalized_written"]),
        "proof_written": int(delivery_row["proof_written"]),
        "stage153_full_package_ready": 0,
        "official_config_changed": 0,
        "strategy_rule_created": 0,
        "true_engine_run": 0,
        "true_engine_run_count": 0,
        "ab_triggered": 0,
        "order_api_called": 0,
        "ctp_connected": 0,
        "side_effect_count": int(delivery_row["expected_files_written"] > 0),
        "current_package_promotion_allowed": 0,
        "true_engine_allowed": 0,
        "strategy_feature_usable": 0,
        "objective_completion_proven": 0,
        "visual_output_count": 5,
    }
    summary.update(metrics)
    gate = _gate_status(summary)

    _write_csv(pd.DataFrame([summary]), SUMMARY_OUT)
    _write_csv(selected_frame, SELECTED_REQUEST_OUT)
    _write_csv(pd.DataFrame([fetch_status]), FETCH_STATUS_OUT)
    _write_csv(raw.head(200), RAW_SAMPLE_OUT)
    _write_csv(normalized.head(200), NORMALIZED_SAMPLE_OUT)
    _write_csv(delivery, DELIVERY_AUDIT_OUT)
    _write_csv(gate, GATE_OUT)
    _write_json(
        DECISION_OUT,
        {
            "decision": decision,
            "summary": summary,
            "outputs": {
                "summary": SUMMARY_OUT,
                "selected_request": SELECTED_REQUEST_OUT,
                "fetch_status": FETCH_STATUS_OUT,
                "raw_sample": RAW_SAMPLE_OUT,
                "normalized_sample": NORMALIZED_SAMPLE_OUT,
                "delivery_audit": DELIVERY_AUDIT_OUT,
                "gate_status": GATE_OUT,
                "report": REPORT_OUT,
                "charts": [PATH_CHART_OUT, KLINE_CHART_OUT, VOLUME_CHART_OUT, DELIVERY_CHART_OUT, GATE_CHART_OUT],
            },
        },
    )
    _write_report(summary, selected_frame, pd.DataFrame([fetch_status]), delivery, gate)
    _plot_path(curve, summary)
    _plot_kline(normalized)
    _plot_volume(normalized)
    _plot_delivery(delivery)
    _plot_gate(gate)
    print(json.dumps(_json_safe(summary), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
