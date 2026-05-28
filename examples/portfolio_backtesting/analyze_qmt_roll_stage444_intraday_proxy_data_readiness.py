from __future__ import annotations

import importlib.util
import json
import math
from datetime import datetime, time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from vnpy.trader.constant import Exchange, Interval
from vnpy.trader.database import get_database


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

MODEL_TAG = "stage444_intraday_proxy_data_readiness_v1"
OUTPUT_PREFIX = "qmt_roll_stage444_intraday_proxy_data_readiness"
LINE_ID = "futures_trend_drawdown30_preserve_return"

STAGE443_TRADE_GAP_PATH = (
    OUTPUT_DIR
    / "qmt_roll_stage443_execution_proxy_calibration_trade_gap_ledger_stage443_execution_proxy_calibration_v1.csv"
)
STAGE443_WORST_DATES_PATH = (
    OUTPUT_DIR
    / "qmt_roll_stage443_execution_proxy_calibration_worst_gap_dates_stage443_execution_proxy_calibration_v1.csv"
)

DB_OVERVIEW_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_database_overview_{MODEL_TAG}.csv"
TARGETS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_required_proxy_targets_{MODEL_TAG}.csv"
COVERAGE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_coverage_summary_{MODEL_TAG}.csv"
SYMBOL_PLAN_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_symbol_download_plan_{MODEL_TAG}.csv"
PRIORITY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_priority_targets_{MODEL_TAG}.csv"
READINESS_JSON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_readiness_{MODEL_TAG}.json"
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


def _combine(date_value: Any, clock: time) -> pd.Timestamp:
    date = pd.Timestamp(date_value).normalize()
    return pd.Timestamp.combine(date.date(), clock)


def _parse_vt_symbol(vt_symbol: str) -> tuple[str, Exchange]:
    symbol, exchange_value = vt_symbol.split(".", 1)
    return symbol, Exchange(exchange_value)


def _to_tqsdk_symbol(vt_symbol: str) -> str:
    symbol, exchange_value = vt_symbol.split(".", 1)
    return f"{exchange_value}.{symbol}"


