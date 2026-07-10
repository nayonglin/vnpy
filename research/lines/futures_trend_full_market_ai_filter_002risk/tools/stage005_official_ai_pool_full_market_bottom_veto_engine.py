#!/usr/bin/env python3
"""Stage005: keep the official C9 pool and use full-market AI only as a veto.

Stage001-004 replaced the official product selection with a full-market
score-only selector and destroyed the trend right tail.  This stage changes the
role of the full-market score: the official live AI pool remains primary, while
the full-market PIT score can only veto official-pool products that rank in the
bottom quartile of active products.  Risk sizing is intentionally kept identical
to official C9 so this run isolates the product-pool overlay.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import stage001_full_market_pit_ai_risk002_engine as base
from qmt_roll_official_live_config import OFFICIAL_LIVE_AI_ELIGIBILITY_PATH


LINE_ID = base.LINE_ID
STAGE_ID = "stage005_official_ai_pool_full_market_bottom_veto_engine"
STAGE_LABEL = "Stage005"
MODEL_TAG = f"{STAGE_ID}_v1"
OUTPUT_PREFIX = f"full_market_ai002_{STAGE_ID}"

CANDIDATE_VERSION = "official_ai_pool_full_market_bottom25_veto_official_risk"
STRATEGY_NAME = "official_ai_pool_full_market_bottom25_veto_entry_filter"
SCORE_TYPE = "official_ai_pool_with_full_market_bottom25_pit_veto"

BOTTOM_VETO_QUANTILE = 0.25
MIN_ACTIVE_PRODUCTS_FOR_VETO = 12

OUT = base.LINE_DIR / "outputs" / STAGE_ID
STAGES_DIR = base.LINE_DIR / "stages"
STAGE_RECORD_PATH = STAGES_DIR / "20260709_2210_stage005_official_ai_pool_full_market_bottom_veto_engine.md"

FEATURE_PANEL_PATH = OUT / f"{OUTPUT_PREFIX}_feature_panel_{MODEL_TAG}.csv.gz"
ELIGIBILITY_PATH = OUT / f"{OUTPUT_PREFIX}_eligibility_{MODEL_TAG}.csv"
ELIGIBILITY_AUDIT_PATH = OUT / f"{OUTPUT_PREFIX}_eligibility_audit_{MODEL_TAG}.csv"
OVERLAY_AUDIT_PATH = OUT / f"{OUTPUT_PREFIX}_official_overlay_audit_{MODEL_TAG}.csv"
CANDIDATE_DAILY_PATH = OUT / f"{OUTPUT_PREFIX}_candidate_daily_{MODEL_TAG}.csv.gz"
CANDIDATE_ENTRY_CANDIDATES_PATH = OUT / f"{OUTPUT_PREFIX}_candidate_entry_candidates_{MODEL_TAG}.csv.gz"
CANDIDATE_ENTRY_RISK_PATH = OUT / f"{OUTPUT_PREFIX}_candidate_entry_risk_{MODEL_TAG}.csv.gz"
CANDIDATE_TRADES_PATH = OUT / f"{OUTPUT_PREFIX}_candidate_trades_{MODEL_TAG}.csv.gz"
CANDIDATE_TRADE_EVENTS_PATH = OUT / f"{OUTPUT_PREFIX}_candidate_trade_events_{MODEL_TAG}.csv.gz"
CURVES_PATH = OUT / f"{OUTPUT_PREFIX}_ac_curves_{MODEL_TAG}.csv.gz"
SUMMARY_PATH = OUT / f"{OUTPUT_PREFIX}_ac_summary_{MODEL_TAG}.csv"
AI_USAGE_AUDIT_PATH = OUT / f"{OUTPUT_PREFIX}_ai_usage_audit_{MODEL_TAG}.csv"
RISK_RESTORE_AUDIT_PATH = OUT / f"{OUTPUT_PREFIX}_risk_restore_audit_{MODEL_TAG}.csv"
DECISION_PATH = OUT / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUT / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUT / f"{OUTPUT_PREFIX}_equity_drawdown_{MODEL_TAG}.png"


def _risk_restore_audit(entry_risk: pd.DataFrame, entry_candidates: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for name, frame in (("entry_risk", entry_risk), ("entry_candidates", entry_candidates)):
        data = frame.copy()
        if data.empty:
            rows.append({"frame": name, "rows": 0})
            continue
        risk_ratio = pd.to_numeric(data.get("risk_ratio", 0.0), errors="coerce").fillna(0.0)
        risk_multiplier = pd.to_numeric(data.get("risk_multiplier", 0.0), errors="coerce").fillna(0.0)
        oi_enabled = pd.to_numeric(data.get("oi_price_confirm_risk_restore_enabled", 0), errors="coerce").fillna(0).astype(int)
        oi_applied = pd.to_numeric(data.get("oi_price_confirm_risk_restore_applied", 0), errors="coerce").fillna(0).astype(int)
        rows.append(
            {
                "frame": name,
                "rows": int(len(data)),
                "risk_ratio_min": float(risk_ratio.min()) if len(risk_ratio) else 0.0,
                "risk_ratio_max": float(risk_ratio.max()) if len(risk_ratio) else 0.0,
                "risk_multiplier_min": float(risk_multiplier.min()) if len(risk_multiplier) else 0.0,
                "risk_multiplier_max": float(risk_multiplier.max()) if len(risk_multiplier) else 0.0,
                "risk_multiplier_gt1_rows": int((risk_multiplier > 1.0 + 1e-12).sum()),
                "oi_restore_enabled_rows": int(oi_enabled.sum()),
                "oi_restore_applied_rows": int(oi_applied.sum()),
            }
        )
    return pd.DataFrame(rows)


def _full_market_score_lookup(feature_panel: pd.DataFrame) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for eval_date, group in feature_panel.groupby("eval_date", sort=True):
        data = group.copy()
        available = data[data["data_available"].eq(1)].copy()
        data["full_market_active_count"] = int(len(available))
        data["full_market_score_rank_available"] = np.nan
        data["full_market_rank_pct_available"] = np.nan
        data["full_market_bottom_veto"] = 0
        data["full_market_veto_reason"] = "not_active_or_cold_start"
        if len(available) >= MIN_ACTIVE_PRODUCTS_FOR_VETO:
            ranks = available["score"].rank(method="first", ascending=False).astype(int)
            rank_pct = ranks.astype(float) / float(len(available))
            bottom_veto = rank_pct > (1.0 - BOTTOM_VETO_QUANTILE)
            data.loc[available.index, "full_market_score_rank_available"] = ranks
            data.loc[available.index, "full_market_rank_pct_available"] = rank_pct
            data.loc[available.index, "full_market_veto_reason"] = "full_market_score_ok"
            data.loc[rank_pct[bottom_veto].index, "full_market_bottom_veto"] = 1
            data.loc[rank_pct[bottom_veto].index, "full_market_veto_reason"] = "full_market_bottom25_veto"
        else:
            data["full_market_veto_reason"] = "cold_start_neutral_no_veto"
        frames.append(data)
    result = pd.concat(frames, ignore_index=True, sort=False)
    result["eval_date"] = pd.to_datetime(result["eval_date"], errors="coerce").dt.normalize()
    return result


def _build_eligibility(feature_panel: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    score_panel = _full_market_score_lookup(feature_panel)
    score_lookup = score_panel[
        [
            "eval_date",
            "product_vt_symbol",
            "score",
            "data_available",
            "full_market_active_count",
            "full_market_score_rank_available",
            "full_market_rank_pct_available",
            "full_market_bottom_veto",
            "full_market_veto_reason",
        ]
    ].copy()
    score_lookup = score_lookup.rename(columns={"score": "full_market_score"})
    score_lookup["eval_date"] = score_lookup["eval_date"].dt.date.astype(str)

    official = pd.read_csv(OFFICIAL_LIVE_AI_ELIGIBILITY_PATH, encoding="utf-8-sig")
    official["eval_date"] = pd.to_datetime(official["eval_date"], errors="coerce").dt.date.astype(str)
    official["product_vt_symbol"] = official["product_vt_symbol"].astype(str)
    official["official_score"] = pd.to_numeric(official.get("score", 0.0), errors="coerce").fillna(0.0)
    official["official_score_rank"] = pd.to_numeric(official.get("score_rank", 0), errors="coerce").fillna(0).astype(int)
    official["official_top_n"] = pd.to_numeric(official.get("top_n", 0), errors="coerce").fillna(0).astype(int)

    merged = official.merge(score_lookup, on=["eval_date", "product_vt_symbol"], how="left")
    merged["full_market_score_available"] = merged["full_market_score"].notna().astype(int)
    merged["full_market_bottom_veto"] = pd.to_numeric(merged["full_market_bottom_veto"], errors="coerce").fillna(0).astype(int)
    merged["overlay_keep"] = 1
    merged.loc[merged["full_market_bottom_veto"].eq(1), "overlay_keep"] = 0
    merged["overlay_reason"] = "official_pool_kept"
    merged.loc[merged["full_market_bottom_veto"].eq(1), "overlay_reason"] = "official_pool_product_in_full_market_bottom25"
    merged.loc[merged["full_market_score_available"].eq(0), "overlay_reason"] = "official_pool_no_full_market_panel_keep"

    kept = merged[merged["overlay_keep"].eq(1)].copy()
    kept = kept.sort_values(["eval_date", "official_score_rank", "product_vt_symbol"]).reset_index(drop=True)
    kept["score"] = pd.to_numeric(kept["full_market_score"], errors="coerce").fillna(kept["official_score"])
    kept["score_rank"] = kept.groupby("eval_date").cumcount() + 1
    kept["top_n"] = kept.groupby("eval_date")["product_vt_symbol"].transform("count").astype(int)
    kept["strategy"] = STRATEGY_NAME
    kept["score_type"] = SCORE_TYPE
    eligibility = kept[
        ["strategy", "score_type", "eval_date", "product_vt_symbol", "score", "score_rank", "top_n"]
    ].copy()

    overlay_audit = merged[
        [
            "eval_date",
            "product_vt_symbol",
            "official_score",
            "official_score_rank",
            "official_top_n",
            "full_market_score",
            "data_available",
            "full_market_active_count",
            "full_market_score_rank_available",
            "full_market_rank_pct_available",
            "full_market_bottom_veto",
            "overlay_keep",
            "overlay_reason",
        ]
    ].copy()

    eligibility_audit = (
        merged.groupby("eval_date", as_index=False)
        .agg(
            official_count=("product_vt_symbol", "count"),
            kept_count=("overlay_keep", "sum"),
            vetoed_count=("full_market_bottom_veto", "sum"),
            no_full_market_panel_count=("full_market_score_available", lambda s: int((s == 0).sum())),
            min_full_market_rank_pct=("full_market_rank_pct_available", "min"),
            max_full_market_rank_pct=("full_market_rank_pct_available", "max"),
            active_count=("full_market_active_count", "max"),
        )
        .sort_values("eval_date")
    )
    return eligibility, eligibility_audit, overlay_audit


def _metadata() -> dict[str, Any]:
    live_overrides = dict(base.build_official_live_strategy_overrides())
    universe_path = str(live_overrides["product_universe_csv_path"])
    supported_symbols = base.load_product_universe_symbols(universe_path)
    return base.build_contract_metadata(supported_symbols=supported_symbols)


def _candidate_profile(metadata: dict[str, Any]) -> dict[str, Any]:
    profile = base.s847._c9_profile(metadata)
    spec = profile["spec"]
    profile_name = "stage005_official_ai_pool_full_market_bottom25_veto"
    capital = replace(
        spec.capital,
        variant=profile_name,
        label="Stage005 official AI pool + full-market bottom25 veto",
        account_capital=base.CAPITAL,
        c3_capital=base.CAPITAL,
        note=(
            f"{spec.capital.note} | Stage005 independent line. Official C9 risk sizing is unchanged; "
            "full-market PIT score is only a bottom-quartile veto on the official AI pool."
        ),
    )
    live_overrides = dict(base.build_official_live_strategy_overrides())
    overrides = {
        **spec.overrides,
        **live_overrides,
        "enable_ai_product_pool_filter": True,
        "ai_product_pool_eligibility_path": str(ELIGIBILITY_PATH),
        "ai_product_pool_strategy": STRATEGY_NAME,
        "account_capital": base.CAPITAL,
        "c3_capital": base.CAPITAL,
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


def _decision(summary: pd.DataFrame, eligibility_audit: pd.DataFrame, ai_usage: pd.DataFrame, risk_audit: pd.DataFrame) -> dict[str, Any]:
    a = summary[summary["version"].eq(base.OFFICIAL_VERSION)].iloc[0].to_dict()
    c = summary[summary["version"].eq(CANDIDATE_VERSION)].iloc[0].to_dict()
    usage_summary = ai_usage[ai_usage["ai_product_pool_signal_date"].astype(str).eq("__summary__")]
    return_retention = float(c["total_return_pct"] / a["total_return_pct"]) if a["total_return_pct"] else 0.0
    dd_delta = float(c["max_drawdown_pct"] - a["max_drawdown_pct"])
    decision = (
        "stage005_continue_to_halfyear_if_independent_review_passes"
        if return_retention >= 0.50 and dd_delta >= 0.0
        else "stage005_stop_or_attribution_before_more_runs"
    )
    return {
        "stage": STAGE_LABEL,
        "stage_id": STAGE_ID,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S CST"),
        "hypothesis": "Full-market score may work as a low-authority veto on the official AI pool, preserving official diversification and right-tail opportunities.",
        "official_ai_eligibility_path": str(OFFICIAL_LIVE_AI_ELIGIBILITY_PATH),
        "bottom_veto_quantile": BOTTOM_VETO_QUANTILE,
        "min_active_products_for_veto": MIN_ACTIVE_PRODUCTS_FOR_VETO,
        "risk_sizing_change": "none: official C9 risk and OI restore are intentionally unchanged",
        "a_official": a,
        "c_candidate": c,
        "return_delta_pct": float(c["total_return_pct"] - a["total_return_pct"]),
        "return_retention_ratio": return_retention,
        "drawdown_delta_pct": dd_delta,
        "total_vetoed_official_pool_rows": int(pd.to_numeric(eligibility_audit["vetoed_count"], errors="coerce").sum()),
        "total_kept_official_pool_rows": int(pd.to_numeric(eligibility_audit["kept_count"], errors="coerce").sum()),
        "ai_usage_summary": usage_summary.iloc[0].to_dict() if not usage_summary.empty else {},
        "risk_restore_audit": risk_audit.to_dict(orient="records"),
        "decision": decision,
        "overfit_before": "low_to_medium: this is a role change from selector to veto, with one natural bottom-quartile cutoff and no product blacklist.",
        "overfit_after": "pending_independent_review",
        "continue_value_before": "yes: it tests whether full-market features can add value without replacing the official pool.",
        "continue_value_after": "pending_independent_review",
    }


def _summarize_curve(frame: pd.DataFrame) -> dict[str, Any]:
    row = base._summarize_curve(frame)
    row["stage"] = STAGE_LABEL
    row["model_tag"] = MODEL_TAG
    row["line_id"] = LINE_ID
    return row


def _plot(curves: pd.DataFrame) -> None:
    if curves.empty:
        return
    fig, axes = base.plt.subplots(2, 1, figsize=(13, 8), sharex=True)
    labels = {
        base.OFFICIAL_VERSION: "Official C9/15w",
        CANDIDATE_VERSION: "Stage005 official pool + full-market bottom25 veto",
    }
    colors = {base.OFFICIAL_VERSION: "#111827", CANDIDATE_VERSION: "#0891b2"}
    for version, group in curves.groupby("version", sort=False):
        data = group.sort_values("date")
        x = pd.to_datetime(data["date"])
        equity = pd.to_numeric(data["account_equity_for_metrics"], errors="coerce").ffill()
        axes[0].plot(x, equity, label=labels.get(version, version), color=colors.get(version), linewidth=1.1)
        axes[1].plot(x, base._drawdown_pct(equity), label=labels.get(version, version), color=colors.get(version), linewidth=1.0)
    axes[0].axhline(base.CAPITAL, color="#64748b", linestyle="--", linewidth=0.9)
    axes[0].set_title("Stage005 A/C equity")
    axes[0].set_ylabel("account equity")
    axes[0].grid(alpha=0.25)
    axes[0].legend(loc="best")
    axes[1].axhline(-40.0, color="#111827", linestyle="--", linewidth=0.9)
    axes[1].set_title("Stage005 A/C drawdown")
    axes[1].set_ylabel("drawdown %")
    axes[1].grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=170)
    base.plt.close(fig)


def _write_report(
    summary: pd.DataFrame,
    eligibility_audit: pd.DataFrame,
    overlay_audit: pd.DataFrame,
    ai_usage: pd.DataFrame,
    risk_audit: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    veto_rows = overlay_audit[overlay_audit["overlay_keep"].eq(0)].copy()
    lines = [
        "# Stage005 正式 AI 池 + 全市场底部四分位 veto 真实引擎",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        f"- line_id：`{LINE_ID}`",
        "- 阶段性质：独立研究线最小真实引擎 A/C；不改官方实盘、CTP、邮件或 launchd。",
        "- 外部调研判断：ML/meta-labeling 更适合做 primary strategy 的二级过滤；趋势跟随需要保留足够分散和右尾。",
        "- 运行前过拟合判断：低到中等。只用一个自然 bottom quartile veto，不按坏窗口或品种黑名单救参。",
        "- 运行前继续价值判断：有。Stage001-004 说明 full-market selector 权限太高，本阶段验证低权限 overlay。",
        "",
        "## A/C 结果",
        "",
        base._md_table(summary[
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
        ]),
        "",
        "## 正式 AI 池 overlay 审计",
        "",
        base._md_table(eligibility_audit.tail(12)),
        "",
        "## 被 veto 的正式池样本",
        "",
        base._md_table(veto_rows.tail(30)),
        "",
        "## AI 使用审计",
        "",
        base._md_table(ai_usage.head(20)),
        "",
        "## OI restore / 风险审计",
        "",
        base._md_table(risk_audit),
        "",
        "## 决策",
        "",
        f"- 决策：`{decision['decision']}`",
        f"- 收益保留率：`{decision['return_retention_ratio']:.4f}`",
        f"- 回撤变化：`{decision['drawdown_delta_pct']:.4f}` 百分点",
        f"- 输出图：`{CHART_PATH}`",
        "- 运行后过拟合判断：等待独立 agent review。",
        "- 运行后继续价值判断：等待独立 agent review。",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_stage_record(summary: pd.DataFrame, decision: dict[str, Any]) -> None:
    c = summary[summary["version"].eq(CANDIDATE_VERSION)].iloc[0].to_dict()
    a = summary[summary["version"].eq(base.OFFICIAL_VERSION)].iloc[0].to_dict()
    lines = [
        "# Stage005 正式 AI 池 + 全市场底部四分位 veto 真实引擎",
        "",
        f"- line_id：`{LINE_ID}`",
        "- 当前模式：`day`",
        f"- 记录时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        "- 阶段性质：独立研究线最小 A/C 真实引擎回测",
        "- 是否重要突破：待独立 review；本阶段先验证结构角色切换",
        "- 是否触发A/B：是，A=官方 C9/15w；C=官方 C9/15w + 正式 AI 池内 full-market bottom25 veto",
        "",
        "## 外部调研与判断",
        "",
        "- 参考资料：Hudson & Thames meta-labeling、AQR managed futures、QuantInsti cross-sectional momentum ML。",
        "- 我的判断：AI 不应在当前特征质量下替代趋势策略的产品池；更合理的是作为低权限 veto 或 sizing overlay。",
        "",
        "## 本次变更",
        "",
        f"- 新增脚本：`research/lines/{LINE_ID}/tools/stage005_official_ai_pool_full_market_bottom_veto_engine.py`",
        f"- 新增参数：`BOTTOM_VETO_QUANTILE={BOTTOM_VETO_QUANTILE}`、`MIN_ACTIVE_PRODUCTS_FOR_VETO={MIN_ACTIVE_PRODUCTS_FOR_VETO}`",
        "- 修改参数：候选 C 的 AI eligibility 从正式文件改为“正式文件减去全市场分数底部四分位”。",
        "- 删除参数：本阶段不删除正式风险参数，不关闭 OI restore，不改 product_universe。",
        "",
        "## 回测参数",
        "",
        f"- 数据区间：`{base.REQUESTED_START.date()}` 到 `{base.REQUESTED_END.date()}`",
        f"- 账户规模：`{base.CAPITAL:,.0f}`",
        "- 成本口径：沿用 C9 真实引擎原成本/slippage 配置。",
        "- 风险口径：官方 C9 风险原样保留；本阶段不测试 `0.02` 风险。",
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
        f"- 收益保留率：`{decision['return_retention_ratio']:.4f}`",
        f"- C 相对 A 收益差：`{decision['return_delta_pct']:.4f}` 百分点；回撤差：`{decision['drawdown_delta_pct']:.4f}` 百分点。",
        "",
        "## 输出文件",
        "",
        f"- report：`{REPORT_PATH}`",
        f"- summary：`{SUMMARY_PATH}`",
        f"- eligibility：`{ELIGIBILITY_PATH}`",
        f"- overlay_audit：`{OVERLAY_AUDIT_PATH}`",
        f"- risk_restore_audit：`{RISK_RESTORE_AUDIT_PATH}`",
        f"- chart：`{CHART_PATH}`",
        "",
        "## 结论",
        "",
        f"- 本阶段结论：`{decision['decision']}`",
        "- 是否进入下一步：等待独立 agent review 后决定。",
        "- 下一步：若 C 在保持 50%+ 收益的同时改善回撤，再跑逐半年多周期；否则停止该 veto 形状。",
        "",
        "## 过拟合反思",
        "",
        "- 运行前判断：低到中等。结构角色从 selector 降为 veto，不按坏窗口和单品种救参。",
        "- 运行后判断：等待独立 review。",
        "",
        "## 继续价值反思",
        "",
        "- 运行前判断：有价值。它验证 full-market 特征能否作为低权限 overlay，而不是替代正式 AI 池。",
        "- 运行后判断：等待独立 review。",
    ]
    STAGE_RECORD_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _append_back_log(summary: pd.DataFrame, decision: dict[str, Any]) -> None:
    c = summary[summary["version"].eq(CANDIDATE_VERSION)].iloc[0].to_dict()
    a = summary[summary["version"].eq(base.OFFICIAL_VERSION)].iloc[0].to_dict()
    text = (
        f"\n{datetime.now().strftime('%Y-%m-%d %H:%M CST')}：`{LINE_ID}` Stage005 完成正式 AI 池 + 全市场 bottom25 veto "
        f"最小真实引擎 A/C，决策 `{decision['decision']}`。新增脚本 `research/lines/{LINE_ID}/tools/stage005_official_ai_pool_full_market_bottom_veto_engine.py`；"
        f"新增 eligibility `{ELIGIBILITY_PATH}`，overlay_audit `{OVERLAY_AUDIT_PATH}`，report `{REPORT_PATH}`。"
        f"新增参数：`BOTTOM_VETO_QUANTILE={BOTTOM_VETO_QUANTILE}`、`MIN_ACTIVE_PRODUCTS_FOR_VETO={MIN_ACTIVE_PRODUCTS_FOR_VETO}`；"
        "修改参数：C 使用正式 AI 池内 full-market bottom25 veto；删除参数：本阶段不删除正式风险参数，不关闭 OI restore，不改 product_universe。"
        f"A 官方 C9/15w：期末权益 `{a['end_equity']:,.2f}`、总收益 `{a['total_return_pct']:.4f}%`、最大回撤 `{a['max_drawdown_pct']:.4f}%`、"
        f"Sharpe `{a['sharpe']:.4f}`、总滑点 `{a['total_slippage']:,.2f}`、总交易次数 `{a['total_trade_count']:,.0f}`、胜率 `{a['nonzero_daily_win_rate_pct']:.4f}%`。"
        f"C 候选：期末权益 `{c['end_equity']:,.2f}`、总收益 `{c['total_return_pct']:.4f}%`、最大回撤 `{c['max_drawdown_pct']:.4f}%`、"
        f"Sharpe `{c['sharpe']:.4f}`、总滑点 `{c['total_slippage']:,.2f}`、总交易次数 `{c['total_trade_count']:,.0f}`、胜率 `{c['nonzero_daily_win_rate_pct']:.4f}%`。"
        f"新增结果：收益保留率 `{decision['return_retention_ratio']:.4f}`，C 相对 A 收益差 `{decision['return_delta_pct']:.4f}` 百分点，"
        f"回撤差 `{decision['drawdown_delta_pct']:.4f}` 百分点；删除结果：删除“full-market score 必须作为主选择器才有价值”的隐含假设。"
        "运行前过拟合反思：低到中等，角色切换为低权限 veto 且只用自然四分位；运行后过拟合反思：待独立 agent review。"
        "运行前继续价值反思：有，验证 full-market 特征能否在不替代正式池时改善路径；运行后继续价值反思：待独立 agent review。\n"
    )
    with (base.ROOT / "back_log.md").open("a", encoding="utf-8") as fh:
        fh.write(text)


def _update_line(summary: pd.DataFrame, decision: dict[str, Any]) -> None:
    c = summary[summary["version"].eq(CANDIDATE_VERSION)].iloc[0].to_dict()
    addition = (
        "\n## Stage005\n\n"
        f"- 时间: `{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`\n"
        f"- 决策: `{decision['decision']}`\n"
        f"- C 期末权益: `{c['end_equity']:,.2f}`，总收益 `{c['total_return_pct']:.4f}%`，最大回撤 `{c['max_drawdown_pct']:.4f}%`，Sharpe `{c['sharpe']:.4f}`。\n"
        f"- 收益保留率: `{decision['return_retention_ratio']:.4f}`，回撤变化 `{decision['drawdown_delta_pct']:.4f}` 百分点。\n"
        "- 状态: 已跑单起点真实引擎，等待独立 agent review 后再决定是否扩展逐半年多周期。\n"
    )
    with (base.LINE_DIR / "LINE.md").open("a", encoding="utf-8") as fh:
        fh.write(addition)


def build() -> dict[str, pd.DataFrame]:
    OUT.mkdir(parents=True, exist_ok=True)
    STAGES_DIR.mkdir(parents=True, exist_ok=True)

    universe = base._load_universe()
    calendar = base._load_trade_calendar()
    eval_dates = base._build_eval_dates(calendar)
    feature_panel = base._build_feature_panel(universe, eval_dates)
    feature_panel = _full_market_score_lookup(feature_panel)
    eligibility, eligibility_audit, overlay_audit = _build_eligibility(feature_panel)

    feature_panel.to_csv(FEATURE_PANEL_PATH, index=False, encoding="utf-8-sig")
    eligibility.to_csv(ELIGIBILITY_PATH, index=False, encoding="utf-8-sig")
    eligibility_audit.to_csv(ELIGIBILITY_AUDIT_PATH, index=False, encoding="utf-8-sig")
    overlay_audit.to_csv(OVERLAY_AUDIT_PATH, index=False, encoding="utf-8-sig")

    metadata = _metadata()
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
    curves["stage"] = STAGE_LABEL
    curves["model_tag"] = MODEL_TAG
    curves["line_id"] = LINE_ID
    summary = pd.DataFrame([_summarize_curve(group) for _, group in curves.groupby("version", sort=False)])
    ai_usage = base._ai_usage_audit(frames.get("entry_candidates", pd.DataFrame()))
    risk_audit = _risk_restore_audit(frames.get("entry_risk", pd.DataFrame()), frames.get("entry_candidates", pd.DataFrame()))
    decision = _decision(summary, eligibility_audit, ai_usage, risk_audit)

    curves.to_csv(CURVES_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    ai_usage.to_csv(AI_USAGE_AUDIT_PATH, index=False, encoding="utf-8-sig")
    risk_audit.to_csv(RISK_RESTORE_AUDIT_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(base._json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _plot(curves)
    _write_report(summary, eligibility_audit, overlay_audit, ai_usage, risk_audit, decision)
    _write_stage_record(summary, decision)
    _append_back_log(summary, decision)
    _update_line(summary, decision)

    return {
        "feature_panel": feature_panel,
        "eligibility": eligibility,
        "eligibility_audit": eligibility_audit,
        "overlay_audit": overlay_audit,
        "candidate_daily": candidate_daily,
        "curves": curves,
        "summary": summary,
        "ai_usage": ai_usage,
        "risk_audit": risk_audit,
    }


def main() -> None:
    outputs = build()
    print(outputs["summary"].to_string(index=False))
    print(outputs["eligibility_audit"].tail(12).to_string(index=False))
    print(outputs["risk_audit"].to_string(index=False))
    print(f"report={REPORT_PATH}")
    print(f"chart={CHART_PATH}")


if __name__ == "__main__":
    main()
