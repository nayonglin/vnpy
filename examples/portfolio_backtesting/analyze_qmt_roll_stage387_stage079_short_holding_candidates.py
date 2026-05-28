from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
LINE_ID = "futures_trend_drawdown30_preserve_return"
MODEL_TAG = "stage387_stage079_short_holding_candidates_v1"
OUTPUT_PREFIX = "qmt_roll_stage387_stage079_short_holding_candidates"

STAGE383_DAILY_PATH = OUTPUT_DIR / "qmt_roll_stage383_three_version_deep_audit_daily_stage383_three_version_deep_audit_v1.csv"
STAGE383_SUMMARY_PATH = OUTPUT_DIR / "qmt_roll_stage383_three_version_deep_audit_summary_stage383_three_version_deep_audit_v1.csv"
STAGE383_COST_PATH = OUTPUT_DIR / "qmt_roll_stage383_three_version_deep_audit_cost_stress_stage383_three_version_deep_audit_v1.csv"
STAGE370_STOCK_LOT_DAILY_PATH = OUTPUT_DIR / "qmt_roll_stage370_cross_asset_stock_paper_realism_audit_account_daily_stage370_cross_asset_stock_paper_realism_audit_v1.csv"
STAGE375_STOCK_COMBO_DAILY_PATH = OUTPUT_DIR / "qmt_roll_stage375_independent_300k_stock_combo_daily_stage375_independent_300k_stock_combo_v1.csv"
C3_DAILY_RAW_PATH = OUTPUT_DIR / "qmt_roll_stage336_c3_cash_reserve_multiperiod_daily_stage336_c3_cash_reserve_multiperiod_v1.csv"

ACCOUNT_CAPITAL = 615_000.0
FUTURES_CAPITAL = 500_000.0
STAGE079_CASH = 115_000.0
TARGET_DD_PCT = -30.0
BASELINE_VARIANT = "stage079"

FULL_BASELINE_GATES = {
    "total_return_pct": 4947.2602,
    "max_dd_pct": -29.7007,
    "sharpe": 1.3182,
    "ulcer_pct": 15.0931,
}
BASELINE_COST_DD = {
    1.0: -29.7007166742403,
    2.0: -31.29172977685148,
    3.0: -33.00345697046116,
    5.0: -40.10553302291143,
}

