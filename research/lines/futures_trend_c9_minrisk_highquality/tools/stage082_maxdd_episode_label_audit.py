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
STAGE = "Stage082"
MODEL_TAG = "stage082_maxdd_episode_label_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage082_c9_minrisk_maxdd_episode_label_audit"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
TOOL_DIR = SCRIPT_PATH.parent
EXAMPLE_DIR = REPO_DIR / "examples" / "portfolio_backtesting"
for item in [str(TOOL_DIR), str(EXAMPLE_DIR)]:
    if item not in sys.path:
        sys.path.insert(0, item)

import stage008_no_follow_reduce_true_engine as s008
from qmt_roll_official_live_config import OFFICIAL_LIVE_ALIAS, OFFICIAL_LIVE_VERSION


LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage082_maxdd_episode_label_audit"

FEATURES_IN = (
    LINE_DIR
    / "outputs"
    / "stage024_preentry_risk_granularity_forensics"
    / "qmt_roll_stage024_c9_minrisk_preentry_risk_granularity_forensics_features_"
    "stage024_preentry_risk_granularity_forensics_v1.csv"
)
NOISE_FEATURES_IN = (
    LINE_DIR
    / "outputs"
    / "stage081_noise_floor_stop_distance_audit"
    / "qmt_roll_stage081_c9_minrisk_noise_floor_stop_distance_audit_features_"
    "stage081_noise_floor_stop_distance_audit_v1.csv"
)
OFFICIAL_CURVE_IN = (
    LINE_DIR
    / "outputs"
    / "stage010_authoritative_minute_coverage_audit"
    / "qmt_roll_stage010_c9_minrisk_authoritative_minute_coverage_audit_official_curve_"
    "stage010_authoritative_minute_coverage_audit_v1.csv"
)
OFFICIAL_SUMMARY_IN = (
    LINE_DIR
    / "outputs"
    / "stage010_authoritative_minute_coverage_audit"
    / "qmt_roll_stage010_c9_minrisk_authoritative_minute_coverage_audit_summary_"
    "stage010_authoritative_minute_coverage_audit_v1.csv"
)

FEATURES_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_features_{MODEL_TAG}.csv"
SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
LABEL_SCORECARD_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_label_scorecard_{MODEL_TAG}.csv"
YEAR_MATRIX_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_label_year_matrix_{MODEL_TAG}.csv"
CONTRIBUTION_CURVE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_contribution_curve_{MODEL_TAG}.csv"
ATLAS_MANIFEST_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_atlas_manifest_{MODEL_TAG}.csv"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_maxdd_episode_path_chart_{MODEL_TAG}.png"
LABEL_SCATTER_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_label_loss_capture_scatter_{MODEL_TAG}.png"
LABEL_HEATMAP_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_top_label_year_heatmap_{MODEL_TAG}.png"
ATLAS_TEMPLATE = OUTPUT_DIR / f"{OUTPUT_PREFIX}_atlas_page{{page:03d}}_{MODEL_TAG}.png"

CAPITAL = 150_000.0
MAX_LABELS_FOR_HEATMAP = 12
MAX_ATLAS_ROWS = 16
PER_PAGE = 4
ATLAS_BARS = 120
MIN_PREFLIGHT_LOTS = 20


# These labels were created by Stage023 for forensic decomposition and include
# realized future PnL. They are not live-visible and must never pass a trading
# preflight gate.
OUTCOME_DERIVED_EXCLUDED_LABEL_COLUMNS = {
    "loss_flag",
    "win_flag",
    "active2_loss_flag",
    "stress_loss_flag",
    "active2_stress_loss_flag",
}


BOOLEAN_LABEL_COLUMNS = [
    "clean_continuation_30m",
    "no_follow_30m",
    "entry_instant_minute_available",
    "tag_entry_open_aligned",
    "tag_first_bar_aligned",
    "tag_entry_or_first_aligned",
    "tag_entry_and_first_aligned",
    "tag_ai4_6_entry_open_aligned",
    "tag_ai4_6_first_bar_aligned",
    "tag_ai4_6_entry_or_first_aligned",
    "tag_ai4_6_entry_and_first_aligned",
    "preentry_system_stress_bool",
    "active_2_flag",
    "stress_flag",
    "margin_cap_binding_flag",
    "same_dir_corr_high_flag",
    "long_flag",
    "risk_distance_available_flag",
    "under_noise_floor",
    "noise_ready",
]

CATEGORICAL_LABEL_COLUMNS = [
    "risk_multiplier_bucket",
    "loss_streak_bucket",
    "active_positions_bucket",
    "ai_rank_bucket",
    "rsi_bucket",
    "stop_distance_bucket",
    "portfolio_drawdown_bucket",
    "same_direction_active_bucket",
    "entry_open_relation_bucket",
    "first_bar_relation_bucket",
    "first_bar_body_bucket",
    "first_adverse_wick_bucket",
    "prev_drawdown_bucket",
    "prev_broker_bucket",
    "prev_vol_bucket",
    "prev_active_bucket",
    "preentry_system_stress_bucket",
    "selected_volume_bucket_stage024",
    "contracts_by_risk_bucket_stage024",
    "risk_cash_bucket_stage024",
    "risk_to_target_bucket_stage024",
    "margin_to_risk_contract_bucket_stage024",
    "noise_floor_state",
    "noise_ratio_bucket",
]


