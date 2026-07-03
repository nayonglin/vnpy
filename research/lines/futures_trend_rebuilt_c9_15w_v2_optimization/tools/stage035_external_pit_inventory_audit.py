from __future__ import annotations

from datetime import datetime
import json
import os
from pathlib import Path
import re
from typing import Any

import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[4]
LINE_ID = "futures_trend_rebuilt_c9_15w_v2_optimization"
STAGE = "Stage035"
MODEL_TAG = "stage035_external_pit_inventory_audit_v1"
OUTPUT_PREFIX = "rebuilt_c9_v2_stage035_external_pit_inventory_audit"

LINE_DIR = PROJECT_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage035_external_pit_inventory_audit"
STAGES_DIR = LINE_DIR / "stages"

INVENTORY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_inventory_{MODEL_TAG}.csv"
ROUTE_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_route_summary_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

ORDERFLOW_RE = re.compile(
    r"(?<![a-z0-9])(orderflow|order_flow|depth|mbo|mbp|orderbook|order_book|tick|ticks|quote|quotes|lob)(?![a-z0-9])",
    re.I,
)
OPTION_RE = re.compile(
    r"(?<![a-z0-9])(option|options|iv|implied|skew|greek|greeks|vol_surface|volatility_surface)(?![a-z0-9])",
    re.I,
)
EXECUTION_RE = re.compile(
    r"(?<![a-z0-9])(execution|replay|broker|fill|fills|deal|deals|order|orders|trade_event|trade_events|position_change|position_changes|ctp|simnow)(?![a-z0-9])",
    re.I,
)
MINUTE_CACHE_RE = re.compile(r"(?<![a-z0-9])(downloaded_futures|minute_backtest|completed_minute_backtest)(?![a-z0-9])", re.I)

DATA_SUFFIXES = {
    ".csv",
    ".gz",
    ".parquet",
    ".feather",
    ".h5",
    ".hdf5",
    ".db",
    ".sqlite",
    ".json",
    ".jsonl",
    ".xls",
    ".xlsx",
}

ROUTE_IDS = [
    "authorized_orderflow_depth_mbo",
    "options_iv_skew",
    "broker_or_production_execution_replay",
    "minute_ohlcv_backtest_cache",
]

EXCLUDED_DIRS = {
    ".git",
    ".mamba-root",
    ".py311",
    ".pytest_cache",
    ".ruff_cache",
    "__pycache__",
    "node_modules",
    ".venv",
    "venv",
}


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


def _norm(path: Path | str) -> str:
    return str(path).replace("\\", "/").lstrip("./")


def _parts(path: Path | str) -> tuple[str, ...]:
    return tuple(part for part in Path(_norm(path)).parts if part not in {"."})


def _has_data_suffix(path: Path | str) -> bool:
    name = _norm(path).lower()
    if name.endswith(".csv.gz"):
        return True
    return Path(name).suffix in DATA_SUFFIXES


def _is_live_log(path: Path | str) -> bool:
    parts = _parts(path)
    normalized = _norm(path).lower()
    if len(parts) >= 2 and parts[0] == ".vntrader" and parts[1] == "log":
        return True
    if parts and parts[0] == "log":
        return True
    return "ctp_live" in normalized and normalized.endswith((".log", ".jsonl", ".txt"))


def _is_research_artifact(path: Path | str) -> bool:
    parts = _parts(path)
    if len(parts) >= 4 and parts[0] == "research" and parts[1] == "lines":
        return True
    if parts and parts[0] == "tests":
        return True
    if len(parts) >= 3 and parts[0] == "examples" and parts[1] == "portfolio_backtesting" and parts[2] == "backtest_outputs":
        return True
    return False


def _is_doc_or_code(path: Path | str) -> bool:
    parts = _parts(path)
    suffix = Path(_norm(path)).suffix.lower()
    return bool(parts and parts[0] in {"docs", "skills"}) or suffix in {".py", ".md", ".sh", ".yaml", ".yml", ".env"}


