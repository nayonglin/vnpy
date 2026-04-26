from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from analyze_qmt_range_reversion_core4_v3_exit_structure import _build_round_trips
from qmt_universe import END_DT, PRELOAD_START_DT
from run_qmt_range_reversion_core4_directed_backtest import CORE_UNIVERSE_PATH
from run_qmt_roll_backtest import build_backtest_engine


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"
SOURCE_PREFIX: str = "qmt_range_reversion_core4_directed_product_signal_back_adjusted_v7"
MODEL_TAG: str = "range_reversion_core4_v7_weak_window_trade_replay_v1"

TRADES_PATH: Path = OUTPUT_DIR / f"{SOURCE_PREFIX}_trades_2020_2026_04.csv"
ENTRY_RISK_PATH: Path = OUTPUT_DIR / f"{SOURCE_PREFIX}_entry_risk_diagnostics_2020_2026_04.csv"

DETAIL_PATH: Path = OUTPUT_DIR / f"qmt_range_reversion_core4_v7_weak_window_roundtrips_{MODEL_TAG}.csv"
GROUP_SUMMARY_PATH: Path = OUTPUT_DIR / f"qmt_range_reversion_core4_v7_weak_window_group_summary_{MODEL_TAG}.csv"
FAILURE_SUMMARY_PATH: Path = OUTPUT_DIR / f"qmt_range_reversion_core4_v7_weak_window_failure_summary_{MODEL_TAG}.csv"
SUMMARY_JSON_PATH: Path = OUTPUT_DIR / f"qmt_range_reversion_core4_v7_weak_window_trade_replay_summary_{MODEL_TAG}.json"
REPORT_PATH: Path = OUTPUT_DIR / f"qmt_range_reversion_core4_v7_weak_window_trade_replay_report_{MODEL_TAG}.md"

WEAK_START: pd.Timestamp = pd.Timestamp("2022-12-20")
WEAK_END: pd.Timestamp = pd.Timestamp("2023-06-29")


def _safe_float(value: Any, default: float = float("nan")) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _to_local_date(value: Any) -> pd.Timestamp:
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is not None:
        timestamp = timestamp.tz_localize(None)
    return timestamp.normalize()


def _load_round_trips() -> tuple[pd.DataFrame, pd.DataFrame]:
    trades = pd.read_csv(TRADES_PATH)
    entries = pd.read_csv(ENTRY_RISK_PATH)
    round_trips = _build_round_trips(trades, entries)
    if round_trips.empty:
        return round_trips, entries
    round_trips["entry_date"] = round_trips["entry_datetime"].map(_to_local_date)
    round_trips["exit_date"] = round_trips["exit_datetime"].map(_to_local_date)
    round_trips["entry_year"] = round_trips["entry_date"].dt.year
    return round_trips, entries


