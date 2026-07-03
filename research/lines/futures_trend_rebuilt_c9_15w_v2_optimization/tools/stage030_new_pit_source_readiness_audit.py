from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[4]
LINE_ID = "futures_trend_rebuilt_c9_15w_v2_optimization"
STAGE = "Stage030"
MODEL_TAG = "stage030_new_pit_source_readiness_audit_v1"
OUTPUT_PREFIX = "rebuilt_c9_v2_stage030_new_pit_source_readiness_audit"

LINE_DIR = PROJECT_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage030_new_pit_source_readiness_audit"
STAGES_DIR = LINE_DIR / "stages"

ROUTE_READINESS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_route_readiness_{MODEL_TAG}.csv"
ACQUISITION_CONTRACT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_acquisition_contract_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (pd.Timestamp, datetime)):
        if pd.isna(value):
            return ""
        return value.isoformat()
    if isinstance(value, (np.integer, np.floating)):
        return value.item()
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return value


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_无记录_"
    data = frame.head(max_rows).copy() if max_rows else frame.copy()
    return data.to_markdown(index=False)


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or pd.isna(value):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_bool(value: Any) -> bool:
    return bool(_as_int(value, 0))


def classify_new_pit_route(route: dict[str, Any] | pd.Series) -> dict[str, Any]:
    data = dict(route)
    route_id = str(data.get("route_id", ""))
    family = str(data.get("family", ""))
    local_rule_coverage_count = _as_int(data.get("local_rule_coverage_count"), -1)
    required_decision_count = _as_int(data.get("required_decision_count"), 0)
    local_historical_rows = _as_int(data.get("local_historical_rows"), -1)
    smoke_ready_sources = _as_int(data.get("smoke_backfill_ready_source_count"), 0)

    authorized_history = _as_bool(data.get("authorized_history_available"))
    full_history_ready = _as_bool(data.get("full_history_ready"))
    right_tail_guard_passed = _as_bool(data.get("right_tail_guard_passed"))
    local_contract_history_available = _as_bool(data.get("local_contract_history_available"))
    sdk_calc_available = _as_bool(data.get("sdk_calc_available"))
    prior_route_refuted = _as_bool(data.get("prior_route_refuted"))
    broker_replay_rows = _as_int(data.get("broker_replay_rows"), -1)
    requires_standalone_oos = _as_bool(data.get("requires_standalone_oos"))
    standalone_oos_pass = _as_bool(data.get("standalone_oos_pass"))

    reasons: list[str] = []
    if local_rule_coverage_count == 0 and required_decision_count > 0:
        reasons.append("rule_coverage_zero")
    if not authorized_history:
        reasons.append("no_authorized_history")
    if not right_tail_guard_passed:
        reasons.append("right_tail_guard_missing")
    if sdk_calc_available and (local_historical_rows == 0 or not local_contract_history_available):
        reasons.append("no_historical_option_chain")
    if broker_replay_rows == 0:
        reasons.append("no_broker_execution_replay")
    if smoke_ready_sources > 0 and not full_history_ready:
        reasons.append("smoke_ready_but_not_full_history")
    if prior_route_refuted:
        reasons.append("prior_route_refuted_no_param_rescue")
    if requires_standalone_oos and not standalone_oos_pass:
        reasons.append("no_standalone_oos_proof")

    if "options" in family or "iv" in route_id:
        if sdk_calc_available and (local_historical_rows == 0 or not local_contract_history_available):
            status = "needs_pit_history_acquisition"
            action = "build_pit_option_chain_history_before_signal_audit"
            priority = 65
        else:
            status = "external_data_required"
            action = "acquire_authorized_history_before_strategy_rule"
            priority = 55
    elif "broker" in route_id and broker_replay_rows == 0:
        status = "broker_replay_required"
        action = "import_broker_or_production_execution_replay_first"
        priority = 68
    elif local_rule_coverage_count == 0 or not authorized_history:
        status = "external_data_required"
        action = "acquire_authorized_history_before_strategy_rule"
        priority = 70 if "orderflow" in family or "microstructure" in family else 55
    elif smoke_ready_sources > 0 and not full_history_ready:
        status = "data_engineering_only"
        action = "finish_full_history_raw_manifest_before_signal_audit"
        priority = 50
    elif prior_route_refuted:
        status = "rejected_existing_cache_no_rule"
        action = "do_not_continue_existing_cache_param_rescue"
        priority = 0
    elif requires_standalone_oos and not standalone_oos_pass:
        status = "design_spec_required"
        action = "define_independent_sleeve_and_prove_standalone_oos_first"
        priority = 45
    elif authorized_history and full_history_ready and right_tail_guard_passed:
        status = "eligible_for_predeclared_signal_audit"
        action = "freeze_one_low_degree_hypothesis_then_readonly_audit"
        priority = 80
    else:
        status = "diagnostic_only"
        action = "keep_as_evidence_not_strategy"
        priority = 20

    result = dict(data)
    result["route_status"] = status
    result["recommended_next_action"] = action
    result["priority_score"] = int(priority)
    result["blocking_reasons"] = ",".join(list(dict.fromkeys(reasons)))
    result["rule_candidate_allowed"] = bool(status == "eligible_for_predeclared_signal_audit")
    result["true_engine_allowed"] = False
    result["ab_allowed"] = False
    return result


