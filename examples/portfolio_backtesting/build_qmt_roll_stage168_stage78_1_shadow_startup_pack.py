from __future__ import annotations

import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from qmt_roll_official_stage78_config import (
    OFFICIAL_STAGE78_CAPITAL,
    OFFICIAL_STAGE78_REFERENCE_METRICS,
    OFFICIAL_STAGE78_ROLE,
    OFFICIAL_STAGE78_VERSION,
)


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

MODEL_TAG: str = "stage168_50w_qmt_shadow_startup_v1"
OUTPUT_PREFIX: str = "qmt_roll_stage168_50w_qmt_shadow_startup"
STAGE155_PREFIX: str = "qmt_roll_stage155_stage78_shadow_daily_protocol"
STAGE155_TAG: str = "stage155_stage78_shadow_daily_protocol_v1"

STAGE155_SUMMARY_PATH: Path = OUTPUT_DIR / f"{STAGE155_PREFIX}_summary_{STAGE155_TAG}.json"
STAGE155_DAILY_CONTROL_PATH: Path = OUTPUT_DIR / f"{STAGE155_PREFIX}_daily_control_ledger_{STAGE155_TAG}.csv"
STAGE155_HISTORICAL_INTENT_PATH: Path = OUTPUT_DIR / f"{STAGE155_PREFIX}_historical_intent_ledger_{STAGE155_TAG}.csv"
STAGE155_SOP_PATH: Path = OUTPUT_DIR / f"{STAGE155_PREFIX}_sop_{STAGE155_TAG}.md"

STARTUP_CONFIG_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_config_{MODEL_TAG}.json"
RISK_POLICY_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_risk_policy_{MODEL_TAG}.csv"
QMT_FIELD_MAP_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_qmt_field_map_{MODEL_TAG}.csv"
DAILY_REPORT_TEMPLATE_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_report_template_{MODEL_TAG}.md"
RUNBOOK_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_runbook_{MODEL_TAG}.md"
SUMMARY_JSON_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.json"
REPORT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

SHADOW_CAPITAL: float = OFFICIAL_STAGE78_CAPITAL
MAX_TOLERABLE_DRAWDOWN_PCT: float = 40.0
DRAW_DOWN_WARN_PCT: float = 20.0
DRAW_DOWN_REVIEW_PCT: float = 30.0
DRAW_DOWN_STOP_PCT: float = 40.0
MARGIN_WATCH_PCT: float = 60.0
MARGIN_REVIEW_PCT: float = 70.0
MARGIN_NO_NEW_ORDERS_PCT: float = 80.0
DAILY_LOSS_WATCH_PCT: float = 2.0
DAILY_LOSS_REVIEW_PCT: float = 4.0
DAILY_LOSS_NO_NEW_ORDERS_PCT: float = 6.0
EXECUTION_ADVERSE_WATCH_PCT: float = 1.0
EXECUTION_ADVERSE_REVIEW_PCT: float = 2.0


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


def _to_markdown_table(df: pd.DataFrame, columns: list[str] | None = None, max_rows: int = 30) -> str:
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


def _load_inputs() -> dict[str, Any]:
    summary = _read_json(STAGE155_SUMMARY_PATH)
    daily_control = _read_csv(STAGE155_DAILY_CONTROL_PATH)
    historical_intent = _read_csv(STAGE155_HISTORICAL_INTENT_PATH)

    for frame in (daily_control, historical_intent):
        for column in frame.columns:
            if column.endswith("_date") or column == "date":
                frame[column] = pd.to_datetime(frame[column], errors="coerce").dt.strftime("%Y-%m-%d")

    numeric_daily = [
        "net_pnl",
        "balance",
        "ddpercent",
        "audited_trade_count",
        "next_open_adverse_cash",
        "next_close_adverse_cash",
        "max_projected_margin_usage_pct",
        "manual_review_required",
        "allow_new_orders",
    ]
    for column in numeric_daily:
        daily_control[column] = pd.to_numeric(daily_control.get(column, 0.0), errors="coerce").fillna(0.0)

    numeric_intent = [
        "planned_volume",
        "expected_margin",
        "max_projected_margin_usage_pct",
        "next_open_available",
        "next_close_available",
    ]
    for column in numeric_intent:
        historical_intent[column] = pd.to_numeric(
            historical_intent.get(column, 0.0), errors="coerce"
        ).fillna(0.0)

    return {
        "summary": summary,
        "daily_control": daily_control,
        "historical_intent": historical_intent,
    }


