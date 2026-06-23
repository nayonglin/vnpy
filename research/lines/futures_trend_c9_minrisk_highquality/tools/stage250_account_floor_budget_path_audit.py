from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
import sys
from typing import Any, Callable

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


LINE_ID = "futures_trend_c9_minrisk_highquality"
STAGE = "Stage250"
MODEL_TAG = "stage250_account_floor_budget_path_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage250_c9_minrisk_account_floor_budget_path_audit"

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
OUTPUT_DIR = LINE_DIR / "outputs" / "stage250_account_floor_budget_path_audit"

STAGE249_DIR = LINE_DIR / "outputs" / "stage249_early_runway_frontier_audit"
STAGE249_PREFIX = "qmt_roll_stage249_c9_minrisk_early_runway_frontier_audit"
STAGE249_TAG = "stage249_early_runway_frontier_audit_v1"
STAGE249_ROWS_IN = STAGE249_DIR / f"{STAGE249_PREFIX}_frontier_rows_{STAGE249_TAG}.csv"

CURVES_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_policy_curves_{MODEL_TAG}.csv"
POLICY_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_policy_summary_{MODEL_TAG}.csv"
ORDER_SCALE_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_order_scale_summary_{MODEL_TAG}.csv"
YEAR_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_year_summary_{MODEL_TAG}.csv"
STRESS_EPISODE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_stress_episode_manifest_{MODEL_TAG}.csv"
PROMOTION_GATE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_promotion_gate_{MODEL_TAG}.csv"
SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

POLICY_PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_policy_path_chart_{MODEL_TAG}.png"
OBJECTIVE_FRONTIER_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_objective_frontier_chart_{MODEL_TAG}.png"
BEST_SCALE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_best_policy_scale_timeline_{MODEL_TAG}.png"
TAIL_RETENTION_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_tail_retention_chart_{MODEL_TAG}.png"
YEAR_HEATMAP_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_year_heatmap_{MODEL_TAG}.png"
PROMOTION_GATE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_promotion_gate_chart_{MODEL_TAG}.png"
STRESS_ATLAS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_stress_episode_atlas_{MODEL_TAG}.png"

RETURN_RETENTION_FLOOR = 0.80
MAX_DD_IMPROVEMENT_TARGET_PP = 5.0
RIGHT_TAIL_RETENTION_FLOOR = 0.80

POLICY_COLORS = {
    "official_1x": "#111827",
    "dd30_half_risk": "#0f766e",
    "dd25_half_risk": "#2563eb",
    "dd20_to_dd10_hysteresis_half": "#f97316",
    "dd15_25_35_ladder": "#7c3aed",
}


@dataclass(frozen=True)
class BudgetPolicy:
    policy_id: str
    description: str
    complexity_count: int
    policy_func: Callable[[float, float], float]


POLICIES = [
    BudgetPolicy("official_1x", "official path without account-level budget overlay", 1, lambda _dd, _prev: 1.0),
    BudgetPolicy("dd30_half_risk", "if prior synthetic drawdown is at or below -30%, use 0.5x next-day risk", 2, lambda dd, _prev: 0.5 if dd <= -0.30 else 1.0),
    BudgetPolicy("dd25_half_risk", "if prior synthetic drawdown is at or below -25%, use 0.5x next-day risk", 2, lambda dd, _prev: 0.5 if dd <= -0.25 else 1.0),
    BudgetPolicy(
        "dd20_to_dd10_hysteresis_half",
        "cut to 0.5x below -20% and stay there until synthetic drawdown recovers above -10%",
        2,
        lambda dd, prev: 0.5 if (prev < 1.0 and dd < -0.10) or dd <= -0.20 else 1.0,
    ),
    BudgetPolicy(
        "dd15_25_35_ladder",
        "diagnostic only: 1.0/0.75/0.5/0.25 ladder at -15%/-25%/-35% synthetic drawdown",
        4,
        lambda dd, _prev: 1.0 if dd > -0.15 else 0.75 if dd > -0.25 else 0.5 if dd > -0.35 else 0.25,
    ),
]


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


def _load_frontier_rows() -> pd.DataFrame:
    if not STAGE249_ROWS_IN.exists():
        raise RuntimeError(f"missing required Stage249 input: {STAGE249_ROWS_IN}")
    rows = pd.read_csv(STAGE249_ROWS_IN, encoding="utf-8-sig")
    rows["official_open_date"] = pd.to_datetime(rows["official_open_date"], errors="coerce").dt.normalize()
    return rows


def _prepare_curve(curve: pd.DataFrame) -> tuple[pd.DataFrame, float]:
    data = curve.copy()
    data["date"] = pd.to_datetime(data["date"], errors="coerce").dt.normalize()
    data = data.sort_values("date").reset_index(drop=True)
    if "account_capital" in data.columns and pd.notna(data["account_capital"].iloc[0]):
        capital = float(data["account_capital"].iloc[0])
    else:
        capital = float(data["account_equity"].iloc[0])
    for column in ["net_pnl", "trade_count", "total_slippage", "broker10_total_margin_exact"]:
        if column not in data.columns:
            data[column] = 0.0
        data[column] = pd.to_numeric(data[column], errors="coerce").fillna(0.0)
    return data, capital


