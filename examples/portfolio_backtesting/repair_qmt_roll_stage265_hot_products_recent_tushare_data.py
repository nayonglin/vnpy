from __future__ import annotations

import argparse
import json
import os
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

from run_qmt_roll_selection_long015_volref30_corr_fu_candidate_robustness_backtest import to_markdown_table


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"
RAW_ROOT: Path = PROJECT_DIR / "downloaded_futures" / "tushare_stage265_hot_products_recent"

MODEL_TAG: str = "stage265_hot_products_recent_tushare_data_v1"
OUTPUT_PREFIX: str = "qmt_roll_stage265_hot_products_recent_tushare_data"

MAPPING_PATH: Path = OUTPUT_DIR / "tqsdk_all_futures_main_contract_mapping_2010_2026_04.csv"
MISSING_CONTRACTS_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_missing_contracts_{MODEL_TAG}.csv"
REPAIR_STATUS_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_repair_status_{MODEL_TAG}.csv"
SUMMARY_JSON_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.json"
REPORT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

TARGET_PRODUCTS: tuple[str, ...] = (
    "TA.CZCE",
    "m.DCE",
    "p.DCE",
    "y.DCE",
    "i.DCE",
    "v.DCE",
    "ao.SHFE",
)

ANALYSIS_START: pd.Timestamp = pd.Timestamp("2020-01-01")
ANALYSIS_END: pd.Timestamp = pd.Timestamp("2026-04-30")
RECENT_DAYS: int = 240
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
    return digits


def to_tushare_code(contract_vt_symbol: str, anchor_date: str) -> str:
    symbol, exchange_value = split_vt_symbol(contract_vt_symbol)
    product, digits = extract_product_and_digits(symbol)
    suffix = TUSHARE_EXCHANGE_SUFFIX[exchange_value]
    if exchange_value == "CZCE":
        digits = resolve_czce_digits(digits, pd.Timestamp(anchor_date))
    return f"{product.upper()}{digits}.{suffix}"


def _parse_vt_symbol(vt_symbol: str) -> tuple[str, Exchange] | None:
    if "." not in vt_symbol:
        return None
    symbol, exchange_value = vt_symbol.split(".", 1)
    try:
        return symbol, Exchange(exchange_value)
    except ValueError:
        return None


def database_date_sets(contract_symbols: set[str], start: pd.Timestamp, end: pd.Timestamp) -> dict[str, set[str]]:
    database = get_database()
    result: dict[str, set[str]] = {}
    start_dt = start.to_pydatetime()
    end_dt = end.to_pydatetime()
    for vt_symbol in sorted(contract_symbols):
        parsed = _parse_vt_symbol(vt_symbol)
        if parsed is None:
            result[vt_symbol] = set()
            continue
        symbol, exchange = parsed
        bars = database.load_bar_data(symbol, exchange, Interval.DAILY, start_dt, end_dt)
        result[vt_symbol] = {bar.datetime.date().isoformat() for bar in bars}
    return result


def _target_recent_mapping() -> pd.DataFrame:
    mapping = pd.read_csv(MAPPING_PATH)
    mapping["date"] = pd.to_datetime(mapping["date"]).dt.normalize()
    mapping["main_contract_vt"] = mapping["main_contract_vt"].fillna("").astype(str)
    mapping = mapping[
        mapping["continuous_symbol_vt"].isin(set(TARGET_PRODUCTS))
        & (mapping["main_contract_vt"] != "")
        & (mapping["date"] >= ANALYSIS_START)
        & (mapping["date"] <= ANALYSIS_END)
    ].copy()

    pieces: list[pd.DataFrame] = []
    for _, group in mapping.groupby("continuous_symbol_vt", sort=True):
        group = group.sort_values("date").tail(RECENT_DAYS).copy()
        pieces.append(group)
    if not pieces:
        return mapping.iloc[0:0].copy()
    return pd.concat(pieces, ignore_index=True).sort_values(["continuous_symbol_vt", "date"])


