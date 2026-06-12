from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import replace
import json
import os
from pathlib import Path
from typing import Any

import pandas as pd

import analyze_qmt_roll_stage513_stage208_exact_position_margin_audit as s513
import analyze_qmt_roll_stage650_stage526_200k_capital_reality_check as s650
import analyze_qmt_roll_stage778_stage777_2022_drawdown_forensics as s778
import analyze_qmt_roll_stage800_stage777_long_lower_high_block_yearly as s800
import analyze_qmt_roll_stage804_stage777_long_tighter_initial_stop_yearly as s804
import analyze_qmt_roll_stage813_stage804_rsi_partial_exit_ablation_yearly as s813


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

MODEL_TAG = "stage817_stage813_20w_yearly_v1"
OUTPUT_PREFIX = "qmt_roll_stage817_stage813_20w_yearly"
LINE_ID = "futures_trend_2019_data_extension"

CAPITAL_20W = 200_000.0
YEAR_STARTS = s800.YEAR_STARTS
MAX_WORKERS = max(1, min(4, int(os.environ.get("STAGE817_MAX_WORKERS", "4"))))

VARIANT = "stage817_stage813_20w_am41_oi08_old_ai_long_tighter_stop_rsi95_yearly"
LABEL = "Stage817 Stage813 20w AM41 OI0.8 oldAI long-tight RSI95 yearly"

BASE_50W_SUMMARY_PATH = s813.ON_SUMMARY_PATH
BASE_50W_CURVES_PATH = s813.ON_CURVES_PATH

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
CURVES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv"
RSI_EVENTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_rsi_events_{MODEL_TAG}.csv"
COMPARISON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_comparison_vs_stage813_50w_{MODEL_TAG}.csv"
AGG_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_aggregate_vs_stage813_50w_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


def _json_safe(value: Any) -> Any:
    return s650._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s650._md_table(frame, max_rows=max_rows)


def _year_start_text(start: pd.Timestamp) -> str:
    return pd.Timestamp(start).strftime("%Y-%m")


def _profile_20w(metadata: dict[str, Any], start: pd.Timestamp) -> dict[str, Any]:
    base = s813._profile(metadata, start, enabled=True)
    spec = base["spec"]
    start_text = _year_start_text(start)
    capital = replace(
        spec.capital,
        variant=f"{VARIANT}_{start_text.replace('-', '_')}",
        label=f"{LABEL} {start_text}",
        account_capital=CAPITAL_20W,
        c3_capital=CAPITAL_20W,
        note=(
            f"{spec.capital.note} | Stage817 capital-only stress: account_capital and "
            f"c3_capital changed from 500000 to {CAPITAL_20W:.0f}; all Stage813 logic unchanged."
        ),
    )
    profile = dict(base)
    profile["profile"] = "stage817_stage813_20w_rsi_on"
    profile["spec"] = replace(spec, capital=capital, profile=profile["profile"])
    profile["note"] = (
        "Stage813 official-candidate logic with only account/c3 capital changed to 20w. "
        "AM41/OI0.8/old-AI/long tighter stop/RSI95 partial exit are unchanged."
    )
    return profile


def _run_one(start_text: str) -> tuple[dict[str, Any], pd.DataFrame, pd.DataFrame]:
    start = pd.Timestamp(start_text).normalize()
    metadata = s513._metadata()
    base_c3_overrides = dict(s513._c3_overrides(pd.Timestamp("2018-01-01").to_pydatetime()))
    row, curve, rsi_events = s813._run_profile_once(
        profile=_profile_20w(metadata, start),
        start=start,
        metadata=metadata,
        base_c3_overrides=base_c3_overrides,
    )
    return row, curve, rsi_events


def _load_base_50w() -> tuple[pd.DataFrame, pd.DataFrame]:
    if not BASE_50W_SUMMARY_PATH.exists():
        raise FileNotFoundError(f"missing Stage813 50w summary: {BASE_50W_SUMMARY_PATH}")
    summary = pd.read_csv(BASE_50W_SUMMARY_PATH, encoding="utf-8-sig")
    summary["start_month"] = summary["start_month"].astype(str)
    year_months = {_year_start_text(start) for start in YEAR_STARTS}
    base_summary = summary[summary["start_month"].isin(year_months)].copy().sort_values("start_month")
    if len(base_summary) != len(YEAR_STARTS):
        missing = sorted(year_months - set(base_summary["start_month"]))
        raise RuntimeError(f"missing Stage813 50w yearly rows: {missing}")

    curves = pd.read_csv(BASE_50W_CURVES_PATH, parse_dates=["date"], encoding="utf-8-sig")
    curves["start_month"] = curves["start_month"].astype(str)
    base_curves = curves[curves["start_month"].isin(year_months)].copy().sort_values(["start_month", "date"])
    return base_summary.reset_index(drop=True), base_curves.reset_index(drop=True)


