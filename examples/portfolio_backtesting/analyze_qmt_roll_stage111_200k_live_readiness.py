from __future__ import annotations

import json
import math
import sys
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from typing import Any

import pandas as pd

from analyze_qmt_roll_stage105_margin_constraint_surface import (
    MARGIN_EXTREME_BALANCE_PCT,
    MARGIN_REJECT_BALANCE_PCT,
    MARGIN_WARN_BALANCE_PCT,
    _calculate_daily_risk,
    _calculate_margin_path,
    _safe_float,
    _to_markdown_table,
)
from qmt_roll_stage111_400k_margin_safe_config import (
    STAGE111_MARGIN_PROFILE,
    STAGE111_ROLE,
    STAGE111_VERSION,
    build_stage111_overrides,
)
from qmt_universe import END_DT, START_DT
from run_qmt_alignment_backtest import build_positions_df
from run_qmt_roll_backtest import run_backtest
from run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest import BASE_RISK_RATIO


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

MODEL_TAG: str = "stage112_stage111_200k_live_readiness_v1"
OUTPUT_PREFIX: str = "qmt_roll_stage111_200k_live_readiness"
CAPITAL: float = 200_000.0
SINGLE_CONTRACT_WARN_PCT: float = 20.0
SINGLE_CONTRACT_REJECT_PCT: float = 25.0
WORST_5D_REJECT_PCT: float = -50.0
WORST_20D_REJECT_PCT: float = -70.0

DAILY_MARGIN_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_margin_{MODEL_TAG}.csv"
PRODUCT_DAILY_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_daily_{MODEL_TAG}.csv"
POSITION_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_position_changes_2020_2026_04_{MODEL_TAG}.csv"
SUMMARY_JSON_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.json"
REPORT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


def _run_stage111_200k_backtest() -> tuple[pd.DataFrame, dict[str, Any], pd.DataFrame]:
    print(f"[stage111-200k-readiness] run full: {START_DT.date()} -> {END_DT.date()}")
    log_buffer = StringIO()
    try:
        with redirect_stdout(log_buffer), redirect_stderr(log_buffer):
            engine, analysis_df, statistics = run_backtest(
                risk_ratio=BASE_RISK_RATIO,
                strategy_overrides=build_stage111_overrides(),
                analysis_start=START_DT,
                analysis_end=END_DT,
                capital=CAPITAL,
                save_artifacts=False,
                include_start_year_sweep=False,
                file_prefix=OUTPUT_PREFIX,
                chart_title="QMT Roll Stage111 200k Live Readiness",
            )
    except Exception:
        sys.stderr.write(log_buffer.getvalue())
        raise

    daily = analysis_df.copy() if analysis_df is not None else pd.DataFrame()
    if not daily.empty:
        daily.sort_index(inplace=True)
    positions = build_positions_df(engine)
    return daily, statistics, positions


def _product_exposure(product_daily: pd.DataFrame, daily_margin: pd.DataFrame) -> pd.DataFrame:
    if product_daily.empty:
        return pd.DataFrame()
    balance = daily_margin[["date", "balance"]].copy() if not daily_margin.empty else pd.DataFrame()
    frame = product_daily.merge(balance, on="date", how="left")
    frame["balance"] = pd.to_numeric(frame["balance"], errors="coerce").ffill().fillna(CAPITAL)
    frame["product_margin_to_balance_pct"] = (
        frame["product_margin"] / frame["balance"].replace(0.0, pd.NA) * 100.0
    ).fillna(0.0)
    return (
        frame.groupby("product_vt_symbol", as_index=False)
        .agg(
            total_net_pnl=("product_net_pnl", "sum"),
            total_trade_count=("product_trade_count", "sum"),
            total_slippage=("product_slippage", "sum"),
            active_days=("active_product", "sum"),
            max_margin=("product_margin", "max"),
            max_margin_to_balance_pct=("product_margin_to_balance_pct", "max"),
            max_active_contract_count=("active_contract_count", "max"),
            max_single_contract_margin=("max_single_contract_margin", "max"),
        )
        .sort_values(["max_margin_to_balance_pct", "total_net_pnl"], ascending=[False, False])
        .reset_index(drop=True)
    )


