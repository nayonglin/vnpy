from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any

import pandas as pd
import requests


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
os.environ.setdefault("MPLCONFIGDIR", str(OUTPUT_DIR / ".matplotlib"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


MODEL_TAG = "stage595_p0_official_endpoint_discovery_v1"
OUTPUT_PREFIX = "qmt_roll_stage595_p0_official_endpoint_discovery"
LINE_ID = "futures_trend_drawdown30_preserve_return"

ENDPOINT_DISCOVERY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_endpoint_discovery_{MODEL_TAG}.csv"
PRODUCT_READINESS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_readiness_{MODEL_TAG}.csv"
GATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gates_{MODEL_TAG}.csv"
NEXT_ACTIONS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_next_actions_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

PROBE_DATE = "20260603"
LEGACY_SHFE_DATE = "20200702"
HTTP_TIMEOUT_SECONDS = 12

P0_PRODUCTS = {
    "v.DCE": {"product_code": "V", "exchange": "DCE", "product_name": "PVC", "family": "petrochem"},
    "ao.SHFE": {"product_code": "AO", "exchange": "SHFE", "product_name": "氧化铝", "family": "base_metals"},
    "lu.INE": {"product_code": "LU", "exchange": "INE", "product_name": "低硫燃料油", "family": "energy_oil"},
}


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


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "无数据。"
    view = frame.copy()
    if max_rows is not None:
        view = view.head(max_rows)
    for col in view.columns:
        if pd.api.types.is_float_dtype(view[col]):
            view[col] = view[col].map(lambda x: f"{x:.4f}" if pd.notna(x) else "")
    return view.to_markdown(index=False)


def _base_row(now_local: datetime, now_utc: datetime, product_symbol: str, route: str, name: str, url: str) -> dict[str, Any]:
    product = P0_PRODUCTS[product_symbol]
    return {
        "run_id": now_local.strftime("stage595_%Y%m%d_%H%M%S"),
        "received_at_local": now_local.isoformat(timespec="seconds"),
        "received_at_utc": now_utc.isoformat(timespec="seconds"),
        "line_id": LINE_ID,
        "product_vt_symbol": product_symbol,
        "product_code": product["product_code"],
        "exchange": product["exchange"],
        "product_family": product["family"],
        "product_name": product["product_name"],
        "route": route,
        "endpoint_name": name,
        "official_source": 1,
        "exact_official_page": 0,
        "exact_data_endpoint": 0,
        "source_url": url,
        "http_method": "GET",
        "http_status": "",
        "content_type": "",
        "response_bytes": 0,
        "probe_status": "not_attempted",
        "parse_status": "not_attempted",
        "matched_product": 0,
        "matched_key": "",
        "source_date": "",
        "published_at": "",
        "raw_sha256": "",
        "sample_value_json": "{}",
        "usable_for_forward_monitor": 0,
        "usable_for_history_selector": 0,
        "block_reason": "",
        "notes": "",
    }


def _looks_like_waf(text: str) -> bool:
    markers = ["WEB 应用防火墙", "向右滑动填充拼图", "captcha", "人机识别"]
    return any(marker in text for marker in markers)


def _probe_get(url: str, headers: dict[str, str] | None = None) -> dict[str, Any]:
    try:
        r = requests.get(url, headers=headers or {"User-Agent": "Mozilla/5.0"}, timeout=HTTP_TIMEOUT_SECONDS)
        text = r.text
        status = "waf" if _looks_like_waf(text) else ("http_ok" if r.status_code == 200 else f"http_{r.status_code}")
        return {
            "status": status,
            "http_status": int(r.status_code),
            "content_type": r.headers.get("content-type", ""),
            "response_bytes": int(len(r.content)),
            "text": text[:1200],
            "raw_text": text,
            "raw": r.content,
        }
    except Exception as exc:  # pragma: no cover - external network instability
        return {
            "status": "error",
            "http_status": "",
            "content_type": "",
            "response_bytes": 0,
            "text": str(exc)[:1200],
            "raw_text": "",
            "raw": b"",
            "error_type": type(exc).__name__,
        }


def _probe_dce_post(url: str) -> dict[str, Any]:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "http://www.dce.com.cn/dce/channel/list/187.html",
        "Origin": "http://www.dce.com.cn",
        "Content-Type": "application/json",
    }
    try:
        r = requests.post(url, json={"tradeDate": PROBE_DATE, "varietyId": "all"}, headers=headers, timeout=HTTP_TIMEOUT_SECONDS)
        text = r.text
        status = "waf" if _looks_like_waf(text) else ("http_ok" if r.status_code == 200 else f"http_{r.status_code}")
        return {
            "status": status,
            "http_status": int(r.status_code),
            "content_type": r.headers.get("content-type", ""),
            "response_bytes": int(len(r.content)),
            "text": text[:1200],
            "raw_text": text,
            "raw": r.content,
        }
    except Exception as exc:  # pragma: no cover
        return {
            "status": "error",
            "http_status": "",
            "content_type": "",
            "response_bytes": 0,
            "text": str(exc)[:1200],
            "raw_text": "",
            "raw": b"",
            "error_type": type(exc).__name__,
        }


def _apply_probe(row: dict[str, Any], probe: dict[str, Any]) -> dict[str, Any]:
    row["http_status"] = probe.get("http_status", "")
    row["content_type"] = probe.get("content_type", "")
    row["response_bytes"] = probe.get("response_bytes", 0)
    row["probe_status"] = probe.get("status", "")
    if probe.get("status") == "waf":
        row["block_reason"] = "official_site_waf"
    elif str(probe.get("status", "")).startswith("http_") and probe.get("status") != "http_ok":
        row["block_reason"] = str(probe.get("status"))
    elif probe.get("status") == "error":
        row["block_reason"] = f"{probe.get('error_type', 'error')}: {probe.get('text', '')[:160]}"
    return row


def _parse_json_text(text: str) -> Any | None:
    try:
        return json.loads(text)
    except Exception:
        return None


def _probe_shfe_legacy(row: dict[str, Any], url: str, expected_name: str) -> dict[str, Any]:
    probe = _probe_get(url)
    row = _apply_probe(row, probe)
    row["exact_data_endpoint"] = 1
    data = _parse_json_text(probe.get("raw_text", ""))
    if not isinstance(data, dict):
        row["parse_status"] = "json_parse_failed"
        return row
    cursor = data.get("o_cursor", [])
    matched = [item for item in cursor if expected_name in str(item.get("VARNAME", ""))]
    row["parse_status"] = "json_ok"
    row["source_date"] = str(data.get("o_tradingday", ""))
    row["matched_product"] = int(bool(matched))
    row["matched_key"] = expected_name if matched else ""
    sample = matched[:3] if matched else cursor[:3]
    row["raw_sha256"] = _stable_hash(sample)
    row["sample_value_json"] = json.dumps(_json_safe(sample), ensure_ascii=False, sort_keys=True)
    row["block_reason"] = "legacy_date_only_not_forward" if not matched else "legacy_source_not_current_forward"
    return row


def _probe_ine_kx(row: dict[str, Any], url: str, expected_code: str) -> dict[str, Any]:
    probe = _probe_get(url)
    row = _apply_probe(row, probe)
    row["exact_data_endpoint"] = 1
    data = _parse_json_text(probe.get("raw_text", ""))
    if not isinstance(data, dict):
        row["parse_status"] = "json_parse_failed"
        return row
    rows = data.get("o_curinstrument", []) or data.get("o_cursor", [])
    matched = [item for item in rows if str(item.get("PRODUCTGROUPID", "")).lower() == expected_code.lower() or str(item.get("PRODUCTID", "")).lower().startswith(expected_code.lower())]
    row["parse_status"] = "json_ok"
    row["source_date"] = PROBE_DATE
    row["matched_product"] = int(bool(matched))
    row["matched_key"] = expected_code if matched else ""
    row["raw_sha256"] = _stable_hash(matched[:3] if matched else rows[:3])
    row["sample_value_json"] = json.dumps(_json_safe(matched[:3] if matched else rows[:3]), ensure_ascii=False, sort_keys=True)
    row["notes"] = "daily trading/settlement endpoint works, but it is not inventory/warehouse route"
    row["block_reason"] = "not_inventory_or_event_route"
    return row


def _discover(now_local: datetime, now_utc: datetime) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    dce_url = "http://www.dce.com.cn/dcereport/publicweb/dailystat/wbillWeeklyQuotes"
    row = _base_row(now_local, now_utc, "v.DCE", "warehouse_official", "DCE official warehouse JSON API", dce_url)
    row["exact_official_page"] = 1
    row["exact_data_endpoint"] = 1
    row["http_method"] = "POST"
    row = _apply_probe(row, _probe_dce_post(dce_url))
    row["parse_status"] = "not_parsed_due_block" if row["probe_status"] != "http_ok" else "needs_parser"
    rows.append(row)

    dce_page = "https://www.dce.com.cn/dce/channel/list/187.html"
    row = _base_row(now_local, now_utc, "v.DCE", "warehouse_official_page", "DCE official warehouse page", dce_page)
    row["exact_official_page"] = 1
    row = _apply_probe(row, _probe_get(dce_page))
    row["parse_status"] = "html_page_probe"
    rows.append(row)

    shfe_old = f"https://www.shfe.com.cn/data/tradedata/future/dailydata/{PROBE_DATE}dailystock.dat"
    row = _base_row(now_local, now_utc, "ao.SHFE", "warehouse_official_legacy_dat", "SHFE legacy dailystock DAT current date", shfe_old)
    row["exact_data_endpoint"] = 1
    row = _apply_probe(row, _probe_get(shfe_old))
    row["parse_status"] = "not_parsed_due_404" if row["probe_status"] != "http_ok" else "needs_parser"
    rows.append(row)

    shfe_legacy_ok = f"https://www.shfe.com.cn/data/tradedata/future/dailydata/{LEGACY_SHFE_DATE}dailystock.dat"
    row = _base_row(now_local, now_utc, "ao.SHFE", "warehouse_official_legacy_dat", "SHFE legacy dailystock DAT legacy date", shfe_legacy_ok)
    row = _probe_shfe_legacy(row, shfe_legacy_ok, "氧化铝")
    rows.append(row)

    shfe_new = f"https://www.shfe.com.cn/data/tradedata/future/stockdata/dailystock_{PROBE_DATE}/ZH/all.html"
    row = _base_row(now_local, now_utc, "ao.SHFE", "warehouse_official_new_html", "SHFE new dailystock stockdata HTML", shfe_new)
    row["exact_official_page"] = 1
    row["exact_data_endpoint"] = 1
    row = _apply_probe(row, _probe_get(shfe_new))
    row["parse_status"] = "not_parsed_due_waf" if row["probe_status"] == "waf" else "needs_html_parser"
    rows.append(row)

    shfe_ui = "https://www.shfe.com.cn/reports/tradedata/dailyandweeklydata/?query_params=dailystock"
    row = _base_row(now_local, now_utc, "ao.SHFE", "warehouse_official_page", "SHFE official dailystock UI", shfe_ui)
    row["exact_official_page"] = 1
    row = _apply_probe(row, _probe_get(shfe_ui))
    row["parse_status"] = "html_page_probe"
    rows.append(row)

    ine_dailystock_page = "https://www.ine.cn/reports/tradedata/dailyandweeklydata/?query_params=dailystock"
    row = _base_row(now_local, now_utc, "lu.INE", "warehouse_official_page", "INE official daily warrants UI", ine_dailystock_page)
    row["exact_official_page"] = 1
    row = _apply_probe(row, _probe_get(ine_dailystock_page))
    row["parse_status"] = "html_page_probe"
    rows.append(row)

    ine_weekly_page = "https://www.ine.cn/reports/tradedata/dailyandweeklydata/?query_params=weeklystock"
    row = _base_row(now_local, now_utc, "lu.INE", "weekly_inventory_official_page", "INE official weekly inventory UI", ine_weekly_page)
    row["exact_official_page"] = 1
    row = _apply_probe(row, _probe_get(ine_weekly_page))
    row["parse_status"] = "html_page_probe"
    rows.append(row)

    ine_stockdata = f"https://www.ine.cn/data/tradedata/future/stockdata/dailystock_{PROBE_DATE}/ZH/all.html"
    row = _base_row(now_local, now_utc, "lu.INE", "warehouse_official_new_html_guess", "INE guessed stockdata dailystock HTML", ine_stockdata)
    row["exact_data_endpoint"] = 1
    row = _apply_probe(row, _probe_get(ine_stockdata))
    row["parse_status"] = "not_parsed_due_waf" if row["probe_status"] == "waf" else "not_confirmed_pattern"
    rows.append(row)

    ine_kx = f"https://www.ine.cn/data/tradedata/future/dailydata/kx{PROBE_DATE}.dat"
    row = _base_row(now_local, now_utc, "lu.INE", "daily_trading_context", "INE official daily trading data", ine_kx)
    row = _probe_ine_kx(row, ine_kx, "lu")
    rows.append(row)

    ine_js = f"https://www.ine.cn/data/tradedata/future/dailydata/js{PROBE_DATE}.dat"
    row = _base_row(now_local, now_utc, "lu.INE", "settlement_context", "INE official settlement data", ine_js)
    row = _probe_ine_kx(row, ine_js, "lu")
    rows.append(row)

    frame = pd.DataFrame(rows)
    frame["endpoint_located"] = ((frame["exact_official_page"].eq(1)) | (frame["exact_data_endpoint"].eq(1))).astype(int)
    frame["data_access_ok"] = ((frame["probe_status"].eq("http_ok")) & (frame["parse_status"].isin(["json_ok", "html_page_probe", "needs_html_parser", "needs_parser"]))).astype(int)
    frame["official_auto_monitor_ready"] = (
        frame["exact_data_endpoint"].eq(1)
        & frame["probe_status"].eq("http_ok")
        & frame["matched_product"].eq(1)
        & frame["raw_sha256"].astype(str).str.len().gt(0)
        & ~frame["route"].isin(["daily_trading_context", "settlement_context"])
    ).astype(int)
    frame["usable_for_forward_monitor"] = frame["official_auto_monitor_ready"]
    return frame


def _product_readiness(frame: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for product_symbol, meta in P0_PRODUCTS.items():
        product = frame[frame["product_vt_symbol"].eq(product_symbol)]
        rows.append(
            {
                "product_vt_symbol": product_symbol,
                "product_family": meta["family"],
                "official_pages_or_endpoints_located": int(product["endpoint_located"].sum()),
                "data_access_ok_rows": int(product["data_access_ok"].sum()),
                "waf_or_412_rows": int(product["probe_status"].isin(["waf", "http_412"]).sum()),
                "matched_product_rows": int(product["matched_product"].sum()),
                "official_auto_monitor_ready_rows": int(product["official_auto_monitor_ready"].sum()),
                "ready_role": _role(product_symbol, product),
            }
        )
    return pd.DataFrame(rows)


def _role(product_symbol: str, product: pd.DataFrame) -> str:
    if product["official_auto_monitor_ready"].sum() > 0:
        return "official_forward_ready"
    if product["endpoint_located"].sum() > 0 and product["probe_status"].isin(["waf", "http_412"]).any():
        return "exact_official_located_access_blocked"
    if product["endpoint_located"].sum() > 0:
        return "official_page_located_data_pattern_unresolved"
    return "official_route_not_located"


def _gates(frame: pd.DataFrame, product: pd.DataFrame) -> pd.DataFrame:
    def row(gate: str, passed: bool, value: Any, threshold: str, hard: int, notes: str) -> dict[str, Any]:
        return {"gate": gate, "passed": int(bool(passed)), "value": value, "threshold": threshold, "hard_gate": hard, "notes": notes}

    p0_count = len(product)
    return pd.DataFrame(
        [
            row("all_gap_products_have_exact_official_page_or_endpoint", bool((product["official_pages_or_endpoints_located"] > 0).all()), int((product["official_pages_or_endpoints_located"] > 0).sum()), f"{p0_count}/{p0_count}", 1, "DCE/SHFE/INE official pages or data URLs are now located"),
            row("all_gap_products_have_parsed_current_product_data", bool((product["matched_product_rows"] > 0).all()), int((product["matched_product_rows"] > 0).sum()), f"{p0_count}/{p0_count}", 1, "requires current endpoint data, not legacy or unrelated daily trading data"),
            row("all_gap_products_have_official_auto_monitor_ready", bool((product["official_auto_monitor_ready_rows"] > 0).all()), int((product["official_auto_monitor_ready_rows"] > 0).sum()), f"{p0_count}/{p0_count}", 1, "requires exact endpoint + product match + raw hash"),
            row("no_waf_or_412_on_required_routes", not bool(product["waf_or_412_rows"].sum()), int(product["waf_or_412_rows"].sum()), "0", 1, "current automated requests still face WAF/412 on required routes"),
            row("history_selector_disabled", bool(frame["usable_for_history_selector"].eq(0).all()), int(frame["usable_for_history_selector"].sum()), "0", 1, "no endpoint discovery row is allowed for history selector"),
            row("paper_selector_allowed", False, 0, "true only after monitor + 20 dates", 1, "not allowed in Stage295"),
            row("trading_whitelist_allowed", False, 0, "true only after paper selector + TCA", 1, "not allowed in Stage295"),
        ]
    )


def _next_actions(product: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"priority": "P0", "product_vt_symbol": "v.DCE", "action": "solve_dce_412_or_use_approved_vendor_snapshot", "reason": "DCE warehouse JSON API is located but automated POST returns 412"},
            {"priority": "P0", "product_vt_symbol": "ao.SHFE", "action": "solve_shfe_stockdata_waf_or_browser_cookie_flow", "reason": "SHFE new dailystock stockdata URL is located but returns WAF in direct requests"},
            {"priority": "P0", "product_vt_symbol": "lu.INE", "action": "wire_ine_query_params_dailystock_weeklystock_with_cookie_or_vendor", "reason": "INE exact UI params are found, but direct data file pattern is unresolved/WAF"},
            {"priority": "P0", "product_vt_symbol": "all", "action": "keep_third_party_inventory_as_monitor_auxiliary_only", "reason": "Stage294 third-party inventory works but cannot be promoted to official alpha evidence"},
        ]
    )


