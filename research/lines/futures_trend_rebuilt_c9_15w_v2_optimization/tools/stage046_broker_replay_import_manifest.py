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
STAGE = "Stage046"
MODEL_TAG = "stage046_broker_replay_import_manifest_v1"
OUTPUT_PREFIX = "rebuilt_c9_v2_stage046_broker_replay_import_manifest"

LINE_DIR = PROJECT_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage046_broker_replay_import_manifest"
STAGES_DIR = LINE_DIR / "stages"

INVENTORY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_inventory_{MODEL_TAG}.csv"
READINESS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_readiness_{MODEL_TAG}.csv"
SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
REQUEST_MANIFEST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_request_manifest_{MODEL_TAG}.csv"
DATA_CONTRACT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_data_contract_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

REQUEST_START_DATE = "2026-06-16"
REQUEST_END_DATE = "forward_and_historical_available"
MAX_HEADER_SAMPLE_ROWS = int(os.getenv("STAGE046_MAX_HEADER_SAMPLE_ROWS", "500"))

INTEREST_RE = re.compile(
    r"(?<![a-z0-9])(execution_ledger|execution|trade_event|trade_events|position_change|position_changes|"
    r"fill|fills|deal|deals|order|orders|broker|production|same_source|same[-_]?source|replay|"
    r"ctp|simnow|entrust|成交|委托|报单|回报|持仓变动)(?![a-z0-9])",
    re.I,
)
DATA_SUFFIXES = {".csv", ".json", ".jsonl", ".parquet", ".feather", ".gz", ".xlsx", ".xls"}
EXCLUDED_DIRS = {".git", ".py311", ".mamba-root", ".pytest_cache", ".ruff_cache", "__pycache__", "node_modules"}

REQUIRED_FIELD_SPECS: tuple[dict[str, str], ...] = (
    {"required_field": "session_id", "source_layer": "session_context", "why_required": "区分夜盘/日盘和重启边界"},
    {"required_field": "strategy_version", "source_layer": "strategy_signal", "why_required": "锁定产生信号的线上策略版本"},
    {"required_field": "signal_time", "source_layer": "strategy_signal", "why_required": "计算信号到下单延迟和 PIT 边界"},
    {"required_field": "signal_id", "source_layer": "strategy_signal", "why_required": "把信号、计划、订单和成交串起来"},
    {"required_field": "plan_id", "source_layer": "strategy_signal", "why_required": "对应 Phase D/submit 前订单草案"},
    {"required_field": "order_time", "source_layer": "order_submission", "why_required": "计算下单延迟和订单队列"},
    {"required_field": "order_id", "source_layer": "broker_execution_report", "why_required": "券商/交易所订单编号"},
    {"required_field": "vt_orderid", "source_layer": "broker_execution_report", "why_required": "vn.py 内部订单编号"},
    {"required_field": "vt_symbol", "source_layer": "broker_execution_report", "why_required": "合约级执行归因"},
    {"required_field": "order_status", "source_layer": "broker_execution_report", "why_required": "区分 accepted/partial/filled/canceled/rejected"},
    {"required_field": "direction", "source_layer": "order_submission", "why_required": "方向与滑点符号"},
    {"required_field": "offset", "source_layer": "order_submission", "why_required": "开平仓归因"},
    {"required_field": "requested_volume", "source_layer": "order_submission", "why_required": "部分成交和撤单残量校准"},
    {"required_field": "order_price", "source_layer": "order_submission", "why_required": "arrival/order price benchmark"},
    {"required_field": "fill_time", "source_layer": "broker_execution_report", "why_required": "成交时间和排队/延迟校准"},
    {"required_field": "trade_id", "source_layer": "broker_execution_report", "why_required": "成交唯一编号和撤改冲正去重"},
    {"required_field": "fill_price", "source_layer": "broker_execution_report", "why_required": "真实成交价"},
    {"required_field": "fill_volume", "source_layer": "broker_execution_report", "why_required": "真实成交量"},
    {"required_field": "commission", "source_layer": "broker_execution_report", "why_required": "直接成本"},
    {"required_field": "slippage", "source_layer": "execution_cost", "why_required": "相对预期价格的执行偏差"},
    {"required_field": "position_time", "source_layer": "position_reconciliation", "why_required": "成交后持仓更新时间"},
    {"required_field": "position_after", "source_layer": "position_reconciliation", "why_required": "对账后的合约净持仓"},
    {"required_field": "account_equity", "source_layer": "account_reconciliation", "why_required": "账户权益和保证金容量归因"},
    {"required_field": "source_system", "source_layer": "lineage", "why_required": "确认来自 broker/CTP/SimNow 同源导出"},
    {"required_field": "source_file_hash", "source_layer": "lineage", "why_required": "防止事后改写和重复导入"},
)

