from __future__ import annotations

import json
import math
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from tqsdk import BacktestFinished, TqApi, TqAuth, TqBacktest, TqSim
from vnpy.trader.setting import SETTINGS
from vnpy.trader.utility import ZoneInfo


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
RAW_ROOT = PROJECT_DIR / "downloaded_futures" / "tqsdk_stage446_backtest_minute_proxy_extract"

MODEL_TAG = "stage446_tqsdk_backtest_minute_proxy_extract_v1"
OUTPUT_PREFIX = "qmt_roll_stage446_tqsdk_backtest_minute_proxy_extract"
LINE_ID = "futures_trend_drawdown30_preserve_return"

PRIORITY_TARGETS_PATH = (
    OUTPUT_DIR
    / "qmt_roll_stage444_intraday_proxy_data_readiness_priority_targets_stage444_intraday_proxy_data_readiness_v1.csv"
)
SYMBOL_PLAN_PATH = (
    OUTPUT_DIR
    / "qmt_roll_stage444_intraday_proxy_data_readiness_symbol_download_plan_stage444_intraday_proxy_data_readiness_v1.csv"
)

STATUS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_extract_status_{MODEL_TAG}.csv"
BARS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_minute_bars_{MODEL_TAG}.csv"
COVERAGE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_priority_window_coverage_{MODEL_TAG}.csv"
PROXY_PRICE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_proxy_prices_{MODEL_TAG}.csv"
SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_coverage_summary_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

CHINA_TZ = ZoneInfo("Asia/Shanghai")
MAX_SYMBOLS = int(os.getenv("STAGE446_MAX_SYMBOLS", "5"))
MAX_SECONDS_PER_SYMBOL = int(os.getenv("STAGE446_MAX_SECONDS_PER_SYMBOL", "180"))
START_PADDING_MINUTES = int(os.getenv("STAGE446_START_PADDING_MINUTES", "10"))
END_PADDING_MINUTES = int(os.getenv("STAGE446_END_PADDING_MINUTES", "10"))


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


def _to_tqsdk_symbol(vt_symbol: str) -> str:
    symbol, exchange = str(vt_symbol).split(".", 1)
    return f"{exchange}.{symbol}"


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
        symbol_rows = symbol_rows.merge(plan[["vt_symbol", "suggested_tqsdk_symbol"]], on="vt_symbol", how="left")
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


def _normalize_tqsdk_datetime(value: Any) -> pd.Timestamp:
    ts = pd.to_datetime(value, unit="ns", errors="coerce", utc=True)
    if pd.isna(ts):
        return pd.NaT
    return ts.tz_convert(CHINA_TZ).tz_localize(None)


