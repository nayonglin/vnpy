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
STAGE = "Stage101"
MODEL_TAG = "stage101_absorption_reclaim_leadtime_diagnostic_v1"
OUTPUT_PREFIX = "qmt_roll_stage101_c9_minrisk_absorption_reclaim_leadtime_diagnostic"

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
STAGE100_DIR = LINE_DIR / "outputs" / "stage100_absorption_reclaim_preflight"
OUTPUT_DIR = LINE_DIR / "outputs" / "stage101_absorption_reclaim_leadtime_diagnostic"

STAGE100_ROWS_IN = (
    STAGE100_DIR
    / "qmt_roll_stage100_c9_minrisk_absorption_reclaim_preflight_preflight_rows_"
    "stage100_absorption_reclaim_preflight_v1.csv"
)

LEADTIME_ROWS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_leadtime_rows_{MODEL_TAG}.csv"
LEAD_BUCKET_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_lead_bucket_summary_{MODEL_TAG}.csv"
STATE_EVENT_LEAD_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_state_event_lead_summary_{MODEL_TAG}.csv"
PROMOTION_GATE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_promotion_gate_{MODEL_TAG}.csv"
SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
ATLAS_MANIFEST_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_atlas_manifest_{MODEL_TAG}.csv"

OFFICIAL_PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_chart_{MODEL_TAG}.png"
LEAD_BUCKET_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_lead_bucket_chart_{MODEL_TAG}.png"
STATE_EVENT_LEAD_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_state_event_lead_chart_{MODEL_TAG}.png"
GATE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_promotion_gate_chart_{MODEL_TAG}.png"
ATLAS_TEMPLATE = OUTPUT_DIR / f"{OUTPUT_PREFIX}_atlas_page{{page:03d}}_{MODEL_TAG}.png"

ATLAS_ROWS = 24
ATLAS_PER_PAGE = 4
MAX_ATLAS_BARS = 120

LEAD_BUCKET_ORDER = [
    "same_bar_event",
    "one_bar_lead",
    "two_to_five_bars",
    "six_to_twenty_bars",
    "gt_twenty_bars",
    "no_adverse",
    "no_event",
]

LEAD_BUCKET_COLORS = {
    "same_bar_event": "#dc2626",
    "one_bar_lead": "#f97316",
    "two_to_five_bars": "#eab308",
    "six_to_twenty_bars": "#2563eb",
    "gt_twenty_bars": "#0f766e",
    "no_adverse": "#64748b",
    "no_event": "#94a3b8",
}


def _json_safe(value: Any) -> Any:
    return s045._json_safe(value)


def _safe_float(value: Any, default: float = np.nan) -> float:
    return s045._safe_float(value, default=default)


def _write_csv(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, encoding="utf-8-sig")


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise RuntimeError(f"missing required input: {path}")
    return pd.read_csv(path, encoding="utf-8-sig")


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s038._md_table(frame, max_rows=max_rows)


def _time_text(value: Any) -> str:
    return s045._time_text(value)


def _lead_bucket(value: Any) -> str:
    number = _safe_float(value)
    if not np.isfinite(number):
        return "no_event"
    if number <= 0:
        return "same_bar_event"
    if number == 1:
        return "one_bar_lead"
    if number <= 5:
        return "two_to_five_bars"
    if number <= 20:
        return "six_to_twenty_bars"
    return "gt_twenty_bars"


