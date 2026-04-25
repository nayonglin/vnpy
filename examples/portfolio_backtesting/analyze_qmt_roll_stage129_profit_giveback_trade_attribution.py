from __future__ import annotations

import json
import math
import sys
from collections import deque
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from typing import Any

import pandas as pd

from analyze_qmt_roll_stage105_margin_constraint_surface import _to_markdown_table
from qmt_roll_official_stage78_config import (
    OFFICIAL_STAGE78_CAPITAL,
    OFFICIAL_STAGE78_VERSION,
    build_official_stage78_overrides,
)
from qmt_universe import END_DT, START_DT
from run_qmt_alignment_backtest import build_positions_df, build_trades_df
from run_qmt_roll_backtest import run_backtest
from run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest import BASE_RISK_RATIO


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

MODEL_TAG: str = "stage129_profit_giveback_trade_attribution_v1"
OUTPUT_PREFIX: str = "qmt_roll_stage129_profit_giveback_trade_attribution"

SUMMARY_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
PRODUCT_DELTA_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_delta_{MODEL_TAG}.csv"
DIRECTION_DELTA_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_direction_delta_{MODEL_TAG}.csv"
EXIT_REASON_DELTA_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_exit_reason_delta_{MODEL_TAG}.csv"
ROLLING20_DELTA_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_rolling20_delta_windows_{MODEL_TAG}.csv"
ROUNDTRIP_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_roundtrips_{MODEL_TAG}.csv"
SUMMARY_JSON_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.json"
REPORT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


BASE_PROFILE_NAME: str = "official_stage78_reference"
CANDIDATE_PROFILE_NAME: str = "stage78_giveback10_retain80_min03"
CANDIDATE_PARAMS: dict[str, Any] = {
    "enable_profit_giveback_stop": True,
    "profit_giveback_trigger_pct": 0.10,
    "profit_giveback_retain_ratio": 0.80,
    "profit_giveback_min_lock_pct": 0.03,
}


@dataclass(frozen=True)
class VariantRun:
    profile_name: str
    statistics: dict[str, Any]
    daily: pd.DataFrame
    positions: pd.DataFrame
    trades: pd.DataFrame
    roundtrips: pd.DataFrame
    profit_giveback_stop_update_count: int


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if pd.isna(result) or math.isinf(result):
        return default
    return result


def _build_candidate_overrides() -> dict[str, Any]:
    overrides = build_official_stage78_overrides()
    overrides.update(CANDIDATE_PARAMS)
    return overrides


def _contract_to_product(strategy: Any, vt_symbol: str) -> str:
    source_map = getattr(strategy, "source_symbol_by_contract", {}) if strategy else {}
    product = str(source_map.get(vt_symbol, "") or "")
    if product:
        return product

    if "." not in vt_symbol:
        return vt_symbol
    symbol, exchange = vt_symbol.split(".", 1)
    product_symbol = "".join(ch for ch in symbol if ch.isalpha())
    return f"{product_symbol}.{exchange}" if product_symbol else vt_symbol


