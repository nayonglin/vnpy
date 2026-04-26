from __future__ import annotations

import json
from bisect import bisect_right
from pathlib import Path
from typing import Any

import pandas as pd

from analyze_qmt_range_reversion_core4_v3_exit_structure import _build_round_trips
from main_contract_mapping import ALL_FUTURES_MAPPING_PATH
from qmt_universe import END_DT, PRELOAD_START_DT
from run_qmt_range_reversion_core4_directed_backtest import CORE_UNIVERSE_PATH
from run_qmt_roll_backtest import build_backtest_engine


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"
SOURCE_PREFIX: str = "qmt_range_reversion_core4_directed_product_signal_no_long_prevday_stop_v6"
MODEL_TAG: str = "range_reversion_core4_product_signal_logic_audit_v1"

TRADES_PATH: Path = OUTPUT_DIR / f"{SOURCE_PREFIX}_trades_2020_2026_04.csv"
ENTRY_RISK_PATH: Path = OUTPUT_DIR / f"{SOURCE_PREFIX}_entry_risk_diagnostics_2020_2026_04.csv"

ROLL_EVENTS_PATH: Path = OUTPUT_DIR / f"qmt_range_reversion_core4_roll_events_{MODEL_TAG}.csv"
ENTRY_ROLL_PATH: Path = OUTPUT_DIR / f"qmt_range_reversion_core4_entry_roll_exposure_{MODEL_TAG}.csv"
ROLL_WINDOW_SUMMARY_PATH: Path = OUTPUT_DIR / f"qmt_range_reversion_core4_roll_window_summary_{MODEL_TAG}.csv"
SUMMARY_JSON_PATH: Path = OUTPUT_DIR / f"qmt_range_reversion_core4_product_signal_logic_audit_summary_{MODEL_TAG}.json"
REPORT_PATH: Path = OUTPUT_DIR / f"qmt_range_reversion_core4_product_signal_logic_audit_report_{MODEL_TAG}.md"


def _safe_float(value: Any, default: float = float("nan")) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _pct_change(now: float, prev: float) -> float:
    if pd.isna(now) or pd.isna(prev) or abs(prev) <= 1e-12:
        return float("nan")
    return now / prev - 1.0


def _to_naive_date(value: Any) -> pd.Timestamp:
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is not None:
        timestamp = timestamp.tz_localize(None)
    return timestamp.normalize()


def _load_core_products() -> list[str]:
    universe = pd.read_csv(CORE_UNIVERSE_PATH)
    if "eligible" in universe.columns:
        universe = universe[pd.to_numeric(universe["eligible"], errors="coerce").fillna(0).astype(int) == 1]
    column = "product_vt_symbol" if "product_vt_symbol" in universe.columns else "vt_symbol"
    return sorted(universe[column].dropna().astype(str).unique().tolist())


def _load_bar_history(products: list[str]) -> pd.DataFrame:
    engine, _ = build_backtest_engine(
        preload_start=PRELOAD_START_DT,
        backtest_end=END_DT,
        capital=200_000,
        product_universe_csv_path=str(CORE_UNIVERSE_PATH),
    )
    engine.load_data()

    rows: list[dict[str, Any]] = []
    for (dt, vt_symbol), bar in engine.history_data.items():
        rows.append(
            {
                "date": _to_naive_date(dt),
                "vt_symbol": str(vt_symbol),
                "open": _safe_float(bar.open_price),
                "high": _safe_float(bar.high_price),
                "low": _safe_float(bar.low_price),
                "close": _safe_float(bar.close_price),
                "volume": _safe_float(getattr(bar, "volume", float("nan"))),
                "open_interest": _safe_float(getattr(bar, "open_interest", float("nan"))),
            }
        )
    bars = pd.DataFrame(rows)
    if bars.empty:
        return bars
    bars = bars.sort_values(["vt_symbol", "date"]).reset_index(drop=True)
    return bars


def _bar_lookup(bars: pd.DataFrame) -> dict[tuple[str, pd.Timestamp], dict[str, Any]]:
    return {
        (str(row.vt_symbol), pd.Timestamp(row.date).normalize()): row._asdict()
        for row in bars.itertuples(index=False)
    }


