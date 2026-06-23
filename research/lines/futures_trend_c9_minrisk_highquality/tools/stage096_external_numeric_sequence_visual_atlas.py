from __future__ import annotations

from datetime import datetime
from pathlib import Path
import sys
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


LINE_ID = "futures_trend_c9_minrisk_highquality"
STAGE = "Stage096"
MODEL_TAG = "stage096_external_numeric_sequence_visual_atlas_v1"
OUTPUT_PREFIX = "qmt_roll_stage096_c9_minrisk_external_numeric_sequence_visual_atlas"
SEQUENCE_SCHEMA_VERSION = "external_numeric_sequence_visual_atlas_v1"
BOTTOM_LOSS_VISUAL_COUNT = 12
MAXDD_CONTEXT_DD_PCT = -40.0
LOTS_PER_ATLAS_PAGE = 4

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
TOOLS_DIR = SCRIPT_PATH.parent
EXAMPLE_DIR = REPO_DIR / "examples" / "portfolio_backtesting"
for path in [str(EXAMPLE_DIR), str(TOOLS_DIR)]:
    if path not in sys.path:
        sys.path.insert(0, path)

from qmt_roll_official_live_config import OFFICIAL_LIVE_ALIAS, OFFICIAL_LIVE_VERSION
from stage089_external_raw_backfill_manifest_probe import (
    _json_safe,
    _load_official_curve,
    _md_table,
    _official_metrics,
    _write_csv,
)


LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
STAGE095_DIR = LINE_DIR / "outputs" / "stage095_full_numeric_feature_extraction_stability_audit"
OUTPUT_DIR = LINE_DIR / "outputs" / "stage096_external_numeric_sequence_visual_atlas"

FEATURE_ROWS_IN = (
    STAGE095_DIR
    / "qmt_roll_stage095_c9_minrisk_full_numeric_feature_extraction_stability_audit_feature_rows_"
    "stage095_full_numeric_feature_extraction_stability_audit_v1.csv"
)
LOT_SUMMARY_IN = (
    STAGE095_DIR
    / "qmt_roll_stage095_c9_minrisk_full_numeric_feature_extraction_stability_audit_lot_summary_"
    "stage095_full_numeric_feature_extraction_stability_audit_v1.csv"
)

SEQUENCE_ROWS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_sequence_rows_{MODEL_TAG}.csv"
SELECTED_LOTS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_selected_lots_{MODEL_TAG}.csv"
COHORT_SEQUENCE_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cohort_sequence_summary_{MODEL_TAG}.csv"
ATLAS_MANIFEST_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_atlas_manifest_{MODEL_TAG}.csv"
SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

OFFICIAL_CONTEXT_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_context_chart_{MODEL_TAG}.png"
COHORT_SEQUENCE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cohort_sequence_chart_{MODEL_TAG}.png"
SELECTION_COVERAGE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_selection_coverage_chart_{MODEL_TAG}.png"

DISPLAY_METRICS = [
    "warehouse_qty",
    "warehouse_change",
    "member_volume",
    "member_net_oi",
]

METRIC_DEFS = [
    ("warehouse_qty", "warehouse", "仓单数量/标准仓单量", "warehouse_receipt_qty_sum", "warehouse_wbill_qty_sum"),
    ("warehouse_change", "warehouse", "仓单当日变化", "warehouse_change_qty_sum", "warehouse_diff_qty_sum"),
    ("warehouse_forecast", "warehouse", "有效预报", "warehouse_valid_forecast_qty_sum", None),
    ("member_volume", "member_rank", "成交/交易量", "member_rank_volume_sum", None),
    ("member_volume_change", "member_rank", "成交/交易量变化", "member_rank_volume_change_sum", None),
    ("member_long_oi", "member_rank", "持买仓量", "member_rank_long_oi_sum", None),
    ("member_short_oi", "member_rank", "持卖仓量", "member_rank_short_oi_sum", None),
    ("member_net_oi", "member_rank", "持买-持卖", "member_rank_long_oi_sum", "member_rank_short_oi_sum"),
    (
        "member_net_oi_change",
        "member_rank",
        "持买变化-持卖变化",
        "member_rank_long_oi_change_sum",
        "member_rank_short_oi_change_sum",
    ),
]

