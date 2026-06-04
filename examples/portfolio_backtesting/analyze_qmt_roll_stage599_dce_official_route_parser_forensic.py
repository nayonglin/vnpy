from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import inspect
import io
import json
import math
import multiprocessing as mp
import os
from pathlib import Path
import re
from typing import Any
from zoneinfo import ZoneInfo


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
os.environ.setdefault("MPLCONFIGDIR", str(OUTPUT_DIR / ".matplotlib"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


MODEL_TAG = "stage599_dce_official_route_parser_forensic_v1"
OUTPUT_PREFIX = "qmt_roll_stage599_dce_official_route_parser_forensic"
LINE_ID = "futures_trend_drawdown30_preserve_return"

FUNCTION_FORENSICS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_function_forensics_{MODEL_TAG}.csv"
AKSHARE_PROBE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_akshare_probe_{MODEL_TAG}.csv"
HTTP_PROBE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_http_probe_{MODEL_TAG}.csv"
ROUTE_READINESS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_route_readiness_{MODEL_TAG}.csv"
GATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gates_{MODEL_TAG}.csv"
NEXT_ACTIONS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_next_actions_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

PRODUCTS = {
    "j.DCE": {"code": "J", "variety": "j", "family": "black_ferrous", "cn_name": "coke"},
    "i.DCE": {"code": "I", "variety": "i", "family": "black_ferrous", "cn_name": "iron_ore"},
}

AK_FUNCTIONS = [
    "futures_warehouse_receipt_dce",
    "futures_dce_position_rank",
    "get_dce_rank_table",
    "futures_dce_position_rank_other",
]

HTTP_TIMEOUT = 10
WORKER_TIMEOUT = 16
LOOKBACK_DAYS = 7
EXPECTED_PRODUCTS = ["j.DCE", "i.DCE"]


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, tuple):
        return [_json_safe(v) for v in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        number = float(value)
        return None if math.isnan(number) or math.isinf(number) else number
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    return value


def _stable_hash(payload: Any) -> str:
    text = json.dumps(_json_safe(payload), ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _md_table(frame: pd.DataFrame, columns: list[str] | None = None, max_rows: int = 30) -> str:
    if frame.empty:
        return "_empty_"
    view = frame.copy()
    if columns is not None:
        view = view[[col for col in columns if col in view.columns]]
    if len(view) > max_rows:
        view = view.head(max_rows)
    for column in view.columns:
        if pd.api.types.is_float_dtype(view[column]):
            view[column] = view[column].map(lambda item: f"{item:.4f}" if pd.notna(item) else "")
    return view.to_markdown(index=False)


def _now_pair() -> tuple[datetime, datetime]:
    now_utc = datetime.now(timezone.utc)
    now_local = now_utc.astimezone(ZoneInfo("Asia/Shanghai"))
    return now_local, now_utc


def _candidate_dates(now_local: datetime) -> list[str]:
    day = pd.Timestamp(now_local.date())
    return [(day - pd.Timedelta(days=offset)).strftime("%Y%m%d") for offset in range(LOOKBACK_DAYS + 1)]


def _extract_urls(source: str) -> list[str]:
    return sorted(set(re.findall(r"https?://[^\"'\s)]+", source)))


def collect_function_forensics(now_local: datetime) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    try:
        import akshare as ak

        ak_version = getattr(ak, "__version__", "")
    except Exception as exc:
        return pd.DataFrame(
            [
                {
                    "function_name": "akshare_import",
                    "akshare_version": "",
                    "exists": 0,
                    "signature": "",
                    "source_file": "",
                    "source_sha256": "",
                    "embedded_urls": "",
                    "status": "error",
                    "error_type": type(exc).__name__,
                    "error_message": str(exc)[:700],
                    "observed_at": now_local.isoformat(timespec="seconds"),
                }
            ]
        )

    for name in AK_FUNCTIONS:
        row = {
            "function_name": name,
            "akshare_version": ak_version,
            "exists": 0,
            "signature": "",
            "source_file": "",
            "source_sha256": "",
            "embedded_urls": "",
            "status": "missing",
            "error_type": "",
            "error_message": "",
            "observed_at": now_local.isoformat(timespec="seconds"),
        }
        try:
            fn = getattr(ak, name, None)
            if fn is None:
                rows.append(row)
                continue
            source = inspect.getsource(fn)
            row.update(
                {
                    "exists": 1,
                    "signature": str(inspect.signature(fn)),
                    "source_file": inspect.getfile(fn),
                    "source_sha256": hashlib.sha256(source.encode("utf-8")).hexdigest(),
                    "embedded_urls": " | ".join(_extract_urls(source)),
                    "status": "ok",
                }
            )
        except Exception as exc:
            row.update({"status": "error", "error_type": type(exc).__name__, "error_message": str(exc)[:700]})
        rows.append(row)
    return pd.DataFrame(rows)


def _summarize_akshare_result(result: Any) -> dict[str, Any]:
    if isinstance(result, pd.DataFrame):
        columns = [str(col) for col in result.columns]
        records = result.head(3).to_dict("records") if len(result) else []
        return {
            "result_kind": "dataframe",
            "rows": int(len(result)),
            "keys_count": 0,
            "sample_keys": "",
            "columns": ",".join(columns[:20]),
            "sample_hash": _stable_hash(records),
        }
    if isinstance(result, dict):
        keys = list(result.keys())
        rows_total = 0
        product_hits = {symbol: 0 for symbol in EXPECTED_PRODUCTS}
        for key, value in result.items():
            key_text = str(key).lower()
            if isinstance(value, pd.DataFrame):
                rows_total += int(len(value))
            for symbol, meta in PRODUCTS.items():
                if re.match(rf"^{re.escape(meta['variety'])}\d", key_text) or key_text.upper() == meta["code"]:
                    product_hits[symbol] = 1
        return {
            "result_kind": "dict",
            "rows": rows_total,
            "keys_count": int(len(keys)),
            "sample_keys": ",".join([str(key) for key in keys[:12]]),
            "columns": "",
            "sample_hash": _stable_hash([str(key) for key in keys[:20]]),
            **{f"hit_{symbol}": hit for symbol, hit in product_hits.items()},
        }
    return {
        "result_kind": type(result).__name__,
        "rows": 0,
        "keys_count": 0,
        "sample_keys": "",
        "columns": "",
        "sample_hash": _stable_hash(str(result)[:500]),
    }


def _call_akshare(function_name: str, args: tuple[Any, ...], kwargs: dict[str, Any], timeout: int = WORKER_TIMEOUT) -> dict[str, Any]:
    def worker(queue: mp.Queue) -> None:
        try:
            import akshare as ak

            fn = getattr(ak, function_name)
            result = fn(*args, **kwargs)
            queue.put({"status": "ok", **_summarize_akshare_result(result)})
        except Exception as exc:  # pragma: no cover - external endpoints are unstable
            queue.put(
                {
                    "status": "error",
                    "result_kind": "",
                    "rows": 0,
                    "keys_count": 0,
                    "sample_keys": "",
                    "columns": "",
                    "sample_hash": "",
                    "error_type": type(exc).__name__,
                    "error_message": str(exc)[:700],
                }
            )

    ctx = mp.get_context("fork")
    queue: mp.Queue = ctx.Queue()
    process = ctx.Process(target=worker, args=(queue,))
    process.start()
    process.join(timeout)
    if process.is_alive():
        process.terminate()
        process.join(2)
        return {
            "status": "timeout",
            "result_kind": "",
            "rows": 0,
            "keys_count": 0,
            "sample_keys": "",
            "columns": "",
            "sample_hash": "",
            "error_type": "Timeout",
            "error_message": f">{timeout}s",
        }
    if queue.empty():
        return {
            "status": "empty",
            "result_kind": "",
            "rows": 0,
            "keys_count": 0,
            "sample_keys": "",
            "columns": "",
            "sample_hash": "",
            "error_type": "EmptyResult",
            "error_message": "worker returned no message",
        }
    return queue.get()


def collect_akshare_probes(now_local: datetime) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    dates = _candidate_dates(now_local)
    for date in dates[:4]:
        probes = [
            ("futures_warehouse_receipt_dce", (date,), {}),
            ("futures_dce_position_rank", (date,), {"vars_list": ["J", "I"]}),
            ("get_dce_rank_table", (date,), {"vars_list": ["J", "I"]}),
        ]
        for function_name, args, kwargs in probes:
            result = _call_akshare(function_name, args, kwargs)
            rows.append(
                {
                    "probe_date": date,
                    "function_name": function_name,
                    "args_json": json.dumps(_json_safe(args), ensure_ascii=False),
                    "kwargs_json": json.dumps(_json_safe(kwargs), ensure_ascii=False, sort_keys=True),
                    "status": result.get("status", ""),
                    "result_kind": result.get("result_kind", ""),
                    "rows": int(result.get("rows", 0) or 0),
                    "keys_count": int(result.get("keys_count", 0) or 0),
                    "sample_keys": result.get("sample_keys", ""),
                    "columns": result.get("columns", ""),
                    "hit_j.DCE": int(result.get("hit_j.DCE", 0) or 0),
                    "hit_i.DCE": int(result.get("hit_i.DCE", 0) or 0),
                    "error_type": result.get("error_type", ""),
                    "error_message": result.get("error_message", ""),
                    "sample_hash": result.get("sample_hash", ""),
                }
            )
    return pd.DataFrame(rows)


def _text_head(content: bytes, limit: int = 240) -> str:
    text = content[:limit].decode("utf-8", errors="replace")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _http_probe(
    name: str,
    method: str,
    url: str,
    expected: str,
    params: dict[str, Any] | None = None,
    data: dict[str, Any] | None = None,
    json_payload: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    import requests

    started = datetime.now(timezone.utc)
    row = {
        "probe_name": name,
        "method": method,
        "url": url,
        "expected": expected,
        "status": "not_run",
        "http_status": 0,
        "content_type": "",
        "content_length": 0,
        "elapsed_ms": np.nan,
        "is_json": 0,
        "json_top_keys": "",
        "entity_count": 0,
        "is_zip": 0,
        "zip_file_count": 0,
        "html_contract_count": 0,
        "text_head": "",
        "error_type": "",
        "error_message": "",
        "raw_sha256": "",
    }
    try:
        session = requests.Session()
        req_headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            "Accept": "application/json,text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        if headers:
            req_headers.update(headers)
        if method.upper() == "POST":
            response = session.post(
                url,
                params=params,
                data=data,
                json=json_payload,
                headers=req_headers,
                timeout=HTTP_TIMEOUT,
            )
        else:
            response = session.get(url, params=params, headers=req_headers, timeout=HTTP_TIMEOUT)
        elapsed_ms = (datetime.now(timezone.utc) - started).total_seconds() * 1000.0
        content = response.content or b""
        row.update(
            {
                "status": "response",
                "http_status": int(response.status_code),
                "content_type": response.headers.get("Content-Type", ""),
                "content_length": int(len(content)),
                "elapsed_ms": elapsed_ms,
                "text_head": _text_head(content),
                "raw_sha256": hashlib.sha256(content).hexdigest(),
            }
        )
        if content.startswith(b"PK"):
            row["is_zip"] = 1
            try:
                import zipfile

                with zipfile.ZipFile(io.BytesIO(content), mode="r") as zf:
                    row["zip_file_count"] = len(zf.namelist())
            except Exception as exc:
                row["error_type"] = type(exc).__name__
                row["error_message"] = str(exc)[:700]
        try:
            parsed = response.json()
            row["is_json"] = 1
            if isinstance(parsed, dict):
                row["json_top_keys"] = ",".join([str(key) for key in parsed.keys()])
                data_obj = parsed.get("data")
                if isinstance(data_obj, dict):
                    entity = data_obj.get("entityList")
                    if isinstance(entity, list):
                        row["entity_count"] = len(entity)
            elif isinstance(parsed, list):
                row["json_top_keys"] = "list"
                row["entity_count"] = len(parsed)
        except Exception:
            pass
        text = content.decode("utf-8", errors="ignore")
        row["html_contract_count"] = len(re.findall(r"name=[\"']contract[\"']", text))
        if expected == "json" and not row["is_json"]:
            row["status"] = "not_json"
            row["error_type"] = row["error_type"] or "JSONDecodeError"
        elif expected == "zip" and not row["is_zip"]:
            row["status"] = "not_zip"
            row["error_type"] = row["error_type"] or "BadZipFile"
        elif response.status_code != 200:
            row["status"] = "http_error"
        else:
            row["status"] = "ok"
    except Exception as exc:  # pragma: no cover - external endpoints are unstable
        elapsed_ms = (datetime.now(timezone.utc) - started).total_seconds() * 1000.0
        row.update(
            {
                "status": "network_error",
                "elapsed_ms": elapsed_ms,
                "error_type": type(exc).__name__,
                "error_message": str(exc)[:700],
            }
        )
    return row


def collect_http_probes(now_local: datetime) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    dates = _candidate_dates(now_local)
    member_url = "http://www.dce.com.cn/dcereport/publicweb/dailystat/memberDealPosi/batchDownload"
    warehouse_url = "http://www.dce.com.cn/dcereport/publicweb/dailystat/wbillWeeklyQuotes"
    legacy_member_url = "http://portal.dce.com.cn/publicweb/quotesdata/memberDealPosiQuotes.html"
    legacy_warehouse_url = "http://portal.dce.com.cn/publicweb/quotesdata/wbillWeeklyQuotes.html"

    for date in dates[:5]:
        rows.append(
            {
                "probe_date": date,
                **_http_probe(
                    name="member_batch_download_source_payload",
                    method="POST",
                    url=member_url,
                    expected="zip",
                    json_payload={
                        "tradeDate": date,
                        "varietyId": "a",
                        "contractId": "a2601",
                        "tradeType": "1",
                        "lang": "zh",
                    },
                ),
            }
        )
        rows.append(
            {
                "probe_date": date,
                **_http_probe(
                    name="warehouse_json_all",
                    method="POST",
                    url=warehouse_url,
                    expected="json",
                    json_payload={"tradeDate": date, "varietyId": "all"},
                ),
            }
        )
        rows.append(
            {
                "probe_date": date,
                **_http_probe(
                    name="warehouse_form_all",
                    method="POST",
                    url=warehouse_url,
                    expected="json",
                    data={"tradeDate": date, "varietyId": "all"},
                ),
            }
        )
    for date in dates[:3]:
        year = int(date[:4])
        month_zero_based = int(date[4:6]) - 1
        day = int(date[6:8])
        for symbol, meta in PRODUCTS.items():
            rows.append(
                {
                    "probe_date": date,
                    "product_vt_symbol": symbol,
                    **_http_probe(
                        name="legacy_member_html_contract_all",
                        method="POST",
                        url=legacy_member_url,
                        expected="html",
                        data={
                            "memberDealPosiQuotes.variety": meta["variety"],
                            "memberDealPosiQuotes.trade_type": "0",
                            "year": year,
                            "month": month_zero_based,
                            "day": str(day).zfill(2),
                            "contract.contract_id": "all",
                            "contract.variety_id": meta["variety"],
                            "contract": "",
                        },
                    ),
                }
            )
    rows.append(
        {
            "probe_date": dates[0],
            **_http_probe(
                name="legacy_warehouse_html_landing",
                method="GET",
                url=legacy_warehouse_url,
                expected="html",
            ),
        }
    )
    return pd.DataFrame(rows)


def build_route_readiness(akshare_probe: pd.DataFrame, http_probe: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for symbol in EXPECTED_PRODUCTS:
        member_ak = akshare_probe[
            (akshare_probe["function_name"].isin(["futures_dce_position_rank", "get_dce_rank_table"]))
            & (pd.to_numeric(akshare_probe[f"hit_{symbol}"], errors="coerce").fillna(0) > 0)
        ]
        member_http = http_probe[
            http_probe["probe_name"].isin(["member_batch_download_source_payload", "legacy_member_html_contract_all"])
            & (http_probe["status"].eq("ok"))
        ]
        warehouse_ak = akshare_probe[
            (akshare_probe["function_name"].eq("futures_warehouse_receipt_dce"))
            & (akshare_probe["status"].eq("ok"))
            & ((pd.to_numeric(akshare_probe["rows"], errors="coerce").fillna(0) > 0) | (pd.to_numeric(akshare_probe["keys_count"], errors="coerce").fillna(0) > 0))
        ]
        warehouse_http = http_probe[
            http_probe["probe_name"].isin(["warehouse_json_all", "warehouse_form_all"])
            & (http_probe["status"].eq("ok"))
            & (pd.to_numeric(http_probe["entity_count"], errors="coerce").fillna(0) > 0)
        ]
        rows.append(
            {
                "product_vt_symbol": symbol,
                "route": "member_detail",
                "official_route_found": int(not member_http.empty or not member_ak.empty),
                "akshare_parser_ready": int(not member_ak.empty),
                "direct_http_ready": int(not member_http.empty),
                "latest_akshare_error": _latest_error(
                    akshare_probe[akshare_probe["function_name"].isin(["futures_dce_position_rank", "get_dce_rank_table"])]
                ),
                "promotion_ready": int(not member_ak.empty),
            }
        )
        rows.append(
            {
                "product_vt_symbol": symbol,
                "route": "warehouse",
                "official_route_found": int(not warehouse_http.empty or not warehouse_ak.empty),
                "akshare_parser_ready": int(not warehouse_ak.empty),
                "direct_http_ready": int(not warehouse_http.empty),
                "latest_akshare_error": _latest_error(
                    akshare_probe[akshare_probe["function_name"].eq("futures_warehouse_receipt_dce")]
                ),
                "promotion_ready": int(not warehouse_ak.empty),
            }
        )
    return pd.DataFrame(rows)


def _latest_error(frame: pd.DataFrame) -> str:
    if frame.empty:
        return ""
    errors = frame[frame["status"].ne("ok")].copy()
    if errors.empty:
        return ""
    row = errors.iloc[0]
    return f"{row.get('error_type', '')}: {row.get('error_message', '')}"[:500]


def build_gates(function_forensics: pd.DataFrame, akshare_probe: pd.DataFrame, http_probe: pd.DataFrame, route_readiness: pd.DataFrame) -> pd.DataFrame:
    gates = [
        {
            "gate": "akshare_import_and_functions_exist",
            "required": "all required functions exist",
            "value": int(function_forensics["exists"].sum()),
            "threshold": len(AK_FUNCTIONS),
            "passed": int(int(function_forensics["exists"].sum()) == len(AK_FUNCTIONS)),
            "hard_gate": 1,
        },
        {
            "gate": "dce_member_official_http_reachable",
            "required": "member HTTP returns zip or parseable legacy html",
            "value": int(
                len(
                    http_probe[
                        http_probe["probe_name"].isin(["member_batch_download_source_payload", "legacy_member_html_contract_all"])
                        & http_probe["status"].eq("ok")
                    ]
                )
            ),
            "threshold": 1,
            "passed": int(
                len(
                    http_probe[
                        http_probe["probe_name"].isin(["member_batch_download_source_payload", "legacy_member_html_contract_all"])
                        & http_probe["status"].eq("ok")
                    ]
                )
                >= 1
            ),
            "hard_gate": 1,
        },
        {
            "gate": "dce_warehouse_official_http_reachable",
            "required": "warehouse HTTP returns json entityList",
            "value": int(
                len(
                    http_probe[
                        http_probe["probe_name"].isin(["warehouse_json_all", "warehouse_form_all"])
                        & http_probe["status"].eq("ok")
                        & (pd.to_numeric(http_probe["entity_count"], errors="coerce").fillna(0) > 0)
                    ]
                )
            ),
            "threshold": 1,
            "passed": int(
                len(
                    http_probe[
                        http_probe["probe_name"].isin(["warehouse_json_all", "warehouse_form_all"])
                        & http_probe["status"].eq("ok")
                        & (pd.to_numeric(http_probe["entity_count"], errors="coerce").fillna(0) > 0)
                    ]
                )
                >= 1
            ),
            "hard_gate": 1,
        },
        {
            "gate": "dce_member_akshare_parser_ready_for_j_i",
            "required": "j/i both hit through AKShare member route",
            "value": int(route_readiness[(route_readiness["route"].eq("member_detail")) & route_readiness["akshare_parser_ready"].eq(1)].shape[0]),
            "threshold": len(EXPECTED_PRODUCTS),
            "passed": int(route_readiness[(route_readiness["route"].eq("member_detail")) & route_readiness["akshare_parser_ready"].eq(1)].shape[0] == len(EXPECTED_PRODUCTS)),
            "hard_gate": 1,
        },
        {
            "gate": "dce_warehouse_akshare_parser_ready",
            "required": "warehouse parser returns non-empty rows",
            "value": int(route_readiness[(route_readiness["route"].eq("warehouse")) & route_readiness["akshare_parser_ready"].eq(1)].shape[0]),
            "threshold": len(EXPECTED_PRODUCTS),
            "passed": int(route_readiness[(route_readiness["route"].eq("warehouse")) & route_readiness["akshare_parser_ready"].eq(1)].shape[0] == len(EXPECTED_PRODUCTS)),
            "hard_gate": 1,
        },
        {
            "gate": "black_ferrous_p1_promotion_allowed",
            "required": "official member and warehouse parser ready for both products",
            "value": int(route_readiness["promotion_ready"].sum()),
            "threshold": len(EXPECTED_PRODUCTS) * 2,
            "passed": int(route_readiness["promotion_ready"].sum() == len(EXPECTED_PRODUCTS) * 2),
            "hard_gate": 1,
        },
        {
            "gate": "no_strategy_backtest_or_parameter_search",
            "required": "forensic stage only",
            "value": 1,
            "threshold": 1,
            "passed": 1,
            "hard_gate": 1,
        },
    ]
    return pd.DataFrame(gates)


def build_next_actions(gates: pd.DataFrame, akshare_probe: pd.DataFrame, http_probe: pd.DataFrame) -> pd.DataFrame:
    actions: list[dict[str, Any]] = []
    member_bad_zip = akshare_probe[
        akshare_probe["function_name"].eq("futures_dce_position_rank")
        & akshare_probe["error_type"].astype(str).str.contains("BadZipFile", na=False)
    ]
    warehouse_json_error = akshare_probe[
        akshare_probe["function_name"].eq("futures_warehouse_receipt_dce")
        & akshare_probe["error_type"].astype(str).str.contains("JSONDecodeError", na=False)
    ]
    member_http_ok = http_probe[
        http_probe["probe_name"].isin(["member_batch_download_source_payload", "legacy_member_html_contract_all"])
        & http_probe["status"].eq("ok")
    ]
    warehouse_http_ok = http_probe[
        http_probe["probe_name"].isin(["warehouse_json_all", "warehouse_form_all"])
        & http_probe["status"].eq("ok")
        & (pd.to_numeric(http_probe["entity_count"], errors="coerce").fillna(0) > 0)
    ]

    if not member_http_ok.empty and not member_bad_zip.empty:
        actions.append(
            {
                "priority": "P0",
                "action": "Patch local member parser or switch Stage598 to direct DCE endpoint",
                "reason": "Official member route is reachable but AKShare parser still fails.",
                "promotion_effect": "Can turn member_detail from red to green after product-key validation.",
            }
        )
    elif member_http_ok.empty:
        actions.append(
            {
                "priority": "P0",
                "action": "Do not promote j/i; collect exact DCE access failure evidence and retry with stable official endpoint",
                "reason": "Member route is not reliably reachable through current environment.",
                "promotion_effect": "Blocks official source gate.",
            }
        )
    if not warehouse_http_ok.empty and not warehouse_json_error.empty:
        actions.append(
            {
                "priority": "P0",
                "action": "Patch local warehouse parser around current DCE JSON response",
                "reason": "Official warehouse route is reachable but AKShare wrapper raises JSONDecodeError on some dates.",
                "promotion_effect": "Can turn warehouse from red to green after j/i row matching.",
            }
        )
    elif warehouse_http_ok.empty:
        actions.append(
            {
                "priority": "P0",
                "action": "Do not promote j/i; keep warehouse route as blocked until JSON entityList is stable",
                "reason": "Warehouse endpoint did not return parseable product rows.",
                "promotion_effect": "Blocks official source gate.",
            }
        )
    actions.append(
        {
            "priority": "P1",
            "action": "Keep accumulating forward received_at dates only after official parser closure",
            "reason": "Forward depth cannot compensate for an untrusted parser route.",
            "promotion_effect": "Preserves point-in-time discipline.",
        }
    )
    actions.append(
        {
            "priority": "P1",
            "action": "No product whitelist, paper sleeve, or return backtest for j/i yet",
            "reason": "This stage is source-route forensics, not alpha proof.",
            "promotion_effect": "Avoids overfitting and false source confidence.",
        }
    )
    return pd.DataFrame(actions)


def _status_score(status: str) -> float:
    if status == "ok":
        return 1.0
    if status in {"response", "not_json", "not_zip"}:
        return 0.35
    if status == "timeout":
        return 0.15
    return 0.0


def write_chart(function_forensics: pd.DataFrame, akshare_probe: pd.DataFrame, http_probe: pd.DataFrame, route_readiness: pd.DataFrame, gates: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(16, 10))
    fig.suptitle("Stage599 DCE Official Route Parser Forensic", fontsize=15, fontweight="bold")

    ax = axes[0, 0]
    fn_view = function_forensics.copy()
    colors = ["#2f855a" if item == "ok" else "#c53030" for item in fn_view["status"]]
    ax.barh(fn_view["function_name"], fn_view["exists"], color=colors)
    ax.set_xlim(0, 1.2)
    version = fn_view["akshare_version"].dropna().astype(str).iloc[0] if not fn_view.empty else ""
    ax.set_title(f"Local AKShare functions (version {version})")
    ax.set_xlabel("exists")

    ax = axes[0, 1]
    ak_view = akshare_probe.groupby("function_name", as_index=False).agg(
        ok_count=("status", lambda s: int((s == "ok").sum())),
        error_count=("status", lambda s: int((s != "ok").sum())),
    )
    y = np.arange(len(ak_view))
    ax.barh(y, ak_view["ok_count"], color="#2f855a", label="ok")
    ax.barh(y, ak_view["error_count"], left=ak_view["ok_count"], color="#c53030", label="not ok")
    ax.set_yticks(y, ak_view["function_name"])
    ax.set_title("AKShare wrapper probes")
    ax.legend(loc="lower right")

    ax = axes[1, 0]
    http_view = http_probe.copy()
    http_view["score"] = http_view["status"].map(_status_score)
    http_summary = http_view.groupby("probe_name", as_index=False)["score"].max().sort_values("score")
    colors = ["#2f855a" if score >= 1 else "#dd6b20" if score > 0 else "#c53030" for score in http_summary["score"]]
    ax.barh(http_summary["probe_name"], http_summary["score"], color=colors)
    ax.set_xlim(0, 1.05)
    ax.set_title("Direct DCE HTTP route best status")
    ax.set_xlabel("1=ready, 0.35=response but wrong format")

    ax = axes[1, 1]
    matrix = route_readiness.pivot(index="product_vt_symbol", columns="route", values="promotion_ready").reindex(EXPECTED_PRODUCTS)
    if matrix.empty:
        matrix = pd.DataFrame(0, index=EXPECTED_PRODUCTS, columns=["member_detail", "warehouse"])
    im = ax.imshow(matrix.fillna(0).values, cmap=matplotlib.colors.ListedColormap(["#c53030", "#2f855a"]), vmin=0, vmax=1)
    ax.set_xticks(np.arange(len(matrix.columns)), matrix.columns, rotation=20, ha="right")
    ax.set_yticks(np.arange(len(matrix.index)), matrix.index)
    ax.set_title("Product official parser readiness")
    for i in range(matrix.shape[0]):
        for j in range(matrix.shape[1]):
            value = int(matrix.iloc[i, j])
            ax.text(j, i, "ready" if value else "blocked", ha="center", va="center", color="white", fontsize=9)

    gate_passed = int(gates["passed"].sum()) if not gates.empty else 0
    gate_total = int(len(gates))
    fig.text(0.01, 0.01, f"Hard gates passed: {gate_passed}/{gate_total}. No strategy backtest or parameter search in this stage.", fontsize=10)
    fig.tight_layout(rect=[0, 0.03, 1, 0.95])
    fig.savefig(CHART_PATH, dpi=150)
    plt.close(fig)


def write_report(
    now_local: datetime,
    function_forensics: pd.DataFrame,
    akshare_probe: pd.DataFrame,
    http_probe: pd.DataFrame,
    route_readiness: pd.DataFrame,
    gates: pd.DataFrame,
    next_actions: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    report = f"""# Stage599 DCE Official Route Parser Forensic

- line_id: `{LINE_ID}`
- observed_at: `{now_local.isoformat(timespec="seconds")}`
- decision: `{decision["decision"]}`
- promotion_allowed: `{decision["promotion_allowed"]}`
- paper_selector_allowed: `{decision["paper_selector_allowed"]}`
- trading_whitelist_allowed: `{decision["trading_whitelist_allowed"]}`

## Scope

This stage is source-route forensics for `j.DCE/i.DCE`. It does not run strategy returns, does not change product whitelist, and does not tune parameters.

## Function Forensics

{_md_table(function_forensics, ["function_name", "akshare_version", "exists", "signature", "status", "embedded_urls"], 20)}

## AKShare Probe Summary

{_md_table(akshare_probe, ["probe_date", "function_name", "status", "result_kind", "rows", "keys_count", "hit_j.DCE", "hit_i.DCE", "error_type", "error_message"], 40)}

## Direct HTTP Probe Summary

{_md_table(http_probe, ["probe_date", "probe_name", "status", "http_status", "content_type", "content_length", "is_json", "entity_count", "is_zip", "zip_file_count", "html_contract_count", "error_type", "text_head"], 50)}

## Route Readiness

{_md_table(route_readiness, None, 20)}

## Gates

{_md_table(gates, None, 20)}

## Next Actions

{_md_table(next_actions, None, 20)}
"""
    REPORT_PATH.write_text(report, encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    now_local, now_utc = _now_pair()

    function_forensics = collect_function_forensics(now_local)
    akshare_probe = collect_akshare_probes(now_local)
    http_probe = collect_http_probes(now_local)
    route_readiness = build_route_readiness(akshare_probe, http_probe)
    gates = build_gates(function_forensics, akshare_probe, http_probe, route_readiness)
    next_actions = build_next_actions(gates, akshare_probe, http_probe)

    hard_gates = gates[gates["hard_gate"].eq(1)].copy()
    hard_passed = int(hard_gates["passed"].sum())
    hard_total = int(len(hard_gates))
    promotion_allowed = bool(hard_passed == hard_total and route_readiness["promotion_ready"].sum() == len(EXPECTED_PRODUCTS) * 2)
    decision = {
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "observed_at_local": now_local.isoformat(timespec="seconds"),
        "observed_at_utc": now_utc.isoformat(timespec="seconds"),
        "decision": "dce_official_route_parser_blocked_no_paper" if not promotion_allowed else "dce_official_route_parser_ready_for_forward_ledger",
        "promotion_allowed": promotion_allowed,
        "paper_selector_allowed": False,
        "trading_whitelist_allowed": False,
        "hard_gates_passed": hard_passed,
        "hard_gates_total": hard_total,
        "akshare_ok_count": int(akshare_probe["status"].eq("ok").sum()),
        "akshare_probe_count": int(len(akshare_probe)),
        "http_ok_count": int(http_probe["status"].eq("ok").sum()),
        "http_probe_count": int(len(http_probe)),
        "route_ready_count": int(route_readiness["promotion_ready"].sum()),
        "route_ready_total": int(len(route_readiness)),
        "outputs": {
            "function_forensics": str(FUNCTION_FORENSICS_PATH),
            "akshare_probe": str(AKSHARE_PROBE_PATH),
            "http_probe": str(HTTP_PROBE_PATH),
            "route_readiness": str(ROUTE_READINESS_PATH),
            "gates": str(GATES_PATH),
            "next_actions": str(NEXT_ACTIONS_PATH),
            "report": str(REPORT_PATH),
            "chart": str(CHART_PATH),
        },
    }

    function_forensics.to_csv(FUNCTION_FORENSICS_PATH, index=False)
    akshare_probe.to_csv(AKSHARE_PROBE_PATH, index=False)
    http_probe.to_csv(HTTP_PROBE_PATH, index=False)
    route_readiness.to_csv(ROUTE_READINESS_PATH, index=False)
    gates.to_csv(GATES_PATH, index=False)
    next_actions.to_csv(NEXT_ACTIONS_PATH, index=False)
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    write_chart(function_forensics, akshare_probe, http_probe, route_readiness, gates)
    write_report(now_local, function_forensics, akshare_probe, http_probe, route_readiness, gates, next_actions, decision)

    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
