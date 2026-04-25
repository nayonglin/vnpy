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

EXPERIMENT_TAG: str = "qmt_roll_selection_long015_volref30_corr_new_product_ablation"
SUMMARY_CSV_PATH: Path = OUTPUT_DIR / f"{EXPERIMENT_TAG}_summary.csv"
SUMMARY_JSON_PATH: Path = OUTPUT_DIR / f"{EXPERIMENT_TAG}_summary.json"
UNIVERSE_DIR: Path = OUTPUT_DIR / f"{EXPERIMENT_TAG}_universes"

STRUCTURAL_UNIVERSE_PATH: Path = (
    OUTPUT_DIR / "qmt_roll_full_market_structural_prefilter_eligible_full_market_structural_prefilter_v1.csv"
)

NEW_PRODUCTS: tuple[str, ...] = ("UR.CZCE", "eb.DCE", "pg.DCE", "fu.SHFE", "sn.SHFE")


EXPERIMENT_PRODUCT_SETS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("static18_plus_UR", ("UR.CZCE",)),
    ("static18_plus_eb", ("eb.DCE",)),
    ("static18_plus_pg", ("pg.DCE",)),
    ("static18_plus_fu", ("fu.SHFE",)),
    ("static18_plus_sn", ("sn.SHFE",)),
    ("static18_plus_fu_sn", ("fu.SHFE", "sn.SHFE")),
    ("static18_plus_fu_sn_eb", ("fu.SHFE", "sn.SHFE", "eb.DCE")),
    ("structural23_without_UR_pg", ("eb.DCE", "fu.SHFE", "sn.SHFE")),
)


def _load_structural_universe() -> pd.DataFrame:
    if not STRUCTURAL_UNIVERSE_PATH.exists():
        raise FileNotFoundError(STRUCTURAL_UNIVERSE_PATH)
    df = pd.read_csv(STRUCTURAL_UNIVERSE_PATH)
    df["product_vt_symbol"] = df["product_vt_symbol"].astype(str)
    df["is_static_strategy_product"] = pd.to_numeric(df["is_static_strategy_product"], errors="coerce").fillna(0).astype(int)
    return df


def _write_universe_csv(
    *,
    structural_universe: pd.DataFrame,
    experiment_name: str,
    new_products: tuple[str, ...],
) -> Path:
    static_products = set(
        structural_universe.loc[structural_universe["is_static_strategy_product"] == 1, "product_vt_symbol"].astype(str)
    )
    selected = static_products | set(new_products)
    missing = sorted(selected - set(structural_universe["product_vt_symbol"].astype(str)))
    if missing:
        raise ValueError(f"{experiment_name} has products missing from structural universe: {missing}")

    universe = structural_universe[structural_universe["product_vt_symbol"].isin(selected)].copy()
    universe.sort_values(["exchange", "product_vt_symbol"], inplace=True)
    UNIVERSE_DIR.mkdir(parents=True, exist_ok=True)
    path = UNIVERSE_DIR / f"{EXPERIMENT_TAG}_{experiment_name}_universe.csv"
    universe.to_csv(path, index=False, encoding="utf-8-sig")
    return path


def run_experiments() -> pd.DataFrame:
    structural_universe = _load_structural_universe()
    rows: list[dict[str, Any]] = []
    for experiment_name, new_products in EXPERIMENT_PRODUCT_SETS:
        universe_path = _write_universe_csv(
            structural_universe=structural_universe,
            experiment_name=experiment_name,
            new_products=new_products,
        )
        strategy_overrides = {
            **CORR20_06_08_FLOOR35_OVERRIDES,
            "product_universe_csv_path": str(universe_path),
        }
        print(f"[new-product-ablation] running {experiment_name}: {', '.join(new_products)}")
        _, _, statistics = run_backtest(
            risk_ratio=BASE_RISK_RATIO,
            strategy_overrides=strategy_overrides,
            analysis_start=START_DT,
            analysis_end=END_DT,
            capital=200_000,
            save_artifacts=True,
            include_start_year_sweep=False,
            file_prefix=f"{EXPERIMENT_TAG}_{experiment_name}_formal",
            chart_title=f"QMT Roll VolRef30 Corr Floor35 New Product Ablation {experiment_name}",
        )
        rows.append(
            build_summary_row(
                statistics,
                analysis_start=START_DT,
                analysis_end=END_DT,
                experiment_name=experiment_name,
                added_new_products=",".join(new_products),
                added_new_product_count=len(new_products),
                universe_path=str(universe_path),
                strategy_overrides_json=json.dumps(strategy_overrides, ensure_ascii=False, sort_keys=True),
                total_net_pnl=float(statistics.get("total_net_pnl", 0) or 0),
                total_slippage=float(statistics.get("total_slippage", 0) or 0),
                total_commission=float(statistics.get("total_commission", 0) or 0),
                profit_days=int(statistics.get("profit_days", 0) or 0),
                loss_days=int(statistics.get("loss_days", 0) or 0),
            )
        )
    summary_df = pd.DataFrame(rows)
    summary_df.sort_values(["added_new_product_count", "experiment_name"], inplace=True)
    summary_df.reset_index(drop=True, inplace=True)
    return summary_df


