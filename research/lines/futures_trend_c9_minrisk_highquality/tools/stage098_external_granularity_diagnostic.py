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
STAGE = "Stage098"
MODEL_TAG = "stage098_external_granularity_diagnostic_v1"
OUTPUT_PREFIX = "qmt_roll_stage098_c9_minrisk_external_granularity_diagnostic"

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
STAGE096_DIR = LINE_DIR / "outputs" / "stage096_external_numeric_sequence_visual_atlas"
STAGE097_DIR = LINE_DIR / "outputs" / "stage097_external_sequence_hypothesis_preflight"
OUTPUT_DIR = LINE_DIR / "outputs" / "stage098_external_granularity_diagnostic"

SEQUENCE_ROWS_IN = (
    STAGE096_DIR
    / "qmt_roll_stage096_c9_minrisk_external_numeric_sequence_visual_atlas_sequence_rows_"
    "stage096_external_numeric_sequence_visual_atlas_v1.csv"
)
LOT_PREFLIGHT_IN = (
    STAGE097_DIR
    / "qmt_roll_stage097_c9_minrisk_external_sequence_hypothesis_preflight_lot_preflight_"
    "stage097_external_sequence_hypothesis_preflight_v1.csv"
)

LOT_DIAGNOSTIC_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_lot_diagnostic_{MODEL_TAG}.csv"
COLLISION_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_collision_summary_{MODEL_TAG}.csv"
COLLISION_GROUPS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_collision_groups_{MODEL_TAG}.csv"
PRODUCT_YEAR_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_year_summary_{MODEL_TAG}.csv"
SOURCE_GAP_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_source_gap_summary_{MODEL_TAG}.csv"
GRANULARITY_GATE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_granularity_gate_{MODEL_TAG}.csv"
SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

OFFICIAL_PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_chart_{MODEL_TAG}.png"
COLLISION_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_collision_chart_{MODEL_TAG}.png"
PRODUCT_YEAR_DENSITY_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_year_density_chart_{MODEL_TAG}.png"
GATE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_granularity_gate_chart_{MODEL_TAG}.png"

SIGN_METRICS = ["warehouse_qty", "warehouse_change", "member_volume", "member_net_oi"]
SIGN_DAYS = [-7, -6, -5, -4, -3, -2, -1]

BLOCK_COLORS = {
    "member_detail_missing": "#a855f7",
    "same_contract_entry_conflict": "#dc2626",
    "product_year_state_tail_conflict": "#f97316",
    "product_year_singleton": "#64748b",
    "coarse_state_only": "#2563eb",
}


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise RuntimeError(f"missing required input: {path}")
    return pd.read_csv(path, encoding="utf-8-sig")


def _sign_token(value: Any) -> str:
    number = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(number):
        return "m"
    if number > 0:
        return "+"
    if number < 0:
        return "-"
    return "0"


def _load_inputs() -> tuple[pd.DataFrame, pd.DataFrame]:
    sequence = _read_csv(SEQUENCE_ROWS_IN)
    lots = _read_csv(LOT_PREFLIGHT_IN)
    sequence["lot_id"] = pd.to_numeric(sequence["lot_id"], errors="coerce").fillna(0).astype(int)
    sequence["days_to_entry"] = pd.to_numeric(sequence["days_to_entry"], errors="coerce").astype("Int64")
    sequence["value_delta_from_first"] = pd.to_numeric(sequence["value_delta_from_first"], errors="coerce")
    lots["lot_id"] = pd.to_numeric(lots["lot_id"], errors="coerce").fillna(0).astype(int)
    lots["entry_date"] = pd.to_datetime(lots["entry_date"], errors="coerce").dt.normalize()
    lots["entry_year"] = lots["entry_date"].dt.year
    return sequence, lots


