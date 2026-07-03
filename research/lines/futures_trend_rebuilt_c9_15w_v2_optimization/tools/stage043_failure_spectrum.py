from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
import json
from pathlib import Path
import re
from typing import Any

import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[4]
LINE_ID = "futures_trend_rebuilt_c9_15w_v2_optimization"
STAGE = "Stage043"
MODEL_TAG = "stage043_failure_spectrum_v1"
OUTPUT_PREFIX = "rebuilt_c9_v2_stage043_failure_spectrum"

LINE_DIR = PROJECT_DIR / "research" / "lines" / LINE_ID
OUTPUT_ROOT = LINE_DIR / "outputs"
OUTPUT_DIR = OUTPUT_ROOT / "stage043_failure_spectrum"
STAGES_DIR = LINE_DIR / "stages"

INVENTORY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_inventory_{MODEL_TAG}.csv"
SPECTRUM_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_route_spectrum_{MODEL_TAG}.csv"
ACTION_QUEUE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_action_queue_{MODEL_TAG}.csv"
NO_GO_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_no_go_list_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

SOURCE_LINKS = {
    "deflated_sharpe_ratio": "https://www.pm-research.com/content/iijpormgmt/40/5/94",
    "backtest_overfitting_bayesian_review": "https://www.mdpi.com/2227-9091/9/1/18",
    "portfolio_optimization_dangers_backtesting": "https://portfoliooptimizationbook.com/book/8.3-dangers-backtesting.html",
    "pysystemtrade_backtesting": "https://github.com/pst-group/pysystemtrade/blob/develop/docs/backtesting.md",
}

ROUTE_CLASS_ORDER = [
    "rejected_existing_feature_or_shape",
    "data_required_or_external_state",
    "engineering_ready_not_signal",
    "candidate_needs_true_engine_or_user_approval",
    "diagnostic_or_attribution_only",
    "other",
]


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        result = float(value)
        if np.isnan(result) or np.isinf(result):
            return None
        return result
    if isinstance(value, (pd.Timestamp, datetime)):
        if pd.isna(value):
            return ""
        return value.isoformat()
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


def _as_dict(row: Mapping[str, Any] | pd.Series | dict[str, Any]) -> dict[str, Any]:
    if isinstance(row, pd.Series):
        return row.to_dict()
    return dict(row)


def _text(row: Mapping[str, Any] | pd.Series | dict[str, Any]) -> str:
    data = _as_dict(row)
    return " ".join(
        str(data.get(key, "") or "")
        for key in (
            "stage",
            "model_tag",
            "decision",
            "best_next_direction",
            "notes",
            "route_id",
        )
    ).lower()


def extract_stage_number(path_or_name: str | Path) -> int | None:
    text = str(path_or_name).replace("\\", "/")
    match = re.search(r"stage[_-]?0*([0-9]{1,4})", text, flags=re.I)
    if not match:
        return None
    return int(match.group(1))


