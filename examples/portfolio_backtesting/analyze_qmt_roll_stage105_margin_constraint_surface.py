from __future__ import annotations

import json
import math
import re
import sys
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from main_contract_mapping import build_contract_metadata, load_product_universe_symbols
from qmt_roll_stage105_fu_sn_config import (
    STAGE105_ROLE,
    STAGE105_SIZING_EQUITY_CAP,
    STAGE105_VERSION,
    build_stage105_manifest,
    build_stage105_overrides,
)
from qmt_universe import END_DT, START_DT
from run_qmt_alignment_backtest import build_positions_df
from run_qmt_roll_backtest import run_backtest
from run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest import BASE_RISK_RATIO


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

MODEL_TAG: str = "stage109_margin_constraint_surface_v1"
OUTPUT_PREFIX: str = "qmt_roll_stage105_margin_constraint_surface"
CAPITAL: float = 400_000.0
MARGIN_WARN_BALANCE_PCT: float = 60.0
MARGIN_EXTREME_BALANCE_PCT: float = 80.0
MARGIN_REJECT_BALANCE_PCT: float = 100.0
SINGLE_CONTRACT_WARN_PCT: float = 20.0

SUMMARY_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
SUMMARY_JSON_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.json"
REPORT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


@dataclass(frozen=True)
class MarginProfile:
    profile_name: str
    max_capital_usage_ratio: float
    max_single_trade_capital_usage_ratio: float


PROFILES: tuple[MarginProfile, ...] = (
    MarginProfile("cap70_single35", 0.70, 0.35),
    MarginProfile("cap60_single30", 0.60, 0.30),
    MarginProfile("cap50_single25", 0.50, 0.25),
    MarginProfile("cap45_single20", 0.45, 0.20),
)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if pd.isna(result) or math.isinf(result):
        return default
    return result


def _product_from_contract(vt_symbol: object) -> str:
    raw = str(vt_symbol)
    if "." not in raw:
        return raw
    symbol, exchange = raw.split(".", 1)
    match = re.match(r"^([A-Za-z]+)", symbol)
    product = match.group(1) if match else symbol
    return f"{product}.{exchange}"


def _to_markdown_table(df: pd.DataFrame, columns: list[str] | None = None, max_rows: int = 30) -> str:
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


def _calculate_daily_risk(daily: pd.DataFrame, capital: float) -> pd.DataFrame:
    if daily.empty:
        return pd.DataFrame()

    frame = daily.reset_index().rename(columns={"index": "date"}).copy()
    frame["date"] = pd.to_datetime(frame["date"]).dt.normalize()
    for column in ["balance", "net_pnl", "trade_count", "slippage", "ddpercent"]:
        frame[column] = pd.to_numeric(frame.get(column, 0.0), errors="coerce").fillna(0.0)

    frame["previous_balance"] = frame["balance"].shift(1).fillna(capital).replace(0.0, np.nan)
    frame["daily_net_pnl_pct_prev_balance"] = (frame["net_pnl"] / frame["previous_balance"] * 100.0).fillna(0.0)
    frame["rolling_5d_net_pnl"] = frame["net_pnl"].rolling(5, min_periods=1).sum()
    frame["rolling_20d_net_pnl"] = frame["net_pnl"].rolling(20, min_periods=1).sum()
    frame["rolling_5d_pct_capital"] = frame["rolling_5d_net_pnl"] / capital * 100.0
    frame["rolling_20d_pct_capital"] = frame["rolling_20d_net_pnl"] / capital * 100.0
    frame["loss_day"] = (frame["net_pnl"] < 0).astype(int)
    loss_group = (frame["loss_day"] != frame["loss_day"].shift()).cumsum()
    frame["consecutive_loss_days"] = frame.groupby(loss_group)["loss_day"].cumsum() * frame["loss_day"]
    return frame


