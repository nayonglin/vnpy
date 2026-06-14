from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import replace
from datetime import datetime
import json
import os
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import analyze_qmt_roll_stage513_stage208_exact_position_margin_audit as s513
import analyze_qmt_roll_stage650_stage526_200k_capital_reality_check as s650
import analyze_qmt_roll_stage825_stage819_intraday_rule_forensics as s825
import analyze_qmt_roll_stage827_stage819_intraday_c2_engine_ac as s827
import analyze_qmt_roll_stage830_stage827_c2_broker10_margin_cap as s830
import qmt_roll_official_candidate_stage819_30w_config as stage819_cfg


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

LINE_ID = "futures_trend_stage819_intraday_rules"
STAGE = "Stage831"
MODEL_TAG = "stage831_stage830_c4_yearly_robustness_v1"
OUTPUT_PREFIX = "qmt_roll_stage831_stage830_c4_yearly_robustness"

BASE_ARM = s830.BASE_ARM
CAP_ARM = s830.CAP_ARM
DATA_END = pd.Timestamp("2026-05-29")
YEAR_STARTS = tuple(pd.date_range("2018-01-01", "2026-01-01", freq="YS"))
MAX_WORKERS = max(1, min(3, int(os.environ.get("STAGE831_MAX_WORKERS", "2"))))

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
CURVES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv"
COMPARISON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_comparison_{MODEL_TAG}.csv"
AGGREGATE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_aggregate_{MODEL_TAG}.csv"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
METRIC_CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_metric_chart_{MODEL_TAG}.png"
SELECTED_CURVES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_selected_curves_{MODEL_TAG}.png"

_WORKER_STATE: dict[str, Any] = {}


def _json_safe(value: Any) -> Any:
    return s650._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s650._md_table(frame, max_rows=max_rows)


def _month_text(value: pd.Timestamp) -> str:
    return pd.Timestamp(value).strftime("%Y-%m")


def _ensure_worker_state() -> dict[str, Any]:
    if _WORKER_STATE:
        return _WORKER_STATE
    metadata = s513._metadata()
    vt_symbols = set(str(item) for item in metadata["vt_symbols"])
    minute_bars = s825._load_minute_bars(vt_symbols)
    s827._GLOBAL_MINUTE_BY_SYMBOL = s825._minute_groups(minute_bars)
    _WORKER_STATE["metadata"] = metadata
    return _WORKER_STATE


def _profile_for_arm(metadata: dict[str, Any], arm: str, start: pd.Timestamp) -> dict[str, Any]:
    start_text = _month_text(start)
    if arm == BASE_ARM:
        profile = s827._profile(metadata, enabled=False)
        label = f"Stage831 Stage819 baseline yearly {start_text}"
        note = "Stage831 yearly robustness A arm; Stage819 baseline with C2 and broker10 cap disabled."
    elif arm == CAP_ARM:
        profile = s830._cap_profile(metadata)
        label = f"Stage831 Stage830 C4 yearly {start_text}"
        note = (
            "Stage831 yearly robustness C arm; Stage827 C2 intraday stop plus frozen Stage830 "
            "broker10 100pct flat-entry margin cap."
        )
    else:
        raise ValueError(f"unknown arm: {arm}")

    spec = profile["spec"]
    capital = replace(
        spec.capital,
        variant=f"stage831_{arm}_{start_text.replace('-', '_')}",
        label=label,
        note=f"{spec.capital.note} | {note}",
    )
    result = dict(profile)
    result["spec"] = replace(spec, capital=capital, profile=result["profile"])
    return result


