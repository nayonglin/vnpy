from __future__ import annotations

from dataclasses import replace
from datetime import datetime
import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import analyze_qmt_roll_stage513_stage208_exact_position_margin_audit as s513
import analyze_qmt_roll_stage650_stage526_200k_capital_reality_check as s650
import analyze_qmt_roll_stage653_stage526_200k_forced_margin_deleverage as s653
import analyze_qmt_roll_stage659_stage653_2026_ytd_latest_ai_shadow as s659
import analyze_qmt_roll_stage660_stage653_multiperiod_live_audit as s660
import analyze_qmt_roll_stage661_stage653_min_one_throttle_multiperiod as s661
from main_contract_mapping import build_contract_metadata, load_product_universe_symbols
from qmt_roll_official_live_config import OFFICIAL_LIVE_PROFILE_NAME, OFFICIAL_LIVE_VERSION


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

MODEL_TAG = "stage666_stage372_500k_risk005_ag_ab_v1"
OUTPUT_PREFIX = "qmt_roll_stage666_stage372_500k_risk005_ag_ab"
LINE_ID = "futures_trend_drawdown30_preserve_return"

CAPITAL = 500_000.0
RISK_MULTIPLIER = 0.05
AG_PRODUCT = "ag.SHFE"
PLUS_AG_STRATEGY = "stage666_stage372_500k_risk005_plus_ag_entry_filter"

VARIANT_NO_AG = "stage372_500k_risk005_no_ag"
VARIANT_PLUS_AG = "stage372_500k_risk005_plus_ag"

GENERATED_DIR = OUTPUT_DIR / "stage666_generated_inputs"
UNIVERSE_PLUS_AG_PATH = GENERATED_DIR / f"{OUTPUT_PREFIX}_plus_ag_universe_{MODEL_TAG}.csv"
HIST_ELIGIBILITY_PLUS_AG_PATH = GENERATED_DIR / f"{OUTPUT_PREFIX}_historical_plus_ag_eligibility_{MODEL_TAG}.csv"
LATEST_ELIGIBILITY_PLUS_AG_PATH = GENERATED_DIR / f"{OUTPUT_PREFIX}_latest_plus_ag_eligibility_{MODEL_TAG}.csv"

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
COST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cost_stress_{MODEL_TAG}.csv"
COMPARISON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_comparison_{MODEL_TAG}.csv"
ROLLING_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_rolling_{MODEL_TAG}.csv"
ANNUAL_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_annual_{MODEL_TAG}.csv"
MONTHLY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_monthly_{MODEL_TAG}.csv"
CURVES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv"
AG_ACTIVITY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_ag_activity_{MODEL_TAG}.csv"
CHECKS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_checks_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"


def _json_safe(value: Any) -> Any:
    return s650._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s650._md_table(frame, max_rows=max_rows)


def _drawdown_pct(equity: pd.Series) -> pd.Series:
    values = pd.to_numeric(equity, errors="coerce").ffill().fillna(CAPITAL)
    peak = values.cummax()
    return (values / peak.replace(0.0, np.nan) - 1.0).replace([np.inf, -np.inf], np.nan).fillna(0.0) * 100.0


def _sharpe(equity: pd.Series) -> float:
    returns = pd.to_numeric(equity, errors="coerce").ffill().pct_change().replace([np.inf, -np.inf], np.nan).fillna(0.0)
    std = float(returns.std(ddof=1))
    if std <= 0:
        return 0.0
    return float(returns.mean() / std * np.sqrt(252.0))


def _cagr_pct(equity: pd.Series, dates: pd.Series) -> float:
    if len(equity) < 2:
        return 0.0
    start = float(equity.iloc[0])
    end = float(equity.iloc[-1])
    if start <= 0 or end <= 0:
        return 0.0
    days = max((pd.Timestamp(dates.iloc[-1]) - pd.Timestamp(dates.iloc[0])).days, 1)
    return float((end / start) ** (365.25 / days) - 1.0) * 100.0


def _official_symbols() -> list[str]:
    overrides = s513._c3_overrides(s513.START_DT)
    symbols = load_product_universe_symbols(str(overrides.get("product_universe_csv_path", "") or ""))
    if not symbols:
        symbols = s513._metadata()["product_symbols"]
    return sorted(set(symbols))


def _write_plus_ag_universe(base_symbols: list[str]) -> None:
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    rows = []
    for symbol in sorted(set(base_symbols) | {AG_PRODUCT}):
        product, exchange = symbol.split(".", 1)
        rows.append(
            {
                "product_vt_symbol": symbol,
                "product": product,
                "exchange": exchange,
                "eligible": 1,
                "source": "stage666_500k_risk005_plus_ag_fixed_add_one",
            }
        )
    pd.DataFrame(rows).to_csv(UNIVERSE_PLUS_AG_PATH, index=False, encoding="utf-8-sig")