def _cash_threshold(pct: float) -> float:
    return SHADOW_CAPITAL * pct / 100.0


def _build_startup_config(stage155_summary: dict[str, Any]) -> dict[str, Any]:
    reference = OFFICIAL_STAGE78_REFERENCE_METRICS["full_2020_2026"]
    latest = OFFICIAL_STAGE78_REFERENCE_METRICS["latest_2026"]
    source_max_margin = _safe_float(stage155_summary.get("source_stage154", {}).get("max_projected_margin_usage_pct"))
    capital_adjusted_margin = source_max_margin * OFFICIAL_STAGE78_CAPITAL / SHADOW_CAPITAL

    return {
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "is_strategy_change": False,
        "is_backtest": False,
        "strategy": {
            "version": OFFICIAL_STAGE78_VERSION,
            "role": OFFICIAL_STAGE78_ROLE,
            "formal_capital": OFFICIAL_STAGE78_CAPITAL,
            "reference_metrics": {
                "full_2020_2026": reference,
                "latest_2026": latest,
            },
        },
        "account_boundary": {
            "shadow_capital": SHADOW_CAPITAL,
            "max_tolerable_drawdown_pct": MAX_TOLERABLE_DRAWDOWN_PCT,
            "max_tolerable_loss_cash": _cash_threshold(MAX_TOLERABLE_DRAWDOWN_PCT),
            "drawdown_warn_pct": DRAW_DOWN_WARN_PCT,
            "drawdown_warn_loss_cash": _cash_threshold(DRAW_DOWN_WARN_PCT),
            "drawdown_review_pct": DRAW_DOWN_REVIEW_PCT,
            "drawdown_review_loss_cash": _cash_threshold(DRAW_DOWN_REVIEW_PCT),
            "drawdown_stop_pct": DRAW_DOWN_STOP_PCT,
            "drawdown_stop_loss_cash": _cash_threshold(DRAW_DOWN_STOP_PCT),
        },
        "execution_policy": {
            "signal_source": "Stage78 trading-day daily bar",
            "signal_freeze_time": "after T trading day 15:00 close",
            "night_session_shadow_policy": "record_real_t1_open_proxy",
            "real_t1_open_proxy": "night products use T evening 21:00 area; non-night products use next day 09:00 area",
            "day_session_open_proxy": "all products additionally record next day 09:00 area",
            "real_money_order_mode_initial": "read_only_or_simulated_shadow",
            "real_money_night_auto_order": False,
            "real_order_enabled": False,
            "allowed_live_action_now": "generate_signals_and_reconcile_only",
        },
        "risk_policy": {
            "margin_watch_pct": MARGIN_WATCH_PCT,
            "margin_review_pct": MARGIN_REVIEW_PCT,
            "margin_no_new_orders_pct": MARGIN_NO_NEW_ORDERS_PCT,
            "daily_loss_watch_cash": _cash_threshold(DAILY_LOSS_WATCH_PCT),
            "daily_loss_review_cash": _cash_threshold(DAILY_LOSS_REVIEW_PCT),
            "daily_loss_no_new_orders_cash": _cash_threshold(DAILY_LOSS_NO_NEW_ORDERS_PCT),
            "execution_adverse_watch_cash": _cash_threshold(EXECUTION_ADVERSE_WATCH_PCT),
            "execution_adverse_review_cash": _cash_threshold(EXECUTION_ADVERSE_REVIEW_PCT),
            "source_stage155_max_projected_margin_usage_pct": source_max_margin,
            "capital_adjusted_max_projected_margin_usage_pct_proxy": capital_adjusted_margin,
        },
        "qmt_local_security": {
            "account_id_env": "QMT_SHADOW_ACCOUNT_ID",
            "userdata_path_env": "QMT_USERDATA_PATH",
            "session_id_env": "QMT_SESSION_ID",
            "password_policy": "do_not_store_in_repo_or_chat",
            "first_connection_mode": "query_only",
            "write_api_initially_disabled": True,
        },
        "stage155_sources": {
            "summary": str(STAGE155_SUMMARY_PATH),
            "daily_control": str(STAGE155_DAILY_CONTROL_PATH),
            "historical_intent": str(STAGE155_HISTORICAL_INTENT_PATH),
            "sop": str(STAGE155_SOP_PATH),
        },
    }


