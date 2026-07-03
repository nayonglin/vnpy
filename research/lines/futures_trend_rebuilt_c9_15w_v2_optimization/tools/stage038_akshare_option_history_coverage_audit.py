from __future__ import annotations

from datetime import datetime
import json
import multiprocessing as mp
import os
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[4]
LINE_ID = "futures_trend_rebuilt_c9_15w_v2_optimization"
STAGE = "Stage038"
MODEL_TAG = "stage038_akshare_option_history_coverage_audit_v1"
OUTPUT_PREFIX = "rebuilt_c9_v2_stage038_akshare_option_history_coverage_audit"

LINE_DIR = PROJECT_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage038_akshare_option_history_coverage_audit"
STAGES_DIR = LINE_DIR / "stages"

PROBE_PLAN_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_probe_plan_{MODEL_TAG}.csv"
PROBE_RESULTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_probe_results_{MODEL_TAG}.csv"
PRODUCT_COVERAGE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_coverage_{MODEL_TAG}.csv"
EXCHANGE_COVERAGE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_exchange_coverage_{MODEL_TAG}.csv"
DATA_CONTRACT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_data_contract_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

ENABLE_NETWORK_PROBE = os.getenv("STAGE038_ENABLE_NETWORK_PROBE", "1").strip() != "0"
PROBE_TIMEOUT_SECONDS = int(os.getenv("STAGE038_PROBE_TIMEOUT_SECONDS", "16"))
MAX_PROBES = int(os.getenv("STAGE038_MAX_PROBES", "40"))
MIN_YEARS_HIT = int(os.getenv("STAGE038_MIN_YEARS_HIT", "3"))

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

AKSHARE_TARGET_OPTION_MAP = {
    "SA.CZCE": {"exchange": "CZCE", "function_name": "option_hist_czce", "symbol": "纯碱期权"},
    "si.GFEX": {"exchange": "GFEX", "function_name": "option_hist_gfex", "symbol": "工业硅"},
    "FG.CZCE": {"exchange": "CZCE", "function_name": "option_hist_czce", "symbol": "玻璃期权"},
    "MA.CZCE": {"exchange": "CZCE", "function_name": "option_hist_czce", "symbol": "甲醇期权"},
    "OI.CZCE": {"exchange": "CZCE", "function_name": "option_hist_czce", "symbol": "菜籽油期权"},
    "AP.CZCE": {"exchange": "CZCE", "function_name": "option_hist_czce", "symbol": "苹果期权"},
    "rb.SHFE": {"exchange": "SHFE", "function_name": "option_hist_shfe", "symbol": "螺纹钢期权"},
    "SM.CZCE": {"exchange": "CZCE", "function_name": "option_hist_czce", "symbol": "锰硅期权"},
    "ru.SHFE": {"exchange": "SHFE", "function_name": "option_hist_shfe", "symbol": "天胶期权"},
    "SH.CZCE": {"exchange": "CZCE", "function_name": "option_hist_czce", "symbol": "烧碱期权"},
    "lh.DCE": {"exchange": "DCE", "function_name": "option_hist_dce", "symbol": "生猪期权"},
    "jd.DCE": {"exchange": "DCE", "function_name": "option_hist_dce", "symbol": "鸡蛋期权"},
}

AKSHARE_UNMAPPED_TARGETS = {
    "jm.DCE": "local_akshare_option_hist_dce_symbol_map_has_no_jm_or_coking_coal_option",
    "fu.SHFE": "local_akshare_option_hist_shfe_symbol_map_has_no_fu_or_fuel_oil_option",
}

TARGET_SAMPLE_DATES = {
    "CZCE": ("20210615", "20240603", "20260629"),
    "GFEX": ("20230724", "20250801", "20260629"),
    "SHFE": ("20250418", "20260629"),
    "DCE": ("20251016", "20260629"),
}

