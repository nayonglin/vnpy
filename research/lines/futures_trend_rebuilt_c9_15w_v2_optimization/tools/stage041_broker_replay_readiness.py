from __future__ import annotations

from datetime import datetime
import gzip
import json
import os
from pathlib import Path
import re
from typing import Any

import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[4]
LINE_ID = "futures_trend_rebuilt_c9_15w_v2_optimization"
STAGE = "Stage041"
MODEL_TAG = "stage041_broker_replay_readiness_v1"
OUTPUT_PREFIX = "rebuilt_c9_v2_stage041_broker_replay_readiness"

LINE_DIR = PROJECT_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage041_broker_replay_readiness"
STAGES_DIR = LINE_DIR / "stages"

INVENTORY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_inventory_{MODEL_TAG}.csv"
READINESS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_readiness_{MODEL_TAG}.csv"
SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DATA_CONTRACT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_data_contract_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

INTEREST_RE = re.compile(
    r"(?<![a-z0-9])(execution_ledger|execution|trade_event|trade_events|position_change|position_changes|"
    r"fill|fills|deal|deals|order|orders|broker|production|same_source|replay|ctp|simnow)(?![a-z0-9])",
    re.I,
)

DATA_SUFFIXES = {".csv", ".json", ".jsonl", ".parquet", ".feather", ".gz"}
EXCLUDED_DIRS = {".git", ".py311", ".mamba-root", ".pytest_cache", ".ruff_cache", "__pycache__", "node_modules"}
MIN_ACCEPTED_COVERAGE_DAYS = int(os.getenv("STAGE041_MIN_ACCEPTED_COVERAGE_DAYS", "20"))
MAX_HEADER_SAMPLE_ROWS = int(os.getenv("STAGE041_MAX_HEADER_SAMPLE_ROWS", "200"))

SOURCE_LINKS = {
    "bailey_overfit_paper": "https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2507040",
    "portfolio_optimization_dangers_backtesting": "https://portfoliooptimizationbook.com/book/8.3-dangers-backtesting.html",
    "quantstart_transaction_costs": "https://www.quantstart.com/articles/Successful-Backtesting-of-Algorithmic-Trading-Strategies-Part-II/",
    "pysystemtrade_backtesting": "https://github.com/pst-group/pysystemtrade/blob/develop/docs/backtesting.md",
    "pysystemtrade_capital_correction": "https://qoppac.blogspot.com/2016/06/capital-correction-pysystemtrade.html",
}


SIGNAL_COLUMNS = {"signal_time", "signal_datetime", "signal_ts", "signal_id", "plan_id", "candidate_id"}
ORDER_COLUMNS = {"order_time", "order_datetime", "order_ts", "order_id", "vt_orderid", "order_volume", "order_price"}
FILL_COLUMNS = {"fill_time", "fill_datetime", "trade_time", "trade_datetime", "fill_ts", "trade_id", "vt_tradeid", "fill_volume", "fill_price"}
POSITION_COLUMNS = {"position_time", "position_datetime", "position_ts", "position_after", "net_position", "position_change"}
SYMBOL_COLUMNS = {"vt_symbol", "symbol", "instrument_id", "contract"}
SIDE_COLUMNS = {"direction", "side", "offset", "order_side"}


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
    return suffix in {".py", ".md", ".sh", ".cpp", ".hpp", ".yaml", ".yml", ".env"}


def _is_config(path: Path | str) -> bool:
    lower = _norm(path).lower()
    name = Path(lower).name
    return lower.endswith(".env") or lower.endswith(".local.env") or name.startswith("connect_") or name in {"vt_setting.json"}


def _is_research_or_backtest_artifact(path: Path | str) -> bool:
    parts = _parts(path)
    if len(parts) >= 2 and parts[0] == "research" and parts[1] == "lines":
        return True
    if parts and parts[0] == "tests":
        return True
    if len(parts) >= 3 and parts[0] == "examples" and parts[1] in {"portfolio_backtesting", "alpha_research"}:
        return True
    return False


def _is_protected_live_log(path: Path | str) -> bool:
    parts = _parts(path)
    lower = _norm(path).lower()
    protected_tokens = {"official_live", "ctp", "simnow", "readonly", "reconcile", "session_daemon", "timed_cycle", "phase_d"}
    if parts and parts[0] in {"official_live", ".vntrader", "log"}:
        return True
    return bool(protected_tokens.intersection(parts) and lower.endswith((".log", ".jsonl", ".json", ".csv", ".csv.gz", ".txt")))


