from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


LINE_ID = "futures_trend_c9_minrisk_highquality"
STAGE = "Stage023"
MODEL_TAG = "stage023_active2_stress_loss_decomposition_v1"
OUTPUT_PREFIX = "qmt_roll_stage023_c9_minrisk_active2_stress_loss_decomposition"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
EXAMPLE_DIR = REPO_DIR / "examples" / "portfolio_backtesting"
if str(EXAMPLE_DIR) not in sys.path:
    sys.path.insert(0, str(EXAMPLE_DIR))

from qmt_roll_official_live_config import OFFICIAL_LIVE_ALIAS, OFFICIAL_LIVE_VERSION


LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
STAGE022_DIR = LINE_DIR / "outputs" / "stage022_path_risk_state_forensics"
OUTPUT_DIR = LINE_DIR / "outputs" / "stage023_active2_stress_loss_decomposition"

ENTRY_STATE_IN = (
    STAGE022_DIR
    / "qmt_roll_stage022_c9_minrisk_path_risk_state_forensics_entry_state_features_"
    "stage022_path_risk_state_forensics_v1.csv"
)
DAILY_STATE_IN = (
    STAGE022_DIR
    / "qmt_roll_stage022_c9_minrisk_path_risk_state_forensics_daily_state_"
    "stage022_path_risk_state_forensics_v1.csv"
)

FEATURES_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_features_{MODEL_TAG}.csv"
COHORT_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cohort_summary_{MODEL_TAG}.csv"
BUCKET_ATTR_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_bucket_attribution_{MODEL_TAG}.csv"
YEAR_PRODUCT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_year_product_matrix_{MODEL_TAG}.csv"
STRUCTURE_RATE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_structure_rates_{MODEL_TAG}.csv"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_path_contribution_chart_{MODEL_TAG}.png"
STRUCTURE_HEATMAP_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_structure_rate_heatmap_{MODEL_TAG}.png"
ACTIVE2_HEATMAP_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_active2_product_year_heatmap_{MODEL_TAG}.png"
STRESS_LOSS_HEATMAP_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_stress_loss_product_year_heatmap_{MODEL_TAG}.png"
SCATTER_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_preentry_state_scatter_{MODEL_TAG}.png"


def _json_safe(value: Any) -> Any:
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        if np.isnan(value) or np.isinf(value):
            return None
        return float(value)
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    return value


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise RuntimeError(f"missing required input: {path}")
    return pd.read_csv(path, encoding="utf-8-sig")


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_empty_"
    data = frame.copy()
    if max_rows is not None:
        data = data.head(max_rows)
    display = data.copy()
    for column in display.columns:
        if pd.api.types.is_float_dtype(display[column]):
            display[column] = display[column].map(lambda value: "" if pd.isna(value) else f"{value:.4f}")
    headers = list(display.columns)
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for _, row in display.iterrows():
        lines.append("| " + " | ".join(str(row[column]) for column in headers) + " |")
    return "\n".join(lines)


