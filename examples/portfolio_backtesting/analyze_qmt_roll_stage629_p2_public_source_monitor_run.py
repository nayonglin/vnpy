from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import html
import json
import math
import os
from pathlib import Path
import re
import socket
import ssl
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
os.environ.setdefault("MPLCONFIGDIR", str(OUTPUT_DIR / ".matplotlib"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


LINE_ID = "futures_trend_drawdown30_preserve_return"
MODEL_TAG = "stage629_p2_public_source_monitor_run_v1"
OUTPUT_PREFIX = "qmt_roll_stage629_p2_public_source_monitor_run"

RUN_LEDGER_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_run_ledger_{MODEL_TAG}.csv"
PRODUCT_STATUS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_status_{MODEL_TAG}.csv"
ROUTE_STATUS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_route_status_{MODEL_TAG}.csv"
GATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gates_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

TIMEOUT_SECONDS = 20
MIN_RESPONSE_BYTES = 500
REQUIRED_ACTIVE_PRODUCTS = 3
REQUIRED_ACTIVE_MONITOR_OK_PRODUCTS = 3
REQUIRED_EVENT_MONITOR_PRODUCTS = 2
REQUIRED_PIT_DATES_FOR_SELECTOR = 20

REFERENCES = [
    "SHFE Daily Data: https://www.shfe.cn/eng/reports/StatisticalData/DailyData/",
    "ESMIS API Documentation: https://esmis.nal.usda.gov/api-documentation",
    "NASS Crop Progress methodology: https://www.nass.usda.gov/Surveys/Guide_to_NASS_Surveys/Crop_Progress_and_Condition/index.php",
    "ESMIS Crop Progress release page: https://esmis.nal.usda.gov/publication/crop-progress/2026-06-01",
    "ESMIS WASDE release page: https://esmis.nal.usda.gov/publication/world-agricultural-supply-and-demand-estimates/2026-05-12-0",
    "ERS Cotton and Wool Outlook: https://ers.usda.gov/publications/pub-details?pubid=114047",
]

ACTIVE_MONITOR_TARGETS = [
    {
        "product_vt_symbol": "ag.SHFE",
        "product_family": "precious_metals",
        "source_name": "SHFE Daily Data",
        "source_url": "https://www.shfe.cn/eng/reports/StatisticalData/DailyData/",
        "source_authority": "official_public_exchange",
        "source_class": "public_html_daily_data",
        "route": "exchange_warehouse_member",
        "event_family": "exchange_warehouse_member",
        "event_type": "shfe_daily_data_page",
        "monitor_frequency": "exchange_daily",
        "keywords": ["Daily Warrant", "Daily Ranking", "Warehouse", "SHFE"],
        "expected_products": ["ag", "silver", "warrant", "ranking"],
        "mapping_method": "direct_shfe_product_to_daily_data_page",
        "event_monitor_candidate": 0,
    },
    {
        "product_vt_symbol": "CY.CZCE",
        "product_family": "soft_agri",
        "source_name": "ESMIS Crop Progress release page",
        "source_url": "https://esmis.nal.usda.gov/publication/crop-progress/2026-06-01",
        "source_authority": "official_public_usda",
        "source_class": "public_html_event_release_page",
        "route": "manual_event",
        "event_family": "crop_progress_condition",
        "event_type": "crop_progress_release_page",
        "monitor_frequency": "weekly_in_season",
        "keywords": ["Crop Progress", "Release date", "prog2226.txt", "Jun 01 2026"],
        "expected_products": ["cotton", "crop", "progress"],
        "mapping_method": "manual_cotton_supply_to_czce_cotton_yarn_chain",
        "event_monitor_candidate": 1,
    },
    {
        "product_vt_symbol": "CY.CZCE",
        "product_family": "soft_agri",
        "source_name": "NASS Crop Progress guide",
        "source_url": "https://www.nass.usda.gov/Surveys/Guide_to_NASS_Surveys/Crop_Progress_and_Condition/index.php",
        "source_authority": "official_public_usda",
        "source_class": "public_html_event_methodology",
        "route": "manual_event",
        "event_family": "crop_progress_condition",
        "event_type": "crop_progress_methodology_page",
        "monitor_frequency": "methodology_reference",
        "keywords": ["4:00 p.m.", "Crop Progress", "condition", "Quick Stats"],
        "expected_products": ["cotton", "condition", "progress"],
        "mapping_method": "methodology_support_for_crop_progress_monitor",
        "event_monitor_candidate": 1,
    },
    {
        "product_vt_symbol": "CY.CZCE",
        "product_family": "soft_agri",
        "source_name": "USDA ERS Cotton and Wool Outlook",
        "source_url": "https://ers.usda.gov/publications/pub-details?pubid=114047",
        "source_authority": "official_public_usda",
        "source_class": "public_html_event_release_page",
        "route": "monthly_supply_demand",
        "event_family": "monthly_supply_demand",
        "event_type": "cotton_wool_outlook_release_page",
        "monitor_frequency": "monthly_release",
        "keywords": ["Cotton and Wool Outlook", "May 2026", "cotton projections", "Download"],
        "expected_products": ["cotton", "wool", "outlook"],
        "mapping_method": "manual_cotton_supply_to_czce_cotton_yarn_chain",
        "event_monitor_candidate": 1,
    },
    {
        "product_vt_symbol": "SR.CZCE",
        "product_family": "soft_agri",
        "source_name": "ESMIS WASDE release page",
        "source_url": "https://esmis.nal.usda.gov/publication/world-agricultural-supply-and-demand-estimates/2026-05-12-0",
        "source_authority": "official_public_usda",
        "source_class": "public_html_event_release_page",
        "route": "monthly_supply_demand",
        "event_family": "monthly_supply_demand",
        "event_type": "wasde_esmis_release_page",
        "monitor_frequency": "monthly_release",
        "keywords": ["WASDE", "wasde0526v2.txt", "World Agricultural Supply and Demand Estimates", "May 12 2026"],
        "expected_products": ["sugar", "cotton", "WASDE"],
        "mapping_method": "manual_sugar_supply_to_czce_white_sugar",
        "event_monitor_candidate": 1,
    },
    {
        "product_vt_symbol": "CY.CZCE,SR.CZCE",
        "product_family": "soft_agri",
        "source_name": "ESMIS API Documentation",
        "source_url": "https://esmis.nal.usda.gov/api-documentation",
        "source_authority": "official_public_usda",
        "source_class": "public_api_contract_page",
        "route": "api_contract",
        "event_family": "source_contract",
        "event_type": "esmis_api_documentation",
        "monitor_frequency": "methodology_reference",
        "keywords": ["API Documentation", "publication", "release", "USDA"],
        "expected_products": ["USDA", "ESMIS"],
        "mapping_method": "source_api_contract_for_usda_releases",
        "event_monitor_candidate": 0,
    },
]

BLOCKED_ROUTE_TARGETS = [
    {
        "product_vt_symbol": "CY.CZCE",
        "product_family": "soft_agri",
        "source_name": "CZCE reference data",
        "source_url": "https://english.czce.com.cn/en/DFSStaticFiles/Future/2023/20231229/EnglishFutureDataReferenceData.htm",
        "source_authority": "official_public_exchange",
        "source_class": "official_static_reference",
        "route": "contract_reference",
        "status": "blocked_stage626_http_412",
        "next_action": "browser_cdp_or_authorized_source_forensic",
    },
    {
        "product_vt_symbol": "SR.CZCE",
        "product_family": "soft_agri",
        "source_name": "CZCE reference data",
        "source_url": "https://english.czce.com.cn/en/DFSStaticFiles/Future/2024/20240418/EnglishFutureDataReferenceData.htm",
        "source_authority": "official_public_exchange",
        "source_class": "official_static_reference",
        "route": "contract_reference",
        "status": "blocked_stage626_http_412",
        "next_action": "browser_cdp_or_authorized_source_forensic",
    },
    {
        "product_vt_symbol": "CY.CZCE,SR.CZCE",
        "product_family": "soft_agri",
        "source_name": "CZCE warehouse static file",
        "source_url": "https://www.czce.com.cn/cn/DFSStaticFiles/Future/2024/20240418/FutureDataWhsheet.xlsx",
        "source_authority": "official_public_exchange",
        "source_class": "official_static_warehouse_file",
        "route": "warehouse",
        "status": "blocked_stage626_http_404",
        "next_action": "browser_cdp_or_authorized_source_forensic",
    },
]


def _now_cst() -> datetime:
    return datetime.now(timezone(timedelta(hours=8)))


def _fmt_cst(value: datetime) -> str:
    return value.strftime("%Y-%m-%d %H:%M:%S CST")


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        number = float(value)
        return None if math.isnan(number) or math.isinf(number) else number
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    return value


def _num(frame: pd.DataFrame, column: str, default: float = 0.0) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=float)
    return (
        pd.to_numeric(frame[column], errors="coerce")
        .replace([np.inf, -np.inf], np.nan)
        .fillna(default)
        .astype(float)
    )


def _md_table(frame: pd.DataFrame, columns: list[str] | None = None, max_rows: int = 40) -> str:
    if frame.empty:
        return "_empty_"
    view = frame.copy()
    if columns is not None:
        view = view[[column for column in columns if column in view.columns]]
    if len(view) > max_rows:
        view = view.head(max_rows)
    for column in view.columns:
        if pd.api.types.is_float_dtype(view[column]):
            view[column] = view[column].map(lambda item: f"{item:.4f}" if pd.notna(item) else "")
    return view.to_markdown(index=False)


def _clean_text(text: str) -> str:
    text = re.sub(r"<script\b[^>]*>.*?</script>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<style\b[^>]*>.*?</style>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _decode_body(body: bytes, content_type: str) -> str:
    charset_match = re.search(r"charset=([^;\s]+)", content_type, flags=re.I)
    charsets = [charset_match.group(1)] if charset_match else []
    charsets.extend(["utf-8", "gb18030", "gbk"])
    for charset in charsets:
        try:
            return body.decode(charset, errors="strict")
        except UnicodeError:
            continue
    return body.decode("utf-8", errors="replace")


def _fetch_url(url: str, referer: str = "") -> dict[str, Any]:
    headers = {
        "User-Agent": "Mozilla/5.0 stage629-p2-public-source-monitor/1.0",
        "Accept": "text/html,text/plain,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8",
    }
    if referer:
        headers["Referer"] = referer
    request = Request(url, headers=headers)
    started = datetime.now(timezone.utc)
    try:
        context = ssl.create_default_context()
        with urlopen(request, timeout=TIMEOUT_SECONDS, context=context) as response:
            body = response.read(2_500_000)
            elapsed_ms = round((datetime.now(timezone.utc) - started).total_seconds() * 1000, 1)
            content_type = response.headers.get("content-type", "")
            text = _decode_body(body, content_type)
            return {
                "fetch_status": "ok",
                "http_status": int(getattr(response, "status", 200)),
                "final_url": response.geturl(),
                "content_type": content_type,
                "response_bytes": len(body),
                "elapsed_ms": elapsed_ms,
                "text": text,
                "raw_sha256": hashlib.sha256(body).hexdigest() if body else "",
                "fetch_error": "",
            }
    except HTTPError as error:
        body = error.read(200_000)
        content_type = error.headers.get("content-type", "") if error.headers else ""
        return {
            "fetch_status": "http_error",
            "http_status": int(error.code),
            "final_url": url,
            "content_type": content_type,
            "response_bytes": len(body),
            "elapsed_ms": round((datetime.now(timezone.utc) - started).total_seconds() * 1000, 1),
            "text": _decode_body(body, content_type) if body else "",
            "raw_sha256": hashlib.sha256(body).hexdigest() if body else "",
            "fetch_error": str(error),
        }
    except (URLError, socket.timeout, TimeoutError) as error:
        return {
            "fetch_status": "network_error",
            "http_status": 0,
            "final_url": url,
            "content_type": "",
            "response_bytes": 0,
            "elapsed_ms": round((datetime.now(timezone.utc) - started).total_seconds() * 1000, 1),
            "text": "",
            "raw_sha256": "",
            "fetch_error": repr(error),
        }


def _keyword_hits(text: str, keywords: list[str]) -> tuple[int, str]:
    lowered = text.lower()
    hits = [keyword for keyword in keywords if keyword.lower() in lowered]
    return len(hits), ",".join(hits)


def _discover_text_link(source_url: str, text: str) -> str:
    links = re.findall(r'href=["\']([^"\']+)["\']', text, flags=re.I)
    txt_links = [urljoin(source_url, link) for link in links if ".txt" in link.lower()]
    if not txt_links:
        return ""
    priority_patterns = ["prog", "wasde"]
    for pattern in priority_patterns:
        for link in txt_links:
            if pattern in link.lower():
                return link
    return txt_links[0]


def build_run_ledger(generated_at: datetime) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    run_id = f"{MODEL_TAG}_{generated_at.strftime('%Y%m%d_%H%M%S')}"
    received_at_local = _fmt_cst(generated_at)
    received_at_utc = generated_at.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    for index, target in enumerate(ACTIVE_MONITOR_TARGETS, start=1):
        result = _fetch_url(target["source_url"])
        cleaned = _clean_text(result["text"])
        keyword_count, keyword_hits = _keyword_hits(cleaned, target["keywords"])
        product_count, product_hits = _keyword_hits(cleaned, target["expected_products"])
        discovered_txt = _discover_text_link(result["final_url"] or target["source_url"], result["text"])

        linked_result = {
            "fetch_status": "",
            "http_status": 0,
            "final_url": "",
            "response_bytes": 0,
            "elapsed_ms": 0.0,
            "raw_sha256": "",
            "text": "",
        }
        if discovered_txt:
            linked_result = _fetch_url(discovered_txt, referer=result["final_url"] or target["source_url"])
        linked_cleaned = _clean_text(str(linked_result.get("text", "")))
        linked_keyword_count, linked_keyword_hits = _keyword_hits(linked_cleaned, target["keywords"])
        linked_product_count, linked_product_hits = _keyword_hits(linked_cleaned, target["expected_products"])

        any_raw_hash = int(bool(result["raw_sha256"]) or bool(linked_result.get("raw_sha256")))
        combined_bytes = int(result["response_bytes"]) + int(linked_result.get("response_bytes", 0))
        monitor_ok = int(
            result["fetch_status"] == "ok"
            and result["http_status"] == 200
            and combined_bytes >= MIN_RESPONSE_BYTES
            and any_raw_hash
            and (keyword_count + linked_keyword_count) > 0
            and (product_count + linked_product_count) > 0
        )
        event_auto_monitor_validated = int(
            monitor_ok
            and int(target["event_monitor_candidate"]) == 1
            and (bool(discovered_txt) or target["route"] in {"monthly_supply_demand", "manual_event"})
        )
        rows.append(
            {
                "run_id": run_id,
                "row_id": f"stage629_{index:03d}",
                "received_at_local": received_at_local,
                "received_at_utc": received_at_utc,
                "line_id": LINE_ID,
                "product_vt_symbol": target["product_vt_symbol"],
                "product_family": target["product_family"],
                "source_name": target["source_name"],
                "source_url": target["source_url"],
                "final_url": result["final_url"],
                "source_authority": target["source_authority"],
                "source_class": target["source_class"],
                "route": target["route"],
                "event_family": target["event_family"],
                "event_type": target["event_type"],
                "monitor_frequency": target["monitor_frequency"],
                "http_status": int(result["http_status"]),
                "fetch_status": result["fetch_status"],
                "fetch_error": result["fetch_error"],
                "content_type": result["content_type"],
                "response_bytes": int(result["response_bytes"]),
                "elapsed_ms": float(result["elapsed_ms"]),
                "raw_sha256": result["raw_sha256"],
                "raw_sha256_present": int(bool(result["raw_sha256"])),
                "discovered_txt_url": discovered_txt,
                "linked_text_fetch_status": linked_result.get("fetch_status", ""),
                "linked_text_http_status": int(linked_result.get("http_status", 0) or 0),
                "linked_text_final_url": linked_result.get("final_url", ""),
                "linked_text_bytes": int(linked_result.get("response_bytes", 0) or 0),
                "linked_text_sha256": linked_result.get("raw_sha256", ""),
                "linked_text_sha256_present": int(bool(linked_result.get("raw_sha256", ""))),
                "combined_response_bytes": combined_bytes,
                "any_raw_hash_present": any_raw_hash,
                "keyword_hit_count": keyword_count,
                "keyword_hits": keyword_hits,
                "product_hit_count": product_count,
                "product_hits": product_hits,
                "linked_text_keyword_hit_count": linked_keyword_count,
                "linked_text_keyword_hits": linked_keyword_hits,
                "linked_text_product_hit_count": linked_product_count,
                "linked_text_product_hits": linked_product_hits,
                "combined_keyword_hit_count": keyword_count + linked_keyword_count,
                "combined_product_hit_count": product_count + linked_product_count,
                "monitor_ok": monitor_ok,
                "event_auto_monitor_validated": event_auto_monitor_validated,
                "usable_for_forward_monitor": monitor_ok,
                "usable_for_history_selector": 0,
                "event_signal_ready": 0,
                "paper_or_whitelist_allowed": 0,
                "raw_text_excerpt": cleaned[:240],
                "product_mapping_method": target["mapping_method"],
                "point_in_time_rule": "Use received_at_local/source_url/final_url/raw_sha256 only; never backfill into history selector.",
                "notes": "Repeatable P2 public source monitor run; stage-scoped output, no strategy replay.",
            }
        )
    return pd.DataFrame(rows)


def build_product_status(ledger: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    frame = ledger.copy()
    for column in [
        "monitor_ok",
        "event_auto_monitor_validated",
        "usable_for_history_selector",
        "event_signal_ready",
        "paper_or_whitelist_allowed",
        "combined_response_bytes",
    ]:
        frame[column] = _num(frame, column)

    expanded: list[dict[str, Any]] = []
    for _, row in frame.iterrows():
        products = [item.strip() for item in str(row["product_vt_symbol"]).split(",") if item.strip()]
        weight = 1.0 / len(products) if products else 1.0
        for product in products or [str(row["product_vt_symbol"])]:
            item = row.to_dict()
            item["product_vt_symbol"] = product
            item["_weight"] = weight
            expanded.append(item)
    expanded_frame = pd.DataFrame(expanded)

    for (family, product), group in expanded_frame.groupby(["product_family", "product_vt_symbol"], sort=False):
        rows.append(
            {
                "product_family": family,
                "product_vt_symbol": product,
                "monitor_rows": float(group["_weight"].sum()),
                "monitor_ok_rows": float((group["monitor_ok"] * group["_weight"]).sum()),
                "event_monitor_rows": float((group["event_auto_monitor_validated"] * group["_weight"]).sum()),
                "history_selector_rows": int(group["usable_for_history_selector"].sum()),
                "event_signal_ready_rows": int(group["event_signal_ready"].sum()),
                "paper_or_whitelist_rows": int(group["paper_or_whitelist_allowed"].sum()),
                "total_bytes": int(group["combined_response_bytes"].sum()),
                "raw_hash_rows": int(group["any_raw_hash_present"].sum()),
                "pit_received_dates": int(group["received_at_local"].nunique()),
                "monitor_status": "forward_monitor_ok"
                if (group["monitor_ok"] * group["_weight"]).sum() > 0
                else "monitor_failed",
                "missing_for_selector": "20_pit_dates,episodes,predictive_audit,live_tca,live_context",
            }
        )
    return pd.DataFrame(rows)


def build_route_status(ledger: pd.DataFrame) -> pd.DataFrame:
    active = ledger.copy()
    active["route_mode"] = "active_monitor"
    active["route_status"] = np.where(_num(active, "monitor_ok").eq(1), "ok", "failed")
    active_routes = active[
        [
            "product_family",
            "product_vt_symbol",
            "source_name",
            "source_url",
            "source_authority",
            "source_class",
            "route",
            "route_mode",
            "route_status",
            "http_status",
            "fetch_status",
        ]
    ].copy()
    blocked = pd.DataFrame(BLOCKED_ROUTE_TARGETS)
    if not blocked.empty:
        blocked["route_mode"] = "blocked_route_catalog"
        blocked["route_status"] = blocked["status"]
        blocked["http_status"] = 0
        blocked["fetch_status"] = blocked["status"]
        blocked = blocked[
            [
                "product_family",
                "product_vt_symbol",
                "source_name",
                "source_url",
                "source_authority",
                "source_class",
                "route",
                "route_mode",
                "route_status",
                "http_status",
                "fetch_status",
            ]
        ]
    return pd.concat([active_routes, blocked], ignore_index=True)


def build_gates(ledger: pd.DataFrame, product_status: pd.DataFrame) -> pd.DataFrame:
    active_products = int(product_status["product_vt_symbol"].nunique()) if not product_status.empty else 0
    ok_products = int((product_status["monitor_ok_rows"] > 0).sum()) if not product_status.empty else 0
    event_products = int((product_status["event_monitor_rows"] > 0).sum()) if not product_status.empty else 0
    selector_rows = int(_num(product_status, "history_selector_rows").sum() + _num(product_status, "event_signal_ready_rows").sum())
    whitelist_rows = int(_num(product_status, "paper_or_whitelist_rows").sum())
    min_pit_dates = int(_num(product_status, "pit_received_dates").min()) if not product_status.empty else 0
    failed_active_rows = int((ledger["monitor_ok"].astype(int) == 0).sum()) if not ledger.empty else 0
    rows = [
        {
            "gate": "active_products_covered",
            "passed": int(active_products >= REQUIRED_ACTIVE_PRODUCTS),
            "current": active_products,
            "required": REQUIRED_ACTIVE_PRODUCTS,
            "note": "ag/CY/SR should all have active monitor rows.",
        },
        {
            "gate": "active_monitor_ok_products",
            "passed": int(ok_products >= REQUIRED_ACTIVE_MONITOR_OK_PRODUCTS),
            "current": ok_products,
            "required": REQUIRED_ACTIVE_MONITOR_OK_PRODUCTS,
            "note": "each active P2 product needs at least one machine-readable row.",
        },
        {
            "gate": "event_monitor_ok_products",
            "passed": int(event_products >= REQUIRED_EVENT_MONITOR_PRODUCTS),
            "current": event_products,
            "required": REQUIRED_EVENT_MONITOR_PRODUCTS,
            "note": "CY/SR should have event-oriented monitor rows; ag still needs event source.",
        },
        {
            "gate": "failed_active_rows_zero",
            "passed": int(failed_active_rows == 0),
            "current": failed_active_rows,
            "required": 0,
            "note": "active monitor should separate known blocked routes from run failures.",
        },
        {
            "gate": "selector_rows_zero",
            "passed": int(selector_rows == 0),
            "current": selector_rows,
            "required": 0,
            "note": "monitor rows must not enter history selector.",
        },
        {
            "gate": "paper_whitelist_zero",
            "passed": int(whitelist_rows == 0),
            "current": whitelist_rows,
            "required": 0,
            "note": "no paper or trading whitelist from monitor rows.",
        },
        {
            "gate": "pit_dates_still_below_selector_threshold",
            "passed": int(min_pit_dates < REQUIRED_PIT_DATES_FOR_SELECTOR),
            "current": min_pit_dates,
            "required": f"<{REQUIRED_PIT_DATES_FOR_SELECTOR}",
            "note": "fail-closed discipline; one run is not enough for selector.",
        },
    ]
    return pd.DataFrame(rows)


def write_report(
    generated_at: datetime,
    ledger: pd.DataFrame,
    product_status: pd.DataFrame,
    route_status: pd.DataFrame,
    gates: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    lines = [
        "# Stage629 P2 Public Source Monitor Run",
        "",
        f"- line_id: `{LINE_ID}`",
        f"- generated_at: `{_fmt_cst(generated_at)}`",
        f"- decision: `{decision['decision']}`",
        "- stage nature: repeatable public source monitor run; no master selector, no strategy replay, no paper whitelist, no CTP/order path.",
        "",
        "## External Research And Judgement",
        "",
        "References:",
        *[f"- {item}" for item in REFERENCES],
        "",
        "Judgement:",
        "- A useful PIT monitor stores both successful and failed fetch evidence with received_at/source_url/final_url/raw_hash/status.",
        "- Known blocked CZCE static routes should remain in a blocked-route catalog instead of poisoning active monitor quality.",
        "- Monitor rows can accumulate evidence; they cannot become selector rows without 20 PIT dates, episodes, predictive audit and live TCA.",
        "",
        "## Key Results",
        "",
        f"- active rows: `{decision['active_rows']}`",
        f"- active monitor ok rows: `{decision['active_monitor_ok_rows']}`",
        f"- active products covered: `{decision['active_products_covered']}`",
        f"- event monitor products: `{decision['event_monitor_products']}`",
        f"- selector rows: `{decision['selector_rows']}`",
        f"- paper/whitelist rows: `{decision['paper_or_whitelist_rows']}`",
        f"- hard gates: `{decision['hard_gates_passed']}/{decision['hard_gates_total']}`",
        "",
        "## Product Status",
        "",
        _md_table(product_status, max_rows=20),
        "",
        "## Route Status",
        "",
        _md_table(route_status, max_rows=20),
        "",
        "## Gates",
        "",
        _md_table(gates, max_rows=20),
        "",
        "## Run Ledger Sample",
        "",
        _md_table(
            ledger,
            [
                "product_vt_symbol",
                "source_name",
                "http_status",
                "fetch_status",
                "combined_response_bytes",
                "any_raw_hash_present",
                "monitor_ok",
                "event_auto_monitor_validated",
                "discovered_txt_url",
            ],
            max_rows=12,
        ),
        "",
        "## Visual Review Checklist",
        "",
        "- Product bars should show ag/CY/SR coverage and whether event monitor exists.",
        "- Route matrix must separate active monitor rows from blocked CZCE catalog routes.",
        "- Gate panel must distinguish green lock-discipline gates from actual promotion readiness.",
        "- Hash/byte chart should expose silent low-byte or missing-hash failures.",
        "",
        "## Output Files",
        "",
        f"- run ledger: `{RUN_LEDGER_PATH}`",
        f"- product status: `{PRODUCT_STATUS_PATH}`",
        f"- route status: `{ROUTE_STATUS_PATH}`",
        f"- gates: `{GATES_PATH}`",
        f"- decision: `{DECISION_PATH}`",
        f"- chart: `{CHART_PATH}`",
        "",
    ]
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def plot_chart(ledger: pd.DataFrame, product_status: pd.DataFrame, route_status: pd.DataFrame, gates: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(18, 12), constrained_layout=True)
    fig.suptitle("Stage629 P2 public source monitor run: PIT evidence accumulates, selector locked", fontsize=16)

    ax = axes[0, 0]
    products = product_status["product_vt_symbol"].astype(str).tolist()
    x = np.arange(len(products))
    width = 0.22
    ax.bar(x - width, product_status["monitor_ok_rows"], width, label="monitor ok", color="#54a24b")
    ax.bar(x, product_status["event_monitor_rows"], width, label="event monitor", color="#4c78a8")
    ax.bar(x + width, product_status["pit_received_dates"], width, label="PIT dates", color="#f58518")
    ax.set_xticks(x)
    ax.set_xticklabels(products)
    ax.set_title("Product monitor coverage from this run")
    ax.set_ylabel("weighted rows / dates")
    ax.legend(loc="upper left")

    ax = axes[0, 1]
    route_counts = (
        route_status.groupby(["route_mode", "route_status"], sort=False)
        .size()
        .reset_index(name="rows")
    )
    labels = route_counts["route_mode"] + "\n" + route_counts["route_status"]
    colors = ["#54a24b" if "ok" in status else "#e45756" for status in route_counts["route_status"]]
    ax.bar(labels, route_counts["rows"], color=colors)
    for idx, row in route_counts.reset_index(drop=True).iterrows():
        ax.text(idx, row["rows"] + 0.05, str(int(row["rows"])), ha="center", va="bottom", fontsize=9)
    ax.tick_params(axis="x", rotation=20)
    ax.set_title("Route mode/status: active monitors vs blocked catalog")
    ax.set_ylabel("rows")

    ax = axes[1, 0]
    plot_frame = ledger.copy()
    plot_frame["short_source"] = plot_frame["source_name"].str.replace("ESMIS ", "", regex=False).str.replace("USDA ", "", regex=False)
    ax.barh(plot_frame["short_source"], plot_frame["combined_response_bytes"], color=np.where(plot_frame["monitor_ok"].astype(int).eq(1), "#54a24b", "#e45756"))
    for idx, row in plot_frame.reset_index(drop=True).iterrows():
        hash_label = "hash" if int(row["any_raw_hash_present"]) else "nohash"
        ax.text(row["combined_response_bytes"] + 1000, idx, hash_label, va="center", fontsize=8)
    ax.set_title("Bytes and hash presence by active source")
    ax.set_xlabel("combined response bytes")

    ax = axes[1, 1]
    gate_colors = ["#54a24b" if bool(row["passed"]) else "#e45756" for _, row in gates.iterrows()]
    ax.barh(gates["gate"], [1] * len(gates), color=gate_colors)
    for idx, row in gates.reset_index(drop=True).iterrows():
        ax.text(0.02, idx, str(row["current"]), va="center", ha="left", color="white", fontsize=9, fontweight="bold")
    ax.set_xlim(0, 1)
    ax.set_xticks([])
    ax.set_title("Monitor gates: green includes fail-closed locks")

    CHART_PATH.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(CHART_PATH, dpi=160)
    plt.close(fig)


def main() -> None:
    generated_at = _now_cst()
    ledger = build_run_ledger(generated_at)
    product_status = build_product_status(ledger)
    route_status = build_route_status(ledger)
    gates = build_gates(ledger, product_status)

    active_monitor_ok_rows = int(_num(ledger, "monitor_ok").sum())
    active_products_covered = int(product_status["product_vt_symbol"].nunique()) if not product_status.empty else 0
    event_monitor_products = int((_num(product_status, "event_monitor_rows") > 0).sum()) if not product_status.empty else 0
    selector_rows = int(_num(product_status, "history_selector_rows").sum() + _num(product_status, "event_signal_ready_rows").sum())
    whitelist_rows = int(_num(product_status, "paper_or_whitelist_rows").sum())
    hard_gates_passed = int(_num(gates, "passed").sum())
    hard_gates_total = int(len(gates))
    decision = {
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at_cst": _fmt_cst(generated_at),
        "decision": "p2_public_source_monitor_run_collected_selector_locked",
        "promotion_allowed": False,
        "paper_selector_allowed": False,
        "trading_whitelist_allowed": False,
        "active_rows": int(len(ledger)),
        "active_monitor_ok_rows": active_monitor_ok_rows,
        "active_products_covered": active_products_covered,
        "event_monitor_products": event_monitor_products,
        "selector_rows": selector_rows,
        "paper_or_whitelist_rows": whitelist_rows,
        "hard_gates_passed": hard_gates_passed,
        "hard_gates_total": hard_gates_total,
        "summary": (
            "P2 public source monitor run collected active raw-hash evidence for ag/CY/SR while keeping CZCE blocked routes separate; "
            "selector, paper and trading whitelist remain locked."
        ),
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ledger.to_csv(RUN_LEDGER_PATH, index=False, encoding="utf-8-sig")
    product_status.to_csv(PRODUCT_STATUS_PATH, index=False, encoding="utf-8-sig")
    route_status.to_csv(ROUTE_STATUS_PATH, index=False, encoding="utf-8-sig")
    gates.to_csv(GATES_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    write_report(generated_at, ledger, product_status, route_status, gates, decision)
    plot_chart(ledger, product_status, route_status, gates)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