def _build_risk_policy(config: dict[str, Any]) -> pd.DataFrame:
    rows = [
        {
            "risk_layer": "drawdown",
            "level": "watch",
            "threshold": f"{DRAW_DOWN_WARN_PCT:.0f}%",
            "cash_value": _cash_threshold(DRAW_DOWN_WARN_PCT),
            "action": "日报标黄；检查持仓集中、滑点和是否处于历史冷启动亏损带。",
        },
        {
            "risk_layer": "drawdown",
            "level": "review",
            "threshold": f"{DRAW_DOWN_REVIEW_PCT:.0f}%",
            "cash_value": _cash_threshold(DRAW_DOWN_REVIEW_PCT),
            "action": "暂停放大风险；只允许影子盘继续记录，人工复核是否和历史压力段一致。",
        },
        {
            "risk_layer": "drawdown",
            "level": "stop",
            "threshold": f"{DRAW_DOWN_STOP_PCT:.0f}%",
            "cash_value": _cash_threshold(DRAW_DOWN_STOP_PCT),
            "action": "硬停止新增开仓；只允许降风险、平风险和人工接管。",
        },
        {
            "risk_layer": "margin_usage",
            "level": "watch",
            "threshold": f"{MARGIN_WATCH_PCT:.0f}%",
            "cash_value": "",
            "action": "日报标黄；确认可用资金和保证金口径。",
        },
        {
            "risk_layer": "margin_usage",
            "level": "review",
            "threshold": f"{MARGIN_REVIEW_PCT:.0f}%",
            "cash_value": "",
            "action": "人工复核后才允许记录新增开仓意图；真实资金不得自动开仓。",
        },
        {
            "risk_layer": "margin_usage",
            "level": "no_new_orders",
            "threshold": f"{MARGIN_NO_NEW_ORDERS_PCT:.0f}%",
            "cash_value": "",
            "action": "禁止新增开仓，只允许降风险。",
        },
        {
            "risk_layer": "daily_loss",
            "level": "watch",
            "threshold": f"{DAILY_LOSS_WATCH_PCT:.0f}% capital",
            "cash_value": _cash_threshold(DAILY_LOSS_WATCH_PCT),
            "action": "检查是否由跳空、滑点、持仓集中或数据异常导致。",
        },
        {
            "risk_layer": "daily_loss",
            "level": "review",
            "threshold": f"{DAILY_LOSS_REVIEW_PCT:.0f}% capital",
            "cash_value": _cash_threshold(DAILY_LOSS_REVIEW_PCT),
            "action": "当天不允许真实新增开仓；继续影子盘记录和对账。",
        },
        {
            "risk_layer": "daily_loss",
            "level": "no_new_orders",
            "threshold": f"{DAILY_LOSS_NO_NEW_ORDERS_PCT:.0f}% capital",
            "cash_value": _cash_threshold(DAILY_LOSS_NO_NEW_ORDERS_PCT),
            "action": "进入当日停机复核。",
        },
        {
            "risk_layer": "execution_adverse",
            "level": "watch",
            "threshold": f"{EXECUTION_ADVERSE_WATCH_PCT:.0f}% capital",
            "cash_value": _cash_threshold(EXECUTION_ADVERSE_WATCH_PCT),
            "action": "标记执行偏差观察；不得因单日偏差改策略。",
        },
        {
            "risk_layer": "execution_adverse",
            "level": "review",
            "threshold": f"{EXECUTION_ADVERSE_REVIEW_PCT:.0f}% capital",
            "cash_value": _cash_threshold(EXECUTION_ADVERSE_REVIEW_PCT),
            "action": "连续出现时暂停真实接入计划，先复核执行窗口。",
        },
    ]
    policy = pd.DataFrame(rows)
    policy["strategy_version"] = config["strategy"]["version"]
    policy["shadow_capital"] = SHADOW_CAPITAL
    return policy


