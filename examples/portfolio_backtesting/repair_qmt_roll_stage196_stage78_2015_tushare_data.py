from __future__ import annotations

import argparse
import json
import re
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import tushare as ts

from vnpy.trader.constant import Exchange, Interval
from vnpy.trader.database import get_database
from vnpy.trader.object import BarData
from vnpy.trader.utility import ZoneInfo

from main_contract_mapping import load_mapping_df, load_product_universe_symbols
from qmt_roll_official_stage78_config import (
    OFFICIAL_STAGE78_CAPITAL,
    OFFICIAL_STAGE78_ROLE,
    OFFICIAL_STAGE78_VERSION,
    build_official_stage78_overrides,
)
from run_qmt_roll_selection_long015_volref30_corr_fu_candidate_robustness_backtest import to_markdown_table


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"
RAW_ROOT: Path = PROJECT_DIR / "downloaded_futures" / "tushare_stage196_stage78_2015_2019"

MODEL_TAG: str = "stage196_stage78_2015_2019_tushare_data_repair_v1"
OUTPUT_PREFIX: str = "qmt_roll_stage196_stage78_2015_2019_tushare_data_repair"

MISSING_CONTRACTS_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_missing_contracts_{MODEL_TAG}.csv"
REPAIR_STATUS_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_repair_status_{MODEL_TAG}.csv"
SUMMARY_JSON_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.json"
REPORT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

TARGET_START: datetime = datetime(2015, 1, 5)
TARGET_END: datetime = datetime(2019, 12, 31)
CHINA_TZ = ZoneInfo("Asia/Shanghai")
REQUEST_INTERVAL_SECONDS: float = 0.55

TUSHARE_EXCHANGE_SUFFIX: dict[str, str] = {
    "SHFE": "SHF",
    "DCE": "DCE",
    "CZCE": "ZCE",
    "CFFEX": "CFX",
    "INE": "INE",
    "GFEX": "GFE",
}


@dataclass(frozen=True)
class ContractTarget:
    product_vt_symbol: str
    contract_vt_symbol: str
    symbol: str
    exchange_value: str
    tushare_code: str
    first_missing_date: str
    last_missing_date: str
    missing_days_before: int


def split_vt_symbol(vt_symbol: str) -> tuple[str, str]:
    symbol, exchange_value = vt_symbol.split(".", 1)
    return symbol, exchange_value


def extract_product_and_digits(symbol: str) -> tuple[str, str]:
    match = re.fullmatch(r"([A-Za-z]+)([0-9]+)", symbol)
    if not match:
        raise ValueError(f"unsupported contract symbol format: {symbol}")
    return match.group(1), match.group(2)


def resolve_czce_digits(digits: str, anchor_date: pd.Timestamp) -> str:
    """Resolve CZCE 3-digit legacy contract code to Tushare YYMM code."""
    if len(digits) != 3:
        return digits

    year_digit = int(digits[0])
    month = int(digits[1:])
    candidates: list[tuple[int, str]] = []

    for year in range(anchor_date.year - 1, anchor_date.year + 11):
        if year % 10 != year_digit:
            continue
        delivery = pd.Timestamp(year=year, month=month, day=1) + pd.offsets.MonthEnd(0)
        distance = int((delivery - anchor_date).days)
        if distance >= -20:
            candidates.append((distance, f"{year % 100:02d}{month:02d}"))

    if candidates:
        candidates.sort(key=lambda item: (item[0] < 0, abs(item[0])))
        return candidates[0][1]

    fallback_year = 2000 + year_digit
    if fallback_year < anchor_date.year - 5:
        fallback_year += 10
    return f"{fallback_year % 100:02d}{month:02d}"


def to_tushare_code(contract_vt_symbol: str, anchor_date: str) -> str:
    symbol, exchange_value = split_vt_symbol(contract_vt_symbol)
    product, digits = extract_product_and_digits(symbol)
    suffix = TUSHARE_EXCHANGE_SUFFIX[exchange_value]

    if exchange_value == "CZCE":
        digits = resolve_czce_digits(digits, pd.Timestamp(anchor_date))

    return f"{product.upper()}{digits}.{suffix}"