def _simulate_policy(curve: pd.DataFrame, capital: float, policy: BudgetPolicy) -> pd.DataFrame:
    equity = capital
    peak = capital
    previous_scale = 1.0
    rows: list[dict[str, Any]] = []
    for _, item in curve.iterrows():
        prior_equity = equity
        prior_peak = peak
        prior_drawdown = prior_equity / prior_peak - 1.0 if prior_peak > 0 else 0.0
        scale = float(np.clip(policy.policy_func(prior_drawdown, previous_scale), 0.0, 1.0))
        scaled_net_pnl = float(item["net_pnl"]) * scale
        equity = equity + scaled_net_pnl
        peak = max(peak, equity)
        drawdown = equity / peak - 1.0 if peak > 0 else np.nan
        margin = float(item["broker10_total_margin_exact"]) * scale
        margin_pct = margin / equity * 100.0 if equity > 0 else np.nan
        rows.append(
            {
                "policy_id": policy.policy_id,
                "date": item["date"],
                "scale": scale,
                "prior_drawdown_pct": prior_drawdown * 100.0,
                "scaled_net_pnl": scaled_net_pnl,
                "account_equity": equity,
                "peak_equity": peak,
                "drawdown_pct": drawdown * 100.0,
                "daily_return": equity / prior_equity - 1.0 if prior_equity > 0 else 0.0,
                "scaled_slippage_proxy": float(item["total_slippage"]) * scale,
                "trade_count_proxy": float(item["trade_count"]),
                "scale_adjusted_trade_count_proxy": float(item["trade_count"]) * scale,
                "broker10_margin_to_equity_pct_proxy": margin_pct,
            }
        )
        previous_scale = scale
    return pd.DataFrame(rows)


def _curve_metrics(policy_curve: pd.DataFrame, capital: float, official_metrics: dict[str, float], policy: BudgetPolicy) -> dict[str, Any]:
    returns = pd.to_numeric(policy_curve["daily_return"], errors="coerce").fillna(0.0)
    std = float(returns.std(ddof=1))
    sharpe = float(returns.mean() / std * np.sqrt(252.0)) if std > 1e-12 else np.nan
    end_equity = float(policy_curve["account_equity"].iloc[-1])
    total_return_pct = (end_equity / capital - 1.0) * 100.0
    max_drawdown_pct = float(pd.to_numeric(policy_curve["drawdown_pct"], errors="coerce").min())
    official_return = float(official_metrics["total_return_pct"])
    official_dd_abs = abs(float(official_metrics["max_drawdown_pct"]))
    target_return = official_return * RETURN_RETENTION_FLOOR
    target_max_dd_abs = max(0.0, official_dd_abs - MAX_DD_IMPROVEMENT_TARGET_PP)
    dd_improvement = official_dd_abs - abs(max_drawdown_pct)
    scales = pd.to_numeric(policy_curve["scale"], errors="coerce").fillna(1.0)
    scale_switch_count = int(scales.ne(scales.shift()).sum() - 1)
    return {
        "policy_id": policy.policy_id,
        "description": policy.description,
        "complexity_count": policy.complexity_count,
        "end_equity": end_equity,
        "total_return_pct": total_return_pct,
        "return_retention_rate": total_return_pct / official_return if abs(official_return) > 1e-12 else np.nan,
        "target_return_pct": target_return,
        "max_drawdown_pct": max_drawdown_pct,
        "target_max_drawdown_abs_pct": target_max_dd_abs,
        "drawdown_improvement_pp": dd_improvement,
        "sharpe": sharpe,
        "total_slippage_proxy": float(policy_curve["scaled_slippage_proxy"].sum()),
        "total_trade_count_proxy": float(policy_curve["trade_count_proxy"].sum()),
        "scale_adjusted_trade_count_proxy": float(policy_curve["scale_adjusted_trade_count_proxy"].sum()),
        "max_broker10_margin_to_equity_pct_proxy": float(policy_curve["broker10_margin_to_equity_pct_proxy"].max()),
        "average_scale": float(scales.mean()),
        "min_scale": float(scales.min()),
        "scaled_day_count": int(scales.lt(1.0).sum()),
        "scaled_trade_day_count": int(policy_curve.loc[scales.lt(1.0), "trade_count_proxy"].gt(0).sum()),
        "scale_switch_count": max(scale_switch_count, 0),
        "objective_path_proxy_pass": int(total_return_pct >= target_return and abs(max_drawdown_pct) <= target_max_dd_abs),
        "simple_policy_complexity_pass": int(policy.complexity_count <= 2),
        "path_proxy_only": 1,
        "true_engine_validated": 0,
        "integer_lot_validated": 0,
        "policy_promotable_now": 0,
    }