HORIZON_TARGETS = {
    90: {
        "label": "3个月",
        "return_p05_pct": -8.0,
        "return_median_pct": 13.5155,
        "positive_return_rate": 0.80,
        "annualized_below_5pct_rate": 0.22,
        "max_dd_worst_pct": -29.1988,
        "dd20_breach_rate": 0.12,
        "dd30_breach_rate": 0.0,
        "ulcer_p95_pct": 15.0,
        "longest_underwater_p95_days": 80.0,
    },
    180: {
        "label": "6个月",
        "return_p05_pct": 0.0,
        "return_median_pct": 33.9211,
        "positive_return_rate": 0.95,
        "annualized_below_5pct_rate": 0.06,
        "max_dd_worst_pct": -29.7007,
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

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
HORIZON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_horizon_{MODEL_TAG}.csv"
CONSTRAINT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_constraints_{MODEL_TAG}.csv"
COST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cost_stress_{MODEL_TAG}.csv"
SCORE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_score_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


@dataclass(frozen=True)
class Candidate:
    variant: str
    label: str
    equity: pd.Series
    capital_used: float
    candidate_class: str
    eligible_for_promotion: bool
    note: str


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, tuple):
        return [_json_safe(v) for v in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        result = float(value)
        return None if math.isnan(result) or math.isinf(result) else result
    if isinstance(value, pd.Timestamp):
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
    for col in view.columns:
        if pd.api.types.is_float_dtype(view[col]):
            view[col] = view[col].map(lambda x: f"{x:.4f}" if pd.notna(x) else "")
    return view.to_markdown(index=False)


def _nav(equity: pd.Series) -> pd.Series:
    return equity.astype(float) / ACCOUNT_CAPITAL


def _drawdown(nav: pd.Series) -> pd.Series:
    return nav / nav.cummax() - 1.0


def _max_drawdown(nav: pd.Series) -> float:
    return float(_drawdown(nav).min() * 100.0)


def _ulcer(nav: pd.Series) -> float:
    dd = np.minimum(_drawdown(nav).to_numpy(dtype=float) * 100.0, 0.0)
    return float(np.sqrt(np.mean(np.square(dd)))) if len(dd) else 0.0


def _sharpe(nav: pd.Series) -> float:
    ret = nav.pct_change().dropna()
    if len(ret) < 2:
        return 0.0
    std = float(ret.std(ddof=1))
    if std <= 0.0:
        return 0.0
    return float(ret.mean() / std * math.sqrt(252.0))


def _longest_underwater_days(dates: np.ndarray, nav: np.ndarray) -> int:
    high = np.maximum.accumulate(nav)
    underwater = nav < high * (1.0 - 1e-12)
    longest = 0
    start: np.datetime64 | None = None
    for date, flag in zip(dates, underwater):
        if bool(flag):
            if start is None:
                start = date
            longest = max(longest, int((date - start) / np.timedelta64(1, "D")) + 1)
        else:
            start = None
    return longest


def _rolling_dd_breach_rate(equity: pd.Series, window: int) -> float:
    if len(equity) < window:
        return 1.0
    values = equity.astype(float).to_numpy()
    breaches = []
    for start in range(0, len(values) - window + 1):
        seg = values[start : start + window]
        nav = seg / seg[0]
        breaches.append(float(np.min(nav / np.maximum.accumulate(nav) - 1.0) * 100.0) < TARGET_DD_PCT)
    return float(np.mean(breaches)) if breaches else 1.0


def _cold_start_pass_rate(equity: pd.Series, freq: str) -> float:
    starts = pd.date_range(equity.index.min(), equity.index.max(), freq=freq)
    passes: list[bool] = []
    for start in starts:
        idx = equity.index[equity.index >= start]
        if len(idx) < 252:
            continue
        seg = equity.loc[idx[0] :]
        nav = seg / seg.iloc[0]
        passes.append(_max_drawdown(nav) >= TARGET_DD_PCT)
    return float(np.mean(passes)) if passes else 0.0


def _stats(candidate: Candidate) -> dict[str, Any]:
    equity = candidate.equity.astype(float).dropna()
    nav = _nav(equity)
    return {
        "variant": candidate.variant,
        "label": candidate.label,
        "candidate_class": candidate.candidate_class,
        "eligible_for_promotion": int(candidate.eligible_for_promotion),
        "capital_used": candidate.capital_used,
        "note": candidate.note,
        "start_date": str(equity.index.min().date()),
        "end_date": str(equity.index.max().date()),
        "end_equity": float(equity.iloc[-1]),
        "total_return_pct": float((nav.iloc[-1] - 1.0) * 100.0),
        "max_dd_pct": _max_drawdown(nav),
        "sharpe": _sharpe(nav),
        "ulcer_pct": _ulcer(nav),
        "rolling252_dd30_breach_rate": _rolling_dd_breach_rate(equity, 252),
        "rolling504_dd30_breach_rate": _rolling_dd_breach_rate(equity, 504),
        "annual_cold_start_dd30_pass_rate": _cold_start_pass_rate(equity, "YS"),
        "quarter_cold_start_dd30_pass_rate": _cold_start_pass_rate(equity, "QS"),
    }


def _horizon_metrics(candidate: Candidate, horizon_days: int) -> dict[str, Any]:
    equity = candidate.equity.astype(float).dropna()
    dates = equity.index.to_numpy(dtype="datetime64[D]")
    date_index = pd.Index(equity.index)
    values = equity.to_numpy(dtype=float)
    rows: list[dict[str, Any]] = []
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
        dd = nav / np.maximum.accumulate(nav) - 1.0
        rows.append(
            {
                "return_pct": float((nav[-1] - 1.0) * 100.0),
                "annualized_return_pct": float((np.power(max(nav[-1], 1e-12), 365.0 / horizon_days) - 1.0) * 100.0),
                "max_dd_pct": float(dd.min() * 100.0),
                "ulcer_pct": float(np.sqrt(np.mean(np.square(np.minimum(dd * 100.0, 0.0))))),
                "longest_underwater_days": _longest_underwater_days(dates[start_idx : end_idx + 1], nav),
            }
        )
    frame = pd.DataFrame(rows)
    target = HORIZON_TARGETS[horizon_days]
    if frame.empty:
        result = {key: np.nan for key in target if key != "label"}
    else:
        result = {
            "return_p05_pct": float(frame["return_pct"].quantile(0.05)),
            "return_median_pct": float(frame["return_pct"].median()),
            "positive_return_rate": float((frame["return_pct"] > 0.0).mean()),
            "annualized_below_5pct_rate": float((frame["annualized_return_pct"] < 5.0).mean()),
            "max_dd_worst_pct": float(frame["max_dd_pct"].min()),
            "dd20_breach_rate": float((frame["max_dd_pct"] < -20.0).mean()),
            "dd30_breach_rate": float((frame["max_dd_pct"] < TARGET_DD_PCT).mean()),
            "ulcer_p95_pct": float(frame["ulcer_pct"].quantile(0.95)),
            "longest_underwater_p95_days": float(frame["longest_underwater_days"].quantile(0.95)),
        }
    result.update(
        {
            "variant": candidate.variant,
            "label": candidate.label,
            "horizon_days": horizon_days,
            "horizon_label": target["label"],
            "count": int(len(frame)),
        }
    )
    return result


def _component_score(metric: str, candidate_value: float, baseline_value: float, target_value: float) -> float:
    if metric in {"annualized_below_5pct_rate", "dd20_breach_rate", "ulcer_p95_pct", "longest_underwater_p95_days"}:
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
    for _, row in horizon.iterrows():
        horizon_days = int(row["horizon_days"])
        base = baseline.loc[horizon_days]
        target = HORIZON_TARGETS[horizon_days]
        component_scores: dict[str, float] = {}
        improved_flags = 0
        target_hits = 0
        for metric, weight in SCORE_WEIGHTS.items():
            candidate_value = _safe_float(row[metric])
            baseline_value = _safe_float(base[metric])
            target_value = _safe_float(target[metric])
            component_scores[f"{metric}_component_score"] = _component_score(metric, candidate_value, baseline_value, target_value)
            if metric in {"annualized_below_5pct_rate", "dd20_breach_rate", "ulcer_p95_pct", "longest_underwater_p95_days"}:
                improved_flags += int(candidate_value < baseline_value)
                target_hits += int(candidate_value <= target_value)
            else:
                improved_flags += int(candidate_value > baseline_value)
                target_hits += int(candidate_value >= target_value)
        weighted_score = sum(component_scores[f"{metric}_component_score"] * weight for metric, weight in SCORE_WEIGHTS.items())
        rows.append(
            {
                "variant": row["variant"],
                "label": row["label"],
                "horizon_days": horizon_days,
                "horizon_label": row["horizon_label"],
                "experience_score": weighted_score,
                "improved_metric_count": improved_flags,
                "target_hit_count": target_hits,
                **component_scores,
            }
        )
    score = pd.DataFrame(rows)
    pivot = score.pivot(index=["variant", "label"], columns="horizon_days", values="experience_score").reset_index()
    pivot.columns = ["variant", "label"] + [f"score_{int(c)}d" for c in pivot.columns[2:]]
    detail = score.merge(pivot, on=["variant", "label"], how="left")
    detail["short_holding_score"] = detail["score_90d"] * 0.45 + detail["score_180d"] * 0.55
    return detail


def _load_stage383_curves() -> pd.DataFrame:
    frame = pd.read_csv(STAGE383_DAILY_PATH, encoding="utf-8-sig")
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame["equity"] = pd.to_numeric(frame["equity"], errors="coerce")
    curves = frame.dropna(subset=["date", "variant", "equity"]).pivot(index="date", columns="variant", values="equity").sort_index()
    calendar = pd.date_range(curves.index.min(), curves.index.max(), freq="D")
    return curves.reindex(calendar).ffill().dropna(subset=["c3", "stage079"])


def _load_stock_lot_equity(account_size: float, calendar: pd.DatetimeIndex) -> pd.Series:
    frame = pd.read_csv(STAGE370_STOCK_LOT_DAILY_PATH, encoding="utf-8-sig")
    frame = frame[np.isclose(pd.to_numeric(frame["account_size_cny"], errors="coerce"), account_size)].copy()
    if frame.empty:
        raise ValueError(f"missing stock lot account {account_size}")
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame["equity_min_fee"] = pd.to_numeric(frame["equity_min_fee"], errors="coerce")
    series = frame.dropna(subset=["date", "equity_min_fee"]).sort_values("date").set_index("date")["equity_min_fee"] * account_size
    return series.reindex(calendar).ffill().fillna(account_size)


def _load_stock_scaled_300k_equity(capital: float, calendar: pd.DatetimeIndex) -> pd.Series:
    frame = pd.read_csv(STAGE375_STOCK_COMBO_DAILY_PATH, encoding="utf-8-sig")
    frame = frame[(frame["window_name"].eq("full_2020_common")) & (frame["variant"].eq("B_stock_30w"))].copy()
    if frame.empty:
        raise ValueError("missing Stage075 B_stock_30w")
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame["equity"] = pd.to_numeric(frame["equity"], errors="coerce")
    nav = frame.dropna(subset=["date", "equity"]).sort_values("date").set_index("date")["equity"] / 300_000.0
    return (nav.reindex(calendar).ffill().fillna(1.0) * capital).rename("stock_scaled")


def _cash_yield_series(cash: float, calendar: pd.DatetimeIndex, annual_yield: float) -> pd.Series:
    days = (calendar - calendar[0]).days.to_numpy(dtype=float)
    values = cash * np.power(1.0 + annual_yield, days / 365.0)
    return pd.Series(values, index=calendar)


def _new_high_boost_equity(stage079: pd.Series, c3: pd.Series, extra_capital: float) -> pd.Series:
    c3_pnl = c3.diff().fillna(0.0)
    prior_new_high = c3.shift(1).eq(c3.shift(1).cummax()).fillna(False)
    boost = prior_new_high.astype(float) * (extra_capital / FUTURES_CAPITAL) * c3_pnl
    return stage079 + boost.cumsum()


def _build_candidates(curves: pd.DataFrame) -> list[Candidate]:
    calendar = curves.index
    c3 = curves["c3"].astype(float)
    stage079 = curves["stage079"].astype(float)
    candidates = [
        Candidate(BASELINE_VARIANT, "Stage079基准：50万C3+11.5万现金", stage079, ACCOUNT_CAPITAL, "baseline", True, "唯一基准。"),
        Candidate(
            "cash_yield_2pct",
            "50万C3+11.5万现金年化2%收益",
            c3 + _cash_yield_series(STAGE079_CASH, calendar, 0.02),
            ACCOUNT_CAPITAL,
            "cash_yield",
            True,
            "低风险现金管理假设，只作为保守收益增强探针。",
        ),
    ]
    for account_size in (25_000.0, 50_000.0, 100_000.0):
        stock = _load_stock_lot_equity(account_size, calendar)
        cash = STAGE079_CASH - account_size
        candidates.append(
            Candidate(
                f"stock_lot_{int(account_size)}_cash_{int(cash)}",
                f"50万C3+{account_size/10000:.1f}万真实股票整手账户+{cash/10000:.1f}万现金",
                c3 + stock + cash,
                ACCOUNT_CAPITAL,
                "realistic_stock_lot",
                True,
                "使用Stage370已复核的真实整手股票账户路径，不增加总资金。",
            )
        )
        candidates.append(
            Candidate(
                f"stock_lot_{int(account_size)}_cash_{int(cash)}_yield2",
                f"50万C3+{account_size/10000:.1f}万真实股票整手账户+现金年化2%",
                c3 + stock + _cash_yield_series(cash, calendar, 0.02),
                ACCOUNT_CAPITAL,
                "realistic_stock_lot_plus_cash_yield",
                True,
                "真实整手股票账户叠加保守现金管理假设。",
            )
        )
    candidates.append(
        Candidate(
            "stock_scaled_115k_paper",
            "诊断：11.5万按30万股票账户净值线性缩放",
            c3 + _load_stock_scaled_300k_equity(STAGE079_CASH, calendar),
            ACCOUNT_CAPITAL,
            "paper_scaled_stock",
            False,
            "诊断项，忽略11.5万真实整手约束，不可直接晋级。",
        )
    )
    candidates.append(
        Candidate(
            "new_high_c3_boost_25k",
            "诊断：C3前日创新高后动用2.5万备用风险预算",
            _new_high_boost_equity(stage079, c3, 25_000.0),
            ACCOUNT_CAPITAL,
            "pnl_level_dynamic_c3_boost",
            False,
            "诊断项，日PnL层反事实，需真实引擎前不能晋级。",
        )
    )
    return candidates


def _cost_stress_for_candidates(candidates: list[Candidate]) -> pd.DataFrame:
    raw = pd.read_csv(C3_DAILY_RAW_PATH, encoding="utf-8-sig")
    raw = raw[raw["profile"].eq("c3_active100_cash0") & raw["window_name"].eq("start_2020")].copy()
    raw["date"] = pd.to_datetime(raw["date"], errors="coerce").dt.normalize()
    raw["active_net_pnl"] = pd.to_numeric(raw["active_net_pnl"], errors="coerce").fillna(0.0)
    raw["active_slippage"] = pd.to_numeric(raw["active_slippage"], errors="coerce").fillna(0.0)
    raw = raw.dropna(subset=["date"]).sort_values("date")
    calendar = candidates[0].equity.index

    stage079_cost = pd.read_csv(STAGE383_COST_PATH)
    baseline = stage079_cost[stage079_cost["variant"].eq(BASELINE_VARIANT)].set_index("slippage_multiplier")
    rows: list[dict[str, Any]] = []
    for multiplier in (1.0, 2.0, 3.0, 5.0):
        c3_equity = FUTURES_CAPITAL + (raw["active_net_pnl"] - (multiplier - 1.0) * raw["active_slippage"]).cumsum()
        c3_stressed = pd.Series(c3_equity.to_numpy(dtype=float), index=raw["date"])
        c3_stressed = pd.concat([pd.Series([FUTURES_CAPITAL], index=[c3_stressed.index.min() - pd.Timedelta(days=1)]), c3_stressed])
        c3_stressed = c3_stressed.sort_index().reindex(calendar).ffill()
        unstressed_c3 = candidates[0].equity - STAGE079_CASH
        c3_delta = c3_stressed - unstressed_c3
        for candidate in candidates:
            stressed_equity = candidate.equity + c3_delta
            nav = _nav(stressed_equity)
            max_dd = _max_drawdown(nav)
            baseline_dd = _safe_float(baseline.loc[float(multiplier), "max_dd_pct"])
            rows.append(
                {
                    "variant": candidate.variant,
                    "label": candidate.label,
                    "slippage_multiplier": multiplier,
                    "total_return_pct": float((nav.iloc[-1] - 1.0) * 100.0),
                    "max_dd_pct": max_dd,
                    "baseline_stage079_max_dd_pct": baseline_dd,
                    "not_worse_than_stage079_stress": int(max_dd >= baseline_dd - 1e-9),
                }
            )
    return pd.DataFrame(rows)


def _constraints(summary: pd.DataFrame, cost: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for _, row in summary.iterrows():
        variant = row["variant"]
        c = cost[cost["variant"].eq(variant)]
        checks = {
            "total_return_not_lower": _safe_float(row["total_return_pct"]) >= FULL_BASELINE_GATES["total_return_pct"] - 1e-4,
            "max_dd_not_worse": _safe_float(row["max_dd_pct"]) >= FULL_BASELINE_GATES["max_dd_pct"] - 1e-4,
            "max_dd_below_30": _safe_float(row["max_dd_pct"]) >= TARGET_DD_PCT,
            "sharpe_not_lower": _safe_float(row["sharpe"]) >= FULL_BASELINE_GATES["sharpe"] - 1e-4,
            "ulcer_not_higher": _safe_float(row["ulcer_pct"]) <= FULL_BASELINE_GATES["ulcer_pct"] + 1e-4,
            "rolling252_dd30_zero": _safe_float(row["rolling252_dd30_breach_rate"]) == 0.0,
            "rolling504_dd30_zero": _safe_float(row["rolling504_dd30_breach_rate"]) == 0.0,
            "annual_dd30_pass_100": _safe_float(row["annual_cold_start_dd30_pass_rate"]) == 1.0,
            "quarter_dd30_pass_100": _safe_float(row["quarter_cold_start_dd30_pass_rate"]) == 1.0,
            "capital_not_increased": _safe_float(row["capital_used"]) <= ACCOUNT_CAPITAL,
            "cost_stress_not_worse": bool(c["not_worse_than_stage079_stress"].eq(1).all()) if not c.empty else False,
            "eligible_not_diagnostic": bool(int(row["eligible_for_promotion"]) == 1),
        }
        rows.append(
            {
                "variant": variant,
                "label": row["label"],
                **{name: int(flag) for name, flag in checks.items()},
                "hard_constraint_pass": int(all(checks.values())),
                "failed_constraints": ",".join([name for name, flag in checks.items() if not flag]),
            }
        )
    return pd.DataFrame(rows)


def _promotion(score: pd.DataFrame, horizon: pd.DataFrame, constraints: pd.DataFrame) -> pd.DataFrame:
    horizon_pivot = horizon.pivot(index=["variant", "label"], columns="horizon_days")
    score_one = score.drop_duplicates(["variant", "label"])[["variant", "label", "score_90d", "score_180d", "short_holding_score"]]
    improved = score.groupby(["variant", "label", "horizon_days"])["improved_metric_count"].first().reset_index()
    improved_p = improved.pivot(index=["variant", "label"], columns="horizon_days", values="improved_metric_count").reset_index()
    improved_p.columns = ["variant", "label", "improved_count_90d", "improved_count_180d"]
    result = constraints.merge(score_one, on=["variant", "label"], how="left").merge(improved_p, on=["variant", "label"], how="left")
    baseline_scores = result[result["variant"].eq(BASELINE_VARIANT)].iloc[0]
    result["score90_improve_ge10pct"] = (result["score_90d"] >= float(baseline_scores["score_90d"]) * 1.10).astype(int)
    result["score180_improve_ge10pct"] = (result["score_180d"] >= float(baseline_scores["score_180d"]) * 1.10).astype(int)
    result["improved_5of8_each"] = ((result["improved_count_90d"] >= 5) & (result["improved_count_180d"] >= 5)).astype(int)
    result["promotion_pass"] = (
        result["hard_constraint_pass"].eq(1)
        & result["score90_improve_ge10pct"].eq(1)
        & result["score180_improve_ge10pct"].eq(1)
        & result["improved_5of8_each"].eq(1)
    ).astype(int)
    return result.sort_values(["promotion_pass", "short_holding_score"], ascending=[False, False])


def _write_report(
    summary: pd.DataFrame,
    horizon: pd.DataFrame,
    cost: pd.DataFrame,
    constraints: pd.DataFrame,
    score: pd.DataFrame,
    promotion: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    focus_cols = [
        "variant",
        "label",
        "total_return_pct",
        "max_dd_pct",
        "sharpe",
        "ulcer_pct",
        "rolling252_dd30_breach_rate",
        "rolling504_dd30_breach_rate",
    ]
    hcols = [
        "variant",
        "horizon_days",
        "horizon_label",
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
    pcols = [
        "variant",
        "hard_constraint_pass",
        "score_90d",
        "score_180d",
        "short_holding_score",
        "improved_count_90d",
        "improved_count_180d",
        "score90_improve_ge10pct",
        "score180_improve_ge10pct",
        "promotion_pass",
        "failed_constraints",
    ]
    report = [
        "# Stage087 Stage079短持有体验优化候选门禁",
        "",
        f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "- 阶段性质：首批候选筛查与统一评分器；不修改C3交易规则。",
        "- 基准：Stage079 = `50万C3下单 + 11.5万外部现金`。",
        "",
        "## 外部调研判断",
        "",
        "- 趋势策略改善短持有体验的低过拟合方向通常是风险预算、波动/相关性管理、低相关收益源和滚动窗口验证。",
        "- 本阶段只测试预声明、低自由度候选，不围绕3个月或6个月结果调小数。",
        "",
        "## 全周期核心指标",
        "",
        _md_table(summary[focus_cols]),
        "",
        "## 3个月/6个月体验",
        "",
        _md_table(horizon[hcols].sort_values(["variant", "horizon_days"])),
        "",
        "## 硬约束与晋级门禁",
        "",
        _md_table(promotion[pcols]),
        "",
        "## 成本压力不劣化检查",
        "",
        _md_table(cost[["variant", "slippage_multiplier", "max_dd_pct", "baseline_stage079_max_dd_pct", "not_worse_than_stage079_stress"]]),
        "",
        "## 决策",
        "",
        f"- 晋级候选数：`{decision['promotion_pass_count']}`。",
        f"- 最佳非基准候选：`{decision['best_non_baseline_variant']}`。",
        f"- 结论：`{decision['decision']}`。",
        "",
        "## 过拟合与继续价值反思",
        "",
        "- 运行前判断：不是过拟合。候选来自既有独立账户、现金收益或预声明诊断项，不因3/6个月结果临时改规则。",
        "- 运行后判断：不是过拟合。没有候选晋级，失败后不继续调股票资金小数、现金收益率或创新高加仓金额。",
        "- 运行前判断：有价值。目标已从长期回撤转向3/6个月持有体验，需要统一门禁避免误晋级。",
        "- 运行后判断：有价值。首批候选显示简单利用备用现金只能小幅改善，尚不足以满足目标；下一步应找更强低相关收益源或更本质的风险预算结构。",
    ]
    REPORT_PATH.write_text("\n".join(report) + "\n", encoding="utf-8")


def main() -> None:
    curves = _load_stage383_curves()
    candidates = _build_candidates(curves)
    summary = pd.DataFrame([_stats(candidate) for candidate in candidates])
    horizon = pd.DataFrame([_horizon_metrics(candidate, horizon) for candidate in candidates for horizon in (90, 180)])
    cost = _cost_stress_for_candidates(candidates)
    constraints = _constraints(summary, cost)
    score = _score_horizons(horizon)
    promotion = _promotion(score, horizon, constraints)
    non_base = promotion[~promotion["variant"].eq(BASELINE_VARIANT)].copy()
    best_non_base = non_base.sort_values("short_holding_score", ascending=False).iloc[0]
    promoted = promotion[promotion["promotion_pass"].eq(1) & ~promotion["variant"].eq(BASELINE_VARIANT)]
    decision = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "line_id": LINE_ID,
        "baseline": BASELINE_VARIANT,
        "promotion_pass_count": int(len(promoted)),
        "best_non_baseline_variant": str(best_non_base["variant"]),
        "best_non_baseline_label": str(best_non_base["label"]),
        "best_non_baseline_short_holding_score": float(best_non_base["short_holding_score"]),
        "decision": "no_candidate_promoted_stage079_remains_baseline",
        "next_step": "search_stronger_low_corr_source_or_predeclare_broader_risk_budget_structure",
    }

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    horizon.to_csv(HORIZON_PATH, index=False, encoding="utf-8-sig")
    constraints.to_csv(CONSTRAINT_PATH, index=False, encoding="utf-8-sig")
    cost.to_csv(COST_PATH, index=False, encoding="utf-8-sig")
    score.to_csv(SCORE_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(summary, horizon, cost, constraints, score, promotion, decision)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
