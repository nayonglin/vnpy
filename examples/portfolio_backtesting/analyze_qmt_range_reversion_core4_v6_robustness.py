from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from analyze_qmt_range_reversion_core4_v3_exit_structure import _build_round_trips


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"
SOURCE_PREFIX: str = "qmt_range_reversion_core4_directed_product_signal_no_long_prevday_stop_v6"
MODEL_TAG: str = "range_reversion_core4_v6_robustness_v1"

DAILY_PATH: Path = OUTPUT_DIR / f"{SOURCE_PREFIX}_daily_equity.csv"
TRADES_PATH: Path = OUTPUT_DIR / f"{SOURCE_PREFIX}_trades_2020_2026_04.csv"
ENTRY_RISK_PATH: Path = OUTPUT_DIR / f"{SOURCE_PREFIX}_entry_risk_diagnostics_2020_2026_04.csv"

YEAR_SUMMARY_PATH: Path = OUTPUT_DIR / f"qmt_range_reversion_core4_v6_year_summary_{MODEL_TAG}.csv"
QUARTER_SUMMARY_PATH: Path = OUTPUT_DIR / f"qmt_range_reversion_core4_v6_quarter_summary_{MODEL_TAG}.csv"
START_YEAR_SUMMARY_PATH: Path = OUTPUT_DIR / f"qmt_range_reversion_core4_v6_start_year_summary_{MODEL_TAG}.csv"
ROLLING_SUMMARY_PATH: Path = OUTPUT_DIR / f"qmt_range_reversion_core4_v6_rolling_summary_{MODEL_TAG}.csv"
PRODUCT_YEAR_SUMMARY_PATH: Path = OUTPUT_DIR / f"qmt_range_reversion_core4_v6_product_year_summary_{MODEL_TAG}.csv"
SUMMARY_JSON_PATH: Path = OUTPUT_DIR / f"qmt_range_reversion_core4_v6_robustness_summary_{MODEL_TAG}.json"
REPORT_PATH: Path = OUTPUT_DIR / f"qmt_range_reversion_core4_v6_robustness_report_{MODEL_TAG}.md"


def _load_inputs() -> tuple[pd.DataFrame, pd.DataFrame]:
    if not DAILY_PATH.exists():
        raise FileNotFoundError(DAILY_PATH)
    if not TRADES_PATH.exists():
        raise FileNotFoundError(TRADES_PATH)
    if not ENTRY_RISK_PATH.exists():
        raise FileNotFoundError(ENTRY_RISK_PATH)

    daily = pd.read_csv(DAILY_PATH)
    daily["date"] = pd.to_datetime(daily["date"])
    daily = daily.sort_values("date").reset_index(drop=True)

    trades = pd.read_csv(TRADES_PATH)
    entries = pd.read_csv(ENTRY_RISK_PATH)
    round_trips = _build_round_trips(trades, entries)
    if not round_trips.empty:
        round_trips["entry_year"] = pd.to_datetime(round_trips["entry_datetime"]).dt.year
        round_trips["entry_quarter"] = pd.to_datetime(round_trips["entry_datetime"]).dt.to_period("Q").astype(str)
    return daily, round_trips


def _max_drawdown(balance: pd.Series) -> tuple[float, float]:
    if balance.empty:
        return 0.0, 0.0
    high = balance.cummax()
    drawdown = balance - high
    dd_pct = drawdown / high.replace(0, pd.NA) * 100.0
    return float(drawdown.min()), float(dd_pct.min())


def _annualized_sharpe(balance: pd.Series) -> float:
    returns = balance.pct_change().dropna()
    std = float(returns.std())
    if std <= 1e-12:
        return 0.0
    return float(returns.mean() / std * (240 ** 0.5))


def _segment_metrics(frame: pd.DataFrame, label: str, label_column: str) -> dict[str, Any]:
    if frame.empty:
        return {label_column: label}
    start_balance = float(frame["balance"].iloc[0])
    end_balance = float(frame["balance"].iloc[-1])
    net_pnl = end_balance - start_balance
    max_dd, max_dd_pct = _max_drawdown(frame["balance"])
    return {
        label_column: label,
        "start_date": frame["date"].iloc[0].date().isoformat(),
        "end_date": frame["date"].iloc[-1].date().isoformat(),
        "start_balance": start_balance,
        "end_balance": end_balance,
        "net_pnl": net_pnl,
        "return_pct": net_pnl / start_balance * 100.0 if start_balance else 0.0,
        "max_drawdown": max_dd,
        "max_dd_pct": max_dd_pct,
        "sharpe_like": _annualized_sharpe(frame["balance"]),
        "slippage": float(frame["slippage"].sum()),
        "trade_count": int(frame["trade_count"].sum()),
        "profit_days": int((frame["net_pnl"] > 0).sum()),
        "loss_days": int((frame["net_pnl"] < 0).sum()),
    }