def _json_safe(value: Any) -> Any:
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        if np.isnan(value) or np.isinf(value):
            return None
        return float(value)
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value


def _read_required_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise RuntimeError(f"missing required input: {path}")
    return pd.read_csv(path, encoding="utf-8-sig")


def _safe_float(value: Any, default: float = np.nan) -> float:
    try:
        if pd.isna(value):
            return default
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if np.isfinite(number) else default


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
    lines = [
        "| " + " | ".join(str(column) for column in display.columns) + " |",
        "| " + " | ".join(["---"] * len(display.columns)) + " |",
    ]
    for _, row in display.iterrows():
        lines.append("| " + " | ".join(str(row[column]) for column in display.columns) + " |")
    return "\n".join(lines)


def _prepare_curve() -> pd.DataFrame:
    curve = _read_required_csv(OFFICIAL_CURVE_IN)
    curve["date"] = pd.to_datetime(curve["date"], errors="coerce").dt.normalize()
    for column in ["account_equity", "drawdown_pct", "broker10_margin_to_equity_pct"]:
        curve[column] = pd.to_numeric(curve[column], errors="coerce")
    curve = curve.dropna(subset=["date", "account_equity"]).sort_values("date").reset_index(drop=True)
    curve["running_peak_equity"] = curve["account_equity"].cummax()
    trough_idx = int(curve["drawdown_pct"].idxmin())
    trough = curve.loc[trough_idx]
    before = curve.loc[:trough_idx].copy()
    peak_equity = float(before["account_equity"].max())
    peak_candidates = before[before["account_equity"].eq(peak_equity)]
    peak_idx = int(peak_candidates.index[-1])
    peak_date = pd.Timestamp(curve.loc[peak_idx, "date"])
    trough_date = pd.Timestamp(trough["date"])
    after = curve.loc[trough_idx:].copy()
    recovery_rows = after[after["account_equity"].ge(peak_equity)]
    recovery_date = pd.NaT if recovery_rows.empty else pd.Timestamp(recovery_rows.iloc[0]["date"])
    curve["stage082_maxdd_episode"] = curve["date"].between(peak_date, trough_date)
    curve.attrs["maxdd_peak_date"] = peak_date
    curve.attrs["maxdd_trough_date"] = trough_date
    curve.attrs["maxdd_recovery_date"] = recovery_date
    curve.attrs["maxdd_peak_equity"] = peak_equity
    curve.attrs["maxdd_trough_equity"] = float(trough["account_equity"])
    curve.attrs["maxdd_pct"] = float(trough["drawdown_pct"])
    return curve


def _prepare_features(curve: pd.DataFrame) -> pd.DataFrame:
    features = _read_required_csv(FEATURES_IN)
    noise_cols = [
        "lot_id",
        "noise_ready",
        "under_noise_floor",
        "noise_floor_state",
        "noise_ratio_bucket",
        "stop_to_noise_ratio",
    ]
    if NOISE_FEATURES_IN.exists():
        noise = _read_required_csv(NOISE_FEATURES_IN)
        present = [column for column in noise_cols if column in noise.columns]
        if "lot_id" in present:
            features = features.merge(noise[present].drop_duplicates("lot_id"), on="lot_id", how="left")
    for column in ["entry_date", "exit_date"]:
        features[column] = pd.to_datetime(features[column], errors="coerce").dt.normalize()
    for column in [
        "entry_price",
        "realized_pnl",
        "risk_amount",
        "r_multiple",
        "volume",
        "size",
        "stop_distance",
        "big_winner",
        "stage861_covered",
        "first_30m_directional_r",
        "first_30m_mfe_r",
        "first_30m_mae_r",
        "entry_open_gap_r",
        "first_bar_directional_r",
    ]:
        if column in features.columns:
            features[column] = pd.to_numeric(features[column], errors="coerce")
    features["entry_year"] = features["entry_date"].dt.year
    features["product_key"] = features.get("product", features.get("vt_symbol", "missing")).fillna("missing").astype(str)
    features["positive_pnl"] = features["realized_pnl"].where(features["realized_pnl"] > 0.0, 0.0)
    features["negative_pnl"] = features["realized_pnl"].where(features["realized_pnl"] < 0.0, 0.0)
    peak_date = curve.attrs["maxdd_peak_date"]
    trough_date = curve.attrs["maxdd_trough_date"]
    features["stage082_overlap_maxdd_peak_to_trough"] = (
        features["entry_date"].le(trough_date) & features["exit_date"].ge(peak_date)
    )
    features["stage082_exit_in_maxdd_peak_to_trough"] = features["exit_date"].between(peak_date, trough_date)
    features["stage082_entry_in_maxdd_peak_to_trough"] = features["entry_date"].between(peak_date, trough_date)
    features["stage082_maxdd_overlap_negative"] = (
        features["stage082_overlap_maxdd_peak_to_trough"] & features["realized_pnl"].lt(0.0)
    )
    features["stage082_maxdd_loss_abs"] = np.where(
        features["stage082_maxdd_overlap_negative"],
        features["realized_pnl"].abs(),
        0.0,
    )
    features["stage082_maxdd_loss_group"] = np.where(
        features["stage082_maxdd_overlap_negative"],
        "maxdd_overlap_loss",
        np.where(features["stage082_overlap_maxdd_peak_to_trough"], "maxdd_overlap_nonloss", "outside_maxdd_overlap"),
    )
    return features


