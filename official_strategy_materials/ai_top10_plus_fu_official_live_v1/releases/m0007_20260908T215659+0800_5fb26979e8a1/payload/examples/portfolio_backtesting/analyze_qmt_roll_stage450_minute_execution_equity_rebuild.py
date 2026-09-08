from __future__ import annotations

import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
LINE_ID = "futures_trend_drawdown30_preserve_return"
MODEL_TAG = "stage450_minute_execution_equity_rebuild_v1"
OUTPUT_PREFIX = "qmt_roll_stage450_minute_execution_equity_rebuild"

ACCOUNT_CAPITAL = 615_000.0
BASELINE_VARIANT = "stage079"
STAGE103_VARIANT = "xsmom_vt10_q_momq_round_half_true_broker10_guard"
TARGET_DD_PCT = -30.0

STAGE403_DAILY_PATH = (
    OUTPUT_DIR
    / "qmt_roll_stage403_stage079_xsmom_execution_margin_audit_daily_stage403_stage079_xsmom_execution_margin_audit_v1.csv"
)
STAGE149_DETAIL_PATH = (
    OUTPUT_DIR
    / "qmt_roll_stage449_minute_session_rebuild_full_ledger_proxy_detail_stage449_minute_session_rebuild_full_v1.csv"
)

DAILY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_{MODEL_TAG}.csv"
TRADE_DELTA_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trade_delta_{MODEL_TAG}.csv"
SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
HORIZON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_horizon_{MODEL_TAG}.csv"
SCORE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_score_{MODEL_TAG}.csv"
COST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cost_stress_{MODEL_TAG}.csv"
GATE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gate_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"


HORIZON_TARGETS = {
    90: {
        "label": "3个月",
        "return_p05_pct": -8.0,
        "return_median_pct": 13.52,
        "positive_return_rate": 0.80,
        "annualized_below_5pct_rate": 0.22,
        "max_dd_worst_pct": -29.20,
        "dd20_breach_rate": 0.12,
        "dd30_breach_rate": 0.0,
        "ulcer_p95_pct": 15.0,
        "longest_underwater_p95_days": 80.0,
    },
    180: {
        "label": "6个月",
        "return_p05_pct": 0.0,
        "return_median_pct": 33.92,
        "positive_return_rate": 0.95,
        "annualized_below_5pct_rate": 0.06,
        "max_dd_worst_pct": -29.70,
        "dd20_breach_rate": 0.25,
        "dd30_breach_rate": 0.0,
        "ulcer_p95_pct": 17.0,
        "longest_underwater_p95_days": 150.0,
    },
}
SCORE_WEIGHTS = {
    "return_p05_pct": 0.25,
    "positive_return_rate": 0.20,
    "annualized_below_5pct_rate": 0.15,
    "dd20_breach_rate": 0.20,
    "ulcer_p95_pct": 0.10,
    "longest_underwater_p95_days": 0.10,
}


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, tuple):
        return [_json_safe(v) for v in value]
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


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(result) or math.isinf(result):
        return default
    return result


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "无数据。"
    view = frame.copy()
    if max_rows is not None:
        view = view.head(max_rows)
    for column in view.columns:
        if pd.api.types.is_float_dtype(view[column]):
            view[column] = view[column].map(lambda value: f"{value:.4f}" if pd.notna(value) else "")
    return view.to_markdown(index=False)


def _drawdown(nav: pd.Series) -> pd.Series:
    return nav / nav.cummax() - 1.0


def _max_drawdown_pct(nav: pd.Series | np.ndarray) -> float:
    series = pd.Series(nav, dtype=float)
    if series.empty:
        return 0.0
    return float((series / series.cummax() - 1.0).min() * 100.0)


def _ulcer_pct(nav: pd.Series | np.ndarray) -> float:
    series = pd.Series(nav, dtype=float)
    if series.empty:
        return 0.0
    dd = np.minimum((series / series.cummax() - 1.0).to_numpy(dtype=float) * 100.0, 0.0)
    return float(np.sqrt(np.mean(dd**2)))


def _sharpe(nav: pd.Series) -> float:
    ret = nav.pct_change().dropna()
    if len(ret) < 2:
        return 0.0
    std = float(ret.std(ddof=1))
    if std <= 0.0:
        return 0.0
    return float(ret.mean() / std * math.sqrt(252.0))


def _longest_underwater_days(dates: np.ndarray, nav: np.ndarray) -> int:
    peak = np.maximum.accumulate(nav)
    underwater = nav < peak * (1.0 - 1e-12)
    longest = 0
    start: np.datetime64 | None = None
    for date, flag in zip(dates, underwater):
        if bool(flag):
            if start is None:
                start = date
            longest = max(longest, int((date - start) / np.timedelta64(1, "D")) + 1)
        else:
            start = None
    return int(longest)


def _side_pnl_multiplier(direction: str, offset: str) -> int:
    sell_like = (direction == "Short" and offset == "Open") or (direction == "Long" and offset == "Close")
    return 1 if sell_like else -1


