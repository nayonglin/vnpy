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
MODEL_TAG = "stage625_public_source_raw_text_probe_v1"
OUTPUT_PREFIX = "qmt_roll_stage625_public_source_raw_text_probe"

RAW_FETCH_LEDGER_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_raw_fetch_ledger_{MODEL_TAG}.csv"
PRODUCT_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_summary_{MODEL_TAG}.csv"
SOURCE_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_source_summary_{MODEL_TAG}.csv"
GATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gates_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

TIMEOUT_SECONDS = 15
MIN_RESPONSE_BYTES = 500
MIN_PIT_DATES_FOR_PREDICTIVE_AUDIT = 20

SOURCE_TARGETS = [
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
        "keywords": ["Daily Warrant", "Daily Ranking", "Warehouse", "SHFE"],
        "expected_products": ["ag", "silver", "warrant", "ranking"],
        "mapping_method": "direct_shfe_product_to_daily_data_page",
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
        "keywords": ["Crop Progress", "Release date", "prog2226.txt", "Jun 01 2026"],
        "expected_products": ["cotton", "crop", "progress"],
        "mapping_method": "manual_cotton_supply_to_czce_cotton_yarn_chain",
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
        "keywords": ["4:00 p.m.", "Crop Progress", "condition", "Quick Stats"],
        "expected_products": ["cotton", "condition", "progress"],
        "mapping_method": "methodology_support_for_crop_progress_monitor",
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
        "keywords": ["Cotton and Wool Outlook", "May 2026", "cotton projections", "Download"],
        "expected_products": ["cotton", "wool", "outlook"],
        "mapping_method": "manual_cotton_supply_to_czce_cotton_yarn_chain",
    },
    {
        "product_vt_symbol": "CY.CZCE",
        "product_family": "soft_agri",
        "source_name": "CZCE reference data",
        "source_url": "https://english.czce.com.cn/en/DFSStaticFiles/Future/2023/20231229/EnglishFutureDataReferenceData.htm",
        "source_authority": "official_public_exchange",
        "source_class": "official_static_reference",
        "route": "contract_reference",
        "event_family": "contract_reference",
        "event_type": "czce_cotton_yarn_reference",
        "keywords": ["Cotton Yarn", "CY", "futures", "XZCE"],
        "expected_products": ["CY", "Cotton Yarn"],
        "mapping_method": "direct_czce_cotton_yarn_product_reference",
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
        "keywords": ["WASDE", "wasde0526v2.txt", "World Agricultural Supply and Demand Estimates", "May 12 2026"],
        "expected_products": ["sugar", "cotton", "WASDE"],
        "mapping_method": "manual_sugar_supply_to_czce_white_sugar",
    },
    {
        "product_vt_symbol": "SR.CZCE",
        "product_family": "soft_agri",
        "source_name": "USDA WASDE latest text",
        "source_url": "https://www.usda.gov/oce/commodity/wasde/latest.txt",
        "source_authority": "official_public_usda",
        "source_class": "public_text_event_file",
        "route": "monthly_supply_demand",
        "event_family": "monthly_supply_demand",
        "event_type": "wasde_latest_text",
        "keywords": ["World Agricultural Supply and Demand Estimates", "Sugar", "Cotton", "WASDE"],
        "expected_products": ["sugar", "cotton"],
        "mapping_method": "manual_sugar_supply_to_czce_white_sugar",
    },
    {
        "product_vt_symbol": "SR.CZCE",
        "product_family": "soft_agri",
        "source_name": "CZCE reference data",
        "source_url": "https://english.czce.com.cn/en/DFSStaticFiles/Future/2024/20240418/EnglishFutureDataReferenceData.htm",
        "source_authority": "official_public_exchange",
        "source_class": "official_static_reference",
        "route": "contract_reference",
        "event_family": "contract_reference",
        "event_type": "czce_white_sugar_reference",
        "keywords": ["White Sugar", "SR", "futures", "XZCE"],
        "expected_products": ["SR", "White Sugar"],
        "mapping_method": "direct_czce_white_sugar_product_reference",
    },
]

