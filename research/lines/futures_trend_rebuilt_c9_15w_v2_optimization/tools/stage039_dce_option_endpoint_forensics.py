from __future__ import annotations

from datetime import datetime
from io import BytesIO, StringIO
import hashlib
import json
import os
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import requests


PROJECT_DIR = Path(__file__).resolve().parents[4]
LINE_ID = "futures_trend_rebuilt_c9_15w_v2_optimization"
STAGE = "Stage039"
MODEL_TAG = "stage039_dce_option_endpoint_forensics_v1"
OUTPUT_PREFIX = "rebuilt_c9_v2_stage039_dce_option_endpoint_forensics"

LINE_DIR = PROJECT_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage039_dce_option_endpoint_forensics"
STAGES_DIR = LINE_DIR / "stages"

PROBE_PLAN_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_probe_plan_{MODEL_TAG}.csv"
PROBE_RESULTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_probe_results_{MODEL_TAG}.csv"
FAMILY_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_family_summary_{MODEL_TAG}.csv"
DATA_CONTRACT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_data_contract_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

ENABLE_NETWORK_PROBE = os.getenv("STAGE039_ENABLE_NETWORK_PROBE", "1").strip() != "0"
REQUEST_TIMEOUT_SECONDS = int(os.getenv("STAGE039_REQUEST_TIMEOUT_SECONDS", "15"))
MAX_PROBES = int(os.getenv("STAGE039_MAX_PROBES", "20"))

DCE_JSON_ENDPOINTS = (
    "http://www.dce.com.cn/dcereport/publicweb/dailystat/dayQuotes",
    "https://www.dce.com.cn/dcereport/publicweb/dailystat/dayQuotes",
)
DCE_LEGACY_EXPORT_ENDPOINTS = (
    "http://www.dce.com.cn/publicweb/quotesdata/exportDayQuotesChData.html",
    "http://portal.dce.com.cn/publicweb/quotesdata/exportDayQuotesChData.html",
)

DCE_OPTION_PROBES = (
    {"target_product": "jd.DCE", "symbol": "鸡蛋期权", "variety_code": "jd", "trade_date": "20251016"},
    {"target_product": "jd.DCE", "symbol": "鸡蛋期权", "variety_code": "jd", "trade_date": "20260629"},
    {"target_product": "lh.DCE", "symbol": "生猪期权", "variety_code": "lh", "trade_date": "20251016"},
    {"target_product": "m.DCE", "symbol": "豆粕期权", "variety_code": "m", "trade_date": "20240603"},
    {"target_product": "pp.DCE", "symbol": "聚丙烯期权", "variety_code": "pp", "trade_date": "20251016"},
)

SOURCE_LINKS = {
    "akshare_cons_dce_legacy": "https://github.com/akfamily/akshare/blob/main/akshare/option/cons.py",
    "akshare_option_docs": "https://akshare.akfamily.xyz/data/option/option.html",
    "dce_site": "https://www.dce.com.cn/dceg/",
    "ceic_dce_option_open_interest": "https://www.ceicdata.com/zh-hans/china/dalian-commodity-exchange-commodity-options-open-position-daily/cn-open-position-dalian-commodity-exchange-options-log",
}

REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    "Accept": "application/json,text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
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


def build_legacy_export_payload(variety_code: str, trade_date: str) -> dict[str, str]:
    date = str(trade_date)
    month_zero_based = str(int(date[4:6]) - 1)
    return {
        "dayQuotes.variety": str(variety_code),
        "dayQuotes.trade_type": "1",
        "year": date[:4],
        "month": month_zero_based,
        "day": date[6:8],
        "exportFlag": "excel",
    }


def build_json_payload(variety_code: str, trade_date: str) -> dict[str, Any]:
    return {
        "contractId": "",
        "lang": "zh",
        "optionSeries": "",
        "statisticsType": 0,
        "tradeDate": str(trade_date),
        "tradeType": "2",
        "varietyId": str(variety_code),
    }


