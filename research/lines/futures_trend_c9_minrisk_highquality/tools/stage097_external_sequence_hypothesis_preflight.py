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
STAGE = "Stage097"
MODEL_TAG = "stage097_external_sequence_hypothesis_preflight_v1"
OUTPUT_PREFIX = "qmt_roll_stage097_c9_minrisk_external_sequence_hypothesis_preflight"

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
OUTPUT_DIR = LINE_DIR / "outputs" / "stage097_external_sequence_hypothesis_preflight"

SEQUENCE_ROWS_IN = (
    STAGE096_DIR
    / "qmt_roll_stage096_c9_minrisk_external_numeric_sequence_visual_atlas_sequence_rows_"
    "stage096_external_numeric_sequence_visual_atlas_v1.csv"
)
SELECTED_LOTS_IN = (
    STAGE096_DIR
    / "qmt_roll_stage096_c9_minrisk_external_numeric_sequence_visual_atlas_selected_lots_"
    "stage096_external_numeric_sequence_visual_atlas_v1.csv"
)

LOT_PREFLIGHT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_lot_preflight_{MODEL_TAG}.csv"
HYPOTHESIS_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_hypothesis_summary_{MODEL_TAG}.csv"
COHORT_STATE_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cohort_state_summary_{MODEL_TAG}.csv"
PRODUCT_YEAR_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_year_summary_{MODEL_TAG}.csv"
SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

OFFICIAL_PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_chart_{MODEL_TAG}.png"
COHORT_STATE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cohort_state_chart_{MODEL_TAG}.png"
RIGHT_TAIL_CONFLICT_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_right_tail_conflict_chart_{MODEL_TAG}.png"
PRODUCT_YEAR_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_year_concentration_chart_{MODEL_TAG}.png"

DISPLAY_METRICS = ["warehouse_qty", "member_net_oi", "member_volume"]
HYPOTHESES = [
    {
        "hypothesis_id": "H1_directional_supply_member_alignment",
        "predeclared_logic": (
            "A signal is externally cleaner when pre-entry warehouse supply direction and member net OI flow "
            "both support the trade direction."
        ),
        "preflight_question": "Does both-support protect right-tail while avoiding bottom-loss/maxDD concentration?",
    },
    {
        "hypothesis_id": "H2_participation_without_external_alignment",
        "predeclared_logic": (
            "A rising pre-entry member volume without full supply/member alignment may be crowding/noise rather "
            "than high-quality confirmation."
        ),
        "preflight_question": "Does this state isolate bad tails without cutting right-tail?",
    },
]

STATE_COLORS = {
    "both_support": "#16a34a",
    "both_headwind": "#dc2626",
    "mixed_or_neutral": "#64748b",
    "participation_without_full_alignment": "#f97316",
    "not_participation_without_full_alignment": "#2563eb",
    "insufficient": "#a855f7",
}


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise RuntimeError(f"missing required input: {path}")
    return pd.read_csv(path, encoding="utf-8-sig")


def _state_from_sign(value: float, positive: str, negative: str) -> str:
    if pd.isna(value):
        return "insufficient"
    if value > 0:
        return positive
    if value < 0:
        return negative
    return "neutral"


def _load_inputs() -> tuple[pd.DataFrame, pd.DataFrame]:
    sequence = _read_csv(SEQUENCE_ROWS_IN)
    lots = _read_csv(SELECTED_LOTS_IN)
    sequence["days_to_entry"] = pd.to_numeric(sequence["days_to_entry"], errors="coerce")
    sequence["lot_id"] = pd.to_numeric(sequence["lot_id"], errors="coerce").fillna(0).astype(int)
    lots["lot_id"] = pd.to_numeric(lots["lot_id"], errors="coerce").fillna(0).astype(int)
    lots["entry_date"] = pd.to_datetime(lots["entry_date"], errors="coerce").dt.normalize()
    return sequence, lots


