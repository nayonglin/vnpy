from __future__ import annotations

from datetime import datetime
from io import BytesIO
import hashlib
import json
import re
from pathlib import Path
import sys
from typing import Any
import zipfile

import matplotlib

matplotlib.use("Agg")
from matplotlib.colors import BoundaryNorm, ListedColormap
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import requests
import urllib3


LINE_ID = "futures_trend_c9_minrisk_highquality"
STAGE = "Stage089"
MODEL_TAG = "stage089_external_raw_backfill_manifest_probe_v1"
OUTPUT_PREFIX = "qmt_roll_stage089_c9_minrisk_external_raw_backfill_manifest_probe"
ACCOUNT_CAPITAL = 150_000.0
REQUEST_TIMEOUT = 10
TRADING_DAYS_PER_YEAR = 252

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
EXAMPLE_DIR = REPO_DIR / "examples" / "portfolio_backtesting"
if str(EXAMPLE_DIR) not in sys.path:
    sys.path.insert(0, str(EXAMPLE_DIR))

from qmt_roll_official_live_config import OFFICIAL_LIVE_ALIAS, OFFICIAL_LIVE_VERSION


LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
STAGE010_DIR = LINE_DIR / "outputs" / "stage010_authoritative_minute_coverage_audit"
OUTPUT_DIR = LINE_DIR / "outputs" / "stage089_external_raw_backfill_manifest_probe"
RAW_DIR = OUTPUT_DIR / "raw"

OFFICIAL_CURVE_IN = (
    STAGE010_DIR
    / "qmt_roll_stage010_c9_minrisk_authoritative_minute_coverage_audit_official_curve_"
    "stage010_authoritative_minute_coverage_audit_v1.csv"
)
OFFICIAL_SUMMARY_IN = (
    STAGE010_DIR
    / "qmt_roll_stage010_c9_minrisk_authoritative_minute_coverage_audit_summary_"
    "stage010_authoritative_minute_coverage_audit_v1.csv"
)
OFFICIAL_CLOSED_LOTS_IN = (
    STAGE010_DIR
    / "qmt_roll_stage010_c9_minrisk_authoritative_minute_coverage_audit_official_closed_lots_"
    "stage010_authoritative_minute_coverage_audit_v1.csv"
)

MANIFEST_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_manifest_{MODEL_TAG}.csv"
SOURCE_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_source_summary_{MODEL_TAG}.csv"
PRODUCT_YEAR_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_year_requirement_{MODEL_TAG}.csv"
SCHEMA_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_schema_summary_{MODEL_TAG}.csv"
SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

OFFICIAL_MANIFEST_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_manifest_chart_{MODEL_TAG}.png"
SOURCE_YEAR_MATRIX_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_source_year_matrix_chart_{MODEL_TAG}.png"
PRODUCT_YEAR_HIT_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_year_hit_chart_{MODEL_TAG}.png"
SCHEMA_RAW_BYTES_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_schema_raw_bytes_chart_{MODEL_TAG}.png"

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36"
    )
}

SOURCE_SPECS = {
    "czce_member_rank": {
        "exchange": "CZCE",
        "method": "GET",
        "kind": "czce_holding_excel",
        "doc_url": "https://www.czce.com.cn/cn/jysj/ccpm/H077003004index_1.htm",
    },
    "czce_warehouse": {
        "exchange": "CZCE",
        "method": "GET",
        "kind": "czce_warehouse_excel",
        "doc_url": "https://www.czce.com.cn/cn/jysj/cdrb/H077003010index_1.htm",
    },
    "gfex_warehouse": {
        "exchange": "GFEX",
        "method": "POST_FORM",
        "kind": "gfex_warehouse_json",
        "doc_url": "https://www.gfex.com.cn/gfex/cdrb/hqsj_tjsj.shtml",
    },
}


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        number = float(value)
        return None if np.isnan(number) or np.isinf(number) else number
    if isinstance(value, (pd.Timestamp, datetime)):
        if pd.isna(value):
            return None
        return pd.Timestamp(value).strftime("%Y-%m-%d")
    return value


def _read_csv(path: Path, required: bool = True) -> pd.DataFrame:
    if not path.exists():
        if required:
            raise RuntimeError(f"missing required input: {path}")
        return pd.DataFrame()
    return pd.read_csv(path, encoding="utf-8-sig")


