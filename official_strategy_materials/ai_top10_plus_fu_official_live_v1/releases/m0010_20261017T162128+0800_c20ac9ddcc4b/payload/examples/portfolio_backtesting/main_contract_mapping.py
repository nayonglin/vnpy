from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from contract_metadata import build_resolved_metadata, load_contract_metadata_df
from qmt_universe import MARGIN_RATIOS, PRICETICKS, RATES, SIZES, SLIPPAGES


DEFAULT_MAPPING_PATH: Path = (
    Path(__file__).resolve().parent / "backtest_outputs" / "tqsdk_main_contract_mapping_2020_2026_04.csv"
)
ALL_FUTURES_MAPPING_PATH: Path = (
    Path(__file__).resolve().parent / "backtest_outputs" / "tqsdk_all_futures_main_contract_mapping_2010_2026_04.csv"
)
DEFAULT_DYNAMIC_MARGIN_RATIO: float = 0.15


def get_preferred_mapping_path() -> Path:
    if ALL_FUTURES_MAPPING_PATH.exists():
        return ALL_FUTURES_MAPPING_PATH
    return DEFAULT_MAPPING_PATH


def load_mapping_df(mapping_path: Path | None = None) -> pd.DataFrame:
    path: Path
    if mapping_path is not None:
        path = mapping_path
    else:
        path = get_preferred_mapping_path()
    df: pd.DataFrame = pd.read_csv(path)
    df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
    df["main_contract_vt"] = df["main_contract_vt"].fillna("")
    return df


def load_product_universe_symbols(universe_csv_path: str | Path | None = None) -> list[str] | None:
    if universe_csv_path is None or str(universe_csv_path).strip() == "":
        return None

    path = Path(str(universe_csv_path)).expanduser()
    if not path.exists():
        raise FileNotFoundError(f"product universe csv not found: {path}")

    df = pd.read_csv(path)
    if "eligible" in df.columns:
        df = df[pd.to_numeric(df["eligible"], errors="coerce").fillna(0).astype(int) == 1].copy()
    column = "product_vt_symbol" if "product_vt_symbol" in df.columns else "vt_symbol"
    if column not in df.columns:
        raise ValueError(f"product universe csv missing product symbol column: {path}")

    symbols = sorted(set(df[column].dropna().astype(str)))
    if not symbols:
        raise ValueError(f"product universe csv has no symbols: {path}")
    return symbols


def _resolve_supported_symbols(supported_symbols: Iterable[str] | None = None) -> set[str]:
    if supported_symbols is None:
        return set(RATES.keys())
    return {str(symbol) for symbol in supported_symbols if str(symbol)}


def build_daily_mapping(
    mapping_path: Path | None = None,
    supported_symbols: Iterable[str] | None = None,
) -> dict[str, dict[str, str]]:
    df: pd.DataFrame = load_mapping_df(mapping_path)
    supported_set: set[str] = _resolve_supported_symbols(supported_symbols)
    df = df[df["continuous_symbol_vt"].isin(supported_set)].copy()
    mapping: dict[str, dict[str, str]] = {}

    for row in df.itertuples(index=False):
        if not row.main_contract_vt:
            continue
        mapping.setdefault(row.date, {})[row.continuous_symbol_vt] = row.main_contract_vt

    return mapping


def _product_defaults(product_symbol: str, product_metadata: dict[str, pd.Series]) -> dict[str, Any]:
    row = product_metadata.get(product_symbol)
    metadata_size = 0
    metadata_pricetick = 0.0
    if row is not None:
        if pd.notna(row.get("volume_multiple")) and float(row["volume_multiple"]) > 0:
            metadata_size = int(round(float(row["volume_multiple"])))
        if pd.notna(row.get("price_tick")) and float(row["price_tick"]) > 0:
            metadata_pricetick = float(row["price_tick"])

    size = int(SIZES.get(product_symbol, 0) or metadata_size or 1)
    pricetick = float(PRICETICKS.get(product_symbol, 0.0) or metadata_pricetick or 1.0)
    margin_ratio = float(MARGIN_RATIOS.get(product_symbol, 0.0) or DEFAULT_DYNAMIC_MARGIN_RATIO)
    return {
        "rate": float(RATES.get(product_symbol, 0.0)),
        "slippage": float(SLIPPAGES.get(product_symbol, 0.0) or pricetick),
        "size": size,
        "pricetick": pricetick,
        "margin_ratio": margin_ratio,
    }


def _load_product_metadata() -> dict[str, pd.Series]:
    metadata_df = load_contract_metadata_df()
    if metadata_df.empty or "vt_symbol" not in metadata_df.columns:
        return {}
    if "symbol_kind" in metadata_df.columns:
        metadata_df = metadata_df[metadata_df["symbol_kind"] == "product_cont"].copy()
    return {str(row["vt_symbol"]): row for _, row in metadata_df.iterrows()}


def build_contract_metadata(
    mapping_path: Path | None = None,
    supported_symbols: Iterable[str] | None = None,
) -> dict[str, Any]:
    df: pd.DataFrame = load_mapping_df(mapping_path)
    supported_set: set[str] = _resolve_supported_symbols(supported_symbols)
    df = df[df["continuous_symbol_vt"].isin(supported_set)].copy()
    df = df[df["main_contract_vt"] != ""].copy()
    df = df.drop_duplicates(subset=["main_contract_vt"], keep="first")

    vt_symbols: list[str] = sorted(df["main_contract_vt"].tolist())
    source_symbol_by_contract: dict[str, str] = dict(
        zip(df["main_contract_vt"], df["continuous_symbol_vt"], strict=False)
    )
    product_metadata = _load_product_metadata()
    defaults_by_product = {
        product_symbol: _product_defaults(product_symbol, product_metadata)
        for product_symbol in sorted(set(source_symbol_by_contract.values()))
    }

    rates: dict[str, float] = {
        vt_symbol: float(defaults_by_product[source_symbol_by_contract[vt_symbol]]["rate"]) for vt_symbol in vt_symbols
    }
    slippages: dict[str, float] = {
        vt_symbol: float(defaults_by_product[source_symbol_by_contract[vt_symbol]]["slippage"]) for vt_symbol in vt_symbols
    }
    default_sizes: dict[str, int] = {
        vt_symbol: int(defaults_by_product[source_symbol_by_contract[vt_symbol]]["size"]) for vt_symbol in vt_symbols
    }
    default_priceticks: dict[str, float] = {
        vt_symbol: float(defaults_by_product[source_symbol_by_contract[vt_symbol]]["pricetick"]) for vt_symbol in vt_symbols
    }
    default_margin_ratios: dict[str, float] = {
        vt_symbol: float(defaults_by_product[source_symbol_by_contract[vt_symbol]]["margin_ratio"]) for vt_symbol in vt_symbols
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
