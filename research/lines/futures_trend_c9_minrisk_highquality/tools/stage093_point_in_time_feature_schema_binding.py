from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import sys
from typing import Any

import matplotlib

matplotlib.use("Agg")
from matplotlib.colors import BoundaryNorm, ListedColormap
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


LINE_ID = "futures_trend_c9_minrisk_highquality"
STAGE = "Stage093"
MODEL_TAG = "stage093_point_in_time_feature_schema_binding_v1"
OUTPUT_PREFIX = "qmt_roll_stage093_c9_minrisk_point_in_time_feature_schema_binding"
FEATURE_SCHEMA_VERSION = "external_raw_state_schema_v1"
ACCOUNT_CAPITAL = 150_000.0

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
EXAMPLE_DIR = REPO_DIR / "examples" / "portfolio_backtesting"
if str(EXAMPLE_DIR) not in sys.path:
    sys.path.insert(0, str(EXAMPLE_DIR))

from qmt_roll_official_live_config import OFFICIAL_LIVE_ALIAS, OFFICIAL_LIVE_VERSION
from stage089_external_raw_backfill_manifest_probe import (
    OFFICIAL_CLOSED_LOTS_IN,
    _json_safe,
    _load_official_curve,
    _md_table,
    _official_metrics,
    _read_csv,
    _write_csv,
)


LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
STAGE090_DIR = LINE_DIR / "outputs" / "stage090_preentry_window_raw_manifest_design"
STAGE091_DIR = LINE_DIR / "outputs" / "stage091_preentry_window_raw_full_backfill"
STAGE092_DIR = LINE_DIR / "outputs" / "stage092_product_timing_gap_right_tail_audit"
OUTPUT_DIR = LINE_DIR / "outputs" / "stage093_point_in_time_feature_schema_binding"

LINKS_IN = (
    STAGE090_DIR
    / "qmt_roll_stage090_c9_minrisk_preentry_window_raw_manifest_design_lot_window_links_"
    "stage090_preentry_window_raw_manifest_design_v1.csv"
)
RESULTS_IN = (
    STAGE091_DIR
    / "qmt_roll_stage091_c9_minrisk_preentry_window_raw_full_backfill_backfill_results_"
    "stage091_preentry_window_raw_full_backfill_v1.csv"
)
PRODUCT_STATUS_IN = (
    STAGE092_DIR
    / "qmt_roll_stage092_c9_minrisk_product_timing_gap_right_tail_audit_product_date_status_"
    "stage092_product_timing_gap_right_tail_audit_v1.csv"
)

FEATURE_ROWS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_feature_rows_{MODEL_TAG}.csv"
LOT_SOURCE_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_lot_source_summary_{MODEL_TAG}.csv"
LOT_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_lot_summary_{MODEL_TAG}.csv"
SOURCE_STATE_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_source_state_summary_{MODEL_TAG}.csv"
SCHEMA_FIELD_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_schema_fields_{MODEL_TAG}.csv"
SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

OFFICIAL_FEATURE_PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_feature_path_chart_{MODEL_TAG}.png"
SOURCE_STATE_HEATMAP_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_source_state_heatmap_{MODEL_TAG}.png"
LOT_COVERAGE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_lot_coverage_chart_{MODEL_TAG}.png"
SCHEMA_FIELD_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_schema_field_chart_{MODEL_TAG}.png"


def _target_date(value: Any) -> str:
    text = str(value).strip()
    if text.endswith(".0"):
        text = text[:-2]
    return text.zfill(8)


def _source_family(source_id: str) -> str:
    if source_id.endswith("member_rank"):
        return "member_rank"
    if source_id.endswith("warehouse"):
        return "warehouse"
    return "unknown"


def _load_links() -> pd.DataFrame:
    links = _read_csv(LINKS_IN)
    links["target_date"] = links["target_date"].map(_target_date)
    links["entry_date"] = pd.to_datetime(links["entry_date"], errors="coerce").dt.normalize()
    links["target_date_dt"] = pd.to_datetime(links["target_date"], format="%Y%m%d", errors="coerce")
    links["realized_pnl"] = pd.to_numeric(links.get("realized_pnl", 0.0), errors="coerce").fillna(0.0)
    return links


