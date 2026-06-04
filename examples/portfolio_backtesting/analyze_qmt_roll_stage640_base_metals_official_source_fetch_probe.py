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
MODEL_TAG = "stage640_base_metals_official_source_fetch_probe_v1"
OUTPUT_PREFIX = "qmt_roll_stage640_base_metals_official_source_fetch_probe"

FETCH_LEDGER_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_fetch_ledger_{MODEL_TAG}.csv"
ROUTE_STATUS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_route_status_{MODEL_TAG}.csv"
SOURCE_READINESS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_source_readiness_{MODEL_TAG}.csv"
GATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gates_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

TIMEOUT_SECONDS = 18
MIN_RESPONSE_BYTES = 500
REQUIRED_PIT_DATES_FOR_SELECTOR = 20
PROBE_DATE = os.environ.get("STAGE640_PROBE_DATE", "20260603")
LEGACY_SHFE_DATE = "20200702"

REFERENCES = [
    "LME stock movement report: https://www.lme.com/market-data/reports-and-data/warehouse-and-stocks-reports/stocks-summary/stock-movement-report",
    "LME historical warehouse stock movements PDF: https://www.lme.com/-/media/files/data/accessing-market-data/historical-data/lme-warehouse--stock-movements.pdf",
    "LME market data services agreement: https://datalicensing.lme.com/LinkClick.aspx?fileticket=UFrs0Huks4Y%3D&portalid=0",
    "SHFE Daily Data: https://www.shfe.cn/eng/reports/StatisticalData/DailyData/",
    "SHFE dailystock UI: https://www.shfe.com.cn/reports/tradedata/dailyandweeklydata/?query_params=dailystock",
]