def _is_config_file(path: Path | str) -> bool:
    normalized = _norm(path).lower()
    suffix = Path(normalized).suffix
    name = Path(normalized).name
    return bool(
        suffix == ".env"
        or normalized.endswith(".local.env")
        or normalized.endswith(".example.env")
        or name.startswith("connect_") and suffix == ".json"
        or name in {"vt_setting.json", "vt_symbols.json"}
    )


def classify_path(path: Path, size_bytes: int = 0) -> dict[str, Any]:
    path_text = _norm(path)
    lower = path_text.lower()

    if MINUTE_CACHE_RE.search(path_text):
        route_id = "minute_ohlcv_backtest_cache"
    elif OPTION_RE.search(path_text):
        route_id = "options_iv_skew"
    elif ORDERFLOW_RE.search(path_text):
        route_id = "authorized_orderflow_depth_mbo"
    elif EXECUTION_RE.search(path_text):
        route_id = "broker_or_production_execution_replay"
    else:
        route_id = "unclassified"

    protected_live_log = _is_live_log(path)
    research_artifact = _is_research_artifact(path)
    doc_or_code = _is_doc_or_code(path)
    config_file = _is_config_file(path)
    data_like = _has_data_suffix(path)
    schema_validation_required = False
    rule_candidate_allowed = False
    true_engine_allowed = False

    if protected_live_log:
        asset_kind = "protected_live_log"
        route_id = "broker_or_production_execution_replay"
    elif config_file:
        asset_kind = "configuration_file"
    elif research_artifact:
        asset_kind = "research_artifact"
    elif route_id == "minute_ohlcv_backtest_cache":
        asset_kind = "minute_ohlcv_backtest_cache"
    elif route_id == "options_iv_skew" and doc_or_code:
        asset_kind = "code_capability_doc"
    elif route_id == "broker_or_production_execution_replay" and doc_or_code:
        asset_kind = "execution_sop_or_code"
    elif route_id == "authorized_orderflow_depth_mbo" and doc_or_code:
        asset_kind = "orderflow_code_or_doc"
    elif route_id == "authorized_orderflow_depth_mbo" and data_like:
        asset_kind = "potential_pit_data"
        schema_validation_required = True
    elif route_id == "options_iv_skew" and data_like:
        asset_kind = "potential_option_chain_history"
        schema_validation_required = True
    elif route_id == "broker_or_production_execution_replay" and data_like:
        asset_kind = "potential_same_source_replay_schema_candidate"
        schema_validation_required = True
    elif doc_or_code:
        asset_kind = "code_or_doc_hit"
    else:
        asset_kind = "unclassified_hit"

    if route_id not in ROUTE_IDS:
        route_id = "unclassified"

    return {
        "path": path_text,
        "route_id": route_id,
        "asset_kind": asset_kind,
        "size_bytes": int(size_bytes or 0),
        "data_like": bool(data_like),
        "protected_live_log": bool(protected_live_log),
        "research_artifact": bool(research_artifact),
        "schema_validation_required": bool(schema_validation_required),
        "rule_candidate_allowed": bool(rule_candidate_allowed),
        "true_engine_allowed": bool(true_engine_allowed),
        "order_api_allowed": False,
        "blocking_reason": _blocking_reason(route_id, asset_kind, lower),
    }


def _blocking_reason(route_id: str, asset_kind: str, path_lower: str) -> str:
    if asset_kind == "protected_live_log":
        return "protected_live_log_not_research_dataset"
    if asset_kind == "research_artifact":
        return "research_or_backtest_artifact_not_new_pit_source"
    if asset_kind == "minute_ohlcv_backtest_cache":
        return "minute_ohlcv_cache_already_refuted_for_microstructure_rule"
    if asset_kind in {"code_capability_doc", "execution_sop_or_code", "orderflow_code_or_doc", "code_or_doc_hit"}:
        return "code_or_doc_capability_not_historical_pit_data"
    if asset_kind == "potential_pit_data":
        return "schema_license_hash_and_coverage_validation_required"
    if asset_kind == "potential_option_chain_history":
        return "option_chain_schema_iv_skew_pit_validation_required"
    if asset_kind == "potential_same_source_replay_schema_candidate":
        return "same_source_signal_order_trade_join_validation_required"
    if "env" in path_lower:
        return "configuration_file_not_research_dataset"
    return "not_rule_ready"


