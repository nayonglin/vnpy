from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import analyze_qmt_roll_stage501_asymmetric_entry_exit_execution as s501
import analyze_qmt_roll_stage513_stage208_exact_position_margin_audit as s513
import analyze_qmt_roll_stage650_stage526_200k_capital_reality_check as s650
import analyze_qmt_roll_stage653_stage526_200k_forced_margin_deleverage as s653
import analyze_qmt_roll_stage748_half_risk_no_streak_500k as s748
import analyze_qmt_roll_stage751_cash_reserve_bucket_monthly_start as s751
import analyze_qmt_roll_stage757_c50_oi_confirm_risk_restore as s757
import analyze_qmt_roll_stage764_stage757_cash_reserve_45w5w_monthly_start as s764


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

MODEL_TAG = "stage766_2019_start_stage757_stage764_v1"
OUTPUT_PREFIX = "qmt_roll_stage766_2019_start_stage757_stage764"
LINE_ID = "futures_trend_2019_data_extension"

ANALYSIS_END = pd.Timestamp("2026-05-29")
STARTS = (
    pd.Timestamp("2019-01-01"),
    pd.Timestamp("2020-01-01"),
)
STAGE757_ARM = "A_stage757_c50_oi_restore"
STAGE764_ARM = "B_stage764_stage757_cash_reserve_45w5w"

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
CURVES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv"
COST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cost_stress_{MODEL_TAG}.csv"
SOURCE_COUNTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_source_counts_{MODEL_TAG}.csv"
RESERVE_EVENTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_reserve_events_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_equity_curves_{MODEL_TAG}.png"


def _json_safe(value: Any) -> Any:
    return s650._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s650._md_table(frame, max_rows=max_rows)


def _window_name(start: pd.Timestamp) -> str:
    return f"start_{start.strftime('%Y_%m')}"


def _window_label(start: pd.Timestamp) -> str:
    return f"{start.strftime('%Y-%m')} independent start to {ANALYSIS_END.strftime('%Y-%m-%d')}"


def _preload_for_start(start: pd.Timestamp) -> pd.Timestamp:
    if start < pd.Timestamp("2020-01-01"):
        return (start - pd.Timedelta(days=365)).normalize()
    return pd.Timestamp(s653.s517.PRELOAD_START_DT).normalize()


