from __future__ import annotations

import json
import os
import time
from calendar import monthrange
from datetime import datetime
from pathlib import Path
from typing import Any

import tushare as ts

from vnpy.alpha import AlphaLab
from vnpy.trader.constant import Exchange, Interval
from vnpy.trader.object import BarData


ROOT_PATH: Path = Path(__file__).resolve().parents[2]

TASK_NAME: str = os.getenv("TASK_NAME", "csi1000")
LAB_PATH: Path = Path(os.getenv("LAB_PATH", str(ROOT_PATH / "lab" / TASK_NAME)))

INDEX_SYMBOL: str = os.getenv("INDEX_SYMBOL", "000852.SSE")
TUSHARE_INDEX_CODE: str = os.getenv("TUSHARE_INDEX_CODE", "000852.SH")

START_DATE: str = os.getenv("START_DATE", "20150101")
END_DATE: str = os.getenv("END_DATE", datetime.now().strftime("%Y%m%d"))

COMPONENT_SOURCE: str = os.getenv("COMPONENT_SOURCE", "tushare").strip().lower()
BAR_SOURCE: str = os.getenv("BAR_SOURCE", "tushare").strip().lower()

MANUAL_SYMBOLS: str = os.getenv("MANUAL_SYMBOLS", "").strip()
SYMBOLS_FILE: str = os.getenv("SYMBOLS_FILE", "").strip()

MAX_SYMBOLS: int = int(os.getenv("MAX_SYMBOLS", "0") or 0)
SLEEP_SECONDS: float = float(os.getenv("SLEEP_SECONDS", "1.25") or 0.0)
DOWNLOAD_INDEX_BAR: bool = os.getenv("DOWNLOAD_INDEX_BAR", "0").strip() == "1"


def log(message: str) -> None:
    """Print logs in unbuffered mode for long-running downloads."""
    print(message, flush=True)


def parse_ymd(value: str) -> datetime:
    """Parse YYYYMMDD string into datetime."""
    return datetime.strptime(value, "%Y%m%d")


def format_shelve_date(value: str) -> str:
    """Convert YYYYMMDD into YYYY-MM-DD for AlphaLab shelve keys."""
    return parse_ymd(value).strftime("%Y-%m-%d")


def to_float(value: Any, scale: float = 1.0) -> float:
    """Convert nullable numeric values returned by Tushare."""
    if value is None:
        return 0.0

    try:
        if value != value:      # NaN check
            return 0.0
    except TypeError:
        pass

    return float(value) * scale


def split_ts_code(ts_code: str) -> tuple[str, Exchange]:
    """Map Tushare ts_code into vn.py symbol and exchange."""
    symbol, suffix = ts_code.split(".")
    suffix = suffix.upper()

    if suffix == "SH":
        return symbol, Exchange.SSE
    if suffix == "SZ":
        return symbol, Exchange.SZSE
    if suffix == "BJ":
        return symbol, Exchange.BSE

    raise ValueError(f"Unsupported Tushare suffix: {ts_code}")


def ts_code_to_vt_symbol(ts_code: str) -> str:
    """Convert Tushare ts_code into vn.py vt_symbol."""
    symbol, exchange = split_ts_code(ts_code)
    return f"{symbol}.{exchange.value}"


def month_windows(start_date: str, end_date: str) -> list[tuple[str, str]]:
    """Generate month-by-month windows for index constituent queries."""
    windows: list[tuple[str, str]] = []

    current: datetime = parse_ymd(start_date).replace(day=1)
    end_dt: datetime = parse_ymd(end_date)

    while current <= end_dt:
        month_end_day: int = monthrange(current.year, current.month)[1]
        window_start: str = current.strftime("%Y%m%d")
        window_end: str = current.replace(day=month_end_day).strftime("%Y%m%d")

        if window_end > end_date:
            window_end = end_date

        windows.append((window_start, window_end))

        if current.month == 12:
            current = current.replace(year=current.year + 1, month=1)
        else:
            current = current.replace(month=current.month + 1)

    return windows


def get_tushare_client() -> Any:
    """Create Tushare Pro client from env token."""
    token: str = os.getenv("TUSHARE_TOKEN", "").strip()
    if not token:
        raise RuntimeError("Missing TUSHARE_TOKEN environment variable")

    return ts.pro_api(token)


