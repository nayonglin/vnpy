from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
from io import StringIO
import sys
import time
from typing import Any

import numpy as np
import pandas as pd
import requests


ROOT = Path(__file__).resolve().parents[4]
LINE_ID = "futures_trend_rebuilt_c9_15w_v2_optimization"
STAGE = "Stage090"
MODEL_TAG = "stage090_gtja_jd_margin_batch_gate_v1"
OUTPUT_PREFIX = "rebuilt_c9_v2_stage090_gtja_jd_margin_batch_gate"

LINE_DIR = ROOT / "research" / "lines" / LINE_ID
OUT = LINE_DIR / "outputs" / "stage090_gtja_jd_margin_batch_gate"
STAGES_DIR = LINE_DIR / "stages"

STAGE020_PRODUCT_RETURNS = (
    LINE_DIR
    / "outputs/stage020_sqlite_jd_repair_xsmom_inputs/"
    / "rebuilt_c9_v2_stage020_sqlite_jd_repair_xsmom_inputs_product_returns_stage020_sqlite_jd_repair_xsmom_inputs_v1.csv"
)

SOURCE_AUDIT_PATH = OUT / f"{OUTPUT_PREFIX}_source_audit_{MODEL_TAG}.csv"
REQUIRED_JD_DAYS_PATH = OUT / f"{OUTPUT_PREFIX}_required_jd_days_{MODEL_TAG}.csv"
GTJA_DATE_AUDIT_PATH = OUT / f"{OUTPUT_PREFIX}_gtja_date_audit_{MODEL_TAG}.csv"
GTJA_ADJUSTMENTS_PATH = OUT / f"{OUTPUT_PREFIX}_gtja_adjustments_{MODEL_TAG}.csv"
CANDIDATE_DAILY_MARGIN_PATH = OUT / f"{OUTPUT_PREFIX}_candidate_daily_margin_{MODEL_TAG}.csv"
COVERAGE_SUMMARY_PATH = OUT / f"{OUTPUT_PREFIX}_coverage_summary_{MODEL_TAG}.csv"
INPUT_AUDIT_PATH = OUT / f"{OUTPUT_PREFIX}_input_audit_{MODEL_TAG}.csv"
DECISION_PATH = OUT / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUT / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

GTJA_PC_CALENDAR_URL = "https://www.gtjaqh.com/pc/calendar"
REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

EXTERNAL_RESEARCH = [
    {
        "source_id": "gtja_calendar_public_page",
        "url": "https://www.gtjaqh.com/pc/calendar?date=20260625",
        "use": "GTJA public calendar exposes margin ratio, limit ratio and special contract adjustments for JD.",
    },
    {
        "source_id": "akshare_futures_rule_docs",
        "url": "https://akshare.akfamily.xyz/data/futures/futures.html",
        "use": "AKShare documents futures_rule as GTJA futures calendar with margin and special adjustment fields.",
    },
    {
        "source_id": "dce_daily_trading_parameters",
        "url": "https://www.dce.com.cn/dceg/channel/list/488.html",
        "use": "DCE official daily trading parameters remain preferred if accessible; GTJA is a broker reconstruction route.",
    },
]


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        number = float(value)
        return None if not np.isfinite(number) else number
    if isinstance(value, float):
        return None if not np.isfinite(value) else value
    if isinstance(value, (pd.Timestamp, datetime)):
        return "" if pd.isna(value) else value.isoformat()
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return value


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_无记录_"
    data = frame.head(max_rows).copy() if max_rows else frame.copy()
    return data.to_markdown(index=False)


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path, encoding="utf-8-sig")