def build_probe_plan() -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for probe in DCE_OPTION_PROBES:
        for endpoint in DCE_JSON_ENDPOINTS:
            rows.append(
                {
                    **probe,
                    "probe_id": f"{probe['target_product'].replace('.', '_')}_json_{probe['trade_date']}_{'https' if endpoint.startswith('https') else 'http'}",
                    "endpoint_family": "akshare_json_dcereport",
                    "endpoint_url": endpoint,
                    "request_mode": "json_post",
                    "payload_json": json.dumps(build_json_payload(probe["variety_code"], probe["trade_date"]), ensure_ascii=False, sort_keys=True),
                }
            )
        for endpoint in DCE_LEGACY_EXPORT_ENDPOINTS:
            rows.append(
                {
                    **probe,
                    "probe_id": f"{probe['target_product'].replace('.', '_')}_legacy_{probe['trade_date']}_{'portal' if 'portal' in endpoint else 'www'}",
                    "endpoint_family": "legacy_export_form",
                    "endpoint_url": endpoint,
                    "request_mode": "form_post",
                    "payload_json": json.dumps(build_legacy_export_payload(probe["variety_code"], probe["trade_date"]), ensure_ascii=False, sort_keys=True),
                }
            )
    return pd.DataFrame(rows).head(MAX_PROBES).copy()


def _detect_columns(columns: list[str]) -> dict[str, bool]:
    joined = ",".join(map(str, columns))
    return {
        "has_contract_column": any(key in joined for key in ["合约", "合约代码", "contractId", "Contract"]),
        "has_oi_column": any(key in joined for key in ["持仓量", "openInterest", "Open Interest"]),
        "has_iv_column": any(key in joined for key in ["隐含波动率", "impliedVolatility", "SIGMA"]),
        "has_publish_timestamp": any(key in joined for key in ["发布时间", "发布日期", "publish", "timestamp", "time"]),
    }


def _detect_text_columns(text: str) -> dict[str, bool]:
    return _detect_columns(text.splitlines()[:5])


def _try_parse_content(content: bytes, content_type: str) -> dict[str, Any]:
    if not content:
        return {"parseable_rows": 0, "parse_method": "empty", "columns": []}
    columns: list[str] = []
    rows = 0
    parse_method = "unparsed"
    try:
        excel_df = pd.read_excel(BytesIO(content), header=1)
        if not excel_df.empty:
            columns = list(map(str, excel_df.columns))
            rows = int(len(excel_df.dropna(how="all")))
            parse_method = "read_excel_header1"
            return {"parseable_rows": rows, "parse_method": parse_method, "columns": columns}
    except Exception:
        pass

    for encoding in ("utf-8", "gbk", "gb18030"):
        try:
            text = content.decode(encoding, errors="ignore")
            if not text.strip():
                continue
            if "<table" in text.lower():
                try:
                    tables = pd.read_html(StringIO(text))
                    if tables:
                        table = tables[0]
                        columns = list(map(str, table.columns))
                        rows = int(len(table.dropna(how="all")))
                        parse_method = f"read_html_{encoding}"
                        return {"parseable_rows": rows, "parse_method": parse_method, "columns": columns}
                except Exception:
                    pass
            lines = [line for line in text.splitlines() if line.strip()]
            tab_lines = [line for line in lines if "\t" in line]
            if tab_lines:
                columns = [item.strip() for item in tab_lines[0].split("\t") if item.strip()]
                rows = max(0, len(tab_lines) - 1)
                parse_method = f"tab_text_{encoding}"
                return {"parseable_rows": rows, "parse_method": parse_method, "columns": columns}
            detected = _detect_text_columns(text)
            return {"parseable_rows": 0, "parse_method": f"text_{encoding}", "columns": [], **detected}
        except Exception:
            continue
    return {"parseable_rows": 0, "parse_method": parse_method, "columns": []}


