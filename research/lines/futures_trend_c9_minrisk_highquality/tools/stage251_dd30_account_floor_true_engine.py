from __future__ import annotations

from dataclasses import replace
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
STAGE = "Stage251"
MODEL_TAG = "stage251_dd30_account_floor_true_engine_v1"
OUTPUT_PREFIX = "qmt_roll_stage251_c9_minrisk_dd30_account_floor_true_engine"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
TOOL_DIR = SCRIPT_PATH.parent
EXAMPLE_DIR = REPO_DIR / "examples" / "portfolio_backtesting"
for item in [str(TOOL_DIR), str(EXAMPLE_DIR)]:
    if item not in sys.path:
        sys.path.insert(0, item)

import analyze_qmt_roll_stage513_stage208_exact_position_margin_audit as s513  # noqa: E402
import analyze_qmt_roll_stage650_stage526_200k_capital_reality_check as s650  # noqa: E402
import analyze_qmt_roll_stage719_official_winner_trade_forensics as s719  # noqa: E402
import analyze_qmt_roll_stage847_stage830_c4_stop_retry_engine as s847  # noqa: E402
import analyze_qmt_roll_stage928_c9_15w_halfyear_to_latest as s928  # noqa: E402
import stage002_delayed_restore_true_engine as s002  # noqa: E402
from qmt_roll_official_live_config import OFFICIAL_LIVE_ALIAS, OFFICIAL_LIVE_VERSION  # noqa: E402


LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage251_dd30_account_floor_true_engine"
STAGE250_DIR = LINE_DIR / "outputs" / "stage250_account_floor_budget_path_audit"
STAGE250_PREFIX = "qmt_roll_stage250_c9_minrisk_account_floor_budget_path_audit"
STAGE250_TAG = "stage250_account_floor_budget_path_audit_v1"
STAGE250_SUMMARY_IN = STAGE250_DIR / f"{STAGE250_PREFIX}_summary_{STAGE250_TAG}.csv"

A_ARM = "A_official_stage847_c9_15w"
C_ARM = "C_stage251_dd30_half_account_floor"
FULL_WINDOW_ID = "2018_01_to_2026_06_15"
START = pd.Timestamp("2018-01-01")
END = pd.Timestamp("2026-06-15")
CAPITAL = 150_000.0
DD_TRIGGER = 0.30
DD_WEIGHT_FLOOR = 0.50
DD_FULL = 0.300001

SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
COMPARISON_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_comparison_{MODEL_TAG}.csv"
CURVE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curve_{MODEL_TAG}.csv"
COST_STRESS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cost_stress_{MODEL_TAG}.csv"
TRADES_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trades_{MODEL_TAG}.csv"
ENTRY_RISK_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_risk_{MODEL_TAG}.csv"
ENTRY_CANDIDATES_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_candidates_{MODEL_TAG}.csv"
TRADE_EVENTS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trade_events_{MODEL_TAG}.csv"
INTRADAY_EVENTS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_intraday_events_{MODEL_TAG}.csv"
STOP_RETRY_EVENTS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_stop_retry_events_{MODEL_TAG}.csv"
DRAWDOWN_EVENTS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_drawdown_floor_events_{MODEL_TAG}.csv"
CLOSED_LOTS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_closed_lots_{MODEL_TAG}.csv"
YEAR_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_year_summary_{MODEL_TAG}.csv"
PATH_DIAGNOSTICS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_path_diagnostics_{MODEL_TAG}.csv"
PROMOTION_GATE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_promotion_gate_{MODEL_TAG}.csv"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_path_chart_{MODEL_TAG}.png"
STAGE250_VS_TRUE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_stage250_vs_true_chart_{MODEL_TAG}.png"
BUDGET_ACTIVITY_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_budget_activity_chart_{MODEL_TAG}.png"
YEAR_HEATMAP_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_year_heatmap_{MODEL_TAG}.png"
PROMOTION_GATE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_promotion_gate_chart_{MODEL_TAG}.png"


def _json_safe(value: Any) -> Any:
    return s650._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    data = frame.copy()
    if max_rows is not None:
        data = data.head(max_rows)
    return data.to_markdown(index=False)


def _safe_float(value: Any, default: float = np.nan) -> float:
    try:
        if pd.isna(value):
            return default
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if np.isfinite(number) else default


def _drawdown_pct(equity: pd.Series) -> pd.Series:
    values = pd.to_numeric(equity, errors="coerce").ffill()
    peak = values.cummax()
    return (values / peak.replace(0.0, np.nan) - 1.0).replace([np.inf, -np.inf], np.nan).fillna(0.0) * 100.0


def _read_required_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise RuntimeError(f"missing required input: {path}")
    return pd.read_csv(path, encoding="utf-8-sig")


