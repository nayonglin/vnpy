from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from qmt_roll_official_stage78_config import OFFICIAL_STAGE78_CAPITAL, OFFICIAL_STAGE78_VERSION, build_official_stage78_manifest
from qmt_universe import END_DT, START_DT
from run_qmt_alignment_backtest import OUTPUT_DIR
from run_qmt_roll_monte_carlo import DAILY_BLOCK_SIZE, N_SIMULATIONS, RNG_SEED


MODEL_TAG = "stage232_deployment_capital_tranching_v1"
OUTPUT_PREFIX = "qmt_roll_stage232_deployment_capital_tranching"
BASELINE_DAILY_PATH = OUTPUT_DIR / "qmt_roll_stage225_stage78_1_ai_ablation_suite_main_daily_stage225_stage78_1_ai_ablation_suite_v1.csv"
MULTIPERIOD_CURVES_PATH = OUTPUT_DIR / "qmt_roll_stage225_stage78_1_ai_ablation_suite_multiperiod_curves_stage225_stage78_1_ai_ablation_suite_v1.csv"

WINDOWS: tuple[tuple[str, str, datetime, datetime], ...] = (
    ("since_2020", "2020起点至今", START_DT, END_DT),
    ("since_2021", "2021起点至今", datetime(2021, 1, 1), END_DT),
    ("since_2022", "2022起点至今", datetime(2022, 1, 1), END_DT),
    ("since_2023", "2023起点至今", datetime(2023, 1, 1), END_DT),
    ("since_2024", "2024起点至今", datetime(2024, 1, 1), END_DT),
    ("since_2025", "2025起点至今", datetime(2025, 1, 1), END_DT),
    ("ytd_2026", "2026起点至今", datetime(2026, 1, 1), END_DT),
    ("phase_2020_2021", "2020-2021独立启动", datetime(2020, 1, 1), datetime(2021, 12, 31)),
    ("phase_2022_2023", "2022-2023独立启动", datetime(2022, 1, 1), datetime(2023, 12, 31)),
    ("phase_2024_2025", "2024-2025独立启动", datetime(2024, 1, 1), datetime(2025, 12, 31)),
    ("phase_2026_latest", "2026独立启动至最新", datetime(2026, 1, 1), END_DT),
)


@dataclass(frozen=True)
class TranchePolicy:
    name: str
    production_floor: float
    sweep_start: float
    sweep_ratio: float
    lock_ratio: float
    expansion_ratio: float
    rebalance_frequency: str = "M"


POLICIES: tuple[TranchePolicy, ...] = (
    TranchePolicy(
        name="baseline_full_reinvest",
        production_floor=OFFICIAL_STAGE78_CAPITAL,
        sweep_start=float("inf"),
        sweep_ratio=0.0,
        lock_ratio=0.0,
        expansion_ratio=0.0,
    ),
    TranchePolicy(
        name="profit_tranche_v1",
        production_floor=OFFICIAL_STAGE78_CAPITAL,
        sweep_start=3_000_000.0,
        sweep_ratio=0.70,
        lock_ratio=0.70,
        expansion_ratio=0.30,
    ),
    TranchePolicy(
        name="balanced_tranche_v1",
        production_floor=OFFICIAL_STAGE78_CAPITAL,
        sweep_start=5_000_000.0,
        sweep_ratio=0.50,
        lock_ratio=0.60,
        expansion_ratio=0.40,
    ),
)


def _load_daily_returns() -> pd.DataFrame:
    df = pd.read_csv(MULTIPERIOD_CURVES_PATH)
    df = df[df["variant"].eq("ai_on")].copy()
    df["date"] = pd.to_datetime(df["date"])
    df["balance"] = pd.to_numeric(df["rebased_balance"], errors="coerce").fillna(pd.to_numeric(df["balance"], errors="coerce"))
    frames: list[pd.DataFrame] = []
    for _, group in df.groupby("window_name", sort=False):
        group = group.sort_values("date").reset_index(drop=True)
        group["return"] = group["balance"].pct_change().fillna(group["balance"] / OFFICIAL_STAGE78_CAPITAL - 1.0)
        frames.append(group)
    return pd.concat(frames, ignore_index=True)


def _is_rebalance_day(dates: pd.Series, idx: int) -> bool:
    if idx == len(dates) - 1:
        return True
    current = dates.iloc[idx]
    nxt = dates.iloc[idx + 1]
    return current.month != nxt.month or current.year != nxt.year


def _path_metrics(total_equity: np.ndarray, initial_capital: float = OFFICIAL_STAGE78_CAPITAL) -> dict[str, float]:
    high = np.maximum.accumulate(total_equity)
    drawdown = total_equity - high
    dd_pct = np.divide(drawdown, high, out=np.zeros_like(drawdown), where=high != 0) * 100.0
    daily_return = pd.Series(total_equity).pct_change().fillna(0.0).to_numpy(dtype=float)
    std = float(np.std(daily_return, ddof=1)) if len(daily_return) > 1 else 0.0
    sharpe = float(np.mean(daily_return) / std * np.sqrt(252)) if std > 0 else 0.0
    return {
        "end_equity": float(total_equity[-1]),
        "total_return_pct": float((total_equity[-1] / initial_capital - 1.0) * 100.0),
        "max_dd_percent": float(dd_pct.min()),
        "max_drawdown": float(drawdown.min()),
        "sharpe_ratio": sharpe,
    }


