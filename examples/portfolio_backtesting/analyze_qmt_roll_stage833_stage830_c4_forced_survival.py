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
STAGE = "Stage833"
MODEL_TAG = "stage833_stage830_c4_forced_survival_v1"
OUTPUT_PREFIX = "qmt_roll_stage833_stage830_c4_forced_survival"

STAGE832_TAG = "stage832_stage831_c4_stress_forensics_v1"
STAGE832_PREFIX = "qmt_roll_stage832_stage831_c4_stress_forensics"
STAGE832_SUMMARY_PATH = OUTPUT_DIR / f"{STAGE832_PREFIX}_summary_{STAGE832_TAG}.csv"
STAGE832_CURVES_PATH = OUTPUT_DIR / f"{STAGE832_PREFIX}_curves_{STAGE832_TAG}.csv"

BASE_ARM = s830.BASE_ARM
C4_ARM = s830.CAP_ARM
C5_ARM = "stage833_stage819_c2_broker10_cap_forced100_to100"
DATA_END = pd.Timestamp("2026-05-29")
STRESS_STARTS = ("2018-01", "2019-01", "2020-01", "2021-01")

FORCED_TRIGGER_RATIO = 1.00
FORCED_TARGET_RATIO = 1.00
FORCED_BROKER_MULTIPLIER = s830.BROKER_MARGIN_MULTIPLIER
MAX_WORKERS = max(1, min(2, int(os.environ.get("STAGE833_MAX_WORKERS", "2"))))

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
CURVES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv"
COMPARISON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_comparison_{MODEL_TAG}.csv"
AGGREGATE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_aggregate_{MODEL_TAG}.csv"
TRADE_EVENTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trade_events_{MODEL_TAG}.csv"
INTRADAY_EVENTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_intraday_events_{MODEL_TAG}.csv"
FORCED_EVENTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_forced_events_{MODEL_TAG}.csv"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

_WORKER_STATE: dict[str, Any] = {}


def _json_safe(value: Any) -> Any:
    return s650._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s650._md_table(frame, max_rows=max_rows)


def _month_text(value: Any) -> str:
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


def _load_stage832_reference() -> tuple[pd.DataFrame, pd.DataFrame]:
    if not STAGE832_SUMMARY_PATH.exists() or not STAGE832_CURVES_PATH.exists():
        raise FileNotFoundError("Stage832 reference outputs are required before Stage833")
    summary = pd.read_csv(STAGE832_SUMMARY_PATH, encoding="utf-8-sig")
    curves = pd.read_csv(STAGE832_CURVES_PATH, encoding="utf-8-sig")
    summary = summary[summary["start_month"].astype(str).isin(STRESS_STARTS)].copy()
    curves = curves[curves["start_month"].astype(str).isin(STRESS_STARTS)].copy()
    summary = summary[summary["arm"].isin([BASE_ARM, C4_ARM])].copy()
    curves = curves[curves["arm"].isin([BASE_ARM, C4_ARM])].copy()
    return summary, curves


def _profile_c5(metadata: dict[str, Any], start: pd.Timestamp) -> dict[str, Any]:
    start_text = _month_text(start)
    profile = s830._cap_profile(metadata)
    spec = profile["spec"]
    capital = replace(
        spec.capital,
        variant=f"stage833_{C5_ARM}_{start_text.replace('-', '_')}",
        label=f"Stage833 C5 C4 + forced survival {start_text}",
        note=(
            f"{spec.capital.note} | Stage833 C5: C4 plus full-path forced margin survival. "
            "After mark-to-market, if broker10 margin/equity exceeds 100%, reduce largest-margin "
            "positions until the same 100% survival line is reached."
        ),
    )
    overrides = {
        **spec.overrides,
        "enable_stage827_intraday_c2_stop": True,
        "enable_stage830_broker10_margin_cap": True,
        "stage830_broker_margin_multiplier": s830.BROKER_MARGIN_MULTIPLIER,
        "stage830_projected_broker10_margin_to_equity_cap": s830.PROJECTED_BROKER10_MARGIN_TO_EQUITY_CAP,
        "enable_forced_margin_deleverage": True,
        "forced_margin_deleverage_trigger_ratio": FORCED_TRIGGER_RATIO,
        "forced_margin_deleverage_target_ratio": FORCED_TARGET_RATIO,
        "forced_margin_deleverage_broker_multiplier": FORCED_BROKER_MULTIPLIER,
        "forced_margin_deleverage_priority": "largest_margin",
        "forced_margin_deleverage_max_reductions_per_day": 100,
    }
    result = dict(profile)
    result["profile"] = C5_ARM
    result["strategy_cls"] = s830.QmtRollPortfolioStrategyStage830C2Broker10MarginCap
    result["spec"] = replace(spec, capital=capital, overrides=overrides, profile=C5_ARM)
    return result


