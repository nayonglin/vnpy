from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import re
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from tqsdk import TqAuth
from tqsdk.calendar import TqContCalendar

PROJECT_ROOT: Path = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from vnpy.trader.constant import Exchange, Interval
from vnpy.trader.database import get_database
from vnpy.trader.object import HistoryRequest
from vnpy.trader.setting import SETTINGS

from main_contract_mapping import ALL_FUTURES_MAPPING_PATH, load_product_universe_symbols
from qmt_roll_official_stage78_config import OFFICIAL_STAGE78_VERSION, build_official_stage78_paths


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

MODEL_TAG: str = "stage173_forward_main_contract_data_update_v1"
OUTPUT_PREFIX: str = "qmt_roll_stage173_forward_main_contract_data_update"

DEFAULT_MAPPING_START: str = "2026-05-01"
DEFAULT_BAR_START: str = "2026-04-22"
DEFAULT_END: str = "2026-05-07"

STATUS_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_contract_bar_status_{MODEL_TAG}.csv"
MAPPING_APPEND_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_mapping_rows_{MODEL_TAG}.csv"
SUMMARY_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.json"
REPORT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

LOCAL_TQSDK_PATH: Path = PROJECT_ROOT / "vnpy_tqsdk" / "tqsdk_datafeed.py"
WIDE_MAPPING_PATH: Path = OUTPUT_DIR / "tqsdk_all_futures_main_contract_mapping_wide_2010_2026_04.csv"
SUMMARY_MAPPING_PATH: Path = OUTPUT_DIR / "tqsdk_all_futures_main_contract_mapping_summary_2010_2026_04.json"


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if pd.isna(result) or math.isinf(result):
        return default
    return result


def _fmt(value: Any, digits: int = 4) -> str:
    if isinstance(value, (int, np.integer)):
        return f"{int(value):,}"
    numeric = _safe_float(value, default=float("nan"))
    if math.isnan(numeric):
        return str(value)
    if abs(numeric) >= 1000:
        return f"{numeric:,.0f}"
    return f"{numeric:.{digits}f}"


def _to_markdown_table(df: pd.DataFrame, columns: list[str] | None = None, max_rows: int = 40) -> str:
    if df.empty:
        return "_No rows._"
    view = df.copy()
    if columns is not None:
        view = view.loc[:, [column for column in columns if column in view.columns]]
    view = view.head(max_rows).copy()
    for column in view.columns:
        if pd.api.types.is_numeric_dtype(view[column]):
            view[column] = view[column].map(_fmt)
    return "\n".join(
        [
            "| " + " | ".join(view.columns) + " |",
            "| " + " | ".join(["---"] * len(view.columns)) + " |",
            *["| " + " | ".join(map(str, row)) + " |" for row in view.to_numpy()],
        ]
    )


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


def _normalize_product(product: str, exchange: str) -> str:
    if exchange in {"CZCE", "CFFEX"}:
        return product.upper()
    return product.lower()


def _tq_to_vt_symbol(tq_symbol: str) -> str:
    if not tq_symbol:
        return ""
    exchange, symbol = tq_symbol.split(".", 1)
    return f"{symbol}.{exchange}"


def _split_product_vt(product_vt: str) -> tuple[str, str]:
    product, exchange = product_vt.split(".", 1)
    return product, exchange


def _split_contract_vt(vt_symbol: str) -> tuple[str, Exchange]:
    symbol, exchange = vt_symbol.split(".", 1)
    return symbol, Exchange(exchange)


def _official_universe() -> list[str]:
    universe_path, _ = build_official_stage78_paths()
    symbols = load_product_universe_symbols(universe_path)
    if not symbols:
        raise RuntimeError(f"empty official Stage78 universe: {universe_path}")
    return symbols