def _extract_symbol(row: Any, username: str, password: str) -> tuple[dict[str, Any], pd.DataFrame]:
    vt_symbol = str(row.vt_symbol)
    tq_symbol = str(row.suggested_tqsdk_symbol)
    start_dt = (pd.Timestamp(row.target_start) - timedelta(minutes=START_PADDING_MINUTES)).to_pydatetime()
    end_dt = (pd.Timestamp(row.target_end) + timedelta(minutes=END_PADDING_MINUTES)).to_pydatetime()
    raw_path = RAW_ROOT / tq_symbol.split(".", 1)[0] / f"{tq_symbol.split('.', 1)[1]}_minute_backtest.csv"
    raw_path.parent.mkdir(parents=True, exist_ok=True)

    status = {
        "vt_symbol": vt_symbol,
        "tq_symbol": tq_symbol,
        "extract_start": pd.Timestamp(start_dt),
        "extract_end": pd.Timestamp(end_dt),
        "priority_targets": int(row.priority_targets),
        "unique_trades": int(row.unique_trades),
        "max_abs_next_open_adverse_cash": float(row.max_abs_next_open_adverse_cash),
        "calendar_validation_targets": int(row.calendar_validation_targets),
        "raw_path": str(raw_path),
        "status": "unknown",
        "rows": 0,
        "elapsed_seconds": 0.0,
        "message": "",
    }
    started = time.time()
    rows: list[dict[str, Any]] = []
    seen_ids: set[int] = set()
    api: TqApi | None = None
    try:
        api = TqApi(
            TqSim(),
            backtest=TqBacktest(start_dt=start_dt, end_dt=end_dt),
            auth=TqAuth(username, password),
        )
        klines = api.get_kline_serial(tq_symbol, duration_seconds=60, data_length=500)
        while True:
            if time.time() - started > MAX_SECONDS_PER_SYMBOL:
                status["status"] = "timeout"
                status["message"] = f"timeout_after_{MAX_SECONDS_PER_SYMBOL}s"
                break
            api.wait_update()
            if not api.is_changing(klines.iloc[-1], "datetime"):
                continue
            row_data = klines.iloc[-1].to_dict()
            bar_id = int(row_data.get("id", -1))
            if bar_id in seen_ids:
                continue
            seen_ids.add(bar_id)
            bar_dt = _normalize_tqsdk_datetime(row_data.get("datetime"))
            if pd.isna(bar_dt):
                continue
            rows.append(
                {
                    "vt_symbol": vt_symbol,
                    "tq_symbol": tq_symbol,
                    "bar_datetime": bar_dt,
                    "bar_id": bar_id,
                    "open": float(row_data.get("open", np.nan)),
                    "high": float(row_data.get("high", np.nan)),
                    "low": float(row_data.get("low", np.nan)),
                    "close": float(row_data.get("close", np.nan)),
                    "volume": float(row_data.get("volume", np.nan)),
                    "open_oi": float(row_data.get("open_oi", np.nan)),
                    "close_oi": float(row_data.get("close_oi", np.nan)),
                }
            )
    except BacktestFinished:
        status["status"] = "extracted"
    except Exception as exc:
        status["status"] = "failed"
        status["message"] = repr(exc)
    finally:
        if api is not None:
            api.close()

    bars = pd.DataFrame(rows)
    if not bars.empty:
        bars = bars.drop_duplicates(["vt_symbol", "bar_datetime"]).sort_values(["vt_symbol", "bar_datetime"])
        bars.to_csv(raw_path, index=False, encoding="utf-8-sig")
    status["rows"] = int(len(bars))
    if status["status"] == "unknown":
        status["status"] = "extracted" if len(bars) else "empty"
    status["elapsed_seconds"] = round(time.time() - started, 2)
    return status, bars


def _coverage_for_targets(targets: pd.DataFrame, bars: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    if bars.empty:
        bars = pd.DataFrame(columns=["vt_symbol", "bar_datetime", "open", "high", "low", "close", "volume"])
    bars = bars.copy()
    bars["bar_datetime"] = pd.to_datetime(bars["bar_datetime"], errors="coerce").dt.tz_localize(None)
    grouped = {symbol: frame.sort_values("bar_datetime") for symbol, frame in bars.groupby("vt_symbol", sort=False)}

    coverage_rows: list[dict[str, Any]] = []
    proxy_rows: list[dict[str, Any]] = []
    for row in targets.itertuples(index=False):
        vt_symbol = str(row.vt_symbol)
        frame = grouped.get(vt_symbol, pd.DataFrame())
        start = pd.Timestamp(row.target_start)
        end = pd.Timestamp(row.target_end)
        in_window = frame[(frame["bar_datetime"] >= start) & (frame["bar_datetime"] < end)].copy() if not frame.empty else pd.DataFrame()
        count = int(len(in_window))
        covered = int(count > 0)
        first_bar = in_window.iloc[0].to_dict() if count else {}
        last_bar = in_window.iloc[-1].to_dict() if count else {}
        coverage_rows.append(
            {
                "trade_id": str(row.trade_id),
                "vt_symbol": vt_symbol,
                "proxy_type": str(row.proxy_type),
                "target_start": start,
                "target_end": end,
                "abs_next_open_adverse_cash": float(row.abs_next_open_adverse_cash),
                "calendar_validation_required": int(row.calendar_validation_required),
                "minute_bar_count": count,
                "covered": covered,
                "first_bar_datetime": first_bar.get("bar_datetime", ""),
                "first_open": first_bar.get("open", np.nan),
                "first_close": first_bar.get("close", np.nan),
                "last_bar_datetime": last_bar.get("bar_datetime", ""),
                "last_open": last_bar.get("open", np.nan),
                "last_close": last_bar.get("close", np.nan),
            }
        )
        if count:
            proxy_rows.append(
                {
                    "trade_id": str(row.trade_id),
                    "vt_symbol": vt_symbol,
                    "proxy_type": str(row.proxy_type),
                    "proxy_bar_count": count,
                    "proxy_first_time": first_bar.get("bar_datetime", ""),
                    "proxy_first_open": first_bar.get("open", np.nan),
                    "proxy_first_close": first_bar.get("close", np.nan),
                    "proxy_last_time": last_bar.get("bar_datetime", ""),
                    "proxy_last_open": last_bar.get("open", np.nan),
                    "proxy_last_close": last_bar.get("close", np.nan),
                    "proxy_vwap_like": (
                        float((in_window["close"] * in_window["volume"]).sum() / in_window["volume"].sum())
                        if float(in_window["volume"].sum()) > 0
                        else float(in_window["close"].mean())
                    ),
                }
            )
    return pd.DataFrame(coverage_rows), pd.DataFrame(proxy_rows)


def _summary(status: pd.DataFrame, coverage: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = [
        {
            "bucket_type": "all",
            "bucket": "all",
            "required_targets": int(len(coverage)),
            "covered_targets": int(coverage["covered"].sum()) if not coverage.empty else 0,
            "coverage_rate": float(coverage["covered"].mean()) if not coverage.empty else 0.0,
            "extracted_symbols": int((status["status"] == "extracted").sum()) if not status.empty else 0,
            "failed_symbols": int((status["status"] == "failed").sum()) if not status.empty else 0,
            "timeout_symbols": int((status["status"] == "timeout").sum()) if not status.empty else 0,
        }
    ]
    if not coverage.empty:
        for keys in [["vt_symbol"], ["proxy_type"], ["calendar_validation_required"]]:
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
            group["extracted_symbols"] = np.nan
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
                        "extracted_symbols",
                        "failed_symbols",
                        "timeout_symbols",
                        "max_abs_next_open_adverse_cash",
                    ]
                ].to_dict("records")
            )
    return pd.DataFrame(rows)


