from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from qmt_roll_official_stage78_config import OFFICIAL_STAGE78_CAPITAL, build_official_stage78_overrides
from qmt_universe import END_DT, START_DT
from run_qmt_roll_backtest import build_summary_row, run_backtest
from run_qmt_roll_selection_long015_volref30_corr_fu_candidate_robustness_backtest import (
    AI_SATELLITE_POST_SIGNAL_STRATEGY_NAME,
)
from run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest import (
    BASE_RISK_RATIO,
)


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

EXPERIMENT_TAG: str = "qmt_roll_selection_long015_volref30_corr_fu_satellite_post_signal_formal"
SUMMARY_CSV_PATH: Path = OUTPUT_DIR / f"{EXPERIMENT_TAG}_summary.csv"
SUMMARY_JSON_PATH: Path = OUTPUT_DIR / f"{EXPERIMENT_TAG}_summary.json"
SLIPPAGE_STRESS_CSV_PATH: Path = OUTPUT_DIR / f"{EXPERIMENT_TAG}_slippage_stress.csv"

SLIPPAGE_MULTIPLIERS: tuple[float, ...] = (1.0, 1.5, 2.0, 3.0, 5.0)


def calculate_metrics_from_net_pnl(
    net_pnl: np.ndarray,
    *,
    initial_capital: float = OFFICIAL_STAGE78_CAPITAL,
) -> dict[str, float]:
    if len(net_pnl) == 0:
        return {
            "end_balance": 0.0,
            "total_return_pct": 0.0,
            "max_dd_percent": 0.0,
            "sharpe_ratio": 0.0,
        }
    equity = initial_capital + np.cumsum(net_pnl.astype(float))
    prev_equity = np.concatenate([[initial_capital], equity[:-1]])
    returns = np.divide(net_pnl, prev_equity, out=np.zeros_like(net_pnl, dtype=float), where=prev_equity != 0)
    high_water = np.maximum.accumulate(equity)
    drawdown_pct = np.divide(equity - high_water, high_water, out=np.zeros_like(equity), where=high_water != 0) * 100.0
    return_std = float(np.std(returns, ddof=1)) if len(returns) > 1 else 0.0
    sharpe_ratio = float(np.mean(returns) / return_std * np.sqrt(240)) if return_std > 0 else 0.0
    return {
        "end_balance": float(equity[-1]),
        "total_return_pct": float((equity[-1] / initial_capital - 1.0) * 100.0),
        "max_dd_percent": float(drawdown_pct.min()),
        "sharpe_ratio": sharpe_ratio,
    }


def build_slippage_stress(analysis_df: pd.DataFrame | None) -> pd.DataFrame:
    if analysis_df is None or analysis_df.empty:
        return pd.DataFrame()
    frame = analysis_df.reset_index().rename(columns={"index": "date"}).copy()
    base_net_pnl = frame["net_pnl"].to_numpy(dtype=float)
    slippage = frame["slippage"].to_numpy(dtype=float)
    trade_count = int(frame["trade_count"].sum())
    rows: list[dict[str, Any]] = []
    for multiplier in SLIPPAGE_MULTIPLIERS:
        stressed_net_pnl = base_net_pnl - (multiplier - 1.0) * slippage
        metrics = calculate_metrics_from_net_pnl(stressed_net_pnl)
        rows.append(
            {
                "experiment_name": "ai_top8_plus_fu_satellite_post_signal",
                "slippage_multiplier": multiplier,
                "extra_slippage": float(((multiplier - 1.0) * slippage).sum()),
                "total_slippage": float((multiplier * slippage).sum()),
                "total_trade_count": trade_count,
                **metrics,
            }
        )
    return pd.DataFrame(rows)


