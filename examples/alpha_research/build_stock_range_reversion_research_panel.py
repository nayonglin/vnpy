from __future__ import annotations

import json
import os
import time
from bisect import bisect_right
from calendar import monthrange
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any

import baostock as bs
import pandas as pd
import polars as pl


BASE_DIR: Path = Path(__file__).resolve().parent
DEFAULT_OUTPUT_DIR: Path = BASE_DIR / "native_results" / "stock_range_reversion_cache"
LEGACY_CACHE_DIR: Path = BASE_DIR / "native_results" / "cache"

OUTPUT_DIR: Path = Path(os.getenv("OUTPUT_DIR", str(DEFAULT_OUTPUT_DIR))).expanduser().resolve()
START_DATE: str = os.getenv("START_DATE", "20180101")
END_DATE: str = os.getenv("END_DATE", datetime.now().strftime("%Y%m%d"))
UNIVERSE_SOURCE: str = os.getenv("UNIVERSE_SOURCE", "existing_cache").strip().lower()
INDEX_CODE: str = os.getenv("INDEX_CODE", "000852")
TUSHARE_INDEX_CODE: str = os.getenv("TUSHARE_INDEX_CODE", "000852.SH")
BENCHMARK_CODE: str = os.getenv("BENCHMARK_CODE", "sh.000852")
MAX_SYMBOLS: int = int(os.getenv("MAX_SYMBOLS", "0") or 0)
SLEEP_SECONDS: float = float(os.getenv("SLEEP_SECONDS", "0.05") or 0.0)
TUSHARE_SLEEP_SECONDS: float = float(os.getenv("TUSHARE_SLEEP_SECONDS", str(SLEEP_SECONDS)) or 0.0)
BAR_WORKERS: int = int(os.getenv("BAR_WORKERS", "1") or 1)
BAR_CACHE_REFRESH: bool = os.getenv("BAR_CACHE_REFRESH", "0").strip() == "1"
MIN_LISTING_DAYS: int = int(os.getenv("MIN_LISTING_DAYS", "120") or 0)
MIN_ADV20_TURNOVER: float = float(os.getenv("MIN_ADV20_TURNOVER", "20000000") or 0.0)
COMPONENT_LOOKBACK_DAYS: int = int(os.getenv("COMPONENT_LOOKBACK_DAYS", "370") or 0)
TUSHARE_RETRIES: int = int(os.getenv("TUSHARE_RETRIES", "3") or 1)
TUSHARE_RETRY_SLEEP: float = float(os.getenv("TUSHARE_RETRY_SLEEP", "3") or 0.0)
ALLOW_UNIVERSE_FALLBACK: bool = os.getenv("ALLOW_UNIVERSE_FALLBACK", "0").strip() == "1"
REFRESH: bool = os.getenv("REFRESH", "1").strip() == "1"

RAW_ADJUST_FLAG: str = "3"
QFQ_ADJUST_FLAG: str = "2"
FIELDS: str = "date,code,open,high,low,close,preclose,volume,amount,turn,pctChg,tradestatus,isST"


def log(message: str) -> None:
    """Print an unbuffered progress message."""
    print(message, flush=True)


def parse_ymd(value: str) -> datetime:
    """Parse YYYYMMDD into datetime."""
    return datetime.strptime(value, "%Y%m%d")


def normalize_date(value: str) -> str:
    """Normalize YYYYMMDD into YYYY-MM-DD for Baostock."""
    return parse_ymd(value).strftime("%Y-%m-%d")