def _load_bar_history(contracts: set[str]) -> pd.DataFrame:
    engine, _ = build_backtest_engine(
        preload_start=PRELOAD_START_DT,
        backtest_end=END_DT,
        capital=200_000,
        product_universe_csv_path=str(CORE_UNIVERSE_PATH),
    )
    engine.load_data()

    rows: list[dict[str, Any]] = []
    for (dt, vt_symbol), bar in engine.history_data.items():
        if vt_symbol not in contracts:
            continue
        rows.append(
            {
                "date": _to_local_date(dt),
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
    pieces: list[pd.DataFrame] = []
    for _, group in bars.groupby("vt_symbol", sort=False):
        group = group.copy()
        group["ret_5d"] = group["close"].pct_change(5)
        group["ret_20d"] = group["close"].pct_change(20)
        channel_high = group["high"].rolling(20).max()
        channel_low = group["low"].rolling(20).min()
        channel_width = (channel_high - channel_low).replace(0, pd.NA)
        group["channel_position_20"] = (group["close"] - channel_low) / channel_width
        pieces.append(group)
    return pd.concat(pieces, ignore_index=True)


def _entry_lookup(entries: pd.DataFrame) -> dict[tuple[str, str], dict[str, Any]]:
    lookup: dict[tuple[str, str], dict[str, Any]] = {}
    for row in entries.itertuples(index=False):
        lookup[(str(row.contract_vt_symbol), str(row.datetime))] = row._asdict()
    return lookup


def _path_metrics(row: pd.Series, history: pd.DataFrame, entry_fields: dict[str, Any]) -> dict[str, Any]:
    entry_date = _to_local_date(row["entry_date"])
    exit_date = _to_local_date(row["exit_date"])
    path = history[(history["date"] >= entry_date) & (history["date"] <= exit_date)].copy()
    after = history[(history["date"] > exit_date)].head(10).copy()
    prior = history[history["date"] < entry_date].tail(1).copy()

    entry_price = float(row["entry_price"])
    exit_price = float(row["exit_price"])
    direction = str(row["direction"])
    stop_price = _safe_float(entry_fields.get("stop_price"))
    stop_distance = abs(entry_price - stop_price) if not pd.isna(stop_price) else _safe_float(
        entry_fields.get("stop_distance")
    )
    if pd.isna(stop_distance) or stop_distance <= 0:
        stop_distance = max(abs(entry_price) * 0.02, 1e-9)

    if path.empty:
        mfe = mae = float("nan")
        bars_held = 0
    elif direction == "long":
        mfe = float(path["high"].max()) - entry_price
        mae = entry_price - float(path["low"].min())
        bars_held = len(path)
    else:
        mfe = entry_price - float(path["low"].min())
        mae = float(path["high"].max()) - entry_price
        bars_held = len(path)

    if after.empty:
        post_10d_favorable = float("nan")
        post_10d_adverse = float("nan")
    elif direction == "long":
        post_10d_favorable = float(after["high"].max()) - exit_price
        post_10d_adverse = exit_price - float(after["low"].min())
    else:
        post_10d_favorable = exit_price - float(after["low"].min())
        post_10d_adverse = float(after["high"].max()) - exit_price

    entry_pre_ret_5d = _safe_float(prior["ret_5d"].iloc[-1]) if not prior.empty else float("nan")
    entry_pre_ret_20d = _safe_float(prior["ret_20d"].iloc[-1]) if not prior.empty else float("nan")
    entry_channel_position_20 = (
        _safe_float(prior["channel_position_20"].iloc[-1]) if not prior.empty else float("nan")
    )

    mfe_to_risk = mfe / stop_distance if not pd.isna(mfe) else float("nan")
    mae_to_risk = mae / stop_distance if not pd.isna(mae) else float("nan")
    post_10d_favorable_to_risk = (
        post_10d_favorable / stop_distance if not pd.isna(post_10d_favorable) else float("nan")
    )

    entry_context = str(entry_fields.get("env_gate_entry_context", ""))
    exit_reason = str(row.get("exit_reason", ""))
    failure_type = "not_failure" if float(row["pnl"]) >= 0 else "unclassified_loss"
    if float(row["pnl"]) < 0:
        if entry_context == "rollover_reopen":
            failure_type = "rollover_reopen_loss"
        elif mfe_to_risk < 0.30 and mae_to_risk >= 0.70:
            failure_type = "wrong_direction_or_bad_timing"
        elif post_10d_favorable_to_risk >= 1.0:
            failure_type = "stop_too_early_then_recovered"
        elif "base_stop" in exit_reason:
            failure_type = "base_stop_no_fast_recovery"

    return {
        "bars_held": bars_held,
        "entry_context": entry_context,
        "signal": str(entry_fields.get("signal", "")),
        "rsi_value": _safe_float(entry_fields.get("streak_entry_structure_risk_recovery_rsi_value")),
        "stop_price": stop_price,
        "stop_distance": stop_distance,
        "mfe": mfe,
        "mae": mae,
        "mfe_to_risk": mfe_to_risk,
        "mae_to_risk": mae_to_risk,
        "post_10d_favorable": post_10d_favorable,
        "post_10d_adverse": post_10d_adverse,
        "post_10d_favorable_to_risk": post_10d_favorable_to_risk,
        "entry_pre_ret_5d": entry_pre_ret_5d,
        "entry_pre_ret_20d": entry_pre_ret_20d,
        "entry_channel_position_20": entry_channel_position_20,
        "failure_type": failure_type,
    }


def _target_group(row: pd.Series) -> str:
    if WEAK_START <= row["entry_date"] <= WEAK_END:
        return "weak_2022_12_to_2023_06"
    if row["entry_year"] == 2023 and row["product_vt_symbol"] == "PF.CZCE" and row["direction"] == "long":
        return "pf_2023_long"
    if row["entry_year"] == 2021 and row["product_vt_symbol"] == "cs.DCE" and row["direction"] == "short":
        return "cs_2021_short"
    return ""


def _build_detail(round_trips: pd.DataFrame, entries: pd.DataFrame, bars: pd.DataFrame) -> pd.DataFrame:
    lookup = _entry_lookup(entries)
    bars_by_contract = {contract: group for contract, group in bars.groupby("vt_symbol", sort=False)}
    rows: list[dict[str, Any]] = []
    for _, row in round_trips.iterrows():
        group = _target_group(row)
        if not group:
            continue
        contract = str(row["contract_vt_symbol"])
        entry_fields = lookup.get((contract, str(row["entry_datetime"])), {})
        history = bars_by_contract.get(contract, pd.DataFrame())
        metrics = _path_metrics(row, history, entry_fields)
        rows.append(
            {
                "target_group": group,
                "product_vt_symbol": row["product_vt_symbol"],
                "contract_vt_symbol": contract,
                "direction": row["direction"],
                "entry_datetime": row["entry_datetime"],
                "exit_datetime": row["exit_datetime"],
                "entry_price": row["entry_price"],
                "exit_price": row["exit_price"],
                "volume": row["volume"],
                "pnl": row["pnl"],
                "exit_reason": row["exit_reason"],
                **metrics,
            }
        )
    return pd.DataFrame(rows)


def _summarize(detail: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    if detail.empty:
        return pd.DataFrame()
    summary = detail.groupby(group_cols, dropna=False).agg(
        round_trips=("pnl", "size"),
        pnl=("pnl", "sum"),
        avg_pnl=("pnl", "mean"),
        win_rate=("pnl", lambda s: float((s > 0).mean())),
        avg_mfe_to_risk=("mfe_to_risk", "mean"),
        avg_mae_to_risk=("mae_to_risk", "mean"),
        avg_post_10d_favorable_to_risk=("post_10d_favorable_to_risk", "mean"),
        worst_pnl=("pnl", "min"),
        best_pnl=("pnl", "max"),
    ).reset_index()
    return summary.sort_values(["pnl", "round_trips"], ascending=[True, False]).reset_index(drop=True)


def _write_report(detail: pd.DataFrame, group_summary: pd.DataFrame, failure_summary: pd.DataFrame) -> None:
    worst_rows = detail.sort_values(["pnl", "entry_datetime"], ascending=[True, True])
    lines = [
        "# QMT Range Reversion Core4 V7 Weak Window Trade Replay",
        "",
        "## Scope",
        "- Reads existing v7 trades and bar history only; no new backtest is run.",
        "- Focuses on the worst 2022-12 to 2023-06 window, 2023 PF long losses, and 2021 cs short losses.",
        "",
        "## Group Summary",
        group_summary.to_markdown(index=False) if not group_summary.empty else "- Empty.",
        "",
        "## Failure Type Summary",
        failure_summary.to_markdown(index=False) if not failure_summary.empty else "- Empty.",
        "",
        "## Trade Detail",
        worst_rows[
            [
                "target_group",
                "product_vt_symbol",
                "contract_vt_symbol",
                "direction",
                "entry_datetime",
                "exit_datetime",
                "pnl",
                "exit_reason",
                "entry_context",
                "mfe_to_risk",
                "mae_to_risk",
                "post_10d_favorable_to_risk",
                "failure_type",
            ]
        ].to_markdown(index=False)
        if not worst_rows.empty
        else "- Empty.",
    ]
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    round_trips, entries = _load_round_trips()
    contracts = set(round_trips["contract_vt_symbol"].dropna().astype(str))
    bars = _load_bar_history(contracts)
    detail = _build_detail(round_trips, entries, bars)
    group_summary = _summarize(detail, ["target_group"])
    failure_summary = _summarize(detail, ["failure_type"])

    detail.to_csv(DETAIL_PATH, index=False, encoding="utf-8-sig")
    group_summary.to_csv(GROUP_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    failure_summary.to_csv(FAILURE_SUMMARY_PATH, index=False, encoding="utf-8-sig")

    payload = {
        "model_tag": MODEL_TAG,
        "source_prefix": SOURCE_PREFIX,
        "round_trips_reviewed": int(len(detail)),
        "total_pnl_reviewed": float(detail["pnl"].sum()) if not detail.empty else 0.0,
        "groups": group_summary.to_dict("records") if not group_summary.empty else [],
        "failure_types": failure_summary.to_dict("records") if not failure_summary.empty else [],
        "outputs": {
            "detail": str(DETAIL_PATH),
            "group_summary": str(GROUP_SUMMARY_PATH),
            "failure_summary": str(FAILURE_SUMMARY_PATH),
            "report": str(REPORT_PATH),
        },
    }
    SUMMARY_JSON_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(detail, group_summary, failure_summary)

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    print(group_summary.to_string(index=False))
    print(failure_summary.to_string(index=False))
    print(detail.sort_values(["pnl", "entry_datetime"], ascending=[True, True]).to_string(index=False))


if __name__ == "__main__":
    main()
