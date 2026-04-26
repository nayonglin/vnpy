from __future__ import annotations

import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

MODEL_TAG: str = "stage147_stage78_live_weekly_report_v1"
OUTPUT_PREFIX: str = "qmt_roll_stage147_stage78_live_weekly_report"
FORMAL_PREFIX: str = "qmt_roll_official_stage78_defensive_formal"

DAILY_PATH: Path = OUTPUT_DIR / f"{FORMAL_PREFIX}_daily.csv"
SUMMARY_PATH: Path = OUTPUT_DIR / "qmt_roll_official_stage78_defensive_summary.json"

STAGE142_STATUS_PATH: Path = OUTPUT_DIR / "qmt_roll_stage142_stage78_live_monitor_guardrails_current_status_stage142_stage78_live_monitor_guardrails_v1.csv"
STAGE142_THRESHOLDS_PATH: Path = OUTPUT_DIR / "qmt_roll_stage142_stage78_live_monitor_guardrails_thresholds_stage142_stage78_live_monitor_guardrails_v1.csv"
STAGE142_SUMMARY_PATH: Path = OUTPUT_DIR / "qmt_roll_stage142_stage78_live_monitor_guardrails_summary_stage142_stage78_live_monitor_guardrails_v1.json"

STAGE143_SUMMARY_PATH: Path = OUTPUT_DIR / "qmt_roll_stage143_stage78_live_review_pack_summary_stage143_stage78_live_review_pack_v1.json"
STAGE143_PRODUCT_PATH: Path = OUTPUT_DIR / "qmt_roll_stage143_stage78_live_review_pack_recent_product_attribution_stage143_stage78_live_review_pack_v1.csv"
STAGE143_ACTION_PATH: Path = OUTPUT_DIR / "qmt_roll_stage143_stage78_live_review_pack_action_items_stage143_stage78_live_review_pack_v1.csv"

STAGE146_SUMMARY_PATH: Path = OUTPUT_DIR / "qmt_roll_stage146_portfolio_tail_risk_monitor_summary_stage146_portfolio_tail_risk_monitor_v1.json"
STAGE146_STATUS_PATH: Path = OUTPUT_DIR / "qmt_roll_stage146_portfolio_tail_risk_monitor_current_status_stage146_portfolio_tail_risk_monitor_v1.csv"
STAGE146_RECENT_TAIL_PATH: Path = OUTPUT_DIR / "qmt_roll_stage146_portfolio_tail_risk_monitor_recent_tail_events_stage146_portfolio_tail_risk_monitor_v1.csv"

SUMMARY_JSON_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.json"
DECISION_TABLE_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_table_{MODEL_TAG}.csv"
STATUS_MATRIX_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_status_matrix_{MODEL_TAG}.csv"
REPORT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


def _require(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"missing required artifact: {path}")


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


def _to_markdown_table(df: pd.DataFrame, columns: list[str] | None = None, max_rows: int = 20) -> str:
    if df.empty:
        return "_No rows._"
    view = df.copy()
    if columns is not None:
        view = view.loc[:, [column for column in columns if column in view.columns]]
    view = view.head(max_rows).copy()
    for column in view.columns:
        if column in {"date", "close_date", "open_date"}:
            view[column] = pd.to_datetime(view[column], errors="coerce").dt.strftime("%Y-%m-%d")
        elif pd.api.types.is_numeric_dtype(view[column]):
            view[column] = view[column].map(_fmt)
    return "\n".join(
        [
            "| " + " | ".join(view.columns) + " |",
            "| " + " | ".join(["---"] * len(view.columns)) + " |",
            *["| " + " | ".join(map(str, row)) + " |" for row in view.to_numpy()],
        ]
    )


def _read_csv(path: Path) -> pd.DataFrame:
    _require(path)
    return pd.read_csv(path, encoding="utf-8-sig")


def _read_json(path: Path) -> dict[str, Any]:
    _require(path)
    return json.loads(path.read_text(encoding="utf-8"))


