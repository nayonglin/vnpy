from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys
import time
from typing import Any

import matplotlib

matplotlib.use("Agg")
from matplotlib.colors import BoundaryNorm, ListedColormap
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import requests
import urllib3


LINE_ID = "futures_trend_c9_minrisk_highquality"
STAGE = "Stage091"
MODEL_TAG = "stage091_preentry_window_raw_full_backfill_v1"
OUTPUT_PREFIX = "qmt_roll_stage091_c9_minrisk_preentry_window_raw_full_backfill"
REQUEST_TIMEOUT = 15
REQUEST_RETRIES = 2
REQUEST_SLEEP_SECONDS = 0.12
CHECKPOINT_EVERY = 25

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
EXAMPLE_DIR = REPO_DIR / "examples" / "portfolio_backtesting"
if str(EXAMPLE_DIR) not in sys.path:
    sys.path.insert(0, str(EXAMPLE_DIR))

from qmt_roll_official_live_config import OFFICIAL_LIVE_ALIAS, OFFICIAL_LIVE_VERSION
from stage089_external_raw_backfill_manifest_probe import (
    HEADERS,
    SOURCE_SPECS,
    _json_safe,
    _load_official_curve,
    _md_table,
    _official_metrics,
    _raw_extension,
    _read_csv,
    _schema_hash,
    _spec_for,
    _symbols_from_czce_holding,
    _symbols_from_czce_warehouse,
    _symbols_from_gfex_warehouse,
    _write_csv,
)


LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
STAGE090_DIR = LINE_DIR / "outputs" / "stage090_preentry_window_raw_manifest_design"
OUTPUT_DIR = LINE_DIR / "outputs" / "stage091_preentry_window_raw_full_backfill"
RAW_DIR = OUTPUT_DIR / "raw"

PLAN_IN = (
    STAGE090_DIR
    / "qmt_roll_stage090_c9_minrisk_preentry_window_raw_manifest_design_planned_raw_manifest_"
    "stage090_preentry_window_raw_manifest_design_v1.csv"
)

RESULTS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_backfill_results_{MODEL_TAG}.csv"
SOURCE_YEAR_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_source_year_summary_{MODEL_TAG}.csv"
PRODUCT_YEAR_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_year_coverage_{MODEL_TAG}.csv"
SOURCE_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_source_summary_{MODEL_TAG}.csv"
SCHEMA_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_schema_summary_{MODEL_TAG}.csv"
FAILURE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_failure_rows_{MODEL_TAG}.csv"
SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

OFFICIAL_PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_backfill_chart_{MODEL_TAG}.png"
SOURCE_YEAR_HEATMAP_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_source_year_parse_heatmap_{MODEL_TAG}.png"
PRODUCT_YEAR_HEATMAP_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_year_hit_heatmap_{MODEL_TAG}.png"
SCHEMA_BYTES_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_schema_bytes_chart_{MODEL_TAG}.png"

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def _target_date(value: Any) -> str:
    text = str(value).strip()
    if text.endswith(".0"):
        text = text[:-2]
    return text.zfill(8)


def _parse_content(source_id: str, content: bytes) -> tuple[int, list[str], list[str], str]:
    kind = SOURCE_SPECS[source_id]["kind"]
    if kind == "czce_holding_excel":
        return _symbols_from_czce_holding(content)
    if kind == "czce_warehouse_excel":
        return _symbols_from_czce_warehouse(content)
    return _symbols_from_gfex_warehouse(content)


def _row_key(source_id: str, target_date: str) -> str:
    return f"{source_id}|{target_date}"


def _load_plan() -> pd.DataFrame:
    plan = _read_csv(PLAN_IN)
    plan["source_id"] = plan["source_id"].astype(str)
    plan["target_date"] = plan["target_date"].map(_target_date)
    plan["target_year"] = plan["target_date"].str.slice(0, 4).astype(int)
    plan["needed_products"] = plan["needed_products"].fillna("").astype(str)
    plan["_key"] = plan.apply(lambda row: _row_key(str(row["source_id"]), str(row["target_date"])), axis=1)
    plan = plan.sort_values(["source_id", "target_date"]).drop_duplicates("_key").reset_index(drop=True)
    return plan


