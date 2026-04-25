from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from qmt_universe import END_DT, START_DT
from run_qmt_roll_backtest import build_summary_row, run_backtest
from run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest import (
    BASE_RISK_RATIO,
    CORR20_06_08_FLOOR35_OVERRIDES,
)


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

EXPERIMENT_TAG: str = "qmt_roll_selection_long015_volref30_corr_ai_product_pool_formal"
SUMMARY_CSV_PATH: Path = OUTPUT_DIR / f"{EXPERIMENT_TAG}_summary.csv"
SUMMARY_JSON_PATH: Path = OUTPUT_DIR / f"{EXPERIMENT_TAG}_summary.json"
ELIGIBILITY_PATH: Path = (
    OUTPUT_DIR / "qmt_roll_ai_product_pool_shadow_portfolio_eligibility_ai_product_pool_shadow_v1.csv"
)


EXPERIMENTS: tuple[dict[str, Any], ...] = (
    {
        "experiment_name": "ai_top8_product_pool",
        "file_prefix": "qmt_roll_selection_long015_volref30_corr_ai_top8_product_pool_formal",
        "chart_title": "QMT Roll VolRef30 Corr Floor35 AI Top8 Product Pool Formal",
        "strategy_overrides": {
            **CORR20_06_08_FLOOR35_OVERRIDES,
            "enable_ai_product_pool_filter": True,
            "ai_product_pool_eligibility_path": str(ELIGIBILITY_PATH),
            "ai_product_pool_strategy": "ai_top8_entry_filter",
        },
    },
)


def run_experiments() -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for experiment in EXPERIMENTS:
        experiment_name = str(experiment["experiment_name"])
        strategy_overrides = dict(experiment["strategy_overrides"])
        print(f"[ai-product-pool-formal] running {experiment_name}")
        _, _, statistics = run_backtest(
            risk_ratio=BASE_RISK_RATIO,
            strategy_overrides=strategy_overrides,
            analysis_start=START_DT,
            analysis_end=END_DT,
            capital=200_000,
            save_artifacts=True,
            include_start_year_sweep=False,
            file_prefix=str(experiment["file_prefix"]),
            chart_title=str(experiment["chart_title"]),
        )
        rows.append(
            build_summary_row(
                statistics,
                analysis_start=START_DT,
                analysis_end=END_DT,
                experiment_name=experiment_name,
                strategy_overrides_json=json.dumps(strategy_overrides, ensure_ascii=False, sort_keys=True),
                total_net_pnl=float(statistics.get("total_net_pnl", 0) or 0),
                total_slippage=float(statistics.get("total_slippage", 0) or 0),
                total_commission=float(statistics.get("total_commission", 0) or 0),
                profit_days=int(statistics.get("profit_days", 0) or 0),
                loss_days=int(statistics.get("loss_days", 0) or 0),
            )
        )
    summary_df = pd.DataFrame(rows)
    summary_df.sort_values("experiment_name", inplace=True)
    summary_df.reset_index(drop=True, inplace=True)
    return summary_df


def build_payload(summary_df: pd.DataFrame) -> dict[str, Any]:
    baseline = {
        "experiment_name": "stage53_floor35_baseline",
        "end_balance": 2_902_355,
        "total_return_pct": 1351.18,
        "max_dd_percent": -36.99,
        "sharpe_ratio": 1.0225,
        "total_slippage": 349_080,
        "total_trade_count": 1158,
    }
    payload: dict[str, Any] = {
        "experiment_tag": EXPERIMENT_TAG,
        "base_risk_ratio": BASE_RISK_RATIO,
        "analysis_start": START_DT.date().isoformat(),
        "analysis_end": END_DT.date().isoformat(),
        "eligibility_path": str(ELIGIBILITY_PATH),
        "baseline_reference": baseline,
        "experiments": summary_df.to_dict(orient="records"),
    }
    if not summary_df.empty:
        row = summary_df.iloc[0]
        payload["comparison_vs_stage53_floor35_baseline"] = {
            "end_balance_diff": float(row["end_balance"] - baseline["end_balance"]),
            "total_return_pct_diff": float(row["total_return_pct"] - baseline["total_return_pct"]),
            "max_dd_percent_diff": float(row["max_dd_percent"] - baseline["max_dd_percent"]),
            "sharpe_ratio_diff": float(row["sharpe_ratio"] - baseline["sharpe_ratio"]),
            "total_slippage_diff": float(row["total_slippage"] - baseline["total_slippage"]),
            "total_trade_count_diff": int(row["total_trade_count"] - baseline["total_trade_count"]),
        }
    return payload


def main() -> None:
    if not ELIGIBILITY_PATH.exists():
        raise FileNotFoundError(f"missing AI product pool eligibility csv: {ELIGIBILITY_PATH}")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    summary_df = run_experiments()
    summary_df.to_csv(SUMMARY_CSV_PATH, index=False, encoding="utf-8-sig")
    SUMMARY_JSON_PATH.write_text(json.dumps(build_payload(summary_df), ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[ai-product-pool-formal] summary csv: {SUMMARY_CSV_PATH}")
    print(f"[ai-product-pool-formal] summary json: {SUMMARY_JSON_PATH}")
    print(summary_df.to_string(index=False))


if __name__ == "__main__":
    main()
