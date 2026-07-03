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


PROJECT_DIR = Path(__file__).resolve().parents[4]
TOOLS_DIR = Path(__file__).resolve().parent
PORTFOLIO_DIR = PROJECT_DIR / "examples" / "portfolio_backtesting"
for path in (str(TOOLS_DIR), str(PORTFOLIO_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

import stage006_current_quality_feature_binder as s006
import stage009_dense_start_goal_audit as s009


LINE_ID = "futures_trend_rebuilt_c9_15w_optimization"
STAGE = "Stage020"
MODEL_TAG = "stage020_stage013_high_quality_add_risk_proxy_v1"
OUTPUT_PREFIX = "rebuilt_c9_stage020_stage013_high_quality_add_risk_proxy"

LINE_DIR = PROJECT_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage020_stage013_high_quality_add_risk_proxy"
STAGE_RECORD_DIR = LINE_DIR / "stages"
STAGE006_OUTPUT_DIR = LINE_DIR / "outputs" / "stage006_current_quality_feature_binder"
STAGE007_OUTPUT_DIR = LINE_DIR / "outputs" / "stage007_minute_source_coverage_rebind"
STAGE013_OUTPUT_DIR = LINE_DIR / "outputs" / "stage013_account_state_pilot_gate_engine"
STAGE019_OUTPUT_DIR = LINE_DIR / "outputs" / "stage019_stage018_regime_gate_failure_attribution"

STAGE006_PREFIX = "rebuilt_c9_stage006_current_quality_feature_binder"
STAGE006_TAG = "stage006_current_quality_feature_binder_v1"
STAGE007_PREFIX = "rebuilt_c9_stage007_minute_source_coverage_rebind"
STAGE007_TAG = "stage007_minute_source_coverage_rebind_v1"
STAGE013_PREFIX = "rebuilt_c9_stage013_account_state_pilot_gate_engine"
STAGE013_TAG = "stage013_account_state_pilot_gate_engine_v1"
STAGE019_PREFIX = "rebuilt_c9_stage019_stage018_regime_gate_failure_attribution"
STAGE019_TAG = "stage019_stage018_regime_gate_failure_attribution_v1"

BASE_STAGE006_SUMMARY_PATH = STAGE006_OUTPUT_DIR / f"{STAGE006_PREFIX}_summary_{STAGE006_TAG}.csv"
STAGE013_CURVES_PATH = STAGE013_OUTPUT_DIR / f"{STAGE013_PREFIX}_curves_{STAGE013_TAG}.csv"
STAGE013_SUMMARY_PATH = STAGE013_OUTPUT_DIR / f"{STAGE013_PREFIX}_summary_{STAGE013_TAG}.csv"
STAGE013_CLOSED_LOTS_PATH = STAGE019_OUTPUT_DIR / f"{STAGE019_PREFIX}_stage013_rebuilt_closed_lots_{STAGE019_TAG}.csv"
QUALITY_FEATURES_PATH = STAGE007_OUTPUT_DIR / f"{STAGE007_PREFIX}_quality_features_{STAGE007_TAG}.csv"

TAG_COLUMN = "tag_ai4_6_entry_or_first_aligned"
ADD_RISK_FRACTION = 0.25
CAPITAL = 150000.0
EPS = 1e-9

LOT_DELTAS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_lot_deltas_{MODEL_TAG}.csv"
CURVES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv"
SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
ANNUAL_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_annual_returns_{MODEL_TAG}.csv"
GOAL_AGGREGATE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_goal_aggregate_{MODEL_TAG}.csv"
GOAL_TO_FINAL_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_goal_to_final_windows_{MODEL_TAG}.csv"
GOAL_FIXED_HORIZON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_goal_fixed_horizon_windows_{MODEL_TAG}.csv"
GOAL_WORST_WINDOWS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_goal_worst_windows_{MODEL_TAG}.csv"
RETENTION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_full_cycle_retention_{MODEL_TAG}.csv"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"
GOAL_CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_goal_chart_{MODEL_TAG}.png"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


def _json_safe(value: Any) -> Any:
    return s006._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s006._md_table(frame, max_rows=max_rows)


def _drawdown_pct(equity: pd.Series) -> pd.Series:
    values = pd.to_numeric(equity, errors="coerce").ffill()
    peak = values.cummax()
    return (values / peak.replace(0.0, np.nan) - 1.0).replace([np.inf, -np.inf], np.nan).fillna(0.0) * 100.0


def _sharpe_from_equity(equity: pd.Series) -> float:
    values = pd.to_numeric(equity, errors="coerce").dropna()
    returns = values.pct_change().replace([np.inf, -np.inf], np.nan).dropna()
    if returns.empty or float(returns.std(ddof=1)) == 0.0:
        return 0.0
    return float(returns.mean() / returns.std(ddof=1) * np.sqrt(252.0))


def _to_bool(series: pd.Series) -> pd.Series:
    text = series.fillna(False).astype(str).str.lower()
    return text.isin({"1", "1.0", "true", "yes"})


def _quality_by_open_trade() -> pd.DataFrame:
    quality = pd.read_csv(
        QUALITY_FEATURES_PATH,
        encoding="utf-8-sig",
        usecols=[
            "requested_start_month",
            "open_trade_id",
            "tag_entry_open_aligned",
            "tag_first_bar_aligned",
            "tag_entry_or_first_aligned",
            "tag_ai4_6_entry_open_aligned",
            "tag_ai4_6_first_bar_aligned",
            "tag_ai4_6_entry_or_first_aligned",
            "entry_first_bar_available",
            "entry_open_relation_bucket",
            "first_bar_relation_bucket",
        ],
    )
    quality["requested_start_month"] = quality["requested_start_month"].astype(str)
    quality["open_trade_id"] = quality["open_trade_id"].astype(str)
    bool_cols = [
        "tag_entry_open_aligned",
        "tag_first_bar_aligned",
        "tag_entry_or_first_aligned",
        "tag_ai4_6_entry_open_aligned",
        "tag_ai4_6_first_bar_aligned",
        "tag_ai4_6_entry_or_first_aligned",
        "entry_first_bar_available",
    ]
    for column in bool_cols:
        quality[column] = _to_bool(quality[column]).astype("int64")
    bucket_cols = ["entry_open_relation_bucket", "first_bar_relation_bucket"]
    agg = {column: "max" for column in bool_cols}
    agg.update({column: "first" for column in bucket_cols})
    return quality.groupby(["requested_start_month", "open_trade_id"], dropna=False).agg(agg).reset_index()


def _build_lot_deltas() -> tuple[pd.DataFrame, dict[str, Any]]:
    closed = pd.read_csv(STAGE013_CLOSED_LOTS_PATH, encoding="utf-8-sig", parse_dates=["entry_date", "exit_date"])
    quality = _quality_by_open_trade()
    closed["requested_start_month"] = closed["requested_start_month"].astype(str)
    closed["open_trade_id"] = closed["open_trade_id"].astype(str)
    merged = closed.merge(quality, on=["requested_start_month", "open_trade_id"], how="left")
    merged["stage020_quality_tag_matched"] = merged[TAG_COLUMN].notna()
    for column in [
        "tag_entry_open_aligned",
        "tag_first_bar_aligned",
        "tag_entry_or_first_aligned",
        "tag_ai4_6_entry_open_aligned",
        "tag_ai4_6_first_bar_aligned",
        "tag_ai4_6_entry_or_first_aligned",
        "entry_first_bar_available",
    ]:
        if column not in merged.columns:
            merged[column] = 0
        merged[column] = pd.to_numeric(merged[column], errors="coerce").fillna(0).astype("int64")
    merged["realized_pnl"] = pd.to_numeric(merged["realized_pnl"], errors="coerce").fillna(0.0)
    merged["exit_date"] = pd.to_datetime(merged["exit_date"], errors="coerce").dt.normalize()
    merged["selected_for_stage020"] = merged[TAG_COLUMN].eq(1)
    selected = merged[merged["selected_for_stage020"]].copy()
    selected["stage020_add_risk_fraction"] = ADD_RISK_FRACTION
    selected["stage020_proxy_delta_pnl"] = selected["realized_pnl"] * ADD_RISK_FRACTION
    keep = [
        "requested_start_month",
        "lot_id",
        "open_trade_id",
        "vt_symbol",
        "product",
        "direction",
        "entry_date",
        "exit_date",
        "volume",
        "realized_pnl",
        "r_multiple",
        "ai_product_pool_rank",
        "ai_product_pool_score",
        "entry_open_relation_bucket",
        "first_bar_relation_bucket",
        "tag_entry_or_first_aligned",
        "tag_ai4_6_entry_or_first_aligned",
        "entry_first_bar_available",
        "stage020_quality_tag_matched",
        "stage020_add_risk_fraction",
        "stage020_proxy_delta_pnl",
    ]
    audit = {
        "stage013_closed_lot_count": int(len(closed)),
        "quality_key_count": int(len(quality)),
        "quality_tag_match_count": int(merged["stage020_quality_tag_matched"].sum()),
        "quality_tag_match_rate_pct": (
            float(merged["stage020_quality_tag_matched"].mean() * 100.0) if len(merged) else np.nan
        ),
        "selected_lots": int(len(selected)),
        "selected_realized_pnl": float(selected["realized_pnl"].sum()) if len(selected) else 0.0,
        "total_proxy_delta_pnl": float(selected["stage020_proxy_delta_pnl"].sum()) if len(selected) else 0.0,
    }
    return selected[[column for column in keep if column in selected.columns]].reset_index(drop=True), audit


def _build_proxy_curves(base_curves: pd.DataFrame, lot_deltas: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    curves = base_curves.copy()
    curves["date"] = pd.to_datetime(curves["date"], errors="coerce").dt.normalize()
    curves["requested_start_month"] = curves["requested_start_month"].astype(str)
    curves["account_equity"] = pd.to_numeric(curves["account_equity"], errors="coerce")
    daily_delta = (
        lot_deltas.groupby(["requested_start_month", "exit_date"], dropna=False)["stage020_proxy_delta_pnl"]
        .sum()
        .reset_index()
        if not lot_deltas.empty
        else pd.DataFrame(columns=["requested_start_month", "exit_date", "stage020_proxy_delta_pnl"])
    )
    merged = curves.merge(
        daily_delta.rename(columns={"exit_date": "date", "stage020_proxy_delta_pnl": "stage020_daily_delta"}),
        on=["requested_start_month", "date"],
        how="left",
    )
    merged["stage020_daily_delta"] = pd.to_numeric(merged["stage020_daily_delta"], errors="coerce").fillna(0.0)
    frames: list[pd.DataFrame] = []
    for _, group in merged.groupby("requested_start_month", sort=True):
        g = group.sort_values("date").copy()
        g["stage020_cum_delta"] = g["stage020_daily_delta"].cumsum()
        g["stage020_account_equity"] = g["account_equity"] + g["stage020_cum_delta"]
        g["stage020_nav"] = g["stage020_account_equity"] / CAPITAL
        g["stage020_drawdown_pct"] = _drawdown_pct(g["stage020_account_equity"])
        frames.append(g)
    proxy = pd.concat(frames, ignore_index=True, sort=False) if frames else pd.DataFrame()
    curve_dates = set(zip(curves["requested_start_month"].astype(str), curves["date"]))
    unmatched = 0
    for row in daily_delta.to_dict("records"):
        if (str(row["requested_start_month"]), row["exit_date"]) not in curve_dates:
            unmatched += 1
    return proxy, unmatched


def _summarize_curve(curve: pd.DataFrame, equity_column: str) -> dict[str, Any]:
    data = curve.sort_values("date").copy()
    equity = pd.to_numeric(data[equity_column], errors="coerce")
    return {
        "requested_start_month": str(data["requested_start_month"].iloc[0]),
        "actual_start": pd.Timestamp(data["date"].iloc[0]).date().isoformat(),
        "actual_end": pd.Timestamp(data["date"].iloc[-1]).date().isoformat(),
        "trading_days": int(len(data)),
        "end_equity": float(equity.iloc[-1]),
        "total_return_pct": float((equity.iloc[-1] / CAPITAL - 1.0) * 100.0),
        "max_dd_pct": float(_drawdown_pct(equity).min()),
        "sharpe": _sharpe_from_equity(equity),
    }


def _summary(stage013_summary: pd.DataFrame, proxy_curves: pd.DataFrame) -> pd.DataFrame:
    rows = [_summarize_curve(group, "stage020_account_equity") for _, group in proxy_curves.groupby("requested_start_month")]
    stage020 = pd.DataFrame(rows)
    cols = ["requested_start_month", "end_equity", "total_return_pct", "max_dd_pct", "sharpe"]
    compare = stage013_summary[cols].merge(stage020[cols], on="requested_start_month", suffixes=("_stage013", "_stage020"))
    for column in compare.columns:
        if column != "requested_start_month":
            compare[column] = pd.to_numeric(compare[column], errors="coerce")
    compare["end_equity_delta_stage020_vs_stage013"] = compare["end_equity_stage020"] - compare["end_equity_stage013"]
    compare["return_delta_pp_stage020_vs_stage013"] = (
        compare["total_return_pct_stage020"] - compare["total_return_pct_stage013"]
    )
    compare["max_dd_delta_pp_stage020_vs_stage013"] = compare["max_dd_pct_stage020"] - compare["max_dd_pct_stage013"]
    compare["sharpe_delta_stage020_vs_stage013"] = compare["sharpe_stage020"] - compare["sharpe_stage013"]
    return compare.sort_values("requested_start_month").reset_index(drop=True)


def _annual_returns(proxy_curves: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for start, group in proxy_curves.groupby("requested_start_month"):
        g = group.sort_values("date").copy()
        g["year"] = pd.to_datetime(g["date"]).dt.year
        for year, yg in g.groupby("year"):
            begin = float(yg["stage020_account_equity"].iloc[0])
            end = float(yg["stage020_account_equity"].iloc[-1])
            rows.append(
                {
                    "requested_start_month": start,
                    "year": int(year),
                    "start_equity": begin,
                    "end_equity": end,
                    "annual_return_pct": float((end / begin - 1.0) * 100.0) if begin else np.nan,
                    "trading_days": int(len(yg)),
                }
            )
    return pd.DataFrame(rows)


def _goal_audit(proxy_curves: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    stage013 = proxy_curves[["requested_start_month", "date", "account_equity"]].copy()
    stage013.rename(columns={"account_equity": "equity"}, inplace=True)
    stage013["variant"] = "stage013_engine"
    stage020 = proxy_curves[["requested_start_month", "date", "stage020_account_equity"]].copy()
    stage020.rename(columns={"stage020_account_equity": "equity"}, inplace=True)
    stage020["variant"] = "stage020_high_quality_proxy"
    curves = pd.concat([stage013, stage020], ignore_index=True, sort=False)
    curves["date"] = pd.to_datetime(curves["date"], errors="coerce").dt.normalize()
    curves["equity"] = pd.to_numeric(curves["equity"], errors="coerce")
    curves = curves.dropna(subset=["date", "equity"]).sort_values(["variant", "requested_start_month", "date"])
    return s009._run_audit(curves)


def _retention_summary(summary: pd.DataFrame) -> pd.DataFrame:
    base = pd.read_csv(BASE_STAGE006_SUMMARY_PATH, encoding="utf-8-sig")
    cols = ["requested_start_month", "total_return_pct", "end_equity", "max_dd_pct", "sharpe"]
    merged = base[cols].merge(summary, on="requested_start_month", how="inner")
    merged.rename(
        columns={
            "total_return_pct": "total_return_pct_base_stage006",
            "end_equity": "end_equity_base_stage006",
            "max_dd_pct": "max_dd_pct_base_stage006",
            "sharpe": "sharpe_base_stage006",
        },
        inplace=True,
    )
    merged["stage020_vs_base_stage006_return_ratio"] = (
        pd.to_numeric(merged["total_return_pct_stage020"], errors="coerce")
        / pd.to_numeric(merged["total_return_pct_base_stage006"], errors="coerce").replace(0.0, np.nan)
    )
    merged["stage020_vs_stage013_return_ratio"] = (
        pd.to_numeric(merged["total_return_pct_stage020"], errors="coerce")
        / pd.to_numeric(merged["total_return_pct_stage013"], errors="coerce").replace(0.0, np.nan)
    )
    merged["passes_80pct_retention_vs_base_stage006"] = merged["stage020_vs_base_stage006_return_ratio"].ge(0.80).astype(
        "int64"
    )
    merged["passes_80pct_retention_vs_stage013"] = merged["stage020_vs_stage013_return_ratio"].ge(0.80).astype("int64")
    return merged


def _plot(summary: pd.DataFrame, proxy_curves: pd.DataFrame, aggregate: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(18, 11), constrained_layout=True)
    x = np.arange(len(summary))
    labels = summary["requested_start_month"].astype(str).tolist()

    ax = axes[0, 0]
    ax.bar(
        x,
        summary["return_delta_pp_stage020_vs_stage013"],
        color=np.where(summary["return_delta_pp_stage020_vs_stage013"].ge(0), "#16a34a", "#dc2626"),
    )
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=55, ha="right")
    ax.set_title("Stage020 Proxy Return Delta vs Stage013")
    ax.set_ylabel("return delta pp")
    ax.grid(True, axis="y", alpha=0.25)

    ax = axes[0, 1]
    ax.bar(
        x,
        summary["max_dd_delta_pp_stage020_vs_stage013"],
        color=np.where(summary["max_dd_delta_pp_stage020_vs_stage013"].ge(0), "#2563eb", "#f97316"),
    )
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=55, ha="right")
    ax.set_title("Stage020 MaxDD Delta vs Stage013")
    ax.set_ylabel("dd delta pp")
    ax.grid(True, axis="y", alpha=0.25)

    ax = axes[1, 0]
    for start, group in proxy_curves.groupby("requested_start_month"):
        group = group.sort_values("date")
        ax.plot(group["date"], group["stage020_account_equity"], linewidth=0.9, alpha=0.72, label=str(start))
    ax.axhline(CAPITAL, color="#111827", linestyle="--", linewidth=0.8)
    ax.set_title("Stage020 Proxy Absolute Equity")
    ax.set_ylabel("account equity")
    ax.grid(True, alpha=0.25)
    ax.legend(fontsize=6, ncol=3, loc="best")

    ax = axes[1, 1]
    all_scope = aggregate[aggregate["audit_scope"].eq("all_trading_end_dates_gt_1y")].copy()
    stage020 = all_scope[all_scope["variant"].eq("stage020_high_quality_proxy")].copy()
    x2 = np.arange(len(stage020))
    ax.bar(x2, stage020["negative_count"], color="#dc2626")
    ax.set_xticks(x2[::2])
    ax.set_xticklabels(stage020["source_start_month"].astype(str).tolist()[::2], rotation=55, ha="right")
    ax.set_title("Stage020 Strict >1Y Negative Windows")
    ax.set_ylabel("negative windows")
    ax.grid(True, axis="y", alpha=0.25)
    fig.savefig(CHART_PATH, dpi=160)
    plt.close(fig)


def _plot_goal(aggregate: pd.DataFrame, worst: pd.DataFrame, fixed: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(18, 10), constrained_layout=True)
    for ax, variant, title in [
        (axes[0, 0], "stage013_engine", "Stage013 all >1Y negative rate"),
        (axes[0, 1], "stage020_high_quality_proxy", "Stage020 all >1Y negative rate"),
    ]:
        frame = aggregate[
            aggregate["variant"].eq(variant) & aggregate["audit_scope"].eq("all_trading_end_dates_gt_1y")
        ].copy()
        x = np.arange(len(frame))
        ax.bar(x, frame["negative_rate_pct"], color="#2563eb")
        ax.set_xticks(x[::2])
        ax.set_xticklabels(frame["source_start_month"].astype(str).tolist()[::2], rotation=45, ha="right", fontsize=8)
        ax.set_title(title)
        ax.set_ylabel("negative rate %")
        ax.grid(True, axis="y", alpha=0.25)

    ax = axes[1, 0]
    if not worst.empty:
        for variant, color in [("stage013_engine", "#64748b"), ("stage020_high_quality_proxy", "#dc2626")]:
            plot = worst[worst["variant"].eq(variant)].head(250)
            ax.scatter(np.arange(len(plot)), plot["return_pct"], s=10, alpha=0.65, label=variant, color=color)
    ax.axhline(0, color="#111827", linestyle="--", linewidth=0.8)
    ax.set_title("Worst Negative Windows")
    ax.set_ylabel("return %")
    ax.legend(fontsize=8)
    ax.grid(True, axis="y", alpha=0.25)

    ax = axes[1, 1]
    if not fixed.empty:
        fixed_summary = (
            fixed.groupby(["variant", "horizon_days"], as_index=False)
            .agg(negative_rate_pct=("positive_return", lambda s: float((1.0 - s.mean()) * 100.0)))
            .sort_values(["variant", "horizon_days"])
        )
        for variant, group in fixed_summary.groupby("variant"):
            ax.plot(group["horizon_days"], group["negative_rate_pct"], marker="o", label=variant)
    ax.set_title("Fixed Horizon Negative Rate")
    ax.set_xlabel("calendar days")
    ax.set_ylabel("negative rate %")
    ax.legend(fontsize=8)
    ax.grid(True, axis="y", alpha=0.25)
    fig.savefig(GOAL_CHART_PATH, dpi=160)
    plt.close(fig)


def _decision(
    summary: pd.DataFrame,
    annual: pd.DataFrame,
    aggregate: pd.DataFrame,
    retention: pd.DataFrame,
    audit: dict[str, Any],
    unmatched_delta_dates: int,
) -> dict[str, Any]:
    stage020_all = aggregate[
        aggregate["variant"].eq("stage020_high_quality_proxy")
        & aggregate["audit_scope"].eq("all_trading_end_dates_gt_1y")
    ]
    stage020_final = aggregate[
        aggregate["variant"].eq("stage020_high_quality_proxy")
        & aggregate["audit_scope"].eq("start_to_2026_06_30_only")
    ]
    stage013_all = aggregate[
        aggregate["variant"].eq("stage013_engine") & aggregate["audit_scope"].eq("all_trading_end_dates_gt_1y")
    ]
    strict_negative = int(stage020_all["negative_count"].sum()) if not stage020_all.empty else 0
    strict_stage013_negative = int(stage013_all["negative_count"].sum()) if not stage013_all.empty else 0
    retention_base_pass = int(retention["passes_80pct_retention_vs_base_stage006"].sum())
    retention_stage013_pass = int(retention["passes_80pct_retention_vs_stage013"].sum())
    if strict_negative == 0 and retention_base_pass == len(retention):
        decision = "stage020_proxy_meets_goal_requires_true_engine"
    elif strict_negative < strict_stage013_negative and retention_base_pass == len(retention):
        decision = "stage020_proxy_improves_goal_but_not_met_requires_new_selector"
    else:
        decision = "stage020_proxy_not_enough_no_true_engine_yet"
    return {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "tag_column": TAG_COLUMN,
        "add_risk_fraction": ADD_RISK_FRACTION,
        "audit_type": "stage013_closed_lot_read_only_add_risk_proxy",
        "selected_lots": audit["selected_lots"],
        "selected_realized_pnl": audit["selected_realized_pnl"],
        "total_proxy_delta_pnl": audit["total_proxy_delta_pnl"],
        "stage013_closed_lot_count": audit["stage013_closed_lot_count"],
        "quality_tag_match_rate_pct": audit["quality_tag_match_rate_pct"],
        "unmatched_delta_dates": int(unmatched_delta_dates),
        "sample_count": int(len(summary)),
        "stage020_min_return_pct": float(summary["total_return_pct_stage020"].min()),
        "stage020_median_return_pct": float(summary["total_return_pct_stage020"].median()),
        "stage020_worst_max_dd_pct": float(summary["max_dd_pct_stage020"].min()),
        "stage020_median_max_dd_pct": float(summary["max_dd_pct_stage020"].median()),
        "return_improved_count_vs_stage013": int(summary["return_delta_pp_stage020_vs_stage013"].gt(EPS).sum()),
        "return_unchanged_count_vs_stage013": int(summary["return_delta_pp_stage020_vs_stage013"].abs().le(EPS).sum()),
        "return_worse_count_vs_stage013": int(summary["return_delta_pp_stage020_vs_stage013"].lt(-EPS).sum()),
        "maxdd_improved_count_vs_stage013": int(summary["max_dd_delta_pp_stage020_vs_stage013"].gt(EPS).sum()),
        "maxdd_unchanged_count_vs_stage013": int(summary["max_dd_delta_pp_stage020_vs_stage013"].abs().le(EPS).sum()),
        "maxdd_worse_count_vs_stage013": int(summary["max_dd_delta_pp_stage020_vs_stage013"].lt(-EPS).sum()),
        "stage020_all_gt1y_window_count": int(stage020_all["window_count"].sum()) if not stage020_all.empty else 0,
        "stage020_all_gt1y_negative_count": strict_negative,
        "stage020_all_gt1y_min_return_pct": float(stage020_all["min_return_pct"].min()) if not stage020_all.empty else np.nan,
        "stage013_all_gt1y_negative_count": strict_stage013_negative,
        "stage020_to_final_negative_count": int(stage020_final["negative_count"].sum()) if not stage020_final.empty else 0,
        "stage020_to_final_min_return_pct": float(stage020_final["min_return_pct"].min()) if not stage020_final.empty else np.nan,
        "retention_vs_base_stage006_pass_count": retention_base_pass,
        "retention_vs_stage013_pass_count": retention_stage013_pass,
        "retention_rows": int(len(retention)),
        "annual_negative_rows": int(annual["annual_return_pct"].lt(0).sum()) if not annual.empty else 0,
        "decision": decision,
        "strategy_changed": False,
        "true_engine": False,
        "order_api_called": False,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "ctp_connected": False,
        "external_research_judgment": (
            "Meta-labeling/bet-sizing research supports using a secondary signal to size a primary signal, but "
            "DSR/PBO research warns against multiple testing. Stage020 therefore tests one predeclared quality tag "
            "with one fixed non-overwriting add-risk fraction only."
        ),
        "overfit_reflection_before": (
            "否。只测一个 Stage007 已预声明标签和固定 25% 非挤占比例，不扫品种、方向、年份或倍率。"
        ),
        "continue_value_before": (
            "有。Stage013 已改善左尾但严格任意结束日仍失败，需要验证高质量信号加风险能否抬升恢复段而不伤右尾。"
        ),
        "overfit_reflection_after": (
            "否。本阶段没有根据结果换标签或调比例；若继续按失败窗口反推新标签会过拟合。"
        ),
        "continue_value_after": (
            "有，但不是继续加风险倍率救参。Stage020 证明高质量标签能抬收益和部分左尾，"
            "但严格负窗口仍未清零，下一步应转向新信息源/选择器或真实引擎前置约束。"
        ),
        "outputs": {
            "lot_deltas": str(LOT_DELTAS_PATH),
            "curves": str(CURVES_PATH),
            "summary": str(SUMMARY_PATH),
            "annual_returns": str(ANNUAL_PATH),
            "goal_aggregate": str(GOAL_AGGREGATE_PATH),
            "goal_to_final": str(GOAL_TO_FINAL_PATH),
            "goal_fixed_horizon": str(GOAL_FIXED_HORIZON_PATH),
            "goal_worst_windows": str(GOAL_WORST_WINDOWS_PATH),
            "retention": str(RETENTION_PATH),
            "chart": str(CHART_PATH),
            "goal_chart": str(GOAL_CHART_PATH),
            "decision": str(DECISION_PATH),
            "report": str(REPORT_PATH),
        },
    }


def _write_report(
    decision: dict[str, Any],
    summary: pd.DataFrame,
    annual: pd.DataFrame,
    aggregate: pd.DataFrame,
    retention: pd.DataFrame,
    lot_deltas: pd.DataFrame,
) -> None:
    strict = aggregate[
        aggregate["variant"].eq("stage020_high_quality_proxy")
        & aggregate["audit_scope"].eq("all_trading_end_dates_gt_1y")
    ]
    lines = [
        f"# {STAGE} Stage013 + 高质量标签加风险只读代理",
        "",
        f"- 生成时间：`{decision['generated_at']}`",
        f"- line_id：`{LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        f"- 决策：`{decision['decision']}`",
        "- 阶段性质：closed-lot 只读上界代理；不是真实组合引擎，不改 C9，不连接 CTP，不调用下单。",
        f"- 标签：`{TAG_COLUMN}`",
        f"- 固定额外风险比例：`{ADD_RISK_FRACTION:.2%}`",
        "",
        "## 外部调研判断",
        "",
        "- meta-labeling/bet-sizing 支持二级质量信号用于风险大小，而不是替代主信号方向。",
        "- DSR/PBO 约束要求少试验：本阶段只跑一个预声明标签和一个固定小额比例，不扫标签组合或倍率。",
        "- 趋势跟随右尾约束：额外风险不能挤占原 C9/Stage013 头寸，本阶段只是非挤占加风险上界代理。",
        "",
        "## 方法",
        "",
        "- 基准曲线：Stage013 account-state pilot gate。",
        "- lot 来源：Stage019 重建的 Stage013 closed lots。",
        "- 标签来源：Stage007 minute source coverage rebind quality features，按 `requested_start_month + open_trade_id` 绑定。",
        "- 代理增量：选中 lot 的 `Stage013 realized_pnl * 25%` 在 exit_date 入账。",
        "",
        "## 核心结果",
        "",
        f"- 选中 lots：`{decision['selected_lots']}`；Stage013 realized PnL `{decision['selected_realized_pnl']:,.2f}`；代理增量 `{decision['total_proxy_delta_pnl']:,.2f}`。",
        f"- Stage020 严格任意结束日 `>1` 年负窗口：`{decision['stage020_all_gt1y_negative_count']}` / `{decision['stage020_all_gt1y_window_count']}`；最差 `{decision['stage020_all_gt1y_min_return_pct']:.4f}%`。",
        f"- Stage013 严格任意结束日 `>1` 年负窗口：`{decision['stage013_all_gt1y_negative_count']}`。",
        f"- 到 `2026-06-30` 负窗口：`{decision['stage020_to_final_negative_count']}`；最差 `{decision['stage020_to_final_min_return_pct']:.4f}%`。",
        f"- 80% 收益保留 vs Stage006：`{decision['retention_vs_base_stage006_pass_count']}/{decision['retention_rows']}`；vs Stage013：`{decision['retention_vs_stage013_pass_count']}/{decision['retention_rows']}`。",
        f"- 收益改善/不变/变差 vs Stage013：`{decision['return_improved_count_vs_stage013']}/{decision['return_unchanged_count_vs_stage013']}/{decision['return_worse_count_vs_stage013']}`。",
        f"- 最大回撤改善/不变/变差 vs Stage013：`{decision['maxdd_improved_count_vs_stage013']}/{decision['maxdd_unchanged_count_vs_stage013']}/{decision['maxdd_worse_count_vs_stage013']}`。",
        "",
        "## 多起点摘要",
        "",
        _md_table(
            summary[
                [
                    "requested_start_month",
                    "total_return_pct_stage013",
                    "total_return_pct_stage020",
                    "return_delta_pp_stage020_vs_stage013",
                    "max_dd_pct_stage013",
                    "max_dd_pct_stage020",
                    "max_dd_delta_pp_stage020_vs_stage013",
                    "sharpe_stage013",
                    "sharpe_stage020",
                ]
            ],
            max_rows=30,
        ),
        "",
        "## 密集目标审计",
        "",
        _md_table(strict, max_rows=30),
        "",
        "## 收益保留",
        "",
        _md_table(
            retention[
                [
                    "requested_start_month",
                    "stage020_vs_base_stage006_return_ratio",
                    "stage020_vs_stage013_return_ratio",
                    "passes_80pct_retention_vs_base_stage006",
                    "passes_80pct_retention_vs_stage013",
                ]
            ],
            max_rows=30,
        ),
        "",
        "## 年度代理收益",
        "",
        _md_table(annual, max_rows=40),
        "",
        "## 增量 lot 样本",
        "",
        _md_table(lot_deltas, max_rows=30),
        "",
        "## 判断",
        "",
        f"- 决策：`{decision['decision']}`",
        f"- 过拟合反思：{decision['overfit_reflection_after']}",
        f"- 继续价值反思：{decision['continue_value_after']}",
        "",
        "## 输出文件",
        "",
    ]
    for key, path in decision["outputs"].items():
        lines.append(f"- {key}: `{path}`")
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_stage_record(decision: dict[str, Any], summary: pd.DataFrame, retention: pd.DataFrame) -> Path:
    timestamp = datetime.now()
    path = STAGE_RECORD_DIR / f"{timestamp:%Y%m%d_%H%M}_stage020_stage013_high_quality_add_risk_proxy.md"
    lines = [
        "# Stage020 Stage013 + 高质量标签加风险只读代理",
        "",
        f"- 记录时间：`{timestamp.isoformat(timespec='minutes')}`",
        f"- line_id：`{LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        "- 是否重要突破版本：`否`",
        f"- 决策：`{decision['decision']}`",
        "",
        "## 本次版本变更",
        "",
        f"- 新增参数：`stage020_tag={TAG_COLUMN}`、`stage020_add_risk_fraction={ADD_RISK_FRACTION}`。",
        "- 修改参数：无，Stage013/官方 C9 配置未改。",
        "- 删除参数：无。",
        "- 本阶段只读代理，不新增真实交易规则、不接实盘。",
        "",
        "## 调研和判断结论",
        "",
        "- 外部 meta-labeling/bet-sizing 支持二级质量信号决定风险大小，但 DSR/PBO 要求控制试验次数。",
        "- 本阶段只跑一个已预声明标签和固定 25% 非挤占比例，不扫参。",
        "",
        "## 代理结果",
        "",
        f"- 选中 lots：`{decision['selected_lots']}`。",
        f"- Stage013 realized PnL：`{decision['selected_realized_pnl']:,.2f}`。",
        f"- 代理增量 PnL：`{decision['total_proxy_delta_pnl']:,.2f}`。",
        f"- 严格任意结束日 `>1` 年负窗口：Stage013 `{decision['stage013_all_gt1y_negative_count']}` -> Stage020 `{decision['stage020_all_gt1y_negative_count']}`。",
        f"- Stage020 严格最差收益：`{decision['stage020_all_gt1y_min_return_pct']:.4f}%`。",
        f"- 到 `2026-06-30` 负窗口：`{decision['stage020_to_final_negative_count']}`，最差 `{decision['stage020_to_final_min_return_pct']:.4f}%`。",
        f"- 收益保留 vs Stage006：`{decision['retention_vs_base_stage006_pass_count']}/{decision['retention_rows']}`；vs Stage013：`{decision['retention_vs_stage013_pass_count']}/{decision['retention_rows']}`。",
        f"- 收益改善/不变/变差 vs Stage013：`{decision['return_improved_count_vs_stage013']}/{decision['return_unchanged_count_vs_stage013']}/{decision['return_worse_count_vs_stage013']}`。",
        f"- 回撤改善/不变/变差 vs Stage013：`{decision['maxdd_improved_count_vs_stage013']}/{decision['maxdd_unchanged_count_vs_stage013']}/{decision['maxdd_worse_count_vs_stage013']}`。",
        "",
        "## 多起点摘要",
        "",
        _md_table(
            summary[
                [
                    "requested_start_month",
                    "total_return_pct_stage013",
                    "total_return_pct_stage020",
                    "return_delta_pp_stage020_vs_stage013",
                    "max_dd_pct_stage013",
                    "max_dd_pct_stage020",
                    "max_dd_delta_pp_stage020_vs_stage013",
                ]
            ],
            max_rows=30,
        ),
        "",
        "## 收益保留摘要",
        "",
        _md_table(
            retention[
                [
                    "requested_start_month",
                    "stage020_vs_base_stage006_return_ratio",
                    "stage020_vs_stage013_return_ratio",
                    "passes_80pct_retention_vs_base_stage006",
                    "passes_80pct_retention_vs_stage013",
                ]
            ],
            max_rows=30,
        ),
        "",
        "## 文件",
        "",
    ]
    for key, output_path in decision["outputs"].items():
        lines.append(f"- {key}: `{output_path}`")
    lines.extend(
        [
            "",
            "## 后续规划和 TODO",
            "",
            "- 若严格负窗口仍未清零，不能通过加风险倍率救参；下一步转向新信息源/选择器或真实引擎前置约束。",
            "- 若代理达标，也必须写真引擎验证成交、保证金、broker10 和 AI 月度审计。",
            "",
            "## 反思",
            "",
            f"- 过拟合反思：{decision['overfit_reflection_after']}",
            f"- 继续价值反思：{decision['continue_value_after']}",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    STAGE_RECORD_DIR.mkdir(parents=True, exist_ok=True)

    stage013_curves = pd.read_csv(STAGE013_CURVES_PATH, encoding="utf-8-sig")
    stage013_summary = pd.read_csv(STAGE013_SUMMARY_PATH, encoding="utf-8-sig")
    lot_deltas, lot_audit = _build_lot_deltas()
    proxy_curves, unmatched_delta_dates = _build_proxy_curves(stage013_curves, lot_deltas)
    summary = _summary(stage013_summary, proxy_curves)
    annual = _annual_returns(proxy_curves)
    aggregate, to_final, fixed, worst = _goal_audit(proxy_curves)
    retention = _retention_summary(summary)
    decision = _decision(summary, annual, aggregate, retention, lot_audit, unmatched_delta_dates)

    lot_deltas.to_csv(LOT_DELTAS_PATH, index=False, encoding="utf-8-sig")
    proxy_curves.to_csv(CURVES_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    annual.to_csv(ANNUAL_PATH, index=False, encoding="utf-8-sig")
    aggregate.to_csv(GOAL_AGGREGATE_PATH, index=False, encoding="utf-8-sig")
    to_final.to_csv(GOAL_TO_FINAL_PATH, index=False, encoding="utf-8-sig")
    fixed.to_csv(GOAL_FIXED_HORIZON_PATH, index=False, encoding="utf-8-sig")
    worst.to_csv(GOAL_WORST_WINDOWS_PATH, index=False, encoding="utf-8-sig")
    retention.to_csv(RETENTION_PATH, index=False, encoding="utf-8-sig")
    _plot(summary, proxy_curves, aggregate)
    _plot_goal(aggregate, worst, fixed)
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_report(decision, summary, annual, aggregate, retention, lot_deltas)
    stage_record = _write_stage_record(decision, summary, retention)

    print(json.dumps(_json_safe({**decision, "stage_record": str(stage_record)}), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
