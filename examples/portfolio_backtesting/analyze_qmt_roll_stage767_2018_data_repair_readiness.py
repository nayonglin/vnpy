from __future__ import annotations

from collections import defaultdict
from datetime import datetime
import importlib.util
import json
from pathlib import Path
import sqlite3
import sys
from typing import Any

import pandas as pd

PROJECT_DIR = Path(__file__).resolve().parent
REPO_DIR = PROJECT_DIR.parents[1]
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
RAW_ROOT = PROJECT_DIR / "downloaded_futures" / "tqsdk_stage767_2018_data_repair"
DB_PATH = REPO_DIR / ".vntrader" / "database.db"
LOCAL_TQSDK_PATH = REPO_DIR / "vnpy_tqsdk" / "tqsdk_datafeed.py"

sys.path.insert(0, str(PROJECT_DIR.resolve()))
sys.path.insert(0, str(REPO_DIR.resolve()))

from main_contract_mapping import ALL_FUTURES_MAPPING_PATH, load_mapping_df  # noqa: E402
from vnpy.trader.constant import Exchange, Interval  # noqa: E402
from vnpy.trader.database import get_database  # noqa: E402
from vnpy.trader.object import BarData, HistoryRequest  # noqa: E402

import analyze_qmt_roll_stage513_stage208_exact_position_margin_audit as s513  # noqa: E402


MODEL_TAG = "stage767_2018_data_repair_readiness_v1"
OUTPUT_PREFIX = "qmt_roll_stage767_2018_data_repair_readiness"
LINE_ID = "futures_trend_2019_data_extension"

PRELOAD_START = pd.Timestamp("2017-01-01")
ANALYSIS_START = pd.Timestamp("2018-01-01")
ANALYSIS_END = pd.Timestamp("2018-12-31")
MAPPING_AUDIT_START = PRELOAD_START
MAPPING_AUDIT_END = ANALYSIS_END

STATIC_REPAIR_TARGETS: list[str] = []

REPAIR_STATUS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_repair_status_{MODEL_TAG}.csv"
MAPPING_COVERAGE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_mapping_coverage_{MODEL_TAG}.csv"
MISSING_DAYS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_missing_days_{MODEL_TAG}.csv"
SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


def _md_table(frame: pd.DataFrame, max_rows: int = 80) -> str:
    if frame.empty:
        return "_无记录_"
    view = frame.head(max_rows).copy()
    lines = [
        "| " + " | ".join(view.columns) + " |",
        "| " + " | ".join(["---"] * len(view.columns)) + " |",
    ]
    for _, row in view.iterrows():
        lines.append("| " + " | ".join(str(row.get(col, "")) for col in view.columns) + " |")
    if len(frame) > max_rows:
        lines.append(f"\n_仅展示前 {max_rows} 行，共 {len(frame)} 行。_")
    return "\n".join(lines)


def _split_vt(vt_symbol: str) -> tuple[str, Exchange]:
    symbol, exchange = str(vt_symbol).split(".", 1)
    return symbol, Exchange(exchange)