def _prepare_rows(rows: pd.DataFrame) -> pd.DataFrame:
    data = rows.copy()
    for column in ["official_open_date", "first_adverse_time", "first_reclaim_time", "replay_c9_first_event_time"]:
        data[column] = pd.to_datetime(data[column], errors="coerce")
    for column in [
        "first_adverse_bar_idx",
        "first_reclaim_bar_idx",
        "pre_event_bar_count",
        "order_realized_pnl",
        "right_tail_visual",
        "bottom_loss_visual",
        "maxdd_context",
    ]:
        data[column] = pd.to_numeric(data[column], errors="coerce")
    data["event_bar_idx"] = np.where(
        data["replay_c9_first_event"].astype(str).isin(["stop", "progress"]),
        data["pre_event_bar_count"] - 1,
        np.nan,
    )
    data["bars_from_adverse_to_event"] = data["event_bar_idx"] - data["first_adverse_bar_idx"]
    data["bars_from_reclaim_to_event"] = data["event_bar_idx"] - data["first_reclaim_bar_idx"]
    data["minutes_from_adverse_to_event"] = (
        data["replay_c9_first_event_time"] - data["first_adverse_time"]
    ).dt.total_seconds() / 60.0
    data["minutes_from_reclaim_to_event"] = (
        data["replay_c9_first_event_time"] - data["first_reclaim_time"]
    ).dt.total_seconds() / 60.0
    data["adverse_to_event_bucket"] = data["bars_from_adverse_to_event"].map(_lead_bucket)
    data.loc[data["adverse_seen"].fillna(0).astype(int).eq(0), "adverse_to_event_bucket"] = "no_adverse"
    data.loc[~data["replay_c9_first_event"].astype(str).isin(["stop", "progress"]), "adverse_to_event_bucket"] = "no_event"
    data["bad_state_stop"] = (
        data["acceptance_state"].eq("adverse_no_reclaim_before_c9_event")
        & data["replay_c9_first_event"].eq("stop")
    ).astype(int)
    data["delayed_reclaim_progress"] = (
        data["acceptance_state"].eq("delayed_absorption_reclaim")
        & data["replay_c9_first_event"].eq("progress")
    ).astype(int)
    data["delayed_reclaim_stop"] = (
        data["acceptance_state"].eq("delayed_absorption_reclaim")
        & data["replay_c9_first_event"].eq("stop")
    ).astype(int)
    data["first_adverse_action_would_hit_right_tail"] = (
        data["acceptance_state"].eq("delayed_absorption_reclaim") & data["right_tail_visual"].eq(1)
    ).astype(int)
    data["leadtime_rule_allowed"] = 0
    data["true_engine_allowed"] = 0
    return data


def _lead_bucket_summary(rows: pd.DataFrame) -> pd.DataFrame:
    bad = rows[rows["bad_state_stop"].eq(1)].copy()
    if bad.empty:
        return pd.DataFrame()
    summary = (
        bad.groupby("adverse_to_event_bucket", dropna=False)
        .agg(
            order_count=("official_open_trade_id", "nunique"),
            pnl_sum=("order_realized_pnl", "sum"),
            pnl_min=("order_realized_pnl", "min"),
            pnl_max=("order_realized_pnl", "max"),
            median_bars_from_adverse_to_event=("bars_from_adverse_to_event", "median"),
            median_minutes_from_adverse_to_event=("minutes_from_adverse_to_event", "median"),
            maxdd_context_count=("maxdd_context", "sum"),
        )
        .reset_index()
    )
    summary["bucket_order"] = summary["adverse_to_event_bucket"].map({key: idx for idx, key in enumerate(LEAD_BUCKET_ORDER)})
    return summary.sort_values("bucket_order").drop(columns=["bucket_order"]).reset_index(drop=True)


def _state_event_lead_summary(rows: pd.DataFrame) -> pd.DataFrame:
    summary = (
        rows.groupby(["acceptance_state", "replay_c9_first_event", "adverse_to_event_bucket"], dropna=False)
        .agg(
            order_count=("official_open_trade_id", "nunique"),
            pnl_sum=("order_realized_pnl", "sum"),
            right_tail_count=("right_tail_visual", "sum"),
            bottom_loss_count=("bottom_loss_visual", "sum"),
            maxdd_context_count=("maxdd_context", "sum"),
            median_bars_from_adverse_to_event=("bars_from_adverse_to_event", "median"),
            median_minutes_from_adverse_to_event=("minutes_from_adverse_to_event", "median"),
        )
        .reset_index()
    )
    summary["bucket_order"] = summary["adverse_to_event_bucket"].map({key: idx for idx, key in enumerate(LEAD_BUCKET_ORDER)})
    return summary.sort_values(["acceptance_state", "replay_c9_first_event", "bucket_order"]).drop(
        columns=["bucket_order"]
    ).reset_index(drop=True)


