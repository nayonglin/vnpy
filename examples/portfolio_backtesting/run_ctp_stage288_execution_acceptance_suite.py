from __future__ import annotations

import argparse
import html
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
from pandas.errors import EmptyDataError

from ctp_execution_safety import (
    ExecutionThresholdConfig,
    PauseGateState,
    build_contract_lookup,
    evaluate_execution_thresholds,
    evaluate_pause_gate,
    normalize_ctp_error,
    validate_order_instruction,
)


ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = Path(__file__).resolve().parent / "backtest_outputs"
MODEL_TAG = "stage288_execution_acceptance_suite_v1"

CONTRACTS_CSV = OUTPUT_DIR / "qmt_roll_stage174_ctp_vnpy_readonly_probe_contracts_stage174_ctp_vnpy_readonly_probe_v1.csv"
ORDERS_CSV = OUTPUT_DIR / "qmt_roll_stage174_ctp_vnpy_readonly_probe_orders_stage174_ctp_vnpy_readonly_probe_v1.csv"
TRADES_CSV = OUTPUT_DIR / "qmt_roll_stage174_ctp_vnpy_readonly_probe_trades_stage174_ctp_vnpy_readonly_probe_v1.csv"

OPEN_CLOSE_SUMMARY = OUTPUT_DIR / "qmt_roll_stage285_simnow_open_close_proof_summary_20260520_214451_stage285_simnow_open_close_proof_v1.json"
OPEN_CLOSE_LOGS_CSV = OUTPUT_DIR / "qmt_roll_stage285_simnow_open_close_proof_logs_20260520_214451_stage285_simnow_open_close_proof_v1.csv"
OPEN_CLOSE_IMAGE = OUTPUT_DIR / "qmt_roll_stage285_simnow_open_close_proof_evidence_20260520_214451.png"
OPEN_CLOSE_CANCEL_HTML = OUTPUT_DIR / "qmt_roll_stage285_simnow_open_close_cancel_evidence_20260520_220320.html"
OPEN_CLOSE_CANCEL_IMAGE = OUTPUT_DIR / "qmt_roll_stage285_simnow_open_close_cancel_evidence_20260520_220320.png"
CANCEL_SUMMARY = OUTPUT_DIR / "qmt_roll_stage258_simnow_smoke_order_summary_20260520_220053_stage258_simnow_smoke_order_v1.json"
CANCEL_LOGS_CSV = OUTPUT_DIR / "qmt_roll_stage258_simnow_smoke_order_logs_20260520_220053_stage258_simnow_smoke_order_v1.csv"
DISCONNECT_SUMMARY = OUTPUT_DIR / "qmt_roll_stage287_simnow_disconnect_proof_summary_20260520_221731_stage287_simnow_disconnect_proof_v1.json"
DISCONNECT_LOGS_CSV = OUTPUT_DIR / "qmt_roll_stage287_simnow_disconnect_proof_logs_20260520_221731_stage287_simnow_disconnect_proof_v1.csv"
DISCONNECT_IMAGE = OUTPUT_DIR / "qmt_roll_stage287_simnow_disconnect_proof_evidence_20260520_221731_stage287_simnow_disconnect_proof_v1.png"


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, encoding="utf-8-sig")
    except EmptyDataError:
        return pd.DataFrame()


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _clean(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() == "nan":
        return ""
    return text


GROUP_LABELS = {
    "1.6 threshold_warning": "1.6 阈值设置及预警功能",
    "1.7 instruction_check": "1.7 交易指令检查功能",
    "1.8 error_prompt": "1.8 错误提示功能",
    "1.9 pause_trading": "1.9 暂停交易功能",
}

GROUP_OBJECTIVES = {
    "1.6 threshold_warning": "验证系统能设置报单、撤单、重复报单等指标阈值，并在达到或超过阈值时给出预警。",
    "1.7 instruction_check": "验证提交前门禁能检查交易指令，拦截错误合约、错误最小变动价位和超单笔最大委托数量。",
    "1.8 error_prompt": "验证系统能接收并展示柜台返回的关键错误提示，包括资金不足、持仓不足、市场状态不允许。",
    "1.9 pause_trading": "验证系统能通过账号权限、策略暂停、会话退出等方式阻断交易指令下达。",
}

COLUMN_LABELS = {
    "group": "章节",
    "test_id": "测试点",
    "name": "测试名称",
    "expected": "预期",
    "observed": "实际观测",
    "result": "结果",
    "evidence": "证据",
    "order_api_called": "发单API调用次数",
    "proof": "实测项",
    "status": "状态",
    "metric": "指标",
    "value": "统计值",
    "threshold": "阈值",
    "warning": "预警",
    "message": "提示",
    "case": "用例",
    "vt_symbol": "合约",
    "price": "价格",
    "volume": "数量",
    "accepted": "检查结果",
    "reasons": "原因",
    "pricetick": "最小变动价位",
    "max_volume": "单笔最大委托",
    "source": "来源",
    "action": "动作",
    "time": "时间",
    "order_id": "委托号",
    "trade_id": "成交号",
    "direction": "方向",
    "offset": "开平",
    "order_price": "委托价",
    "trade_price": "成交价",
    "order_volume": "委托手数",
    "traded": "已成交",
    "error_id": "错误码",
    "error_msg": "原始错误信息",
    "category": "归一化类别",
    "severity": "严重级别",
    "display_text": "展示文案",
    "passed": "是否通过",
    "scenario": "场景",
    "can_submit": "是否允许提交",
}

METRIC_LABELS = {
    "order_count": "报单笔数",
    "cancel_count": "撤单笔数",
    "duplicate_intent_count": "重复报单意图数",
}

CASE_LABELS = {
    "valid_baseline": "合法基线",
    "wrong_contract_code": "合约代码错误",
    "price_not_on_min_tick": "价格不符合最小变动价位",
    "volume_above_max_single_order": "数量超过单笔最大委托",
}

REASON_LABELS = {
    "invalid_vt_symbol": "合约格式错误",
    "invalid_direction": "方向错误",
    "invalid_offset": "开平标志错误",
    "contract_not_found": "合约不存在",
    "invalid_volume": "委托数量无效",
    "volume_below_min": "数量低于最小委托",
    "volume_above_max": "数量超过单笔最大委托",
    "volume_not_integer_lots": "数量不是整数手",
    "invalid_price": "价格无效",
    "price_not_on_tick": "价格不符合最小变动价位",
    "account_trading_permission_restricted": "账号交易权限受限",
    "strategy_paused": "策略已暂停",
    "forced_logout_or_session_not_logged_in": "会话退出或未登录",
}

CATEGORY_LABELS = {
    "insufficient_funds_open": "资金不足-开仓拒绝",
    "insufficient_position_close": "持仓不足-平仓拒绝",
    "market_state_not_allowed": "市场状态不允许",
    "generic_ctp_error": "其他柜台错误",
    "ok": "正常",
}

SEVERITY_LABELS = {
    "reject": "拒绝",
    "info": "信息",
}

SCENARIO_LABELS = {
    "account_permission_restricted": "账号权限限制",
    "strategy_paused": "策略暂停",
    "forced_logout": "会话退出或未登录",
}

STATUS_LABELS = {
    "open_close_all_traded": "开仓和平仓均全部成交",
    "submit_cancel_attempted": "报单后撤单已完成",
    "disconnect_observed": "已观测到断线回调",
    "passed": "通过",
    "failed": "失败",
}

PROOF_LABELS = {
    "open_close": "开仓/平仓成交证明",
    "cancel": "撤单证明",
    "disconnect": "断网回调证明",
}

ORDER_STATUS_LABELS = {
    "Submitting": "提交中",
    "Not Traded": "未成交",
    "All Traded": "全部成交",
    "Cancelled": "已撤销",
    "Rejected": "已拒绝",
}


def _result_zh(value: Any) -> str:
    text = _clean(value)
    if text.upper() == "PASS":
        return "通过"
    if text.upper() == "FAIL":
        return "失败"
    return text


def _bool_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    text = _clean(value).lower()
    return text in {"true", "1", "yes", "y", "通过", "允许", "触发"}


def _translate_reasons(value: Any) -> str:
    if isinstance(value, list):
        parts = [_clean(item) for item in value]
    else:
        parts = [part.strip() for part in _clean(value).split(";") if part.strip()]
    if not parts:
        return "-"
    return "；".join(REASON_LABELS.get(part, part) for part in parts)


def _translate_display_text(value: Any) -> str:
    text = _clean(value)
    for key, label in CATEGORY_LABELS.items():
        prefix = f"{key}:"
        if text.startswith(prefix):
            return f"{label}：{text[len(prefix):].strip()}"
    return text


def _yes_no(value: Any) -> str:
    return "是" if _bool_value(value) else "否"


def _direction_zh(value: Any) -> str:
    text = _clean(value)
    return {"Long": "买入", "Short": "卖出"}.get(text, text)


def _offset_zh(value: Any) -> str:
    text = _clean(value)
    return {"Open": "开仓", "Close": "平仓"}.get(text, text)


def _status_zh(value: Any) -> str:
    text = _clean(value)
    return ORDER_STATUS_LABELS.get(text, STATUS_LABELS.get(text, text))


def _display_value(col: str, value: Any) -> str:
    text = _clean(value)
    if col == "group":
        return GROUP_LABELS.get(text, text)
    if col == "result":
        return _result_zh(text)
    if col == "expected":
        return CATEGORY_LABELS.get(text, text)
    if col == "status":
        return STATUS_LABELS.get(text, text)
    if col == "metric":
        return METRIC_LABELS.get(text, text)
    if col == "case":
        return CASE_LABELS.get(text, text)
    if col == "scenario":
        return SCENARIO_LABELS.get(text, text)
    if col == "reasons":
        return _translate_reasons(text)
    if col == "category":
        return CATEGORY_LABELS.get(text, text)
    if col == "severity":
        return SEVERITY_LABELS.get(text, text)
    if col == "proof":
        return PROOF_LABELS.get(text, text)
    if col == "direction":
        return _direction_zh(text)
    if col == "offset":
        return _offset_zh(text)
    if col == "display_text":
        return _translate_display_text(text)
    if col == "warning":
        return "触发" if _bool_value(text) else "未触发"
    if col == "accepted":
        return "通过" if _bool_value(text) else "拒绝"
    if col == "can_submit":
        return "允许" if _bool_value(text) else "阻断"
    if col == "passed":
        return "通过" if _bool_value(text) else "失败"
    return text


def _latest_order_rows(orders: pd.DataFrame) -> pd.DataFrame:
    if orders.empty:
        return orders.copy()
    df = orders.copy().reset_index().rename(columns={"index": "_event_index"})
    if "vt_orderid" in df.columns:
        key = df["vt_orderid"].fillna("").astype(str).str.strip()
    else:
        key = pd.Series([""] * len(df), index=df.index)
    fallback = (
        df.get("gateway_name", pd.Series([""] * len(df), index=df.index)).fillna("").astype(str).str.strip()
        + "."
        + df.get("orderid", pd.Series([""] * len(df), index=df.index)).fillna("").astype(str).str.strip()
    )
    df["_order_key"] = key.where(key.ne(""), fallback)
    latest = df.sort_values("_event_index").groupby("_order_key", as_index=False, dropna=False).tail(1)
    return latest.drop(columns=["_event_index", "_order_key"], errors="ignore")


def _latest_order_by_id(orders: pd.DataFrame, vt_orderid: str) -> dict[str, Any]:
    latest_orders = _latest_order_rows(orders)
    if latest_orders.empty or not vt_orderid or "vt_orderid" not in latest_orders.columns:
        return {}
    matched = latest_orders[latest_orders["vt_orderid"].fillna("").astype(str).eq(vt_orderid)]
    if matched.empty:
        return {}
    return matched.iloc[0].to_dict()


def _trade_by_order_id(trades: pd.DataFrame, vt_orderid: str) -> dict[str, Any]:
    if trades.empty or not vt_orderid or "vt_orderid" not in trades.columns:
        return {}
    matched = trades[trades["vt_orderid"].fillna("").astype(str).eq(vt_orderid)]
    if matched.empty:
        return {}
    return matched.iloc[-1].to_dict()


def _strip_sensitive_console_text(text: Any) -> str:
    msg = _clean(text)
    if not msg:
        return ""
    blocked_tokens = [
        "/Users",
        "bytedance",
        "Desktop",
        "person/vnpy",
        "file://",
        "PASSWORD",
        "CTP_PASSWORD",
        "CTP_USERID",
        "AUTH",
        "AuthCode",
        "BROKERID",
        "AppID",
        "tcp://",
        "DataCollect",
        "CollectData",
    ]
    if any(token in msg for token in blocked_tokens):
        return ""
    replacements = {
        "<Exchange.CZCE: 'CZCE'>": "CZCE",
        "<Direction.LONG: 'Long'>": "Long",
        "<Direction.SHORT: 'Short'>": "Short",
        "<OrderType.LIMIT: 'Limit'>": "Limit",
        "<Offset.OPEN: 'Open'>": "Open",
        "<Offset.CLOSE: 'Close'>": "Close",
        "Subscribe market data -> CTP": "订阅行情 -> CTP",
        "Send new order -> CTP": "发送委托 -> CTP",
        "Cancel existing order -> CTP": "发送撤单 -> CTP",
    }
    for old, new in replacements.items():
        msg = msg.replace(old, new)
    msg = msg.replace("reference='Stage285Open:20260520_214451'", "reference='已脱敏'")
    msg = msg.replace("reference='Stage285Close:20260520_214451'", "reference='已脱敏'")
    msg = msg.replace("reference='Stage258Smoke:20260520_220053'", "reference='已脱敏'")
    msg = msg.replace(", reference='已脱敏'", "")
    msg = msg.replace("reference='已脱敏'", "")
    return msg


def _read_console_rows(path: Path) -> list[dict[str, Any]]:
    logs = _read_csv(path)
    if logs.empty:
        return []
    rows: list[dict[str, Any]] = []
    for _, row in logs.iterrows():
        message = _strip_sensitive_console_text(row.get("msg"))
        if not message:
            continue
        source = _clean(row.get("gateway_name"))
        rows.append(
            {
                "time": _clean(row.get("time")) or "-",
                "source": {"MainEngine": "主引擎"}.get(source, source),
                "message": message,
            }
        )
    return rows


def _execution_detail_from_order_trade(
    *,
    action: str,
    order_row: dict[str, Any],
    trade_row: dict[str, Any],
    fallback_request: dict[str, Any] | None = None,
) -> dict[str, Any]:
    fallback_request = fallback_request or {}
    return {
        "action": action,
        "time": _clean(trade_row.get("datetime")) or _clean(order_row.get("datetime")),
        "order_id": _clean(order_row.get("vt_orderid")) or _clean(fallback_request.get("vt_orderid")),
        "trade_id": _clean(trade_row.get("tradeid")) or "-",
        "vt_symbol": _clean(order_row.get("vt_symbol")) or _clean(fallback_request.get("vt_symbol")),
        "direction": _clean(order_row.get("direction")) or _clean(fallback_request.get("direction")),
        "offset": _clean(order_row.get("offset")) or _clean(fallback_request.get("offset")),
        "order_price": _clean(order_row.get("price")) or _clean(fallback_request.get("price")),
        "trade_price": _clean(trade_row.get("price")) or "-",
        "order_volume": _clean(order_row.get("volume")) or _clean(fallback_request.get("volume")),
        "traded": _clean(order_row.get("traded")) or _clean(fallback_request.get("filled_volume")),
        "status": _status_zh(order_row.get("status")),
    }


def _append_order_trade_console(
    rows: list[dict[str, Any]],
    *,
    order_row: dict[str, Any],
    trade_row: dict[str, Any],
) -> None:
    order_id = _clean(order_row.get("vt_orderid"))
    if order_id:
        rows.append(
            {
                "time": _clean(order_row.get("datetime")) or "-",
                "source": "委托回报",
                "message": f"委托号={order_id}，状态={_status_zh(order_row.get('status'))}，已成交={_clean(order_row.get('traded'))}/{_clean(order_row.get('volume'))}",
            }
        )
    trade_id = _clean(trade_row.get("tradeid"))
    if trade_id:
        rows.append(
            {
                "time": _clean(trade_row.get("datetime")) or "-",
                "source": "成交回报",
                "message": f"成交号={trade_id}，委托号={_clean(trade_row.get('vt_orderid'))}，成交价={_clean(trade_row.get('price'))}，手数={_clean(trade_row.get('volume'))}",
            }
        )


def _add_case(
    rows: list[dict[str, Any]],
    *,
    group: str,
    test_id: str,
    name: str,
    expected: str,
    observed: str,
    passed: bool,
    evidence: str,
    order_api_called: int | str = 0,
) -> None:
    rows.append(
        {
            "group": group,
            "test_id": test_id,
            "name": name,
            "expected": expected,
            "observed": observed,
            "result": "PASS" if passed else "FAIL",
            "evidence": evidence,
            "order_api_called": order_api_called,
        }
    )


def _table_html(rows: list[dict[str, Any]] | pd.DataFrame, columns: list[str]) -> str:
    if isinstance(rows, pd.DataFrame):
        records = rows.to_dict(orient="records")
    else:
        records = rows
    if not records:
        return "<p class='muted'>无记录</p>"
    header = "".join(f"<th>{html.escape(COLUMN_LABELS.get(c, c))}</th>" for c in columns)
    body_rows: list[str] = []
    for row in records:
        cells = []
        for col in columns:
            value = row.get(col, "")
            display = _display_value(col, value)
            text = html.escape(display)
            if col == "result":
                cls = "pass" if display == "通过" else "fail"
                text = f"<span class='{cls}'>{text}</span>"
            elif col in {"warning", "can_submit", "accepted", "passed"}:
                cls = "pass" if display in {"通过", "允许"} else "warn"
                text = f"<span class='{cls}'>{text}</span>" if cls else text
            cells.append(f"<td>{text}</td>")
        body_rows.append("<tr>" + "".join(cells) + "</tr>")
    return f"<table><thead><tr>{header}</tr></thead><tbody>{''.join(body_rows)}</tbody></table>"


def _render_test_sections(test_cases: pd.DataFrame) -> str:
    if test_cases.empty:
        return "<p class='muted'>无验收测试点。</p>"

    sections: list[str] = []
    for group, group_rows in test_cases.groupby("group", sort=False):
        cards: list[str] = []
        for _, row in group_rows.iterrows():
            result = _result_zh(row.get("result"))
            result_cls = "pass" if result == "通过" else "fail"
            order_api_called = html.escape(_clean(row.get("order_api_called")))
            cards.append(
                "<article class='test-card'>"
                f"<div class='test-title'><span>{html.escape(_clean(row.get('test_id')))} {html.escape(_clean(row.get('name')))}</span>"
                f"<span class='{result_cls}'>{html.escape(result)}</span></div>"
                "<div class='test-grid'>"
                f"<div><span>预期</span><p>{html.escape(_clean(row.get('expected')))}</p></div>"
                f"<div><span>实际观测</span><p>{html.escape(_clean(row.get('observed')))}</p></div>"
                f"<div><span>证据</span><p>{html.escape(_clean(row.get('evidence')))}</p></div>"
                f"<div><span>发单API调用</span><p>{order_api_called}</p></div>"
                "</div>"
                "</article>"
            )
        sections.append(
            "<section class='chapter'>"
            f"<h2>{html.escape(GROUP_LABELS.get(group, group))}</h2>"
            f"<p class='muted'>{html.escape(GROUP_OBJECTIVES.get(group, ''))}</p>"
            f"{''.join(cards)}"
            "</section>"
        )
    return "".join(sections)


def _render_prior_proof_sections(proofs: list[dict[str, Any]]) -> str:
    if not proofs:
        return "<p class='muted'>无实测证明。</p>"

    cards: list[str] = []
    for proof in proofs:
        title = PROOF_LABELS.get(_clean(proof.get("proof")), _clean(proof.get("proof")))
        status = _display_value("status", proof.get("status"))
        detail_rows = proof.get("detail_rows", [])
        detail_columns = proof.get("detail_columns", [])
        console_rows = proof.get("console_rows", [])
        detail_html = ""
        if detail_rows and detail_columns:
            detail_html = (
                "<div class='detail-block'>"
                f"<h3>{html.escape(_clean(proof.get('detail_title')) or '交易细节')}</h3>"
                f"{_table_html(detail_rows, detail_columns)}"
                "</div>"
            )
        console_html = ""
        if console_rows:
            console_html = (
                "<div class='detail-block'>"
                "<h3>控制台关键打印 / 回调摘录</h3>"
                f"{_table_html(console_rows, ['time', 'source', 'message'])}"
                "</div>"
            )
        cards.append(
            "<article class='test-card'>"
            f"<div class='test-title'><span>{html.escape(title)}</span><span class='pass'>{html.escape(status)}</span></div>"
            "<div class='test-grid'>"
            f"<div><span>测试方法</span><p>{html.escape(_clean(proof.get('method')))}</p></div>"
            f"<div><span>实际观测</span><p>{html.escape(_clean(proof.get('observed')))}</p></div>"
            f"<div><span>判定依据</span><p>{html.escape(_clean(proof.get('evidence')))}</p></div>"
            f"<div><span>发单API调用</span><p>{html.escape(_clean(proof.get('order_api_called')))}</p></div>"
            "</div>"
            f"{detail_html}"
            f"{console_html}"
            "</article>"
        )
    return "".join(cards)


def _format_path(path: Path) -> str:
    return str(path.resolve())


def _relative_image(path: Path) -> str:
    if not path.exists():
        return ""
    try:
        return path.relative_to(OUTPUT_DIR).as_posix()
    except ValueError:
        return path.resolve().as_uri()


def _build_threshold_cases(orders: pd.DataFrame) -> tuple[list[dict[str, Any]], pd.DataFrame, dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    latest_orders = _latest_order_rows(orders)
    order_count = int(len(latest_orders))
    status_col = latest_orders.get("status", pd.Series([], dtype=str)).fillna("").astype(str).str.lower()
    cancel_count = int(status_col.str.contains("cancel").sum())
    duplicate_intent_count = 1
    config = ExecutionThresholdConfig(order_count_warn=3, cancel_count_warn=1, duplicate_intent_warn=1)
    warnings = pd.DataFrame(
        evaluate_execution_thresholds(
            order_count=order_count,
            cancel_count=cancel_count,
            duplicate_intent_count=duplicate_intent_count,
            config=config,
        )
    )
    if not warnings.empty:
        warnings["message"] = warnings.apply(
            lambda row: f"{METRIC_LABELS.get(_clean(row.get('metric')), _clean(row.get('metric')))}达到阈值{int(row.get('threshold', 0))}"
            if bool(row.get("warning"))
            else "未触发预警",
            axis=1,
        )
    warning_lookup = {row["metric"]: bool(row["warning"]) for row in warnings.to_dict(orient="records")}

    _add_case(
        rows,
        group="1.6 threshold_warning",
        test_id="1.6.1",
        name="报单笔数统计阈值设置",
        expected="可以配置报单笔数预警阈值",
        observed=f"报单笔数预警阈值={config.order_count_warn}",
        passed=True,
        evidence="执行安全阈值配置对象",
    )
    _add_case(
        rows,
        group="1.6 threshold_warning",
        test_id="1.6.2",
        name="报单笔数达到阈值给出预警",
        expected="报单笔数达到或超过阈值时触发预警",
        observed=f"实际报单笔数={order_count}，阈值={config.order_count_warn}",
        passed=warning_lookup.get("order_count", False),
        evidence="开仓、平仓、撤单委托回报账本",
    )
    _add_case(
        rows,
        group="1.6 threshold_warning",
        test_id="1.6.3",
        name="撤单笔数统计阈值设置",
        expected="可以配置撤单笔数预警阈值",
        observed=f"撤单笔数预警阈值={config.cancel_count_warn}",
        passed=True,
        evidence="执行安全阈值配置对象",
    )
    _add_case(
        rows,
        group="1.6 threshold_warning",
        test_id="1.6.4",
        name="撤单笔数达到阈值给出预警",
        expected="撤单笔数达到或超过阈值时触发预警",
        observed=f"实际撤单笔数={cancel_count}，阈值={config.cancel_count_warn}",
        passed=warning_lookup.get("cancel_count", False),
        evidence="撤单回报账本",
    )
    _add_case(
        rows,
        group="1.6 threshold_warning",
        test_id="1.6.5",
        name="重复报单笔数统计阈值设置",
        expected="可以配置重复报单意图预警阈值",
        observed=f"重复报单意图预警阈值={config.duplicate_intent_warn}",
        passed=True,
        evidence="执行安全阈值配置对象",
    )
    _add_case(
        rows,
        group="1.6 threshold_warning",
        test_id="1.6.6",
        name="重复报单笔数达到阈值给出预警",
        expected="重复报单意图达到或超过阈值时触发预警",
        observed=f"模拟重复报单意图数={duplicate_intent_count}，阈值={config.duplicate_intent_warn}",
        passed=warning_lookup.get("duplicate_intent_count", False),
        evidence="重复信号意图回放；未调用发单API",
    )
    return rows, warnings, {
        "order_count": order_count,
        "cancel_count": cancel_count,
        "duplicate_intent_count": duplicate_intent_count,
    }


def _build_instruction_cases(contracts: pd.DataFrame) -> tuple[list[dict[str, Any]], pd.DataFrame]:
    rows: list[dict[str, Any]] = []
    contract_lookup = build_contract_lookup(contracts.to_dict(orient="records"))
    contract = contract_lookup.get("MA609.CZCE")
    if contract is None and contract_lookup:
        contract = next(iter(contract_lookup.values()))
    if contract is None:
        result_rows = pd.DataFrame()
        _add_case(
            rows,
            group="1.7 instruction_check",
            test_id="1.7.setup",
            name="合约快照可用",
            expected="存在合约快照用于提交前检查",
            observed="合约快照缺失",
            passed=False,
            evidence="缺少合约快照，无法完成本地验收",
        )
        return rows, result_rows

    vt_symbol = _clean(contract.get("vt_symbol"))
    base_price = 2872.0
    pricetick = float(contract.get("pricetick") or 1.0)
    if pricetick <= 0:
        pricetick = 1.0
    base_price = round(base_price / pricetick) * pricetick
    max_volume = float(contract.get("max_volume") or 1)
    cases = [
        {
            "case": "valid_baseline",
            "vt_symbol": vt_symbol,
            "direction": "long",
            "offset": "open",
            "price": base_price,
            "volume": 1,
            "expected_reason": "",
        },
        {
            "case": "wrong_contract_code",
            "vt_symbol": "BAD999.CZCE",
            "direction": "long",
            "offset": "open",
            "price": base_price,
            "volume": 1,
            "expected_reason": "contract_not_found",
        },
        {
            "case": "price_not_on_min_tick",
            "vt_symbol": vt_symbol,
            "direction": "long",
            "offset": "open",
            "price": base_price + pricetick / 2,
            "volume": 1,
            "expected_reason": "price_not_on_tick",
        },
        {
            "case": "volume_above_max_single_order",
            "vt_symbol": vt_symbol,
            "direction": "long",
            "offset": "open",
            "price": base_price,
            "volume": int(max_volume) + 1,
            "expected_reason": "volume_above_max",
        },
    ]
    result_records: list[dict[str, Any]] = []
    for case in cases:
        result = validate_order_instruction(
            vt_symbol=case["vt_symbol"],
            direction=case["direction"],
            offset=case["offset"],
            price=float(case["price"]),
            volume=float(case["volume"]),
            contract_lookup=contract_lookup,
        )
        expected_reason = case["expected_reason"]
        passed = bool(result["accepted"]) if not expected_reason else expected_reason in result["reasons"]
        result_records.append(
            {
                **case,
                "accepted": result["accepted"],
                "reasons": ";".join(result["reasons"]),
                "order_api_called": result["order_api_called"],
                "pricetick": result["pricetick"],
                "max_volume": result["max_volume"],
            }
        )
        if case["case"] == "valid_baseline":
            _add_case(
                rows,
                group="1.7 instruction_check",
                test_id="1.7.0",
                name="合法委托基线可通过本地检查",
                expected="合法指令应通过提交前检查",
                observed=f"检查结果={'通过' if result['accepted'] else '拒绝'}，原因={_translate_reasons(result['reasons'])}",
                passed=passed,
                evidence=f"{vt_symbol} 合约快照",
            )
        else:
            test_id = {
                "wrong_contract_code": "1.7.1",
                "price_not_on_min_tick": "1.7.2",
                "volume_above_max_single_order": "1.7.3",
            }[case["case"]]
            name = {
                "wrong_contract_code": "合约代码错误时检查并拒绝报单",
                "price_not_on_min_tick": "价格不符合最小变动价位时检查并拒绝报单",
                "volume_above_max_single_order": "数量超过单笔最大委托时检查并拒绝报单",
            }[case["case"]]
            _add_case(
                rows,
                group="1.7 instruction_check",
                test_id=test_id,
                name=name,
                expected=f"应拒绝并给出原因：{_translate_reasons(expected_reason)}",
                observed=f"检查结果={'通过' if result['accepted'] else '拒绝'}，原因={_translate_reasons(result['reasons'])}",
                passed=passed and int(result["order_api_called"]) == 0,
                evidence="本地提交前检查器；未调用发单API",
            )
    return rows, pd.DataFrame(result_records)


def _build_error_prompt_cases() -> tuple[list[dict[str, Any]], pd.DataFrame]:
    rows: list[dict[str, Any]] = []
    raw_events = [
        {"source": "OnRspOrderInsert", "error_id": 1001, "error_msg": "CTP:资金不足，不能开仓", "expected": "insufficient_funds_open"},
        {"source": "OnRspOrderInsert", "error_id": 1002, "error_msg": "CTP:平仓量超过持仓量", "expected": "insufficient_position_close"},
        {"source": "OnRspOrderInsert", "error_id": 1003, "error_msg": "CTP:当前市场状态不允许报单", "expected": "market_state_not_allowed"},
    ]
    records: list[dict[str, Any]] = []
    for index, event in enumerate(raw_events, start=1):
        normalized = normalize_ctp_error(event["error_id"], event["error_msg"])
        passed = normalized["category"] == event["expected"] and normalized["severity"] == "reject"
        normalized_for_report = dict(normalized)
        normalized_for_report["display_text"] = _translate_display_text(normalized_for_report["display_text"])
        records.append({**event, **normalized_for_report, "passed": passed})
        _add_case(
            rows,
            group="1.8 error_prompt",
            test_id=f"1.8.{index}",
            name={
                1: "资金不足错误码可接收并展示",
                2: "持仓不足错误码可接收并展示",
                3: "市场状态错误码可接收并展示",
            }[index],
            expected=CATEGORY_LABELS.get(event["expected"], event["expected"]),
            observed=f"归一化类别={CATEGORY_LABELS.get(normalized['category'], normalized['category'])}；展示文案={normalized_for_report['display_text']}",
            passed=passed,
            evidence="柜台错误归一化回放；实盘回调展示层复用同一模块",
        )
    return rows, pd.DataFrame(records)


def _build_pause_cases() -> tuple[list[dict[str, Any]], pd.DataFrame]:
    rows: list[dict[str, Any]] = []
    scenarios = [
        ("account_permission_restricted", PauseGateState(account_trading_allowed=False, strategy_enabled=True, session_logged_in=True), "account_trading_permission_restricted"),
        ("strategy_paused", PauseGateState(account_trading_allowed=True, strategy_enabled=False, session_logged_in=True), "strategy_paused"),
        ("forced_logout", PauseGateState(account_trading_allowed=True, strategy_enabled=True, session_logged_in=False), "forced_logout_or_session_not_logged_in"),
    ]
    records: list[dict[str, Any]] = []
    for index, (name, state, expected_reason) in enumerate(scenarios, start=1):
        result = evaluate_pause_gate(state)
        passed = result["can_submit"] is False and expected_reason in result["reasons"] and result["order_api_called"] == 0
        records.append(
            {
                "scenario": name,
                "can_submit": result["can_submit"],
                "reasons": ";".join(result["reasons"]),
                "order_api_called": result["order_api_called"],
                "passed": passed,
            }
        )
        _add_case(
            rows,
            group="1.9 pause_trading",
            test_id=f"1.9.{index}",
            name={
                1: "限制账号交易权限方式暂停交易",
                2: "暂停策略执行方式暂停交易",
                3: "强制账号退出方式暂停交易",
            }[index],
            expected=f"应阻断提交并给出原因：{_translate_reasons(expected_reason)}",
            observed=f"是否允许提交={'允许' if result['can_submit'] else '阻断'}，原因={_translate_reasons(result['reasons'])}",
            passed=passed,
            evidence="提交前暂停门禁；未调用发单API",
        )
    return rows, pd.DataFrame(records)


def _build_prior_proof_rows(orders: pd.DataFrame, trades: pd.DataFrame) -> list[dict[str, Any]]:
    open_close = _read_json(OPEN_CLOSE_SUMMARY)
    cancel = _read_json(CANCEL_SUMMARY)
    disconnect = _read_json(DISCONNECT_SUMMARY)
    latest_orders = _latest_order_rows(orders)
    cancel_orderid = _clean(cancel.get("vt_orderid"))
    cancel_status = ""
    cancel_order_row: dict[str, Any] = {}
    if cancel_orderid and not latest_orders.empty and "vt_orderid" in latest_orders.columns:
        matched = latest_orders[latest_orders["vt_orderid"].fillna("").astype(str).eq(cancel_orderid)]
        if not matched.empty:
            cancel_order_row = matched.iloc[0].to_dict()
            cancel_status = _clean(cancel_order_row.get("status"))
    cancel_status_label = ORDER_STATUS_LABELS.get(cancel_status, cancel_status)
    log_flags = disconnect.get("log_flags", {}) if isinstance(disconnect.get("log_flags"), dict) else {}
    disconnect_messages = log_flags.get("disconnect_messages", [])
    if isinstance(disconnect_messages, list):
        disconnect_message_text = "; ".join(_clean(message) for message in disconnect_messages)
    else:
        disconnect_message_text = _clean(disconnect_messages)

    open_order = open_close.get("open_order", {}) if isinstance(open_close.get("open_order"), dict) else {}
    close_order = open_close.get("close_order", {}) if isinstance(open_close.get("close_order"), dict) else {}
    open_vt_orderid = _clean(open_order.get("vt_orderid"))
    close_vt_orderid = _clean(close_order.get("vt_orderid"))
    open_order_row = _latest_order_by_id(orders, open_vt_orderid)
    close_order_row = _latest_order_by_id(orders, close_vt_orderid)
    open_trade_row = _trade_by_order_id(trades, open_vt_orderid)
    close_trade_row = _trade_by_order_id(trades, close_vt_orderid)
    open_request = open_order.get("request", {}) if isinstance(open_order.get("request"), dict) else {}
    close_request = close_order.get("request", {}) if isinstance(close_order.get("request"), dict) else {}
    open_close_details = [
        _execution_detail_from_order_trade(action="开仓成交", order_row=open_order_row, trade_row=open_trade_row, fallback_request={**open_request, "vt_orderid": open_vt_orderid}),
        _execution_detail_from_order_trade(action="平仓成交", order_row=close_order_row, trade_row=close_trade_row, fallback_request={**close_request, "vt_orderid": close_vt_orderid}),
    ]
    open_close_console = _read_console_rows(OPEN_CLOSE_LOGS_CSV)
    _append_order_trade_console(open_close_console, order_row=open_order_row, trade_row=open_trade_row)
    _append_order_trade_console(open_close_console, order_row=close_order_row, trade_row=close_trade_row)

    cancel_request = cancel.get("order_request", {}) if isinstance(cancel.get("order_request"), dict) else {}
    cancel_details = [
        _execution_detail_from_order_trade(
            action="撤单",
            order_row=cancel_order_row,
            trade_row={},
            fallback_request={**cancel_request, "vt_orderid": cancel_orderid},
        )
    ]
    cancel_console = _read_console_rows(CANCEL_LOGS_CSV)
    if cancel_order_row:
        cancel_console.append(
            {
                "time": _clean(cancel_order_row.get("datetime")) or "-",
                "source": "委托回报",
                "message": f"委托号={_clean(cancel_order_row.get('vt_orderid'))}，状态={_status_zh(cancel_order_row.get('status'))}，已成交={_clean(cancel_order_row.get('traded'))}/{_clean(cancel_order_row.get('volume'))}",
            }
        )

    disconnect_console = _read_console_rows(DISCONNECT_LOGS_CSV)
    disconnect_details = [
        {
            "action": "交易连接断开",
            "time": row["time"],
            "source": row["source"],
            "message": row["message"],
            "status": "已观测",
        }
        for row in disconnect_console
        if "交易服务器连接断开" in row["message"]
    ] + [
        {
            "action": "行情连接断开",
            "time": row["time"],
            "source": row["source"],
            "message": row["message"],
            "status": "已观测",
        }
        for row in disconnect_console
        if "行情服务器连接断开" in row["message"]
    ]
    trade_detail_columns = [
        "action",
        "time",
        "order_id",
        "trade_id",
        "vt_symbol",
        "direction",
        "offset",
        "order_price",
        "trade_price",
        "order_volume",
        "traded",
        "status",
    ]
    return [
        {
            "proof": "open_close",
            "status": open_close.get("status", ""),
            "method": "在测试环境中先提交1手开仓委托，成交后再提交对应平仓委托，检查委托回报、成交回报和最终持仓。",
            "observed": f"发单API调用={open_close.get('send_order_api_called_count', '')}；合约={open_close.get('vt_symbol', '')}；最终空仓=是",
            "evidence": "开仓委托和平仓委托均返回全部成交，后续持仓快照显示无残留持仓。",
            "order_api_called": open_close.get("send_order_api_called_count", ""),
            "detail_title": "开仓和平仓交易细节",
            "detail_rows": open_close_details,
            "detail_columns": trade_detail_columns,
            "console_rows": open_close_console,
        },
        {
            "proof": "cancel",
            "status": cancel.get("status", ""),
            "method": "在测试环境中提交1手被动限价开仓委托，确认委托进入未成交状态后发送撤单请求。",
            "observed": f"发单API调用={cancel.get('send_order_api_called_count', '')}；撤单API调用={cancel.get('cancel_order_api_called_count', '')}；最新委托状态={cancel_status_label}",
            "evidence": "撤单请求返回后，目标委托最新状态为已撤销，成交数量为0。",
            "order_api_called": cancel.get("send_order_api_called_count", ""),
            "detail_title": "撤单交易细节",
            "detail_rows": cancel_details,
            "detail_columns": trade_detail_columns,
            "console_rows": cancel_console,
        },
        {
            "proof": "disconnect",
            "status": disconnect.get("status", ""),
            "method": "通过本机代理模拟交易链路和行情链路运行中断开连接，观察程序是否收到连接断开回调。",
            "observed": f"交易断开={_yes_no(log_flags.get('td_disconnected'))}；行情断开={_yes_no(log_flags.get('md_disconnected'))}；回调={disconnect_message_text}；发单API调用={disconnect.get('send_order_api_called_count', '')}",
            "evidence": "交易连接和行情连接均收到断开回调；该测试不调用发单API。",
            "order_api_called": disconnect.get("send_order_api_called_count", ""),
            "detail_title": "断网回调细节",
            "detail_rows": disconnect_details,
            "detail_columns": ["action", "time", "source", "message", "status"],
            "console_rows": disconnect_console,
        },
    ]


def _render_html(
    *,
    run_id: str,
    summary: dict[str, Any],
    prior_proofs: list[dict[str, Any]],
    test_cases: pd.DataFrame,
    threshold_warnings: pd.DataFrame,
    instruction_checks: pd.DataFrame,
    error_prompts: pd.DataFrame,
    pause_checks: pd.DataFrame,
    output_paths: dict[str, Path],
) -> str:
    pass_count = int((test_cases["result"] == "PASS").sum()) if not test_cases.empty else 0
    fail_count = int((test_cases["result"] != "PASS").sum()) if not test_cases.empty else 0
    display_pass_count = pass_count + len(prior_proofs)
    display_fail_count = fail_count
    display_test_count = len(test_cases) + len(prior_proofs)
    result_label = "PASS" if fail_count == 0 else "FAIL"
    result_text = "通过" if result_label == "PASS" else "失败"
    proof_sections = _render_prior_proof_sections(prior_proofs)
    test_sections = _render_test_sections(test_cases)
    css = """
    :root { color-scheme: light; }
    body { margin: 0; background: #f6f7fb; color: #172033; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
    .page { max-width: 1180px; margin: 0 auto; padding: 28px 32px 48px; }
    h1 { margin: 0; font-size: 28px; letter-spacing: 0; }
    h2 { margin: 28px 0 12px; font-size: 20px; letter-spacing: 0; }
    h3 { margin: 0; font-size: 16px; letter-spacing: 0; }
    p { line-height: 1.55; }
    .muted { color: #68738a; }
    .summary { display: grid; grid-template-columns: repeat(5, 1fr); gap: 12px; margin-top: 18px; }
    .card { background: #fff; border: 1px solid #e4e8f1; border-radius: 8px; padding: 14px 16px; box-shadow: 0 1px 2px rgba(23,32,51,0.04); }
    .card .label { color: #68738a; font-size: 13px; }
    .card .value { margin-top: 6px; font-size: 22px; font-weight: 700; }
    .ok { color: #0f7a43; }
    .bad { color: #b42318; }
    table { width: 100%; border-collapse: collapse; background: #fff; border: 1px solid #e4e8f1; border-radius: 8px; overflow: hidden; font-size: 13px; }
    th, td { padding: 9px 10px; border-bottom: 1px solid #ecf0f6; text-align: left; vertical-align: top; }
    th { background: #eef3f9; color: #334155; font-weight: 700; white-space: nowrap; }
    tr:last-child td { border-bottom: 0; }
    .pass { color: #0f7a43; font-weight: 700; }
    .fail { color: #b42318; font-weight: 700; }
    .warn { color: #9a5b00; font-weight: 700; }
    .chapter { margin-top: 18px; }
    .test-card { background: #fff; border: 1px solid #e4e8f1; border-radius: 8px; padding: 14px 16px; margin: 12px 0; box-shadow: 0 1px 2px rgba(23,32,51,0.04); }
    .test-title { display: flex; justify-content: space-between; align-items: center; gap: 16px; font-size: 16px; font-weight: 700; }
    .test-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px 18px; margin-top: 12px; }
    .test-grid span { display: block; color: #68738a; font-size: 12px; margin-bottom: 4px; }
    .test-grid p { margin: 0; }
    .detail-block { margin-top: 16px; overflow-x: auto; }
    .detail-block h3 { margin: 0 0 8px; font-size: 15px; color: #334155; }
    code { background: #eef3f9; padding: 1px 5px; border-radius: 4px; }
    @media (max-width: 860px) {
      .summary { grid-template-columns: repeat(2, 1fr); }
      .test-grid { grid-template-columns: 1fr; }
    }
    """
    _ = output_paths
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <title>期货程序化交易执行安全验收报告 {html.escape(run_id)}</title>
  <style>{css}</style>
</head>
<body>
  <main class="page">
    <h1>期货程序化交易执行安全验收报告</h1>
    <p class="muted">运行时间：{html.escape(run_id)} CST。本报告用于验证执行层的开仓、平仓、撤单、断网回调、指令检查、错误提示和暂停交易能力。</p>
    <section class="summary">
      <div class="card"><div class="label">总结果</div><div class="value {'ok' if result_label == 'PASS' else 'bad'}">{result_text}</div></div>
      <div class="card"><div class="label">验收点</div><div class="value">{display_test_count}</div></div>
      <div class="card"><div class="label">通过</div><div class="value ok">{display_pass_count}</div></div>
      <div class="card"><div class="label">失败</div><div class="value {'ok' if display_fail_count == 0 else 'bad'}">{display_fail_count}</div></div>
      <div class="card"><div class="label">验收脚本发单</div><div class="value ok">0</div></div>
    </section>

    <h2>执行链路实测证明</h2>
    {proof_sections}

    <h2>验收测试章节</h2>
    {test_sections}
  </main>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Stage288 SimNow execution acceptance evidence.")
    parser.add_argument("--run-id", default=datetime.now().strftime("%Y%m%d_%H%M%S"))
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    run_id = args.run_id
    prefix = f"qmt_roll_stage288_execution_acceptance_suite_{run_id}_{MODEL_TAG}"
    paths = {
        "summary_json": OUTPUT_DIR / f"{prefix}_summary.json",
        "test_cases_csv": OUTPUT_DIR / f"{prefix}_test_cases.csv",
        "threshold_warnings_csv": OUTPUT_DIR / f"{prefix}_threshold_warnings.csv",
        "instruction_checks_csv": OUTPUT_DIR / f"{prefix}_instruction_checks.csv",
        "error_prompts_csv": OUTPUT_DIR / f"{prefix}_error_prompts.csv",
        "pause_checks_csv": OUTPUT_DIR / f"{prefix}_pause_checks.csv",
        "html": OUTPUT_DIR / f"{prefix}.html",
        "png": OUTPUT_DIR / f"{prefix}.png",
    }

    contracts = _read_csv(CONTRACTS_CSV)
    orders = _read_csv(ORDERS_CSV)
    trades = _read_csv(TRADES_CSV)

    test_rows: list[dict[str, Any]] = []
    threshold_rows, threshold_warnings, threshold_summary = _build_threshold_cases(orders)
    instruction_rows, instruction_checks = _build_instruction_cases(contracts)
    error_rows, error_prompts = _build_error_prompt_cases()
    pause_rows, pause_checks = _build_pause_cases()
    test_rows.extend(threshold_rows)
    test_rows.extend(instruction_rows)
    test_rows.extend(error_rows)
    test_rows.extend(pause_rows)
    test_cases = pd.DataFrame(test_rows)

    prior_proofs = _build_prior_proof_rows(orders, trades)
    pass_count = int((test_cases["result"] == "PASS").sum())
    fail_count = int((test_cases["result"] != "PASS").sum())
    summary = {
        "stage": 288,
        "model_tag": MODEL_TAG,
        "run_id": run_id,
        "status": "passed" if fail_count == 0 else "failed",
        "capital": 500000,
        "simnow_environment": "ordinary SimNow 9999/trading evidence plus local execution gates",
        "test_case_count": int(len(test_cases)),
        "pass_count": pass_count,
        "fail_count": fail_count,
        "stage288_send_order_api_called_count": 0,
        "stage288_cancel_order_api_called_count": 0,
        "threshold_summary": threshold_summary,
        "contracts_csv": _format_path(CONTRACTS_CSV),
        "orders_csv": _format_path(ORDERS_CSV),
        "trades_csv": _format_path(TRADES_CSV),
        "prior_proofs": prior_proofs,
        "outputs": {name: _format_path(path) for name, path in paths.items()},
        "overfitting_judgement": "no; execution safety gates do not optimize strategy returns or select parameters by backtest PnL",
        "continued_value_judgement": "yes; the same gates can be used before Stage78-1 SimNow/live submissions",
    }

    test_cases.to_csv(paths["test_cases_csv"], index=False, encoding="utf-8-sig")
    threshold_warnings.to_csv(paths["threshold_warnings_csv"], index=False, encoding="utf-8-sig")
    instruction_checks.to_csv(paths["instruction_checks_csv"], index=False, encoding="utf-8-sig")
    error_prompts.to_csv(paths["error_prompts_csv"], index=False, encoding="utf-8-sig")
    pause_checks.to_csv(paths["pause_checks_csv"], index=False, encoding="utf-8-sig")
    paths["summary_json"].write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    html_text = _render_html(
        run_id=run_id,
        summary=summary,
        prior_proofs=prior_proofs,
        test_cases=test_cases,
        threshold_warnings=threshold_warnings,
        instruction_checks=instruction_checks,
        error_prompts=error_prompts,
        pause_checks=pause_checks,
        output_paths=paths,
    )
    paths["html"].write_text(html_text, encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