def _comparison(candidate: pd.DataFrame, base: pd.DataFrame) -> pd.DataFrame:
    comparison = s800._comparison(candidate, base).sort_values("start_month").reset_index(drop=True)
    min_equity_map = candidate.set_index("start_month")["min_equity"].to_dict() if "min_equity" in candidate.columns else {}
    count_map = (
        candidate.set_index("start_month")["rsi_partial_exit_count"].to_dict()
        if "rsi_partial_exit_count" in candidate.columns
        else {}
    )
    volume_map = (
        candidate.set_index("start_month")["rsi_partial_exit_volume"].to_dict()
        if "rsi_partial_exit_volume" in candidate.columns
        else {}
    )
    comparison["min_equity_candidate"] = comparison["start_month"].map(min_equity_map).fillna(0.0).astype(float)
    comparison["rsi_partial_exit_count_20w"] = comparison["start_month"].map(count_map).fillna(0).astype(int)
    comparison["rsi_partial_exit_volume_20w"] = comparison["start_month"].map(volume_map).fillna(0).astype(int)
    comparison["lower_high_block_count"] = 0
    return comparison


def _aggregate(comparison: pd.DataFrame) -> pd.DataFrame:
    aggregate = s800._aggregate(comparison)
    aggregate.rename(columns={"total_blocked_long_signals": "unused_total_blocked_long_signals"}, inplace=True)
    for bucket in aggregate["bucket"].astype(str).tolist():
        mask = comparison["start_month"].lt("2026-01") if bucket == "mature_ex_2026" else pd.Series(True, index=comparison.index)
        frame = comparison[mask].copy()
        idx = aggregate["bucket"].astype(str).eq(bucket)
        aggregate.loc[idx, "total_rsi_partial_exit_count_20w"] = int(frame["rsi_partial_exit_count_20w"].sum())
        aggregate.loc[idx, "total_rsi_partial_exit_volume_20w"] = int(frame["rsi_partial_exit_volume_20w"].sum())
        aggregate.loc[idx, "candidate_survival_fail_count"] = int(frame["min_equity_candidate"].le(0.0).sum())
        aggregate.loc[idx, "candidate_broker100_fail_count"] = int(
            frame["max_broker10_margin_to_equity_pct_candidate"].gt(100.0).sum()
        )
    return aggregate


