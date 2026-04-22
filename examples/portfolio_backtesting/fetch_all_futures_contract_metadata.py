from __future__ import annotations

from datetime import datetime
from pathlib import Path
import re

import pandas as pd
from tqsdk import TqApi, TqAuth

from vnpy.trader.setting import SETTINGS


OUTPUT_DIR: Path = Path(__file__).resolve().parent / "backtest_outputs"
DOWNLOAD_STATUS_PATH: Path = (
    Path(__file__).resolve().parent
    / "downloaded_futures"
    / "tqsdk_daily_2010_2026_04"
    / "_download_status.csv"
)


def normalize_product(product: str, exchange: str) -> str:
    if exchange in {"CZCE", "CFFEX"}:
        return product.upper()
    return product.lower()


def extract_product(symbol: str) -> str:
    match = re.match(r"([A-Za-z]+)", symbol)
    if not match:
        raise ValueError(f"Cannot extract product from symbol: {symbol}")
    return match.group(1)


def build_targets() -> list[dict[str, str]]:
    df = pd.read_csv(DOWNLOAD_STATUS_PATH)
    df = df[df["status"] == "downloaded"].copy()

    targets: list[dict[str, str]] = []
    seen: set[str] = set()

    for row in df[["tq_symbol", "exchange", "symbol"]].drop_duplicates().itertuples(index=False):
        if row.tq_symbol in seen:
            continue
        seen.add(str(row.tq_symbol))
        targets.append(
            {
                "vt_symbol": f"{row.symbol}.{row.exchange}",
                "source_symbol_vt": f"{extract_product(str(row.symbol))}.{row.exchange}",
                "symbol_kind": "contract",
                "tq_symbol": str(row.tq_symbol),
            }
        )

    for row in df[["exchange", "symbol"]].drop_duplicates().itertuples(index=False):
        product = extract_product(str(row.symbol))
        vt_symbol = f"{product}.{row.exchange}"
        tq_symbol = f"KQ.m@{row.exchange}.{normalize_product(product, str(row.exchange))}"
        if tq_symbol in seen:
            continue
        seen.add(tq_symbol)
        targets.append(
            {
                "vt_symbol": vt_symbol,
                "source_symbol_vt": vt_symbol,
                "symbol_kind": "product_cont",
                "tq_symbol": tq_symbol,
            }
        )

    return targets


def to_float(value: object) -> float | None:
    try:
        if value is None:
            return None
        result = float(value)
        if pd.isna(result):
            return None
        return result
    except (TypeError, ValueError):
        return None


def reference_price(quote: dict) -> float | None:
    for field in ("pre_settlement", "last_price", "average"):
        value = to_float(quote.get(field))
        if value and value > 0:
            return value
    return None


def fetch_rows() -> list[dict[str, object]]:
    username: str = SETTINGS["datafeed.username"]
    password: str = SETTINGS["datafeed.password"]
    if not username or not password:
        raise RuntimeError("Missing TqSdk credentials in settings.")

    targets = build_targets()
    rows: list[dict[str, object]] = []

    api = TqApi(auth=TqAuth(username, password))
    try:
        total = len(targets)
        for index, target in enumerate(targets, start=1):
            quote = api.get_quote(target["tq_symbol"])
            volume_multiple = to_float(quote.get("volume_multiple"))
            price_tick = to_float(quote.get("price_tick"))
            margin = to_float(quote.get("margin"))
            ref_price = reference_price(quote)

            margin_ratio: float | None = None
            if margin and ref_price and volume_multiple and volume_multiple > 0:
                denominator = ref_price * volume_multiple
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
                    "last_price": to_float(quote.get("last_price")),
                    "pre_settlement": to_float(quote.get("pre_settlement")),
                    "reference_price": ref_price,
                    "margin_ratio": margin_ratio,
                    "commission": to_float(quote.get("commission")),
                    "underlying_symbol": quote.get("underlying_symbol"),
                    "fetched_at": datetime.now().isoformat(timespec="seconds"),
                }
            )
            if index == 1 or index % 100 == 0 or index == total:
                print(f"[{index}/{total}] fetched {target['vt_symbol']} <- {target['tq_symbol']}", flush=True)
    finally:
        api.close()

    return rows


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = fetch_rows()
    df = pd.DataFrame(rows)
    output_path = OUTPUT_DIR / "tqsdk_all_futures_contract_metadata.csv"
    df.sort_values(["symbol_kind", "vt_symbol"], inplace=True)
    df.to_csv(output_path, index=False, encoding="utf-8-sig")
    print(f"saved contract metadata: {output_path}")
    print(f"rows: {len(df)}")


if __name__ == "__main__":
    main()
