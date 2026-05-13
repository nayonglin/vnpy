from __future__ import annotations

import argparse
import json
import math
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

MODEL_TAG: str = "stage170_forward_data_gap_check_v1"
OUTPUT_PREFIX: str = "qmt_roll_stage170_forward_data_gap_check"
STAGE169_PREFIX: str = "qmt_roll_stage169_50w_qmt_shadow_daily_runner"
STAGE169_TAG: str = "stage169_50w_qmt_shadow_daily_runner_v1"
STAGE168_PREFIX: str = "qmt_roll_stage168_50w_qmt_shadow_startup"
STAGE168_TAG: str = "stage168_50w_qmt_shadow_startup_v1"
STAGE155_PREFIX: str = "qmt_roll_stage155_stage78_shadow_daily_protocol"
STAGE155_TAG: str = "stage155_stage78_shadow_daily_protocol_v1"
STAGE154_PREFIX: str = "qmt_roll_stage154_stage78_shadow_execution_ledger"
STAGE154_TAG: str = "stage154_stage78_shadow_execution_ledger_v1"

STAGE168_CONFIG_PATH: Path = OUTPUT_DIR / f"{STAGE168_PREFIX}_config_{STAGE168_TAG}.json"
STAGE155_DAILY_CONTROL_PATH: Path = OUTPUT_DIR / f"{STAGE155_PREFIX}_daily_control_ledger_{STAGE155_TAG}.csv"
STAGE155_HISTORICAL_INTENT_PATH: Path = OUTPUT_DIR / f"{STAGE155_PREFIX}_historical_intent_ledger_{STAGE155_TAG}.csv"
STAGE154_TRADE_LEDGER_PATH: Path = OUTPUT_DIR / f"{STAGE154_PREFIX}_trade_ledger_{STAGE154_TAG}.csv"
FORMAL_DAILY_PATH: Path = OUTPUT_DIR / "qmt_roll_official_stage78_defensive_formal_daily.csv"
FORMAL_TRADES_PATH: Path = OUTPUT_DIR / "qmt_roll_official_stage78_defensive_formal_trades_2020_2026_04.csv"


def _require(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"missing required artifact: {path}")


def _read_json(path: Path) -> dict[str, Any]:
    _require(path)
    return json.loads(path.read_text(encoding="utf-8"))


def _read_csv(path: Path) -> pd.DataFrame:
    _require(path)
    return pd.read_csv(path, encoding="utf-8-sig")


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


def _parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


# Futures exchanges keep weekend make-up workdays closed; this list follows published 2026 exchange holiday notices.
EXCHANGE_HOLIDAY_RANGES_2026: tuple[tuple[str, str], ...] = (
    ("2026-01-01", "2026-01-03"),
    ("2026-02-15", "2026-02-23"),
    ("2026-04-04", "2026-04-06"),
    ("2026-05-01", "2026-05-05"),
    ("2026-06-19", "2026-06-21"),
    ("2026-09-25", "2026-09-27"),
    ("2026-10-01", "2026-10-07"),
)


def _holiday_set_2026() -> set[date]:
    holidays: set[date] = set()
    for start, end in EXCHANGE_HOLIDAY_RANGES_2026:
        current = _parse_date(start)
        stop = _parse_date(end)
        while current <= stop:
            holidays.add(current)
            current += timedelta(days=1)
    return holidays


HOLIDAYS_2026: set[date] = _holiday_set_2026()


def _is_trading_day(day: date) -> bool:
    if day.weekday() >= 5:
        return False
    if day.year == 2026 and day in HOLIDAYS_2026:
        return False
    return True


def _previous_trading_day(day: date) -> date:
    current = day - timedelta(days=1)
    while not _is_trading_day(current):
        current -= timedelta(days=1)
    return current