def build_missing_contract_targets() -> pd.DataFrame:
    mapping = _target_recent_mapping()
    if mapping.empty:
        return pd.DataFrame()
    contract_symbols = set(mapping["main_contract_vt"].astype(str))
    date_sets = database_date_sets(contract_symbols, mapping["date"].min(), mapping["date"].max())

    missing_rows: list[dict[str, Any]] = []
    for row in mapping.itertuples(index=False):
        date_text = pd.Timestamp(row.date).date().isoformat()
        contract_vt_symbol = str(row.main_contract_vt)
        if date_text in date_sets.get(contract_vt_symbol, set()):
            continue
        missing_rows.append(
            {
                "product_vt_symbol": str(row.continuous_symbol_vt),
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

    missing = pd.DataFrame(missing_rows)
    grouped_rows: list[dict[str, Any]] = []
    for (product_vt_symbol, contract_vt_symbol), group in missing.groupby(
        ["product_vt_symbol", "contract_vt_symbol"], sort=True
    ):
        first_date = str(group["date"].min())
        last_date = str(group["date"].max())
        symbol, exchange_value = split_vt_symbol(str(contract_vt_symbol))
        grouped_rows.append(
            {
                "product_vt_symbol": str(product_vt_symbol),
                "contract_vt_symbol": str(contract_vt_symbol),
                "symbol": symbol,
                "exchange": exchange_value,
                "tushare_code": to_tushare_code(str(contract_vt_symbol), first_date),
                "first_missing_date": first_date,
                "last_missing_date": last_date,
                "missing_days_before": int(len(group)),
            }
        )

    result = pd.DataFrame(grouped_rows)
    result.sort_values(["product_vt_symbol", "first_missing_date", "contract_vt_symbol"], inplace=True)
    return result.reset_index(drop=True)


def load_existing_status() -> pd.DataFrame:
    if REPAIR_STATUS_CSV_PATH.exists():
        return pd.read_csv(REPAIR_STATUS_CSV_PATH)
    return pd.DataFrame()


def save_status(df: pd.DataFrame) -> None:
    if not df.empty:
        df.sort_values(["product_vt_symbol", "contract_vt_symbol"], inplace=True)
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
    df = pro.fut_daily(
        ts_code=target.tushare_code,
        start_date=target.first_missing_date.replace("-", ""),
        end_date=target.last_missing_date.replace("-", ""),
    )
    if df is None or df.empty:
        return pd.DataFrame()
    df = df.copy()
    df["trade_date"] = pd.to_datetime(df["trade_date"], format="%Y%m%d", errors="coerce").dt.strftime("%Y-%m-%d")
    df = df.dropna(subset=["trade_date"])
    for column in ["open", "high", "low", "close", "vol", "amount", "oi"]:
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
        dt = pd.Timestamp(str(row.trade_date)).tz_localize(CHINA_TZ)
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
                gateway_name="TUSHARE_STAGE265",
            )
        )
    return bars


def build_missing_dates_by_contract() -> dict[str, set[str]]:
    mapping = _target_recent_mapping()
    if mapping.empty:
        return {}
    contract_symbols = set(mapping["main_contract_vt"].astype(str))
    date_sets = database_date_sets(contract_symbols, mapping["date"].min(), mapping["date"].max())
    result: dict[str, set[str]] = {}
    for row in mapping.itertuples(index=False):
        date_text = pd.Timestamp(row.date).date().isoformat()
        contract_vt_symbol = str(row.main_contract_vt)
        if date_text not in date_sets.get(contract_vt_symbol, set()):
            result.setdefault(contract_vt_symbol, set()).add(date_text)
    return result


def count_covered_missing_dates(df: pd.DataFrame, missing_dates: set[str]) -> int:
    if df.empty:
        return 0
    return len(set(df["trade_date"].astype(str)) & missing_dates)


def repair_contracts(limit: int | None, force: bool, dry_run: bool) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    RAW_ROOT.mkdir(parents=True, exist_ok=True)

    targets_df = build_missing_contract_targets()
    targets_df.to_csv(MISSING_CONTRACTS_CSV_PATH, index=False, encoding="utf-8-sig")
    status_df = load_existing_status()
    if targets_df.empty or dry_run:
        payload = build_summary(targets_df, status_df, elapsed_seconds=0.0, dry_run=dry_run)
        SUMMARY_JSON_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        REPORT_PATH.write_text(build_report(targets_df, status_df, payload), encoding="utf-8")
        return targets_df, status_df, payload

    existing_imported: set[str] = set()
    if not status_df.empty and not force and "status" in status_df.columns:
        imported = status_df[status_df["status"].astype(str).str.startswith("imported")]
        existing_imported = set(imported["contract_vt_symbol"].astype(str))
    run_df = targets_df[~targets_df["contract_vt_symbol"].astype(str).isin(existing_imported)].copy()
    if limit is not None:
        run_df = run_df.head(limit).copy()

    token = os.environ.get("TUSHARE_TOKEN") or os.environ.get("TUSHARE_PRO_TOKEN") or ""
    pro = ts.pro_api(token if token else None)
    database = get_database()
    missing_dates_by_contract = build_missing_dates_by_contract()

    started_at = time.time()
    print(f"[stage265] missing contracts: {len(targets_df)}")
    print(f"[stage265] to repair this run: {len(run_df)}")
    for index, row in enumerate(run_df.itertuples(index=False), start=1):
        target = target_from_row(row)
        missing_dates = missing_dates_by_contract.get(target.contract_vt_symbol, set())
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
            record["fetched_rows"] = int(len(df))
            if df.empty:
                record["status"] = "empty"
                record["message"] = "tushare returned empty daily data"
            else:
                file_path = raw_csv_path(target)
                df.to_csv(file_path, index=False, encoding="utf-8-sig")
                bars = build_bars(df, target)
                if bars:
                    database.save_bar_data(bars)
                covered = count_covered_missing_dates(df, missing_dates)
                record["imported_rows"] = int(len(bars))
                record["covered_missing_days_after_fetch"] = int(covered)
                record["remaining_missing_days_after_fetch"] = max(target.missing_days_before - int(covered), 0)
                record["raw_csv"] = str(file_path)
                record["status"] = "imported" if covered > 0 else "imported_no_target_dates"
        except Exception as exc:
            record["status"] = "failed"
            record["message"] = repr(exc)

        status_df = upsert_status(status_df, record)
        save_status(status_df)
        payload = build_summary(targets_df, status_df, time.time() - started_at, dry_run=False)
        SUMMARY_JSON_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        REPORT_PATH.write_text(build_report(targets_df, status_df, payload), encoding="utf-8")
        print(
            f"[{index}/{len(run_df)}] {record['status']} {target.contract_vt_symbol} <- {target.tushare_code} "
            f"fetched={record['fetched_rows']} covered={record['covered_missing_days_after_fetch']}/"
            f"{target.missing_days_before}",
            flush=True,
        )
        time.sleep(REQUEST_INTERVAL_SECONDS)

    payload = build_summary(targets_df, status_df, time.time() - started_at, dry_run=False)
    SUMMARY_JSON_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_PATH.write_text(build_report(targets_df, status_df, payload), encoding="utf-8")
    return targets_df, status_df, payload


