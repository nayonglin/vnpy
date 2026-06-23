from __future__ import annotations

from datetime import datetime
import json
import math
from pathlib import Path
from typing import Any
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


LINE_ID = "futures_trend_c9_minrisk_highquality"
STAGE = "Stage018"
MODEL_TAG = "stage018_quality_conditioned_risk_shave_proxy_v1"
OUTPUT_PREFIX = "qmt_roll_stage018_c9_minrisk_quality_conditioned_risk_shave_proxy"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
TOOL_DIR = SCRIPT_PATH.parent
EXAMPLE_DIR = REPO_DIR / "examples" / "portfolio_backtesting"
for item in [str(TOOL_DIR), str(EXAMPLE_DIR)]:
    if item not in sys.path:
        sys.path.insert(0, item)

import stage013_minrisk_clean_restore_true_engine as s013
import stage015_preentry_structure_attribution as s015
from qmt_roll_official_live_config import OFFICIAL_LIVE_ALIAS, OFFICIAL_LIVE_VERSION


LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage018_quality_conditioned_risk_shave_proxy"
STAGE010_DIR = LINE_DIR / "outputs" / "stage010_authoritative_minute_coverage_audit"
STAGE012_DIR = LINE_DIR / "outputs" / "stage012_risk_invalid_repair_forensics"
STAGE016_DIR = LINE_DIR / "outputs" / "stage016_intersection_stability_audit"

CAPITAL = 150_000.0
TRADING_DAYS_PER_YEAR = 252
LOW_QUALITY_WEIGHT = 0.80
PER_PAGE = 4
MAX_ATLAS_ROWS = 24

CURVE_IN = (
    STAGE010_DIR
    / "qmt_roll_stage010_c9_minrisk_authoritative_minute_coverage_audit_official_curve_stage010_authoritative_minute_coverage_audit_v1.csv"
)
SUMMARY_IN = (
    STAGE010_DIR
    / "qmt_roll_stage010_c9_minrisk_authoritative_minute_coverage_audit_summary_stage010_authoritative_minute_coverage_audit_v1.csv"
)
FEATURES_IN = (
    STAGE016_DIR
    / "qmt_roll_stage016_c9_minrisk_intersection_stability_audit_features_stage016_intersection_stability_audit_v1.csv"
)
REPAIRED_FEATURES_IN = (
    STAGE012_DIR
    / "qmt_roll_stage012_c9_minrisk_risk_invalid_repair_forensics_features_repaired_quality_stage012_risk_invalid_repair_forensics_v1.csv"
)

FEATURES_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_features_{MODEL_TAG}.csv"
DAILY_WEIGHTS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_weights_{MODEL_TAG}.csv"
CURVES_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv"
METRICS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_metrics_{MODEL_TAG}.csv"
YEAR_STATS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_year_stats_{MODEL_TAG}.csv"
SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_path_drawdown_chart_{MODEL_TAG}.png"
WEIGHT_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_weight_share_chart_{MODEL_TAG}.png"
SCATTER_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_return_drawdown_scatter_{MODEL_TAG}.png"
YEAR_HEATMAP_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_year_return_heatmap_{MODEL_TAG}.png"
ATLAS_MANIFEST_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_atlas_manifest_{MODEL_TAG}.csv"
ATLAS_TEMPLATE = OUTPUT_DIR / f"{OUTPUT_PREFIX}_atlas_page{{page:03d}}_{MODEL_TAG}.png"


POLICIES: list[dict[str, Any]] = [
    {
        "variant": "A_official_c9_15w",
        "policy_type": "official",
        "description": "Official C9/15w path; no quality-conditioned risk shave.",
    },
    {
        "variant": "fixed80_global_reference",
        "policy_type": "fixed_daily_weight",
        "description": "Global fixed 80% official daily risk reference.",
    },
    {
        "variant": "no_follow_30m_low_quality_80",
        "policy_type": "quality_conditioned_daily_proxy",
        "low_share_column": "active_share_no_follow_30m",
        "description": "Only active risk from repaired no_follow_30m lots receives 80% daily risk weight.",
    },
    {
        "variant": "entry_unaligned_low_quality_80",
        "policy_type": "quality_conditioned_daily_proxy",
        "low_share_column": "active_share_entry_unaligned",
        "description": "Active risk outside entry_or_first_aligned receives 80% daily risk weight.",
    },
    {
        "variant": "combined_low_quality_80",
        "policy_type": "quality_conditioned_daily_proxy",
        "low_share_column": "active_share_combined_low_quality",
        "description": "Active risk that is no_follow_30m OR entry-unaligned receives 80% daily risk weight.",
    },
    {
        "variant": "strict_hq_only_full_else80",
        "policy_type": "quality_conditioned_daily_proxy",
        "low_share_column": "active_share_not_strict_hq",
        "description": "Only ai_rank_4_6 AND entry/first-minute aligned active risk keeps full weight; all other active risk receives 80%.",
    },
]


