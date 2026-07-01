from __future__ import annotations

from dataclasses import replace
from datetime import datetime
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import analyze_qmt_roll_stage650_stage526_200k_capital_reality_check as s650
import analyze_qmt_roll_stage653_stage526_200k_forced_margin_deleverage as s653
import analyze_qmt_roll_stage660_stage653_multiperiod_live_audit as s660
import analyze_qmt_roll_stage830_stage827_c2_broker10_margin_cap as s830
import analyze_qmt_roll_stage847_stage830_c4_stop_retry_engine as s847
import analyze_qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow as s901
from qmt_roll_official_live_config import (
    OFFICIAL_LIVE_AI_ELIGIBILITY_PATH,
    OFFICIAL_LIVE_ALIAS,
    OFFICIAL_LIVE_VERSION,
    build_official_live_strategy_overrides,
)


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

LINE_ID = "futures_trend_stage819_intraday_rules"
STAGE = "Stage156"
MODEL_TAG = "stage156_current_rebuild_three_arm_annual_baseline_v1"
OUTPUT_PREFIX = "qmt_roll_stage156_current_rebuild_three_arm_annual_baseline"

CAPITAL = 150_000.0
REQUESTED_START = pd.Timestamp("2018-01-01")
REQUESTED_END = pd.Timestamp("2026-06-30")
START_MONTHS = (1,)

ARM_STAGE372 = "stage372_legacy_recovery_sleeve_15w_current_ai"
ARM_C4 = "stage819_c4_broker10_cap_15w_current_ai"
ARM_C9 = "stage847_c9_stop_retry_15w_current_ai"

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
AGG_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_aggregate_{MODEL_TAG}.csv"
COMPARISON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_comparison_{MODEL_TAG}.csv"
CURVES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

RECOVERY_SLEEVE_OVERRIDES: dict[str, Any] = {
    "enable_streak_entry_structure_risk_recovery": True,
    "streak_entry_structure_recovery_signals": "long_case1a,short_case1a",
    "streak_entry_structure_recovery_min_multiplier": 1.0,
    "streak_entry_structure_recovery_require_flat_portfolio": True,
    "streak_entry_structure_recovery_max_same_direction_corr": 0.30,
    "streak_entry_structure_recovery_require_rsi_confirmation": False,
    "enable_recovery_sleeve": True,
    "recovery_sleeve_base_multiplier_max": 0.1000001,
    "recovery_sleeve_broker_margin_multiplier": 1.65,
    "recovery_sleeve_max_single_contract_broker_margin_to_equity": 0.20,
    "recovery_sleeve_cooldown_days": 20,
    "recovery_sleeve_volume": 1,
}


def _json_safe(value: Any) -> Any:
    return s650._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s650._md_table(frame, max_rows=max_rows)


def _date_text(value: Any) -> str:
    return pd.Timestamp(value).date().isoformat()


def _start_month_text(value: pd.Timestamp) -> str:
    return pd.Timestamp(value).strftime("%Y-%m")


def _build_start_dates() -> list[pd.Timestamp]:
    starts: list[pd.Timestamp] = []
    for year in range(REQUESTED_START.year, REQUESTED_END.year + 1):
        for month in START_MONTHS:
            start = pd.Timestamp(year=year, month=month, day=1)
            if REQUESTED_START <= start <= REQUESTED_END:
                starts.append(start)
    return starts


def _drawdown_pct(equity: pd.Series) -> pd.Series:
    values = pd.to_numeric(equity, errors="coerce").ffill()
    peak = values.cummax()
    return (values / peak.replace(0.0, np.nan) - 1.0).replace([np.inf, -np.inf], np.nan).fillna(0.0) * 100.0


def _daily_sharpe(nav: pd.Series) -> float:
    returns = pd.to_numeric(nav, errors="coerce").pct_change().replace([np.inf, -np.inf], np.nan).dropna()
    if returns.empty:
        return 0.0
    std = float(returns.std(ddof=1))
    if std <= 0.0 or np.isnan(std):
        return 0.0
    return float(returns.mean() / std * np.sqrt(252.0))


