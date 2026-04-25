from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

LONG015_DAILY_PATH: Path = OUTPUT_DIR / "qmt_roll_selection_pairwise_v2_volume_tilt_long015_daily.csv"
VOLREF30_DAILY_PATH: Path = OUTPUT_DIR / "qmt_roll_selection_pairwise_v2_volume_tilt_long015_volref30_daily.csv"

ROLLING_SUMMARY_CSV_PATH: Path = OUTPUT_DIR / "qmt_roll_selection_pairwise_v2_volume_tilt_long015_volref30_bootstrap_rolling_summary.csv"
BOOTSTRAP_JSON_PATH: Path = OUTPUT_DIR / "qmt_roll_selection_pairwise_v2_volume_tilt_long015_volref30_bootstrap_summary.json"

BLOCK_LENGTHS: tuple[int, ...] = (5, 20, 60)
BOOTSTRAP_ITERATIONS: int = 5000
RANDOM_SEED: int = 20260424
ROLLING_WINDOWS: tuple[int, ...] = (126, 252, 504)


def load_daily_curve(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["date"] = pd.to_datetime(df["date"])
    df.sort_values("date", inplace=True)
    df.reset_index(drop=True, inplace=True)
    return df


def build_delta_frame() -> pd.DataFrame:
    long015 = load_daily_curve(LONG015_DAILY_PATH)
    volref30 = load_daily_curve(VOLREF30_DAILY_PATH)

    merged = long015.merge(
        volref30,
        on="date",
        suffixes=("_long015", "_volref30"),
        how="inner",
    )
    merged["delta_net_pnl"] = merged["net_pnl_volref30"] - merged["net_pnl_long015"]
    merged["delta_trade_count"] = merged["trade_count_volref30"] - merged["trade_count_long015"]
    return merged


def sample_moving_blocks(values: np.ndarray, block_length: int, rng: np.random.Generator) -> np.ndarray:
    n = len(values)
    if n <= 0:
        return np.array([], dtype=np.float64)

    indices: list[np.ndarray] = []
    while sum(len(idx) for idx in indices) < n:
        start = int(rng.integers(0, max(1, n - block_length + 1)))
        block = np.arange(start, min(n, start + block_length))
        indices.append(block)
    sampled_index = np.concatenate(indices)[:n]
    return values[sampled_index]


def bootstrap_summary(delta_net_pnl: np.ndarray) -> dict[str, object]:
    rng = np.random.default_rng(RANDOM_SEED)
    observed_total = float(delta_net_pnl.sum())
    observed_mean = float(delta_net_pnl.mean())

    payload: dict[str, object] = {
        "observed_total_delta_net_pnl": observed_total,
        "observed_mean_daily_delta_net_pnl": observed_mean,
        "iterations": BOOTSTRAP_ITERATIONS,
        "block_lengths": list(BLOCK_LENGTHS),
    }

    block_results: list[dict[str, object]] = []
    for block_length in BLOCK_LENGTHS:
        sampled_totals = np.empty(BOOTSTRAP_ITERATIONS, dtype=np.float64)
        for i in range(BOOTSTRAP_ITERATIONS):
            sampled = sample_moving_blocks(delta_net_pnl, block_length, rng)
            sampled_totals[i] = sampled.sum()

        block_results.append(
            {
                "block_length": block_length,
                "mean_total_delta_net_pnl": float(sampled_totals.mean()),
                "median_total_delta_net_pnl": float(np.median(sampled_totals)),
                "p05_total_delta_net_pnl": float(np.quantile(sampled_totals, 0.05)),
                "p25_total_delta_net_pnl": float(np.quantile(sampled_totals, 0.25)),
                "p75_total_delta_net_pnl": float(np.quantile(sampled_totals, 0.75)),
                "p95_total_delta_net_pnl": float(np.quantile(sampled_totals, 0.95)),
                "positive_total_delta_probability": float((sampled_totals > 0.0).mean()),
                "non_negative_total_delta_probability": float((sampled_totals >= 0.0).mean()),
            }
        )

    payload["bootstrap"] = block_results
    return payload


def compute_window_metrics(window_df: pd.DataFrame) -> dict[str, float]:
    long_end = float(window_df["balance_long015"].iloc[-1])
    volref30_end = float(window_df["balance_volref30"].iloc[-1])
    long_start = float(window_df["balance_long015"].iloc[0] - window_df["net_pnl_long015"].iloc[0])
    volref30_start = float(window_df["balance_volref30"].iloc[0] - window_df["net_pnl_volref30"].iloc[0])

    def total_return(end_balance: float, start_balance: float) -> float:
        if abs(start_balance) < 1e-9:
            return 0.0
        return (end_balance / start_balance - 1.0) * 100.0

    long_total_return = total_return(long_end, long_start)
    volref30_total_return = total_return(volref30_end, volref30_start)

    long_curve = window_df["balance_long015"].to_numpy(dtype=np.float64)
    volref30_curve = window_df["balance_volref30"].to_numpy(dtype=np.float64)
    long_dd = float(((long_curve / np.maximum.accumulate(long_curve)) - 1.0).min() * 100.0)
    volref30_dd = float(((volref30_curve / np.maximum.accumulate(volref30_curve)) - 1.0).min() * 100.0)

    return {
        "delta_end_balance": volref30_end - long_end,
        "delta_total_return_pct": volref30_total_return - long_total_return,
        "delta_max_dd_pct": volref30_dd - long_dd,
        "delta_net_pnl": float(window_df["delta_net_pnl"].sum()),
    }


def rolling_summary(delta_df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for window in ROLLING_WINDOWS:
        if len(delta_df) < window:
            continue

        metrics_rows: list[dict[str, float]] = []
        for start in range(0, len(delta_df) - window + 1):
            window_df = delta_df.iloc[start:start + window]
            metrics_rows.append(compute_window_metrics(window_df))

        metrics_df = pd.DataFrame(metrics_rows)
        rows.append(
            {
                "window_days": window,
                "sample_count": int(len(metrics_df)),
                "positive_end_balance_ratio": float((metrics_df["delta_end_balance"] > 0.0).mean()),
                "positive_total_return_ratio": float((metrics_df["delta_total_return_pct"] > 0.0).mean()),
                "better_max_dd_ratio": float((metrics_df["delta_max_dd_pct"] > 0.0).mean()),
                "mean_delta_end_balance": float(metrics_df["delta_end_balance"].mean()),
                "median_delta_end_balance": float(metrics_df["delta_end_balance"].median()),
                "mean_delta_total_return_pct": float(metrics_df["delta_total_return_pct"].mean()),
                "median_delta_total_return_pct": float(metrics_df["delta_total_return_pct"].median()),
            }
        )

    return pd.DataFrame(rows)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    delta_df = build_delta_frame()
    bootstrap_payload = bootstrap_summary(delta_df["delta_net_pnl"].to_numpy(dtype=np.float64))
    rolling_df = rolling_summary(delta_df)

    BOOTSTRAP_JSON_PATH.write_text(
        json.dumps(bootstrap_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    rolling_df.to_csv(ROLLING_SUMMARY_CSV_PATH, index=False, encoding="utf-8-sig")

    print(f"bootstrap summary json: {BOOTSTRAP_JSON_PATH}")
    print(f"rolling summary csv: {ROLLING_SUMMARY_CSV_PATH}")
    print(json.dumps(bootstrap_payload, ensure_ascii=False, indent=2))
    print(rolling_df.to_string(index=False))


if __name__ == "__main__":
    main()
