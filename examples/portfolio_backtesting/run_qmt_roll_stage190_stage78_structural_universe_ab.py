from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from qmt_roll_official_stage78_config import (
    OFFICIAL_STAGE78_CAPITAL,
    OFFICIAL_STAGE78_VERSION,
    build_official_stage78_overrides,
)
from qmt_universe import END_DT, START_DT
from run_qmt_roll_backtest import build_summary_row, run_backtest
from run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest import BASE_RISK_RATIO


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

EXPERIMENT_TAG: str = "qmt_roll_stage190_stage78_structural_universe_ab"
SUMMARY_CSV_PATH: Path = OUTPUT_DIR / f"{EXPERIMENT_TAG}_summary.csv"
SUMMARY_JSON_PATH: Path = OUTPUT_DIR / f"{EXPERIMENT_TAG}_summary.json"
REPORT_PATH: Path = OUTPUT_DIR / f"{EXPERIMENT_TAG}_report.md"

STRUCTURAL_UNIVERSE_PATH: Path = (
    OUTPUT_DIR / "qmt_roll_full_market_structural_prefilter_eligible_full_market_structural_prefilter_v1.csv"
)
STRUCTURAL_AI_ELIGIBILITY_PATH: Path = (
    OUTPUT_DIR / "qmt_roll_full_market_structural_prefilter_ai_eligibility_full_market_structural_prefilter_v1.csv"
)


def _stage78_with_overrides(extra: dict[str, Any]) -> dict[str, Any]:
    overrides = build_official_stage78_overrides()
    overrides.update(extra)
    return overrides


def _experiment_specs() -> tuple[dict[str, Any], ...]:
    return (
        {
            "experiment_name": "A_official_stage78",
            "role": "baseline",
            "file_prefix": "qmt_roll_stage190_A_official_stage78",
            "chart_title": "Stage190 A Official Stage78",
            "strategy_overrides": build_official_stage78_overrides(),
        },
        {
            "experiment_name": "B_stage78_structural_all_no_ai",
            "role": "candidate_base_universe",
            "file_prefix": "qmt_roll_stage190_B_stage78_structural_all_no_ai",
            "chart_title": "Stage190 B Stage78 Structural All No AI",
            "strategy_overrides": _stage78_with_overrides(
                {
                    "product_universe_csv_path": str(STRUCTURAL_UNIVERSE_PATH),
                    "enable_ai_product_pool_filter": False,
                }
            ),
        },
        {
            "experiment_name": "C_stage78_structural_ai_top8",
            "role": "promotion_candidate",
            "file_prefix": "qmt_roll_stage190_C_stage78_structural_ai_top8",
            "chart_title": "Stage190 C Stage78 Structural AI Top8",
            "strategy_overrides": _stage78_with_overrides(
                {
                    "product_universe_csv_path": str(STRUCTURAL_UNIVERSE_PATH),
                    "enable_ai_product_pool_filter": True,
                    "ai_product_pool_eligibility_path": str(STRUCTURAL_AI_ELIGIBILITY_PATH),
                    "ai_product_pool_strategy": "ai_structural_top8_entry_filter",
                }
            ),
        },
        {
            "experiment_name": "D_stage78_structural_simple_top8",
            "role": "transparent_candidate",
            "file_prefix": "qmt_roll_stage190_D_stage78_structural_simple_top8",
            "chart_title": "Stage190 D Stage78 Structural Simple Top8",
            "strategy_overrides": _stage78_with_overrides(
                {
                    "product_universe_csv_path": str(STRUCTURAL_UNIVERSE_PATH),
                    "enable_ai_product_pool_filter": True,
                    "ai_product_pool_eligibility_path": str(STRUCTURAL_AI_ELIGIBILITY_PATH),
                    "ai_product_pool_strategy": "simple_structural_top8_entry_filter",
                }
            ),
        },
    )


