#!/usr/bin/env python3
"""Stage008: guarded bottom25 veto that protects official high-rank names.

Stage007 showed the raw full-market bottom25 veto has defensive value but fails
strict return retention in 2022-01 and 2026-01.  This version keeps the same
bottom25 signal but reduces its authority: it can only veto the tail of the
official AI pool.  Official rank 1-4 is always protected.
"""

from __future__ import annotations

from datetime import datetime
import json
from typing import Any

import numpy as np
import pandas as pd

import stage007_current_ai_paired_bottom_veto_halfyear_engine as s007
import stage001_full_market_pit_ai_risk002_engine as base
import stage005_official_ai_pool_full_market_bottom_veto_engine as s005
from qmt_roll_official_live_config import OFFICIAL_LIVE_AI_ELIGIBILITY_PATH


LINE_ID = base.LINE_ID
STAGE_ID = "stage008_guarded_official_tail_bottom_veto_halfyear_engine"
STAGE_LABEL = "Stage008"
MODEL_TAG = f"{STAGE_ID}_v1"
OUTPUT_PREFIX = f"full_market_ai002_{STAGE_ID}"

A0_VERSION = s007.A0_VERSION
CANDIDATE_VERSION = "current_official_ai_guarded_tail_bottom25_veto_official_risk"
STRATEGY_NAME_A0 = "stage008_current_official_ai_no_veto_entry_filter"
STRATEGY_NAME_C = "stage008_current_official_ai_guarded_tail_bottom25_veto_entry_filter"
SCORE_TYPE_A0 = "stage008_current_official_ai_no_veto"
SCORE_TYPE_C = "stage008_current_official_ai_guarded_tail_bottom25_veto"

PROTECTED_OFFICIAL_RANK_MAX = 4
BOTTOM_VETO_QUANTILE = s007.BOTTOM_VETO_QUANTILE
MIN_ACTIVE_PRODUCTS_FOR_VETO = s007.MIN_ACTIVE_PRODUCTS_FOR_VETO
REQUESTED_START = s007.REQUESTED_START
REQUESTED_END = s007.REQUESTED_END

OUT = base.LINE_DIR / "outputs" / STAGE_ID
STAGES_DIR = base.LINE_DIR / "stages"
STAGE_RECORD_PATH = STAGES_DIR / "20260709_2315_stage008_guarded_official_tail_bottom_veto_halfyear_engine.md"

FEATURE_PANEL_PATH = OUT / f"{OUTPUT_PREFIX}_feature_panel_{MODEL_TAG}.csv.gz"
A0_ELIGIBILITY_PATH = OUT / f"{OUTPUT_PREFIX}_a0_eligibility_{MODEL_TAG}.csv"
C_ELIGIBILITY_PATH = OUT / f"{OUTPUT_PREFIX}_candidate_eligibility_{MODEL_TAG}.csv"
ELIGIBILITY_AUDIT_PATH = OUT / f"{OUTPUT_PREFIX}_eligibility_audit_{MODEL_TAG}.csv"
OVERLAY_AUDIT_PATH = OUT / f"{OUTPUT_PREFIX}_official_overlay_audit_{MODEL_TAG}.csv"
CURVES_PATH = OUT / f"{OUTPUT_PREFIX}_ac_curves_{MODEL_TAG}.csv.gz"
SUMMARY_PATH = OUT / f"{OUTPUT_PREFIX}_ac_summary_{MODEL_TAG}.csv"
PAIR_SUMMARY_PATH = OUT / f"{OUTPUT_PREFIX}_pair_summary_{MODEL_TAG}.csv"
STATS_PATH = OUT / f"{OUTPUT_PREFIX}_stats_{MODEL_TAG}.csv"
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
    data["top_n"] = pd.to_numeric(data.get("top_n", 0), errors="coerce").fillna(0).astype(int)
    data = data.sort_values(["eval_date", "score_rank", "product_vt_symbol"]).reset_index(drop=True)
    data["score_rank"] = data.groupby("eval_date").cumcount() + 1
    data["top_n"] = data.groupby("eval_date")["product_vt_symbol"].transform("count").astype(int)
    data["strategy"] = strategy_name
    data["score_type"] = score_type
    return data[["strategy", "score_type", "eval_date", "product_vt_symbol", "score", "score_rank", "top_n"]].copy()


