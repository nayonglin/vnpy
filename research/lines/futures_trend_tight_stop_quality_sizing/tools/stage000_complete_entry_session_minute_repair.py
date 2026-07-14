from __future__ import annotations

from datetime import datetime, timedelta
import hashlib
import json
import logging
from pathlib import Path
import sqlite3
import sys
import time
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
LINE_DIR = ROOT / "research" / "lines" / "futures_trend_tight_stop_quality_sizing"
PORTFOLIO_DIR = ROOT / "examples" / "portfolio_backtesting"
DATA_ROOT = PORTFOLIO_DIR / "downloaded_futures"
OUT = LINE_DIR / "outputs" / "stage000_complete_entry_session_minute_repair"
RAW_ROOT = OUT / "raw"

MODEL_TAG = "stage000_complete_entry_session_minute_repair_v1"
PREFIX = "tight_stop_quality_stage000"
TRADES_PATH = OUT / "source_stage003_pre_repair_ab_trades.csv.gz"
DATABASE_PATH = ROOT / ".vntrader" / "database.db"
PATCH_PATH = OUT / f"{PREFIX}_entry_session_minute_patch_{MODEL_TAG}.csv"
AUDIT_PATH = OUT / f"{PREFIX}_entry_session_coverage_audit_{MODEL_TAG}.csv"
DOWNLOAD_STATUS_PATH = OUT / f"{PREFIX}_download_status_{MODEL_TAG}.csv"
DECISION_PATH = OUT / f"{PREFIX}_decision_{MODEL_TAG}.json"
INPUT_MANIFEST_PATH = OUT / f"{PREFIX}_input_manifest_{MODEL_TAG}.csv"
RUNTIME_GAPS_PATH = OUT / f"{PREFIX}_runtime_discovered_gaps_{MODEL_TAG}.csv"

