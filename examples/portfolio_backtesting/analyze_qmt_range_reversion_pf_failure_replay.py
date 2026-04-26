from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from analyze_qmt_range_reversion_core4_v3_exit_structure import _build_round_trips
from qmt_universe import END_DT, PRELOAD_START_DT
from run_qmt_range_reversion_core4_directed_backtest import CORE_UNIVERSE_PATH
from run_qmt_roll_backtest import build_backtest_engine


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"
SOURCE_PREFIX: str = "qmt_range_reversion_core4_directed_product_signal_no_streak_kill_v3"
MODEL_TAG: str = "range_reversion_pf_failure_replay_v1"

TRADES_PATH: Path = OUTPUT_DIR / f"{SOURCE_PREFIX}_trades_2020_2026_04.csv"
ENTRY_RISK_PATH: Path = OUTPUT_DIR / f"{SOURCE_PREFIX}_entry_risk_diagnostics_2020_2026_04.csv"

PF_ROUND_TRIPS_PATH: Path = OUTPUT_DIR / f"qmt_range_reversion_pf_failure_roundtrips_{MODEL_TAG}.csv"
PF_EXIT_SUMMARY_PATH: Path = OUTPUT_DIR / f"qmt_range_reversion_pf_failure_exit_summary_{MODEL_TAG}.csv"
PF_YEAR_SUMMARY_PATH: Path = OUTPUT_DIR / f"qmt_range_reversion_pf_failure_year_summary_{MODEL_TAG}.csv"
PF_BUCKET_SUMMARY_PATH: Path = OUTPUT_DIR / f"qmt_range_reversion_pf_failure_bucket_summary_{MODEL_TAG}.csv"
SUMMARY_JSON_PATH: Path = OUTPUT_DIR / f"qmt_range_reversion_pf_failure_summary_{MODEL_TAG}.json"
REPORT_PATH: Path = OUTPUT_DIR / f"qmt_range_reversion_pf_failure_report_{MODEL_TAG}.md"


def _safe_float(value: Any, default: float = float("nan")) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result


def _load_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if not TRADES_PATH.exists():
        raise FileNotFoundError(TRADES_PATH)
    if not ENTRY_RISK_PATH.exists():
        raise FileNotFoundError(ENTRY_RISK_PATH)
    trades = pd.read_csv(TRADES_PATH)
    entries = pd.read_csv(ENTRY_RISK_PATH)
    round_trips = _build_round_trips(trades, entries)
    return trades, entries, round_trips


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
                "datetime": pd.Timestamp(dt),
                "date": pd.Timestamp(dt).date(),
                "vt_symbol": vt_symbol,
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
        channel_high = group["high"].rolling(20).max()
        channel_low = group["low"].rolling(20).min()
        channel_width = (channel_high - channel_low).replace(0, pd.NA)
        group["channel_middle_20"] = (channel_high + channel_low) / 2.0
        group["channel_position_20"] = (group["close"] - channel_low) / channel_width
        group["ret_1d"] = group["close"].pct_change(1)
        group["ret_5d"] = group["close"].pct_change(5)
        group["ret_20d"] = group["close"].pct_change(20)
        group["range_pct_20"] = channel_width / group["close"]
        pieces.append(group)
    return pd.concat(pieces, ignore_index=True)


def _entry_lookup(entries: pd.DataFrame) -> dict[tuple[str, date], dict[str, Any]]:
    lookup: dict[tuple[str, date], dict[str, Any]] = {}
    if entries.empty:
        return lookup
    entries = entries.copy()
    entries["entry_date_obj"] = pd.to_datetime(entries["date"]).dt.date
    for row in entries.itertuples(index=False):
        key = (str(row.contract_vt_symbol), row.entry_date_obj)
        lookup[key] = row._asdict()
    return lookup


def _first_date(series: pd.Series) -> str:
    matches = series[series].index
    if len(matches) == 0:
        return ""
    return str(matches[0])


