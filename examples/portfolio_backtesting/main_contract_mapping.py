from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from contract_metadata import build_resolved_metadata
from qmt_universe import MARGIN_RATIOS, PRICETICKS, RATES, SIZES, SLIPPAGES


DEFAULT_MAPPING_PATH: Path = (
    Path(__file__).resolve().parent / "backtest_outputs" / "tqsdk_main_contract_mapping_2020_2026_04.csv"
)


def load_mapping_df(mapping_path: Path | None = None) -> pd.DataFrame:
    path: Path = mapping_path or DEFAULT_MAPPING_PATH
    df: pd.DataFrame = pd.read_csv(path)
    df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
    df["main_contract_vt"] = df["main_contract_vt"].fillna("")
    return df


def build_daily_mapping(mapping_path: Path | None = None) -> dict[str, dict[str, str]]:
    df: pd.DataFrame = load_mapping_df(mapping_path)
    mapping: dict[str, dict[str, str]] = {}

    for row in df.itertuples(index=False):
        if not row.main_contract_vt:
            continue
        mapping.setdefault(row.date, {})[row.continuous_symbol_vt] = row.main_contract_vt

    return mapping


def build_contract_metadata(mapping_path: Path | None = None) -> dict[str, Any]:
    df: pd.DataFrame = load_mapping_df(mapping_path)
    df = df[df["main_contract_vt"] != ""].copy()
    df = df.drop_duplicates(subset=["main_contract_vt"], keep="first")

    vt_symbols: list[str] = sorted(df["main_contract_vt"].tolist())
    source_symbol_by_contract: dict[str, str] = dict(
        zip(df["main_contract_vt"], df["continuous_symbol_vt"], strict=False)
    )

    rates: dict[str, float] = {
        vt_symbol: float(RATES[source_symbol_by_contract[vt_symbol]]) for vt_symbol in vt_symbols
    }
    slippages: dict[str, float] = {
        vt_symbol: float(SLIPPAGES[source_symbol_by_contract[vt_symbol]]) for vt_symbol in vt_symbols
    }
    default_sizes: dict[str, int] = {
        vt_symbol: int(SIZES[source_symbol_by_contract[vt_symbol]]) for vt_symbol in vt_symbols
    }
    default_priceticks: dict[str, float] = {
        vt_symbol: float(PRICETICKS[source_symbol_by_contract[vt_symbol]]) for vt_symbol in vt_symbols
    }
    default_margin_ratios: dict[str, float] = {
        vt_symbol: float(MARGIN_RATIOS[source_symbol_by_contract[vt_symbol]]) for vt_symbol in vt_symbols
    }
    resolved = build_resolved_metadata(
        vt_symbols=vt_symbols,
        default_sizes=default_sizes,
        default_priceticks=default_priceticks,
        default_margin_ratios=default_margin_ratios,
        fallback_symbol_by_vt=source_symbol_by_contract,
    )
    sizes: dict[str, int] = resolved["sizes"]
    priceticks: dict[str, float] = resolved["priceticks"]
    margin_ratios: dict[str, float] = resolved["margin_ratios"]

    product_symbols: list[str] = sorted(df["continuous_symbol_vt"].drop_duplicates().tolist())

    return {
        "vt_symbols": vt_symbols,
        "rates": rates,
        "slippages": slippages,
        "sizes": sizes,
        "priceticks": priceticks,
        "margin_ratios": margin_ratios,
        "metadata_sources": resolved["metadata_sources"],
        "source_symbol_by_contract": source_symbol_by_contract,
        "product_symbols": product_symbols,
    }
