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
STAGE = "Stage045"
MODEL_TAG = "stage045_option_chain_acquisition_manifest_v1"
OUTPUT_PREFIX = "rebuilt_c9_v2_stage045_option_chain_acquisition_manifest"

LINE_DIR = PROJECT_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage045_option_chain_acquisition_manifest"
STAGES_DIR = LINE_DIR / "stages"

INVENTORY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_inventory_{MODEL_TAG}.csv"
READINESS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_readiness_{MODEL_TAG}.csv"
SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
TARGET_MANIFEST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_target_product_manifest_{MODEL_TAG}.csv"
REQUEST_MANIFEST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_vendor_request_manifest_{MODEL_TAG}.csv"
DATA_CONTRACT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_data_contract_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

REQUEST_START_DATE = "2018-01-01"
REQUEST_END_DATE = "2026-06-30"
MAX_HEADER_SAMPLE_ROWS = int(os.getenv("STAGE045_MAX_HEADER_SAMPLE_ROWS", "500"))

TARGET_PRODUCTS = (
    "SA.CZCE",
    "si.GFEX",
    "FG.CZCE",
    "MA.CZCE",
    "OI.CZCE",
    "jm.DCE",
    "AP.CZCE",
    "rb.SHFE",
    "fu.SHFE",
    "SM.CZCE",
    "ru.SHFE",
    "SH.CZCE",
    "lh.DCE",
    "jd.DCE",
)

CURRENT_REBUILT_AI_POOL_HINT = {"SA.CZCE", "si.GFEX", "FG.CZCE", "MA.CZCE", "OI.CZCE", "jm.DCE", "AP.CZCE", "SM.CZCE", "fu.SHFE"}

INTEREST_RE = re.compile(
    r"(?<![a-z0-9])(option[_-]?chain|options?[_-]?chain|option[_-]?quote|option[_-]?quotes|"
    r"implied[_-]?vol|iv[_-]?skew|greeks?|delta|gamma|vega|theta|strike|expiry|expiration|"
    r"期权链|期权行情|隐含波动率|希腊值)(?![a-z0-9])",
    re.I,
)
DATA_SUFFIXES = {".csv", ".json", ".jsonl", ".parquet", ".feather", ".gz", ".xlsx", ".xls"}
EXCLUDED_DIRS = {".git", ".py311", ".mamba-root", ".pytest_cache", ".ruff_cache", "__pycache__", "node_modules"}

QUOTE_TIME_COLUMNS = {"quote_datetime", "quote_time", "trade_datetime", "datetime", "timestamp", "date", "trade_date"}
PUBLISH_TIME_COLUMNS = {"publish_datetime", "publish_time", "receive_time", "received_time", "ts_recv", "source_publish_time"}
UNDERLYING_PRODUCT_COLUMNS = {"underlying_product", "product", "root_symbol", "underlying_root"}
UNDERLYING_SYMBOL_COLUMNS = {"underlying_symbol", "underlying", "underlying_vt_symbol", "futures_symbol"}
OPTION_SYMBOL_COLUMNS = {"option_symbol", "vt_symbol", "symbol", "instrument_id", "contract"}
EXCHANGE_COLUMNS = {"exchange", "market", "venue"}
EXPIRY_COLUMNS = {"expiry_date", "expiration_date", "expire_date", "maturity_date", "到期日"}
STRIKE_COLUMNS = {"strike", "strike_price", "exercise_price", "行权价"}
OPTION_TYPE_COLUMNS = {"option_type", "cp", "call_put", "right", "看涨看跌"}
UNDERLYING_PRICE_COLUMNS = {"underlying_price", "futures_price", "underlying_close", "标的价格"}
PRICE_COLUMNS = {"settlement", "close", "last_price", "bid_price", "ask_price", "option_price"}
IV_COLUMNS = {"implied_volatility", "iv", "iv_mid", "iv_settlement", "隐含波动率"}
DELTA_COLUMNS = {"delta", "option_delta"}
OI_COLUMNS = {"open_interest", "oi", "position", "持仓量"}
VOLUME_COLUMNS = {"volume", "vol", "成交量"}
SOURCE_COLUMNS = {"source_system", "source", "vendor", "dataset"}
SOURCE_HASH_COLUMNS = {"source_file_hash", "sha256", "source_hash", "data_hash", "raw_hash", "file_hash"}

