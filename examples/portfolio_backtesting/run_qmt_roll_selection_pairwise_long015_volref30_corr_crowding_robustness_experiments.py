from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

BASELINE_DAILY_PATH: Path = OUTPUT_DIR / "qmt_roll_selection_long015_volref30_corr_formal_current_daily.csv"
CANDIDATE_DAILY_PATH: Path = OUTPUT_DIR / "qmt_roll_selection_long015_volref30_corr_formal_floor35_daily.csv"

OUTPUT_PREFIX: str = "qmt_roll_selection_pairwise_long015_volref30_corr_crowding_robustness"

ROLLING_WINDOWS_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_rolling_windows.csv"
ROLLING_COMPARISON_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_rolling_comparison.csv"
ROLLING_SUMMARY_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_rolling_summary.csv"
BLOCK_BOOTSTRAP_PATHS_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_block_bootstrap_paths.csv"
BLOCK_BOOTSTRAP_SUMMARY_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_block_bootstrap_summary.csv"
SLIPPAGE_STRESS_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_slippage_stress.csv"
SUMMARY_JSON_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary.json"

INITIAL_CAPITAL: float = 200_000.0
TRADING_DAYS_PER_YEAR: int = 240
ROLLING_WINDOWS: tuple[int, ...] = (240, 480, 720)
ROLLING_STEP: int = 20
BOOTSTRAP_BLOCK_LENGTHS: tuple[int, ...] = (20, 40, 60)
BOOTSTRAP_PATH_COUNT: int = 1_000
RANDOM_SEED: int = 20260424
SLIPPAGE_MULTIPLIERS: tuple[float, ...] = (1.0, 1.5, 2.0, 3.0, 5.0)


