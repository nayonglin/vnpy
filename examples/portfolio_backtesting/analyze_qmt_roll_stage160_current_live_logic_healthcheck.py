from __future__ import annotations

import ast
from datetime import datetime
import json
from pathlib import Path
from typing import Any

import pandas as pd

import analyze_qmt_roll_stage650_stage526_200k_capital_reality_check as s650
import analyze_qmt_roll_stage157_current_rebuild_c9_stop_retry_attribution as s157
from qmt_roll_official_live_config import (
    OFFICIAL_LIVE_AI_ELIGIBILITY_PATH,
    OFFICIAL_LIVE_ALIAS,
    OFFICIAL_LIVE_CAPITAL,
    OFFICIAL_LIVE_PROFILE_NAME,
    OFFICIAL_LIVE_SIGNAL_PLAN_PATH,
    OFFICIAL_LIVE_SUMMARY_PATH,
    OFFICIAL_LIVE_VERSION,
    build_official_live_strategy_overrides,
)


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

LINE_ID = "futures_trend_stage819_intraday_rules"
STAGE = "Stage160"
MODEL_TAG = "stage160_current_live_logic_healthcheck_v1"
OUTPUT_PREFIX = "qmt_roll_stage160_current_live_logic_healthcheck"

CHECKS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_checks_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

STRATEGY_PATH = PROJECT_DIR / "qmt_roll_portfolio_strategy.py"
STAGE830_PATH = PROJECT_DIR / "analyze_qmt_roll_stage830_stage827_c2_broker10_margin_cap.py"
STAGE847_PATH = PROJECT_DIR / "analyze_qmt_roll_stage847_stage830_c4_stop_retry_engine.py"
STAGE901_PATH = PROJECT_DIR / "analyze_qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow.py"

STAGE847_ENTRY_CANDIDATES_PATH = (
    OUTPUT_DIR
    / "qmt_roll_stage847_stage830_c4_stop_retry_engine_entry_candidates_"
    "stage847_stage830_c4_stop_retry_engine_v1.csv"
)
STAGE830_ENTRY_CANDIDATES_PATH = (
    OUTPUT_DIR
    / "qmt_roll_stage830_stage827_c2_broker10_margin_cap_entry_candidates_"
    "stage830_stage827_c2_broker10_margin_cap_v1.csv"
)
STAGE901_ENTRY_CANDIDATES_PATH = (
    OUTPUT_DIR
    / "qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow_entry_candidates_"
    "stage901_stage847_c9_2026_ytd_live_shadow_v1.csv"
)
STAGE847_TRADE_EVENTS_PATH = (
    OUTPUT_DIR
    / "qmt_roll_stage847_stage830_c4_stop_retry_engine_trade_events_"
    "stage847_stage830_c4_stop_retry_engine_v1.csv"
)
STAGE830_TRADE_EVENTS_PATH = (
    OUTPUT_DIR
    / "qmt_roll_stage830_stage827_c2_broker10_margin_cap_trade_events_"
    "stage830_stage827_c2_broker10_margin_cap_v1.csv"
)
STAGE901_TRADE_EVENTS_PATH = (
    OUTPUT_DIR
    / "qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow_trade_events_"
    "stage901_stage847_c9_2026_ytd_live_shadow_v1.csv"
)


def _json_safe(value: Any) -> Any:
    return s650._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s650._md_table(frame, max_rows=max_rows)


def _check_rows() -> list[dict[str, Any]]:
    return []


def _add(
    rows: list[dict[str, Any]],
    *,
    check_id: str,
    status: str,
    severity: str,
    evidence: str,
    detail: str,
) -> None:
    rows.append(
        {
            "stage": STAGE,
            "line_id": LINE_ID,
            "model_tag": MODEL_TAG,
            "check_id": check_id,
            "status": status,
            "severity": severity,
            "evidence": evidence,
            "detail": detail,
        }
    )


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _value_counts(path: Path, column: str) -> dict[str, int]:
    if not path.exists() or path.stat().st_size <= 4:
        return {}
    frame = pd.read_csv(path, encoding="utf-8-sig")
    if column not in frame.columns:
        return {}
    return {str(key): int(value) for key, value in frame[column].astype(str).value_counts(dropna=False).items()}


