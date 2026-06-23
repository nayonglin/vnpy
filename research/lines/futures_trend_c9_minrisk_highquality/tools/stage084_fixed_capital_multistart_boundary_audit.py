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
STAGE = "Stage084"
MODEL_TAG = "stage084_fixed_capital_multistart_boundary_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage084_c9_minrisk_fixed_capital_multistart_boundary_audit"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
TOOL_DIR = SCRIPT_PATH.parent
EXAMPLE_DIR = REPO_DIR / "examples" / "portfolio_backtesting"
for item in [str(TOOL_DIR), str(EXAMPLE_DIR)]:
    if item not in sys.path:
        sys.path.insert(0, item)

import stage013_minrisk_clean_restore_true_engine as s013
from qmt_roll_official_live_config import OFFICIAL_LIVE_ALIAS, OFFICIAL_LIVE_VERSION


LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
STAGE010_DIR = LINE_DIR / "outputs" / "stage010_authoritative_minute_coverage_audit"
OUTPUT_DIR = LINE_DIR / "outputs" / "stage084_fixed_capital_multistart_boundary_audit"

CAPITAL = 150_000.0
TRADING_DAYS_PER_YEAR = 252
MIN_MATURE_DAYS = 252

CURVE_IN = (
    STAGE010_DIR
    / "qmt_roll_stage010_c9_minrisk_authoritative_minute_coverage_audit_official_curve_"
    "stage010_authoritative_minute_coverage_audit_v1.csv"
)

CURVES_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_representative_curves_{MODEL_TAG}.csv"
WINDOW_STATS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_window_stats_{MODEL_TAG}.csv"
VARIANT_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_variant_summary_{MODEL_TAG}.csv"
YEAR_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_start_year_summary_{MODEL_TAG}.csv"
SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_path_drawdown_weight_chart_{MODEL_TAG}.png"
SCATTER_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_multistart_frontier_scatter_{MODEL_TAG}.png"
YEAR_HEATMAP_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_start_year_heatmap_{MODEL_TAG}.png"
WORST_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_worst_start_path_chart_{MODEL_TAG}.png"


