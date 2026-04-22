from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

from qmt_universe import PRODUCT_SPECS
from run_qmt_alignment_backtest import OUTPUT_DIR


FILE_PREFIX: str = "qmt_roll"
N_SIMULATIONS: int = 1000
TRADE_BLOCK_SIZE: int = 5
DAILY_BLOCK_SIZE: int = 20
RNG_SEED: int = 42


def extract_product(symbol: str) -> str:
    matched = re.match(r"[A-Za-z]+", symbol)
    return matched.group(0) if matched else symbol


def build_size_map() -> dict[str, int]:
    size_map: dict[str, int] = {}
    for spec in PRODUCT_SPECS:
        size_map[spec.product.upper()] = spec.size
        size_map[spec.product.lower()] = spec.size
    return size_map


def load_initial_capital(file_prefix: str) -> float:
    statistics_path: Path = (OUTPUT_DIR / f"{file_prefix}_statistics.json").resolve()
    with statistics_path.open("r", encoding="utf-8") as f:
        statistics = json.load(f)
    return float(statistics.get("capital", 0) or 0)


def calculate_path_metrics(values: np.ndarray, initial_capital: float) -> dict[str, float]:
    highlevel: np.ndarray = np.maximum.accumulate(values)
    drawdown: np.ndarray = values - highlevel
    dd_percent: np.ndarray = np.divide(
        drawdown,
        highlevel,
        out=np.zeros_like(drawdown, dtype=float),
        where=highlevel != 0,
    ) * 100.0
    end_balance: float = float(values[-1])
    return {
        "end_balance": end_balance,
        "total_return_pct": (end_balance / initial_capital - 1.0) * 100.0 if initial_capital > 0 else 0.0,
        "max_drawdown": float(drawdown.min()),
        "max_dd_percent": float(dd_percent.min()),
    }


def build_round_trip_pnls(trades_df: pd.DataFrame) -> np.ndarray:
    size_map = build_size_map()
    trades_df = trades_df.copy()
    trades_df["datetime"] = pd.to_datetime(trades_df["datetime"])
    trades_df.sort_values("datetime", inplace=True)

    realized_pnls: list[float] = []
    for _, group in trades_df.groupby("vt_symbol"):
        open_layers: list[list[float]] = []
        for row in group.itertuples():
            price = float(row.price)
            volume = float(row.volume)
            if row.direction == "Long" and row.offset == "Open":
                open_layers.append([price, volume])
                continue

            if row.direction != "Short" or row.offset != "Close":
                continue

            remain = volume
            product = extract_product(row.symbol)
            contract_size = float(size_map.get(product, 1))
            while remain > 1e-9 and open_layers:
                entry_price, entry_volume = open_layers[0]
                matched_volume = min(remain, entry_volume)
                realized_pnls.append((price - entry_price) * matched_volume * contract_size)
                entry_volume -= matched_volume
                remain -= matched_volume
                if entry_volume <= 1e-9:
                    open_layers.pop(0)
                else:
                    open_layers[0][1] = entry_volume

    return np.array(realized_pnls, dtype=float)


def simulate_trade_bootstrap(
    round_trip_pnls: np.ndarray,
    rng: np.random.Generator,
    initial_capital: float,
) -> pd.DataFrame:
    n = len(round_trip_pnls)
    if n == 0:
        return pd.DataFrame(columns=["simulation", "method", "end_balance", "total_return_pct", "max_drawdown", "max_dd_percent"])

    rows: list[dict[str, float | int | str]] = []
    blocks_per_path: int = int(np.ceil(n / TRADE_BLOCK_SIZE))
    for simulation in range(1, N_SIMULATIONS + 1):
        sampled: list[float] = []
        for _ in range(blocks_per_path):
            start_idx = int(rng.integers(0, n))
            for offset in range(TRADE_BLOCK_SIZE):
                sampled.append(float(round_trip_pnls[(start_idx + offset) % n]))
        pnl_path = np.array(sampled[:n], dtype=float)
        equity_path = initial_capital + np.cumsum(pnl_path)
        metrics = calculate_path_metrics(equity_path, initial_capital)
        rows.append({"simulation": simulation, "method": "trade_block_bootstrap", **metrics})
    return pd.DataFrame(rows)


