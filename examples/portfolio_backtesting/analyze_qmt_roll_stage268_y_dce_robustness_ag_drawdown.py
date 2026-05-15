from __future__ import annotations

import json
import math
import re
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from qmt_roll_official_stage78_config import OFFICIAL_STAGE78_CAPITAL, build_official_stage78_paths
from run_qmt_roll_backtest import build_summary_row, run_backtest
from run_qmt_roll_selection_long015_volref30_corr_fu_candidate_robustness_backtest import to_markdown_table
from run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest import BASE_RISK_RATIO
from run_qmt_roll_stage267_hot_product_official_add_one_validation import (
    ELIGIBILITY_DIR as STAGE267_ELIGIBILITY_DIR,
    EXPERIMENT_TAG as STAGE267_EXPERIMENT_TAG,
    FIXED_FU_PRODUCT,
    OFFICIAL_AI_STRATEGY_NAME,
    OFFICIAL_BASELINE_NAME,
    UNIVERSE_DIR as STAGE267_UNIVERSE_DIR,
    _experiment_name as stage267_experiment_name,
    _official_products as stage267_official_products,
    _strategy_overrides as stage267_strategy_overrides,
    build_candidate_eligibility,
    build_universe,
)
from qmt_universe import END_DT


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

MODEL_TAG: str = "stage268_y_dce_robustness_ag_drawdown_v1"
OUTPUT_PREFIX: str = "qmt_roll_stage268_y_dce_robustness_ag_drawdown"

Y_PRODUCT: str = "y.DCE"
AG_PRODUCT: str = "ag.SHFE"

START_YEAR_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_y_start_year_{MODEL_TAG}.csv"
QUARTER_COLD_START_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_y_quarter_cold_start_{MODEL_TAG}.csv"
QUARTER_TRUE_RERUN_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_y_quarter_true_rerun_{MODEL_TAG}.csv"
WEAK_WINDOW_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_y_weak_window_backtest_{MODEL_TAG}.csv"
WEAK_ROLLING_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_y_weak_rolling_{MODEL_TAG}.csv"
SLIPPAGE_STRESS_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_y_slippage_stress_{MODEL_TAG}.csv"
AG_PRODUCT_CONTRIB_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_ag_drawdown_product_contrib_{MODEL_TAG}.csv"
AG_YEAR_CONTRIB_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_ag_year_contrib_{MODEL_TAG}.csv"
AG_ENTRY_DIAGNOSTICS_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_ag_entry_diagnostics_{MODEL_TAG}.csv"
SUMMARY_JSON_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.json"
REPORT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
RUN_CACHE_DIR: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_run_cache_{MODEL_TAG}"
RUN_LOG_DIR: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_logs_{MODEL_TAG}"

BASE_DAILY_PATH: Path = OUTPUT_DIR / (
    f"{STAGE267_EXPERIMENT_TAG}_{OFFICIAL_BASELINE_NAME}_daily.csv"
)
Y_DAILY_PATH: Path = OUTPUT_DIR / (
    f"{STAGE267_EXPERIMENT_TAG}_{stage267_experiment_name(Y_PRODUCT)}_daily.csv"
)
AG_DAILY_PATH: Path = OUTPUT_DIR / (
    f"{STAGE267_EXPERIMENT_TAG}_{stage267_experiment_name(AG_PRODUCT)}_daily.csv"
)
BASE_POSITION_CHANGES_PATH: Path = OUTPUT_DIR / (
    f"{STAGE267_EXPERIMENT_TAG}_{OFFICIAL_BASELINE_NAME}_position_changes_2020_2026_04.csv"
)
AG_POSITION_CHANGES_PATH: Path = OUTPUT_DIR / (
    f"{STAGE267_EXPERIMENT_TAG}_{stage267_experiment_name(AG_PRODUCT)}_position_changes_2020_2026_04.csv"
)
AG_TRADES_PATH: Path = OUTPUT_DIR / (
    f"{STAGE267_EXPERIMENT_TAG}_{stage267_experiment_name(AG_PRODUCT)}_trades_2020_2026_04.csv"
)
AG_ENTRY_RISK_PATH: Path = OUTPUT_DIR / (
    f"{STAGE267_EXPERIMENT_TAG}_{stage267_experiment_name(AG_PRODUCT)}_entry_risk_diagnostics_2020_2026_04.csv"
)

SLIPPAGE_MULTIPLIERS: tuple[float, ...] = (1.0, 3.0, 5.0)
TRADING_DAYS_PER_YEAR: int = 240
START_YEARS: tuple[int, ...] = (2020, 2021, 2022, 2023, 2024, 2025, 2026)
ROLLING_WINDOWS: tuple[int, ...] = (63, 126, 252)
TRUE_QUARTER_RERUN_COUNT: int = 4


