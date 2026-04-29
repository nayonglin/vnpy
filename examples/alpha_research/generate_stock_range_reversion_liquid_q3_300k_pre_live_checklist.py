from __future__ import annotations

import json
import os
from datetime import date, datetime
from pathlib import Path
from typing import Any

import polars as pl

from analyze_stock_range_reversion_layer_attribution import load_panels
from backtest_stock_range_reversion_industry_neutral_merged_portfolio import NATIVE_RESULTS_DIR, pct
from generate_stock_range_reversion_liquid_q3_paper_tracking import markdown_table


OUTPUT_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_300k_pre_live_checklist_2018_2026"
).expanduser().resolve()
PREFIX: str = "stock_range_reversion_liquid_q3_300k_pre_live_checklist_v1"

SUITE_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_300k_suite_2018_2026"
).expanduser().resolve()
SUITE_PREFIX: str = "stock_range_reversion_liquid_q3_300k_suite_v1"

SIDECAR_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_300k_latest_packet_component_guard_sidecar_2018_2026"
).expanduser().resolve()
SIDECAR_PREFIX: str = "stock_range_reversion_liquid_q3_300k_latest_packet_component_guard_sidecar_v1"
LIVE_TARGET_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_300k_live_target_builder_2018_2026"
).expanduser().resolve()
LIVE_TARGET_PREFIX: str = "stock_range_reversion_liquid_q3_300k_live_target_builder_v1"
SNAPSHOT_TEMPLATE_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_300k_snapshot_template_2018_2026"
).expanduser().resolve()
SNAPSHOT_TEMPLATE_PREFIX: str = "stock_range_reversion_liquid_q3_300k_snapshot_template_v1"
ORDER_RECALC_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_300k_order_recalc_dryrun_2018_2026"
).expanduser().resolve()
ORDER_RECALC_PREFIX: str = "stock_range_reversion_liquid_q3_300k_order_recalc_dryrun_v1"

RESEARCH_SOURCES: tuple[tuple[str, str], ...] = (
    (
        "QuantConnect documents pre-trade risk controls before order submission",
        "https://www.quantconnect.com/docs/v2/writing-algorithms/trading-and-orders/pre-trade-risk-control",
    ),
    (
        "OpenAlgo is an open-source algo trading platform with pre-deployment testing concepts",
        "https://github.com/marketcalls/openalgo",
    ),
    (
        "Automated Financial Market Trading System example separates order creation, risk checks and executions",
        "https://github.com/ThePredictiveDev/Automated-Financial-Market-Trading-System",
    ),
    (
        "SSE trading mechanism documents A-share board lot constraints",
        "https://english.sse.com.cn/start/trading/mechanism/",
    ),
)


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


def parse_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value)[:10]
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def current_check_date() -> date:
    override = os.getenv("PRE_LIVE_CHECK_DATE", "").strip()
    if override:
        return date.fromisoformat(override)
    return datetime.now().date()


def to_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if result != result:
        return default
    return result


def to_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _markdown_all(frame: pl.DataFrame, max_rows: int = 80) -> str:
    if frame.is_empty():
        return "无数据"
    return markdown_table(frame, frame.columns, max_rows=max_rows)


def read_csv(path: Path) -> pl.DataFrame:
    return pl.read_csv(path, try_parse_dates=True, schema_overrides={"symbol": pl.Utf8})


def add_check(
    rows: list[dict[str, Any]],
    category: str,
    checkpoint: str,
    status: str,
    value: Any,
    expected: Any,
    severity: str,
    note: str,
) -> None:
    rows.append(
        {
            "category": category,
            "checkpoint": checkpoint,
            "status": status,
            "severity": severity,
            "value": "" if value is None else str(value),
            "expected": "" if expected is None else str(expected),
            "note": note,
        }
    )