def _build_roundtrips(engine: Any, trades: pd.DataFrame) -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame()

    strategy = getattr(engine, "strategy", None)
    size_map: dict[str, int] = getattr(engine, "sizes", {})
    queues: dict[tuple[str, str], deque[dict[str, Any]]] = {}
    rows: list[dict[str, Any]] = []
    lot_id = 0

    trade_df = trades.copy()
    trade_df["datetime"] = pd.to_datetime(trade_df["datetime"]).dt.tz_localize(None)
    trade_df.sort_values(["datetime", "vt_symbol", "trade_id"], inplace=True)

    for _, trade in trade_df.iterrows():
        vt_symbol = str(trade["vt_symbol"])
        direction = str(trade["direction"])
        offset = str(trade["offset"])
        price = float(trade["price"])
        volume = float(trade["volume"])
        trade_dt = pd.Timestamp(trade["datetime"])
        contract_size = float(size_map.get(vt_symbol, 1))
        product_vt_symbol = _contract_to_product(strategy, vt_symbol)

        if offset == "Open":
            position_direction = "long" if direction == "Long" else "short"
            queue_key = (vt_symbol, position_direction)
            queues.setdefault(queue_key, deque()).append(
                {
                    "entry_datetime": trade_dt,
                    "entry_date": trade_dt.date().isoformat(),
                    "entry_price": price,
                    "volume": volume,
                    "product_vt_symbol": product_vt_symbol,
                }
            )
            continue

        position_direction = "long" if direction == "Short" else "short"
        queue_key = (vt_symbol, position_direction)
        queue = queues.setdefault(queue_key, deque())
        remaining = volume

        while remaining > 1e-9 and queue:
            entry = queue[0]
            matched_volume = min(remaining, float(entry["volume"]))
            entry_price = float(entry["entry_price"])
            if position_direction == "long":
                gross_pnl = (price - entry_price) * matched_volume * contract_size
            else:
                gross_pnl = (entry_price - price) * matched_volume * contract_size

            lot_id += 1
            rows.append(
                {
                    "roundtrip_id": lot_id,
                    "vt_symbol": vt_symbol,
                    "product_vt_symbol": str(entry["product_vt_symbol"]),
                    "position_direction": position_direction,
                    "entry_datetime": entry["entry_datetime"],
                    "entry_date": str(entry["entry_date"]),
                    "exit_datetime": trade_dt,
                    "exit_date": trade_dt.date().isoformat(),
                    "entry_price": entry_price,
                    "exit_price": price,
                    "volume": matched_volume,
                    "contract_size": contract_size,
                    "gross_pnl": gross_pnl,
                    "holding_days": int((trade_dt - pd.Timestamp(entry["entry_datetime"])).days),
                    "exit_reason": str(trade.get("exit_reason", "") or ""),
                }
            )

            entry["volume"] = float(entry["volume"]) - matched_volume
            remaining -= matched_volume
            if float(entry["volume"]) <= 1e-9:
                queue.popleft()

    roundtrips = pd.DataFrame(rows)
    if not roundtrips.empty:
        roundtrips.sort_values(["exit_datetime", "vt_symbol", "roundtrip_id"], inplace=True)
    return roundtrips


def _add_product_column(positions: pd.DataFrame, strategy: Any) -> pd.DataFrame:
    if positions.empty:
        return positions
    result = positions.copy()
    result["product_vt_symbol"] = result["vt_symbol"].map(lambda symbol: _contract_to_product(strategy, str(symbol)))
    return result


def _run_variant(profile_name: str, strategy_overrides: dict[str, Any]) -> VariantRun:
    print(f"[stage129-profit-giveback-attribution] run {profile_name}", flush=True)
    log_buffer = StringIO()
    try:
        with redirect_stdout(log_buffer), redirect_stderr(log_buffer):
            engine, daily, statistics = run_backtest(
                risk_ratio=BASE_RISK_RATIO,
                strategy_overrides=strategy_overrides,
                analysis_start=START_DT,
                analysis_end=END_DT,
                capital=OFFICIAL_STAGE78_CAPITAL,
                save_artifacts=False,
                include_start_year_sweep=False,
            )
    except Exception:
        sys.stderr.write(log_buffer.getvalue())
        raise

    strategy = getattr(engine, "strategy", None)
    daily_df = daily.copy() if daily is not None else pd.DataFrame()
    if not daily_df.empty:
        daily_df.sort_index(inplace=True)
    positions = _add_product_column(build_positions_df(engine), strategy)
    trades = build_trades_df(engine)
    roundtrips = _build_roundtrips(engine, trades)
    for frame in (trades, roundtrips, positions):
        if not frame.empty:
            frame.insert(0, "profile_name", profile_name)

    return VariantRun(
        profile_name=profile_name,
        statistics=statistics,
        daily=daily_df,
        positions=positions,
        trades=trades,
        roundtrips=roundtrips,
        profit_giveback_stop_update_count=int(getattr(strategy, "profit_giveback_stop_update_count", 0) if strategy else 0),
    )


