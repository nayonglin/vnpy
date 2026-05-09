from __future__ import annotations

import argparse
import importlib.util
import json
import math
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

PROJECT_ROOT: Path = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from vnpy.trader.constant import Interval
from vnpy.trader.database import get_database
from vnpy.trader.object import HistoryRequest
from vnpy.trader.setting import SETTINGS

from qmt_universe import PRODUCT_SPECS


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

MODEL_TAG: str = "stage171_forward_market_data_update_v1"
OUTPUT_PREFIX: str = "qmt_roll_stage171_forward_market_data_update"
DEFAULT_START: str = "2026-04-22"
DEFAULT_END: str = "2026-05-07"

STATUS_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_status_{MODEL_TAG}.csv"
SUMMARY_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.json"
REPORT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

LOCAL_TQSDK_PATH: Path = PROJECT_ROOT / "vnpy_tqsdk" / "tqsdk_datafeed.py"


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


def _query_and_save(start: datetime, end: datetime, dry_run: bool) -> tuple[pd.DataFrame, dict[str, Any]]:
    TqsdkDatafeed = _load_tqsdk_datafeed_class()
    datafeed = TqsdkDatafeed()
    database = get_database()
    rows: list[dict[str, Any]] = []
    started_at = time.time()

    for spec in PRODUCT_SPECS:
        req = HistoryRequest(
            symbol=spec.product,
            exchange=spec.exchange,
            interval=Interval.DAILY,
            start=start,
            end=end,
        )
        status = "unknown"
        message = ""
        count = 0
        min_date = ""
        max_date = ""
        try:
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
                "product_vt_symbol": spec.vt_symbol,
                "product": spec.product,
                "exchange": spec.exchange.value,
                "status": status,
                "bar_count": count,
                "min_date": min_date,
                "max_date": max_date,
                "message": message,
            }
        )
        print(f"[stage171] {spec.vt_symbol} {status} bars={count} {min_date}->{max_date}", flush=True)

    status_df = pd.DataFrame(rows)
    summary = {
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "is_strategy_change": False,
        "is_backtest": False,
        "dry_run": dry_run,
        "start": start.date().isoformat(),
        "end": end.date().isoformat(),
        "product_count": int(len(status_df)),
        "saved_count": int(status_df["status"].isin(["saved", "fetched"]).sum()),
        "failed_count": int((status_df["status"] == "failed").sum()),
        "empty_count": int((status_df["status"] == "empty").sum()),
        "min_saved_date": status_df.loc[status_df["min_date"].astype(str).ne(""), "min_date"].min()
        if not status_df.empty
        else "",
        "max_saved_date": status_df.loc[status_df["max_date"].astype(str).ne(""), "max_date"].max()
        if not status_df.empty
        else "",
        "elapsed_seconds": round(time.time() - started_at, 2),
        "credential_status": _credential_status(),
        "judgement": {
            "overfit_before": "否。Stage171只补前向行情，不改策略、不生成新信号。",
            "continue_before": "是。Stage170已经证明最新日报被数据缺口阻断。",
            "overfit_after": "否。下载/入库日线不会改变Stage78参数。",
            "continue_after": "是。数据补齐后应运行冻结Stage78前向信号和Stage169目标日报。",
        },
        "outputs": {
            "status": str(STATUS_PATH),
            "summary": str(SUMMARY_PATH),
            "report": str(REPORT_PATH),
        },
    }
    return status_df, summary


def _write_report(status_df: pd.DataFrame, summary: dict[str, Any]) -> None:
    lines = [
        "# Stage171 前向行情补数",
        "",
        "## 定位",
        "",
        "- 本阶段不是策略版本，不修改Stage78参数，不触发A/B。",
        "- 目标是补齐Stage170识别出的前向日线缺口，为最新影子盘日报提供行情输入。",
        "",
        "## 运行参数",
        "",
        f"- 数据区间：`{summary['start']}` 到 `{summary['end']}`",
        f"- dry_run：`{summary['dry_run']}`",
        f"- 数据源：`{summary['credential_status']['datafeed_name']}`",
        f"- TqSdk用户名已配置：`{summary['credential_status']['username_configured']}`",
        f"- TqSdk密码已配置：`{summary['credential_status']['password_configured']}`",
        "",
        "## 补数状态",
        "",
        _to_markdown_table(
            status_df,
            ["product_vt_symbol", "status", "bar_count", "min_date", "max_date", "message"],
            max_rows=40,
        ),
        "",
        "## 汇总",
        "",
        f"- 产品数：`{summary['product_count']}`",
        f"- 成功/可用：`{summary['saved_count']}`",
        f"- 失败：`{summary['failed_count']}`",
        f"- 空数据：`{summary['empty_count']}`",
        f"- 最大补齐日期：`{summary['max_saved_date']}`",
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
        "- 重新运行Stage170确认数据缺口是否消失。",
        "- 用冻结Stage78跑到目标完整交易日，生成前向daily和理论信号。",
        "- 再运行Stage169生成最新目标日报。",
    ]
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch and save forward daily bars for Stage78 product universe.")
    parser.add_argument("--start", default=DEFAULT_START, help="Start date YYYY-MM-DD.")
    parser.add_argument("--end", default=DEFAULT_END, help="End date YYYY-MM-DD.")
    parser.add_argument("--dry-run", action="store_true", help="Fetch but do not save to database.")
    args = parser.parse_args()

    start = datetime.strptime(args.start, "%Y-%m-%d")
    end = datetime.strptime(args.end, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
    status_df, summary = _query_and_save(start, end, args.dry_run)

    status_df.to_csv(STATUS_PATH, index=False, encoding="utf-8-sig")
    SUMMARY_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    _write_report(status_df, summary)

    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    print(f"wrote: {REPORT_PATH}")


if __name__ == "__main__":
    main()
