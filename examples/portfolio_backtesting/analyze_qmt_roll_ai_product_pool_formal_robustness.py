from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

BASELINE_PREFIX: str = "qmt_roll_selection_long015_volref30_corr_formal_floor35"
AI_PREFIX: str = "qmt_roll_selection_long015_volref30_corr_ai_top8_product_pool_formal"
OUTPUT_PREFIX: str = "qmt_roll_ai_product_pool_formal_robustness"
MODEL_TAG: str = "ai_top8_formal_robustness_v1"

BASELINE_DAILY_PATH: Path = OUTPUT_DIR / f"{BASELINE_PREFIX}_daily.csv"
AI_DAILY_PATH: Path = OUTPUT_DIR / f"{AI_PREFIX}_daily.csv"

LEAVE_ONE_YEAR_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_leave_one_year_{MODEL_TAG}.csv"
SLIPPAGE_STRESS_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_slippage_stress_{MODEL_TAG}.csv"
START_DATE_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_start_date_{MODEL_TAG}.csv"
SUMMARY_JSON_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.json"
REPORT_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

TRADING_DAYS_PER_YEAR: int = 240
POST_SIGNAL_START: pd.Timestamp = pd.Timestamp("2022-02-07")
SLIPPAGE_MULTIPLIERS: tuple[float, ...] = (1.0, 2.0, 3.0, 5.0)
START_DATES: tuple[pd.Timestamp, ...] = (
    pd.Timestamp("2022-02-07"),
    pd.Timestamp("2023-01-03"),
    pd.Timestamp("2024-01-02"),
    pd.Timestamp("2025-01-02"),
    pd.Timestamp("2026-01-02"),
)


def load_daily(path: Path, strategy: str) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"missing daily csv: {path}")
    df = pd.read_csv(path)
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    for column in ["net_pnl", "balance", "trade_count", "slippage"]:
        df[column] = pd.to_numeric(df[column], errors="coerce").fillna(0.0)
    df["strategy"] = strategy
    df.sort_values("date", inplace=True)
    df.reset_index(drop=True, inplace=True)
    return df


def metrics_from_net_pnl(df: pd.DataFrame, initial_balance: float, net_pnl_column: str = "net_pnl") -> dict[str, float]:
    if df.empty:
        return {
            "end_balance": initial_balance,
            "total_return_pct": 0.0,
            "max_dd_percent": 0.0,
            "sharpe_ratio": 0.0,
            "total_net_pnl": 0.0,
            "total_trade_count": 0.0,
            "total_slippage": 0.0,
        }
    net_pnl = df[net_pnl_column].to_numpy(dtype=float)
    equity = initial_balance + np.cumsum(net_pnl)
    previous = np.concatenate([[initial_balance], equity[:-1]])
    returns = np.divide(net_pnl, previous, out=np.zeros_like(net_pnl), where=previous != 0.0)
    high = np.maximum.accumulate(equity)
    drawdown_pct = np.divide(equity - high, high, out=np.zeros_like(equity), where=high != 0.0) * 100.0
    return_std = float(np.std(returns, ddof=1)) if len(returns) > 1 else 0.0
    sharpe = float(np.mean(returns) / return_std * math.sqrt(TRADING_DAYS_PER_YEAR)) if return_std > 0 else 0.0
    return {
        "end_balance": float(equity[-1]),
        "total_return_pct": float((equity[-1] / initial_balance - 1.0) * 100.0) if initial_balance else 0.0,
        "max_dd_percent": float(drawdown_pct.min()) if len(drawdown_pct) else 0.0,
        "sharpe_ratio": sharpe,
        "total_net_pnl": float(np.sum(net_pnl)),
        "total_trade_count": float(df["trade_count"].sum()),
        "total_slippage": float(df["slippage"].sum()),
    }


def initial_balance_for_start(df: pd.DataFrame, start_date: pd.Timestamp) -> float:
    part = df[df["date"] >= start_date]
    if part.empty:
        return float(df["balance"].iloc[-1])
    first = part.iloc[0]
    return float(first["balance"] - first["net_pnl"])


