from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import sys
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


LINE_ID = "futures_trend_c9_minrisk_highquality"
STAGE = "Stage249"
MODEL_TAG = "stage249_early_runway_frontier_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage249_c9_minrisk_early_runway_frontier_audit"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
TOOLS_DIR = SCRIPT_PATH.parent
EXAMPLE_DIR = REPO_DIR / "examples" / "portfolio_backtesting"
for path in [str(TOOLS_DIR), str(EXAMPLE_DIR)]:
    if path not in sys.path:
        sys.path.insert(0, path)

import stage038_order_event_replay_prototype_audit as s038  # noqa: E402
import stage045_event_time_field_sync_audit as s045  # noqa: E402
import stage100_absorption_reclaim_preflight as s100  # noqa: E402


LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage249_early_runway_frontier_audit"

STAGE248_DIR = LINE_DIR / "outputs" / "stage248_close_dwell_acceptance_preflight"
STAGE248_PREFIX = "qmt_roll_stage248_c9_minrisk_close_dwell_acceptance_preflight"
STAGE248_TAG = "stage248_close_dwell_acceptance_preflight_v1"
STAGE248_ROWS_IN = STAGE248_DIR / f"{STAGE248_PREFIX}_dwell_rows_{STAGE248_TAG}.csv"

STAGE239_DIR = LINE_DIR / "outputs" / "stage239_read_only_universal_signal_quality_audit"
STAGE239_PREFIX = "qmt_roll_stage239_c9_minrisk_read_only_universal_signal_quality_audit"
STAGE239_TAG = "stage239_read_only_universal_signal_quality_audit_v1"
STAGE239_JOINED_IN = STAGE239_DIR / f"{STAGE239_PREFIX}_joined_signal_label_audit_{STAGE239_TAG}.csv"

ROWS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_frontier_rows_{MODEL_TAG}.csv"
FRONTIER_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_frontier_summary_{MODEL_TAG}.csv"
EVENT_BUCKET_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_event_bucket_summary_{MODEL_TAG}.csv"
FEATURE_SIGNAL_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_predecision_feature_signal_summary_{MODEL_TAG}.csv"
PROMOTION_GATE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_promotion_gate_{MODEL_TAG}.csv"
SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
ATLAS_MANIFEST_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_atlas_manifest_{MODEL_TAG}.csv"

OFFICIAL_PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_frontier_chart_{MODEL_TAG}.png"
FRONTIER_CONTRIBUTION_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_frontier_contribution_chart_{MODEL_TAG}.png"
EVENT_BUCKET_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_event_bucket_chart_{MODEL_TAG}.png"
FEATURE_CAPTURE_HEATMAP_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_predecision_feature_capture_heatmap_{MODEL_TAG}.png"
PROMOTION_GATE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_promotion_gate_chart_{MODEL_TAG}.png"
ATLAS_TEMPLATE = OUTPUT_DIR / f"{OUTPUT_PREFIX}_atlas_page{{page:03d}}_{MODEL_TAG}.png"

EARLY_STATES = {"first_bar_event_no_closed_dwell", "short_runway_le5_no_dwell"}
ATLAS_ROWS = 24
ATLAS_PER_PAGE = 4
MAX_ATLAS_BARS = 90

FEATURES = [
    ("aligned_bar_return_1m", "quality_quintile_aligned_bar_return_1m"),
    ("low_range_ratio_1m", "quality_quintile_low_range_ratio_1m"),
    ("directional_efficiency_30m", "quality_quintile_directional_efficiency_30m"),
    ("low_realized_volatility_30m", "quality_quintile_low_realized_volatility_30m"),
    ("volume_participation_30m", "quality_quintile_volume_participation_30m"),
    ("volume_zscore_60m", "quality_quintile_volume_zscore_60m"),
    ("aligned_turnover_vwap_gap_30m", "quality_quintile_aligned_turnover_vwap_gap_30m"),
]

FRONTIER_COLORS = {
    "early_no_dwell": "#7c3aed",
    "adequate_dwell": "#0f766e",
}


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise RuntimeError(f"missing required input: {path}")
    return pd.read_csv(path, encoding="utf-8-sig")


