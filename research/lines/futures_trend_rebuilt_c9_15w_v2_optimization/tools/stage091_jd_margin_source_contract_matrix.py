from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import importlib
import importlib.util
import inspect
import json
from pathlib import Path
import sys
from typing import Any

import numpy as np
import pandas as pd
import requests


ROOT = Path(__file__).resolve().parents[4]
LINE_ID = "futures_trend_rebuilt_c9_15w_v2_optimization"
STAGE = "Stage091"
MODEL_TAG = "stage091_jd_margin_source_contract_matrix_v1"
OUTPUT_PREFIX = "rebuilt_c9_v2_stage091_jd_margin_source_contract_matrix"

LINE_DIR = ROOT / "research" / "lines" / LINE_ID
OUT = LINE_DIR / "outputs" / "stage091_jd_margin_source_contract_matrix"
STAGES_DIR = LINE_DIR / "stages"

STAGE088_DECISION = LINE_DIR / "outputs/stage088_jd_margin_source_audit/rebuilt_c9_v2_stage088_jd_margin_source_audit_decision_stage088_jd_margin_source_audit_v1.json"
STAGE089_DECISION = LINE_DIR / "outputs/stage089_jd_margin_endpoint_probe/rebuilt_c9_v2_stage089_jd_margin_endpoint_probe_decision_stage089_jd_margin_endpoint_probe_v1.json"
STAGE090_DECISION = LINE_DIR / "outputs/stage090_gtja_jd_margin_batch_gate/rebuilt_c9_v2_stage090_gtja_jd_margin_batch_gate_decision_stage090_gtja_jd_margin_batch_gate_v1.json"
STAGE090_COVERAGE = LINE_DIR / "outputs/stage090_gtja_jd_margin_batch_gate/rebuilt_c9_v2_stage090_gtja_jd_margin_batch_gate_coverage_summary_stage090_gtja_jd_margin_batch_gate_v1.csv"

ROUTE_MATRIX_PATH = OUT / f"{OUTPUT_PREFIX}_route_matrix_{MODEL_TAG}.csv"
LOCAL_CAPABILITY_PATH = OUT / f"{OUTPUT_PREFIX}_local_capability_{MODEL_TAG}.csv"
DCE_HTTP_PROBE_PATH = OUT / f"{OUTPUT_PREFIX}_dce_http_probe_{MODEL_TAG}.csv"
INPUT_AUDIT_PATH = OUT / f"{OUTPUT_PREFIX}_input_audit_{MODEL_TAG}.csv"
DECISION_PATH = OUT / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUT / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

EXTERNAL_RESEARCH = [
    {
        "source_id": "dce_daily_trading_parameters_page",
        "url": "https://www.dce.com.cn/dalianshangpin/ywfw/ywcs/jycs/rjycs/index.html",
        "finding": "DCE has an official daily trading parameters page for business parameters.",
    },
    {
        "source_id": "dce_portal_api_service_news",
        "url": "https://www.dce.com.cn/dce/content/2025/wm/18625789.html",
        "finding": "DCE announced a portal API service for registered users covering public portal information, including business parameters.",
    },
    {
        "source_id": "akshare_futures_settle_docs",
        "url": "https://akshare.akfamily.xyz/data/futures/futures.html",
        "finding": "AKShare futures_settle provides settlement parameters but explicitly does not support DCE.",
    },
    {
        "source_id": "gtja_calendar",
        "url": "https://www.gtjaqh.com/pc/calendar?date=20260625",
        "finding": "GTJA calendar exposes broker-company margin standards and special contract adjustments, not exchange margin.",
    },
    {
        "source_id": "cno_pendata_settlement_parameter_database",
        "url": "https://www.ssrdata.com/data/Chinese-Futures/Futures-js/index",
        "finding": "A paid/permissioned Chinese futures daily settlement parameter database claims long history coverage, but no local license/dataset is present.",
    },
]


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        number = float(value)
        return None if not np.isfinite(number) else number
    if isinstance(value, float):
        return None if not np.isfinite(value) else value
    if isinstance(value, (pd.Timestamp, datetime)):
        return "" if pd.isna(value) else value.isoformat()
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return value


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _input_audit(paths: list[Path]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for path in paths:
        if path.exists() and path.is_file():
            stat = path.stat()
            rows.append(
                {
                    "path": str(path),
                    "exists": True,
                    "bytes": int(stat.st_size),
                    "mtime": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
                    "sha256": _sha256(path),
                }
            )
        else:
            rows.append({"path": str(path), "exists": False, "bytes": 0, "mtime": "", "sha256": ""})
    return pd.DataFrame(rows)


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, encoding="utf-8-sig")


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_无记录_"
    data = frame.head(max_rows).copy() if max_rows else frame.copy()
    return data.to_markdown(index=False)


