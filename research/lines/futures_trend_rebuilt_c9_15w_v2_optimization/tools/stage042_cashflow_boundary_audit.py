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
STAGE = "Stage042"
MODEL_TAG = "stage042_cashflow_boundary_audit_v1"
OUTPUT_PREFIX = "rebuilt_c9_v2_stage042_cashflow_boundary_audit"

LINE_DIR = PROJECT_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage042_cashflow_boundary_audit"
STAGES_DIR = LINE_DIR / "stages"

INVENTORY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_inventory_{MODEL_TAG}.csv"
READINESS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_readiness_{MODEL_TAG}.csv"
SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DATA_CONTRACT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_data_contract_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

INTEREST_RE = re.compile(
    r"(?<![a-z0-9])(cash|capital|ledger|account|balance|equity|deposit|withdraw|withdrawal|transfer|"
    r"statement|settlement|出入金|入金|出金|资金|权益|账户|结算)(?![a-z0-9])",
    re.I,
)
DATA_SUFFIXES = {".csv", ".json", ".jsonl", ".xlsx", ".xls", ".parquet", ".feather", ".gz"}
EXCLUDED_DIRS = {".git", ".py311", ".mamba-root", ".pytest_cache", ".ruff_cache", "__pycache__", "node_modules"}
MAX_HEADER_SAMPLE_ROWS = int(os.getenv("STAGE042_MAX_HEADER_SAMPLE_ROWS", "200"))

DATE_COLUMNS = {"date", "trade_date", "business_date", "statement_date", "datetime", "timestamp"}
ACCOUNT_COLUMNS = {"broker_account", "account_id", "investor_id", "account", "账户", "资金账号"}
FLOW_ID_COLUMNS = {"cash_flow_id", "flow_id", "transfer_id", "external_cash_flow_id", "流水号", "资金流水号"}
FLOW_TYPE_COLUMNS = {"flow_type", "cash_flow_type", "type", "direction", "入出金类型", "业务类型"}
FLOW_AMOUNT_COLUMNS = {"cash_flow_amount", "amount", "transfer_amount", "deposit_withdraw_amount", "发生金额", "出入金金额"}
EQUITY_COLUMNS = {"account_equity", "equity", "balance", "dynamic_equity", "客户权益", "动态权益", "账户权益"}
EQUITY_BEFORE_COLUMNS = {"account_equity_before", "equity_before", "balance_before", "before_equity", "变动前权益"}
EQUITY_AFTER_COLUMNS = {"account_equity_after", "equity_after", "balance_after", "after_equity", "变动后权益"}
SOURCE_COLUMNS = {"source_system", "source", "broker", "statement_source", "来源"}