def database_date_sets(contract_symbols: set[str], start: datetime, end: datetime) -> dict[str, set[str]]:
    database = get_database()
    exchange_by_value = {item.exchange.value: item.exchange for item in database.get_bar_overview()}
    result: dict[str, set[str]] = {}

    for vt_symbol in sorted(contract_symbols):
        symbol, exchange_value = split_vt_symbol(vt_symbol)
        exchange = exchange_by_value.get(exchange_value)
        if exchange is None:
            result[vt_symbol] = set()
            continue
        bars = database.load_bar_data(symbol, exchange, Interval.DAILY, start, end)
        result[vt_symbol] = {bar.datetime.date().isoformat() for bar in bars}

    return result


def build_missing_contract_targets() -> pd.DataFrame:
    strategy_overrides = build_official_stage78_overrides()
    product_symbols = load_product_universe_symbols(str(strategy_overrides["product_universe_csv_path"]))
    if not product_symbols:
        raise RuntimeError("Stage78 product universe is empty.")

    mapping_df = load_mapping_df()
    mapping_df = mapping_df[
        mapping_df["continuous_symbol_vt"].isin(set(product_symbols))
        & (mapping_df["main_contract_vt"].fillna("") != "")
    ].copy()
    mapping_df["date"] = pd.to_datetime(mapping_df["date"]).dt.date.astype(str)
    mapping_df = mapping_df[
        (mapping_df["date"] >= TARGET_START.date().isoformat())
        & (mapping_df["date"] <= TARGET_END.date().isoformat())
    ].copy()

    contract_symbols = set(mapping_df["main_contract_vt"].astype(str))
    date_sets = database_date_sets(contract_symbols, TARGET_START, TARGET_END)

    missing_rows: list[dict[str, Any]] = []
    for row in mapping_df.itertuples(index=False):
        date_text = str(row.date)
        contract_vt_symbol = str(row.main_contract_vt)
        if date_text in date_sets.get(contract_vt_symbol, set()):
            continue
        product_vt_symbol = str(row.continuous_symbol_vt)
        missing_rows.append(
            {
                "product_vt_symbol": product_vt_symbol,
                "contract_vt_symbol": contract_vt_symbol,
                "date": date_text,
            }
        )

    if not missing_rows:
        return pd.DataFrame(
            columns=[
                "product_vt_symbol",
                "contract_vt_symbol",
                "symbol",
                "exchange",
                "tushare_code",
                "first_missing_date",
                "last_missing_date",
                "missing_days_before",
            ]
        )

    missing_df = pd.DataFrame(missing_rows)
    grouped_rows: list[dict[str, Any]] = []
    for (product_vt_symbol, contract_vt_symbol), group in missing_df.groupby(
        ["product_vt_symbol", "contract_vt_symbol"], sort=True
    ):
        first_date = str(group["date"].min())
        last_date = str(group["date"].max())
        symbol, exchange_value = split_vt_symbol(str(contract_vt_symbol))
        grouped_rows.append(
            {
                "product_vt_symbol": product_vt_symbol,
                "contract_vt_symbol": contract_vt_symbol,
                "symbol": symbol,
                "exchange": exchange_value,
                "tushare_code": to_tushare_code(str(contract_vt_symbol), first_date),
                "first_missing_date": first_date,
                "last_missing_date": last_date,
                "missing_days_before": int(len(group)),
            }
        )

    result = pd.DataFrame(grouped_rows)
    result.sort_values(["first_missing_date", "exchange", "symbol"], inplace=True)
    return result


def load_existing_status() -> pd.DataFrame:
    if REPAIR_STATUS_CSV_PATH.exists():
        return pd.read_csv(REPAIR_STATUS_CSV_PATH)
    return pd.DataFrame()


def save_status(df: pd.DataFrame) -> None:
    if df.empty:
        return
    df.sort_values(["status", "exchange", "symbol"], inplace=True)
    df.to_csv(REPAIR_STATUS_CSV_PATH, index=False, encoding="utf-8-sig")


def upsert_status(status_df: pd.DataFrame, record: dict[str, Any]) -> pd.DataFrame:
    if status_df.empty:
        return pd.DataFrame([record])

    mask = status_df["contract_vt_symbol"].astype(str) == str(record["contract_vt_symbol"])
    if mask.any():
        for key, value in record.items():
            status_df.loc[mask, key] = value
        return status_df

    return pd.concat([status_df, pd.DataFrame([record])], ignore_index=True)