def _find_spec_path(module_name: str) -> str:
    spec = importlib.util.find_spec(module_name)
    if spec is None:
        return ""
    return str(spec.origin or "")


def build_local_capability() -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for module_name in ["akshare", "tqsdk", "rqdatac"]:
        spec_path = _find_spec_path(module_name)
        present = bool(spec_path)
        version = ""
        public_functions: list[str] = []
        source_evidence = ""
        if present:
            module = importlib.import_module(module_name)
            version = str(getattr(module, "__version__", ""))
            public_functions = [
                name
                for name in dir(module)
                if any(token in name.lower() for token in ["margin", "settle", "future", "commission"])
            ][:80]
            if module_name == "tqsdk":
                try:
                    from tqsdk import TqApi  # type: ignore

                    query_settlement = inspect.getsource(TqApi.query_symbol_settlement)
                    source_evidence = (
                        "query_symbol_settlement_columns=datetime/symbol/settlement;"
                        f"mentions_margin={'margin' in query_settlement.lower()}"
                    )
                except Exception as exc:  # noqa: BLE001 - source introspection only.
                    source_evidence = f"source_inspect_error={type(exc).__name__}:{str(exc)[:120]}"
            elif module_name == "rqdatac":
                try:
                    import rqdatac.services.future as rq_future  # type: ignore

                    source = inspect.getsource(rq_future.get_commission_margin)
                    source_evidence = (
                        "get_commission_margin_fields=margin_type,long_margin_ratio,short_margin_ratio;"
                        f"has_date_parameter={'date' in inspect.signature(rq_future.get_commission_margin).parameters}"
                    )
                    if "start_date" in source or "end_date" in source:
                        source_evidence += ";source_mentions_start_or_end_date=True"
                except Exception as exc:  # noqa: BLE001 - source introspection only.
                    source_evidence = f"source_inspect_error={type(exc).__name__}:{str(exc)[:120]}"
            elif module_name == "akshare":
                source_evidence = "installed; docs checked externally; futures_settle DCE unsupported per docs and Stage089 probe"
        rows.append(
            {
                "module": module_name,
                "present": present,
                "version": version,
                "spec_path": spec_path,
                "margin_related_public_functions": ",".join(public_functions),
                "source_evidence": source_evidence,
            }
        )
    return pd.DataFrame(rows)


def probe_dce_http(timeout: float) -> pd.DataFrame:
    endpoints = [
        ("daily_parameters_page", "GET", "https://www.dce.com.cn/dalianshangpin/ywfw/ywcs/jycs/rjycs/index.html", None),
        ("legacy_tradepara_contract_info_http", "POST", "http://www.dce.com.cn/dcereport/publicweb/tradepara/contractInfo", {"lang": "zh", "tradeType": "1", "varietyId": "all"}),
        ("legacy_tradepara_contract_info_https", "POST", "https://www.dce.com.cn/dcereport/publicweb/tradepara/contractInfo", {"lang": "zh", "tradeType": "1", "varietyId": "all"}),
        ("legacy_daily_trading_parameters_guess", "POST", "http://www.dce.com.cn/dcereport/publicweb/tradepara/dailyTradingParameters", {"lang": "zh", "tradeType": "1", "varietyId": "all"}),
    ]
    rows: list[dict[str, Any]] = []
    for route_id, method, url, payload in endpoints:
        now = datetime.now().isoformat(timespec="seconds")
        try:
            if method == "POST":
                resp = requests.post(url, data=payload or {}, headers=REQUEST_HEADERS, timeout=timeout)
            else:
                resp = requests.get(url, headers=REQUEST_HEADERS, timeout=timeout)
            text = resp.text[:400].replace("\n", " ").strip()
            content_type = resp.headers.get("content-type", "")
            rows.append(
                {
                    "route_id": route_id,
                    "method": method,
                    "url": url,
                    "probe_time": now,
                    "status": "http_response",
                    "http_status": resp.status_code,
                    "content_type": content_type,
                    "bytes": len(resp.content),
                    "looks_json": "json" in content_type.lower() or resp.text.strip().startswith(("{", "[")),
                    "looks_anti_scrape": resp.status_code == 412 or "meta id=" in resp.text[:1000],
                    "sample": text,
                }
            )
        except Exception as exc:  # noqa: BLE001 - endpoint probe.
            rows.append(
                {
                    "route_id": route_id,
                    "method": method,
                    "url": url,
                    "probe_time": now,
                    "status": "error",
                    "http_status": "",
                    "content_type": "",
                    "bytes": 0,
                    "looks_json": False,
                    "looks_anti_scrape": False,
                    "sample": f"{type(exc).__name__}: {str(exc)[:240]}",
                }
            )
    return pd.DataFrame(rows)


