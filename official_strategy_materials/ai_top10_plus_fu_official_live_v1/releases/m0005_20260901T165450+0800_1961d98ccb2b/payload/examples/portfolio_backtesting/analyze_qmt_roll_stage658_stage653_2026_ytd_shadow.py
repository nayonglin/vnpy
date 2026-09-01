from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

import analyze_qmt_roll_stage513_stage208_exact_position_margin_audit as s513  # noqa: E402
import analyze_qmt_roll_stage650_stage526_200k_capital_reality_check as s650  # noqa: E402
import analyze_qmt_roll_stage653_stage526_200k_forced_margin_deleverage as s653  # noqa: E402


MODEL_TAG = "stage658_stage653_2026_ytd_shadow_v1"
OUTPUT_PREFIX = "qmt_roll_stage658_stage653_2026_ytd_shadow"
LINE_ID = "futures_trend_drawdown30_preserve_return"

ANALYSIS_START = datetime(2026, 1, 1)
ANALYSIS_END = s653.s517.END_DT
CURRENT_VARIANT = "stage526_200k_force95_to80_largest_margin_r080_pc25_maxpos4"
BASELINE_VARIANT = s653.BASELINE_VARIANT
SELECTED_VARIANTS = (BASELINE_VARIANT, CURRENT_VARIANT)

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
COST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cost_stress_{MODEL_TAG}.csv"
DAILY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_{MODEL_TAG}.csv"
POSITIONS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_positions_{MODEL_TAG}.csv"
PRODUCT_MARGIN_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_margin_{MODEL_TAG}.csv"
MONTHLY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_monthly_{MODEL_TAG}.csv"
CURRENT_POSITIONS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_current_positions_{MODEL_TAG}.csv"
EVENT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_event_days_{MODEL_TAG}.csv"
FORCED_EVENTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_forced_events_{MODEL_TAG}.csv"
FORCED_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_forced_summary_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


def _json_safe(value: Any) -> Any:
    return s650._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s650._md_table(frame, max_rows=max_rows)


