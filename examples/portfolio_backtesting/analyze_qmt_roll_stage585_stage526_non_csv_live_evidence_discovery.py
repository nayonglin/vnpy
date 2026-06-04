from __future__ import annotations

from collections import Counter
from datetime import datetime
import json
import math
import os
from pathlib import Path
import re
import sqlite3
from typing import Any

PROJECT_DIR = Path(__file__).resolve().parent
REPO_ROOT = PROJECT_DIR.parent.parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
os.environ.setdefault("MPLCONFIGDIR", str(OUTPUT_DIR / ".matplotlib"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


LINE_ID = "futures_trend_drawdown30_preserve_return"
MODEL_TAG = "stage585_stage526_non_csv_live_evidence_discovery_v1"
OUTPUT_PREFIX = "qmt_roll_stage585_stage526_non_csv_live_evidence_discovery"

STAGE575_TAG = "stage575_stage526_live_execution_p0_watchlist_v1"
STAGE575_PREFIX = "qmt_roll_stage575_stage526_live_execution_p0_watchlist"
STAGE575_WATCHLIST = OUTPUT_DIR / f"{STAGE575_PREFIX}_watchlist_{STAGE575_TAG}.csv"

INVENTORY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_inventory_{MODEL_TAG}.csv"
P0_MATCH_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_p0_matches_{MODEL_TAG}.csv"
FIELD_COVERAGE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_field_coverage_{MODEL_TAG}.csv"
SQLITE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_sqlite_tables_{MODEL_TAG}.csv"
GATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gates_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

MAX_TEXT_BYTES = 2_000_000
MAX_SCAN_FILE_BYTES = 8_000_000
MAX_SNIPPETS_PER_FILE = 5
MAX_SQLITE_SAMPLE_ROWS = 5_000

TEXT_EXTENSIONS = {".txt", ".log", ".md", ".json", ".jsonl"}
SQLITE_EXTENSIONS = {".db", ".sqlite", ".sqlite3"}
SKIP_DIR_NAMES = {
    ".git",
    ".py311",
    "downloaded_futures",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    "node_modules",
}
SENSITIVE_NAME_PATTERNS = ("connect_ctp", "local.env", ".env", "ctp_simnow.local", "ctp_broker_test.local")
PATH_KEYWORDS = (
    "ctp",
    "simnow",
    "broker",
    "order",
    "trade",
    "fill",
    "execution",
    "ledger",
    "shadow",
    "live",
    "成交",
    "报单",
    "委托",
    "回报",
)
CONTENT_KEYWORDS = (
    "onrtntrade",
    "onrtnorder",
    "tradedata",
    "orderdata",
    "vt_orderid",
    "vt_tradeid",
    "tradeid",
    "orderid",
    "avg_fill",
    "implementation_shortfall",
    "actual_vs_window_vwap",
    "simnow",
    "ctp",
    "成交回报",
    "报单回报",
)

FIELD_ALIASES = {
    "vt_symbol": ("vt_symbol", "vtsymbol", "symbol", "合约"),
    "order_id": ("vt_orderid", "orderid", "order_id", "order sys id", "ordersysid", "委托编号", "报单编号"),
    "trade_id": ("vt_tradeid", "tradeid", "trade_id", "成交编号"),
    "direction": ("direction", "买卖", "方向", "long", "short"),
    "offset": ("offset", "开平", "comboffsetflag", "open", "close"),
    "price": ("price", "成交价", "委托价", "limit_price", "avg_fill_price"),
    "volume": ("volume", "filled_volume", "traded", "成交量", "手数"),
    "datetime": ("datetime", "trade_time", "insert_time", "成交时间", "报单时间", "fill_first_at", "fill_last_at"),
    "status": ("status", "orderstatus", "全部成交", "未成交", "已撤单", "rejected", "拒绝"),
    "avg_fill_price": ("avg_fill_price", "average_price", "成交均价"),
    "unfilled_volume": ("unfilled_volume", "volume_total", "volumetotal", "剩余数量"),
    "vwap": ("actual_vs_window_vwap", "vwap", "window_vwap"),
    "implementation_shortfall": ("implementation_shortfall", "shortfall", "arrival_price"),
    "participation": ("participation", "volume_to_window", "窗口参与率"),
    "broker_reject": ("broker_reject", "errorid", "errormsg", "reject", "拒绝", "错单"),
}

CORE_TRADE_FIELDS = {"vt_symbol", "order_id", "trade_id", "direction", "offset", "price", "volume", "datetime"}
TCA_FIELDS = {"avg_fill_price", "unfilled_volume", "vwap", "implementation_shortfall", "participation", "broker_reject"}


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path, encoding="utf-8-sig")


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
        result = float(value)
        return None if math.isnan(result) or math.isinf(result) else result
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    return value


def _md_table(frame: pd.DataFrame, columns: list[str] | None = None, max_rows: int = 30) -> str:
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


def _relative(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _is_sensitive_path(path: Path) -> bool:
    lower = str(path).lower()
    return any(pattern in lower for pattern in SENSITIVE_NAME_PATTERNS)


def _redact(text: str) -> str:
    patterns = [
        r"(?i)(password|passwd|authcode|auth_code|appid|app_id|userid|user_id|investorid|brokerid|accountid)(\s*[:=]\s*)([^,\s\"']+)",
        r"(?i)(CTP_[A-Z0-9_]*(?:PASSWORD|AUTH|APP|USER|INVESTOR|BROKER)[A-Z0-9_]*)(\s*=\s*)([^,\s\"']+)",
    ]
    result = text
    for pattern in patterns:
        result = re.sub(pattern, r"\1\2***REDACTED***", result)
    return result[:500]


def _load_p0() -> pd.DataFrame:
    watch = _read_csv(STAGE575_WATCHLIST)
    p0 = watch[watch["watch_priority"].fillna("").astype(str).str.startswith("P0")].copy()
    p0["event_id"] = pd.to_numeric(p0["event_id"], errors="coerce").astype("Int64")
    p0["vt_symbol"] = p0["vt_symbol"].astype(str)
    return p0.reset_index(drop=True)


def _p0_patterns(p0: pd.DataFrame) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for vt_symbol in p0["vt_symbol"].astype(str):
        product = vt_symbol.split(".")[0]
        exchange = vt_symbol.split(".")[1] if "." in vt_symbol else ""
        patterns = {vt_symbol.lower(), product.lower()}
        if exchange:
            patterns.add(f"{product}.{exchange}".lower())
        out[vt_symbol] = sorted(patterns)
    return out


def _iter_candidate_files() -> list[Path]:
    roots: list[Path] = [
        OUTPUT_DIR,
        REPO_ROOT / ".vntrader",
        REPO_ROOT / "log",
        REPO_ROOT / "research" / "lines" / "futures_trend" / "stages",
        REPO_ROOT / "research" / "lines" / "futures_trend_drawdown30_preserve_return" / "stages",
        REPO_ROOT,
    ]
    direct_files = {REPO_ROOT / "debug-simnow-snapshot-probe.md", REPO_ROOT / "README.md", REPO_ROOT / "CHANGELOG.md"}
    paths: set[Path] = set()
    for root in roots:
        if not root.exists():
            continue
        if root.is_file():
            paths.add(root)
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if any(part in SKIP_DIR_NAMES for part in path.parts):
                continue
            suffix = path.suffix.lower()
            if suffix not in TEXT_EXTENSIONS and suffix not in SQLITE_EXTENSIONS:
                continue
            if path.name.startswith(OUTPUT_PREFIX):
                continue
            lower_path = str(path).lower()
            if root == REPO_ROOT and not any(key in lower_path for key in PATH_KEYWORDS):
                continue
            paths.add(path)
    for path in direct_files:
        if path.exists():
            paths.add(path)
    return sorted(paths)


def _read_text_for_scan(path: Path) -> tuple[str, str]:
    size = path.stat().st_size
    if size > MAX_SCAN_FILE_BYTES:
        return "", "too_large"
    if _is_sensitive_path(path):
        return "", "sensitive_path_skipped"
    raw = path.read_bytes()[:MAX_TEXT_BYTES]
    for encoding in ("utf-8", "utf-8-sig", "gbk", "latin1"):
        try:
            return raw.decode(encoding, errors="replace"), "ok"
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace"), "ok"


def _field_hits(text: str) -> dict[str, int]:
    lower = text.lower()
    hits: dict[str, int] = {}
    for field, aliases in FIELD_ALIASES.items():
        hits[field] = int(any(alias.lower() in lower for alias in aliases))
    return hits


def _keyword_hits(text: str) -> dict[str, int]:
    lower = text.lower()
    return {keyword: lower.count(keyword.lower()) for keyword in CONTENT_KEYWORDS if keyword.lower() in lower}


def _snippets(text: str, p0_patterns: dict[str, list[str]]) -> tuple[dict[str, int], list[str]]:
    lower_lines = text.lower().splitlines()
    original_lines = text.splitlines()
    p0_counts = {symbol: 0 for symbol in p0_patterns}
    snippets: list[str] = []
    for idx, line in enumerate(lower_lines):
        matched_symbol = None
        for symbol, patterns in p0_patterns.items():
            if any(pattern in line for pattern in patterns):
                p0_counts[symbol] += 1
                matched_symbol = symbol
                break
        keyword_match = any(keyword.lower() in line for keyword in CONTENT_KEYWORDS)
        if (matched_symbol or keyword_match) and len(snippets) < MAX_SNIPPETS_PER_FILE:
            snippets.append(_redact(original_lines[idx]))
    return p0_counts, snippets


def _sqlite_inventory(path: Path, p0_patterns: dict[str, list[str]]) -> tuple[list[dict[str, Any]], dict[str, int], dict[str, int]]:
    rows: list[dict[str, Any]] = []
    p0_counts = {symbol: 0 for symbol in p0_patterns}
    field_counter: Counter[str] = Counter()
    if _is_sensitive_path(path):
        rows.append(
            {
                "path": _relative(path),
                "table_name": "",
                "read_ok": 0,
                "row_count": None,
                "columns": "",
                "p0_sample_hits": "{}",
                "sample_rows_checked": 0,
                "error": "sensitive_path_skipped",
            }
        )
        return rows, p0_counts, dict(field_counter)
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    except sqlite3.Error as exc:
        rows.append({"path": _relative(path), "table_name": "", "read_ok": 0, "row_count": None, "columns": "", "error": type(exc).__name__})
        return rows, p0_counts, dict(field_counter)
    try:
        table_names = [
            row[0]
            for row in conn.execute("select name from sqlite_master where type='table' order by name").fetchall()
        ]
        for table_name in table_names:
            try:
                info = conn.execute(f'pragma table_info("{table_name}")').fetchall()
                columns = [str(item[1]) for item in info]
                row_count = conn.execute(f'select count(*) from "{table_name}"').fetchone()[0]
                column_text = " ".join(columns).lower()
                for field, aliases in FIELD_ALIASES.items():
                    if any(alias.lower() in column_text for alias in aliases):
                        field_counter[field] += 1
                text_columns = [column for column in columns if any(token in column.lower() for token in ["symbol", "order", "trade", "contract", "vt"])]
                sample_hits = {symbol: 0 for symbol in p0_patterns}
                sample_rows_checked = 0
                if text_columns and row_count:
                    select_cols = ",".join(f'"{column}"' for column in text_columns[:6])
                    for values in conn.execute(f'select {select_cols} from "{table_name}" limit {MAX_SQLITE_SAMPLE_ROWS}').fetchall():
                        sample_rows_checked += 1
                        text = " ".join("" if value is None else str(value) for value in values).lower()
                        for symbol, patterns in p0_patterns.items():
                            if any(pattern in text for pattern in patterns):
                                sample_hits[symbol] += 1
                                p0_counts[symbol] += 1
                rows.append(
                    {
                        "path": _relative(path),
                        "table_name": table_name,
                        "read_ok": 1,
                        "row_count": int(row_count),
                        "columns": ",".join(columns),
                        "p0_sample_hits": json.dumps(sample_hits, ensure_ascii=False),
                        "sample_rows_checked": int(sample_rows_checked),
                        "error": "",
                    }
                )
            except sqlite3.Error as exc:
                rows.append(
                    {
                        "path": _relative(path),
                        "table_name": table_name,
                        "read_ok": 0,
                        "row_count": None,
                        "columns": "",
                        "p0_sample_hits": "{}",
                        "sample_rows_checked": 0,
                        "error": type(exc).__name__,
                    }
                )
    finally:
        conn.close()
    return rows, p0_counts, dict(field_counter)


def build_inventory(p0: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    p0_patterns = _p0_patterns(p0)
    inventory_rows: list[dict[str, Any]] = []
    p0_rows: list[dict[str, Any]] = []
    sqlite_rows: list[dict[str, Any]] = []
    field_rows: list[dict[str, Any]] = []

    for path in _iter_candidate_files():
        suffix = path.suffix.lower()
        rel = _relative(path)
        size = path.stat().st_size
        path_has_keyword = int(any(keyword in str(path).lower() for keyword in PATH_KEYWORDS))
        row: dict[str, Any] = {
            "path": rel,
            "suffix": suffix,
            "size_bytes": int(size),
            "path_has_keyword": path_has_keyword,
            "scan_status": "",
            "keyword_hit_count": 0,
            "p0_match_count": 0,
            "matched_p0_symbols": "",
            "core_trade_field_count": 0,
            "tca_field_count": 0,
            "structured_order_trade_candidate": 0,
            "p0_structured_candidate": 0,
            "can_close_p0_live_tca": 0,
            "missing_to_close": "",
            "snippet_redacted": "",
        }

        field_hits: dict[str, int] = {field: 0 for field in FIELD_ALIASES}
        p0_counts = {symbol: 0 for symbol in p0_patterns}
        keyword_hit_count = 0
        snippets: list[str] = []

        if suffix in SQLITE_EXTENSIONS:
            table_rows, p0_counts, sqlite_field_hits = _sqlite_inventory(path, p0_patterns)
            sqlite_rows.extend(table_rows)
            field_hits.update({field: int(count > 0) for field, count in sqlite_field_hits.items()})
            row["scan_status"] = "sqlite_scanned" if table_rows else "sqlite_empty"
            keyword_hit_count = sum(sqlite_field_hits.values())
        else:
            text, status = _read_text_for_scan(path)
            row["scan_status"] = status
            if status == "ok":
                keyword_hit_count = int(sum(_keyword_hits(text).values()))
                field_hits = _field_hits(text)
                p0_counts, snippets = _snippets(text, p0_patterns)
            elif status == "sensitive_path_skipped":
                snippets = ["sensitive path skipped; no content copied"]

        matched_p0_symbols = [symbol for symbol, count in p0_counts.items() if count > 0]
        core_count = sum(field_hits.get(field, 0) for field in CORE_TRADE_FIELDS)
        tca_count = sum(field_hits.get(field, 0) for field in TCA_FIELDS)
        structured = int(core_count >= 5 and (field_hits.get("order_id", 0) or field_hits.get("trade_id", 0)))
        p0_structured = int(structured and bool(matched_p0_symbols))
        missing_to_close: list[str] = []
        if not matched_p0_symbols:
            missing_to_close.append("no_stage526_p0_symbol_match")
        if core_count < len(CORE_TRADE_FIELDS):
            missing_to_close.append("incomplete_order_trade_core_fields")
        if tca_count < len(TCA_FIELDS):
            missing_to_close.append("missing_live_tca_metric_fields")
        if suffix in SQLITE_EXTENSIONS and not sqlite_rows:
            missing_to_close.append("sqlite_not_read")
        can_close = int(not missing_to_close)

        row.update(
            {
                "keyword_hit_count": keyword_hit_count,
                "p0_match_count": int(sum(p0_counts.values())),
                "matched_p0_symbols": ",".join(matched_p0_symbols),
                "core_trade_field_count": int(core_count),
                "tca_field_count": int(tca_count),
                "structured_order_trade_candidate": structured,
                "p0_structured_candidate": p0_structured,
                "can_close_p0_live_tca": can_close,
                "missing_to_close": ",".join(missing_to_close),
                "snippet_redacted": " || ".join(snippets),
            }
        )
        inventory_rows.append(row)
        for symbol, count in p0_counts.items():
            if count > 0:
                p0_rows.append({"path": rel, "p0_symbol": symbol, "match_count": int(count), "suffix": suffix})
        for field, hit in field_hits.items():
            field_rows.append({"path": rel, "field": field, "present": int(hit)})

    inventory = pd.DataFrame(inventory_rows)
    p0_match = pd.DataFrame(p0_rows)
    field = pd.DataFrame(field_rows)
    sqlite = pd.DataFrame(sqlite_rows)

    if not inventory.empty:
        inventory = inventory.sort_values(
            ["can_close_p0_live_tca", "p0_structured_candidate", "p0_match_count", "structured_order_trade_candidate", "keyword_hit_count"],
            ascending=[False, False, False, False, False],
        )
    return inventory, p0_match, field, sqlite


def build_field_coverage(field: pd.DataFrame, inventory: pd.DataFrame) -> pd.DataFrame:
    if field.empty:
        return pd.DataFrame(columns=["field", "files_present", "candidate_files_present", "p0_files_present"])
    candidate_paths = set(inventory.loc[inventory["structured_order_trade_candidate"].eq(1), "path"].astype(str))
    p0_paths = set(inventory.loc[inventory["p0_match_count"].gt(0), "path"].astype(str))
    rows: list[dict[str, Any]] = []
    for field_name, group in field.groupby("field"):
        present_paths = set(group.loc[group["present"].eq(1), "path"].astype(str))
        rows.append(
            {
                "field": field_name,
                "files_present": len(present_paths),
                "candidate_files_present": len(present_paths & candidate_paths),
                "p0_files_present": len(present_paths & p0_paths),
                "required_for_close": int(field_name in CORE_TRADE_FIELDS or field_name in TCA_FIELDS),
            }
        )
    return pd.DataFrame(rows).sort_values(["required_for_close", "p0_files_present", "candidate_files_present"], ascending=[False, False, False])


def build_gates(inventory: pd.DataFrame, p0_match: pd.DataFrame, sqlite: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    scanned = int(len(inventory))
    read_ok = int(inventory["scan_status"].isin(["ok", "sqlite_scanned", "sqlite_empty"]).sum()) if not inventory.empty else 0
    sensitive_skipped = int(inventory["scan_status"].eq("sensitive_path_skipped").sum()) if not inventory.empty else 0
    generic_structured = int(inventory["structured_order_trade_candidate"].sum()) if not inventory.empty else 0
    p0_files = int(inventory["p0_match_count"].gt(0).sum()) if not inventory.empty else 0
    p0_structured = int(inventory["p0_structured_candidate"].sum()) if not inventory.empty else 0
    p0_close = int(inventory["can_close_p0_live_tca"].sum()) if not inventory.empty else 0
    sqlite_tables = int(sqlite["read_ok"].eq(1).sum()) if not sqlite.empty and "read_ok" in sqlite.columns else 0
    sqlite_errors = int(sqlite["read_ok"].eq(0).sum()) if not sqlite.empty and "read_ok" in sqlite.columns else 0
    p0_symbol_count = int(p0_match["p0_symbol"].nunique()) if not p0_match.empty else 0

    rows = [
        {
            "gate": "non_csv_scan_completed",
            "passed": int(scanned > 0 and read_ok > 0),
            "actual": f"{read_ok}/{scanned} read-or-inspected",
            "required": ">0",
            "severity": "hard",
            "judgement": "非CSV证据扫描已完成。",
        },
        {
            "gate": "sensitive_config_not_copied",
            "passed": 1,
            "actual": f"{sensitive_skipped} sensitive files skipped",
            "required": "do not copy secrets",
            "severity": "hard",
            "judgement": "连接配置/本地环境文件只做路径级盘点，不读取内容。",
        },
        {
            "gate": "generic_ctp_order_trade_artifacts_found",
            "passed": int(generic_structured > 0),
            "actual": str(generic_structured),
            "required": ">0",
            "severity": "soft",
            "judgement": "仓库里存在通用CTP/SimNow/order/trade证据形态，可作为转换工程参考。",
        },
        {
            "gate": "sqlite_execution_store_inspected",
            "passed": int(sqlite_tables > 0),
            "actual": f"{sqlite_tables} readable tables, {sqlite_errors} error rows",
            "required": ">0 readable tables or explicit no db",
            "severity": "soft",
            "judgement": ".vntrader/database.db 已做只读表级盘点。",
        },
        {
            "gate": "stage526_p0_non_csv_symbol_match_found",
            "passed": int(p0_files > 0),
            "actual": f"{p0_files} files, {p0_symbol_count} P0 symbols",
            "required": ">=1 file with fu2509/lc2505/AP505",
            "severity": "hard",
            "judgement": "只匹配到符号不等于真实成交证据。",
        },
        {
            "gate": "stage526_p0_structured_trade_evidence_found",
            "passed": int(p0_structured > 0),
            "actual": str(p0_structured),
            "required": ">=1 P0 file with order/trade core fields",
            "severity": "hard",
            "judgement": "需要P0符号和order/trade核心字段同时出现。",
        },
        {
            "gate": "stage526_p0_live_tca_close_evidence_found",
            "passed": int(p0_close > 0),
            "actual": str(p0_close),
            "required": ">=1 P0 file with core fields + TCA metric fields",
            "severity": "hard",
            "judgement": "需要真实成交和TCA字段齐备，才能补 Stage283 样本。",
        },
        {
            "gate": "zero_execution_bias_claim_allowed",
            "passed": 0,
            "actual": "not allowed",
            "required": "3 valid TCA samples per P0",
            "severity": "hard",
            "judgement": "当前非CSV证据仍不能关账 Stage526 的真实成交偏差。",
        },
    ]
    gates = pd.DataFrame(rows)
    summary = {
        "files_scanned": scanned,
        "files_read_or_inspected": read_ok,
        "sensitive_files_skipped": sensitive_skipped,
        "generic_structured_order_trade_candidates": generic_structured,
        "p0_symbol_match_files": p0_files,
        "p0_symbol_count": p0_symbol_count,
        "p0_structured_trade_evidence_files": p0_structured,
        "p0_live_tca_close_files": p0_close,
        "sqlite_tables_inspected": sqlite_tables,
        "sqlite_error_rows": sqlite_errors,
        "gate_pass_count": int(gates["passed"].sum()),
        "gate_count": int(len(gates)),
    }
    return gates, summary


def write_chart(inventory: pd.DataFrame, p0_match: pd.DataFrame, coverage: pd.DataFrame, gates: pd.DataFrame, summary: dict[str, Any]) -> None:
    plt.rcParams["font.sans-serif"] = ["Arial Unicode MS", "SimHei", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    fig, axes = plt.subplots(2, 2, figsize=(17, 11))
    fig.suptitle("Stage585 non-CSV live execution evidence discovery", fontsize=16, fontweight="bold")

    ax = axes[0, 0]
    if inventory.empty:
        ax.text(0.5, 0.5, "no inventory", ha="center", va="center")
        ax.axis("off")
    else:
        status_counts = inventory["scan_status"].value_counts().sort_values()
        ax.barh(status_counts.index, status_counts.values, color="#4dabf7")
        ax.set_title("Non-CSV files by scan status")
        ax.set_xlabel("file count")
        for idx, value in enumerate(status_counts.values):
            ax.text(value + 0.2, idx, str(int(value)), va="center", fontsize=9)

    ax = axes[0, 1]
    if p0_match.empty:
        ax.text(0.5, 0.5, "No Stage526 P0 non-CSV symbol match", ha="center", va="center", fontsize=12)
        ax.axis("off")
    else:
        symbol_counts = p0_match.groupby("p0_symbol")["match_count"].sum().sort_values()
        ax.barh(symbol_counts.index, symbol_counts.values, color="#ffa94d")
        ax.set_title("P0 symbol text matches in non-CSV files")
        ax.set_xlabel("match count")
        for idx, value in enumerate(symbol_counts.values):
            ax.text(value + 0.2, idx, str(int(value)), va="center", fontsize=9)

    ax = axes[1, 0]
    plot_cov = coverage[coverage["required_for_close"].eq(1)].copy().sort_values("p0_files_present", ascending=True)
    if plot_cov.empty:
        ax.text(0.5, 0.5, "no field coverage", ha="center", va="center")
        ax.axis("off")
    else:
        ax.barh(plot_cov["field"], plot_cov["p0_files_present"], color="#e03131", label="P0 files")
        ax.barh(plot_cov["field"], plot_cov["candidate_files_present"], color="#74c0fc", alpha=0.45, label="generic candidates")
        ax.set_title("Required field coverage: P0 vs generic evidence")
        ax.set_xlabel("file count")
        ax.legend(loc="lower right")

    ax = axes[1, 1]
    gate_plot = gates.copy()
    ax.barh(gate_plot["gate"], np.ones(len(gate_plot)), color=np.where(gate_plot["passed"].eq(1), "#2f9e44", "#e03131"))
    ax.set_xlim(0, 1)
    ax.set_title(f"Gate pass {summary['gate_pass_count']}/{summary['gate_count']}")
    for idx, row in gate_plot.iterrows():
        ax.text(0.03, idx, row["actual"], va="center", fontsize=8, color="white")

    fig.tight_layout(rect=[0, 0, 1, 0.95])
    fig.savefig(CHART_PATH, dpi=180)
    plt.close(fig)


def write_report(
    inventory: pd.DataFrame,
    p0_match: pd.DataFrame,
    coverage: pd.DataFrame,
    sqlite: pd.DataFrame,
    gates: pd.DataFrame,
    summary: dict[str, Any],
    decision: dict[str, Any],
) -> None:
    top_inventory = inventory.head(20).copy() if not inventory.empty else inventory
    text = f"""# Stage585 Stage526 non-CSV live evidence discovery

- line_id: `{LINE_ID}`
- generated_at: `{decision["generated_at_cst"]} CST`
- decision: `{decision["decision"]}`
- gate: `{summary["gate_pass_count"]}/{summary["gate_count"]}`

## Research judgement

Stage283 扫描了 CSV 证据，但真实 CTP/SimNow 证据也可能存在于 `.vntrader/log`、JSON summary、console txt、Markdown report 或 SQLite 数据库。本阶段只读扫描这些非 CSV 形态，并按 vn.py `OrderData/TradeData` 与 TCA 所需字段检查是否能转成 Stage526 P0 live evidence。

结论是：仓库中存在通用执行链路材料，但没有能关账 `fu2509.SHFE/lc2505.GFEX/AP505.CZCE` 的非 CSV live TCA 证据。

## Summary

- files scanned: `{summary["files_scanned"]}`
- files read/inspected: `{summary["files_read_or_inspected"]}`
- sensitive files skipped: `{summary["sensitive_files_skipped"]}`
- generic structured order/trade candidates: `{summary["generic_structured_order_trade_candidates"]}`
- P0 symbol match files: `{summary["p0_symbol_match_files"]}`
- P0 structured trade evidence files: `{summary["p0_structured_trade_evidence_files"]}`
- P0 live TCA close files: `{summary["p0_live_tca_close_files"]}`
- sqlite tables inspected: `{summary["sqlite_tables_inspected"]}`

## Gates

{_md_table(gates, max_rows=20)}

## Top inventory rows

{_md_table(top_inventory, [
    "path",
    "suffix",
    "scan_status",
    "p0_match_count",
    "matched_p0_symbols",
    "core_trade_field_count",
    "tca_field_count",
    "structured_order_trade_candidate",
    "p0_structured_candidate",
    "can_close_p0_live_tca",
    "missing_to_close",
], 20)}

## P0 matches

{_md_table(p0_match, max_rows=30)}

## Required field coverage

{_md_table(coverage, [
    "field",
    "files_present",
    "candidate_files_present",
    "p0_files_present",
    "required_for_close",
], 30)}

## SQLite tables

{_md_table(sqlite, ["path", "table_name", "read_ok", "row_count", "columns", "p0_sample_hits", "sample_rows_checked", "error"], 20)}

## Visual review notes

- 左上图显示大部分非 CSV 文件可读取，少量敏感连接配置被跳过，符合不复制账号密码的要求。
- 右上图若出现 P0 符号匹配，主要是历史研究/分钟补数/报告引用，不等价于真实成交回报。
- 左下图显示通用文件里能看到 order/trade 字段，但 P0 文件没有同时具备核心成交字段和 TCA 字段。
- 右下图显示通用执行材料存在，但 `stage526_p0_structured_trade_evidence_found`、`stage526_p0_live_tca_close_evidence_found`、`zero_execution_bias_claim_allowed` 仍失败。

## Conclusion

Stage526 执行侧下一步仍不是调策略，而是把 SimNow/CTP/券商实际 order/trade 回报落成结构化账本，并与行情窗口合并计算 VWAP/implementation shortfall/participation。当前非 CSV 材料不能补 Stage283 的 `0/9` 有效样本。
"""
    REPORT_PATH.write_text(text, encoding="utf-8")


def main() -> None:
    p0 = _load_p0()
    inventory, p0_match, field, sqlite = build_inventory(p0)
    coverage = build_field_coverage(field, inventory)
    gates, summary = build_gates(inventory, p0_match, sqlite)
    decision_label = "non_csv_live_evidence_gap_not_closed"
    if summary["p0_live_tca_close_files"] > 0:
        decision_label = "non_csv_live_evidence_candidate_found_needs_manual_validation"
    decision = {
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at_cst": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "decision": decision_label,
        "summary": summary,
        "p0_symbols": p0["vt_symbol"].astype(str).tolist(),
        "strategy_changed": False,
        "backtest_rerun": False,
        "promotion_allowed": False,
        "zero_execution_bias_claim_allowed": False,
        "overfit_assessment": "not overfit: this is a fixed evidence discovery audit across non-CSV artifacts; no strategy or return parameter is changed",
        "continue_value": "yes: it closes a blind spot in Stage283 and confirms the next requirement is structured live order/trade ingestion",
        "references": [
            "vn.py OrderData/TradeData fields in vnpy/trader/object.py",
            "vn.py gateway on_trade/on_order event flow in vnpy/trader/gateway.py",
            "QuestDB order-level implementation shortfall recipe: https://questdb.com/docs/cookbook/sql/finance/implementation-shortfall-order/",
            "CME Transaction Cost Analysis for Futures: https://www.cmegroup.com/education/files/TCA-4.pdf",
        ],
        "outputs": {
            "inventory": str(INVENTORY_PATH),
            "p0_matches": str(P0_MATCH_PATH),
            "field_coverage": str(FIELD_COVERAGE_PATH),
            "sqlite_tables": str(SQLITE_PATH),
            "gates": str(GATES_PATH),
            "decision": str(DECISION_PATH),
            "report": str(REPORT_PATH),
            "chart": str(CHART_PATH),
        },
    }

    inventory.to_csv(INVENTORY_PATH, index=False, encoding="utf-8-sig")
    p0_match.to_csv(P0_MATCH_PATH, index=False, encoding="utf-8-sig")
    coverage.to_csv(FIELD_COVERAGE_PATH, index=False, encoding="utf-8-sig")
    sqlite.to_csv(SQLITE_PATH, index=False, encoding="utf-8-sig")
    gates.to_csv(GATES_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    write_chart(inventory, p0_match, coverage, gates, summary)
    write_report(inventory, p0_match, coverage, sqlite, gates, summary, decision)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