def _load_resume_results() -> dict[str, dict[str, Any]]:
    if not RESULTS_OUT.exists():
        return {}
    existing = _read_csv(RESULTS_OUT, required=False)
    if existing.empty:
        return {}
    existing["target_date"] = existing["target_date"].map(_target_date)
    rows: dict[str, dict[str, Any]] = {}
    for row in existing.to_dict("records"):
        key = _row_key(str(row.get("source_id", "")), str(row.get("target_date", "")))
        raw_file = str(row.get("raw_file", ""))
        raw_exists = bool(raw_file and (REPO_DIR / raw_file).exists())
        parsed = str(row.get("status", "")) == "parsed_ok" and int(float(row.get("parse_ready", 0) or 0)) == 1
        if parsed and raw_exists:
            rows[key] = row
    return rows


def _base_result(row: pd.Series, spec: dict[str, Any]) -> dict[str, Any]:
    return {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "source_id": str(row["source_id"]),
        "exchange": str(row["exchange"]),
        "target_date": str(row["target_date"]),
        "target_year": int(row["target_year"]),
        "method": str(spec["method"]),
        "url": str(spec["url"]),
        "payload_json": json.dumps(spec.get("payload", {}), ensure_ascii=False, sort_keys=True),
        "doc_url": str(spec["doc_url"]),
        "needed_products": str(row["needed_products"]),
        "needed_product_count": int(row["needed_product_count"]),
        "linked_lot_count": int(row["linked_lot_count"]),
        "linked_vt_symbol_count": int(row["linked_vt_symbol_count"]),
        "status": "not_attempted",
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
        "needed_symbol_hit_count": 0,
        "needed_symbol_miss_count": int(row["needed_product_count"]),
        "needed_symbol_hit_all": 0,
        "schema_hash": "",
        "schema_columns": "",
        "attempt_count": 0,
        "error_type": "",
        "error_message": "",
        "parse_error_type": "",
        "parse_error_message": "",
    }


def _request(spec: dict[str, Any]) -> requests.Response:
    if spec["method"] == "POST_FORM":
        return requests.post(
            spec["url"],
            data=spec.get("payload", {}),
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT,
            verify=False,
        )
    return requests.get(spec["url"], headers=HEADERS, timeout=REQUEST_TIMEOUT, verify=False)


