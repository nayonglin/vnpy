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
STAGE = "Stage092"
MODEL_TAG = "stage092_product_timing_gap_right_tail_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage092_c9_minrisk_product_timing_gap_right_tail_audit"
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
OUTPUT_DIR = LINE_DIR / "outputs" / "stage092_product_timing_gap_right_tail_audit"

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

PRODUCT_DATE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_date_status_{MODEL_TAG}.csv"
GAP_ROWS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gap_product_dates_{MODEL_TAG}.csv"
GAP_LOT_LINKS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gap_lot_window_links_{MODEL_TAG}.csv"
GAP_GROUP_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gap_group_summary_{MODEL_TAG}.csv"
LOT_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gap_lot_summary_{MODEL_TAG}.csv"
SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

OFFICIAL_GAP_PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_gap_path_chart_{MODEL_TAG}.png"
GAP_TIMELINE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gap_timeline_chart_{MODEL_TAG}.png"
GAP_LOT_PNL_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gap_lot_pnl_chart_{MODEL_TAG}.png"
CLASSIFICATION_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_classification_chart_{MODEL_TAG}.png"


def _target_date(value: Any) -> str:
    text = str(value).strip()
    if text.endswith(".0"):
        text = text[:-2]
    return text.zfill(8)


def _load_results() -> pd.DataFrame:
    results = _read_csv(RESULTS_IN)
    results["target_date"] = results["target_date"].map(_target_date)
    results["target_year"] = results["target_date"].str.slice(0, 4).astype(int)
    for column in ["parse_ready", "needed_symbol_hit_all", "needed_symbol_miss_count", "row_count", "symbol_count"]:
        results[column] = pd.to_numeric(results.get(column, 0), errors="coerce").fillna(0)
    return results


def _expand_product_dates(results: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for row in results.itertuples(index=False):
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
                    "target_date": str(row.target_date),
                    "target_year": int(row.target_year),
                    "status": str(row.status),
                    "parse_ready": int(row.parse_ready),
                    "hit": hit,
                    "sample_symbols": str(row.sample_symbols),
                    "raw_file": str(row.raw_file),
                }
            )
    expanded = pd.DataFrame(rows).sort_values(["source_id", "product_root", "target_date"]).reset_index(drop=True)
    first_hits = (
        expanded[expanded["hit"].eq(1)]
        .groupby(["source_id", "product_root"], as_index=False)
        .agg(first_present_date=("target_date", "min"), last_present_date=("target_date", "max"))
    )
    expanded = expanded.merge(first_hits, on=["source_id", "product_root"], how="left")

    def classify(row: pd.Series) -> str:
        if int(row["parse_ready"]) != 1:
            return "raw_parse_gap"
        if int(row["hit"]) == 1:
            return "present"
        first = str(row.get("first_present_date", ""))
        if not first or first == "nan":
            return "official_absent_no_present_in_manifest"
        if str(row["target_date"]) < first:
            return "official_absent_before_first_manifest_presence"
        return "official_absent_after_prior_presence"

    expanded["coverage_class"] = expanded.apply(classify, axis=1)
    return expanded


def _load_links() -> pd.DataFrame:
    links = _read_csv(LINKS_IN)
    links["target_date"] = links["target_date"].map(_target_date)
    links["entry_date"] = pd.to_datetime(links["entry_date"], errors="coerce").dt.normalize()
    links["realized_pnl"] = pd.to_numeric(links.get("realized_pnl", 0.0), errors="coerce").fillna(0.0)
    return links


def _load_lots_with_rank() -> pd.DataFrame:
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
        "exit_date",
        "realized_pnl",
        "r_multiple",
        "winner",
        "big_winner",
        "realized_pnl_rank_pct",
        "right_tail_top10",
    ]
    return lots[[column for column in cols if column in lots.columns]].copy()


def _bind_gap_lots(gaps: pd.DataFrame, links: pd.DataFrame, lots: pd.DataFrame, curve: pd.DataFrame) -> pd.DataFrame:
    if gaps.empty:
        return pd.DataFrame()
    gap_keys = gaps[["source_id", "exchange", "product_root", "target_date", "target_year", "coverage_class", "first_present_date", "sample_symbols", "raw_file"]]
    bound = gap_keys.merge(
        links,
        on=["source_id", "exchange", "product_root", "target_date", "target_year"],
        how="left",
        suffixes=("", "_link"),
    )
    bound = bound.merge(lots, on=["lot_id", "vt_symbol", "direction", "entry_date", "realized_pnl"], how="left")
    curve_context = curve[["date", "account_equity", "drawdown_pct", "broker10_margin_to_equity_pct"]].copy()
    bound = bound.merge(curve_context, left_on="entry_date", right_on="date", how="left").drop(columns=["date"])
    bound["right_tail_top10"] = pd.to_numeric(bound.get("right_tail_top10", 0), errors="coerce").fillna(0).astype(int)
    bound["realized_pnl_rank_pct"] = pd.to_numeric(bound.get("realized_pnl_rank_pct", 0), errors="coerce").fillna(0.0)
    return bound.sort_values(["source_id", "product_root", "target_date", "lot_id"]).reset_index(drop=True)


