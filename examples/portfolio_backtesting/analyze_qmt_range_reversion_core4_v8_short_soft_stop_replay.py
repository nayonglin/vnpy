from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

from analyze_qmt_range_reversion_core4_v3_exit_structure import _build_round_trips
from analyze_qmt_range_reversion_core4_v7_weak_window_trade_replay import _load_bar_history


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"
SOURCE_PREFIX: str = "qmt_range_reversion_core4_directed_product_signal_back_adjusted_v8_two_stage_stop"
MODEL_TAG: str = "range_reversion_core4_v8_short_soft_stop_replay_v1"

TRADES_PATH: Path = OUTPUT_DIR / f"{SOURCE_PREFIX}_trades_2020_2026_04.csv"
ENTRY_RISK_PATH: Path = OUTPUT_DIR / f"{SOURCE_PREFIX}_entry_risk_diagnostics_2020_2026_04.csv"
CANDIDATES_PATH: Path = OUTPUT_DIR / f"{SOURCE_PREFIX}_entry_candidate_snapshots_2020_2026_04.csv"

DETAIL_PATH: Path = OUTPUT_DIR / f"qmt_range_reversion_core4_v8_short_roundtrip_detail_{MODEL_TAG}.csv"
SOFT_DETAIL_PATH: Path = OUTPUT_DIR / f"qmt_range_reversion_core4_v8_short_soft_stop_detail_{MODEL_TAG}.csv"
SHORT_EXIT_SUMMARY_PATH: Path = OUTPUT_DIR / f"qmt_range_reversion_core4_v8_short_exit_summary_{MODEL_TAG}.csv"
SOFT_YEAR_SUMMARY_PATH: Path = OUTPUT_DIR / f"qmt_range_reversion_core4_v8_short_soft_stop_year_summary_{MODEL_TAG}.csv"
SOFT_RSI_SUMMARY_PATH: Path = OUTPUT_DIR / f"qmt_range_reversion_core4_v8_short_soft_stop_rsi_summary_{MODEL_TAG}.csv"
SOFT_FAILURE_SUMMARY_PATH: Path = OUTPUT_DIR / f"qmt_range_reversion_core4_v8_short_soft_stop_failure_summary_{MODEL_TAG}.csv"
SUMMARY_JSON_PATH: Path = OUTPUT_DIR / f"qmt_range_reversion_core4_v8_short_soft_stop_replay_summary_{MODEL_TAG}.json"
REPORT_PATH: Path = OUTPUT_DIR / f"qmt_range_reversion_core4_v8_short_soft_stop_replay_report_{MODEL_TAG}.md"

TARGET_EXIT_REASON: str = "short_soft_base_stop_confirmed"


