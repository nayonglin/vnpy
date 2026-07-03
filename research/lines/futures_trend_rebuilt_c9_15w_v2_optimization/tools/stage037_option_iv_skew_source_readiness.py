from __future__ import annotations

from datetime import datetime
import importlib
import inspect
import json
import multiprocessing as mp
import os
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[4]
LINE_ID = "futures_trend_rebuilt_c9_15w_v2_optimization"
STAGE = "Stage037"
MODEL_TAG = "stage037_option_iv_skew_source_readiness_v1"
OUTPUT_PREFIX = "rebuilt_c9_v2_stage037_option_iv_skew_source_readiness"

LINE_DIR = PROJECT_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage037_option_iv_skew_source_readiness"
STAGES_DIR = LINE_DIR / "stages"

SOURCE_READINESS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_source_readiness_{MODEL_TAG}.csv"
TARGET_COVERAGE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_target_product_option_coverage_{MODEL_TAG}.csv"
AKSHARE_FUNCTIONS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_akshare_option_functions_{MODEL_TAG}.csv"
PROBE_RESULTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_probe_results_{MODEL_TAG}.csv"
DATA_CONTRACT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_data_contract_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

ENABLE_NETWORK_PROBE = os.getenv("STAGE037_ENABLE_NETWORK_PROBE", "1").strip() != "0"
PROBE_TIMEOUT_SECONDS = int(os.getenv("STAGE037_PROBE_TIMEOUT_SECONDS", "18"))
MAX_PROBES = int(os.getenv("STAGE037_MAX_PROBES", "4"))

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

STATIC_OPTION_SYMBOL_BY_PRODUCT = {
    "SA.CZCE": "纯碱期权",
    "si.GFEX": "工业硅",
    "FG.CZCE": "玻璃期权",
    "MA.CZCE": "甲醇期权",
    "OI.CZCE": "菜籽油期权",
    "jm.DCE": "焦煤期权",
    "AP.CZCE": "苹果期权",
    "rb.SHFE": "螺纹钢期权",
    "fu.SHFE": "燃料油期权",
    "SM.CZCE": "锰硅期权",
    "ru.SHFE": "橡胶期权",
    "SH.CZCE": "烧碱期权",
}

AKSHARE_PROBES = (
    {
        "probe_id": "akshare_dce_option_hist_m",
        "function_name": "option_hist_dce",
        "kwargs": {"symbol": "豆粕期权", "trade_date": "20240603"},
        "probe_scope": "DCE commodity option daily chain price/OI",
    },
    {
        "probe_id": "akshare_czce_option_hist_ma",
        "function_name": "option_hist_czce",
        "kwargs": {"symbol": "甲醇期权", "trade_date": "20240603"},
        "probe_scope": "CZCE commodity option daily chain price/OI",
    },
    {
        "probe_id": "akshare_shfe_option_vol_cu",
        "function_name": "option_vol_shfe",
        "kwargs": {"symbol": "铜期权", "trade_date": "20250418"},
        "probe_scope": "SHFE official option implied volatility table",
    },
    {
        "probe_id": "akshare_gfex_option_vol_si",
        "function_name": "option_vol_gfex",
        "kwargs": {"symbol": "工业硅", "trade_date": "20230724"},
        "probe_scope": "GFEX official option implied volatility table",
    },
)

