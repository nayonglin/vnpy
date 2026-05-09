from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from run_qmt_roll_backtest import START_YEAR_WINDOWS, build_summary_row, run_backtest
from run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest import BASE_RISK_RATIO
from run_qmt_roll_stage192_manual_pool_add_one_validation import (
    BASE_EXPERIMENT_NAME,
    CANDIDATE_PRODUCTS,
    EXPERIMENT_TAG as STAGE192_TAG,
    build_post_signal_eligibility,
    build_universe,
)
from run_qmt_roll_selection_long015_volref30_corr_fu_candidate_robustness_backtest import (
    CAPITAL,
    CYCLE_WINDOWS,
    FU_PRODUCT,
    to_markdown_table,
)
from run_qmt_roll_stage192_manual_pool_add_one_validation import _strategy_overrides as stage192_strategy_overrides


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

EXPERIMENT_TAG: str = "qmt_roll_stage193_fu_satellite_deep_validation"
MODEL_TAG: str = "stage193_fu_satellite_deep_validation_v1"

SUMMARY_CSV_PATH: Path = OUTPUT_DIR / f"{EXPERIMENT_TAG}_summary_{MODEL_TAG}.csv"
COMPARISON_CSV_PATH: Path = OUTPUT_DIR / f"{EXPERIMENT_TAG}_comparison_{MODEL_TAG}.csv"
START_YEAR_CSV_PATH: Path = OUTPUT_DIR / f"{EXPERIMENT_TAG}_start_year_{MODEL_TAG}.csv"
START_YEAR_COMPARISON_CSV_PATH: Path = OUTPUT_DIR / f"{EXPERIMENT_TAG}_start_year_comparison_{MODEL_TAG}.csv"
ANNUAL_CSV_PATH: Path = OUTPUT_DIR / f"{EXPERIMENT_TAG}_annual_returns_{MODEL_TAG}.csv"
SLIPPAGE_STRESS_CSV_PATH: Path = OUTPUT_DIR / f"{EXPERIMENT_TAG}_slippage_stress_{MODEL_TAG}.csv"
SLIPPAGE_COMPARISON_CSV_PATH: Path = OUTPUT_DIR / f"{EXPERIMENT_TAG}_slippage_comparison_{MODEL_TAG}.csv"
EQUITY_CURVE_CSV_PATH: Path = OUTPUT_DIR / f"{EXPERIMENT_TAG}_equity_curves_{MODEL_TAG}.csv"
EQUITY_CURVE_HTML_PATH: Path = OUTPUT_DIR / f"{EXPERIMENT_TAG}_equity_curves_{MODEL_TAG}.html"
SUMMARY_JSON_PATH: Path = OUTPUT_DIR / f"{EXPERIMENT_TAG}_summary_{MODEL_TAG}.json"
REPORT_PATH: Path = OUTPUT_DIR / f"{EXPERIMENT_TAG}_report_{MODEL_TAG}.md"

PROFILE_NO_FU: str = "manual18_ai_top8_no_fu"
PROFILE_WITH_FU: str = "manual18_ai_top8_plus_fu"
PROFILE_SPECS: tuple[dict[str, Any], ...] = (
    {
        "profile_name": PROFILE_NO_FU,
        "experiment_name": BASE_EXPERIMENT_NAME,
        "satellite_products": (),
    },
    {
        "profile_name": PROFILE_WITH_FU,
        "experiment_name": "manual18_plus_fu_SHFE",
        "satellite_products": (FU_PRODUCT,),
    },
)

SLIPPAGE_MULTIPLIERS: tuple[float, ...] = (1.0, 1.5, 2.0, 3.0, 5.0)
TRADING_DAYS_PER_YEAR: int = 240


def _safe_float(value: Any) -> float:
    try:
        if pd.isna(value):
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def profile_overrides(experiment_name: str, satellites: tuple[str, ...]) -> dict[str, Any]:
    universe_path = build_universe(experiment_name, satellites)
    eligibility_path, strategy_name = build_post_signal_eligibility(experiment_name, satellites)
    return stage192_strategy_overrides(universe_path, eligibility_path, strategy_name, satellites)


