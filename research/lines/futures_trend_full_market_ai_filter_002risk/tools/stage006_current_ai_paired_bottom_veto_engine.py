#!/usr/bin/env python3
"""Stage006: paired current-official-AI A0/C test for the Stage005 veto.

The Stage005 independent review found an A/C pairing issue: C used the current
official AI eligibility file, while A was a frozen Stage167 curve generated with
an older AI file.  This stage fixes that by running both arms through the same
current C9 engine and the same current official AI file:

- A0: current official AI file, no full-market veto.
- C:  current official AI file, with full-market bottom-quartile veto.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
import json
from typing import Any

import numpy as np
import pandas as pd

import stage001_full_market_pit_ai_risk002_engine as base
import stage005_official_ai_pool_full_market_bottom_veto_engine as s005
from qmt_roll_official_live_config import OFFICIAL_LIVE_AI_ELIGIBILITY_PATH


LINE_ID = base.LINE_ID
STAGE_ID = "stage006_current_ai_paired_bottom_veto_engine"
STAGE_LABEL = "Stage006"
MODEL_TAG = f"{STAGE_ID}_v1"
OUTPUT_PREFIX = f"full_market_ai002_{STAGE_ID}"

A0_VERSION = "current_official_ai_no_veto_official_risk"
CANDIDATE_VERSION = "current_official_ai_full_market_bottom25_veto_official_risk"
STRATEGY_NAME_A0 = "current_official_ai_no_veto_entry_filter"
STRATEGY_NAME_C = "current_official_ai_full_market_bottom25_veto_entry_filter"
SCORE_TYPE_A0 = "current_official_ai_no_veto"
SCORE_TYPE_C = "current_official_ai_with_full_market_bottom25_pit_veto"

BOTTOM_VETO_QUANTILE = s005.BOTTOM_VETO_QUANTILE
MIN_ACTIVE_PRODUCTS_FOR_VETO = s005.MIN_ACTIVE_PRODUCTS_FOR_VETO

OUT = base.LINE_DIR / "outputs" / STAGE_ID
STAGES_DIR = base.LINE_DIR / "stages"
STAGE_RECORD_PATH = STAGES_DIR / "20260709_2245_stage006_current_ai_paired_bottom_veto_engine.md"

FEATURE_PANEL_PATH = OUT / f"{OUTPUT_PREFIX}_feature_panel_{MODEL_TAG}.csv.gz"
A0_ELIGIBILITY_PATH = OUT / f"{OUTPUT_PREFIX}_a0_eligibility_{MODEL_TAG}.csv"
C_ELIGIBILITY_PATH = OUT / f"{OUTPUT_PREFIX}_candidate_eligibility_{MODEL_TAG}.csv"
ELIGIBILITY_AUDIT_PATH = OUT / f"{OUTPUT_PREFIX}_eligibility_audit_{MODEL_TAG}.csv"
OVERLAY_AUDIT_PATH = OUT / f"{OUTPUT_PREFIX}_official_overlay_audit_{MODEL_TAG}.csv"
A0_DAILY_PATH = OUT / f"{OUTPUT_PREFIX}_a0_daily_{MODEL_TAG}.csv.gz"
CANDIDATE_DAILY_PATH = OUT / f"{OUTPUT_PREFIX}_candidate_daily_{MODEL_TAG}.csv.gz"
A0_ENTRY_CANDIDATES_PATH = OUT / f"{OUTPUT_PREFIX}_a0_entry_candidates_{MODEL_TAG}.csv.gz"
CANDIDATE_ENTRY_CANDIDATES_PATH = OUT / f"{OUTPUT_PREFIX}_candidate_entry_candidates_{MODEL_TAG}.csv.gz"
A0_ENTRY_RISK_PATH = OUT / f"{OUTPUT_PREFIX}_a0_entry_risk_{MODEL_TAG}.csv.gz"
CANDIDATE_ENTRY_RISK_PATH = OUT / f"{OUTPUT_PREFIX}_candidate_entry_risk_{MODEL_TAG}.csv.gz"
A0_TRADES_PATH = OUT / f"{OUTPUT_PREFIX}_a0_trades_{MODEL_TAG}.csv.gz"
CANDIDATE_TRADES_PATH = OUT / f"{OUTPUT_PREFIX}_candidate_trades_{MODEL_TAG}.csv.gz"
A0_TRADE_EVENTS_PATH = OUT / f"{OUTPUT_PREFIX}_a0_trade_events_{MODEL_TAG}.csv.gz"
CANDIDATE_TRADE_EVENTS_PATH = OUT / f"{OUTPUT_PREFIX}_candidate_trade_events_{MODEL_TAG}.csv.gz"
CURVES_PATH = OUT / f"{OUTPUT_PREFIX}_ac_curves_{MODEL_TAG}.csv.gz"
SUMMARY_PATH = OUT / f"{OUTPUT_PREFIX}_ac_summary_{MODEL_TAG}.csv"
AI_USAGE_AUDIT_PATH = OUT / f"{OUTPUT_PREFIX}_ai_usage_audit_{MODEL_TAG}.csv"
RISK_RESTORE_AUDIT_PATH = OUT / f"{OUTPUT_PREFIX}_risk_restore_audit_{MODEL_TAG}.csv"
DECISION_PATH = OUT / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUT / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUT / f"{OUTPUT_PREFIX}_equity_drawdown_{MODEL_TAG}.png"


def _official_eligibility_for_strategy(strategy_name: str, score_type: str) -> pd.DataFrame:
    data = pd.read_csv(OFFICIAL_LIVE_AI_ELIGIBILITY_PATH, encoding="utf-8-sig")
    data["eval_date"] = pd.to_datetime(data["eval_date"], errors="coerce").dt.date.astype(str)
    data["product_vt_symbol"] = data["product_vt_symbol"].astype(str)
    data["score"] = pd.to_numeric(data.get("score", 0.0), errors="coerce").fillna(0.0)
    data["score_rank"] = pd.to_numeric(data.get("score_rank", 0), errors="coerce").fillna(0).astype(int)
    data = data.sort_values(["eval_date", "score_rank", "product_vt_symbol"]).reset_index(drop=True)
    data["score_rank"] = data.groupby("eval_date").cumcount() + 1
    data["top_n"] = data.groupby("eval_date")["product_vt_symbol"].transform("count").astype(int)
    data["strategy"] = strategy_name
    data["score_type"] = score_type
    return data[["strategy", "score_type", "eval_date", "product_vt_symbol", "score", "score_rank", "top_n"]].copy()


def _metadata() -> dict[str, Any]:
    live_overrides = dict(base.build_official_live_strategy_overrides())
    supported_symbols = base.load_product_universe_symbols(str(live_overrides["product_universe_csv_path"]))
    return base.build_contract_metadata(supported_symbols=supported_symbols)


def _profile(metadata: dict[str, Any], *, version: str, strategy_name: str, eligibility_path: Any, label: str) -> dict[str, Any]:
    profile = base.s847._c9_profile(metadata)
    spec = profile["spec"]
    capital = replace(
        spec.capital,
        variant=version,
        label=label,
        account_capital=base.CAPITAL,
        c3_capital=base.CAPITAL,
        note=f"{spec.capital.note} | Stage006 paired current official AI file test. {label}",
    )
    live_overrides = dict(base.build_official_live_strategy_overrides())
    overrides = {
        **spec.overrides,
        **live_overrides,
        "enable_ai_product_pool_filter": True,
        "ai_product_pool_eligibility_path": str(eligibility_path),
        "ai_product_pool_strategy": strategy_name,
        "account_capital": base.CAPITAL,
        "c3_capital": base.CAPITAL,
    }
    result = dict(profile)
    result["profile"] = version
    result["strategy_cls"] = base.s847.QmtRollPortfolioStrategyStage847C9StopRetry
    result["spec"] = replace(spec, capital=capital, overrides=overrides, profile=version)
    return result


def _run_profile(metadata: dict[str, Any], profile: dict[str, Any], version: str) -> tuple[pd.DataFrame, dict[str, pd.DataFrame], Any]:
    original_start = base.s847.START
    original_end = base.s847.END
    original_minute_by_symbol = base.s847.s827._GLOBAL_MINUTE_BY_SYMBOL
    base.s901._ensure_c9_minute_bars(metadata)
    try:
        base.s847.START = base.REQUESTED_START.normalize()
        base.s847.END = base.REQUESTED_END.normalize()
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
    combined["version"] = version
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
        frame["version"] = version
        frame["stage"] = STAGE_LABEL
        frame["model_tag"] = MODEL_TAG
        frame["line_id"] = LINE_ID
    return combined, frames, spec


def _summarize_curve(frame: pd.DataFrame) -> dict[str, Any]:
    row = base._summarize_curve(frame)
    row["stage"] = STAGE_LABEL
    row["model_tag"] = MODEL_TAG
    row["line_id"] = LINE_ID
    return row


def _risk_restore_audit(frames_by_version: dict[str, dict[str, pd.DataFrame]]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for version, frames in frames_by_version.items():
        for name in ("entry_risk", "entry_candidates"):
            data = frames.get(name, pd.DataFrame()).copy()
            if data.empty:
                rows.append({"version": version, "frame": name, "rows": 0})
                continue
            risk_ratio = pd.to_numeric(data.get("risk_ratio", 0.0), errors="coerce").fillna(0.0)
            risk_multiplier = pd.to_numeric(data.get("risk_multiplier", 0.0), errors="coerce").fillna(0.0)
            oi_enabled = pd.to_numeric(data.get("oi_price_confirm_risk_restore_enabled", 0), errors="coerce").fillna(0).astype(int)
            oi_applied = pd.to_numeric(data.get("oi_price_confirm_risk_restore_applied", 0), errors="coerce").fillna(0).astype(int)
            rows.append(
                {
                    "version": version,
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


def _ai_usage_audit(frames_by_version: dict[str, dict[str, pd.DataFrame]]) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    for version, frames in frames_by_version.items():
        audit = base._ai_usage_audit(frames.get("entry_candidates", pd.DataFrame())).copy()
        audit.insert(0, "version", version)
        rows.append(audit)
    return pd.concat(rows, ignore_index=True, sort=False) if rows else pd.DataFrame()


def _decision(summary: pd.DataFrame, eligibility_audit: pd.DataFrame, ai_usage: pd.DataFrame, risk_audit: pd.DataFrame) -> dict[str, Any]:
    a0 = summary[summary["version"].eq(A0_VERSION)].iloc[0].to_dict()
    c = summary[summary["version"].eq(CANDIDATE_VERSION)].iloc[0].to_dict()
    return_retention = float(c["total_return_pct"] / a0["total_return_pct"]) if a0["total_return_pct"] else 0.0
    dd_delta = float(c["max_drawdown_pct"] - a0["max_drawdown_pct"])
    decision = (
        "stage006_continue_to_halfyear_if_independent_review_passes"
        if return_retention >= 0.50 and dd_delta >= 0.0
        else "stage006_stop_or_attribution_before_more_runs"
    )
    return {
        "stage": STAGE_LABEL,
        "stage_id": STAGE_ID,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S CST"),
        "hypothesis": "If the Stage005 effect survives a paired current-AI baseline, the veto signal is not merely AI file drift.",
        "official_ai_eligibility_path": str(OFFICIAL_LIVE_AI_ELIGIBILITY_PATH),
        "bottom_veto_quantile": BOTTOM_VETO_QUANTILE,
        "min_active_products_for_veto": MIN_ACTIVE_PRODUCTS_FOR_VETO,
        "a0_current_official_ai": a0,
        "c_candidate": c,
        "return_delta_pct": float(c["total_return_pct"] - a0["total_return_pct"]),
        "return_retention_ratio": return_retention,
        "drawdown_delta_pct": dd_delta,
        "total_vetoed_official_pool_rows": int(pd.to_numeric(eligibility_audit["vetoed_count"], errors="coerce").sum()),
        "total_kept_official_pool_rows": int(pd.to_numeric(eligibility_audit["kept_count"], errors="coerce").sum()),
        "ai_usage_summary": ai_usage[ai_usage["ai_product_pool_signal_date"].astype(str).eq("__summary__")].to_dict(orient="records"),
        "risk_restore_audit": risk_audit.to_dict(orient="records"),
        "decision": decision,
        "overfit_before": "low_to_medium: fixes evaluation pairing before any new parameter tuning.",
        "overfit_after": "pending_independent_review",
        "continue_value_before": "yes: Stage005 had a promising but unpaired result; this is the minimal validity repair.",
        "continue_value_after": "pending_independent_review",
    }


def _plot(curves: pd.DataFrame) -> None:
    if curves.empty:
        return
    fig, axes = base.plt.subplots(2, 1, figsize=(13, 8), sharex=True)
    labels = {
        A0_VERSION: "A0 current official AI",
        CANDIDATE_VERSION: "C current official AI + bottom25 veto",
    }
    colors = {A0_VERSION: "#111827", CANDIDATE_VERSION: "#059669"}
    for version, group in curves.groupby("version", sort=False):
        data = group.sort_values("date")
        x = pd.to_datetime(data["date"])
        equity = pd.to_numeric(data["account_equity_for_metrics"], errors="coerce").ffill()
        axes[0].plot(x, equity, label=labels.get(version, version), color=colors.get(version), linewidth=1.1)
        axes[1].plot(x, base._drawdown_pct(equity), label=labels.get(version, version), color=colors.get(version), linewidth=1.0)
    axes[0].axhline(base.CAPITAL, color="#64748b", linestyle="--", linewidth=0.9)
    axes[0].set_title("Stage006 paired current-AI equity")
    axes[0].set_ylabel("account equity")
    axes[0].grid(alpha=0.25)
    axes[0].legend(loc="best")
    axes[1].axhline(-40.0, color="#111827", linestyle="--", linewidth=0.9)
    axes[1].set_title("Stage006 paired current-AI drawdown")
    axes[1].set_ylabel("drawdown %")
    axes[1].grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=170)
    base.plt.close(fig)


def _write_report(summary: pd.DataFrame, eligibility_audit: pd.DataFrame, overlay_audit: pd.DataFrame, ai_usage: pd.DataFrame, risk_audit: pd.DataFrame, decision: dict[str, Any]) -> None:
    veto_rows = overlay_audit[overlay_audit["overlay_keep"].eq(0)].copy()
    lines = [
        "# Stage006 当前官方 AI 同口径配对 bottom25 veto 真实引擎",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        f"- line_id：`{LINE_ID}`",
        "- 阶段性质：修复 Stage005 审计阻塞的最小 A0/C 配对；不改官方实盘、CTP、邮件或 launchd。",
        "- 外部调研判断：paired evaluation 必须保持数据、窗口、成本和组合规则一致；本阶段只修复 AI 文件口径。",
        "- 运行前过拟合判断：低到中等。没有新增参数，只修正评估口径。",
        "- 运行前继续价值判断：有。Stage005 有强信号但 A/C 口径不严，本阶段判断信号是否仍成立。",
        "",
        "## A0/C 结果",
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
        base._md_table(ai_usage[ai_usage["ai_product_pool_signal_date"].astype(str).eq("__summary__")]),
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
    a0 = summary[summary["version"].eq(A0_VERSION)].iloc[0].to_dict()
    c = summary[summary["version"].eq(CANDIDATE_VERSION)].iloc[0].to_dict()
    lines = [
        "# Stage006 当前官方 AI 同口径配对 bottom25 veto 真实引擎",
        "",
        f"- line_id：`{LINE_ID}`",
        "- 当前模式：`day`",
        f"- 记录时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        "- 阶段性质：Stage005 审计阻塞修复 / 最小 A0/C 真实引擎配对",
        "- 是否重要突破：待独立 review；若通过则可进入逐半年多周期",
        "- 是否触发A/B：是，A0=当前官方 AI 无 veto；C=当前官方 AI + full-market bottom25 veto",
        "",
        "## 本次变更",
        "",
        f"- 新增脚本：`research/lines/{LINE_ID}/tools/stage006_current_ai_paired_bottom_veto_engine.py`",
        "- 新增参数：无；继承 Stage005 的 `BOTTOM_VETO_QUANTILE=0.25` 和 `MIN_ACTIVE_PRODUCTS_FOR_VETO=12`。",
        "- 修改参数：A0 与 C 均使用当前磁盘官方 AI 文件并通过同一真实引擎运行。",
        "- 删除参数：删除 Stage005 与冻结 Stage167 曲线直接对比的口径。",
        "",
        "## 回测参数",
        "",
        f"- 数据区间：`{base.REQUESTED_START.date()}` 到 `{base.REQUESTED_END.date()}`",
        f"- 账户规模：`{base.CAPITAL:,.0f}`",
        "- 成本/风险口径：沿用官方 C9 真实引擎原成本、风险和 OI restore。",
        "",
        "## 结果",
        "",
        f"- A0 期末权益：`{a0['end_equity']:,.2f}`；总收益 `{a0['total_return_pct']:.4f}%`；最大回撤 `{a0['max_drawdown_pct']:.4f}%`；Sharpe `{a0['sharpe']:.4f}`",
        f"- C 期末权益：`{c['end_equity']:,.2f}`",
        f"- C 总收益：`{c['total_return_pct']:.4f}%`",
        f"- C 最大回撤：`{c['max_drawdown_pct']:.4f}%`",
        f"- C Sharpe：`{c['sharpe']:.4f}`",
        f"- C 总滑点：`{c['total_slippage']:,.2f}`",
        f"- C 总交易次数：`{c['total_trade_count']:,.0f}`",
        f"- C 胜率：`{c['nonzero_daily_win_rate_pct']:.4f}%`，口径为非零交易日胜率，不是逐笔胜率。",
        f"- 收益保留率：`{decision['return_retention_ratio']:.4f}`",
        f"- C 相对 A0 收益差：`{decision['return_delta_pct']:.4f}` 百分点；回撤差：`{decision['drawdown_delta_pct']:.4f}` 百分点。",
        "",
        "## 输出文件",
        "",
        f"- report：`{REPORT_PATH}`",
        f"- summary：`{SUMMARY_PATH}`",
        f"- A0 eligibility：`{A0_ELIGIBILITY_PATH}`",
        f"- C eligibility：`{C_ELIGIBILITY_PATH}`",
        f"- overlay_audit：`{OVERLAY_AUDIT_PATH}`",
        f"- risk_restore_audit：`{RISK_RESTORE_AUDIT_PATH}`",
        f"- chart：`{CHART_PATH}`",
        "",
        "## 结论",
        "",
        f"- 本阶段结论：`{decision['decision']}`",
        "- 是否进入下一步：等待独立 agent review 后决定。",
        "- 下一步：若审计通过并保持收益保留/回撤改善，再进入逐半年多周期。",
        "",
        "## 过拟合反思",
        "",
        "- 运行前判断：低到中等。修复评估口径，不新增救参。",
        "- 运行后判断：等待独立 review。",
        "",
        "## 继续价值反思",
        "",
        "- 运行前判断：有价值。它是 Stage005 进入多周期前必须补的同口径验证。",
        "- 运行后判断：等待独立 review。",
    ]
    STAGE_RECORD_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _append_back_log(summary: pd.DataFrame, decision: dict[str, Any]) -> None:
    a0 = summary[summary["version"].eq(A0_VERSION)].iloc[0].to_dict()
    c = summary[summary["version"].eq(CANDIDATE_VERSION)].iloc[0].to_dict()
    text = (
        f"\n{datetime.now().strftime('%Y-%m-%d %H:%M CST')}：`{LINE_ID}` Stage006 完成当前官方 AI 同口径 A0/C bottom25 veto "
        f"最小真实引擎配对，决策 `{decision['decision']}`。新增脚本 `research/lines/{LINE_ID}/tools/stage006_current_ai_paired_bottom_veto_engine.py`；"
        f"新增 A0 eligibility `{A0_ELIGIBILITY_PATH}`，C eligibility `{C_ELIGIBILITY_PATH}`，overlay_audit `{OVERLAY_AUDIT_PATH}`，report `{REPORT_PATH}`。"
        "新增参数：无，继承 Stage005 `BOTTOM_VETO_QUANTILE=0.25`、`MIN_ACTIVE_PRODUCTS_FOR_VETO=12`；"
        "修改参数：A0 与 C 均使用当前磁盘官方 AI 文件并通过同一真实引擎运行；删除参数：删除 Stage005 与冻结 Stage167 曲线直接对比口径。"
        f"A0 当前官方 AI：期末权益 `{a0['end_equity']:,.2f}`、总收益 `{a0['total_return_pct']:.4f}%`、最大回撤 `{a0['max_drawdown_pct']:.4f}%`、"
        f"Sharpe `{a0['sharpe']:.4f}`、总滑点 `{a0['total_slippage']:,.2f}`、总交易次数 `{a0['total_trade_count']:,.0f}`、胜率 `{a0['nonzero_daily_win_rate_pct']:.4f}%`。"
        f"C 候选：期末权益 `{c['end_equity']:,.2f}`、总收益 `{c['total_return_pct']:.4f}%`、最大回撤 `{c['max_drawdown_pct']:.4f}%`、"
        f"Sharpe `{c['sharpe']:.4f}`、总滑点 `{c['total_slippage']:,.2f}`、总交易次数 `{c['total_trade_count']:,.0f}`、胜率 `{c['nonzero_daily_win_rate_pct']:.4f}%`。"
        f"新增结果：收益保留率 `{decision['return_retention_ratio']:.4f}`，C 相对 A0 收益差 `{decision['return_delta_pct']:.4f}` 百分点，"
        f"回撤差 `{decision['drawdown_delta_pct']:.4f}` 百分点；删除结果：删除 Stage005 严格 A/C 同口径已满足的假设。"
        "运行前过拟合反思：低到中等，修正评估口径不新增参数；运行后过拟合反思：待独立 agent review。"
        "运行前继续价值反思：有，Stage005 进入多周期前必须完成同口径验证；运行后继续价值反思：待独立 agent review。\n"
    )
    with (base.ROOT / "back_log.md").open("a", encoding="utf-8") as fh:
        fh.write(text)


def _update_line(summary: pd.DataFrame, decision: dict[str, Any]) -> None:
    a0 = summary[summary["version"].eq(A0_VERSION)].iloc[0].to_dict()
    c = summary[summary["version"].eq(CANDIDATE_VERSION)].iloc[0].to_dict()
    addition = (
        "\n## Stage006\n\n"
        f"- 时间: `{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`\n"
        f"- 决策: `{decision['decision']}`\n"
        f"- A0 期末权益: `{a0['end_equity']:,.2f}`，总收益 `{a0['total_return_pct']:.4f}%`，最大回撤 `{a0['max_drawdown_pct']:.4f}%`，Sharpe `{a0['sharpe']:.4f}`。\n"
        f"- C 期末权益: `{c['end_equity']:,.2f}`，总收益 `{c['total_return_pct']:.4f}%`，最大回撤 `{c['max_drawdown_pct']:.4f}%`，Sharpe `{c['sharpe']:.4f}`。\n"
        f"- 收益保留率: `{decision['return_retention_ratio']:.4f}`，回撤变化 `{decision['drawdown_delta_pct']:.4f}` 百分点。\n"
        "- 状态: 已跑同口径单起点真实引擎，等待独立 agent review 后再决定是否扩展逐半年多周期。\n"
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
    feature_panel = s005._full_market_score_lookup(feature_panel)
    a0_eligibility = _official_eligibility_for_strategy(STRATEGY_NAME_A0, SCORE_TYPE_A0)
    c_eligibility, eligibility_audit, overlay_audit = s005._build_eligibility(feature_panel)
    c_eligibility = c_eligibility.copy()
    c_eligibility["strategy"] = STRATEGY_NAME_C
    c_eligibility["score_type"] = SCORE_TYPE_C

    feature_panel.to_csv(FEATURE_PANEL_PATH, index=False, encoding="utf-8-sig")
    a0_eligibility.to_csv(A0_ELIGIBILITY_PATH, index=False, encoding="utf-8-sig")
    c_eligibility.to_csv(C_ELIGIBILITY_PATH, index=False, encoding="utf-8-sig")
    eligibility_audit.to_csv(ELIGIBILITY_AUDIT_PATH, index=False, encoding="utf-8-sig")
    overlay_audit.to_csv(OVERLAY_AUDIT_PATH, index=False, encoding="utf-8-sig")

    metadata = _metadata()
    a0_profile = _profile(
        metadata,
        version=A0_VERSION,
        strategy_name=STRATEGY_NAME_A0,
        eligibility_path=A0_ELIGIBILITY_PATH,
        label="A0 current official AI no veto",
    )
    c_profile = _profile(
        metadata,
        version=CANDIDATE_VERSION,
        strategy_name=STRATEGY_NAME_C,
        eligibility_path=C_ELIGIBILITY_PATH,
        label="C current official AI plus full-market bottom25 veto",
    )
    a0_daily, a0_frames, _ = _run_profile(metadata, a0_profile, A0_VERSION)
    c_daily, c_frames, _ = _run_profile(metadata, c_profile, CANDIDATE_VERSION)
    a0_daily.to_csv(A0_DAILY_PATH, index=False, encoding="utf-8-sig")
    c_daily.to_csv(CANDIDATE_DAILY_PATH, index=False, encoding="utf-8-sig")
    for frames, paths in (
        (a0_frames, {
            "entry_candidates": A0_ENTRY_CANDIDATES_PATH,
            "entry_risk": A0_ENTRY_RISK_PATH,
            "trades": A0_TRADES_PATH,
            "trade_events": A0_TRADE_EVENTS_PATH,
        }),
        (c_frames, {
            "entry_candidates": CANDIDATE_ENTRY_CANDIDATES_PATH,
            "entry_risk": CANDIDATE_ENTRY_RISK_PATH,
            "trades": CANDIDATE_TRADES_PATH,
            "trade_events": CANDIDATE_TRADE_EVENTS_PATH,
        }),
    ):
        for name, path in paths.items():
            frame = frames.get(name, pd.DataFrame()).copy()
            if not frame.empty:
                frame.to_csv(path, index=False, encoding="utf-8-sig")

    a0_curve = base._curve_for_metrics(a0_daily, A0_VERSION)
    c_curve = base._curve_for_metrics(c_daily, CANDIDATE_VERSION)
    curves = pd.concat([a0_curve, c_curve], ignore_index=True, sort=False)
    curves = curves.sort_values(["version", "date"]).reset_index(drop=True)
    curves["stage"] = STAGE_LABEL
    curves["model_tag"] = MODEL_TAG
    curves["line_id"] = LINE_ID
    summary = pd.DataFrame([_summarize_curve(group) for _, group in curves.groupby("version", sort=False)])
    frames_by_version = {A0_VERSION: a0_frames, CANDIDATE_VERSION: c_frames}
    ai_usage = _ai_usage_audit(frames_by_version)
    risk_audit = _risk_restore_audit(frames_by_version)
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
        "a0_eligibility": a0_eligibility,
        "c_eligibility": c_eligibility,
        "eligibility_audit": eligibility_audit,
        "overlay_audit": overlay_audit,
        "a0_daily": a0_daily,
        "candidate_daily": c_daily,
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