def _trading_days_between(start_exclusive: date | None, end_inclusive: date) -> list[date]:
    if start_exclusive is None:
        return []
    current = start_exclusive + timedelta(days=1)
    days: list[date] = []
    while current <= end_inclusive:
        if _is_trading_day(current):
            days.append(current)
        current += timedelta(days=1)
    return days


def _date_stats(name: str, path: Path, primary_date_column: str, extra_date_columns: list[str] | None = None) -> dict[str, Any]:
    extra_date_columns = extra_date_columns or []
    date_columns = [primary_date_column, *extra_date_columns] if primary_date_column else extra_date_columns
    if not path.exists():
        return {
            "artifact": name,
            "path": str(path),
            "exists": False,
            "rows": 0,
            "max_date": "",
            "min_date": "",
            "extra_max_date": "",
            "primary_date_column": primary_date_column,
            "date_columns": ",".join(date_columns),
            "status": "MISSING_FILE",
        }
    frame = _read_csv(path)
    primary = pd.to_datetime(frame[primary_date_column], errors="coerce") if primary_date_column in frame.columns else pd.Series(dtype="datetime64[ns]")
    extra_max_dates: list[pd.Timestamp] = []
    for column in extra_date_columns:
        if column not in frame.columns:
            continue
        parsed = pd.to_datetime(frame[column], errors="coerce")
        if parsed.notna().any():
            extra_max_dates.append(parsed.max())
    max_date = primary.max().date().isoformat() if primary.notna().any() else ""
    min_date = primary.min().date().isoformat() if primary.notna().any() else ""
    extra_max_date = max(extra_max_dates).date().isoformat() if extra_max_dates else ""
    return {
        "artifact": name,
        "path": str(path),
        "exists": True,
        "rows": int(len(frame)),
        "max_date": max_date,
        "min_date": min_date,
        "extra_max_date": extra_max_date,
        "primary_date_column": primary_date_column,
        "date_columns": ",".join(date_columns),
        "status": "OK",
    }


def _paths_for(as_of: date) -> dict[str, Path]:
    key = as_of.strftime("%Y%m%d")
    return {
        "artifact_status": OUTPUT_DIR / f"{OUTPUT_PREFIX}_artifact_status_{key}_{MODEL_TAG}.csv",
        "missing_trading_days": OUTPUT_DIR / f"{OUTPUT_PREFIX}_missing_trading_days_{key}_{MODEL_TAG}.csv",
        "action_plan": OUTPUT_DIR / f"{OUTPUT_PREFIX}_action_plan_{key}_{MODEL_TAG}.csv",
        "summary": OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{key}_{MODEL_TAG}.json",
        "report": OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{key}_{MODEL_TAG}.md",
    }


def _build_artifact_status(target_date: date) -> pd.DataFrame:
    specs = [
        ("stage168_config", STAGE168_CONFIG_PATH, "", []),
        ("stage155_daily_control", STAGE155_DAILY_CONTROL_PATH, "date", []),
        ("stage155_historical_intent", STAGE155_HISTORICAL_INTENT_PATH, "decision_date", ["plan_date"]),
        ("stage154_trade_ledger", STAGE154_TRADE_LEDGER_PATH, "date", ["next_trade_date"]),
        ("formal_daily", FORMAL_DAILY_PATH, "date", []),
        ("formal_trades", FORMAL_TRADES_PATH, "date", []),
    ]
    rows = [_date_stats(name, path, primary, extra) for name, path, primary, extra in specs]
    result = pd.DataFrame(rows)
    result["target_latest_complete_trading_day"] = target_date.isoformat()
    result["fresh_enough_for_daily_report"] = result["max_date"].map(
        lambda value: bool(value) and _parse_date(str(value)) >= target_date
    )
    result.loc[result["artifact"].eq("stage168_config"), "fresh_enough_for_daily_report"] = result.loc[
        result["artifact"].eq("stage168_config"), "exists"
    ]
    return result