def _write_report(comparison: pd.DataFrame, aggregate: pd.DataFrame, decision: dict[str, Any]) -> None:
    display_cols = [
        "start_month",
        "total_return_pct_base",
        "total_return_pct_candidate",
        "total_return_pct_delta",
        "max_dd_pct_base",
        "max_dd_pct_candidate",
        "max_dd_pct_delta",
        "sharpe_base",
        "sharpe_candidate",
        "sharpe_delta",
        "total_trade_count_base",
        "total_trade_count_candidate",
        "total_trade_count_delta",
        "max_broker10_margin_to_equity_pct_base",
        "max_broker10_margin_to_equity_pct_candidate",
        "rsi_partial_exit_count_20w",
    ]
    lines = [
        "# Stage817 Stage813 20w本金年度起点回测",
        "",
        f"- line_id：`{LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        "- A：已登记 Stage813 50w 候选：AM41、基础风险0.40、OI命中恢复0.80、旧正式AI、maxpos4、多头更紧初始止损、RSI95半平。",
        "- C：同 A，仅把 `account_capital/c3_capital` 改成 `200000`。",
        "- 不改正式配置、不连接 CTP、不调用下单。",
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
        f"- 判断：{decision['judgment']}",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    base_summary, _base_curves = _load_base_50w()
    tasks = [start.strftime("%Y-%m-%d") for start in YEAR_STARTS]
    rows: list[dict[str, Any]] = []
    curves: list[pd.DataFrame] = []
    rsi_events: list[pd.DataFrame] = []

    print(f"[stage817] launching {len(tasks)} yearly Stage813 20w runs workers={MAX_WORKERS}", flush=True)
    if MAX_WORKERS == 1:
        for idx, task in enumerate(tasks, start=1):
            print(f"[stage817] running {idx}/{len(tasks)} {task}", flush=True)
            row, curve, events = _run_one(task)
            rows.append(row)
            curves.append(curve)
            rsi_events.append(events)
    else:
        with ProcessPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_map = {executor.submit(_run_one, task): task for task in tasks}
            for idx, future in enumerate(as_completed(future_map), start=1):
                task = future_map[future]
                row, curve, events = future.result()
                rows.append(row)
                curves.append(curve)
                rsi_events.append(events)
                print(f"[stage817] completed {idx}/{len(tasks)} {task}", flush=True)

    candidate_summary = s804.s772._add_month_fields(pd.DataFrame(rows)).sort_values("start_month").reset_index(drop=True)
    candidate_curves = pd.concat(curves, ignore_index=True, sort=False).sort_values(["start_month", "date"]).reset_index(drop=True)
    rsi_event_df = (
        pd.concat(rsi_events, ignore_index=True, sort=False)
        if rsi_events
        else pd.DataFrame(columns=["start_month", "reason"])
    )
    comparison = _comparison(candidate_summary, base_summary)
    aggregate = _aggregate(comparison)

    candidate_summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    candidate_curves.to_csv(CURVES_PATH, index=False, encoding="utf-8-sig")
    rsi_event_df.to_csv(RSI_EVENTS_PATH, index=False, encoding="utf-8-sig")
    comparison.to_csv(COMPARISON_PATH, index=False, encoding="utf-8-sig")
    aggregate.to_csv(AGG_PATH, index=False, encoding="utf-8-sig")

    mature = aggregate[aggregate["bucket"].eq("mature_ex_2026")].iloc[0].to_dict()
    all_row = aggregate[aggregate["bucket"].eq("all")].iloc[0].to_dict()
    hard_fail = (
        int(mature["candidate_dd40_fail_count"]) > int(mature["base_dd40_fail_count"])
        or int(mature["candidate_broker100_fail_count"]) > 0
        or int(mature["candidate_survival_fail_count"]) > 0
    )
    decision_label = "stage817_stage813_20w_yearly_not_live_ready" if hard_fail else "stage817_stage813_20w_yearly_watch"
    decision = {
        "stage": "Stage817",
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "base": "official_candidate_stage813_50w_am41_oi08_old_ai_long_tighter_stop_rsi95_v1 yearly starts",
        "candidate": "Stage813 logic with account_capital/c3_capital changed to 200000",
        "change": {
            "account_capital_before": 500_000.0,
            "account_capital_after": CAPITAL_20W,
            "c3_capital_before": 500_000.0,
            "c3_capital_after": CAPITAL_20W,
            "strategy_logic_changed": False,
        },
        "decision": decision_label,
        "judgment": (
            "Capital-only deployment stress. This tests whether the Stage813 candidate survives 20w integer lots, "
            "margin, and cost path pressure; it does not change alpha logic."
        ),
        "aggregate_all": all_row,
        "aggregate_mature_ex_2026": mature,
        "outputs": {
            "summary": str(SUMMARY_PATH),
            "curves": str(CURVES_PATH),
            "rsi_events": str(RSI_EVENTS_PATH),
            "comparison": str(COMPARISON_PATH),
            "aggregate": str(AGG_PATH),
            "report": str(REPORT_PATH),
        },
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_report(comparison, aggregate, decision)

    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print("aggregate_vs_stage813_50w")
    print(aggregate.to_string(index=False))
    print("comparison_vs_stage813_50w")
    print(
        comparison[
            [
                "start_month",
                "total_return_pct_base",
                "total_return_pct_candidate",
                "total_return_pct_delta",
                "max_dd_pct_base",
                "max_dd_pct_candidate",
                "max_dd_pct_delta",
                "sharpe_base",
                "sharpe_candidate",
                "sharpe_delta",
                "total_trade_count_base",
                "total_trade_count_candidate",
                "total_trade_count_delta",
                "max_broker10_margin_to_equity_pct_base",
                "max_broker10_margin_to_equity_pct_candidate",
                "rsi_partial_exit_count_20w",
            ]
        ].to_string(index=False)
    )


if __name__ == "__main__":
    main()