def _load_results() -> pd.DataFrame:
    results = _read_csv(RESULTS_IN)
    results["target_date"] = results["target_date"].map(_target_date)
    keep = [
        "source_id",
        "target_date",
        "status",
        "http_status",
        "content_bytes",
        "hash_ready",
        "parse_ready",
        "row_count",
        "symbol_count",
        "schema_hash",
        "raw_file",
        "sha256",
    ]
    results = results[[col for col in keep if col in results.columns]].copy()
    for column in ["http_status", "content_bytes", "hash_ready", "parse_ready", "row_count", "symbol_count"]:
        results[column] = pd.to_numeric(results.get(column, 0), errors="coerce").fillna(0)
    return results


def _load_product_status() -> pd.DataFrame:
    status = _read_csv(PRODUCT_STATUS_IN)
    status["target_date"] = status["target_date"].map(_target_date)
    status["target_date_dt"] = pd.to_datetime(status["target_date"], format="%Y%m%d", errors="coerce")
    status["first_present_date"] = status["first_present_date"].fillna("").astype(str).map(
        lambda value: "" if value in {"", "nan", "NaT"} else _target_date(value)
    )
    status["first_present_date_dt"] = pd.to_datetime(status["first_present_date"], format="%Y%m%d", errors="coerce")
    status["last_present_date"] = status["last_present_date"].fillna("").astype(str).map(
        lambda value: "" if value in {"", "nan", "NaT"} else _target_date(value)
    )
    status["hit"] = pd.to_numeric(status.get("hit", 0), errors="coerce").fillna(0).astype(int)
    status["parse_ready"] = pd.to_numeric(status.get("parse_ready", 0), errors="coerce").fillna(0).astype(int)
    return status


def _load_lots() -> pd.DataFrame:
    lots = _read_csv(OFFICIAL_CLOSED_LOTS_IN)
    lots["entry_date"] = pd.to_datetime(lots["entry_date"], errors="coerce").dt.normalize()
    lots["realized_pnl"] = pd.to_numeric(lots.get("realized_pnl", 0.0), errors="coerce").fillna(0.0)
    lots["realized_pnl_rank_pct"] = lots["realized_pnl"].rank(method="average", pct=True)
    lots["right_tail_top10"] = (lots["realized_pnl_rank_pct"] >= 0.90).astype(int)
    cols = [
        "lot_id",
        "vt_symbol",
        "direction",
        "entry_date",
        "realized_pnl",
        "r_multiple",
        "winner",
        "big_winner",
        "realized_pnl_rank_pct",
        "right_tail_top10",
    ]
    return lots[[col for col in cols if col in lots.columns]].copy()


