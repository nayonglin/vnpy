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


BASE_DIR: Path = Path(__file__).resolve().parent
NATIVE_RESULTS_DIR: Path = BASE_DIR / "native_results"
DEFAULT_PANEL_DIRS: list[Path] = [
    NATIVE_RESULTS_DIR / "stock_range_reversion_cache_tushare_daily_2018_2020",
    NATIVE_RESULTS_DIR / "stock_range_reversion_cache_tushare_daily_2021",
    NATIVE_RESULTS_DIR / "stock_range_reversion_cache_tushare_daily_2022",
    NATIVE_RESULTS_DIR / "stock_range_reversion_cache_tushare_daily_2023",
    NATIVE_RESULTS_DIR / "stock_range_reversion_cache_tushare_daily_2024",
    NATIVE_RESULTS_DIR / "stock_range_reversion_cache_tushare_daily_2025_2026",
]

OUTPUT_DIR: Path = Path(
    os.getenv(
        "OUTPUT_DIR",
        str(NATIVE_RESULTS_DIR / "stock_range_reversion_layer_tags_tushare_2018_2026"),
    )
).expanduser().resolve()

PANEL_DIRS_ENV: str = os.getenv("PANEL_DIRS", "").strip()
PANEL_DIRS: list[Path] = (
    [Path(item).expanduser().resolve() for item in PANEL_DIRS_ENV.split(",") if item.strip()]
    if PANEL_DIRS_ENV
    else DEFAULT_PANEL_DIRS
)

TUSHARE_RETRIES: int = int(os.getenv("TUSHARE_RETRIES", "8") or 1)
TUSHARE_RETRY_SLEEP: float = float(os.getenv("TUSHARE_RETRY_SLEEP", "90") or 0.0)
TUSHARE_CALL_SLEEP_SECONDS: float = float(os.getenv("TUSHARE_CALL_SLEEP_SECONDS", "2.5") or 0.0)
TUSHARE_DATE_SLEEP_SECONDS: float = float(os.getenv("TUSHARE_DATE_SLEEP_SECONDS", "0.5") or 0.0)
REFRESH: bool = os.getenv("REFRESH", "0").strip() == "1"
BASIC_REFRESH: bool = os.getenv("BASIC_REFRESH", "0").strip() == "1"
DAILY_BASIC_CACHE_REFRESH: bool = os.getenv("DAILY_BASIC_CACHE_REFRESH", "0").strip() == "1"
MAX_DATES: int = int(os.getenv("MAX_DATES", "0") or 0)
N_GROUPS: int = int(os.getenv("N_GROUPS", "5") or 5)
DAILY_BASIC_FETCH_MODE: str = os.getenv("DAILY_BASIC_FETCH_MODE", "date").strip().lower()

DAILY_BASIC_FIELDS: str = ",".join(
    [
        "ts_code",
        "trade_date",
        "close",
        "turnover_rate",
        "turnover_rate_f",
        "volume_ratio",
        "pe",
        "pe_ttm",
        "pb",
        "ps",
        "ps_ttm",
        "dv_ratio",
        "dv_ttm",
        "total_share",
        "float_share",
        "free_share",
        "total_mv",
        "circ_mv",
    ]
)

STOCK_BASIC_FIELDS: str = ",".join(
    [
        "ts_code",
        "symbol",
        "name",
        "area",
        "industry",
        "market",
        "exchange",
        "curr_type",
        "list_status",
        "list_date",
        "delist_date",
        "is_hs",
        "act_name",
        "act_ent_type",
    ]
)


def log(message: str) -> None:
    """Print one progress line immediately."""
    print(message, flush=True)


def get_pro() -> Any:
    """Create a Tushare Pro client."""
    token = os.getenv("TUSHARE_TOKEN", "").strip()
    if not token:
        raise RuntimeError("TUSHARE_TOKEN is missing")
    return ts.pro_api(token)


def ts_code_to_symbol(ts_code: str) -> str:
    """Convert a Tushare code like 000001.SZ to 000001."""
    return str(ts_code).split(".")[0]


def vt_symbol_to_ts_code(vt_symbol: str) -> str:
    """Convert a vn.py vt_symbol into Tushare ts_code."""
    symbol, exchange = str(vt_symbol).split(".")
    if exchange == "SSE":
        return f"{symbol}.SH"
    if exchange == "SZSE":
        return f"{symbol}.SZ"
    if exchange == "BSE":
        return f"{symbol}.BJ"
    raise ValueError(f"Unsupported vt_symbol exchange: {vt_symbol}")