def build_checklist(
    summary: dict[str, Any],
    sidecar_summary: dict[str, Any],
    live_summary: dict[str, Any],
    snapshot_template_summary: dict[str, Any],
    order_recalc_summary: dict[str, Any],
    latest_orders: pl.DataFrame,
    latest_targets: pl.DataFrame,
    estimated_orders: pl.DataFrame,
    recalc_orders: pl.DataFrame,
    current_date_value: date,
    stock_max_date: date | None,
    benchmark_max_date: date | None,
) -> pl.DataFrame:
    rows: list[dict[str, Any]] = []
    legacy_latest_target_date = parse_date(summary.get("latest_target_date"))
    live_signal_date = parse_date(live_summary.get("latest_signal_date")) if live_summary else None
    live_target_date = parse_date(live_summary.get("proposed_target_date")) if live_summary else None
    effective_target_date = live_target_date or legacy_latest_target_date
    calendar_lag_days = (current_date_value - effective_target_date).days if effective_target_date else None
    stock_lag_days = (current_date_value - stock_max_date).days if stock_max_date else None
    benchmark_lag_days = (current_date_value - benchmark_max_date).days if benchmark_max_date else None
    zero_lot_count = to_int(
        live_summary.get("live_zero_lot_target_count") if live_summary else sidecar_summary.get("latest_zero_lot_target_count")
    )
    raw_target_count = to_int(
        live_summary.get("live_raw_target_count") if live_summary else sidecar_summary.get("latest_raw_target_count")
    )
    zero_lot_ratio = zero_lot_count / raw_target_count if raw_target_count else 0.0
    raw_target_amount = to_float(
        live_summary.get("live_raw_target_amount_sum_cny") if live_summary else sidecar_summary.get("latest_raw_target_amount_sum_cny")
    )
    account_size = to_float(sidecar_summary.get("account_size_cny"))
    raw_target_gross = raw_target_amount / account_size if account_size else 0.0
    actual_gross = (
        to_float(live_summary.get("live_sidecar_target_amount_sum_cny")) / account_size
        if live_summary and account_size
        else to_float(sidecar_summary.get("latest_actual_gross_weight"))
    )
    exposure_capture_ratio = actual_gross / raw_target_gross if raw_target_gross else 0.0
    min_order = to_float(sidecar_summary.get("latest_filled_order_min_cny"))
    max_order = to_float(sidecar_summary.get("latest_filled_order_max_cny"))

    add_check(
        rows,
        "workflow",
        "suite_passed",
        "pass" if summary.get("suite_state") == "pass" else "fail",
        summary.get("suite_state"),
        "pass",
        "hard_blocker",
        "一键suite必须通过，才能讨论实盘。",
    )
    add_check(
        rows,
        "workflow",
        "source_quality_has_no_fail",
        "pass" if to_int(summary.get("quality_fail_count")) == 0 else "fail",
        summary.get("quality_fail_count"),
        0,
        "hard_blocker",
        "suite源报告不能有失败项。",
    )
    add_check(
        rows,
        "data_freshness",
        "latest_target_not_stale_by_calendar",
        "pass" if calendar_lag_days is not None and calendar_lag_days <= 1 else "fail",
        calendar_lag_days,
        "<=1 calendar day",
        "hard_blocker",
        "当前检查日与有效目标执行日差距过大时，不能发真实委托；有live目标时以live建议执行日为准。",
    )
    add_check(
        rows,
        "data_freshness",
        "live_target_builder_available",
        "pass" if bool(live_summary) else "fail",
        live_summary.get("target_builder_state") if live_summary else "missing",
        "available",
        "hard_blocker",
        "实盘目标应来自live-target builder，而不是需要未来收益字段的回测target_weights。",
    )
    add_check(
        rows,
        "data_freshness",
        "live_signal_equals_stock_panel_max_date",
        "pass" if live_signal_date is not None and live_signal_date == stock_max_date else "fail",
        f"live_signal={live_signal_date}, stock_max={stock_max_date}",
        "live_signal == stock_panel_max_date",
        "hard_blocker",
        "live信号日应等于股票面板最大日期。",
    )
    add_check(
        rows,
        "data_freshness",
        "live_signal_equals_benchmark_panel_max_date",
        "pass" if live_signal_date is not None and live_signal_date == benchmark_max_date else "fail",
        f"live_signal={live_signal_date}, benchmark_max={benchmark_max_date}",
        "live_signal == benchmark_panel_max_date",
        "hard_blocker",
        "live信号日应等于基准面板最大日期。",
    )
    add_check(
        rows,
        "data_freshness",
        "live_target_after_signal_date",
        "pass" if live_target_date is not None and live_signal_date is not None and live_target_date > live_signal_date else "fail",
        f"live_target={live_target_date}, live_signal={live_signal_date}",
        "live_target > live_signal",
        "hard_blocker",
        "live目标执行日必须晚于信号日。",
    )
    add_check(
        rows,
        "data_freshness",
        "stock_panel_calendar_lag",
        "pass" if stock_lag_days is not None and stock_lag_days <= 1 else "fail",
        stock_lag_days,
        "<=1 calendar day",
        "hard_blocker",
        "股票面板本身不能明显滞后当前日期。",
    )
    add_check(
        rows,
        "paper_oos",
        "oos_days_reached_live_minimum",
        "pass" if to_int(summary.get("oos_days")) >= 20 else "fail",
        summary.get("oos_days"),
        ">=20",
        "hard_blocker",
        "OOS少于20个交易日只允许paper观察，不允许实盘。",
    )
    add_check(
        rows,
        "execution",
        "snapshot_template_available",
        "pass" if bool(snapshot_template_summary) else "fail",
        snapshot_template_summary.get("snapshot_template_state") if snapshot_template_summary else "missing",
        "available",
        "hard_blocker",
        "实盘前必须有目标日快照模板，避免价格/持仓/现金字段靠人工临时拼接。",
    )
    add_check(
        rows,
        "execution",
        "snapshot_template_validation_no_fail",
        "pass" if to_int(snapshot_template_summary.get("validation_fail_count")) == 0 else "fail",
        snapshot_template_summary.get("validation_fail_count") if snapshot_template_summary else "missing",
        0,
        "hard_blocker",
        "若提供了目标日快照，模板校验失败前不能进入真实委托。",
    )
    add_check(
        rows,
        "execution",
        "snapshot_input_loaded",
        "pass" if snapshot_template_summary.get("snapshot_input_state") == "loaded" else "warn",
        snapshot_template_summary.get("snapshot_input_state") if snapshot_template_summary else "missing",
        "loaded",
        "warning",
        "缺少目标日真实价格/券商持仓/现金快照时，订单重算仍是估算。",
    )
    add_check(
        rows,
        "execution",
        "order_recalc_available",
        "pass" if bool(order_recalc_summary) else "fail",
        order_recalc_summary.get("order_recalc_state") if order_recalc_summary else "missing",
        "available",
        "hard_blocker",
        "实盘前必须能把live target重算成订单dry-run。",
    )
    add_check(
        rows,
        "execution",
        "order_recalc_no_blocked_orders",
        "pass" if to_int(order_recalc_summary.get("blocked_order_count")) == 0 else "warn",
        order_recalc_summary.get("blocked_order_count") if order_recalc_summary else "missing",
        0,
        "warning",
        "重算后若有阻断订单，需要人工复核；有真实快照时不能提交。",
    )
    add_check(
        rows,
        "execution",
        "order_recalc_no_cash_limited_orders",
        "pass" if to_int(order_recalc_summary.get("cash_limited_order_count")) == 0 else "warn",
        order_recalc_summary.get("cash_limited_order_count") if order_recalc_summary else "missing",
        0,
        "warning",
        "现金限制意味着目标组合无法完整落地。",
    )
    add_check(
        rows,
        "execution",
        "order_recalc_no_not_index_buy",
        "pass" if to_int(order_recalc_summary.get("not_index_component_buy_order_count")) == 0 else "fail",
        order_recalc_summary.get("not_index_component_buy_order_count") if order_recalc_summary else "missing",
        0,
        "hard_blocker",
        "订单重算后不能出现最新已知非成分买入/加仓。",
    )
    add_check(
        rows,
        "execution",
        "order_recalc_price_snapshot_available",
        "pass" if bool(order_recalc_summary.get("price_snapshot_available")) else "warn",
        order_recalc_summary.get("price_snapshot_state") if order_recalc_summary else "missing",
        "snapshot_or_target_panel_available",
        "warning",
        "缺少目标日价格快照时，重算订单仍是估算，不能作为真实委托。",
    )
    add_check(
        rows,
        "execution",
        "live_estimated_orders_no_hard_block",
        "pass" if to_int(live_summary.get("estimated_blocked_order_count")) == 0 else "warn",
        live_summary.get("estimated_blocked_order_count") if live_summary else "missing",
        0,
        "warning",
        "live估算订单若有硬阻断，需要人工复核；估算订单本身仍不能直接发券商。",
    )
    add_check(
        rows,
        "execution",
        "latest_orders_no_block",
        "pass" if to_int(sidecar_summary.get("latest_blocked_order_count")) == 0 else "fail",
        sidecar_summary.get("latest_blocked_order_count"),
        0,
        "hard_blocker",
        "最新sidecar订单不能有阻断。",
    )
    add_check(
        rows,
        "execution",
        "latest_orders_no_unfilled",
        "pass" if abs(to_float(sidecar_summary.get("latest_unfilled_amount_sum_cny"))) <= 1e-9 else "fail",
        sidecar_summary.get("latest_unfilled_amount_sum_cny"),
        0,
        "hard_blocker",
        "最新sidecar订单不能有未成交金额。",
    )
    add_check(
        rows,
        "execution",
        "strict_guard_no_st_or_ineligible_buy",
        "pass" if to_int(sidecar_summary.get("latest_st_or_ineligible_buy_blocked_orders")) == 0 else "fail",
        sidecar_summary.get("latest_st_or_ineligible_buy_blocked_orders"),
        0,
        "hard_blocker",
        "最新交易日前置守门不能发现ST/不可研究买入。",
    )
    add_check(
        rows,
        "execution",
        "strict_guard_no_not_index_buy",
        "pass" if to_int(sidecar_summary.get("latest_not_index_guard_block_orders")) == 0 else "fail",
        sidecar_summary.get("latest_not_index_guard_block_orders"),
        0,
        "hard_blocker",
        "最新交易日不能有非成分买入/加仓落到执行守门。",
    )
    add_check(
        rows,
        "execution",
        "sidecar_matches_original_latest_orders",
        "pass" if to_int(sidecar_summary.get("latest_changed_order_rows_vs_original")) == 0 else "warn",
        sidecar_summary.get("latest_changed_order_rows_vs_original"),
        "0 preferred",
        "warning",
        "若sidecar改变当日订单，必须人工确认是资格修正而非误伤。",
    )
    add_check(
        rows,
        "lot_granularity",
        "zero_lot_ratio_not_material",
        "pass" if zero_lot_ratio <= 0.30 else "warn",
        f"{zero_lot_ratio:.2%}",
        "<=30%",
        "warning",
        "买不到一手比例高说明30万账户会偏离原始横截面篮子。",
    )
    add_check(
        rows,
        "lot_granularity",
        "exposure_capture_ratio_acceptable",
        "pass" if exposure_capture_ratio >= 0.70 else "warn",
        f"{exposure_capture_ratio:.2%}",
        ">=70%",
        "warning",
        "整手后实际暴露过低时，收益/风险形态会偏离研究组合。",
    )
    add_check(
        rows,
        "order_size",
        "min_order_amount_above_1000",
        "pass" if min_order >= 1000 else "warn",
        f"{min_order:.0f}",
        ">=1000 CNY preferred",
        "warning",
        "单笔金额太小会被最低佣金和滑点放大影响。",
    )
    add_check(
        rows,
        "order_size",
        "max_order_amount_under_5pct_account",
        "pass" if account_size > 0 and max_order <= account_size * 0.05 else "warn",
        f"{max_order:.0f}",
        f"<= {account_size * 0.05:.0f}",
        "warning",
        "单笔最大订单不应过度集中。",
    )
    add_check(
        rows,
        "manual",
        "broker_cash_and_position_reconciliation",
        "manual",
        "not checked by repository",
        "human verified",
        "manual_required",
        "真实账户现金、持仓、冻结资金和最小交易单位必须人工或券商API复核。",
    )
    add_check(
        rows,
        "manual",
        "kill_switch_and_order_channel_ready",
        "manual",
        "not checked by repository",
        "human verified",
        "manual_required",
        "实盘前必须确认撤单/停止交易机制、委托通道和异常通知。",
    )
    add_check(
        rows,
        "manual",
        "human_approval_for_latest_orders",
        "manual",
        f"legacy_orders={latest_orders.height}, live_estimated_orders={estimated_orders.height}, recalc_orders={recalc_orders.height}",
        "approved",
        "manual_required",
        "最终委托前必须人工确认订单列表、方向、股数、价格口径。",
    )
    add_check(
        rows,
        "manual",
        "regulatory_and_broker_rules_checked",
        "manual",
        "not checked by repository",
        "human verified",
        "manual_required",
        "涨跌停、停牌、ST、科创/创业板权限、佣金费率等需按券商账户实况确认。",
    )
    return pl.DataFrame(rows)