def classify_replay_path(path: Path, size_bytes: int = 0) -> dict[str, Any]:
    text = _norm(path)
    lower = text.lower()
    data_like = _has_data_suffix(path)
    protected_live = _is_protected_live_log(path)
    research_artifact = _is_research_or_backtest_artifact(path)
    code_or_doc = _is_code_or_doc(path)
    config_file = _is_config(path)

    schema_required = False
    if protected_live:
        asset_kind = "protected_live_execution_log"
        blocking = "protected_live_log_not_signal_source"
    elif research_artifact:
        asset_kind = "research_or_backtest_artifact"
        blocking = "research_backtest_artifact_not_production_replay"
    elif config_file:
        asset_kind = "configuration_file"
        blocking = "configuration_file_not_replay_dataset"
    elif code_or_doc:
        asset_kind = "execution_code_or_doc"
        blocking = "code_or_doc_not_replay_dataset"
    elif data_like and INTEREST_RE.search(text):
        asset_kind = "potential_same_source_replay_schema_candidate"
        blocking = "schema_and_coverage_validation_required"
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
        "research_artifact": bool(research_artifact),
        "schema_validation_required": bool(schema_required),
        "rule_candidate_allowed": False,
        "true_engine_allowed": False,
        "order_api_allowed": False,
        "blocking_reason": blocking,
        "path_hint": lower,
    }


def _lower_columns(frame: pd.DataFrame) -> set[str]:
    return {str(col).strip().lower() for col in frame.columns}


def _has_any(columns: set[str], candidates: set[str]) -> bool:
    return bool(columns.intersection(candidates))


def _parse_time_column(frame: pd.DataFrame, names: set[str]) -> pd.Series | None:
    lower_map = {str(col).strip().lower(): col for col in frame.columns}
    for name in names:
        if name in lower_map:
            return pd.to_datetime(frame[lower_map[name]], errors="coerce")
    return None


def _coverage_days(frame: pd.DataFrame) -> int:
    for names in ({"fill_time", "fill_datetime", "trade_time", "trade_datetime"}, {"order_time", "order_datetime"}, {"signal_time", "signal_datetime"}):
        times = _parse_time_column(frame, names)
        if times is not None:
            return int(times.dropna().dt.date.nunique())
    return 0


def validate_replay_schema(frame: pd.DataFrame, min_coverage_days: int = MIN_ACCEPTED_COVERAGE_DAYS) -> dict[str, Any]:
    columns = _lower_columns(frame)
    has_signal = _has_any(columns, SIGNAL_COLUMNS)
    has_order = _has_any(columns, ORDER_COLUMNS)
    has_fill = _has_any(columns, FILL_COLUMNS)
    has_position = _has_any(columns, POSITION_COLUMNS)
    has_symbol = _has_any(columns, SYMBOL_COLUMNS)
    has_side = _has_any(columns, SIDE_COLUMNS)
    schema_complete = bool(has_signal and has_order and has_fill and has_position and has_symbol and has_side)

    signal_time = _parse_time_column(frame, {"signal_time", "signal_datetime", "signal_ts"})
    order_time = _parse_time_column(frame, {"order_time", "order_datetime", "order_ts"})
    fill_time = _parse_time_column(frame, {"fill_time", "fill_datetime", "trade_time", "trade_datetime", "fill_ts"})
    position_time = _parse_time_column(frame, {"position_time", "position_datetime", "position_ts"})

    has_time_order_violation = False
    if signal_time is not None and order_time is not None:
        has_time_order_violation |= bool((signal_time > order_time).fillna(False).any())
    if order_time is not None and fill_time is not None:
        has_time_order_violation |= bool((order_time > fill_time).fillna(False).any())
    if fill_time is not None and position_time is not None:
        has_time_order_violation |= bool((fill_time > position_time).fillna(False).any())

    coverage = _coverage_days(frame)
    reasons: list[str] = []
    if not schema_complete:
        if not has_signal:
            reasons.append("missing_signal_fields")
        if not has_order:
            reasons.append("missing_order_fields")
        if not has_fill:
            reasons.append("missing_fill_fields")
        if not has_position:
            reasons.append("missing_position_fields")
        if not has_symbol:
            reasons.append("missing_symbol_fields")
        if not has_side:
            reasons.append("missing_side_fields")
    if has_time_order_violation:
        reasons.append("time_order_violation")
    if coverage < min_coverage_days:
        reasons.append("coverage_days_below_minimum")

    replay_ready = bool(schema_complete and not has_time_order_violation and coverage >= min_coverage_days)
    return {
        "row_count_sampled": int(len(frame)),
        "column_count": int(len(frame.columns)),
        "columns": ",".join(map(str, frame.columns)),
        "has_signal_fields": bool(has_signal),
        "has_order_fields": bool(has_order),
        "has_fill_fields": bool(has_fill),
        "has_position_fields": bool(has_position),
        "has_symbol_fields": bool(has_symbol),
        "has_side_fields": bool(has_side),
        "schema_complete": bool(schema_complete),
        "coverage_day_count": int(coverage),
        "has_time_order_violation": bool(has_time_order_violation),
        "replay_ready": bool(replay_ready),
        "accepted_same_source_replay": bool(replay_ready),
        "blocking_reasons": ",".join(list(dict.fromkeys(reasons))),
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
                for key in ("data", "records", "rows", "events"):
                    if isinstance(data.get(key), list):
                        return pd.DataFrame(data[key][:MAX_HEADER_SAMPLE_ROWS])
                return pd.DataFrame([data])
    except Exception:
        return None
    return None


def iter_replay_paths(root: Path = PROJECT_DIR) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    root = root.resolve()
    for current, dirs, files in os.walk(root):
        dirs[:] = [item for item in dirs if item not in EXCLUDED_DIRS]
        current_path = Path(current)
        for name in files:
            relative = (current_path / name).relative_to(root)
            if not INTEREST_RE.search(_norm(relative)):
                continue
            file_path = current_path / name
            try:
                size_bytes = file_path.stat().st_size
            except OSError:
                size_bytes = 0
            rows.append(classify_replay_path(relative, size_bytes))
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
                        "coverage_day_count": 0,
                        "has_time_order_violation": False,
                        "replay_ready": False,
                        "accepted_same_source_replay": False,
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
                    "has_signal_fields": False,
                    "has_order_fields": False,
                    "has_fill_fields": False,
                    "has_position_fields": False,
                    "has_symbol_fields": False,
                    "has_side_fields": False,
                    "schema_complete": False,
                    "coverage_day_count": 0,
                    "has_time_order_violation": False,
                    "replay_ready": False,
                    "accepted_same_source_replay": False,
                    "blocking_reasons": str(row.get("blocking_reason", "")),
                }
            )
        result["rule_candidate_allowed"] = bool(result.get("accepted_same_source_replay", False))
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
                    "research_artifact_count": 0,
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
                "research_artifact_count": int(group["research_artifact"].astype(bool).sum()) if "research_artifact" in group else 0,
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
                "required_source": "same production broker or SimNow/CTP replay export generated before research use, not research backtest outputs",
                "required_fields": "signal_time,signal_id,order_time,order_id,fill_time,trade_id,position_time,vt_symbol,direction,offset,order_volume,fill_volume,order_price,fill_price,position_after",
                "required_checks": "signal_time<=order_time<=fill_time<=position_time, per_file_hash, source_system, export_time, coverage_days>=20, no manual posthoc labels, no protected-live-log feature extraction",
                "allowed_use": "execution cost/slippage/latency/partial-fill calibration and fail-closed reconciliation only after user approval",
                "forbidden_shortcut": "do_not_use_protected_live_logs_or_research_trade_events_as_alpha_features",
            }
        ]
    )