def _promotion_gate(rows: pd.DataFrame) -> pd.DataFrame:
    bad = rows[rows["bad_state_stop"].eq(1)]
    delayed = rows[rows["acceptance_state"].eq("delayed_absorption_reclaim")]
    bad_same_or_one = int(bad["bars_from_adverse_to_event"].le(1).sum())
    bad_same = int(bad["bars_from_adverse_to_event"].le(0).sum())
    bad_two_plus = int(bad["bars_from_adverse_to_event"].ge(2).sum())
    delayed_right_tail = int(delayed["right_tail_visual"].sum())
    delayed_bottom_loss = int(delayed["bottom_loss_visual"].sum())
    delayed_progress_pnl = float(rows.loc[rows["delayed_reclaim_progress"].eq(1), "order_realized_pnl"].sum())
    rows_out = [
        {
            "gate_id": "no_reclaim_confirmation_too_late",
            "evidence_value": bad_same_or_one,
            "evidence_unit": "bad-state C9-stop orders with <=1 bar lead from first adverse touch",
            "pass_for_true_engine": 0,
            "judgment": "blocked",
        },
        {
            "gate_id": "same_bar_stop_ordering_ambiguity",
            "evidence_value": bad_same,
            "evidence_unit": "bad-state C9-stop orders where first adverse touch is on the stop event bar",
            "pass_for_true_engine": 0,
            "judgment": "blocked",
        },
        {
            "gate_id": "first_adverse_touch_hits_right_tail",
            "evidence_value": delayed_right_tail,
            "evidence_unit": "delayed-reclaim right-tail orders that already had first adverse touch",
            "pass_for_true_engine": 0,
            "judgment": "blocked",
        },
        {
            "gate_id": "delayed_reclaim_not_clean",
            "evidence_value": delayed_bottom_loss,
            "evidence_unit": "delayed-reclaim bottom-loss visual orders",
            "pass_for_true_engine": 0,
            "judgment": "blocked",
        },
        {
            "gate_id": "long_lead_requires_window_parameter",
            "evidence_value": bad_two_plus,
            "evidence_unit": "bad-state C9-stop orders with >=2 bars lead; rescue would require a waiting window",
            "pass_for_true_engine": 0,
            "judgment": "blocked",
        },
        {
            "gate_id": "right_tail_progress_dependency",
            "evidence_value": delayed_progress_pnl,
            "evidence_unit": "official PnL in delayed-reclaim/progress orders that must be protected",
            "pass_for_true_engine": 0,
            "judgment": "blocked",
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
    lead_bucket_summary: pd.DataFrame,
    gate: pd.DataFrame,
) -> pd.DataFrame:
    metrics = s038._official_metrics(curve, lots)
    bad = rows[rows["bad_state_stop"].eq(1)]
    delayed = rows[rows["acceptance_state"].eq("delayed_absorption_reclaim")]
    bad_same_or_one = int(bad["bars_from_adverse_to_event"].le(1).sum())
    bad_same_or_one_ratio = bad_same_or_one / len(bad) if len(bad) else np.nan
    bad_le_5 = int(bad["bars_from_adverse_to_event"].le(5).sum())
    bad_le_5_ratio = bad_le_5 / len(bad) if len(bad) else np.nan
    return pd.DataFrame(
        [
            {
                "stage": STAGE,
                "model_tag": MODEL_TAG,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "line_id": LINE_ID,
                "decision": "stage101_leadtime_not_actionable_no_rule",
                "official_config_changed": 0,
                "strategy_rule_created": 0,
                "true_engine_run": 0,
                "ab_triggered": 0,
                "order_api_called": 0,
                "ctp_connected": 0,
                "timestamp_ready_order_count": int(len(rows)),
                "bad_state_c9_stop_order_count": int(len(bad)),
                "bad_state_same_bar_order_count": int(bad["bars_from_adverse_to_event"].le(0).sum()),
                "bad_state_le_one_bar_order_count": bad_same_or_one,
                "bad_state_le_one_bar_ratio": bad_same_or_one_ratio,
                "bad_state_le_five_bar_order_count": bad_le_5,
                "bad_state_le_five_bar_ratio": bad_le_5_ratio,
                "bad_state_median_bars_to_event": float(bad["bars_from_adverse_to_event"].median())
                if len(bad)
                else np.nan,
                "bad_state_median_minutes_to_event": float(bad["minutes_from_adverse_to_event"].median())
                if len(bad)
                else np.nan,
                "bad_state_gt_twenty_bar_order_count": int(bad["bars_from_adverse_to_event"].gt(20).sum()),
                "delayed_reclaim_right_tail_count": int(delayed["right_tail_visual"].sum()),
                "delayed_reclaim_bottom_loss_count": int(delayed["bottom_loss_visual"].sum()),
                "delayed_reclaim_progress_pnl_sum": float(
                    rows.loc[rows["delayed_reclaim_progress"].eq(1), "order_realized_pnl"].sum()
                ),
                "lead_bucket_count": int(len(lead_bucket_summary)),
                "promotion_gate_count": int(len(gate)),
                "promotion_gate_pass_count": int(pd.to_numeric(gate["pass_for_true_engine"], errors="coerce").sum()),
                "leadtime_rule_allowed": 0,
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
    points = rows[rows["bad_state_stop"].eq(1)][["official_open_date", "adverse_to_event_bucket"]].merge(
        data[["date", "account_equity"]],
        left_on="official_open_date",
        right_on="date",
        how="left",
    )
    for bucket, group in points.groupby("adverse_to_event_bucket"):
        axes[0].scatter(
            group["official_open_date"],
            group["account_equity"],
            s=28,
            color=LEAD_BUCKET_COLORS.get(bucket, "#64748b"),
            label=bucket,
            alpha=0.8,
        )
    axes[0].legend(loc="upper left", fontsize=8, ncol=2)
    counts = rows[rows["bad_state_stop"].eq(1)]["adverse_to_event_bucket"].value_counts()
    counts = counts.reindex([item for item in LEAD_BUCKET_ORDER if item in counts.index])
    axes[2].bar(counts.index, counts.values, color=[LEAD_BUCKET_COLORS.get(item, "#64748b") for item in counts.index])
    axes[2].set_ylabel("bad-state stop orders")
    axes[2].tick_params(axis="x", rotation=20)
    axes[2].grid(True, axis="y", alpha=0.25)
    axes[0].set_title(
        f"{STAGE} lead-time diagnostic | bad stop {int(summary['bad_state_c9_stop_order_count'])} | rule_allowed=0"
    )
    fig.tight_layout()
    fig.savefig(OFFICIAL_PATH_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_lead_bucket(lead_bucket_summary: pd.DataFrame) -> None:
    data = lead_bucket_summary.copy()
    fig, axes = plt.subplots(2, 1, figsize=(12, 7), sharex=True)
    colors = [LEAD_BUCKET_COLORS.get(item, "#64748b") for item in data["adverse_to_event_bucket"]]
    axes[0].bar(data["adverse_to_event_bucket"], data["order_count"], color=colors, alpha=0.85)
    axes[0].set_ylabel("orders")
    axes[0].grid(True, axis="y", alpha=0.25)
    axes[1].bar(data["adverse_to_event_bucket"], data["pnl_sum"], color=colors, alpha=0.85)
    axes[1].axhline(0, color="#111827", linewidth=0.8)
    axes[1].set_ylabel("PnL sum")
    axes[1].tick_params(axis="x", rotation=20)
    axes[1].grid(True, axis="y", alpha=0.25)
    axes[0].set_title("Stage101 adverse-no-reclaim lead time is mostly too late")
    fig.tight_layout()
    fig.savefig(LEAD_BUCKET_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_state_event_lead(summary: pd.DataFrame) -> None:
    keep = summary[
        summary["acceptance_state"].isin(["adverse_no_reclaim_before_c9_event", "delayed_absorption_reclaim"])
    ].copy()
    labels = keep["acceptance_state"] + "|" + keep["replay_c9_first_event"] + "|" + keep["adverse_to_event_bucket"]
    fig, ax = plt.subplots(figsize=(14, 6))
    colors = [LEAD_BUCKET_COLORS.get(item, "#64748b") for item in keep["adverse_to_event_bucket"]]
    ax.bar(labels, keep["pnl_sum"], color=colors, alpha=0.82)
    ax.axhline(0, color="#111827", linewidth=0.8)
    ax.set_ylabel("PnL sum")
    ax.set_title("Stage101 lead buckets mix bad stop labels with delayed-reclaim right-tail protection")
    ax.tick_params(axis="x", rotation=35, labelsize=8)
    ax.grid(True, axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(STATE_EVENT_LEAD_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_gate(gate: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(12, 4.8))
    ax.bar(gate["gate_id"], gate["evidence_value"], color="#dc2626", alpha=0.82)
    ax.set_ylabel("evidence")
    ax.set_title("Stage101 actionability gates all blocked")
    ax.tick_params(axis="x", rotation=22)
    ax.grid(True, axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(GATE_CHART_OUT, dpi=160)
    plt.close(fig)


def _select_atlas_rows(rows: pd.DataFrame) -> pd.DataFrame:
    selected_parts = []
    bad = rows[rows["bad_state_stop"].eq(1)]
    for bucket in LEAD_BUCKET_ORDER:
        group = bad[bad["adverse_to_event_bucket"].eq(bucket)].copy()
        if not group.empty:
            selected_parts.append(group.sort_values("order_realized_pnl").head(2))
    delayed_right = rows[
        rows["acceptance_state"].eq("delayed_absorption_reclaim") & rows["right_tail_visual"].eq(1)
    ].sort_values("order_realized_pnl", ascending=False).head(6)
    delayed_loss = rows[
        rows["acceptance_state"].eq("delayed_absorption_reclaim") & rows["bottom_loss_visual"].eq(1)
    ].sort_values("order_realized_pnl").head(4)
    selected_parts.extend([delayed_right, delayed_loss])
    if not selected_parts:
        return pd.DataFrame()
    selected = pd.concat(selected_parts, ignore_index=True)
    selected = selected.drop_duplicates("candidate_index").head(ATLAS_ROWS)
    return selected.reset_index(drop=True)


def _plot_atlas(rows: pd.DataFrame, merged: pd.DataFrame, groups: dict[str, pd.DataFrame]) -> pd.DataFrame:
    selected = _select_atlas_rows(rows)
    manifest_rows: list[dict[str, Any]] = []
    if selected.empty:
        return pd.DataFrame()
    merged_index = merged.set_index("candidate_index", drop=False)
    total_pages = int(np.ceil(len(selected) / ATLAS_PER_PAGE))
    for page in range(total_pages):
        chunk = selected.iloc[page * ATLAS_PER_PAGE : (page + 1) * ATLAS_PER_PAGE]
        fig, axes = plt.subplots(len(chunk), 1, figsize=(13, 3.2 * len(chunk)), squeeze=False)
        out_path = Path(str(ATLAS_TEMPLATE).format(page=page + 1))
        for ax, (_, item) in zip(axes[:, 0], chunk.iterrows()):
            row = merged_index.loc[item["candidate_index"]]
            entry = _safe_float(row.get("replay_open_price"))
            risk = _safe_float(row.get("replay_risk_price"))
            sign = s038._direction_sign(row.get("direction"))
            scan = s100._pre_event_scan(row, groups)
            if scan.empty or not np.isfinite(entry) or not np.isfinite(risk) or risk <= 0:
                ax.text(0.5, 0.5, "missing path", transform=ax.transAxes, ha="center", va="center")
                continue
            path = s100._path_arrays(scan, entry, risk, sign).head(MAX_ATLAS_BARS)
            x = path["bar_idx"]
            ax.fill_between(x, path["low_r"], path["high_r"], color="#cbd5e1", alpha=0.45)
            ax.plot(x, path["close_r"], color=LEAD_BUCKET_COLORS.get(item["adverse_to_event_bucket"], "#334155"), linewidth=1.25)
            ax.axhline(0, color="#111827", linewidth=0.8)
            ax.axhline(0.5, color="#16a34a", linewidth=0.8, linestyle="--")
            ax.axhline(-0.5, color="#dc2626", linewidth=0.8, linestyle="--")
            if np.isfinite(_safe_float(item.get("first_adverse_bar_idx"))):
                ax.axvline(float(item["first_adverse_bar_idx"]), color="#dc2626", linewidth=0.9, linestyle=":")
            if np.isfinite(_safe_float(item.get("first_reclaim_bar_idx"))):
                ax.axvline(float(item["first_reclaim_bar_idx"]), color="#0f766e", linewidth=0.9, linestyle=":")
            if np.isfinite(_safe_float(item.get("event_bar_idx"))):
                ax.axvline(float(item["event_bar_idx"]), color="#111827", linewidth=0.9, linestyle="--")
            title = (
                f"{item['vt_symbol']} {item['direction']} {pd.Timestamp(item['official_open_date']).date()} | "
                f"{item['acceptance_state']} {item['replay_c9_first_event']} {item['adverse_to_event_bucket']} | "
                f"lead {item['bars_from_adverse_to_event'] if pd.notna(item['bars_from_adverse_to_event']) else ''} bars | "
                f"pnl {item['order_realized_pnl']:,.0f}"
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
                    "replay_c9_first_event": item["replay_c9_first_event"],
                    "adverse_to_event_bucket": item["adverse_to_event_bucket"],
                    "bars_from_adverse_to_event": item["bars_from_adverse_to_event"],
                    "minutes_from_adverse_to_event": item["minutes_from_adverse_to_event"],
                    "order_realized_pnl": item["order_realized_pnl"],
                    "right_tail_visual": item["right_tail_visual"],
                    "bottom_loss_visual": item["bottom_loss_visual"],
                    "maxdd_context": item["maxdd_context"],
                    "atlas_path": str(out_path),
                }
            )
        axes[-1, 0].set_xlabel("minute bar index from replay open; red=first adverse, green=reclaim, black=C9 event")
        fig.tight_layout()
        fig.savefig(out_path, dpi=160)
        plt.close(fig)
    return pd.DataFrame(manifest_rows)


def _write_report(
    summary: pd.DataFrame,
    lead_bucket_summary: pd.DataFrame,
    state_event_lead_summary: pd.DataFrame,
    gate: pd.DataFrame,
    atlas_manifest: pd.DataFrame,
) -> None:
    row = summary.iloc[0]
    report = "\n".join(
        [
            f"# {STAGE} absorption reclaim lead-time diagnostic",
            "",
            "## Decision",
            "",
            f"- decision: `{row['decision']}`",
            "- nature: read-only lead-time actionability diagnostic; no strategy rule, no true engine, no A/B, no CTP, no order API.",
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
            "## Lead-time Summary",
            "",
            f"- timestamp-ready orders: `{int(row['timestamp_ready_order_count'])}`",
            f"- bad-state C9-stop orders: `{int(row['bad_state_c9_stop_order_count'])}`",
            f"- same-bar stop orders: `{int(row['bad_state_same_bar_order_count'])}`",
            f"- <=1 bar lead orders: `{int(row['bad_state_le_one_bar_order_count'])}` (`{row['bad_state_le_one_bar_ratio']:.4f}`)",
            f"- <=5 bar lead orders: `{int(row['bad_state_le_five_bar_order_count'])}` (`{row['bad_state_le_five_bar_ratio']:.4f}`)",
            f"- median bad-state bars to event: `{row['bad_state_median_bars_to_event']:.4f}`",
            f"- median bad-state minutes to event: `{row['bad_state_median_minutes_to_event']:.4f}`",
            f"- >20 bar bad-state orders: `{int(row['bad_state_gt_twenty_bar_order_count'])}`",
            f"- delayed reclaim right-tail count: `{int(row['delayed_reclaim_right_tail_count'])}`",
            f"- delayed reclaim bottom-loss count: `{int(row['delayed_reclaim_bottom_loss_count'])}`",
            f"- delayed reclaim progress PnL: `{row['delayed_reclaim_progress_pnl_sum']:,.0f}`",
            f"- promotion gate pass count: `{int(row['promotion_gate_pass_count'])}`",
            "",
            "## Bad-state Lead Bucket Summary",
            "",
            _md_table(lead_bucket_summary, max_rows=20),
            "",
            "## State Event Lead Summary",
            "",
            _md_table(state_event_lead_summary, max_rows=60),
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
            f"- lead bucket chart: `{LEAD_BUCKET_CHART_OUT}`",
            f"- state event lead chart: `{STATE_EVENT_LEAD_CHART_OUT}`",
            f"- promotion gate chart: `{GATE_CHART_OUT}`",
            f"- atlas manifest: `{ATLAS_MANIFEST_OUT}`",
            "",
            "## Judgment",
            "",
            (
                "The negative adverse-no-reclaim label is mostly confirmed too late: most C9-stop cases have zero or one "
                "bar between first adverse touch and the stop event. Acting at first adverse touch is not acceptable either, "
                "because delayed-reclaim right-tail orders already contain the same first-adverse touch. This branch remains "
                "read-only and cannot enter true engine."
            ),
            "",
        ]
    )
    REPORT_OUT.parent.mkdir(parents=True, exist_ok=True)
    REPORT_OUT.write_text(report, encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    merged, curve, lots, _intraday, groups = s045._prepare_event_sync_frame()
    stage100_rows = _read_csv(STAGE100_ROWS_IN)
    rows = _prepare_rows(stage100_rows)
    lead_bucket_summary = _lead_bucket_summary(rows)
    state_event_lead_summary = _state_event_lead_summary(rows)
    gate = _promotion_gate(rows)
    summary = _summary(curve, lots, rows, lead_bucket_summary, gate)
    atlas_manifest = _plot_atlas(rows, merged, groups)

    _write_csv(rows, LEADTIME_ROWS_OUT)
    _write_csv(lead_bucket_summary, LEAD_BUCKET_SUMMARY_OUT)
    _write_csv(state_event_lead_summary, STATE_EVENT_LEAD_SUMMARY_OUT)
    _write_csv(gate, PROMOTION_GATE_OUT)
    _write_csv(summary, SUMMARY_OUT)
    _write_csv(atlas_manifest, ATLAS_MANIFEST_OUT)

    _plot_official_path(curve, rows, summary.iloc[0])
    _plot_lead_bucket(lead_bucket_summary)
    _plot_state_event_lead(state_event_lead_summary)
    _plot_gate(gate)
    _write_report(summary, lead_bucket_summary, state_event_lead_summary, gate, atlas_manifest)

    decision = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "decision": str(summary.iloc[0]["decision"]),
        "summary_path": str(SUMMARY_OUT),
        "report_path": str(REPORT_OUT),
        "leadtime_rows_path": str(LEADTIME_ROWS_OUT),
        "lead_bucket_summary_path": str(LEAD_BUCKET_SUMMARY_OUT),
        "state_event_lead_summary_path": str(STATE_EVENT_LEAD_SUMMARY_OUT),
        "promotion_gate_path": str(PROMOTION_GATE_OUT),
        "atlas_manifest_path": str(ATLAS_MANIFEST_OUT),
        "charts": [
            str(OFFICIAL_PATH_CHART_OUT),
            str(LEAD_BUCKET_CHART_OUT),
            str(STATE_EVENT_LEAD_CHART_OUT),
            str(GATE_CHART_OUT),
        ],
        "promotion_gate_pass_count": int(summary.iloc[0]["promotion_gate_pass_count"]),
        "leadtime_rule_allowed": 0,
        "true_engine_allowed": 0,
        "strategy_feature_usable": 0,
    }
    DECISION_OUT.write_text(json.dumps(_json_safe(decision), indent=2), encoding="utf-8")
    print(json.dumps(_json_safe(decision), indent=2))


if __name__ == "__main__":
    main()