def round_half_up(value: float) -> float:
    """Round to 2 decimals using exchange-like half-up behavior."""
    return float(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def to_float(value: Any) -> float | None:
    """Convert nullable numeric cells returned by Baostock."""
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def get_limit_ratio(symbol: str, date_str: str, is_st: bool) -> float:
    """Infer daily price limit ratio from A-share board rules and ST status."""
    if is_st:
        return 0.05

    trade_date = datetime.strptime(date_str, "%Y-%m-%d").date()

    if symbol.startswith(("8", "4")):
        return 0.30
    if symbol.startswith("688"):
        return 0.20
    if symbol.startswith(("300", "301")):
        reform_date = datetime(2020, 8, 24).date()
        return 0.20 if trade_date >= reform_date else 0.10

    return 0.10


def code_to_symbol(code: str) -> str:
    """Convert sh.600000 into 600000."""
    return code.split(".")[-1]


def symbol_to_bs_code(symbol: str) -> str:
    """Infer Baostock code from a six-digit A-share symbol."""
    if symbol.startswith(("6", "9")):
        return f"sh.{symbol}"
    if symbol.startswith(("0", "2", "3")):
        return f"sz.{symbol}"
    if symbol.startswith(("4", "8")):
        return f"bj.{symbol}"
    raise ValueError(f"Cannot infer exchange for symbol: {symbol}")


def symbol_to_vt_symbol(symbol: str) -> str:
    """Infer vn.py vt_symbol from a six-digit A-share symbol."""
    if symbol.startswith(("6", "9")):
        return f"{symbol}.SSE"
    if symbol.startswith(("0", "2", "3")):
        return f"{symbol}.SZSE"
    if symbol.startswith(("4", "8")):
        return f"{symbol}.BSE"
    return f"{symbol}.UNKNOWN"


def month_windows(start_date: str, end_date: str) -> list[tuple[str, str]]:
    """Generate month windows in YYYYMMDD format."""
    windows: list[tuple[str, str]] = []
    current = parse_ymd(start_date).replace(day=1)
    end_dt = parse_ymd(end_date)

    while current <= end_dt:
        month_end = current.replace(day=monthrange(current.year, current.month)[1])
        window_start = current.strftime("%Y%m%d")
        window_end = min(month_end, end_dt).strftime("%Y%m%d")
        windows.append((window_start, window_end))
        if current.month == 12:
            current = current.replace(year=current.year + 1, month=1)
        else:
            current = current.replace(month=current.month + 1)

    return windows


def shift_yyyymmdd(value: str, days: int) -> str:
    """Shift YYYYMMDD by a number of calendar days."""
    return (parse_ymd(value) + timedelta(days=days)).strftime("%Y%m%d")


def load_existing_cache_symbols() -> list[str]:
    """Load symbols from the previous alpha-research cache."""
    path = LEGACY_CACHE_DIR / "stock_panel.parquet"
    if not path.exists():
        raise FileNotFoundError(f"Legacy stock cache does not exist: {path}")
    df = pl.read_parquet(path)
    return sorted(df["symbol"].unique().to_list())


def load_manual_symbols() -> list[str]:
    """Load manual symbols from env vars."""
    symbols: list[str] = []
    manual = os.getenv("MANUAL_SYMBOLS", "").strip()
    if manual:
        symbols.extend(item.strip() for item in manual.split(",") if item.strip())

    file_path = os.getenv("SYMBOLS_FILE", "").strip()
    if file_path:
        path = Path(file_path).expanduser().resolve()
        for line in path.read_text(encoding="utf-8").splitlines():
            value = line.strip()
            if value and not value.startswith("#"):
                symbols.append(value)

    symbols = sorted({item.split(".")[0] for item in symbols})
    if not symbols:
        raise RuntimeError("manual universe requires MANUAL_SYMBOLS or SYMBOLS_FILE")
    return symbols


def fetch_akshare_current_csi_symbols() -> list[str]:
    """Fetch current CSI 1000 constituents from CSIndex through Akshare."""
    import akshare as ak

    cons = ak.index_stock_cons_csindex(symbol=INDEX_CODE)
    return sorted(cons["成分券代码"].astype(str).unique().tolist())


def query_baostock_hs300_components(date_str: str) -> list[dict[str, Any]]:
    """Query one historical HS300 constituent snapshot from Baostock."""
    rs = bs.query_hs300_stocks(date=date_str)
    if rs.error_code != "0":
        raise RuntimeError(f"query_hs300_stocks failed for {date_str}: {rs.error_msg}")

    rows: list[dict[str, Any]] = []
    while rs.next():
        item = dict(zip(rs.fields, rs.get_row_data(), strict=False))
        symbol = code_to_symbol(item["code"])
        update_date = item.get("updateDate") or date_str
        rows.append(
            {
                "snapshot_date": datetime.strptime(update_date, "%Y-%m-%d").date(),
                "symbol": symbol,
                "vt_symbol": symbol_to_vt_symbol(symbol),
                "weight": None,
                "source": "baostock_hs300",
            }
        )
    return rows


def fetch_baostock_hs300_historical_components() -> tuple[list[str], pl.DataFrame, str]:
    """Fetch historical HS300 constituent snapshots from Baostock month-end queries."""
    component_start = shift_yyyymmdd(START_DATE, -COMPONENT_LOOKBACK_DAYS)
    rows: list[dict[str, Any]] = []

    login_result = bs.login()
    if login_result.error_code != "0":
        raise RuntimeError(f"baostock login failed: {login_result.error_msg}")

    try:
        for start, end in month_windows(component_start, END_DATE):
            query_date = normalize_date(end)
            log(f"[component] baostock hs300 {query_date}")
            rows.extend(query_baostock_hs300_components(query_date))
            if SLEEP_SECONDS:
                time.sleep(SLEEP_SECONDS)
    finally:
        bs.logout()

    if not rows:
        raise RuntimeError("Baostock returned no HS300 component rows")

    component_df = pl.DataFrame(rows).unique(["snapshot_date", "symbol"]).sort(["snapshot_date", "symbol"])
    symbols = sorted(component_df["symbol"].unique().to_list())
    return symbols, component_df, "baostock_hs300_historical"


def fetch_tushare_historical_components() -> tuple[list[str], pl.DataFrame, str]:
    """Fetch historical CSI constituent snapshots from Tushare when token exists."""
    token = os.getenv("TUSHARE_TOKEN", "").strip()
    if not token:
        raise RuntimeError("TUSHARE_TOKEN is missing")

    import tushare as ts

    pro = ts.pro_api(token)
    rows: list[dict[str, Any]] = []
    component_start = shift_yyyymmdd(START_DATE, -COMPONENT_LOOKBACK_DAYS)

    for start, end in month_windows(component_start, END_DATE):
        log(f"[component] tushare index_weight {start}->{end}")
        last_error: Exception | None = None
        df = None
        for attempt in range(1, TUSHARE_RETRIES + 1):
            try:
                df = pro.index_weight(
                    index_code=TUSHARE_INDEX_CODE,
                    start_date=start,
                    end_date=end,
                    fields="trade_date,con_code,weight",
                )
                last_error = None
                break
            except Exception as exc:
                last_error = exc
                log(f"[component] retry {attempt}/{TUSHARE_RETRIES} failed {start}->{end}: {exc}")
                if attempt < TUSHARE_RETRIES and TUSHARE_RETRY_SLEEP:
                    time.sleep(TUSHARE_RETRY_SLEEP)

        if last_error is not None:
            raise RuntimeError(f"Tushare index_weight failed after retries for {start}->{end}: {last_error}")

        if df is None or df.empty:
            if TUSHARE_SLEEP_SECONDS:
                time.sleep(TUSHARE_SLEEP_SECONDS)
            continue
        for row in df.itertuples(index=False):
            symbol = str(row.con_code).split(".")[0]
            rows.append(
                {
                    "snapshot_date": datetime.strptime(str(row.trade_date), "%Y%m%d").date(),
                    "symbol": symbol,
                    "vt_symbol": symbol_to_vt_symbol(symbol),
                    "weight": to_float(row.weight),
                    "source": "tushare_index_weight",
                }
            )
        if TUSHARE_SLEEP_SECONDS:
            time.sleep(TUSHARE_SLEEP_SECONDS)

    if not rows:
        raise RuntimeError("Tushare returned no index_weight component rows")

    component_df = pl.DataFrame(rows).unique(["snapshot_date", "symbol"]).sort(["snapshot_date", "symbol"])
    symbols = sorted(component_df["symbol"].unique().to_list())
    return symbols, component_df, "tushare_historical"


def resolve_universe() -> tuple[list[str], pl.DataFrame, dict[str, Any]]:
    """Resolve the stock universe and component metadata."""
    meta: dict[str, Any] = {
        "universe_source_requested": UNIVERSE_SOURCE,
        "tushare_token_present": bool(os.getenv("TUSHARE_TOKEN", "").strip()),
        "historical_components_available": False,
        "universe_warning": "",
    }

    if UNIVERSE_SOURCE == "tushare_csi1000":
        try:
            symbols, component_df, source = fetch_tushare_historical_components()
            meta["historical_components_available"] = True
            meta["universe_source_actual"] = source
            return symbols, component_df, meta
        except Exception as exc:
            if not ALLOW_UNIVERSE_FALLBACK:
                raise
            meta["universe_warning"] = (
                f"Tushare historical components unavailable: {exc}; "
                "fallback to existing_cache static universe."
            )
            symbols = load_existing_cache_symbols()
    elif UNIVERSE_SOURCE == "baostock_hs300":
        symbols, component_df, source = fetch_baostock_hs300_historical_components()
        meta["historical_components_available"] = True
        meta["universe_source_actual"] = source
        return symbols, component_df, meta
    elif UNIVERSE_SOURCE == "akshare_csi1000":
        symbols = fetch_akshare_current_csi_symbols()
        meta["universe_warning"] = "Akshare current CSI constituents are not historical membership."
    elif UNIVERSE_SOURCE == "manual":
        symbols = load_manual_symbols()
        meta["universe_warning"] = "Manual universe is static, not historical membership."
    elif UNIVERSE_SOURCE == "existing_cache":
        symbols = load_existing_cache_symbols()
        meta["universe_warning"] = "Existing cache universe is static, not historical membership."
    else:
        raise ValueError(f"Unsupported UNIVERSE_SOURCE: {UNIVERSE_SOURCE}")

    if MAX_SYMBOLS:
        symbols = symbols[:MAX_SYMBOLS]

    rows = [
        {
            "snapshot_date": parse_ymd(START_DATE).date(),
            "symbol": symbol,
            "vt_symbol": symbol_to_vt_symbol(symbol),
            "weight": None,
            "source": f"{UNIVERSE_SOURCE}_static",
        }
        for symbol in symbols
    ]
    component_df = pl.DataFrame(rows)
    meta["universe_source_actual"] = f"{UNIVERSE_SOURCE}_static"
    return symbols, component_df, meta


def fetch_stock_basic() -> pl.DataFrame:
    """Fetch stock listing metadata from Baostock."""
    rs = bs.query_stock_basic()
    if rs.error_code != "0":
        raise RuntimeError(f"query_stock_basic failed: {rs.error_msg}")

    rows: list[list[str]] = []
    while rs.next():
        rows.append(rs.get_row_data())

    if not rows:
        raise RuntimeError("query_stock_basic returned no rows")

    df = pl.from_pandas(pd.DataFrame(rows, columns=rs.fields))
    return (
        df.with_columns(
            pl.col("code").map_elements(code_to_symbol, return_dtype=pl.String).alias("symbol"),
            pl.col("ipoDate").str.strptime(pl.Date, "%Y-%m-%d", strict=False).alias("ipo_date"),
            pl.when(pl.col("outDate") == "")
            .then(None)
            .otherwise(pl.col("outDate"))
            .str.strptime(pl.Date, "%Y-%m-%d", strict=False)
            .alias("out_date"),
            (pl.col("type") == "1").alias("is_stock_type"),
            (pl.col("status") == "1").alias("is_listed_status"),
        )
        .select(
            [
                "symbol",
                "code",
                "code_name",
                "ipo_date",
                "out_date",
                "is_stock_type",
                "is_listed_status",
            ]
        )
        .unique("symbol")
    )


def query_history(bs_code: str, adjustflag: str) -> pd.DataFrame:
    """Query one Baostock daily history table."""
    rs = bs.query_history_k_data_plus(
        bs_code,
        FIELDS,
        start_date=normalize_date(START_DATE),
        end_date=normalize_date(END_DATE),
        frequency="d",
        adjustflag=adjustflag,
    )
    if rs.error_code != "0":
        raise RuntimeError(f"query_history failed for {bs_code}: {rs.error_msg}")

    rows: list[list[str]] = []
    while rs.next():
        rows.append(rs.get_row_data())

    if not rows:
        return pd.DataFrame(columns=rs.fields)

    return pd.DataFrame(rows, columns=rs.fields)


def normalize_history(raw_pdf: pd.DataFrame, qfq_pdf: pd.DataFrame, symbol: str) -> pl.DataFrame:
    """Merge raw and forward-adjusted price histories into one panel."""
    if raw_pdf.empty:
        return pl.DataFrame()

    raw = raw_pdf.copy()
    qfq = qfq_pdf.copy()
    raw["symbol"] = symbol
    qfq = qfq[["date", "code", "open", "high", "low", "close", "preclose"]].copy()
    qfq.columns = ["date", "code", "qfq_open", "qfq_high", "qfq_low", "qfq_close", "qfq_preclose"]

    merged = raw.merge(qfq, on=["date", "code"], how="left")
    df = pl.from_pandas(merged)

    numeric_cols = [
        "open",
        "high",
        "low",
        "close",
        "preclose",
        "volume",
        "amount",
        "turn",
        "pctChg",
        "qfq_open",
        "qfq_high",
        "qfq_low",
        "qfq_close",
        "qfq_preclose",
    ]

    df = df.with_columns(
        [pl.when(pl.col(col) == "").then(None).otherwise(pl.col(col)).alias(col) for col in numeric_cols]
    )

    df = df.with_columns(
        pl.col("date").str.strptime(pl.Date, "%Y-%m-%d").alias("datetime"),
        pl.col("symbol").cast(pl.String),
        pl.lit(symbol_to_vt_symbol(symbol)).alias("vt_symbol"),
        pl.col("code").cast(pl.String).alias("bs_code"),
        pl.col("open").cast(pl.Float64, strict=False).alias("raw_open"),
        pl.col("high").cast(pl.Float64, strict=False).alias("raw_high"),
        pl.col("low").cast(pl.Float64, strict=False).alias("raw_low"),
        pl.col("close").cast(pl.Float64, strict=False).alias("raw_close"),
        pl.col("preclose").cast(pl.Float64, strict=False).alias("raw_preclose"),
        pl.col("qfq_open").cast(pl.Float64, strict=False),
        pl.col("qfq_high").cast(pl.Float64, strict=False),
        pl.col("qfq_low").cast(pl.Float64, strict=False),
        pl.col("qfq_close").cast(pl.Float64, strict=False),
        pl.col("qfq_preclose").cast(pl.Float64, strict=False),
        pl.col("volume").cast(pl.Float64, strict=False),
        pl.col("amount").cast(pl.Float64, strict=False).alias("turnover"),
        pl.col("turn").cast(pl.Float64, strict=False).alias("turnover_rate"),
        pl.col("pctChg").cast(pl.Float64, strict=False).alias("pct_chg"),
        (pl.col("tradestatus") != "1").alias("is_suspended"),
        (pl.col("isST") == "1").alias("is_st"),
    )

    limit_rows: list[dict[str, Any]] = []
    for row in df.select(["datetime", "symbol", "raw_preclose", "is_st"]).iter_rows(named=True):
        preclose = row["raw_preclose"]
        if preclose is None:
            up_limit = None
            down_limit = None
        else:
            ratio = get_limit_ratio(row["symbol"], row["datetime"].strftime("%Y-%m-%d"), row["is_st"])
            up_limit = round_half_up(preclose * (1 + ratio))
            down_limit = round_half_up(preclose * (1 - ratio))
        limit_rows.append(
            {
                "datetime": row["datetime"],
                "symbol": row["symbol"],
                "raw_up_limit": up_limit,
                "raw_down_limit": down_limit,
            }
        )

    limit_df = pl.DataFrame(limit_rows)
    df = df.join(limit_df, on=["datetime", "symbol"], how="left")

    return df.select(
        [
            "datetime",
            "symbol",
            "vt_symbol",
            "bs_code",
            "raw_open",
            "raw_high",
            "raw_low",
            "raw_close",
            "raw_preclose",
            "qfq_open",
            "qfq_high",
            "qfq_low",
            "qfq_close",
            "qfq_preclose",
            "volume",
            "turnover",
            "turnover_rate",
            "pct_chg",
            "is_suspended",
            "is_st",
            "raw_up_limit",
            "raw_down_limit",
        ]
    )


def bar_cache_dir() -> Path:
    """Return the per-symbol Baostock cache directory for this date/price schema."""
    return OUTPUT_DIR / "bar_cache" / f"{START_DATE}_{END_DATE}_{RAW_ADJUST_FLAG}_{QFQ_ADJUST_FLAG}"


def bar_cache_path(cache_dir: Path, symbol: str) -> Path:
    """Return one symbol's cached parquet path."""
    return cache_dir / f"{symbol}.parquet"


def download_symbol_history(symbol: str) -> pl.DataFrame:
    """Download and normalize one symbol history."""
    bs_code = symbol_to_bs_code(symbol)
    raw_pdf = query_history(bs_code, RAW_ADJUST_FLAG)
    qfq_pdf = query_history(bs_code, QFQ_ADJUST_FLAG)
    return normalize_history(raw_pdf, qfq_pdf, symbol)


def download_symbol_to_cache(symbol: str, cache_dir: Path) -> tuple[str, int, str]:
    """Download one symbol and persist it to cache."""
    path = bar_cache_path(cache_dir, symbol)
    if path.exists() and not BAR_CACHE_REFRESH:
        try:
            return symbol, pl.read_parquet(path).height, ""
        except Exception:
            path.unlink(missing_ok=True)

    try:
        frame = download_symbol_history(symbol)
        if frame.is_empty():
            return symbol, 0, "empty"
        frame.write_parquet(path)
        return symbol, frame.height, ""
    except Exception as exc:
        return symbol, 0, str(exc)


def build_stock_panel(symbols: list[str]) -> tuple[pl.DataFrame, list[str]]:
    """Download stock raw and qfq histories and build the research panel."""
    if MAX_SYMBOLS:
        symbols = symbols[:MAX_SYMBOLS]

    cache_dir = bar_cache_dir()
    cache_dir.mkdir(parents=True, exist_ok=True)
    failed: list[str] = []

    missing_symbols = [
        symbol
        for symbol in symbols
        if BAR_CACHE_REFRESH or not bar_cache_path(cache_dir, symbol).exists()
    ]
    cached_count = len(symbols) - len(missing_symbols)
    log(f"[bar] cache_dir={cache_dir}")
    log(f"[bar] cached={cached_count} missing={len(missing_symbols)} workers=1")
    if BAR_WORKERS > 1:
        log("[bar] BAR_WORKERS>1 is disabled because Baostock login state is not process-safe")

    for index, symbol in enumerate(missing_symbols, start=1):
        bs_code = symbol_to_bs_code(symbol)
        log(f"[bar] {index}/{len(missing_symbols)} {bs_code}")
        downloaded_symbol, rows, error = download_symbol_to_cache(symbol, cache_dir)
        if error:
            failed.append(downloaded_symbol)
            log(f"[bar] failed {downloaded_symbol}: {error}")
        elif rows == 0:
            failed.append(downloaded_symbol)

        if SLEEP_SECONDS:
            time.sleep(SLEEP_SECONDS)

    frames: list[pl.DataFrame] = []
    for symbol in symbols:
        path = bar_cache_path(cache_dir, symbol)
        if not path.exists():
            if symbol not in failed:
                failed.append(symbol)
            continue
        try:
            frames.append(pl.read_parquet(path))
        except Exception as exc:
            failed.append(symbol)
            log(f"[bar] failed to read cache {symbol}: {exc}")

    if not frames:
        raise RuntimeError("No stock history was downloaded")

    panel = pl.concat(frames, how="vertical").sort(["symbol", "datetime"])
    return panel, failed


def fetch_benchmark() -> pl.DataFrame:
    """Fetch raw CSI benchmark bars from Baostock."""
    rs = bs.query_history_k_data_plus(
        BENCHMARK_CODE,
        "date,code,open,high,low,close,preclose,volume,amount,pctChg",
        start_date=normalize_date(START_DATE),
        end_date=normalize_date(END_DATE),
        frequency="d",
        adjustflag=RAW_ADJUST_FLAG,
    )
    if rs.error_code != "0":
        raise RuntimeError(f"benchmark query failed: {rs.error_msg}")

    rows: list[list[str]] = []
    while rs.next():
        rows.append(rs.get_row_data())

    if not rows:
        raise RuntimeError("benchmark query returned no rows")

    df = pl.from_pandas(pd.DataFrame(rows, columns=rs.fields))
    numeric_cols = ["open", "high", "low", "close", "preclose", "volume", "amount", "pctChg"]
    df = df.with_columns(
        [pl.when(pl.col(col) == "").then(None).otherwise(pl.col(col)).alias(col) for col in numeric_cols]
    )
    return (
        df.with_columns(
            pl.col("date").str.strptime(pl.Date, "%Y-%m-%d").alias("datetime"),
            pl.col("code").alias("bs_code"),
            pl.col("open").cast(pl.Float64, strict=False),
            pl.col("high").cast(pl.Float64, strict=False),
            pl.col("low").cast(pl.Float64, strict=False),
            pl.col("close").cast(pl.Float64, strict=False),
            pl.col("preclose").cast(pl.Float64, strict=False),
            pl.col("volume").cast(pl.Float64, strict=False),
            pl.col("amount").cast(pl.Float64, strict=False).alias("turnover"),
            pl.col("pctChg").cast(pl.Float64, strict=False).alias("pct_chg"),
        )
        .select(["datetime", "bs_code", "open", "high", "low", "close", "preclose", "volume", "turnover", "pct_chg"])
        .sort("datetime")
    )


def enrich_panel(panel: pl.DataFrame, stock_basic: pl.DataFrame, universe_meta: dict[str, Any]) -> pl.DataFrame:
    """Add metadata, limit flags, listing age, and liquidity fields."""
    enriched = panel.join(stock_basic, on="symbol", how="left")

    enriched = enriched.with_columns(
        (pl.col("datetime") - pl.col("ipo_date")).dt.total_days().alias("listing_days"),
        pl.col("turnover").rolling_mean(20).over("symbol").alias("adv20_turnover"),
        pl.col("volume").rolling_mean(20).over("symbol").alias("adv20_volume"),
        (pl.col("raw_open") == pl.col("raw_high"))
        .and_(pl.col("raw_high") == pl.col("raw_low"))
        .and_(pl.col("raw_low") == pl.col("raw_close"))
        .alias("is_one_price_bar"),
    )

    enriched = enriched.with_columns(
        (
            pl.col("is_one_price_bar")
            & (pl.col("raw_close") >= pl.col("raw_up_limit") - 0.005)
        ).alias("is_oneword_limit_up"),
        (
            pl.col("is_one_price_bar")
            & (pl.col("raw_close") <= pl.col("raw_down_limit") + 0.005)
        ).alias("is_oneword_limit_down"),
        (pl.col("raw_close") >= pl.col("raw_up_limit") - 0.005).alias("is_limit_up_close"),
        (pl.col("raw_close") <= pl.col("raw_down_limit") + 0.005).alias("is_limit_down_close"),
    )

    enriched = enriched.with_columns(
        (
            (~pl.col("is_suspended"))
            & (~pl.col("is_st"))
            & pl.col("is_stock_type").fill_null(False)
            & pl.col("is_listed_status").fill_null(False)
            & (pl.col("listing_days") >= MIN_LISTING_DAYS)
            & (pl.col("volume").fill_null(0) > 0)
            & (pl.col("turnover").fill_null(0) > 0)
            & (pl.col("adv20_turnover").fill_null(0) >= MIN_ADV20_TURNOVER)
            & pl.col("qfq_close").is_not_null()
        ).alias("eligible_research_row"),
        pl.lit(universe_meta.get("universe_source_actual", "")).alias("universe_source"),
        pl.lit(bool(universe_meta.get("historical_components_available", False))).alias("has_historical_component_source"),
    )

    return enriched.sort(["symbol", "datetime"])


def build_daily_component_membership(panel: pl.DataFrame, component_df: pl.DataFrame) -> pl.DataFrame:
    """Map every panel date to the latest known component snapshot without lookahead."""
    dates = panel.select("datetime").unique().sort("datetime")["datetime"].to_list()
    snapshots = component_df.select("snapshot_date").unique().sort("snapshot_date")["snapshot_date"].to_list()
    if not dates or not snapshots:
        return pl.DataFrame({"datetime": [], "symbol": [], "is_index_component": [], "component_weight": [], "component_snapshot_date": []})

    component_by_snapshot: dict[Any, pl.DataFrame] = {
        snapshot: component_df.filter(pl.col("snapshot_date") == snapshot).select(["symbol", "weight"])
        for snapshot in snapshots
    }

    frames: list[pl.DataFrame] = []
    for trade_date in dates:
        index = bisect_right(snapshots, trade_date) - 1
        if index < 0:
            continue
        snapshot = snapshots[index]
        frame = component_by_snapshot[snapshot].with_columns(
            pl.lit(trade_date).alias("datetime"),
            pl.lit(True).alias("is_index_component"),
            pl.lit(snapshot).alias("component_snapshot_date"),
            pl.col("weight").alias("component_weight"),
        ).select(["datetime", "symbol", "is_index_component", "component_weight", "component_snapshot_date"])
        frames.append(frame)

    if not frames:
        return pl.DataFrame({"datetime": [], "symbol": [], "is_index_component": [], "component_weight": [], "component_snapshot_date": []})

    return pl.concat(frames, how="vertical")


def apply_component_membership(panel: pl.DataFrame, component_df: pl.DataFrame, universe_meta: dict[str, Any]) -> pl.DataFrame:
    """Attach historical/static index membership to the research panel."""
    membership = build_daily_component_membership(panel, component_df)
    if membership.is_empty():
        return panel.with_columns(
            pl.lit(False).alias("is_index_component"),
            pl.lit(None, dtype=pl.Float64).alias("component_weight"),
            pl.lit(None, dtype=pl.Date).alias("component_snapshot_date"),
        )

    enriched = panel.join(membership, on=["datetime", "symbol"], how="left")
    historical_available = bool(universe_meta.get("historical_components_available", False))

    return enriched.with_columns(
        pl.col("is_index_component").fill_null(False),
        pl.col("component_weight").cast(pl.Float64, strict=False),
        pl.col("component_snapshot_date").cast(pl.Date, strict=False),
        pl.lit(historical_available).alias("has_historical_component_source"),
    )


def summarize(panel: pl.DataFrame, benchmark: pl.DataFrame, failed: list[str], universe_meta: dict[str, Any]) -> dict[str, Any]:
    """Build a compact manifest summary."""
    return {
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "start_date": START_DATE,
        "end_date": END_DATE,
        "raw_adjustflag": RAW_ADJUST_FLAG,
        "qfq_adjustflag": QFQ_ADJUST_FLAG,
        "output_dir": str(OUTPUT_DIR),
        "universe": universe_meta,
        "stock_rows": panel.height,
        "stock_symbols": panel["symbol"].n_unique(),
        "stock_date_min": str(panel["datetime"].min()),
        "stock_date_max": str(panel["datetime"].max()),
        "benchmark_rows": benchmark.height,
        "benchmark_date_min": str(benchmark["datetime"].min()),
        "benchmark_date_max": str(benchmark["datetime"].max()),
        "failed_symbols": failed,
        "failed_symbol_count": len(failed),
        "eligible_rows": int(panel["eligible_research_row"].sum()),
        "eligible_ratio": float(panel["eligible_research_row"].mean()),
        "component_rows": int(panel["is_index_component"].sum()) if "is_index_component" in panel.columns else 0,
        "component_ratio": float(panel["is_index_component"].mean()) if "is_index_component" in panel.columns else 0.0,
        "eligible_component_rows": int(panel["eligible_component_row"].sum()) if "eligible_component_row" in panel.columns else 0,
        "eligible_component_ratio": float(panel["eligible_component_row"].mean()) if "eligible_component_row" in panel.columns else 0.0,
        "min_listing_days": MIN_LISTING_DAYS,
        "min_adv20_turnover": MIN_ADV20_TURNOVER,
        "component_lookback_days": COMPONENT_LOOKBACK_DAYS,
        "known_limitations": [
            "Historical component membership is only available when the selected UNIVERSE_SOURCE provides point-in-time constituent snapshots.",
            "Raw prices are used for tradability and limit checks; qfq prices are used for signal and return research.",
            "This builder prepares research data only; it does not run a trading backtest.",
        ],
    }


def write_report(summary: dict[str, Any], paths: dict[str, Path]) -> Path:
    """Write a Chinese manifest report for the generated panel."""
    report_path = OUTPUT_DIR / "stock_range_reversion_research_manifest.md"
    universe = summary["universe"]
    lines = [
        "# 股票震荡研究面板构建记录",
        "",
        "## 核心结论",
        "",
        "- 已生成独立股票震荡研究面板，不覆盖原有 `native_results/cache` 示例数据。",
        "- 面板同时保留原始价和前复权价：原始价用于停牌、涨跌停、成交额等交易约束；前复权价用于信号和收益研究。",
        f"- 股票行数：`{summary['stock_rows']}`，股票数：`{summary['stock_symbols']}`，日期：`{summary['stock_date_min']}`到`{summary['stock_date_max']}`。",
        f"- 可研究行数：`{summary['eligible_rows']}`，占比：`{summary['eligible_ratio']:.2%}`。",
        f"- 成分内行数：`{summary['component_rows']}`，占比：`{summary['component_ratio']:.2%}`。",
        f"- 成分内可研究行数：`{summary['eligible_component_rows']}`，占比：`{summary['eligible_component_ratio']:.2%}`。",
        f"- 股票池实际来源：`{universe.get('universe_source_actual')}`。",
        f"- 是否有历史成分来源：`{universe.get('historical_components_available')}`。",
    ]

    warning = universe.get("universe_warning")
    if warning:
        lines.append(f"- 股票池警告：`{warning}`")

    lines.extend(
        [
            "",
            "## 仍需注意",
            "",
            "- 若没有 Tushare 历史成分权限，本面板仍然只能解决复权、上市天数、流动性和交易约束问题，不能完全消除历史成分幸存者偏差。",
            "- 当前脚本只构建研究数据，不产生交易策略、不产生资金曲线。",
            "- 后续信号归因应优先读取本面板中的 `qfq_*` 字段和 `eligible_research_row`。",
            "",
            "## 输出文件",
            "",
        ]
    )

    for name, path in paths.items():
        lines.append(f"- {name}: `{path}`")

    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path


def main() -> None:
    """Build the stock range-reversion research panel."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    panel_path = OUTPUT_DIR / "stock_range_reversion_research_panel.parquet"
    benchmark_path = OUTPUT_DIR / "stock_range_reversion_benchmark.parquet"
    component_path = OUTPUT_DIR / "stock_range_reversion_components.parquet"
    basic_path = OUTPUT_DIR / "stock_range_reversion_stock_basic.parquet"
    manifest_path = OUTPUT_DIR / "stock_range_reversion_research_manifest.json"

    if panel_path.exists() and benchmark_path.exists() and manifest_path.exists() and not REFRESH:
        log(f"cache exists and REFRESH=0: {OUTPUT_DIR}")
        return

    symbols, component_df, universe_meta = resolve_universe()
    if MAX_SYMBOLS:
        symbols = symbols[:MAX_SYMBOLS]
    log(f"[universe] symbols={len(symbols)} source={universe_meta.get('universe_source_actual')}")

    login_result = bs.login()
    if login_result.error_code != "0":
        raise RuntimeError(f"baostock login failed: {login_result.error_msg}")

    try:
        stock_basic = fetch_stock_basic()
        panel, failed = build_stock_panel(symbols)
        benchmark = fetch_benchmark()
    finally:
        bs.logout()

    panel = enrich_panel(panel, stock_basic, universe_meta)
    panel = apply_component_membership(panel, component_df, universe_meta)
    panel = panel.with_columns(
        (pl.col("eligible_research_row") & pl.col("is_index_component")).alias("eligible_component_row")
    )
    summary = summarize(panel, benchmark, failed, universe_meta)

    panel.write_parquet(panel_path)
    benchmark.write_parquet(benchmark_path)
    component_df.write_parquet(component_path)
    stock_basic.write_parquet(basic_path)
    manifest_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")

    report_path = write_report(
        summary,
        {
            "panel": panel_path,
            "benchmark": benchmark_path,
            "components": component_path,
            "stock_basic": basic_path,
            "manifest_json": manifest_path,
        },
    )

    log(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    log(f"report={report_path}")


if __name__ == "__main__":
    main()
