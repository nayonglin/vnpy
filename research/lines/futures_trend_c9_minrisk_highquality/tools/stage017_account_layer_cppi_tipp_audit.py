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
STAGE = "Stage017"
MODEL_TAG = "stage017_account_layer_cppi_tipp_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage017_c9_minrisk_account_layer_cppi_tipp_audit"

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
OUTPUT_DIR = LINE_DIR / "outputs" / "stage017_account_layer_cppi_tipp_audit"
STAGE010_DIR = LINE_DIR / "outputs" / "stage010_authoritative_minute_coverage_audit"

CAPITAL = 150_000.0
TRADING_DAYS_PER_YEAR = 252

CURVE_IN = (
    STAGE010_DIR
    / "qmt_roll_stage010_c9_minrisk_authoritative_minute_coverage_audit_official_curve_stage010_authoritative_minute_coverage_audit_v1.csv"
)
SUMMARY_IN = (
    STAGE010_DIR
    / "qmt_roll_stage010_c9_minrisk_authoritative_minute_coverage_audit_summary_stage010_authoritative_minute_coverage_audit_v1.csv"
)

CURVES_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv"
METRICS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_metrics_{MODEL_TAG}.csv"
YEAR_STATS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_year_stats_{MODEL_TAG}.csv"
SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_path_drawdown_chart_{MODEL_TAG}.png"
WEIGHT_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_weight_floor_chart_{MODEL_TAG}.png"
SCATTER_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_return_drawdown_scatter_{MODEL_TAG}.png"
YEAR_HEATMAP_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_year_return_heatmap_{MODEL_TAG}.png"