SOURCE_LINKS = {
    "tqsdk_professional": "https://doc.shinnytech.com/tqsdk/latest/profession.html",
    "tqsdk_data_downloader": "https://tqsdk-python.readthedocs.io/en/latest/reference/tqsdk.tools.download.html",
    "tqsdk_market_data": "https://doc.shinnytech.com/tqsdk/latest/usage/mddatas.html",
    "ricequant_options": "https://www.ricequant.com/doc/rqdata/python/options-mod",
    "cme_greeks_iv": "https://www.cmegroup.com/market-data/greeks-and-implied-volatility-data.html",
    "databento_options": "https://databento.com/options",
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


def _is_research_or_probe_artifact(path: Path | str) -> bool:
    parts = _parts(path)
    if len(parts) >= 2 and parts[0] == "research" and parts[1] == "lines":
        return True
    if parts and parts[0] == "tests":
        return True
    if len(parts) >= 2 and parts[0] == "examples" and parts[1] in {"portfolio_backtesting", "alpha_research"}:
        return True
    return False


def _is_code_or_doc(path: Path | str) -> bool:
    return Path(_norm(path).lower()).suffix in {".py", ".md", ".sh", ".yaml", ".yml", ".txt", ".env"}


def classify_option_chain_path(path: Path, size_bytes: int = 0) -> dict[str, Any]:
    text = _norm(path)
    data_like = _has_data_suffix(path)
    research = _is_research_or_probe_artifact(path)
    code_or_doc = _is_code_or_doc(path)
    schema_required = False

    if research:
        asset_kind = "research_or_probe_artifact"
        blocking = "research_probe_or_backtest_artifact_not_vendor_option_chain_history"
    elif code_or_doc:
        asset_kind = "option_chain_code_or_doc"
        blocking = "code_or_doc_not_vendor_option_chain_history"
    elif data_like and INTEREST_RE.search(text):
        asset_kind = "potential_vendor_option_chain_schema_candidate"
        blocking = "schema_hash_pit_and_coverage_validation_required"
        schema_required = True
    elif INTEREST_RE.search(text):
        asset_kind = "non_data_option_chain_hit"
        blocking = "not_data_file"
    else:
        asset_kind = "unclassified"
        blocking = "not_option_chain_related"

    return {
        "path": text,
        "asset_kind": asset_kind,
        "size_bytes": int(size_bytes or 0),
        "data_like": bool(data_like),
        "research_artifact": bool(research),
        "schema_validation_required": bool(schema_required),
        "schema_complete": False,
        "pit_rule_audit_allowed": False,
        "accepted_option_chain_dataset": False,
        "rule_candidate_allowed": False,
        "true_engine_allowed": False,
        "order_api_allowed": False,
        "blocking_reason": blocking,
    }


def _lower_columns(frame: pd.DataFrame) -> set[str]:
    return {str(col).strip().lower() for col in frame.columns}


def _has_any(columns: set[str], candidates: set[str]) -> bool:
    return bool(columns.intersection({item.lower() for item in candidates}))


def validate_option_chain_schema(frame: pd.DataFrame) -> dict[str, Any]:
    columns = _lower_columns(frame)
    has_quote_time = _has_any(columns, QUOTE_TIME_COLUMNS)
    has_publish_time = _has_any(columns, PUBLISH_TIME_COLUMNS)
    has_underlying_product = _has_any(columns, UNDERLYING_PRODUCT_COLUMNS)
    has_underlying_symbol = _has_any(columns, UNDERLYING_SYMBOL_COLUMNS)
    has_option_symbol = _has_any(columns, OPTION_SYMBOL_COLUMNS)
    has_exchange = _has_any(columns, EXCHANGE_COLUMNS)
    has_expiry = _has_any(columns, EXPIRY_COLUMNS)
    has_strike = _has_any(columns, STRIKE_COLUMNS)
    has_option_type = _has_any(columns, OPTION_TYPE_COLUMNS)
    has_underlying_price = _has_any(columns, UNDERLYING_PRICE_COLUMNS)
    has_price = _has_any(columns, PRICE_COLUMNS)
    has_iv = _has_any(columns, IV_COLUMNS)
    has_delta = _has_any(columns, DELTA_COLUMNS)
    has_open_interest = _has_any(columns, OI_COLUMNS)
    has_volume = _has_any(columns, VOLUME_COLUMNS)
    has_source = _has_any(columns, SOURCE_COLUMNS)
    has_hash = _has_any(columns, SOURCE_HASH_COLUMNS)

    required_flags = {
        "has_quote_time": has_quote_time,
        "has_publish_or_receive_time": has_publish_time,
        "has_underlying_product": has_underlying_product,
        "has_underlying_symbol": has_underlying_symbol,
        "has_option_symbol": has_option_symbol,
        "has_exchange": has_exchange,
        "has_expiry": has_expiry,
        "has_strike": has_strike,
        "has_option_type": has_option_type,
        "has_underlying_price": has_underlying_price,
        "has_price": has_price,
        "has_iv": has_iv,
        "has_delta": has_delta,
        "has_open_interest": has_open_interest,
        "has_volume": has_volume,
        "has_source_system": has_source,
        "has_source_hash": has_hash,
    }
    reasons: list[str] = []
    for key, present in required_flags.items():
        if not present:
            reasons.append("missing_" + key.removeprefix("has_"))

    schema_complete = bool(all(required_flags.values()))
    return {
        "row_count_sampled": int(len(frame)),
        "column_count": int(len(frame.columns)),
        "columns": ",".join(map(str, frame.columns)),
        **{key: bool(value) for key, value in required_flags.items()},
        "schema_complete": bool(schema_complete),
        "pit_rule_audit_allowed": bool(schema_complete),
        "accepted_option_chain_dataset": bool(schema_complete),
        "blocking_reasons": ",".join(reasons),
    }


def build_target_product_manifest() -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for product in TARGET_PRODUCTS:
        root, exchange = product.split(".")
        rows.append(
            {
                "target_product": product,
                "product_root": root,
                "exchange": exchange,
                "requested_start_date": REQUEST_START_DATE,
                "requested_end_date": REQUEST_END_DATE,
                "required_if_listed": True,
                "current_rebuilt_ai_pool_hint": product in CURRENT_REBUILT_AI_POOL_HINT,
                "goal_jd_extension": product == "jd.DCE",
                "required_granularity": "daily_full_chain_minimum; tick_or_1min_quote_preferred",
                "required_vendor_return": "return_empty_with_official_no_listing_flag_if_product_had_no_listed_options",
            }
        )
    return pd.DataFrame(rows)


def build_vendor_request_manifest(target_manifest: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for row in target_manifest.to_dict("records"):
        rows.append(
            {
                "request_id": f"option_chain_{row['target_product']}_{REQUEST_START_DATE}_{REQUEST_END_DATE}",
                "target_product": row["target_product"],
                "exchange": row["exchange"],
                "start_date": REQUEST_START_DATE,
                "end_date": REQUEST_END_DATE,
                "minimum_frequency": "daily_chain",
                "preferred_frequency": "tick_or_1min_quotes_with_daily_settlement",
                "required_fields": (
                    "quote_datetime,publish_datetime,underlying_product,underlying_symbol,option_symbol,exchange,"
                    "expiry_date,strike,option_type,underlying_price,settlement/bid_price/ask_price,"
                    "implied_volatility,delta,open_interest,volume,source_system,source_file_hash"
                ),
                "required_checks_before_signal": "source_hash,continuous_calendar_by_product,official_no_listing_flag,pit_timestamp,roll_symbol_mapping,call_put_pair_integrity",
                "acceptance_gate": "schema_complete_and_product_calendar_covered_before_readonly_iv_skew_audit",
            }
        )
    return pd.DataFrame(rows)


def build_data_contract() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "contract_id": "vendor_commodity_option_chain_history",
                "required_access": "TqSdk professional DataDownloader, RQData commodity option APIs, or equivalent authorized vendor export",
                "required_fields": (
                    "quote_datetime,publish_datetime/receive_time,underlying_product,underlying_symbol,option_symbol,exchange,"
                    "expiry_date,strike,option_type,underlying_price,option_price_or_settlement,bid_price,ask_price,"
                    "implied_volatility,delta,open_interest,volume,source_system,source_file_hash"
                ),
                "required_pit_checks": "publish_or_exchange_timestamp,per_file_hash,continuous_calendar_by_product,official_no_listing_flag,call_put_pair_integrity,no_forward_filled_iv_before_publication",
                "allowed_use": "readonly IV level/skew/term-structure/stress audit; only after multi-product coverage passes may enter proxy or true engine review",
                "forbidden_shortcut": "do_not_use_single_day_probe_sparse_year_sample_or_installed_vendor_sdk_as_signal",
            }
        ]
    )


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
                for key in ("data", "records", "rows", "chains", "quotes", "options"):
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


