from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any
import zipfile
from io import BytesIO

import matplotlib

matplotlib.use("Agg")
from matplotlib.colors import BoundaryNorm, ListedColormap
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import requests
import urllib3


LINE_ID = "futures_trend_c9_minrisk_highquality"
STAGE = "Stage090"
MODEL_TAG = "stage090_preentry_window_raw_manifest_design_v1"
OUTPUT_PREFIX = "qmt_roll_stage090_c9_minrisk_preentry_window_raw_manifest_design"
ACCOUNT_CAPITAL = 150_000.0
LOOKBACK_TRADING_DAYS = 7
REQUEST_TIMEOUT = 10

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
EXAMPLE_DIR = REPO_DIR / "examples" / "portfolio_backtesting"
if str(EXAMPLE_DIR) not in sys.path:
    sys.path.insert(0, str(EXAMPLE_DIR))

from qmt_roll_official_live_config import OFFICIAL_LIVE_ALIAS, OFFICIAL_LIVE_VERSION
from stage089_external_raw_backfill_manifest_probe import (
    HEADERS,
    OFFICIAL_CLOSED_LOTS_IN,
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
OUTPUT_DIR = LINE_DIR / "outputs" / "stage090_preentry_window_raw_manifest_design"
RAW_DIR = OUTPUT_DIR / "raw"

PLAN_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_planned_raw_manifest_{MODEL_TAG}.csv"
LINKS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_lot_window_links_{MODEL_TAG}.csv"
PROBE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_probe_results_{MODEL_TAG}.csv"
SOURCE_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_source_summary_{MODEL_TAG}.csv"
PRODUCT_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_summary_{MODEL_TAG}.csv"
SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

OFFICIAL_PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_manifest_chart_{MODEL_TAG}.png"
PLAN_HEATMAP_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_planned_source_year_heatmap_{MODEL_TAG}.png"
PROBE_HEATMAP_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_probe_status_heatmap_{MODEL_TAG}.png"
PRODUCT_HIT_HEATMAP_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_probe_product_hit_heatmap_{MODEL_TAG}.png"

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

ALLOWED_SOURCES_BY_EXCHANGE = {
    "CZCE": ["czce_member_rank", "czce_warehouse"],
    "GFEX": ["gfex_warehouse"],
}


def _exchange_from_vt_symbol(vt_symbol: str) -> str:
    text = str(vt_symbol)
    return text.split(".")[-1].upper() if "." in text else "UNKNOWN"


def _root_from_vt_symbol(vt_symbol: str) -> str:
    match = re.match(r"([A-Za-z]+)", str(vt_symbol))
    return match.group(1).upper() if match else str(vt_symbol).upper()


def _load_relevant_lots() -> pd.DataFrame:
    lots = _read_csv(OFFICIAL_CLOSED_LOTS_IN)
    lots["entry_date"] = pd.to_datetime(lots["entry_date"], errors="coerce").dt.normalize()
    lots = lots.dropna(subset=["entry_date"]).copy()
    lots["exchange_norm"] = lots["vt_symbol"].map(_exchange_from_vt_symbol)
    lots["product_root"] = lots["vt_symbol"].map(_root_from_vt_symbol)
    lots["realized_pnl"] = pd.to_numeric(lots.get("realized_pnl", 0.0), errors="coerce").fillna(0.0)
    lots = lots[lots["exchange_norm"].isin(ALLOWED_SOURCES_BY_EXCHANGE)].copy()
    return lots.sort_values(["entry_date", "lot_id"]).reset_index(drop=True)


def _previous_trading_dates(calendar: pd.Series, entry_date: pd.Timestamp) -> list[pd.Timestamp]:
    prior = calendar[calendar < entry_date].tail(LOOKBACK_TRADING_DAYS)
    return [pd.Timestamp(date).normalize() for date in prior.tolist()]


def _build_lot_window_links(lots: pd.DataFrame, curve: pd.DataFrame) -> pd.DataFrame:
    calendar = pd.to_datetime(curve["date"], errors="coerce").dropna().sort_values().drop_duplicates().reset_index(drop=True)
    rows: list[dict[str, Any]] = []
    for lot in lots.itertuples(index=False):
        entry_date = pd.Timestamp(lot.entry_date).normalize()
        prior_dates = _previous_trading_dates(calendar, entry_date)
        sources = ALLOWED_SOURCES_BY_EXCHANGE.get(str(lot.exchange_norm), [])
        for source_id in sources:
            for offset, target_date in enumerate(reversed(prior_dates), start=1):
                rows.append(
                    {
                        "source_id": source_id,
                        "exchange": str(lot.exchange_norm),
                        "lot_id": int(lot.lot_id),
                        "vt_symbol": str(lot.vt_symbol),
                        "product_root": str(lot.product_root),
                        "direction": str(lot.direction),
                        "entry_date": entry_date.strftime("%Y-%m-%d"),
                        "entry_year": int(entry_date.year),
                        "target_date": target_date.strftime("%Y%m%d"),
                        "target_year": int(target_date.year),
                        "preentry_trading_day_offset": offset,
                        "realized_pnl": float(lot.realized_pnl),
                    }
                )
    return pd.DataFrame(rows).sort_values(["source_id", "target_date", "product_root", "lot_id", "preentry_trading_day_offset"])


def _build_plan(links: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for (source_id, target_date), group in links.groupby(["source_id", "target_date"], sort=True):
        spec = _spec_for(source_id, str(target_date))
        products = sorted(group["product_root"].dropna().astype(str).str.upper().unique().tolist())
        vt_symbols = sorted(group["vt_symbol"].dropna().astype(str).unique().tolist())
        rows.append(
            {
                "source_id": source_id,
                "exchange": spec["exchange"],
                "target_date": str(target_date),
                "target_year": int(str(target_date)[:4]),
                "method": spec["method"],
                "url": spec["url"],
                "payload_json": json.dumps(spec.get("payload", {}), ensure_ascii=False, sort_keys=True),
                "doc_url": spec["doc_url"],
                "planned_raw_stem": f"raw/{source_id}/{source_id}_{target_date}",
                "needed_product_count": int(len(products)),
                "needed_products": "|".join(products),
                "linked_lot_count": int(group["lot_id"].nunique()),
                "linked_vt_symbol_count": int(len(vt_symbols)),
                "linked_vt_symbols": "|".join(vt_symbols[:80]),
                "linked_realized_pnl_context": float(group.drop_duplicates(["source_id", "target_date", "lot_id"])["realized_pnl"].sum()),
                "is_probe": 0,
                "probe_reason": "",
            }
        )
    return pd.DataFrame(rows).sort_values(["source_id", "target_date"]).reset_index(drop=True)


def _select_probe_keys(plan: pd.DataFrame, links: pd.DataFrame) -> set[tuple[str, str]]:
    keys: set[tuple[str, str]] = set()
    for (source_id, year), group in plan.groupby(["source_id", "target_year"], sort=True):
        chosen = group.sort_values(["linked_lot_count", "target_date"], ascending=[False, True]).iloc[0]
        keys.add((str(source_id), str(chosen["target_date"])))

    gfex_focus = links[
        links["source_id"].eq("gfex_warehouse")
        & links["product_root"].isin(["LC", "SI"])
        & links["entry_year"].eq(2023)
    ]
    for row in gfex_focus.itertuples(index=False):
        keys.add((str(row.source_id), str(row.target_date)))
    return keys


def _mark_probe_rows(plan: pd.DataFrame, links: pd.DataFrame) -> pd.DataFrame:
    probe_keys = _select_probe_keys(plan, links)
    plan = plan.copy()
    plan["is_probe"] = plan.apply(lambda row: int((str(row["source_id"]), str(row["target_date"])) in probe_keys), axis=1)
    reason_map: dict[tuple[str, str], list[str]] = {}
    for key in probe_keys:
        reason_map.setdefault(key, []).append("source_year_representative")
    gfex_focus = links[
        links["source_id"].eq("gfex_warehouse")
        & links["product_root"].isin(["LC", "SI"])
        & links["entry_year"].eq(2023)
    ]
    for row in gfex_focus.itertuples(index=False):
        reason_map.setdefault((str(row.source_id), str(row.target_date)), []).append("gfex_lc_si_2023_preentry_focus")
    plan["probe_reason"] = plan.apply(
        lambda row: "|".join(sorted(set(reason_map.get((str(row["source_id"]), str(row["target_date"])), [])))),
        axis=1,
    )
    return plan


def _parse_content(source_id: str, content: bytes) -> tuple[int, list[str], list[str], str]:
    kind = SOURCE_SPECS[source_id]["kind"]
    if kind == "czce_holding_excel":
        return _symbols_from_czce_holding(content)
    if kind == "czce_warehouse_excel":
        return _symbols_from_czce_warehouse(content)
    return _symbols_from_gfex_warehouse(content)


def _run_probe(row: pd.Series) -> dict[str, Any]:
    source_id = str(row["source_id"])
    target_date = str(row["target_date"])
    spec = _spec_for(source_id, target_date)
    out = {
        "source_id": source_id,
        "exchange": str(row["exchange"]),
        "target_date": target_date,
        "target_year": int(row["target_year"]),
        "method": str(row["method"]),
        "url": str(row["url"]),
        "payload_json": str(row["payload_json"]),
        "probe_reason": str(row["probe_reason"]),
        "needed_products": str(row["needed_products"]),
        "needed_product_count": int(row["needed_product_count"]),
        "linked_lot_count": int(row["linked_lot_count"]),
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
        "needed_symbol_hit_count": 0,
        "needed_symbol_miss_count": int(row["needed_product_count"]),
        "needed_symbol_hit_all": 0,
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
                hits = {product for product in needed if product in symbol_set or any(symbol.startswith(product) for symbol in symbol_set)}
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
    except Exception as exc:  # noqa: BLE001
        out["status"] = "network_error"
        out["error_type"] = type(exc).__name__
        out["error_message"] = str(exc)[:300]
    return out


def _source_summary(plan: pd.DataFrame, links: pd.DataFrame, probes: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for source_id, group in plan.groupby("source_id", sort=True):
        p = probes[probes["source_id"].eq(source_id)] if not probes.empty else pd.DataFrame()
        l = links[links["source_id"].eq(source_id)]
        parsed = int(pd.to_numeric(p.get("parse_ready", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()) if not p.empty else 0
        hit_all = int(pd.to_numeric(p.get("needed_symbol_hit_all", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()) if not p.empty else 0
        rows.append(
            {
                "source_id": source_id,
                "exchange": str(group["exchange"].iloc[0]),
                "planned_raw_date_count": int(len(group)),
                "planned_year_count": int(group["target_year"].nunique()),
                "planned_link_count": int(len(l)),
                "planned_unique_lot_count": int(l["lot_id"].nunique()),
                "planned_product_count": int(l["product_root"].nunique()),
                "probe_count": int(len(p)),
                "probe_parsed_count": parsed,
                "probe_needed_symbol_hit_all_count": hit_all,
                "probe_hash_count": int(pd.to_numeric(p.get("hash_ready", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()) if not p.empty else 0,
                "probe_http_error_count": int(p["status"].eq("http_error").sum()) if not p.empty else 0,
                "probe_parse_fail_count": int(p["status"].eq("http_ok_parse_failed").sum()) if not p.empty else 0,
                "preentry_manifest_ready": int(len(group) > 0 and len(p) > 0 and parsed == len(p)),
                "full_raw_download_done": 0,
            }
        )
    return pd.DataFrame(rows).sort_values(["preentry_manifest_ready", "source_id"], ascending=[False, True])


def _product_summary(links: pd.DataFrame, probes: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for (source_id, product_root), group in links.groupby(["source_id", "product_root"], sort=True):
        probe_subset = probes[
            probes["source_id"].eq(source_id)
            & probes["needed_products"].astype(str).str.split("|").apply(lambda items: product_root in items)
        ] if not probes.empty else pd.DataFrame()
        rows.append(
            {
                "source_id": source_id,
                "product_root": product_root,
                "exchange": str(group["exchange"].iloc[0]),
                "unique_lot_count": int(group["lot_id"].nunique()),
                "planned_target_date_count": int(group["target_date"].nunique()),
                "first_entry_date": str(group["entry_date"].min()),
                "last_entry_date": str(group["entry_date"].max()),
                "first_target_date": str(group["target_date"].min()),
                "last_target_date": str(group["target_date"].max()),
                "probe_row_count": int(len(probe_subset)),
                "probe_hit_all_count": int(probe_subset["needed_symbol_hit_all"].sum()) if not probe_subset.empty else 0,
            }
        )
    return pd.DataFrame(rows).sort_values(["source_id", "product_root"])


def _summary(curve: pd.DataFrame, lots: pd.DataFrame, links: pd.DataFrame, plan: pd.DataFrame, probes: pd.DataFrame, source_summary: pd.DataFrame) -> pd.DataFrame:
    metrics = _official_metrics(curve)
    probe_parsed = int(pd.to_numeric(probes["parse_ready"], errors="coerce").fillna(0).sum()) if not probes.empty else 0
    probe_hash = int(pd.to_numeric(probes["hash_ready"], errors="coerce").fillna(0).sum()) if not probes.empty else 0
    probe_hit_all = int(pd.to_numeric(probes["needed_symbol_hit_all"], errors="coerce").fillna(0).sum()) if not probes.empty else 0
    ready_sources = int(source_summary["preentry_manifest_ready"].sum()) if not source_summary.empty else 0
    decision = (
        "stage090_preentry_window_manifest_built_probe_all_parsed_no_rule"
        if probe_parsed == len(probes) and ready_sources == len(source_summary)
        else "stage090_preentry_window_manifest_probe_has_gaps_no_rule"
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
                "lookback_trading_days": LOOKBACK_TRADING_DAYS,
                "relevant_lot_count": int(lots["lot_id"].nunique()),
                "lot_window_link_count": int(len(links)),
                "planned_raw_date_count": int(len(plan)),
                "planned_source_count": int(plan["source_id"].nunique()),
                "planned_product_count": int(links["product_root"].nunique()),
                "planned_year_count": int(plan["target_year"].nunique()),
                "probe_count": int(len(probes)),
                "probe_parsed_count": probe_parsed,
                "probe_hash_count": probe_hash,
                "probe_needed_symbol_hit_all_count": probe_hit_all,
                "preentry_manifest_ready_source_count": ready_sources,
                "full_raw_download_done": 0,
                **metrics,
            }
        ]
    )


def _plot_official_path(curve: pd.DataFrame, plan: pd.DataFrame, summary: pd.Series) -> None:
    yearly = plan.pivot_table(index="target_year", columns="source_id", values="target_date", aggfunc="count").fillna(0.0)
    probes = plan[plan["is_probe"].eq(1)].pivot_table(index="target_year", columns="source_id", values="target_date", aggfunc="count").fillna(0.0)
    fig, axes = plt.subplots(4, 1, figsize=(14, 10), gridspec_kw={"height_ratios": [2.0, 1.1, 1.1, 1.3]})
    axes[0].plot(curve["date"], curve["account_equity"], color="#0f766e", linewidth=1.5)
    axes[0].set_title("Stage090 official path and preentry raw manifest plan")
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
        axes[3].bar(x + (idx - 1) * width, yearly[column], width=width, color=colors[idx % len(colors)], alpha=0.55, label=f"{column} planned")
        if column in probes:
            axes[3].scatter(x + (idx - 1) * width, probes[column].reindex(yearly.index).fillna(0), color="#111827", s=18)
    axes[3].set_xticks(x)
    axes[3].set_xticklabels(yearly.index.astype(str).tolist())
    axes[3].set_ylabel("planned raw dates")
    axes[3].set_title("Preentry window planned raw dates by source-year; black dots=probe counts")
    axes[3].grid(True, axis="y", alpha=0.25)
    axes[3].legend(loc="upper left", fontsize=8)
    fig.suptitle(
        f"Decision={summary['decision']} | planned raw dates {int(summary['planned_raw_date_count'])}; "
        f"probe parsed {int(summary['probe_parsed_count'])}/{int(summary['probe_count'])}",
        y=0.995,
        fontsize=12,
    )
    fig.tight_layout()
    fig.savefig(OFFICIAL_PATH_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_plan_heatmap(plan: pd.DataFrame) -> None:
    pivot = plan.pivot_table(index="source_id", columns="target_year", values="target_date", aggfunc="count").fillna(0.0)
    fig, ax = plt.subplots(figsize=(11, 4.5))
    im = ax.imshow(pivot.to_numpy(dtype=float), aspect="auto", cmap="YlGnBu")
    ax.set_xticks(np.arange(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns.astype(str).tolist())
    ax.set_yticks(np.arange(len(pivot.index)))
    ax.set_yticklabels(pivot.index.tolist())
    for i in range(pivot.shape[0]):
        for j in range(pivot.shape[1]):
            ax.text(j, i, str(int(pivot.iloc[i, j])), ha="center", va="center", fontsize=9)
    ax.set_title("Stage090 planned preentry raw manifest date count by source-year")
    fig.colorbar(im, ax=ax, fraction=0.025, pad=0.02)
    fig.tight_layout()
    fig.savefig(PLAN_HEATMAP_OUT, dpi=160)
    plt.close(fig)


def _plot_probe_heatmap(probes: pd.DataFrame) -> None:
    if probes.empty:
        return
    pivot = probes.pivot_table(index="source_id", columns="target_year", values="parse_ready", aggfunc="sum").fillna(0.0)
    fig, ax = plt.subplots(figsize=(11, 4.5))
    im = ax.imshow(pivot.to_numpy(dtype=float), aspect="auto", cmap="YlGnBu")
    ax.set_xticks(np.arange(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns.astype(str).tolist())
    ax.set_yticks(np.arange(len(pivot.index)))
    ax.set_yticklabels(pivot.index.tolist())
    for i in range(pivot.shape[0]):
        for j in range(pivot.shape[1]):
            ax.text(j, i, str(int(pivot.iloc[i, j])), ha="center", va="center", fontsize=9)
    ax.set_title("Stage090 probe parsed count by source-year")
    fig.colorbar(im, ax=ax, fraction=0.025, pad=0.02)
    fig.tight_layout()
    fig.savefig(PROBE_HEATMAP_OUT, dpi=160)
    plt.close(fig)


def _plot_product_hit_heatmap(probes: pd.DataFrame) -> None:
    if probes.empty:
        return
    rows: list[dict[str, Any]] = []
    for row in probes.itertuples(index=False):
        needed = [item for item in str(row.needed_products).split("|") if item]
        symbols = {symbol.upper() for symbol in str(row.sample_symbols).split("|") if symbol}
        for product in needed:
            hit = int(product.upper() in symbols or any(symbol.startswith(product.upper()) for symbol in symbols))
            rows.append({"row_label": f"{row.source_id}:{product}", "target_year": int(row.target_year), "hit": hit})
    frame = pd.DataFrame(rows)
    if frame.empty:
        return
    pivot = frame.pivot_table(index="row_label", columns="target_year", values="hit", aggfunc="max")
    data = pivot.fillna(-1.0)
    cmap = ListedColormap(["#e5e7eb", "#b91c1c", "#047857"])
    norm = BoundaryNorm([-1.5, -0.5, 0.5, 1.5], cmap.N)
    fig, ax = plt.subplots(figsize=(11, max(4, 0.35 * len(pivot.index))))
    im = ax.imshow(data.to_numpy(dtype=float), aspect="auto", cmap=cmap, norm=norm)
    ax.set_xticks(np.arange(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns.astype(str).tolist())
    ax.set_yticks(np.arange(len(pivot.index)))
    ax.set_yticklabels(pivot.index.tolist(), fontsize=8)
    for i in range(pivot.shape[0]):
        for j in range(pivot.shape[1]):
            value = data.iloc[i, j]
            ax.text(j, i, "-" if value < 0 else str(int(value)), ha="center", va="center", fontsize=8)
    ax.set_title("Stage090 probe needed-product symbol hit; gray=not probed")
    cbar = fig.colorbar(im, ax=ax, fraction=0.025, pad=0.02, ticks=[-1, 0, 1])
    cbar.ax.set_yticklabels(["n/a", "miss", "hit"])
    fig.tight_layout()
    fig.savefig(PRODUCT_HIT_HEATMAP_OUT, dpi=160)
    plt.close(fig)


def _write_report(summary: pd.DataFrame, source_summary: pd.DataFrame, product_summary: pd.DataFrame, plan: pd.DataFrame, probes: pd.DataFrame) -> None:
    row = summary.iloc[0]
    report = "\n".join(
        [
            f"# {STAGE} preentry window raw manifest design",
            "",
            "## Decision",
            "",
            f"- decision: `{row['decision']}`",
            "- nature: C9 preentry-window raw manifest design and limited probe; no strategy rule, no true engine, no A/B, no CTP, no order API.",
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
            "## Manifest summary",
            "",
            f"- lookback trading days: `{int(row['lookback_trading_days'])}`",
            f"- relevant lots: `{int(row['relevant_lot_count'])}`",
            f"- lot-window links: `{int(row['lot_window_link_count'])}`",
            f"- planned raw dates: `{int(row['planned_raw_date_count'])}`",
            f"- planned sources/products/years: `{int(row['planned_source_count'])}` / `{int(row['planned_product_count'])}` / `{int(row['planned_year_count'])}`",
            f"- probes: `{int(row['probe_count'])}`, parsed `{int(row['probe_parsed_count'])}`, hashed `{int(row['probe_hash_count'])}`, needed-symbol-all-hit `{int(row['probe_needed_symbol_hit_all_count'])}`",
            f"- full raw download done: `{int(row['full_raw_download_done'])}`",
            "",
            "## Source summary",
            "",
            _md_table(source_summary, max_rows=20),
            "",
            "## Product summary",
            "",
            _md_table(product_summary, max_rows=40),
            "",
            "## Probe sample",
            "",
            _md_table(
                probes[
                    [
                        "source_id",
                        "target_date",
                        "probe_reason",
                        "status",
                        "parse_ready",
                        "needed_products",
                        "needed_symbol_hit_count",
                        "needed_symbol_miss_count",
                        "raw_file",
                    ]
                ],
                max_rows=60,
            ),
            "",
            "## Plan sample",
            "",
            _md_table(
                plan[
                    [
                        "source_id",
                        "target_date",
                        "needed_products",
                        "linked_lot_count",
                        "is_probe",
                        "probe_reason",
                        "url",
                        "payload_json",
                    ]
                ],
                max_rows=60,
            ),
            "",
            "## Visual outputs",
            "",
            f"- official path manifest chart: `{OFFICIAL_PATH_CHART_OUT}`",
            f"- planned source-year heatmap: `{PLAN_HEATMAP_OUT}`",
            f"- probe status heatmap: `{PROBE_HEATMAP_OUT}`",
            f"- probe product hit heatmap: `{PRODUCT_HIT_HEATMAP_OUT}`",
            "",
            "## External sources used",
            "",
            "- AKShare changelog confirms CZCE wrapper renames; Stage090 therefore stores raw URL/payload/hash instead of trusting wrapper outputs.",
            "- CZCE and GFEX official public endpoints are used only for raw probe and manifest engineering.",
            "",
            "## Judgment",
            "",
            "- This stage makes the preentry external-data plan more concrete, but it is still not a trading rule.",
            "- Planned rows are not downloaded full-history raw data; full_raw_download_done remains 0.",
            "- Source, date, product hit, and missing status cannot be used for true engine or A/B before full point-in-time coverage and right-tail safety pass.",
        ]
    )
    REPORT_OUT.write_text(report + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    curve = _load_official_curve()
    lots = _load_relevant_lots()
    links = _build_lot_window_links(lots, curve)
    plan = _build_plan(links)
    plan = _mark_probe_rows(plan, links)
    probes = pd.DataFrame([_run_probe(row) for _, row in plan[plan["is_probe"].eq(1)].iterrows()])
    source_summary = _source_summary(plan, links, probes)
    product_summary = _product_summary(links, probes)
    summary = _summary(curve, lots, links, plan, probes, source_summary)

    _write_csv(plan, PLAN_OUT)
    _write_csv(links, LINKS_OUT)
    _write_csv(probes, PROBE_OUT)
    _write_csv(source_summary, SOURCE_SUMMARY_OUT)
    _write_csv(product_summary, PRODUCT_SUMMARY_OUT)
    _write_csv(summary, SUMMARY_OUT)
    DECISION_OUT.write_text(
        json.dumps(_json_safe(summary.iloc[0].to_dict()), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    _plot_official_path(curve, plan, summary.iloc[0])
    _plot_plan_heatmap(plan)
    _plot_probe_heatmap(probes)
    _plot_product_hit_heatmap(probes)
    _write_report(summary, source_summary, product_summary, plan, probes)

    print(json.dumps(_json_safe(summary.iloc[0].to_dict()), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
