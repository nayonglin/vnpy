from __future__ import annotations

from datetime import datetime
import json
import math
from pathlib import Path
from typing import Any, Callable
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


LINE_ID = "futures_trend_c9_minrisk_highquality"
STAGE = "Stage016"
MODEL_TAG = "stage016_intersection_stability_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage016_c9_minrisk_intersection_stability_audit"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
TOOL_DIR = SCRIPT_PATH.parent
EXAMPLE_DIR = REPO_DIR / "examples" / "portfolio_backtesting"
for item in [str(TOOL_DIR), str(EXAMPLE_DIR)]:
    if item not in sys.path:
        sys.path.insert(0, item)

import stage015_preentry_structure_attribution as s015
from qmt_roll_official_live_config import OFFICIAL_LIVE_ALIAS, OFFICIAL_LIVE_VERSION


LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage016_intersection_stability_audit"
STAGE010_DIR = LINE_DIR / "outputs" / "stage010_authoritative_minute_coverage_audit"
STAGE015_DIR = LINE_DIR / "outputs" / "stage015_preentry_structure_attribution"

CAPITAL = 150_000.0
PER_PAGE = 4
MAX_ATLAS_ROWS = 20

FEATURES_IN = (
    STAGE015_DIR
    / "qmt_roll_stage015_c9_minrisk_preentry_structure_attribution_features_stage015_preentry_structure_attribution_v1.csv"
)
CURVE_IN = (
    STAGE010_DIR
    / "qmt_roll_stage010_c9_minrisk_authoritative_minute_coverage_audit_official_curve_stage010_authoritative_minute_coverage_audit_v1.csv"
)

FEATURES_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_features_{MODEL_TAG}.csv"
STATS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_intersection_stats_{MODEL_TAG}.csv"
YEAR_STATS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_intersection_year_stats_{MODEL_TAG}.csv"
PAIR_MATRIX_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_pair_matrix_{MODEL_TAG}.csv"
SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_intersection_path_chart_{MODEL_TAG}.png"
STABILITY_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_intersection_stability_scatter_{MODEL_TAG}.png"
HEATMAP_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_intersection_year_heatmap_{MODEL_TAG}.png"
ATLAS_MANIFEST_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_atlas_manifest_{MODEL_TAG}.csv"
ATLAS_TEMPLATE = OUTPUT_DIR / f"{OUTPUT_PREFIX}_atlas_page{{page:03d}}_{MODEL_TAG}.png"


def _json_safe(value: Any) -> Any:
    return s015._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s015._md_table(frame, max_rows=max_rows)


def _safe_float(value: Any, default: float = np.nan) -> float:
    return s015._safe_float(value, default=default)


def _normalize_day(value: Any) -> pd.Timestamp:
    return s015._normalize_day(value)


def _read_required_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise RuntimeError(f"missing required input: {path}")
    return pd.read_csv(path, encoding="utf-8-sig")


def _ensure_numeric(data: pd.DataFrame, columns: list[str]) -> None:
    for column in columns:
        if column in data.columns:
            data[column] = pd.to_numeric(data[column], errors="coerce")


def _prepare_features() -> pd.DataFrame:
    data = _read_required_csv(FEATURES_IN)
    _ensure_numeric(
        data,
        [
            "realized_pnl",
            "positive_pnl",
            "negative_pnl",
            "r_multiple",
            "winner",
            "big_winner",
            "entry_year",
            "stage014_delta_allocated_to_lot",
            "stage014_delta_candidate_minus_official",
            "stage014_event_index",
            "entry_price",
            "risk_for_entry_instant",
            "first_bar_directional_r",
            "entry_open_gap_r",
            "first_30m_directional_r",
            "first_30m_mae_r",
        ],
    )
    data["entry_day"] = data["entry_date"].map(_normalize_day)
    data["exit_day"] = data["exit_date"].map(_normalize_day)
    if "positive_pnl" not in data.columns:
        data["positive_pnl"] = data["realized_pnl"].clip(lower=0.0).fillna(0.0)
    if "negative_pnl" not in data.columns:
        data["negative_pnl"] = data["realized_pnl"].clip(upper=0.0).fillna(0.0)
    for column in [
        "ai_rank_bucket",
        "entry_open_relation_bucket",
        "first_bar_relation_bucket",
        "entry_context",
        "risk_multiplier_bucket",
        "rsi_bucket",
        "coverage_bucket",
        "stage014_state_group",
    ]:
        if column not in data.columns:
            data[column] = "missing"
        data[column] = data[column].fillna("missing").astype(str)
    return data