def iter_option_chain_paths(root: Path = PROJECT_DIR) -> list[dict[str, Any]]:
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
            rows.append(classify_option_chain_path(relative, size_bytes))
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
                        "pit_rule_audit_allowed": False,
                        "accepted_option_chain_dataset": False,
                        "blocking_reasons": "sample_read_failed_or_unsupported_format",
                    }
                )
            else:
                result.update(validate_option_chain_schema(sample))
        else:
            result.update(
                {
                    "row_count_sampled": 0,
                    "column_count": 0,
                    "columns": "",
                    "schema_complete": False,
                    "pit_rule_audit_allowed": False,
                    "accepted_option_chain_dataset": False,
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
                    "accepted_option_chain_dataset_count": 0,
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
                "accepted_option_chain_dataset_count": int(group["accepted_option_chain_dataset"].astype(bool).sum()) if "accepted_option_chain_dataset" in group else 0,
                "pit_rule_audit_allowed_count": int(group["pit_rule_audit_allowed"].astype(bool).sum()) if "pit_rule_audit_allowed" in group else 0,
                "blocking_reasons": ",".join(sorted(set(",".join(group["blocking_reasons"].fillna("").astype(str)).split(",")) - {""}))
                if "blocking_reasons" in group
                else "",
            }
        )
    return pd.DataFrame(rows)


