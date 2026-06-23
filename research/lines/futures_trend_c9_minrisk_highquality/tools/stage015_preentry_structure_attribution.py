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
STAGE = "Stage015"
MODEL_TAG = "stage015_preentry_structure_attribution_v1"
OUTPUT_PREFIX = "qmt_roll_stage015_c9_minrisk_preentry_structure_attribution"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
TOOL_DIR = SCRIPT_PATH.parent
EXAMPLE_DIR = REPO_DIR / "examples" / "portfolio_backtesting"
for item in [str(TOOL_DIR), str(EXAMPLE_DIR)]:
    if item not in sys.path:
        sys.path.insert(0, item)

import stage010_authoritative_minute_coverage_audit as s010
import stage013_minrisk_clean_restore_true_engine as s013
from qmt_roll_official_live_config import OFFICIAL_LIVE_ALIAS, OFFICIAL_LIVE_VERSION


LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage015_preentry_structure_attribution"
STAGE010_DIR = LINE_DIR / "outputs" / "stage010_authoritative_minute_coverage_audit"
STAGE014_DIR = LINE_DIR / "outputs" / "stage014_stage013_failure_attribution"

START = pd.Timestamp("2018-01-01")
END = pd.Timestamp("2026-06-15")
CAPITAL = 150_000.0
PER_PAGE = 4
MAX_ATLAS_ROWS = 20

FEATURES_IN = (
    STAGE010_DIR
    / "qmt_roll_stage010_c9_minrisk_authoritative_minute_coverage_audit_coverage_features_stage010_authoritative_minute_coverage_audit_v1.csv"
)
CURVE_IN = (
    STAGE010_DIR
    / "qmt_roll_stage010_c9_minrisk_authoritative_minute_coverage_audit_official_curve_stage010_authoritative_minute_coverage_audit_v1.csv"
)
SUMMARY_IN = (
    STAGE010_DIR
    / "qmt_roll_stage010_c9_minrisk_authoritative_minute_coverage_audit_summary_stage010_authoritative_minute_coverage_audit_v1.csv"
)
STAGE014_LEDGER_IN = (
    STAGE014_DIR
    / "qmt_roll_stage014_c9_minrisk_stage013_failure_attribution_event_match_ledger_stage014_stage013_failure_attribution_v1.csv"
)

FEATURES_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_features_{MODEL_TAG}.csv"
BUCKET_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_bucket_stats_{MODEL_TAG}.csv"
YEAR_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_bucket_year_stats_{MODEL_TAG}.csv"
SELECTED_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_selected_buckets_{MODEL_TAG}.csv"
SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_path_bucket_chart_{MODEL_TAG}.png"
SCATTER_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_bucket_scatter_chart_{MODEL_TAG}.png"
ATLAS_MANIFEST_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_atlas_manifest_{MODEL_TAG}.csv"
ATLAS_TEMPLATE = OUTPUT_DIR / f"{OUTPUT_PREFIX}_atlas_page{{page:03d}}_{MODEL_TAG}.png"


PREENTRY_FEATURES = [
    "entry_context",
    "signal",
    "direction",
    "risk_multiplier_bucket",
    "loss_streak_bucket",
    "active_positions_bucket",
    "ai_rank_bucket",
    "rsi_bucket",
    "stop_distance_bucket",
    "recovery_bucket",
    "streak_recovery_bucket",
    "breakout_bucket",
    "daily_directional_alignment_bucket",
    "portfolio_drawdown_bucket",
    "same_direction_active_bucket",
]

ENTRY_INSTANT_FEATURES = [
    "entry_open_relation_bucket",
    "first_bar_relation_bucket",
    "first_bar_body_bucket",
    "first_bar_adverse_wick_bucket",
]


def _json_safe(value: Any) -> Any:
    return s013._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s013._md_table(frame, max_rows=max_rows)


def _safe_float(value: Any, default: float = np.nan) -> float:
    return s013._safe_float(value, default=default)


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


def _direction_sign(direction: Any) -> int:
    return -1 if str(direction).lower() == "short" else 1


def _signed_bucket(value: Any, *, prefix: str = "") -> str:
    x = _safe_float(value)
    if not np.isfinite(x):
        return f"{prefix}missing" if prefix else "missing"
    if x > 0:
        return f"{prefix}aligned" if prefix else "aligned"
    if x < 0:
        return f"{prefix}adverse" if prefix else "adverse"
    return f"{prefix}flat" if prefix else "flat"


def _portfolio_drawdown_bucket(value: Any) -> str:
    x = _safe_float(value)
    if not np.isfinite(x):
        return "portfolio_dd_missing"
    # Fixed broad risk-state bands; used only for attribution, not tuning.
    if x >= -5:
        return "portfolio_dd_0_5"
    if x >= -15:
        return "portfolio_dd_5_15"
    if x >= -30:
        return "portfolio_dd_15_30"
    return "portfolio_dd_ge30"


