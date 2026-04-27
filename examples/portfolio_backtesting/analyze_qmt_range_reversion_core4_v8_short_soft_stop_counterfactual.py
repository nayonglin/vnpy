from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from analyze_qmt_range_reversion_core4_v3_exit_structure import _build_round_trips
from analyze_qmt_range_reversion_core4_v7_weak_window_trade_replay import _load_bar_history
from analyze_qmt_range_reversion_core4_v8_short_soft_stop_replay import (
    _lookup_by_contract_datetime,
    _safe_float,
    _timestamp_key,
    _to_local_date,
)


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"
SOURCE_PREFIX: str = "qmt_range_reversion_core4_directed_product_signal_back_adjusted_v8_two_stage_stop"
MODEL_TAG: str = "range_reversion_core4_v8_short_soft_stop_counterfactual_v1"

TRADES_PATH: Path = OUTPUT_DIR / f"{SOURCE_PREFIX}_trades_2020_2026_04.csv"
ENTRY_RISK_PATH: Path = OUTPUT_DIR / f"{SOURCE_PREFIX}_entry_risk_diagnostics_2020_2026_04.csv"
CANDIDATES_PATH: Path = OUTPUT_DIR / f"{SOURCE_PREFIX}_entry_candidate_snapshots_2020_2026_04.csv"

DETAIL_PATH: Path = OUTPUT_DIR / f"qmt_range_reversion_core4_v8_short_soft_stop_counterfactual_detail_{MODEL_TAG}.csv"
SUMMARY_PATH: Path = OUTPUT_DIR / f"qmt_range_reversion_core4_v8_short_soft_stop_counterfactual_summary_{MODEL_TAG}.csv"
YEAR_SUMMARY_PATH: Path = OUTPUT_DIR / f"qmt_range_reversion_core4_v8_short_soft_stop_counterfactual_year_summary_{MODEL_TAG}.csv"
JSON_PATH: Path = OUTPUT_DIR / f"qmt_range_reversion_core4_v8_short_soft_stop_counterfactual_summary_{MODEL_TAG}.json"
REPORT_PATH: Path = OUTPUT_DIR / f"qmt_range_reversion_core4_v8_short_soft_stop_counterfactual_report_{MODEL_TAG}.md"

TARGET_EXIT_REASON: str = "short_soft_base_stop_confirmed"
CHANNEL_WINDOW: int = 20
MAX_HOLDING_BARS: int = 6
HARD_STOP_R_MULTIPLE: float = 2.0


def _load_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if not TRADES_PATH.exists():
        raise FileNotFoundError(TRADES_PATH)
    if not ENTRY_RISK_PATH.exists():
        raise FileNotFoundError(ENTRY_RISK_PATH)

    trades = pd.read_csv(TRADES_PATH)
    entries = pd.read_csv(ENTRY_RISK_PATH)
    candidates = pd.read_csv(CANDIDATES_PATH) if CANDIDATES_PATH.exists() else pd.DataFrame()
    round_trips = _build_round_trips(trades, entries)
    if not round_trips.empty:
        round_trips["entry_date"] = round_trips["entry_datetime"].map(_to_local_date)
        round_trips["exit_date"] = round_trips["exit_datetime"].map(_to_local_date)
        round_trips["entry_year"] = round_trips["entry_date"].dt.year
    return round_trips, entries, candidates


def _prepare_bars(contracts: set[str]) -> dict[str, pd.DataFrame]:
    bars = _load_bar_history(contracts)
    if bars.empty:
        return {}

    pieces: list[pd.DataFrame] = []
    for _, group in bars.groupby("vt_symbol", sort=False):
        group = group.sort_values("date").copy()
        channel_high = group["high"].rolling(CHANNEL_WINDOW).max()
        channel_low = group["low"].rolling(CHANNEL_WINDOW).min()
        group["channel_middle_20"] = (channel_high + channel_low) / 2.0
        pieces.append(group)
    bars = pd.concat(pieces, ignore_index=True)
    return {contract: group.reset_index(drop=True) for contract, group in bars.groupby("vt_symbol", sort=False)}


def _hard_stop_execution_price(bar: pd.Series, hard_stop: float) -> float:
    open_price = _safe_float(bar.get("open"))
    if pd.isna(open_price) or open_price <= 0:
        open_price = _safe_float(bar.get("close"))
    if open_price >= hard_stop:
        return open_price
    return hard_stop


