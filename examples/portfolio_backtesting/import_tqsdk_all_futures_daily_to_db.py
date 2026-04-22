from __future__ import annotations

from datetime import datetime
from pathlib import Path
import json
import time

import pandas as pd

from vnpy.trader.constant import Exchange, Interval
from vnpy.trader.database import get_database
from vnpy.trader.object import BarData
from vnpy.trader.utility import ZoneInfo, get_file_path


CHINA_TZ = ZoneInfo("Asia/Shanghai")
CSV_ROOT: Path = Path(__file__).resolve().parent / "downloaded_futures" / "tqsdk_daily_2010_2026_04"
DOWNLOAD_STATUS_PATH: Path = CSV_ROOT / "_download_status.csv"
IMPORT_STATUS_PATH: Path = CSV_ROOT / "_import_status.csv"
IMPORT_SUMMARY_PATH: Path = CSV_ROOT / "_import_summary.json"
DB_PATH: Path = get_file_path("database.db")


def load_download_status() -> pd.DataFrame:
    if not DOWNLOAD_STATUS_PATH.exists():
        raise FileNotFoundError(f"Download status file not found: {DOWNLOAD_STATUS_PATH}")
    df = pd.read_csv(DOWNLOAD_STATUS_PATH)
    return df[df["status"] == "downloaded"].copy()


def load_import_status() -> pd.DataFrame:
    if IMPORT_STATUS_PATH.exists():
        return pd.read_csv(IMPORT_STATUS_PATH)
    return pd.DataFrame(columns=["tq_symbol", "exchange", "symbol", "status", "rows", "file_path", "message", "updated_at"])


def save_import_status(df: pd.DataFrame) -> None:
    df.sort_values(["status", "exchange", "symbol"], inplace=True)
    df.to_csv(IMPORT_STATUS_PATH, index=False, encoding="utf-8-sig")


def upsert_import_status(
    status_df: pd.DataFrame,
    *,
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


def write_summary(status_df: pd.DataFrame, total_files: int, elapsed_seconds: float) -> None:
    summary = {
        "csv_root": str(CSV_ROOT),
        "database_path": str(DB_PATH),
        "total_files": total_files,
        "imported": int((status_df["status"] == "imported").sum()) if not status_df.empty else 0,
        "skipped": int((status_df["status"] == "skipped").sum()) if not status_df.empty else 0,
        "failed": int((status_df["status"] == "failed").sum()) if not status_df.empty else 0,
        "elapsed_seconds": round(elapsed_seconds, 2),
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }
    IMPORT_SUMMARY_PATH.write_text(json.dumps(summary, ensure_ascii=True, indent=2), encoding="utf-8")


def build_bars(file_path: Path, symbol: str, exchange: Exchange) -> list[BarData]:
    df = pd.read_csv(file_path)
    if df.empty:
        return []

    bars: list[BarData] = []
    for row in df.itertuples(index=False):
        dt = pd.Timestamp(row.datetime)
        if dt.tzinfo is None:
            dt = dt.tz_localize(CHINA_TZ)
        else:
            dt = dt.tz_convert(CHINA_TZ)

        bars.append(
            BarData(
                symbol=symbol,
                exchange=exchange,
                interval=Interval.DAILY,
                datetime=dt.to_pydatetime(),
                open_price=float(row.open),
                high_price=float(row.high),
                low_price=float(row.low),
                close_price=float(row.close),
                volume=float(row.volume),
                turnover=0.0,
                open_interest=float(getattr(row, "open_oi", 0.0) or 0.0),
                gateway_name="CSV_IMPORT",
            )
        )
    return bars


def main() -> None:
    started_at = time.time()
    download_df = load_download_status()
    import_df = load_import_status()
    database = get_database()

    total_files = len(download_df)
    print(f"CSV root: {CSV_ROOT}", flush=True)
    print(f"Database path: {DB_PATH}", flush=True)
    print(f"Files to import: {total_files}", flush=True)

    for index, row in enumerate(download_df.itertuples(index=False), start=1):
        tq_symbol = str(row.tq_symbol)
        exchange_value = str(row.exchange)
        symbol = str(row.symbol)
        file_path = Path(str(row.file_path))

        if not file_path.exists():
            import_df = upsert_import_status(
                import_df,
                tq_symbol=tq_symbol,
                exchange=exchange_value,
                symbol=symbol,
                status="failed",
                rows=0,
                file_path=str(file_path),
                message="csv file missing",
            )
            continue

        existing = import_df[import_df["tq_symbol"] == tq_symbol]
        if not existing.empty and str(existing.iloc[-1]["status"]) == "imported":
            if index == 1 or index % 100 == 0 or index == total_files:
                print(f"[{index}/{total_files}] skipped {tq_symbol} already imported", flush=True)
            continue

        try:
            bars = build_bars(file_path, symbol=symbol, exchange=Exchange(exchange_value))
            if not bars:
                import_df = upsert_import_status(
                    import_df,
                    tq_symbol=tq_symbol,
                    exchange=exchange_value,
                    symbol=symbol,
                    status="skipped",
                    rows=0,
                    file_path=str(file_path),
                    message="empty csv",
                )
            else:
                database.save_bar_data(bars)
                import_df = upsert_import_status(
                    import_df,
                    tq_symbol=tq_symbol,
                    exchange=exchange_value,
                    symbol=symbol,
                    status="imported",
                    rows=len(bars),
                    file_path=str(file_path),
                    message="",
                )
        except Exception as exc:
            import_df = upsert_import_status(
                import_df,
                tq_symbol=tq_symbol,
                exchange=exchange_value,
                symbol=symbol,
                status="failed",
                rows=0,
                file_path=str(file_path),
                message=repr(exc),
            )

        if index == 1 or index % 20 == 0 or index == total_files:
            save_import_status(import_df)
            write_summary(import_df, total_files, time.time() - started_at)
            latest = import_df[import_df["tq_symbol"] == tq_symbol].iloc[-1]
            print(
                f"[{index}/{total_files}] {latest['status']} {tq_symbol} rows={int(latest['rows'])}",
                flush=True,
            )

    save_import_status(import_df)
    write_summary(import_df, total_files, time.time() - started_at)


if __name__ == "__main__":
    main()