def _configure_paths(source_prefix: str | None = None, model_tag: str | None = None) -> None:
    global SOURCE_PREFIX
    global MODEL_TAG
    global TRADES_PATH
    global ENTRY_RISK_PATH
    global CANDIDATES_PATH
    global DETAIL_PATH
    global SOFT_DETAIL_PATH
    global SHORT_EXIT_SUMMARY_PATH
    global SOFT_YEAR_SUMMARY_PATH
    global SOFT_RSI_SUMMARY_PATH
    global SOFT_FAILURE_SUMMARY_PATH
    global SUMMARY_JSON_PATH
    global REPORT_PATH

    if source_prefix:
        SOURCE_PREFIX = source_prefix
    if model_tag:
        MODEL_TAG = model_tag

    report_prefix = "qmt_range_reversion_core4"
    if "_v9_" in SOURCE_PREFIX:
        report_prefix = "qmt_range_reversion_core4_v9"
    elif "_v8_" in SOURCE_PREFIX:
        report_prefix = "qmt_range_reversion_core4_v8"

    TRADES_PATH = OUTPUT_DIR / f"{SOURCE_PREFIX}_trades_2020_2026_04.csv"
    ENTRY_RISK_PATH = OUTPUT_DIR / f"{SOURCE_PREFIX}_entry_risk_diagnostics_2020_2026_04.csv"
    CANDIDATES_PATH = OUTPUT_DIR / f"{SOURCE_PREFIX}_entry_candidate_snapshots_2020_2026_04.csv"

    DETAIL_PATH = OUTPUT_DIR / f"{report_prefix}_short_roundtrip_detail_{MODEL_TAG}.csv"
    SOFT_DETAIL_PATH = OUTPUT_DIR / f"{report_prefix}_short_soft_stop_detail_{MODEL_TAG}.csv"
    SHORT_EXIT_SUMMARY_PATH = OUTPUT_DIR / f"{report_prefix}_short_exit_summary_{MODEL_TAG}.csv"
    SOFT_YEAR_SUMMARY_PATH = OUTPUT_DIR / f"{report_prefix}_short_soft_stop_year_summary_{MODEL_TAG}.csv"
    SOFT_RSI_SUMMARY_PATH = OUTPUT_DIR / f"{report_prefix}_short_soft_stop_rsi_summary_{MODEL_TAG}.csv"
    SOFT_FAILURE_SUMMARY_PATH = OUTPUT_DIR / f"{report_prefix}_short_soft_stop_failure_summary_{MODEL_TAG}.csv"
    SUMMARY_JSON_PATH = OUTPUT_DIR / f"{report_prefix}_short_soft_stop_replay_summary_{MODEL_TAG}.json"
    REPORT_PATH = OUTPUT_DIR / f"{report_prefix}_short_soft_stop_replay_report_{MODEL_TAG}.md"


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


def _timestamp_key(value: Any) -> str:
    timestamp = pd.Timestamp(value)
    return str(timestamp)


def _lookup_by_contract_datetime(frame: pd.DataFrame) -> dict[tuple[str, str], dict[str, Any]]:
    if frame.empty or "contract_vt_symbol" not in frame.columns or "datetime" not in frame.columns:
        return {}

    lookup: dict[tuple[str, str], dict[str, Any]] = {}
    for row in frame.itertuples(index=False):
        row_dict = row._asdict()
        lookup[(str(row_dict["contract_vt_symbol"]), _timestamp_key(row_dict["datetime"]))] = row_dict
    return lookup


def _load_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
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
    return round_trips, entries, candidates, trades


def _rsi_bucket(value: float) -> str:
    if pd.isna(value):
        return "unknown"
    if value < 60:
        return "rsi_lt_60"
    if value < 65:
        return "rsi_60_65"
    if value < 70:
        return "rsi_65_70"
    return "rsi_ge_70"


def _reconstruct_short_dynamic_stop(
    history: pd.DataFrame,
    entry_date: pd.Timestamp,
    exit_date: pd.Timestamp,
    initial_stop: float,
) -> float:
    if history.empty or pd.isna(initial_stop) or initial_stop <= 0:
        return float("nan")

    prior_rows = history[history["date"] < entry_date].tail(1)
    held = history[(history["date"] >= entry_date) & (history["date"] <= exit_date)].copy()
    if held.empty:
        return float("nan")

    ordered = pd.concat([prior_rows, held], ignore_index=True)
    dynamic_stop = float(initial_stop)
    previous_high = float("nan")
    for row in ordered.itertuples(index=False):
        current_date = _to_local_date(row.date)
        high_price = _safe_float(row.high)
        if current_date > entry_date and not pd.isna(previous_high):
            dynamic_stop = min(dynamic_stop, previous_high)
        if current_date >= exit_date:
            return dynamic_stop
        previous_high = high_price

    return dynamic_stop


