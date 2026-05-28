from __future__ import annotations

import json
import math
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from tqsdk import TqApi, TqAuth
from tqsdk.tools import DataDownloader
from vnpy.trader.setting import SETTINGS
from vnpy.trader.utility import ZoneInfo


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
RAW_ROOT = PROJECT_DIR / "downloaded_futures" / "tqsdk_stage445_priority_minute_probe"

MODEL_TAG = "stage445_tqsdk_priority_minute_probe_v1"
OUTPUT_PREFIX = "qmt_roll_stage445_tqsdk_priority_minute_probe"
LINE_ID = "futures_trend_drawdown30_preserve_return"

PRIORITY_TARGETS_PATH = (
    OUTPUT_DIR
    / "qmt_roll_stage444_intraday_proxy_data_readiness_priority_targets_stage444_intraday_proxy_data_readiness_v1.csv"
)
SYMBOL_PLAN_PATH = (
    OUTPUT_DIR
    / "qmt_roll_stage444_intraday_proxy_data_readiness_symbol_download_plan_stage444_intraday_proxy_data_readiness_v1.csv"
)

STATUS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_download_status_{MODEL_TAG}.csv"
COVERAGE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_priority_window_coverage_{MODEL_TAG}.csv"
SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_coverage_summary_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

CHINA_TZ = ZoneInfo("Asia/Shanghai")
MAX_SYMBOLS = int(os.getenv("STAGE445_MAX_SYMBOLS", "35"))
PER_SYMBOL_TIMEOUT_SECONDS = int(os.getenv("STAGE445_PER_SYMBOL_TIMEOUT_SECONDS", "90"))
SLEEP_SECONDS = float(os.getenv("STAGE445_SLEEP_SECONDS", "0.05"))


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        result = float(value)
        return None if math.isnan(result) or math.isinf(result) else result
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    return value


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "无数据。"
    view = frame.copy()
    if max_rows is not None:
        view = view.head(max_rows)
    for column in view.columns:
        if pd.api.types.is_float_dtype(view[column]):
            view[column] = view[column].map(lambda value: f"{value:.4f}" if pd.notna(value) else "")
    return view.to_markdown(index=False)


def _require_credentials() -> tuple[str, str]:
    username = str(SETTINGS.get("datafeed.username", ""))
    password = str(SETTINGS.get("datafeed.password", ""))
    if not username or not password:
        raise RuntimeError("TqSdk credentials are missing in vn.py SETTINGS.")
    return username, password


def _load_inputs() -> tuple[pd.DataFrame, pd.DataFrame]:
    targets = pd.read_csv(PRIORITY_TARGETS_PATH, encoding="utf-8-sig")
    plan = pd.read_csv(SYMBOL_PLAN_PATH, encoding="utf-8-sig")
    for column in ["decision_date", "next_trade_date", "target_start", "target_end"]:
        targets[column] = pd.to_datetime(targets[column], errors="coerce").dt.tz_localize(None)
    targets["abs_next_open_adverse_cash"] = pd.to_numeric(
        targets["abs_next_open_adverse_cash"], errors="coerce"
    ).fillna(0.0)
    targets["calendar_validation_required"] = pd.to_numeric(
        targets.get("calendar_validation_required", 0), errors="coerce"
    ).fillna(0).astype(int)
    return targets.dropna(subset=["vt_symbol", "target_start", "target_end"]).copy(), plan


def _selected_symbols(targets: pd.DataFrame, plan: pd.DataFrame) -> pd.DataFrame:
    symbol_rows = (
        targets.groupby(["vt_symbol", "product_vt_symbol"], sort=True)
        .agg(
            target_start=("target_start", "min"),
            target_end=("target_end", "max"),
            priority_targets=("trade_id", "count"),
            unique_trades=("trade_id", "nunique"),
            max_abs_next_open_adverse_cash=("abs_next_open_adverse_cash", "max"),
            calendar_validation_targets=("calendar_validation_required", "sum"),
        )
        .reset_index()
    )
    if not plan.empty and "suggested_tqsdk_symbol" in plan.columns:
        symbol_rows = symbol_rows.merge(
            plan[["vt_symbol", "suggested_tqsdk_symbol"]],
            on="vt_symbol",
            how="left",
        )
    else:
        symbol_rows["suggested_tqsdk_symbol"] = symbol_rows["vt_symbol"].map(_to_tqsdk_symbol)
    symbol_rows["suggested_tqsdk_symbol"] = symbol_rows["suggested_tqsdk_symbol"].fillna(
        symbol_rows["vt_symbol"].map(_to_tqsdk_symbol)
    )
    symbol_rows = symbol_rows.sort_values(
        ["priority_targets", "max_abs_next_open_adverse_cash"],
        ascending=[False, False],
    ).reset_index(drop=True)
    if MAX_SYMBOLS > 0:
        symbol_rows = symbol_rows.head(MAX_SYMBOLS).copy()
    return symbol_rows