def _tag_definitions() -> list[tuple[str, str, Callable[[pd.DataFrame], pd.Series]]]:
    return [
        (
            "ai_rank_4_6",
            "Stage015 right-tail asymmetry bucket: ai_rank_bucket == rank_4_6.",
            lambda df: df["ai_rank_bucket"].eq("rank_4_6"),
        ),
        (
            "entry_open_aligned",
            "Entry-day first minute open is already aligned with official direction.",
            lambda df: df["entry_open_relation_bucket"].eq("entry_open_aligned"),
        ),
        (
            "first_bar_aligned",
            "First entry-day minute close is aligned with official direction.",
            lambda df: df["first_bar_relation_bucket"].eq("first_bar_aligned"),
        ),
        (
            "entry_or_first_aligned",
            "Either entry open or first minute close is aligned.",
            lambda df: df["entry_open_relation_bucket"].eq("entry_open_aligned")
            | df["first_bar_relation_bucket"].eq("first_bar_aligned"),
        ),
        (
            "entry_and_first_aligned",
            "Both entry open and first minute close are aligned.",
            lambda df: df["entry_open_relation_bucket"].eq("entry_open_aligned")
            & df["first_bar_relation_bucket"].eq("first_bar_aligned"),
        ),
        (
            "ai4_6_entry_open_aligned",
            "ai_rank_4_6 AND entry_open_aligned.",
            lambda df: df["ai_rank_bucket"].eq("rank_4_6")
            & df["entry_open_relation_bucket"].eq("entry_open_aligned"),
        ),
        (
            "ai4_6_first_bar_aligned",
            "ai_rank_4_6 AND first_bar_aligned.",
            lambda df: df["ai_rank_bucket"].eq("rank_4_6")
            & df["first_bar_relation_bucket"].eq("first_bar_aligned"),
        ),
        (
            "ai4_6_entry_or_first_aligned",
            "ai_rank_4_6 AND (entry_open_aligned OR first_bar_aligned).",
            lambda df: df["ai_rank_bucket"].eq("rank_4_6")
            & (
                df["entry_open_relation_bucket"].eq("entry_open_aligned")
                | df["first_bar_relation_bucket"].eq("first_bar_aligned")
            ),
        ),
        (
            "ai4_6_entry_and_first_aligned",
            "ai_rank_4_6 AND entry_open_aligned AND first_bar_aligned.",
            lambda df: df["ai_rank_bucket"].eq("rank_4_6")
            & df["entry_open_relation_bucket"].eq("entry_open_aligned")
            & df["first_bar_relation_bucket"].eq("first_bar_aligned"),
        ),
        (
            "ai4_6_not_aligned",
            "ai_rank_4_6 but neither entry open nor first minute close is aligned.",
            lambda df: df["ai_rank_bucket"].eq("rank_4_6")
            & ~(
                df["entry_open_relation_bucket"].eq("entry_open_aligned")
                | df["first_bar_relation_bucket"].eq("first_bar_aligned")
            ),
        ),
        (
            "aligned_not_ai4_6",
            "Entry/first-minute aligned but not ai_rank_4_6.",
            lambda df: ~df["ai_rank_bucket"].eq("rank_4_6")
            & (
                df["entry_open_relation_bucket"].eq("entry_open_aligned")
                | df["first_bar_relation_bucket"].eq("first_bar_aligned")
            ),
        ),
        (
            "not_ai4_6_or_not_aligned",
            "Complement of ai4_6_entry_or_first_aligned.",
            lambda df: ~(
                df["ai_rank_bucket"].eq("rank_4_6")
                & (
                    df["entry_open_relation_bucket"].eq("entry_open_aligned")
                    | df["first_bar_relation_bucket"].eq("first_bar_aligned")
                )
            ),
        ),
    ]


def _add_tags(data: pd.DataFrame) -> pd.DataFrame:
    data = data.copy()
    for name, _description, fn in _tag_definitions():
        data[f"tag_{name}"] = fn(data).fillna(False).astype(bool)
    return data


