from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


DEFAULT_CONTRACT_METADATA_PATH: Path = (
    Path(__file__).resolve().parent / "backtest_outputs" / "tqsdk_contract_metadata.csv"
)


def load_contract_metadata_df(metadata_path: Path | None = None) -> pd.DataFrame:
    path: Path = metadata_path or DEFAULT_CONTRACT_METADATA_PATH
    if not path.exists():
        return pd.DataFrame()

    df: pd.DataFrame = pd.read_csv(path)
    if "vt_symbol" not in df.columns:
        return pd.DataFrame()

    numeric_columns: tuple[str, ...] = (
        "price_tick",
        "volume_multiple",
        "margin",
        "margin_ratio",
        "last_price",
        "pre_settlement",
        "reference_price",
        "commission",
    )
    for column in numeric_columns:
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce")

    return df


def _pick_best_row(
    metadata_df: pd.DataFrame,
    vt_symbol: str,
    fallback_vt_symbol: str | None = None,
) -> pd.Series | None:
    if metadata_df.empty:
        return None

    matched_df: pd.DataFrame = metadata_df[metadata_df["vt_symbol"] == vt_symbol]
    if matched_df.empty and fallback_vt_symbol:
        matched_df = metadata_df[metadata_df["vt_symbol"] == fallback_vt_symbol]
    if matched_df.empty:
        return None

    if "symbol_kind" in matched_df.columns:
        matched_df = matched_df.copy()
        priority_map: dict[str, int] = {
            "contract": 0,
            "product_cont": 1,
        }
        matched_df["priority"] = matched_df["symbol_kind"].map(priority_map).fillna(99)
        matched_df.sort_values(["priority"], inplace=True)

    return matched_df.iloc[0]


def build_resolved_metadata(
    vt_symbols: list[str],
    default_sizes: dict[str, int],
    default_priceticks: dict[str, float],
    default_margin_ratios: dict[str, float],
    fallback_symbol_by_vt: dict[str, str] | None = None,
    metadata_path: Path | None = None,
) -> dict[str, dict[str, Any]]:
    metadata_df: pd.DataFrame = load_contract_metadata_df(metadata_path)
    fallback_map: dict[str, str] = fallback_symbol_by_vt or {}

    sizes: dict[str, int] = {}
    priceticks: dict[str, float] = {}
    margin_ratios: dict[str, float] = {}
    metadata_sources: dict[str, str] = {}

    for vt_symbol in vt_symbols:
        fallback_vt_symbol: str | None = fallback_map.get(vt_symbol)
        row: pd.Series | None = _pick_best_row(metadata_df, vt_symbol, fallback_vt_symbol)

        size: int = int(default_sizes[vt_symbol])
        pricetick: float = float(default_priceticks[vt_symbol])
        margin_ratio: float = float(default_margin_ratios[vt_symbol])
        source: str = "static"

        if row is not None:
            if pd.notna(row.get("volume_multiple")) and float(row["volume_multiple"]) > 0:
                size = int(round(float(row["volume_multiple"])))
            if pd.notna(row.get("price_tick")) and float(row["price_tick"]) > 0:
                pricetick = float(row["price_tick"])
            if pd.notna(row.get("margin_ratio")) and float(row["margin_ratio"]) > 0:
                margin_ratio = float(row["margin_ratio"])
            source = "tqsdk"

        sizes[vt_symbol] = size
        priceticks[vt_symbol] = pricetick
        margin_ratios[vt_symbol] = margin_ratio
        metadata_sources[vt_symbol] = source

    return {
        "sizes": sizes,
        "priceticks": priceticks,
        "margin_ratios": margin_ratios,
        "metadata_sources": metadata_sources,
    }