def _input_audit(paths: list[Path]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for path in paths:
        if path.exists() and path.is_file():
            stat = path.stat()
            rows.append(
                {
                    "path": str(path),
                    "exists": True,
                    "bytes": int(stat.st_size),
                    "mtime": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
                    "sha256": _sha256(path),
                }
            )
        else:
            rows.append({"path": str(path), "exists": False, "bytes": 0, "mtime": "", "sha256": ""})
    return pd.DataFrame(rows)


def load_required_jd_days() -> pd.DataFrame:
    data = _read_csv(STAGE020_PRODUCT_RETURNS)
    required = {"date", "product_vt_symbol", "main_contract_vt", "main_close", "product_return"}
    missing = sorted(required - set(data.columns))
    if missing:
        raise ValueError(f"Stage020 product returns missing columns: {missing}")
    data["trade_date"] = pd.to_datetime(data["date"], errors="coerce").dt.date.astype(str)
    jd = data[data["product_vt_symbol"].astype(str).eq("jd.DCE")].copy()
    jd = jd.dropna(subset=["trade_date", "main_contract_vt"]).reset_index(drop=True)
    jd["main_contract_vt"] = jd["main_contract_vt"].astype(str)
    return jd[["trade_date", "product_vt_symbol", "main_contract_vt", "main_close", "product_return", "close_source"]]


def _clean_columns(table: pd.DataFrame) -> pd.DataFrame:
    data = table.copy()
    data.columns = [str(col).replace("\n", "").strip() for col in data.columns]
    return data


def _extract_tables(html: str) -> list[pd.DataFrame]:
    try:
        return [_clean_columns(tbl) for tbl in pd.read_html(StringIO(html), header=1)]
    except ValueError:
        return []


def _find_rule_table(tables: list[pd.DataFrame]) -> pd.DataFrame:
    candidates: list[pd.DataFrame] = []
    for table in tables:
        columns = set(table.columns.astype(str))
        score = sum(col in columns for col in ["交易所", "品种", "代码", "交易保证金比例", "特殊合约参数调整"])
        if score >= 3:
            candidates.append(table)
    if candidates:
        candidates.sort(key=len, reverse=True)
        return candidates[0].copy()
    return pd.DataFrame()


def _safe_margin_ratio(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip().replace("%", "").replace("％", "")
    if text in {"", "--", "nan", "None"}:
        return None
    try:
        return float(text) / 100.0
    except ValueError:
        return None


def _normalize_contract_code(code: str) -> str:
    cleaned = re.sub(r"\s+", "", str(code).upper())
    if not cleaned:
        return ""
    if cleaned.startswith("JD"):
        digits = re.sub(r"[^0-9]", "", cleaned[2:])
    else:
        digits = re.sub(r"[^0-9]", "", cleaned)
    if len(digits) == 3:
        digits = "2" + digits
    if len(digits) != 4:
        return ""
    return f"jd{digits}.DCE"


def _month_code_to_int(code: str) -> int | None:
    vt = _normalize_contract_code(code)
    if not vt:
        return None
    digits = vt[2:6]
    year = 2000 + int(digits[:2])
    month = int(digits[2:])
    if month < 1 or month > 12:
        return None
    return year * 12 + month


def _int_to_contract(month_index: int) -> str:
    year = month_index // 12
    month = month_index % 12
    if month == 0:
        year -= 1
        month = 12
    return f"jd{year % 100:02d}{month:02d}.DCE"


def _expand_contract_expr(expr: str) -> list[str]:
    text = re.sub(r"\s+", "", str(expr).upper())
    if not text:
        return []
    expanded: list[str] = []
    for part in re.split(r"[、,，/]", text):
        if not part:
            continue
        if "-" in part or "至" in part or "~" in part:
            pieces = re.split(r"[-至~]", part, maxsplit=1)
            if len(pieces) == 2:
                left = _month_code_to_int(pieces[0])
                right_code = pieces[1]
                if not right_code.upper().startswith("JD"):
                    right_code = "JD" + right_code
                right = _month_code_to_int(right_code)
                if left is not None and right is not None and left <= right and right - left <= 36:
                    expanded.extend(_int_to_contract(idx) for idx in range(left, right + 1))
            continue
        normalized = _normalize_contract_code(part)
        if normalized:
            expanded.append(normalized)
    return sorted(set(expanded))


def parse_jd_adjustments(trade_date: str, raw_adjustment: str, source_hash: str) -> list[dict[str, Any]]:
    text = str(raw_adjustment or "").replace("\n", " ").strip()
    if not text or text.lower() == "nan":
        return []
    rows: list[dict[str, Any]] = []
    pattern = re.compile(
        r"((?:JD\s*\d{3,4})(?:\s*(?:-|至|~)\s*(?:JD\s*)?\d{3,4})?(?:\s*[、,，/]\s*(?:JD\s*)?\d{3,4})*)"
        r"\s*合约交易保证金比例为\s*([0-9.]+)\s*[%％]",
        re.IGNORECASE,
    )
    for expr, margin_text in pattern.findall(text):
        contracts = _expand_contract_expr(expr)
        if not contracts:
            continue
        ratio = float(margin_text) / 100.0
        for contract_vt in contracts:
            rows.append(
                {
                    "trade_date": trade_date,
                    "contract_vt": contract_vt,
                    "broker_margin_ratio": ratio,
                    "raw_adjustment": raw_adjustment,
                    "source_system": "gtja_pc_calendar_direct_html",
                    "source_response_hash": source_hash,
                    "accepted_for_true_ledger": False,
                    "reject_reason": "batch_candidate_missing_official_exchange_margin_and_publish_time",
                }
            )
    return rows


def fetch_gtja_rule(date: str, session: requests.Session, timeout: float) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    request_date = str(date).replace("-", "")
    trade_date = pd.to_datetime(date).date().isoformat()
    url = f"{GTJA_PC_CALENDAR_URL}?date={request_date}"
    requested_at = datetime.now().isoformat(timespec="seconds")
    audit: dict[str, Any] = {
        "trade_date": trade_date,
        "request_date": request_date,
        "url": url,
        "requested_at": requested_at,
        "http_status": 0,
        "response_bytes": 0,
        "response_sha256": "",
        "parse_status": "not_started",
        "row_count": 0,
        "jd_row_count": 0,
        "jd_product_broker_margin_ratio": None,
        "raw_adjustment": "",
        "error": "",
    }
    candidate: dict[str, Any] = {}
    adjustments: list[dict[str, Any]] = []
    try:
        response = session.get(GTJA_PC_CALENDAR_URL, params={"date": request_date}, headers=REQUEST_HEADERS, timeout=timeout)
        audit["http_status"] = int(response.status_code)
        payload = response.content
        audit["response_bytes"] = len(payload)
        audit["response_sha256"] = _sha256_bytes(payload)
        response.encoding = response.apparent_encoding or response.encoding
        tables = _extract_tables(response.text)
        table = _find_rule_table(tables)
        if table.empty:
            audit["parse_status"] = "no_rule_table"
            audit["error"] = "no rule table found"
            return audit, candidate, adjustments
        audit["row_count"] = int(len(table))
        mask = table.astype(str).apply(lambda col: col.str.contains("鸡蛋|JD", case=False, na=False)).any(axis=1)
        jd_rows = table[mask].copy()
        audit["jd_row_count"] = int(len(jd_rows))
        if jd_rows.empty:
            audit["parse_status"] = "no_jd_row"
            audit["error"] = "rule table found but no JD rows"
            return audit, candidate, adjustments
        if "代码" in jd_rows.columns:
            product_rows = jd_rows[jd_rows["代码"].astype(str).str.upper().eq("JD")].copy()
        else:
            product_rows = pd.DataFrame()
        if product_rows.empty:
            product_rows = jd_rows.head(1).copy()
        row = product_rows.iloc[0]
        product_ratio = _safe_margin_ratio(row.get("交易保证金比例"))
        raw_adjustment = str(row.get("特殊合约参数调整", "") or "")
        audit["jd_product_broker_margin_ratio"] = product_ratio
        audit["raw_adjustment"] = raw_adjustment
        audit["parse_status"] = "ok" if product_ratio is not None else "jd_margin_missing"
        adjustments = parse_jd_adjustments(audit["trade_date"], raw_adjustment, str(audit["response_sha256"]))
        candidate = {
            "trade_date": audit["trade_date"],
            "jd_product_broker_margin_ratio": product_ratio,
            "raw_adjustment": raw_adjustment,
            "source_system": "gtja_pc_calendar_direct_html",
            "source_response_hash": audit["response_sha256"],
            "url": url,
            "accepted_for_true_ledger": False,
            "reject_reason": "candidate_only_missing_exchange_margin_and_publish_time",
        }
        return audit, candidate, adjustments
    except Exception as exc:  # noqa: BLE001 - endpoint probe should record all errors.
        audit["parse_status"] = "error"
        audit["error"] = f"{type(exc).__name__}: {str(exc)[:300]}"
        return audit, candidate, adjustments


def build_candidate_daily_margin(required: pd.DataFrame, date_candidates: pd.DataFrame, adjustments: pd.DataFrame) -> pd.DataFrame:
    data = required[["trade_date", "main_contract_vt"]].copy()
    data.rename(columns={"main_contract_vt": "contract_vt"}, inplace=True)
    data = data.merge(
        date_candidates[["trade_date", "jd_product_broker_margin_ratio", "source_system", "source_response_hash", "url", "accepted_for_true_ledger", "reject_reason"]],
        on="trade_date",
        how="left",
    )
    if adjustments.empty:
        data["special_broker_margin_ratio"] = np.nan
        data["special_raw_adjustment"] = ""
    else:
        adj = adjustments[["trade_date", "contract_vt", "broker_margin_ratio", "raw_adjustment"]].copy()
        adj.rename(columns={"broker_margin_ratio": "special_broker_margin_ratio", "raw_adjustment": "special_raw_adjustment"}, inplace=True)
        data = data.merge(adj, on=["trade_date", "contract_vt"], how="left")
    data["broker_margin_ratio"] = data["special_broker_margin_ratio"].where(
        pd.notna(data["special_broker_margin_ratio"]),
        data["jd_product_broker_margin_ratio"],
    )
    data["exchange_margin_ratio"] = np.nan
    data["publish_or_effective_time"] = ""
    data["accepted_for_jd_contract_daily_margin_history"] = False
    data["pit_acceptance"] = np.where(
        pd.notna(data["broker_margin_ratio"]),
        "rebuild_candidate_not_accepted",
        "missing",
    )
    data["blocking_reason"] = np.where(
        pd.notna(data["broker_margin_ratio"]),
        "missing_exchange_margin_or_publish_effective_time",
        "missing_gtja_margin_for_required_day",
    )
    cols = [
        "trade_date",
        "contract_vt",
        "exchange_margin_ratio",
        "broker_margin_ratio",
        "jd_product_broker_margin_ratio",
        "special_broker_margin_ratio",
        "special_raw_adjustment",
        "source_system",
        "source_response_hash",
        "url",
        "publish_or_effective_time",
        "accepted_for_jd_contract_daily_margin_history",
        "pit_acceptance",
        "blocking_reason",
    ]
    return data[cols]


def summarize_coverage(required: pd.DataFrame, date_audit: pd.DataFrame, candidate_daily: pd.DataFrame) -> pd.DataFrame:
    required_dates = set(required["trade_date"].astype(str))
    ok_dates = set(date_audit.loc[date_audit["parse_status"].eq("ok"), "trade_date"].astype(str))
    candidate_dates = set(candidate_daily.loc[pd.notna(candidate_daily["broker_margin_ratio"]), "trade_date"].astype(str))
    accepted_rows = int(candidate_daily["accepted_for_jd_contract_daily_margin_history"].astype(bool).sum())
    rows = [
        {"metric": "required_jd_day_rows", "value": int(len(required)), "detail": ""},
        {"metric": "required_unique_dates", "value": int(len(required_dates)), "detail": ""},
        {"metric": "gtja_parse_ok_dates", "value": int(len(ok_dates)), "detail": ""},
        {"metric": "candidate_margin_dates", "value": int(len(candidate_dates)), "detail": ""},
        {"metric": "missing_candidate_dates", "value": int(len(required_dates - candidate_dates)), "detail": ",".join(sorted(required_dates - candidate_dates)[:30])},
        {
            "metric": "candidate_daily_margin_rows",
            "value": int(pd.notna(candidate_daily["broker_margin_ratio"]).sum()),
            "detail": "",
        },
        {
            "metric": "accepted_daily_margin_rows",
            "value": accepted_rows,
            "detail": "",
        },
        {
            "metric": "contract_count_with_candidate_rows",
            "value": int(candidate_daily.loc[pd.notna(candidate_daily["broker_margin_ratio"]), "contract_vt"].nunique()),
            "detail": "",
        },
        {
            "metric": "required_contract_count",
            "value": int(required["main_contract_vt"].nunique()),
            "detail": "",
        },
        {
            "metric": "special_adjustment_required_rows",
            "value": int(pd.notna(candidate_daily["special_broker_margin_ratio"]).sum()),
            "detail": "",
        },
    ]
    return pd.DataFrame(rows)


def run_batch(max_dates: int | None, sleep_seconds: float, timeout: float) -> dict[str, Any]:
    required = load_required_jd_days()
    unique_dates = sorted(required["trade_date"].astype(str).unique())
    selected_dates = unique_dates[:max_dates] if max_dates else unique_dates

    session = requests.Session()
    date_audit_rows: list[dict[str, Any]] = []
    candidate_rows: list[dict[str, Any]] = []
    adjustment_rows: list[dict[str, Any]] = []
    for idx, date in enumerate(selected_dates, start=1):
        audit, candidate, adjustments = fetch_gtja_rule(date, session, timeout)
        date_audit_rows.append(audit)
        if candidate:
            candidate_rows.append(candidate)
        adjustment_rows.extend(adjustments)
        if idx == 1 or idx % 100 == 0 or idx == len(selected_dates):
            print(
                f"[{datetime.now().isoformat(timespec='seconds')}] Stage090 fetched {idx}/{len(selected_dates)} dates; "
                f"latest={date} request={audit.get('request_date', '')} status={audit['parse_status']}",
                flush=True,
            )
        if sleep_seconds > 0:
            time.sleep(sleep_seconds)

    date_audit = pd.DataFrame(date_audit_rows)
    date_candidates = pd.DataFrame(candidate_rows)
    if date_candidates.empty:
        date_candidates = pd.DataFrame(
            columns=["trade_date", "jd_product_broker_margin_ratio", "source_system", "source_response_hash", "url", "accepted_for_true_ledger", "reject_reason"]
        )
    adjustments = pd.DataFrame(adjustment_rows)
    if adjustments.empty:
        adjustments = pd.DataFrame(
            columns=["trade_date", "contract_vt", "broker_margin_ratio", "raw_adjustment", "source_system", "source_response_hash", "accepted_for_true_ledger", "reject_reason"]
        )
    candidate_daily = build_candidate_daily_margin(required[required["trade_date"].isin(selected_dates)].copy(), date_candidates, adjustments)
    coverage_summary = summarize_coverage(required[required["trade_date"].isin(selected_dates)].copy(), date_audit, candidate_daily)

    accepted_rows = int(candidate_daily["accepted_for_jd_contract_daily_margin_history"].astype(bool).sum())
    candidate_rows_count = int(pd.notna(candidate_daily["broker_margin_ratio"]).sum())
    missing_rows = int(pd.isna(candidate_daily["broker_margin_ratio"]).sum())
    required_rows = int(len(candidate_daily))
    full_required_run = len(selected_dates) == len(unique_dates)
    decision_name = "stage090_gtja_batch_candidate_not_accepted"
    if full_required_run and candidate_rows_count == required_rows and accepted_rows == 0:
        decision_name = "stage090_gtja_full_coverage_candidate_not_accepted"
    if missing_rows > 0:
        decision_name = "stage090_gtja_batch_coverage_incomplete_not_accepted"

    source_audit = pd.DataFrame(
        [
            {
                "candidate_id": "gtja_pc_calendar_direct_jd_batch",
                "source_type": "broker_calendar_margin_history_reconstruction",
                "required_unique_dates": len(selected_dates),
                "parse_ok_dates": int(date_audit["parse_status"].eq("ok").sum()) if not date_audit.empty else 0,
                "required_rows": required_rows,
                "candidate_rows": candidate_rows_count,
                "missing_rows": missing_rows,
                "adjustment_rows": int(len(adjustments)),
                "has_broker_margin_ratio": candidate_rows_count > 0,
                "has_exchange_margin_ratio": False,
                "has_source_hash": bool(not date_audit.empty and date_audit["response_sha256"].astype(str).ne("").any()),
                "has_publish_or_effective_time": False,
                "accepted_for_jd_contract_daily_margin_history": False,
                "pit_acceptance": "rebuild_candidate_not_accepted" if candidate_rows_count else "rejected",
                "reject_reason": "missing_exchange_margin_or_publish_effective_time",
                "detail": "GTJA direct page can reconstruct broker margin candidates for available dates; not accepted for true ledger.",
            }
        ]
    )

    decision = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "decision": decision_name,
        "full_required_run": full_required_run,
        "required_unique_dates": int(len(selected_dates)),
        "required_jd_day_rows": required_rows,
        "gtja_parse_ok_dates": int(date_audit["parse_status"].eq("ok").sum()) if not date_audit.empty else 0,
        "candidate_daily_margin_rows": candidate_rows_count,
        "missing_candidate_daily_margin_rows": missing_rows,
        "adjustment_rows": int(len(adjustments)),
        "accepted_candidate_count": 0,
        "ready_for_true_ledger_replay": False,
        "remaining_blocker": "jd_contract_daily_margin_history",
        "strategy_changed": False,
        "true_engine_run": False,
        "order_api_calls": 0,
        "ctp_connected": False,
        "next_step": "If GTJA coverage is incomplete, keep DCE/vendor official data as priority; if coverage is full, still need exchange margin or accepted broker margin policy before true ledger.",
    }

    return {
        "required": required,
        "selected_required": required[required["trade_date"].isin(selected_dates)].copy(),
        "date_audit": date_audit,
        "date_candidates": date_candidates,
        "adjustments": adjustments,
        "candidate_daily": candidate_daily,
        "coverage_summary": coverage_summary,
        "source_audit": source_audit,
        "decision": decision,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-dates", type=int, default=0, help="Optional debug cap; default 0 means all required JD dates.")
    parser.add_argument("--sleep", type=float, default=0.02)
    parser.add_argument("--timeout", type=float, default=10.0)
    args = parser.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    STAGES_DIR.mkdir(parents=True, exist_ok=True)

    result = run_batch(max_dates=args.max_dates or None, sleep_seconds=args.sleep, timeout=args.timeout)
    selected_required = result["selected_required"]
    date_audit = result["date_audit"]
    adjustments = result["adjustments"]
    candidate_daily = result["candidate_daily"]
    coverage_summary = result["coverage_summary"]
    source_audit = result["source_audit"]
    decision = result["decision"]

    source_audit.to_csv(SOURCE_AUDIT_PATH, index=False, encoding="utf-8-sig")
    selected_required.to_csv(REQUIRED_JD_DAYS_PATH, index=False, encoding="utf-8-sig")
    date_audit.to_csv(GTJA_DATE_AUDIT_PATH, index=False, encoding="utf-8-sig")
    adjustments.to_csv(GTJA_ADJUSTMENTS_PATH, index=False, encoding="utf-8-sig")
    candidate_daily.to_csv(CANDIDATE_DAILY_MARGIN_PATH, index=False, encoding="utf-8-sig")
    coverage_summary.to_csv(COVERAGE_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    _input_audit([STAGE020_PRODUCT_RETURNS, Path(__file__).resolve()]).to_csv(INPUT_AUDIT_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")

    report_lines = [
        "# Stage090 GTJA JD margin batch gate",
        "",
        "## 结论",
        "",
        "- GTJA 日历可作为 broker margin reconstruction 候选源审计，但本阶段不 accepted。",
        "- 不 accepted 的原因不是收益差，而是数据合同仍缺 DCE/exchange margin、发布时间/有效时间链；若覆盖不完整，还缺必要交易日。",
        "- 本阶段不跑 true ledger、不回测收益、不改策略。",
        "",
        "## 外部调研与判断",
        "",
    ]
    for item in EXTERNAL_RESEARCH:
        report_lines.append(f"- `{item['source_id']}`：{item['url']}；{item['use']}")
    report_lines.extend(
        [
            "",
            "## Source Audit",
            "",
            _md_table(source_audit),
            "",
            "## Coverage Summary",
            "",
            _md_table(coverage_summary),
            "",
            "## Date Audit Samples",
            "",
            _md_table(date_audit.head(20)),
            "",
            "## Candidate Daily Margin Samples",
            "",
            _md_table(candidate_daily.head(30)),
            "",
            "## 决策",
            "",
            f"- decision：`{decision['decision']}`",
            f"- full_required_run：`{decision['full_required_run']}`",
            f"- required_unique_dates：`{decision['required_unique_dates']}`",
            f"- required_jd_day_rows：`{decision['required_jd_day_rows']}`",
            f"- gtja_parse_ok_dates：`{decision['gtja_parse_ok_dates']}`",
            f"- candidate_daily_margin_rows：`{decision['candidate_daily_margin_rows']}`",
            f"- missing_candidate_daily_margin_rows：`{decision['missing_candidate_daily_margin_rows']}`",
            f"- adjustment_rows：`{decision['adjustment_rows']}`",
            f"- accepted_candidate_count：`{decision['accepted_candidate_count']}`",
            f"- ready_for_true_ledger_replay：`{decision['ready_for_true_ledger_replay']}`",
            "",
            "## 反思",
            "",
            "- 运行前过拟合反思：否。只做数据覆盖和解析验收，不看收益、不调规则。",
            "- 运行后过拟合反思：否。结果继续停在数据闸门，没有把 broker 样本直接用于策略。",
            "- 运行前继续价值反思：有。Stage089 reviewer 建议把 GTJA 路线一次性验清。",
            "- 运行后继续价值反思：有条件。若覆盖不完整，应优先找 DCE/vendor；若覆盖完整，仍要补 exchange margin 或明确 broker-margin-only 的验收政策。",
            "",
            "## 输出",
            "",
            f"- source_audit：`{SOURCE_AUDIT_PATH}`",
            f"- required_jd_days：`{REQUIRED_JD_DAYS_PATH}`",
            f"- gtja_date_audit：`{GTJA_DATE_AUDIT_PATH}`",
            f"- gtja_adjustments：`{GTJA_ADJUSTMENTS_PATH}`",
            f"- candidate_daily_margin：`{CANDIDATE_DAILY_MARGIN_PATH}`",
            f"- coverage_summary：`{COVERAGE_SUMMARY_PATH}`",
            f"- input_audit：`{INPUT_AUDIT_PATH}`",
            f"- decision：`{DECISION_PATH}`",
        ]
    )
    REPORT_PATH.write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    stage_path = STAGES_DIR / f"{datetime.now().strftime('%Y%m%d_%H%M')}_stage090_gtja_jd_margin_batch_gate.md"
    stage_text = f"""# Stage090 GTJA JD margin batch gate

- line_id：`{LINE_ID}`
- 当前模式：day
- 记录时间：{datetime.now().isoformat(timespec="seconds")}
- 阶段性质：只读数据覆盖/解析验收；不回测收益，不改官方 live config、不连接 CTP、不调用下单
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

{chr(10).join(f"- `{item['source_id']}`：{item['url']}；{item['use']}" for item in EXTERNAL_RESEARCH)}

## 本次变更

- 新增脚本：`research/lines/{LINE_ID}/tools/stage090_gtja_jd_margin_batch_gate.py`
- 新增参数：`sleep={args.sleep}`、`timeout={args.timeout}`、`max_dates={args.max_dates}`
- 修改参数：无正式策略参数修改。
- 删除参数：无。

## 结果

- decision：`{decision['decision']}`
- full_required_run：`{decision['full_required_run']}`
- required_unique_dates：`{decision['required_unique_dates']}`
- required_jd_day_rows：`{decision['required_jd_day_rows']}`
- gtja_parse_ok_dates：`{decision['gtja_parse_ok_dates']}`
- candidate_daily_margin_rows：`{decision['candidate_daily_margin_rows']}`
- missing_candidate_daily_margin_rows：`{decision['missing_candidate_daily_margin_rows']}`
- adjustment_rows：`{decision['adjustment_rows']}`
- accepted_candidate_count：`0`
- ready_for_true_ledger_replay：`False`
- remaining_blocker：`jd_contract_daily_margin_history`
- 策略变更：`False`
- true engine run：`False`
- order API：`0`
- CTP：`False`

## Source Audit

{_md_table(source_audit)}

## Coverage Summary

{_md_table(coverage_summary)}

## Date Audit Samples

{_md_table(date_audit.head(20))}

## Candidate Daily Margin Samples

{_md_table(candidate_daily.head(30))}

## 回测记录字段

- 本阶段不新增回测，因此不新增期末权益、总收益、最大回撤、Sharpe、滑点、交易次数、胜率。

## 过拟合反思

- 运行前：否。只做数据覆盖和解析验收，不看收益、不调规则。
- 运行后：否。结果继续停在数据闸门，没有把 broker 样本直接用于策略。

## 继续价值反思

- 运行前：有。Stage089 reviewer 建议把 GTJA 路线一次性验清。
- 运行后：有条件。若覆盖不完整，应优先找 DCE/vendor；若覆盖完整，仍要补 exchange margin 或明确 broker-margin-only 的验收政策。

## 输出文件

- report：`{REPORT_PATH}`
- source_audit：`{SOURCE_AUDIT_PATH}`
- required_jd_days：`{REQUIRED_JD_DAYS_PATH}`
- gtja_date_audit：`{GTJA_DATE_AUDIT_PATH}`
- gtja_adjustments：`{GTJA_ADJUSTMENTS_PATH}`
- candidate_daily_margin：`{CANDIDATE_DAILY_MARGIN_PATH}`
- coverage_summary：`{COVERAGE_SUMMARY_PATH}`
- input_audit：`{INPUT_AUDIT_PATH}`
- decision：`{DECISION_PATH}`
"""
    stage_path.write_text(stage_text, encoding="utf-8")
    print(json.dumps(_json_safe({"stage_record": stage_path, **decision}), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