def _to_tqsdk_symbol(vt_symbol: str) -> str:
    symbol, exchange = str(vt_symbol).split(".", 1)
    return f"{exchange}.{symbol}"


def _csv_path_for_symbol(tq_symbol: str) -> Path:
    exchange, symbol = tq_symbol.split(".", 1)
    return RAW_ROOT / exchange / f"{symbol}_minute.csv"


def _download_one_symbol(api: TqApi, row: Any) -> dict[str, Any]:
    tq_symbol = str(row.suggested_tqsdk_symbol)
    csv_path = _csv_path_for_symbol(tq_symbol)
    csv_path.parent.mkdir(parents=True, exist_ok=True)

    start_dt = pd.Timestamp(row.target_start).to_pydatetime()
    end_dt = pd.Timestamp(row.target_end).to_pydatetime()

    status = {
        "vt_symbol": str(row.vt_symbol),
        "tq_symbol": tq_symbol,
        "target_start": pd.Timestamp(row.target_start),
        "target_end": pd.Timestamp(row.target_end),
        "priority_targets": int(row.priority_targets),
        "unique_trades": int(row.unique_trades),
        "max_abs_next_open_adverse_cash": float(row.max_abs_next_open_adverse_cash),
        "calendar_validation_targets": int(row.calendar_validation_targets),
        "csv_path": str(csv_path),
        "status": "unknown",
        "progress": 0.0,
        "rows": 0,
        "elapsed_seconds": 0.0,
        "message": "",
    }

    started = time.time()
    try:
        downloader = DataDownloader(
            api,
            symbol_list=tq_symbol,
            dur_sec=60,
            start_dt=start_dt,
            end_dt=end_dt,
            csv_file_name=str(csv_path),
        )
        while not downloader.is_finished():
            api.wait_update()
            status["progress"] = float(downloader.get_progress())
            if time.time() - started > PER_SYMBOL_TIMEOUT_SECONDS:
                status["status"] = "timeout"
                status["message"] = f"timeout_after_{PER_SYMBOL_TIMEOUT_SECONDS}s"
                break
            if SLEEP_SECONDS > 0:
                time.sleep(SLEEP_SECONDS)
        if status["status"] != "timeout":
            status["progress"] = float(downloader.get_progress())
            status["status"] = "downloaded" if csv_path.exists() and csv_path.stat().st_size > 0 else "empty"
            if status["status"] == "empty":
                status["message"] = "empty_or_missing_csv"
    except Exception as exc:
        status["status"] = "failed"
        status["message"] = repr(exc)

    status["elapsed_seconds"] = round(time.time() - started, 2)
    if csv_path.exists() and csv_path.stat().st_size > 0:
        try:
            status["rows"] = int(len(pd.read_csv(csv_path)))
        except Exception as exc:
            status["message"] = f"{status['message']} read_rows_failed={exc!r}".strip()
    return status


def _normalize_downloaded_datetime(frame: pd.DataFrame) -> pd.Series:
    raw = frame["datetime"]
    if pd.api.types.is_numeric_dtype(raw):
        dt = pd.to_datetime(raw, unit="ns", errors="coerce", utc=True).dt.tz_convert(CHINA_TZ).dt.tz_localize(None)
    else:
        dt = pd.to_datetime(raw, errors="coerce")
        if getattr(dt.dt, "tz", None) is not None:
            dt = dt.dt.tz_convert(CHINA_TZ).dt.tz_localize(None)
    return dt