def _build_roll_events(products: list[str], bars: pd.DataFrame) -> pd.DataFrame:
    mapping = pd.read_csv(ALL_FUTURES_MAPPING_PATH)
    mapping["date"] = pd.to_datetime(mapping["date"]).dt.normalize()
    mapping["main_contract_vt"] = mapping["main_contract_vt"].fillna("").astype(str)
    mapping = mapping[mapping["continuous_symbol_vt"].isin(products)].copy()
    mapping = mapping[mapping["main_contract_vt"] != ""].copy()
    mapping = mapping.sort_values(["continuous_symbol_vt", "date"]).reset_index(drop=True)
    lookup = _bar_lookup(bars)

    rows: list[dict[str, Any]] = []
    for product, group in mapping.groupby("continuous_symbol_vt", sort=False):
        group = group.reset_index(drop=True)
        for index in range(1, len(group)):
            current_contract = str(group.loc[index, "main_contract_vt"])
            previous_contract = str(group.loc[index - 1, "main_contract_vt"])
            if current_contract == previous_contract:
                continue

            roll_date = pd.Timestamp(group.loc[index, "date"]).normalize()
            prev_date = pd.Timestamp(group.loc[index - 1, "date"]).normalize()
            old_prev = lookup.get((previous_contract, prev_date), {})
            old_today = lookup.get((previous_contract, roll_date), {})
            new_prev = lookup.get((current_contract, prev_date), {})
            new_today = lookup.get((current_contract, roll_date), {})
            old_prev_close = _safe_float(old_prev.get("close"))
            old_today_close = _safe_float(old_today.get("close"))
            new_prev_close = _safe_float(new_prev.get("close"))
            new_today_close = _safe_float(new_today.get("close"))
            spliced_ret = _pct_change(new_today_close, old_prev_close)
            new_own_ret = _pct_change(new_today_close, new_prev_close)
            old_own_ret = _pct_change(old_today_close, old_prev_close)
            basis_jump = spliced_ret - new_own_ret if not pd.isna(new_own_ret) else spliced_ret

            rows.append(
                {
                    "product_vt_symbol": product,
                    "roll_date": roll_date,
                    "previous_mapping_date": prev_date,
                    "old_contract": previous_contract,
                    "new_contract": current_contract,
                    "old_prev_close": old_prev_close,
                    "old_today_close": old_today_close,
                    "new_prev_close": new_prev_close,
                    "new_today_close": new_today_close,
                    "spliced_return_pct": spliced_ret * 100.0,
                    "new_contract_own_return_pct": new_own_ret * 100.0,
                    "old_contract_own_return_pct": old_own_ret * 100.0,
                    "basis_jump_pct": basis_jump * 100.0,
                    "abs_basis_jump_pct": abs(basis_jump) * 100.0,
                }
            )
    return pd.DataFrame(rows)


def _attach_roll_exposure(round_trips: pd.DataFrame, roll_events: pd.DataFrame) -> pd.DataFrame:
    if round_trips.empty:
        return round_trips

    result = round_trips.copy()
    result["entry_date"] = result["entry_datetime"].map(_to_naive_date)
    result["exit_date"] = result["exit_datetime"].map(_to_naive_date)
    roll_by_product: dict[str, list[pd.Timestamp]] = {}
    event_by_key: dict[tuple[str, pd.Timestamp], dict[str, Any]] = {}

    for row in roll_events.itertuples(index=False):
        product = str(row.product_vt_symbol)
        roll_date = pd.Timestamp(row.roll_date).normalize()
        roll_by_product.setdefault(product, []).append(roll_date)
        event_by_key[(product, roll_date)] = row._asdict()
    for product in roll_by_product:
        roll_by_product[product] = sorted(roll_by_product[product])

    nearest_dates: list[pd.Timestamp | pd.NaT] = []
    days_since_roll: list[float] = []
    abs_basis_jump_pct: list[float] = []
    roll_old_contract: list[str] = []
    roll_new_contract: list[str] = []

    for row in result.itertuples(index=False):
        product = str(row.product_vt_symbol)
        entry_date = _to_naive_date(row.entry_date)
        roll_dates = roll_by_product.get(product, [])
        index = bisect_right(roll_dates, entry_date) - 1
        if index < 0:
            nearest_dates.append(pd.NaT)
            days_since_roll.append(float("nan"))
            abs_basis_jump_pct.append(float("nan"))
            roll_old_contract.append("")
            roll_new_contract.append("")
            continue
        roll_date = roll_dates[index]
        event = event_by_key[(product, roll_date)]
        nearest_dates.append(roll_date)
        days_since_roll.append(float((entry_date - roll_date).days))
        abs_basis_jump_pct.append(_safe_float(event.get("abs_basis_jump_pct")))
        roll_old_contract.append(str(event.get("old_contract", "")))
        roll_new_contract.append(str(event.get("new_contract", "")))

    result["nearest_prev_roll_date"] = nearest_dates
    result["calendar_days_since_roll"] = days_since_roll
    result["nearest_roll_abs_basis_jump_pct"] = abs_basis_jump_pct
    result["nearest_roll_old_contract"] = roll_old_contract
    result["nearest_roll_new_contract"] = roll_new_contract
    for window in [0, 1, 3, 5, 10, 20]:
        result[f"entry_within_{window}d_after_roll"] = (
            pd.to_numeric(result["calendar_days_since_roll"], errors="coerce").between(0, window, inclusive="both")
        )
    return result