def _reverse_hit_count(path: Path) -> int:
    if not path.exists() or path.stat().st_size <= 4:
        return 0
    frame = pd.read_csv(path, encoding="utf-8-sig")
    hits = 0
    for column in frame.columns:
        series = frame[column].astype(str)
        hits += int(series.str.contains("reverse", case=False, na=False).sum())
    return hits


def _stop_retry_sequence_audit(path: Path) -> dict[str, Any]:
    if not path.exists() or path.stat().st_size <= 4:
        return {
            "event_count": 0,
            "synthetic_trades_column": False,
            "parse_fail_count": 0,
            "state_anomaly_count": 0,
            "max_retries_values": [],
            "final_state_counts": {},
        }
    frame = pd.read_csv(path, encoding="utf-8-sig")
    state_anomalies = 0
    for row in frame.itertuples(index=False):
        final_state = str(getattr(row, "final_state", ""))
        first_stop_idx = int(getattr(row, "first_stop_bar_index", -1))
        reentry_idx = int(getattr(row, "reentry_bar_index", -1))
        retry_failed_idx = int(getattr(row, "retry_failed_bar_index", -1))
        retry_reentered = int(getattr(row, "retry_reentered", 0))
        retry_failed = int(getattr(row, "retry_failed", 0))
        if first_stop_idx < 0:
            state_anomalies += 1
        if final_state == "flat_no_reentry" and (retry_reentered != 0 or retry_failed != 0 or reentry_idx >= 0):
            state_anomalies += 1
        if final_state == "open_after_reentry" and (
            retry_reentered != 1 or retry_failed != 0 or reentry_idx <= first_stop_idx or retry_failed_idx >= 0
        ):
            state_anomalies += 1
        if final_state == "flat_retry_failed" and (
            retry_reentered != 1 or retry_failed != 1 or reentry_idx <= first_stop_idx or retry_failed_idx <= reentry_idx
        ):
            state_anomalies += 1
    if "synthetic_trades" not in frame.columns:
        return {
            "event_count": int(len(frame)),
            "synthetic_trades_column": False,
            "parse_fail_count": 0,
            "state_anomaly_count": int(state_anomalies),
            "max_retries_values": sorted(str(item) for item in frame.get("max_retries", pd.Series(dtype=object)).dropna().unique()),
            "final_state_counts": {
                str(key): int(value)
                for key, value in frame.get("final_state", pd.Series(dtype=object)).astype(str).value_counts().items()
            },
        }
    parse_fail = 0
    sequence_anomalies = 0
    for row in frame.itertuples(index=False):
        raw = getattr(row, "synthetic_trades", "")
        try:
            sequence = ast.literal_eval(str(raw))
        except (SyntaxError, ValueError):
            parse_fail += 1
            continue
        if not isinstance(sequence, list) or not sequence:
            sequence_anomalies += 1
            continue
        actions = [str(item.get("action") or "") for item in sequence if isinstance(item, dict)]
        final_state = str(getattr(row, "final_state", ""))
        if actions[0] != "close":
            sequence_anomalies += 1
        if final_state == "open_after_reentry" and actions != ["close", "open"]:
            sequence_anomalies += 1
        if final_state == "flat_retry_failed" and actions != ["close", "open", "close"]:
            sequence_anomalies += 1
        if final_state == "flat_no_reentry" and actions != ["close"]:
            sequence_anomalies += 1
    return {
        "event_count": int(len(frame)),
        "synthetic_trades_column": True,
        "parse_fail_count": int(parse_fail),
        "state_anomaly_count": int(state_anomalies + sequence_anomalies),
        "max_retries_values": sorted(str(item) for item in frame.get("max_retries", pd.Series(dtype=object)).dropna().unique()),
        "final_state_counts": {
            str(key): int(value)
            for key, value in frame.get("final_state", pd.Series(dtype=object)).astype(str).value_counts().items()
        },
    }


def _ai_pool_audit(path: Path, strategy: str) -> dict[str, Any]:
    if not path.exists() or path.stat().st_size <= 4:
        return {"exists": False, "rows": 0, "strategy_rows": 0}
    frame = pd.read_csv(path, encoding="utf-8-sig")
    result: dict[str, Any] = {
        "exists": True,
        "rows": int(len(frame)),
        "columns": list(frame.columns),
        "strategy_rows": 0,
    }
    if {"strategy", "eval_date", "product_vt_symbol"}.issubset(frame.columns):
        temp = frame[frame["strategy"].astype(str).eq(str(strategy))].copy()
        result["strategy_rows"] = int(len(temp))
        if not temp.empty:
            temp["eval_date"] = pd.to_datetime(temp["eval_date"], errors="coerce")
            result["eval_date_min"] = temp["eval_date"].min().date().isoformat()
            result["eval_date_max"] = temp["eval_date"].max().date().isoformat()
            result["unique_eval_dates"] = int(temp["eval_date"].nunique())
            result["unique_products"] = int(temp["product_vt_symbol"].astype(str).nunique())
    return result