def build_route_matrix(
    local_capability: pd.DataFrame,
    dce_probe: pd.DataFrame,
    stage088: dict[str, Any],
    stage089: dict[str, Any],
    stage090: dict[str, Any],
    stage090_coverage: pd.DataFrame,
) -> pd.DataFrame:
    stage090_required = int(stage090.get("required_unique_dates") or stage090.get("required_jd_day_rows") or 0)
    stage090_missing = int(stage090.get("missing_candidate_daily_margin_rows") or 0)
    gtja_covered = int(stage090.get("candidate_daily_margin_rows") or 0)

    dce_any_success = bool(
        not dce_probe.empty
        and dce_probe["status"].eq("http_response").any()
        and dce_probe["looks_json"].eq(True).any()
        and dce_probe["looks_anti_scrape"].eq(False).any()
    )
    akshare_present = bool(local_capability.query("module == 'akshare'")["present"].any()) if not local_capability.empty else False
    tqsdk_present = bool(local_capability.query("module == 'tqsdk'")["present"].any()) if not local_capability.empty else False
    rqdatac_present = bool(local_capability.query("module == 'rqdatac'")["present"].any()) if not local_capability.empty else False

    routes = [
        {
            "route_id": "dce_registered_portal_api",
            "source_rank": 1,
            "source_class": "official_exchange_registered_api",
            "current_status": "not_acquired_credentials_or_docs",
            "has_exchange_margin_ratio": "expected_must_verify",
            "has_contract_daily_grain": "expected_must_verify",
            "has_pit_timestamp_or_publish_time": "unknown_until_docs",
            "has_raw_hash_chain": "unknown_until_download",
            "coverage_status": "potential_full_coverage_must_verify",
            "accepted_now": False,
            "can_be_accepted_after_import": True,
            "action": "obtain DCE portal API credentials/docs, download raw daily trading parameters, hash and validate coverage",
            "reason": "Official route announced for business parameters, but no local authenticated dataset/API documentation is present.",
        },
        {
            "route_id": "dce_public_daily_parameters_page_or_legacy_dcereport",
            "source_rank": 2,
            "source_class": "official_exchange_public_web",
            "current_status": "blocked_or_not_machine_readable" if not dce_any_success else "needs_schema_parse",
            "has_exchange_margin_ratio": "expected_if_accessible",
            "has_contract_daily_grain": "expected_if_accessible",
            "has_pit_timestamp_or_publish_time": "page_dependent",
            "has_raw_hash_chain": "download_dependent",
            "coverage_status": "not_acquired",
            "accepted_now": False,
            "can_be_accepted_after_import": bool(dce_any_success),
            "action": "only proceed if a stable official raw table/API can be downloaded and hashed",
            "reason": "Local terminal probes did not acquire accepted machine-readable data; this does not prove every public HTML path is impossible.",
        },
        {
            "route_id": "akshare_futures_settle_dce",
            "source_rank": 3,
            "source_class": "public_wrapper_exchange_settle",
            "current_status": "installed_but_dce_unsupported" if akshare_present else "package_missing",
            "has_exchange_margin_ratio": "for_supported_exchanges_only",
            "has_contract_daily_grain": "for_supported_exchanges_only",
            "has_pit_timestamp_or_publish_time": False,
            "has_raw_hash_chain": False,
            "coverage_status": "dce_unsupported",
            "accepted_now": False,
            "can_be_accepted_after_import": False,
            "action": "do not use for DCE until upstream adds DCE support and raw provenance is validated",
            "reason": "AKShare docs and Stage089 both show futures_settle currently does not support DCE.",
        },
        {
            "route_id": "gtja_calendar_broker_margin_reconstruction",
            "source_rank": 4,
            "source_class": "broker_calendar_margin",
            "current_status": "coverage_incomplete_not_exchange_margin",
            "has_exchange_margin_ratio": False,
            "has_contract_daily_grain": "partially_reconstructable",
            "has_pit_timestamp_or_publish_time": False,
            "has_raw_hash_chain": "response_hash_only_no_raw_html_archive",
            "coverage_status": f"{gtja_covered}/{stage090_required} required JD days covered; missing={stage090_missing}",
            "accepted_now": False,
            "can_be_accepted_after_import": False,
            "action": "keep as broker cross-check only; do not feed true ledger",
            "reason": "GTJA is broker-company margin, Stage090 has 106 missing rows and reviewer found special-adjustment parser undercounts.",
        },
        {
            "route_id": "tqsdk_historical_settlement_or_quote_margin",
            "source_rank": 5,
            "source_class": "vendor_api_current_or_settlement",
            "current_status": "installed_not_contract_daily_margin_history" if tqsdk_present else "package_missing",
            "has_exchange_margin_ratio": "current_quote_or_sim_margin_only",
            "has_contract_daily_grain": "symbol_info_yes_history_margin_no",
            "has_pit_timestamp_or_publish_time": "settlement_has_generation_note_not_margin",
            "has_raw_hash_chain": False,
            "coverage_status": "settlement_data_support_from_20200102_but_no_margin_history_column",
            "accepted_now": False,
            "can_be_accepted_after_import": False,
            "action": "use for minute/settlement/current risk checks, not for JD true-ledger historical margin unless vendor provides a separate margin history export",
            "reason": "TqSdk query_symbol_settlement returns settlement only; quote/scenario margin is current or account-derived, not 2020-2026 PIT daily margin.",
        },
        {
            "route_id": "rqdatac_futures_get_commission_margin",
            "source_rank": 6,
            "source_class": "vendor_api_current_margin",
            "current_status": "installed_api_has_margin_fields_no_date_parameter" if rqdatac_present else "package_missing",
            "has_exchange_margin_ratio": "unknown_vendor_current",
            "has_contract_daily_grain": True,
            "has_pit_timestamp_or_publish_time": False,
            "has_raw_hash_chain": False,
            "coverage_status": "no_date_range_parameter_in_local_api",
            "accepted_now": False,
            "can_be_accepted_after_import": False,
            "action": "ask vendor for historical daily commission/margin export with date and raw provenance before using",
            "reason": "Local RQData API exposes long/short margin ratio fields but no start/end date parameter for historical daily margin series.",
        },
        {
            "route_id": "licensed_settlement_parameter_database",
            "source_rank": 7,
            "source_class": "paid_vendor_dataset",
            "current_status": "not_present_locally",
            "has_exchange_margin_ratio": "claimed_by_vendor",
            "has_contract_daily_grain": "claimed_by_vendor",
            "has_pit_timestamp_or_publish_time": "must_verify",
            "has_raw_hash_chain": "must_verify",
            "coverage_status": "potential_2012_to_present_claim",
            "accepted_now": False,
            "can_be_accepted_after_import": True,
            "action": "license/export sample, then validate fields, dates, JD coverage, raw hashes and PIT timing",
            "reason": "External database claims long settlement-parameter coverage, but current workspace has no licensed extract.",
        },
        {
            "route_id": "broker_live_account_margin_snapshots",
            "source_rank": 8,
            "source_class": "broker_or_ctp_current_snapshot",
            "current_status": "current_or_position_specific_only",
            "has_exchange_margin_ratio": False,
            "has_contract_daily_grain": "only_if_daily_snapshot_pipeline_exists",
            "has_pit_timestamp_or_publish_time": "snapshot_time_only",
            "has_raw_hash_chain": "possible_for_future_snapshots",
            "coverage_status": "not_historical_full_coverage",
            "accepted_now": False,
            "can_be_accepted_after_import": False,
            "action": "use for forward live risk reconciliation only; do not backfill historical true ledger",
            "reason": "Broker/CTP snapshots are account/broker-specific and cannot recreate full 2020-2026 exchange margin history.",
        },
    ]
    matrix = pd.DataFrame(routes)
    matrix["accepted_now"] = matrix["accepted_now"].astype(bool)
    matrix["source_rank"] = matrix["source_rank"].astype(int)
    return matrix