def build_payload(summary_df: pd.DataFrame) -> dict[str, Any]:
    references = {
        "stage53_18_product_floor35": {
            "end_balance": 2_902_355,
            "total_return_pct": 1351.18,
            "max_dd_percent": -36.99,
            "sharpe_ratio": 1.0225,
            "total_slippage": 349_080,
            "total_trade_count": 1158,
        },
        "stage68_18_product_ai_top8": {
            "end_balance": 3_894_190,
            "total_return_pct": 1847.09,
            "max_dd_percent": -36.99,
            "sharpe_ratio": 1.2080,
            "total_slippage": 257_880,
            "total_trade_count": 720,
        },
        "stage73_structural_prefilter_all": {
            "end_balance": 2_239_105,
            "total_return_pct": 1019.5525,
            "max_dd_percent": -45.489211,
            "sharpe_ratio": 0.702855,
            "total_slippage": 316_180,
            "total_trade_count": 1436,
        },
    }
    payload: dict[str, Any] = {
        "experiment_tag": EXPERIMENT_TAG,
        "base_risk_ratio": BASE_RISK_RATIO,
        "analysis_start": START_DT.date().isoformat(),
        "analysis_end": END_DT.date().isoformat(),
        "structural_universe_path": str(STRUCTURAL_UNIVERSE_PATH),
        "new_products": list(NEW_PRODUCTS),
        "experiments": summary_df.to_dict(orient="records"),
        "references": references,
        "artifacts": {
            "summary_csv": str(SUMMARY_CSV_PATH),
            "summary_json": str(SUMMARY_JSON_PATH),
            "universe_dir": str(UNIVERSE_DIR),
        },
        "design_boundary": (
            "Diagnostic ablation only. Product admission is not decided by a single full-period result; "
            "candidates must survive multi-period and robustness checks before becoming official."
        ),
    }
    for reference_name, reference in references.items():
        payload[f"comparison_vs_{reference_name}"] = []
        for row in summary_df.to_dict(orient="records"):
            payload[f"comparison_vs_{reference_name}"].append(
                {
                    "experiment_name": row["experiment_name"],
                    "end_balance_diff": float(row["end_balance"] - reference["end_balance"]),
                    "total_return_pct_diff": float(row["total_return_pct"] - reference["total_return_pct"]),
                    "max_dd_percent_diff": float(row["max_dd_percent"] - reference["max_dd_percent"]),
                    "sharpe_ratio_diff": float(row["sharpe_ratio"] - reference["sharpe_ratio"]),
                    "total_slippage_diff": float(row["total_slippage"] - reference["total_slippage"]),
                    "total_trade_count_diff": int(row["total_trade_count"] - reference["total_trade_count"]),
                }
            )
    return payload


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    summary_df = run_experiments()
    summary_df.to_csv(SUMMARY_CSV_PATH, index=False, encoding="utf-8-sig")
    SUMMARY_JSON_PATH.write_text(json.dumps(build_payload(summary_df), ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[new-product-ablation] summary csv: {SUMMARY_CSV_PATH}")
    print(f"[new-product-ablation] summary json: {SUMMARY_JSON_PATH}")
    print(summary_df.to_string(index=False))


if __name__ == "__main__":
    main()
