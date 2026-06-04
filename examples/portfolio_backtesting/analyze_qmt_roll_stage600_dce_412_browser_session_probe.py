from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
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


MODEL_TAG = "stage600_dce_412_browser_session_probe_v1"
OUTPUT_PREFIX = "qmt_roll_stage600_dce_412_browser_session_probe"
LINE_ID = "futures_trend_drawdown30_preserve_return"

HTTP_PROBE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_http_probe_{MODEL_TAG}.csv"
BROWSER_PROBE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_browser_probe_{MODEL_TAG}.csv"
COOKIE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_browser_cookies_{MODEL_TAG}.csv"
GATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gates_{MODEL_TAG}.csv"
NEXT_ACTIONS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_next_actions_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"
BROWSER_SCREENSHOT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_browser_page_{MODEL_TAG}.png"

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)

HTTP_TIMEOUT = 12
BROWSER_TIMEOUT_SECONDS = 150
NPM_INSTALL_TIMEOUT_SECONDS = 120
PROBE_DATE = "20260603"

DCE_HOME = "http://www.dce.com.cn"
DCE_HOME_HTTPS = "https://www.dce.com.cn"
DCE_WAREHOUSE_PAGE = "http://www.dce.com.cn/dalianshangpin/xqsj/tjsj26/rtj/cdrb/index.html"
DCE_MEMBER_PAGE = "http://www.dce.com.cn/dalianshangpin/xqsj/tjsj26/rtj/rcjccpm/index.html"
DCE_EXT_PORTAL = "https://extportal.dce.com.cn/file/pc/index.html"
DCE_WAREHOUSE_ENDPOINT = "http://www.dce.com.cn/dcereport/publicweb/dailystat/wbillWeeklyQuotes"
DCE_MEMBER_ENDPOINT = "http://www.dce.com.cn/dcereport/publicweb/dailystat/memberDealPosi/batchDownload"

