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
STAGE = "Stage013"
MODEL_TAG = "stage013_guarded_quality_add_risk_proxy_v1"
OUTPUT_PREFIX = "rebuilt_c9_v2_stage013_guarded_quality_add_risk_proxy"
SELECTOR_NAME = "ai_rank_1_8_selected_volume_gt1_risk_multiplier_lt2"
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
import stage010_quality_add_risk_proxy as s010


OUTPUT_DIR = LINE_DIR / "outputs" / "stage013_guarded_quality_add_risk_proxy"

STAGE010_OUTPUT_DIR = LINE_DIR / "outputs" / "stage010_quality_add_risk_proxy"
STAGE010_PREFIX = "rebuilt_c9_v2_stage010_quality_add_risk_proxy"
STAGE010_TAG = "stage010_quality_add_risk_proxy_v1"
STAGE010_LOT_DELTAS_PATH = STAGE010_OUTPUT_DIR / f"{STAGE010_PREFIX}_lot_deltas_{STAGE010_TAG}.csv.gz"
STAGE010_AGGREGATE_PATH = STAGE010_OUTPUT_DIR / f"{STAGE010_PREFIX}_goal_aggregate_{STAGE010_TAG}.csv"
STAGE010_RETENTION_PATH = STAGE010_OUTPUT_DIR / f"{STAGE010_PREFIX}_retention_vs_stage013_{STAGE010_TAG}.csv"

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
STAGE_RECORD_PATH = LINE_DIR / "stages" / "20260702_0448_stage013_guarded_quality_add_risk_proxy.md"


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


def select_guarded_quality_events(stage010_lot_deltas: pd.DataFrame) -> pd.DataFrame:
    risk_multiplier = _numeric(stage010_lot_deltas, "risk_multiplier")
    return stage010_lot_deltas.loc[risk_multiplier.lt(2.0)].copy().reset_index(drop=True)


