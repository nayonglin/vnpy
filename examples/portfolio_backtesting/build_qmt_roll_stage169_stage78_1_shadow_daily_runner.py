from __future__ import annotations

import argparse
import json
import math
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

MODEL_TAG: str = "stage169_50w_qmt_shadow_daily_runner_v1"
OUTPUT_PREFIX: str = "qmt_roll_stage169_50w_qmt_shadow_daily_runner"
STAGE168_PREFIX: str = "qmt_roll_stage168_50w_qmt_shadow_startup"
STAGE168_TAG: str = "stage168_50w_qmt_shadow_startup_v1"
STAGE155_PREFIX: str = "qmt_roll_stage155_stage78_shadow_daily_protocol"
STAGE155_TAG: str = "stage155_stage78_shadow_daily_protocol_v1"

STAGE168_CONFIG_PATH: Path = OUTPUT_DIR / f"{STAGE168_PREFIX}_config_{STAGE168_TAG}.json"
STAGE168_RISK_POLICY_PATH: Path = OUTPUT_DIR / f"{STAGE168_PREFIX}_risk_policy_{STAGE168_TAG}.csv"
STAGE155_DAILY_CONTROL_PATH: Path = OUTPUT_DIR / f"{STAGE155_PREFIX}_daily_control_ledger_{STAGE155_TAG}.csv"
STAGE155_HISTORICAL_INTENT_PATH: Path = OUTPUT_DIR / f"{STAGE155_PREFIX}_historical_intent_ledger_{STAGE155_TAG}.csv"


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
    config = _read_json(STAGE168_CONFIG_PATH)
    risk_policy = _read_csv(STAGE168_RISK_POLICY_PATH)
    daily_control = _read_csv(STAGE155_DAILY_CONTROL_PATH)
    historical_intent = _read_csv(STAGE155_HISTORICAL_INTENT_PATH)

    daily_control["date"] = pd.to_datetime(daily_control["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    for column in ["decision_date", "plan_date"]:
        historical_intent[column] = pd.to_datetime(historical_intent[column], errors="coerce").dt.strftime("%Y-%m-%d")

    numeric_daily_columns = [
        "net_pnl",
        "balance",
        "ddpercent",
        "audited_trade_count",
        "next_open_adverse_cash",
        "next_close_adverse_cash",
        "max_projected_margin_usage_pct",
        "allow_new_orders",
        "manual_review_required",
    ]
    for column in numeric_daily_columns:
        daily_control[column] = pd.to_numeric(daily_control.get(column, 0.0), errors="coerce").fillna(0.0)

    numeric_intent_columns = [
        "planned_volume",
        "expected_margin",
        "next_open_proxy_price",
        "next_close_proxy_price",
        "next_open_available",
        "next_close_available",
        "max_projected_margin_usage_pct",
        "next_open_adverse_cash_proxy",
        "next_close_adverse_cash_proxy",
    ]
    for column in numeric_intent_columns:
        historical_intent[column] = pd.to_numeric(
            historical_intent.get(column, 0.0), errors="coerce"
        ).fillna(0.0)

    return {
        "config": config,
        "risk_policy": risk_policy,
        "daily_control": daily_control.dropna(subset=["date"]).reset_index(drop=True),
        "historical_intent": historical_intent.dropna(subset=["decision_date"]).reset_index(drop=True),
    }


def _default_trade_date(historical_intent: pd.DataFrame) -> str:
    non_empty = historical_intent[historical_intent["decision_date"].astype(str).str.len() > 0]
    if non_empty.empty:
        raise RuntimeError("historical intent ledger has no decision_date")
    return str(non_empty["decision_date"].max())


def _mask_account_id(account_id: str) -> str:
    if not account_id:
        return ""
    if len(account_id) <= 4:
        return "*" * len(account_id)
    return f"{account_id[:2]}***{account_id[-2:]}"


def _env_status() -> dict[str, Any]:
    account_id = os.getenv("QMT_SHADOW_ACCOUNT_ID", "")
    userdata_path = os.getenv("QMT_USERDATA_PATH", "")
    session_id = os.getenv("QMT_SESSION_ID", "")
    userdata_exists = bool(userdata_path) and Path(userdata_path).exists()
    configured = bool(account_id and userdata_path and session_id)
    return {
        "qmt_shadow_account_id_masked": _mask_account_id(account_id),
        "qmt_userdata_path_configured": bool(userdata_path),
        "qmt_userdata_path_exists": userdata_exists,
        "qmt_session_id_configured": bool(session_id),
        "qmt_query_mode": "env_present_not_connected" if configured else "not_configured",
        "real_order_enabled": False,
        "note": "Stage169 does not import xtquant; it only records local readiness for read-only connection.",
    }


def _classify_risk(daily_row: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    policy = config["risk_policy"]
    account = config["account_boundary"]
    dd_abs = abs(min(_safe_float(daily_row.get("ddpercent")), 0.0))
    net_pnl = _safe_float(daily_row.get("net_pnl"))
    daily_loss = abs(min(net_pnl, 0.0))
    margin_usage = _safe_float(daily_row.get("max_projected_margin_usage_pct"))
    execution_adverse = max(
        _safe_float(daily_row.get("next_open_adverse_cash")),
        _safe_float(daily_row.get("next_close_adverse_cash")),
        0.0,
    )

    level = "normal"
    reasons: list[str] = []
    stage155_allow_new_orders = int(_safe_float(daily_row.get("allow_new_orders"), 1.0))
    allow_real_new_orders = stage155_allow_new_orders

    if dd_abs >= account["drawdown_stop_pct"]:
        level = "stop"
        allow_real_new_orders = 0
        reasons.append("drawdown_stop")
    elif dd_abs >= account["drawdown_review_pct"]:
        level = "review"
        reasons.append("drawdown_review")
    elif dd_abs >= account["drawdown_warn_pct"]:
        level = "watch"
        reasons.append("drawdown_watch")

    if margin_usage >= policy["margin_no_new_orders_pct"]:
        level = "stop"
        allow_real_new_orders = 0
        reasons.append("margin_no_new_orders")
    elif margin_usage >= policy["margin_review_pct"] and level not in {"stop"}:
        level = "review"
        reasons.append("margin_review")
    elif margin_usage >= policy["margin_watch_pct"] and level == "normal":
        level = "watch"
        reasons.append("margin_watch")

    if daily_loss >= policy["daily_loss_no_new_orders_cash"]:
        level = "stop"
        allow_real_new_orders = 0
        reasons.append("daily_loss_no_new_orders")
    elif daily_loss >= policy["daily_loss_review_cash"] and level not in {"stop"}:
        level = "review"
        reasons.append("daily_loss_review")
    elif daily_loss >= policy["daily_loss_watch_cash"] and level == "normal":
        level = "watch"
        reasons.append("daily_loss_watch")

    if execution_adverse >= policy["execution_adverse_review_cash"] and level not in {"stop"}:
        level = "review"
        reasons.append("execution_adverse_review")
    elif execution_adverse >= policy["execution_adverse_watch_cash"] and level == "normal":
        level = "watch"
        reasons.append("execution_adverse_watch")

    if _safe_float(daily_row.get("manual_review_required")) > 0 and level == "normal":
        level = "watch"
        reasons.append("stage155_manual_review")

    if level in {"review", "stop"}:
        allow_real_new_orders = 0

    return {
        "risk_level": level,
        "stage155_allow_new_orders": int(stage155_allow_new_orders),
        "allow_shadow_record": 1,
        "allow_real_new_orders": int(allow_real_new_orders),
        "reasons": reasons or ["none"],
        "drawdown_pct_abs": dd_abs,
        "daily_loss_cash": daily_loss,
        "margin_usage_pct": margin_usage,
        "execution_adverse_cash": execution_adverse,
    }


def _build_signal_plan(signals: pd.DataFrame) -> pd.DataFrame:
    if signals.empty:
        return pd.DataFrame(
            columns=[
                "shadow_session_id",
                "product_vt_symbol",
                "vt_symbol",
                "direction",
                "offset",
                "planned_volume",
                "real_t1_open_proxy_price",
                "day_session_open_proxy_price",
                "proxy_quality",
                "shadow_run_permission",
            ]
        )
    plan = signals.copy()
    plan["real_t1_open_proxy_price"] = plan["next_open_proxy_price"]
    plan["day_session_open_proxy_price"] = ""
    plan["proxy_quality"] = "day_session_09_proxy_requires_intraday_or_qmt_bar"
    cols = [
        "shadow_session_id",
        "product_vt_symbol",
        "vt_symbol",
        "direction",
        "offset",
        "planned_volume",
        "real_t1_open_proxy_price",
        "day_session_open_proxy_price",
        "proxy_quality",
        "shadow_run_permission",
    ]
    return plan.loc[:, cols].sort_values(["product_vt_symbol", "vt_symbol"]).reset_index(drop=True)


def _paths_for_date(trade_date: str) -> dict[str, Path]:
    date_key = trade_date.replace("-", "")
    return {
        "signal_plan": OUTPUT_DIR / f"{OUTPUT_PREFIX}_signal_plan_{date_key}_{MODEL_TAG}.csv",
        "risk_snapshot": OUTPUT_DIR / f"{OUTPUT_PREFIX}_risk_snapshot_{date_key}_{MODEL_TAG}.json",
        "daily_report": OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_report_{date_key}_{MODEL_TAG}.md",
        "summary": OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{date_key}_{MODEL_TAG}.json",
    }


def _write_report(
    trade_date: str,
    config: dict[str, Any],
    daily_row: dict[str, Any],
    signal_plan: pd.DataFrame,
    risk_snapshot: dict[str, Any],
    qmt_env: dict[str, Any],
    paths: dict[str, Path],
) -> None:
    lines = [
        "# Stage169 50w QMT影子盘日报",
        "",
        f"- 交易日：`{trade_date}`",
        f"- 策略版本：`{config['strategy']['version']}`",
        f"- 资金边界：`{config['account_boundary']['shadow_capital']:,.0f}`",
        "- 运行模式：`offline_shadow_read_only`",
        "- 真实报单：`false`",
        "- 夜盘自动报单：`false`",
        "",
        "## 今日结论",
        "",
        f"- 风险级别：`{risk_snapshot['risk_level']}`",
        f"- 是否允许影子盘记录：`{risk_snapshot['allow_shadow_record']}`",
        f"- 是否允许真实新增开仓：`{risk_snapshot['allow_real_new_orders']}`",
        f"- 触发原因：`{', '.join(risk_snapshot['reasons'])}`",
        f"- 当日理论/历史信号数：`{len(signal_plan)}`",
        "",
        "## 信号计划",
        "",
        _to_markdown_table(
            signal_plan,
            [
                "shadow_session_id",
                "product_vt_symbol",
                "vt_symbol",
                "direction",
                "offset",
                "planned_volume",
                "real_t1_open_proxy_price",
                "day_session_open_proxy_price",
                "proxy_quality",
                "shadow_run_permission",
            ],
            max_rows=40,
        ),
        "",
        "## 风险快照",
        "",
        f"- 当前历史代理回撤：`{risk_snapshot['drawdown_pct_abs']:.4f}%`",
        f"- 当日历史代理亏损：`{risk_snapshot['daily_loss_cash']:,.0f}`",
        f"- 计划保证金占用：`{risk_snapshot['margin_usage_pct']:.4f}%`",
        f"- 执行不利冲击代理：`{risk_snapshot['execution_adverse_cash']:,.0f}`",
        f"- Stage155执行状态：`{daily_row.get('execution_status', '')}`",
        f"- Stage155动作建议：{daily_row.get('required_action', '')}",
        "",
        "## QMT只读就绪",
        "",
        f"- 账号环境变量：`{'configured' if qmt_env['qmt_shadow_account_id_masked'] else 'missing'}`",
        f"- 账号脱敏：`{qmt_env['qmt_shadow_account_id_masked']}`",
        f"- userdata路径已配置：`{qmt_env['qmt_userdata_path_configured']}`",
        f"- userdata路径存在：`{qmt_env['qmt_userdata_path_exists']}`",
        f"- session_id已配置：`{qmt_env['qmt_session_id_configured']}`",
        f"- QMT查询状态：`{qmt_env['qmt_query_mode']}`",
        "",
        "## 异常",
        "",
        "- `day_session_open_proxy_price`仍需接入分钟线或QMT行情后补齐。",
        "- QMT只读查询尚未接入；本报告先验证日报结构和风控闸门。",
        "",
        "## 输出文件",
        "",
        _to_markdown_table(pd.DataFrame([{"artifact": key, "path": str(path)} for key, path in paths.items()]), ["artifact", "path"]),
        "",
        "## 反思",
        "",
        "- 运行前过拟合反思：否。Stage169只是按固定Stage155意图和Stage168风控生成日报，不改信号。",
        "- 运行后过拟合反思：否。没有根据日报结果修改参数或筛掉信号。",
        "- 运行前继续价值反思：是。日报runner是影子盘能否长期运行的基本闭环。",
        "- 运行后继续价值反思：是。下一步接入QMT只读查询和分钟线代理价即可转入真实前向记录。",
    ]
    paths["daily_report"].write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build one Stage169 50w QMT shadow daily report.")
    parser.add_argument("--trade-date", default="", help="Decision date to report, YYYY-MM-DD. Defaults to latest signal date.")
    args = parser.parse_args()

    inputs = _load_inputs()
    trade_date = args.trade_date or _default_trade_date(inputs["historical_intent"])
    paths = _paths_for_date(trade_date)

    daily_matches = inputs["daily_control"][inputs["daily_control"]["date"] == trade_date]
    if daily_matches.empty:
        raise RuntimeError(f"trade date {trade_date} not found in daily control ledger")
    daily_row = daily_matches.iloc[-1].to_dict()
    signals = inputs["historical_intent"][inputs["historical_intent"]["decision_date"] == trade_date].copy()
    signal_plan = _build_signal_plan(signals)
    risk_snapshot = _classify_risk(daily_row, inputs["config"])
    risk_snapshot.update(
        {
            "trade_date": trade_date,
            "strategy_version": inputs["config"]["strategy"]["version"],
            "signal_count": int(len(signal_plan)),
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
    )
    qmt_env = _env_status()
    summary = {
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "trade_date": trade_date,
        "is_strategy_change": False,
        "is_backtest": False,
        "signal_count": int(len(signal_plan)),
        "risk_snapshot": risk_snapshot,
        "qmt_env": qmt_env,
        "outputs": {key: str(value) for key, value in paths.items()},
        "judgement": {
            "overfit_before": "否。固定Stage78与Stage168风控，只生成单日日报。",
            "continue_before": "是。先跑通离线日报结构，才能接真实QMT只读数据。",
            "overfit_after": "否。没有修改任何策略参数或过滤信号。",
            "continue_after": "是。下一步接入QMT只读查询和分钟线/夜盘代理价。",
        },
    }

    signal_plan.to_csv(paths["signal_plan"], index=False, encoding="utf-8-sig")
    paths["risk_snapshot"].write_text(json.dumps(risk_snapshot, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    paths["summary"].write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    _write_report(trade_date, inputs["config"], daily_row, signal_plan, risk_snapshot, qmt_env, paths)

    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    print(f"wrote: {paths['daily_report']}")


if __name__ == "__main__":
    main()