def simulate_daily_block_bootstrap(
    daily_returns: np.ndarray,
    rng: np.random.Generator,
    initial_capital: float,
) -> pd.DataFrame:
    n = len(daily_returns)
    if n == 0:
        return pd.DataFrame(columns=["simulation", "method", "end_balance", "total_return_pct", "max_drawdown", "max_dd_percent"])

    rows: list[dict[str, float | int | str]] = []
    blocks_per_path: int = int(np.ceil(n / DAILY_BLOCK_SIZE))
    for simulation in range(1, N_SIMULATIONS + 1):
        sampled: list[float] = []
        for _ in range(blocks_per_path):
            start_idx = int(rng.integers(0, n))
            for offset in range(DAILY_BLOCK_SIZE):
                sampled.append(float(daily_returns[(start_idx + offset) % n]))
        return_path = np.array(sampled[:n], dtype=float)
        equity_path = initial_capital * np.cumprod(1.0 + return_path)
        metrics = calculate_path_metrics(equity_path, initial_capital)
        rows.append({"simulation": simulation, "method": "daily_block_bootstrap", **metrics})
    return pd.DataFrame(rows)


def build_quantile_summary(simulation_df: pd.DataFrame, initial_capital: float) -> pd.DataFrame:
    if simulation_df.empty:
        return pd.DataFrame()

    quantiles = [0.01, 0.05, 0.10, 0.50, 0.90, 0.95, 0.99]
    rows: list[dict[str, float | str]] = []
    for method, group in simulation_df.groupby("method"):
        row: dict[str, float | str] = {
            "method": method,
            "simulations": int(len(group)),
            "initial_capital": initial_capital,
            "loss_probability_pct": float((group["end_balance"] < initial_capital).mean() * 100.0),
            "ruin_probability_pct": float((group["end_balance"] <= 0).mean() * 100.0),
            "dd_over_20pct_probability_pct": float((group["max_dd_percent"] <= -20.0).mean() * 100.0),
            "dd_over_30pct_probability_pct": float((group["max_dd_percent"] <= -30.0).mean() * 100.0),
            "dd_over_40pct_probability_pct": float((group["max_dd_percent"] <= -40.0).mean() * 100.0),
        }
        for q in quantiles:
            q_label = str(int(q * 100)).zfill(2)
            row[f"end_balance_q{q_label}"] = float(group["end_balance"].quantile(q))
            row[f"total_return_pct_q{q_label}"] = float(group["total_return_pct"].quantile(q))
            row[f"max_dd_percent_q{q_label}"] = float(group["max_dd_percent"].quantile(q))
        rows.append(row)
    return pd.DataFrame(rows)


def main() -> None:
    trades_path: Path = (OUTPUT_DIR / f"{FILE_PREFIX}_trades_2020_2026_04.csv").resolve()
    daily_path: Path = (OUTPUT_DIR / f"{FILE_PREFIX}_daily_equity.csv").resolve()
    initial_capital: float = load_initial_capital(FILE_PREFIX)

    trades_df = pd.read_csv(trades_path)
    daily_df = pd.read_csv(daily_path)
    daily_returns = pd.to_numeric(daily_df["return"], errors="coerce").fillna(0.0).to_numpy(dtype=float)
    round_trip_pnls = build_round_trip_pnls(trades_df)

    rng = np.random.default_rng(RNG_SEED)
    trade_mc_df = simulate_trade_bootstrap(round_trip_pnls, rng, initial_capital)
    daily_mc_df = simulate_daily_block_bootstrap(daily_returns, rng, initial_capital)
    simulation_df = pd.concat([trade_mc_df, daily_mc_df], ignore_index=True)
    summary_df = build_quantile_summary(simulation_df, initial_capital)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    simulation_path: Path = (OUTPUT_DIR / f"{FILE_PREFIX}_monte_carlo_simulations.csv").resolve()
    summary_path: Path = (OUTPUT_DIR / f"{FILE_PREFIX}_monte_carlo_summary.csv").resolve()
    simulation_df.to_csv(simulation_path, index=False, encoding="utf-8-sig")
    summary_df.to_csv(summary_path, index=False, encoding="utf-8-sig")

    print(f"[monte_carlo] simulations csv: {simulation_path}")
    print(f"[monte_carlo] summary csv: {summary_path}")
    if not summary_df.empty:
        print(summary_df.to_string(index=False))


if __name__ == "__main__":
    main()