def build_leave_one_year(baseline: pd.DataFrame, ai: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    post_baseline = baseline[baseline["date"] >= POST_SIGNAL_START].copy()
    post_ai = ai[ai["date"] >= POST_SIGNAL_START].copy()
    initial_balance = initial_balance_for_start(baseline, POST_SIGNAL_START)
    years = sorted(set(post_baseline["date"].dt.year) | set(post_ai["date"].dt.year))
    for excluded_year in years:
        base_part = post_baseline[post_baseline["date"].dt.year != excluded_year]
        ai_part = post_ai[post_ai["date"].dt.year != excluded_year]
        base_metrics = metrics_from_net_pnl(base_part, initial_balance)
        ai_metrics = metrics_from_net_pnl(ai_part, initial_balance)
        rows.append(
            {
                "excluded_year": int(excluded_year),
                "baseline_total_net_pnl": base_metrics["total_net_pnl"],
                "ai_total_net_pnl": ai_metrics["total_net_pnl"],
                "ai_net_pnl_diff": ai_metrics["total_net_pnl"] - base_metrics["total_net_pnl"],
                "baseline_sharpe": base_metrics["sharpe_ratio"],
                "ai_sharpe": ai_metrics["sharpe_ratio"],
                "ai_sharpe_diff": ai_metrics["sharpe_ratio"] - base_metrics["sharpe_ratio"],
                "baseline_max_dd_percent": base_metrics["max_dd_percent"],
                "ai_max_dd_percent": ai_metrics["max_dd_percent"],
            }
        )
    return pd.DataFrame(rows)


def build_slippage_stress(baseline: pd.DataFrame, ai: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for start_name, start_date in [("full", baseline["date"].min()), ("post_signal", POST_SIGNAL_START)]:
        initial_balance = initial_balance_for_start(baseline, start_date)
        base_part = baseline[baseline["date"] >= start_date].copy()
        ai_part = ai[ai["date"] >= start_date].copy()
        for multiplier in SLIPPAGE_MULTIPLIERS:
            for strategy, part in [("baseline", base_part), ("ai_top8", ai_part)]:
                stressed = part.copy()
                stressed["stressed_net_pnl"] = stressed["net_pnl"] - (multiplier - 1.0) * stressed["slippage"]
                metrics = metrics_from_net_pnl(stressed, initial_balance, "stressed_net_pnl")
                rows.append(
                    {
                        "start_name": start_name,
                        "start_date": start_date.date().isoformat(),
                        "strategy": strategy,
                        "slippage_multiplier": multiplier,
                        **metrics,
                    }
                )
    result = pd.DataFrame(rows)
    baseline_rows = result[result["strategy"] == "baseline"].copy()
    compare_rows: list[dict[str, Any]] = []
    for _, ai_row in result[result["strategy"] == "ai_top8"].iterrows():
        base_row = baseline_rows[
            (baseline_rows["start_name"] == ai_row["start_name"])
            & (baseline_rows["slippage_multiplier"] == ai_row["slippage_multiplier"])
        ].iloc[0]
        payload = ai_row.to_dict()
        payload["end_balance_diff_vs_baseline"] = float(ai_row["end_balance"] - base_row["end_balance"])
        payload["sharpe_diff_vs_baseline"] = float(ai_row["sharpe_ratio"] - base_row["sharpe_ratio"])
        payload["max_dd_percent_diff_vs_baseline"] = float(ai_row["max_dd_percent"] - base_row["max_dd_percent"])
        compare_rows.append(payload)
    return pd.DataFrame(compare_rows)


def build_start_date_sensitivity(baseline: pd.DataFrame, ai: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for start_date in START_DATES:
        initial_balance = initial_balance_for_start(baseline, start_date)
        base_part = baseline[baseline["date"] >= start_date].copy()
        ai_part = ai[ai["date"] >= start_date].copy()
        if base_part.empty or ai_part.empty:
            continue
        base_metrics = metrics_from_net_pnl(base_part, initial_balance)
        ai_metrics = metrics_from_net_pnl(ai_part, initial_balance)
        rows.append(
            {
                "start_date": start_date.date().isoformat(),
                "baseline_end_balance": base_metrics["end_balance"],
                "ai_end_balance": ai_metrics["end_balance"],
                "ai_end_balance_diff": ai_metrics["end_balance"] - base_metrics["end_balance"],
                "baseline_total_return_pct": base_metrics["total_return_pct"],
                "ai_total_return_pct": ai_metrics["total_return_pct"],
                "baseline_max_dd_percent": base_metrics["max_dd_percent"],
                "ai_max_dd_percent": ai_metrics["max_dd_percent"],
                "baseline_sharpe": base_metrics["sharpe_ratio"],
                "ai_sharpe": ai_metrics["sharpe_ratio"],
                "ai_sharpe_diff": ai_metrics["sharpe_ratio"] - base_metrics["sharpe_ratio"],
                "baseline_trade_count": base_metrics["total_trade_count"],
                "ai_trade_count": ai_metrics["total_trade_count"],
                "baseline_slippage": base_metrics["total_slippage"],
                "ai_slippage": ai_metrics["total_slippage"],
            }
        )
    return pd.DataFrame(rows)


def to_markdown_table(df: pd.DataFrame) -> str:
    if df.empty:
        return "_empty_"
    view = df.copy()
    for column in view.columns:
        if pd.api.types.is_float_dtype(view[column]):
            view[column] = view[column].map(lambda value: f"{value:.4f}")
    header = "| " + " | ".join(view.columns) + " |"
    separator = "| " + " | ".join(["---"] * len(view.columns)) + " |"
    rows = ["| " + " | ".join(map(str, row)) + " |" for row in view.to_numpy()]
    return "\n".join([header, separator, *rows])


def build_report(leave_one_year: pd.DataFrame, slippage_stress: pd.DataFrame, start_date: pd.DataFrame) -> str:
    lines = [
        "# AI Product Pool Formal Robustness",
        "",
        "## Leave One Year Out",
        "",
        to_markdown_table(leave_one_year),
        "",
        "## Slippage Stress",
        "",
        to_markdown_table(slippage_stress),
        "",
        "## Start Date Sensitivity",
        "",
        to_markdown_table(start_date),
    ]
    return "\n".join(lines)


def main() -> None:
    baseline = load_daily(BASELINE_DAILY_PATH, "baseline")
    ai = load_daily(AI_DAILY_PATH, "ai_top8")
    leave_one_year = build_leave_one_year(baseline, ai)
    slippage_stress = build_slippage_stress(baseline, ai)
    start_date = build_start_date_sensitivity(baseline, ai)

    leave_one_year.to_csv(LEAVE_ONE_YEAR_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    slippage_stress.to_csv(SLIPPAGE_STRESS_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    start_date.to_csv(START_DATE_OUTPUT_PATH, index=False, encoding="utf-8-sig")

    payload = {
        "model_tag": MODEL_TAG,
        "baseline_prefix": BASELINE_PREFIX,
        "ai_prefix": AI_PREFIX,
        "post_signal_start": POST_SIGNAL_START.date().isoformat(),
        "slippage_multipliers": list(SLIPPAGE_MULTIPLIERS),
        "start_dates": [date.date().isoformat() for date in START_DATES],
        "leave_one_year": leave_one_year.to_dict(orient="records"),
        "slippage_stress": slippage_stress.to_dict(orient="records"),
        "start_date_sensitivity": start_date.to_dict(orient="records"),
        "artifacts": {
            "leave_one_year_csv": str(LEAVE_ONE_YEAR_OUTPUT_PATH),
            "slippage_stress_csv": str(SLIPPAGE_STRESS_OUTPUT_PATH),
            "start_date_csv": str(START_DATE_OUTPUT_PATH),
            "summary_json": str(SUMMARY_JSON_OUTPUT_PATH),
            "report_md": str(REPORT_OUTPUT_PATH),
        },
        "judgement": (
            "A fixed AI Top8 product pool is useful only if it remains better after leave-one-year, "
            "slippage stress, and start-date sensitivity checks."
        ),
    }
    SUMMARY_JSON_OUTPUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_OUTPUT_PATH.write_text(build_report(leave_one_year, slippage_stress, start_date), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
