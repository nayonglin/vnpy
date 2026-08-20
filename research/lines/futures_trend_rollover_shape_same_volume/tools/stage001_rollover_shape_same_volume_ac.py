from __future__ import annotations

from dataclasses import replace
from datetime import datetime
import json
from pathlib import Path
from typing import Any

import pandas as pd

import analyze_qmt_roll_stage513_stage208_exact_position_margin_audit as s513
import analyze_qmt_roll_stage827_stage819_intraday_c2_engine_ac as s827
import analyze_qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow as s901
import qmt_roll_official_live_config as live_cfg


LINE_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = LINE_DIR / "artifacts" / "stage001"

BASE_PROFILE = "stage001_A_official_live_c9_15w"
CANDIDATE_PROFILE = "stage001_C_official_live_c9_15w_rollover_shape_same_volume"
START = pd.Timestamp("2018-01-01")
END = pd.Timestamp("2026-05-29")

SUMMARY_PATH = OUTPUT_DIR / "stage001_ac_summary.csv"
COMPARISON_PATH = OUTPUT_DIR / "stage001_ac_comparison.csv"
CURVE_PATH = OUTPUT_DIR / "stage001_ac_curve.csv"
ROLLOVER_PATH = OUTPUT_DIR / "stage001_rollover_shape_diagnostics.csv"
TRADES_PATH = OUTPUT_DIR / "stage001_trades.csv"
TRADE_EVENTS_PATH = OUTPUT_DIR / "stage001_trade_events.csv"
DECISION_PATH = OUTPUT_DIR / "stage001_decision.json"


def _overrides(*, candidate: bool) -> dict[str, Any]:
    overrides = live_cfg.build_official_live_strategy_overrides()
    overrides["enable_rollover_shape_same_volume_reopen"] = bool(candidate)
    return overrides


def _run_arm(
    *,
    profile_name: str,
    candidate: bool,
    metadata: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, pd.DataFrame]]:
    original_builder = s901.build_official_live_strategy_overrides
    try:
        s901.build_official_live_strategy_overrides = lambda: _overrides(candidate=candidate)
        combined, frames, live_spec = s901._run_live_c9(metadata, START, END)
    finally:
        s901.build_official_live_strategy_overrides = original_builder

    metric_capital = replace(
        live_spec.capital,
        variant=profile_name,
        label=(
            "C: 正式 C9/15万 + 换月形态确认原手数完整重开"
            if candidate
            else "A: 正式 C9/15万原样基线"
        ),
    )
    metric_spec = replace(live_spec, capital=metric_capital, profile=profile_name)
    summary, curve = s827._metric(
        {"profile": profile_name, "spec": metric_spec},
        combined,
    )
    return summary, curve, frames


def _reconcile_targeted_trades(
    diagnostics: pd.DataFrame,
    trades: pd.DataFrame,
) -> pd.DataFrame:
    result = diagnostics.copy()
    for column, default in {
        "fill_status": "",
        "fill_trade_id": "",
        "fill_datetime": "",
        "fill_volume": 0,
    }.items():
        result[column] = default
    if result.empty or trades.empty:
        return result

    actual = trades.copy().reset_index(drop=True)
    actual["_datetime"] = pd.to_datetime(actual.get("datetime"), errors="coerce")
    actual["_trade_date"] = actual["_datetime"].map(
        lambda value: pd.Timestamp(value).tz_localize(None).normalize() if pd.notna(value) else pd.NaT
    )
    actual["_direction"] = actual.get("direction", "").map(s901._normal_direction)
    actual["_offset"] = actual.get("offset", "").map(s901._normal_offset)
    actual["_volume"] = pd.to_numeric(actual.get("volume", 0), errors="coerce").fillna(0).astype(int)
    used_trade_indexes: set[int] = set()

    targeted_indexes = result.index[result["status"].astype(str).eq("targeted")]
    for diagnostic_index in targeted_indexes:
        row = result.loc[diagnostic_index]
        intent_date = pd.Timestamp(row["datetime"]).tz_localize(None).normalize()
        deadline = intent_date + pd.Timedelta(days=10)
        candidates = actual[
            actual.index.map(lambda index: index not in used_trade_indexes)
            & actual["_offset"].eq("open")
            & actual["vt_symbol"].astype(str).eq(str(row["target_contract_vt_symbol"]))
            & actual["_direction"].eq(str(row["direction"]).lower())
            & actual["_volume"].eq(int(row["final_volume"]))
            & actual["_trade_date"].ge(intent_date)
            & actual["_trade_date"].le(deadline)
        ].sort_values("_datetime")
        if candidates.empty:
            result.at[diagnostic_index, "fill_status"] = "unfilled"
            continue
        trade_index = int(candidates.index[0])
        trade = candidates.iloc[0]
        used_trade_indexes.add(trade_index)
        result.at[diagnostic_index, "fill_status"] = "filled"
        result.at[diagnostic_index, "fill_trade_id"] = str(trade.get("trade_id", ""))
        result.at[diagnostic_index, "fill_datetime"] = str(trade["_datetime"])
        result.at[diagnostic_index, "fill_volume"] = int(trade["_volume"])
    return result


