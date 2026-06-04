from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import html
import json
import math
import multiprocessing as mp
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import textwrap
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
import requests


LINE_ID = "futures_trend_drawdown30_preserve_return"
MODEL_TAG = "stage641_shfe_current_warehouse_route_forensic_v1"
OUTPUT_PREFIX = "qmt_roll_stage641_shfe_current_warehouse_route_forensic"

HTTP_PROBE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_http_probe_{MODEL_TAG}.csv"
BROWSER_PROBE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_browser_probe_{MODEL_TAG}.csv"
COOKIE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_browser_cookies_{MODEL_TAG}.csv"
AK_PROBE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_akshare_probe_{MODEL_TAG}.csv"
ROUTE_MATRIX_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_route_matrix_{MODEL_TAG}.csv"
GATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gates_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"
BROWSER_SCREENSHOT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_browser_page_{MODEL_TAG}.png"

PROBE_DATE = os.environ.get("STAGE641_PROBE_DATE", "20260603")
CURRENT_DATES = [PROBE_DATE, "20260604", "20260602", "20260529"]
LEGACY_DATE = "20200702"
HTTP_TIMEOUT_SECONDS = 14
BROWSER_TIMEOUT_SECONDS = 150
NPM_INSTALL_TIMEOUT_SECONDS = 120
AK_TIMEOUT_SECONDS = 20

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)

REFERENCES = [
    "SHFE dailystock UI: https://www.shfe.com.cn/reports/tradedata/dailyandweeklydata/?query_params=dailystock",
    "SHFE Daily Data English page: https://www.shfe.cn/eng/reports/StatisticalData/DailyData/",
    "AkShare legacy SHFE warehouse interface reference: https://cloud.tencent.com/developer/article/1666918",
    "AKShare local source: .py311/lib/python3.11/site-packages/akshare/futures/futures_warehouse_receipt.py",
    "AKShare local source: .py311/lib/python3.11/site-packages/akshare/futures/receipt.py",
    "AKShare local source: .py311/lib/python3.11/site-packages/akshare/futures/futures_stock_js.py",
]

PRODUCT_KEYWORDS = [
    "氧化铝",
    "铜",
    "铝",
    "aluminium",
    "aluminum",
    "copper",
]

WAF_MARKERS = [
    "WEB 应用防火墙",
    "向右滑动填充拼图",
    "人机识别",
    "captcha",
    "Just a moment",
    "Enable JavaScript and cookies",
    "Cloudflare",
    "Forbidden",
]


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
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


def _now_pair() -> tuple[datetime, datetime]:
    now_utc = datetime.now(timezone.utc)
    return now_utc.astimezone(ZoneInfo("Asia/Shanghai")), now_utc