def _coverage_for_downloads(targets: pd.DataFrame, status: pd.DataFrame) -> pd.DataFrame:
    status_map = status.set_index("vt_symbol").to_dict("index") if not status.empty else {}
    rows: list[dict[str, Any]] = []
    bar_cache: dict[str, pd.DataFrame] = {}

    for row in targets.itertuples(index=False):
        vt_symbol = str(row.vt_symbol)
        stat = status_map.get(vt_symbol, {})
        csv_path = Path(str(stat.get("csv_path", "")))
        bars = bar_cache.get(vt_symbol)
        if bars is None:
            if csv_path.exists() and csv_path.stat().st_size > 0:
                try:
                    bars = pd.read_csv(csv_path)
                    if "datetime" in bars.columns:
                        bars["bar_datetime"] = _normalize_downloaded_datetime(bars)
                    else:
                        bars["bar_datetime"] = pd.NaT
                except Exception:
                    bars = pd.DataFrame(columns=["bar_datetime"])
            else:
                bars = pd.DataFrame(columns=["bar_datetime"])
            bar_cache[vt_symbol] = bars

        start = pd.Timestamp(row.target_start)
        end = pd.Timestamp(row.target_end)
        if bars.empty:
            count = 0
        else:
            mask = (bars["bar_datetime"] >= start) & (bars["bar_datetime"] < end)
            count = int(mask.sum())

        rows.append(
            {
                "trade_id": str(row.trade_id),
                "vt_symbol": vt_symbol,
                "proxy_type": str(row.proxy_type),
                "target_start": start,
                "target_end": end,
                "abs_next_open_adverse_cash": float(row.abs_next_open_adverse_cash),
                "calendar_validation_required": int(row.calendar_validation_required),
                "download_status": str(stat.get("status", "not_selected")),
                "csv_path": str(csv_path) if csv_path else "",
                "minute_bar_count": count,
                "covered": int(count > 0),
            }
        )
    return pd.DataFrame(rows)


def _coverage_summary(coverage: pd.DataFrame, status: pd.DataFrame) -> pd.DataFrame:
    rows = [
        {
            "bucket_type": "all_selected_priority_targets",
            "bucket": "all",
            "required_targets": int(len(coverage)),
            "covered_targets": int(coverage["covered"].sum()) if not coverage.empty else 0,
            "coverage_rate": float(coverage["covered"].mean()) if not coverage.empty else 0.0,
            "downloaded_symbols": int((status["status"] == "downloaded").sum()) if not status.empty else 0,
            "failed_symbols": int((status["status"] == "failed").sum()) if not status.empty else 0,
            "timeout_symbols": int((status["status"] == "timeout").sum()) if not status.empty else 0,
        }
    ]
    if not coverage.empty:
        for keys in [["vt_symbol"], ["proxy_type"], ["calendar_validation_required"], ["download_status"]]:
            group = (
                coverage.groupby(keys, sort=True)
                .agg(
                    required_targets=("trade_id", "count"),
                    covered_targets=("covered", "sum"),
                    max_abs_next_open_adverse_cash=("abs_next_open_adverse_cash", "max"),
                )
                .reset_index()
            )
            group["coverage_rate"] = group["covered_targets"] / group["required_targets"]
            group["bucket_type"] = "+".join(keys)
            group["bucket"] = group[keys].astype(str).agg("|".join, axis=1)
            group["downloaded_symbols"] = np.nan
            group["failed_symbols"] = np.nan
            group["timeout_symbols"] = np.nan
            rows.extend(
                group[
                    [
                        "bucket_type",
                        "bucket",
                        "required_targets",
                        "covered_targets",
                        "coverage_rate",
                        "downloaded_symbols",
                        "failed_symbols",
                        "timeout_symbols",
                        "max_abs_next_open_adverse_cash",
                    ]
                ].to_dict("records")
            )
    return pd.DataFrame(rows)


def _decision(status: pd.DataFrame, coverage: pd.DataFrame, selected_count: int) -> dict[str, Any]:
    required = int(len(coverage))
    covered = int(coverage["covered"].sum()) if required else 0
    coverage_rate = float(covered / required) if required else 0.0
    downloaded = int((status["status"] == "downloaded").sum()) if not status.empty else 0
    failed = int(status["status"].isin(["failed", "timeout"]).sum()) if not status.empty else 0
    permission_blocked = (
        int(status["message"].astype(str).str.contains("不支持下载历史数据功能|tqsdk-buy", regex=True).sum())
        if not status.empty and "message" in status.columns
        else 0
    )
    if permission_blocked and permission_blocked == selected_count:
        label = "tqsdk_history_download_permission_blocked"
    elif required and covered == required:
        label = "priority_minute_data_ready_for_proxy_rebuild"
    elif covered > 0:
        label = "partial_priority_minute_data_downloaded_calendar_or_session_gap"
    else:
        label = "priority_minute_download_failed_or_no_target_windows_covered"
    return {
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "decision": label,
        "selected_symbols": selected_count,
        "downloaded_symbols": downloaded,
        "failed_or_timeout_symbols": failed,
        "permission_blocked_symbols": permission_blocked,
        "required_priority_targets": required,
        "covered_priority_targets": covered,
        "coverage_rate": coverage_rate,
        "raw_root": str(RAW_ROOT),
        "outputs": {
            "download_status": str(STATUS_PATH),
            "priority_window_coverage": str(COVERAGE_PATH),
            "coverage_summary": str(SUMMARY_PATH),
            "report": str(REPORT_PATH),
        },
        "next_step": "若高优先级窗口覆盖可用，Stage146 用下载的分钟线重构代理成交价；若大量窗口仍缺失，先处理交易日历/夜盘会话映射。",
    }