def _same_direction_active_bucket(value: Any) -> str:
    x = _safe_float(value)
    if not np.isfinite(x):
        return "same_dir_active_missing"
    if x <= 0:
        return "same_dir_active_0"
    if x == 1:
        return "same_dir_active_1"
    if x <= 3:
        return "same_dir_active_2_3"
    return "same_dir_active_ge4"


def _daily_alignment(row: pd.Series) -> str:
    direction = str(row.get("direction", "")).lower()
    bullish = _safe_float(row.get("bullish_alignment"), 0.0) > 0
    bearish = _safe_float(row.get("bearish_alignment"), 0.0) > 0
    if direction == "long":
        return "daily_aligned" if bullish else "daily_not_aligned"
    if direction == "short":
        return "daily_aligned" if bearish else "daily_not_aligned"
    return "daily_alignment_missing"


def _prepare_base_features() -> pd.DataFrame:
    data = _read_required_csv(FEATURES_IN)
    data["entry_day"] = data["entry_date"].map(_normalize_day)
    data["exit_day"] = data["exit_date"].map(_normalize_day)
    numeric_cols = [
        "realized_pnl",
        "volume",
        "size",
        "entry_price",
        "exit_price",
        "risk_amount",
        "r_multiple",
        "stop_distance",
        "risk_price",
        "portfolio_drawdown_pct",
        "same_direction_correlation_active_count",
        "bullish_alignment",
        "bearish_alignment",
        "big_winner",
        "winner",
    ]
    for column in numeric_cols:
        if column in data.columns:
            data[column] = pd.to_numeric(data[column], errors="coerce")
    data["positive_pnl"] = pd.to_numeric(data["realized_pnl"], errors="coerce").clip(lower=0.0).fillna(0.0)
    data["negative_pnl"] = pd.to_numeric(data["realized_pnl"], errors="coerce").clip(upper=0.0).fillna(0.0)
    data["risk_for_entry_instant"] = pd.to_numeric(data.get("risk_price"), errors="coerce")
    missing_risk = ~np.isfinite(data["risk_for_entry_instant"]) | (data["risk_for_entry_instant"] <= 0)
    data.loc[missing_risk, "risk_for_entry_instant"] = pd.to_numeric(data.get("stop_distance"), errors="coerce")
    data["daily_directional_alignment_bucket"] = data.apply(_daily_alignment, axis=1)
    data["portfolio_drawdown_bucket"] = data.get("portfolio_drawdown_pct", pd.Series(index=data.index)).map(
        _portfolio_drawdown_bucket
    )
    data["same_direction_active_bucket"] = data.get(
        "same_direction_correlation_active_count", pd.Series(index=data.index)
    ).map(_same_direction_active_bucket)
    for column in PREENTRY_FEATURES:
        if column not in data.columns:
            data[column] = "missing"
        data[column] = data[column].fillna("missing").astype(str)
    return data


def _load_stage014_ledger() -> pd.DataFrame:
    if not STAGE014_LEDGER_IN.exists():
        return pd.DataFrame()
    ledger = _read_required_csv(STAGE014_LEDGER_IN)
    ledger["entry_day"] = ledger["entry_day"].map(_normalize_day)
    for column in ["delta_candidate_minus_official", "official_pnl", "candidate_pnl"]:
        if column in ledger.columns:
            ledger[column] = pd.to_numeric(ledger[column], errors="coerce")
    keep = [
        "event_index",
        "vt_symbol",
        "direction",
        "entry_day",
        "final_state",
        "state_group",
        "official_lots",
        "official_pnl",
        "candidate_pnl",
        "delta_candidate_minus_official",
    ]
    return ledger[[column for column in keep if column in ledger.columns]].copy()


def _merge_stage014(features: pd.DataFrame, ledger: pd.DataFrame) -> pd.DataFrame:
    data = features.copy()
    if ledger.empty:
        data["stage014_state_group"] = ""
        data["stage014_delta_candidate_minus_official"] = np.nan
        data["stage014_delta_allocated_to_lot"] = np.nan
        data["stage014_event_index"] = np.nan
        return data
    merged = data.merge(
        ledger.rename(
            columns={
                "event_index": "stage014_event_index",
                "state_group": "stage014_state_group",
                "final_state": "stage014_final_state",
                "official_lots": "stage014_official_lots",
                "delta_candidate_minus_official": "stage014_delta_candidate_minus_official",
                "official_pnl": "stage014_official_pnl",
                "candidate_pnl": "stage014_candidate_pnl",
            }
        ),
        on=["vt_symbol", "direction", "entry_day"],
        how="left",
    )
    official_lots = pd.to_numeric(merged.get("stage014_official_lots"), errors="coerce").replace(0, np.nan)
    merged["stage014_delta_allocated_to_lot"] = pd.to_numeric(
        merged.get("stage014_delta_candidate_minus_official"), errors="coerce"
    ) / official_lots
    return merged


