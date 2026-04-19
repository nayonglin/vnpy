from __future__ import annotations

import os
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

import akshare as ak
import baostock as bs
import pandas as pd
import polars as pl


START_DATE: str = "2025-01-01"
END_DATE: str = "2026-04-17"
HOLDING_DAYS: int = 5
INDEX_CODE: str = "000852"          # CSI 1000
BENCHMARK_CODE: str = "sh.000852"
OUTPUT_DIR: Path = Path(__file__).resolve().parent / "public_results"
MAX_SYMBOLS: int | None = int(os.getenv("MAX_SYMBOLS", "0")) or None


def round_half_up(value: float) -> float:
    """Round to 2 decimals using exchange-like half-up behavior."""
    return float(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def get_limit_ratio(symbol: str, date_str: str, is_st: bool) -> float:
    """Infer daily price limit ratio from board rules and ST status."""
    if is_st:
        return 0.05

    if symbol.startswith(("8", "4")):
        return 0.30

    trade_date = datetime.strptime(date_str, "%Y-%m-%d").date()

    if symbol.startswith("688"):
        return 0.20

    if symbol.startswith(("300", "301")):
        reform_date = datetime(2020, 8, 24).date()
        return 0.20 if trade_date >= reform_date else 0.10

    return 0.10


def fetch_constituents() -> list[str]:
    """Fetch latest CSI 1000 constituents from CSIndex."""
    cons = ak.index_stock_cons_csindex(symbol=INDEX_CODE)
    codes = cons["成分券代码"].astype(str).tolist()
    codes = sorted(set(codes))
    if MAX_SYMBOLS is not None:
        codes = codes[:MAX_SYMBOLS]
    return codes


def fetch_stock_history(symbol: str) -> pd.DataFrame:
    """Fetch raw daily data for one stock from baostock."""
    bs_symbol = ("sh." if symbol.startswith("6") else "sz.") + symbol
    rs = bs.query_history_k_data_plus(
        bs_symbol,
        "date,code,open,high,low,close,preclose,volume,amount,turn,pctChg,tradestatus,isST",
        start_date=START_DATE,
        end_date=END_DATE,
        frequency="d",
        adjustflag="3",
    )

    rows: list[list[str]] = []
    while rs.error_code == "0" and rs.next():
        rows.append(rs.get_row_data())

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows, columns=rs.fields)
    return df


def fetch_benchmark() -> pl.DataFrame:
    """Fetch CSI 1000 index daily close from baostock."""
    rs = bs.query_history_k_data_plus(
        BENCHMARK_CODE,
        "date,code,open,high,low,close,preclose,volume,amount,pctChg",
        start_date=START_DATE,
        end_date=END_DATE,
        frequency="d",
        adjustflag="3",
    )

    rows: list[list[str]] = []
    while rs.error_code == "0" and rs.next():
        rows.append(rs.get_row_data())

    df = pd.DataFrame(rows, columns=rs.fields)
    return pl.from_pandas(df).with_columns(
        pl.col("date").str.strptime(pl.Date, "%Y-%m-%d").alias("datetime"),
        pl.col("close").cast(pl.Float64),
    ).select(["datetime", "close"])


