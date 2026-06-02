from __future__ import annotations

from datetime import datetime, timedelta
import json
import logging
import math
from pathlib import Path
import sys
import time
from typing import Any

import numpy as np
import pandas as pd
from tqsdk import BacktestFinished, TqApi, TqAuth, TqBacktest, TqSim
from vnpy.trader.setting import SETTINGS
from vnpy.trader.utility import ZoneInfo


logging.getLogger().setLevel(logging.WARNING)
logging.getLogger("tqsdk").setLevel(logging.WARNING)

PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
sys.path.insert(0, str(PROJECT_DIR.resolve()))

import analyze_qmt_roll_stage508_xsmom_true_carry_replay as s508  # noqa: E402


MODEL_TAG = "stage509_xsmom_true_carry_fallback_backfill_v1"
OUTPUT_PREFIX = "qmt_roll_stage509_xsmom_true_carry_fallback_backfill"
LINE_ID = "futures_trend_drawdown30_preserve_return"

RAW_ROOT = PROJECT_DIR / "downloaded_futures" / "tqsdk_stage509_xsmom_true_carry_fallback_backfill"
CHINA_TZ = ZoneInfo("Asia/Shanghai")
MAX_SECONDS_PER_SYMBOL = 240
WINDOW_PADDING_MINUTES = 10

ORDER_LEDGER_PATH = s508.ORDER_LEDGER_PATH
WINDOW_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_windows_{MODEL_TAG}.csv"
STATUS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_status_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        result = float(value)
        return None if math.isnan(result) or math.isinf(result) else result
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    return value


def _require_credentials() -> tuple[str, str]:
    username = str(SETTINGS.get("datafeed.username", ""))
    password = str(SETTINGS.get("datafeed.password", ""))
    if not username or not password:
        raise RuntimeError("TqSdk credentials are missing in vn.py SETTINGS.")
    return username, password


def _to_tqsdk_symbol(vt_symbol: str) -> str:
    symbol, exchange = str(vt_symbol).split(".", 1)
    return f"{exchange}.{symbol}"


def _raw_path(vt_symbol: str) -> Path:
    symbol, exchange = str(vt_symbol).split(".", 1)
    return RAW_ROOT / exchange / f"{symbol}_minute_backtest.csv"


def _normalize_tqsdk_datetime(value: Any) -> pd.Timestamp:
    ts = pd.to_datetime(value, unit="ns", errors="coerce", utc=True)
    if pd.isna(ts):
        return pd.NaT
    return ts.tz_convert(CHINA_TZ).tz_localize(None)


def _load_existing_stage509_raw(vt_symbol: str) -> pd.DataFrame:
    path = _raw_path(vt_symbol)
    if not path.exists():
        return pd.DataFrame()
    frame = pd.read_csv(path, encoding="utf-8-sig")
    if frame.empty:
        return frame
    frame["bar_datetime"] = pd.to_datetime(frame["bar_datetime"], errors="coerce").dt.tz_localize(None)
    frame["vt_symbol"] = vt_symbol
    return frame.dropna(subset=["bar_datetime"]).copy()


def _build_windows(order_ledger: pd.DataFrame) -> pd.DataFrame:
    fallback = order_ledger[order_ledger["price_source"].astype(str).str.startswith("fallback")].copy()
    if fallback.empty:
        return pd.DataFrame()
    fallback["date"] = pd.to_datetime(fallback["date"], errors="coerce").dt.normalize()
    fallback["signal_date"] = pd.to_datetime(fallback["signal_date"], errors="coerce").dt.normalize()
    rows: list[dict[str, Any]] = []
    for row in fallback.dropna(subset=["date", "signal_date", "contract"]).itertuples(index=False):
        contract = str(row.contract)
        fill_date = pd.Timestamp(row.date).normalize()
        signal_date = pd.Timestamp(row.signal_date).normalize()
        rows.append(
            {
                "contract": contract,
                "product": str(row.product),
                "signal_date": signal_date,
                "fill_date": fill_date,
                "window_type": "prev_signal_night_2100_2105",
                "target_start": signal_date + pd.Timedelta(hours=21),
                "target_end": signal_date + pd.Timedelta(hours=21, minutes=5),
            }
        )
        rows.append(
            {
                "contract": contract,
                "product": str(row.product),
                "signal_date": signal_date,
                "fill_date": fill_date,
                "window_type": "fill_day_0900_0905",
                "target_start": fill_date + pd.Timedelta(hours=9),
                "target_end": fill_date + pd.Timedelta(hours=9, minutes=5),
            }
        )
    if not rows:
        return pd.DataFrame()
    return (
        pd.DataFrame(rows)
        .drop_duplicates(["contract", "target_start", "target_end", "window_type"])
        .sort_values(["contract", "target_start", "window_type"])
        .reset_index(drop=True)
    )


def _windows_covered(vt_symbol: str, windows: pd.DataFrame) -> bool:
    s508._load_minute_bars.cache_clear()
    bars = s508._load_minute_bars(vt_symbol)
    if bars.empty:
        return False
    for row in windows.itertuples(index=False):
        start = pd.Timestamp(row.target_start)
        end = pd.Timestamp(row.target_end)
        if bars[(bars["bar_datetime"] >= start) & (bars["bar_datetime"] < end)].empty:
            return False
    return True