def _decision(frame: pd.DataFrame, product: pd.DataFrame, gates: pd.DataFrame, now_local: datetime, now_utc: datetime) -> dict[str, Any]:
    hard = gates[gates["hard_gate"].eq(1)]
    if bool((product["official_auto_monitor_ready_rows"] > 0).all()):
        label = "p0_official_endpoints_monitor_ready_not_history_selector"
    elif bool((product["official_pages_or_endpoints_located"] > 0).all()):
        label = "p0_official_endpoints_located_access_or_parser_blocked"
    else:
        label = "p0_official_endpoint_discovery_incomplete"
    return {
        "stage": "Stage295",
        "script_stage": "Stage595",
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at_local": now_local.isoformat(timespec="seconds"),
        "generated_at_utc": now_utc.isoformat(timespec="seconds"),
        "decision": label,
        "promotion_allowed": False,
        "paper_selector_allowed": False,
        "trading_whitelist_allowed": False,
        "probe_date": PROBE_DATE,
        "endpoint_rows": int(len(frame)),
        "hard_gates_passed": int(hard["passed"].sum()),
        "hard_gates_total": int(len(hard)),
        "products_with_official_page_or_endpoint": int((product["official_pages_or_endpoints_located"] > 0).sum()),
        "products_with_current_parsed_product_data": int((product["matched_product_rows"] > 0).sum()),
        "products_with_official_auto_monitor_ready": int((product["official_auto_monitor_ready_rows"] > 0).sum()),
        "waf_or_412_rows": int(product["waf_or_412_rows"].sum()),
        "overfit_boundary": "Official endpoint discovery only; no PnL, no selector scores, no whitelist tuning.",
        "next_step": "Resolve WAF/412/cookie or approved vendor route, then collect 20 received_at snapshots before predictive tests.",
    }


