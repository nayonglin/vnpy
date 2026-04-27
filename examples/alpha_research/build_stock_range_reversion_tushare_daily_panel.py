from __future__ import annotations

import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import polars as pl
import tushare as ts

from build_stock_range_reversion_research_panel import (
    BENCHMARK_CODE,
    COMPONENT_LOOKBACK_DAYS,
    END_DATE,
    INDEX_CODE,
    MAX_SYMBOLS,
    MIN_ADV20_TURNOVER,
    MIN_LISTING_DAYS,
    OUTPUT_DIR,
    REFRESH,
    START_DATE,
    TUSHARE_INDEX_CODE,
    apply_component_membership,
    fetch_tushare_historical_components,
    get_limit_ratio,
    log,
    parse_ymd,
    round_half_up,
    summarize,
    symbol_to_vt_symbol,
    write_report,
)


TUSHARE_DAILY_SLEEP_SECONDS: float = float(os.getenv("TUSHARE_DAILY_SLEEP_SECONDS", "0.35") or 0.0)
TUSHARE_CALL_SLEEP_SECONDS: float = float(os.getenv("TUSHARE_CALL_SLEEP_SECONDS", "0") or 0.0)
TUSHARE_DAILY_RETRIES: int = int(os.getenv("TUSHARE_DAILY_RETRIES", "5") or 1)
TUSHARE_DAILY_RETRY_SLEEP: float = float(os.getenv("TUSHARE_DAILY_RETRY_SLEEP", "20") or 0.0)
DAILY_CACHE_REFRESH: bool = os.getenv("DAILY_CACHE_REFRESH", "0").strip() == "1"
COMPONENT_CACHE_REFRESH: bool = os.getenv("COMPONENT_CACHE_REFRESH", "0").strip() == "1"
BASIC_CACHE_REFRESH: bool = os.getenv("BASIC_CACHE_REFRESH", "0").strip() == "1"
FETCH_STK_LIMIT: bool = os.getenv("FETCH_STK_LIMIT", "0").strip() == "1"


def get_pro() -> Any:
    """Create a Tushare Pro client."""
    token = os.getenv("TUSHARE_TOKEN", "").strip()
    if not token:
        raise RuntimeError("TUSHARE_TOKEN is missing")
    return ts.pro_api(token)


def to_symbol(ts_code: str) -> str:
    """Convert 000001.SZ into 000001."""
    return str(ts_code).split(".")[0]


def to_bs_code(ts_code: str) -> str:
    """Convert a Tushare stock or index code into Baostock-style code."""
    symbol, suffix = str(ts_code).split(".")
    suffix = suffix.upper()
    if suffix == "SH":
        return f"sh.{symbol}"
    if suffix == "SZ":
        return f"sz.{symbol}"
    if suffix == "BJ":
        return f"bj.{symbol}"
    return str(ts_code)


def call_with_retry(name: str, func: Any, **kwargs: Any) -> pd.DataFrame:
    """Call one Tushare endpoint with retries."""
    last_error: Exception | None = None
    for attempt in range(1, TUSHARE_DAILY_RETRIES + 1):
        try:
            data = func(**kwargs)
            if TUSHARE_CALL_SLEEP_SECONDS:
                time.sleep(TUSHARE_CALL_SLEEP_SECONDS)
            return data
        except Exception as exc:
            last_error = exc
            log(f"[tushare] retry {attempt}/{TUSHARE_DAILY_RETRIES} failed {name}: {exc}")
            if attempt < TUSHARE_DAILY_RETRIES and TUSHARE_DAILY_RETRY_SLEEP:
                time.sleep(TUSHARE_DAILY_RETRY_SLEEP)
    raise RuntimeError(f"Tushare call failed after retries: {name}: {last_error}")


def trade_dates(pro: Any) -> list[str]:
    """Load open trading dates."""
    df = call_with_retry(
        "trade_cal",
        pro.trade_cal,
        exchange="SSE",
        start_date=START_DATE,
        end_date=END_DATE,
        fields="cal_date,is_open",
    )
    return sorted(df.loc[df["is_open"] == 1, "cal_date"].astype(str).tolist())