def _run_one(task: tuple[str, str]) -> tuple[dict[str, Any], pd.DataFrame]:
    arm, start_text = task
    state = _ensure_worker_state()
    metadata = state["metadata"]
    start = pd.Timestamp(start_text).normalize()
    original_start = s827.START
    original_end = s827.END
    try:
        s827.START = start
        s827.END = DATA_END
        profile = _profile_for_arm(metadata, arm, start)
        combined, frames = s827._run_profile(profile, metadata)
        summary, curve = s827._metric(profile, combined)
        row = summary.iloc[0].to_dict()
        row["arm"] = arm
        row["requested_start_month"] = start_text
        row["start_month"] = start_text
        row["start_year"] = int(start.year)
        row["analysis_start"] = start.strftime("%Y-%m-%d")
        row["analysis_end"] = DATA_END.strftime("%Y-%m-%d")

        trade_events = frames.get("trade_events", pd.DataFrame()).copy()
        intraday_events = frames.get("intraday_events", pd.DataFrame()).copy()
        if not trade_events.empty and "reason" in trade_events.columns:
            reasons = trade_events["reason"].astype(str)
            cap_events = trade_events[reasons.str.startswith("broker10_margin_cap", na=False)].copy()
        else:
            cap_events = pd.DataFrame()
        if not cap_events.empty:
            reduced = pd.to_numeric(cap_events.get("reduced_volume", 0), errors="coerce").fillna(0.0)
            row["stage830_cap_event_count"] = int(len(cap_events))
            row["stage830_cap_block_count"] = int(cap_events["reason"].astype(str).eq("broker10_margin_cap_block").sum())
            row["stage830_cap_reduced_volume"] = float(reduced.sum())
        else:
            row["stage830_cap_event_count"] = 0
            row["stage830_cap_block_count"] = 0
            row["stage830_cap_reduced_volume"] = 0.0
        if not intraday_events.empty:
            row["stage827_intraday_event_count"] = int(len(intraday_events))
            row["stage827_intraday_event_volume"] = float(
                pd.to_numeric(intraday_events.get("volume", 0), errors="coerce").fillna(0.0).sum()
            )
        else:
            row["stage827_intraday_event_count"] = 0
            row["stage827_intraday_event_volume"] = 0.0

        curve = curve.copy()
        curve["arm"] = arm
        curve["requested_start_month"] = start_text
        curve["start_month"] = start_text
        curve["start_year"] = int(start.year)
        curve["analysis_start"] = start.strftime("%Y-%m-%d")
        curve["analysis_end"] = DATA_END.strftime("%Y-%m-%d")
        return row, curve
    finally:
        s827.START = original_start
        s827.END = original_end