def _build_qmt_field_map() -> pd.DataFrame:
    rows = [
        {
            "stage168_table": "qmt_connection",
            "field_name": "userdata_path",
            "qmt_source": "QMT_USERDATA_PATH env / local client userdata_mini",
            "required_phase": "read_only",
            "security_rule": "local_env_only",
            "notes": "路径不写入公开报告，可在本机私有配置保存。",
        },
        {
            "stage168_table": "qmt_connection",
            "field_name": "account_id",
            "qmt_source": "QMT_SHADOW_ACCOUNT_ID env / StockAccount",
            "required_phase": "read_only",
            "security_rule": "mask_in_reports",
            "notes": "聊天和仓库只记录脱敏账号。",
        },
        {
            "stage168_table": "account_reconcile",
            "field_name": "total_asset",
            "qmt_source": "XtQuantTrader.query_stock_asset / on_stock_asset",
            "required_phase": "read_only",
            "security_rule": "numeric_only",
            "notes": "用于权益、回撤和资金对账。",
        },
        {
            "stage168_table": "account_reconcile",
            "field_name": "cash",
            "qmt_source": "XtAsset.cash",
            "required_phase": "read_only",
            "security_rule": "numeric_only",
            "notes": "用于可用资金检查。",
        },
        {
            "stage168_table": "position_reconcile",
            "field_name": "positions",
            "qmt_source": "query_stock_positions / on_stock_position",
            "required_phase": "read_only",
            "security_rule": "symbol_and_volume_only",
            "notes": "先做真实持仓查询，不做报单。",
        },
        {
            "stage168_table": "order_event",
            "field_name": "order_status",
            "qmt_source": "on_stock_order / query_stock_orders",
            "required_phase": "simulated_order",
            "security_rule": "record_raw_status",
            "notes": "回调和查询都要落表，二者不一致时进入exception。",
        },
        {
            "stage168_table": "fill_event",
            "field_name": "fill_price",
            "qmt_source": "on_stock_trade / query_stock_trades",
            "required_phase": "simulated_order",
            "security_rule": "record_fill_level",
            "notes": "计算相对real_t1_open_proxy和day_session_open_proxy的成交偏差。",
        },
        {
            "stage168_table": "exception",
            "field_name": "connection_status",
            "qmt_source": "on_connected / on_disconnected / query_account_status",
            "required_phase": "read_only",
            "security_rule": "no_secret",
            "notes": "断线、延迟、重复回报都先暂停真实接入。",
        },
    ]
    return pd.DataFrame(rows)


def _build_startup_gates(config: dict[str, Any], daily_control: pd.DataFrame) -> pd.DataFrame:
    reference_dd = abs(_safe_float(config["strategy"]["reference_metrics"]["full_2020_2026"]["max_dd_percent"]))
    allowed_dd = config["account_boundary"]["max_tolerable_drawdown_pct"]
    dd_buffer = allowed_dd - reference_dd
    capital_adjusted_margin = config["risk_policy"]["capital_adjusted_max_projected_margin_usage_pct_proxy"]
    manual_review_days = int(daily_control["manual_review_required"].sum())
    no_new_orders_days = int((daily_control["allow_new_orders"] == 0).sum())

    rows = [
        {
            "gate": "Stage78 version freeze",
            "status": "PASS",
            "evidence": f"{OFFICIAL_STAGE78_VERSION} remains the frozen formal baseline.",
            "required_action": "不改Stage78参数。",
        },
        {
            "gate": "50w drawdown boundary",
            "status": "WATCH" if dd_buffer < 5 else "PASS",
            "evidence": f"历史最大回撤约{reference_dd:.2f}%，用户硬边界{allowed_dd:.2f}%，缓冲{dd_buffer:.2f}个百分点。",
            "required_action": "只允许影子盘或小风险试运行前置验证；不得满风险直接实盘。",
        },
        {
            "gate": "50w margin proxy",
            "status": "PASS" if capital_adjusted_margin < MARGIN_WATCH_PCT else "WATCH",
            "evidence": f"Stage155最大计划保证金占用折算50万约{capital_adjusted_margin:.2f}%。",
            "required_action": "影子盘日报继续跟踪真实保证金占用。",
        },
        {
            "gate": "Stage155 manual review days",
            "status": "WATCH" if manual_review_days > 0 else "PASS",
            "evidence": f"历史协议中需要人工复核日{manual_review_days}天，禁止新增开仓日{no_new_orders_days}天。",
            "required_action": "日报必须暴露复核原因，不允许自动忽略。",
        },
        {
            "gate": "Night session policy",
            "status": "PASS",
            "evidence": "影子盘记录真实T+1开盘代理价和保守日盘09:00代理价；真钱第一版不自动夜盘报单。",
            "required_action": "后续脚本补齐real_t1_open_proxy与day_session_open_proxy字段。",
        },
        {
            "gate": "QMT credentials",
            "status": "BLOCKED_BY_USER_ENV",
            "evidence": "账号、userdata路径、会话号必须在本机环境变量或QMT客户端配置，不进入聊天和仓库。",
            "required_action": "用户在本机配置QMT_SHADOW_ACCOUNT_ID、QMT_USERDATA_PATH、QMT_SESSION_ID。",
        },
        {
            "gate": "QMT write permission",
            "status": "NOT_ALLOWED_YET",
            "evidence": "当前启动包只允许查询资金、持仓、委托、成交；真实报单开关保持关闭。",
            "required_action": "至少20-30个交易日影子盘稳定后再评审。",
        },
    ]
    return pd.DataFrame(rows)