def _simulate_policy(
    returns: np.ndarray,
    dates: pd.Series,
    policy: TranchePolicy,
    *,
    initial_capital: float = OFFICIAL_STAGE78_CAPITAL,
) -> pd.DataFrame:
    production = float(initial_capital)
    locked = 0.0
    expansion = 0.0
    records: list[dict[str, Any]] = []
    for idx, daily_return in enumerate(returns):
        production *= 1.0 + float(daily_return)
        if production < 0:
            production = 0.0

        sweep = 0.0
        refill = 0.0
        if _is_rebalance_day(dates, idx):
            if production < policy.production_floor and expansion > 0:
                refill = min(policy.production_floor - production, expansion)
                production += refill
                expansion -= refill
            if production > policy.sweep_start:
                sweep = (production - policy.sweep_start) * policy.sweep_ratio
                production -= sweep
                locked += sweep * policy.lock_ratio
                expansion += sweep * policy.expansion_ratio

        total_equity = production + locked + expansion
        records.append(
            {
                "date": dates.iloc[idx],
                "policy": policy.name,
                "production_equity": production,
                "locked_equity": locked,
                "expansion_equity": expansion,
                "total_equity": total_equity,
                "sweep_amount": sweep,
                "refill_amount": refill,
                "daily_return_source": float(daily_return),
            }
        )
    return pd.DataFrame(records)


