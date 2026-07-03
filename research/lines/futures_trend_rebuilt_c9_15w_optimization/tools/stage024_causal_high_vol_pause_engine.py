from __future__ import annotations

from dataclasses import replace
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
TOOLS_DIR = Path(__file__).resolve().parent
PORTFOLIO_DIR = PROJECT_DIR / "examples" / "portfolio_backtesting"
for path in (str(TOOLS_DIR), str(PORTFOLIO_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

import analyze_qmt_roll_stage167_c9_live_15w_multiperiod_ai_audit as s167
import analyze_qmt_roll_stage847_stage830_c4_stop_retry_engine as s847
import analyze_qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow as s901
import stage006_current_quality_feature_binder as s006
import stage009_dense_start_goal_audit as s009
import stage013_account_state_pilot_gate_engine as s013
import stage018_regime_pilot_gate_engine as s018
from qmt_roll_official_live_config import (
    OFFICIAL_LIVE_ALIAS,
    OFFICIAL_LIVE_CAPITAL,
    OFFICIAL_LIVE_CAPITAL_LABEL,
    OFFICIAL_LIVE_VERSION,
)


LINE_ID = "futures_trend_rebuilt_c9_15w_optimization"
STAGE = "Stage024"
MODEL_TAG = "stage024_causal_high_vol_pause_engine_v1"
OUTPUT_PREFIX = "rebuilt_c9_stage024_causal_high_vol_pause_engine"
PROFILE_NAME = "stage024_causal_high_vol_pause_engine"

TARGET_REGIMES = ("high_vol_high_eff",)
REQUESTED_END = pd.Timestamp("2026-06-30")
CAPITAL = 150000.0

LINE_DIR = PROJECT_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage024_causal_high_vol_pause_engine"
STAGE_RECORD_DIR = LINE_DIR / "stages"

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
CURVES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv"
ENTRY_CANDIDATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_candidates_{MODEL_TAG}.csv"
TRADES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trades_{MODEL_TAG}.csv"
ENTRY_RISK_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_risk_{MODEL_TAG}.csv"
TRADE_EVENTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trade_events_{MODEL_TAG}.csv"
PAUSE_EVENTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_pause_events_{MODEL_TAG}.csv"
REGIME_TABLE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_causal_regime_table_{MODEL_TAG}.csv"
GOAL_AGGREGATE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_goal_aggregate_{MODEL_TAG}.csv"
GOAL_TO_FINAL_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_goal_to_final_windows_{MODEL_TAG}.csv"
GOAL_FIXED_HORIZON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_goal_fixed_horizon_windows_{MODEL_TAG}.csv"
GOAL_WORST_WINDOWS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_goal_worst_windows_{MODEL_TAG}.csv"
RETENTION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_retention_{MODEL_TAG}.csv"
PERFORMANCE_CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_performance_chart_{MODEL_TAG}.png"
GOAL_AUDIT_CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_goal_audit_chart_{MODEL_TAG}.png"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


def _json_safe(value: Any) -> Any:
    return s006._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s006._md_table(frame, max_rows=max_rows)


def _date_text(value: Any) -> str:
    return pd.Timestamp(value).date().isoformat()


def _start_month_text(value: Any) -> str:
    return pd.Timestamp(value).strftime("%Y-%m")


def _stage024_apply_regime_pause_gate(
    *,
    sizing: dict[str, Any],
    entry_context: str,
    regime_info: dict[str, Any] | None,
    enabled: bool,
    target_regimes: tuple[str, ...] = TARGET_REGIMES,
) -> tuple[int, dict[str, Any]]:
    selected_before = max(0, int(sizing.get("selected_volume") or 0))
    info = dict(regime_info or {})
    regime = str(info.get("stage018_joint_regime") or "missing")
    target_set = {str(item) for item in target_regimes}
    selected_after = selected_before
    applied = 0

    if not enabled:
        reason = "disabled"
    elif selected_before <= 0:
        reason = "zero_selected_volume"
    elif str(entry_context or "") != "flat_entry":
        reason = "non_flat_entry_context"
    elif regime not in target_set:
        reason = "regime_not_target"
    else:
        selected_after = 0
        applied = int(selected_after != selected_before)
        reason = "stage024_causal_high_vol_pause_flat_entry" if applied else "already_zero"

    fields = {
        "stage024_pause_gate_enabled": int(bool(enabled)),
        "stage024_pause_gate_applied": applied,
        "stage024_pause_gate_reason": reason,
        "stage024_pause_gate_target_regimes": ",".join(sorted(target_set)),
        "stage024_pause_gate_joint_regime": regime,
        "stage024_pause_gate_source_date": str(info.get("stage018_regime_source_date") or ""),
        "stage024_pause_gate_vol60_bucket": str(info.get("stage018_vol60_bucket") or "missing"),
        "stage024_pause_gate_eff60_bucket": str(info.get("stage018_eff60_bucket") or "missing"),
        "stage024_pause_gate_selected_volume_before": selected_before,
        "stage024_pause_gate_selected_volume_after": selected_after,
        "stage024_pause_gate_reduced_volume": selected_before - selected_after,
    }
    return selected_after, fields


class QmtRollPortfolioStrategyStage024CausalHighVolPause(s013.QmtRollPortfolioStrategyStage013AccountStatePilotGate):
    enable_stage024_regime_pause_gate: bool = False
    stage024_pause_target_regimes: str = ",".join(TARGET_REGIMES)
    stage024_market_daily_path: str = str(s018.MARKET_DAILY_PATH)

    parameters = s013.QmtRollPortfolioStrategyStage013AccountStatePilotGate.parameters + [
        "enable_stage024_regime_pause_gate",
        "stage024_pause_target_regimes",
        "stage024_market_daily_path",
    ]
    variables = s013.QmtRollPortfolioStrategyStage013AccountStatePilotGate.variables + [
        "stage024_pause_gate_count",
        "stage024_pause_gate_reduced_volume",
    ]

    def __init__(self, strategy_engine: Any, strategy_name: str, vt_symbols: list[str], setting: dict[str, Any]) -> None:
        super().__init__(strategy_engine, strategy_name, vt_symbols, setting)
        self.stage024_pause_gate_events: list[dict[str, Any]] = []
        self.stage024_pause_gate_count: int = 0
        self.stage024_pause_gate_reduced_volume: int = 0
        self.stage024_regime_by_date = s018._stage018_load_regime_map(
            str(getattr(self, "stage024_market_daily_path", str(s018.MARKET_DAILY_PATH)) or s018.MARKET_DAILY_PATH)
        )

    def _target_regimes(self) -> tuple[str, ...]:
        values = [item.strip() for item in str(self.stage024_pause_target_regimes or "").split(",")]
        return tuple(item for item in values if item)

    def _plan_flat_entry_candidates(self, day_contexts: list[Any]) -> dict[str, dict[str, Any]]:
        plans = super()._plan_flat_entry_candidates(day_contexts)
        if not self.enable_stage024_regime_pause_gate:
            return plans

        for product_vt_symbol, plan in plans.items():
            if str(plan.get("candidate_status") or "") != "opened":
                continue
            bar = plan.get("target_bar")
            bar_datetime = getattr(bar, "datetime", None)
            date_key = pd.Timestamp(bar_datetime).date().isoformat() if bar_datetime is not None else ""
            sizing = dict(plan.get("sizing") or {})
            selected_after, fields = _stage024_apply_regime_pause_gate(
                sizing=sizing,
                entry_context="flat_entry",
                regime_info=self.stage024_regime_by_date.get(date_key),
                enabled=bool(self.enable_stage024_regime_pause_gate),
                target_regimes=self._target_regimes(),
            )
            sizing.update(fields)
            plan["sizing"] = sizing
            if int(fields["stage024_pause_gate_applied"]) != 1:
                continue

            sizing["selected_volume"] = selected_after
            plan["volume"] = selected_after
            plan["candidate_status"] = "skipped"
            plan["skip_reason"] = "stage024_causal_high_vol_pause"

            event = self._stage024_event_from_plan(str(product_vt_symbol), plan, fields)
            self.stage024_pause_gate_events.append(event)
            self.trade_event_diagnostics.append(event)
            self.stage024_pause_gate_count += 1
            self.stage024_pause_gate_reduced_volume += int(fields["stage024_pause_gate_reduced_volume"])
        return plans

    def _stage024_event_from_plan(
        self,
        product_vt_symbol: str,
        plan: dict[str, Any],
        fields: dict[str, Any],
    ) -> dict[str, Any]:
        bar = plan.get("target_bar")
        bar_datetime = getattr(bar, "datetime", None)
        close_price = float(getattr(bar, "close_price", 0.0) or 0.0)
        direction = str(plan.get("direction") or "")
        return {
            "datetime": bar_datetime,
            "date": pd.Timestamp(bar_datetime).date() if bar_datetime is not None else "",
            "vt_symbol": str(plan.get("target_contract") or ""),
            "contract_vt_symbol": str(plan.get("target_contract") or ""),
            "product_vt_symbol": product_vt_symbol,
            "position_direction": direction,
            "direction": direction,
            "offset": "Sizing",
            "reason": "stage024_regime_pause_gate",
            "volume": int(fields["stage024_pause_gate_selected_volume_after"]),
            "price": close_price,
            "entry_context": "flat_entry",
            "signal": str(plan.get("signal") or ""),
            "candidate_status_after": str(plan.get("candidate_status") or ""),
            "skip_reason_after": str(plan.get("skip_reason") or ""),
            **fields,
        }


def _stage024_profile(metadata: dict[str, Any]) -> dict[str, Any]:
    profile = s013._stage013_profile(metadata)
    spec = profile["spec"]
    capital = replace(
        spec.capital,
        variant=PROFILE_NAME,
        label=f"{OFFICIAL_LIVE_CAPITAL_LABEL} {OFFICIAL_LIVE_ALIAS} Stage024 causal high-vol pause",
        account_capital=OFFICIAL_LIVE_CAPITAL,
        c3_capital=OFFICIAL_LIVE_CAPITAL,
        note=(
            f"{spec.capital.note} | Stage024 isolated research candidate. "
            "When the prior-day causal regime is high-vol/high-efficiency, flat entries are paused to zero; "
            "existing positions are not force-closed and official live config is not mutated."
        ),
    )
    overrides = {
        **spec.overrides,
        "enable_stage024_regime_pause_gate": True,
        "stage024_pause_target_regimes": ",".join(TARGET_REGIMES),
        "stage024_market_daily_path": str(s018.MARKET_DAILY_PATH),
    }
    result = dict(profile)
    result["profile"] = PROFILE_NAME
    result["strategy_cls"] = QmtRollPortfolioStrategyStage024CausalHighVolPause
    result["spec"] = replace(spec, capital=capital, overrides=overrides, profile=PROFILE_NAME)
    return result


def _run_live_stage024(
    metadata: dict[str, Any],
    analysis_start: pd.Timestamp,
    analysis_end: pd.Timestamp,
) -> tuple[pd.DataFrame, dict[str, pd.DataFrame], Any]:
    original_start = s847.START
    original_end = s847.END
    original_minute_by_symbol = s847.s827._GLOBAL_MINUTE_BY_SYMBOL
    s901._ensure_c9_minute_bars(metadata)
    try:
        s847.START = analysis_start.normalize()
        s847.END = analysis_end.normalize()
        profile = _stage024_profile(metadata)
        combined, frames = s013._run_profile(profile, metadata)
        spec = profile["spec"]
    finally:
        s847.START = original_start
        s847.END = original_end
        s847.s827._GLOBAL_MINUTE_BY_SYMBOL = original_minute_by_symbol

    combined["account_capital"] = spec.capital.account_capital
    combined["c3_capital"] = spec.capital.c3_capital
    combined["profile"] = spec.profile
    for frame in frames.values():
        if frame.empty:
            continue
        frame["account_capital"] = spec.capital.account_capital
        frame["c3_capital"] = spec.capital.c3_capital
        frame["profile"] = spec.profile
    return combined, frames, spec


def _frame_with_run_columns(frame: pd.DataFrame, start: pd.Timestamp) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    result = frame.copy()
    result["stage"] = STAGE
    result["model_tag"] = MODEL_TAG
    result["line_id"] = LINE_ID
    result["official_live_version"] = OFFICIAL_LIVE_VERSION
    result["official_live_alias"] = OFFICIAL_LIVE_ALIAS
    result["requested_start"] = _date_text(start)
    result["requested_start_month"] = _start_month_text(start)
    result["requested_end"] = _date_text(REQUESTED_END)
    return result


def _append_frame(target: list[pd.DataFrame], frame: pd.DataFrame, start: pd.Timestamp) -> None:
    frame = _frame_with_run_columns(frame, start)
    if not frame.empty:
        target.append(frame)


def _summarize_curve(curve: pd.DataFrame, requested_start: pd.Timestamp) -> dict[str, Any]:
    row = s167._summarize_curve(curve, requested_start)
    row.update(
        {
            "stage": STAGE,
            "model_tag": MODEL_TAG,
            "line_id": LINE_ID,
            "official_live_profile_name": PROFILE_NAME,
            "requested_end": REQUESTED_END.date().isoformat(),
        }
    )
    return row


def _run_multistart() -> dict[str, pd.DataFrame]:
    metadata = s901.s513._metadata()
    starts = s167._build_start_dates()
    summary_rows: list[dict[str, Any]] = []
    curve_frames: list[pd.DataFrame] = []
    candidate_frames: list[pd.DataFrame] = []
    trade_frames: list[pd.DataFrame] = []
    entry_risk_frames: list[pd.DataFrame] = []
    trade_event_frames: list[pd.DataFrame] = []

    for idx, start in enumerate(starts, start=1):
        print(f"[stage024] running {idx}/{len(starts)} start={_date_text(start)}", flush=True)
        combined, frames, _spec = _run_live_stage024(metadata, start, REQUESTED_END)

        curve = combined.copy()
        curve["stage"] = STAGE
        curve["model_tag"] = MODEL_TAG
        curve["line_id"] = LINE_ID
        curve["official_live_version"] = OFFICIAL_LIVE_VERSION
        curve["official_live_alias"] = OFFICIAL_LIVE_ALIAS
        curve["requested_start"] = _date_text(start)
        curve["requested_start_month"] = _start_month_text(start)
        curve["requested_end"] = _date_text(REQUESTED_END)
        curve["date"] = pd.to_datetime(curve["date"], errors="coerce").dt.normalize()
        curve = curve.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
        curve["nav"] = pd.to_numeric(curve["account_equity"], errors="coerce") / CAPITAL
        curve["absolute_equity"] = pd.to_numeric(curve["account_equity"], errors="coerce")
        curve["drawdown_pct"] = s167._drawdown_pct(pd.to_numeric(curve["account_equity"], errors="coerce"))
        curve["days_since_start"] = np.arange(len(curve), dtype=int)
        curve_frames.append(curve)
        summary_rows.append(_summarize_curve(curve, start))

        _append_frame(candidate_frames, frames.get("entry_candidates", pd.DataFrame()), start)
        _append_frame(trade_frames, frames.get("trades", pd.DataFrame()), start)
        _append_frame(entry_risk_frames, frames.get("entry_risk", pd.DataFrame()), start)
        _append_frame(trade_event_frames, frames.get("trade_events", pd.DataFrame()), start)

    trade_events = pd.concat(trade_event_frames, ignore_index=True, sort=False) if trade_event_frames else pd.DataFrame()
    pause_events = (
        trade_events[trade_events["reason"].astype(str).eq("stage024_regime_pause_gate")].copy()
        if not trade_events.empty and "reason" in trade_events.columns
        else pd.DataFrame()
    )
    return {
        "summary": pd.DataFrame(summary_rows).sort_values("requested_start").reset_index(drop=True),
        "curves": pd.concat(curve_frames, ignore_index=True, sort=False) if curve_frames else pd.DataFrame(),
        "entry_candidates": pd.concat(candidate_frames, ignore_index=True, sort=False) if candidate_frames else pd.DataFrame(),
        "trades": pd.concat(trade_frames, ignore_index=True, sort=False) if trade_frames else pd.DataFrame(),
        "entry_risk": pd.concat(entry_risk_frames, ignore_index=True, sort=False) if entry_risk_frames else pd.DataFrame(),
        "trade_events": trade_events,
        "pause_events": pause_events,
    }


def _retention_summary(candidate_summary: pd.DataFrame) -> pd.DataFrame:
    base = pd.read_csv(s006.SUMMARY_PATH, encoding="utf-8-sig")
    cols = ["requested_start_month", "total_return_pct", "end_equity", "max_dd_pct", "sharpe"]
    merged = base[cols].merge(
        candidate_summary[cols],
        on="requested_start_month",
        how="inner",
        suffixes=("_base_stage006", "_stage024"),
    )
    merged["stage024_vs_base_return_ratio"] = (
        pd.to_numeric(merged["total_return_pct_stage024"], errors="coerce")
        / pd.to_numeric(merged["total_return_pct_base_stage006"], errors="coerce").replace(0.0, np.nan)
    )
    merged["passes_80pct_retention"] = (
        pd.to_numeric(merged["total_return_pct_stage024"], errors="coerce")
        >= pd.to_numeric(merged["total_return_pct_base_stage006"], errors="coerce") * 0.8
    ).astype("int64")
    return merged


def _goal_audit(curves: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    audit_curves = curves[["requested_start_month", "date", "account_equity"]].copy()
    audit_curves.rename(columns={"account_equity": "equity"}, inplace=True)
    audit_curves["variant"] = "stage024_engine"
    audit_curves["date"] = pd.to_datetime(audit_curves["date"], errors="coerce").dt.normalize()
    audit_curves["equity"] = pd.to_numeric(audit_curves["equity"], errors="coerce")
    audit_curves = audit_curves.dropna(subset=["date", "equity"])
    return s009._run_audit(audit_curves)


def _plot_performance(curves: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 1, figsize=(18, 11), sharex=True, constrained_layout=True)
    for start, group in curves.groupby("requested_start_month"):
        group = group.sort_values("date")
        axes[0].plot(group["date"], group["account_equity"], linewidth=0.9, alpha=0.74, label=str(start))
        axes[1].plot(group["date"], group["drawdown_pct"], linewidth=0.9, alpha=0.74, label=str(start))
    axes[0].axhline(CAPITAL, color="#111827", linestyle="--", linewidth=0.9, label="initial 150k")
    axes[0].set_title("Stage024 Absolute Account Equity By Cold Start")
    axes[0].set_ylabel("account equity")
    axes[1].set_title("Stage024 Drawdown By Cold Start")
    axes[1].set_ylabel("drawdown %")
    axes[1].set_xlabel("date")
    for ax in axes:
        ax.grid(True, alpha=0.25)
        ax.legend(fontsize=7, ncol=3, loc="best")
    fig.savefig(PERFORMANCE_CHART_PATH, dpi=160)
    plt.close(fig)


def _plot_goal_audit(aggregate: pd.DataFrame, worst: pd.DataFrame, fixed: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(18, 10), constrained_layout=True)
    all_scope = aggregate[aggregate["audit_scope"].eq("all_trading_end_dates_gt_1y")].copy()
    final_scope = aggregate[aggregate["audit_scope"].eq("start_to_2026_06_30_only")].copy()
    for ax, frame, title in [
        (axes[0, 0], all_scope, "Negative Rate: All Trading End Dates > 1Y"),
        (axes[0, 1], final_scope, "Negative Rate: Start To 2026-06-30"),
    ]:
        labels = frame["source_start_month"].astype(str).tolist()
        x = np.arange(len(frame))
        ax.bar(x, frame["negative_rate_pct"], color="#2563eb")
        ax.set_xticks(x[::2])
        ax.set_xticklabels(labels[::2], rotation=45, ha="right", fontsize=8)
        ax.set_title(title)
        ax.set_ylabel("negative rate %")
        ax.grid(True, axis="y", alpha=0.25)

    ax = axes[1, 0]
    if not worst.empty:
        plot = worst.head(120).copy()
        ax.scatter(np.arange(len(plot)), plot["return_pct"], s=12, color="#dc2626")
    ax.axhline(0, color="#111827", linewidth=0.9, linestyle="--")
    ax.set_title("Worst Negative Windows")
    ax.set_ylabel("return %")
    ax.grid(True, axis="y", alpha=0.25)

    ax = axes[1, 1]
    if not fixed.empty:
        fixed_summary = (
            fixed.groupby("horizon_days", as_index=False)
            .agg(negative_rate_pct=("positive_return", lambda s: float((1.0 - s.mean()) * 100.0)))
            .sort_values("horizon_days")
        )
        ax.plot(fixed_summary["horizon_days"], fixed_summary["negative_rate_pct"], marker="o", color="#16a34a")
    ax.set_title("Fixed Horizon Negative Rate")
    ax.set_xlabel("calendar days")
    ax.set_ylabel("negative rate %")
    ax.grid(True, axis="y", alpha=0.25)
    fig.savefig(GOAL_AUDIT_CHART_PATH, dpi=160)
    plt.close(fig)


def _metrics(
    summary: pd.DataFrame,
    aggregate: pd.DataFrame,
    retention: pd.DataFrame,
    pause_events: pd.DataFrame,
) -> dict[str, Any]:
    all_scope = aggregate[aggregate["audit_scope"].eq("all_trading_end_dates_gt_1y")]
    final_scope = aggregate[aggregate["audit_scope"].eq("start_to_2026_06_30_only")]
    total_negative = int(pd.to_numeric(all_scope["negative_count"], errors="coerce").fillna(0).sum())
    min_strict = float(pd.to_numeric(all_scope["min_return_pct"], errors="coerce").min())
    final_negative = int(pd.to_numeric(final_scope["negative_count"], errors="coerce").fillna(0).sum())
    final_min = float(pd.to_numeric(final_scope["min_return_pct"], errors="coerce").min())
    retention_pass = int(pd.to_numeric(retention["passes_80pct_retention"], errors="coerce").fillna(0).sum())
    pause_count = int(len(pause_events))
    pause_reduced_volume = (
        int(pd.to_numeric(pause_events.get("stage024_pause_gate_reduced_volume", pd.Series(dtype=float)), errors="coerce").fillna(0).sum())
        if not pause_events.empty
        else 0
    )
    return {
        "sample_count": int(summary["requested_start_month"].nunique()),
        "positive_start_count": int(pd.to_numeric(summary["total_return_pct"], errors="coerce").gt(0).sum()),
        "min_total_return_pct": float(pd.to_numeric(summary["total_return_pct"], errors="coerce").min()),
        "median_total_return_pct": float(pd.to_numeric(summary["total_return_pct"], errors="coerce").median()),
        "max_total_return_pct": float(pd.to_numeric(summary["total_return_pct"], errors="coerce").max()),
        "worst_max_dd_pct": float(pd.to_numeric(summary["max_dd_pct"], errors="coerce").min()),
        "median_max_dd_pct": float(pd.to_numeric(summary["max_dd_pct"], errors="coerce").median()),
        "min_sharpe": float(pd.to_numeric(summary["sharpe"], errors="coerce").min()),
        "median_sharpe": float(pd.to_numeric(summary["sharpe"], errors="coerce").median()),
        "strict_negative_window_count": total_negative,
        "strict_min_return_pct": min_strict,
        "to_final_negative_window_count": final_negative,
        "to_final_min_return_pct": final_min,
        "retention_pass_count": retention_pass,
        "retention_rows": int(len(retention)),
        "pause_event_count": pause_count,
        "pause_reduced_volume": pause_reduced_volume,
    }


def _write_report(
    decision: dict[str, Any],
    summary: pd.DataFrame,
    aggregate: pd.DataFrame,
    retention: pd.DataFrame,
    pause_events: pd.DataFrame,
) -> None:
    report = f"""# Stage024 因果高波动 regime 暂停新开仓真实引擎候选

- 生成时间：`{decision['generated_at']}`
- line_id：`{LINE_ID}`
- model_tag：`{MODEL_TAG}`
- 决策：`{decision['decision']}`
- 阶段性质：独立研究 profile 真实引擎回测；不改 C9 官方线上配置，不连接 CTP，不调用下单。

## 外部调研判断

- 资料支持 volatility/regime filter 可降低部分极端回撤，但也会增加空仓并错过趋势右尾。
- Stage023 的最高 lift regime 来自只读统计，Stage024 只使用 Stage018 已实现的因果 expanding quantile regime 表。

## 固定规则

- 只在前一交易日因果 regime 为 `{','.join(TARGET_REGIMES)}` 时暂停新的 `flat_entry`。
- 不强平已有仓位，不影响非 flat-entry，不按品种、方向、日期或 source 定制。

## 核心结果

- 正收益起点：`{decision['positive_start_count']}/{decision['sample_count']}`
- 期末收益 最小/中位/最大：`{decision['min_total_return_pct']:.4f}% / {decision['median_total_return_pct']:.4f}% / {decision['max_total_return_pct']:.4f}%`
- 最差最大回撤：`{decision['worst_max_dd_pct']:.4f}%`
- 严格任意结束日 `>1` 年负窗口：`{decision['strict_negative_window_count']}`
- 严格最差收益：`{decision['strict_min_return_pct']:.4f}%`
- 到 `2026-06-30` 负窗口：`{decision['to_final_negative_window_count']}`；最差 `{decision['to_final_min_return_pct']:.4f}%`
- 80% 收益保留：`{decision['retention_pass_count']}/{decision['retention_rows']}`
- 暂停事件：`{decision['pause_event_count']}`；减少手数：`{decision['pause_reduced_volume']}`

## 多起点摘要

{_md_table(summary)}

## 目标审计摘要

{_md_table(aggregate.head(40))}

## 收益保留

{_md_table(retention)}

## 暂停事件样本

{_md_table(pause_events.head(30))}

## 判断

- 决策：`{decision['decision']}`。
- 过拟合反思：{decision['overfit_reflection_after']}
- 继续价值反思：{decision['continue_value_after']}

## 输出文件

- summary: `{SUMMARY_PATH}`
- curves: `{CURVES_PATH}`
- pause_events: `{PAUSE_EVENTS_PATH}`
- causal_regime_table: `{REGIME_TABLE_PATH}`
- goal_aggregate: `{GOAL_AGGREGATE_PATH}`
- retention: `{RETENTION_PATH}`
- performance_chart: `{PERFORMANCE_CHART_PATH}`
- goal_audit_chart: `{GOAL_AUDIT_CHART_PATH}`
- decision: `{DECISION_PATH}`
- report: `{REPORT_PATH}`
"""
    REPORT_PATH.write_text(report, encoding="utf-8")


def _write_stage_record(decision: dict[str, Any]) -> Path:
    record_path = STAGE_RECORD_DIR / f"{datetime.now().strftime('%Y%m%d_%H%M')}_stage024_causal_high_vol_pause_engine.md"
    content = f"""# Stage024 - 因果高波动 regime 暂停新开仓真实引擎候选

## 变更时间

- {decision['generated_at']} CST

## 是否重要突破版本

- 否。独立研究 profile，未改官方线上 C9/15w。

## 本次版本改动内容

- 新增工具：`research/lines/{LINE_ID}/tools/stage024_causal_high_vol_pause_engine.py`
- 新增独立策略类：`QmtRollPortfolioStrategyStage024CausalHighVolPause`
- 只在前一交易日因果 regime 为 `{','.join(TARGET_REGIMES)}` 时暂停新的 `flat_entry`，不强平已有仓位。

## 新增参数

- `enable_stage024_regime_pause_gate=True`
- `stage024_pause_target_regimes={','.join(TARGET_REGIMES)}`

## 修改参数

- 无。官方线上配置未改。

## 删除参数

- 无。

## 新增回测结果

- 正收益起点：`{decision['positive_start_count']}/{decision['sample_count']}`
- 期末收益最小/中位/最大：`{decision['min_total_return_pct']:.4f}% / {decision['median_total_return_pct']:.4f}% / {decision['max_total_return_pct']:.4f}%`
- 最大回撤最差：`{decision['worst_max_dd_pct']:.4f}%`
- Sharpe 最小/中位：`{decision['min_sharpe']:.4f} / {decision['median_sharpe']:.4f}`
- 严格任意结束日 `>1` 年负窗口：`{decision['strict_negative_window_count']}`
- 严格最差收益：`{decision['strict_min_return_pct']:.4f}%`
- 到 `2026-06-30` 负窗口：`{decision['to_final_negative_window_count']}`
- 80% 收益保留：`{decision['retention_pass_count']}/{decision['retention_rows']}`
- 暂停事件：`{decision['pause_event_count']}`
- 减少手数：`{decision['pause_reduced_volume']}`

## 修改回测结果

- 无。

## 删除回测结果

- 无。

## 交易成本指标

- 总滑点、总交易次数、胜率见 summary 输出；本阶段不新增成本模型。

## 调研与判断结论

- 调研结论：regime filter 有理论依据，但容易错杀趋势右尾；必须以收益保留为硬门。
- 判断结论：`{decision['decision']}`。

## 过拟合与继续价值反思

- 运行前是否过拟合：否。规则只来自 Stage023 的候选前兆并做因果化，不按品种/日期/source 调整。
- 运行前是否有价值继续：有。该阶段验证坏环境前兆是否能真实改变 holding PnL 路径。
- 运行后是否过拟合：{decision['overfit_reflection_after']}
- 运行后是否有价值继续：{decision['continue_value_after']}

## 后续规划和 TODO

- 若收益保留失败或负窗口未清零，不晋级，不继续扫同类 regime 阈值。
- 若有局部改善，下一步只能做更强因果稳定性和右尾错杀归因。

## 输出文件

- `{REPORT_PATH}`
- `{DECISION_PATH}`
- `{PERFORMANCE_CHART_PATH}`
- `{GOAL_AUDIT_CHART_PATH}`
"""
    record_path.write_text(content, encoding="utf-8")
    return record_path


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    STAGE_RECORD_DIR.mkdir(parents=True, exist_ok=True)

    frames = _run_multistart()
    summary = frames["summary"]
    curves = frames["curves"]
    pause_events = frames["pause_events"]
    aggregate, to_final, fixed, worst = _goal_audit(curves)
    retention = _retention_summary(summary)
    regime_table = s018._stage018_build_causal_regime_table()
    _plot_performance(curves)
    _plot_goal_audit(aggregate, worst, fixed)

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    curves.to_csv(CURVES_PATH, index=False, encoding="utf-8-sig")
    frames["entry_candidates"].to_csv(ENTRY_CANDIDATES_PATH, index=False, encoding="utf-8-sig")
    frames["trades"].to_csv(TRADES_PATH, index=False, encoding="utf-8-sig")
    frames["entry_risk"].to_csv(ENTRY_RISK_PATH, index=False, encoding="utf-8-sig")
    frames["trade_events"].to_csv(TRADE_EVENTS_PATH, index=False, encoding="utf-8-sig")
    pause_events.to_csv(PAUSE_EVENTS_PATH, index=False, encoding="utf-8-sig")
    regime_table.to_csv(REGIME_TABLE_PATH, index=False, encoding="utf-8-sig")
    aggregate.to_csv(GOAL_AGGREGATE_PATH, index=False, encoding="utf-8-sig")
    to_final.to_csv(GOAL_TO_FINAL_PATH, index=False, encoding="utf-8-sig")
    fixed.to_csv(GOAL_FIXED_HORIZON_PATH, index=False, encoding="utf-8-sig")
    worst.to_csv(GOAL_WORST_WINDOWS_PATH, index=False, encoding="utf-8-sig")
    retention.to_csv(RETENTION_PATH, index=False, encoding="utf-8-sig")

    metrics = _metrics(summary, aggregate, retention, pause_events)
    decision = {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().replace(microsecond=0).isoformat(),
        "audit_type": "causal_high_vol_high_eff_flat_entry_pause_true_engine",
        "decision": (
            "stage024_goal_pass_needs_review"
            if metrics["strict_negative_window_count"] == 0 and metrics["retention_pass_count"] == metrics["retention_rows"]
            else "stage024_not_promoted"
        ),
        "target_regimes": list(TARGET_REGIMES),
        "strategy_changed": True,
        "official_live_config_changed": False,
        "true_engine": True,
        "order_api_called": False,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "ctp_connected": False,
        **metrics,
        "external_research_judgment": (
            "Regime filters can reduce drawdown but often miss trend right tails. Stage024 tests a single causal "
            "high-vol/high-efficiency pause and keeps 80% return retention as a hard gate."
        ),
        "overfit_reflection_before": "否。规则没有按品种/方向/日期/source 定制，并且使用前一日因果 regime。",
        "continue_value_before": "有。只有真实引擎才能验证暂停新开仓是否改变 holding PnL 路径。",
        "overfit_reflection_after": "待运行结果解释；若收益保留失败，不继续扫同类 regime 阈值。",
        "continue_value_after": "待运行结果解释。",
        "outputs": {
            "summary": str(SUMMARY_PATH),
            "curves": str(CURVES_PATH),
            "pause_events": str(PAUSE_EVENTS_PATH),
            "causal_regime_table": str(REGIME_TABLE_PATH),
            "goal_aggregate": str(GOAL_AGGREGATE_PATH),
            "retention": str(RETENTION_PATH),
            "performance_chart": str(PERFORMANCE_CHART_PATH),
            "goal_audit_chart": str(GOAL_AUDIT_CHART_PATH),
            "decision": str(DECISION_PATH),
            "report": str(REPORT_PATH),
        },
    }

    if decision["decision"] == "stage024_goal_pass_needs_review":
        decision["overfit_reflection_after"] = "否，但仍需独立复核；这是低自由度因果规则，不是参数网格最优。"
        decision["continue_value_after"] = "有。需要做复核、成本敏感和实盘前 SOP，不可直接上线。"
    else:
        decision["overfit_reflection_after"] = "否。本阶段没有用结果反调阈值；若继续在同类 regime 上扫参会过拟合。"
        decision["continue_value_after"] = "有限。若失败，下一步应转向新的外生信息源或重新审计右尾错杀，而不是继续调 regime 分位。"

    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(decision, summary, aggregate, retention, pause_events)
    stage_record = _write_stage_record(decision)
    decision["stage_record"] = str(stage_record)
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