def load_symbols_from_file(file_path: str) -> list[str]:
    """Load symbol list from txt/json/csv file."""
    path: Path = Path(file_path).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"SYMBOLS_FILE does not exist: {path}")

    suffix: str = path.suffix.lower()

    if suffix == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return [str(item).strip() for item in data if str(item).strip()]
        raise ValueError("JSON symbols file must be a list of ts_code strings")

    if suffix == ".csv":
        import csv

        with path.open(encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames or "ts_code" not in reader.fieldnames:
                raise ValueError("CSV symbols file must contain a ts_code column")
            return [row["ts_code"].strip() for row in reader if row.get("ts_code", "").strip()]

    symbols: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        symbol: str = line.strip()
        if symbol and not symbol.startswith("#"):
            symbols.append(symbol)
    return symbols


def load_manual_ts_codes() -> list[str]:
    """Load static symbols for low-permission tokens or quick validation."""
    symbols: list[str] = []

    if MANUAL_SYMBOLS:
        symbols.extend([item.strip() for item in MANUAL_SYMBOLS.split(",") if item.strip()])

    if SYMBOLS_FILE:
        symbols.extend(load_symbols_from_file(SYMBOLS_FILE))

    symbols = sorted(set(symbols))
    if not symbols:
        raise RuntimeError(
            "COMPONENT_SOURCE=manual requires MANUAL_SYMBOLS or SYMBOLS_FILE"
        )

    return symbols


def download_components_from_tushare(pro: Any, index_code: str, start_date: str, end_date: str) -> dict[str, list[str]]:
    """
    Download monthly constituent snapshots from Tushare index_weight.

    Note: this endpoint requires higher Tushare permissions. We keep the raw
    rebalance snapshots instead of expanding them into every trading day.
    """
    component_map: dict[str, set[str]] = {}

    for window_start, window_end in month_windows(start_date, end_date):
        log(f"[component] index_weight {window_start} -> {window_end}")
        try:
            df = pro.index_weight(
                index_code=index_code,
                start_date=window_start,
                end_date=window_end,
                fields="trade_date,con_code,weight",
            )
        except Exception as exc:
            raise RuntimeError(
                "Tushare index_weight query failed. Historical CSI 1000 "
                "constituents require index permissions; otherwise use "
                "COMPONENT_SOURCE=manual with MANUAL_SYMBOLS or SYMBOLS_FILE."
            ) from exc

        if df is None or df.empty:
            if SLEEP_SECONDS:
                time.sleep(SLEEP_SECONDS)
            continue

        for row in df.itertuples(index=False):
            trade_date: str = format_shelve_date(str(row.trade_date))
            vt_symbol: str = ts_code_to_vt_symbol(str(row.con_code))
            component_map.setdefault(trade_date, set()).add(vt_symbol)

        if SLEEP_SECONDS:
            time.sleep(SLEEP_SECONDS)

    if not component_map:
        raise RuntimeError(
            "No component snapshots were returned from Tushare index_weight. "
            "Check index code and token permissions."
        )

    return {
        trade_date: sorted(vt_symbols)
        for trade_date, vt_symbols in sorted(component_map.items())
    }


def build_manual_components(ts_codes: list[str], start_date: str, end_date: str) -> dict[str, list[str]]:
    """Create a static component mapping spanning the whole backtest window."""
    vt_symbols: list[str] = sorted(ts_code_to_vt_symbol(ts_code) for ts_code in ts_codes)
    return {
        format_shelve_date(start_date): vt_symbols,
        format_shelve_date(end_date): vt_symbols,
    }


def resolve_component_data(pro: Any) -> tuple[dict[str, list[str]], list[str]]:
    """Resolve constituent snapshots and the symbol universe to download."""
    if COMPONENT_SOURCE == "tushare":
        component_data = download_components_from_tushare(
            pro,
            TUSHARE_INDEX_CODE,
            START_DATE,
            END_DATE,
        )
        ts_codes: list[str] = sorted({
            f"{vt_symbol.split('.')[0]}.{'SH' if vt_symbol.endswith('.SSE') else 'SZ' if vt_symbol.endswith('.SZSE') else 'BJ'}"
            for vt_symbols in component_data.values()
            for vt_symbol in vt_symbols
        })
        return component_data, ts_codes

    if COMPONENT_SOURCE == "manual":
        ts_codes = load_manual_ts_codes()
        component_data = build_manual_components(ts_codes, START_DATE, END_DATE)
        return component_data, ts_codes

    raise ValueError(f"Unsupported COMPONENT_SOURCE: {COMPONENT_SOURCE}")


def download_stock_daily_bars(pro: Any, ts_code: str, start_date: str, end_date: str) -> list[BarData]:
    """Download one stock's daily bars and convert them into AlphaLab format."""
    df = pro.daily(
        ts_code=ts_code,
        start_date=start_date,
        end_date=end_date,
        fields="ts_code,trade_date,open,high,low,close,vol,amount",
    )
    if df is None or df.empty:
        return []

    df = df.sort_values("trade_date")
    symbol, exchange = split_ts_code(ts_code)

    bars: list[BarData] = []
    for row in df.itertuples(index=False):
        bars.append(
            BarData(
                symbol=symbol,
                exchange=exchange,
                datetime=parse_ymd(str(row.trade_date)),
                interval=Interval.DAILY,
                open_price=to_float(row.open),
                high_price=to_float(row.high),
                low_price=to_float(row.low),
                close_price=to_float(row.close),
                volume=to_float(row.vol, scale=100.0),         # vol unit: hand
                turnover=to_float(row.amount, scale=1000.0),   # amount unit: thousand yuan
                open_interest=0.0,
                gateway_name="TUSHARE",
            )
        )
    return bars


def download_index_daily_bars(pro: Any, ts_code: str, start_date: str, end_date: str) -> list[BarData]:
    """Download benchmark index bars when the token has index permissions."""
    df = pro.index_daily(
        ts_code=ts_code,
        start_date=start_date,
        end_date=end_date,
        fields="ts_code,trade_date,open,high,low,close,vol,amount",
    )
    if df is None or df.empty:
        return []

    df = df.sort_values("trade_date")
    symbol, exchange = split_ts_code(ts_code)

    bars: list[BarData] = []
    for row in df.itertuples(index=False):
        bars.append(
            BarData(
                symbol=symbol,
                exchange=exchange,
                datetime=parse_ymd(str(row.trade_date)),
                interval=Interval.DAILY,
                open_price=to_float(row.open),
                high_price=to_float(row.high),
                low_price=to_float(row.low),
                close_price=to_float(row.close),
                volume=to_float(row.vol, scale=100.0),
                turnover=to_float(row.amount, scale=1000.0),
                open_interest=0.0,
                gateway_name="TUSHARE",
            )
        )
    return bars


def download_daily_bars(lab: AlphaLab, pro: Any, ts_codes: list[str]) -> tuple[list[str], list[str]]:
    """Download and save daily bars for all symbols."""
    success: list[str] = []
    failed: list[str] = []

    if MAX_SYMBOLS:
        ts_codes = ts_codes[:MAX_SYMBOLS]
        log(f"[bar] MAX_SYMBOLS enabled: {len(ts_codes)}")

    for index, ts_code in enumerate(ts_codes, start=1):
        log(f"[bar] {index}/{len(ts_codes)} {ts_code}")
        try:
            bars = download_stock_daily_bars(pro, ts_code, START_DATE, END_DATE)
            if not bars:
                failed.append(ts_code)
            else:
                lab.save_bar_data(bars)
                success.append(ts_code)
        except Exception as exc:
            failed.append(ts_code)
            log(f"[bar] failed {ts_code}: {exc}")

        if SLEEP_SECONDS:
            time.sleep(SLEEP_SECONDS)

    return success, failed


def maybe_download_benchmark(lab: AlphaLab, pro: Any) -> None:
    """Try downloading CSI 1000 benchmark bars when index permissions exist."""
    if not DOWNLOAD_INDEX_BAR:
        return

    log(f"[index] downloading benchmark {TUSHARE_INDEX_CODE}")
    try:
        bars = download_index_daily_bars(pro, TUSHARE_INDEX_CODE, START_DATE, END_DATE)
    except Exception as exc:
        log(f"[index] skipped: {exc}")
        return

    if not bars:
        log("[index] skipped: no benchmark bars returned")
        return

    lab.save_bar_data(bars)
    log(f"[index] saved {len(bars)} benchmark bars")


def main() -> None:
    """Prepare AlphaLab data directory for CSI 1000 research."""
    if BAR_SOURCE != "tushare":
        raise ValueError(f"Unsupported BAR_SOURCE: {BAR_SOURCE}")

    log(f"task_name={TASK_NAME}")
    log(f"lab_path={LAB_PATH}")
    log(f"component_source={COMPONENT_SOURCE}")
    log(f"bar_source={BAR_SOURCE}")
    log(f"index_symbol={INDEX_SYMBOL}")
    log(f"tushare_index_code={TUSHARE_INDEX_CODE}")
    log(f"date_range={START_DATE}->{END_DATE}")

    pro = get_tushare_client()
    lab = AlphaLab(str(LAB_PATH))

    component_data, ts_codes = resolve_component_data(pro)
    lab.save_component_data(INDEX_SYMBOL, component_data)

    log(f"[component] snapshots={len(component_data)}")
    log(f"[component] unique_symbols={len(ts_codes)}")

    success, failed = download_daily_bars(lab, pro, ts_codes)
    maybe_download_benchmark(lab, pro)

    log(f"[summary] success={len(success)} failed={len(failed)}")
    if failed:
        failed_preview: str = ", ".join(failed[:20])
        log(f"[summary] failed_symbols_preview={failed_preview}")


if __name__ == "__main__":
    main()