def _write_daily_report_template(config: dict[str, Any]) -> None:
    lines = [
        "# Stage78 50w QMT影子盘日报",
        "",
        "- 交易日：`YYYY-MM-DD`",
        f"- 策略版本：`{config['strategy']['version']}`",
        f"- 影子盘资金：`{SHADOW_CAPITAL:,.0f}`",
        "- 运行模式：`read_only_or_simulated_shadow`",
        "- 信号冻结：`yes/no`",
        "",
        "## 今日结论",
        "",
        "- 今日是否允许新增开仓：",
        "- 今日是否需要人工复核：",
        "- 今日最大问题：",
        "- 明日动作：",
        "",
        "## 信号与订单计划",
        "",
        "| shadow_session_id | product | vt_symbol | direction | offset | volume | reason | real_t1_open_proxy | day_session_open_proxy | permission |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        "",
        "## 风险检查",
        "",
        f"- 当前回撤预警线：`{DRAW_DOWN_WARN_PCT:.0f}%` / `{_cash_threshold(DRAW_DOWN_WARN_PCT):,.0f}`",
        f"- 当前回撤复核线：`{DRAW_DOWN_REVIEW_PCT:.0f}%` / `{_cash_threshold(DRAW_DOWN_REVIEW_PCT):,.0f}`",
        f"- 当前回撤硬停止：`{DRAW_DOWN_STOP_PCT:.0f}%` / `{_cash_threshold(DRAW_DOWN_STOP_PCT):,.0f}`",
        f"- 保证金watch/review/no-new：`{MARGIN_WATCH_PCT:.0f}%` / `{MARGIN_REVIEW_PCT:.0f}%` / `{MARGIN_NO_NEW_ORDERS_PCT:.0f}%`",
        f"- 单日亏损watch/review/no-new：`{_cash_threshold(DAILY_LOSS_WATCH_PCT):,.0f}` / `{_cash_threshold(DAILY_LOSS_REVIEW_PCT):,.0f}` / `{_cash_threshold(DAILY_LOSS_NO_NEW_ORDERS_PCT):,.0f}`",
        "",
        "## QMT只读对账",
        "",
        "- 连接状态：",
        "- 账户权益：",
        "- 可用资金：",
        "- 保证金占用/风险率：",
        "- 持仓差异：",
        "- 委托差异：",
        "- 成交差异：",
        "",
        "## 异常记录",
        "",
        "| exception_id | type | severity | related_id | action | note |",
        "| --- | --- | --- | --- | --- | --- |",
        "",
        "## 当日判断",
        "",
        "- 过拟合反思：否/是；原因：",
        "- 继续价值反思：否/是；原因：",
    ]
    DAILY_REPORT_TEMPLATE_PATH.write_text("\n".join(lines), encoding="utf-8")