def make_readiness_decision(routes: pd.DataFrame) -> dict[str, Any]:
    data = routes.copy()
    immediate = data[data["rule_candidate_allowed"].astype(bool)]
    acquisition = data[
        data["route_status"].astype(str).isin(
            ["external_data_required", "needs_pit_history_acquisition", "broker_replay_required", "data_engineering_only"]
        )
    ]
    top = (
        data.sort_values(["priority_score", "route_id"], ascending=[False, True]).head(1).to_dict("records")
        if not data.empty
        else []
    )

    if immediate.empty:
        decision = "stage030_new_pit_routes_data_first_no_strategy_candidate"
        best_next_direction = "authorized_orderflow_or_options_iv_history_or_broker_replay"
    else:
        decision = "stage030_has_new_pit_route_for_readonly_signal_audit"
        best_next_direction = str(immediate.sort_values("priority_score", ascending=False).iloc[0]["route_id"])

    return {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().replace(microsecond=0).isoformat(),
        "decision": decision,
        "best_next_direction": best_next_direction,
        "route_count": int(len(data)),
        "immediate_strategy_candidate_count": int(len(immediate)),
        "acquisition_route_count": int(len(acquisition)),
        "blocked_route_count": int((~data["rule_candidate_allowed"].astype(bool)).sum()),
        "acquisition_manifest_required": bool(immediate.empty and not acquisition.empty),
        "top_route": top[0] if top else {},
        "strategy_changed": False,
        "official_live_strategy_changed": False,
        "true_engine": False,
        "order_api_called": False,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "ctp_connected": False,
        "external_research_judgment": (
            "TqSdk and vn.py can express option IV/Greeks and tick/depth data, while orderflow/MBO style data "
            "is the right information layer for microstructure. The current repo evidence still lacks authorized "
            "full-history option chains, orderflow/depth or production execution replay, so Stage030 remains data-first."
        ),
        "overfit_reflection_before": (
            "否。Stage030 只审计新 PIT 数据源合同，不新增规则、不按收益窗口调参。"
        ),
        "overfit_reflection_after": (
            "否。结论继续阻止用现有低信息源救参；若把缺失/ready 状态或单个 source 写成规则才是过拟合。"
        ),
        "continue_value_before": (
            "有。Stage029 后必须把新信息源路线拆成可执行的数据合同，否则无法进入真正的高质量信号研究。"
        ),
        "continue_value_after": (
            "有，但下一步价值来自补授权历史数据或生产执行回放，不来自当前本地文件继续挖阈值。"
        ),
    }


