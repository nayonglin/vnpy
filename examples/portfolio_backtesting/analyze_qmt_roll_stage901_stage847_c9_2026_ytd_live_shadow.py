from __future__ import annotations

import argparse
from dataclasses import replace
from datetime import datetime
import json
from pathlib import Path
from typing import Any

import pandas as pd

import analyze_qmt_roll_stage513_stage208_exact_position_margin_audit as s513
import analyze_qmt_roll_stage650_stage526_200k_capital_reality_check as s650
import analyze_qmt_roll_stage653_stage526_200k_forced_margin_deleverage as s653
import analyze_qmt_roll_stage658_stage653_2026_ytd_shadow as s658
import analyze_qmt_roll_stage660_stage653_multiperiod_live_audit as s660
import analyze_qmt_roll_stage847_stage830_c4_stop_retry_engine as s847
from qmt_roll_official_live_config import (
    OFFICIAL_LIVE_ALIAS,
    OFFICIAL_LIVE_CAPITAL,
    OFFICIAL_LIVE_CAPITAL_LABEL,
    OFFICIAL_LIVE_CURRENT_POSITIONS_PATH,
    OFFICIAL_LIVE_PROFILE_NAME,
    OFFICIAL_LIVE_REPORT_PATH,
    OFFICIAL_LIVE_SHADOW_ANALYSIS_START_DATE,
    OFFICIAL_LIVE_SIGNAL_PLAN_PATH,
    OFFICIAL_LIVE_SUMMARY_PATH,
    OFFICIAL_LIVE_VERSION,
    build_official_live_risk_snapshot,
)


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

MODEL_TAG = "stage901_stage847_c9_2026_ytd_live_shadow_v1"
OUTPUT_PREFIX = "qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow"
LINE_ID = "futures_trend_stage819_intraday_rules"

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
COST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cost_stress_{MODEL_TAG}.csv"
DAILY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_{MODEL_TAG}.csv"
POSITIONS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_positions_{MODEL_TAG}.csv"
PRODUCT_MARGIN_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_margin_{MODEL_TAG}.csv"
MONTHLY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_monthly_{MODEL_TAG}.csv"
CURRENT_POSITIONS_PATH = OFFICIAL_LIVE_CURRENT_POSITIONS_PATH
TRADES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trades_{MODEL_TAG}.csv"
ENTRY_RISK_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_risk_{MODEL_TAG}.csv"
ENTRY_CANDIDATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_candidates_{MODEL_TAG}.csv"
TRADE_EVENTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trade_events_{MODEL_TAG}.csv"
INTRADAY_EVENTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_intraday_events_{MODEL_TAG}.csv"
PENDING_ORDERS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_pending_orders_{MODEL_TAG}.csv"
SIGNAL_PLAN_PATH = OFFICIAL_LIVE_SIGNAL_PLAN_PATH
DECISION_PATH = OFFICIAL_LIVE_SUMMARY_PATH
REPORT_PATH = OFFICIAL_LIVE_REPORT_PATH