def build_guarded_lot_deltas(stage010_lot_deltas: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    selected = select_guarded_quality_events(stage010_lot_deltas)
    result = selected.copy()
    if result.empty:
        result["stage013_selector"] = []
        result["stage013_add_risk_fraction"] = []
        result["stage013_proxy_delta_pnl"] = []
    else:
        if "requested_start_month" not in result.columns:
            result["requested_start_month"] = ""
        if "entry_date" not in result.columns:
            result["entry_date"] = pd.NaT
        if "exit_date" not in result.columns:
            result["exit_date"] = pd.NaT
        result["requested_start_month"] = result["requested_start_month"].astype(str)
        result["entry_date"] = pd.to_datetime(result["entry_date"], errors="coerce").dt.normalize()
        result["exit_date"] = pd.to_datetime(result["exit_date"], errors="coerce").dt.normalize()
        result["realized_pnl"] = _numeric(result, "realized_pnl", 0.0).fillna(0.0)
        result["stage013_selector"] = SELECTOR_NAME
        result["stage013_add_risk_fraction"] = ADD_RISK_FRACTION
        result["stage013_proxy_delta_pnl"] = result["realized_pnl"] * ADD_RISK_FRACTION
    audit = {
        "selector": SELECTOR_NAME,
        "add_risk_fraction": ADD_RISK_FRACTION,
        "stage010_selected_lot_count": int(len(stage010_lot_deltas)),
        "stage013_guarded_lot_count": int(len(result)),
        "excluded_risk_multiplier_ge2_count": int(len(stage010_lot_deltas) - len(result)),
        "guarded_source_count": int(result["requested_start_month"].nunique()) if "requested_start_month" in result else 0,
        "guarded_year_count": int(result["entry_date"].dt.year.nunique()) if "entry_date" in result and len(result) else 0,
        "guarded_product_count": int(result["product"].nunique()) if "product" in result and len(result) else 0,
        "guarded_realized_pnl": float(_numeric(result, "realized_pnl", 0.0).sum()) if len(result) else 0.0,
        "guarded_proxy_delta_pnl": float(_numeric(result, "stage013_proxy_delta_pnl", 0.0).sum()) if len(result) else 0.0,
        "excluded_realized_pnl": float(
            _numeric(stage010_lot_deltas, "realized_pnl", 0.0).sum() - _numeric(result, "realized_pnl", 0.0).sum()
        ),
        "guarded_bad_path_rate_pct": float(_numeric(result, "bad_path", 0.0).mean() * 100.0) if len(result) else np.nan,
        "guarded_big_winner_rate_pct": float(_numeric(result, "big_winner", 0.0).mean() * 100.0) if len(result) else np.nan,
    }
    return result.reset_index(drop=True), audit


def build_proxy_curves(base_curves: pd.DataFrame, lot_deltas: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    curves = base_curves.copy()
    curves["date"] = pd.to_datetime(curves["date"], errors="coerce").dt.normalize()
    curves["requested_start_month"] = curves["requested_start_month"].astype(str)
    curves["account_equity"] = pd.to_numeric(curves["account_equity"], errors="coerce")
    daily_delta = (
        lot_deltas.groupby(["requested_start_month", "exit_date"], dropna=False)["stage013_proxy_delta_pnl"]
        .sum()
        .reset_index()
        if not lot_deltas.empty
        else pd.DataFrame(columns=["requested_start_month", "exit_date", "stage013_proxy_delta_pnl"])
    )
    merged = curves.merge(
        daily_delta.rename(columns={"exit_date": "date", "stage013_proxy_delta_pnl": "stage013_daily_delta"}),
        on=["requested_start_month", "date"],
        how="left",
    )
    merged["stage013_daily_delta"] = pd.to_numeric(merged["stage013_daily_delta"], errors="coerce").fillna(0.0)
    frames: list[pd.DataFrame] = []
    for _, group in merged.groupby("requested_start_month", sort=True):
        g = group.sort_values("date").copy()
        g["stage013_guarded_cum_delta"] = g["stage013_daily_delta"].cumsum()
        g["stage013_guarded_account_equity"] = g["account_equity"] + g["stage013_guarded_cum_delta"]
        g["stage013_guarded_nav"] = g["stage013_guarded_account_equity"] / CAPITAL
        g["stage013_guarded_drawdown_pct"] = _drawdown_pct(g["stage013_guarded_account_equity"])
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
        rows.append(_summarize_curve(group, "account_equity", "stage013_engine"))
        rows.append(_summarize_curve(group, "stage013_guarded_account_equity", "stage013_guarded_quality_add_risk_proxy"))
    return pd.DataFrame(rows).sort_values(["variant", "requested_start_month"]).reset_index(drop=True)


def _wide_summary(summary: pd.DataFrame) -> pd.DataFrame:
    pivots = []
    for metric in ["end_equity", "total_return_pct", "max_dd_pct", "sharpe"]:
        pivot = summary.pivot(index="requested_start_month", columns="variant", values=metric)
        pivot.columns = [f"{metric}_{column}" for column in pivot.columns]
        pivots.append(pivot)
    wide = pd.concat(pivots, axis=1).reset_index()
    wide["return_delta_pp_stage013_guarded_vs_base"] = (
        wide["total_return_pct_stage013_guarded_quality_add_risk_proxy"] - wide["total_return_pct_stage013_engine"]
    )
    wide["maxdd_delta_pp_stage013_guarded_vs_base"] = (
        wide["max_dd_pct_stage013_guarded_quality_add_risk_proxy"] - wide["max_dd_pct_stage013_engine"]
    )
    return wide.sort_values("requested_start_month").reset_index(drop=True)


def _goal_audit(proxy_curves: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    parts = []
    for variant, column in [
        ("stage013_engine", "account_equity"),
        ("stage013_guarded_quality_add_risk_proxy", "stage013_guarded_account_equity"),
    ]:
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
    wide["stage013_guarded_vs_base_return_ratio"] = (
        pd.to_numeric(wide["total_return_pct_stage013_guarded_quality_add_risk_proxy"], errors="coerce")
        / pd.to_numeric(wide["total_return_pct_stage013_engine"], errors="coerce").replace(0.0, np.nan)
    )
    wide["passes_80pct_retention_vs_stage013"] = (
        wide["total_return_pct_stage013_guarded_quality_add_risk_proxy"]
        >= wide["total_return_pct_stage013_engine"] * 0.8
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


def _stage010_comparison() -> dict[str, Any]:
    if not STAGE010_AGGREGATE_PATH.exists():
        return {}
    aggregate = _read_csv(STAGE010_AGGREGATE_PATH)
    retention = _read_csv(STAGE010_RETENTION_PATH) if STAGE010_RETENTION_PATH.exists() else pd.DataFrame()
    metrics = _strict_metrics(aggregate, "stage010_quality_add_risk_proxy")
    if not retention.empty and "total_return_pct_stage010_quality_add_risk_proxy" in retention.columns:
        metrics["stage010_to_final_min_return_pct_from_retention"] = float(
            pd.to_numeric(retention["total_return_pct_stage010_quality_add_risk_proxy"], errors="coerce").min()
        )
    return metrics


def _decision(
    summary: pd.DataFrame,
    aggregate: pd.DataFrame,
    retention: pd.DataFrame,
    audit: dict[str, Any],
    unmatched_delta_dates: int,
) -> dict[str, Any]:
    wide = _wide_summary(summary)
    candidate = "stage013_guarded_quality_add_risk_proxy"
    base = "stage013_engine"
    base_metrics = _strict_metrics(aggregate, base)
    candidate_metrics = _strict_metrics(aggregate, candidate)
    stage010_metrics = _stage010_comparison()
    candidate_neg = candidate_metrics.get(f"{candidate}_all_gt1y_negative_count", 0)
    base_neg = base_metrics.get(f"{base}_all_gt1y_negative_count", 0)
    stage010_neg = stage010_metrics.get("stage010_quality_add_risk_proxy_all_gt1y_negative_count")
    retention_pass = int(retention["passes_80pct_retention_vs_stage013"].sum()) if not retention.empty else 0
    if candidate_neg <= 0 and retention_pass == len(retention):
        decision = "stage013_goal_pass_candidate_needs_true_engine_validation"
        reason = "guarded proxy 已满足严格 >365 天无负窗口和 80% 收益保留，但仍是 proxy，必须进入真实引擎验证。"
    elif stage010_neg is not None and candidate_neg < int(stage010_neg):
        decision = "stage013_guarded_proxy_improves_stage010_left_tail_need_true_engine"
        reason = "guarded proxy 相比 Stage010 减少严格负窗口，同时保持 80% 收益保留；下一步应做真实引擎或更细路径校验。"
    elif candidate_neg < base_neg:
        decision = "stage013_guarded_proxy_improves_base_but_not_stage010"
        reason = "guarded proxy 改善 base 左尾，但未确认优于 Stage010；保留为研究线索，不进入正式候选。"
    else:
        decision = "stage013_guarded_proxy_not_promoted"
        reason = "guarded proxy 没有改善严格路径目标或收益保留，不继续此形状。"
    result: dict[str, Any] = {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "baseline_A": "stage013_account_state_pilot_gate_engine",
        "candidate_C": candidate,
        "audit_type": "closed_lot_read_only_guarded_add_risk_proxy",
        **audit,
        **base_metrics,
        **candidate_metrics,
        **stage010_metrics,
        "unmatched_delta_dates": int(unmatched_delta_dates),
        "sample_count": int(wide["requested_start_month"].nunique()),
        "candidate_min_return_pct": float(wide["total_return_pct_stage013_guarded_quality_add_risk_proxy"].min()),
        "candidate_median_return_pct": float(wide["total_return_pct_stage013_guarded_quality_add_risk_proxy"].median()),
        "candidate_worst_max_dd_pct": float(wide["max_dd_pct_stage013_guarded_quality_add_risk_proxy"].min()),
        "candidate_median_max_dd_pct": float(wide["max_dd_pct_stage013_guarded_quality_add_risk_proxy"].median()),
        "return_improved_count_vs_base": int(wide["return_delta_pp_stage013_guarded_vs_base"].gt(EPS).sum()),
        "return_worse_count_vs_base": int(wide["return_delta_pp_stage013_guarded_vs_base"].lt(-EPS).sum()),
        "maxdd_improved_count_vs_base": int(wide["maxdd_delta_pp_stage013_guarded_vs_base"].gt(EPS).sum()),
        "maxdd_worse_count_vs_base": int(wide["maxdd_delta_pp_stage013_guarded_vs_base"].lt(-EPS).sum()),
        "retention_vs_stage013_pass_count": retention_pass,
        "retention_rows": int(len(retention)),
        "strategy_changed": False,
        "true_engine": False,
        "order_api_called": False,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "ctp_connected": False,
        "decision": decision,
        "decision_reason": reason,
        "external_research_judgment": (
            "Meta-labeling/bet-sizing can justify adding risk only when the primary signal is already present and "
            "the risk layer avoids doubling exposure during stress states. risk_multiplier<2 is an existing strategy "
            "state, not a fitted product/date rule."
        ),
        "overfit_reflection_before": (
            "中等偏低。risk_multiplier<2 来自 Stage012 预声明 guard 家族和既有风险状态；但它是从 Stage011 失败归因里挑出的 near-miss，必须只当 proxy。"
        ),
        "continue_value_before": (
            "有价值。它保留 Stage010 约 99.3% 选中 PnL，同时修复 focus proxy 拖累，值得用完整路径 proxy 验证。"
        ),
        "overfit_reflection_after": (
            "待本次结果判断；若失败后继续叠 active/corr/rsi 或调 risk_multiplier 阈值，就是过拟合。"
        ),
        "continue_value_after": (
            "待本次结果判断；只有严格负窗口和收益保留同时改善，才值得真实引擎。"
        ),
        "official_live_impact": {
            "strategy_changed": False,
            "official_live_config_changed": False,
            "order_api_called": False,
            "ctp_connected": False,
            "research_only": True,
        },
    }
    return result


def _plot_curves(proxy_curves: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 1, figsize=(17, 9), sharex=True, constrained_layout=True)
    for source, group in proxy_curves.groupby("requested_start_month", sort=True):
        g = group.sort_values("date")
        axes[0].plot(g["date"], g["stage013_guarded_account_equity"], linewidth=0.9, label=str(source))
        axes[1].plot(g["date"], g["stage013_guarded_drawdown_pct"], linewidth=0.8, label=str(source))
    axes[0].axhline(CAPITAL, color="#111827", linestyle="--", linewidth=0.8, label="initial 150k")
    axes[0].set_title("Stage013 Guarded Quality Add Risk Absolute Account Equity")
    axes[0].set_ylabel("account equity")
    axes[0].grid(True, alpha=0.25)
    axes[1].set_title("Stage013 Guarded Quality Add Risk Drawdown")
    axes[1].set_ylabel("drawdown %")
    axes[1].set_xlabel("date")
    axes[1].grid(True, alpha=0.25)
    axes[0].legend(loc="upper left", ncol=4, fontsize=7)
    axes[1].legend(loc="lower left", ncol=4, fontsize=7)
    fig.savefig(CHART_PATH, dpi=160)
    plt.close(fig)


def _write_report(decision: dict[str, Any], summary: pd.DataFrame, aggregate: pd.DataFrame, retention: pd.DataFrame) -> None:
    text = f"""# Stage013 Guarded Quality Add-risk Proxy

- line_id：`{LINE_ID}`
- 记录时间：{decision["generated_at"]}
- 决策：`{decision["decision"]}`

## 假设

冻结 Stage010 质量条件 `AI rank 1-8 + selected_volume>1`，只在 `risk_multiplier<2` 时叠加固定 `+25%` 非挤占 proxy。理由是 `risk_multiplier>=2` 已经代表策略自身处于加风险或恢复状态，再叠加 Stage010 可能重复放大压力段。

## 结果概要

```json
{json.dumps(_json_safe({k: decision[k] for k in [
    "stage010_selected_lot_count",
    "stage013_guarded_lot_count",
    "excluded_risk_multiplier_ge2_count",
    "guarded_realized_pnl",
    "guarded_proxy_delta_pnl",
    "candidate_min_return_pct",
    "candidate_worst_max_dd_pct",
    "retention_vs_stage013_pass_count",
    "retention_rows",
]}), ensure_ascii=False, indent=2)}
```

## 多起点摘要

{_md_table(summary, max_rows=34)}

## 严格窗口摘要

{_md_table(aggregate, max_rows=20)}

## 收益保留

{_md_table(retention, max_rows=20)}

## 结论

- {decision["decision_reason"]}
- 本阶段仍是 closed-lot proxy，不是真实引擎，不改实盘。

## 过拟合反思

- 运行前：{decision["overfit_reflection_before"]}
- 运行后：{decision["overfit_reflection_after"]}

## 继续价值反思

- 运行前：{decision["continue_value_before"]}
- 运行后：{decision["continue_value_after"]}
"""
    REPORT_PATH.write_text(text, encoding="utf-8")


def _write_stage_record(decision: dict[str, Any], summary: pd.DataFrame, aggregate: pd.DataFrame, retention: pd.DataFrame) -> None:
    text = f"""# Stage013 Guarded Quality Add-risk Proxy

- line_id：`{LINE_ID}`
- 当前模式：day
- 记录时间：{decision["generated_at"]}
- 阶段性质：closed-lot 非挤占加风险 proxy；不改官方 live config、不连接 CTP、不调用下单
- 是否重要突破：否
- 是否触发A/B：否；本阶段只是 v2 研究线 proxy，若结果显著再进入真实引擎 A/B

## 外部调研与判断

- 参考资料：Lopez de Prado / Hudson & Thames meta-labeling、trend-following right-tail/risk sizing、pysystemtrade capital/risk overlay。
- 我的判断：二级质量层可以做加风险，但不能在策略自身已经提高 `risk_multiplier` 的状态里盲目重复加风险。

## 本次变更

- 新增脚本：`research/lines/{LINE_ID}/tools/stage013_guarded_quality_add_risk_proxy.py`
- 新增测试：`tests/test_rebuilt_c9_v2_stage013_guarded_quality_proxy.py`
- 新增参数：`SELECTOR={SELECTOR_NAME}`、`ADD_RISK_FRACTION={ADD_RISK_FRACTION}`
- 修改参数：无
- 删除参数：Stage010 选中 lot 中 `risk_multiplier>=2` 不参与本阶段加风险 proxy

## 结果

- Stage010 selected lots：`{decision["stage010_selected_lot_count"]}`
- Stage013 guarded lots：`{decision["stage013_guarded_lot_count"]}`
- excluded risk_multiplier>=2：`{decision["excluded_risk_multiplier_ge2_count"]}`
- guarded realized PnL：`{decision["guarded_realized_pnl"]:.2f}`
- guarded proxy delta：`{decision["guarded_proxy_delta_pnl"]:.2f}`
- 期末最差收益：`{decision["candidate_min_return_pct"]:.4f}%`
- 最差最大回撤：`{decision["candidate_worst_max_dd_pct"]:.4f}%`
- 80% 收益保留：`{decision["retention_vs_stage013_pass_count"]}/{decision["retention_rows"]}`
- 严格 >365 天负窗口：`{decision["stage013_guarded_quality_add_risk_proxy_all_gt1y_negative_count"]}/{decision["stage013_guarded_quality_add_risk_proxy_all_gt1y_window_count"]}`
- 严格最差窗口收益：`{decision["stage013_guarded_quality_add_risk_proxy_all_gt1y_min_return_pct"]:.4f}%`
- 决策：`{decision["decision"]}`
- 原因：{decision["decision_reason"]}

## 多起点摘要

{_md_table(summary, max_rows=34)}

## 严格窗口摘要

{_md_table(aggregate, max_rows=20)}

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
    stage010_lots = _read_csv(STAGE010_LOT_DELTAS_PATH)
    base_curves = _read_csv(STAGE013_CURVES_PATH)
    lot_deltas, audit = build_guarded_lot_deltas(stage010_lots)
    proxy_curves, unmatched = build_proxy_curves(base_curves, lot_deltas)
    summary = _summary(proxy_curves)
    ab_summary = _wide_summary(summary)
    aggregate, to_final, fixed_horizon, worst_windows = _goal_audit(proxy_curves)
    retention = _retention(summary)
    decision = _decision(summary, aggregate, retention, audit, unmatched)
    if decision["decision"] == "stage013_guarded_proxy_improves_stage010_left_tail_need_true_engine":
        decision["overfit_reflection_after"] = (
            "否，但仍需谨慎。该 proxy 用既有 risk_multiplier 状态过滤，未按产品/日期救参；下一步必须真实引擎验证。"
        )
        decision["continue_value_after"] = "有价值。若真实引擎也保留改善，可进入正式 A/B；否则回退。"
    elif decision["decision"] == "stage013_goal_pass_candidate_needs_true_engine_validation":
        decision["overfit_reflection_after"] = (
            "中等。proxy 达标但仍不是实际撮合路径，必须用真实引擎和更多分段反证。"
        )
        decision["continue_value_after"] = "有价值。应立即进入真实引擎验证，而不是继续加条件。"
    else:
        decision["overfit_reflection_after"] = (
            "否。本阶段冻结单一结构假设，结果不支持时不继续叠加条件。"
        )
        decision["continue_value_after"] = "有限。若未优于 Stage010，应转向新 PIT 信息源或真实持仓路径。"
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
    return decision


if __name__ == "__main__":
    print(json.dumps(_json_safe(run()), ensure_ascii=False, indent=2))