def _write_csv(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, encoding="utf-8-sig")


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_empty_"
    display = frame.head(max_rows).copy() if max_rows is not None else frame.copy()
    for column in display.columns:
        if pd.api.types.is_float_dtype(display[column]):
            display[column] = display[column].map(lambda value: "" if pd.isna(value) else f"{value:.4f}")
    lines = [
        "| " + " | ".join(str(column) for column in display.columns) + " |",
        "| " + " | ".join(["---"] * len(display.columns)) + " |",
    ]
    for _, row in display.iterrows():
        lines.append("| " + " | ".join(str(row[column]) for column in display.columns) + " |")
    return "\n".join(lines)


def _load_official_curve() -> pd.DataFrame:
    curve = _read_csv(OFFICIAL_CURVE_IN)
    curve["date"] = pd.to_datetime(curve["date"], errors="coerce").dt.normalize()
    curve = curve.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    for column in ["account_equity", "drawdown_pct", "slippage", "trade_count", "broker10_margin_to_equity_pct"]:
        curve[column] = pd.to_numeric(curve.get(column, 0.0), errors="coerce").fillna(0.0)
    prev = curve["account_equity"].shift(1)
    if not curve.empty:
        prev.iloc[0] = ACCOUNT_CAPITAL
    curve["daily_return"] = (curve["account_equity"] / prev - 1.0).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    return curve


def _official_metrics(curve: pd.DataFrame) -> dict[str, float]:
    official_summary = _read_csv(OFFICIAL_SUMMARY_IN, required=False)
    row = official_summary.iloc[0].to_dict() if not official_summary.empty else {}

    def val(column: str, default: float) -> float:
        try:
            number = float(row.get(column, default))
        except (TypeError, ValueError):
            return default
        return default if np.isnan(number) or np.isinf(number) else number

    returns = pd.to_numeric(curve["daily_return"], errors="coerce").fillna(0.0)
    std = float(returns.std(ddof=1)) if len(returns) > 1 else 0.0
    end = float(curve["account_equity"].iloc[-1]) if not curve.empty else ACCOUNT_CAPITAL
    return {
        "end_equity": val("end_equity", end),
        "total_return_pct": val("total_return_pct", (end / ACCOUNT_CAPITAL - 1.0) * 100.0),
        "max_dd_pct": val("max_dd_pct", float(curve["drawdown_pct"].min()) if not curve.empty else 0.0),
        "sharpe": val("sharpe", (float(returns.mean()) / std * np.sqrt(TRADING_DAYS_PER_YEAR)) if std > 0 else 0.0),
        "total_slippage": val("total_slippage", float(curve["slippage"].sum())),
        "total_trade_count": val("total_trade_count", float(curve["trade_count"].sum())),
        "win_rate_pct": val("nonzero_daily_win_rate_pct", 0.0),
        "broker10_peak_margin_to_equity_pct": val(
            "max_broker10_margin_to_equity_pct",
            float(curve["broker10_margin_to_equity_pct"].max()) if not curve.empty else 0.0,
        ),
    }


def _anchor_dates(curve: pd.DataFrame) -> list[str]:
    dates = pd.to_datetime(curve["date"]).sort_values().reset_index(drop=True)
    years = range(int(dates.dt.year.min()), int(dates.dt.year.max()) + 1)
    anchors: list[str] = []
    for year in years:
        target = pd.Timestamp(year=year, month=6, day=3)
        subset = dates[dates >= target]
        subset = subset[subset.dt.year.eq(year)]
        if subset.empty:
            subset = dates[dates.dt.year.eq(year)]
        if not subset.empty:
            anchors.append(pd.Timestamp(subset.iloc[0]).strftime("%Y%m%d"))
    return anchors


