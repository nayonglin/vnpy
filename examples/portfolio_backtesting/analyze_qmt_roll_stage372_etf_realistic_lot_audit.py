from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
ALPHA_RESULTS_DIR = PROJECT_DIR.parent / "alpha_research" / "native_results"

MODEL_TAG = "stage372_etf_realistic_lot_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage372_etf_realistic_lot_audit"

C3_DAILY_PATH = (
    OUTPUT_DIR
    / "qmt_roll_stage336_c3_cash_reserve_multiperiod_daily_stage336_c3_cash_reserve_multiperiod_v1.csv"
)
ETF_SIGNAL_DAILY_PATH = (
    ALPHA_RESULTS_DIR
    / "stock_range_reversion_broad_etf_signal_sleeve_2018_2026"
    / "stock_range_reversion_broad_etf_signal_sleeve_v1_daily.csv"
)
ETF_TARGETS_PATH = (
    ALPHA_RESULTS_DIR
    / "stock_range_reversion_broad_etf_signal_sleeve_2018_2026"
    / "stock_range_reversion_broad_etf_signal_sleeve_v1_targets.csv"
)
ETF_DAILY_PATH = (
    ALPHA_RESULTS_DIR
    / "stock_range_reversion_broad_etf_data_2018_2026"
    / "stock_range_reversion_broad_etf_data_v1_selected_daily.csv"
)

BASE_PROFILE = "c3_active100_cash0"
BASE_WINDOW = "start_2020"
INITIAL_CAPITAL = 500_000.0
ETF_LEG_CAPITAL = 25_000.0
LOT_SIZE = 100
PASS_MAX_DD = -30.0
PASS_RETURN_RETENTION = 80.0

CANDIDATE_PORTFOLIO = (
    "primary_core_liquid_p10_50000__connors_rsi2_ma200__sleeve10__cap50__cost20bp"
)


@dataclass(frozen=True)
class FeeProfile:
    name: str
    label: str
    one_way_bps: float
    min_fee: float


FEE_PROFILES = (
    FeeProfile("lot100_fee10bp_min0", "100份整手+单向10bp+无最低佣金", 10.0, 0.0),
    FeeProfile("lot100_fee10bp_min5", "100份整手+单向10bp+5元最低佣金", 10.0, 5.0),
    FeeProfile("lot100_fee20bp_min5", "100份整手+单向20bp+5元最低佣金压力", 20.0, 5.0),
)
MAIN_FEE_PROFILE = "lot100_fee10bp_min5"


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(result) or math.isinf(result):
        return default
    return result


def _max_drawdown(nav: pd.Series) -> float:
    if nav.empty:
        return 0.0
    return float((nav / nav.cummax() - 1.0).min())


def _ulcer(nav: pd.Series) -> float:
    if nav.empty:
        return 0.0
    dd = (nav / nav.cummax() - 1.0) * 100.0
    return float(np.sqrt(np.mean(np.square(np.minimum(dd, 0.0)))))


def _longest_underwater(nav: pd.Series) -> int:
    longest = 0
    current = 0
    for value in nav / nav.cummax() - 1.0:
        if value < -1e-12:
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return int(longest)


def _annualized_sharpe(daily_ret: pd.Series) -> float:
    daily_ret = daily_ret.dropna().astype(float)
    if len(daily_ret) < 2:
        return 0.0
    std = float(daily_ret.std(ddof=1))
    if std <= 0.0:
        return 0.0
    return float(daily_ret.mean() / std * math.sqrt(252.0))


def _stats(name: str, label: str, daily_ret: pd.Series) -> dict[str, Any]:
    daily_ret = daily_ret.fillna(0.0).astype(float)
    nav = (1.0 + daily_ret).cumprod()
    if nav.empty:
        return {
            "variant": name,
            "label": label,
            "days": 0,
            "total_return_pct": 0.0,
            "max_dd_percent": 0.0,
            "sharpe": 0.0,
            "ulcer": 0.0,
            "longest_underwater_days": 0,
        }
    return {
        "variant": name,
        "label": label,
        "days": int(len(daily_ret)),
        "start_date": str(daily_ret.index.min().date()),
        "end_date": str(daily_ret.index.max().date()),
        "end_nav": float(nav.iloc[-1]),
        "total_return_pct": float((nav.iloc[-1] - 1.0) * 100.0),
        "max_dd_percent": _max_drawdown(nav) * 100.0,
        "sharpe": _annualized_sharpe(daily_ret),
        "ulcer": _ulcer(nav),
        "longest_underwater_days": _longest_underwater(nav),
        "positive_day_rate": float((daily_ret > 0.0).mean()),
    }


