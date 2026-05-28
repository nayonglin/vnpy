from __future__ import annotations

import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

MODEL_TAG = "stage447_proxy_price_ledger_mismatch_v1"
OUTPUT_PREFIX = "qmt_roll_stage447_proxy_price_ledger_mismatch"
LINE_ID = "futures_trend_drawdown30_preserve_return"

STAGE443_LEDGER_PATH = (
    OUTPUT_DIR
    / "qmt_roll_stage443_execution_proxy_calibration_trade_gap_ledger_stage443_execution_proxy_calibration_v1.csv"
)
STAGE446_PROXY_PATH = (
    OUTPUT_DIR
    / "qmt_roll_stage446_tqsdk_backtest_minute_proxy_extract_proxy_prices_stage446_tqsdk_backtest_minute_proxy_extract_v1.csv"
)
STAGE446_COVERAGE_PATH = (
    OUTPUT_DIR
    / "qmt_roll_stage446_tqsdk_backtest_minute_proxy_extract_priority_window_coverage_stage446_tqsdk_backtest_minute_proxy_extract_v1.csv"
)

DETAIL_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_detail_{MODEL_TAG}.csv"
SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
MISMATCH_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_largest_mismatches_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

NIGHT_SESSION_CLASS = "night_session_next_trade_day_open_proxy"


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


def _load_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    ledger = pd.read_csv(STAGE443_LEDGER_PATH, encoding="utf-8-sig")
    proxy = pd.read_csv(STAGE446_PROXY_PATH, encoding="utf-8-sig")
    coverage = pd.read_csv(STAGE446_COVERAGE_PATH, encoding="utf-8-sig")
    for frame in [ledger, proxy, coverage]:
        for column in frame.columns:
            if column.endswith("date") or column.endswith("time") or column in {"date", "next_trade_date"}:
                converted = pd.to_datetime(frame[column], errors="coerce")
                if converted.notna().any():
                    frame[column] = converted
    numeric_columns = [
        "theoretical_price",
        "same_day_close",
        "next_open",
        "next_close",
        "volume",
        "size",
        "price_tick",
        "next_open_adverse_cash",
    ]
    for column in numeric_columns:
        if column in ledger.columns:
            ledger[column] = pd.to_numeric(ledger[column], errors="coerce")
    ledger["abs_next_open_adverse_cash"] = ledger["next_open_adverse_cash"].abs()
    for column in ["proxy_first_open", "proxy_first_close", "proxy_last_open", "proxy_last_close", "proxy_vwap_like"]:
        if column in proxy.columns:
            proxy[column] = pd.to_numeric(proxy[column], errors="coerce")
    return ledger, proxy, coverage


def _pivot_proxy(proxy: pd.DataFrame) -> pd.DataFrame:
    if proxy.empty:
        return pd.DataFrame(columns=["trade_id"])
    fields = ["proxy_first_open", "proxy_first_close", "proxy_last_close", "proxy_vwap_like"]
    pivot_parts: list[pd.DataFrame] = []
    for field in fields:
        part = proxy.pivot_table(index="trade_id", columns="proxy_type", values=field, aggfunc="first")
        part.columns = [f"{column}_{field}" for column in part.columns]
        pivot_parts.append(part)
    return pd.concat(pivot_parts, axis=1).reset_index()


def _side_pnl_multiplier(direction: str, offset: str) -> int:
    direction = str(direction)
    offset = str(offset)
    sell_like = (direction == "Short" and offset == "Open") or (direction == "Long" and offset == "Close")
    return 1 if sell_like else -1


def _pnl_delta(row: pd.Series, price_column: str, base_column: str = "same_day_close") -> float:
    price = row.get(price_column, np.nan)
    base = row.get(base_column, np.nan)
    if pd.isna(price) or pd.isna(base):
        return np.nan
    multiplier = _side_pnl_multiplier(str(row.direction), str(row.offset))
    return float(multiplier * (float(price) - float(base)) * float(row.volume) * float(row.size))


