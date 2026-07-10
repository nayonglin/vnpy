#!/usr/bin/env python3
"""Stage003: Stage002 bottom-quartile veto with effective risk capped at 0.02.

Stage002 showed that setting risk_ratio_* to 0.02 is not the same as capping
effective entry risk at 2%, because the inherited OI-confirm restore can lift
many entries to risk_multiplier=2.0. This stage keeps the same full-market AI
veto as Stage002, but disables OI-confirm risk restore so the user's requested
base risk is not silently amplified.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
import json
from pathlib import Path
from typing import Any

import pandas as pd

import stage001_full_market_pit_ai_risk002_engine as base
import stage002_full_market_ai_bottom_quartile_veto_engine as s2


LINE_ID = base.LINE_ID
STAGE_ID = "stage003_bottom_quartile_veto_effective_risk_cap_engine"
STAGE_LABEL = "Stage003"
MODEL_TAG = f"{STAGE_ID}_v1"
OUTPUT_PREFIX = f"full_market_ai002_{STAGE_ID}"

CANDIDATE_VERSION = "full_market_pit_ai_bottom25_veto_effective_risk002"
STRATEGY_NAME = "full_market_pit_profit_memory_bottom25_veto_effective_risk002"
SCORE_TYPE = "pit_strategy_profit_memory_existing_features_bottom_quartile_veto_effective_risk_cap"

OUT = base.LINE_DIR / "outputs" / STAGE_ID
STAGES_DIR = base.LINE_DIR / "stages"
STAGE_RECORD_PATH = STAGES_DIR / "20260709_2000_stage003_bottom_quartile_veto_effective_risk_cap_engine.md"

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
RISK_RESTORE_AUDIT_PATH = OUT / f"{OUTPUT_PREFIX}_risk_restore_audit_{MODEL_TAG}.csv"
DECISION_PATH = OUT / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUT / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUT / f"{OUTPUT_PREFIX}_equity_drawdown_{MODEL_TAG}.png"


def _configure_stage_modules() -> None:
    for module in (s2, base):
        module.STAGE_ID = STAGE_ID
        module.STAGE_LABEL = STAGE_LABEL
        module.MODEL_TAG = MODEL_TAG
        module.OUTPUT_PREFIX = OUTPUT_PREFIX
        module.CANDIDATE_VERSION = CANDIDATE_VERSION
        module.STRATEGY_NAME = STRATEGY_NAME
        module.SCORE_TYPE = SCORE_TYPE
        module.OUT = OUT
        module.STAGES_DIR = STAGES_DIR
        module.STAGE_RECORD_PATH = STAGE_RECORD_PATH
        module.FEATURE_PANEL_PATH = FEATURE_PANEL_PATH
        module.ELIGIBILITY_PATH = ELIGIBILITY_PATH
        module.ELIGIBILITY_AUDIT_PATH = ELIGIBILITY_AUDIT_PATH
        module.CANDIDATE_DAILY_PATH = CANDIDATE_DAILY_PATH
        module.CANDIDATE_ENTRY_CANDIDATES_PATH = CANDIDATE_ENTRY_CANDIDATES_PATH
        module.CANDIDATE_ENTRY_RISK_PATH = CANDIDATE_ENTRY_RISK_PATH
        module.CANDIDATE_TRADES_PATH = CANDIDATE_TRADES_PATH
        module.CANDIDATE_TRADE_EVENTS_PATH = CANDIDATE_TRADE_EVENTS_PATH
        module.CURVES_PATH = CURVES_PATH
        module.SUMMARY_PATH = SUMMARY_PATH
        module.AI_USAGE_AUDIT_PATH = AI_USAGE_AUDIT_PATH
        module.DECISION_PATH = DECISION_PATH
        module.REPORT_PATH = REPORT_PATH
        module.CHART_PATH = CHART_PATH


def _candidate_profile(metadata: dict[str, Any]) -> dict[str, Any]:
    profile = base.s847._c9_profile(metadata)
    spec = profile["spec"]
    profile_name = "stage003_full_market_ai_bottom25_veto_effective_risk002"
    capital = replace(
        spec.capital,
        variant=profile_name,
        label="Stage003 full-market PIT AI bottom25 veto + effective risk 0.02",
        account_capital=base.CAPITAL,
        c3_capital=base.CAPITAL,
        risk_multiplier=base.RISK_MULTIPLIER_FOR_LABEL,
        note=(
            f"{spec.capital.note} | Stage003 independent line. Same active bottom-quartile AI veto as Stage002, "
            "but OI-confirm risk restore is disabled so risk_ratio_* 0.02 is not amplified."
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
        "enable_oi_price_confirm_risk_restore": False,
        "oi_price_confirm_risk_restore_multiplier": 1.0,
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


def _risk_restore_audit(entry_risk: pd.DataFrame, entry_candidates: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for name, frame in (("entry_risk", entry_risk), ("entry_candidates", entry_candidates)):
        data = frame.copy()
        if data.empty:
            rows.append({"frame": name, "rows": 0})
            continue
        risk_multiplier = pd.to_numeric(data.get("risk_multiplier", 0.0), errors="coerce").fillna(0.0)
        oi_enabled = pd.to_numeric(data.get("oi_price_confirm_risk_restore_enabled", 0), errors="coerce").fillna(0).astype(int)
        oi_applied = pd.to_numeric(data.get("oi_price_confirm_risk_restore_applied", 0), errors="coerce").fillna(0).astype(int)
        risk_ratio = pd.to_numeric(data.get("risk_ratio", 0.0), errors="coerce").fillna(0.0)
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


def _decision(summary: pd.DataFrame, eligibility_audit: pd.DataFrame, ai_usage: pd.DataFrame, risk_audit: pd.DataFrame) -> dict[str, Any]:
    a = summary[summary["version"].eq(base.OFFICIAL_VERSION)].iloc[0].to_dict()
    c = summary[summary["version"].eq(CANDIDATE_VERSION)].iloc[0].to_dict()
    usage_summary = ai_usage[ai_usage["ai_product_pool_signal_date"].astype(str).eq("__summary__")]
    return {
        "stage": STAGE_LABEL,
        "stage_id": STAGE_ID,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S CST"),
        "hypothesis": "If risk_ratio_* is set to 0.02, inherited OI-confirm restore should be disabled to test the real effective-risk-2% version.",
        "selector": "Stage002 active full-market PIT bottom quartile veto",
        "target_base_risk_ratio": base.TARGET_BASE_RISK_RATIO,
        "disable_oi_price_confirm_risk_restore": True,
        "a_official": a,
        "c_candidate": c,
        "return_delta_pct": float(c["total_return_pct"] - a["total_return_pct"]),
        "drawdown_delta_pct": float(c["max_drawdown_pct"] - a["max_drawdown_pct"]),
        "min_monthly_selected_count": int(pd.to_numeric(eligibility_audit["selected_count"], errors="coerce").min()),
        "max_monthly_vetoed_count": int(pd.to_numeric(eligibility_audit["vetoed_count"], errors="coerce").max()),
        "ai_usage_summary": usage_summary.iloc[0].to_dict() if not usage_summary.empty else {},
        "risk_restore_audit": risk_audit.to_dict(orient="records"),
        "decision": (
            "stage003_continue_to_halfyear_if_independent_review_passes"
            if c["total_return_pct"] > 0
            and c["max_drawdown_pct"] > -70.0
            and c["max_broker10_margin_to_equity_pct"] <= 110.0
            else "stage003_stop_or_attribution_before_more_runs"
        ),
        "overfit_before": "no: this fixes effective-risk semantics exposed by review rather than tuning decimals.",
        "overfit_after": "pending_independent_review",
        "continue_value_before": "yes: validates whether Stage002 failed mainly because 0.02 was amplified by OI restore.",
        "continue_value_after": "pending_independent_review",
    }


def _plot(curves: pd.DataFrame) -> None:
    if curves.empty:
        return
    fig, axes = base.plt.subplots(2, 1, figsize=(13, 8), sharex=True)
    labels = {
        base.OFFICIAL_VERSION: "Official C9/15w",
        CANDIDATE_VERSION: "Stage003 bottom25 veto + effective risk 0.02",
    }
    colors = {base.OFFICIAL_VERSION: "#111827", CANDIDATE_VERSION: "#7c3aed"}
    for version, group in curves.groupby("version", sort=False):
        data = group.sort_values("date")
        x = pd.to_datetime(data["date"])
        equity = pd.to_numeric(data["account_equity_for_metrics"], errors="coerce").ffill()
        axes[0].plot(x, equity, label=labels.get(version, version), color=colors.get(version), linewidth=1.1)
        axes[1].plot(x, base._drawdown_pct(equity), label=labels.get(version, version), color=colors.get(version), linewidth=1.0)
    axes[0].axhline(base.CAPITAL, color="#64748b", linestyle="--", linewidth=0.9)
    axes[0].set_title("Stage003 A/C equity")
    axes[0].set_ylabel("account equity")
    axes[0].grid(alpha=0.25)
    axes[0].legend(loc="best")
    axes[1].axhline(-40.0, color="#111827", linestyle="--", linewidth=0.9)
    axes[1].set_title("Stage003 A/C drawdown")
    axes[1].set_ylabel("drawdown %")
    axes[1].grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=170)
    base.plt.close(fig)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return base._md_table(frame, max_rows=max_rows)


def _write_report(summary: pd.DataFrame, eligibility_audit: pd.DataFrame, ai_usage: pd.DataFrame, risk_audit: pd.DataFrame, decision: dict[str, Any]) -> None:
    lines = [
        "# Stage003 全市场 AI 底部四分位 veto + 有效风险 0.02 真实引擎",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        f"- line_id：`{LINE_ID}`",
        "- 阶段性质：独立研究线最小真实引擎 A/C；不改官方实盘、CTP、邮件或 launchd。",
        "- 外部调研判断：position sizing 必须按实际有效风险评估，不能只看 base risk ratio；本阶段修正 Stage002 暴露出的 OI restore 放大问题。",
        "- 运行前过拟合判断：否。这不是调小数，而是让用户要求的 `0.02` 与引擎实际有效风险一致。",
        "",
        "## A/C 结果",
        "",
        _md_table(summary[[
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
        ]]),
        "",
        "## AI 文件审计",
        "",
        _md_table(eligibility_audit.tail(12)),
        "",
        "## AI 使用审计",
        "",
        _md_table(ai_usage.head(20)),
        "",
        "## OI restore / 有效风险审计",
        "",
        _md_table(risk_audit),
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
        "# Stage003 全市场 AI 底部四分位 veto + 有效风险 0.02 真实引擎",
        "",
        f"- line_id：`{LINE_ID}`",
        "- 当前模式：`day`",
        f"- 记录时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        "- 阶段性质：独立研究线最小 A/C 真实引擎回测",
        "- 是否重要突破：否，Stage002 独立 review 后的有效风险语义验证",
        "- 是否触发A/B：是，A=官方 C9/15w；C=Stage002 active full-market bottom25 veto + risk_ratio_* 0.02 + OI restore disabled",
        "",
        "## 本次变更",
        "",
        f"- 新增脚本：`research/lines/{LINE_ID}/tools/stage003_bottom_quartile_veto_effective_risk_cap_engine.py`",
        "- 新增参数：`enable_oi_price_confirm_risk_restore=False`、`oi_price_confirm_risk_restore_multiplier=1.0`",
        "- 修改参数：继承 Stage002 active full-market bottom25 veto 与 `risk_ratio_* = 0.02`，但关闭 OI confirm 风险恢复，避免有效风险被放大到 `0.04`。",
        "- 删除参数：删除 OI confirm restore 对本候选的加风险效果。",
        "",
        "## 回测参数",
        "",
        f"- 数据区间：`{base.REQUESTED_START.date()}` 到 `{base.REQUESTED_END.date()}`",
        f"- 账户规模：`{base.CAPITAL:,.0f}`",
        "- 成本口径：沿用 C9 真实引擎原成本/slippage 配置。",
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
        f"- risk_restore_audit：`{RISK_RESTORE_AUDIT_PATH}`",
        "",
        "## 结论",
        "",
        f"- 本阶段结论：`{decision['decision']}`",
        "- 是否进入下一步：等待独立 agent review 后决定。",
        "- 下一步：若仍明显失败，停止 full-market broad-veto 方向，回到更窄 AI 承载或只读归因。",
        "",
        "## 过拟合反思",
        "",
        "- 运行前判断：否。关闭 OI restore 是修正有效风险定义，不是根据结果调小数。",
        "- 运行后判断：等待独立 review。",
        "",
        "## 继续价值反思",
        "",
        "- 运行前判断：有价值，因为 Stage002 发现 `0.02` 会被 OI restore 放大。",
        "- 运行后判断：等待独立 review。",
    ]
    STAGE_RECORD_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _append_back_log(summary: pd.DataFrame, decision: dict[str, Any]) -> None:
    c = summary[summary["version"].eq(CANDIDATE_VERSION)].iloc[0].to_dict()
    a = summary[summary["version"].eq(base.OFFICIAL_VERSION)].iloc[0].to_dict()
    text = (
        f"\n{datetime.now().strftime('%Y-%m-%d %H:%M CST')}：`{LINE_ID}` Stage003 完成 full-market active bottom25 veto + 有效风险 `0.02` "
        f"最小真实引擎 A/C，决策 `{decision['decision']}`。新增脚本 `research/lines/{LINE_ID}/tools/stage003_bottom_quartile_veto_effective_risk_cap_engine.py`；"
        f"新增 risk_restore_audit `{RISK_RESTORE_AUDIT_PATH}`，report `{REPORT_PATH}`。"
        "新增参数：`enable_oi_price_confirm_risk_restore=False`、`oi_price_confirm_risk_restore_multiplier=1.0`；"
        "修改参数：继承 Stage002 active bottom25 veto 与 `risk_ratio_* = 0.02`，但关闭 OI restore；删除参数：删除本候选的 OI confirm 加风险效果。"
        f"A 官方 C9/15w：期末权益 `{a['end_equity']:,.2f}`、总收益 `{a['total_return_pct']:.4f}%`、最大回撤 `{a['max_drawdown_pct']:.4f}%`、"
        f"Sharpe `{a['sharpe']:.4f}`、总滑点 `{a['total_slippage']:,.2f}`、总交易次数 `{a['total_trade_count']:,.0f}`、胜率 `{a['nonzero_daily_win_rate_pct']:.4f}%`。"
        f"C 候选：期末权益 `{c['end_equity']:,.2f}`、总收益 `{c['total_return_pct']:.4f}%`、最大回撤 `{c['max_drawdown_pct']:.4f}%`、"
        f"Sharpe `{c['sharpe']:.4f}`、总滑点 `{c['total_slippage']:,.2f}`、总交易次数 `{c['total_trade_count']:,.0f}`、胜率 `{c['nonzero_daily_win_rate_pct']:.4f}%`。"
        f"新增结果：C 相对 A 收益差 `{decision['return_delta_pct']:.4f}` 百分点，回撤差 `{decision['drawdown_delta_pct']:.4f}` 百分点。"
        "运行前过拟合反思：否，关闭 OI restore 是修正有效风险定义，不是扫风险小数；运行后过拟合反思：待独立 agent review。"
        "运行前继续价值反思：有，验证 Stage002 失败是否主要来自 OI restore 放大；运行后继续价值反思：待独立 agent review。\n"
    )
    with (base.ROOT / "back_log.md").open("a", encoding="utf-8") as fh:
        fh.write(text)


def _update_line(summary: pd.DataFrame, decision: dict[str, Any]) -> None:
    c = summary[summary["version"].eq(CANDIDATE_VERSION)].iloc[0].to_dict()
    addition = (
        "\n## Stage003\n\n"
        f"- 时间: `{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`\n"
        f"- 决策: `{decision['decision']}`\n"
        f"- C 期末权益: `{c['end_equity']:,.2f}`，总收益 `{c['total_return_pct']:.4f}%`，最大回撤 `{c['max_drawdown_pct']:.4f}%`，Sharpe `{c['sharpe']:.4f}`。\n"
        "- 状态: 已跑单起点真实引擎，等待独立 agent review 后再决定是否扩展逐半年多周期。\n"
    )
    with (base.LINE_DIR / "LINE.md").open("a", encoding="utf-8") as fh:
        fh.write(addition)


def build() -> dict[str, pd.DataFrame]:
    _configure_stage_modules()
    OUT.mkdir(parents=True, exist_ok=True)
    STAGES_DIR.mkdir(parents=True, exist_ok=True)

    universe = base._load_universe()
    calendar = base._load_trade_calendar()
    eval_dates = base._build_eval_dates(calendar)
    feature_panel = base._build_feature_panel(universe, eval_dates)
    feature_panel = s2._apply_bottom_quartile_veto(feature_panel)
    eligibility, eligibility_audit = s2._build_eligibility(feature_panel)

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
    risk_audit = _risk_restore_audit(frames.get("entry_risk", pd.DataFrame()), frames.get("entry_candidates", pd.DataFrame()))
    decision = _decision(summary, eligibility_audit, ai_usage, risk_audit)

    curves.to_csv(CURVES_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    ai_usage.to_csv(AI_USAGE_AUDIT_PATH, index=False, encoding="utf-8-sig")
    risk_audit.to_csv(RISK_RESTORE_AUDIT_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(base._json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _plot(curves)
    _write_report(summary, eligibility_audit, ai_usage, risk_audit, decision)
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
        "risk_audit": risk_audit,
    }


def main() -> None:
    outputs = build()
    print(outputs["summary"].to_string(index=False))
    print(outputs["risk_audit"].to_string(index=False))
    print(f"report={REPORT_PATH}")
    print(f"chart={CHART_PATH}")


if __name__ == "__main__":
    main()
