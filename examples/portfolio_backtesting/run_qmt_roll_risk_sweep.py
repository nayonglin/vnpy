from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from run_qmt_alignment_backtest import OUTPUT_DIR
from run_qmt_roll_backtest import run_backtest


RISK_GRID: list[float] = [0.01, 0.015, 0.02, 0.025, 0.03, 0.035, 0.04]
ANNUALIZATION_DAYS: int = 240


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _compute_calmar(annual_return_pct: float, max_dd_percent: float) -> float:
    dd_abs: float = abs(max_dd_percent)
    if dd_abs <= 1e-9:
        return 0.0
    return annual_return_pct / dd_abs


def _compute_drawdown_duration(daily_df: pd.DataFrame) -> int:
    if daily_df.empty or "drawdown" not in daily_df.columns:
        return 0
    in_dd = daily_df["drawdown"] < 0
    max_duration: int = 0
    current: int = 0
    for flag in in_dd.tolist():
        if flag:
            current += 1
            max_duration = max(max_duration, current)
        else:
            current = 0
    return max_duration


def _compute_score(row: dict[str, Any]) -> float:
    annual_return_pct: float = _safe_float(row.get("annual_return_pct"))
    sharpe_ratio: float = _safe_float(row.get("sharpe_ratio"))
    calmar_ratio: float = _safe_float(row.get("calmar_ratio"))
    max_dd_percent: float = _safe_float(row.get("max_dd_percent"))
    dd_duration: float = _safe_float(row.get("max_dd_duration_days"))

    # Risk-adjusted score: reward return+quality, penalize deep/long drawdown.
    return (
        0.40 * calmar_ratio
        + 0.30 * sharpe_ratio
        + 0.20 * (annual_return_pct / 100.0)
        - 0.08 * (abs(max_dd_percent) / 100.0)
        - 0.02 * (dd_duration / ANNUALIZATION_DAYS)
    )


def run_sweep() -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for risk_ratio in RISK_GRID:
        ratio_label: str = f"{risk_ratio:.3f}"
        file_prefix: str = f"qmt_roll_risk_{ratio_label.replace('.', 'p')}"
        print(f"[sweep] running risk_ratio={ratio_label}")
        engine, daily_df, stats = run_backtest(
            risk_ratio=risk_ratio,
            save_artifacts=True,
            file_prefix=file_prefix,
            chart_title=f"QMT Roll Risk Sweep {ratio_label}",
        )
        del engine

        max_dd_duration_days: int = _compute_drawdown_duration(daily_df if daily_df is not None else pd.DataFrame())
        annual_return_pct: float = _safe_float(stats.get("annual_return"))
        max_dd_percent: float = _safe_float(stats.get("max_ddpercent"))
        calmar_ratio: float = _compute_calmar(annual_return_pct, max_dd_percent)

        row: dict[str, Any] = {
            "risk_ratio": risk_ratio,
            "start_date": stats.get("start_date"),
            "end_date": stats.get("end_date"),
            "end_balance": _safe_float(stats.get("end_balance")),
            "total_return_pct": _safe_float(stats.get("total_return")),
            "annual_return_pct": annual_return_pct,
            "max_dd_percent": max_dd_percent,
            "max_drawdown": _safe_float(stats.get("max_drawdown")),
            "max_dd_duration_days": max_dd_duration_days,
            "sharpe_ratio": _safe_float(stats.get("sharpe_ratio")),
            "return_std_pct": _safe_float(stats.get("return_std")),
            "daily_return_pct": _safe_float(stats.get("daily_return")),
            "total_trade_count": int(_safe_float(stats.get("total_trade_count"))),
            "calmar_ratio": calmar_ratio,
            "statistics_json": str((OUTPUT_DIR / f"{file_prefix}_statistics.json").resolve()),
            "dashboard_html": str((OUTPUT_DIR / f"{file_prefix}_professional_dashboard.html").resolve()),
        }
        row["score"] = _compute_score(row)
        rows.append(row)

    result_df: pd.DataFrame = pd.DataFrame(rows)
    result_df.sort_values("score", ascending=False, inplace=True)
    result_df["rank"] = range(1, len(result_df) + 1)
    ordered_columns: list[str] = [
        "rank",
        "risk_ratio",
        "score",
        "annual_return_pct",
        "max_dd_percent",
        "calmar_ratio",
        "sharpe_ratio",
        "end_balance",
        "total_return_pct",
        "max_dd_duration_days",
        "total_trade_count",
        "start_date",
        "end_date",
        "statistics_json",
        "dashboard_html",
    ]
    return result_df[ordered_columns]


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    result_df: pd.DataFrame = run_sweep()
    summary_csv: Path = (OUTPUT_DIR / "qmt_roll_risk_sweep_summary.csv").resolve()
    result_df.to_csv(summary_csv, index=False)
    top3 = result_df.head(3)[
        ["risk_ratio", "score", "annual_return_pct", "max_dd_percent", "calmar_ratio", "sharpe_ratio"]
    ]
    print(f"[sweep] summary csv: {summary_csv}")
    print("[sweep] top3:")
    print(top3.to_string(index=False))


if __name__ == "__main__":
    main()