def iter_matching_paths(root: Path = PROJECT_DIR) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    root = root.resolve()
    for current, dirs, files in os.walk(root):
        dirs[:] = [item for item in dirs if item not in EXCLUDED_DIRS]
        current_path = Path(current)
        for name in files:
            file_path = current_path / name
            try:
                relative = file_path.relative_to(root)
            except ValueError:
                relative = file_path
            relative_text = _norm(relative)
            if not _matches_interest(relative_text):
                continue
            try:
                size_bytes = file_path.stat().st_size
            except OSError:
                size_bytes = 0
            rows.append(classify_path(relative, size_bytes))
    return rows


def _matches_interest(path_text: str) -> bool:
    return bool(
        ORDERFLOW_RE.search(path_text)
        or OPTION_RE.search(path_text)
        or EXECUTION_RE.search(path_text)
        or MINUTE_CACHE_RE.search(path_text)
    )


def summarize_routes(rows: pd.DataFrame) -> pd.DataFrame:
    records: list[dict[str, Any]] = []
    if rows.empty:
        rows = pd.DataFrame(columns=["route_id", "asset_kind", "size_bytes", "schema_validation_required", "rule_candidate_allowed"])

    for route_id in ROUTE_IDS:
        data = rows[rows["route_id"].astype(str) == route_id].copy() if "route_id" in rows else pd.DataFrame()
        asset_kind = data["asset_kind"].astype(str) if not data.empty else pd.Series(dtype=str)
        potential_mask = asset_kind.isin(
            [
                "potential_pit_data",
                "potential_option_chain_history",
                "potential_same_source_replay_schema_candidate",
            ]
        )
        schema_count = int(data["schema_validation_required"].astype(bool).sum()) if not data.empty else 0
        rule_allowed_count = int(data["rule_candidate_allowed"].astype(bool).sum()) if not data.empty else 0
        accepted_same_source_replay_count = int((asset_kind == "accepted_same_source_replay").sum())

        if rule_allowed_count:
            route_status = "eligible_for_predeclared_signal_audit"
        elif schema_count:
            route_status = "local_schema_validation_required_no_rule"
        elif len(data):
            route_status = "local_evidence_not_rule_data"
        else:
            route_status = "not_found"

        blocking_reasons = sorted(set(data["blocking_reason"].dropna().astype(str))) if not data.empty else ["no_local_file_hit"]
        records.append(
            {
                "route_id": route_id,
                "route_status": route_status,
                "evidence_file_count": int(len(data)),
                "total_size_bytes": int(data["size_bytes"].sum()) if not data.empty else 0,
                "potential_schema_candidate_file_count": int(potential_mask.sum()) if not data.empty else 0,
                "accepted_same_source_replay_file_count": accepted_same_source_replay_count,
                "protected_live_log_count": int((asset_kind == "protected_live_log").sum()) if not data.empty else 0,
                "research_artifact_count": int((asset_kind == "research_artifact").sum()) if not data.empty else 0,
                "code_capability_doc_count": int(asset_kind.isin(["code_capability_doc", "execution_sop_or_code", "orderflow_code_or_doc", "code_or_doc_hit"]).sum())
                if not data.empty
                else 0,
                "minute_ohlcv_backtest_cache_count": int((asset_kind == "minute_ohlcv_backtest_cache").sum()) if not data.empty else 0,
                "schema_validation_required_count": schema_count,
                "rule_candidate_allowed": bool(rule_allowed_count),
                "true_engine_allowed": False,
                "ab_allowed": False,
                "blocking_reasons": ",".join(blocking_reasons),
            }
        )

    return pd.DataFrame(records)