def _comparison(summary: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    metric_cols = [
        "end_equity",
        "total_return_pct",
        "max_dd_pct",
        "sharpe",
        "total_slippage",
        "total_trade_count",
        "nonzero_daily_win_rate_pct",
        "max_broker10_margin_to_equity_pct",
        "p95_broker10_margin_to_equity_pct",
        "days_over_100pct",
        "days_over_90pct",
        "dd40_fail",
        "dd50_fail",
        "stage827_intraday_event_count",
        "stage827_intraday_event_volume",
        "stage830_cap_event_count",
        "stage830_cap_block_count",
        "stage830_cap_reduced_volume",
    ]
    for start_month, group in summary.groupby("start_month", sort=True):
        indexed = group.set_index("arm")
        if BASE_ARM not in indexed.index or CAP_ARM not in indexed.index:
            continue
        base = indexed.loc[BASE_ARM]
        cap = indexed.loc[CAP_ARM]
        item: dict[str, Any] = {
            "start_month": start_month,
            "start_year": int(cap["start_year"]),
            "analysis_start": str(cap["analysis_start"]),
            "analysis_end": str(cap["analysis_end"]),
        }
        for column in metric_cols:
            item[f"{column}_A"] = float(pd.to_numeric(pd.Series([base.get(column, np.nan)]), errors="coerce").iloc[0])
            item[f"{column}_C4"] = float(pd.to_numeric(pd.Series([cap.get(column, np.nan)]), errors="coerce").iloc[0])
        item["end_equity_delta_C4_vs_A"] = item["end_equity_C4"] - item["end_equity_A"]
        item["total_return_delta_C4_vs_A_pp"] = item["total_return_pct_C4"] - item["total_return_pct_A"]
        item["max_dd_delta_C4_vs_A_pp"] = item["max_dd_pct_C4"] - item["max_dd_pct_A"]
        item["sharpe_delta_C4_vs_A"] = item["sharpe_C4"] - item["sharpe_A"]
        item["slippage_delta_C4_vs_A"] = item["total_slippage_C4"] - item["total_slippage_A"]
        item["trade_count_delta_C4_vs_A"] = item["total_trade_count_C4"] - item["total_trade_count_A"]
        item["broker10_peak_delta_C4_vs_A_pp"] = (
            item["max_broker10_margin_to_equity_pct_C4"] - item["max_broker10_margin_to_equity_pct_A"]
        )
        item["C4_return_win"] = int(item["total_return_pct_C4"] > item["total_return_pct_A"])
        item["C4_dd_win"] = int(item["max_dd_pct_C4"] > item["max_dd_pct_A"])
        item["C4_sharpe_win"] = int(item["sharpe_C4"] > item["sharpe_A"])
        item["C4_double_win"] = int(item["C4_return_win"] and item["C4_dd_win"])
        item["C4_broker100_fail"] = int(item["max_broker10_margin_to_equity_pct_C4"] > 100.0)
        item["A_broker100_fail"] = int(item["max_broker10_margin_to_equity_pct_A"] > 100.0)
        rows.append(item)
    return pd.DataFrame(rows).sort_values("start_month").reset_index(drop=True)


def _aggregate(comparison: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    buckets = {
        "all": comparison.index == comparison.index,
        "mature_ex_2026": comparison["start_month"].astype(str).lt("2026-01"),
        "post_2020": comparison["start_month"].astype(str).ge("2020-01"),
    }
    for bucket, mask in buckets.items():
        frame = comparison[mask].copy()
        if frame.empty:
            continue
        rows.append(
            {
                "bucket": bucket,
                "window_count": int(len(frame)),
                "C4_return_win_count": int(frame["C4_return_win"].sum()),
                "C4_dd_win_count": int(frame["C4_dd_win"].sum()),
                "C4_sharpe_win_count": int(frame["C4_sharpe_win"].sum()),
                "C4_double_win_count": int(frame["C4_double_win"].sum()),
                "C4_positive_count": int((frame["total_return_pct_C4"] > 0.0).sum()),
                "A_positive_count": int((frame["total_return_pct_A"] > 0.0).sum()),
                "median_return_delta_pp": float(frame["total_return_delta_C4_vs_A_pp"].median()),
                "p10_return_delta_pp": float(frame["total_return_delta_C4_vs_A_pp"].quantile(0.10)),
                "median_dd_delta_pp": float(frame["max_dd_delta_C4_vs_A_pp"].median()),
                "p10_dd_delta_pp": float(frame["max_dd_delta_C4_vs_A_pp"].quantile(0.10)),
                "median_sharpe_delta": float(frame["sharpe_delta_C4_vs_A"].median()),
                "A_dd40_fail_count": int(frame["dd40_fail_A"].sum()),
                "C4_dd40_fail_count": int(frame["dd40_fail_C4"].sum()),
                "A_dd50_fail_count": int(frame["dd50_fail_A"].sum()),
                "C4_dd50_fail_count": int(frame["dd50_fail_C4"].sum()),
                "A_broker100_fail_count": int(frame["A_broker100_fail"].sum()),
                "C4_broker100_fail_count": int(frame["C4_broker100_fail"].sum()),
                "A_worst_dd_pct": float(frame["max_dd_pct_A"].min()),
                "C4_worst_dd_pct": float(frame["max_dd_pct_C4"].min()),
                "A_min_return_pct": float(frame["total_return_pct_A"].min()),
                "C4_min_return_pct": float(frame["total_return_pct_C4"].min()),
                "C4_total_intraday_events": int(frame["stage827_intraday_event_count_C4"].sum()),
                "C4_total_intraday_volume": float(frame["stage827_intraday_event_volume_C4"].sum()),
                "C4_total_cap_events": int(frame["stage830_cap_event_count_C4"].sum()),
                "C4_total_cap_reduced_volume": float(frame["stage830_cap_reduced_volume_C4"].sum()),
            }
        )
    return pd.DataFrame(rows)


def _plot_metric_chart(comparison: pd.DataFrame) -> None:
    if comparison.empty:
        return
    x = np.arange(len(comparison))
    labels = comparison["start_month"].astype(str).tolist()
    fig, axes = plt.subplots(3, 1, figsize=(15, 11), sharex=True, constrained_layout=True)
    axes[0].bar(x - 0.18, comparison["total_return_pct_A"], width=0.36, label="A baseline", color="#2563eb")
    axes[0].bar(x + 0.18, comparison["total_return_pct_C4"], width=0.36, label="C4", color="#16a34a")
    axes[0].set_title("Yearly starts total return pct")
    axes[1].bar(x - 0.18, comparison["max_dd_pct_A"], width=0.36, label="A baseline", color="#2563eb")
    axes[1].bar(x + 0.18, comparison["max_dd_pct_C4"], width=0.36, label="C4", color="#16a34a")
    axes[1].set_title("Yearly starts max drawdown pct")
    axes[2].bar(x - 0.18, comparison["max_broker10_margin_to_equity_pct_A"], width=0.36, label="A baseline", color="#2563eb")
    axes[2].bar(x + 0.18, comparison["max_broker10_margin_to_equity_pct_C4"], width=0.36, label="C4", color="#16a34a")
    axes[2].axhline(100.0, color="#dc2626", linestyle="--", linewidth=1.0, label="broker10 100")
    axes[2].set_title("Yearly starts max broker10 margin/equity pct")
    axes[2].set_xticks(x)
    axes[2].set_xticklabels(labels, rotation=30, ha="right")
    for ax in axes:
        ax.grid(True, axis="y", alpha=0.25)
        ax.legend(loc="best")
    fig.savefig(METRIC_CHART_PATH, dpi=160)
    plt.close(fig)


def _plot_selected_curves(curves: pd.DataFrame) -> None:
    if curves.empty:
        return
    selected = {"2018-01", "2020-01", "2022-01", "2024-01", "2026-01"}
    data = curves[curves["start_month"].astype(str).isin(selected)].copy()
    if data.empty:
        return
    data["date"] = pd.to_datetime(data["date"], errors="coerce", format="mixed")
    fig, axes = plt.subplots(len(selected), 1, figsize=(15, 13), sharex=False, constrained_layout=True)
    axes_list = list(np.atleast_1d(axes))
    color_map = {BASE_ARM: "#2563eb", CAP_ARM: "#16a34a"}
    for ax, start_month in zip(axes_list, sorted(selected), strict=False):
        frame = data[data["start_month"].astype(str).eq(start_month)].copy()
        for arm, group in frame.groupby("arm"):
            group = group.sort_values("date")
            equity_col = "account_equity" if "account_equity" in group.columns else "rebased_equity"
            y = pd.to_numeric(group[equity_col], errors="coerce")
            y = y / y.iloc[0] if len(y) and y.iloc[0] else y
            ax.plot(group["date"], y, color=color_map.get(str(arm), "#111827"), label="A" if arm == BASE_ARM else "C4")
        ax.set_title(start_month)
        ax.grid(True, alpha=0.25)
        ax.legend(loc="best")
    fig.suptitle("Stage831 selected yearly-start NAV curves", fontsize=15)
    fig.savefig(SELECTED_CURVES_PATH, dpi=160)
    plt.close(fig)


def _decision(aggregate: pd.DataFrame) -> dict[str, Any]:
    mature = aggregate[aggregate["bucket"].eq("mature_ex_2026")].iloc[0].to_dict()
    all_row = aggregate[aggregate["bucket"].eq("all")].iloc[0].to_dict()
    mature_count = int(mature["window_count"])
    robust_core = (
        int(mature["C4_return_win_count"]) >= 5
        and int(mature["C4_dd_win_count"]) >= 5
        and int(mature["C4_double_win_count"]) >= 4
        and int(mature["C4_dd50_fail_count"]) <= int(mature["A_dd50_fail_count"])
    )
    broker_tail = int(mature["C4_broker100_fail_count"]) > int(mature["A_broker100_fail_count"])
    decision_label = (
        "stage831_c4_internal_candidate_needs_official_comparison_broker_tail_warning"
        if robust_core and broker_tail
        else "stage831_c4_internal_candidate_continue"
        if robust_core
        else "stage831_c4_not_robust_enough"
    )
    return {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "source_candidate": stage819_cfg.OFFICIAL_CANDIDATE_STAGE819_30W_VERSION,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "formal_ab_triggered": False,
        "strategy_changed": False,
        "ctp_connected": False,
        "order_api_called": False,
        "year_start_count": len(YEAR_STARTS),
        "mature_window_count": mature_count,
        "arms": {"A": BASE_ARM, "C4": CAP_ARM},
        "frozen_parameters": {
            "stage827_intraday_c2_stop_r": s827.STOP_R,
            "stage827_intraday_c2_confirm_r": s827.CONFIRM_R,
            "stage830_broker_margin_multiplier": s830.BROKER_MARGIN_MULTIPLIER,
            "stage830_projected_broker10_margin_to_equity_cap": s830.PROJECTED_BROKER10_MARGIN_TO_EQUITY_CAP,
        },
        "aggregate": aggregate.to_dict("records"),
        "robust_core": bool(robust_core),
        "broker_tail_warning": bool(broker_tail),
        "decision": decision_label,
        "judgment": (
            "Stage831 freezes Stage830 parameters and checks yearly start robustness. It is an internal Stage819 "
            "candidate-line validation, not a formal live-default A/B against Stage372."
        ),
        "overfit_reflection": (
            "Low-to-medium. The start grid and thresholds are predeclared and no parameter is tuned, but the rule was "
            "selected after seeing the 2018 full-path Stage830 improvement, so promotion still requires common-window "
            "and official-version comparison."
        ),
        "continue_value": (
            "Continue only if yearly starts show broad return/drawdown improvement. If broker100 tail persists, the next "
            "research step should be full-path holding margin survival, not lowering the entry cap by small increments."
        ),
        "outputs": {
            "summary": str(SUMMARY_PATH),
            "curves": str(CURVES_PATH),
            "comparison": str(COMPARISON_PATH),
            "aggregate": str(AGGREGATE_PATH),
            "report": str(REPORT_PATH),
            "metric_chart": str(METRIC_CHART_PATH),
            "selected_curves": str(SELECTED_CURVES_PATH),
            "decision": str(DECISION_PATH),
        },
        "all_bucket": all_row,
        "mature_bucket": mature,
    }


def _write_report(comparison: pd.DataFrame, aggregate: pd.DataFrame, decision: dict[str, Any]) -> None:
    display_cols = [
        "start_month",
        "total_return_pct_A",
        "total_return_pct_C4",
        "total_return_delta_C4_vs_A_pp",
        "max_dd_pct_A",
        "max_dd_pct_C4",
        "max_dd_delta_C4_vs_A_pp",
        "sharpe_A",
        "sharpe_C4",
        "sharpe_delta_C4_vs_A",
        "max_broker10_margin_to_equity_pct_A",
        "max_broker10_margin_to_equity_pct_C4",
        "stage827_intraday_event_count_C4",
        "stage830_cap_event_count_C4",
        "stage830_cap_reduced_volume_C4",
    ]
    lines = [
        "# Stage831 Stage830 C4年度起点稳健性",
        "",
        f"- line_id：`{LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        f"- 源候选：`{stage819_cfg.OFFICIAL_CANDIDATE_STAGE819_30W_VERSION}`",
        "- 阶段性质：冻结 Stage830 参数的候选线内部跨起点验证；不改正式策略、不连接 CTP、不调用下单。",
        "- A：Stage819 baseline。",
        "- C4：Stage827 C2 日内实时止损 + Stage830 broker10 100% flat-entry 保证金入口闸门。",
        "- 本阶段不扫描 `1R`、保证金阈值、broker multiplier、冷却天数、品种过滤或年份过滤。",
        "",
        "## Aggregate",
        "",
        _md_table(aggregate, max_rows=10),
        "",
        "## Yearly Comparison",
        "",
        _md_table(comparison[display_cols], max_rows=20),
        "",
        "## Decision",
        "",
        f"- 决策：`{decision['decision']}`",
        f"- robust_core：`{decision['robust_core']}`",
        f"- broker_tail_warning：`{decision['broker_tail_warning']}`",
        f"- 判断：{decision['judgment']}",
        "",
        "## Charts",
        "",
        f"- metric chart：`{METRIC_CHART_PATH}`",
        f"- selected curves：`{SELECTED_CURVES_PATH}`",
        "",
        "## Overfit / Continue",
        "",
        f"- 过拟合反思：{decision['overfit_reflection']}",
        f"- 继续价值：{decision['continue_value']}",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    tasks = [(arm, _month_text(start)) for start in YEAR_STARTS for arm in (BASE_ARM, CAP_ARM)]
    rows: list[dict[str, Any]] = []
    curves: list[pd.DataFrame] = []

    print(f"[stage831] launching {len(tasks)} yearly A/C4 runs workers={MAX_WORKERS}", flush=True)
    if MAX_WORKERS == 1:
        for index, task in enumerate(tasks, start=1):
            print(f"[stage831] running {index}/{len(tasks)} {task[1]} {task[0]}", flush=True)
            row, curve = _run_one(task)
            rows.append(row)
            curves.append(curve)
    else:
        with ProcessPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_map = {executor.submit(_run_one, task): task for task in tasks}
            for index, future in enumerate(as_completed(future_map), start=1):
                task = future_map[future]
                row, curve = future.result()
                rows.append(row)
                curves.append(curve)
                print(f"[stage831] completed {index}/{len(tasks)} {task[1]} {task[0]}", flush=True)

    summary = pd.DataFrame(rows).sort_values(["start_month", "arm"]).reset_index(drop=True)
    curve_df = pd.concat(curves, ignore_index=True, sort=False).sort_values(["start_month", "arm", "date"])
    comparison = _comparison(summary)
    aggregate = _aggregate(comparison)
    decision = _decision(aggregate)

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    curve_df.to_csv(CURVES_PATH, index=False, encoding="utf-8-sig")
    comparison.to_csv(COMPARISON_PATH, index=False, encoding="utf-8-sig")
    aggregate.to_csv(AGGREGATE_PATH, index=False, encoding="utf-8-sig")
    _plot_metric_chart(comparison)
    _plot_selected_curves(curve_df)
    _write_report(comparison, aggregate, decision)
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), flush=True)
    print("aggregate", flush=True)
    print(aggregate.to_string(index=False), flush=True)
    print("comparison", flush=True)
    print(comparison.to_string(index=False), flush=True)


if __name__ == "__main__":
    main()