def build_decision(route_matrix: pd.DataFrame, local_capability: pd.DataFrame, dce_probe: pd.DataFrame) -> dict[str, Any]:
    accepted_now = int(route_matrix["accepted_now"].sum())
    accept_after = int(route_matrix["can_be_accepted_after_import"].astype(bool).sum())
    official_potential = route_matrix[
        route_matrix["source_class"].astype(str).str.contains("official_exchange_registered_api|paid_vendor_dataset", regex=True)
        & route_matrix["can_be_accepted_after_import"].astype(bool)
    ]
    return {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "decision": "stage091_no_accepted_jd_margin_source_route_matrix_ready",
        "accepted_route_count": accepted_now,
        "can_be_accepted_after_import_count": accept_after,
        "preferred_next_route": official_potential.iloc[0]["route_id"] if not official_potential.empty else "",
        "route_count": int(len(route_matrix)),
        "local_package_count": int(local_capability["present"].sum()) if not local_capability.empty else 0,
        "dce_probe_count": int(len(dce_probe)),
        "dce_probe_success_json_count": int(dce_probe["looks_json"].eq(True).sum()) if not dce_probe.empty else 0,
        "ready_for_true_ledger_replay": False,
        "remaining_blocker": "jd_contract_daily_margin_history",
        "strategy_changed": False,
        "true_engine_run": False,
        "order_api_calls": 0,
        "ctp_connected": False,
        "overfit_before": "否。数据源资格矩阵不看收益、不调参数。",
        "overfit_after": "否。输出只改变数据合同判断，不进入策略收益优化。",
        "continue_before": "有。保证金历史是 true ledger 的硬阻塞。",
        "continue_after": "有，但下一步应拿 DCE 注册 API 或授权 vendor 数据，而不是继续救 GTJA/公共端点。",
    }