def _fee(amount: float, profile: FeeProfile) -> float:
    if amount <= 0.0:
        return 0.0
    return max(profile.min_fee, amount * profile.one_way_bps / 10_000.0)


def _load_c3_daily_ret() -> pd.Series:
    df = pd.read_csv(C3_DAILY_PATH)
    df = df[(df["profile"].eq(BASE_PROFILE)) & (df["window_name"].eq(BASE_WINDOW))].copy()
    if df.empty:
        raise ValueError(f"missing {BASE_PROFILE}/{BASE_WINDOW} in {C3_DAILY_PATH}")
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df[df["date"].notna()].sort_values("date")
    balance = pd.to_numeric(df["balance"], errors="coerce").ffill()
    ret = balance.pct_change()
    ret.iloc[0] = balance.iloc[0] / INITIAL_CAPITAL - 1.0
    ret.index = pd.DatetimeIndex(df["date"])
    return ret.astype(float)


def _load_paper_etf_ret() -> pd.Series:
    df = pd.read_csv(ETF_SIGNAL_DAILY_PATH)
    df = df[df["portfolio"].eq(CANDIDATE_PORTFOLIO)].copy()
    if df.empty:
        raise ValueError(f"missing ETF candidate {CANDIDATE_PORTFOLIO}")
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df[df["date"].notna()].sort_values("date")
    ret = pd.to_numeric(df["strategy_daily_ret"], errors="coerce").fillna(0.0)
    ret.index = pd.DatetimeIndex(df["date"])
    return ret.astype(float)


def _load_targets() -> pd.DataFrame:
    df = pd.read_csv(ETF_TARGETS_PATH)
    df = df[df["portfolio"].eq(CANDIDATE_PORTFOLIO)].copy()
    if df.empty:
        raise ValueError(f"missing target rows for {CANDIDATE_PORTFOLIO}")
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["target_weight"] = pd.to_numeric(df["target_weight"], errors="coerce").fillna(0.0)
    return df[df["date"].notna()].sort_values(["date", "ts_code"]).copy()


def _load_price_panel(codes: list[str]) -> pd.DataFrame:
    df = pd.read_csv(ETF_DAILY_PATH)
    df = df[df["ts_code"].isin(codes)].copy()
    if df.empty:
        raise ValueError("missing selected ETF prices for candidate codes")
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["close"] = pd.to_numeric(df["close"], errors="coerce")
    df = df[df["date"].notna() & df["close"].gt(0.0)]
    panel = df.pivot_table(index="date", columns="ts_code", values="close", aggfunc="last")
    return panel.sort_index().ffill()


def _target_map_for_signal_dates(targets: pd.DataFrame) -> dict[pd.Timestamp, dict[str, float]]:
    result: dict[pd.Timestamp, dict[str, float]] = {}
    for date, group in targets.groupby("date"):
        weights = (
            group.groupby("ts_code")["target_weight"]
            .sum()
            .loc[lambda s: s > 0.0]
            .to_dict()
        )
        result[pd.Timestamp(date)] = {str(k): float(v) for k, v in weights.items()}
    return result