def _as_bool(series: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(series):
        return series.fillna(False)
    return series.astype(str).str.lower().isin(["true", "1", "yes", "y"])


def _safe_rate(mask: pd.Series, count: int) -> float:
    if count == 0:
        return 0.0
    return float(mask.fillna(False).sum()) / float(count) * 100.0


def _exchange_from_symbol(vt_symbol: Any, product: Any) -> str:
    text = "" if pd.isna(vt_symbol) else str(vt_symbol)
    if "." in text:
        return text.rsplit(".", 1)[-1]
    product_text = "" if pd.isna(product) else str(product)
    if "." in product_text:
        return product_text.rsplit(".", 1)[-1]
    return "missing"


def _prepare_features() -> pd.DataFrame:
    data = _read_csv(ENTRY_STATE_IN)
    for column in [
        "realized_pnl",
        "risk_amount",
        "r_multiple",
        "entry_risk_distance_pct",
        "prev_drawdown_pct",
        "prev_broker10_margin_to_equity_pct",
        "prev_rolling20_ann_vol_pct",
        "prev_c3_active_contracts",
        "selected_volume",
        "contracts_by_risk",
        "contracts_by_margin",
        "same_direction_correlation_active_count",
        "same_direction_correlation_max_corr",
    ]:
        if column in data.columns:
            data[column] = pd.to_numeric(data[column], errors="coerce")
        else:
            data[column] = np.nan

    data["entry_date"] = pd.to_datetime(data["entry_date"], errors="coerce")
    data["exit_date"] = pd.to_datetime(data["exit_date"], errors="coerce")
    data["entry_year"] = data["entry_date"].dt.year
    data["exit_day"] = data["exit_date"].dt.normalize()
    data["product_key"] = data["product"].fillna("missing").astype(str)
    data["exchange"] = [
        _exchange_from_symbol(vt_symbol, product)
        for vt_symbol, product in zip(data.get("vt_symbol", ""), data.get("product", ""))
    ]

    for column in [
        "preentry_system_stress",
        "tag_entry_open_aligned",
        "tag_first_bar_aligned",
        "tag_entry_or_first_aligned",
        "tag_ai4_6_entry_or_first_aligned",
        "stage861_covered",
    ]:
        if column in data.columns:
            data[f"{column}_bool"] = _as_bool(data[column])
        else:
            data[f"{column}_bool"] = False

    data["loss_flag"] = data["realized_pnl"] < 0.0
    data["win_flag"] = data["realized_pnl"] > 0.0
    data["active_2_flag"] = data["prev_active_bucket"].astype(str).eq("active_2")
    data["stress_flag"] = data["preentry_system_stress_bool"]
    data["active2_loss_flag"] = data["active_2_flag"] & data["loss_flag"]
    data["stress_loss_flag"] = data["stress_flag"] & data["loss_flag"]
    data["active2_stress_loss_flag"] = data["active_2_flag"] & data["stress_flag"] & data["loss_flag"]
    data["margin_cap_binding_flag"] = (
        data["contracts_by_margin"].notna()
        & data["contracts_by_risk"].notna()
        & (data["contracts_by_margin"] < data["contracts_by_risk"])
    )
    data["same_dir_corr_high_flag"] = (
        data["same_direction_correlation_active_count"].fillna(0.0).ge(1.0)
        & data["same_direction_correlation_max_corr"].fillna(0.0).gt(0.60)
    )
    data["long_flag"] = data["direction"].astype(str).eq("long")
    data["risk_distance_available_flag"] = data["entry_risk_distance_pct"].notna()
    data["loss_tag_note"] = np.where(
        data["loss_flag"],
        "future_outcome_label_for_forensics_only",
        "not_loss_or_unlabeled",
    )
    return data


def _prepare_daily_state() -> pd.DataFrame:
    data = _read_csv(DAILY_STATE_IN)
    data["date"] = pd.to_datetime(data["date"], errors="coerce")
    data = data.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    for column in [
        "account_equity",
        "drawdown_pct",
        "broker10_margin_to_equity_pct",
        "c3_active_contracts",
    ]:
        if column in data.columns:
            data[column] = pd.to_numeric(data[column], errors="coerce").fillna(0.0)
        else:
            data[column] = 0.0
    return data


def _cohort_masks(data: pd.DataFrame) -> dict[str, pd.Series]:
    true = pd.Series(True, index=data.index)
    return {
        "all_lots": true,
        "active_2_all": data["active_2_flag"],
        "active_2_loss_future_label": data["active2_loss_flag"],
        "active_2_win": data["active_2_flag"] & data["win_flag"],
        "stress_all": data["stress_flag"],
        "stress_loss_future_label": data["stress_loss_flag"],
        "stress_win": data["stress_flag"] & data["win_flag"],
        "active2_stress_loss_future_label": data["active2_stress_loss_flag"],
        "non_active2_nonstress": (~data["active_2_flag"]) & (~data["stress_flag"]),
    }


def _negative_concentration(group: pd.DataFrame, key: str) -> tuple[float, float]:
    losses = group[group["realized_pnl"] < 0.0].copy()
    total_loss_abs = float((-losses["realized_pnl"]).sum())
    if total_loss_abs <= 0.0:
        return 0.0, 0.0
    by_key = (-losses.groupby(key)["realized_pnl"].sum()).sort_values(ascending=False)
    top1 = float(by_key.head(1).sum()) / total_loss_abs * 100.0
    top3 = float(by_key.head(3).sum()) / total_loss_abs * 100.0
    return top1, top3


def _cohort_summary(data: pd.DataFrame) -> pd.DataFrame:
    total_positive = float(data.loc[data["realized_pnl"] > 0.0, "realized_pnl"].sum())
    total_negative_abs = float((-data.loc[data["realized_pnl"] < 0.0, "realized_pnl"]).sum())
    rows: list[dict[str, Any]] = []
    for name, mask in _cohort_masks(data).items():
        group = data[mask].copy()
        lot_count = int(len(group))
        positive_pnl = float(group.loc[group["realized_pnl"] > 0.0, "realized_pnl"].sum())
        negative_abs = float((-group.loc[group["realized_pnl"] < 0.0, "realized_pnl"]).sum())
        yearly = group.groupby("entry_year")["realized_pnl"].sum().dropna()
        top1_product_loss_share, top3_product_loss_share = _negative_concentration(group, "product_key")
        top1_year_loss_share, top3_year_loss_share = _negative_concentration(group, "entry_year")
        rows.append(
            {
                "cohort": name,
                "lot_count": lot_count,
                "product_count": int(group["product_key"].nunique()) if lot_count else 0,
                "exchange_count": int(group["exchange"].nunique()) if lot_count else 0,
                "year_count": int(group["entry_year"].nunique()) if lot_count else 0,
                "net_pnl": float(group["realized_pnl"].sum()),
                "positive_pnl": positive_pnl,
                "negative_pnl_abs": negative_abs,
                "positive_coverage_pct": positive_pnl / total_positive * 100.0 if total_positive else 0.0,
                "negative_coverage_pct": negative_abs / total_negative_abs * 100.0 if total_negative_abs else 0.0,
                "positive_year_count": int((yearly > 0.0).sum()),
                "negative_year_count": int((yearly < 0.0).sum()),
                "entry_or_first_aligned_rate_pct": _safe_rate(group["tag_entry_or_first_aligned_bool"], lot_count),
                "ai4_6_entry_or_first_aligned_rate_pct": _safe_rate(
                    group["tag_ai4_6_entry_or_first_aligned_bool"], lot_count
                ),
                "margin_cap_binding_rate_pct": _safe_rate(group["margin_cap_binding_flag"], lot_count),
                "same_dir_corr_high_rate_pct": _safe_rate(group["same_dir_corr_high_flag"], lot_count),
                "stage861_covered_rate_pct": _safe_rate(group["stage861_covered_bool"], lot_count),
                "long_rate_pct": _safe_rate(group["long_flag"], lot_count),
                "mean_prev_drawdown_pct": float(group["prev_drawdown_pct"].mean()) if lot_count else 0.0,
                "mean_prev_broker10_pct": float(group["prev_broker10_margin_to_equity_pct"].mean())
                if lot_count
                else 0.0,
                "mean_prev_roll20_vol_pct": float(group["prev_rolling20_ann_vol_pct"].mean()) if lot_count else 0.0,
                "mean_risk_distance_pct": float(group["entry_risk_distance_pct"].mean()) if lot_count else 0.0,
                "top1_product_loss_share_pct": top1_product_loss_share,
                "top3_product_loss_share_pct": top3_product_loss_share,
                "top1_year_loss_share_pct": top1_year_loss_share,
                "top3_year_loss_share_pct": top3_year_loss_share,
                "future_outcome_label_used": "loss" in name,
            }
        )
    return pd.DataFrame(rows)


def _bucket_attribution(data: pd.DataFrame) -> pd.DataFrame:
    bucket_columns = [
        "prev_active_bucket",
        "prev_drawdown_bucket",
        "prev_broker_bucket",
        "prev_vol_bucket",
        "entry_open_relation_bucket",
        "first_bar_relation_bucket",
        "direction",
        "exchange",
        "risk_mode",
        "risk_multiplier_bucket",
        "coverage_bucket",
        "same_direction_active_bucket",
    ]
    rows: list[dict[str, Any]] = []
    total_positive = float(data.loc[data["realized_pnl"] > 0.0, "realized_pnl"].sum())
    total_negative_abs = float((-data.loc[data["realized_pnl"] < 0.0, "realized_pnl"]).sum())
    for cohort, mask in _cohort_masks(data).items():
        group = data[mask].copy()
        for column in bucket_columns:
            if column not in group.columns:
                continue
            filled = group[column].fillna("missing").astype(str)
            for value, sub_index in filled.groupby(filled).groups.items():
                sub = group.loc[list(sub_index)]
                positive = float(sub.loc[sub["realized_pnl"] > 0.0, "realized_pnl"].sum())
                negative_abs = float((-sub.loc[sub["realized_pnl"] < 0.0, "realized_pnl"]).sum())
                rows.append(
                    {
                        "cohort": cohort,
                        "bucket_column": column,
                        "bucket_value": value,
                        "lot_count": int(len(sub)),
                        "net_pnl": float(sub["realized_pnl"].sum()),
                        "positive_pnl": positive,
                        "negative_pnl_abs": negative_abs,
                        "positive_coverage_pct": positive / total_positive * 100.0 if total_positive else 0.0,
                        "negative_coverage_pct": negative_abs / total_negative_abs * 100.0
                        if total_negative_abs
                        else 0.0,
                        "year_count": int(sub["entry_year"].nunique()),
                        "product_count": int(sub["product_key"].nunique()),
                    }
                )
    return pd.DataFrame(rows).sort_values(["cohort", "bucket_column", "net_pnl"]).reset_index(drop=True)


def _year_product_matrix(data: pd.DataFrame) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    for cohort, mask in _cohort_masks(data).items():
        group = data[mask].copy()
        if group.empty:
            continue
        pivot = (
            group.groupby(["product_key", "entry_year"])["realized_pnl"]
            .sum()
            .reset_index()
            .assign(cohort=cohort)
        )
        rows.append(pivot)
    if not rows:
        return pd.DataFrame(columns=["cohort", "product_key", "entry_year", "realized_pnl"])
    return pd.concat(rows, ignore_index=True)[["cohort", "product_key", "entry_year", "realized_pnl"]]


def _structure_rates(summary: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "entry_or_first_aligned_rate_pct",
        "ai4_6_entry_or_first_aligned_rate_pct",
        "margin_cap_binding_rate_pct",
        "same_dir_corr_high_rate_pct",
        "stage861_covered_rate_pct",
        "long_rate_pct",
    ]
    rates = summary[["cohort", *columns]].copy()
    return rates


def _cumulative_lot_pnl_by_exit(data: pd.DataFrame, daily: pd.DataFrame, mask: pd.Series) -> pd.Series:
    group = data[mask & data["exit_day"].notna()].copy()
    pnl_by_day = group.groupby("exit_day")["realized_pnl"].sum()
    index = pd.DatetimeIndex(daily["date"].dt.normalize())
    series = pnl_by_day.reindex(index, fill_value=0.0).cumsum()
    series.index = daily["date"].values
    return series


def _plot_path_contribution(data: pd.DataFrame, daily: pd.DataFrame) -> None:
    masks = _cohort_masks(data)
    fig, axes = plt.subplots(3, 1, figsize=(14, 11), sharex=True, gridspec_kw={"height_ratios": [2.0, 1.2, 1.0]})
    axes[0].plot(daily["date"], daily["account_equity"], color="#2563eb", linewidth=1.5, label="official equity")
    axes[0].set_yscale("log")
    axes[0].set_ylabel("equity log")
    axes[0].grid(True, alpha=0.25)
    axes[0].legend(loc="upper left")

    colors = {
        "active_2_all": "#dc2626",
        "stress_all": "#ea580c",
        "active_2_loss_future_label": "#7f1d1d",
        "stress_loss_future_label": "#9a3412",
        "non_active2_nonstress": "#16a34a",
    }
    for cohort in [
        "active_2_all",
        "stress_all",
        "active_2_loss_future_label",
        "stress_loss_future_label",
        "non_active2_nonstress",
    ]:
        series = _cumulative_lot_pnl_by_exit(data, daily, masks[cohort])
        axes[1].plot(series.index, series.values, linewidth=1.25, label=cohort, color=colors[cohort])
    axes[1].axhline(0.0, color="#111827", linewidth=0.8)
    axes[1].set_ylabel("closed-lot cumulative pnl")
    axes[1].grid(True, alpha=0.25)
    axes[1].legend(loc="upper left", ncol=2, fontsize=8)

    axes[2].plot(daily["date"], daily["drawdown_pct"], color="#334155", linewidth=1.1, label="official drawdown")
    axes[2].plot(
        daily["date"],
        daily["broker10_margin_to_equity_pct"],
        color="#9333ea",
        linewidth=0.9,
        alpha=0.8,
        label="broker10 pct",
    )
    axes[2].axhline(-40.0, color="#dc2626", linestyle="--", linewidth=0.8)
    axes[2].axhline(100.0, color="#9333ea", linestyle="--", linewidth=0.8)
    axes[2].set_ylabel("pct")
    axes[2].grid(True, alpha=0.25)
    axes[2].legend(loc="lower left", ncol=2, fontsize=8)
    fig.suptitle("Stage023 official path and forensic cohort contribution")
    fig.tight_layout(rect=[0, 0, 1, 0.97])
    fig.savefig(PATH_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_structure_heatmap(rates: pd.DataFrame) -> None:
    display = rates.set_index("cohort")
    preferred_rows = [
        "all_lots",
        "active_2_all",
        "active_2_loss_future_label",
        "stress_all",
        "stress_loss_future_label",
        "active2_stress_loss_future_label",
        "non_active2_nonstress",
    ]
    display = display.reindex([row for row in preferred_rows if row in display.index])
    values = display.to_numpy(dtype=float)
    fig, ax = plt.subplots(figsize=(13, 6))
    image = ax.imshow(values, aspect="auto", cmap="RdYlGn", vmin=0.0, vmax=100.0)
    ax.set_yticks(np.arange(len(display.index)))
    ax.set_yticklabels(display.index, fontsize=8)
    ax.set_xticks(np.arange(len(display.columns)))
    ax.set_xticklabels([column.replace("_rate_pct", "") for column in display.columns], rotation=35, ha="right", fontsize=8)
    for y in range(values.shape[0]):
        for x in range(values.shape[1]):
            ax.text(x, y, f"{values[y, x]:.1f}", ha="center", va="center", fontsize=7, color="#111827")
    ax.set_title("Stage023 structure rates by cohort")
    fig.colorbar(image, ax=ax, fraction=0.025, pad=0.02, label="rate pct")
    fig.tight_layout()
    fig.savefig(STRUCTURE_HEATMAP_OUT, dpi=160)
    plt.close(fig)


def _plot_product_year_heatmap(data: pd.DataFrame, cohort_name: str, mask: pd.Series, output: Path, title: str) -> None:
    group = data[mask].copy()
    if group.empty:
        return
    product_order = (
        group.groupby("product_key")["realized_pnl"]
        .sum()
        .abs()
        .sort_values(ascending=False)
        .head(12)
        .index.tolist()
    )
    pivot = (
        group[group["product_key"].isin(product_order)]
        .pivot_table(index="product_key", columns="entry_year", values="realized_pnl", aggfunc="sum", fill_value=0.0)
        .reindex(product_order)
    )
    values = pivot.to_numpy(dtype=float)
    vmax = max(float(np.nanmax(np.abs(values))), 1.0)
    fig, ax = plt.subplots(figsize=(12, 7))
    image = ax.imshow(values, aspect="auto", cmap="RdBu", vmin=-vmax, vmax=vmax)
    ax.set_yticks(np.arange(len(pivot.index)))
    ax.set_yticklabels(pivot.index, fontsize=8)
    ax.set_xticks(np.arange(len(pivot.columns)))
    ax.set_xticklabels([str(int(column)) for column in pivot.columns], fontsize=8)
    for y in range(values.shape[0]):
        for x in range(values.shape[1]):
            if abs(values[y, x]) >= vmax * 0.08:
                ax.text(x, y, f"{values[y, x]/10000:.0f}w", ha="center", va="center", fontsize=7, color="#111827")
    ax.set_title(f"{title} ({cohort_name})")
    fig.colorbar(image, ax=ax, fraction=0.025, pad=0.02, label="net pnl")
    fig.tight_layout()
    fig.savefig(output, dpi=160)
    plt.close(fig)


def _plot_scatter(data: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(11, 7))
    base = data.copy()
    colors = np.where(base["active2_loss_flag"], "#7f1d1d", np.where(base["stress_loss_flag"], "#ea580c", "#94a3b8"))
    sizes = np.clip(np.abs(base["realized_pnl"]) / 5000.0, 10.0, 260.0)
    ax.scatter(
        base["prev_drawdown_pct"],
        base["prev_broker10_margin_to_equity_pct"],
        s=sizes,
        c=colors,
        alpha=0.62,
        edgecolor="white",
        linewidth=0.4,
    )
    ax.axvline(-20.0, color="#dc2626", linestyle="--", linewidth=0.8)
    ax.axvline(-30.0, color="#dc2626", linestyle=":", linewidth=0.8)
    ax.axhline(90.0, color="#9333ea", linestyle="--", linewidth=0.8)
    ax.set_xlabel("previous day drawdown pct")
    ax.set_ylabel("previous day broker10 margin/equity pct")
    ax.set_title("Stage023 pre-entry state scatter; size = abs closed-lot pnl")
    ax.grid(True, alpha=0.25)
    handles = [
        plt.Line2D([0], [0], marker="o", color="w", markerfacecolor="#7f1d1d", markersize=8, label="active_2 loss"),
        plt.Line2D([0], [0], marker="o", color="w", markerfacecolor="#ea580c", markersize=8, label="stress loss"),
        plt.Line2D([0], [0], marker="o", color="w", markerfacecolor="#94a3b8", markersize=8, label="other"),
    ]
    ax.legend(handles=handles, loc="upper left")
    fig.tight_layout()
    fig.savefig(SCATTER_OUT, dpi=160)
    plt.close(fig)


def _top_negative_product_year(data: pd.DataFrame, mask: pd.Series, limit: int = 10) -> pd.DataFrame:
    group = data[mask].copy()
    if group.empty:
        return pd.DataFrame()
    out = (
        group.groupby(["product_key", "entry_year"])["realized_pnl"]
        .sum()
        .sort_values()
        .head(limit)
        .reset_index()
    )
    return out


def _write_report(
    data: pd.DataFrame,
    daily: pd.DataFrame,
    summary: pd.DataFrame,
    bucket_attr: pd.DataFrame,
    year_product: pd.DataFrame,
    structure_rates: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    masks = _cohort_masks(data)
    active2_year = (
        data[masks["active_2_all"]].groupby("entry_year")["realized_pnl"].sum().reset_index().sort_values("entry_year")
    )
    stress_loss_year = (
        data[masks["stress_loss_future_label"]]
        .groupby("entry_year")["realized_pnl"]
        .sum()
        .reset_index()
        .sort_values("entry_year")
    )
    active2_top_neg = _top_negative_product_year(data, masks["active_2_all"], 12)
    stress_loss_top_neg = _top_negative_product_year(data, masks["stress_loss_future_label"], 12)
    active2_buckets = bucket_attr[
        bucket_attr["cohort"].eq("active_2_all")
        & bucket_attr["bucket_column"].isin(
            ["entry_open_relation_bucket", "first_bar_relation_bucket", "direction", "exchange"]
        )
    ].sort_values("net_pnl")
    stress_loss_buckets = bucket_attr[
        bucket_attr["cohort"].eq("stress_loss_future_label")
        & bucket_attr["bucket_column"].isin(
            ["entry_open_relation_bucket", "first_bar_relation_bucket", "direction", "exchange"]
        )
    ].sort_values("net_pnl")

    lines = [
        f"# {STAGE} active_2 / stress_loss 二级只读拆解",
        "",
        f"- line_id：`{LINE_ID}`",
        f"- 当前官方版本：`{OFFICIAL_LIVE_VERSION}` / `{OFFICIAL_LIVE_ALIAS}`",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`",
        "- 阶段性质：只读法证；`loss` cohort 使用未来结果标签，只能解释失败结构，不能作为实时规则。",
        "- 候选状态：`candidate_ready=0`，不改正式配置、不连接 CTP、不调用订单 API。",
        "",
        "## 核心结论",
        "",
        f"- 决策：`{decision['decision']}`。",
        f"- `active_2_all` 净 PnL `{decision['active2_all_net_pnl']:.2f}`，"
        f"但负年 `{decision['active2_negative_year_count']}` 个、正年 `{decision['active2_positive_year_count']}` 个，"
        "不是单调风险状态。",
        f"- `stress_loss` 是未来亏损标签，亏损集中度高：top1 年亏损占 `{decision['stress_loss_top1_year_loss_share_pct']:.4f}%`，"
        f"top3 产品亏损占 `{decision['stress_loss_top3_product_loss_share_pct']:.4f}%`。",
        "- 入场结构没有形成一个可交易的共同形状；aligned、ai4/6 aligned、同向相关、margin cap binding 都不足以把坏样本从右尾中干净切出来。",
        "",
        "## cohort 摘要",
        "",
        _md_table(
            summary[
                [
                    "cohort",
                    "lot_count",
                    "product_count",
                    "year_count",
                    "net_pnl",
                    "positive_coverage_pct",
                    "negative_coverage_pct",
                    "positive_year_count",
                    "negative_year_count",
                    "entry_or_first_aligned_rate_pct",
                    "ai4_6_entry_or_first_aligned_rate_pct",
                    "margin_cap_binding_rate_pct",
                    "same_dir_corr_high_rate_pct",
                    "top3_product_loss_share_pct",
                    "top1_year_loss_share_pct",
                ]
            ]
        ),
        "",
        "## active_2 年度 PnL",
        "",
        _md_table(active2_year),
        "",
        "## stress_loss 年度 PnL",
        "",
        _md_table(stress_loss_year),
        "",
        "## active_2 最差产品-年份",
        "",
        _md_table(active2_top_neg),
        "",
        "## stress_loss 最差产品-年份",
        "",
        _md_table(stress_loss_top_neg),
        "",
        "## active_2 入场结构/方向/交易所桶",
        "",
        _md_table(active2_buckets.head(20)),
        "",
        "## stress_loss 入场结构/方向/交易所桶",
        "",
        _md_table(stress_loss_buckets.head(20)),
        "",
        "## 输出文件",
        "",
        f"- features：`{FEATURES_OUT}`",
        f"- cohort summary：`{COHORT_SUMMARY_OUT}`",
        f"- bucket attribution：`{BUCKET_ATTR_OUT}`",
        f"- year product matrix：`{YEAR_PRODUCT_OUT}`",
        f"- structure rates：`{STRUCTURE_RATE_OUT}`",
        f"- path contribution chart：`{PATH_CHART_OUT}`",
        f"- structure heatmap：`{STRUCTURE_HEATMAP_OUT}`",
        f"- active2 product-year heatmap：`{ACTIVE2_HEATMAP_OUT}`",
        f"- stress loss product-year heatmap：`{STRESS_LOSS_HEATMAP_OUT}`",
        f"- pre-entry scatter：`{SCATTER_OUT}`",
        f"- decision：`{DECISION_OUT}`",
        "",
        "## 视觉判断",
        "",
        "- path contribution chart 显示，`active_2_loss` 与 `stress_loss` 的红/橙亏损曲线不是稳定提前下行的风险覆盖层，而是集中在若干压力段和产品簇。",
        "- product-year heatmap 显示 `active_2` 的净亏主要来自 `2022` 与 `2025` 的少数产品-年份块；`stress_loss` 更集中在 `2022`。",
        "- structure heatmap 显示亏损 cohort 仍有相当比例的 aligned、same-dir/cap 状态，不能用一个入场结构标签简单切断。",
        "- scatter 显示前一日 drawdown/broker10 空间中亏损点与其他点混杂；粗压力状态不是坏信号充分条件。",
        "",
        "## 后续边界",
        "",
        "- 停止把 `active_2`、`stress_loss`、`2022` 产品簇或任一产品/方向写成交易规则。",
        "- 若继续，本路线应转向真正外生、入场前可见且不依赖最终盈亏标签的风险源；或者只做 forward watch，不再从历史亏损 cohort 反推规则。",
    ]
    REPORT_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    data = _prepare_features()
    daily = _prepare_daily_state()
    summary = _cohort_summary(data)
    bucket_attr = _bucket_attribution(data)
    year_product = _year_product_matrix(data)
    structure_rates = _structure_rates(summary)

    masks = _cohort_masks(data)
    active2 = summary[summary["cohort"].eq("active_2_all")].iloc[0].to_dict()
    stress_loss = summary[summary["cohort"].eq("stress_loss_future_label")].iloc[0].to_dict()
    active2_loss = summary[summary["cohort"].eq("active_2_loss_future_label")].iloc[0].to_dict()
    stress_all = summary[summary["cohort"].eq("stress_all")].iloc[0].to_dict()

    decision = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "candidate_ready": 0,
        "ab_triggered": 0,
        "decision": "stage023_active2_stress_loss_no_candidate_concentrated_nonmonotonic_future_label",
        "reason": [
            "active_2_all is negative but non-monotonic across adjacent active-count states and has both positive and negative years.",
            "stress_all was positive in Stage022; stress_loss uses future outcome labels and cannot become a live rule.",
            "loss concentration is dominated by a few product-year blocks, especially 2022/2025 for active_2 and 2022 for stress_loss.",
            "entry-open/first-bar alignment, same-direction correlation, and margin-cap binding do not form a clean cross-year universal bad-signal structure.",
        ],
        "active2_all_net_pnl": active2["net_pnl"],
        "active2_all_lot_count": active2["lot_count"],
        "active2_positive_year_count": active2["positive_year_count"],
        "active2_negative_year_count": active2["negative_year_count"],
        "active2_loss_net_pnl": active2_loss["net_pnl"],
        "active2_loss_top3_product_loss_share_pct": active2_loss["top3_product_loss_share_pct"],
        "active2_loss_top1_year_loss_share_pct": active2_loss["top1_year_loss_share_pct"],
        "stress_all_net_pnl": stress_all["net_pnl"],
        "stress_loss_net_pnl": stress_loss["net_pnl"],
        "stress_loss_lot_count": stress_loss["lot_count"],
        "stress_loss_top3_product_loss_share_pct": stress_loss["top3_product_loss_share_pct"],
        "stress_loss_top1_year_loss_share_pct": stress_loss["top1_year_loss_share_pct"],
        "output_files": {
            "features": FEATURES_OUT,
            "cohort_summary": COHORT_SUMMARY_OUT,
            "bucket_attribution": BUCKET_ATTR_OUT,
            "year_product_matrix": YEAR_PRODUCT_OUT,
            "structure_rates": STRUCTURE_RATE_OUT,
            "report": REPORT_OUT,
            "path_contribution_chart": PATH_CHART_OUT,
            "structure_heatmap": STRUCTURE_HEATMAP_OUT,
            "active2_product_year_heatmap": ACTIVE2_HEATMAP_OUT,
            "stress_loss_product_year_heatmap": STRESS_LOSS_HEATMAP_OUT,
            "preentry_state_scatter": SCATTER_OUT,
        },
    }

    data.to_csv(FEATURES_OUT, index=False, encoding="utf-8-sig")
    summary.to_csv(COHORT_SUMMARY_OUT, index=False, encoding="utf-8-sig")
    bucket_attr.to_csv(BUCKET_ATTR_OUT, index=False, encoding="utf-8-sig")
    year_product.to_csv(YEAR_PRODUCT_OUT, index=False, encoding="utf-8-sig")
    structure_rates.to_csv(STRUCTURE_RATE_OUT, index=False, encoding="utf-8-sig")
    DECISION_OUT.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    _plot_path_contribution(data, daily)
    _plot_structure_heatmap(structure_rates)
    _plot_product_year_heatmap(
        data,
        "active_2_all",
        masks["active_2_all"],
        ACTIVE2_HEATMAP_OUT,
        "Stage023 active_2 product-year net pnl",
    )
    _plot_product_year_heatmap(
        data,
        "stress_loss_future_label",
        masks["stress_loss_future_label"],
        STRESS_LOSS_HEATMAP_OUT,
        "Stage023 stress_loss product-year net pnl",
    )
    _plot_scatter(data)
    _write_report(data, daily, summary, bucket_attr, year_product, structure_rates, decision)

    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