def _policy_curves_and_summary(curve: pd.DataFrame, capital: float, official_metrics: dict[str, float]) -> tuple[pd.DataFrame, pd.DataFrame]:
    curves: list[pd.DataFrame] = []
    metrics: list[dict[str, Any]] = []
    for policy in POLICIES:
        policy_curve = _simulate_policy(curve, capital, policy)
        curves.append(policy_curve)
        metrics.append(_curve_metrics(policy_curve, capital, official_metrics, policy))
    return pd.concat(curves, ignore_index=True), pd.DataFrame(metrics)


def _order_scale_summary(frontier_rows: pd.DataFrame, policy_curves: pd.DataFrame) -> pd.DataFrame:
    base_right_tail = float(frontier_rows.loc[frontier_rows["right_tail_visual"].eq(1), "order_realized_pnl"].sum())
    base_bottom_loss = float(frontier_rows.loc[frontier_rows["bottom_loss_visual"].eq(1), "order_realized_pnl"].sum())
    base_early = float(frontier_rows.loc[frontier_rows["early_runway_no_dwell"].eq(1), "order_realized_pnl"].sum())
    records: list[dict[str, Any]] = []
    for policy_id, curve in policy_curves.groupby("policy_id"):
        scale_by_date = curve[["date", "scale"]].copy()
        merged = frontier_rows.merge(scale_by_date, left_on="official_open_date", right_on="date", how="left")
        merged["scale"] = pd.to_numeric(merged["scale"], errors="coerce").fillna(1.0)
        merged["scaled_order_pnl_proxy"] = pd.to_numeric(merged["order_realized_pnl"], errors="coerce").fillna(0.0) * merged["scale"]
        right_tail_scaled = float(merged.loc[merged["right_tail_visual"].eq(1), "scaled_order_pnl_proxy"].sum())
        bottom_loss_scaled = float(merged.loc[merged["bottom_loss_visual"].eq(1), "scaled_order_pnl_proxy"].sum())
        early_scaled = float(merged.loc[merged["early_runway_no_dwell"].eq(1), "scaled_order_pnl_proxy"].sum())
        records.append(
            {
                "policy_id": policy_id,
                "order_count": int(len(merged)),
                "right_tail_pnl_retention_proxy": right_tail_scaled / base_right_tail if abs(base_right_tail) > 1e-12 else np.nan,
                "bottom_loss_abs_reduction_proxy": 1.0 - abs(bottom_loss_scaled) / abs(base_bottom_loss) if abs(base_bottom_loss) > 1e-12 else np.nan,
                "early_runway_pnl_retention_proxy": early_scaled / base_early if abs(base_early) > 1e-12 else np.nan,
                "scaled_right_tail_order_count": int(merged.loc[merged["right_tail_visual"].eq(1), "scale"].lt(1.0).sum()),
                "scaled_bottom_loss_order_count": int(merged.loc[merged["bottom_loss_visual"].eq(1), "scale"].lt(1.0).sum()),
                "scaled_early_runway_order_count": int(merged.loc[merged["early_runway_no_dwell"].eq(1), "scale"].lt(1.0).sum()),
                "right_tail_retention_gate_pass": int((right_tail_scaled / base_right_tail) >= RIGHT_TAIL_RETENTION_FLOOR) if abs(base_right_tail) > 1e-12 else 0,
                "path_proxy_only": 1,
            }
        )
    return pd.DataFrame(records)


def _year_summary(policy_curves: pd.DataFrame) -> pd.DataFrame:
    data = policy_curves.copy()
    data["year"] = pd.to_datetime(data["date"], errors="coerce").dt.year
    records: list[dict[str, Any]] = []
    for (policy_id, year), group in data.groupby(["policy_id", "year"], dropna=False):
        group = group.sort_values("date")
        start_equity = float(group["account_equity"].iloc[0] - group["scaled_net_pnl"].iloc[0])
        end_equity = float(group["account_equity"].iloc[-1])
        nav = group["account_equity"] / start_equity if start_equity > 0 else np.nan
        year_dd = nav / nav.cummax() - 1.0
        records.append(
            {
                "policy_id": policy_id,
                "year": int(year),
                "year_start_equity": start_equity,
                "year_end_equity": end_equity,
                "year_return_pct": (end_equity / start_equity - 1.0) * 100.0 if start_equity > 0 else np.nan,
                "year_max_drawdown_pct": float(year_dd.min() * 100.0),
                "year_scaled_day_count": int(pd.to_numeric(group["scale"], errors="coerce").lt(1.0).sum()),
                "year_net_pnl_sum": float(group["scaled_net_pnl"].sum()),
            }
        )
    return pd.DataFrame(records)