def _label_masks(features: pd.DataFrame) -> dict[str, pd.Series]:
    masks: dict[str, pd.Series] = {}
    for column in BOOLEAN_LABEL_COLUMNS:
        if column not in features.columns:
            continue
        if column in OUTCOME_DERIVED_EXCLUDED_LABEL_COLUMNS:
            continue
        series = features[column]
        if series.dtype == bool:
            mask = series.fillna(False)
        else:
            numeric = pd.to_numeric(series, errors="coerce")
            if numeric.notna().any():
                mask = numeric.fillna(0).ne(0)
            else:
                mask = series.fillna("").astype(str).str.lower().isin(["true", "1", "yes"])
        masks[f"{column}=1"] = mask.astype(bool)
    for column in CATEGORICAL_LABEL_COLUMNS:
        if column not in features.columns:
            continue
        values = features[column].fillna("missing").astype(str)
        for value in sorted(values.unique()):
            if value in {"", "nan", "None"}:
                continue
            masks[f"{column}={value}"] = values.eq(value)
    return masks


def _label_scorecard(features: pd.DataFrame) -> pd.DataFrame:
    total_loss_abs = float(features["stage082_maxdd_loss_abs"].sum())
    rows: list[dict[str, Any]] = []
    for label, mask in _label_masks(features).items():
        group = features[mask].copy()
        if group.empty:
            continue
        loss_capture = float(group["stage082_maxdd_loss_abs"].sum())
        if loss_capture <= 0.0 and len(group) < 5:
            continue
        positive = float(group["positive_pnl"].sum())
        negative = float(group["negative_pnl"].sum())
        net = float(group["realized_pnl"].sum())
        big_winner_lots = int(pd.to_numeric(group.get("big_winner", 0), errors="coerce").fillna(0).gt(0).sum())
        maxdd_loss_lots = int(group["stage082_maxdd_overlap_negative"].sum())
        rows.append(
            {
                "label": label,
                "lots": int(len(group)),
                "products": int(group["product_key"].nunique()),
                "entry_years": int(group["entry_year"].nunique()),
                "net_pnl": net,
                "positive_pnl": positive,
                "negative_pnl": negative,
                "big_winner_lots": big_winner_lots,
                "maxdd_loss_lots": maxdd_loss_lots,
                "maxdd_loss_capture_abs": loss_capture,
                "maxdd_loss_capture_pct": loss_capture / total_loss_abs * 100.0 if total_loss_abs else np.nan,
                "right_tail_to_loss_capture": positive / loss_capture if loss_capture > 0.0 else np.nan,
                "net_to_loss_capture": net / loss_capture if loss_capture > 0.0 else np.nan,
                "preflight_pass": bool(
                    total_loss_abs
                    and loss_capture / total_loss_abs >= 0.20
                    and len(group) >= MIN_PREFLIGHT_LOTS
                    and net <= 0.0
                    and positive <= loss_capture
                    and big_winner_lots == 0
                    and group["product_key"].nunique() >= 5
                    and group["entry_year"].nunique() >= 4
                ),
            }
        )
    score = pd.DataFrame(rows)
    if score.empty:
        return score
    return score.sort_values(
        ["preflight_pass", "maxdd_loss_capture_pct", "net_pnl"],
        ascending=[False, False, True],
    ).reset_index(drop=True)


def _year_matrix(features: pd.DataFrame, score: pd.DataFrame) -> pd.DataFrame:
    if score.empty:
        return pd.DataFrame()
    top_labels = score.head(MAX_LABELS_FOR_HEATMAP)["label"].tolist()
    masks = _label_masks(features)
    rows: list[dict[str, Any]] = []
    for label in top_labels:
        mask = masks.get(label)
        if mask is None:
            continue
        group = features[mask].copy()
        for year, year_group in group.groupby("entry_year"):
            rows.append(
                {
                    "label": label,
                    "entry_year": int(year),
                    "lots": int(len(year_group)),
                    "net_pnl": float(year_group["realized_pnl"].sum()),
                    "maxdd_loss_capture_abs": float(year_group["stage082_maxdd_loss_abs"].sum()),
                    "big_winner_lots": int(
                        pd.to_numeric(year_group.get("big_winner", 0), errors="coerce").fillna(0).gt(0).sum()
                    ),
                }
            )
    return pd.DataFrame(rows).sort_values(["label", "entry_year"]).reset_index(drop=True)