def _event_summary(
    profile_name: str,
    frames: dict[str, pd.DataFrame],
) -> tuple[dict[str, Any], pd.DataFrame]:
    diagnostics = frames.get("rollover_shape_same_volume", pd.DataFrame()).copy()
    trades = frames.get("trades", pd.DataFrame()).copy()
    diagnostics = _reconcile_targeted_trades(diagnostics, trades)
    trade_events = frames.get("trade_events", pd.DataFrame()).copy()
    rollover_close_count = 0
    if not trade_events.empty and "reason" in trade_events.columns:
        rollover_close_count = int(trade_events["reason"].astype(str).eq("rollover_close").sum())

    targeted = diagnostics[diagnostics.get("status", pd.Series(dtype="object")).astype(str).eq("targeted")].copy()
    opened = targeted[targeted.get("fill_status", pd.Series(dtype="object")).astype(str).eq("filled")].copy()
    skipped = diagnostics[diagnostics.get("status", pd.Series(dtype="object")).astype(str).eq("skipped")].copy()
    short_history = diagnostics[
        pd.to_numeric(diagnostics.get("target_am_inited", 1), errors="coerce").fillna(1).eq(0)
    ].copy() if not diagnostics.empty else pd.DataFrame()

    exact_volume_pass = bool(
        not diagnostics.empty
        and len(targeted) > 0
        and len(targeted) + len(skipped) == len(diagnostics)
        and pd.to_numeric(skipped.get("final_volume", 0), errors="coerce").fillna(0).eq(0).all()
        and pd.to_numeric(targeted["previous_volume"], errors="coerce")
        .eq(pd.to_numeric(targeted["final_volume"], errors="coerce"))
        .all()
        and len(opened) == len(targeted)
        and pd.to_numeric(opened["previous_volume"], errors="coerce")
        .eq(pd.to_numeric(opened["fill_volume"], errors="coerce"))
        .all()
    )
    return {
        "profile": profile_name,
        "rollover_close_count": rollover_close_count,
        "candidate_diagnostic_count": int(len(diagnostics)),
        "short_history_candidate_count": int(len(short_history)),
        "targeted_count": int(len(targeted)),
        "opened_count": int(len(opened)),
        "unfilled_target_count": int(len(targeted) - len(opened)),
        "skipped_count": int(len(skipped)),
        "exact_volume_pass": int(exact_volume_pass),
    }, diagnostics