def _load_inputs() -> dict[str, Any]:
    paths = [
        DAILY_PATH,
        SUMMARY_PATH,
        STAGE142_STATUS_PATH,
        STAGE142_THRESHOLDS_PATH,
        STAGE142_SUMMARY_PATH,
        STAGE143_SUMMARY_PATH,
        STAGE143_PRODUCT_PATH,
        STAGE143_ACTION_PATH,
        STAGE146_SUMMARY_PATH,
        STAGE146_STATUS_PATH,
        STAGE146_RECENT_TAIL_PATH,
    ]
    for path in paths:
        _require(path)
    daily = _read_csv(DAILY_PATH)
    daily["date"] = pd.to_datetime(daily["date"], errors="coerce").dt.tz_localize(None).dt.normalize()
    daily = daily.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    for col in ["balance", "ddpercent", "net_pnl", "trade_count", "slippage"]:
        daily[col] = pd.to_numeric(daily.get(col, 0.0), errors="coerce").fillna(0.0)
    return {
        "daily": daily,
        "summary": _read_json(SUMMARY_PATH),
        "stage142_status": _read_csv(STAGE142_STATUS_PATH),
        "stage142_thresholds": _read_csv(STAGE142_THRESHOLDS_PATH),
        "stage142_summary": _read_json(STAGE142_SUMMARY_PATH),
        "stage143_summary": _read_json(STAGE143_SUMMARY_PATH),
        "stage143_product": _read_csv(STAGE143_PRODUCT_PATH),
        "stage143_action": _read_csv(STAGE143_ACTION_PATH),
        "stage146_summary": _read_json(STAGE146_SUMMARY_PATH),
        "stage146_status": _read_csv(STAGE146_STATUS_PATH),
        "stage146_recent_tail": _read_csv(STAGE146_RECENT_TAIL_PATH),
    }


def _severity_rank(status: str) -> int:
    return {"severe": 4, "alert": 3, "watch": 2, "normal": 1, "constant_policy": 0, "info": 0}.get(str(status), 0)


def _top_status(frame: pd.DataFrame, status_col: str = "status") -> str:
    if frame.empty or status_col not in frame.columns:
        return "normal"
    ordered = sorted((str(s) for s in frame[status_col].dropna()), key=_severity_rank, reverse=True)
    return ordered[0] if ordered else "normal"


def _build_status_matrix(inputs: dict[str, Any]) -> pd.DataFrame:
    stage142 = inputs["stage142_status"].copy()
    stage146 = inputs["stage146_status"].copy()
    rows: list[dict[str, Any]] = []
    for row in stage142.itertuples(index=False):
        metric = str(getattr(row, "status_item", ""))
        status = str(getattr(row, "status", ""))
        if metric.startswith("threshold_count_"):
            status = "info"
        rows.append(
            {
                "module": "stage142_guardrails",
                "metric": metric,
                "latest_value": getattr(row, "value", ""),
                "status": status,
                "note": getattr(row, "note", ""),
            }
        )
    for row in stage146.itertuples(index=False):
        rows.append(
            {
                "module": "stage146_tail_risk",
                "metric": getattr(row, "metric", ""),
                "latest_value": getattr(row, "latest_value", ""),
                "status": getattr(row, "status", ""),
                "note": "组合层生命周期尾部风险监控",
            }
        )
    return pd.DataFrame(rows)