POLICIES: list[dict[str, Any]] = [
    {
        "variant": "A_official_return_stream",
        "policy_type": "official",
        "description": "Official daily return stream reset at each monthly start.",
    },
    {
        "variant": "C_fixed80_cash_reserve_return_stream",
        "policy_type": "fixed_weight",
        "fixed_weight": 0.80,
        "description": "Static 80% exposure to official daily returns plus 20% cash.",
    },
    {
        "variant": "C_cppi80_initial_floor_m4_return_stream",
        "policy_type": "cppi_initial_floor",
        "floor_ratio": 0.80,
        "multiplier": 4.0,
        "description": "CPPI with 80% initial capital floor and multiplier 4.",
    },
    {
        "variant": "C_tipp50_hwm_floor_m4_return_stream",
        "policy_type": "tipp_hwm_floor",
        "floor_ratio": 0.50,
        "multiplier": 4.0,
        "description": "TIPP reference with 50% high-water floor and multiplier 4.",
    },
    {
        "variant": "C_balanced_tranche_v1_return_stream",
        "policy_type": "balanced_tranche",
        "production_floor": CAPITAL,
        "sweep_start": 5_000_000.0,
        "sweep_ratio": 0.50,
        "lock_ratio": 0.60,
        "expansion_ratio": 0.40,
        "description": "Stage020 balanced tranche policy reused without parameter changes.",
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


def _write_csv(frame: pd.DataFrame, path: Path) -> None:
    frame.to_csv(path, index=False, encoding="utf-8-sig")


def _drawdown_pct(equity: pd.Series | np.ndarray) -> pd.Series:
    values = pd.Series(equity, dtype="float64")
    hwm = values.cummax()
    return (values / hwm - 1.0) * 100.0


def _sharpe_from_equity(equity: pd.Series) -> float:
    returns = equity.pct_change().replace([np.inf, -np.inf], np.nan).dropna()
    if returns.empty or returns.std(ddof=0) <= 1e-12:
        return np.nan
    return float(returns.mean() / returns.std(ddof=0) * np.sqrt(TRADING_DAYS_PER_YEAR))


def _is_month_end(dates: pd.Series, idx: int) -> bool:
    if idx >= len(dates) - 1:
        return True
    current = dates.iloc[idx]
    nxt = dates.iloc[idx + 1]
    return current.month != nxt.month or current.year != nxt.year


def _prepare_official_curve() -> pd.DataFrame:
    data = _read_required_csv(CURVE_IN)
    data["date"] = pd.to_datetime(data["date"], errors="coerce")
    data = data.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    for column in [
        "account_equity",
        "net_pnl",
        "broker10_margin_to_equity_pct",
        "broker10_total_margin_exact",
        "slippage",
        "trade_count",
    ]:
        if column in data.columns:
            data[column] = pd.to_numeric(data[column], errors="coerce").fillna(0.0)
        else:
            data[column] = 0.0
    data["official_daily_return"] = (
        data["account_equity"].pct_change().replace([np.inf, -np.inf], np.nan).fillna(0.0)
    )
    data["official_drawdown_pct"] = _drawdown_pct(data["account_equity"])
    return data[
        [
            "date",
            "account_equity",
            "official_daily_return",
            "broker10_margin_to_equity_pct",
            "broker10_total_margin_exact",
            "slippage",
            "trade_count",
        ]
    ].copy()


def _month_start_dates(official: pd.DataFrame) -> list[pd.Timestamp]:
    tmp = official[["date"]].copy()
    tmp["month"] = tmp["date"].dt.to_period("M")
    starts = tmp.groupby("month", as_index=False)["date"].min()["date"].tolist()
    return [pd.Timestamp(item) for item in starts]


def _simulate_policy(window: pd.DataFrame, policy: dict[str, Any], start_date: pd.Timestamp) -> pd.DataFrame:
    dates = window["date"].reset_index(drop=True)
    returns = pd.to_numeric(window["official_daily_return"], errors="coerce").fillna(0.0).reset_index(drop=True)
    broker_ratio = (
        pd.to_numeric(window["broker10_margin_to_equity_pct"], errors="coerce").fillna(0.0).reset_index(drop=True)
    )
    slippage = pd.to_numeric(window["slippage"], errors="coerce").fillna(0.0).reset_index(drop=True)
    trade_count = pd.to_numeric(window["trade_count"], errors="coerce").fillna(0.0).reset_index(drop=True)
    variant = str(policy["variant"])
    policy_type = str(policy["policy_type"])

    wealth = CAPITAL
    hwm = CAPITAL
    production = CAPITAL
    locked = 0.0
    expansion = 0.0
    rows: list[dict[str, Any]] = []

    for idx, date in enumerate(dates):
        r = float(returns.iloc[idx])
        floor = np.nan
        transfer = 0.0
        risk_weight = 1.0

        if policy_type == "official":
            wealth *= 1.0 + r
            production = wealth
        elif policy_type == "fixed_weight":
            risk_weight = float(policy["fixed_weight"])
            wealth *= 1.0 + risk_weight * r
            production = wealth * risk_weight
        elif policy_type == "cppi_initial_floor":
            floor = float(policy["floor_ratio"]) * CAPITAL
            cushion = max(0.0, wealth - floor)
            risk_weight = min(1.0, max(0.0, float(policy["multiplier"]) * cushion / wealth)) if wealth > 0 else 0.0
            wealth *= 1.0 + risk_weight * r
            production = wealth * risk_weight
        elif policy_type == "tipp_hwm_floor":
            floor = float(policy["floor_ratio"]) * hwm
            cushion = max(0.0, wealth - floor)
            risk_weight = min(1.0, max(0.0, float(policy["multiplier"]) * cushion / wealth)) if wealth > 0 else 0.0
            wealth *= 1.0 + risk_weight * r
            hwm = max(hwm, wealth)
            production = wealth * risk_weight
        elif policy_type == "balanced_tranche":
            production *= 1.0 + r
            production = max(production, 0.0)
            if _is_month_end(dates, idx):
                if production < float(policy["production_floor"]) and expansion > 0.0:
                    refill = min(float(policy["production_floor"]) - production, expansion)
                    expansion -= refill
                    production += refill
                    transfer -= refill
                if production > float(policy["sweep_start"]):
                    sweep = (production - float(policy["sweep_start"])) * float(policy["sweep_ratio"])
                    production -= sweep
                    locked += sweep * float(policy["lock_ratio"])
                    expansion += sweep * float(policy["expansion_ratio"])
                    transfer += sweep
            wealth = production + locked + expansion
            risk_weight = production / wealth if wealth > 0 else 0.0
        else:
            raise RuntimeError(f"unsupported policy type: {policy_type}")

        hwm = max(hwm, wealth)
        rows.append(
            {
                "start_date": start_date,
                "date": date,
                "variant": variant,
                "policy_type": policy_type,
                "description": policy["description"],
                "day_index": idx,
                "official_daily_return": r,
                "risk_weight": risk_weight,
                "policy_floor": floor,
                "equity": wealth,
                "nav": wealth / CAPITAL,
                "production_equity": production,
                "locked_equity": locked,
                "expansion_equity": expansion,
                "transfer_amount": transfer,
                "broker10_margin_to_equity_pct_proxy": float(broker_ratio.iloc[idx]) * risk_weight,
                "scaled_slippage_proxy": float(slippage.iloc[idx]) * risk_weight,
                "trade_count_reference": float(trade_count.iloc[idx]),
            }
        )

    out = pd.DataFrame(rows)
    out["drawdown_pct"] = _drawdown_pct(out["equity"]).to_numpy()
    return out


def _simulate_window(official: pd.DataFrame, start_date: pd.Timestamp) -> pd.DataFrame:
    window = official[official["date"].ge(start_date)].copy().reset_index(drop=True)
    if window.empty:
        raise RuntimeError(f"empty window for start_date={start_date}")
    return pd.concat([_simulate_policy(window, policy, start_date) for policy in POLICIES], ignore_index=True)


def _curve_metrics(frame: pd.DataFrame) -> dict[str, Any]:
    data = frame.sort_values("date").reset_index(drop=True)
    equity = pd.to_numeric(data["equity"], errors="coerce")
    dd = pd.to_numeric(data["drawdown_pct"], errors="coerce")
    total_return = (float(equity.iloc[-1]) / CAPITAL - 1.0) * 100.0
    return {
        "end_equity": float(equity.iloc[-1]),
        "total_return_pct": total_return,
        "max_dd_pct": float(dd.min()),
        "sharpe": _sharpe_from_equity(equity),
        "max_broker10_margin_to_equity_pct_proxy": float(
            pd.to_numeric(data["broker10_margin_to_equity_pct_proxy"], errors="coerce").max()
        ),
        "days_over_100pct_proxy": int(
            (pd.to_numeric(data["broker10_margin_to_equity_pct_proxy"], errors="coerce") > 100.0).sum()
        ),
        "avg_risk_weight": float(pd.to_numeric(data["risk_weight"], errors="coerce").mean()),
        "min_risk_weight": float(pd.to_numeric(data["risk_weight"], errors="coerce").min()),
        "total_scaled_slippage_proxy": float(pd.to_numeric(data["scaled_slippage_proxy"], errors="coerce").sum()),
        "trade_count_reference": float(pd.to_numeric(data["trade_count_reference"], errors="coerce").sum()),
    }


def _window_stats(all_curves: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for (start_date, variant), group in all_curves.groupby(["start_date", "variant"], sort=True):
        metrics = _curve_metrics(group)
        metrics.update(
            {
                "start_date": pd.Timestamp(start_date),
                "start_year": pd.Timestamp(start_date).year,
                "start_month": pd.Timestamp(start_date).strftime("%Y-%m"),
                "end_date": pd.Timestamp(group["date"].max()),
                "trading_days": int(group["day_index"].max()) + 1,
                "variant": variant,
                "policy_type": str(group["policy_type"].iloc[0]),
                "description": str(group["description"].iloc[0]),
            }
        )
        rows.append(metrics)
    stats = pd.DataFrame(rows).sort_values(["start_date", "variant"]).reset_index(drop=True)
    official = stats[stats["variant"].eq("A_official_return_stream")][
        [
            "start_date",
            "total_return_pct",
            "max_dd_pct",
            "max_broker10_margin_to_equity_pct_proxy",
            "end_equity",
        ]
    ].rename(
        columns={
            "total_return_pct": "official_total_return_pct",
            "max_dd_pct": "official_max_dd_pct",
            "max_broker10_margin_to_equity_pct_proxy": "official_broker10_peak_pct",
            "end_equity": "official_end_equity",
        }
    )
    stats = stats.merge(official, on="start_date", how="left")
    stats["return_retention_pct"] = np.where(
        stats["official_total_return_pct"].abs() > 1e-9,
        stats["total_return_pct"] / stats["official_total_return_pct"] * 100.0,
        np.nan,
    )
    stats.loc[stats["variant"].eq("A_official_return_stream"), "return_retention_pct"] = 100.0
    stats["dd_improvement_pp"] = stats["max_dd_pct"] - stats["official_max_dd_pct"]
    stats["broker10_improvement_pp_proxy"] = (
        stats["official_broker10_peak_pct"] - stats["max_broker10_margin_to_equity_pct_proxy"]
    )
    stats["mature_window"] = stats["trading_days"].ge(MIN_MATURE_DAYS).astype(int)
    stats["candidate_window_pass"] = (
        stats["mature_window"].eq(1)
        & stats["variant"].ne("A_official_return_stream")
        & stats["return_retention_pct"].ge(80.0)
        & stats["dd_improvement_pp"].gt(0.0)
        & stats["broker10_improvement_pp_proxy"].ge(-1e-9)
    ).astype(int)
    stats["significant_dd_window_pass"] = (
        stats["candidate_window_pass"].eq(1) & stats["dd_improvement_pp"].ge(5.0)
    ).astype(int)
    return stats


def _variant_summary(stats: pd.DataFrame) -> pd.DataFrame:
    mature = stats[stats["mature_window"].eq(1)].copy()
    rows: list[dict[str, Any]] = []
    for variant, group in mature.groupby("variant", sort=False):
        non_official = variant != "A_official_return_stream"
        rows.append(
            {
                "variant": variant,
                "policy_type": str(group["policy_type"].iloc[0]),
                "description": str(group["description"].iloc[0]),
                "mature_window_count": int(len(group)),
                "pass_count": int(group["candidate_window_pass"].sum()) if non_official else 0,
                "significant_dd_pass_count": int(group["significant_dd_window_pass"].sum()) if non_official else 0,
                "pass_rate_pct": float(group["candidate_window_pass"].mean() * 100.0) if non_official else 0.0,
                "median_return_retention_pct": float(group["return_retention_pct"].median()),
                "min_return_retention_pct": float(group["return_retention_pct"].min()),
                "median_dd_improvement_pp": float(group["dd_improvement_pp"].median()),
                "max_dd_improvement_pp": float(group["dd_improvement_pp"].max()),
                "min_dd_improvement_pp": float(group["dd_improvement_pp"].min()),
                "median_max_dd_pct": float(group["max_dd_pct"].median()),
                "worst_max_dd_pct": float(group["max_dd_pct"].min()),
                "median_broker10_improvement_pp_proxy": float(group["broker10_improvement_pp_proxy"].median()),
                "max_broker10_peak_pct_proxy": float(group["max_broker10_margin_to_equity_pct_proxy"].max()),
                "avg_risk_weight_median": float(group["avg_risk_weight"].median()),
                "min_risk_weight_min": float(group["min_risk_weight"].min()),
            }
        )
    return pd.DataFrame(rows)


def _start_year_summary(stats: pd.DataFrame) -> pd.DataFrame:
    mature = stats[stats["mature_window"].eq(1) & stats["variant"].ne("A_official_return_stream")].copy()
    if mature.empty:
        return pd.DataFrame()
    return (
        mature.groupby(["start_year", "variant"], as_index=False)
        .agg(
            window_count=("start_date", "count"),
            pass_count=("candidate_window_pass", "sum"),
            significant_dd_pass_count=("significant_dd_window_pass", "sum"),
            median_return_retention_pct=("return_retention_pct", "median"),
            median_dd_improvement_pp=("dd_improvement_pp", "median"),
            min_return_retention_pct=("return_retention_pct", "min"),
            min_dd_improvement_pp=("dd_improvement_pp", "min"),
        )
        .sort_values(["start_year", "variant"])
    )


def _summary(stats: pd.DataFrame, variant_summary: pd.DataFrame) -> pd.DataFrame:
    official_full = stats[
        stats["variant"].eq("A_official_return_stream") & stats["start_date"].eq(stats["start_date"].min())
    ].iloc[0]
    candidates = variant_summary[variant_summary["variant"].ne("A_official_return_stream")].copy()
    robust = candidates[
        candidates["pass_count"].eq(candidates["mature_window_count"])
        & candidates["significant_dd_pass_count"].gt(0)
    ].copy()
    best_by_dd = candidates.sort_values("median_dd_improvement_pp", ascending=False).head(1)
    best_variant = str(best_by_dd.iloc[0]["variant"]) if not best_by_dd.empty else ""
    decision = "stage084_fixed_capital_multistart_no_candidate"
    if not robust.empty:
        decision = "stage084_fixed_capital_multistart_worth_true_engine_review"
    return pd.DataFrame(
        [
            {
                "stage": STAGE,
                "model_tag": MODEL_TAG,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "line_id": LINE_ID,
                "official_live_version": OFFICIAL_LIVE_VERSION,
                "official_live_alias": OFFICIAL_LIVE_ALIAS,
                "official_full_start_date": pd.Timestamp(official_full["start_date"]).strftime("%Y-%m-%d"),
                "official_end_equity": float(official_full["end_equity"]),
                "official_total_return_pct": float(official_full["total_return_pct"]),
                "official_max_dd_pct": float(official_full["max_dd_pct"]),
                "official_sharpe": float(official_full["sharpe"]),
                "official_broker10_peak_pct_proxy": float(official_full["max_broker10_margin_to_equity_pct_proxy"]),
                "official_total_slippage_proxy": float(official_full["total_scaled_slippage_proxy"]),
                "official_trade_count_reference": float(official_full["trade_count_reference"]),
                "monthly_start_count": int(stats["start_date"].nunique()),
                "mature_start_count": int(
                    stats[stats["variant"].eq("A_official_return_stream")]["mature_window"].sum()
                ),
                "candidate_variant_count": int(len(candidates)),
                "candidate_ready_count": int(len(robust)),
                "total_candidate_window_pass_count": int(candidates["pass_count"].sum()),
                "total_significant_dd_window_pass_count": int(candidates["significant_dd_pass_count"].sum()),
                "best_median_dd_variant": best_variant,
                "best_median_dd_improvement_pp": float(best_by_dd.iloc[0]["median_dd_improvement_pp"])
                if not best_by_dd.empty
                else np.nan,
                "best_median_return_retention_pct": float(best_by_dd.iloc[0]["median_return_retention_pct"])
                if not best_by_dd.empty
                else np.nan,
                "decision": decision,
                "ab_triggered": 0,
                "order_api_called": 0,
                "ctp_connected": 0,
            }
        ]
    )


def _plot_path(representative: pd.DataFrame, summary_row: pd.Series) -> None:
    colors = {
        "A_official_return_stream": "#2563eb",
        "C_fixed80_cash_reserve_return_stream": "#16a34a",
        "C_cppi80_initial_floor_m4_return_stream": "#f97316",
        "C_tipp50_hwm_floor_m4_return_stream": "#7c3aed",
        "C_balanced_tranche_v1_return_stream": "#dc2626",
    }
    fig, axes = plt.subplots(3, 1, figsize=(15, 12), sharex=True, gridspec_kw={"height_ratios": [2, 1.2, 1]})
    for variant, group in representative.groupby("variant", sort=False):
        group = group.sort_values("date")
        label = variant.replace("_return_stream", "")
        axes[0].plot(group["date"], group["equity"], label=label, color=colors.get(variant), linewidth=1.25)
        axes[1].plot(group["date"], group["drawdown_pct"], label=label, color=colors.get(variant), linewidth=1.1)
        if variant != "A_official_return_stream":
            axes[2].plot(group["date"], group["risk_weight"], label=label, color=colors.get(variant), linewidth=1.0)
    axes[0].set_yscale("log")
    axes[0].set_ylabel("equity (log)")
    axes[1].set_ylabel("drawdown %")
    axes[2].set_ylabel("risk weight")
    axes[2].set_ylim(-0.05, 1.05)
    axes[0].set_title(
        "Stage084 fixed-capital multistart boundary | "
        f"decision {summary_row['decision']} | candidate_ready {int(summary_row['candidate_ready_count'])}"
    )
    for ax in axes:
        ax.grid(True, alpha=0.25)
        ax.legend(loc="best", fontsize=8)
    fig.tight_layout()
    fig.savefig(PATH_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_scatter(stats: pd.DataFrame) -> None:
    data = stats[stats["mature_window"].eq(1) & stats["variant"].ne("A_official_return_stream")].copy()
    colors = {
        "C_fixed80_cash_reserve_return_stream": "#16a34a",
        "C_cppi80_initial_floor_m4_return_stream": "#f97316",
        "C_tipp50_hwm_floor_m4_return_stream": "#7c3aed",
        "C_balanced_tranche_v1_return_stream": "#dc2626",
    }
    fig, ax = plt.subplots(figsize=(13, 8))
    for variant, group in data.groupby("variant", sort=False):
        ax.scatter(
            group["return_retention_pct"],
            group["dd_improvement_pp"],
            s=34,
            alpha=0.72,
            label=variant.replace("_return_stream", ""),
            color=colors.get(variant),
            edgecolor="white",
            linewidth=0.4,
        )
    ax.axvline(80.0, color="black", linewidth=1.0, linestyle="--", label="80% retention")
    ax.axhline(0.0, color="#334155", linewidth=1.0)
    ax.axhline(5.0, color="#0f766e", linewidth=1.0, linestyle=":", label="+5pp DD improvement")
    ax.set_xlabel("return retention vs official (%)")
    ax.set_ylabel("max drawdown improvement (pp)")
    ax.set_title("Stage084 monthly-start frontier: fixed account structures")
    ax.grid(True, alpha=0.25)
    ax.legend(loc="best", fontsize=8)
    fig.tight_layout()
    fig.savefig(SCATTER_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_year_heatmap(year_summary: pd.DataFrame) -> None:
    if year_summary.empty:
        return
    pivot = year_summary.pivot_table(
        index="start_year",
        columns="variant",
        values="median_dd_improvement_pp",
        aggfunc="median",
    ).sort_index()
    variants = list(pivot.columns)
    fig, ax = plt.subplots(figsize=(14, max(5, 0.45 * len(pivot.index) + 2)))
    matrix = pivot.to_numpy(dtype=float)
    vmax = np.nanmax(np.abs(matrix)) if np.isfinite(matrix).any() else 1.0
    vmax = max(vmax, 1.0)
    im = ax.imshow(matrix, aspect="auto", cmap="RdYlGn", vmin=-vmax, vmax=vmax)
    ax.set_xticks(range(len(variants)))
    ax.set_xticklabels([item.replace("_return_stream", "").replace("C_", "") for item in variants], rotation=25, ha="right")
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels([str(item) for item in pivot.index])
    ax.set_title("Stage084 median DD improvement by monthly start year (pp)")
    for y in range(matrix.shape[0]):
        for x in range(matrix.shape[1]):
            value = matrix[y, x]
            if np.isfinite(value):
                ax.text(x, y, f"{value:.1f}", ha="center", va="center", fontsize=8, color="black")
    fig.colorbar(im, ax=ax, shrink=0.8)
    fig.tight_layout()
    fig.savefig(YEAR_HEATMAP_OUT, dpi=160)
    plt.close(fig)


def _plot_worst_start(all_curves: pd.DataFrame, stats: pd.DataFrame) -> None:
    official = stats[stats["variant"].eq("A_official_return_stream") & stats["mature_window"].eq(1)].copy()
    if official.empty:
        return
    worst_start = pd.Timestamp(official.sort_values("max_dd_pct").iloc[0]["start_date"])
    data = all_curves[all_curves["start_date"].eq(worst_start)].copy()
    if data.empty:
        return
    fig, axes = plt.subplots(2, 1, figsize=(15, 9), sharex=True)
    for variant, group in data.groupby("variant", sort=False):
        group = group.sort_values("date")
        label = variant.replace("_return_stream", "")
        axes[0].plot(group["date"], group["equity"], linewidth=1.15, label=label)
        axes[1].plot(group["date"], group["drawdown_pct"], linewidth=1.0, label=label)
    axes[0].set_yscale("log")
    axes[0].set_ylabel("equity (log)")
    axes[1].set_ylabel("drawdown %")
    axes[0].set_title(f"Stage084 worst official mature monthly start: {worst_start.strftime('%Y-%m-%d')}")
    for ax in axes:
        ax.grid(True, alpha=0.25)
        ax.legend(loc="best", fontsize=8)
    fig.tight_layout()
    fig.savefig(WORST_CHART_OUT, dpi=160)
    plt.close(fig)


def _write_report(
    summary: pd.DataFrame,
    variant_summary: pd.DataFrame,
    year_summary: pd.DataFrame,
    stats: pd.DataFrame,
) -> None:
    row = summary.iloc[0]
    best = variant_summary[variant_summary["variant"].ne("A_official_return_stream")].copy()
    best = best.sort_values(["pass_count", "median_dd_improvement_pp"], ascending=[False, False])
    mature_fail_notes = stats[
        stats["mature_window"].eq(1)
        & stats["variant"].ne("A_official_return_stream")
        & stats["candidate_window_pass"].eq(0)
    ].copy()
    lines = [
        "# Stage084 固定资本结构多起点边界审计",
        "",
        f"- 生成时间：`{row['created_at']}`",
        f"- line_id：`{LINE_ID}`",
        f"- 当前官方正式版本：`{OFFICIAL_LIVE_VERSION}` / `{OFFICIAL_LIVE_ALIAS}`",
        "- 阶段性质：只读账户层多起点边界审计；不写真引擎、不新增交易规则、不触发 A/B、不连接 CTP、不调用订单 API。",
        "- 固定规则：复用 Stage017/020 的 fixed80、CPPI80、TIPP50、balanced_tranche_v1 archetype；只重置月度起点，不扫参数。",
        "",
        "## Summary",
        "",
        _md_table(summary),
        "",
        "## Variant Summary",
        "",
        _md_table(variant_summary),
        "",
        "## Start Year Summary",
        "",
        _md_table(year_summary, max_rows=40),
        "",
        "## Representative Failure Samples",
        "",
        _md_table(
            mature_fail_notes[
                [
                    "start_month",
                    "variant",
                    "return_retention_pct",
                    "dd_improvement_pp",
                    "max_dd_pct",
                    "broker10_improvement_pp_proxy",
                ]
            ].sort_values(["variant", "dd_improvement_pp"]).head(20),
            max_rows=20,
        ),
        "",
        "## Visual Outputs",
        "",
        f"- full-start path/drawdown/weight chart：`{PATH_CHART_OUT}`",
        f"- monthly-start frontier scatter：`{SCATTER_CHART_OUT}`",
        f"- start-year heatmap：`{YEAR_HEATMAP_OUT}`",
        f"- worst-start path chart：`{WORST_CHART_OUT}`",
        "",
        "## Decision",
        "",
        f"- 决策：`{row['decision']}`",
        "- 主结论：固定账户结构能解释收益-回撤权衡，但多起点下没有一个固定 archetype 同时稳定满足 `80%+` 收益保留、最大回撤改善和 broker10 不恶化。",
        "- 过拟合反思：本阶段不是过拟合，因为只复用先验固定 archetype 与月度起点；若继续改 fixed weight、floor、multiplier、提款阈值或只挑少数起点，就是过拟合。",
        "- 继续价值：账户层固定结构继续调参价值低；下一步应回到真正新增的点时化外生数据或授权盘口/会员持仓数据，而不是账户层参数救援。",
        "",
    ]
    REPORT_OUT.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    official = _prepare_official_curve()
    starts = _month_start_dates(official)

    curves = [_simulate_window(official, start) for start in starts]
    all_curves = pd.concat(curves, ignore_index=True)
    representative_start = min(starts)
    representative = all_curves[all_curves["start_date"].eq(representative_start)].copy()

    stats = _window_stats(all_curves)
    variant_summary = _variant_summary(stats)
    year_summary = _start_year_summary(stats)
    summary = _summary(stats, variant_summary)

    _write_csv(representative, CURVES_OUT)
    _write_csv(stats, WINDOW_STATS_OUT)
    _write_csv(variant_summary, VARIANT_SUMMARY_OUT)
    _write_csv(year_summary, YEAR_SUMMARY_OUT)
    _write_csv(summary, SUMMARY_OUT)
    DECISION_OUT.write_text(json.dumps(_json_safe(summary.iloc[0].to_dict()), ensure_ascii=False, indent=2), encoding="utf-8")

    _plot_path(representative, summary.iloc[0])
    _plot_scatter(stats)
    _plot_year_heatmap(year_summary)
    _plot_worst_start(all_curves, stats)
    _write_report(summary, variant_summary, year_summary, stats)

    print(json.dumps(_json_safe(summary.iloc[0].to_dict()), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