def _comparison(summary: pd.DataFrame, event_summary: pd.DataFrame) -> pd.DataFrame:
    metrics = [
        "end_equity",
        "total_return_pct",
        "max_dd_pct",
        "sharpe",
        "total_slippage",
        "total_trade_count",
        "nonzero_daily_win_rate_pct",
    ]
    base = summary[summary["arm"].eq(BASE_PROFILE)].iloc[0]
    candidate = summary[summary["arm"].eq(CANDIDATE_PROFILE)].iloc[0]
    row: dict[str, Any] = {"base": BASE_PROFILE, "candidate": CANDIDATE_PROFILE}
    for metric in metrics:
        base_value = float(base[metric])
        candidate_value = float(candidate[metric])
        row[f"A_{metric}"] = base_value
        row[f"C_{metric}"] = candidate_value
        row[f"delta_{metric}"] = candidate_value - base_value
    candidate_events = event_summary[event_summary["profile"].eq(CANDIDATE_PROFILE)].iloc[0]
    for key in [
        "rollover_close_count",
        "candidate_diagnostic_count",
        "short_history_candidate_count",
        "targeted_count",
        "opened_count",
        "unfilled_target_count",
        "skipped_count",
        "exact_volume_pass",
    ]:
        row[key] = int(candidate_events[key])
    return pd.DataFrame([row])


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    metadata = s513._metadata()
    summaries: list[pd.DataFrame] = []
    curves: list[pd.DataFrame] = []
    event_rows: list[dict[str, Any]] = []
    diagnostics: list[pd.DataFrame] = []
    actual_trades: list[pd.DataFrame] = []
    trade_events: list[pd.DataFrame] = []

    for candidate in [False, True]:
        profile_name = CANDIDATE_PROFILE if candidate else BASE_PROFILE
        summary, curve, frames = _run_arm(
            profile_name=profile_name,
            candidate=candidate,
            metadata=metadata,
        )
        summaries.append(summary)
        curves.append(curve)
        event_row, reconciled_diagnostics = _event_summary(profile_name, frames)
        event_rows.append(event_row)
        for source, target in [
            (reconciled_diagnostics, diagnostics),
            (frames.get("trades", pd.DataFrame()), actual_trades),
            (frames.get("trade_events", pd.DataFrame()), trade_events),
        ]:
            if source.empty:
                continue
            item = source.copy()
            item["profile"] = profile_name
            target.append(item)

    summary = pd.concat(summaries, ignore_index=True, sort=False)
    curve = pd.concat(curves, ignore_index=True, sort=False)
    event_summary = pd.DataFrame(event_rows)
    comparison = _comparison(summary, event_summary)
    diagnostic_frame = pd.concat(diagnostics, ignore_index=True, sort=False) if diagnostics else pd.DataFrame()
    trades_frame = pd.concat(actual_trades, ignore_index=True, sort=False) if actual_trades else pd.DataFrame()
    trade_event_frame = pd.concat(trade_events, ignore_index=True, sort=False) if trade_events else pd.DataFrame()

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    comparison.to_csv(COMPARISON_PATH, index=False, encoding="utf-8-sig")
    curve.to_csv(CURVE_PATH, index=False, encoding="utf-8-sig")
    diagnostic_frame.to_csv(ROLLOVER_PATH, index=False, encoding="utf-8-sig")
    trades_frame.to_csv(TRADES_PATH, index=False, encoding="utf-8-sig")
    trade_event_frame.to_csv(TRADE_EVENTS_PATH, index=False, encoding="utf-8-sig")
    if int(comparison.iloc[0]["exact_volume_pass"]) != 1:
        raise RuntimeError(
            "rollover_exact_volume_invariant_failed: "
            + json.dumps(event_rows, ensure_ascii=False)
        )

    decision = {
        "line_id": "futures_trend_rollover_shape_same_volume",
        "stage": "Stage001",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "period": {"start": str(START.date()), "end": str(END.date())},
        "A": BASE_PROFILE,
        "C": CANDIDATE_PROFILE,
        "candidate_rule": {
            "history": "new contract only, point-in-time, minimum MA40 observations",
            "long": "MA5>MA10>MA20>MA40 and MACD histogram>0",
            "short": "MA5<MA10<MA20<MA40 and MACD histogram<0",
            "volume": "exact previous live volume or skip",
        },
        "event_summary": event_rows,
        "comparison": comparison.iloc[0].to_dict(),
    }
    DECISION_PATH.write_text(json.dumps(decision, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(decision, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