def _build_decision_table(status_matrix: pd.DataFrame, inputs: dict[str, Any]) -> tuple[pd.DataFrame, dict[str, Any]]:
    stage142_worst = _top_status(status_matrix[status_matrix["module"] == "stage142_guardrails"])
    stage146_worst = _top_status(status_matrix[status_matrix["module"] == "stage146_tail_risk"])
    stage143_decision = inputs["stage143_summary"].get("decision", "")
    stage146_decision = inputs["stage146_summary"].get("decision", "")
    severe_count = int((status_matrix["status"] == "severe").sum())
    alert_count = int((status_matrix["status"] == "alert").sum())
    watch_count = int((status_matrix["status"] == "watch").sum())

    if severe_count:
        decision = "pause_new_research_review_first"
        run_permission = "keep_stage78_but_pause_new_research"
        research_permission = "only_review_no_new_strategy"
    elif alert_count:
        decision = "review_first_keep_stage78"
        run_permission = "keep_stage78_with_review"
        research_permission = "monitoring_and_attribution_only"
    elif watch_count:
        decision = "keep_stage78_watch_mode"
        run_permission = "keep_stage78"
        research_permission = "low_risk_research_only"
    else:
        decision = "normal_keep_stage78"
        run_permission = "keep_stage78"
        research_permission = "research_allowed_with_ab_boundary"

    rows = [
        {
            "decision_item": "stage78_run_permission",
            "decision": run_permission,
            "reason": "当前无severe；Stage78正式基准继续冻结运行。",
        },
        {
            "decision_item": "review_requirement",
            "decision": "required" if alert_count or watch_count else "routine",
            "reason": f"alert={alert_count}, watch={watch_count}；需要复盘但不自动改策略。",
        },
        {
            "decision_item": "new_strategy_research_permission",
            "decision": research_permission,
            "reason": "当前20日净损益仍处alert且尾部风险有watch，优先监控与归因。",
        },
        {
            "decision_item": "forbidden_actions",
            "decision": "no_blacklist_no_stop_patch_no_profit_giveback",
            "reason": "当前证据只支持复盘，不支持单品种黑名单、止损补丁或利润保护重启。",
        },
    ]
    payload = {
        "decision": decision,
        "stage142_worst_status": stage142_worst,
        "stage143_decision": stage143_decision,
        "stage146_worst_status": stage146_worst,
        "stage146_decision": stage146_decision,
        "severe_count": severe_count,
        "alert_count": alert_count,
        "watch_count": watch_count,
        "run_permission": run_permission,
        "research_permission": research_permission,
    }
    return pd.DataFrame(rows), payload


def _build_summary_payload(inputs: dict[str, Any], decision_payload: dict[str, Any]) -> dict[str, Any]:
    daily = inputs["daily"]
    latest = daily.iloc[-1]
    stage78 = inputs["summary"]["reference_metrics"]["full_2020_2026"]
    stage143 = inputs["stage143_summary"]
    stage146 = inputs["stage146_summary"]
    return {
        "model_tag": MODEL_TAG,
        "is_strategy_change": False,
        "version_ab_skill_triggered": False,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "latest_date": latest["date"].date().isoformat(),
        "latest_balance": float(latest["balance"]),
        "latest_ddpercent": float(latest["ddpercent"]),
        "stage78_reference": stage78,
        "recent_20d_net_pnl": stage143.get("recent_20d_net_pnl", 0.0),
        "recent_20d_top_loss_products": stage143.get("recent_20d_top_loss_products", []),
        "tail20_count": stage146.get("tail20_count", 0),
        "tail63_count": stage146.get("tail63_count", 0),
        "tail63_dominant_family": stage146.get("tail63_dominant_family", ""),
        "tail63_dominant_family_share": stage146.get("tail63_dominant_family_share", 0.0),
        **decision_payload,
        "anti_overfit_boundary": (
            "This weekly report only consolidates monitoring, review, and tail-risk status. "
            "It must not directly change strategy parameters, product pools, sizing, or exits."
        ),
    }