def make_stage041_decision(readiness: pd.DataFrame) -> dict[str, Any]:
    accepted = int(readiness["accepted_same_source_replay"].astype(bool).sum()) if not readiness.empty and "accepted_same_source_replay" in readiness.columns else 0
    schema_candidates = int(readiness["schema_validation_required"].astype(bool).sum()) if not readiness.empty and "schema_validation_required" in readiness.columns else 0
    schema_complete = int(readiness["schema_complete"].astype(bool).sum()) if not readiness.empty and "schema_complete" in readiness.columns else 0
    protected = int(readiness["protected_live_log"].astype(bool).sum()) if not readiness.empty and "protected_live_log" in readiness.columns else 0
    research = int(readiness["research_artifact"].astype(bool).sum()) if not readiness.empty and "research_artifact" in readiness.columns else 0

    if accepted > 0:
        decision = "stage041_broker_replay_has_accepted_dataset_needs_user_approved_cost_audit"
        best_next_direction = "predeclare_execution_cost_calibration_no_alpha_feature"
    else:
        decision = "stage041_broker_replay_no_accepted_same_source_dataset"
        if schema_candidates > 0 or schema_complete > 0:
            best_next_direction = "complete_schema_hash_coverage_and_time_order_validation_before_any_replay_audit"
        else:
            best_next_direction = "external_authorized_replay_or_real_cash_ledger_audit"

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
        "accepted_same_source_replay_count": int(accepted),
        "protected_live_log_count": int(protected),
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
            "交易执行回放的合理用途是校准滑点、成本、延迟、部分成交和风控 fail-closed 约束。"
            "结合 PBO/回测危险文献，不能把实盘日志、研究 trade_events 或事后成交表现反向作为 alpha 特征，"
            "否则会把选择偏差和未来信息带入 AI 选品。"
        ),
        "overfit_reflection_before": "否。本阶段只审计 same-source replay 数据合同，不跑收益、不新增交易规则。",
        "overfit_reflection_after": "否。即使发现候选文件，也只允许后续做执行成本校准，不允许作为入场信号。",
        "continue_value_before": "有。Stage040 后缺少 TqSdk 期权链权限，必须确认是否存在同源执行回放可用于提升回测真实性。",
        "continue_value_after": (
            "有但偏工程真实性；若没有 accepted replay，下一步只能导入授权 replay 或转真实现金账本/出入金约束，"
            "不能继续拿研究输出救参。"
        ),
    }