def _entry_instant_metrics(row: pd.Series, minute_by_symbol: dict[str, pd.DataFrame]) -> dict[str, Any]:
    vt_symbol = str(row.get("vt_symbol", ""))
    entry_day = _normalize_day(row.get("entry_date"))
    bars = minute_by_symbol.get(vt_symbol, pd.DataFrame())
    day = bars[bars["bar_date"].eq(entry_day)].copy().sort_values("bar_datetime") if not bars.empty else pd.DataFrame()
    risk = _safe_float(row.get("risk_for_entry_instant"))
    entry = _safe_float(row.get("entry_price"))
    if day.empty or not np.isfinite(risk) or risk <= 0 or not np.isfinite(entry):
        return {
            "entry_instant_minute_available": 0,
            "entry_first_bar_time": "",
            "entry_open_gap_r": np.nan,
            "first_bar_directional_r": np.nan,
            "first_bar_body_directional_r": np.nan,
            "first_bar_mfe_r": np.nan,
            "first_bar_mae_r": np.nan,
            "first_bar_oi_change": np.nan,
            "entry_open_relation_bucket": "entry_open_missing",
            "first_bar_relation_bucket": "first_bar_missing",
            "first_bar_body_bucket": "first_body_missing",
            "first_bar_adverse_wick_bucket": "first_adverse_wick_missing",
        }
    first = day.iloc[0]
    sign = _direction_sign(row.get("direction"))
    open_price = _safe_float(first.get("open"))
    close_price = _safe_float(first.get("close"))
    high = _safe_float(first.get("high"))
    low = _safe_float(first.get("low"))
    entry_open_gap_r = sign * (open_price - entry) / risk if np.isfinite(open_price) else np.nan
    first_bar_directional_r = sign * (close_price - entry) / risk if np.isfinite(close_price) else np.nan
    first_bar_body_directional_r = sign * (close_price - open_price) / risk if np.isfinite(close_price) and np.isfinite(open_price) else np.nan
    if str(row.get("direction")).lower() == "short":
        mfe = (entry - low) / risk if np.isfinite(low) else np.nan
        mae = (high - entry) / risk if np.isfinite(high) else np.nan
    else:
        mfe = (high - entry) / risk if np.isfinite(high) else np.nan
        mae = (entry - low) / risk if np.isfinite(low) else np.nan
    open_oi = _safe_float(first.get("open_oi"))
    close_oi = _safe_float(first.get("close_oi"))
    oi_change = close_oi - open_oi if np.isfinite(open_oi) and np.isfinite(close_oi) else np.nan
    return {
        "entry_instant_minute_available": 1,
        "entry_first_bar_time": pd.Timestamp(first["bar_datetime"]).isoformat(),
        "entry_open_gap_r": entry_open_gap_r,
        "first_bar_directional_r": first_bar_directional_r,
        "first_bar_body_directional_r": first_bar_body_directional_r,
        "first_bar_mfe_r": max(0.0, mfe) if np.isfinite(mfe) else np.nan,
        "first_bar_mae_r": max(0.0, mae) if np.isfinite(mae) else np.nan,
        "first_bar_oi_change": oi_change,
        "entry_open_relation_bucket": _signed_bucket(entry_open_gap_r, prefix="entry_open_"),
        "first_bar_relation_bucket": _signed_bucket(first_bar_directional_r, prefix="first_bar_"),
        "first_bar_body_bucket": _signed_bucket(first_bar_body_directional_r, prefix="first_body_"),
        "first_bar_adverse_wick_bucket": (
            "first_adverse_wick_none"
            if np.isfinite(mae) and mae <= 0
            else "first_adverse_wick_present"
            if np.isfinite(mae)
            else "first_adverse_wick_missing"
        ),
    }


def _add_entry_instant_features(features: pd.DataFrame, minute_bars: pd.DataFrame) -> pd.DataFrame:
    minute_by_symbol = s010.s008.s825._minute_groups(minute_bars)
    rows = [_entry_instant_metrics(row, minute_by_symbol) for _, row in features.iterrows()]
    extra = pd.DataFrame(rows)
    return pd.concat([features.reset_index(drop=True), extra.reset_index(drop=True)], axis=1)