SOURCE_LINKS = {
    "pysystemtrade_capital_correction": "https://qoppac.blogspot.com/2016/06/capital-correction-pysystemtrade.html",
    "pysystemtrade_backtesting": "https://github.com/pst-group/pysystemtrade/blob/develop/docs/backtesting.md",
    "time_weighted_return_investopedia": "https://www.investopedia.com/terms/t/time-weightedror.asp",
    "portfolio_return_math": "https://portfoliooptimizer.io/blog/the-mathematics-of-portfolio-return-simple-return-money-weighted-return-and-time-weighted-return/",
    "fia_automated_trading_risk_controls": "https://www.fia.org/sites/default/files/2024-07/FIA_WP_AUTOMATED%20TRADING%20RISK%20CONTROLS_FINAL_0.pdf",
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


def _is_research_artifact(path: Path | str) -> bool:
    parts = _parts(path)
    if len(parts) >= 2 and parts[0] == "research" and parts[1] == "lines":
        return True
    if parts and parts[0] == "tests":
        return True
    if len(parts) >= 2 and parts[0] == "examples":
        return True
    return False


def _is_protected_live_or_config(path: Path | str) -> bool:
    parts = set(_parts(path))
    lower = _norm(path).lower()
    protected_tokens = {"official_live", "ctp", "simnow", "readonly", "reconcile", "session_daemon", ".vntrader", "log"}
    if parts.intersection(protected_tokens) and lower.endswith((".csv", ".csv.gz", ".json", ".jsonl", ".log", ".txt", ".xlsx", ".xls")):
        return True
    return lower.endswith(".env") or lower.endswith(".local.env") or lower.endswith(".example.env")


def _is_code_or_doc(path: Path | str) -> bool:
    suffix = Path(_norm(path).lower()).suffix
    return suffix in {".py", ".md", ".sh", ".yaml", ".yml", ".cpp", ".hpp"}


def classify_cashflow_path(path: Path, size_bytes: int = 0) -> dict[str, Any]:
    text = _norm(path)
    data_like = _has_data_suffix(path)
    research = _is_research_artifact(path)
    protected = _is_protected_live_or_config(path)
    code_or_doc = _is_code_or_doc(path)
    schema_required = False

    if protected:
        asset_kind = "protected_live_or_config_cash_artifact"
        blocking = "protected_live_or_config_not_research_cash_ledger"
    elif research:
        asset_kind = "research_or_backtest_cash_artifact"
        blocking = "research_artifact_not_actual_cashflow_ledger"
    elif code_or_doc:
        asset_kind = "cash_code_or_doc"
        blocking = "code_or_doc_not_actual_cashflow_ledger"
    elif data_like and INTEREST_RE.search(text):
        asset_kind = "potential_actual_cashflow_ledger"
        blocking = "schema_source_hash_and_cashflow_method_validation_required"
        schema_required = True
    elif INTEREST_RE.search(text):
        asset_kind = "non_data_cash_hit"
        blocking = "not_data_file"
    else:
        asset_kind = "unclassified"
        blocking = "not_cashflow_related"

    return {
        "path": text,
        "asset_kind": asset_kind,
        "size_bytes": int(size_bytes or 0),
        "data_like": bool(data_like),
        "research_artifact": bool(research),
        "protected_live_or_config": bool(protected),
        "schema_validation_required": bool(schema_required),
        "actual_cashflow_ledger_accepted": False,
        "account_layer_audit_allowed": False,
        "strategy_objective_credit_allowed": False,
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


def _find_column(frame: pd.DataFrame, candidates: set[str]) -> str | None:
    lower_map = {str(col).strip().lower(): str(col) for col in frame.columns}
    for candidate in candidates:
        key = candidate.lower()
        if key in lower_map:
            return lower_map[key]
    return None


def validate_cashflow_schema(frame: pd.DataFrame) -> dict[str, Any]:
    columns = _lower_columns(frame)
    has_date = _has_any(columns, DATE_COLUMNS)
    has_account = _has_any(columns, ACCOUNT_COLUMNS)
    has_identity = _has_any(columns, FLOW_ID_COLUMNS)
    has_type = _has_any(columns, FLOW_TYPE_COLUMNS)
    has_amount = _has_any(columns, FLOW_AMOUNT_COLUMNS)
    has_equity = _has_any(columns, EQUITY_COLUMNS) or (_has_any(columns, EQUITY_BEFORE_COLUMNS) and _has_any(columns, EQUITY_AFTER_COLUMNS))
    has_source = _has_any(columns, SOURCE_COLUMNS)
    schema_complete = bool(has_date and has_account and has_identity and has_type and has_amount and has_equity and has_source)

    cashflow_sign_violation = False
    amount_col = _find_column(frame, FLOW_AMOUNT_COLUMNS)
    type_col = _find_column(frame, FLOW_TYPE_COLUMNS)
    if amount_col and type_col:
        amounts = pd.to_numeric(frame[amount_col], errors="coerce")
        types = frame[type_col].astype(str).str.lower()
        deposit_mask = types.str.contains("deposit|in|入金|转入", regex=True, na=False)
        withdraw_mask = types.str.contains("withdraw|out|出金|转出", regex=True, na=False)
        cashflow_sign_violation = bool(((deposit_mask & amounts.lt(0)) | (withdraw_mask & amounts.gt(0))).fillna(False).any())

    reasons: list[str] = []
    if not has_date:
        reasons.append("missing_date")
    if not has_account:
        reasons.append("missing_account")
    if not has_identity:
        reasons.append("missing_cashflow_identity")
    if not has_type:
        reasons.append("missing_flow_type")
    if not has_amount:
        reasons.append("missing_cashflow_amount")
    if not has_equity:
        reasons.append("missing_equity_fields")
    if not has_source:
        reasons.append("missing_source_system")
    if cashflow_sign_violation:
        reasons.append("cashflow_sign_violation")

    account_layer_allowed = bool(schema_complete and not cashflow_sign_violation)
    return {
        "row_count_sampled": int(len(frame)),
        "column_count": int(len(frame.columns)),
        "columns": ",".join(map(str, frame.columns)),
        "has_date": bool(has_date),
        "has_account": bool(has_account),
        "has_cashflow_identity": bool(has_identity),
        "has_flow_type": bool(has_type),
        "has_cashflow_amount": bool(has_amount),
        "has_equity_fields": bool(has_equity),
        "has_source_system": bool(has_source),
        "schema_complete": bool(schema_complete),
        "cashflow_sign_violation": bool(cashflow_sign_violation),
        "actual_cashflow_ledger_accepted": bool(account_layer_allowed),
        "account_layer_audit_allowed": bool(account_layer_allowed),
        "strategy_objective_credit_allowed": False,
        "blocking_reasons": ",".join(list(dict.fromkeys(reasons))),
    }


def classify_cashflow_objective_credit(uses_external_cashflow: bool, return_metric: str) -> dict[str, Any]:
    metric = str(return_metric).strip().lower()
    reasons: list[str] = []
    if uses_external_cashflow:
        reasons.append("external_cashflow_cannot_prove_strategy_return")
    if metric in {"money_weighted_return", "mwr", "irr"}:
        reasons.append("money_weighted_return_is_account_experience_not_strategy_twr")
    strategy_credit = bool(not uses_external_cashflow and metric in {"time_weighted_return", "twr", "strategy_nav"})
    return {
        "uses_external_cashflow": bool(uses_external_cashflow),
        "return_metric": metric,
        "strategy_objective_credit_allowed": bool(strategy_credit),
        "account_experience_metric_allowed": bool(metric in {"money_weighted_return", "mwr", "irr", "cash_equity_path"}),
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
                for key in ("data", "records", "rows", "cashflows", "events"):
                    if isinstance(data.get(key), list):
                        return pd.DataFrame(data[key][:MAX_HEADER_SAMPLE_ROWS])
                return pd.DataFrame([data])
        if lower.endswith((".xlsx", ".xls")):
            return pd.read_excel(path, nrows=MAX_HEADER_SAMPLE_ROWS)
    except Exception:
        return None
    return None


def iter_cashflow_paths(root: Path = PROJECT_DIR) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    root = root.resolve()
    for current, dirs, files in os.walk(root):
        dirs[:] = [item for item in dirs if item not in EXCLUDED_DIRS]
        current_path = Path(current)
        for name in files:
            relative = (current_path / name).relative_to(root)
            if not INTEREST_RE.search(_norm(relative)):
                continue
            try:
                size_bytes = (current_path / name).stat().st_size
            except OSError:
                size_bytes = 0
            rows.append(classify_cashflow_path(relative, size_bytes))
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
                        "actual_cashflow_ledger_accepted": False,
                        "account_layer_audit_allowed": False,
                        "strategy_objective_credit_allowed": False,
                        "blocking_reasons": "sample_read_failed_or_unsupported_format",
                    }
                )
            else:
                result.update(validate_cashflow_schema(sample))
        else:
            result.update(
                {
                    "row_count_sampled": 0,
                    "column_count": 0,
                    "columns": "",
                    "schema_complete": False,
                    "actual_cashflow_ledger_accepted": False,
                    "account_layer_audit_allowed": False,
                    "strategy_objective_credit_allowed": False,
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
                    "accepted_cashflow_ledger_count": 0,
                    "strategy_objective_credit_allowed_count": 0,
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
                "accepted_cashflow_ledger_count": int(group["actual_cashflow_ledger_accepted"].astype(bool).sum())
                if "actual_cashflow_ledger_accepted" in group
                else 0,
                "account_layer_audit_allowed_count": int(group["account_layer_audit_allowed"].astype(bool).sum())
                if "account_layer_audit_allowed" in group
                else 0,
                "strategy_objective_credit_allowed_count": int(group["strategy_objective_credit_allowed"].astype(bool).sum())
                if "strategy_objective_credit_allowed" in group
                else 0,
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
                "contract_id": "actual_cashflow_ledger_account_boundary",
                "required_source": "broker statement or bank transfer ledger exported before research use; not research profit-lock/cash-overlay outputs",
                "required_fields": "date,broker_account,cash_flow_id,flow_type,cash_flow_amount,account_equity_before/account_equity_after_or_account_equity,source_system",
                "required_checks": "per_file_hash,export_time,source_system,deposit_positive_withdrawal_negative,TWR_for_strategy,MWR_or_cash_equity_path_only_for_account_experience",
                "allowed_use": "live account capacity, capital call, withdrawal schedule, reserve runway and liquidity governance audit",
                "forbidden_shortcut": "do_not_count_external_deposits_or_withdrawal_timing_as_strategy_return_or_ai_alpha",
            }
        ]
    )


