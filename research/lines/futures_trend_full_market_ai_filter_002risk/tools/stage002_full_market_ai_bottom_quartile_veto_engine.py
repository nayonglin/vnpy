#!/usr/bin/env python3
"""Stage002: full-market PIT AI bottom-quartile veto + 0.02 risk.

Stage001 proved that hard top8 positive selection destroys too much of the
trend-following right tail. This stage keeps the user's full-market AI idea,
but changes the selector from "only top8 can trade" to a broader meta-label:
rank the full market monthly and veto only the bottom quartile. The primary
C9 entry/exit logic still decides whether a product has an actual trade.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import stage001_full_market_pit_ai_risk002_engine as base


LINE_ID = base.LINE_ID
STAGE_ID = "stage002_full_market_ai_bottom_quartile_veto_engine"
STAGE_LABEL = "Stage002"
MODEL_TAG = f"{STAGE_ID}_v1"
OUTPUT_PREFIX = f"full_market_ai002_{STAGE_ID}"

CANDIDATE_VERSION = "full_market_pit_ai_bottom25_veto_risk002"
STRATEGY_NAME = "full_market_pit_profit_memory_bottom25_veto_risk002"
SCORE_TYPE = "pit_strategy_profit_memory_existing_features_bottom_quartile_veto"

BOTTOM_VETO_QUANTILE = 0.25
MIN_ACTIVE_PRODUCTS_FOR_VETO = 12

OUT = base.LINE_DIR / "outputs" / STAGE_ID
STAGES_DIR = base.LINE_DIR / "stages"
STAGE_RECORD_PATH = STAGES_DIR / "20260709_1740_stage002_full_market_ai_bottom_quartile_veto_engine.md"

FEATURE_PANEL_PATH = OUT / f"{OUTPUT_PREFIX}_feature_panel_{MODEL_TAG}.csv.gz"
ELIGIBILITY_PATH = OUT / f"{OUTPUT_PREFIX}_eligibility_{MODEL_TAG}.csv"
ELIGIBILITY_AUDIT_PATH = OUT / f"{OUTPUT_PREFIX}_eligibility_audit_{MODEL_TAG}.csv"
CANDIDATE_DAILY_PATH = OUT / f"{OUTPUT_PREFIX}_candidate_daily_{MODEL_TAG}.csv.gz"
CANDIDATE_ENTRY_CANDIDATES_PATH = OUT / f"{OUTPUT_PREFIX}_candidate_entry_candidates_{MODEL_TAG}.csv.gz"
CANDIDATE_ENTRY_RISK_PATH = OUT / f"{OUTPUT_PREFIX}_candidate_entry_risk_{MODEL_TAG}.csv.gz"
CANDIDATE_TRADES_PATH = OUT / f"{OUTPUT_PREFIX}_candidate_trades_{MODEL_TAG}.csv.gz"
CANDIDATE_TRADE_EVENTS_PATH = OUT / f"{OUTPUT_PREFIX}_candidate_trade_events_{MODEL_TAG}.csv.gz"
CURVES_PATH = OUT / f"{OUTPUT_PREFIX}_ac_curves_{MODEL_TAG}.csv.gz"
SUMMARY_PATH = OUT / f"{OUTPUT_PREFIX}_ac_summary_{MODEL_TAG}.csv"
AI_USAGE_AUDIT_PATH = OUT / f"{OUTPUT_PREFIX}_ai_usage_audit_{MODEL_TAG}.csv"
DECISION_PATH = OUT / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUT / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUT / f"{OUTPUT_PREFIX}_equity_drawdown_{MODEL_TAG}.png"


def _configure_base_globals() -> None:
    base.STAGE_ID = STAGE_ID
    base.STAGE_LABEL = STAGE_LABEL
    base.MODEL_TAG = MODEL_TAG
    base.OUTPUT_PREFIX = OUTPUT_PREFIX
    base.CANDIDATE_VERSION = CANDIDATE_VERSION
    base.STRATEGY_NAME = STRATEGY_NAME
    base.SCORE_TYPE = SCORE_TYPE
    base.OUT = OUT
    base.STAGES_DIR = STAGES_DIR
    base.STAGE_RECORD_PATH = STAGE_RECORD_PATH
    base.FEATURE_PANEL_PATH = FEATURE_PANEL_PATH
    base.ELIGIBILITY_PATH = ELIGIBILITY_PATH
    base.ELIGIBILITY_AUDIT_PATH = ELIGIBILITY_AUDIT_PATH
    base.CANDIDATE_DAILY_PATH = CANDIDATE_DAILY_PATH
    base.CANDIDATE_ENTRY_CANDIDATES_PATH = CANDIDATE_ENTRY_CANDIDATES_PATH
    base.CANDIDATE_ENTRY_RISK_PATH = CANDIDATE_ENTRY_RISK_PATH
    base.CANDIDATE_TRADES_PATH = CANDIDATE_TRADES_PATH
    base.CANDIDATE_TRADE_EVENTS_PATH = CANDIDATE_TRADE_EVENTS_PATH
    base.CURVES_PATH = CURVES_PATH
    base.SUMMARY_PATH = SUMMARY_PATH
    base.AI_USAGE_AUDIT_PATH = AI_USAGE_AUDIT_PATH
    base.DECISION_PATH = DECISION_PATH
    base.REPORT_PATH = REPORT_PATH
    base.CHART_PATH = CHART_PATH


def _apply_bottom_quartile_veto(feature_panel: pd.DataFrame) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for eval_date, group in feature_panel.groupby("eval_date", sort=True):
        data = group.copy()
        data["stage002_available_count"] = int(data["data_available"].sum())
        data["stage002_score_rank_available"] = np.nan
        data["stage002_cutoff_rank"] = np.nan
        data["stage002_vetoed"] = 0
        data["selected_topn"] = 0
        data["selection_reason"] = "insufficient_history_after_warmup"

        available = data[data["data_available"].eq(1)].copy()
        available_count = int(len(available))
        if available_count < MIN_ACTIVE_PRODUCTS_FOR_VETO:
            data["selected_topn"] = 1
            data["selection_reason"] = "cold_start_neutral_all_pass"
            data["stage002_cutoff_rank"] = int(len(data))
            data["score_rank"] = data["score"].rank(method="first", ascending=False).astype(int)
            frames.append(data)
            continue

        cutoff = max(1, int(math.ceil(available_count * (1.0 - BOTTOM_VETO_QUANTILE))))
        ranks = available["score"].rank(method="first", ascending=False).astype(int)
        selected_index = set(ranks[ranks <= cutoff].index.tolist())
        vetoed_index = set(ranks[ranks > cutoff].index.tolist())

        data.loc[available.index, "stage002_score_rank_available"] = ranks
        data["stage002_cutoff_rank"] = cutoff
        data.loc[list(selected_index), "selected_topn"] = 1
        data.loc[list(selected_index), "selection_reason"] = "ai_not_bottom_quartile"
        data.loc[list(vetoed_index), "stage002_vetoed"] = 1
        data.loc[list(vetoed_index), "selection_reason"] = "ai_bottom_quartile_veto"
        data["score_rank"] = data["score"].rank(method="first", ascending=False).astype(int)
        frames.append(data)
    result = pd.concat(frames, ignore_index=True, sort=False)
    return result.sort_values(["eval_date", "score_rank", "product_vt_symbol"]).reset_index(drop=True)


def _build_eligibility(feature_panel: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    panel = _apply_bottom_quartile_veto(feature_panel)
    selected = panel[panel["selected_topn"].eq(1)].copy()
    selected = selected.sort_values(["eval_date", "score", "product_vt_symbol"], ascending=[True, False, True])
    selected["score_rank"] = selected.groupby("eval_date").cumcount() + 1
    selected["top_n"] = selected.groupby("eval_date")["product_vt_symbol"].transform("count").astype(int)
    selected["strategy"] = STRATEGY_NAME
    selected["score_type"] = SCORE_TYPE
    eligibility = selected[
        ["strategy", "score_type", "eval_date", "product_vt_symbol", "score", "score_rank", "top_n"]
    ].copy()
    eligibility["eval_date"] = pd.to_datetime(eligibility["eval_date"], errors="coerce").dt.date.astype(str)

    audit = (
        panel.groupby("eval_date", as_index=False)
        .agg(
            all_product_count=("product_vt_symbol", "count"),
            data_available_count=("data_available", "sum"),
            selected_count=("selected_topn", "sum"),
            vetoed_count=("stage002_vetoed", "sum"),
            old_feature_rows=("existing_feature_available_count", lambda s: int((s > 0).sum())),
            min_score=("score", "min"),
            max_score=("score", "max"),
            cutoff_rank=("stage002_cutoff_rank", "max"),
        )
        .sort_values("eval_date")
    )
    audit["warmup_neutral_all_pass"] = audit["data_available_count"].lt(MIN_ACTIVE_PRODUCTS_FOR_VETO).astype(int)
    audit["eval_date"] = pd.to_datetime(audit["eval_date"], errors="coerce").dt.date.astype(str)
    return eligibility, audit


def _candidate_profile(metadata: dict[str, Any]) -> dict[str, Any]:
    profile = base.s847._c9_profile(metadata)
    spec = profile["spec"]
    profile_name = "stage002_full_market_pit_ai_bottom25_veto_risk002"
    capital = replace(
        spec.capital,
        variant=profile_name,
        label="Stage002 full-market PIT AI bottom25 veto + risk_ratio_0.02",
        account_capital=base.CAPITAL,
        c3_capital=base.CAPITAL,
        risk_multiplier=base.RISK_MULTIPLIER_FOR_LABEL,
        note=(
            f"{spec.capital.note} | Stage002 independent line. Full-market PIT bottom-quartile veto, "
            "warmup months pass all products neutrally, all risk_ratio_* fields set to 0.02."
        ),
    )
    live_overrides = dict(base.build_official_live_strategy_overrides())
    overrides = {
        **spec.overrides,
        **live_overrides,
        "product_universe_csv_path": str(base.FULL_MARKET_UNIVERSE_PATH),
        "enable_ai_product_pool_filter": True,
        "ai_product_pool_eligibility_path": str(ELIGIBILITY_PATH),
        "ai_product_pool_strategy": STRATEGY_NAME,
        "account_capital": base.CAPITAL,
        "c3_capital": base.CAPITAL,
        "risk_ratio_of_total_assets": base.TARGET_BASE_RISK_RATIO,
        "risk_ratio_breakout": base.TARGET_BASE_RISK_RATIO,
        "risk_ratio_ma_cross_breakout": base.TARGET_BASE_RISK_RATIO,
        "risk_ratio_open_interest_surge": base.TARGET_BASE_RISK_RATIO,
        "risk_ratio_open_interest_decline": base.TARGET_BASE_RISK_RATIO,
        "risk_ratio_volume_open_interest_surge": base.TARGET_BASE_RISK_RATIO,
    }
    result = dict(profile)
    result["profile"] = profile_name
    result["strategy_cls"] = base.s847.QmtRollPortfolioStrategyStage847C9StopRetry
    result["spec"] = replace(spec, capital=capital, overrides=overrides, profile=profile_name)
    return result


def _run_candidate(metadata: dict[str, Any]) -> tuple[pd.DataFrame, dict[str, pd.DataFrame], Any]:
    original_start = base.s847.START
    original_end = base.s847.END
    original_minute_by_symbol = base.s847.s827._GLOBAL_MINUTE_BY_SYMBOL
    base.s901._ensure_c9_minute_bars(metadata)
    try:
        base.s847.START = base.REQUESTED_START.normalize()
        base.s847.END = base.REQUESTED_END.normalize()
        profile = _candidate_profile(metadata)
        combined, frames = base.s847._run_profile(profile, metadata)
        spec = profile["spec"]
    finally:
        base.s847.START = original_start
        base.s847.END = original_end
        base.s847.s827._GLOBAL_MINUTE_BY_SYMBOL = original_minute_by_symbol
    combined = combined.copy()
    combined["account_capital"] = base.CAPITAL
    combined["c3_capital"] = base.CAPITAL
    combined["profile"] = spec.profile
    combined["version"] = CANDIDATE_VERSION
    combined["requested_start_month"] = base.START_MONTH
    combined["stage"] = STAGE_LABEL
    combined["model_tag"] = MODEL_TAG
    combined["line_id"] = LINE_ID
    for frame in frames.values():
        if frame.empty:
            continue
        frame["account_capital"] = base.CAPITAL
        frame["c3_capital"] = base.CAPITAL
        frame["profile"] = spec.profile
        frame["version"] = CANDIDATE_VERSION
        frame["stage"] = STAGE_LABEL
        frame["model_tag"] = MODEL_TAG
        frame["line_id"] = LINE_ID
    return combined, frames, spec


def _decision(summary: pd.DataFrame, eligibility_audit: pd.DataFrame, ai_usage: pd.DataFrame) -> dict[str, Any]:
    a = summary[summary["version"].eq(base.OFFICIAL_VERSION)].iloc[0].to_dict()
    c = summary[summary["version"].eq(CANDIDATE_VERSION)].iloc[0].to_dict()
    usage_summary = ai_usage[ai_usage["ai_product_pool_signal_date"].astype(str).eq("__summary__")]
    usage = usage_summary.iloc[0].to_dict() if not usage_summary.empty else {}
    return {
        "stage": STAGE_LABEL,
        "stage_id": STAGE_ID,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S CST"),
        "hypothesis": "A broad full-market AI bottom-quartile veto preserves trend-following diversification better than hard top8 while still removing poor PIT product candidates.",
        "bottom_veto_quantile": BOTTOM_VETO_QUANTILE,
        "min_active_products_for_veto": MIN_ACTIVE_PRODUCTS_FOR_VETO,
        "target_base_risk_ratio": base.TARGET_BASE_RISK_RATIO,
        "a_official": a,
        "c_candidate": c,
        "return_delta_pct": float(c["total_return_pct"] - a["total_return_pct"]),
        "drawdown_delta_pct": float(c["max_drawdown_pct"] - a["max_drawdown_pct"]),
        "min_monthly_selected_count": int(pd.to_numeric(eligibility_audit["selected_count"], errors="coerce").min()),
        "max_monthly_vetoed_count": int(pd.to_numeric(eligibility_audit["vetoed_count"], errors="coerce").max()),
        "ai_usage_summary": usage,
        "decision": (
            "stage002_continue_to_halfyear_if_independent_review_passes"
            if c["total_return_pct"] > 0
            and c["total_return_pct"] >= a["total_return_pct"] * 0.35
            and c["max_drawdown_pct"] >= a["max_drawdown_pct"] - 5.0
            else "stage002_stop_or_attribution_before_more_runs"
        ),
        "overfit_before": "medium: keeps full-market AI but uses one predeclared quartile veto, not a tuned topN sweep.",
        "overfit_after": "pending_independent_review",
        "continue_value_before": "yes: directly addresses Stage001 failure mode of over-narrow top8 selection.",
        "continue_value_after": "pending_independent_review",
    }


def _plot(curves: pd.DataFrame) -> None:
    if curves.empty:
        return
    fig, axes = base.plt.subplots(2, 1, figsize=(13, 8), sharex=True)
    labels = {
        base.OFFICIAL_VERSION: "Official C9/15w",
        CANDIDATE_VERSION: "Stage002 full-market AI bottom25 veto + risk 0.02",
    }
    colors = {base.OFFICIAL_VERSION: "#111827", CANDIDATE_VERSION: "#0f766e"}
    for version, group in curves.groupby("version", sort=False):
        data = group.sort_values("date")
        x = pd.to_datetime(data["date"])
        equity = pd.to_numeric(data["account_equity_for_metrics"], errors="coerce").ffill()
        axes[0].plot(x, equity, label=labels.get(version, version), color=colors.get(version), linewidth=1.1)
        axes[1].plot(x, base._drawdown_pct(equity), label=labels.get(version, version), color=colors.get(version), linewidth=1.0)
    axes[0].axhline(base.CAPITAL, color="#64748b", linestyle="--", linewidth=0.9)
    axes[0].set_title("Stage002 A/C equity")
    axes[0].set_ylabel("account equity")
    axes[0].grid(alpha=0.25)
    axes[0].legend(loc="best")
    axes[1].axhline(-40.0, color="#111827", linestyle="--", linewidth=0.9)
    axes[1].set_title("Stage002 A/C drawdown")
    axes[1].set_ylabel("drawdown %")
    axes[1].grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=170)
    base.plt.close(fig)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return base._md_table(frame, max_rows=max_rows)


def _write_report(
    summary: pd.DataFrame,
    eligibility: pd.DataFrame,
    eligibility_audit: pd.DataFrame,
    ai_usage: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    latest_pool = eligibility[eligibility["eval_date"].astype(str).eq(str(eligibility["eval_date"].max()))].copy()
    top_counts = (
        eligibility.groupby("product_vt_symbol", as_index=False)
        .size()
        .rename(columns={"size": "selected_months"})
        .sort_values(["selected_months", "product_vt_symbol"], ascending=[False, True])
        .head(20)
    )
    lines = [
        "# Stage002 全市场 PIT AI 底部四分位 veto + 0.02 基础风险真实引擎",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        f"- line_id：`{LINE_ID}`",
        "- 阶段性质：独立研究线最小真实引擎 A/C；不改官方实盘、CTP、邮件或 launchd。",
        "- 外部调研判断：趋势跟随右尾稀疏，全市场过滤更适合先做 meta-label/veto，而不是用 top8 替代主策略分散化。",
        "- 运行前过拟合判断：中等。固定底部四分位是低自由度结构，但仍可能追历史赢家；本阶段不扫 veto 分位。",
        "- 运行前继续价值判断：有。它直接验证 Stage001 top8 过窄这一失败归因。",
        "",
        "## A/C 结果",
        "",
        _md_table(
            summary[
                [
                    "version",
                    "end_equity",
                    "total_return_pct",
                    "max_drawdown_pct",
                    "sharpe",
                    "total_slippage",
                    "total_trade_count",
                    "nonzero_daily_win_rate_pct",
                    "days_below_initial",
                    "max_consecutive_below_initial_days",
                    "max_broker10_margin_to_equity_pct",
                ]
            ]
        ),
        "",
        "## 最新一期 AI 允许池",
        "",
        _md_table(latest_pool[["eval_date", "product_vt_symbol", "score", "score_rank", "top_n"]], max_rows=30),
        "",
        "## 入选月份最多的品种",
        "",
        _md_table(top_counts),
        "",
        "## AI 文件审计",
        "",
        _md_table(eligibility_audit.tail(12)),
        "",
        "## AI 使用审计",
        "",
        _md_table(ai_usage.head(20)),
        "",
        "## 决策",
        "",
        f"- 决策：`{decision['decision']}`",
        f"- 输出图：`{CHART_PATH}`",
        "- 运行后过拟合判断：等待独立 agent review。",
        "- 运行后继续价值判断：等待独立 agent review。",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_stage_record(summary: pd.DataFrame, decision: dict[str, Any]) -> None:
    c = summary[summary["version"].eq(CANDIDATE_VERSION)].iloc[0].to_dict()
    a = summary[summary["version"].eq(base.OFFICIAL_VERSION)].iloc[0].to_dict()
    lines = [
        "# Stage002 全市场 PIT AI 底部四分位 veto + 0.02 基础风险真实引擎",
        "",
        f"- line_id：`{LINE_ID}`",
        "- 当前模式：`day`",
        f"- 记录时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        "- 阶段性质：独立研究线最小 A/C 真实引擎回测",
        "- 是否重要突破：否，Stage001 失败后的结构性修正验证",
        "- 是否触发A/B：是，A=官方 C9/15w；C=全市场 PIT AI 底部四分位 veto + risk_ratio_* 0.02",
        "",
        "## 外部调研与判断",
        "",
        "- 参考资料：Time-series momentum、cross-sectional momentum、ML ranking 与 meta-labeling 资料。",
        "- 我的判断：趋势策略收益来自稀疏右尾，过窄 top8 容易砍掉未来赢家；更合理的第一步是只 veto 最差候选，保留主策略分散化。",
        "",
        "## 本次变更",
        "",
        f"- 新增脚本：`research/lines/{LINE_ID}/tools/stage002_full_market_ai_bottom_quartile_veto_engine.py`",
        "- 新增参数：`BOTTOM_VETO_QUANTILE=0.25`、`MIN_ACTIVE_PRODUCTS_FOR_VETO=12`",
        "- 修改参数：AI eligibility 从 Stage001 top8 改为底部四分位 veto；`risk_ratio_*` 继续固定 `0.02`；full-market 57 品种 universe 不变。",
        "- 删除参数：删除 Stage001 的硬 top8 允许池；不恢复固定卫星品种。",
        "",
        "## 回测/归因参数",
        "",
        f"- 数据区间：`{base.REQUESTED_START.date()}` 到 `{base.REQUESTED_END.date()}`",
        f"- 账户规模：`{base.CAPITAL:,.0f}`",
        "- 成本口径：沿用 C9 真实引擎原成本/slippage 配置。",
        "- 策略/归因口径：A 复用 Stage167 官方 C9/15w 曲线；C 新跑真实引擎。",
        "",
        "## 结果",
        "",
        f"- A 期末权益：`{a['end_equity']:,.2f}`；总收益 `{a['total_return_pct']:.4f}%`；最大回撤 `{a['max_drawdown_pct']:.4f}%`；Sharpe `{a['sharpe']:.4f}`",
        f"- C 期末权益：`{c['end_equity']:,.2f}`",
        f"- C 总收益：`{c['total_return_pct']:.4f}%`",
        f"- C 最大回撤：`{c['max_drawdown_pct']:.4f}%`",
        f"- C Sharpe：`{c['sharpe']:.4f}`",
        f"- C 总滑点：`{c['total_slippage']:,.2f}`",
        f"- C 总交易次数：`{c['total_trade_count']:,.0f}`",
        f"- C 胜率：`{c['nonzero_daily_win_rate_pct']:.4f}%`，口径为非零交易日胜率，不是逐笔胜率。",
        f"- C 最大 broker10 保证金/权益：`{c['max_broker10_margin_to_equity_pct']:.4f}%`",
        f"- C 相对 A 收益差：`{decision['return_delta_pct']:.4f}` 百分点；回撤差：`{decision['drawdown_delta_pct']:.4f}` 百分点。",
        "",
        "## 输出文件",
        "",
        f"- report：`{REPORT_PATH}`",
        f"- summary：`{SUMMARY_PATH}`",
        f"- eligibility：`{ELIGIBILITY_PATH}`",
        f"- feature_panel：`{FEATURE_PANEL_PATH}`",
        f"- daily：`{CANDIDATE_DAILY_PATH}`",
        f"- quality：`{AI_USAGE_AUDIT_PATH}`",
        "",
        "## 结论",
        "",
        f"- 本阶段结论：`{decision['decision']}`",
        "- 是否进入下一步：等待独立 agent review 后决定。",
        "- 下一步：若 review 通过且 C 明显优于 Stage001，再考虑逐半年多周期；否则做更深归因。",
        "",
        "## 过拟合反思",
        "",
        "- 运行前判断：中等。底部四分位是常见低自由度结构，但仍源自 Stage001 失败归因。",
        "- 运行后判断：等待独立 review；本阶段没有扫分位、topN、窗口或权重。",
        "- 原因：只验证一个结构性假设：AI 应先做 veto，而不是硬 top8。",
        "",
        "## 继续价值反思",
        "",
        "- 运行前判断：有价值，因为它正面修正 Stage001 的过窄过滤问题。",
        "- 运行后判断：等待独立 review。",
        "- 原因：单起点仍只是第一关。",
    ]
    STAGE_RECORD_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _append_back_log(summary: pd.DataFrame, decision: dict[str, Any]) -> None:
    c = summary[summary["version"].eq(CANDIDATE_VERSION)].iloc[0].to_dict()
    a = summary[summary["version"].eq(base.OFFICIAL_VERSION)].iloc[0].to_dict()
    text = (
        f"\n{datetime.now().strftime('%Y-%m-%d %H:%M CST')}：`{LINE_ID}` Stage002 完成全市场 PIT AI 底部四分位 veto + `risk_ratio_* = 0.02` "
        f"最小真实引擎 A/C，决策 `{decision['decision']}`。新增脚本 `research/lines/{LINE_ID}/tools/stage002_full_market_ai_bottom_quartile_veto_engine.py`；"
        f"新增 eligibility `{ELIGIBILITY_PATH}`，feature panel `{FEATURE_PANEL_PATH}`，report `{REPORT_PATH}`。"
        "新增参数：`BOTTOM_VETO_QUANTILE=0.25`、`MIN_ACTIVE_PRODUCTS_FOR_VETO=12`；"
        "修改参数：AI eligibility 从 Stage001 top8 改为底部四分位 veto，full-market 57 品种和 `risk_ratio_* = 0.02` 不变；"
        "删除参数：删除硬 top8 允许池，不恢复固定卫星品种。"
        f"A 官方 C9/15w：期末权益 `{a['end_equity']:,.2f}`、总收益 `{a['total_return_pct']:.4f}%`、最大回撤 `{a['max_drawdown_pct']:.4f}%`、"
        f"Sharpe `{a['sharpe']:.4f}`、总滑点 `{a['total_slippage']:,.2f}`、总交易次数 `{a['total_trade_count']:,.0f}`、"
        f"非零交易日胜率 `{a['nonzero_daily_win_rate_pct']:.4f}%`。"
        f"C 候选：期末权益 `{c['end_equity']:,.2f}`、总收益 `{c['total_return_pct']:.4f}%`、最大回撤 `{c['max_drawdown_pct']:.4f}%`、"
        f"Sharpe `{c['sharpe']:.4f}`、总滑点 `{c['total_slippage']:,.2f}`、总交易次数 `{c['total_trade_count']:,.0f}`、"
        f"胜率 `{c['nonzero_daily_win_rate_pct']:.4f}%`（非零交易日胜率口径）。"
        f"新增结果：C 相对 A 收益差 `{decision['return_delta_pct']:.4f}` 百分点，回撤差 `{decision['drawdown_delta_pct']:.4f}` 百分点；"
        "删除结果：删除 Stage001 硬 top8 作为候选推进的假设。运行前过拟合反思：中等，候选来自 Stage001 失败归因但只用一个预声明四分位 veto。"
        "运行后过拟合反思：待独立 agent review；本阶段没有扫分位、topN、窗口或权重。运行前继续价值反思：有，检验 AI 从 positive selector 转为 veto filter。"
        "运行后继续价值反思：待独立 agent review 后决定是否扩展多周期。\n"
    )
    with (base.ROOT / "back_log.md").open("a", encoding="utf-8") as fh:
        fh.write(text)


def _update_line(summary: pd.DataFrame, decision: dict[str, Any]) -> None:
    c = summary[summary["version"].eq(CANDIDATE_VERSION)].iloc[0].to_dict()
    addition = (
        "\n## Stage002\n\n"
        f"- 时间: `{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`\n"
        f"- 决策: `{decision['decision']}`\n"
        f"- C 期末权益: `{c['end_equity']:,.2f}`，总收益 `{c['total_return_pct']:.4f}%`，最大回撤 `{c['max_drawdown_pct']:.4f}%`，Sharpe `{c['sharpe']:.4f}`。\n"
        "- 状态: 已跑单起点真实引擎，等待独立 agent review 后再决定是否扩展逐半年多周期。\n"
    )
    with (base.LINE_DIR / "LINE.md").open("a", encoding="utf-8") as fh:
        fh.write(addition)


def build() -> dict[str, pd.DataFrame]:
    _configure_base_globals()
    OUT.mkdir(parents=True, exist_ok=True)
    STAGES_DIR.mkdir(parents=True, exist_ok=True)

    universe = base._load_universe()
    calendar = base._load_trade_calendar()
    eval_dates = base._build_eval_dates(calendar)
    feature_panel = base._build_feature_panel(universe, eval_dates)
    feature_panel = _apply_bottom_quartile_veto(feature_panel)
    eligibility, eligibility_audit = _build_eligibility(feature_panel)

    feature_panel.to_csv(FEATURE_PANEL_PATH, index=False, encoding="utf-8-sig")
    eligibility.to_csv(ELIGIBILITY_PATH, index=False, encoding="utf-8-sig")
    eligibility_audit.to_csv(ELIGIBILITY_AUDIT_PATH, index=False, encoding="utf-8-sig")

    metadata = base._metadata()
    candidate_daily, frames, _spec = _run_candidate(metadata)
    candidate_daily.to_csv(CANDIDATE_DAILY_PATH, index=False, encoding="utf-8-sig")
    for name, path in (
        ("entry_candidates", CANDIDATE_ENTRY_CANDIDATES_PATH),
        ("entry_risk", CANDIDATE_ENTRY_RISK_PATH),
        ("trades", CANDIDATE_TRADES_PATH),
        ("trade_events", CANDIDATE_TRADE_EVENTS_PATH),
    ):
        frame = frames.get(name, pd.DataFrame()).copy()
        if not frame.empty:
            frame.to_csv(path, index=False, encoding="utf-8-sig")

    official_curve = base._curve_for_metrics(base._read_official_curve(), base.OFFICIAL_VERSION)
    candidate_curve = base._curve_for_metrics(candidate_daily, CANDIDATE_VERSION)
    curves = pd.concat([official_curve, candidate_curve], ignore_index=True, sort=False)
    curves = curves.sort_values(["version", "date"]).reset_index(drop=True)
    summary = pd.DataFrame([base._summarize_curve(group) for _, group in curves.groupby("version", sort=False)])
    ai_usage = base._ai_usage_audit(frames.get("entry_candidates", pd.DataFrame()))
    decision = _decision(summary, eligibility_audit, ai_usage)

    curves.to_csv(CURVES_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    ai_usage.to_csv(AI_USAGE_AUDIT_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(base._json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _plot(curves)
    _write_report(summary, eligibility, eligibility_audit, ai_usage, decision)
    _write_stage_record(summary, decision)
    _append_back_log(summary, decision)
    _update_line(summary, decision)

    return {
        "feature_panel": feature_panel,
        "eligibility": eligibility,
        "eligibility_audit": eligibility_audit,
        "candidate_daily": candidate_daily,
        "curves": curves,
        "summary": summary,
        "ai_usage": ai_usage,
    }


def main() -> None:
    outputs = build()
    print(outputs["summary"].to_string(index=False))
    print(f"report={REPORT_PATH}")
    print(f"chart={CHART_PATH}")


if __name__ == "__main__":
    main()