def _write_report(status: pd.DataFrame, coverage: pd.DataFrame, summary: pd.DataFrame, decision: dict[str, Any]) -> None:
    top_missing = (
        coverage[coverage["covered"].eq(0)]
        .sort_values("abs_next_open_adverse_cash", ascending=False)
        .head(40)
        if not coverage.empty
        else pd.DataFrame()
    )
    report = [
        "# Stage145 TqSdk高优先级分钟线采样探针",
        "",
        f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "- 阶段性质：执行数据采样探针；不修改策略规则，不导入vn.py数据库。",
        f"- 最大采样合约数：`{MAX_SYMBOLS}`。",
        f"- 单合约超时秒数：`{PER_SYMBOL_TIMEOUT_SECONDS}`。",
        "",
        "## 外部调研判断",
        "",
        "- TqSdk `DataDownloader` 支持按合约、周期、起止时间下载历史数据；本阶段使用 `dur_sec=60`。",
        "- 该工具可以验证分钟线历史采样是否可行，但不能替代执行撮合模型；后续仍需用采样价重构订单路径。",
        "",
        "## 下载状态",
        "",
        _md_table(status, max_rows=80),
        "",
        "## 覆盖摘要",
        "",
        _md_table(summary, max_rows=100),
        "",
        "## 未覆盖高冲击窗口样例",
        "",
        _md_table(top_missing, max_rows=40),
        "",
        "## 决策",
        "",
        f"- 决策标签：`{decision['decision']}`。",
        f"- 选中合约数：`{decision['selected_symbols']}`。",
        f"- 成功下载合约数：`{decision['downloaded_symbols']}`。",
        f"- 失败/超时合约数：`{decision['failed_or_timeout_symbols']}`。",
        f"- TqSdk历史下载权限阻断合约数：`{decision['permission_blocked_symbols']}`。",
        f"- 目标窗口：`{decision['required_priority_targets']}`。",
        f"- 已覆盖窗口：`{decision['covered_priority_targets']}`。",
        f"- 覆盖率：`{decision['coverage_rate']:.4%}`。",
        "",
        "## 结论",
        "",
        "- 本阶段不产生新策略候选，也不证明 Stage103 可执行。",
        "- 若所有合约返回 TqSdk 历史下载权限不足，结论应记为数据权限阻断，而不是分钟线不存在。",
        "- 若高优先级窗口能覆盖，下一步用真实分钟线重构 `14:55/20:55/21:00/08:55/09:00` 代理成交价。",
        "- 若日盘周末标签窗口未覆盖，不直接视作数据失败，必须先用交易所实际交易日历校正。",
        "",
        "## 过拟合与继续价值反思",
        "",
        "- 运行前过拟合反思：否。只补执行数据，不筛交易规则。",
        "- 运行后过拟合反思：否。覆盖失败只影响数据路径，不作为过滤日期/品种的依据。",
        "- 运行前继续价值反思：是。分钟线是 Stage103 是否能进真实 paper 的硬前置。",
        "- 运行后继续价值反思：取决于覆盖率；若覆盖可用，应继续做代理成交价重构。",
    ]
    REPORT_PATH.write_text("\n".join(report), encoding="utf-8")


def main() -> None:
    targets, plan = _load_inputs()
    selected = _selected_symbols(targets, plan)
    selected_targets = targets[targets["vt_symbol"].isin(set(selected["vt_symbol"]))].copy()

    username, password = _require_credentials()
    RAW_ROOT.mkdir(parents=True, exist_ok=True)

    api = TqApi(auth=TqAuth(username, password))
    status_rows: list[dict[str, Any]] = []
    try:
        for row in selected.itertuples(index=False):
            result = _download_one_symbol(api, row)
            status_rows.append(result)
            pd.DataFrame(status_rows).to_csv(STATUS_PATH, index=False, encoding="utf-8-sig")
            print(
                f"{result['status']} {result['vt_symbol']} {result['tq_symbol']} "
                f"rows={result['rows']} progress={result['progress']:.4f}",
                flush=True,
            )
    finally:
        api.close()

    status = pd.DataFrame(status_rows)
    coverage = _coverage_for_downloads(selected_targets, status)
    summary = _coverage_summary(coverage, status)
    decision = _decision(status, coverage, len(selected))

    status.to_csv(STATUS_PATH, index=False, encoding="utf-8-sig")
    coverage.to_csv(COVERAGE_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(status, coverage, summary, decision)

    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), flush=True)
    print(f"wrote: {REPORT_PATH}", flush=True)


if __name__ == "__main__":
    main()
