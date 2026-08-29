from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import json
import math
from pathlib import Path
import sys
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from vnpy.trader.constant import Interval


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
sys.path.insert(0, str(PROJECT_DIR.resolve()))

import analyze_qmt_roll_stage506_next_real_forward_risk_signal_frontier as s506  # noqa: E402
import analyze_qmt_roll_stage513_stage208_exact_position_margin_audit as s513  # noqa: E402
from qmt_backtest_runtime_guard import assert_stage196_database_sentinels  # noqa: E402
from qmt_roll_portfolio_strategy import QmtRollPortfolioStrategy  # noqa: E402
from qmt_universe import END_DT, PRELOAD_START_DT, START_DT  # noqa: E402
from run_qmt_alignment_backtest import build_positions_df  # noqa: E402
from run_qmt_roll_backtest import build_roll_setting  # noqa: E402
from run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest import (  # noqa: E402
    BASE_RISK_RATIO,
)


MODEL_TAG = "stage516_margin_aware_sizing_frontier_v1"
OUTPUT_PREFIX = "qmt_roll_stage516_margin_aware_sizing_frontier"
LINE_ID = "futures_trend_drawdown30_preserve_return"

ACCOUNT_CAPITAL = 615_000.0
C3_CAPITAL = 500_000.0
BASELINE_STAGE079_RETURN_PCT = 4_947.260162601626
BROKER_MARGIN_MULTIPLIER = float(s513.s403.BROKER10_MULTIPLIER)

POSITIONS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_positions_{MODEL_TAG}.csv"
C3_DAILY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_c3_daily_{MODEL_TAG}.csv"
MARGIN_DAILY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_margin_daily_{MODEL_TAG}.csv"
SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
COST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cost_stress_{MODEL_TAG}.csv"
WINDOW_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_window_metrics_{MODEL_TAG}.csv"
ROLLING_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_rolling_holding_{MODEL_TAG}.csv"
EVENT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_margin_events_{MODEL_TAG}.csv"
PRODUCT_EVENT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_margin_events_{MODEL_TAG}.csv"
DIAGNOSTIC_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_diagnostics_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"


@dataclass(frozen=True)
class VariantSpec:
    variant: str
    label: str
    risk_multiplier: float
    sizing_equity_cap: float
    max_capital_usage_ratio: float
    max_single_trade_capital_usage_ratio: float
    enable_incremental_gate: bool
    note: str


VARIANTS: tuple[VariantSpec, ...] = (
    VariantSpec(
        "r060_legacy_nocap_u90",
        "risk060 legacy no-cap/u90",
        0.60,
        0.0,
        0.90,
        0.70,
        False,
        "Stage214 risk060 clean C3 复刻；sizing_equity_cap=0 表示不封顶，作为 exact margin 对照。",
    ),
    VariantSpec(
        "r070_legacy_nocap_u90",
        "risk070 legacy no-cap/u90",
        0.70,
        0.0,
        0.90,
        0.70,
        False,
        "Stage214 risk070 clean C3 复刻；高收益但高保证金占用对照。",
    ),
    VariantSpec(
        "r060_cap500_u80",
        "risk060 cap500k/u80",
        0.60,
        500_000.0,
        0.80,
        0.50,
        True,
        "把 C3 sizing equity 锁回 50万，并把开仓保证金预算降到 80%。",
    ),
    VariantSpec(
        "r080_cap500_u80",
        "risk080 cap500k/u80",
        0.80,
        500_000.0,
        0.80,
        0.50,
        True,
        "在相同 50万/80% 保证金壳里提高风险预算，检验是否只是 cap 绑定。",
    ),
    VariantSpec(
        "r100_cap500_u70",
        "risk100 cap500k/u70",
        1.00,
        500_000.0,
        0.70,
        0.45,
        True,
        "更高风险预算但更紧总保证金预算，测试 cap 优先结构。",
    ),
    VariantSpec(
        "r080_cap400_u80",
        "risk080 cap400k/u80",
        0.80,
        400_000.0,
        0.80,
        0.50,
        True,
        "把可承载 C3 sizing 退到 40万，观察保证金与收益摊薄边界。",
    ),
    VariantSpec(
        "r100_cap400_u70",
        "risk100 cap400k/u70",
        1.00,
        400_000.0,
        0.70,
        0.45,
        True,
        "40万 sizing cap + 70% 保证金壳，高风险预算只允许在低保证金机会中表达。",
    ),
)