def make_stage042_decision(readiness: pd.DataFrame) -> dict[str, Any]:
    accepted = int(readiness["actual_cashflow_ledger_accepted"].astype(bool).sum()) if not readiness.empty and "actual_cashflow_ledger_accepted" in readiness.columns else 0
    schema_candidates = int(readiness["schema_validation_required"].astype(bool).sum()) if not readiness.empty and "schema_validation_required" in readiness.columns else 0
    schema_complete = int(readiness["schema_complete"].astype(bool).sum()) if not readiness.empty and "schema_complete" in readiness.columns else 0
    strategy_credit = int(readiness["strategy_objective_credit_allowed"].astype(bool).sum()) if not readiness.empty and "strategy_objective_credit_allowed" in readiness.columns else 0
    research = int(readiness["research_artifact"].astype(bool).sum()) if not readiness.empty and "research_artifact" in readiness.columns else 0
    protected = int(readiness["protected_live_or_config"].astype(bool).sum()) if not readiness.empty and "protected_live_or_config" in readiness.columns else 0

    if accepted > 0:
        decision = "stage042_cashflow_has_account_layer_dataset_no_strategy_credit"
        best_next_direction = "account_capacity_and_liquidity_governance_audit_only"
    else:
        decision = "stage042_cashflow_no_accepted_actual_cash_ledger"
        best_next_direction = "import_actual_broker_or_bank_cashflow_ledger_or_stop_account_layer_route"

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
        "accepted_cashflow_ledger_count": int(accepted),
        "strategy_objective_credit_allowed_count": int(strategy_credit),
        "research_artifact_count": int(research),
        "protected_live_or_config_count": int(protected),
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
            "资本校正和现金管理可以约束实盘可用风险资本；TWR/MWR 资料说明出入金会影响账户体验指标，"
            "但策略评价应剔除外部现金流影响。因此真实现金账本最多用于账户容量、追加保证金、出金和备用金治理，"
            "不能证明策略本身满足任意起点正收益或 AI 高质量信号。"
        ),
        "overfit_reflection_before": "否。本阶段只审计现金流边界，不用现金流修饰收益曲线。",
        "overfit_reflection_after": "否。外部入金/出金被明确排除出策略目标信用，避免把账户行为当 alpha。",
        "continue_value_before": "有。Stage041 后没有同源 replay，新数据缺失时只能确认账户层是否有真实现金账本可做可执行性约束。",
        "continue_value_after": (
            "有限。没有 accepted cashflow ledger 时，账户层也不能继续；若未来导入真实账本，也只能做实盘容量治理，"
            "不能替代新 PIT 信号或策略回测目标。"
        ),
    }


