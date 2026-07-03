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
STAGE = "Stage044"
MODEL_TAG = "stage044_orderflow_depth_contract_v1"
OUTPUT_PREFIX = "rebuilt_c9_v2_stage044_orderflow_depth_contract"

LINE_DIR = PROJECT_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage044_orderflow_depth_contract"
STAGES_DIR = LINE_DIR / "stages"

INVENTORY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_inventory_{MODEL_TAG}.csv"
READINESS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_readiness_{MODEL_TAG}.csv"
SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DATA_CONTRACT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_data_contract_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

INTEREST_RE = re.compile(
    r"(?<![a-z0-9])(order[_-]?flow|order[_-]?book|orderbook|limit[_-]?order[_-]?book|market[_-]?depth|"
    r"depth|mbo|mbp10|mbp[_-]?10|l2|l3|bbo|quote|quotes|盘口|深度|逐笔委托|委托簿)(?![a-z0-9])",
    re.I,
)
BAR_RE = re.compile(r"(minute|bar|bars|ohlcv|kline|candles|full_minute_bars|分钟|k线)", re.I)

DATA_SUFFIXES = {".csv", ".json", ".jsonl", ".parquet", ".feather", ".gz"}
EXCLUDED_DIRS = {".git", ".py311", ".mamba-root", ".pytest_cache", ".ruff_cache", "__pycache__", "node_modules"}
MAX_HEADER_SAMPLE_ROWS = int(os.getenv("STAGE044_MAX_HEADER_SAMPLE_ROWS", "500"))

EVENT_TIME_COLUMNS = {"ts_event", "event_time", "exchange_time", "exchange_timestamp", "datetime", "timestamp", "time"}
RECEIVE_TIME_COLUMNS = {"ts_recv", "receive_time", "received_time", "publish_time", "local_time", "local_timestamp", "source_publish_time"}
SYMBOL_COLUMNS = {"vt_symbol", "symbol", "instrument_id", "contract", "security_id", "raw_symbol"}
SOURCE_COLUMNS = {"source_system", "source", "vendor", "dataset", "publisher"}
SOURCE_HASH_COLUMNS = {"source_file_hash", "sha256", "source_hash", "data_hash", "raw_hash", "file_hash"}

MBO_ORDER_COLUMNS = {"order_id", "orderid", "order_ref", "order_reference", "queue_id"}
MBO_ACTION_COLUMNS = {"action", "event_type", "update_action", "message_type", "operation"}
SIDE_COLUMNS = {"side", "direction", "bid_ask", "book_side"}
PRICE_COLUMNS = {"price", "px", "order_price"}
SIZE_COLUMNS = {"size", "qty", "quantity", "volume", "order_qty", "order_size"}