def _post_exit_path_metrics(
    direction: str,
    after: pd.DataFrame,
    exit_price: float,
    entry_price: float,
    risk_distance: float,
    horizon: int,
) -> dict[str, Any]:
    window = after.head(horizon)
    if window.empty or risk_distance <= 0:
        return {
            f"post_{horizon}d_favorable": float("nan"),
            f"post_{horizon}d_adverse": float("nan"),
            f"post_{horizon}d_favorable_to_risk": float("nan"),
            f"post_{horizon}d_hit_breakeven": 0,
        }

    if direction == "short":
        favorable = exit_price - float(window["low"].min())
        adverse = float(window["high"].max()) - exit_price
        hit_breakeven = int(float(window["low"].min()) <= entry_price)
    else:
        favorable = float(window["high"].max()) - exit_price
        adverse = exit_price - float(window["low"].min())
        hit_breakeven = int(float(window["high"].max()) >= entry_price)

    return {
        f"post_{horizon}d_favorable": favorable,
        f"post_{horizon}d_adverse": adverse,
        f"post_{horizon}d_favorable_to_risk": favorable / risk_distance,
        f"post_{horizon}d_hit_breakeven": hit_breakeven,
    }


def _round_trip_metrics(
    row: pd.Series,
    history: pd.DataFrame,
    entry_fields: dict[str, Any],
    candidate_fields: dict[str, Any],
) -> dict[str, Any]:
    entry_date = _to_local_date(row["entry_date"])
    exit_date = _to_local_date(row["exit_date"])
    path = history[(history["date"] >= entry_date) & (history["date"] <= exit_date)].copy()
    after = history[history["date"] > exit_date].copy()
    prior = history[history["date"] < entry_date].tail(1).copy()

    entry_price = float(row["entry_price"])
    exit_price = float(row["exit_price"])
    direction = str(row["direction"])
    initial_stop = _safe_float(entry_fields.get("stop_price"))
    risk_distance = abs(entry_price - initial_stop) if not pd.isna(initial_stop) else _safe_float(
        entry_fields.get("stop_distance")
    )
    if pd.isna(risk_distance) or risk_distance <= 0:
        risk_distance = max(abs(entry_price) * 0.02, 1e-9)

    if path.empty:
        mfe = mae = float("nan")
        bars_held = 0
    elif direction == "short":
        mfe = entry_price - float(path["low"].min())
        mae = float(path["high"].max()) - entry_price
        bars_held = len(path)
    else:
        mfe = float(path["high"].max()) - entry_price
        mae = entry_price - float(path["low"].min())
        bars_held = len(path)

    dynamic_stop_at_exit = float("nan")
    dynamic_stop_distance = float("nan")
    dynamic_stop_ratio = float("nan")
    stop_tightened_by = float("nan")
    exit_overshoot_to_dynamic = float("nan")
    exit_overshoot_to_risk = float("nan")
    if direction == "short":
        dynamic_stop_at_exit = _reconstruct_short_dynamic_stop(history, entry_date, exit_date, initial_stop)
        if not pd.isna(dynamic_stop_at_exit):
            dynamic_stop_distance = dynamic_stop_at_exit - entry_price
            dynamic_stop_ratio = dynamic_stop_distance / risk_distance if risk_distance > 0 else float("nan")
            stop_tightened_by = initial_stop - dynamic_stop_at_exit
            exit_overshoot_to_dynamic = exit_price - dynamic_stop_at_exit
            exit_overshoot_to_risk = exit_overshoot_to_dynamic / risk_distance if risk_distance > 0 else float("nan")

    entry_rsi = _safe_float(
        candidate_fields.get("rsi_value"),
        _safe_float(entry_fields.get("streak_entry_structure_risk_recovery_rsi_value")),
    )
    entry_context = str(entry_fields.get("env_gate_entry_context", candidate_fields.get("entry_context", "")) or "")
    exit_reason = str(row.get("exit_reason", "") or "")

    post_metrics: dict[str, Any] = {}
    for horizon in (5, 10, 20):
        post_metrics.update(
            _post_exit_path_metrics(direction, after, exit_price, entry_price, risk_distance, horizon)
        )

    failure_type = "not_target"
    if exit_reason == TARGET_EXIT_REASON:
        post_10d = _safe_float(post_metrics.get("post_10d_favorable_to_risk"))
        post_20d = _safe_float(post_metrics.get("post_20d_favorable_to_risk"))
        if entry_context == "rollover_reopen":
            failure_type = "rollover_reopen_soft_stop_loss"
        elif not pd.isna(dynamic_stop_ratio) and dynamic_stop_ratio <= 0.60 and post_10d >= 1.0:
            failure_type = "trailing_soft_stop_too_tight_then_recovered"
        elif post_10d >= 1.0 or post_20d >= 1.5:
            failure_type = "soft_stop_then_later_recovered"
        elif not pd.isna(exit_overshoot_to_risk) and exit_overshoot_to_risk >= 0.50:
            failure_type = "soft_confirm_close_lag_cost"
        elif not pd.isna(mfe) and mfe / risk_distance < 0.30:
            failure_type = "wrong_direction_or_bad_timing"
        else:
            failure_type = "soft_stop_no_clear_recovery"

    entry_pre_ret_5d = _safe_float(prior["ret_5d"].iloc[-1]) if not prior.empty else float("nan")
    entry_pre_ret_20d = _safe_float(prior["ret_20d"].iloc[-1]) if not prior.empty else float("nan")
    entry_channel_position_20 = (
        _safe_float(prior["channel_position_20"].iloc[-1]) if not prior.empty else float("nan")
    )

    return {
        "bars_held": bars_held,
        "signal": str(entry_fields.get("signal", candidate_fields.get("signal", "")) or ""),
        "entry_context": entry_context,
        "entry_rsi": entry_rsi,
        "entry_rsi_bucket": _rsi_bucket(entry_rsi),
        "entry_pre_ret_5d": entry_pre_ret_5d,
        "entry_pre_ret_20d": entry_pre_ret_20d,
        "entry_channel_position_20": entry_channel_position_20,
        "initial_stop_price": initial_stop,
        "initial_stop_distance": risk_distance,
        "initial_stop_distance_pct": risk_distance / entry_price if entry_price > 0 else float("nan"),
        "dynamic_stop_at_exit": dynamic_stop_at_exit,
        "dynamic_stop_distance_at_exit": dynamic_stop_distance,
        "dynamic_stop_distance_ratio_to_initial": dynamic_stop_ratio,
        "stop_tightened_by": stop_tightened_by,
        "exit_overshoot_to_dynamic_stop": exit_overshoot_to_dynamic,
        "exit_overshoot_to_initial_risk": exit_overshoot_to_risk,
        "mfe": mfe,
        "mae": mae,
        "mfe_to_initial_risk": mfe / risk_distance if risk_distance > 0 else float("nan"),
        "mae_to_initial_risk": mae / risk_distance if risk_distance > 0 else float("nan"),
        "portfolio_drawdown_pct": _safe_float(entry_fields.get("portfolio_drawdown_pct")),
        "loss_streak": _safe_float(entry_fields.get("loss_streak")),
        "candidate_status": str(candidate_fields.get("candidate_status", "") or ""),
        "active_positions_before": _safe_float(candidate_fields.get("active_positions_before")),
        "failure_type": failure_type,
        **post_metrics,
    }


