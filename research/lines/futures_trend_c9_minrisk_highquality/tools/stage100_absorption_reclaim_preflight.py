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
STAGE = "Stage100"
MODEL_TAG = "stage100_absorption_reclaim_preflight_v1"
OUTPUT_PREFIX = "qmt_roll_stage100_c9_minrisk_absorption_reclaim_preflight"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
TOOLS_DIR = SCRIPT_PATH.parent
EXAMPLE_DIR = REPO_DIR / "examples" / "portfolio_backtesting"
for path in [str(TOOLS_DIR), str(EXAMPLE_DIR)]:
    if path not in sys.path:
        sys.path.insert(0, path)

import stage038_order_event_replay_prototype_audit as s038  # noqa: E402
import stage045_event_time_field_sync_audit as s045  # noqa: E402


LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage100_absorption_reclaim_preflight"

PREFLIGHT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_preflight_rows_{MODEL_TAG}.csv"
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
GATE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_promotion_gate_chart_{MODEL_TAG}.png"
ATLAS_TEMPLATE = OUTPUT_DIR / f"{OUTPUT_PREFIX}_atlas_page{{page:03d}}_{MODEL_TAG}.png"

EPS = 1e-10
ATLAS_ROWS = 20
ATLAS_PER_PAGE = 4
MAX_ATLAS_BARS = 90
MAXDD_START = pd.Timestamp("2022-05-30")
MAXDD_END = pd.Timestamp("2023-03-09")

STATE_COLORS = {
    "delayed_absorption_reclaim": "#0f766e",
    "same_bar_adverse_reclaim_ambiguous": "#f97316",
    "direct_no_adverse_before_c9_event": "#2563eb",
    "adverse_no_reclaim_before_c9_event": "#dc2626",
    "invalid_or_missing_minute_path": "#64748b",
}


def _write_csv(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, encoding="utf-8-sig")


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s038._md_table(frame, max_rows=max_rows)


def _json_safe(value: Any) -> Any:
    return s045._json_safe(value)


def _safe_float(value: Any, default: float = np.nan) -> float:
    return s045._safe_float(value, default=default)


def _direction_sign(direction: Any) -> int:
    return s038._direction_sign(direction)


def _time_text(value: Any) -> str:
    return s045._time_text(value)


def _order_pnl(lots: pd.DataFrame) -> pd.DataFrame:
    frame = lots.copy()
    frame["realized_pnl"] = pd.to_numeric(frame["realized_pnl"], errors="coerce").fillna(0.0)
    frame["entry_date"] = pd.to_datetime(frame["entry_date"], errors="coerce").dt.normalize()
    return (
        frame.groupby("open_trade_id", dropna=False)
        .agg(
            order_lot_count=("lot_id", "nunique"),
            order_realized_pnl=("realized_pnl", "sum"),
            order_positive_pnl=("realized_pnl", lambda values: float(pd.to_numeric(values, errors="coerce").clip(lower=0).sum())),
            order_negative_pnl=("realized_pnl", lambda values: float(pd.to_numeric(values, errors="coerce").clip(upper=0).sum())),
            order_first_entry_date=("entry_date", "min"),
            order_exit_date=("exit_date", "max"),
            product=("product", "first"),
            ai_rank_bucket=("ai_rank_bucket", "first"),
        )
        .reset_index()
        .rename(columns={"open_trade_id": "official_open_trade_id"})
    )