FETCH_TARGETS = [
    {
        "route_id": "lme_stock_movement_page",
        "product_vt_symbol": "base_metals.LME",
        "source_name": "LME stock movement report page",
        "source_url": "https://www.lme.com/market-data/reports-and-data/warehouse-and-stocks-reports/stocks-summary/stock-movement-report",
        "source_authority": "official_public_lme",
        "route_role": "official_stock_report_page",
        "monitor_frequency": "daily_public_page_or_login_report",
        "payload_expected": 0,
        "keywords": ["daily warehouse stock", "opening", "closing stock", "cancelled", "metric tonnes"],
        "product_keywords": ["aluminium", "copper", "zinc", "nickel", "lead", "tin"],
        "point_in_time_rule": "Page/hash evidence only; LME daily report data may require login or licensed distributor.",
    },
    {
        "route_id": "lme_historical_stock_movements_pdf",
        "product_vt_symbol": "base_metals.LME",
        "source_name": "LME warehouse stock movements methodology PDF",
        "source_url": "https://www.lme.com/-/media/files/data/accessing-market-data/historical-data/lme-warehouse--stock-movements.pdf",
        "source_authority": "official_public_lme",
        "route_role": "official_methodology_pdf",
        "monitor_frequency": "static_methodology",
        "payload_expected": 0,
        "keywords": ["Warehouse Stock Movements", "4.30 pm", "9.00 am", "LME approved warehouses"],
        "product_keywords": ["LME", "warehouse", "stock"],
        "point_in_time_rule": "Methodology/hash evidence only; not a tradable signal.",
    },
    {
        "route_id": "shfe_daily_data_english_page",
        "product_vt_symbol": "ao.SHFE",
        "source_name": "SHFE Daily Data English page",
        "source_url": "https://www.shfe.cn/eng/reports/StatisticalData/DailyData/",
        "source_authority": "official_public_exchange",
        "route_role": "official_daily_data_page",
        "monitor_frequency": "daily",
        "payload_expected": 0,
        "keywords": ["Daily Warrant", "Daily Ranking", "Warehouse", "SHFE"],
        "product_keywords": ["aluminium", "copper", "zinc", "AO", "warrant"],
        "point_in_time_rule": "Page/hash evidence only; exact product payload must be validated separately.",
    },
    {
        "route_id": "shfe_dailystock_ui",
        "product_vt_symbol": "ao.SHFE",
        "source_name": "SHFE dailystock UI",
        "source_url": "https://www.shfe.com.cn/reports/tradedata/dailyandweeklydata/?query_params=dailystock",
        "source_authority": "official_public_exchange",
        "route_role": "official_dailystock_ui",
        "monitor_frequency": "daily",
        "payload_expected": 0,
        "keywords": ["仓单日报", "氧化铝", "铜", "铝"],
        "product_keywords": ["氧化铝", "铜", "铝", "AO"],
        "point_in_time_rule": "UI page/hash evidence only; direct requests may hit WAF.",
    },
    {
        "route_id": "shfe_current_dailystock_dat",
        "product_vt_symbol": "ao.SHFE",
        "source_name": "SHFE current dailystock DAT",
        "source_url": f"https://www.shfe.com.cn/data/tradedata/future/dailydata/{PROBE_DATE}dailystock.dat",
        "source_authority": "official_public_exchange",
        "route_role": "official_current_payload_guess",
        "monitor_frequency": "daily",
        "payload_expected": 1,
        "keywords": ["VARNAME", "氧化铝", "铜", "铝"],
        "product_keywords": ["氧化铝", "铜", "铝", "AO"],
        "point_in_time_rule": f"Stage-scoped current payload probe for {PROBE_DATE}; do not backfill selector.",
    },
    {
        "route_id": "shfe_current_stockdata_html",
        "product_vt_symbol": "ao.SHFE",
        "source_name": "SHFE current stockdata HTML",
        "source_url": f"https://www.shfe.com.cn/data/tradedata/future/stockdata/dailystock_{PROBE_DATE}/ZH/all.html",
        "source_authority": "official_public_exchange",
        "route_role": "official_current_payload_guess",
        "monitor_frequency": "daily",
        "payload_expected": 1,
        "keywords": ["氧化铝", "铜", "铝", "仓单"],
        "product_keywords": ["氧化铝", "铜", "铝", "AO"],
        "point_in_time_rule": f"Stage-scoped current payload probe for {PROBE_DATE}; do not backfill selector.",
    },
    {
        "route_id": "shfe_legacy_dailystock_dat_known_ok",
        "product_vt_symbol": "ao.SHFE",
        "source_name": "SHFE legacy dailystock DAT known historical date",
        "source_url": f"https://www.shfe.com.cn/data/tradedata/future/dailydata/{LEGACY_SHFE_DATE}dailystock.dat",
        "source_authority": "official_public_exchange",
        "route_role": "official_legacy_payload_reference",
        "monitor_frequency": "static_legacy_reference",
        "payload_expected": 1,
        "keywords": ["VARNAME", "氧化铝", "铜", "铝"],
        "product_keywords": ["氧化铝", "铜", "铝", "AO"],
        "point_in_time_rule": "Legacy route shape reference only; not current forward data.",
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


def _decode_body(body: bytes, content_type: str) -> str:
    charset_match = re.search(r"charset=([^;\s]+)", content_type, flags=re.I)
    charsets = [charset_match.group(1)] if charset_match else []
    charsets.extend(["utf-8", "gb18030", "gbk", "latin1"])
    for charset in charsets:
        try:
            return body.decode(charset, errors="strict")
        except UnicodeError:
            continue
    return body.decode("utf-8", errors="replace")


def _clean_text(text: str) -> str:
    text = re.sub(r"<script\b[^>]*>.*?</script>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<style\b[^>]*>.*?</style>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _looks_like_waf(text: str) -> bool:
    markers = ["WEB 应用防火墙", "captcha", "人机识别", "向右滑动填充拼图", "Forbidden"]
    return any(marker.lower() in text.lower() for marker in markers)


def _fetch_url(url: str) -> dict[str, Any]:
    headers = {
        "User-Agent": "Mozilla/5.0 stage640-base-metals-source-probe/1.0",
        "Accept": "text/html,text/plain,application/json,application/pdf,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }
    request = Request(url, headers=headers)
    started = datetime.now(timezone.utc)
    try:
        context = ssl.create_default_context()
        with urlopen(request, timeout=TIMEOUT_SECONDS, context=context) as response:
            body = response.read(4_000_000)
            content_type = response.headers.get("content-type", "")
            text = _decode_body(body, content_type)
            return {
                "fetch_status": "ok",
                "http_status": int(getattr(response, "status", 200)),
                "final_url": response.geturl(),
                "content_type": content_type,
                "response_bytes": len(body),
                "elapsed_ms": round((datetime.now(timezone.utc) - started).total_seconds() * 1000, 1),
                "raw_sha256": hashlib.sha256(body).hexdigest() if body else "",
                "text": text,
                "fetch_error": "",
            }
    except HTTPError as error:
        body = error.read(500_000)
        content_type = error.headers.get("content-type", "") if error.headers else ""
        text = _decode_body(body, content_type) if body else ""
        return {
            "fetch_status": "waf_or_http_error" if _looks_like_waf(text) else "http_error",
            "http_status": int(error.code),
            "final_url": url,
            "content_type": content_type,
            "response_bytes": len(body),
            "elapsed_ms": round((datetime.now(timezone.utc) - started).total_seconds() * 1000, 1),
            "raw_sha256": hashlib.sha256(body).hexdigest() if body else "",
            "text": text,
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
            "raw_sha256": "",
            "text": "",
            "fetch_error": repr(error),
        }


def _keyword_hits(text: str, keywords: list[str]) -> tuple[int, str]:
    lower = text.lower()
    hits = [keyword for keyword in keywords if keyword.lower() in lower]
    return len(hits), ",".join(hits)


def _parse_json_like_payload(text: str) -> dict[str, Any]:
    try:
        data = json.loads(text)
    except Exception:
        return {"json_parse_ok": 0, "matched_payload_rows": 0, "sample_json": "{}"}
    rows: list[Any] = []
    if isinstance(data, dict):
        for key in ["o_cursor", "o_curinstrument", "data", "result"]:
            value = data.get(key)
            if isinstance(value, list):
                rows = value
                break
    matched = [
        row
        for row in rows
        if any(keyword in json.dumps(_json_safe(row), ensure_ascii=False) for keyword in ["氧化铝", "铜", "铝", "AO"])
    ]
    sample = matched[:5] if matched else rows[:5]
    return {
        "json_parse_ok": int(isinstance(data, dict)),
        "matched_payload_rows": len(matched),
        "sample_json": json.dumps(_json_safe(sample), ensure_ascii=False, sort_keys=True),
    }


def build_fetch_ledger(generated_at: datetime) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    run_id = f"{MODEL_TAG}_{generated_at.strftime('%Y%m%d_%H%M%S')}"
    received_at_local = _fmt_cst(generated_at)
    received_at_utc = generated_at.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for index, target in enumerate(FETCH_TARGETS, start=1):
        result = _fetch_url(str(target["source_url"]))
        clean = _clean_text(str(result["text"]))
        waf_like = int(_looks_like_waf(clean))
        keyword_count, keyword_hits = _keyword_hits(clean, list(target["keywords"]))
        product_count, product_hits = _keyword_hits(clean, list(target["product_keywords"]))
        parsed = _parse_json_like_payload(str(result["text"]))
        page_fetch_validated = int(
            result["fetch_status"] == "ok"
            and int(result["http_status"]) == 200
            and int(result["response_bytes"]) >= MIN_RESPONSE_BYTES
            and bool(result["raw_sha256"])
            and waf_like == 0
            and keyword_count >= 1
        )
        payload_data_validated = int(
            page_fetch_validated
            and int(target["payload_expected"]) == 1
            and (product_count >= 1 or int(parsed["matched_payload_rows"]) > 0)
        )
        rows.append(
            {
                "run_id": run_id,
                "row_id": f"stage640_{index:03d}",
                "received_at_local": received_at_local,
                "received_at_utc": received_at_utc,
                "line_id": LINE_ID,
                "route_id": target["route_id"],
                "product_vt_symbol": target["product_vt_symbol"],
                "product_family": "base_metals",
                "source_name": target["source_name"],
                "source_url": target["source_url"],
                "final_url": result["final_url"],
                "source_authority": target["source_authority"],
                "route_role": target["route_role"],
                "monitor_frequency": target["monitor_frequency"],
                "payload_expected": int(target["payload_expected"]),
                "http_status": int(result["http_status"]),
                "fetch_status": result["fetch_status"],
                "fetch_error": result["fetch_error"],
                "content_type": result["content_type"],
                "response_bytes": int(result["response_bytes"]),
                "elapsed_ms": float(result["elapsed_ms"]),
                "raw_sha256": result["raw_sha256"],
                "raw_sha256_present": int(bool(result["raw_sha256"])),
                "waf_like": waf_like,
                "keyword_hit_count": keyword_count,
                "keyword_hits": keyword_hits,
                "product_hit_count": product_count,
                "product_hits": product_hits,
                "json_parse_ok": int(parsed["json_parse_ok"]),
                "matched_payload_rows": int(parsed["matched_payload_rows"]),
                "sample_value_json": parsed["sample_json"],
                "page_fetch_validated": page_fetch_validated,
                "payload_data_validated": payload_data_validated,
                "active_fetch_validated": page_fetch_validated,
                "usable_for_forward_monitor": payload_data_validated,
                "usable_for_history_selector": 0,
                "event_signal_ready": 0,
                "paper_or_whitelist_allowed": 0,
                "raw_text_excerpt": clean[:280],
                "point_in_time_rule": target["point_in_time_rule"],
                "notes": "Stage-scoped base_metals source probe only; no master append and no selector.",
            }
        )
    return pd.DataFrame(rows)


def build_route_status(ledger: pd.DataFrame) -> pd.DataFrame:
    return ledger.groupby(["source_authority", "route_role"], as_index=False).agg(
        rows=("row_id", "count"),
        page_fetch_validated_rows=("page_fetch_validated", "sum"),
        payload_expected_rows=("payload_expected", "sum"),
        payload_data_validated_rows=("payload_data_validated", "sum"),
        raw_hash_rows=("raw_sha256_present", "sum"),
        waf_like_rows=("waf_like", "sum"),
        min_keyword_hits=("keyword_hit_count", "min"),
        total_bytes=("response_bytes", "sum"),
    )


def build_source_readiness(ledger: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for source_authority, group in ledger.groupby("source_authority"):
        page_ok = int(group["page_fetch_validated"].sum())
        payload_ok = int(group["payload_data_validated"].sum())
        payload_expected = int(group["payload_expected"].sum())
        rows.append(
            {
                "product_family": "base_metals",
                "source_authority": source_authority,
                "source_rows": int(len(group)),
                "page_fetch_validated_rows": page_ok,
                "payload_expected_rows": payload_expected,
                "payload_data_validated_rows": payload_ok,
                "raw_hash_rows": int(group["raw_sha256_present"].sum()),
                "waf_like_rows": int(group["waf_like"].sum()),
                "pit_received_dates": int(group["received_at_local"].nunique()),
                "history_selector_rows": int(group["usable_for_history_selector"].sum()),
                "paper_or_whitelist_rows": int(group["paper_or_whitelist_allowed"].sum()),
                "readiness": _readiness_label(source_authority, page_ok, payload_ok, payload_expected),
                "promotion_allowed": 0,
                "paper_allowed": 0,
                "trading_whitelist_allowed": 0,
            }
        )
    return pd.DataFrame(rows)


def _readiness_label(source_authority: str, page_ok: int, payload_ok: int, payload_expected: int) -> str:
    if payload_expected > 0 and payload_ok > 0:
        return "stage_scoped_payload_validated_selector_locked"
    if page_ok > 0:
        return "page_hash_validated_payload_not_ready"
    if source_authority == "official_public_lme":
        return "lme_route_not_validated_or_license_blocked"
    return "route_not_validated_or_waf_blocked"


def build_gates(ledger: pd.DataFrame, source_readiness: pd.DataFrame) -> pd.DataFrame:
    page_ok = int(ledger["page_fetch_validated"].sum())
    payload_ok = int(ledger["payload_data_validated"].sum())
    raw_hash = int(ledger["raw_sha256_present"].sum())
    waf_rows = int(ledger["waf_like"].sum())
    selector_rows = int(ledger["usable_for_history_selector"].sum() + ledger["event_signal_ready"].sum())
    whitelist_rows = int(ledger["paper_or_whitelist_allowed"].sum())
    pit_dates = int(source_readiness["pit_received_dates"].max()) if not source_readiness.empty else 0
    rows = [
        {
            "gate": "base_metals_official_sources_touched",
            "passed": int(ledger["source_authority"].nunique() >= 2),
            "current": int(ledger["source_authority"].nunique()),
            "required": ">=2",
            "note": "LME and SHFE official routes should both be probed.",
        },
        {
            "gate": "page_hash_rows_present",
            "passed": int(raw_hash >= 2),
            "current": raw_hash,
            "required": ">=2",
            "note": "Fetched routes should store raw_sha256 evidence.",
        },
        {
            "gate": "active_page_fetch_validated_rows",
            "passed": int(page_ok >= 2),
            "current": page_ok,
            "required": ">=2",
            "note": "Official source pages or methodology routes need live page/hash validation.",
        },
        {
            "gate": "payload_data_validated_rows",
            "passed": int(payload_ok >= 1),
            "current": payload_ok,
            "required": ">=1",
            "note": "At least one exact current or legacy data payload should contain base-metal product context.",
        },
        {
            "gate": "waf_like_rows_zero",
            "passed": int(waf_rows == 0),
            "current": waf_rows,
            "required": 0,
            "note": "WAF/captcha-like responses cannot be used by automation.",
        },
        {
            "gate": "pit_dates_below_selector_threshold",
            "passed": int(pit_dates < REQUIRED_PIT_DATES_FOR_SELECTOR),
            "current": pit_dates,
            "required": f"<{REQUIRED_PIT_DATES_FOR_SELECTOR}",
            "note": "One received_at date must remain selector-locked.",
        },
        {
            "gate": "selector_rows_zero",
            "passed": int(selector_rows == 0),
            "current": selector_rows,
            "required": 0,
            "note": "No history selector or event signal is generated.",
        },
        {
            "gate": "paper_whitelist_zero",
            "passed": int(whitelist_rows == 0),
            "current": whitelist_rows,
            "required": 0,
            "note": "Source probe cannot create paper or trading whitelist.",
        },
        {
            "gate": "master_append_zero_stage_scoped",
            "passed": 1,
            "current": 0,
            "required": 0,
            "note": "This stage writes scoped outputs only; master append requires a later gate.",
        },
    ]
    return pd.DataFrame(rows)


def build_decision(generated_at: datetime, ledger: pd.DataFrame, source_readiness: pd.DataFrame, gates: pd.DataFrame) -> dict[str, Any]:
    page_ok = int(ledger["page_fetch_validated"].sum())
    payload_ok = int(ledger["payload_data_validated"].sum())
    if payload_ok >= 1 and page_ok >= 2:
        decision = "base_metals_official_payload_probe_partial_selector_locked"
    elif page_ok >= 2:
        decision = "base_metals_official_pages_hash_ready_payload_blocked_selector_locked"
    else:
        decision = "base_metals_official_source_fetch_incomplete_selector_locked"
    return {
        "model_tag": MODEL_TAG,
        "decision": decision,
        "generated_at_cst": _fmt_cst(generated_at),
        "line_id": LINE_ID,
        "probe_date": PROBE_DATE,
        "fetch_rows": int(len(ledger)),
        "source_authorities": int(ledger["source_authority"].nunique()),
        "active_page_fetch_validated_rows": page_ok,
        "payload_data_validated_rows": payload_ok,
        "raw_hash_rows": int(ledger["raw_sha256_present"].sum()),
        "waf_like_rows": int(ledger["waf_like"].sum()),
        "pit_dates_now": int(source_readiness["pit_received_dates"].max()) if not source_readiness.empty else 0,
        "selector_rows": int(ledger["usable_for_history_selector"].sum() + ledger["event_signal_ready"].sum()),
        "paper_or_whitelist_rows": int(ledger["paper_or_whitelist_allowed"].sum()),
        "promotion_allowed": 0,
        "paper_allowed": 0,
        "trading_whitelist_allowed": 0,
        "hard_gates_passed": int(gates["passed"].sum()),
        "hard_gates_total": int(len(gates)),
        "fetch_ledger_path": str(FETCH_LEDGER_PATH),
        "route_status_path": str(ROUTE_STATUS_PATH),
        "source_readiness_path": str(SOURCE_READINESS_PATH),
        "chart_path": str(CHART_PATH),
    }


def write_chart(ledger: pd.DataFrame, source_readiness: pd.DataFrame, gates: pd.DataFrame, decision: dict[str, Any]) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(17, 10))
    fig.suptitle("Stage640 base metals official source probe: source evidence first, selector locked", fontsize=15)

    ax = axes[0, 0]
    plot = ledger[["route_id", "raw_sha256_present", "page_fetch_validated", "payload_data_validated", "waf_like"]].copy()
    plot["no_waf"] = 1 - plot["waf_like"].astype(int)
    metrics = ["raw_sha256_present", "page_fetch_validated", "payload_data_validated", "no_waf"]
    plot = plot[["route_id", *metrics]].set_index("route_id")
    image = ax.imshow(plot.values.astype(float), aspect="auto", cmap="RdYlGn", vmin=0, vmax=1)
    ax.set_title("Route validation layers")
    ax.set_xticks(np.arange(len(metrics)))
    ax.set_xticklabels(["hash", "page ok", "payload ok", "no WAF"], rotation=20, ha="right")
    ax.set_yticks(np.arange(len(plot.index)))
    ax.set_yticklabels(plot.index.tolist(), fontsize=8)
    for i in range(plot.shape[0]):
        for j in range(plot.shape[1]):
            ax.text(j, i, str(int(plot.iloc[i, j])), ha="center", va="center", fontsize=8)
    fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04)

    ax = axes[0, 1]
    by_source = ledger.groupby("source_authority").agg(
        page=("page_fetch_validated", "sum"),
        payload=("payload_data_validated", "sum"),
        waf=("waf_like", "sum"),
    )
    x = np.arange(len(by_source.index))
    ax.bar(x - 0.22, by_source["page"], width=0.22, label="page ok", color="#3182ce")
    ax.bar(x, by_source["payload"], width=0.22, label="payload ok", color="#dd6b20")
    ax.bar(x + 0.22, by_source["waf"], width=0.22, label="WAF-like", color="#e53e3e")
    ax.set_xticks(x)
    ax.set_xticklabels(by_source.index.tolist(), rotation=15, ha="right")
    ax.set_title("LME vs SHFE route readiness")
    ax.set_ylabel("rows")
    ax.legend(fontsize=8)
    ax.grid(axis="y", alpha=0.25)

    ax = axes[1, 0]
    if source_readiness.empty:
        ax.text(0.5, 0.5, "No source readiness", ha="center", va="center")
        ax.set_axis_off()
    else:
        status_plot = source_readiness.set_index("source_authority")[
            ["page_fetch_validated_rows", "payload_data_validated_rows", "pit_received_dates", "history_selector_rows", "paper_or_whitelist_rows"]
        ]
        status_plot.plot(kind="bar", ax=ax)
        ax.axhline(REQUIRED_PIT_DATES_FOR_SELECTOR, color="tab:red", linestyle="--", linewidth=1, label="selector PIT threshold")
        ax.set_title("Source readiness: PIT depth and selector locks")
        ax.set_ylabel("rows / dates")
        ax.tick_params(axis="x", rotation=15)
        ax.legend(loc="upper right", fontsize=8)

    ax = axes[1, 1]
    colors = ["tab:green" if int(item) == 1 else "tab:red" for item in gates["passed"]]
    ax.barh(gates["gate"], [1] * len(gates), color=colors)
    ax.set_xlim(0, 1)
    ax.set_title("Hard gates: green includes fail-closed locks")
    ax.tick_params(axis="y", labelsize=8)
    for i, row in gates.iterrows():
        label = f"{'PASS' if int(row['passed']) else 'FAIL'} {row['current']}"
        ax.text(0.02, i, label, va="center", ha="left", fontsize=8, color="white", fontweight="bold")

    fig.tight_layout(rect=(0, 0, 1, 0.94))
    fig.savefig(CHART_PATH, dpi=180)
    plt.close(fig)


def write_report(
    generated_at: datetime,
    ledger: pd.DataFrame,
    route_status: pd.DataFrame,
    source_readiness: pd.DataFrame,
    gates: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    interpretation = [
        "- `base_metals` 的官方 source 路线可以被拆成 LME 全球库存语义和 SHFE 国内仓单/日数据语义。",
        "- LME 官方页面说明库存数据的发布时间、计量单位和 on/cancelled warrant 结构，但完整日度数据访问可能依赖登录、授权或 licensed data distributor。",
        "- SHFE 更贴近国内合约，但直接脚本访问可能遇到 WAF 或当前端点模式变化；因此不能把页面可达误读为 payload 可用。",
        "- 本阶段只验证 source 可达性和 hash/PIT 纪律，不能进入 selector、paper、A/B 或白名单。",
    ]
    lines = [
        "# Stage640 Base Metals Official Source Fetch Probe Report",
        "",
        f"- line_id: `{LINE_ID}`",
        f"- generated_at_cst: `{_fmt_cst(generated_at)}`",
        f"- decision: `{decision['decision']}`",
        "- stage nature: base_metals official source fetch probe; stage-scoped only; no master append, no strategy replay, no selector, no paper, no whitelist, no CTP.",
        "",
        "## External Research And Judgement",
        "",
        "References:",
        *[f"- {item}" for item in REFERENCES],
        "",
        "Judgement:",
        *interpretation,
        "",
        "## Key Numbers",
        "",
        f"- fetch rows: `{decision['fetch_rows']}`",
        f"- source authorities: `{decision['source_authorities']}`",
        f"- active page fetch validated rows: `{decision['active_page_fetch_validated_rows']}`",
        f"- payload data validated rows: `{decision['payload_data_validated_rows']}`",
        f"- raw hash rows: `{decision['raw_hash_rows']}`",
        f"- WAF-like rows: `{decision['waf_like_rows']}`",
        f"- PIT dates now: `{decision['pit_dates_now']}`",
        f"- selector rows: `{decision['selector_rows']}`",
        f"- paper/whitelist rows: `{decision['paper_or_whitelist_rows']}`",
        f"- hard gates: `{decision['hard_gates_passed']}/{decision['hard_gates_total']}`",
        "",
        "## Fetch Ledger",
        "",
        _md_table(
            ledger,
            columns=[
                "route_id",
                "source_authority",
                "route_role",
                "http_status",
                "fetch_status",
                "response_bytes",
                "raw_sha256_present",
                "waf_like",
                "keyword_hit_count",
                "keyword_hits",
                "product_hit_count",
                "product_hits",
                "json_parse_ok",
                "matched_payload_rows",
                "page_fetch_validated",
                "payload_data_validated",
                "usable_for_history_selector",
                "paper_or_whitelist_allowed",
            ],
        ),
        "",
        "## Route Status",
        "",
        _md_table(route_status),
        "",
        "## Source Readiness",
        "",
        _md_table(source_readiness),
        "",
        "## Gates",
        "",
        _md_table(gates),
        "",
        "## Interpretation",
        "",
        *interpretation,
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    generated_at = _now_cst()
    ledger = build_fetch_ledger(generated_at)
    route_status = build_route_status(ledger)
    source_readiness = build_source_readiness(ledger)
    gates = build_gates(ledger, source_readiness)
    decision = build_decision(generated_at, ledger, source_readiness, gates)

    ledger.to_csv(FETCH_LEDGER_PATH, index=False, encoding="utf-8-sig")
    route_status.to_csv(ROUTE_STATUS_PATH, index=False, encoding="utf-8-sig")
    source_readiness.to_csv(SOURCE_READINESS_PATH, index=False, encoding="utf-8-sig")
    gates.to_csv(GATES_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    write_chart(ledger, source_readiness, gates, decision)
    write_report(generated_at, ledger, route_status, source_readiness, gates, decision)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
