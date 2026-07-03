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
LINE_ID = "futures_trend_rebuilt_c9_15w_v2_optimization"
UPSTREAM_LINE_ID = "futures_trend_rebuilt_c9_15w_optimization"
STAGE = "Stage014"
MODEL_TAG = "stage014_integer_add_risk_feasibility_audit_v1"
OUTPUT_PREFIX = "rebuilt_c9_v2_stage014_integer_add_risk_feasibility_audit"
ADD_RISK_FRACTION = 0.25
CAPITAL = 150000.0
EPS = 1e-9

LINE_DIR = PROJECT_DIR / "research" / "lines" / LINE_ID
UPSTREAM_LINE_DIR = PROJECT_DIR / "research" / "lines" / UPSTREAM_LINE_ID
UPSTREAM_TOOLS_DIR = UPSTREAM_LINE_DIR / "tools"
if str(UPSTREAM_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(UPSTREAM_TOOLS_DIR))

TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import stage009_dense_start_goal_audit as s009_goal
import stage009_meta_label_entry_quality_audit as s009_quality


OUTPUT_DIR = LINE_DIR / "outputs" / "stage014_integer_add_risk_feasibility_audit"

STAGE013_OUTPUT_DIR = LINE_DIR / "outputs" / "stage013_guarded_quality_add_risk_proxy"
STAGE013_PREFIX = "rebuilt_c9_v2_stage013_guarded_quality_add_risk_proxy"
STAGE013_TAG = "stage013_guarded_quality_add_risk_proxy_v1"
STAGE013_LOT_DELTAS_PATH = STAGE013_OUTPUT_DIR / f"{STAGE013_PREFIX}_lot_deltas_{STAGE013_TAG}.csv.gz"

STAGE013_BASE_OUTPUT_DIR = UPSTREAM_LINE_DIR / "outputs" / "stage013_account_state_pilot_gate_engine"
STAGE013_BASE_PREFIX = "rebuilt_c9_stage013_account_state_pilot_gate_engine"
STAGE013_BASE_TAG = "stage013_account_state_pilot_gate_engine_v1"
STAGE013_CURVES_PATH = STAGE013_BASE_OUTPUT_DIR / f"{STAGE013_BASE_PREFIX}_curves_{STAGE013_BASE_TAG}.csv"

LOT_DELTAS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_lot_deltas_{MODEL_TAG}.csv.gz"
CURVES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv"
SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
AB_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_ab_summary_{MODEL_TAG}.csv"
GOAL_AGGREGATE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_goal_aggregate_{MODEL_TAG}.csv"
GOAL_TO_FINAL_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_goal_to_final_windows_{MODEL_TAG}.csv"
GOAL_FIXED_HORIZON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_goal_fixed_horizon_windows_{MODEL_TAG}.csv"
GOAL_WORST_WINDOWS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_goal_worst_windows_{MODEL_TAG}.csv"
RETENTION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_retention_vs_stage013_{MODEL_TAG}.csv"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_absolute_equity_chart_{MODEL_TAG}.png"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
STAGE_RECORD_PATH = LINE_DIR / "stages" / "20260702_0453_stage014_integer_add_risk_feasibility_audit.md"


VARIANT_COLUMNS = {
    "stage013_engine": "account_equity",
    "stage013_guarded_fractional_add_risk_proxy": "stage014_fractional_account_equity",
    "stage014_floor_integer_add_risk_proxy": "stage014_floor_account_equity",
    "stage014_ceil_integer_add_risk_proxy": "stage014_ceil_account_equity",
}


def _json_safe(value: Any) -> Any:
    return s009_quality._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s009_quality._md_table(frame, max_rows=max_rows or 20)


def _read_csv(path: Path, **kwargs: Any) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path, encoding="utf-8-sig", **kwargs)


def _numeric(frame: pd.DataFrame, column: str, default: float = np.nan) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=float)
    return pd.to_numeric(frame[column], errors="coerce")


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