def _bucket_year_stats(data: pd.DataFrame, feature_columns: list[str]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for feature in feature_columns:
        for (value, year), group in data.groupby([feature, "entry_year"], dropna=False):
            rows.append(
                {
                    "feature": feature,
                    "bucket": str(value),
                    "entry_year": int(year) if pd.notna(year) else np.nan,
                    "events": int(len(group)),
                    "products": int(group["product"].astype(str).nunique()),
                    "official_pnl": float(group["realized_pnl"].fillna(0.0).sum()),
                    "positive_pnl": float(group["positive_pnl"].sum()),
                    "negative_pnl": float(group["negative_pnl"].sum()),
                    "big_winner_count": int(pd.to_numeric(group.get("big_winner"), errors="coerce").fillna(0).sum()),
                    "stage014_delta_sum": float(
                        pd.to_numeric(group.get("stage014_delta_allocated_to_lot"), errors="coerce")
                        .fillna(0.0)
                        .sum()
                    ),
                }
            )
    return pd.DataFrame(rows)


def _bucket_stats(data: pd.DataFrame, year_stats: pd.DataFrame, feature_columns: list[str]) -> pd.DataFrame:
    total_pnl = float(data["realized_pnl"].fillna(0.0).sum())
    total_positive = float(data["positive_pnl"].sum())
    total_negative_abs = float(abs(data["negative_pnl"].sum()))
    total_lots = max(1, int(len(data)))
    total_stage014_allocated_delta = float(
        pd.to_numeric(data.get("stage014_delta_allocated_to_lot"), errors="coerce").fillna(0.0).sum()
    )
    rows: list[dict[str, Any]] = []
    for feature in feature_columns:
        feature_bucket_count = int(data[feature].astype(str).nunique(dropna=False)) if feature in data.columns else 0
        for value, group in data.groupby(feature, dropna=False):
            value_text = str(value)
            yearly = year_stats[(year_stats["feature"].eq(feature)) & (year_stats["bucket"].eq(value_text))]
            positive_years = int((yearly["official_pnl"] > 0).sum()) if not yearly.empty else 0
            negative_years = int((yearly["official_pnl"] < 0).sum()) if not yearly.empty else 0
            pnl = float(group["realized_pnl"].fillna(0.0).sum())
            positive = float(group["positive_pnl"].sum())
            negative = float(group["negative_pnl"].sum())
            stage014_delta = float(
                pd.to_numeric(group.get("stage014_delta_allocated_to_lot"), errors="coerce").fillna(0.0).sum()
            )
            stage014_matched_lots = int(
                pd.to_numeric(group.get("stage014_delta_allocated_to_lot"), errors="coerce").notna().sum()
            )
            stage014_unique_events = int(
                pd.to_numeric(group.get("stage014_event_index"), errors="coerce").dropna().nunique()
            )
            rows.append(
                {
                    "feature": feature,
                    "bucket": value_text,
                    "events": int(len(group)),
                    "bucket_event_share_pct": float(len(group) / total_lots * 100.0),
                    "feature_bucket_count": feature_bucket_count,
                    "products": int(group["product"].astype(str).nunique()),
                    "years": int(group["entry_year"].nunique()),
                    "official_pnl": pnl,
                    "positive_pnl": positive,
                    "negative_pnl": negative,
                    "median_r_multiple": float(pd.to_numeric(group["r_multiple"], errors="coerce").median()),
                    "win_rate_pct": float(pd.to_numeric(group.get("winner"), errors="coerce").fillna(0.0).mean() * 100.0),
                    "big_winner_count": int(pd.to_numeric(group.get("big_winner"), errors="coerce").fillna(0.0).sum()),
                    "big_winner_pnl": float(group.loc[pd.to_numeric(group.get("big_winner"), errors="coerce").fillna(0.0) > 0, "realized_pnl"].sum()),
                    "positive_years": positive_years,
                    "negative_years": negative_years,
                    "min_year_pnl": float(yearly["official_pnl"].min()) if not yearly.empty else np.nan,
                    "max_year_pnl": float(yearly["official_pnl"].max()) if not yearly.empty else np.nan,
                    "net_pnl_share_pct": pnl / total_pnl * 100.0 if abs(total_pnl) > 1e-9 else np.nan,
                    "positive_pnl_capture_pct": positive / total_positive * 100.0 if abs(total_positive) > 1e-9 else np.nan,
                    "negative_pnl_capture_pct": abs(negative) / total_negative_abs * 100.0 if total_negative_abs > 1e-9 else np.nan,
                    "stage014_matched_lot_count": stage014_matched_lots,
                    "stage014_unique_event_count": stage014_unique_events,
                    "stage014_delta_sum": stage014_delta,
                    "stage014_negative_delta_sum": min(0.0, stage014_delta),
                    "stage014_delta_share_of_all_pct": stage014_delta
                    / total_stage014_allocated_delta
                    * 100.0
                    if abs(total_stage014_allocated_delta) > 1e-9
                    else np.nan,
                }
            )
    stats = pd.DataFrame(rows)
    stats["eligible_broad_bucket"] = (
        (pd.to_numeric(stats["events"], errors="coerce") >= 10)
        & (pd.to_numeric(stats["years"], errors="coerce") >= 4)
        & (pd.to_numeric(stats["products"], errors="coerce") >= 5)
    ).astype(int)
    stats["informative_broad_bucket"] = (
        stats["eligible_broad_bucket"].eq(1)
        & (pd.to_numeric(stats["feature_bucket_count"], errors="coerce") > 1)
        & (pd.to_numeric(stats["events"], errors="coerce") < total_lots)
    ).astype(int)
    stats["positive_minus_negative_capture_pp"] = stats["positive_pnl_capture_pct"] - stats["negative_pnl_capture_pct"]
    return stats.sort_values(["eligible_broad_bucket", "official_pnl"], ascending=[False, False]).reset_index(drop=True)


def _select_buckets(stats: pd.DataFrame) -> pd.DataFrame:
    eligible = stats[stats["informative_broad_bucket"].eq(1)].copy()
    if eligible.empty:
        eligible = stats[stats["eligible_broad_bucket"].eq(1)].copy()
    selected_frames: list[pd.DataFrame] = []
    if not eligible.empty:
        selected_frames.append(eligible.sort_values("official_pnl", ascending=False).head(8).assign(selection_reason="top_net_pnl_broad"))
        selected_frames.append(
            eligible.sort_values("positive_minus_negative_capture_pp", ascending=False)
            .head(8)
            .assign(selection_reason="top_right_tail_asymmetry_broad")
        )
        selected_frames.append(
            eligible.sort_values("stage014_negative_delta_sum", ascending=True)
            .head(8)
            .assign(selection_reason="top_stage013_failure_overlap_broad")
        )
        selected_frames.append(eligible.sort_values("negative_pnl").head(8).assign(selection_reason="top_loss_broad"))
    if not selected_frames:
        return pd.DataFrame()
    selected = pd.concat(selected_frames, ignore_index=True, sort=False)
    return selected.drop_duplicates(["feature", "bucket", "selection_reason"]).reset_index(drop=True)


def _feature_bucket_mask(data: pd.DataFrame, feature: str, bucket: str) -> pd.Series:
    if feature not in data.columns:
        return pd.Series(False, index=data.index)
    return data[feature].astype(str).eq(str(bucket))


def _plot_path_chart(curve: pd.DataFrame, features: pd.DataFrame, selected: pd.DataFrame) -> None:
    curve = curve.copy()
    curve["date"] = pd.to_datetime(curve["date"], errors="coerce")
    curve = curve.dropna(subset=["date"]).sort_values("date")
    features = features.copy()
    features["exit_day"] = features["exit_day"].map(_normalize_day)
    fig, axes = plt.subplots(3, 1, figsize=(18, 12), sharex=False, constrained_layout=True)
    axes[0].plot(curve["date"], curve["account_equity"], color="#2563eb", linewidth=1.25, label="Official C9/15w equity")
    marker_rows = (
        features[pd.to_numeric(features.get("stage014_delta_candidate_minus_official"), errors="coerce").fillna(0.0) < 0]
        .sort_values("stage014_delta_candidate_minus_official")
        .head(16)
    )
    for _, row in marker_rows.iterrows():
        axes[0].axvline(row["entry_day"], color="#dc2626", alpha=0.18, linewidth=0.9)
    axes[0].set_title("Official C9/15w path with Stage013 missed-right-tail markers")
    axes[0].legend(loc="best")
    axes[0].grid(True, alpha=0.2)

    axes[1].plot(curve["date"], curve["drawdown_pct"], color="#0f766e", linewidth=1.0, label="Official drawdown pct")
    axes[1].axhline(-40, color="#dc2626", linestyle="--", linewidth=0.8, alpha=0.6)
    axes[1].axhline(-50, color="#7f1d1d", linestyle="--", linewidth=0.8, alpha=0.6)
    axes[1].set_title("Official drawdown")
    axes[1].legend(loc="best")
    axes[1].grid(True, alpha=0.2)

    plotted = 0
    if not selected.empty:
        selected_plot = selected[selected["selection_reason"].isin(["top_net_pnl_broad", "top_stage013_failure_overlap_broad"])]
        selected_plot = selected_plot.drop_duplicates(["feature", "bucket"]).head(10)
        colors = plt.cm.tab10(np.linspace(0, 1, max(1, len(selected_plot))))
        for color, (_, row) in zip(colors, selected_plot.iterrows(), strict=False):
            mask = _feature_bucket_mask(features, str(row["feature"]), str(row["bucket"]))
            group = features[mask].dropna(subset=["exit_day"]).sort_values("exit_day")
            if group.empty:
                continue
            series = group.groupby("exit_day")["realized_pnl"].sum().sort_index().cumsum()
            axes[2].plot(series.index, series.values, linewidth=1.0, color=color, label=f"{row['feature']}={row['bucket']}")
            plotted += 1
    axes[2].axhline(0, color="#334155", linewidth=0.8)
    axes[2].set_title("Read-only cumulative realized PnL by broad pre-entry / entry-instant buckets")
    if plotted:
        axes[2].legend(loc="best", fontsize=7)
    axes[2].grid(True, alpha=0.2)
    fig.savefig(PATH_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_bucket_scatter(stats: pd.DataFrame) -> None:
    data = stats[stats["eligible_broad_bucket"].eq(1)].copy()
    if data.empty:
        data = stats.copy()
    if data.empty:
        return
    x = pd.to_numeric(data["positive_pnl_capture_pct"], errors="coerce")
    y = pd.to_numeric(data["negative_pnl_capture_pct"], errors="coerce")
    size = np.clip(pd.to_numeric(data["events"], errors="coerce").fillna(1.0), 1, 120) * 5
    pnl = pd.to_numeric(data["official_pnl"], errors="coerce").fillna(0.0)
    fig, ax = plt.subplots(figsize=(14, 9), constrained_layout=True)
    scatter = ax.scatter(x, y, s=size, c=pnl, cmap="RdYlGn", alpha=0.75, edgecolor="#334155", linewidth=0.3)
    ax.plot([0, max(1.0, x.max())], [0, max(1.0, x.max())], color="#64748b", linestyle="--", linewidth=0.9)
    label_rows = pd.concat(
        [
            data.sort_values("official_pnl", ascending=False).head(5),
            data.sort_values("stage014_negative_delta_sum").head(5),
            data.sort_values("negative_pnl").head(5),
        ],
        ignore_index=True,
    ).drop_duplicates(["feature", "bucket"])
    for _, row in label_rows.iterrows():
        ax.annotate(
            f"{row['feature']}={row['bucket']}",
            (row["positive_pnl_capture_pct"], row["negative_pnl_capture_pct"]),
            fontsize=7,
            xytext=(4, 4),
            textcoords="offset points",
        )
    ax.set_xlabel("Positive PnL captured (%)")
    ax.set_ylabel("Absolute negative PnL captured (%)")
    ax.set_title("Broad bucket right-tail capture vs loss capture (read-only attribution)")
    ax.grid(True, alpha=0.2)
    fig.colorbar(scatter, ax=ax, label="Official realized PnL")
    fig.savefig(SCATTER_CHART_OUT, dpi=170)
    plt.close(fig)


def _select_atlas_rows(features: pd.DataFrame) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    if "stage014_delta_candidate_minus_official" in features.columns:
        frames.append(
            features[pd.to_numeric(features["stage014_delta_candidate_minus_official"], errors="coerce").notna()]
            .sort_values("stage014_delta_candidate_minus_official")
            .head(8)
        )
    frames.append(features.sort_values("realized_pnl", ascending=False).head(6))
    frames.append(features.sort_values("realized_pnl").head(6))
    selected = pd.concat(frames, ignore_index=True, sort=False)
    return selected.drop_duplicates(["vt_symbol", "entry_date", "direction"]).head(MAX_ATLAS_ROWS)


def _plot_atlas(features: pd.DataFrame, minute_bars: pd.DataFrame) -> tuple[list[Path], pd.DataFrame]:
    selected = _select_atlas_rows(features)
    if selected.empty:
        return [], pd.DataFrame()
    minute_by_symbol = s010.s008.s825._minute_groups(minute_bars)
    pages = int(math.ceil(len(selected) / PER_PAGE))
    paths: list[Path] = []
    manifest: list[dict[str, Any]] = []
    for page in range(1, pages + 1):
        part = selected.iloc[(page - 1) * PER_PAGE : page * PER_PAGE].copy()
        fig, axes = plt.subplots(len(part), 1, figsize=(18, max(4.2, 3.4 * len(part))), constrained_layout=True)
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
                s010.s008.s825._plot_candles(ax, day)
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
                    ax.axvline(29, color="#64748b", linewidth=0.9, alpha=0.7, label="30m")
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
                    f"{vt_symbol} {row.get('direction')} {entry_day:%Y-%m-%d} pnl={_safe_float(row.get('realized_pnl'), 0):,.0f} "
                    f"stage014_delta={_safe_float(row.get('stage014_delta_candidate_minus_official'), 0):,.0f} "
                    f"ctx={row.get('entry_context')} risk={row.get('risk_multiplier_bucket')} "
                    f"rsi={row.get('rsi_bucket')} first={row.get('first_bar_relation_bucket')}"
                ),
                fontsize=8.2,
                loc="left",
            )
            manifest.append(
                {
                    "page": page,
                    "vt_symbol": vt_symbol,
                    "entry_date": entry_day.strftime("%Y-%m-%d"),
                    "direction": row.get("direction", ""),
                    "realized_pnl": _safe_float(row.get("realized_pnl")),
                    "stage014_delta_candidate_minus_official": _safe_float(
                        row.get("stage014_delta_candidate_minus_official")
                    ),
                    "entry_context": row.get("entry_context", ""),
                    "risk_multiplier_bucket": row.get("risk_multiplier_bucket", ""),
                    "rsi_bucket": row.get("rsi_bucket", ""),
                    "first_bar_relation_bucket": row.get("first_bar_relation_bucket", ""),
                    "entry_open_relation_bucket": row.get("entry_open_relation_bucket", ""),
                }
            )
        fig.suptitle("Stage015 pre-entry / entry-instant structure minute-K atlas", fontsize=12)
        path = Path(str(ATLAS_TEMPLATE).format(page=page))
        fig.savefig(path, dpi=170)
        plt.close(fig)
        paths.append(path)
    return paths, pd.DataFrame(manifest)