def call_with_retry(name: str, func: Any, **kwargs: Any) -> pd.DataFrame:
    """Call one Tushare endpoint with retry and pacing."""
    last_error: Exception | None = None
    for attempt in range(1, TUSHARE_RETRIES + 1):
        try:
            data = func(**kwargs)
            if TUSHARE_CALL_SLEEP_SECONDS:
                time.sleep(TUSHARE_CALL_SLEEP_SECONDS)
            return data
        except Exception as exc:
            last_error = exc
            log(f"[tushare] retry {attempt}/{TUSHARE_RETRIES} failed {name}: {exc}")
            if attempt < TUSHARE_RETRIES and TUSHARE_RETRY_SLEEP:
                time.sleep(TUSHARE_RETRY_SLEEP)
    raise RuntimeError(f"Tushare call failed after retries: {name}: {last_error}")


def load_panel_rows() -> pl.DataFrame:
    """Load the minimum rows needed for layer-tag joins and audits."""
    frames: list[pl.DataFrame] = []
    needed = [
        "datetime",
        "symbol",
        "vt_symbol",
        "turnover",
        "adv20_turnover",
        "volume",
        "adv20_volume",
        "eligible_research_row",
        "is_index_component",
        "eligible_component_row",
    ]
    for panel_dir in PANEL_DIRS:
        panel_path = panel_dir / "stock_range_reversion_research_panel.parquet"
        if not panel_path.exists():
            raise FileNotFoundError(f"missing panel: {panel_path}")
        schema = pl.scan_parquet(panel_path).collect_schema()
        columns = [col for col in needed if col in schema.names()]
        frame = pl.read_parquet(panel_path, columns=columns)
        for col in needed:
            if col not in frame.columns:
                dtype = pl.Boolean if col.startswith("is_") or col.startswith("eligible_") else pl.Float64
                if col in {"datetime"}:
                    dtype = pl.Date
                if col in {"symbol", "vt_symbol"}:
                    dtype = pl.String
                frame = frame.with_columns(pl.lit(None, dtype=dtype).alias(col))
        frames.append(frame.select(needed))
    return pl.concat(frames, how="vertical").unique(["datetime", "symbol"]).sort(["datetime", "symbol"])


def fetch_stock_basic(pro: Any, path: Path) -> pl.DataFrame:
    """Fetch static stock tags such as industry, market, and area."""
    if path.exists() and not BASIC_REFRESH:
        return pl.read_parquet(path)

    frames: list[pd.DataFrame] = []
    for status in ["L", "D", "P"]:
        df = call_with_retry(
            f"stock_basic_{status}",
            pro.stock_basic,
            exchange="",
            list_status=status,
            fields=STOCK_BASIC_FIELDS,
        )
        if df is not None and not df.empty:
            frames.append(df)
    if not frames:
        raise RuntimeError("Tushare stock_basic returned no rows")

    out = (
        pl.from_pandas(pd.concat(frames, ignore_index=True))
        .with_columns(
            pl.col("ts_code").cast(pl.String),
            pl.col("symbol").cast(pl.String),
            pl.col("name").cast(pl.String).alias("stock_name"),
            pl.col("area").cast(pl.String),
            pl.col("industry").cast(pl.String),
            pl.col("market").cast(pl.String),
            pl.col("exchange").cast(pl.String),
            pl.col("curr_type").cast(pl.String),
            pl.col("list_status").cast(pl.String),
            pl.col("list_date").str.strptime(pl.Date, "%Y%m%d", strict=False),
            pl.col("delist_date").str.strptime(pl.Date, "%Y%m%d", strict=False),
            pl.col("is_hs").cast(pl.String),
            pl.col("act_name").cast(pl.String),
            pl.col("act_ent_type").cast(pl.String),
        )
        .select(
            [
                "symbol",
                "ts_code",
                "stock_name",
                "area",
                "industry",
                "market",
                "exchange",
                "curr_type",
                "list_status",
                "list_date",
                "delist_date",
                "is_hs",
                "act_name",
                "act_ent_type",
            ]
        )
        .unique("symbol")
        .sort("symbol")
    )
    out.write_parquet(path)
    return out


def daily_basic_cache_dir() -> Path:
    """Return cache directory for per-date daily_basic data."""
    return OUTPUT_DIR / "tushare_daily_basic_cache"