def run_cycle_summary() -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    rows: list[dict[str, Any]] = []
    full_daily: dict[str, pd.DataFrame] = {}
    for profile in PROFILE_SPECS:
        profile_name = str(profile["profile_name"])
        experiment_name = str(profile["experiment_name"])
        satellites = tuple(profile["satellite_products"])
        overrides = profile_overrides(experiment_name, satellites)
        for window in CYCLE_WINDOWS:
            window_name = str(window["window_name"])
            save_artifacts = window_name == "full_2020_2026"
            file_prefix = f"{EXPERIMENT_TAG}_{profile_name}_full" if save_artifacts else f"{EXPERIMENT_TAG}_{profile_name}_{window_name}"
            print(f"[stage193] cycle {profile_name} / {window_name}")
            _, daily, statistics = run_backtest(
                risk_ratio=BASE_RISK_RATIO,
                strategy_overrides=overrides,
                analysis_start=window["analysis_start"],
                analysis_end=window["analysis_end"],
                capital=CAPITAL,
                save_artifacts=save_artifacts,
                include_start_year_sweep=False,
                file_prefix=file_prefix,
                chart_title=f"Stage193 {profile_name} {window_name}",
            )
            rows.append(
                build_summary_row(
                    statistics,
                    analysis_start=window["analysis_start"],
                    analysis_end=window["analysis_end"],
                    profile_name=profile_name,
                    experiment_name=experiment_name,
                    window_name=window_name,
                    display_label=str(window["display_label"]),
                    satellite_products=",".join(satellites),
                    satellite_count=len(satellites),
                    strategy_overrides_json=json.dumps(overrides, ensure_ascii=False, sort_keys=True),
                    total_net_pnl=float(statistics.get("total_net_pnl", 0) or 0),
                    total_slippage=float(statistics.get("total_slippage", 0) or 0),
                    total_commission=float(statistics.get("total_commission", 0) or 0),
                    profit_days=int(statistics.get("profit_days", 0) or 0),
                    loss_days=int(statistics.get("loss_days", 0) or 0),
                )
            )
            if save_artifacts and daily is not None and not daily.empty:
                full_daily[profile_name] = daily.copy()
    return pd.DataFrame(rows).sort_values(["window_name", "profile_name"]).reset_index(drop=True), full_daily


def run_start_year_summary() -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for profile in PROFILE_SPECS:
        profile_name = str(profile["profile_name"])
        experiment_name = str(profile["experiment_name"])
        satellites = tuple(profile["satellite_products"])
        overrides = profile_overrides(experiment_name, satellites)
        for window_name, display_label, analysis_start, analysis_end in START_YEAR_WINDOWS:
            print(f"[stage193] start-year {profile_name} / {window_name}")
            _, _, statistics = run_backtest(
                risk_ratio=BASE_RISK_RATIO,
                strategy_overrides=overrides,
                analysis_start=analysis_start,
                analysis_end=analysis_end,
                capital=CAPITAL,
                save_artifacts=False,
                include_start_year_sweep=False,
                file_prefix=f"{EXPERIMENT_TAG}_{profile_name}_{window_name}",
                chart_title=f"Stage193 {profile_name} {window_name}",
            )
            rows.append(
                build_summary_row(
                    statistics,
                    analysis_start=analysis_start,
                    analysis_end=analysis_end,
                    profile_name=profile_name,
                    experiment_name=experiment_name,
                    window_name=window_name,
                    display_label=display_label,
                    satellite_products=",".join(satellites),
                    satellite_count=len(satellites),
                    total_net_pnl=float(statistics.get("total_net_pnl", 0) or 0),
                    total_slippage=float(statistics.get("total_slippage", 0) or 0),
                    total_commission=float(statistics.get("total_commission", 0) or 0),
                    profit_days=int(statistics.get("profit_days", 0) or 0),
                    loss_days=int(statistics.get("loss_days", 0) or 0),
                )
            )
    return pd.DataFrame(rows).sort_values(["window_name", "profile_name"]).reset_index(drop=True)