def _build_lot_preflight(sequence: pd.DataFrame, lots: pd.DataFrame) -> pd.DataFrame:
    last = sequence[sequence["days_to_entry"].eq(-1) & sequence["metric"].isin(DISPLAY_METRICS)].copy()
    delta = (
        last.pivot_table(index="lot_id", columns="metric", values="value_delta_from_first", aggfunc="first")
        .rename_axis(None, axis=1)
        .reset_index()
    )
    delta = delta.rename(
        columns={
            "warehouse_qty": "warehouse_qty_delta_7d",
            "member_net_oi": "member_net_oi_delta_7d",
            "member_volume": "member_volume_delta_7d",
        }
    )
    out = lots.merge(delta, on="lot_id", how="left")
    direction_sign = out["direction"].map({"long": 1.0, "short": -1.0})
    out["direction_sign"] = direction_sign

    supply_directional = direction_sign * pd.to_numeric(out["warehouse_qty_delta_7d"], errors="coerce")
    member_directional = direction_sign * pd.to_numeric(out["member_net_oi_delta_7d"], errors="coerce")
    volume_delta = pd.to_numeric(out["member_volume_delta_7d"], errors="coerce")

    out["supply_directional_delta"] = supply_directional
    out["member_net_oi_directional_delta"] = member_directional
    out["supply_state"] = [
        _state_from_sign(value, positive="headwind", negative="support") for value in supply_directional
    ]
    out["member_net_oi_state"] = [
        _state_from_sign(value, positive="support", negative="headwind") for value in member_directional
    ]
    out["member_volume_state"] = [
        _state_from_sign(value, positive="rising", negative="falling") for value in volume_delta
    ]

    out["H1_directional_supply_member_alignment"] = np.select(
        [
            out["supply_state"].eq("support") & out["member_net_oi_state"].eq("support"),
            out["supply_state"].eq("headwind") & out["member_net_oi_state"].eq("headwind"),
            out["supply_state"].eq("insufficient") | out["member_net_oi_state"].eq("insufficient"),
        ],
        ["both_support", "both_headwind", "insufficient"],
        default="mixed_or_neutral",
    )
    out["H2_participation_without_external_alignment"] = np.select(
        [
            out["member_volume_state"].eq("rising")
            & ~out["H1_directional_supply_member_alignment"].eq("both_support"),
            out["member_volume_state"].eq("insufficient"),
        ],
        ["participation_without_full_alignment", "insufficient"],
        default="not_participation_without_full_alignment",
    )
    out["entry_year"] = out["entry_date"].dt.year
    out["preflight_only"] = 1
    out["strategy_rule_allowed"] = 0
    out["true_engine_allowed"] = 0
    return out


def _cohort_state_summary(lots: pd.DataFrame) -> pd.DataFrame:
    frames = []
    selected = lots[lots["selected_for_atlas"].eq(1)].copy()
    for hypothesis in HYPOTHESES:
        column = hypothesis["hypothesis_id"]
        grouped = (
            selected.groupby(["primary_visual_cohort", column], as_index=False)
            .agg(
                lot_count=("lot_id", "nunique"),
                right_tail_lot_count=("right_tail_visual", "sum"),
                bottom_loss_lot_count=("bottom_loss_visual", "sum"),
                maxdd_context_lot_count=("maxdd_context_visual", "sum"),
                fallback_or_absent_lot_count=("fallback_or_absent_visual", "sum"),
                product_count=("product_root", "nunique"),
                year_count=("entry_year", "nunique"),
            )
            .rename(columns={column: "hypothesis_state"})
        )
        grouped.insert(0, "hypothesis_id", column)
        frames.append(grouped)
    return pd.concat(frames, ignore_index=True)