def load_daily(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["date"] = pd.to_datetime(df["date"])
    df.sort_values("date", inplace=True)
    df.reset_index(drop=True, inplace=True)
    return df


def calculate_metrics_from_returns(returns: np.ndarray, *, initial_capital: float = INITIAL_CAPITAL) -> dict[str, float]:
    if len(returns) == 0:
        return empty_metrics()
    equity = initial_capital * np.cumprod(1.0 + returns.astype(float))
    return calculate_metrics_from_equity(equity, returns, initial_capital=initial_capital)


def calculate_metrics_from_net_pnl(net_pnl: np.ndarray, *, initial_capital: float = INITIAL_CAPITAL) -> dict[str, float]:
    if len(net_pnl) == 0:
        return empty_metrics()
    equity = initial_capital + np.cumsum(net_pnl.astype(float))
    prev_equity = np.concatenate([[initial_capital], equity[:-1]])
    returns = np.divide(net_pnl, prev_equity, out=np.zeros_like(net_pnl, dtype=float), where=prev_equity != 0)
    return calculate_metrics_from_equity(equity, returns, initial_capital=initial_capital)


def calculate_metrics_from_equity(
    equity: np.ndarray,
    returns: np.ndarray,
    *,
    initial_capital: float = INITIAL_CAPITAL,
) -> dict[str, float]:
    end_balance = float(equity[-1])
    total_return_pct = (end_balance / initial_capital - 1.0) * 100.0
    high_water = np.maximum.accumulate(equity)
    drawdown_pct = np.divide(
        equity - high_water,
        high_water,
        out=np.zeros_like(equity, dtype=float),
        where=high_water != 0,
    ) * 100.0
    max_dd_percent = float(drawdown_pct.min())
    return_std = float(np.std(returns, ddof=1)) if len(returns) > 1 else 0.0
    sharpe_ratio = float(np.mean(returns) / return_std * np.sqrt(TRADING_DAYS_PER_YEAR)) if return_std > 0 else 0.0
    return {
        "end_balance": end_balance,
        "total_return_pct": total_return_pct,
        "max_dd_percent": max_dd_percent,
        "sharpe_ratio": sharpe_ratio,
        "daily_return_mean": float(np.mean(returns)),
        "daily_return_std": return_std,
    }


def empty_metrics() -> dict[str, float]:
    return {
        "end_balance": 0.0,
        "total_return_pct": 0.0,
        "max_dd_percent": 0.0,
        "sharpe_ratio": 0.0,
        "daily_return_mean": 0.0,
        "daily_return_std": 0.0,
    }


def build_rolling_windows(strategy_name: str, daily: pd.DataFrame) -> pd.DataFrame:
    returns = daily["return"].to_numpy(dtype=float)
    rows: list[dict[str, Any]] = []
    for window in ROLLING_WINDOWS:
        if len(daily) < window:
            continue
        for start in range(0, len(daily) - window + 1, ROLLING_STEP):
            end = start + window
            metrics = calculate_metrics_from_returns(returns[start:end])
            rows.append(
                {
                    "strategy_name": strategy_name,
                    "window_days": window,
                    "start_date": daily["date"].iloc[start].date().isoformat(),
                    "end_date": daily["date"].iloc[end - 1].date().isoformat(),
                    **metrics,
                }
            )
    return pd.DataFrame(rows)


def build_rolling_comparison(rolling_df: pd.DataFrame) -> pd.DataFrame:
    baseline = rolling_df[rolling_df["strategy_name"] == "baseline"].copy()
    candidate = rolling_df[rolling_df["strategy_name"] == "candidate"].copy()
    merged = baseline.merge(
        candidate,
        on=["window_days", "start_date", "end_date"],
        suffixes=("_baseline", "_candidate"),
        how="inner",
    )
    for column in ["end_balance", "total_return_pct", "max_dd_percent", "sharpe_ratio"]:
        merged[f"{column}_diff"] = merged[f"{column}_candidate"] - merged[f"{column}_baseline"]
    return merged


def summarize_rolling(rolling_df: pd.DataFrame) -> pd.DataFrame:
    grouped = rolling_df.groupby(["strategy_name", "window_days"]).agg(
        window_count=("start_date", "size"),
        positive_return_rate=("total_return_pct", lambda values: float((values > 0).mean())),
        mean_total_return_pct=("total_return_pct", "mean"),
        median_total_return_pct=("total_return_pct", "median"),
        min_total_return_pct=("total_return_pct", "min"),
        q10_total_return_pct=("total_return_pct", lambda values: float(np.quantile(values, 0.10))),
        mean_max_dd_percent=("max_dd_percent", "mean"),
        worst_max_dd_percent=("max_dd_percent", "min"),
        median_sharpe_ratio=("sharpe_ratio", "median"),
        min_sharpe_ratio=("sharpe_ratio", "min"),
    )
    grouped.reset_index(inplace=True)
    return grouped


def sample_block_returns(
    returns: np.ndarray,
    *,
    block_length: int,
    rng: np.random.Generator,
) -> np.ndarray:
    sampled: list[np.ndarray] = []
    while sum(len(block) for block in sampled) < len(returns):
        start = int(rng.integers(0, max(1, len(returns) - block_length + 1)))
        sampled.append(returns[start : start + block_length])
    return np.concatenate(sampled)[: len(returns)]


def build_block_bootstrap_paths(strategy_name: str, daily: pd.DataFrame) -> pd.DataFrame:
    returns = daily["return"].to_numpy(dtype=float)
    rng = np.random.default_rng(RANDOM_SEED + (0 if strategy_name == "baseline" else 10_000))
    rows: list[dict[str, Any]] = []
    for block_length in BOOTSTRAP_BLOCK_LENGTHS:
        for path_index in range(BOOTSTRAP_PATH_COUNT):
            sampled_returns = sample_block_returns(returns, block_length=block_length, rng=rng)
            metrics = calculate_metrics_from_returns(sampled_returns)
            rows.append(
                {
                    "strategy_name": strategy_name,
                    "block_length": block_length,
                    "path_index": path_index,
                    **metrics,
                }
            )
    return pd.DataFrame(rows)


def summarize_bootstrap(paths_df: pd.DataFrame) -> pd.DataFrame:
    grouped = paths_df.groupby(["strategy_name", "block_length"]).agg(
        path_count=("path_index", "size"),
        final_equity_mean=("end_balance", "mean"),
        final_equity_median=("end_balance", "median"),
        final_equity_p05=("end_balance", lambda values: float(np.quantile(values, 0.05))),
        final_equity_p01=("end_balance", lambda values: float(np.quantile(values, 0.01))),
        probability_final_below_initial=("end_balance", lambda values: float((values < INITIAL_CAPITAL).mean())),
        total_return_p05=("total_return_pct", lambda values: float(np.quantile(values, 0.05))),
        max_dd_median=("max_dd_percent", "median"),
        max_dd_p05=("max_dd_percent", lambda values: float(np.quantile(values, 0.05))),
        probability_max_dd_below_minus_50=("max_dd_percent", lambda values: float((values < -50.0).mean())),
        sharpe_median=("sharpe_ratio", "median"),
        sharpe_p05=("sharpe_ratio", lambda values: float(np.quantile(values, 0.05))),
        probability_sharpe_below_zero=("sharpe_ratio", lambda values: float((values < 0.0).mean())),
    )
    grouped.reset_index(inplace=True)
    return grouped


def build_slippage_stress(daily: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    base_net_pnl = daily["net_pnl"].to_numpy(dtype=float)
    slippage = daily["slippage"].to_numpy(dtype=float)
    for multiplier in SLIPPAGE_MULTIPLIERS:
        stressed_net_pnl = base_net_pnl - (multiplier - 1.0) * slippage
        metrics = calculate_metrics_from_net_pnl(stressed_net_pnl)
        rows.append(
            {
                "slippage_multiplier": multiplier,
                "extra_slippage": float(((multiplier - 1.0) * slippage).sum()),
                "total_slippage": float((multiplier * slippage).sum()),
                **metrics,
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    baseline_daily = load_daily(BASELINE_DAILY_PATH)
    candidate_daily = load_daily(CANDIDATE_DAILY_PATH)

    rolling_df = pd.concat(
        [
            build_rolling_windows("baseline", baseline_daily),
            build_rolling_windows("candidate", candidate_daily),
        ],
        ignore_index=True,
    )
    rolling_comparison = build_rolling_comparison(rolling_df)
    rolling_summary = summarize_rolling(rolling_df)

    bootstrap_paths = pd.concat(
        [
            build_block_bootstrap_paths("baseline", baseline_daily),
            build_block_bootstrap_paths("candidate", candidate_daily),
        ],
        ignore_index=True,
    )
    bootstrap_summary = summarize_bootstrap(bootstrap_paths)
    slippage_stress = build_slippage_stress(candidate_daily)

    rolling_df.to_csv(ROLLING_WINDOWS_CSV_PATH, index=False, encoding="utf-8-sig")
    rolling_comparison.to_csv(ROLLING_COMPARISON_CSV_PATH, index=False, encoding="utf-8-sig")
    rolling_summary.to_csv(ROLLING_SUMMARY_CSV_PATH, index=False, encoding="utf-8-sig")
    bootstrap_paths.to_csv(BLOCK_BOOTSTRAP_PATHS_CSV_PATH, index=False, encoding="utf-8-sig")
    bootstrap_summary.to_csv(BLOCK_BOOTSTRAP_SUMMARY_CSV_PATH, index=False, encoding="utf-8-sig")
    slippage_stress.to_csv(SLIPPAGE_STRESS_CSV_PATH, index=False, encoding="utf-8-sig")

    candidate_rolling = rolling_summary[rolling_summary["strategy_name"] == "candidate"].to_dict(orient="records")
    candidate_bootstrap = bootstrap_summary[bootstrap_summary["strategy_name"] == "candidate"].to_dict(
        orient="records"
    )
    comparison_summary = rolling_comparison.groupby("window_days").agg(
        comparison_count=("start_date", "size"),
        candidate_win_rate_end_balance=("end_balance_diff", lambda values: float((values > 0).mean())),
        median_end_balance_diff=("end_balance_diff", "median"),
        median_sharpe_diff=("sharpe_ratio_diff", "median"),
        median_max_dd_percent_diff=("max_dd_percent_diff", "median"),
    )
    comparison_summary.reset_index(inplace=True)

    payload: dict[str, Any] = {
        "analysis": OUTPUT_PREFIX,
        "rolling_windows": list(ROLLING_WINDOWS),
        "rolling_step": ROLLING_STEP,
        "bootstrap_block_lengths": list(BOOTSTRAP_BLOCK_LENGTHS),
        "bootstrap_path_count": BOOTSTRAP_PATH_COUNT,
        "random_seed": RANDOM_SEED,
        "candidate_rolling_summary": candidate_rolling,
        "rolling_comparison_summary": comparison_summary.to_dict(orient="records"),
        "candidate_block_bootstrap_summary": candidate_bootstrap,
        "slippage_stress": slippage_stress.to_dict(orient="records"),
        "artifacts": {
            "rolling_windows_csv": str(ROLLING_WINDOWS_CSV_PATH),
            "rolling_comparison_csv": str(ROLLING_COMPARISON_CSV_PATH),
            "rolling_summary_csv": str(ROLLING_SUMMARY_CSV_PATH),
            "block_bootstrap_paths_csv": str(BLOCK_BOOTSTRAP_PATHS_CSV_PATH),
            "block_bootstrap_summary_csv": str(BLOCK_BOOTSTRAP_SUMMARY_CSV_PATH),
            "slippage_stress_csv": str(SLIPPAGE_STRESS_CSV_PATH),
            "summary_json": str(SUMMARY_JSON_PATH),
        },
    }
    SUMMARY_JSON_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )

    print(f"robustness summary json: {SUMMARY_JSON_PATH}")
    print(f"rolling summary csv: {ROLLING_SUMMARY_CSV_PATH}")
    print(f"bootstrap summary csv: {BLOCK_BOOTSTRAP_SUMMARY_CSV_PATH}")
    print(f"slippage stress csv: {SLIPPAGE_STRESS_CSV_PATH}")
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    print("\n[rolling summary]")
    print(rolling_summary.to_string(index=False))
    print("\n[rolling comparison]")
    print(comparison_summary.to_string(index=False))
    print("\n[bootstrap summary]")
    print(bootstrap_summary.to_string(index=False))
    print("\n[slippage stress]")
    print(slippage_stress.to_string(index=False))


if __name__ == "__main__":
    main()