def _load_stage403_daily() -> pd.DataFrame:
    frame = pd.read_csv(STAGE403_DAILY_PATH, encoding="utf-8-sig")
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame = frame[frame["window_name"].eq("start_2020")].copy()
    for column in [
        "c3_net_pnl",
        "c3_trade_count",
        "c3_slippage",
        "satellite_daily_pnl",
        "satellite_slippage_cost",
        "equity",
        "trade_count",
        "combo_slippage",
    ]:
        frame[column] = pd.to_numeric(frame.get(column, 0.0), errors="coerce").fillna(0.0)
    return frame.dropna(subset=["date"]).sort_values(["variant", "date"])


def _load_trade_delta(trading_dates: pd.DatetimeIndex) -> pd.DataFrame:
    detail = pd.read_csv(STAGE149_DETAIL_PATH, encoding="utf-8-sig")
    for column in ["date", "next_trade_date"]:
        detail[column] = pd.to_datetime(detail[column], errors="coerce").dt.normalize()
    numeric_cols = [
        "theoretical_price",
        "same_last5_vwap",
        "same_last5_first_open",
        "preferred_real_open_proxy",
        "volume",
        "size",
        "price_tick",
    ]
    for column in numeric_cols:
        detail[column] = pd.to_numeric(detail.get(column, np.nan), errors="coerce")

    next_date_map: dict[pd.Timestamp, pd.Timestamp] = {}
    for value in sorted(detail["next_trade_date"].dropna().unique()):
        ts = pd.Timestamp(value).normalize()
        idx = trading_dates[trading_dates >= ts]
        next_date_map[ts] = pd.Timestamp(idx[0]).normalize() if len(idx) else ts

    rows: list[dict[str, Any]] = []
    for row in detail.itertuples(index=False):
        theoretical = _safe_float(row.theoretical_price, np.nan)
        volume = _safe_float(row.volume, np.nan)
        size = _safe_float(row.size, np.nan)
        valid_base = bool(pd.notna(theoretical) and theoretical > 0.0 and volume > 0.0 and size > 0.0)
        multiplier = _side_pnl_multiplier(str(row.direction), str(row.offset))

        def delta(proxy_value: Any) -> float:
            proxy = _safe_float(proxy_value, np.nan)
            if not valid_base or pd.isna(proxy) or proxy <= 0.0:
                return 0.0
            return float(multiplier * (proxy - theoretical) * volume * size)

        trade_date = pd.Timestamp(row.date).normalize()
        next_trade_date = pd.Timestamp(row.next_trade_date).normalize() if pd.notna(row.next_trade_date) else trade_date
        open_adjust_date = next_date_map.get(next_trade_date, trade_date)
        rows.append(
            {
                "trade_id": str(row.trade_id),
                "trade_date": trade_date,
                "open_adjust_date": open_adjust_date,
                "vt_symbol": str(row.vt_symbol),
                "product_vt_symbol": str(row.product_vt_symbol),
                "direction": str(row.direction),
                "offset": str(row.offset),
                "session_proxy_class": str(row.session_proxy_class),
                "theoretical_price": theoretical,
                "same_last5_vwap": _safe_float(row.same_last5_vwap, np.nan),
                "same_last5_first_open": _safe_float(row.same_last5_first_open, np.nan),
                "preferred_real_open_proxy": _safe_float(row.preferred_real_open_proxy, np.nan),
                "volume": volume,
                "size": size,
                "valid_theoretical_price": int(valid_base),
                "has_same_last5_vwap": int(valid_base and pd.notna(row.same_last5_vwap) and _safe_float(row.same_last5_vwap) > 0.0),
                "has_preferred_open": int(
                    valid_base
                    and pd.notna(row.preferred_real_open_proxy)
                    and _safe_float(row.preferred_real_open_proxy) > 0.0
                ),
                "same_last5_delta_vs_engine_trade": delta(row.same_last5_vwap),
                "same_last5_first_open_delta_vs_engine_trade": delta(row.same_last5_first_open),
                "preferred_open_delta_vs_engine_trade": delta(row.preferred_real_open_proxy),
            }
        )
    return pd.DataFrame(rows).sort_values(["trade_date", "trade_id"]).reset_index(drop=True)


def _aggregate_delta(trade_delta: pd.DataFrame, date_col: str, delta_col: str, trading_dates: pd.DatetimeIndex) -> pd.Series:
    if trade_delta.empty:
        return pd.Series(0.0, index=trading_dates)
    grouped = trade_delta.groupby(date_col, sort=True)[delta_col].sum()
    return grouped.reindex(trading_dates).fillna(0.0).astype(float)