def _sequence_signatures(sequence: pd.DataFrame) -> pd.DataFrame:
    frame = sequence[sequence["metric"].isin(SIGN_METRICS) & sequence["days_to_entry"].isin(SIGN_DAYS)].copy()
    frame["sign"] = frame["value_delta_from_first"].map(_sign_token)
    rows: list[dict[str, Any]] = []
    for lot_id, group in frame.groupby("lot_id"):
        item: dict[str, Any] = {"lot_id": int(lot_id)}
        for metric in SIGN_METRICS:
            metric_group = group[group["metric"].eq(metric)].set_index("days_to_entry")
            token = "".join(str(metric_group["sign"].get(day, "m")) for day in SIGN_DAYS)
            item[f"{metric}_sign_path"] = token
        item["sequence_sign_path_signature"] = "|".join(item[f"{metric}_sign_path"] for metric in SIGN_METRICS)
        rows.append(item)
    return pd.DataFrame(rows)


def _group_stats(frame: pd.DataFrame, group_cols: list[str], level: str, scope: str) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame()
    grouped = (
        frame.groupby(group_cols, dropna=False)
        .agg(
            lot_count=("lot_id", "nunique"),
            realized_pnl_min=("realized_pnl", "min"),
            realized_pnl_max=("realized_pnl", "max"),
            realized_pnl_sum=("realized_pnl", "sum"),
            right_tail_lot_count=("right_tail_visual", "sum"),
            bottom_loss_lot_count=("bottom_loss_visual", "sum"),
            maxdd_context_lot_count=("maxdd_context_visual", "sum"),
            fallback_or_absent_lot_count=("fallback_or_absent_visual", "sum"),
            product_count=("product_root", "nunique"),
            year_count=("entry_year", "nunique"),
        )
        .reset_index()
    )
    grouped.insert(0, "scope", scope)
    grouped.insert(1, "signature_level", level)
    grouped["pnl_range"] = grouped["realized_pnl_max"] - grouped["realized_pnl_min"]
    grouped["pnl_sign_conflict"] = (
        grouped["realized_pnl_min"].lt(0) & grouped["realized_pnl_max"].gt(0)
    ).astype(int)
    grouped["tail_conflict"] = (
        grouped["right_tail_lot_count"].gt(0)
        & (grouped["bottom_loss_lot_count"].gt(0) | grouped["maxdd_context_lot_count"].gt(0))
    ).astype(int)
    grouped["multi_lot_group"] = grouped["lot_count"].gt(1).astype(int)
    grouped["signature_key"] = grouped[group_cols].astype(str).agg("|".join, axis=1)
    return grouped


