from __future__ import annotations

from datetime import date
from pathlib import Path
import json

import pandas as pd
from tqsdk import TqAuth
from tqsdk.calendar import TqContCalendar

from vnpy.trader.setting import SETTINGS

from qmt_universe import END_DT, PRODUCT_SPECS, START_DT


START_DATE: date = START_DT.date()
END_DATE: date = END_DT.date()
OUTPUT_DIR: Path = Path(__file__).resolve().parent / "backtest_outputs"


def tq_to_vt_symbol(tq_symbol: str) -> str:
    exchange, symbol = tq_symbol.split(".", 1)
    return f"{symbol}.{exchange}"


def build_mapping_df() -> pd.DataFrame:
    username: str = SETTINGS["datafeed.username"]
    password: str = SETTINGS["datafeed.password"]

    if not username or not password:
        raise RuntimeError("缺少 TqSdk 认证信息，请先在 vt_setting.json 中配置 datafeed.username/password")

    auth = TqAuth(username, password)
    auth.login()

    tq_symbols: list[str] = [spec.tq_cont_symbol for spec in PRODUCT_SPECS]
    calendar = TqContCalendar(
        start_dt=START_DATE,
        end_dt=END_DATE,
        symbols=tq_symbols,
        headers=auth._base_headers,
    )

    df: pd.DataFrame = calendar.df.copy()
    df = df[["date", *tq_symbols]]

    rows: list[dict] = []
    for _, row in df.iterrows():
        trade_date = row["date"].date() if hasattr(row["date"], "date") else row["date"]
        for spec in PRODUCT_SPECS:
            underlying_symbol: str = row[spec.tq_cont_symbol]
            rows.append(
                {
                    "date": trade_date.isoformat(),
                    "product": spec.product,
                    "exchange": spec.exchange.value,
                    "continuous_symbol_tq": spec.tq_cont_symbol,
                    "continuous_symbol_vt": spec.vt_symbol,
                    "main_contract_tq": underlying_symbol,
                    "main_contract_vt": tq_to_vt_symbol(underlying_symbol) if underlying_symbol else "",
                }
            )

    mapping_df: pd.DataFrame = pd.DataFrame(rows)
    mapping_df.sort_values(["date", "exchange", "product"], inplace=True)
    return mapping_df


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    mapping_df: pd.DataFrame = build_mapping_df()

    detail_path: Path = OUTPUT_DIR / "tqsdk_main_contract_mapping_2020_2026_04.csv"
    mapping_df.to_csv(detail_path, index=False, encoding="utf-8-sig")
    print(f"mapping csv: {detail_path}")

    wide_df: pd.DataFrame = mapping_df.pivot(index="date", columns="continuous_symbol_vt", values="main_contract_vt")
    wide_path: Path = OUTPUT_DIR / "tqsdk_main_contract_mapping_wide_2020_2026_04.csv"
    wide_df.to_csv(wide_path, encoding="utf-8-sig")
    print(f"mapping wide csv: {wide_path}")

    summary: dict[str, dict[str, str | int]] = {}
    for continuous_symbol, group in mapping_df.groupby("continuous_symbol_vt"):
        summary[continuous_symbol] = {
            "rows": int(len(group)),
            "start": str(group["date"].iloc[0]),
            "end": str(group["date"].iloc[-1]),
            "distinct_main_contracts": int(group["main_contract_vt"].nunique()),
            "latest_main_contract": str(group["main_contract_vt"].iloc[-1]),
        }

    summary_path: Path = OUTPUT_DIR / "tqsdk_main_contract_mapping_summary_2020_2026_04.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"mapping summary json: {summary_path}")


if __name__ == "__main__":
    main()