def write_report(
    route_matrix: pd.DataFrame,
    local_capability: pd.DataFrame,
    dce_probe: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    report = f"""# {STAGE} JD 保证金数据源资格矩阵

## 外部调研与判断

| source_id | url | finding |
| --- | --- | --- |
{chr(10).join(f"| {row['source_id']} | {row['url']} | {row['finding']} |" for row in EXTERNAL_RESEARCH)}

我的判断：JD 精确逐日保证金不能再用 GTJA broker margin 或静态最低保证金补。能进入 true ledger 的路线只剩两类：`DCE 注册门户 API/官方原始表`，或 `授权 vendor 的逐日结算参数导出`。两者都必须带合约日粒度、交易所保证金率、发布时间/生效时间、原始文件/hash、连续覆盖。

## Route Matrix

{_md_table(route_matrix)}

## Local Capability

{_md_table(local_capability)}

## DCE HTTP Probe

{_md_table(dce_probe)}

## 决策

```json
{json.dumps(_json_safe(decision), ensure_ascii=False, indent=2)}
```

## 回测记录字段

- 本阶段不新增回测，因此不新增期末权益、总收益、最大回撤、Sharpe、滑点、交易次数、胜率。

## 过拟合反思

- 运行前：否。数据源资格矩阵不看收益、不调参数。
- 运行后：否。输出只改变数据合同判断，不进入策略收益优化。

## 继续价值反思

- 运行前：有。保证金历史是 true ledger 的硬阻塞。
- 运行后：有，但下一步应拿 DCE 注册 API 或授权 vendor 数据，而不是继续救 GTJA/公共端点。

## 输出

- route_matrix：`{ROUTE_MATRIX_PATH}`
- local_capability：`{LOCAL_CAPABILITY_PATH}`
- dce_http_probe：`{DCE_HTTP_PROBE_PATH}`
- input_audit：`{INPUT_AUDIT_PATH}`
- decision：`{DECISION_PATH}`
"""
    REPORT_PATH.write_text(report, encoding="utf-8")


def write_stage_record(decision: dict[str, Any]) -> Path:
    now = datetime.now()
    stage_path = STAGES_DIR / f"{now:%Y%m%d_%H%M}_stage091_jd_margin_source_contract_matrix.md"
    text = f"""# Stage091 JD 保证金数据源资格矩阵

- line_id：`{LINE_ID}`
- 当前模式：day
- 记录时间：{now:%Y-%m-%d %H:%M} CST
- 工作区/分支：`{ROOT}`
- 阶段性质：数据合同/来源资格闸门
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：DCE 日交易参数页、DCE 对外门户 API 服务新闻、AKShare futures_settle 文档、GTJA calendar、CnOpenData 每日期货结算参数数据库。
- 我的判断：当前没有任何已验收的 `jd_contract_daily_margin_history`。能进入 true ledger 的路线只剩 DCE 注册门户 API/官方原始表，或授权 vendor 的逐日结算参数导出；GTJA、TqSdk 当前 quote/settlement、RQData 当前 `get_commission_margin` 都不能直接作为 2020-2026 JD 逐日保证金历史。

## 本次变更

- 新增脚本：`research/lines/{LINE_ID}/tools/stage091_jd_margin_source_contract_matrix.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：`--timeout`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：2020-01-02 到 2026-06-30 的 JD true-ledger 数据需求；本阶段不回测。
- 账户规模：不适用
- 成本口径：不适用
- 样本过滤：仅做数据源资格和本地能力审计。
- 策略/归因口径：不改策略、不跑 true engine、不连接 CTP、不调用订单 API。

## 结果

- 期末权益：不适用
- 总收益：不适用
- 最大回撤：不适用
- Sharpe：不适用
- 总滑点：不适用
- 总交易次数：不适用
- 胜率：不适用
- 其他关键指标：`accepted_route_count={decision['accepted_route_count']}`，`can_be_accepted_after_import_count={decision['can_be_accepted_after_import_count']}`，`preferred_next_route={decision['preferred_next_route']}`，`ready_for_true_ledger_replay=False`。

## 输出文件

- report：`{REPORT_PATH}`
- summary：`{ROUTE_MATRIX_PATH}`
- orders：不适用
- daily：不适用
- quality：`{LOCAL_CAPABILITY_PATH}`

## 结论

- 本阶段结论：`{decision['decision']}`。
- 是否进入下一步：是。
- 下一步：优先获取 DCE 注册门户 API 文档/凭证或授权 vendor 逐日结算参数样本；拿到后先做 hash/PIT/覆盖验收，再考虑 Stage208 true ledger。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：只做数据源资格矩阵，不看收益、不调策略参数。

## 继续价值反思

- 运行前判断：有。
- 运行后判断：有。
- 原因：JD 保证金历史仍是 true ledger 硬阻塞，但已明确下一步不应继续在 GTJA 或 DCE 未授权公共端点上消耗。

## 合入建议

- 是否更新本线 `LINE.md`：暂不更新，等拿到 DCE/vendor 数据或确认路线废弃再更新。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：否。
"""
    stage_path.write_text(text, encoding="utf-8")
    return stage_path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeout", type=float, default=8.0)
    args = parser.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    STAGES_DIR.mkdir(parents=True, exist_ok=True)

    stage088 = _read_json(STAGE088_DECISION)
    stage089 = _read_json(STAGE089_DECISION)
    stage090 = _read_json(STAGE090_DECISION)
    stage090_coverage = _read_csv(STAGE090_COVERAGE)
    local_capability = build_local_capability()
    dce_probe = probe_dce_http(args.timeout)
    route_matrix = build_route_matrix(local_capability, dce_probe, stage088, stage089, stage090, stage090_coverage)
    input_audit = _input_audit([STAGE088_DECISION, STAGE089_DECISION, STAGE090_DECISION, STAGE090_COVERAGE])
    decision = build_decision(route_matrix, local_capability, dce_probe)

    local_capability.to_csv(LOCAL_CAPABILITY_PATH, index=False, encoding="utf-8-sig")
    dce_probe.to_csv(DCE_HTTP_PROBE_PATH, index=False, encoding="utf-8-sig")
    route_matrix.to_csv(ROUTE_MATRIX_PATH, index=False, encoding="utf-8-sig")
    input_audit.to_csv(INPUT_AUDIT_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    write_report(route_matrix, local_capability, dce_probe, decision)
    stage_path = write_stage_record(decision)

    print(json.dumps(_json_safe({"decision": decision, "stage_path": stage_path, "report_path": REPORT_PATH}), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