def _write_plus_ag_eligibility(source_path: Path, target_path: Path) -> None:
    source = pd.read_csv(source_path, encoding="utf-8-sig")
    required = {"strategy", "score_type", "eval_date", "product_vt_symbol", "score", "score_rank", "top_n"}
    missing = required - set(source.columns)
    if missing:
        raise ValueError(f"eligibility source missing columns {sorted(missing)}: {source_path}")

    source_strategy = str(source["strategy"].dropna().astype(str).iloc[0])
    frame = source[source["strategy"].astype(str).eq(source_strategy)].copy()
    frame["strategy"] = PLUS_AG_STRATEGY
    frame["eval_date"] = pd.to_datetime(frame["eval_date"], errors="coerce").dt.strftime("%Y-%m-%d")
    for column in ["score", "score_rank", "top_n"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(0.0)

    groups: list[pd.DataFrame] = []
    for eval_date, group in frame.groupby("eval_date", sort=True):
        group = group.copy()
        if not group["product_vt_symbol"].astype(str).eq(AG_PRODUCT).any():
            max_rank = int(group["score_rank"].max()) if not group.empty else 0
            max_top_n = int(group["top_n"].max()) if not group.empty else 0
            group["top_n"] = max_top_n + 1
            min_score = float(group["score"].min()) if not group.empty else 0.0
            group = pd.concat(
                [
                    group,
                    pd.DataFrame(
                        [
                            {
                                "strategy": PLUS_AG_STRATEGY,
                                "score_type": "stage666_fixed_add_one_ag",
                                "eval_date": str(eval_date),
                                "product_vt_symbol": AG_PRODUCT,
                                "score": min_score - 1e-6,
                                "score_rank": max_rank + 1,
                                "top_n": max_top_n + 1,
                            }
                        ]
                    ),
                ],
                ignore_index=True,
                sort=False,
            )
        groups.append(group)

    result = pd.concat(groups, ignore_index=True, sort=False)
    result.sort_values(["eval_date", "score_rank", "product_vt_symbol"], inplace=True)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(target_path, index=False, encoding="utf-8-sig")


def _prepare_inputs() -> dict[str, Any]:
    base_symbols = _official_symbols()
    plus_symbols = sorted(set(base_symbols) | {AG_PRODUCT})
    _write_plus_ag_universe(base_symbols)
    historical_source = Path(str(s513._c3_overrides(s513.START_DT)["ai_product_pool_eligibility_path"])).resolve()
    latest_source = s659.DEFAULT_AI_ELIGIBILITY_PATH.resolve()
    _write_plus_ag_eligibility(historical_source, HIST_ELIGIBILITY_PLUS_AG_PATH)
    _write_plus_ag_eligibility(latest_source, LATEST_ELIGIBILITY_PLUS_AG_PATH)
    return {
        "base_symbols": base_symbols,
        "plus_symbols": plus_symbols,
        "historical_eligibility_source": str(historical_source),
        "latest_eligibility_source": str(latest_source),
        "base_metadata": build_contract_metadata(supported_symbols=base_symbols),
        "plus_metadata": build_contract_metadata(supported_symbols=plus_symbols),
    }


def _base_500k_spec(metadata: dict[str, Any]) -> s653.ForcedVariant:
    official = s660._official_spec(metadata)
    capital = replace(
        official.capital,
        variant=VARIANT_NO_AG,
        label="50w Stage372 recovery sleeve risk005 no-ag",
        account_capital=CAPITAL,
        c3_capital=CAPITAL,
        risk_multiplier=RISK_MULTIPLIER,
        note=(
            "Stage666 B: keep Stage372 official logic and product pool, set account/c3 capital to 500k "
            "and capital risk_multiplier to 0.05."
        ),
    )
    return replace(official, capital=capital, profile="stage372_500k_risk005_no_ag")


def _plus_ag_500k_spec(metadata: dict[str, Any]) -> s653.ForcedVariant:
    official = s660._official_spec(metadata)
    capital = replace(
        official.capital,
        variant=VARIANT_PLUS_AG,
        label="50w Stage372 recovery sleeve risk005 plus-ag",
        account_capital=CAPITAL,
        c3_capital=CAPITAL,
        risk_multiplier=RISK_MULTIPLIER,
        note=(
            "Stage666 C: 500k/risk005 plus fixed ag.SHFE in product universe and every AI eligibility snapshot."
        ),
    )
    overrides = {
        **official.overrides,
        "product_universe_csv_path": str(UNIVERSE_PLUS_AG_PATH),
        "enable_ai_product_pool_filter": True,
        "ai_product_pool_eligibility_path": str(HIST_ELIGIBILITY_PLUS_AG_PATH),
        "ai_product_pool_strategy": PLUS_AG_STRATEGY,
    }
    return replace(official, capital=capital, overrides=overrides, profile="stage372_500k_risk005_plus_ag")


def _run_window_with_positions(
    *,
    spec: s653.ForcedVariant,
    metadata: dict[str, Any],
    analysis_start: pd.Timestamp,
    analysis_end: pd.Timestamp,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    original_start = s653.s517.START_DT
    original_end = s653.s517.END_DT
    try:
        s653.s517.START_DT = analysis_start.to_pydatetime()
        s653.s517.END_DT = analysis_end.to_pydatetime()
        daily, positions, usage, forced_events = s653._run_variant(replace(spec), metadata)
    finally:
        s653.s517.START_DT = original_start
        s653.s517.END_DT = original_end

    daily["account_capital"] = spec.capital.account_capital
    daily["c3_capital"] = spec.capital.c3_capital
    daily["profile"] = spec.profile
    positions["account_capital"] = spec.capital.account_capital
    positions["c3_capital"] = spec.capital.c3_capital
    c3_margin_daily, _product_margin = s513._position_margin(positions, metadata)
    combined = s650._combine_daily(daily, c3_margin_daily, spec.capital)
    combined["profile"] = spec.profile
    for column in [
        "forced_margin_deleverage_count",
        "forced_margin_deleverage_closed_volume",
        "forced_margin_deleverage_ratio",
        "forced_margin_deleverage_max_observed_ratio",
    ]:
        combined[column] = daily[column].iloc[0] if column in daily.columns and not daily.empty else 0
    return combined, positions, usage, forced_events


def _run_latest_ytd(
    *,
    spec: s653.ForcedVariant,
    metadata: dict[str, Any],
    ai_eligibility_path: Path,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    daily, positions, _usage, forced_events = s659._run_variant_dynamic(
        spec,
        metadata,
        datetime.strptime("2026-01-01", "%Y-%m-%d"),
        datetime.strptime("2026-06-05", "%Y-%m-%d"),
        ai_eligibility_path,
    )
    daily["account_capital"] = spec.capital.account_capital
    daily["c3_capital"] = spec.capital.c3_capital
    daily["profile"] = spec.profile
    positions["account_capital"] = spec.capital.account_capital
    positions["c3_capital"] = spec.capital.c3_capital
    c3_margin_daily, _product_margin = s513._position_margin(positions, metadata)
    combined = s650._combine_daily(daily, c3_margin_daily, spec.capital)
    combined["profile"] = spec.profile
    for column in [
        "forced_margin_deleverage_count",
        "forced_margin_deleverage_closed_volume",
        "forced_margin_deleverage_ratio",
        "forced_margin_deleverage_max_observed_ratio",
    ]:
        combined[column] = daily[column].iloc[0] if column in daily.columns and not daily.empty else 0
    return combined, forced_events


def _window_metrics(
    frame: pd.DataFrame,
    *,
    spec: s653.ForcedVariant,
    window_name: str,
    window_label: str,
    group: str,
    source_name: str,
    caveat: str,
    forced_events: pd.DataFrame,
) -> tuple[dict[str, Any], pd.DataFrame, list[dict[str, Any]]]:
    if frame.empty:
        raise ValueError(f"empty window frame: {window_name}")

    ordered = frame.sort_values("date").reset_index(drop=True)
    ordered["date"] = pd.to_datetime(ordered["date"], errors="coerce").dt.normalize()
    net_pnl = ordered["net_pnl"].astype(float)
    equity = ordered["account_equity"].astype(float)
    dates = ordered["date"]
    dd = _drawdown_pct(equity)
    margin = ordered["broker10_total_margin_exact"].astype(float) / equity.replace(0.0, np.nan) * 100.0
    margin = margin.replace([np.inf, -np.inf], np.nan).fillna(0.0)
    nonzero_pnl = net_pnl[net_pnl.abs().gt(1e-12)]

    start_date = pd.Timestamp(dates.iloc[0]).date().isoformat()
    end_date = pd.Timestamp(dates.iloc[-1]).date().isoformat()
    event_count = 0
    event_volume = 0.0
    if not forced_events.empty:
        events = forced_events.copy()
        events["date"] = pd.to_datetime(events["date"], errors="coerce").dt.normalize()
        events = events[
            events["variant"].astype(str).eq(spec.capital.variant)
            & events["date"].ge(pd.Timestamp(start_date))
            & events["date"].le(pd.Timestamp(end_date))
        ]
        event_count = int(len(events))
        event_volume = float(pd.to_numeric(events.get("reduce_volume", 0.0), errors="coerce").fillna(0.0).sum())

    summary = {
        "variant": spec.capital.variant,
        "window_name": window_name,
        "window_label": window_label,
        "window_group": group,
        "source_name": source_name,
        "analysis_start": start_date,
        "analysis_end": end_date,
        "trading_days": int(len(ordered)),
        "start_equity_path": float(equity.iloc[0]),
        "end_equity_path": float(equity.iloc[-1]),
        "path_return_pct": float((equity.iloc[-1] / CAPITAL - 1.0) * 100.0),
        "rebased_end_equity": float(equity.iloc[-1]),
        "rebased_total_return_pct": float((equity.iloc[-1] / CAPITAL - 1.0) * 100.0),
        "rebased_cagr_pct": _cagr_pct(equity, dates),
        "rebased_max_dd_pct": float(dd.min()),
        "rebased_sharpe": _sharpe(equity),
        "rebased_min_equity": float(equity.min()),
        "max_broker10_margin_to_rebased_equity_pct": float(margin.max()),
        "p95_broker10_margin_to_rebased_equity_pct": float(margin.quantile(0.95)),
        "days_over_100pct": int(margin.gt(100.0 + 1e-9).sum()),
        "days_over_90pct": int(margin.gt(90.0 + 1e-9).sum()),
        "total_slippage": float(ordered["total_slippage"].sum()),
        "total_trade_count": float(ordered["trade_count"].sum()),
        "nonzero_daily_win_rate_pct": float(nonzero_pnl.gt(0.0).mean() * 100.0) if len(nonzero_pnl) else 0.0,
        "forced_margin_deleverage_count": event_count,
        "forced_margin_deleverage_closed_volume": event_volume,
        "dd40_pass": int(float(dd.min()) >= -40.0),
        "broker10_100_pass": int(margin.max() <= 100.0 + 1e-9),
        "broker10_90_watch_pass": int(margin.max() < 90.0),
        "account_survival_pass": int(equity.min() > 0.0),
        "deployable_pass": int(float(dd.min()) >= -40.0 and margin.max() <= 100.0 + 1e-9 and equity.min() > 0.0),
        "caveat": caveat,
    }

    curve = pd.DataFrame(
        {
            "date": dates,
            "variant": spec.capital.variant,
            "window_name": window_name,
            "window_label": window_label,
            "window_group": group,
            "source_name": source_name,
            "rebased_equity": equity,
            "rebased_nav": equity / CAPITAL,
            "drawdown_pct": dd,
            "broker10_margin_to_rebased_equity_pct": margin,
            "net_pnl": net_pnl,
            "trade_count": ordered["trade_count"].astype(float),
            "total_slippage": ordered["total_slippage"].astype(float),
        }
    )

    cost_rows: list[dict[str, Any]] = []
    cumulative_slippage = ordered["total_slippage"].astype(float).cumsum()
    for multiplier in (1.0, 2.0, 3.0):
        stressed = equity - cumulative_slippage * max(0.0, multiplier - 1.0)
        stressed_dd = _drawdown_pct(stressed)
        stressed_margin = ordered["broker10_total_margin_exact"].astype(float) / stressed.replace(0.0, np.nan) * 100.0
        stressed_margin = stressed_margin.replace([np.inf, -np.inf], np.nan).fillna(0.0)
        cost_rows.append(
            {
                "variant": spec.capital.variant,
                "window_name": window_name,
                "window_label": window_label,
                "cost_multiplier": multiplier,
                "end_equity": float(stressed.iloc[-1]),
                "total_return_pct": float((stressed.iloc[-1] / CAPITAL - 1.0) * 100.0),
                "max_dd_pct": float(stressed_dd.min()),
                "sharpe": _sharpe(stressed),
                "max_broker10_margin_to_equity_pct": float(stressed_margin.max()),
                "days_over_100pct": int(stressed_margin.gt(100.0 + 1e-9).sum()),
                "account_survival_pass": int(stressed.min() > 0.0),
                "deployable_pass": int(stressed_dd.min() >= -40.0 and stressed_margin.max() <= 100.0 + 1e-9 and stressed.min() > 0.0),
            }
        )
    return summary, curve, cost_rows


def _period_metrics(group: pd.DataFrame, *, name: str, label: str, period_group: str, source_name: str, variant: str) -> dict[str, Any]:
    ordered = group.sort_values("date").reset_index(drop=True)
    if ordered.empty:
        raise ValueError(f"empty period: {name}")
    dates = ordered["date"]
    net_pnl = ordered["net_pnl"].astype(float)
    end_equity = ordered["rebased_equity"].astype(float)
    start_equity = float(end_equity.iloc[0] - net_pnl.iloc[0])
    path = pd.Series([start_equity] + end_equity.tolist())
    dd = _drawdown_pct(path)
    margin = ordered["broker10_margin_to_rebased_equity_pct"].astype(float)
    nonzero_pnl = net_pnl[net_pnl.abs().gt(1e-12)]
    return {
        "variant": variant,
        "window_name": name,
        "window_label": label,
        "window_group": period_group,
        "source_name": source_name,
        "analysis_start": pd.Timestamp(dates.iloc[0]).date().isoformat(),
        "analysis_end": pd.Timestamp(dates.iloc[-1]).date().isoformat(),
        "trading_days": int(len(ordered)),
        "period_start_equity": start_equity,
        "period_end_equity": float(end_equity.iloc[-1]),
        "period_pnl": float(net_pnl.sum()),
        "period_pnl_on_500k_pct": float(net_pnl.sum() / CAPITAL * 100.0),
        "period_return_pct": float((end_equity.iloc[-1] / max(start_equity, 1e-9) - 1.0) * 100.0),
        "period_max_dd_pct": float(dd.min()),
        "period_sharpe": _sharpe(pd.Series(path)),
        "max_broker10_margin_to_equity_pct": float(margin.max()),
        "days_over_100pct": int(margin.gt(100.0 + 1e-9).sum()),
        "days_over_90pct": int(margin.gt(90.0 + 1e-9).sum()),
        "total_trade_count": float(ordered["trade_count"].sum()),
        "total_slippage": float(ordered["total_slippage"].sum()),
        "nonzero_daily_win_rate_pct": float(nonzero_pnl.gt(0.0).mean() * 100.0) if len(nonzero_pnl) else 0.0,
    }


def _annual_monthly(full_curve: pd.DataFrame, source_name: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    ordered = full_curve.sort_values("date").copy()
    ordered["year"] = pd.to_datetime(ordered["date"]).dt.year.astype(str)
    ordered["month"] = pd.to_datetime(ordered["date"]).dt.to_period("M").astype(str)
    variant = str(ordered["variant"].iloc[0])
    annual = [
        _period_metrics(group, name=f"year_{year}", label=f"{year}年度", period_group="calendar_year", source_name=source_name, variant=variant)
        for year, group in ordered.groupby("year", sort=True)
    ]
    monthly = [
        _period_metrics(group, name=f"month_{month}", label=f"{month}月度", period_group="calendar_month", source_name=source_name, variant=variant)
        for month, group in ordered.groupby("month", sort=True)
    ]
    return pd.DataFrame(annual), pd.DataFrame(monthly)


def _rolling_metrics(full_curve: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for variant, group in full_curve.groupby("variant", sort=False):
        ordered = group.sort_values("date").reset_index(drop=True)
        for holding_days in (63, 126, 252):
            returns: list[float] = []
            dds: list[float] = []
            starts: list[str] = []
            ends: list[str] = []
            for start in range(0, len(ordered) - holding_days + 1):
                window = ordered.iloc[start : start + holding_days].copy()
                equity = window["rebased_equity"].astype(float).reset_index(drop=True)
                if len(equity) < 2 or float(equity.iloc[0]) <= 0:
                    continue
                returns.append(float((equity.iloc[-1] / equity.iloc[0] - 1.0) * 100.0))
                dds.append(float(_drawdown_pct(equity).min()))
                starts.append(pd.Timestamp(window["date"].iloc[0]).date().isoformat())
                ends.append(pd.Timestamp(window["date"].iloc[-1]).date().isoformat())
            if returns:
                ret_series = pd.Series(returns)
                worst_idx = int(ret_series.idxmin())
                rows.append(
                    {
                        "variant": variant,
                        "holding_days": holding_days,
                        "sample_count": int(len(returns)),
                        "min_return_pct": float(ret_series.min()),
                        "p05_return_pct": float(ret_series.quantile(0.05)),
                        "median_return_pct": float(ret_series.median()),
                        "positive_rate_pct": float(ret_series.gt(0.0).mean() * 100.0),
                        "min_window_dd_pct": float(min(dds)),
                        "worst_return_start": starts[worst_idx],
                        "worst_return_end": ends[worst_idx],
                    }
                )
    return pd.DataFrame(rows)


def _comparison(summary: pd.DataFrame, cost: pd.DataFrame) -> pd.DataFrame:
    base = summary[summary["variant"].eq(VARIANT_NO_AG)].set_index("window_name")
    plus = summary[summary["variant"].eq(VARIANT_PLUS_AG)].set_index("window_name")
    rows: list[dict[str, Any]] = []
    for name in plus.index:
        if name not in base.index:
            continue
        brow = base.loc[name]
        crow = plus.loc[name]
        rows.append(
            {
                "window_name": name,
                "window_label": crow["window_label"],
                "window_group": crow["window_group"],
                "no_ag_return_pct": float(brow["rebased_total_return_pct"]),
                "plus_ag_return_pct": float(crow["rebased_total_return_pct"]),
                "delta_return_pct": float(crow["rebased_total_return_pct"] - brow["rebased_total_return_pct"]),
                "no_ag_max_dd_pct": float(brow["rebased_max_dd_pct"]),
                "plus_ag_max_dd_pct": float(crow["rebased_max_dd_pct"]),
                "delta_max_dd_pct": float(crow["rebased_max_dd_pct"] - brow["rebased_max_dd_pct"]),
                "no_ag_sharpe": float(brow["rebased_sharpe"]),
                "plus_ag_sharpe": float(crow["rebased_sharpe"]),
                "delta_sharpe": float(crow["rebased_sharpe"] - brow["rebased_sharpe"]),
                "no_ag_trades": float(brow["total_trade_count"]),
                "plus_ag_trades": float(crow["total_trade_count"]),
                "delta_trades": float(crow["total_trade_count"] - brow["total_trade_count"]),
                "no_ag_slippage": float(brow["total_slippage"]),
                "plus_ag_slippage": float(crow["total_slippage"]),
                "delta_slippage": float(crow["total_slippage"] - brow["total_slippage"]),
                "no_ag_margin_peak_pct": float(brow["max_broker10_margin_to_rebased_equity_pct"]),
                "plus_ag_margin_peak_pct": float(crow["max_broker10_margin_to_rebased_equity_pct"]),
                "delta_margin_peak_pct": float(crow["max_broker10_margin_to_rebased_equity_pct"] - brow["max_broker10_margin_to_rebased_equity_pct"]),
            }
        )
    base_cost = cost[(cost["variant"].eq(VARIANT_NO_AG)) & (cost["cost_multiplier"].eq(2.0))].set_index("window_name")
    plus_cost = cost[(cost["variant"].eq(VARIANT_PLUS_AG)) & (cost["cost_multiplier"].eq(2.0))].set_index("window_name")
    for row in rows:
        name = str(row["window_name"])
        if name in base_cost.index and name in plus_cost.index:
            row["no_ag_2x_max_dd_pct"] = float(base_cost.loc[name, "max_dd_pct"])
            row["plus_ag_2x_max_dd_pct"] = float(plus_cost.loc[name, "max_dd_pct"])
            row["delta_2x_max_dd_pct"] = float(plus_cost.loc[name, "max_dd_pct"] - base_cost.loc[name, "max_dd_pct"])
    return pd.DataFrame(rows)


def _ag_activity(positions: pd.DataFrame, usage: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    pos = positions.copy()
    if not pos.empty:
        pos["date"] = pd.to_datetime(pos["date"], errors="coerce").dt.normalize()
        pos = pos[pos["vt_symbol"].astype(str).str.startswith("ag")].copy()
        active = pos[pd.to_numeric(pos.get("end_pos", 0.0), errors="coerce").fillna(0.0).abs().gt(0)]
        rows.append(
            {
                "scope": "full_positions",
                "ag_net_pnl": float(pd.to_numeric(pos.get("net_pnl", 0.0), errors="coerce").fillna(0.0).sum()),
                "ag_slippage": float(pd.to_numeric(pos.get("slippage", 0.0), errors="coerce").fillna(0.0).sum()),
                "ag_trade_count": float(pd.to_numeric(pos.get("trade_count", 0.0), errors="coerce").fillna(0.0).sum()),
                "ag_active_days": int(active["date"].nunique()),
                "ag_first_active_date": active["date"].min().date().isoformat() if not active.empty else "",
                "ag_last_active_date": active["date"].max().date().isoformat() if not active.empty else "",
            }
        )
    if not usage.empty:
        ag_usage = usage[usage["vt_symbol"].astype(str).str.startswith("ag")].copy()
        rows.append(
            {
                "scope": "full_trade_usage",
                "ag_net_pnl": 0.0,
                "ag_slippage": 0.0,
                "ag_trade_count": float(pd.to_numeric(ag_usage.get("order_volume", 0.0), errors="coerce").fillna(0.0).sum()),
                "ag_active_days": int(pd.to_datetime(ag_usage.get("fill_date"), errors="coerce").dt.normalize().nunique()) if not ag_usage.empty else 0,
                "ag_first_active_date": str(ag_usage["fill_date"].min()) if not ag_usage.empty else "",
                "ag_last_active_date": str(ag_usage["fill_date"].max()) if not ag_usage.empty else "",
            }
        )
    return pd.DataFrame(rows)


def _checks(summary: pd.DataFrame, cost: pd.DataFrame, comparison: pd.DataFrame, rolling: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for variant in (VARIANT_NO_AG, VARIANT_PLUS_AG):
        full = summary[(summary["variant"].eq(variant)) & (summary["window_name"].eq("full_2020_20260430"))]
        cost2 = cost[(cost["variant"].eq(variant)) & (cost["window_name"].eq("full_2020_20260430")) & (cost["cost_multiplier"].eq(2.0))]
        if not full.empty:
            row = full.iloc[0]
            rows.extend(
                [
                    {
                        "variant": variant,
                        "check_name": "full_dd40",
                        "status": "pass" if float(row["rebased_max_dd_pct"]) >= -40.0 else "fail",
                        "value": float(row["rebased_max_dd_pct"]),
                        "threshold": ">= -40",
                        "comment": "全周期正常成本最大回撤。",
                    },
                    {
                        "variant": variant,
                        "check_name": "full_margin100",
                        "status": "pass" if int(row["days_over_100pct"]) == 0 else "fail",
                        "value": int(row["days_over_100pct"]),
                        "threshold": "0 days",
                        "comment": "broker10保证金不穿100%。",
                    },
                    {
                        "variant": variant,
                        "check_name": "full_return_positive",
                        "status": "pass" if float(row["rebased_total_return_pct"]) > 0 else "fail",
                        "value": float(row["rebased_total_return_pct"]),
                        "threshold": "> 0",
                        "comment": "低风险倍率不应把长期收益压成负。",
                    },
                ]
            )
        if not cost2.empty:
            row = cost2.iloc[0]
            rows.append(
                {
                    "variant": variant,
                    "check_name": "full_2x_cost_dd40",
                    "status": "pass" if float(row["max_dd_pct"]) >= -40.0 else "fail",
                    "value": float(row["max_dd_pct"]),
                    "threshold": ">= -40",
                    "comment": "全周期2x成本压力最大回撤。",
                }
            )
        roll = rolling[rolling["variant"].eq(variant)]
        if not roll.empty:
            rows.append(
                {
                    "variant": variant,
                    "check_name": "rolling_p05_return_min",
                    "status": "watch" if float(roll["p05_return_pct"].min()) < 0 else "pass",
                    "value": float(roll["p05_return_pct"].min()),
                    "threshold": ">= 0 preferred",
                    "comment": "短持有左尾体验。",
                }
            )
    full_cmp = comparison[comparison["window_name"].eq("full_2020_20260430")]
    if not full_cmp.empty:
        row = full_cmp.iloc[0]
        rows.append(
            {
                "variant": "plus_vs_no_ag",
                "check_name": "plus_ag_full_return_improves",
                "status": "pass" if float(row["delta_return_pct"]) > 0 else "fail",
                "value": float(row["delta_return_pct"]),
                "threshold": "> 0",
                "comment": "固定加ag至少应提升50万/risk005全周期收益。",
            }
        )
        rows.append(
            {
                "variant": "plus_vs_no_ag",
                "check_name": "plus_ag_sharpe_not_worse",
                "status": "pass" if float(row["delta_sharpe"]) >= -0.03 else "fail",
                "value": float(row["delta_sharpe"]),
                "threshold": ">= -0.03",
                "comment": "固定加ag不应明显伤害风险收益比。",
            }
        )
    return pd.DataFrame(rows)


def _plot(curves: pd.DataFrame, comparison: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(16, 10), dpi=160)
    ax_nav, ax_dd, ax_delta, ax_margin = axes.flatten()
    full = curves[curves["window_name"].eq("full_2020_20260430")].copy()
    for variant, group in full.groupby("variant", sort=False):
        group = group.sort_values("date")
        ax_nav.plot(pd.to_datetime(group["date"]), group["rebased_nav"], linewidth=1.1, label=variant)
        ax_dd.plot(pd.to_datetime(group["date"]), group["drawdown_pct"], linewidth=1.0, label=variant)
        ax_margin.plot(pd.to_datetime(group["date"]), group["broker10_margin_to_rebased_equity_pct"], linewidth=1.0, label=variant)
    ax_nav.set_title("Full NAV")
    ax_dd.set_title("Full drawdown")
    ax_delta.set_title("Plus ag return delta")
    ax_margin.set_title("Broker10 margin / equity")
    for ax in (ax_nav, ax_dd, ax_margin):
        ax.grid(alpha=0.25)
        ax.legend(fontsize=8)
    ax_dd.axhline(-40.0, color="#111111", linestyle="--", linewidth=0.8)
    ax_margin.axhline(90.0, color="#d62728", linestyle="--", linewidth=0.8)
    ax_margin.axhline(100.0, color="#8c0000", linestyle="--", linewidth=0.8)
    view = comparison[comparison["window_group"].isin(["historical_full", "start_year", "market_phase"])]
    ax_delta.bar(view["window_name"], view["delta_return_pct"].astype(float), color="#2ca02c")
    ax_delta.axhline(0.0, color="#333333", linewidth=0.8)
    ax_delta.tick_params(axis="x", rotation=35)
    ax_delta.grid(axis="y", alpha=0.25)
    fig.suptitle("Stage666 500k risk005 no-ag vs plus-ag", fontsize=14)
    fig.tight_layout()
    fig.savefig(CHART_PATH)
    plt.close(fig)


def _write_report(
    summary: pd.DataFrame,
    cost: pd.DataFrame,
    comparison: pd.DataFrame,
    rolling: pd.DataFrame,
    checks: pd.DataFrame,
    ag_activity: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    key_cols = [
        "variant",
        "window_name",
        "analysis_start",
        "analysis_end",
        "rebased_end_equity",
        "rebased_total_return_pct",
        "rebased_max_dd_pct",
        "rebased_sharpe",
        "max_broker10_margin_to_rebased_equity_pct",
        "total_slippage",
        "total_trade_count",
        "nonzero_daily_win_rate_pct",
        "deployable_pass",
    ]
    lines = [
        "# Stage666 50万 risk0.05 加/不加 ag 多周期审计",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        f"- line_id：`{LINE_ID}`",
        f"- 当前 official live：`{OFFICIAL_LIVE_VERSION}` / `{OFFICIAL_LIVE_PROFILE_NAME}`",
        "- B：Stage372逻辑，50万，`risk_multiplier=0.05`，不加 `ag`。",
        "- C：B基础上固定加入 `ag.SHFE` 到产品宇宙和每月AI eligibility。",
        "- 本阶段不修改正式配置、不连接 CTP、不调用下单。",
        "",
        "## 检查",
        "",
        _md_table(checks, max_rows=80),
        "",
        "## 多周期结果",
        "",
        _md_table(summary[key_cols], max_rows=120),
        "",
        "## C vs B",
        "",
        _md_table(comparison, max_rows=80),
        "",
        "## 成本压力",
        "",
        _md_table(cost, max_rows=160),
        "",
        "## 滚动窗口",
        "",
        _md_table(rolling, max_rows=60),
        "",
        "## ag 活跃度",
        "",
        _md_table(ag_activity, max_rows=20),
        "",
        "## 决策",
        "",
        f"- 决策：`{decision['decision']}`。",
        f"- 硬失败项：`{', '.join(decision['hard_fail_checks']) or '无'}`。",
        f"- 观察项：`{', '.join(decision['watch_checks']) or '无'}`。",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _run_variant_suite(
    *,
    spec: s653.ForcedVariant,
    metadata: dict[str, Any],
    latest_ai_path: Path,
) -> tuple[list[dict[str, Any]], list[pd.DataFrame], list[dict[str, Any]], pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    summary_rows: list[dict[str, Any]] = []
    curve_frames: list[pd.DataFrame] = []
    cost_rows: list[dict[str, Any]] = []
    full_positions = pd.DataFrame()
    full_usage = pd.DataFrame()
    annual_frames: list[pd.DataFrame] = []
    monthly_frames: list[pd.DataFrame] = []

    for window_name, window_label, group, start, end in s660.WINDOWS:
        analysis_start = pd.Timestamp(start)
        analysis_end = pd.Timestamp(end) if end else pd.Timestamp("2026-04-30")
        print(f"[stage666] {spec.capital.variant} {window_name}: {analysis_start.date()} -> {analysis_end.date()}", flush=True)
        frame, positions, usage, forced_events = _run_window_with_positions(
            spec=spec,
            metadata=metadata,
            analysis_start=analysis_start,
            analysis_end=analysis_end,
        )
        row, curve, costs = _window_metrics(
            frame,
            spec=spec,
            window_name=window_name,
            window_label=window_label,
            group=group,
            source_name=f"{spec.capital.variant}_independent_window",
            caveat="历史窗口独立重跑，50万 fresh capital，risk_multiplier=0.05。",
            forced_events=forced_events,
        )
        summary_rows.append(row)
        curve_frames.append(curve)
        cost_rows.extend(costs)
        if window_name == "full_2020_20260430":
            full_positions = positions.copy()
            full_usage = usage.copy()
            annual, monthly = _annual_monthly(curve, f"{spec.capital.variant}_full_path")
            annual_frames.append(annual)
            monthly_frames.append(monthly)

    print(f"[stage666] {spec.capital.variant} ytd latest-ai", flush=True)
    ytd_frame, ytd_forced = _run_latest_ytd(spec=spec, metadata=metadata, ai_eligibility_path=latest_ai_path)
    ytd_row, ytd_curve, ytd_costs = _window_metrics(
        ytd_frame,
        spec=spec,
        window_name="ytd_2026_latest_ai",
        window_label="2026年初至2026-06-05最新AI池",
        group="latest_ytd",
        source_name=f"{spec.capital.variant}_latest_ai_ytd",
        caveat="最新AI池年初至今影子盘，50万 fresh capital，risk_multiplier=0.05。",
        forced_events=ytd_forced,
    )
    summary_rows.append(ytd_row)
    curve_frames.append(ytd_curve)
    cost_rows.extend(ytd_costs)
    return (
        summary_rows,
        curve_frames,
        cost_rows,
        full_positions,
        full_usage,
        pd.concat(annual_frames, ignore_index=True, sort=False) if annual_frames else pd.DataFrame(),
        pd.concat(monthly_frames, ignore_index=True, sort=False) if monthly_frames else pd.DataFrame(),
    )


def main() -> None:
    prepared = _prepare_inputs()
    no_ag_spec = _base_500k_spec(prepared["base_metadata"])
    plus_ag_spec = _plus_ag_500k_spec(prepared["plus_metadata"])

    all_summary_rows: list[dict[str, Any]] = []
    all_curve_frames: list[pd.DataFrame] = []
    all_cost_rows: list[dict[str, Any]] = []
    annual_frames: list[pd.DataFrame] = []
    monthly_frames: list[pd.DataFrame] = []

    no_summary, no_curves, no_cost, _no_pos, _no_usage, no_annual, no_monthly = _run_variant_suite(
        spec=no_ag_spec,
        metadata=prepared["base_metadata"],
        latest_ai_path=s659.DEFAULT_AI_ELIGIBILITY_PATH.resolve(),
    )
    plus_summary, plus_curves, plus_cost, plus_positions, plus_usage, plus_annual, plus_monthly = _run_variant_suite(
        spec=plus_ag_spec,
        metadata=prepared["plus_metadata"],
        latest_ai_path=LATEST_ELIGIBILITY_PLUS_AG_PATH,
    )

    all_summary_rows.extend(no_summary)
    all_summary_rows.extend(plus_summary)
    all_curve_frames.extend(no_curves)
    all_curve_frames.extend(plus_curves)
    all_cost_rows.extend(no_cost)
    all_cost_rows.extend(plus_cost)
    annual_frames.extend([no_annual, plus_annual])
    monthly_frames.extend([no_monthly, plus_monthly])

    summary = pd.DataFrame(all_summary_rows)
    curves = pd.concat(all_curve_frames, ignore_index=True, sort=False)
    cost = pd.DataFrame(all_cost_rows)
    comparison = _comparison(summary, cost)
    rolling = _rolling_metrics(curves[curves["window_name"].eq("full_2020_20260430")])
    annual = pd.concat([frame for frame in annual_frames if not frame.empty], ignore_index=True, sort=False)
    monthly = pd.concat([frame for frame in monthly_frames if not frame.empty], ignore_index=True, sort=False)
    ag_activity = _ag_activity(plus_positions, plus_usage)
    checks = _checks(summary, cost, comparison, rolling)

    hard_fail_checks = checks[checks["status"].eq("fail")].apply(lambda row: f"{row['variant']}:{row['check_name']}", axis=1).tolist()
    watch_checks = checks[checks["status"].eq("watch")].apply(lambda row: f"{row['variant']}:{row['check_name']}", axis=1).tolist()
    full_cmp = comparison[comparison["window_name"].eq("full_2020_20260430")]
    plus_decision = "plus_ag_rejected"
    if not full_cmp.empty and float(full_cmp.iloc[0]["delta_return_pct"]) > 0 and float(full_cmp.iloc[0]["delta_sharpe"]) >= -0.03:
        plus_decision = "plus_ag_watch_not_auto_promote" if watch_checks else "plus_ag_passes_first_gate"
    decision = {
        "stage": "Stage378",
        "script_stage": "Stage666",
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "official_live_profile": OFFICIAL_LIVE_PROFILE_NAME,
        "arms": {
            "B": f"{VARIANT_NO_AG}: 500k, risk_multiplier=0.05, official Stage372 pool",
            "C": f"{VARIANT_PLUS_AG}: B plus fixed {AG_PRODUCT}",
        },
        "decision": plus_decision,
        "hard_fail_checks": hard_fail_checks,
        "watch_checks": watch_checks,
        "overfitting_reflection": (
            "The 500k/risk005 capital profile is a structural sizing test. Adding ag still has selection-after-review "
            "risk, so it must beat the no-ag arm across broad windows before any promotion."
        ),
        "continued_value_reflection": (
            "The low-risk capital profile is worth measuring because it may address margin/path risk. Fixed ag is only "
            "worth continuing if it improves the no-ag 500k/risk005 control without path damage."
        ),
        "inputs": {
            "base_symbols": prepared["base_symbols"],
            "plus_symbols": prepared["plus_symbols"],
            "historical_eligibility_source": prepared["historical_eligibility_source"],
            "latest_eligibility_source": prepared["latest_eligibility_source"],
            "plus_ag_universe": str(UNIVERSE_PLUS_AG_PATH),
            "plus_ag_historical_eligibility": str(HIST_ELIGIBILITY_PLUS_AG_PATH),
            "plus_ag_latest_eligibility": str(LATEST_ELIGIBILITY_PLUS_AG_PATH),
        },
        "outputs": {
            "summary": str(SUMMARY_PATH),
            "cost": str(COST_PATH),
            "comparison": str(COMPARISON_PATH),
            "rolling": str(ROLLING_PATH),
            "annual": str(ANNUAL_PATH),
            "monthly": str(MONTHLY_PATH),
            "curves": str(CURVES_PATH),
            "ag_activity": str(AG_ACTIVITY_PATH),
            "checks": str(CHECKS_PATH),
            "report": str(REPORT_PATH),
            "chart": str(CHART_PATH),
            "decision": str(DECISION_PATH),
        },
    }

    _plot(curves, comparison)
    _write_report(summary, cost, comparison, rolling, checks, ag_activity, decision)

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    cost.to_csv(COST_PATH, index=False, encoding="utf-8-sig")
    comparison.to_csv(COMPARISON_PATH, index=False, encoding="utf-8-sig")
    rolling.to_csv(ROLLING_PATH, index=False, encoding="utf-8-sig")
    annual.to_csv(ANNUAL_PATH, index=False, encoding="utf-8-sig")
    monthly.to_csv(MONTHLY_PATH, index=False, encoding="utf-8-sig")
    curves.to_csv(CURVES_PATH, index=False, encoding="utf-8-sig")
    ag_activity.to_csv(AG_ACTIVITY_PATH, index=False, encoding="utf-8-sig")
    checks.to_csv(CHECKS_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