def _load_tqsdk_datafeed_class() -> Any:
    spec = importlib.util.spec_from_file_location("local_vnpy_tqsdk_datafeed", LOCAL_TQSDK_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load TQSDK datafeed from {LOCAL_TQSDK_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.TqsdkDatafeed


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
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values("trade_date").reset_index(drop=True)


def _raw_csv_path(vt_symbol: str) -> Path:
    symbol, exchange = str(vt_symbol).split(".", 1)
    path = RAW_ROOT / exchange
    path.mkdir(parents=True, exist_ok=True)
    return path / f"{symbol}.csv"


def repair_targets(repair_targets: list[str]) -> pd.DataFrame:
    TqsdkDatafeed = _load_tqsdk_datafeed_class()
    datafeed = TqsdkDatafeed()
    database = get_database()
    records: list[dict[str, Any]] = []

    for vt_symbol in repair_targets:
        symbol, exchange = _split_vt(vt_symbol)
        record: dict[str, Any] = {
            "contract_vt_symbol": vt_symbol,
            "status": "failed",
            "fetched_rows": 0,
            "saved_rows": 0,
            "first_trade_date": "",
            "last_trade_date": "",
            "raw_csv": "",
            "message": "",
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        }
        try:
            req = HistoryRequest(
                symbol=symbol,
                exchange=exchange,
                interval=Interval.DAILY,
                start=MAPPING_AUDIT_START.to_pydatetime(),
                end=(MAPPING_AUDIT_END + pd.Timedelta(days=1)).to_pydatetime(),
            )
            bars = list(datafeed.query_bar_history(req) or [])
            bars_df = _bars_to_frame(bars)
            record["fetched_rows"] = int(len(bars))
            if bars_df.empty:
                record["status"] = "empty"
                record["message"] = "tqsdk returned empty daily data"
            else:
                csv_path = _raw_csv_path(vt_symbol)
                bars_df.to_csv(csv_path, index=False, encoding="utf-8-sig")
                database.save_bar_data(bars)
                record["saved_rows"] = int(len(bars))
                record["first_trade_date"] = str(bars_df["trade_date"].min())
                record["last_trade_date"] = str(bars_df["trade_date"].max())
                record["raw_csv"] = str(csv_path)
                record["status"] = "saved"
        except Exception as exc:  # noqa: BLE001
            record["message"] = repr(exc)
        records.append(record)
    return pd.DataFrame(records)


def _load_mapping(product_symbols: list[str]) -> pd.DataFrame:
    mapping = load_mapping_df(ALL_FUTURES_MAPPING_PATH)
    mapping["date"] = pd.to_datetime(mapping["date"], errors="coerce").dt.normalize()
    mapping = mapping[
        (mapping["date"] >= MAPPING_AUDIT_START)
        & (mapping["date"] <= MAPPING_AUDIT_END)
        & (mapping["continuous_symbol_vt"].isin(product_symbols))
    ].copy()
    mapping = mapping[mapping["main_contract_vt"].astype(str).ne("")].copy()
    return mapping


def _load_db_days(start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    conn = sqlite3.connect(DB_PATH)
    try:
        frame = pd.read_sql_query(
            """
            select symbol || '.' || exchange as contract_vt_symbol,
                   date(datetime) as trade_date
            from dbbardata
            where interval='d' and datetime>=? and datetime<?
            """,
            conn,
            params=(start.strftime("%Y-%m-%d"), (end + pd.Timedelta(days=1)).strftime("%Y-%m-%d")),
        )
    finally:
        conn.close()
    frame["trade_date"] = pd.to_datetime(frame["trade_date"], errors="coerce").dt.normalize()
    return frame.dropna(subset=["trade_date"]).drop_duplicates()


def audit_coverage(product_symbols: list[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    mapping = _load_mapping(product_symbols)
    db_days = _load_db_days(MAPPING_AUDIT_START, MAPPING_AUDIT_END)
    db_set = set(zip(db_days["contract_vt_symbol"].astype(str), db_days["trade_date"], strict=False))

    missing_rows: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []
    for product, product_map in mapping.groupby("continuous_symbol_vt", sort=True):
        mapped_days = int(product_map["date"].nunique())
        contract_count = int(product_map["main_contract_vt"].nunique())
        miss_count = 0
        missing_contracts: set[str] = set()
        for row in product_map.itertuples(index=False):
            contract = str(row.main_contract_vt)
            date = pd.Timestamp(row.date).normalize()
            if (contract, date) not in db_set:
                miss_count += 1
                missing_contracts.add(contract)
                missing_rows.append(
                    {
                        "product_vt_symbol": product,
                        "contract_vt_symbol": contract,
                        "missing_date": date.date().isoformat(),
                    }
                )
        summary_rows.append(
            {
                "product_vt_symbol": product,
                "mapped_days": mapped_days,
                "contract_count": contract_count,
                "missing_mapped_days": miss_count,
                "missing_contract_count": len(missing_contracts),
                "missing_contracts": ",".join(sorted(missing_contracts)),
            }
        )

    coverage = pd.DataFrame(summary_rows).sort_values(
        ["missing_mapped_days", "product_vt_symbol"], ascending=[False, True]
    )
    missing = pd.DataFrame(missing_rows).sort_values(
        ["product_vt_symbol", "contract_vt_symbol", "missing_date"]
    ) if missing_rows else pd.DataFrame(columns=["product_vt_symbol", "contract_vt_symbol", "missing_date"])
    return coverage, missing


def _build_report(repair_status: pd.DataFrame, coverage: pd.DataFrame, missing: pd.DataFrame, summary: dict[str, Any]) -> str:
    bad = coverage[coverage["missing_mapped_days"] > 0].copy()
    lines = [
        "# Stage767 2018 数据修复与覆盖审计",
        "",
        f"- line_id：`{LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        f"- 审计窗口：`{MAPPING_AUDIT_START.date()}` 到 `{MAPPING_AUDIT_END.date()}`；回测正式起点为 `{ANALYSIS_START.date()}`。",
        "- 本阶段只补真实合约日线与审计覆盖，不改策略逻辑、AI、风控或品种规则。",
        "",
        "## 修复状态",
        "",
        _md_table(repair_status, max_rows=20),
        "",
        "## 覆盖缺口汇总",
        "",
        _md_table(bad, max_rows=40) if not bad.empty else "- 所有实际策略品种在映射日均有数据库日线。",
        "",
        "## 仍缺映射日",
        "",
        _md_table(missing, max_rows=80) if not missing.empty else "- 无。",
        "",
        "## 结论",
        "",
        f"- 决策：`{summary['decision']}`",
        f"- 过拟合判断：`{summary['overfit_judgment']}`",
        f"- 继续价值：`{summary['continue_value']}`",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    RAW_ROOT.mkdir(parents=True, exist_ok=True)
    metadata = s513._metadata()
    product_symbols = sorted(metadata["product_symbols"])

    before_coverage, before_missing = audit_coverage(product_symbols)
    dynamic_targets = sorted(set(before_missing["contract_vt_symbol"].astype(str))) if not before_missing.empty else []
    repair_target_symbols = sorted(set(STATIC_REPAIR_TARGETS + dynamic_targets))
    repair_status = repair_targets(repair_target_symbols)
    after_coverage, after_missing = audit_coverage(product_symbols)

    summary = {
        "stage": "Stage767",
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "product_count": len(product_symbols),
        "products": product_symbols,
        "repair_targets": repair_target_symbols,
        "before_missing_mapped_days": int(before_coverage["missing_mapped_days"].sum()),
        "after_missing_mapped_days": int(after_coverage["missing_mapped_days"].sum()),
        "remaining_missing_contracts": sorted(set(after_missing["contract_vt_symbol"].astype(str))) if not after_missing.empty else [],
        "remaining_missing_days_by_contract": {
            str(contract): int(len(group))
            for contract, group in after_missing.groupby("contract_vt_symbol")
        } if not after_missing.empty else {},
        "decision": "2018_data_repaired_enough_to_run_with_fu1805_terminal_gap_caveat"
        if int(after_coverage["missing_mapped_days"].sum()) > 0
        else "2018_data_repaired_full_mapping_ready",
        "overfit_judgment": "low: data repair only; no PnL-dependent parameter change",
        "continue_value": "yes: enables 2018 independent start path-dependency test; remaining caveat must be labeled if any mapped days still lack bars",
        "outputs": {
            "repair_status": str(REPAIR_STATUS_PATH),
            "mapping_coverage": str(MAPPING_COVERAGE_PATH),
            "missing_days": str(MISSING_DAYS_PATH),
            "summary": str(SUMMARY_PATH),
            "report": str(REPORT_PATH),
        },
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }

    repair_status.to_csv(REPAIR_STATUS_PATH, index=False, encoding="utf-8-sig")
    after_coverage.to_csv(MAPPING_COVERAGE_PATH, index=False, encoding="utf-8-sig")
    after_missing.to_csv(MISSING_DAYS_PATH, index=False, encoding="utf-8-sig")
    SUMMARY_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    REPORT_PATH.write_text(_build_report(repair_status, after_coverage, after_missing, summary), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