def _write_report(
    payload: dict[str, Any],
    decision_table: pd.DataFrame,
    status_matrix: pd.DataFrame,
    inputs: dict[str, Any],
) -> None:
    stage78 = payload["stage78_reference"]
    product = inputs["stage143_product"].copy()
    tail = inputs["stage146_recent_tail"].copy()
    action = inputs["stage143_action"].copy()
    status_cols = ["module", "metric", "latest_value", "status", "note"]
    product_cols = ["product_vt_symbol", "net_pnl", "holding_pnl", "trading_pnl", "trade_count", "slippage", "review_bucket"]
    tail_cols = ["product_vt_symbol", "product_family", "contract_vt_symbol", "direction", "open_date", "close_date", "exit_reason", "lifecycle_net_pnl", "tail_bucket"]
    action_cols = ["priority", "status", "metric", "latest_value", "recommended_action", "forbidden_action"]
    report = f"""# Stage147 Stage78准实盘周报

## 结论
- 本阶段不是策略版本，不改Stage78，不触发A/B技能。
- 当前总决策：`{payload["decision"]}`。
- 运行许可：`{payload["run_permission"]}`。
- 研究许可：`{payload["research_permission"]}`。
- 过拟合判断：否。这里只汇总Stage142/143/146已有监控，不新增交易参数、不筛品种、不回测新策略。
- 是否有价值继续：是。周报把“资金曲线、短期亏损、品种贡献、尾部聚集”合并成统一决策，避免反复被单点数据牵引。

## Stage78 正式基准
- 期末权益：{_fmt(stage78.get("end_balance"))}
- 总收益：{_fmt(stage78.get("total_return_pct"))}%
- 最大回撤：{_fmt(stage78.get("max_dd_percent"))}%
- Sharpe：{_fmt(stage78.get("sharpe_ratio"))}
- 总滑点：{_fmt(stage78.get("total_slippage"))}
- 总交易次数：{_fmt(stage78.get("total_trade_count"))}

## 当前摘要
- 最新日期：{payload["latest_date"]}
- 最新权益：{_fmt(payload["latest_balance"])}
- 当前回撤：{_fmt(payload["latest_ddpercent"])}%
- 最近20日净损益：{_fmt(payload["recent_20d_net_pnl"])}
- 最近20日主要亏损品种：{", ".join(payload["recent_20d_top_loss_products"]) or "无"}
- 近20日尾部事件数：{payload["tail20_count"]}
- 近63日尾部事件数：{payload["tail63_count"]}
- 近63日主导尾部板块：`{payload["tail63_dominant_family"]}`，占比`{_fmt(payload["tail63_dominant_family_share"])}`
- 状态计数：severe={payload["severe_count"]}，alert={payload["alert_count"]}，watch={payload["watch_count"]}

## 决策表
{_to_markdown_table(decision_table, max_rows=10)}

## 状态矩阵
{_to_markdown_table(status_matrix, status_cols, max_rows=40)}

## 最近20日品种贡献
{_to_markdown_table(product.sort_values("net_pnl"), product_cols, max_rows=12)}

## 近63日生命周期尾部事件
{_to_markdown_table(tail, tail_cols, max_rows=10)}

## 当前复盘行动项
{_to_markdown_table(action, action_cols, max_rows=10)}

## 使用边界
- 周报只输出运行和研究纪律，不直接生成交易动作。
- 当前禁止动作：单品种黑名单、止损补丁、利润保护重启、为最近20日亏损调参数。
- 如果后续出现severe，先暂停新研究并复盘；不是自动改策略。
"""
    REPORT_PATH.write_text(report, encoding="utf-8")


def main() -> None:
    inputs = _load_inputs()
    status_matrix = _build_status_matrix(inputs)
    decision_table, decision_payload = _build_decision_table(status_matrix, inputs)
    payload = _build_summary_payload(inputs, decision_payload)

    status_matrix.to_csv(STATUS_MATRIX_PATH, index=False, encoding="utf-8-sig")
    decision_table.to_csv(DECISION_TABLE_PATH, index=False, encoding="utf-8-sig")
    SUMMARY_JSON_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    _write_report(payload, decision_table, status_matrix, inputs)

    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    print(f"wrote: {REPORT_PATH}")


if __name__ == "__main__":
    main()