COHORT_ORDER = ["fallback_or_absent", "right_tail", "bottom_loss", "maxdd_context"]
COHORT_COLORS = {
    "fallback_or_absent": "#7c3aed",
    "right_tail": "#f97316",
    "bottom_loss": "#dc2626",
    "maxdd_context": "#2563eb",
}


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise RuntimeError(f"missing required input: {path}")
    return pd.read_csv(path, encoding="utf-8-sig")


def _safe_float(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return np.nan
    return number if np.isfinite(number) else np.nan


def _first_non_null(row: pd.Series, first: str, second: str | None = None) -> float:
    value = _safe_float(row.get(first, np.nan))
    if not np.isnan(value):
        return value
    if second is None:
        return np.nan
    return _safe_float(row.get(second, np.nan))


def _load_feature_rows() -> pd.DataFrame:
    rows = _read_csv(FEATURE_ROWS_IN)
    rows["entry_date"] = pd.to_datetime(rows["entry_date"], errors="coerce").dt.normalize()
    rows["target_date"] = rows["target_date"].astype(str).str.zfill(8)
    rows["target_date_dt"] = pd.to_datetime(rows["target_date"], format="%Y%m%d", errors="coerce")
    rows["preentry_trading_day_offset"] = pd.to_numeric(rows["preentry_trading_day_offset"], errors="coerce").fillna(0).astype(int)
    rows["days_to_entry"] = -rows["preentry_trading_day_offset"]
    for column in [
        "lot_id",
        "realized_pnl",
        "realized_pnl_rank_pct",
        "right_tail_top10",
        "numeric_feature_ready",
        "present_numeric_ready",
    ]:
        rows[column] = pd.to_numeric(rows.get(column, 0), errors="coerce").fillna(0)
    rows["lot_id"] = rows["lot_id"].astype(int)
    rows["right_tail_top10"] = rows["right_tail_top10"].astype(int)
    return rows


def _load_lot_summary() -> pd.DataFrame:
    lots = _read_csv(LOT_SUMMARY_IN)
    lots["lot_id"] = pd.to_numeric(lots["lot_id"], errors="coerce").fillna(0).astype(int)
    lots["entry_date"] = pd.to_datetime(lots["entry_date"], errors="coerce").dt.normalize()
    lots["realized_pnl"] = pd.to_numeric(lots.get("realized_pnl", 0.0), errors="coerce").fillna(0.0)
    lots["realized_pnl_rank_pct"] = pd.to_numeric(lots.get("realized_pnl_rank_pct", 0.0), errors="coerce").fillna(0.0)
    lots["right_tail_top10"] = pd.to_numeric(lots.get("right_tail_top10", 0), errors="coerce").fillna(0).astype(int)
    return lots


def _maxdd_context_window(curve: pd.DataFrame) -> tuple[pd.Timestamp, pd.Timestamp, pd.Timestamp, float]:
    trough_row = curve.loc[curve["drawdown_pct"].idxmin()]
    trough_date = pd.Timestamp(trough_row["date"]).normalize()
    maxdd = float(trough_row["drawdown_pct"])
    episode = curve[curve["drawdown_pct"].le(MAXDD_CONTEXT_DD_PCT)].copy()
    if episode.empty:
        return trough_date, trough_date, trough_date, maxdd
    return (
        pd.Timestamp(episode["date"].min()).normalize(),
        pd.Timestamp(episode["date"].max()).normalize(),
        trough_date,
        maxdd,
    )


def _select_lots(rows: pd.DataFrame, lot_summary: pd.DataFrame, curve: pd.DataFrame) -> pd.DataFrame:
    start, end, trough, maxdd = _maxdd_context_window(curve)
    flags = (
        rows.groupby("lot_id", as_index=False)
        .agg(
            has_subtotal_fallback=("aggregation_source", lambda values: int(any("subtotal" in str(value) for value in values))),
            has_absent_state=("product_present_state", lambda values: int(any(str(value) != "present" for value in values))),
            linked_feature_row_count=("feature_row_id", "count"),
        )
    )
    lots = lot_summary.merge(flags, on="lot_id", how="left")
    for column in ["has_subtotal_fallback", "has_absent_state", "linked_feature_row_count"]:
        if column not in lots:
            lots[column] = 0
        lots[column] = pd.to_numeric(lots[column], errors="coerce").fillna(0).astype(int)
    lots["right_tail_visual"] = lots["right_tail_top10"].astype(int)
    bottom_ids = set(lots.sort_values(["realized_pnl", "lot_id"]).head(BOTTOM_LOSS_VISUAL_COUNT)["lot_id"].astype(int))
    lots["bottom_loss_visual"] = lots["lot_id"].isin(bottom_ids).astype(int)
    lots["maxdd_context_visual"] = lots["entry_date"].between(start, end).astype(int)
    lots["fallback_or_absent_visual"] = ((lots["has_subtotal_fallback"].eq(1)) | (lots["has_absent_state"].eq(1))).astype(int)
    lots["selected_for_atlas"] = (
        lots["right_tail_visual"].eq(1)
        | lots["bottom_loss_visual"].eq(1)
        | lots["maxdd_context_visual"].eq(1)
        | lots["fallback_or_absent_visual"].eq(1)
    ).astype(int)

    def primary(row: pd.Series) -> str:
        for cohort in COHORT_ORDER:
            if cohort == "right_tail" and int(row["right_tail_visual"]) == 1:
                return cohort
            if cohort == "bottom_loss" and int(row["bottom_loss_visual"]) == 1:
                return cohort
            if cohort == "maxdd_context" and int(row["maxdd_context_visual"]) == 1:
                return cohort
            if cohort == "fallback_or_absent" and int(row["fallback_or_absent_visual"]) == 1:
                return cohort
        return "not_selected"

    lots["primary_visual_cohort"] = lots.apply(primary, axis=1)
    lots["cohort_flags"] = lots.apply(
        lambda row: "|".join(
            flag
            for flag, column in [
                ("right_tail", "right_tail_visual"),
                ("bottom_loss", "bottom_loss_visual"),
                ("maxdd_context", "maxdd_context_visual"),
                ("fallback_or_absent", "fallback_or_absent_visual"),
            ]
            if int(row[column]) == 1
        ),
        axis=1,
    )
    lots["maxdd_context_start"] = start.strftime("%Y-%m-%d")
    lots["maxdd_context_end"] = end.strftime("%Y-%m-%d")
    lots["maxdd_trough_date"] = trough.strftime("%Y-%m-%d")
    lots["maxdd_trough_pct"] = maxdd
    return lots.sort_values(["selected_for_atlas", "primary_visual_cohort", "entry_date", "lot_id"], ascending=[False, True, True, True])


def _build_sequence_rows(rows: pd.DataFrame, selected_lots: pd.DataFrame) -> pd.DataFrame:
    lot_flags = selected_lots[
        [
            "lot_id",
            "selected_for_atlas",
            "primary_visual_cohort",
            "cohort_flags",
            "right_tail_visual",
            "bottom_loss_visual",
            "maxdd_context_visual",
            "fallback_or_absent_visual",
        ]
    ]
    frame = rows.merge(lot_flags, on="lot_id", how="left")
    for column in ["selected_for_atlas", "right_tail_visual", "bottom_loss_visual", "maxdd_context_visual", "fallback_or_absent_visual"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(0).astype(int)
    frame["primary_visual_cohort"] = frame["primary_visual_cohort"].fillna("not_selected")
    frame["cohort_flags"] = frame["cohort_flags"].fillna("")

    out_rows: list[dict[str, Any]] = []
    for _, row in frame.iterrows():
        for metric, source_family, label, first_col, second_col in METRIC_DEFS:
            if str(row["source_family"]) != source_family:
                continue
            if metric == "member_net_oi":
                value = _safe_float(row.get(first_col, np.nan)) - _safe_float(row.get(second_col, np.nan))
            elif metric == "member_net_oi_change":
                value = _safe_float(row.get(first_col, np.nan)) - _safe_float(row.get(second_col, np.nan))
            else:
                value = _first_non_null(row, first_col, second_col)
            out_rows.append(
                {
                    "sequence_schema_version": SEQUENCE_SCHEMA_VERSION,
                    "stage": STAGE,
                    "model_tag": MODEL_TAG,
                    "lot_id": int(row["lot_id"]),
                    "vt_symbol": row["vt_symbol"],
                    "product_root": row["product_root"],
                    "direction": row["direction"],
                    "entry_date": row["entry_date"],
                    "target_date": row["target_date"],
                    "days_to_entry": int(row["days_to_entry"]),
                    "preentry_trading_day_offset": int(row["preentry_trading_day_offset"]),
                    "source_id": row["source_id"],
                    "source_family": row["source_family"],
                    "metric": metric,
                    "metric_label": label,
                    "value": value,
                    "aggregation_source": row.get("aggregation_source", ""),
                    "product_present_state": row.get("product_present_state", ""),
                    "numeric_feature_ready": int(row.get("numeric_feature_ready", 0)),
                    "selected_for_atlas": int(row["selected_for_atlas"]),
                    "primary_visual_cohort": row["primary_visual_cohort"],
                    "cohort_flags": row["cohort_flags"],
                    "realized_pnl": _safe_float(row.get("realized_pnl", np.nan)),
                    "realized_pnl_rank_pct": _safe_float(row.get("realized_pnl_rank_pct", np.nan)),
                    "right_tail_top10": int(row.get("right_tail_top10", 0)),
                    "strategy_rule_allowed": 0,
                    "true_engine_allowed": 0,
                }
            )
    sequence = pd.DataFrame(out_rows)
    sequence["entry_date"] = pd.to_datetime(sequence["entry_date"], errors="coerce").dt.strftime("%Y-%m-%d")
    sequence["value"] = pd.to_numeric(sequence["value"], errors="coerce")
    sequence = sequence.sort_values(["lot_id", "source_family", "metric", "days_to_entry"]).reset_index(drop=True)
    sequence["first_valid_value"] = sequence.groupby(["lot_id", "source_family", "metric"])["value"].transform(
        lambda values: values.dropna().iloc[0] if not values.dropna().empty else np.nan
    )
    sequence["value_delta_from_first"] = sequence["value"] - sequence["first_valid_value"]
    sequence["value_index_to_first_100"] = np.where(
        sequence["first_valid_value"].abs() > 1e-12,
        sequence["value"] / sequence["first_valid_value"] * 100.0,
        np.nan,
    )
    return sequence


def _cohort_sequence_summary(sequence: pd.DataFrame) -> pd.DataFrame:
    selected = sequence[sequence["selected_for_atlas"].eq(1)].copy()
    grouped = (
        selected.groupby(["primary_visual_cohort", "metric", "days_to_entry"], as_index=False)
        .agg(
            row_count=("value", "count"),
            lot_count=("lot_id", "nunique"),
            value_median=("value", "median"),
            value_delta_median=("value_delta_from_first", "median"),
            value_index_median=("value_index_to_first_100", "median"),
        )
        .sort_values(["primary_visual_cohort", "metric", "days_to_entry"])
    )
    return grouped


def _atlas_manifest(selected_lots: pd.DataFrame) -> pd.DataFrame:
    selected = selected_lots[selected_lots["selected_for_atlas"].eq(1)].copy()
    selected = selected.sort_values(["primary_visual_cohort", "entry_date", "lot_id"]).reset_index(drop=True)
    selected["atlas_order"] = np.arange(1, len(selected) + 1)
    selected["atlas_page"] = ((selected["atlas_order"] - 1) // LOTS_PER_ATLAS_PAGE + 1).astype(int)
    return selected


def _summary(curve: pd.DataFrame, rows: pd.DataFrame, sequence: pd.DataFrame, selected_lots: pd.DataFrame, manifest: pd.DataFrame) -> pd.DataFrame:
    metrics = _official_metrics(curve)
    start, end, trough, maxdd = _maxdd_context_window(curve)
    selected = selected_lots[selected_lots["selected_for_atlas"].eq(1)]
    return pd.DataFrame(
        [
            {
                "stage": STAGE,
                "model_tag": MODEL_TAG,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "line_id": LINE_ID,
                "decision": "stage096_visual_atlas_ready_no_rule",
                "official_live_alias": OFFICIAL_LIVE_ALIAS,
                "official_live_version": OFFICIAL_LIVE_VERSION,
                "official_config_changed": 0,
                "strategy_rule_created": 0,
                "true_engine_run": 0,
                "ab_triggered": 0,
                "order_api_called": 0,
                "ctp_connected": 0,
                "sequence_schema_version": SEQUENCE_SCHEMA_VERSION,
                "feature_row_count": int(len(rows)),
                "sequence_row_count": int(len(sequence)),
                "lot_count": int(selected_lots["lot_id"].nunique()),
                "selected_lot_count": int(len(selected)),
                "atlas_page_count": int(manifest["atlas_page"].max()) if not manifest.empty else 0,
                "right_tail_visual_lot_count": int(selected_lots["right_tail_visual"].sum()),
                "bottom_loss_visual_lot_count": int(selected_lots["bottom_loss_visual"].sum()),
                "maxdd_context_visual_lot_count": int(selected_lots["maxdd_context_visual"].sum()),
                "fallback_or_absent_visual_lot_count": int(selected_lots["fallback_or_absent_visual"].sum()),
                "maxdd_context_start": start.strftime("%Y-%m-%d"),
                "maxdd_context_end": end.strftime("%Y-%m-%d"),
                "maxdd_trough_date": trough.strftime("%Y-%m-%d"),
                "maxdd_trough_pct": maxdd,
                "visual_atlas_created": 1,
                "economic_semantic_precheck_done": 1,
                "strategy_feature_usable": 0,
                **metrics,
            }
        ]
    )


def _plot_official_context(curve: pd.DataFrame, manifest: pd.DataFrame, summary: pd.Series) -> None:
    fig, axes = plt.subplots(3, 1, figsize=(14, 9), gridspec_kw={"height_ratios": [2.0, 1.0, 1.4]})
    axes[0].plot(curve["date"], curve["account_equity"], color="#0f766e", linewidth=1.5)
    axes[0].set_ylabel("equity")
    axes[0].grid(True, alpha=0.25)
    axes[1].plot(curve["date"], curve["drawdown_pct"], color="#dc2626", linewidth=1.2)
    axes[1].axhline(MAXDD_CONTEXT_DD_PCT, color="#111827", linestyle="--", linewidth=0.8)
    axes[1].set_ylabel("drawdown %")
    axes[1].grid(True, alpha=0.25)
    selected = manifest.copy()
    if not selected.empty:
        curve_points = curve[["date", "account_equity"]].copy()
        curve_points["date"] = pd.to_datetime(curve_points["date"]).dt.normalize()
        selected["entry_date_dt"] = pd.to_datetime(selected["entry_date"]).dt.normalize()
        selected = pd.merge_asof(
            selected.sort_values("entry_date_dt"),
            curve_points.sort_values("date"),
            left_on="entry_date_dt",
            right_on="date",
            direction="nearest",
        )
        for cohort, group in selected.groupby("primary_visual_cohort"):
            axes[0].scatter(
                group["entry_date_dt"],
                group["account_equity"],
                s=30,
                label=cohort,
                color=COHORT_COLORS.get(cohort, "#64748b"),
                alpha=0.85,
            )
        axes[0].legend(loc="upper left", fontsize=8, ncol=2)
        counts = selected["primary_visual_cohort"].value_counts().reindex(COHORT_ORDER).fillna(0)
        axes[2].bar(counts.index, counts.values, color=[COHORT_COLORS.get(item, "#64748b") for item in counts.index], alpha=0.8)
        axes[2].set_ylabel("selected lots")
        axes[2].grid(True, axis="y", alpha=0.25)
    axes[0].set_title(
        f"{STAGE} external numeric visual atlas | selected lots {int(summary['selected_lot_count'])} | "
        f"rule_allowed=0"
    )
    fig.tight_layout()
    fig.savefig(OFFICIAL_CONTEXT_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_cohort_sequence(sequence_summary: pd.DataFrame) -> None:
    metrics = DISPLAY_METRICS
    fig, axes = plt.subplots(2, 2, figsize=(13, 8), sharex=True)
    axes_flat = axes.ravel()
    for ax, metric in zip(axes_flat, metrics):
        frame = sequence_summary[sequence_summary["metric"].eq(metric)].copy()
        for cohort in COHORT_ORDER:
            group = frame[frame["primary_visual_cohort"].eq(cohort)].sort_values("days_to_entry")
            if group.empty:
                continue
            ax.plot(
                group["days_to_entry"],
                group["value_delta_median"],
                marker="o",
                linewidth=1.2,
                label=cohort,
                color=COHORT_COLORS.get(cohort, "#64748b"),
            )
        ax.axhline(0, color="#111827", linewidth=0.7, alpha=0.5)
        ax.set_title(metric)
        ax.set_xlabel("trading days to entry")
        ax.set_ylabel("median delta from first")
        ax.grid(True, alpha=0.25)
    axes_flat[0].legend(loc="best", fontsize=8)
    fig.suptitle("Stage096 cohort median sequence shape for visual precheck only")
    fig.tight_layout()
    fig.savefig(COHORT_SEQUENCE_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_selection_coverage(selected_lots: pd.DataFrame) -> None:
    counts = pd.DataFrame(
        [
            ("right_tail", int(selected_lots["right_tail_visual"].sum())),
            ("bottom_loss", int(selected_lots["bottom_loss_visual"].sum())),
            ("maxdd_context", int(selected_lots["maxdd_context_visual"].sum())),
            ("fallback_or_absent", int(selected_lots["fallback_or_absent_visual"].sum())),
            ("selected_union", int(selected_lots["selected_for_atlas"].sum())),
        ],
        columns=["cohort", "lot_count"],
    )
    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.bar(counts["cohort"], counts["lot_count"], color="#2563eb", alpha=0.75)
    ax.set_ylabel("lot count")
    ax.set_title("Stage096 fixed visual cohorts; not trading buckets")
    ax.grid(True, axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(SELECTION_COVERAGE_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_atlas_pages(sequence: pd.DataFrame, manifest: pd.DataFrame) -> list[Path]:
    pages: list[Path] = []
    selected_sequence = sequence[sequence["selected_for_atlas"].eq(1)].copy()
    for page, page_lots in manifest.groupby("atlas_page"):
        page_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_atlas_page_{int(page):03d}_{MODEL_TAG}.png"
        pages.append(page_path)
        fig, axes = plt.subplots(LOTS_PER_ATLAS_PAGE, len(DISPLAY_METRICS), figsize=(15, 10), squeeze=False)
        for row_idx in range(LOTS_PER_ATLAS_PAGE):
            if row_idx >= len(page_lots):
                for ax in axes[row_idx]:
                    ax.axis("off")
                continue
            lot = page_lots.iloc[row_idx]
            lot_seq = selected_sequence[selected_sequence["lot_id"].eq(int(lot["lot_id"]))]
            for col_idx, metric in enumerate(DISPLAY_METRICS):
                ax = axes[row_idx, col_idx]
                metric_seq = lot_seq[lot_seq["metric"].eq(metric)].sort_values("days_to_entry")
                if metric_seq.empty or metric_seq["value"].dropna().empty:
                    ax.text(0.5, 0.5, "n/a", ha="center", va="center", transform=ax.transAxes)
                    ax.set_xticks([])
                    ax.set_yticks([])
                else:
                    ax.plot(metric_seq["days_to_entry"], metric_seq["value"], marker="o", linewidth=1.1, color="#2563eb")
                    ax.grid(True, alpha=0.25)
                if row_idx == 0:
                    ax.set_title(metric, fontsize=10)
                if col_idx == 0:
                    label = (
                        f"lot {int(lot['lot_id'])} {lot['vt_symbol']} {lot['direction']}\n"
                        f"pnl {float(lot['realized_pnl']):,.0f} | {lot['primary_visual_cohort']}"
                    )
                    ax.set_ylabel(label, fontsize=8)
                ax.set_xlabel("days")
        fig.suptitle(f"Stage096 external numeric preentry sequence atlas page {int(page):03d}; visual only, rule_allowed=0")
        fig.tight_layout()
        fig.savefig(page_path, dpi=150)
        plt.close(fig)
    return pages


def _write_report(summary: pd.DataFrame, selected_lots: pd.DataFrame, sequence_summary: pd.DataFrame, atlas_pages: list[Path]) -> None:
    row = summary.iloc[0]
    selected = selected_lots[selected_lots["selected_for_atlas"].eq(1)].copy()
    cohort_counts = selected["primary_visual_cohort"].value_counts().rename_axis("primary_visual_cohort").reset_index(name="lot_count")
    report = "\n".join(
        [
            f"# {STAGE} external numeric sequence visual atlas",
            "",
            "## Decision",
            "",
            f"- decision: `{row['decision']}`",
            "- nature: fixed visual atlas and economic semantic precheck; no thresholds, no TopN, no rolling, no flow weights, no true engine, no A/B, no CTP, no order API.",
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
            "## Visual atlas summary",
            "",
            f"- feature rows: `{int(row['feature_row_count'])}`",
            f"- sequence rows: `{int(row['sequence_row_count'])}`",
            f"- lot count: `{int(row['lot_count'])}`",
            f"- selected lot count: `{int(row['selected_lot_count'])}`",
            f"- atlas pages: `{int(row['atlas_page_count'])}`",
            f"- right-tail visual lots: `{int(row['right_tail_visual_lot_count'])}`",
            f"- bottom-loss visual lots: `{int(row['bottom_loss_visual_lot_count'])}`",
            f"- maxDD context visual lots: `{int(row['maxdd_context_visual_lot_count'])}`",
            f"- fallback-or-absent visual lots: `{int(row['fallback_or_absent_visual_lot_count'])}`",
            f"- maxDD context: `{row['maxdd_context_start']}` to `{row['maxdd_context_end']}`, trough `{row['maxdd_trough_date']}` `{row['maxdd_trough_pct']:.4f}%`",
            f"- strategy feature usable: `{int(row['strategy_feature_usable'])}`",
            "",
            "## Cohort counts",
            "",
            _md_table(cohort_counts, max_rows=20),
            "",
            "## Selected lot sample",
            "",
            _md_table(
                selected[
                    [
                        "lot_id",
                        "vt_symbol",
                        "direction",
                        "entry_date",
                        "realized_pnl",
                        "realized_pnl_rank_pct",
                        "primary_visual_cohort",
                        "cohort_flags",
                    ]
                ].head(60),
                max_rows=60,
            ),
            "",
            "## Sequence summary sample",
            "",
            _md_table(sequence_summary.head(80), max_rows=80),
            "",
            "## Visual outputs",
            "",
            f"- official context chart: `{OFFICIAL_CONTEXT_CHART_OUT}`",
            f"- cohort sequence chart: `{COHORT_SEQUENCE_CHART_OUT}`",
            f"- selection coverage chart: `{SELECTION_COVERAGE_CHART_OUT}`",
            f"- atlas manifest: `{ATLAS_MANIFEST_OUT}`",
            f"- atlas pages: `{len(atlas_pages)}` files, first `{atlas_pages[0] if atlas_pages else ''}`",
            "",
            "## Judgment",
            "",
            "- The atlas is useful for human visual inspection of external supply/participation states before entries.",
            "- It does not establish a tradable rule; every plotted cohort is a visual audit cohort, not a decision bucket.",
            "- Any future rule must start from a separately predeclared economic hypothesis and then pass right-tail protection before true engine discussion.",
        ]
    )
    REPORT_OUT.write_text(report + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    curve = _load_official_curve()
    rows = _load_feature_rows()
    lot_summary = _load_lot_summary()
    selected_lots = _select_lots(rows, lot_summary, curve)
    sequence = _build_sequence_rows(rows, selected_lots)
    sequence_summary = _cohort_sequence_summary(sequence)
    manifest = _atlas_manifest(selected_lots)
    summary = _summary(curve, rows, sequence, selected_lots, manifest)

    _write_csv(sequence, SEQUENCE_ROWS_OUT)
    _write_csv(selected_lots, SELECTED_LOTS_OUT)
    _write_csv(sequence_summary, COHORT_SEQUENCE_SUMMARY_OUT)
    _write_csv(manifest, ATLAS_MANIFEST_OUT)
    _write_csv(summary, SUMMARY_OUT)
    DECISION_OUT.write_text(
        pd.Series(_json_safe(summary.iloc[0].to_dict())).to_json(force_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    _plot_official_context(curve, manifest, summary.iloc[0])
    _plot_cohort_sequence(sequence_summary)
    _plot_selection_coverage(selected_lots)
    atlas_pages = _plot_atlas_pages(sequence, manifest)
    _write_report(summary, selected_lots, sequence_summary, atlas_pages)


if __name__ == "__main__":
    main()