def _path_arrays(scan: pd.DataFrame, entry: float, risk: float, sign: int) -> pd.DataFrame:
    data = scan.copy()
    for column in ["open", "high", "low", "close", "volume"]:
        data[column] = pd.to_numeric(data[column], errors="coerce")
    data["bar_datetime_ts"] = pd.to_datetime(data["bar_datetime_ts"], errors="coerce")
    if sign == 1:
        data["high_r"] = (data["high"] - entry) / risk
        data["low_r"] = (data["low"] - entry) / risk
        data["close_r"] = (data["close"] - entry) / risk
        data["adverse_hit"] = data["low"].lt(entry - EPS)
        data["reclaim_close"] = data["close"].ge(entry - EPS)
    else:
        data["high_r"] = (entry - data["low"]) / risk
        data["low_r"] = (entry - data["high"]) / risk
        data["close_r"] = (entry - data["close"]) / risk
        data["adverse_hit"] = data["high"].gt(entry + EPS)
        data["reclaim_close"] = data["close"].le(entry + EPS)
    data["bar_idx"] = np.arange(len(data))
    return data


def _pre_event_scan(row: pd.Series, groups: dict[str, pd.DataFrame]) -> pd.DataFrame:
    scan = s045._scan_bars_for_row(row, groups)
    if scan.empty:
        return scan
    event_time = pd.to_datetime(row.get("replay_c9_first_event_time"), errors="coerce")
    if pd.notna(event_time):
        scan = scan[pd.to_datetime(scan["bar_datetime_ts"], errors="coerce").le(pd.Timestamp(event_time))].copy()
    return scan.reset_index(drop=True)


def _classify_row(row: pd.Series, groups: dict[str, pd.DataFrame]) -> dict[str, Any]:
    entry = _safe_float(row.get("replay_open_price"))
    risk = _safe_float(row.get("replay_risk_price"))
    sign = _direction_sign(row.get("direction"))
    scan = _pre_event_scan(row, groups)
    base = {
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
        "acceptance_state": "invalid_or_missing_minute_path",
        "adverse_seen": 0,
        "reclaim_seen": 0,
        "same_bar_ambiguity": 0,
        "first_adverse_time": "",
        "first_reclaim_time": "",
        "first_adverse_bar_idx": np.nan,
        "first_reclaim_bar_idx": np.nan,
        "bars_to_reclaim_after_adverse": np.nan,
        "pre_event_bar_count": int(len(scan)),
        "pre_event_mfe_r": np.nan,
        "pre_event_mae_r": np.nan,
        "pre_event_close_r": np.nan,
        "preflight_rule_allowed": 0,
        "true_engine_allowed": 0,
    }
    if scan.empty or not np.isfinite(entry) or not np.isfinite(risk) or risk <= 0:
        return base

    path = _path_arrays(scan, entry, risk, sign)
    base["pre_event_mfe_r"] = float(pd.to_numeric(path["high_r"], errors="coerce").max())
    base["pre_event_mae_r"] = float(pd.to_numeric(path["low_r"], errors="coerce").min())
    base["pre_event_close_r"] = float(pd.to_numeric(path["close_r"], errors="coerce").iloc[-1])

    first_adverse_idx: int | None = None
    first_reclaim_idx: int | None = None
    same_bar = 0
    for _, item in path.iterrows():
        idx = int(item["bar_idx"])
        adverse_hit = bool(item["adverse_hit"])
        reclaim_close = bool(item["reclaim_close"])
        if first_adverse_idx is None and adverse_hit:
            first_adverse_idx = idx
            if reclaim_close:
                first_reclaim_idx = idx
                same_bar = 1
                break
            continue
        if first_adverse_idx is not None and reclaim_close:
            first_reclaim_idx = idx
            break

    if first_adverse_idx is None:
        state = "direct_no_adverse_before_c9_event"
    elif first_reclaim_idx is None:
        state = "adverse_no_reclaim_before_c9_event"
    elif same_bar:
        state = "same_bar_adverse_reclaim_ambiguous"
    else:
        state = "delayed_absorption_reclaim"

    base["acceptance_state"] = state
    base["adverse_seen"] = int(first_adverse_idx is not None)
    base["reclaim_seen"] = int(first_reclaim_idx is not None)
    base["same_bar_ambiguity"] = int(same_bar)
    if first_adverse_idx is not None:
        item = path.iloc[first_adverse_idx]
        base["first_adverse_time"] = _time_text(item.get("bar_datetime_ts"))
        base["first_adverse_bar_idx"] = first_adverse_idx
    if first_reclaim_idx is not None:
        item = path.iloc[first_reclaim_idx]
        base["first_reclaim_time"] = _time_text(item.get("bar_datetime_ts"))
        base["first_reclaim_bar_idx"] = first_reclaim_idx
    if first_adverse_idx is not None and first_reclaim_idx is not None:
        base["bars_to_reclaim_after_adverse"] = int(first_reclaim_idx - first_adverse_idx)
    return base