def _build_missing_days(artifact_status: pd.DataFrame, target_date: date) -> pd.DataFrame:
    daily_rows = artifact_status[artifact_status["artifact"].isin(["stage155_daily_control", "formal_daily"])]
    max_candidates: list[date] = []
    for value in daily_rows["max_date"].tolist():
        if value:
            max_candidates.append(_parse_date(str(value)))
    latest_daily = max(max_candidates) if max_candidates else None
    missing = _trading_days_between(latest_daily, target_date)
    return pd.DataFrame(
        [
            {
                "missing_trading_day": day.isoformat(),
                "reason": "local_daily_and_stage155_not_updated",
                "required_input": "official_stage78_forward_daily_bar_or_qmt_readonly_snapshot",
            }
            for day in missing
        ]
    )


def _build_action_plan(artifact_status: pd.DataFrame, missing_days: pd.DataFrame, target_date: date) -> pd.DataFrame:
    missing_count = len(missing_days)
    rows = [
        {
            "step": 1,
            "action": "更新行情到目标完整交易日",
            "status": "BLOCKED" if missing_count else "DONE",
            "detail": f"目标完整交易日为{target_date.isoformat()}；本地daily缺口{missing_count}个交易日。",
        },
        {
            "step": 2,
            "action": "用冻结Stage78生成前向理论信号",
            "status": "BLOCKED" if missing_count else "READY",
            "detail": "不能用旧历史intent代替5月前向信号。",
        },
        {
            "step": 3,
            "action": "生成Stage169目标日期日报",
            "status": "BLOCKED" if missing_count else "READY",
            "detail": f"日报目标应为{target_date.isoformat()}，即as-of日前一完整交易日。",
        },
        {
            "step": 4,
            "action": "接入QMT只读账户/持仓/委托/成交",
            "status": "OPTIONAL_FOR_SIGNAL_REPORT_REQUIRED_FOR_RECONCILE",
            "detail": "不需要真实下单；但完整对账日报需要QMT只读。",
        },
        {
            "step": 5,
            "action": "补齐夜盘/日盘代理价字段",
            "status": "BLOCKED" if missing_count else "READY",
            "detail": "需要分钟线或QMT行情，尤其是有夜盘品种21:00附近代理价。",
        },
    ]
    return pd.DataFrame(rows)


def _build_summary(
    as_of: date,
    target_date: date,
    artifact_status: pd.DataFrame,
    missing_days: pd.DataFrame,
    action_plan: pd.DataFrame,
) -> dict[str, Any]:
    missing_count = int(len(missing_days))
    stale_artifacts = artifact_status[
        artifact_status["exists"] & artifact_status["max_date"].astype(str).ne("") & ~artifact_status["fresh_enough_for_daily_report"]
    ]["artifact"].tolist()
    can_generate_target_report = missing_count == 0 and not stale_artifacts
    return {
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "as_of_date": as_of.isoformat(),
        "target_latest_complete_trading_day": target_date.isoformat(),
        "is_strategy_change": False,
        "is_backtest": False,
        "can_generate_target_report_from_local_data": bool(can_generate_target_report),
        "missing_trading_day_count": missing_count,
        "missing_trading_days": missing_days["missing_trading_day"].tolist() if not missing_days.empty else [],
        "stale_artifacts": stale_artifacts,
        "requires_live_order_data": False,
        "requires_forward_market_data": missing_count > 0,
        "requires_qmt_readonly_for_full_reconcile": True,
        "next_action": "update_forward_market_data_then_run_stage78_signal" if missing_count else "run_stage169_for_target_date",
        "judgement": {
            "overfit_before": "否。Stage170只检查数据时效，不改策略、不筛信号。",
            "continue_before": "是。没有最新日报的问题必须自动暴露，否则影子盘无法前向运行。",
            "overfit_after": "否。本阶段只产出缺口表和行动清单。",
            "continue_after": "是。下一步是补前向行情并接QMT只读对账，不是调参。",
        },
        "outputs": {key: str(value) for key, value in _paths_for(as_of).items()},
    }


