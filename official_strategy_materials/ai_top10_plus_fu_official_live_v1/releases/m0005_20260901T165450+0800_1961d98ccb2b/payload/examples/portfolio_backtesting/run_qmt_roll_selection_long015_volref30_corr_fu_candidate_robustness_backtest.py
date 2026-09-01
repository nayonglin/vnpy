from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from qmt_universe import END_DT, START_DT
from run_qmt_roll_backtest import START_YEAR_WINDOWS, build_summary_row, run_backtest
from run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest import (
    BASE_RISK_RATIO,
    CORR20_06_08_FLOOR35_OVERRIDES,
)


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

EXPERIMENT_TAG: str = "qmt_roll_selection_long015_volref30_corr_fu_candidate_robustness"
UNIVERSE_PATH: Path = OUTPUT_DIR / f"{EXPERIMENT_TAG}_static18_plus_fu_universe.csv"
AI_SATELLITE_ELIGIBILITY_PATH: Path = (
    OUTPUT_DIR / f"{EXPERIMENT_TAG}_ai_top8_plus_fu_satellite_eligibility.csv"
)
AI_SATELLITE_POST_SIGNAL_ELIGIBILITY_PATH: Path = (
    OUTPUT_DIR / f"{EXPERIMENT_TAG}_ai_top8_plus_fu_satellite_post_signal_eligibility.csv"
)

STRUCTURAL_UNIVERSE_PATH: Path = (
    OUTPUT_DIR / "qmt_roll_full_market_structural_prefilter_eligible_full_market_structural_prefilter_v1.csv"
)
AI_TOP8_ELIGIBILITY_PATH: Path = (
    OUTPUT_DIR / "qmt_roll_ai_product_pool_shadow_portfolio_eligibility_ai_product_pool_shadow_v1.csv"
)
AI_MULTICYCLE_REFERENCE_PATH: Path = (
    OUTPUT_DIR / "qmt_roll_ai_product_pool_multicycle_backtest_summary_ai_top8_multicycle_v1.csv"
)

CYCLE_SUMMARY_PATH: Path = OUTPUT_DIR / f"{EXPERIMENT_TAG}_cycle_summary.csv"
START_YEAR_SUMMARY_PATH: Path = OUTPUT_DIR / f"{EXPERIMENT_TAG}_start_year_summary.csv"
SLIPPAGE_STRESS_PATH: Path = OUTPUT_DIR / f"{EXPERIMENT_TAG}_slippage_stress.csv"
COMBINED_CYCLE_SUMMARY_PATH: Path = OUTPUT_DIR / f"{EXPERIMENT_TAG}_combined_cycle_summary.csv"
SUMMARY_JSON_PATH: Path = OUTPUT_DIR / f"{EXPERIMENT_TAG}_summary.json"
REPORT_PATH: Path = OUTPUT_DIR / f"{EXPERIMENT_TAG}_report.md"

CAPITAL: float = 200_000.0
FU_PRODUCT: str = "fu.SHFE"
AI_SATELLITE_STRATEGY_NAME: str = "ai_top8_plus_fu_satellite_entry_filter"
AI_SATELLITE_POST_SIGNAL_STRATEGY_NAME: str = "ai_top8_plus_fu_satellite_post_signal_entry_filter"
SLIPPAGE_MULTIPLIERS: tuple[float, ...] = (1.0, 1.5, 2.0, 3.0, 5.0)

CYCLE_WINDOWS: tuple[dict[str, Any], ...] = (
    {
        "window_name": "full_2020_2026",
        "display_label": "full",
        "analysis_start": START_DT,
        "analysis_end": END_DT,
    },
    {
        "window_name": "pre_ai_2020_2021",
        "display_label": "pre_ai",
        "analysis_start": datetime(2020, 1, 1),
        "analysis_end": datetime(2021, 12, 31),
    },
    {
        "window_name": "post_signal_2022_2026",
        "display_label": "post_signal",
        "analysis_start": datetime(2022, 2, 7),
        "analysis_end": END_DT,
    },
    {
        "window_name": "early_ai_2022_2023",
        "display_label": "early_ai",
        "analysis_start": datetime(2022, 2, 7),
        "analysis_end": datetime(2023, 12, 31),
    },
    {
        "window_name": "trend_rich_2024_2025",
        "display_label": "trend_rich",
        "analysis_start": datetime(2024, 1, 1),
        "analysis_end": datetime(2025, 12, 31),
    },
    {
        "window_name": "latest_2026",
        "display_label": "latest",
        "analysis_start": datetime(2026, 1, 1),
        "analysis_end": END_DT,
    },
)


