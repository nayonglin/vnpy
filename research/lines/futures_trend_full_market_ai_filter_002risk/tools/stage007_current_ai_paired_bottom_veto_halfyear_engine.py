#!/usr/bin/env python3
"""Stage007: half-year paired validation for the Stage006 bottom25 veto."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import stage001_full_market_pit_ai_risk002_engine as base
import stage005_official_ai_pool_full_market_bottom_veto_engine as s005
import stage006_current_ai_paired_bottom_veto_engine as s006
from qmt_roll_official_live_config import OFFICIAL_LIVE_AI_ELIGIBILITY_PATH


LINE_ID = base.LINE_ID
STAGE_ID = "stage007_current_ai_paired_bottom_veto_halfyear_engine"
STAGE_LABEL = "Stage007"
MODEL_TAG = f"{STAGE_ID}_v1"
OUTPUT_PREFIX = f"full_market_ai002_{STAGE_ID}"

A0_VERSION = "current_official_ai_no_veto_official_risk"
CANDIDATE_VERSION = "current_official_ai_full_market_bottom25_veto_official_risk"
STRATEGY_NAME_A0 = "stage007_current_official_ai_no_veto_entry_filter"
STRATEGY_NAME_C = "stage007_current_official_ai_full_market_bottom25_veto_entry_filter"
SCORE_TYPE_A0 = "stage007_current_official_ai_no_veto"
SCORE_TYPE_C = "stage007_current_official_ai_with_full_market_bottom25_pit_veto"

REQUESTED_START = pd.Timestamp("2020-01-01")
REQUESTED_END = pd.Timestamp("2026-06-30")
START_MONTHS = (1, 7)
BOTTOM_VETO_QUANTILE = s005.BOTTOM_VETO_QUANTILE
MIN_ACTIVE_PRODUCTS_FOR_VETO = s005.MIN_ACTIVE_PRODUCTS_FOR_VETO

OUT = base.LINE_DIR / "outputs" / STAGE_ID
STAGES_DIR = base.LINE_DIR / "stages"
STAGE_RECORD_PATH = STAGES_DIR / "20260709_2255_stage007_current_ai_paired_bottom_veto_halfyear_engine.md"

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


def _sha16(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()[:16]


def _start_dates() -> list[pd.Timestamp]:
    starts: list[pd.Timestamp] = []
    for year in range(REQUESTED_START.year, REQUESTED_END.year + 1):
        for month in START_MONTHS:
            start = pd.Timestamp(year=year, month=month, day=1)
            if REQUESTED_START <= start <= REQUESTED_END:
                starts.append(start)
    return starts


def _start_month_text(value: pd.Timestamp) -> str:
    return pd.Timestamp(value).strftime("%Y-%m")


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


def _build_candidate_eligibility_preserve_official(feature_panel: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
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
    merged["overlay_keep"] = 1
    merged.loc[merged["full_market_bottom_veto"].eq(1), "overlay_keep"] = 0
    merged["overlay_reason"] = "official_pool_kept"
    merged.loc[merged["full_market_bottom_veto"].eq(1), "overlay_reason"] = "official_pool_product_in_full_market_bottom25"
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
    supported_symbols = base.load_product_universe_symbols(str(live_overrides["product_universe_csv_path"]))
    return base.build_contract_metadata(supported_symbols=supported_symbols)


def _profile(metadata: dict[str, Any], *, version: str, strategy_name: str, eligibility_path: Path, label: str) -> dict[str, Any]:
    profile = base.s847._c9_profile(metadata)
    spec = profile["spec"]
    capital = replace(
        spec.capital,
        variant=version,
        label=label,
        account_capital=base.CAPITAL,
        c3_capital=base.CAPITAL,
        note=f"{spec.capital.note} | Stage007 half-year paired current official AI test. {label}",
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


def _run_profile_for_start(metadata: dict[str, Any], profile: dict[str, Any], version: str, start: pd.Timestamp) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    original_start = base.s847.START
    original_end = base.s847.END
    original_minute_by_symbol = base.s847.s827._GLOBAL_MINUTE_BY_SYMBOL
    base.s901._ensure_c9_minute_bars(metadata)
    try:
        base.s847.START = start.normalize()
        base.s847.END = REQUESTED_END.normalize()
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
    combined["requested_start_month"] = _start_month_text(start)
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
        frame["requested_start_month"] = _start_month_text(start)
        frame["stage"] = STAGE_LABEL
        frame["model_tag"] = MODEL_TAG
        frame["line_id"] = LINE_ID
    return combined, frames


def _summarize_curve(frame: pd.DataFrame) -> dict[str, Any]:
    row = base._summarize_curve(frame)
    row["stage"] = STAGE_LABEL
    row["model_tag"] = MODEL_TAG
    row["line_id"] = LINE_ID
    row["requested_start_month"] = str(frame["requested_start_month"].iloc[0])
    return row


def _risk_restore_audit(frames_rows: list[tuple[str, str, dict[str, pd.DataFrame]]]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for start_month, version, frames in frames_rows:
        for name in ("entry_risk", "entry_candidates"):
            data = frames.get(name, pd.DataFrame()).copy()
            if data.empty:
                rows.append({"requested_start_month": start_month, "version": version, "frame": name, "rows": 0})
                continue
            risk_ratio = pd.to_numeric(data.get("risk_ratio", 0.0), errors="coerce").fillna(0.0)
            risk_multiplier = pd.to_numeric(data.get("risk_multiplier", 0.0), errors="coerce").fillna(0.0)
            oi_enabled = pd.to_numeric(data.get("oi_price_confirm_risk_restore_enabled", 0), errors="coerce").fillna(0).astype(int)
            oi_applied = pd.to_numeric(data.get("oi_price_confirm_risk_restore_applied", 0), errors="coerce").fillna(0).astype(int)
            rows.append(
                {
                    "requested_start_month": start_month,
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


def _ai_usage_audit(frames_rows: list[tuple[str, str, dict[str, pd.DataFrame]]]) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    for start_month, version, frames in frames_rows:
        audit = base._ai_usage_audit(frames.get("entry_candidates", pd.DataFrame())).copy()
        audit.insert(0, "requested_start_month", start_month)
        audit.insert(1, "version", version)
        rows.append(audit)
    return pd.concat(rows, ignore_index=True, sort=False) if rows else pd.DataFrame()


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


def _stats(pair_summary: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "stage": STAGE_LABEL,
                "model_tag": MODEL_TAG,
                "line_id": LINE_ID,
                "sample_count": int(len(pair_summary)),
                "start_min": str(pair_summary["requested_start_month"].min()),
                "start_max": str(pair_summary["requested_start_month"].max()),
                "c_positive_count": int(pair_summary["c_positive"].sum()),
                "return50_pass_count": int(pair_summary["passes_return50"].sum()),
                "drawdown_improved_count": int(pair_summary["drawdown_improved"].sum()),
                "min_return_retention_ratio": float(pd.to_numeric(pair_summary["return_retention_ratio"], errors="coerce").min()),
                "median_return_retention_ratio": float(pd.to_numeric(pair_summary["return_retention_ratio"], errors="coerce").median()),
                "min_c_return_pct": float(pd.to_numeric(pair_summary["c_total_return_pct"], errors="coerce").min()),
                "median_c_return_pct": float(pd.to_numeric(pair_summary["c_total_return_pct"], errors="coerce").median()),
                "max_c_return_pct": float(pd.to_numeric(pair_summary["c_total_return_pct"], errors="coerce").max()),
                "worst_c_drawdown_pct": float(pd.to_numeric(pair_summary["c_max_drawdown_pct"], errors="coerce").min()),
                "median_c_drawdown_pct": float(pd.to_numeric(pair_summary["c_max_drawdown_pct"], errors="coerce").median()),
                "min_drawdown_delta_pct": float(pd.to_numeric(pair_summary["drawdown_delta_pct"], errors="coerce").min()),
                "median_drawdown_delta_pct": float(pd.to_numeric(pair_summary["drawdown_delta_pct"], errors="coerce").median()),
                "median_sharpe_delta": float(pd.to_numeric(pair_summary["sharpe_delta"], errors="coerce").median()),
                "total_trade_reduction": float((pair_summary["a0_total_trade_count"] - pair_summary["c_total_trade_count"]).sum()),
                "total_slippage_reduction": float((pair_summary["a0_total_slippage"] - pair_summary["c_total_slippage"]).sum()),
            }
        ]
    )


def _decision(pair_summary: pd.DataFrame, stats: pd.DataFrame, ai_usage: pd.DataFrame, risk_audit: pd.DataFrame) -> dict[str, Any]:
    stat = stats.iloc[0].to_dict()
    sample_count = int(stat["sample_count"])
    decision = (
        "stage007_candidate_for_cost_sensitivity_and_independent_review"
        if int(stat["return50_pass_count"]) == sample_count
        and int(stat["drawdown_improved_count"]) >= max(1, sample_count - 2)
        and float(stat["min_return_retention_ratio"]) >= 0.50
        else "stage007_stop_or_attribution_before_more_runs"
    )
    return {
        "stage": STAGE_LABEL,
        "stage_id": STAGE_ID,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S CST"),
        "official_ai_path": str(OFFICIAL_LIVE_AI_ELIGIBILITY_PATH),
        "official_ai_sha16": _sha16(OFFICIAL_LIVE_AI_ELIGIBILITY_PATH),
        "a0_eligibility_sha16": _sha16(A0_ELIGIBILITY_PATH),
        "candidate_eligibility_sha16": _sha16(C_ELIGIBILITY_PATH),
        "bottom_veto_quantile": BOTTOM_VETO_QUANTILE,
        "min_active_products_for_veto": MIN_ACTIVE_PRODUCTS_FOR_VETO,
        "stats": stat,
        "pair_summary_preview": pair_summary.to_dict(orient="records"),
        "ai_usage_summary_rows": ai_usage[ai_usage["ai_product_pool_signal_date"].astype(str).eq("__summary__")].to_dict(orient="records"),
        "risk_restore_audit_rows": risk_audit.to_dict(orient="records"),
        "decision": decision,
        "overfit_before": "low_to_medium: no new threshold; extends Stage006 across fixed half-year starts.",
        "overfit_after": "pending_independent_review",
        "continue_value_before": "yes: multiperiod validation is required before any promotion discussion.",
        "continue_value_after": "pending_independent_review",
    }


def _plot(curves: pd.DataFrame) -> None:
    if curves.empty:
        return
    fig, axes = base.plt.subplots(2, 1, figsize=(14, 9), sharex=True)
    colors = {A0_VERSION: "#111827", CANDIDATE_VERSION: "#059669"}
    styles = {A0_VERSION: "--", CANDIDATE_VERSION: "-"}
    for (start_month, version), group in curves.groupby(["requested_start_month", "version"], sort=True):
        data = group.sort_values("date")
        x = pd.to_datetime(data["date"])
        equity = pd.to_numeric(data["account_equity_for_metrics"], errors="coerce").ffill()
        label = f"{start_month} {'A0' if version == A0_VERSION else 'C'}"
        alpha = 0.45 if version == A0_VERSION else 0.78
        axes[0].plot(x, equity, label=label, color=colors.get(version), linestyle=styles.get(version, "-"), linewidth=0.9, alpha=alpha)
        axes[1].plot(x, base._drawdown_pct(equity), label=label, color=colors.get(version), linestyle=styles.get(version, "-"), linewidth=0.8, alpha=alpha)
    axes[0].axhline(base.CAPITAL, color="#64748b", linestyle=":", linewidth=0.9)
    axes[0].set_title("Stage007 half-year paired current-AI equity")
    axes[0].set_ylabel("account equity")
    axes[0].grid(alpha=0.25)
    axes[1].axhline(-40.0, color="#111827", linestyle=":", linewidth=0.9)
    axes[1].set_title("Stage007 half-year paired current-AI drawdown")
    axes[1].set_ylabel("drawdown %")
    axes[1].grid(alpha=0.25)
    handles, labels = axes[0].get_legend_handles_labels()
    if len(handles) <= 30:
        axes[0].legend(loc="best", fontsize=7, ncol=2)
    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=170)
    base.plt.close(fig)


def _write_report(summary: pd.DataFrame, pair_summary: pd.DataFrame, stats: pd.DataFrame, decision: dict[str, Any]) -> None:
    lines = [
        "# Stage007 当前官方 AI 同口径 bottom25 veto 逐半年验证",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        f"- line_id：`{LINE_ID}`",
        "- 阶段性质：Stage006 扩展逐半年起点；不改官方实盘、CTP、邮件或 launchd。",
        "- 外部调研判断：多周期/多起点评估是避免单点样本误判的最低要求；本阶段不新增参数。",
        "- 运行前过拟合判断：低到中等。没有新增阈值，只扩展固定起点。",
        "- 运行前继续价值判断：有。Stage006 已通过独立审计，需要验证路径稳健性。",
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
        "# Stage007 当前官方 AI 同口径 bottom25 veto 逐半年验证",
        "",
        f"- line_id：`{LINE_ID}`",
        "- 当前模式：`day`",
        f"- 记录时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        "- 阶段性质：Stage006 通过独立审计后的逐半年 A0/C 真实引擎验证",
        "- 是否重要突破：待独立 review",
        "- 是否触发A/B：是，A0=当前官方 AI 无 veto；C=当前官方 AI + full-market bottom25 veto",
        "",
        "## 本次变更",
        "",
        f"- 新增脚本：`research/lines/{LINE_ID}/tools/stage007_current_ai_paired_bottom_veto_halfyear_engine.py`",
        "- 新增参数：无；继承 Stage006/005 的 bottom25 veto。",
        "- 修改参数：起点从单一 `2020-01` 扩展为 `2020-01` 到 `2026-01` 逐半年，终点固定 `2026-06-30`。",
        "- 删除参数：无。",
        "",
        "## 回测参数",
        "",
        f"- 起点：`{stat['start_min']}` 到 `{stat['start_max']}`，共 `{int(stat['sample_count'])}` 个。",
        f"- 终点：`{REQUESTED_END.date()}`",
        f"- 账户规模：`{base.CAPITAL:,.0f}`",
        "- 成本/风险口径：沿用官方 C9 真实引擎原成本、风险和 OI restore。",
        f"- 输入 hash：official_ai `{decision['official_ai_sha16']}`，A0 `{decision['a0_eligibility_sha16']}`，C `{decision['candidate_eligibility_sha16']}`。",
        "",
        "## 结果",
        "",
        f"- 样本数：`{int(stat['sample_count'])}`",
        f"- C 正收益数：`{int(stat['c_positive_count'])}`",
        f"- 收益保留 >=50%：`{int(stat['return50_pass_count'])}/{int(stat['sample_count'])}`",
        f"- 回撤改善：`{int(stat['drawdown_improved_count'])}/{int(stat['sample_count'])}`",
        f"- 最小/中位收益保留：`{float(stat['min_return_retention_ratio']):.4f}` / `{float(stat['median_return_retention_ratio']):.4f}`",
        f"- C 最小/中位/最大收益：`{float(stat['min_c_return_pct']):.4f}%` / `{float(stat['median_c_return_pct']):.4f}%` / `{float(stat['max_c_return_pct']):.4f}%`",
        f"- C 最差/中位回撤：`{float(stat['worst_c_drawdown_pct']):.4f}%` / `{float(stat['median_c_drawdown_pct']):.4f}%`",
        f"- 回撤变化最小/中位：`{float(stat['min_drawdown_delta_pct']):.4f}` / `{float(stat['median_drawdown_delta_pct']):.4f}` 百分点",
        f"- 总交易减少：`{float(stat['total_trade_reduction']):.0f}`，总滑点减少：`{float(stat['total_slippage_reduction']):,.2f}`。",
        "",
        "## 输出文件",
        "",
        f"- report：`{REPORT_PATH}`",
        f"- summary：`{SUMMARY_PATH}`",
        f"- pair_summary：`{PAIR_SUMMARY_PATH}`",
        f"- stats：`{STATS_PATH}`",
        f"- curves：`{CURVES_PATH}`",
        f"- chart：`{CHART_PATH}`",
        "",
        "## 结论",
        "",
        f"- 本阶段结论：`{decision['decision']}`",
        "- 是否进入下一步：等待独立 agent review 后决定；若通过，下一步做成本敏感与弱窗口归因。",
        "",
        "## 过拟合反思",
        "",
        "- 运行前判断：低到中等。扩展样本，不新增参数。",
        "- 运行后判断：等待独立 review。",
        "",
        "## 继续价值反思",
        "",
        "- 运行前判断：有价值。多周期是必要门槛。",
        "- 运行后判断：等待独立 review。",
    ]
    STAGE_RECORD_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _append_back_log(pair_summary: pd.DataFrame, stats: pd.DataFrame, decision: dict[str, Any]) -> None:
    stat = stats.iloc[0].to_dict()
    text = (
        f"\n{datetime.now().strftime('%Y-%m-%d %H:%M CST')}：`{LINE_ID}` Stage007 完成当前官方 AI 同口径 bottom25 veto 逐半年 A0/C "
        f"真实引擎验证，决策 `{decision['decision']}`。新增脚本 `research/lines/{LINE_ID}/tools/stage007_current_ai_paired_bottom_veto_halfyear_engine.py`；"
        f"新增 summary `{SUMMARY_PATH}`，pair_summary `{PAIR_SUMMARY_PATH}`，stats `{STATS_PATH}`，report `{REPORT_PATH}`。"
        "新增参数：无；修改参数：起点扩展为逐半年，终点固定 `2026-06-30`；删除参数：无。"
        f"新增结果：样本 `{int(stat['sample_count'])}`，C 正收益 `{int(stat['c_positive_count'])}`，收益保留>=50% `{int(stat['return50_pass_count'])}/{int(stat['sample_count'])}`，"
        f"回撤改善 `{int(stat['drawdown_improved_count'])}/{int(stat['sample_count'])}`，最小/中位收益保留 `{float(stat['min_return_retention_ratio']):.4f}/{float(stat['median_return_retention_ratio']):.4f}`，"
        f"C 最小/中位/最大收益 `{float(stat['min_c_return_pct']):.4f}%/{float(stat['median_c_return_pct']):.4f}%/{float(stat['max_c_return_pct']):.4f}%`，"
        f"C 最差/中位回撤 `{float(stat['worst_c_drawdown_pct']):.4f}%/{float(stat['median_c_drawdown_pct']):.4f}%`，"
        f"回撤变化最小/中位 `{float(stat['min_drawdown_delta_pct']):.4f}/{float(stat['median_drawdown_delta_pct']):.4f}` 百分点。"
        "运行前过拟合反思：低到中等，扩样本不救参；运行后过拟合反思：待独立 agent review。"
        "运行前继续价值反思：有，多周期是必要门槛；运行后继续价值反思：待独立 agent review。\n"
    )
    with (base.ROOT / "back_log.md").open("a", encoding="utf-8") as fh:
        fh.write(text)


def _update_line(stats: pd.DataFrame, decision: dict[str, Any]) -> None:
    stat = stats.iloc[0].to_dict()
    addition = (
        "\n## Stage007\n\n"
        f"- 时间: `{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`\n"
        f"- 决策: `{decision['decision']}`\n"
        f"- 样本数: `{int(stat['sample_count'])}`，C 正收益 `{int(stat['c_positive_count'])}`，收益保留>=50% `{int(stat['return50_pass_count'])}/{int(stat['sample_count'])}`，回撤改善 `{int(stat['drawdown_improved_count'])}/{int(stat['sample_count'])}`。\n"
        f"- 最小/中位收益保留: `{float(stat['min_return_retention_ratio']):.4f}` / `{float(stat['median_return_retention_ratio']):.4f}`；C 最差回撤 `{float(stat['worst_c_drawdown_pct']):.4f}%`。\n"
        "- 状态: 已跑逐半年多周期真实引擎，等待独立 agent review 后再决定是否做成本敏感和弱窗口归因。\n"
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
    c_eligibility, eligibility_audit, overlay_audit = _build_candidate_eligibility_preserve_official(feature_panel)
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
        label="Stage007 A0 current official AI no veto",
    )
    c_profile = _profile(
        metadata,
        version=CANDIDATE_VERSION,
        strategy_name=STRATEGY_NAME_C,
        eligibility_path=C_ELIGIBILITY_PATH,
        label="Stage007 C current official AI plus full-market bottom25 veto",
    )

    curves: list[pd.DataFrame] = []
    frames_rows: list[tuple[str, str, dict[str, pd.DataFrame]]] = []
    for start in _start_dates():
        start_month = _start_month_text(start)
        print(f"running {start_month} A0", flush=True)
        a0_daily, a0_frames = _run_profile_for_start(metadata, a0_profile, A0_VERSION, start)
        print(f"running {start_month} C", flush=True)
        c_daily, c_frames = _run_profile_for_start(metadata, c_profile, CANDIDATE_VERSION, start)
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
        _summarize_curve(group)
        for _, group in curve_frame.groupby(["requested_start_month", "version"], sort=True)
    ])
    pair = _pair_summary(summary)
    stats = _stats(pair)
    ai_usage = _ai_usage_audit(frames_rows)
    risk_audit = _risk_restore_audit(frames_rows)
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