SOURCE_LINKS = {
    "cme_mbo_faq": "https://www.cmegroup.com/articles/faqs/market-by-order-mbo.html",
    "databento_mbo_schema": "https://databento.com/docs/schemas-and-data-formats/mbo",
    "databento_mbp10_schema": "https://databento.com/docs/schemas-and-data-formats/mbp-10",
    "hftbacktest_order_book_imbalance": "https://hftbacktest.readthedocs.io/en/latest/tutorials/Market%20Making%20with%20Alpha%20-%20Order%20Book%20Imbalance.html",
    "order_book_filtration_signal_extraction": "https://arxiv.org/html/2507.22712v1",
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
    return Path(_norm(path).lower()).suffix in {".py", ".md", ".sh", ".yaml", ".yml", ".cpp", ".hpp", ".txt", ".env"}


def _is_research_or_backtest_artifact(path: Path | str) -> bool:
    parts = _parts(path)
    if len(parts) >= 2 and parts[0] == "research" and parts[1] == "lines":
        return True
    if parts and parts[0] == "tests":
        return True
    if len(parts) >= 2 and parts[0] == "examples" and parts[1] in {"portfolio_backtesting", "alpha_research"}:
        return True
    return False


def _is_protected_live_or_config(path: Path | str) -> bool:
    parts = set(_parts(path))
    lower = _norm(path).lower()
    protected_tokens = {"official_live", "ctp", "simnow", "readonly", "reconcile", "session_daemon", "timed_cycle", "phase_d", ".vntrader", "log"}
    if parts.intersection(protected_tokens) and lower.endswith((".csv", ".csv.gz", ".json", ".jsonl", ".log", ".txt", ".xlsx", ".xls")):
        return True
    return lower.endswith(".env") or lower.endswith(".local.env") or lower.endswith(".example.env")


def _is_minute_or_bar_cache(path: Path | str) -> bool:
    text = _norm(path).lower()
    return _has_data_suffix(path) and bool(BAR_RE.search(text))


def classify_orderflow_path(path: Path, size_bytes: int = 0) -> dict[str, Any]:
    text = _norm(path)
    data_like = _has_data_suffix(path)
    research = _is_research_or_backtest_artifact(path)
    protected = _is_protected_live_or_config(path)
    minute_cache = _is_minute_or_bar_cache(path)
    code_or_doc = _is_code_or_doc(path)

    schema_required = False
    if protected:
        asset_kind = "protected_live_or_config_artifact"
        blocking = "protected_live_or_config_not_orderflow_signal_source"
    elif research:
        asset_kind = "research_or_backtest_artifact"
        blocking = "research_or_backtest_artifact_not_orderflow_depth_source"
    elif minute_cache:
        asset_kind = "minute_ohlcv_or_bar_cache"
        blocking = "bars_do_not_contain_book_queue_or_depth_events"
    elif code_or_doc:
        asset_kind = "orderflow_code_or_doc"
        blocking = "code_or_doc_not_orderflow_depth_dataset"
    elif data_like and INTEREST_RE.search(text):
        asset_kind = "potential_orderflow_depth_schema_candidate"
        blocking = "schema_hash_pit_and_coverage_validation_required"
        schema_required = True
    elif INTEREST_RE.search(text):
        asset_kind = "non_data_orderflow_hit"
        blocking = "not_data_file"
    else:
        asset_kind = "unclassified"
        blocking = "not_orderflow_depth_related"

    return {
        "path": text,
        "asset_kind": asset_kind,
        "size_bytes": int(size_bytes or 0),
        "data_like": bool(data_like),
        "research_artifact": bool(research),
        "protected_live_or_config": bool(protected),
        "minute_or_bar_cache": bool(minute_cache),
        "schema_validation_required": bool(schema_required),
        "schema_complete": False,
        "pit_rule_audit_allowed": False,
        "accepted_orderflow_dataset": False,
        "rule_candidate_allowed": False,
        "true_engine_allowed": False,
        "order_api_allowed": False,
        "blocking_reason": blocking,
    }


def _lower_columns(frame: pd.DataFrame) -> set[str]:
    return {str(col).strip().lower() for col in frame.columns}


def _has_any(columns: set[str], candidates: set[str]) -> bool:
    lower_candidates = {item.lower() for item in candidates}
    return bool(columns.intersection(lower_candidates))


def _wide_mbp_levels(columns: set[str]) -> set[int]:
    levels: set[int] = set()
    patterns = [
        re.compile(r"^(bid|ask)_(px|price|sz|size|qty|volume)_([0-9]+)$"),
        re.compile(r"^(bid|ask)(px|price|sz|size|qty|volume)_([0-9]+)$"),
        re.compile(r"^(bid|ask)_(px|price|sz|size|qty|volume)([0-9]+)$"),
    ]
    for col in columns:
        for pattern in patterns:
            match = pattern.match(col)
            if match:
                raw_level = match.group(3)
                level = int(raw_level) + 1 if raw_level.startswith("0") else int(raw_level)
                levels.add(level)
    return levels


def _long_depth_schema(columns: set[str]) -> bool:
    return bool({"level", "side", "price"}.issubset(columns) and columns.intersection({"size", "qty", "quantity", "volume"}))


def _detect_mbp(columns: set[str]) -> tuple[bool, int]:
    levels = _wide_mbp_levels(columns)
    long_depth = _long_depth_schema(columns)
    max_level = max(levels) if levels else (10 if long_depth else 0)
    has_wide_top = bool(
        ({"bid_px_00", "ask_px_00", "bid_sz_00", "ask_sz_00"}.issubset(columns))
        or ({"bid_price_1", "ask_price_1", "bid_volume_1", "ask_volume_1"}.issubset(columns))
        or ({"bidpx1", "askpx1", "bidsz1", "asksz1"}.issubset(columns))
    )
    return bool((has_wide_top and max_level >= 1) or long_depth), int(max_level)


def _detect_mbo(columns: set[str]) -> bool:
    return bool(
        _has_any(columns, MBO_ORDER_COLUMNS)
        and _has_any(columns, MBO_ACTION_COLUMNS)
        and _has_any(columns, SIDE_COLUMNS)
        and _has_any(columns, PRICE_COLUMNS)
        and _has_any(columns, SIZE_COLUMNS)
    )


def validate_orderflow_schema(frame: pd.DataFrame) -> dict[str, Any]:
    columns = _lower_columns(frame)
    has_event_time = _has_any(columns, EVENT_TIME_COLUMNS)
    has_receive = _has_any(columns, RECEIVE_TIME_COLUMNS)
    has_symbol = _has_any(columns, SYMBOL_COLUMNS)
    has_source = _has_any(columns, SOURCE_COLUMNS)
    has_source_hash = _has_any(columns, SOURCE_HASH_COLUMNS)
    is_mbp, max_level = _detect_mbp(columns)
    is_mbo = _detect_mbo(columns)
    has_order_identity = _has_any(columns, MBO_ORDER_COLUMNS)
    has_action = _has_any(columns, MBO_ACTION_COLUMNS)

    if is_mbo:
        schema_family = "mbo"
        depth_complete = True
    elif is_mbp:
        schema_family = "mbp10" if max_level >= 10 else "mbp_partial"
        depth_complete = max_level >= 10
    else:
        schema_family = "unknown"
        depth_complete = False

    schema_complete = bool(has_event_time and has_receive and has_symbol and has_source and has_source_hash and depth_complete)
    if is_mbo:
        schema_complete = bool(schema_complete and has_order_identity and has_action)

    reasons: list[str] = []
    if not has_event_time:
        reasons.append("missing_event_time")
    if not has_receive:
        reasons.append("missing_receive_or_publish_time")
    if not has_symbol:
        reasons.append("missing_symbol")
    if not depth_complete:
        reasons.append("missing_full_mbp10_or_mbo_depth_fields")
    if is_mbo and not has_order_identity:
        reasons.append("missing_order_identity")
    if is_mbo and not has_action:
        reasons.append("missing_action")
    if not has_source:
        reasons.append("missing_source_system")
    if not has_source_hash:
        reasons.append("missing_source_hash")

    return {
        "row_count_sampled": int(len(frame)),
        "column_count": int(len(frame.columns)),
        "columns": ",".join(map(str, frame.columns)),
        "schema_family": schema_family,
        "has_event_time": bool(has_event_time),
        "has_receive_or_publish_time": bool(has_receive),
        "has_symbol": bool(has_symbol),
        "has_source_system": bool(has_source),
        "has_source_hash": bool(has_source_hash),
        "has_order_identity": bool(has_order_identity),
        "has_action": bool(has_action),
        "is_mbp_depth": bool(is_mbp),
        "is_mbo_depth": bool(is_mbo),
        "max_book_level_detected": int(max_level),
        "schema_complete": bool(schema_complete),
        "pit_rule_audit_allowed": bool(schema_complete),
        "accepted_orderflow_dataset": bool(schema_complete),
        "blocking_reasons": ",".join(reasons),
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
                for key in ("data", "records", "rows", "events", "ticks"):
                    if isinstance(data.get(key), list):
                        return pd.DataFrame(data[key][:MAX_HEADER_SAMPLE_ROWS])
                return pd.DataFrame([data])
        if lower.endswith(".parquet"):
            return pd.read_parquet(path).head(MAX_HEADER_SAMPLE_ROWS)
        if lower.endswith(".feather"):
            return pd.read_feather(path).head(MAX_HEADER_SAMPLE_ROWS)
    except Exception:
        return None
    return None


def iter_orderflow_paths(root: Path = PROJECT_DIR) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    root = root.resolve()
    for current, dirs, files in os.walk(root):
        dirs[:] = [item for item in dirs if item not in EXCLUDED_DIRS]
        current_path = Path(current)
        for name in files:
            relative = (current_path / name).relative_to(root)
            text = _norm(relative)
            if not (INTEREST_RE.search(text) or (BAR_RE.search(text) and _has_data_suffix(relative))):
                continue
            try:
                size_bytes = (current_path / name).stat().st_size
            except OSError:
                size_bytes = 0
            rows.append(classify_orderflow_path(relative, size_bytes))
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
                        "schema_family": "unreadable",
                        "schema_complete": False,
                        "pit_rule_audit_allowed": False,
                        "accepted_orderflow_dataset": False,
                        "blocking_reasons": "sample_read_failed_or_unsupported_format",
                    }
                )
            else:
                result.update(validate_orderflow_schema(sample))
        else:
            result.update(
                {
                    "row_count_sampled": 0,
                    "column_count": 0,
                    "columns": "",
                    "schema_family": "",
                    "schema_complete": False,
                    "pit_rule_audit_allowed": False,
                    "accepted_orderflow_dataset": False,
                    "blocking_reasons": str(row.get("blocking_reason", "")),
                }
            )
        result["rule_candidate_allowed"] = bool(result.get("pit_rule_audit_allowed", False))
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
                    "accepted_orderflow_dataset_count": 0,
                    "pit_rule_audit_allowed_count": 0,
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
                "accepted_orderflow_dataset_count": int(group["accepted_orderflow_dataset"].astype(bool).sum()) if "accepted_orderflow_dataset" in group else 0,
                "pit_rule_audit_allowed_count": int(group["pit_rule_audit_allowed"].astype(bool).sum()) if "pit_rule_audit_allowed" in group else 0,
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
                "contract_id": "authorized_mbp10_depth_history",
                "schema_family": "mbp10",
                "required_fields": "ts_event,ts_recv,vt_symbol/instrument_id,bid_px_00..09,ask_px_00..09,bid_sz_00..09,ask_sz_00..09,source_system,source_file_hash",
                "required_checks": "exchange_event_time_before_signal,receive_or_publish_time_present,continuous_target_pool_calendar,per_file_hash,roll_symbol_mapping,session_filter,cost_latency_join_key",
                "allowed_use": "PIT depth imbalance, micro-price, VAMP, liquidity stress and entry quality audit after coverage validation",
                "forbidden_shortcut": "do_not_use_minute_bars_or_research_trade_events_as_l2_depth_proxy",
            },
            {
                "contract_id": "authorized_mbo_full_depth_history",
                "schema_family": "mbo",
                "required_fields": "ts_event,ts_recv,vt_symbol/instrument_id,order_id,action,side,price,size,source_system,source_file_hash",
                "required_checks": "book_replay_reconstructable,add_cancel_modify_trade_actions,queue_position_replay,exchange_event_time_before_signal,per_file_hash,continuous_target_pool_calendar",
                "allowed_use": "queue pressure, cancellation imbalance, large order persistence and passive fill/adverse selection audit",
                "forbidden_shortcut": "do_not_infer_queue_position_from_l1_or_ohlcv",
            },
        ]
    )


