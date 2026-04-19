from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd
from tqsdk import TqApi, TqAuth

from contract_metadata import DEFAULT_CONTRACT_METADATA_PATH
from main_contract_mapping import DEFAULT_MAPPING_PATH, load_mapping_df
from qmt_universe import PRODUCT_SPECS
from vnpy.trader.constant import Exchange
from vnpy.trader.setting import SETTINGS


def normalize_product(product: str, exchange_value: str) -> str:
    if exchange_value in {Exchange.CZCE.value, Exchange.CFFEX.value}:
        return product.upper()
    return product.lower()


def normalize_contract_symbol(symbol: str, exchange_value: str) -> str:
    if exchange_value in {Exchange.CZCE.value, Exchange.CFFEX.value}:
        return symbol.upper()
    return symbol.lower()


def product_vt_to_tq_symbol(vt_symbol: str) -> str:
    product, exchange_value = vt_symbol.split(".", 1)
    return f"KQ.m@{exchange_value}.{normalize_product(product, exchange_value)}"


def contract_vt_to_tq_symbol(vt_symbol: str) -> str:
    symbol, exchange_value = vt_symbol.split(".", 1)
    return f"{exchange_value}.{normalize_contract_symbol(symbol, exchange_value)}"


def build_targets(mapping_path: Path | None = None) -> list[dict[str, str]]:
    targets: list[dict[str, str]] = []
    seen_vt_symbols: set[str] = set()

    for spec in PRODUCT_SPECS:
        vt_symbol: str = spec.vt_symbol
        if vt_symbol in seen_vt_symbols:
            continue
        seen_vt_symbols.add(vt_symbol)
        targets.append(
            {
                "vt_symbol": vt_symbol,
                "source_symbol_vt": vt_symbol,
                "symbol_kind": "product_cont",
                "tq_symbol": product_vt_to_tq_symbol(vt_symbol),
            }
        )

    mapping_df: pd.DataFrame = load_mapping_df(mapping_path or DEFAULT_MAPPING_PATH)
    mapping_df = mapping_df[mapping_df["main_contract_vt"] != ""].drop_duplicates(subset=["main_contract_vt"])

    for row in mapping_df.itertuples(index=False):
        vt_symbol: str = row.main_contract_vt
        if vt_symbol in seen_vt_symbols:
            continue
        seen_vt_symbols.add(vt_symbol)
        targets.append(
            {
                "vt_symbol": vt_symbol,
                "source_symbol_vt": row.continuous_symbol_vt,
                "symbol_kind": "contract",
                "tq_symbol": contract_vt_to_tq_symbol(vt_symbol),
            }
        )

    return targets


def _to_float(value: object) -> float | None:
    try:
        if value is None:
            return None
        result = float(value)
        if pd.isna(result):
            return None
        return result
    except (TypeError, ValueError):
        return None


def _reference_price(quote: dict) -> float | None:
    for field in ("pre_settlement", "last_price", "average"):
        value = _to_float(quote.get(field))
        if value and value > 0:
            return value
    return None


def fetch_metadata_rows(mapping_path: Path | None = None) -> list[dict[str, object]]:
    username: str = SETTINGS["datafeed.username"]
    password: str = SETTINGS["datafeed.password"]
    if not username or not password:
        raise RuntimeError("TqSdk credentials are missing in vt_setting.json.")

    targets = build_targets(mapping_path)
    rows: list[dict[str, object]] = []

    api = TqApi(auth=TqAuth(username, password))
    try:
        total = len(targets)
        for index, target in enumerate(targets, start=1):
            quote = api.get_quote(target["tq_symbol"])
            api.wait_update()

            volume_multiple = _to_float(quote.get("volume_multiple"))
            price_tick = _to_float(quote.get("price_tick"))
            margin = _to_float(quote.get("margin"))
            reference_price = _reference_price(quote)

            margin_ratio: float | None = None
            if margin and reference_price and volume_multiple and volume_multiple > 0:
                denominator = reference_price * volume_multiple
                if denominator > 0:
                    margin_ratio = margin / denominator

            rows.append(
                {
                    "vt_symbol": target["vt_symbol"],
                    "source_symbol_vt": target["source_symbol_vt"],
                    "symbol_kind": target["symbol_kind"],
                    "tq_symbol": target["tq_symbol"],
                    "instrument_id": quote.get("instrument_id"),
                    "exchange_id": quote.get("exchange_id"),
                    "product_id": quote.get("product_id"),
                    "ins_class": quote.get("ins_class"),
                    "price_tick": price_tick,
                    "volume_multiple": volume_multiple,
                    "margin": margin,
                    "last_price": _to_float(quote.get("last_price")),
                    "pre_settlement": _to_float(quote.get("pre_settlement")),
                    "reference_price": reference_price,
                    "margin_ratio": margin_ratio,
                    "commission": _to_float(quote.get("commission")),
                    "underlying_symbol": quote.get("underlying_symbol"),
                    "fetched_at": datetime.now().isoformat(timespec="seconds"),
                }
            )
            if index == 1 or index % 20 == 0 or index == total:
                print(
                    f"[{index}/{total}] fetched {target['vt_symbol']} <- {target['tq_symbol']}",
                    flush=True,
                )
    finally:
        api.close()

    return rows


def main() -> None:
    rows = fetch_metadata_rows()
    df = pd.DataFrame(rows)
    output_path: Path = DEFAULT_CONTRACT_METADATA_PATH
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.sort_values(["symbol_kind", "vt_symbol"], inplace=True)
    df.to_csv(output_path, index=False, encoding="utf-8-sig")
    print(f"saved contract metadata: {output_path}")
    print(f"rows: {len(df)}")
    print(df.head(10).to_string(index=False))


if __name__ == "__main__":
    main()