def _summary(features: pd.DataFrame, stats: pd.DataFrame, selected: pd.DataFrame) -> dict[str, Any]:
    total_positive = float(features["positive_pnl"].sum())
    total_negative = float(features["negative_pnl"].sum())
    broad = stats[stats["eligible_broad_bucket"].eq(1)].copy()
    informative = stats[stats["informative_broad_bucket"].eq(1)].copy()
    analysis_pool = informative if not informative.empty else broad
    best_net = analysis_pool.sort_values("official_pnl", ascending=False).head(1).to_dict("records")
    best_asym = analysis_pool.sort_values("positive_minus_negative_capture_pp", ascending=False).head(1).to_dict("records")
    worst_loss = analysis_pool.sort_values("negative_pnl").head(1).to_dict("records")
    worst_stage014 = analysis_pool.sort_values("stage014_negative_delta_sum").head(1).to_dict("records")
    return {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "official_live_alias": OFFICIAL_LIVE_ALIAS,
        "official_lots": int(len(features)),
        "stage861_entry_instant_available": int(features["entry_instant_minute_available"].sum()),
        "total_official_realized_pnl": float(features["realized_pnl"].fillna(0.0).sum()),
        "total_positive_pnl": total_positive,
        "total_negative_pnl": total_negative,
        "broad_bucket_count": int(len(broad)),
        "informative_broad_bucket_count": int(len(informative)),
        "selected_bucket_count": int(len(selected)),
        "best_net_broad_bucket": best_net[0] if best_net else {},
        "best_right_tail_asymmetry_bucket": best_asym[0] if best_asym else {},
        "worst_loss_broad_bucket": worst_loss[0] if worst_loss else {},
        "worst_stage013_failure_overlap_bucket": worst_stage014[0] if worst_stage014 else {},
        "decision": "stage015_preentry_structure_readonly_no_trade_rule",
    }