def _collision_tables(lots: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    levels = [
        ("h_state", ["H1_directional_supply_member_alignment", "H2_participation_without_external_alignment"]),
        (
            "product_year_h_state",
            [
                "product_root",
                "entry_year",
                "H1_directional_supply_member_alignment",
                "H2_participation_without_external_alignment",
            ],
        ),
        ("same_contract_entry", ["vt_symbol", "direction", "entry_date"]),
        ("sequence_sign_path", ["sequence_sign_path_signature"]),
    ]
    groups: list[pd.DataFrame] = []
    for scope, frame in [("all", lots), ("selected", lots[lots["selected_for_atlas"].eq(1)])]:
        for level, columns in levels:
            groups.append(_group_stats(frame, columns, level, scope))
    group_table = pd.concat(groups, ignore_index=True)
    summary = (
        group_table.groupby(["scope", "signature_level"], as_index=False)
        .agg(
            group_count=("signature_key", "count"),
            multi_lot_group_count=("multi_lot_group", "sum"),
            pnl_sign_conflict_group_count=("pnl_sign_conflict", "sum"),
            tail_conflict_group_count=("tail_conflict", "sum"),
            max_lot_count=("lot_count", "max"),
            max_pnl_range=("pnl_range", "max"),
        )
        .sort_values(["scope", "signature_level"])
    )
    return summary, group_table


def _product_year_summary(lots: pd.DataFrame) -> pd.DataFrame:
    selected = lots[lots["selected_for_atlas"].eq(1)].copy()
    summary = (
        selected.groupby(["product_root", "entry_year"], as_index=False)
        .agg(
            lot_count=("lot_id", "nunique"),
            right_tail_lot_count=("right_tail_visual", "sum"),
            bottom_loss_lot_count=("bottom_loss_visual", "sum"),
            maxdd_context_lot_count=("maxdd_context_visual", "sum"),
            fallback_or_absent_lot_count=("fallback_or_absent_visual", "sum"),
            h_state_count=("H1_directional_supply_member_alignment", "nunique"),
            pnl_min=("realized_pnl", "min"),
            pnl_max=("realized_pnl", "max"),
        )
        .sort_values(["entry_year", "product_root"])
    )
    summary["pnl_sign_conflict"] = (summary["pnl_min"].lt(0) & summary["pnl_max"].gt(0)).astype(int)
    summary["tail_conflict"] = (
        summary["right_tail_lot_count"].gt(0)
        & (summary["bottom_loss_lot_count"].gt(0) | summary["maxdd_context_lot_count"].gt(0))
    ).astype(int)
    summary["singleton_cell"] = summary["lot_count"].eq(1).astype(int)
    return summary


def _source_gap_summary(lots: pd.DataFrame) -> pd.DataFrame:
    frame = lots.copy()
    for column in ["member_net_oi_delta_7d", "warehouse_qty_delta_7d", "member_volume_delta_7d"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return (
        frame.groupby("product_root", as_index=False)
        .agg(
            lot_count=("lot_id", "nunique"),
            selected_lot_count=("selected_for_atlas", "sum"),
            source_count_min=("source_count", "min"),
            source_count_max=("source_count", "max"),
            member_net_oi_ready_count=("member_net_oi_delta_7d", lambda values: int(values.notna().sum())),
            member_volume_ready_count=("member_volume_delta_7d", lambda values: int(values.notna().sum())),
            warehouse_ready_count=("warehouse_qty_delta_7d", lambda values: int(values.notna().sum())),
            right_tail_lot_count=("right_tail_visual", "sum"),
            bottom_loss_lot_count=("bottom_loss_visual", "sum"),
        )
        .assign(
            member_detail_missing=lambda df: df["member_net_oi_ready_count"].lt(df["lot_count"]).astype(int),
            source_family_gap=lambda df: df["source_count_min"].lt(2).astype(int),
        )
        .sort_values(["member_detail_missing", "source_family_gap", "selected_lot_count"], ascending=False)
    )


def _lot_diagnostic(lots: pd.DataFrame, group_table: pd.DataFrame, product_year: pd.DataFrame) -> pd.DataFrame:
    out = lots.copy()
    py = product_year[["product_root", "entry_year", "lot_count", "singleton_cell", "tail_conflict"]].rename(
        columns={
            "lot_count": "product_year_selected_lot_count",
            "singleton_cell": "product_year_singleton",
            "tail_conflict": "product_year_tail_conflict",
        }
    )
    out = out.merge(py, on=["product_root", "entry_year"], how="left")

    same = group_table[
        group_table["signature_level"].eq("same_contract_entry") & group_table["scope"].eq("all")
    ][["vt_symbol", "direction", "entry_date", "pnl_sign_conflict", "tail_conflict", "lot_count"]].rename(
        columns={
            "pnl_sign_conflict": "same_contract_pnl_sign_conflict",
            "tail_conflict": "same_contract_tail_conflict",
            "lot_count": "same_contract_lot_count",
        }
    )
    same["entry_date"] = pd.to_datetime(same["entry_date"], errors="coerce").dt.normalize()
    out = out.merge(same, on=["vt_symbol", "direction", "entry_date"], how="left")

    state = group_table[
        group_table["signature_level"].eq("product_year_h_state") & group_table["scope"].eq("selected")
    ][
        [
            "product_root",
            "entry_year",
            "H1_directional_supply_member_alignment",
            "H2_participation_without_external_alignment",
            "tail_conflict",
            "pnl_sign_conflict",
        ]
    ].rename(
        columns={
            "tail_conflict": "product_year_state_tail_conflict",
            "pnl_sign_conflict": "product_year_state_pnl_sign_conflict",
        }
    )
    out = out.merge(
        state,
        on=[
            "product_root",
            "entry_year",
            "H1_directional_supply_member_alignment",
            "H2_participation_without_external_alignment",
        ],
        how="left",
    )

    for column in [
        "product_year_selected_lot_count",
        "product_year_singleton",
        "product_year_tail_conflict",
        "same_contract_pnl_sign_conflict",
        "same_contract_tail_conflict",
        "same_contract_lot_count",
        "product_year_state_tail_conflict",
        "product_year_state_pnl_sign_conflict",
    ]:
        out[column] = pd.to_numeric(out[column], errors="coerce").fillna(0).astype(int)

    member_missing = out["member_net_oi_delta_7d"].isna()
    out["granularity_block_reason"] = np.select(
        [
            member_missing,
            out["same_contract_pnl_sign_conflict"].eq(1) | out["same_contract_tail_conflict"].eq(1),
            out["product_year_state_tail_conflict"].eq(1),
            out["product_year_singleton"].eq(1),
        ],
        [
            "member_detail_missing",
            "same_contract_entry_conflict",
            "product_year_state_tail_conflict",
            "product_year_singleton",
        ],
        default="coarse_state_only",
    )
    out["granularity_rule_allowed"] = 0
    out["true_engine_allowed"] = 0
    return out


def _granularity_gate(
    lot_diag: pd.DataFrame,
    collision_summary: pd.DataFrame,
    product_year: pd.DataFrame,
    source_gap: pd.DataFrame,
) -> pd.DataFrame:
    selected_collision = collision_summary[collision_summary["scope"].eq("selected")]
    py_cells = len(product_year)
    singleton_cells = int(product_year["singleton_cell"].sum())
    same_entry_conflicts = int(
        selected_collision[selected_collision["signature_level"].eq("same_contract_entry")][
            "pnl_sign_conflict_group_count"
        ].iloc[0]
    )
    state_tail_conflicts = int(
        selected_collision[selected_collision["signature_level"].eq("product_year_h_state")][
            "tail_conflict_group_count"
        ].iloc[0]
    )
    member_missing_products = int(source_gap["member_detail_missing"].sum())
    rows = [
        {
            "gate_id": "right_tail_conflict",
            "evidence_value": state_tail_conflicts,
            "evidence_unit": "selected product-year H-state groups with right-tail and bad-tail conflict",
            "judgment": "fail_rule_promotion",
            "rule_allowed": 0,
            "next_data_needed": "more granular state that separates right-tail from bottom/maxDD before any engine",
        },
        {
            "gate_id": "product_year_sparsity",
            "evidence_value": singleton_cells,
            "evidence_unit": f"singleton selected product-year cells out of {py_cells}",
            "judgment": "fail_rule_promotion",
            "rule_allowed": 0,
            "next_data_needed": "broader OOS coverage or abandon product/year rescue",
        },
        {
            "gate_id": "same_contract_entry_collision",
            "evidence_value": same_entry_conflicts,
            "evidence_unit": "selected same-contract-entry groups with positive/negative PnL conflict",
            "judgment": "fail_rule_promotion",
            "rule_allowed": 0,
            "next_data_needed": "layer-level executable/minute state, not product-total external state",
        },
        {
            "gate_id": "member_detail_gap",
            "evidence_value": member_missing_products,
            "evidence_unit": "products without complete member net OI detail in current source set",
            "judgment": "fail_rule_promotion",
            "rule_allowed": 0,
            "next_data_needed": "authorized/vendor member rank for missing exchanges or category/seat-level data",
        },
    ]
    gate = pd.DataFrame(rows)
    gate["preflight_only"] = 1
    gate["strategy_feature_usable"] = 0
    return gate


def _summary(
    curve: pd.DataFrame,
    lot_diag: pd.DataFrame,
    collision_summary: pd.DataFrame,
    product_year: pd.DataFrame,
    source_gap: pd.DataFrame,
    gate: pd.DataFrame,
) -> pd.DataFrame:
    metrics = _official_metrics(curve)
    selected = lot_diag[lot_diag["selected_for_atlas"].eq(1)]
    selected_collision = collision_summary[collision_summary["scope"].eq("selected")]
    product_year_cells = int(len(product_year))
    singleton_cells = int(product_year["singleton_cell"].sum())
    py_state_tail_conflict_count = int(
        selected_collision[selected_collision["signature_level"].eq("product_year_h_state")][
            "tail_conflict_group_count"
        ].iloc[0]
    )
    same_contract_pnl_conflict_count = int(
        selected_collision[selected_collision["signature_level"].eq("same_contract_entry")][
            "pnl_sign_conflict_group_count"
        ].iloc[0]
    )
    return pd.DataFrame(
        [
            {
                "stage": STAGE,
                "model_tag": MODEL_TAG,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "line_id": LINE_ID,
                "decision": "stage098_product_total_granularity_insufficient_no_rule",
                "official_live_alias": OFFICIAL_LIVE_ALIAS,
                "official_live_version": OFFICIAL_LIVE_VERSION,
                "official_config_changed": 0,
                "strategy_rule_created": 0,
                "true_engine_run": 0,
                "ab_triggered": 0,
                "order_api_called": 0,
                "ctp_connected": 0,
                "selected_lot_count": int(selected["lot_id"].nunique()),
                "all_lot_count": int(lot_diag["lot_id"].nunique()),
                "selected_product_year_cell_count": product_year_cells,
                "selected_product_year_singleton_cell_count": singleton_cells,
                "selected_product_year_singleton_cell_ratio": singleton_cells / product_year_cells
                if product_year_cells
                else np.nan,
                "selected_product_year_h_state_tail_conflict_group_count": py_state_tail_conflict_count,
                "selected_same_contract_entry_pnl_conflict_group_count": same_contract_pnl_conflict_count,
                "member_detail_missing_product_count": int(source_gap["member_detail_missing"].sum()),
                "source_family_gap_product_count": int(source_gap["source_family_gap"].sum()),
                "granularity_gate_count": int(len(gate)),
                "granularity_gate_failed_count": int((gate["rule_allowed"].eq(0)).sum()),
                "hypotheses_promoted_to_true_engine": 0,
                "preflight_only": 1,
                "strategy_feature_usable": 0,
                **metrics,
            }
        ]
    )


def _plot_official_path(curve: pd.DataFrame, lot_diag: pd.DataFrame, summary: pd.Series) -> None:
    selected = lot_diag[lot_diag["selected_for_atlas"].eq(1)].copy()
    fig, axes = plt.subplots(3, 1, figsize=(14, 9), gridspec_kw={"height_ratios": [2.0, 1.0, 1.2]})
    axes[0].plot(curve["date"], curve["account_equity"], color="#0f766e", linewidth=1.4)
    axes[0].set_ylabel("equity")
    axes[0].grid(True, alpha=0.25)
    axes[1].plot(curve["date"], curve["drawdown_pct"], color="#dc2626", linewidth=1.1)
    axes[1].set_ylabel("drawdown %")
    axes[1].grid(True, alpha=0.25)
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
        for reason, group in selected.groupby("granularity_block_reason"):
            axes[0].scatter(
                group["entry_date_dt"],
                group["account_equity"],
                s=30,
                color=BLOCK_COLORS.get(reason, "#64748b"),
                label=reason,
                alpha=0.86,
            )
        axes[0].legend(loc="upper left", fontsize=8, ncol=2)
        counts = selected["granularity_block_reason"].value_counts()
        axes[2].bar(counts.index, counts.values, color=[BLOCK_COLORS.get(item, "#64748b") for item in counts.index])
        axes[2].set_ylabel("selected lots")
        axes[2].tick_params(axis="x", rotation=20)
        axes[2].grid(True, axis="y", alpha=0.25)
    axes[0].set_title(
        f"{STAGE} product-total granularity diagnostic | selected {int(summary['selected_lot_count'])} | rule_allowed=0"
    )
    fig.tight_layout()
    fig.savefig(OFFICIAL_PATH_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_collision(collision_summary: pd.DataFrame) -> None:
    selected = collision_summary[collision_summary["scope"].eq("selected")].copy()
    x = np.arange(len(selected))
    fig, ax = plt.subplots(figsize=(12, 5))
    width = 0.25
    ax.bar(x - width, selected["multi_lot_group_count"], width=width, label="multi_lot", color="#2563eb")
    ax.bar(x, selected["pnl_sign_conflict_group_count"], width=width, label="pnl_sign_conflict", color="#dc2626")
    ax.bar(x + width, selected["tail_conflict_group_count"], width=width, label="tail_conflict", color="#f97316")
    ax.set_xticks(x)
    ax.set_xticklabels(selected["signature_level"], rotation=20, ha="right")
    ax.set_ylabel("group count")
    ax.set_title("Stage098 selected collision diagnostics by signature level")
    ax.grid(True, axis="y", alpha=0.25)
    ax.legend()
    fig.tight_layout()
    fig.savefig(COLLISION_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_product_year_density(product_year: pd.DataFrame) -> None:
    pivot = product_year.pivot_table(index="product_root", columns="entry_year", values="lot_count", fill_value=0)
    pivot = pivot.sort_index()
    fig, ax = plt.subplots(figsize=(11, 5))
    im = ax.imshow(pivot.to_numpy(), aspect="auto", cmap="Blues")
    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns)
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels(pivot.index)
    for row_idx, product in enumerate(pivot.index):
        for col_idx, year in enumerate(pivot.columns):
            value = int(pivot.loc[product, year])
            if value > 0:
                ax.text(col_idx, row_idx, str(value), ha="center", va="center", fontsize=8)
    ax.set_title("Stage098 selected lot count by product-year; sparse cells block rule promotion")
    fig.colorbar(im, ax=ax, label="selected lot count")
    fig.tight_layout()
    fig.savefig(PRODUCT_YEAR_DENSITY_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_gate(gate: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(11, 4.5))
    ax.bar(gate["gate_id"], gate["evidence_value"], color="#dc2626", alpha=0.8)
    ax.set_ylabel("evidence count")
    ax.set_title("Stage098 granularity gates all fail rule promotion")
    ax.tick_params(axis="x", rotation=20)
    ax.grid(True, axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(GATE_CHART_OUT, dpi=160)
    plt.close(fig)


def _write_report(
    summary: pd.DataFrame,
    collision_summary: pd.DataFrame,
    collision_groups: pd.DataFrame,
    product_year: pd.DataFrame,
    source_gap: pd.DataFrame,
    gate: pd.DataFrame,
) -> None:
    row = summary.iloc[0]
    report = "\n".join(
        [
            f"# {STAGE} external granularity diagnostic",
            "",
            "## Decision",
            "",
            f"- decision: `{row['decision']}`",
            "- nature: product-total granularity diagnostic; no thresholds, no true engine, no A/B, no CTP, no order API.",
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
            "",
            "## Granularity Summary",
            "",
            f"- selected lots: `{int(row['selected_lot_count'])}`",
            f"- all lots: `{int(row['all_lot_count'])}`",
            f"- selected product-year cells: `{int(row['selected_product_year_cell_count'])}`",
            f"- singleton product-year cells: `{int(row['selected_product_year_singleton_cell_count'])}`",
            f"- singleton product-year cell ratio: `{row['selected_product_year_singleton_cell_ratio']:.4f}`",
            f"- selected product-year H-state tail conflict groups: `{int(row['selected_product_year_h_state_tail_conflict_group_count'])}`",
            f"- selected same-contract-entry PnL conflict groups: `{int(row['selected_same_contract_entry_pnl_conflict_group_count'])}`",
            f"- member detail missing products: `{int(row['member_detail_missing_product_count'])}`",
            f"- source family gap products: `{int(row['source_family_gap_product_count'])}`",
            f"- strategy feature usable: `{int(row['strategy_feature_usable'])}`",
            "",
            "## Granularity Gates",
            "",
            _md_table(gate, max_rows=20),
            "",
            "## Collision Summary",
            "",
            _md_table(collision_summary, max_rows=20),
            "",
            "## Strong Collision Groups",
            "",
            _md_table(
                collision_groups[
                    (collision_groups["scope"].eq("selected"))
                    & (collision_groups["tail_conflict"].eq(1) | collision_groups["pnl_sign_conflict"].eq(1))
                ].head(30),
                max_rows=30,
            ),
            "",
            "## Product-year Summary",
            "",
            _md_table(product_year.head(60), max_rows=60),
            "",
            "## Source Gap Summary",
            "",
            _md_table(source_gap, max_rows=20),
            "",
            "## Visual outputs",
            "",
            f"- official path chart: `{OFFICIAL_PATH_CHART_OUT}`",
            f"- collision chart: `{COLLISION_CHART_OUT}`",
            f"- product-year density chart: `{PRODUCT_YEAR_DENSITY_CHART_OUT}`",
            f"- granularity gate chart: `{GATE_CHART_OUT}`",
            "",
            "## Judgment",
            "",
            "- Product-total warehouse/member signals are too coarse for direct rule promotion.",
            "- The next useful data would need finer member/seat/category structure, contract-month OI migration, basis/inventory linkage, or authorized order-flow data.",
            "- Continuing to tune H1/H2 or product-year slices would be overfitting.",
        ]
    )
    REPORT_OUT.write_text(report + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    curve = _load_official_curve()
    sequence, lots = _load_inputs()
    signatures = _sequence_signatures(sequence)
    lots = lots.merge(signatures, on="lot_id", how="left")
    lots["sequence_sign_path_signature"] = lots["sequence_sign_path_signature"].fillna("missing")

    collision_summary, collision_groups = _collision_tables(lots)
    product_year = _product_year_summary(lots)
    source_gap = _source_gap_summary(lots)
    lot_diag = _lot_diagnostic(lots, collision_groups, product_year)
    gate = _granularity_gate(lot_diag, collision_summary, product_year, source_gap)
    summary = _summary(curve, lot_diag, collision_summary, product_year, source_gap, gate)

    _write_csv(lot_diag, LOT_DIAGNOSTIC_OUT)
    _write_csv(collision_summary, COLLISION_SUMMARY_OUT)
    _write_csv(collision_groups, COLLISION_GROUPS_OUT)
    _write_csv(product_year, PRODUCT_YEAR_SUMMARY_OUT)
    _write_csv(source_gap, SOURCE_GAP_SUMMARY_OUT)
    _write_csv(gate, GRANULARITY_GATE_OUT)
    _write_csv(summary, SUMMARY_OUT)
    DECISION_OUT.write_text(
        pd.Series(_json_safe(summary.iloc[0].to_dict())).to_json(force_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    _plot_official_path(curve, lot_diag, summary.iloc[0])
    _plot_collision(collision_summary)
    _plot_product_year_density(product_year)
    _plot_gate(gate)
    _write_report(summary, collision_summary, collision_groups, product_year, source_gap, gate)


if __name__ == "__main__":
    main()
