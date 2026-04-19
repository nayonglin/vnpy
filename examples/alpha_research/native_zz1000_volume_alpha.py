from __future__ import annotations

import os
from pathlib import Path
from typing import Callable

import matplotlib
import numpy as np

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import baostock as bs
import polars as pl
from matplotlib.backends.backend_pdf import PdfPages

from vnpy.alpha import AlphaDataset, Segment
from vnpy.alpha.dataset import process_cs_rank_norm, process_fill_na
from vnpy.alpha.model.models.lasso_model import LassoModel

from public_zz1000_volume_research import (
    END_DATE,
    START_DATE,
    fetch_benchmark,
    fetch_constituents,
    build_stock_panel,
    prepare_labels,
)


OUTPUT_DIR: Path = Path(__file__).resolve().parent / "native_results"
CACHE_DIR: Path = OUTPUT_DIR / "cache"
MAX_SYMBOLS: int | None = int(os.getenv("MAX_SYMBOLS", "300")) or None
REFRESH_DATA: bool = os.getenv("REFRESH_DATA", "0") == "1"


FEATURE_NAMES: list[str] = [
    "vol_ratio_5",
    "vol_ratio_20",
    "vol_chg_1",
    "vol_chg_5",
    "turnover_ratio_20",
    "price_vol_sync_1",
    "vol_price_pressure",
]

MASK_FEATURE_NAME: str = "trade_mask"
MASK_SOURCE_NAME: str = "trade_mask_src"
LABEL_SOURCE_NAME: str = "future_label"


class VolumeAlphaDataset(AlphaDataset):
    """Native vnpy.alpha dataset for CSI1000 volume factor research."""

    def __init__(
        self,
        df: pl.DataFrame,
        train_period: tuple[str, str],
        valid_period: tuple[str, str],
        test_period: tuple[str, str],
    ) -> None:
        super().__init__(df, train_period, valid_period, test_period)

        self.add_feature("vol_ratio_5", "volume / ts_mean(volume, 5)")
        self.add_feature("vol_ratio_20", "volume / ts_mean(volume, 20)")
        self.add_feature("vol_chg_1", "volume / ts_delay(volume, 1) - 1")
        self.add_feature("vol_chg_5", "volume / ts_delay(volume, 5) - 1")
        self.add_feature("turnover_ratio_20", "turnover / ts_mean(turnover, 20)")
        self.add_feature("price_vol_sync_1", "(close / ts_delay(close, 1) - 1) * (volume / ts_delay(volume, 1) - 1)")
        self.add_feature("vol_price_pressure", "abs(close / ts_delay(close, 1) - 1) * (volume / ts_mean(volume, 20))")
        self.add_feature(MASK_FEATURE_NAME, MASK_SOURCE_NAME)
        self.set_label(LABEL_SOURCE_NAME)


def save_figures(
    pdf: PdfPages,
    png_prefix: str,
    start_index: int,
) -> tuple[list[Path], int]:
    """Persist all current matplotlib figures and return saved file paths."""
    fig_nums = plt.get_fignums()
    saved_paths: list[Path] = []
    index = start_index

    for num in fig_nums:
        fig = plt.figure(num)
        if not fig.axes:
            continue
        if all((not ax.lines and not ax.collections and not ax.patches and not ax.images and not ax.texts) for ax in fig.axes):
            continue

        pdf.savefig(fig, bbox_inches="tight")
        png_path = OUTPUT_DIR / f"{png_prefix}_{index:02d}.png"
        fig.savefig(png_path, bbox_inches="tight", dpi=150)
        saved_paths.append(png_path)
        index += 1

    if fig_nums:
        plt.close("all")

    return saved_paths, index


def tradeable_processor(df: pl.DataFrame) -> pl.DataFrame:
    """Keep only rows that pass real trading filters."""
    return df.filter(pl.col(MASK_FEATURE_NAME) == 1).drop(MASK_FEATURE_NAME)


def learn_label_processor(df: pl.DataFrame) -> pl.DataFrame:
    """Keep rows with valid labels for model fitting."""
    df = df.with_columns(pl.col("label").fill_nan(None))
    return df.drop_nulls(subset=["label"])


def infer_fill_processor(df: pl.DataFrame) -> pl.DataFrame:
    """Cross-sectionally normalize features and fill missing feature values."""
    df = process_cs_rank_norm(df, FEATURE_NAMES)
    df = process_fill_na(df, 0.0, fill_label=False)
    return df