def _summary_row(run: VariantRun) -> dict[str, Any]:
    return {
        "profile_name": run.profile_name,
        "base_version": OFFICIAL_STAGE78_VERSION,
        "capital": OFFICIAL_STAGE78_CAPITAL,
        "end_balance": _safe_float(run.statistics.get("end_balance")),
        "total_return_pct": _safe_float(run.statistics.get("total_return")),
        "max_dd_percent": _safe_float(run.statistics.get("max_ddpercent")),
        "sharpe_ratio": _safe_float(run.statistics.get("sharpe_ratio")),
        "total_slippage": _safe_float(run.statistics.get("total_slippage")),
        "total_trade_count": int(_safe_float(run.statistics.get("total_trade_count"))),
        "win_ratio_pct": _safe_float(run.statistics.get("win_ratio")),
        "roundtrip_count": int(len(run.roundtrips)),
        "roundtrip_gross_pnl": _safe_float(run.roundtrips["gross_pnl"].sum()) if not run.roundtrips.empty else 0.0,
        "roundtrip_avg_pnl": _safe_float(run.roundtrips["gross_pnl"].mean()) if not run.roundtrips.empty else 0.0,
        "roundtrip_median_pnl": _safe_float(run.roundtrips["gross_pnl"].median()) if not run.roundtrips.empty else 0.0,
        "roundtrip_win_ratio_pct": _safe_float((run.roundtrips["gross_pnl"] > 0).mean() * 100.0)
        if not run.roundtrips.empty
        else 0.0,
        "profit_giveback_stop_update_count": run.profit_giveback_stop_update_count,
    }


def _aggregate_roundtrips(roundtrips: pd.DataFrame, key: str) -> pd.DataFrame:
    if roundtrips.empty:
        return pd.DataFrame(columns=[key, "gross_pnl", "roundtrip_count", "win_ratio_pct", "avg_holding_days"])
    grouped = (
        roundtrips.groupby(key, dropna=False)
        .agg(
            gross_pnl=("gross_pnl", "sum"),
            roundtrip_count=("gross_pnl", "size"),
            win_ratio_pct=("gross_pnl", lambda values: float((values > 0).mean() * 100.0)),
            avg_holding_days=("holding_days", "mean"),
        )
        .reset_index()
    )
    return grouped


def _build_delta_table(base: pd.DataFrame, candidate: pd.DataFrame, key: str) -> pd.DataFrame:
    base_agg = _aggregate_roundtrips(base, key).rename(
        columns={
            "gross_pnl": "stage78_gross_pnl",
            "roundtrip_count": "stage78_roundtrip_count",
            "win_ratio_pct": "stage78_win_ratio_pct",
            "avg_holding_days": "stage78_avg_holding_days",
        }
    )
    candidate_agg = _aggregate_roundtrips(candidate, key).rename(
        columns={
            "gross_pnl": "stage128_gross_pnl",
            "roundtrip_count": "stage128_roundtrip_count",
            "win_ratio_pct": "stage128_win_ratio_pct",
            "avg_holding_days": "stage128_avg_holding_days",
        }
    )
    comparison = candidate_agg.merge(base_agg, on=key, how="outer").fillna(0.0)
    comparison["gross_pnl_delta"] = comparison["stage128_gross_pnl"] - comparison["stage78_gross_pnl"]
    comparison["roundtrip_count_delta"] = comparison["stage128_roundtrip_count"] - comparison["stage78_roundtrip_count"]
    comparison["win_ratio_pct_delta"] = comparison["stage128_win_ratio_pct"] - comparison["stage78_win_ratio_pct"]
    comparison.sort_values("gross_pnl_delta", ascending=False, inplace=True)
    return comparison