def _build_daily(stage403: pd.DataFrame, trade_delta: pd.DataFrame) -> pd.DataFrame:
    stage079 = stage403[stage403["variant"].eq(BASELINE_VARIANT)].copy()
    stage103 = stage403[stage403["variant"].eq(STAGE103_VARIANT)].copy()
    if stage079.empty or stage103.empty:
        raise RuntimeError("missing Stage079 or Stage103 daily data")
    base = stage079.drop_duplicates("date", keep="last").sort_values("date")
    s103 = stage103.drop_duplicates("date", keep="last").sort_values("date")
    trading_dates = pd.DatetimeIndex(base["date"])

    same_delta = _aggregate_delta(trade_delta, "trade_date", "same_last5_delta_vs_engine_trade", trading_dates)
    same_first_delta = _aggregate_delta(
        trade_delta,
        "trade_date",
        "same_last5_first_open_delta_vs_engine_trade",
        trading_dates,
    )
    open_delta = _aggregate_delta(trade_delta, "open_adjust_date", "preferred_open_delta_vs_engine_trade", trading_dates)

    daily = pd.DataFrame(
        {
            "date": trading_dates,
            "c3_net_pnl": base["c3_net_pnl"].to_numpy(dtype=float),
            "c3_slippage": base["c3_slippage"].to_numpy(dtype=float),
            "c3_trade_count": base["c3_trade_count"].to_numpy(dtype=float),
            "stage103_satellite_pnl": s103["satellite_daily_pnl"].to_numpy(dtype=float),
            "stage103_satellite_slippage": s103["satellite_slippage_cost"].to_numpy(dtype=float),
            "stage079_original_equity": base["equity"].to_numpy(dtype=float),
            "stage103_original_equity": s103["equity"].to_numpy(dtype=float),
            "same_last5_delta": same_delta.to_numpy(dtype=float),
            "same_last5_first_open_delta": same_first_delta.to_numpy(dtype=float),
            "preferred_open_delta": open_delta.to_numpy(dtype=float),
        }
    )
    daily["stage079_rebuilt_original"] = ACCOUNT_CAPITAL + daily["c3_net_pnl"].cumsum()
    daily["stage079_minute_1455_vwap"] = ACCOUNT_CAPITAL + (
        daily["c3_net_pnl"] + daily["same_last5_delta"]
    ).cumsum()
    daily["stage079_minute_1455_first_open"] = ACCOUNT_CAPITAL + (
        daily["c3_net_pnl"] + daily["same_last5_first_open_delta"]
    ).cumsum()
    daily["stage079_minute_preferred_open"] = ACCOUNT_CAPITAL + (
        daily["c3_net_pnl"] + daily["preferred_open_delta"]
    ).cumsum()
    daily["stage103_minute_1455_vwap_c3_only"] = ACCOUNT_CAPITAL + (
        daily["c3_net_pnl"] + daily["same_last5_delta"] + daily["stage103_satellite_pnl"]
    ).cumsum()
    daily["stage103_minute_preferred_open_c3_only"] = ACCOUNT_CAPITAL + (
        daily["c3_net_pnl"] + daily["preferred_open_delta"] + daily["stage103_satellite_pnl"]
    ).cumsum()
    return daily


def _calendar_equity(daily: pd.DataFrame, equity_col: str) -> pd.Series:
    series = daily.sort_values("date").set_index("date")[equity_col].astype(float)
    calendar = pd.date_range(series.index.min(), series.index.max(), freq="D")
    return series.reindex(calendar).ffill()


def _rolling_dd_breach_rate(equity: pd.Series, window: int) -> float:
    values = equity.to_numpy(dtype=float)
    if len(values) < window:
        return 1.0
    breaches: list[bool] = []
    for start in range(0, len(values) - window + 1):
        segment = values[start : start + window]
        nav = segment / segment[0]
        breaches.append(_max_drawdown_pct(nav) < TARGET_DD_PCT)
    return float(np.mean(breaches)) if breaches else 1.0


def _cold_start_pass_rate(equity: pd.Series, freq: str) -> float:
    starts = pd.date_range(equity.index.min(), equity.index.max(), freq=freq)
    passes: list[bool] = []
    for start in starts:
        idx = equity.index[equity.index >= start]
        if len(idx) < 252:
            continue
        segment = equity.loc[idx[0] :]
        nav = segment / segment.iloc[0]
        passes.append(_max_drawdown_pct(nav) >= TARGET_DD_PCT)
    return float(np.mean(passes)) if passes else 0.0


def _summary_for(variant: str, label: str, equity: pd.Series, capital_used: float = ACCOUNT_CAPITAL) -> dict[str, Any]:
    nav = equity.astype(float) / ACCOUNT_CAPITAL
    return {
        "variant": variant,
        "label": label,
        "capital_used": capital_used,
        "start_date": str(equity.index.min().date()),
        "end_date": str(equity.index.max().date()),
        "end_equity": float(equity.iloc[-1]),
        "total_return_pct": float((nav.iloc[-1] - 1.0) * 100.0),
        "max_dd_pct": _max_drawdown_pct(nav),
        "sharpe": _sharpe(nav),
        "ulcer_pct": _ulcer_pct(nav),
        "rolling252_dd30_breach_rate": _rolling_dd_breach_rate(equity, 252),
        "rolling504_dd30_breach_rate": _rolling_dd_breach_rate(equity, 504),
        "annual_cold_start_dd30_pass_rate": _cold_start_pass_rate(equity, "YS"),
        "quarter_cold_start_dd30_pass_rate": _cold_start_pass_rate(equity, "QS"),
    }


