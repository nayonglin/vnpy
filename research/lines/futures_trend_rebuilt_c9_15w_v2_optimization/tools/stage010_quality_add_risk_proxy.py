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
STAGE = "Stage010"
MODEL_TAG = "stage010_quality_add_risk_proxy_v1"
OUTPUT_PREFIX = "rebuilt_c9_v2_stage010_quality_add_risk_proxy"
SELECTOR_NAME = "ai_rank_1_8_and_selected_volume_gt1"
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


OUTPUT_DIR = LINE_DIR / "outputs" / "stage010_quality_add_risk_proxy"
STAGE009_OUTPUT_DIR = LINE_DIR / "outputs" / "stage009_meta_label_entry_quality_audit"
STAGE009_PREFIX = "rebuilt_c9_v2_stage009_meta_label_entry_quality_audit"
STAGE009_TAG = "stage009_meta_label_entry_quality_audit_v1"
STAGE009_EVENTS_PATH = STAGE009_OUTPUT_DIR / f"{STAGE009_PREFIX}_quality_events_{STAGE009_TAG}.csv.gz"

STAGE013_OUTPUT_DIR = UPSTREAM_LINE_DIR / "outputs" / "stage013_account_state_pilot_gate_engine"
STAGE013_PREFIX = "rebuilt_c9_stage013_account_state_pilot_gate_engine"
STAGE013_TAG = "stage013_account_state_pilot_gate_engine_v1"
STAGE013_CURVES_PATH = STAGE013_OUTPUT_DIR / f"{STAGE013_PREFIX}_curves_{STAGE013_TAG}.csv"
STAGE013_SUMMARY_PATH = STAGE013_OUTPUT_DIR / f"{STAGE013_PREFIX}_summary_{STAGE013_TAG}.csv"

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
STAGE_RECORD_PATH = LINE_DIR / "stages" / "20260702_0429_stage010_quality_add_risk_proxy.md"


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


def select_stage010_quality_events(events: pd.DataFrame) -> pd.DataFrame:
    rank = _numeric(events, "ai_product_pool_rank")
    selected_volume = _numeric(events, "selected_volume")
    mask = rank.ge(1) & rank.le(8) & selected_volume.gt(1)
    return events.loc[mask].copy().reset_index(drop=True)