def write_report(inventory: pd.DataFrame, readiness: pd.DataFrame, summary: pd.DataFrame, data_contract: pd.DataFrame, decision: dict[str, Any]) -> None:
    top = readiness.sort_values(["asset_kind", "size_bytes"], ascending=[True, False]).head(60) if not readiness.empty else readiness
    lines = [
        "# Stage041 Broker/Production Same-Source Replay Readiness",
        "",
        f"- line_id：`{LINE_ID}`",
        f"- 记录时间：{decision['generated_at']}",
        f"- 决策：`{decision['decision']}`",
        "- 阶段性质：只读执行回放数据合同审计；不回测、不改策略、不连接 CTP、不调用订单 API。",
        "",
        "## 外部调研与判断",
        "",
        "- 回测过拟合与选择偏差文献要求记录试验次数和避免从结果反推规则。",
        "- 交易成本/滑点资料支持使用真实成交校准执行模型，但这属于执行层校准，不是 alpha 信号生成。",
        "- pysystemtrade 的生产化思路也把账户/执行现实约束与策略规则分层处理。",
        "- 我的判断：same-source replay 有价值，但只在字段、hash、时间顺序、覆盖和来源都通过后，用于成本/延迟校准；不能把实盘日志或研究 trade_events 直接喂给 AI 选品。",
        "",
        "## Summary",
        "",
        _md_table(summary),
        "",
        "## Data contract",
        "",
        _md_table(data_contract),
        "",
        "## Representative readiness rows",
        "",
        _md_table(
            top[
                [
                    "path",
                    "asset_kind",
                    "schema_validation_required",
                    "schema_complete",
                    "coverage_day_count",
                    "accepted_same_source_replay",
                    "blocking_reasons",
                ]
            ],
            max_rows=60,
        )
        if not top.empty
        else "_无记录_",
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


def write_stage_record(summary: pd.DataFrame, decision: dict[str, Any]) -> Path:
    STAGES_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    path = STAGES_DIR / f"{timestamp}_stage041_broker_replay_readiness.md"
    text = f"""# Stage041 Broker/Production Same-Source Replay Readiness

- line_id：`{LINE_ID}`
- 当前模式：day
- 记录时间：{decision['generated_at']}
- 阶段性质：只读执行回放数据合同审计；不回测、不改策略、不连接 CTP、不调用下单
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：Bailey/Lopez de Prado 回测过拟合、Portfolio Optimization 回测危险、QuantStart 交易成本、pysystemtrade backtesting/capital correction。
- 我的判断：同源执行回放可以提升滑点、延迟、部分成交和执行风控建模真实性，但不能作为 alpha 或 AI 选品输入；保护实盘日志、研究 trade_events、脚本/文档都不算 accepted replay。

## 本次变更

- 新增脚本：`research/lines/{LINE_ID}/tools/stage041_broker_replay_readiness.py`
- 新增测试：`tests/test_rebuilt_c9_v2_stage041_broker_replay_readiness.py`
- 新增参数：`STAGE041_MIN_ACCEPTED_COVERAGE_DAYS={MIN_ACCEPTED_COVERAGE_DAYS}`、`STAGE041_MAX_HEADER_SAMPLE_ROWS={MAX_HEADER_SAMPLE_ROWS}`
- 修改参数：无正式策略参数修改
- 删除参数：无

## 结果

- decision：`{decision['decision']}`
- best_next_direction：`{decision['best_next_direction']}`
- file_count：`{decision['file_count']}`
- schema_candidate_file_count：`{decision['schema_candidate_file_count']}`
- schema_complete_file_count：`{decision['schema_complete_file_count']}`
- accepted_same_source_replay_count：`{decision['accepted_same_source_replay_count']}`
- protected_live_log_count：`{decision['protected_live_log_count']}`
- research_artifact_count：`{decision['research_artifact_count']}`
- immediate_strategy_candidate_count：`0`
- 策略变更：`False`
- true engine：`False`
- order API：`0`
- CTP：`False`

## Summary

{_md_table(summary)}

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
    inventory = pd.DataFrame(iter_replay_paths(PROJECT_DIR))
    if inventory.empty:
        inventory = pd.DataFrame(
            columns=[
                "path",
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
                "path_hint",
            ]
        )
    readiness = build_readiness(inventory, PROJECT_DIR)
    summary = summarize_readiness(readiness)
    data_contract = build_data_contract()
    decision = make_stage041_decision(readiness)
    write_report(inventory, readiness, summary, data_contract, decision)
    stage_record = write_stage_record(summary, decision)

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