def _to_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or pd.isna(value):
            return default
    except (TypeError, ValueError):
        pass
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def classify_decision(row: Mapping[str, Any] | pd.Series | dict[str, Any]) -> dict[str, Any]:
    data = _as_dict(row)
    text = _text(data)
    immediate = _to_int(data.get("immediate_strategy_candidate_count"), 0)

    candidate_tokens = ("has_", "candidates", "candidate", "need_true", "need_path", "need_guard", "quality_split")
    data_tokens = (
        "not_ready",
        "data_first",
        "external_data",
        "external_authorized",
        "data_contract",
        "no_accepted",
        "credentials",
        "permission",
        "not_continuous",
        "switch_source",
        "source_readiness",
        "tqsdk",
        "vendor",
        "endpoint",
        "replay",
        "cashflow",
        "cash_ledger",
        "inventory_no_local_rule_candidate",
        "schema",
        "coverage",
    )
    engineering_tokens = ("ready_for", "verified_ready", "target_covered", "no_gaps_ready")
    rejection_tokens = (
        "not_promoted",
        "not_goal",
        "no_stable",
        "no_candidate",
        "not_enough",
        "not_rule_ready",
        "not_rule_data",
        "not_signal",
        "keep_readonly",
        "not_direct",
    )
    diagnostic_tokens = ("attribution", "diagnostic", "inventory", "audit", "forensics")

    if immediate > 0:
        route_class = "candidate_needs_true_engine_or_user_approval"
        reason = "nonzero_immediate_candidate_count_requires_user_ab_gate"
    elif any(token in text for token in candidate_tokens) and any(token in text for token in ("need_true", "need_path", "need_guard", "quality_split", "has_stable", "has_pit")):
        route_class = "candidate_needs_true_engine_or_user_approval"
        reason = "candidate_language_but_no_immediate_strategy_candidate"
    elif any(token in text for token in engineering_tokens) and any(token in text for token in ("no_rule", "no_strategy_candidate", "not_signal")):
        route_class = "engineering_ready_not_signal"
        reason = "engineering_asset_ready_but_signal_rule_not_accepted"
    elif any(token in text for token in data_tokens):
        route_class = "data_required_or_external_state"
        reason = "decision_requires_external_or_schema_ready_data"
    elif any(token in text for token in rejection_tokens):
        route_class = "rejected_existing_feature_or_shape"
        reason = "existing_feature_shape_or_proxy_rejected"
    elif any(token in text for token in diagnostic_tokens):
        route_class = "diagnostic_or_attribution_only"
        reason = "attribution_or_inventory_stage_without_promotion"
    else:
        route_class = "other"
        reason = "unclassified_decision_text"

    data["route_class"] = route_class
    data["classify_reason"] = reason
    data["local_rescue_allowed"] = False
    data["strategy_rule_allowed_next"] = False
    return data


def iter_decision_files(output_root: Path = OUTPUT_ROOT) -> list[Path]:
    if not output_root.exists():
        return []
    return sorted(
        path
        for path in output_root.glob("**/*decision*.json")
        if "stage043_failure_spectrum" not in str(path)
    )