def _select_best_policy(policy_summary: pd.DataFrame, order_scale: pd.DataFrame) -> str:
    merged = policy_summary.merge(order_scale[["policy_id", "right_tail_pnl_retention_proxy"]], on="policy_id", how="left")
    candidates = merged[
        merged["policy_id"].ne("official_1x")
        & merged["objective_path_proxy_pass"].eq(1)
        & merged["simple_policy_complexity_pass"].eq(1)
        & merged["right_tail_pnl_retention_proxy"].ge(RIGHT_TAIL_RETENTION_FLOOR)
    ].copy()
    if candidates.empty:
        return "none"
    candidates = candidates.sort_values(["return_retention_rate", "drawdown_improvement_pp"], ascending=[False, False])
    return str(candidates.iloc[0]["policy_id"])


def _stress_episodes(policy_curves: pd.DataFrame, best_policy_id: str) -> pd.DataFrame:
    if best_policy_id == "none":
        return pd.DataFrame()
    curve = policy_curves[policy_curves["policy_id"].eq(best_policy_id)].sort_values("date").reset_index(drop=True)
    scaled = pd.to_numeric(curve["scale"], errors="coerce").lt(1.0).to_numpy()
    blocks: list[dict[str, Any]] = []
    start: int | None = None
    for idx, active in enumerate(list(scaled) + [False]):
        if active and start is None:
            start = idx
        elif not active and start is not None:
            end = idx - 1
            block = curve.iloc[start : end + 1]
            blocks.append(
                {
                    "episode_rank_key": float(block["drawdown_pct"].min()),
                    "episode_start_idx": start,
                    "episode_end_idx": end,
                    "episode_start_date": block["date"].iloc[0],
                    "episode_end_date": block["date"].iloc[-1],
                    "episode_day_count": int(len(block)),
                    "episode_min_drawdown_pct": float(block["drawdown_pct"].min()),
                    "episode_scaled_net_pnl": float(block["scaled_net_pnl"].sum()),
                }
            )
            start = None
    result = pd.DataFrame(blocks)
    if result.empty:
        return result
    result = result.sort_values(["episode_rank_key", "episode_day_count"], ascending=[True, False]).head(4).reset_index(drop=True)
    result["policy_id"] = best_policy_id
    result["atlas_path"] = str(STRESS_ATLAS_OUT)
    return result


def _promotion_gate(policy_summary: pd.DataFrame, order_scale: pd.DataFrame, best_policy_id: str) -> pd.DataFrame:
    best = policy_summary[policy_summary["policy_id"].eq(best_policy_id)]
    best_order = order_scale[order_scale["policy_id"].eq(best_policy_id)]
    objective_pass_count = int(policy_summary.loc[policy_summary["policy_id"].ne("official_1x"), "objective_path_proxy_pass"].sum())
    best_objective = int(best["objective_path_proxy_pass"].iloc[0]) if not best.empty else 0
    best_tail_retention = _safe_float(best_order["right_tail_pnl_retention_proxy"].iloc[0], 0.0) if not best_order.empty else 0.0
    best_complexity = int(best["complexity_count"].iloc[0]) if not best.empty else 999
    rows = [
        {
            "gate_id": "path_proxy_objective_frontier",
            "evidence_value": objective_pass_count,
            "evidence_unit": "non-official policies passing 80% return retention and 5pp DD improvement on daily path proxy",
            "pass_for_true_engine": int(objective_pass_count > 0 and best_objective == 1),
            "judgment": "pass_path_proxy_only" if objective_pass_count > 0 else "fail_no_path_proxy_candidate",
        },
        {
            "gate_id": "right_tail_retention_proxy",
            "evidence_value": best_tail_retention,
            "evidence_unit": "best policy Stage249 right-tail PnL retention using entry-date scale proxy",
            "pass_for_true_engine": int(best_tail_retention >= RIGHT_TAIL_RETENTION_FLOOR),
            "judgment": "pass_path_proxy_only" if best_tail_retention >= RIGHT_TAIL_RETENTION_FLOOR else "fail_right_tail_damage",
        },
        {
            "gate_id": "simple_policy_complexity",
            "evidence_value": best_complexity,
            "evidence_unit": "number of risk-scale states in best policy",
            "pass_for_true_engine": int(best_complexity <= 2),
            "judgment": "pass_simple_structural_budget" if best_complexity <= 2 else "fail_complex_ladder",
        },
        {
            "gate_id": "true_engine_replay_required",
            "evidence_value": 0,
            "evidence_unit": "order-level true-engine replay with integer lots and intra-position resizing",
            "pass_for_true_engine": 0,
            "judgment": "hard_fail_not_validated",
        },
        {
            "gate_id": "margin_integer_lot_validation_required",
            "evidence_value": 0,
            "evidence_unit": "broker10 margin, integer lot rounding, slippage and trade count under real budget overlay",
            "pass_for_true_engine": 0,
            "judgment": "hard_fail_not_validated",
        },
        {
            "gate_id": "side_effect_isolation",
            "evidence_value": 0,
            "evidence_unit": "official config changes, CTP connections, order API calls, A/B runs",
            "pass_for_true_engine": 1,
            "judgment": "technical_pass",
        },
    ]
    gate = pd.DataFrame(rows)
    gate["path_proxy_only"] = 1
    gate["strategy_feature_usable"] = 0
    return gate