def _write_runbook(config: dict[str, Any], field_map: pd.DataFrame, risk_policy: pd.DataFrame) -> None:
    lines = [
        "# Stage168 50w QMT影子盘启动Runbook",
        "",
        "## 定位",
        "",
        "- 本启动包不是新策略，不修改Stage78正式信号和参数。",
        "- 当前只允许影子盘和QMT只读查询；真实报单开关保持关闭。",
        "- 目标是把50万资金、40%最大容忍回撤、夜盘交易日口径和QMT对账字段固定下来。",
        "",
        "## 本机私有配置",
        "",
        "- `QMT_SHADOW_ACCOUNT_ID`：QMT账号标识，报告中必须脱敏。",
        "- `QMT_USERDATA_PATH`：QMT客户端`userdata_mini`或对应本机目录。",
        "- `QMT_SESSION_ID`：本地连接会话号，可用固定整数。",
        "- 账号密码不得写入仓库、聊天、stage文件或日报。",
        "",
        "## 每日流程",
        "",
        "1. T日15:00后生成Stage78理论信号并冻结。",
        "2. 识别下一交易日执行代理价：有夜盘品种记录当晚21:00附近，无夜盘品种记录次日09:00附近。",
        "3. 额外记录所有品种次日09:00日盘代理价，作为保守执行对照。",
        "4. QMT只读查询账户权益、可用资金、持仓、委托、成交和连接状态。",
        "5. 生成日报，任何持仓/资金/成交差异都必须进入异常表。",
        "6. 连续20-30个交易日稳定后，才讨论模拟报单；真钱自动夜盘报单另行评审。",
        "",
        "## 风控规则",
        "",
        _to_markdown_table(risk_policy, ["risk_layer", "level", "threshold", "cash_value", "action"], max_rows=30),
        "",
        "## QMT字段映射",
        "",
        _to_markdown_table(field_map, ["stage168_table", "field_name", "qmt_source", "required_phase", "notes"], max_rows=30),
        "",
        "## 当前判断",
        "",
        f"- Stage78历史最大回撤约`{abs(config['strategy']['reference_metrics']['full_2020_2026']['max_dd_percent']):.2f}%`，低于用户`40%`硬边界但缓冲很薄。",
        f"- 50万最大容忍亏损约`{config['account_boundary']['max_tolerable_loss_cash']:,.0f}`。",
        "- 现阶段结论是可进入影子盘启动，不可直接实盘。",
    ]
    RUNBOOK_PATH.write_text("\n".join(lines), encoding="utf-8")


def _build_summary(
    config: dict[str, Any],
    risk_policy: pd.DataFrame,
    field_map: pd.DataFrame,
    gates: pd.DataFrame,
    daily_control: pd.DataFrame,
    historical_intent: pd.DataFrame,
) -> dict[str, Any]:
    status_counts = gates["status"].value_counts().to_dict()
    return {
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "is_strategy_change": False,
        "is_backtest": False,
        "official_version": OFFICIAL_STAGE78_VERSION,
        "shadow_capital": SHADOW_CAPITAL,
        "max_tolerable_drawdown_pct": MAX_TOLERABLE_DRAWDOWN_PCT,
        "max_tolerable_loss_cash": _cash_threshold(MAX_TOLERABLE_DRAWDOWN_PCT),
        "allowed_next_mode": "50w_qmt_shadow_read_only",
        "real_order_enabled": False,
        "real_money_night_auto_order": False,
        "startup_gate_status_counts": {str(key): int(value) for key, value in status_counts.items()},
        "stage155_daily_control_rows": int(len(daily_control)),
        "stage155_historical_intent_rows": int(len(historical_intent)),
        "risk_policy_rows": int(len(risk_policy)),
        "qmt_field_map_rows": int(len(field_map)),
        "judgement": {
            "overfit_before": "否。Stage168只把用户资金、回撤边界、QMT只读接入和夜盘口径写成启动包，不修改策略参数。",
            "continue_before": "是。Stage78进入实盘前最缺的是真实前向执行、持仓和资金闭环。",
            "overfit_after": "否。本阶段没有新增买卖规则，没有根据历史结果筛选品种或日期。",
            "continue_after": "是。下一步可以实现每日影子盘runner和QMT只读健康检查。",
        },
        "outputs": {
            "startup_config": str(STARTUP_CONFIG_PATH),
            "risk_policy": str(RISK_POLICY_PATH),
            "qmt_field_map": str(QMT_FIELD_MAP_PATH),
            "daily_report_template": str(DAILY_REPORT_TEMPLATE_PATH),
            "runbook": str(RUNBOOK_PATH),
            "summary": str(SUMMARY_JSON_PATH),
            "report": str(REPORT_PATH),
        },
    }


