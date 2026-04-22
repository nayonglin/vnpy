from __future__ import annotations

from datetime import datetime
from pathlib import Path
import json
import time

import pandas as pd
from tqsdk import TqApi, TqAuth

from vnpy.trader.constant import Exchange
from vnpy.trader.setting import SETTINGS
from vnpy.trader.utility import ZoneInfo


START_DT: datetime = datetime(2010, 1, 1)
END_DT: datetime = datetime(2026, 4, 30, 23, 59, 59)
CHINA_TZ = ZoneInfo("Asia/Shanghai")
OUTPUT_ROOT: Path = Path(__file__).resolve().parent / "downloaded_futures" / "tqsdk_daily_2010_2026_04"
STATUS_PATH: Path = OUTPUT_ROOT / "_download_status.csv"
SUMMARY_PATH: Path = OUTPUT_ROOT / "_download_summary.json"
SYMBOLS_PATH: Path = OUTPUT_ROOT / "_symbols.csv"

FUTURES_EXCHANGES: set[str] = {
    Exchange.CFFEX.value,
    Exchange.SHFE.value,
    Exchange.CZCE.value,
    Exchange.DCE.value,
    Exchange.INE.value,
    Exchange.GFEX.value,
}


def require_credentials() -> tuple[str, str]:
    username: str = SETTINGS["datafeed.username"]
    password: str = SETTINGS["datafeed.password"]
    if not username or not password:
        raise RuntimeError("TqSdk credentials are missing. Please configure `datafeed.username` and `datafeed.password`.")
    return username, password


def split_tq_symbol(tq_symbol: str) -> tuple[str, str]:
    exchange, symbol = tq_symbol.split(".", 1)
    return exchange, symbol


def estimate_data_length(start: datetime, end: datetime) -> int:
    span_days = max((end - start).days, 1)
    estimated = span_days + 600
    return min(max(estimated, 3000), 10000)


def list_all_futures_symbols(api: TqApi) -> list[str]:
    symbols = list(api.query_quotes(ins_class="FUTURE", expired=True))
    filtered = [s for s in symbols if "." in s and s.split(".", 1)[0] in FUTURES_EXCHANGES]
    filtered = sorted(set(filtered))
    return filtered


def fetch_daily_bars(api: TqApi, tq_symbol: str, data_length: int) -> pd.DataFrame:
    df = api.get_kline_serial(tq_symbol, duration_seconds=60 * 60 * 24, data_length=data_length)
    if df is None or df.empty:
        return pd.DataFrame()

    result = df.copy()
    result["datetime"] = pd.to_datetime(result["datetime"], unit="ns", utc=True).dt.tz_convert(CHINA_TZ)
    start_ts = pd.Timestamp(START_DT, tz=CHINA_TZ)
    end_ts = pd.Timestamp(END_DT, tz=CHINA_TZ)
    result = result[(result["datetime"] >= start_ts) & (result["datetime"] <= end_ts)]
    if result.empty:
        return result

    result["trade_date"] = result["datetime"].dt.strftime("%Y-%m-%d")
    columns = [
        "trade_date",
        "datetime",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "open_oi",
        "close_oi",
    ]
    existing_columns = [column for column in columns if column in result.columns]
    return result[existing_columns].copy()


def load_status() -> pd.DataFrame:
    if STATUS_PATH.exists():
        return pd.read_csv(STATUS_PATH)
    return pd.DataFrame(columns=["tq_symbol", "exchange", "symbol", "status", "rows", "file_path", "message", "updated_at"])


def save_status(df: pd.DataFrame) -> None:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    df.sort_values(["status", "exchange", "symbol"], inplace=True)
    df.to_csv(STATUS_PATH, index=False, encoding="utf-8-sig")


def upsert_status(
    status_df: pd.DataFrame,
    tq_symbol: str,
    exchange: str,
    symbol: str,
    status: str,
    rows: int,
    file_path: str,
    message: str,
) -> pd.DataFrame:
    record = {
        "tq_symbol": tq_symbol,
        "exchange": exchange,
        "symbol": symbol,
        "status": status,
        "rows": rows,
        "file_path": file_path,
        "message": message,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }
    if status_df.empty:
        return pd.DataFrame([record])

    mask = status_df["tq_symbol"] == tq_symbol
    if mask.any():
        for key, value in record.items():
            status_df.loc[mask, key] = value
        return status_df

    return pd.concat([status_df, pd.DataFrame([record])], ignore_index=True)