def _build_daily_delta(base: VariantRun, candidate: VariantRun) -> pd.DataFrame:
    left = base.daily[["balance", "net_pnl", "drawdown", "ddpercent"]].copy().reset_index()
    right = candidate.daily[["balance", "net_pnl", "drawdown", "ddpercent"]].copy().reset_index()
    left.rename(
        columns={
            left.columns[0]: "date",
            "balance": "stage78_balance",
            "net_pnl": "stage78_net_pnl",
            "drawdown": "stage78_drawdown",
            "ddpercent": "stage78_ddpercent",
        },
        inplace=True,
    )
    right.rename(
        columns={
            right.columns[0]: "date",
            "balance": "stage128_balance",
            "net_pnl": "stage128_net_pnl",
            "drawdown": "stage128_drawdown",
            "ddpercent": "stage128_ddpercent",
        },
        inplace=True,
    )
    daily = left.merge(right, on="date", how="outer").sort_values("date").ffill().fillna(0.0)
    daily["balance_delta"] = daily["stage128_balance"] - daily["stage78_balance"]
    daily["net_pnl_delta"] = daily["stage128_net_pnl"] - daily["stage78_net_pnl"]
    daily["ddpercent_delta"] = daily["stage128_ddpercent"] - daily["stage78_ddpercent"]
    return daily


def _select_non_overlapping_windows(windows: pd.DataFrame, *, largest: bool, top_n: int = 8) -> pd.DataFrame:
    if windows.empty:
        return windows
    sorted_windows = windows.sort_values("rolling20_net_pnl_delta", ascending=not largest).copy()
    selected: list[pd.Series] = []
    occupied: set[pd.Timestamp] = set()
    for _, row in sorted_windows.iterrows():
        dates = set(pd.date_range(pd.Timestamp(row["start_date"]), pd.Timestamp(row["end_date"]), freq="D"))
        if dates & occupied:
            continue
        selected.append(row)
        occupied.update(dates)
        if len(selected) >= top_n:
            break
    return pd.DataFrame(selected)


def _build_rolling20_windows(daily_delta: pd.DataFrame) -> pd.DataFrame:
    if daily_delta.empty:
        return pd.DataFrame()
    daily = daily_delta.copy()
    daily["date"] = pd.to_datetime(daily["date"])
    daily["rolling20_net_pnl_delta"] = daily["net_pnl_delta"].rolling(20, min_periods=20).sum()
    daily["start_date"] = daily["date"].shift(19)
    windows = daily.dropna(subset=["rolling20_net_pnl_delta", "start_date"]).copy()
    windows["end_date"] = windows["date"]
    windows = windows[
        [
            "start_date",
            "end_date",
            "rolling20_net_pnl_delta",
            "balance_delta",
            "stage78_balance",
            "stage128_balance",
        ]
    ]
    best = _select_non_overlapping_windows(windows, largest=True)
    worst = _select_non_overlapping_windows(windows, largest=False)
    if not best.empty:
        best.insert(0, "window_type", "stage128_best_delta")
    if not worst.empty:
        worst.insert(0, "window_type", "stage128_worst_delta")
    result = pd.concat([best, worst], ignore_index=True, sort=False) if not best.empty or not worst.empty else pd.DataFrame()
    if not result.empty:
        for column in ["start_date", "end_date"]:
            result[column] = pd.to_datetime(result[column]).dt.date.astype(str)
    return result


def _position_product_delta(base_positions: pd.DataFrame, candidate_positions: pd.DataFrame) -> pd.DataFrame:
    def aggregate(frame: pd.DataFrame, prefix: str) -> pd.DataFrame:
        if frame.empty:
            return pd.DataFrame(columns=["product_vt_symbol", f"{prefix}_net_pnl", f"{prefix}_trade_count"])
        return (
            frame.groupby("product_vt_symbol", dropna=False)
            .agg(**{f"{prefix}_net_pnl": ("net_pnl", "sum"), f"{prefix}_trade_count": ("trade_count", "sum")})
            .reset_index()
        )

    base = aggregate(base_positions, "stage78")
    candidate = aggregate(candidate_positions, "stage128")
    result = candidate.merge(base, on="product_vt_symbol", how="outer").fillna(0.0)
    result["net_pnl_delta"] = result["stage128_net_pnl"] - result["stage78_net_pnl"]
    result["trade_count_delta"] = result["stage128_trade_count"] - result["stage78_trade_count"]
    result.sort_values("net_pnl_delta", ascending=False, inplace=True)
    return result