def fetch_stock_basic(pro: Any) -> pl.DataFrame:
    """Fetch listed, delisted, and paused stock metadata."""
    frames: list[pd.DataFrame] = []
    for status in ["L", "D", "P"]:
        df = call_with_retry(
            f"stock_basic_{status}",
            pro.stock_basic,
            exchange="",
            list_status=status,
            fields="ts_code,symbol,name,list_date,delist_date",
        )
        if df is not None and not df.empty:
            df["list_status"] = status
            frames.append(df)
    if not frames:
        raise RuntimeError("Tushare stock_basic returned no rows")

    df = pl.from_pandas(pd.concat(frames, ignore_index=True)).with_columns(
        pl.col("symbol").cast(pl.String),
        pl.col("ts_code").map_elements(to_bs_code, return_dtype=pl.String).alias("code"),
        pl.col("name").cast(pl.String).alias("code_name"),
        pl.col("list_date").str.strptime(pl.Date, "%Y%m%d", strict=False).alias("ipo_date"),
        pl.col("delist_date").str.strptime(pl.Date, "%Y%m%d", strict=False).alias("out_date"),
        pl.lit(True).alias("is_stock_type"),
    )
    return df.select(
        [
            "symbol",
            "code",
            "code_name",
            "ipo_date",
            "out_date",
            "is_stock_type",
        ]
    ).unique("symbol")


def load_or_fetch_stock_basic(pro: Any, path: Path) -> pl.DataFrame:
    """Load stock_basic from cache or fetch it from Tushare."""
    if path.exists() and not BASIC_CACHE_REFRESH:
        return pl.read_parquet(path)
    data = fetch_stock_basic(pro)
    data.write_parquet(path)
    return data


def fetch_namechange_st(pro: Any, symbols: set[str]) -> pl.DataFrame:
    """Fetch ST intervals from Tushare namechange records when available."""
    try:
        df = call_with_retry(
            "namechange",
            pro.namechange,
            fields="ts_code,name,start_date,end_date,change_reason",
        )
    except Exception as exc:
        log(f"[namechange] skipped: {exc}")
        return pl.DataFrame({"symbol": [], "start_date": [], "end_date": []})

    if df is None or df.empty:
        return pl.DataFrame({"symbol": [], "start_date": [], "end_date": []})

    pdf = df.copy()
    pdf["symbol"] = pdf["ts_code"].astype(str).str.split(".").str[0]
    pdf = pdf[pdf["symbol"].isin(symbols)]
    pdf = pdf[pdf["name"].astype(str).str.contains("ST", na=False)]
    if pdf.empty:
        return pl.DataFrame({"symbol": [], "start_date": [], "end_date": []})

    return pl.from_pandas(pdf).with_columns(
        pl.col("symbol").cast(pl.String),
        pl.col("start_date").str.strptime(pl.Date, "%Y%m%d", strict=False),
        pl.col("end_date").str.strptime(pl.Date, "%Y%m%d", strict=False),
    ).select(["symbol", "start_date", "end_date"])


def load_or_fetch_namechange_st(pro: Any, symbols: set[str], path: Path) -> pl.DataFrame:
    """Load ST interval cache or fetch it from Tushare."""
    if path.exists() and not BASIC_CACHE_REFRESH:
        return pl.read_parquet(path)
    data = fetch_namechange_st(pro, symbols)
    data.write_parquet(path)
    return data


def date_cache_dir() -> Path:
    """Return the per-trade-date Tushare cache directory."""
    return OUTPUT_DIR / "tushare_daily_cache" / f"{START_DATE}_{END_DATE}"


def date_cache_path(cache_dir: Path, trade_date: str) -> Path:
    """Return one trade date's cached parquet path."""
    return cache_dir / f"{trade_date}.parquet"