def _build_feature_rows(links: pd.DataFrame, results: pd.DataFrame, product_status: pd.DataFrame, lots: pd.DataFrame) -> pd.DataFrame:
    rows = links.merge(
        product_status[
            [
                "source_id",
                "exchange",
                "product_root",
                "target_date",
                "hit",
                "coverage_class",
                "first_present_date",
                "first_present_date_dt",
                "last_present_date",
            ]
        ],
        on=["source_id", "exchange", "product_root", "target_date"],
        how="left",
    )
    rows = rows.merge(results, on=["source_id", "target_date"], how="left")
    rows = rows.merge(lots, on=["lot_id", "vt_symbol", "direction", "entry_date", "realized_pnl"], how="left")
    rows["feature_schema_version"] = FEATURE_SCHEMA_VERSION
    rows["source_family"] = rows["source_id"].map(_source_family)
    rows["raw_hash_ready"] = pd.to_numeric(rows.get("hash_ready", 0), errors="coerce").fillna(0).astype(int)
    rows["raw_parse_ready"] = pd.to_numeric(rows.get("parse_ready", 0), errors="coerce").fillna(0).astype(int)
    rows["source_ready"] = ((rows["raw_hash_ready"].eq(1)) & (rows["raw_parse_ready"].eq(1))).astype(int)
    rows["symbol_hit"] = pd.to_numeric(rows.get("hit", 0), errors="coerce").fillna(0).astype(int)
    rows["product_present_state"] = rows["coverage_class"].fillna("missing_product_status").astype(str)
    rows["first_present_known"] = rows["first_present_date"].fillna("").astype(str).ne("").astype(int)
    rows["target_minus_first_present_calendar_days"] = (
        rows["target_date_dt"] - rows["first_present_date_dt"]
    ).dt.days
    rows["target_minus_first_present_calendar_days"] = rows["target_minus_first_present_calendar_days"].fillna(-99999).astype(int)
    rows["target_before_first_present"] = (rows["target_minus_first_present_calendar_days"] < 0).astype(int)
    rows["entry_minus_target_calendar_days"] = (rows["entry_date"] - rows["target_date_dt"]).dt.days.fillna(-1).astype(int)
    rows["state_feature_ready"] = (
        rows["source_ready"].eq(1)
        & rows["product_present_state"].isin(
            [
                "present",
                "official_absent_before_first_manifest_presence",
                "official_absent_no_present_in_manifest",
                "official_absent_after_prior_presence",
            ]
        )
    ).astype(int)
    rows["quantity_feature_ready"] = 0
    rows["member_rank_numeric_feature_ready"] = 0
    rows["warehouse_numeric_feature_ready"] = 0
    rows["strategy_rule_allowed"] = 0
    rows["true_engine_allowed"] = 0
    rows["feature_binding_scope"] = "state_only_no_numeric_signal"
    rows["right_tail_top10"] = pd.to_numeric(rows.get("right_tail_top10", 0), errors="coerce").fillna(0).astype(int)
    rows["realized_pnl_rank_pct"] = pd.to_numeric(rows.get("realized_pnl_rank_pct", 0), errors="coerce").fillna(0.0)
    columns = [
        "feature_schema_version",
        "feature_binding_scope",
        "source_id",
        "source_family",
        "exchange",
        "lot_id",
        "vt_symbol",
        "product_root",
        "direction",
        "entry_date",
        "target_date",
        "target_year",
        "preentry_trading_day_offset",
        "entry_minus_target_calendar_days",
        "source_ready",
        "raw_hash_ready",
        "raw_parse_ready",
        "state_feature_ready",
        "quantity_feature_ready",
        "member_rank_numeric_feature_ready",
        "warehouse_numeric_feature_ready",
        "product_present_state",
        "symbol_hit",
        "first_present_known",
        "first_present_date",
        "last_present_date",
        "target_minus_first_present_calendar_days",
        "target_before_first_present",
        "http_status",
        "content_bytes",
        "row_count",
        "symbol_count",
        "schema_hash",
        "sha256",
        "raw_file",
        "strategy_rule_allowed",
        "true_engine_allowed",
        "realized_pnl",
        "r_multiple",
        "realized_pnl_rank_pct",
        "right_tail_top10",
    ]
    return rows[[col for col in columns if col in rows.columns]].sort_values(
        ["entry_date", "lot_id", "source_id", "target_date"]
    ).reset_index(drop=True)


def _lot_source_summary(rows: pd.DataFrame) -> pd.DataFrame:
    grouped = (
        rows.groupby(["source_id", "source_family", "exchange", "lot_id", "vt_symbol", "product_root", "direction", "entry_date"], as_index=False)
        .agg(
            preentry_row_count=("target_date", "nunique"),
            state_ready_count=("state_feature_ready", "sum"),
            present_count=("symbol_hit", "sum"),
            absent_before_first_count=("target_before_first_present", "sum"),
            raw_parse_ready_count=("raw_parse_ready", "sum"),
            quantity_ready_count=("quantity_feature_ready", "sum"),
            first_target_date=("target_date", "min"),
            last_target_date=("target_date", "max"),
            first_present_date=("first_present_date", "first"),
            realized_pnl=("realized_pnl", "first"),
            r_multiple=("r_multiple", "first"),
            realized_pnl_rank_pct=("realized_pnl_rank_pct", "first"),
            right_tail_top10=("right_tail_top10", "first"),
        )
        .sort_values(["entry_date", "lot_id", "source_id"])
    )
    grouped["all_state_ready"] = (grouped["state_ready_count"].eq(grouped["preentry_row_count"])).astype(int)
    grouped["all_product_present"] = (grouped["present_count"].eq(grouped["preentry_row_count"])).astype(int)
    return grouped


