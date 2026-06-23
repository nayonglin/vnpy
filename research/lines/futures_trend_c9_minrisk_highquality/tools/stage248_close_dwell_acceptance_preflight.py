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
STAGE = "Stage248"
MODEL_TAG = "stage248_close_dwell_acceptance_preflight_v1"
OUTPUT_PREFIX = "qmt_roll_stage248_c9_minrisk_close_dwell_acceptance_preflight"

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
OUTPUT_DIR = LINE_DIR / "outputs" / "stage248_close_dwell_acceptance_preflight"

ROWS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_dwell_rows_{MODEL_TAG}.csv"
STATE_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_state_summary_{MODEL_TAG}.csv"
STATE_EVENT_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_state_event_summary_{MODEL_TAG}.csv"
PROMOTION_GATE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_promotion_gate_{MODEL_TAG}.csv"
SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
ATLAS_MANIFEST_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_atlas_manifest_{MODEL_TAG}.csv"

OFFICIAL_PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_chart_{MODEL_TAG}.png"
STATE_CONTRIBUTION_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_state_contribution_chart_{MODEL_TAG}.png"
STATE_SUMMARY_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_state_summary_chart_{MODEL_TAG}.png"
DWELL_MATRIX_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_dwell_event_matrix_{MODEL_TAG}.png"
PROMOTION_GATE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_promotion_gate_chart_{MODEL_TAG}.png"
ATLAS_TEMPLATE = OUTPUT_DIR / f"{OUTPUT_PREFIX}_atlas_page{{page:03d}}_{MODEL_TAG}.png"

EPS = 1e-10
DWELL_WINDOW_BARS = 30
MIN_DWELL_BARS = 6
MAJORITY_RATIO = 2.0 / 3.0
ATLAS_ROWS = 24
ATLAS_PER_PAGE = 4
MAX_ATLAS_BARS = 90
MAXDD_START = pd.Timestamp("2022-05-30")
MAXDD_END = pd.Timestamp("2023-03-09")

STATE_COLORS = {
    "positive_acceptance_dwell": "#0f766e",
    "underwater_acceptance_dwell": "#dc2626",
    "two_sided_chop_dwell": "#f97316",
    "mixed_or_neutral_dwell": "#2563eb",
    "short_runway_le5_no_dwell": "#9333ea",
    "first_bar_event_no_closed_dwell": "#64748b",
    "invalid_or_missing_minute_path": "#94a3b8",
}