def _make_chart(frame: pd.DataFrame, product: pd.DataFrame, gates: pd.DataFrame, decision: dict[str, Any]) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(17, 11))
    fig.suptitle(f"Stage595 official endpoint discovery: {decision['decision']}", fontsize=12)

    ax = axes[0, 0]
    metrics = ["endpoint_located", "data_access_ok", "matched_product", "official_auto_monitor_ready"]
    pivot = (
        frame.groupby("product_vt_symbol")[metrics].max()
        .reindex(index=["v.DCE", "ao.SHFE", "lu.INE"])
        .fillna(0)
    )
    im = ax.imshow(pivot.to_numpy(dtype=float), aspect="auto", cmap="RdYlGn", vmin=0, vmax=1)
    ax.set_title("Endpoint readiness layers")
    ax.set_yticks(np.arange(len(pivot.index)))
    ax.set_yticklabels(pivot.index.tolist())
    ax.set_xticks(np.arange(len(metrics)))
    ax.set_xticklabels(["located", "access", "matched", "monitor"], rotation=25, ha="right")
    for i in range(pivot.shape[0]):
        for j in range(pivot.shape[1]):
            ax.text(j, i, int(pivot.iloc[i, j]), ha="center", va="center", fontsize=9)
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)

    ax = axes[0, 1]
    x = np.arange(len(product))
    ax.bar(x - 0.25, product["official_pages_or_endpoints_located"], width=0.25, label="located")
    ax.bar(x, product["data_access_ok_rows"], width=0.25, label="access ok")
    ax.bar(x + 0.25, product["official_auto_monitor_ready_rows"], width=0.25, label="monitor ready")
    ax.set_title("Product route counts")
    ax.set_xticks(x)
    ax.set_xticklabels(product["product_vt_symbol"].tolist(), rotation=20, ha="right")
    ax.set_ylabel("rows")
    ax.legend(fontsize=8)
    ax.grid(axis="y", alpha=0.25)

    ax = axes[1, 0]
    status = frame.groupby(["product_vt_symbol", "probe_status"]).size().reset_index(name="count")
    products = ["v.DCE", "ao.SHFE", "lu.INE"]
    bottom = np.zeros(len(products))
    for status_name in sorted(status["probe_status"].unique()):
        vals = []
        for product_symbol in products:
            match = status[(status["product_vt_symbol"].eq(product_symbol)) & (status["probe_status"].eq(status_name))]
            vals.append(int(match["count"].iloc[0]) if not match.empty else 0)
        ax.bar(products, vals, bottom=bottom, label=status_name)
        bottom += np.asarray(vals)
    ax.set_title("Probe statuses by product")
    ax.set_xticks(np.arange(len(products)))
    ax.set_xticklabels(products)
    ax.legend(fontsize=7)
    ax.grid(axis="y", alpha=0.25)

    ax = axes[1, 1]
    hard = gates[gates["hard_gate"].eq(1)].copy()
    labels = {
        "all_gap_products_have_exact_official_page_or_endpoint": "located",
        "all_gap_products_have_parsed_current_product_data": "parsed\nproduct",
        "all_gap_products_have_official_auto_monitor_ready": "monitor\nready",
        "no_waf_or_412_on_required_routes": "no WAF\n412",
        "history_selector_disabled": "history\nzero",
        "paper_selector_allowed": "paper\nallowed",
        "trading_whitelist_allowed": "trading\nallowed",
    }
    hard["label"] = hard["gate"].map(labels).fillna(hard["gate"])
    colors = np.where(hard["passed"].eq(1), "#2f855a", "#c53030")
    y = np.arange(len(hard))
    ax.barh(y, hard["passed"], color=colors)
    ax.set_yticks(y)
    ax.set_yticklabels(hard["label"].tolist(), fontsize=8)
    ax.set_xlim(0, 1)
    ax.set_title("Hard gates")
    ax.set_xlabel("pass")
    ax.grid(axis="x", alpha=0.25)

    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(CHART_PATH, dpi=160)
    plt.close(fig)