def _year_summary(daily: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for year, group in daily.groupby(daily["date"].dt.year, sort=True):
        rows.append(_segment_metrics(group, str(year), "year"))
    return pd.DataFrame(rows)


def _quarter_summary(daily: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for quarter, group in daily.groupby(daily["date"].dt.to_period("Q").astype(str), sort=True):
        rows.append(_segment_metrics(group, str(quarter), "quarter"))
    return pd.DataFrame(rows)


def _start_year_summary(daily: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for year in sorted(daily["date"].dt.year.unique()):
        group = daily[daily["date"].dt.year >= year].copy()
        rows.append(_segment_metrics(group, f"since_{year}", "window"))
    return pd.DataFrame(rows)


def _rolling_summary(daily: pd.DataFrame, windows: list[int] | None = None) -> pd.DataFrame:
    windows = windows or [63, 126, 252]
    rows: list[dict[str, Any]] = []
    for window in windows:
        if len(daily) < window:
            continue
        for end_index in range(window - 1, len(daily)):
            frame = daily.iloc[end_index - window + 1 : end_index + 1].copy()
            row = _segment_metrics(frame, f"{window}d", "window")
            row["window_days"] = window
            rows.append(row)
    result = pd.DataFrame(rows)
    if result.empty:
        return result
    return result.sort_values(["return_pct", "max_dd_pct"], ascending=[True, True]).reset_index(drop=True)


def _product_year_summary(round_trips: pd.DataFrame) -> pd.DataFrame:
    if round_trips.empty:
        return pd.DataFrame()
    summary = round_trips.groupby(["entry_year", "product_vt_symbol", "direction"], dropna=False).agg(
        round_trips=("pnl", "size"),
        pnl=("pnl", "sum"),
        avg_pnl=("pnl", "mean"),
        win_rate=("pnl", lambda s: float((s > 0).mean())),
        worst_pnl=("pnl", "min"),
        best_pnl=("pnl", "max"),
    ).reset_index()
    return summary.sort_values(["entry_year", "pnl"], ascending=[True, False]).reset_index(drop=True)


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
    }


def _write_report(
    year_summary: pd.DataFrame,
    quarter_summary: pd.DataFrame,
    start_year_summary: pd.DataFrame,
    rolling_summary: pd.DataFrame,
    product_year_summary: pd.DataFrame,
    drawdown_event: dict[str, Any],
) -> None:
    worst_rolling = rolling_summary.head(10)
    lines = [
        "# QMT Range Reversion Core4 V6 Robustness",
        "",
        "## Scope",
        "- This report reads the existing v6 curve and trades only; no new backtest is run.",
        "",
        "## Drawdown Event",
        json.dumps(drawdown_event, ensure_ascii=False, indent=2),
        "",
        "## Year Summary",
        year_summary.to_markdown(index=False) if not year_summary.empty else "- Empty.",
        "",
        "## Start-Year Summary",
        start_year_summary.to_markdown(index=False) if not start_year_summary.empty else "- Empty.",
        "",
        "## Worst Rolling Windows",
        worst_rolling.to_markdown(index=False) if not worst_rolling.empty else "- Empty.",
        "",
        "## Quarter Summary",
        quarter_summary.to_markdown(index=False) if not quarter_summary.empty else "- Empty.",
        "",
        "## Product Year Summary",
        product_year_summary.to_markdown(index=False) if not product_year_summary.empty else "- Empty.",
    ]
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    daily, round_trips = _load_inputs()
    year_summary = _year_summary(daily)
    quarter_summary = _quarter_summary(daily)
    start_year_summary = _start_year_summary(daily)
    rolling_summary = _rolling_summary(daily)
    product_year_summary = _product_year_summary(round_trips)
    drawdown_event = _drawdown_event(daily)

    year_summary.to_csv(YEAR_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    quarter_summary.to_csv(QUARTER_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    start_year_summary.to_csv(START_YEAR_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    rolling_summary.to_csv(ROLLING_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    product_year_summary.to_csv(PRODUCT_YEAR_SUMMARY_PATH, index=False, encoding="utf-8-sig")

    negative_years = year_summary[year_summary["net_pnl"] < 0]["year"].astype(str).tolist()
    worst_year = year_summary.sort_values("net_pnl").head(1).to_dict("records")
    worst_252 = rolling_summary[rolling_summary["window_days"].eq(252)].head(1).to_dict("records")
    payload = {
        "model_tag": MODEL_TAG,
        "source_prefix": SOURCE_PREFIX,
        "negative_years": negative_years,
        "worst_year": worst_year[0] if worst_year else {},
        "worst_252d_window": worst_252[0] if worst_252 else {},
        "drawdown_event": drawdown_event,
        "outputs": {
            "year_summary": str(YEAR_SUMMARY_PATH),
            "quarter_summary": str(QUARTER_SUMMARY_PATH),
            "start_year_summary": str(START_YEAR_SUMMARY_PATH),
            "rolling_summary": str(ROLLING_SUMMARY_PATH),
            "product_year_summary": str(PRODUCT_YEAR_SUMMARY_PATH),
            "report": str(REPORT_PATH),
        },
    }
    SUMMARY_JSON_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(year_summary, quarter_summary, start_year_summary, rolling_summary, product_year_summary, drawdown_event)

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    print(year_summary.to_string(index=False))
    print(start_year_summary.to_string(index=False))
    print(rolling_summary.head(10).to_string(index=False))
    print(product_year_summary.to_string(index=False))


if __name__ == "__main__":
    main()