def compute_integer_add_risk_lot_deltas(lots: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    result = lots.copy()
    selected_volume = _numeric(result, "selected_volume", 0.0).fillna(0.0)
    realized_pnl = _numeric(result, "realized_pnl", 0.0).fillna(0.0)
    desired_extra_lots = selected_volume * ADD_RISK_FRACTION
    floor_extra_lots = np.floor(desired_extra_lots + EPS).astype("int64")
    ceil_extra_lots = np.where(selected_volume.gt(0.0), np.ceil(desired_extra_lots - EPS), 0).astype("int64")
    with np.errstate(divide="ignore", invalid="ignore"):
        floor_fraction = np.where(selected_volume.gt(0.0), floor_extra_lots / selected_volume, 0.0)
        ceil_fraction = np.where(selected_volume.gt(0.0), ceil_extra_lots / selected_volume, 0.0)

    result["selected_volume"] = selected_volume
    result["realized_pnl"] = realized_pnl
    result["stage014_continuous_add_risk_fraction"] = ADD_RISK_FRACTION
    result["stage014_desired_extra_lots"] = desired_extra_lots
    result["stage014_floor_extra_lots"] = floor_extra_lots
    result["stage014_ceil_extra_lots"] = ceil_extra_lots
    result["stage014_floor_add_fraction"] = floor_fraction
    result["stage014_ceil_add_fraction"] = ceil_fraction
    result["stage014_fractional_proxy_delta_pnl"] = realized_pnl * ADD_RISK_FRACTION
    result["stage014_floor_proxy_delta_pnl"] = realized_pnl * result["stage014_floor_add_fraction"]
    result["stage014_ceil_proxy_delta_pnl"] = realized_pnl * result["stage014_ceil_add_fraction"]

    stage013_proxy = _numeric(result, "stage013_proxy_delta_pnl", np.nan)
    stage013_delta_diff = (stage013_proxy - result["stage014_fractional_proxy_delta_pnl"]).abs()
    floor_delta = float(result["stage014_floor_proxy_delta_pnl"].sum())
    ceil_delta = float(result["stage014_ceil_proxy_delta_pnl"].sum())
    fractional_delta = float(result["stage014_fractional_proxy_delta_pnl"].sum())
    floor_zero_mask = selected_volume.gt(0.0) & pd.Series(floor_extra_lots, index=result.index).eq(0)
    integer_volume_mismatch = (selected_volume - selected_volume.round()).abs().gt(EPS)
    audit = {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "continuous_add_risk_fraction": ADD_RISK_FRACTION,
        "input_lot_count": int(len(result)),
        "integer_volume_mismatch_count": int(integer_volume_mismatch.sum()),
        "floor_zero_extra_lot_count": int(floor_zero_mask.sum()),
        "floor_zero_extra_lot_realized_pnl": float(realized_pnl.loc[floor_zero_mask].sum()),
        "floor_zero_extra_lot_fractional_delta_pnl": float(
            result.loc[floor_zero_mask, "stage014_fractional_proxy_delta_pnl"].sum()
        ),
        "fractional_proxy_delta_pnl": fractional_delta,
        "floor_integer_proxy_delta_pnl": floor_delta,
        "ceil_integer_proxy_delta_pnl": ceil_delta,
        "floor_realization_ratio_vs_fractional": float(floor_delta / fractional_delta) if abs(fractional_delta) > EPS else np.nan,
        "ceil_realization_ratio_vs_fractional": float(ceil_delta / fractional_delta) if abs(fractional_delta) > EPS else np.nan,
        "stage013_delta_recompute_max_abs_diff": float(stage013_delta_diff.dropna().max()) if stage013_delta_diff.notna().any() else np.nan,
        "floor_extra_lot_sum": int(pd.Series(floor_extra_lots).sum()),
        "ceil_extra_lot_sum": int(pd.Series(ceil_extra_lots).sum()),
    }
    return result.reset_index(drop=True), audit


def build_integer_proxy_curves(base_curves: pd.DataFrame, lot_deltas: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    curves = base_curves.copy()
    curves["date"] = pd.to_datetime(curves["date"], errors="coerce").dt.normalize()
    curves["requested_start_month"] = curves["requested_start_month"].astype(str)
    curves["account_equity"] = pd.to_numeric(curves["account_equity"], errors="coerce")
    delta_columns = [
        "stage014_fractional_proxy_delta_pnl",
        "stage014_floor_proxy_delta_pnl",
        "stage014_ceil_proxy_delta_pnl",
    ]
    lot_deltas = lot_deltas.copy()
    for column in delta_columns:
        if column not in lot_deltas.columns:
            lot_deltas[column] = 0.0
    if lot_deltas.empty:
        daily_delta = pd.DataFrame(columns=["requested_start_month", "exit_date", *delta_columns])
    else:
        daily_delta = (
            lot_deltas.groupby(["requested_start_month", "exit_date"], dropna=False)[delta_columns]
            .sum()
            .reset_index()
        )
    merged = curves.merge(
        daily_delta.rename(columns={"exit_date": "date"}),
        on=["requested_start_month", "date"],
        how="left",
    )
    for column in delta_columns:
        merged[column] = pd.to_numeric(merged[column], errors="coerce").fillna(0.0)
    frames: list[pd.DataFrame] = []
    for _, group in merged.groupby("requested_start_month", sort=True):
        g = group.sort_values("date").copy()
        g["stage014_fractional_cum_delta"] = g["stage014_fractional_proxy_delta_pnl"].cumsum()
        g["stage014_floor_cum_delta"] = g["stage014_floor_proxy_delta_pnl"].cumsum()
        g["stage014_ceil_cum_delta"] = g["stage014_ceil_proxy_delta_pnl"].cumsum()
        g["stage014_fractional_account_equity"] = g["account_equity"] + g["stage014_fractional_cum_delta"]
        g["stage014_floor_account_equity"] = g["account_equity"] + g["stage014_floor_cum_delta"]
        g["stage014_ceil_account_equity"] = g["account_equity"] + g["stage014_ceil_cum_delta"]
        for prefix in ["fractional", "floor", "ceil"]:
            equity_column = f"stage014_{prefix}_account_equity"
            g[f"stage014_{prefix}_nav"] = g[equity_column] / CAPITAL
            g[f"stage014_{prefix}_drawdown_pct"] = _drawdown_pct(g[equity_column])
        frames.append(g)
    proxy = pd.concat(frames, ignore_index=True, sort=False) if frames else pd.DataFrame()
    curve_dates = set(zip(curves["requested_start_month"].astype(str), curves["date"]))
    unmatched = 0
    for row in daily_delta.to_dict("records"):
        if (str(row["requested_start_month"]), row["exit_date"]) not in curve_dates:
            unmatched += 1
    return proxy, unmatched


def _summarize_curve(curve: pd.DataFrame, equity_column: str, variant: str) -> dict[str, Any]:
    data = curve.sort_values("date").copy()
    equity = pd.to_numeric(data[equity_column], errors="coerce")
    return {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "variant": variant,
        "requested_start_month": str(data["requested_start_month"].iloc[0]),
        "actual_start": pd.Timestamp(data["date"].iloc[0]).date().isoformat(),
        "actual_end": pd.Timestamp(data["date"].iloc[-1]).date().isoformat(),
        "trading_days": int(len(data)),
        "end_equity": float(equity.iloc[-1]),
        "total_return_pct": float((equity.iloc[-1] / CAPITAL - 1.0) * 100.0),
        "max_dd_pct": float(_drawdown_pct(equity).min()),
        "sharpe": _sharpe_from_equity(equity),
    }


def _summary(proxy_curves: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for _, group in proxy_curves.groupby("requested_start_month", sort=True):
        for variant, column in VARIANT_COLUMNS.items():
            rows.append(_summarize_curve(group, column, variant))
    return pd.DataFrame(rows).sort_values(["variant", "requested_start_month"]).reset_index(drop=True)


def _wide_summary(summary: pd.DataFrame) -> pd.DataFrame:
    pivots = []
    for metric in ["end_equity", "total_return_pct", "max_dd_pct", "sharpe"]:
        pivot = summary.pivot(index="requested_start_month", columns="variant", values=metric)
        pivot.columns = [f"{metric}_{column}" for column in pivot.columns]
        pivots.append(pivot)
    wide = pd.concat(pivots, axis=1).reset_index()
    for variant in [
        "stage013_guarded_fractional_add_risk_proxy",
        "stage014_floor_integer_add_risk_proxy",
        "stage014_ceil_integer_add_risk_proxy",
    ]:
        wide[f"return_delta_pp_{variant}_vs_stage013_engine"] = (
            wide[f"total_return_pct_{variant}"] - wide["total_return_pct_stage013_engine"]
        )
        wide[f"maxdd_delta_pp_{variant}_vs_stage013_engine"] = (
            wide[f"max_dd_pct_{variant}"] - wide["max_dd_pct_stage013_engine"]
        )
    return wide.sort_values("requested_start_month").reset_index(drop=True)


def _goal_audit(proxy_curves: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    parts = []
    for variant, column in VARIANT_COLUMNS.items():
        frame = proxy_curves[["requested_start_month", "date", column]].copy()
        frame.rename(columns={column: "equity"}, inplace=True)
        frame["variant"] = variant
        parts.append(frame)
    curves = pd.concat(parts, ignore_index=True, sort=False)
    curves["date"] = pd.to_datetime(curves["date"], errors="coerce").dt.normalize()
    curves["equity"] = pd.to_numeric(curves["equity"], errors="coerce")
    curves = curves.dropna(subset=["date", "equity"]).sort_values(["variant", "requested_start_month", "date"])
    return s009_goal._run_audit(curves)


def _retention(summary: pd.DataFrame) -> pd.DataFrame:
    wide = _wide_summary(summary)
    base = "total_return_pct_stage013_engine"
    for variant in [
        "stage013_guarded_fractional_add_risk_proxy",
        "stage014_floor_integer_add_risk_proxy",
        "stage014_ceil_integer_add_risk_proxy",
    ]:
        candidate = f"total_return_pct_{variant}"
        wide[f"{variant}_return_ratio_vs_stage013"] = (
            pd.to_numeric(wide[candidate], errors="coerce")
            / pd.to_numeric(wide[base], errors="coerce").replace(0.0, np.nan)
        )
        wide[f"passes_80pct_retention_{variant}_vs_stage013"] = (
            pd.to_numeric(wide[candidate], errors="coerce")
            >= pd.to_numeric(wide[base], errors="coerce") * 0.8
        ).astype("int64")
    return wide


def _strict_metrics(aggregate: pd.DataFrame, variant: str) -> dict[str, Any]:
    all_gt1y = aggregate[aggregate["variant"].eq(variant) & aggregate["audit_scope"].eq("all_trading_end_dates_gt_1y")]
    final = aggregate[aggregate["variant"].eq(variant) & aggregate["audit_scope"].eq("start_to_2026_06_30_only")]
    return {
        f"{variant}_all_gt1y_window_count": int(all_gt1y["window_count"].sum()) if not all_gt1y.empty else 0,
        f"{variant}_all_gt1y_negative_count": int(all_gt1y["negative_count"].sum()) if not all_gt1y.empty else 0,
        f"{variant}_all_gt1y_min_return_pct": float(all_gt1y["min_return_pct"].min()) if not all_gt1y.empty else np.nan,
        f"{variant}_to_final_negative_count": int(final["negative_count"].sum()) if not final.empty else 0,
        f"{variant}_to_final_min_return_pct": float(final["min_return_pct"].min()) if not final.empty else np.nan,
    }


def _decision(
    summary: pd.DataFrame,
    aggregate: pd.DataFrame,
    retention: pd.DataFrame,
    audit: dict[str, Any],
    unmatched_delta_dates: int,
) -> dict[str, Any]:
    wide = _wide_summary(summary)
    variants = [
        "stage013_engine",
        "stage013_guarded_fractional_add_risk_proxy",
        "stage014_floor_integer_add_risk_proxy",
        "stage014_ceil_integer_add_risk_proxy",
    ]
    metrics: dict[str, Any] = {}
    for variant in variants:
        metrics.update(_strict_metrics(aggregate, variant))
    floor_variant = "stage014_floor_integer_add_risk_proxy"
    ceil_variant = "stage014_ceil_integer_add_risk_proxy"
    fractional_variant = "stage013_guarded_fractional_add_risk_proxy"
    floor_neg = int(metrics[f"{floor_variant}_all_gt1y_negative_count"])
    ceil_neg = int(metrics[f"{ceil_variant}_all_gt1y_negative_count"])
    fractional_neg = int(metrics[f"{fractional_variant}_all_gt1y_negative_count"])
    base_neg = int(metrics["stage013_engine_all_gt1y_negative_count"])
    floor_retention = int(retention[f"passes_80pct_retention_{floor_variant}_vs_stage013"].sum())
    ceil_retention = int(retention[f"passes_80pct_retention_{ceil_variant}_vs_stage013"].sum())
    rows = int(len(retention))
    if floor_neg <= fractional_neg and floor_retention == rows:
        decision = "stage014_floor_integer_feasible_needs_true_engine"
        reason = "floor 整数手可以保留连续 proxy 的主要路径改善且满足 80% 收益保留，下一步才值得写真实引擎。"
    elif floor_neg < base_neg and floor_retention == rows:
        decision = "stage014_floor_integer_partially_feasible_but_under_realizes_fractional_proxy"
        reason = "floor 整数手改善 base，但未完全复现连续 guarded proxy；下一步需评估是否值得真实引擎。"
    elif ceil_neg <= fractional_neg and ceil_retention == rows:
        decision = "stage014_ceil_integer_feasible_but_over_sizes_small_lots"
        reason = "ceil 整数手能复现或超过连续 proxy，但小手数会从 +25% 变成 +50% 到 +100%，不能直接当保守实盘候选。"
    else:
        decision = "stage014_integer_rounding_not_enough"
        reason = "整数手约束削弱或扭曲了 Stage013 连续加风险 proxy，不能直接进入真实引擎。"
    result: dict[str, Any] = {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "baseline_A": "stage013_account_state_pilot_gate_engine",
        "candidate_C": "stage014_floor_or_ceil_integer_add_risk_proxy",
        "audit_type": "integer_contract_feasibility_audit_for_guarded_add_risk_proxy",
        **audit,
        **metrics,
        "unmatched_delta_dates": int(unmatched_delta_dates),
        "sample_count": int(wide["requested_start_month"].nunique()),
        "floor_min_return_pct": float(wide["total_return_pct_stage014_floor_integer_add_risk_proxy"].min()),
        "floor_median_return_pct": float(wide["total_return_pct_stage014_floor_integer_add_risk_proxy"].median()),
        "floor_worst_max_dd_pct": float(wide["max_dd_pct_stage014_floor_integer_add_risk_proxy"].min()),
        "ceil_min_return_pct": float(wide["total_return_pct_stage014_ceil_integer_add_risk_proxy"].min()),
        "ceil_median_return_pct": float(wide["total_return_pct_stage014_ceil_integer_add_risk_proxy"].median()),
        "ceil_worst_max_dd_pct": float(wide["max_dd_pct_stage014_ceil_integer_add_risk_proxy"].min()),
        "fractional_min_return_pct": float(wide["total_return_pct_stage013_guarded_fractional_add_risk_proxy"].min()),
        "fractional_worst_max_dd_pct": float(wide["max_dd_pct_stage013_guarded_fractional_add_risk_proxy"].min()),
        "floor_retention_vs_stage013_pass_count": floor_retention,
        "ceil_retention_vs_stage013_pass_count": ceil_retention,
        "retention_rows": rows,
        "strategy_changed": False,
        "true_engine": False,
        "order_api_called": False,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "ctp_connected": False,
        "decision": decision,
        "decision_reason": reason,
        "external_research_judgment": (
            "Position sizing must be executable in integer contracts. Meta-labeling/bet-sizing can size existing "
            "primary signals, but small-account futures sizing can materially differ from a continuous +25% proxy."
        ),
        "overfit_reflection_before": (
            "否。本阶段不是新增择时条件，而是检验 Stage013 连续加风险 proxy 是否能落到整数手执行。"
        ),
        "continue_value_before": (
            "有价值。若整数手不可行，直接写真实引擎只会把 proxy 的错觉带进后续研究。"
        ),
        "overfit_reflection_after": "",
        "continue_value_after": "",
        "official_live_impact": {
            "strategy_changed": False,
            "official_live_config_changed": False,
            "order_api_called": False,
            "ctp_connected": False,
            "research_only": True,
        },
    }
    if decision == "stage014_floor_integer_feasible_needs_true_engine":
        result["overfit_reflection_after"] = "否。该结果来自执行约束校验，不是新筛选条件；下一步仍需真实引擎而不是继续调参。"
        result["continue_value_after"] = "有价值。可以进入真实引擎验证，重点看保证金、重试、开仓日止损重进和整数手路径。"
    elif decision == "stage014_floor_integer_partially_feasible_but_under_realizes_fractional_proxy":
        result["overfit_reflection_after"] = "否。floor 是保守执行约束，表现变弱说明连续 proxy 存在可执行性折扣。"
        result["continue_value_after"] = "中等。只有当折扣后仍显著改善严格左尾，才值得做真实引擎。"
    elif decision == "stage014_ceil_integer_feasible_but_over_sizes_small_lots":
        result["overfit_reflection_after"] = "中等。ceil 不是拟合阈值，但它会系统性高估小手数风险，不应直接上线。"
        result["continue_value_after"] = "有限。除非另有风险预算证明，否则不应把 ceil 当正式候选。"
    else:
        result["overfit_reflection_after"] = "否。本阶段验证失败后不继续围绕 rounding 救参。"
        result["continue_value_after"] = "有限。应回到新 PIT 信息源或真实持仓路径，而不是强行把连续 proxy 离散化。"
    return result


def _plot_curves(proxy_curves: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 1, figsize=(17, 9), sharex=True, constrained_layout=True)
    for source, group in proxy_curves.groupby("requested_start_month", sort=True):
        g = group.sort_values("date")
        axes[0].plot(g["date"], g["stage014_floor_account_equity"], linewidth=0.85, alpha=0.85, label=f"{source} floor")
        axes[0].plot(g["date"], g["stage014_ceil_account_equity"], linewidth=0.65, alpha=0.35, linestyle="--", label=f"{source} ceil")
        axes[1].plot(g["date"], g["stage014_floor_drawdown_pct"], linewidth=0.85, alpha=0.85, label=f"{source} floor")
    axes[0].axhline(CAPITAL, color="#111827", linestyle="--", linewidth=0.8, label="initial 150k")
    axes[0].set_title("Stage014 Integer Add-risk Feasibility Absolute Account Equity")
    axes[0].set_ylabel("account equity")
    axes[0].grid(True, alpha=0.25)
    axes[1].set_title("Stage014 Floor Integer Add-risk Drawdown")
    axes[1].set_ylabel("drawdown %")
    axes[1].set_xlabel("date")
    axes[1].grid(True, alpha=0.25)
    axes[0].legend(loc="upper left", ncol=4, fontsize=6)
    axes[1].legend(loc="lower left", ncol=4, fontsize=6)
    fig.savefig(CHART_PATH, dpi=160)
    plt.close(fig)


def _write_report(decision: dict[str, Any], summary: pd.DataFrame, aggregate: pd.DataFrame, retention: pd.DataFrame) -> None:
    key_metrics = {
        key: decision[key]
        for key in [
            "input_lot_count",
            "fractional_proxy_delta_pnl",
            "floor_integer_proxy_delta_pnl",
            "ceil_integer_proxy_delta_pnl",
            "floor_realization_ratio_vs_fractional",
            "ceil_realization_ratio_vs_fractional",
            "floor_zero_extra_lot_count",
            "floor_zero_extra_lot_realized_pnl",
            "floor_min_return_pct",
            "ceil_min_return_pct",
            "floor_retention_vs_stage013_pass_count",
            "ceil_retention_vs_stage013_pass_count",
            "retention_rows",
        ]
    }
    text = f"""# Stage014 Integer Add-risk Feasibility Audit

- line_id：`{LINE_ID}`
- 记录时间：{decision["generated_at"]}
- 决策：`{decision["decision"]}`

## 假设

Stage013 的 `risk_multiplier<2` guarded quality add-risk 仍是连续 `+25%` closed-lot proxy。期货真实执行必须是整数手，所以本阶段只检验两种离散化：

- `floor`：`floor(selected_volume * 25%)`，保守，不会超过连续 proxy。
- `ceil`：`ceil(selected_volume * 25%)`，更接近“至少加 1 手”，但小手数会显著超过连续 proxy。

## 结果概要

```json
{json.dumps(_json_safe(key_metrics), ensure_ascii=False, indent=2)}
```

## 多起点摘要

{_md_table(summary, max_rows=68)}

## 严格窗口摘要

{_md_table(aggregate, max_rows=40)}

## 收益保留

{_md_table(retention, max_rows=20)}

## 结论

- {decision["decision_reason"]}
- 本阶段仍是只读整数手 feasibility proxy，不是真实引擎，不改实盘。

## 过拟合反思

- 运行前：{decision["overfit_reflection_before"]}
- 运行后：{decision["overfit_reflection_after"]}

## 继续价值反思

- 运行前：{decision["continue_value_before"]}
- 运行后：{decision["continue_value_after"]}
"""
    REPORT_PATH.write_text(text, encoding="utf-8")


def _write_stage_record(decision: dict[str, Any], summary: pd.DataFrame, aggregate: pd.DataFrame, retention: pd.DataFrame) -> None:
    text = f"""# Stage014 Integer Add-risk Feasibility Audit

- line_id：`{LINE_ID}`
- 当前模式：day
- 记录时间：{decision["generated_at"]}
- 阶段性质：Stage013 guarded quality add-risk 的整数手可实现性审计；不改官方 live config、不连接 CTP、不调用下单
- 是否重要突破：否
- 是否触发A/B：否；本阶段还不是策略引擎，只判断是否值得进入真实引擎

## 外部调研与判断

- 参考资料：pysystemtrade rounded positions/buffering、Hudson & Thames meta-labeling、期货 position sizing 风控资料。
- 我的判断：连续 `+25%` 在期货里不是天然可执行，尤其 `selected_volume=1/2/3` 时 floor 等于不加仓、ceil 则明显超配；所以必须先量化整数手折扣。

## 本次变更

- 新增脚本：`research/lines/{LINE_ID}/tools/stage014_integer_add_risk_feasibility_audit.py`
- 新增测试：`tests/test_rebuilt_c9_v2_stage014_integer_add_risk_feasibility.py`
- 新增参数：`ADD_RISK_FRACTION={ADD_RISK_FRACTION}`、`floor/ceil integer extra lots`
- 修改参数：无
- 删除参数：无

## 结果

- 输入 guarded lots：`{decision["input_lot_count"]}`
- 连续 proxy delta：`{decision["fractional_proxy_delta_pnl"]:.2f}`
- floor integer delta：`{decision["floor_integer_proxy_delta_pnl"]:.2f}`，实现比例 `{decision["floor_realization_ratio_vs_fractional"]:.4f}`
- ceil integer delta：`{decision["ceil_integer_proxy_delta_pnl"]:.2f}`，实现比例 `{decision["ceil_realization_ratio_vs_fractional"]:.4f}`
- floor 额外手数为 0 的 lots：`{decision["floor_zero_extra_lot_count"]}`，这些 lots 的 realized PnL `{decision["floor_zero_extra_lot_realized_pnl"]:.2f}`
- floor 期末最差收益：`{decision["floor_min_return_pct"]:.4f}%`
- ceil 期末最差收益：`{decision["ceil_min_return_pct"]:.4f}%`
- floor 80% 收益保留：`{decision["floor_retention_vs_stage013_pass_count"]}/{decision["retention_rows"]}`
- ceil 80% 收益保留：`{decision["ceil_retention_vs_stage013_pass_count"]}/{decision["retention_rows"]}`
- floor 严格 >365 天负窗口：`{decision["stage014_floor_integer_add_risk_proxy_all_gt1y_negative_count"]}/{decision["stage014_floor_integer_add_risk_proxy_all_gt1y_window_count"]}`
- floor 严格最差窗口收益：`{decision["stage014_floor_integer_add_risk_proxy_all_gt1y_min_return_pct"]:.4f}%`
- ceil 严格 >365 天负窗口：`{decision["stage014_ceil_integer_add_risk_proxy_all_gt1y_negative_count"]}/{decision["stage014_ceil_integer_add_risk_proxy_all_gt1y_window_count"]}`
- ceil 严格最差窗口收益：`{decision["stage014_ceil_integer_add_risk_proxy_all_gt1y_min_return_pct"]:.4f}%`
- 决策：`{decision["decision"]}`
- 原因：{decision["decision_reason"]}

## 多起点摘要

{_md_table(summary, max_rows=68)}

## 严格窗口摘要

{_md_table(aggregate, max_rows=40)}

## 过拟合反思

- 运行前判断：{decision["overfit_reflection_before"]}
- 运行后判断：{decision["overfit_reflection_after"]}

## 继续价值反思

- 运行前判断：{decision["continue_value_before"]}
- 运行后判断：{decision["continue_value_after"]}

## 输出文件

- lot_deltas: `{LOT_DELTAS_PATH}`
- curves: `{CURVES_PATH}`
- summary: `{SUMMARY_PATH}`
- ab_summary: `{AB_SUMMARY_PATH}`
- goal_aggregate: `{GOAL_AGGREGATE_PATH}`
- goal_to_final: `{GOAL_TO_FINAL_PATH}`
- goal_fixed_horizon: `{GOAL_FIXED_HORIZON_PATH}`
- goal_worst_windows: `{GOAL_WORST_WINDOWS_PATH}`
- retention: `{RETENTION_PATH}`
- chart: `{CHART_PATH}`
- decision: `{DECISION_PATH}`
- report: `{REPORT_PATH}`
"""
    STAGE_RECORD_PATH.write_text(text, encoding="utf-8")


def run() -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    stage013_lots = _read_csv(STAGE013_LOT_DELTAS_PATH)
    base_curves = _read_csv(STAGE013_CURVES_PATH)
    lot_deltas, audit = compute_integer_add_risk_lot_deltas(stage013_lots)
    lot_deltas["requested_start_month"] = lot_deltas["requested_start_month"].astype(str)
    lot_deltas["entry_date"] = pd.to_datetime(lot_deltas["entry_date"], errors="coerce").dt.normalize()
    lot_deltas["exit_date"] = pd.to_datetime(lot_deltas["exit_date"], errors="coerce").dt.normalize()
    proxy_curves, unmatched = build_integer_proxy_curves(base_curves, lot_deltas)
    summary = _summary(proxy_curves)
    ab_summary = _wide_summary(summary)
    aggregate, to_final, fixed_horizon, worst_windows = _goal_audit(proxy_curves)
    retention = _retention(summary)
    decision = _decision(summary, aggregate, retention, audit, unmatched)
    lot_deltas.to_csv(LOT_DELTAS_PATH, index=False, encoding="utf-8-sig", compression="gzip")
    proxy_curves.to_csv(CURVES_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    ab_summary.to_csv(AB_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    aggregate.to_csv(GOAL_AGGREGATE_PATH, index=False, encoding="utf-8-sig")
    to_final.to_csv(GOAL_TO_FINAL_PATH, index=False, encoding="utf-8-sig")
    fixed_horizon.to_csv(GOAL_FIXED_HORIZON_PATH, index=False, encoding="utf-8-sig")
    worst_windows.to_csv(GOAL_WORST_WINDOWS_PATH, index=False, encoding="utf-8-sig")
    retention.to_csv(RETENTION_PATH, index=False, encoding="utf-8-sig")
    _plot_curves(proxy_curves)
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(decision, summary, aggregate, retention)
    _write_stage_record(decision, summary, aggregate, retention)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    return decision


if __name__ == "__main__":
    run()