def _contribution_curve(features: pd.DataFrame, curve: pd.DataFrame) -> pd.DataFrame:
    records = features.copy()
    records["date"] = records["exit_date"]
    records["maxdd_overlap_loss_pnl"] = np.where(records["stage082_maxdd_overlap_negative"], records["realized_pnl"], 0.0)
    records["maxdd_overlap_nonloss_pnl"] = np.where(
        records["stage082_overlap_maxdd_peak_to_trough"] & ~records["stage082_maxdd_overlap_negative"],
        records["realized_pnl"],
        0.0,
    )
    records["outside_pnl"] = np.where(~records["stage082_overlap_maxdd_peak_to_trough"], records["realized_pnl"], 0.0)
    daily = (
        records.groupby("date", as_index=False)[
            ["realized_pnl", "maxdd_overlap_loss_pnl", "maxdd_overlap_nonloss_pnl", "outside_pnl"]
        ]
        .sum()
        .rename(columns={"realized_pnl": "closed_lot_realized_pnl"})
    )
    out = curve.merge(daily, on="date", how="left")
    for column in ["closed_lot_realized_pnl", "maxdd_overlap_loss_pnl", "maxdd_overlap_nonloss_pnl", "outside_pnl"]:
        out[column] = out[column].fillna(0.0)
        out[f"cumulative_{column}"] = out[column].cumsum()
    out.attrs.update(curve.attrs)
    return out


def _summary(features: pd.DataFrame, curve: pd.DataFrame, official_summary: pd.DataFrame, score: pd.DataFrame) -> pd.DataFrame:
    official = official_summary.copy()
    for column in official.columns:
        if column not in {"arm", "stage", "model_tag", "line_id", "window_id", "variant", "label", "note"}:
            converted = pd.to_numeric(official[column], errors="coerce")
            if converted.notna().any():
                official[column] = converted
    base = official.iloc[0].to_dict() if len(official) else {}
    overlap = features[features["stage082_overlap_maxdd_peak_to_trough"]]
    overlap_loss = features[features["stage082_maxdd_overlap_negative"]]
    pass_count = int(score["preflight_pass"].sum()) if not score.empty and "preflight_pass" in score else 0
    return pd.DataFrame(
        [
            {
                "stage": STAGE,
                "official_live_version": OFFICIAL_LIVE_VERSION,
                "official_live_alias": OFFICIAL_LIVE_ALIAS,
                "end_equity": _safe_float(base.get("end_equity")),
                "total_return_pct": _safe_float(base.get("total_return_pct")),
                "max_dd_pct": _safe_float(base.get("max_dd_pct")),
                "sharpe": _safe_float(base.get("sharpe")),
                "total_slippage": _safe_float(base.get("total_slippage")),
                "total_trade_count": _safe_float(base.get("total_trade_count")),
                "win_rate_pct": _safe_float(base.get("nonzero_daily_win_rate_pct")),
                "max_broker10_margin_to_equity_pct": _safe_float(base.get("max_broker10_margin_to_equity_pct")),
                "maxdd_peak_date": curve.attrs["maxdd_peak_date"].date().isoformat(),
                "maxdd_trough_date": curve.attrs["maxdd_trough_date"].date().isoformat(),
                "maxdd_recovery_date": ""
                if pd.isna(curve.attrs["maxdd_recovery_date"])
                else curve.attrs["maxdd_recovery_date"].date().isoformat(),
                "maxdd_peak_equity": curve.attrs["maxdd_peak_equity"],
                "maxdd_trough_equity": curve.attrs["maxdd_trough_equity"],
                "maxdd_curve_dd_pct": curve.attrs["maxdd_pct"],
                "closed_lots": int(len(features)),
                "overlap_lots": int(len(overlap)),
                "overlap_net_pnl": float(overlap["realized_pnl"].sum()),
                "overlap_loss_lots": int(len(overlap_loss)),
                "overlap_loss_abs": float(overlap_loss["realized_pnl"].abs().sum()),
                "overlap_loss_net_pnl": float(overlap_loss["realized_pnl"].sum()),
                "overlap_loss_products": int(overlap_loss["product_key"].nunique()),
                "overlap_loss_years": int(overlap_loss["entry_year"].nunique()),
                "candidate_label_count": int(len(score)),
                "preflight_pass_label_count": pass_count,
            }
        ]
    )