def parse_decision_file(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    stage_no = extract_stage_number(str(data.get("stage", ""))) or extract_stage_number(path)
    return {
        "stage": data.get("stage") or (f"Stage{stage_no:03d}" if stage_no is not None else ""),
        "stage_no": stage_no,
        "model_tag": data.get("model_tag", ""),
        "decision": data.get("decision", ""),
        "best_next_direction": data.get("best_next_direction", ""),
        "immediate_strategy_candidate_count": _to_int(data.get("immediate_strategy_candidate_count"), 0),
        "strategy_rule_created": bool(data.get("strategy_rule_created", False)),
        "official_live_strategy_changed": bool(data.get("official_live_strategy_changed", False)),
        "true_engine": bool(data.get("true_engine", False)),
        "ab_triggered": bool(data.get("ab_triggered", False)),
        "order_api_called": bool(data.get("order_api_called", False)),
        "send_order_api_called_count": _to_int(data.get("send_order_api_called_count"), 0),
        "cancel_order_api_called_count": _to_int(data.get("cancel_order_api_called_count"), 0),
        "ctp_connected": bool(data.get("ctp_connected", False)),
        "decision_path": str(path.relative_to(PROJECT_DIR)),
    }


def build_decision_inventory(paths: list[Path] | None = None) -> pd.DataFrame:
    paths = paths if paths is not None else iter_decision_files()
    rows: list[dict[str, Any]] = []
    for path in paths:
        try:
            rows.append(classify_decision(parse_decision_file(path)))
        except Exception as exc:
            rows.append(
                classify_decision(
                    {
                        "stage": "",
                        "stage_no": extract_stage_number(path),
                        "model_tag": "",
                        "decision": "parse_failed",
                        "best_next_direction": "",
                        "immediate_strategy_candidate_count": 0,
                        "strategy_rule_created": False,
                        "official_live_strategy_changed": False,
                        "true_engine": False,
                        "ab_triggered": False,
                        "order_api_called": False,
                        "send_order_api_called_count": 0,
                        "cancel_order_api_called_count": 0,
                        "ctp_connected": False,
                        "decision_path": str(path.relative_to(PROJECT_DIR)),
                        "notes": f"{type(exc).__name__}:{exc}",
                    }
                )
            )
    frame = pd.DataFrame(rows)
    if frame.empty:
        return pd.DataFrame(
            columns=[
                "stage",
                "stage_no",
                "model_tag",
                "decision",
                "best_next_direction",
                "immediate_strategy_candidate_count",
                "route_class",
                "classify_reason",
                "decision_path",
            ]
        )
    frame["stage_no"] = pd.to_numeric(frame["stage_no"], errors="coerce").astype("Int64")
    return frame.sort_values(["stage_no", "decision_path"], na_position="last").reset_index(drop=True)


def summarize_spectrum(inventory: pd.DataFrame) -> pd.DataFrame:
    if inventory.empty:
        return pd.DataFrame(
            [
                {
                    "route_class": "none",
                    "stage_count": 0,
                    "min_stage": None,
                    "max_stage": None,
                    "immediate_strategy_candidate_count": 0,
                    "strategy_rule_created_count": 0,
                    "true_engine_count": 0,
                    "order_api_called_count": 0,
                    "ctp_connected_count": 0,
                    "representative_decisions": "",
                }
            ]
        )

    rows: list[dict[str, Any]] = []
    for route_class, group in inventory.groupby("route_class", sort=False):
        stage_numbers = pd.to_numeric(group["stage_no"], errors="coerce").dropna().astype(int)
        rows.append(
            {
                "route_class": route_class,
                "stage_count": int(len(group)),
                "min_stage": int(stage_numbers.min()) if not stage_numbers.empty else None,
                "max_stage": int(stage_numbers.max()) if not stage_numbers.empty else None,
                "immediate_strategy_candidate_count": int(group["immediate_strategy_candidate_count"].fillna(0).astype(int).sum()),
                "strategy_rule_created_count": int(group["strategy_rule_created"].astype(bool).sum()) if "strategy_rule_created" in group else 0,
                "true_engine_count": int(group["true_engine"].astype(bool).sum()) if "true_engine" in group else 0,
                "order_api_called_count": int(group["order_api_called"].astype(bool).sum()) if "order_api_called" in group else 0,
                "ctp_connected_count": int(group["ctp_connected"].astype(bool).sum()) if "ctp_connected" in group else 0,
                "representative_decisions": "; ".join(group["decision"].dropna().astype(str).head(5)),
            }
        )
    result = pd.DataFrame(rows)
    result["sort_key"] = result["route_class"].map({name: idx for idx, name in enumerate(ROUTE_CLASS_ORDER)}).fillna(999).astype(int)
    return result.sort_values(["sort_key", "min_stage"], na_position="last").drop(columns=["sort_key"]).reset_index(drop=True)


def _count_matching(spectrum: pd.DataFrame, *needles: str) -> int:
    if spectrum.empty:
        return 0
    text = " ".join(spectrum.astype(str).agg(" ".join, axis=1).str.lower().tolist())
    return int(sum(1 for needle in needles if needle.lower() in text))


def build_route_queue(spectrum: pd.DataFrame) -> pd.DataFrame:
    rows = [
        {
            "priority": 1,
            "route_id": "authorized_orderflow_depth_mbo_or_mbp10",
            "route_type": "new_pit_signal_source",
            "requires_external_state": True,
            "strategy_rule_allowed": False,
            "required_data_contract": "authorized PIT depth/orderflow with exchange timestamp, symbol, bid/ask depth, queue or MBP10 fields, source hash, publish/receive time and continuous target-pool calendar",
            "expected_use": "entry quality confirmation after schema/hash/PIT validation",
            "forbidden_shortcut": "do_not_use_minute_ohlcv_or_current_oi_as_orderflow_proxy",
            "evidence_stage_count_hint": _count_matching(spectrum, "orderflow", "depth", "mbo", "mbp"),
            "next_action": "obtain_or_generate_accepted_schema_ready_depth_dataset_before_any_rule_test",
        },
        {
            "priority": 2,
            "route_id": "vendor_option_chain_iv_skew",
            "route_type": "new_pit_signal_source",
            "requires_external_state": True,
            "strategy_rule_allowed": False,
            "required_data_contract": "TqSdk/vendor commodity option chain history with IV, delta, skew, open interest, volume, PIT timestamp, source hash and coverage for target pool including jd/lh/fu/jm where available",
            "expected_use": "volatility stress and skew confirmation after coverage audit",
            "forbidden_shortcut": "do_not_treat_akshare_sparse_probe_or_tqsdk_install_state_as_rule_data",
            "evidence_stage_count_hint": _count_matching(spectrum, "option", "iv", "skew", "tqsdk", "vendor"),
            "next_action": "configure_authorized_vendor_credentials_or_import_hashed_history_then_repeat_readiness",
        },
        {
            "priority": 3,
            "route_id": "broker_same_source_replay",
            "route_type": "execution_truth_dataset",
            "requires_external_state": True,
            "strategy_rule_allowed": False,
            "required_data_contract": "same-source signal->order->fill->position-change replay with signal/order/fill/position timestamps, symbol, side, price, volume and enough coverage days",
            "expected_use": "slippage, latency, partial fill and execution safety calibration",
            "forbidden_shortcut": "do_not_use_research_trade_events_or_protected_logs_as_ai_alpha_input",
            "evidence_stage_count_hint": _count_matching(spectrum, "replay", "broker", "same_source"),
            "next_action": "import_accepted_production_replay_or_stop_execution_calibration_route",
        },
        {
            "priority": 4,
            "route_id": "actual_cashflow_ledger_account_governance",
            "route_type": "account_governance_dataset",
            "requires_external_state": True,
            "strategy_rule_allowed": False,
            "required_data_contract": "broker or bank cashflow ledger with account, cash_flow_id, flow_type, amount, equity before/after, source hash and export time",
            "expected_use": "capacity, reserve, capital call and liquidity governance only",
            "forbidden_shortcut": "do_not_count_external_deposits_or_withdrawals_as_strategy_return_or_ai_alpha",
            "evidence_stage_count_hint": _count_matching(spectrum, "cashflow", "cash_ledger", "cash"),
            "next_action": "import_real_cash_ledger_only_if_account_capacity_governance_is_the_next_question",
        },
        {
            "priority": 5,
            "route_id": "new_oos_forward_watch",
            "route_type": "validation_process",
            "requires_external_state": True,
            "strategy_rule_allowed": False,
            "required_data_contract": "freeze monthly AI pools, input hashes, shadow outputs, current curves and all rejected trial records before future observations arrive",
            "expected_use": "measure live or forward out-of-sample decay without additional in-sample rescue",
            "forbidden_shortcut": "do_not_relabel_rebuilt_outputs_as_deleted_pre_cleanup_exact_baseline",
            "evidence_stage_count_hint": _count_matching(spectrum, "not_promoted", "not_goal", "no_candidate"),
            "next_action": "freeze_forward_watch_bundle_and_wait_for_unseen_sessions_before_promotion_claims",
        },
        {
            "priority": 6,
            "route_id": "independent_sleeve_from_separate_research_line",
            "route_type": "structural_diversifier",
            "requires_external_state": False,
            "strategy_rule_allowed": False,
            "required_data_contract": "separate strategy line with its own entry logic, costs, positions, margin, OOS and no parameter search against current C9 left-tail dates",
            "expected_use": "future combination or A/B only after independent validation",
            "forbidden_shortcut": "do_not_mix_current_failed_C9_thresholds_into_a_new_sleeve",
            "evidence_stage_count_hint": _count_matching(spectrum, "sleeve", "xsmom", "blend"),
            "next_action": "only_continue_if_a_separate_line_produces_a_stable_independent_candidate",
        },
    ]
    return pd.DataFrame(rows).sort_values("priority").reset_index(drop=True)


def build_no_go_list(inventory: pd.DataFrame) -> pd.DataFrame:
    rows = [
        {
            "no_go_id": "current_visible_ai_minute_oi_member_rank_and_account_threshold_rescue",
            "scope": "local_field_parameter_rescue",
            "evidence": "Stage002-036 and upstream Stage081 repeatedly rejected current visible AI, minute, OI, member-rank, account-threshold and risk-multiplier shapes",
            "forbidden_next_action": "do_not_scan_topN_R_multiplier_risk_floor_month_product_direction_or_threshold_variants",
        },
        {
            "no_go_id": "option_iv_skew_sparse_probe_or_install_state_as_signal",
            "scope": "option_route_shortcut",
            "evidence": "Stage037-040 found function probes, sparse AKShare coverage, DCE endpoint failures and missing TqSdk credentials, but no schema-ready continuous PIT option chain",
            "forbidden_next_action": "do_not_convert_single_day_or_sparse_option_probe_into_AI_pool_or_add_risk_rule",
        },
        {
            "no_go_id": "research_trade_events_or_protected_live_logs_as_alpha",
            "scope": "execution_replay_shortcut",
            "evidence": "Stage041 found no accepted same-source broker replay; protected logs remain evidence, not training features",
            "forbidden_next_action": "do_not_train_or_select_AI_pool_from_research_trade_events_execution_ledger_or_smoke_logs",
        },
        {
            "no_go_id": "external_cashflow_strategy_goal_credit",
            "scope": "account_cashflow_shortcut",
            "evidence": "Stage042 found no accepted cashflow ledger and explicitly disallowed external deposits/withdrawals from strategy objective credit",
            "forbidden_next_action": "do_not_use_deposits_withdrawals_reserve_bucket_or_cash_overlay_to_claim_strategy_return_goal",
        },
        {
            "no_go_id": "functional_rebuild_as_deleted_exact_baseline",
            "scope": "baseline_claim_boundary",
            "evidence": "Rebuild evidence supports current rebuilt benchmark, not byte-for-byte deleted pre-cleanup official pool equivalence",
            "forbidden_next_action": "do_not_claim_historical_1to1_restoration_without_pre_cleanup_hashes_or_backup_snapshots",
        },
    ]
    result = pd.DataFrame(rows)
    if not inventory.empty:
        result["supporting_stage_count"] = [
            int(inventory["decision"].astype(str).str.contains("not_promoted|not_goal|no_stable|no_candidate", regex=True).sum()),
            int(inventory["decision"].astype(str).str.contains("option|akshare|dce|tqsdk|not_continuous|not_ready", regex=True, case=False).sum()),
            int(inventory["decision"].astype(str).str.contains("replay|broker|same_source", regex=True, case=False).sum()),
            int(inventory["decision"].astype(str).str.contains("cashflow|cash_ledger|cash", regex=True, case=False).sum()),
            int(len(inventory)),
        ]
    else:
        result["supporting_stage_count"] = 0
    return result


def make_stage043_decision(spectrum: pd.DataFrame, queue: pd.DataFrame) -> dict[str, Any]:
    if spectrum.empty:
        class_counts: dict[str, int] = {}
        immediate = 0
        strategy_rule_created_count = 0
        true_engine_count = 0
        order_api_count = 0
        ctp_count = 0
    else:
        if "route_class" in spectrum.columns and "stage_count" in spectrum.columns:
            class_counts = {
                str(row["route_class"]): _to_int(row["stage_count"], 0)
                for row in spectrum[["route_class", "stage_count"]].to_dict("records")
            }
        else:
            class_counts = spectrum["route_class"].value_counts().to_dict() if "route_class" in spectrum.columns else {}
        immediate = int(spectrum["immediate_strategy_candidate_count"].fillna(0).astype(int).sum()) if "immediate_strategy_candidate_count" in spectrum.columns else 0
        strategy_rule_created_count = int(spectrum["strategy_rule_created_count"].fillna(0).astype(int).sum()) if "strategy_rule_created_count" in spectrum.columns else 0
        if "strategy_rule_created" in spectrum.columns:
            strategy_rule_created_count += int(spectrum["strategy_rule_created"].astype(bool).sum())
        true_engine_count = int(spectrum["true_engine_count"].fillna(0).astype(int).sum()) if "true_engine_count" in spectrum.columns else 0
        if "true_engine" in spectrum.columns:
            true_engine_count += int(spectrum["true_engine"].astype(bool).sum())
        order_api_count = int(spectrum["order_api_called_count"].fillna(0).astype(int).sum()) if "order_api_called_count" in spectrum.columns else 0
        if "order_api_called" in spectrum.columns:
            order_api_count += int(spectrum["order_api_called"].astype(bool).sum())
        ctp_count = int(spectrum["ctp_connected_count"].fillna(0).astype(int).sum()) if "ctp_connected_count" in spectrum.columns else 0
        if "ctp_connected" in spectrum.columns:
            ctp_count += int(spectrum["ctp_connected"].astype(bool).sum())

    local_rescue_allowed = bool(immediate > 0)
    if local_rescue_allowed:
        decision = "stage043_failure_spectrum_has_candidate_requires_ab_gate"
        best_next_direction = "freeze_candidate_and_request_user_ab_decision"
    else:
        decision = "stage043_failure_spectrum_requires_new_data_or_forward_oos_no_local_rescue"
        best_next_direction = "obtain_new_schema_ready_pit_or_execution_data_or_freeze_forward_oos_watch"

    return {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().replace(microsecond=0).isoformat(),
        "decision": decision,
        "best_next_direction": best_next_direction,
        "rejected_count": int(class_counts.get("rejected_existing_feature_or_shape", 0)),
        "data_required_count": int(class_counts.get("data_required_or_external_state", 0)),
        "engineering_ready_not_signal_count": int(class_counts.get("engineering_ready_not_signal", 0)),
        "candidate_needs_true_engine_or_user_approval_count": int(class_counts.get("candidate_needs_true_engine_or_user_approval", 0)),
        "route_class_counts": {str(key): int(value) for key, value in class_counts.items()},
        "action_queue_count": int(len(queue)),
        "immediate_strategy_candidate_count": int(immediate),
        "local_rescue_allowed": bool(local_rescue_allowed),
        "strategy_rule_created": False,
        "strategy_rule_created_count": int(strategy_rule_created_count),
        "official_live_strategy_changed": False,
        "true_engine": False,
        "true_engine_count": int(true_engine_count),
        "ab_triggered": False,
        "order_api_called": False,
        "order_api_called_count": int(order_api_count),
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "ctp_connected": False,
        "ctp_connected_count": int(ctp_count),
        "source_links": SOURCE_LINKS,
        "external_research_judgment": (
            "Deflated Sharpe Ratio 和 backtest overfitting 资料都指向同一个纪律：必须记录所有试验，"
            "不要只展示胜出结果；Portfolio Optimization 的 backtesting danger 章节也把多重测试/p-hacking 列为核心风险。"
            "因此 Stage043 的判断是，当前没有新 PIT/执行/账户真数据时，继续在已失败本地字段上救参比暂停更容易制造假阳性。"
        ),
        "overfit_reflection_before": "否。本阶段不挑参数、不跑新曲线，只把已完成试验的失败和数据缺口归档。",
        "overfit_reflection_after": "否。输出明确禁止在已失败字段上局部救参，降低多重测试假阳性风险。",
        "continue_value_before": "有。Stage040-042 后需要把外部数据路线、禁做清单和 forward watch 边界固化，避免继续消耗在低价值救参上。",
        "continue_value_after": (
            "有但条件化。若没有授权 orderflow/depth、vendor 期权链、broker replay 或真实现金账本，"
            "本线应转为冻结/forward OOS；若拿到新数据，再按 action queue 从数据合同开始。"
        ),
    }


def write_report(inventory: pd.DataFrame, spectrum: pd.DataFrame, queue: pd.DataFrame, no_go: pd.DataFrame, decision: dict[str, Any]) -> None:
    inventory_cols = [
        "stage",
        "stage_no",
        "decision",
        "best_next_direction",
        "route_class",
        "classify_reason",
        "immediate_strategy_candidate_count",
        "decision_path",
    ]
    lines = [
        "# Stage043 失败谱系与下一步数据需求清单",
        "",
        f"- line_id：`{LINE_ID}`",
        f"- 记录时间：{decision['generated_at']}",
        f"- 决策：`{decision['decision']}`",
        "- 阶段性质：只读决策控制；不回测、不改策略、不连接 CTP、不调用订单 API。",
        "",
        "## 外部调研与判断",
        "",
        "- Deflated Sharpe Ratio/多重测试资料提示：如果只展示胜出回测而不记录所有试验，会系统性抬高假阳性概率。",
        "- Backtest overfitting 综述和 Portfolio Optimization 的 backtesting danger 资料把 p-hacking/selection bias 视为策略研究的核心风险。",
        "- pysystemtrade backtesting 文档强调可复验 backtest 流程；对应到本线就是每个阶段要留 decision、输入和失败原因。",
        "- 我的判断：当前本地可见字段已经被多轮反证；没有新 PIT/执行真数据时，继续救参的预期价值低于冻结并准备数据合同。",
        "",
        "## Route Spectrum",
        "",
        _md_table(spectrum),
        "",
        "## Action Queue",
        "",
        _md_table(queue),
        "",
        "## No-Go List",
        "",
        _md_table(no_go),
        "",
        "## Decision Inventory",
        "",
        _md_table(inventory[inventory_cols], max_rows=80) if not inventory.empty else "_无记录_",
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


def write_stage_record(spectrum: pd.DataFrame, queue: pd.DataFrame, no_go: pd.DataFrame, decision: dict[str, Any]) -> Path:
    STAGES_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    path = STAGES_DIR / f"{timestamp}_stage043_failure_spectrum.md"
    text = f"""# Stage043 失败谱系与下一步数据需求清单

- line_id：`{LINE_ID}`
- 当前模式：day
- 记录时间：{decision['generated_at']}
- 阶段性质：只读决策控制；不回测、不改策略、不连接 CTP、不调用下单
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：Deflated Sharpe Ratio、backtest overfitting 综述、Portfolio Optimization backtesting dangers、pysystemtrade backtesting。
- 我的判断：当前本地字段的多阶段优化已经进入高假阳性风险区；合理下一步不是继续救参，而是补授权 PIT/执行真数据、冻结 forward OOS，或转完全独立策略线。

## 本次变更

- 新增脚本：`research/lines/{LINE_ID}/tools/stage043_failure_spectrum.py`
- 新增测试：`tests/test_rebuilt_c9_v2_stage043_failure_spectrum.py`
- 新增参数：无
- 修改参数：无正式策略参数修改
- 删除参数：无

## 结果

- decision：`{decision['decision']}`
- best_next_direction：`{decision['best_next_direction']}`
- rejected_count：`{decision['rejected_count']}`
- data_required_count：`{decision['data_required_count']}`
- engineering_ready_not_signal_count：`{decision['engineering_ready_not_signal_count']}`
- candidate_needs_true_engine_or_user_approval_count：`{decision['candidate_needs_true_engine_or_user_approval_count']}`
- action_queue_count：`{decision['action_queue_count']}`
- local_rescue_allowed：`{decision['local_rescue_allowed']}`
- immediate_strategy_candidate_count：`{decision['immediate_strategy_candidate_count']}`
- 策略变更：`False`
- true engine：`False`
- order API：`0`
- CTP：`False`

## Route Spectrum

{_md_table(spectrum)}

## Action Queue

{_md_table(queue)}

## No-Go List

{_md_table(no_go)}

## 过拟合反思

- 运行前判断：{decision['overfit_reflection_before']}
- 运行后判断：{decision['overfit_reflection_after']}

## 继续价值反思

- 运行前判断：{decision['continue_value_before']}
- 运行后判断：{decision['continue_value_after']}

## 输出文件

- decision_inventory：`{INVENTORY_PATH}`
- route_spectrum：`{SPECTRUM_PATH}`
- action_queue：`{ACTION_QUEUE_PATH}`
- no_go_list：`{NO_GO_PATH}`
- decision：`{DECISION_PATH}`
- report：`{REPORT_PATH}`
"""
    path.write_text(text, encoding="utf-8")
    return path


def run() -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    inventory = build_decision_inventory()
    spectrum = summarize_spectrum(inventory)
    queue = build_route_queue(spectrum)
    no_go = build_no_go_list(inventory)
    decision = make_stage043_decision(spectrum, queue)

    write_report(inventory, spectrum, queue, no_go, decision)
    stage_record = write_stage_record(spectrum, queue, no_go, decision)

    inventory.to_csv(INVENTORY_PATH, index=False, encoding="utf-8-sig")
    spectrum.to_csv(SPECTRUM_PATH, index=False, encoding="utf-8-sig")
    queue.to_csv(ACTION_QUEUE_PATH, index=False, encoding="utf-8-sig")
    no_go.to_csv(NO_GO_PATH, index=False, encoding="utf-8-sig")
    decision["outputs"] = {
        "decision_inventory": str(INVENTORY_PATH),
        "route_spectrum": str(SPECTRUM_PATH),
        "action_queue": str(ACTION_QUEUE_PATH),
        "no_go_list": str(NO_GO_PATH),
        "decision": str(DECISION_PATH),
        "report": str(REPORT_PATH),
        "stage_record": str(stage_record),
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    return decision


if __name__ == "__main__":
    run()