WAREHOUSE_PAYLOAD = {"tradeDate": PROBE_DATE, "varietyId": "all"}
MEMBER_PAYLOAD = {
    "tradeDate": PROBE_DATE,
    "varietyId": "a",
    "contractId": "a2601",
    "tradeType": "1",
    "lang": "zh",
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


def _body_head(content: bytes, limit: int = 260) -> str:
    text = content[:limit].decode("utf-8", errors="replace")
    return " ".join(text.split())


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
    return now_utc.astimezone(ZoneInfo("Asia/Shanghai")), now_utc


def _classify_content(response: requests.Response | None, content: bytes) -> dict[str, Any]:
    result = {
        "is_json": 0,
        "json_top_keys": "",
        "entity_count": 0,
        "is_zip": int(content.startswith(b"PK")),
        "challenge_like": 0,
        "dce_412_marker": 0,
    }
    text = content.decode("utf-8", errors="ignore")
    if response is not None and response.status_code == 412:
        result["dce_412_marker"] = 1
        result["challenge_like"] = 1
    if "9wq7NOeAWkjr" in text or "HTTP 412" in text or "412" in text[:1000]:
        result["challenge_like"] = 1
    try:
        parsed = json.loads(text)
        result["is_json"] = 1
        if isinstance(parsed, dict):
            result["json_top_keys"] = ",".join([str(key) for key in parsed.keys()])
            data = parsed.get("data")
            if isinstance(data, dict) and isinstance(data.get("entityList"), list):
                result["entity_count"] = len(data["entityList"])
        elif isinstance(parsed, list):
            result["json_top_keys"] = "list"
            result["entity_count"] = len(parsed)
    except Exception:
        pass
    return result


def _request_row(
    session: requests.Session,
    phase: str,
    name: str,
    method: str,
    url: str,
    expected: str,
    json_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    row = {
        "phase": phase,
        "probe_name": name,
        "method": method,
        "url": url,
        "expected": expected,
        "status": "not_run",
        "http_status": 0,
        "final_url": "",
        "content_type": "",
        "content_length": 0,
        "elapsed_ms": np.nan,
        "cookie_count": 0,
        "is_json": 0,
        "json_top_keys": "",
        "entity_count": 0,
        "is_zip": 0,
        "challenge_like": 0,
        "dce_412_marker": 0,
        "body_head": "",
        "error_type": "",
        "error_message": "",
        "raw_sha256": "",
    }
    started = datetime.now(timezone.utc)
    try:
        headers = {"User-Agent": USER_AGENT, "Accept": "application/json,text/html,application/xhtml+xml,*/*"}
        if method.upper() == "POST":
            response = session.post(url, json=json_payload, headers=headers, timeout=HTTP_TIMEOUT)
        else:
            response = session.get(url, headers=headers, timeout=HTTP_TIMEOUT)
        elapsed_ms = (datetime.now(timezone.utc) - started).total_seconds() * 1000.0
        content = response.content or b""
        classification = _classify_content(response, content)
        ok = False
        if expected == "html":
            ok = response.status_code == 200 and len(content) > 100
        elif expected == "json":
            ok = response.status_code == 200 and classification["is_json"] == 1 and classification["entity_count"] > 0
        elif expected == "zip":
            ok = response.status_code == 200 and classification["is_zip"] == 1
        row.update(
            {
                "status": "ok" if ok else "blocked_or_wrong_format",
                "http_status": int(response.status_code),
                "final_url": str(response.url),
                "content_type": response.headers.get("Content-Type", ""),
                "content_length": int(len(content)),
                "elapsed_ms": elapsed_ms,
                "cookie_count": int(len(session.cookies)),
                "body_head": _body_head(content),
                "raw_sha256": hashlib.sha256(content).hexdigest(),
                **classification,
            }
        )
    except Exception as exc:
        elapsed_ms = (datetime.now(timezone.utc) - started).total_seconds() * 1000.0
        row.update(
            {
                "status": "error",
                "elapsed_ms": elapsed_ms,
                "cookie_count": int(len(session.cookies)),
                "error_type": type(exc).__name__,
                "error_message": str(exc)[:700],
            }
        )
    return row


def collect_http_session_probes() -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    direct = requests.Session()
    rows.append(_request_row(direct, "direct", "warehouse_post_no_cookie", "POST", DCE_WAREHOUSE_ENDPOINT, "json", WAREHOUSE_PAYLOAD))
    rows.append(_request_row(direct, "direct", "member_post_no_cookie", "POST", DCE_MEMBER_ENDPOINT, "zip", MEMBER_PAYLOAD))

    session = requests.Session()
    for name, url in [
        ("home_http", DCE_HOME),
        ("home_https", DCE_HOME_HTTPS),
        ("warehouse_page", DCE_WAREHOUSE_PAGE),
        ("member_page", DCE_MEMBER_PAGE),
        ("ext_portal", DCE_EXT_PORTAL),
    ]:
        rows.append(_request_row(session, "session_warmup", name, "GET", url, "html"))
    rows.append(_request_row(session, "after_session_warmup", "warehouse_post_after_pages", "POST", DCE_WAREHOUSE_ENDPOINT, "json", WAREHOUSE_PAYLOAD))
    rows.append(_request_row(session, "after_session_warmup", "member_post_after_pages", "POST", DCE_MEMBER_ENDPOINT, "zip", MEMBER_PAYLOAD))
    return pd.DataFrame(rows)


def append_browser_cookie_replay(http_probe: pd.DataFrame, cookies: pd.DataFrame) -> pd.DataFrame:
    if cookies.empty or "name" not in cookies.columns or "value" not in cookies.columns:
        return http_probe
    session = requests.Session()
    for _, row in cookies.iterrows():
        name = str(row.get("name", ""))
        value = str(row.get("value", ""))
        if not name or not value:
            continue
        kwargs: dict[str, Any] = {}
        if pd.notna(row.get("domain", np.nan)):
            kwargs["domain"] = str(row.get("domain"))
        if pd.notna(row.get("path", np.nan)):
            kwargs["path"] = str(row.get("path"))
        session.cookies.set(name, value, **kwargs)
    rows = [
        _request_row(session, "browser_cookie_replay", "warehouse_post_with_browser_cookies", "POST", DCE_WAREHOUSE_ENDPOINT, "json", WAREHOUSE_PAYLOAD),
        _request_row(session, "browser_cookie_replay", "member_post_with_browser_cookies", "POST", DCE_MEMBER_ENDPOINT, "zip", MEMBER_PAYLOAD),
    ]
    return pd.concat([http_probe, pd.DataFrame(rows)], ignore_index=True)


def _node_script() -> str:
    screenshot = str(BROWSER_SCREENSHOT_PATH)
    return textwrap.dedent(
        f"""
        import {{ chromium }} from 'playwright';
        const screenshotPath = {json.dumps(screenshot)};
        const userAgent = {json.dumps(USER_AGENT)};
        const probeDate = {json.dumps(PROBE_DATE)};
        const warehousePayload = {json.dumps(WAREHOUSE_PAYLOAD)};
        const memberPayload = {json.dumps(MEMBER_PAYLOAD)};
        const urls = {{
          home: {json.dumps(DCE_HOME)},
          warehousePage: {json.dumps(DCE_WAREHOUSE_PAGE)},
          memberPage: {json.dumps(DCE_MEMBER_PAGE)},
          warehouseEndpoint: {json.dumps(DCE_WAREHOUSE_ENDPOINT)},
          memberEndpoint: {json.dumps(DCE_MEMBER_ENDPOINT)}
        }};

        function head(text, n=260) {{
          return String(text || '').slice(0, n).replace(/\\s+/g, ' ').trim();
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

        async function pageFetch(page, endpoint, expected, payload, name) {{
          const started = Date.now();
          try {{
            const out = await page.evaluate(async (args) => {{
              const response = await fetch(args.endpoint, {{
                method: 'POST',
                headers: {{
                  'Content-Type': 'application/json',
                  'Accept': 'application/json,application/zip,text/html,*/*'
                }},
                body: JSON.stringify(args.payload)
              }});
              const text = await response.text();
              return {{
                status: response.status,
                contentType: response.headers.get('content-type') || '',
                text,
              }};
            }}, {{ endpoint, payload }});
            const text = out.text || '';
            let isJson = 0;
            let entityCount = 0;
            let jsonTopKeys = '';
            try {{
              const parsed = JSON.parse(text);
              isJson = 1;
              if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {{
                jsonTopKeys = Object.keys(parsed).join(',');
                if (parsed.data && Array.isArray(parsed.data.entityList)) {{
                  entityCount = parsed.data.entityList.length;
                }}
              }} else if (Array.isArray(parsed)) {{
                jsonTopKeys = 'list';
                entityCount = parsed.length;
              }}
            }} catch (_err) {{}}
            const isZip = text.startsWith('PK') ? 1 : 0;
            const challengeLike = (out.status === 412 || text.includes('9wq7NOeAWkjr')) ? 1 : 0;
            const ok = expected === 'json' ? (out.status === 200 && isJson && entityCount > 0) : (out.status === 200 && isZip);
            return {{
              probe_name: name,
              status: ok ? 'ok' : 'blocked_or_wrong_format',
              http_status: out.status,
              content_type: out.contentType,
              content_length: text.length,
              elapsed_ms: Date.now() - started,
              is_json: isJson,
              json_top_keys: jsonTopKeys,
              entity_count: entityCount,
              is_zip: isZip,
              challenge_like: challengeLike,
              dce_412_marker: out.status === 412 ? 1 : 0,
              body_head: head(text),
              error_type: '',
              error_message: '',
            }};
          }} catch (err) {{
            return {{
              probe_name: name,
              status: 'error',
              http_status: 0,
              content_type: '',
              content_length: 0,
              elapsed_ms: Date.now() - started,
              is_json: 0,
              json_top_keys: '',
              entity_count: 0,
              is_zip: 0,
              challenge_like: 0,
              dce_412_marker: 0,
              body_head: '',
              error_type: err && err.name ? err.name : 'Error',
              error_message: String(err && err.message ? err.message : err).slice(0, 700),
            }};
          }}
        }}

        const result = {{
          status: 'not_run',
          launch_options: '',
          page_title: '',
          final_url: '',
          screenshot_path: screenshotPath,
          cookies: [],
          page_steps: [],
          endpoint_probes: [],
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
          for (const [name, url] of [['home', urls.home], ['warehouse_page', urls.warehousePage], ['member_page', urls.memberPage]]) {{
            const started = Date.now();
            try {{
              const response = await page.goto(url, {{ waitUntil: 'domcontentloaded', timeout: 20000 }});
              await page.waitForTimeout(2500);
              result.page_steps.push({{
                name,
                url,
                status: response ? response.status() : 0,
                final_url: page.url(),
                title: await page.title(),
                elapsed_ms: Date.now() - started,
              }});
            }} catch (err) {{
              result.page_steps.push({{
                name,
                url,
                status: 0,
                final_url: page.url(),
                title: await page.title().catch(() => ''),
                elapsed_ms: Date.now() - started,
                error_type: err && err.name ? err.name : 'Error',
                error_message: String(err && err.message ? err.message : err).slice(0, 700),
              }});
            }}
          }}
          result.page_title = await page.title();
          result.final_url = page.url();
          await page.screenshot({{ path: screenshotPath, fullPage: true }}).catch(() => null);
          result.cookies = await context.cookies();
          result.endpoint_probes.push(await pageFetch(page, urls.warehouseEndpoint, 'json', warehousePayload, 'browser_fetch_warehouse_json'));
          result.endpoint_probes.push(await pageFetch(page, urls.memberEndpoint, 'zip', memberPayload, 'browser_fetch_member_zip'));
          result.status = 'ok';
          await browser.close();
        }} catch (err) {{
          result.status = 'error';
          result.error_type = err && err.name ? err.name : 'Error';
          result.error_message = String(err && err.message ? err.message : err).slice(0, 1200);
          if (browser) {{
            await browser.close().catch(() => null);
          }}
        }}
        console.log(JSON.stringify(result));
        """
    )


def collect_browser_probe() -> tuple[pd.DataFrame, pd.DataFrame]:
    node = shutil.which("node")
    npm = shutil.which("npm")
    base = {
        "tool": "playwright_temp_npm",
        "npx_path": npm or "",
        "browser_status": "not_run",
        "launch_options": "",
        "page_title": "",
        "final_url": "",
        "screenshot_path": str(BROWSER_SCREENSHOT_PATH),
        "probe_name": "",
        "status": "not_run",
        "http_status": 0,
        "content_type": "",
        "content_length": 0,
        "elapsed_ms": np.nan,
        "is_json": 0,
        "json_top_keys": "",
        "entity_count": 0,
        "is_zip": 0,
        "challenge_like": 0,
        "dce_412_marker": 0,
        "body_head": "",
        "error_type": "",
        "error_message": "",
    }
    if not node or not npm:
        return pd.DataFrame([{**base, "browser_status": "missing_node_or_npm", "status": "error", "error_type": "MissingNodeOrNpm"}]), pd.DataFrame()

    with tempfile.TemporaryDirectory(prefix="stage600_dce_") as tmpdir:
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
        cmd = [node, str(script_path)]
        try:
            proc = subprocess.run(
                cmd,
                cwd=str(tmp_path),
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=BROWSER_TIMEOUT_SECONDS,
                check=False,
            )
        except Exception as exc:
            return (
                pd.DataFrame(
                    [
                        {
                            **base,
                            "browser_status": "subprocess_error",
                            "status": "error",
                            "error_type": type(exc).__name__,
                            "error_message": str(exc)[:1200],
                        }
                    ]
                ),
                pd.DataFrame(),
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
                        "error_type": "NpxProcessFailed",
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
    endpoint_probes = data.get("endpoint_probes") or []
    if endpoint_probes:
        for item in endpoint_probes:
            rows.append(
                {
                    **base,
                    "browser_status": data.get("status", ""),
                    "launch_options": data.get("launch_options", ""),
                    "page_title": data.get("page_title", ""),
                    "final_url": data.get("final_url", ""),
                    **{key: item.get(key, base.get(key, "")) for key in [
                        "probe_name",
                        "status",
                        "http_status",
                        "content_type",
                        "content_length",
                        "elapsed_ms",
                        "is_json",
                        "json_top_keys",
                        "entity_count",
                        "is_zip",
                        "challenge_like",
                        "dce_412_marker",
                        "body_head",
                        "error_type",
                        "error_message",
                    ]},
                }
            )
    else:
        rows.append(
            {
                **base,
                "browser_status": data.get("status", ""),
                "status": "error",
                "error_type": data.get("error_type", ""),
                "error_message": data.get("error_message", ""),
                "launch_options": data.get("launch_options", ""),
                "page_title": data.get("page_title", ""),
                "final_url": data.get("final_url", ""),
            }
        )
    cookies = pd.DataFrame(data.get("cookies") or [])
    if cookies.empty:
        cookies = pd.DataFrame(columns=["name", "domain", "path", "expires", "httpOnly", "secure", "sameSite"])
    return pd.DataFrame(rows), cookies


def build_gates(http_probe: pd.DataFrame, browser_probe: pd.DataFrame, cookies: pd.DataFrame) -> pd.DataFrame:
    direct_412 = int(
        len(
            http_probe[
                http_probe["phase"].eq("direct")
                & http_probe["dce_412_marker"].eq(1)
            ]
        )
    )
    warmup_success = int(len(http_probe[(http_probe["phase"].eq("session_warmup")) & (http_probe["http_status"].eq(200))]))
    post_after_ready = int(len(http_probe[(http_probe["phase"].eq("after_session_warmup")) & http_probe["status"].eq("ok")]))
    browser_available = int(len(browser_probe[browser_probe["browser_status"].eq("ok")]) > 0)
    browser_cookie_count = int(len(cookies))
    browser_warehouse_ready = int(len(browser_probe[(browser_probe["probe_name"].eq("browser_fetch_warehouse_json")) & browser_probe["status"].eq("ok")]) > 0)
    browser_member_ready = int(len(browser_probe[(browser_probe["probe_name"].eq("browser_fetch_member_zip")) & browser_probe["status"].eq("ok")]) > 0)
    gates = [
        {
            "gate": "direct_requests_reproduced_412",
            "required": "direct requests must reproduce Stage299 blocker",
            "value": direct_412,
            "threshold": 2,
            "passed": int(direct_412 >= 2),
            "hard_gate": 0,
        },
        {
            "gate": "dce_pages_reachable_before_api",
            "required": "at least one DCE public page reachable",
            "value": warmup_success,
            "threshold": 1,
            "passed": int(warmup_success >= 1),
            "hard_gate": 1,
        },
        {
            "gate": "requests_session_cookie_solves_api",
            "required": "requests.Session warmup makes official endpoint usable",
            "value": post_after_ready,
            "threshold": 2,
            "passed": int(post_after_ready >= 2),
            "hard_gate": 1,
        },
        {
            "gate": "playwright_browser_available",
            "required": "npx playwright can launch a real browser",
            "value": browser_available,
            "threshold": 1,
            "passed": browser_available,
            "hard_gate": 1,
        },
        {
            "gate": "browser_cookies_observed",
            "required": "browser page creates observable cookies/session state",
            "value": browser_cookie_count,
            "threshold": 1,
            "passed": int(browser_cookie_count >= 1),
            "hard_gate": 1,
        },
        {
            "gate": "browser_warehouse_fetch_ready",
            "required": "browser-context fetch returns warehouse JSON rows",
            "value": browser_warehouse_ready,
            "threshold": 1,
            "passed": browser_warehouse_ready,
            "hard_gate": 1,
        },
        {
            "gate": "browser_member_fetch_ready",
            "required": "browser-context fetch returns member zip",
            "value": browser_member_ready,
            "threshold": 1,
            "passed": browser_member_ready,
            "hard_gate": 1,
        },
        {
            "gate": "no_strategy_backtest_or_parameter_search",
            "required": "source forensic only",
            "value": 1,
            "threshold": 1,
            "passed": 1,
            "hard_gate": 1,
        },
    ]
    return pd.DataFrame(gates)


def build_next_actions(gates: pd.DataFrame) -> pd.DataFrame:
    browser_ready = bool(gates.loc[gates["gate"].eq("browser_warehouse_fetch_ready"), "passed"].sum()) and bool(
        gates.loc[gates["gate"].eq("browser_member_fetch_ready"), "passed"].sum()
    )
    if browser_ready:
        actions = [
            {
                "priority": "P0",
                "action": "Freeze browser-cookie official source collector and write point-in-time ledger rows",
                "reason": "Browser context can access DCE endpoints that direct requests cannot.",
                "promotion_effect": "Moves j/i official route from blocked to forward-ledger candidate, still no alpha promotion.",
            },
            {
                "priority": "P1",
                "action": "Run 20 cross-day received_at samples before any predictive audit",
                "reason": "A working source is not enough; selector needs forward sample depth.",
                "promotion_effect": "Preserves no-backfill discipline.",
            },
        ]
    else:
        actions = [
            {
                "priority": "P0",
                "action": "Do not promote j/i; browser/session did not close DCE official route",
                "reason": "Official API remains unusable for automated point-in-time collection.",
                "promotion_effect": "Keeps black_ferrous as source/TCA worklist only.",
            },
            {
                "priority": "P0",
                "action": "Search for authorized DCE data channel or exchange-published alternate downloadable route",
                "reason": "Bypassing an official anti-bot page is not robust enough for live strategy evidence.",
                "promotion_effect": "Needed before any official member/warehouse feature can be used.",
            },
            {
                "priority": "P1",
                "action": "Keep third-party basis/inventory as monitor only",
                "reason": "Third-party availability cannot replace official source and TCA gates.",
                "promotion_effect": "Avoids false alpha confidence.",
            },
        ]
    actions.append(
        {
            "priority": "P1",
            "action": "No j/i paper, A/B, whitelist, or return backtest from this stage",
            "reason": "This stage only tests source executability.",
            "promotion_effect": "Prevents overfitting to a data plumbing experiment.",
        }
    )
    return pd.DataFrame(actions)


def write_chart(http_probe: pd.DataFrame, browser_probe: pd.DataFrame, cookies: pd.DataFrame, gates: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(16, 10))
    fig.suptitle("Stage600 DCE 412 Browser Session Probe", fontsize=15, fontweight="bold")

    ax = axes[0, 0]
    http_summary = http_probe.copy()
    status_score = {"ok": 1.0, "blocked_or_wrong_format": 0.35, "error": 0.0}
    http_summary["score"] = http_summary["status"].map(status_score).fillna(0.0)
    labels = http_summary["phase"] + "\n" + http_summary["probe_name"]
    colors = ["#2f855a" if score >= 1 else "#dd6b20" if score > 0 else "#c53030" for score in http_summary["score"]]
    ax.barh(labels, http_summary["score"], color=colors)
    ax.set_xlim(0, 1.05)
    ax.set_title("Requests / Session HTTP probes")
    ax.set_xlabel("1=usable, 0.35=response wrong format")

    ax = axes[0, 1]
    browser_view = browser_probe.copy()
    if browser_view.empty:
        browser_view = pd.DataFrame([{"probe_name": "browser_missing", "status": "error", "http_status": 0, "score": 0.0}])
    browser_view["score"] = browser_view["status"].map(status_score).fillna(0.0)
    colors = ["#2f855a" if score >= 1 else "#dd6b20" if score > 0 else "#c53030" for score in browser_view["score"]]
    ax.barh(browser_view["probe_name"], browser_view["score"], color=colors)
    for i, row in browser_view.reset_index(drop=True).iterrows():
        ax.text(float(row["score"]) + 0.02, i, f"HTTP {int(row.get('http_status', 0) or 0)}", va="center", fontsize=9)
    ax.set_xlim(0, 1.2)
    ax.set_title("Browser-context endpoint fetch")
    ax.set_xlabel("1=usable")

    ax = axes[1, 0]
    gate_view = gates.copy()
    colors = ["#2f855a" if item else "#c53030" for item in gate_view["passed"]]
    ax.barh(gate_view["gate"], gate_view["passed"], color=colors)
    ax.set_xlim(0, 1.2)
    ax.set_title("Source executability gates")

    ax = axes[1, 1]
    cookie_count = len(cookies)
    challenge_count = int(http_probe["challenge_like"].sum()) + int(browser_probe["challenge_like"].sum() if not browser_probe.empty else 0)
    values = [cookie_count, challenge_count]
    ax.bar(["browser cookies", "challenge markers"], values, color=["#3182ce", "#dd6b20"])
    ax.set_title("Session artifacts vs anti-bot markers")
    ax.set_ylabel("count")
    for i, value in enumerate(values):
        ax.text(i, value + 0.05, str(value), ha="center")

    hard = gates[gates["hard_gate"].eq(1)]
    fig.text(0.01, 0.01, f"Hard gates passed: {int(hard['passed'].sum())}/{len(hard)}. No strategy backtest or parameter search.", fontsize=10)
    fig.tight_layout(rect=[0, 0.03, 1, 0.95])
    fig.savefig(CHART_PATH, dpi=150)
    plt.close(fig)


def write_report(
    now_local: datetime,
    http_probe: pd.DataFrame,
    browser_probe: pd.DataFrame,
    cookies: pd.DataFrame,
    gates: pd.DataFrame,
    next_actions: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    report = f"""# Stage600 DCE 412 Browser Session Probe

- line_id: `{LINE_ID}`
- observed_at: `{now_local.isoformat(timespec="seconds")}`
- decision: `{decision["decision"]}`
- promotion_allowed: `{decision["promotion_allowed"]}`
- paper_selector_allowed: `{decision["paper_selector_allowed"]}`
- trading_whitelist_allowed: `{decision["trading_whitelist_allowed"]}`

## Scope

This stage tests whether a browser/cookie session can convert DCE `HTTP 412` official routes into a stable point-in-time data source. It does not run strategy returns and does not alter any product whitelist.

## HTTP Session Probes

{_md_table(http_probe, ["phase", "probe_name", "status", "http_status", "content_type", "cookie_count", "is_json", "entity_count", "is_zip", "challenge_like", "dce_412_marker", "body_head"], 30)}

## Browser Probes

{_md_table(browser_probe, ["browser_status", "launch_options", "page_title", "final_url", "probe_name", "status", "http_status", "content_type", "is_json", "entity_count", "is_zip", "challenge_like", "dce_412_marker", "error_type", "error_message", "body_head"], 20)}

## Browser Cookies

{_md_table(cookies, ["name", "domain", "path", "expires", "httpOnly", "secure", "sameSite"], 20)}

## Gates

{_md_table(gates, None, 20)}

## Next Actions

{_md_table(next_actions, None, 20)}
"""
    REPORT_PATH.write_text(report, encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    now_local, now_utc = _now_pair()

    browser_probe, cookies = collect_browser_probe()
    http_probe = append_browser_cookie_replay(collect_http_session_probes(), cookies)
    gates = build_gates(http_probe, browser_probe, cookies)
    next_actions = build_next_actions(gates)

    hard = gates[gates["hard_gate"].eq(1)]
    browser_ready = bool(
        gates.loc[gates["gate"].eq("browser_warehouse_fetch_ready"), "passed"].sum()
        and gates.loc[gates["gate"].eq("browser_member_fetch_ready"), "passed"].sum()
    )
    decision = {
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "observed_at_local": now_local.isoformat(timespec="seconds"),
        "observed_at_utc": now_utc.isoformat(timespec="seconds"),
        "decision": "dce_browser_session_source_candidate_no_paper" if browser_ready else "dce_browser_session_not_ready_official_source_blocked",
        "promotion_allowed": False,
        "paper_selector_allowed": False,
        "trading_whitelist_allowed": False,
        "hard_gates_passed": int(hard["passed"].sum()),
        "hard_gates_total": int(len(hard)),
        "browser_ready": browser_ready,
        "browser_cookie_count": int(len(cookies)),
        "http_probe_count": int(len(http_probe)),
        "browser_probe_count": int(len(browser_probe)),
        "outputs": {
            "http_probe": str(HTTP_PROBE_PATH),
            "browser_probe": str(BROWSER_PROBE_PATH),
            "browser_cookies": str(COOKIE_PATH),
            "gates": str(GATES_PATH),
            "next_actions": str(NEXT_ACTIONS_PATH),
            "report": str(REPORT_PATH),
            "chart": str(CHART_PATH),
            "browser_screenshot": str(BROWSER_SCREENSHOT_PATH),
        },
    }

    http_probe.to_csv(HTTP_PROBE_PATH, index=False)
    browser_probe.to_csv(BROWSER_PROBE_PATH, index=False)
    cookies.to_csv(COOKIE_PATH, index=False)
    gates.to_csv(GATES_PATH, index=False)
    next_actions.to_csv(NEXT_ACTIONS_PATH, index=False)
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    write_chart(http_probe, browser_probe, cookies, gates)
    write_report(now_local, http_probe, browser_probe, cookies, gates, next_actions, decision)

    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