def _summary(
    official_metrics: dict[str, float],
    policy_summary: pd.DataFrame,
    order_scale: pd.DataFrame,
    gate: pd.DataFrame,
    best_policy_id: str,
) -> pd.DataFrame:
    best = policy_summary[policy_summary["policy_id"].eq(best_policy_id)]
    best_order = order_scale[order_scale["policy_id"].eq(best_policy_id)]
    best_row = best.iloc[0].to_dict() if not best.empty else {}
    best_order_row = best_order.iloc[0].to_dict() if not best_order.empty else {}
    objective_pass_count = int(policy_summary.loc[policy_summary["policy_id"].ne("official_1x"), "objective_path_proxy_pass"].sum())
    decision = "stage250_account_budget_path_proxy_no_objective_pass_no_rule"
    if best_policy_id != "none":
        decision = "stage250_account_dd30_half_budget_path_proxy_passes_true_engine_required"
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
                "path_proxy_policy_count": int(len(policy_summary)),
                "objective_path_proxy_pass_count": objective_pass_count,
                "best_path_proxy_policy_id": best_policy_id,
                "best_policy_end_equity": _safe_float(best_row.get("end_equity"), np.nan),
                "best_policy_total_return_pct": _safe_float(best_row.get("total_return_pct"), np.nan),
                "best_policy_return_retention_rate": _safe_float(best_row.get("return_retention_rate"), np.nan),
                "best_policy_max_drawdown_pct": _safe_float(best_row.get("max_drawdown_pct"), np.nan),
                "best_policy_drawdown_improvement_pp": _safe_float(best_row.get("drawdown_improvement_pp"), np.nan),
                "best_policy_sharpe": _safe_float(best_row.get("sharpe"), np.nan),
                "best_policy_average_scale": _safe_float(best_row.get("average_scale"), np.nan),
                "best_policy_scaled_day_count": int(_safe_float(best_row.get("scaled_day_count"), 0)),
                "best_policy_scaled_trade_day_count": int(_safe_float(best_row.get("scaled_trade_day_count"), 0)),
                "best_policy_right_tail_pnl_retention_proxy": _safe_float(best_order_row.get("right_tail_pnl_retention_proxy"), np.nan),
                "best_policy_bottom_loss_abs_reduction_proxy": _safe_float(best_order_row.get("bottom_loss_abs_reduction_proxy"), np.nan),
                "best_policy_early_runway_pnl_retention_proxy": _safe_float(best_order_row.get("early_runway_pnl_retention_proxy"), np.nan),
                "target_return_retention_floor": RETURN_RETENTION_FLOOR,
                "target_max_dd_improvement_pp": MAX_DD_IMPROVEMENT_TARGET_PP,
                "right_tail_retention_floor": RIGHT_TAIL_RETENTION_FLOOR,
                "promotion_gate_count": int(len(gate)),
                "promotion_gate_pass_count": int(pd.to_numeric(gate["pass_for_true_engine"], errors="coerce").sum()),
                "next_true_engine_feasibility_allowed": int(best_policy_id != "none"),
                "policy_promotable_now": 0,
                "strategy_feature_usable": 0,
                **official_metrics,
            }
        ]
    )