def build_lot_deltas(events: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    selected = select_stage010_quality_events(events)
    result = selected.copy()
    result["requested_start_month"] = result["requested_start_month"].astype(str)
    result["entry_date"] = pd.to_datetime(result["entry_date"], errors="coerce").dt.normalize()
    result["exit_date"] = pd.to_datetime(result["exit_date"], errors="coerce").dt.normalize()
    result["realized_pnl"] = pd.to_numeric(result["realized_pnl"], errors="coerce").fillna(0.0)
    result["stage010_selector"] = SELECTOR_NAME
    result["stage010_add_risk_fraction"] = ADD_RISK_FRACTION
    result["stage010_proxy_delta_pnl"] = result["realized_pnl"] * ADD_RISK_FRACTION
    audit = {
        "selector": SELECTOR_NAME,
        "add_risk_fraction": ADD_RISK_FRACTION,
        "quality_event_count": int(len(events)),
        "selected_lot_count": int(len(result)),
        "selected_source_count": int(result["requested_start_month"].nunique()) if not result.empty else 0,
        "selected_year_count": int(result["entry_date"].dt.year.nunique()) if not result.empty else 0,
        "selected_product_count": int(result["product"].nunique()) if "product" in result.columns and not result.empty else 0,
        "selected_realized_pnl": float(result["realized_pnl"].sum()) if not result.empty else 0.0,
        "proxy_delta_pnl": float(result["stage010_proxy_delta_pnl"].sum()) if not result.empty else 0.0,
        "selected_big_winner_rate_pct": float(_numeric(result, "big_winner").mean() * 100.0) if not result.empty else np.nan,
        "selected_bad_path_rate_pct": float(_numeric(result, "bad_path").mean() * 100.0) if not result.empty else np.nan,
    }
    return result.reset_index(drop=True), audit


def build_proxy_curves(base_curves: pd.DataFrame, lot_deltas: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    curves = base_curves.copy()
    curves["date"] = pd.to_datetime(curves["date"], errors="coerce").dt.normalize()
    curves["requested_start_month"] = curves["requested_start_month"].astype(str)
    curves["account_equity"] = pd.to_numeric(curves["account_equity"], errors="coerce")
    daily_delta = (
        lot_deltas.groupby(["requested_start_month", "exit_date"], dropna=False)["stage010_proxy_delta_pnl"]
        .sum()
        .reset_index()
        if not lot_deltas.empty
        else pd.DataFrame(columns=["requested_start_month", "exit_date", "stage010_proxy_delta_pnl"])
    )
    merged = curves.merge(
        daily_delta.rename(columns={"exit_date": "date", "stage010_proxy_delta_pnl": "stage010_daily_delta"}),
        on=["requested_start_month", "date"],
        how="left",
    )
    merged["stage010_daily_delta"] = pd.to_numeric(merged["stage010_daily_delta"], errors="coerce").fillna(0.0)
    frames: list[pd.DataFrame] = []
    for _, group in merged.groupby("requested_start_month", sort=True):
        g = group.sort_values("date").copy()
        g["stage010_cum_delta"] = g["stage010_daily_delta"].cumsum()
        g["stage010_account_equity"] = g["account_equity"] + g["stage010_cum_delta"]
        g["stage010_nav"] = g["stage010_account_equity"] / CAPITAL
        g["stage010_drawdown_pct"] = _drawdown_pct(g["stage010_account_equity"])
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
        rows.append(_summarize_curve(group, "stage010_account_equity", "stage010_quality_add_risk_proxy"))
    return pd.DataFrame(rows).sort_values(["variant", "requested_start_month"]).reset_index(drop=True)


def _wide_summary(summary: pd.DataFrame) -> pd.DataFrame:
    pivots = []
    for metric in ["end_equity", "total_return_pct", "max_dd_pct", "sharpe"]:
        pivot = summary.pivot(index="requested_start_month", columns="variant", values=metric)
        pivot.columns = [f"{metric}_{column}" for column in pivot.columns]
        pivots.append(pivot)
    wide = pd.concat(pivots, axis=1).reset_index()
    wide["return_delta_pp_stage010_vs_stage013"] = (
        wide["total_return_pct_stage010_quality_add_risk_proxy"] - wide["total_return_pct_stage013_engine"]
    )
    wide["maxdd_delta_pp_stage010_vs_stage013"] = (
        wide["max_dd_pct_stage010_quality_add_risk_proxy"] - wide["max_dd_pct_stage013_engine"]
    )
    return wide.sort_values("requested_start_month").reset_index(drop=True)


def _goal_audit(proxy_curves: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    parts = []
    for variant, column in [
        ("stage013_engine", "account_equity"),
        ("stage010_quality_add_risk_proxy", "stage010_account_equity"),
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
    wide["stage010_vs_stage013_return_ratio"] = (
        pd.to_numeric(wide["total_return_pct_stage010_quality_add_risk_proxy"], errors="coerce")
        / pd.to_numeric(wide["total_return_pct_stage013_engine"], errors="coerce").replace(0.0, np.nan)
    )
    wide["passes_80pct_retention_vs_stage013"] = (
        wide["total_return_pct_stage010_quality_add_risk_proxy"]
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


def _decision(
    summary: pd.DataFrame,
    aggregate: pd.DataFrame,
    retention: pd.DataFrame,
    audit: dict[str, Any],
    unmatched_delta_dates: int,
) -> dict[str, Any]:
    wide = _wide_summary(summary)
    result: dict[str, Any] = {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "baseline_A": "stage013_account_state_pilot_gate_engine",
        "candidate_C": "stage010_quality_add_risk_proxy",
        "audit_type": "closed_lot_read_only_non_overwriting_add_risk_proxy",
        **audit,
        "unmatched_delta_dates": int(unmatched_delta_dates),
        "sample_count": int(wide["requested_start_month"].nunique()),
        "stage010_min_return_pct": float(wide["total_return_pct_stage010_quality_add_risk_proxy"].min()),
        "stage010_median_return_pct": float(wide["total_return_pct_stage010_quality_add_risk_proxy"].median()),
        "stage010_worst_max_dd_pct": float(wide["max_dd_pct_stage010_quality_add_risk_proxy"].min()),
        "stage010_median_max_dd_pct": float(wide["max_dd_pct_stage010_quality_add_risk_proxy"].median()),
        "return_improved_count_vs_stage013": int(wide["return_delta_pp_stage010_vs_stage013"].gt(EPS).sum()),
        "return_unchanged_count_vs_stage013": int(wide["return_delta_pp_stage010_vs_stage013"].abs().le(EPS).sum()),
        "return_worse_count_vs_stage013": int(wide["return_delta_pp_stage010_vs_stage013"].lt(-EPS).sum()),
        "maxdd_improved_count_vs_stage013": int(wide["maxdd_delta_pp_stage010_vs_stage013"].gt(EPS).sum()),
        "maxdd_unchanged_count_vs_stage013": int(wide["maxdd_delta_pp_stage010_vs_stage013"].abs().le(EPS).sum()),
        "maxdd_worse_count_vs_stage013": int(wide["maxdd_delta_pp_stage010_vs_stage013"].lt(-EPS).sum()),
        "retention_vs_stage013_pass_count": int(retention["passes_80pct_retention_vs_stage013"].sum()),
        "retention_rows": int(len(retention)),
        "strategy_changed": False,
        "true_engine": False,
        "order_api_called": False,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "ctp_connected": False,
        "external_research_judgment": (
            "Meta-labeling supports using a secondary quality layer for bet sizing, but this Stage010 run is only a "
            "frozen closed-lot proxy for Stage009's strongest broad candidate, not a real trading engine."
        ),
        "overfit_reflection_before": (
            "有风险但可控。候选来自 Stage009 closed-lot 元标签；本阶段只冻结一个条件和固定 25% 非挤占比例，不扫 rank/topN/产品/日期。"
        ),
        "continue_value_before": (
            "有价值。它直接检验 Stage009 质量候选是否能转成多起点资金曲线改善，而不是只看逐笔均值。"
        ),
        "overfit_reflection_after": (
            "待结果判断；如果失败后改 rank/topN、加品种方向过滤或调 25%，就是过拟合。"
        ),
    }
    result.update(_strict_metrics(aggregate, "stage013_engine"))
    result.update(_strict_metrics(aggregate, "stage010_quality_add_risk_proxy"))
    strict_negative = result["stage010_quality_add_risk_proxy_all_gt1y_negative_count"]
    base_negative = result["stage013_engine_all_gt1y_negative_count"]
    retention_full = result["retention_vs_stage013_pass_count"] == result["retention_rows"]
    if strict_negative == 0 and retention_full:
        decision = "stage010_proxy_meets_goal_requires_true_engine"
        continue_after = "有。proxy 达到目标形状，下一步必须进真实引擎验真，不能直接上线。"
    elif strict_negative < base_negative and retention_full:
        decision = "stage010_proxy_improves_left_tail_need_failure_attribution"
        continue_after = "有但未达标。候选能改善左尾数量并保留收益，下一步归因剩余负窗口或进更严格 proxy。"
    else:
        decision = "stage010_proxy_not_promoted_no_param_rescue"
        continue_after = "有限。若没有改善严格负窗口或收益保留失败，不应继续调同一候选。"
    result["decision"] = decision
    result["continue_value_after"] = continue_after
    result["outputs"] = {
        "lot_deltas": str(LOT_DELTAS_PATH),
        "curves": str(CURVES_PATH),
        "summary": str(SUMMARY_PATH),
        "ab_summary": str(AB_SUMMARY_PATH),
        "goal_aggregate": str(GOAL_AGGREGATE_PATH),
        "goal_to_final": str(GOAL_TO_FINAL_PATH),
        "goal_fixed_horizon": str(GOAL_FIXED_HORIZON_PATH),
        "goal_worst_windows": str(GOAL_WORST_WINDOWS_PATH),
        "retention": str(RETENTION_PATH),
        "chart": str(CHART_PATH),
        "decision": str(DECISION_PATH),
        "report": str(REPORT_PATH),
        "stage_record": str(STAGE_RECORD_PATH),
    }
    return result


def _plot_performance(curves: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 1, figsize=(18, 11), sharex=True, constrained_layout=True)
    for start, group in curves.groupby("requested_start_month"):
        group = group.sort_values("date")
        axes[0].plot(group["date"], group["stage010_account_equity"], linewidth=0.9, alpha=0.76, label=str(start))
        axes[1].plot(group["date"], group["stage010_drawdown_pct"], linewidth=0.9, alpha=0.76, label=str(start))
    axes[0].axhline(CAPITAL, color="#111827", linestyle="--", linewidth=0.9, label="initial 150k")
    axes[0].set_title("Stage010 Absolute Account Equity By Cold Start")
    axes[0].set_ylabel("account equity")
    axes[1].set_title("Stage010 Drawdown By Cold Start")
    axes[1].set_ylabel("drawdown %")
    axes[1].set_xlabel("date")
    for ax in axes:
        ax.grid(True, alpha=0.25)
        ax.legend(fontsize=7, ncol=3, loc="best")
    fig.savefig(CHART_PATH, dpi=160)
    plt.close(fig)


def _write_report(decision: dict[str, Any], summary: pd.DataFrame, aggregate: pd.DataFrame, retention: pd.DataFrame) -> None:
    wide = _wide_summary(summary)
    strict = aggregate[
        aggregate["variant"].eq("stage010_quality_add_risk_proxy")
        & aggregate["audit_scope"].eq("all_trading_end_dates_gt_1y")
    ]
    lines = [
        "# Stage010 - Stage009 质量候选非挤占加风险 proxy",
        "",
        f"- 生成时间：`{decision['generated_at']}`",
        f"- 决策：`{decision['decision']}`",
        "- 阶段性质：closed-lot 只读 proxy；不是真实组合引擎，不改 C9，不连接 CTP，不调用下单。",
        f"- selector：`{SELECTOR_NAME}`",
        f"- 固定额外风险比例：`{ADD_RISK_FRACTION:.2%}`",
        "",
        "## 核心结果",
        "",
        f"- 选中 lots：`{decision['selected_lot_count']}`；selected realized PnL `{decision['selected_realized_pnl']:,.2f}`；proxy delta `{decision['proxy_delta_pnl']:,.2f}`。",
        f"- Stage010 严格任意 `>1` 年负窗口：`{decision['stage010_quality_add_risk_proxy_all_gt1y_negative_count']}` / `{decision['stage010_quality_add_risk_proxy_all_gt1y_window_count']}`；最差 `{decision['stage010_quality_add_risk_proxy_all_gt1y_min_return_pct']:.4f}%`。",
        f"- Stage013 严格任意 `>1` 年负窗口：`{decision['stage013_engine_all_gt1y_negative_count']}`。",
        f"- 到 `2026-06-30` 负窗口：`{decision['stage010_quality_add_risk_proxy_to_final_negative_count']}`；最差 `{decision['stage010_quality_add_risk_proxy_to_final_min_return_pct']:.4f}%`。",
        f"- 80% 收益保留 vs Stage013：`{decision['retention_vs_stage013_pass_count']}/{decision['retention_rows']}`。",
        f"- 收益改善/不变/变差 vs Stage013：`{decision['return_improved_count_vs_stage013']}/{decision['return_unchanged_count_vs_stage013']}/{decision['return_worse_count_vs_stage013']}`。",
        f"- 回撤改善/不变/变差 vs Stage013：`{decision['maxdd_improved_count_vs_stage013']}/{decision['maxdd_unchanged_count_vs_stage013']}/{decision['maxdd_worse_count_vs_stage013']}`。",
        "",
        "## 多起点摘要",
        "",
        _md_table(
            wide[
                [
                    "requested_start_month",
                    "total_return_pct_stage013_engine",
                    "total_return_pct_stage010_quality_add_risk_proxy",
                    "return_delta_pp_stage010_vs_stage013",
                    "max_dd_pct_stage013_engine",
                    "max_dd_pct_stage010_quality_add_risk_proxy",
                    "maxdd_delta_pp_stage010_vs_stage013",
                ]
            ],
            max_rows=30,
        ),
        "",
        "## 严格目标审计",
        "",
        _md_table(strict, max_rows=30),
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
    wide = _wide_summary(summary)
    strict = aggregate[
        aggregate["variant"].eq("stage010_quality_add_risk_proxy")
        & aggregate["audit_scope"].eq("all_trading_end_dates_gt_1y")
    ]
    record = f"""# Stage010 Stage009 质量候选非挤占加风险 proxy

- line_id：`{LINE_ID}`
- 当前模式：day
- 记录时间：{decision["generated_at"]}
- 阶段性质：closed-lot 只读 proxy；不改官方 live config、不连接 CTP、不调用下单
- 是否重要突破：否
- 是否触发A/B：是，A=Stage013，C=Stage013 + `{SELECTOR_NAME}` 固定 `+25%` 非挤占 proxy

## 外部调研与判断

- 参考资料：Meta-labeling / bet sizing、trend-following right-tail/risk sizing、pysystemtrade capital/risk overlay。
- 我的判断：Stage009 候选只有先通过多起点路径 proxy，才值得进入真实组合引擎；逐笔均值 lift 不足以证明能上线。

## 本次变更

- 新增脚本：`research/lines/{LINE_ID}/tools/stage010_quality_add_risk_proxy.py`
- 新增测试：`tests/test_rebuilt_c9_v2_stage010_quality_add_risk_proxy.py`
- 新增参数：`SELECTOR_NAME={SELECTOR_NAME}`、`ADD_RISK_FRACTION={ADD_RISK_FRACTION}`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 输入：Stage009 quality events + Stage013 多起点资金曲线。
- C：对满足 `AI rank 1-8 + selected_volume>1` 的 closed lots，在退出日加入 `realized_pnl * 25%` 的非挤占 proxy delta。
- 注意：本阶段不是真实引擎，不产生真实新增订单、滑点、保证金或整数手路径，只作为进入真实引擎前的上界筛选。

## 结果

- 选中 lots：`{decision["selected_lot_count"]}`
- selected realized PnL：`{decision["selected_realized_pnl"]:,.2f}`
- proxy delta：`{decision["proxy_delta_pnl"]:,.2f}`
- 期末收益最小/中位：`{decision["stage010_min_return_pct"]:.4f}%` / `{decision["stage010_median_return_pct"]:.4f}%`
- 最大回撤最差/中位：`{decision["stage010_worst_max_dd_pct"]:.4f}%` / `{decision["stage010_median_max_dd_pct"]:.4f}%`
- 严格任意 `>1` 年负窗口：`{decision["stage010_quality_add_risk_proxy_all_gt1y_negative_count"]}/{decision["stage010_quality_add_risk_proxy_all_gt1y_window_count"]}`，最差 `{decision["stage010_quality_add_risk_proxy_all_gt1y_min_return_pct"]:.4f}%`
- 到 `2026-06-30` 负窗口：`{decision["stage010_quality_add_risk_proxy_to_final_negative_count"]}`，最差 `{decision["stage010_quality_add_risk_proxy_to_final_min_return_pct"]:.4f}%`
- 80% 收益保留 vs Stage013：`{decision["retention_vs_stage013_pass_count"]}/{decision["retention_rows"]}`
- 收益改善/不变/变差 vs Stage013：`{decision["return_improved_count_vs_stage013"]}/{decision["return_unchanged_count_vs_stage013"]}/{decision["return_worse_count_vs_stage013"]}`
- 回撤改善/不变/变差 vs Stage013：`{decision["maxdd_improved_count_vs_stage013"]}/{decision["maxdd_unchanged_count_vs_stage013"]}/{decision["maxdd_worse_count_vs_stage013"]}`
- 决策：`{decision["decision"]}`

## 多起点摘要

{_md_table(wide[["requested_start_month", "total_return_pct_stage013_engine", "total_return_pct_stage010_quality_add_risk_proxy", "return_delta_pp_stage010_vs_stage013", "max_dd_pct_stage013_engine", "max_dd_pct_stage010_quality_add_risk_proxy"]], max_rows=24)}

## 严格目标摘要

{_md_table(strict, max_rows=24)}

## 过拟合反思

- 运行前判断：{decision["overfit_reflection_before"]}
- 运行后判断：{decision["overfit_reflection_after"]}
- 原因：本阶段冻结一个候选和一个比例；若失败后调 rank/topN/比例或产品方向，就是过拟合。

## 继续价值反思

- 运行前判断：{decision["continue_value_before"]}
- 运行后判断：{decision["continue_value_after"]}

## 输出文件

- lot_deltas: `{decision["outputs"]["lot_deltas"]}`
- curves: `{decision["outputs"]["curves"]}`
- summary: `{decision["outputs"]["summary"]}`
- ab_summary: `{decision["outputs"]["ab_summary"]}`
- goal_aggregate: `{decision["outputs"]["goal_aggregate"]}`
- retention: `{decision["outputs"]["retention"]}`
- chart: `{decision["outputs"]["chart"]}`
- decision: `{decision["outputs"]["decision"]}`
- report: `{decision["outputs"]["report"]}`
"""
    STAGE_RECORD_PATH.write_text(record, encoding="utf-8")


def run() -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    STAGE_RECORD_PATH.parent.mkdir(parents=True, exist_ok=True)
    if STAGE009_EVENTS_PATH.exists():
        events = _read_csv(STAGE009_EVENTS_PATH)
    else:
        closed = _read_csv(s009_quality.STAGE013_CLOSED_LOTS_PATH)
        events = s009_quality.prepare_closed_lots_for_quality_audit(closed)
    lot_deltas, audit = build_lot_deltas(events)
    base_curves = _read_csv(STAGE013_CURVES_PATH, parse_dates=["date"])
    proxy_curves, unmatched = build_proxy_curves(base_curves, lot_deltas)
    summary = _summary(proxy_curves)
    ab_summary = _wide_summary(summary)
    aggregate, to_final, fixed, worst = _goal_audit(proxy_curves)
    retention = _retention(summary)
    decision = _decision(summary, aggregate, retention, audit, unmatched)
    if decision["decision"] == "stage010_proxy_not_promoted_no_param_rescue":
        decision["overfit_reflection_after"] = (
            "否。本阶段没有根据结果调参；若继续救同一条件的 rank/topN/比例/产品方向，就是过拟合。"
        )
    else:
        decision["overfit_reflection_after"] = (
            "有风险但可控。本阶段仍是 proxy，不可直接上线；若下一步进真实引擎，必须继续冻结条件和比例。"
        )

    lot_deltas.to_csv(LOT_DELTAS_PATH, index=False, encoding="utf-8-sig", compression="gzip")
    proxy_curves.to_csv(CURVES_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    ab_summary.to_csv(AB_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    aggregate.to_csv(GOAL_AGGREGATE_PATH, index=False, encoding="utf-8-sig")
    to_final.to_csv(GOAL_TO_FINAL_PATH, index=False, encoding="utf-8-sig")
    fixed.to_csv(GOAL_FIXED_HORIZON_PATH, index=False, encoding="utf-8-sig")
    worst.to_csv(GOAL_WORST_WINDOWS_PATH, index=False, encoding="utf-8-sig")
    retention.to_csv(RETENTION_PATH, index=False, encoding="utf-8-sig")
    _plot_performance(proxy_curves)
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(decision, summary, aggregate, retention)
    _write_stage_record(decision, summary, aggregate)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    return decision


if __name__ == "__main__":
    run()