def _write_csv(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, encoding="utf-8-sig")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(s045._json_safe(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s038._md_table(frame, max_rows=max_rows)


def _safe_float(value: Any, default: float = np.nan) -> float:
    return s045._safe_float(value, default=default)


def _direction_sign(direction: Any) -> int:
    return s038._direction_sign(direction)


def _time_text(value: Any) -> str:
    return s045._time_text(value)


def _event_bar_idx(path: pd.DataFrame, value: Any) -> float:
    ts = pd.to_datetime(value, errors="coerce")
    if pd.isna(ts) or path.empty:
        return np.nan
    times = pd.to_datetime(path["bar_datetime_ts"], errors="coerce")
    hits = np.where(times.eq(pd.Timestamp(ts)).to_numpy())[0]
    return float(hits[0]) if len(hits) else np.nan


def _sign_transition_count(signs: list[int]) -> int:
    nonzero = [item for item in signs if item != 0]
    if len(nonzero) <= 1:
        return 0
    return int(sum(1 for prev, cur in zip(nonzero[:-1], nonzero[1:]) if prev != cur))


def _max_streak(signs: list[int], target: int) -> int:
    best = 0
    current = 0
    for item in signs:
        if item == target:
            current += 1
            best = max(best, current)
        else:
            current = 0
    return int(best)


def _classify_row(row: pd.Series, groups: dict[str, pd.DataFrame]) -> dict[str, Any]:
    entry = _safe_float(row.get("replay_open_price"))
    risk = _safe_float(row.get("replay_risk_price"))
    sign = _direction_sign(row.get("direction"))
    scan = s100._pre_event_scan(row, groups)
    base: dict[str, Any] = {
        "candidate_index": row.get("candidate_index"),
        "official_open_trade_id": row.get("official_open_trade_id"),
        "vt_symbol": row.get("vt_symbol"),
        "direction": row.get("direction"),
        "official_open_date": row.get("official_open_date"),
        "replay_event_family": row.get("replay_event_family"),
        "replay_c9_first_event": row.get("replay_c9_first_event"),
        "replay_c9_first_event_time": row.get("replay_c9_first_event_time"),
        "entry_price": entry,
        "risk_price": risk,
        "dwell_state": "invalid_or_missing_minute_path",
        "pre_event_bar_count": int(len(scan)),
        "event_bar_idx": np.nan,
        "analysis_bar_count": 0,
        "positive_close_count": 0,
        "negative_close_count": 0,
        "neutral_close_count": 0,
        "positive_close_ratio": np.nan,
        "negative_close_ratio": np.nan,
        "sign_transition_count": 0,
        "max_positive_streak": 0,
        "max_negative_streak": 0,
        "analysis_final_close_r": np.nan,
        "analysis_mean_close_r": np.nan,
        "analysis_min_close_r": np.nan,
        "analysis_max_close_r": np.nan,
        "pre_event_mfe_r": np.nan,
        "pre_event_mae_r": np.nan,
        "pre_event_close_r": np.nan,
        "dwell_rule_allowed": 0,
        "true_engine_allowed": 0,
    }
    if scan.empty or not np.isfinite(entry) or not np.isfinite(risk) or risk <= 0:
        return base

    path = s100._path_arrays(scan, entry, risk, sign)
    if path.empty:
        return base
    base["pre_event_bar_count"] = int(len(path))
    base["event_bar_idx"] = _event_bar_idx(path, row.get("replay_c9_first_event_time"))
    base["pre_event_mfe_r"] = float(pd.to_numeric(path["high_r"], errors="coerce").max())
    base["pre_event_mae_r"] = float(pd.to_numeric(path["low_r"], errors="coerce").min())
    base["pre_event_close_r"] = float(pd.to_numeric(path["close_r"], errors="coerce").iloc[-1])

    event_idx = base["event_bar_idx"]
    if len(path) <= 1 or (np.isfinite(event_idx) and event_idx <= 0):
        base["dwell_state"] = "first_bar_event_no_closed_dwell"
        return base
    if len(path) < MIN_DWELL_BARS or (np.isfinite(event_idx) and event_idx < MIN_DWELL_BARS):
        base["dwell_state"] = "short_runway_le5_no_dwell"
        return base

    window = path.head(min(DWELL_WINDOW_BARS, len(path))).copy()
    close_r = pd.to_numeric(window["close_r"], errors="coerce").fillna(0.0).to_numpy()
    signs = [1 if value > EPS else -1 if value < -EPS else 0 for value in close_r]
    count = int(len(signs))
    pos = int(sum(1 for item in signs if item == 1))
    neg = int(sum(1 for item in signs if item == -1))
    neu = int(sum(1 for item in signs if item == 0))
    pos_ratio = pos / count if count else np.nan
    neg_ratio = neg / count if count else np.nan
    transitions = _sign_transition_count(signs)
    final_close = float(close_r[-1]) if count else np.nan

    base.update(
        {
            "analysis_bar_count": count,
            "positive_close_count": pos,
            "negative_close_count": neg,
            "neutral_close_count": neu,
            "positive_close_ratio": float(pos_ratio),
            "negative_close_ratio": float(neg_ratio),
            "sign_transition_count": transitions,
            "max_positive_streak": _max_streak(signs, 1),
            "max_negative_streak": _max_streak(signs, -1),
            "analysis_final_close_r": final_close,
            "analysis_mean_close_r": float(np.nanmean(close_r)),
            "analysis_min_close_r": float(np.nanmin(close_r)),
            "analysis_max_close_r": float(np.nanmax(close_r)),
        }
    )

    if pos_ratio >= MAJORITY_RATIO and final_close > 0:
        state = "positive_acceptance_dwell"
    elif neg_ratio >= MAJORITY_RATIO and final_close < 0:
        state = "underwater_acceptance_dwell"
    elif transitions >= 3 and max(pos_ratio, neg_ratio) < MAJORITY_RATIO:
        state = "two_sided_chop_dwell"
    else:
        state = "mixed_or_neutral_dwell"
    base["dwell_state"] = state
    return base


def _dwell_rows(merged: pd.DataFrame, lots: pd.DataFrame, groups: dict[str, pd.DataFrame]) -> pd.DataFrame:
    result = pd.DataFrame([_classify_row(row, groups) for _, row in merged.iterrows()])
    pnl = s100._order_pnl(lots)
    result = result.merge(pnl, on="official_open_trade_id", how="left")
    result["order_realized_pnl"] = pd.to_numeric(result["order_realized_pnl"], errors="coerce").fillna(0.0)
    result["official_open_date"] = pd.to_datetime(result["official_open_date"], errors="coerce").dt.normalize()
    result["decision_year"] = result["official_open_date"].dt.year.astype("Int64")
    result["maxdd_context"] = result["official_open_date"].between(MAXDD_START, MAXDD_END).astype(int)
    result["pnl_rank_desc"] = result["order_realized_pnl"].rank(ascending=False, method="first")
    result["pnl_rank_asc"] = result["order_realized_pnl"].rank(ascending=True, method="first")
    visual_n = max(12, int(np.ceil(len(result) * 0.08)))
    result["right_tail_visual"] = result["pnl_rank_desc"].le(visual_n).astype(int)
    result["bottom_loss_visual"] = result["pnl_rank_asc"].le(visual_n).astype(int)
    result["selected_for_atlas"] = 0

    selected_index: set[int] = set(result[result["right_tail_visual"].eq(1)].sort_values("pnl_rank_desc").head(8).index)
    selected_index.update(result[result["bottom_loss_visual"].eq(1)].sort_values("pnl_rank_asc").head(8).index)
    selected_index.update(result[result["maxdd_context"].eq(1)].sort_values(["dwell_state", "order_realized_pnl"]).head(8).index)
    for _state, group in result.groupby("dwell_state"):
        selected_index.update(group.reindex(group["order_realized_pnl"].abs().sort_values(ascending=False).index).head(2).index)
    selected = list(selected_index)[:ATLAS_ROWS]
    if selected:
        result.loc[selected, "selected_for_atlas"] = 1
    return result.sort_values(["official_open_date", "candidate_index"]).reset_index(drop=True)


def _state_summary(rows: pd.DataFrame) -> pd.DataFrame:
    summary = (
        rows.groupby("dwell_state", dropna=False)
        .agg(
            order_count=("official_open_trade_id", "nunique"),
            lot_count=("order_lot_count", "sum"),
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
            median_positive_close_ratio=("positive_close_ratio", "median"),
            median_negative_close_ratio=("negative_close_ratio", "median"),
            median_sign_transition_count=("sign_transition_count", "median"),
            median_final_close_r=("analysis_final_close_r", "median"),
            median_pre_event_mfe_r=("pre_event_mfe_r", "median"),
            median_pre_event_mae_r=("pre_event_mae_r", "median"),
        )
        .reset_index()
    )
    summary["pnl_sign_conflict"] = (summary["pnl_min"].lt(0) & summary["pnl_max"].gt(0)).astype(int)
    summary["right_tail_and_bottom_loss_conflict"] = (
        summary["right_tail_count"].gt(0) & summary["bottom_loss_count"].gt(0)
    ).astype(int)
    return summary.sort_values("order_count", ascending=False).reset_index(drop=True)


def _state_event_summary(rows: pd.DataFrame) -> pd.DataFrame:
    summary = (
        rows.groupby(["dwell_state", "replay_c9_first_event"], dropna=False)
        .agg(
            order_count=("official_open_trade_id", "nunique"),
            pnl_sum=("order_realized_pnl", "sum"),
            pnl_min=("order_realized_pnl", "min"),
            pnl_max=("order_realized_pnl", "max"),
            right_tail_count=("right_tail_visual", "sum"),
            bottom_loss_count=("bottom_loss_visual", "sum"),
            maxdd_context_count=("maxdd_context", "sum"),
        )
        .reset_index()
    )
    return summary.sort_values(["dwell_state", "replay_c9_first_event"]).reset_index(drop=True)


def _promotion_gate(rows: pd.DataFrame, state_summary: pd.DataFrame) -> pd.DataFrame:
    positive = rows[rows["dwell_state"].eq("positive_acceptance_dwell")]
    bad = rows[rows["dwell_state"].isin(["underwater_acceptance_dwell", "two_sided_chop_dwell"])]
    right_tail_total = int(rows["right_tail_visual"].sum())
    bottom_loss_total = int(rows["bottom_loss_visual"].sum())
    right_tail_outside_positive = int(right_tail_total - positive["right_tail_visual"].sum())
    bottom_loss_outside_bad = int(bottom_loss_total - bad["bottom_loss_visual"].sum())
    mixed_states = int(state_summary["pnl_sign_conflict"].sum())
    tail_conflict_states = int(state_summary["right_tail_and_bottom_loss_conflict"].sum())
    adequate = rows[~rows["dwell_state"].isin(["first_bar_event_no_closed_dwell", "short_runway_le5_no_dwell", "invalid_or_missing_minute_path"])]
    rows_out = [
        {
            "gate_id": "close_only_no_intrabar_ordering",
            "evidence_value": 0,
            "evidence_unit": "uses minute close dwell only; no high-low sequencing",
            "pass_for_true_engine": 1,
            "judgment": "technical_pass_but_not_sufficient",
        },
        {
            "gate_id": "right_tail_protection",
            "evidence_value": right_tail_outside_positive,
            "evidence_unit": "right-tail visual orders outside positive_acceptance_dwell",
            "pass_for_true_engine": int(right_tail_outside_positive == 0),
            "judgment": "pass" if right_tail_outside_positive == 0 else "fail_or_watch_only",
        },
        {
            "gate_id": "bottom_loss_separation",
            "evidence_value": bottom_loss_outside_bad,
            "evidence_unit": "bottom-loss visual orders outside underwater/chop dwell",
            "pass_for_true_engine": int(bottom_loss_outside_bad == 0),
            "judgment": "pass" if bottom_loss_outside_bad == 0 else "fail_or_watch_only",
        },
        {
            "gate_id": "state_pnl_mixture",
            "evidence_value": mixed_states,
            "evidence_unit": "dwell states with both positive and negative PnL",
            "pass_for_true_engine": int(mixed_states == 0),
            "judgment": "pass" if mixed_states == 0 else "fail_or_watch_only",
        },
        {
            "gate_id": "tail_state_conflict",
            "evidence_value": tail_conflict_states,
            "evidence_unit": "states containing both right-tail and bottom-loss visual orders",
            "pass_for_true_engine": int(tail_conflict_states == 0),
            "judgment": "pass" if tail_conflict_states == 0 else "fail_or_watch_only",
        },
        {
            "gate_id": "adequate_dwell_sample_breadth",
            "evidence_value": int(adequate["product"].nunique()),
            "evidence_unit": "products with at least six-bar close-dwell evidence",
            "pass_for_true_engine": int(adequate["product"].nunique() >= 12 and adequate["decision_year"].nunique() >= 5),
            "judgment": "breadth_only_not_alpha",
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
    state_summary: pd.DataFrame,
    gate: pd.DataFrame,
) -> pd.DataFrame:
    metrics = s038._official_metrics(curve, lots)
    state_lookup = state_summary.set_index("dwell_state")

    def state_num(state: str, column: str, default: float = 0.0) -> float:
        if state in state_lookup.index and column in state_lookup.columns:
            return _safe_float(state_lookup.loc[state, column], default)
        return default

    positive_tail = state_num("positive_acceptance_dwell", "right_tail_count")
    positive_bottom = state_num("positive_acceptance_dwell", "bottom_loss_count")
    underwater_tail = state_num("underwater_acceptance_dwell", "right_tail_count")
    underwater_bottom = state_num("underwater_acceptance_dwell", "bottom_loss_count")
    decision = "stage248_close_dwell_acceptance_mixed_tail_conflict_no_rule"
    if int(gate["pass_for_true_engine"].sum()) == len(gate):
        decision = "stage248_close_dwell_acceptance_watch_only_needs_true_engine_review"
    return pd.DataFrame(
        [
            {
                "stage": STAGE,
                "model_tag": MODEL_TAG,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "line_id": LINE_ID,
                "decision": decision,
                "official_config_changed": 0,
                "strategy_rule_created": 0,
                "true_engine_run": 0,
                "ab_triggered": 0,
                "order_api_called": 0,
                "ctp_connected": 0,
                "timestamp_ready_order_count": int(len(rows)),
                "dwell_state_count": int(rows["dwell_state"].nunique()),
                "adequate_dwell_order_count": int(
                    (~rows["dwell_state"].isin(["first_bar_event_no_closed_dwell", "short_runway_le5_no_dwell", "invalid_or_missing_minute_path"])).sum()
                ),
                "positive_acceptance_order_count": int(state_num("positive_acceptance_dwell", "order_count")),
                "positive_acceptance_pnl_sum": state_num("positive_acceptance_dwell", "pnl_sum"),
                "positive_acceptance_right_tail_count": int(positive_tail),
                "positive_acceptance_bottom_loss_count": int(positive_bottom),
                "underwater_acceptance_order_count": int(state_num("underwater_acceptance_dwell", "order_count")),
                "underwater_acceptance_pnl_sum": state_num("underwater_acceptance_dwell", "pnl_sum"),
                "underwater_acceptance_right_tail_count": int(underwater_tail),
                "underwater_acceptance_bottom_loss_count": int(underwater_bottom),
                "right_tail_visual_count": int(rows["right_tail_visual"].sum()),
                "bottom_loss_visual_count": int(rows["bottom_loss_visual"].sum()),
                "maxdd_context_order_count": int(rows["maxdd_context"].sum()),
                "pnl_mixed_state_count": int(state_summary["pnl_sign_conflict"].sum()),
                "tail_conflict_state_count": int(state_summary["right_tail_and_bottom_loss_conflict"].sum()),
                "promotion_gate_count": int(len(gate)),
                "promotion_gate_pass_count": int(pd.to_numeric(gate["pass_for_true_engine"], errors="coerce").sum()),
                "dwell_rule_allowed": 0,
                "true_engine_allowed": 0,
                "strategy_feature_usable": 0,
                **metrics,
            }
        ]
    )


def _plot_official_path(curve: pd.DataFrame, rows: pd.DataFrame, summary: pd.Series) -> None:
    data = curve.copy()
    data["date"] = pd.to_datetime(data["date"], errors="coerce").dt.normalize()
    fig, axes = plt.subplots(3, 1, figsize=(14, 10), gridspec_kw={"height_ratios": [2.0, 1.0, 1.2]})
    axes[0].plot(data["date"], data["account_equity"], color="#0f766e", linewidth=1.2)
    axes[0].set_ylabel("equity")
    axes[0].grid(True, alpha=0.25)
    axes[1].plot(data["date"], data["drawdown_pct"], color="#dc2626", linewidth=1.0)
    axes[1].set_ylabel("drawdown %")
    axes[1].grid(True, alpha=0.25)
    points = rows[["official_open_date", "dwell_state"]].merge(
        data[["date", "account_equity"]], left_on="official_open_date", right_on="date", how="left"
    )
    for state, group in points.groupby("dwell_state"):
        axes[0].scatter(
            group["official_open_date"],
            group["account_equity"],
            s=24,
            color=STATE_COLORS.get(state, "#64748b"),
            label=state,
            alpha=0.72,
        )
    axes[0].legend(loc="upper left", fontsize=7, ncol=2)
    counts = rows["dwell_state"].value_counts()
    axes[2].bar(counts.index, counts.values, color=[STATE_COLORS.get(item, "#64748b") for item in counts.index])
    axes[2].set_ylabel("orders")
    axes[2].tick_params(axis="x", rotation=18)
    axes[2].grid(True, axis="y", alpha=0.25)
    axes[0].set_title(
        f"{STAGE} close-dwell preflight | orders {int(summary['timestamp_ready_order_count'])} | true_engine=0"
    )
    fig.tight_layout()
    fig.savefig(OFFICIAL_PATH_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_state_contribution(rows: pd.DataFrame) -> None:
    data = rows.sort_values(["official_open_date", "candidate_index"]).copy()
    fig, ax = plt.subplots(figsize=(13, 6))
    for state, group in data.groupby("dwell_state"):
        series = group.groupby("official_open_date")["order_realized_pnl"].sum().sort_index().cumsum()
        ax.plot(series.index, series.values, label=state, color=STATE_COLORS.get(state, "#64748b"), linewidth=1.35)
    ax.axhline(0, color="#111827", linewidth=0.8)
    ax.set_title("Stage248 official realized PnL contribution by close-dwell state")
    ax.set_ylabel("cumulative realized PnL")
    ax.grid(True, alpha=0.25)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(STATE_CONTRIBUTION_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_state_summary(state_summary: pd.DataFrame) -> None:
    data = state_summary.copy()
    x = np.arange(len(data))
    colors = [STATE_COLORS.get(item, "#64748b") for item in data["dwell_state"]]
    fig, axes = plt.subplots(2, 1, figsize=(13, 8), sharex=True, gridspec_kw={"height_ratios": [1.0, 1.1]})
    axes[0].bar(x, data["order_count"], color=colors, alpha=0.82)
    axes[0].set_ylabel("orders")
    axes[0].grid(True, axis="y", alpha=0.25)
    axes[1].bar(x, data["pnl_sum"], color=colors, alpha=0.82)
    axes[1].axhline(0, color="#111827", linewidth=0.8)
    axes[1].set_ylabel("PnL sum")
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(data["dwell_state"], rotation=18, ha="right")
    axes[1].grid(True, axis="y", alpha=0.25)
    axes[0].set_title("Stage248 state count and PnL; mixture blocks rule creation")
    fig.tight_layout()
    fig.savefig(STATE_SUMMARY_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_dwell_matrix(state_event: pd.DataFrame) -> None:
    pivot = state_event.pivot_table(index="dwell_state", columns="replay_c9_first_event", values="pnl_sum", aggfunc="sum", fill_value=0.0)
    if pivot.empty:
        return
    fig, ax = plt.subplots(figsize=(9, 5.8))
    values = pivot.to_numpy(dtype=float)
    limit = max(abs(float(values.min())), abs(float(values.max())), 1.0)
    im = ax.imshow(values, cmap="RdYlGn", vmin=-limit, vmax=limit, aspect="auto")
    ax.set_xticks(np.arange(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns, rotation=20, ha="right")
    ax.set_yticks(np.arange(len(pivot.index)))
    ax.set_yticklabels(pivot.index)
    for i in range(values.shape[0]):
        for j in range(values.shape[1]):
            ax.text(j, i, f"{values[i, j] / 10000:.0f}w", ha="center", va="center", fontsize=8, color="#111827")
    ax.set_title("Stage248 PnL matrix by close-dwell state and C9 first event")
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    fig.tight_layout()
    fig.savefig(DWELL_MATRIX_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_gate(gate: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(12, 4.8))
    colors = ["#16a34a" if int(item) else "#dc2626" for item in gate["pass_for_true_engine"]]
    ax.bar(gate["gate_id"], gate["evidence_value"], color=colors, alpha=0.82)
    ax.set_ylabel("evidence count")
    ax.set_title("Stage248 promotion gates: close-only passes technically, tail gates decide")
    ax.tick_params(axis="x", rotation=22)
    ax.grid(True, axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(PROMOTION_GATE_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_atlas(rows: pd.DataFrame, merged: pd.DataFrame, groups: dict[str, pd.DataFrame]) -> pd.DataFrame:
    selected = rows[rows["selected_for_atlas"].eq(1)].copy()
    selected = selected.sort_values(
        ["right_tail_visual", "bottom_loss_visual", "maxdd_context", "order_realized_pnl"],
        ascending=[False, False, False, True],
    ).head(ATLAS_ROWS)
    manifest_rows: list[dict[str, Any]] = []
    if selected.empty:
        return pd.DataFrame()
    merged_index = merged.set_index("candidate_index", drop=False)
    total_pages = int(np.ceil(len(selected) / ATLAS_PER_PAGE))
    for page in range(total_pages):
        chunk = selected.iloc[page * ATLAS_PER_PAGE : (page + 1) * ATLAS_PER_PAGE]
        fig, axes = plt.subplots(len(chunk), 1, figsize=(13, 3.1 * len(chunk)), squeeze=False)
        out_path = Path(str(ATLAS_TEMPLATE).format(page=page + 1))
        for ax, (_, item) in zip(axes[:, 0], chunk.iterrows()):
            row = merged_index.loc[item["candidate_index"]]
            entry = _safe_float(row.get("replay_open_price"))
            risk = _safe_float(row.get("replay_risk_price"))
            sign = _direction_sign(row.get("direction"))
            scan = s100._pre_event_scan(row, groups)
            if scan.empty or not np.isfinite(entry) or not np.isfinite(risk) or risk <= 0:
                ax.text(0.5, 0.5, "missing path", transform=ax.transAxes, ha="center", va="center")
                continue
            path = s100._path_arrays(scan, entry, risk, sign).head(MAX_ATLAS_BARS)
            x = path["bar_idx"]
            ax.fill_between(x, path["low_r"], path["high_r"], color="#cbd5e1", alpha=0.42, label="high-low R")
            ax.plot(x, path["close_r"], color=STATE_COLORS.get(item["dwell_state"], "#334155"), linewidth=1.3, label="close R")
            ax.axhline(0, color="#111827", linewidth=0.8)
            ax.axvspan(0, min(DWELL_WINDOW_BARS, max(len(path) - 1, 0)), color="#e2e8f0", alpha=0.22)
            title = (
                f"{item['vt_symbol']} {item['direction']} {pd.Timestamp(item['official_open_date']).date()} | "
                f"{item['dwell_state']} | pnl {item['order_realized_pnl']:,.0f} | "
                f"pos {item['positive_close_ratio']:.2f} neg {item['negative_close_ratio']:.2f} | "
                f"rt {int(item['right_tail_visual'])} bl {int(item['bottom_loss_visual'])} md {int(item['maxdd_context'])}"
            )
            ax.set_title(title, fontsize=9)
            ax.set_ylabel("directional R")
            ax.grid(True, alpha=0.25)
            manifest_rows.append(
                {
                    "page": page + 1,
                    "candidate_index": item["candidate_index"],
                    "official_open_trade_id": item["official_open_trade_id"],
                    "vt_symbol": item["vt_symbol"],
                    "direction": item["direction"],
                    "official_open_date": item["official_open_date"],
                    "dwell_state": item["dwell_state"],
                    "order_realized_pnl": item["order_realized_pnl"],
                    "positive_close_ratio": item["positive_close_ratio"],
                    "negative_close_ratio": item["negative_close_ratio"],
                    "right_tail_visual": item["right_tail_visual"],
                    "bottom_loss_visual": item["bottom_loss_visual"],
                    "maxdd_context": item["maxdd_context"],
                    "atlas_path": str(out_path),
                }
            )
        axes[-1, 0].set_xlabel("minute bar index from replay open until C9 first event or day end")
        fig.tight_layout()
        fig.savefig(out_path, dpi=160)
        plt.close(fig)
    return pd.DataFrame(manifest_rows)


def _write_report(
    summary: pd.DataFrame,
    state_summary: pd.DataFrame,
    state_event_summary: pd.DataFrame,
    gate: pd.DataFrame,
    atlas_manifest: pd.DataFrame,
) -> None:
    row = summary.iloc[0]
    report = "\n".join(
        [
            f"# {STAGE} close dwell acceptance preflight",
            "",
            "## Decision",
            "",
            f"- decision: `{row['decision']}`",
            "- nature: read-only preflight; no strategy rule, no true engine, no A/B, no CTP, no order API.",
            "- frozen idea: use only minute closes after official replay open to test whether price is accepted on the profit side, underwater side, or keeps chopping before C9 first event.",
            "- anti-overfit guard: this stage does not sweep dwell windows or ratios; the 30-bar window and two-thirds majority are treated as a diagnostic lens, not a trading parameter.",
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
            "## Preflight summary",
            "",
            f"- timestamp-ready orders: `{int(row['timestamp_ready_order_count'])}`",
            f"- dwell states: `{int(row['dwell_state_count'])}`",
            f"- adequate dwell orders: `{int(row['adequate_dwell_order_count'])}`",
            f"- positive acceptance orders: `{int(row['positive_acceptance_order_count'])}`",
            f"- positive acceptance PnL: `{row['positive_acceptance_pnl_sum']:,.0f}`",
            f"- positive acceptance right-tail/bottom-loss: `{int(row['positive_acceptance_right_tail_count'])}` / `{int(row['positive_acceptance_bottom_loss_count'])}`",
            f"- underwater acceptance orders: `{int(row['underwater_acceptance_order_count'])}`",
            f"- underwater acceptance PnL: `{row['underwater_acceptance_pnl_sum']:,.0f}`",
            f"- underwater acceptance right-tail/bottom-loss: `{int(row['underwater_acceptance_right_tail_count'])}` / `{int(row['underwater_acceptance_bottom_loss_count'])}`",
            f"- right-tail visual orders: `{int(row['right_tail_visual_count'])}`",
            f"- bottom-loss visual orders: `{int(row['bottom_loss_visual_count'])}`",
            f"- maxDD context orders: `{int(row['maxdd_context_order_count'])}`",
            f"- mixed PnL states: `{int(row['pnl_mixed_state_count'])}`",
            f"- tail-conflict states: `{int(row['tail_conflict_state_count'])}`",
            f"- promotion gate pass count: `{int(row['promotion_gate_pass_count'])}` / `{int(row['promotion_gate_count'])}`",
            "",
            "## State Summary",
            "",
            _md_table(state_summary, max_rows=20),
            "",
            "## State Event Summary",
            "",
            _md_table(state_event_summary, max_rows=40),
            "",
            "## Promotion Gates",
            "",
            _md_table(gate, max_rows=20),
            "",
            "## Atlas Manifest",
            "",
            _md_table(atlas_manifest, max_rows=60),
            "",
            "## Visual outputs",
            "",
            f"- official path chart: `{OFFICIAL_PATH_CHART_OUT}`",
            f"- state contribution chart: `{STATE_CONTRIBUTION_CHART_OUT}`",
            f"- state summary chart: `{STATE_SUMMARY_CHART_OUT}`",
            f"- dwell/event matrix: `{DWELL_MATRIX_CHART_OUT}`",
            f"- promotion gate chart: `{PROMOTION_GATE_CHART_OUT}`",
            f"- atlas manifest: `{ATLAS_MANIFEST_OUT}`",
            "",
            "## Judgment",
            "",
            (
                "Close-dwell acceptance is more robust than intrabar touch sequencing, but it is still only a diagnostic "
                "unless it protects right-tail orders and separates bottom-loss orders without mixed states. Promotion "
                "requires all tail and mixture gates to pass, not just a clean-looking contribution curve."
            ),
            "",
        ]
    )
    REPORT_OUT.parent.mkdir(parents=True, exist_ok=True)
    REPORT_OUT.write_text(report, encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    merged, curve, lots, _intraday, groups = s045._prepare_event_sync_frame()
    rows = _dwell_rows(merged, lots, groups)
    state_summary = _state_summary(rows)
    state_event_summary = _state_event_summary(rows)
    gate = _promotion_gate(rows, state_summary)
    summary = _summary(curve, lots, rows, state_summary, gate)
    atlas_manifest = _plot_atlas(rows, merged, groups)

    _write_csv(rows, ROWS_OUT)
    _write_csv(state_summary, STATE_SUMMARY_OUT)
    _write_csv(state_event_summary, STATE_EVENT_SUMMARY_OUT)
    _write_csv(gate, PROMOTION_GATE_OUT)
    _write_csv(summary, SUMMARY_OUT)
    _write_csv(atlas_manifest, ATLAS_MANIFEST_OUT)

    _plot_official_path(curve, rows, summary.iloc[0])
    _plot_state_contribution(rows)
    _plot_state_summary(state_summary)
    _plot_dwell_matrix(state_event_summary)
    _plot_gate(gate)
    _write_report(summary, state_summary, state_event_summary, gate, atlas_manifest)

    decision = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "decision": str(summary.iloc[0]["decision"]),
        "summary_path": str(SUMMARY_OUT),
        "report_path": str(REPORT_OUT),
        "dwell_rows_path": str(ROWS_OUT),
        "state_summary_path": str(STATE_SUMMARY_OUT),
        "state_event_summary_path": str(STATE_EVENT_SUMMARY_OUT),
        "promotion_gate_path": str(PROMOTION_GATE_OUT),
        "atlas_manifest_path": str(ATLAS_MANIFEST_OUT),
        "charts": [
            str(OFFICIAL_PATH_CHART_OUT),
            str(STATE_CONTRIBUTION_CHART_OUT),
            str(STATE_SUMMARY_CHART_OUT),
            str(DWELL_MATRIX_CHART_OUT),
            str(PROMOTION_GATE_CHART_OUT),
        ],
        "timestamp_ready_order_count": int(summary.iloc[0]["timestamp_ready_order_count"]),
        "promotion_gate_pass_count": int(summary.iloc[0]["promotion_gate_pass_count"]),
        "dwell_rule_allowed": 0,
        "true_engine_allowed": 0,
        "strategy_feature_usable": 0,
    }
    _write_json(DECISION_OUT, decision)
    print(json.dumps(s045._json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