def _simulate_ignore_loss_zone_soft_stop(
    row: pd.Series,
    history: pd.DataFrame,
    entry_fields: dict[str, Any],
    candidate_fields: dict[str, Any],
) -> dict[str, Any]:
    entry_date = _to_local_date(row["entry_date"])
    actual_exit_date = _to_local_date(row["exit_date"])
    entry_price = float(row["entry_price"])
    actual_exit_price = float(row["exit_price"])
    volume = float(row["volume"])
    contract_size = _safe_float(entry_fields.get("size"), 1.0)
    initial_stop = _safe_float(entry_fields.get("stop_price"))
    risk_distance = abs(entry_price - initial_stop) if not pd.isna(initial_stop) else _safe_float(
        entry_fields.get("stop_distance")
    )
    if pd.isna(risk_distance) or risk_distance <= 0:
        risk_distance = max(abs(entry_price) * 0.02, 1e-9)
    hard_stop = entry_price + HARD_STOP_R_MULTIPLE * risk_distance

    path = history[history["date"] >= entry_date].copy().head(MAX_HOLDING_BARS)
    actual_exit_index = None
    simulated_exit_reason = "counterfactual_no_data"
    simulated_exit_date = actual_exit_date
    simulated_exit_price = actual_exit_price
    simulated_bars_held = 0

    for index, bar in enumerate(path.itertuples(index=False), start=1):
        current = pd.Series(bar._asdict())
        current_date = _to_local_date(current["date"])
        if current_date == actual_exit_date:
            actual_exit_index = index

        high_price = _safe_float(current.get("high"))
        close_price = _safe_float(current.get("close"))
        channel_middle = _safe_float(current.get("channel_middle_20"))

        if high_price >= hard_stop:
            simulated_exit_reason = "counterfactual_hard_stop"
            simulated_exit_date = current_date
            simulated_exit_price = _hard_stop_execution_price(current, hard_stop)
            simulated_bars_held = index
            break

        if not pd.isna(channel_middle) and close_price <= channel_middle:
            simulated_exit_reason = "counterfactual_channel_middle_exit"
            simulated_exit_date = current_date
            simulated_exit_price = close_price
            simulated_bars_held = index
            break

        if index >= MAX_HOLDING_BARS:
            simulated_exit_reason = "counterfactual_time_exit"
            simulated_exit_date = current_date
            simulated_exit_price = close_price
            simulated_bars_held = index
            break

    actual_pnl = float(row["pnl"])
    simulated_pnl = (entry_price - simulated_exit_price) * volume * contract_size
    delta_pnl = simulated_pnl - actual_pnl
    actual_bars_held = int(actual_exit_index or 0)
    entry_rsi = _safe_float(
        candidate_fields.get("rsi_value"),
        _safe_float(entry_fields.get("streak_entry_structure_risk_recovery_rsi_value")),
    )

    return {
        "entry_context": str(entry_fields.get("env_gate_entry_context", candidate_fields.get("entry_context", "")) or ""),
        "entry_rsi": entry_rsi,
        "initial_stop_price": initial_stop,
        "initial_risk_distance": risk_distance,
        "hard_stop_price": hard_stop,
        "actual_exit_date": actual_exit_date,
        "actual_exit_price": actual_exit_price,
        "actual_pnl": actual_pnl,
        "actual_bars_held": actual_bars_held,
        "simulated_exit_reason": simulated_exit_reason,
        "simulated_exit_date": simulated_exit_date,
        "simulated_exit_price": simulated_exit_price,
        "simulated_pnl": simulated_pnl,
        "simulated_bars_held": simulated_bars_held,
        "delta_pnl": delta_pnl,
        "delta_r": delta_pnl / max(volume * contract_size * risk_distance, 1e-9),
        "actual_exit_to_simulated_exit_bars": max(0, simulated_bars_held - actual_bars_held),
    }


def _build_detail(round_trips: pd.DataFrame, entries: pd.DataFrame, candidates: pd.DataFrame) -> pd.DataFrame:
    target = round_trips[
        round_trips["direction"].eq("short") & round_trips["exit_reason"].eq(TARGET_EXIT_REASON)
    ].copy()
    if target.empty:
        return pd.DataFrame()

    entry_lookup = _lookup_by_contract_datetime(entries)
    candidate_lookup = _lookup_by_contract_datetime(candidates)
    bars_by_contract = _prepare_bars(set(target["contract_vt_symbol"].dropna().astype(str)))

    rows: list[dict[str, Any]] = []
    for _, row in target.iterrows():
        contract = str(row["contract_vt_symbol"])
        key = (contract, _timestamp_key(row["entry_datetime"]))
        history = bars_by_contract.get(contract, pd.DataFrame())
        metrics = _simulate_ignore_loss_zone_soft_stop(
            row,
            history,
            entry_lookup.get(key, {}),
            candidate_lookup.get(key, {}),
        )
        rows.append(
            {
                "product_vt_symbol": row["product_vt_symbol"],
                "contract_vt_symbol": contract,
                "entry_year": int(row["entry_year"]),
                "entry_datetime": row["entry_datetime"],
                "exit_datetime": row["exit_datetime"],
                "entry_price": row["entry_price"],
                "volume": row["volume"],
                **metrics,
            }
        )
    return pd.DataFrame(rows)


