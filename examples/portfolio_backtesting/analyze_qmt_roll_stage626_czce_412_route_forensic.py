from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import html
import http.cookiejar
import json
import math
import os
from pathlib import Path
import re
import socket
import ssl
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import HTTPCookieProcessor, Request, build_opener


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
os.environ.setdefault("MPLCONFIGDIR", str(OUTPUT_DIR / ".matplotlib"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


LINE_ID = "futures_trend_drawdown30_preserve_return"
MODEL_TAG = "stage626_czce_412_route_forensic_v1"
OUTPUT_PREFIX = "qmt_roll_stage626_czce_412_route_forensic"

PROBE_LEDGER_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_probe_ledger_{MODEL_TAG}.csv"
TARGET_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_target_summary_{MODEL_TAG}.csv"
STRATEGY_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_strategy_summary_{MODEL_TAG}.csv"
GATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gates_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

TIMEOUT_SECONDS = 15
MIN_RESPONSE_BYTES = 500
MIN_KEYWORD_HITS = 1

REFERENCES = [
    "CZCE home page: https://www.czce.com.cn/",
    "CZCE English reference data example: https://english.czce.com.cn/en/DFSStaticFiles/Future/2024/20240418/EnglishFutureDataReferenceData.htm",
    "CZCE position ranking page: https://www.czce.com.cn/cn/jysj/ccpm/H077003004index_1.htm",
    "CZCE warehouse receipt page: https://www.czce.com.cn/cn/jysj/cdrb/H077003010index_1.htm",
    "MDN 412 explanation: https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/412",
]

TARGETS = [
    {
        "target_id": "english_ref_20240418",
        "product_vt_symbol": "SR.CZCE",
        "target_group": "official_static_reference",
        "source_url": "https://english.czce.com.cn/en/DFSStaticFiles/Future/2024/20240418/EnglishFutureDataReferenceData.htm",
        "expected_keywords": ["White Sugar", "SR", "Futures", "ZCE"],
        "warmup_group": "english",
        "route": "contract_reference",
    },
    {
        "target_id": "english_ref_20231229",
        "product_vt_symbol": "CY.CZCE",
        "target_group": "official_static_reference",
        "source_url": "https://english.czce.com.cn/en/DFSStaticFiles/Future/2023/20231229/EnglishFutureDataReferenceData.htm",
        "expected_keywords": ["Cotton Yarn", "CY", "Futures", "ZCE"],
        "warmup_group": "english",
        "route": "contract_reference",
    },
    {
        "target_id": "cn_holding_20240102",
        "product_vt_symbol": "CY.CZCE,SR.CZCE",
        "target_group": "position_rank_static_file",
        "source_url": "https://www.czce.com.cn/cn/DFSStaticFiles/Future/2024/20240102/FutureDataHolding.htm",
        "expected_keywords": ["持仓排名", "白糖", "棉纱", "郑州商品交易所"],
        "warmup_group": "cn_position",
        "route": "member_detail",
    },
    {
        "target_id": "cn_holding_20240418",
        "product_vt_symbol": "CY.CZCE,SR.CZCE",
        "target_group": "position_rank_static_file",
        "source_url": "https://www.czce.com.cn/cn/DFSStaticFiles/Future/2024/20240418/FutureDataHolding.htm",
        "expected_keywords": ["持仓排名", "白糖", "棉纱", "郑州商品交易所"],
        "warmup_group": "cn_position",
        "route": "member_detail",
    },
    {
        "target_id": "cn_warehouse_20240418",
        "product_vt_symbol": "CY.CZCE,SR.CZCE",
        "target_group": "warehouse_static_file",
        "source_url": "https://www.czce.com.cn/cn/DFSStaticFiles/Future/2024/20240418/FutureDataWhsheet.xlsx",
        "expected_keywords": ["", "xlsx"],
        "warmup_group": "cn_warehouse",
        "route": "warehouse",
    },
    {
        "target_id": "cn_warehouse_http_20240418",
        "product_vt_symbol": "CY.CZCE,SR.CZCE",
        "target_group": "warehouse_static_file",
        "source_url": "http://www.czce.com.cn/cn/DFSStaticFiles/Future/2024/20240418/FutureDataWhsheet.xlsx",
        "expected_keywords": ["", "xlsx"],
        "warmup_group": "cn_warehouse",
        "route": "warehouse",
    },
]

WARMUP_URLS = {
    "english": [
        "https://english.czce.com.cn/en/",
        "https://english.czce.com.cn/en/AboutUs/Overview/Overview/H081001001003index_1.htm",
    ],
    "cn_position": [
        "https://www.czce.com.cn/",
        "https://www.czce.com.cn/cn/jysj/ccpm/H077003004index_1.htm",
    ],
    "cn_warehouse": [
        "https://www.czce.com.cn/",
        "https://www.czce.com.cn/cn/jysj/cdrb/H077003010index_1.htm",
    ],
}

HEADER_VARIANTS = {
    "minimal": {
        "User-Agent": "stage626-czce-route-forensic/1.0",
        "Accept": "*/*",
    },
    "chrome_en": {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8",
    },
    "chrome_zh": {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.7",
    },
    "chrome_download": {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Accept": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/octet-stream,text/html,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.7",
    },
}

PROBE_STRATEGIES = [
    {"strategy_id": "direct_minimal", "header_variant": "minimal", "warmup": False, "referer": ""},
    {"strategy_id": "direct_chrome_en", "header_variant": "chrome_en", "warmup": False, "referer": ""},
    {"strategy_id": "direct_chrome_zh", "header_variant": "chrome_zh", "warmup": False, "referer": ""},
    {"strategy_id": "referer_home_chrome", "header_variant": "chrome_zh", "warmup": False, "referer": "home"},
    {"strategy_id": "referer_listing_chrome", "header_variant": "chrome_zh", "warmup": False, "referer": "listing"},
    {"strategy_id": "warmup_then_target", "header_variant": "chrome_zh", "warmup": True, "referer": "listing"},
    {"strategy_id": "download_accept_warmup", "header_variant": "chrome_download", "warmup": True, "referer": "listing"},
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


def _clean_text(text: str) -> str:
    text = re.sub(r"<script\b[^>]*>.*?</script>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<style\b[^>]*>.*?</style>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _fetch(opener: Any, url: str, headers: dict[str, str]) -> dict[str, Any]:
    request = Request(url, headers=headers)
    started = datetime.now(timezone.utc)
    try:
        context = ssl.create_default_context()
        # urlopen opener does not accept context directly after build_opener; HTTPSHandler is enough here.
        del context
        with opener.open(request, timeout=TIMEOUT_SECONDS) as response:
            body = response.read(2_000_000)
            content_type = response.headers.get("content-type", "")
            text = _decode_body(body, content_type)
            return {
                "status": "ok",
                "http_status": int(getattr(response, "status", 200)),
                "final_url": response.geturl(),
                "content_type": content_type,
                "response_bytes": len(body),
                "elapsed_ms": round((datetime.now(timezone.utc) - started).total_seconds() * 1000, 1),
                "raw_sha256": hashlib.sha256(body).hexdigest() if body else "",
                "text": text,
                "error": "",
            }
    except HTTPError as error:
        body = b""
        text = ""
        try:
            body = error.read(200_000)
            text = _decode_body(body, error.headers.get("content-type", ""))
        except Exception:
            pass
        return {
            "status": "http_error",
            "http_status": int(error.code),
            "final_url": url,
            "content_type": error.headers.get("content-type", "") if hasattr(error, "headers") else "",
            "response_bytes": len(body),
            "elapsed_ms": round((datetime.now(timezone.utc) - started).total_seconds() * 1000, 1),
            "raw_sha256": hashlib.sha256(body).hexdigest() if body else "",
            "text": text,
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
            "raw_sha256": "",
            "text": "",
            "error": str(error),
        }


def _keyword_hits(text: str, keywords: list[str]) -> tuple[int, str]:
    if not keywords:
        return 0, ""
    clean = _clean_text(text).lower()
    hits = [keyword for keyword in keywords if keyword and keyword.lower() in clean]
    return len(hits), ",".join(hits)


def _referer_for(target: dict[str, Any], referer_mode: str) -> str:
    if referer_mode == "home":
        return "https://english.czce.com.cn/en/" if target["warmup_group"] == "english" else "https://www.czce.com.cn/"
    if referer_mode == "listing":
        warmups = WARMUP_URLS.get(str(target["warmup_group"]), [])
        return warmups[-1] if warmups else ""
    return ""


def _probe_one(target: dict[str, Any], strategy: dict[str, Any], received_at: datetime) -> dict[str, Any]:
    cookie_jar = http.cookiejar.CookieJar()
    opener = build_opener(HTTPCookieProcessor(cookie_jar))
    headers = dict(HEADER_VARIANTS[str(strategy["header_variant"])])
    referer = _referer_for(target, str(strategy["referer"]))
    warmup_statuses: list[str] = []
    warmup_bytes = 0
    if bool(strategy["warmup"]):
        for warmup_url in WARMUP_URLS.get(str(target["warmup_group"]), []):
            warmup_headers = dict(headers)
            if warmup_statuses:
                warmup_headers["Referer"] = WARMUP_URLS[str(target["warmup_group"])][0]
            warmup_result = _fetch(opener, warmup_url, warmup_headers)
            warmup_statuses.append(f"{warmup_result['http_status']}:{warmup_result['status']}")
            warmup_bytes += int(warmup_result["response_bytes"])
    target_headers = dict(headers)
    if referer:
        target_headers["Referer"] = referer
    result = _fetch(opener, str(target["source_url"]), target_headers)
    keyword_count, keyword_hits = _keyword_hits(str(result["text"]), list(target["expected_keywords"]))
    content_type = str(result["content_type"]).lower()
    is_binary_xlsx = str(target["source_url"]).lower().endswith(".xlsx") and int(result["response_bytes"]) >= MIN_RESPONSE_BYTES
    content_match = int(keyword_count >= MIN_KEYWORD_HITS or is_binary_xlsx)
    route_ready = int(result["status"] == "ok" and int(result["response_bytes"]) >= MIN_RESPONSE_BYTES and content_match)
    return {
        "run_id": MODEL_TAG,
        "received_at_local": _fmt_cst(received_at),
        "received_at_utc": received_at.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "line_id": LINE_ID,
        "target_id": target["target_id"],
        "product_vt_symbol": target["product_vt_symbol"],
        "target_group": target["target_group"],
        "route": target["route"],
        "source_url": target["source_url"],
        "strategy_id": strategy["strategy_id"],
        "header_variant": strategy["header_variant"],
        "warmup": int(bool(strategy["warmup"])),
        "referer_mode": strategy["referer"],
        "referer_url": referer,
        "warmup_statuses": ",".join(warmup_statuses),
        "warmup_bytes": warmup_bytes,
        "cookie_count_after_warmup": len(cookie_jar),
        "fetch_status": result["status"],
        "http_status": result["http_status"],
        "content_type": result["content_type"],
        "response_bytes": result["response_bytes"],
        "elapsed_ms": result["elapsed_ms"],
        "final_url": result["final_url"],
        "raw_sha256": result["raw_sha256"],
        "raw_sha256_present": int(bool(result["raw_sha256"])),
        "keyword_hit_count": keyword_count,
        "keyword_hits": keyword_hits,
        "content_match": content_match,
        "route_ready": route_ready,
        "http_412": int(int(result["http_status"]) == 412),
        "http_403": int(int(result["http_status"]) == 403),
        "http_404": int(int(result["http_status"]) == 404),
        "usable_for_forward_monitor": route_ready,
        "usable_for_history_selector": 0,
        "event_signal_ready": 0,
        "paper_or_whitelist_allowed": 0,
        "error": result["error"],
        "raw_text_excerpt": _clean_text(str(result["text"]))[:220],
        "notes": "CZCE route forensic only; no master ledger append and no strategy replay.",
    }


def build_probe_ledger(received_at: datetime) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for target in TARGETS:
        for strategy in PROBE_STRATEGIES:
            rows.append(_probe_one(target, strategy, received_at))
    return pd.DataFrame(rows)


def build_target_summary(ledger: pd.DataFrame) -> pd.DataFrame:
    summary = ledger.groupby(["target_id", "product_vt_symbol", "target_group", "route"], as_index=False).agg(
        attempts=("strategy_id", "count"),
        ok_rows=("fetch_status", lambda series: int((series == "ok").sum())),
        route_ready_rows=("route_ready", "sum"),
        http_412_rows=("http_412", "sum"),
        http_403_rows=("http_403", "sum"),
        max_response_bytes=("response_bytes", "max"),
        best_keyword_hits=("keyword_hit_count", "max"),
        best_strategy=("strategy_id", lambda series: ""),
    )
    best_rows = []
    for _, row in summary.iterrows():
        subset = ledger[ledger["target_id"].eq(row["target_id"])].copy()
        subset = subset.sort_values(["route_ready", "keyword_hit_count", "response_bytes"], ascending=False)
        best_rows.append(str(subset.iloc[0]["strategy_id"]) if not subset.empty else "")
    summary["best_strategy"] = best_rows
    summary["forward_monitor_allowed"] = (summary["route_ready_rows"].gt(0)).astype(int)
    summary["selector_allowed"] = 0
    return summary


def build_strategy_summary(ledger: pd.DataFrame) -> pd.DataFrame:
    return ledger.groupby(["strategy_id", "header_variant", "warmup", "referer_mode"], as_index=False).agg(
        attempts=("target_id", "count"),
        route_ready_rows=("route_ready", "sum"),
        ok_rows=("fetch_status", lambda series: int((series == "ok").sum())),
        http_412_rows=("http_412", "sum"),
        http_403_rows=("http_403", "sum"),
        max_cookie_count=("cookie_count_after_warmup", "max"),
        total_response_bytes=("response_bytes", "sum"),
    )


def build_gates(ledger: pd.DataFrame, target_summary: pd.DataFrame) -> pd.DataFrame:
    gates = [
        {
            "gate": "czce_route_ready_any",
            "passed": int(ledger["route_ready"].sum() > 0),
            "current": str(int(ledger["route_ready"].sum())),
            "required": ">0",
            "note": "At least one CZCE static/reference route must be machine-readable.",
        },
        {
            "gate": "english_reference_ready",
            "passed": int(
                target_summary.loc[
                    target_summary["target_id"].isin(["english_ref_20240418", "english_ref_20231229"]),
                    "route_ready_rows",
                ].sum()
                > 0
            ),
            "current": str(
                int(
                    target_summary.loc[
                        target_summary["target_id"].isin(["english_ref_20240418", "english_ref_20231229"]),
                        "route_ready_rows",
                    ].sum()
                )
            ),
            "required": ">0",
            "note": "English contract reference is needed for product mapping repair.",
        },
        {
            "gate": "cn_position_or_warehouse_ready",
            "passed": int(
                target_summary.loc[
                    target_summary["target_group"].isin(["position_rank_static_file", "warehouse_static_file"]),
                    "route_ready_rows",
                ].sum()
                > 0
            ),
            "current": str(
                int(
                    target_summary.loc[
                        target_summary["target_group"].isin(["position_rank_static_file", "warehouse_static_file"]),
                        "route_ready_rows",
                    ].sum()
                )
            ),
            "required": ">0",
            "note": "Member/warehouse route needs at least one official data file.",
        },
        {
            "gate": "http_412_reproduced",
            "passed": int(ledger["http_412"].sum() > 0),
            "current": str(int(ledger["http_412"].sum())),
            "required": ">0",
            "note": "Reproducing 412 is useful evidence for route-specific blocker.",
        },
        {
            "gate": "warmup_cookie_helped",
            "passed": int(
                ledger.loc[ledger["warmup"].eq(1), "route_ready"].sum()
                > ledger.loc[ledger["warmup"].eq(0), "route_ready"].sum()
            ),
            "current": f"warmup={int(ledger.loc[ledger['warmup'].eq(1), 'route_ready'].sum())},direct={int(ledger.loc[ledger['warmup'].eq(0), 'route_ready'].sum())}",
            "required": "warmup > direct",
            "note": "If false, simple browser-like warmup did not solve access.",
        },
        {
            "gate": "history_selector_rows_zero",
            "passed": int(ledger["usable_for_history_selector"].sum() == 0),
            "current": str(int(ledger["usable_for_history_selector"].sum())),
            "required": "0",
            "note": "No route forensic row enters history selector.",
        },
        {
            "gate": "event_signal_ready_zero",
            "passed": int(ledger["event_signal_ready"].sum() == 0),
            "current": str(int(ledger["event_signal_ready"].sum())),
            "required": "0",
            "note": "Route access is not alpha evidence.",
        },
        {
            "gate": "paper_whitelist_locked",
            "passed": int(ledger["paper_or_whitelist_allowed"].sum() == 0),
            "current": str(int(ledger["paper_or_whitelist_allowed"].sum())),
            "required": "0",
            "note": "No paper selector or trading whitelist permission.",
        },
    ]
    return pd.DataFrame(gates)


def make_chart(ledger: pd.DataFrame, target_summary: pd.DataFrame, strategy_summary: pd.DataFrame, gates: pd.DataFrame) -> None:
    targets = list(target_summary["target_id"])
    strategies = [item["strategy_id"] for item in PROBE_STRATEGIES]
    matrix = pd.DataFrame(0, index=targets, columns=strategies, dtype=float)
    labels = pd.DataFrame("", index=targets, columns=strategies)
    for _, row in ledger.iterrows():
        score = 3 if int(row["route_ready"]) else 2 if str(row["fetch_status"]) == "ok" else 1 if int(row["http_412"]) else 0
        label = "READY" if score == 3 else "OK" if score == 2 else "412" if score == 1 else "FAIL"
        matrix.loc[str(row["target_id"]), str(row["strategy_id"])] = score
        labels.loc[str(row["target_id"]), str(row["strategy_id"])] = label

    fig, axes = plt.subplots(2, 2, figsize=(19, 12))
    fig.suptitle("Stage626 CZCE 412 route forensic: source route only, selector locked", fontsize=16)

    ax = axes[0, 0]
    cmap = matplotlib.colors.ListedColormap(["#fed7d7", "#fbd38d", "#bee3f8", "#c6f6d5"])
    norm = matplotlib.colors.BoundaryNorm([-0.5, 0.5, 1.5, 2.5, 3.5], cmap.N)
    ax.imshow(matrix.values, cmap=cmap, norm=norm, aspect="auto")
    ax.set_xticks(range(len(strategies)))
    ax.set_xticklabels(strategies, rotation=35, ha="right", fontsize=8)
    ax.set_yticks(range(len(targets)))
    ax.set_yticklabels(targets, fontsize=8)
    ax.set_title("Target x request strategy status")
    for i in range(matrix.shape[0]):
        for j in range(matrix.shape[1]):
            ax.text(j, i, labels.iloc[i, j], ha="center", va="center", fontsize=7, fontweight="bold")

    ax = axes[0, 1]
    status_counts = ledger["http_status"].astype(str).value_counts().sort_index()
    ax.bar(status_counts.index, status_counts.values, color="#3182ce")
    ax.set_title("HTTP status count across probe matrix")
    ax.set_xlabel("http status")
    ax.set_ylabel("attempts")
    for x, value in enumerate(status_counts.values):
        ax.text(x, value + 0.2, str(int(value)), ha="center", fontsize=9)

    ax = axes[1, 0]
    strategy_plot = strategy_summary.sort_values("route_ready_rows")
    ax.barh(strategy_plot["strategy_id"], strategy_plot["route_ready_rows"], color="#38a169")
    ax.set_title("Route-ready rows by strategy")
    ax.set_xlabel("route-ready rows")
    for y, value in enumerate(strategy_plot["route_ready_rows"]):
        ax.text(value + 0.03, y, str(int(value)), va="center", fontsize=9)

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
    target_summary: pd.DataFrame,
    strategy_summary: pd.DataFrame,
    gates: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    report = f"""# Stage626 CZCE 412 Route Forensic

- line_id: `{LINE_ID}`
- generated_at: `{_fmt_cst(received_at)}`
- decision: `{decision["decision"]}`
- stage nature: CZCE public route forensic only; no master ledger append, no strategy replay, no selector, no paper whitelist, no CTP/order path.

## External Research And Judgement

References:
{chr(10).join(f"- {item}" for item in REFERENCES)}

Judgement:
- General HTTP 412 can reflect unmet server-side request preconditions; public search did not identify a CZCE-specific official explanation.
- Therefore this stage uses a request matrix instead of assuming one fix.
- Route readiness can only support forward monitor plumbing; it cannot become selector evidence.

## Key Results

- probe rows: `{len(ledger)}`
- route-ready rows: `{int(ledger["route_ready"].sum())}`
- HTTP 412 rows: `{int(ledger["http_412"].sum())}`
- HTTP 403 rows: `{int(ledger["http_403"].sum())}`
- hard gates: `{int(gates["passed"].sum())}/{len(gates)}`
- selector unlocked now: `{decision["selector_unlocked_now"]}`

## Target Summary

{_md_table(target_summary, max_rows=20)}

## Strategy Summary

{_md_table(strategy_summary, max_rows=20)}

## Gates

{_md_table(gates, max_rows=20)}

## Visual Review Notes

- Top-left heatmap separates `READY`, plain `OK`, `412`, and `FAIL`; a green cell is only route evidence, not alpha.
- Top-right shows whether `412` is a concentrated blocker or whether other statuses dominate.
- Bottom-left shows whether warmup/referer/browser-like headers actually improve route readiness.
- Bottom-right must keep selector/paper locked regardless of route outcome.

## Output Files

- probe ledger: `{PROBE_LEDGER_PATH}`
- target summary: `{TARGET_SUMMARY_PATH}`
- strategy summary: `{STRATEGY_SUMMARY_PATH}`
- gates: `{GATES_PATH}`
- decision: `{DECISION_PATH}`
- chart: `{CHART_PATH}`
"""
    REPORT_PATH.write_text(report, encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    received_at = _now_cst()
    ledger = build_probe_ledger(received_at)
    target_summary = build_target_summary(ledger)
    strategy_summary = build_strategy_summary(ledger)
    gates = build_gates(ledger, target_summary)
    decision = {
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at_cst": _fmt_cst(received_at),
        "decision": "czce_412_route_forensic_completed_selector_locked",
        "probe_rows": int(len(ledger)),
        "targets": int(ledger["target_id"].nunique()),
        "strategies": int(ledger["strategy_id"].nunique()),
        "route_ready_rows": int(ledger["route_ready"].sum()),
        "http_412_rows": int(ledger["http_412"].sum()),
        "http_403_rows": int(ledger["http_403"].sum()),
        "forward_monitor_rows": int(ledger["usable_for_forward_monitor"].sum()),
        "history_selector_rows": int(ledger["usable_for_history_selector"].sum()),
        "event_signal_ready_rows": int(ledger["event_signal_ready"].sum()),
        "selector_unlocked_now": 0,
        "paper_or_whitelist_allowed": 0,
        "trading_whitelist_allowed": False,
        "promotion_allowed": False,
        "hard_gates_passed": int(gates["passed"].sum()),
        "hard_gates_total": int(len(gates)),
        "summary": (
            "CZCE static/reference route forensic is complete for this matrix; "
            "any route-ready rows remain forward-monitor evidence only, while selector and paper stay locked."
        ),
    }
    ledger.to_csv(PROBE_LEDGER_PATH, index=False, encoding="utf-8-sig")
    target_summary.to_csv(TARGET_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    strategy_summary.to_csv(STRATEGY_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    gates.to_csv(GATES_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    write_report(received_at, ledger, target_summary, strategy_summary, gates, decision)
    make_chart(ledger, target_summary, strategy_summary, gates)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