def _build_summary(
    statistics: dict[str, Any],
    daily_risk: pd.DataFrame,
    daily_margin: pd.DataFrame,
    product_exposure: pd.DataFrame,
) -> dict[str, Any]:
    worst_daily = daily_risk.loc[daily_risk["net_pnl"].idxmin()].to_dict() if not daily_risk.empty else {}
    worst_5d = daily_risk.loc[daily_risk["rolling_5d_net_pnl"].idxmin()].to_dict() if not daily_risk.empty else {}
    worst_20d = daily_risk.loc[daily_risk["rolling_20d_net_pnl"].idxmin()].to_dict() if not daily_risk.empty else {}
    max_margin = (
        daily_margin.loc[daily_margin["total_margin_to_balance_pct"].idxmax()].to_dict()
        if not daily_margin.empty
        else {}
    )
    max_single_contract = (
        daily_margin.loc[daily_margin["max_single_contract_margin_pct_capital"].idxmax()].to_dict()
        if not daily_margin.empty
        else {}
    )

    max_margin_to_balance = _safe_float(max_margin.get("total_margin_to_balance_pct"))
    reject_margin_days = int((daily_margin["total_margin_to_balance_pct"] > MARGIN_REJECT_BALANCE_PCT).sum()) if not daily_margin.empty else 0
    extreme_margin_days = int((daily_margin["total_margin_to_balance_pct"] > MARGIN_EXTREME_BALANCE_PCT).sum()) if not daily_margin.empty else 0
    warn_margin_days = int((daily_margin["total_margin_to_balance_pct"] > MARGIN_WARN_BALANCE_PCT).sum()) if not daily_margin.empty else 0
    max_single_contract_pct = _safe_float(max_single_contract.get("max_single_contract_margin_pct_capital"))
    worst_5d_pct = _safe_float(worst_5d.get("rolling_5d_pct_capital"))
    worst_20d_pct = _safe_float(worst_20d.get("rolling_20d_pct_capital"))

    hard_reasons: list[str] = []
    warn_reasons: list[str] = []
    if reject_margin_days > 0 or max_margin_to_balance > MARGIN_REJECT_BALANCE_PCT:
        hard_reasons.append("margin_to_balance_gt_100pct")
    elif extreme_margin_days > 0 or max_margin_to_balance > MARGIN_EXTREME_BALANCE_PCT:
        hard_reasons.append("margin_to_balance_gt_80pct")
    if max_single_contract_pct > SINGLE_CONTRACT_REJECT_PCT:
        hard_reasons.append("single_contract_margin_too_coarse")
    elif max_single_contract_pct > SINGLE_CONTRACT_WARN_PCT:
        warn_reasons.append("single_contract_margin_warn")
    if worst_5d_pct < WORST_5D_REJECT_PCT:
        hard_reasons.append("worst_5d_loss_too_large")
    if worst_20d_pct < WORST_20D_REJECT_PCT:
        hard_reasons.append("worst_20d_loss_too_large")

    if hard_reasons:
        decision = "REJECT_200K_AS_IS"
    elif warn_reasons:
        decision = "WATCH_200K"
    else:
        decision = "PASS_200K_FULL_WINDOW"

    return {
        "model_tag": MODEL_TAG,
        "base_version": STAGE111_VERSION,
        "base_role": STAGE111_ROLE,
        "capital": CAPITAL,
        "base_risk_ratio": BASE_RISK_RATIO,
        "margin_profile": STAGE111_MARGIN_PROFILE,
        "statistics": {
            "end_balance": _safe_float(statistics.get("end_balance")),
            "total_return_pct": _safe_float(statistics.get("total_return")),
            "annual_return_pct": _safe_float(statistics.get("annual_return")),
            "max_dd_percent": _safe_float(statistics.get("max_ddpercent")),
            "sharpe_ratio": _safe_float(statistics.get("sharpe_ratio")),
            "return_drawdown_ratio": _safe_float(statistics.get("return_drawdown_ratio")),
            "total_slippage": _safe_float(statistics.get("total_slippage")),
            "total_trade_count": _safe_float(statistics.get("total_trade_count")),
            "win_ratio_pct": _safe_float(statistics.get("win_ratio")),
        },
        "path_risk": {
            "worst_daily_net_pnl": _safe_float(worst_daily.get("net_pnl")),
            "worst_daily_date": str(worst_daily.get("date", ""))[:10],
            "worst_daily_pct_prev_balance": _safe_float(worst_daily.get("daily_net_pnl_pct_prev_balance")),
            "worst_5d_net_pnl": _safe_float(worst_5d.get("rolling_5d_net_pnl")),
            "worst_5d_end_date": str(worst_5d.get("date", ""))[:10],
            "worst_5d_pct_capital": worst_5d_pct,
            "worst_20d_net_pnl": _safe_float(worst_20d.get("rolling_20d_net_pnl")),
            "worst_20d_end_date": str(worst_20d.get("date", ""))[:10],
            "worst_20d_pct_capital": worst_20d_pct,
            "max_consecutive_loss_days": int(daily_risk["consecutive_loss_days"].max()) if not daily_risk.empty else 0,
        },
        "margin_risk": {
            "max_total_margin": _safe_float(max_margin.get("total_margin")),
            "max_total_margin_date": str(max_margin.get("date", ""))[:10],
            "max_total_margin_to_balance_pct": max_margin_to_balance,
            "max_total_margin_to_initial_capital_pct": _safe_float(max_margin.get("total_margin_to_initial_capital_pct")),
            "max_total_notional_to_balance_pct": _safe_float(max_margin.get("total_notional_to_balance_pct")),
            "warn_margin_days_gt_60pct": warn_margin_days,
            "extreme_margin_days_gt_80pct": extreme_margin_days,
            "reject_margin_days_gt_100pct": reject_margin_days,
            "max_active_product_count": int(daily_margin["active_product_count"].max()) if not daily_margin.empty else 0,
            "max_active_contract_count": int(daily_margin["active_contract_count"].max()) if not daily_margin.empty else 0,
            "max_single_contract_margin_pct_capital": max_single_contract_pct,
            "max_single_contract_margin": _safe_float(max_single_contract.get("max_single_contract_margin")),
            "max_single_contract_margin_date": str(max_single_contract.get("date", ""))[:10],
        },
        "decision": {
            "label": decision,
            "hard_reasons": hard_reasons,
            "warn_reasons": warn_reasons,
        },
        "top_product_exposure": product_exposure.head(10).to_dict(orient="records"),
        "outputs": {
            "daily_margin": str(DAILY_MARGIN_PATH),
            "product_daily": str(PRODUCT_DAILY_PATH),
            "positions": str(POSITION_PATH),
            "summary_json": str(SUMMARY_JSON_PATH),
            "report": str(REPORT_PATH),
        },
    }


