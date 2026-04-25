from __future__ import annotations

import json
import math
import re
import sys
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from qmt_roll_official_stage78_config import (
    OFFICIAL_STAGE78_REFERENCE_METRICS,
    OFFICIAL_STAGE78_ROLE,
    OFFICIAL_STAGE78_VERSION,
    build_official_stage78_overrides,
)
from qmt_universe import END_DT, START_DT
from run_qmt_roll_backtest import build_summary_row, run_backtest
from run_qmt_roll_official_stage78_fu_sn_satellite_candidate_backtest import (
    CAPITAL,
    EXPERIMENT_NAME,
    MODEL_TAG as CANDIDATE_MODEL_TAG,
    SATELLITE_PRODUCTS,
    SIZING_EQUITY_CAP,
    SN_PRODUCT,
    build_strategy_overrides,
)
from run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest import BASE_RISK_RATIO


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

MODEL_TAG: str = "stage78_fu_sn_satellite_robustness_v1"
OUTPUT_PREFIX: str = "qmt_roll_official_stage78_fu_sn_satellite_robustness"
FULL_ARTIFACT_PREFIX: str = f"{OUTPUT_PREFIX}_candidate_full"

FULL_SUMMARY_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_full_summary_{MODEL_TAG}.csv"
PRODUCT_ATTRIBUTION_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_attribution_{MODEL_TAG}.csv"
PRODUCT_YEAR_ATTRIBUTION_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_year_attribution_{MODEL_TAG}.csv"
SLIPPAGE_STRESS_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_slippage_stress_{MODEL_TAG}.csv"
SLIPPAGE_COMPARISON_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_slippage_comparison_{MODEL_TAG}.csv"
START_YEAR_COMPARISON_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_start_year_comparison_{MODEL_TAG}.csv"
SUMMARY_JSON_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.json"
REPORT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

CANDIDATE_POSITION_CHANGES_PATH: Path = (
    OUTPUT_DIR / f"{FULL_ARTIFACT_PREFIX}_position_changes_2020_2026_04.csv"
)
QUARTER_SUMMARY_PATH: Path = (
    OUTPUT_DIR
    / "qmt_roll_official_stage78_fu_sn_satellite_quarterly_walkforward_quarter_summary_stage78_fu_sn_satellite_quarterly_wf_v1.csv"
)

PROFILE_STAGE78: str = OFFICIAL_STAGE78_VERSION
PROFILE_CANDIDATE: str = "stage78_plus_fu_sn_satellite"
TRADING_DAYS_PER_YEAR: int = 240
SLIPPAGE_MULTIPLIERS: tuple[float, ...] = (1.0, 1.5, 2.0, 3.0, 5.0)
START_YEAR_WINDOWS: tuple[str, ...] = (
    "q2020_1",
    "q2021_1",
    "q2022_1",
    "q2023_1",
    "q2024_1",
    "q2025_1",
    "q2026_1",
)


def _safe_float(value: Any) -> float:
    try:
        if pd.isna(value):
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _safe_int(value: Any) -> int:
    return int(round(_safe_float(value)))


def product_from_contract(vt_symbol: object) -> str:
    raw = str(vt_symbol)
    if "." not in raw:
        return raw
    symbol, exchange = raw.split(".", 1)
    match = re.match(r"^([A-Za-z]+)", symbol)
    product = match.group(1) if match else symbol
    return f"{product}.{exchange}"


def to_markdown_table(df: pd.DataFrame, columns: list[str] | None = None, max_rows: int = 30) -> str:
    if df.empty:
        return "_empty_"
    view = df[columns].copy() if columns else df.copy()
    view = view.head(max_rows)
    for column in view.columns:
        if pd.api.types.is_float_dtype(view[column]):
            view[column] = view[column].map(lambda value: f"{value:.4f}")
    header = "| " + " | ".join(view.columns) + " |"
    separator = "| " + " | ".join(["---"] * len(view.columns)) + " |"
    rows = ["| " + " | ".join(map(str, row)) + " |" for row in view.to_numpy()]
    return "\n".join([header, separator, *rows])