def _json_safe(value: Any) -> Any:
    return s013._json_safe(value)


def _safe_float(value: Any, default: float = np.nan) -> float:
    return s013._safe_float(value, default=default)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s013._md_table(frame, max_rows=max_rows)


def _read_required_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise RuntimeError(f"missing required input: {path}")
    return pd.read_csv(path, encoding="utf-8-sig")


def _normalize_day(value: Any) -> pd.Timestamp:
    ts = pd.to_datetime(value, errors="coerce", format="mixed")
    if pd.isna(ts):
        return pd.NaT
    ts = pd.Timestamp(ts)
    if ts.tzinfo is not None:
        ts = ts.tz_localize(None)
    return ts.normalize()


def _drawdown_pct(equity: pd.Series) -> pd.Series:
    hwm = equity.cummax()
    return (equity / hwm - 1.0) * 100.0


def _sharpe_from_equity(equity: pd.Series) -> float:
    returns = equity.pct_change().replace([np.inf, -np.inf], np.nan).dropna()
    if returns.empty or returns.std(ddof=0) <= 1e-12:
        return np.nan
    return float(returns.mean() / returns.std(ddof=0) * np.sqrt(TRADING_DAYS_PER_YEAR))


def _ulcer_pct(drawdown_pct: pd.Series) -> float:
    dd = pd.to_numeric(drawdown_pct, errors="coerce").fillna(0.0).clip(upper=0.0)
    return float(np.sqrt(np.mean(np.square(dd))))


def _prepare_official_curve() -> pd.DataFrame:
    data = _read_required_csv(CURVE_IN)
    data["date"] = pd.to_datetime(data["date"], errors="coerce")
    data = data.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    for column in [
        "net_pnl",
        "account_equity",
        "drawdown_pct",
        "broker10_total_margin_exact",
        "broker10_margin_to_equity_pct",
        "slippage",
        "trade_count",
    ]:
        if column in data.columns:
            data[column] = pd.to_numeric(data[column], errors="coerce").fillna(0.0)
        else:
            data[column] = 0.0
    return data


def _prepare_features() -> pd.DataFrame:
    data = _read_required_csv(FEATURES_IN)
    repaired = _read_required_csv(REPAIRED_FEATURES_IN)
    keep = [
        "lot_id",
        "repair_quality_label",
        "repair_first_30m_directional_r",
        "repair_first_30m_mae_r",
        "repair_plan_fill_gap_r",
    ]
    repaired = repaired[[column for column in keep if column in repaired.columns]].copy()
    data = data.merge(repaired, on="lot_id", how="left", suffixes=("", "_stage012"))

    data["entry_day"] = data["entry_date"].map(_normalize_day)
    data["exit_day"] = data["exit_date"].map(_normalize_day)
    for column in ["realized_pnl", "positive_pnl", "negative_pnl", "risk_amount", "volume", "size", "stop_distance"]:
        if column in data.columns:
            data[column] = pd.to_numeric(data[column], errors="coerce")
    data["risk_base"] = pd.to_numeric(data.get("risk_amount"), errors="coerce").abs()
    fallback = (
        pd.to_numeric(data.get("volume"), errors="coerce").abs()
        * pd.to_numeric(data.get("size"), errors="coerce").abs()
        * pd.to_numeric(data.get("stop_distance"), errors="coerce").abs()
    )
    data.loc[~np.isfinite(data["risk_base"]) | (data["risk_base"] <= 0), "risk_base"] = fallback
    data.loc[~np.isfinite(data["risk_base"]) | (data["risk_base"] <= 0), "risk_base"] = 1.0

    if "repair_quality_label" not in data.columns:
        data["repair_quality_label"] = "missing"
    data["repair_quality_label"] = data["repair_quality_label"].fillna("missing").astype(str)
    for column in ["tag_entry_or_first_aligned", "tag_ai4_6_entry_or_first_aligned"]:
        if column not in data.columns:
            data[column] = False
        data[column] = data[column].fillna(False).astype(bool)

    data["is_no_follow_30m"] = data["repair_quality_label"].eq("no_follow_30m")
    data["is_entry_unaligned"] = ~data["tag_entry_or_first_aligned"]
    data["is_combined_low_quality"] = data["is_no_follow_30m"] | data["is_entry_unaligned"]
    data["is_strict_hq"] = data["tag_ai4_6_entry_or_first_aligned"]
    data["is_not_strict_hq"] = ~data["is_strict_hq"]
    data["positive_pnl"] = pd.to_numeric(data["realized_pnl"], errors="coerce").clip(lower=0.0).fillna(0.0)
    data["negative_pnl"] = pd.to_numeric(data["realized_pnl"], errors="coerce").clip(upper=0.0).fillna(0.0)
    return data