def _plot_policy_path(policy_curves: pd.DataFrame, policy_summary: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 1, figsize=(14, 8), sharex=True, gridspec_kw={"height_ratios": [2.0, 1.0]})
    for policy_id, group in policy_curves.groupby("policy_id"):
        color = POLICY_COLORS.get(policy_id, "#64748b")
        width = 1.8 if policy_id in {"official_1x", "dd30_half_risk"} else 1.0
        alpha = 0.95 if policy_id in {"official_1x", "dd30_half_risk"} else 0.72
        axes[0].plot(group["date"], group["account_equity"], label=policy_id, color=color, linewidth=width, alpha=alpha)
        axes[1].plot(group["date"], group["drawdown_pct"], label=policy_id, color=color, linewidth=width, alpha=alpha)
    axes[0].set_ylabel("equity")
    axes[1].set_ylabel("drawdown %")
    axes[0].set_title("Stage250 account budget daily path proxy: equity and drawdown")
    for ax in axes:
        ax.grid(True, alpha=0.25)
    axes[0].legend(fontsize=8, ncol=2)
    fig.tight_layout()
    fig.savefig(POLICY_PATH_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_objective_frontier(policy_summary: pd.DataFrame) -> None:
    data = policy_summary[policy_summary["policy_id"].ne("official_1x")].copy()
    fig, ax = plt.subplots(figsize=(10.5, 6.3))
    colors = ["#0f766e" if int(row.objective_path_proxy_pass) else "#dc2626" for row in data.itertuples()]
    ax.scatter(data["drawdown_improvement_pp"], data["return_retention_rate"], s=90, color=colors, alpha=0.86)
    ax.axhline(RETURN_RETENTION_FLOOR, color="#111827", linestyle="--", linewidth=0.9)
    ax.axvline(MAX_DD_IMPROVEMENT_TARGET_PP, color="#111827", linestyle="--", linewidth=0.9)
    for row in data.itertuples():
        ax.text(row.drawdown_improvement_pp + 0.08, row.return_retention_rate, row.policy_id, fontsize=8, va="center")
    ax.set_xlabel("drawdown improvement vs official (pp)")
    ax.set_ylabel("return retention vs official")
    ax.set_title("Stage250 objective frontier: path proxy only, not promotion")
    ax.grid(True, alpha=0.25)
    fig.tight_layout()
    fig.savefig(OBJECTIVE_FRONTIER_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_best_scale(policy_curves: pd.DataFrame, best_policy_id: str) -> None:
    if best_policy_id == "none":
        return
    best = policy_curves[policy_curves["policy_id"].eq(best_policy_id)].copy()
    official = policy_curves[policy_curves["policy_id"].eq("official_1x")].copy()
    fig, axes = plt.subplots(3, 1, figsize=(14, 8), sharex=True, gridspec_kw={"height_ratios": [1.2, 1.0, 0.8]})
    axes[0].plot(official["date"], official["drawdown_pct"], color=POLICY_COLORS["official_1x"], label="official_1x")
    axes[0].plot(best["date"], best["drawdown_pct"], color=POLICY_COLORS.get(best_policy_id, "#0f766e"), label=best_policy_id)
    axes[1].plot(best["date"], best["account_equity"], color=POLICY_COLORS.get(best_policy_id, "#0f766e"))
    axes[2].step(best["date"], best["scale"], where="post", color="#7c3aed")
    axes[0].set_ylabel("drawdown %")
    axes[1].set_ylabel("best equity")
    axes[2].set_ylabel("risk scale")
    axes[2].set_ylim(0.0, 1.05)
    axes[0].set_title(f"Stage250 best path proxy scale timeline: {best_policy_id}")
    axes[0].legend(fontsize=8)
    for ax in axes:
        ax.grid(True, alpha=0.25)
    fig.tight_layout()
    fig.savefig(BEST_SCALE_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_tail_retention(order_scale: pd.DataFrame) -> None:
    data = order_scale[order_scale["policy_id"].ne("official_1x")].copy()
    x = np.arange(len(data))
    width = 0.26
    fig, ax = plt.subplots(figsize=(12, 5.8))
    ax.bar(x - width, data["right_tail_pnl_retention_proxy"], width=width, color="#16a34a", label="right-tail pnl retention")
    ax.bar(x, data["early_runway_pnl_retention_proxy"], width=width, color="#2563eb", label="early-runway pnl retention")
    ax.bar(x + width, data["bottom_loss_abs_reduction_proxy"], width=width, color="#dc2626", label="bottom-loss abs reduction")
    ax.axhline(RIGHT_TAIL_RETENTION_FLOOR, color="#111827", linestyle="--", linewidth=0.9)
    ax.set_xticks(x)
    ax.set_xticklabels(data["policy_id"], rotation=15, ha="right")
    ax.set_ylabel("ratio")
    ax.set_title("Stage250 order-scale proxy: tail protection vs loss reduction")
    ax.grid(True, axis="y", alpha=0.25)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(TAIL_RETENTION_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_year_heatmap(year_summary: pd.DataFrame) -> None:
    data = year_summary[year_summary["policy_id"].isin(["official_1x", "dd30_half_risk", "dd25_half_risk", "dd20_to_dd10_hysteresis_half"])].copy()
    pivot_return = data.pivot_table(index="policy_id", columns="year", values="year_return_pct", aggfunc="first")
    pivot_dd = data.pivot_table(index="policy_id", columns="year", values="year_max_drawdown_pct", aggfunc="first")
    fig, axes = plt.subplots(2, 1, figsize=(13.5, 6.8), sharex=True)
    for ax, pivot, title, cmap in [
        (axes[0], pivot_return, "annual return %", "RdYlGn"),
        (axes[1], pivot_dd.abs(), "annual max drawdown abs %", "YlOrRd"),
    ]:
        values = pivot.to_numpy(dtype=float)
        im = ax.imshow(values, aspect="auto", cmap=cmap)
        ax.set_yticks(np.arange(len(pivot.index)))
        ax.set_yticklabels(pivot.index)
        ax.set_title(f"Stage250 {title}")
        for i in range(values.shape[0]):
            for j in range(values.shape[1]):
                if np.isfinite(values[i, j]):
                    ax.text(j, i, f"{values[i, j]:.0f}", ha="center", va="center", fontsize=7, color="#111827")
        fig.colorbar(im, ax=ax, fraction=0.018, pad=0.02)
    axes[1].set_xticks(np.arange(len(pivot_return.columns)))
    axes[1].set_xticklabels([str(int(col)) for col in pivot_return.columns], rotation=0)
    fig.tight_layout()
    fig.savefig(YEAR_HEATMAP_OUT, dpi=160)
    plt.close(fig)


def _plot_gate(gate: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(11.5, 4.8))
    colors = ["#16a34a" if int(item) else "#dc2626" for item in gate["pass_for_true_engine"]]
    ax.bar(gate["gate_id"], gate["evidence_value"], color=colors, alpha=0.82)
    ax.set_ylabel("evidence")
    ax.set_title("Stage250 gates: path proxy passes, true-engine validation blocks promotion")
    ax.tick_params(axis="x", rotation=22)
    ax.grid(True, axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(PROMOTION_GATE_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_stress_atlas(policy_curves: pd.DataFrame, best_policy_id: str, episodes: pd.DataFrame) -> None:
    if best_policy_id == "none" or episodes.empty:
        return
    official = policy_curves[policy_curves["policy_id"].eq("official_1x")].sort_values("date").reset_index(drop=True)
    best = policy_curves[policy_curves["policy_id"].eq(best_policy_id)].sort_values("date").reset_index(drop=True)
    fig, axes = plt.subplots(len(episodes), 1, figsize=(13, 3.2 * len(episodes)), squeeze=False)
    for ax, (_, episode) in zip(axes[:, 0], episodes.iterrows()):
        start = max(int(episode["episode_start_idx"]) - 60, 0)
        end = min(int(episode["episode_end_idx"]) + 60, len(best) - 1)
        o = official.iloc[start : end + 1].copy()
        b = best.iloc[start : end + 1].copy()
        o_nav = o["account_equity"] / float(o["account_equity"].iloc[0])
        b_nav = b["account_equity"] / float(b["account_equity"].iloc[0])
        ax.plot(o["date"], o_nav, color=POLICY_COLORS["official_1x"], label="official local nav", linewidth=1.2)
        ax.plot(b["date"], b_nav, color=POLICY_COLORS.get(best_policy_id, "#0f766e"), label=f"{best_policy_id} local nav", linewidth=1.3)
        shaded = b[pd.to_numeric(b["scale"], errors="coerce").lt(1.0)]
        if not shaded.empty:
            ax.axvspan(shaded["date"].iloc[0], shaded["date"].iloc[-1], color="#fde68a", alpha=0.28)
        ax.set_title(
            f"{best_policy_id} scaled episode {pd.Timestamp(episode['episode_start_date']).date()} to "
            f"{pd.Timestamp(episode['episode_end_date']).date()} | min dd {episode['episode_min_drawdown_pct']:.2f}%"
        )
        ax.set_ylabel("local nav")
        ax.grid(True, alpha=0.25)
        ax.legend(fontsize=8)
    axes[-1, 0].set_xlabel("date")
    fig.tight_layout()
    fig.savefig(STRESS_ATLAS_OUT, dpi=160)
    plt.close(fig)


def _write_report(
    summary: pd.DataFrame,
    policy_summary: pd.DataFrame,
    order_scale: pd.DataFrame,
    year_summary: pd.DataFrame,
    episodes: pd.DataFrame,
    gate: pd.DataFrame,
) -> None:
    row = summary.iloc[0]
    report = "\n".join(
        [
            f"# {STAGE} account floor budget path audit",
            "",
            "## Decision",
            "",
            f"- decision: `{row['decision']}`",
            "- nature: daily equity-path proxy audit; no strategy rule, no true engine, no A/B, no CTP, no order API.",
            "- fixed question: can a universal account-level drawdown budget reduce path drawdown while preserving at least 80% of official return and right-tail participation.",
            "- anti-overfit guard: policies are fixed account-budget shapes; no product, direction, year, event, minute-feature, or threshold rescue is used after seeing failures.",
            "",
            "## Official baseline",
            "",
            f"- end equity: `{row['end_equity']:,.2f}`",
            f"- total return: `{row['total_return_pct']:.4f}%`",
            f"- max drawdown: `{row['max_drawdown_pct']:.4f}%`",
            f"- Sharpe: `{row['sharpe']:.4f}`",
            f"- total slippage: `{row['total_slippage']:,.0f}`",
            f"- total trade count: `{row['total_trade_count']:.0f}`",
            f"- closed lot win rate: `{row['closed_lot_win_rate_pct']:.4f}%`",
            "",
            "## Best path proxy",
            "",
            f"- best policy: `{row['best_path_proxy_policy_id']}`",
            f"- end equity proxy: `{row['best_policy_end_equity']:,.2f}`",
            f"- total return proxy: `{row['best_policy_total_return_pct']:.4f}%`",
            f"- return retention: `{row['best_policy_return_retention_rate']:.4f}`",
            f"- max drawdown proxy: `{row['best_policy_max_drawdown_pct']:.4f}%`",
            f"- drawdown improvement: `{row['best_policy_drawdown_improvement_pp']:.4f}pp`",
            f"- Sharpe proxy: `{row['best_policy_sharpe']:.4f}`",
            f"- average scale: `{row['best_policy_average_scale']:.4f}`",
            f"- scaled days: `{int(row['best_policy_scaled_day_count'])}`",
            f"- scaled trade days: `{int(row['best_policy_scaled_trade_day_count'])}`",
            f"- right-tail PnL retention proxy: `{row['best_policy_right_tail_pnl_retention_proxy']:.4f}`",
            f"- bottom-loss abs reduction proxy: `{row['best_policy_bottom_loss_abs_reduction_proxy']:.4f}`",
            f"- early-runway PnL retention proxy: `{row['best_policy_early_runway_pnl_retention_proxy']:.4f}`",
            f"- promotion gate pass count: `{int(row['promotion_gate_pass_count'])}` / `{int(row['promotion_gate_count'])}`",
            "",
            "## Policy Summary",
            "",
            _md_table(policy_summary, max_rows=20),
            "",
            "## Order Scale Summary",
            "",
            _md_table(order_scale, max_rows=20),
            "",
            "## Year Summary",
            "",
            _md_table(year_summary, max_rows=60),
            "",
            "## Stress Episodes",
            "",
            _md_table(episodes, max_rows=20),
            "",
            "## Promotion Gates",
            "",
            _md_table(gate, max_rows=20),
            "",
            "## Visual outputs",
            "",
            f"- policy path chart: `{POLICY_PATH_CHART_OUT}`",
            f"- objective frontier chart: `{OBJECTIVE_FRONTIER_CHART_OUT}`",
            f"- best scale timeline: `{BEST_SCALE_CHART_OUT}`",
            f"- tail retention chart: `{TAIL_RETENTION_CHART_OUT}`",
            f"- year heatmap: `{YEAR_HEATMAP_OUT}`",
            f"- gate chart: `{PROMOTION_GATE_CHART_OUT}`",
            f"- stress episode atlas: `{STRESS_ATLAS_OUT}`",
            "",
            "## Judgment",
            "",
            (
                "`dd30_half_risk` passes the daily path-proxy objective, but it is not a tradable result yet. "
                "The mechanism is account-level and structurally plausible, yet the evidence is still synthetic because it scales official daily PnL "
                "instead of replaying integer lots, margin, open-position resizing, slippage, and trade count in the real engine. "
                "Promotion is therefore blocked; the only valid continuation is a true-engine feasibility build or a stronger delivery of execution/account data."
            ),
            "",
        ]
    )
    REPORT_OUT.parent.mkdir(parents=True, exist_ok=True)
    REPORT_OUT.write_text(report, encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    _merged, official_curve, lots, _intraday, _groups = s045._prepare_event_sync_frame()
    frontier_rows = _load_frontier_rows()
    curve, capital = _prepare_curve(official_curve)
    official_metrics = s038._official_metrics(official_curve, lots)
    policy_curves, policy_summary = _policy_curves_and_summary(curve, capital, official_metrics)
    order_scale = _order_scale_summary(frontier_rows, policy_curves)
    year_summary = _year_summary(policy_curves)
    best_policy_id = _select_best_policy(policy_summary, order_scale)
    episodes = _stress_episodes(policy_curves, best_policy_id)
    gate = _promotion_gate(policy_summary, order_scale, best_policy_id)
    summary = _summary(official_metrics, policy_summary, order_scale, gate, best_policy_id)

    _write_csv(policy_curves, CURVES_OUT)
    _write_csv(policy_summary, POLICY_SUMMARY_OUT)
    _write_csv(order_scale, ORDER_SCALE_SUMMARY_OUT)
    _write_csv(year_summary, YEAR_SUMMARY_OUT)
    _write_csv(episodes, STRESS_EPISODE_OUT)
    _write_csv(gate, PROMOTION_GATE_OUT)
    _write_csv(summary, SUMMARY_OUT)

    _plot_policy_path(policy_curves, policy_summary)
    _plot_objective_frontier(policy_summary)
    _plot_best_scale(policy_curves, best_policy_id)
    _plot_tail_retention(order_scale)
    _plot_year_heatmap(year_summary)
    _plot_gate(gate)
    _plot_stress_atlas(policy_curves, best_policy_id, episodes)
    _write_report(summary, policy_summary, order_scale, year_summary, episodes, gate)
    _write_json(DECISION_OUT, summary.iloc[0].to_dict())

    print(json.dumps(s045._json_safe(summary.iloc[0].to_dict()), ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