def _build_report(
    summary: pd.DataFrame,
    product_delta: pd.DataFrame,
    direction_delta: pd.DataFrame,
    exit_reason_delta: pd.DataFrame,
    rolling20: pd.DataFrame,
) -> str:
    total_delta = float(
        summary.loc[summary["profile_name"].eq(CANDIDATE_PROFILE_NAME), "end_balance"].iloc[0]
        - summary.loc[summary["profile_name"].eq(BASE_PROFILE_NAME), "end_balance"].iloc[0]
    )
    top_product_delta = _safe_float(product_delta["net_pnl_delta"].iloc[0]) if not product_delta.empty else 0.0
    top_product_share = top_product_delta / total_delta * 100.0 if abs(total_delta) > 1e-9 else 0.0
    improved_products = int((product_delta["net_pnl_delta"] > 0).sum()) if not product_delta.empty else 0
    worsened_products = int((product_delta["net_pnl_delta"] < 0).sum()) if not product_delta.empty else 0

    return "\n".join(
        [
            "# Stage129 Profit Giveback Trade Attribution",
            "",
            "## Boundary",
            "",
            "- Base: `official_stage78_defensive_v1`.",
            "- Candidate: `stage78_giveback10_retain80_min03` from Stage128.",
            "- No new parameters, no tuning, no product/date/direction filter.",
            "",
            "## Full Summary",
            "",
            _to_markdown_table(
                summary,
                [
                    "profile_name",
                    "end_balance",
                    "total_return_pct",
                    "max_dd_percent",
                    "sharpe_ratio",
                    "total_slippage",
                    "total_trade_count",
                    "win_ratio_pct",
                    "roundtrip_count",
                    "roundtrip_gross_pnl",
                    "profit_giveback_stop_update_count",
                ],
            ),
            "",
            "## Product Net-Pnl Delta",
            "",
            _to_markdown_table(
                product_delta.head(12),
                [
                    "product_vt_symbol",
                    "stage128_net_pnl",
                    "stage78_net_pnl",
                    "net_pnl_delta",
                    "stage128_trade_count",
                    "stage78_trade_count",
                    "trade_count_delta",
                ],
            ),
            "",
            "## Worst Product Net-Pnl Delta",
            "",
            _to_markdown_table(
                product_delta.sort_values("net_pnl_delta", ascending=True).head(8),
                [
                    "product_vt_symbol",
                    "stage128_net_pnl",
                    "stage78_net_pnl",
                    "net_pnl_delta",
                    "stage128_trade_count",
                    "stage78_trade_count",
                    "trade_count_delta",
                ],
            ),
            "",
            "## Direction Gross-Pnl Delta",
            "",
            _to_markdown_table(
                direction_delta,
                [
                    "position_direction",
                    "stage128_gross_pnl",
                    "stage78_gross_pnl",
                    "gross_pnl_delta",
                    "stage128_roundtrip_count",
                    "stage78_roundtrip_count",
                ],
            ),
            "",
            "## Exit Reason Gross-Pnl Delta",
            "",
            _to_markdown_table(
                exit_reason_delta.head(12),
                [
                    "exit_reason",
                    "stage128_gross_pnl",
                    "stage78_gross_pnl",
                    "gross_pnl_delta",
                    "stage128_roundtrip_count",
                    "stage78_roundtrip_count",
                ],
            ),
            "",
            "## Rolling 20-Day Delta Windows",
            "",
            _to_markdown_table(
                rolling20,
                [
                    "window_type",
                    "start_date",
                    "end_date",
                    "rolling20_net_pnl_delta",
                    "balance_delta",
                    "stage78_balance",
                    "stage128_balance",
                ],
            ),
            "",
            "## Concentration Check",
            "",
            f"- End-balance delta: `{total_delta:,.0f}`.",
            f"- Improved products: `{improved_products}`; worsened products: `{worsened_products}`.",
            f"- Top product net-pnl delta share of total delta: `{top_product_share:.2f}%`.",
            "- If one product or one window explains almost all improvement, treat the candidate as fragile.",
            "",
            "## Judgement Rule",
            "",
            "- Valuable if improvement is distributed across products/directions/windows and does not only come from a single historical accident.",
            "- If improvement is concentrated, stop before formalizing and do not tune the giveback thresholds.",
        ]
    )


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    base = _run_variant(BASE_PROFILE_NAME, build_official_stage78_overrides())
    candidate = _run_variant(CANDIDATE_PROFILE_NAME, _build_candidate_overrides())

    summary = pd.DataFrame([_summary_row(base), _summary_row(candidate)])
    product_delta = _position_product_delta(base.positions, candidate.positions)
    direction_delta = _build_delta_table(base.roundtrips, candidate.roundtrips, "position_direction")
    exit_reason_delta = _build_delta_table(base.roundtrips, candidate.roundtrips, "exit_reason")
    daily_delta = _build_daily_delta(base, candidate)
    rolling20 = _build_rolling20_windows(daily_delta)
    roundtrips = pd.concat([base.roundtrips, candidate.roundtrips], ignore_index=True, sort=False)

    summary.to_csv(SUMMARY_CSV_PATH, index=False, encoding="utf-8-sig")
    product_delta.to_csv(PRODUCT_DELTA_CSV_PATH, index=False, encoding="utf-8-sig")
    direction_delta.to_csv(DIRECTION_DELTA_CSV_PATH, index=False, encoding="utf-8-sig")
    exit_reason_delta.to_csv(EXIT_REASON_DELTA_CSV_PATH, index=False, encoding="utf-8-sig")
    rolling20.to_csv(ROLLING20_DELTA_CSV_PATH, index=False, encoding="utf-8-sig")
    roundtrips.to_csv(ROUNDTRIP_CSV_PATH, index=False, encoding="utf-8-sig")

    payload = {
        "model_tag": MODEL_TAG,
        "base_version": OFFICIAL_STAGE78_VERSION,
        "candidate_params": CANDIDATE_PARAMS,
        "summary": summary.to_dict(orient="records"),
        "product_delta_top": product_delta.head(20).to_dict(orient="records"),
        "direction_delta": direction_delta.to_dict(orient="records"),
        "exit_reason_delta_top": exit_reason_delta.head(20).to_dict(orient="records"),
        "rolling20_delta_windows": rolling20.to_dict(orient="records"),
        "output_paths": {
            "summary": str(SUMMARY_CSV_PATH),
            "product_delta": str(PRODUCT_DELTA_CSV_PATH),
            "direction_delta": str(DIRECTION_DELTA_CSV_PATH),
            "exit_reason_delta": str(EXIT_REASON_DELTA_CSV_PATH),
            "rolling20_delta_windows": str(ROLLING20_DELTA_CSV_PATH),
            "roundtrips": str(ROUNDTRIP_CSV_PATH),
            "report": str(REPORT_PATH),
        },
    }
    SUMMARY_JSON_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_PATH.write_text(_build_report(summary, product_delta, direction_delta, exit_reason_delta, rolling20), encoding="utf-8")

    print(f"[stage129-profit-giveback-attribution] summary: {SUMMARY_CSV_PATH}")
    print(f"[stage129-profit-giveback-attribution] product delta: {PRODUCT_DELTA_CSV_PATH}")
    print(f"[stage129-profit-giveback-attribution] report: {REPORT_PATH}")
    print(summary.to_string(index=False))
    print(product_delta.head(12).to_string(index=False))
    print(direction_delta.to_string(index=False))
    print(exit_reason_delta.head(12).to_string(index=False))
    print(rolling20.to_string(index=False))


if __name__ == "__main__":
    main()