def _module_available(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None


def _load_stage443_trade_gap() -> pd.DataFrame:
    frame = pd.read_csv(STAGE443_TRADE_GAP_PATH, encoding="utf-8-sig")
    for column in ["date", "next_trade_date"]:
        frame[column] = pd.to_datetime(frame[column], errors="coerce").dt.tz_localize(None).dt.normalize()
    for column in ["next_open_adverse_cash", "next_close_adverse_cash", "volume", "size"]:
        frame[column] = pd.to_numeric(frame.get(column, 0.0), errors="coerce").fillna(0.0)
    return frame.dropna(subset=["date", "next_trade_date", "vt_symbol"]).sort_values(["date", "vt_symbol", "trade_id"])


def _load_worst_dates() -> pd.DataFrame:
    if not STAGE443_WORST_DATES_PATH.exists():
        return pd.DataFrame(columns=["date"])
    frame = pd.read_csv(STAGE443_WORST_DATES_PATH, encoding="utf-8-sig")
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.tz_localize(None).dt.normalize()
    return frame.dropna(subset=["date"])


def _database_overview() -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for overview in get_database().get_bar_overview():
        interval = getattr(overview, "interval", "")
        exchange = getattr(overview, "exchange", "")
        rows.append(
            {
                "symbol": str(getattr(overview, "symbol", "")),
                "exchange": getattr(exchange, "value", str(exchange)),
                "vt_symbol": f"{getattr(overview, 'symbol', '')}.{getattr(exchange, 'value', str(exchange))}",
                "interval": getattr(interval, "value", str(interval)),
                "count": int(getattr(overview, "count", 0) or 0),
                "start": getattr(overview, "start", None),
                "end": getattr(overview, "end", None),
            }
        )
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    frame["start"] = pd.to_datetime(frame["start"], errors="coerce").dt.tz_localize(None)
    frame["end"] = pd.to_datetime(frame["end"], errors="coerce").dt.tz_localize(None)
    return frame.sort_values(["interval", "exchange", "symbol"]).reset_index(drop=True)


def _build_required_targets(trades: pd.DataFrame, worst_dates: pd.DataFrame) -> pd.DataFrame:
    worst_set = {pd.Timestamp(value).normalize() for value in worst_dates["date"].dropna().tolist()}
    rows: list[dict[str, Any]] = []
    for row in trades.itertuples(index=False):
        decision_date = pd.Timestamp(row.date).normalize()
        next_trade_date = pd.Timestamp(row.next_trade_date).normalize()
        abs_open_impact = abs(float(row.next_open_adverse_cash))
        priority = "high" if decision_date in worst_set or abs_open_impact >= 500_000 else "normal"
        base = {
            "trade_id": str(row.trade_id),
            "decision_date": decision_date,
            "next_trade_date": next_trade_date,
            "product_vt_symbol": str(row.product_vt_symbol),
            "vt_symbol": str(row.vt_symbol),
            "direction": str(row.direction),
            "offset": str(row.offset),
            "session_proxy_class": str(row.session_proxy_class),
            "abs_next_open_adverse_cash": abs_open_impact,
            "priority": priority,
        }
        rows.append(
            {
                **base,
                "proxy_type": "same_day_close_last_5m",
                "target_start": _combine(decision_date, time(14, 55)),
                "target_end": _combine(decision_date, time(15, 0)),
                "reason": "检验同日收盘口径是否能用盘中最后5分钟代理，而不是未来收盘价。",
            }
        )
        rows.append(
            {
                **base,
                "proxy_type": "day_session_auction_0855_0900",
                "target_start": _combine(next_trade_date, time(8, 55)),
                "target_end": _combine(next_trade_date, time(9, 0)),
                "reason": "无夜盘或错过夜盘时，次日日盘集合竞价代理。",
            }
        )
        rows.append(
            {
                **base,
                "proxy_type": "day_session_open_0900_0905",
                "target_start": _combine(next_trade_date, time(9, 0)),
                "target_end": _combine(next_trade_date, time(9, 5)),
                "reason": "次日日盘开盘5分钟可成交代理。",
            }
        )
        if str(row.session_proxy_class) == NIGHT_SESSION_CLASS:
            rows.append(
                {
                    **base,
                    "proxy_type": "night_auction_2055_2100",
                    "target_start": _combine(decision_date, time(20, 55)),
                    "target_end": _combine(decision_date, time(21, 0)),
                    "reason": "有夜盘品种的下一交易日集合竞价代理。",
                }
            )
            rows.append(
                {
                    **base,
                    "proxy_type": "night_session_open_2100_2105",
                    "target_start": _combine(decision_date, time(21, 0)),
                    "target_end": _combine(decision_date, time(21, 5)),
                    "reason": "有夜盘品种的下一交易日开盘5分钟代理。",
                }
            )
    targets = pd.DataFrame(rows)
    targets["target_start_weekday"] = pd.to_datetime(targets["target_start"], errors="coerce").dt.weekday
    targets["target_end_weekday"] = pd.to_datetime(targets["target_end"], errors="coerce").dt.weekday
    targets["calendar_validation_required"] = (
        (targets["target_start_weekday"] >= 5) | (targets["target_end_weekday"] >= 5)
    ).astype(int)
    return targets.sort_values(["priority", "decision_date", "vt_symbol", "proxy_type"], ascending=[False, True, True, True])


def _load_minute_bars_for_window(vt_symbol: str, start: pd.Timestamp, end: pd.Timestamp) -> int:
    symbol, exchange = _parse_vt_symbol(vt_symbol)
    bars = get_database().load_bar_data(
        symbol=symbol,
        exchange=exchange,
        interval=Interval.MINUTE,
        start=start.to_pydatetime(),
        end=end.to_pydatetime(),
    )
    return len(bars)


def _attach_local_minute_coverage(targets: pd.DataFrame, overview: pd.DataFrame) -> pd.DataFrame:
    targets = targets.copy()
    minute_overview = overview[overview["interval"].eq(Interval.MINUTE.value)].copy() if not overview.empty else pd.DataFrame()
    if minute_overview.empty:
        targets["local_minute_bar_count"] = 0
        targets["local_minute_covered"] = 0
        targets["coverage_note"] = "vnpy_database_has_no_minute_bar_overview"
        return targets

    available_symbols = set(minute_overview["vt_symbol"].astype(str))
    counts: list[int] = []
    notes: list[str] = []
    for row in targets.itertuples(index=False):
        vt_symbol = str(row.vt_symbol)
        if vt_symbol not in available_symbols:
            counts.append(0)
            notes.append("minute_symbol_missing")
            continue
        count = _load_minute_bars_for_window(
            vt_symbol,
            pd.Timestamp(row.target_start),
            pd.Timestamp(row.target_end),
        )
        counts.append(count)
        notes.append("covered" if count > 0 else "minute_window_missing")
    targets["local_minute_bar_count"] = counts
    targets["local_minute_covered"] = (targets["local_minute_bar_count"] > 0).astype(int)
    targets["coverage_note"] = notes
    return targets


def _coverage_summary(targets: pd.DataFrame) -> pd.DataFrame:
    if targets.empty:
        return pd.DataFrame()
    rows: list[pd.DataFrame] = []
    for keys in [["proxy_type"], ["priority"], ["product_vt_symbol"], ["vt_symbol"], ["session_proxy_class"]]:
        group = (
            targets.groupby(keys, sort=True)
            .agg(
                required_targets=("trade_id", "count"),
                covered_targets=("local_minute_covered", "sum"),
                unique_trades=("trade_id", "nunique"),
                high_priority_targets=("priority", lambda s: int((s == "high").sum())),
            )
            .reset_index()
        )
        group["bucket_type"] = "+".join(keys)
        group["bucket"] = group[keys].astype(str).agg("|".join, axis=1)
        group["coverage_rate"] = group["covered_targets"] / group["required_targets"]
        rows.append(group[["bucket_type", "bucket", "required_targets", "covered_targets", "coverage_rate", "unique_trades", "high_priority_targets"]])
    total = pd.DataFrame(
        [
            {
                "bucket_type": "all",
                "bucket": "all",
                "required_targets": int(len(targets)),
                "covered_targets": int(targets["local_minute_covered"].sum()),
                "coverage_rate": float(targets["local_minute_covered"].mean()) if len(targets) else 0.0,
                "unique_trades": int(targets["trade_id"].nunique()),
                "high_priority_targets": int((targets["priority"] == "high").sum()),
            }
        ]
    )
    return pd.concat([total, *rows], ignore_index=True)


def _symbol_download_plan(targets: pd.DataFrame) -> pd.DataFrame:
    if targets.empty:
        return pd.DataFrame()
    plan = (
        targets.groupby(["vt_symbol", "product_vt_symbol"], sort=True)
        .agg(
            first_target_start=("target_start", "min"),
            last_target_end=("target_end", "max"),
            required_targets=("trade_id", "count"),
            unique_trade_dates=("decision_date", "nunique"),
            unique_next_trade_dates=("next_trade_date", "nunique"),
            high_priority_targets=("priority", lambda s: int((s == "high").sum())),
        )
        .reset_index()
    )
    plan["suggested_tqsdk_symbol"] = plan["vt_symbol"].map(_to_tqsdk_symbol)
    plan["duration_seconds"] = 60
    plan["minimum_data_goal"] = "cover target windows only; full 2020-2026 minute history is preferable if quota allows"
    return plan.sort_values(["high_priority_targets", "required_targets"], ascending=[False, False]).reset_index(drop=True)


def _priority_targets(targets: pd.DataFrame) -> pd.DataFrame:
    if targets.empty:
        return pd.DataFrame()
    priority = targets[targets["priority"].eq("high")].copy()
    if priority.empty:
        priority = targets.sort_values("abs_next_open_adverse_cash", ascending=False).head(200).copy()
    return priority.sort_values(
        ["abs_next_open_adverse_cash", "decision_date", "vt_symbol"], ascending=[False, True, True]
    ).head(500)


def _readiness_payload(overview: pd.DataFrame, targets: pd.DataFrame, coverage: pd.DataFrame, plan: pd.DataFrame) -> dict[str, Any]:
    minute_overview = overview[overview["interval"].eq(Interval.MINUTE.value)] if not overview.empty else pd.DataFrame()
    target_total = int(len(targets))
    covered_total = int(targets["local_minute_covered"].sum()) if target_total else 0
    return {
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "decision": "minute_proxy_data_missing_build_sampling_plan"
        if covered_total < target_total
        else "minute_proxy_data_ready_for_execution_proxy_backtest",
        "local_minute_bar_overview_rows": int(len(minute_overview)),
        "required_proxy_targets": target_total,
        "covered_proxy_targets": covered_total,
        "coverage_rate": float(covered_total / target_total) if target_total else 0.0,
        "unique_trade_count": int(targets["trade_id"].nunique()) if target_total else 0,
        "unique_contract_count": int(targets["vt_symbol"].nunique()) if target_total else 0,
        "high_priority_target_count": int((targets["priority"] == "high").sum()) if target_total else 0,
        "calendar_validation_required_count": int(targets["calendar_validation_required"].sum()) if target_total else 0,
        "tqsdk_available": _module_available("tqsdk"),
        "xtquant_available": _module_available("xtquant"),
        "outputs": {
            "database_overview": str(DB_OVERVIEW_PATH),
            "required_proxy_targets": str(TARGETS_PATH),
            "coverage_summary": str(COVERAGE_PATH),
            "symbol_download_plan": str(SYMBOL_PLAN_PATH),
            "priority_targets": str(PRIORITY_PATH),
            "report": str(REPORT_PATH),
        },
        "next_step": "补分钟线/QMT行情采样后，回到Stage143执行代理回测；不要在同日收盘口径继续优化3/6个月指标。",
    }


def _write_report(
    overview: pd.DataFrame,
    targets: pd.DataFrame,
    coverage: pd.DataFrame,
    plan: pd.DataFrame,
    priority: pd.DataFrame,
    readiness: dict[str, Any],
) -> None:
    interval_summary = (
        overview.groupby("interval", sort=True)
        .agg(rows=("vt_symbol", "count"), total_bars=("count", "sum"), symbols=("vt_symbol", "nunique"))
        .reset_index()
        if not overview.empty
        else pd.DataFrame()
    )
    coverage_focus = coverage[coverage["bucket_type"].isin(["all", "proxy_type", "priority", "session_proxy_class"])].copy()
    report = [
        "# Stage144 分钟线执行代理数据覆盖审计",
        "",
        f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "- 阶段性质：数据覆盖与采样清单审计；不修改策略规则。",
        "- 目标：验证 Stage143 之后是否已有足够分钟线/QMT数据支持 `20:55/21:00/09:00/14:55` 执行代理。",
        "",
        "## 外部调研判断",
        "",
        "- TqSdk `get_kline_serial(symbol, 60, ...)` 支持分钟K线序列；可用于补合约级执行代理窗口。",
        "- vn.py 数据库支持 `Interval.MINUTE` 的 `save_bar_data/load_bar_data`，本地若有分钟线可直接复用。",
        "- xtquant/QMT 也有行情获取接口，但本仓库当前没有已落地的全历史分钟线文件；应先生成明确采样清单再补数据。",
        "",
        "## 本地数据库概览",
        "",
        _md_table(interval_summary),
        "",
        "## 覆盖结论",
        "",
        f"- 决策标签：`{readiness['decision']}`。",
        f"- 本地分钟线 overview 行数：`{readiness['local_minute_bar_overview_rows']}`。",
        f"- 需要采样窗口：`{readiness['required_proxy_targets']}`。",
        f"- 已覆盖窗口：`{readiness['covered_proxy_targets']}`。",
        f"- 覆盖率：`{readiness['coverage_rate']:.4%}`。",
        f"- 涉及交易数：`{readiness['unique_trade_count']}`。",
        f"- 涉及合约数：`{readiness['unique_contract_count']}`。",
        f"- 高优先级窗口数：`{readiness['high_priority_target_count']}`。",
        f"- 需要交易所日历复核的窗口数：`{readiness['calendar_validation_required_count']}`。",
        f"- tqsdk 可导入：`{readiness['tqsdk_available']}`。",
        f"- xtquant 可导入：`{readiness['xtquant_available']}`。",
        "",
        "## 覆盖分桶",
        "",
        _md_table(coverage_focus, max_rows=80),
        "",
        "## 下载/采样计划按合约汇总",
        "",
        _md_table(plan, max_rows=40),
        "",
        "## 高优先级采样窗口样例",
        "",
        _md_table(
            priority[
                [
                    "trade_id",
                    "decision_date",
                    "next_trade_date",
                    "vt_symbol",
                    "proxy_type",
                    "target_start",
                    "target_end",
                    "abs_next_open_adverse_cash",
                    "calendar_validation_required",
                    "coverage_note",
                ]
            ],
            max_rows=40,
        ),
        "",
        "## 结论",
        "",
        "- 本阶段不产生新候选，也不证明 Stage103 可执行。",
        "- 若分钟线覆盖率为 0，下一步必须补数据；否则继续在同日收盘假设下优化 3/6个月体验，属于执行口径风险。",
        "- `target_start/target_end` 是从 Stage443 日线成交迁移清单生成的候选窗口；涉及周末/节假日自然日标签的窗口，采集时必须用交易所实际交易日历校正。",
        "- 补数后再做 Stage145：用真实 `20:55/21:00/09:00/14:55` 代理价重构 C3/Stage103 的执行路径。",
        "",
        "## 过拟合与继续价值反思",
        "",
        "- 运行前过拟合反思：否。只检查数据覆盖，不挑信号。",
        "- 运行后过拟合反思：否。输出的是全订单采样清单，不按结果删除日期或品种。",
        "- 运行前继续价值反思：是。执行代理数据是 Stage103 能否进入 paper 的前置。",
        "- 运行后继续价值反思：是。没有分钟线时，补数据比继续救参数更有价值。",
    ]
    REPORT_PATH.write_text("\n".join(report), encoding="utf-8")


def main() -> None:
    trades = _load_stage443_trade_gap()
    worst_dates = _load_worst_dates()
    overview = _database_overview()
    targets = _build_required_targets(trades, worst_dates)
    targets = _attach_local_minute_coverage(targets, overview)
    coverage = _coverage_summary(targets)
    plan = _symbol_download_plan(targets)
    priority = _priority_targets(targets)
    readiness = _readiness_payload(overview, targets, coverage, plan)

    overview.to_csv(DB_OVERVIEW_PATH, index=False, encoding="utf-8-sig")
    targets.to_csv(TARGETS_PATH, index=False, encoding="utf-8-sig")
    coverage.to_csv(COVERAGE_PATH, index=False, encoding="utf-8-sig")
    plan.to_csv(SYMBOL_PLAN_PATH, index=False, encoding="utf-8-sig")
    priority.to_csv(PRIORITY_PATH, index=False, encoding="utf-8-sig")
    READINESS_JSON_PATH.write_text(json.dumps(_json_safe(readiness), ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(overview, targets, coverage, plan, priority, readiness)

    print(json.dumps(_json_safe(readiness), ensure_ascii=False, indent=2))
    print(f"wrote: {REPORT_PATH}")


if __name__ == "__main__":
    main()