def _horizon_for(variant: str, label: str, equity: pd.Series, horizon_days: int) -> dict[str, Any]:
    dates = equity.index.to_numpy(dtype="datetime64[D]")
    date_index = pd.Index(equity.index)
    values = equity.to_numpy(dtype=float)
    rows: list[dict[str, float]] = []
    last_start = equity.index.max() - pd.Timedelta(days=horizon_days)
    for start_idx, start_date in enumerate(equity.index):
        if start_date > last_start:
            break
        end_date = start_date + pd.Timedelta(days=horizon_days)
        if end_date not in date_index:
            continue
        end_idx = int(date_index.get_loc(end_date))
        segment = values[start_idx : end_idx + 1]
        nav = segment / segment[0]
        total_return = nav[-1] - 1.0
        annualized = np.power(max(nav[-1], 1e-12), 365.0 / horizon_days) - 1.0
        dd = nav / np.maximum.accumulate(nav) - 1.0
        rows.append(
            {
                "return_pct": float(total_return * 100.0),
                "annualized_return_pct": float(annualized * 100.0),
                "max_dd_pct": float(dd.min() * 100.0),
                "ulcer_pct": float(np.sqrt(np.mean(np.minimum(dd * 100.0, 0.0) ** 2))),
                "longest_underwater_days": float(_longest_underwater_days(dates[start_idx : end_idx + 1], nav)),
            }
        )
    frame = pd.DataFrame(rows)
    result = {
        "variant": variant,
        "label": label,
        "horizon_days": horizon_days,
        "horizon_label": HORIZON_TARGETS[horizon_days]["label"],
        "count": int(len(frame)),
        "return_p05_pct": float(frame["return_pct"].quantile(0.05)) if not frame.empty else np.nan,
        "return_median_pct": float(frame["return_pct"].median()) if not frame.empty else np.nan,
        "positive_return_rate": float((frame["return_pct"] > 0.0).mean()) if not frame.empty else np.nan,
        "annualized_below_5pct_rate": float((frame["annualized_return_pct"] < 5.0).mean())
        if not frame.empty
        else np.nan,
        "max_dd_worst_pct": float(frame["max_dd_pct"].min()) if not frame.empty else np.nan,
        "dd20_breach_rate": float((frame["max_dd_pct"] < -20.0).mean()) if not frame.empty else np.nan,
        "dd30_breach_rate": float((frame["max_dd_pct"] < -30.0).mean()) if not frame.empty else np.nan,
        "ulcer_p95_pct": float(frame["ulcer_pct"].quantile(0.95)) if not frame.empty else np.nan,
        "longest_underwater_p95_days": float(frame["longest_underwater_days"].quantile(0.95))
        if not frame.empty
        else np.nan,
    }
    return result


def _component_score(metric: str, candidate_value: float, baseline_value: float, target_value: float) -> float:
    lower_is_better = metric in {
        "annualized_below_5pct_rate",
        "dd20_breach_rate",
        "ulcer_p95_pct",
        "longest_underwater_p95_days",
    }
    if lower_is_better:
        denominator = baseline_value - target_value
        if abs(denominator) < 1e-12:
            return 100.0 if candidate_value <= baseline_value else 0.0
        return 100.0 + (baseline_value - candidate_value) / denominator * 100.0
    denominator = target_value - baseline_value
    if abs(denominator) < 1e-12:
        return 100.0 if candidate_value >= baseline_value else 0.0
    return 100.0 + (candidate_value - baseline_value) / denominator * 100.0