def _build_detail(round_trips: pd.DataFrame, entries: pd.DataFrame, candidates: pd.DataFrame) -> pd.DataFrame:
    if round_trips.empty:
        return pd.DataFrame()

    entry_lookup = _lookup_by_contract_datetime(entries)
    candidate_lookup = _lookup_by_contract_datetime(candidates)
    short_round_trips = round_trips[round_trips["direction"].eq("short")].copy()
    contracts = set(short_round_trips["contract_vt_symbol"].dropna().astype(str))
    bars = _load_bar_history(contracts)
    bars_by_contract = {contract: group for contract, group in bars.groupby("vt_symbol", sort=False)}

    rows: list[dict[str, Any]] = []
    for _, row in short_round_trips.iterrows():
        contract = str(row["contract_vt_symbol"])
        key = (contract, _timestamp_key(row["entry_datetime"]))
        entry_fields = entry_lookup.get(key, {})
        candidate_fields = candidate_lookup.get(key, {})
        history = bars_by_contract.get(contract, pd.DataFrame())
        metrics = _round_trip_metrics(row, history, entry_fields, candidate_fields)
        rows.append(
            {
                "product_vt_symbol": row["product_vt_symbol"],
                "contract_vt_symbol": contract,
                "direction": row["direction"],
                "entry_datetime": row["entry_datetime"],
                "exit_datetime": row["exit_datetime"],
                "entry_date": row["entry_date"],
                "exit_date": row["exit_date"],
                "entry_year": int(row["entry_year"]),
                "entry_price": row["entry_price"],
                "exit_price": row["exit_price"],
                "volume": row["volume"],
                "pnl": row["pnl"],
                "exit_reason": row["exit_reason"],
                **metrics,
            }
        )
    return pd.DataFrame(rows)