def _safe_float(value: Any) -> float:
    try:
        if pd.isna(value):
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _load_daily(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    df = pd.read_csv(path)
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    for column in ["net_pnl", "balance", "trade_count", "slippage", "drawdown", "ddpercent"]:
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce").fillna(0.0)
    return df.sort_values("date").reset_index(drop=True)


def _metrics_from_net_pnl(
    df: pd.DataFrame,
    initial_balance: float,
    net_pnl_column: str = "net_pnl",
) -> dict[str, float]:
    if df.empty:
        return {
            "end_balance": float(initial_balance),
            "total_return_pct": 0.0,
            "max_dd_percent": 0.0,
            "sharpe_ratio": 0.0,
            "total_net_pnl": 0.0,
            "total_slippage": 0.0,
            "total_trade_count": 0.0,
            "win_rate_day_pct": 0.0,
        }
    net_pnl = pd.to_numeric(df[net_pnl_column], errors="coerce").fillna(0.0).to_numpy(dtype=float)
    equity = float(initial_balance) + np.cumsum(net_pnl)
    previous = np.concatenate([[float(initial_balance)], equity[:-1]])
    returns = np.divide(net_pnl, previous, out=np.zeros_like(net_pnl), where=previous != 0.0)
    high = np.maximum.accumulate(equity)
    drawdown_pct = np.divide(equity - high, high, out=np.zeros_like(equity), where=high != 0.0) * 100.0
    std = float(np.std(returns, ddof=1)) if len(returns) > 1 else 0.0
    sharpe = float(np.mean(returns) / std * math.sqrt(TRADING_DAYS_PER_YEAR)) if std > 0 else 0.0
    return {
        "end_balance": float(equity[-1]),
        "total_return_pct": float((equity[-1] / initial_balance - 1.0) * 100.0) if initial_balance else 0.0,
        "max_dd_percent": float(drawdown_pct.min()) if len(drawdown_pct) else 0.0,
        "sharpe_ratio": sharpe,
        "total_net_pnl": float(net_pnl.sum()),
        "total_slippage": float(pd.to_numeric(df.get("slippage", 0.0), errors="coerce").fillna(0.0).sum()),
        "total_trade_count": float(pd.to_numeric(df.get("trade_count", 0.0), errors="coerce").fillna(0.0).sum()),
        "win_rate_day_pct": float((net_pnl > 0).mean() * 100.0),
    }


def _drawdown_event(daily: pd.DataFrame) -> dict[str, Any]:
    if daily.empty:
        return {}
    high = daily["balance"].cummax()
    drawdown = daily["balance"] - high
    trough_idx = int(drawdown.idxmin())
    peak_balance = float(high.iloc[trough_idx])
    peak_candidates = daily.loc[:trough_idx]
    peak_idx = int(peak_candidates[peak_candidates["balance"].eq(peak_balance)].index[-1])
    recovery = daily.loc[trough_idx:]
    recovered = recovery[recovery["balance"] >= peak_balance]
    recovery_date = "" if recovered.empty else recovered["date"].iloc[0].date().isoformat()
    return {
        "peak_date": daily["date"].iloc[peak_idx].date().isoformat(),
        "trough_date": daily["date"].iloc[trough_idx].date().isoformat(),
        "recovery_date": recovery_date,
        "peak_balance": peak_balance,
        "trough_balance": float(daily["balance"].iloc[trough_idx]),
        "drawdown": float(drawdown.iloc[trough_idx]),
        "drawdown_pct": float(drawdown.iloc[trough_idx] / peak_balance * 100.0) if peak_balance else 0.0,
        "duration_days": int((daily["date"].iloc[trough_idx] - daily["date"].iloc[peak_idx]).days),
    }


def _ensure_stage267_paths(product: str | None) -> tuple[Path, Path, str, tuple[str, ...]]:
    official_products, _, official_eligibility_path = stage267_official_products()
    experiment_name = stage267_experiment_name(product)
    selected_products = set(official_products)
    extra_products: tuple[str, ...] = ()
    if product:
        selected_products.add(product)
        extra_products = (product,)
    universe_path = STAGE267_UNIVERSE_DIR / f"{STAGE267_EXPERIMENT_TAG}_{experiment_name}_universe.csv"
    if not universe_path.exists():
        universe_path = build_universe(experiment_name, selected_products)
    if extra_products:
        eligibility_path = STAGE267_ELIGIBILITY_DIR / f"{STAGE267_EXPERIMENT_TAG}_{experiment_name}_eligibility.csv"
        if not eligibility_path.exists():
            eligibility_path, strategy_name = build_candidate_eligibility(
                experiment_name,
                official_eligibility_path,
                extra_products,
            )
        else:
            strategy_name = f"{STAGE267_EXPERIMENT_TAG}_{experiment_name}_entry_filter"
    else:
        _, eligibility_path = build_official_stage78_paths()
        strategy_name = OFFICIAL_AI_STRATEGY_NAME
    risk_state_products = tuple(sorted({FIXED_FU_PRODUCT, *extra_products}))
    return universe_path, eligibility_path, strategy_name, risk_state_products


def _overrides_for(product: str | None) -> dict[str, Any]:
    universe_path, eligibility_path, strategy_name, risk_state_products = _ensure_stage267_paths(product)
    return stage267_strategy_overrides(universe_path, eligibility_path, strategy_name, risk_state_products)


def _run_strategy_window(
    product: str | None,
    window_name: str,
    analysis_start: datetime,
    analysis_end: datetime,
    window_type: str,
) -> dict[str, Any]:
    label = "A_static18_fu" if product is None else f"C_plus_{product.replace('.', '_')}"
    cache_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", f"{window_type}_{window_name}_{label}.json")
    cache_path = RUN_CACHE_DIR / cache_name
    log_path = RUN_LOG_DIR / cache_name.replace(".json", ".log")
    if cache_path.exists():
        print(f"[stage268] cache_hit {window_type} {window_name} {label}", flush=True)
        return json.loads(cache_path.read_text(encoding="utf-8"))
    print(f"[stage268] {window_type} {window_name} {label} {analysis_start.date()} -> {analysis_end.date()}", flush=True)
    RUN_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    RUN_LOG_DIR.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8") as log_file:
        with redirect_stdout(log_file), redirect_stderr(log_file):
            _, _, statistics = run_backtest(
                risk_ratio=BASE_RISK_RATIO,
                strategy_overrides=_overrides_for(product),
                analysis_start=analysis_start,
                analysis_end=analysis_end,
                capital=OFFICIAL_STAGE78_CAPITAL,
                save_artifacts=False,
                include_start_year_sweep=False,
                file_prefix=f"{OUTPUT_PREFIX}_{window_type}_{window_name}_{label}",
                chart_title=f"Stage268 {window_type} {window_name} {label}",
            )
    row = build_summary_row(
        statistics,
        analysis_start=analysis_start,
        analysis_end=analysis_end,
        window_type=window_type,
        window_name=window_name,
        strategy_label=label,
        candidate_product=product or "",
        total_net_pnl=float(statistics.get("total_net_pnl", 0) or 0),
        total_slippage=float(statistics.get("total_slippage", 0) or 0),
        total_commission=float(statistics.get("total_commission", 0) or 0),
        profit_days=int(statistics.get("profit_days", 0) or 0),
        loss_days=int(statistics.get("loss_days", 0) or 0),
    )
    cache_path.write_text(json.dumps(row, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return row


def _add_vs_a_diff(df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    key_cols = ["window_type", "window_name", "analysis_start", "analysis_end"]
    for _, group in df.groupby(key_cols, dropna=False, sort=False):
        if set(group["strategy_label"]) < {"A_static18_fu", "C_plus_y_DCE"}:
            continue
        base = group[group["strategy_label"].eq("A_static18_fu")].iloc[0]
        cand = group[group["strategy_label"].eq("C_plus_y_DCE")].iloc[0]
        payload = cand.to_dict()
        payload["A_end_balance"] = float(base["end_balance"])
        payload["A_total_return_pct"] = float(base["total_return_pct"])
        payload["A_max_dd_percent"] = float(base["max_dd_percent"])
        payload["A_sharpe_ratio"] = float(base["sharpe_ratio"])
        payload["A_total_slippage"] = float(base.get("total_slippage", 0))
        payload["A_total_trade_count"] = float(base["total_trade_count"])
        payload["end_balance_diff_vs_A"] = float(cand["end_balance"] - base["end_balance"])
        payload["return_diff_vs_A"] = float(cand["total_return_pct"] - base["total_return_pct"])
        payload["dd_diff_vs_A"] = float(cand["max_dd_percent"] - base["max_dd_percent"])
        payload["sharpe_diff_vs_A"] = float(cand["sharpe_ratio"] - base["sharpe_ratio"])
        payload["trade_count_diff_vs_A"] = float(cand["total_trade_count"] - base["total_trade_count"])
        payload["slippage_diff_vs_A"] = float(cand.get("total_slippage", 0) - base.get("total_slippage", 0))
        rows.append(payload)
    return pd.DataFrame(rows)


def _start_year_sweep() -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for year in START_YEARS:
        start = datetime(year, 1, 1)
        if start > END_DT:
            continue
        window_name = f"since_{year}"
        rows.append(_run_strategy_window(None, window_name, start, END_DT, "start_year"))
        rows.append(_run_strategy_window(Y_PRODUCT, window_name, start, END_DT, "start_year"))
    return _add_vs_a_diff(pd.DataFrame(rows))


def _quarter_starts() -> list[tuple[str, datetime]]:
    starts: list[tuple[str, datetime]] = []
    for year in range(2020, END_DT.year + 1):
        for month in (1, 4, 7, 10):
            start = datetime(year, month, 1)
            if start > END_DT:
                continue
            starts.append((f"{year}Q{(month - 1) // 3 + 1}", start))
    return starts


def _daily_window_summary_row(
    metrics: dict[str, float],
    *,
    analysis_start: datetime,
    analysis_end: datetime,
    window_type: str,
    window_name: str,
    strategy_label: str,
    candidate_product: str,
) -> dict[str, Any]:
    return {
        "analysis_start": analysis_start.date().isoformat(),
        "analysis_end": analysis_end.date().isoformat(),
        "window_type": window_type,
        "window_name": window_name,
        "strategy_label": strategy_label,
        "candidate_product": candidate_product,
        "end_balance": metrics["end_balance"],
        "total_return_pct": metrics["total_return_pct"],
        "max_dd_percent": metrics["max_dd_percent"],
        "sharpe_ratio": metrics["sharpe_ratio"],
        "total_net_pnl": metrics["total_net_pnl"],
        "total_slippage": metrics["total_slippage"],
        "total_trade_count": metrics["total_trade_count"],
        "win_rate_day_pct": metrics["win_rate_day_pct"],
    }


def _quarter_cold_start_sweep() -> pd.DataFrame:
    base = _load_daily(BASE_DAILY_PATH)
    y = _load_daily(Y_DAILY_PATH)
    rows: list[dict[str, Any]] = []
    for window_name, start in _quarter_starts():
        base_part = base[(base["date"] >= pd.Timestamp(start)) & (base["date"] <= pd.Timestamp(END_DT))].copy()
        y_part = y[(y["date"] >= pd.Timestamp(start)) & (y["date"] <= pd.Timestamp(END_DT))].copy()
        rows.append(
            _daily_window_summary_row(
                _metrics_from_net_pnl(base_part, OFFICIAL_STAGE78_CAPITAL),
                analysis_start=start,
                analysis_end=END_DT,
                window_type="quarter_path_reset",
                window_name=window_name,
                strategy_label="A_static18_fu",
                candidate_product="",
            )
        )
        rows.append(
            _daily_window_summary_row(
                _metrics_from_net_pnl(y_part, OFFICIAL_STAGE78_CAPITAL),
                analysis_start=start,
                analysis_end=END_DT,
                window_type="quarter_path_reset",
                window_name=window_name,
                strategy_label="C_plus_y_DCE",
                candidate_product=Y_PRODUCT,
            )
        )
    return _add_vs_a_diff(pd.DataFrame(rows))


def _quarter_true_rerun_sweep(quarter_path_reset: pd.DataFrame) -> pd.DataFrame:
    if quarter_path_reset.empty:
        return pd.DataFrame()
    selected = quarter_path_reset.sort_values(
        ["return_diff_vs_A", "dd_diff_vs_A"],
        ascending=[True, True],
    ).head(TRUE_QUARTER_RERUN_COUNT)
    rows: list[dict[str, Any]] = []
    for _, row in selected.iterrows():
        window_name = str(row["window_name"])
        start = pd.Timestamp(row["analysis_start"]).to_pydatetime()
        rows.append(_run_strategy_window(None, window_name, start, END_DT, "quarter_true_rerun"))
        rows.append(_run_strategy_window(Y_PRODUCT, window_name, start, END_DT, "quarter_true_rerun"))
    return _add_vs_a_diff(pd.DataFrame(rows))


def _weak_window_sweep() -> pd.DataFrame:
    windows: list[tuple[str, datetime, datetime]] = [
        ("pre_ai_2020_2021", datetime(2020, 1, 1), datetime(2021, 12, 31)),
        ("post_signal_2022_2026", datetime(2022, 2, 7), END_DT),
        ("early_ai_2022_2023", datetime(2022, 2, 7), datetime(2023, 12, 31)),
        ("trend_rich_2024_2025", datetime(2024, 1, 1), datetime(2025, 12, 31)),
        ("latest_2026", datetime(2026, 1, 1), END_DT),
    ]
    rows: list[dict[str, Any]] = []
    for window_name, start, end in windows:
        rows.append(_run_strategy_window(None, window_name, start, end, "weak_window"))
        rows.append(_run_strategy_window(Y_PRODUCT, window_name, start, end, "weak_window"))
    return _add_vs_a_diff(pd.DataFrame(rows))


def _slippage_stress() -> pd.DataFrame:
    base = _load_daily(BASE_DAILY_PATH)
    y = _load_daily(Y_DAILY_PATH)
    rows: list[dict[str, Any]] = []
    for start_name, start_date in [
        ("full_2020_2026", pd.Timestamp("2020-01-01")),
        ("post_signal_2022_2026", pd.Timestamp("2022-02-07")),
        ("latest_2026", pd.Timestamp("2026-01-01")),
    ]:
        base_part = base[base["date"] >= start_date].copy()
        y_part = y[y["date"] >= start_date].copy()
        for multiplier in SLIPPAGE_MULTIPLIERS:
            base_stressed = base_part.copy()
            y_stressed = y_part.copy()
            base_stressed["stressed_net_pnl"] = base_stressed["net_pnl"] - (multiplier - 1.0) * base_stressed["slippage"]
            y_stressed["stressed_net_pnl"] = y_stressed["net_pnl"] - (multiplier - 1.0) * y_stressed["slippage"]
            base_metrics = _metrics_from_net_pnl(base_stressed, OFFICIAL_STAGE78_CAPITAL, "stressed_net_pnl")
            y_metrics = _metrics_from_net_pnl(y_stressed, OFFICIAL_STAGE78_CAPITAL, "stressed_net_pnl")
            rows.append(
                {
                    "start_name": start_name,
                    "start_date": start_date.date().isoformat(),
                    "slippage_multiplier": multiplier,
                    "y_end_balance": y_metrics["end_balance"],
                    "A_end_balance": base_metrics["end_balance"],
                    "end_balance_diff_vs_A": y_metrics["end_balance"] - base_metrics["end_balance"],
                    "y_total_return_pct": y_metrics["total_return_pct"],
                    "A_total_return_pct": base_metrics["total_return_pct"],
                    "return_diff_vs_A": y_metrics["total_return_pct"] - base_metrics["total_return_pct"],
                    "y_max_dd_percent": y_metrics["max_dd_percent"],
                    "A_max_dd_percent": base_metrics["max_dd_percent"],
                    "dd_diff_vs_A": y_metrics["max_dd_percent"] - base_metrics["max_dd_percent"],
                    "y_sharpe_ratio": y_metrics["sharpe_ratio"],
                    "A_sharpe_ratio": base_metrics["sharpe_ratio"],
                    "sharpe_diff_vs_A": y_metrics["sharpe_ratio"] - base_metrics["sharpe_ratio"],
                    "y_total_slippage": y_metrics["total_slippage"] * multiplier,
                    "A_total_slippage": base_metrics["total_slippage"] * multiplier,
                }
            )
    return pd.DataFrame(rows)


def _rolling_window_metrics() -> pd.DataFrame:
    base = _load_daily(BASE_DAILY_PATH)
    y = _load_daily(Y_DAILY_PATH)
    merged = base[["date", "net_pnl", "slippage", "trade_count"]].merge(
        y[["date", "net_pnl", "slippage", "trade_count"]],
        on="date",
        suffixes=("_A", "_y"),
    )
    rows: list[dict[str, Any]] = []
    for window in ROLLING_WINDOWS:
        if len(merged) < window:
            continue
        for end_idx in range(window - 1, len(merged)):
            part = merged.iloc[end_idx - window + 1 : end_idx + 1].copy()
            base_frame = pd.DataFrame(
                {
                    "net_pnl": part["net_pnl_A"],
                    "slippage": part["slippage_A"],
                    "trade_count": part["trade_count_A"],
                }
            )
            y_frame = pd.DataFrame(
                {
                    "net_pnl": part["net_pnl_y"],
                    "slippage": part["slippage_y"],
                    "trade_count": part["trade_count_y"],
                }
            )
            base_metrics = _metrics_from_net_pnl(base_frame, OFFICIAL_STAGE78_CAPITAL)
            y_metrics = _metrics_from_net_pnl(y_frame, OFFICIAL_STAGE78_CAPITAL)
            rows.append(
                {
                    "window_days": window,
                    "start_date": part["date"].iloc[0].date().isoformat(),
                    "end_date": part["date"].iloc[-1].date().isoformat(),
                    "A_total_net_pnl": base_metrics["total_net_pnl"],
                    "y_total_net_pnl": y_metrics["total_net_pnl"],
                    "net_pnl_diff_vs_A": y_metrics["total_net_pnl"] - base_metrics["total_net_pnl"],
                    "A_return_pct": base_metrics["total_return_pct"],
                    "y_return_pct": y_metrics["total_return_pct"],
                    "return_diff_vs_A": y_metrics["total_return_pct"] - base_metrics["total_return_pct"],
                    "A_max_dd_percent": base_metrics["max_dd_percent"],
                    "y_max_dd_percent": y_metrics["max_dd_percent"],
                    "dd_diff_vs_A": y_metrics["max_dd_percent"] - base_metrics["max_dd_percent"],
                    "A_sharpe_ratio": base_metrics["sharpe_ratio"],
                    "y_sharpe_ratio": y_metrics["sharpe_ratio"],
                    "sharpe_diff_vs_A": y_metrics["sharpe_ratio"] - base_metrics["sharpe_ratio"],
                }
            )
    result = pd.DataFrame(rows)
    if result.empty:
        return result
    return result.sort_values(["window_days", "net_pnl_diff_vs_A", "y_return_pct"], ascending=[True, True, True])


def _product_from_vt_symbol(vt_symbol: Any) -> str:
    text = str(vt_symbol)
    if "." not in text:
        return text
    symbol, exchange = text.split(".", 1)
    match = re.match(r"[A-Za-z]+", symbol)
    product = match.group(0) if match else symbol
    return f"{product}.{exchange}"


def _load_position_changes(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    df = pd.read_csv(path)
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    df["product_vt_symbol"] = df["vt_symbol"].map(_product_from_vt_symbol)
    for column in ["net_pnl", "slippage", "trade_count", "turnover", "holding_pnl", "trading_pnl"]:
        df[column] = pd.to_numeric(df[column], errors="coerce").fillna(0.0)
    return df


def _ag_drawdown_analysis() -> tuple[dict[str, Any], pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    base_daily = _load_daily(BASE_DAILY_PATH)
    ag_daily = _load_daily(AG_DAILY_PATH)
    event = _drawdown_event(ag_daily)
    start = pd.Timestamp(event["peak_date"])
    end = pd.Timestamp(event["trough_date"])

    ag_event_daily = ag_daily[(ag_daily["date"] >= start) & (ag_daily["date"] <= end)].copy()
    base_event_daily = base_daily[(base_daily["date"] >= start) & (base_daily["date"] <= end)].copy()
    event["ag_event_net_pnl"] = float(ag_event_daily["net_pnl"].sum())
    event["A_event_net_pnl"] = float(base_event_daily["net_pnl"].sum())
    event["event_net_pnl_diff_vs_A"] = event["ag_event_net_pnl"] - event["A_event_net_pnl"]
    event["ag_event_slippage"] = float(ag_event_daily["slippage"].sum())
    event["A_event_slippage"] = float(base_event_daily["slippage"].sum())
    event["ag_event_trade_count"] = int(ag_event_daily["trade_count"].sum())
    event["A_event_trade_count"] = int(base_event_daily["trade_count"].sum())

    ag_pc = _load_position_changes(AG_POSITION_CHANGES_PATH)
    base_pc = _load_position_changes(BASE_POSITION_CHANGES_PATH)
    ag_period = ag_pc[(ag_pc["date"] >= start) & (ag_pc["date"] <= end)].copy()
    base_period = base_pc[(base_pc["date"] >= start) & (base_pc["date"] <= end)].copy()
    ag_group = ag_period.groupby("product_vt_symbol", as_index=False).agg(
        ag_net_pnl=("net_pnl", "sum"),
        ag_holding_pnl=("holding_pnl", "sum"),
        ag_trading_pnl=("trading_pnl", "sum"),
        ag_slippage=("slippage", "sum"),
        ag_trade_count=("trade_count", "sum"),
        ag_turnover=("turnover", "sum"),
    )
    base_group = base_period.groupby("product_vt_symbol", as_index=False).agg(
        A_net_pnl=("net_pnl", "sum"),
        A_slippage=("slippage", "sum"),
        A_trade_count=("trade_count", "sum"),
    )
    contrib = ag_group.merge(base_group, on="product_vt_symbol", how="outer").fillna(0.0)
    contrib["net_pnl_diff_vs_A"] = contrib["ag_net_pnl"] - contrib["A_net_pnl"]
    contrib["slippage_diff_vs_A"] = contrib["ag_slippage"] - contrib["A_slippage"]
    contrib["trade_count_diff_vs_A"] = contrib["ag_trade_count"] - contrib["A_trade_count"]
    contrib.sort_values(["ag_net_pnl", "net_pnl_diff_vs_A"], ascending=[True, True], inplace=True)

    ag_full = ag_pc.copy()
    ag_full["year"] = ag_full["date"].dt.year
    year_contrib = ag_full.groupby(["year", "product_vt_symbol"], as_index=False).agg(
        net_pnl=("net_pnl", "sum"),
        slippage=("slippage", "sum"),
        trade_count=("trade_count", "sum"),
    )
    year_contrib = year_contrib[year_contrib["product_vt_symbol"].eq(AG_PRODUCT)].copy()
    year_contrib.sort_values("year", inplace=True)

    entries = pd.read_csv(AG_ENTRY_RISK_PATH)
    entries["date"] = pd.to_datetime(entries["date"]).dt.normalize()
    entries = entries[entries["product_vt_symbol"].astype(str).eq(AG_PRODUCT)].copy()
    for column in [
        "actual_margin_amount",
        "projected_total_margin_after",
        "portfolio_drawdown_pct",
        "target_risk_amount",
        "actual_risk_amount",
        "size",
        "same_direction_correlation_active_count",
        "same_direction_correlation_max_corr",
    ]:
        if column in entries.columns:
            entries[column] = pd.to_numeric(entries[column], errors="coerce").fillna(0.0)
    entries["inside_ag_max_drawdown_event"] = ((entries["date"] >= start) & (entries["date"] <= end)).astype(int)
    entry_summary = pd.DataFrame(
        [
            {
                "scope": "all_ag_entries",
                "entry_count": int(len(entries)),
                "long_count": int((entries["direction"].astype(str).str.lower() == "long").sum()),
                "short_count": int((entries["direction"].astype(str).str.lower() == "short").sum()),
                "avg_actual_margin_amount": float(entries.get("actual_margin_amount", pd.Series(dtype=float)).mean() or 0.0),
                "max_actual_margin_amount": float(entries.get("actual_margin_amount", pd.Series(dtype=float)).max() or 0.0),
                "avg_projected_total_margin_after": float(
                    entries.get("projected_total_margin_after", pd.Series(dtype=float)).mean() or 0.0
                ),
                "max_projected_total_margin_after": float(
                    entries.get("projected_total_margin_after", pd.Series(dtype=float)).max() or 0.0
                ),
                "avg_portfolio_drawdown_pct": float(
                    entries.get("portfolio_drawdown_pct", pd.Series(dtype=float)).mean() or 0.0
                ),
                "max_same_direction_active_count": float(
                    entries.get("same_direction_correlation_active_count", pd.Series(dtype=float)).max() or 0.0
                ),
                "max_same_direction_corr": float(
                    entries.get("same_direction_correlation_max_corr", pd.Series(dtype=float)).max() or 0.0
                ),
            },
            {
                "scope": "ag_entries_inside_max_drawdown_event",
                "entry_count": int(entries["inside_ag_max_drawdown_event"].sum()),
                "long_count": int(
                    (
                        entries["inside_ag_max_drawdown_event"].eq(1)
                        & entries["direction"].astype(str).str.lower().eq("long")
                    ).sum()
                ),
                "short_count": int(
                    (
                        entries["inside_ag_max_drawdown_event"].eq(1)
                        & entries["direction"].astype(str).str.lower().eq("short")
                    ).sum()
                ),
                "avg_actual_margin_amount": float(
                    entries.loc[entries["inside_ag_max_drawdown_event"].eq(1), "actual_margin_amount"].mean()
                    if "actual_margin_amount" in entries
                    else 0.0
                ),
                "max_actual_margin_amount": float(
                    entries.loc[entries["inside_ag_max_drawdown_event"].eq(1), "actual_margin_amount"].max()
                    if "actual_margin_amount" in entries
                    else 0.0
                ),
                "avg_projected_total_margin_after": float(
                    entries.loc[entries["inside_ag_max_drawdown_event"].eq(1), "projected_total_margin_after"].mean()
                    if "projected_total_margin_after" in entries
                    else 0.0
                ),
                "max_projected_total_margin_after": float(
                    entries.loc[entries["inside_ag_max_drawdown_event"].eq(1), "projected_total_margin_after"].max()
                    if "projected_total_margin_after" in entries
                    else 0.0
                ),
                "avg_portfolio_drawdown_pct": float(
                    entries.loc[entries["inside_ag_max_drawdown_event"].eq(1), "portfolio_drawdown_pct"].mean()
                    if "portfolio_drawdown_pct" in entries
                    else 0.0
                ),
                "max_same_direction_active_count": float(
                    entries.loc[
                        entries["inside_ag_max_drawdown_event"].eq(1),
                        "same_direction_correlation_active_count",
                    ].max()
                    if "same_direction_correlation_active_count" in entries
                    else 0.0
                ),
                "max_same_direction_corr": float(
                    entries.loc[
                        entries["inside_ag_max_drawdown_event"].eq(1),
                        "same_direction_correlation_max_corr",
                    ].max()
                    if "same_direction_correlation_max_corr" in entries
                    else 0.0
                ),
            },
        ]
    ).fillna(0.0)

    ag_trade_rows = pd.read_csv(AG_TRADES_PATH)
    ag_trade_rows["product_vt_symbol"] = ag_trade_rows["vt_symbol"].map(_product_from_vt_symbol)
    ag_only_trades = ag_trade_rows[ag_trade_rows["product_vt_symbol"].eq(AG_PRODUCT)].copy()
    event["ag_full_trade_rows"] = int(len(ag_only_trades))
    event["ag_open_rows"] = int(ag_only_trades["offset"].astype(str).str.lower().eq("open").sum())
    event["ag_close_rows"] = int(ag_only_trades["offset"].astype(str).str.lower().eq("close").sum())
    event["ag_total_volume"] = float(pd.to_numeric(ag_only_trades["volume"], errors="coerce").fillna(0.0).sum())

    return event, contrib, year_contrib, entry_summary


def _write_report(
    start_year: pd.DataFrame,
    quarter_path_reset: pd.DataFrame,
    quarter_true_rerun: pd.DataFrame,
    weak_window: pd.DataFrame,
    weak_rolling: pd.DataFrame,
    slippage: pd.DataFrame,
    ag_event: dict[str, Any],
    ag_contrib: pd.DataFrame,
    ag_year: pd.DataFrame,
    ag_entry: pd.DataFrame,
    judgement: dict[str, Any],
) -> str:
    worst_quarters = quarter_path_reset.sort_values(["return_diff_vs_A", "dd_diff_vs_A"], ascending=[True, True]).head(12)
    true_quarters = quarter_true_rerun.sort_values(["return_diff_vs_A", "dd_diff_vs_A"], ascending=[True, True])
    worst_rolling = weak_rolling.groupby("window_days", group_keys=False).head(8) if not weak_rolling.empty else weak_rolling
    top_ag_losses = ag_contrib.head(12)
    lines = [
        "# Stage268 Y.DCE Robustness And Ag.SHFE Drawdown Source",
        "",
        "## Design",
        "",
        "- A: Stage78-1 official baseline `static18 + fu`.",
        "- C_y: A + `y.DCE`; no parameter changes.",
        "- `y.DCE` is validated by actual start-year backtests, all-quarter path-reset scan, worst-quarter true reruns, named weak-window backtests, rolling weak-window attribution, and 1x/3x/5x slippage stress.",
        "- `ag.SHFE` is not promoted here; this report only decomposes its max drawdown source from saved Stage267 artifacts.",
        "",
        "## Judgement",
        "",
        json.dumps(judgement, ensure_ascii=False, indent=2),
        "",
        "## Y.DCE Start-Year",
        "",
        to_markdown_table(start_year),
        "",
        "## Y.DCE Worst Quarter Path Resets",
        "",
        to_markdown_table(worst_quarters),
        "",
        "## Y.DCE Worst Quarter True Reruns",
        "",
        to_markdown_table(true_quarters),
        "",
        "## Y.DCE Named Weak Windows",
        "",
        to_markdown_table(weak_window),
        "",
        "## Y.DCE Worst Rolling Windows",
        "",
        to_markdown_table(worst_rolling),
        "",
        "## Y.DCE Slippage Stress",
        "",
        to_markdown_table(slippage),
        "",
        "## Ag.SHFE Max Drawdown Event",
        "",
        json.dumps(ag_event, ensure_ascii=False, indent=2),
        "",
        "## Ag.SHFE Drawdown Product Contribution",
        "",
        to_markdown_table(top_ag_losses),
        "",
        "## Ag.SHFE Year Contribution",
        "",
        to_markdown_table(ag_year),
        "",
        "## Ag.SHFE Entry Diagnostics",
        "",
        to_markdown_table(ag_entry),
    ]
    return "\n".join(lines)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    start_year = _start_year_sweep()
    quarter = _quarter_cold_start_sweep()
    quarter_true = _quarter_true_rerun_sweep(quarter)
    weak_window = _weak_window_sweep()
    weak_rolling = _rolling_window_metrics()
    slippage = _slippage_stress()
    ag_event, ag_contrib, ag_year, ag_entry = _ag_drawdown_analysis()

    start_year.to_csv(START_YEAR_CSV_PATH, index=False, encoding="utf-8-sig")
    quarter.to_csv(QUARTER_COLD_START_CSV_PATH, index=False, encoding="utf-8-sig")
    quarter_true.to_csv(QUARTER_TRUE_RERUN_CSV_PATH, index=False, encoding="utf-8-sig")
    weak_window.to_csv(WEAK_WINDOW_CSV_PATH, index=False, encoding="utf-8-sig")
    weak_rolling.to_csv(WEAK_ROLLING_CSV_PATH, index=False, encoding="utf-8-sig")
    slippage.to_csv(SLIPPAGE_STRESS_CSV_PATH, index=False, encoding="utf-8-sig")
    ag_contrib.to_csv(AG_PRODUCT_CONTRIB_CSV_PATH, index=False, encoding="utf-8-sig")
    ag_year.to_csv(AG_YEAR_CONTRIB_CSV_PATH, index=False, encoding="utf-8-sig")
    ag_entry.to_csv(AG_ENTRY_DIAGNOSTICS_CSV_PATH, index=False, encoding="utf-8-sig")

    y_start_pass = bool(
        (start_year["end_balance_diff_vs_A"] > 0).all()
        and (start_year["sharpe_diff_vs_A"] > 0).mean() >= 0.70
        and (start_year["dd_diff_vs_A"] >= -2.0).all()
    )
    y_quarter_path_pass = bool(
        (quarter["end_balance_diff_vs_A"] > 0).mean() >= 0.70
        and (quarter["dd_diff_vs_A"] >= -5.0).mean() >= 0.85
    )
    y_quarter_true_pass = bool(
        not quarter_true.empty
        and (quarter_true["end_balance_diff_vs_A"] > 0).all()
        and (quarter_true["dd_diff_vs_A"] >= -5.0).all()
    )
    y_slippage_pass = bool(
        (slippage[slippage["start_name"].eq("full_2020_2026")]["end_balance_diff_vs_A"] > 0).all()
        and (slippage[slippage["start_name"].eq("full_2020_2026")]["sharpe_diff_vs_A"] > 0).all()
    )
    y_weak_pass = bool(
        (weak_window["end_balance_diff_vs_A"] > 0).mean() >= 0.60
        and (weak_window["dd_diff_vs_A"] >= -5.0).all()
    )
    ag_event_product = ag_contrib[ag_contrib["product_vt_symbol"].eq(AG_PRODUCT)]
    ag_event_net_pnl = float(ag_event_product["ag_net_pnl"].iloc[0]) if not ag_event_product.empty else 0.0
    ag_is_main_event_loss = bool(ag_event_net_pnl < 0 and abs(ag_event_net_pnl) >= abs(float(ag_event["ag_event_net_pnl"])) * 0.25)

    judgement = {
        "y_start_year_pass": y_start_pass,
        "y_quarter_path_reset_pass": y_quarter_path_pass,
        "y_quarter_true_rerun_pass": y_quarter_true_pass,
        "y_weak_window_pass": y_weak_pass,
        "y_slippage_stress_pass": y_slippage_pass,
        "y_promotion_decision": (
            "advance_to_next_validation"
            if (y_start_pass and y_quarter_true_pass and y_slippage_pass and y_weak_pass)
            else "hold_as_research_lead"
        ),
        "ag_is_main_max_drawdown_loss_source": ag_is_main_event_loss,
        "ag_drawdown_decision": "do_not_promote_until_drawdown_source_is_resolved",
    }

    payload = {
        "model_tag": MODEL_TAG,
        "baseline": OFFICIAL_BASELINE_NAME,
        "candidate_y": Y_PRODUCT,
        "candidate_ag": AG_PRODUCT,
        "capital": OFFICIAL_STAGE78_CAPITAL,
        "base_risk_ratio": BASE_RISK_RATIO,
        "slippage_multipliers": list(SLIPPAGE_MULTIPLIERS),
        "start_years": list(START_YEARS),
        "quarter_start_count": int(len(_quarter_starts())),
        "true_quarter_rerun_count": int(len(quarter_true)),
        "ag_drawdown_event": ag_event,
        "judgement": judgement,
        "artifacts": {
            "start_year_csv": str(START_YEAR_CSV_PATH),
            "quarter_cold_start_csv": str(QUARTER_COLD_START_CSV_PATH),
            "quarter_true_rerun_csv": str(QUARTER_TRUE_RERUN_CSV_PATH),
            "weak_window_csv": str(WEAK_WINDOW_CSV_PATH),
            "weak_rolling_csv": str(WEAK_ROLLING_CSV_PATH),
            "slippage_stress_csv": str(SLIPPAGE_STRESS_CSV_PATH),
            "ag_product_contrib_csv": str(AG_PRODUCT_CONTRIB_CSV_PATH),
            "ag_year_contrib_csv": str(AG_YEAR_CONTRIB_CSV_PATH),
            "ag_entry_diagnostics_csv": str(AG_ENTRY_DIAGNOSTICS_CSV_PATH),
            "summary_json": str(SUMMARY_JSON_PATH),
            "report_md": str(REPORT_PATH),
        },
    }
    SUMMARY_JSON_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_PATH.write_text(
        _write_report(
            start_year,
            quarter,
            quarter_true,
            weak_window,
            weak_rolling,
            slippage,
            ag_event,
            ag_contrib,
            ag_year,
            ag_entry,
            judgement,
        ),
        encoding="utf-8",
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    print("\n[start_year]")
    print(start_year.to_string(index=False))
    print("\n[quarter_worst]")
    print(quarter.sort_values(["return_diff_vs_A", "dd_diff_vs_A"], ascending=[True, True]).head(12).to_string(index=False))
    print("\n[quarter_true_rerun]")
    print(quarter_true.to_string(index=False))
    print("\n[weak_window]")
    print(weak_window.to_string(index=False))
    print("\n[slippage]")
    print(slippage.to_string(index=False))
    print("\n[ag_event]")
    print(json.dumps(ag_event, ensure_ascii=False, indent=2))
    print("\n[ag_contrib_head]")
    print(ag_contrib.head(12).to_string(index=False))


if __name__ == "__main__":
    main()
