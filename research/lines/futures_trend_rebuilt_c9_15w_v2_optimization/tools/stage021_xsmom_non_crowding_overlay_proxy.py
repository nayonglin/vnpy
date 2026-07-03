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
STAGE = "Stage021"
MODEL_TAG = "stage021_xsmom_non_crowding_overlay_proxy_v1"
OUTPUT_PREFIX = "rebuilt_c9_v2_stage021_xsmom_non_crowding_overlay_proxy"

LINE_DIR = PROJECT_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage021_xsmom_non_crowding_overlay_proxy"
STAGES_DIR = LINE_DIR / "stages"
TOOLS_DIR = Path(__file__).resolve().parent
UPSTREAM_TOOLS_DIR = PROJECT_DIR / "research" / "lines" / UPSTREAM_LINE_ID / "tools"
for path in (TOOLS_DIR, UPSTREAM_TOOLS_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import stage009_dense_start_goal_audit as s009_goal  # noqa: E402


C9_CURVES_PATH = (
    PROJECT_DIR
    / "examples"
    / "portfolio_backtesting"
    / "backtest_outputs"
    / "qmt_roll_stage167_c9_live_15w_multiperiod_ai_audit_curves_stage167_c9_live_15w_multiperiod_ai_audit_v1.csv"
)
STAGE020_OUTPUT_DIR = LINE_DIR / "outputs" / "stage020_sqlite_jd_repair_xsmom_inputs"
STAGE020_PREFIX = "rebuilt_c9_v2_stage020_sqlite_jd_repair_xsmom_inputs"
STAGE020_TAG = "stage020_sqlite_jd_repair_xsmom_inputs_v1"
SATELLITE_DAILY_PATH = STAGE020_OUTPUT_DIR / f"{STAGE020_PREFIX}_satellite_daily_{STAGE020_TAG}.csv"

CURVES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv"
SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
GOAL_AGGREGATE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_goal_aggregate_{MODEL_TAG}.csv"
GOAL_TO_FINAL_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_goal_to_final_windows_{MODEL_TAG}.csv"
GOAL_FIXED_HORIZON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_goal_fixed_horizon_windows_{MODEL_TAG}.csv"
GOAL_WORST_WINDOWS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_goal_worst_windows_{MODEL_TAG}.csv"
RETENTION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_retention_vs_c9_{MODEL_TAG}.csv"
VARIANT_GOAL_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_variant_goal_table_{MODEL_TAG}.csv"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_absolute_equity_chart_{MODEL_TAG}.png"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
STAGE_RECORD_PATH = STAGES_DIR / "20260702_0635_stage021_xsmom_non_crowding_overlay_proxy.md"

CAPITAL = 150_000.0
ANALYSIS_END = pd.Timestamp("2026-06-30")
START_MONTHS = tuple(pd.date_range("2020-01-01", "2025-01-01", freq="6MS"))
SPECS = ("mom_12m_skip1m", "mom_6m_skip1m")
OVERLAY_WEIGHTS = (0.025, 0.05, 0.075, 0.10, 0.20, 0.30)
BASE_VARIANT = "c9_base"
DEFAULT_COST_BPS = 10.0
EPS = 1e-9


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (pd.Timestamp, datetime)):
        if pd.isna(value):
            return ""
        return value.isoformat()
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            return str(value)
    if pd.isna(value):
        return ""
    return value


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_无记录_"
    data = frame.head(max_rows).copy() if max_rows else frame.copy()
    return data.to_markdown(index=False)


def _read_csv(path: Path, **kwargs: Any) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path, encoding="utf-8-sig", **kwargs)


def _month_text(value: Any) -> str:
    return pd.Timestamp(value).strftime("%Y-%m")


def _weight_label(weight: float) -> str:
    return f"{weight * 100:g}".replace(".", "p")


def _cost_label(cost_bps: float) -> str:
    return f"{cost_bps:g}".replace(".", "p")