def _safe_sum(frame: pd.DataFrame, column: str) -> float:
    if column not in frame.columns:
        return 0.0
    return float(pd.to_numeric(frame[column], errors="coerce").fillna(0.0).sum())


def _safe_max(frame: pd.DataFrame, column: str) -> float:
    if column not in frame.columns:
        return 0.0
    series = pd.to_numeric(frame[column], errors="coerce").dropna()
    return float(series.max()) if len(series) else 0.0


def _current_ai_capital_overrides() -> dict[str, Any]:
    live = dict(build_official_live_strategy_overrides())
    result = {
        "account_capital": CAPITAL,
        "c3_capital": CAPITAL,
        "enable_ai_product_pool_filter": True,
        "ai_product_pool_eligibility_path": str(OFFICIAL_LIVE_AI_ELIGIBILITY_PATH),
        "ai_product_pool_strategy": str(live.get("ai_product_pool_strategy", "")),
    }
    if "ai_product_pool_use_next_trade_date_for_entry" in live:
        result["ai_product_pool_use_next_trade_date_for_entry"] = bool(
            live.get("ai_product_pool_use_next_trade_date_for_entry")
        )
    return result


def _stage372_spec(metadata: dict[str, Any], start: pd.Timestamp) -> s653.ForcedVariant:
    identity_map = s653.s519._product_identity_cluster_map(metadata)
    variants = s653._variants(identity_map)
    base = next(
        item
        for item in variants
        if item.capital.variant == "stage526_200k_force95_to80_largest_margin_r080_pc25_maxpos4"
    )
    capital = replace(
        base.capital,
        variant=f"{ARM_STAGE372}_{_start_month_text(start).replace('-', '_')}",
        label=f"15w Stage372 legacy recovery sleeve current AI {_start_month_text(start)}",
        account_capital=CAPITAL,
        c3_capital=CAPITAL,
        note=(
            f"{base.capital.note} | Stage156 current-rebuild baseline: Stage372 recovery sleeve logic, "
            "fresh 15w capital, current Stage182 AI pool."
        ),
    )
    overrides = {
        **base.overrides,
        **RECOVERY_SLEEVE_OVERRIDES,
        **_current_ai_capital_overrides(),
    }
    return s653.ForcedVariant(
        capital=capital,
        overrides=overrides,
        profile=ARM_STAGE372,
    )


def _with_legacy_stage372_state() -> dict[str, Any]:
    state = {
        "OFFICIAL_LIVE_PROFILE_NAME": s660.OFFICIAL_LIVE_PROFILE_NAME,
        "OFFICIAL_LIVE_BASE_PROFILE_NAME": s660.OFFICIAL_LIVE_BASE_PROFILE_NAME,
        "OFFICIAL_LIVE_ALIAS": s660.OFFICIAL_LIVE_ALIAS,
        "OFFICIAL_LIVE_CAPITAL": s660.OFFICIAL_LIVE_CAPITAL,
        "OFFICIAL_LIVE_STRATEGY_OVERRIDES": s660.OFFICIAL_LIVE_STRATEGY_OVERRIDES,
    }
    s660.OFFICIAL_LIVE_PROFILE_NAME = s901.LEGACY_STAGE372_PROFILE_NAME
    s660.OFFICIAL_LIVE_BASE_PROFILE_NAME = s901.LEGACY_STAGE372_BASE_PROFILE_NAME
    s660.OFFICIAL_LIVE_ALIAS = "Stage372-20w"
    s660.OFFICIAL_LIVE_CAPITAL = 200_000.0
    s660.OFFICIAL_LIVE_STRATEGY_OVERRIDES = dict(s901.LEGACY_STAGE372_STRATEGY_OVERRIDES)
    return state


def _restore_legacy_state(state: dict[str, Any]) -> None:
    for key, value in state.items():
        setattr(s660, key, value)