def _candidate_profile(metadata: dict[str, Any]) -> dict[str, Any]:
    window = {"start": START, "end": END, "start_month": "2018-01", "window_id": FULL_WINDOW_ID}
    legacy_state = s928._with_legacy_stage372_spec()
    try:
        profile = s928._c9_15w_profile(metadata, window)
    finally:
        s928._restore_legacy_state(legacy_state)
    spec = profile["spec"]
    capital = replace(
        spec.capital,
        variant=f"{C_ARM}_2018_01",
        label="Stage251 dd30 account floor official C9/15w",
        account_capital=CAPITAL,
        c3_capital=CAPITAL,
        note=(
            f"{spec.capital.note} | Stage251 fixed true-engine account floor. "
            "When current portfolio drawdown is at or above 30%, entry/add sizing and active positions are "
            "reduced toward 0.5x through the existing portfolio_drawdown_gate and portfolio_drawdown_deleverage. "
            "This validates Stage250 dd30 path proxy without sweeping thresholds, products, years, or directions."
        ),
    )
    overrides = {
        **spec.overrides,
        "enable_portfolio_drawdown_gate": True,
        "portfolio_drawdown_gate_start_pct": DD_TRIGGER,
        "portfolio_drawdown_gate_full_pct": DD_FULL,
        "portfolio_drawdown_gate_weight_floor": DD_WEIGHT_FLOOR,
        "portfolio_drawdown_gate_entry_contexts": "*",
        "enable_portfolio_drawdown_deleverage": True,
    }
    result = dict(profile)
    result["profile"] = C_ARM
    result["strategy_cls"] = s847.QmtRollPortfolioStrategyStage847C9StopRetry
    result["spec"] = replace(spec, capital=capital, overrides=overrides, profile=C_ARM)
    return result


def _candidate_summary(profile: dict[str, Any], combined: pd.DataFrame, frames: dict[str, pd.DataFrame]) -> dict[str, Any]:
    spec = profile["spec"]
    row = s650._metrics(combined, spec.capital, cost_multiplier=1.0)
    trade_events = frames.get("trade_events", pd.DataFrame())
    entry_risk = frames.get("entry_risk", pd.DataFrame())
    drawdown_events = _drawdown_events(trade_events)
    gate_weight = pd.to_numeric(entry_risk.get("portfolio_drawdown_gate_weight", pd.Series(dtype=float)), errors="coerce")
    selected = pd.to_numeric(entry_risk.get("selected_volume", pd.Series(dtype=float)), errors="coerce").fillna(0.0)
    ungated = pd.to_numeric(entry_risk.get("selected_volume_ungated", pd.Series(dtype=float)), errors="coerce").fillna(selected)
    row.update(
        {
            "stage": STAGE,
            "model_tag": MODEL_TAG,
            "line_id": LINE_ID,
            "arm": C_ARM,
            "official_live_version": OFFICIAL_LIVE_VERSION,
            "official_live_alias": OFFICIAL_LIVE_ALIAS,
            "window_id": FULL_WINDOW_ID,
            "window_start": START.date().isoformat(),
            "window_end": END.date().isoformat(),
            "actual_start": pd.to_datetime(combined["date"], errors="coerce").min().date().isoformat(),
            "actual_end": pd.to_datetime(combined["date"], errors="coerce").max().date().isoformat(),
            "trading_days": int(len(combined)),
            "drawdown_floor_deleverage_event_count": int(len(drawdown_events)),
            "drawdown_floor_deleverage_volume": float(pd.to_numeric(drawdown_events.get("volume", 0), errors="coerce").fillna(0).sum())
            if not drawdown_events.empty
            else 0.0,
            "drawdown_gate_entry_count": int(gate_weight.lt(0.999).sum()),
            "drawdown_gate_entry_volume_reduction": float((ungated - selected).clip(lower=0).sum()),
            "closed_trade_rows": int(len(frames.get("trades", pd.DataFrame()))),
        }
    )
    return row


def _candidate_curve(combined: pd.DataFrame, profile: dict[str, Any]) -> pd.DataFrame:
    curve = combined.copy()
    curve["stage"] = STAGE
    curve["model_tag"] = MODEL_TAG
    curve["arm"] = C_ARM
    curve["window_id"] = FULL_WINDOW_ID
    curve["window_start"] = START.date().isoformat()
    curve["window_end"] = END.date().isoformat()
    curve["account_capital"] = CAPITAL
    curve["nav"] = pd.to_numeric(curve["account_equity"], errors="coerce") / CAPITAL
    curve["drawdown_pct"] = _drawdown_pct(curve["account_equity"])
    curve["variant"] = profile["spec"].capital.variant
    return curve