def target_from_row(row: Any) -> ContractTarget:
    return ContractTarget(
        product_vt_symbol=str(row.product_vt_symbol),
        contract_vt_symbol=str(row.contract_vt_symbol),
        symbol=str(row.symbol),
        exchange_value=str(row.exchange),
        tushare_code=str(row.tushare_code),
        first_missing_date=str(row.first_missing_date),
        last_missing_date=str(row.last_missing_date),
        missing_days_before=int(row.missing_days_before),
    )


def fetch_tushare_daily(pro: Any, target: ContractTarget) -> pd.DataFrame:
    start_date = target.first_missing_date.replace("-", "")
    end_date = target.last_missing_date.replace("-", "")
    df = pro.fut_daily(ts_code=target.tushare_code, start_date=start_date, end_date=end_date)
    if df is None:
        return pd.DataFrame()
    if df.empty:
        return df
    df = df.copy()
    df["trade_date"] = pd.to_datetime(df["trade_date"], format="%Y%m%d", errors="coerce").dt.strftime("%Y-%m-%d")
    df = df.dropna(subset=["trade_date"])
    numeric_columns = ["open", "high", "low", "close", "vol", "amount", "oi"]
    for column in numeric_columns:
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce")
    df = df.dropna(subset=["open", "high", "low", "close"])
    df.sort_values("trade_date", inplace=True)
    return df


def raw_csv_path(target: ContractTarget) -> Path:
    exchange_dir = RAW_ROOT / target.exchange_value
    exchange_dir.mkdir(parents=True, exist_ok=True)
    safe_code = target.tushare_code.replace(".", "_")
    return exchange_dir / f"{target.symbol}__{safe_code}.csv"


def build_bars(df: pd.DataFrame, target: ContractTarget) -> list[BarData]:
    exchange = Exchange(target.exchange_value)
    bars: list[BarData] = []
    for row in df.itertuples(index=False):
        trade_date = str(row.trade_date)
        dt = pd.Timestamp(trade_date).tz_localize(CHINA_TZ)
        bars.append(
            BarData(
                symbol=target.symbol,
                exchange=exchange,
                interval=Interval.DAILY,
                datetime=dt.to_pydatetime(),
                open_price=float(row.open),
                high_price=float(row.high),
                low_price=float(row.low),
                close_price=float(row.close),
                volume=float(getattr(row, "vol", 0.0) or 0.0),
                turnover=float(getattr(row, "amount", 0.0) or 0.0) * 10000,
                open_interest=float(getattr(row, "oi", 0.0) or 0.0),
                gateway_name="TUSHARE_REPAIR",
            )
        )
    return bars


def count_covered_missing_dates(df: pd.DataFrame, target: ContractTarget, missing_dates: set[str]) -> int:
    if df.empty:
        return 0
    fetched_dates = set(df["trade_date"].astype(str))
    return len(missing_dates & fetched_dates)


def build_missing_dates_by_contract() -> dict[str, set[str]]:
    strategy_overrides = build_official_stage78_overrides()
    product_symbols = load_product_universe_symbols(str(strategy_overrides["product_universe_csv_path"]))
    if not product_symbols:
        raise RuntimeError("Stage78 product universe is empty.")

    mapping_df = load_mapping_df()
    mapping_df = mapping_df[
        mapping_df["continuous_symbol_vt"].isin(set(product_symbols))
        & (mapping_df["main_contract_vt"].fillna("") != "")
    ].copy()
    mapping_df["date"] = pd.to_datetime(mapping_df["date"]).dt.date.astype(str)
    mapping_df = mapping_df[
        (mapping_df["date"] >= TARGET_START.date().isoformat())
        & (mapping_df["date"] <= TARGET_END.date().isoformat())
    ].copy()
    contract_symbols = set(mapping_df["main_contract_vt"].astype(str))
    date_sets = database_date_sets(contract_symbols, TARGET_START, TARGET_END)

    result: dict[str, set[str]] = {}
    for row in mapping_df.itertuples(index=False):
        date_text = str(row.date)
        contract_vt_symbol = str(row.main_contract_vt)
        if date_text not in date_sets.get(contract_vt_symbol, set()):
            result.setdefault(contract_vt_symbol, set()).add(date_text)
    return result