def _safe_float(value: Any) -> float:
    try:
        if pd.isna(value):
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _format_float(value: Any) -> str:
    number = _safe_float(value)
    return f"{number:.4f}"


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


def build_static18_plus_fu_universe() -> Path:
    if not STRUCTURAL_UNIVERSE_PATH.exists():
        raise FileNotFoundError(STRUCTURAL_UNIVERSE_PATH)
    df = pd.read_csv(STRUCTURAL_UNIVERSE_PATH)
    df["product_vt_symbol"] = df["product_vt_symbol"].astype(str)
    df["is_static_strategy_product"] = pd.to_numeric(df["is_static_strategy_product"], errors="coerce").fillna(0).astype(int)
    selected = (df["is_static_strategy_product"] == 1) | (df["product_vt_symbol"] == FU_PRODUCT)
    universe = df[selected].copy()
    if FU_PRODUCT not in set(universe["product_vt_symbol"].astype(str)):
        raise ValueError(f"{FU_PRODUCT} missing from structural universe")
    universe.sort_values(["exchange", "product_vt_symbol"], inplace=True)
    universe.to_csv(UNIVERSE_PATH, index=False, encoding="utf-8-sig")
    return UNIVERSE_PATH


def load_static_products() -> list[str]:
    if not STRUCTURAL_UNIVERSE_PATH.exists():
        raise FileNotFoundError(STRUCTURAL_UNIVERSE_PATH)
    df = pd.read_csv(STRUCTURAL_UNIVERSE_PATH)
    df["product_vt_symbol"] = df["product_vt_symbol"].astype(str)
    df["is_static_strategy_product"] = pd.to_numeric(df["is_static_strategy_product"], errors="coerce").fillna(0).astype(int)
    return sorted(df.loc[df["is_static_strategy_product"] == 1, "product_vt_symbol"].astype(str).tolist())


def build_ai_satellite_frame(strategy_name: str) -> pd.DataFrame:
    if not AI_TOP8_ELIGIBILITY_PATH.exists():
        raise FileNotFoundError(AI_TOP8_ELIGIBILITY_PATH)
    df = pd.read_csv(AI_TOP8_ELIGIBILITY_PATH)
    top8 = df[df["strategy"].astype(str) == "ai_top8_entry_filter"].copy()
    if top8.empty:
        raise ValueError("ai_top8_entry_filter eligibility is empty")

    satellite = top8.copy()
    satellite["strategy"] = strategy_name
    satellite["top_n"] = 9

    fu_rows: list[dict[str, Any]] = []
    for eval_date, group in satellite.groupby("eval_date", sort=True):
        if FU_PRODUCT in set(group["product_vt_symbol"].astype(str)):
            continue
        min_score = pd.to_numeric(group["score"], errors="coerce").min()
        fu_rows.append(
            {
                "strategy": strategy_name,
                "score_type": "ai_top8_plus_fixed_fu_satellite",
                "eval_date": eval_date,
                "product_vt_symbol": FU_PRODUCT,
                "score": float(min_score) - 1e-6 if pd.notna(min_score) else 0.0,
                "score_rank": 9,
                "top_n": 9,
            }
        )

    if fu_rows:
        satellite = pd.concat([satellite, pd.DataFrame(fu_rows)], ignore_index=True)
    satellite.sort_values(["eval_date", "score_rank", "product_vt_symbol"], inplace=True)
    return satellite


def build_ai_satellite_eligibility() -> Path:
    satellite = build_ai_satellite_frame(AI_SATELLITE_STRATEGY_NAME)
    satellite.to_csv(AI_SATELLITE_ELIGIBILITY_PATH, index=False, encoding="utf-8-sig")
    return AI_SATELLITE_ELIGIBILITY_PATH