def daily_basic_symbol_cache_dir() -> Path:
    """Return cache directory for per-symbol daily_basic data."""
    return OUTPUT_DIR / "tushare_daily_basic_symbol_cache"


def fetch_one_daily_basic(pro: Any, trade_date: str, symbols: set[str], cache_dir: Path) -> pl.DataFrame:
    """Fetch one trade_date's daily_basic rows and cache them."""
    path = cache_dir / f"{trade_date}.parquet"
    if path.exists() and not DAILY_BASIC_CACHE_REFRESH:
        return pl.read_parquet(path)

    df = call_with_retry(
        f"daily_basic_{trade_date}",
        pro.daily_basic,
        trade_date=trade_date,
        fields=DAILY_BASIC_FIELDS,
    )
    if df is None or df.empty:
        out = empty_daily_basic_frame()
        out.write_parquet(path)
        return out

    pdf = df.copy()
    pdf["symbol"] = pdf["ts_code"].astype(str).str.split(".").str[0]
    pdf = pdf[pdf["symbol"].isin(symbols)]
    if pdf.empty:
        out = empty_daily_basic_frame()
        out.write_parquet(path)
        return out

    out = pl.from_pandas(pdf).with_columns(
        pl.col("trade_date").str.strptime(pl.Date, "%Y%m%d", strict=False).alias("datetime"),
        pl.col("symbol").cast(pl.String),
        pl.col("ts_code").cast(pl.String),
        *[
            pl.col(col).cast(pl.Float64, strict=False)
            for col in [
                "close",
                "turnover_rate",
                "turnover_rate_f",
                "volume_ratio",
                "pe",
                "pe_ttm",
                "pb",
                "ps",
                "ps_ttm",
                "dv_ratio",
                "dv_ttm",
                "total_share",
                "float_share",
                "free_share",
                "total_mv",
                "circ_mv",
            ]
            if col in pdf.columns
        ],
    )
    out = out.select(empty_daily_basic_frame().columns)
    out.write_parquet(path)
    return out


def fetch_one_daily_basic_symbol(pro: Any, ts_code: str, start_date: str, end_date: str, cache_dir: Path) -> pl.DataFrame:
    """Fetch one symbol's daily_basic history and cache it."""
    path = cache_dir / f"{ts_code}_{start_date}_{end_date}.parquet"
    if path.exists() and not DAILY_BASIC_CACHE_REFRESH:
        return pl.read_parquet(path)

    df = call_with_retry(
        f"daily_basic_{ts_code}",
        pro.daily_basic,
        ts_code=ts_code,
        start_date=start_date,
        end_date=end_date,
        fields=DAILY_BASIC_FIELDS,
    )
    if df is None or df.empty:
        out = empty_daily_basic_frame()
        out.write_parquet(path)
        return out

    pdf = df.copy()
    pdf["symbol"] = pdf["ts_code"].astype(str).str.split(".").str[0]
    out = pl.from_pandas(pdf).with_columns(
        pl.col("trade_date").str.strptime(pl.Date, "%Y%m%d", strict=False).alias("datetime"),
        pl.col("symbol").cast(pl.String),
        pl.col("ts_code").cast(pl.String),
        *[
            pl.col(col).cast(pl.Float64, strict=False)
            for col in [
                "close",
                "turnover_rate",
                "turnover_rate_f",
                "volume_ratio",
                "pe",
                "pe_ttm",
                "pb",
                "ps",
                "ps_ttm",
                "dv_ratio",
                "dv_ttm",
                "total_share",
                "float_share",
                "free_share",
                "total_mv",
                "circ_mv",
            ]
            if col in pdf.columns
        ],
    )
    out = out.select(empty_daily_basic_frame().columns)
    out.write_parquet(path)
    return out


def empty_daily_basic_frame() -> pl.DataFrame:
    """Return an empty frame with the daily_basic schema."""
    return pl.DataFrame(
        schema={
            "datetime": pl.Date,
            "symbol": pl.String,
            "ts_code": pl.String,
            "close": pl.Float64,
            "turnover_rate": pl.Float64,
            "turnover_rate_f": pl.Float64,
            "volume_ratio": pl.Float64,
            "pe": pl.Float64,
            "pe_ttm": pl.Float64,
            "pb": pl.Float64,
            "ps": pl.Float64,
            "ps_ttm": pl.Float64,
            "dv_ratio": pl.Float64,
            "dv_ttm": pl.Float64,
            "total_share": pl.Float64,
            "float_share": pl.Float64,
            "free_share": pl.Float64,
            "total_mv": pl.Float64,
            "circ_mv": pl.Float64,
        }
    )