LEGACY_STAGE372_PROFILE_NAME = "stage526_200k_force95_to80_recovery_sleeve_r080_pc25_maxpos4"
LEGACY_STAGE372_BASE_PROFILE_NAME = "stage526_200k_force95_to80_largest_margin_r080_pc25_maxpos4"
LEGACY_STAGE372_STRATEGY_OVERRIDES: dict[str, Any] = {
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


def _run_live_c9(
    metadata: dict[str, Any],
    analysis_start: pd.Timestamp,
    analysis_end: pd.Timestamp,
) -> tuple[pd.DataFrame, dict[str, pd.DataFrame], Any]:
    original_start = s847.START
    original_end = s847.END
    legacy_official_state = {
        "OFFICIAL_LIVE_PROFILE_NAME": s660.OFFICIAL_LIVE_PROFILE_NAME,
        "OFFICIAL_LIVE_BASE_PROFILE_NAME": s660.OFFICIAL_LIVE_BASE_PROFILE_NAME,
        "OFFICIAL_LIVE_ALIAS": s660.OFFICIAL_LIVE_ALIAS,
        "OFFICIAL_LIVE_CAPITAL": s660.OFFICIAL_LIVE_CAPITAL,
        "OFFICIAL_LIVE_STRATEGY_OVERRIDES": s660.OFFICIAL_LIVE_STRATEGY_OVERRIDES,
    }
    try:
        s660.OFFICIAL_LIVE_PROFILE_NAME = LEGACY_STAGE372_PROFILE_NAME
        s660.OFFICIAL_LIVE_BASE_PROFILE_NAME = LEGACY_STAGE372_BASE_PROFILE_NAME
        s660.OFFICIAL_LIVE_ALIAS = "Stage372-20w"
        s660.OFFICIAL_LIVE_CAPITAL = 200_000.0
        s660.OFFICIAL_LIVE_STRATEGY_OVERRIDES = dict(LEGACY_STAGE372_STRATEGY_OVERRIDES)

        s847.START = analysis_start.normalize()
        s847.END = analysis_end.normalize()
        profile = s847._c9_profile(metadata)
        spec = profile["spec"]
        capital = replace(
            spec.capital,
            variant=OFFICIAL_LIVE_PROFILE_NAME,
            label=f"{OFFICIAL_LIVE_CAPITAL_LABEL} {OFFICIAL_LIVE_ALIAS} live default",
            account_capital=OFFICIAL_LIVE_CAPITAL,
            c3_capital=OFFICIAL_LIVE_CAPITAL,
            note=(
                f"{spec.capital.note} | Stage901 official live default operator override. "
                "C9 is promoted to live default by explicit operator request; no parameter search."
            ),
        )
        live_profile = dict(profile)
        live_profile["profile"] = OFFICIAL_LIVE_PROFILE_NAME
        live_profile["spec"] = replace(spec, capital=capital, profile=OFFICIAL_LIVE_PROFILE_NAME)
        combined, frames = s847._run_profile(live_profile, metadata)
        live_spec = live_profile["spec"]
    finally:
        s847.START = original_start
        s847.END = original_end
        for key, value in legacy_official_state.items():
            setattr(s660, key, value)

    combined["account_capital"] = live_spec.capital.account_capital
    combined["c3_capital"] = live_spec.capital.c3_capital
    combined["profile"] = live_spec.profile
    for frame in frames.values():
        if frame.empty:
            continue
        frame["account_capital"] = live_spec.capital.account_capital
        frame["c3_capital"] = live_spec.capital.c3_capital
        frame["profile"] = live_spec.profile
    for column in [
        "forced_margin_deleverage_count",
        "forced_margin_deleverage_closed_volume",
        "forced_margin_deleverage_ratio",
        "forced_margin_deleverage_max_observed_ratio",
    ]:
        combined[column] = 0
    return combined, frames, live_spec


def _signal_plan_from_trades(trades: pd.DataFrame, target_date: pd.Timestamp) -> pd.DataFrame:
    columns = [
        "shadow_session_id",
        "trade_id",
        "vt_symbol",
        "direction",
        "offset",
        "volume",
        "theoretical_price",
        "real_t1_open_proxy_price",
        "day_session_open_proxy_price",
        "proxy_quality",
        "exit_reason",
    ]
    if trades.empty:
        return pd.DataFrame(columns=columns)
    frame = trades.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame = frame[frame["date"].eq(target_date.normalize())].copy()
    if frame.empty:
        return pd.DataFrame(columns=columns)
    target = target_date.date().isoformat()
    frame["shadow_session_id"] = frame["trade_id"].astype(str).map(
        lambda value: f"C9LIVE-{target.replace('-', '')}-{value.replace('.', '-')}"
    )
    frame["theoretical_price"] = pd.to_numeric(frame.get("price", 0.0), errors="coerce").fillna(0.0)
    frame["real_t1_open_proxy_price"] = ""
    frame["day_session_open_proxy_price"] = ""
    frame["proxy_quality"] = "historical_shadow_trade_price_no_broker_submit"
    for column in columns:
        if column not in frame.columns:
            frame[column] = ""
    return frame.loc[:, columns].sort_values(["vt_symbol", "trade_id"]).reset_index(drop=True)


def _write_report(
    summary: pd.DataFrame,
    cost: pd.DataFrame,
    monthly: pd.DataFrame,
    current_positions: pd.DataFrame,
    signal_plan: pd.DataFrame,
    pending_orders: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    lines = [
        "# Stage901 C9 当前实盘默认影子盘",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        f"- line_id：`{LINE_ID}`",
        f"- 当前实盘默认：`{OFFICIAL_LIVE_VERSION}` / `{OFFICIAL_LIVE_ALIAS}`。",
        f"- 统计区间：`{decision['analysis_start']}` 至 `{decision['analysis_end']}`。",
        "- 性质：只读影子盘绩效；不连接 CTP，不读取账户，不调用下单。",
        "- 统计起点由 `OFFICIAL_LIVE_SHADOW_ANALYSIS_START_DATE` 或命令行 `--analysis-start` 决定。",
        "- 切换口径：operator override，把 C9 从 primary candidate 切为 live default。",
        "",
        "## 核心结果",
        "",
        _md_table(
            summary[
                [
                    "variant",
                    "end_equity",
                    "total_return_pct",
                    "cagr_pct",
                    "max_dd_pct",
                    "sharpe",
                    "max_broker10_margin_to_equity_pct",
                    "days_over_100pct",
                    "days_over_90pct",
                    "total_slippage",
                    "total_trade_count",
                    "nonzero_daily_win_rate_pct",
                    "deployable_pass",
                ]
            ]
        ),
        "",
        "## 月度结果",
        "",
        _md_table(
            monthly[
                [
                    "variant",
                    "month",
                    "start_equity",
                    "end_equity",
                    "return_pct",
                    "max_dd_pct",
                    "max_broker10_margin_to_equity_pct",
                    "trade_count",
                    "slippage",
                ]
            ],
            max_rows=80,
        ),
        "",
        "## 当前持仓快照",
        "",
        _md_table(current_positions, max_rows=80),
        "",
        "## 目标日信号计划",
        "",
        _md_table(signal_plan, max_rows=80),
        "",
        "## 目标日后 Pending Orders",
        "",
        _md_table(pending_orders, max_rows=80),
        "",
        "## 成本压力",
        "",
        _md_table(
            cost[
                [
                    "variant",
                    "cost_multiplier",
                    "end_equity",
                    "total_return_pct",
                    "max_dd_pct",
                    "sharpe",
                    "max_broker10_margin_to_equity_pct",
                    "deployable_pass",
                ]
            ],
            max_rows=20,
        ),
        "",
        "## 判断",
        "",
        f"- 风险层级：`{decision['risk_snapshot']['risk_level']}`。",
        f"- 是否允许真实新开仓：`{decision['risk_snapshot']['allow_real_new_orders']}`。",
        f"- 目标日信号数：`{decision['target_signal_count']}`。",
        f"- 目标日后 pending order 数：`{decision['pending_order_count']}`。",
        "- 决策：`stage901_c9_live_default_shadow_measured_no_order_api`。",
        "- 后续真实执行仍需 fresh read-only、dry-run、broker-state reconciliation 和显式下单确认。",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run C9 official live default shadow.")
    parser.add_argument("--analysis-start", default=OFFICIAL_LIVE_SHADOW_ANALYSIS_START_DATE)
    parser.add_argument("--target-date", default="2026-06-12")
    args = parser.parse_args()

    analysis_start = pd.Timestamp(str(args.analysis_start)).normalize()
    analysis_end = pd.Timestamp(str(args.target_date)).normalize()

    metadata = s513._metadata()
    combined, frames, spec = _run_live_c9(metadata, analysis_start, analysis_end)
    positions = frames.get("positions", pd.DataFrame()).copy()
    trades = frames.get("trades", pd.DataFrame()).copy()
    entry_risk = frames.get("entry_risk", pd.DataFrame()).copy()
    entry_candidates = frames.get("entry_candidates", pd.DataFrame()).copy()
    trade_events = frames.get("trade_events", pd.DataFrame()).copy()
    intraday_events = frames.get("intraday_events", pd.DataFrame()).copy()
    pending_orders = frames.get("pending_orders", pd.DataFrame()).copy()

    if not positions.empty:
        _margin_daily, product_margin = s513._position_margin(positions, metadata)
    else:
        product_margin = pd.DataFrame()

    summary_rows = []
    cost_rows = []
    for cost_multiplier in s653.COST_MULTIPLIERS:
        row = s650._metrics(combined, spec.capital, cost_multiplier)
        row["profile"] = spec.profile
        row["official_live_version"] = OFFICIAL_LIVE_VERSION
        cost_rows.append(row)
        if cost_multiplier == 1.0:
            summary_rows.append(row)
    summary = pd.DataFrame(summary_rows)
    cost = pd.DataFrame(cost_rows)
    monthly = s658._monthly_returns(combined)
    latest_date = pd.to_datetime(combined["date"], errors="coerce").max().normalize()
    current_positions = s658._current_positions(positions, metadata, latest_date)
    signal_plan = _signal_plan_from_trades(trades, analysis_end)

    current_row = summary[summary["variant"].eq(OFFICIAL_LIVE_PROFILE_NAME)].to_dict(orient="records")
    decision = {
        "stage": "Stage901",
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "analysis_start": analysis_start.date().isoformat(),
        "analysis_end": analysis_end.date().isoformat(),
        "latest_available_data_date": latest_date.date().isoformat(),
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "official_live_alias": OFFICIAL_LIVE_ALIAS,
        "current_variant": current_row[0] if current_row else {},
        "risk_snapshot": {},
        "decision": "stage901_c9_live_default_shadow_measured_no_order_api",
        "execution_scope": "read-only backtest/shadow performance only; no CTP connection and no order API call",
        "target_signal_count": int(len(signal_plan)),
        "pending_order_count": int(len(pending_orders)),
        "pending_orders": pending_orders.to_dict(orient="records"),
        "order_api_called": False,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
    }
    decision["risk_snapshot"] = build_official_live_risk_snapshot(decision)

    combined.to_csv(DAILY_PATH, index=False, encoding="utf-8-sig")
    positions.to_csv(POSITIONS_PATH, index=False, encoding="utf-8-sig")
    product_margin.to_csv(PRODUCT_MARGIN_PATH, index=False, encoding="utf-8-sig")
    monthly.to_csv(MONTHLY_PATH, index=False, encoding="utf-8-sig")
    current_positions.to_csv(CURRENT_POSITIONS_PATH, index=False, encoding="utf-8-sig")
    trades.to_csv(TRADES_PATH, index=False, encoding="utf-8-sig")
    entry_risk.to_csv(ENTRY_RISK_PATH, index=False, encoding="utf-8-sig")
    entry_candidates.to_csv(ENTRY_CANDIDATES_PATH, index=False, encoding="utf-8-sig")
    trade_events.to_csv(TRADE_EVENTS_PATH, index=False, encoding="utf-8-sig")
    intraday_events.to_csv(INTRADAY_EVENTS_PATH, index=False, encoding="utf-8-sig")
    pending_orders.to_csv(PENDING_ORDERS_PATH, index=False, encoding="utf-8-sig")
    signal_plan.to_csv(SIGNAL_PLAN_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    cost.to_csv(COST_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_report(summary, cost, monthly, current_positions, signal_plan, pending_orders, decision)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