ROLLING_HORIZONS: tuple[int, ...] = (63, 126, 252, 504)
COST_MULTIPLIERS: tuple[float, ...] = (1.0, 2.0, 3.0)
WINDOWS: tuple[tuple[str, str, datetime, datetime], ...] = (
    ("full_2020_2026", "2020起点至今", START_DT, END_DT),
    ("since_2021", "2021起点至今", datetime(2021, 1, 1), END_DT),
    ("since_2022", "2022起点至今", datetime(2022, 1, 1), END_DT),
    ("since_2023", "2023起点至今", datetime(2023, 1, 1), END_DT),
    ("since_2024", "2024起点至今", datetime(2024, 1, 1), END_DT),
    ("since_2025", "2025起点至今", datetime(2025, 1, 1), END_DT),
    ("ytd_2026", "2026起点至今", datetime(2026, 1, 1), END_DT),
    ("phase_2020_2021", "2020-2021独立段", datetime(2020, 1, 1), datetime(2021, 12, 31)),
    ("phase_2022_2023", "2022-2023独立段", datetime(2022, 1, 1), datetime(2023, 12, 31)),
    ("phase_2024_2025", "2024-2025独立段", datetime(2024, 1, 1), datetime(2025, 12, 31)),
)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(result) or math.isinf(result):
        return default
    return result


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        result = float(value)
        return None if math.isnan(result) or math.isinf(result) else result
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    return value


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "无数据。"
    view = frame.copy()
    if max_rows is not None:
        view = view.head(max_rows)
    for column in view.columns:
        if pd.api.types.is_float_dtype(view[column]):
            view[column] = view[column].map(lambda item: f"{item:.4f}" if pd.notna(item) else "")
    return view.to_markdown(index=False)


def _drawdown_pct(equity: pd.Series) -> pd.Series:
    values = equity.astype(float)
    return (values / values.cummax() - 1.0) * 100.0


def _max_drawdown_pct(equity: pd.Series) -> float:
    if equity.empty:
        return 0.0
    return float(_drawdown_pct(equity).min())


def _ulcer_pct(equity: pd.Series) -> float:
    if equity.empty:
        return 0.0
    dd = _drawdown_pct(equity)
    return float(np.sqrt(np.mean(np.square(np.minimum(dd.to_numpy(dtype=float), 0.0)))))


def _longest_underwater_days(equity: pd.Series) -> int:
    longest = 0
    current = 0
    for value in _drawdown_pct(equity).to_numpy(dtype=float):
        if value < -1e-12:
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return int(longest)


def _sharpe(equity: pd.Series) -> float:
    returns = equity.astype(float).pct_change().replace([np.inf, -np.inf], np.nan).fillna(0.0)
    std = float(returns.std(ddof=1))
    if std <= 0:
        return 0.0
    return float(returns.mean() / std * math.sqrt(252.0))


def _stressed_equity(frame: pd.DataFrame, cost_multiplier: float) -> pd.Series:
    ordered = frame.sort_values("date").copy()
    slippage = pd.to_numeric(ordered["total_slippage"], errors="coerce").fillna(0.0).cumsum()
    additional = slippage * max(0.0, float(cost_multiplier) - 1.0)
    equity = ordered["account_equity"].astype(float) - additional
    return pd.Series(equity.to_numpy(dtype=float), index=pd.to_datetime(ordered["date"]))