def _score_horizons(horizon: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    baseline = horizon[horizon["variant"].eq(BASELINE_VARIANT)].set_index("horizon_days")
    for row in horizon.itertuples(index=False):
        horizon_days = int(row.horizon_days)
        base = baseline.loc[horizon_days]
        target = HORIZON_TARGETS[horizon_days]
        component_scores: dict[str, float] = {}
        for metric, weight in SCORE_WEIGHTS.items():
            candidate_value = _safe_float(getattr(row, metric))
            baseline_value = _safe_float(base[metric])
            target_value = _safe_float(target[metric])
            component_scores[f"{metric}_component_score"] = _component_score(metric, candidate_value, baseline_value, target_value)
        weighted_score = sum(component_scores[f"{metric}_component_score"] * weight for metric, weight in SCORE_WEIGHTS.items())
        rows.append(
            {
                "variant": row.variant,
                "label": row.label,
                "horizon_days": horizon_days,
                "horizon_label": row.horizon_label,
                "experience_score": weighted_score,
                **component_scores,
            }
        )
    score = pd.DataFrame(rows)
    pivot = score.pivot(index=["variant", "label"], columns="horizon_days", values="experience_score").reset_index()
    pivot.columns = ["variant", "label"] + [f"score_{int(column)}d" for column in pivot.columns[2:]]
    detail = score.merge(pivot, on=["variant", "label"], how="left")
    detail["short_holding_score"] = detail["score_90d"] * 0.45 + detail["score_180d"] * 0.55
    return detail


def _improved_count(metrics: pd.Series, baseline: pd.Series) -> tuple[int, str]:
    checks = {
        "return_p05": metrics["return_p05_pct"] > baseline["return_p05_pct"],
        "return_median": metrics["return_median_pct"] >= baseline["return_median_pct"],
        "positive_rate": metrics["positive_return_rate"] > baseline["positive_return_rate"],
        "below_5_rate": metrics["annualized_below_5pct_rate"] < baseline["annualized_below_5pct_rate"],
        "worst_dd": metrics["max_dd_worst_pct"] >= baseline["max_dd_worst_pct"],
        "dd20_rate": metrics["dd20_breach_rate"] < baseline["dd20_breach_rate"],
        "ulcer_p95": metrics["ulcer_p95_pct"] < baseline["ulcer_p95_pct"],
        "uw_p95": metrics["longest_underwater_p95_days"] < baseline["longest_underwater_p95_days"],
    }
    improved = [name for name, flag in checks.items() if flag]
    return len(improved), ",".join(improved)


def _cost_stress(daily: pd.DataFrame, variants: list[dict[str, str]]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    slippage = daily["c3_slippage"].astype(float)
    if "stage103" in {item["variant"] for item in variants}:
        pass
    base_by_multiplier: dict[float, float] = {}
    for multiplier in (1.0, 2.0, 3.0, 5.0):
        for item in variants:
            equity = daily[item["equity_col"]].astype(float) - (multiplier - 1.0) * slippage.cumsum()
            calendar = pd.Series(equity.to_numpy(dtype=float), index=pd.to_datetime(daily["date"]))
            calendar = calendar.reindex(pd.date_range(calendar.index.min(), calendar.index.max(), freq="D")).ffill()
            nav = calendar / ACCOUNT_CAPITAL
            max_dd = _max_drawdown_pct(nav)
            if item["variant"] == BASELINE_VARIANT:
                base_by_multiplier[multiplier] = max_dd
            rows.append(
                {
                    "variant": item["variant"],
                    "label": item["label"],
                    "slippage_multiplier": multiplier,
                    "total_return_pct": float((nav.iloc[-1] - 1.0) * 100.0),
                    "max_dd_pct": max_dd,
                }
            )
    result = pd.DataFrame(rows)
    result["baseline_stage079_max_dd_pct"] = result["slippage_multiplier"].map(base_by_multiplier)
    result["not_worse_than_stage079_stress"] = (
        result["max_dd_pct"] >= result["baseline_stage079_max_dd_pct"] - 1e-9
    ).astype(int)
    return result


def _target_pass(metrics: pd.Series, horizon_days: int) -> tuple[int, str]:
    target = HORIZON_TARGETS[horizon_days]
    checks = {
        "return_p05": metrics["return_p05_pct"] > target["return_p05_pct"],
        "return_median": metrics["return_median_pct"] >= target["return_median_pct"],
        "positive_rate": metrics["positive_return_rate"] >= target["positive_return_rate"],
        "below_5_rate": metrics["annualized_below_5pct_rate"] <= target["annualized_below_5pct_rate"],
        "worst_dd": metrics["max_dd_worst_pct"] >= target["max_dd_worst_pct"],
        "dd20_rate": metrics["dd20_breach_rate"] <= target["dd20_breach_rate"],
        "dd30_rate": metrics["dd30_breach_rate"] <= target["dd30_breach_rate"],
        "ulcer_p95": metrics["ulcer_p95_pct"] <= target["ulcer_p95_pct"],
        "uw_p95": metrics["longest_underwater_p95_days"] <= target["longest_underwater_p95_days"],
    }
    failed = [name for name, flag in checks.items() if not flag]
    return int(all(checks.values())), ",".join(failed)


def _gate(summary: pd.DataFrame, horizon: pd.DataFrame, score: pd.DataFrame, cost: pd.DataFrame) -> pd.DataFrame:
    baseline_summary = summary[summary["variant"].eq(BASELINE_VARIANT)].iloc[0]
    baseline_horizon = horizon[horizon["variant"].eq(BASELINE_VARIANT)].set_index("horizon_days")
    score_wide = score.drop_duplicates(["variant", "label"])[
        ["variant", "label", "score_90d", "score_180d", "short_holding_score"]
    ]
    rows: list[dict[str, Any]] = []
    for row in summary.itertuples(index=False):
        variant = str(row.variant)
        cost_ok = int(cost[cost["variant"].eq(variant)]["not_worse_than_stage079_stress"].eq(1).all())
        checks = {
            "total_return_not_lower": _safe_float(row.total_return_pct) >= _safe_float(baseline_summary["total_return_pct"]) - 1e-6,
            "max_dd_not_worse": _safe_float(row.max_dd_pct) >= _safe_float(baseline_summary["max_dd_pct"]) - 1e-6,
            "max_dd_below_30": _safe_float(row.max_dd_pct) >= TARGET_DD_PCT,
            "sharpe_not_lower": _safe_float(row.sharpe) >= _safe_float(baseline_summary["sharpe"]) - 1e-6,
            "ulcer_not_higher": _safe_float(row.ulcer_pct) <= _safe_float(baseline_summary["ulcer_pct"]) + 1e-6,
            "rolling252_dd30_zero": _safe_float(row.rolling252_dd30_breach_rate) <= 0.0,
            "rolling504_dd30_zero": _safe_float(row.rolling504_dd30_breach_rate) <= 0.0,
            "annual_dd30_pass_100": _safe_float(row.annual_cold_start_dd30_pass_rate) >= 1.0,
            "quarter_dd30_pass_100": _safe_float(row.quarter_cold_start_dd30_pass_rate) >= 1.0,
            "capital_not_increased": _safe_float(row.capital_used) <= ACCOUNT_CAPITAL,
            "cost_stress_not_worse": bool(cost_ok),
        }
        failed_hard = [name for name, flag in checks.items() if not flag]
        h90 = horizon[(horizon["variant"].eq(variant)) & (horizon["horizon_days"].eq(90))].iloc[0]
        h180 = horizon[(horizon["variant"].eq(variant)) & (horizon["horizon_days"].eq(180))].iloc[0]
        improved_90, improved_metrics_90 = _improved_count(h90, baseline_horizon.loc[90])
        improved_180, improved_metrics_180 = _improved_count(h180, baseline_horizon.loc[180])
        target90, failed90 = _target_pass(h90, 90)
        target180, failed180 = _target_pass(h180, 180)
        scores = score_wide[score_wide["variant"].eq(variant)].iloc[0]
        score90_ok = _safe_float(scores["score_90d"]) >= 110.0
        score180_ok = _safe_float(scores["score_180d"]) >= 110.0
        promotion_pass = all(checks.values()) and score90_ok and score180_ok and improved_90 >= 5 and improved_180 >= 5
        rows.append(
            {
                "variant": variant,
                "label": str(row.label),
                **{name: int(flag) for name, flag in checks.items()},
                "hard_constraint_pass": int(all(checks.values())),
                "failed_hard_constraints": ",".join(failed_hard),
                "score_90d": _safe_float(scores["score_90d"]),
                "score_180d": _safe_float(scores["score_180d"]),
                "short_holding_score": _safe_float(scores["short_holding_score"]),
                "score90_improve_ge10pct": int(score90_ok),
                "score180_improve_ge10pct": int(score180_ok),
                "improved_count_90d": improved_90,
                "improved_count_180d": improved_180,
                "improved_metrics_90d": improved_metrics_90,
                "improved_metrics_180d": improved_metrics_180,
                "target_90d_pass": target90,
                "target_180d_pass": target180,
                "target_90d_failed": failed90,
                "target_180d_failed": failed180,
                "promotion_gate_pass": int(promotion_pass),
            }
        )
    return pd.DataFrame(rows).sort_values(["promotion_gate_pass", "short_holding_score"], ascending=[False, False])


def _plot(daily: pd.DataFrame) -> None:
    variants = [
        ("stage079_original_equity", "Stage079 original", "#4c78a8"),
        ("stage079_minute_1455_vwap", "Stage079 14:55 VWAP", "#f58518"),
        ("stage079_minute_preferred_open", "Stage079 real open", "#54a24b"),
        ("stage103_original_equity", "Stage103 original", "#b279a2"),
        ("stage103_minute_1455_vwap_c3_only", "Stage103 14:55 C3-only", "#e45756"),
        ("stage103_minute_preferred_open_c3_only", "Stage103 real open C3-only", "#72b7b2"),
    ]
    fig, axes = plt.subplots(2, 1, figsize=(13, 8), sharex=True)
    x = pd.to_datetime(daily["date"])
    for column, label, color in variants:
        nav = daily[column].astype(float) / ACCOUNT_CAPITAL
        axes[0].plot(x, nav, label=label, color=color, linewidth=1.2)
        dd = nav / nav.cummax() - 1.0
        axes[1].plot(x, dd * 100.0, label=label, color=color, linewidth=1.0)
    axes[0].set_title("Minute execution proxy first-order equity")
    axes[0].set_ylabel("NAV")
    axes[0].legend(ncol=2, fontsize=8)
    axes[1].set_title("Underwater drawdown")
    axes[1].set_ylabel("Drawdown %")
    axes[1].axhline(-30.0, color="#222222", linestyle="--", linewidth=1.0)
    axes[1].grid(True, alpha=0.25)
    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=160)
    plt.close(fig)


def _write_report(
    summary: pd.DataFrame,
    horizon: pd.DataFrame,
    score: pd.DataFrame,
    cost: pd.DataFrame,
    gate: pd.DataFrame,
    trade_delta: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    summary_cols = [
        "variant",
        "total_return_pct",
        "max_dd_pct",
        "sharpe",
        "ulcer_pct",
        "rolling252_dd30_breach_rate",
        "rolling504_dd30_breach_rate",
        "annual_cold_start_dd30_pass_rate",
        "quarter_cold_start_dd30_pass_rate",
    ]
    horizon_cols = [
        "variant",
        "horizon_days",
        "return_p05_pct",
        "return_median_pct",
        "positive_return_rate",
        "annualized_below_5pct_rate",
        "max_dd_worst_pct",
        "dd20_breach_rate",
        "dd30_breach_rate",
        "ulcer_p95_pct",
        "longest_underwater_p95_days",
    ]
    gate_cols = [
        "variant",
        "hard_constraint_pass",
        "score_90d",
        "score_180d",
        "short_holding_score",
        "improved_count_90d",
        "improved_count_180d",
        "promotion_gate_pass",
        "failed_hard_constraints",
    ]
    largest = trade_delta.reindex(
        trade_delta["preferred_open_delta_vs_engine_trade"].abs().sort_values(ascending=False).index
    ).head(30)
    report = [
        "# Stage150 分钟代理执行权益重构审计",
        "",
        f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "- 阶段性质：执行口径重构；不新增策略、不修改 Stage079/C3/Stage103 交易规则。",
        "- 基准：Stage079 = `50万C3下单 + 11.5万外部现金`。",
        "- 关键修正：执行损益差必须用 `proxy_price - theoretical_price`，不能用 `proxy_price - same_day_close`。",
        "",
        "## 外部调研判断",
        "",
        "- Implementation shortfall 的核心是决策/模型价格与实际执行价格之间的损益差。",
        "- 日线策略可以用日线生成信号，但成交建模需要使用下一可执行时点或更低频数据；Backtrader/Nautilus 等框架文档也都强调订单执行发生在后续 bar 或带有明确 bar 时间语义。",
        "- 因此本阶段只做一阶实现偏差审计，不把结果当成完整真实引擎回测。",
        "",
        "## 决策",
        "",
        f"- 决策标签：`{decision['decision']}`。",
        f"- 机械分数门禁通过项：`{decision['mechanical_promotion_gate_pass_variants']}`。",
        f"- 本阶段实际晋级项：`{decision['actual_promotion_gate_pass_variants']}`。",
        "- 说明：机械分数门禁只表示一阶权益曲线满足既定分数，不代表允许真实晋级。",
        f"- Stage149账本交易数：`{decision['trade_count']}`。",
        f"- 有效 theoretical price 交易数：`{decision['valid_theoretical_trade_count']}`。",
        f"- 14:55 VWAP 可用交易数：`{decision['same_last5_available_trade_count']}`。",
        f"- preferred real open 可用交易数：`{decision['preferred_open_available_trade_count']}`。",
        f"- 14:55 VWAP 一阶执行差合计：`{decision['same_last5_total_delta_vs_engine_trade']:.2f}`。",
        f"- preferred real open 一阶执行差合计：`{decision['preferred_open_total_delta_vs_engine_trade']:.2f}`。",
        "",
        "## 全周期指标",
        "",
        _md_table(summary[summary_cols]),
        "",
        "## 3个月/6个月体验",
        "",
        _md_table(horizon[horizon_cols].sort_values(["variant", "horizon_days"])),
        "",
        "## 分数与硬约束",
        "",
        _md_table(gate[gate_cols]),
        "",
        "## 成本压力",
        "",
        _md_table(
            cost[["variant", "slippage_multiplier", "max_dd_pct", "baseline_stage079_max_dd_pct", "not_worse_than_stage079_stress"]]
        ),
        "",
        "## preferred open 最大单笔实现偏差",
        "",
        _md_table(
            largest[
                [
                    "trade_id",
                    "trade_date",
                    "open_adjust_date",
                    "vt_symbol",
                    "direction",
                    "offset",
                    "theoretical_price",
                    "preferred_real_open_proxy",
                    "preferred_open_delta_vs_engine_trade",
                    "same_last5_vwap",
                    "same_last5_delta_vs_engine_trade",
                ]
            ],
            max_rows=30,
        ),
        "",
        "## 结论",
        "",
        "- 这是必要但仍不充分的执行审计：它修正了成交价实现偏差，但未重放因成交时点变化导致的后续持仓路径变化。",
        "- 若分钟代理曲线已经打穿 Stage079 硬约束，Stage103 或任何新候选都不能进入真实 paper/影子盘。",
        "- 若分钟代理曲线未打穿，只能说明成交价一阶偏差可接受，下一步仍要做真实引擎路径重放。",
        "",
        "## 过拟合与继续价值反思",
        "",
        "- 运行前过拟合反思：否。只替换执行价格评价口径，不改变信号、不筛日期/品种、不调参数。",
        "- 运行后过拟合反思：否。结果只用于执行模型裁决，不作为过滤或加仓规则。",
        "- 运行前继续价值反思：是。Stage149 的 same close 现金差不能直接用于权益，必须回到原引擎成交价。",
        "- 运行后继续价值反思：若一阶执行偏差仍显著，应继续做真实路径重放；若已明显失败，应暂停新alpha优化。",
    ]
    REPORT_PATH.write_text("\n".join(report), encoding="utf-8")


def main() -> None:
    stage403 = _load_stage403_daily()
    trading_dates = pd.DatetimeIndex(
        stage403[stage403["variant"].eq(BASELINE_VARIANT)]
        .drop_duplicates("date", keep="last")
        .sort_values("date")["date"]
    )
    trade_delta = _load_trade_delta(trading_dates)
    daily = _build_daily(stage403, trade_delta)
    variants = [
        {
            "variant": BASELINE_VARIANT,
            "label": "Stage079 original same-day engine",
            "equity_col": "stage079_rebuilt_original",
            "capital_used": ACCOUNT_CAPITAL,
        },
        {
            "variant": "stage079_minute_1455_vwap",
            "label": "Stage079 C3 14:55 last5 VWAP first-order",
            "equity_col": "stage079_minute_1455_vwap",
            "capital_used": ACCOUNT_CAPITAL,
        },
        {
            "variant": "stage079_minute_1455_first_open",
            "label": "Stage079 C3 14:55 first-open first-order",
            "equity_col": "stage079_minute_1455_first_open",
            "capital_used": ACCOUNT_CAPITAL,
        },
        {
            "variant": "stage079_minute_preferred_open",
            "label": "Stage079 C3 next session open first-order",
            "equity_col": "stage079_minute_preferred_open",
            "capital_used": ACCOUNT_CAPITAL,
        },
        {
            "variant": "stage103_original_same",
            "label": "Stage103 original same-day engine",
            "equity_col": "stage103_original_equity",
            "capital_used": ACCOUNT_CAPITAL,
        },
        {
            "variant": "stage103_minute_1455_vwap_c3_only",
            "label": "Stage103 C3 14:55 VWAP first-order, xsmom frozen",
            "equity_col": "stage103_minute_1455_vwap_c3_only",
            "capital_used": ACCOUNT_CAPITAL,
        },
        {
            "variant": "stage103_minute_preferred_open_c3_only",
            "label": "Stage103 C3 next session open first-order, xsmom frozen",
            "equity_col": "stage103_minute_preferred_open_c3_only",
            "capital_used": ACCOUNT_CAPITAL,
        },
    ]

    summary_rows: list[dict[str, Any]] = []
    horizon_rows: list[dict[str, Any]] = []
    for item in variants:
        equity = _calendar_equity(daily, item["equity_col"])
        summary_rows.append(_summary_for(item["variant"], item["label"], equity, item["capital_used"]))
        for horizon_days in (90, 180):
            horizon_rows.append(_horizon_for(item["variant"], item["label"], equity, horizon_days))
    summary = pd.DataFrame(summary_rows)
    horizon = pd.DataFrame(horizon_rows)
    score = _score_horizons(horizon)
    cost = _cost_stress(daily, variants)
    gate = _gate(summary, horizon, score, cost)

    decision = {
        "stage": "Stage150",
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "decision": "minute_execution_first_order_rebuild_complete_need_true_path_replay",
        "trade_count": int(len(trade_delta)),
        "valid_theoretical_trade_count": int(trade_delta["valid_theoretical_price"].sum()),
        "same_last5_available_trade_count": int(trade_delta["has_same_last5_vwap"].sum()),
        "preferred_open_available_trade_count": int(trade_delta["has_preferred_open"].sum()),
        "same_last5_total_delta_vs_engine_trade": float(trade_delta["same_last5_delta_vs_engine_trade"].sum()),
        "preferred_open_total_delta_vs_engine_trade": float(trade_delta["preferred_open_delta_vs_engine_trade"].sum()),
        "mechanical_promotion_gate_pass_variants": gate[gate["promotion_gate_pass"].eq(1)]["variant"].tolist(),
        "actual_promotion_gate_pass_variants": [],
        "execution_audit_not_strategy_promotion": True,
        "hard_constraint_pass_variants": gate[gate["hard_constraint_pass"].eq(1)]["variant"].tolist(),
        "outputs": {
            "daily": str(DAILY_PATH),
            "trade_delta": str(TRADE_DELTA_PATH),
            "summary": str(SUMMARY_PATH),
            "horizon": str(HORIZON_PATH),
            "score": str(SCORE_PATH),
            "cost": str(COST_PATH),
            "gate": str(GATE_PATH),
            "chart": str(CHART_PATH),
            "report": str(REPORT_PATH),
        },
        "next_step": "用分钟代理成交价做真实引擎路径重放；若路径重放仍保留Stage079硬约束，再讨论3/6个月体验优化。",
    }

    daily.to_csv(DAILY_PATH, index=False, encoding="utf-8-sig")
    trade_delta.to_csv(TRADE_DELTA_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    horizon.to_csv(HORIZON_PATH, index=False, encoding="utf-8-sig")
    score.to_csv(SCORE_PATH, index=False, encoding="utf-8-sig")
    cost.to_csv(COST_PATH, index=False, encoding="utf-8-sig")
    gate.to_csv(GATE_PATH, index=False, encoding="utf-8-sig")
    _plot(daily)
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(summary, horizon, score, cost, gate, trade_delta, decision)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print(f"wrote: {REPORT_PATH}")


if __name__ == "__main__":
    main()