def repair_contracts(limit: int | None, force: bool) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    RAW_ROOT.mkdir(parents=True, exist_ok=True)

    targets_df = build_missing_contract_targets()
    targets_df.to_csv(MISSING_CONTRACTS_CSV_PATH, index=False, encoding="utf-8-sig")
    status_df = load_existing_status()

    if targets_df.empty:
        payload = build_summary(targets_df, status_df, 0.0)
        return targets_df, status_df, payload

    existing_imported: set[str] = set()
    if not status_df.empty and not force and "status" in status_df.columns:
        imported = status_df[status_df["status"].astype(str).eq("imported")]
        existing_imported = set(imported["contract_vt_symbol"].astype(str))

    run_df = targets_df[~targets_df["contract_vt_symbol"].astype(str).isin(existing_imported)].copy()
    if limit is not None:
        run_df = run_df.head(limit).copy()

    pro = ts.pro_api()
    database = get_database()
    missing_dates_by_contract = build_missing_dates_by_contract()

    started_at = time.time()
    total = len(run_df)
    print(f"[stage196] missing contracts: {len(targets_df)}")
    print(f"[stage196] to repair this run: {total}")

    for index, row in enumerate(run_df.itertuples(index=False), start=1):
        target = target_from_row(row)
        record = {
            "product_vt_symbol": target.product_vt_symbol,
            "contract_vt_symbol": target.contract_vt_symbol,
            "symbol": target.symbol,
            "exchange": target.exchange_value,
            "tushare_code": target.tushare_code,
            "first_missing_date": target.first_missing_date,
            "last_missing_date": target.last_missing_date,
            "missing_days_before": target.missing_days_before,
            "fetched_rows": 0,
            "imported_rows": 0,
            "covered_missing_days_after_fetch": 0,
            "remaining_missing_days_after_fetch": target.missing_days_before,
            "raw_csv": "",
            "status": "failed",
            "message": "",
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        }

        try:
            df = fetch_tushare_daily(pro, target)
            record["fetched_rows"] = len(df)
            if df.empty:
                record["status"] = "empty"
                record["message"] = "tushare returned empty daily data"
            else:
                file_path = raw_csv_path(target)
                df.to_csv(file_path, index=False, encoding="utf-8-sig")
                bars = build_bars(df, target)
                if bars:
                    database.save_bar_data(bars)
                missing_dates = missing_dates_by_contract.get(target.contract_vt_symbol, set())
                covered = count_covered_missing_dates(df, target, missing_dates)
                record["imported_rows"] = len(bars)
                record["covered_missing_days_after_fetch"] = covered
                record["remaining_missing_days_after_fetch"] = max(target.missing_days_before - covered, 0)
                record["raw_csv"] = str(file_path)
                record["status"] = "imported" if covered > 0 else "imported_no_target_dates"
                record["message"] = ""
        except Exception as exc:
            record["status"] = "failed"
            record["message"] = repr(exc)

        status_df = upsert_status(status_df, record)
        if index == 1 or index % 10 == 0 or index == total:
            save_status(status_df)
            payload = build_summary(targets_df, status_df, time.time() - started_at)
            SUMMARY_JSON_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            REPORT_PATH.write_text(build_report(targets_df, status_df, payload), encoding="utf-8")
            print(
                f"[{index}/{total}] {record['status']} {target.contract_vt_symbol} <- {target.tushare_code} "
                f"fetched={record['fetched_rows']} covered={record['covered_missing_days_after_fetch']}/"
                f"{target.missing_days_before}",
                flush=True,
            )

        time.sleep(REQUEST_INTERVAL_SECONDS)

    save_status(status_df)
    payload = build_summary(targets_df, status_df, time.time() - started_at)
    SUMMARY_JSON_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_PATH.write_text(build_report(targets_df, status_df, payload), encoding="utf-8")
    return targets_df, status_df, payload