def _decision(summary: pd.DataFrame, score: pd.DataFrame) -> dict[str, Any]:
    row = summary.iloc[0].to_dict()
    pass_labels = score[score["preflight_pass"].astype(bool)] if not score.empty else pd.DataFrame()
    if not pass_labels.empty:
        label = "stage082_existing_label_promising_but_needs_nonfit_true_engine_gate"
        main = "one_or_more_visible_labels_passed_strict_preflight"
    else:
        label = "stage082_no_existing_visible_label_isolates_maxdd_without_righttail_damage"
        main = "maxdd_losses_not_separable_by_existing_visible_labels"
    return {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "official_live_alias": OFFICIAL_LIVE_ALIAS,
        "stage_type": "readonly_maxdd_episode_label_audit",
        "candidate_rule_tested": False,
        "ab_triggered": False,
        "decision": label,
        "main_conclusion": main,
        "summary": row,
        "top_labels": score.head(10).to_dict("records") if not score.empty else [],
        "pass_flags": {
            "any_label_passes_preflight": bool(not pass_labels.empty),
            "no_direct_true_engine": True,
            "visual_outputs_generated": True,
        },
        "preflight_controls": {
            "min_preflight_lots": MIN_PREFLIGHT_LOTS,
            "excluded_outcome_derived_labels": sorted(OUTCOME_DERIVED_EXCLUDED_LABEL_COLUMNS),
            "exclusion_reason": "future_realized_pnl_or_win_loss_label_not_live_visible",
        },
        "external_research_judgment": (
            "Trend-following evidence emphasizes right-tail concentration and acceptance of drawdowns. Stage082 "
            "therefore asks whether max-drawdown losses are separable by already documented live-visible labels, "
            "excluding any future outcome labels, before writing any new execution rule."
        ),
        "overfit_reflection_before": (
            "No: this is an episode attribution using the realized official max drawdown window and a fixed list of "
            "previously documented live-visible labels. Outcome-derived loss/win labels are explicitly excluded, and "
            "the audit does not create a threshold, product, direction, year, or month branch."
        ),
        "continue_value_before": (
            "Yes: repeated true-engine failures suggest the next useful work is to prove whether max drawdown has a "
            "right-tail-safe observable cause, not to keep adding small exit rules."
        ),
        "overfit_reflection_after": "",
        "continue_value_after": "",
        "order_api_called": False,
        "ctp_connected": False,
        "outputs": {
            "features": str(FEATURES_OUT),
            "summary": str(SUMMARY_OUT),
            "label_scorecard": str(LABEL_SCORECARD_OUT),
            "year_matrix": str(YEAR_MATRIX_OUT),
            "contribution_curve": str(CONTRIBUTION_CURVE_OUT),
            "path_chart": str(PATH_CHART_OUT),
            "label_scatter": str(LABEL_SCATTER_OUT),
            "label_heatmap": str(LABEL_HEATMAP_OUT),
            "atlas_manifest": str(ATLAS_MANIFEST_OUT),
            "report": str(REPORT_OUT),
            "decision": str(DECISION_OUT),
        },
    }