def _decision(status: pd.DataFrame, coverage: pd.DataFrame, proxy_prices: pd.DataFrame) -> dict[str, Any]:
    required = int(len(coverage))
    covered = int(coverage["covered"].sum()) if required else 0
    coverage_rate = float(covered / required) if required else 0.0
    if required and covered == required:
        label = "priority_proxy_windows_fully_covered"
    elif covered > 0:
        label = "priority_proxy_windows_partially_covered_need_calendar_session_mapping"
    else:
        label = "tqsdk_backtest_minute_extract_no_window_coverage"
    return {
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "decision": label,
        "selected_symbols": int(len(status)),
        "extracted_symbols": int((status["status"] == "extracted").sum()) if not status.empty else 0,
        "failed_or_timeout_symbols": int(status["status"].isin(["failed", "timeout"]).sum()) if not status.empty else 0,
        "extracted_minute_bars": int(status["rows"].sum()) if not status.empty else 0,
        "required_priority_targets": required,
        "covered_priority_targets": covered,
        "coverage_rate": coverage_rate,
        "proxy_price_rows": int(len(proxy_prices)),
        "outputs": {
            "extract_status": str(STATUS_PATH),
            "minute_bars": str(BARS_PATH),
            "priority_window_coverage": str(COVERAGE_PATH),
            "proxy_prices": str(PROXY_PRICE_PATH),
            "coverage_summary": str(SUMMARY_PATH),
            "report": str(REPORT_PATH),
        },
        "next_step": "若覆盖率足够，Stage147 把代理价接回 Stage143 order ledger，重构 Stage079/Stage103 执行路径；否则先修交易日历和会话窗口。",
    }