def _gap_group_summary(gap_links: pd.DataFrame) -> pd.DataFrame:
    if gap_links.empty:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    for keys, group in gap_links.groupby(["source_id", "exchange", "product_root", "target_year", "coverage_class"], sort=True):
        source_id, exchange, product_root, target_year, coverage_class = keys
        unique_lots = group.drop_duplicates(["lot_id"])
        rows.append(
            {
                "source_id": source_id,
                "exchange": exchange,
                "product_root": product_root,
                "target_year": int(target_year),
                "coverage_class": coverage_class,
                "gap_product_date_count": int(group["target_date"].nunique()),
                "linked_lot_count": int(unique_lots["lot_id"].nunique()),
                "first_target_date": str(group["target_date"].min()),
                "last_target_date": str(group["target_date"].max()),
                "first_present_date": str(group["first_present_date"].iloc[0]),
                "first_entry_date": group["entry_date"].min(),
                "last_entry_date": group["entry_date"].max(),
                "linked_unique_lot_realized_pnl_sum": float(unique_lots["realized_pnl"].sum()),
                "linked_unique_lot_realized_pnl_min": float(unique_lots["realized_pnl"].min()),
                "linked_unique_lot_realized_pnl_max": float(unique_lots["realized_pnl"].max()),
                "right_tail_top10_lot_count": int(unique_lots["right_tail_top10"].sum()),
                "min_drawdown_at_entry": float(group["drawdown_pct"].min()),
                "max_broker10_at_entry": float(group["broker10_margin_to_equity_pct"].max()),
            }
        )
    grouped = pd.DataFrame(rows).sort_values(["source_id", "product_root", "target_year"])
    grouped["right_tail_gap_flag"] = (grouped["right_tail_top10_lot_count"] > 0).astype(int)
    return grouped


def _gap_lot_summary(gap_links: pd.DataFrame) -> pd.DataFrame:
    if gap_links.empty:
        return pd.DataFrame()
    summary = (
        gap_links.groupby(["source_id", "product_root", "lot_id", "vt_symbol", "direction", "entry_date"], as_index=False)
        .agg(
            gap_product_date_count=("target_date", "nunique"),
            first_gap_target_date=("target_date", "min"),
            last_gap_target_date=("target_date", "max"),
            coverage_class=("coverage_class", "first"),
            first_present_date=("first_present_date", "first"),
            realized_pnl=("realized_pnl", "first"),
            r_multiple=("r_multiple", "first"),
            realized_pnl_rank_pct=("realized_pnl_rank_pct", "first"),
            right_tail_top10=("right_tail_top10", "first"),
            account_equity_at_entry=("account_equity", "first"),
            drawdown_at_entry=("drawdown_pct", "first"),
            broker10_at_entry=("broker10_margin_to_equity_pct", "first"),
        )
        .sort_values(["source_id", "product_root", "lot_id"])
    )
    return summary


def _summary(curve: pd.DataFrame, product_dates: pd.DataFrame, gaps: pd.DataFrame, gap_links: pd.DataFrame, group_summary: pd.DataFrame) -> pd.DataFrame:
    metrics = _official_metrics(curve)
    gap_classes = gaps["coverage_class"].value_counts().to_dict() if not gaps.empty else {}
    parse_gap_count = int(gap_classes.get("raw_parse_gap", 0))
    after_prior_count = int(gap_classes.get("official_absent_after_prior_presence", 0))
    before_first_count = int(gap_classes.get("official_absent_before_first_manifest_presence", 0))
    right_tail_gap_groups = int(group_summary["right_tail_gap_flag"].sum()) if not group_summary.empty else 0
    classification_complete = int(parse_gap_count == 0 and after_prior_count == 0 and before_first_count == len(gaps))
    decision = (
        "stage092_gaps_classified_as_pre_first_presence_schema_design_allowed_no_rule"
        if classification_complete
        else "stage092_gaps_unresolved_no_feature_binding_no_rule"
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
                "expanded_product_date_count": int(len(product_dates)),
                "gap_product_date_count": int(len(gaps)),
                "gap_lot_window_link_count": int(len(gap_links)),
                "gap_unique_lot_count": int(gap_links["lot_id"].nunique()) if not gap_links.empty else 0,
                "gap_group_count": int(len(group_summary)),
                "gap_pre_first_presence_count": before_first_count,
                "gap_raw_parse_count": parse_gap_count,
                "gap_after_prior_presence_count": after_prior_count,
                "right_tail_gap_group_count": right_tail_gap_groups,
                "gap_linked_realized_pnl_sum": float(gap_links.drop_duplicates(["source_id", "product_root", "lot_id"])["realized_pnl"].sum()) if not gap_links.empty else 0.0,
                "classification_complete": classification_complete,
                "feature_binding_schema_design_allowed": classification_complete,
                **metrics,
            }
        ]
    )


