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
MODEL_TAG = "stage635_lh_monthly_source_fetch_probe_v1"
OUTPUT_PREFIX = "qmt_roll_stage635_lh_monthly_source_fetch_probe"

STAGE634_SOURCE_CONTRACT = (
    OUTPUT_DIR / "qmt_roll_stage634_watchline_source_contract_audit_source_contract_stage634_watchline_source_contract_audit_v1.csv"
)

FETCH_LEDGER_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_fetch_ledger_{MODEL_TAG}.csv"
PRODUCT_STATUS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_status_{MODEL_TAG}.csv"
FIELD_MATRIX_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_field_matrix_{MODEL_TAG}.csv"
GATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gates_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

TIMEOUT_SECONDS = 20
MIN_RESPONSE_BYTES = 500
REQUIRED_PIT_DATES_FOR_SELECTOR = 20
REQUIRED_MONTHLY_SOURCE_ROWS = 2

REFERENCES = [
    "MOA live hog monthly data example: https://www.moa.gov.cn/ztzl/szcpxx/jdsj/2025/202501/",
    "NAHS monthly livestock and feed price bulletin latest example: https://www.nahs.org.cn/jcyj/scxs/202605/t20260519_472251.htm",
    "NAHS livestock market page: https://www.nahs.org.cn/jchsjcm/xqsc/",
    "GitHub fushare fundamentals monitor reference: https://github.com/LowinLi/fushare",
]