MIN_SESSION_BARS = 100
ALLOWED_SESSION_BAR_COUNTS = {225, 345, 465, 555}
SOURCE_ROOT_NAMES = (
    "tqsdk_stage448_minute_session_rebuild_batch",
    "tqsdk_stage459_completed_preclose_full_bar_shard",
    "tqsdk_stage462_completed_preclose_full_dates_shard",
    "tqsdk_stage491_covered_key_full_session_backfill",
    "tqsdk_stage498_actual_trade_fill_key_backfill",
    "tqsdk_stage504_next_real_open_fallback_backfill",
    "tqsdk_stage506_next_real_forward_risk_signal_frontier",
    "tqsdk_stage859_stage856_remaining_gap_backfill",
    "tqsdk_stage900_stage898_c9_gap_backfill",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _required_pairs() -> list[tuple[str, pd.Timestamp]]:
    if not TRADES_PATH.exists():
        raise RuntimeError(f"missing prior A/C trade evidence: {TRADES_PATH}")
    trades = pd.read_csv(TRADES_PATH, usecols=["offset", "vt_symbol", "date"])
    opened = trades[trades["offset"].astype(str).str.lower().eq("open")].copy()
    opened["trade_date"] = pd.to_datetime(opened["date"], errors="coerce").dt.tz_localize(None).dt.normalize()
    opened = opened.dropna(subset=["trade_date"])
    pair_set = set(zip(opened["vt_symbol"].astype(str), opened["trade_date"]))
    if RUNTIME_GAPS_PATH.exists():
        runtime = pd.read_csv(RUNTIME_GAPS_PATH)
        runtime["trade_date"] = pd.to_datetime(runtime["trade_date"], errors="coerce").dt.normalize()
        runtime = runtime.dropna(subset=["vt_symbol", "trade_date"])
        pair_set.update(zip(runtime["vt_symbol"].astype(str), runtime["trade_date"]))
    pairs = sorted(
        pair_set,
        key=lambda item: (item[1], item[0]),
    )
    if not pairs:
        raise RuntimeError("no opened trade pairs found")
    return pairs


def _symbol_token(path: Path) -> str:
    return path.name.split("_", 1)[0].lower()


def _source_priority(path: Path) -> int:
    text = str(path)
    if str(RAW_ROOT) in text:
        return 100
    for rank, name in enumerate(reversed(SOURCE_ROOT_NAMES), start=1):
        if name in text:
            return 10 + rank
    return 1


def _candidate_index(symbols: set[str]) -> dict[str, list[Path]]:
    by_token = {symbol.split(".", 1)[0].lower(): symbol for symbol in symbols}
    result: dict[str, list[Path]] = {symbol: [] for symbol in symbols}
    roots = [DATA_ROOT / name for name in SOURCE_ROOT_NAMES] + [RAW_ROOT]
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("*.csv"):
            symbol = by_token.get(_symbol_token(path))
            if symbol is not None:
                result[symbol].append(path)
    return result


def _datetime_column(columns: list[str]) -> str | None:
    return next(
        (column for column in ("bar_datetime", "datetime", "time", "date", "trade_time") if column in columns),
        None,
    )


def _read_window(path: Path, vt_symbol: str, trade_date: pd.Timestamp) -> pd.DataFrame:
    try:
        header = pd.read_csv(path, nrows=0, encoding="utf-8-sig")
    except Exception:
        return pd.DataFrame()
    datetime_column = _datetime_column(list(header.columns))
    required = {"open", "high", "low", "close"}
    if datetime_column is None or not required.issubset(header.columns):
        return pd.DataFrame()
    usecols = [datetime_column, "open", "high", "low", "close"]
    if "volume" in header.columns:
        usecols.append("volume")
    if "vt_symbol" in header.columns:
        usecols.append("vt_symbol")
    try:
        data = pd.read_csv(path, usecols=usecols, encoding="utf-8-sig")
    except Exception:
        return pd.DataFrame()
    if "vt_symbol" in data.columns:
        data = data[data["vt_symbol"].astype(str).eq(vt_symbol)].copy()
    if data.empty:
        return pd.DataFrame()
    data["bar_datetime"] = pd.to_datetime(data[datetime_column], errors="coerce").dt.tz_localize(None)
    data = data.dropna(subset=["bar_datetime"])
    data = data[
        data["bar_datetime"].between(
            trade_date - pd.Timedelta(days=7),
            trade_date + pd.Timedelta(hours=16),
            inclusive="left",
        )
    ].copy()
    if data.empty:
        return pd.DataFrame()
    for column in ("open", "high", "low", "close", "volume"):
        if column not in data.columns:
            data[column] = 0.0
        data[column] = pd.to_numeric(data[column], errors="coerce")
    data = data.dropna(subset=["open", "high", "low", "close"])
    data["minute_source"] = str(path)
    data["source_priority"] = _source_priority(path)
    data["true_ohlc"] = (
        ~np.isclose(data["high"], data["low"], rtol=0.0, atol=1e-12)
        | ~np.isclose(data["open"], data["close"], rtol=0.0, atol=1e-12)
    ).astype(int)
    return data[
        [
            "bar_datetime",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "minute_source",
            "source_priority",
            "true_ohlc",
        ]
    ]


def _daily_bar(connection: sqlite3.Connection, vt_symbol: str, trade_date: pd.Timestamp) -> tuple[float, ...] | None:
    symbol, exchange = vt_symbol.split(".", 1)
    row = connection.execute(
        """
        SELECT open_price, high_price, low_price, close_price
        FROM dbbardata
        WHERE symbol = ? AND exchange = ? AND interval = 'd' AND date(datetime) = ?
        """,
        (symbol, exchange, trade_date.date().isoformat()),
    ).fetchone()
    return tuple(float(value) for value in row) if row is not None else None


def _previous_trade_date(
    connection: sqlite3.Connection,
    vt_symbol: str,
    trade_date: pd.Timestamp,
) -> pd.Timestamp | None:
    symbol, exchange = vt_symbol.split(".", 1)
    row = connection.execute(
        """
        SELECT MAX(date(datetime))
        FROM dbbardata
        WHERE symbol = ? AND exchange = ? AND interval = 'd' AND date(datetime) < ?
        """,
        (symbol, exchange, trade_date.date().isoformat()),
    ).fetchone()
    if row is None or row[0] is None:
        return None
    return pd.Timestamp(row[0]).normalize()


def _candidate_sessions(
    data: pd.DataFrame,
    trade_date: pd.Timestamp,
    previous_trade_date: pd.Timestamp | None,
) -> list[pd.DataFrame]:
    if data.empty:
        return []
    data = data.sort_values(["bar_datetime", "true_ohlc", "source_priority"])
    data = data.drop_duplicates("bar_datetime", keep="last")
    day = data[
        (data["bar_datetime"] >= trade_date + pd.Timedelta(hours=8))
        & (data["bar_datetime"] < trade_date + pd.Timedelta(hours=16))
    ].copy()
    sessions = [day]
    if previous_trade_date is not None:
        evening_start = pd.Timestamp(previous_trade_date).normalize() + pd.Timedelta(hours=20)
        evening_end = pd.Timestamp(previous_trade_date).normalize() + pd.Timedelta(days=1, hours=8)
        overnight = data[
            (data["bar_datetime"] >= evening_start)
            & (data["bar_datetime"] < evening_end)
        ]
        if not overnight.empty:
            sessions.append(pd.concat([overnight, day], ignore_index=True).sort_values("bar_datetime"))
    unique_sessions: dict[tuple[pd.Timestamp, ...], pd.DataFrame] = {}
    for session in sessions:
        if session.empty:
            continue
        session = session.drop_duplicates("bar_datetime", keep="last")
        key = tuple(pd.to_datetime(session["bar_datetime"]).tolist())
        unique_sessions[key] = session
    return list(unique_sessions.values())


def _ohlc(session: pd.DataFrame) -> tuple[float, float, float, float]:
    return (
        float(session["open"].iloc[0]),
        float(session["high"].max()),
        float(session["low"].min()),
        float(session["close"].iloc[-1]),
    )


def _select_exact_session(
    frames: list[pd.DataFrame],
    daily: tuple[float, ...] | None,
    trade_date: pd.Timestamp,
    previous_trade_date: pd.Timestamp | None,
) -> pd.DataFrame:
    if daily is None or not frames:
        return pd.DataFrame()
    exact: list[pd.DataFrame] = []
    for source_frame in frames:
        for session in _candidate_sessions(source_frame, trade_date, previous_trade_date):
            geometry_ok = bool(
                (session["high"] >= session[["open", "close"]].max(axis=1)).all()
                and (session["low"] <= session[["open", "close"]].min(axis=1)).all()
                and (session["high"] >= session["low"]).all()
            )
            if (
                len(session) in ALLOWED_SESSION_BAR_COUNTS
                and not session["bar_datetime"].duplicated().any()
                and geometry_ok
                and float(pd.to_numeric(session["volume"], errors="coerce").fillna(0.0).sum()) > 0.0
                and np.allclose(_ohlc(session), daily, rtol=0.0, atol=1e-8)
            ):
                exact.append(session)
    if not exact:
        return pd.DataFrame()
    return max(
        exact,
        key=lambda item: (
            int(item["source_priority"].max()),
            int(item["true_ohlc"].sum()),
            len(item),
        ),
    ).copy()


def _raw_path(vt_symbol: str, trade_date: pd.Timestamp) -> Path:
    symbol, exchange = vt_symbol.split(".", 1)
    return RAW_ROOT / exchange / f"{symbol}_{trade_date.strftime('%Y%m%d')}_full_session.csv"


def _tq_symbol(vt_symbol: str) -> str:
    symbol, exchange = vt_symbol.split(".", 1)
    return f"{exchange}.{symbol}"


def _normalize_tq_datetime(value: Any) -> pd.Timestamp:
    from vnpy.trader.utility import ZoneInfo

    timestamp = pd.to_datetime(value, unit="ns", errors="coerce", utc=True)
    if pd.isna(timestamp):
        return pd.NaT
    return timestamp.tz_convert(ZoneInfo("Asia/Shanghai")).tz_localize(None)


def _download_full_window(vt_symbol: str, trade_date: pd.Timestamp) -> dict[str, Any]:
    from tqsdk import BacktestFinished, TqApi, TqAuth, TqBacktest, TqSim
    from vnpy.trader.setting import SETTINGS

    path = _raw_path(vt_symbol, trade_date)
    path.parent.mkdir(parents=True, exist_ok=True)
    username = str(SETTINGS.get("datafeed.username", ""))
    password = str(SETTINGS.get("datafeed.password", ""))
    if not username or not password:
        raise RuntimeError("TqSdk credentials missing")
    logging.getLogger().setLevel(logging.WARNING)
    logging.getLogger("tqsdk").setLevel(logging.WARNING)
    start = (trade_date - pd.Timedelta(days=7)) + pd.Timedelta(hours=16)
    end = trade_date + pd.Timedelta(hours=16, minutes=10)
    started = time.time()
    rows: list[dict[str, Any]] = []
    seen: set[int] = set()
    api = None
    bars = None

    def append_bar(item: dict[str, Any]) -> None:
        bar_id = int(item.get("id", -1))
        if bar_id in seen:
            return
        seen.add(bar_id)
        bar_datetime = _normalize_tq_datetime(item.get("datetime"))
        if pd.isna(bar_datetime):
            return
        rows.append(
            {
                "vt_symbol": vt_symbol,
                "bar_datetime": bar_datetime,
                "open": float(item.get("open", np.nan)),
                "high": float(item.get("high", np.nan)),
                "low": float(item.get("low", np.nan)),
                "close": float(item.get("close", np.nan)),
                "volume": float(item.get("volume", 0.0)),
            }
        )

    try:
        api = TqApi(
            TqSim(),
            backtest=TqBacktest(start_dt=start.to_pydatetime(), end_dt=end.to_pydatetime()),
            auth=TqAuth(username, password),
            disable_print=True,
        )
        bars = api.get_kline_serial(_tq_symbol(vt_symbol), duration_seconds=60, data_length=3000)
        while True:
            if time.time() - started > 120:
                raise RuntimeError(f"TqSdk timeout: {vt_symbol} {trade_date.date()}")
            api.wait_update()
            if not api.is_changing(bars.iloc[-1], "datetime"):
                continue
            if len(bars) < 2:
                continue
            # TqBacktest's last row is the currently forming minute. Persist the
            # previous row so OHLC and volume are final rather than close-only.
            append_bar(bars.iloc[-2].to_dict())
    except BacktestFinished:
        if bars is not None and not bars.empty:
            append_bar(bars.iloc[-1].to_dict())
    finally:
        if api is not None:
            api.close()
    frame = pd.DataFrame(rows).drop_duplicates(["vt_symbol", "bar_datetime"])
    if frame.empty:
        raise RuntimeError(f"TqSdk returned no bars: {vt_symbol} {trade_date.date()}")
    frame.to_csv(path, index=False, encoding="utf-8-sig")
    return {
        "vt_symbol": vt_symbol,
        "trade_date": trade_date.date().isoformat(),
        "path": str(path),
        "rows": int(len(frame)),
        "elapsed_seconds": round(time.time() - started, 2),
        "status": "downloaded",
    }


def _audit_and_sessions(
    pairs: list[tuple[str, pd.Timestamp]],
    index: dict[str, list[Path]],
) -> tuple[pd.DataFrame, dict[tuple[str, pd.Timestamp], pd.DataFrame], set[Path]]:
    connection = sqlite3.connect(DATABASE_PATH)
    rows: list[dict[str, Any]] = []
    sessions: dict[tuple[str, pd.Timestamp], pd.DataFrame] = {}
    used_paths: set[Path] = set()
    try:
        for vt_symbol, trade_date in pairs:
            paths = index.get(vt_symbol, [])
            frames = []
            for path in paths:
                frame = _read_window(path, vt_symbol, trade_date)
                if not frame.empty:
                    frames.append(frame)
            daily = _daily_bar(connection, vt_symbol, trade_date)
            previous_trade_date = _previous_trade_date(connection, vt_symbol, trade_date)
            session = _select_exact_session(frames, daily, trade_date, previous_trade_date)
            if not session.empty:
                session["vt_symbol"] = vt_symbol
                session["bar_date"] = trade_date
                sessions[(vt_symbol, trade_date)] = session
                used_paths.update(Path(path) for path in session["minute_source"].astype(str).unique())
            rows.append(
                {
                    "vt_symbol": vt_symbol,
                    "trade_date": trade_date.date().isoformat(),
                    "source_file_count": int(len(paths)),
                    "session_bars": int(len(session)),
                    "true_ohlc_bars": int(session["true_ohlc"].sum()) if not session.empty else 0,
                    "daily_ohlc_exact": int(not session.empty),
                    "session_start": session["bar_datetime"].min() if not session.empty else pd.NaT,
                    "session_end": session["bar_datetime"].max() if not session.empty else pd.NaT,
                    "daily_open": daily[0] if daily else np.nan,
                    "daily_high": daily[1] if daily else np.nan,
                    "daily_low": daily[2] if daily else np.nan,
                    "daily_close": daily[3] if daily else np.nan,
                    "previous_trade_date": previous_trade_date.date().isoformat() if previous_trade_date is not None else "",
                }
            )
    finally:
        connection.close()
    return pd.DataFrame(rows), sessions, used_paths


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    pairs = _required_pairs()
    index = _candidate_index({symbol for symbol, _ in pairs})
    initial_audit, _, _ = _audit_and_sessions(pairs, index)
    missing = initial_audit[initial_audit["daily_ohlc_exact"].eq(0)]
    statuses = []
    for row in missing.itertuples(index=False):
        print(f"[stage000] download {row.vt_symbol} {row.trade_date}", flush=True)
        statuses.append(_download_full_window(str(row.vt_symbol), pd.Timestamp(row.trade_date)))
    pd.DataFrame(statuses).to_csv(DOWNLOAD_STATUS_PATH, index=False)

    final_index = _candidate_index({symbol for symbol, _ in pairs})
    audit, sessions, used_paths = _audit_and_sessions(pairs, final_index)
    failures = audit[audit["daily_ohlc_exact"].eq(0)]
    audit.to_csv(AUDIT_PATH, index=False)
    if not failures.empty:
        raise RuntimeError(
            "entry-session minute repair still incomplete: "
            + failures[["vt_symbol", "trade_date"]].to_dict("records").__repr__()
        )
    patch = pd.concat(sessions.values(), ignore_index=True, sort=False)
    patch = patch.sort_values(["vt_symbol", "bar_date", "bar_datetime"])
    duplicate_count = int(patch.duplicated(["vt_symbol", "bar_date", "bar_datetime"]).sum())
    if duplicate_count:
        raise RuntimeError(f"duplicate repaired minute keys: {duplicate_count}")
    patch[
        [
            "vt_symbol",
            "bar_datetime",
            "bar_date",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "minute_source",
        ]
    ].to_csv(PATCH_PATH, index=False, encoding="utf-8-sig")
    decision = {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "required_symbol_dates": int(len(pairs)),
        "downloaded_symbol_dates": int(len(statuses)),
        "covered_symbol_dates": int(audit["daily_ohlc_exact"].sum()),
        "patch_rows": int(len(patch)),
        "duplicate_count": duplicate_count,
        "patch_sha256": _sha256(PATCH_PATH),
        "audit_sha256": _sha256(AUDIT_PATH),
        "decision": "complete_entry_session_minute_patch_ready",
    }
    DECISION_PATH.write_text(json.dumps(decision, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    manifest_paths = [TRADES_PATH, DATABASE_PATH, *sorted(used_paths)]
    pd.DataFrame(
        [
            {"path": str(path), "bytes": path.stat().st_size, "sha256": _sha256(path)}
            for path in manifest_paths
        ]
    ).to_csv(INPUT_MANIFEST_PATH, index=False)
    print(json.dumps(decision, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