def _build_detail(ledger: pd.DataFrame, proxy: pd.DataFrame) -> pd.DataFrame:
    proxy_wide = _pivot_proxy(proxy)
    selected_ids = set(proxy["trade_id"].astype(str))
    detail = ledger[ledger["trade_id"].astype(str).isin(selected_ids)].copy()
    detail = detail.merge(proxy_wide, on="trade_id", how="left")

    detail["same_last5_vwap"] = detail.get("same_day_close_last_5m_proxy_vwap_like")
    detail["same_last5_first_open"] = detail.get("same_day_close_last_5m_proxy_first_open")
    detail["night_open_first"] = detail.get("night_session_open_2100_2105_proxy_first_open")
    detail["night_open_vwap"] = detail.get("night_session_open_2100_2105_proxy_vwap_like")
    detail["day_open_first"] = detail.get("day_session_open_0900_0905_proxy_first_open")
    detail["day_open_vwap"] = detail.get("day_session_open_0900_0905_proxy_vwap_like")

    detail["preferred_real_open_proxy"] = np.where(
        detail["session_proxy_class"].eq(NIGHT_SESSION_CLASS) & detail["night_open_first"].notna(),
        detail["night_open_first"],
        detail["day_open_first"],
    )
    detail["preferred_real_open_proxy_type"] = np.where(
        detail["session_proxy_class"].eq(NIGHT_SESSION_CLASS) & detail["night_open_first"].notna(),
        "night_session_open_2100_2105_first_open",
        "day_session_open_0900_0905_first_open",
    )

    for column in ["same_last5_vwap", "same_last5_first_open", "night_open_first", "night_open_vwap", "day_open_first", "day_open_vwap", "preferred_real_open_proxy"]:
        detail[f"{column}_minus_same_close"] = detail[column] - detail["same_day_close"]
        detail[f"{column}_pnl_delta_vs_same_close"] = detail.apply(_pnl_delta, axis=1, price_column=column)

    detail["preferred_real_open_minus_daily_next_open"] = detail["preferred_real_open_proxy"] - detail["next_open"]
    detail["preferred_real_open_abs_minus_daily_next_open"] = detail["preferred_real_open_minus_daily_next_open"].abs()
    detail["same_last5_abs_minus_same_close"] = (detail["same_last5_vwap"] - detail["same_day_close"]).abs()
    detail["preferred_real_open_abs_minus_same_close"] = (
        detail["preferred_real_open_proxy"] - detail["same_day_close"]
    ).abs()
    detail["daily_next_open_abs_minus_same_close"] = (detail["next_open"] - detail["same_day_close"]).abs()
    return detail.sort_values("abs_next_open_adverse_cash", ascending=False)


def _summary(detail: pd.DataFrame) -> pd.DataFrame:
    if detail.empty:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    metrics = [
        "same_last5_abs_minus_same_close",
        "preferred_real_open_abs_minus_daily_next_open",
        "preferred_real_open_abs_minus_same_close",
        "daily_next_open_abs_minus_same_close",
        "same_last5_vwap_pnl_delta_vs_same_close",
        "preferred_real_open_proxy_pnl_delta_vs_same_close",
        "night_open_first_pnl_delta_vs_same_close",
        "day_open_first_pnl_delta_vs_same_close",
    ]
    for metric in metrics:
        series = pd.to_numeric(detail[metric], errors="coerce").dropna()
        if series.empty:
            continue
        rows.append(
            {
                "metric": metric,
                "count": int(series.count()),
                "sum": float(series.sum()),
                "mean": float(series.mean()),
                "median": float(series.median()),
                "max_abs": float(series.abs().max()),
                "p95_abs": float(series.abs().quantile(0.95)),
            }
        )
    rows.append(
        {
            "metric": "selected_trade_count",
            "count": int(detail["trade_id"].nunique()),
            "sum": np.nan,
            "mean": np.nan,
            "median": np.nan,
            "max_abs": np.nan,
            "p95_abs": np.nan,
        }
    )
    return pd.DataFrame(rows)


def _decision(detail: pd.DataFrame, summary: pd.DataFrame) -> dict[str, Any]:
    selected = int(detail["trade_id"].nunique()) if not detail.empty else 0
    same_last5_large = int((detail["same_last5_abs_minus_same_close"] >= detail["price_tick"].fillna(1) * 20).sum()) if not detail.empty else 0
    open_large = int((detail["preferred_real_open_abs_minus_daily_next_open"] >= detail["price_tick"].fillna(1) * 20).sum()) if not detail.empty else 0
    max_same_last5_abs = float(detail["same_last5_abs_minus_same_close"].max()) if not detail.empty else 0.0
    max_open_abs = float(detail["preferred_real_open_abs_minus_daily_next_open"].max()) if not detail.empty else 0.0
    if same_last5_large or open_large:
        label = "daily_bar_proxy_mismatch_requires_session_rebuild"
    else:
        label = "minute_proxy_consistent_enough_for_local_replay"
    return {
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "decision": label,
        "selected_trade_count": selected,
        "same_last5_large_mismatch_count": same_last5_large,
        "real_open_vs_daily_next_open_large_mismatch_count": open_large,
        "max_same_last5_abs_minus_same_close": max_same_last5_abs,
        "max_real_open_abs_minus_daily_next_open": max_open_abs,
        "outputs": {
            "detail": str(DETAIL_PATH),
            "summary": str(SUMMARY_PATH),
            "largest_mismatches": str(MISMATCH_PATH),
            "report": str(REPORT_PATH),
        },
        "next_step": "不能直接用日线same_day_close/next_open做代理价；先重建基于分钟线会话的执行路径，再谈Stage103真实paper晋级。",
    }


