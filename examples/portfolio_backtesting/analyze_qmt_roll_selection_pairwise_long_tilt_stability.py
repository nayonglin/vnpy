from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

BASE_EXPERIMENT_NAME: str = "selection_pairwise_v2"
BASE_FILE_PREFIX: str = "qmt_roll_selection_pairwise_v2_long_tilt_stability"

EXPERIMENTS: tuple[tuple[str, str], ...] = (
    ("selection_pairwise_v2_volume_tilt_long010", "qmt_roll_selection_pairwise_v2_volume_tilt_long010_stability"),
    ("selection_pairwise_v2_volume_tilt_long015", "qmt_roll_selection_pairwise_v2_volume_tilt_long015_stability"),
    ("selection_pairwise_v2_volume_tilt_long020", "qmt_roll_selection_pairwise_v2_volume_tilt_long020_stability"),
)

BLOCK_LENGTHS: tuple[int, ...] = (5, 20, 60)
BOOTSTRAP_ITERATIONS: int = 5000
RANDOM_SEED: int = 20260424
ROLLING_WINDOWS: tuple[int, ...] = (126, 252, 504)

SUMMARY_JSON_PATH: Path = OUTPUT_DIR / "qmt_roll_selection_pairwise_long_tilt_stability_analysis_summary.json"
ROLLING_CSV_PATH: Path = OUTPUT_DIR / "qmt_roll_selection_pairwise_long_tilt_stability_analysis_rolling.csv"


def load_daily_curve(file_prefix: str) -> pd.DataFrame:
    path = OUTPUT_DIR / f"{file_prefix}_daily.csv"
    df = pd.read_csv(path)
    df["date"] = pd.to_datetime(df["date"])
    df.sort_values("date", inplace=True)
    df.reset_index(drop=True, inplace=True)
    return df


def build_delta_frame(base_df: pd.DataFrame, compare_df: pd.DataFrame, compare_suffix: str) -> pd.DataFrame:
    merged = base_df.merge(
        compare_df,
        on="date",
        suffixes=("_base", compare_suffix),
        how="inner",
    )
    merged["delta_net_pnl"] = merged[f"net_pnl{compare_suffix}"] - merged["net_pnl_base"]
    merged["delta_trade_count"] = merged[f"trade_count{compare_suffix}"] - merged["trade_count_base"]
    return merged


def sample_moving_blocks(values: np.ndarray, block_length: int, rng: np.random.Generator) -> np.ndarray:
    n = len(values)
    if n <= 0:
        return np.array([], dtype=np.float64)

    blocks: list[np.ndarray] = []
    total = 0
    while total < n:
        start = int(rng.integers(0, max(1, n - block_length + 1)))
        block = np.arange(start, min(n, start + block_length))
        blocks.append(block)
        total += len(block)
    sampled_index = np.concatenate(blocks)[:n]
    return values[sampled_index]