def fetch_daily_basic_panel(pro: Any, dates: list[Any], symbols: set[str], path: Path) -> pl.DataFrame:
    """Fetch or load the full daily_basic panel."""
    if path.exists() and not REFRESH:
        return pl.read_parquet(path)

    cache_dir = daily_basic_cache_dir()
    cache_dir.mkdir(parents=True, exist_ok=True)

    trade_dates = [date.strftime("%Y%m%d") for date in dates]
    if MAX_DATES:
        trade_dates = trade_dates[:MAX_DATES]

    frames: list[pl.DataFrame] = []
    for index, trade_date in enumerate(trade_dates, start=1):
        log(f"[daily_basic] {index}/{len(trade_dates)} {trade_date}")
        frame = fetch_one_daily_basic(pro, trade_date, symbols, cache_dir)
        if not frame.is_empty():
            frames.append(frame)
        if TUSHARE_DATE_SLEEP_SECONDS:
            time.sleep(TUSHARE_DATE_SLEEP_SECONDS)

    out = pl.concat(frames, how="vertical") if frames else empty_daily_basic_frame()
    out = out.unique(["datetime", "symbol"]).sort(["datetime", "symbol"])
    out.write_parquet(path)
    return out


def fetch_daily_basic_panel_by_symbol(pro: Any, panel_rows: pl.DataFrame, path: Path) -> pl.DataFrame:
    """Fetch or load daily_basic panel by symbol, useful for smaller custom universes."""
    if path.exists() and not REFRESH:
        return pl.read_parquet(path)

    cache_dir = daily_basic_symbol_cache_dir()
    cache_dir.mkdir(parents=True, exist_ok=True)

    symbol_map = (
        panel_rows.select(["symbol", "vt_symbol"])
        .drop_nulls(["symbol", "vt_symbol"])
        .unique("symbol")
        .with_columns(pl.col("vt_symbol").map_elements(vt_symbol_to_ts_code, return_dtype=pl.String).alias("ts_code"))
        .sort("ts_code")
    )
    ts_codes = symbol_map["ts_code"].to_list()
    start_date = panel_rows["datetime"].min().strftime("%Y%m%d")
    end_date = panel_rows["datetime"].max().strftime("%Y%m%d")

    frames: list[pl.DataFrame] = []
    for index, ts_code in enumerate(ts_codes, start=1):
        log(f"[daily_basic_symbol] {index}/{len(ts_codes)} {ts_code}")
        frame = fetch_one_daily_basic_symbol(pro, ts_code, start_date, end_date, cache_dir)
        if not frame.is_empty():
            frames.append(frame)
        if TUSHARE_DATE_SLEEP_SECONDS:
            time.sleep(TUSHARE_DATE_SLEEP_SECONDS)

    out = pl.concat(frames, how="vertical") if frames else empty_daily_basic_frame()
    out = out.unique(["datetime", "symbol"]).sort(["datetime", "symbol"])
    out.write_parquet(path)
    return out


def add_quantile_bucket(df: pl.DataFrame, column: str, bucket_col: str) -> pl.DataFrame:
    """Add same-day cross-sectional ordinal quantile bucket; 1 is low, N_GROUPS is high."""
    if column not in df.columns:
        return df.with_columns(pl.lit(None, dtype=pl.Int64).alias(bucket_col))

    return (
        df.with_columns(
            pl.when(pl.col(column).is_not_null() & pl.col(column).is_finite())
            .then(pl.col(column).rank("ordinal").over("datetime"))
            .otherwise(None)
            .alias(f"_{bucket_col}_rank"),
            pl.col(column).is_not_null().sum().over("datetime").alias(f"_{bucket_col}_n"),
        )
        .with_columns(
            pl.when(pl.col(f"_{bucket_col}_rank").is_null() | (pl.col(f"_{bucket_col}_n") <= 0))
            .then(None)
            .otherwise(
                ((((pl.col(f"_{bucket_col}_rank") - 1) * N_GROUPS) / pl.col(f"_{bucket_col}_n"))
                .floor()
                .cast(pl.Int64)
                + 1)
                .clip(1, N_GROUPS)
            )
            .alias(bucket_col)
        )
        .drop([f"_{bucket_col}_rank", f"_{bucket_col}_n"])
    )