def _build_candidate_eligibility(feature_panel: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    score_panel = s005._full_market_score_lookup(feature_panel)
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
    merged["official_rank_protected"] = merged["official_score_rank"].le(PROTECTED_OFFICIAL_RANK_MAX).astype(int)
    merged["guarded_bottom_veto"] = (
        merged["full_market_bottom_veto"].eq(1) & merged["official_rank_protected"].eq(0)
    ).astype(int)
    merged["overlay_keep"] = 1
    merged.loc[merged["guarded_bottom_veto"].eq(1), "overlay_keep"] = 0
    merged["overlay_reason"] = "official_pool_kept"
    merged.loc[merged["official_rank_protected"].eq(1), "overlay_reason"] = "official_rank_protected"
    merged.loc[merged["guarded_bottom_veto"].eq(1), "overlay_reason"] = "tail_product_full_market_bottom25_veto"
    merged.loc[merged["full_market_score_available"].eq(0), "overlay_reason"] = "official_pool_no_full_market_panel_keep"

    kept = merged[merged["overlay_keep"].eq(1)].copy()
    kept = kept.sort_values(["eval_date", "official_score_rank", "product_vt_symbol"]).reset_index(drop=True)
    kept["score"] = kept["official_score"]
    kept["score_rank"] = kept.groupby("eval_date").cumcount() + 1
    kept["top_n"] = kept.groupby("eval_date")["product_vt_symbol"].transform("count").astype(int)
    kept["strategy"] = STRATEGY_NAME_C
    kept["score_type"] = SCORE_TYPE_C
    eligibility = kept[["strategy", "score_type", "eval_date", "product_vt_symbol", "score", "score_rank", "top_n"]].copy()

    overlay_audit = merged[
        [
            "eval_date",
            "product_vt_symbol",
            "official_score",
            "official_score_rank",
            "official_top_n",
            "official_rank_protected",
            "full_market_score",
            "data_available",
            "full_market_active_count",
            "full_market_score_rank_available",
            "full_market_rank_pct_available",
            "full_market_bottom_veto",
            "guarded_bottom_veto",
            "overlay_keep",
            "overlay_reason",
        ]
    ].copy()
    eligibility_audit = (
        merged.groupby("eval_date", as_index=False)
        .agg(
            official_count=("product_vt_symbol", "count"),
            protected_count=("official_rank_protected", "sum"),
            kept_count=("overlay_keep", "sum"),
            raw_vetoed_count=("full_market_bottom_veto", "sum"),
            guarded_vetoed_count=("guarded_bottom_veto", "sum"),
            no_full_market_panel_count=("full_market_score_available", lambda s: int((s == 0).sum())),
            min_full_market_rank_pct=("full_market_rank_pct_available", "min"),
            max_full_market_rank_pct=("full_market_rank_pct_available", "max"),
            active_count=("full_market_active_count", "max"),
        )
        .sort_values("eval_date")
    )
    return eligibility, eligibility_audit, overlay_audit


def _profile(metadata: dict[str, Any], *, version: str, strategy_name: str, eligibility_path: Any, label: str) -> dict[str, Any]:
    return s007._profile(metadata, version=version, strategy_name=strategy_name, eligibility_path=eligibility_path, label=label)


def _decision(pair_summary: pd.DataFrame, stats: pd.DataFrame, ai_usage: pd.DataFrame, risk_audit: pd.DataFrame) -> dict[str, Any]:
    stat = stats.iloc[0].to_dict()
    sample_count = int(stat["sample_count"])
    decision = (
        "stage008_candidate_for_cost_sensitivity_and_independent_review"
        if int(stat["return50_pass_count"]) == sample_count
        and int(stat["drawdown_improved_count"]) >= max(1, sample_count - 1)
        and float(stat["min_return_retention_ratio"]) >= 0.50
        and int(stat["c_positive_count"]) == sample_count
        else "stage008_stop_or_attribution_before_more_runs"
    )
    return {
        "stage": STAGE_LABEL,
        "stage_id": STAGE_ID,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S CST"),
        "official_ai_path": str(OFFICIAL_LIVE_AI_ELIGIBILITY_PATH),
        "official_ai_sha16": s007._sha16(OFFICIAL_LIVE_AI_ELIGIBILITY_PATH),
        "a0_eligibility_sha16": s007._sha16(A0_ELIGIBILITY_PATH),
        "candidate_eligibility_sha16": s007._sha16(C_ELIGIBILITY_PATH),
        "bottom_veto_quantile": BOTTOM_VETO_QUANTILE,
        "protected_official_rank_max": PROTECTED_OFFICIAL_RANK_MAX,
        "min_active_products_for_veto": MIN_ACTIVE_PRODUCTS_FOR_VETO,
        "stats": stat,
        "pair_summary_preview": pair_summary.to_dict(orient="records"),
        "ai_usage_summary_rows": ai_usage[ai_usage["ai_product_pool_signal_date"].astype(str).eq("__summary__")].to_dict(orient="records"),
        "risk_restore_audit_rows": risk_audit.to_dict(orient="records"),
        "decision": decision,
        "overfit_before": "medium: one guarded structural variant after Stage007 failure; no threshold sweep beyond protecting the official top half.",
        "overfit_after": "pending_independent_review",
        "continue_value_before": "yes: tests whether veto value survives when official high-confidence core is protected.",
        "continue_value_after": "pending_independent_review",
    }


def _pair_summary(summary: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for start_month, group in summary.groupby("requested_start_month", sort=True):
        a0 = group[group["version"].eq(A0_VERSION)].iloc[0]
        c = group[group["version"].eq(CANDIDATE_VERSION)].iloc[0]
        rows.append(
            {
                "requested_start_month": start_month,
                "a0_end_equity": float(a0["end_equity"]),
                "c_end_equity": float(c["end_equity"]),
                "a0_total_return_pct": float(a0["total_return_pct"]),
                "c_total_return_pct": float(c["total_return_pct"]),
                "return_retention_ratio": float(c["total_return_pct"] / a0["total_return_pct"]) if float(a0["total_return_pct"]) else np.nan,
                "return_delta_pct": float(c["total_return_pct"] - a0["total_return_pct"]),
                "a0_max_drawdown_pct": float(a0["max_drawdown_pct"]),
                "c_max_drawdown_pct": float(c["max_drawdown_pct"]),
                "drawdown_delta_pct": float(c["max_drawdown_pct"] - a0["max_drawdown_pct"]),
                "a0_sharpe": float(a0["sharpe"]),
                "c_sharpe": float(c["sharpe"]),
                "sharpe_delta": float(c["sharpe"] - a0["sharpe"]),
                "a0_total_trade_count": float(a0["total_trade_count"]),
                "c_total_trade_count": float(c["total_trade_count"]),
                "a0_total_slippage": float(a0["total_slippage"]),
                "c_total_slippage": float(c["total_slippage"]),
                "passes_return50": int(float(c["total_return_pct"]) >= float(a0["total_return_pct"]) * 0.50),
                "drawdown_improved": int(float(c["max_drawdown_pct"]) >= float(a0["max_drawdown_pct"])),
                "c_positive": int(float(c["total_return_pct"]) > 0.0),
            }
        )
    return pd.DataFrame(rows).sort_values("requested_start_month").reset_index(drop=True)


def _plot(curves: pd.DataFrame) -> None:
    s007.CHART_PATH = CHART_PATH
    s007.A0_VERSION = A0_VERSION
    old_candidate = s007.CANDIDATE_VERSION
    try:
        s007.CANDIDATE_VERSION = CANDIDATE_VERSION
        s007._plot(curves)
    finally:
        s007.CANDIDATE_VERSION = old_candidate


def _write_report(summary: pd.DataFrame, pair_summary: pd.DataFrame, stats: pd.DataFrame, decision: dict[str, Any]) -> None:
    lines = [
        "# Stage008 guarded official-tail bottom25 veto 逐半年验证",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        f"- line_id：`{LINE_ID}`",
        f"- 规则：保护 official rank <= `{PROTECTED_OFFICIAL_RANK_MAX}`，只允许 full-market bottom25 veto official 尾部。",
        "- 阶段性质：Stage007 失败后的唯一 guarded 结构验证；不改官方实盘、CTP、邮件或 launchd。",
        "- 外部调研判断：meta-label/veto 应该低权限叠加在 primary signal 上，不应覆盖核心高置信信号。",
        "- 运行前过拟合判断：中等。它针对 Stage007 失败做结构保护，但不扫分位或 rank 小数。",
        "- 运行前继续价值判断：有。验证防守收益是否能保留，同时修复 2022/2026 过度否决。",
        "",
        "## 统计汇总",
        "",
        base._md_table(stats),
        "",
        "## A0/C 配对结果",
        "",
        base._md_table(pair_summary),
        "",
        "## 分版本 summary",
        "",
        base._md_table(summary[[
            "requested_start_month",
            "version",
            "end_equity",
            "total_return_pct",
            "max_drawdown_pct",
            "sharpe",
            "total_slippage",
            "total_trade_count",
            "nonzero_daily_win_rate_pct",
            "max_broker10_margin_to_equity_pct",
        ]]),
        "",
        "## 决策",
        "",
        f"- 决策：`{decision['decision']}`",
        f"- 输入 hash：official_ai `{decision['official_ai_sha16']}`，A0 `{decision['a0_eligibility_sha16']}`，C `{decision['candidate_eligibility_sha16']}`",
        f"- 输出图：`{CHART_PATH}`",
        "- 运行后过拟合判断：等待独立 agent review。",
        "- 运行后继续价值判断：等待独立 agent review。",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_stage_record(pair_summary: pd.DataFrame, stats: pd.DataFrame, decision: dict[str, Any]) -> None:
    stat = stats.iloc[0].to_dict()
    lines = [
        "# Stage008 guarded official-tail bottom25 veto 逐半年验证",
        "",
        f"- line_id：`{LINE_ID}`",
        "- 当前模式：`day`",
        f"- 记录时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        "- 阶段性质：Stage007 失败后的 guarded 结构验证",
        "- 是否重要突破：待独立 review",
        "- 是否触发A/B：是，A0=当前官方 AI 无 veto；C=当前官方 AI + guarded tail bottom25 veto",
        "",
        "## 本次变更",
        "",
        f"- 新增脚本：`research/lines/{LINE_ID}/tools/stage008_guarded_official_tail_bottom_veto_halfyear_engine.py`",
        f"- 新增参数：`PROTECTED_OFFICIAL_RANK_MAX={PROTECTED_OFFICIAL_RANK_MAX}`。",
        "- 修改参数：full-market bottom25 veto 只允许作用于 official rank 5 及以后。",
        "- 删除参数：无。",
        "",
        "## 回测参数",
        "",
        f"- 起点：`{stat['start_min']}` 到 `{stat['start_max']}`，共 `{int(stat['sample_count'])}` 个。",
        f"- 终点：`{REQUESTED_END.date()}`",
        f"- 账户规模：`{base.CAPITAL:,.0f}`",
        "- 成本/风险口径：沿用官方 C9 真实引擎原成本、风险和 OI restore。",
        "",
        "## 结果",
        "",
        f"- C 正收益数：`{int(stat['c_positive_count'])}/{int(stat['sample_count'])}`",
        f"- 收益保留 >=50%：`{int(stat['return50_pass_count'])}/{int(stat['sample_count'])}`",
        f"- 回撤改善：`{int(stat['drawdown_improved_count'])}/{int(stat['sample_count'])}`",
        f"- 最小/中位收益保留：`{float(stat['min_return_retention_ratio']):.4f}` / `{float(stat['median_return_retention_ratio']):.4f}`",
        f"- C 最小/中位/最大收益：`{float(stat['min_c_return_pct']):.4f}%` / `{float(stat['median_c_return_pct']):.4f}%` / `{float(stat['max_c_return_pct']):.4f}%`",
        f"- C 最差/中位回撤：`{float(stat['worst_c_drawdown_pct']):.4f}%` / `{float(stat['median_c_drawdown_pct']):.4f}%`",
        f"- 回撤变化最小/中位：`{float(stat['min_drawdown_delta_pct']):.4f}` / `{float(stat['median_drawdown_delta_pct']):.4f}` 百分点",
        "",
        "## 输出文件",
        "",
        f"- report：`{REPORT_PATH}`",
        f"- summary：`{SUMMARY_PATH}`",
        f"- pair_summary：`{PAIR_SUMMARY_PATH}`",
        f"- stats：`{STATS_PATH}`",
        f"- chart：`{CHART_PATH}`",
        "",
        "## 结论",
        "",
        f"- 本阶段结论：`{decision['decision']}`",
        "- 是否进入下一步：等待独立 agent review 后决定。",
        "",
        "## 过拟合反思",
        "",
        "- 运行前判断：中等。只做一个结构保护版本，不扫参数。",
        "- 运行后判断：等待独立 review。",
        "",
        "## 继续价值反思",
        "",
        "- 运行前判断：有价值。它直接验证 full-market veto 是否应只作用于 official 尾部。",
        "- 运行后判断：等待独立 review。",
    ]
    STAGE_RECORD_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _append_back_log(pair_summary: pd.DataFrame, stats: pd.DataFrame, decision: dict[str, Any]) -> None:
    stat = stats.iloc[0].to_dict()
    text = (
        f"\n{datetime.now().strftime('%Y-%m-%d %H:%M CST')}：`{LINE_ID}` Stage008 完成 guarded official-tail bottom25 veto "
        f"逐半年 A0/C 真实引擎验证，决策 `{decision['decision']}`。新增脚本 `research/lines/{LINE_ID}/tools/stage008_guarded_official_tail_bottom_veto_halfyear_engine.py`；"
        f"新增参数 `PROTECTED_OFFICIAL_RANK_MAX={PROTECTED_OFFICIAL_RANK_MAX}`；修改参数：full-market bottom25 veto 只作用于 official rank 5 及以后；删除参数：无。"
        f"新增结果：样本 `{int(stat['sample_count'])}`，C 正收益 `{int(stat['c_positive_count'])}`，收益保留>=50% `{int(stat['return50_pass_count'])}/{int(stat['sample_count'])}`，"
        f"回撤改善 `{int(stat['drawdown_improved_count'])}/{int(stat['sample_count'])}`，最小/中位收益保留 `{float(stat['min_return_retention_ratio']):.4f}/{float(stat['median_return_retention_ratio']):.4f}`，"
        f"C 最小/中位/最大收益 `{float(stat['min_c_return_pct']):.4f}%/{float(stat['median_c_return_pct']):.4f}%/{float(stat['max_c_return_pct']):.4f}%`，"
        f"C 最差/中位回撤 `{float(stat['worst_c_drawdown_pct']):.4f}%/{float(stat['median_c_drawdown_pct']):.4f}%`，"
        f"回撤变化最小/中位 `{float(stat['min_drawdown_delta_pct']):.4f}/{float(stat['median_drawdown_delta_pct']):.4f}` 百分点。"
        "运行前过拟合反思：中等，唯一 guarded 结构版本不扫参；运行后过拟合反思：待独立 agent review。"
        "运行前继续价值反思：有，验证 veto 是否应只作用于 official 尾部；运行后继续价值反思：待独立 agent review。\n"
    )
    with (base.ROOT / "back_log.md").open("a", encoding="utf-8") as fh:
        fh.write(text)


def _update_line(stats: pd.DataFrame, decision: dict[str, Any]) -> None:
    stat = stats.iloc[0].to_dict()
    addition = (
        "\n## Stage008\n\n"
        f"- 时间: `{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`\n"
        f"- 决策: `{decision['decision']}`\n"
        f"- 规则: 保护 official rank <= `{PROTECTED_OFFICIAL_RANK_MAX}`，full-market bottom25 veto 只作用于 official 尾部。\n"
        f"- 样本数: `{int(stat['sample_count'])}`，C 正收益 `{int(stat['c_positive_count'])}`，收益保留>=50% `{int(stat['return50_pass_count'])}/{int(stat['sample_count'])}`，回撤改善 `{int(stat['drawdown_improved_count'])}/{int(stat['sample_count'])}`。\n"
        f"- 最小/中位收益保留: `{float(stat['min_return_retention_ratio']):.4f}` / `{float(stat['median_return_retention_ratio']):.4f}`；C 最差回撤 `{float(stat['worst_c_drawdown_pct']):.4f}%`。\n"
        "- 状态: 已跑逐半年多周期真实引擎，等待独立 agent review。\n"
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
    a0_eligibility = _official_eligibility_for_strategy(STRATEGY_NAME_A0, SCORE_TYPE_A0)
    c_eligibility, eligibility_audit, overlay_audit = _build_candidate_eligibility(feature_panel)
    feature_panel.to_csv(FEATURE_PANEL_PATH, index=False, encoding="utf-8-sig")
    a0_eligibility.to_csv(A0_ELIGIBILITY_PATH, index=False, encoding="utf-8-sig")
    c_eligibility.to_csv(C_ELIGIBILITY_PATH, index=False, encoding="utf-8-sig")
    eligibility_audit.to_csv(ELIGIBILITY_AUDIT_PATH, index=False, encoding="utf-8-sig")
    overlay_audit.to_csv(OVERLAY_AUDIT_PATH, index=False, encoding="utf-8-sig")

    metadata = s007._metadata()
    a0_profile = _profile(
        metadata,
        version=A0_VERSION,
        strategy_name=STRATEGY_NAME_A0,
        eligibility_path=A0_ELIGIBILITY_PATH,
        label="Stage008 A0 current official AI no veto",
    )
    c_profile = _profile(
        metadata,
        version=CANDIDATE_VERSION,
        strategy_name=STRATEGY_NAME_C,
        eligibility_path=C_ELIGIBILITY_PATH,
        label="Stage008 C guarded official-tail full-market bottom25 veto",
    )

    curves: list[pd.DataFrame] = []
    frames_rows: list[tuple[str, str, dict[str, pd.DataFrame]]] = []
    for start in s007._start_dates():
        start_month = s007._start_month_text(start)
        print(f"running {start_month} A0", flush=True)
        a0_daily, a0_frames = s007._run_profile_for_start(metadata, a0_profile, A0_VERSION, start)
        print(f"running {start_month} C", flush=True)
        c_daily, c_frames = s007._run_profile_for_start(metadata, c_profile, CANDIDATE_VERSION, start)
        curves.append(base._curve_for_metrics(a0_daily, A0_VERSION))
        curves.append(base._curve_for_metrics(c_daily, CANDIDATE_VERSION))
        frames_rows.append((start_month, A0_VERSION, a0_frames))
        frames_rows.append((start_month, CANDIDATE_VERSION, c_frames))

    curve_frame = pd.concat(curves, ignore_index=True, sort=False)
    curve_frame = curve_frame.sort_values(["requested_start_month", "version", "date"]).reset_index(drop=True)
    curve_frame["stage"] = STAGE_LABEL
    curve_frame["model_tag"] = MODEL_TAG
    curve_frame["line_id"] = LINE_ID
    summary = pd.DataFrame([
        s007._summarize_curve(group)
        for _, group in curve_frame.groupby(["requested_start_month", "version"], sort=True)
    ])
    summary["stage"] = STAGE_LABEL
    summary["model_tag"] = MODEL_TAG
    pair = _pair_summary(summary)
    stats = s007._stats(pair)
    stats["stage"] = STAGE_LABEL
    stats["model_tag"] = MODEL_TAG
    ai_usage = s007._ai_usage_audit(frames_rows)
    risk_audit = s007._risk_restore_audit(frames_rows)
    decision = _decision(pair, stats, ai_usage, risk_audit)

    curve_frame.to_csv(CURVES_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    pair.to_csv(PAIR_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    stats.to_csv(STATS_PATH, index=False, encoding="utf-8-sig")
    ai_usage.to_csv(AI_USAGE_AUDIT_PATH, index=False, encoding="utf-8-sig")
    risk_audit.to_csv(RISK_RESTORE_AUDIT_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(base._json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _plot(curve_frame)
    _write_report(summary, pair, stats, decision)
    _write_stage_record(pair, stats, decision)
    _append_back_log(pair, stats, decision)
    _update_line(stats, decision)
    return {
        "feature_panel": feature_panel,
        "a0_eligibility": a0_eligibility,
        "c_eligibility": c_eligibility,
        "eligibility_audit": eligibility_audit,
        "overlay_audit": overlay_audit,
        "curves": curve_frame,
        "summary": summary,
        "pair_summary": pair,
        "stats": stats,
        "ai_usage": ai_usage,
        "risk_audit": risk_audit,
    }


def main() -> None:
    outputs = build()
    print(outputs["stats"].to_string(index=False))
    print(outputs["pair_summary"].to_string(index=False))
    print(f"report={REPORT_PATH}")
    print(f"chart={CHART_PATH}")


if __name__ == "__main__":
    main()