def _run_stage372(metadata: dict[str, Any], start: pd.Timestamp) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    spec = _stage372_spec(metadata, start)
    combined, forced_events = s660._run_independent_window(
        spec=spec,
        metadata=metadata,
        analysis_start=start,
        analysis_end=REQUESTED_END,
    )
    frames = {
        "forced_events": forced_events,
        "trades": pd.DataFrame(),
        "trade_events": pd.DataFrame(),
        "intraday_events": pd.DataFrame(),
        "stop_retry_events": pd.DataFrame(),
    }
    return combined, frames


def _stage819_c4_profile(metadata: dict[str, Any], start: pd.Timestamp) -> dict[str, Any]:
    state = _with_legacy_stage372_state()
    try:
        profile = s830._cap_profile(metadata)
    finally:
        _restore_legacy_state(state)
    spec = profile["spec"]
    capital = replace(
        spec.capital,
        variant=f"{ARM_C4}_{_start_month_text(start).replace('-', '_')}",
        label=f"15w Stage819/C4 broker10 cap current AI {_start_month_text(start)}",
        account_capital=CAPITAL,
        c3_capital=CAPITAL,
        note=(
            f"{spec.capital.note} | Stage156 current-rebuild baseline: Stage819 C4, "
            "fresh 15w capital, current Stage182 AI pool."
        ),
    )
    overrides = {
        **spec.overrides,
        **_current_ai_capital_overrides(),
        "enable_stage827_intraday_c2_stop": True,
        "enable_stage830_broker10_margin_cap": True,
        "stage830_broker_margin_multiplier": s830.BROKER_MARGIN_MULTIPLIER,
        "stage830_projected_broker10_margin_to_equity_cap": s830.PROJECTED_BROKER10_MARGIN_TO_EQUITY_CAP,
    }
    result = dict(profile)
    result["profile"] = ARM_C4
    result["spec"] = replace(spec, capital=capital, overrides=overrides, profile=ARM_C4)
    return result


def _stage847_c9_profile(metadata: dict[str, Any], start: pd.Timestamp) -> dict[str, Any]:
    state = _with_legacy_stage372_state()
    try:
        profile = s847._c9_profile(metadata)
    finally:
        _restore_legacy_state(state)
    spec = profile["spec"]
    capital = replace(
        spec.capital,
        variant=f"{ARM_C9}_{_start_month_text(start).replace('-', '_')}",
        label=f"15w Stage847/C9 stop retry current AI {_start_month_text(start)}",
        account_capital=CAPITAL,
        c3_capital=CAPITAL,
        note=(
            f"{spec.capital.note} | Stage156 current-rebuild baseline: Stage847 C9 stop/retry, "
            "fresh 15w capital, current Stage182 AI pool."
        ),
    )
    overrides = {
        **spec.overrides,
        **_current_ai_capital_overrides(),
        "enable_stage827_intraday_c2_stop": True,
        "enable_stage830_broker10_margin_cap": True,
        "enable_stage847_half_r_stop_retry": True,
        "stage847_stop_retry_r": s847.STOP_RETRY_R,
        "stage847_max_retries": s847.MAX_RETRIES,
    }
    result = dict(profile)
    result["profile"] = ARM_C9
    result["spec"] = replace(spec, capital=capital, overrides=overrides, profile=ARM_C9)
    return result


def _run_stage847_profile(
    *,
    profile: dict[str, Any],
    start: pd.Timestamp,
) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    original_start = s847.START
    original_end = s847.END
    try:
        s847.START = start.normalize()
        s847.END = REQUESTED_END.normalize()
        combined, frames = s847._run_profile(profile, s901.s513._metadata())
    finally:
        s847.START = original_start
        s847.END = original_end
    return combined, frames