def build_layer_tags(panel_rows: pl.DataFrame, daily_basic: pl.DataFrame, stock_basic: pl.DataFrame) -> pl.DataFrame:
    """Join static and time-series layer tags onto the research symbol-date grid."""
    daily_basic = daily_basic.rename(
        {
            "close": "basic_close",
            "turnover_rate": "basic_turnover_rate",
        }
    )
    tags = (
        panel_rows.join(daily_basic, on=["datetime", "symbol"], how="left")
        .join(stock_basic, on="symbol", how="left")
        .with_columns(
            pl.col("ts_code").is_not_null().alias("has_daily_basic"),
            (pl.col("turnover") / 100_000_000.0).alias("turnover_yuan_100m"),
            (pl.col("adv20_turnover") / 100_000_000.0).alias("adv20_turnover_yuan_100m"),
        )
    )
    for column, bucket in [
        ("circ_mv", "circ_mv_q"),
        ("total_mv", "total_mv_q"),
        ("free_share", "free_share_q"),
        ("basic_turnover_rate", "turnover_rate_q"),
        ("turnover_rate_f", "turnover_rate_f_q"),
        ("pb", "pb_q"),
        ("pe_ttm", "pe_ttm_q"),
        ("adv20_turnover_yuan_100m", "adv20_turnover_q"),
    ]:
        tags = add_quantile_bucket(tags, column, bucket)
    return tags.sort(["datetime", "symbol"])


def summarize(tags: pl.DataFrame, stock_basic: pl.DataFrame, daily_basic: pl.DataFrame) -> dict[str, Any]:
    """Build JSON-friendly coverage summary."""
    eligible = tags.filter(pl.col("eligible_component_row").fill_null(False))
    summary: dict[str, Any] = {
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "output_dir": str(OUTPUT_DIR),
        "panel_dirs": [str(path) for path in PANEL_DIRS],
        "date_min": str(tags["datetime"].min()),
        "date_max": str(tags["datetime"].max()),
        "tag_rows": tags.height,
        "symbol_count": tags["symbol"].n_unique(),
        "date_count": tags["datetime"].n_unique(),
        "daily_basic_rows": daily_basic.height,
        "stock_basic_rows": stock_basic.height,
        "has_daily_basic_rows": int(tags["has_daily_basic"].sum()),
        "has_daily_basic_ratio": float(tags["has_daily_basic"].mean()),
        "eligible_component_rows": eligible.height,
        "eligible_component_daily_basic_rows": int(eligible["has_daily_basic"].sum()) if eligible.height else 0,
        "eligible_component_daily_basic_ratio": float(eligible["has_daily_basic"].mean()) if eligible.height else 0.0,
        "industry_non_null_rows": int(tags["industry"].is_not_null().sum()),
        "industry_non_null_ratio": float(tags["industry"].is_not_null().mean()),
        "market_non_null_rows": int(tags["market"].is_not_null().sum()),
        "market_non_null_ratio": float(tags["market"].is_not_null().mean()),
        "known_limitations": [
            "stock_basic industry is a static Tushare tag and may not represent historical industry changes.",
            "daily_basic is used as same-date layer metadata for attribution; no trading rule is created here.",
            "Layer buckets are same-day cross-sectional quintiles over the research grid, not optimized thresholds.",
        ],
    }
    for col in ["total_mv", "circ_mv", "turnover_rate_f", "pb", "pe_ttm", "free_share"]:
        summary[f"{col}_non_null_rows"] = int(tags[col].is_not_null().sum()) if col in tags.columns else 0
        summary[f"{col}_non_null_ratio"] = float(tags[col].is_not_null().mean()) if col in tags.columns else 0.0
    return summary


def build_daily_coverage(tags: pl.DataFrame) -> pl.DataFrame:
    """Summarize daily tag coverage."""
    return (
        tags.group_by("datetime")
        .agg(
            pl.len().alias("rows"),
            pl.col("has_daily_basic").sum().alias("daily_basic_rows"),
            pl.col("eligible_component_row").fill_null(False).sum().alias("eligible_component_rows"),
            (
                pl.col("has_daily_basic").cast(pl.Int64)
                * pl.col("eligible_component_row").fill_null(False).cast(pl.Int64)
            )
            .sum()
            .alias("eligible_component_daily_basic_rows"),
        )
        .with_columns(
            (pl.col("daily_basic_rows") / pl.col("rows")).alias("daily_basic_ratio"),
            (
                pl.col("eligible_component_daily_basic_rows")
                / pl.when(pl.col("eligible_component_rows") > 0).then(pl.col("eligible_component_rows")).otherwise(None)
            ).alias("eligible_component_daily_basic_ratio"),
        )
        .sort("datetime")
    )