def _preflight_rows(merged: pd.DataFrame, lots: pd.DataFrame, groups: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows = [_classify_row(row, groups) for _, row in merged.iterrows()]
    result = pd.DataFrame(rows)
    pnl = _order_pnl(lots)
    result = result.merge(pnl, on="official_open_trade_id", how="left")
    result["order_realized_pnl"] = pd.to_numeric(result["order_realized_pnl"], errors="coerce").fillna(0.0)
    result["official_open_date"] = pd.to_datetime(result["official_open_date"], errors="coerce").dt.normalize()
    result["maxdd_context"] = result["official_open_date"].between(MAXDD_START, MAXDD_END).astype(int)
    result["pnl_rank_desc"] = result["order_realized_pnl"].rank(ascending=False, method="first")
    result["pnl_rank_asc"] = result["order_realized_pnl"].rank(ascending=True, method="first")
    visual_n = max(12, int(np.ceil(len(result) * 0.08)))
    result["right_tail_visual"] = result["pnl_rank_desc"].le(visual_n).astype(int)
    result["bottom_loss_visual"] = result["pnl_rank_asc"].le(visual_n).astype(int)
    result["selected_for_atlas"] = 0
    selected_index = set(result[result["right_tail_visual"].eq(1)].sort_values("pnl_rank_desc").head(8).index)
    selected_index.update(result[result["bottom_loss_visual"].eq(1)].sort_values("pnl_rank_asc").head(8).index)
    selected_index.update(
        result[result["maxdd_context"].eq(1)]
        .sort_values(["acceptance_state", "order_realized_pnl"])
        .head(8)
        .index
    )
    for state, group in result.groupby("acceptance_state"):
        selected_index.update(group.reindex(group["order_realized_pnl"].abs().sort_values(ascending=False).index).head(2).index)
    result.loc[list(selected_index)[:ATLAS_ROWS], "selected_for_atlas"] = 1
    return result.sort_values(["official_open_date", "candidate_index"]).reset_index(drop=True)


def _state_summary(rows: pd.DataFrame) -> pd.DataFrame:
    summary = (
        rows.groupby("acceptance_state", dropna=False)
        .agg(
            order_count=("official_open_trade_id", "nunique"),
            lot_count=("order_lot_count", "sum"),
            pnl_sum=("order_realized_pnl", "sum"),
            pnl_mean=("order_realized_pnl", "mean"),
            pnl_min=("order_realized_pnl", "min"),
            pnl_max=("order_realized_pnl", "max"),
            positive_order_count=("order_realized_pnl", lambda values: int((pd.to_numeric(values, errors="coerce") > 0).sum())),
            negative_order_count=("order_realized_pnl", lambda values: int((pd.to_numeric(values, errors="coerce") < 0).sum())),
            right_tail_count=("right_tail_visual", "sum"),
            bottom_loss_count=("bottom_loss_visual", "sum"),
            maxdd_context_count=("maxdd_context", "sum"),
            same_bar_ambiguity_count=("same_bar_ambiguity", "sum"),
            median_bars_to_reclaim=("bars_to_reclaim_after_adverse", "median"),
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
        rows.groupby(["acceptance_state", "replay_c9_first_event"], dropna=False)
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
    return summary.sort_values(["acceptance_state", "replay_c9_first_event"]).reset_index(drop=True)


def _promotion_gate(rows: pd.DataFrame, state_summary: pd.DataFrame) -> pd.DataFrame:
    delayed = rows[rows["acceptance_state"].eq("delayed_absorption_reclaim")]
    right_tail_total = int(rows["right_tail_visual"].sum())
    right_tail_delayed = int(delayed["right_tail_visual"].sum()) if not delayed.empty else 0
    bottom_loss_delayed = int(delayed["bottom_loss_visual"].sum()) if not delayed.empty else 0
    mixed_states = int(state_summary["pnl_sign_conflict"].sum())
    tail_conflict_states = int(state_summary["right_tail_and_bottom_loss_conflict"].sum())
    ambiguity_orders = int(rows["same_bar_ambiguity"].sum())
    rows_out = [
        {
            "gate_id": "right_tail_protection",
            "evidence_value": right_tail_total - right_tail_delayed,
            "evidence_unit": "right-tail visual orders outside delayed absorption reclaim",
            "pass_for_true_engine": 0,
            "judgment": "fail_or_watch_only",
        },
        {
            "gate_id": "bottom_loss_separation",
            "evidence_value": bottom_loss_delayed,
            "evidence_unit": "bottom-loss visual orders also inside delayed absorption reclaim",
            "pass_for_true_engine": 0,
            "judgment": "fail_or_watch_only",
        },
        {
            "gate_id": "state_pnl_mixture",
            "evidence_value": mixed_states,
            "evidence_unit": "acceptance states with both positive and negative PnL",
            "pass_for_true_engine": 0,
            "judgment": "fail_or_watch_only",
        },
        {
            "gate_id": "same_bar_ordering_ambiguity",
            "evidence_value": ambiguity_orders,
            "evidence_unit": "orders where adverse touch and reclaim close occur in same minute bar",
            "pass_for_true_engine": 0,
            "judgment": "fail_or_watch_only",
        },
        {
            "gate_id": "tail_state_conflict",
            "evidence_value": tail_conflict_states,
            "evidence_unit": "states containing both right-tail and bottom-loss visual orders",
            "pass_for_true_engine": 0,
            "judgment": "fail_or_watch_only",
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
    state_event_summary: pd.DataFrame,
    gate: pd.DataFrame,
) -> pd.DataFrame:
    metrics = s038._official_metrics(curve, lots)
    delayed = state_summary[state_summary["acceptance_state"].eq("delayed_absorption_reclaim")]
    delayed_count = int(delayed["order_count"].iloc[0]) if not delayed.empty else 0
    delayed_pnl = float(delayed["pnl_sum"].iloc[0]) if not delayed.empty else 0.0
    adverse_stop = state_event_summary[
        state_event_summary["acceptance_state"].eq("adverse_no_reclaim_before_c9_event")
        & state_event_summary["replay_c9_first_event"].eq("stop")
    ]
    delayed_progress = state_event_summary[
        state_event_summary["acceptance_state"].eq("delayed_absorption_reclaim")
        & state_event_summary["replay_c9_first_event"].eq("progress")
    ]
    return pd.DataFrame(
        [
            {
                "stage": STAGE,
                "model_tag": MODEL_TAG,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "line_id": LINE_ID,
                "decision": "stage100_absorption_reclaim_preflight_mixed_no_rule",
                "official_config_changed": 0,
                "strategy_rule_created": 0,
                "true_engine_run": 0,
                "ab_triggered": 0,
                "order_api_called": 0,
                "ctp_connected": 0,
                "timestamp_ready_order_count": int(len(rows)),
                "acceptance_state_count": int(rows["acceptance_state"].nunique()),
                "delayed_absorption_reclaim_order_count": delayed_count,
                "delayed_absorption_reclaim_pnl_sum": delayed_pnl,
                "right_tail_visual_count": int(rows["right_tail_visual"].sum()),
                "bottom_loss_visual_count": int(rows["bottom_loss_visual"].sum()),
                "maxdd_context_order_count": int(rows["maxdd_context"].sum()),
                "same_bar_ambiguity_order_count": int(rows["same_bar_ambiguity"].sum()),
                "pnl_mixed_state_count": int(state_summary["pnl_sign_conflict"].sum()),
                "tail_conflict_state_count": int(state_summary["right_tail_and_bottom_loss_conflict"].sum()),
                "adverse_no_reclaim_c9_stop_order_count": int(adverse_stop["order_count"].iloc[0])
                if not adverse_stop.empty
                else 0,
                "delayed_reclaim_c9_progress_order_count": int(delayed_progress["order_count"].iloc[0])
                if not delayed_progress.empty
                else 0,
                "delayed_reclaim_c9_progress_pnl_sum": float(delayed_progress["pnl_sum"].iloc[0])
                if not delayed_progress.empty
                else 0.0,
                "promotion_gate_count": int(len(gate)),
                "promotion_gate_pass_count": int(pd.to_numeric(gate["pass_for_true_engine"], errors="coerce").sum()),
                "preflight_rule_allowed": 0,
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
    points = rows[["official_open_date", "acceptance_state"]].merge(
        data[["date", "account_equity"]], left_on="official_open_date", right_on="date", how="left"
    )
    for state, group in points.groupby("acceptance_state"):
        axes[0].scatter(
            group["official_open_date"],
            group["account_equity"],
            s=24,
            color=STATE_COLORS.get(state, "#64748b"),
            label=state,
            alpha=0.72,
        )
    axes[0].legend(loc="upper left", fontsize=7, ncol=2)
    counts = rows["acceptance_state"].value_counts()
    axes[2].bar(counts.index, counts.values, color=[STATE_COLORS.get(item, "#64748b") for item in counts.index])
    axes[2].set_ylabel("orders")
    axes[2].tick_params(axis="x", rotation=18)
    axes[2].grid(True, axis="y", alpha=0.25)
    axes[0].set_title(
        f"{STAGE} absorption reclaim preflight | orders {int(summary['timestamp_ready_order_count'])} | rule_allowed=0"
    )
    fig.tight_layout()
    fig.savefig(OFFICIAL_PATH_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_state_contribution(rows: pd.DataFrame) -> None:
    data = rows.sort_values(["official_open_date", "candidate_index"]).copy()
    fig, ax = plt.subplots(figsize=(13, 6))
    for state, group in data.groupby("acceptance_state"):
        series = (
            group.groupby("official_open_date")["order_realized_pnl"]
            .sum()
            .sort_index()
            .cumsum()
        )
        ax.plot(series.index, series.values, label=state, color=STATE_COLORS.get(state, "#64748b"), linewidth=1.4)
    ax.axhline(0, color="#111827", linewidth=0.8)
    ax.set_title("Stage100 official realized PnL contribution by predeclared acceptance state")
    ax.set_ylabel("cumulative realized PnL")
    ax.grid(True, alpha=0.25)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(STATE_CONTRIBUTION_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_state_summary(state_summary: pd.DataFrame) -> None:
    data = state_summary.copy()
    x = np.arange(len(data))
    fig, axes = plt.subplots(2, 1, figsize=(13, 8), sharex=True, gridspec_kw={"height_ratios": [1.0, 1.1]})
    colors = [STATE_COLORS.get(item, "#64748b") for item in data["acceptance_state"]]
    axes[0].bar(x, data["order_count"], color=colors, alpha=0.82)
    axes[0].set_ylabel("orders")
    axes[0].grid(True, axis="y", alpha=0.25)
    axes[1].bar(x, data["pnl_sum"], color=colors, alpha=0.82)
    axes[1].axhline(0, color="#111827", linewidth=0.8)
    axes[1].set_ylabel("PnL sum")
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(data["acceptance_state"], rotation=18, ha="right")
    axes[1].grid(True, axis="y", alpha=0.25)
    axes[0].set_title("Stage100 state count and PnL; mixed states block promotion")
    fig.tight_layout()
    fig.savefig(STATE_SUMMARY_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_gate(gate: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(11, 4.8))
    ax.bar(gate["gate_id"], gate["evidence_value"], color="#dc2626", alpha=0.82)
    ax.set_ylabel("evidence count")
    ax.set_title("Stage100 promotion gates all blocked")
    ax.tick_params(axis="x", rotation=20)
    ax.grid(True, axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(GATE_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_atlas(rows: pd.DataFrame, merged: pd.DataFrame, groups: dict[str, pd.DataFrame]) -> pd.DataFrame:
    selected = rows[rows["selected_for_atlas"].eq(1)].copy()
    selected = selected.sort_values(["right_tail_visual", "bottom_loss_visual", "maxdd_context", "order_realized_pnl"], ascending=[False, False, False, True])
    selected = selected.head(ATLAS_ROWS)
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
            scan = _pre_event_scan(row, groups)
            if scan.empty or not np.isfinite(entry) or not np.isfinite(risk) or risk <= 0:
                ax.text(0.5, 0.5, "missing path", transform=ax.transAxes, ha="center", va="center")
                continue
            path = _path_arrays(scan, entry, risk, sign).head(MAX_ATLAS_BARS)
            x = path["bar_idx"]
            ax.fill_between(x, path["low_r"], path["high_r"], color="#cbd5e1", alpha=0.45, label="bar high-low R")
            ax.plot(x, path["close_r"], color=STATE_COLORS.get(item["acceptance_state"], "#334155"), linewidth=1.2, label="close R")
            ax.axhline(0, color="#111827", linewidth=0.8)
            ax.axhline(0.5, color="#16a34a", linewidth=0.8, linestyle="--")
            ax.axhline(-0.5, color="#dc2626", linewidth=0.8, linestyle="--")
            if np.isfinite(item["first_adverse_bar_idx"]):
                ax.axvline(item["first_adverse_bar_idx"], color="#dc2626", linewidth=0.9, linestyle=":")
            if np.isfinite(item["first_reclaim_bar_idx"]):
                ax.axvline(item["first_reclaim_bar_idx"], color="#0f766e", linewidth=0.9, linestyle=":")
            title = (
                f"{item['vt_symbol']} {item['direction']} {pd.Timestamp(item['official_open_date']).date()} | "
                f"{item['acceptance_state']} | pnl {item['order_realized_pnl']:,.0f} | "
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
                    "acceptance_state": item["acceptance_state"],
                    "order_realized_pnl": item["order_realized_pnl"],
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
            f"# {STAGE} absorption reclaim preflight",
            "",
            "## Decision",
            "",
            f"- decision: `{row['decision']}`",
            "- nature: read-only preflight; no strategy rule, no true engine, no A/B, no CTP, no order API.",
            "- frozen idea: adverse touch after entry, then a later minute close reclaims entry price before C9 first event.",
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
            f"- acceptance states: `{int(row['acceptance_state_count'])}`",
            f"- delayed absorption reclaim orders: `{int(row['delayed_absorption_reclaim_order_count'])}`",
            f"- delayed absorption reclaim PnL: `{row['delayed_absorption_reclaim_pnl_sum']:,.0f}`",
            f"- right-tail visual orders: `{int(row['right_tail_visual_count'])}`",
            f"- bottom-loss visual orders: `{int(row['bottom_loss_visual_count'])}`",
            f"- maxDD context orders: `{int(row['maxdd_context_order_count'])}`",
            f"- same-bar ambiguity orders: `{int(row['same_bar_ambiguity_order_count'])}`",
            f"- mixed PnL states: `{int(row['pnl_mixed_state_count'])}`",
            f"- tail-conflict states: `{int(row['tail_conflict_state_count'])}`",
            f"- adverse-no-reclaim with C9 stop: `{int(row['adverse_no_reclaim_c9_stop_order_count'])}`",
            f"- delayed reclaim with C9 progress: `{int(row['delayed_reclaim_c9_progress_order_count'])}`",
            f"- delayed reclaim C9 progress PnL: `{row['delayed_reclaim_c9_progress_pnl_sum']:,.0f}`",
            f"- promotion gate pass count: `{int(row['promotion_gate_pass_count'])}`",
            "",
            "## State Summary",
            "",
            _md_table(state_summary, max_rows=20),
            "",
            "## State Event Summary",
            "",
            _md_table(state_event_summary, max_rows=30),
            "",
            "## Promotion Gates",
            "",
            _md_table(gate, max_rows=20),
            "",
            "## Atlas Manifest",
            "",
            _md_table(atlas_manifest, max_rows=40),
            "",
            "## Visual outputs",
            "",
            f"- official path chart: `{OFFICIAL_PATH_CHART_OUT}`",
            f"- state contribution chart: `{STATE_CONTRIBUTION_CHART_OUT}`",
            f"- state summary chart: `{STATE_SUMMARY_CHART_OUT}`",
            f"- promotion gate chart: `{GATE_CHART_OUT}`",
            f"- atlas manifest: `{ATLAS_MANIFEST_OUT}`",
            "",
            "## Judgment",
            "",
            (
                "The absorption-reclaim idea is economically distinct from the closed no-follow and hard-exit routes, "
                "but the read-only state split is mixed and has same-bar ordering ambiguity. It is not rule-ready and "
                "must not enter true engine without a stronger, point-in-time spec that protects right-tail orders."
            ),
            "",
        ]
    )
    REPORT_OUT.parent.mkdir(parents=True, exist_ok=True)
    REPORT_OUT.write_text(report, encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    merged, curve, lots, _intraday, groups = s045._prepare_event_sync_frame()
    rows = _preflight_rows(merged, lots, groups)
    state_summary = _state_summary(rows)
    state_event_summary = _state_event_summary(rows)
    gate = _promotion_gate(rows, state_summary)
    summary = _summary(curve, lots, rows, state_summary, state_event_summary, gate)
    atlas_manifest = _plot_atlas(rows, merged, groups)

    _write_csv(rows, PREFLIGHT_OUT)
    _write_csv(state_summary, STATE_SUMMARY_OUT)
    _write_csv(state_event_summary, STATE_EVENT_SUMMARY_OUT)
    _write_csv(gate, PROMOTION_GATE_OUT)
    _write_csv(summary, SUMMARY_OUT)
    _write_csv(atlas_manifest, ATLAS_MANIFEST_OUT)

    _plot_official_path(curve, rows, summary.iloc[0])
    _plot_state_contribution(rows)
    _plot_state_summary(state_summary)
    _plot_gate(gate)
    _write_report(summary, state_summary, state_event_summary, gate, atlas_manifest)

    decision = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "decision": str(summary.iloc[0]["decision"]),
        "summary_path": str(SUMMARY_OUT),
        "report_path": str(REPORT_OUT),
        "preflight_rows_path": str(PREFLIGHT_OUT),
        "state_summary_path": str(STATE_SUMMARY_OUT),
        "state_event_summary_path": str(STATE_EVENT_SUMMARY_OUT),
        "promotion_gate_path": str(PROMOTION_GATE_OUT),
        "atlas_manifest_path": str(ATLAS_MANIFEST_OUT),
        "charts": [
            str(OFFICIAL_PATH_CHART_OUT),
            str(STATE_CONTRIBUTION_CHART_OUT),
            str(STATE_SUMMARY_CHART_OUT),
            str(GATE_CHART_OUT),
        ],
        "promotion_gate_pass_count": int(summary.iloc[0]["promotion_gate_pass_count"]),
        "preflight_rule_allowed": 0,
        "true_engine_allowed": 0,
        "strategy_feature_usable": 0,
    }
    DECISION_OUT.write_text(json.dumps(_json_safe(decision), indent=2), encoding="utf-8")
    print(json.dumps(_json_safe(decision), indent=2))


if __name__ == "__main__":
    main()