def build_stock_panel(symbols: list[str]) -> pl.DataFrame:
    """Download and normalize current CSI 1000 constituent daily data."""
    frames: list[pd.DataFrame] = []

    for i, symbol in enumerate(symbols, start=1):
        if i % 100 == 0:
            print(f"downloaded {i}/{len(symbols)} symbols", flush=True)

        pdf = fetch_stock_history(symbol)
        if pdf.empty:
            continue

        pdf["symbol"] = symbol
        frames.append(pdf)

    if not frames:
        raise RuntimeError("No stock data downloaded")

    raw = pd.concat(frames, ignore_index=True)
    df = pl.from_pandas(raw)

    numeric_cols: list[str] = [
        "open",
        "high",
        "low",
        "close",
        "preclose",
        "volume",
        "amount",
        "turn",
        "pctChg",
    ]

    df = df.with_columns(
        [pl.when(pl.col(col) == "").then(None).otherwise(pl.col(col)).alias(col) for col in numeric_cols]
    )

    df = df.with_columns(
        pl.col("date").str.strptime(pl.Date, "%Y-%m-%d").alias("datetime"),
        pl.col("symbol").alias("symbol"),
        pl.col("code").str.replace("^sh\\.", "").str.replace("^sz\\.", "").alias("code_str"),
        pl.col("open").cast(pl.Float64, strict=False),
        pl.col("high").cast(pl.Float64, strict=False),
        pl.col("low").cast(pl.Float64, strict=False),
        pl.col("close").cast(pl.Float64, strict=False),
        pl.col("preclose").cast(pl.Float64, strict=False),
        pl.col("volume").cast(pl.Float64, strict=False),
        pl.col("amount").cast(pl.Float64, strict=False).alias("turnover"),
        pl.col("turn").cast(pl.Float64, strict=False),
        pl.col("pctChg").cast(pl.Float64, strict=False),
        (pl.col("tradestatus") != "1").alias("is_suspended"),
        (pl.col("isST") == "1").alias("is_st"),
    ).select(
        [
            "datetime",
            "symbol",
            "code_str",
            "open",
            "high",
            "low",
            "close",
            "preclose",
            "volume",
            "turnover",
            "turn",
            "pctChg",
            "is_suspended",
            "is_st",
        ]
    )

    limit_rows: list[dict] = []
    for row in df.select(["datetime", "symbol", "preclose", "is_st"]).iter_rows(named=True):
        ratio = get_limit_ratio(row["symbol"], row["datetime"].strftime("%Y-%m-%d"), row["is_st"])
        up_limit = round_half_up(row["preclose"] * (1 + ratio))
        down_limit = round_half_up(row["preclose"] * (1 - ratio))
        limit_rows.append(
            {
                "datetime": row["datetime"],
                "symbol": row["symbol"],
                "up_limit": up_limit,
                "down_limit": down_limit,
            }
        )

    limit_df = pl.DataFrame(limit_rows)
    df = df.join(limit_df, on=["datetime", "symbol"], how="left")
    return df.sort(["symbol", "datetime"])


def prepare_labels(df: pl.DataFrame, benchmark_df: pl.DataFrame) -> pl.DataFrame:
    """Build real filters and future excess return label."""
    df = df.with_columns(
        pl.col("close").shift(-1).over("symbol").alias("entry_close"),
        pl.col("open").shift(-1).over("symbol").alias("entry_open"),
        pl.col("high").shift(-1).over("symbol").alias("entry_high"),
        pl.col("low").shift(-1).over("symbol").alias("entry_low"),
        pl.col("is_suspended").shift(-1).over("symbol").alias("entry_is_suspended"),
        pl.col("is_st").shift(-1).over("symbol").alias("entry_is_st"),
        pl.col("up_limit").shift(-1).over("symbol").alias("entry_up_limit"),
        pl.col("close").shift(-HOLDING_DAYS).over("symbol").alias("exit_close"),
        pl.col("open").shift(-HOLDING_DAYS).over("symbol").alias("exit_open"),
        pl.col("high").shift(-HOLDING_DAYS).over("symbol").alias("exit_high"),
        pl.col("low").shift(-HOLDING_DAYS).over("symbol").alias("exit_low"),
        pl.col("is_suspended").shift(-HOLDING_DAYS).over("symbol").alias("exit_is_suspended"),
        pl.col("down_limit").shift(-HOLDING_DAYS).over("symbol").alias("exit_down_limit"),
    )

    df = df.with_columns(
        (~pl.col("entry_is_suspended").fill_null(True)).alias("pass_suspend_entry"),
        (~pl.col("exit_is_suspended").fill_null(True)).alias("pass_suspend_exit"),
        ((~pl.col("is_st").fill_null(True)) & (~pl.col("entry_is_st").fill_null(True))).alias("pass_st"),
        (
            (
                (pl.col("entry_open") == pl.col("entry_high"))
                & (pl.col("entry_high") == pl.col("entry_low"))
                & (pl.col("entry_low") == pl.col("entry_close"))
                & (pl.col("entry_close") >= pl.col("entry_up_limit") - 0.005)
            )
            .fill_null(True)
        ).alias("entry_oneword_limit_up"),
        (
            (
                (pl.col("exit_open") == pl.col("exit_high"))
                & (pl.col("exit_high") == pl.col("exit_low"))
                & (pl.col("exit_low") == pl.col("exit_close"))
                & (pl.col("exit_close") <= pl.col("exit_down_limit") + 0.005)
            )
            .fill_null(True)
        ).alias("exit_oneword_limit_down"),
    ).with_columns(
        (~pl.col("entry_oneword_limit_up")).alias("pass_limit_entry"),
        (~pl.col("exit_oneword_limit_down")).alias("pass_limit_exit"),
        (pl.col("exit_close") / pl.col("entry_close") - 1).alias("ret_5"),
    )

    bm = benchmark_df.sort("datetime").with_columns(
        pl.col("close").shift(-1).alias("bm_entry_close"),
        pl.col("close").shift(-HOLDING_DAYS).alias("bm_exit_close"),
    ).with_columns(
        (pl.col("bm_exit_close") / pl.col("bm_entry_close") - 1).alias("bm_ret_5")
    ).select(["datetime", "bm_ret_5"])

    df = df.join(bm, on="datetime", how="left").with_columns(
        (pl.col("ret_5") - pl.col("bm_ret_5")).alias("excess_ret_5"),
    )

    df = df.with_columns(
        (
            pl.col("pass_suspend_entry")
            & pl.col("pass_suspend_exit")
            & pl.col("pass_st")
            & pl.col("pass_limit_entry")
            & pl.col("pass_limit_exit")
            & pl.col("ret_5").is_not_null()
            & pl.col("excess_ret_5").is_not_null()
            & (pl.col("volume") > 0)
            & (pl.col("turnover") > 0)
        ).alias("final_keep")
    )
    return df