def build_pair_comparison(summary: pd.DataFrame) -> pd.DataFrame:
    value_columns = [
        "end_balance",
        "total_return_pct",
        "max_dd_percent",
        "sharpe_ratio",
        "total_slippage",
        "total_trade_count",
        "win_ratio_pct",
    ]
    no_fu = summary[summary["profile_name"] == PROFILE_NO_FU][["window_name", *value_columns]].copy()
    with_fu = summary[summary["profile_name"] == PROFILE_WITH_FU][["window_name", *value_columns]].copy()
    merged = no_fu.merge(with_fu, on="window_name", suffixes=("_no_fu", "_with_fu"), how="inner")
    for column in value_columns:
        merged[f"{column}_diff"] = merged[f"{column}_with_fu"] - merged[f"{column}_no_fu"]
    merged["with_fu_return_better"] = merged["total_return_pct_diff"] > 0
    merged["with_fu_sharpe_better"] = merged["sharpe_ratio_diff"] > 0
    merged["with_fu_dd_not_worse"] = merged["max_dd_percent_diff"] >= -1e-9
    return merged.sort_values("window_name").reset_index(drop=True)


def annual_returns(full_daily: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for profile_name, daily in full_daily.items():
        df = daily.reset_index().rename(columns={"index": "date"}).copy()
        df["date"] = pd.to_datetime(df["date"])
        df["balance"] = pd.to_numeric(df["balance"], errors="coerce")
        previous_balance = CAPITAL
        for year, group in df.groupby(df["date"].dt.year, sort=True):
            group = group.sort_values("date")
            start_balance = float(previous_balance)
            end_balance = float(group["balance"].iloc[-1])
            min_balance = float(group["balance"].min())
            year_pnl = end_balance - start_balance
            rows.append(
                {
                    "profile_name": profile_name,
                    "year": int(year),
                    "start_balance": start_balance,
                    "end_balance": end_balance,
                    "year_pnl": year_pnl,
                    "year_return_pct": year_pnl / start_balance * 100.0 if start_balance else 0.0,
                    "min_balance_in_year": min_balance,
                }
            )
            previous_balance = end_balance
    return pd.DataFrame(rows).sort_values(["year", "profile_name"]).reset_index(drop=True)


def calculate_metrics_from_net_pnl(net_pnl: np.ndarray) -> dict[str, float]:
    if len(net_pnl) == 0:
        return {"end_balance": 0.0, "total_return_pct": 0.0, "max_dd_percent": 0.0, "sharpe_ratio": 0.0}
    equity = CAPITAL + np.cumsum(net_pnl.astype(float))
    previous_equity = np.concatenate([[CAPITAL], equity[:-1]])
    returns = np.divide(net_pnl, previous_equity, out=np.zeros_like(net_pnl, dtype=float), where=previous_equity != 0)
    high_water = np.maximum.accumulate(equity)
    drawdown_pct = np.divide(
        equity - high_water,
        high_water,
        out=np.zeros_like(equity, dtype=float),
        where=high_water != 0,
    ) * 100.0
    return_std = float(np.std(returns, ddof=1)) if len(returns) > 1 else 0.0
    sharpe = float(np.mean(returns) / return_std * math.sqrt(TRADING_DAYS_PER_YEAR)) if return_std > 0 else 0.0
    return {
        "end_balance": float(equity[-1]),
        "total_return_pct": float((equity[-1] / CAPITAL - 1.0) * 100.0),
        "max_dd_percent": float(drawdown_pct.min()),
        "sharpe_ratio": sharpe,
    }


def slippage_stress(full_daily: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for profile_name, daily in full_daily.items():
        frame = daily.reset_index().rename(columns={"index": "date"}).copy()
        net_pnl = pd.to_numeric(frame["net_pnl"], errors="coerce").fillna(0.0).to_numpy(dtype=float)
        slippage = pd.to_numeric(frame["slippage"], errors="coerce").fillna(0.0).to_numpy(dtype=float)
        trade_count = int(pd.to_numeric(frame["trade_count"], errors="coerce").fillna(0.0).sum())
        for multiplier in SLIPPAGE_MULTIPLIERS:
            stressed_net_pnl = net_pnl - (multiplier - 1.0) * slippage
            rows.append(
                {
                    "profile_name": profile_name,
                    "slippage_multiplier": multiplier,
                    "extra_slippage": float(((multiplier - 1.0) * slippage).sum()),
                    "total_slippage": float((multiplier * slippage).sum()),
                    "total_trade_count": trade_count,
                    **calculate_metrics_from_net_pnl(stressed_net_pnl),
                }
            )
    return pd.DataFrame(rows).sort_values(["slippage_multiplier", "profile_name"]).reset_index(drop=True)


def build_slippage_comparison(stress: pd.DataFrame) -> pd.DataFrame:
    if stress.empty:
        return pd.DataFrame()
    value_columns = [
        "end_balance",
        "total_return_pct",
        "max_dd_percent",
        "sharpe_ratio",
        "total_slippage",
        "total_trade_count",
    ]
    no_fu = stress[stress["profile_name"] == PROFILE_NO_FU][["slippage_multiplier", *value_columns]].copy()
    with_fu = stress[stress["profile_name"] == PROFILE_WITH_FU][["slippage_multiplier", *value_columns]].copy()
    merged = no_fu.merge(with_fu, on="slippage_multiplier", suffixes=("_no_fu", "_with_fu"), how="inner")
    for column in value_columns:
        merged[f"{column}_diff"] = merged[f"{column}_with_fu"] - merged[f"{column}_no_fu"]
    return merged.sort_values("slippage_multiplier").reset_index(drop=True)


def build_equity_curves(full_daily: dict[str, pd.DataFrame]) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for profile_name, daily in full_daily.items():
        df = daily.reset_index().rename(columns={"index": "date"})[["date", "balance"]].copy()
        df["date"] = pd.to_datetime(df["date"])
        df["profile_name"] = profile_name
        frames.append(df)
    curves = pd.concat(frames, ignore_index=True).sort_values(["date", "profile_name"])
    wide = curves.pivot_table(index="date", columns="profile_name", values="balance", aggfunc="last").sort_index()
    wide.to_csv(EQUITY_CURVE_CSV_PATH, encoding="utf-8-sig")
    return curves


def write_equity_html(curves: pd.DataFrame) -> None:
    try:
        import plotly.graph_objects as go

        fig = go.Figure()
        for profile_name, group in curves.groupby("profile_name", sort=False):
            fig.add_trace(go.Scatter(x=group["date"], y=group["balance"], mode="lines", name=str(profile_name)))
        fig.update_layout(
            title="Stage193 Fu Satellite Deep Validation Equity Curves",
            xaxis_title="Date",
            yaxis_title="Balance",
            hovermode="x unified",
            template="plotly_white",
            width=1200,
            height=720,
        )
        fig.write_html(EQUITY_CURVE_HTML_PATH, include_plotlyjs="cdn")
    except Exception as exc:
        EQUITY_CURVE_HTML_PATH.write_text(
            f"<html><body><h1>Stage193 Equity Curves</h1><p>Plotly failed: {exc}</p></body></html>",
            encoding="utf-8",
        )


def build_report(
    summary: pd.DataFrame,
    comparison: pd.DataFrame,
    start_year: pd.DataFrame,
    start_year_comparison: pd.DataFrame,
    annual: pd.DataFrame,
    stress: pd.DataFrame,
    stress_comparison: pd.DataFrame,
) -> str:
    result_columns = [
        "window_name",
        "profile_name",
        "end_balance",
        "total_return_pct",
        "max_dd_percent",
        "sharpe_ratio",
        "total_slippage",
        "total_trade_count",
        "win_ratio_pct",
    ]
    compare_columns = [
        "window_name",
        "end_balance_diff",
        "total_return_pct_diff",
        "max_dd_percent_diff",
        "sharpe_ratio_diff",
        "total_trade_count_diff",
        "with_fu_return_better",
        "with_fu_sharpe_better",
        "with_fu_dd_not_worse",
    ]
    start_compare_columns = [
        "window_name",
        "end_balance_diff",
        "total_return_pct_diff",
        "max_dd_percent_diff",
        "sharpe_ratio_diff",
        "with_fu_return_better",
        "with_fu_sharpe_better",
        "with_fu_dd_not_worse",
    ]
    annual_columns = [
        "year",
        "profile_name",
        "start_balance",
        "end_balance",
        "year_return_pct",
        "min_balance_in_year",
    ]
    stress_compare_columns = [
        "slippage_multiplier",
        "end_balance_diff",
        "total_return_pct_diff",
        "max_dd_percent_diff",
        "sharpe_ratio_diff",
        "total_trade_count_diff",
    ]
    return "\n".join(
        [
            "# Stage193 Fu Satellite Deep Validation",
            "",
            "## Design",
            "",
            "- Compare no-fu versus fixed `fu.SHFE` satellite under the Stage78 product-pool cadence.",
            "- Fixed arms only; no parameter rescue, no threshold search.",
            "- `with_fu` uses the same profit-only streak isolation as the frozen Stage78 formal profile.",
            "",
            "## Cycle Results",
            "",
            to_markdown_table(summary[result_columns]),
            "",
            "## Cycle Comparison",
            "",
            to_markdown_table(comparison[compare_columns]),
            "",
            "## Start-Year Results",
            "",
            to_markdown_table(start_year[result_columns]),
            "",
            "## Start-Year Comparison",
            "",
            to_markdown_table(start_year_comparison[start_compare_columns]),
            "",
            "## Annual Returns",
            "",
            to_markdown_table(annual[annual_columns]),
            "",
            "## Slippage Stress",
            "",
            to_markdown_table(stress),
            "",
            "## Slippage Comparison",
            "",
            to_markdown_table(stress_comparison[stress_compare_columns]),
            "",
            "## Equity Curves",
            "",
            f"- HTML: `{EQUITY_CURVE_HTML_PATH}`",
            f"- CSV: `{EQUITY_CURVE_CSV_PATH}`",
        ]
    )


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if FU_PRODUCT not in CANDIDATE_PRODUCTS:
        raise ValueError(f"{FU_PRODUCT} not in stage192 candidate list")

    summary, full_daily = run_cycle_summary()
    comparison = build_pair_comparison(summary)
    start_year = run_start_year_summary()
    start_year_comparison = build_pair_comparison(start_year)
    annual = annual_returns(full_daily)
    stress = slippage_stress(full_daily)
    stress_comparison = build_slippage_comparison(stress)
    curves = build_equity_curves(full_daily)
    write_equity_html(curves)

    summary.to_csv(SUMMARY_CSV_PATH, index=False, encoding="utf-8-sig")
    comparison.to_csv(COMPARISON_CSV_PATH, index=False, encoding="utf-8-sig")
    start_year.to_csv(START_YEAR_CSV_PATH, index=False, encoding="utf-8-sig")
    start_year_comparison.to_csv(START_YEAR_COMPARISON_CSV_PATH, index=False, encoding="utf-8-sig")
    annual.to_csv(ANNUAL_CSV_PATH, index=False, encoding="utf-8-sig")
    stress.to_csv(SLIPPAGE_STRESS_CSV_PATH, index=False, encoding="utf-8-sig")
    stress_comparison.to_csv(SLIPPAGE_COMPARISON_CSV_PATH, index=False, encoding="utf-8-sig")

    payload = {
        "experiment_tag": EXPERIMENT_TAG,
        "model_tag": MODEL_TAG,
        "base_risk_ratio": BASE_RISK_RATIO,
        "capital": CAPITAL,
        "source_stage": STAGE192_TAG,
        "profiles": PROFILE_SPECS,
        "artifacts": {
            "summary": str(SUMMARY_CSV_PATH),
            "comparison": str(COMPARISON_CSV_PATH),
            "start_year": str(START_YEAR_CSV_PATH),
            "start_year_comparison": str(START_YEAR_COMPARISON_CSV_PATH),
            "annual": str(ANNUAL_CSV_PATH),
            "slippage_stress": str(SLIPPAGE_STRESS_CSV_PATH),
            "slippage_comparison": str(SLIPPAGE_COMPARISON_CSV_PATH),
            "equity_curve_csv": str(EQUITY_CURVE_CSV_PATH),
            "equity_curve_html": str(EQUITY_CURVE_HTML_PATH),
            "report": str(REPORT_PATH),
        },
        "cycle_comparison": comparison.to_dict(orient="records"),
        "start_year_comparison": start_year_comparison.to_dict(orient="records"),
        "annual_returns": annual.to_dict(orient="records"),
        "slippage_comparison": stress_comparison.to_dict(orient="records"),
    }
    SUMMARY_JSON_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_PATH.write_text(
        build_report(summary, comparison, start_year, start_year_comparison, annual, stress, stress_comparison),
        encoding="utf-8",
    )

    print(f"[stage193] report: {REPORT_PATH}")
    print(f"[stage193] equity html: {EQUITY_CURVE_HTML_PATH}")
    print(comparison.to_string(index=False))
    print(start_year_comparison.to_string(index=False))
    print(stress_comparison.to_string(index=False))


if __name__ == "__main__":
    main()