def _normalize_official_products() -> pd.DataFrame:
    lots = _read_csv(OFFICIAL_CLOSED_LOTS_IN)
    lots["entry_date"] = pd.to_datetime(lots["entry_date"], errors="coerce")
    lots = lots.dropna(subset=["entry_date"]).copy()

    def exchange_from_row(row: pd.Series) -> str:
        for value in [row.get("product", ""), row.get("vt_symbol", "")]:
            text = str(value)
            if "." in text:
                return text.split(".")[-1].upper()
        return "UNKNOWN"

    def root_from_row(row: pd.Series) -> str:
        text = str(row.get("vt_symbol", ""))
        match = re.match(r"([A-Za-z]+)", text)
        if match:
            return match.group(1).upper()
        text = str(row.get("product", "")).split(".")[0]
        match = re.match(r"([A-Za-z]+)", text)
        return match.group(1).upper() if match else text.upper()

    lots["exchange_norm"] = lots.apply(exchange_from_row, axis=1)
    lots["product_root"] = lots.apply(root_from_row, axis=1)
    lots["entry_year"] = lots["entry_date"].dt.year.astype(int)
    lots["realized_pnl"] = pd.to_numeric(lots.get("realized_pnl", 0.0), errors="coerce").fillna(0.0)
    grouped = (
        lots.groupby(["exchange_norm", "product_root", "entry_year"], as_index=False)
        .agg(lot_count=("lot_id", "count"), realized_pnl=("realized_pnl", "sum"))
        .sort_values(["exchange_norm", "product_root", "entry_year"])
    )
    return grouped