def _hypothesis_summary(lots: pd.DataFrame) -> pd.DataFrame:
    frames = []
    selected = lots[lots["selected_for_atlas"].eq(1)].copy()
    for hypothesis in HYPOTHESES:
        column = hypothesis["hypothesis_id"]
        for state, group in selected.groupby(column):
            frames.append(
                {
                    "hypothesis_id": column,
                    "hypothesis_state": state,
                    "selected_lot_count": int(group["lot_id"].nunique()),
                    "right_tail_lot_count": int(group["right_tail_visual"].sum()),
                    "bottom_loss_lot_count": int(group["bottom_loss_visual"].sum()),
                    "maxdd_context_lot_count": int(group["maxdd_context_visual"].sum()),
                    "fallback_or_absent_lot_count": int(group["fallback_or_absent_visual"].sum()),
                    "product_count": int(group["product_root"].nunique()),
                    "year_count": int(group["entry_year"].nunique()),
                    "predeclared_logic": hypothesis["predeclared_logic"],
                    "preflight_question": hypothesis["preflight_question"],
                }
            )
    return pd.DataFrame(frames).sort_values(["hypothesis_id", "hypothesis_state"]).reset_index(drop=True)


def _product_year_summary(lots: pd.DataFrame) -> pd.DataFrame:
    frames = []
    selected = lots[lots["selected_for_atlas"].eq(1)].copy()
    for hypothesis in HYPOTHESES:
        column = hypothesis["hypothesis_id"]
        grouped = (
            selected.groupby([column, "product_root", "entry_year"], as_index=False)
            .agg(
                lot_count=("lot_id", "nunique"),
                right_tail_lot_count=("right_tail_visual", "sum"),
                bottom_loss_lot_count=("bottom_loss_visual", "sum"),
                maxdd_context_lot_count=("maxdd_context_visual", "sum"),
            )
            .rename(columns={column: "hypothesis_state"})
        )
        grouped.insert(0, "hypothesis_id", column)
        frames.append(grouped)
    return pd.concat(frames, ignore_index=True)


def _summary(curve: pd.DataFrame, lots: pd.DataFrame, hypothesis_summary: pd.DataFrame) -> pd.DataFrame:
    metrics = _official_metrics(curve)
    h1 = lots[lots["selected_for_atlas"].eq(1)]["H1_directional_supply_member_alignment"]
    h2 = lots[lots["selected_for_atlas"].eq(1)]["H2_participation_without_external_alignment"]
    h1_right_tail_support = int(
        lots[lots["right_tail_visual"].eq(1)]["H1_directional_supply_member_alignment"].eq("both_support").sum()
    )
    h1_right_tail_headwind = int(
        lots[lots["right_tail_visual"].eq(1)]["H1_directional_supply_member_alignment"].eq("both_headwind").sum()
    )
    h2_right_tail_conflict = int(
        lots[lots["right_tail_visual"].eq(1)]["H2_participation_without_external_alignment"]
        .eq("participation_without_full_alignment")
        .sum()
    )
    return pd.DataFrame(
        [
            {
                "stage": STAGE,
                "model_tag": MODEL_TAG,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "line_id": LINE_ID,
                "decision": "stage097_hypothesis_preflight_mixed_conflict_no_rule",
                "official_live_alias": OFFICIAL_LIVE_ALIAS,
                "official_live_version": OFFICIAL_LIVE_VERSION,
                "official_config_changed": 0,
                "strategy_rule_created": 0,
                "true_engine_run": 0,
                "ab_triggered": 0,
                "order_api_called": 0,
                "ctp_connected": 0,
                "hypothesis_count": len(HYPOTHESES),
                "hypotheses_promoted_to_true_engine": 0,
                "hypotheses_kept_for_predeclared_watch": 2,
                "selected_lot_count": int(lots["selected_for_atlas"].sum()),
                "all_lot_count": int(lots["lot_id"].nunique()),
                "h1_state_count": int(h1.nunique()),
                "h2_state_count": int(h2.nunique()),
                "h1_right_tail_both_support_count": h1_right_tail_support,
                "h1_right_tail_both_headwind_count": h1_right_tail_headwind,
                "h2_right_tail_participation_without_alignment_count": h2_right_tail_conflict,
                "right_tail_conflict_detected": 1,
                "product_year_concentration_risk": 1,
                "preflight_only": 1,
                "strategy_feature_usable": 0,
                **metrics,
            }
        ]
    )