def _active_share(active: pd.DataFrame, mask_column: str) -> float:
    if active.empty:
        return 0.0
    total = pd.to_numeric(active["risk_base"], errors="coerce").fillna(0.0).sum()
    if total <= 1e-12:
        return 0.0
    low = pd.to_numeric(active.loc[active[mask_column].fillna(False), "risk_base"], errors="coerce").fillna(0.0).sum()
    return float(np.clip(low / total, 0.0, 1.0))


def _daily_active_weights(official: pd.DataFrame, features: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    valid = features.dropna(subset=["entry_day", "exit_day"]).copy()
    for date in pd.to_datetime(official["date"], errors="coerce"):
        day = pd.Timestamp(date).normalize()
        active = valid[(valid["entry_day"] <= day) & (valid["exit_day"] >= day)].copy()
        active_risk = float(pd.to_numeric(active["risk_base"], errors="coerce").fillna(0.0).sum()) if not active.empty else 0.0
        rows.append(
            {
                "date": day,
                "active_lot_count": int(len(active)),
                "active_risk_base": active_risk,
                "active_share_no_follow_30m": _active_share(active, "is_no_follow_30m"),
                "active_share_entry_unaligned": _active_share(active, "is_entry_unaligned"),
                "active_share_combined_low_quality": _active_share(active, "is_combined_low_quality"),
                "active_share_not_strict_hq": _active_share(active, "is_not_strict_hq"),
                "active_share_strict_hq": _active_share(active, "is_strict_hq"),
            }
        )
    weights = pd.DataFrame(rows)
    for policy in POLICIES:
        variant = str(policy["variant"])
        if policy["policy_type"] == "official":
            weights[f"risk_weight_{variant}"] = 1.0
        elif policy["policy_type"] == "fixed_daily_weight":
            weights[f"risk_weight_{variant}"] = LOW_QUALITY_WEIGHT
        else:
            share = pd.to_numeric(weights[str(policy["low_share_column"])], errors="coerce").fillna(0.0)
            weights[f"risk_weight_{variant}"] = 1.0 - (1.0 - LOW_QUALITY_WEIGHT) * share
    return weights


def _simulate_curves(official: pd.DataFrame, weights: pd.DataFrame) -> pd.DataFrame:
    base = official.copy()
    base["date"] = pd.to_datetime(base["date"], errors="coerce").dt.normalize()
    weights = weights.copy()
    weights["date"] = pd.to_datetime(weights["date"], errors="coerce").dt.normalize()
    data = base.merge(weights, on="date", how="left")
    curves: list[pd.DataFrame] = []
    for policy in POLICIES:
        variant = str(policy["variant"])
        risk_weight = pd.to_numeric(data[f"risk_weight_{variant}"], errors="coerce").fillna(1.0)
        out = data.copy()
        out["variant"] = variant
        out["policy_type"] = str(policy["policy_type"])
        out["description"] = str(policy["description"])
        out["risk_weight"] = risk_weight
        out["scaled_net_pnl"] = pd.to_numeric(out["net_pnl"], errors="coerce").fillna(0.0) * risk_weight
        out["overlay_equity"] = CAPITAL + out["scaled_net_pnl"].cumsum()
        out["overlay_nav"] = out["overlay_equity"] / CAPITAL
        out["overlay_drawdown_pct"] = _drawdown_pct(out["overlay_equity"])
        out["scaled_broker10_margin_exact"] = (
            pd.to_numeric(out["broker10_total_margin_exact"], errors="coerce").fillna(0.0) * risk_weight
        )
        out["scaled_broker10_margin_to_equity_pct"] = np.where(
            out["overlay_equity"] > 0,
            out["scaled_broker10_margin_exact"] / out["overlay_equity"] * 100.0,
            np.nan,
        )
        out["scaled_slippage"] = pd.to_numeric(out["slippage"], errors="coerce").fillna(0.0) * risk_weight
        curves.append(out)
    return pd.concat(curves, ignore_index=True, sort=False)


def _metrics(curves: pd.DataFrame, official_metrics: dict[str, float]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    official_return = official_metrics["total_return_pct"]
    for variant, group in curves.groupby("variant", sort=False):
        group = group.sort_values("date")
        equity = pd.to_numeric(group["overlay_equity"], errors="coerce")
        dd = pd.to_numeric(group["overlay_drawdown_pct"], errors="coerce")
        total_return = (float(equity.iloc[-1]) / CAPITAL - 1.0) * 100.0
        row = {
            "variant": variant,
            "policy_type": str(group["policy_type"].iloc[0]),
            "description": str(group["description"].iloc[0]),
            "end_equity": float(equity.iloc[-1]),
            "total_return_pct": total_return,
            "return_retention_pct": total_return / official_return * 100.0 if abs(official_return) > 1e-9 else np.nan,
            "max_dd_pct": float(dd.min()),
            "dd_improvement_pp": float(dd.min()) - official_metrics["max_dd_pct"],
            "ulcer_pct": _ulcer_pct(dd),
            "sharpe": _sharpe_from_equity(equity),
            "avg_risk_weight": float(pd.to_numeric(group["risk_weight"], errors="coerce").mean()),
            "min_risk_weight": float(pd.to_numeric(group["risk_weight"], errors="coerce").min()),
            "days_risk_weight_below_95pct": int((pd.to_numeric(group["risk_weight"], errors="coerce") < 0.95).sum()),
            "max_broker10_margin_to_equity_pct": float(
                pd.to_numeric(group["scaled_broker10_margin_to_equity_pct"], errors="coerce").max()
            ),
            "days_over_100pct": int((pd.to_numeric(group["scaled_broker10_margin_to_equity_pct"], errors="coerce") > 100).sum()),
            "days_over_90pct": int((pd.to_numeric(group["scaled_broker10_margin_to_equity_pct"], errors="coerce") > 90).sum()),
            "total_scaled_slippage": float(pd.to_numeric(group["scaled_slippage"], errors="coerce").fillna(0.0).sum()),
            "official_trade_count_reference": float(pd.to_numeric(group["trade_count"], errors="coerce").fillna(0.0).sum()),
        }
        row["return_80_pass"] = int(row["return_retention_pct"] >= 79.999)
        row["dd_better_than_official"] = int(row["max_dd_pct"] > official_metrics["max_dd_pct"])
        row["broker10_not_worse_pass"] = int(
            row["max_broker10_margin_to_equity_pct"] <= official_metrics["max_broker10_margin_to_equity_pct"] + 1e-9
        )
        row["headline_metric_pass"] = int(
            row["return_80_pass"] == 1 and row["dd_better_than_official"] == 1 and row["broker10_not_worse_pass"] == 1
        )
        row["meaningful_dd5_pass"] = int(row["dd_improvement_pp"] >= 5.0)
        row["candidate_ready"] = 0
        if variant == "A_official_c9_15w":
            row["decision_note"] = "official benchmark"
        elif row["headline_metric_pass"] and row["meaningful_dd5_pass"] == 0:
            row["decision_note"] = "headline proxy passes, but drawdown improvement is too small and proxy-only"
        elif row["headline_metric_pass"]:
            row["decision_note"] = "headline proxy passes, but still proxy-only and needs true engine/integer-lot validation"
        elif row["return_80_pass"] == 0:
            row["decision_note"] = "fails return retention"
        elif row["dd_better_than_official"] == 0:
            row["decision_note"] = "does not reduce drawdown"
        else:
            row["decision_note"] = "proxy-only; broker10 or drawdown does not pass"
        rows.append(row)
    return pd.DataFrame(rows)


def _year_stats(curves: pd.DataFrame) -> pd.DataFrame:
    data = curves.copy()
    data["year"] = pd.to_datetime(data["date"]).dt.year
    rows: list[dict[str, Any]] = []
    for (variant, year), group in data.groupby(["variant", "year"], sort=False):
        group = group.sort_values("date")
        start_equity = float(group["overlay_equity"].iloc[0] - group["scaled_net_pnl"].iloc[0])
        end_equity = float(group["overlay_equity"].iloc[-1])
        rows.append(
            {
                "variant": variant,
                "year": int(year),
                "start_equity": start_equity,
                "end_equity": end_equity,
                "year_return_pct": (end_equity / start_equity - 1.0) * 100.0 if start_equity > 0 else np.nan,
                "year_pnl": float(pd.to_numeric(group["scaled_net_pnl"], errors="coerce").fillna(0.0).sum()),
                "year_max_dd_pct": float(pd.to_numeric(group["overlay_drawdown_pct"], errors="coerce").min()),
                "avg_risk_weight": float(pd.to_numeric(group["risk_weight"], errors="coerce").mean()),
                "min_risk_weight": float(pd.to_numeric(group["risk_weight"], errors="coerce").min()),
            }
        )
    return pd.DataFrame(rows)


def _feature_bucket_stats(features: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    masks = {
        "no_follow_30m": features["is_no_follow_30m"],
        "entry_unaligned": features["is_entry_unaligned"],
        "combined_low_quality": features["is_combined_low_quality"],
        "strict_hq": features["is_strict_hq"],
        "not_strict_hq": features["is_not_strict_hq"],
    }
    total_positive = float(features["positive_pnl"].sum())
    total_negative = float(abs(features["negative_pnl"].sum()))
    for label, mask in masks.items():
        group = features[mask.fillna(False)].copy()
        rows.append(
            {
                "bucket": label,
                "lots": int(len(group)),
                "products": int(group["product"].astype(str).nunique()) if not group.empty else 0,
                "years": int(group["entry_year"].nunique()) if "entry_year" in group.columns and not group.empty else 0,
                "official_pnl": float(group["realized_pnl"].fillna(0.0).sum()) if not group.empty else 0.0,
                "positive_pnl": float(group["positive_pnl"].fillna(0.0).sum()) if not group.empty else 0.0,
                "negative_pnl": float(group["negative_pnl"].fillna(0.0).sum()) if not group.empty else 0.0,
                "positive_capture_pct": float(group["positive_pnl"].sum() / total_positive * 100.0)
                if total_positive > 1e-9 and not group.empty
                else 0.0,
                "negative_capture_pct": float(abs(group["negative_pnl"].sum()) / total_negative * 100.0)
                if total_negative > 1e-9 and not group.empty
                else 0.0,
                "big_winner_count": int(pd.to_numeric(group.get("big_winner"), errors="coerce").fillna(0.0).sum())
                if not group.empty
                else 0,
            }
        )
    return pd.DataFrame(rows)


def _plot_path_drawdown(curves: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 1, figsize=(18, 11), sharex=True, constrained_layout=True)
    colors = {
        "A_official_c9_15w": "#2563eb",
        "fixed80_global_reference": "#0891b2",
        "no_follow_30m_low_quality_80": "#16a34a",
        "entry_unaligned_low_quality_80": "#f59e0b",
        "combined_low_quality_80": "#dc2626",
        "strict_hq_only_full_else80": "#7c3aed",
    }
    for variant, group in curves.groupby("variant", sort=False):
        group = group.sort_values("date")
        axes[0].plot(group["date"], group["overlay_equity"], label=variant, color=colors.get(variant), linewidth=1.05)
        axes[1].plot(group["date"], group["overlay_drawdown_pct"], label=variant, color=colors.get(variant), linewidth=0.95)
    axes[0].set_yscale("log")
    axes[0].set_title("Quality-conditioned 80% risk-shave proxy wealth paths")
    axes[0].grid(True, alpha=0.2)
    axes[0].legend(loc="best", fontsize=8)
    axes[1].axhline(-40, color="#dc2626", linestyle="--", linewidth=0.8, alpha=0.6)
    axes[1].axhline(-50, color="#7f1d1d", linestyle="--", linewidth=0.8, alpha=0.6)
    axes[1].set_title("Drawdown paths")
    axes[1].grid(True, alpha=0.2)
    axes[1].legend(loc="best", fontsize=8)
    fig.savefig(PATH_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_weight_chart(weights: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 1, figsize=(18, 10), sharex=True, constrained_layout=True)
    axes[0].plot(weights["date"], weights["active_share_no_follow_30m"], label="no_follow active risk share", linewidth=0.9)
    axes[0].plot(weights["date"], weights["active_share_entry_unaligned"], label="entry unaligned active risk share", linewidth=0.9)
    axes[0].plot(weights["date"], weights["active_share_combined_low_quality"], label="combined low-quality active risk share", linewidth=0.9)
    axes[0].plot(weights["date"], weights["active_share_not_strict_hq"], label="not strict-HQ active risk share", linewidth=0.9)
    axes[0].set_ylim(-0.02, 1.02)
    axes[0].set_title("Daily active risk share by low-quality definition")
    axes[0].grid(True, alpha=0.2)
    axes[0].legend(loc="best", fontsize=8)

    for policy in POLICIES:
        variant = str(policy["variant"])
        if variant == "A_official_c9_15w":
            continue
        axes[1].plot(weights["date"], weights[f"risk_weight_{variant}"], label=variant, linewidth=0.9)
    axes[1].set_ylim(0.78, 1.02)
    axes[1].set_title("Daily proxy risk weight after fixed 80% low-quality shave")
    axes[1].grid(True, alpha=0.2)
    axes[1].legend(loc="best", fontsize=8)
    fig.savefig(WEIGHT_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_scatter(metrics: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(12, 8), constrained_layout=True)
    data = metrics.copy()
    colors = np.where(data["headline_metric_pass"].eq(1), "#16a34a", "#dc2626")
    ax.scatter(data["return_retention_pct"], data["max_dd_pct"], s=170, c=colors, alpha=0.78, edgecolor="#334155")
    for _, row in data.iterrows():
        ax.annotate(str(row["variant"]), (row["return_retention_pct"], row["max_dd_pct"]), fontsize=8, xytext=(5, 5), textcoords="offset points")
    ax.axvline(80, color="#2563eb", linestyle="--", linewidth=0.9, label="80% return retention")
    official_dd = float(data.loc[data["variant"].eq("A_official_c9_15w"), "max_dd_pct"].iloc[0])
    ax.axhline(official_dd, color="#64748b", linestyle="--", linewidth=0.9, label="official max DD")
    ax.set_xlabel("Return retention vs official (%)")
    ax.set_ylabel("Max drawdown (%)")
    ax.set_title("Quality-conditioned proxy trade-off")
    ax.grid(True, alpha=0.2)
    ax.legend(loc="best")
    fig.savefig(SCATTER_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_year_heatmap(year_stats: pd.DataFrame) -> None:
    pivot = year_stats.pivot_table(index="variant", columns="year", values="year_return_pct", aggfunc="sum")
    fig, ax = plt.subplots(figsize=(17, 8), constrained_layout=True)
    values = pivot.values
    limit = np.nanpercentile(np.abs(values), 95) if values.size else 1.0
    limit = max(float(limit), 1.0)
    im = ax.imshow(values, cmap="RdYlGn", aspect="auto", vmin=-limit, vmax=limit)
    ax.set_xticks(np.arange(len(pivot.columns)))
    ax.set_xticklabels([str(int(col)) for col in pivot.columns], rotation=45, ha="right", fontsize=8)
    ax.set_yticks(np.arange(len(pivot.index)))
    ax.set_yticklabels(pivot.index, fontsize=8)
    for i in range(values.shape[0]):
        for j in range(values.shape[1]):
            ax.text(j, i, f"{values[i, j]:.0f}%", ha="center", va="center", fontsize=6, color="#0f172a")
    ax.set_title("Calendar-year return by quality-conditioned proxy")
    fig.colorbar(im, ax=ax, label="Year return (%)")
    fig.savefig(YEAR_HEATMAP_OUT, dpi=170)
    plt.close(fig)


def _direction_sign(direction: Any) -> int:
    return -1 if str(direction).lower() == "short" else 1


def _select_atlas_rows(features: pd.DataFrame) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    no_follow = features[features["is_no_follow_30m"]].copy()
    if not no_follow.empty:
        frames.append(no_follow.sort_values("realized_pnl").head(6).assign(atlas_reason="no_follow_big_losses"))
        frames.append(no_follow.sort_values("realized_pnl", ascending=False).head(6).assign(atlas_reason="no_follow_false_positive_winners"))
    unaligned = features[features["is_entry_unaligned"]].copy()
    if not unaligned.empty:
        frames.append(unaligned.sort_values("realized_pnl", ascending=False).head(5).assign(atlas_reason="entry_unaligned_top_winners"))
    strict_hq = features[features["is_strict_hq"]].copy()
    if not strict_hq.empty:
        frames.append(strict_hq.sort_values("realized_pnl", ascending=False).head(4).assign(atlas_reason="strict_hq_top_winners"))
        frames.append(strict_hq.sort_values("realized_pnl").head(3).assign(atlas_reason="strict_hq_losses"))
    if not frames:
        return pd.DataFrame()
    selected = pd.concat(frames, ignore_index=True, sort=False)
    return selected.drop_duplicates(["vt_symbol", "entry_date", "direction"]).head(MAX_ATLAS_ROWS)


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
        fig, axes = plt.subplots(len(part), 1, figsize=(18, max(4.2, 3.6 * len(part))), constrained_layout=True)
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
                    f"quality={row.get('repair_quality_label')} "
                    f"entry_align={bool(row.get('tag_entry_or_first_aligned', False))} "
                    f"strict_hq={bool(row.get('is_strict_hq', False))}"
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
                    "repair_quality_label": row.get("repair_quality_label", ""),
                    "tag_entry_or_first_aligned": bool(row.get("tag_entry_or_first_aligned", False)),
                    "is_strict_hq": bool(row.get("is_strict_hq", False)),
                }
            )
        fig.suptitle("Stage018 quality-conditioned proxy minute-K atlas", fontsize=12)
        path = Path(str(ATLAS_TEMPLATE).format(page=page))
        fig.savefig(path, dpi=170)
        plt.close(fig)
        paths.append(path)
    manifest = pd.DataFrame(manifest_rows)
    manifest.to_csv(ATLAS_MANIFEST_OUT, index=False, encoding="utf-8-sig")
    return paths, manifest


def _summary(metrics: pd.DataFrame, feature_stats: pd.DataFrame) -> dict[str, Any]:
    official = metrics[metrics["variant"].eq("A_official_c9_15w")].head(1).to_dict("records")[0]
    passing = metrics[metrics["headline_metric_pass"].eq(1)].copy()
    return {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "official_live_alias": OFFICIAL_LIVE_ALIAS,
        "official_total_return_pct": official["total_return_pct"],
        "official_max_dd_pct": official["max_dd_pct"],
        "policy_count": int(len(metrics)),
        "headline_metric_pass_count": int(len(passing)),
        "meaningful_dd5_pass_count": int(pd.to_numeric(metrics["meaningful_dd5_pass"], errors="coerce").fillna(0).sum()),
        "candidate_ready_count": int(pd.to_numeric(metrics["candidate_ready"], errors="coerce").fillna(0).sum()),
        "best_dd_variant": metrics.sort_values("max_dd_pct", ascending=False).head(1).to_dict("records")[0],
        "best_return_retention_variant": metrics[~metrics["variant"].eq("A_official_c9_15w")]
        .sort_values("return_retention_pct", ascending=False)
        .head(1)
        .to_dict("records")[0],
        "feature_bucket_stats": feature_stats.to_dict("records"),
        "decision": "stage018_quality_conditioned_risk_shave_proxy_no_candidate",
    }


def _decision(summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "official_live_alias": OFFICIAL_LIVE_ALIAS,
        "decision": "stage018_quality_conditioned_risk_shave_proxy_no_candidate",
        "summary": summary,
        "order_api_called": False,
        "ctp_connected": False,
        "external_research_judgment": (
            "Trend-following position-sizing literature supports testing risk sizing without changing entry/exit alpha, "
            "but also warns against parameter optimization and right-tail destruction. Stage018 therefore freezes one "
            "low-quality weight at 80% and audits only broad minute-quality archetypes."
        ),
        "overfit_reflection_before": (
            "No: variants are predeclared broad tags from prior forensic stages; no product/year/direction/window scan."
        ),
        "continue_value_before": (
            "Yes: Stage017 rejected account-layer CPPI/TIPP; a lighter quality-conditioned proxy can test whether minute quality tags improve fixed80."
        ),
        "overfit_reflection_after": (
            "No candidate selected. If a variant looks superficially better, it remains proxy-only and cannot be promoted without true-engine and OOS validation."
        ),
        "continue_value_after": (
            "Depends on metrics: continue only if quality-conditioned curves show materially better drawdown than fixed80 without right-tail collapse."
        ),
        "outputs": {
            "features": str(FEATURES_OUT),
            "daily_weights": str(DAILY_WEIGHTS_OUT),
            "curves": str(CURVES_OUT),
            "metrics": str(METRICS_OUT),
            "year_stats": str(YEAR_STATS_OUT),
            "summary": str(SUMMARY_OUT),
            "path_chart": str(PATH_CHART_OUT),
            "weight_chart": str(WEIGHT_CHART_OUT),
            "scatter_chart": str(SCATTER_CHART_OUT),
            "year_heatmap": str(YEAR_HEATMAP_OUT),
            "atlas_manifest": str(ATLAS_MANIFEST_OUT),
            "report": str(REPORT_OUT),
            "decision": str(DECISION_OUT),
        },
    }


def _write_report(summary: dict[str, Any], metrics: pd.DataFrame, feature_stats: pd.DataFrame, year_stats: pd.DataFrame) -> None:
    report = "\n".join(
        [
            "# Stage018 quality-conditioned risk-shave proxy",
            "",
            f"- generated_at: `{datetime.now():%Y-%m-%d %H:%M}`",
            f"- line_id: `{LINE_ID}`",
            f"- official: `{OFFICIAL_LIVE_VERSION}` / `{OFFICIAL_LIVE_ALIAS}`",
            "- type: read-only daily active-risk proxy; no true engine, no CTP, no order API.",
            "- fixed low-quality risk weight: `80%`.",
            "- decision: `stage018_quality_conditioned_risk_shave_proxy_no_candidate`",
            "",
            "## External Research Judgment",
            "",
            "- Position-sizing research in trend-following CTAs supports testing risk sizing while holding entry/exit alpha constant.",
            "- The same literature warns against over-optimizing sizing parameters and against destroying right-tail participation.",
            "- Stage018 freezes one weight only and compares broad quality labels against global fixed80.",
            "",
            "## Summary",
            "",
            _md_table(pd.DataFrame([summary])),
            "",
            "## Metrics",
            "",
            _md_table(metrics, max_rows=20),
            "",
            "## Feature Bucket Stats",
            "",
            _md_table(feature_stats, max_rows=20),
            "",
            "## Year Stats",
            "",
            _md_table(year_stats.head(80), max_rows=80),
            "",
            "## Output Files",
            "",
            f"- curves: `{CURVES_OUT}`",
            f"- daily weights: `{DAILY_WEIGHTS_OUT}`",
            f"- metrics: `{METRICS_OUT}`",
            f"- path chart: `{PATH_CHART_OUT}`",
            f"- weight chart: `{WEIGHT_CHART_OUT}`",
            f"- scatter chart: `{SCATTER_CHART_OUT}`",
            f"- year heatmap: `{YEAR_HEATMAP_OUT}`",
            f"- atlas manifest: `{ATLAS_MANIFEST_OUT}`",
            "",
            "## Judgment",
            "",
            "- This is a proxy over official daily PnL, weighted by active lot risk share. It is not a deployable execution engine.",
            "- Passing `80%` return retention inside this proxy is necessary but not sufficient.",
            "- Candidate readiness is forced to `0`; any useful shape would still need a true integer-lot engine.",
            "",
            "## Reflections",
            "",
            "- overfit_reflection_before: `No: fixed broad labels and one fixed 80% low-quality weight.`",
            "- overfit_reflection_after: `No candidate selected; using the chart to choose a different shave weight would overfit.`",
            "- continue_value_before: `Yes: tests whether minute-quality tags add value beyond global fixed80.`",
            "- continue_value_after: `Only if the visual path shows a structural improvement rather than a single-window cosmetic change.`",
        ]
    )
    REPORT_OUT.write_text(report, encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print("[stage018] loading official curve and minute-quality features", flush=True)
    official = _prepare_official_curve()
    features = _prepare_features()
    official_summary = _read_required_csv(SUMMARY_IN)
    official_metrics = {
        "total_return_pct": float(pd.to_numeric(official_summary["total_return_pct"], errors="coerce").iloc[0]),
        "max_dd_pct": float(pd.to_numeric(official_summary["max_dd_pct"], errors="coerce").iloc[0]),
        "max_broker10_margin_to_equity_pct": float(
            pd.to_numeric(official_summary["max_broker10_margin_to_equity_pct"], errors="coerce").iloc[0]
        ),
    }

    print("[stage018] building daily active risk shares", flush=True)
    daily_weights = _daily_active_weights(official, features)
    curves = _simulate_curves(official, daily_weights)
    metrics = _metrics(curves, official_metrics)
    year_stats = _year_stats(curves)
    feature_stats = _feature_bucket_stats(features)
    summary = _summary(metrics, feature_stats)
    decision = _decision(summary)

    print("[stage018] plotting visuals", flush=True)
    _plot_path_drawdown(curves)
    _plot_weight_chart(daily_weights)
    _plot_scatter(metrics)
    _plot_year_heatmap(year_stats)
    _plot_atlas(features)

    features.to_csv(FEATURES_OUT, index=False, encoding="utf-8-sig")
    daily_weights.to_csv(DAILY_WEIGHTS_OUT, index=False, encoding="utf-8-sig")
    curves.to_csv(CURVES_OUT, index=False, encoding="utf-8-sig")
    metrics.to_csv(METRICS_OUT, index=False, encoding="utf-8-sig")
    year_stats.to_csv(YEAR_STATS_OUT, index=False, encoding="utf-8-sig")
    pd.DataFrame([summary]).to_csv(SUMMARY_OUT, index=False, encoding="utf-8-sig")
    DECISION_OUT.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(summary, metrics, feature_stats, year_stats)

    print(json.dumps(_json_safe(summary), ensure_ascii=False, indent=2), flush=True)
    print(f"[stage018] wrote {OUTPUT_DIR}", flush=True)


if __name__ == "__main__":
    main()