def build_ai_satellite_post_signal_eligibility() -> Path:
    satellite = build_ai_satellite_frame(AI_SATELLITE_POST_SIGNAL_STRATEGY_NAME)
    static_products = load_static_products()
    pre_signal_rows = [
        {
            "strategy": AI_SATELLITE_POST_SIGNAL_STRATEGY_NAME,
            "score_type": "static18_pre_ai_boundary",
            "eval_date": "2019-12-31",
            "product_vt_symbol": product,
            "score": 0.0,
            "score_rank": rank,
            "top_n": len(static_products),
        }
        for rank, product in enumerate(static_products, start=1)
    ]
    satellite = pd.concat([pd.DataFrame(pre_signal_rows), satellite], ignore_index=True)
    satellite.sort_values(["eval_date", "score_rank", "product_vt_symbol"], inplace=True)
    satellite.to_csv(AI_SATELLITE_POST_SIGNAL_ELIGIBILITY_PATH, index=False, encoding="utf-8-sig")
    return AI_SATELLITE_POST_SIGNAL_ELIGIBILITY_PATH


def strategy_specs(
    universe_path: Path,
    satellite_path: Path,
    satellite_post_signal_path: Path,
) -> tuple[dict[str, Any], ...]:
    return (
        {
            "strategy_name": "static18_plus_fu",
            "display_name": "Static18 + fu",
            "strategy_overrides": {
                **CORR20_06_08_FLOOR35_OVERRIDES,
                "product_universe_csv_path": str(universe_path),
            },
        },
        {
            "strategy_name": "ai_top8_plus_fu_satellite",
            "display_name": "AI Top8 + fixed fu satellite",
            "strategy_overrides": {
                **CORR20_06_08_FLOOR35_OVERRIDES,
                "product_universe_csv_path": str(universe_path),
                "enable_ai_product_pool_filter": True,
                "ai_product_pool_eligibility_path": str(satellite_path),
                "ai_product_pool_strategy": AI_SATELLITE_STRATEGY_NAME,
            },
        },
        {
            "strategy_name": "ai_top8_plus_fu_satellite_post_signal",
            "display_name": "AI Top8 + fu satellite after AI signal",
            "strategy_overrides": {
                **CORR20_06_08_FLOOR35_OVERRIDES,
                "product_universe_csv_path": str(universe_path),
                "enable_ai_product_pool_filter": True,
                "ai_product_pool_eligibility_path": str(satellite_post_signal_path),
                "ai_product_pool_strategy": AI_SATELLITE_POST_SIGNAL_STRATEGY_NAME,
            },
        },
    )


def run_cycle_backtests(specs: tuple[dict[str, Any], ...]) -> tuple[pd.DataFrame, pd.DataFrame | None]:
    rows: list[dict[str, Any]] = []
    full_static18_plus_fu_daily: pd.DataFrame | None = None

    for window in CYCLE_WINDOWS:
        window_name = str(window["window_name"])
        analysis_start = window["analysis_start"]
        analysis_end = window["analysis_end"]
        for spec in specs:
            strategy_name = str(spec["strategy_name"])
            strategy_overrides = dict(spec["strategy_overrides"])
            print(
                f"[fu-candidate-robustness] cycle {window_name} / {strategy_name}: "
                f"{analysis_start.date()} -> {analysis_end.date()}"
            )
            _, analysis_df, statistics = run_backtest(
                risk_ratio=BASE_RISK_RATIO,
                strategy_overrides=strategy_overrides,
                analysis_start=analysis_start,
                analysis_end=analysis_end,
                capital=CAPITAL,
                save_artifacts=False,
                include_start_year_sweep=False,
                file_prefix=f"{EXPERIMENT_TAG}_{window_name}_{strategy_name}",
                chart_title=f"QMT Roll {window_name} {strategy_name}",
            )
            rows.append(
                build_summary_row(
                    statistics,
                    analysis_start=analysis_start,
                    analysis_end=analysis_end,
                    window_name=window_name,
                    display_label=str(window["display_label"]),
                    strategy_name=strategy_name,
                    display_name=str(spec["display_name"]),
                    strategy_overrides_json=json.dumps(strategy_overrides, ensure_ascii=False, sort_keys=True),
                    total_net_pnl=float(statistics.get("total_net_pnl", 0) or 0),
                    total_slippage=float(statistics.get("total_slippage", 0) or 0),
                    total_commission=float(statistics.get("total_commission", 0) or 0),
                    profit_days=int(statistics.get("profit_days", 0) or 0),
                    loss_days=int(statistics.get("loss_days", 0) or 0),
                )
            )
            if window_name == "full_2020_2026" and strategy_name == "static18_plus_fu" and analysis_df is not None:
                full_static18_plus_fu_daily = analysis_df.copy()

    summary = pd.DataFrame(rows).sort_values(["analysis_start", "strategy_name"]).reset_index(drop=True)
    return summary, full_static18_plus_fu_daily