def _run_variant(spec: VariantSpec, metadata: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    assert_stage196_database_sentinels()
    s506._patch_stage506_raw_roots()
    overrides = s513._c3_overrides(START_DT)
    preload_start = max(PRELOAD_START_DT, START_DT - timedelta(days=365))
    _, open_map = s506.s501._seed_proxy_maps()
    engine = s506.s502.ConfirmedDailyNextRealOpenEngine(open_map)
    engine.output = lambda msg: None
    engine.set_parameters(
        vt_symbols=metadata["vt_symbols"],
        interval=Interval.DAILY,
        start=preload_start,
        end=END_DT,
        rates=metadata["rates"],
        slippages=metadata["slippages"],
        sizes=metadata["sizes"],
        priceticks=metadata["priceticks"],
        capital=C3_CAPITAL,
    )
    setting = build_roll_setting(
        metadata["margin_ratios"],
        risk_ratio=BASE_RISK_RATIO * float(spec.risk_multiplier),
        strategy_overrides=overrides,
    )
    setting.update(
        {
            "capital_base": C3_CAPITAL,
            "sizing_equity_cap": float(spec.sizing_equity_cap),
            "max_capital_usage_ratio": float(spec.max_capital_usage_ratio),
            "max_single_trade_capital_usage_ratio": float(spec.max_single_trade_capital_usage_ratio),
        }
    )
    if spec.enable_incremental_gate:
        setting.update(
            {
                "enable_incremental_margin_budget_gate": True,
                "incremental_margin_budget_gate_usage_ratio": float(spec.max_capital_usage_ratio),
                "incremental_margin_budget_gate_min_openable_candidates": 1,
                "incremental_margin_budget_gate_protected_selection_rank": 0,
            }
        )
    engine.add_strategy(QmtRollPortfolioStrategy, setting)
    engine.load_data()
    engine.run_backtesting()
    daily_df = engine.calculate_result()
    if daily_df is None or daily_df.empty:
        raise RuntimeError(f"empty daily result: {spec.variant}")

    daily = daily_df.copy()
    daily = daily.loc[(daily.index >= START_DT.date()) & (daily.index <= END_DT.date())].reset_index()
    daily.rename(columns={"index": "date"}, inplace=True)
    daily["date"] = pd.to_datetime(daily["date"], errors="coerce").dt.normalize()
    for column in ["net_pnl", "trade_count", "slippage", "commission", "turnover"]:
        daily[column] = pd.to_numeric(daily.get(column, 0.0), errors="coerce").fillna(0.0)
    daily["c3_equity"] = C3_CAPITAL + daily["net_pnl"].cumsum()
    daily["variant"] = spec.variant
    daily["combo_variant"] = spec.variant
    daily["label"] = spec.label
    daily["risk_multiplier"] = spec.risk_multiplier
    daily["sizing_equity_cap"] = spec.sizing_equity_cap
    daily["max_capital_usage_ratio"] = spec.max_capital_usage_ratio
    daily["max_single_trade_capital_usage_ratio"] = spec.max_single_trade_capital_usage_ratio
    daily["enable_incremental_gate"] = int(spec.enable_incremental_gate)
    daily["note"] = spec.note

    positions = build_positions_df(engine)
    if positions.empty:
        raise RuntimeError(f"empty positions: {spec.variant}")
    positions["variant"] = spec.variant
    positions["combo_variant"] = spec.variant
    positions["label"] = spec.label
    positions["risk_multiplier"] = spec.risk_multiplier
    positions["sizing_equity_cap"] = spec.sizing_equity_cap
    positions["max_capital_usage_ratio"] = spec.max_capital_usage_ratio

    diagnostics = pd.DataFrame(getattr(engine.strategy, "entry_risk_diagnostics", []))
    if not diagnostics.empty:
        diagnostics["variant"] = spec.variant
        diagnostics["label"] = spec.label
        diagnostics["risk_multiplier"] = spec.risk_multiplier
    return daily, positions, diagnostics


def _combine_daily(c3_daily: pd.DataFrame, margin_daily: pd.DataFrame, xsmom_daily: pd.DataFrame) -> pd.DataFrame:
    x = xsmom_daily[
        ["date", "xsmom_true_daily_pnl", "xsmom_true_slippage_cost", "xsmom_true_margin", "xsmom_true_held_contract_count"]
    ].copy()
    rows: list[pd.DataFrame] = []
    for variant, frame in c3_daily.groupby("variant", sort=False):
        merged = frame.sort_values("date").merge(
            x,
            on="date",
            how="left",
        ).merge(
            margin_daily[margin_daily["variant"].eq(variant)][
                ["date", "c3_margin_exact", "c3_active_contracts", "c3_active_products"]
            ],
            on="date",
            how="left",
        )
        for column in [
            "xsmom_true_daily_pnl",
            "xsmom_true_slippage_cost",
            "xsmom_true_margin",
            "xsmom_true_held_contract_count",
            "c3_margin_exact",
            "c3_active_contracts",
            "c3_active_products",
        ]:
            merged[column] = pd.to_numeric(merged.get(column, 0.0), errors="coerce").fillna(0.0)
        merged["total_net_pnl"] = merged["net_pnl"].astype(float) + merged["xsmom_true_daily_pnl"].astype(float)
        merged["total_slippage"] = merged["slippage"].astype(float) + merged["xsmom_true_slippage_cost"].astype(float)
        merged["account_equity"] = ACCOUNT_CAPITAL + merged["total_net_pnl"].cumsum()
        merged["total_margin_exact"] = merged["c3_margin_exact"] + merged["xsmom_true_margin"]
        merged["broker10_total_margin_exact"] = merged["total_margin_exact"] * BROKER_MARGIN_MULTIPLIER
        merged["broker10_margin_to_equity_pct"] = (
            merged["broker10_total_margin_exact"] / merged["account_equity"].replace(0.0, np.nan) * 100.0
        ).replace([np.inf, -np.inf], np.nan).fillna(0.0)
        rows.append(merged)
    return pd.concat(rows, ignore_index=True, sort=False)


def _metrics_from_equity(
    equity: pd.Series,
    frame: pd.DataFrame,
    *,
    variant: str,
    label: str,
    cost_multiplier: float,
) -> dict[str, Any]:
    ordered = frame.sort_values("date").copy()
    margin_ratio = (
        ordered["broker10_total_margin_exact"].astype(float).to_numpy()
        / np.maximum(equity.to_numpy(dtype=float), 1e-9)
        * 100.0
    )
    total_profit = float(equity.iloc[-1] - ACCOUNT_CAPITAL) if not equity.empty else 0.0
    nonzero_pnl = ordered["total_net_pnl"].astype(float)
    nonzero_pnl = nonzero_pnl[nonzero_pnl.abs() > 1e-12]
    return {
        "variant": variant,
        "label": label,
        "cost_multiplier": cost_multiplier,
        "end_equity": float(equity.iloc[-1]) if not equity.empty else ACCOUNT_CAPITAL,
        "total_return_pct": total_profit / ACCOUNT_CAPITAL * 100.0,
        "return_retention_vs_stage079_pct": (total_profit / ACCOUNT_CAPITAL * 100.0) / BASELINE_STAGE079_RETURN_PCT * 100.0,
        "max_dd_pct": _max_drawdown_pct(equity),
        "ulcer_pct": _ulcer_pct(equity),
        "sharpe": _sharpe(equity),
        "longest_underwater_days": _longest_underwater_days(equity),
        "max_broker10_margin_to_equity_pct": float(np.max(margin_ratio)) if len(margin_ratio) else 0.0,
        "p95_broker10_margin_to_equity_pct": float(np.quantile(margin_ratio, 0.95)) if len(margin_ratio) else 0.0,
        "days_over_100pct": int(np.sum(margin_ratio > 100.0 + 1e-9)),
        "days_over_90pct": int(np.sum(margin_ratio > 90.0 + 1e-9)),
        "total_slippage": float(ordered["total_slippage"].sum()),
        "total_trade_count": float(ordered["trade_count"].sum() + ordered["xsmom_true_held_contract_count"].diff().abs().fillna(0.0).sum()),
        "nonzero_daily_win_rate_pct": float((nonzero_pnl > 0.0).mean() * 100.0) if len(nonzero_pnl) else 0.0,
        "dd40_pass": int(_max_drawdown_pct(equity) >= -40.0),
        "broker10_100_pass": int(np.all(margin_ratio <= 100.0 + 1e-9)) if len(margin_ratio) else 1,
        "broker10_90_pass": int(np.all(margin_ratio <= 90.0 + 1e-9)) if len(margin_ratio) else 1,
    }


def _summary_and_cost(combo_daily: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    summary_rows: list[dict[str, Any]] = []
    cost_rows: list[dict[str, Any]] = []
    specs = {spec.variant: spec for spec in VARIANTS}
    for variant, frame in combo_daily.groupby("variant", sort=False):
        spec = specs[variant]
        for cost_multiplier in COST_MULTIPLIERS:
            equity = _stressed_equity(frame, cost_multiplier)
            row = _metrics_from_equity(
                equity,
                frame,
                variant=variant,
                label=spec.label,
                cost_multiplier=cost_multiplier,
            )
            row.update(
                {
                    "risk_multiplier": spec.risk_multiplier,
                    "sizing_equity_cap": spec.sizing_equity_cap,
                    "max_capital_usage_ratio": spec.max_capital_usage_ratio,
                    "max_single_trade_capital_usage_ratio": spec.max_single_trade_capital_usage_ratio,
                    "enable_incremental_gate": int(spec.enable_incremental_gate),
                }
            )
            cost_rows.append(row)
            if cost_multiplier == 1.0:
                summary_rows.append(row)
    return pd.DataFrame(summary_rows), pd.DataFrame(cost_rows)


def _window_metrics(combo_daily: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for variant, frame in combo_daily.groupby("variant", sort=False):
        label = str(frame["label"].iloc[0])
        ordered = frame.sort_values("date")
        for window_name, display_label, start, end in WINDOWS:
            sliced = ordered[ordered["date"].between(pd.Timestamp(start), pd.Timestamp(end))].copy()
            if sliced.empty:
                continue
            equity = pd.Series(sliced["account_equity"].to_numpy(dtype=float), index=pd.to_datetime(sliced["date"]))
            base = float(equity.iloc[0])
            total_return = float(equity.iloc[-1] / base - 1.0) * 100.0 if base > 0 else 0.0
            margin_ratio = sliced["broker10_margin_to_equity_pct"].astype(float)
            rows.append(
                {
                    "variant": variant,
                    "label": label,
                    "window_name": window_name,
                    "display_label": display_label,
                    "start": pd.Timestamp(start).date().isoformat(),
                    "end": pd.Timestamp(end).date().isoformat(),
                    "holding_days": int(len(sliced)),
                    "window_return_pct": total_return,
                    "window_max_dd_pct": _max_drawdown_pct(equity),
                    "window_ulcer_pct": _ulcer_pct(equity),
                    "window_sharpe": _sharpe(equity),
                    "window_max_broker10_margin_to_equity_pct": float(margin_ratio.max()),
                    "window_days_over_100pct": int((margin_ratio > 100.0).sum()),
                }
            )
    return pd.DataFrame(rows)


def _rolling_window_drawdown(values: np.ndarray) -> float:
    if len(values) == 0:
        return 0.0
    peaks = np.maximum.accumulate(values)
    dd = values / np.maximum(peaks, 1e-9) - 1.0
    return float(np.min(dd) * 100.0)


def _rolling_holding(combo_daily: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for variant, frame in combo_daily.groupby("variant", sort=False):
        label = str(frame["label"].iloc[0])
        ordered = frame.sort_values("date").reset_index(drop=True)
        equity = ordered["account_equity"].astype(float).to_numpy()
        dates = pd.to_datetime(ordered["date"]).reset_index(drop=True)
        for horizon in ROLLING_HORIZONS:
            if len(ordered) <= horizon:
                continue
            returns: list[float] = []
            dds: list[float] = []
            starts: list[pd.Timestamp] = []
            ends: list[pd.Timestamp] = []
            for start_idx in range(0, len(ordered) - horizon):
                end_idx = start_idx + horizon
                window_values = equity[start_idx : end_idx + 1]
                start_value = max(float(window_values[0]), 1e-9)
                returns.append(float(window_values[-1] / start_value - 1.0) * 100.0)
                dds.append(_rolling_window_drawdown(window_values))
                starts.append(pd.Timestamp(dates.iloc[start_idx]))
                ends.append(pd.Timestamp(dates.iloc[end_idx]))
            ret_arr = np.asarray(returns, dtype=float)
            dd_arr = np.asarray(dds, dtype=float)
            worst_idx = int(np.argmin(ret_arr))
            rows.append(
                {
                    "variant": variant,
                    "label": label,
                    "holding_days": int(horizon),
                    "sample_count": int(len(ret_arr)),
                    "min_return_pct": float(np.min(ret_arr)),
                    "p05_return_pct": float(np.quantile(ret_arr, 0.05)),
                    "p10_return_pct": float(np.quantile(ret_arr, 0.10)),
                    "median_return_pct": float(np.median(ret_arr)),
                    "p90_return_pct": float(np.quantile(ret_arr, 0.90)),
                    "positive_rate_pct": float(np.mean(ret_arr > 0.0) * 100.0),
                    "loss_rate_pct": float(np.mean(ret_arr < 0.0) * 100.0),
                    "min_window_dd_pct": float(np.min(dd_arr)),
                    "p10_window_dd_pct": float(np.quantile(dd_arr, 0.10)),
                    "worst_return_start": starts[worst_idx].date().isoformat(),
                    "worst_return_end": ends[worst_idx].date().isoformat(),
                }
            )
    return pd.DataFrame(rows)


def _event_days(combo_daily: pd.DataFrame, product_margin: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    event_rows: list[dict[str, Any]] = []
    product_rows: list[pd.DataFrame] = []
    for variant, frame in combo_daily.groupby("variant", sort=False):
        ordered = frame.sort_values("date")
        equity = pd.Series(ordered["account_equity"].to_numpy(dtype=float), index=pd.to_datetime(ordered["date"]))
        margin_ratio = pd.Series(ordered["broker10_margin_to_equity_pct"].to_numpy(dtype=float), index=pd.to_datetime(ordered["date"]))
        dd = _drawdown_pct(equity)
        dates = list(margin_ratio.sort_values(ascending=False).head(10).index)
        dates.extend(list(dd.sort_values(ascending=True).head(10).index))
        seen: set[pd.Timestamp] = set()
        for date in dates:
            date = pd.Timestamp(date).normalize()
            if date in seen:
                continue
            seen.add(date)
            row = ordered[ordered["date"].eq(date)].iloc[0]
            event_rows.append(
                {
                    "variant": variant,
                    "label": str(row["label"]),
                    "date": date.date().isoformat(),
                    "account_equity": float(row["account_equity"]),
                    "drawdown_pct": float(dd.loc[date]),
                    "broker10_margin_to_equity_pct": float(row["broker10_margin_to_equity_pct"]),
                    "c3_margin_exact": float(row["c3_margin_exact"]),
                    "xsmom_true_margin": float(row["xsmom_true_margin"]),
                    "c3_active_products": int(row["c3_active_products"]),
                    "xsmom_true_held_contract_count": int(row["xsmom_true_held_contract_count"]),
                }
            )
            products = product_margin[
                product_margin["variant"].eq(variant)
                & product_margin["date"].eq(date)
                & product_margin["c3_margin_exact"].gt(0.0)
            ].copy()
            if not products.empty:
                products["event_date"] = date.date().isoformat()
                products["label"] = str(row["label"])
                product_rows.append(products.sort_values("c3_margin_exact", ascending=False).head(6))
    event_df = pd.DataFrame(event_rows)
    product_df = pd.concat(product_rows, ignore_index=True) if product_rows else pd.DataFrame()
    return event_df, product_df


def _decision(summary: pd.DataFrame, cost: pd.DataFrame, rolling: pd.DataFrame) -> dict[str, Any]:
    full_1x = summary.copy()
    cost_2x = cost[cost["cost_multiplier"].eq(2.0)].set_index("variant")
    candidates = []
    for row in full_1x.itertuples(index=False):
        row_dict = row._asdict()
        v = str(row_dict["variant"])
        two_x = cost_2x.loc[v] if v in cost_2x.index else None
        dd2_pass = int(_safe_float(two_x["max_dd_pct"]) >= -40.0) if two_x is not None else 0
        hard_pass = int(
            int(row_dict["dd40_pass"]) == 1
            and int(row_dict["broker10_100_pass"]) == 1
            and dd2_pass == 1
        )
        strong_pass = int(hard_pass and int(row_dict["broker10_90_pass"]) == 1 and row_dict["return_retention_vs_stage079_pct"] >= 50.0)
        score = (
            _safe_float(row_dict["return_retention_vs_stage079_pct"])
            - max(0.0, _safe_float(row_dict["max_broker10_margin_to_equity_pct"]) - 90.0) * 2.0
            + max(-40.0, _safe_float(row_dict["max_dd_pct"]))
        )
        candidates.append(
            {
                "variant": v,
                "label": str(row_dict["label"]),
                "hard_pass": hard_pass,
                "strong_pass": strong_pass,
                "dd2_pass": dd2_pass,
                "score": score,
                "return_retention_vs_stage079_pct": _safe_float(row_dict["return_retention_vs_stage079_pct"]),
                "max_dd_pct": _safe_float(row_dict["max_dd_pct"]),
                "max_broker10_margin_to_equity_pct": _safe_float(row_dict["max_broker10_margin_to_equity_pct"]),
                "days_over_100pct": int(row_dict["days_over_100pct"]),
                "days_over_90pct": int(row_dict["days_over_90pct"]),
            }
        )
    ranked = sorted(candidates, key=lambda item: (item["strong_pass"], item["hard_pass"], item["score"]), reverse=True)
    best = ranked[0] if ranked else {}
    holding_126 = rolling[rolling["holding_days"].eq(126)].copy()
    best_126 = (
        holding_126.sort_values(["p10_return_pct", "positive_rate_pct"], ascending=[False, False]).head(1).to_dict(orient="records")
        if not holding_126.empty
        else []
    )
    if best.get("strong_pass"):
        label = "margin_aware_sizing_strong_candidate"
    elif best.get("hard_pass"):
        label = "margin_aware_sizing_hard_pass_but_return_or_90cap_weak"
    else:
        label = "margin_aware_sizing_not_ready"
    return {
        "stage": "Stage216",
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "decision": label,
        "best_variant": best,
        "best_126d_holding_experience": best_126[0] if best_126 else {},
        "ranked_variants": ranked,
        "next_step": (
            "If no hard-pass variant exists, stop using scalar risk/cap fixes and move to active deleveraging "
            "or lower-margin independent alpha; if a hard-pass exists, run exact margin by fresh-start windows."
        ),
    }


def _plot(combo_daily: pd.DataFrame, summary: pd.DataFrame, rolling: pd.DataFrame, decision: dict[str, Any]) -> None:
    selected = ["r060_legacy_nocap_u90", "r070_legacy_nocap_u90"]
    ranked = [item["variant"] for item in decision.get("ranked_variants", [])]
    for variant in ranked:
        if variant not in selected:
            selected.append(variant)
        if len(selected) >= 5:
            break

    fig, axes = plt.subplots(2, 2, figsize=(15, 10))
    ax_nav, ax_dd, ax_margin, ax_roll = axes.ravel()
    colors = plt.cm.tab10(np.linspace(0, 1, max(10, len(selected))))
    color_map = {variant: colors[idx] for idx, variant in enumerate(selected)}

    for variant, frame in combo_daily[combo_daily["variant"].isin(selected)].groupby("variant", sort=False):
        frame = frame.sort_values("date")
        label = str(frame["label"].iloc[0])
        x = pd.to_datetime(frame["date"])
        equity = pd.Series(frame["account_equity"].to_numpy(dtype=float), index=x)
        nav = equity / ACCOUNT_CAPITAL
        ax_nav.plot(x, nav, label=label, linewidth=1.05, color=color_map.get(variant))
        ax_dd.plot(x, _drawdown_pct(equity), label=label, linewidth=0.95, color=color_map.get(variant))
        ax_margin.plot(x, frame["broker10_margin_to_equity_pct"].astype(float), label=label, linewidth=0.95, color=color_map.get(variant))

    ax_nav.set_title("Account NAV: C3 exact variants + fixed true xsmom")
    ax_nav.set_ylabel("NAV")
    ax_nav.grid(True, alpha=0.22)
    ax_nav.legend(fontsize=7)
    ax_dd.set_title("Underwater drawdown")
    ax_dd.set_ylabel("Drawdown %")
    ax_dd.axhline(-40.0, color="#222222", linestyle="--", linewidth=1.0)
    ax_dd.grid(True, alpha=0.22)
    ax_margin.set_title("Broker10 exact margin / equity")
    ax_margin.set_ylabel("Margin / equity %")
    ax_margin.axhline(100.0, color="#222222", linestyle="--", linewidth=1.0)
    ax_margin.axhline(90.0, color="#777777", linestyle=":", linewidth=0.9)
    ax_margin.grid(True, alpha=0.22)

    plot_summary = summary[summary["variant"].isin(selected)].copy()
    ax_roll.scatter(
        plot_summary["return_retention_vs_stage079_pct"],
        plot_summary["max_broker10_margin_to_equity_pct"],
        s=70,
        c=[color_map.get(v, "#333333") for v in plot_summary["variant"]],
    )
    for row in plot_summary.itertuples(index=False):
        ax_roll.annotate(str(row.variant).replace("_", "\n"), (row.return_retention_vs_stage079_pct, row.max_broker10_margin_to_equity_pct), fontsize=7)
    ax_roll.axhline(100.0, color="#222222", linestyle="--", linewidth=1.0)
    ax_roll.axhline(90.0, color="#777777", linestyle=":", linewidth=0.9)
    ax_roll.axvline(50.0, color="#777777", linestyle=":", linewidth=0.9)
    ax_roll.set_title("Return retention vs exact margin")
    ax_roll.set_xlabel("Retention vs Stage079 deployed return %")
    ax_roll.set_ylabel("Max broker10 margin / equity %")
    ax_roll.grid(True, alpha=0.22)

    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=160)
    plt.close(fig)


def _write_report(
    summary: pd.DataFrame,
    cost: pd.DataFrame,
    windows: pd.DataFrame,
    rolling: pd.DataFrame,
    events: pd.DataFrame,
    product_events: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    full = summary.sort_values(
        ["broker10_100_pass", "return_retention_vs_stage079_pct", "max_broker10_margin_to_equity_pct"],
        ascending=[False, False, True],
    )
    cost_view = cost[cost["cost_multiplier"].isin([1.0, 2.0, 3.0])].sort_values(["variant", "cost_multiplier"])
    roll_view = rolling[rolling["holding_days"].isin([63, 126, 252, 504])].sort_values(
        ["holding_days", "p10_return_pct"],
        ascending=[True, False],
    )
    report = [
        "# Stage216 保证金感知 sizing 粗前沿",
        "",
        f"- 生成时间：{decision['generated_at']}",
        f"- line_id：`{LINE_ID}`",
        "- 阶段性质：只读结构实验；固定 Stage079/C3 信号与品种池，只改粗档资金壳、sizing cap 与保证金预算，不改入场/出场逻辑。",
        "- 运行前过拟合判断：否。这里测试的是实盘资金承载结构，不是按收益曲线微调参数；档位很粗，且先验来自交易所保证金约束。",
        "- 运行前继续价值判断：是。Stage215 已确认代理保证金无效，必须用 exact position margin 先证明候选能下单。",
        "",
        "## 外部调研判断",
        "",
        "- SHFE/CFFEX 规则都把交易保证金、结算准备金、提高保证金、限制开仓、强平等作为真实交易约束；因此候选不能只看权益曲线，必须前置保证金预算并用持仓逐日复算。",
        "- vn.py/VeighNa 是事件驱动交易框架，适合把风控放在下单和持仓管理层；我的判断是：若只靠事后加现金或代理保证金，无法解释真实可成交性。",
        "",
        "## 决策",
        "",
        f"- 决策标签：`{decision['decision']}`。",
        f"- 最优综合候选：`{decision.get('best_variant', {}).get('variant', '')}`。",
        f"- 最优候选收益保留/最大回撤/最大 broker10 保证金："
        f"`{decision.get('best_variant', {}).get('return_retention_vs_stage079_pct', 0.0):.4f}% / "
        f"{decision.get('best_variant', {}).get('max_dd_pct', 0.0):.4f}% / "
        f"{decision.get('best_variant', {}).get('max_broker10_margin_to_equity_pct', 0.0):.4f}%`。",
        "",
        "## 全周期 1x 成本 exact margin",
        "",
        _md_table(
            full[
                [
                    "variant",
                    "label",
                    "risk_multiplier",
                    "sizing_equity_cap",
                    "max_capital_usage_ratio",
                    "total_return_pct",
                    "return_retention_vs_stage079_pct",
                    "max_dd_pct",
                    "ulcer_pct",
                    "sharpe",
                    "max_broker10_margin_to_equity_pct",
                    "days_over_100pct",
                    "days_over_90pct",
                    "dd40_pass",
                    "broker10_100_pass",
                    "broker10_90_pass",
                ]
            ]
        ),
        "",
        "## 成本压力",
        "",
        _md_table(
            cost_view[
                [
                    "variant",
                    "cost_multiplier",
                    "total_return_pct",
                    "return_retention_vs_stage079_pct",
                    "max_dd_pct",
                    "ulcer_pct",
                    "sharpe",
                    "max_broker10_margin_to_equity_pct",
                    "days_over_100pct",
                    "dd40_pass",
                    "broker10_100_pass",
                ]
            ],
            max_rows=42,
        ),
        "",
        "## 多起点/分段",
        "",
        _md_table(
            windows[
                [
                    "variant",
                    "window_name",
                    "window_return_pct",
                    "window_max_dd_pct",
                    "window_ulcer_pct",
                    "window_max_broker10_margin_to_equity_pct",
                    "window_days_over_100pct",
                ]
            ].sort_values(["variant", "window_name"]),
            max_rows=90,
        ),
        "",
        "## 任意时点启动后的持有体验",
        "",
        _md_table(
            roll_view[
                [
                    "variant",
                    "holding_days",
                    "min_return_pct",
                    "p05_return_pct",
                    "p10_return_pct",
                    "median_return_pct",
                    "positive_rate_pct",
                    "min_window_dd_pct",
                    "worst_return_start",
                    "worst_return_end",
                ]
            ],
            max_rows=120,
        ),
        "",
        "## 关键事件日",
        "",
        _md_table(
            events.sort_values(["variant", "broker10_margin_to_equity_pct"], ascending=[True, False])[
                [
                    "variant",
                    "date",
                    "account_equity",
                    "drawdown_pct",
                    "broker10_margin_to_equity_pct",
                    "c3_margin_exact",
                    "xsmom_true_margin",
                    "c3_active_products",
                    "xsmom_true_held_contract_count",
                ]
            ],
            max_rows=80,
        ),
        "",
        "## 关键事件日 C3 产品保证金",
        "",
        _md_table(
            product_events[
                [
                    "variant",
                    "event_date",
                    "product_vt_symbol",
                    "c3_margin_exact",
                    "active_contracts",
                    "holding_pnl",
                    "trading_pnl",
                    "net_pnl",
                ]
            ].sort_values(["variant", "event_date", "c3_margin_exact"], ascending=[True, True, False]),
            max_rows=120,
        )
        if not product_events.empty
        else "无数据。",
        "",
        "## 图表视觉复盘",
        "",
        "- 图表包含账户净值、回撤、broker10 exact 保证金占用、收益保留与保证金散点；重点观察是否有点同时落在 `broker10<=100%`、`回撤>=-40%`、收益保留较高区域。",
        "- 如果净值线明显低于 legacy 但保证金仍穿 100%，说明仅压 sizing cap 不能解决实盘承载，需要主动降仓而非开仓预算。",
        "- 如果保证金线降到 90-100% 内但 NAV 明显塌缩，则说明资本效率被保证金约束吃掉，不适合作为 Stage079 替代。",
        "",
        "## 结论",
        "",
        "- 本阶段只判断资金壳方向是否值得继续，不把任何粗档视为正式策略。",
        "- 若没有 hard pass，下一步不应继续扫 `risk_multiplier` 小数或 `sizing_equity_cap` 小数；应转向持仓期主动 deleveraging、品种保证金贡献治理、或者保证金轻的独立收益源。",
        "- 若出现 hard pass，则下一步做 fresh-start、多周期 exact margin、真实手续费/保证金率历史表复核后再谈候选晋级。",
        "",
        "## 过拟合与继续价值反思",
        "",
        "- 运行后过拟合判断：以最终 decision 为准；本阶段仍是粗档结构验证，没有使用未来收益调信号。",
        "- 运行后继续价值判断：以最终 decision 为准；若粗档资金壳失败，继续价值在换机制，不在扫参。",
    ]
    REPORT_PATH.write_text("\n".join(report) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    metadata = s513._metadata()
    daily_frames: list[pd.DataFrame] = []
    position_frames: list[pd.DataFrame] = []
    diagnostic_frames: list[pd.DataFrame] = []
    for spec in VARIANTS:
        print(f"[stage516] running {spec.variant}", flush=True)
        daily, positions, diagnostics = _run_variant(spec, metadata)
        daily_frames.append(daily)
        position_frames.append(positions)
        if not diagnostics.empty:
            diagnostic_frames.append(diagnostics)

    c3_daily = pd.concat(daily_frames, ignore_index=True)
    positions = pd.concat(position_frames, ignore_index=True)
    c3_margin_daily, product_margin = s513._position_margin(positions, metadata)
    xsmom_daily = s513._load_xsmom_daily()
    combo_daily = _combine_daily(c3_daily, c3_margin_daily, xsmom_daily)
    summary, cost = _summary_and_cost(combo_daily)
    windows = _window_metrics(combo_daily)
    rolling = _rolling_holding(combo_daily)
    events, product_events = _event_days(combo_daily, product_margin)
    decision = _decision(summary, cost, rolling)
    _plot(combo_daily, summary, rolling, decision)
    _write_report(summary, cost, windows, rolling, events, product_events, decision)

    positions.to_csv(POSITIONS_PATH, index=False, encoding="utf-8-sig")
    c3_daily.to_csv(C3_DAILY_PATH, index=False, encoding="utf-8-sig")
    combo_daily.to_csv(MARGIN_DAILY_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    cost.to_csv(COST_PATH, index=False, encoding="utf-8-sig")
    windows.to_csv(WINDOW_PATH, index=False, encoding="utf-8-sig")
    rolling.to_csv(ROLLING_PATH, index=False, encoding="utf-8-sig")
    events.to_csv(EVENT_PATH, index=False, encoding="utf-8-sig")
    product_events.to_csv(PRODUCT_EVENT_PATH, index=False, encoding="utf-8-sig")
    diagnostics = pd.concat(diagnostic_frames, ignore_index=True) if diagnostic_frames else pd.DataFrame()
    diagnostics.to_csv(DIAGNOSTIC_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