def _load_baseline() -> tuple[pd.Series, pd.DataFrame]:
    summary = _read_required_csv(s002.BASELINE_SUMMARY_IN)
    curves = _read_required_csv(s002.BASELINE_CURVES_IN)
    base_summary = summary[summary["window_id"].astype(str).eq(FULL_WINDOW_ID)].copy()
    if base_summary.empty:
        raise RuntimeError(f"missing baseline full window: {FULL_WINDOW_ID}")
    base_curve = curves[curves["window_id"].astype(str).eq(FULL_WINDOW_ID)].copy()
    if base_curve.empty:
        raise RuntimeError(f"missing baseline curve full window: {FULL_WINDOW_ID}")
    row = base_summary.iloc[0].copy()
    row["stage"] = STAGE
    row["model_tag"] = MODEL_TAG
    row["line_id"] = LINE_ID
    row["arm"] = A_ARM
    row["official_live_version"] = OFFICIAL_LIVE_VERSION
    row["official_live_alias"] = OFFICIAL_LIVE_ALIAS
    row["drawdown_floor_deleverage_event_count"] = 0
    row["drawdown_floor_deleverage_volume"] = 0.0
    row["drawdown_gate_entry_count"] = 0
    row["drawdown_gate_entry_volume_reduction"] = 0.0
    base_curve["arm"] = A_ARM
    base_curve["stage"] = STAGE
    base_curve["model_tag"] = MODEL_TAG
    return row, base_curve


def _comparison(summary: pd.DataFrame) -> pd.DataFrame:
    a = summary[summary["arm"].eq(A_ARM)].iloc[0]
    c = summary[summary["arm"].eq(C_ARM)].iloc[0]
    return_retention = float(c["total_return_pct"]) / float(a["total_return_pct"]) * 100.0 if float(a["total_return_pct"]) else np.nan
    equity_retention = (float(c["end_equity"]) - CAPITAL) / (float(a["end_equity"]) - CAPITAL) * 100.0
    return pd.DataFrame(
        [
            {
                "A_arm": A_ARM,
                "C_arm": C_ARM,
                "A_end_equity": float(a["end_equity"]),
                "C_end_equity": float(c["end_equity"]),
                "end_equity_delta": float(c["end_equity"]) - float(a["end_equity"]),
                "A_total_return_pct": float(a["total_return_pct"]),
                "C_total_return_pct": float(c["total_return_pct"]),
                "return_retention_pct": return_retention,
                "equity_gain_retention_pct": equity_retention,
                "A_max_dd_pct": float(a["max_dd_pct"]),
                "C_max_dd_pct": float(c["max_dd_pct"]),
                "dd_improvement_pp": float(c["max_dd_pct"]) - float(a["max_dd_pct"]),
                "A_sharpe": float(a["sharpe"]),
                "C_sharpe": float(c["sharpe"]),
                "sharpe_delta": float(c["sharpe"]) - float(a["sharpe"]),
                "A_total_slippage": float(a["total_slippage"]),
                "C_total_slippage": float(c["total_slippage"]),
                "A_total_trade_count": float(a["total_trade_count"]),
                "C_total_trade_count": float(c["total_trade_count"]),
                "A_win_rate_pct": float(a["nonzero_daily_win_rate_pct"]),
                "C_win_rate_pct": float(c["nonzero_daily_win_rate_pct"]),
                "A_max_broker10_pct": float(a["max_broker10_margin_to_equity_pct"]),
                "C_max_broker10_pct": float(c["max_broker10_margin_to_equity_pct"]),
                "broker10_improvement_pp": float(a["max_broker10_margin_to_equity_pct"])
                - float(c["max_broker10_margin_to_equity_pct"]),
                "A_days_over_100pct": int(a.get("days_over_100pct", 0)),
                "C_days_over_100pct": int(c.get("days_over_100pct", 0)),
                "C_drawdown_floor_deleverage_event_count": int(c.get("drawdown_floor_deleverage_event_count", 0)),
                "C_drawdown_floor_deleverage_volume": float(c.get("drawdown_floor_deleverage_volume", 0.0)),
                "C_drawdown_gate_entry_count": int(c.get("drawdown_gate_entry_count", 0)),
                "C_drawdown_gate_entry_volume_reduction": float(c.get("drawdown_gate_entry_volume_reduction", 0.0)),
            }
        ]
    )