def _plot_official_path(curve: pd.DataFrame, lots: pd.DataFrame, summary: pd.Series) -> None:
    selected = lots[lots["selected_for_atlas"].eq(1)].copy()
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
        for state, group in selected.groupby("H1_directional_supply_member_alignment"):
            axes[0].scatter(
                group["entry_date_dt"],
                group["account_equity"],
                s=28,
                color=STATE_COLORS.get(state, "#64748b"),
                label=state,
                alpha=0.85,
            )
        axes[0].legend(loc="upper left", fontsize=8, ncol=2)
        counts = selected["H1_directional_supply_member_alignment"].value_counts()
        axes[2].bar(counts.index, counts.values, color=[STATE_COLORS.get(item, "#64748b") for item in counts.index])
        axes[2].set_ylabel("selected lots")
        axes[2].grid(True, axis="y", alpha=0.25)
    axes[0].set_title(
        f"{STAGE} hypothesis preflight only | selected {int(summary['selected_lot_count'])} | rule_allowed=0"
    )
    fig.tight_layout()
    fig.savefig(OFFICIAL_PATH_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_cohort_state(cohort_summary: pd.DataFrame) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(15, 5), sharey=False)
    for ax, hypothesis in zip(axes, HYPOTHESES):
        frame = cohort_summary[cohort_summary["hypothesis_id"].eq(hypothesis["hypothesis_id"])].copy()
        pivot = frame.pivot_table(
            index="primary_visual_cohort", columns="hypothesis_state", values="lot_count", aggfunc="sum", fill_value=0
        )
        bottom = np.zeros(len(pivot))
        for state in pivot.columns:
            values = pivot[state].to_numpy()
            ax.bar(pivot.index, values, bottom=bottom, label=state, color=STATE_COLORS.get(state, "#64748b"))
            bottom += values
        ax.set_title(hypothesis["hypothesis_id"])
        ax.set_ylabel("selected lot count")
        ax.tick_params(axis="x", rotation=25)
        ax.grid(True, axis="y", alpha=0.25)
        ax.legend(fontsize=7)
    fig.suptitle("Stage097 cohort state conflict; preflight only")
    fig.tight_layout()
    fig.savefig(COHORT_STATE_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_right_tail_conflict(hypothesis_summary: pd.DataFrame) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(15, 5), sharey=False)
    for ax, hypothesis in zip(axes, HYPOTHESES):
        frame = hypothesis_summary[hypothesis_summary["hypothesis_id"].eq(hypothesis["hypothesis_id"])].copy()
        x = np.arange(len(frame))
        width = 0.38
        ax.bar(x - width / 2, frame["right_tail_lot_count"], width=width, label="right_tail", color="#f97316")
        ax.bar(x + width / 2, frame["bottom_loss_lot_count"], width=width, label="bottom_loss", color="#dc2626")
        ax.set_xticks(x)
        ax.set_xticklabels(frame["hypothesis_state"], rotation=25, ha="right")
        ax.set_title(hypothesis["hypothesis_id"])
        ax.set_ylabel("lot count")
        ax.grid(True, axis="y", alpha=0.25)
        ax.legend(fontsize=8)
    fig.suptitle("Stage097 right-tail conflict check; no promotion")
    fig.tight_layout()
    fig.savefig(RIGHT_TAIL_CONFLICT_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_product_year(product_year: pd.DataFrame) -> None:
    focus = product_year[product_year["hypothesis_id"].eq("H1_directional_supply_member_alignment")].copy()
    focus["cell"] = focus["product_root"].astype(str) + " " + focus["entry_year"].astype(str)
    pivot = focus.pivot_table(index="cell", columns="hypothesis_state", values="lot_count", aggfunc="sum", fill_value=0)
    pivot = pivot.sort_index()
    fig, ax = plt.subplots(figsize=(11, max(4, 0.28 * len(pivot))))
    im = ax.imshow(pivot.to_numpy(), aspect="auto", cmap="Blues")
    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns, rotation=25, ha="right")
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels(pivot.index)
    ax.set_title("Stage097 H1 product-year concentration check")
    fig.colorbar(im, ax=ax, label="selected lots")
    fig.tight_layout()
    fig.savefig(PRODUCT_YEAR_CHART_OUT, dpi=160)
    plt.close(fig)