def _decision(summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "official_live_alias": OFFICIAL_LIVE_ALIAS,
        "decision": "stage015_preentry_structure_readonly_no_trade_rule",
        "summary": summary,
        "order_api_called": False,
        "ctp_connected": False,
        "external_research_judgment": (
            "Intraday momentum and ORB references support path information, but Stage013 shows post-entry "
            "confirmation can destroy trend-following right tails. Stage015 therefore audits only broad "
            "pre-entry / entry-instant structures before designing any rule."
        ),
        "overfit_reflection_before": (
            "No: this is a read-only attribution over predeclared broad visible fields, with no trade branch."
        ),
        "continue_value_before": (
            "Yes: Stage014 proved the 30m default-minrisk route cuts right-tail exposure; the next useful "
            "question is whether visible entry-time structure explains those right tails."
        ),
        "overfit_reflection_after": (
            "No trade rule is selected. Any attempt to combine the best buckets into a filter without fresh "
            "A/C validation would be overfitting."
        ),
        "continue_value_after": (
            "Useful as an attribution screen; it should only lead to a frozen candidate if a broad bucket is "
            "stable across products and years while preserving right-tail exposure."
        ),
        "outputs": {
            "features": str(FEATURES_OUT),
            "bucket_stats": str(BUCKET_OUT),
            "bucket_year_stats": str(YEAR_OUT),
            "selected_buckets": str(SELECTED_OUT),
            "summary": str(SUMMARY_OUT),
            "path_chart": str(PATH_CHART_OUT),
            "scatter_chart": str(SCATTER_CHART_OUT),
            "atlas_manifest": str(ATLAS_MANIFEST_OUT),
            "report": str(REPORT_OUT),
            "decision": str(DECISION_OUT),
        },
    }