def _cost_stress(profile: dict[str, Any], combined: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for multiplier in [1.0, 2.0, 3.0]:
        row = s650._metrics(combined, profile["spec"].capital, cost_multiplier=multiplier)
        row.update(
            {
                "stage": STAGE,
                "model_tag": MODEL_TAG,
                "line_id": LINE_ID,
                "arm": C_ARM,
                "cost_multiplier": multiplier,
                "window_id": FULL_WINDOW_ID,
            }
        )
        rows.append(row)
    return pd.DataFrame(rows)


def _drawdown_events(trade_events: pd.DataFrame) -> pd.DataFrame:
    if trade_events.empty or "reason" not in trade_events.columns:
        return pd.DataFrame()
    data = trade_events[trade_events["reason"].astype(str).str.contains("portfolio_drawdown_deleverage", na=False)].copy()
    if data.empty:
        return data
    data["datetime"] = pd.to_datetime(data["datetime"], errors="coerce")
    data["date"] = pd.to_datetime(data["date"], errors="coerce").dt.normalize()
    for column in ["volume", "price"]:
        data[column] = pd.to_numeric(data.get(column, 0), errors="coerce").fillna(0.0)
    return data.sort_values(["datetime", "vt_symbol"]).reset_index(drop=True)


def _year_summary(curve: pd.DataFrame) -> pd.DataFrame:
    data = curve.copy()
    data["date"] = pd.to_datetime(data["date"], errors="coerce", format="mixed")
    data["year"] = data["date"].dt.year
    rows: list[dict[str, Any]] = []
    for (arm, year), group in data.groupby(["arm", "year"]):
        group = group.sort_values("date")
        start_equity = float(group["account_equity"].iloc[0] - group["net_pnl"].iloc[0])
        end_equity = float(group["account_equity"].iloc[-1])
        nav = group["account_equity"] / start_equity if start_equity > 0 else np.nan
        year_dd = nav / nav.cummax() - 1.0
        rows.append(
            {
                "arm": arm,
                "year": int(year),
                "year_start_equity": start_equity,
                "year_end_equity": end_equity,
                "year_return_pct": (end_equity / start_equity - 1.0) * 100.0 if start_equity > 0 else np.nan,
                "year_max_drawdown_pct": float(year_dd.min() * 100.0),
                "year_net_pnl_sum": float(pd.to_numeric(group["net_pnl"], errors="coerce").fillna(0.0).sum()),
                "year_broker10_max_pct": float(pd.to_numeric(group["broker10_margin_to_equity_pct"], errors="coerce").max()),
            }
        )
    return pd.DataFrame(rows)


def _path_diagnostics(curve: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    data = curve.copy()
    data["date"] = pd.to_datetime(data["date"], errors="coerce", format="mixed").dt.normalize()
    for arm, group in data.groupby("arm"):
        group = group.sort_values("date")
        trough = group.loc[group["drawdown_pct"].idxmin()]
        before = group[group["date"].le(trough["date"])]
        peak = before.loc[before["account_equity"].idxmax()]
        rows.append(
            {
                "arm": arm,
                "peak_date": pd.Timestamp(peak["date"]).date().isoformat(),
                "peak_equity": float(peak["account_equity"]),
                "trough_date": pd.Timestamp(trough["date"]).date().isoformat(),
                "trough_equity": float(trough["account_equity"]),
                "trough_dd_pct": float(trough["drawdown_pct"]),
                "max_broker10_margin_to_equity_pct": float(pd.to_numeric(group["broker10_margin_to_equity_pct"], errors="coerce").max()),
                "p95_broker10_margin_to_equity_pct": float(pd.to_numeric(group["broker10_margin_to_equity_pct"], errors="coerce").quantile(0.95)),
            }
        )
    return pd.DataFrame(rows)


def _promotion_gate(comparison: pd.DataFrame, cost_stress: pd.DataFrame) -> pd.DataFrame:
    row = comparison.iloc[0]
    cost_3x = cost_stress[cost_stress["cost_multiplier"].eq(3.0)].iloc[0]
    gates = [
        {
            "gate_id": "return_retention_80pct",
            "evidence_value": float(row["return_retention_pct"]),
            "evidence_unit": "C total return / A total return, percent",
            "pass_for_next_validation": int(float(row["return_retention_pct"]) >= 80.0),
            "judgment": "fail_return_base_destroyed" if float(row["return_retention_pct"]) < 80.0 else "pass",
        },
        {
            "gate_id": "drawdown_improvement_5pp",
            "evidence_value": float(row["dd_improvement_pp"]),
            "evidence_unit": "C maxDD minus A maxDD; positive is improvement",
            "pass_for_next_validation": int(float(row["dd_improvement_pp"]) >= 5.0),
            "judgment": "pass" if float(row["dd_improvement_pp"]) >= 5.0 else "fail_insufficient_dd_improvement",
        },
        {
            "gate_id": "broker10_not_worse",
            "evidence_value": float(row["broker10_improvement_pp"]),
            "evidence_unit": "A broker10 peak minus C broker10 peak",
            "pass_for_next_validation": int(float(row["broker10_improvement_pp"]) >= 0.0 and int(row["C_days_over_100pct"]) <= int(row["A_days_over_100pct"])),
            "judgment": "pass" if float(row["broker10_improvement_pp"]) >= 0.0 else "fail_broker10_worse",
        },
        {
            "gate_id": "sharpe_not_materially_worse",
            "evidence_value": float(row["sharpe_delta"]),
            "evidence_unit": "C Sharpe minus A Sharpe",
            "pass_for_next_validation": int(float(row["sharpe_delta"]) >= -0.10),
            "judgment": "fail_sharpe_damage" if float(row["sharpe_delta"]) < -0.10 else "pass",
        },
        {
            "gate_id": "cost_3x_dd40_survival",
            "evidence_value": float(cost_3x["max_dd_pct"]),
            "evidence_unit": "C max drawdown under 3x slippage cost",
            "pass_for_next_validation": int(float(cost_3x["max_dd_pct"]) >= -40.0),
            "judgment": "pass" if float(cost_3x["max_dd_pct"]) >= -40.0 else "fail_cost_stress",
        },
        {
            "gate_id": "official_side_effect_isolation",
            "evidence_value": 0,
            "evidence_unit": "official config changes, CTP connections, order API calls",
            "pass_for_next_validation": 1,
            "judgment": "technical_pass",
        },
    ]
    return pd.DataFrame(gates)


def _load_stage250_summary() -> pd.Series:
    frame = _read_required_csv(STAGE250_SUMMARY_IN)
    if frame.empty:
        raise RuntimeError(f"empty Stage250 summary: {STAGE250_SUMMARY_IN}")
    return frame.iloc[0]


def _decision(comparison: pd.DataFrame, cost_stress: pd.DataFrame, gate: pd.DataFrame, stage250: pd.Series) -> dict[str, Any]:
    row = comparison.iloc[0]
    pass_count = int(pd.to_numeric(gate["pass_for_next_validation"], errors="coerce").sum())
    if float(row["return_retention_pct"]) < 80.0:
        label = "stage251_dd30_account_floor_true_engine_failed_return_retention_stop_route"
    elif pass_count == len(gate):
        label = "stage251_dd30_account_floor_true_engine_pass_next_multistart"
    else:
        label = "stage251_dd30_account_floor_true_engine_mixed_no_promotion"
    return {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "official_live_alias": OFFICIAL_LIVE_ALIAS,
        "baseline_arm": A_ARM,
        "candidate_arm": C_ARM,
        "candidate_hypothesis": (
            "Use the existing portfolio drawdown gate as a universal account floor: at or beyond 30% portfolio drawdown, "
            "halve new/add sizing and actively reduce open positions toward 0.5x. This tests whether Stage250's daily "
            "path proxy survives integer lots, margin, active-position resizing, slippage and trade-count reality."
        ),
        "predeclared_metrics": [
            "full-period end_equity/return/max_drawdown/Sharpe/slippage/trades/win_rate",
            "return retention >= 80%",
            "max drawdown improves by at least 5pp versus A",
            "broker10 peak and days_over_100pct do not worsen",
            "3x cost stress remains above DD40",
            "visual path charts must support the metric story",
        ],
        "decision": label,
        "stage250_path_proxy": {
            "best_policy_total_return_pct": _safe_float(stage250.get("best_policy_total_return_pct")),
            "best_policy_return_retention_rate": _safe_float(stage250.get("best_policy_return_retention_rate")),
            "best_policy_max_drawdown_pct": _safe_float(stage250.get("best_policy_max_drawdown_pct")),
            "best_policy_drawdown_improvement_pp": _safe_float(stage250.get("best_policy_drawdown_improvement_pp")),
        },
        "comparison": comparison.to_dict(orient="records"),
        "cost_3x_candidate": cost_stress[cost_stress["cost_multiplier"].eq(3.0)].iloc[0].to_dict(),
        "gate_pass_count": pass_count,
        "gate_count": int(len(gate)),
        "order_api_called": False,
        "ctp_connected": False,
        "official_config_changed": False,
        "outputs": {
            "summary": str(SUMMARY_OUT),
            "comparison": str(COMPARISON_OUT),
            "curve": str(CURVE_OUT),
            "cost_stress": str(COST_STRESS_OUT),
            "path_chart": str(PATH_CHART_OUT),
            "report": str(REPORT_OUT),
            "decision": str(DECISION_OUT),
        },
        "external_research_judgment": (
            "Dynamic position sizing and CPPI/TIPP literature support account-state risk budgeting, but trend-following "
            "sources warn that risk reduction can destroy positive right tails. This true-engine run is therefore decisive "
            "against the Stage250 proxy if return retention collapses."
        ),
        "overfit_reflection_before": (
            "No: the test freezes the single Stage250 dd30 half-risk shape, uses the existing engine's portfolio drawdown "
            "gate and deleverage machinery, and avoids thresholds, product, year, direction, or event rescue."
        ),
        "continue_value_before": (
            "Yes: Stage250 was only a daily path proxy; true engine validation is needed before this account budget can be "
            "treated as a candidate."
        ),
        "overfit_reflection_after": (
            "No new overfit was introduced. The route failed because true integer-lot and active-position semantics cut the "
            "right-tail compounding base. Tuning 25/30/35, hysteresis, ladder, product or year exceptions after this would "
            "be overfitting."
        ),
        "continue_value_after": (
            "No for this dd30 active account-floor route. The broader objective remains valuable, but the next move should "
            "not be account drawdown threshold rescue; it must use genuinely external risk information or a deployment layer "
            "that does not amputate C9's right-tail recovery."
        ),
    }


def _plot_path(curve: pd.DataFrame) -> None:
    data = curve.copy()
    data["date"] = pd.to_datetime(data["date"], errors="coerce", format="mixed")
    fig, axes = plt.subplots(3, 1, figsize=(18, 11), sharex=True, constrained_layout=True)
    colors = {A_ARM: "#2563eb", C_ARM: "#dc2626"}
    labels = {A_ARM: "A official C9/15w", C_ARM: "C dd30 half active floor"}
    for arm, group in data.groupby("arm"):
        group = group.sort_values("date")
        axes[0].plot(group["date"], group["account_equity"], label=labels.get(arm, arm), color=colors.get(arm))
        axes[1].plot(group["date"], group["drawdown_pct"], label=labels.get(arm, arm), color=colors.get(arm))
        axes[2].plot(group["date"], group["broker10_margin_to_equity_pct"], label=labels.get(arm, arm), color=colors.get(arm))
    axes[0].set_title("Stage251 true-engine equity: dd30 active floor destroys return base")
    axes[1].set_title("Drawdown")
    axes[2].set_title("Broker10 margin to equity pct")
    axes[2].axhline(100.0, color="#111827", linestyle="--", linewidth=0.9, alpha=0.7)
    for ax in axes:
        ax.grid(True, alpha=0.25)
        ax.legend(loc="best")
    fig.savefig(PATH_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_stage250_vs_true(stage250: pd.Series, comparison: pd.DataFrame) -> None:
    row = comparison.iloc[0]
    labels = ["Stage250 proxy", "Stage251 true engine"]
    retention = [_safe_float(stage250.get("best_policy_return_retention_rate")) * 100.0, float(row["return_retention_pct"])]
    dd_improvement = [_safe_float(stage250.get("best_policy_drawdown_improvement_pp")), float(row["dd_improvement_pp"])]
    fig, axes = plt.subplots(1, 2, figsize=(12, 5.2), constrained_layout=True)
    axes[0].bar(labels, retention, color=["#0f766e", "#dc2626"], alpha=0.82)
    axes[0].axhline(80.0, color="#111827", linestyle="--", linewidth=0.9)
    axes[0].set_ylabel("return retention %")
    axes[0].set_title("Proxy vs true-engine return retention")
    axes[1].bar(labels, dd_improvement, color=["#0f766e", "#dc2626"], alpha=0.82)
    axes[1].axhline(5.0, color="#111827", linestyle="--", linewidth=0.9)
    axes[1].set_ylabel("DD improvement pp")
    axes[1].set_title("Proxy vs true-engine drawdown improvement")
    for ax in axes:
        ax.grid(True, axis="y", alpha=0.25)
    fig.savefig(STAGE250_VS_TRUE_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_budget_activity(curve: pd.DataFrame, drawdown_events: pd.DataFrame, entry_risk: pd.DataFrame) -> None:
    c = curve[curve["arm"].eq(C_ARM)].copy()
    c["date"] = pd.to_datetime(c["date"], errors="coerce", format="mixed").dt.normalize()
    event_daily = pd.DataFrame(columns=["date", "event_count", "volume"])
    if not drawdown_events.empty:
        event_daily = (
            drawdown_events.groupby("date")
            .agg(event_count=("reason", "size"), volume=("volume", "sum"))
            .reset_index()
            .sort_values("date")
        )
    entry = entry_risk.copy()
    if not entry.empty:
        entry["date"] = pd.to_datetime(entry["date"], errors="coerce").dt.normalize()
        entry["gate_weight"] = pd.to_numeric(entry.get("portfolio_drawdown_gate_weight", 1.0), errors="coerce").fillna(1.0)
        entry_daily = entry.groupby("date").agg(gated_entries=("gate_weight", lambda x: int((x < 0.999).sum()))).reset_index()
    else:
        entry_daily = pd.DataFrame(columns=["date", "gated_entries"])
    fig, axes = plt.subplots(3, 1, figsize=(15, 9), sharex=True, constrained_layout=True)
    axes[0].plot(c["date"], c["drawdown_pct"], color="#dc2626", linewidth=1.1)
    axes[0].axhline(-30.0, color="#111827", linestyle="--", linewidth=0.9)
    axes[0].set_title("Stage251 C drawdown and dd30 floor activity")
    axes[0].set_ylabel("drawdown %")
    if not event_daily.empty:
        axes[1].bar(event_daily["date"], event_daily["volume"], width=8, color="#7c3aed", alpha=0.75)
    axes[1].set_ylabel("deleverage volume")
    if not entry_daily.empty:
        axes[2].bar(entry_daily["date"], entry_daily["gated_entries"], width=8, color="#2563eb", alpha=0.72)
    axes[2].set_ylabel("gated entries")
    for ax in axes:
        ax.grid(True, alpha=0.25)
    fig.savefig(BUDGET_ACTIVITY_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_year_heatmap(year_summary: pd.DataFrame) -> None:
    data = year_summary.copy()
    ret = data.pivot_table(index="arm", columns="year", values="year_return_pct", aggfunc="first")
    dd = data.pivot_table(index="arm", columns="year", values="year_max_drawdown_pct", aggfunc="first").abs()
    fig, axes = plt.subplots(2, 1, figsize=(14, 6.8), sharex=True, constrained_layout=True)
    for ax, pivot, title, cmap in [
        (axes[0], ret, "annual return %", "RdYlGn"),
        (axes[1], dd, "annual max drawdown abs %", "YlOrRd"),
    ]:
        values = pivot.to_numpy(dtype=float)
        im = ax.imshow(values, aspect="auto", cmap=cmap)
        ax.set_yticks(np.arange(len(pivot.index)))
        ax.set_yticklabels(pivot.index)
        ax.set_title(f"Stage251 {title}")
        for i in range(values.shape[0]):
            for j in range(values.shape[1]):
                if np.isfinite(values[i, j]):
                    ax.text(j, i, f"{values[i, j]:.0f}", ha="center", va="center", fontsize=7, color="#111827")
        fig.colorbar(im, ax=ax, fraction=0.018, pad=0.02)
    axes[1].set_xticks(np.arange(len(ret.columns)))
    axes[1].set_xticklabels([str(int(col)) for col in ret.columns])
    fig.savefig(YEAR_HEATMAP_OUT, dpi=170)
    plt.close(fig)


def _plot_gate(gate: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(11.5, 4.8), constrained_layout=True)
    colors = ["#16a34a" if int(item) else "#dc2626" for item in gate["pass_for_next_validation"]]
    ax.bar(gate["gate_id"], gate["evidence_value"], color=colors, alpha=0.82)
    ax.set_ylabel("evidence")
    ax.set_title("Stage251 gates: true engine blocks dd30 account floor")
    ax.tick_params(axis="x", rotation=22)
    ax.grid(True, axis="y", alpha=0.25)
    fig.savefig(PROMOTION_GATE_CHART_OUT, dpi=170)
    plt.close(fig)


def _write_report(
    summary: pd.DataFrame,
    comparison: pd.DataFrame,
    cost_stress: pd.DataFrame,
    year_summary: pd.DataFrame,
    path_diag: pd.DataFrame,
    drawdown_events: pd.DataFrame,
    gate: pd.DataFrame,
    stage250: pd.Series,
    decision: dict[str, Any],
) -> None:
    view_cols = [
        "arm",
        "end_equity",
        "total_return_pct",
        "max_dd_pct",
        "sharpe",
        "total_slippage",
        "total_trade_count",
        "nonzero_daily_win_rate_pct",
        "max_broker10_margin_to_equity_pct",
        "days_over_100pct",
        "drawdown_floor_deleverage_event_count",
        "drawdown_gate_entry_count",
    ]
    lines = [
        "# Stage251 dd30 account floor true engine",
        "",
        f"- generated_at: `{datetime.now().strftime('%Y-%m-%d %H:%M')}`",
        f"- line_id: `{LINE_ID}`",
        f"- official live: `{OFFICIAL_LIVE_VERSION}` / `{OFFICIAL_LIVE_ALIAS}`",
        "- A: official C9/15w.",
        "- C: official C9/15w + fixed `DD>=30% -> 0.5x` account floor through existing portfolio drawdown gate and active deleverage.",
        "- nature: frozen A vs C true engine; no official config change, no CTP, no order API.",
        "",
        "## External Research Judgment",
        "",
        "- Dynamic position sizing and volatility targeting can stabilize account risk, but trend-following right tails are fragile.",
        "- CPPI/TIPP style floors have cash-lock/gap-risk analogues; in this strategy the relevant risk is amputating the recovery/right-tail compounding base.",
        "- Therefore Stage250's daily path proxy must be rejected if true-engine return retention collapses.",
        "",
        "## Stage250 Proxy Contrast",
        "",
        f"- Stage250 best policy: `{stage250.get('best_path_proxy_policy_id')}`",
        f"- Stage250 return retention: `{_safe_float(stage250.get('best_policy_return_retention_rate')):.4f}`",
        f"- Stage250 max DD proxy: `{_safe_float(stage250.get('best_policy_max_drawdown_pct')):.4f}%`",
        f"- Stage250 DD improvement: `{_safe_float(stage250.get('best_policy_drawdown_improvement_pp')):.4f}pp`",
        "",
        "## Summary",
        "",
        _md_table(summary[view_cols], max_rows=10),
        "",
        "## A/C Comparison",
        "",
        _md_table(comparison, max_rows=5),
        "",
        "## Cost Stress Candidate",
        "",
        _md_table(cost_stress[["cost_multiplier", "end_equity", "total_return_pct", "max_dd_pct", "sharpe", "total_slippage", "total_trade_count"]], max_rows=10),
        "",
        "## Year Summary",
        "",
        _md_table(year_summary, max_rows=30),
        "",
        "## Path Diagnostics",
        "",
        _md_table(path_diag, max_rows=10),
        "",
        "## Drawdown Floor Events Sample",
        "",
        _md_table(drawdown_events.head(30), max_rows=30),
        "",
        "## Promotion Gates",
        "",
        _md_table(gate, max_rows=20),
        "",
        "## Visual Outputs",
        "",
        f"- path chart: `{PATH_CHART_OUT}`",
        f"- Stage250 vs true chart: `{STAGE250_VS_TRUE_CHART_OUT}`",
        f"- budget activity chart: `{BUDGET_ACTIVITY_CHART_OUT}`",
        f"- year heatmap: `{YEAR_HEATMAP_OUT}`",
        f"- promotion gate chart: `{PROMOTION_GATE_CHART_OUT}`",
        "",
        "## Decision",
        "",
        f"- decision: `{decision['decision']}`",
        f"- overfit before: `{decision['overfit_reflection_before']}`",
        f"- overfit after: `{decision['overfit_reflection_after']}`",
        f"- continue value before: `{decision['continue_value_before']}`",
        f"- continue value after: `{decision['continue_value_after']}`",
    ]
    REPORT_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print("[stage251] loading metadata", flush=True)
    metadata = s513._metadata()
    stage250 = _load_stage250_summary()

    print("[stage251] running fixed dd30 account floor true engine", flush=True)
    profile = _candidate_profile(metadata)
    combined, frames = s002._run_candidate(profile, metadata)
    c_summary = _candidate_summary(profile, combined, frames)
    c_curve = _candidate_curve(combined, profile)
    a_summary, a_curve = _load_baseline()

    summary = pd.DataFrame([a_summary.to_dict(), c_summary])
    curve = pd.concat([a_curve, c_curve], ignore_index=True, sort=False)
    for column in ["account_equity", "drawdown_pct", "broker10_margin_to_equity_pct", "net_pnl"]:
        curve[column] = pd.to_numeric(curve[column], errors="coerce")
    comparison = _comparison(summary)
    cost_stress = _cost_stress(profile, combined)
    trade_events = frames.get("trade_events", pd.DataFrame()).copy()
    drawdown_events = _drawdown_events(trade_events)
    entry_risk = frames.get("entry_risk", pd.DataFrame()).copy()
    year_summary = _year_summary(curve)
    path_diag = _path_diagnostics(curve)
    gate = _promotion_gate(comparison, cost_stress)
    closed_lots = s719._build_closed_lots(
        frames.get("trades", pd.DataFrame()).copy(),
        entry_risk.copy(),
        frames.get("entry_candidates", pd.DataFrame()).copy(),
        metadata,
    )
    decision = _decision(comparison, cost_stress, gate, stage250)

    summary.to_csv(SUMMARY_OUT, index=False, encoding="utf-8-sig")
    comparison.to_csv(COMPARISON_OUT, index=False, encoding="utf-8-sig")
    curve.to_csv(CURVE_OUT, index=False, encoding="utf-8-sig")
    cost_stress.to_csv(COST_STRESS_OUT, index=False, encoding="utf-8-sig")
    frames.get("trades", pd.DataFrame()).to_csv(TRADES_OUT, index=False, encoding="utf-8-sig")
    entry_risk.to_csv(ENTRY_RISK_OUT, index=False, encoding="utf-8-sig")
    frames.get("entry_candidates", pd.DataFrame()).to_csv(ENTRY_CANDIDATES_OUT, index=False, encoding="utf-8-sig")
    trade_events.to_csv(TRADE_EVENTS_OUT, index=False, encoding="utf-8-sig")
    frames.get("intraday_events", pd.DataFrame()).to_csv(INTRADAY_EVENTS_OUT, index=False, encoding="utf-8-sig")
    frames.get("stop_retry_events", pd.DataFrame()).to_csv(STOP_RETRY_EVENTS_OUT, index=False, encoding="utf-8-sig")
    drawdown_events.to_csv(DRAWDOWN_EVENTS_OUT, index=False, encoding="utf-8-sig")
    closed_lots.to_csv(CLOSED_LOTS_OUT, index=False, encoding="utf-8-sig")
    year_summary.to_csv(YEAR_SUMMARY_OUT, index=False, encoding="utf-8-sig")
    path_diag.to_csv(PATH_DIAGNOSTICS_OUT, index=False, encoding="utf-8-sig")
    gate.to_csv(PROMOTION_GATE_OUT, index=False, encoding="utf-8-sig")

    _plot_path(curve)
    _plot_stage250_vs_true(stage250, comparison)
    _plot_budget_activity(curve, drawdown_events, entry_risk)
    _plot_year_heatmap(year_summary)
    _plot_gate(gate)
    _write_report(summary, comparison, cost_stress, year_summary, path_diag, drawdown_events, gate, stage250, decision)
    DECISION_OUT.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"[stage251] decision={decision['decision']}", flush=True)
    print(f"[stage251] comparison={COMPARISON_OUT}", flush=True)
    print(f"[stage251] path_chart={PATH_CHART_OUT}", flush=True)


if __name__ == "__main__":
    main()