def _lot_summary(rows: pd.DataFrame) -> pd.DataFrame:
    grouped = (
        rows.groupby(["lot_id", "vt_symbol", "product_root", "direction", "entry_date"], as_index=False)
        .agg(
            source_count=("source_id", "nunique"),
            feature_row_count=("target_date", "count"),
            state_ready_count=("state_feature_ready", "sum"),
            source_ready_count=("source_ready", "sum"),
            product_present_count=("symbol_hit", "sum"),
            absent_before_first_count=("target_before_first_present", "sum"),
            quantity_ready_count=("quantity_feature_ready", "sum"),
            first_target_date=("target_date", "min"),
            last_target_date=("target_date", "max"),
            realized_pnl=("realized_pnl", "first"),
            r_multiple=("r_multiple", "first"),
            realized_pnl_rank_pct=("realized_pnl_rank_pct", "first"),
            right_tail_top10=("right_tail_top10", "first"),
        )
        .sort_values(["entry_date", "lot_id"])
    )
    grouped["all_state_ready"] = grouped["state_ready_count"].eq(grouped["feature_row_count"]).astype(int)
    grouped["all_source_ready"] = grouped["source_ready_count"].eq(grouped["feature_row_count"]).astype(int)
    grouped["state_ready_ratio"] = grouped["state_ready_count"] / grouped["feature_row_count"].replace(0, np.nan)
    grouped["product_present_ratio"] = grouped["product_present_count"] / grouped["feature_row_count"].replace(0, np.nan)
    return grouped


def _source_state_summary(rows: pd.DataFrame) -> pd.DataFrame:
    summary = (
        rows.groupby(["source_id", "source_family", "target_year", "product_present_state"], as_index=False)
        .agg(
            feature_row_count=("lot_id", "count"),
            unique_lot_count=("lot_id", "nunique"),
            state_ready_count=("state_feature_ready", "sum"),
            symbol_hit_count=("symbol_hit", "sum"),
            right_tail_top10_row_count=("right_tail_top10", "sum"),
        )
        .sort_values(["source_id", "target_year", "product_present_state"])
    )
    return summary


def _schema_fields() -> pd.DataFrame:
    rows = [
        ("feature_schema_version", "string", "固定 schema 版本", 1, 0),
        ("source_id", "string", "官方 raw source 标识", 1, 0),
        ("source_family", "string", "member_rank 或 warehouse", 1, 0),
        ("target_date", "YYYYMMDD", "入场前 raw 交易日", 1, 0),
        ("preentry_trading_day_offset", "int", "相对 entry_date 的前 N 个交易日", 1, 0),
        ("source_ready", "0/1", "raw hash + parse 是否完成", 1, 0),
        ("raw_hash_ready", "0/1", "raw 响应是否有 sha256", 1, 0),
        ("raw_parse_ready", "0/1", "raw 响应是否解析成功", 1, 0),
        ("state_feature_ready", "0/1", "状态字段是否可用于只读绑定", 1, 0),
        ("product_present_state", "category", "产品状态：present 或官方首次出现前缺席等", 1, 0),
        ("symbol_hit", "0/1", "raw 产品列表是否包含目标产品", 1, 0),
        ("first_present_date", "YYYYMMDD", "该 source/product 在 manifest 中首次出现日期", 1, 0),
        ("target_minus_first_present_calendar_days", "int", "target_date 相对首次出现日期的日历差", 1, 0),
        ("quantity_feature_ready", "0/1", "仓单/持仓数值特征是否已审计可用；Stage093 固定为0", 1, 0),
        ("member_rank_numeric_feature_ready", "0/1", "会员排名数值字段是否已审计可用；Stage093 固定为0", 1, 0),
        ("warehouse_numeric_feature_ready", "0/1", "仓单数值字段是否已审计可用；Stage093 固定为0", 1, 0),
        ("strategy_rule_allowed", "0/1", "是否允许进入交易规则；Stage093 固定为0", 1, 0),
        ("true_engine_allowed", "0/1", "是否允许 true engine；Stage093 固定为0", 1, 0),
    ]
    return pd.DataFrame(rows, columns=["field", "dtype", "description", "point_in_time_safe", "trading_rule_allowed"])