def write_report(inventory: pd.DataFrame, readiness: pd.DataFrame, summary: pd.DataFrame, data_contract: pd.DataFrame, decision: dict[str, Any]) -> None:
    top = readiness.sort_values(["asset_kind", "size_bytes"], ascending=[True, False]).head(60) if not readiness.empty else readiness
    cols = [
        "path",
        "asset_kind",
        "schema_validation_required",
        "schema_complete",
        "actual_cashflow_ledger_accepted",
        "strategy_objective_credit_allowed",
        "blocking_reasons",
    ]
    lines = [
        "# Stage042 真实现金账本/出入金边界审计",
        "",
        f"- line_id：`{LINE_ID}`",
        f"- 记录时间：{decision['generated_at']}",
        f"- 决策：`{decision['decision']}`",
        "- 阶段性质：只读账户现金流边界审计；不回测、不改策略、不连接 CTP、不调用订单 API。",
        "",
        "## 外部调研与判断",
        "",
        "- pysystemtrade capital correction 支持根据账户资金状态调整可用风险资本，但这属于账户治理。",
        "- TWR/MWR 资料说明外部出入金会改变账户体验指标，策略表现应使用剔除现金流影响的口径。",
        "- FIA 自动交易风险控制资料把 credit/collateral 与 pre-trade risk 区分开，提示账户容量治理不能替代信号 alpha。",
        "- 我的判断：真实现金账本如果存在，只能用于容量、追加保证金、出金/备用金约束，不能证明策略目标达成。",
        "",
        "## Summary",
        "",
        _md_table(summary),
        "",
        "## Data contract",
        "",
        _md_table(data_contract),
        "",
        "## Representative rows",
        "",
        _md_table(top[cols], max_rows=60) if not top.empty else "_无记录_",
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
    path = STAGES_DIR / f"{timestamp}_stage042_cashflow_boundary_audit.md"
    text = f"""# Stage042 真实现金账本/出入金边界审计

- line_id：`{LINE_ID}`
- 当前模式：day
- 记录时间：{decision['generated_at']}
- 阶段性质：只读账户现金流边界审计；不回测、不改策略、不连接 CTP、不调用下单
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：pysystemtrade capital correction/backtesting、TWR/MWR 回报口径、FIA 自动交易风险控制。
- 我的判断：真实现金账本可以约束账户容量、追加保证金、出金/备用金和流动性治理；但外部现金流不能计入策略目标信用，不能证明“任意起点一年以上正收益”或“AI 高质量信号”。

## 本次变更

- 新增脚本：`research/lines/{LINE_ID}/tools/stage042_cashflow_boundary_audit.py`
- 新增测试：`tests/test_rebuilt_c9_v2_stage042_cashflow_boundary_audit.py`
- 新增参数：`STAGE042_MAX_HEADER_SAMPLE_ROWS={MAX_HEADER_SAMPLE_ROWS}`
- 修改参数：无正式策略参数修改
- 删除参数：无

## 结果

- decision：`{decision['decision']}`
- best_next_direction：`{decision['best_next_direction']}`
- file_count：`{decision['file_count']}`
- schema_candidate_file_count：`{decision['schema_candidate_file_count']}`
- schema_complete_file_count：`{decision['schema_complete_file_count']}`
- accepted_cashflow_ledger_count：`{decision['accepted_cashflow_ledger_count']}`
- strategy_objective_credit_allowed_count：`{decision['strategy_objective_credit_allowed_count']}`
- research_artifact_count：`{decision['research_artifact_count']}`
- protected_live_or_config_count：`{decision['protected_live_or_config_count']}`
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
    inventory = pd.DataFrame(iter_cashflow_paths(PROJECT_DIR))
    if inventory.empty:
        inventory = pd.DataFrame(
            columns=[
                "path",
                "asset_kind",
                "size_bytes",
                "data_like",
                "research_artifact",
                "protected_live_or_config",
                "schema_validation_required",
                "actual_cashflow_ledger_accepted",
                "account_layer_audit_allowed",
                "strategy_objective_credit_allowed",
                "rule_candidate_allowed",
                "true_engine_allowed",
                "order_api_allowed",
                "blocking_reason",
            ]
        )
    readiness = build_readiness(inventory, PROJECT_DIR)
    summary = summarize_readiness(readiness)
    data_contract = build_data_contract()
    decision = make_stage042_decision(readiness)
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