def write_summary(status_df: pd.DataFrame, total_symbols: int, elapsed_seconds: float) -> None:
    summary = {
        "root": str(OUTPUT_ROOT),
        "start": START_DT.isoformat(),
        "end": END_DT.isoformat(),
        "total_symbols": total_symbols,
        "downloaded": int((status_df["status"] == "downloaded").sum()) if not status_df.empty else 0,
        "skipped": int((status_df["status"] == "skipped").sum()) if not status_df.empty else 0,
        "empty": int((status_df["status"] == "empty").sum()) if not status_df.empty else 0,
        "failed": int((status_df["status"] == "failed").sum()) if not status_df.empty else 0,
        "elapsed_seconds": round(elapsed_seconds, 2),
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }
    SUMMARY_PATH.write_text(json.dumps(summary, ensure_ascii=True, indent=2), encoding="utf-8")


def main() -> None:
    username, password = require_credentials()
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

    started_at = time.time()
    status_df = load_status()
    data_length = estimate_data_length(START_DT, END_DT)

    api = TqApi(auth=TqAuth(username, password))
    try:
        symbols = list_all_futures_symbols(api)
        pd.DataFrame({"tq_symbol": symbols}).to_csv(SYMBOLS_PATH, index=False, encoding="utf-8-sig")
        total = len(symbols)
        print(f"Total futures symbols: {total}", flush=True)
        print(f"Output root: {OUTPUT_ROOT}", flush=True)

        for index, tq_symbol in enumerate(symbols, start=1):
            exchange, symbol = split_tq_symbol(tq_symbol)
            exchange_dir = OUTPUT_ROOT / exchange
            exchange_dir.mkdir(parents=True, exist_ok=True)
            file_path = exchange_dir / f"{symbol}.csv"

            if file_path.exists() and file_path.stat().st_size > 0:
                rows = 0
                try:
                    existing_df = pd.read_csv(file_path, usecols=["trade_date"])
                    rows = len(existing_df)
                except Exception:
                    rows = 0

                status_df = upsert_status(
                    status_df,
                    tq_symbol,
                    exchange,
                    symbol,
                    "skipped",
                    rows,
                    str(file_path),
                    "existing file",
                )
                if index == 1 or index % 50 == 0 or index == total:
                    print(f"[{index}/{total}] skipped {tq_symbol} rows={rows}", flush=True)
                continue

            try:
                bars_df = fetch_daily_bars(api, tq_symbol, data_length)
                if bars_df.empty:
                    status_df = upsert_status(
                        status_df,
                        tq_symbol,
                        exchange,
                        symbol,
                        "empty",
                        0,
                        str(file_path),
                        "no bars in requested range",
                    )
                else:
                    bars_df.to_csv(file_path, index=False, encoding="utf-8-sig")
                    status_df = upsert_status(
                        status_df,
                        tq_symbol,
                        exchange,
                        symbol,
                        "downloaded",
                        len(bars_df),
                        str(file_path),
                        "",
                    )
            except Exception as exc:
                status_df = upsert_status(
                    status_df,
                    tq_symbol,
                    exchange,
                    symbol,
                    "failed",
                    0,
                    str(file_path),
                    repr(exc),
                )

            if index == 1 or index % 20 == 0 or index == total:
                save_status(status_df)
                write_summary(status_df, total, time.time() - started_at)
                latest = status_df[status_df["tq_symbol"] == tq_symbol].iloc[-1]
                print(
                    f"[{index}/{total}] {latest['status']} {tq_symbol} rows={int(latest['rows'])} file={file_path.name}",
                    flush=True,
                )
    finally:
        api.close()
        save_status(status_df)
        total_symbols = len(status_df["tq_symbol"].unique()) if not status_df.empty else 0
        write_summary(status_df, total_symbols, time.time() - started_at)


if __name__ == "__main__":
    main()