def fetch_one_trade_date(pro: Any, trade_date: str, symbols: set[str], cache_dir: Path) -> pl.DataFrame:
    """Fetch and cache one trading date's raw, limit, and adjustment data."""
    path = date_cache_path(cache_dir, trade_date)
    if path.exists() and not DAILY_CACHE_REFRESH:
        return pl.read_parquet(path)

    raw = call_with_retry(
        f"daily_{trade_date}",
        pro.daily,
        trade_date=trade_date,
        fields="ts_code,trade_date,open,high,low,close,pre_close,pct_chg,vol,amount",
    )
    adj = call_with_retry(
        f"adj_factor_{trade_date}",
        pro.adj_factor,
        trade_date=trade_date,
        fields="ts_code,trade_date,adj_factor",
    )
    if FETCH_STK_LIMIT:
        limit_df = call_with_retry(
            f"stk_limit_{trade_date}",
            pro.stk_limit,
            trade_date=trade_date,
            fields="ts_code,trade_date,up_limit,down_limit",
        )
    else:
        limit_df = pd.DataFrame(columns=["ts_code", "trade_date", "up_limit", "down_limit"])

    if raw is None or raw.empty:
        out = pl.DataFrame()
        out.write_parquet(path)
        return out

    raw["symbol"] = raw["ts_code"].astype(str).str.split(".").str[0]
    raw = raw[raw["symbol"].isin(symbols)]
    if raw.empty:
        out = pl.DataFrame()
        out.write_parquet(path)
        return out

    merged = raw.merge(adj, on=["ts_code", "trade_date"], how="left")
    merged = merged.merge(limit_df, on=["ts_code", "trade_date"], how="left")
    out = pl.from_pandas(merged).with_columns(
        pl.col("trade_date").str.strptime(pl.Date, "%Y%m%d").alias("datetime"),
        pl.col("symbol").cast(pl.String),
        pl.col("symbol").map_elements(symbol_to_vt_symbol, return_dtype=pl.String).alias("vt_symbol"),
        pl.col("ts_code").map_elements(to_bs_code, return_dtype=pl.String).alias("bs_code"),
        pl.col("open").cast(pl.Float64, strict=False).alias("raw_open"),
        pl.col("high").cast(pl.Float64, strict=False).alias("raw_high"),
        pl.col("low").cast(pl.Float64, strict=False).alias("raw_low"),
        pl.col("close").cast(pl.Float64, strict=False).alias("raw_close"),
        pl.col("pre_close").cast(pl.Float64, strict=False).alias("raw_preclose"),
        (pl.col("vol").cast(pl.Float64, strict=False) * 100.0).alias("volume"),
        (pl.col("amount").cast(pl.Float64, strict=False) * 1000.0).alias("turnover"),
        pl.lit(None, dtype=pl.Float64).alias("turnover_rate"),
        pl.col("pct_chg").cast(pl.Float64, strict=False),
        pl.col("up_limit").cast(pl.Float64, strict=False).alias("raw_up_limit"),
        pl.col("down_limit").cast(pl.Float64, strict=False).alias("raw_down_limit"),
        pl.col("adj_factor").cast(pl.Float64, strict=False),
    ).select(
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
            "volume",
            "turnover",
            "turnover_rate",
            "pct_chg",
            "raw_up_limit",
            "raw_down_limit",
            "adj_factor",
        ]
    )
    out.write_parquet(path)
    return out


def fetch_daily_market_panel(pro: Any, symbols: list[str]) -> pl.DataFrame:
    """Fetch all trade-date daily panels and concatenate them."""
    dates = trade_dates(pro)
    symbol_set = set(symbols)
    cache_dir = date_cache_dir()
    cache_dir.mkdir(parents=True, exist_ok=True)

    frames: list[pl.DataFrame] = []
    for index, trade_date in enumerate(dates, start=1):
        log(f"[daily] {index}/{len(dates)} {trade_date}")
        frame = fetch_one_trade_date(pro, trade_date, symbol_set, cache_dir)
        if not frame.is_empty():
            frames.append(frame)
        if TUSHARE_DAILY_SLEEP_SECONDS:
            time.sleep(TUSHARE_DAILY_SLEEP_SECONDS)

    if not frames:
        raise RuntimeError("No Tushare daily rows were downloaded")

    return pl.concat(frames, how="vertical").with_columns(
        pl.col("symbol").map_elements(symbol_to_vt_symbol, return_dtype=pl.String).alias("vt_symbol")
    ).sort(["symbol", "datetime"])


def add_qfq_prices(panel: pl.DataFrame) -> pl.DataFrame:
    """Calculate forward-adjusted prices from raw prices and adj_factor."""
    latest_factor = (
        panel.filter(pl.col("adj_factor").is_not_null())
        .sort(["symbol", "datetime"])
        .group_by("symbol")
        .agg(pl.col("adj_factor").last().alias("latest_adj_factor"))
    )
    return panel.join(latest_factor, on="symbol", how="left").with_columns(
        (pl.col("raw_open") * pl.col("adj_factor") / pl.col("latest_adj_factor")).alias("qfq_open"),
        (pl.col("raw_high") * pl.col("adj_factor") / pl.col("latest_adj_factor")).alias("qfq_high"),
        (pl.col("raw_low") * pl.col("adj_factor") / pl.col("latest_adj_factor")).alias("qfq_low"),
        (pl.col("raw_close") * pl.col("adj_factor") / pl.col("latest_adj_factor")).alias("qfq_close"),
        (pl.col("raw_preclose") * pl.col("adj_factor") / pl.col("latest_adj_factor")).alias("qfq_preclose"),
    ).drop("latest_adj_factor")