def _run_c5(start_text: str) -> dict[str, pd.DataFrame]:
    state = _ensure_worker_state()
    metadata = state["metadata"]
    start = pd.Timestamp(f"{start_text}-01").normalize()
    original_start = s827.START
    original_end = s827.END
    try:
        s827.START = start
        s827.END = DATA_END
        profile = _profile_c5(metadata, start)
        combined, frames = s827._run_profile(profile, metadata)
        summary, curve = s827._metric(profile, combined)
        for frame in [summary, curve]:
            frame["arm"] = C5_ARM
            frame["requested_start_month"] = start_text
            frame["start_month"] = start_text
            frame["start_year"] = int(start.year)
            frame["analysis_start"] = start.strftime("%Y-%m-%d")
            frame["analysis_end"] = DATA_END.strftime("%Y-%m-%d")

        trade_events = frames.get("trade_events", pd.DataFrame()).copy()
        intraday_events = frames.get("intraday_events", pd.DataFrame()).copy()
        for frame in [trade_events, intraday_events]:
            if frame.empty:
                continue
            frame["arm"] = C5_ARM
            frame["requested_start_month"] = start_text
            frame["start_month"] = start_text
            frame["start_year"] = int(start.year)
            frame["analysis_start"] = start.strftime("%Y-%m-%d")
            frame["analysis_end"] = DATA_END.strftime("%Y-%m-%d")

        forced_events = pd.DataFrame()
        if not trade_events.empty and "reason" in trade_events.columns:
            forced_events = trade_events[trade_events["reason"].astype(str).eq("forced_margin_deleverage")].copy()

        summary["stage827_intraday_event_count"] = int(len(intraday_events))
        summary["stage827_intraday_event_volume"] = (
            float(pd.to_numeric(intraday_events.get("volume", 0), errors="coerce").fillna(0.0).sum())
            if not intraday_events.empty
            else 0.0
        )
        if not trade_events.empty and "reason" in trade_events.columns:
            cap_events = trade_events[trade_events["reason"].astype(str).str.startswith("broker10_margin_cap", na=False)].copy()
        else:
            cap_events = pd.DataFrame()
        summary["stage830_cap_event_count"] = int(len(cap_events))
        summary["stage830_cap_reduced_volume"] = (
            float(pd.to_numeric(cap_events.get("reduced_volume", 0), errors="coerce").fillna(0.0).sum())
            if not cap_events.empty
            else 0.0
        )
        summary["stage833_forced_event_count"] = int(len(forced_events))
        summary["stage833_forced_closed_volume"] = (
            float(pd.to_numeric(forced_events.get("volume", 0), errors="coerce").fillna(0.0).sum())
            if not forced_events.empty
            else 0.0
        )

        return {
            "summary": summary,
            "curves": curve,
            "trade_events": trade_events,
            "intraday_events": intraday_events,
            "forced_events": forced_events,
        }
    finally:
        s827.START = original_start
        s827.END = original_end


def _concat(results: list[dict[str, pd.DataFrame]], key: str) -> pd.DataFrame:
    frames = [item.get(key, pd.DataFrame()) for item in results if not item.get(key, pd.DataFrame()).empty]
    return pd.concat(frames, ignore_index=True, sort=False) if frames else pd.DataFrame()