def _extract_symbol_windows(vt_symbol: str, windows: pd.DataFrame, username: str, password: str) -> dict[str, Any]:
    covered_before = _windows_covered(vt_symbol, windows)
    if covered_before:
        existing = s508._load_minute_bars(vt_symbol)
        return {
            "contract": vt_symbol,
            "tq_symbol": _to_tqsdk_symbol(vt_symbol),
            "status": "cached_raw",
            "target_windows": int(len(windows)),
            "covered_before": True,
            "covered_after_extract": True,
            "rows": int(len(existing)),
            "new_rows": 0,
            "elapsed_seconds": 0.0,
            "message": "",
        }

    tq_symbol = _to_tqsdk_symbol(vt_symbol)
    start_dt = pd.Timestamp(windows["target_start"].min()) - timedelta(minutes=WINDOW_PADDING_MINUTES)
    end_dt = pd.Timestamp(windows["target_end"].max()) + timedelta(minutes=WINDOW_PADDING_MINUTES)
    status = {
        "contract": vt_symbol,
        "tq_symbol": tq_symbol,
        "extract_start": start_dt,
        "extract_end": end_dt,
        "target_windows": int(len(windows)),
        "covered_before": False,
        "status": "unknown",
        "rows": 0,
        "new_rows": 0,
        "elapsed_seconds": 0.0,
        "message": "",
    }

    rows: list[dict[str, Any]] = []
    seen_ids: set[int] = set()
    started = time.time()
    api: TqApi | None = None
    try:
        api = TqApi(
            TqSim(),
            backtest=TqBacktest(start_dt=start_dt.to_pydatetime(), end_dt=end_dt.to_pydatetime()),
            auth=TqAuth(username, password),
        )
        klines = api.get_kline_serial(tq_symbol, duration_seconds=60, data_length=500)
        while True:
            if time.time() - started > MAX_SECONDS_PER_SYMBOL:
                status["status"] = "timeout"
                status["message"] = f"timeout_after_{MAX_SECONDS_PER_SYMBOL}s"
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
                    "vt_symbol": vt_symbol,
                    "tq_symbol": tq_symbol,
                    "bar_datetime": bar_dt,
                    "bar_id": bar_id,
                    "open": float(bar.get("open", np.nan)),
                    "high": float(bar.get("high", np.nan)),
                    "low": float(bar.get("low", np.nan)),
                    "close": float(bar.get("close", np.nan)),
                    "volume": float(bar.get("volume", np.nan)),
                    "open_oi": float(bar.get("open_oi", np.nan)),
                    "close_oi": float(bar.get("close_oi", np.nan)),
                }
            )
    except BacktestFinished:
        status["status"] = "extracted"
    except Exception as exc:
        status["status"] = "failed"
        status["message"] = repr(exc)
    finally:
        if api is not None:
            api.close()

    new_bars = pd.DataFrame(rows)
    old_bars = _load_existing_stage509_raw(vt_symbol)
    frames = [frame for frame in (old_bars, new_bars) if not frame.empty]
    merged = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    if not merged.empty:
        merged["bar_datetime"] = pd.to_datetime(merged["bar_datetime"], errors="coerce").dt.tz_localize(None)
        merged = merged.dropna(subset=["bar_datetime"]).drop_duplicates(["vt_symbol", "bar_datetime"], keep="last")
        merged = merged.sort_values(["vt_symbol", "bar_datetime"]).reset_index(drop=True)
        path = _raw_path(vt_symbol)
        path.parent.mkdir(parents=True, exist_ok=True)
        merged.to_csv(path, index=False, encoding="utf-8-sig")

    s508._load_minute_bars.cache_clear()
    if status["status"] == "unknown":
        status["status"] = "extracted" if len(new_bars) else "empty"
    status["rows"] = int(len(merged))
    status["new_rows"] = int(len(new_bars))
    status["elapsed_seconds"] = round(time.time() - started, 2)
    status["covered_after_extract"] = bool(_windows_covered(vt_symbol, windows))
    return status


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    order_ledger = pd.read_csv(ORDER_LEDGER_PATH, encoding="utf-8-sig")
    windows = _build_windows(order_ledger)
    windows.to_csv(WINDOW_PATH, index=False, encoding="utf-8-sig")
    if windows.empty:
        decision = {
            "stage": "Stage209",
            "model_tag": MODEL_TAG,
            "line_id": LINE_ID,
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "decision": "no_stage208_xsmom_fallback_to_backfill",
            "fallback_contracts": 0,
            "covered_after_extract_contracts": 0,
        }
        STATUS_PATH.write_text("", encoding="utf-8")
        DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
        return

    username, password = _require_credentials()
    statuses: list[dict[str, Any]] = []
    for contract, group in windows.groupby("contract", sort=True):
        statuses.append(_extract_symbol_windows(str(contract), group.copy(), username, password))
    status_frame = pd.DataFrame(statuses)
    status_frame.to_csv(STATUS_PATH, index=False, encoding="utf-8-sig")
    covered = int(status_frame["covered_after_extract"].fillna(False).sum()) if not status_frame.empty else 0
    failed = status_frame[~status_frame["covered_after_extract"].fillna(False)].copy() if not status_frame.empty else pd.DataFrame()
    decision = {
        "stage": "Stage209",
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "decision": "xsmom_backfill_complete" if failed.empty else "xsmom_backfill_partial",
        "fallback_contracts": int(windows["contract"].nunique()),
        "target_windows": int(len(windows)),
        "covered_after_extract_contracts": covered,
        "uncovered_contracts": failed["contract"].astype(str).tolist() if not failed.empty else [],
        "outputs": {
            "windows": str(WINDOW_PATH.resolve()),
            "status": str(STATUS_PATH.resolve()),
            "raw_root": str(RAW_ROOT.resolve()),
        },
        "next_step": "重跑 Stage208，检查 xsmom fallback 是否清零。",
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