def make_stage044_decision(readiness: pd.DataFrame) -> dict[str, Any]:
    accepted = int(readiness["accepted_orderflow_dataset"].astype(bool).sum()) if not readiness.empty and "accepted_orderflow_dataset" in readiness.columns else 0
    schema_candidates = int(readiness["schema_validation_required"].astype(bool).sum()) if not readiness.empty and "schema_validation_required" in readiness.columns else 0
    schema_complete = int(readiness["schema_complete"].astype(bool).sum()) if not readiness.empty and "schema_complete" in readiness.columns else 0
    minute_cache = int(readiness["minute_or_bar_cache"].astype(bool).sum()) if not readiness.empty and "minute_or_bar_cache" in readiness.columns else 0
    research = int(readiness["research_artifact"].astype(bool).sum()) if not readiness.empty and "research_artifact" in readiness.columns else 0
    protected = int(readiness["protected_live_or_config"].astype(bool).sum()) if not readiness.empty and "protected_live_or_config" in readiness.columns else 0

    if accepted > 0:
        decision = "stage044_orderflow_depth_has_schema_ready_dataset_needs_readonly_signal_audit"
        best_next_direction = "build_pit_depth_features_and_readonly_signal_audit_before_any_engine_rule"
        immediate = 0
    else:
        decision = "stage044_orderflow_depth_no_accepted_dataset_data_contract_only"
        best_next_direction = "import_authorized_mbp10_or_mbo_history_with_hashes_or_keep_route_blocked"
        immediate = 0

    return {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().replace(microsecond=0).isoformat(),
        "decision": decision,
        "best_next_direction": best_next_direction,
        "file_count": int(len(readiness)),
        "schema_candidate_file_count": int(schema_candidates),
        "schema_complete_file_count": int(schema_complete),
        "accepted_orderflow_dataset_count": int(accepted),
        "minute_or_bar_cache_count": int(minute_cache),
        "research_artifact_count": int(research),
        "protected_live_or_config_count": int(protected),
        "immediate_strategy_candidate_count": int(immediate),
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
            "Order Flow Imbalance 和 LOB 资料支持把多档盘口、订单增删改和成交流作为短周期压力特征；"
            "CME/Databento 文档也说明 MBO 是逐订单 L3，MBP-10 是前十档 L2。"
            "但这些特征只有在具备事件时间、接收/发布时间、连续日历、symbol 映射和源 hash 时才可做 PIT 审计。"
        ),
        "overfit_reflection_before": "否。本阶段不回测、不挑阈值，只检查 Stage043 第一优先级数据路线是否真的可用。",
        "overfit_reflection_after": "否。若无 accepted orderflow dataset，继续保持 data-first，避免用分钟线或研究成交事件制造伪微观结构特征。",
        "continue_value_before": "有。目标需要更强的高质量信号识别，orderflow/depth 是结构上不同于日线/AI桶的外生信息源。",
        "continue_value_after": (
            "有但取决于数据。没有授权 MBP10/MBO 历史时不能进入信号审计；若后续导入，下一步先做只读 PIT 深度特征审计，"
            "再决定是否进入真实引擎。"
        ),
    }