def _metric_value(row: pd.Series, column: str) -> float:
    return float(pd.to_numeric(pd.Series([row.get(column, np.nan)]), errors="coerce").iloc[0])


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
        "stage830_cap_reduced_volume",
        "stage833_forced_event_count",
        "stage833_forced_closed_volume",
    ]
    for start_month, group in summary.groupby("start_month", sort=True):
        indexed = group.set_index("arm")
        if BASE_ARM not in indexed.index or C4_ARM not in indexed.index or C5_ARM not in indexed.index:
            continue
        row: dict[str, Any] = {"start_month": start_month}
        for arm, label in [(BASE_ARM, "A"), (C4_ARM, "C4"), (C5_ARM, "C5")]:
            source = indexed.loc[arm]
            for column in metric_cols:
                row[f"{column}_{label}"] = _metric_value(source, column)
        row["end_equity_delta_C5_vs_A"] = row["end_equity_C5"] - row["end_equity_A"]
        row["end_equity_delta_C5_vs_C4"] = row["end_equity_C5"] - row["end_equity_C4"]
        row["return_delta_C5_vs_A_pp"] = row["total_return_pct_C5"] - row["total_return_pct_A"]
        row["return_delta_C5_vs_C4_pp"] = row["total_return_pct_C5"] - row["total_return_pct_C4"]
        row["dd_delta_C5_vs_A_pp"] = row["max_dd_pct_C5"] - row["max_dd_pct_A"]
        row["dd_delta_C5_vs_C4_pp"] = row["max_dd_pct_C5"] - row["max_dd_pct_C4"]
        row["broker10_delta_C5_vs_C4_pp"] = (
            row["max_broker10_margin_to_equity_pct_C5"] - row["max_broker10_margin_to_equity_pct_C4"]
        )
        row["C5_return_win_vs_A"] = int(row["total_return_pct_C5"] > row["total_return_pct_A"])
        row["C5_dd_win_vs_A"] = int(row["max_dd_pct_C5"] > row["max_dd_pct_A"])
        row["C5_dd_win_vs_C4"] = int(row["max_dd_pct_C5"] > row["max_dd_pct_C4"])
        row["C5_broker100_fail"] = int(row["max_broker10_margin_to_equity_pct_C5"] > 100.0)
        row["C4_broker100_fail"] = int(row["max_broker10_margin_to_equity_pct_C4"] > 100.0)
        rows.append(row)
    return pd.DataFrame(rows).sort_values("start_month").reset_index(drop=True)


def _aggregate(comparison: pd.DataFrame) -> pd.DataFrame:
    if comparison.empty:
        return pd.DataFrame()
    return pd.DataFrame(
        [
            {
                "bucket": "stress_starts",
                "window_count": int(len(comparison)),
                "C5_return_win_vs_A_count": int(comparison["C5_return_win_vs_A"].sum()),
                "C5_dd_win_vs_A_count": int(comparison["C5_dd_win_vs_A"].sum()),
                "C5_dd_win_vs_C4_count": int(comparison["C5_dd_win_vs_C4"].sum()),
                "A_dd50_fail_count": int(comparison["dd50_fail_A"].sum()),
                "C4_dd50_fail_count": int(comparison["dd50_fail_C4"].sum()),
                "C5_dd50_fail_count": int(comparison["dd50_fail_C5"].sum()),
                "A_broker100_fail_count": int((comparison["max_broker10_margin_to_equity_pct_A"] > 100.0).sum()),
                "C4_broker100_fail_count": int(comparison["C4_broker100_fail"].sum()),
                "C5_broker100_fail_count": int(comparison["C5_broker100_fail"].sum()),
                "median_return_delta_C5_vs_A_pp": float(comparison["return_delta_C5_vs_A_pp"].median()),
                "median_return_delta_C5_vs_C4_pp": float(comparison["return_delta_C5_vs_C4_pp"].median()),
                "median_dd_delta_C5_vs_A_pp": float(comparison["dd_delta_C5_vs_A_pp"].median()),
                "median_dd_delta_C5_vs_C4_pp": float(comparison["dd_delta_C5_vs_C4_pp"].median()),
                "max_broker10_C5": float(comparison["max_broker10_margin_to_equity_pct_C5"].max()),
                "forced_event_count": int(comparison["stage833_forced_event_count_C5"].sum()),
                "forced_closed_volume": float(comparison["stage833_forced_closed_volume_C5"].sum()),
            }
        ]
    )