def _summarize(
    *,
    arm: str,
    combined: pd.DataFrame,
    frames: dict[str, pd.DataFrame],
    start: pd.Timestamp,
) -> dict[str, Any]:
    frame = combined.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame = frame.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    if frame.empty:
        raise RuntimeError(f"empty combined frame for {arm} {start.date().isoformat()}")
    equity = pd.to_numeric(frame["account_equity"], errors="coerce").ffill()
    nav = equity / CAPITAL
    drawdown = _drawdown_pct(equity)
    broker10 = pd.to_numeric(frame.get("broker10_margin_to_equity_pct", 0.0), errors="coerce").fillna(0.0)
    trade_events = frames.get("trade_events", pd.DataFrame())
    stop_retry_events = frames.get("stop_retry_events", pd.DataFrame())
    intraday_events = frames.get("intraday_events", pd.DataFrame())
    forced_events = frames.get("forced_events", pd.DataFrame())
    broker10_cap_event_count = 0
    if not trade_events.empty and "reason" in trade_events.columns:
        broker10_cap_event_count = int(
            trade_events["reason"].astype(str).str.startswith("broker10_margin_cap", na=False).sum()
        )
    end_equity = float(equity.iloc[-1])
    elapsed_days = max(1, int((frame["date"].iloc[-1] - frame["date"].iloc[0]).days))
    return {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "arm": arm,
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "official_live_alias": OFFICIAL_LIVE_ALIAS,
        "ai_pool_path": str(OFFICIAL_LIVE_AI_ELIGIBILITY_PATH),
        "requested_start": _date_text(start),
        "requested_start_month": _start_month_text(start),
        "requested_end": _date_text(REQUESTED_END),
        "actual_start": _date_text(frame["date"].iloc[0]),
        "actual_end": _date_text(frame["date"].iloc[-1]),
        "trading_days": int(len(frame)),
        "calendar_days": int(elapsed_days + 1),
        "account_capital": CAPITAL,
        "end_equity": end_equity,
        "total_return_pct": float((end_equity / CAPITAL - 1.0) * 100.0),
        "cagr_pct": float((end_equity / CAPITAL) ** (365.25 / elapsed_days) - 1.0) * 100.0,
        "max_dd_pct": float(drawdown.min()) if len(drawdown) else 0.0,
        "min_equity": float(equity.min()) if len(equity) else end_equity,
        "max_equity": float(equity.max()) if len(equity) else end_equity,
        "sharpe": _daily_sharpe(nav),
        "total_slippage": _safe_sum(frame, "slippage"),
        "total_trade_count": _safe_sum(frame, "trade_count"),
        "max_broker10_margin_to_equity_pct": float(broker10.max()) if len(broker10) else 0.0,
        "days_over_100pct": int((broker10 > 100.0).sum()) if len(broker10) else 0,
        "dd30_fail": int(float(drawdown.min()) < -30.0) if len(drawdown) else 0,
        "dd40_fail": int(float(drawdown.min()) < -40.0) if len(drawdown) else 0,
        "dd50_fail": int(float(drawdown.min()) < -50.0) if len(drawdown) else 0,
        "broker100_fail": int(float(broker10.max()) > 100.0) if len(broker10) else 0,
        "forced_event_count": int(len(forced_events)),
        "intraday_event_count": int(len(intraday_events)),
        "stop_retry_event_count": int(len(stop_retry_events)),
        "broker10_cap_event_count": broker10_cap_event_count,
    }


def _curve_frame(arm: str, combined: pd.DataFrame, start: pd.Timestamp) -> pd.DataFrame:
    frame = combined.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame = frame.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    frame["stage"] = STAGE
    frame["model_tag"] = MODEL_TAG
    frame["line_id"] = LINE_ID
    frame["arm"] = arm
    frame["requested_start"] = _date_text(start)
    frame["requested_start_month"] = _start_month_text(start)
    frame["requested_end"] = _date_text(REQUESTED_END)
    frame["account_capital"] = CAPITAL
    frame["nav"] = pd.to_numeric(frame["account_equity"], errors="coerce") / CAPITAL
    frame["drawdown_pct"] = _drawdown_pct(pd.to_numeric(frame["account_equity"], errors="coerce"))
    frame["days_since_start"] = np.arange(len(frame), dtype=int)
    return frame


