from __future__ import annotations

from datetime import date
from pathlib import Path
import json
import re

import pandas as pd
from tqsdk import TqAuth
from tqsdk.calendar import TqContCalendar

from vnpy.trader.setting import SETTINGS


START_DATE: date = date(2010, 1, 1)
END_DATE: date = date(2026, 4, 30)
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


def tq_to_vt_symbol(tq_symbol: str) -> str:
    exchange, symbol = tq_symbol.split(".", 1)
    return f"{symbol}.{exchange}"


def build_product_df() -> pd.DataFrame:
    df = pd.read_csv(DOWNLOAD_STATUS_PATH)
    df = df[df["status"] == "downloaded"].copy()
    df["product"] = df["symbol"].map(extract_product)
    product_df = df[["exchange", "product"]].drop_duplicates().copy()
    product_df["product_vt"] = product_df["product"] + "." + product_df["exchange"]
    product_df["continuous_symbol_tq"] = product_df.apply(
        lambda row: f"KQ.m@{row['exchange']}.{normalize_product(str(row['product']), str(row['exchange']))}",
        axis=1,
    )
    product_df.sort_values(["exchange", "product"], inplace=True)
    return product_df


def build_mapping_df() -> pd.DataFrame:
    username: str = SETTINGS["datafeed.username"]
    password: str = SETTINGS["datafeed.password"]
    if not username or not password:
        raise RuntimeError("Missing TqSdk credentials in settings.")

    product_df = build_product_df()
    tq_symbols: list[str] = product_df["continuous_symbol_tq"].tolist()

    auth = TqAuth(username, password)
    auth.login()

    calendar = TqContCalendar(
        start_dt=START_DATE,
        end_dt=END_DATE,
        symbols=tq_symbols,
        headers=auth._base_headers,
    )

    calendar_df = calendar.df.copy()
    calendar_df = calendar_df[["date", *tq_symbols]]

    rows: list[dict[str, str]] = []
    product_by_tq = {
        row.continuous_symbol_tq: {
            "product": row.product,
            "exchange": row.exchange,
            "continuous_symbol_vt": row.product_vt,
        }
        for row in product_df.itertuples(index=False)
    }

    for _, row in calendar_df.iterrows():
        trade_date = row["date"].date() if hasattr(row["date"], "date") else row["date"]
        for tq_symbol in tq_symbols:
            info = product_by_tq[tq_symbol]
            underlying_symbol = row[tq_symbol]
            rows.append(
                {
                    "date": trade_date.isoformat(),
                    "product": info["product"],
                    "exchange": info["exchange"],
                    "continuous_symbol_tq": tq_symbol,
                    "continuous_symbol_vt": info["continuous_symbol_vt"],
                    "main_contract_tq": underlying_symbol,
                    "main_contract_vt": tq_to_vt_symbol(underlying_symbol) if underlying_symbol else "",
                }
            )

    mapping_df = pd.DataFrame(rows)
    mapping_df.sort_values(["date", "exchange", "product"], inplace=True)
    return mapping_df


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    product_df = build_product_df()
    mapping_df = build_mapping_df()

    detail_path = OUTPUT_DIR / "tqsdk_all_futures_main_contract_mapping_2010_2026_04.csv"
    wide_path = OUTPUT_DIR / "tqsdk_all_futures_main_contract_mapping_wide_2010_2026_04.csv"
    summary_path = OUTPUT_DIR / "tqsdk_all_futures_main_contract_mapping_summary_2010_2026_04.json"
    product_path = OUTPUT_DIR / "tqsdk_all_futures_products_2010_2026_04.csv"

    mapping_df.to_csv(detail_path, index=False, encoding="utf-8-sig")
    mapping_df.pivot(index="date", columns="continuous_symbol_vt", values="main_contract_vt").to_csv(
        wide_path, encoding="utf-8-sig"
    )
    product_df.to_csv(product_path, index=False, encoding="utf-8-sig")

    summary = {
        "products": int(len(product_df)),
        "rows": int(len(mapping_df)),
        "start": START_DATE.isoformat(),
        "end": END_DATE.isoformat(),
        "latest_contract_count": int(mapping_df[mapping_df["date"] == mapping_df["date"].max()]["main_contract_vt"].nunique()),
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"product csv: {product_path}")
    print(f"mapping csv: {detail_path}")
    print(f"mapping wide csv: {wide_path}")
    print(f"mapping summary json: {summary_path}")
    print(f"products: {summary['products']}")
    print(f"rows: {summary['rows']}")


if __name__ == "__main__":
    main()