def _fetch_mapping_rows(product_symbols: list[str], mapping_start: date, end: date) -> pd.DataFrame:
    username = str(SETTINGS["datafeed.username"] or "")
    password = str(SETTINGS["datafeed.password"] or "")
    if not username or not password:
        raise RuntimeError("missing TqSdk credentials in vn.py settings")

    product_rows: list[dict[str, str]] = []
    for product_vt in product_symbols:
        product, exchange = _split_product_vt(product_vt)
        continuous_symbol_tq = f"KQ.m@{exchange}.{_normalize_product(product, exchange)}"
        product_rows.append(
            {
                "product": product,
                "exchange": exchange,
                "continuous_symbol_tq": continuous_symbol_tq,
                "continuous_symbol_vt": product_vt,
            }
        )

    auth = TqAuth(username, password)
    auth.login()
    tq_symbols = [row["continuous_symbol_tq"] for row in product_rows]
    calendar_end = end + timedelta(days=14)
    calendar = TqContCalendar(
        start_dt=mapping_start,
        end_dt=calendar_end,
        symbols=tq_symbols,
        headers=auth._base_headers,
    )
    calendar_df = calendar.df.copy()

    trading_dates = sorted(
        {
            (value.date() if hasattr(value, "date") else value).isoformat()
            for value in calendar_df["date"].tolist()
        }
    )
    next_dates = [value for value in trading_dates if value > end.isoformat()]
    if not next_dates:
        raise RuntimeError(
            "tqsdk_forward_trading_calendar_missing_next_session"
        )
    forward_calendar = {
        "source": "tqsdk.TqContCalendar",
        "calendar_start": mapping_start.isoformat(),
        "calendar_end": calendar_end.isoformat(),
        "completed_target_date": end.isoformat(),
        "next_trading_session_date": next_dates[0],
        "trading_date_count": len(trading_dates),
        "trading_dates_sha256": hashlib.sha256(
            json.dumps(
                trading_dates,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest(),
    }

    rows: list[dict[str, str]] = []
    product_by_tq = {row["continuous_symbol_tq"]: row for row in product_rows}
    for _, row in calendar_df.iterrows():
        trade_date = row["date"].date() if hasattr(row["date"], "date") else row["date"]
        if trade_date > end:
            continue
        for tq_symbol in tq_symbols:
            info = product_by_tq[tq_symbol]
            underlying = str(row[tq_symbol] or "")
            rows.append(
                {
                    "date": trade_date.isoformat(),
                    "product": info["product"],
                    "exchange": info["exchange"],
                    "continuous_symbol_tq": tq_symbol,
                    "continuous_symbol_vt": info["continuous_symbol_vt"],
                    "main_contract_tq": underlying,
                    "main_contract_vt": _tq_to_vt_symbol(underlying) if underlying else "",
                }
            )

    mapping_rows = pd.DataFrame(rows)
    mapping_rows.sort_values(["date", "exchange", "product"], inplace=True)
    mapping_rows.reset_index(drop=True, inplace=True)
    mapping_rows.attrs["forward_calendar"] = forward_calendar
    return mapping_rows


def _update_mapping_file(mapping_rows: pd.DataFrame, product_symbols: list[str], mapping_start: date, end: date) -> dict[str, Any]:
    if not ALL_FUTURES_MAPPING_PATH.exists():
        raise FileNotFoundError(f"missing mapping file: {ALL_FUTURES_MAPPING_PATH}")

    existing = pd.read_csv(ALL_FUTURES_MAPPING_PATH)
    existing["date"] = pd.to_datetime(existing["date"]).dt.strftime("%Y-%m-%d")
    existing["continuous_symbol_vt"] = existing["continuous_symbol_vt"].astype(str)

    start_s = mapping_start.isoformat()
    end_s = end.isoformat()
    replace_mask = (
        existing["continuous_symbol_vt"].isin(product_symbols)
        & existing["date"].between(start_s, end_s)
    )
    replaced_rows = int(replace_mask.sum())
    combined = pd.concat([existing.loc[~replace_mask].copy(), mapping_rows], ignore_index=True)
    combined["date"] = pd.to_datetime(combined["date"]).dt.strftime("%Y-%m-%d")
    combined.sort_values(["date", "exchange", "product"], inplace=True)
    combined.drop_duplicates(subset=["date", "continuous_symbol_vt"], keep="last", inplace=True)
    combined.to_csv(ALL_FUTURES_MAPPING_PATH, index=False, encoding="utf-8-sig")

    wide = combined.pivot(index="date", columns="continuous_symbol_vt", values="main_contract_vt")
    wide.to_csv(WIDE_MAPPING_PATH, encoding="utf-8-sig")
    mapping_summary = {
        "products": int(combined["continuous_symbol_vt"].nunique()),
        "rows": int(len(combined)),
        "start": str(combined["date"].min()),
        "end": str(combined["date"].max()),
        "latest_contract_count": int(
            combined.loc[combined["date"] == combined["date"].max(), "main_contract_vt"].replace("", np.nan).nunique()
        ),
        "stage173_note": "Stage173 appended/replaced official Stage78 universe rows through the forward target date.",
        "updated_at": datetime.now().isoformat(timespec="minutes"),
    }
    SUMMARY_MAPPING_PATH.write_text(json.dumps(mapping_summary, ensure_ascii=False, indent=2), encoding="utf-8")
    mapping_rows.to_csv(MAPPING_APPEND_PATH, index=False, encoding="utf-8-sig")

    return {
        "mapping_path": str(ALL_FUTURES_MAPPING_PATH),
        "wide_mapping_path": str(WIDE_MAPPING_PATH),
        "mapping_summary_path": str(SUMMARY_MAPPING_PATH),
        "mapping_rows_path": str(MAPPING_APPEND_PATH),
        "mapping_rows": int(len(mapping_rows)),
        "replaced_rows": replaced_rows,
        "combined_rows": int(len(combined)),
        "combined_max_date": str(combined["date"].max()),
    }


def _fetch_and_save_contract_bars(contract_symbols: list[str], bar_start: datetime, end: datetime, dry_run: bool) -> pd.DataFrame:
    TqsdkDatafeed = _load_tqsdk_datafeed_class()
    datafeed = TqsdkDatafeed()
    database = get_database()
    rows: list[dict[str, Any]] = []

    for vt_symbol in contract_symbols:
        status = "unknown"
        message = ""
        count = 0
        min_date = ""
        max_date = ""
        try:
            symbol, exchange = _split_contract_vt(vt_symbol)
            req = HistoryRequest(
                symbol=symbol,
                exchange=exchange,
                interval=Interval.DAILY,
                start=bar_start,
                end=end,
            )
            bars = datafeed.query_bar_history(req)
            count = len(bars) if bars else 0
            if not bars:
                status = "empty"
                message = "no bars returned"
            else:
                dates = [bar.datetime.date().isoformat() for bar in bars]
                min_date = min(dates)
                max_date = max(dates)
                if not dry_run:
                    database.save_bar_data(bars)
                status = "fetched" if dry_run else "saved"
                message = "dry_run" if dry_run else ""
        except Exception as exc:
            status = "failed"
            message = repr(exc)

        rows.append(
            {
                "main_contract_vt": vt_symbol,
                "status": status,
                "bar_count": count,
                "min_date": min_date,
                "max_date": max_date,
                "message": message,
            }
        )
        print(f"[stage173] {vt_symbol} {status} bars={count} {min_date}->{max_date}", flush=True)

    status_df = pd.DataFrame(rows)
    status_df.sort_values(["status", "main_contract_vt"], inplace=True)
    status_df.to_csv(STATUS_PATH, index=False, encoding="utf-8-sig")
    return status_df


def _contracts_from_mapping(product_symbols: list[str], bar_start: date, end: date) -> list[str]:
    mapping = pd.read_csv(ALL_FUTURES_MAPPING_PATH)
    mapping["date"] = pd.to_datetime(mapping["date"]).dt.strftime("%Y-%m-%d")
    mapping["continuous_symbol_vt"] = mapping["continuous_symbol_vt"].astype(str)
    mapping["main_contract_vt"] = mapping["main_contract_vt"].fillna("").astype(str)
    selected = mapping[
        mapping["continuous_symbol_vt"].isin(product_symbols)
        & mapping["date"].between(bar_start.isoformat(), end.isoformat())
        & mapping["main_contract_vt"].ne("")
    ].copy()
    return sorted(selected["main_contract_vt"].dropna().astype(str).unique().tolist())


def _write_report(status_df: pd.DataFrame, summary: dict[str, Any]) -> None:
    lines = [
        "# Stage173 前向主力合约数据补齐",
        "",
        "## 定位",
        "",
        "- 本阶段不是策略版本，不修改Stage78参数，不触发A/B。",
        "- 目的：把Stage78前向影子盘所需的主力映射和真实主力合约日线补齐。",
        "",
        "## 参数",
        "",
        f"- 策略基准：`{OFFICIAL_STAGE78_VERSION}`",
        f"- 主力映射区间：`{summary['mapping_start']}` 到 `{summary['end']}`",
        f"- 合约K线区间：`{summary['bar_start']}` 到 `{summary['end']}`",
        f"- dry_run：`{summary['dry_run']}`",
        f"- 官方产品数：`{summary['product_count']}`",
        f"- 涉及主力合约数：`{summary['contract_count']}`",
        "",
        "## 映射更新",
        "",
        f"- 新映射行数：`{summary['mapping_update']['mapping_rows']}`",
        f"- 替换旧行数：`{summary['mapping_update']['replaced_rows']}`",
        f"- 映射文件最大日期：`{summary['mapping_update']['combined_max_date']}`",
        "",
        "## 合约K线状态",
        "",
        _to_markdown_table(status_df, ["main_contract_vt", "status", "bar_count", "min_date", "max_date", "message"], 80),
        "",
        "## 汇总",
        "",
        f"- 成功/可用：`{summary['saved_count']}`",
        f"- 失败：`{summary['failed_count']}`",
        f"- 空数据：`{summary['empty_count']}`",
        f"- 最大保存日期：`{summary['max_saved_date']}`",
        f"- 耗时秒：`{summary['elapsed_seconds']}`",
        "",
        "## 反思",
        "",
        f"- 运行前过拟合反思：{summary['judgement']['overfit_before']}",
        f"- 运行前继续价值反思：{summary['judgement']['continue_before']}",
        f"- 运行后过拟合反思：{summary['judgement']['overfit_after']}",
        f"- 运行后继续价值反思：{summary['judgement']['continue_after']}",
        "",
        "## 下一步",
        "",
        "- 重跑Stage172，验证冻结Stage78是否能生成目标日 `2026-05-07` 的前向日报。",
        "- 若仍然缺日，继续检查vn.py数据库中目标主力合约日线覆盖，而不是修改策略参数。",
    ]
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Stage173 forward main contract mapping and bar updater.")
    parser.add_argument("--mapping-start", default=DEFAULT_MAPPING_START)
    parser.add_argument("--bar-start", default=DEFAULT_BAR_START)
    parser.add_argument("--end", default=DEFAULT_END)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    started_at = time.time()
    mapping_start = datetime.strptime(args.mapping_start, "%Y-%m-%d").date()
    bar_start_date = datetime.strptime(args.bar_start, "%Y-%m-%d").date()
    end_date = datetime.strptime(args.end, "%Y-%m-%d").date()
    if mapping_start > end_date:
        raise ValueError("mapping-start must be <= end")
    if bar_start_date > end_date:
        raise ValueError("bar-start must be <= end")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    product_symbols = _official_universe()
    mapping_rows = _fetch_mapping_rows(product_symbols, mapping_start, end_date)
    forward_calendar = dict(mapping_rows.attrs.get("forward_calendar", {}))
    mapping_update = _update_mapping_file(mapping_rows, product_symbols, mapping_start, end_date)
    contract_symbols = _contracts_from_mapping(product_symbols, bar_start_date, end_date)
    status_df = _fetch_and_save_contract_bars(
        contract_symbols,
        datetime.combine(bar_start_date, datetime.min.time()),
        datetime.combine(end_date, datetime.min.time()),
        bool(args.dry_run),
    )

    nonempty_dates = status_df.loc[status_df["max_date"].astype(str).ne(""), "max_date"]
    summary = {
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "is_strategy_change": False,
        "is_backtest": False,
        "dry_run": bool(args.dry_run),
        "official_version": OFFICIAL_STAGE78_VERSION,
        "mapping_start": mapping_start.isoformat(),
        "bar_start": bar_start_date.isoformat(),
        "end": end_date.isoformat(),
        "product_count": int(len(product_symbols)),
        "contract_count": int(len(contract_symbols)),
        "saved_count": int(status_df["status"].isin(["saved", "fetched"]).sum()) if not status_df.empty else 0,
        "failed_count": int((status_df["status"] == "failed").sum()) if not status_df.empty else 0,
        "empty_count": int((status_df["status"] == "empty").sum()) if not status_df.empty else 0,
        "max_saved_date": str(nonempty_dates.max()) if not nonempty_dates.empty else "",
        "elapsed_seconds": round(time.time() - started_at, 2),
        "credential_status": _credential_status(),
        "mapping_update": mapping_update,
        "forward_trading_calendar": forward_calendar,
        "judgement": {
            "overfit_before": "否。Stage173只补主力映射和真实合约行情，不改信号、参数或筛选规则。",
            "continue_before": "是。Stage172证明回测仍停在2026-04-21，断点在数据链而不是日报模板。",
            "overfit_after": "否。补数扩大可观测前向区间，不参与挑参。",
            "continue_after": "是。若目标日数据闭环通过，才能开始真正的影子盘日报和QMT只读对账。",
        },
        "outputs": {
            "status": str(STATUS_PATH),
            "mapping_rows": str(MAPPING_APPEND_PATH),
            "summary": str(SUMMARY_PATH),
            "report": str(REPORT_PATH),
        },
    }

    SUMMARY_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(status_df, summary)

    print(f"summary json: {SUMMARY_PATH}")
    print(f"report: {REPORT_PATH}")
    print(f"status csv: {STATUS_PATH}")
    print(f"mapping rows csv: {MAPPING_APPEND_PATH}")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