def _download_row(row: pd.Series) -> dict[str, Any]:
    source_id = str(row["source_id"])
    target_date = str(row["target_date"])
    spec = _spec_for(source_id, target_date)
    out = _base_result(row, spec)
    last_exc: Exception | None = None

    for attempt in range(1, REQUEST_RETRIES + 2):
        out["attempt_count"] = attempt
        try:
            response = _request(spec)
            content = response.content or b""
            digest = hashlib.sha256(content).hexdigest() if content else ""
            content_type = str(response.headers.get("content-type", ""))
            raw_ext = _raw_extension(spec["kind"], content, content_type, target_date)
            raw_path = RAW_DIR / source_id / f"{source_id}_{target_date}.{raw_ext}"
            raw_path.parent.mkdir(parents=True, exist_ok=True)
            raw_path.write_bytes(content)
            out.update(
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
                    row_count, symbols, columns, schema_hash = _parse_content(source_id, content)
                    symbol_set = {symbol.upper() for symbol in symbols}
                    needed = {symbol.upper() for symbol in str(row["needed_products"]).split("|") if symbol}
                    hits = {
                        product
                        for product in needed
                        if product in symbol_set or any(symbol.startswith(product) for symbol in symbol_set)
                    }
                    out.update(
                        {
                            "status": "parsed_ok",
                            "parse_ready": 1,
                            "row_count": int(row_count),
                            "symbol_count": int(len(symbols)),
                            "sample_symbols": "|".join(symbols[:80]),
                            "needed_symbol_hit_count": int(len(hits)),
                            "needed_symbol_miss_count": int(max(len(needed) - len(hits), 0)),
                            "needed_symbol_hit_all": int(len(hits) == len(needed)),
                            "schema_hash": schema_hash,
                            "schema_columns": "|".join(columns[:40]),
                        }
                    )
                except Exception as exc:  # noqa: BLE001
                    out["status"] = "http_ok_parse_failed"
                    out["parse_error_type"] = type(exc).__name__
                    out["parse_error_message"] = str(exc)[:300]
            return out
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            time.sleep(REQUEST_SLEEP_SECONDS * attempt)

    out["status"] = "network_error"
    out["error_type"] = type(last_exc).__name__ if last_exc else "UnknownError"
    out["error_message"] = str(last_exc)[:300] if last_exc else ""
    return out


def _checkpoint(results: list[dict[str, Any]]) -> None:
    frame = pd.DataFrame(results).sort_values(["source_id", "target_date"]).reset_index(drop=True)
    _write_csv(frame, RESULTS_OUT)


def _run_backfill(plan: pd.DataFrame) -> pd.DataFrame:
    resume = _load_resume_results()
    results: list[dict[str, Any]] = []
    completed = 0
    total = len(plan)
    for _, row in plan.iterrows():
        key = str(row["_key"])
        if key in resume:
            results.append(resume[key])
            completed += 1
            continue
        result = _download_row(row)
        results.append(result)
        completed += 1
        if completed % CHECKPOINT_EVERY == 0:
            _checkpoint(results)
            print(f"{STAGE} progress {completed}/{total}", flush=True)
        time.sleep(REQUEST_SLEEP_SECONDS)
    _checkpoint(results)
    return pd.DataFrame(results).sort_values(["source_id", "target_date"]).reset_index(drop=True)


def _source_year_summary(plan: pd.DataFrame, results: pd.DataFrame) -> pd.DataFrame:
    merged = plan[["_key", "source_id", "exchange", "target_date", "target_year", "needed_products"]].merge(
        results,
        on=["source_id", "target_date", "target_year"],
        how="left",
        suffixes=("_plan", ""),
    )
    rows: list[dict[str, Any]] = []
    for (source_id, year), group in merged.groupby(["source_id", "target_year"], sort=True):
        parse_ready = pd.to_numeric(group.get("parse_ready", 0), errors="coerce").fillna(0)
        hash_ready = pd.to_numeric(group.get("hash_ready", 0), errors="coerce").fillna(0)
        hit_all = pd.to_numeric(group.get("needed_symbol_hit_all", 0), errors="coerce").fillna(0)
        rows.append(
            {
                "source_id": source_id,
                "exchange": str(group["exchange_plan"].iloc[0]) if "exchange_plan" in group else str(group["exchange"].iloc[0]),
                "target_year": int(year),
                "planned_count": int(len(group)),
                "hash_count": int(hash_ready.sum()),
                "parsed_count": int(parse_ready.sum()),
                "needed_hit_all_count": int(hit_all.sum()),
                "http_error_count": int(group["status"].eq("http_error").sum()),
                "parse_fail_count": int(group["status"].eq("http_ok_parse_failed").sum()),
                "network_error_count": int(group["status"].eq("network_error").sum()),
                "median_content_bytes": float(pd.to_numeric(group.get("content_bytes", 0), errors="coerce").median()),
            }
        )
    return pd.DataFrame(rows).sort_values(["source_id", "target_year"])


def _product_year_coverage(plan: pd.DataFrame, results: pd.DataFrame) -> pd.DataFrame:
    merged = plan.merge(
        results[
            [
                "source_id",
                "target_date",
                "parse_ready",
                "needed_symbol_hit_all",
                "sample_symbols",
                "status",
            ]
        ],
        on=["source_id", "target_date"],
        how="left",
    )
    rows: list[dict[str, Any]] = []
    for row in merged.itertuples(index=False):
        needed = [item for item in str(row.needed_products).split("|") if item]
        symbols = {symbol.upper() for symbol in str(row.sample_symbols).split("|") if symbol}
        for product in needed:
            product_u = product.upper()
            hit = int(product_u in symbols or any(symbol.startswith(product_u) for symbol in symbols))
            rows.append(
                {
                    "source_id": str(row.source_id),
                    "exchange": str(row.exchange),
                    "product_root": product_u,
                    "target_year": int(row.target_year),
                    "target_date": str(row.target_date),
                    "parse_ready": int(float(row.parse_ready or 0)) if not pd.isna(row.parse_ready) else 0,
                    "hit": hit,
                    "status": str(row.status),
                }
            )
    expanded = pd.DataFrame(rows)
    if expanded.empty:
        return expanded
    summary = (
        expanded.groupby(["source_id", "exchange", "product_root", "target_year"], as_index=False)
        .agg(
            planned_date_count=("target_date", "nunique"),
            parsed_date_count=("parse_ready", "sum"),
            hit_date_count=("hit", "sum"),
            miss_date_count=("hit", lambda value: int((pd.to_numeric(value, errors="coerce").fillna(0) == 0).sum())),
            first_target_date=("target_date", "min"),
            last_target_date=("target_date", "max"),
        )
        .sort_values(["source_id", "product_root", "target_year"])
    )
    summary["hit_ratio"] = summary["hit_date_count"] / summary["planned_date_count"].replace(0, np.nan)
    summary["all_dates_hit"] = (summary["hit_date_count"].eq(summary["planned_date_count"])).astype(int)
    return summary


def _source_summary(results: pd.DataFrame, plan: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for source_id, group in results.groupby("source_id", sort=True):
        p = plan[plan["source_id"].eq(source_id)]
        parse_ready = pd.to_numeric(group.get("parse_ready", 0), errors="coerce").fillna(0)
        hash_ready = pd.to_numeric(group.get("hash_ready", 0), errors="coerce").fillna(0)
        hit_all = pd.to_numeric(group.get("needed_symbol_hit_all", 0), errors="coerce").fillna(0)
        rows.append(
            {
                "source_id": source_id,
                "exchange": str(group["exchange"].iloc[0]),
                "planned_count": int(len(p)),
                "result_count": int(len(group)),
                "hash_count": int(hash_ready.sum()),
                "parsed_count": int(parse_ready.sum()),
                "needed_hit_all_count": int(hit_all.sum()),
                "http_error_count": int(group["status"].eq("http_error").sum()),
                "parse_fail_count": int(group["status"].eq("http_ok_parse_failed").sum()),
                "network_error_count": int(group["status"].eq("network_error").sum()),
                "full_raw_download_done": int(len(group) == len(p) and int(hash_ready.sum()) == len(p)),
                "full_raw_parse_done": int(len(group) == len(p) and int(parse_ready.sum()) == len(p)),
            }
        )
    return pd.DataFrame(rows).sort_values(["source_id"])


def _schema_summary(results: pd.DataFrame) -> pd.DataFrame:
    parsed = results[results["parse_ready"].eq(1)].copy()
    if parsed.empty:
        return pd.DataFrame()
    parsed["schema_hash"] = parsed["schema_hash"].fillna("").astype(str)
    grouped = (
        parsed.groupby(["source_id", "schema_hash"], as_index=False)
        .agg(
            row_count=("target_date", "count"),
            first_target_date=("target_date", "min"),
            last_target_date=("target_date", "max"),
            median_content_bytes=("content_bytes", "median"),
            sample_columns=("schema_columns", "first"),
        )
        .sort_values(["source_id", "row_count"], ascending=[True, False])
    )
    return grouped


def _summary(
    curve: pd.DataFrame,
    plan: pd.DataFrame,
    results: pd.DataFrame,
    source_summary: pd.DataFrame,
    product_year: pd.DataFrame,
) -> pd.DataFrame:
    metrics = _official_metrics(curve)
    result_count = int(len(results))
    planned_count = int(len(plan))
    parsed_count = int(pd.to_numeric(results.get("parse_ready", 0), errors="coerce").fillna(0).sum())
    hash_count = int(pd.to_numeric(results.get("hash_ready", 0), errors="coerce").fillna(0).sum())
    hit_all = int(pd.to_numeric(results.get("needed_symbol_hit_all", 0), errors="coerce").fillna(0).sum())
    product_year_all_hit = int(product_year["all_dates_hit"].sum()) if not product_year.empty else 0
    product_year_count = int(len(product_year))
    parse_done = int(parsed_count == planned_count and result_count == planned_count)
    download_done = int(hash_count == planned_count and result_count == planned_count)
    if parse_done and hit_all == planned_count:
        decision = "stage091_full_raw_backfill_all_parsed_all_product_hits_no_rule"
    elif parse_done:
        decision = "stage091_full_raw_backfill_all_parsed_product_timing_gaps_no_rule"
    else:
        decision = "stage091_full_raw_backfill_has_download_or_parse_gaps_no_rule"
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
                "request_timeout_seconds": REQUEST_TIMEOUT,
                "request_retries": REQUEST_RETRIES,
                "request_sleep_seconds": REQUEST_SLEEP_SECONDS,
                "planned_raw_date_count": planned_count,
                "result_count": result_count,
                "hash_count": hash_count,
                "parsed_count": parsed_count,
                "needed_symbol_hit_all_count": hit_all,
                "source_count": int(plan["source_id"].nunique()),
                "product_count": int(
                    len(
                        sorted(
                            {
                                item
                                for text in plan["needed_products"].fillna("").astype(str)
                                for item in text.split("|")
                                if item
                            }
                        )
                    )
                ),
                "year_count": int(plan["target_year"].nunique()),
                "source_full_download_done_count": int(source_summary["full_raw_download_done"].sum()) if not source_summary.empty else 0,
                "source_full_parse_done_count": int(source_summary["full_raw_parse_done"].sum()) if not source_summary.empty else 0,
                "product_year_count": product_year_count,
                "product_year_all_hit_count": product_year_all_hit,
                "http_error_count": int(results["status"].eq("http_error").sum()) if not results.empty else 0,
                "parse_fail_count": int(results["status"].eq("http_ok_parse_failed").sum()) if not results.empty else 0,
                "network_error_count": int(results["status"].eq("network_error").sum()) if not results.empty else 0,
                "full_raw_download_done": download_done,
                "full_raw_parse_done": parse_done,
                **metrics,
            }
        ]
    )