def _summarize(frame: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame()
    summary = frame.groupby(group_cols, dropna=False).agg(
        round_trips=("pnl", "size"),
        pnl=("pnl", "sum"),
        avg_pnl=("pnl", "mean"),
        win_rate=("pnl", lambda s: float((s > 0).mean())),
        avg_bars_held=("bars_held", "mean"),
        avg_entry_rsi=("entry_rsi", "mean"),
        avg_initial_stop_distance_pct=("initial_stop_distance_pct", "mean"),
        avg_dynamic_stop_ratio=("dynamic_stop_distance_ratio_to_initial", "mean"),
        avg_exit_overshoot_r=("exit_overshoot_to_initial_risk", "mean"),
        avg_mfe_r=("mfe_to_initial_risk", "mean"),
        avg_mae_r=("mae_to_initial_risk", "mean"),
        avg_post_10d_favorable_r=("post_10d_favorable_to_risk", "mean"),
        post_10d_breakeven_rate=("post_10d_hit_breakeven", "mean"),
        worst_pnl=("pnl", "min"),
        best_pnl=("pnl", "max"),
    ).reset_index()
    return summary.sort_values(["pnl", "round_trips"], ascending=[True, False]).reset_index(drop=True)


def _write_report(
    soft_detail: pd.DataFrame,
    short_exit_summary: pd.DataFrame,
    soft_year_summary: pd.DataFrame,
    soft_rsi_summary: pd.DataFrame,
    soft_failure_summary: pd.DataFrame,
) -> None:
    worst_rows = soft_detail.sort_values(["pnl", "entry_datetime"], ascending=[True, True])
    lines = [
        "# QMT Range Reversion Core4 V8 Short Soft Stop Replay",
        "",
        "## Scope",
        "- Reads existing v8 trades, entry diagnostics, candidate snapshots and bar history only; no new backtest is run.",
        "- Focuses on `short_soft_base_stop_confirmed`, the largest remaining loss bucket in v8.",
        "- The goal is attribution, not parameter search or product blacklisting.",
        "",
        "## Short Exit Summary",
        short_exit_summary.to_markdown(index=False) if not short_exit_summary.empty else "- Empty.",
        "",
        "## Target Soft Stop By Year",
        soft_year_summary.to_markdown(index=False) if not soft_year_summary.empty else "- Empty.",
        "",
        "## Target Soft Stop By RSI Bucket",
        soft_rsi_summary.to_markdown(index=False) if not soft_rsi_summary.empty else "- Empty.",
        "",
        "## Target Failure Type",
        soft_failure_summary.to_markdown(index=False) if not soft_failure_summary.empty else "- Empty.",
        "",
        "## Target Trade Detail",
        worst_rows[
            [
                "product_vt_symbol",
                "contract_vt_symbol",
                "entry_datetime",
                "exit_datetime",
                "pnl",
                "volume",
                "entry_context",
                "entry_rsi",
                "initial_stop_distance_pct",
                "dynamic_stop_distance_ratio_to_initial",
                "exit_overshoot_to_initial_risk",
                "mfe_to_initial_risk",
                "mae_to_initial_risk",
                "post_10d_favorable_to_risk",
                "post_10d_hit_breakeven",
                "failure_type",
            ]
        ].to_markdown(index=False)
        if not worst_rows.empty
        else "- Empty.",
    ]
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-prefix", default=SOURCE_PREFIX)
    parser.add_argument("--model-tag", default=MODEL_TAG)
    args = parser.parse_args()
    _configure_paths(args.source_prefix, args.model_tag)

    round_trips, entries, candidates, _ = _load_inputs()
    detail = _build_detail(round_trips, entries, candidates)
    soft_detail = detail[detail["exit_reason"].eq(TARGET_EXIT_REASON)].copy()

    short_exit_summary = _summarize(detail, ["exit_reason"])
    soft_year_summary = _summarize(soft_detail, ["entry_year"])
    soft_rsi_summary = _summarize(soft_detail, ["entry_rsi_bucket"])
    soft_failure_summary = _summarize(soft_detail, ["failure_type"])

    detail.to_csv(DETAIL_PATH, index=False, encoding="utf-8-sig")
    soft_detail.to_csv(SOFT_DETAIL_PATH, index=False, encoding="utf-8-sig")
    short_exit_summary.to_csv(SHORT_EXIT_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    soft_year_summary.to_csv(SOFT_YEAR_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    soft_rsi_summary.to_csv(SOFT_RSI_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    soft_failure_summary.to_csv(SOFT_FAILURE_SUMMARY_PATH, index=False, encoding="utf-8-sig")

    worst_trade = soft_detail.sort_values("pnl").head(1).to_dict("records")
    payload = {
        "model_tag": MODEL_TAG,
        "source_prefix": SOURCE_PREFIX,
        "target_exit_reason": TARGET_EXIT_REASON,
        "short_round_trips": int(len(detail)),
        "target_round_trips": int(len(soft_detail)),
        "target_pnl": float(soft_detail["pnl"].sum()) if not soft_detail.empty else 0.0,
        "target_products": sorted(soft_detail["product_vt_symbol"].dropna().astype(str).unique().tolist())
        if not soft_detail.empty
        else [],
        "target_years": sorted(soft_detail["entry_year"].dropna().astype(int).unique().tolist())
        if not soft_detail.empty
        else [],
        "worst_trade": worst_trade[0] if worst_trade else {},
        "failure_types": soft_failure_summary.to_dict("records") if not soft_failure_summary.empty else [],
        "outputs": {
            "detail": str(DETAIL_PATH),
            "soft_detail": str(SOFT_DETAIL_PATH),
            "short_exit_summary": str(SHORT_EXIT_SUMMARY_PATH),
            "soft_year_summary": str(SOFT_YEAR_SUMMARY_PATH),
            "soft_rsi_summary": str(SOFT_RSI_SUMMARY_PATH),
            "soft_failure_summary": str(SOFT_FAILURE_SUMMARY_PATH),
            "report": str(REPORT_PATH),
        },
    }
    SUMMARY_JSON_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    _write_report(soft_detail, short_exit_summary, soft_year_summary, soft_rsi_summary, soft_failure_summary)

    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    print(short_exit_summary.to_string(index=False))
    print(soft_year_summary.to_string(index=False))
    print(soft_rsi_summary.to_string(index=False))
    print(soft_failure_summary.to_string(index=False))
    print(soft_detail.sort_values(["pnl", "entry_datetime"], ascending=[True, True]).to_string(index=False))


if __name__ == "__main__":
    main()