def _path_metrics_for_round_trip(
    row: pd.Series,
    bars_by_contract: dict[str, pd.DataFrame],
    entry_rows: dict[tuple[str, date], dict[str, Any]],
) -> dict[str, Any]:
    contract = str(row["contract_vt_symbol"])
    direction = str(row["direction"])
    entry_dt = pd.Timestamp(row["entry_datetime"])
    exit_dt = pd.Timestamp(row["exit_datetime"])
    entry_date = entry_dt.date()
    exit_date = exit_dt.date()
    entry_price = _safe_float(row["entry_price"])
    exit_price = _safe_float(row["exit_price"])
    volume = _safe_float(row["volume"], 0.0)

    entry_row = entry_rows.get((contract, entry_date), {})
    stop_price = _safe_float(entry_row.get("stop_price"))
    stop_distance = abs(entry_price - stop_price) if pd.notna(stop_price) else float("nan")
    size = _safe_float(entry_row.get("size"), 1.0)

    contract_bars = bars_by_contract.get(contract, pd.DataFrame())
    if contract_bars.empty:
        return {
            "bar_count_after_entry": 0,
            "path_missing": 1,
        }

    contract_bars = contract_bars.set_index("date", drop=False)
    entry_features = contract_bars.loc[entry_date].to_dict() if entry_date in contract_bars.index else {}
    path = contract_bars[(contract_bars["date"] > entry_date) & (contract_bars["date"] <= exit_date)].copy()
    if path.empty and exit_date in contract_bars.index:
        path = contract_bars[contract_bars["date"] == exit_date].copy()

    metrics: dict[str, Any] = {
        "bar_count_after_entry": int(len(path)),
        "path_missing": int(path.empty),
        "entry_rsi": _safe_float(entry_row.get("streak_entry_structure_risk_recovery_rsi_value")),
        "entry_stop_distance": stop_distance,
        "entry_stop_distance_pct": stop_distance / entry_price if entry_price > 0 and pd.notna(stop_distance) else float("nan"),
        "entry_channel_position_20": _safe_float(entry_features.get("channel_position_20")),
        "entry_channel_middle_20": _safe_float(entry_features.get("channel_middle_20")),
        "entry_ret_1d": _safe_float(entry_features.get("ret_1d")),
        "entry_ret_5d": _safe_float(entry_features.get("ret_5d")),
        "entry_ret_20d": _safe_float(entry_features.get("ret_20d")),
        "entry_range_pct_20": _safe_float(entry_features.get("range_pct_20")),
    }
    if path.empty:
        return metrics

    path = path.set_index("date", drop=False)
    if direction == "long":
        adverse_move = float(path["low"].min()) - entry_price
        favorable_move = float(path["high"].max()) - entry_price
        initial_stop_hit_mask = path["low"] <= stop_price if pd.notna(stop_price) else pd.Series(False, index=path.index)
        middle_hit_mask = path["close"] >= path["channel_middle_20"]
    else:
        adverse_move = entry_price - float(path["high"].max())
        favorable_move = entry_price - float(path["low"].min())
        initial_stop_hit_mask = path["high"] >= stop_price if pd.notna(stop_price) else pd.Series(False, index=path.index)
        middle_hit_mask = path["close"] <= path["channel_middle_20"]

    pnl = _safe_float(row["pnl"])
    mae_cash = min(adverse_move, 0.0) * volume * size
    mfe_cash = max(favorable_move, 0.0) * volume * size
    first_initial_stop_date = _first_date(initial_stop_hit_mask.fillna(False))
    dynamic_stop_hit_mask, first_dynamic_stop_price = _dynamic_previous_day_stop_hits(
        direction=direction,
        contract_bars=contract_bars,
        path=path,
        initial_stop_price=stop_price,
    )
    first_stop_date = _first_date(dynamic_stop_hit_mask.fillna(False))
    first_middle_date = _first_date(middle_hit_mask.fillna(False))

    metrics.update(
        {
            "mae_price": min(adverse_move, 0.0),
            "mfe_price": max(favorable_move, 0.0),
            "mae_cash": mae_cash,
            "mfe_cash": mfe_cash,
            "mae_r": abs(min(adverse_move, 0.0)) / stop_distance if stop_distance > 0 else float("nan"),
            "mfe_r": max(favorable_move, 0.0) / stop_distance if stop_distance > 0 else float("nan"),
            "pnl_to_mfe_ratio": pnl / mfe_cash if mfe_cash > 0 else float("nan"),
            "first_initial_stop_date": first_initial_stop_date,
            "first_stop_date": first_stop_date,
            "first_dynamic_stop_price": first_dynamic_stop_price,
            "first_middle_date": first_middle_date,
            "stop_before_middle": int(bool(first_stop_date and (not first_middle_date or first_stop_date <= first_middle_date))),
            "middle_before_stop": int(bool(first_middle_date and (not first_stop_date or first_middle_date < first_stop_date))),
            "exit_price_vs_entry_pct": (exit_price / entry_price - 1.0) if entry_price > 0 else float("nan"),
        }
    )
    return metrics