def run_formal() -> tuple[pd.DataFrame, pd.DataFrame]:
    strategy_overrides: dict[str, Any] = build_official_stage78_overrides()
    print("[fu-satellite-post-signal-formal] running formal backtest")
    _, analysis_df, statistics = run_backtest(
        risk_ratio=BASE_RISK_RATIO,
        strategy_overrides=strategy_overrides,
        analysis_start=START_DT,
        analysis_end=END_DT,
        capital=OFFICIAL_STAGE78_CAPITAL,
        save_artifacts=True,
        include_start_year_sweep=False,
        file_prefix=EXPERIMENT_TAG,
        chart_title="QMT Roll VolRef30 Corr Floor35 AI Top8 + Fu Satellite Post Signal Formal",
    )
    row = build_summary_row(
        statistics,
        analysis_start=START_DT,
        analysis_end=END_DT,
        experiment_name="ai_top8_plus_fu_satellite_post_signal",
        universe_path=str(strategy_overrides.get("product_universe_csv_path", "")),
        ai_product_pool_eligibility_path=str(strategy_overrides.get("ai_product_pool_eligibility_path", "")),
        ai_product_pool_strategy=AI_SATELLITE_POST_SIGNAL_STRATEGY_NAME,
        sizing_equity_cap=float(strategy_overrides.get("sizing_equity_cap", 0.0) or 0.0),
        strategy_overrides_json=json.dumps(strategy_overrides, ensure_ascii=False, sort_keys=True),
        total_net_pnl=float(statistics.get("total_net_pnl", 0) or 0),
        total_slippage=float(statistics.get("total_slippage", 0) or 0),
        total_commission=float(statistics.get("total_commission", 0) or 0),
        profit_days=int(statistics.get("profit_days", 0) or 0),
        loss_days=int(statistics.get("loss_days", 0) or 0),
    )
    return pd.DataFrame([row]), build_slippage_stress(analysis_df)


def build_payload(summary: pd.DataFrame, slippage_stress: pd.DataFrame) -> dict[str, Any]:
    references = {
        "stage68_71_ai_top8_product_pool": {
            "end_balance": 3_894_190,
            "total_return_pct": 1847.095,
            "max_dd_percent": -36.990703,
            "sharpe_ratio": 1.208030,
            "total_slippage": 257_880,
            "total_trade_count": 720,
        },
        "stage53_baseline_floor35": {
            "end_balance": 2_902_355,
            "total_return_pct": 1351.1775,
            "max_dd_percent": -36.990703,
            "sharpe_ratio": 1.022532,
            "total_slippage": 349_080,
            "total_trade_count": 1158,
        },
    }
    payload: dict[str, Any] = {
        "experiment_tag": EXPERIMENT_TAG,
        "base_risk_ratio": BASE_RISK_RATIO,
        "analysis_start": START_DT.date().isoformat(),
        "analysis_end": END_DT.date().isoformat(),
        "experiments": summary.to_dict(orient="records"),
        "slippage_stress": slippage_stress.to_dict(orient="records"),
        "references": references,
        "artifacts": {
            "summary_csv": str(SUMMARY_CSV_PATH),
            "summary_json": str(SUMMARY_JSON_PATH),
            "slippage_stress_csv": str(SLIPPAGE_STRESS_CSV_PATH),
            "file_prefix": EXPERIMENT_TAG,
        },
    }
    if not summary.empty:
        row = summary.iloc[0]
        for name, reference in references.items():
            payload[f"comparison_vs_{name}"] = {
                "end_balance_diff": float(row["end_balance"] - reference["end_balance"]),
                "total_return_pct_diff": float(row["total_return_pct"] - reference["total_return_pct"]),
                "max_dd_percent_diff": float(row["max_dd_percent"] - reference["max_dd_percent"]),
                "sharpe_ratio_diff": float(row["sharpe_ratio"] - reference["sharpe_ratio"]),
                "total_slippage_diff": float(row["total_slippage"] - reference["total_slippage"]),
                "total_trade_count_diff": int(row["total_trade_count"] - reference["total_trade_count"]),
            }
    return payload


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    summary, slippage_stress = run_formal()
    summary.to_csv(SUMMARY_CSV_PATH, index=False, encoding="utf-8-sig")
    slippage_stress.to_csv(SLIPPAGE_STRESS_CSV_PATH, index=False, encoding="utf-8-sig")
    SUMMARY_JSON_PATH.write_text(
        json.dumps(build_payload(summary, slippage_stress), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[fu-satellite-post-signal-formal] summary csv: {SUMMARY_CSV_PATH}")
    print(f"[fu-satellite-post-signal-formal] summary json: {SUMMARY_JSON_PATH}")
    print(f"[fu-satellite-post-signal-formal] slippage stress csv: {SLIPPAGE_STRESS_CSV_PATH}")
    print(summary.to_string(index=False))
    print(slippage_stress.to_string(index=False))


if __name__ == "__main__":
    main()