def run_start_year_backtests(static18_plus_fu_overrides: dict[str, Any]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for window_name, display_label, analysis_start, analysis_end in START_YEAR_WINDOWS:
        print(f"[fu-candidate-robustness] start-year {window_name}: {analysis_start.date()} -> {analysis_end.date()}")
        _, _, statistics = run_backtest(
            risk_ratio=BASE_RISK_RATIO,
            strategy_overrides=static18_plus_fu_overrides,
            analysis_start=analysis_start,
            analysis_end=analysis_end,
            capital=CAPITAL,
            save_artifacts=False,
            include_start_year_sweep=False,
            file_prefix=f"{EXPERIMENT_TAG}_{window_name}_static18_plus_fu",
            chart_title=f"QMT Roll {window_name} static18_plus_fu",
        )
        rows.append(
            build_summary_row(
                statistics,
                analysis_start=analysis_start,
                analysis_end=analysis_end,
                window_name=window_name,
                display_label=display_label,
                strategy_name="static18_plus_fu",
                total_net_pnl=float(statistics.get("total_net_pnl", 0) or 0),
                total_slippage=float(statistics.get("total_slippage", 0) or 0),
                total_commission=float(statistics.get("total_commission", 0) or 0),
                profit_days=int(statistics.get("profit_days", 0) or 0),
                loss_days=int(statistics.get("loss_days", 0) or 0),
            )
        )
    return pd.DataFrame(rows).sort_values("analysis_start").reset_index(drop=True)


def calculate_metrics_from_net_pnl(net_pnl: np.ndarray, *, initial_capital: float = CAPITAL) -> dict[str, float]:
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


def build_slippage_stress(daily: pd.DataFrame | None) -> pd.DataFrame:
    if daily is None or daily.empty:
        return pd.DataFrame()
    frame = daily.reset_index().rename(columns={"index": "date"}).copy()
    base_net_pnl = frame["net_pnl"].to_numpy(dtype=float)
    slippage = frame["slippage"].to_numpy(dtype=float)
    trade_count = int(frame["trade_count"].sum())
    rows: list[dict[str, Any]] = []
    for multiplier in SLIPPAGE_MULTIPLIERS:
        stressed_net_pnl = base_net_pnl - (multiplier - 1.0) * slippage
        metrics = calculate_metrics_from_net_pnl(stressed_net_pnl)
        rows.append(
            {
                "strategy_name": "static18_plus_fu",
                "slippage_multiplier": multiplier,
                "extra_slippage": float(((multiplier - 1.0) * slippage).sum()),
                "total_slippage": float((multiplier * slippage).sum()),
                "total_trade_count": trade_count,
                **metrics,
            }
        )
    return pd.DataFrame(rows)


def load_reference_cycle_summary() -> pd.DataFrame:
    if not AI_MULTICYCLE_REFERENCE_PATH.exists():
        return pd.DataFrame()
    reference = pd.read_csv(AI_MULTICYCLE_REFERENCE_PATH)
    keep = reference[reference["strategy_name"].isin(["baseline_floor35", "ai_top8_product_pool"])].copy()
    keep["source"] = "stage68_71_reference"
    return keep


def build_cycle_comparison(combined: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for window_name, group in combined.groupby("window_name", sort=False):
        by_strategy = {str(row.strategy_name): row for row in group.itertuples(index=False)}
        for candidate_name in [
            "static18_plus_fu",
            "ai_top8_plus_fu_satellite",
            "ai_top8_plus_fu_satellite_post_signal",
        ]:
            candidate = by_strategy.get(candidate_name)
            if candidate is None:
                continue
            for reference_name in ["baseline_floor35", "ai_top8_product_pool"]:
                reference = by_strategy.get(reference_name)
                if reference is None:
                    continue
                rows.append(
                    {
                        "window_name": window_name,
                        "candidate_name": candidate_name,
                        "reference_name": reference_name,
                        "end_balance_diff": _safe_float(candidate.end_balance) - _safe_float(reference.end_balance),
                        "total_return_pct_diff": _safe_float(candidate.total_return_pct)
                        - _safe_float(reference.total_return_pct),
                        "max_dd_percent_diff": _safe_float(candidate.max_dd_percent)
                        - _safe_float(reference.max_dd_percent),
                        "sharpe_ratio_diff": _safe_float(candidate.sharpe_ratio) - _safe_float(reference.sharpe_ratio),
                        "trade_count_diff": int(_safe_float(candidate.total_trade_count) - _safe_float(reference.total_trade_count)),
                        "slippage_diff": _safe_float(candidate.total_slippage) - _safe_float(reference.total_slippage),
                    }
                )
    return pd.DataFrame(rows)


def build_report(
    cycle_summary: pd.DataFrame,
    start_year_summary: pd.DataFrame,
    slippage_stress: pd.DataFrame,
    combined_summary: pd.DataFrame,
    cycle_comparison: pd.DataFrame,
) -> str:
    cycle_view = cycle_summary[
        [
            "window_name",
            "strategy_name",
            "end_balance",
            "total_return_pct",
            "max_dd_percent",
            "sharpe_ratio",
            "total_trade_count",
            "total_slippage",
        ]
    ].copy()
    start_view = start_year_summary[
        [
            "window_name",
            "end_balance",
            "total_return_pct",
            "max_dd_percent",
            "sharpe_ratio",
            "total_trade_count",
            "total_slippage",
        ]
    ].copy()
    stress_view = slippage_stress[
        [
            "slippage_multiplier",
            "end_balance",
            "total_return_pct",
            "max_dd_percent",
            "sharpe_ratio",
            "total_slippage",
            "total_trade_count",
        ]
    ].copy()
    comparison_view = cycle_comparison[
        [
            "window_name",
            "candidate_name",
            "reference_name",
            "end_balance_diff",
            "total_return_pct_diff",
            "max_dd_percent_diff",
            "sharpe_ratio_diff",
        ]
    ].copy()
    reference_view = combined_summary[
        combined_summary["strategy_name"].isin(["baseline_floor35", "ai_top8_product_pool"])
    ][
        [
            "window_name",
            "strategy_name",
            "end_balance",
            "total_return_pct",
            "max_dd_percent",
            "sharpe_ratio",
        ]
    ].copy()

    lines = [
        "# Fu Candidate Robustness Backtest",
        "",
        "## Boundary",
        "",
        "- This is a candidate robustness test, not an official strategy upgrade.",
        "- `fu.SHFE` is tested as a fixed satellite candidate after structural prefiltering.",
        "- The AI test keeps the original AI Top8 logic and only appends `fu.SHFE` as a fixed satellite.",
        "- No TopN search, no parameter optimization, and no full-market expansion.",
        "",
        "## Candidate Cycle Summary",
        "",
        to_markdown_table(cycle_view),
        "",
        "## Reference Cycle Summary",
        "",
        to_markdown_table(reference_view),
        "",
        "## Candidate vs References",
        "",
        to_markdown_table(comparison_view),
        "",
        "## Static18 Plus Fu Start-Year Sweep",
        "",
        to_markdown_table(start_view),
        "",
        "## Static18 Plus Fu Slippage Stress",
        "",
        to_markdown_table(stress_view),
    ]
    return "\n".join(lines)


def build_payload(
    cycle_summary: pd.DataFrame,
    start_year_summary: pd.DataFrame,
    slippage_stress: pd.DataFrame,
    combined_summary: pd.DataFrame,
    cycle_comparison: pd.DataFrame,
) -> dict[str, Any]:
    return {
        "experiment_tag": EXPERIMENT_TAG,
        "base_risk_ratio": BASE_RISK_RATIO,
        "capital": CAPITAL,
        "fu_product": FU_PRODUCT,
        "cycle_windows": [
            {
                **window,
                "analysis_start": window["analysis_start"].date().isoformat(),
                "analysis_end": window["analysis_end"].date().isoformat(),
            }
            for window in CYCLE_WINDOWS
        ],
        "artifacts": {
            "universe_csv": str(UNIVERSE_PATH),
            "ai_satellite_eligibility_csv": str(AI_SATELLITE_ELIGIBILITY_PATH),
            "ai_satellite_post_signal_eligibility_csv": str(AI_SATELLITE_POST_SIGNAL_ELIGIBILITY_PATH),
            "cycle_summary_csv": str(CYCLE_SUMMARY_PATH),
            "start_year_summary_csv": str(START_YEAR_SUMMARY_PATH),
            "slippage_stress_csv": str(SLIPPAGE_STRESS_PATH),
            "combined_cycle_summary_csv": str(COMBINED_CYCLE_SUMMARY_PATH),
            "summary_json": str(SUMMARY_JSON_PATH),
            "report_md": str(REPORT_PATH),
        },
        "cycle_summary": cycle_summary.to_dict(orient="records"),
        "start_year_summary": start_year_summary.to_dict(orient="records"),
        "slippage_stress": slippage_stress.to_dict(orient="records"),
        "combined_cycle_summary": combined_summary.to_dict(orient="records"),
        "cycle_comparison": cycle_comparison.to_dict(orient="records"),
        "design_boundary": (
            "A positive full-period result is insufficient. fu.SHFE must improve robustness across cycles "
            "and not damage the current AI Top8 candidate before it can be promoted."
        ),
    }


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    universe_path = build_static18_plus_fu_universe()
    satellite_path = build_ai_satellite_eligibility()
    satellite_post_signal_path = build_ai_satellite_post_signal_eligibility()
    specs = strategy_specs(universe_path, satellite_path, satellite_post_signal_path)

    cycle_summary, full_static18_plus_fu_daily = run_cycle_backtests(specs)
    start_year_summary = run_start_year_backtests(dict(specs[0]["strategy_overrides"]))
    slippage_stress = build_slippage_stress(full_static18_plus_fu_daily)

    reference_summary = load_reference_cycle_summary()
    if not reference_summary.empty:
        cycle_summary["source"] = "stage75_fu_candidate"
        combined_summary = pd.concat([reference_summary, cycle_summary], ignore_index=True, sort=False)
        combined_summary.sort_values(["analysis_start", "strategy_name"], inplace=True)
        combined_summary.reset_index(drop=True, inplace=True)
    else:
        combined_summary = cycle_summary.copy()
        combined_summary["source"] = "stage75_fu_candidate"
    cycle_comparison = build_cycle_comparison(combined_summary)

    cycle_summary.to_csv(CYCLE_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    start_year_summary.to_csv(START_YEAR_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    slippage_stress.to_csv(SLIPPAGE_STRESS_PATH, index=False, encoding="utf-8-sig")
    combined_summary.to_csv(COMBINED_CYCLE_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    SUMMARY_JSON_PATH.write_text(
        json.dumps(
            build_payload(cycle_summary, start_year_summary, slippage_stress, combined_summary, cycle_comparison),
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    REPORT_PATH.write_text(
        build_report(cycle_summary, start_year_summary, slippage_stress, combined_summary, cycle_comparison),
        encoding="utf-8",
    )

    print(f"[fu-candidate-robustness] cycle summary csv: {CYCLE_SUMMARY_PATH}")
    print(f"[fu-candidate-robustness] start-year summary csv: {START_YEAR_SUMMARY_PATH}")
    print(f"[fu-candidate-robustness] slippage stress csv: {SLIPPAGE_STRESS_PATH}")
    print(f"[fu-candidate-robustness] report md: {REPORT_PATH}")
    print(cycle_summary.to_string(index=False))
    print(start_year_summary.to_string(index=False))
    print(slippage_stress.to_string(index=False))


if __name__ == "__main__":
    main()