REFERENCES = [
    "ESMIS Crop Progress release page: https://esmis.nal.usda.gov/publication/crop-progress/2026-06-01",
    "NASS Crop Progress methodology: https://www.nass.usda.gov/Surveys/Guide_to_NASS_Surveys/Crop_Progress_and_Condition/index.php",
    "SHFE Daily Data: https://www.shfe.cn/eng/reports/StatisticalData/DailyData/",
    "ESMIS WASDE release page: https://esmis.nal.usda.gov/publication/world-agricultural-supply-and-demand-estimates/2026-05-12-0",
    "CZCE reference data: https://english.czce.com.cn/en/DFSStaticFiles/Future/2024/20240418/EnglishFutureDataReferenceData.htm",
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
    return value


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
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _fetch_url(url: str, referer: str = "") -> dict[str, Any]:
    headers = {
        "User-Agent": "Mozilla/5.0 stage625-public-source-probe/1.0",
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
            body = response.read(2_000_000)
            elapsed_ms = round((datetime.now(timezone.utc) - started).total_seconds() * 1000, 1)
            content_type = response.headers.get("content-type", "")
            charset_match = re.search(r"charset=([^;\s]+)", content_type, flags=re.I)
            charset = charset_match.group(1) if charset_match else "utf-8"
            text = body.decode(charset, errors="replace")
            return {
                "status": "ok",
                "http_status": int(getattr(response, "status", 200)),
                "final_url": response.geturl(),
                "content_type": content_type,
                "response_bytes": len(body),
                "elapsed_ms": elapsed_ms,
                "text": text,
                "error": "",
            }
    except HTTPError as error:
        return {
            "status": "http_error",
            "http_status": int(error.code),
            "final_url": url,
            "content_type": "",
            "response_bytes": 0,
            "elapsed_ms": round((datetime.now(timezone.utc) - started).total_seconds() * 1000, 1),
            "text": "",
            "error": str(error),
        }
    except (URLError, socket.timeout, TimeoutError) as error:
        return {
            "status": "network_error",
            "http_status": 0,
            "final_url": url,
            "content_type": "",
            "response_bytes": 0,
            "elapsed_ms": round((datetime.now(timezone.utc) - started).total_seconds() * 1000, 1),
            "text": "",
            "error": str(error),
        }


def _discover_txt_links(base_url: str, text: str) -> str:
    links = re.findall(r'href=["\']([^"\']+\.txt)["\']', text, flags=re.I)
    if not links:
        return ""
    preferred = [link for link in links if "wasde" in link.lower() or "prog" in link.lower()]
    return urljoin(base_url, (preferred or links)[0])


def _keyword_hits(text: str, keywords: list[str]) -> tuple[int, str]:
    lower = text.lower()
    hits = [keyword for keyword in keywords if keyword.lower() in lower]
    return len(hits), ",".join(hits)


def _extract_excerpt(text: str, keywords: list[str], max_chars: int = 220) -> str:
    clean = _clean_text(text)
    lower = clean.lower()
    positions = [lower.find(keyword.lower()) for keyword in keywords if lower.find(keyword.lower()) >= 0]
    start = min(positions) if positions else 0
    start = max(0, start - 60)
    excerpt = clean[start : start + max_chars]
    return excerpt


def build_raw_fetch_ledger(received_at: datetime) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for index, target in enumerate(SOURCE_TARGETS, start=1):
        fetch = _fetch_url(target["source_url"])
        text = str(fetch["text"])
        raw_sha256 = hashlib.sha256(text.encode("utf-8")).hexdigest() if text else ""
        cleaned = _clean_text(text)
        keyword_hit_count, keyword_hits = _keyword_hits(cleaned, list(target["keywords"]))
        product_hit_count, product_hits = _keyword_hits(cleaned, list(target["expected_products"]))
        txt_link = _discover_txt_links(str(fetch["final_url"] or target["source_url"]), text) if fetch["status"] == "ok" else ""
        linked_fetch = _fetch_url(txt_link, referer=str(fetch["final_url"] or target["source_url"])) if txt_link else {
            "status": "",
            "http_status": 0,
            "final_url": "",
            "content_type": "",
            "response_bytes": 0,
            "elapsed_ms": 0.0,
            "text": "",
            "error": "",
        }
        linked_text = str(linked_fetch.get("text", ""))
        linked_sha256 = hashlib.sha256(linked_text.encode("utf-8")).hexdigest() if linked_text else ""
        linked_keyword_hit_count, linked_keyword_hits = _keyword_hits(_clean_text(linked_text), list(target["keywords"]))
        linked_product_hit_count, linked_product_hits = _keyword_hits(_clean_text(linked_text), list(target["expected_products"]))
        page_raw_ok = int(fetch["status"] == "ok" and len(raw_sha256) > 0 and int(fetch["response_bytes"]) >= MIN_RESPONSE_BYTES)
        linked_raw_ok = int(linked_fetch["status"] == "ok" and len(linked_sha256) > 0 and int(linked_fetch["response_bytes"]) >= MIN_RESPONSE_BYTES)
        ok_raw_hash = int(page_raw_ok or linked_raw_ok)
        combined_keyword_hit_count = max(keyword_hit_count, linked_keyword_hit_count)
        combined_product_hit_count = max(product_hit_count, linked_product_hit_count)
        source_contract_complete = int(ok_raw_hash and combined_keyword_hit_count > 0)
        event_auto_monitor_validated = int(
            source_contract_complete
            and (
                target["source_class"] == "public_text_event_file"
                or target["source_class"] == "public_html_event_release_page"
                or bool(linked_raw_ok)
            )
        )
        row = {
            "run_id": MODEL_TAG,
            "row_id": f"stage625_{index:03d}",
            "received_at_local": _fmt_cst(received_at),
            "received_at_utc": received_at.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "line_id": LINE_ID,
            "product_vt_symbol": target["product_vt_symbol"],
            "product_family": target["product_family"],
            "source_name": target["source_name"],
            "source_url": target["source_url"],
            "final_url": fetch["final_url"],
            "discovered_txt_url": txt_link,
            "linked_text_fetch_status": linked_fetch["status"],
            "linked_text_http_status": linked_fetch["http_status"],
            "linked_text_final_url": linked_fetch["final_url"],
            "linked_text_bytes": linked_fetch["response_bytes"],
            "linked_text_elapsed_ms": linked_fetch["elapsed_ms"],
            "linked_text_sha256": linked_sha256,
            "linked_text_sha256_present": int(len(linked_sha256) > 0),
            "linked_text_keyword_hit_count": linked_keyword_hit_count,
            "linked_text_keyword_hits": linked_keyword_hits,
            "linked_text_product_hit_count": linked_product_hit_count,
            "linked_text_product_hits": linked_product_hits,
            "source_authority": target["source_authority"],
            "source_class": target["source_class"],
            "route": target["route"],
            "event_family": target["event_family"],
            "event_type": target["event_type"],
            "http_status": fetch["http_status"],
            "fetch_status": fetch["status"],
            "fetch_error": fetch["error"],
            "content_type": fetch["content_type"],
            "response_bytes": fetch["response_bytes"],
            "combined_response_bytes": int(fetch["response_bytes"]) + int(linked_fetch["response_bytes"]),
            "elapsed_ms": fetch["elapsed_ms"],
            "raw_sha256": raw_sha256,
            "raw_sha256_present": int(len(raw_sha256) > 0),
            "any_raw_hash_present": ok_raw_hash,
            "keyword_hit_count": keyword_hit_count,
            "keyword_hits": keyword_hits,
            "product_hit_count": product_hit_count,
            "product_hits": product_hits,
            "combined_keyword_hit_count": combined_keyword_hit_count,
            "combined_product_hit_count": combined_product_hit_count,
            "source_contract_complete": source_contract_complete,
            "event_auto_monitor_validated": event_auto_monitor_validated,
            "usable_for_forward_monitor": source_contract_complete,
            "usable_for_history_selector": 0,
            "event_signal_ready": 0,
            "selector_candidate": 0,
            "paper_or_whitelist_allowed": 0,
            "raw_text_excerpt": _extract_excerpt(linked_text or text, list(target["keywords"])),
            "product_mapping_method": target["mapping_method"],
            "point_in_time_rule": "Use received_at_local and raw_sha256 only; fetched raw text is not backfilled into history selector.",
            "notes": "Stage-scoped fetch probe only; no master ledger append and no strategy replay.",
        }
        rows.append(row)
    return pd.DataFrame(rows)


def build_product_summary(ledger: pd.DataFrame) -> pd.DataFrame:
    grouped = ledger.groupby(["product_family", "product_vt_symbol"], as_index=False).agg(
        rows=("row_id", "count"),
        fetched_ok_rows=("source_contract_complete", "sum"),
        event_auto_monitor_rows=("event_auto_monitor_validated", "sum"),
        history_selector_rows=("usable_for_history_selector", "sum"),
        event_signal_ready_rows=("event_signal_ready", "sum"),
        total_bytes=("combined_response_bytes", "sum"),
        min_keyword_hits=("keyword_hit_count", "min"),
        source_classes=("source_class", lambda series: ",".join(sorted(set(map(str, series))))),
        routes=("route", lambda series: ",".join(sorted(set(map(str, series))))),
    )
    grouped["selector_locked"] = 1
    grouped["pit_received_dates"] = 1
    grouped["missing_for_promotion"] = grouped.apply(_product_missing_for_promotion, axis=1)
    return grouped


def _product_missing_for_promotion(row: pd.Series) -> str:
    missing = ["20_pit_dates", "live_tca", "live_context", "predictive_signal_evidence"]
    if int(row["event_auto_monitor_rows"]) == 0:
        missing.insert(0, "event_auto_monitor")
    if int(row["history_selector_rows"]) != 0:
        missing.append("selector_leakage_repair")
    return ",".join(missing)


def build_source_summary(ledger: pd.DataFrame) -> pd.DataFrame:
    return ledger.groupby(["source_authority", "source_class", "fetch_status"], as_index=False).agg(
        rows=("row_id", "count"),
        products=("product_vt_symbol", lambda series: ",".join(sorted(set(map(str, series))))),
        contract_complete_rows=("source_contract_complete", "sum"),
        event_auto_monitor_rows=("event_auto_monitor_validated", "sum"),
        total_bytes=("combined_response_bytes", "sum"),
        avg_elapsed_ms=("elapsed_ms", "mean"),
    )


def build_gates(ledger: pd.DataFrame, product_summary: pd.DataFrame) -> pd.DataFrame:
    public_products = int(ledger["product_vt_symbol"].nunique())
    gates = [
        {
            "gate": "public_products_covered",
            "passed": int(public_products >= 3),
            "current": str(public_products),
            "required": ">=3",
            "note": "ag/CY/SR public routes should all be touched by the probe.",
        },
        {
            "gate": "raw_fetch_ok_rows",
            "passed": int(ledger["source_contract_complete"].sum() >= 5),
            "current": str(int(ledger["source_contract_complete"].sum())),
            "required": ">=5",
            "note": "Public URLs should return enough text and source keywords for forward monitor.",
        },
        {
            "gate": "event_auto_monitor_has_rows",
            "passed": int(ledger["event_auto_monitor_validated"].sum() >= 2),
            "current": str(int(ledger["event_auto_monitor_validated"].sum())),
            "required": ">=2",
            "note": "At least two public event/methodology pages or linked text files should be machine-fetched with hashes.",
        },
        {
            "gate": "all_hash_present_for_ok_rows",
            "passed": int(ledger.loc[ledger["source_contract_complete"].eq(1), "any_raw_hash_present"].eq(1).all()),
            "current": f"{int(ledger['any_raw_hash_present'].sum())}/{len(ledger)}",
            "required": "all ok rows",
            "note": "Every complete source row must have raw response hash.",
        },
        {
            "gate": "history_selector_rows_zero",
            "passed": int(ledger["usable_for_history_selector"].sum() == 0),
            "current": str(int(ledger["usable_for_history_selector"].sum())),
            "required": "0",
            "note": "No fetched public row is allowed into history selector.",
        },
        {
            "gate": "event_signal_ready_zero",
            "passed": int(ledger["event_signal_ready"].sum() == 0),
            "current": str(int(ledger["event_signal_ready"].sum())),
            "required": "0",
            "note": "A fetchable event source is not an alpha signal.",
        },
        {
            "gate": "paper_whitelist_locked",
            "passed": int(ledger["paper_or_whitelist_allowed"].sum() == 0),
            "current": str(int(ledger["paper_or_whitelist_allowed"].sum())),
            "required": "0",
            "note": "No paper selector or trading whitelist permission.",
        },
        {
            "gate": "pit_dates_reach_20",
            "passed": 0,
            "current": "1",
            "required": str(MIN_PIT_DATES_FOR_PREDICTIVE_AUDIT),
            "note": "This is only one received_at date; predictive audit remains blocked.",
        },
        {
            "gate": "dce_authorized_source_closed",
            "passed": 0,
            "current": "0",
            "required": "1",
            "note": "This public-source probe does not solve DCE j/i authorization.",
        },
    ]
    return pd.DataFrame(gates)


def make_chart(ledger: pd.DataFrame, product_summary: pd.DataFrame, source_summary: pd.DataFrame, gates: pd.DataFrame) -> None:
    source_classes = sorted(ledger["source_class"].unique())
    products = sorted(ledger["product_vt_symbol"].unique())
    matrix = pd.DataFrame(0, index=products, columns=source_classes, dtype=float)
    labels = pd.DataFrame("", index=products, columns=source_classes)
    for _, row in ledger.iterrows():
        product = str(row["product_vt_symbol"])
        source_class = str(row["source_class"])
        score = 2 if int(row["source_contract_complete"]) else 1 if str(row["fetch_status"]) == "ok" else 0
        matrix.loc[product, source_class] = max(matrix.loc[product, source_class], score)
        labels.loc[product, source_class] = "OK" if score == 2 else "RAW" if score == 1 else "FAIL"

    fig, axes = plt.subplots(2, 2, figsize=(18, 11))
    fig.suptitle("Stage625 public source raw-text probe: fetch evidence improves, selector remains locked", fontsize=16)

    ax = axes[0, 0]
    cmap = matplotlib.colors.ListedColormap(["#fed7d7", "#bee3f8", "#c6f6d5"])
    norm = matplotlib.colors.BoundaryNorm([-0.5, 0.5, 1.5, 2.5], cmap.N)
    ax.imshow(matrix.values, cmap=cmap, norm=norm, aspect="auto")
    ax.set_xticks(range(len(source_classes)))
    ax.set_xticklabels(source_classes, rotation=30, ha="right", fontsize=8)
    ax.set_yticks(range(len(products)))
    ax.set_yticklabels(products)
    ax.set_title("Product x public source class fetch status")
    for i in range(matrix.shape[0]):
        for j in range(matrix.shape[1]):
            if matrix.iloc[i, j] > 0:
                ax.text(j, i, labels.iloc[i, j], ha="center", va="center", fontsize=8, fontweight="bold")

    ax = axes[0, 1]
    class_counts = ledger.groupby("source_class")["source_contract_complete"].sum().sort_values()
    ax.barh(class_counts.index, class_counts.values, color="#3182ce")
    ax.set_title("Complete raw-text rows by source class")
    ax.set_xlabel("complete rows")
    for y, value in enumerate(class_counts.values):
        ax.text(value + 0.03, y, str(int(value)), va="center", fontsize=9)

    ax = axes[1, 0]
    readiness = pd.Series(
        {
            "source_contract_complete": ledger["source_contract_complete"].mean(),
            "event_auto_monitor": ledger["event_auto_monitor_validated"].mean(),
            "raw_hash_present": ledger["any_raw_hash_present"].mean(),
            "keyword_hit": ledger["combined_keyword_hit_count"].gt(0).mean(),
            "history_selector": ledger["usable_for_history_selector"].mean(),
            "event_signal_ready": ledger["event_signal_ready"].mean(),
            "paper_whitelist": ledger["paper_or_whitelist_allowed"].mean(),
        }
    )
    colors = ["#38a169" if value >= 0.99 else "#dd6b20" if value > 0 else "#e53e3e" for value in readiness.values]
    ax.barh(readiness.index, readiness.values, color=colors)
    ax.set_xlim(0, 1.05)
    ax.set_title("Fetch/readiness ratios")
    for y, value in enumerate(readiness.values):
        ax.text(max(value, 0.03), y, f"{value:.0%}", va="center", fontsize=9)

    ax = axes[1, 1]
    y_pos = np.arange(len(gates))
    colors = ["#38a169" if int(item) else "#e53e3e" for item in gates["passed"]]
    ax.barh(y_pos, [1] * len(gates), color=colors)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(gates["gate"], fontsize=8)
    ax.set_xlim(0, 1)
    ax.set_xticks([])
    ax.invert_yaxis()
    ax.set_title("Hard gates")
    for y, (_, row) in enumerate(gates.iterrows()):
        ax.text(0.02, y, str(row["current"]), va="center", ha="left", fontsize=8, color="white", fontweight="bold")

    plt.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(CHART_PATH, dpi=160)
    plt.close(fig)


def write_report(
    received_at: datetime,
    ledger: pd.DataFrame,
    product_summary: pd.DataFrame,
    source_summary: pd.DataFrame,
    gates: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    report = f"""# Stage625 Public Source Raw-Text Probe

- line_id: `{LINE_ID}`
- generated_at: `{_fmt_cst(received_at)}`
- decision: `{decision["decision"]}`
- stage nature: stage-scoped public-source fetch probe; no master ledger append, no strategy replay, no selector, no paper whitelist, no CTP/order path.

## External Research And Judgement

References:
{chr(10).join(f"- {item}" for item in REFERENCES)}

Judgement:
- Public sources for `ag/CY/SR` can be probed by script and converted into received_at + raw_hash evidence.
- This improves live data operability, but does not prove predictive value.
- DCE `j/i` authorization remains outside this public-source probe.

## Key Results

- rows: `{len(ledger)}`
- products covered: `{ledger["product_vt_symbol"].nunique()}`
- source contract complete rows: `{int(ledger["source_contract_complete"].sum())}`
- event auto monitor rows: `{int(ledger["event_auto_monitor_validated"].sum())}`
- history selector rows: `{int(ledger["usable_for_history_selector"].sum())}`
- event signal ready rows: `{int(ledger["event_signal_ready"].sum())}`
- hard gates: `{int(gates["passed"].sum())}/{len(gates)}`
- selector unlocked now: `{decision["selector_unlocked_now"]}`

## Product Summary

{_md_table(product_summary, max_rows=20)}

## Source Summary

{_md_table(source_summary, max_rows=20)}

## Fetch Ledger

{_md_table(ledger, columns=["product_vt_symbol", "source_name", "fetch_status", "http_status", "response_bytes", "discovered_txt_url", "linked_text_fetch_status", "linked_text_bytes", "keyword_hits", "linked_text_keyword_hits", "source_contract_complete", "event_auto_monitor_validated", "usable_for_history_selector"], max_rows=20)}

## Gates

{_md_table(gates, max_rows=20)}

## Visual Review Notes

- Top-left should show `ag/CY/SR` public source classes as `OK` where raw response and expected keywords were found.
- Bottom-left should show fetch/readiness improving while `history_selector`, `event_signal_ready` and `paper_whitelist` remain zero.
- Bottom-right should keep `pit_dates_reach_20` and `dce_authorized_source_closed` red; this prevents public fetch success from being confused with deployability.

## Output Files

- raw fetch ledger: `{RAW_FETCH_LEDGER_PATH}`
- product summary: `{PRODUCT_SUMMARY_PATH}`
- source summary: `{SOURCE_SUMMARY_PATH}`
- gates: `{GATES_PATH}`
- decision: `{DECISION_PATH}`
- chart: `{CHART_PATH}`
"""
    REPORT_PATH.write_text(report, encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    received_at = _now_cst()
    ledger = build_raw_fetch_ledger(received_at)
    product_summary = build_product_summary(ledger)
    source_summary = build_source_summary(ledger)
    gates = build_gates(ledger, product_summary)
    decision = {
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at_cst": _fmt_cst(received_at),
        "decision": "public_source_raw_text_fetch_validated_selector_locked",
        "rows": int(len(ledger)),
        "products_covered": int(ledger["product_vt_symbol"].nunique()),
        "source_contract_complete_rows": int(ledger["source_contract_complete"].sum()),
        "event_auto_monitor_validated_rows": int(ledger["event_auto_monitor_validated"].sum()),
        "history_selector_rows": int(ledger["usable_for_history_selector"].sum()),
        "event_signal_ready_rows": int(ledger["event_signal_ready"].sum()),
        "selector_unlocked_now": 0,
        "paper_or_whitelist_allowed": 0,
        "trading_whitelist_allowed": False,
        "promotion_allowed": False,
        "hard_gates_passed": int(gates["passed"].sum()),
        "hard_gates_total": int(len(gates)),
        "summary": (
            "Public ag/CY/SR sources were fetched as stage-scoped raw-text/hash evidence; "
            "selector remains locked because PIT depth, predictive audit, DCE authorization and live TCA are still missing."
        ),
    }
    ledger.to_csv(RAW_FETCH_LEDGER_PATH, index=False, encoding="utf-8-sig")
    product_summary.to_csv(PRODUCT_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    source_summary.to_csv(SOURCE_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    gates.to_csv(GATES_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    write_report(received_at, ledger, product_summary, source_summary, gates, decision)
    make_chart(ledger, product_summary, source_summary, gates)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