ADDITIONAL_ENDPOINT_PROBES = (
    {
        "target_product": "DCE.endpoint",
        "exchange": "DCE",
        "function_name": "option_hist_dce",
        "symbol": "豆粕期权",
        "trade_date": "20240603",
        "endpoint_family": "hist_chain",
        "plan_role": "dce_stage037_failure_recheck",
    },
    {
        "target_product": "DCE.endpoint",
        "exchange": "DCE",
        "function_name": "option_hist_dce",
        "symbol": "聚丙烯期权",
        "trade_date": "20251016",
        "endpoint_family": "hist_chain",
        "plan_role": "dce_official_doc_example_probe",
    },
    {
        "target_product": "ru.SHFE",
        "exchange": "SHFE",
        "function_name": "option_vol_shfe",
        "symbol": "天胶期权",
        "trade_date": "20250418",
        "endpoint_family": "series_iv",
        "plan_role": "shfe_iv_endpoint_probe",
    },
    {
        "target_product": "si.GFEX",
        "exchange": "GFEX",
        "function_name": "option_vol_gfex",
        "symbol": "工业硅",
        "trade_date": "20230724",
        "endpoint_family": "series_iv",
        "plan_role": "gfex_iv_endpoint_probe",
    },
)

SOURCE_LINKS = {
    "akshare_option_docs": "https://akshare.akfamily.xyz/data/option/option.html",
    "akshare_github": "https://github.com/akfamily/akshare",
    "akshare_changelog": "https://akshare.akfamily.xyz/changelog.html",
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


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or pd.isna(value):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_bool(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    return bool(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_无记录_"
    data = frame.head(max_rows).copy() if max_rows else frame.copy()
    return data.to_markdown(index=False)


def _probe_year(trade_date: str) -> int:
    return int(str(trade_date)[:4])


def _detect_columns(columns: list[str]) -> dict[str, bool]:
    joined = ",".join(columns)
    return {
        "has_iv_column": any(key in joined for key in ["隐含波动率", "SIGMA", "sigma", "impliedVolatility"]),
        "has_delta_column": any(key in joined for key in ["DELTA", "Delta", "德尔塔", "delta"]),
        "has_oi_column": any(key in joined for key in ["持仓量", "OPENINTEREST", "openInterest"]),
        "has_contract_column": any(key in joined for key in ["合约", "合约代码", "合约名称", "INSTRUMENTID"]),
        "has_publish_timestamp": any(key in joined for key in ["发布时间", "发布日期", "publish", "timestamp", "time"]),
    }


def build_probe_plan() -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for product in TARGET_PRODUCTS:
        mapping = AKSHARE_TARGET_OPTION_MAP.get(product)
        if not mapping:
            exchange = product.split(".")[-1]
            rows.append(
                {
                    "probe_id": f"unmapped_{product.replace('.', '_')}",
                    "target_product": product,
                    "exchange": exchange,
                    "function_name": "",
                    "symbol": "",
                    "trade_date": "",
                    "probe_year": 0,
                    "endpoint_family": "unmapped",
                    "plan_role": "target_without_local_akshare_option_symbol_map",
                    "target_has_akshare_symbol_map": False,
                    "plan_note": AKSHARE_UNMAPPED_TARGETS.get(product, "no_local_mapping"),
                }
            )
            continue
        dates = TARGET_SAMPLE_DATES[mapping["exchange"]]
        for trade_date in dates:
            rows.append(
                {
                    "probe_id": f"{product.replace('.', '_')}_{mapping['function_name']}_{trade_date}",
                    "target_product": product,
                    "exchange": mapping["exchange"],
                    "function_name": mapping["function_name"],
                    "symbol": mapping["symbol"],
                    "trade_date": trade_date,
                    "probe_year": _probe_year(trade_date),
                    "endpoint_family": "hist_chain",
                    "plan_role": "target_product_sparse_year_probe",
                    "target_has_akshare_symbol_map": True,
                    "plan_note": "sparse_probe_only_not_full_history_download",
                }
            )
    for item in ADDITIONAL_ENDPOINT_PROBES:
        rows.append(
            {
                "probe_id": f"{item['target_product'].replace('.', '_')}_{item['function_name']}_{item['trade_date']}",
                "target_product": item["target_product"],
                "exchange": item["exchange"],
                "function_name": item["function_name"],
                "symbol": item["symbol"],
                "trade_date": item["trade_date"],
                "probe_year": _probe_year(item["trade_date"]),
                "endpoint_family": item["endpoint_family"],
                "plan_role": item["plan_role"],
                "target_has_akshare_symbol_map": item["target_product"] in AKSHARE_TARGET_OPTION_MAP,
                "plan_note": "endpoint_diagnostic_not_product_coverage_gate",
            }
        )
    plan = pd.DataFrame(rows)
    return plan.head(MAX_PROBES).copy()


def classify_probe_outcome(probe: dict[str, Any] | pd.Series) -> dict[str, Any]:
    data = dict(probe)
    status = str(data.get("status", "")).strip()
    exchange = str(data.get("exchange", ""))
    rows = _as_int(data.get("rows"), 0)
    ok = status == "ok" and rows > 0
    has_iv = _as_bool(data.get("has_iv_column", False))
    has_oi = _as_bool(data.get("has_oi_column", False))
    has_contract = _as_bool(data.get("has_contract_column", False))
    has_timestamp = _as_bool(data.get("has_publish_timestamp", False))
    continuous_audit_passed = _as_bool(data.get("continuous_audit_passed", False))

    reasons: list[str] = []
    schema_ready = bool(ok and has_iv and has_oi and has_contract and has_timestamp and continuous_audit_passed)

    if ok:
        if not has_iv:
            reasons.append("missing_iv_column")
        if not has_oi:
            reasons.append("missing_open_interest_column")
        if not has_contract:
            reasons.append("missing_contract_column")
        if not has_timestamp:
            reasons.append("missing_publish_timestamp")
        if not continuous_audit_passed:
            reasons.append("single_or_sparse_year_probe")
        probe_status = "schema_ready_probe" if schema_ready else "sample_ok_not_continuous"
    elif status in {"disabled", "not_run"}:
        reasons.append("network_probe_disabled")
        probe_status = "not_run"
    elif status == "unmapped":
        reasons.append("target_product_not_in_local_akshare_symbol_map")
        probe_status = "target_unmapped_in_akshare_local_function"
    elif exchange == "DCE":
        reasons.append("probe_not_ok")
        reasons.append("dce_probe_failed_not_exchange_wide_rejection")
        probe_status = "endpoint_or_date_probe_failed_needs_alternative_probe"
    else:
        reasons.append("probe_not_ok")
        probe_status = "probe_failed_needs_source_or_date_check"

    result = dict(data)
    result["probe_status"] = probe_status
    result["schema_ready_probe"] = bool(schema_ready)
    result["rule_candidate_allowed"] = bool(schema_ready)
    result["blocking_reasons"] = ",".join(list(dict.fromkeys(reasons)))
    return result


def _akshare_probe_worker(function_name: str, kwargs: dict[str, Any], queue: mp.Queue) -> None:
    try:
        import akshare as ak

        func = getattr(ak, function_name)
        data = func(**kwargs)
        if isinstance(data, pd.DataFrame):
            columns = list(map(str, data.columns))
            detected = _detect_columns(columns)
            queue.put(
                {
                    "status": "ok",
                    "rows": int(len(data)),
                    "columns": columns,
                    "column_count": int(len(columns)),
                    "head_json": data.head(2).astype(str).to_dict(orient="records"),
                    **detected,
                }
            )
        elif data is None:
            queue.put({"status": "none", "rows": 0, "columns": [], "column_count": 0})
        else:
            queue.put({"status": "non_dataframe", "rows": 0, "columns": [], "column_count": 0, "type": type(data).__name__})
    except Exception as exc:
        queue.put({"status": "error", "rows": 0, "columns": [], "column_count": 0, "error_type": type(exc).__name__, "error_message": str(exc)[:500]})


def _run_one_probe(row: dict[str, Any], ctx: mp.context.BaseContext) -> dict[str, Any]:
    if not row.get("function_name"):
        return {
            "status": "unmapped",
            "rows": 0,
            "columns": [],
            "column_count": 0,
            "error_type": "UnmappedTarget",
            "error_message": str(row.get("plan_note", "")),
            "has_iv_column": False,
            "has_delta_column": False,
            "has_oi_column": False,
            "has_contract_column": False,
            "has_publish_timestamp": False,
        }
    if not ENABLE_NETWORK_PROBE:
        return {
            "status": "disabled",
            "rows": 0,
            "columns": [],
            "column_count": 0,
            "error_type": "",
            "error_message": "",
            "has_iv_column": False,
            "has_delta_column": False,
            "has_oi_column": False,
            "has_contract_column": False,
            "has_publish_timestamp": False,
        }
    queue: mp.Queue = ctx.Queue()
    kwargs = {"symbol": row["symbol"], "trade_date": row["trade_date"]}
    process = ctx.Process(target=_akshare_probe_worker, args=(str(row["function_name"]), kwargs, queue))
    process.start()
    process.join(PROBE_TIMEOUT_SECONDS)
    if process.is_alive():
        process.terminate()
        process.join(2)
        return {
            "status": "timeout",
            "rows": 0,
            "columns": [],
            "column_count": 0,
            "error_type": "Timeout",
            "error_message": f"timeout_after_{PROBE_TIMEOUT_SECONDS}s",
            "has_iv_column": False,
            "has_delta_column": False,
            "has_oi_column": False,
            "has_contract_column": False,
            "has_publish_timestamp": False,
        }
    if queue.empty():
        return {
            "status": "empty_message",
            "rows": 0,
            "columns": [],
            "column_count": 0,
            "error_type": "EmptyQueue",
            "error_message": "",
            "has_iv_column": False,
            "has_delta_column": False,
            "has_oi_column": False,
            "has_contract_column": False,
            "has_publish_timestamp": False,
        }
    return queue.get()


def run_akshare_history_probes(probe_plan: pd.DataFrame) -> pd.DataFrame:
    ctx = mp.get_context("spawn")
    rows: list[dict[str, Any]] = []
    for raw_row in probe_plan.to_dict("records"):
        result = _run_one_probe(raw_row, ctx)
        merged = {
            **raw_row,
            "status": str(result.get("status", "")),
            "rows": _as_int(result.get("rows"), 0),
            "column_count": _as_int(result.get("column_count"), 0),
            "columns": ",".join(map(str, result.get("columns", []) or [])),
            "has_iv_column": bool(result.get("has_iv_column", False)),
            "has_delta_column": bool(result.get("has_delta_column", False)),
            "has_oi_column": bool(result.get("has_oi_column", False)),
            "has_contract_column": bool(result.get("has_contract_column", False)),
            "has_publish_timestamp": bool(result.get("has_publish_timestamp", False)),
            "continuous_audit_passed": False,
            "error_type": str(result.get("error_type", "")),
            "error_message": str(result.get("error_message", "")),
            "head_json": json.dumps(_json_safe(result.get("head_json", [])), ensure_ascii=False),
        }
        rows.append(classify_probe_outcome(merged))
    return pd.DataFrame(rows)


def summarize_product_coverage(probes: pd.DataFrame, min_years_hit: int = MIN_YEARS_HIT) -> pd.DataFrame:
    if probes.empty:
        return pd.DataFrame()
    target_rows = probes[~probes["target_product"].astype(str).str.endswith(".endpoint")].copy()
    rows: list[dict[str, Any]] = []
    for product, group in target_rows.groupby("target_product", sort=True):
        exchange = str(group["exchange"].dropna().iloc[0]) if "exchange" in group and not group.empty else product.split(".")[-1]
        ok = group[group["status"].astype(str).eq("ok") & pd.to_numeric(group["rows"], errors="coerce").fillna(0).gt(0)]
        ok_years = sorted({int(year) for year in pd.to_numeric(ok.get("probe_year", pd.Series(dtype=int)), errors="coerce").dropna().astype(int)})
        ok_year_count = len(ok_years)
        has_iv = bool(ok["has_iv_column"].astype(bool).any()) if not ok.empty and "has_iv_column" in ok else False
        has_oi = bool(ok["has_oi_column"].astype(bool).any()) if not ok.empty and "has_oi_column" in ok else False
        has_contract = bool(ok["has_contract_column"].astype(bool).any()) if not ok.empty and "has_contract_column" in ok else False
        has_timestamp = bool(ok["has_publish_timestamp"].astype(bool).any()) if not ok.empty and "has_publish_timestamp" in ok else False
        all_success_timestamps = bool(ok["has_publish_timestamp"].astype(bool).all()) if not ok.empty and "has_publish_timestamp" in ok else False
        all_required_cols = has_iv and has_oi and has_contract
        continuous_ready = bool(group.get("continuous_audit_passed", pd.Series([False] * len(group))).astype(bool).any())

        reasons: list[str] = []
        if ok_year_count <= 0:
            reasons.append("no_successful_probe")
        if ok_year_count < min_years_hit:
            reasons.append("less_than_min_years_hit")
        if not has_iv:
            reasons.append("no_iv_column_in_successful_probes")
        if not has_oi:
            reasons.append("no_open_interest_column_in_successful_probes")
        if not has_contract:
            reasons.append("no_contract_column_in_successful_probes")
        if not has_timestamp:
            reasons.append("no_publish_timestamp_in_successful_probes")
        elif not all_success_timestamps:
            reasons.append("some_successful_probes_missing_publish_timestamp")
        if not continuous_ready:
            reasons.append("no_continuous_calendar_audit")

        schema_ready = bool(ok_year_count >= min_years_hit and all_required_cols and all_success_timestamps and continuous_ready)
        if schema_ready:
            coverage_status = "schema_ready_for_readonly_signal_audit"
        elif ok_year_count > 0:
            coverage_status = "sample_years_ok_not_pit_continuous"
        elif group["probe_status"].astype(str).eq("target_unmapped_in_akshare_local_function").all():
            coverage_status = "target_unmapped_in_akshare_local_function"
        else:
            coverage_status = "no_successful_probe_yet"

        rows.append(
            {
                "target_product": product,
                "exchange": exchange,
                "planned_probe_count": int(len(group)),
                "successful_probe_count": int(len(ok)),
                "ok_year_count": int(ok_year_count),
                "ok_years": ",".join(map(str, ok_years)),
                "has_iv_any_success": bool(has_iv),
                "has_oi_any_success": bool(has_oi),
                "has_contract_any_success": bool(has_contract),
                "has_publish_timestamp_any_success": bool(has_timestamp),
                "continuous_audit_passed": bool(continuous_ready),
                "schema_ready_product": bool(schema_ready),
                "coverage_status": coverage_status,
                "blocking_reasons": ",".join(list(dict.fromkeys(reasons))),
            }
        )
    return pd.DataFrame(rows).sort_values(["schema_ready_product", "exchange", "target_product"], ascending=[False, True, True])


def summarize_exchange_coverage(product_coverage: pd.DataFrame) -> pd.DataFrame:
    if product_coverage.empty:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    for exchange, group in product_coverage.groupby("exchange", sort=True):
        successful_probe_count = (
            group["successful_probe_count"].astype(int)
            if "successful_probe_count" in group
            else pd.Series([0] * len(group), index=group.index)
        )
        blocking_reasons = (
            ",".join(group["blocking_reasons"].astype(str)).split(",")
            if "blocking_reasons" in group
            else []
        )
        rows.append(
            {
                "exchange": exchange,
                "target_product_count": int(len(group)),
                "successful_product_count": int(successful_probe_count.gt(0).sum()),
                "schema_ready_product_count": int(group["schema_ready_product"].astype(bool).sum()),
                "coverage_statuses": ",".join(sorted(set(group["coverage_status"].astype(str)))),
                "blocking_reasons": ",".join(sorted(set(blocking_reasons) - {""})),
            }
        )
    return pd.DataFrame(rows)


def build_data_contract(product_coverage: pd.DataFrame, probes: pd.DataFrame) -> pd.DataFrame:
    missing_or_blocked = ",".join(
        product_coverage.loc[~product_coverage["schema_ready_product"].astype(bool), "target_product"].astype(str)
    ) if not product_coverage.empty else ""
    dce_status = ",".join(
        sorted(set(probes.loc[probes["exchange"].astype(str).eq("DCE"), "probe_status"].astype(str)))
    ) if not probes.empty and "exchange" in probes else ""
    return pd.DataFrame(
        [
            {
                "contract_id": "akshare_commodity_option_chain_pit_history",
                "minimum_coverage": "2018-01-01 to 2026-06-30 daily PIT option chain; sparse probes are not enough",
                "required_fields": "trade_date,publish_or_exchange_timestamp,exchange,underlying_product,underlying_contract,option_contract,call_put,strike,expiry,last,settlement,volume,open_interest,implied_vol,delta,raw_hash,source_url",
                "required_audit": "raw_hash_per_trade_date,stable_symbol_map,no_future_publish_time,continuous_calendar_by_product,endpoint_version_or_code_hash",
                "current_blocked_targets": missing_or_blocked,
                "dce_probe_interpretation": dce_status,
                "forbidden_shortcut": "do_not_treat_ok_sample_date_or_option_vol_series_as_continuous_tradeable_iv_skew_feature",
            }
        ]
    )


def make_stage038_decision(product_coverage: pd.DataFrame, exchange_coverage: pd.DataFrame, probes: pd.DataFrame) -> dict[str, Any]:
    schema_ready_count = int(product_coverage["schema_ready_product"].astype(bool).sum()) if not product_coverage.empty else 0
    successful_product_count = int(product_coverage["successful_probe_count"].astype(int).gt(0).sum()) if not product_coverage.empty and "successful_probe_count" in product_coverage else 0
    successful_probe_count = int((probes["status"].astype(str).eq("ok") & pd.to_numeric(probes["rows"], errors="coerce").fillna(0).gt(0)).sum()) if not probes.empty else 0
    dce_alt_needed = bool(
        not probes.empty
        and probes["exchange"].astype(str).eq("DCE").any()
        and probes["probe_status"].astype(str).eq("endpoint_or_date_probe_failed_needs_alternative_probe").any()
    )

    if schema_ready_count > 0:
        decision = "stage038_akshare_option_history_partial_schema_ready_needs_readonly_signal_spec"
        best_next_direction = "freeze_one_iv_skew_hypothesis_and_run_readonly_signal_audit_only"
    else:
        decision = "stage038_akshare_option_history_not_continuous_keep_data_contract"
        best_next_direction = "build_full_pit_option_chain_history_or_switch_to_authorized_orderflow"

    return {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().replace(microsecond=0).isoformat(),
        "decision": decision,
        "best_next_direction": best_next_direction,
        "target_product_count": int(len(product_coverage)),
        "successful_product_count": successful_product_count,
        "schema_ready_product_count": schema_ready_count,
        "exchange_count": int(len(exchange_coverage)),
        "probe_count": int(len(probes)),
        "successful_probe_count": successful_probe_count,
        "dce_alternative_probe_required": bool(dce_alt_needed),
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
            "AKShare 官方文档和本机源码确认商品期权 hist/vol 接口存在，且 changelog 显示 option_hist_dce 近期有修复记录。"
            "这支持继续做覆盖审计；但公共接口样本不包含可验证发布时间，也没有连续日历/hash，因此不能直接作为 AI 特征或交易规则输入。"
        ),
        "overfit_reflection_before": (
            "否。本阶段只检查公共接口是否能形成 PIT 数据合同，不回测、不调阈值、不选品种方向。"
        ),
        "overfit_reflection_after": (
            "否。即使样本成功，也只记录覆盖和缺口；没有把某个成功日期或失败日期转化成策略规则。"
        ),
        "continue_value_before": (
            "有。Stage037 证明期权 IV/skew 有接口但缺连续历史；继续确认覆盖能决定这条路线是否值得数据工程投入。"
        ),
        "continue_value_after": (
            "有但受限。若不能补齐 PIT 时间戳、raw hash 和连续覆盖，期权路线只能停在数据合同，不能进入回测优化。"
        ),
    }


def _write_report(
    decision: dict[str, Any],
    probe_plan: pd.DataFrame,
    probes: pd.DataFrame,
    product_coverage: pd.DataFrame,
    exchange_coverage: pd.DataFrame,
    data_contract: pd.DataFrame,
) -> None:
    lines = [
        "# Stage038 AKShare 商品期权历史覆盖审计",
        "",
        f"- line_id：`{LINE_ID}`",
        f"- 记录时间：{decision['generated_at']}",
        f"- 决策：`{decision['decision']}`",
        "- 阶段性质：AKShare 公共接口小矩阵覆盖审计；不回测、不改策略、不连接 CTP、不调用订单 API。",
        "",
        "## 外部调研与判断",
        "",
        "- AKShare 官方期权文档列出 `option_hist_dce/czce/shfe/gfex` 与 `option_vol_shfe/gfex`；GitHub README 指向官方中文文档，changelog 显示 1.17.68 对商品期权接口做过重命名并修复 `option_hist_dce`。",
        "- 本机 AKShare 源码显示 DCE 支持 `鸡蛋期权/生猪期权`，但未见 `焦煤期权`；SHFE 支持 `螺纹钢期权/天胶期权`，未见 `燃料油期权`。",
        "- 我的判断：公共接口可以作为复水入口候选，但样本探针不是 PIT 数据；必须补 raw hash、发布时间和连续日历后才能谈 IV/skew 信号。",
        "",
        "## Probe plan",
        "",
        _md_table(probe_plan, max_rows=40),
        "",
        "## Probe results",
        "",
        _md_table(
            probes[
                [
                    "probe_id",
                    "target_product",
                    "exchange",
                    "function_name",
                    "symbol",
                    "trade_date",
                    "status",
                    "rows",
                    "has_iv_column",
                    "has_oi_column",
                    "has_publish_timestamp",
                    "probe_status",
                    "blocking_reasons",
                ]
            ],
            max_rows=40,
        ),
        "",
        "## Product coverage",
        "",
        _md_table(product_coverage),
        "",
        "## Exchange coverage",
        "",
        _md_table(exchange_coverage),
        "",
        "## Data contract",
        "",
        _md_table(data_contract),
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


def _write_stage_record(
    decision: dict[str, Any],
    probe_plan: pd.DataFrame,
    probes: pd.DataFrame,
    product_coverage: pd.DataFrame,
    exchange_coverage: pd.DataFrame,
) -> Path:
    STAGES_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    path = STAGES_DIR / f"{timestamp}_stage038_akshare_option_history_coverage_audit.md"
    text = f"""# Stage038 AKShare 商品期权历史覆盖审计

- line_id：`{LINE_ID}`
- 当前模式：day
- 记录时间：{decision['generated_at']}
- 阶段性质：只读数据覆盖/接口稳定性审计；不回测、不改策略、不连接 CTP、不调用下单
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：AKShare 官方期权数据文档、AKShare GitHub README、AKShare changelog。
- 我的判断：AKShare 可以作为公开商品期权链复水入口候选，但当前只验证稀疏样本，不能证明 2018-2026 连续 PIT 历史；样本成功也不能直接转成 AI 特征。

## 本次变更

- 新增脚本：`research/lines/{LINE_ID}/tools/stage038_akshare_option_history_coverage_audit.py`
- 新增测试：`tests/test_rebuilt_c9_v2_stage038_akshare_option_history_coverage_audit.py`
- 新增参数：`STAGE038_ENABLE_NETWORK_PROBE={int(ENABLE_NETWORK_PROBE)}`、`STAGE038_PROBE_TIMEOUT_SECONDS={PROBE_TIMEOUT_SECONDS}`、`STAGE038_MAX_PROBES={MAX_PROBES}`、`STAGE038_MIN_YEARS_HIT={MIN_YEARS_HIT}`
- 修改参数：无正式策略参数修改
- 删除参数：无

## 结果

- decision：`{decision['decision']}`
- best_next_direction：`{decision['best_next_direction']}`
- probe_count：`{decision['probe_count']}`
- successful_probe_count：`{decision['successful_probe_count']}`
- target_product_count：`{decision['target_product_count']}`
- successful_product_count：`{decision['successful_product_count']}`
- schema_ready_product_count：`{decision['schema_ready_product_count']}`
- dce_alternative_probe_required：`{decision['dce_alternative_probe_required']}`
- immediate_strategy_candidate_count：`0`
- 策略变更：`False`
- true engine：`False`
- order API：`0`
- CTP：`False`

## Probe plan

{_md_table(probe_plan, max_rows=40)}

## Probe results

{_md_table(probes[['probe_id', 'target_product', 'exchange', 'function_name', 'symbol', 'trade_date', 'status', 'rows', 'has_iv_column', 'has_oi_column', 'has_publish_timestamp', 'probe_status', 'blocking_reasons']], max_rows=40)}

## Product coverage

{_md_table(product_coverage)}

## Exchange coverage

{_md_table(exchange_coverage)}

## 过拟合反思

- 运行前判断：{decision['overfit_reflection_before']}
- 运行后判断：{decision['overfit_reflection_after']}

## 继续价值反思

- 运行前判断：{decision['continue_value_before']}
- 运行后判断：{decision['continue_value_after']}

## 输出文件

- probe_plan：`{PROBE_PLAN_PATH}`
- probe_results：`{PROBE_RESULTS_PATH}`
- product_coverage：`{PRODUCT_COVERAGE_PATH}`
- exchange_coverage：`{EXCHANGE_COVERAGE_PATH}`
- data_contract：`{DATA_CONTRACT_PATH}`
- decision：`{DECISION_PATH}`
- report：`{REPORT_PATH}`
"""
    path.write_text(text, encoding="utf-8")
    return path


def run() -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    probe_plan = build_probe_plan()
    probes = run_akshare_history_probes(probe_plan)
    product_coverage = summarize_product_coverage(probes, min_years_hit=MIN_YEARS_HIT)
    exchange_coverage = summarize_exchange_coverage(product_coverage)
    data_contract = build_data_contract(product_coverage, probes)
    decision = make_stage038_decision(product_coverage, exchange_coverage, probes)
    _write_report(decision, probe_plan, probes, product_coverage, exchange_coverage, data_contract)
    stage_record = _write_stage_record(decision, probe_plan, probes, product_coverage, exchange_coverage)

    probe_plan.to_csv(PROBE_PLAN_PATH, index=False, encoding="utf-8-sig")
    probes.to_csv(PROBE_RESULTS_PATH, index=False, encoding="utf-8-sig")
    product_coverage.to_csv(PRODUCT_COVERAGE_PATH, index=False, encoding="utf-8-sig")
    exchange_coverage.to_csv(EXCHANGE_COVERAGE_PATH, index=False, encoding="utf-8-sig")
    data_contract.to_csv(DATA_CONTRACT_PATH, index=False, encoding="utf-8-sig")
    decision["outputs"] = {
        "probe_plan": str(PROBE_PLAN_PATH),
        "probe_results": str(PROBE_RESULTS_PATH),
        "product_coverage": str(PRODUCT_COVERAGE_PATH),
        "exchange_coverage": str(EXCHANGE_COVERAGE_PATH),
        "data_contract": str(DATA_CONTRACT_PATH),
        "decision": str(DECISION_PATH),
        "report": str(REPORT_PATH),
        "stage_record": str(stage_record),
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    return decision


if __name__ == "__main__":
    run()