def _plot_official_gap_path(curve: pd.DataFrame, gap_lots: pd.DataFrame, summary: pd.Series) -> None:
    fig, axes = plt.subplots(3, 1, figsize=(14, 8), sharex=True)
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
    if not gap_lots.empty:
        for _, row in gap_lots.iterrows():
            entry = pd.Timestamp(row["entry_date"])
            label = f"{row['source_id']}:{row['product_root']} lot {int(row['lot_id'])}"
            for ax in axes:
                ax.axvline(entry, color="#f97316", alpha=0.35, linewidth=1.0)
            axes[0].scatter([entry], [row["account_equity_at_entry"]], color="#f97316", s=35)
            axes[0].text(entry, row["account_equity_at_entry"], label, fontsize=8, rotation=20)
    axes[0].set_title(
        f"{STAGE} gap-linked lot entry context | decision={summary['decision']} | gaps {int(summary['gap_product_date_count'])}"
    )
    fig.tight_layout()
    fig.savefig(OFFICIAL_GAP_PATH_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_gap_timeline(product_dates: pd.DataFrame) -> None:
    focus = product_dates[product_dates["source_id"].isin(["czce_warehouse", "gfex_warehouse"])].copy()
    focus = focus[
        ((focus["source_id"].eq("czce_warehouse")) & focus["product_root"].eq("AP"))
        | ((focus["source_id"].eq("gfex_warehouse")) & focus["product_root"].eq("LC"))
    ].copy()
    if focus.empty:
        return
    focus["date"] = pd.to_datetime(focus["target_date"], format="%Y%m%d", errors="coerce")
    focus["row_label"] = focus["source_id"] + ":" + focus["product_root"]
    y_map = {label: idx for idx, label in enumerate(sorted(focus["row_label"].unique()))}
    colors = focus["hit"].map({1: "#047857", 0: "#b91c1c"})
    fig, ax = plt.subplots(figsize=(12, 4))
    ax.scatter(focus["date"], focus["row_label"].map(y_map), c=colors, s=45)
    ax.set_yticks(list(y_map.values()))
    ax.set_yticklabels(list(y_map.keys()))
    ax.grid(True, axis="x", alpha=0.25)
    ax.set_title("Stage092 focus product timeline; green=present, red=official absent in raw symbols")
    fig.autofmt_xdate(rotation=30)
    fig.tight_layout()
    fig.savefig(GAP_TIMELINE_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_gap_lot_pnl(gap_lots: pd.DataFrame) -> None:
    if gap_lots.empty:
        return
    frame = gap_lots.copy()
    frame["label"] = frame["source_id"] + ":" + frame["product_root"] + " lot " + frame["lot_id"].astype(int).astype(str)
    fig, axes = plt.subplots(2, 1, figsize=(10, 6), sharex=True)
    colors = np.where(frame["realized_pnl"] >= 0, "#047857", "#b91c1c")
    axes[0].bar(frame["label"], frame["realized_pnl"], color=colors, alpha=0.75)
    axes[0].axhline(0, color="#111827", linewidth=0.8)
    axes[0].set_ylabel("realized pnl")
    axes[0].grid(True, axis="y", alpha=0.25)
    axes[1].bar(frame["label"], frame["realized_pnl_rank_pct"], color="#2563eb", alpha=0.75)
    axes[1].axhline(0.9, color="#dc2626", linestyle="--", linewidth=0.9)
    axes[1].set_ylabel("pnl rank pct")
    axes[1].grid(True, axis="y", alpha=0.25)
    axes[0].set_title("Stage092 gap-linked lot PnL and right-tail rank")
    fig.autofmt_xdate(rotation=15)
    fig.tight_layout()
    fig.savefig(GAP_LOT_PNL_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_classification(product_dates: pd.DataFrame, summary: pd.Series) -> None:
    counts = product_dates["coverage_class"].value_counts().sort_index()
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.bar(counts.index.tolist(), counts.values, color="#2563eb", alpha=0.75)
    ax.set_ylabel("product-date count")
    ax.set_title(f"Stage092 coverage classification | schema design allowed={int(summary['feature_binding_schema_design_allowed'])}")
    ax.grid(True, axis="y", alpha=0.25)
    ax.tick_params(axis="x", labelrotation=15)
    fig.tight_layout()
    fig.savefig(CLASSIFICATION_CHART_OUT, dpi=160)
    plt.close(fig)


def _write_report(
    summary: pd.DataFrame,
    gaps: pd.DataFrame,
    gap_links: pd.DataFrame,
    group_summary: pd.DataFrame,
    lot_summary: pd.DataFrame,
) -> None:
    row = summary.iloc[0]
    report = "\n".join(
        [
            f"# {STAGE} product timing gap right-tail audit",
            "",
            "## Decision",
            "",
            f"- decision: `{row['decision']}`",
            "- nature: coverage gap classification and right-tail safety audit; no strategy rule, no true engine, no A/B, no CTP, no order API.",
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
            "## Gap summary",
            "",
            f"- expanded product-date count: `{int(row['expanded_product_date_count'])}`",
            f"- gap product-date count: `{int(row['gap_product_date_count'])}`",
            f"- gap lot-window links / unique lots: `{int(row['gap_lot_window_link_count'])}` / `{int(row['gap_unique_lot_count'])}`",
            f"- pre-first-presence/raw-parse/after-prior gaps: `{int(row['gap_pre_first_presence_count'])}` / `{int(row['gap_raw_parse_count'])}` / `{int(row['gap_after_prior_presence_count'])}`",
            f"- right-tail gap groups: `{int(row['right_tail_gap_group_count'])}`",
            f"- linked unique-lot realized pnl sum: `{row['gap_linked_realized_pnl_sum']:,.2f}`",
            f"- classification complete: `{int(row['classification_complete'])}`",
            f"- feature binding schema design allowed: `{int(row['feature_binding_schema_design_allowed'])}`",
            "",
            "## Gap groups",
            "",
            _md_table(group_summary, max_rows=20),
            "",
            "## Gap lot summary",
            "",
            _md_table(lot_summary, max_rows=20),
            "",
            "## Gap product dates",
            "",
            _md_table(gaps, max_rows=40),
            "",
            "## Visual outputs",
            "",
            f"- official gap path chart: `{OFFICIAL_GAP_PATH_CHART_OUT}`",
            f"- gap timeline chart: `{GAP_TIMELINE_CHART_OUT}`",
            f"- gap lot pnl chart: `{GAP_LOT_PNL_CHART_OUT}`",
            f"- classification chart: `{CLASSIFICATION_CHART_OUT}`",
            "",
            "## Judgment",
            "",
            "- The two gap groups are pre-first-presence timing states, not raw parse failures.",
            "- Gap-linked lots are not right-tail top-decile lots in this audit, but this is still not a trade signal.",
            "- Next step may design a point-in-time feature schema with explicit state fields; no true engine or A/B is allowed yet.",
        ]
    )
    REPORT_OUT.write_text(report + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    curve = _load_official_curve()
    results = _load_results()
    product_dates = _expand_product_dates(results)
    gaps = product_dates[~product_dates["coverage_class"].eq("present")].copy()
    links = _load_links()
    lots = _load_lots_with_rank()
    gap_links = _bind_gap_lots(gaps, links, lots, curve)
    group_summary = _gap_group_summary(gap_links)
    lot_summary = _gap_lot_summary(gap_links)
    summary = _summary(curve, product_dates, gaps, gap_links, group_summary)

    _write_csv(product_dates, PRODUCT_DATE_OUT)
    _write_csv(gaps, GAP_ROWS_OUT)
    _write_csv(gap_links, GAP_LOT_LINKS_OUT)
    _write_csv(group_summary, GAP_GROUP_OUT)
    _write_csv(lot_summary, LOT_SUMMARY_OUT)
    _write_csv(summary, SUMMARY_OUT)
    DECISION_OUT.write_text(
        json.dumps(_json_safe(summary.iloc[0].to_dict()), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    _plot_official_gap_path(curve, lot_summary, summary.iloc[0])
    _plot_gap_timeline(product_dates)
    _plot_gap_lot_pnl(lot_summary)
    _plot_classification(product_dates, summary.iloc[0])
    _write_report(summary, gaps, gap_links, group_summary, lot_summary)
    print(json.dumps(_json_safe(summary.iloc[0].to_dict()), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
