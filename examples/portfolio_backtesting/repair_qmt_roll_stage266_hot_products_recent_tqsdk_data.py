from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

PROJECT_ROOT: Path = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from vnpy.trader.constant import Exchange, Interval
from vnpy.trader.database import get_database
from vnpy.trader.object import BarData, HistoryRequest
from vnpy.trader.setting import SETTINGS

from repair_qmt_roll_stage265_hot_products_recent_tushare_data import (
    TARGET_PRODUCTS,
    build_missing_contract_targets,
    build_missing_dates_by_contract,
)


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"
RAW_ROOT: Path = PROJECT_DIR / "downloaded_futures" / "tqsdk_stage266_hot_products_recent"
LOCAL_TQSDK_PATH: Path = PROJECT_ROOT / "vnpy_tqsdk" / "tqsdk_datafeed.py"

MODEL_TAG: str = "stage266_hot_products_recent_tqsdk_data_v1"
OUTPUT_PREFIX: str = "qmt_roll_stage266_hot_products_recent_tqsdk_data"

MISSING_CONTRACTS_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_missing_contracts_{MODEL_TAG}.csv"
REPAIR_STATUS_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_repair_status_{MODEL_TAG}.csv"
SUMMARY_JSON_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.json"
REPORT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

DEFAULT_PADDING_DAYS: int = 10


@dataclass(frozen=True)
class ContractTarget:
    product_vt_symbol: str
    contract_vt_symbol: str
    symbol: str
    exchange_value: str
    first_missing_date: str
    last_missing_date: str
    missing_days_before: int