def run_experiments() -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for spec in _experiment_specs():
        print(f"[stage190] running {spec['experiment_name']}")
        _, _, statistics = run_backtest(
            risk_ratio=BASE_RISK_RATIO,
            strategy_overrides=dict(spec["strategy_overrides"]),
            analysis_start=START_DT,
            analysis_end=END_DT,
            capital=OFFICIAL_STAGE78_CAPITAL,
            save_artifacts=True,
            include_start_year_sweep=False,
            file_prefix=str(spec["file_prefix"]),
            chart_title=str(spec["chart_title"]),
        )
        rows.append(
            build_summary_row(
                statistics,
                analysis_start=START_DT,
                analysis_end=END_DT,
                experiment_name=str(spec["experiment_name"]),
                role=str(spec["role"]),
                official_version=OFFICIAL_STAGE78_VERSION,
                universe_path=str(spec["strategy_overrides"].get("product_universe_csv_path", "")),
                ai_eligibility_path=str(spec["strategy_overrides"].get("ai_product_pool_eligibility_path", ""))
                if bool(spec["strategy_overrides"].get("enable_ai_product_pool_filter", False))
                else "",
                ai_strategy=str(spec["strategy_overrides"].get("ai_product_pool_strategy", ""))
                if bool(spec["strategy_overrides"].get("enable_ai_product_pool_filter", False))
                else "",
                strategy_overrides_json=json.dumps(
                    spec["strategy_overrides"],
                    ensure_ascii=False,
                    sort_keys=True,
                ),
                total_net_pnl=float(statistics.get("total_net_pnl", 0) or 0),
                total_slippage=float(statistics.get("total_slippage", 0) or 0),
                total_commission=float(statistics.get("total_commission", 0) or 0),
                profit_days=int(statistics.get("profit_days", 0) or 0),
                loss_days=int(statistics.get("loss_days", 0) or 0),
            )
        )
    return pd.DataFrame(rows)


def _safe_float(value: Any) -> float:
    try:
        if pd.isna(value):
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def build_payload(summary: pd.DataFrame) -> dict[str, Any]:
    baseline_row = summary[summary["experiment_name"] == "A_official_stage78"].iloc[0].to_dict()
    comparisons: list[dict[str, Any]] = []
    for row in summary.to_dict(orient="records"):
        comparisons.append(
            {
                "experiment_name": row["experiment_name"],
                "role": row["role"],
                "end_balance_diff_vs_A": _safe_float(row["end_balance"]) - _safe_float(baseline_row["end_balance"]),
                "total_return_pct_diff_vs_A": _safe_float(row["total_return_pct"])
                - _safe_float(baseline_row["total_return_pct"]),
                "max_dd_percent_diff_vs_A": _safe_float(row["max_dd_percent"])
                - _safe_float(baseline_row["max_dd_percent"]),
                "sharpe_ratio_diff_vs_A": _safe_float(row["sharpe_ratio"])
                - _safe_float(baseline_row["sharpe_ratio"]),
                "total_slippage_diff_vs_A": _safe_float(row["total_slippage"])
                - _safe_float(baseline_row["total_slippage"]),
                "total_trade_count_diff_vs_A": int(row["total_trade_count"] - baseline_row["total_trade_count"]),
            }
        )
    return {
        "experiment_tag": EXPERIMENT_TAG,
        "official_version": OFFICIAL_STAGE78_VERSION,
        "hypothesis": (
            "A structurally screened full-market base universe may reduce manual universe bias while keeping "
            "Stage78's defensive mechanics intact."
        ),
        "analysis_start": START_DT.date().isoformat(),
        "analysis_end": END_DT.date().isoformat(),
        "capital": OFFICIAL_STAGE78_CAPITAL,
        "arms": [
            {
                "arm": "A",
                "name": "official_stage78",
                "meaning": "Frozen official Stage78 defensive baseline.",
            },
            {
                "arm": "B",
                "name": "stage78_structural_all_no_ai",
                "meaning": "Stage78 mechanics on structural base universe without monthly AI entry filter.",
            },
            {
                "arm": "C",
                "name": "stage78_structural_ai_top8",
                "meaning": "Promotion candidate: Stage78 mechanics plus structural base universe and AI top8 entry filter.",
            },
            {
                "arm": "D",
                "name": "stage78_structural_simple_top8",
                "meaning": "Transparent alternative using simple score top8 inside the structural universe.",
            },
        ],
        "structural_universe_path": str(STRUCTURAL_UNIVERSE_PATH),
        "structural_ai_eligibility_path": str(STRUCTURAL_AI_ELIGIBILITY_PATH),
        "experiments": summary.to_dict(orient="records"),
        "comparison_vs_A": comparisons,
        "pass_fail_rule": (
            "C can advance only if it improves or clearly matches A on full-cycle return/Sharpe without materially "
            "worsening drawdown, slippage, or trade count; otherwise keep as research-only."
        ),
    }