def load_or_download_data() -> tuple[pl.DataFrame, pl.DataFrame]:
    """Load cached real data or download it again."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    stock_path = CACHE_DIR / "stock_panel.parquet"
    benchmark_path = CACHE_DIR / "benchmark.parquet"

    if stock_path.exists() and benchmark_path.exists() and not REFRESH_DATA:
        stock_df = pl.read_parquet(stock_path)
        benchmark_df = pl.read_parquet(benchmark_path)
        return stock_df, benchmark_df

    symbols = fetch_constituents()
    if MAX_SYMBOLS is not None:
        symbols = symbols[:MAX_SYMBOLS]

    login_result = bs.login()
    if login_result.error_code != "0":
        raise RuntimeError(f"baostock login failed: {login_result.error_msg}")

    try:
        stock_df = build_stock_panel(symbols)
        benchmark_df = fetch_benchmark()
    finally:
        bs.logout()

    stock_df.write_parquet(stock_path)
    benchmark_df.write_parquet(benchmark_path)
    return stock_df, benchmark_df


def build_native_df(stock_df: pl.DataFrame, benchmark_df: pl.DataFrame) -> pl.DataFrame:
    """Transform raw real data into vnpy.alpha input frame."""
    labeled_df = prepare_labels(stock_df, benchmark_df)

    native_df = labeled_df.with_columns(
        pl.col("datetime").cast(pl.Datetime),
        pl.when(pl.col("symbol").str.starts_with("6"))
        .then(pl.col("symbol") + pl.lit(".SSE"))
        .otherwise(pl.col("symbol") + pl.lit(".SZSE"))
        .alias("vt_symbol"),
        (pl.col("turnover") / pl.col("volume")).alias("vwap"),
        pl.col("final_keep").cast(pl.Int32).alias(MASK_SOURCE_NAME),
        pl.col("excess_ret_5").alias(LABEL_SOURCE_NAME),
    ).select(
        [
            "datetime",
            "vt_symbol",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "turnover",
            "vwap",
            MASK_SOURCE_NAME,
            LABEL_SOURCE_NAME,
        ]
    ).sort(["datetime", "vt_symbol"])

    return native_df


def build_dataset(native_df: pl.DataFrame) -> VolumeAlphaDataset:
    """Create dataset and apply native vnpy.alpha preprocessing."""
    dataset = VolumeAlphaDataset(
        native_df,
        train_period=(START_DATE, "2025-09-30"),
        valid_period=("2025-10-01", "2025-12-31"),
        test_period=("2026-01-01", END_DATE),
    )

    dataset.prepare_data(max_workers=4)
    dataset.add_processor("infer", tradeable_processor)
    dataset.add_processor("infer", infer_fill_processor)
    dataset.add_processor("learn", learn_label_processor)
    dataset.process_data()
    return dataset


def build_signal(dataset: VolumeAlphaDataset) -> tuple[pl.DataFrame, str]:
    """Train native LASSO model and build prediction signal."""
    model = LassoModel(alpha=0.0001, max_iter=4000, random_state=42)
    model.fit(dataset)
    model.detail()

    pred = model.predict(dataset, Segment.TEST)
    infer_df = dataset.fetch_infer(Segment.TEST).select(["datetime", "vt_symbol", "price_vol_sync_1"])

    if np.nanstd(pred) < 1e-12:
        signal_df = infer_df.select(["datetime", "vt_symbol"]).with_columns(
            (-pl.col("price_vol_sync_1")).alias("signal")
        )
        return signal_df, "fallback_factor"

    signal_df = infer_df.select(["datetime", "vt_symbol"]).with_columns(
        pl.Series(name="signal", values=pred, dtype=pl.Float64)
    )
    return signal_df, "lasso_model"


def render_report(
    title: str,
    render_func: Callable[[], None],
    pdf_name: str,
    png_prefix: str,
) -> list[Path]:
    """Run native vnpy chart generation and save all figures."""
    plt.close("all")
    print(f"rendering {title} ...", flush=True)
    pdf_path = OUTPUT_DIR / pdf_name
    saved_paths: list[Path] = []
    index: int = 1

    original_show = plt.show

    def capture_show(*args, **kwargs) -> None:
        nonlocal index, saved_paths
        current_paths, index = save_figures(pdf, png_prefix, index)
        saved_paths.extend(current_paths)

    with PdfPages(pdf_path) as pdf:
        plt.show = capture_show
        try:
            render_func()
            current_paths, index = save_figures(pdf, png_prefix, index)
            saved_paths.extend(current_paths)
        finally:
            plt.show = original_show
            plt.close("all")

    print(f"saved {len(saved_paths)} figures to {pdf_path}", flush=True)
    return saved_paths


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    stock_df, benchmark_df = load_or_download_data()
    native_df = build_native_df(stock_df, benchmark_df)
    dataset = build_dataset(native_df)

    native_df.write_parquet(OUTPUT_DIR / "native_input.parquet")
    dataset.raw_df.write_parquet(OUTPUT_DIR / "dataset_raw.parquet")
    dataset.learn_df.write_parquet(OUTPUT_DIR / "dataset_learn.parquet")
    dataset.infer_df.write_parquet(OUTPUT_DIR / "dataset_infer.parquet")

    feature_paths = render_report(
        title="feature performance: price_vol_sync_1",
        render_func=lambda: dataset.show_feature_performance("price_vol_sync_1"),
        pdf_name="feature_price_vol_sync_1_tearsheet.pdf",
        png_prefix="feature_price_vol_sync_1",
    )

    signal_df, signal_mode = build_signal(dataset)
    signal_df.write_parquet(OUTPUT_DIR / "signal_test.parquet")

    signal_paths = render_report(
        title=f"signal performance: {signal_mode}",
        render_func=lambda: dataset.show_signal_performance(signal_df),
        pdf_name=f"signal_{signal_mode}_tearsheet.pdf",
        png_prefix=f"signal_{signal_mode}",
    )

    summary_items = [
        ("stock_rows", stock_df.height),
        ("native_rows", native_df.height),
        ("raw_rows", dataset.raw_df.height),
        ("learn_rows", dataset.learn_df.height),
        ("infer_rows", dataset.infer_df.height),
        ("signal_rows", signal_df.height),
        ("signal_mode", signal_mode),
        ("feature_report_figures", len(feature_paths)),
        ("signal_report_figures", len(signal_paths)),
    ]
    summary = pl.DataFrame(
        {
            "item": [item for item, _ in summary_items],
            "value": [str(value) for _, value in summary_items],
        }
    )
    summary.write_csv(OUTPUT_DIR / "native_summary.csv")
    print(summary, flush=True)


if __name__ == "__main__":
    main()