SOURCE_LINKS = {
    "tqsdk_option_docs": "https://doc.shinnytech.com/tqsdk/latest/demo/option_base.html",
    "tqsdk_downloader_docs": "https://tqsdk-python.readthedocs.io/en/latest/reference/tqsdk.tools.download.html",
    "akshare_option_docs": "https://akshare.akfamily.xyz/data/option/option.html",
    "ricequant_option_greeks_docs": "https://www.ricequant.com/doc/rqdata/python/options-mod",
    "commodity_implied_skew_paper": "https://www.bcb.gov.br/pec/wps/ingl/wps479.pdf",
    "commodity_option_iv_returns_paper": "https://assets.super.so/e46b77e7-ee08-445e-b43f-4ffd88ae0a0e/files/2f2fc428-925c-4041-9f6d-bc387d904820.pdf",
    "cme_cvol_skew_article": "https://www.cmegroup.com/insights/economic-research/2023/is-cvol-skew-a-leading-indicator-of-price-trends-in-commodities-bonds-and-currency-markets.html",
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


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or pd.isna(value):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_bool(value: Any) -> bool:
    return bool(_as_int(value, 0))


def _module_status(module_name: str) -> tuple[str, str]:
    try:
        module = importlib.import_module(module_name)
        return "installed", str(getattr(module, "__version__", ""))
    except Exception as exc:
        return f"import_failed:{type(exc).__name__}", ""


def _inspect_akshare_option_functions() -> pd.DataFrame:
    status, _version = _module_status("akshare")
    rows: list[dict[str, Any]] = []
    if status != "installed":
        return pd.DataFrame(rows)
    import akshare as ak

    for name in sorted(dir(ak)):
        lower = name.lower()
        if not any(key in lower for key in ["option", "greek", "volatility"]):
            continue
        obj = getattr(ak, name)
        if not callable(obj):
            continue
        try:
            signature = str(inspect.signature(obj))
        except Exception:
            signature = ""
        doc = (getattr(obj, "__doc__", "") or "").strip().replace("\n", " ")
        is_commodity = int(name.startswith("option_hist_") or name.startswith("option_vol_") or name.startswith("option_commodity"))
        rows.append(
            {
                "function_name": name,
                "signature": signature,
                "is_commodity_option_endpoint": is_commodity,
                "doc_head": doc[:240],
            }
        )
    return pd.DataFrame(rows)


def build_target_product_option_coverage() -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for product in TARGET_PRODUCTS:
        option_name = STATIC_OPTION_SYMBOL_BY_PRODUCT.get(product, "")
        has_listed = bool(option_name)
        blocking = "" if has_listed else "no_listed_commodity_option_or_not_verified_for_target_product"
        rows.append(
            {
                "target_product": product,
                "option_symbol_name": option_name,
                "has_listed_option": bool(has_listed),
                "coverage_blocking_reason": blocking,
            }
        )
    return pd.DataFrame(rows)


def classify_option_source(source: dict[str, Any] | pd.Series) -> dict[str, Any]:
    data = dict(source)
    source_id = str(data.get("source_id", ""))
    source_type = str(data.get("source_type", ""))
    module_status = str(data.get("module_status", "installed"))
    calc_iv_available = _as_bool(data.get("calc_iv_available"))
    historical_chain_available = _as_bool(data.get("historical_chain_available"))
    pit_timestamp_available = _as_bool(data.get("pit_timestamp_available"))
    credential_available = _as_bool(data.get("credential_available"))
    permission_verified = _as_bool(data.get("permission_verified"))
    continuous_years_ready = _as_bool(data.get("continuous_years_ready"))
    target_total = _as_int(data.get("target_products_total"), 0)
    target_with_option = _as_int(data.get("target_products_with_listed_option"), 0)
    probe_success_count = _as_int(data.get("probe_success_count"), 0)

    reasons: list[str] = []
    if not module_status.startswith("installed"):
        reasons.append("module_not_available")
    if calc_iv_available and not historical_chain_available:
        reasons.append("no_historical_chain")
    if historical_chain_available and not pit_timestamp_available:
        reasons.append("no_verified_pit_timestamp")
    if target_total and target_with_option < target_total:
        reasons.append("incomplete_target_product_coverage")
    if historical_chain_available and not continuous_years_ready:
        reasons.append("no_continuous_2018_2026_history")
    if source_type == "credential_datafeed" and not credential_available:
        reasons.append("credentials_missing")
    if source_type == "history_downloader" and not permission_verified:
        reasons.append("history_download_permission_unverified")
    if source_type == "public_endpoint" and probe_success_count <= 0:
        reasons.append("no_successful_probe")

    schema_ready = bool(
        module_status.startswith("installed")
        and historical_chain_available
        and pit_timestamp_available
        and continuous_years_ready
        and probe_success_count > 0
        and target_total > 0
        and target_with_option == target_total
    )

    if not module_status.startswith("installed"):
        status = "missing_dependency"
        action = "install_or_enable_dependency_before_probe"
        priority = 5
    elif source_type == "sdk_calc" and calc_iv_available and not historical_chain_available:
        status = "compute_only_no_pit_history"
        action = "acquire_historical_option_chain_before_iv_skew_signal"
        priority = 40
    elif source_type == "credential_datafeed" and not credential_available:
        status = "credential_missing_no_probe"
        action = "configure_datafeed_credentials_before_history_probe"
        priority = 45
    elif source_type == "history_downloader" and not permission_verified:
        status = "permission_unverified_history_downloader_no_rule"
        action = "verify_historical_download_permission_on_small_option_chain"
        priority = 50
    elif schema_ready:
        status = "schema_ready_for_predeclared_readonly_signal_audit"
        action = "freeze_one_iv_skew_hypothesis_then_readonly_audit"
        priority = 80
    elif historical_chain_available:
        status = "partial_public_endpoint_probe_no_rule"
        action = "build_full_pit_history_schema_hash_and_coverage_before_signal"
        priority = 60 if probe_success_count > 0 else 55
    else:
        status = "not_rule_ready"
        action = "keep_as_capability_evidence_not_feature"
        priority = 20

    result = dict(data)
    result["source_id"] = source_id
    result["source_type"] = source_type
    result["source_status"] = status
    result["priority_score"] = priority
    result["recommended_next_action"] = action
    result["blocking_reasons"] = ",".join(list(dict.fromkeys(reasons)))
    result["schema_ready_for_signal_audit"] = bool(schema_ready)
    result["rule_candidate_allowed"] = bool(schema_ready)
    result["true_engine_allowed"] = False
    result["ab_allowed"] = False
    return result


def _akshare_probe_worker(function_name: str, kwargs: dict[str, Any], queue: mp.Queue) -> None:
    try:
        import akshare as ak

        func = getattr(ak, function_name)
        data = func(**kwargs)
        if isinstance(data, pd.DataFrame):
            columns = list(map(str, data.columns))
            queue.put(
                {
                    "status": "ok",
                    "rows": int(len(data)),
                    "columns": columns,
                    "column_count": int(len(columns)),
                    "head_json": data.head(2).astype(str).to_dict(orient="records"),
                }
            )
        else:
            queue.put({"status": "non_dataframe", "rows": 0, "columns": [], "type": type(data).__name__})
    except Exception as exc:
        queue.put({"status": "error", "rows": 0, "columns": [], "error_type": type(exc).__name__, "error_message": str(exc)[:500]})


def run_akshare_probes() -> pd.DataFrame:
    if not ENABLE_NETWORK_PROBE:
        return pd.DataFrame(
            [
                {
                    "probe_id": "network_probe_disabled",
                    "function_name": "",
                    "status": "disabled",
                    "rows": 0,
                    "columns": "",
                    "error_type": "",
                    "error_message": "",
                }
            ]
        )

    rows: list[dict[str, Any]] = []
    ctx = mp.get_context("spawn")
    for probe in AKSHARE_PROBES[:MAX_PROBES]:
        queue: mp.Queue = ctx.Queue()
        process = ctx.Process(target=_akshare_probe_worker, args=(probe["function_name"], probe["kwargs"], queue))
        process.start()
        process.join(PROBE_TIMEOUT_SECONDS)
        if process.is_alive():
            process.terminate()
            process.join(2)
            result = {"status": "timeout", "rows": 0, "columns": [], "error_type": "Timeout", "error_message": ""}
        elif queue.empty():
            result = {"status": "empty_message", "rows": 0, "columns": [], "error_type": "EmptyQueue", "error_message": ""}
        else:
            result = queue.get()
        rows.append(
            {
                "probe_id": probe["probe_id"],
                "function_name": probe["function_name"],
                "kwargs": json.dumps(probe["kwargs"], ensure_ascii=False, sort_keys=True),
                "probe_scope": probe["probe_scope"],
                "status": str(result.get("status", "")),
                "rows": _as_int(result.get("rows"), 0),
                "column_count": _as_int(result.get("column_count"), 0),
                "columns": ",".join(map(str, result.get("columns", []) or [])),
                "error_type": str(result.get("error_type", "")),
                "error_message": str(result.get("error_message", "")),
                "head_json": json.dumps(_json_safe(result.get("head_json", [])), ensure_ascii=False),
            }
        )
    return pd.DataFrame(rows)


def build_source_readiness(akshare_functions: pd.DataFrame, probes: pd.DataFrame, coverage: pd.DataFrame) -> pd.DataFrame:
    target_total = int(len(coverage))
    target_with_option = int(coverage["has_listed_option"].astype(bool).sum()) if not coverage.empty else 0
    probe_success = int((probes["status"].astype(str).eq("ok") & pd.to_numeric(probes["rows"], errors="coerce").fillna(0).gt(0)).sum()) if not probes.empty else 0
    probe_errors = int(len(probes) - probe_success) if not probes.empty else 0
    ak_status, ak_version = _module_status("akshare")
    tq_status, tq_version = _module_status("tqsdk")
    rq_status, rq_version = _module_status("rqdatac")
    opt_status, opt_version = _module_status("vnpy_optionmaster")

    has_ak_daily = bool(
        not akshare_functions.empty
        and akshare_functions["function_name"].astype(str).isin(
            ["option_hist_dce", "option_hist_czce", "option_hist_shfe", "option_hist_gfex"]
        ).any()
    )
    has_ak_vol = bool(
        not akshare_functions.empty
        and akshare_functions["function_name"].astype(str).isin(["option_vol_shfe", "option_vol_gfex"]).any()
    )

    rows = [
        {
            "source_id": "tqsdk_tafunc",
            "source_type": "sdk_calc",
            "module_status": tq_status,
            "version": tq_version,
            "calc_iv_available": int(tq_status == "installed"),
            "historical_chain_available": 0,
            "pit_timestamp_available": 0,
            "target_products_with_listed_option": 0,
            "target_products_total": target_total,
            "probe_success_count": 0,
            "probe_error_count": 0,
            "continuous_years_ready": 0,
            "credential_available": 0,
            "permission_verified": 0,
            "source_note": "TqSdk tafunc/get_impv can calculate IV if option chain prices already exist; it is not a PIT history source by itself.",
        },
        {
            "source_id": "tqsdk_data_downloader",
            "source_type": "history_downloader",
            "module_status": tq_status,
            "version": tq_version,
            "calc_iv_available": 0,
            "historical_chain_available": int(tq_status == "installed"),
            "pit_timestamp_available": int(tq_status == "installed"),
            "target_products_with_listed_option": 0,
            "target_products_total": target_total,
            "probe_success_count": 0,
            "probe_error_count": 0,
            "continuous_years_ready": 0,
            "credential_available": 0,
            "permission_verified": 0,
            "source_note": "TqSdk DataDownloader is documented for futures/options history but previous repo evidence showed professional-download permission can block it.",
        },
        {
            "source_id": "akshare_exchange_option_daily",
            "source_type": "public_endpoint",
            "module_status": ak_status,
            "version": ak_version,
            "calc_iv_available": int(has_ak_vol),
            "historical_chain_available": int(has_ak_daily or has_ak_vol),
            "pit_timestamp_available": 0,
            "target_products_with_listed_option": target_with_option,
            "target_products_total": target_total,
            "probe_success_count": probe_success,
            "probe_error_count": probe_errors,
            "continuous_years_ready": 0,
            "credential_available": 1,
            "permission_verified": int(probe_success > 0),
            "source_note": "AKShare exposes exchange daily option price/vol endpoints, but this stage only probes availability and does not build continuous PIT history.",
        },
        {
            "source_id": "rqdatac_options",
            "source_type": "credential_datafeed",
            "module_status": rq_status,
            "version": rq_version,
            "calc_iv_available": int(rq_status == "installed"),
            "historical_chain_available": int(rq_status == "installed"),
            "pit_timestamp_available": int(rq_status == "installed"),
            "target_products_with_listed_option": 0,
            "target_products_total": target_total,
            "probe_success_count": 0,
            "probe_error_count": 0,
            "continuous_years_ready": 0,
            "credential_available": int(bool(os.getenv("RQDATAC2_CONF") or os.getenv("RQDATAC_CONF") or (os.getenv("RQDATA_USERNAME") and os.getenv("RQDATA_PASSWORD")))),
            "permission_verified": 0,
            "source_note": "Ricequant documents options greeks/IV access, but this local environment has no rqdatac credential variables.",
        },
        {
            "source_id": "vnpy_optionmaster",
            "source_type": "sdk_calc",
            "module_status": opt_status,
            "version": opt_version,
            "calc_iv_available": int(opt_status == "installed"),
            "historical_chain_available": 0,
            "pit_timestamp_available": 0,
            "target_products_with_listed_option": 0,
            "target_products_total": target_total,
            "probe_success_count": 0,
            "probe_error_count": 0,
            "continuous_years_ready": 0,
            "credential_available": 0,
            "permission_verified": 0,
            "source_note": "OptionMaster is a pricing/risk module, not a historical commodity option chain dataset.",
        },
    ]
    return pd.DataFrame([classify_option_source(row) for row in rows])


def build_data_contract(sources: pd.DataFrame, coverage: pd.DataFrame) -> pd.DataFrame:
    missing_products = ",".join(coverage.loc[~coverage["has_listed_option"].astype(bool), "target_product"].astype(str))
    return pd.DataFrame(
        [
            {
                "contract_id": "commodity_option_chain_pit_history",
                "minimum_coverage": "2018-01-01 to 2026-06-30 daily PIT option chain for each target product with listed commodity options",
                "required_fields": "trade_date,publish_or_exchange_timestamp,exchange,underlying_product,underlying_contract,option_contract,call_put,strike,expiry,last,settlement,volume,open_interest,bid1,ask1,implied_vol,delta,raw_hash,source_url_or_vendor_permission",
                "required_schema_checks": "no_future_publish_time,stable_contract_parser,raw_hash_per_trade_date,listed_option_product_map,continuous_calendar_audit",
                "known_target_product_gaps": missing_products,
                "first_allowed_research_after_delivery": "schema_readiness_stage_then_predeclared_readonly_iv_skew_signal_audit",
                "forbidden_shortcut": "do_not_use_single_date_probe_or_compute_only_iv_function_as_trading_feature",
            }
        ]
    )


def make_option_readiness_decision(sources: pd.DataFrame, coverage: pd.DataFrame) -> dict[str, Any]:
    ready = sources[sources["schema_ready_for_signal_audit"].astype(bool)] if not sources.empty else pd.DataFrame()
    partial = sources[sources["source_status"].astype(str).str.contains("partial|permission|credential|compute", regex=True)] if not sources.empty else pd.DataFrame()
    missing_target_count = int((~coverage["has_listed_option"].astype(bool)).sum()) if not coverage.empty else 0
    if not ready.empty:
        decision = "stage037_option_iv_skew_has_schema_ready_source_for_readonly_audit"
        best_next_direction = str(ready.sort_values("priority_score", ascending=False).iloc[0]["source_id"])
    else:
        decision = "stage037_option_iv_skew_sources_not_rule_ready_data_contract_required"
        best_next_direction = "build_or_import_pit_option_chain_history_before_signal"

    top_source = (
        sources.sort_values(["priority_score", "source_id"], ascending=[False, True]).head(1).to_dict("records")[0]
        if not sources.empty
        else {}
    )
    return {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().replace(microsecond=0).isoformat(),
        "decision": decision,
        "best_next_direction": best_next_direction,
        "source_count": int(len(sources)),
        "schema_ready_source_count": int(len(ready)),
        "partial_or_blocked_source_count": int(len(partial)),
        "immediate_strategy_candidate_count": int(len(ready)),
        "target_product_count": int(len(coverage)),
        "target_products_with_listed_option": int(coverage["has_listed_option"].astype(bool).sum()) if not coverage.empty else 0,
        "target_products_without_listed_option": missing_target_count,
        "top_source": top_source,
        "data_contract_required": bool(ready.empty),
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
            "Commodity option implied volatility and skew have published predictive evidence and exchange-practitioner support, "
            "but this repo must first build PIT option-chain history with timestamps, hashes, coverage and product mapping. "
            "Compute functions or single-date public probes are capability evidence, not tradeable features."
        ),
        "overfit_reflection_before": (
            "否。Stage037 只审计期权 IV/skew 数据源能力和覆盖，不回测收益、不选择阈值、不新增交易规则。"
        ),
        "overfit_reflection_after": (
            "否。即使 public endpoint 探针成功，也保持 data-first；若用单日接口成功直接写 IV/skew 规则才是过拟合。"
        ),
        "continue_value_before": (
            "有。Stage036 后资金层细调价值低，期权 IV/skew 是少数真正不同信息层，值得先验证数据合同。"
        ),
        "continue_value_after": (
            "有，但下一步价值取决于是否能导入连续 PIT 期权链；如果拿不到历史链，就不能沿这条路线做信号优化。"
        ),
    }