def _dynamic_previous_day_stop_hits(
    *,
    direction: str,
    contract_bars: pd.DataFrame,
    path: pd.DataFrame,
    initial_stop_price: float,
) -> tuple[pd.Series, float]:
    if pd.isna(initial_stop_price) or path.empty:
        return pd.Series(False, index=path.index), float("nan")

    history = contract_bars.set_index("date", drop=False).sort_index()
    current_stop = float(initial_stop_price)
    hit_values: list[bool] = []
    hit_index: list[date] = []
    first_hit_stop = float("nan")

    for path_date, bar in path.iterrows():
        prior = history[history["date"] < path_date].tail(1)
        if not prior.empty:
            previous = prior.iloc[-1]
            if direction == "long":
                current_stop = max(current_stop, _safe_float(previous.get("low"), current_stop))
            else:
                current_stop = min(current_stop, _safe_float(previous.get("high"), current_stop))

        if direction == "long":
            hit = _safe_float(bar.get("low")) <= current_stop
        else:
            hit = _safe_float(bar.get("high")) >= current_stop

        if hit and pd.isna(first_hit_stop):
            first_hit_stop = current_stop
        hit_values.append(bool(hit))
        hit_index.append(path_date)

    return pd.Series(hit_values, index=hit_index), first_hit_stop


def _enrich_round_trips(round_trips: pd.DataFrame, entries: pd.DataFrame, bars: pd.DataFrame) -> pd.DataFrame:
    if round_trips.empty:
        return round_trips
    bars_by_contract = {
        str(contract): group.sort_values("date").reset_index(drop=True)
        for contract, group in bars.groupby("vt_symbol", sort=False)
    }
    entry_rows = _entry_lookup(entries)
    enriched_rows: list[dict[str, Any]] = []
    for _, row in round_trips.iterrows():
        result = row.to_dict()
        result.update(_path_metrics_for_round_trip(row, bars_by_contract, entry_rows))
        result["holding_calendar_days"] = (
            pd.Timestamp(row["exit_datetime"]).date() - pd.Timestamp(row["entry_datetime"]).date()
        ).days
        enriched_rows.append(result)
    return pd.DataFrame(enriched_rows)