def _write_report(
    summary: dict[str, Any],
    stats: pd.DataFrame,
    selected: pd.DataFrame,
    year_stats: pd.DataFrame,
    atlas_paths: list[Path],
) -> None:
    broad = stats[stats["eligible_broad_bucket"].eq(1)].copy()
    informative = stats[stats["informative_broad_bucket"].eq(1)].copy()
    analysis_pool = informative if not informative.empty else broad
    top_net = analysis_pool.sort_values("official_pnl", ascending=False).head(12)
    top_asym = analysis_pool.sort_values("positive_minus_negative_capture_pp", ascending=False).head(12)
    top_stage014 = analysis_pool.sort_values("stage014_negative_delta_sum").head(12)
    top_loss = analysis_pool.sort_values("negative_pnl").head(12)
    report = "\n".join(
        [
            "# Stage015 pre-entry / entry-instant structure attribution",
            "",
            f"- generated_at: `{datetime.now():%Y-%m-%d %H:%M}`",
            f"- line_id: `{LINE_ID}`",
            f"- official: `{OFFICIAL_LIVE_VERSION}` / `{OFFICIAL_LIVE_ALIAS}`",
            "- type: read-only attribution; no trading rule, no CTP, no order API.",
            "- decision: `stage015_preentry_structure_readonly_no_trade_rule`",
            "",
            "## External Research Judgment",
            "",
            "- Trend-following and intraday-momentum references support using path information, but only when it preserves right-tail exposure.",
            "- Stage014 already falsified a broad post-entry 30m minimum-risk gate, so Stage015 only audits fields visible before or at entry.",
            "",
            "## Summary",
            "",
            _md_table(pd.DataFrame([summary])),
            "",
            "## Top Net Broad Buckets",
            "",
            _md_table(top_net, max_rows=12),
            "",
            "## Top Right-Tail Asymmetry Broad Buckets",
            "",
            _md_table(top_asym, max_rows=12),
            "",
            "## Top Stage013 Failure Overlap Buckets",
            "",
            _md_table(top_stage014, max_rows=12),
            "",
            "## Top Loss Broad Buckets",
            "",
            _md_table(top_loss, max_rows=12),
            "",
            "## Selected Buckets",
            "",
            _md_table(selected.head(32), max_rows=32),
            "",
            "## Output Files",
            "",
            f"- features: `{FEATURES_OUT}`",
            f"- bucket_stats: `{BUCKET_OUT}`",
            f"- bucket_year_stats: `{YEAR_OUT}`",
            f"- selected_buckets: `{SELECTED_OUT}`",
            f"- path chart: `{PATH_CHART_OUT}`",
            f"- scatter chart: `{SCATTER_CHART_OUT}`",
            *[f"- minute atlas: `{path}`" for path in atlas_paths],
            "",
            "## Judgment",
            "",
            "- overfit_reflection_before: `No: read-only broad visible-field attribution, no new trading branch.`",
            "- overfit_reflection_after: `No trade rule selected; combining buckets into a filter without frozen A/C would overfit.`",
            "- continue_value_before: `Yes: Stage014 demands a switch away from post-entry minimum-risk gates.`",
            "- continue_value_after: `Useful as an attribution screen; promotion requires a separate frozen true-engine candidate.`",
        ]
    )
    REPORT_OUT.write_text(report, encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print("[stage015] loading base features and official curve", flush=True)
    features = _prepare_base_features()
    curve = _read_required_csv(CURVE_IN)
    _ = _read_required_csv(SUMMARY_IN)
    ledger = _load_stage014_ledger()
    features = _merge_stage014(features, ledger)

    vt_symbols = sorted(features["vt_symbol"].astype(str).dropna().unique())
    print("[stage015] loading Stage861 full minute bars", flush=True)
    minute_bars = s010.s008.s928._load_stage861_full_minute_bars(vt_symbols)
    features = _add_entry_instant_features(features, minute_bars)

    feature_columns = PREENTRY_FEATURES + ENTRY_INSTANT_FEATURES
    print("[stage015] computing bucket attribution", flush=True)
    year_stats = _bucket_year_stats(features, feature_columns)
    stats = _bucket_stats(features, year_stats, feature_columns)
    selected = _select_buckets(stats)
    summary = _summary(features, stats, selected)
    decision = _decision(summary)

    print("[stage015] plotting charts and atlas", flush=True)
    _plot_path_chart(curve, features, selected)
    _plot_bucket_scatter(stats)
    atlas_paths, atlas_manifest = _plot_atlas(features, minute_bars)

    features.to_csv(FEATURES_OUT, index=False, encoding="utf-8-sig")
    stats.to_csv(BUCKET_OUT, index=False, encoding="utf-8-sig")
    year_stats.to_csv(YEAR_OUT, index=False, encoding="utf-8-sig")
    selected.to_csv(SELECTED_OUT, index=False, encoding="utf-8-sig")
    pd.DataFrame([summary]).to_csv(SUMMARY_OUT, index=False, encoding="utf-8-sig")
    atlas_manifest.to_csv(ATLAS_MANIFEST_OUT, index=False, encoding="utf-8-sig")
    DECISION_OUT.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(summary, stats, selected, year_stats, atlas_paths)

    print(json.dumps(_json_safe(summary), ensure_ascii=False, indent=2), flush=True)
    print(f"[stage015] wrote {OUTPUT_DIR}", flush=True)


if __name__ == "__main__":
    main()