def _plot(comparison: pd.DataFrame) -> None:
    if comparison.empty:
        return
    x = np.arange(len(comparison))
    labels = comparison["start_month"].astype(str).tolist()
    fig, axes = plt.subplots(3, 1, figsize=(14, 10), sharex=True, constrained_layout=True)
    width = 0.25
    for ax, metric, title in [
        (axes[0], "total_return_pct", "Total return pct"),
        (axes[1], "max_dd_pct", "Max drawdown pct"),
        (axes[2], "max_broker10_margin_to_equity_pct", "Max broker10 margin/equity pct"),
    ]:
        ax.bar(x - width, comparison[f"{metric}_A"], width=width, label="A", color="#2563eb")
        ax.bar(x, comparison[f"{metric}_C4"], width=width, label="C4", color="#16a34a")
        ax.bar(x + width, comparison[f"{metric}_C5"], width=width, label="C5", color="#dc2626")
        if metric == "max_broker10_margin_to_equity_pct":
            ax.axhline(100.0, color="#111827", linestyle="--", linewidth=1.0)
        if metric == "max_dd_pct":
            ax.axhline(-50.0, color="#111827", linestyle="--", linewidth=1.0)
        ax.set_title(title)
        ax.grid(True, axis="y", alpha=0.25)
        ax.legend(loc="best")
    axes[-1].set_xticks(x)
    axes[-1].set_xticklabels(labels, rotation=25, ha="right")
    fig.savefig(CHART_PATH, dpi=160)
    plt.close(fig)


def _decision(aggregate: pd.DataFrame, comparison: pd.DataFrame) -> dict[str, Any]:
    row = aggregate.iloc[0].to_dict() if not aggregate.empty else {}
    broker_fixed = int(row.get("C5_broker100_fail_count", 999)) == 0
    dd_not_worse_than_c4 = int(row.get("C5_dd_win_vs_C4_count", 0)) >= 3
    return_retention = float(row.get("median_return_delta_C5_vs_C4_pp", -1e9)) > -500.0
    decision_label = (
        "stage833_c5_stress_fix_candidate_needs_yearly"
        if broker_fixed and dd_not_worse_than_c4 and return_retention
        else "stage833_c5_stress_survival_not_enough"
    )
    return {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "source_candidate": stage819_cfg.OFFICIAL_CANDIDATE_STAGE819_30W_VERSION,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "strategy_changed": False,
        "formal_ab_triggered": False,
        "ctp_connected": False,
        "order_api_called": False,
        "arms": {"A": BASE_ARM, "C4": C4_ARM, "C5": C5_ARM},
        "stress_starts": list(STRESS_STARTS),
        "frozen_parameters": {
            "stage827_intraday_c2_stop_r": s827.STOP_R,
            "stage827_intraday_c2_confirm_r": s827.CONFIRM_R,
            "stage830_broker_margin_multiplier": s830.BROKER_MARGIN_MULTIPLIER,
            "stage830_projected_broker10_margin_to_equity_cap": s830.PROJECTED_BROKER10_MARGIN_TO_EQUITY_CAP,
            "forced_margin_deleverage_trigger_ratio": FORCED_TRIGGER_RATIO,
            "forced_margin_deleverage_target_ratio": FORCED_TARGET_RATIO,
            "forced_margin_deleverage_broker_multiplier": FORCED_BROKER_MULTIPLIER,
            "forced_margin_deleverage_priority": "largest_margin",
        },
        "aggregate": aggregate.to_dict("records"),
        "comparison": comparison.to_dict("records"),
        "decision": decision_label,
        "judgment": (
            "Stage833 tests whether the Stage832 stress mechanism is fixable by a full-path holding margin "
            "survival rule. It is a stress-start filter, not promotion."
        ),
        "overfit_reflection": (
            "Low-to-medium. The 100% survival line is selected from broker survival semantics, not an optimized "
            "return threshold, but the sample is restricted to known stress starts."
        ),
        "continue_value": (
            "If C5 removes broker100 without destroying return/drawdown, next step is all-year starts. If it fails, "
            "the C2/C4 path should stop rather than scan thresholds."
        ),
        "outputs": {
            "summary": str(SUMMARY_PATH),
            "curves": str(CURVES_PATH),
            "comparison": str(COMPARISON_PATH),
            "aggregate": str(AGGREGATE_PATH),
            "trade_events": str(TRADE_EVENTS_PATH),
            "intraday_events": str(INTRADAY_EVENTS_PATH),
            "forced_events": str(FORCED_EVENTS_PATH),
            "report": str(REPORT_PATH),
            "chart": str(CHART_PATH),
            "decision": str(DECISION_PATH),
        },
    }


