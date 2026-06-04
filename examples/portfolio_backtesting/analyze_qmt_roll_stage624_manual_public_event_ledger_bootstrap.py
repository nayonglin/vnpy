from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
os.environ.setdefault("MPLCONFIGDIR", str(OUTPUT_DIR / ".matplotlib"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


LINE_ID = "futures_trend_drawdown30_preserve_return"
MODEL_TAG = "stage624_manual_public_event_ledger_bootstrap_v1"
OUTPUT_PREFIX = "qmt_roll_stage624_manual_public_event_ledger_bootstrap"

LEDGER_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_event_ledger_{MODEL_TAG}.csv"
PRODUCT_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_summary_{MODEL_TAG}.csv"
SOURCE_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_source_summary_{MODEL_TAG}.csv"
GATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gates_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

MONITOR_PRODUCTS = ["j.DCE", "i.DCE", "ag.SHFE", "CY.CZCE", "SR.CZCE"]
MIN_PIT_DATES_FOR_PREDICTIVE_AUDIT = 20

PRODUCT_FAMILY = {
    "j.DCE": "black_ferrous",
    "i.DCE": "black_ferrous",
    "ag.SHFE": "precious_metals",
    "CY.CZCE": "soft_agri",
    "SR.CZCE": "soft_agri",
}

PRODUCT_CODE = {
    "j.DCE": "j",
    "i.DCE": "i",
    "ag.SHFE": "ag",
    "CY.CZCE": "CY",
    "SR.CZCE": "SR",
}

EXCHANGE = {
    "j.DCE": "DCE",
    "i.DCE": "DCE",
    "ag.SHFE": "SHFE",
    "CY.CZCE": "CZCE",
    "SR.CZCE": "CZCE",
}

REFERENCES = [
    "DCE API SDK / credentials required: https://pypi.org/project/dceapi/",
    "DCE API Rust docs / news delivery member market services: https://docs.rs/dceapi-rs/latest/dceapi_rs/",
    "ICE DCE licensed data catalog: https://developer.ice.com/fixed-income-data-services/catalog/dalian-commodity-exchange-dce",
    "SHFE Daily Data / ranking and warrant reports: https://www.shfe.cn/eng/reports/StatisticalData/DailyData/",
    "USDA NASS National Crop Progress: https://data.nass.usda.gov/Publications/National_Crop_Progress/index.php",
    "USDA WASDE release page: https://www.usda.gov/about-usda/general-information/staff-offices/office-chief-economist/commodity-markets/wasde-report",
    "USDA ERS Cotton and Wool Outlook page: https://ers.usda.gov/publications/pub-details?pubid=114047",
    "CZCE English overview: https://english.czce.com.cn/en/AboutUs/Overview/Overview/H081001001003index_1.htm",
    "CZCE static reference data example: https://english.czce.com.cn/en/DFSStaticFiles/Future/2024/20240418/EnglishFutureDataReferenceData.htm",
]

SOURCE_BLUEPRINTS = [
    {
        "product_vt_symbol": "j.DCE",
        "source_name": "DCE API SDK / News, Delivery, Member services",
        "source_url": "https://pypi.org/project/dceapi/",
        "source_class": "authorized_dce_api_catalog",
        "source_authority": "authorized_exchange_api_candidate",
        "published_at": "2026-01-20T00:00:00+00:00",
        "published_at_confidence": "sdk_release_date",
        "headline": "DCE authorized API route for notices, delivery and member ranking",
        "summary": "Catalog row only: DCE j needs authorized API credentials before any automatic event or delivery monitor can be treated as live evidence.",
        "raw_text_excerpt": "DCE API catalog supports news, market, delivery and member services, but use requires DCE_API_KEY and DCE_SECRET.",
        "event_family": "exchange_notice_delivery_margin",
        "event_type": "authorized_api_catalog",
        "direction_hint": "none_source_only",
        "status": "authorization_required_source_catalog",
        "source_access_state": "authorization_required",
        "requires_credentials": 1,
        "credentials_present": 0,
        "manual_capture_required": 0,
        "usable_for_forward_monitor": 0,
        "usable_for_history_selector": 0,
        "notes": "Cannot become selector evidence until credentials and read-only endpoint probe are validated.",
    },
    {
        "product_vt_symbol": "i.DCE",
        "source_name": "DCE API SDK / News, Delivery, Member services",
        "source_url": "https://pypi.org/project/dceapi/",
        "source_class": "authorized_dce_api_catalog",
        "source_authority": "authorized_exchange_api_candidate",
        "published_at": "2026-01-20T00:00:00+00:00",
        "published_at_confidence": "sdk_release_date",
        "headline": "DCE authorized API route for iron ore notices and delivery context",
        "summary": "Catalog row only: DCE i needs authorized API credentials before member or warehouse event evidence can be used.",
        "raw_text_excerpt": "DCE API catalog supports articles, delivery data, warehouse receipts and member rankings; credentials are required.",
        "event_family": "exchange_notice_delivery_margin",
        "event_type": "authorized_api_catalog",
        "direction_hint": "none_source_only",
        "status": "authorization_required_source_catalog",
        "source_access_state": "authorization_required",
        "requires_credentials": 1,
        "credentials_present": 0,
        "manual_capture_required": 0,
        "usable_for_forward_monitor": 0,
        "usable_for_history_selector": 0,
        "notes": "This keeps black_ferrous as P1 worklist, not a tradeable selector.",
    },
    {
        "product_vt_symbol": "j.DCE",
        "source_name": "ICE DCE licensed market data catalog",
        "source_url": "https://developer.ice.com/fixed-income-data-services/catalog/dalian-commodity-exchange-dce",
        "source_class": "licensed_vendor_candidate",
        "source_authority": "licensed_vendor_candidate",
        "published_at": "",
        "published_at_confidence": "unknown",
        "headline": "Licensed DCE market data route with depth and history",
        "summary": "Vendor catalog row only: useful as a possible normalized market data route, not current internal evidence.",
        "raw_text_excerpt": "ICE catalog describes DCE market data availability via consolidated feed and historical products.",
        "event_family": "licensed_market_data",
        "event_type": "vendor_market_data_catalog",
        "direction_hint": "none_source_only",
        "status": "licensed_vendor_required",
        "source_access_state": "licensed_vendor_required",
        "requires_credentials": 1,
        "credentials_present": 0,
        "manual_capture_required": 0,
        "usable_for_forward_monitor": 0,
        "usable_for_history_selector": 0,
        "notes": "Vendor contract route only; no selector or paper permission.",
    },
    {
        "product_vt_symbol": "i.DCE",
        "source_name": "ICE DCE licensed market data catalog",
        "source_url": "https://developer.ice.com/fixed-income-data-services/catalog/dalian-commodity-exchange-dce",
        "source_class": "licensed_vendor_candidate",
        "source_authority": "licensed_vendor_candidate",
        "published_at": "",
        "published_at_confidence": "unknown",
        "headline": "Licensed DCE market data route for iron ore depth/history",
        "summary": "Vendor catalog row only: potentially useful for execution and live data, not current selector evidence.",
        "raw_text_excerpt": "ICE catalog describes DCE Level 1, Level 2 and historical market data access through licensed products.",
        "event_family": "licensed_market_data",
        "event_type": "vendor_market_data_catalog",
        "direction_hint": "none_source_only",
        "status": "licensed_vendor_required",
        "source_access_state": "licensed_vendor_required",
        "requires_credentials": 1,
        "credentials_present": 0,
        "manual_capture_required": 0,
        "usable_for_forward_monitor": 0,
        "usable_for_history_selector": 0,
        "notes": "Useful for future TCA/source closure, not for immediate strategy change.",
    },
    {
        "product_vt_symbol": "ag.SHFE",
        "source_name": "SHFE Daily Data",
        "source_url": "https://www.shfe.cn/eng/reports/StatisticalData/DailyData/",
        "source_class": "manual_public_exchange_source",
        "source_authority": "official_public_exchange",
        "published_at": "",
        "published_at_confidence": "daily_page_dynamic",
        "headline": "SHFE daily ranking and warrant source for silver",
        "summary": "Public manual route: SHFE daily data lists member ranking and warehouse stock report types that can be captured point-in-time.",
        "raw_text_excerpt": "SHFE Daily Data page exposes daily ranking and futures exchange warehouse stocks daily report categories.",
        "event_family": "exchange_warehouse_member",
        "event_type": "daily_warrant_member_ranking_catalog",
        "direction_hint": "none_source_only",
        "status": "manual_public_capture_ready",
        "source_access_state": "manual_capture_required",
        "requires_credentials": 0,
        "credentials_present": 0,
        "manual_capture_required": 1,
        "usable_for_forward_monitor": 1,
        "usable_for_history_selector": 0,
        "notes": "Forward monitor only until parser records dated raw text/hash repeatedly.",
    },
    {
        "product_vt_symbol": "CY.CZCE",
        "source_name": "USDA NASS National Crop Progress",
        "source_url": "https://data.nass.usda.gov/Publications/National_Crop_Progress/index.php",
        "source_class": "manual_public_event_source",
        "source_authority": "official_public_usda",
        "published_at": "",
        "published_at_confidence": "weekly_release_page",
        "headline": "Cotton crop progress and condition monitor for cotton yarn chain",
        "summary": "Public event route: NASS Crop Progress gives weekly crop progress and condition reports; CY mapping is indirect through cotton supply.",
        "raw_text_excerpt": "NASS National Crop Progress page provides crop progress reports and cotton timetable resources for weekly monitoring.",
        "event_family": "crop_progress_condition",
        "event_type": "cotton_crop_progress_source_catalog",
        "direction_hint": "none_source_only",
        "status": "manual_public_event_source_catalog",
        "source_access_state": "manual_capture_required",
        "requires_credentials": 0,
        "credentials_present": 0,
        "manual_capture_required": 1,
        "usable_for_forward_monitor": 1,
        "usable_for_history_selector": 0,
        "notes": "CY relevance is lower than direct cotton futures; needs forward episodes before IC audit.",
    },
    {
        "product_vt_symbol": "CY.CZCE",
        "source_name": "USDA ERS Cotton and Wool Outlook",
        "source_url": "https://ers.usda.gov/publications/pub-details?pubid=114047",
        "source_class": "manual_public_event_source",
        "source_authority": "official_public_usda",
        "published_at": "2026-05-14T00:00:00+00:00",
        "published_at_confidence": "source_index_release_date",
        "headline": "Monthly cotton supply and trade context for CY",
        "summary": "Public event route: ERS Cotton and Wool Outlook provides USDA monthly cotton projections and textile trade context.",
        "raw_text_excerpt": "ERS Cotton and Wool Outlook page describes monthly cotton projections, fiber data and trade context.",
        "event_family": "monthly_supply_demand",
        "event_type": "cotton_outlook_source_catalog",
        "direction_hint": "none_source_only",
        "status": "manual_public_event_source_catalog",
        "source_access_state": "manual_capture_required",
        "requires_credentials": 0,
        "credentials_present": 0,
        "manual_capture_required": 1,
        "usable_for_forward_monitor": 1,
        "usable_for_history_selector": 0,
        "notes": "Use received_at, not published_at, for all future selector eligibility.",
    },
    {
        "product_vt_symbol": "CY.CZCE",
        "source_name": "CZCE English overview / cotton contract catalog",
        "source_url": "https://english.czce.com.cn/en/AboutUs/Overview/Overview/H081001001003index_1.htm",
        "source_class": "official_static_reference",
        "source_authority": "official_public_exchange",
        "published_at": "",
        "published_at_confidence": "unknown_static_page",
        "headline": "CZCE cotton and cotton yarn product scope reference",
        "summary": "Static reference route: confirms CZCE lists cotton and cotton yarn products, but it is not an event by itself.",
        "raw_text_excerpt": "CZCE overview lists cotton and cotton yarn among its launched futures products.",
        "event_family": "contract_reference",
        "event_type": "czce_product_scope_reference",
        "direction_hint": "none_source_only",
        "status": "static_reference_only",
        "source_access_state": "manual_reference_only",
        "requires_credentials": 0,
        "credentials_present": 0,
        "manual_capture_required": 1,
        "usable_for_forward_monitor": 1,
        "usable_for_history_selector": 0,
        "notes": "Reference supports mapping, not alpha.",
    },
    {
        "product_vt_symbol": "SR.CZCE",
        "source_name": "USDA WASDE",
        "source_url": "https://www.usda.gov/about-usda/general-information/staff-offices/office-chief-economist/commodity-markets/wasde-report",
        "source_class": "manual_public_event_source",
        "source_authority": "official_public_usda",
        "published_at": "2026-05-12T12:00:00-04:00",
        "published_at_confidence": "source_release_calendar",
        "headline": "WASDE sugar supply and use monitor",
        "summary": "Public event route: WASDE covers U.S. sugar and Mexico sugar supply/use; mapping to SR is macro, not China direct.",
        "raw_text_excerpt": "WASDE release page states the monthly report covers cotton and U.S./Mexico sugar supply and use.",
        "event_family": "monthly_supply_demand",
        "event_type": "sugar_wasde_source_catalog",
        "direction_hint": "none_source_only",
        "status": "manual_public_event_source_catalog",
        "source_access_state": "manual_capture_required",
        "requires_credentials": 0,
        "credentials_present": 0,
        "manual_capture_required": 1,
        "usable_for_forward_monitor": 1,
        "usable_for_history_selector": 0,
        "notes": "SR relevance is global macro; it needs forward evidence before any selector use.",
    },
    {
        "product_vt_symbol": "SR.CZCE",
        "source_name": "CZCE static reference data / White Sugar futures",
        "source_url": "https://english.czce.com.cn/en/DFSStaticFiles/Future/2024/20240418/EnglishFutureDataReferenceData.htm",
        "source_class": "official_static_reference",
        "source_authority": "official_public_exchange",
        "published_at": "2024-04-18T00:00:00+08:00",
        "published_at_confidence": "static_file_path_date",
        "headline": "CZCE white sugar contract reference",
        "summary": "Static reference route: confirms White Sugar futures contract details and trading structure for mapping.",
        "raw_text_excerpt": "CZCE reference data includes White Sugar futures rows and contract metadata.",
        "event_family": "contract_reference",
        "event_type": "czce_sugar_contract_reference",
        "direction_hint": "none_source_only",
        "status": "static_reference_only",
        "source_access_state": "manual_reference_only",
        "requires_credentials": 0,
        "credentials_present": 0,
        "manual_capture_required": 1,
        "usable_for_forward_monitor": 1,
        "usable_for_history_selector": 0,
        "notes": "Reference supports product mapping and capacity checks, not trading signal.",
    },
]


def _now_cst() -> datetime:
    return datetime.now(timezone(timedelta(hours=8)))


def _fmt_cst(value: datetime) -> str:
    return value.strftime("%Y-%m-%d %H:%M:%S CST")


def _parse_datetime(text: str) -> datetime | None:
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


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


def build_ledger(received_at: datetime) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for index, item in enumerate(SOURCE_BLUEPRINTS, start=1):
        product = item["product_vt_symbol"]
        published = _parse_datetime(str(item.get("published_at", "")))
        source_age_hours = ""
        if published is not None:
            source_age_hours = round((received_at.astimezone(timezone.utc) - published.astimezone(timezone.utc)).total_seconds() / 3600, 2)
        raw_payload = "|".join(
            [
                LINE_ID,
                product,
                item["source_name"],
                item["source_url"],
                item["headline"],
                item["raw_text_excerpt"],
                _fmt_cst(received_at),
            ]
        )
        event_signal_ready = 0
        event_auto_monitor_validated = 0
        row = {
            "run_id": MODEL_TAG,
            "row_id": f"stage624_{index:03d}",
            "received_at_local": _fmt_cst(received_at),
            "received_at_utc": received_at.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "line_id": LINE_ID,
            "route": "manual_public_event_or_source_catalog",
            "product_vt_symbol": product,
            "product_code": PRODUCT_CODE[product],
            "exchange": EXCHANGE[product],
            "product_family": PRODUCT_FAMILY[product],
            "source_name": item["source_name"],
            "source_url": item["source_url"],
            "source_class": item["source_class"],
            "source_authority": item["source_authority"],
            "published_at": item["published_at"],
            "published_at_confidence": item["published_at_confidence"],
            "headline": item["headline"],
            "summary": item["summary"],
            "raw_text_hash": _sha256(raw_payload),
            "raw_text_excerpt": item["raw_text_excerpt"],
            "event_family": item["event_family"],
            "event_type": item["event_type"],
            "sentiment_label": "neutral_source_catalog",
            "sentiment_score": 0.0,
            "relevance_score": _relevance_score(product, item["event_family"], item["source_class"]),
            "direction_hint": item["direction_hint"],
            "mapper_version": "manual_public_event_mapper_v1",
            "product_mapping_method": _mapping_method(product, item["source_class"]),
            "status": item["status"],
            "source_access_state": item["source_access_state"],
            "source_age_hours": source_age_hours,
            "requires_credentials": int(item["requires_credentials"]),
            "credentials_present": int(item["credentials_present"]),
            "manual_capture_required": int(item["manual_capture_required"]),
            "usable_for_forward_monitor": int(item["usable_for_forward_monitor"]),
            "usable_for_history_selector": int(item["usable_for_history_selector"]),
            "event_auto_monitor_validated": event_auto_monitor_validated,
            "event_signal_ready": event_signal_ready,
            "selector_candidate": 0,
            "paper_or_whitelist_allowed": 0,
            "point_in_time_rule": "Use received_at_local only; published_at never grants history selector eligibility; no backfill into strategy history.",
            "notes": item["notes"],
        }
        rows.append(row)
    ledger = pd.DataFrame(rows)
    ledger["raw_text_hash_present"] = ledger["raw_text_hash"].astype(str).str.len().gt(0).astype(int)
    ledger["source_url_present"] = ledger["source_url"].astype(str).str.len().gt(0).astype(int)
    ledger["product_mapping_present"] = ledger["product_vt_symbol"].isin(MONITOR_PRODUCTS).astype(int)
    return ledger


def _mapping_method(product: str, source_class: str) -> str:
    if product in {"j.DCE", "i.DCE"}:
        return "direct_exchange_product_to_dce_api_or_vendor_catalog"
    if product == "ag.SHFE":
        return "direct_shfe_product_to_daily_warrant_member_catalog"
    if product == "CY.CZCE":
        if "usda" in source_class or "event" in source_class:
            return "manual_cotton_supply_to_czce_cotton_yarn_chain"
        return "direct_czce_cotton_yarn_product_reference"
    if product == "SR.CZCE":
        if "event" in source_class:
            return "manual_sugar_supply_to_czce_white_sugar"
        return "direct_czce_white_sugar_product_reference"
    return "manual_product_mapping"


def _relevance_score(product: str, event_family: str, source_class: str) -> float:
    if product in {"j.DCE", "i.DCE"} and "authorized" in source_class:
        return 0.85
    if product in {"j.DCE", "i.DCE"} and "licensed" in source_class:
        return 0.70
    if product == "ag.SHFE":
        return 0.80
    if product == "CY.CZCE" and event_family in {"crop_progress_condition", "monthly_supply_demand"}:
        return 0.55
    if product == "CY.CZCE":
        return 0.70
    if product == "SR.CZCE" and event_family == "monthly_supply_demand":
        return 0.60
    if product == "SR.CZCE":
        return 0.75
    return 0.50


def build_product_summary(ledger: pd.DataFrame) -> pd.DataFrame:
    grouped = ledger.groupby(["product_family", "product_vt_symbol", "exchange"], as_index=False).agg(
        ledger_rows=("row_id", "count"),
        forward_monitor_rows=("usable_for_forward_monitor", "sum"),
        history_selector_rows=("usable_for_history_selector", "sum"),
        event_auto_monitor_rows=("event_auto_monitor_validated", "sum"),
        event_signal_ready_rows=("event_signal_ready", "sum"),
        credential_required_rows=("requires_credentials", "sum"),
        credential_present_rows=("credentials_present", "sum"),
        manual_capture_rows=("manual_capture_required", "sum"),
        source_classes=("source_class", lambda series: ",".join(sorted(set(map(str, series))))),
        event_families=("event_family", lambda series: ",".join(sorted(set(map(str, series))))),
        avg_relevance_score=("relevance_score", "mean"),
    )
    grouped["selector_locked"] = 1
    grouped["paper_or_whitelist_allowed"] = 0
    grouped["pit_received_dates"] = 1
    grouped["missing_for_promotion"] = grouped.apply(_product_missing_for_promotion, axis=1)
    return grouped


def _product_missing_for_promotion(row: pd.Series) -> str:
    missing = ["event_auto_monitor", "20_pit_dates", "live_tca", "live_context"]
    if int(row["credential_required_rows"]) > int(row["credential_present_rows"]):
        missing.insert(0, "authorized_credentials")
    if int(row["event_signal_ready_rows"]) == 0:
        missing.append("predictive_signal_evidence")
    return ",".join(missing)


def build_source_summary(ledger: pd.DataFrame) -> pd.DataFrame:
    return ledger.groupby(["source_class", "source_authority", "source_access_state"], as_index=False).agg(
        rows=("row_id", "count"),
        products=("product_vt_symbol", lambda series: ",".join(sorted(set(map(str, series))))),
        forward_monitor_rows=("usable_for_forward_monitor", "sum"),
        history_selector_rows=("usable_for_history_selector", "sum"),
        requires_credentials=("requires_credentials", "sum"),
        credentials_present=("credentials_present", "sum"),
        manual_capture_rows=("manual_capture_required", "sum"),
        event_signal_ready_rows=("event_signal_ready", "sum"),
    )


def build_gates(ledger: pd.DataFrame, product_summary: pd.DataFrame) -> pd.DataFrame:
    source_products = int(ledger["product_vt_symbol"].nunique())
    max_pit_dates = 1
    gates = [
        {
            "gate": "all_monitor_products_have_source_catalog",
            "passed": int(source_products == len(MONITOR_PRODUCTS)),
            "current": str(source_products),
            "required": str(len(MONITOR_PRODUCTS)),
            "note": "Every Stage316/321 monitor product has at least one manual/public/authorized source row.",
        },
        {
            "gate": "raw_text_hash_present_all_rows",
            "passed": int(ledger["raw_text_hash_present"].eq(1).all()),
            "current": f"{int(ledger['raw_text_hash_present'].sum())}/{len(ledger)}",
            "required": f"{len(ledger)}/{len(ledger)}",
            "note": "Rows carry source-excerpt hashes for auditability; no long source text is embedded.",
        },
        {
            "gate": "product_mapping_present_all_rows",
            "passed": int(ledger["product_mapping_present"].eq(1).all()),
            "current": f"{int(ledger['product_mapping_present'].sum())}/{len(ledger)}",
            "required": f"{len(ledger)}/{len(ledger)}",
            "note": "All rows map to j/i/ag/CY/SR only.",
        },
        {
            "gate": "history_selector_rows_zero",
            "passed": int(ledger["usable_for_history_selector"].sum() == 0),
            "current": str(int(ledger["usable_for_history_selector"].sum())),
            "required": "0",
            "note": "No row is allowed into history selector or backtest alpha.",
        },
        {
            "gate": "paper_whitelist_locked",
            "passed": int(ledger["paper_or_whitelist_allowed"].sum() == 0),
            "current": str(int(ledger["paper_or_whitelist_allowed"].sum())),
            "required": "0",
            "note": "No paper selector or trading whitelist permission.",
        },
        {
            "gate": "selector_locked",
            "passed": int(product_summary["selector_locked"].eq(1).all()),
            "current": "0 selector rows",
            "required": "locked",
            "note": "This is a ledger bootstrap, not a deployable signal.",
        },
        {
            "gate": "dce_authorized_credentials_present",
            "passed": int(
                ledger.loc[ledger["source_class"].eq("authorized_dce_api_catalog"), "credentials_present"].sum()
                >= ledger.loc[ledger["source_class"].eq("authorized_dce_api_catalog"), "requires_credentials"].sum()
            ),
            "current": str(int(ledger.loc[ledger["source_class"].eq("authorized_dce_api_catalog"), "credentials_present"].sum())),
            "required": str(int(ledger.loc[ledger["source_class"].eq("authorized_dce_api_catalog"), "requires_credentials"].sum())),
            "note": "DCE j/i still require authorized credentials before automatic official monitor.",
        },
        {
            "gate": "event_auto_monitor_validated",
            "passed": int(ledger["event_auto_monitor_validated"].sum() > 0),
            "current": str(int(ledger["event_auto_monitor_validated"].sum())),
            "required": ">0",
            "note": "No automatic raw-text event monitor has been validated yet.",
        },
        {
            "gate": "pit_dates_reach_20",
            "passed": int(max_pit_dates >= MIN_PIT_DATES_FOR_PREDICTIVE_AUDIT),
            "current": str(max_pit_dates),
            "required": str(MIN_PIT_DATES_FOR_PREDICTIVE_AUDIT),
            "note": "Only one received_at date in this bootstrap; predictive audit remains blocked.",
        },
        {
            "gate": "event_signal_ready_zero",
            "passed": int(ledger["event_signal_ready"].sum() == 0),
            "current": str(int(ledger["event_signal_ready"].sum())),
            "required": "0",
            "note": "Explicitly confirms no event row is being treated as alpha signal.",
        },
    ]
    return pd.DataFrame(gates)


def make_chart(ledger: pd.DataFrame, product_summary: pd.DataFrame, source_summary: pd.DataFrame, gates: pd.DataFrame) -> None:
    status_score = {
        "authorization_required_source_catalog": 1,
        "licensed_vendor_required": 1,
        "manual_public_capture_ready": 3,
        "manual_public_event_source_catalog": 3,
        "static_reference_only": 2,
    }
    score_label = {0: "", 1: "LOCK", 2: "REF", 3: "MON"}
    event_families = sorted(ledger["event_family"].unique())
    matrix = pd.DataFrame(0, index=MONITOR_PRODUCTS, columns=event_families, dtype=float)
    labels = pd.DataFrame("", index=MONITOR_PRODUCTS, columns=event_families)
    for _, row in ledger.iterrows():
        product = str(row["product_vt_symbol"])
        family = str(row["event_family"])
        score = status_score.get(str(row["status"]), 0)
        if score >= matrix.loc[product, family]:
            matrix.loc[product, family] = score
            labels.loc[product, family] = score_label.get(score, "")

    fig, axes = plt.subplots(2, 2, figsize=(18, 11))
    fig.suptitle("Stage624 manual/public event ledger bootstrap: source catalog only, selector locked", fontsize=16)

    ax = axes[0, 0]
    cmap = matplotlib.colors.ListedColormap(["#f7fafc", "#fed7d7", "#bee3f8", "#c6f6d5"])
    norm = matplotlib.colors.BoundaryNorm([-0.5, 0.5, 1.5, 2.5, 3.5], cmap.N)
    ax.imshow(matrix.values, cmap=cmap, norm=norm, aspect="auto")
    ax.set_xticks(range(len(event_families)))
    ax.set_xticklabels(event_families, rotation=35, ha="right")
    ax.set_yticks(range(len(MONITOR_PRODUCTS)))
    ax.set_yticklabels(MONITOR_PRODUCTS)
    ax.set_title("Product x event-source family status")
    for i in range(matrix.shape[0]):
        for j in range(matrix.shape[1]):
            text = labels.iloc[i, j]
            if text:
                ax.text(j, i, text, ha="center", va="center", fontsize=9, fontweight="bold")

    ax = axes[0, 1]
    family_counts = ledger["event_family"].value_counts().sort_values()
    ax.barh(family_counts.index, family_counts.values, color="#3182ce")
    ax.set_title("Event/source taxonomy rows")
    ax.set_xlabel("rows")
    for y, value in enumerate(family_counts.values):
        ax.text(value + 0.05, y, str(int(value)), va="center", fontsize=9)

    ax = axes[1, 0]
    completeness = pd.Series(
        {
            "source_url": ledger["source_url_present"].mean(),
            "raw_hash": ledger["raw_text_hash_present"].mean(),
            "product_map": ledger["product_mapping_present"].mean(),
            "published_at": ledger["published_at"].astype(str).ne("").mean(),
            "forward_monitor": ledger["usable_for_forward_monitor"].mean(),
            "history_selector": ledger["usable_for_history_selector"].mean(),
            "event_auto_monitor": ledger["event_auto_monitor_validated"].mean(),
            "event_signal_ready": ledger["event_signal_ready"].mean(),
        }
    )
    colors = ["#38a169" if value >= 0.99 else "#dd6b20" if value > 0 else "#e53e3e" for value in completeness.values]
    ax.barh(completeness.index, completeness.values, color=colors)
    ax.set_xlim(0, 1.05)
    ax.set_title("Field completeness and readiness ratios")
    for y, value in enumerate(completeness.values):
        ax.text(max(value, 0.03), y, f"{value:.0%}", va="center", fontsize=9, color="black")

    ax = axes[1, 1]
    gate_view = gates.copy()
    y_pos = np.arange(len(gate_view))
    gate_colors = ["#38a169" if int(item) else "#e53e3e" for item in gate_view["passed"]]
    ax.barh(y_pos, [1] * len(gate_view), color=gate_colors)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(gate_view["gate"], fontsize=8)
    ax.set_xlim(0, 1)
    ax.set_xticks([])
    ax.invert_yaxis()
    ax.set_title("Hard gates")
    for y, (_, row) in enumerate(gate_view.iterrows()):
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
    passed = int(gates["passed"].sum())
    total = len(gates)
    report = f"""# Stage624 Manual/Public Event Ledger Bootstrap

- line_id: `{LINE_ID}`
- generated_at: `{_fmt_cst(received_at)}`
- decision: `{decision["decision"]}`
- stage nature: read-only source/event ledger bootstrap; no strategy replay, no selector, no paper whitelist, no CTP/order path.

## External Research And Judgement

References:
{chr(10).join(f"- {item}" for item in REFERENCES)}

Judgement:
- The low-single-risk breadth route remains valid, but product selection must be source/TCA/live executable.
- DCE j/i still need authorized API or licensed vendor access; public rows are not enough for selector evidence.
- SHFE and USDA/CZCE public rows are suitable for forward monitor bootstrap, but they are source rows, not alpha events.
- Every row is forced to `usable_for_history_selector=0`; this prevents backfilled event data from becoming hindsight selector input.

## Key Results

- ledger rows: `{len(ledger)}`
- products covered: `{ledger["product_vt_symbol"].nunique()}/{len(MONITOR_PRODUCTS)}`
- forward monitor rows: `{int(ledger["usable_for_forward_monitor"].sum())}`
- history selector rows: `{int(ledger["usable_for_history_selector"].sum())}`
- event auto monitor validated rows: `{int(ledger["event_auto_monitor_validated"].sum())}`
- event signal ready rows: `{int(ledger["event_signal_ready"].sum())}`
- hard gates: `{passed}/{total}`
- selector unlocked now: `{decision["selector_unlocked_now"]}`
- paper/whitelist allowed: `{decision["paper_or_whitelist_allowed"]}`

## Product Summary

{_md_table(product_summary, max_rows=20)}

## Source Summary

{_md_table(source_summary, max_rows=20)}

## Gates

{_md_table(gates, max_rows=20)}

## Visual Review Notes

- Top-left heatmap should show `j/i` locked at DCE authorized/vendor rows, while `ag/CY/SR` have public monitor/reference rows. This separation is intended: public source catalog is not selector permission.
- Top-right taxonomy should show multiple event/source families, not a one-source monoculture.
- Bottom-left should show source URL/hash/product mapping are complete, while history selector, auto monitor and event signal readiness remain red or zero.
- Bottom-right should show fail-closed gates green and predictive/credential gates red.

## Conclusion

This stage improves the external data path, not the trading rule. It creates a point-in-time auditable source catalog for `j/i/ag/CY/SR`, but the selector remains locked because DCE authorization, automatic raw-text monitoring, 20 PIT dates, live TCA and live context are still missing.

## Output Files

- ledger: `{LEDGER_PATH}`
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
    ledger = build_ledger(received_at)
    product_summary = build_product_summary(ledger)
    source_summary = build_source_summary(ledger)
    gates = build_gates(ledger, product_summary)

    decision = {
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at_cst": _fmt_cst(received_at),
        "decision": "manual_public_event_ledger_bootstrapped_selector_locked",
        "ledger_rows": int(len(ledger)),
        "products_covered": int(ledger["product_vt_symbol"].nunique()),
        "forward_monitor_rows": int(ledger["usable_for_forward_monitor"].sum()),
        "history_selector_rows": int(ledger["usable_for_history_selector"].sum()),
        "event_auto_monitor_validated_rows": int(ledger["event_auto_monitor_validated"].sum()),
        "event_signal_ready_rows": int(ledger["event_signal_ready"].sum()),
        "dce_authorized_credentials_present": int(
            ledger.loc[ledger["source_class"].eq("authorized_dce_api_catalog"), "credentials_present"].sum()
        ),
        "selector_unlocked_now": 0,
        "paper_or_whitelist_allowed": 0,
        "trading_whitelist_allowed": False,
        "promotion_allowed": False,
        "hard_gates_passed": int(gates["passed"].sum()),
        "hard_gates_total": int(len(gates)),
        "summary": (
            "Manual/public source and event catalog rows now cover j/i/ag/CY/SR, "
            "but DCE authorization, event auto monitor, 20 PIT dates, live TCA and live context remain missing; selector stays locked."
        ),
    }

    ledger.to_csv(LEDGER_PATH, index=False, encoding="utf-8-sig")
    product_summary.to_csv(PRODUCT_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    source_summary.to_csv(SOURCE_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    gates.to_csv(GATES_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    write_report(received_at, ledger, product_summary, source_summary, gates, decision)
    make_chart(ledger, product_summary, source_summary, gates)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