def _write_report(
    decision: dict[str, Any],
    sources: pd.DataFrame,
    coverage: pd.DataFrame,
    functions: pd.DataFrame,
    probes: pd.DataFrame,
    contract: pd.DataFrame,
) -> None:
    lines = [
        "# Stage037 期权 IV/skew 数据源 readiness 审计",
        "",
        f"- line_id：`{LINE_ID}`",
        f"- 记录时间：{decision['generated_at']}",
        f"- 决策：`{decision['decision']}`",
        "- 阶段性质：数据源能力/覆盖/探针审计；不回测、不改策略、不连接 CTP、不调用订单 API。",
        "",
        "## 外部调研与判断",
        "",
        "- 商品期权隐含波动率、偏度和风险中性偏度在论文中被用于解释或预测商品期货收益；CME 也有 CVOL/skew 与商品趋势的实践文章。",
        "- TqSdk 文档有期权链、Greeks、隐含波动率和波动率曲面示例，DataDownloader 文档说明历史期货/期权下载属于专业版能力。",
        "- AKShare 当前暴露多个商品期权日频和隐含波动率接口；Ricequant 文档显示可取国内期权 greeks/IV，但本机无 rqdatac 凭证。",
        "- 我的判断：这是有价值的新信息层，但当前只能进入数据合同，不允许写信号规则。",
        "",
        "## Source readiness",
        "",
        _md_table(
            sources[
                [
                    "source_id",
                    "source_type",
                    "module_status",
                    "source_status",
                    "priority_score",
                    "schema_ready_for_signal_audit",
                    "rule_candidate_allowed",
                    "blocking_reasons",
                    "recommended_next_action",
                ]
            ]
        ),
        "",
        "## Target product option coverage",
        "",
        _md_table(coverage),
        "",
        "## AKShare probes",
        "",
        _md_table(probes, max_rows=20),
        "",
        "## AKShare option function inventory",
        "",
        _md_table(functions[["function_name", "signature", "is_commodity_option_endpoint", "doc_head"]], max_rows=30)
        if not functions.empty
        else "_无 AKShare 函数清单_",
        "",
        "## Data contract",
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


def _write_stage_record(decision: dict[str, Any], sources: pd.DataFrame, coverage: pd.DataFrame, probes: pd.DataFrame) -> Path:
    STAGES_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    path = STAGES_DIR / f"{timestamp}_stage037_option_iv_skew_source_readiness.md"
    probe_ok = int((probes["status"].astype(str).eq("ok") & pd.to_numeric(probes["rows"], errors="coerce").fillna(0).gt(0)).sum()) if not probes.empty else 0
    text = f"""# Stage037 期权 IV/skew 数据源 readiness 审计

- line_id：`{LINE_ID}`
- 当前模式：day
- 记录时间：{decision['generated_at']}
- 阶段性质：只读数据源能力/覆盖/小探针审计；不回测、不改策略、不连接 CTP、不调用下单
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：TqSdk 期权基础和 DataDownloader 文档、AKShare 期权数据文档、Ricequant options greeks 文档、商品期权 implied skew/IV 与商品收益相关论文、CME CVOL skew 文章。
- 我的判断：期权 IV/skew 是比当前 OI/分钟线更不同的信息层，可能服务于“AI 选品/高质量信号确认”；但必须先有 2018-2026 连续 PIT 期权链，不能把计算函数或单日接口当成特征。

## 本次变更

- 新增脚本：`research/lines/{LINE_ID}/tools/stage037_option_iv_skew_source_readiness.py`
- 新增测试：`tests/test_rebuilt_c9_v2_stage037_option_iv_skew_source_readiness.py`
- 新增参数：`STAGE037_ENABLE_NETWORK_PROBE={int(ENABLE_NETWORK_PROBE)}`、`STAGE037_PROBE_TIMEOUT_SECONDS={PROBE_TIMEOUT_SECONDS}`、`STAGE037_MAX_PROBES={MAX_PROBES}`
- 修改参数：无正式策略参数修改
- 删除参数：无

## 结果

- decision：`{decision['decision']}`
- best_next_direction：`{decision['best_next_direction']}`
- source_count：`{decision['source_count']}`
- schema_ready_source_count：`{decision['schema_ready_source_count']}`
- immediate_strategy_candidate_count：`{decision['immediate_strategy_candidate_count']}`
- target_product_count：`{decision['target_product_count']}`
- target_products_with_listed_option：`{decision['target_products_with_listed_option']}`
- target_products_without_listed_option：`{decision['target_products_without_listed_option']}`
- AKShare successful probes：`{probe_ok}/{len(probes)}`
- 策略变更：`False`
- true engine：`False`
- order API：`0`
- CTP：`False`

## Source readiness

{_md_table(sources[['source_id', 'source_status', 'priority_score', 'rule_candidate_allowed', 'blocking_reasons', 'recommended_next_action']])}

## Target coverage

{_md_table(coverage)}

## Probe results

{_md_table(probes, max_rows=20)}

## 过拟合反思

- 运行前判断：{decision['overfit_reflection_before']}
- 运行后判断：{decision['overfit_reflection_after']}

## 继续价值反思

- 运行前判断：{decision['continue_value_before']}
- 运行后判断：{decision['continue_value_after']}

## 输出文件

- source_readiness：`{SOURCE_READINESS_PATH}`
- target_coverage：`{TARGET_COVERAGE_PATH}`
- akshare_functions：`{AKSHARE_FUNCTIONS_PATH}`
- probes：`{PROBE_RESULTS_PATH}`
- data_contract：`{DATA_CONTRACT_PATH}`
- decision：`{DECISION_PATH}`
- report：`{REPORT_PATH}`
"""
    path.write_text(text, encoding="utf-8")
    return path


def run() -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    coverage = build_target_product_option_coverage()
    functions = _inspect_akshare_option_functions()
    probes = run_akshare_probes()
    sources = build_source_readiness(functions, probes, coverage)
    contract = build_data_contract(sources, coverage)
    decision = make_option_readiness_decision(sources, coverage)
    _write_report(decision, sources, coverage, functions, probes, contract)
    stage_record = _write_stage_record(decision, sources, coverage, probes)

    sources.to_csv(SOURCE_READINESS_PATH, index=False, encoding="utf-8-sig")
    coverage.to_csv(TARGET_COVERAGE_PATH, index=False, encoding="utf-8-sig")
    functions.to_csv(AKSHARE_FUNCTIONS_PATH, index=False, encoding="utf-8-sig")
    probes.to_csv(PROBE_RESULTS_PATH, index=False, encoding="utf-8-sig")
    contract.to_csv(DATA_CONTRACT_PATH, index=False, encoding="utf-8-sig")
    decision["outputs"] = {
        "source_readiness": str(SOURCE_READINESS_PATH),
        "target_coverage": str(TARGET_COVERAGE_PATH),
        "akshare_functions": str(AKSHARE_FUNCTIONS_PATH),
        "probes": str(PROBE_RESULTS_PATH),
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