def overlay_variant_name(spec: str, weight: float, cost_bps: float) -> str:
    return f"c9_plus_xsmom_{spec}_w{_weight_label(weight)}_cost{_cost_label(cost_bps)}bps"


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


def _load_c9_curves() -> pd.DataFrame:
    data = _read_csv(C9_CURVES_PATH, usecols=["requested_start_month", "date", "account_equity"])
    data["requested_start_month"] = data["requested_start_month"].astype(str)
    wanted = {_month_text(item) for item in START_MONTHS}
    data = data[data["requested_start_month"].isin(wanted)].copy()
    data["date"] = pd.to_datetime(data["date"], errors="coerce").dt.normalize()
    data = data[data["date"].le(ANALYSIS_END)].copy()
    data["account_equity"] = pd.to_numeric(data["account_equity"], errors="coerce")
    data = data.dropna(subset=["date", "account_equity"])
    return data.sort_values(["requested_start_month", "date"]).reset_index(drop=True)


def _load_satellite_daily() -> pd.DataFrame:
    data = _read_csv(SATELLITE_DAILY_PATH)
    data["date"] = pd.to_datetime(data["date"], errors="coerce").dt.normalize()
    return data.dropna(subset=["date"]).sort_values(["spec", "date"]).reset_index(drop=True)


def _prepare_satellite_returns(satellite_daily: pd.DataFrame, *, spec: str, cost_bps: float) -> pd.DataFrame:
    column = f"satellite_return_cost{cost_bps:g}bps"
    if column not in satellite_daily.columns:
        raise KeyError(f"satellite return column not found: {column}")
    data = satellite_daily[satellite_daily["spec"].astype(str).eq(spec)].copy()
    data["date"] = pd.to_datetime(data["date"], errors="coerce").dt.normalize()
    data["satellite_return"] = pd.to_numeric(data[column], errors="coerce").fillna(0.0)
    return data[["date", "satellite_return"]].dropna(subset=["date"]).drop_duplicates("date", keep="last")


def build_non_crowding_overlay_curves(
    c9_curves: pd.DataFrame,
    satellite_daily: pd.DataFrame,
    *,
    weights: tuple[float, ...] = OVERLAY_WEIGHTS,
    specs: tuple[str, ...] = SPECS,
    cost_bps: float = DEFAULT_COST_BPS,
    capital: float = CAPITAL,
) -> pd.DataFrame:
    c9 = c9_curves.copy()
    c9["requested_start_month"] = c9["requested_start_month"].astype(str)
    c9["date"] = pd.to_datetime(c9["date"], errors="coerce").dt.normalize()
    c9["account_equity"] = pd.to_numeric(c9["account_equity"], errors="coerce")
    c9 = c9.dropna(subset=["date", "account_equity"]).sort_values(["requested_start_month", "date"])

    base = c9.copy()
    base["variant"] = BASE_VARIANT
    base["xsmom_spec"] = ""
    base["xsmom_weight"] = 0.0
    base["cost_bps"] = 0.0
    base["satellite_return"] = 0.0
    base["xsmom_nav"] = 1.0
    base["xsmom_pnl_delta"] = 0.0
    base["c9_account_equity"] = base["account_equity"]
    base["stage"] = STAGE
    base["model_tag"] = MODEL_TAG
    base["line_id"] = LINE_ID
    rows: list[pd.DataFrame] = [base]

    for spec in specs:
        sat = _prepare_satellite_returns(satellite_daily, spec=spec, cost_bps=cost_bps)
        for weight in weights:
            variant = overlay_variant_name(spec, float(weight), float(cost_bps))
            for _, group in c9.groupby("requested_start_month", sort=True):
                merged = group.merge(sat, on="date", how="left")
                merged["satellite_return"] = pd.to_numeric(merged["satellite_return"], errors="coerce").fillna(0.0)
                if not merged.empty:
                    merged.loc[merged.index[0], "satellite_return"] = 0.0
                merged["xsmom_nav"] = (1.0 + merged["satellite_return"]).cumprod()
                merged["xsmom_pnl_delta"] = float(capital) * float(weight) * (merged["xsmom_nav"] - 1.0)
                merged["c9_account_equity"] = merged["account_equity"]
                merged["account_equity"] = merged["c9_account_equity"] + merged["xsmom_pnl_delta"]
                merged["variant"] = variant
                merged["xsmom_spec"] = spec
                merged["xsmom_weight"] = float(weight)
                merged["cost_bps"] = float(cost_bps)
                merged["stage"] = STAGE
                merged["model_tag"] = MODEL_TAG
                merged["line_id"] = LINE_ID
                rows.append(merged)

    result = pd.concat(rows, ignore_index=True, sort=False)
    result["drawdown_pct"] = result.groupby(["variant", "requested_start_month"])["account_equity"].transform(
        _drawdown_pct
    )
    return result.sort_values(["variant", "requested_start_month", "date"]).reset_index(drop=True)