def _write_csv(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, encoding="utf-8-sig")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(s045._json_safe(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s038._md_table(frame, max_rows=max_rows)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if np.isfinite(number) else default


def _load_joined_rows() -> pd.DataFrame:
    rows = _read_csv(STAGE248_ROWS_IN)
    feature = _read_csv(STAGE239_JOINED_IN)
    keep_cols = ["candidate_index"] + [column for _name, column in FEATURES if column in feature.columns]
    keep_cols += [
        "risk_bad_label",
        "ordinary_clean_label",
        "low_resolution_label",
        "event_time_missing_label",
    ]
    keep_cols = list(dict.fromkeys([column for column in keep_cols if column in feature.columns]))
    data = rows.merge(feature[keep_cols], on="candidate_index", how="left", validate="one_to_one")
    data["official_open_date"] = pd.to_datetime(data["official_open_date"], errors="coerce").dt.normalize()
    data["early_runway_no_dwell"] = data["dwell_state"].isin(EARLY_STATES).astype(int)
    data["frontier_bucket"] = np.where(data["early_runway_no_dwell"].eq(1), "early_no_dwell", "adequate_dwell")
    data["early_progress"] = (data["early_runway_no_dwell"].eq(1) & data["replay_c9_first_event"].astype(str).eq("progress")).astype(int)
    data["early_stop"] = (data["early_runway_no_dwell"].eq(1) & data["replay_c9_first_event"].astype(str).eq("stop")).astype(int)
    event_idx = pd.to_numeric(data["event_bar_idx"], errors="coerce")
    data["event_bucket"] = np.select(
        [
            event_idx.le(0),
            event_idx.gt(0) & event_idx.le(5),
            event_idx.gt(5),
            event_idx.isna(),
        ],
        ["first_bar_event", "bar1_to_5_event", "gt5_bar_event", "no_event_or_unknown"],
        default="no_event_or_unknown",
    )
    data["selected_for_stage249_atlas"] = 0
    selected: set[int] = set()
    early = data[data["early_runway_no_dwell"].eq(1)]
    selected.update(early[early["right_tail_visual"].eq(1)].sort_values("pnl_rank_desc").head(10).index)
    selected.update(early[early["bottom_loss_visual"].eq(1)].sort_values("pnl_rank_asc").head(10).index)
    selected.update(data[data["maxdd_context"].eq(1)].sort_values(["early_runway_no_dwell", "order_realized_pnl"], ascending=[False, True]).head(6).index)
    if selected:
        data.loc[list(selected)[:ATLAS_ROWS], "selected_for_stage249_atlas"] = 1
    return data.sort_values(["official_open_date", "candidate_index"]).reset_index(drop=True)


def _frontier_summary(rows: pd.DataFrame) -> pd.DataFrame:
    summary = (
        rows.groupby("frontier_bucket", dropna=False)
        .agg(
            order_count=("candidate_index", "count"),
            product_count=("product", "nunique"),
            year_count=("decision_year", "nunique"),
            pnl_sum=("order_realized_pnl", "sum"),
            pnl_mean=("order_realized_pnl", "mean"),
            pnl_min=("order_realized_pnl", "min"),
            pnl_max=("order_realized_pnl", "max"),
            positive_order_count=("order_realized_pnl", lambda values: int((pd.to_numeric(values, errors="coerce") > 0).sum())),
            negative_order_count=("order_realized_pnl", lambda values: int((pd.to_numeric(values, errors="coerce") < 0).sum())),
            right_tail_count=("right_tail_visual", "sum"),
            bottom_loss_count=("bottom_loss_visual", "sum"),
            maxdd_context_count=("maxdd_context", "sum"),
            progress_count=("replay_c9_first_event", lambda values: int((values.astype(str) == "progress").sum())),
            stop_count=("replay_c9_first_event", lambda values: int((values.astype(str) == "stop").sum())),
            median_event_bar_idx=("event_bar_idx", "median"),
            median_pre_event_mfe_r=("pre_event_mfe_r", "median"),
            median_pre_event_mae_r=("pre_event_mae_r", "median"),
        )
        .reset_index()
    )
    total_pnl = float(pd.to_numeric(rows["order_realized_pnl"], errors="coerce").sum())
    total_rt = int(rows["right_tail_visual"].sum())
    total_bl = int(rows["bottom_loss_visual"].sum())
    summary["pnl_share"] = summary["pnl_sum"] / total_pnl if abs(total_pnl) > 1e-9 else np.nan
    summary["right_tail_share"] = summary["right_tail_count"] / total_rt if total_rt else np.nan
    summary["bottom_loss_share"] = summary["bottom_loss_count"] / total_bl if total_bl else np.nan
    return summary.sort_values("frontier_bucket").reset_index(drop=True)


def _event_bucket_summary(rows: pd.DataFrame) -> pd.DataFrame:
    order = ["first_bar_event", "bar1_to_5_event", "gt5_bar_event", "no_event_or_unknown"]
    summary = (
        rows.groupby(["event_bucket", "replay_c9_first_event"], dropna=False)
        .agg(
            order_count=("candidate_index", "count"),
            pnl_sum=("order_realized_pnl", "sum"),
            right_tail_count=("right_tail_visual", "sum"),
            bottom_loss_count=("bottom_loss_visual", "sum"),
            maxdd_context_count=("maxdd_context", "sum"),
        )
        .reset_index()
    )
    summary["event_bucket"] = pd.Categorical(summary["event_bucket"], categories=order, ordered=True)
    return summary.sort_values(["event_bucket", "replay_c9_first_event"]).reset_index(drop=True)


def _feature_signal_summary(rows: pd.DataFrame) -> pd.DataFrame:
    early_rt_total = int((rows["early_runway_no_dwell"].eq(1) & rows["right_tail_visual"].eq(1)).sum())
    records: list[dict[str, Any]] = []
    for feature_name, quintile_col in FEATURES:
        if quintile_col not in rows.columns:
            continue
        quintile = pd.to_numeric(rows[quintile_col], errors="coerce")
        top = rows[quintile.ge(4)].copy()
        q5 = rows[quintile.eq(5)].copy()
        for signal_id, group in [("q4q5_top_quality", top), ("q5_top_quality", q5)]:
            early_rt = int((group["early_runway_no_dwell"].eq(1) & group["right_tail_visual"].eq(1)).sum())
            records.append(
                {
                    "feature_id": feature_name,
                    "signal_id": signal_id,
                    "signal_order_count": int(len(group)),
                    "early_right_tail_capture_count": early_rt,
                    "early_right_tail_capture_rate": early_rt / early_rt_total if early_rt_total else np.nan,
                    "right_tail_count": int(group["right_tail_visual"].sum()),
                    "bottom_loss_count": int(group["bottom_loss_visual"].sum()),
                    "risk_bad_count": int(pd.to_numeric(group.get("risk_bad_label", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()),
                    "early_bottom_loss_count": int((group["early_runway_no_dwell"].eq(1) & group["bottom_loss_visual"].eq(1)).sum()),
                    "early_progress_count": int(group["early_progress"].sum()),
                    "strategy_rule_allowed": 0,
                    "true_engine_allowed": 0,
                }
            )
    result = pd.DataFrame(records)
    if not result.empty:
        result["clean_early_tail_signal"] = (
            result["early_right_tail_capture_count"].eq(early_rt_total)
            & result["bottom_loss_count"].eq(0)
            & result["risk_bad_count"].eq(0)
        ).astype(int)
    return result


def _promotion_gate(rows: pd.DataFrame, feature_signal: pd.DataFrame) -> pd.DataFrame:
    early = rows[rows["early_runway_no_dwell"].eq(1)]
    early_rt = int(early["right_tail_visual"].sum())
    early_bl = int(early["bottom_loss_visual"].sum())
    early_pnl = float(early["order_realized_pnl"].sum())
    total_pnl = float(rows["order_realized_pnl"].sum())
    pnl_share = early_pnl / total_pnl if abs(total_pnl) > 1e-9 else np.nan
    best_capture = int(feature_signal["early_right_tail_capture_count"].max()) if not feature_signal.empty else 0
    clean_feature_count = int(feature_signal["clean_early_tail_signal"].sum()) if not feature_signal.empty else 0
    rows_out = [
        {
            "gate_id": "early_runway_right_tail_dependency",
            "evidence_value": early_rt,
            "evidence_unit": "right-tail visual orders in first-bar or <=5-bar no-dwell frontier",
            "pass_for_true_engine": int(early_rt == 0),
            "judgment": "fail_blocks_delayed_confirmation",
        },
        {
            "gate_id": "early_runway_pnl_dependency",
            "evidence_value": pnl_share,
            "evidence_unit": "share of Stage248 order PnL in early no-dwell frontier",
            "pass_for_true_engine": int(pnl_share <= 0.05),
            "judgment": "fail_material_pnl_dependency",
        },
        {
            "gate_id": "early_frontier_tail_symmetry",
            "evidence_value": early_bl,
            "evidence_unit": "bottom-loss visual orders also in early no-dwell frontier",
            "pass_for_true_engine": int(early_bl == 0),
            "judgment": "fail_no_simple_good_bad_split",
        },
        {
            "gate_id": "predecision_feature_full_capture",
            "evidence_value": best_capture,
            "evidence_unit": "best q4q5/q5 single-feature capture of early right-tail orders",
            "pass_for_true_engine": int(best_capture == early_rt and clean_feature_count > 0),
            "judgment": "fail_existing_predecision_features_insufficient",
        },
        {
            "gate_id": "no_rule_no_engine_isolation",
            "evidence_value": 0,
            "evidence_unit": "strategy rules, true engine, A/B, order API calls",
            "pass_for_true_engine": 1,
            "judgment": "technical_pass",
        },
    ]
    gate = pd.DataFrame(rows_out)
    gate["preflight_only"] = 1
    gate["strategy_feature_usable"] = 0
    return gate


def _summary(
    curve: pd.DataFrame,
    lots: pd.DataFrame,
    rows: pd.DataFrame,
    frontier: pd.DataFrame,
    feature_signal: pd.DataFrame,
    gate: pd.DataFrame,
) -> pd.DataFrame:
    metrics = s038._official_metrics(curve, lots)
    early = frontier[frontier["frontier_bucket"].eq("early_no_dwell")]
    early_row = early.iloc[0].to_dict() if not early.empty else {}
    early_rt_total = int(_safe_float(early_row.get("right_tail_count"), 0))
    best_capture = int(feature_signal["early_right_tail_capture_count"].max()) if not feature_signal.empty else 0
    clean_feature_count = int(feature_signal["clean_early_tail_signal"].sum()) if not feature_signal.empty else 0
    return pd.DataFrame(
        [
            {
                "stage": STAGE,
                "model_tag": MODEL_TAG,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "line_id": LINE_ID,
                "decision": "stage249_early_runway_frontier_blocks_delayed_confirmation_no_rule",
                "official_config_changed": 0,
                "strategy_rule_created": 0,
                "true_engine_run": 0,
                "ab_triggered": 0,
                "order_api_called": 0,
                "ctp_connected": 0,
                "timestamp_ready_order_count": int(len(rows)),
                "early_runway_order_count": int(_safe_float(early_row.get("order_count"), 0)),
                "early_runway_pnl_sum": _safe_float(early_row.get("pnl_sum"), 0.0),
                "early_runway_pnl_share": _safe_float(early_row.get("pnl_share"), 0.0),
                "early_runway_right_tail_count": early_rt_total,
                "early_runway_right_tail_share": _safe_float(early_row.get("right_tail_share"), 0.0),
                "early_runway_bottom_loss_count": int(_safe_float(early_row.get("bottom_loss_count"), 0)),
                "early_runway_bottom_loss_share": _safe_float(early_row.get("bottom_loss_share"), 0.0),
                "early_progress_order_count": int(rows["early_progress"].sum()),
                "early_stop_order_count": int(rows["early_stop"].sum()),
                "best_predecision_feature_early_right_tail_capture_count": best_capture,
                "clean_predecision_feature_signal_count": clean_feature_count,
                "promotion_gate_count": int(len(gate)),
                "promotion_gate_pass_count": int(pd.to_numeric(gate["pass_for_true_engine"], errors="coerce").sum()),
                "frontier_rule_allowed": 0,
                "true_engine_allowed": 0,
                "strategy_feature_usable": 0,
                **metrics,
            }
        ]
    )


def _plot_official_path(curve: pd.DataFrame, rows: pd.DataFrame, summary: pd.Series) -> None:
    data = curve.copy()
    data["date"] = pd.to_datetime(data["date"], errors="coerce").dt.normalize()
    fig, axes = plt.subplots(3, 1, figsize=(14, 10), gridspec_kw={"height_ratios": [2.0, 1.0, 1.1]})
    axes[0].plot(data["date"], data["account_equity"], color="#0f766e", linewidth=1.2)
    axes[1].plot(data["date"], data["drawdown_pct"], color="#dc2626", linewidth=1.0)
    points = rows[["official_open_date", "frontier_bucket"]].merge(
        data[["date", "account_equity"]], left_on="official_open_date", right_on="date", how="left"
    )
    for bucket, group in points.groupby("frontier_bucket"):
        axes[0].scatter(
            group["official_open_date"],
            group["account_equity"],
            s=24,
            color=FRONTIER_COLORS.get(bucket, "#64748b"),
            label=bucket,
            alpha=0.72,
        )
    axes[0].set_title(
        f"{STAGE} early runway frontier | early_rt={int(summary['early_runway_right_tail_count'])} | true_engine=0"
    )
    axes[0].set_ylabel("equity")
    axes[1].set_ylabel("drawdown %")
    axes[0].legend(fontsize=8)
    for ax in axes[:2]:
        ax.grid(True, alpha=0.25)
    counts = rows["frontier_bucket"].value_counts()
    axes[2].bar(counts.index, counts.values, color=[FRONTIER_COLORS.get(item, "#64748b") for item in counts.index])
    axes[2].set_ylabel("orders")
    axes[2].grid(True, axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(OFFICIAL_PATH_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_frontier_contribution(rows: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(13, 6))
    for bucket, group in rows.groupby("frontier_bucket"):
        series = group.groupby("official_open_date")["order_realized_pnl"].sum().sort_index().cumsum()
        ax.plot(series.index, series.values, label=bucket, color=FRONTIER_COLORS.get(bucket, "#64748b"), linewidth=1.5)
    ax.axhline(0, color="#111827", linewidth=0.8)
    ax.set_title("Stage249 cumulative official PnL by early-runway frontier")
    ax.set_ylabel("cumulative realized PnL")
    ax.grid(True, alpha=0.25)
    ax.legend()
    fig.tight_layout()
    fig.savefig(FRONTIER_CONTRIBUTION_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_event_bucket(event_summary: pd.DataFrame) -> None:
    data = event_summary.groupby("event_bucket", observed=False).agg(pnl_sum=("pnl_sum", "sum"), right_tail_count=("right_tail_count", "sum"), bottom_loss_count=("bottom_loss_count", "sum")).reset_index()
    x = np.arange(len(data))
    fig, axes = plt.subplots(2, 1, figsize=(12, 7), sharex=True)
    axes[0].bar(x, data["pnl_sum"], color="#0f766e", alpha=0.78)
    axes[0].axhline(0, color="#111827", linewidth=0.8)
    axes[0].set_ylabel("PnL sum")
    axes[0].grid(True, axis="y", alpha=0.25)
    width = 0.36
    axes[1].bar(x - width / 2, data["right_tail_count"], width=width, color="#16a34a", label="right-tail")
    axes[1].bar(x + width / 2, data["bottom_loss_count"], width=width, color="#dc2626", label="bottom-loss")
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(data["event_bucket"], rotation=15, ha="right")
    axes[1].set_ylabel("visual count")
    axes[1].grid(True, axis="y", alpha=0.25)
    axes[1].legend()
    axes[0].set_title("Stage249 event timing bucket: early buckets carry both right-tail and bottom-loss")
    fig.tight_layout()
    fig.savefig(EVENT_BUCKET_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_feature_capture(feature_signal: pd.DataFrame) -> None:
    if feature_signal.empty:
        return
    data = feature_signal[feature_signal["signal_id"].eq("q4q5_top_quality")].copy()
    data = data.set_index("feature_id")[["early_right_tail_capture_count", "bottom_loss_count", "risk_bad_count"]]
    fig, ax = plt.subplots(figsize=(9.5, 5.8))
    values = data.to_numpy(dtype=float)
    im = ax.imshow(values, cmap="YlOrRd", aspect="auto")
    ax.set_xticks(np.arange(len(data.columns)))
    ax.set_xticklabels(data.columns, rotation=20, ha="right")
    ax.set_yticks(np.arange(len(data.index)))
    ax.set_yticklabels(data.index)
    for i in range(values.shape[0]):
        for j in range(values.shape[1]):
            ax.text(j, i, f"{values[i, j]:.0f}", ha="center", va="center", fontsize=8, color="#111827")
    ax.set_title("Stage249 q4/q5 predecision feature capture: no clean early-tail isolator")
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    fig.tight_layout()
    fig.savefig(FEATURE_CAPTURE_HEATMAP_OUT, dpi=160)
    plt.close(fig)


def _plot_gate(gate: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(11.5, 4.8))
    colors = ["#16a34a" if int(item) else "#dc2626" for item in gate["pass_for_true_engine"]]
    ax.bar(gate["gate_id"], gate["evidence_value"], color=colors, alpha=0.82)
    ax.set_ylabel("evidence")
    ax.set_title("Stage249 gates: early-runway frontier blocks delayed confirmation")
    ax.tick_params(axis="x", rotation=22)
    ax.grid(True, axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(PROMOTION_GATE_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_atlas(rows: pd.DataFrame, merged: pd.DataFrame, groups: dict[str, pd.DataFrame]) -> pd.DataFrame:
    selected = rows[rows["selected_for_stage249_atlas"].eq(1)].copy()
    selected = selected.sort_values(
        ["right_tail_visual", "bottom_loss_visual", "maxdd_context", "order_realized_pnl"],
        ascending=[False, False, False, True],
    ).head(ATLAS_ROWS)
    if selected.empty:
        return pd.DataFrame()
    merged_index = merged.set_index("candidate_index", drop=False)
    manifest: list[dict[str, Any]] = []
    total_pages = int(np.ceil(len(selected) / ATLAS_PER_PAGE))
    for page in range(total_pages):
        chunk = selected.iloc[page * ATLAS_PER_PAGE : (page + 1) * ATLAS_PER_PAGE]
        fig, axes = plt.subplots(len(chunk), 1, figsize=(13, 3.1 * len(chunk)), squeeze=False)
        out_path = Path(str(ATLAS_TEMPLATE).format(page=page + 1))
        for ax, (_, item) in zip(axes[:, 0], chunk.iterrows()):
            row = merged_index.loc[item["candidate_index"]]
            entry = _safe_float(row.get("replay_open_price"), np.nan)
            risk = _safe_float(row.get("replay_risk_price"), np.nan)
            sign = s038._direction_sign(row.get("direction"))
            scan = s100._pre_event_scan(row, groups)
            if scan.empty or not np.isfinite(entry) or not np.isfinite(risk) or risk <= 0:
                ax.text(0.5, 0.5, "missing path", transform=ax.transAxes, ha="center", va="center")
                continue
            path = s100._path_arrays(scan, entry, risk, sign).head(MAX_ATLAS_BARS)
            x = path["bar_idx"]
            ax.fill_between(x, path["low_r"], path["high_r"], color="#cbd5e1", alpha=0.42)
            color = FRONTIER_COLORS.get(item["frontier_bucket"], "#334155")
            ax.plot(x, path["close_r"], color=color, linewidth=1.3)
            ax.axhline(0, color="#111827", linewidth=0.8)
            if np.isfinite(_safe_float(item.get("event_bar_idx"), np.nan)):
                ax.axvline(float(item["event_bar_idx"]), color="#7c3aed", linestyle=":", linewidth=1.0)
            title = (
                f"{item['vt_symbol']} {item['direction']} {pd.Timestamp(item['official_open_date']).date()} | "
                f"{item['frontier_bucket']} {item['event_bucket']} {item['replay_c9_first_event']} | "
                f"pnl {item['order_realized_pnl']:,.0f} | rt {int(item['right_tail_visual'])} "
                f"bl {int(item['bottom_loss_visual'])}"
            )
            ax.set_title(title, fontsize=9)
            ax.set_ylabel("directional R")
            ax.grid(True, alpha=0.25)
            manifest.append(
                {
                    "page": page + 1,
                    "candidate_index": item["candidate_index"],
                    "official_open_trade_id": item["official_open_trade_id"],
                    "vt_symbol": item["vt_symbol"],
                    "direction": item["direction"],
                    "official_open_date": item["official_open_date"],
                    "frontier_bucket": item["frontier_bucket"],
                    "event_bucket": item["event_bucket"],
                    "replay_c9_first_event": item["replay_c9_first_event"],
                    "order_realized_pnl": item["order_realized_pnl"],
                    "right_tail_visual": item["right_tail_visual"],
                    "bottom_loss_visual": item["bottom_loss_visual"],
                    "atlas_path": str(out_path),
                }
            )
        axes[-1, 0].set_xlabel("minute bar index from replay open until C9 first event or day end")
        fig.tight_layout()
        fig.savefig(out_path, dpi=160)
        plt.close(fig)
    return pd.DataFrame(manifest)


def _write_report(
    summary: pd.DataFrame,
    frontier: pd.DataFrame,
    event_summary: pd.DataFrame,
    feature_signal: pd.DataFrame,
    gate: pd.DataFrame,
    atlas: pd.DataFrame,
) -> None:
    row = summary.iloc[0]
    report = "\n".join(
        [
            f"# {STAGE} early runway frontier audit",
            "",
            "## Decision",
            "",
            f"- decision: `{row['decision']}`",
            "- nature: read-only frontier audit; no strategy rule, no true engine, no A/B, no CTP, no order API.",
            "- frozen question: how much official right-tail and PnL arrives before a close-dwell confirmation can exist, and can existing predecision features identify those orders.",
            "",
            "## Baseline path",
            "",
            f"- end equity: `{row['end_equity']:,.2f}`",
            f"- total return: `{row['total_return_pct']:.4f}%`",
            f"- max drawdown: `{row['max_drawdown_pct']:.4f}%`",
            f"- Sharpe: `{row['sharpe']:.4f}`",
            f"- total slippage: `{row['total_slippage']:,.0f}`",
            f"- total trade count: `{row['total_trade_count']:.0f}`",
            f"- closed lot win rate: `{row['closed_lot_win_rate_pct']:.4f}%`",
            "",
            "## Frontier summary",
            "",
            f"- timestamp-ready orders: `{int(row['timestamp_ready_order_count'])}`",
            f"- early runway orders: `{int(row['early_runway_order_count'])}`",
            f"- early runway PnL: `{row['early_runway_pnl_sum']:,.0f}`",
            f"- early runway PnL share: `{row['early_runway_pnl_share']:.4f}`",
            f"- early runway right-tail: `{int(row['early_runway_right_tail_count'])}` / share `{row['early_runway_right_tail_share']:.4f}`",
            f"- early runway bottom-loss: `{int(row['early_runway_bottom_loss_count'])}` / share `{row['early_runway_bottom_loss_share']:.4f}`",
            f"- early progress orders: `{int(row['early_progress_order_count'])}`",
            f"- early stop orders: `{int(row['early_stop_order_count'])}`",
            f"- best predecision feature early right-tail capture: `{int(row['best_predecision_feature_early_right_tail_capture_count'])}`",
            f"- clean predecision feature signal count: `{int(row['clean_predecision_feature_signal_count'])}`",
            f"- promotion gate pass count: `{int(row['promotion_gate_pass_count'])}` / `{int(row['promotion_gate_count'])}`",
            "",
            "## Frontier Bucket Summary",
            "",
            _md_table(frontier, max_rows=20),
            "",
            "## Event Bucket Summary",
            "",
            _md_table(event_summary, max_rows=40),
            "",
            "## Predecision Feature Signal Summary",
            "",
            _md_table(feature_signal, max_rows=30),
            "",
            "## Promotion Gates",
            "",
            _md_table(gate, max_rows=20),
            "",
            "## Atlas Manifest",
            "",
            _md_table(atlas, max_rows=60),
            "",
            "## Visual outputs",
            "",
            f"- official path frontier chart: `{OFFICIAL_PATH_CHART_OUT}`",
            f"- frontier contribution chart: `{FRONTIER_CONTRIBUTION_CHART_OUT}`",
            f"- event bucket chart: `{EVENT_BUCKET_CHART_OUT}`",
            f"- predecision feature capture heatmap: `{FEATURE_CAPTURE_HEATMAP_OUT}`",
            f"- promotion gate chart: `{PROMOTION_GATE_CHART_OUT}`",
            f"- atlas manifest: `{ATLAS_MANIFEST_OUT}`",
            "",
            "## Judgment",
            "",
            (
                "The early no-dwell frontier is not a nuisance bucket: it carries material PnL and half of the visual right-tail, "
                "while also containing half of the visual bottom-loss. Existing Stage239 predecision single features do not isolate "
                "this frontier cleanly. Delayed confirmation must therefore remain blocked unless a higher-information source can "
                "decide before or at the early progress boundary."
            ),
            "",
        ]
    )
    REPORT_OUT.parent.mkdir(parents=True, exist_ok=True)
    REPORT_OUT.write_text(report, encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    merged, curve, lots, _intraday, groups = s045._prepare_event_sync_frame()
    rows = _load_joined_rows()
    frontier = _frontier_summary(rows)
    event_summary = _event_bucket_summary(rows)
    feature_signal = _feature_signal_summary(rows)
    gate = _promotion_gate(rows, feature_signal)
    summary = _summary(curve, lots, rows, frontier, feature_signal, gate)
    atlas = _plot_atlas(rows, merged, groups)

    _write_csv(rows, ROWS_OUT)
    _write_csv(frontier, FRONTIER_SUMMARY_OUT)
    _write_csv(event_summary, EVENT_BUCKET_SUMMARY_OUT)
    _write_csv(feature_signal, FEATURE_SIGNAL_SUMMARY_OUT)
    _write_csv(gate, PROMOTION_GATE_OUT)
    _write_csv(summary, SUMMARY_OUT)
    _write_csv(atlas, ATLAS_MANIFEST_OUT)

    _plot_official_path(curve, rows, summary.iloc[0])
    _plot_frontier_contribution(rows)
    _plot_event_bucket(event_summary)
    _plot_feature_capture(feature_signal)
    _plot_gate(gate)
    _write_report(summary, frontier, event_summary, feature_signal, gate, atlas)

    decision = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "decision": str(summary.iloc[0]["decision"]),
        "summary_path": str(SUMMARY_OUT),
        "report_path": str(REPORT_OUT),
        "frontier_rows_path": str(ROWS_OUT),
        "frontier_summary_path": str(FRONTIER_SUMMARY_OUT),
        "event_bucket_summary_path": str(EVENT_BUCKET_SUMMARY_OUT),
        "feature_signal_summary_path": str(FEATURE_SIGNAL_SUMMARY_OUT),
        "promotion_gate_path": str(PROMOTION_GATE_OUT),
        "atlas_manifest_path": str(ATLAS_MANIFEST_OUT),
        "charts": [
            str(OFFICIAL_PATH_CHART_OUT),
            str(FRONTIER_CONTRIBUTION_CHART_OUT),
            str(EVENT_BUCKET_CHART_OUT),
            str(FEATURE_CAPTURE_HEATMAP_OUT),
            str(PROMOTION_GATE_CHART_OUT),
        ],
        "timestamp_ready_order_count": int(summary.iloc[0]["timestamp_ready_order_count"]),
        "early_runway_right_tail_count": int(summary.iloc[0]["early_runway_right_tail_count"]),
        "promotion_gate_pass_count": int(summary.iloc[0]["promotion_gate_pass_count"]),
        "frontier_rule_allowed": 0,
        "true_engine_allowed": 0,
        "strategy_feature_usable": 0,
    }
    _write_json(DECISION_OUT, decision)
    print(json.dumps(s045._json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