def _summarize_roll_windows(entry_roll: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    if entry_roll.empty:
        return pd.DataFrame(rows)
    total_pnl = float(entry_roll["pnl"].sum())
    total_trips = int(len(entry_roll))
    for window in [0, 1, 3, 5, 10, 20]:
        flag = f"entry_within_{window}d_after_roll"
        group = entry_roll[entry_roll[flag]].copy()
        rows.append(
            {
                "window": f"{window}d_after_roll",
                "round_trips": int(len(group)),
                "round_trip_share": int(len(group)) / total_trips if total_trips else 0.0,
                "pnl": float(group["pnl"].sum()) if not group.empty else 0.0,
                "pnl_share": float(group["pnl"].sum()) / total_pnl if abs(total_pnl) > 1e-12 else 0.0,
                "avg_pnl": float(group["pnl"].mean()) if not group.empty else 0.0,
                "win_rate": float((group["pnl"] > 0).mean()) if not group.empty else 0.0,
                "worst_pnl": float(group["pnl"].min()) if not group.empty else 0.0,
                "avg_abs_basis_jump_pct": float(group["nearest_roll_abs_basis_jump_pct"].mean()) if not group.empty else 0.0,
            }
        )
    non_roll = entry_roll[~entry_roll["entry_within_20d_after_roll"]].copy()
    rows.append(
        {
            "window": "outside_20d_after_roll",
            "round_trips": int(len(non_roll)),
            "round_trip_share": int(len(non_roll)) / total_trips if total_trips else 0.0,
            "pnl": float(non_roll["pnl"].sum()) if not non_roll.empty else 0.0,
            "pnl_share": float(non_roll["pnl"].sum()) / total_pnl if abs(total_pnl) > 1e-12 else 0.0,
            "avg_pnl": float(non_roll["pnl"].mean()) if not non_roll.empty else 0.0,
            "win_rate": float((non_roll["pnl"] > 0).mean()) if not non_roll.empty else 0.0,
            "worst_pnl": float(non_roll["pnl"].min()) if not non_roll.empty else 0.0,
            "avg_abs_basis_jump_pct": float(non_roll["nearest_roll_abs_basis_jump_pct"].mean()) if not non_roll.empty else 0.0,
        }
    )
    return pd.DataFrame(rows)


def _write_report(roll_events: pd.DataFrame, entry_roll: pd.DataFrame, window_summary: pd.DataFrame) -> None:
    product_roll = (
        roll_events.groupby("product_vt_symbol", dropna=False)
        .agg(
            roll_events=("roll_date", "size"),
            avg_abs_basis_jump_pct=("abs_basis_jump_pct", "mean"),
            median_abs_basis_jump_pct=("abs_basis_jump_pct", "median"),
            max_abs_basis_jump_pct=("abs_basis_jump_pct", "max"),
        )
        .reset_index()
        if not roll_events.empty
        else pd.DataFrame()
    )
    worst_rolls = roll_events.sort_values("abs_basis_jump_pct", ascending=False).head(15)
    near_roll_trades = (
        entry_roll[entry_roll["entry_within_5d_after_roll"]]
        .sort_values(["pnl", "entry_datetime"], ascending=[True, True])
        .head(20)
        if not entry_roll.empty
        else pd.DataFrame()
    )

    lines = [
        "# QMT Range Reversion Core4 Product Signal Logic Audit",
        "",
        "## Scope",
        "- Reads existing v6 trades and bar history only; no new backtest is run.",
        "- Tests whether the current product-continuous signal series injects unadjusted roll jumps into range indicators.",
        "",
        "## Roll Jump Summary",
        product_roll.to_markdown(index=False) if not product_roll.empty else "- Empty.",
        "",
        "## Worst Roll Jumps",
        worst_rolls.to_markdown(index=False) if not worst_rolls.empty else "- Empty.",
        "",
        "## Trade Exposure Near Roll",
        window_summary.to_markdown(index=False) if not window_summary.empty else "- Empty.",
        "",
        "## Worst Trades Within 5 Calendar Days After Roll",
        near_roll_trades[
            [
                "product_vt_symbol",
                "contract_vt_symbol",
                "direction",
                "entry_datetime",
                "exit_datetime",
                "pnl",
                "exit_reason",
                "nearest_prev_roll_date",
                "calendar_days_since_roll",
                "nearest_roll_abs_basis_jump_pct",
            ]
        ].to_markdown(index=False)
        if not near_roll_trades.empty
        else "- Empty.",
    ]
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    products = _load_core_products()
    bars = _load_bar_history(products)
    roll_events = _build_roll_events(products, bars)

    trades = pd.read_csv(TRADES_PATH)
    entries = pd.read_csv(ENTRY_RISK_PATH)
    round_trips = _build_round_trips(trades, entries)
    entry_roll = _attach_roll_exposure(round_trips, roll_events)
    window_summary = _summarize_roll_windows(entry_roll)

    roll_events.to_csv(ROLL_EVENTS_PATH, index=False, encoding="utf-8-sig")
    entry_roll.to_csv(ENTRY_ROLL_PATH, index=False, encoding="utf-8-sig")
    window_summary.to_csv(ROLL_WINDOW_SUMMARY_PATH, index=False, encoding="utf-8-sig")

    breakthrough_suspect = bool(
        not roll_events.empty
        and float(roll_events["abs_basis_jump_pct"].quantile(0.90)) >= 1.0
        and not entry_roll.empty
        and float(entry_roll["entry_within_5d_after_roll"].mean()) >= 0.2
    )
    payload = {
        "model_tag": MODEL_TAG,
        "source_prefix": SOURCE_PREFIX,
        "products": products,
        "roll_events": int(len(roll_events)),
        "round_trips": int(len(entry_roll)),
        "median_abs_basis_jump_pct": float(roll_events["abs_basis_jump_pct"].median()) if not roll_events.empty else 0.0,
        "p90_abs_basis_jump_pct": float(roll_events["abs_basis_jump_pct"].quantile(0.90)) if not roll_events.empty else 0.0,
        "max_abs_basis_jump_pct": float(roll_events["abs_basis_jump_pct"].max()) if not roll_events.empty else 0.0,
        "entry_share_within_5d_after_roll": float(entry_roll["entry_within_5d_after_roll"].mean()) if not entry_roll.empty else 0.0,
        "pnl_within_5d_after_roll": float(
            entry_roll.loc[entry_roll["entry_within_5d_after_roll"], "pnl"].sum()
        )
        if not entry_roll.empty
        else 0.0,
        "breakthrough_suspect": breakthrough_suspect,
        "outputs": {
            "roll_events": str(ROLL_EVENTS_PATH),
            "entry_roll_exposure": str(ENTRY_ROLL_PATH),
            "roll_window_summary": str(ROLL_WINDOW_SUMMARY_PATH),
            "report": str(REPORT_PATH),
        },
    }
    SUMMARY_JSON_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(roll_events, entry_roll, window_summary)

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    print(window_summary.to_string(index=False))
    if not roll_events.empty:
        print(roll_events.sort_values("abs_basis_jump_pct", ascending=False).head(10).to_string(index=False))


if __name__ == "__main__":
    main()