def _stable_hash(payload: Any) -> str:
    text = json.dumps(_json_safe(payload), ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _text_head(text: str, limit: int = 320) -> str:
    return " ".join(str(text or "")[:limit].split())


def _decode_response_text(response: requests.Response) -> str:
    content = response.content or b""
    for encoding in ["utf-8", "gb18030", "gbk", response.encoding or "", "latin1"]:
        if not encoding:
            continue
        try:
            return content.decode(encoding, errors="strict")
        except UnicodeError:
            continue
    return content.decode("utf-8", errors="replace")


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
    text = re.sub(r"<script\b[^>]*>.*?</script>", " ", str(text), flags=re.I | re.S)
    text = re.sub(r"<style\b[^>]*>.*?</style>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _looks_like_waf(text: str, status_code: int = 0) -> bool:
    clean = str(text or "")
    if status_code in {403, 412}:
        return True
    return any(marker.lower() in clean.lower() for marker in WAF_MARKERS)


def _keyword_hits(text: str, keywords: list[str] = PRODUCT_KEYWORDS) -> tuple[int, str]:
    lower = str(text or "").lower()
    hits = [keyword for keyword in keywords if keyword.lower() in lower]
    return len(hits), ",".join(hits)


def _extract_payload_rows(parsed: Any) -> list[Any]:
    if isinstance(parsed, list):
        return parsed
    if not isinstance(parsed, dict):
        return []
    for key in ["o_cursor", "o_curinstrument", "data", "result", "records", "values"]:
        value = parsed.get(key)
        if isinstance(value, list):
            return value
        if isinstance(value, dict):
            nested = _extract_payload_rows(value)
            if nested:
                return nested
    return []


def _classify_payload(text: str, status_code: int = 0, expected: str = "auto") -> dict[str, Any]:
    clean = _clean_text(text)
    waf_like = int(_looks_like_waf(clean or text, status_code=status_code))
    keyword_count, keyword_hits = _keyword_hits(clean + "\n" + str(text or ""))
    parsed: Any = None
    json_parse_ok = 0
    rows: list[Any] = []
    json_top_keys = ""
    try:
        parsed = json.loads(text)
        json_parse_ok = 1
        if isinstance(parsed, dict):
            json_top_keys = ",".join([str(key) for key in parsed.keys()])
        elif isinstance(parsed, list):
            json_top_keys = "list"
        rows = _extract_payload_rows(parsed)
    except Exception:
        parsed = None
    matched_rows = [
        row
        for row in rows
        if any(keyword.lower() in json.dumps(_json_safe(row), ensure_ascii=False).lower() for keyword in PRODUCT_KEYWORDS)
    ]
    warehouse_context = any(marker.lower() in (clean + "\n" + str(text or "")).lower() for marker in ["仓单", "warrant", "wrchg", "wrt"])
    html_product_match = int(expected in {"html", "auto"} and keyword_count > 0 and warehouse_context and waf_like == 0)
    return {
        "waf_like": waf_like,
        "keyword_hit_count": keyword_count,
        "keyword_hits": keyword_hits,
        "json_parse_ok": json_parse_ok,
        "json_top_keys": json_top_keys,
        "payload_row_count": int(len(rows)),
        "matched_payload_rows": int(len(matched_rows)),
        "html_product_match": html_product_match,
        "page_ready": int(expected == "page" and keyword_count > 0 and waf_like == 0),
        "sample_value_json": json.dumps(_json_safe((matched_rows or rows)[:5]), ensure_ascii=False, sort_keys=True),
        "clean_head": clean[:320],
    }


def _base_http_row(phase: str, route: dict[str, Any]) -> dict[str, Any]:
    return {
        "phase": phase,
        "route_id": route["route_id"],
        "route_name": route["route_name"],
        "url": route["url"],
        "method": "GET",
        "expected": route["expected"],
        "source_authority": route["source_authority"],
        "source_role": route["source_role"],
        "current_date_flag": int(route["current_date_flag"]),
        "legacy_flag": int(route["legacy_flag"]),
        "third_party_flag": 0,
        "status": "not_run",
        "http_status": 0,
        "final_url": "",
        "content_type": "",
        "content_length": 0,
        "elapsed_ms": np.nan,
        "cookie_count": 0,
        "raw_sha256": "",
        "raw_sha256_present": 0,
        "waf_like": 0,
        "keyword_hit_count": 0,
        "keyword_hits": "",
        "json_parse_ok": 0,
        "json_top_keys": "",
        "payload_row_count": 0,
        "matched_payload_rows": 0,
        "html_product_match": 0,
        "page_ready": 0,
        "payload_ready": 0,
        "current_payload_ready": 0,
        "official_current_payload_ready": 0,
        "legacy_shape_validated": 0,
        "selector_rows": 0,
        "paper_whitelist_rows": 0,
        "sample_value_json": "[]",
        "body_head": "",
        "error_type": "",
        "error_message": "",
    }


def _route_targets() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = [
        {
            "route_id": "www_dailystock_ui",
            "route_name": "SHFE dailystock UI",
            "url": "https://www.shfe.com.cn/reports/tradedata/dailyandweeklydata/?query_params=dailystock",
            "expected": "page",
            "source_authority": "official_shfe",
            "source_role": "current_ui_page",
            "current_date_flag": 1,
            "legacy_flag": 0,
        },
        {
            "route_id": "www_english_dailydata",
            "route_name": "SHFE English Daily Data page",
            "url": "https://www.shfe.cn/eng/reports/StatisticalData/DailyData/",
            "expected": "page",
            "source_authority": "official_shfe",
            "source_role": "current_dailydata_page",
            "current_date_flag": 1,
            "legacy_flag": 0,
        },
    ]
    for date in CURRENT_DATES:
        rows.extend(
            [
                {
                    "route_id": f"www_dailydata_dat_{date}",
                    "route_name": f"www dailydata dailystock DAT {date}",
                    "url": f"https://www.shfe.com.cn/data/tradedata/future/dailydata/{date}dailystock.dat",
                    "expected": "json",
                    "source_authority": "official_shfe",
                    "source_role": "current_dailydata_dat",
                    "current_date_flag": 1,
                    "legacy_flag": 0,
                },
                {
                    "route_id": f"www_dailydata_html_{date}",
                    "route_name": f"www dailydata dailystock HTML {date}",
                    "url": f"https://www.shfe.com.cn/data/tradedata/future/dailydata/{date}dailystock.html",
                    "expected": "html",
                    "source_authority": "official_shfe",
                    "source_role": "current_dailydata_html",
                    "current_date_flag": 1,
                    "legacy_flag": 0,
                },
                {
                    "route_id": f"www_stockdata_zh_{date}",
                    "route_name": f"www stockdata ZH all.html {date}",
                    "url": f"https://www.shfe.com.cn/data/tradedata/future/stockdata/dailystock_{date}/ZH/all.html",
                    "expected": "html",
                    "source_authority": "official_shfe",
                    "source_role": "current_stockdata_zh_html",
                    "current_date_flag": 1,
                    "legacy_flag": 0,
                },
                {
                    "route_id": f"www_stockdata_en_{date}",
                    "route_name": f"www stockdata EN all.html {date}",
                    "url": f"https://www.shfe.com.cn/data/tradedata/future/stockdata/dailystock_{date}/EN/all.html",
                    "expected": "html",
                    "source_authority": "official_shfe",
                    "source_role": "current_stockdata_en_html",
                    "current_date_flag": 1,
                    "legacy_flag": 0,
                },
                {
                    "route_id": f"tsite_dat_{date}",
                    "route_name": f"tsite dailydata DAT {date}",
                    "url": f"http://tsite.shfe.com.cn/data/dailydata/{date}dailystock.dat",
                    "expected": "json",
                    "source_authority": "official_shfe_tsite",
                    "source_role": "current_tsite_dat",
                    "current_date_flag": 1,
                    "legacy_flag": 0,
                },
                {
                    "route_id": f"tsite_html_{date}",
                    "route_name": f"tsite dailydata HTML {date}",
                    "url": f"http://tsite.shfe.com.cn/data/dailydata/{date}dailystock.html",
                    "expected": "html",
                    "source_authority": "official_shfe_tsite",
                    "source_role": "current_tsite_html",
                    "current_date_flag": 1,
                    "legacy_flag": 0,
                },
                {
                    "route_id": f"tsite_dataview_{date}",
                    "route_name": f"tsite dataview dailystock {date}",
                    "url": f"https://tsite.shfe.com.cn/statements/dataview.html?paramid=dailystock&paramdate={date}",
                    "expected": "page",
                    "source_authority": "official_shfe_tsite",
                    "source_role": "current_tsite_dataview",
                    "current_date_flag": 1,
                    "legacy_flag": 0,
                },
            ]
        )
    rows.extend(
        [
            {
                "route_id": f"legacy_www_dailydata_dat_{LEGACY_DATE}",
                "route_name": f"legacy known-good DAT {LEGACY_DATE}",
                "url": f"https://www.shfe.com.cn/data/tradedata/future/dailydata/{LEGACY_DATE}dailystock.dat",
                "expected": "json",
                "source_authority": "official_shfe",
                "source_role": "legacy_dailydata_dat_shape_reference",
                "current_date_flag": 0,
                "legacy_flag": 1,
            },
            {
                "route_id": f"legacy_www_stockdata_zh_{LEGACY_DATE}",
                "route_name": f"legacy stockdata ZH all.html {LEGACY_DATE}",
                "url": f"https://www.shfe.com.cn/data/tradedata/future/stockdata/dailystock_{LEGACY_DATE}/ZH/all.html",
                "expected": "html",
                "source_authority": "official_shfe",
                "source_role": "legacy_stockdata_shape_reference",
                "current_date_flag": 0,
                "legacy_flag": 1,
            },
        ]
    )
    return rows


def _request_get(session: requests.Session, phase: str, route: dict[str, Any]) -> dict[str, Any]:
    row = _base_http_row(phase, route)
    started = datetime.now(timezone.utc)
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,text/plain,application/json,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Referer": "https://www.shfe.com.cn/reports/tradedata/dailyandweeklydata/?query_params=dailystock",
    }
    try:
        response = session.get(str(route["url"]), headers=headers, timeout=HTTP_TIMEOUT_SECONDS)
        elapsed_ms = (datetime.now(timezone.utc) - started).total_seconds() * 1000.0
        content = response.content or b""
        text = _decode_response_text(response)
        classification = _classify_payload(text, int(response.status_code), expected=str(route["expected"]))
        raw_sha256 = hashlib.sha256(content).hexdigest() if content else ""
        data_payload_ready = int(
            int(response.status_code) == 200
            and bool(raw_sha256)
            and classification["waf_like"] == 0
            and (
                (str(route["expected"]) == "json" and int(classification["json_parse_ok"]) > 0 and int(classification["matched_payload_rows"]) > 0)
                or (str(route["expected"]) == "html" and int(classification["html_product_match"]) > 0)
            )
        )
        row.update(
            {
                "status": "ok" if (data_payload_ready or int(classification["page_ready"]) > 0) else "blocked_or_wrong_format",
                "http_status": int(response.status_code),
                "final_url": str(response.url),
                "content_type": response.headers.get("Content-Type", ""),
                "content_length": int(len(content)),
                "elapsed_ms": round(elapsed_ms, 1),
                "cookie_count": int(len(session.cookies)),
                "raw_sha256": raw_sha256,
                "raw_sha256_present": int(bool(raw_sha256)),
                "payload_ready": data_payload_ready,
                "current_payload_ready": int(data_payload_ready and int(route["current_date_flag"]) == 1),
                "official_current_payload_ready": int(data_payload_ready and int(route["current_date_flag"]) == 1 and str(route["source_authority"]).startswith("official")),
                "legacy_shape_validated": int(data_payload_ready and int(route["legacy_flag"]) == 1),
                "body_head": _text_head(classification["clean_head"] or text),
                **classification,
            }
        )
    except Exception as exc:
        elapsed_ms = (datetime.now(timezone.utc) - started).total_seconds() * 1000.0
        row.update(
            {
                "status": "error",
                "elapsed_ms": round(elapsed_ms, 1),
                "cookie_count": int(len(session.cookies)),
                "error_type": type(exc).__name__,
                "error_message": str(exc)[:700],
            }
        )
    return row


def collect_http_probe() -> pd.DataFrame:
    routes = _route_targets()
    rows: list[dict[str, Any]] = []
    direct = requests.Session()
    for route in routes:
        rows.append(_request_get(direct, "direct", route))

    warm_session = requests.Session()
    for route in routes[:2]:
        rows.append(_request_get(warm_session, "session_warmup_page", route))
    for route in routes[2:]:
        rows.append(_request_get(warm_session, "after_session_warmup", route))
    return pd.DataFrame(rows)


def append_cookie_replay(http_probe: pd.DataFrame, cookies: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    if cookies.empty or "name" not in cookies.columns:
        return http_probe, 0
    session = requests.Session()
    for _, cookie in cookies.iterrows():
        name = str(cookie.get("name", ""))
        value = str(cookie.get("value", ""))
        if not name:
            continue
        kwargs: dict[str, Any] = {}
        domain = cookie.get("domain", "")
        path = cookie.get("path", "")
        if pd.notna(domain) and str(domain):
            kwargs["domain"] = str(domain)
        if pd.notna(path) and str(path):
            kwargs["path"] = str(path)
        session.cookies.set(name, value, **kwargs)
    replay_routes = [
        route
        for route in _route_targets()
        if route["source_role"] in {"current_dailydata_dat", "current_stockdata_zh_html", "current_stockdata_en_html", "current_tsite_dataview"}
        or int(route["legacy_flag"]) == 1
    ]
    rows = [_request_get(session, "browser_cookie_replay", route) for route in replay_routes]
    return pd.concat([http_probe, pd.DataFrame(rows)], ignore_index=True), 1


def _node_script() -> str:
    browser_routes = [
        route
        for route in _route_targets()
        if str(route["url"]).startswith("https://www.shfe.com.cn")
        or str(route["url"]).startswith("https://www.shfe.cn")
        or str(route["url"]).startswith("https://tsite.shfe.com.cn")
    ]
    return textwrap.dedent(
        f"""
        import {{ chromium }} from 'playwright';
        import crypto from 'node:crypto';
        const userAgent = {json.dumps(USER_AGENT)};
        const screenshotPath = {json.dumps(str(BROWSER_SCREENSHOT_PATH))};
        const routes = {json.dumps(browser_routes, ensure_ascii=False)};

        function head(text, n=320) {{
          return String(text || '').slice(0, n).replace(/\\s+/g, ' ').trim();
        }}
        function looksWaf(text, status) {{
          const body = String(text || '').toLowerCase();
          if ([403, 412].includes(status)) return 1;
          for (const marker of {json.dumps(WAF_MARKERS, ensure_ascii=False)}) {{
            if (body.includes(String(marker).toLowerCase())) return 1;
          }}
          return 0;
        }}
        function productHits(text) {{
          const body = String(text || '').toLowerCase();
          const hits = [];
          for (const marker of {json.dumps(PRODUCT_KEYWORDS, ensure_ascii=False)}) {{
            if (body.includes(String(marker).toLowerCase())) hits.push(marker);
          }}
          return hits;
        }}
        function payloadRows(parsed) {{
          if (Array.isArray(parsed)) return parsed;
          if (!parsed || typeof parsed !== 'object') return [];
          for (const key of ['o_cursor', 'o_curinstrument', 'data', 'result', 'records', 'values']) {{
            const value = parsed[key];
            if (Array.isArray(value)) return value;
            if (value && typeof value === 'object') {{
              const nested = payloadRows(value);
              if (nested.length) return nested;
            }}
          }}
          return [];
        }}
        async function launchBrowser() {{
          const attempts = [
            {{ channel: 'chrome', headless: true }},
            {{ channel: 'chromium', headless: true }},
            {{ headless: true }}
          ];
          let lastError = null;
          for (const options of attempts) {{
            try {{
              const browser = await chromium.launch(options);
              return {{ browser, launchOptions: JSON.stringify(options) }};
            }} catch (err) {{
              lastError = String(err && err.message ? err.message : err);
            }}
          }}
          throw new Error(lastError || 'browser launch failed');
        }}
        async function contextFetch(context, route) {{
          const started = Date.now();
          try {{
            const response = await context.request.get(route.url, {{
              headers: {{
                'Accept': 'text/html,text/plain,application/json,application/xhtml+xml,*/*',
              }},
              timeout: 25000,
            }});
            const text = await response.text();
            const out = {{
              status: response.status(),
              finalUrl: response.url(),
              contentType: response.headers()['content-type'] || '',
              text,
            }};
            let jsonParseOk = 0;
            let jsonTopKeys = '';
            let rows = [];
            try {{
              const parsed = JSON.parse(out.text || '');
              jsonParseOk = 1;
              jsonTopKeys = Array.isArray(parsed) ? 'list' : Object.keys(parsed || {{}}).join(',');
              rows = payloadRows(parsed);
            }} catch (_err) {{}}
            const hits = productHits(out.text || '');
            const matched = rows.filter((row) => productHits(JSON.stringify(row)).length > 0);
            const waf = looksWaf(out.text || '', out.status);
            const rawSha256 = crypto.createHash('sha256').update(out.text || '', 'utf8').digest('hex');
            const warehouseContext = ['仓单', 'warrant', 'wrchg', 'wrt'].some((marker) => String(out.text || '').toLowerCase().includes(marker));
            const htmlProductMatch = route.expected === 'html' && hits.length > 0 && warehouseContext && !waf ? 1 : 0;
            const payloadReady = out.status === 200 && !waf && rawSha256 && (
              (route.expected === 'json' && jsonParseOk && matched.length > 0) ||
              htmlProductMatch
            );
            const pageReady = route.expected === 'page' && hits.length > 0 && !waf ? 1 : 0;
            return {{
              ...route,
              phase: 'browser_context_fetch',
              status: payloadReady || pageReady ? 'ok' : 'blocked_or_wrong_format',
              http_status: out.status,
              final_url: out.finalUrl || '',
              content_type: out.contentType || '',
              content_length: (out.text || '').length,
              elapsed_ms: Date.now() - started,
              raw_sha256: rawSha256,
              raw_sha256_present: rawSha256 ? 1 : 0,
              waf_like: waf,
              keyword_hit_count: hits.length,
              keyword_hits: hits.join(','),
              json_parse_ok: jsonParseOk,
              json_top_keys: jsonTopKeys,
              payload_row_count: rows.length,
              matched_payload_rows: matched.length,
              html_product_match: htmlProductMatch,
              page_ready: pageReady,
              payload_ready: payloadReady ? 1 : 0,
              current_payload_ready: payloadReady && route.current_date_flag ? 1 : 0,
              official_current_payload_ready: payloadReady && route.current_date_flag ? 1 : 0,
              legacy_shape_validated: payloadReady && route.legacy_flag ? 1 : 0,
              selector_rows: 0,
              paper_whitelist_rows: 0,
              sample_value_json: JSON.stringify((matched.length ? matched : rows).slice(0, 5)),
              body_head: head(out.text),
              error_type: '',
              error_message: ''
            }};
          }} catch (err) {{
            return {{
              ...route,
              phase: 'browser_context_fetch',
              status: 'error',
              http_status: 0,
              final_url: '',
              content_type: '',
              content_length: 0,
              elapsed_ms: Date.now() - started,
              raw_sha256: '',
              raw_sha256_present: 0,
              waf_like: 0,
              keyword_hit_count: 0,
              keyword_hits: '',
              json_parse_ok: 0,
              json_top_keys: '',
              payload_row_count: 0,
              matched_payload_rows: 0,
              html_product_match: 0,
              page_ready: 0,
              payload_ready: 0,
              current_payload_ready: 0,
              official_current_payload_ready: 0,
              legacy_shape_validated: 0,
              selector_rows: 0,
              paper_whitelist_rows: 0,
              sample_value_json: '[]',
              body_head: '',
              error_type: err && err.name ? err.name : 'Error',
              error_message: String(err && err.message ? err.message : err).slice(0, 800)
            }};
          }}
        }}

        const result = {{
          browser_status: 'not_run',
          launch_options: '',
          page_title: '',
          final_url: '',
          screenshot_path: screenshotPath,
          page_steps: [],
          endpoint_probes: [],
          cookies: [],
          error_type: '',
          error_message: ''
        }};
        let browser = null;
        try {{
          const launched = await launchBrowser();
          browser = launched.browser;
          result.launch_options = launched.launchOptions;
          const context = await browser.newContext({{
            userAgent,
            viewport: {{ width: 1365, height: 900 }},
            ignoreHTTPSErrors: true,
          }});
          const page = await context.newPage();
          for (const route of routes.filter((r) => ['current_ui_page', 'current_dailydata_page'].includes(r.source_role))) {{
            const started = Date.now();
            try {{
              const response = await page.goto(route.url, {{ waitUntil: 'domcontentloaded', timeout: 25000 }});
              await page.waitForTimeout(3500);
              result.page_steps.push({{
                route_id: route.route_id,
                url: route.url,
                status: response ? response.status() : 0,
                final_url: page.url(),
                title: await page.title(),
                elapsed_ms: Date.now() - started,
              }});
            }} catch (err) {{
              result.page_steps.push({{
                route_id: route.route_id,
                url: route.url,
                status: 0,
                final_url: page.url(),
                title: await page.title().catch(() => ''),
                elapsed_ms: Date.now() - started,
                error_type: err && err.name ? err.name : 'Error',
                error_message: String(err && err.message ? err.message : err).slice(0, 800)
              }});
            }}
          }}
          result.page_title = await page.title();
          result.final_url = page.url();
          await page.screenshot({{ path: screenshotPath, fullPage: true }}).catch(() => null);
          result.cookies = await context.cookies();
          for (const route of routes) {{
            result.endpoint_probes.push(await contextFetch(context, route));
          }}
          result.browser_status = 'ok';
          await browser.close();
        }} catch (err) {{
          result.browser_status = 'error';
          result.error_type = err && err.name ? err.name : 'Error';
          result.error_message = String(err && err.message ? err.message : err).slice(0, 1200);
          if (browser) await browser.close().catch(() => null);
        }}
        console.log(JSON.stringify(result));
        """
    )


def collect_browser_probe() -> tuple[pd.DataFrame, pd.DataFrame]:
    node = shutil.which("node")
    npm = shutil.which("npm")
    base = {
        "phase": "browser_context_fetch",
        "browser_status": "not_run",
        "launch_options": "",
        "page_title": "",
        "browser_final_url": "",
        "screenshot_path": str(BROWSER_SCREENSHOT_PATH),
        "route_id": "",
        "route_name": "",
        "url": "",
        "expected": "",
        "source_authority": "",
        "source_role": "",
        "current_date_flag": 0,
        "legacy_flag": 0,
        "third_party_flag": 0,
        "status": "not_run",
        "http_status": 0,
        "final_url": "",
        "content_type": "",
        "content_length": 0,
        "elapsed_ms": np.nan,
        "raw_sha256": "",
        "raw_sha256_present": 0,
        "waf_like": 0,
        "keyword_hit_count": 0,
        "keyword_hits": "",
        "json_parse_ok": 0,
        "json_top_keys": "",
        "payload_row_count": 0,
        "matched_payload_rows": 0,
        "html_product_match": 0,
        "page_ready": 0,
        "payload_ready": 0,
        "current_payload_ready": 0,
        "official_current_payload_ready": 0,
        "legacy_shape_validated": 0,
        "selector_rows": 0,
        "paper_whitelist_rows": 0,
        "sample_value_json": "[]",
        "body_head": "",
        "error_type": "",
        "error_message": "",
    }
    if not node or not npm:
        return pd.DataFrame([{**base, "browser_status": "missing_node_or_npm", "status": "error", "error_type": "MissingNodeOrNpm"}]), pd.DataFrame()

    with tempfile.TemporaryDirectory(prefix="stage641_shfe_") as tmpdir:
        tmp_path = Path(tmpdir)
        script_path = tmp_path / "probe.mjs"
        (tmp_path / "package.json").write_text('{"type":"module","private":true}\n', encoding="utf-8")
        script_path.write_text(_node_script(), encoding="utf-8")
        env = os.environ.copy()
        env.setdefault("PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD", "1")
        env.setdefault("npm_config_yes", "true")
        install = subprocess.run(
            [npm, "install", "playwright", "--no-save", "--silent"],
            cwd=str(tmp_path),
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=NPM_INSTALL_TIMEOUT_SECONDS,
            check=False,
        )
        if install.returncode != 0:
            return (
                pd.DataFrame(
                    [
                        {
                            **base,
                            "browser_status": "npm_install_failed",
                            "status": "error",
                            "error_type": "NpmInstallFailed",
                            "error_message": ((install.stderr or "") + "\n" + (install.stdout or ""))[:1200],
                        }
                    ]
                ),
                pd.DataFrame(),
            )
        proc = subprocess.run(
            [node, str(script_path)],
            cwd=str(tmp_path),
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=BROWSER_TIMEOUT_SECONDS,
            check=False,
        )

    stdout = (proc.stdout or "").strip()
    stderr = (proc.stderr or "").strip()
    if proc.returncode != 0 or not stdout:
        return (
            pd.DataFrame(
                [
                    {
                        **base,
                        "browser_status": "process_failed",
                        "status": "error",
                        "error_type": "BrowserProcessFailed",
                        "error_message": (stderr or stdout)[:1200],
                    }
                ]
            ),
            pd.DataFrame(),
        )
    try:
        data = json.loads(stdout.splitlines()[-1])
    except Exception as exc:
        return (
            pd.DataFrame(
                [
                    {
                        **base,
                        "browser_status": "json_parse_failed",
                        "status": "error",
                        "error_type": type(exc).__name__,
                        "error_message": (stdout + "\n" + stderr)[:1200],
                    }
                ]
            ),
            pd.DataFrame(),
        )

    rows: list[dict[str, Any]] = []
    for item in data.get("endpoint_probes") or []:
        route = {
            "route_id": item.get("route_id", ""),
            "route_name": item.get("route_name", ""),
            "url": item.get("url", ""),
            "expected": item.get("expected", ""),
            "source_authority": item.get("source_authority", ""),
            "source_role": item.get("source_role", ""),
            "current_date_flag": int(item.get("current_date_flag", 0) or 0),
            "legacy_flag": int(item.get("legacy_flag", 0) or 0),
        }
        rows.append(
            {
                **base,
                **route,
                "browser_status": data.get("browser_status", ""),
                "launch_options": data.get("launch_options", ""),
                "page_title": data.get("page_title", ""),
                "browser_final_url": data.get("final_url", ""),
                "status": item.get("status", "not_run"),
                "http_status": int(item.get("http_status", 0) or 0),
                "final_url": item.get("final_url", ""),
                "content_type": item.get("content_type", ""),
                "content_length": int(item.get("content_length", 0) or 0),
                "elapsed_ms": item.get("elapsed_ms", np.nan),
                "raw_sha256": item.get("raw_sha256", ""),
                "raw_sha256_present": int(item.get("raw_sha256_present", 0) or 0),
                "waf_like": int(item.get("waf_like", 0) or 0),
                "keyword_hit_count": int(item.get("keyword_hit_count", 0) or 0),
                "keyword_hits": item.get("keyword_hits", ""),
                "json_parse_ok": int(item.get("json_parse_ok", 0) or 0),
                "json_top_keys": item.get("json_top_keys", ""),
                "payload_row_count": int(item.get("payload_row_count", 0) or 0),
                "matched_payload_rows": int(item.get("matched_payload_rows", 0) or 0),
                "html_product_match": int(item.get("html_product_match", 0) or 0),
                "page_ready": int(item.get("page_ready", 0) or 0),
                "payload_ready": int(item.get("payload_ready", 0) or 0),
                "current_payload_ready": int(item.get("current_payload_ready", 0) or 0),
                "official_current_payload_ready": int(item.get("official_current_payload_ready", 0) or 0),
                "legacy_shape_validated": int(item.get("legacy_shape_validated", 0) or 0),
                "selector_rows": 0,
                "paper_whitelist_rows": 0,
                "sample_value_json": item.get("sample_value_json", "[]"),
                "body_head": item.get("body_head", ""),
                "error_type": item.get("error_type", ""),
                "error_message": item.get("error_message", ""),
            }
        )
    if not rows:
        rows.append(
            {
                **base,
                "browser_status": data.get("browser_status", ""),
                "status": "error",
                "error_type": data.get("error_type", ""),
                "error_message": data.get("error_message", ""),
            }
        )
    cookies = pd.DataFrame(data.get("cookies") or [])
    if cookies.empty:
        cookies = pd.DataFrame(columns=["name", "value", "domain", "path", "expires", "httpOnly", "secure", "sameSite"])
    return pd.DataFrame(rows), cookies


def _run_ak_probe(function_name: str, date: str) -> dict[str, Any]:
    def worker(queue: mp.Queue) -> None:
        try:
            import akshare as ak

            result = getattr(ak, function_name)(date=date)
            if isinstance(result, dict):
                packed: dict[str, Any] = {}
                row_count = 0
                for key, item in result.items():
                    if isinstance(item, pd.DataFrame):
                        row_count += len(item)
                        packed[str(key)] = {
                            "rows": int(len(item)),
                            "columns": list(item.columns),
                            "records": item.head(10).to_dict("records"),
                        }
                    else:
                        packed[str(key)] = {"repr": str(item)[:300], "type": type(item).__name__}
                queue.put({"status": "ok", "kind": "dict", "rows": row_count, "keys": list(result.keys()), "payload": packed})
            elif isinstance(result, pd.DataFrame):
                queue.put({"status": "ok", "kind": "dataframe", "rows": int(len(result)), "columns": list(result.columns), "payload": result.head(30).to_dict("records")})
            else:
                queue.put({"status": "ok", "kind": type(result).__name__, "rows": 0, "payload": str(result)[:400]})
        except Exception as exc:
            queue.put({"status": "error", "error_type": type(exc).__name__, "error_message": str(exc)[:800]})

    ctx = mp.get_context("fork")
    queue: mp.Queue = ctx.Queue()
    process = ctx.Process(target=worker, args=(queue,))
    process.start()
    process.join(AK_TIMEOUT_SECONDS)
    if process.is_alive():
        process.terminate()
        process.join(2)
        return {"status": "timeout", "error_type": "Timeout", "error_message": f">{AK_TIMEOUT_SECONDS}s"}
    if queue.empty():
        return {"status": "empty", "error_type": "EmptyResult", "error_message": "worker returned no message"}
    return queue.get()


def collect_akshare_probe() -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    calls = [
        ("futures_shfe_warehouse_receipt", PROBE_DATE, "official_wrapper_current_dailystock"),
        ("futures_shfe_warehouse_receipt", LEGACY_DATE, "official_wrapper_legacy_shape"),
        ("futures_stock_shfe_js", PROBE_DATE, "third_party_jin10_weekly_stock_current"),
    ]
    for function_name, date, route_id in calls:
        result = _run_ak_probe(function_name, date)
        payload_text = json.dumps(_json_safe(result.get("payload", {})), ensure_ascii=False, sort_keys=True)
        keyword_count, keyword_hits = _keyword_hits(payload_text)
        rows_returned = int(result.get("rows", 0) or 0)
        ok_rows = int(result.get("status") == "ok" and rows_returned > 0)
        third_party = int(function_name == "futures_stock_shfe_js")
        rows.append(
            {
                "phase": "akshare_wrapper",
                "route_id": route_id,
                "route_name": function_name,
                "url": "akshare_local_function",
                "expected": "dataframe_or_dict",
                "source_authority": "third_party_jin10_akshare" if third_party else "official_shfe_via_akshare",
                "source_role": "third_party_weekly_stock_monitor" if third_party else "warehouse_receipt_wrapper",
                "current_date_flag": int(date != LEGACY_DATE),
                "legacy_flag": int(date == LEGACY_DATE),
                "third_party_flag": third_party,
                "status": "ok" if ok_rows else result.get("status", "error"),
                "http_status": 0,
                "final_url": "",
                "content_type": "",
                "content_length": len(payload_text.encode("utf-8")),
                "elapsed_ms": np.nan,
                "cookie_count": 0,
                "raw_sha256": _stable_hash(result),
                "raw_sha256_present": 1,
                "waf_like": int("WEB 应用防火墙" in str(result) or "向右滑动填充拼图" in str(result)),
                "keyword_hit_count": keyword_count,
                "keyword_hits": keyword_hits,
                "json_parse_ok": 1,
                "json_top_keys": ",".join(result.keys()),
                "payload_row_count": rows_returned,
                "matched_payload_rows": rows_returned if keyword_count else 0,
                "html_product_match": 0,
                "payload_ready": ok_rows,
                "current_payload_ready": int(ok_rows and date != LEGACY_DATE),
                "official_current_payload_ready": int(ok_rows and date != LEGACY_DATE and not third_party),
                "legacy_shape_validated": int(ok_rows and date == LEGACY_DATE),
                "selector_rows": 0,
                "paper_whitelist_rows": 0,
                "sample_value_json": payload_text[:3000],
                "body_head": _text_head(payload_text),
                "error_type": result.get("error_type", ""),
                "error_message": result.get("error_message", ""),
                "date": date,
            }
        )
    return pd.DataFrame(rows)


def build_route_matrix(http_probe: pd.DataFrame, browser_probe: pd.DataFrame, ak_probe: pd.DataFrame) -> pd.DataFrame:
    browser_as_http = browser_probe.copy()
    for column in http_probe.columns:
        if column not in browser_as_http.columns:
            browser_as_http[column] = np.nan
    for column in http_probe.columns:
        if column not in ak_probe.columns:
            ak_probe[column] = np.nan
    matrix = pd.concat([http_probe, browser_as_http[http_probe.columns], ak_probe[http_probe.columns]], ignore_index=True)
    matrix["route_key"] = matrix["phase"].astype(str) + "::" + matrix["route_id"].astype(str)
    return matrix


def build_gates(route_matrix: pd.DataFrame, browser_probe: pd.DataFrame, cookies: pd.DataFrame, cookie_replay_attempted: int) -> pd.DataFrame:
    official = route_matrix[route_matrix["source_authority"].astype(str).str.startswith("official")].copy()
    official_current = official[official["current_date_flag"].eq(1)].copy()
    official_route_variants = int(official_current["source_role"].nunique())
    current_ready = int(official_current["official_current_payload_ready"].sum())
    legacy_ready = int(route_matrix["legacy_shape_validated"].sum())
    browser_attempted = int(len(browser_probe) > 0 and not browser_probe["browser_status"].eq("not_run").all())
    waf_rows = int(route_matrix["waf_like"].sum())
    blocked_current_rows = int(len(official_current[(official_current["status"].isin(["blocked_or_wrong_format", "error", "timeout", "empty"])) | (official_current["http_status"].isin([403, 404, 412]))]))
    selector_rows = int(route_matrix["selector_rows"].fillna(0).sum())
    paper_rows = int(route_matrix["paper_whitelist_rows"].fillna(0).sum())
    ak_inspected = int(len(route_matrix[route_matrix["phase"].eq("akshare_wrapper")]) >= 3)
    third_party_monitor_rows = int(route_matrix[(route_matrix["third_party_flag"].fillna(0).eq(1)) & route_matrix["payload_ready"].fillna(0).eq(1)].shape[0])
    gates = [
        {
            "gate": "official_route_variants_tested",
            "passed": int(official_route_variants >= 8),
            "current": official_route_variants,
            "required": ">=8",
            "note": "Test current SHFE www/tsite/UI/DAT/HTML/stockdata variants, not one URL only.",
        },
        {
            "gate": "akshare_source_inspected",
            "passed": ak_inspected,
            "current": int(len(route_matrix[route_matrix["phase"].eq("akshare_wrapper")])),
            "required": ">=3 wrapper rows",
            "note": "Check local AKShare wrappers and third-party Jin10 monitor route.",
        },
        {
            "gate": "legacy_payload_shape_validated",
            "passed": int(legacy_ready > 0),
            "current": legacy_ready,
            "required": ">0",
            "note": "Legacy known-good route must prove field shape still exists.",
        },
        {
            "gate": "current_official_payload_ready",
            "passed": int(current_ready > 0),
            "current": current_ready,
            "required": ">0",
            "note": "Only this would move SHFE current warehouse route into forward PIT candidate.",
        },
        {
            "gate": "browser_context_attempted",
            "passed": browser_attempted,
            "current": browser_attempted,
            "required": 1,
            "note": "Browser/CDP session should be attempted for WAF forensic.",
        },
        {
            "gate": "cookie_replay_attempted",
            "passed": int(cookie_replay_attempted == 1),
            "current": cookie_replay_attempted,
            "required": 1,
            "note": "Replay observed browser cookies through requests when cookies are available.",
        },
        {
            "gate": "waf_or_blocker_classified",
            "passed": int(waf_rows > 0 or blocked_current_rows > 0),
            "current": f"waf={waf_rows},blocked_current={blocked_current_rows}",
            "required": "waf>0 or blocked_current>0",
            "note": "Current route blocker should be classified instead of silently ignored.",
        },
        {
            "gate": "third_party_monitor_not_selector",
            "passed": int(third_party_monitor_rows >= 0 and selector_rows == 0),
            "current": f"third_party_monitor_rows={third_party_monitor_rows},selector={selector_rows}",
            "required": "selector=0",
            "note": "Jin10/AKShare can only be monitor evidence, not selector unlock.",
        },
        {
            "gate": "selector_rows_zero",
            "passed": int(selector_rows == 0),
            "current": selector_rows,
            "required": 0,
            "note": "Route forensic must not create selector samples.",
        },
        {
            "gate": "paper_whitelist_zero",
            "passed": int(paper_rows == 0),
            "current": paper_rows,
            "required": 0,
            "note": "Route forensic must not create paper or trading whitelist rows.",
        },
        {
            "gate": "master_append_zero_stage_scoped",
            "passed": 1,
            "current": 0,
            "required": 0,
            "note": "This stage is scoped forensic only; no master PIT append.",
        },
    ]
    return pd.DataFrame(gates)


def build_decision(now_local: datetime, route_matrix: pd.DataFrame, gates: pd.DataFrame, cookie_replay_attempted: int) -> dict[str, Any]:
    official_current_ready = int(route_matrix["official_current_payload_ready"].fillna(0).sum())
    legacy_shape = int(route_matrix["legacy_shape_validated"].fillna(0).sum())
    browser_attempted = int(gates.loc[gates["gate"].eq("browser_context_attempted"), "passed"].sum() > 0)
    waf_rows = int(route_matrix["waf_like"].fillna(0).sum())
    blocked_current_rows = int(
        len(
            route_matrix[
                route_matrix["current_date_flag"].fillna(0).eq(1)
                & route_matrix["source_authority"].astype(str).str.startswith("official")
                & (
                    route_matrix["status"].isin(["blocked_or_wrong_format", "error", "timeout", "empty"])
                    | route_matrix["http_status"].isin([403, 404, 412])
                )
            ]
        )
    )
    if official_current_ready > 0:
        decision = "shfe_current_warehouse_official_route_ready_selector_locked"
    elif legacy_shape > 0 and browser_attempted and (waf_rows > 0 or blocked_current_rows > 0):
        decision = "shfe_current_warehouse_route_blocked_legacy_shape_validated_selector_locked"
    else:
        decision = "shfe_current_warehouse_route_forensic_incomplete_selector_locked"
    return {
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at_cst": now_local.strftime("%Y-%m-%d %H:%M:%S CST"),
        "probe_date": PROBE_DATE,
        "decision": decision,
        "official_current_payload_ready_rows": official_current_ready,
        "legacy_payload_shape_validated_rows": legacy_shape,
        "browser_attempted": browser_attempted,
        "browser_cookie_count": int(len(COOKIE_PATH.read_text(encoding="utf-8-sig").splitlines()) - 1) if COOKIE_PATH.exists() else 0,
        "cookie_replay_attempted": cookie_replay_attempted,
        "waf_like_rows": waf_rows,
        "blocked_current_rows": blocked_current_rows,
        "third_party_monitor_ready_rows": int(route_matrix[(route_matrix["third_party_flag"].fillna(0).eq(1)) & route_matrix["payload_ready"].fillna(0).eq(1)].shape[0]),
        "selector_rows": int(route_matrix["selector_rows"].fillna(0).sum()),
        "paper_whitelist_rows": int(route_matrix["paper_whitelist_rows"].fillna(0).sum()),
        "promotion_allowed": 0,
        "paper_allowed": 0,
        "trading_whitelist_allowed": 0,
        "hard_gates_passed": int(gates["passed"].sum()),
        "hard_gates_total": int(len(gates)),
        "http_probe_path": str(HTTP_PROBE_PATH),
        "browser_probe_path": str(BROWSER_PROBE_PATH),
        "ak_probe_path": str(AK_PROBE_PATH),
        "route_matrix_path": str(ROUTE_MATRIX_PATH),
        "gates_path": str(GATES_PATH),
        "report_path": str(REPORT_PATH),
        "chart_path": str(CHART_PATH),
        "browser_screenshot_path": str(BROWSER_SCREENSHOT_PATH),
    }


def write_chart(route_matrix: pd.DataFrame, gates: pd.DataFrame, decision: dict[str, Any]) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(18, 11))
    fig.suptitle("Stage641 SHFE current warehouse route forensic: source route first, selector locked", fontsize=15)

    ax = axes[0, 0]
    heat = route_matrix[
        route_matrix["source_authority"].astype(str).str.startswith("official")
        & route_matrix["current_date_flag"].fillna(0).eq(1)
    ].copy()
    heat = heat[heat["phase"].isin(["direct", "after_session_warmup", "browser_context_fetch", "browser_cookie_replay"])].copy()
    heat["no_waf"] = 1 - heat["waf_like"].fillna(0).astype(int)
    heat["json_or_html_match"] = (
        (heat["json_parse_ok"].fillna(0).astype(int) > 0)
        | (heat["html_product_match"].fillna(0).astype(int) > 0)
    ).astype(int)
    heat = (
        heat.groupby(["source_role"], as_index=False)
        .agg(
            raw_sha256_present=("raw_sha256_present", "max"),
            no_waf=("no_waf", "max"),
            json_or_html_match=("json_or_html_match", "max"),
            official_current_payload_ready=("official_current_payload_ready", "max"),
            rows=("route_id", "count"),
        )
        .sort_values(["source_role"])
    )
    if heat.empty:
        ax.text(0.5, 0.5, "No current official route rows", ha="center", va="center")
        ax.set_axis_off()
    else:
        metrics = ["raw_sha256_present", "no_waf", "json_or_html_match", "official_current_payload_ready"]
        image = ax.imshow(heat[metrics].fillna(0).astype(float).values, aspect="auto", cmap="RdYlGn", vmin=0, vmax=1)
        ax.set_xticks(np.arange(len(metrics)))
        ax.set_xticklabels(["hash", "no WAF", "parse/match", "current ready"], rotation=20, ha="right")
        labels = (heat["source_role"].astype(str) + " (" + heat["rows"].astype(str) + ")").tolist()
        ax.set_yticks(np.arange(len(labels)))
        ax.set_yticklabels(labels, fontsize=8)
        for i in range(len(heat)):
            for j in range(len(metrics)):
                ax.text(j, i, str(int(heat.iloc[i][metrics[j]])), ha="center", va="center", fontsize=7)
        ax.set_title("Current official route validation layers")
        fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04)

    ax = axes[0, 1]
    phase = route_matrix.groupby("phase", as_index=False).agg(
        rows=("route_id", "count"),
        ready=("official_current_payload_ready", "sum"),
        waf=("waf_like", "sum"),
        legacy=("legacy_shape_validated", "sum"),
    )
    x = np.arange(len(phase))
    ax.bar(x - 0.27, phase["rows"], width=0.18, label="rows", color="#a0aec0")
    ax.bar(x - 0.09, phase["ready"], width=0.18, label="current ready", color="#2f855a")
    ax.bar(x + 0.09, phase["legacy"], width=0.18, label="legacy shape", color="#3182ce")
    ax.bar(x + 0.27, phase["waf"], width=0.18, label="WAF/block", color="#c53030")
    ax.set_xticks(x)
    ax.set_xticklabels(phase["phase"].tolist(), rotation=20, ha="right")
    ax.set_title("Phase-level route evidence")
    ax.set_ylabel("count")
    ax.legend(fontsize=8)
    ax.grid(axis="y", alpha=0.25)

    ax = axes[1, 0]
    readiness = pd.DataFrame(
        [
            {"bucket": "current official", "ready": int(decision["official_current_payload_ready_rows"]), "blocked": int(decision["blocked_current_rows"])},
            {"bucket": "legacy shape", "ready": int(decision["legacy_payload_shape_validated_rows"]), "blocked": 0},
            {"bucket": "third-party monitor", "ready": int(decision["third_party_monitor_ready_rows"]), "blocked": 0},
            {"bucket": "selector/paper", "ready": 0, "blocked": 1},
        ]
    )
    x = np.arange(len(readiness))
    ax.bar(x - 0.18, readiness["ready"], width=0.36, color="#2f855a", label="ready/evidence")
    ax.bar(x + 0.18, readiness["blocked"], width=0.36, color="#c53030", label="blocked/locked")
    ax.set_xticks(x)
    ax.set_xticklabels(readiness["bucket"].tolist(), rotation=15, ha="right")
    ax.set_title("Readiness: current vs legacy vs third-party")
    ax.set_ylabel("rows")
    ax.legend(fontsize=8)
    ax.grid(axis="y", alpha=0.25)

    ax = axes[1, 1]
    colors = ["#2f855a" if int(item) else "#c53030" for item in gates["passed"]]
    ax.barh(gates["gate"], [1] * len(gates), color=colors)
    ax.set_xlim(0, 1)
    ax.set_title("Hard gates: red failures must remain visible")
    ax.tick_params(axis="y", labelsize=8)
    for i, row in gates.reset_index(drop=True).iterrows():
        label = f"{'PASS' if int(row['passed']) else 'FAIL'} {row['current']}"
        ax.text(0.02, i, label, va="center", ha="left", fontsize=8, color="white", fontweight="bold")

    fig.tight_layout(rect=(0, 0, 1, 0.94))
    fig.savefig(CHART_PATH, dpi=170)
    plt.close(fig)