def build_summary(
    targets_df: pd.DataFrame,
    status_df: pd.DataFrame,
    elapsed_seconds: float,
    dry_run: bool,
) -> dict[str, Any]:
    missing_days_total = int(targets_df["missing_days_before"].sum()) if not targets_df.empty else 0
    covered_days = 0
    status_counts: dict[str, int] = {}
    if not status_df.empty and "status" in status_df.columns:
        status_counts = {str(k): int(v) for k, v in status_df["status"].value_counts().items()}
        covered_days = int(
            pd.to_numeric(status_df.get("covered_missing_days_after_fetch", 0), errors="coerce")
            .fillna(0)
            .sum()
        )
    by_product: dict[str, dict[str, int]] = {}
    if not targets_df.empty:
        product_missing = (
            targets_df.groupby("product_vt_symbol")
            .agg(missing_contracts=("contract_vt_symbol", "nunique"), missing_days_before=("missing_days_before", "sum"))
            .astype(int)
        )
        by_product = product_missing.to_dict(orient="index")
        if not status_df.empty:
            product_covered = (
                status_df.groupby("product_vt_symbol")["covered_missing_days_after_fetch"]
                .apply(lambda s: int(pd.to_numeric(s, errors="coerce").fillna(0).sum()))
            )
            for product, covered in product_covered.items():
                by_product.setdefault(str(product), {})["covered_missing_days_after_fetch"] = int(covered)
    return {
        "model_tag": MODEL_TAG,
        "target_products": list(TARGET_PRODUCTS),
        "analysis_end": ANALYSIS_END.date().isoformat(),
        "recent_days": RECENT_DAYS,
        "dry_run": dry_run,
        "missing_contracts": int(len(targets_df)),
        "missing_mapped_days_before": missing_days_total,
        "covered_missing_days_after_fetch": covered_days,
        "status_counts": status_counts,
        "by_product": by_product,
        "raw_root": str(RAW_ROOT),
        "missing_contracts_csv": str(MISSING_CONTRACTS_CSV_PATH),
        "repair_status_csv": str(REPAIR_STATUS_CSV_PATH),
        "report": str(REPORT_PATH),
        "elapsed_seconds": round(elapsed_seconds, 2),
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }


def build_report(targets_df: pd.DataFrame, status_df: pd.DataFrame, payload: dict[str, Any]) -> str:
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
    status_view = status_df.copy()
    if not status_view.empty:
        status_view = status_view.sort_values(["product_vt_symbol", "contract_vt_symbol"]).head(60)
    lines = [
        "# Stage265 Hot Products Recent Tushare Data Repair",
        "",
        "## Purpose",
        "",
        "- Repair recent dominant-contract daily bars for hot universe expansion targets.",
        "- This is a data-quality step, not a strategy optimization.",
        "- Stage78-1 formal configuration is not modified.",
        "",
        "## Summary",
        "",
        f"- Target products: `{', '.join(TARGET_PRODUCTS)}`",
        f"- Analysis end: `{payload['analysis_end']}`",
        f"- Recent days: `{payload['recent_days']}`",
        f"- Dry run: `{payload['dry_run']}`",
        f"- Missing contracts before repair: `{payload['missing_contracts']}`",
        f"- Missing mapped days before repair: `{payload['missing_mapped_days_before']}`",
        f"- Covered missing days after fetch: `{payload['covered_missing_days_after_fetch']}`",
        f"- Status counts: `{payload['status_counts']}`",
        "",
        "## Missing By Product",
        "",
        to_markdown_table(product_view) if not product_view.empty else "- No missing contracts.",
        "",
        "## Repair Status Sample",
        "",
        to_markdown_table(status_view) if not status_view.empty else "- No repair status rows yet.",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Repair recent hot product daily bars through Tushare fut_daily.")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    targets_df, status_df, payload = repair_contracts(args.limit, args.force, args.dry_run)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    print(f"missing contracts: {MISSING_CONTRACTS_CSV_PATH}")
    print(f"repair status: {REPAIR_STATUS_CSV_PATH}")
    print(f"report: {REPORT_PATH}")


if __name__ == "__main__":
    main()