def write_report(summary: dict[str, Any], paths: dict[str, Path]) -> Path:
    """Write a concise Chinese report for the layer tag build."""
    report_path = OUTPUT_DIR / "stock_range_reversion_layer_tags_report.md"
    lines = [
        "# 股票震荡分层标签数据报告",
        "",
        f"- 生成时间：`{summary['created_at']}`",
        f"- 日期范围：`{summary['date_min']}`到`{summary['date_max']}`",
        f"- 标签行数：`{summary['tag_rows']:,}`，股票数：`{summary['symbol_count']:,}`，交易日：`{summary['date_count']:,}`",
        f"- daily_basic 覆盖：`{summary['has_daily_basic_rows']:,}`行，占比`{summary['has_daily_basic_ratio']:.2%}`",
        f"- 成分内可研究行 daily_basic 覆盖：`{summary['eligible_component_daily_basic_rows']:,}`/`{summary['eligible_component_rows']:,}`，占比`{summary['eligible_component_daily_basic_ratio']:.2%}`",
        f"- 行业标签非空：`{summary['industry_non_null_rows']:,}`行，占比`{summary['industry_non_null_ratio']:.2%}`",
        f"- 市场板块标签非空：`{summary['market_non_null_rows']:,}`行，占比`{summary['market_non_null_ratio']:.2%}`",
        "",
        "## 核心字段覆盖",
        "",
    ]
    for col in ["total_mv", "circ_mv", "turnover_rate_f", "pb", "pe_ttm", "free_share"]:
        lines.append(
            f"- `{col}`：`{summary[f'{col}_non_null_rows']:,}`行，占比`{summary[f'{col}_non_null_ratio']:.2%}`"
        )
    lines.extend(
        [
            "",
            "## 输出文件",
            "",
        ]
    )
    for name, path in paths.items():
        lines.append(f"- `{name}`：`{path}`")
    lines.extend(
        [
            "",
            "## 已知限制",
            "",
        ]
    )
    for item in summary["known_limitations"]:
        lines.append(f"- {item}")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path


def main() -> None:
    """Build Tushare daily_basic and stock_basic layer tags for stock range research."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    daily_basic_path = OUTPUT_DIR / "stock_range_reversion_daily_basic.parquet"
    stock_basic_path = OUTPUT_DIR / "stock_range_reversion_stock_basic_layer.parquet"
    tag_path = OUTPUT_DIR / "stock_range_reversion_layer_tags.parquet"
    daily_coverage_path = OUTPUT_DIR / "stock_range_reversion_layer_tags_daily_coverage.csv"
    summary_path = OUTPUT_DIR / "stock_range_reversion_layer_tags_summary.json"

    panel_rows = load_panel_rows()
    dates = panel_rows.select("datetime").unique().sort("datetime")["datetime"].to_list()
    symbols = set(panel_rows["symbol"].unique().to_list())

    pro = get_pro()
    stock_basic = fetch_stock_basic(pro, stock_basic_path)
    if DAILY_BASIC_FETCH_MODE == "symbol":
        daily_basic = fetch_daily_basic_panel_by_symbol(pro, panel_rows, daily_basic_path)
    elif DAILY_BASIC_FETCH_MODE == "date":
        daily_basic = fetch_daily_basic_panel(pro, dates, symbols, daily_basic_path)
    else:
        raise ValueError(f"Unsupported DAILY_BASIC_FETCH_MODE: {DAILY_BASIC_FETCH_MODE}")
    tags = build_layer_tags(panel_rows, daily_basic, stock_basic)
    daily_coverage = build_daily_coverage(tags)
    summary = summarize(tags, stock_basic, daily_basic)

    tags.write_parquet(tag_path)
    daily_coverage.write_csv(daily_coverage_path)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    report_path = write_report(
        summary,
        {
            "daily_basic": daily_basic_path,
            "stock_basic_layer": stock_basic_path,
            "layer_tags": tag_path,
            "daily_coverage": daily_coverage_path,
            "summary": summary_path,
        },
    )
    log(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    log(f"report={report_path}")


if __name__ == "__main__":
    main()