def classify_endpoint_probe(probe: dict[str, Any] | pd.Series) -> dict[str, Any]:
    data = dict(probe)
    family = str(data.get("endpoint_family", ""))
    status = str(data.get("status", ""))
    parseable_rows = _as_int(data.get("parseable_rows"), 0)
    has_contract = _as_bool(data.get("has_contract_column", False))
    has_oi = _as_bool(data.get("has_oi_column", False))
    has_iv = _as_bool(data.get("has_iv_column", False))
    has_timestamp = _as_bool(data.get("has_publish_timestamp", False))
    continuous_ready = _as_bool(data.get("continuous_audit_passed", False))

    reasons: list[str] = []
    endpoint_candidate = False
    if family == "akshare_json_dcereport" and status in {"http_ok_non_json", "http_error_non_json", "json_decode_error"}:
        probe_status = "json_endpoint_not_returning_json_needs_alternative_endpoint"
        reasons.append("dce_json_endpoint_not_json")
        if _as_int(data.get("http_status"), 0) >= 400:
            reasons.append("http_412_or_error_non_json")
    elif status in {"timeout", "request_error", "disabled"}:
        probe_status = "endpoint_probe_failed"
        reasons.append(status)
    elif parseable_rows > 0 and family == "legacy_export_form":
        probe_status = "legacy_export_candidate_not_pit_ready"
        endpoint_candidate = True
    elif parseable_rows > 0 and family == "akshare_json_dcereport":
        probe_status = "json_endpoint_recovered_not_pit_ready"
        endpoint_candidate = True
    elif status == "ok":
        probe_status = "endpoint_ok_but_no_parseable_rows"
        reasons.append("no_parseable_rows")
    else:
        probe_status = "endpoint_probe_failed"
        reasons.append("probe_not_ok")

    if endpoint_candidate:
        if not has_contract:
            reasons.append("missing_contract_column")
        if not has_oi:
            reasons.append("missing_open_interest_column")
        if not has_iv:
            reasons.append("missing_iv_column")
        if not has_timestamp:
            reasons.append("missing_publish_timestamp")
        if not continuous_ready:
            reasons.append("no_continuous_calendar_audit")

    schema_ready = bool(endpoint_candidate and has_contract and has_oi and has_iv and has_timestamp and continuous_ready)
    result = dict(data)
    result["probe_status"] = probe_status
    result["endpoint_recovery_candidate"] = bool(endpoint_candidate)
    result["schema_ready_probe"] = bool(schema_ready)
    result["rule_candidate_allowed"] = bool(schema_ready)
    result["blocking_reasons"] = ",".join(list(dict.fromkeys(reasons)))
    return result


def _request_probe(row: dict[str, Any]) -> dict[str, Any]:
    if not ENABLE_NETWORK_PROBE:
        return {"status": "disabled", "http_status": 0, "content_type": "", "body_size": 0, "parseable_rows": 0}
    payload = json.loads(str(row["payload_json"]))
    try:
        if row["request_mode"] == "json_post":
            response = requests.post(row["endpoint_url"], json=payload, headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT_SECONDS)
        else:
            response = requests.post(row["endpoint_url"], data=payload, headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT_SECONDS)
        content = response.content or b""
        content_type = response.headers.get("Content-Type", "")
        body_sha256 = hashlib.sha256(content).hexdigest() if content else ""
        body_prefix = content[:160].decode("utf-8", errors="replace").replace("\n", "\\n").replace("\r", "\\r")
        result: dict[str, Any] = {
            "http_status": int(response.status_code),
            "content_type": content_type,
            "body_size": int(len(content)),
            "body_sha256": body_sha256,
            "body_prefix": body_prefix,
        }
        if row["request_mode"] == "json_post":
            try:
                data_json = response.json()
                rows = data_json.get("data", []) if isinstance(data_json, dict) else []
                frame = pd.DataFrame(rows)
                columns = list(map(str, frame.columns))
                result.update(
                    {
                        "status": "ok",
                        "parseable_rows": int(len(frame)),
                        "parse_method": "response_json_data",
                        "columns": columns,
                        **_detect_columns(columns),
                    }
                )
            except Exception as exc:
                parsed = _try_parse_content(content, content_type)
                columns = list(map(str, parsed.get("columns", []) or []))
                result.update(
                    {
                        "status": "http_ok_non_json" if response.ok else "http_error_non_json",
                        "parseable_rows": _as_int(parsed.get("parseable_rows"), 0),
                        "parse_method": parsed.get("parse_method", ""),
                        "columns": columns,
                        "error_type": type(exc).__name__,
                        "error_message": str(exc)[:300],
                        **_detect_columns(columns),
                    }
                )
        else:
            parsed = _try_parse_content(content, content_type)
            columns = list(map(str, parsed.get("columns", []) or []))
            result.update(
                {
                    "status": "ok" if response.ok else "http_error",
                    "parseable_rows": _as_int(parsed.get("parseable_rows"), 0),
                    "parse_method": parsed.get("parse_method", ""),
                    "columns": columns,
                    **_detect_columns(columns),
                }
            )
        return result
    except requests.Timeout as exc:
        return {"status": "timeout", "http_status": 0, "content_type": "", "body_size": 0, "parseable_rows": 0, "error_type": type(exc).__name__, "error_message": str(exc)[:300]}
    except Exception as exc:
        return {"status": "request_error", "http_status": 0, "content_type": "", "body_size": 0, "parseable_rows": 0, "error_type": type(exc).__name__, "error_message": str(exc)[:300]}