def _plot_official_path(curve: pd.DataFrame, plan: pd.DataFrame, source_year: pd.DataFrame, summary: pd.Series) -> None:
    planned = plan.pivot_table(index="target_year", columns="source_id", values="target_date", aggfunc="count").fillna(0.0)
    parsed = source_year.pivot_table(index="target_year", columns="source_id", values="parsed_count", aggfunc="sum").fillna(0.0)
    fig, axes = plt.subplots(4, 1, figsize=(14, 10), gridspec_kw={"height_ratios": [2.0, 1.1, 1.1, 1.3]})
    axes[0].plot(curve["date"], curve["account_equity"], color="#0f766e", linewidth=1.5)
    axes[0].set_title("Stage091 official path and full raw backfill")
    axes[0].set_ylabel("equity")
    axes[0].grid(True, alpha=0.25)
    axes[1].plot(curve["date"], curve["drawdown_pct"], color="#dc2626", linewidth=1.2)
    axes[1].set_ylabel("drawdown %")
    axes[1].grid(True, alpha=0.25)
    axes[2].plot(curve["date"], curve["broker10_margin_to_equity_pct"], color="#7c3aed", linewidth=1.2)
    axes[2].axhline(100, color="#111827", linestyle="--", linewidth=0.8)
    axes[2].set_ylabel("broker10 %")
    axes[2].grid(True, alpha=0.25)
    x = np.arange(len(planned.index))
    width = 0.25
    colors = ["#2563eb", "#f97316", "#16a34a"]
    for idx, column in enumerate(planned.columns):
        pos = x + (idx - 1) * width
        axes[3].bar(pos, planned[column], width=width, color=colors[idx % len(colors)], alpha=0.35, label=f"{column} planned")
        axes[3].scatter(pos, parsed[column].reindex(planned.index).fillna(0), color="#111827", s=18)
    axes[3].set_xticks(x)
    axes[3].set_xticklabels(planned.index.astype(str).tolist())
    axes[3].set_ylabel("raw dates")
    axes[3].set_title("Planned raw dates by source-year; black dots=parsed raw dates")
    axes[3].grid(True, axis="y", alpha=0.25)
    axes[3].legend(loc="upper left", fontsize=8)
    fig.suptitle(
        f"Decision={summary['decision']} | parsed {int(summary['parsed_count'])}/{int(summary['planned_raw_date_count'])}; "
        f"product-year all-hit {int(summary['product_year_all_hit_count'])}/{int(summary['product_year_count'])}",
        y=0.995,
        fontsize=12,
    )
    fig.tight_layout()
    fig.savefig(OFFICIAL_PATH_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_source_year_heatmap(source_year: pd.DataFrame) -> None:
    if source_year.empty:
        return
    pivot_planned = source_year.pivot_table(index="source_id", columns="target_year", values="planned_count", aggfunc="sum").fillna(0.0)
    pivot_parsed = source_year.pivot_table(index="source_id", columns="target_year", values="parsed_count", aggfunc="sum").fillna(0.0)
    ratio = pivot_parsed / pivot_planned.replace(0, np.nan)
    fig, ax = plt.subplots(figsize=(11, 4.5))
    im = ax.imshow(ratio.fillna(-1).to_numpy(dtype=float), aspect="auto", cmap="YlGnBu", vmin=0, vmax=1)
    ax.set_xticks(np.arange(len(ratio.columns)))
    ax.set_xticklabels(ratio.columns.astype(str).tolist())
    ax.set_yticks(np.arange(len(ratio.index)))
    ax.set_yticklabels(ratio.index.tolist())
    for i in range(ratio.shape[0]):
        for j in range(ratio.shape[1]):
            planned = int(pivot_planned.iloc[i, j])
            parsed = int(pivot_parsed.iloc[i, j])
            label = "-" if planned == 0 else f"{parsed}/{planned}"
            ax.text(j, i, label, ha="center", va="center", fontsize=9)
    ax.set_title("Stage091 parsed/planned raw dates by source-year")
    fig.colorbar(im, ax=ax, fraction=0.025, pad=0.02)
    fig.tight_layout()
    fig.savefig(SOURCE_YEAR_HEATMAP_OUT, dpi=160)
    plt.close(fig)


def _plot_product_year_heatmap(product_year: pd.DataFrame) -> None:
    if product_year.empty:
        return
    frame = product_year.copy()
    frame["row_label"] = frame["source_id"].astype(str) + ":" + frame["product_root"].astype(str)
    pivot = frame.pivot_table(index="row_label", columns="target_year", values="hit_ratio", aggfunc="min")
    data = pivot.fillna(-1.0)
    cmap = ListedColormap(["#e5e7eb", "#b91c1c", "#facc15", "#047857"])
    norm = BoundaryNorm([-1.5, -0.5, 0.00001, 0.99999, 1.5], cmap.N)
    fig, ax = plt.subplots(figsize=(11, max(4, 0.35 * len(pivot.index))))
    im = ax.imshow(data.to_numpy(dtype=float), aspect="auto", cmap=cmap, norm=norm)
    ax.set_xticks(np.arange(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns.astype(str).tolist())
    ax.set_yticks(np.arange(len(pivot.index)))
    ax.set_yticklabels(pivot.index.tolist(), fontsize=8)
    for i in range(pivot.shape[0]):
        for j in range(pivot.shape[1]):
            value = data.iloc[i, j]
            if value < 0:
                label = "-"
            else:
                planned = int(
                    frame[
                        frame["row_label"].eq(pivot.index[i]) & frame["target_year"].eq(pivot.columns[j])
                    ]["planned_date_count"].sum()
                )
                hit = int(
                    frame[
                        frame["row_label"].eq(pivot.index[i]) & frame["target_year"].eq(pivot.columns[j])
                    ]["hit_date_count"].sum()
                )
                label = f"{hit}/{planned}"
            ax.text(j, i, label, ha="center", va="center", fontsize=8)
    ax.set_title("Stage091 product hit dates / planned dates; gray=n/a, red=0, yellow=partial, green=all")
    cbar = fig.colorbar(im, ax=ax, fraction=0.025, pad=0.02, ticks=[-1, 0, 0.5, 1])
    cbar.ax.set_yticklabels(["n/a", "0", "partial", "all"])
    fig.tight_layout()
    fig.savefig(PRODUCT_YEAR_HEATMAP_OUT, dpi=160)
    plt.close(fig)


def _plot_schema_bytes(source_year: pd.DataFrame, schema_summary: pd.DataFrame) -> None:
    if source_year.empty:
        return
    bytes_pivot = source_year.pivot_table(index="source_id", columns="target_year", values="median_content_bytes", aggfunc="median").fillna(0.0)
    schema_counts = schema_summary.groupby("source_id")["schema_hash"].nunique().sort_index() if not schema_summary.empty else pd.Series(dtype=float)
    fig, axes = plt.subplots(2, 1, figsize=(11, 6), gridspec_kw={"height_ratios": [2.0, 1.0]})
    im = axes[0].imshow(bytes_pivot.to_numpy(dtype=float), aspect="auto", cmap="YlOrBr")
    axes[0].set_xticks(np.arange(len(bytes_pivot.columns)))
    axes[0].set_xticklabels(bytes_pivot.columns.astype(str).tolist())
    axes[0].set_yticks(np.arange(len(bytes_pivot.index)))
    axes[0].set_yticklabels(bytes_pivot.index.tolist())
    for i in range(bytes_pivot.shape[0]):
        for j in range(bytes_pivot.shape[1]):
            axes[0].text(j, i, f"{int(bytes_pivot.iloc[i, j] / 1000)}k", ha="center", va="center", fontsize=8)
    axes[0].set_title("Median raw bytes by source-year")
    fig.colorbar(im, ax=axes[0], fraction=0.025, pad=0.02)
    if not schema_counts.empty:
        axes[1].bar(schema_counts.index.tolist(), schema_counts.values, color="#2563eb", alpha=0.75)
    axes[1].set_ylabel("schema count")
    axes[1].grid(True, axis="y", alpha=0.25)
    axes[1].set_title("Distinct schema hashes by source")
    fig.tight_layout()
    fig.savefig(SCHEMA_BYTES_CHART_OUT, dpi=160)
    plt.close(fig)


def _write_report(
    summary: pd.DataFrame,
    source_summary: pd.DataFrame,
    source_year: pd.DataFrame,
    product_year: pd.DataFrame,
    schema_summary: pd.DataFrame,
    failures: pd.DataFrame,
) -> None:
    row = summary.iloc[0]
    report = "\n".join(
        [
            f"# {STAGE} preentry window raw full backfill",
            "",
            "## Decision",
            "",
            f"- decision: `{row['decision']}`",
            "- nature: fixed Stage090 source/date full raw download and coverage audit; no strategy rule, no true engine, no A/B, no CTP, no order API.",
            "",
            "## Baseline path",
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
            "## Backfill summary",
            "",
            f"- planned raw dates: `{int(row['planned_raw_date_count'])}`",
            f"- results/hash/parsed: `{int(row['result_count'])}` / `{int(row['hash_count'])}` / `{int(row['parsed_count'])}`",
            f"- needed-symbol-all-hit: `{int(row['needed_symbol_hit_all_count'])}`",
            f"- source full download/parse done: `{int(row['source_full_download_done_count'])}` / `{int(row['source_full_parse_done_count'])}`",
            f"- product-year all-hit: `{int(row['product_year_all_hit_count'])}` / `{int(row['product_year_count'])}`",
            f"- http/parse/network errors: `{int(row['http_error_count'])}` / `{int(row['parse_fail_count'])}` / `{int(row['network_error_count'])}`",
            f"- full raw download done: `{int(row['full_raw_download_done'])}`",
            f"- full raw parse done: `{int(row['full_raw_parse_done'])}`",
            "",
            "## Source summary",
            "",
            _md_table(source_summary, max_rows=20),
            "",
            "## Source-year summary",
            "",
            _md_table(source_year, max_rows=80),
            "",
            "## Product-year coverage gaps",
            "",
            _md_table(product_year[product_year["all_dates_hit"].eq(0)].copy(), max_rows=80) if not product_year.empty else "_empty_",
            "",
            "## Schema summary",
            "",
            _md_table(schema_summary, max_rows=30),
            "",
            "## Failure rows",
            "",
            _md_table(failures, max_rows=80),
            "",
            "## Visual outputs",
            "",
            f"- official path backfill chart: `{OFFICIAL_PATH_CHART_OUT}`",
            f"- source-year parse heatmap: `{SOURCE_YEAR_HEATMAP_OUT}`",
            f"- product-year hit heatmap: `{PRODUCT_YEAR_HEATMAP_OUT}`",
            f"- schema bytes chart: `{SCHEMA_BYTES_CHART_OUT}`",
            "",
            "## External sources used",
            "",
            "- AKShare changelog and futures docs were used only to confirm wrapper instability and source names.",
            "- CZCE and GFEX official public endpoints were used for raw response provenance.",
            "",
            "## Judgment",
            "",
            "- This stage can prove raw coverage and product timing gaps, but still cannot produce a trading rule.",
            "- Product hit/miss, source ready/missing, schema hash, content bytes, and download status are coverage labels only.",
            "- Point-in-time feature binding must wait until coverage gaps and right-tail safety are audited.",
        ]
    )
    REPORT_OUT.write_text(report + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    curve = _load_official_curve()
    plan = _load_plan()
    results = _run_backfill(plan)
    source_year = _source_year_summary(plan, results)
    product_year = _product_year_coverage(plan, results)
    source_summary = _source_summary(results, plan)
    schema_summary = _schema_summary(results)
    failures = results[~results["status"].eq("parsed_ok")].copy()
    product_misses = product_year[product_year["all_dates_hit"].eq(0)].copy() if not product_year.empty else pd.DataFrame()
    summary = _summary(curve, plan, results, source_summary, product_year)

    _write_csv(results, RESULTS_OUT)
    _write_csv(source_year, SOURCE_YEAR_OUT)
    _write_csv(product_year, PRODUCT_YEAR_OUT)
    _write_csv(source_summary, SOURCE_SUMMARY_OUT)
    _write_csv(schema_summary, SCHEMA_SUMMARY_OUT)
    _write_csv(failures, FAILURE_OUT)
    _write_csv(summary, SUMMARY_OUT)
    DECISION_OUT.write_text(
        json.dumps(_json_safe(summary.iloc[0].to_dict()), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    _plot_official_path(curve, plan, source_year, summary.iloc[0])
    _plot_source_year_heatmap(source_year)
    _plot_product_year_heatmap(product_year)
    _plot_schema_bytes(source_year, schema_summary)
    _write_report(summary, source_summary, source_year, product_year, schema_summary, failures)

    print(json.dumps(_json_safe(summary.iloc[0].to_dict()), ensure_ascii=False, indent=2))
    if not product_misses.empty:
        print("product_year_misses")
        print(product_misses.to_string(index=False, max_rows=80))


if __name__ == "__main__":
    main()