def apply_status_and_filters(panel: pl.DataFrame, stock_basic: pl.DataFrame, st_df: pl.DataFrame) -> pl.DataFrame:
    """Add listing, ST, suspension, limit, and eligibility fields."""
    enriched = panel.join(stock_basic, on="symbol", how="left")
    if st_df.is_empty():
        enriched = enriched.with_columns(pl.lit(False).alias("is_st"))
    else:
        st_marks = []
        dates = enriched.select("datetime").unique().sort("datetime")["datetime"].to_list()
        for row in st_df.iter_rows(named=True):
            start = row["start_date"]
            end = row["end_date"] or parse_ymd(END_DATE).date()
            for date in dates:
                if start and start <= date <= end:
                    st_marks.append({"symbol": row["symbol"], "datetime": date, "is_st": True})
        mark_df = (
            pl.DataFrame(st_marks).unique(["symbol", "datetime"])
            if st_marks
            else pl.DataFrame({"symbol": [], "datetime": [], "is_st": []})
        )
        enriched = enriched.join(mark_df, on=["symbol", "datetime"], how="left").with_columns(
            pl.col("is_st").fill_null(False)
        )

    limit_rows: list[dict[str, Any]] = []
    missing_limit = enriched.filter(
        pl.col("raw_preclose").is_not_null()
        & (pl.col("raw_up_limit").is_null() | pl.col("raw_down_limit").is_null())
    )
    for row in missing_limit.select(["datetime", "symbol", "raw_preclose", "is_st"]).iter_rows(named=True):
        ratio = get_limit_ratio(row["symbol"], row["datetime"].strftime("%Y-%m-%d"), row["is_st"])
        limit_rows.append(
            {
                "datetime": row["datetime"],
                "symbol": row["symbol"],
                "computed_up_limit": round_half_up(row["raw_preclose"] * (1 + ratio)),
                "computed_down_limit": round_half_up(row["raw_preclose"] * (1 - ratio)),
            }
        )

    if limit_rows:
        computed_limits = pl.DataFrame(limit_rows)
        enriched = enriched.join(computed_limits, on=["datetime", "symbol"], how="left").with_columns(
            pl.coalesce([pl.col("raw_up_limit"), pl.col("computed_up_limit")]).alias("raw_up_limit"),
            pl.coalesce([pl.col("raw_down_limit"), pl.col("computed_down_limit")]).alias("raw_down_limit"),
        ).drop(["computed_up_limit", "computed_down_limit"])

    enriched = enriched.with_columns(
        (pl.col("datetime") - pl.col("ipo_date")).dt.total_days().alias("listing_days"),
        (
            pl.col("raw_close").is_null()
            | (pl.col("datetime") < pl.col("ipo_date"))
            | (pl.col("out_date").is_not_null() & (pl.col("datetime") > pl.col("out_date")))
        ).alias("is_suspended"),
        (
            pl.col("out_date").is_null() | (pl.col("datetime") <= pl.col("out_date"))
        ).alias("is_listed_status"),
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
    return enriched.with_columns(
        (
            (~pl.col("is_suspended"))
            & (~pl.col("is_st"))
            & pl.col("is_stock_type").fill_null(True)
            & pl.col("is_listed_status").fill_null(False)
            & (pl.col("listing_days") >= MIN_LISTING_DAYS)
            & (pl.col("volume").fill_null(0) > 0)
            & (pl.col("turnover").fill_null(0) > 0)
            & (pl.col("adv20_turnover").fill_null(0) >= MIN_ADV20_TURNOVER)
            & pl.col("qfq_close").is_not_null()
        ).alias("eligible_research_row"),
        pl.lit("tushare_daily").alias("price_source"),
        pl.lit("tushare_historical").alias("universe_source"),
        pl.lit(True).alias("has_historical_component_source"),
    ).sort(["symbol", "datetime"])


def build_full_calendar_panel(raw_panel: pl.DataFrame, symbols: list[str], dates: list[Any]) -> pl.DataFrame:
    """Expand to symbol-date grid so suspended dates are explicit."""
    grid = pl.DataFrame({"datetime": dates}).join(pl.DataFrame({"symbol": symbols}), how="cross")
    return grid.join(raw_panel, on=["datetime", "symbol"], how="left").with_columns(
        pl.col("symbol").map_elements(symbol_to_vt_symbol, return_dtype=pl.String).alias("vt_symbol"),
    )


def fetch_benchmark(pro: Any) -> pl.DataFrame:
    """Fetch CSI 1000 index daily bars from Tushare."""
    df = call_with_retry(
        "index_daily",
        pro.index_daily,
        ts_code=TUSHARE_INDEX_CODE,
        start_date=START_DATE,
        end_date=END_DATE,
        fields="ts_code,trade_date,open,high,low,close,pre_close,pct_chg,vol,amount",
    )
    if df is None or df.empty:
        raise RuntimeError("Tushare index_daily returned no benchmark rows")
    return pl.from_pandas(df).with_columns(
        pl.col("trade_date").str.strptime(pl.Date, "%Y%m%d").alias("datetime"),
        pl.lit(BENCHMARK_CODE).alias("bs_code"),
        pl.col("open").cast(pl.Float64, strict=False),
        pl.col("high").cast(pl.Float64, strict=False),
        pl.col("low").cast(pl.Float64, strict=False),
        pl.col("close").cast(pl.Float64, strict=False),
        pl.col("pre_close").cast(pl.Float64, strict=False).alias("preclose"),
        (pl.col("vol").cast(pl.Float64, strict=False) * 100.0).alias("volume"),
        (pl.col("amount").cast(pl.Float64, strict=False) * 1000.0).alias("turnover"),
        pl.col("pct_chg").cast(pl.Float64, strict=False),
    ).select(["datetime", "bs_code", "open", "high", "low", "close", "preclose", "volume", "turnover", "pct_chg"]).sort("datetime")


def load_or_fetch_components(component_path: Path) -> tuple[list[str], pl.DataFrame, str]:
    """Load historical components from cache or fetch and persist them."""
    if component_path.exists() and not COMPONENT_CACHE_REFRESH:
        component_df = pl.read_parquet(component_path)
        symbols = sorted(component_df["symbol"].unique().to_list())
        return symbols, component_df, "tushare_historical"

    symbols, component_df, source = fetch_tushare_historical_components()
    component_df.write_parquet(component_path)
    return symbols, component_df, source


def main() -> None:
    """Build long-history stock range-reversion panel from Tushare date batches."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    panel_path = OUTPUT_DIR / "stock_range_reversion_research_panel.parquet"
    benchmark_path = OUTPUT_DIR / "stock_range_reversion_benchmark.parquet"
    component_path = OUTPUT_DIR / "stock_range_reversion_components.parquet"
    basic_path = OUTPUT_DIR / "stock_range_reversion_stock_basic.parquet"
    st_path = OUTPUT_DIR / "stock_range_reversion_namechange_st.parquet"
    manifest_path = OUTPUT_DIR / "stock_range_reversion_research_manifest.json"

    if panel_path.exists() and benchmark_path.exists() and manifest_path.exists() and not REFRESH:
        log(f"cache exists and REFRESH=0: {OUTPUT_DIR}")
        return

    pro = get_pro()
    symbols, component_df, source = load_or_fetch_components(component_path)
    if MAX_SYMBOLS:
        symbols = symbols[:MAX_SYMBOLS]
    universe_meta = {
        "universe_source_requested": "tushare_csi1000",
        "tushare_token_present": True,
        "historical_components_available": True,
        "universe_warning": "",
        "universe_source_actual": source,
    }
    log(f"[universe] symbols={len(symbols)} source={source} index={INDEX_CODE}")

    stock_basic = load_or_fetch_stock_basic(pro, basic_path)
    st_df = load_or_fetch_namechange_st(pro, set(symbols), st_path)
    raw_panel = fetch_daily_market_panel(pro, symbols)
    dates = trade_dates(pro)
    raw_panel = build_full_calendar_panel(raw_panel, symbols, [parse_ymd(date).date() for date in dates])
    panel = add_qfq_prices(raw_panel)
    panel = apply_status_and_filters(panel, stock_basic, st_df)
    panel = apply_component_membership(panel, component_df, universe_meta)
    panel = panel.with_columns(
        (pl.col("eligible_research_row") & pl.col("is_index_component")).alias("eligible_component_row")
    )
    benchmark = fetch_benchmark(pro)
    failed = sorted(set(symbols) - set(panel.filter(pl.col("raw_close").is_not_null())["symbol"].unique().to_list()))
    summary = summarize(panel, benchmark, failed, universe_meta)
    summary["price_source"] = "tushare_daily_by_trade_date"
    summary["st_source"] = "tushare_namechange_best_effort"

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