def build_route_inventory() -> pd.DataFrame:
    routes = [
        {
            "route_id": "authorized_orderflow_depth_mbo",
            "family": "microstructure_orderflow",
            "summary": "订单流/盘口/MBO 是正确信息层，但本地规则级覆盖仍为 0/219。",
            "local_rule_coverage_count": 0,
            "required_decision_count": 219,
            "authorized_history_available": 0,
            "right_tail_guard_passed": 0,
            "stage_refs": "futures_trend_c9_minrisk_highquality Stage103,Stage262",
        },
        {
            "route_id": "broker_or_production_execution_replay",
            "family": "execution_replay",
            "summary": "生产或券商执行回放可解决同源成交语义，但真实 replay rows 仍为 0。",
            "local_rule_coverage_count": 0,
            "required_decision_count": 219,
            "authorized_history_available": 0,
            "broker_replay_rows": 0,
            "right_tail_guard_passed": 0,
            "stage_refs": "futures_trend_c9_minrisk_highquality Stage261,Stage262",
        },
        {
            "route_id": "options_iv_skew",
            "family": "options_volatility",
            "summary": "TqSdk/OptionMaster 具备 IV/Greeks 计算能力，但本地没有 2018-2026 商品期权链 PIT 历史。",
            "sdk_calc_available": 1,
            "local_historical_rows": 0,
            "local_contract_history_available": 0,
            "authorized_history_available": 0,
            "right_tail_guard_passed": 0,
            "stage_refs": "TqSdk option docs, vn.py OptionMaster docs",
        },
        {
            "route_id": "official_raw_czce_member_warehouse_gfex_warehouse",
            "family": "official_raw_external_state",
            "summary": "CZCE member/warehouse 与 GFEX warehouse 小 manifest 通过，但尚非全历史、非策略候选。",
            "smoke_backfill_ready_source_count": 3,
            "full_history_ready": 0,
            "authorized_history_available": 1,
            "right_tail_guard_passed": 0,
            "stage_refs": "futures_trend_c9_minrisk_highquality Stage088,Stage089,Stage090",
        },
        {
            "route_id": "existing_member_rank_basis_warehouse_cache",
            "family": "existing_external_cache",
            "summary": "现有会员排名/基差/仓单 cache 覆盖和 provenance 不足，且简单信号已在旧恢复线反证。",
            "prior_route_refuted": 1,
            "authorized_history_available": 0,
            "right_tail_guard_passed": 0,
            "stage_refs": "rebuilt Stage045-047,Stage073,Stage079-081; c9_minrisk Stage087",
        },
        {
            "route_id": "independent_sleeve_separate_carry_or_range",
            "family": "independent_sleeve",
            "summary": "独立 sleeve 仍可能有价值，但必须先定义独立收益源并通过 standalone OOS。",
            "requires_standalone_oos": 1,
            "standalone_oos_pass": 0,
            "authorized_history_available": 1,
            "full_history_ready": 0,
            "right_tail_guard_passed": 0,
            "stage_refs": "Stage029 next direction",
        },
    ]
    return pd.DataFrame([classify_new_pit_route(route) for route in routes])