def add_factors(df: pl.DataFrame) -> pl.DataFrame:
    """Create basic volume factors."""
    df = df.with_columns(
        pl.col("volume").shift(1).over("symbol").alias("volume_lag_1"),
        pl.col("volume").shift(5).over("symbol").alias("volume_lag_5"),
        pl.col("volume").rolling_mean(5).over("symbol").alias("volume_ma_5"),
        pl.col("volume").rolling_mean(20).over("symbol").alias("volume_ma_20"),
        pl.col("turnover").rolling_mean(20).over("symbol").alias("turnover_ma_20"),
        pl.col("close").shift(1).over("symbol").alias("close_lag_1"),
    ).with_columns(
        (pl.col("volume") / pl.col("volume_ma_5")).alias("vol_ratio_5"),
        (pl.col("volume") / pl.col("volume_ma_20")).alias("vol_ratio_20"),
        (pl.col("volume") / pl.col("volume_lag_1") - 1).alias("vol_chg_1"),
        (pl.col("volume") / pl.col("volume_lag_5") - 1).alias("vol_chg_5"),
        (pl.col("turnover") / pl.col("turnover_ma_20")).alias("turnover_ratio_20"),
        (pl.col("close") / pl.col("close_lag_1") - 1).alias("ret_1"),
    ).with_columns(
        (pl.col("ret_1") * pl.col("vol_chg_1")).alias("price_vol_sync_1"),
        (pl.col("ret_1").abs() * pl.col("vol_ratio_20")).alias("vol_price_pressure"),
    )
    return df


def add_quantile_groups(df: pl.DataFrame, factor_col: str, n_groups: int = 5) -> pl.DataFrame:
    """Assign daily cross-sectional groups."""
    return df.with_columns(
        pl.col(factor_col).rank("ordinal").over("datetime").alias("_rank"),
        pl.len().over("datetime").alias("_n"),
    ).with_columns(
        ((((pl.col("_rank") - 1) * n_groups) / pl.col("_n")).floor().cast(pl.Int64) + 1)
        .clip(1, n_groups)
        .alias("group")
    ).drop(["_rank", "_n"])