def _aggregate(summary: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for arm, group in summary.groupby("arm", sort=True):
        returns = pd.to_numeric(group["total_return_pct"], errors="coerce")
        dds = pd.to_numeric(group["max_dd_pct"], errors="coerce")
        sharpes = pd.to_numeric(group["sharpe"], errors="coerce")
        broker = pd.to_numeric(group["max_broker10_margin_to_equity_pct"], errors="coerce")
        rows.append(
            {
                "stage": STAGE,
                "model_tag": MODEL_TAG,
                "line_id": LINE_ID,
                "arm": arm,
                "sample_count": int(len(group)),
                "positive_count": int((returns > 0.0).sum()),
                "min_return_pct": float(returns.min()),
                "median_return_pct": float(returns.median()),
                "max_return_pct": float(returns.max()),
                "worst_max_dd_pct": float(dds.min()),
                "median_max_dd_pct": float(dds.median()),
                "median_sharpe": float(sharpes.median()),
                "min_sharpe": float(sharpes.min()),
                "peak_broker10_margin_to_equity_pct": float(broker.max()),
                "dd30_fail_count": int(pd.to_numeric(group["dd30_fail"], errors="coerce").fillna(0).sum()),
                "dd40_fail_count": int(pd.to_numeric(group["dd40_fail"], errors="coerce").fillna(0).sum()),
                "dd50_fail_count": int(pd.to_numeric(group["dd50_fail"], errors="coerce").fillna(0).sum()),
                "broker100_fail_count": int(pd.to_numeric(group["broker100_fail"], errors="coerce").fillna(0).sum()),
                "total_trade_count_sum": float(
                    pd.to_numeric(group["total_trade_count"], errors="coerce").fillna(0.0).sum()
                ),
                "total_slippage_sum": float(
                    pd.to_numeric(group["total_slippage"], errors="coerce").fillna(0.0).sum()
                ),
                "total_stop_retry_event_count": int(
                    pd.to_numeric(group["stop_retry_event_count"], errors="coerce").fillna(0).sum()
                ),
                "total_forced_event_count": int(
                    pd.to_numeric(group["forced_event_count"], errors="coerce").fillna(0).sum()
                ),
                "total_broker10_cap_event_count": int(
                    pd.to_numeric(group["broker10_cap_event_count"], errors="coerce").fillna(0).sum()
                ),
            }
        )
    return pd.DataFrame(rows)


def _comparison(summary: pd.DataFrame) -> pd.DataFrame:
    base = summary[summary["arm"].eq(ARM_STAGE372)].copy()
    c4 = summary[summary["arm"].eq(ARM_C4)].copy()
    c9 = summary[summary["arm"].eq(ARM_C9)].copy()
    merged = (
        base.merge(c4, on="requested_start_month", suffixes=("_stage372", "_c4"))
        .merge(c9, on="requested_start_month")
        .rename(
            columns={
                "end_equity": "end_equity_c9",
                "total_return_pct": "total_return_pct_c9",
                "max_dd_pct": "max_dd_pct_c9",
                "sharpe": "sharpe_c9",
                "total_trade_count": "total_trade_count_c9",
                "max_broker10_margin_to_equity_pct": "max_broker10_margin_to_equity_pct_c9",
            }
        )
    )
    rows: list[dict[str, Any]] = []
    for row in merged.itertuples(index=False):
        rows.append(
            {
                "requested_start_month": row.requested_start_month,
                "return_stage372": row.total_return_pct_stage372,
                "return_c4": row.total_return_pct_c4,
                "return_c9": row.total_return_pct_c9,
                "c9_minus_stage372_return_pp": row.total_return_pct_c9 - row.total_return_pct_stage372,
                "c9_minus_c4_return_pp": row.total_return_pct_c9 - row.total_return_pct_c4,
                "dd_stage372": row.max_dd_pct_stage372,
                "dd_c4": row.max_dd_pct_c4,
                "dd_c9": row.max_dd_pct_c9,
                "c9_minus_stage372_dd_pp": row.max_dd_pct_c9 - row.max_dd_pct_stage372,
                "c9_minus_c4_dd_pp": row.max_dd_pct_c9 - row.max_dd_pct_c4,
                "sharpe_stage372": row.sharpe_stage372,
                "sharpe_c4": row.sharpe_c4,
                "sharpe_c9": row.sharpe_c9,
                "broker10_stage372": row.max_broker10_margin_to_equity_pct_stage372,
                "broker10_c4": row.max_broker10_margin_to_equity_pct_c4,
                "broker10_c9": row.max_broker10_margin_to_equity_pct_c9,
                "trades_stage372": row.total_trade_count_stage372,
                "trades_c4": row.total_trade_count_c4,
                "trades_c9": row.total_trade_count_c9,
            }
        )
    return pd.DataFrame(rows)


def _write_report(summary: pd.DataFrame, aggregate: pd.DataFrame, comparison: pd.DataFrame, decision: dict[str, Any]) -> None:
    view_summary = summary[
        [
            "arm",
            "requested_start_month",
            "actual_end",
            "end_equity",
            "total_return_pct",
            "max_dd_pct",
            "sharpe",
            "max_broker10_margin_to_equity_pct",
            "total_trade_count",
            "stop_retry_event_count",
            "forced_event_count",
            "broker10_cap_event_count",
        ]
    ].copy()
    view_comparison = comparison[
        [
            "requested_start_month",
            "return_stage372",
            "return_c4",
            "return_c9",
            "c9_minus_stage372_return_pp",
            "c9_minus_c4_return_pp",
            "dd_stage372",
            "dd_c4",
            "dd_c9",
            "c9_minus_stage372_dd_pp",
            "c9_minus_c4_dd_pp",
        ]
    ].copy()
    lines = [
        "# Stage156 当前重建版三臂年度基准",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        f"- line_id：`{LINE_ID}`",
        f"- 当前官方版本：`{OFFICIAL_LIVE_VERSION}` / `{OFFICIAL_LIVE_ALIAS}`。",
        f"- 统一资金：`{CAPITAL:,.0f}`。",
        f"- 统一 AI 池：`{OFFICIAL_LIVE_AI_ELIGIBILITY_PATH}`。",
        f"- 起点：从 `{REQUESTED_START.date()}` 起，每年 `1月1日`；请求结束日 `{REQUESTED_END.date()}`。",
        "- 三臂：Stage372 legacy recovery sleeve、Stage819/C4 broker10 cap、Stage847/C9 0.5R stop retry once。",
        "- 不连接 CTP，不读取账户，不调用订单 API。",
        "",
        "## Aggregate",
        "",
        _md_table(aggregate, max_rows=20),
        "",
        "## Pairwise",
        "",
        _md_table(view_comparison, max_rows=80),
        "",
        "## Windows",
        "",
        _md_table(view_summary, max_rows=120),
        "",
        "## Decision",
        "",
        f"- 决策：`{decision['decision']}`",
        f"- 过拟合反思：{decision['overfit_reflection_after']}",
        f"- 继续价值反思：{decision['continue_value_after']}",
        "",
        "## Outputs",
        "",
    ]
    for key, path in decision["outputs"].items():
        lines.append(f"- {key}: `{path}`")
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(
        f"[stage156] starts={REQUESTED_START.date()} end={REQUESTED_END.date()} "
        "arms=stage372,c4,c9 capital=15w current_ai",
        flush=True,
    )
    metadata = s901.s513._metadata()
    s901._ensure_c9_minute_bars(metadata)
    starts = _build_start_dates()

    summary_rows: list[dict[str, Any]] = []
    curve_frames: list[pd.DataFrame] = []
    for idx, start in enumerate(starts, start=1):
        for arm in [ARM_STAGE372, ARM_C4, ARM_C9]:
            print(f"[stage156] running start {idx}/{len(starts)} {start.date()} arm={arm}", flush=True)
            if arm == ARM_STAGE372:
                combined, frames = _run_stage372(metadata, start)
            elif arm == ARM_C4:
                combined, frames = _run_stage847_profile(
                    profile=_stage819_c4_profile(metadata, start),
                    start=start,
                )
            elif arm == ARM_C9:
                combined, frames = _run_stage847_profile(
                    profile=_stage847_c9_profile(metadata, start),
                    start=start,
                )
            else:
                raise RuntimeError(f"unknown arm: {arm}")
            summary_rows.append(_summarize(arm=arm, combined=combined, frames=frames, start=start))
            curve_frames.append(_curve_frame(arm, combined, start))

    summary = pd.DataFrame(summary_rows).sort_values(["requested_start", "arm"]).reset_index(drop=True)
    curves = pd.concat(curve_frames, ignore_index=True, sort=False) if curve_frames else pd.DataFrame()
    aggregate = _aggregate(summary)
    comparison = _comparison(summary)

    c9_return_wins_vs_stage372 = int((comparison["c9_minus_stage372_return_pp"] > 0.0).sum())
    c9_return_wins_vs_c4 = int((comparison["c9_minus_c4_return_pp"] > 0.0).sum())
    c9_dd_wins_vs_stage372 = int((comparison["c9_minus_stage372_dd_pp"] >= 0.0).sum())
    c9_dd_wins_vs_c4 = int((comparison["c9_minus_c4_dd_pp"] >= 0.0).sum())
    decision = {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "official_live_alias": OFFICIAL_LIVE_ALIAS,
        "capital": CAPITAL,
        "ai_pool_path": str(OFFICIAL_LIVE_AI_ELIGIBILITY_PATH),
        "requested_start": REQUESTED_START.date().isoformat(),
        "requested_end": REQUESTED_END.date().isoformat(),
        "sample_count_per_arm": int(len(starts)),
        "arms": [ARM_STAGE372, ARM_C4, ARM_C9],
        "c9_return_wins_vs_stage372": c9_return_wins_vs_stage372,
        "c9_return_wins_vs_c4": c9_return_wins_vs_c4,
        "c9_dd_wins_vs_stage372": c9_dd_wins_vs_stage372,
        "c9_dd_wins_vs_c4": c9_dd_wins_vs_c4,
        "aggregate": aggregate.to_dict(orient="records"),
        "decision": "stage156_three_arm_current_rebuild_baseline_measured_no_order_api",
        "order_api_called": False,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "ctp_connected": False,
        "external_research_judgment": (
            "Skipped external search per operator constraint; this is a local historical-structure baseline."
        ),
        "overfit_reflection_before": (
            "否。三臂、资金、AI 池、年度起点和终点均预先固定，不根据结果挑参数。"
        ),
        "continue_value_before": (
            "是。Stage154/155 已确认 AI 必须保留；三臂基准能定位 C9 相对旧正式骨架和 C4 的真实边际。"
        ),
        "overfit_reflection_after": "待运行后填写",
        "continue_value_after": "待运行后填写",
        "outputs": {
            "summary": str(SUMMARY_PATH),
            "aggregate": str(AGG_PATH),
            "comparison": str(COMPARISON_PATH),
            "curves": str(CURVES_PATH),
            "decision": str(DECISION_PATH),
            "report": str(REPORT_PATH),
        },
    }
    if c9_return_wins_vs_c4 >= 7 and c9_dd_wins_vs_c4 <= 4:
        decision["overfit_reflection_after"] = (
            "否，但不能把 C9 的收益优势理解成低风险优势；它更像进攻结构，仍需要账户/持仓层风险尾治理。"
        )
    else:
        decision["overfit_reflection_after"] = (
            "否。本阶段只做固定三臂基准；结果用于归因，不产生新参数或过滤规则。"
        )
    decision["continue_value_after"] = (
        "是。下一步应基于三臂差异做风险尾归因或 AI 拦截归因，而不是扫 C9 R 倍数、重试次数或 AI topN。"
    )

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    aggregate.to_csv(AGG_PATH, index=False, encoding="utf-8-sig")
    comparison.to_csv(COMPARISON_PATH, index=False, encoding="utf-8-sig")
    curves.to_csv(CURVES_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_report(summary, aggregate, comparison, decision)

    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print("aggregate")
    print(aggregate.to_string(index=False))
    print("comparison")
    print(comparison.to_string(index=False))


if __name__ == "__main__":
    main()