def _monthly_returns(combo_daily: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for variant, frame in combo_daily.groupby("variant", sort=False):
        ordered = frame.sort_values("date").copy()
        ordered["month"] = pd.to_datetime(ordered["date"]).dt.to_period("M")
        previous_equity = float(ordered["account_capital"].iloc[0])
        for month, month_frame in ordered.groupby("month", sort=True):
            start_equity = previous_equity
            end_equity = float(month_frame["account_equity"].iloc[-1])
            previous_equity = end_equity
            month_dates = pd.to_datetime(month_frame["date"]).reset_index(drop=True)
            equity = pd.Series(
                np.r_[start_equity, month_frame["account_equity"].to_numpy(dtype=float)],
                index=pd.Index([month_dates.iloc[0] - pd.Timedelta(days=1), *month_dates]),
            )
            rows.append(
                {
                    "variant": variant,
                    "label": str(month_frame["label"].iloc[0]),
                    "month": str(month),
                    "start_equity": start_equity,
                    "end_equity": end_equity,
                    "return_pct": (end_equity / max(start_equity, 1e-9) - 1.0) * 100.0,
                    "max_dd_pct": s650._max_drawdown_pct(equity),
                    "trade_count": float(month_frame["trade_count"].sum()),
                    "slippage": float(month_frame["total_slippage"].sum()),
                    "max_broker10_margin_to_equity_pct": float(
                        month_frame["broker10_margin_to_equity_pct"].max()
                    ),
                }
            )
    return pd.DataFrame(rows)


def _current_positions(positions: pd.DataFrame, metadata: dict[str, Any], latest_date: pd.Timestamp) -> pd.DataFrame:
    columns = [
        "variant",
        "label",
        "date",
        "vt_symbol",
        "product_vt_symbol",
        "direction",
        "end_pos",
        "close_price",
        "margin_exact",
    ]
    frame = positions.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame = frame[frame["date"].eq(latest_date)].copy()
    if frame.empty:
        return pd.DataFrame(columns=columns)
    for column in ["end_pos", "close_price"]:
        frame[column] = pd.to_numeric(frame.get(column, 0.0), errors="coerce").fillna(0.0)
    frame = frame[frame["end_pos"].abs().gt(0)].copy()
    if frame.empty:
        return pd.DataFrame(columns=columns)
    frame["size"] = frame["vt_symbol"].map(metadata["sizes"]).fillna(1.0).astype(float)
    frame["margin_ratio"] = frame["vt_symbol"].map(metadata["margin_ratios"]).fillna(0.15).astype(float)
    frame["product_vt_symbol"] = frame["vt_symbol"].map(s513._product_from_contract)
    frame["direction"] = np.where(frame["end_pos"].gt(0), "long", "short")
    frame["margin_exact"] = (
        frame["end_pos"].abs()
        * frame["close_price"].clip(lower=0.0)
        * frame["size"]
        * frame["margin_ratio"]
    )
    return frame[columns].sort_values(["variant", "margin_exact"], ascending=[True, False])


def _run_selected_variant(
    spec: s653.ForcedVariant,
    metadata: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    original_start = s653.s517.START_DT
    try:
        s653.s517.START_DT = ANALYSIS_START
        return s653._run_variant(spec, metadata)
    finally:
        s653.s517.START_DT = original_start


def _write_report(
    summary: pd.DataFrame,
    cost: pd.DataFrame,
    monthly: pd.DataFrame,
    current_positions: pd.DataFrame,
    events: pd.DataFrame,
    forced_summary: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    current = summary[summary["variant"].eq(CURRENT_VARIANT)].copy()
    baseline = summary[summary["variant"].eq(BASELINE_VARIANT)].copy()
    lines = [
        "# Stage658 Stage653 2026 年初至今影子盘",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        f"- line_id：`{LINE_ID}`",
        f"- 统计区间：`{ANALYSIS_START.date()}` 至 `{ANALYSIS_END.date()}`；结束日来自当前仓库 `qmt_universe.END_DT`。",
        "- 性质：只读影子盘绩效；不连接 CTP，不读取账户，不调用下单。",
        "- 当前候选：`stage526_200k_force95_to80_largest_margin_r080_pc25_maxpos4`。",
        "- 对照：`stage526_200k_allin_r080_pc25_maxpos4`，仅用于理解收益牺牲，不作为今晚执行候选。",
        "- 运行前过拟合判断：否。固定版本冷启动复算，没有新增参数。",
        "- 运行前继续价值判断：是。它直接检验当前准实盘候选在 2026 年内样本的资金曲线、回撤和保证金压力。",
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
                    "forced_margin_deleverage_count",
                    "forced_margin_deleverage_closed_volume",
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
        "## 强制减仓事件",
        "",
        _md_table(forced_summary),
        "",
        "## 关键风险日",
        "",
        _md_table(events, max_rows=30),
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
        f"- 当前候选：{current.to_dict(orient='records')[0] if not current.empty else {}}",
        f"- all-in 对照：{baseline.to_dict(orient='records')[0] if not baseline.empty else {}}",
        f"- 决策：`{decision['decision']}`。",
        "- 本阶段只回答年内影子绩效；真实执行仍要等夜盘前 CTP fresh snapshot、信号计划和下单闸门。",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    metadata = s513._metadata()
    identity_map = s653.s519._product_identity_cluster_map(metadata)
    specs = [spec for spec in s653._variants(identity_map) if spec.capital.variant in SELECTED_VARIANTS]
    spec_map = {spec.capital.variant: spec for spec in specs}

    daily_frames: list[pd.DataFrame] = []
    position_frames: list[pd.DataFrame] = []
    product_frames: list[pd.DataFrame] = []
    forced_event_frames: list[pd.DataFrame] = []

    for spec in specs:
        print(f"[stage658] running {spec.capital.variant}", flush=True)
        daily, positions, _, forced_events = _run_selected_variant(spec, metadata)
        daily["account_capital"] = spec.capital.account_capital
        daily["c3_capital"] = spec.capital.c3_capital
        daily["profile"] = spec.profile
        positions["account_capital"] = spec.capital.account_capital
        positions["c3_capital"] = spec.capital.c3_capital
        c3_margin_daily, product_margin = s513._position_margin(positions, metadata)
        combined = s650._combine_daily(daily, c3_margin_daily, spec.capital)
        combined["profile"] = spec.profile
        for column in [
            "forced_margin_deleverage_count",
            "forced_margin_deleverage_closed_volume",
            "forced_margin_deleverage_ratio",
            "forced_margin_deleverage_max_observed_ratio",
        ]:
            combined[column] = daily[column].iloc[0] if column in daily.columns and not daily.empty else 0
        daily_frames.append(combined)
        position_frames.append(positions)
        product_frames.append(product_margin)
        if not forced_events.empty:
            forced_event_frames.append(forced_events)

    combo_daily = pd.concat(daily_frames, ignore_index=True, sort=False)
    positions_all = pd.concat(position_frames, ignore_index=True, sort=False)
    product_margin_all = pd.concat(product_frames, ignore_index=True, sort=False)
    forced_events_all = (
        pd.concat(forced_event_frames, ignore_index=True, sort=False) if forced_event_frames else pd.DataFrame()
    )
    forced_summary = s653._forced_summary(specs, forced_events_all)

    summary_rows: list[dict[str, Any]] = []
    cost_rows: list[dict[str, Any]] = []
    for variant, frame in combo_daily.groupby("variant", sort=False):
        spec = spec_map[variant]
        for cost_multiplier in s653.COST_MULTIPLIERS:
            row = s653._metrics_with_profile(frame, spec, cost_multiplier)
            cost_rows.append(row)
            if cost_multiplier == 1.0:
                summary_rows.append(row)
    summary = pd.DataFrame(summary_rows)
    cost = pd.DataFrame(cost_rows)
    summary, cost = s653._add_retention(summary, cost)
    monthly = _monthly_returns(combo_daily)
    events = s650._event_days(combo_daily, product_margin_all)
    latest_date = pd.to_datetime(combo_daily["date"]).max().normalize()
    current_positions = _current_positions(positions_all, metadata, latest_date)

    current_row = summary[summary["variant"].eq(CURRENT_VARIANT)].to_dict(orient="records")
    baseline_row = summary[summary["variant"].eq(BASELINE_VARIANT)].to_dict(orient="records")
    decision = {
        "stage": "Stage358",
        "script_stage": "Stage658",
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "analysis_start": ANALYSIS_START.date().isoformat(),
        "analysis_end": ANALYSIS_END.date().isoformat(),
        "latest_available_data_date": latest_date.date().isoformat(),
        "current_variant": current_row[0] if current_row else {},
        "baseline_variant": baseline_row[0] if baseline_row else {},
        "decision": "stage653_2026_ytd_shadow_measured_no_order_api",
        "execution_scope": "read-only backtest/shadow performance only; no CTP connection and no order API call",
        "data_limitation": "Repository qmt_universe.END_DT currently stops at 2026-04-30.",
    }

    combo_daily.to_csv(DAILY_PATH, index=False, encoding="utf-8-sig")
    positions_all.to_csv(POSITIONS_PATH, index=False, encoding="utf-8-sig")
    product_margin_all.to_csv(PRODUCT_MARGIN_PATH, index=False, encoding="utf-8-sig")
    monthly.to_csv(MONTHLY_PATH, index=False, encoding="utf-8-sig")
    current_positions.to_csv(CURRENT_POSITIONS_PATH, index=False, encoding="utf-8-sig")
    events.to_csv(EVENT_PATH, index=False, encoding="utf-8-sig")
    forced_summary.to_csv(FORCED_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    if not forced_events_all.empty:
        forced_events_all.to_csv(FORCED_EVENTS_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    cost.to_csv(COST_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_report(summary, cost, monthly, current_positions, events, forced_summary, decision)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