def _write_report(
    as_of: date,
    target_date: date,
    artifact_status: pd.DataFrame,
    missing_days: pd.DataFrame,
    action_plan: pd.DataFrame,
    summary: dict[str, Any],
    paths: dict[str, Path],
) -> None:
    lines = [
        "# Stage170 前向数据缺口检查",
        "",
        "## 定位",
        "",
        "- 本阶段不是策略版本，不修改Stage78参数，不触发A/B。",
        "- 目标是解释为什么没有生成最新交易日日报，并给出下一步数据接入动作。",
        "",
        "## 日期判断",
        "",
        f"- as-of日期：`{as_of.isoformat()}`",
        f"- 目标最新完整交易日：`{target_date.isoformat()}`",
        "- 判断口径：使用as-of日前一完整交易日；2026年劳动节5月1日至5月5日休市，5月6日起照常开市。",
        "",
        "## 本地数据状态",
        "",
        _to_markdown_table(
            artifact_status,
            [
                "artifact",
                "exists",
                "rows",
                "primary_date_column",
                "min_date",
                "max_date",
                "extra_max_date",
                "target_latest_complete_trading_day",
                "fresh_enough_for_daily_report",
            ],
            max_rows=20,
        ),
        "",
        "## 缺失交易日",
        "",
        _to_markdown_table(missing_days, ["missing_trading_day", "reason", "required_input"], max_rows=40),
        "",
        "## 行动清单",
        "",
        _to_markdown_table(action_plan, ["step", "action", "status", "detail"], max_rows=20),
        "",
        "## 判断",
        "",
        f"- 是否能用本地数据生成目标日报：`{summary['can_generate_target_report_from_local_data']}`",
        f"- 是否需要真实下单数据：`{summary['requires_live_order_data']}`",
        f"- 是否需要前向行情数据：`{summary['requires_forward_market_data']}`",
        f"- 完整对账是否需要QMT只读：`{summary['requires_qmt_readonly_for_full_reconcile']}`",
        f"- 下一步：`{summary['next_action']}`",
        "",
        "## 反思",
        "",
        f"- 运行前过拟合反思：{summary['judgement']['overfit_before']}",
        f"- 运行前继续价值反思：{summary['judgement']['continue_before']}",
        f"- 运行后过拟合反思：{summary['judgement']['overfit_after']}",
        f"- 运行后继续价值反思：{summary['judgement']['continue_after']}",
        "",
        "## 输出文件",
        "",
        _to_markdown_table(pd.DataFrame([{"artifact": key, "path": str(value)} for key, value in paths.items()]), ["artifact", "path"], max_rows=20),
    ]
    paths["report"].write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Check forward data gap for Stage78 shadow daily reports.")
    parser.add_argument("--as-of-date", default=date.today().isoformat(), help="As-of date, YYYY-MM-DD.")
    args = parser.parse_args()

    as_of = _parse_date(args.as_of_date)
    target_date = _previous_trading_day(as_of)
    paths = _paths_for(as_of)

    artifact_status = _build_artifact_status(target_date)
    missing_days = _build_missing_days(artifact_status, target_date)
    action_plan = _build_action_plan(artifact_status, missing_days, target_date)
    summary = _build_summary(as_of, target_date, artifact_status, missing_days, action_plan)

    artifact_status.to_csv(paths["artifact_status"], index=False, encoding="utf-8-sig")
    missing_days.to_csv(paths["missing_trading_days"], index=False, encoding="utf-8-sig")
    action_plan.to_csv(paths["action_plan"], index=False, encoding="utf-8-sig")
    paths["summary"].write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    _write_report(as_of, target_date, artifact_status, missing_days, action_plan, summary, paths)

    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    print(f"wrote: {paths['report']}")


if __name__ == "__main__":
    main()