def _load_tqsdk_datafeed_class() -> Any:
    spec = importlib.util.spec_from_file_location("local_vnpy_tqsdk_datafeed", LOCAL_TQSDK_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load TqSdk datafeed from {LOCAL_TQSDK_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.TqsdkDatafeed


def _credential_status() -> dict[str, Any]:
    username = str(SETTINGS["datafeed.username"] or "")
    password = str(SETTINGS["datafeed.password"] or "")
    return {
        "datafeed_name": str(SETTINGS["datafeed.name"] or ""),
        "username_configured": bool(username),
        "username_length": len(username) if username else 0,
        "password_configured": bool(password),
        "password_length": len(password) if password else 0,
    }


def _split_contract_vt(vt_symbol: str) -> tuple[str, Exchange]:
    symbol, exchange_value = vt_symbol.split(".", 1)
    return symbol, Exchange(exchange_value)


def _target_from_row(row: Any) -> ContractTarget:
    return ContractTarget(
        product_vt_symbol=str(row.product_vt_symbol),
        contract_vt_symbol=str(row.contract_vt_symbol),
        symbol=str(row.symbol),
        exchange_value=str(row.exchange),
        first_missing_date=str(row.first_missing_date),
        last_missing_date=str(row.last_missing_date),
        missing_days_before=int(row.missing_days_before),
    )


def _load_existing_status() -> pd.DataFrame:
    if REPAIR_STATUS_CSV_PATH.exists():
        return pd.read_csv(REPAIR_STATUS_CSV_PATH)
    return pd.DataFrame()


def _save_status(df: pd.DataFrame) -> None:
    if df.empty:
        return
    df.sort_values(["product_vt_symbol", "contract_vt_symbol"], inplace=True)
    df.to_csv(REPAIR_STATUS_CSV_PATH, index=False, encoding="utf-8-sig")


def _upsert_status(status_df: pd.DataFrame, record: dict[str, Any]) -> pd.DataFrame:
    if status_df.empty:
        return pd.DataFrame([record])
    mask = status_df["contract_vt_symbol"].astype(str) == str(record["contract_vt_symbol"])
    if mask.any():
        for key, value in record.items():
            status_df.loc[mask, key] = value
        return status_df
    return pd.concat([status_df, pd.DataFrame([record])], ignore_index=True)


def _bar_request_window(target: ContractTarget, padding_days: int) -> tuple[datetime, datetime]:
    start = pd.Timestamp(target.first_missing_date) - pd.Timedelta(days=padding_days)
    end = pd.Timestamp(target.last_missing_date) + pd.Timedelta(days=padding_days)
    return start.to_pydatetime(), end.to_pydatetime()


def _raw_csv_path(target: ContractTarget) -> Path:
    exchange_dir = RAW_ROOT / target.exchange_value
    exchange_dir.mkdir(parents=True, exist_ok=True)
    return exchange_dir / f"{target.symbol}.csv"


def _bars_to_frame(bars: list[BarData]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for bar in bars:
        rows.append(
            {
                "trade_date": pd.Timestamp(bar.datetime).date().isoformat(),
                "datetime": pd.Timestamp(bar.datetime).isoformat(),
                "symbol": bar.symbol,
                "exchange": bar.exchange.value,
                "open": float(bar.open_price),
                "high": float(bar.high_price),
                "low": float(bar.low_price),
                "close": float(bar.close_price),
                "volume": float(bar.volume),
                "open_interest": float(bar.open_interest),
            }
        )
    if not rows:
        return pd.DataFrame(
            columns=[
                "trade_date",
                "datetime",
                "symbol",
                "exchange",
                "open",
                "high",
                "low",
                "close",
                "volume",
                "open_interest",
            ]
        )
    return pd.DataFrame(rows).sort_values(["trade_date", "symbol", "exchange"]).reset_index(drop=True)


def _count_covered_missing_dates(bars_df: pd.DataFrame, missing_dates: set[str]) -> int:
    if bars_df.empty:
        return 0
    return len(set(bars_df["trade_date"].astype(str)) & missing_dates)


def _fetch_contract_bars(datafeed: Any, target: ContractTarget, padding_days: int) -> list[BarData]:
    symbol, exchange = _split_contract_vt(target.contract_vt_symbol)
    start, end = _bar_request_window(target, padding_days)
    req = HistoryRequest(
        symbol=symbol,
        exchange=exchange,
        interval=Interval.DAILY,
        start=start,
        end=end,
    )
    bars = datafeed.query_bar_history(req)
    return list(bars or [])


def repair_contracts(limit: int | None, force: bool, dry_run: bool, padding_days: int) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    RAW_ROOT.mkdir(parents=True, exist_ok=True)

    targets_df = build_missing_contract_targets()
    targets_df.to_csv(MISSING_CONTRACTS_CSV_PATH, index=False, encoding="utf-8-sig")
    status_df = _load_existing_status()
    if targets_df.empty or dry_run:
        payload = _build_summary(targets_df, status_df, elapsed_seconds=0.0, dry_run=dry_run)
        SUMMARY_JSON_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        REPORT_PATH.write_text(_build_report(targets_df, status_df, payload), encoding="utf-8")
        return targets_df, status_df, payload

    existing_done: set[str] = set()
    if not status_df.empty and not force and "status" in status_df.columns:
        done = status_df[status_df["status"].astype(str).isin(["saved", "saved_no_target_dates"])]
        existing_done = set(done["contract_vt_symbol"].astype(str))
    run_df = targets_df[~targets_df["contract_vt_symbol"].astype(str).isin(existing_done)].copy()
    if limit is not None:
        run_df = run_df.head(limit).copy()

    TqsdkDatafeed = _load_tqsdk_datafeed_class()
    datafeed = TqsdkDatafeed()
    database = get_database()
    missing_dates_by_contract = build_missing_dates_by_contract()

    started_at = time.time()
    print(f"[stage266] missing contracts: {len(targets_df)}")
    print(f"[stage266] to repair this run: {len(run_df)}")
    for index, row in enumerate(run_df.itertuples(index=False), start=1):
        target = _target_from_row(row)
        missing_dates = missing_dates_by_contract.get(target.contract_vt_symbol, set())
        record = {
            "product_vt_symbol": target.product_vt_symbol,
            "contract_vt_symbol": target.contract_vt_symbol,
            "symbol": target.symbol,
            "exchange": target.exchange_value,
            "first_missing_date": target.first_missing_date,
            "last_missing_date": target.last_missing_date,
            "missing_days_before": target.missing_days_before,
            "fetched_rows": 0,
            "saved_rows": 0,
            "covered_missing_days_after_fetch": 0,
            "remaining_missing_days_after_fetch": target.missing_days_before,
            "raw_csv": "",
            "status": "failed",
            "message": "",
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        }
        try:
            bars = _fetch_contract_bars(datafeed, target, padding_days)
            bars_df = _bars_to_frame(bars)
            record["fetched_rows"] = int(len(bars_df))
            if bars_df.empty:
                record["status"] = "empty"
                record["message"] = "tqsdk returned empty daily data"
            else:
                file_path = _raw_csv_path(target)
                bars_df.to_csv(file_path, index=False, encoding="utf-8-sig")
                database.save_bar_data(bars)
                covered = _count_covered_missing_dates(bars_df, missing_dates)
                record["saved_rows"] = int(len(bars))
                record["covered_missing_days_after_fetch"] = int(covered)
                record["remaining_missing_days_after_fetch"] = max(target.missing_days_before - int(covered), 0)
                record["raw_csv"] = str(file_path)
                record["status"] = "saved" if covered > 0 else "saved_no_target_dates"
        except Exception as exc:
            record["status"] = "failed"
            record["message"] = repr(exc)

        status_df = _upsert_status(status_df, record)
        _save_status(status_df)
        payload = _build_summary(targets_df, status_df, time.time() - started_at, dry_run=False)
        SUMMARY_JSON_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        REPORT_PATH.write_text(_build_report(targets_df, status_df, payload), encoding="utf-8")
        print(
            f"[{index}/{len(run_df)}] {record['status']} {target.contract_vt_symbol} "
            f"fetched={record['fetched_rows']} covered={record['covered_missing_days_after_fetch']}/"
            f"{target.missing_days_before}",
            flush=True,
        )

    payload = _build_summary(targets_df, status_df, time.time() - started_at, dry_run=False)
    SUMMARY_JSON_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_PATH.write_text(_build_report(targets_df, status_df, payload), encoding="utf-8")
    return targets_df, status_df, payload


def _build_summary(
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
        "dry_run": dry_run,
        "missing_contracts": int(len(targets_df)),
        "missing_mapped_days_before": missing_days_total,
        "covered_missing_days_after_fetch": covered_days,
        "remaining_missing_days_after_fetch": max(missing_days_total - covered_days, 0),
        "status_counts": status_counts,
        "by_product": by_product,
        "credential_status": _credential_status(),
        "raw_root": str(RAW_ROOT),
        "missing_contracts_csv": str(MISSING_CONTRACTS_CSV_PATH),
        "repair_status_csv": str(REPAIR_STATUS_CSV_PATH),
        "report": str(REPORT_PATH),
        "elapsed_seconds": round(elapsed_seconds, 2),
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }


def _to_markdown_table(df: pd.DataFrame, max_rows: int = 80) -> str:
    if df.empty:
        return "_empty_"
    view = df.head(max_rows).copy()
    header = "| " + " | ".join(view.columns) + " |"
    sep = "| " + " | ".join(["---"] * len(view.columns)) + " |"
    rows = ["| " + " | ".join(map(str, row)) + " |" for row in view.to_numpy()]
    return "\n".join([header, sep, *rows])


def _build_report(targets_df: pd.DataFrame, status_df: pd.DataFrame, payload: dict[str, Any]) -> str:
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
        status_view = status_view.sort_values(["product_vt_symbol", "contract_vt_symbol"])

    lines = [
        "# Stage266 Hot Products Recent TQSDK Data Repair",
        "",
        "## Purpose",
        "",
        "- Repair recent dominant-contract daily bars for hot universe expansion targets using the local TQSDK datafeed.",
        "- This is a data-quality step, not a strategy optimization.",
        "- Stage78-1 formal configuration is not modified.",
        "",
        "## Summary",
        "",
        f"- Target products: `{', '.join(TARGET_PRODUCTS)}`",
        f"- Dry run: `{payload['dry_run']}`",
        f"- Missing contracts before repair: `{payload['missing_contracts']}`",
        f"- Missing mapped days before repair: `{payload['missing_mapped_days_before']}`",
        f"- Covered missing days after fetch: `{payload['covered_missing_days_after_fetch']}`",
        f"- Remaining missing days after fetch: `{payload['remaining_missing_days_after_fetch']}`",
        f"- Status counts: `{payload['status_counts']}`",
        f"- Credential status: `{payload['credential_status']}`",
        "",
        "## Missing By Product",
        "",
        _to_markdown_table(product_view) if not product_view.empty else "- No missing contracts.",
        "",
        "## Repair Status",
        "",
        _to_markdown_table(status_view) if not status_view.empty else "- No repair status rows yet.",
        "",
        "## Judgement",
        "",
        "- Overfitting: no. This step only increases data observability and does not alter strategy parameters or pick products by PnL.",
        "- Continued value: yes if it reduces `recent_bar_incomplete`; otherwise the bottleneck becomes credential/data-vendor access rather than strategy design.",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Repair recent hot product daily bars through local TQSDK datafeed.")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--padding-days", type=int, default=DEFAULT_PADDING_DAYS)
    args = parser.parse_args()
    targets_df, status_df, payload = repair_contracts(
        limit=args.limit,
        force=bool(args.force),
        dry_run=bool(args.dry_run),
        padding_days=int(args.padding_days),
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    print(f"missing contracts: {MISSING_CONTRACTS_CSV_PATH}")
    print(f"repair status: {REPAIR_STATUS_CSV_PATH}")
    print(f"report: {REPORT_PATH}")


if __name__ == "__main__":
    main()