def write_report(inventory: pd.DataFrame, readiness: pd.DataFrame, summary: pd.DataFrame, data_contract: pd.DataFrame, decision: dict[str, Any]) -> None:
    cols = [
        "path",
        "asset_kind",
        "schema_validation_required",
        "schema_family",
        "schema_complete",
        "pit_rule_audit_allowed",
        "accepted_orderflow_dataset",
        "blocking_reasons",
    ]
    representative = readiness.sort_values(["asset_kind", "size_bytes"], ascending=[True, False]).head(80) if not readiness.empty else readiness
    lines = [
        "# Stage044 授权 orderflow/depth 数据合同与本地 readiness 审计",
        "",
        f"- line_id：`{LINE_ID}`",
        f"- 记录时间：{decision['generated_at']}",
        f"- 决策：`{decision['decision']}`",
        "- 阶段性质：只读数据合同/readiness；不回测、不改策略、不连接 CTP、不调用订单 API。",
        "",
        "## 外部调研与判断",
        "",
        "- Order Flow Imbalance/LOB 研究支持用盘口深度、订单增删改和成交流构造短周期压力特征。",
        "- CME MBO 资料说明 MBO 是逐订单、全深度、可看队列位置的 L3 数据；Databento MBP-10 资料说明 MBP-10 是前十档聚合深度事件。",
        "- 我的判断：这条路线是当前最有可能提供“高质量信号识别”的新信息源，但必须先满足 PIT 时间戳、接收/发布时间、连续覆盖、symbol 映射和源 hash。",
        "",
        "## Summary",
        "",
        _md_table(summary),
        "",
        "## Data Contract",
        "",
        _md_table(data_contract),
        "",
        "## Representative Rows",
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


def write_stage_record(summary: pd.DataFrame, data_contract: pd.DataFrame, decision: dict[str, Any]) -> Path:
    STAGES_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    path = STAGES_DIR / f"{timestamp}_stage044_orderflow_depth_contract.md"
    text = f"""# Stage044 授权 orderflow/depth 数据合同与本地 readiness 审计

- line_id：`{LINE_ID}`
- 当前模式：day
- 记录时间：{decision['generated_at']}
- 阶段性质：只读数据合同/readiness；不回测、不改策略、不连接 CTP、不调用下单
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：CME Market by Order、Databento MBO/MBP-10 schema、HftBacktest order book imbalance、LOB signal extraction 研究。
- 我的判断：orderflow/depth 是当前 C9 本地字段之外的优先新信息源，但必须先拿到授权 MBP10/MBO 历史和 hash；分钟线、研究 trade_events、保护日志都不能替代。

## 本次变更

- 新增脚本：`research/lines/{LINE_ID}/tools/stage044_orderflow_depth_contract.py`
- 新增测试：`tests/test_rebuilt_c9_v2_stage044_orderflow_depth_contract.py`
- 新增参数：`STAGE044_MAX_HEADER_SAMPLE_ROWS={MAX_HEADER_SAMPLE_ROWS}`
- 修改参数：无正式策略参数修改
- 删除参数：无

## 结果

- decision：`{decision['decision']}`
- best_next_direction：`{decision['best_next_direction']}`
- file_count：`{decision['file_count']}`
- schema_candidate_file_count：`{decision['schema_candidate_file_count']}`
- schema_complete_file_count：`{decision['schema_complete_file_count']}`
- accepted_orderflow_dataset_count：`{decision['accepted_orderflow_dataset_count']}`
- minute_or_bar_cache_count：`{decision['minute_or_bar_cache_count']}`
- research_artifact_count：`{decision['research_artifact_count']}`
- protected_live_or_config_count：`{decision['protected_live_or_config_count']}`
- immediate_strategy_candidate_count：`0`
- 策略变更：`False`
- true engine：`False`
- order API：`0`
- CTP：`False`

## Summary

{_md_table(summary)}

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
- data_contract：`{DATA_CONTRACT_PATH}`
- decision：`{DECISION_PATH}`
- report：`{REPORT_PATH}`
"""
    path.write_text(text, encoding="utf-8")
    return path


def run() -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    inventory = pd.DataFrame(iter_orderflow_paths(PROJECT_DIR))
    if inventory.empty:
        inventory = pd.DataFrame(
            columns=[
                "path",
                "asset_kind",
                "size_bytes",
                "data_like",
                "research_artifact",
                "protected_live_or_config",
                "minute_or_bar_cache",
                "schema_validation_required",
                "schema_complete",
                "pit_rule_audit_allowed",
                "accepted_orderflow_dataset",
                "rule_candidate_allowed",
                "true_engine_allowed",
                "order_api_allowed",
                "blocking_reason",
            ]
        )
    readiness = build_readiness(inventory, PROJECT_DIR)
    summary = summarize_readiness(readiness)
    data_contract = build_data_contract()
    decision = make_stage044_decision(readiness)
    write_report(inventory, readiness, summary, data_contract, decision)
    stage_record = write_stage_record(summary, data_contract, decision)

    inventory.to_csv(INVENTORY_PATH, index=False, encoding="utf-8-sig")
    readiness.to_csv(READINESS_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    data_contract.to_csv(DATA_CONTRACT_PATH, index=False, encoding="utf-8-sig")
    decision["outputs"] = {
        "inventory": str(INVENTORY_PATH),
        "readiness": str(READINESS_PATH),
        "summary": str(SUMMARY_PATH),
        "data_contract": str(DATA_CONTRACT_PATH),
        "decision": str(DECISION_PATH),
        "report": str(REPORT_PATH),
        "stage_record": str(stage_record),
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    return decision


if __name__ == "__main__":
    run()