def _build_report(summary: dict[str, Any], product_exposure: pd.DataFrame) -> str:
    stats = summary["statistics"]
    path = summary["path_risk"]
    margin = summary["margin_risk"]
    decision = summary["decision"]
    return "\n".join(
        [
            "# Stage111 200k Live Readiness",
            "",
            "## Boundary",
            "",
            "- Stage111 trading logic and capital constraints are unchanged.",
            "- Only account capital is changed from `400,000` to `200,000`.",
            "- This full-window audit is a feasibility check, not a promotion.",
            "",
            "## Result",
            "",
            f"- End balance: `{stats['end_balance']:,.0f}`",
            f"- Total return: `{stats['total_return_pct']:.4f}%`",
            f"- Max drawdown: `{stats['max_dd_percent']:.4f}%`",
            f"- Sharpe: `{stats['sharpe_ratio']:.4f}`",
            f"- Total slippage: `{stats['total_slippage']:,.0f}`",
            f"- Total trade count: `{stats['total_trade_count']:,.0f}`",
            f"- Win ratio: `{stats['win_ratio_pct']:.4f}%`",
            "",
            "## Path Risk",
            "",
            f"- Worst daily net pnl: `{path['worst_daily_net_pnl']:,.0f}` on `{path['worst_daily_date']}` "
            f"(`{path['worst_daily_pct_prev_balance']:.4f}%` previous balance)",
            f"- Worst 5d net pnl: `{path['worst_5d_net_pnl']:,.0f}` ending `{path['worst_5d_end_date']}` "
            f"(`{path['worst_5d_pct_capital']:.4f}%` initial capital)",
            f"- Worst 20d net pnl: `{path['worst_20d_net_pnl']:,.0f}` ending `{path['worst_20d_end_date']}` "
            f"(`{path['worst_20d_pct_capital']:.4f}%` initial capital)",
            f"- Max consecutive loss days: `{path['max_consecutive_loss_days']}`",
            "",
            "## Margin Risk",
            "",
            f"- Max margin / balance: `{margin['max_total_margin_to_balance_pct']:.4f}%`",
            f"- Max margin / initial capital: `{margin['max_total_margin_to_initial_capital_pct']:.4f}%`",
            f"- Margin days >60% balance: `{margin['warn_margin_days_gt_60pct']}`",
            f"- Margin days >80% balance: `{margin['extreme_margin_days_gt_80pct']}`",
            f"- Margin days >100% balance: `{margin['reject_margin_days_gt_100pct']}`",
            f"- Max single-contract margin / initial capital: `{margin['max_single_contract_margin_pct_capital']:.4f}%`",
            "",
            "## Product Exposure Top 10",
            "",
            _to_markdown_table(
                product_exposure,
                [
                    "product_vt_symbol",
                    "total_net_pnl",
                    "total_trade_count",
                    "active_days",
                    "max_margin",
                    "max_margin_to_balance_pct",
                    "max_active_contract_count",
                    "max_single_contract_margin",
                ],
                max_rows=10,
            ),
            "",
            "## Decision",
            "",
            f"- Label: `{decision['label']}`",
            f"- Hard reasons: `{decision['hard_reasons']}`",
            f"- Warn reasons: `{decision['warn_reasons']}`",
            "- If rejected, do not run quarterly promotion until the hard blocker is solved.",
        ]
    )


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    daily, statistics, positions = _run_stage111_200k_backtest()
    daily_risk = _calculate_daily_risk(daily, CAPITAL)
    daily_margin, product_daily = _calculate_margin_path(positions, daily_risk, capital=CAPITAL)
    product_exposure = _product_exposure(product_daily, daily_margin)
    summary = _build_summary(statistics, daily_risk, daily_margin, product_exposure)

    daily_margin.to_csv(DAILY_MARGIN_PATH, index=False, encoding="utf-8-sig")
    product_daily.to_csv(PRODUCT_DAILY_PATH, index=False, encoding="utf-8-sig")
    positions.to_csv(POSITION_PATH, index=False, encoding="utf-8-sig")
    SUMMARY_JSON_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    REPORT_PATH.write_text(_build_report(summary, product_exposure), encoding="utf-8")

    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    print(f"[stage111-200k-readiness] report: {REPORT_PATH}")


if __name__ == "__main__":
    main()