FETCH_TARGETS = [
    {
        "product_vt_symbol": "lh.DCE",
        "product_family": "livestock",
        "source_name": "MOA live hog product monthly data",
        "source_url": "https://www.moa.gov.cn/ztzl/szcpxx/jdsj/2025/202501/",
        "source_authority": "government_official",
        "source_class": "monthly_supply_demand_release",
        "release_period": "2025-01",
        "monitor_frequency": "monthly_release",
        "keywords": ["能繁母猪", "定点屠宰", "生猪出场价格", "猪粮比价"],
        "expected_fields": [
            "sow_inventory",
            "slaughter_volume",
            "hog_exit_price",
            "pig_grain_ratio",
        ],
        "point_in_time_rule": "Use received_at/source_url/final_url/raw_sha256 only; do not backfill into selector.",
    },
    {
        "product_vt_symbol": "lh.DCE",
        "product_family": "livestock",
        "source_name": "NAHS monthly livestock and feed price bulletin",
        "source_url": "https://www.nahs.org.cn/jcyj/scxs/202605/t20260519_472251.htm",
        "source_authority": "government_official",
        "source_class": "monthly_price_release",
        "release_period": "2026-04",
        "monitor_frequency": "monthly_release",
        "keywords": ["生猪产品价格", "生猪平均价格", "猪肉平均价格", "猪粮比价", "豆粕"],
        "expected_fields": [
            "piglet_price",
            "hog_market_price",
            "pork_market_price",
            "pig_grain_ratio",
        ],
        "point_in_time_rule": "Use received_at/source_url/final_url/raw_sha256 only; do not backfill into selector.",
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


def _fetch_url(url: str) -> dict[str, Any]:
    headers = {
        "User-Agent": "Mozilla/5.0 stage635-lh-monthly-source-fetch-probe/1.0",
        "Accept": "text/html,text/plain,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.7",
    }
    request = Request(url, headers=headers)
    started = datetime.now(timezone.utc)
    try:
        context = ssl.create_default_context()
        with urlopen(request, timeout=TIMEOUT_SECONDS, context=context) as response:
            body = response.read(3_000_000)
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
        body = error.read(300_000)
        content_type = error.headers.get("content-type", "") if error.headers else ""
        return {
            "fetch_status": "http_error",
            "http_status": int(error.code),
            "final_url": url,
            "content_type": content_type,
            "response_bytes": len(body),
            "elapsed_ms": round((datetime.now(timezone.utc) - started).total_seconds() * 1000, 1),
            "raw_sha256": hashlib.sha256(body).hexdigest() if body else "",
            "text": _decode_body(body, content_type) if body else "",
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
    hits = [keyword for keyword in keywords if keyword.lower() in text.lower()]
    return len(hits), ",".join(hits)


def _extract_float(patterns: list[str], text: str) -> float | None:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.I)
        if match:
            try:
                return float(match.group(1).replace(",", ""))
            except ValueError:
                continue
    return None


def _extract_fields(source_class: str, text: str) -> dict[str, float]:
    if source_class == "monthly_supply_demand_release":
        patterns = {
            "sow_inventory": [r"能繁母猪存栏（万头）\s*([0-9.]+)", r"能繁母猪存栏.*?([0-9]{3,5}(?:\.[0-9]+)?)"],
            "slaughter_volume": [r"屠宰企业屠宰量（万头）\s*([0-9.]+)", r"定点屠宰企业屠宰量.*?([0-9]{3,5}(?:\.[0-9]+)?)"],
            "hog_exit_price": [r"生猪出场价格（元/公斤）\s*([0-9.]+)", r"生猪出场价格.*?([0-9]+(?:\.[0-9]+)?)"],
            "pig_grain_ratio": [r"猪粮比价\s*([0-9.]+)", r"猪粮比.*?([0-9]+(?:\.[0-9]+)?)\s*[:：]?\s*1?"],
        }
    else:
        patterns = {
            "piglet_price": [r"仔猪平均价格\s*([0-9.]+)元/公斤", r"全国仔猪平均价格\s*([0-9.]+)元/公斤"],
            "hog_market_price": [r"生猪平均价格\s*([0-9.]+)元/公斤", r"全国生猪平均价格\s*([0-9.]+)元/公斤"],
            "pork_market_price": [r"猪肉平均价格\s*([0-9.]+)元/公斤", r"全国猪肉平均价格\s*([0-9.]+)元/公斤"],
            "pig_grain_ratio": [r"猪粮比价为\s*([0-9.]+)\s*[:：]\s*1", r"本月猪粮比价为\s*([0-9.]+)\s*[:：]\s*1"],
        }
    values: dict[str, float] = {}
    for field, field_patterns in patterns.items():
        value = _extract_float(field_patterns, text)
        if value is not None:
            values[field] = value
    return values


def _stage634_lh_monthly_contract_rows() -> int:
    if not STAGE634_SOURCE_CONTRACT.exists():
        return 0
    frame = pd.read_csv(STAGE634_SOURCE_CONTRACT, encoding="utf-8-sig")
    frame = frame[
        frame["product_vt_symbol"].astype(str).eq("lh.DCE")
        & frame["cadence"].astype(str).str.contains("monthly", case=False, na=False)
    ]
    return int(len(frame))


def build_fetch_ledger(generated_at: datetime) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    run_id = f"{MODEL_TAG}_{generated_at.strftime('%Y%m%d_%H%M%S')}"
    received_at_local = _fmt_cst(generated_at)
    received_at_utc = generated_at.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for index, target in enumerate(FETCH_TARGETS, start=1):
        result = _fetch_url(target["source_url"])
        cleaned = _clean_text(result["text"])
        keyword_count, keyword_hits = _keyword_hits(cleaned, target["keywords"])
        extracted = _extract_fields(target["source_class"], cleaned)
        extracted_expected_count = sum(1 for field in target["expected_fields"] if field in extracted)
        active_fetch_validated = int(
            result["fetch_status"] == "ok"
            and result["http_status"] == 200
            and int(result["response_bytes"]) >= MIN_RESPONSE_BYTES
            and bool(result["raw_sha256"])
            and keyword_count >= 2
            and extracted_expected_count >= 2
        )
        rows.append(
            {
                "run_id": run_id,
                "row_id": f"stage635_{index:03d}",
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
                "release_period": target["release_period"],
                "monitor_frequency": target["monitor_frequency"],
                "http_status": int(result["http_status"]),
                "fetch_status": result["fetch_status"],
                "fetch_error": result["fetch_error"],
                "content_type": result["content_type"],
                "response_bytes": int(result["response_bytes"]),
                "elapsed_ms": float(result["elapsed_ms"]),
                "raw_sha256": result["raw_sha256"],
                "raw_sha256_present": int(bool(result["raw_sha256"])),
                "keyword_hit_count": keyword_count,
                "keyword_hits": keyword_hits,
                "expected_field_count": len(target["expected_fields"]),
                "extracted_expected_field_count": extracted_expected_count,
                "extracted_fields_json": json.dumps(_json_safe(extracted), ensure_ascii=False, sort_keys=True),
                "active_fetch_validated": active_fetch_validated,
                "usable_for_forward_monitor": active_fetch_validated,
                "usable_for_history_selector": 0,
                "event_signal_ready": 0,
                "paper_or_whitelist_allowed": 0,
                "raw_text_excerpt": cleaned[:260],
                "point_in_time_rule": target["point_in_time_rule"],
                "notes": "Stage-scoped active fetch probe only; no master append and no selector.",
            }
        )
    return pd.DataFrame(rows)


def build_product_status(ledger: pd.DataFrame) -> pd.DataFrame:
    if ledger.empty:
        return pd.DataFrame()
    frame = ledger.copy()
    for column in [
        "active_fetch_validated",
        "raw_sha256_present",
        "response_bytes",
        "usable_for_history_selector",
        "event_signal_ready",
        "paper_or_whitelist_allowed",
    ]:
        frame[column] = _num(frame, column)
    status = frame.groupby(["product_family", "product_vt_symbol"]).agg(
        fetch_rows=("row_id", "count"),
        active_fetch_validated_rows=("active_fetch_validated", "sum"),
        raw_hash_rows=("raw_sha256_present", "sum"),
        total_response_bytes=("response_bytes", "sum"),
        unique_source_classes=("source_class", "nunique"),
        min_extracted_expected_field_count=("extracted_expected_field_count", "min"),
        total_extracted_expected_field_count=("extracted_expected_field_count", "sum"),
        pit_received_dates=("received_at_local", "nunique"),
        history_selector_rows=("usable_for_history_selector", "sum"),
        event_signal_ready_rows=("event_signal_ready", "sum"),
        paper_or_whitelist_rows=("paper_or_whitelist_allowed", "sum"),
    ).reset_index()
    status["monitor_status"] = np.where(
        (status["active_fetch_validated_rows"] >= REQUIRED_MONTHLY_SOURCE_ROWS)
        & (status["raw_hash_rows"] >= REQUIRED_MONTHLY_SOURCE_ROWS),
        "lh_monthly_source_fetch_validated_stage_scoped",
        "lh_monthly_source_fetch_incomplete",
    )
    status["missing_for_selector"] = "20_pit_dates,independent_episodes,predictive_audit,live_tca,live_context"
    status["promotion_allowed"] = 0
    status["paper_allowed"] = 0
    status["trading_whitelist_allowed"] = 0
    return status


def build_field_matrix(ledger: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for _, row in ledger.iterrows():
        extracted = json.loads(row.get("extracted_fields_json", "{}") or "{}")
        for field, value in extracted.items():
            rows.append(
                {
                    "source_name": row["source_name"],
                    "source_class": row["source_class"],
                    "release_period": row["release_period"],
                    "field": field,
                    "value": value,
                    "present": 1,
                }
            )
    return pd.DataFrame(rows)


def build_gates(ledger: pd.DataFrame, status: pd.DataFrame, field_matrix: pd.DataFrame) -> pd.DataFrame:
    contract_rows = _stage634_lh_monthly_contract_rows()
    active_ok = int(_num(ledger, "active_fetch_validated").sum()) if not ledger.empty else 0
    raw_hash = int(_num(ledger, "raw_sha256_present").sum()) if not ledger.empty else 0
    extract_ok = int((_num(ledger, "extracted_expected_field_count") >= 2).sum()) if not ledger.empty else 0
    pit_dates = int(_num(status, "pit_received_dates").max()) if not status.empty else 0
    selector_rows = int(_num(status, "history_selector_rows").sum() + _num(status, "event_signal_ready_rows").sum()) if not status.empty else 0
    whitelist_rows = int(_num(status, "paper_or_whitelist_rows").sum()) if not status.empty else 0
    field_count = int(len(field_matrix))
    rows = [
        {
            "gate": "stage634_lh_monthly_contract_loaded",
            "passed": int(contract_rows >= REQUIRED_MONTHLY_SOURCE_ROWS),
            "current": contract_rows,
            "required": f">={REQUIRED_MONTHLY_SOURCE_ROWS}",
            "note": "Stage634 must provide lh monthly official source contracts.",
        },
        {
            "gate": "official_monthly_targets_fetched_ok",
            "passed": int(active_ok >= REQUIRED_MONTHLY_SOURCE_ROWS),
            "current": active_ok,
            "required": f">={REQUIRED_MONTHLY_SOURCE_ROWS}",
            "note": "MOA and NAHS monthly sources need active fetch validation.",
        },
        {
            "gate": "raw_hash_rows_present",
            "passed": int(raw_hash >= REQUIRED_MONTHLY_SOURCE_ROWS),
            "current": raw_hash,
            "required": f">={REQUIRED_MONTHLY_SOURCE_ROWS}",
            "note": "Each active source must store raw_sha256 for PIT evidence.",
        },
        {
            "gate": "field_extraction_probe_ok",
            "passed": int(extract_ok >= REQUIRED_MONTHLY_SOURCE_ROWS),
            "current": extract_ok,
            "required": f">={REQUIRED_MONTHLY_SOURCE_ROWS}",
            "note": "Probe must extract at least two expected fields per official source.",
        },
        {
            "gate": "extracted_field_rows_present",
            "passed": int(field_count >= 4),
            "current": field_count,
            "required": ">=4",
            "note": "Parsed values are only audit evidence, not selector features yet.",
        },
        {
            "gate": "pit_dates_still_below_selector_threshold",
            "passed": int(pit_dates < REQUIRED_PIT_DATES_FOR_SELECTOR),
            "current": pit_dates,
            "required": f"<{REQUIRED_PIT_DATES_FOR_SELECTOR}",
            "note": "One received_at date cannot unlock selector.",
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
            "note": "Fetch probe cannot create paper or trading whitelist.",
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


def write_chart(ledger: pd.DataFrame, status: pd.DataFrame, field_matrix: pd.DataFrame, gates: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(16, 10))
    fig.suptitle("Stage635 lh monthly official source fetch probe: hashes collected, selector locked", fontsize=15)

    ax = axes[0, 0]
    metrics = [
        "http_ok",
        "bytes_ok",
        "raw_sha256_present",
        "keyword_ok",
        "field_ok",
    ]
    plot = ledger.copy()
    plot["http_ok"] = (plot["http_status"].astype(int) == 200).astype(int)
    plot["bytes_ok"] = (plot["response_bytes"].astype(float) >= MIN_RESPONSE_BYTES).astype(int)
    plot["keyword_ok"] = (plot["keyword_hit_count"].astype(float) >= 2).astype(int)
    plot["field_ok"] = (plot["extracted_expected_field_count"].astype(float) >= 2).astype(int)
    x = np.arange(len(plot))
    width = 0.14
    for idx, metric in enumerate(metrics):
        ax.bar(x + (idx - 2) * width, plot[metric].astype(float), width=width, label=metric)
    ax.set_xticks(x)
    ax.set_xticklabels(plot["source_class"], rotation=10, ha="right")
    ax.set_ylim(0, 1.05)
    ax.set_title("Fetch validation layers")
    ax.legend(loc="upper right", fontsize=8)

    ax = axes[0, 1]
    if field_matrix.empty:
        ax.text(0.5, 0.5, "No parsed fields", ha="center", va="center")
        ax.set_axis_off()
    else:
        pivot = field_matrix.pivot_table(index="field", columns="source_class", values="present", aggfunc="max", fill_value=0)
        image = ax.imshow(pivot.values, aspect="auto", cmap="Greens", vmin=0, vmax=1)
        ax.set_xticks(np.arange(len(pivot.columns)))
        ax.set_xticklabels(pivot.columns, rotation=10, ha="right")
        ax.set_yticks(np.arange(len(pivot.index)))
        ax.set_yticklabels(pivot.index, fontsize=9)
        ax.set_title("Parsed field presence")
        for i in range(pivot.shape[0]):
            for j in range(pivot.shape[1]):
                ax.text(j, i, str(int(pivot.values[i, j])), ha="center", va="center", fontsize=8)
        fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04)

    ax = axes[1, 0]
    if status.empty:
        ax.text(0.5, 0.5, "No product status", ha="center", va="center")
        ax.set_axis_off()
    else:
        status_plot = status[["active_fetch_validated_rows", "raw_hash_rows", "pit_received_dates", "history_selector_rows", "paper_or_whitelist_rows"]].T
        status_plot.columns = status["product_vt_symbol"].tolist()
        status_plot.plot(kind="bar", ax=ax, color=["tab:blue"])
        ax.axhline(REQUIRED_PIT_DATES_FOR_SELECTOR, color="tab:red", linestyle="--", linewidth=1, label="selector PIT threshold")
        ax.set_title("Product status: fetch ok, PIT depth still insufficient")
        ax.set_ylabel("rows / dates")
        ax.tick_params(axis="x", rotation=20)
        ax.legend(loc="upper right", fontsize=8)

    ax = axes[1, 1]
    colors = ["tab:green" if int(item) == 1 else "tab:red" for item in gates["passed"]]
    ax.barh(gates["gate"], gates["passed"], color=colors)
    ax.set_xlim(0, 1)
    ax.set_title("Hard gates: green includes selector locks")
    ax.tick_params(axis="y", labelsize=8)
    for i, row in gates.iterrows():
        ax.text(0.02, i, str(row["current"]), va="center", ha="left", fontsize=8, color="white")

    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(CHART_PATH, dpi=180)
    plt.close(fig)


def write_report(
    generated_at: datetime,
    ledger: pd.DataFrame,
    status: pd.DataFrame,
    field_matrix: pd.DataFrame,
    gates: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    if decision["decision"] == "lh_monthly_source_fetch_validated_stage_scoped_selector_locked":
        interpretation = [
            "- `lh.DCE` 的两个官方月度源已转成 stage-scoped raw-hash/PIT fetch rows，具备进入后续 master append gate 的基础。",
            "- 这仍不是 selector：当前只有一个 received_at 日期，没有独立 episode、预测力审计和 live TCA。",
            "- parsed fields 只是解析探针，后续必须固定字段 schema、幂等追加 master PIT ledger，再累计至少 20 个 received_at 日期。",
        ]
    elif decision["decision"] == "lh_monthly_source_hash_validated_parser_needs_repair_selector_locked":
        interpretation = [
            "- `lh.DCE` 的官方月度源已拿到 raw hash，但字段解析还不完整，只能作为 source 可达性证据。",
            "- 下一步应修 parser/schema，不允许把未稳定解析的字段接入 selector。",
            "- selector、paper、白名单继续锁定。",
        ]
    else:
        interpretation = [
            "- 本轮未拿到 MOA/NAHS raw hash，不能证明 `lh.DCE` 官方月度源可自动化使用。",
            "- 如果错误来自 DNS/沙箱网络，需要在有外部网络权限的环境重跑；如果外部网络仍失败，则源路线需降级或换官方入口。",
            "- selector、paper、白名单继续锁定。",
        ]
    lines = [
        "# Stage635 lh Monthly Source Fetch Probe Report",
        "",
        f"- line_id: `{LINE_ID}`",
        f"- generated_at_cst: `{_fmt_cst(generated_at)}`",
        f"- decision: `{decision['decision']}`",
        "- stage nature: active official source fetch probe; stage-scoped only; no master append, no selector, no paper, no whitelist, no CTP.",
        "",
        "## External Research And Judgement",
        "",
        "References:",
        *[f"- {item}" for item in REFERENCES],
        "",
        "Judgement:",
        "- MOA live hog monthly data is a stronger PIT source than a static product note because it exposes month-tagged supply, slaughter, price and pig-grain-ratio fields.",
        "- NAHS monthly livestock/feed bulletins are also usable as a forward monitor source because they publish dated monthly price text with hog, pork, piglet and pig-grain-ratio context.",
        "- GitHub/fushare confirms that China futures fundamental monitors commonly persist data locally on a schedule, but it does not replace the need for official live-hog raw-hash evidence.",
        "",
        "## Key Numbers",
        "",
        f"- monthly source targets: `{decision['monthly_source_targets']}`",
        f"- active fetch validated rows: `{decision['active_fetch_validated_rows']}`",
        f"- raw hash rows: `{decision['raw_hash_rows']}`",
        f"- extracted field rows: `{decision['extracted_field_rows']}`",
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
                "source_name",
                "source_class",
                "release_period",
                "http_status",
                "fetch_status",
                "response_bytes",
                "raw_sha256_present",
                "keyword_hit_count",
                "keyword_hits",
                "extracted_expected_field_count",
                "active_fetch_validated",
                "usable_for_history_selector",
                "paper_or_whitelist_allowed",
            ],
        ),
        "",
        "## Product Status",
        "",
        _md_table(status),
        "",
        "## Parsed Fields",
        "",
        _md_table(field_matrix),
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
    generated_at = _now_cst()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ledger = build_fetch_ledger(generated_at)
    status = build_product_status(ledger)
    field_matrix = build_field_matrix(ledger)
    gates = build_gates(ledger, status, field_matrix)
    active_fetch_validated_rows = int(_num(ledger, "active_fetch_validated").sum()) if not ledger.empty else 0
    raw_hash_rows = int(_num(ledger, "raw_sha256_present").sum()) if not ledger.empty else 0
    extracted_field_rows = int(len(field_matrix))
    pit_dates_now = int(_num(status, "pit_received_dates").max()) if not status.empty else 0
    selector_rows = int(_num(status, "history_selector_rows").sum() + _num(status, "event_signal_ready_rows").sum()) if not status.empty else 0
    paper_rows = int(_num(status, "paper_or_whitelist_rows").sum()) if not status.empty else 0
    if active_fetch_validated_rows >= REQUIRED_MONTHLY_SOURCE_ROWS and extracted_field_rows >= 4:
        decision_label = "lh_monthly_source_fetch_validated_stage_scoped_selector_locked"
    elif raw_hash_rows >= REQUIRED_MONTHLY_SOURCE_ROWS:
        decision_label = "lh_monthly_source_hash_validated_parser_needs_repair_selector_locked"
    else:
        decision_label = "lh_monthly_source_fetch_probe_failed_selector_locked"
    decision = {
        "decision": decision_label,
        "generated_at_cst": _fmt_cst(generated_at),
        "line_id": LINE_ID,
        "monthly_source_targets": int(len(FETCH_TARGETS)),
        "active_fetch_validated_rows": active_fetch_validated_rows,
        "raw_hash_rows": raw_hash_rows,
        "extracted_field_rows": extracted_field_rows,
        "pit_dates_now": pit_dates_now,
        "selector_rows": selector_rows,
        "paper_or_whitelist_rows": paper_rows,
        "hard_gates_passed": int(gates["passed"].sum()),
        "hard_gates_total": int(len(gates)),
        "fetch_ledger_path": str(FETCH_LEDGER_PATH),
        "product_status_path": str(PRODUCT_STATUS_PATH),
        "field_matrix_path": str(FIELD_MATRIX_PATH),
        "chart_path": str(CHART_PATH),
    }

    ledger.to_csv(FETCH_LEDGER_PATH, index=False, encoding="utf-8-sig")
    status.to_csv(PRODUCT_STATUS_PATH, index=False, encoding="utf-8-sig")
    field_matrix.to_csv(FIELD_MATRIX_PATH, index=False, encoding="utf-8-sig")
    gates.to_csv(GATES_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_report(generated_at, ledger, status, field_matrix, gates, decision)
    write_chart(ledger, status, field_matrix, gates)
    print(json.dumps(_json_safe(decision), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