def _write_report(
    status: pd.DataFrame,
    summary: pd.DataFrame,
    coverage: pd.DataFrame,
    proxy_prices: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    top_proxy = proxy_prices.head(60) if not proxy_prices.empty else pd.DataFrame()
    top_missing = (
        coverage[coverage["covered"].eq(0)]
        .sort_values("abs_next_open_adverse_cash", ascending=False)
        .head(60)
        if not coverage.empty
        else pd.DataFrame()
    )
    report = [
        "# Stage146 TqBacktest分钟线执行代理抽取",
        "",
        f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "- 阶段性质：执行代理分钟线抽取；不修改策略规则，不导入vn.py数据库。",
        f"- 最大抽取合约数：`{MAX_SYMBOLS}`。",
        "",
        "## 外部调研判断",
        "",
        "- TqSdk `DataDownloader` 是专业版历史下载工具，本地账号无权限；但 `TqBacktest` 可进行历史回放并推送分钟K。",
        "- 本阶段使用 `TqBacktest + get_kline_serial(duration_seconds=60)` 抽取目标窗口附近的真实分钟K，作为 Stage143 执行代理回测的输入。",
        "",
        "## 抽取状态",
        "",
        _md_table(status, max_rows=80),
        "",
        "## 覆盖摘要",
        "",
        _md_table(summary, max_rows=120),
        "",
        "## 可用代理价样例",
        "",
        _md_table(top_proxy, max_rows=60),
        "",
        "## 未覆盖高冲击窗口样例",
        "",
        _md_table(top_missing, max_rows=60),
        "",
        "## 决策",
        "",
        f"- 决策标签：`{decision['decision']}`。",
        f"- 抽取合约数：`{decision['selected_symbols']}`。",
        f"- 成功抽取合约数：`{decision['extracted_symbols']}`。",
        f"- 失败/超时合约数：`{decision['failed_or_timeout_symbols']}`。",
        f"- 抽取分钟K数量：`{decision['extracted_minute_bars']}`。",
        f"- 目标窗口：`{decision['required_priority_targets']}`。",
        f"- 覆盖窗口：`{decision['covered_priority_targets']}`。",
        f"- 覆盖率：`{decision['coverage_rate']:.4%}`。",
        "",
        "## 结论",
        "",
        "- 本阶段不产生新策略候选，也不证明 Stage103 可执行。",
        "- 若覆盖率不足，通常不是策略失败，而是 `08:55` 集合竞价无分钟K、夜盘/日盘会话标签或周末交易日标签需要修正。",
        "- 下一步应把已覆盖代理价先接回订单 ledger，做局部 execution proxy 回放；不要按未覆盖日期/品种做黑名单。",
        "",
        "## 过拟合与继续价值反思",
        "",
        "- 运行前过拟合反思：否。只抽取执行数据，不筛交易规则。",
        "- 运行后过拟合反思：否。覆盖状态不用于删交易，只用于判断数据和会话映射是否够用。",
        "- 运行前继续价值反思：是。TqBacktest 已证明分钟K可取得，值得推进到代理成交价重构。",
        "- 运行后继续价值反思：若覆盖率大于0，则继续价值明确，应优先做局部订单代理回放。",
    ]
    REPORT_PATH.write_text("\n".join(report), encoding="utf-8")


def main() -> None:
    targets, plan = _load_inputs()
    selected = _selected_symbols(targets, plan)
    selected_targets = targets[targets["vt_symbol"].isin(set(selected["vt_symbol"]))].copy()
    username, password = _require_credentials()
    RAW_ROOT.mkdir(parents=True, exist_ok=True)

    status_rows: list[dict[str, Any]] = []
    bar_frames: list[pd.DataFrame] = []
    for row in selected.itertuples(index=False):
        status, bars = _extract_symbol(row, username, password)
        status_rows.append(status)
        if not bars.empty:
            bar_frames.append(bars)
        pd.DataFrame(status_rows).to_csv(STATUS_PATH, index=False, encoding="utf-8-sig")
        print(
            f"{status['status']} {status['vt_symbol']} {status['tq_symbol']} rows={status['rows']} "
            f"elapsed={status['elapsed_seconds']}",
            flush=True,
        )

    status = pd.DataFrame(status_rows)
    bars = pd.concat(bar_frames, ignore_index=True) if bar_frames else pd.DataFrame()
    coverage, proxy_prices = _coverage_for_targets(selected_targets, bars)
    summary = _summary(status, coverage)
    decision = _decision(status, coverage, proxy_prices)

    status.to_csv(STATUS_PATH, index=False, encoding="utf-8-sig")
    bars.to_csv(BARS_PATH, index=False, encoding="utf-8-sig")
    coverage.to_csv(COVERAGE_PATH, index=False, encoding="utf-8-sig")
    proxy_prices.to_csv(PROXY_PRICE_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(status, summary, coverage, proxy_prices, decision)

    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), flush=True)
    print(f"wrote: {REPORT_PATH}", flush=True)


if __name__ == "__main__":
    main()