def _write_report(summary: dict[str, Any], config: dict[str, Any], gates: pd.DataFrame) -> None:
    reference = config["strategy"]["reference_metrics"]["full_2020_2026"]
    latest = config["strategy"]["reference_metrics"]["latest_2026"]
    gate_cols = ["gate", "status", "evidence", "required_action"]
    lines = [
        "# Stage168 50w QMT影子盘启动包",
        "",
        "## 定位",
        "",
        "- 本阶段不是新策略版本，不修改Stage78正式参数，不触发A/B。",
        "- 目标是把50万资金、40%最大容忍回撤、QMT只读接入、安全边界和夜盘执行口径固化为可运行启动包。",
        "",
        "## Stage78冻结基准",
        "",
        f"- 版本：`{OFFICIAL_STAGE78_VERSION}`",
        f"- 角色：`{OFFICIAL_STAGE78_ROLE}`",
        f"- 全周期：期末权益`{reference['end_balance']:,.0f}`，总收益`{reference['total_return_pct']:.4f}%`，最大回撤`{reference['max_dd_percent']:.4f}%`，Sharpe`{reference['sharpe_ratio']:.4f}`，总滑点`{reference['total_slippage']:,.0f}`，交易`{reference['total_trade_count']:,.0f}`。",
        f"- latest_2026：期末权益`{latest['end_balance']:,.0f}`，总收益`{latest['total_return_pct']:.4f}%`，最大回撤`{latest['max_dd_percent']:.4f}%`，Sharpe`{latest['sharpe_ratio']:.4f}`。",
        "",
        "## 50万实盘边界",
        "",
        f"- 资金规模：`{SHADOW_CAPITAL:,.0f}`",
        f"- 最大可接受回撤：`{MAX_TOLERABLE_DRAWDOWN_PCT:.0f}%`，约`{_cash_threshold(MAX_TOLERABLE_DRAWDOWN_PCT):,.0f}`。",
        f"- 预警/复核/硬停止：`{DRAW_DOWN_WARN_PCT:.0f}%` / `{DRAW_DOWN_REVIEW_PCT:.0f}%` / `{DRAW_DOWN_STOP_PCT:.0f}%`。",
        f"- 保证金watch/review/no-new：`{MARGIN_WATCH_PCT:.0f}%` / `{MARGIN_REVIEW_PCT:.0f}%` / `{MARGIN_NO_NEW_ORDERS_PCT:.0f}%`。",
        "",
        "## 启动闸门",
        "",
        _to_markdown_table(gates, gate_cols, max_rows=20),
        "",
        "## 夜盘与QMT策略",
        "",
        "- 影子盘记录真实T+1开盘代理价：有夜盘品种按当晚21:00附近，无夜盘品种按次日09:00附近。",
        "- 同时记录保守日盘09:00代理价，给执行偏差做A/B式对账，但不改变策略信号。",
        "- QMT第一步只读查询资金、持仓、委托、成交和连接状态；真实报单和夜盘自动报单均关闭。",
        "- 账号密码不进入聊天、仓库、日报或stage记录，只允许本机环境变量或QMT客户端安全配置。",
        "",
        "## 输出文件",
        "",
        _to_markdown_table(pd.DataFrame([{"artifact": k, "path": v} for k, v in summary["outputs"].items()]), ["artifact", "path"], max_rows=20),
        "",
        "## 反思",
        "",
        f"- 运行前过拟合反思：{summary['judgement']['overfit_before']}",
        f"- 运行前继续价值反思：{summary['judgement']['continue_before']}",
        f"- 运行后过拟合反思：{summary['judgement']['overfit_after']}",
        f"- 运行后继续价值反思：{summary['judgement']['continue_after']}",
        "",
        "## 结论",
        "",
        "- 可以进入`50w_qmt_shadow_read_only`。",
        "- 不能直接进入真钱自动交易。",
        "- 下一步应实现每日runner：生成信号、补夜盘/日盘代理价、读取QMT账户与持仓、生成日报。",
    ]
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    inputs = _load_inputs()
    config = _build_startup_config(inputs["summary"])
    risk_policy = _build_risk_policy(config)
    field_map = _build_qmt_field_map()
    gates = _build_startup_gates(config, inputs["daily_control"])
    summary = _build_summary(config, risk_policy, field_map, gates, inputs["daily_control"], inputs["historical_intent"])

    STARTUP_CONFIG_PATH.write_text(json.dumps(config, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    risk_policy.to_csv(RISK_POLICY_PATH, index=False, encoding="utf-8-sig")
    field_map.to_csv(QMT_FIELD_MAP_PATH, index=False, encoding="utf-8-sig")
    _write_daily_report_template(config)
    _write_runbook(config, field_map, risk_policy)
    SUMMARY_JSON_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    _write_report(summary, config, gates)

    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    print(f"wrote: {REPORT_PATH}")
    print(f"wrote: {RUNBOOK_PATH}")


if __name__ == "__main__":
    main()