def run_profile(
    *,
    profile_name: str,
    strategy_overrides: dict[str, Any],
    save_artifacts: bool,
    file_prefix: str,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    print(f"[stage78-fu-sn-robustness] run {profile_name}: {START_DT.date()} -> {END_DT.date()}")
    log_buffer = StringIO()
    try:
        with redirect_stdout(log_buffer), redirect_stderr(log_buffer):
            _, analysis_df, statistics = run_backtest(
                risk_ratio=BASE_RISK_RATIO,
                strategy_overrides=strategy_overrides,
                analysis_start=START_DT,
                analysis_end=END_DT,
                capital=CAPITAL,
                save_artifacts=save_artifacts,
                include_start_year_sweep=False,
                file_prefix=file_prefix,
                chart_title=f"QMT Roll {profile_name} Robustness",
            )
    except Exception:
        sys.stderr.write(log_buffer.getvalue())
        raise

    if analysis_df is None:
        analysis_df = pd.DataFrame()
    analysis_df = analysis_df.copy()
    if not analysis_df.empty:
        analysis_df.sort_index(inplace=True)
    return analysis_df, statistics


def build_full_summary(stage78_statistics: dict[str, Any], candidate_statistics: dict[str, Any]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for profile_name, statistics, overrides in [
        (PROFILE_STAGE78, stage78_statistics, build_official_stage78_overrides()),
        (PROFILE_CANDIDATE, candidate_statistics, build_strategy_overrides()),
    ]:
        rows.append(
            build_summary_row(
                statistics,
                analysis_start=START_DT,
                analysis_end=END_DT,
                official_version=OFFICIAL_STAGE78_VERSION,
                official_role=OFFICIAL_STAGE78_ROLE,
                experiment_name=EXPERIMENT_NAME if profile_name == PROFILE_CANDIDATE else "official_stage78_defensive_v1",
                profile_name=profile_name,
                window_name="full_2020_2026",
                display_label="full",
                capital=CAPITAL,
                sizing_equity_cap=SIZING_EQUITY_CAP,
                satellite_products=",".join(SATELLITE_PRODUCTS) if profile_name == PROFILE_CANDIDATE else "fu.SHFE",
                strategy_overrides_json=json.dumps(overrides, ensure_ascii=False, sort_keys=True),
                total_net_pnl=float(statistics.get("total_net_pnl", 0) or 0),
                total_slippage=float(statistics.get("total_slippage", 0) or 0),
                total_commission=float(statistics.get("total_commission", 0) or 0),
                profit_days=int(statistics.get("profit_days", 0) or 0),
                loss_days=int(statistics.get("loss_days", 0) or 0),
            )
        )
    summary = pd.DataFrame(rows)
    value_columns = [
        "end_balance",
        "total_return_pct",
        "max_dd_percent",
        "sharpe_ratio",
        "total_slippage",
        "total_trade_count",
    ]
    reference = summary.loc[summary["profile_name"] == PROFILE_STAGE78, value_columns].iloc[0]
    candidate = summary.loc[summary["profile_name"] == PROFILE_CANDIDATE, value_columns].iloc[0]
    diff = {f"{column}_diff_vs_stage78": _safe_float(candidate[column]) - _safe_float(reference[column]) for column in value_columns}
    for column, value in diff.items():
        summary.loc[summary["profile_name"] == PROFILE_CANDIDATE, column] = value
    return summary


def calculate_metrics_from_net_pnl(net_pnl: np.ndarray, *, capital: float = CAPITAL) -> dict[str, float]:
    if len(net_pnl) == 0:
        return {
            "end_balance": 0.0,
            "total_return_pct": 0.0,
            "max_dd_percent": 0.0,
            "sharpe_ratio": 0.0,
        }
    equity = capital + np.cumsum(net_pnl.astype(float))
    previous_equity = np.concatenate([[capital], equity[:-1]])
    returns = np.divide(
        net_pnl,
        previous_equity,
        out=np.zeros_like(net_pnl, dtype=float),
        where=previous_equity != 0,
    )
    high_water = np.maximum.accumulate(equity)
    drawdown_pct = np.divide(
        equity - high_water,
        high_water,
        out=np.zeros_like(equity, dtype=float),
        where=high_water != 0,
    ) * 100.0
    return_std = float(np.std(returns, ddof=1)) if len(returns) > 1 else 0.0
    sharpe_ratio = float(np.mean(returns) / return_std * math.sqrt(TRADING_DAYS_PER_YEAR)) if return_std > 0 else 0.0
    return {
        "end_balance": float(equity[-1]),
        "total_return_pct": float((equity[-1] / capital - 1.0) * 100.0),
        "max_dd_percent": float(drawdown_pct.min()),
        "sharpe_ratio": sharpe_ratio,
    }


def build_slippage_stress(profile_name: str, daily: pd.DataFrame) -> pd.DataFrame:
    if daily.empty:
        return pd.DataFrame()
    frame = daily.reset_index().rename(columns={"index": "date"}).copy()
    base_net_pnl = pd.to_numeric(frame["net_pnl"], errors="coerce").fillna(0.0).to_numpy(dtype=float)
    slippage = pd.to_numeric(frame["slippage"], errors="coerce").fillna(0.0).to_numpy(dtype=float)
    trade_count = _safe_int(pd.to_numeric(frame["trade_count"], errors="coerce").fillna(0.0).sum())

    rows: list[dict[str, Any]] = []
    for multiplier in SLIPPAGE_MULTIPLIERS:
        stressed_net_pnl = base_net_pnl - (multiplier - 1.0) * slippage
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
    return pd.DataFrame(rows)


def build_slippage_comparison(slippage_stress: pd.DataFrame) -> pd.DataFrame:
    value_columns = [
        "end_balance",
        "total_return_pct",
        "max_dd_percent",
        "sharpe_ratio",
        "total_slippage",
        "total_trade_count",
    ]
    reference = slippage_stress[slippage_stress["profile_name"] == PROFILE_STAGE78][
        ["slippage_multiplier", *value_columns]
    ].copy()
    candidate = slippage_stress[slippage_stress["profile_name"] == PROFILE_CANDIDATE][
        ["slippage_multiplier", *value_columns]
    ].copy()
    comparison = reference.merge(candidate, on="slippage_multiplier", suffixes=("_stage78", "_candidate"), how="inner")
    for column in value_columns:
        comparison[f"{column}_diff"] = comparison[f"{column}_candidate"] - comparison[f"{column}_stage78"]
    comparison["candidate_end_balance_better"] = (comparison["end_balance_diff"] > 0).astype(int)
    comparison["candidate_sharpe_better"] = (comparison["sharpe_ratio_diff"] > 0).astype(int)
    comparison["candidate_drawdown_worse"] = (comparison["max_dd_percent_diff"] < 0).astype(int)
    return comparison


def build_product_attribution() -> tuple[pd.DataFrame, pd.DataFrame]:
    if not CANDIDATE_POSITION_CHANGES_PATH.exists():
        raise FileNotFoundError(CANDIDATE_POSITION_CHANGES_PATH)
    positions = pd.read_csv(CANDIDATE_POSITION_CHANGES_PATH)
    positions["date"] = pd.to_datetime(positions["date"])
    positions["year"] = positions["date"].dt.year
    positions["product_vt_symbol"] = positions["vt_symbol"].map(product_from_contract)

    numeric_columns = [
        "trade_count",
        "turnover",
        "commission",
        "slippage",
        "holding_pnl",
        "trading_pnl",
        "total_pnl",
        "net_pnl",
        "end_pos",
    ]
    for column in numeric_columns:
        positions[column] = pd.to_numeric(positions.get(column, 0.0), errors="coerce").fillna(0.0)

    product_daily = (
        positions.groupby(["date", "product_vt_symbol"], as_index=False)
        .agg(
            net_pnl=("net_pnl", "sum"),
            total_pnl=("total_pnl", "sum"),
            trading_pnl=("trading_pnl", "sum"),
            holding_pnl=("holding_pnl", "sum"),
            turnover=("turnover", "sum"),
            commission=("commission", "sum"),
            slippage=("slippage", "sum"),
            trade_count=("trade_count", "sum"),
            abs_end_pos=("end_pos", lambda s: float(np.abs(s).sum())),
        )
        .sort_values(["product_vt_symbol", "date"])
        .reset_index(drop=True)
    )
    product_daily["active_flag"] = (
        (product_daily["trade_count"].abs() > 0)
        | (product_daily["abs_end_pos"].abs() > 0)
        | (product_daily["net_pnl"].abs() > 1e-9)
    ).astype(int)
    product_daily["trade_day_flag"] = (product_daily["trade_count"].abs() > 0).astype(int)

    portfolio_net_pnl = float(product_daily["net_pnl"].sum())
    rows: list[dict[str, Any]] = []
    for product, group in product_daily.groupby("product_vt_symbol", sort=True):
        cumulative = group["net_pnl"].cumsum().to_numpy(dtype=float)
        high_water = np.maximum.accumulate(np.concatenate([[0.0], cumulative]))[1:]
        drawdown_amount = cumulative - high_water
        active = group[group["active_flag"] > 0]
        trade_days = group[group["trade_day_flag"] > 0]
        rows.append(
            {
                "product_vt_symbol": product,
                "total_net_pnl": float(group["net_pnl"].sum()),
                "contribution_pct_of_portfolio_net_pnl": (
                    float(group["net_pnl"].sum()) / portfolio_net_pnl * 100.0 if abs(portfolio_net_pnl) > 1e-12 else 0.0
                ),
                "max_drawdown_amount": float(drawdown_amount.min()) if len(drawdown_amount) else 0.0,
                "max_drawdown_pct_of_capital": (
                    float(drawdown_amount.min()) / CAPITAL * 100.0 if len(drawdown_amount) else 0.0
                ),
                "total_trade_count": float(group["trade_count"].sum()),
                "trade_days": int(group["trade_day_flag"].sum()),
                "active_days": int(group["active_flag"].sum()),
                "total_turnover": float(group["turnover"].sum()),
                "total_slippage": float(group["slippage"].sum()),
                "total_commission": float(group["commission"].sum()),
                "holding_pnl": float(group["holding_pnl"].sum()),
                "trading_pnl": float(group["trading_pnl"].sum()),
                "net_pnl_per_trade": (
                    float(group["net_pnl"].sum()) / float(group["trade_count"].sum())
                    if float(group["trade_count"].sum()) > 0
                    else 0.0
                ),
                "first_active_date": active["date"].min().date().isoformat() if not active.empty else "",
                "last_active_date": active["date"].max().date().isoformat() if not active.empty else "",
                "first_trade_date": trade_days["date"].min().date().isoformat() if not trade_days.empty else "",
                "last_trade_date": trade_days["date"].max().date().isoformat() if not trade_days.empty else "",
            }
        )
    attribution = pd.DataFrame(rows).sort_values("total_net_pnl", ascending=False).reset_index(drop=True)

    year_attribution = (
        positions.groupby(["year", "product_vt_symbol"], as_index=False)
        .agg(
            total_net_pnl=("net_pnl", "sum"),
            total_trade_count=("trade_count", "sum"),
            total_slippage=("slippage", "sum"),
            active_days=("end_pos", lambda s: int((np.abs(s) > 0).sum())),
        )
        .sort_values(["year", "total_net_pnl"], ascending=[True, False])
        .reset_index(drop=True)
    )
    return attribution, year_attribution


def build_start_year_comparison() -> pd.DataFrame:
    if not QUARTER_SUMMARY_PATH.exists():
        raise FileNotFoundError(QUARTER_SUMMARY_PATH)
    quarter = pd.read_csv(QUARTER_SUMMARY_PATH)
    quarter = quarter[
        (quarter["horizon"].astype(str) == "to_end")
        & quarter["window_name"].astype(str).isin(START_YEAR_WINDOWS)
    ].copy()
    value_columns = [
        "end_balance",
        "total_return_pct",
        "max_dd_percent",
        "sharpe_ratio",
        "total_slippage",
        "total_trade_count",
    ]
    reference = quarter[quarter["profile_name"].astype(str) == PROFILE_STAGE78][
        ["window_name", "analysis_start", "analysis_end", *value_columns]
    ].copy()
    candidate = quarter[quarter["profile_name"].astype(str) == PROFILE_CANDIDATE][
        ["window_name", "analysis_start", "analysis_end", *value_columns]
    ].copy()
    comparison = reference.merge(
        candidate,
        on=["window_name", "analysis_start", "analysis_end"],
        suffixes=("_stage78", "_candidate"),
        how="inner",
    )
    for column in value_columns:
        comparison[f"{column}_diff"] = comparison[f"{column}_candidate"] - comparison[f"{column}_stage78"]
    comparison["candidate_return_better"] = (comparison["total_return_pct_diff"] > 1e-9).astype(int)
    comparison["candidate_drawdown_worse"] = (comparison["max_dd_percent_diff"] < -1e-9).astype(int)
    comparison["candidate_sharpe_worse"] = (comparison["sharpe_ratio_diff"] < -1e-9).astype(int)
    return comparison.sort_values("analysis_start").reset_index(drop=True)


def build_payload(
    *,
    full_summary: pd.DataFrame,
    product_attribution: pd.DataFrame,
    product_year_attribution: pd.DataFrame,
    slippage_stress: pd.DataFrame,
    slippage_comparison: pd.DataFrame,
    start_year_comparison: pd.DataFrame,
) -> dict[str, Any]:
    sn_row = product_attribution[product_attribution["product_vt_symbol"] == SN_PRODUCT]
    sn_year = product_year_attribution[product_year_attribution["product_vt_symbol"] == SN_PRODUCT].copy()
    return {
        "model_tag": MODEL_TAG,
        "candidate_model_tag": CANDIDATE_MODEL_TAG,
        "official_version": OFFICIAL_STAGE78_VERSION,
        "official_role": OFFICIAL_STAGE78_ROLE,
        "experiment_name": EXPERIMENT_NAME,
        "base_risk_ratio": BASE_RISK_RATIO,
        "capital": CAPITAL,
        "sizing_equity_cap": SIZING_EQUITY_CAP,
        "satellite_products": list(SATELLITE_PRODUCTS),
        "reference_metrics": OFFICIAL_STAGE78_REFERENCE_METRICS,
        "full_summary": full_summary.to_dict(orient="records"),
        "sn_product_attribution": sn_row.to_dict(orient="records"),
        "sn_year_attribution": sn_year.to_dict(orient="records"),
        "slippage_comparison": slippage_comparison.to_dict(orient="records"),
        "start_year_comparison": start_year_comparison.to_dict(orient="records"),
        "promotion_checks": {
            "sn_total_net_pnl_positive": bool(not sn_row.empty and _safe_float(sn_row.iloc[0]["total_net_pnl"]) > 0),
            "sn_positive_years": int((pd.to_numeric(sn_year["total_net_pnl"], errors="coerce").fillna(0.0) > 0).sum())
            if not sn_year.empty
            else 0,
            "candidate_beats_stage78_under_5x_fair_slippage": bool(
                not slippage_comparison.empty
                and _safe_float(
                    slippage_comparison.loc[
                        slippage_comparison["slippage_multiplier"] == 5.0,
                        "end_balance_diff",
                    ].iloc[0]
                )
                > 0
            ),
            "start_year_positive_diff_count": int(start_year_comparison["candidate_return_better"].sum())
            if not start_year_comparison.empty
            else 0,
            "start_year_window_count": int(len(start_year_comparison)),
        },
        "outputs": {
            "full_summary": str(FULL_SUMMARY_PATH),
            "product_attribution": str(PRODUCT_ATTRIBUTION_PATH),
            "product_year_attribution": str(PRODUCT_YEAR_ATTRIBUTION_PATH),
            "slippage_stress": str(SLIPPAGE_STRESS_PATH),
            "slippage_comparison": str(SLIPPAGE_COMPARISON_PATH),
            "start_year_comparison": str(START_YEAR_COMPARISON_PATH),
            "summary_json": str(SUMMARY_JSON_PATH),
            "report": str(REPORT_PATH),
        },
    }


def build_report(
    *,
    full_summary: pd.DataFrame,
    product_attribution: pd.DataFrame,
    product_year_attribution: pd.DataFrame,
    slippage_comparison: pd.DataFrame,
    start_year_comparison: pd.DataFrame,
) -> str:
    sn_row = product_attribution[product_attribution["product_vt_symbol"] == SN_PRODUCT]
    sn_year = product_year_attribution[product_year_attribution["product_vt_symbol"] == SN_PRODUCT].copy()
    top_product_view = product_attribution.head(12).copy()
    return "\n".join(
        [
            "# Stage78 + fu/sn Satellite Robustness",
            "",
            "## Purpose",
            "",
            "- Falsify the `sn.SHFE` satellite before any formal promotion.",
            "- Check whether the edge is product-specific, survives fair slippage stress, and transfers across start years.",
            "",
            "## Full Summary",
            "",
            to_markdown_table(
                full_summary,
                [
                    "profile_name",
                    "end_balance",
                    "total_return_pct",
                    "max_dd_percent",
                    "sharpe_ratio",
                    "total_slippage",
                    "total_trade_count",
                    "end_balance_diff_vs_stage78",
                    "sharpe_ratio_diff_vs_stage78",
                ],
            ),
            "",
            "## Top Product Attribution",
            "",
            to_markdown_table(
                top_product_view,
                [
                    "product_vt_symbol",
                    "total_net_pnl",
                    "contribution_pct_of_portfolio_net_pnl",
                    "max_drawdown_pct_of_capital",
                    "total_trade_count",
                    "total_slippage",
                    "net_pnl_per_trade",
                    "first_trade_date",
                    "last_trade_date",
                ],
            ),
            "",
            "## sn Attribution",
            "",
            to_markdown_table(
                sn_row,
                [
                    "product_vt_symbol",
                    "total_net_pnl",
                    "contribution_pct_of_portfolio_net_pnl",
                    "max_drawdown_pct_of_capital",
                    "total_trade_count",
                    "total_slippage",
                    "net_pnl_per_trade",
                    "first_trade_date",
                    "last_trade_date",
                ],
            ),
            "",
            "## sn Year Attribution",
            "",
            to_markdown_table(
                sn_year,
                ["year", "product_vt_symbol", "total_net_pnl", "total_trade_count", "total_slippage", "active_days"],
            ),
            "",
            "## Fair Slippage Stress",
            "",
            to_markdown_table(
                slippage_comparison,
                [
                    "slippage_multiplier",
                    "end_balance_stage78",
                    "end_balance_candidate",
                    "end_balance_diff",
                    "max_dd_percent_stage78",
                    "max_dd_percent_candidate",
                    "sharpe_ratio_stage78",
                    "sharpe_ratio_candidate",
                    "sharpe_ratio_diff",
                    "total_slippage_diff",
                ],
            ),
            "",
            "## Start-Year Comparison",
            "",
            to_markdown_table(
                start_year_comparison,
                [
                    "window_name",
                    "analysis_start",
                    "end_balance_stage78",
                    "end_balance_candidate",
                    "end_balance_diff",
                    "total_return_pct_diff",
                    "max_dd_percent_diff",
                    "sharpe_ratio_diff",
                    "candidate_drawdown_worse",
                    "candidate_sharpe_worse",
                ],
            ),
            "",
            "## Judgement",
            "",
            "- Passing this script does not automatically change the official strategy.",
            "- Promotion requires the candidate to show positive `sn` contribution, non-fragile slippage behavior, and acceptable start-year transfer.",
            "- Failure in any of those three checks keeps `sn` research-only.",
        ]
    )


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    stage78_daily, stage78_statistics = run_profile(
        profile_name=PROFILE_STAGE78,
        strategy_overrides=build_official_stage78_overrides(),
        save_artifacts=False,
        file_prefix=f"{OUTPUT_PREFIX}_stage78_full",
    )
    candidate_daily, candidate_statistics = run_profile(
        profile_name=PROFILE_CANDIDATE,
        strategy_overrides=build_strategy_overrides(),
        save_artifacts=True,
        file_prefix=FULL_ARTIFACT_PREFIX,
    )

    full_summary = build_full_summary(stage78_statistics, candidate_statistics)
    product_attribution, product_year_attribution = build_product_attribution()
    slippage_stress = pd.concat(
        [
            build_slippage_stress(PROFILE_STAGE78, stage78_daily),
            build_slippage_stress(PROFILE_CANDIDATE, candidate_daily),
        ],
        ignore_index=True,
    )
    slippage_comparison = build_slippage_comparison(slippage_stress)
    start_year_comparison = build_start_year_comparison()

    full_summary.to_csv(FULL_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    product_attribution.to_csv(PRODUCT_ATTRIBUTION_PATH, index=False, encoding="utf-8-sig")
    product_year_attribution.to_csv(PRODUCT_YEAR_ATTRIBUTION_PATH, index=False, encoding="utf-8-sig")
    slippage_stress.to_csv(SLIPPAGE_STRESS_PATH, index=False, encoding="utf-8-sig")
    slippage_comparison.to_csv(SLIPPAGE_COMPARISON_PATH, index=False, encoding="utf-8-sig")
    start_year_comparison.to_csv(START_YEAR_COMPARISON_PATH, index=False, encoding="utf-8-sig")
    SUMMARY_JSON_PATH.write_text(
        json.dumps(
            build_payload(
                full_summary=full_summary,
                product_attribution=product_attribution,
                product_year_attribution=product_year_attribution,
                slippage_stress=slippage_stress,
                slippage_comparison=slippage_comparison,
                start_year_comparison=start_year_comparison,
            ),
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    REPORT_PATH.write_text(
        build_report(
            full_summary=full_summary,
            product_attribution=product_attribution,
            product_year_attribution=product_year_attribution,
            slippage_comparison=slippage_comparison,
            start_year_comparison=start_year_comparison,
        ),
        encoding="utf-8",
    )

    print(slippage_comparison.to_string(index=False))
    print(start_year_comparison.to_string(index=False))
    print(f"[stage78-fu-sn-robustness] report: {REPORT_PATH}")


if __name__ == "__main__":
    main()