def _run_stage757_window(
    *,
    start: pd.Timestamp,
    metadata: dict[str, Any],
    spec: s653.ForcedVariant,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    original_start = s653.s517.START_DT
    original_end = s653.s517.END_DT
    original_preload = s653.s517.PRELOAD_START_DT
    try:
        s653.s517.START_DT = start.to_pydatetime()
        s653.s517.END_DT = ANALYSIS_END.to_pydatetime()
        s653.s517.PRELOAD_START_DT = _preload_for_start(start).to_pydatetime()
        daily, positions, usage, forced_events = s653._run_variant(replace(spec), metadata)
    finally:
        s653.s517.START_DT = original_start
        s653.s517.END_DT = original_end
        s653.s517.PRELOAD_START_DT = original_preload

    daily["account_capital"] = spec.capital.account_capital
    daily["c3_capital"] = spec.capital.c3_capital
    daily["profile"] = spec.profile
    positions["account_capital"] = spec.capital.account_capital
    positions["c3_capital"] = spec.capital.c3_capital
    margin_daily, _product_margin = s513._position_margin(positions, metadata)
    combined = s650._combine_daily(daily, margin_daily, spec.capital)
    combined["profile"] = spec.profile
    for column in [
        "forced_margin_deleverage_count",
        "forced_margin_deleverage_closed_volume",
        "forced_margin_deleverage_ratio",
        "forced_margin_deleverage_max_observed_ratio",
    ]:
        combined[column] = daily[column].iloc[0] if column in daily.columns and not daily.empty else 0

    forced_events = forced_events.copy()
    if not forced_events.empty:
        forced_events["variant"] = spec.capital.variant
        forced_events["label"] = spec.capital.label
        forced_events["profile"] = spec.profile
    return combined, forced_events, usage


def _run_stage764_window(
    *,
    start: pd.Timestamp,
    metadata: dict[str, Any],
    spec: s653.ForcedVariant,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    s764._patch_stage751_cash_bucket_globals()
    original_preload = s751.s653.s517.PRELOAD_START_DT
    try:
        s751.s653.s517.PRELOAD_START_DT = _preload_for_start(start).to_pydatetime()
        frame, forced_events, reserve_events = s751._run_cash_reserve_variant(
            spec=spec,
            metadata=metadata,
            analysis_start=start,
            analysis_end=ANALYSIS_END,
        )
    finally:
        s751.s653.s517.PRELOAD_START_DT = original_preload
    return frame, forced_events, reserve_events


def _row_and_curve(
    frame: pd.DataFrame,
    *,
    spec: s653.ForcedVariant,
    start: pd.Timestamp,
    arm: str,
    metric_kind: str,
    forced_events: pd.DataFrame,
) -> tuple[dict[str, Any], pd.DataFrame, list[dict[str, Any]]]:
    if metric_kind == "cash_reserve":
        row, curve, costs = s751._metric_row_cash(
            frame,
            spec=spec,
            window_name=_window_name(start),
            window_label=_window_label(start),
            window_group="start_comparison",
            forced_events=forced_events,
        )
    else:
        row, curve, costs = s748._metric_row(
            frame,
            spec=spec,
            window_name=_window_name(start),
            window_label=_window_label(start),
            window_group="start_comparison",
            forced_events=forced_events,
        )
    row["arm"] = arm
    row["requested_start_month"] = start.strftime("%Y-%m")
    row["preload_start"] = _preload_for_start(start).date().isoformat()
    row["analysis_end_requested"] = ANALYSIS_END.date().isoformat()
    row["execution_proxy_note"] = "2019 entries use daily-next-open fallback until Stage149 proxy starts in 2020"
    curve["arm"] = arm
    curve["requested_start_month"] = start.strftime("%Y-%m")
    curve["preload_start"] = _preload_for_start(start).date().isoformat()
    for cost in costs:
        cost["arm"] = arm
        cost["requested_start_month"] = start.strftime("%Y-%m")
        cost["preload_start"] = _preload_for_start(start).date().isoformat()
    return row, curve, costs


def _source_counts(usage: pd.DataFrame, *, arm: str, start: pd.Timestamp) -> pd.DataFrame:
    if usage.empty:
        return pd.DataFrame()
    frame = usage.copy()
    frame["signal_date"] = pd.to_datetime(frame.get("signal_date"), errors="coerce").dt.normalize()
    frame["signal_year"] = frame["signal_date"].dt.year.fillna(0).astype(int)
    frame["price_source"] = frame.get("price_source", "").astype(str)
    out = (
        frame.groupby(["price_source", "signal_year"], as_index=False)
        .size()
        .rename(columns={"size": "trade_count"})
        .sort_values(["signal_year", "price_source"])
    )
    out["arm"] = arm
    out["requested_start_month"] = start.strftime("%Y-%m")
    out["is_fallback"] = out["price_source"].str.startswith("fallback").astype(int)
    return out


def _proxy_coverage() -> dict[str, Any]:
    _close_map, open_map = s501._seed_proxy_maps()
    signal_dates = [key[0] for key in open_map]
    related_2019 = [key for key in open_map if key[0].year == 2019 or key[1].year == 2019]
    return {
        "open_proxy_total": int(len(open_map)),
        "open_proxy_2019_related": int(len(related_2019)),
        "open_proxy_first_signal_date": min(signal_dates).date().isoformat() if signal_dates else "",
        "open_proxy_last_signal_date": max(signal_dates).date().isoformat() if signal_dates else "",
    }


def _ai_coverage() -> dict[str, Any]:
    overrides = s513._c3_overrides(pd.Timestamp("2019-01-01").to_pydatetime())
    path = Path(str(overrides.get("ai_product_pool_eligibility_path", "") or ""))
    strategy = str(overrides.get("ai_product_pool_strategy", "") or "")
    if not path.exists():
        return {"ai_path": str(path), "ai_strategy": strategy, "ai_rows": 0}
    df = pd.read_csv(path)
    df = df[df["strategy"].astype(str).eq(strategy)].copy()
    if df.empty:
        return {"ai_path": str(path), "ai_strategy": strategy, "ai_rows": 0}
    df["eval_date"] = pd.to_datetime(df["eval_date"], errors="coerce").dt.normalize()
    return {
        "ai_path": str(path),
        "ai_strategy": strategy,
        "ai_rows": int(len(df)),
        "ai_first_eval_date": df["eval_date"].min().date().isoformat(),
        "ai_last_eval_date": df["eval_date"].max().date().isoformat(),
        "ai_eval_date_count": int(df["eval_date"].nunique()),
    }


def _plot_curves(curves: pd.DataFrame) -> None:
    data = curves.copy()
    data["date"] = pd.to_datetime(data["date"], errors="coerce").dt.normalize()
    data["label_for_plot"] = data["arm"].astype(str) + " " + data["requested_start_month"].astype(str)
    fig, axes = plt.subplots(2, 1, figsize=(16, 9), sharex=True, gridspec_kw={"height_ratios": [2.2, 1]})
    for label, group in data.groupby("label_for_plot", sort=False):
        group = group.sort_values("date")
        axes[0].plot(group["date"], group["account_equity"], linewidth=1.8, label=label)
        axes[1].plot(group["date"], group["drawdown_pct"], linewidth=1.2, label=label)
    axes[0].set_title("Stage766 2019 start feasibility: Stage757 vs Stage764")
    axes[0].set_ylabel("Account equity")
    axes[0].grid(alpha=0.25)
    axes[0].legend(loc="upper left", fontsize=8)
    axes[1].set_ylabel("Drawdown %")
    axes[1].set_xlabel("Date")
    axes[1].grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=170)
    plt.close(fig)


def _write_report(summary: pd.DataFrame, source_counts: pd.DataFrame, decision: dict[str, Any]) -> None:
    view_cols = [
        "arm",
        "requested_start_month",
        "end_equity",
        "total_return_pct",
        "max_dd_pct",
        "sharpe",
        "total_trade_count",
        "total_slippage",
        "max_broker10_margin_to_equity_pct",
        "reserve_deployed_end",
        "reserve_remaining_end",
    ]
    visible = [col for col in view_cols if col in summary.columns]
    lines = [
        "# Stage766 2019 起点可回测性单臂验证",
        "",
        f"- line_id：`{LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        f"- 终点：`{ANALYSIS_END.date()}`",
        "- 本阶段只读回测，不修改正式配置，不写数据库，不连接 CTP。",
        "",
        "## 数据和执行 caveat",
        "",
        f"- next-real-open proxy 覆盖：`{decision['proxy_coverage']}`",
        f"- AI coverage：`{decision['ai_coverage']}`",
        "- 2019 年内没有 Stage149 next-real-open 分钟代理，成交价格会使用 daily next open fallback；因此 2019 起点可作为路径敏感性验证，但不能和 2020 后执行代理完全等权。",
        "",
        "## 结果摘要",
        "",
        _md_table(summary[visible], max_rows=20),
        "",
        "## 成交价格来源",
        "",
        _md_table(source_counts, max_rows=80),
        "",
        "## 结论",
        "",
        f"- 决策：`{decision['decision']}`",
        f"- 过拟合判断：`{decision['overfit_judgment']}`",
        f"- 继续价值：`{decision['continue_value']}`",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    metadata = s513._metadata()
    stage757_spec = s757._candidate_spec(metadata)
    stage764_spec = s764._cash_reserve_spec(metadata)

    summary_rows: list[dict[str, Any]] = []
    curve_frames: list[pd.DataFrame] = []
    cost_rows: list[dict[str, Any]] = []
    source_frames: list[pd.DataFrame] = []
    reserve_frames: list[pd.DataFrame] = []

    for start in STARTS:
        frame757, forced757, usage757 = _run_stage757_window(start=start, metadata=metadata, spec=stage757_spec)
        row757, curve757, costs757 = _row_and_curve(
            frame757,
            spec=stage757_spec,
            start=start,
            arm=STAGE757_ARM,
            metric_kind="normal",
            forced_events=forced757,
        )
        summary_rows.append(row757)
        curve_frames.append(curve757)
        cost_rows.extend(costs757)
        source = _source_counts(usage757, arm=STAGE757_ARM, start=start)
        if not source.empty:
            source_frames.append(source)

        frame764, forced764, reserve764 = _run_stage764_window(start=start, metadata=metadata, spec=stage764_spec)
        row764, curve764, costs764 = _row_and_curve(
            frame764,
            spec=stage764_spec,
            start=start,
            arm=STAGE764_ARM,
            metric_kind="cash_reserve",
            forced_events=forced764,
        )
        summary_rows.append(row764)
        curve_frames.append(curve764)
        cost_rows.extend(costs764)
        if not reserve764.empty:
            reserve_frames.append(reserve764)

    summary = pd.DataFrame(summary_rows)
    curves = pd.concat(curve_frames, ignore_index=True) if curve_frames else pd.DataFrame()
    costs = pd.DataFrame(cost_rows)
    source_counts = pd.concat(source_frames, ignore_index=True) if source_frames else pd.DataFrame()
    reserve_events = pd.concat(reserve_frames, ignore_index=True) if reserve_frames else pd.DataFrame()

    _plot_curves(curves)

    decision = {
        "stage": "Stage766",
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "decision": "2019_start_backtest_completed_with_execution_proxy_caveat",
        "analysis_end": ANALYSIS_END.date().isoformat(),
        "arms": [STAGE757_ARM, STAGE764_ARM],
        "starts": [start.date().isoformat() for start in STARTS],
        "proxy_coverage": _proxy_coverage(),
        "ai_coverage": _ai_coverage(),
        "overfit_judgment": "low: strategy parameters are frozen; only start date and preload horizon are changed",
        "continue_value": "yes: useful for start-date path dependency; next step is proxy-quality and 2019 attribution, not parameter tuning",
        "outputs": {
            "summary": str(SUMMARY_PATH),
            "curves": str(CURVES_PATH),
            "cost": str(COST_PATH),
            "source_counts": str(SOURCE_COUNTS_PATH),
            "reserve_events": str(RESERVE_EVENTS_PATH),
            "chart": str(CHART_PATH),
            "report": str(REPORT_PATH),
            "decision": str(DECISION_PATH),
        },
    }

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    curves.to_csv(CURVES_PATH, index=False, encoding="utf-8-sig")
    costs.to_csv(COST_PATH, index=False, encoding="utf-8-sig")
    source_counts.to_csv(SOURCE_COUNTS_PATH, index=False, encoding="utf-8-sig")
    reserve_events.to_csv(RESERVE_EVENTS_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_report(summary, source_counts, decision)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