def _summarize(frame: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame()
    summary = frame.groupby(group_cols, dropna=False).agg(
        round_trips=("pnl", "size"),
        pnl=("pnl", "sum"),
        avg_pnl=("pnl", "mean"),
        win_rate=("pnl", lambda s: float((s > 0).mean())),
        base_stop_rate=("exit_reason", lambda s: float(s.astype(str).str.contains("base_stop").mean())),
        stop_before_middle_rate=("stop_before_middle", "mean"),
        middle_before_stop_rate=("middle_before_stop", "mean"),
        avg_holding_days=("holding_calendar_days", "mean"),
        avg_mae_r=("mae_r", "mean"),
        avg_mfe_r=("mfe_r", "mean"),
        avg_entry_stop_distance_pct=("entry_stop_distance_pct", "mean"),
    ).reset_index()
    return summary.sort_values(["pnl", "round_trips"], ascending=[False, False]).reset_index(drop=True)


def _bucket_summary(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame()

    bucket_frames: list[pd.DataFrame] = []
    bucket_specs = {
        "entry_rsi_bucket": pd.cut(
            frame["entry_rsi"],
            bins=[-float("inf"), 30.0, 35.0, 40.0, float("inf")],
            labels=["<=30", "30-35", "35-40", ">40"],
        ),
        "entry_channel_position_bucket": pd.cut(
            frame["entry_channel_position_20"],
            bins=[-float("inf"), 0.15, 0.25, 0.35, float("inf")],
            labels=["<=0.15", "0.15-0.25", "0.25-0.35", ">0.35"],
        ),
        "entry_stop_distance_pct_bucket": pd.cut(
            frame["entry_stop_distance_pct"],
            bins=[-float("inf"), 0.02, 0.03, 0.04, float("inf")],
            labels=["<=2%", "2%-3%", "3%-4%", ">4%"],
        ),
        "entry_ret_5d_bucket": pd.cut(
            frame["entry_ret_5d"],
            bins=[-float("inf"), -0.03, 0.0, 0.03, float("inf")],
            labels=["<=-3%", "-3%-0", "0-3%", ">3%"],
        ),
    }

    working = frame.copy()
    for bucket_name, bucket_values in bucket_specs.items():
        working[bucket_name] = bucket_values.astype("object").fillna("missing")
        summary = _summarize(working, [bucket_name])
        if not summary.empty:
            summary.insert(0, "bucket_type", bucket_name)
            summary = summary.rename(columns={bucket_name: "bucket"})
            bucket_frames.append(summary)

    if not bucket_frames:
        return pd.DataFrame()
    return pd.concat(bucket_frames, ignore_index=True)


def _write_report(
    pf_round_trips: pd.DataFrame,
    exit_summary: pd.DataFrame,
    year_summary: pd.DataFrame,
    bucket_summary: pd.DataFrame,
) -> None:
    lines: list[str] = [
        "# QMT Range Reversion PF Failure Replay",
        "",
        "## Conclusion",
        f"- PF round trips: `{len(pf_round_trips)}`.",
        f"- PF total raw pnl: `{float(pf_round_trips['pnl'].sum()) if not pf_round_trips.empty else 0.0:.2f}`.",
        "- This is attribution only; it does not change strategy rules.",
        "",
        "## Exit Summary",
        exit_summary.to_markdown(index=False) if not exit_summary.empty else "- Empty.",
        "",
        "## Year Summary",
        year_summary.to_markdown(index=False) if not year_summary.empty else "- Empty.",
        "",
        "## Bucket Summary",
        bucket_summary.to_markdown(index=False) if not bucket_summary.empty else "- Empty.",
        "",
        "## Outputs",
        f"- pf_round_trips: `{PF_ROUND_TRIPS_PATH}`",
        f"- exit_summary: `{PF_EXIT_SUMMARY_PATH}`",
        f"- year_summary: `{PF_YEAR_SUMMARY_PATH}`",
        f"- bucket_summary: `{PF_BUCKET_SUMMARY_PATH}`",
    ]
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    _, entries, round_trips = _load_inputs()
    contracts = {str(value) for value in round_trips["contract_vt_symbol"].dropna().unique()}
    bars = _load_bar_history(contracts)
    enriched = _enrich_round_trips(round_trips, entries, bars)
    pf_round_trips = enriched[enriched["product_vt_symbol"].astype(str).eq("PF.CZCE")].copy()
    if not pf_round_trips.empty:
        pf_round_trips["entry_year"] = pd.to_datetime(pf_round_trips["entry_datetime"]).dt.year

    exit_summary = _summarize(pf_round_trips, ["exit_reason"])
    year_summary = _summarize(pf_round_trips, ["entry_year"])
    bucket_summary = _bucket_summary(pf_round_trips)

    pf_round_trips.to_csv(PF_ROUND_TRIPS_PATH, index=False, encoding="utf-8-sig")
    exit_summary.to_csv(PF_EXIT_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    year_summary.to_csv(PF_YEAR_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    bucket_summary.to_csv(PF_BUCKET_SUMMARY_PATH, index=False, encoding="utf-8-sig")

    payload = {
        "model_tag": MODEL_TAG,
        "source_prefix": SOURCE_PREFIX,
        "pf_round_trips": int(len(pf_round_trips)),
        "pf_total_pnl": float(pf_round_trips["pnl"].sum()) if not pf_round_trips.empty else 0.0,
        "pf_win_rate": float((pf_round_trips["pnl"] > 0).mean()) if not pf_round_trips.empty else 0.0,
        "pf_base_stop_rate": float(pf_round_trips["exit_reason"].astype(str).str.contains("base_stop").mean())
        if not pf_round_trips.empty
        else 0.0,
        "pf_stop_before_middle_rate": float(pf_round_trips["stop_before_middle"].mean())
        if not pf_round_trips.empty and "stop_before_middle" in pf_round_trips
        else 0.0,
        "outputs": {
            "pf_round_trips": str(PF_ROUND_TRIPS_PATH),
            "exit_summary": str(PF_EXIT_SUMMARY_PATH),
            "year_summary": str(PF_YEAR_SUMMARY_PATH),
            "bucket_summary": str(PF_BUCKET_SUMMARY_PATH),
            "report": str(REPORT_PATH),
        },
    }
    SUMMARY_JSON_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(pf_round_trips, exit_summary, year_summary, bucket_summary)

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    print(exit_summary.to_string(index=False))
    print(year_summary.to_string(index=False))
    print(bucket_summary.to_string(index=False))


if __name__ == "__main__":
    main()