def make_inventory_decision(route_summary: pd.DataFrame) -> dict[str, Any]:
    if route_summary.empty:
        route_summary = summarize_routes(pd.DataFrame())

    immediate = route_summary[route_summary["rule_candidate_allowed"].astype(bool)]
    schema_candidates = int(route_summary["potential_schema_candidate_file_count"].sum())
    protected_live_logs = int(route_summary["protected_live_log_count"].sum())
    research_artifacts = int(route_summary["research_artifact_count"].sum())
    minute_caches = int(route_summary["minute_ohlcv_backtest_cache_count"].sum())

    if not immediate.empty:
        decision = "stage035_has_predeclared_external_pit_route_for_readonly_audit"
        best_next_direction = str(immediate.iloc[0]["route_id"])
    elif schema_candidates > 0:
        decision = "stage035_local_external_pit_files_need_schema_validation_no_rule"
        best_next_direction = "run_schema_license_hash_coverage_validation_before_any_signal_audit"
    else:
        decision = "stage035_external_pit_inventory_no_local_rule_candidate"
        best_next_direction = "external_data_or_account_outer_layer"

    return {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().replace(microsecond=0).isoformat(),
        "decision": decision,
        "best_next_direction": best_next_direction,
        "route_count": int(len(route_summary)),
        "immediate_strategy_candidate_count": int(len(immediate)),
        "schema_candidate_file_count": int(schema_candidates),
        "protected_live_log_count": protected_live_logs,
        "research_artifact_count": research_artifacts,
        "minute_ohlcv_backtest_cache_count": minute_caches,
        "accepted_same_source_replay_file_count": int(route_summary["accepted_same_source_replay_file_count"].sum()),
        "strategy_rule_created": False,
        "official_live_strategy_changed": False,
        "true_engine": False,
        "ab_triggered": False,
        "order_api_called": False,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "ctp_connected": False,
        "external_research_judgment": (
            "Order-flow/depth/MBO and option IV/skew are theory-backed next information layers, but the local repo "
            "must first prove PIT history, schema/license/hash and coverage. Research outputs, minute backtest caches, "
            "smoke/read-only files and protected live logs are not accepted as strategy data."
        ),
        "overfit_reflection_before": "否。Stage035 只盘点外部 PIT 数据源，不扫收益阈值、不新增交易规则。",
        "overfit_reflection_after": "否。输出继续阻止把研究产物、分钟补数或实盘日志误当成可交易特征。",
        "continue_value_before": "有。Stage034 后公开 raw 路线已停止，必须确认是否存在 orderflow/执行回放/期权链等新 PIT 输入。",
        "continue_value_after": (
            "有，但如果本地仍没有 schema-ready 外部 PIT 文件，下一步价值来自导入授权数据或转账户外层，"
            "不是继续在现有本地文件上救参。"
        ),
    }


def write_report(inventory: pd.DataFrame, summary: pd.DataFrame, decision: dict[str, Any]) -> str:
    route_cols = [
        "route_id",
        "route_status",
        "evidence_file_count",
        "potential_schema_candidate_file_count",
        "accepted_same_source_replay_file_count",
        "protected_live_log_count",
        "research_artifact_count",
        "code_capability_doc_count",
        "minute_ohlcv_backtest_cache_count",
        "rule_candidate_allowed",
        "blocking_reasons",
    ]
    top_inventory_cols = ["path", "route_id", "asset_kind", "size_bytes", "blocking_reason"]
    top_inventory = (
        inventory.sort_values(["route_id", "asset_kind", "size_bytes"], ascending=[True, True, False]).head(40)
        if not inventory.empty
        else inventory
    )
    lines = [
        "# Stage035 外部 PIT 数据源库存审计报告",
        "",
        f"- decision：`{decision['decision']}`",
        f"- best_next_direction：`{decision['best_next_direction']}`",
        f"- schema_candidate_file_count：`{decision['schema_candidate_file_count']}`",
        f"- accepted_same_source_replay_file_count：`{decision['accepted_same_source_replay_file_count']}`",
        f"- protected_live_log_count：`{decision['protected_live_log_count']}`",
        "",
        "## 路线汇总",
        "",
        _md_table(summary[route_cols]),
        "",
        "## 代表性命中文件",
        "",
        _md_table(top_inventory[top_inventory_cols], max_rows=40) if not top_inventory.empty else "_无命中文件_",
        "",
        "## 外部调研判断",
        "",
        "- Order-flow/depth/MBO 方向：公开研究和工程实践都支持盘口不平衡、成交流、队列深度可作为短周期入场/执行质量信息，但必须有历史 PIT 深度或同源执行回放。",
        "- 期权 IV/skew 方向：商品期权隐含波动率、偏度和 risk premia 有作为前瞻波动/尾部风险信息的研究基础；本地只有 OptionMaster 能力文档，不等于 2018-2026 期权链历史。",
        "- 工程判断：没有 schema/license/hash/coverage 前，不允许进入 proxy、true engine、A/B 或正式策略规则。",
    ]
    return "\n".join(lines) + "\n"