def run_endpoint_probes(probe_plan: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for row in probe_plan.to_dict("records"):
        result = _request_probe(row)
        columns = list(map(str, result.get("columns", []) or []))
        merged = {
            **row,
            "status": str(result.get("status", "")),
            "http_status": _as_int(result.get("http_status"), 0),
            "content_type": str(result.get("content_type", "")),
            "body_size": _as_int(result.get("body_size"), 0),
            "body_sha256": str(result.get("body_sha256", "")),
            "body_prefix": str(result.get("body_prefix", ""))[:240],
            "parseable_rows": _as_int(result.get("parseable_rows"), 0),
            "parse_method": str(result.get("parse_method", "")),
            "columns": ",".join(columns),
            "has_contract_column": bool(result.get("has_contract_column", False)),
            "has_oi_column": bool(result.get("has_oi_column", False)),
            "has_iv_column": bool(result.get("has_iv_column", False)),
            "has_publish_timestamp": bool(result.get("has_publish_timestamp", False)),
            "continuous_audit_passed": False,
            "error_type": str(result.get("error_type", "")),
            "error_message": str(result.get("error_message", "")),
        }
        rows.append(classify_endpoint_probe(merged))
    return pd.DataFrame(rows)


def summarize_family_results(probes: pd.DataFrame) -> pd.DataFrame:
    if probes.empty:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    for family, group in probes.groupby("endpoint_family", sort=True):
        rows.append(
            {
                "endpoint_family": family,
                "probe_count": int(len(group)),
                "http_200_count": int(group["http_status"].astype(int).eq(200).sum()),
                "parseable_probe_count": int(group["parseable_rows"].astype(int).gt(0).sum()),
                "endpoint_recovery_candidate_count": int(group["endpoint_recovery_candidate"].astype(bool).sum()),
                "schema_ready_probe_count": int(group["schema_ready_probe"].astype(bool).sum()),
                "probe_statuses": ",".join(sorted(set(group["probe_status"].astype(str)))),
                "blocking_reasons": ",".join(sorted(set(",".join(group["blocking_reasons"].astype(str)).split(",")) - {""})),
            }
        )
    return pd.DataFrame(rows)


def build_data_contract(probes: pd.DataFrame) -> pd.DataFrame:
    candidate_urls = ",".join(sorted(set(probes.loc[probes["endpoint_recovery_candidate"].astype(bool), "endpoint_url"].astype(str)))) if not probes.empty else ""
    return pd.DataFrame(
        [
            {
                "contract_id": "dce_option_chain_legacy_export_recovery",
                "candidate_urls": candidate_urls,
                "required_parser": "parse exportDayQuotesChData rows into option contract, price, volume, open_interest and product/date fields",
                "required_pit_checks": "raw_response_hash, request_url_and_payload_hash, publish_or_exchange_timestamp, no_future_publish_time, continuous_calendar_by_product",
                "required_coverage": "jd/lh plus all DCE mapped target option products from first listing date through 2026-06-30",
                "forbidden_shortcut": "do_not_use_legacy_export_rows_as_iv_skew_signal_without_timestamp_hash_calendar_and_iv_or_delta_reconstruction",
            }
        ]
    )


def make_stage039_decision(probes: pd.DataFrame) -> dict[str, Any]:
    endpoint_candidates = int(probes["endpoint_recovery_candidate"].astype(bool).sum()) if not probes.empty else 0
    schema_ready = int(probes["schema_ready_probe"].astype(bool).sum()) if not probes.empty else 0
    json_failures = int(probes["probe_status"].astype(str).eq("json_endpoint_not_returning_json_needs_alternative_endpoint").sum()) if not probes.empty else 0
    if endpoint_candidates > 0 and schema_ready == 0:
        decision = "stage039_dce_legacy_export_candidate_requires_parser_and_pit_calendar"
        best_next_direction = "build_legacy_export_parser_with_hash_calendar_then_reaudit_dce_jd_lh_coverage"
    elif schema_ready > 0:
        decision = "stage039_dce_endpoint_schema_ready_needs_readonly_signal_spec"
        best_next_direction = "freeze_dce_option_parser_and_run_schema_readiness_again"
    else:
        decision = "stage039_dce_endpoint_no_recovery_candidate_switch_source"
        best_next_direction = "use_vendor_or_tqsdk_history_for_dce_options"
    return {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().replace(microsecond=0).isoformat(),
        "decision": decision,
        "best_next_direction": best_next_direction,
        "probe_count": int(len(probes)),
        "json_endpoint_failure_count": json_failures,
        "endpoint_recovery_candidate_count": endpoint_candidates,
        "schema_ready_probe_count": schema_ready,
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
            "AKShare 主分支仍保留 DCE 旧 exportDayQuotesChData 端点常量，公开抓包资料也指向 "
            "dayQuotes.variety/dayQuotes.trade_type/year/month/day/exportFlag 表单；CEIC 数据说明鸡蛋等 DCE 期权持仓日频确实存在。"
            "因此 Stage038 的 JSONDecodeError 更像当前 JSON 端点或调用方式失效，不是鸡蛋期权数据不存在。"
        ),
        "overfit_reflection_before": "否。本阶段只定位 DCE 端点和导出接口，不做收益回测、不修改策略规则。",
        "overfit_reflection_after": "否。即使旧导出端点可解析，也只作为数据工程候选，不把返回行直接当 AI 特征。",
        "continue_value_before": "有。鸡蛋进入基础池后，DCE 期权链能否复水会影响新 PIT 信息源路线。",
        "continue_value_after": "有但仍是数据工程价值；下一步必须先做 parser、hash、发布时间和连续覆盖，才能讨论 IV/skew 或 AI 选品。",
    }