def summarize_curve(curve: pd.DataFrame, *, variant: str, requested_start_month: str) -> dict[str, Any]:
    data = curve.sort_values("date").drop_duplicates("date").copy()
    equity = pd.to_numeric(data["account_equity"], errors="coerce")
    start_equity = float(equity.iloc[0])
    end_equity = float(equity.iloc[-1])
    return {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "variant": variant,
        "requested_start_month": requested_start_month,
        "xsmom_spec": str(data["xsmom_spec"].iloc[0]) if "xsmom_spec" in data.columns else "",
        "xsmom_weight": float(data["xsmom_weight"].iloc[0]) if "xsmom_weight" in data.columns else 0.0,
        "cost_bps": float(data["cost_bps"].iloc[0]) if "cost_bps" in data.columns else 0.0,
        "start_date": pd.Timestamp(data["date"].iloc[0]).date().isoformat(),
        "end_date": pd.Timestamp(data["date"].iloc[-1]).date().isoformat(),
        "trading_days": int(len(data)),
        "start_equity": start_equity,
        "end_equity": end_equity,
        "total_return_pct": float((end_equity / start_equity - 1.0) * 100.0) if start_equity else np.nan,
        "max_drawdown_pct": float(_drawdown_pct(equity).min()),
        "sharpe": _sharpe_from_equity(equity),
        "xsmom_pnl_delta_end": float(pd.to_numeric(data.get("xsmom_pnl_delta", 0.0), errors="coerce").iloc[-1]),
    }