def build_summary(targets_df: pd.DataFrame, status_df: pd.DataFrame, elapsed_seconds: float) -> dict[str, Any]:
    missing_days_total = int(targets_df["missing_days_before"].sum()) if not targets_df.empty else 0
    contracts_total = int(len(targets_df))
    status_counts: dict[str, int] = {}
    covered_days = 0
    imported_contracts = 0

    if not status_df.empty and "status" in status_df.columns:
        status_counts = {str(k): int(v) for k, v in status_df["status"].value_counts().items()}
        covered_days = int(pd.to_numeric(status_df.get("covered_missing_days_after_fetch", 0), errors="coerce").fillna(0).sum())
        imported_contracts = int(status_df["status"].astype(str).str.startswith("imported").sum())

    return {
        "model_tag": MODEL_TAG,
        "official_version": OFFICIAL_STAGE78_VERSION,
        "official_role": OFFICIAL_STAGE78_ROLE,
        "capital": OFFICIAL_STAGE78_CAPITAL,
        "target_start": TARGET_START.date().isoformat(),
        "target_end": TARGET_END.date().isoformat(),
        "missing_contracts": contracts_total,
        "missing_mapped_days_before": missing_days_total,
        "status_counts": status_counts,
        "imported_contract_status_rows": imported_contracts,
        "covered_missing_days_after_fetch": covered_days,
        "raw_root": str(RAW_ROOT),
        "missing_contracts_csv": str(MISSING_CONTRACTS_CSV_PATH),
        "repair_status_csv": str(REPAIR_STATUS_CSV_PATH),
        "report": str(REPORT_PATH),
        "elapsed_seconds": round(elapsed_seconds, 2),
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }


def build_report(targets_df: pd.DataFrame, status_df: pd.DataFrame, payload: dict[str, Any]) -> str:
    status_view = status_df.copy()
    if not status_view.empty:
        status_view = status_view.sort_values(["status", "missing_days_before"], ascending=[True, False]).head(40)

    product_view = pd.DataFrame()
    if not targets_df.empty:
        product_view = (
            targets_df.groupby("product_vt_symbol", as_index=False)
            .agg(
                missing_contracts=("contract_vt_symbol", "nunique"),
                missing_days_before=("missing_days_before", "sum"),
                first_missing_date=("first_missing_date", "min"),
                last_missing_date=("last_missing_date", "max"),
            )
            .sort_values("missing_days_before", ascending=False)
        )

    lines = [
        "# Stage196 Stage78 2015-2019 Tushare Data Repair",
        "",
        "## Purpose",
        "",
        "- Repair real dominant-contract daily bars required by official Stage78 for 2015-2019 coverage.",
        "- Use Tushare `fut_daily` only for mapped contracts that are missing in the vn.py database.",
        "- Keep strategy parameters unchanged.",
        "",
        "## Summary",
        "",
        f"- Model tag: `{MODEL_TAG}`",
        f"- Official version: `{OFFICIAL_STAGE78_VERSION}`",
        f"- Target window: `{payload['target_start']}` to `{payload['target_end']}`",
        f"- Missing contracts before repair: `{payload['missing_contracts']}`",
        f"- Missing mapped days before repair: `{payload['missing_mapped_days_before']}`",
        f"- Status counts: `{payload['status_counts']}`",
        f"- Covered missing days after fetch: `{payload['covered_missing_days_after_fetch']}`",
        f"- Raw root: `{RAW_ROOT}`",
        "",
        "## Missing By Product",
        "",
        to_markdown_table(product_view.head(40)) if not product_view.empty else "- No missing contracts.",
        "",
        "## Repair Status Sample",
        "",
        to_markdown_table(
            status_view[
                [
                    "contract_vt_symbol",
                    "tushare_code",
                    "status",
                    "missing_days_before",
                    "fetched_rows",
                    "covered_missing_days_after_fetch",
                    "remaining_missing_days_after_fetch",
                    "message",
                ]
            ]
        )
        if not status_view.empty
        else "- No repair status yet.",
        "",
        "## Judgement",
        "",
        "- This stage repairs data only; it does not validate the strategy until Stage194 is rerun.",
        "- Overfitting risk is low because no strategy parameter or universe rule is changed.",
        "- After repair, rerun Stage194 coverage gate and multicycle audit.",
    ]
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Repair Stage78 2015-2019 missing futures daily bars using Tushare.")
    parser.add_argument("--limit", type=int, default=None, help="Limit contracts repaired in this run for smoke testing.")
    parser.add_argument("--force", action="store_true", help="Refetch contracts already marked imported.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    targets_df, status_df, payload = repair_contracts(limit=args.limit, force=bool(args.force))
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    print(f"[stage196] missing contracts: {MISSING_CONTRACTS_CSV_PATH}")
    print(f"[stage196] repair status: {REPAIR_STATUS_CSV_PATH}")
    print(f"[stage196] report: {REPORT_PATH}")


if __name__ == "__main__":
    main()