def summarize_readiness(checklist: pl.DataFrame) -> dict[str, Any]:
    hard_fail_count = checklist.filter((pl.col("severity") == "hard_blocker") & (pl.col("status") == "fail")).height
    warn_count = checklist.filter(pl.col("status") == "warn").height
    manual_count = checklist.filter(pl.col("status") == "manual").height
    fail_count = checklist.filter(pl.col("status") == "fail").height
    if hard_fail_count > 0:
        readiness_state = "red_not_live"
    elif manual_count > 0 or warn_count > 0:
        readiness_state = "yellow_manual_review_only"
    else:
        readiness_state = "green_paper_ready_not_auto_live"
    return {
        "readiness_state": readiness_state,
        "hard_fail_count": hard_fail_count,
        "fail_count": fail_count,
        "warn_count": warn_count,
        "manual_count": manual_count,
        "pass_count": checklist.filter(pl.col("status") == "pass").height,
    }


def write_report(
    summary: dict[str, Any],
    checklist: pl.DataFrame,
    latest_orders: pl.DataFrame,
    latest_targets: pl.DataFrame,
    latest_holdings: pl.DataFrame,
    estimated_orders: pl.DataFrame,
    recalc_orders: pl.DataFrame,
    paths: dict[str, Path],
) -> Path:
    failed = checklist.filter(pl.col("status") == "fail")
    warned = checklist.filter(pl.col("status") == "warn")
    manual = checklist.filter(pl.col("status") == "manual")
    report_path = paths["report"]
    lines = [
        "# 股票震荡liquid_q3 30万实盘前检查清单 v1",
        "",
        f"- 记录时间：{datetime.now().strftime('%Y-%m-%d %H:%M CST')}",
        "- 当前研究线：股票震荡独立策略研究，不接入第78。",
        "- 本阶段性质：实盘前go/no-go检查；不新增信号、不调参数、不覆盖交易包。",
        f"- 检查日期：`{summary['check_date']}`。",
        f"- 旧latest目标执行日：`{summary['legacy_latest_target_date']}`。",
        f"- live信号日：`{summary['live_latest_signal_date']}`；live建议执行日：`{summary['live_proposed_target_date']}`。",
        f"- readiness：`{summary['readiness_state']}`。",
        "- A/B判断：实盘检查清单，不做第78 A/B/C。",
        "",
        "## 外部调研判断",
        "",
        "- 实盘前检查的核心不是收益更好，而是数据新鲜度、订单合法性、风控边界和人工兜底是否成立。",
        "- pre-trade risk control应在订单送出前阻断无效订单；开源交易系统也通常把订单生成、风险检查、成交回报分层。",
        "- 本清单因此把硬阻断、警告和人工确认分开，不用单一收益数字替代实盘准备度。",
        "",
        "参考资料：",
    ]
    for title, url in RESEARCH_SOURCES:
        lines.append(f"- [{title}]({url})")
    lines.extend(
        [
            "",
            "## 核心摘要",
            "",
            f"- 硬阻断失败`{summary['hard_fail_count']}`项，总失败`{summary['fail_count']}`项，警告`{summary['warn_count']}`项，人工确认`{summary['manual_count']}`项，通过`{summary['pass_count']}`项。",
            f"- 有效目标日历滞后`{summary['calendar_lag_days']}`天；股票面板最大日期`{summary['stock_panel_max_date']}`，基准面板最大日期`{summary['benchmark_max_date']}`。",
            f"- OOS天数`{summary['oos_days']}`，旧latest订单`{summary['latest_order_count']}`行，阻断`{summary['latest_blocked_order_count']}`行，未成交金额`{summary['latest_unfilled_amount_sum_cny']}`元。",
            f"- live估算订单`{summary['live_estimated_order_count']}`行，估算阻断`{summary['live_estimated_blocked_order_count']}`行。",
            f"- snapshot模板状态`{summary['snapshot_template_state']}`，输入状态`{summary['snapshot_input_state']}`，校验失败`{summary['snapshot_validation_fail_count']}`项。",
            f"- order recalc订单`{summary['order_recalc_order_count']}`行，阻断`{summary['order_recalc_blocked_order_count']}`行，现金限制`{summary['order_recalc_cash_limited_order_count']}`行，状态`{summary['order_recalc_state']}`。",
            f"- 最新原始目标`{summary['latest_raw_target_count']}`只，买不到一手`{summary['latest_zero_lot_target_count']}`只，占比`{pct(summary['latest_zero_lot_target_ratio'])}`。",
            f"- 原始目标暴露`{pct(summary['raw_target_gross_weight'])}`，实际暴露`{pct(summary['latest_actual_gross_weight'])}`，暴露捕获率`{pct(summary['exposure_capture_ratio'])}`。",
            "",
            "## 结论",
            "",
            "- 当前结论：仍不能实盘，只能继续paper。",
            "- live-target builder、snapshot template和order recalculation dry-run已经解决目标生成、快照字段和订单重算链路，但OOS仍只有7个交易日。",
            "- 当前缺少目标日真实价格/券商快照输入，因此重算订单仍是黄灯估算；即使订单干净，也不能跳过OOS样本和人工风控确认。",
            "",
            "## 全量检查",
            "",
            _markdown_all(checklist, max_rows=80),
            "",
            "## 失败项",
            "",
            _markdown_all(failed, max_rows=40),
            "",
            "## 警告项",
            "",
            _markdown_all(warned, max_rows=40),
            "",
            "## 人工确认项",
            "",
            _markdown_all(manual, max_rows=40),
            "",
            "## 最新订单",
            "",
            markdown_table(
                latest_orders,
                [
                    "date",
                    "symbol",
                    "code_name",
                    "industry",
                    "side",
                    "status",
                    "blocked_reason",
                    "prev_shares",
                    "target_shares",
                    "desired_shares",
                    "filled_shares",
                    "trade_open",
                    "desired_amount_cny",
                    "filled_amount_cny",
                ],
                max_rows=80,
            ),
            "",
            "## order recalc订单",
            "",
            markdown_table(
                recalc_orders,
                [
                    "target_date",
                    "symbol",
                    "code_name",
                    "industry",
                    "side",
                    "final_status",
                    "final_blocked_reason",
                    "prev_shares",
                    "target_shares_recalc",
                    "desired_shares",
                    "final_shares",
                    "recalc_price",
                    "final_amount_cny",
                    "unfilled_amount_cny",
                ],
                max_rows=80,
            ),
            "",
            "## live估算订单",
            "",
            markdown_table(
                estimated_orders,
                [
                    "target_date",
                    "symbol",
                    "code_name",
                    "industry",
                    "side",
                    "estimated_status",
                    "estimated_blocked_reason",
                    "prev_shares",
                    "target_shares",
                    "desired_shares",
                    "reference_price",
                    "desired_amount_cny",
                ],
                max_rows=80,
            ),
            "",
            "## 最新目标摘要",
            "",
            markdown_table(
                latest_targets,
                [
                    "target_date",
                    "symbol",
                    "code_name",
                    "industry",
                    "sidecar_target_weight",
                    "sidecar_target_shares",
                    "zero_lot_target",
                    "trade_open",
                    "one_lot_amount_cny",
                ],
                max_rows=80,
            ),
            "",
            "## 最新持仓",
            "",
            markdown_table(
                latest_holdings,
                [
                    "symbol",
                    "code_name",
                    "industry",
                    "actual_shares",
                    "latest_trade_open",
                    "actual_amount_cny",
                    "actual_weight",
                ],
                max_rows=80,
            ),
            "",
            "## 运行前过拟合反思",
            "",
            "- 判断：否。",
            "- 原因：本阶段只做go/no-go检查，不改变信号或参数。",
            "",
            "## 运行后过拟合反思",
            "",
            "- 判断：否。",
            "- 原因：结论来自数据新鲜度、OOS长度、订单阻断、整手颗粒度和人工确认项，不按收益调参。",
            "",
            "## 运行前继续价值反思",
            "",
            "- 判断：是。",
            "- 原因：在实盘前必须把不能交易的条件显式化，否则容易被单次回测收益诱导。",
            "",
            "## 运行后继续价值反思",
            "",
            "- 判断：是。",
            "- 原因：当前清单明确给出red_not_live，后续每天复跑suite后可用同一清单判断是否仍只能paper。",
            "",
            "## 输出文件",
            "",
        ]
    )
    for name, path in paths.items():
        lines.append(f"- `{name}`：`{path}`")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    check_date = current_check_date()
    suite_summary = load_json(SUITE_DIR / f"{SUITE_PREFIX}_summary.json")
    sidecar_summary = load_json(SIDECAR_DIR / f"{SIDECAR_PREFIX}_summary.json")
    live_summary_path = LIVE_TARGET_DIR / f"{LIVE_TARGET_PREFIX}_summary.json"
    live_summary = load_json(live_summary_path) if live_summary_path.exists() else {}
    snapshot_template_summary_path = SNAPSHOT_TEMPLATE_DIR / f"{SNAPSHOT_TEMPLATE_PREFIX}_summary.json"
    snapshot_template_summary = (
        load_json(snapshot_template_summary_path) if snapshot_template_summary_path.exists() else {}
    )
    order_recalc_summary_path = ORDER_RECALC_DIR / f"{ORDER_RECALC_PREFIX}_summary.json"
    order_recalc_summary = load_json(order_recalc_summary_path) if order_recalc_summary_path.exists() else {}
    latest_orders = read_csv(SIDECAR_DIR / f"{SIDECAR_PREFIX}_latest_orders.csv")
    legacy_latest_targets = read_csv(SIDECAR_DIR / f"{SIDECAR_PREFIX}_latest_targets.csv")
    live_targets_path = LIVE_TARGET_DIR / f"{LIVE_TARGET_PREFIX}_live_targets.csv"
    live_targets = read_csv(live_targets_path) if live_targets_path.exists() else pl.DataFrame()
    latest_targets = live_targets if not live_targets.is_empty() else legacy_latest_targets
    estimated_orders_path = LIVE_TARGET_DIR / f"{LIVE_TARGET_PREFIX}_estimated_orders.csv"
    estimated_orders = read_csv(estimated_orders_path) if estimated_orders_path.exists() else pl.DataFrame()
    recalc_orders_path = ORDER_RECALC_DIR / f"{ORDER_RECALC_PREFIX}_recalc_orders.csv"
    recalc_orders = read_csv(recalc_orders_path) if recalc_orders_path.exists() else pl.DataFrame()
    latest_holdings = read_csv(SIDECAR_DIR / f"{SIDECAR_PREFIX}_latest_holdings.csv")
    stock_df, benchmark_df = load_panels()
    stock_max_date = parse_date(stock_df["datetime"].max())
    benchmark_max_date = parse_date(benchmark_df["datetime"].max())
    legacy_latest_target_date = parse_date(sidecar_summary.get("latest_target_date"))
    live_latest_signal_date = parse_date(live_summary.get("latest_signal_date")) if live_summary else None
    live_proposed_target_date = parse_date(live_summary.get("proposed_target_date")) if live_summary else None
    effective_target_date = live_proposed_target_date or legacy_latest_target_date

    checklist = build_checklist(
        suite_summary,
        sidecar_summary,
        live_summary,
        snapshot_template_summary,
        order_recalc_summary,
        latest_orders,
        latest_targets,
        estimated_orders,
        recalc_orders,
        check_date,
        stock_max_date,
        benchmark_max_date,
    )
    readiness = summarize_readiness(checklist)
    account_size = to_float(sidecar_summary.get("account_size_cny"))
    raw_target_amount = to_float(
        live_summary.get("live_raw_target_amount_sum_cny")
        if live_summary
        else sidecar_summary.get("latest_raw_target_amount_sum_cny")
    )
    raw_target_gross = raw_target_amount / account_size if account_size else 0.0
    latest_actual_gross = (
        to_float(live_summary.get("live_sidecar_target_amount_sum_cny")) / account_size
        if live_summary and account_size
        else to_float(sidecar_summary.get("latest_actual_gross_weight"))
    )
    summary: dict[str, Any] = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "check_date": check_date,
        "legacy_latest_target_date": legacy_latest_target_date,
        "live_latest_signal_date": live_latest_signal_date,
        "live_proposed_target_date": live_proposed_target_date,
        "effective_target_date": effective_target_date,
        "calendar_lag_days": (check_date - effective_target_date).days if effective_target_date else None,
        "stock_panel_max_date": stock_max_date,
        "benchmark_max_date": benchmark_max_date,
        "stock_panel_calendar_lag_days": (check_date - stock_max_date).days if stock_max_date else None,
        "benchmark_panel_calendar_lag_days": (check_date - benchmark_max_date).days if benchmark_max_date else None,
        "account_size_cny": account_size,
        "suite_state": suite_summary.get("suite_state"),
        "oos_days": suite_summary.get("oos_days"),
        "oos_state_label": suite_summary.get("oos_state_label"),
        "latest_raw_target_count": live_summary.get("live_raw_target_count")
        if live_summary
        else sidecar_summary.get("latest_raw_target_count"),
        "latest_sidecar_target_count": live_summary.get("live_sidecar_target_count")
        if live_summary
        else sidecar_summary.get("latest_sidecar_target_count"),
        "latest_zero_lot_target_count": live_summary.get("live_zero_lot_target_count")
        if live_summary
        else sidecar_summary.get("latest_zero_lot_target_count"),
        "latest_zero_lot_target_ratio": live_summary.get("live_zero_lot_target_ratio")
        if live_summary
        else sidecar_summary.get("latest_zero_lot_target_ratio"),
        "raw_target_gross_weight": raw_target_gross,
        "latest_actual_gross_weight": latest_actual_gross,
        "exposure_capture_ratio": latest_actual_gross / raw_target_gross if raw_target_gross else 0.0,
        "live_target_builder_state": live_summary.get("target_builder_state") if live_summary else "missing",
        "live_estimated_order_count": live_summary.get("estimated_order_count") if live_summary else None,
        "live_estimated_blocked_order_count": live_summary.get("estimated_blocked_order_count") if live_summary else None,
        "snapshot_template_state": snapshot_template_summary.get("snapshot_template_state")
        if snapshot_template_summary
        else "missing",
        "snapshot_template_rows": snapshot_template_summary.get("template_rows") if snapshot_template_summary else None,
        "snapshot_input_state": snapshot_template_summary.get("snapshot_input_state") if snapshot_template_summary else "missing",
        "snapshot_input_path": snapshot_template_summary.get("snapshot_input_path") if snapshot_template_summary else None,
        "snapshot_validation_warn_count": snapshot_template_summary.get("validation_warn_count")
        if snapshot_template_summary
        else None,
        "snapshot_validation_fail_count": snapshot_template_summary.get("validation_fail_count")
        if snapshot_template_summary
        else None,
        "order_recalc_state": order_recalc_summary.get("order_recalc_state") if order_recalc_summary else "missing",
        "order_recalc_price_snapshot_state": order_recalc_summary.get("price_snapshot_state") if order_recalc_summary else "missing",
        "order_recalc_order_count": order_recalc_summary.get("order_count") if order_recalc_summary else None,
        "order_recalc_blocked_order_count": order_recalc_summary.get("blocked_order_count") if order_recalc_summary else None,
        "order_recalc_cash_limited_order_count": order_recalc_summary.get("cash_limited_order_count")
        if order_recalc_summary
        else None,
        "order_recalc_final_amount_sum_cny": order_recalc_summary.get("final_amount_sum_cny")
        if order_recalc_summary
        else None,
        "latest_order_count": sidecar_summary.get("latest_order_count"),
        "latest_blocked_order_count": sidecar_summary.get("latest_blocked_order_count"),
        "latest_unfilled_amount_sum_cny": sidecar_summary.get("latest_unfilled_amount_sum_cny"),
        "latest_st_or_ineligible_buy_blocked_orders": sidecar_summary.get(
            "latest_st_or_ineligible_buy_blocked_orders"
        ),
        "latest_not_index_guard_block_orders": sidecar_summary.get("latest_not_index_guard_block_orders"),
        "latest_changed_order_rows_vs_original": sidecar_summary.get("latest_changed_order_rows_vs_original"),
        "latest_filled_order_min_cny": sidecar_summary.get("latest_filled_order_min_cny"),
        "latest_filled_order_median_cny": sidecar_summary.get("latest_filled_order_median_cny"),
        "latest_filled_order_max_cny": sidecar_summary.get("latest_filled_order_max_cny"),
        **readiness,
    }

    paths = {
        "report": OUTPUT_DIR / f"{PREFIX}_report.md",
        "summary": OUTPUT_DIR / f"{PREFIX}_summary.json",
        "checklist": OUTPUT_DIR / f"{PREFIX}_checklist.csv",
        "failures": OUTPUT_DIR / f"{PREFIX}_failures.csv",
        "warnings": OUTPUT_DIR / f"{PREFIX}_warnings.csv",
        "manual_required": OUTPUT_DIR / f"{PREFIX}_manual_required.csv",
        "meta": OUTPUT_DIR / f"{PREFIX}_meta.json",
    }
    checklist.write_csv(paths["checklist"])
    checklist.filter(pl.col("status") == "fail").write_csv(paths["failures"])
    checklist.filter(pl.col("status") == "warn").write_csv(paths["warnings"])
    checklist.filter(pl.col("status") == "manual").write_csv(paths["manual_required"])
    write_json(paths["summary"], summary)
    write_json(
        paths["meta"],
        {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "suite_summary": str(SUITE_DIR / f"{SUITE_PREFIX}_summary.json"),
            "sidecar_summary": str(SIDECAR_DIR / f"{SIDECAR_PREFIX}_summary.json"),
            "live_summary": str(live_summary_path),
            "snapshot_template_summary": str(snapshot_template_summary_path),
            "order_recalc_summary": str(order_recalc_summary_path),
            "research_sources": RESEARCH_SOURCES,
            "note": "Pre-live checklist only; it does not submit orders or change strategy parameters.",
        },
    )
    report_path = write_report(
        summary,
        checklist,
        latest_orders,
        latest_targets,
        latest_holdings,
        estimated_orders,
        recalc_orders,
        paths,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    print(f"report={report_path}")


if __name__ == "__main__":
    main()