def make_stage045_decision(readiness: pd.DataFrame, target_manifest: pd.DataFrame) -> dict[str, Any]:
    accepted = int(readiness["accepted_option_chain_dataset"].astype(bool).sum()) if not readiness.empty and "accepted_option_chain_dataset" in readiness.columns else 0
    schema_candidates = int(readiness["schema_validation_required"].astype(bool).sum()) if not readiness.empty and "schema_validation_required" in readiness.columns else 0
    schema_complete = int(readiness["schema_complete"].astype(bool).sum()) if not readiness.empty and "schema_complete" in readiness.columns else 0
    research = int(readiness["research_artifact"].astype(bool).sum()) if not readiness.empty and "research_artifact" in readiness.columns else 0

    if accepted > 0:
        decision = "stage045_option_chain_has_accepted_dataset_needs_coverage_audit_before_signal"
        best_next_direction = "run_product_calendar_and_iv_skew_readonly_signal_audit"
    else:
        decision = "stage045_option_chain_acquisition_manifest_data_first_no_accepted_dataset"
        best_next_direction = "procure_or_import_vendor_option_chain_history_then_run_acceptance_gate"

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
        "accepted_option_chain_dataset_count": int(accepted),
        "research_artifact_count": int(research),
        "target_product_count": int(len(target_manifest)),
        "jd_included": bool(target_manifest["target_product"].eq("jd.DCE").any()),
        "current_ai_pool_hint_count": int(target_manifest["current_rebuilt_ai_pool_hint"].astype(bool).sum()) if not target_manifest.empty else 0,
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
            "TqSdk 专业版文档显示 DataDownloader 支持期货/期权历史数据；RQData 有国内商品期权主力月份接口，"
            "CME/Databento/Greeks-IV 资料说明期权链、IV、Greeks 是可采购数据形态。"
            "但只有带 PIT 发布时间/接收时间、完整链字段、source hash 和连续覆盖的数据，才能进入只读 IV/skew 信号审计。"
        ),
        "overfit_reflection_before": "否。本阶段不构造 IV/skew 规则，只把 vendor 期权链导入前置条件机器化。",
        "overfit_reflection_after": "否。没有 accepted option chain 时继续 data-first，避免把稀疏探针或 SDK 安装状态当信号。",
        "continue_value_before": "有。目标需要更强的 AI 选品和高质量信号，商品期权 IV/skew 是与日线趋势不同的信息源。",
        "continue_value_after": (
            "有但仍受数据约束。Stage045 给出了 jd 在内的目标产品 manifest 和验收合同；拿不到 vendor 历史链时不能进入规则研究。"
        ),
    }