def _summary(curve: pd.DataFrame, rows: pd.DataFrame, lot_summary: pd.DataFrame, source_state: pd.DataFrame) -> pd.DataFrame:
    metrics = _official_metrics(curve)
    state_ready = int(rows["state_feature_ready"].sum())
    feature_rows = int(len(rows))
    quantity_ready = int(rows["quantity_feature_ready"].sum())
    raw_parse_gap = int(rows["product_present_state"].eq("raw_parse_gap").sum())
    after_prior = int(rows["product_present_state"].eq("official_absent_after_prior_presence").sum())
    absent_before_first = int(rows["product_present_state"].eq("official_absent_before_first_manifest_presence").sum())
    lots_all_state_ready = int(lot_summary["all_state_ready"].sum()) if not lot_summary.empty else 0
    right_tail_all_state_ready = int(
        lot_summary[lot_summary["right_tail_top10"].eq(1)]["all_state_ready"].sum()
    ) if not lot_summary.empty else 0
    right_tail_lot_count = int(lot_summary["right_tail_top10"].sum()) if not lot_summary.empty else 0
    schema_safe = int(
        state_ready == feature_rows
        and quantity_ready == 0
        and raw_parse_gap == 0
        and after_prior == 0
        and int(rows["strategy_rule_allowed"].sum()) == 0
        and int(rows["true_engine_allowed"].sum()) == 0
    )
    decision = (
        "stage093_state_schema_bound_all_state_ready_no_numeric_no_rule"
        if schema_safe
        else "stage093_state_schema_binding_has_gaps_no_rule"
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
                "feature_schema_version": FEATURE_SCHEMA_VERSION,
                "feature_row_count": feature_rows,
                "linked_lot_count": int(lot_summary["lot_id"].nunique()) if not lot_summary.empty else 0,
                "source_count": int(rows["source_id"].nunique()),
                "state_feature_ready_count": state_ready,
                "quantity_feature_ready_count": quantity_ready,
                "product_present_row_count": int(rows["product_present_state"].eq("present").sum()),
                "absent_before_first_row_count": absent_before_first,
                "raw_parse_gap_row_count": raw_parse_gap,
                "after_prior_presence_gap_row_count": after_prior,
                "lot_all_state_ready_count": lots_all_state_ready,
                "right_tail_lot_count": right_tail_lot_count,
                "right_tail_all_state_ready_count": right_tail_all_state_ready,
                "schema_design_complete": schema_safe,
                "feature_binding_read_only": 1,
                "numeric_feature_extraction_done": 0,
                "feature_binding_strategy_usable": 0,
                **metrics,
            }
        ]
    )