def _markdown_table(df: pd.DataFrame) -> str:
    if df.empty:
        return "_empty_"
    view = df.copy()
    for column in view.columns:
        if pd.api.types.is_float_dtype(view[column]):
            view[column] = view[column].map(lambda value: f"{value:.4f}")
    return "\n".join(
        [
            "| " + " | ".join(view.columns) + " |",
            "| " + " | ".join(["---"] * len(view.columns)) + " |",
            *["| " + " | ".join(map(str, row)) + " |" for row in view.to_numpy()],
        ]
    )


def build_report(summary: pd.DataFrame, payload: dict[str, Any]) -> str:
    columns = [
        "experiment_name",
        "role",
        "end_balance",
        "total_return_pct",
        "max_dd_percent",
        "sharpe_ratio",
        "total_slippage",
        "total_trade_count",
        "win_ratio_pct",
    ]
    compare = pd.DataFrame(payload["comparison_vs_A"])
    compare_columns = [
        "experiment_name",
        "end_balance_diff_vs_A",
        "total_return_pct_diff_vs_A",
        "max_dd_percent_diff_vs_A",
        "sharpe_ratio_diff_vs_A",
        "total_slippage_diff_vs_A",
        "total_trade_count_diff_vs_A",
    ]
    return "\n".join(
        [
            "# Stage190 Stage78 Structural Universe A/B",
            "",
            "## Hypothesis",
            "",
            payload["hypothesis"],
            "",
            "## Arms",
            "",
            "- A: official Stage78 defensive baseline.",
            "- B: Stage78 mechanics + structural base universe, no monthly AI filter.",
            "- C: Stage78 mechanics + structural base universe + AI top8.",
            "- D: Stage78 mechanics + structural base universe + simple score top8.",
            "",
            "## Results",
            "",
            _markdown_table(summary[columns]),
            "",
            "## Comparison Vs A",
            "",
            _markdown_table(compare[compare_columns]),
            "",
            "## Pass/Fail Rule",
            "",
            payload["pass_fail_rule"],
        ]
    )


def main() -> None:
    if not STRUCTURAL_UNIVERSE_PATH.exists():
        raise FileNotFoundError(f"missing structural universe csv: {STRUCTURAL_UNIVERSE_PATH}")
    if not STRUCTURAL_AI_ELIGIBILITY_PATH.exists():
        raise FileNotFoundError(f"missing structural AI eligibility csv: {STRUCTURAL_AI_ELIGIBILITY_PATH}")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    summary = run_experiments()
    summary.to_csv(SUMMARY_CSV_PATH, index=False, encoding="utf-8-sig")
    payload = build_payload(summary)
    SUMMARY_JSON_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_PATH.write_text(build_report(summary, payload), encoding="utf-8")
    print(f"[stage190] summary csv: {SUMMARY_CSV_PATH}")
    print(f"[stage190] summary json: {SUMMARY_JSON_PATH}")
    print(f"[stage190] report: {REPORT_PATH}")
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