def write_report(
    readiness: pd.DataFrame,
    summary: pd.DataFrame,
    target_manifest: pd.DataFrame,
    request_manifest: pd.DataFrame,
    data_contract: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    cols = [
        "path",
        "asset_kind",
        "schema_validation_required",
        "schema_complete",
        "pit_rule_audit_allowed",
        "accepted_option_chain_dataset",
        "blocking_reasons",
    ]
    representative = readiness.sort_values(["asset_kind", "size_bytes"], ascending=[True, False]).head(80) if not readiness.empty else readiness
    lines = [
        "# Stage045 vendor/TqSdk 商品期权链导入验收包",
        "",
        f"- line_id：`{LINE_ID}`",
        f"- 记录时间：{decision['generated_at']}",
        f"- 决策：`{decision['decision']}`",
        "- 阶段性质：只读数据采购/导入验收；不回测、不改策略、不连接 CTP、不调用订单 API。",
        "",
        "## 外部调研与判断",
        "",
        "- TqSdk 专业版 DataDownloader 支持期货、期权历史数据下载，且支持 tick 和任意 K 线周期。",
        "- RQData 文档提供国内商品期权主力月份接口，可作为商品期权覆盖/月份映射的备选参考。",
        "- CME/Databento/Greeks-IV 资料说明期权链、IV、Greeks 是可采购和可标准化的数据形态。",
        "- 我的判断：期权 IV/skew 路线值得保留，但必须等完整 vendor 历史链导入并通过 PIT/hash/连续覆盖验收。",
        "",
        "## Summary",
        "",
        _md_table(summary),
        "",
        "## Target Product Manifest",
        "",
        _md_table(target_manifest),
        "",
        "## Vendor Request Manifest",
        "",
        _md_table(request_manifest, max_rows=30),
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


def write_stage_record(summary: pd.DataFrame, target_manifest: pd.DataFrame, data_contract: pd.DataFrame, decision: dict[str, Any]) -> Path:
    STAGES_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    path = STAGES_DIR / f"{timestamp}_stage045_option_chain_acquisition_manifest.md"
    text = f"""# Stage045 vendor/TqSdk 商品期权链导入验收包

- line_id：`{LINE_ID}`
- 当前模式：day
- 记录时间：{decision['generated_at']}
- 阶段性质：只读数据采购/导入验收；不回测、不改策略、不连接 CTP、不调用下单
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：TqSdk 专业版/DataDownloader、TqSdk 合约行情历史数据、RQData options、CME Greeks/IV、Databento options。
- 我的判断：vendor 商品期权链是 Stage043 第二优先级的合理新信息源，但本阶段只建立导入验收包；没有 accepted 历史链前不能做 IV/skew 规则。

## 本次变更

- 新增脚本：`research/lines/{LINE_ID}/tools/stage045_option_chain_acquisition_manifest.py`
- 新增测试：`tests/test_rebuilt_c9_v2_stage045_option_chain_acquisition_manifest.py`
- 新增参数：`STAGE045_MAX_HEADER_SAMPLE_ROWS={MAX_HEADER_SAMPLE_ROWS}`
- 修改参数：无正式策略参数修改
- 删除参数：无

## 结果

- decision：`{decision['decision']}`
- best_next_direction：`{decision['best_next_direction']}`
- target_product_count：`{decision['target_product_count']}`
- jd_included：`{decision['jd_included']}`
- file_count：`{decision['file_count']}`
- schema_candidate_file_count：`{decision['schema_candidate_file_count']}`
- schema_complete_file_count：`{decision['schema_complete_file_count']}`
- accepted_option_chain_dataset_count：`{decision['accepted_option_chain_dataset_count']}`
- immediate_strategy_candidate_count：`0`
- 策略变更：`False`
- true engine：`False`
- order API：`0`
- CTP：`False`

## Summary

{_md_table(summary)}

## Target Product Manifest

{_md_table(target_manifest)}

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
- target_manifest：`{TARGET_MANIFEST_PATH}`
- request_manifest：`{REQUEST_MANIFEST_PATH}`
- data_contract：`{DATA_CONTRACT_PATH}`
- decision：`{DECISION_PATH}`
- report：`{REPORT_PATH}`
"""
    path.write_text(text, encoding="utf-8")
    return path


def run() -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    target_manifest = build_target_product_manifest()
    request_manifest = build_vendor_request_manifest(target_manifest)
    data_contract = build_data_contract()

    inventory = pd.DataFrame(iter_option_chain_paths(PROJECT_DIR))
    if inventory.empty:
        inventory = pd.DataFrame(
            columns=[
                "path",
                "asset_kind",
                "size_bytes",
                "data_like",
                "research_artifact",
                "schema_validation_required",
                "schema_complete",
                "pit_rule_audit_allowed",
                "accepted_option_chain_dataset",
                "rule_candidate_allowed",
                "true_engine_allowed",
                "order_api_allowed",
                "blocking_reason",
            ]
        )
    readiness = build_readiness(inventory, PROJECT_DIR)
    summary = summarize_readiness(readiness)
    decision = make_stage045_decision(readiness, target_manifest)
    write_report(readiness, summary, target_manifest, request_manifest, data_contract, decision)
    stage_record = write_stage_record(summary, target_manifest, data_contract, decision)

    inventory.to_csv(INVENTORY_PATH, index=False, encoding="utf-8-sig")
    readiness.to_csv(READINESS_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    target_manifest.to_csv(TARGET_MANIFEST_PATH, index=False, encoding="utf-8-sig")
    request_manifest.to_csv(REQUEST_MANIFEST_PATH, index=False, encoding="utf-8-sig")
    data_contract.to_csv(DATA_CONTRACT_PATH, index=False, encoding="utf-8-sig")
    decision["outputs"] = {
        "inventory": str(INVENTORY_PATH),
        "readiness": str(READINESS_PATH),
        "summary": str(SUMMARY_PATH),
        "target_manifest": str(TARGET_MANIFEST_PATH),
        "request_manifest": str(REQUEST_MANIFEST_PATH),
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