def _write_report(probe_plan: pd.DataFrame, probes: pd.DataFrame, family_summary: pd.DataFrame, data_contract: pd.DataFrame, decision: dict[str, Any]) -> None:
    lines = [
        "# Stage039 DCE 商品期权端点法证",
        "",
        f"- line_id：`{LINE_ID}`",
        f"- 记录时间：{decision['generated_at']}",
        f"- 决策：`{decision['decision']}`",
        "- 阶段性质：DCE 期权端点只读法证；不回测、不改策略、不连接 CTP、不调用订单 API。",
        "",
        "## 外部调研与判断",
        "",
        "- AKShare 主分支 `cons.py` 保留 `portal.dce.com.cn/publicweb/quotesdata/exportDayQuotesChData.html` 旧导出端点。",
        "- 公开抓包资料显示旧 DCE 导出接口使用 `dayQuotes.variety/dayQuotes.trade_type/year/month/day/exportFlag` 表单参数，其中期权 `trade_type=1`、月份为 0-based。",
        "- CEIC 的 DCE 期权日频持仓指标列出鸡蛋期权，说明“鸡蛋期权数据不存在”不是当前最合理假设。",
        "- 我的判断：当前 JSON endpoint 失败应按端点/调用方式问题处理；旧导出端点若可解析，也必须先做 PIT 数据工程。",
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
                    "endpoint_family",
                    "endpoint_url",
                    "http_status",
                    "content_type",
                    "body_size",
                    "parseable_rows",
                    "parse_method",
                    "has_contract_column",
                    "has_oi_column",
                    "has_iv_column",
                    "probe_status",
                    "blocking_reasons",
                ]
            ],
            max_rows=40,
        ),
        "",
        "## Endpoint family summary",
        "",
        _md_table(family_summary),
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