def _write_report(comparison: pd.DataFrame, aggregate: pd.DataFrame, decision: dict[str, Any]) -> None:
    display_cols = [
        "start_month",
        "total_return_pct_A",
        "total_return_pct_C4",
        "total_return_pct_C5",
        "return_delta_C5_vs_C4_pp",
        "max_dd_pct_A",
        "max_dd_pct_C4",
        "max_dd_pct_C5",
        "dd_delta_C5_vs_C4_pp",
        "max_broker10_margin_to_equity_pct_A",
        "max_broker10_margin_to_equity_pct_C4",
        "max_broker10_margin_to_equity_pct_C5",
        "stage833_forced_event_count_C5",
        "stage833_forced_closed_volume_C5",
    ]
    lines = [
        "# Stage833 C4叠加持仓后保证金生存线压力起点验证",
        "",
        f"- line_id：`{LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        f"- 源候选：`{stage819_cfg.OFFICIAL_CANDIDATE_STAGE819_30W_VERSION}`",
        "- 阶段性质：冻结 C5 stress-start 验证；不改正式策略、不连接 CTP、不调用下单。",
        "- A：Stage819 baseline。",
        "- C4：Stage827 C2 日内实时止损 + Stage830 broker10 100% flat-entry 保证金入口闸门。",
        "- C5：C4 + 持仓后 forced margin survival，broker10 实际保证金/权益 `>100%` 后按最大保证金占用品种减仓到 `100%`。",
        "- 本阶段不扫描 `1R`、entry cap、forced target、broker multiplier、冷却天数、品种过滤或年份过滤。",
        "",
        "## Aggregate",
        "",
        _md_table(aggregate, max_rows=10),
        "",
        "## Stress Start Comparison",
        "",
        _md_table(comparison[display_cols], max_rows=20),
        "",
        "## Decision",
        "",
        f"- 决策：`{decision['decision']}`",
        f"- 判断：{decision['judgment']}",
        "",
        "## Charts",
        "",
        f"- chart：`{CHART_PATH}`",
        "",
        "## Overfit / Continue",
        "",
        f"- 过拟合反思：{decision['overfit_reflection']}",
        f"- 继续价值：{decision['continue_value']}",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    reference_summary, reference_curves = _load_stage832_reference()
    results: list[dict[str, pd.DataFrame]] = []
    print(f"[stage833] launching {len(STRESS_STARTS)} C5 stress-start runs workers={MAX_WORKERS}", flush=True)
    if MAX_WORKERS == 1:
        for index, start in enumerate(STRESS_STARTS, start=1):
            print(f"[stage833] running {index}/{len(STRESS_STARTS)} {start}", flush=True)
            results.append(_run_c5(start))
    else:
        with ProcessPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_map = {executor.submit(_run_c5, start): start for start in STRESS_STARTS}
            for index, future in enumerate(as_completed(future_map), start=1):
                start = future_map[future]
                results.append(future.result())
                print(f"[stage833] completed {index}/{len(STRESS_STARTS)} {start}", flush=True)

    c5_summary = _concat(results, "summary")
    c5_curves = _concat(results, "curves")
    trade_events = _concat(results, "trade_events")
    intraday_events = _concat(results, "intraday_events")
    forced_events = _concat(results, "forced_events")

    summary = pd.concat([reference_summary, c5_summary], ignore_index=True, sort=False)
    curves = pd.concat([reference_curves, c5_curves], ignore_index=True, sort=False)
    comparison = _comparison(summary)
    aggregate = _aggregate(comparison)
    decision = _decision(aggregate, comparison)

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    curves.to_csv(CURVES_PATH, index=False, encoding="utf-8-sig")
    comparison.to_csv(COMPARISON_PATH, index=False, encoding="utf-8-sig")
    aggregate.to_csv(AGGREGATE_PATH, index=False, encoding="utf-8-sig")
    trade_events.to_csv(TRADE_EVENTS_PATH, index=False, encoding="utf-8-sig")
    intraday_events.to_csv(INTRADAY_EVENTS_PATH, index=False, encoding="utf-8-sig")
    forced_events.to_csv(FORCED_EVENTS_PATH, index=False, encoding="utf-8-sig")
    _plot(comparison)
    _write_report(comparison, aggregate, decision)
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), flush=True)
    print("aggregate", flush=True)
    print(aggregate.to_string(index=False), flush=True)
    print("comparison", flush=True)
    print(comparison.to_string(index=False), flush=True)


if __name__ == "__main__":
    main()