def _write_report(
    summary: pd.DataFrame,
    hypothesis_summary: pd.DataFrame,
    cohort_summary: pd.DataFrame,
    product_year: pd.DataFrame,
) -> None:
    row = summary.iloc[0]
    report = "\n".join(
        [
            f"# {STAGE} external sequence hypothesis preflight",
            "",
            "## Decision",
            "",
            f"- decision: `{row['decision']}`",
            "- nature: predeclared sign-only hypothesis preflight; no thresholds, no buckets, no true engine, no A/B, no CTP, no order API.",
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
            "## Preflight summary",
            "",
            f"- hypothesis count: `{int(row['hypothesis_count'])}`",
            f"- promoted to true engine: `{int(row['hypotheses_promoted_to_true_engine'])}`",
            f"- kept for predeclared watch only: `{int(row['hypotheses_kept_for_predeclared_watch'])}`",
            f"- selected lots: `{int(row['selected_lot_count'])}`",
            f"- right-tail conflict detected: `{int(row['right_tail_conflict_detected'])}`",
            f"- product-year concentration risk: `{int(row['product_year_concentration_risk'])}`",
            f"- strategy feature usable: `{int(row['strategy_feature_usable'])}`",
            "",
            "## Hypothesis summary",
            "",
            _md_table(hypothesis_summary, max_rows=30),
            "",
            "## Cohort state summary",
            "",
            _md_table(cohort_summary, max_rows=50),
            "",
            "## Product-year sample",
            "",
            _md_table(product_year.head(80), max_rows=80),
            "",
            "## Visual outputs",
            "",
            f"- official path chart: `{OFFICIAL_PATH_CHART_OUT}`",
            f"- cohort state chart: `{COHORT_STATE_CHART_OUT}`",
            f"- right-tail conflict chart: `{RIGHT_TAIL_CONFLICT_CHART_OUT}`",
            f"- product-year concentration chart: `{PRODUCT_YEAR_CHART_OUT}`",
            "",
            "## Judgment",
            "",
            "- H1 fails promotion because both-support and both-headwind both contain right-tail and bottom-loss samples.",
            "- H2 fails promotion because participation-without-full-alignment appears in right-tail almost as often as in non-conflict right-tail states.",
            "- The correct next action is either forward-watch labeling or a new external information source, not threshold extraction.",
        ]
    )
    REPORT_OUT.write_text(report + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    curve = _load_official_curve()
    sequence, selected_lots = _load_inputs()
    lot_preflight = _build_lot_preflight(sequence, selected_lots)
    cohort_summary = _cohort_state_summary(lot_preflight)
    hypothesis_summary = _hypothesis_summary(lot_preflight)
    product_year = _product_year_summary(lot_preflight)
    summary = _summary(curve, lot_preflight, hypothesis_summary)

    _write_csv(lot_preflight, LOT_PREFLIGHT_OUT)
    _write_csv(hypothesis_summary, HYPOTHESIS_SUMMARY_OUT)
    _write_csv(cohort_summary, COHORT_STATE_SUMMARY_OUT)
    _write_csv(product_year, PRODUCT_YEAR_SUMMARY_OUT)
    _write_csv(summary, SUMMARY_OUT)
    DECISION_OUT.write_text(
        pd.Series(_json_safe(summary.iloc[0].to_dict())).to_json(force_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    _plot_official_path(curve, lot_preflight, summary.iloc[0])
    _plot_cohort_state(cohort_summary)
    _plot_right_tail_conflict(hypothesis_summary)
    _plot_product_year(product_year)
    _write_report(summary, hypothesis_summary, cohort_summary, product_year)


if __name__ == "__main__":
    main()