def _desired_shares(
    target_weights: dict[str, float],
    prices: pd.Series,
    equity: float,
) -> tuple[dict[str, int], list[dict[str, Any]]]:
    desired: dict[str, int] = {}
    rejects: list[dict[str, Any]] = []
    for code, weight in target_weights.items():
        price = _safe_float(prices.get(code), np.nan)
        target_value = equity * weight
        if not np.isfinite(price) or price <= 0.0:
            rejects.append(
                {
                    "ts_code": code,
                    "reason": "missing_price",
                    "target_weight": weight,
                    "target_value": target_value,
                    "target_shares": 0,
                }
            )
            desired[code] = 0
            continue
        lots = int(math.floor(target_value / (price * LOT_SIZE)))
        shares = max(0, lots * LOT_SIZE)
        if shares <= 0 and target_value > 0.0:
            rejects.append(
                {
                    "ts_code": code,
                    "reason": "below_one_lot",
                    "target_weight": weight,
                    "target_value": target_value,
                    "target_shares": 0,
                }
            )
        desired[code] = shares
    return desired, rejects


def _simulate_etf_lot_execution(
    targets: pd.DataFrame,
    prices: pd.DataFrame,
    profile: FeeProfile,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    target_by_signal = _target_map_for_signal_dates(targets)
    dates = list(pd.DatetimeIndex(prices.index).sort_values())
    if len(dates) < 2:
        raise ValueError("not enough ETF price dates")

    schedule: dict[pd.Timestamp, dict[str, float]] = {}
    for idx, signal_date in enumerate(dates[:-1]):
        exec_date = dates[idx + 1]
        schedule[exec_date] = target_by_signal.get(pd.Timestamp(signal_date), {})

    cash = ETF_LEG_CAPITAL
    holdings: dict[str, int] = {}
    prev_equity = ETF_LEG_CAPITAL
    daily_rows: list[dict[str, Any]] = []
    trade_rows: list[dict[str, Any]] = []
    reject_rows: list[dict[str, Any]] = []

    for date in dates:
        close = prices.loc[date]
        value_before = sum(
            shares * _safe_float(close.get(code), 0.0)
            for code, shares in holdings.items()
            if shares
        )
        equity_before = cash + value_before
        target_weights = schedule.get(pd.Timestamp(date))
        is_rebalance = target_weights is not None
        turnover = 0.0
        fees = 0.0
        order_count = 0
        trade_count = 0
        target_count = 0
        unfilled_count = 0
        desired: dict[str, int] = {}

        if is_rebalance:
            target_weights = target_weights or {}
            target_count = len(target_weights)
            desired, rejects = _desired_shares(target_weights, close, equity_before)
            for item in rejects:
                item.update({"date": date, "fee_profile": profile.name})
                reject_rows.append(item)

            all_codes = sorted(set(holdings) | set(desired))

            for code in all_codes:
                current = int(holdings.get(code, 0))
                target = int(desired.get(code, 0))
                if current <= target:
                    continue
                price = _safe_float(close.get(code), np.nan)
                if not np.isfinite(price) or price <= 0.0:
                    continue
                shares = current - target
                amount = shares * price
                trade_fee = _fee(amount, profile)
                cash += amount - trade_fee
                holdings[code] = target
                turnover += amount
                fees += trade_fee
                order_count += 1
                trade_count += 1
                trade_rows.append(
                    {
                        "date": date,
                        "fee_profile": profile.name,
                        "ts_code": code,
                        "side": "sell",
                        "price": price,
                        "shares": shares,
                        "amount": amount,
                        "fee": trade_fee,
                        "cash_after": cash,
                    }
                )

            buy_codes = sorted(
                [code for code in all_codes if int(desired.get(code, 0)) > int(holdings.get(code, 0))],
                key=lambda c: (-target_weights.get(c, 0.0), c),
            )
            for code in buy_codes:
                current = int(holdings.get(code, 0))
                target = int(desired.get(code, 0))
                price = _safe_float(close.get(code), np.nan)
                if not np.isfinite(price) or price <= 0.0:
                    continue
                shares = target - current
                while shares > 0:
                    amount = shares * price
                    trade_fee = _fee(amount, profile)
                    if amount + trade_fee <= cash + 1e-9:
                        break
                    shares -= LOT_SIZE
                if shares <= 0:
                    unfilled_count += 1
                    reject_rows.append(
                        {
                            "date": date,
                            "fee_profile": profile.name,
                            "ts_code": code,
                            "reason": "cash_after_lot_and_fee",
                            "target_weight": target_weights.get(code, 0.0),
                            "target_value": equity_before * target_weights.get(code, 0.0),
                            "target_shares": target,
                        }
                    )
                    continue
                amount = shares * price
                trade_fee = _fee(amount, profile)
                cash -= amount + trade_fee
                holdings[code] = current + shares
                turnover += amount
                fees += trade_fee
                order_count += 1
                trade_count += 1
                if current + shares < target:
                    unfilled_count += 1
                trade_rows.append(
                    {
                        "date": date,
                        "fee_profile": profile.name,
                        "ts_code": code,
                        "side": "buy",
                        "price": price,
                        "shares": shares,
                        "amount": amount,
                        "fee": trade_fee,
                        "cash_after": cash,
                    }
                )

            holdings = {code: shares for code, shares in holdings.items() if shares > 0}

        value_after = sum(
            shares * _safe_float(close.get(code), 0.0)
            for code, shares in holdings.items()
            if shares
        )
        equity_after = cash + value_after
        daily_ret = equity_after / prev_equity - 1.0 if prev_equity > 0.0 else 0.0
        prev_equity = equity_after
        desired_positive = sum(1 for shares in desired.values() if shares > 0)
        actual_positions = sum(1 for shares in holdings.values() if shares > 0)
        target_position_gap = max(0, desired_positive - actual_positions) if is_rebalance else 0
        daily_rows.append(
            {
                "date": date,
                "fee_profile": profile.name,
                "equity": equity_after,
                "daily_ret": daily_ret,
                "cash": cash,
                "invested_value": value_after,
                "gross_exposure": value_after / equity_after if equity_after > 0.0 else 0.0,
                "turnover": turnover,
                "fee": fees,
                "order_count": order_count,
                "trade_count": trade_count,
                "is_rebalance": int(is_rebalance),
                "target_count": target_count,
                "desired_position_count": desired_positive,
                "actual_position_count": actual_positions,
                "unfilled_count": int(unfilled_count + target_position_gap),
            }
        )

    return pd.DataFrame(daily_rows), pd.DataFrame(trade_rows), pd.DataFrame(reject_rows)


def _align_returns(returns: dict[str, pd.Series]) -> pd.DataFrame:
    start = max(series.index.min() for series in returns.values())
    end = min(series.index.max() for series in returns.values())
    start = max(start, pd.Timestamp("2020-01-01"))
    index = pd.date_range(start=start, end=end, freq="D")
    aligned = pd.DataFrame(index=index)
    for name, series in returns.items():
        aligned[name] = series.groupby(level=0).sum().reindex(index).fillna(0.0)
    return aligned


def _window_masks(index: pd.DatetimeIndex) -> dict[str, pd.Series]:
    return {
        "full_common": pd.Series(True, index=index),
        "start_2021": pd.Series(index >= pd.Timestamp("2021-01-01"), index=index),
        "start_2022": pd.Series(index >= pd.Timestamp("2022-01-01"), index=index),
        "start_2023": pd.Series(index >= pd.Timestamp("2023-01-01"), index=index),
        "start_2024": pd.Series(index >= pd.Timestamp("2024-01-01"), index=index),
        "ytd_2026": pd.Series(index >= pd.Timestamp("2026-01-01"), index=index),
        "c3_2021_peak_to_trough": pd.Series(
            (index >= pd.Timestamp("2021-05-12")) & (index <= pd.Timestamp("2021-07-02")),
            index=index,
        ),
    }


def _build_outputs(
    aligned: pd.DataFrame,
    etf_daily_by_profile: dict[str, pd.DataFrame],
    trades: pd.DataFrame,
    rejects: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    series = {
        "A_c3_100": ("C3 100%", aligned["c3"]),
        "cash_control_c3_95_cash_05": ("C3 95% + 现金 5%", 0.95 * aligned["c3"]),
        "C_stage071_paper_c3_95_etf_05": (
            "Stage071连续权重 C3 95% + ETF 5%",
            0.95 * aligned["c3"] + 0.05 * aligned["paper_etf"],
        ),
    }
    for profile in FEE_PROFILES:
        key = f"real_etf_{profile.name}"
        series[f"B_{key}_100"] = (f"真实ETF腿 100% - {profile.label}", aligned[key])
        series[f"C_c3_95_etf_05_{profile.name}"] = (
            f"C3 95% + 真实ETF 5% - {profile.label}",
            0.95 * aligned["c3"] + 0.05 * aligned[key],
        )

    summary_rows = []
    for name, (label, ret) in series.items():
        summary_rows.append(_stats(name, label, ret))
    summary = pd.DataFrame(summary_rows)

    c3_ret = _safe_float(summary.loc[summary["variant"].eq("A_c3_100"), "total_return_pct"].iloc[0])
    for idx, row in summary.iterrows():
        summary.loc[idx, "return_retention_vs_c3_pct"] = (
            _safe_float(row["total_return_pct"]) / c3_ret * 100.0 if c3_ret > 0.0 else np.nan
        )

    window_rows: list[dict[str, Any]] = []
    for window_name, mask in _window_masks(aligned.index).items():
        if not mask.any():
            continue
        for name, (label, ret) in series.items():
            row = _stats(name, label, ret.loc[mask])
            row["window_name"] = window_name
            window_rows.append(row)
    window_summary = pd.DataFrame(window_rows)

    annual_rows: list[dict[str, Any]] = []
    years = sorted(set(aligned.index.year))
    for year in years:
        mask = aligned.index.year == year
        for name, (label, ret) in series.items():
            row = _stats(name, label, ret.loc[mask])
            row["year"] = int(year)
            annual_rows.append(row)
    annual_summary = pd.DataFrame(annual_rows)

    execution_rows = []
    for profile in FEE_PROFILES:
        daily = etf_daily_by_profile[profile.name]
        rebalance = daily[daily["is_rebalance"].eq(1)]
        profile_trades = trades[trades["fee_profile"].eq(profile.name)] if not trades.empty else pd.DataFrame()
        profile_rejects = rejects[rejects["fee_profile"].eq(profile.name)] if not rejects.empty else pd.DataFrame()
        target_events = float(rebalance["target_count"].sum()) if not rebalance.empty else 0.0
        desired_events = float(rebalance["desired_position_count"].sum()) if not rebalance.empty else 0.0
        unfilled = float(rebalance["unfilled_count"].sum()) if not rebalance.empty else 0.0
        execution_rows.append(
            {
                "fee_profile": profile.name,
                "label": profile.label,
                "etf_end_equity": float(daily["equity"].iloc[-1]),
                "etf_total_return_pct": float((daily["equity"].iloc[-1] / ETF_LEG_CAPITAL - 1.0) * 100.0),
                "total_turnover": float(daily["turnover"].sum()),
                "total_fee": float(daily["fee"].sum()),
                "total_trades": int(profile_trades.shape[0]),
                "rebalance_days": int(rebalance.shape[0]),
                "target_events": int(target_events),
                "desired_lot_events": int(desired_events),
                "unfilled_events": int(unfilled),
                "reject_rows": int(profile_rejects.shape[0]),
                "avg_gross_exposure": float(daily["gross_exposure"].mean()),
                "max_gross_exposure": float(daily["gross_exposure"].max()),
                "avg_actual_position_count": float(daily["actual_position_count"].mean()),
                "max_actual_position_count": int(daily["actual_position_count"].max()),
                "fee_to_initial_capital_pct": float(daily["fee"].sum() / ETF_LEG_CAPITAL * 100.0),
                "turnover_to_initial_capital_x": float(daily["turnover"].sum() / ETF_LEG_CAPITAL),
            }
        )
    execution = pd.DataFrame(execution_rows)

    main_variant = f"C_c3_95_etf_05_{MAIN_FEE_PROFILE}"
    main = summary[summary["variant"].eq(main_variant)].iloc[0].to_dict()
    cash = summary[summary["variant"].eq("cash_control_c3_95_cash_05")].iloc[0].to_dict()
    paper = summary[summary["variant"].eq("C_stage071_paper_c3_95_etf_05")].iloc[0].to_dict()
    main_windows = window_summary[window_summary["variant"].eq(main_variant)].copy()
    fail_windows = []
    c3_windows = window_summary[window_summary["variant"].eq("A_c3_100")].set_index("window_name")
    cash_windows = window_summary[window_summary["variant"].eq("cash_control_c3_95_cash_05")].set_index(
        "window_name"
    )
    cash_gate_windows = {
        "full_common",
        "start_2021",
        "start_2022",
        "start_2023",
        "start_2024",
        "ytd_2026",
    }
    for _, row in main_windows.iterrows():
        window = str(row["window_name"])
        c3_window_ret = _safe_float(c3_windows.loc[window, "total_return_pct"]) if window in c3_windows.index else np.nan
        retention = _safe_float(row["total_return_pct"]) / c3_window_ret * 100.0 if c3_window_ret > 0.0 else 100.0
        if _safe_float(row["max_dd_percent"]) < PASS_MAX_DD:
            fail_windows.append({"window_name": window, "reason": "max_drawdown_below_gate"})
        if c3_window_ret > 0.0 and retention < PASS_RETURN_RETENTION:
            fail_windows.append({"window_name": window, "reason": "return_retention_below_gate"})
        if window in cash_gate_windows and window in cash_windows.index:
            cash_row = cash_windows.loc[window]
            if _safe_float(row["total_return_pct"]) < _safe_float(cash_row["total_return_pct"]) - 1e-9:
                fail_windows.append(
                    {
                        "window_name": window,
                        "reason": "cash_window_return_underperformance",
                        "candidate_return_pct": _safe_float(row["total_return_pct"]),
                        "cash_return_pct": _safe_float(cash_row["total_return_pct"]),
                    }
                )
            if _safe_float(row["max_dd_percent"]) < _safe_float(cash_row["max_dd_percent"]) - 1e-9:
                fail_windows.append(
                    {
                        "window_name": window,
                        "reason": "cash_window_drawdown_underperformance",
                        "candidate_max_dd_percent": _safe_float(row["max_dd_percent"]),
                        "cash_max_dd_percent": _safe_float(cash_row["max_dd_percent"]),
                    }
                )
            if _safe_float(row["ulcer"]) > _safe_float(cash_row["ulcer"]) + 1e-9:
                fail_windows.append(
                    {
                        "window_name": window,
                        "reason": "cash_window_ulcer_underperformance",
                        "candidate_ulcer": _safe_float(row["ulcer"]),
                        "cash_ulcer": _safe_float(cash_row["ulcer"]),
                    }
                )

    execution_main = execution[execution["fee_profile"].eq(MAIN_FEE_PROFILE)].iloc[0].to_dict()
    beats_cash_return = _safe_float(main["total_return_pct"]) > _safe_float(cash["total_return_pct"])
    beats_cash_dd = _safe_float(main["max_dd_percent"]) >= _safe_float(cash["max_dd_percent"]) - 1e-9
    beats_cash_ulcer = _safe_float(main["ulcer"]) <= _safe_float(cash["ulcer"]) + 1e-9
    pass_gate = bool(
        _safe_float(main["max_dd_percent"]) >= PASS_MAX_DD
        and _safe_float(main["return_retention_vs_c3_pct"]) >= PASS_RETURN_RETENTION
        and beats_cash_return
        and beats_cash_dd
        and beats_cash_ulcer
        and len(fail_windows) == 0
        and _safe_float(execution_main["etf_total_return_pct"]) > 0.0
    )
    decision = {
        "decision": "candidate_etf_realistic_lot_pass_next_oos_review"
        if pass_gate
        else "fail_etf_realistic_lot_not_robust_vs_cash_windows",
        "main_fee_profile": MAIN_FEE_PROFILE,
        "main_variant": main,
        "cash_control": cash,
        "paper_stage071": paper,
        "execution_main": execution_main,
        "beats_same_weight_cash_return": beats_cash_return,
        "beats_same_weight_cash_dd": beats_cash_dd,
        "beats_same_weight_cash_ulcer": beats_cash_ulcer,
        "fail_windows": fail_windows,
        "predeclared_gates": {
            "max_drawdown_percent_min": PASS_MAX_DD,
            "return_retention_vs_c3_percent_min": PASS_RETURN_RETENTION,
            "must_beat_same_weight_cash_return": True,
            "must_not_worsen_same_weight_cash_drawdown": True,
            "must_not_worsen_same_weight_cash_ulcer": True,
            "must_not_underperform_same_weight_cash_in_core_start_windows": True,
            "realistic_etf_standalone_return_must_be_positive": True,
            "main_cost_case": MAIN_FEE_PROFILE,
        },
    }
    return summary, window_summary, annual_summary, execution, decision


def _write_report(
    summary: pd.DataFrame,
    window_summary: pd.DataFrame,
    annual_summary: pd.DataFrame,
    execution: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    report_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
    main = decision["main_variant"]
    cash = decision["cash_control"]
    paper = decision["paper_stage071"]
    lines = [
        "# Stage372 ETF真实整手承载复核",
        "",
        "## 结论先行",
        "",
        f"- 决策：`{decision['decision']}`。",
        f"- 主审计口径：`{decision['main_fee_profile']}`，即100份整手、单向10bp、5元最低佣金。",
        f"- 真实整手组合：总收益`{_safe_float(main['total_return_pct']):.4f}%`，最大回撤`{_safe_float(main['max_dd_percent']):.4f}%`，Sharpe `{_safe_float(main['sharpe']):.4f}`，Ulcer `{_safe_float(main['ulcer']):.4f}`。",
        f"- 同权重现金：总收益`{_safe_float(cash['total_return_pct']):.4f}%`，最大回撤`{_safe_float(cash['max_dd_percent']):.4f}%`，Ulcer `{_safe_float(cash['ulcer']):.4f}`。",
        f"- Stage071连续权重纸面组合：总收益`{_safe_float(paper['total_return_pct']):.4f}%`，最大回撤`{_safe_float(paper['max_dd_percent']):.4f}%`。",
        "",
        "## 外部规则与本地判断",
        "",
        "- 上交所ETF二级市场最低1手为100份，最小价格变动单位为0.001元；深交所基金份额买入也要求100份或整数倍。",
        "- 因此本阶段不再使用连续权重作为结论，而是把25,000元ETF腿重新按100份整手、现金约束和费用逐日撮合。",
        "- 本阶段不新增ETF、不扫权重、不改C3，只复核Stage071候选是否真实可承载。",
        "",
        "## 主要结果",
        "",
        summary.to_markdown(index=False),
        "",
        "## 执行承载摘要",
        "",
        execution.to_markdown(index=False),
        "",
        "## 多窗口结果",
        "",
        window_summary.to_markdown(index=False),
        "",
        "## 年度结果",
        "",
        annual_summary.to_markdown(index=False),
        "",
        "## 过拟合反思",
        "",
        "- 运行前：不是过拟合。本阶段只检查真实交易约束，没有新增收益参数。",
        "- 运行后：以结果为准。若真实整手后只略优或弱于现金，不应继续扫ETF权重、ETF代码或Connors参数救援。",
        "",
        "## 继续价值反思",
        "",
        "- 运行前：有价值。Stage071的边际优势很小，必须先确认不是连续权重和费用假设造成的纸面优势。",
        "- 运行后：若通过，只能进入OOS/paper复核；若失败，当前ETF小腿不再作为主路径。",
    ]
    report_path.write_text("\n".join(lines), encoding="utf-8")


def _write_html_plot(aligned: pd.DataFrame, summary: pd.DataFrame, decision: dict[str, Any]) -> None:
    variants = [
        ("A_c3_100", "C3 100%", aligned["c3"]),
        ("cash_control_c3_95_cash_05", "C3 95% + 现金 5%", 0.95 * aligned["c3"]),
        (
            "C_stage071_paper_c3_95_etf_05",
            "Stage071连续权重 C3 95% + ETF 5%",
            0.95 * aligned["c3"] + 0.05 * aligned["paper_etf"],
        ),
        (
            f"C_c3_95_etf_05_{MAIN_FEE_PROFILE}",
            "真实整手 C3 95% + ETF 5%",
            0.95 * aligned["c3"] + 0.05 * aligned[f"real_etf_{MAIN_FEE_PROFILE}"],
        ),
    ]
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.08)
    for _, label, ret in variants:
        nav = (1.0 + ret).cumprod()
        dd = nav / nav.cummax() - 1.0
        fig.add_trace(go.Scatter(x=nav.index, y=nav, name=label), row=1, col=1)
        fig.add_trace(go.Scatter(x=dd.index, y=dd * 100.0, name=f"{label}回撤", showlegend=False), row=2, col=1)
    fig.update_layout(
        title=f"Stage372 ETF真实整手承载复核 | {decision['decision']}",
        template="plotly_white",
        height=820,
        hovermode="x unified",
    )
    fig.update_yaxes(title_text="净值", row=1, col=1)
    fig.update_yaxes(title_text="回撤%", row=2, col=1)
    html_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_equity_drawdown_{MODEL_TAG}.html"
    fig.write_html(html_path, include_plotlyjs="cdn")


def main() -> None:
    targets = _load_targets()
    codes = sorted(targets["ts_code"].dropna().astype(str).unique())
    prices = _load_price_panel(codes)
    c3_ret = _load_c3_daily_ret()
    paper_ret = _load_paper_etf_ret()

    etf_daily_by_profile: dict[str, pd.DataFrame] = {}
    trades_all: list[pd.DataFrame] = []
    rejects_all: list[pd.DataFrame] = []
    returns: dict[str, pd.Series] = {"c3": c3_ret, "paper_etf": paper_ret}
    for profile in FEE_PROFILES:
        daily, trades, rejects = _simulate_etf_lot_execution(targets, prices, profile)
        daily["date"] = pd.to_datetime(daily["date"])
        etf_daily_by_profile[profile.name] = daily
        ret = daily.set_index("date")["daily_ret"].astype(float)
        returns[f"real_etf_{profile.name}"] = ret
        trades_all.append(trades)
        rejects_all.append(rejects)

    nonempty_trades = [df for df in trades_all if not df.empty]
    nonempty_rejects = [df for df in rejects_all if not df.empty]
    trades = pd.concat(nonempty_trades, ignore_index=True) if nonempty_trades else pd.DataFrame()
    rejects = pd.concat(nonempty_rejects, ignore_index=True) if nonempty_rejects else pd.DataFrame()

    aligned = _align_returns(returns)
    summary, window_summary, annual_summary, execution, decision = _build_outputs(
        aligned, etf_daily_by_profile, trades, rejects
    )

    daily_out = aligned.copy()
    daily_out.index.name = "date"
    for profile in FEE_PROFILES:
        key = f"real_etf_{profile.name}"
        daily_out[f"C_c3_95_etf_05_{profile.name}"] = 0.95 * daily_out["c3"] + 0.05 * daily_out[key]
    daily_out["cash_control_c3_95_cash_05"] = 0.95 * daily_out["c3"]
    daily_out["C_stage071_paper_c3_95_etf_05"] = 0.95 * daily_out["c3"] + 0.05 * daily_out["paper_etf"]

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    summary.to_csv(OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv", index=False)
    window_summary.to_csv(OUTPUT_DIR / f"{OUTPUT_PREFIX}_window_summary_{MODEL_TAG}.csv", index=False)
    annual_summary.to_csv(OUTPUT_DIR / f"{OUTPUT_PREFIX}_annual_summary_{MODEL_TAG}.csv", index=False)
    execution.to_csv(OUTPUT_DIR / f"{OUTPUT_PREFIX}_execution_summary_{MODEL_TAG}.csv", index=False)
    daily_out.to_csv(OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_{MODEL_TAG}.csv")
    trades.to_csv(OUTPUT_DIR / f"{OUTPUT_PREFIX}_trades_{MODEL_TAG}.csv", index=False)
    rejects.to_csv(OUTPUT_DIR / f"{OUTPUT_PREFIX}_rejects_{MODEL_TAG}.csv", index=False)
    with (OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json").open("w", encoding="utf-8") as file:
        json.dump(decision, file, ensure_ascii=False, indent=2, default=str)
    _write_report(summary, window_summary, annual_summary, execution, decision)
    _write_html_plot(aligned, summary, decision)

    print(json.dumps(decision, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