def _schema_hash(columns: list[str]) -> str:
    if not columns:
        return ""
    canonical = json.dumps(sorted(str(col) for col in columns), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def _normalized_schema_hash(columns: list[str]) -> str:
    normalized = []
    for column in columns:
        text = str(column)
        text = re.sub(r"\d{4}-\d{2}-\d{2}", "YYYY-MM-DD", text)
        text = re.sub(r"\d{8}", "YYYYMMDD", text)
        normalized.append(text)
    return _schema_hash(normalized)


def _symbols_from_czce_holding(content: bytes) -> tuple[int, list[str], list[str], str]:
    frame = pd.read_excel(BytesIO(content))
    columns = [str(col) for col in frame.columns]
    symbols: list[str] = []
    try:
        text_values = frame.astype(str).stack().dropna().astype(str)
        for item in text_values:
            match = re.search(r"品种：.*?([A-Za-z]{1,4})\s*日期", item)
            if match:
                symbols.append(match.group(1).upper())
    except Exception:
        pass
    return int(len(frame)), sorted(set(symbols)), columns, _normalized_schema_hash(columns)


def _symbols_from_czce_warehouse(content: bytes) -> tuple[int, list[str], list[str], str]:
    frame = pd.read_excel(BytesIO(content))
    columns = [str(col) for col in frame.columns]
    symbols: list[str] = []
    try:
        first_col = frame.iloc[:, 0].dropna().astype(str)
        for item in first_col:
            if item.startswith("品种"):
                match = re.search(r"([A-Za-z]+)", item)
                if match:
                    symbols.append(match.group(1).upper())
    except Exception:
        pass
    return int(len(frame)), sorted(set(symbols)), columns, _normalized_schema_hash(columns)


def _symbols_from_gfex_warehouse(content: bytes) -> tuple[int, list[str], list[str], str]:
    data = json.loads(content.decode("utf-8", errors="ignore"))
    rows = data.get("data", []) if isinstance(data, dict) else []
    columns = sorted(rows[0].keys()) if rows and isinstance(rows[0], dict) else sorted(data.keys()) if isinstance(data, dict) else []
    symbols = sorted({str(row.get("varietyOrder", "")).upper() for row in rows if str(row.get("varietyOrder", "")).strip()})
    return int(len(rows)), symbols, [str(col) for col in columns], _schema_hash([str(col) for col in columns])


def _raw_extension(kind: str, content: bytes, content_type: str, date: str) -> str:
    if zipfile.is_zipfile(BytesIO(content)):
        return "zip"
    if "json" in content_type.lower() or kind == "gfex_warehouse_json":
        return "json"
    if kind.startswith("czce"):
        return "xlsx" if int(date) > 20251101 else "xls"
    return "raw"


def _spec_for(source_id: str, date: str) -> dict[str, Any]:
    spec = SOURCE_SPECS[source_id].copy()
    year = date[:4]
    if source_id == "czce_member_rank":
        ext = "xlsx" if int(date) > 20251101 else "xls"
        spec.update(
            {
                "url": f"http://www.czce.com.cn/cn/DFSStaticFiles/Future/{year}/{date}/FutureDataHolding.{ext}",
                "payload": {},
            }
        )
    elif source_id == "czce_warehouse":
        ext = "xlsx" if int(date) > 20251101 else "xls"
        spec.update(
            {
                "url": f"http://www.czce.com.cn/cn/DFSStaticFiles/Future/{year}/{date}/FutureDataWhsheet.{ext}",
                "payload": {},
            }
        )
    elif source_id == "gfex_warehouse":
        spec.update(
            {
                "url": "http://www.gfex.com.cn/u/interfacesWebTdWbillWeeklyQuotes/loadList",
                "payload": {"gen_date": date},
            }
        )
    else:
        raise ValueError(f"unsupported source_id: {source_id}")
    return spec


def _run_manifest_probe(source_id: str, date: str) -> dict[str, Any]:
    spec = _spec_for(source_id, date)
    row = {
        "stage": STAGE,
        "source_id": source_id,
        "exchange": spec["exchange"],
        "trade_date": date,
        "year": int(date[:4]),
        "method": spec["method"],
        "url": spec["url"],
        "payload_json": json.dumps(spec.get("payload", {}), ensure_ascii=False, sort_keys=True),
        "doc_url": spec["doc_url"],
        "status": "error",
        "http_status": np.nan,
        "content_type": "",
        "content_bytes": 0,
        "sha256": "",
        "raw_file": "",
        "hash_ready": 0,
        "parse_ready": 0,
        "row_count": 0,
        "symbol_count": 0,
        "sample_symbols": "",
        "schema_hash": "",
        "schema_columns": "",
        "error_type": "",
        "error_message": "",
        "parse_error_type": "",
        "parse_error_message": "",
    }
    try:
        if spec["method"] == "POST_FORM":
            response = requests.post(
                spec["url"],
                data=spec.get("payload", {}),
                headers=HEADERS,
                timeout=REQUEST_TIMEOUT,
                verify=False,
            )
        else:
            response = requests.get(spec["url"], headers=HEADERS, timeout=REQUEST_TIMEOUT, verify=False)
        content = response.content or b""
        digest = hashlib.sha256(content).hexdigest() if content else ""
        content_type = str(response.headers.get("content-type", ""))
        raw_ext = _raw_extension(spec["kind"], content, content_type, date)
        raw_path = RAW_DIR / source_id / f"{source_id}_{date}.{raw_ext}"
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        raw_path.write_bytes(content)
        row.update(
            {
                "status": "http_ok" if 200 <= int(response.status_code) < 300 else "http_error",
                "http_status": int(response.status_code),
                "content_type": content_type,
                "content_bytes": int(len(content)),
                "sha256": digest,
                "raw_file": str(raw_path.relative_to(REPO_DIR)),
                "hash_ready": int(bool(digest)),
            }
        )
        if 200 <= int(response.status_code) < 300:
            try:
                if spec["kind"] == "czce_holding_excel":
                    row_count, symbols, columns, schema_hash = _symbols_from_czce_holding(content)
                elif spec["kind"] == "czce_warehouse_excel":
                    row_count, symbols, columns, schema_hash = _symbols_from_czce_warehouse(content)
                else:
                    row_count, symbols, columns, schema_hash = _symbols_from_gfex_warehouse(content)
                row.update(
                    {
                        "parse_ready": 1,
                        "row_count": row_count,
                        "symbol_count": len(symbols),
                        "sample_symbols": "|".join(symbols[:40]),
                        "schema_hash": schema_hash,
                        "schema_columns": "|".join(columns[:40]),
                        "status": "parsed_ok",
                    }
                )
            except Exception as exc:  # noqa: BLE001
                row["status"] = "http_ok_parse_failed"
                row["parse_error_type"] = type(exc).__name__
                row["parse_error_message"] = str(exc)[:300]
    except Exception as exc:  # noqa: BLE001
        row["status"] = "network_error"
        row["error_type"] = type(exc).__name__
        row["error_message"] = str(exc)[:300]
    return row


def _source_summary(manifest: pd.DataFrame, anchors: list[str]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for source_id, group in manifest.groupby("source_id", sort=True):
        parsed = int(pd.to_numeric(group["parse_ready"], errors="coerce").fillna(0).sum())
        hashed = int(pd.to_numeric(group["hash_ready"], errors="coerce").fillna(0).sum())
        years = sorted(group.loc[group["parse_ready"].eq(1), "year"].astype(int).unique().tolist())
        schema_count = int(group.loc[group["schema_hash"].astype(str).ne(""), "schema_hash"].nunique())
        small_manifest_pass = int(len(group) == len(anchors) and parsed == len(group) and hashed == len(group))
        rows.append(
            {
                "source_id": source_id,
                "exchange": str(group["exchange"].iloc[0]),
                "anchor_count": int(len(group)),
                "parsed_count": parsed,
                "hash_count": hashed,
                "http_error_count": int(group["status"].eq("http_error").sum()),
                "network_error_count": int(group["status"].eq("network_error").sum()),
                "parse_fail_count": int(group["status"].eq("http_ok_parse_failed").sum()),
                "total_rows": int(pd.to_numeric(group["row_count"], errors="coerce").fillna(0).sum()),
                "schema_hash_count": schema_count,
                "parsed_years": "|".join(str(year) for year in years),
                "small_manifest_pass": small_manifest_pass,
                "full_history_ready": 0,
                "next_action": (
                    "design_full_backfill_manifest_with_rate_limit_and_c9_product_validation"
                    if small_manifest_pass
                    else "repair_endpoint_or_restrict_to_authorized_offline_raw_before_full_backfill"
                ),
            }
        )
    return pd.DataFrame(rows).sort_values(["small_manifest_pass", "source_id"], ascending=[False, True])


def _product_year_requirement(manifest: pd.DataFrame, product_years: pd.DataFrame, anchors: list[str]) -> pd.DataFrame:
    parsed_lookup = {
        (str(row.source_id), int(row.year)): {
            "parse_ready": int(row.parse_ready),
            "sample_symbols": str(row.sample_symbols),
            "schema_hash": str(row.schema_hash),
        }
        for row in manifest.itertuples(index=False)
    }
    rows: list[dict[str, Any]] = []
    for source_id, spec in SOURCE_SPECS.items():
        relevant = product_years[product_years["exchange_norm"].eq(spec["exchange"])].copy()
        anchor_years = sorted({int(date[:4]) for date in anchors})
        products = sorted(str(product).upper() for product in relevant["product_root"].dropna().astype(str).unique())
        for product in products:
            for year in anchor_years:
                lookup = parsed_lookup.get((source_id, year), {"parse_ready": 0, "sample_symbols": "", "schema_hash": ""})
                symbols = {symbol.upper() for symbol in str(lookup["sample_symbols"]).split("|") if symbol}
                product_symbol_hit = int(product in symbols or any(symbol.startswith(product) for symbol in symbols))
                official_row = relevant[
                    relevant["product_root"].eq(product)
                    & relevant["entry_year"].astype(int).eq(year)
                ]
                rows.append(
                    {
                        "source_id": source_id,
                        "exchange": spec["exchange"],
                        "product_root": product,
                        "year": year,
                        "official_lot_count": int(official_row["lot_count"].sum()) if not official_row.empty else 0,
                        "official_realized_pnl": float(official_row["realized_pnl"].sum()) if not official_row.empty else 0.0,
                        "anchor_parse_ready": int(lookup["parse_ready"]),
                        "product_symbol_hit": product_symbol_hit,
                        "schema_hash": str(lookup["schema_hash"]),
                        "sample_symbols": str(lookup["sample_symbols"]),
                    }
                )
    return pd.DataFrame(rows).sort_values(["source_id", "exchange", "product_root", "year"])


def _schema_summary(manifest: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for (source_id, schema_hash), group in manifest[manifest["schema_hash"].astype(str).ne("")].groupby(["source_id", "schema_hash"]):
        rows.append(
            {
                "source_id": source_id,
                "schema_hash": schema_hash,
                "date_count": int(len(group)),
                "first_date": str(group["trade_date"].min()),
                "last_date": str(group["trade_date"].max()),
                "sample_schema_columns": str(group["schema_columns"].iloc[0]),
            }
        )
    return pd.DataFrame(rows).sort_values(["source_id", "first_date"])


def _summary(curve: pd.DataFrame, manifest: pd.DataFrame, source_summary: pd.DataFrame, product_year: pd.DataFrame) -> pd.DataFrame:
    metrics = _official_metrics(curve)
    parsed_count = int(pd.to_numeric(manifest["parse_ready"], errors="coerce").fillna(0).sum())
    hash_count = int(pd.to_numeric(manifest["hash_ready"], errors="coerce").fillna(0).sum())
    small_pass = int(source_summary["small_manifest_pass"].sum())
    product_hits = int(product_year["product_symbol_hit"].sum()) if not product_year.empty else 0
    product_requirements = int(len(product_year))
    active_product_year = product_year[product_year["official_lot_count"].gt(0)] if not product_year.empty else pd.DataFrame()
    active_product_hits = int(active_product_year["product_symbol_hit"].sum()) if not active_product_year.empty else 0
    active_product_requirements = int(len(active_product_year))
    decision = (
        "stage089_small_raw_manifest_all_three_sources_pass_but_not_full_history_no_rule"
        if small_pass == len(SOURCE_SPECS)
        else "stage089_small_raw_manifest_partial_or_blocked_no_rule"
    )
    return pd.DataFrame(
        [
            {
                "stage": STAGE,
                "model_tag": MODEL_TAG,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "line_id": LINE_ID,
                "decision": decision,
                "official_live_alias": OFFICIAL_LIVE_ALIAS,
                "official_live_version": OFFICIAL_LIVE_VERSION,
                "official_config_changed": 0,
                "strategy_rule_created": 0,
                "true_engine_run": 0,
                "ab_triggered": 0,
                "order_api_called": 0,
                "ctp_connected": 0,
                "source_count": int(len(SOURCE_SPECS)),
                "anchor_date_count": int(manifest["trade_date"].nunique()),
                "manifest_row_count": int(len(manifest)),
                "manifest_parsed_count": parsed_count,
                "manifest_hash_count": hash_count,
                "small_manifest_pass_source_count": small_pass,
                "full_history_ready_source_count": 0,
                "product_year_requirement_count": product_requirements,
                "product_year_symbol_hit_count": product_hits,
                "active_product_year_requirement_count": active_product_requirements,
                "active_product_year_symbol_hit_count": active_product_hits,
                **metrics,
            }
        ]
    )


def _plot_official_manifest(curve: pd.DataFrame, manifest: pd.DataFrame, summary: pd.Series) -> None:
    yearly = manifest.pivot_table(index="year", columns="source_id", values="parse_ready", aggfunc="sum").fillna(0.0)
    fig, axes = plt.subplots(4, 1, figsize=(14, 10), gridspec_kw={"height_ratios": [2.0, 1.1, 1.1, 1.2]})
    axes[0].plot(curve["date"], curve["account_equity"], color="#0f766e", linewidth=1.5)
    axes[0].set_title("Stage089 official C9/15w path with small raw manifest anchors")
    axes[0].set_ylabel("equity")
    axes[0].grid(True, alpha=0.25)
    axes[1].plot(curve["date"], curve["drawdown_pct"], color="#dc2626", linewidth=1.2)
    axes[1].set_ylabel("drawdown %")
    axes[1].grid(True, alpha=0.25)
    axes[2].plot(curve["date"], curve["broker10_margin_to_equity_pct"], color="#7c3aed", linewidth=1.2)
    axes[2].axhline(100, color="#111827", linestyle="--", linewidth=0.8)
    axes[2].set_ylabel("broker10 %")
    axes[2].grid(True, alpha=0.25)
    x = np.arange(len(yearly.index))
    width = 0.25
    colors = ["#2563eb", "#f97316", "#16a34a"]
    for idx, column in enumerate(yearly.columns):
        axes[3].bar(x + (idx - 1) * width, yearly[column], width=width, label=column, color=colors[idx % len(colors)])
    axes[3].set_xticks(x)
    axes[3].set_xticklabels(yearly.index.astype(str).tolist())
    axes[3].set_ylabel("parsed anchors")
    axes[3].set_title("Fixed annual anchor parse-ready count by source")
    axes[3].grid(True, axis="y", alpha=0.25)
    axes[3].legend(loc="upper left")
    fig.suptitle(
        f"Decision={summary['decision']} | small manifest pass "
        f"{int(summary['small_manifest_pass_source_count'])}/{int(summary['source_count'])}; full history ready 0",
        y=0.995,
        fontsize=12,
    )
    fig.tight_layout()
    fig.savefig(OFFICIAL_MANIFEST_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_source_year_matrix(manifest: pd.DataFrame) -> None:
    pivot = manifest.pivot_table(index="source_id", columns="year", values="parse_ready", aggfunc="max").fillna(0.0)
    fig, ax = plt.subplots(figsize=(11, 4.5))
    im = ax.imshow(pivot.to_numpy(dtype=float), aspect="auto", vmin=0, vmax=1, cmap="RdYlGn")
    ax.set_xticks(np.arange(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns.astype(str).tolist(), rotation=0)
    ax.set_yticks(np.arange(len(pivot.index)))
    ax.set_yticklabels(pivot.index.tolist())
    for i in range(pivot.shape[0]):
        for j in range(pivot.shape[1]):
            ax.text(j, i, str(int(pivot.iloc[i, j])), ha="center", va="center", fontsize=9)
    ax.set_title("Stage089 source-year raw manifest parse-ready matrix")
    fig.colorbar(im, ax=ax, fraction=0.025, pad=0.02)
    fig.tight_layout()
    fig.savefig(SOURCE_YEAR_MATRIX_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_product_year_hit(product_year: pd.DataFrame) -> None:
    active = product_year[product_year["official_lot_count"].gt(0)].copy()
    if active.empty:
        active = product_year.copy()
    active["row_label"] = active["source_id"] + ":" + active["product_root"]
    pivot = active.pivot_table(index="row_label", columns="year", values="product_symbol_hit", aggfunc="max")
    data = pivot.fillna(-1.0)
    fig, ax = plt.subplots(figsize=(12, max(5, 0.3 * len(pivot.index))))
    cmap = ListedColormap(["#e5e7eb", "#b91c1c", "#047857"])
    norm = BoundaryNorm([-1.5, -0.5, 0.5, 1.5], cmap.N)
    im = ax.imshow(data.to_numpy(dtype=float), aspect="auto", cmap=cmap, norm=norm)
    ax.set_xticks(np.arange(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns.astype(str).tolist())
    ax.set_yticks(np.arange(len(pivot.index)))
    ax.set_yticklabels(pivot.index.tolist(), fontsize=7)
    for i in range(pivot.shape[0]):
        for j in range(pivot.shape[1]):
            value = data.iloc[i, j]
            label = "-" if value < 0 else str(int(value))
            ax.text(j, i, label, ha="center", va="center", fontsize=7)
    ax.set_title("C9 active product-year hit in annual raw anchor symbols; gray=not applicable")
    cbar = fig.colorbar(im, ax=ax, fraction=0.025, pad=0.02, ticks=[-1, 0, 1])
    cbar.ax.set_yticklabels(["n/a", "miss", "hit"])
    fig.tight_layout()
    fig.savefig(PRODUCT_YEAR_HIT_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_schema_raw_bytes(manifest: pd.DataFrame) -> None:
    data = manifest.copy().sort_values(["source_id", "trade_date"])
    data["content_kb"] = pd.to_numeric(data["content_bytes"], errors="coerce").fillna(0.0) / 1024.0
    fig, ax = plt.subplots(figsize=(14, max(5, 0.3 * len(data))))
    colors = np.where(data["parse_ready"].eq(1), "#16a34a", np.where(data["hash_ready"].eq(1), "#f59e0b", "#dc2626"))
    y = np.arange(len(data))
    labels = data["source_id"] + "_" + data["trade_date"].astype(str) + "_" + data["schema_hash"].astype(str).str[:6]
    ax.barh(y, data["content_kb"], color=colors)
    ax.set_yticks(y)
    ax.set_yticklabels(labels.tolist(), fontsize=7)
    ax.set_xlabel("raw response size KB")
    ax.set_title("Stage089 raw bytes and schema hash by annual anchor; green=parsed")
    ax.grid(True, axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(SCHEMA_RAW_BYTES_CHART_OUT, dpi=160)
    plt.close(fig)


def _write_report(
    summary: pd.DataFrame,
    source_summary: pd.DataFrame,
    manifest: pd.DataFrame,
    product_year: pd.DataFrame,
    schema_summary: pd.DataFrame,
) -> None:
    row = summary.iloc[0]
    report = "\n".join(
        [
            f"# {STAGE} external raw backfill manifest probe",
            "",
            "## Decision",
            "",
            f"- decision: `{row['decision']}`",
            f"- official: `{OFFICIAL_LIVE_ALIAS}` / `{OFFICIAL_LIVE_VERSION}`",
            "- nature: small raw backfill manifest probe; no strategy rule, no true engine, no A/B, no CTP, no order API.",
            "",
            "## Official baseline",
            "",
            f"- end equity: `{row['end_equity']:,.2f}`",
            f"- total return: `{row['total_return_pct']:.4f}%`",
            f"- max drawdown: `{row['max_dd_pct']:.4f}%`",
            f"- Sharpe: `{row['sharpe']:.4f}`",
            f"- total slippage: `{row['total_slippage']:,.0f}`",
            f"- total trade count: `{row['total_trade_count']:.0f}`",
            f"- win rate: `{row['win_rate_pct']:.4f}%`",
            f"- broker10 peak: `{row['broker10_peak_margin_to_equity_pct']:.4f}%`",
            "",
            "## Manifest summary",
            "",
            f"- anchor dates: `{int(row['anchor_date_count'])}`",
            f"- manifest rows: `{int(row['manifest_row_count'])}`, parsed `{int(row['manifest_parsed_count'])}`, hashed `{int(row['manifest_hash_count'])}`",
            f"- small manifest pass sources: `{int(row['small_manifest_pass_source_count'])}/{int(row['source_count'])}`",
            f"- full history ready sources: `{int(row['full_history_ready_source_count'])}`",
            f"- product-year symbol hits: `{int(row['product_year_symbol_hit_count'])}/{int(row['product_year_requirement_count'])}`",
            f"- active product-year symbol hits: `{int(row['active_product_year_symbol_hit_count'])}/{int(row['active_product_year_requirement_count'])}`",
            "",
            "## Source summary",
            "",
            _md_table(source_summary, max_rows=20),
            "",
            "## Schema summary",
            "",
            _md_table(schema_summary, max_rows=40),
            "",
            "## Manifest sample",
            "",
            _md_table(
                manifest[
                    [
                        "source_id",
                        "trade_date",
                        "status",
                        "http_status",
                        "content_bytes",
                        "parse_ready",
                        "row_count",
                        "symbol_count",
                        "schema_hash",
                        "raw_file",
                    ]
                ],
                max_rows=40,
            ),
            "",
            "## Product-year sample",
            "",
            _md_table(
                product_year[
                    [
                        "source_id",
                        "product_root",
                        "year",
                        "official_lot_count",
                        "anchor_parse_ready",
                        "product_symbol_hit",
                        "schema_hash",
                    ]
                ],
                max_rows=60,
            ),
            "",
            "## Visual outputs",
            "",
            f"- official manifest chart: `{OFFICIAL_MANIFEST_CHART_OUT}`",
            f"- source-year matrix chart: `{SOURCE_YEAR_MATRIX_CHART_OUT}`",
            f"- product-year hit chart: `{PRODUCT_YEAR_HIT_CHART_OUT}`",
            f"- schema raw bytes chart: `{SCHEMA_RAW_BYTES_CHART_OUT}`",
            "",
            "## External sources used",
            "",
            "- AKShare futures docs and local wrapper source define CZCE member/warehouse and GFEX warehouse endpoint patterns.",
            "- AKShare changelog confirms recent CZCE wrapper renames, so raw manifest stores URL, payload, raw bytes and hash instead of trusting wrapper output.",
            "- GFEX/CZCE official public URLs are retained in the manifest as source documentation, but this stage still treats them as sample probes only.",
            "",
            "## Judgment",
            "",
            "- Passing annual anchors proves only that a small raw manifest route can be engineered.",
            "- This does not prove full C9 product/history coverage, schema stability over every trading day, or strategy value.",
            "- No manifest status, source id, product hit or missing state may be used as a trading rule.",
        ]
    )
    REPORT_OUT.write_text(report + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    curve = _load_official_curve()
    anchors = _anchor_dates(curve)
    manifest_rows = [_run_manifest_probe(source_id, date) for source_id in SOURCE_SPECS for date in anchors]
    manifest = pd.DataFrame(manifest_rows)
    product_years = _normalize_official_products()
    source_summary = _source_summary(manifest, anchors)
    product_year = _product_year_requirement(manifest, product_years, anchors)
    schema_summary = _schema_summary(manifest)
    summary = _summary(curve, manifest, source_summary, product_year)

    _write_csv(manifest, MANIFEST_OUT)
    _write_csv(source_summary, SOURCE_SUMMARY_OUT)
    _write_csv(product_year, PRODUCT_YEAR_OUT)
    _write_csv(schema_summary, SCHEMA_SUMMARY_OUT)
    _write_csv(summary, SUMMARY_OUT)
    DECISION_OUT.write_text(
        json.dumps(_json_safe(summary.iloc[0].to_dict()), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    _plot_official_manifest(curve, manifest, summary.iloc[0])
    _plot_source_year_matrix(manifest)
    _plot_product_year_hit(product_year)
    _plot_schema_raw_bytes(manifest)
    _write_report(summary, source_summary, manifest, product_year, schema_summary)

    print(json.dumps(_json_safe(summary.iloc[0].to_dict()), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