def _calculate_margin_path(
    positions: pd.DataFrame,
    daily_risk: pd.DataFrame,
    *,
    capital: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if positions.empty:
        return pd.DataFrame(), pd.DataFrame()

    frame = positions.copy()
    frame["date"] = pd.to_datetime(frame["date"]).dt.normalize()
    frame["product_vt_symbol"] = frame["vt_symbol"].map(_product_from_contract)
    for column in ["end_pos", "close_price", "net_pnl", "trade_count", "turnover", "slippage"]:
        frame[column] = pd.to_numeric(frame.get(column, 0.0), errors="coerce").fillna(0.0)

    manifest = build_stage105_manifest()
    supported_symbols = load_product_universe_symbols(manifest["product_universe_csv_path"])
    metadata = build_contract_metadata(supported_symbols=supported_symbols)
    frame["size"] = frame["vt_symbol"].map(metadata["sizes"]).fillna(1).astype(float)
    frame["margin_ratio"] = frame["vt_symbol"].map(metadata["margin_ratios"]).fillna(0.15).astype(float)
    frame["abs_end_pos"] = frame["end_pos"].abs()
    frame["position_notional"] = frame["abs_end_pos"] * frame["close_price"].clip(lower=0.0) * frame["size"]
    frame["position_margin"] = frame["position_notional"] * frame["margin_ratio"]
    frame["single_contract_margin"] = frame["close_price"].clip(lower=0.0) * frame["size"] * frame["margin_ratio"]
    frame["active_or_traded_contract"] = ((frame["abs_end_pos"] > 0) | (frame["trade_count"] > 0)).astype(int)
    frame["active_single_contract_margin"] = np.where(
        frame["active_or_traded_contract"] > 0,
        frame["single_contract_margin"],
        0.0,
    )

    product_daily = (
        frame.groupby(["date", "product_vt_symbol"], as_index=False)
        .agg(
            product_margin=("position_margin", "sum"),
            product_notional=("position_notional", "sum"),
            product_net_pnl=("net_pnl", "sum"),
            product_trade_count=("trade_count", "sum"),
            product_slippage=("slippage", "sum"),
            active_contract_count=("abs_end_pos", lambda s: int((s > 0).sum())),
            max_single_contract_margin=("active_single_contract_margin", "max"),
        )
        .sort_values(["date", "product_vt_symbol"])
        .reset_index(drop=True)
    )
    product_daily["active_product"] = (
        (product_daily["product_margin"] > 0)
        | (product_daily["product_net_pnl"].abs() > 1e-9)
        | (product_daily["product_trade_count"] > 0)
    ).astype(int)

    daily_margin = (
        product_daily.groupby("date", as_index=False)
        .agg(
            total_margin=("product_margin", "sum"),
            total_notional=("product_notional", "sum"),
            active_contract_count=("active_contract_count", "sum"),
            active_product_count=("active_product", "sum"),
            max_single_product_margin=("product_margin", "max"),
            max_single_contract_margin=("max_single_contract_margin", "max"),
        )
        .sort_values("date")
        .reset_index(drop=True)
    )
    daily_margin = daily_margin.merge(
        daily_risk[
            [
                "date",
                "balance",
                "net_pnl",
                "daily_net_pnl_pct_prev_balance",
                "rolling_5d_pct_capital",
                "rolling_20d_pct_capital",
                "ddpercent",
                "consecutive_loss_days",
            ]
        ],
        on="date",
        how="left",
    )
    daily_margin["balance"] = pd.to_numeric(daily_margin["balance"], errors="coerce").ffill().fillna(capital)
    daily_margin["total_margin_to_balance_pct"] = (
        daily_margin["total_margin"] / daily_margin["balance"].replace(0.0, np.nan) * 100.0
    ).fillna(0.0)
    daily_margin["total_margin_to_initial_capital_pct"] = daily_margin["total_margin"] / capital * 100.0
    daily_margin["total_notional_to_balance_pct"] = (
        daily_margin["total_notional"] / daily_margin["balance"].replace(0.0, np.nan) * 100.0
    ).fillna(0.0)
    daily_margin["max_single_product_margin_to_balance_pct"] = (
        daily_margin["max_single_product_margin"] / daily_margin["balance"].replace(0.0, np.nan) * 100.0
    ).fillna(0.0)
    daily_margin["max_single_contract_margin_pct_capital"] = (
        daily_margin["max_single_contract_margin"] / capital * 100.0
    ).fillna(0.0)
    return daily_margin, product_daily


def _run_profile(profile: MarginProfile) -> tuple[pd.DataFrame, dict[str, Any], pd.DataFrame, pd.DataFrame]:
    overrides = build_stage105_overrides()
    overrides.update(
        {
            "max_capital_usage_ratio": profile.max_capital_usage_ratio,
            "max_single_trade_capital_usage_ratio": profile.max_single_trade_capital_usage_ratio,
        }
    )

    print(
        f"[stage105-margin-surface] run {profile.profile_name}: "
        f"cap={profile.max_capital_usage_ratio:.2f}, single={profile.max_single_trade_capital_usage_ratio:.2f}"
    )
    log_buffer = StringIO()
    try:
        with redirect_stdout(log_buffer), redirect_stderr(log_buffer):
            engine, analysis_df, statistics = run_backtest(
                risk_ratio=BASE_RISK_RATIO,
                strategy_overrides=overrides,
                analysis_start=START_DT,
                analysis_end=END_DT,
                capital=CAPITAL,
                save_artifacts=False,
                include_start_year_sweep=False,
                file_prefix=f"{OUTPUT_PREFIX}_{profile.profile_name}",
                chart_title=f"QMT Roll Stage105 Margin Constraint {profile.profile_name}",
            )
    except Exception:
        sys.stderr.write(log_buffer.getvalue())
        raise

    daily = analysis_df.copy() if analysis_df is not None else pd.DataFrame()
    if not daily.empty:
        daily.sort_index(inplace=True)
    positions = build_positions_df(engine)
    return daily, statistics, positions, pd.DataFrame(log_buffer.getvalue().splitlines(), columns=["log_line"])


def _summarize_profile(
    profile: MarginProfile,
    statistics: dict[str, Any],
    daily_risk: pd.DataFrame,
    daily_margin: pd.DataFrame,
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
    max_single_contract_pct = _safe_float(max_single_contract.get("max_single_contract_margin_pct_capital"))
    reject_days = int((daily_margin["total_margin_to_balance_pct"] > MARGIN_REJECT_BALANCE_PCT).sum()) if not daily_margin.empty else 0
    extreme_days = int((daily_margin["total_margin_to_balance_pct"] > MARGIN_EXTREME_BALANCE_PCT).sum()) if not daily_margin.empty else 0
    warn_days = int((daily_margin["total_margin_to_balance_pct"] > MARGIN_WARN_BALANCE_PCT).sum()) if not daily_margin.empty else 0

    if max_margin_to_balance <= MARGIN_EXTREME_BALANCE_PCT and reject_days == 0:
        deployment_label = "pass_margin_gate"
    elif reject_days == 0 and max_margin_to_balance <= MARGIN_REJECT_BALANCE_PCT:
        deployment_label = "watch_margin_gate"
    else:
        deployment_label = "reject_margin_gate"

    if max_single_contract_pct > SINGLE_CONTRACT_WARN_PCT:
        deployment_label = f"{deployment_label}_single_contract_coarse"

    return {
        "model_tag": MODEL_TAG,
        "version": STAGE105_VERSION,
        "role": STAGE105_ROLE,
        "profile_name": profile.profile_name,
        "capital": CAPITAL,
        "sizing_equity_cap": STAGE105_SIZING_EQUITY_CAP,
        "base_risk_ratio": BASE_RISK_RATIO,
        "max_capital_usage_ratio": profile.max_capital_usage_ratio,
        "max_single_trade_capital_usage_ratio": profile.max_single_trade_capital_usage_ratio,
        "end_balance": _safe_float(statistics.get("end_balance")),
        "total_return_pct": _safe_float(statistics.get("total_return")),
        "annual_return_pct": _safe_float(statistics.get("annual_return")),
        "max_dd_percent": _safe_float(statistics.get("max_ddpercent")),
        "sharpe_ratio": _safe_float(statistics.get("sharpe_ratio")),
        "return_drawdown_ratio": _safe_float(statistics.get("return_drawdown_ratio")),
        "total_slippage": _safe_float(statistics.get("total_slippage")),
        "total_trade_count": _safe_float(statistics.get("total_trade_count")),
        "worst_daily_net_pnl": _safe_float(worst_daily.get("net_pnl")),
        "worst_daily_date": str(worst_daily.get("date", ""))[:10],
        "worst_daily_pct_prev_balance": _safe_float(worst_daily.get("daily_net_pnl_pct_prev_balance")),
        "worst_5d_pct_capital": _safe_float(worst_5d.get("rolling_5d_pct_capital")),
        "worst_5d_end_date": str(worst_5d.get("date", ""))[:10],
        "worst_20d_pct_capital": _safe_float(worst_20d.get("rolling_20d_pct_capital")),
        "worst_20d_end_date": str(worst_20d.get("date", ""))[:10],
        "max_consecutive_loss_days": int(daily_risk["consecutive_loss_days"].max()) if not daily_risk.empty else 0,
        "max_total_margin": _safe_float(max_margin.get("total_margin")),
        "max_total_margin_date": str(max_margin.get("date", ""))[:10],
        "max_total_margin_to_balance_pct": max_margin_to_balance,
        "max_total_margin_to_initial_capital_pct": _safe_float(max_margin.get("total_margin_to_initial_capital_pct")),
        "max_total_notional_to_balance_pct": _safe_float(max_margin.get("total_notional_to_balance_pct")),
        "warn_margin_days_gt_60pct": warn_days,
        "extreme_margin_days_gt_80pct": extreme_days,
        "reject_margin_days_gt_100pct": reject_days,
        "max_active_product_count": int(daily_margin["active_product_count"].max()) if not daily_margin.empty else 0,
        "max_active_contract_count": int(daily_margin["active_contract_count"].max()) if not daily_margin.empty else 0,
        "max_single_contract_margin_pct_capital": max_single_contract_pct,
        "deployment_label": deployment_label,
    }


def _build_report(summary_df: pd.DataFrame) -> str:
    pass_df = summary_df[summary_df["deployment_label"].astype(str).str.startswith("pass_margin_gate")].copy()
    if pass_df.empty:
        best_name = ""
        judgement = (
            "没有档位通过 80% 保证金占权益硬门槛，现有静态资金约束不足以把 Stage105 变成 400k 可部署正式版。"
        )
    else:
        pass_df.sort_values(["total_return_pct", "sharpe_ratio"], ascending=[False, False], inplace=True)
        best_name = str(pass_df.iloc[0]["profile_name"])
        judgement = (
            f"`{best_name}` 是本轮最优低自由度部署候选：它通过 80% 保证金门槛，且保留了最高收益。"
        )

    columns = [
        "profile_name",
        "max_capital_usage_ratio",
        "max_single_trade_capital_usage_ratio",
        "end_balance",
        "total_return_pct",
        "max_dd_percent",
        "sharpe_ratio",
        "total_trade_count",
        "max_total_margin_to_balance_pct",
        "warn_margin_days_gt_60pct",
        "extreme_margin_days_gt_80pct",
        "reject_margin_days_gt_100pct",
        "worst_20d_pct_capital",
        "deployment_label",
    ]

    return "\n".join(
        [
            "# Stage105 Margin Constraint Surface",
            "",
            "## Boundary",
            "",
            "- This experiment does not change the Stage105 trading logic.",
            "- Only two existing capital-budget parameters are scanned.",
            "- Capital is fixed at `400,000`; sizing equity cap remains Stage105 default.",
            "- The primary acceptance condition is max margin / balance <= 80% with no days above 100%.",
            "",
            "## Summary",
            "",
            _to_markdown_table(summary_df.sort_values("max_capital_usage_ratio", ascending=False), columns),
            "",
            "## Judgement",
            "",
            f"- {judgement}",
            "- If no profile passes, the next step should be dynamic margin de-risking or accepting that Stage105 is not a 400k formal strategy.",
            "- If a profile passes, it should still be tested by start-year and quarterly walk-forward before formal promotion.",
        ]
    )


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    summaries: list[dict[str, Any]] = []

    for profile in PROFILES:
        daily, statistics, positions, run_log = _run_profile(profile)
        daily_risk = _calculate_daily_risk(daily, CAPITAL)
        daily_margin, product_daily = _calculate_margin_path(positions, daily_risk, capital=CAPITAL)

        profile_prefix = f"{OUTPUT_PREFIX}_{profile.profile_name}_{MODEL_TAG}"
        daily_margin.to_csv(OUTPUT_DIR / f"{profile_prefix}_daily_margin.csv", index=False, encoding="utf-8-sig")
        product_daily.to_csv(OUTPUT_DIR / f"{profile_prefix}_product_daily.csv", index=False, encoding="utf-8-sig")
        positions.to_csv(
            OUTPUT_DIR / f"{profile_prefix}_position_changes_2020_2026_04.csv",
            index=False,
            encoding="utf-8-sig",
        )
        run_log.to_csv(OUTPUT_DIR / f"{profile_prefix}_run_log.csv", index=False, encoding="utf-8-sig")

        summary = _summarize_profile(profile, statistics, daily_risk, daily_margin)
        summaries.append(summary)
        print(
            f"[stage105-margin-surface] {profile.profile_name}: "
            f"return={summary['total_return_pct']:.4f}%, dd={summary['max_dd_percent']:.4f}%, "
            f"max_margin/balance={summary['max_total_margin_to_balance_pct']:.4f}%, "
            f"label={summary['deployment_label']}"
        )

    summary_df = pd.DataFrame(summaries)
    summary_df.sort_values(["max_capital_usage_ratio", "max_single_trade_capital_usage_ratio"], ascending=False, inplace=True)
    summary_df.to_csv(SUMMARY_CSV_PATH, index=False, encoding="utf-8-sig")
    SUMMARY_JSON_PATH.write_text(
        json.dumps(
            {
                "model_tag": MODEL_TAG,
                "version": STAGE105_VERSION,
                "capital": CAPITAL,
                "profiles": summaries,
                "outputs": {
                    "summary_csv": str(SUMMARY_CSV_PATH),
                    "summary_json": str(SUMMARY_JSON_PATH),
                    "report": str(REPORT_PATH),
                },
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    REPORT_PATH.write_text(_build_report(summary_df), encoding="utf-8")
    print(json.dumps(summaries, ensure_ascii=False, indent=2, default=str))
    print(f"[stage105-margin-surface] report: {REPORT_PATH}")


if __name__ == "__main__":
    main()