def _write_report(frame: pd.DataFrame, product: pd.DataFrame, gates: pd.DataFrame, next_actions: pd.DataFrame, decision: dict[str, Any]) -> None:
    lines = [
        "# Stage595 P0 官方 endpoint discovery 审计",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        f"- 决策：`{decision['decision']}`",
        "- 阶段性质：官方 endpoint 定位与访问状态审计；不做收益回测，不修改策略，不生成交易候选。",
        "- 关键纪律：只允许发现/探测 endpoint；`usable_for_history_selector` 全部保持 `0`。",
        "",
        "## Product Readiness",
        "",
        _md_table(product),
        "",
        "## Hard Gates",
        "",
        _md_table(gates[gates["hard_gate"].eq(1)]),
        "",
        "## Endpoint Discovery",
        "",
        _md_table(
            frame[
                [
                    "product_vt_symbol",
                    "route",
                    "endpoint_name",
                    "exact_official_page",
                    "exact_data_endpoint",
                    "http_method",
                    "http_status",
                    "probe_status",
                    "parse_status",
                    "matched_product",
                    "official_auto_monitor_ready",
                    "block_reason",
                    "source_url",
                ]
            ],
            max_rows=80,
        ),
        "",
        "## Next Actions",
        "",
        _md_table(next_actions),
        "",
        "## 判断",
        "",
        "- `v.DCE`：DCE 仓单 JSON API 与官方页面已定位，但当前自动 POST 返回 `412`，不能算 forward monitor ready。",
        "- `ao.SHFE`：SHFE 新旧仓单路径均已定位；旧 DAT 仅历史日期可解析且没有氧化铝，2026 当前旧 DAT `404`，新版 stockdata HTML 返回 WAF。",
        "- `lu.INE`：INE 官方 `dailystock/weeklystock` 页面参数已定位；`kx/js` 日数据可访问并匹配 `lu`，但它们是交易/结算上下文，不是仓单/库存路线；仓单/周库存直接数据文件仍未解析成功。",
        "- 因此 Stage294 的第三方库存只能保留为辅助 forward monitor，不能晋级为官方选品 alpha。",
        "",
        "## 输出文件",
        "",
        f"- endpoint discovery：`{ENDPOINT_DISCOVERY_PATH}`",
        f"- product readiness：`{PRODUCT_READINESS_PATH}`",
        f"- gates：`{GATES_PATH}`",
        f"- next actions：`{NEXT_ACTIONS_PATH}`",
        f"- decision：`{DECISION_PATH}`",
        f"- chart：`{CHART_PATH}`",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    now_local = datetime.now().astimezone()
    now_utc = now_local.astimezone(timezone.utc)
    frame = _discover(now_local, now_utc)
    product = _product_readiness(frame)
    gates = _gates(frame, product)
    next_actions = _next_actions(product)
    decision = _decision(frame, product, gates, now_local, now_utc)

    frame.to_csv(ENDPOINT_DISCOVERY_PATH, index=False, encoding="utf-8-sig")
    product.to_csv(PRODUCT_READINESS_PATH, index=False, encoding="utf-8-sig")
    gates.to_csv(GATES_PATH, index=False, encoding="utf-8-sig")
    next_actions.to_csv(NEXT_ACTIONS_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_report(frame, product, gates, next_actions, decision)
    _make_chart(frame, product, gates, decision)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