def _intersection_year_stats(features: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for name, description, _fn in _tag_definitions():
        tag = f"tag_{name}"
        group = features[features[tag]].copy()
        for year, yearly in group.groupby("entry_year", dropna=False):
            rows.append(
                {
                    "tag": name,
                    "description": description,
                    "entry_year": int(year) if pd.notna(year) else np.nan,
                    "events": int(len(yearly)),
                    "products": int(yearly["product"].astype(str).nunique()),
                    "official_pnl": float(yearly["realized_pnl"].fillna(0.0).sum()),
                    "positive_pnl": float(yearly["positive_pnl"].fillna(0.0).sum()),
                    "negative_pnl": float(yearly["negative_pnl"].fillna(0.0).sum()),
                    "big_winner_count": int(pd.to_numeric(yearly["big_winner"], errors="coerce").fillna(0.0).sum()),
                    "stage014_delta_sum": float(
                        pd.to_numeric(yearly["stage014_delta_allocated_to_lot"], errors="coerce")
                        .fillna(0.0)
                        .sum()
                    ),
                }
            )
    return pd.DataFrame(rows)


def _intersection_stats(features: pd.DataFrame, year_stats: pd.DataFrame) -> pd.DataFrame:
    total_lots = max(1, int(len(features)))
    total_pnl = float(features["realized_pnl"].fillna(0.0).sum())
    total_positive = float(features["positive_pnl"].fillna(0.0).sum())
    total_negative_abs = float(abs(features["negative_pnl"].fillna(0.0).sum()))
    total_stage014_delta = float(
        pd.to_numeric(features["stage014_delta_allocated_to_lot"], errors="coerce").fillna(0.0).sum()
    )
    rows: list[dict[str, Any]] = []
    for name, description, _fn in _tag_definitions():
        tag = f"tag_{name}"
        group = features[features[tag]].copy()
        yearly = year_stats[year_stats["tag"].eq(name)].copy()
        pnl = float(group["realized_pnl"].fillna(0.0).sum())
        positive = float(group["positive_pnl"].fillna(0.0).sum())
        negative = float(group["negative_pnl"].fillna(0.0).sum())
        stage014_delta = float(
            pd.to_numeric(group["stage014_delta_allocated_to_lot"], errors="coerce").fillna(0.0).sum()
        )
        negative_delta = float(
            pd.to_numeric(group["stage014_delta_allocated_to_lot"], errors="coerce").fillna(0.0).clip(upper=0.0).sum()
        )
        positive_capture = positive / total_positive * 100.0 if abs(total_positive) > 1e-9 else np.nan
        negative_capture = abs(negative) / total_negative_abs * 100.0 if total_negative_abs > 1e-9 else np.nan
        rows.append(
            {
                "tag": name,
                "description": description,
                "events": int(len(group)),
                "event_share_pct": float(len(group) / total_lots * 100.0),
                "products": int(group["product"].astype(str).nunique()) if not group.empty else 0,
                "years": int(group["entry_year"].nunique()) if not group.empty else 0,
                "official_pnl": pnl,
                "net_pnl_share_pct": pnl / total_pnl * 100.0 if abs(total_pnl) > 1e-9 else np.nan,
                "positive_pnl": positive,
                "negative_pnl": negative,
                "positive_pnl_capture_pct": positive_capture,
                "negative_pnl_capture_pct": negative_capture,
                "positive_minus_negative_capture_pp": positive_capture - negative_capture,
                "median_r_multiple": float(pd.to_numeric(group["r_multiple"], errors="coerce").median())
                if not group.empty
                else np.nan,
                "win_rate_pct": float(pd.to_numeric(group["winner"], errors="coerce").fillna(0.0).mean() * 100.0)
                if not group.empty
                else np.nan,
                "big_winner_count": int(pd.to_numeric(group["big_winner"], errors="coerce").fillna(0.0).sum())
                if not group.empty
                else 0,
                "big_winner_pnl": float(
                    group.loc[
                        pd.to_numeric(group["big_winner"], errors="coerce").fillna(0.0) > 0, "realized_pnl"
                    ].sum()
                )
                if not group.empty
                else 0.0,
                "positive_years": int((yearly["official_pnl"] > 0).sum()) if not yearly.empty else 0,
                "negative_years": int((yearly["official_pnl"] < 0).sum()) if not yearly.empty else 0,
                "min_year_pnl": float(yearly["official_pnl"].min()) if not yearly.empty else np.nan,
                "max_year_pnl": float(yearly["official_pnl"].max()) if not yearly.empty else np.nan,
                "stage014_matched_lot_count": int(
                    pd.to_numeric(group["stage014_delta_allocated_to_lot"], errors="coerce").notna().sum()
                )
                if not group.empty
                else 0,
                "stage014_unique_event_count": int(
                    pd.to_numeric(group["stage014_event_index"], errors="coerce").dropna().nunique()
                )
                if not group.empty
                else 0,
                "stage014_delta_sum": stage014_delta,
                "stage014_negative_delta_sum": negative_delta,
                "stage014_delta_share_of_all_pct": stage014_delta / total_stage014_delta * 100.0
                if abs(total_stage014_delta) > 1e-9
                else np.nan,
                "broad_enough_for_attribution": int(len(group) >= 20 and group["product"].astype(str).nunique() >= 8 and group["entry_year"].nunique() >= 5)
                if not group.empty
                else 0,
            }
        )
    stats = pd.DataFrame(rows)
    stats["all_years_positive"] = (stats["positive_years"].eq(stats["years"]) & stats["years"].gt(0)).astype(int)
    stats["loss_sparse"] = (pd.to_numeric(stats["negative_pnl_capture_pct"], errors="coerce") <= 15.0).astype(int)
    stats["right_tail_asymmetry_ge10pp"] = (
        pd.to_numeric(stats["positive_minus_negative_capture_pp"], errors="coerce") >= 10.0
    ).astype(int)
    stats["read_only_stable_signal_shape"] = (
        stats["broad_enough_for_attribution"].eq(1)
        & stats["all_years_positive"].eq(1)
        & stats["right_tail_asymmetry_ge10pp"].eq(1)
    ).astype(int)
    stats["trade_rule_ready"] = 0
    stats["trade_rule_blocker"] = np.where(
        stats["tag"].eq("not_ai4_6_or_not_aligned"),
        "complement captures most positive and most negative pnl; reducing it would be a broad right-tail cut",
        np.where(
            stats["events"] < 30,
            "sample is small for a live rule; keep as read-only or forward-watch label",
            "historical bucket still captures material losses and lacks true-engine A/C validation",
        ),
    )
    return stats.sort_values(
        ["read_only_stable_signal_shape", "positive_minus_negative_capture_pp", "official_pnl"],
        ascending=[False, False, False],
    ).reset_index(drop=True)


def _pair_matrix(features: pd.DataFrame) -> pd.DataFrame:
    base_tags = [
        "ai_rank_4_6",
        "entry_open_aligned",
        "first_bar_aligned",
        "entry_or_first_aligned",
        "ai4_6_entry_or_first_aligned",
    ]
    rows: list[dict[str, Any]] = []
    for left in base_tags:
        left_mask = features[f"tag_{left}"]
        for right in base_tags:
            right_mask = features[f"tag_{right}"]
            group = features[left_mask & right_mask]
            rows.append(
                {
                    "left_tag": left,
                    "right_tag": right,
                    "events": int(len(group)),
                    "products": int(group["product"].astype(str).nunique()) if not group.empty else 0,
                    "years": int(group["entry_year"].nunique()) if not group.empty else 0,
                    "official_pnl": float(group["realized_pnl"].fillna(0.0).sum()) if not group.empty else 0.0,
                    "negative_pnl": float(group["negative_pnl"].fillna(0.0).sum()) if not group.empty else 0.0,
                }
            )
    return pd.DataFrame(rows)


def _plot_path_chart(curve: pd.DataFrame, features: pd.DataFrame, stats: pd.DataFrame) -> None:
    curve = curve.copy()
    curve["date"] = pd.to_datetime(curve["date"], errors="coerce")
    curve = curve.dropna(subset=["date"]).sort_values("date")
    features = features.copy()
    features["exit_day"] = features["exit_day"].map(_normalize_day)
    fig, axes = plt.subplots(3, 1, figsize=(18, 13), sharex=False, constrained_layout=True)

    axes[0].plot(curve["date"], curve["account_equity"], color="#2563eb", linewidth=1.2, label="Official C9/15w equity")
    marker_rows = (
        features[pd.to_numeric(features["stage014_delta_allocated_to_lot"], errors="coerce").fillna(0.0) < 0]
        .sort_values("stage014_delta_allocated_to_lot")
        .head(14)
    )
    for _, row in marker_rows.iterrows():
        axes[0].axvline(row["entry_day"], color="#dc2626", alpha=0.18, linewidth=0.9)
    axes[0].set_title("Official equity path with Stage013 missed-right-tail lot markers")
    axes[0].legend(loc="best")
    axes[0].grid(True, alpha=0.2)

    if "drawdown_pct" in curve.columns:
        axes[1].plot(curve["date"], curve["drawdown_pct"], color="#0f766e", linewidth=1.0, label="Official drawdown pct")
        axes[1].axhline(-40, color="#dc2626", linestyle="--", linewidth=0.8, alpha=0.65)
        axes[1].axhline(-50, color="#7f1d1d", linestyle="--", linewidth=0.8, alpha=0.65)
        axes[1].set_title("Official drawdown")
        axes[1].legend(loc="best")
        axes[1].grid(True, alpha=0.2)
    else:
        axes[1].axis("off")

    plot_tags = [
        "ai_rank_4_6",
        "entry_or_first_aligned",
        "ai4_6_entry_or_first_aligned",
        "not_ai4_6_or_not_aligned",
    ]
    colors = {
        "ai_rank_4_6": "#7c3aed",
        "entry_or_first_aligned": "#0891b2",
        "ai4_6_entry_or_first_aligned": "#16a34a",
        "not_ai4_6_or_not_aligned": "#dc2626",
    }
    for tag in plot_tags:
        group = features[features[f"tag_{tag}"]].dropna(subset=["exit_day"]).sort_values("exit_day")
        if group.empty:
            continue
        series = group.groupby("exit_day")["realized_pnl"].sum().sort_index().cumsum()
        axes[2].plot(series.index, series.values, linewidth=1.15, color=colors.get(tag), label=tag)
    axes[2].axhline(0, color="#334155", linewidth=0.8)
    axes[2].set_title("Read-only closed-lot contribution curves for predeclared intersections")
    axes[2].legend(loc="best", fontsize=8)
    axes[2].grid(True, alpha=0.2)
    fig.savefig(PATH_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_stability_scatter(stats: pd.DataFrame) -> None:
    data = stats.copy()
    x = pd.to_numeric(data["positive_pnl_capture_pct"], errors="coerce")
    y = pd.to_numeric(data["negative_pnl_capture_pct"], errors="coerce")
    size = np.clip(pd.to_numeric(data["events"], errors="coerce").fillna(1.0), 1, 140) * 7
    c = pd.to_numeric(data["years"], errors="coerce").fillna(0.0)
    fig, ax = plt.subplots(figsize=(14, 9), constrained_layout=True)
    scatter = ax.scatter(x, y, s=size, c=c, cmap="viridis", alpha=0.78, edgecolor="#334155", linewidth=0.4)
    upper = max(float(np.nanmax(x)) if len(x) else 1.0, float(np.nanmax(y)) if len(y) else 1.0, 1.0)
    ax.plot([0, upper], [0, upper], color="#64748b", linestyle="--", linewidth=0.9)
    for _, row in data.iterrows():
        ax.annotate(
            str(row["tag"]),
            (row["positive_pnl_capture_pct"], row["negative_pnl_capture_pct"]),
            fontsize=7,
            xytext=(4, 4),
            textcoords="offset points",
        )
    ax.set_xlabel("Positive PnL captured (%)")
    ax.set_ylabel("Absolute negative PnL captured (%)")
    ax.set_title("Intersection stability: right-tail capture vs loss capture")
    ax.grid(True, alpha=0.2)
    fig.colorbar(scatter, ax=ax, label="Years covered")
    fig.savefig(STABILITY_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_year_heatmap(year_stats: pd.DataFrame, stats: pd.DataFrame) -> None:
    selected_tags = [
        "ai_rank_4_6",
        "entry_or_first_aligned",
        "ai4_6_entry_or_first_aligned",
        "ai4_6_not_aligned",
        "aligned_not_ai4_6",
        "not_ai4_6_or_not_aligned",
    ]
    data = year_stats[year_stats["tag"].isin(selected_tags)].copy()
    if data.empty:
        return
    pivot = data.pivot_table(index="tag", columns="entry_year", values="official_pnl", aggfunc="sum").reindex(selected_tags)
    fig, ax = plt.subplots(figsize=(16, 7), constrained_layout=True)
    values = pivot.fillna(0.0).values
    limit = np.nanpercentile(np.abs(values), 95) if values.size else 1.0
    limit = max(1.0, float(limit))
    im = ax.imshow(values, cmap="RdYlGn", aspect="auto", vmin=-limit, vmax=limit)
    ax.set_xticks(np.arange(len(pivot.columns)))
    ax.set_xticklabels([str(int(col)) for col in pivot.columns], rotation=45, ha="right", fontsize=8)
    ax.set_yticks(np.arange(len(pivot.index)))
    ax.set_yticklabels(pivot.index, fontsize=8)
    for i in range(values.shape[0]):
        for j in range(values.shape[1]):
            text = f"{values[i, j] / 1_000_000:.1f}m" if abs(values[i, j]) >= 100_000 else f"{values[i, j] / 1_000:.0f}k"
            ax.text(j, i, text, ha="center", va="center", fontsize=6, color="#0f172a")
    ax.set_title("Yearly official PnL by predeclared intersection tags")
    fig.colorbar(im, ax=ax, label="Official realized PnL")
    fig.savefig(HEATMAP_CHART_OUT, dpi=170)
    plt.close(fig)


def _select_atlas_rows(features: pd.DataFrame) -> pd.DataFrame:
    target = features[features["tag_ai4_6_entry_or_first_aligned"]].copy()
    frames: list[pd.DataFrame] = []
    if not target.empty:
        frames.append(target.sort_values("realized_pnl", ascending=False).head(5).assign(atlas_reason="intersection_top_winners"))
        frames.append(target.sort_values("realized_pnl").head(5).assign(atlas_reason="intersection_losses"))
        frames.append(
            target.sort_values("stage014_delta_allocated_to_lot").head(5).assign(atlas_reason="intersection_stage013_missed")
        )
    complement = features[~features["tag_ai4_6_entry_or_first_aligned"]].copy()
    if not complement.empty:
        frames.append(
            complement.sort_values("realized_pnl", ascending=False)
            .head(6)
            .assign(atlas_reason="outside_intersection_top_winners")
        )
    if not frames:
        return pd.DataFrame()
    selected = pd.concat(frames, ignore_index=True, sort=False)
    return selected.drop_duplicates(["vt_symbol", "entry_date", "direction"]).head(MAX_ATLAS_ROWS)


def _direction_sign(direction: Any) -> int:
    return -1 if str(direction).lower() == "short" else 1


def _plot_atlas(features: pd.DataFrame) -> tuple[list[Path], pd.DataFrame]:
    selected = _select_atlas_rows(features)
    if selected.empty:
        return [], pd.DataFrame()
    vt_symbols = sorted(selected["vt_symbol"].astype(str).dropna().unique())
    minute_bars = s015.s010.s008.s928._load_stage861_full_minute_bars(vt_symbols)
    minute_by_symbol = s015.s010.s008.s825._minute_groups(minute_bars)
    pages = int(math.ceil(len(selected) / PER_PAGE))
    paths: list[Path] = []
    manifest_rows: list[dict[str, Any]] = []
    for page in range(1, pages + 1):
        part = selected.iloc[(page - 1) * PER_PAGE : page * PER_PAGE].copy()
        fig, axes = plt.subplots(len(part), 1, figsize=(18, max(4.2, 3.5 * len(part))), constrained_layout=True)
        axes_list = list(np.atleast_1d(axes))
        for ax, (_, row) in zip(axes_list, part.iterrows(), strict=False):
            vt_symbol = str(row["vt_symbol"])
            entry_day = _normalize_day(row["entry_date"])
            bars = minute_by_symbol.get(vt_symbol, pd.DataFrame())
            day = (
                bars[bars["bar_date"].eq(entry_day)].copy().sort_values("bar_datetime").head(520).reset_index(drop=True)
                if not bars.empty
                else pd.DataFrame()
            )
            if day.empty:
                ax.axis("off")
                ax.text(0.5, 0.5, f"missing minute bars\n{vt_symbol} {entry_day:%Y-%m-%d}", ha="center", va="center")
            else:
                s015.s010.s008.s825._plot_candles(ax, day)
                entry = _safe_float(row.get("entry_price"))
                risk = _safe_float(row.get("risk_for_entry_instant"))
                sign = _direction_sign(row.get("direction"))
                levels = [("entry", entry, "#2563eb", "-")]
                if np.isfinite(entry) and np.isfinite(risk) and risk > 0:
                    levels.extend(
                        [
                            ("+0.5R", entry + sign * 0.5 * risk, "#16a34a", "--"),
                            ("-0.5R", entry - sign * 0.5 * risk, "#dc2626", ":"),
                        ]
                    )
                for label, price, color, linestyle in levels:
                    if np.isfinite(price):
                        ax.axhline(price, color=color, linestyle=linestyle, linewidth=0.9, label=label)
                if len(day) > 0:
                    ax.axvline(0, color="#0f172a", linewidth=0.9, alpha=0.8, label="first bar")
                if len(day) > 30:
                    ax.axvline(29, color="#64748b", linewidth=0.9, alpha=0.75, label="30m")
                ticks = np.linspace(0, len(day) - 1, num=min(8, len(day)), dtype=int)
                ax.set_xticks(ticks)
                ax.set_xticklabels([pd.Timestamp(day.loc[pos, "bar_datetime"]).strftime("%H:%M") for pos in ticks], fontsize=7)
                handles, labels = ax.get_legend_handles_labels()
                if handles:
                    dedup = dict(zip(labels, handles))
                    ax.legend(dedup.values(), dedup.keys(), loc="best", fontsize=7)
                ax.grid(True, alpha=0.18)
            ax.set_title(
                (
                    f"{row.get('atlas_reason')} | {vt_symbol} {row.get('direction')} {entry_day:%Y-%m-%d} "
                    f"pnl={_safe_float(row.get('realized_pnl'), 0):,.0f} "
                    f"ai={row.get('ai_rank_bucket')} entry={row.get('entry_open_relation_bucket')} "
                    f"first={row.get('first_bar_relation_bucket')} "
                    f"delta={_safe_float(row.get('stage014_delta_allocated_to_lot'), 0):,.0f}"
                ),
                fontsize=8.2,
                loc="left",
            )
            manifest_rows.append(
                {
                    "page": page,
                    "atlas_reason": row.get("atlas_reason", ""),
                    "vt_symbol": vt_symbol,
                    "entry_date": entry_day.strftime("%Y-%m-%d"),
                    "direction": row.get("direction", ""),
                    "realized_pnl": _safe_float(row.get("realized_pnl")),
                    "stage014_delta_allocated_to_lot": _safe_float(row.get("stage014_delta_allocated_to_lot")),
                    "ai_rank_bucket": row.get("ai_rank_bucket", ""),
                    "entry_open_relation_bucket": row.get("entry_open_relation_bucket", ""),
                    "first_bar_relation_bucket": row.get("first_bar_relation_bucket", ""),
                    "tag_ai4_6_entry_or_first_aligned": bool(row.get("tag_ai4_6_entry_or_first_aligned", False)),
                }
            )
        fig.suptitle("Stage016 intersection stability minute-K atlas", fontsize=12)
        path = Path(str(ATLAS_TEMPLATE).format(page=page))
        fig.savefig(path, dpi=170)
        plt.close(fig)
        paths.append(path)
    return paths, pd.DataFrame(manifest_rows)


def _summary(features: pd.DataFrame, stats: pd.DataFrame, pair_matrix: pd.DataFrame) -> dict[str, Any]:
    best = stats[stats["tag"].eq("ai4_6_entry_or_first_aligned")].head(1).to_dict("records")
    complement = stats[stats["tag"].eq("not_ai4_6_or_not_aligned")].head(1).to_dict("records")
    stable_shapes = stats[stats["read_only_stable_signal_shape"].eq(1)].copy()
    return {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "official_live_alias": OFFICIAL_LIVE_ALIAS,
        "official_lots": int(len(features)),
        "total_official_realized_pnl": float(features["realized_pnl"].fillna(0.0).sum()),
        "total_positive_pnl": float(features["positive_pnl"].fillna(0.0).sum()),
        "total_negative_pnl": float(features["negative_pnl"].fillna(0.0).sum()),
        "tag_count": int(len(stats)),
        "read_only_stable_signal_shape_count": int(len(stable_shapes)),
        "primary_intersection": best[0] if best else {},
        "primary_complement": complement[0] if complement else {},
        "entry_open_first_bar_same_event_count": int(
            len(
                features[
                    features["entry_open_relation_bucket"].eq("entry_open_aligned")
                    & features["first_bar_relation_bucket"].eq("first_bar_aligned")
                ]
            )
        ),
        "entry_or_first_aligned_event_count": int(features["tag_entry_or_first_aligned"].sum()),
        "decision": "stage016_intersection_stability_readonly_no_trade_rule",
    }


def _decision(summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "official_live_alias": OFFICIAL_LIVE_ALIAS,
        "decision": "stage016_intersection_stability_readonly_no_trade_rule",
        "summary": summary,
        "order_api_called": False,
        "ctp_connected": False,
        "external_research_judgment": (
            "Current trend-following references emphasize robust time-scale selection, diversification, "
            "leverage/risk controls, and full account curves. They do not justify converting a small "
            "historical entry-time intersection into a live rule without true-engine validation."
        ),
        "overfit_reflection_before": (
            "No: intersections are predeclared from Stage015 and are used only for attribution, not for a new branch."
        ),
        "continue_value_before": (
            "Yes: Stage015's strongest labels need a stability check before deciding whether the entry-structure route lives."
        ),
        "overfit_reflection_after": (
            "No trade rule is selected. Promoting the 24-lot primary intersection into a sizing rule would overfit."
        ),
        "continue_value_after": (
            "Limited. The primary intersection is stable as a right-tail protection tag, but too small and too label-like "
            "to support default minimum-risk sizing. Continue only with forward-watch or pivot to account-layer external sleeves."
        ),
        "outputs": {
            "features": str(FEATURES_OUT),
            "intersection_stats": str(STATS_OUT),
            "intersection_year_stats": str(YEAR_STATS_OUT),
            "pair_matrix": str(PAIR_MATRIX_OUT),
            "summary": str(SUMMARY_OUT),
            "path_chart": str(PATH_CHART_OUT),
            "stability_chart": str(STABILITY_CHART_OUT),
            "heatmap_chart": str(HEATMAP_CHART_OUT),
            "atlas_manifest": str(ATLAS_MANIFEST_OUT),
            "report": str(REPORT_OUT),
            "decision": str(DECISION_OUT),
        },
    }


def _write_report(
    summary: dict[str, Any],
    stats: pd.DataFrame,
    year_stats: pd.DataFrame,
    pair_matrix: pd.DataFrame,
    atlas_paths: list[Path],
) -> None:
    primary = stats[stats["tag"].eq("ai4_6_entry_or_first_aligned")]
    stable = stats[stats["read_only_stable_signal_shape"].eq(1)].copy()
    report = "\n".join(
        [
            "# Stage016 intersection stability audit",
            "",
            f"- generated_at: `{datetime.now():%Y-%m-%d %H:%M}`",
            f"- line_id: `{LINE_ID}`",
            f"- official: `{OFFICIAL_LIVE_VERSION}` / `{OFFICIAL_LIVE_ALIAS}`",
            "- type: read-only intersection stability audit; no trading rule, no CTP, no order API.",
            "- decision: `stage016_intersection_stability_readonly_no_trade_rule`",
            "",
            "## External Research Judgment",
            "",
            "- Recent trend-following references emphasize robust time-scale alignment, diversification, and leverage-sensitive risk controls.",
            "- Open-source systematic futures projects such as pysystemtrade and PyTrendFollow emphasize isolated configuration, full backtest/account curves, and production discipline.",
            "- Judgment: a small historical intersection can be a protection label, but it is not enough to define a universal minimum-risk entry rule.",
            "",
            "## Summary",
            "",
            _md_table(pd.DataFrame([summary])),
            "",
            "## Intersection Stats",
            "",
            _md_table(stats, max_rows=20),
            "",
            "## Primary Intersection",
            "",
            _md_table(primary, max_rows=5),
            "",
            "## Read-Only Stable Signal Shapes",
            "",
            _md_table(stable, max_rows=20),
            "",
            "## Pair Matrix",
            "",
            _md_table(pair_matrix, max_rows=30),
            "",
            "## Visual Outputs",
            "",
            f"- path chart: `{PATH_CHART_OUT}`",
            f"- stability scatter: `{STABILITY_CHART_OUT}`",
            f"- year heatmap: `{HEATMAP_CHART_OUT}`",
            *[f"- minute atlas: `{path}`" for path in atlas_paths],
            "",
            "## Judgment",
            "",
            "- overfit_reflection_before: `No: predeclared intersections only.`",
            "- overfit_reflection_after: `No trade rule selected; using this as a live sizing rule would overfit.`",
            "- continue_value_before: `Yes: Stage015 labels needed a cross-stability audit.`",
            "- continue_value_after: `Limited: keep as forward-watch/protection label, but stop entry-structure true-engine unless new evidence appears.`",
        ]
    )
    REPORT_OUT.write_text(report, encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print("[stage016] loading Stage015 features and official curve", flush=True)
    features = _add_tags(_prepare_features())
    curve = _read_required_csv(CURVE_IN)

    print("[stage016] computing intersection stability", flush=True)
    year_stats = _intersection_year_stats(features)
    stats = _intersection_stats(features, year_stats)
    pair_matrix = _pair_matrix(features)
    summary = _summary(features, stats, pair_matrix)
    decision = _decision(summary)

    print("[stage016] plotting path, stability chart, heatmap, and atlas", flush=True)
    _plot_path_chart(curve, features, stats)
    _plot_stability_scatter(stats)
    _plot_year_heatmap(year_stats, stats)
    atlas_paths, atlas_manifest = _plot_atlas(features)

    features.to_csv(FEATURES_OUT, index=False, encoding="utf-8-sig")
    stats.to_csv(STATS_OUT, index=False, encoding="utf-8-sig")
    year_stats.to_csv(YEAR_STATS_OUT, index=False, encoding="utf-8-sig")
    pair_matrix.to_csv(PAIR_MATRIX_OUT, index=False, encoding="utf-8-sig")
    pd.DataFrame([summary]).to_csv(SUMMARY_OUT, index=False, encoding="utf-8-sig")
    atlas_manifest.to_csv(ATLAS_MANIFEST_OUT, index=False, encoding="utf-8-sig")
    DECISION_OUT.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(summary, stats, year_stats, pair_matrix, atlas_paths)

    print(json.dumps(_json_safe(summary), ensure_ascii=False, indent=2), flush=True)
    print(f"[stage016] wrote {OUTPUT_DIR}", flush=True)


if __name__ == "__main__":
    main()