TIME_FIELDS = ("signal_time", "order_time", "fill_time", "position_time")

SOURCE_LINKS = {
    "fix_execution_report": "https://www.onixs.biz/fix-dictionary/4.4/msgtype_8_8.html",
    "cqg_fix_execution_report": "https://help.cqg.com/apihelp/Documents/executionreportmsgtype83.htm",
    "fia_automated_trading_risk_controls": "https://www.fia.org/sites/default/files/2024-07/FIA_WP_AUTOMATED%20TRADING%20RISK%20CONTROLS_FINAL_0.pdf",
    "quantstart_transaction_costs": "https://www.quantstart.com/articles/Successful-Backtesting-of-Algorithmic-Trading-Strategies-Part-II/",
    "nautilus_execution": "https://nautilustrader.io/docs/latest/concepts/execution/",
    "nautilus_live_reconciliation": "https://nautilustrader.io/docs/latest/concepts/live/",
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


def _norm(path: Path | str) -> str:
    return str(path).replace("\\", "/").lstrip("./")


def _parts(path: Path | str) -> tuple[str, ...]:
    return tuple(part for part in Path(_norm(path)).parts if part and part != ".")


def _has_data_suffix(path: Path | str) -> bool:
    text = _norm(path).lower()
    return text.endswith(".csv.gz") or Path(text).suffix in DATA_SUFFIXES


def _is_code_or_doc(path: Path | str) -> bool:
    suffix = Path(_norm(path).lower()).suffix
    return suffix in {".py", ".md", ".sh", ".cpp", ".hpp", ".yaml", ".yml", ".env", ".txt"}


def _is_research_or_backtest_artifact(path: Path | str) -> bool:
    parts = _parts(path)
    if len(parts) >= 2 and parts[0] == "research" and parts[1] == "lines":
        return True
    if parts and parts[0] == "tests":
        return True
    if len(parts) >= 2 and parts[0] == "examples" and parts[1] in {"portfolio_backtesting", "alpha_research"}:
        return True
    return False


def _is_config(path: Path | str) -> bool:
    lower = _norm(path).lower()
    name = Path(lower).name
    return lower.endswith(".env") or lower.endswith(".local.env") or name.startswith("connect_") or name in {"vt_setting.json"}


def _is_protected_live_log(path: Path | str) -> bool:
    parts = set(_parts(path))
    lower = _norm(path).lower()
    protected_tokens = {
        "official_live",
        "ctp",
        "simnow",
        "readonly",
        "reconcile",
        "session_daemon",
        "timed_cycle",
        "dayclose",
        "phase_d",
        "smoke",
        "execution_ledger",
    }
    if _parts(path) and _parts(path)[0] in {"official_live", ".vntrader", "log"}:
        return True
    return bool(parts.intersection(protected_tokens) and lower.endswith((".log", ".jsonl", ".json", ".csv", ".csv.gz", ".txt")))


def _lower_columns(frame: pd.DataFrame) -> set[str]:
    return {str(col).strip().lower() for col in frame.columns}


def _parse_time(frame: pd.DataFrame, column: str) -> pd.Series | None:
    lower_map = {str(col).strip().lower(): col for col in frame.columns}
    if column not in lower_map:
        return None
    return pd.to_datetime(frame[lower_map[column]], errors="coerce")


def build_replay_request_manifest() -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for spec in REQUIRED_FIELD_SPECS:
        rows.append(
            {
                **spec,
                "required": True,
                "request_start_date": REQUEST_START_DATE,
                "request_end_date": REQUEST_END_DATE,
                "acceptance_gate": "all_required_fields_present_and_signal_time<=order_time<=fill_time<=position_time_and_source_hash_present",
                "forbidden_shortcut": "do_not_use_research_trade_events_or_protected_live_logs_as_alpha_feature",
            }
        )
    return pd.DataFrame(rows)


def validate_replay_schema(frame: pd.DataFrame) -> dict[str, Any]:
    columns = _lower_columns(frame)
    flags = {f"has_{spec['required_field']}": spec["required_field"] in columns for spec in REQUIRED_FIELD_SPECS}

    time_series = {field: _parse_time(frame, field) for field in TIME_FIELDS}
    has_signal_to_position_chain = all(series is not None for series in time_series.values())
    has_time_order_violation = False
    if time_series["signal_time"] is not None and time_series["order_time"] is not None:
        has_time_order_violation |= bool((time_series["signal_time"] > time_series["order_time"]).fillna(False).any())
    if time_series["order_time"] is not None and time_series["fill_time"] is not None:
        has_time_order_violation |= bool((time_series["order_time"] > time_series["fill_time"]).fillna(False).any())
    if time_series["fill_time"] is not None and time_series["position_time"] is not None:
        has_time_order_violation |= bool((time_series["fill_time"] > time_series["position_time"]).fillna(False).any())

    missing_reasons = []
    for spec in REQUIRED_FIELD_SPECS:
        field = spec["required_field"]
        if flags[f"has_{field}"]:
            continue
        if field == "source_file_hash":
            missing_reasons.append("missing_source_hash")
        else:
            missing_reasons.append("missing_" + field)
    if has_time_order_violation:
        missing_reasons.append("time_order_violation")

    fields_complete = all(flags.values())
    schema_complete = bool(fields_complete and has_signal_to_position_chain and not has_time_order_violation)
    accepted = bool(schema_complete)
    return {
        "row_count_sampled": int(len(frame)),
        "column_count": int(len(frame.columns)),
        "columns": ",".join(map(str, frame.columns)),
        **{key: bool(value) for key, value in flags.items()},
        "has_signal_to_position_chain": bool(has_signal_to_position_chain),
        "has_time_order_violation": bool(has_time_order_violation),
        "schema_complete": bool(schema_complete),
        "execution_calibration_allowed": bool(accepted),
        "accepted_same_source_replay": bool(accepted),
        "blocking_reasons": ",".join(list(dict.fromkeys(missing_reasons))),
    }


def classify_replay_import_path(path: Path, size_bytes: int = 0) -> dict[str, Any]:
    text = _norm(path)
    data_like = _has_data_suffix(path)
    protected_live = _is_protected_live_log(path)
    research = _is_research_or_backtest_artifact(path)
    config = _is_config(path)
    code_or_doc = _is_code_or_doc(path)
    schema_required = False
    preserve_by_default = False

    if protected_live:
        asset_kind = "protected_live_evidence_log"
        blocking = "preserve_live_or_evidence_log_not_research_import_source"
        preserve_by_default = True
    elif research:
        asset_kind = "research_or_backtest_artifact"
        blocking = "research_backtest_artifact_not_same_source_broker_replay"
    elif config:
        asset_kind = "configuration_file"
        blocking = "configuration_file_not_replay_dataset"
    elif code_or_doc:
        asset_kind = "execution_code_or_doc"
        blocking = "code_or_doc_not_replay_dataset"
    elif data_like and INTEREST_RE.search(text):
        asset_kind = "potential_broker_replay_schema_candidate"
        blocking = "schema_hash_time_order_and_source_validation_required"
        schema_required = True
    elif INTEREST_RE.search(text):
        asset_kind = "non_data_replay_hit"
        blocking = "not_data_file"
    else:
        asset_kind = "unclassified"
        blocking = "not_replay_related"

    return {
        "path": text,
        "asset_kind": asset_kind,
        "size_bytes": int(size_bytes or 0),
        "data_like": bool(data_like),
        "protected_live_log": bool(protected_live),
        "preserve_by_default": bool(preserve_by_default),
        "research_artifact": bool(research),
        "schema_validation_required": bool(schema_required),
        "schema_complete": False,
        "execution_calibration_allowed": False,
        "accepted_same_source_replay": False,
        "rule_candidate_allowed": False,
        "true_engine_allowed": False,
        "order_api_allowed": False,
        "blocking_reason": blocking,
    }


def _read_candidate_sample(path: Path) -> pd.DataFrame | None:
    try:
        lower = str(path).lower()
        if lower.endswith(".csv.gz"):
            return pd.read_csv(path, compression="gzip", nrows=MAX_HEADER_SAMPLE_ROWS)
        if lower.endswith(".csv"):
            return pd.read_csv(path, nrows=MAX_HEADER_SAMPLE_ROWS)
        if lower.endswith(".jsonl"):
            return pd.read_json(path, lines=True, nrows=MAX_HEADER_SAMPLE_ROWS)
        if lower.endswith(".json"):
            data = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
            if isinstance(data, list):
                return pd.DataFrame(data[:MAX_HEADER_SAMPLE_ROWS])
            if isinstance(data, dict):
                for key in ("data", "records", "rows", "events", "orders", "fills", "trades"):
                    if isinstance(data.get(key), list):
                        return pd.DataFrame(data[key][:MAX_HEADER_SAMPLE_ROWS])
                return pd.DataFrame([data])
        if lower.endswith(".parquet"):
            return pd.read_parquet(path).head(MAX_HEADER_SAMPLE_ROWS)
        if lower.endswith(".feather"):
            return pd.read_feather(path).head(MAX_HEADER_SAMPLE_ROWS)
        if lower.endswith((".xlsx", ".xls")):
            return pd.read_excel(path, nrows=MAX_HEADER_SAMPLE_ROWS)
    except Exception:
        return None
    return None


def iter_replay_import_paths(root: Path = PROJECT_DIR) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    root = root.resolve()
    for current, dirs, files in os.walk(root):
        dirs[:] = [item for item in dirs if item not in EXCLUDED_DIRS]
        current_path = Path(current)
        for name in files:
            relative = (current_path / name).relative_to(root)
            text = _norm(relative)
            if not INTEREST_RE.search(text):
                continue
            try:
                size_bytes = (current_path / name).stat().st_size
            except OSError:
                size_bytes = 0
            rows.append(classify_replay_import_path(relative, size_bytes))
    return rows


def build_readiness(inventory: pd.DataFrame, root: Path = PROJECT_DIR) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for row in inventory.to_dict("records"):
        result = dict(row)
        if bool(row.get("schema_validation_required")):
            sample = _read_candidate_sample(root / str(row["path"]))
            if sample is None:
                result.update(
                    {
                        "row_count_sampled": 0,
                        "column_count": 0,
                        "columns": "",
                        "schema_complete": False,
                        "execution_calibration_allowed": False,
                        "accepted_same_source_replay": False,
                        "has_signal_to_position_chain": False,
                        "has_time_order_violation": False,
                        "blocking_reasons": "sample_read_failed_or_unsupported_format",
                    }
                )
            else:
                result.update(validate_replay_schema(sample))
        else:
            result.update(
                {
                    "row_count_sampled": 0,
                    "column_count": 0,
                    "columns": "",
                    "schema_complete": False,
                    "execution_calibration_allowed": False,
                    "accepted_same_source_replay": False,
                    "has_signal_to_position_chain": False,
                    "has_time_order_violation": False,
                    "blocking_reasons": str(row.get("blocking_reason", "")),
                }
            )
        result["rule_candidate_allowed"] = False
        result["true_engine_allowed"] = False
        rows.append(result)
    return pd.DataFrame(rows)


def summarize_readiness(readiness: pd.DataFrame) -> pd.DataFrame:
    if readiness.empty:
        return pd.DataFrame(
            [
                {
                    "asset_kind": "none",
                    "file_count": 0,
                    "total_size_bytes": 0,
                    "schema_candidate_count": 0,
                    "schema_complete_count": 0,
                    "accepted_same_source_replay_count": 0,
                    "protected_live_log_count": 0,
                    "preserve_by_default_count": 0,
                }
            ]
        )
    rows: list[dict[str, Any]] = []
    for asset_kind, group in readiness.groupby("asset_kind", sort=True):
        rows.append(
            {
                "asset_kind": asset_kind,
                "file_count": int(len(group)),
                "total_size_bytes": int(group["size_bytes"].fillna(0).astype(int).sum()),
                "schema_candidate_count": int(group["schema_validation_required"].astype(bool).sum()),
                "schema_complete_count": int(group["schema_complete"].astype(bool).sum()) if "schema_complete" in group else 0,
                "accepted_same_source_replay_count": int(group["accepted_same_source_replay"].astype(bool).sum())
                if "accepted_same_source_replay" in group
                else 0,
                "protected_live_log_count": int(group["protected_live_log"].astype(bool).sum()) if "protected_live_log" in group else 0,
                "preserve_by_default_count": int(group["preserve_by_default"].astype(bool).sum()) if "preserve_by_default" in group else 0,
                "blocking_reasons": ",".join(sorted(set(",".join(group["blocking_reasons"].fillna("").astype(str)).split(",")) - {""}))
                if "blocking_reasons" in group
                else "",
            }
        )
    return pd.DataFrame(rows)


def build_data_contract() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "contract_id": "broker_production_same_source_replay",
                "required_source": "同一生产/SimNow/CTP链路导出的信号、订单、成交、撤改单、持仓和账户权益事件，不是研究回测输出",
                "required_fields": ",".join(spec["required_field"] for spec in REQUIRED_FIELD_SPECS),
                "required_checks": "signal_time<=order_time<=fill_time<=position_time,source_file_hash,source_system,strategy_version,session_id,no_manual_posthoc_labels",
                "allowed_use": "执行成本、滑点、延迟、部分成交、撤单和重启对账校准；后续仍需只读审计和用户确认",
                "forbidden_shortcut": "保护实盘日志和研究 trade_events 不得直接作为 AI/alpha 特征；缺 hash 或时间链的成交表不得入模",
            }
        ]
    )