def _plot_path(curve: pd.DataFrame) -> None:
    data = curve.copy()
    peak = data.attrs["maxdd_peak_date"]
    trough = data.attrs["maxdd_trough_date"]
    fig, axes = plt.subplots(4, 1, figsize=(14, 12), sharex=True)
    axes[0].plot(data["date"], data["account_equity"], color="#111827", linewidth=1.3, label="official equity")
    axes[0].axvspan(peak, trough, color="#f97316", alpha=0.16, label="maxDD peak-to-trough")
    axes[0].set_title("Stage082 Official MaxDD Episode Attribution")
    axes[0].set_ylabel("Equity")
    axes[0].legend(loc="upper left")

    axes[1].plot(data["date"], data["drawdown_pct"], color="#dc2626", linewidth=1.0, label="official drawdown %")
    axes[1].axvspan(peak, trough, color="#f97316", alpha=0.16)
    axes[1].axhline(data.attrs["maxdd_pct"], color="#7f1d1d", linewidth=0.8, linestyle="--")
    axes[1].set_ylabel("Drawdown %")
    axes[1].legend(loc="lower left")

    axes[2].plot(data["date"], data["broker10_margin_to_equity_pct"], color="#7c3aed", linewidth=1.0, label="broker10 %")
    axes[2].axhline(100.0, color="#991b1b", linewidth=0.8, linestyle="--", alpha=0.7)
    axes[2].axvspan(peak, trough, color="#f97316", alpha=0.16)
    axes[2].set_ylabel("Broker10 %")
    axes[2].legend(loc="upper left")

    axes[3].plot(
        data["date"],
        data["cumulative_maxdd_overlap_loss_pnl"],
        color="#dc2626",
        linewidth=1.1,
        label="cum pnl: maxDD overlap losses",
    )
    axes[3].plot(
        data["date"],
        data["cumulative_maxdd_overlap_nonloss_pnl"],
        color="#0f766e",
        linewidth=1.1,
        label="cum pnl: maxDD overlap non-loss",
    )
    axes[3].plot(data["date"], data["cumulative_outside_pnl"], color="#64748b", linewidth=0.9, label="cum pnl: outside")
    axes[3].axhline(0.0, color="#6b7280", linewidth=0.8)
    axes[3].axvspan(peak, trough, color="#f97316", alpha=0.16)
    axes[3].set_ylabel("Closed-lot PnL")
    axes[3].legend(loc="upper left", ncol=2)
    for ax in axes:
        ax.grid(True, alpha=0.22)
    fig.tight_layout()
    fig.savefig(PATH_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_label_scatter(score: pd.DataFrame) -> None:
    if score.empty:
        return
    data = score.copy()
    data["plot_tail_ratio"] = data["right_tail_to_loss_capture"].replace([np.inf, -np.inf], np.nan).clip(0, 20)
    colors = np.where(data["preflight_pass"], "#16a34a", "#ea580c")
    sizes = 28 + np.minimum(pd.to_numeric(data["big_winner_lots"], errors="coerce").fillna(0), 20) * 8
    fig, axes = plt.subplots(1, 2, figsize=(14, 5.8))
    axes[0].scatter(data["maxdd_loss_capture_pct"], data["net_pnl"], c=colors, s=sizes, alpha=0.75, edgecolors="none")
    axes[0].axhline(0.0, color="#6b7280", linewidth=0.8)
    axes[0].axvline(20.0, color="#111827", linewidth=0.8, linestyle="--")
    axes[0].set_xlabel("MaxDD overlap loss capture %")
    axes[0].set_ylabel("Full-sample net PnL if label acted on")
    axes[0].set_title("Existing Labels: Loss Capture vs Net PnL")
    axes[0].grid(True, alpha=0.2)

    axes[1].scatter(data["maxdd_loss_capture_pct"], data["plot_tail_ratio"], c=colors, s=sizes, alpha=0.75, edgecolors="none")
    axes[1].axhline(1.0, color="#111827", linewidth=0.8, linestyle="--")
    axes[1].axvline(20.0, color="#111827", linewidth=0.8, linestyle="--")
    axes[1].set_xlabel("MaxDD overlap loss capture %")
    axes[1].set_ylabel("Positive PnL / captured MaxDD loss")
    axes[1].set_title("Right-Tail Damage Guard")
    axes[1].grid(True, alpha=0.2)
    fig.tight_layout()
    fig.savefig(LABEL_SCATTER_OUT, dpi=160)
    plt.close(fig)


def _plot_label_heatmap(year_matrix: pd.DataFrame, score: pd.DataFrame) -> None:
    if year_matrix.empty or score.empty:
        return
    top_labels = score.head(MAX_LABELS_FOR_HEATMAP)["label"].tolist()
    pivot = year_matrix[year_matrix["label"].isin(top_labels)].pivot_table(
        index="label",
        columns="entry_year",
        values="net_pnl",
        aggfunc="sum",
        fill_value=0.0,
    )
    pivot = pivot.reindex(top_labels)
    fig, ax = plt.subplots(figsize=(14, max(5.5, 0.42 * len(pivot))))
    matrix = pivot.to_numpy(dtype="float64")
    limit = np.nanmax(np.abs(matrix)) if matrix.size else 1.0
    im = ax.imshow(matrix, cmap="RdYlGn", aspect="auto", vmin=-limit, vmax=limit)
    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels([str(int(column)) for column in pivot.columns], rotation=0)
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels(pivot.index, fontsize=8)
    ax.set_title("Stage082 Top Loss-Capture Labels: Net PnL By Entry Year")
    for i in range(matrix.shape[0]):
        for j in range(matrix.shape[1]):
            ax.text(j, i, f"{matrix[i, j]/10000:.0f}w", ha="center", va="center", fontsize=7, color="#111827")
    fig.colorbar(im, ax=ax, fraction=0.025, pad=0.02, label="net pnl")
    fig.tight_layout()
    fig.savefig(LABEL_HEATMAP_OUT, dpi=160)
    plt.close(fig)


def _atlas_rows(features: pd.DataFrame, score: pd.DataFrame) -> pd.DataFrame:
    top_losses = (
        features[features["stage082_maxdd_overlap_negative"]]
        .sort_values("realized_pnl", ascending=True)
        .head(6)
        .assign(stage082_atlas_group="maxdd_overlap_losers")
    )
    labels = score.head(5)["label"].tolist() if not score.empty else []
    masks = _label_masks(features)
    conflict_mask = pd.Series(False, index=features.index)
    for label in labels:
        if label in masks:
            conflict_mask = conflict_mask | masks[label]
    conflicts = (
        features[conflict_mask & features["realized_pnl"].gt(0)]
        .sort_values("realized_pnl", ascending=False)
        .head(6)
        .assign(stage082_atlas_group="right_tail_conflicts")
    )
    neutral = (
        features[features["stage082_overlap_maxdd_peak_to_trough"] & features["realized_pnl"].ge(0)]
        .sort_values("realized_pnl", ascending=False)
        .head(4)
        .assign(stage082_atlas_group="maxdd_overlap_winners")
    )
    rows = pd.concat([top_losses, conflicts, neutral], ignore_index=True, sort=False)
    rows = rows.drop_duplicates(subset=["vt_symbol", "entry_date", "direction", "entry_price"]).head(MAX_ATLAS_ROWS)
    return rows.reset_index(drop=True)


def _minute_map(minute_bars: pd.DataFrame) -> dict[tuple[str, pd.Timestamp], pd.DataFrame]:
    data = minute_bars.copy()
    data["bar_datetime"] = pd.to_datetime(data["bar_datetime"], errors="coerce")
    data["bar_date"] = pd.to_datetime(data["bar_date"], errors="coerce").dt.normalize()
    for column in ["open", "high", "low", "close"]:
        data[column] = pd.to_numeric(data[column], errors="coerce")
    out: dict[tuple[str, pd.Timestamp], pd.DataFrame] = {}
    for key, group in data.dropna(subset=["vt_symbol", "bar_date", "bar_datetime"]).groupby(["vt_symbol", "bar_date"]):
        out[(str(key[0]), pd.Timestamp(key[1]).normalize())] = group.sort_values("bar_datetime").reset_index(drop=True)
    return out


def _plot_atlas(features: pd.DataFrame, score: pd.DataFrame) -> tuple[list[Path], pd.DataFrame]:
    rows = _atlas_rows(features, score)
    if rows.empty:
        return [], pd.DataFrame()
    vt_symbols = set(rows["vt_symbol"].dropna().astype(str).unique())
    minute_bars = s008.s928._load_stage861_full_minute_bars(vt_symbols)
    minute_by_key = _minute_map(minute_bars)
    manifest_rows: list[dict[str, Any]] = []
    paths: list[Path] = []
    page_count = int(np.ceil(len(rows) / PER_PAGE))
    for page in range(page_count):
        subset = rows.iloc[page * PER_PAGE : (page + 1) * PER_PAGE].reset_index(drop=True)
        fig, axes = plt.subplots(len(subset), 1, figsize=(13, 3.6 * len(subset)), squeeze=False)
        for row_idx, row in subset.iterrows():
            ax = axes[row_idx][0]
            key = (str(row["vt_symbol"]), pd.Timestamp(row["entry_date"]).normalize())
            day = minute_by_key.get(key, pd.DataFrame()).copy()
            if not day.empty:
                day = day.head(ATLAS_BARS)
                x = pd.to_datetime(day["bar_datetime"], errors="coerce")
                ax.plot(x, day["close"], color="#111827", linewidth=1.1, label="close")
                ax.fill_between(x, day["low"], day["high"], color="#94a3b8", alpha=0.20, linewidth=0)
            entry = _safe_float(row.get("entry_price"))
            stop_distance = _safe_float(row.get("stop_distance"))
            sign = 1.0 if str(row.get("direction")) == "long" else -1.0
            stop = entry - sign * stop_distance if np.isfinite(entry) and np.isfinite(stop_distance) else np.nan
            if np.isfinite(entry):
                ax.axhline(entry, color="#2563eb", linewidth=0.9, label="entry")
            if np.isfinite(stop):
                ax.axhline(stop, color="#dc2626", linewidth=0.9, linestyle="--", label="official stop")
            title = (
                f"{row.get('stage082_atlas_group')} | {row.get('vt_symbol')} {row.get('direction')} "
                f"{pd.Timestamp(row.get('entry_date')).date()} | pnl={_safe_float(row.get('realized_pnl')):,.0f} "
                f"maxdd_loss={_safe_float(row.get('stage082_maxdd_loss_abs')):,.0f}"
            )
            ax.set_title(title, fontsize=10)
            ax.grid(True, alpha=0.22)
            ax.legend(loc="upper left", fontsize=8, ncol=3)
            manifest_rows.append(
                {
                    "page": page + 1,
                    "row": row_idx + 1,
                    "lot_id": row.get("lot_id"),
                    "vt_symbol": row.get("vt_symbol"),
                    "entry_date": pd.Timestamp(row.get("entry_date")).date().isoformat(),
                    "direction": row.get("direction"),
                    "atlas_group": row.get("stage082_atlas_group"),
                    "realized_pnl": _safe_float(row.get("realized_pnl")),
                    "stage082_maxdd_loss_abs": _safe_float(row.get("stage082_maxdd_loss_abs")),
                    "minute_rows_plotted": int(len(day)) if not day.empty else 0,
                }
            )
        fig.tight_layout()
        path = Path(str(ATLAS_TEMPLATE).format(page=page + 1))
        fig.savefig(path, dpi=150)
        plt.close(fig)
        paths.append(path)
    return paths, pd.DataFrame(manifest_rows)


def _write_report(
    summary: pd.DataFrame,
    score: pd.DataFrame,
    year_matrix: pd.DataFrame,
    decision: dict[str, Any],
    atlas_paths: list[Path],
) -> None:
    summary_cols = [
        "end_equity",
        "total_return_pct",
        "max_dd_pct",
        "sharpe",
        "total_slippage",
        "total_trade_count",
        "win_rate_pct",
        "maxdd_peak_date",
        "maxdd_trough_date",
        "maxdd_curve_dd_pct",
        "overlap_lots",
        "overlap_net_pnl",
        "overlap_loss_lots",
        "overlap_loss_abs",
        "preflight_pass_label_count",
    ]
    score_cols = [
        "label",
        "lots",
        "products",
        "entry_years",
        "net_pnl",
        "positive_pnl",
        "negative_pnl",
        "big_winner_lots",
        "maxdd_loss_lots",
        "maxdd_loss_capture_pct",
        "right_tail_to_loss_capture",
        "preflight_pass",
    ]
    lines = [
        "# Stage082 最大回撤 episode 可见标签审计",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M')}`",
        f"- line_id：`{LINE_ID}`",
        f"- 当前官方正式版本：`{OFFICIAL_LIVE_VERSION}` / `{OFFICIAL_LIVE_ALIAS}`",
        "- 阶段性质：只读 maxDD episode attribution；不写真引擎、不新增交易规则、不触发 A/B、不连接 CTP、不调用订单 API。",
        "- 预声明问题：最大回撤 peak-to-trough 里的亏损，是否能被已有 live-visible / entry-time 标签捕获，同时不覆盖 C9 右尾。",
        f"- 审计闸门：剔除 `{sorted(OUTCOME_DERIVED_EXCLUDED_LABEL_COLUMNS)}` 等未来盈亏派生标签；preflight 最低样本量 `{MIN_PREFLIGHT_LOTS}` 笔。",
        "",
        "## 外部调研与判断",
        "",
        "- 趋势跟随资料强调右尾集中和短期回撤不可避免；因此任何低回撤规则必须先通过右尾保护审计。",
        "- 本阶段只检查已存在标签，不新增阈值，不按产品、年份、方向或月份救参。",
        "",
        "## Summary",
        "",
        _md_table(summary[summary_cols], max_rows=5),
        "",
        "## Label Scorecard",
        "",
        _md_table(score[score_cols], max_rows=30) if not score.empty else "_empty_",
        "",
        "## Top Label Year Matrix",
        "",
        _md_table(year_matrix, max_rows=60) if not year_matrix.empty else "_empty_",
        "",
        "## Visual Outputs",
        "",
        f"- maxDD path chart：`{PATH_CHART_OUT}`",
        f"- label scatter：`{LABEL_SCATTER_OUT}`",
        f"- label/year heatmap：`{LABEL_HEATMAP_OUT}`",
        *[f"- minute atlas：`{path}`" for path in atlas_paths],
        "",
        "## Decision",
        "",
        f"- 决策：`{decision['decision']}`",
        f"- 主结论：`{decision['main_conclusion']}`",
        f"- 过拟合反思：`{decision['overfit_reflection_after']}`",
        f"- 继续价值：`{decision['continue_value_after']}`",
    ]
    REPORT_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print("[stage082] loading official curve and features", flush=True)
    curve = _prepare_curve()
    features = _prepare_features(curve)
    official_summary = _read_required_csv(OFFICIAL_SUMMARY_IN)
    print("[stage082] building label scorecard", flush=True)
    score = _label_scorecard(features)
    year_matrix = _year_matrix(features, score)
    contribution = _contribution_curve(features, curve)
    summary = _summary(features, curve, official_summary, score)
    decision = _decision(summary, score)
    if decision["decision"] == "stage082_existing_label_promising_but_needs_nonfit_true_engine_gate":
        decision["overfit_reflection_after"] = (
            "No threshold search occurred, but any next step must freeze exactly one label and pass A/B discipline "
            "before a true engine. Do not combine labels after seeing this scorecard."
        )
        decision["continue_value_after"] = (
            "Yes, but only as a separate frozen preflight with version-ab-experiment discipline; no immediate promotion."
        )
    else:
        decision["overfit_reflection_after"] = (
            "No: the audit used a fixed official maxDD window and previously documented labels. Trying to combine "
            "near-miss labels or tune buckets after seeing the scatter would be overfitting."
        )
        decision["continue_value_after"] = (
            "No for existing visible labels as maxDD reducers; continue only with genuinely new external point-in-time "
            "sources or account-level fixed rules that do not alter C9 single-trade right tails."
        )

    print("[stage082] plotting visuals", flush=True)
    _plot_path(contribution)
    _plot_label_scatter(score)
    _plot_label_heatmap(year_matrix, score)
    atlas_paths, atlas_manifest = _plot_atlas(features, score)

    features.to_csv(FEATURES_OUT, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_OUT, index=False, encoding="utf-8-sig")
    score.to_csv(LABEL_SCORECARD_OUT, index=False, encoding="utf-8-sig")
    year_matrix.to_csv(YEAR_MATRIX_OUT, index=False, encoding="utf-8-sig")
    contribution.to_csv(CONTRIBUTION_CURVE_OUT, index=False, encoding="utf-8-sig")
    atlas_manifest.to_csv(ATLAS_MANIFEST_OUT, index=False, encoding="utf-8-sig")
    _write_report(summary, score, year_matrix, decision, atlas_paths)
    DECISION_OUT.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"[stage082] decision={decision['decision']}", flush=True)
    print(f"[stage082] summary={SUMMARY_OUT}", flush=True)
    print(f"[stage082] path_chart={PATH_CHART_OUT}", flush=True)


if __name__ == "__main__":
    main()