def write_stage_record(decision: dict[str, Any]) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    path = STAGES_DIR / f"{timestamp}_stage035_external_pit_inventory_audit.md"
    content = f"""# Stage035 外部 PIT 数据源库存审计

- line_id：`{LINE_ID}`
- 当前模式：day
- 记录时间：{datetime.now().replace(microsecond=0).isoformat()}
- 阶段性质：只读数据源库存审计；不回测、不改策略、不连接 CTP、不调用下单
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考 order-flow/depth/MBO、商品期权 IV/skew、vn.py OptionMaster/执行事件链相关资料。
- 我的判断：这些是比当前公开 raw/分钟/OI 更接近“高质量信号”的信息层，但必须先有 PIT 历史、schema、license、hash 和覆盖；研究产物、分钟补数缓存、smoke/read-only 文件和受保护实盘日志都不能替代。

## 本次变更

- 新增脚本：`research/lines/{LINE_ID}/tools/stage035_external_pit_inventory_audit.py`
- 新增测试：`tests/test_rebuilt_c9_v2_stage035_external_pit_inventory_audit.py`
- 新增输出：inventory、route_summary、decision、report
- 新增参数：无交易参数；只有文件分类口径。
- 修改参数：无
- 删除参数：无

## 结果

- decision：`{decision['decision']}`
- best_next_direction：`{decision['best_next_direction']}`
- route_count：`{decision['route_count']}`
- schema_candidate_file_count：`{decision['schema_candidate_file_count']}`
- accepted_same_source_replay_file_count：`{decision['accepted_same_source_replay_file_count']}`
- protected_live_log_count：`{decision['protected_live_log_count']}`
- immediate_strategy_candidate_count：`{decision['immediate_strategy_candidate_count']}`
- 策略变更：`False`
- true engine：`False`
- order API：`0`

## 输出文件

- inventory：`{INVENTORY_PATH}`
- route_summary：`{ROUTE_SUMMARY_PATH}`
- decision：`{DECISION_PATH}`
- report：`{REPORT_PATH}`

## 过拟合反思

- 运行前判断：{decision['overfit_reflection_before']}
- 运行后判断：{decision['overfit_reflection_after']}

## 继续价值反思

- 运行前判断：{decision['continue_value_before']}
- 运行后判断：{decision['continue_value_after']}

## 合入建议

- 更新本线 `LINE.md`：是。
- 更新 `research/registry.md`：是。
- 追加根目录 `memory.md/back_log.md`：否，除非后续真实 PIT 数据到货并产生可复验候选。
"""
    STAGES_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def run() -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = iter_matching_paths(PROJECT_DIR)
    inventory = pd.DataFrame(rows)
    if inventory.empty:
        inventory = pd.DataFrame(
            columns=[
                "path",
                "route_id",
                "asset_kind",
                "size_bytes",
                "data_like",
                "protected_live_log",
                "research_artifact",
                "schema_validation_required",
                "rule_candidate_allowed",
                "true_engine_allowed",
                "order_api_allowed",
                "blocking_reason",
            ]
        )
    summary = summarize_routes(inventory)
    decision = make_inventory_decision(summary)
    stage_record = write_stage_record(decision)

    inventory.to_csv(INVENTORY_PATH, index=False)
    summary.to_csv(ROUTE_SUMMARY_PATH, index=False)
    REPORT_PATH.write_text(write_report(inventory, summary, decision), encoding="utf-8")
    decision["outputs"] = {
        "inventory": str(INVENTORY_PATH),
        "route_summary": str(ROUTE_SUMMARY_PATH),
        "decision": str(DECISION_PATH),
        "report": str(REPORT_PATH),
        "stage_record": str(stage_record),
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    return decision


if __name__ == "__main__":
    print(json.dumps(_json_safe(run()), ensure_ascii=False, indent=2))