def main() -> None:
    rows = _check_rows()
    overrides = build_official_live_strategy_overrides()
    strategy_name = str(overrides.get("ai_product_pool_strategy", ""))
    ai_audit = _ai_pool_audit(OFFICIAL_LIVE_AI_ELIGIBILITY_PATH, strategy_name)

    _add(
        rows,
        check_id="live_identity",
        status="PASS" if OFFICIAL_LIVE_VERSION.endswith("15w_stage819_05r_stop_retry_once") else "FAIL",
        severity="P0",
        evidence=f"{OFFICIAL_LIVE_VERSION} / {OFFICIAL_LIVE_ALIAS} / {OFFICIAL_LIVE_PROFILE_NAME}",
        detail="当前 live config 指向 C9 15w，而不是 Stage372、Stage78 或 30w previous profile。",
    )
    _add(
        rows,
        check_id="live_capital",
        status="PASS" if float(overrides.get("account_capital", 0.0)) == 150_000.0 and float(overrides.get("c3_capital", 0.0)) == 150_000.0 else "FAIL",
        severity="P0",
        evidence=f"override account_capital={overrides.get('account_capital')} c3_capital={overrides.get('c3_capital')}",
        detail=f"OFFICIAL_LIVE_CAPITAL={OFFICIAL_LIVE_CAPITAL}，策略 override 与 live 资金口径一致。",
    )
    _add(
        rows,
        check_id="live_flags",
        status=(
            "PASS"
            if bool(overrides.get("enable_stage830_broker10_margin_cap"))
            and bool(overrides.get("enable_stage847_half_r_stop_retry"))
            and float(overrides.get("stage847_stop_retry_r", 0.0)) == 0.5
            and int(overrides.get("stage847_max_retries", -1)) == 1
            and bool(overrides.get("enable_ai_product_pool_filter"))
            else "FAIL"
        ),
        severity="P0",
        evidence=json.dumps(
            {
                key: overrides.get(key)
                for key in [
                    "enable_stage830_broker10_margin_cap",
                    "enable_stage847_half_r_stop_retry",
                    "stage847_stop_retry_r",
                    "stage847_max_retries",
                    "enable_ai_product_pool_filter",
                    "ai_product_pool_strategy",
                ]
            },
            ensure_ascii=False,
        ),
        detail="C9 核心开关、0.5R、重试一次、AI 过滤都在 live override 中开启。",
    )
    _add(
        rows,
        check_id="ai_pool_file",
        status="PASS" if ai_audit.get("exists") and int(ai_audit.get("strategy_rows", 0)) > 0 else "FAIL",
        severity="P0",
        evidence=json.dumps(ai_audit, ensure_ascii=False),
        detail="AI 池文件存在且当前策略名有行；若该文件被删或策略名错，会退化为无 AI 行但策略代码 fail-open。",
    )

    strategy_source = _read_text(STRATEGY_PATH)
    _add(
        rows,
        check_id="ai_pit_left_searchsorted",
        status="PASS" if 'searchsorted(normalized_date, side="left") - 1' in strategy_source else "FAIL",
        severity="P0",
        evidence="qmt_roll_portfolio_strategy.py::_ai_product_pool_snapshot",
        detail="AI PIT 语义为 eval_date 当天仍使用上一期 snapshot，避免用当日刚生成池子回看泄漏。",
    )
    _add(
        rows,
        check_id="ai_next_trade_date_default",
        status="PASS" if "ai_product_pool_use_next_trade_date_for_entry" in strategy_source else "FAIL",
        severity="P1",
        evidence=f"override={overrides.get('ai_product_pool_use_next_trade_date_for_entry', '<missing-default-false>')}",
        detail="live override 未显式设置 next-trade-date；基础默认 False，但 exact eval_date 仍因 side='left' 使用上一期。",
    )

    stage830_source = _read_text(STAGE830_PATH)
    cap_scope_is_flat_only = 'if entry_context != "flat_entry":' in stage830_source
    reverse_fail_closed = (
        'entry_context == "reverse_entry"' in stage830_source
        and '"stage830_broker10_margin_cap_reason"] = "reverse_entry_fail_closed"' in stage830_source
        and 'sizing["selected_volume"] = 0' in stage830_source
    )
    reverse_context_counts = {
        "stage847": _value_counts(STAGE847_ENTRY_CANDIDATES_PATH, "entry_context"),
        "stage830": _value_counts(STAGE830_ENTRY_CANDIDATES_PATH, "entry_context"),
        "stage901": _value_counts(STAGE901_ENTRY_CANDIDATES_PATH, "entry_context"),
    }
    reverse_event_hits = {
        "stage847_trade_events": _reverse_hit_count(STAGE847_TRADE_EVENTS_PATH),
        "stage830_trade_events": _reverse_hit_count(STAGE830_TRADE_EVENTS_PATH),
        "stage901_trade_events": _reverse_hit_count(STAGE901_TRADE_EVENTS_PATH),
    }
    _add(
        rows,
        check_id="broker10_cap_reverse_entry_guard",
        status="PASS" if cap_scope_is_flat_only and reverse_fail_closed else ("WARN" if cap_scope_is_flat_only else "FAIL"),
        severity="P2",
        evidence=json.dumps(
            {
                "source_flat_only": cap_scope_is_flat_only,
                "reverse_fail_closed": reverse_fail_closed,
                "entry_context_counts": reverse_context_counts,
                "reverse_event_hits": reverse_event_hits,
            },
            ensure_ascii=False,
        ),
        detail=(
            "Stage830 broker10 cap 对 flat_entry 继续做 100% projected broker10 降手数；"
            "reverse_entry 不复用 flat-entry 公式，而是 fail-closed 为只平旧仓、不直接反手新开。"
        ),
    )

    stop_retry_audit = _stop_retry_sequence_audit(s157.STOP_RETRY_EVENTS_PATH)
    _add(
        rows,
        check_id="c9_stop_retry_event_sequences",
        status=(
            "PASS"
            if stop_retry_audit["event_count"] > 0
            and stop_retry_audit["parse_fail_count"] == 0
            and stop_retry_audit["state_anomaly_count"] == 0
            and stop_retry_audit["max_retries_values"] == ["1"]
            else "FAIL"
        ),
        severity="P0",
        evidence=json.dumps(stop_retry_audit, ensure_ascii=False),
        detail=(
            "Stage157 stop/retry 事件状态字段与 close/open/close 状态机一致，且 max_retries 固定为 1；"
            "当前输出没有 synthetic_trades 列，无法逐条重建合成成交序列。"
        ),
    )
    stage847_source = _read_text(STAGE847_PATH)
    c9_uses_event_datetime = (
        "trade_datetime = _stage847_synthetic_trade_datetime" in stage847_source
        and "datetime=trade_datetime" in stage847_source
        and "_naive_date(trade_datetime)" in stage847_source
    )
    c9_uses_legacy_datetime = "datetime=self.datetime" in stage847_source and "proxy_first_time" in stage847_source
    _add(
        rows,
        check_id="c9_synthetic_trade_datetime_semantics",
        status="PASS" if c9_uses_event_datetime and not c9_uses_legacy_datetime else ("WARN" if c9_uses_legacy_datetime else "FAIL"),
        severity="P2",
        evidence=json.dumps(
            {
                "uses_event_datetime": c9_uses_event_datetime,
                "uses_legacy_datetime": c9_uses_legacy_datetime,
            },
            ensure_ascii=False,
        ),
        detail=(
            "Stage847/C9 合成成交价格与顺序可审计，且 TradeData datetime/fill_date 使用对应分钟触发时间；"
            "这修正 TCA/实盘对齐语义，不改变价格、手数或 stop/retry 状态机。"
        ),
    )

    stage901_source = _read_text(STAGE901_PATH)
    stage901_direct_s660_patch = "s660.OFFICIAL_LIVE_PROFILE_NAME" in stage901_source or "setattr(s660" in stage901_source
    stage847_pins_legacy_base = (
        "_stage847_stage372_legacy_official_context" in stage847_source
        and "LEGACY_STAGE372_PROFILE_NAME" in stage847_source
        and "with _stage847_stage372_legacy_official_context():" in stage847_source
    )
    _add(
        rows,
        check_id="stage901_global_state_restore",
        status="PASS" if stage847_pins_legacy_base and not stage901_direct_s660_patch else ("WARN" if stage901_direct_s660_patch else "FAIL"),
        severity="P2",
        evidence=json.dumps(
            {
                "stage847_pins_legacy_base": stage847_pins_legacy_base,
                "stage901_direct_s660_patch": stage901_direct_s660_patch,
            },
            ensure_ascii=False,
        ),
        detail=(
            "Stage901 不再直接改 Stage660 live 全局；Stage847 profile 构造显式固定历史 Stage372/Stage819 base，"
            "避免当前 live profile 切换后导致独立回测入口找不到 base spec。"
        ),
    )

    decision = {}
    if OFFICIAL_LIVE_SUMMARY_PATH.exists() and OFFICIAL_LIVE_SUMMARY_PATH.stat().st_size > 4:
        decision = json.loads(OFFICIAL_LIVE_SUMMARY_PATH.read_text(encoding="utf-8"))
    order_api_clean = (
        decision.get("order_api_called") is False
        and int(decision.get("send_order_api_called_count", -1)) == 0
        and int(decision.get("cancel_order_api_called_count", -1)) == 0
    )
    _add(
        rows,
        check_id="stage901_no_order_api",
        status="PASS" if order_api_clean else "FAIL",
        severity="P0",
        evidence=json.dumps(
            {
                "decision_path": str(OFFICIAL_LIVE_SUMMARY_PATH),
                "signal_plan_path": str(OFFICIAL_LIVE_SIGNAL_PLAN_PATH),
                "order_api_called": decision.get("order_api_called"),
                "send_order_api_called_count": decision.get("send_order_api_called_count"),
                "cancel_order_api_called_count": decision.get("cancel_order_api_called_count"),
                "target_signal_count": decision.get("target_signal_count"),
                "pending_order_count": decision.get("pending_order_count"),
            },
            ensure_ascii=False,
        ),
        detail="最新 Stage901 影子输出声明未调用订单 API；pending_orders 仍需作为信号来源一起检查，不能只看 signal_plan。",
    )

    checks = pd.DataFrame(rows)
    status_counts = {str(key): int(value) for key, value in checks["status"].value_counts().items()}
    fail_count = int(checks["status"].eq("FAIL").sum())
    warn_count = int(checks["status"].eq("WARN").sum())
    decision_payload = {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "check_count": int(len(checks)),
        "status_counts": status_counts,
        "fail_count": fail_count,
        "warn_count": warn_count,
        "decision": "stage160_fail_found_requires_fix" if fail_count else "stage160_no_p0_p1_logic_bug_found_with_p2_warnings",
        "order_api_called": False,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "ctp_connected": False,
        "external_research_judgment": "Skipped external search per operator constraint; local source/output healthcheck only.",
        "overfit_reflection_before": "否。该阶段检查代码语义和执行输出，不改策略参数。",
        "continue_value_before": "是。Stage159 已反证简单权益代理，继续价值在找真实执行差错风险。",
        "overfit_reflection_after": "否。输出为 bug/warn 清单，不产生 alpha 参数或过滤规则。",
        "continue_value_after": (
            "是。若只剩 P2 工程警告，下一步应补 manifest/healthcheck gate 或订单级 targeted test，而不是扫参。"
        ),
        "outputs": {
            "checks": str(CHECKS_PATH),
            "decision": str(DECISION_PATH),
            "report": str(REPORT_PATH),
        },
    }

    checks.to_csv(CHECKS_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision_payload), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# Stage160 当前 live 逻辑 healthcheck",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        f"- line_id：`{LINE_ID}`",
        "- 性质：只读源码/输出审计；不重跑策略、不连接 CTP、不调用订单 API。",
        "",
        "## Checks",
        "",
        _md_table(checks, max_rows=80),
        "",
        "## Decision",
        "",
        f"- 决策：`{decision_payload['decision']}`",
        f"- 状态统计：`{status_counts}`",
        f"- 过拟合反思：{decision_payload['overfit_reflection_after']}",
        f"- 继续价值反思：{decision_payload['continue_value_after']}",
        "",
        "## Outputs",
        "",
        f"- checks: `{CHECKS_PATH}`",
        f"- decision: `{DECISION_PATH}`",
        f"- report: `{REPORT_PATH}`",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision_payload), ensure_ascii=False, indent=2))
    print(checks.to_string(index=False))


if __name__ == "__main__":
    main()