def make_stage046_decision(readiness: pd.DataFrame, request_manifest: pd.DataFrame) -> dict[str, Any]:
    accepted = int(readiness["accepted_same_source_replay"].astype(bool).sum()) if not readiness.empty and "accepted_same_source_replay" in readiness.columns else 0
    schema_candidates = int(readiness["schema_validation_required"].astype(bool).sum()) if not readiness.empty and "schema_validation_required" in readiness.columns else 0
    schema_complete = int(readiness["schema_complete"].astype(bool).sum()) if not readiness.empty and "schema_complete" in readiness.columns else 0
    protected = int(readiness["preserve_by_default"].astype(bool).sum()) if not readiness.empty and "preserve_by_default" in readiness.columns else 0
    research = int(readiness["research_artifact"].astype(bool).sum()) if not readiness.empty and "research_artifact" in readiness.columns else 0

    if accepted > 0:
        decision = "stage046_broker_replay_has_accepted_dataset_needs_readonly_execution_cost_audit"
        best_next_direction = "run_readonly_execution_cost_latency_partial_fill_audit_before_any_strategy_change"
    else:
        decision = "stage046_broker_replay_import_manifest_data_first_no_accepted_dataset"
        best_next_direction = "procure_or_export_broker_same_source_replay_then_run_acceptance_gate"

    return {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().replace(microsecond=0).isoformat(),
        "decision": decision,
        "best_next_direction": best_next_direction,
        "file_count": int(len(readiness)),
        "required_field_count": int(len(request_manifest)),
        "schema_candidate_file_count": int(schema_candidates),
        "schema_complete_file_count": int(schema_complete),
        "accepted_same_source_replay_count": int(accepted),
        "protected_preserve_file_count": int(protected),
        "research_artifact_count": int(research),
        "immediate_strategy_candidate_count": 0,
        "strategy_rule_created": False,
        "official_live_strategy_changed": False,
        "true_engine": False,
        "ab_triggered": False,
        "order_api_called": False,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "ctp_connected": False,
        "source_links": SOURCE_LINKS,
        "external_research_judgment": (
            "FIX/CQG Execution Report 和 NautilusTrader 文档都把订单生命周期、成交回报、状态和重启对账作为执行系统核心；"
            "FIA 风控材料强调自动化交易要覆盖 pre-trade、post-trade analysis/testing；"
            "QuantStart 的交易成本资料也说明佣金、滑点、冲击等必须进入回测现实性。"
            "因此 same-source replay 有价值，但只能先做执行真实性校准，不允许直接当 AI 选品特征。"
        ),
        "overfit_reflection_before": "否。本阶段是数据合同和验收闸门，不跑收益、不扫参数、不产生策略规则。",
        "overfit_reflection_after": "否。输出继续 data-first，保护日志只保留为证据，不被读成 alpha 或训练样本。",
        "continue_value_before": "有。当前本地字段路线已被多次反证，执行回放可帮助判断回测和实盘滑点/部分成交是否偏离。",
        "continue_value_after": (
            "有但前提是拿到同源数据。若没有 accepted replay，下一步应导入券商/SimNow 同源回放或冻结 forward OOS，"
            "不能继续用研究 trade_events 救参。"
        ),
    }