def summarize_all(curves: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (variant, start_month), group in curves.groupby(["variant", "requested_start_month"], sort=True):
        rows.append(summarize_curve(group, variant=str(variant), requested_start_month=str(start_month)))
    return pd.DataFrame(rows).sort_values(["variant", "requested_start_month"]).reset_index(drop=True)


def audit_goal_windows(curves: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    data = curves[["requested_start_month", "date", "variant", "account_equity"]].copy()
    data.rename(columns={"account_equity": "equity"}, inplace=True)
    data["date"] = pd.to_datetime(data["date"], errors="coerce").dt.normalize()
    data["equity"] = pd.to_numeric(data["equity"], errors="coerce")
    data = data.dropna(subset=["date", "equity"]).sort_values(["variant", "requested_start_month", "date"])
    return s009_goal._run_audit(data)


def retention_vs_base(summary: pd.DataFrame) -> pd.DataFrame:
    data = summary.copy()
    defaults: dict[str, Any] = {"xsmom_spec": "", "xsmom_weight": 0.0, "cost_bps": 0.0}
    for column, default in defaults.items():
        if column not in data.columns:
            data[column] = default
    base = data[data["variant"].eq(BASE_VARIANT)][["requested_start_month", "total_return_pct"]].rename(
        columns={"total_return_pct": "c9_total_return_pct"}
    )
    merged = data.merge(base, on="requested_start_month", how="left")
    merged["return_retention_vs_c9"] = merged["total_return_pct"] / merged["c9_total_return_pct"].replace(0.0, np.nan)
    merged["passes_80pct_retention"] = merged["total_return_pct"].ge(
        merged["c9_total_return_pct"] * 0.8
    ).astype("int64")
    return merged[
        [
            "variant",
            "requested_start_month",
            "xsmom_spec",
            "xsmom_weight",
            "cost_bps",
            "total_return_pct",
            "c9_total_return_pct",
            "return_retention_vs_c9",
            "passes_80pct_retention",
        ]
    ].sort_values(["variant", "requested_start_month"]).reset_index(drop=True)


def _variant_goal_table(aggregate: pd.DataFrame, retention: pd.DataFrame, summary: pd.DataFrame) -> pd.DataFrame:
    all_scope = (
        aggregate[aggregate["audit_scope"].eq("all_trading_end_dates_gt_1y")]
        .groupby("variant", as_index=False)
        .agg(
            all_gt1y_window_count=("window_count", "sum"),
            all_gt1y_negative_count=("negative_count", "sum"),
            all_gt1y_min_return_pct=("min_return_pct", "min"),
            all_gt1y_mean_return_pct=("mean_return_pct", "mean"),
        )
    )
    final_scope = (
        aggregate[aggregate["audit_scope"].eq("start_to_2026_06_30_only")]
        .groupby("variant", as_index=False)
        .agg(
            to_final_window_count=("window_count", "sum"),
            to_final_negative_count=("negative_count", "sum"),
            to_final_min_return_pct=("min_return_pct", "min"),
            to_final_mean_return_pct=("mean_return_pct", "mean"),
        )
    )
    ret_scope = retention.groupby("variant", as_index=False).agg(
        retention_80pct_pass_count=("passes_80pct_retention", "sum"),
        retention_rows=("passes_80pct_retention", "size"),
        min_retention=("return_retention_vs_c9", "min"),
    )
    summary_scope = summary.groupby("variant", as_index=False).agg(
        median_total_return_pct=("total_return_pct", "median"),
        min_total_return_pct=("total_return_pct", "min"),
        worst_max_drawdown_pct=("max_drawdown_pct", "min"),
        median_sharpe=("sharpe", "median"),
        median_xsmom_pnl_delta_end=("xsmom_pnl_delta_end", "median"),
    )
    table = (
        all_scope.merge(final_scope, on="variant", how="outer")
        .merge(ret_scope, on="variant", how="outer")
        .merge(summary_scope, on="variant", how="outer")
    )
    table["objective_pass"] = (
        table["all_gt1y_negative_count"].fillna(1).eq(0)
        & table["to_final_negative_count"].fillna(1).eq(0)
        & table["retention_80pct_pass_count"].eq(table["retention_rows"])
    ).astype("int64")
    return table.sort_values(
        ["objective_pass", "all_gt1y_negative_count", "all_gt1y_min_return_pct", "min_retention"],
        ascending=[False, True, False, False],
    ).reset_index(drop=True)


def _choose_best_variant(variant_goal: pd.DataFrame) -> dict[str, Any]:
    non_base = variant_goal[~variant_goal["variant"].eq(BASE_VARIANT)].copy()
    if non_base.empty:
        return {}
    return non_base.sort_values(
        ["objective_pass", "all_gt1y_negative_count", "all_gt1y_min_return_pct", "min_retention"],
        ascending=[False, True, False, False],
    ).iloc[0].to_dict()


def _decision(summary: pd.DataFrame, aggregate: pd.DataFrame, retention: pd.DataFrame) -> dict[str, Any]:
    variant_goal = _variant_goal_table(aggregate, retention, summary)
    base = variant_goal[variant_goal["variant"].eq(BASE_VARIANT)].iloc[0].to_dict()
    best = _choose_best_variant(variant_goal)
    pass_count = int(variant_goal[~variant_goal["variant"].eq(BASE_VARIANT)]["objective_pass"].sum())
    best_neg = int(best.get("all_gt1y_negative_count", 0)) if best else 0
    base_neg = int(base["all_gt1y_negative_count"])
    best_retention_full = bool(
        best and int(best.get("retention_80pct_pass_count", -1)) == int(best.get("retention_rows", 0))
    )
    if pass_count > 0:
        decision = "stage021_xsmom_overlay_has_goal_candidate_needs_true_combo_margin_audit"
        continue_after = "有。proxy 已通过目标门，但必须进入真实组合、保证金、整数手和交易成本审计，不能直接上线。"
    elif best and best_neg < base_neg and best_retention_full:
        decision = "stage021_xsmom_overlay_improves_left_tail_need_true_combo_margin_audit"
        continue_after = "有但未达标。xsmom 独立袖改善左尾且收益保留达标，下一步验证真实组合可实现性和残余亏损来源。"
    else:
        decision = "stage021_xsmom_overlay_not_promoted_keep_readonly"
        continue_after = "有限。若连 proxy 都不能改善左尾或保留收益，不应继续扫同一 xsmom 权重。"
    result = {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "analysis_end": ANALYSIS_END.date().isoformat(),
        "start_months": [_month_text(item) for item in START_MONTHS],
        "specs": list(SPECS),
        "overlay_weights": list(OVERLAY_WEIGHTS),
        "cost_bps": DEFAULT_COST_BPS,
        "capital": CAPITAL,
        "baseline_variant": BASE_VARIANT,
        "audit_type": "current_c9_plus_xsmom_non_crowding_curve_level_proxy",
        "is_independent_daily_cold_start": False,
        "strategy_changed": False,
        "true_engine": False,
        "order_api_called": False,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "ctp_connected": False,
        "formal_ab_triggered": False,
        "base_all_gt1y_negative_count": base_neg,
        "base_all_gt1y_min_return_pct": float(base["all_gt1y_min_return_pct"]),
        "best_variant": str(best.get("variant", "")) if best else "",
        "best_all_gt1y_negative_count": best_neg,
        "best_all_gt1y_min_return_pct": float(best.get("all_gt1y_min_return_pct", np.nan)) if best else np.nan,
        "best_min_retention": float(best.get("min_retention", np.nan)) if best else np.nan,
        "best_median_total_return_pct": float(best.get("median_total_return_pct", np.nan)) if best else np.nan,
        "best_worst_max_drawdown_pct": float(best.get("worst_max_drawdown_pct", np.nan)) if best else np.nan,
        "objective_pass_variant_count": pass_count,
        "decision": decision,
        "external_research_judgment": (
            "Time-series/cross-sectional momentum and managed-futures literature support low-correlated trend sleeves, "
            "but this stage only tests a predeclared curve-level overlay before any true combo or live change."
        ),
        "overfit_reflection_before": (
            "否。xsmom 的两个 lookback、月度调仓、top/bottom3 和成本列来自 Stage345/Stage020 固定输入；本阶段只做预声明粗权重 overlay。"
        ),
        "overfit_reflection_after": (
            "否，但若根据本次最差窗口继续微调权重、lookback、品种、方向或成本档，就是过拟合。"
        ),
        "continue_value_before": (
            "有价值。Stage018/020 已证明低相关腿有历史线索且输入覆盖完整，必须先看它是否真的改善 C9 路径。"
        ),
        "continue_value_after": continue_after,
        "variant_goal_table": variant_goal.to_dict(orient="records"),
        "outputs": {
            "curves": str(CURVES_PATH),
            "summary": str(SUMMARY_PATH),
            "goal_aggregate": str(GOAL_AGGREGATE_PATH),
            "goal_to_final": str(GOAL_TO_FINAL_PATH),
            "goal_fixed_horizon": str(GOAL_FIXED_HORIZON_PATH),
            "goal_worst_windows": str(GOAL_WORST_WINDOWS_PATH),
            "retention": str(RETENTION_PATH),
            "variant_goal": str(VARIANT_GOAL_PATH),
            "chart": str(CHART_PATH),
            "decision": str(DECISION_PATH),
            "report": str(REPORT_PATH),
            "stage_record": str(STAGE_RECORD_PATH),
        },
    }
    return result


def _plot_absolute_equity(curves: pd.DataFrame, decision: dict[str, Any]) -> None:
    best_variant = decision.get("best_variant") or BASE_VARIANT
    plot = curves[curves["variant"].isin([BASE_VARIANT, best_variant])].copy()
    fig, axes = plt.subplots(2, 1, figsize=(18, 11), sharex=True, constrained_layout=True)
    for variant, group in plot.groupby("variant", sort=False):
        color = "#111827" if variant == BASE_VARIANT else "#2563eb"
        alpha = 0.45 if variant == BASE_VARIANT else 0.82
        for start_month, curve in group.groupby("requested_start_month", sort=True):
            label = f"{variant} {start_month}"
            axes[0].plot(curve["date"], curve["account_equity"], linewidth=0.8, alpha=alpha, color=color, label=label)
            axes[1].plot(curve["date"], curve["drawdown_pct"], linewidth=0.8, alpha=alpha, color=color)
    axes[0].axhline(CAPITAL, color="#6b7280", linestyle="--", linewidth=0.9)
    axes[0].set_title(f"Stage021 Absolute Equity: {BASE_VARIANT} vs {best_variant}")
    axes[0].set_ylabel("account equity")
    axes[1].set_title("Drawdown")
    axes[1].set_ylabel("drawdown %")
    axes[1].set_xlabel("date")
    for ax in axes:
        ax.grid(True, alpha=0.25)
    handles, labels = axes[0].get_legend_handles_labels()
    axes[0].legend(handles[:22], labels[:22], fontsize=6, ncol=2, loc="best")
    fig.savefig(CHART_PATH, dpi=160)
    plt.close(fig)


def _write_report(decision: dict[str, Any], summary: pd.DataFrame, aggregate: pd.DataFrame, retention: pd.DataFrame) -> None:
    variant_goal = pd.DataFrame(decision["variant_goal_table"])
    best_variant = decision["best_variant"]
    best_summary = summary[summary["variant"].eq(best_variant)].copy() if best_variant else pd.DataFrame()
    best_aggregate = aggregate[aggregate["variant"].eq(best_variant)].copy() if best_variant else pd.DataFrame()
    lines = [
        "# Stage021 xsmom 非挤占资金袖 proxy",
        "",
        f"- line_id：`{LINE_ID}`",
        f"- 生成时间：`{decision['generated_at']}`",
        f"- 决策：`{decision['decision']}`",
        "- 阶段性质：curve-level 只读 proxy；不改 C9，不连接 CTP，不调用订单 API。",
        f"- 成本：`{DEFAULT_COST_BPS:g}bps`；权重：`{list(OVERLAY_WEIGHTS)}`；spec：`{list(SPECS)}`。",
        "",
        "## 方法",
        "",
        "- 基础曲线：Stage167 当前重建 C9/15w 多起点资金曲线。",
        "- xsmom 输入：Stage020 已补齐的 19 品种横截面动量 satellite daily，包含 `jd.DCE`。",
        "- 叠加方式：非挤占 overlay，`account_equity = c9_equity + 150000 * weight * (xsmom_nav - 1)`；不降低 C9 本身风险。",
        "- 审计：复用 Stage009/017 严格目标口径，枚举 `2020-01-01` 到 `2025-06-30` 的曲线内交易日起点和所有 `>365` 天终点。",
        "- 注意：本阶段不是独立每日冷启动真引擎，不含保证金、整数手、滑点成交路径和真实组合冲突。",
        "",
        "## 目标门汇总",
        "",
        _md_table(
            variant_goal[
                [
                    "variant",
                    "all_gt1y_negative_count",
                    "all_gt1y_min_return_pct",
                    "to_final_negative_count",
                    "min_retention",
                    "median_total_return_pct",
                    "worst_max_drawdown_pct",
                    "objective_pass",
                ]
            ],
            max_rows=40,
        ),
        "",
        "## 最优候选多起点摘要",
        "",
        _md_table(
            best_summary[
                [
                    "requested_start_month",
                    "total_return_pct",
                    "max_drawdown_pct",
                    "sharpe",
                    "xsmom_pnl_delta_end",
                ]
            ],
            max_rows=20,
        )
        if not best_summary.empty
        else "_无_",
        "",
        "## 最优候选目标审计",
        "",
        _md_table(best_aggregate, max_rows=30) if not best_aggregate.empty else "_无_",
        "",
        "## 收益保留",
        "",
        _md_table(retention[retention["variant"].eq(best_variant)].copy(), max_rows=20)
        if best_variant
        else "_无_",
        "",
        "## 反思",
        "",
        f"- 运行前过拟合反思：{decision['overfit_reflection_before']}",
        f"- 运行后过拟合反思：{decision['overfit_reflection_after']}",
        f"- 运行前继续价值反思：{decision['continue_value_before']}",
        f"- 运行后继续价值反思：{decision['continue_value_after']}",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_stage_record(decision: dict[str, Any], summary: pd.DataFrame, aggregate: pd.DataFrame) -> None:
    variant_goal = pd.DataFrame(decision["variant_goal_table"])
    best_variant = decision["best_variant"]
    best_summary = summary[summary["variant"].eq(best_variant)].copy() if best_variant else pd.DataFrame()
    best_aggregate = aggregate[aggregate["variant"].eq(best_variant)].copy() if best_variant else pd.DataFrame()
    record = f"""# Stage021 xsmom 非挤占资金袖 proxy

- line_id：`{LINE_ID}`
- 当前模式：day
- 记录时间：{decision["generated_at"]}
- 阶段性质：curve-level 只读 proxy；不改官方 live config、不连接 CTP、不调用下单
- 是否重要突破：否
- 是否触发A/B：否。若 proxy 达标，也必须先做真实组合/保证金/整数手审计。

## 外部调研与判断

- 参考：Rob Carver/pysystemtrade 横截面动量、AQR/managed futures 时间序列动量与趋势跟随研究。
- 我的判断：低相关趋势袖有理论和实践依据，但必须先作为独立资金袖验证路径收益；不能为了修某段窗口去调 lookback、品种或方向。

## 本次变更

- 新增脚本：`research/lines/{LINE_ID}/tools/stage021_xsmom_non_crowding_overlay_proxy.py`
- 新增测试：`tests/test_rebuilt_c9_v2_stage021_xsmom_overlay_proxy.py`
- 新增参数：`OVERLAY_WEIGHTS={list(OVERLAY_WEIGHTS)}`、`SPECS={list(SPECS)}`、`DEFAULT_COST_BPS={DEFAULT_COST_BPS}`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 基础曲线：Stage167 当前重建 C9/15w 多起点曲线。
- xsmom 输入：Stage020 `satellite_daily`，19 品种，含 `jd.DCE`。
- 叠加公式：`account_equity = c9_equity + 150000 * weight * (xsmom_nav - 1)`。
- 审计：所有 `2020-01-01` 到 `2025-06-30` 曲线内交易日起点，所有 `>365` 天终点；到 `2026-06-30` 终点；固定 horizon；80% 收益保留 vs C9。

## 结果

- 基准 C9 严格 `>1` 年负窗口：`{decision["base_all_gt1y_negative_count"]}`，最差 `{decision["base_all_gt1y_min_return_pct"]:.4f}%`
- 最优 overlay：`{decision["best_variant"]}`
- 最优 overlay 严格 `>1` 年负窗口：`{decision["best_all_gt1y_negative_count"]}`，最差 `{decision["best_all_gt1y_min_return_pct"]:.4f}%`
- 最优 overlay 最小收益保留：`{decision["best_min_retention"]:.4f}`
- 最优 overlay 多起点中位收益：`{decision["best_median_total_return_pct"]:.4f}%`
- 最优 overlay 最差最大回撤：`{decision["best_worst_max_drawdown_pct"]:.4f}%`
- 目标通过 variant 数：`{decision["objective_pass_variant_count"]}`
- 决策：`{decision["decision"]}`

## 目标门汇总

{_md_table(variant_goal[["variant", "all_gt1y_negative_count", "all_gt1y_min_return_pct", "to_final_negative_count", "min_retention", "median_total_return_pct", "worst_max_drawdown_pct", "objective_pass"]], max_rows=40)}

## 最优候选多起点摘要

{_md_table(best_summary[["requested_start_month", "total_return_pct", "max_drawdown_pct", "sharpe", "xsmom_pnl_delta_end"]], max_rows=20) if not best_summary.empty else "_无_"}

## 最优候选目标审计

{_md_table(best_aggregate, max_rows=30) if not best_aggregate.empty else "_无_"}

## 过拟合反思

- 运行前判断：{decision["overfit_reflection_before"]}
- 运行后判断：{decision["overfit_reflection_after"]}

## 继续价值反思

- 运行前判断：{decision["continue_value_before"]}
- 运行后判断：{decision["continue_value_after"]}

## 输出文件

- curves：`{CURVES_PATH}`
- summary：`{SUMMARY_PATH}`
- goal_aggregate：`{GOAL_AGGREGATE_PATH}`
- goal_to_final：`{GOAL_TO_FINAL_PATH}`
- goal_fixed_horizon：`{GOAL_FIXED_HORIZON_PATH}`
- goal_worst_windows：`{GOAL_WORST_WINDOWS_PATH}`
- retention：`{RETENTION_PATH}`
- variant_goal：`{VARIANT_GOAL_PATH}`
- chart：`{CHART_PATH}`
- decision：`{DECISION_PATH}`
- report：`{REPORT_PATH}`
"""
    STAGE_RECORD_PATH.write_text(record, encoding="utf-8")


def run() -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    STAGES_DIR.mkdir(parents=True, exist_ok=True)
    c9_curves = _load_c9_curves()
    satellite_daily = _load_satellite_daily()
    curves = build_non_crowding_overlay_curves(c9_curves, satellite_daily)
    summary = summarize_all(curves)
    aggregate, to_final, fixed, worst = audit_goal_windows(curves)
    retention = retention_vs_base(summary)
    decision = _decision(summary, aggregate, retention)
    variant_goal = pd.DataFrame(decision["variant_goal_table"])

    curves.to_csv(CURVES_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    aggregate.to_csv(GOAL_AGGREGATE_PATH, index=False, encoding="utf-8-sig")
    to_final.to_csv(GOAL_TO_FINAL_PATH, index=False, encoding="utf-8-sig")
    fixed.to_csv(GOAL_FIXED_HORIZON_PATH, index=False, encoding="utf-8-sig")
    worst.to_csv(GOAL_WORST_WINDOWS_PATH, index=False, encoding="utf-8-sig")
    retention.to_csv(RETENTION_PATH, index=False, encoding="utf-8-sig")
    variant_goal.to_csv(VARIANT_GOAL_PATH, index=False, encoding="utf-8-sig")
    _plot_absolute_equity(curves, decision)
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_report(decision, summary, aggregate, retention)
    _write_stage_record(decision, summary, aggregate)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    return decision


if __name__ == "__main__":
    run()