def build_acquisition_contract(routes: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for route in routes.to_dict("records"):
        route_id = str(route["route_id"])
        status = str(route["route_status"])
        if status not in {"external_data_required", "needs_pit_history_acquisition", "broker_replay_required", "data_engineering_only"}:
            continue
        if route_id == "options_iv_skew":
            fields = "trade_date, exchange_timestamp, underlying_contract, option_contract, strike, expiry, call_put, bid1, ask1, last, volume, open_interest, settlement, raw_hash, source_permission"
            coverage = "2018-01-01 to 2026-06-30 PIT option chain for products with listed options"
        elif "orderflow" in route_id:
            fields = "event_timestamp, exchange_timestamp, contract, bid/ask depth, last trade, volume/open_interest delta, raw_packet_hash, source_schema_version, source_permission"
            coverage = "all C9 entry/reentry decision windows, at least 219/219 historical decision events"
        elif "execution_replay" in route_id:
            fields = "decision_id, signal_time, order_time, exchange_order_id, price, volume, direction, offset, fill_time, queue/status events, raw_log_hash"
            coverage = "broker or production execution replay for all official C9 decision/fill events"
        else:
            fields = "publish_date, source_url, raw_payload_path, raw_hash, parsed_schema_hash, product, contract_or_symbol, value_fields, release_time_assumption"
            coverage = "full PIT history covering 2018-01-01 to 2026-06-30, not just annual or small manifest probes"
        rows.append(
            {
                "route_id": route_id,
                "route_status": status,
                "required_fields": fields,
                "minimum_coverage": coverage,
                "first_allowed_research_after_delivery": "readiness_audit_then_predeclared_readonly_signal_audit",
                "forbidden_shortcut": "do_not_use_ready_missing_status_or_single_source_as_trading_rule",
            }
        )
    return pd.DataFrame(rows)


def _write_report(decision: dict[str, Any], routes: pd.DataFrame, contract: pd.DataFrame) -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Stage030 新 PIT 数据源 readiness 审计",
        "",
        "## 结论",
        "",
        f"- 决策：`{decision['decision']}`",
        f"- 直接策略候选：`{decision['immediate_strategy_candidate_count']}`",
        f"- 需数据/工程先行路线：`{decision['acquisition_route_count']}`",
        "- 本阶段不回测、不写真引擎、不改策略、不触发订单 API。",
        "",
        "## 外部调研与判断",
        "",
        "- TqSdk 文档显示期权链、Greeks、隐含波动率和波动率曲面计算接口可用；但这只是计算能力，不是本地全历史 PIT 期权链。",
        "- vn.py/CTP schema 能表达 tick、盘口和期权数据；旧 minrisk 线 Stage103/262 证明本地没有规则级历史 orderflow/depth/replay 覆盖。",
        "- managed futures/carry/trend 资料支持独立 sleeve 或多信息源分散，但本线不能在已有 xsmom/OI/仓单/会员排名失败路线上继续救参。",
        "",
        "## 路线 readiness",
        "",
        _md_table(
            routes[
                [
                    "route_id",
                    "family",
                    "route_status",
                    "priority_score",
                    "rule_candidate_allowed",
                    "blocking_reasons",
                    "recommended_next_action",
                ]
            ]
        ),
        "",
        "## 数据合同",
        "",
        _md_table(contract),
        "",
        "## 过拟合反思",
        "",
        f"- 运行前：{decision['overfit_reflection_before']}",
        f"- 运行后：{decision['overfit_reflection_after']}",
        "",
        "## 继续价值反思",
        "",
        f"- 运行前：{decision['continue_value_before']}",
        f"- 运行后：{decision['continue_value_after']}",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_stage_record(decision: dict[str, Any]) -> Path:
    STAGES_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    path = STAGES_DIR / f"{timestamp}_stage030_new_pit_source_readiness_audit.md"
    lines = [
        "# Stage030 新 PIT 数据源 readiness 审计",
        "",
        f"- line_id：`{LINE_ID}`",
        "- 当前模式：day",
        f"- 记录时间：{decision['generated_at']}",
        "- 阶段性质：只读数据源 readiness 和 acquisition contract 审计；不回测、不改策略、不连接 CTP、不调用下单",
        "- 是否重要突破：否",
        "- 是否触发A/B：否",
        "",
        "## 外部调研与判断",
        "",
        "- 参考 TqSdk 期权文档、vn.py/OptionMaster 数据能力、订单流/MBO 与系统化趋势跟随资料。",
        "- 我的判断：期权 IV/skew、授权 orderflow/depth、生产执行回放是更高信息密度方向；当前仓库没有足够历史合同，所以先数据工程，不进入策略规则。",
        "",
        "## 本次变更",
        "",
        f"- 新增脚本：`{Path(__file__).relative_to(PROJECT_DIR)}`",
        "- 新增测试：`tests/test_rebuilt_c9_v2_stage030_new_pit_source_readiness.py`",
        "- 新增参数：无交易参数；仅新增路线 readiness 字段。",
        "- 修改参数：无",
        "- 删除参数：无",
        "",
        "## 结果",
        "",
        f"- route_count：`{decision['route_count']}`",
        f"- immediate_strategy_candidate_count：`{decision['immediate_strategy_candidate_count']}`",
        f"- acquisition_route_count：`{decision['acquisition_route_count']}`",
        f"- blocked_route_count：`{decision['blocked_route_count']}`",
        f"- 决策：`{decision['decision']}`",
        f"- 下一方向：`{decision['best_next_direction']}`",
        "",
        "## 输出文件",
        "",
        f"- route_readiness：`{ROUTE_READINESS_PATH}`",
        f"- acquisition_contract：`{ACQUISITION_CONTRACT_PATH}`",
        f"- decision：`{DECISION_PATH}`",
        f"- report：`{REPORT_PATH}`",
        "",
        "## 过拟合反思",
        "",
        f"- 运行前判断：{decision['overfit_reflection_before']}",
        f"- 运行后判断：{decision['overfit_reflection_after']}",
        "",
        "## 继续价值反思",
        "",
        f"- 运行前判断：{decision['continue_value_before']}",
        f"- 运行后判断：{decision['continue_value_after']}",
        "",
        "## 合入建议",
        "",
        "- 更新本线 `LINE.md`：是。",
        "- 更新 `research/registry.md`：是。",
        "- 追加根目录 `memory.md/back_log.md`：否，本阶段是数据合同闸门，不是正式候选或重要突破。",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    routes = build_route_inventory()
    contract = build_acquisition_contract(routes)
    decision = make_readiness_decision(routes)

    routes.to_csv(ROUTE_READINESS_PATH, index=False)
    contract.to_csv(ACQUISITION_CONTRACT_PATH, index=False)
    _write_report(decision, routes, contract)
    stage_record = _write_stage_record(decision)

    decision["outputs"] = {
        "route_readiness": ROUTE_READINESS_PATH,
        "acquisition_contract": ACQUISITION_CONTRACT_PATH,
        "decision": DECISION_PATH,
        "report": REPORT_PATH,
        "stage_record": stage_record,
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