def write_report(
    readiness: pd.DataFrame,
    summary: pd.DataFrame,
    request_manifest: pd.DataFrame,
    data_contract: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    representative = readiness.sort_values(["asset_kind", "size_bytes"], ascending=[True, False]).head(80) if not readiness.empty else readiness
    cols = [
        "path",
        "asset_kind",
        "preserve_by_default",
        "schema_validation_required",
        "schema_complete",
        "execution_calibration_allowed",
        "accepted_same_source_replay",
        "blocking_reasons",
    ]
    lines = [
        "# Stage046 broker/production 同源回放导入验收包",
        "",
        f"- line_id：`{LINE_ID}`",
        f"- 记录时间：{decision['generated_at']}",
        f"- 决策：`{decision['decision']}`",
        "- 阶段性质：只读数据导入合同；不回测、不改策略、不连接 CTP、不调用订单 API。",
        "",
        "## 外部调研与判断",
        "",
        "- FIX Execution Report 用于确认订单接收、状态、成交、拒单和费用等；字段上至少需要 order id、execution id、status/type、数量、价格等。",
        "- FIA 自动化交易风控材料强调 pre-trade、post-trade analysis/testing 和系统安全边界。",
        "- NautilusTrader 文档强调订单生命周期、部分成交、重启对账、缺失成交重建和 ID 确定性。",
        "- QuantStart 交易成本资料提示佣金、滑点、冲击和订单类型是回测现实性的核心。",
        "- 我的判断：同源回放能提高执行真实性，但它不是新 alpha；缺少 hash、时间链或持仓对账的成交表不得进入 AI 或高质量信号。",
        "",
        "## Summary",
        "",
        _md_table(summary),
        "",
        "## Request Manifest",
        "",
        _md_table(request_manifest, max_rows=40),
        "",
        "## Data Contract",
        "",
        _md_table(data_contract),
        "",
        "## Representative Local Hits",
        "",
        _md_table(representative[cols], max_rows=80) if not representative.empty else "_无记录_",
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


def write_stage_record(summary: pd.DataFrame, request_manifest: pd.DataFrame, data_contract: pd.DataFrame, decision: dict[str, Any]) -> Path:
    STAGES_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    path = STAGES_DIR / f"{timestamp}_stage046_broker_replay_import_manifest.md"
    text = f"""# Stage046 broker/production 同源回放导入验收包

- line_id：`{LINE_ID}`
- 当前模式：day
- 记录时间：{decision['generated_at']}
- 阶段性质：只读数据导入合同；不回测、不改策略、不连接 CTP、不调用下单
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：FIX Execution Report、CQG FIX Execution Report、FIA automated trading risk controls、NautilusTrader execution/live reconciliation、QuantStart transaction costs。
- 我的判断：broker/production same-source replay 只适合先做执行成本、延迟、部分成交、撤改和重启对账校准；它不是 AI alpha 输入。缺少 `source_file_hash`、完整信号到持仓时间链、订单状态和账户/持仓对账时，不允许进入回测校准或信号研究。

## 本次变更

- 新增脚本：`research/lines/{LINE_ID}/tools/stage046_broker_replay_import_manifest.py`
- 新增测试：`tests/test_rebuilt_c9_v2_stage046_broker_replay_import_manifest.py`
- 新增参数：`STAGE046_MAX_HEADER_SAMPLE_ROWS={MAX_HEADER_SAMPLE_ROWS}`
- 修改参数：无正式策略参数修改
- 删除参数：无

## 结果

- decision：`{decision['decision']}`
- best_next_direction：`{decision['best_next_direction']}`
- required_field_count：`{decision['required_field_count']}`
- file_count：`{decision['file_count']}`
- schema_candidate_file_count：`{decision['schema_candidate_file_count']}`
- schema_complete_file_count：`{decision['schema_complete_file_count']}`
- accepted_same_source_replay_count：`{decision['accepted_same_source_replay_count']}`
- protected_preserve_file_count：`{decision['protected_preserve_file_count']}`
- research_artifact_count：`{decision['research_artifact_count']}`
- immediate_strategy_candidate_count：`0`
- 策略变更：`False`
- true engine：`False`
- order API：`0`
- CTP：`False`

## Summary

{_md_table(summary)}

## Request Manifest

{_md_table(request_manifest, max_rows=40)}

## Data Contract

{_md_table(data_contract)}

## 过拟合反思

- 运行前判断：{decision['overfit_reflection_before']}
- 运行后判断：{decision['overfit_reflection_after']}

## 继续价值反思

- 运行前判断：{decision['continue_value_before']}
- 运行后判断：{decision['continue_value_after']}

## 输出文件

- inventory：`{INVENTORY_PATH}`
- readiness：`{READINESS_PATH}`
- summary：`{SUMMARY_PATH}`
- request_manifest：`{REQUEST_MANIFEST_PATH}`
- data_contract：`{DATA_CONTRACT_PATH}`
- decision：`{DECISION_PATH}`
- report：`{REPORT_PATH}`
"""
    path.write_text(text, encoding="utf-8")
    return path


def run() -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    inventory = pd.DataFrame(iter_replay_import_paths(PROJECT_DIR))
    if inventory.empty:
        inventory = pd.DataFrame(
            columns=[
                "path",
                "asset_kind",
                "size_bytes",
                "data_like",
                "protected_live_log",
                "preserve_by_default",
                "research_artifact",
                "schema_validation_required",
                "schema_complete",
                "execution_calibration_allowed",
                "accepted_same_source_replay",
                "rule_candidate_allowed",
                "true_engine_allowed",
                "order_api_allowed",
                "blocking_reason",
            ]
        )
    readiness = build_readiness(inventory, PROJECT_DIR)
    summary = summarize_readiness(readiness)
    request_manifest = build_replay_request_manifest()
    data_contract = build_data_contract()
    decision = make_stage046_decision(readiness, request_manifest)

    inventory.to_csv(INVENTORY_PATH, index=False)
    readiness.to_csv(READINESS_PATH, index=False)
    summary.to_csv(SUMMARY_PATH, index=False)
    request_manifest.to_csv(REQUEST_MANIFEST_PATH, index=False)
    data_contract.to_csv(DATA_CONTRACT_PATH, index=False)
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_report(readiness, summary, request_manifest, data_contract, decision)
    stage_record = write_stage_record(summary, request_manifest, data_contract, decision)
    decision["stage_record_path"] = str(stage_record)
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return decision


if __name__ == "__main__":
    print(json.dumps(_json_safe(run()), ensure_ascii=False, indent=2))