def evaluate_factor(df: pl.DataFrame, factor_col: str) -> tuple[dict, pl.DataFrame]:
    """Calculate Rank IC and quintile long-short summary."""
    work = df.filter(
        pl.col("final_keep")
        & pl.col(factor_col).is_not_null()
        & pl.col("excess_ret_5").is_not_null()
    )

    ic_df = work.with_columns(
        pl.col(factor_col).rank("average").over("datetime").alias("factor_rank"),
        pl.col("excess_ret_5").rank("average").over("datetime").alias("label_rank"),
    ).group_by("datetime").agg(
        pl.len().alias("n"),
        pl.corr("factor_rank", "label_rank").alias("rank_ic"),
    ).filter(pl.col("n") >= 50).sort("datetime")

    grouped = add_quantile_groups(work, factor_col, 5).group_by(["datetime", "group"]).agg(
        pl.col("excess_ret_5").mean().alias("group_ret"),
        pl.len().alias("stock_count"),
    ).sort(["datetime", "group"])

    top_df = grouped.filter(pl.col("group") == 5).select(["datetime", pl.col("group_ret").alias("top_ret")])
    bottom_df = grouped.filter(pl.col("group") == 1).select(["datetime", pl.col("group_ret").alias("bottom_ret")])
    ls_df = top_df.join(bottom_df, on="datetime", how="inner").with_columns(
        (pl.col("top_ret") - pl.col("bottom_ret")).alias("ls_ret")
    ).with_columns(
        (pl.col("ls_ret") + 1).cum_prod().sub(1).alias("ls_cum_ret")
    ).sort("datetime")

    summary = {
        "factor": factor_col,
        "sample_days": int(ic_df.height),
        "ic_mean": float(ic_df["rank_ic"].mean()),
        "ic_std": float(ic_df["rank_ic"].std()),
        "ic_ir": float(ic_df["rank_ic"].mean() / ic_df["rank_ic"].std()) if ic_df["rank_ic"].std() else 0.0,
        "ic_positive_ratio": float((ic_df["rank_ic"] > 0).mean()),
        "ls_mean": float(ls_df["ls_ret"].mean()),
        "ls_std": float(ls_df["ls_ret"].std()),
        "ls_ir": float(ls_df["ls_ret"].mean() / ls_df["ls_ret"].std()) if ls_df["ls_ret"].std() else 0.0,
        "ls_cum_ret_last": float(ls_df["ls_cum_ret"][-1]) if ls_df.height else 0.0,
    }
    return summary, grouped


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    symbols = fetch_constituents()
    print(f"constituents: {len(symbols)}", flush=True)

    login_result = bs.login()
    if login_result.error_code != "0":
        raise RuntimeError(f"baostock login failed: {login_result.error_msg}")

    try:
        stock_df = build_stock_panel(symbols)
        benchmark_df = fetch_benchmark()
    finally:
        bs.logout()

    labeled_df = prepare_labels(stock_df, benchmark_df)
    factor_df = add_factors(labeled_df)

    factor_cols = [
        "vol_ratio_5",
        "vol_ratio_20",
        "vol_chg_1",
        "vol_chg_5",
        "turnover_ratio_20",
        "price_vol_sync_1",
        "vol_price_pressure",
    ]

    summaries: list[dict] = []
    for factor in factor_cols:
        summary, grouped = evaluate_factor(factor_df, factor)
        summaries.append(summary)
        grouped.write_csv(OUTPUT_DIR / f"{factor}_grouped.csv")

    summary_df = pl.DataFrame(summaries).sort("ic_mean", descending=True)
    summary_df.write_csv(OUTPUT_DIR / "factor_summary.csv")

    sample_stats = factor_df.select(
        pl.len().alias("raw_rows"),
        pl.col("symbol").n_unique().alias("symbol_count"),
        pl.col("datetime").n_unique().alias("trade_days"),
        pl.col("final_keep").sum().alias("kept_rows"),
        pl.col("pass_suspend_entry").sum().alias("pass_suspend_entry_rows"),
        pl.col("pass_st").sum().alias("pass_st_rows"),
        pl.col("pass_limit_entry").sum().alias("pass_limit_entry_rows"),
        pl.col("pass_limit_exit").sum().alias("pass_limit_exit_rows"),
    )
    sample_stats.write_csv(OUTPUT_DIR / "sample_stats.csv")

    print("sample_stats", flush=True)
    print(sample_stats, flush=True)
    print("factor_summary", flush=True)
    print(summary_df, flush=True)


if __name__ == "__main__":
    main()