def _plot_official_feature_path(curve: pd.DataFrame, lot_summary: pd.DataFrame, summary: pd.Series) -> None:
    fig, axes = plt.subplots(4, 1, figsize=(14, 10), gridspec_kw={"height_ratios": [2.0, 1.1, 1.1, 1.2]})
    axes[0].plot(curve["date"], curve["account_equity"], color="#0f766e", linewidth=1.5)
    axes[0].set_ylabel("equity")
    axes[0].grid(True, alpha=0.25)
    axes[1].plot(curve["date"], curve["drawdown_pct"], color="#dc2626", linewidth=1.2)
    axes[1].set_ylabel("drawdown %")
    axes[1].grid(True, alpha=0.25)
    axes[2].plot(curve["date"], curve["broker10_margin_to_equity_pct"], color="#7c3aed", linewidth=1.2)
    axes[2].axhline(100, color="#111827", linestyle="--", linewidth=0.8)
    axes[2].set_ylabel("broker10 %")
    axes[2].grid(True, alpha=0.25)
    if not lot_summary.empty:
        frame = lot_summary.copy()
        frame["entry_year"] = pd.to_datetime(frame["entry_date"]).dt.year
        yearly = frame.groupby("entry_year", as_index=False).agg(
            lot_count=("lot_id", "count"),
            all_state_ready_count=("all_state_ready", "sum"),
            absent_before_first_count=("absent_before_first_count", "sum"),
        )
        x = np.arange(len(yearly))
        axes[3].bar(x - 0.2, yearly["lot_count"], width=0.4, color="#93c5fd", label="lots")
        axes[3].bar(x + 0.2, yearly["all_state_ready_count"], width=0.4, color="#047857", alpha=0.75, label="all state ready")
        axes[3].scatter(x, yearly["absent_before_first_count"], color="#b91c1c", s=30, label="absent-before-first rows")
        axes[3].set_xticks(x)
        axes[3].set_xticklabels(yearly["entry_year"].astype(str).tolist())
        axes[3].legend(loc="upper left", fontsize=8)
    axes[3].set_ylabel("count")
    axes[3].grid(True, axis="y", alpha=0.25)
    axes[0].set_title(
        f"{STAGE} point-in-time state schema binding | decision={summary['decision']} | "
        f"rows {int(summary['state_feature_ready_count'])}/{int(summary['feature_row_count'])}"
    )
    fig.tight_layout()
    fig.savefig(OFFICIAL_FEATURE_PATH_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_source_state_heatmap(rows: pd.DataFrame) -> None:
    pivot = rows.pivot_table(
        index="source_id",
        columns="target_year",
        values="state_feature_ready",
        aggfunc="mean",
    ).fillna(-1.0)
    fig, ax = plt.subplots(figsize=(11, 4.5))
    im = ax.imshow(pivot.to_numpy(dtype=float), aspect="auto", cmap="YlGnBu", vmin=0, vmax=1)
    ax.set_xticks(np.arange(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns.astype(str).tolist())
    ax.set_yticks(np.arange(len(pivot.index)))
    ax.set_yticklabels(pivot.index.tolist())
    for i in range(pivot.shape[0]):
        for j in range(pivot.shape[1]):
            value = pivot.iloc[i, j]
            label = "-" if value < 0 else f"{value:.0%}"
            ax.text(j, i, label, ha="center", va="center", fontsize=9)
    ax.set_title("Stage093 state feature ready ratio by source-year")
    fig.colorbar(im, ax=ax, fraction=0.025, pad=0.02)
    fig.tight_layout()
    fig.savefig(SOURCE_STATE_HEATMAP_OUT, dpi=160)
    plt.close(fig)


def _plot_lot_coverage(lot_summary: pd.DataFrame) -> None:
    if lot_summary.empty:
        return
    fig, axes = plt.subplots(2, 1, figsize=(12, 6))
    axes[0].hist(lot_summary["state_ready_ratio"], bins=np.linspace(0, 1, 11), color="#047857", alpha=0.75)
    axes[0].set_title("Lot-level state ready ratio")
    axes[0].set_xlabel("ratio")
    axes[0].set_ylabel("lot count")
    axes[0].grid(True, axis="y", alpha=0.25)
    axes[1].scatter(
        lot_summary["realized_pnl_rank_pct"],
        lot_summary["product_present_ratio"],
        c=np.where(lot_summary["right_tail_top10"].eq(1), "#f97316", "#2563eb"),
        alpha=0.7,
        s=28,
    )
    axes[1].axvline(0.9, color="#dc2626", linestyle="--", linewidth=0.9)
    axes[1].set_xlabel("realized pnl rank pct (audit only)")
    axes[1].set_ylabel("product present ratio")
    axes[1].grid(True, alpha=0.25)
    axes[1].set_title("Coverage vs PnL rank is audit context, not a rule")
    fig.tight_layout()
    fig.savefig(LOT_COVERAGE_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_schema_fields(fields: pd.DataFrame) -> None:
    counts = fields.groupby(["point_in_time_safe", "trading_rule_allowed"], as_index=False).agg(field_count=("field", "count"))
    labels = counts.apply(lambda row: f"pit={int(row['point_in_time_safe'])}, rule={int(row['trading_rule_allowed'])}", axis=1)
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.bar(labels, counts["field_count"], color="#2563eb", alpha=0.75)
    ax.set_ylabel("field count")
    ax.set_title("Stage093 schema fields: point-in-time state fields only; no trading-rule fields")
    ax.grid(True, axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(SCHEMA_FIELD_CHART_OUT, dpi=160)
    plt.close(fig)


def _write_report(
    summary: pd.DataFrame,
    lot_summary: pd.DataFrame,
    source_state: pd.DataFrame,
    fields: pd.DataFrame,
) -> None:
    row = summary.iloc[0]
    report = "\n".join(
        [
            f"# {STAGE} point-in-time feature schema binding",
            "",
            "## Decision",
            "",
            f"- decision: `{row['decision']}`",
            "- nature: fixed point-in-time state schema binding; no numeric extraction, no strategy rule, no true engine, no A/B, no CTP, no order API.",
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
            "## Schema binding summary",
            "",
            f"- schema version: `{row['feature_schema_version']}`",
            f"- feature rows: `{int(row['feature_row_count'])}`",
            f"- linked lots / sources: `{int(row['linked_lot_count'])}` / `{int(row['source_count'])}`",
            f"- state feature ready: `{int(row['state_feature_ready_count'])}` / `{int(row['feature_row_count'])}`",
            f"- quantity feature ready: `{int(row['quantity_feature_ready_count'])}`",
            f"- present / absent-before-first / raw-parse-gap / after-prior: `{int(row['product_present_row_count'])}` / `{int(row['absent_before_first_row_count'])}` / `{int(row['raw_parse_gap_row_count'])}` / `{int(row['after_prior_presence_gap_row_count'])}`",
            f"- lot all-state-ready: `{int(row['lot_all_state_ready_count'])}` / `{int(row['linked_lot_count'])}`",
            f"- right-tail all-state-ready: `{int(row['right_tail_all_state_ready_count'])}` / `{int(row['right_tail_lot_count'])}`",
            f"- numeric feature extraction done: `{int(row['numeric_feature_extraction_done'])}`",
            f"- feature binding strategy usable: `{int(row['feature_binding_strategy_usable'])}`",
            "",
            "## Schema fields",
            "",
            _md_table(fields, max_rows=40),
            "",
            "## Source state summary",
            "",
            _md_table(source_state, max_rows=80),
            "",
            "## Lot coverage sample",
            "",
            _md_table(lot_summary.head(40), max_rows=40),
            "",
            "## Visual outputs",
            "",
            f"- official feature path chart: `{OFFICIAL_FEATURE_PATH_CHART_OUT}`",
            f"- source state heatmap: `{SOURCE_STATE_HEATMAP_OUT}`",
            f"- lot coverage chart: `{LOT_COVERAGE_CHART_OUT}`",
            f"- schema field chart: `{SCHEMA_FIELD_CHART_OUT}`",
            "",
            "## Judgment",
            "",
            "- State schema binding is complete and point-in-time safe as a data artifact.",
            "- Numeric warehouse/member-rank extraction remains explicitly disabled.",
            "- This artifact is not strategy-usable; next step must parse numeric fields and run only read-only stability/visual audits before any true engine discussion.",
        ]
    )
    REPORT_OUT.write_text(report + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    curve = _load_official_curve()
    links = _load_links()
    results = _load_results()
    product_status = _load_product_status()
    lots = _load_lots()
    feature_rows = _build_feature_rows(links, results, product_status, lots)
    lot_source = _lot_source_summary(feature_rows)
    lot_summary = _lot_summary(feature_rows)
    source_state = _source_state_summary(feature_rows)
    fields = _schema_fields()
    summary = _summary(curve, feature_rows, lot_summary, source_state)

    _write_csv(feature_rows, FEATURE_ROWS_OUT)
    _write_csv(lot_source, LOT_SOURCE_SUMMARY_OUT)
    _write_csv(lot_summary, LOT_SUMMARY_OUT)
    _write_csv(source_state, SOURCE_STATE_SUMMARY_OUT)
    _write_csv(fields, SCHEMA_FIELD_OUT)
    _write_csv(summary, SUMMARY_OUT)
    DECISION_OUT.write_text(
        json.dumps(_json_safe(summary.iloc[0].to_dict()), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    _plot_official_feature_path(curve, lot_summary, summary.iloc[0])
    _plot_source_state_heatmap(feature_rows)
    _plot_lot_coverage(lot_summary)
    _plot_schema_fields(fields)
    _write_report(summary, lot_summary, source_state, fields)
    print(json.dumps(_json_safe(summary.iloc[0].to_dict()), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