def _run_windows(daily_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    summary_rows: list[dict[str, Any]] = []
    curve_frames: list[pd.DataFrame] = []
    for window_name, display_label, start, end in WINDOWS:
        window_df = daily_df[daily_df["window_name"].eq(window_name)].copy()
        if window_df.empty:
            continue
        dates = window_df["date"].reset_index(drop=True)
        returns = window_df["return"].to_numpy(dtype=float)
        for policy in POLICIES:
            curve = _simulate_policy(returns, dates, policy)
            curve["window_name"] = window_name
            curve["display_label"] = display_label
            metrics = _path_metrics(curve["total_equity"].to_numpy(dtype=float))
            summary_rows.append(
                {
                    "policy": policy.name,
                    "window_name": window_name,
                    "display_label": display_label,
                    "analysis_start": start.date().isoformat(),
                    "analysis_end": end.date().isoformat(),
                    **metrics,
                    "end_production_equity": float(curve["production_equity"].iloc[-1]),
                    "end_locked_equity": float(curve["locked_equity"].iloc[-1]),
                    "end_expansion_equity": float(curve["expansion_equity"].iloc[-1]),
                    "total_swept": float(curve["sweep_amount"].sum()),
                    "total_refilled": float(curve["refill_amount"].sum()),
                }
            )
            curve_frames.append(curve)
    return pd.DataFrame(summary_rows), pd.concat(curve_frames, ignore_index=True)


def _daily_block_bootstrap(policy: TranchePolicy, returns: np.ndarray, dates: pd.Series, rng: np.random.Generator) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    block_count = int(np.ceil(len(returns) / DAILY_BLOCK_SIZE))
    max_start = max(1, len(returns) - DAILY_BLOCK_SIZE + 1)
    synthetic_dates = pd.Series(pd.date_range("2000-01-01", periods=len(returns), freq="B"))
    for sim_id in range(N_SIMULATIONS):
        chunks = []
        for _ in range(block_count):
            start = int(rng.integers(0, max_start))
            chunks.append(returns[start : start + DAILY_BLOCK_SIZE])
        sampled_returns = np.concatenate(chunks)[: len(returns)]
        curve = _simulate_policy(sampled_returns, synthetic_dates, policy)
        metrics = _path_metrics(curve["total_equity"].to_numpy(dtype=float))
        rows.append(
            {
                "policy": policy.name,
                "method": "daily_block_bootstrap",
                "simulation_id": sim_id,
                "min_total_equity": float(curve["total_equity"].min()),
                "min_production_equity": float(curve["production_equity"].min()),
                "end_locked_equity": float(curve["locked_equity"].iloc[-1]),
                "end_expansion_equity": float(curve["expansion_equity"].iloc[-1]),
                **metrics,
            }
        )
    return pd.DataFrame(rows)


def _mc_summary(mc_df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for policy, group in mc_df.groupby("policy", sort=False):
        rows.append(
            {
                "policy": policy,
                "method": "daily_block_bootstrap",
                "simulations": int(len(group)),
                "loss_probability_pct": float((group["total_return_pct"] < 0).mean() * 100.0),
                "production_ruin_probability_pct": float((group["min_production_equity"] <= 0).mean() * 100.0),
                "total_ruin_probability_pct": float((group["min_total_equity"] <= 0).mean() * 100.0),
                "dd_over_20pct_probability_pct": float((group["max_dd_percent"] <= -20.0).mean() * 100.0),
                "dd_over_30pct_probability_pct": float((group["max_dd_percent"] <= -30.0).mean() * 100.0),
                "dd_over_40pct_probability_pct": float((group["max_dd_percent"] <= -40.0).mean() * 100.0),
                "end_equity_q05": float(group["end_equity"].quantile(0.05)),
                "return_pct_q05": float(group["total_return_pct"].quantile(0.05)),
                "max_dd_pct_q05": float(group["max_dd_percent"].quantile(0.05)),
                "end_equity_q50": float(group["end_equity"].quantile(0.50)),
                "return_pct_q50": float(group["total_return_pct"].quantile(0.50)),
                "max_dd_pct_q50": float(group["max_dd_percent"].quantile(0.50)),
                "end_locked_equity_q50": float(group["end_locked_equity"].quantile(0.50)),
            }
        )
    return pd.DataFrame(rows)


def _build_report(summary_df: pd.DataFrame, mc_summary_df: pd.DataFrame, paths: dict[str, str]) -> str:
    lines = [
        "# Stage232 部署资金分层账户层验证",
        "",
        "## 口径",
        "",
        f"- 基准：`{OFFICIAL_STAGE78_VERSION}`",
        f"- 初始资金：`{OFFICIAL_STAGE78_CAPITAL:,.0f}`",
        "- 输入：`78-1 AI ON`日收益路径。",
        "- A：`baseline_full_reinvest`，全部权益继续复利。",
        "- C1：`profit_tranche_v1`，月末超过300万的部分提取70%，其中70%锁盈、30%扩张储备。",
        "- C2：`balanced_tranche_v1`，月末超过500万的部分提取50%，其中60%锁盈、40%扩张储备。",
        "- 注意：这是账户部署层模拟，不是撮合级回测；它用于评估部署资金制度，不替代`78-1`正式回测。",
        "",
        "## 多周期结果",
        "",
        summary_df[
            [
                "policy",
                "window_name",
                "end_equity",
                "total_return_pct",
                "max_dd_percent",
                "sharpe_ratio",
                "end_production_equity",
                "end_locked_equity",
                "end_expansion_equity",
                "total_swept",
            ]
        ].to_markdown(index=False),
        "",
        "## Monte Carlo",
        "",
        mc_summary_df.to_markdown(index=False),
        "",
        "## 输出文件",
        "",
    ]
    for name, path in paths.items():
        lines.append(f"- {name}: `{path}`")
    return "\n".join(lines) + "\n"


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest = build_official_stage78_manifest()
    daily_df = _load_daily_returns()
    summary_df, curves_df = _run_windows(daily_df)
    full_df = daily_df[daily_df["window_name"].eq("since_2020")].copy()
    returns = full_df["return"].to_numpy(dtype=float)
    dates = full_df["date"].reset_index(drop=True)
    rng = np.random.default_rng(RNG_SEED)
    mc_df = pd.concat([_daily_block_bootstrap(policy, returns, dates, rng) for policy in POLICIES], ignore_index=True)
    mc_summary_df = _mc_summary(mc_df)

    paths = {
        "summary": str((OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv").resolve()),
        "curves": str((OUTPUT_DIR / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv").resolve()),
        "mc_simulations": str((OUTPUT_DIR / f"{OUTPUT_PREFIX}_monte_carlo_simulations_{MODEL_TAG}.csv").resolve()),
        "mc_summary": str((OUTPUT_DIR / f"{OUTPUT_PREFIX}_monte_carlo_summary_{MODEL_TAG}.csv").resolve()),
        "report_md": str((OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md").resolve()),
        "manifest": str((OUTPUT_DIR / f"{OUTPUT_PREFIX}_manifest_{MODEL_TAG}.json").resolve()),
    }
    summary_df.to_csv(paths["summary"], index=False, encoding="utf-8-sig")
    curves_df.to_csv(paths["curves"], index=False, encoding="utf-8-sig")
    mc_df.to_csv(paths["mc_simulations"], index=False, encoding="utf-8-sig")
    mc_summary_df.to_csv(paths["mc_summary"], index=False, encoding="utf-8-sig")
    Path(paths["report_md"]).write_text(_build_report(summary_df, mc_summary_df, paths), encoding="utf-8")
    Path(paths["manifest"]).write_text(
        json.dumps(
            {
                "model_tag": MODEL_TAG,
                "output_prefix": OUTPUT_PREFIX,
                "official_manifest": manifest,
                "line_id": "futures_trend_risk_overlay",
                "baseline_daily_path": str(BASELINE_DAILY_PATH.resolve()),
                "multiperiod_curves_path": str(MULTIPERIOD_CURVES_PATH.resolve()),
                "policies": [policy.__dict__ for policy in POLICIES],
                "paths": paths,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(json.dumps(paths, ensure_ascii=False, indent=2))
    print(summary_df[["policy", "window_name", "end_equity", "total_return_pct", "max_dd_percent", "sharpe_ratio", "end_locked_equity"]].to_string(index=False))
    print(mc_summary_df.to_string(index=False))


if __name__ == "__main__":
    main()