def _write_stage_record(probe_plan: pd.DataFrame, probes: pd.DataFrame, family_summary: pd.DataFrame, decision: dict[str, Any]) -> Path:
    STAGES_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    path = STAGES_DIR / f"{timestamp}_stage039_dce_option_endpoint_forensics.md"
    text = f"""# Stage039 DCE 商品期权端点法证

- line_id：`{LINE_ID}`
- 当前模式：day
- 记录时间：{decision['generated_at']}
- 阶段性质：只读端点法证/复水候选审计；不回测、不改策略、不连接 CTP、不调用下单
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：AKShare 主分支 `cons.py`、AKShare 期权文档、DCE 官网、CEIC DCE 期权持仓日频说明、DCE 旧导出端点抓包资料。
- 我的判断：Stage038 的 DCE `JSONDecodeError` 更像当前 JSON 端点或调用方式失效；鸡蛋期权数据本身存在，但公共端点能否稳定复水还要靠旧 export parser、hash、发布时间和连续覆盖证明。

## 本次变更

- 新增脚本：`research/lines/{LINE_ID}/tools/stage039_dce_option_endpoint_forensics.py`
- 新增测试：`tests/test_rebuilt_c9_v2_stage039_dce_option_endpoint_forensics.py`
- 新增参数：`STAGE039_ENABLE_NETWORK_PROBE={int(ENABLE_NETWORK_PROBE)}`、`STAGE039_REQUEST_TIMEOUT_SECONDS={REQUEST_TIMEOUT_SECONDS}`、`STAGE039_MAX_PROBES={MAX_PROBES}`
- 修改参数：无正式策略参数修改
- 删除参数：无

## 结果

- decision：`{decision['decision']}`
- best_next_direction：`{decision['best_next_direction']}`
- probe_count：`{decision['probe_count']}`
- json_endpoint_failure_count：`{decision['json_endpoint_failure_count']}`
- endpoint_recovery_candidate_count：`{decision['endpoint_recovery_candidate_count']}`
- schema_ready_probe_count：`{decision['schema_ready_probe_count']}`
- immediate_strategy_candidate_count：`0`
- 策略变更：`False`
- true engine：`False`
- order API：`0`
- CTP：`False`

## Endpoint family summary

{_md_table(family_summary)}

## Probe results

{_md_table(probes[['probe_id', 'target_product', 'endpoint_family', 'http_status', 'content_type', 'body_size', 'parseable_rows', 'parse_method', 'probe_status', 'blocking_reasons']], max_rows=40)}

## 过拟合反思

- 运行前判断：{decision['overfit_reflection_before']}
- 运行后判断：{decision['overfit_reflection_after']}

## 继续价值反思

- 运行前判断：{decision['continue_value_before']}
- 运行后判断：{decision['continue_value_after']}

## 输出文件

- probe_plan：`{PROBE_PLAN_PATH}`
- probe_results：`{PROBE_RESULTS_PATH}`
- family_summary：`{FAMILY_SUMMARY_PATH}`
- data_contract：`{DATA_CONTRACT_PATH}`
- decision：`{DECISION_PATH}`
- report：`{REPORT_PATH}`
"""
    path.write_text(text, encoding="utf-8")
    return path


def run() -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    probe_plan = build_probe_plan()
    probes = run_endpoint_probes(probe_plan)
    family_summary = summarize_family_results(probes)
    data_contract = build_data_contract(probes)
    decision = make_stage039_decision(probes)
    _write_report(probe_plan, probes, family_summary, data_contract, decision)
    stage_record = _write_stage_record(probe_plan, probes, family_summary, decision)

    probe_plan.to_csv(PROBE_PLAN_PATH, index=False, encoding="utf-8-sig")
    probes.to_csv(PROBE_RESULTS_PATH, index=False, encoding="utf-8-sig")
    family_summary.to_csv(FAMILY_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    data_contract.to_csv(DATA_CONTRACT_PATH, index=False, encoding="utf-8-sig")
    decision["outputs"] = {
        "probe_plan": str(PROBE_PLAN_PATH),
        "probe_results": str(PROBE_RESULTS_PATH),
        "family_summary": str(FAMILY_SUMMARY_PATH),
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