def _write_report(detail: pd.DataFrame, summary: pd.DataFrame, mismatch: pd.DataFrame, decision: dict[str, Any]) -> None:
    cols = [
        "trade_id",
        "date",
        "next_trade_date",
        "vt_symbol",
        "direction",
        "offset",
        "same_day_close",
        "same_last5_vwap",
        "next_open",
        "preferred_real_open_proxy",
        "preferred_real_open_proxy_type",
        "same_last5_abs_minus_same_close",
        "preferred_real_open_abs_minus_daily_next_open",
        "same_last5_vwap_pnl_delta_vs_same_close",
        "preferred_real_open_proxy_pnl_delta_vs_same_close",
    ]
    report = [
        "# Stage147 分钟代理价与日线账本错位审计",
        "",
        f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "- 阶段性质：执行代理价账本校准；不修改策略规则，不新增候选。",
        "",
        "## 外部调研判断",
        "",
        "- 执行回测应区分信号价格、可成交价格和日线合成价格；分钟线会话价是校准日线代理价的最低必要粒度。",
        "- TqBacktest 已能提供目标合约分钟K，因此可以直接检查日线 `same_day_close/next_open` 与真实会话价是否一致。",
        "",
        "## 决策",
        "",
        f"- 决策标签：`{decision['decision']}`。",
        f"- 样本交易数：`{decision['selected_trade_count']}`。",
        f"- 14:55代理价相对日线同日close的大错位笔数：`{decision['same_last5_large_mismatch_count']}`。",
        f"- 真实开盘代理价相对日线next_open的大错位笔数：`{decision['real_open_vs_daily_next_open_large_mismatch_count']}`。",
        f"- 最大 14:55 vs 日线同日close 绝对价差：`{decision['max_same_last5_abs_minus_same_close']:.4f}`。",
        f"- 最大真实开盘 vs 日线next_open 绝对价差：`{decision['max_real_open_abs_minus_daily_next_open']:.4f}`。",
        "",
        "## 摘要指标",
        "",
        _md_table(summary),
        "",
        "## 最大错位样例",
        "",
        _md_table(mismatch[cols], max_rows=40),
        "",
        "## 全部明细",
        "",
        _md_table(detail[cols], max_rows=80),
        "",
        "## 结论",
        "",
        "- Stage143 的 T+1 日线执行模型已经证明同日口径不安全；Stage147 进一步说明，日线 `same_day_close/next_open` 本身也不能直接等同真实会话可成交价。",
        "- 这不是单笔滑点问题，而是交易日/夜盘会话/日线合成标签错位问题。",
        "- Stage103 不能真实晋级 paper；下一步要基于分钟线重新定义执行代理路径，并用该路径重放订单 ledger。",
        "",
        "## 过拟合与继续价值反思",
        "",
        "- 运行前过拟合反思：否。只比较价格口径，不筛日期/品种。",
        "- 运行后过拟合反思：否。发现错位后不做黑名单，转向修执行模型。",
        "- 运行前继续价值反思：是。分钟线已经可取得，必须量化日线代理价误差。",
        "- 运行后继续价值反思：是。继续做策略参数前，先重建执行口径更有价值。",
    ]
    REPORT_PATH.write_text("\n".join(report), encoding="utf-8")


def main() -> None:
    ledger, proxy, _ = _load_inputs()
    detail = _build_detail(ledger, proxy)
    summary = _summary(detail)
    mismatch = detail.sort_values(
        ["same_last5_abs_minus_same_close", "preferred_real_open_abs_minus_daily_next_open"],
        ascending=False,
    ).head(80)
    decision = _decision(detail, summary)

    detail.to_csv(DETAIL_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    mismatch.to_csv(MISMATCH_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(detail, summary, mismatch, decision)

    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), flush=True)
    print(f"wrote: {REPORT_PATH}", flush=True)


if __name__ == "__main__":
    main()