def write_report(now_local: datetime, route_matrix: pd.DataFrame, gates: pd.DataFrame, decision: dict[str, Any]) -> None:
    blocked = route_matrix[
        route_matrix["current_date_flag"].fillna(0).eq(1)
        & route_matrix["source_authority"].astype(str).str.startswith("official")
        & (
            route_matrix["status"].isin(["blocked_or_wrong_format", "error", "timeout", "empty"])
            | route_matrix["http_status"].isin([403, 404, 412])
        )
    ].copy()
    ready = route_matrix[route_matrix["payload_ready"].fillna(0).eq(1)].copy()
    report = f"""# Stage641 SHFE Current Warehouse Route Forensic Report

- line_id: `{LINE_ID}`
- generated_at_cst: `{now_local.strftime("%Y-%m-%d %H:%M:%S CST")}`
- decision: `{decision["decision"]}`
- promotion_allowed: `{decision["promotion_allowed"]}`
- paper_allowed: `{decision["paper_allowed"]}`
- trading_whitelist_allowed: `{decision["trading_whitelist_allowed"]}`

## Scope

本阶段只回答一个问题：`base_metals/ao.SHFE` 这条 SHFE 当前仓单/库存官方源，能否自动化进入 forward PIT 账本。

它不重放策略、不看收益、不改参数、不追加 master ledger、不生成 selector、paper、A/B 或交易白名单。

## External And Source Research Judgement

- 旧 AkShare 文档/旧接口说明 SHFE 仓单日报历史上经由 `dataview.html?paramid=dailystock&paramdate=YYYYMMDD` 或 `dailystock.dat/html` 获取。
- 当前本地 AKShare 源码已经把 `20140519` 之后的仓单函数指向 `https://www.shfe.com.cn/data/tradedata/future/dailydata/{{date}}dailystock.dat`，并另有 `stockdata/dailystock_{{date}}/ZH/all.html` 解析函数。
- 第三方 Jin10 周库存路线可以作为 monitor 候选，但不是官方 PIT selector 证据，不能解锁交易。
- 本阶段判断标准：如果当前官方 route 不能通过 direct/session/browser/cookie-replay 稳定返回产品 payload，就只能保留 source backlog 或寻找授权/替代官方数据渠道。

References:
{chr(10).join([f"- {item}" for item in REFERENCES])}

## Decision JSON

```json
{json.dumps(_json_safe(decision), ensure_ascii=False, indent=2, sort_keys=True)}
```

## Ready / Payload Rows

{_md_table(ready, ["phase", "route_id", "source_authority", "source_role", "current_date_flag", "legacy_flag", "third_party_flag", "status", "http_status", "payload_ready", "official_current_payload_ready", "legacy_shape_validated", "payload_row_count", "matched_payload_rows", "keyword_hits", "body_head"], 40)}

## Blocked Current Official Rows

{_md_table(blocked, ["phase", "route_id", "source_authority", "source_role", "status", "http_status", "waf_like", "content_length", "error_type", "error_message", "body_head"], 50)}

## Gates

{_md_table(gates, None, 30)}

## Interpretation

- 如果 `current_official_payload_ready` 为红灯，不能把 SHFE 当前仓单作为实盘 selector/source feature。
- 如果 legacy shape 为绿灯，只能说明字段结构历史上存在，不能补足当前 PIT。
- 如果 third-party monitor 为绿灯，也只能作为外部观察源，不能替代官方 current payload。
- 本阶段任何绿色 fail-closed gate 都只是纪律保持，不是晋级。
"""
    REPORT_PATH.write_text(report, encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    now_local, _now_utc = _now_pair()

    browser_probe, cookies = collect_browser_probe()
    http_probe, cookie_replay_attempted = append_cookie_replay(collect_http_probe(), cookies)
    ak_probe = collect_akshare_probe()
    route_matrix = build_route_matrix(http_probe, browser_probe, ak_probe)
    gates = build_gates(route_matrix, browser_probe, cookies, cookie_replay_attempted)

    cookies.to_csv(COOKIE_PATH, index=False, encoding="utf-8-sig")
    decision = build_decision(now_local, route_matrix, gates, cookie_replay_attempted)

    http_probe.to_csv(HTTP_PROBE_PATH, index=False, encoding="utf-8-sig")
    browser_probe.to_csv(BROWSER_PROBE_PATH, index=False, encoding="utf-8-sig")
    ak_probe.to_csv(AK_PROBE_PATH, index=False, encoding="utf-8-sig")
    route_matrix.to_csv(ROUTE_MATRIX_PATH, index=False, encoding="utf-8-sig")
    gates.to_csv(GATES_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    write_chart(route_matrix, gates, decision)
    write_report(now_local, route_matrix, gates, decision)

    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