def bootstrap_summary(delta_net_pnl: np.ndarray) -> list[dict[str, float]]:
    rng = np.random.default_rng(RANDOM_SEED)
    results: list[dict[str, float]] = []
    for block_length in BLOCK_LENGTHS:
        sampled_totals = np.empty(BOOTSTRAP_ITERATIONS, dtype=np.float64)
        for i in range(BOOTSTRAP_ITERATIONS):
            sampled = sample_moving_blocks(delta_net_pnl, block_length, rng)
            sampled_totals[i] = sampled.sum()
        results.append(
            {
                "block_length": float(block_length),
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
    return results


def compute_window_metrics(window_df: pd.DataFrame, compare_suffix: str) -> dict[str, float]:
    base_end = float(window_df["balance_base"].iloc[-1])
    compare_end = float(window_df[f"balance{compare_suffix}"].iloc[-1])
    base_start = float(window_df["balance_base"].iloc[0] - window_df["net_pnl_base"].iloc[0])
    compare_start = float(window_df[f"balance{compare_suffix}"].iloc[0] - window_df[f"net_pnl{compare_suffix}"].iloc[0])

    def total_return(end_balance: float, start_balance: float) -> float:
        if abs(start_balance) < 1e-9:
            return 0.0
        return (end_balance / start_balance - 1.0) * 100.0

    base_total_return = total_return(base_end, base_start)
    compare_total_return = total_return(compare_end, compare_start)

    base_curve = window_df["balance_base"].to_numpy(dtype=np.float64)
    compare_curve = window_df[f"balance{compare_suffix}"].to_numpy(dtype=np.float64)
    base_dd = float(((base_curve / np.maximum.accumulate(base_curve)) - 1.0).min() * 100.0)
    compare_dd = float(((compare_curve / np.maximum.accumulate(compare_curve)) - 1.0).min() * 100.0)

    return {
        "delta_end_balance": compare_end - base_end,
        "delta_total_return_pct": compare_total_return - base_total_return,
        "delta_max_dd_pct": compare_dd - base_dd,
        "delta_net_pnl": float(window_df["delta_net_pnl"].sum()),
    }


def rolling_summary(delta_df: pd.DataFrame, compare_suffix: str) -> pd.DataFrame:
    rows: list[dict[str, float]] = []
    for window in ROLLING_WINDOWS:
        if len(delta_df) < window:
            continue
        metrics_rows: list[dict[str, float]] = []
        for start in range(0, len(delta_df) - window + 1):
            window_df = delta_df.iloc[start:start + window]
            metrics_rows.append(compute_window_metrics(window_df, compare_suffix))
        metrics_df = pd.DataFrame(metrics_rows)
        rows.append(
            {
                "window_days": float(window),
                "sample_count": float(len(metrics_df)),
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


def analyze_experiment(base_df: pd.DataFrame, experiment_name: str, file_prefix: str) -> tuple[dict[str, object], pd.DataFrame]:
    compare_df = load_daily_curve(file_prefix)
    compare_suffix = f"_{experiment_name}"
    delta_df = build_delta_frame(base_df, compare_df, compare_suffix)
    payload: dict[str, object] = {
        "experiment_name": experiment_name,
        "observed_total_delta_net_pnl": float(delta_df["delta_net_pnl"].sum()),
        "observed_mean_daily_delta_net_pnl": float(delta_df["delta_net_pnl"].mean()),
        "bootstrap_iterations": BOOTSTRAP_ITERATIONS,
        "block_lengths": list(BLOCK_LENGTHS),
        "bootstrap": bootstrap_summary(delta_df["delta_net_pnl"].to_numpy(dtype=np.float64)),
    }
    rolling_df = rolling_summary(delta_df, compare_suffix)
    rolling_df.insert(0, "experiment_name", experiment_name)
    return payload, rolling_df


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    base_df = load_daily_curve(BASE_FILE_PREFIX)

    experiment_payloads: list[dict[str, object]] = []
    rolling_frames: list[pd.DataFrame] = []
    for experiment_name, file_prefix in EXPERIMENTS:
        payload, rolling_df = analyze_experiment(base_df, experiment_name, file_prefix)
        experiment_payloads.append(payload)
        rolling_frames.append(rolling_df)

    summary_payload = {
        "base_experiment_name": BASE_EXPERIMENT_NAME,
        "base_file_prefix": BASE_FILE_PREFIX,
        "experiments": experiment_payloads,
    }
    SUMMARY_JSON_PATH.write_text(json.dumps(summary_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    rolling_summary_df = pd.concat(rolling_frames, ignore_index=True) if rolling_frames else pd.DataFrame()
    rolling_summary_df.to_csv(ROLLING_CSV_PATH, index=False, encoding="utf-8-sig")

    print(f"stability summary json: {SUMMARY_JSON_PATH}")
    print(f"stability rolling csv: {ROLLING_CSV_PATH}")
    print(json.dumps(summary_payload, ensure_ascii=False, indent=2))
    if not rolling_summary_df.empty:
        print(rolling_summary_df.to_string(index=False))


if __name__ == "__main__":
    main()