def _summarize(detail: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    if detail.empty:
        return pd.DataFrame()
    summary = detail.groupby(group_cols, dropna=False).agg(
        round_trips=("actual_pnl", "size"),
        actual_pnl=("actual_pnl", "sum"),
        simulated_pnl=("simulated_pnl", "sum"),
        delta_pnl=("delta_pnl", "sum"),
        avg_delta_pnl=("delta_pnl", "mean"),
        improved_rate=("delta_pnl", lambda s: float((s > 0).mean())),
        avg_actual_bars_held=("actual_bars_held", "mean"),
        avg_simulated_bars_held=("simulated_bars_held", "mean"),
        avg_delta_r=("delta_r", "mean"),
        worst_delta=("delta_pnl", "min"),
        best_delta=("delta_pnl", "max"),
    ).reset_index()
    return summary.sort_values(["delta_pnl", "round_trips"], ascending=[False, False]).reset_index(drop=True)


def _write_report(detail: pd.DataFrame, summary: pd.DataFrame, year_summary: pd.DataFrame) -> None:
    lines = [
        "# QMT Range Reversion Core4 V8 Short Soft Stop Counterfactual",
        "",
        "## Scope",
        "- Reads existing v8 trades, diagnostics and bar history only; no new backtest is run.",
        "- Counterfactual: ignore the actual short soft stop loss-zone exit, then approximate exits by hard stop, channel-middle touch, or max-holding time exit.",
        "- Channel-middle uses raw contract bar history, so this is attribution evidence, not a replacement backtest.",
        "",
        "## Summary By Counterfactual Exit",
        summary.to_markdown(index=False) if not summary.empty else "- Empty.",
        "",
        "## Summary By Year",
        year_summary.to_markdown(index=False) if not year_summary.empty else "- Empty.",
        "",
        "## Detail",
        detail[
            [
                "product_vt_symbol",
                "contract_vt_symbol",
                "entry_datetime",
                "actual_exit_date",
                "actual_pnl",
                "simulated_exit_reason",
                "simulated_exit_date",
                "simulated_pnl",
                "delta_pnl",
                "delta_r",
                "actual_bars_held",
                "simulated_bars_held",
                "entry_context",
                "entry_rsi",
            ]
        ].to_markdown(index=False)
        if not detail.empty
        else "- Empty.",
    ]
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    round_trips, entries, candidates = _load_inputs()
    detail = _build_detail(round_trips, entries, candidates)
    summary = _summarize(detail, ["simulated_exit_reason"])
    year_summary = _summarize(detail, ["entry_year"])

    detail.to_csv(DETAIL_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    year_summary.to_csv(YEAR_SUMMARY_PATH, index=False, encoding="utf-8-sig")

    payload = {
        "model_tag": MODEL_TAG,
        "source_prefix": SOURCE_PREFIX,
        "target_exit_reason": TARGET_EXIT_REASON,
        "round_trips": int(len(detail)),
        "actual_pnl": float(detail["actual_pnl"].sum()) if not detail.empty else 0.0,
        "simulated_pnl": float(detail["simulated_pnl"].sum()) if not detail.empty else 0.0,
        "delta_pnl": float(detail["delta_pnl"].sum()) if not detail.empty else 0.0,
        "improved_rate": float((detail["delta_pnl"] > 0).mean()) if not detail.empty else 0.0,
        "summary": summary.to_dict("records") if not summary.empty else [],
        "outputs": {
            "detail": str(DETAIL_PATH),
            "summary": str(SUMMARY_PATH),
            "year_summary": str(YEAR_SUMMARY_PATH),
            "report": str(REPORT_PATH),
        },
    }
    JSON_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    _write_report(detail, summary, year_summary)

    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    print(summary.to_string(index=False))
    print(year_summary.to_string(index=False))
    print(detail.sort_values(["delta_pnl", "entry_datetime"], ascending=[False, True]).to_string(index=False))


if __name__ == "__main__":
    main()