POLICIES: list[dict[str, Any]] = [
    {
        "variant": "A_official_c9_15w",
        "policy_type": "official",
        "floor_ratio": np.nan,
        "multiplier": np.nan,
        "description": "Official C9/15w path; no account overlay.",
    },
    {
        "variant": "fixed80_cash_reserve_reference",
        "policy_type": "fixed_weight",
        "fixed_weight": 0.80,
        "floor_ratio": np.nan,
        "multiplier": np.nan,
        "description": "Fixed 80% official-risk exposure plus 20% cash reference.",
    },
    {
        "variant": "cppi80_initial_floor_m4",
        "policy_type": "cppi_initial_floor",
        "floor_ratio": 0.80,
        "multiplier": 4.0,
        "description": "CPPI with 80% initial-capital floor, multiplier 4, risky weight capped at 100%.",
    },
    {
        "variant": "tipp80_hwm_floor_m4",
        "policy_type": "tipp_hwm_floor",
        "floor_ratio": 0.80,
        "multiplier": 4.0,
        "description": "TIPP / drawdown-based CPPI with 80% high-water floor, multiplier 4.",
    },
    {
        "variant": "tipp50_hwm_floor_m4_dd50_reference",
        "policy_type": "tipp_hwm_floor",
        "floor_ratio": 0.50,
        "multiplier": 4.0,
        "description": "DD50 survival reference: TIPP high-water floor 50%, multiplier 4. Not a tuned candidate.",
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


def _prepare_official_curve() -> pd.DataFrame:
    data = _read_required_csv(CURVE_IN)
    data["date"] = pd.to_datetime(data["date"], errors="coerce")
    data = data.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    for column in [
        "net_pnl",
        "account_equity",
        "nav",
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


def _simulate_policy(official: pd.DataFrame, policy: dict[str, Any]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    variant = str(policy["variant"])
    if policy["policy_type"] == "official":
        out = official.copy()
        out["variant"] = variant
        out["policy_type"] = "official"
        out["description"] = policy["description"]
        out["policy_floor"] = np.nan
        out["risk_weight"] = 1.0
        out["scaled_net_pnl"] = out["net_pnl"]
        out["overlay_equity"] = out["account_equity"]
        out["overlay_nav"] = out["overlay_equity"] / CAPITAL
        out["overlay_drawdown_pct"] = _drawdown_pct(out["overlay_equity"])
        out["scaled_broker10_margin_exact"] = out["broker10_total_margin_exact"]
        out["scaled_broker10_margin_to_equity_pct"] = out["broker10_margin_to_equity_pct"]
        out["scaled_slippage"] = out["slippage"]
        return out

    wealth = CAPITAL
    hwm = CAPITAL
    for _, row in official.iterrows():
        if policy["policy_type"] == "fixed_weight":
            floor = np.nan
            risk_weight = float(policy["fixed_weight"])
        elif policy["policy_type"] == "cppi_initial_floor":
            floor = float(policy["floor_ratio"]) * CAPITAL
            cushion = max(0.0, wealth - floor)
            risk_weight = min(1.0, max(0.0, float(policy["multiplier"]) * cushion / wealth)) if wealth > 0 else 0.0
        elif policy["policy_type"] == "tipp_hwm_floor":
            floor = float(policy["floor_ratio"]) * hwm
            cushion = max(0.0, wealth - floor)
            risk_weight = min(1.0, max(0.0, float(policy["multiplier"]) * cushion / wealth)) if wealth > 0 else 0.0
        else:
            raise RuntimeError(f"unsupported policy type: {policy['policy_type']}")

        scaled_pnl = risk_weight * _safe_float(row["net_pnl"], 0.0)
        wealth = wealth + scaled_pnl
        hwm = max(hwm, wealth)
        scaled_margin = risk_weight * _safe_float(row["broker10_total_margin_exact"], 0.0)
        rows.append(
            {
                **row.to_dict(),
                "variant": variant,
                "policy_type": policy["policy_type"],
                "description": policy["description"],
                "policy_floor": floor,
                "risk_weight": risk_weight,
                "scaled_net_pnl": scaled_pnl,
                "overlay_equity": wealth,
                "overlay_nav": wealth / CAPITAL,
                "scaled_broker10_margin_exact": scaled_margin,
                "scaled_broker10_margin_to_equity_pct": scaled_margin / wealth * 100.0 if wealth > 0 else np.nan,
                "scaled_slippage": risk_weight * _safe_float(row["slippage"], 0.0),
            }
        )
    out = pd.DataFrame(rows)
    out["overlay_drawdown_pct"] = _drawdown_pct(out["overlay_equity"])
    return out


def _simulate_all(official: pd.DataFrame) -> pd.DataFrame:
    curves = [_simulate_policy(official, policy) for policy in POLICIES]
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
            "min_equity": float(equity.min()),
            "avg_risk_weight": float(pd.to_numeric(group["risk_weight"], errors="coerce").mean()),
            "min_risk_weight": float(pd.to_numeric(group["risk_weight"], errors="coerce").min()),
            "max_risk_weight": float(pd.to_numeric(group["risk_weight"], errors="coerce").max()),
            "days_risk_weight_below_50pct": int((pd.to_numeric(group["risk_weight"], errors="coerce") < 0.5).sum()),
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
        if row["headline_metric_pass"] and row["meaningful_dd5_pass"] == 0:
            row["decision_note"] = "headline proxy passes, but drawdown improvement is too small and proxy is not deployable"
        elif row["headline_metric_pass"]:
            row["decision_note"] = "headline proxy passes, but still lacks true engine and integer-lot validation"
        elif row["return_80_pass"] == 0:
            row["decision_note"] = "fails return retention"
        elif row["dd_better_than_official"] == 0:
            row["decision_note"] = "does not reduce drawdown"
        else:
            row["decision_note"] = "proxy-only; improvement is too small or accounting path is not deployable"
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
        year_return = (end_equity / start_equity - 1.0) * 100.0 if start_equity > 0 else np.nan
        rows.append(
            {
                "variant": variant,
                "year": int(year),
                "start_equity": start_equity,
                "end_equity": end_equity,
                "year_return_pct": year_return,
                "year_pnl": float(pd.to_numeric(group["scaled_net_pnl"], errors="coerce").fillna(0.0).sum()),
                "year_max_dd_pct": float(pd.to_numeric(group["overlay_drawdown_pct"], errors="coerce").min()),
                "avg_risk_weight": float(pd.to_numeric(group["risk_weight"], errors="coerce").mean()),
                "min_risk_weight": float(pd.to_numeric(group["risk_weight"], errors="coerce").min()),
            }
        )
    return pd.DataFrame(rows)


def _plot_path_drawdown(curves: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 1, figsize=(18, 11), sharex=True, constrained_layout=True)
    colors = {
        "A_official_c9_15w": "#2563eb",
        "fixed80_cash_reserve_reference": "#0891b2",
        "cppi80_initial_floor_m4": "#16a34a",
        "tipp80_hwm_floor_m4": "#dc2626",
        "tipp50_hwm_floor_m4_dd50_reference": "#7c3aed",
    }
    for variant, group in curves.groupby("variant", sort=False):
        group = group.sort_values("date")
        axes[0].plot(group["date"], group["overlay_equity"], label=variant, color=colors.get(variant), linewidth=1.1)
        axes[1].plot(group["date"], group["overlay_drawdown_pct"], label=variant, color=colors.get(variant), linewidth=1.0)
    axes[0].set_yscale("log")
    axes[0].set_title("Official C9/15w vs account-layer CPPI/TIPP proxy wealth paths")
    axes[0].grid(True, alpha=0.2)
    axes[0].legend(loc="best", fontsize=8)
    axes[1].axhline(-40, color="#dc2626", linestyle="--", linewidth=0.8, alpha=0.6)
    axes[1].axhline(-50, color="#7f1d1d", linestyle="--", linewidth=0.8, alpha=0.6)
    axes[1].set_title("Drawdown paths")
    axes[1].grid(True, alpha=0.2)
    axes[1].legend(loc="best", fontsize=8)
    fig.savefig(PATH_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_weight_floor(curves: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 1, figsize=(18, 10), sharex=True, constrained_layout=True)
    focus = curves[~curves["variant"].eq("A_official_c9_15w")].copy()
    for variant, group in focus.groupby("variant", sort=False):
        group = group.sort_values("date")
        axes[0].plot(group["date"], group["risk_weight"], label=variant, linewidth=1.0)
        floor_ratio_to_wealth = pd.to_numeric(group["policy_floor"], errors="coerce") / pd.to_numeric(
            group["overlay_equity"], errors="coerce"
        )
        axes[1].plot(group["date"], floor_ratio_to_wealth, label=variant, linewidth=1.0)
    axes[0].set_title("Risk weight used by account-layer proxy")
    axes[0].set_ylim(-0.02, 1.05)
    axes[0].grid(True, alpha=0.2)
    axes[0].legend(loc="best", fontsize=8)
    axes[1].set_title("Protected floor / proxy wealth")
    axes[1].set_ylim(-0.02, 1.05)
    axes[1].grid(True, alpha=0.2)
    axes[1].legend(loc="best", fontsize=8)
    fig.savefig(WEIGHT_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_scatter(metrics: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(12, 8), constrained_layout=True)
    data = metrics.copy()
    colors = np.where(data["headline_metric_pass"].eq(1), "#16a34a", "#dc2626")
    ax.scatter(data["return_retention_pct"], data["max_dd_pct"], s=180, c=colors, alpha=0.75, edgecolor="#334155")
    for _, row in data.iterrows():
        ax.annotate(str(row["variant"]), (row["return_retention_pct"], row["max_dd_pct"]), fontsize=8, xytext=(5, 5), textcoords="offset points")
    ax.axvline(80, color="#2563eb", linestyle="--", linewidth=0.9, label="80% return retention")
    official_dd = float(data.loc[data["variant"].eq("A_official_c9_15w"), "max_dd_pct"].iloc[0])
    ax.axhline(official_dd, color="#64748b", linestyle="--", linewidth=0.9, label="official max DD")
    ax.set_xlabel("Return retention vs official (%)")
    ax.set_ylabel("Max drawdown (%)")
    ax.set_title("Account-layer proxy trade-off: return retention vs drawdown")
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
    ax.set_title("Calendar-year return by account-layer proxy policy")
    fig.colorbar(im, ax=ax, label="Year return (%)")
    fig.savefig(YEAR_HEATMAP_OUT, dpi=170)
    plt.close(fig)


def _summary(metrics: pd.DataFrame) -> dict[str, Any]:
    official = metrics[metrics["variant"].eq("A_official_c9_15w")].head(1).to_dict("records")[0]
    passing = metrics[metrics["headline_metric_pass"].eq(1)].copy()
    tipp80 = metrics[metrics["variant"].eq("tipp80_hwm_floor_m4")].head(1).to_dict("records")
    fixed80 = metrics[metrics["variant"].eq("fixed80_cash_reserve_reference")].head(1).to_dict("records")
    cppi80 = metrics[metrics["variant"].eq("cppi80_initial_floor_m4")].head(1).to_dict("records")
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
        "candidate_ready_count": int(pd.to_numeric(metrics["candidate_ready"], errors="coerce").fillna(0).sum()),
        "fixed80_reference": fixed80[0] if fixed80 else {},
        "cppi80_initial_floor_reference": cppi80[0] if cppi80 else {},
        "tipp80_hwm_reference": tipp80[0] if tipp80 else {},
        "decision": "stage017_account_layer_cppi_tipp_proxy_no_candidate",
    }


def _decision(summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "official_live_alias": OFFICIAL_LIVE_ALIAS,
        "decision": "stage017_account_layer_cppi_tipp_proxy_no_candidate",
        "summary": summary,
        "order_api_called": False,
        "ctp_connected": False,
        "external_research_judgment": (
            "CPPI/TIPP literature supports a universal account-layer insurance form: allocate risky exposure "
            "as a multiplier of cushion above a protected floor. The same literature highlights gap risk and "
            "deleveraging costs. Stage017 therefore uses it only as a read-only proxy."
        ),
        "overfit_reflection_before": (
            "No: fixed account-layer archetypes are specified before seeing results; no product/year/direction filters."
        ),
        "continue_value_before": (
            "Yes: Stage016 stopped entry-structure true-engine routes, so the next low-overfit route is account-level risk splitting."
        ),
        "overfit_reflection_after": (
            "No candidate is selected. Choosing a floor after seeing the scatter would be overfitting."
        ),
        "continue_value_after": (
            "Limited: account-layer CPPI/TIPP shows the return/drawdown trade-off clearly, but proxy results do not meet the objective."
        ),
        "outputs": {
            "curves": str(CURVES_OUT),
            "metrics": str(METRICS_OUT),
            "year_stats": str(YEAR_STATS_OUT),
            "summary": str(SUMMARY_OUT),
            "path_chart": str(PATH_CHART_OUT),
            "weight_chart": str(WEIGHT_CHART_OUT),
            "scatter_chart": str(SCATTER_CHART_OUT),
            "year_heatmap": str(YEAR_HEATMAP_OUT),
            "report": str(REPORT_OUT),
            "decision": str(DECISION_OUT),
        },
    }


def _write_report(summary: dict[str, Any], metrics: pd.DataFrame, year_stats: pd.DataFrame) -> None:
    report = "\n".join(
        [
            "# Stage017 account-layer CPPI/TIPP proxy audit",
            "",
            f"- generated_at: `{datetime.now():%Y-%m-%d %H:%M}`",
            f"- line_id: `{LINE_ID}`",
            f"- official: `{OFFICIAL_LIVE_VERSION}` / `{OFFICIAL_LIVE_ALIAS}`",
            "- type: read-only account-layer proxy; no trading rule, no true engine, no CTP, no order API.",
            "- decision: `stage017_account_layer_cppi_tipp_proxy_no_candidate`",
            "",
            "## External Research Judgment",
            "",
            "- CPPI/TIPP is a universal account-layer insurance shape: exposure is a multiplier of cushion above a protected floor.",
            "- The same framework carries gap risk and de-leveraging cost; when applied to trend following it can cut the exact right tail we need.",
            "- This stage therefore audits fixed archetypes only and does not choose a floor after the fact.",
            "",
            "## Summary",
            "",
            _md_table(pd.DataFrame([summary])),
            "",
            "## Metrics",
            "",
            _md_table(metrics, max_rows=20),
            "",
            "## Year Stats",
            "",
            _md_table(year_stats.head(60), max_rows=60),
            "",
            "## Output Files",
            "",
            f"- curves: `{CURVES_OUT}`",
            f"- metrics: `{METRICS_OUT}`",
            f"- year_stats: `{YEAR_STATS_OUT}`",
            f"- path chart: `{PATH_CHART_OUT}`",
            f"- weight chart: `{WEIGHT_CHART_OUT}`",
            f"- scatter chart: `{SCATTER_CHART_OUT}`",
            f"- year heatmap: `{YEAR_HEATMAP_OUT}`",
            "",
            "## Judgment",
            "",
            "- `fixed80` preserves exactly 80% of official PnL in this linear proxy, but drawdown barely improves.",
            "- `cppi80_initial_floor_m4` preserves nearly all return, but drawdown is slightly worse than official.",
            "- `tipp80_hwm_floor_m4` improves drawdown materially, but destroys return retention.",
            "- `tipp50_hwm_floor_m4_dd50_reference` keeps high return retention but improves drawdown only slightly.",
            "- Conclusion: account-layer CPPI/TIPP proxy exposes a hard trade-off and does not produce a candidate.",
            "",
            "## Reflections",
            "",
            "- overfit_reflection_before: `No: fixed universal account-layer archetypes, no product/year/direction filters.`",
            "- overfit_reflection_after: `No candidate selected; tuning floors after this chart would overfit.`",
            "- continue_value_before: `Yes: needed after entry-structure route stopped.`",
            "- continue_value_after: `Limited: useful as a boundary, but not enough to meet the objective.`",
        ]
    )
    REPORT_OUT.write_text(report, encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print("[stage017] loading official curve", flush=True)
    official_curve = _prepare_official_curve()
    official_summary = _read_required_csv(SUMMARY_IN)
    official_metrics = {
        "total_return_pct": float(pd.to_numeric(official_summary["total_return_pct"], errors="coerce").iloc[0]),
        "max_dd_pct": float(pd.to_numeric(official_summary["max_dd_pct"], errors="coerce").iloc[0]),
        "max_broker10_margin_to_equity_pct": float(
            pd.to_numeric(official_summary["max_broker10_margin_to_equity_pct"], errors="coerce").iloc[0]
        ),
    }

    print("[stage017] simulating fixed account-layer proxy policies", flush=True)
    curves = _simulate_all(official_curve)
    metrics = _metrics(curves, official_metrics)
    year_stats = _year_stats(curves)
    summary = _summary(metrics)
    decision = _decision(summary)

    print("[stage017] plotting curves", flush=True)
    _plot_path_drawdown(curves)
    _plot_weight_floor(curves)
    _plot_scatter(metrics)
    _plot_year_heatmap(year_stats)

    curves.to_csv(CURVES_OUT, index=False, encoding="utf-8-sig")
    metrics.to_csv(METRICS_OUT, index=False, encoding="utf-8-sig")
    year_stats.to_csv(YEAR_STATS_OUT, index=False, encoding="utf-8-sig")
    pd.DataFrame([summary]).to_csv(SUMMARY_OUT, index=False, encoding="utf-8-sig")
    DECISION_OUT.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(summary, metrics, year_stats)

    print(json.dumps(_json_safe(summary), ensure_ascii=False, indent=2), flush=True)
    print(f"[stage017] wrote {OUTPUT_DIR}", flush=True)


if __name__ == "__main__":
    main()
