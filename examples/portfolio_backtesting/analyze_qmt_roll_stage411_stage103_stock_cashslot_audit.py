from __future__ import annotations

import json
import math
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_DIR.resolve()))

import analyze_qmt_roll_stage387_stage079_short_holding_candidates as s387
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
MODEL_TAG = "stage411_stage103_stock_cashslot_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage411_stage103_stock_cashslot_audit"
LINE_ID = "futures_trend_drawdown30_preserve_return"

ACCOUNT_CAPITAL = 615_000.0
STAGE079_CASH = 115_000.0
BASELINE_VARIANT = "stage079"
STAGE103_VARIANT = "xsmom_vt10_q_momq_round_half_true_broker10_guard"

STAGE403_DAILY_PATH = (
    OUTPUT_DIR / "qmt_roll_stage403_stage079_xsmom_execution_margin_audit_daily_stage403_stage079_xsmom_execution_margin_audit_v1.csv"
)
STAGE403_MARGIN_AUDIT_PATH = (
    OUTPUT_DIR / "qmt_roll_stage403_stage079_xsmom_execution_margin_audit_margin_audit_stage403_stage079_xsmom_execution_margin_audit_v1.csv"
)
STAGE370_STOCK_LOT_DAILY_PATH = (
    OUTPUT_DIR / "qmt_roll_stage370_cross_asset_stock_paper_realism_audit_account_daily_stage370_cross_asset_stock_paper_realism_audit_v1.csv"
)
STAGE375_STOCK_COMBO_DAILY_PATH = (
    OUTPUT_DIR / "qmt_roll_stage375_independent_300k_stock_combo_daily_stage375_independent_300k_stock_combo_v1.csv"
)

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
HORIZON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_horizon_{MODEL_TAG}.csv"
SCORE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_score_{MODEL_TAG}.csv"
COST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cost_stress_{MODEL_TAG}.csv"
GATE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gate_{MODEL_TAG}.csv"
DAILY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_{MODEL_TAG}.csv"
DIAGNOSTIC_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_marginal_diagnostic_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"


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


def _load_stage403_daily() -> pd.DataFrame:
    frame = pd.read_csv(STAGE403_DAILY_PATH, encoding="utf-8-sig")
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame = frame[frame["window_name"].eq("start_2020") & frame["variant"].isin([BASELINE_VARIANT, STAGE103_VARIANT])].copy()
    numeric_cols = [
        "c3_net_pnl",
        "c3_slippage",
        "satellite_daily_pnl",
        "satellite_slippage_cost",
        "combo_slippage",
        "equity",
    ]
    for col in numeric_cols:
        frame[col] = pd.to_numeric(frame[col], errors="coerce").fillna(0.0)
    return frame.sort_values(["variant", "date"])


def _variant_daily(frame: pd.DataFrame, variant: str, calendar: pd.DatetimeIndex) -> pd.DataFrame:
    daily = frame[frame["variant"].eq(variant)].sort_values("date").drop_duplicates("date", keep="last").copy()
    daily = daily.set_index("date").reindex(calendar)
    daily["equity"] = daily["equity"].ffill()
    for col in ["c3_net_pnl", "c3_slippage", "satellite_daily_pnl", "satellite_slippage_cost", "combo_slippage"]:
        daily[col] = pd.to_numeric(daily.get(col, 0.0), errors="coerce").fillna(0.0)
    daily["variant"] = variant
    return daily


def _cash_yield_series(cash: float, calendar: pd.DatetimeIndex, annual_yield: float) -> pd.Series:
    days = (calendar - calendar[0]).days.to_numpy(dtype=float)
    values = cash * np.power(1.0 + annual_yield, days / 365.0)
    return pd.Series(values, index=calendar)


def _load_stock_lot_equity(account_size: float, calendar: pd.DatetimeIndex) -> pd.Series:
    frame = pd.read_csv(STAGE370_STOCK_LOT_DAILY_PATH, encoding="utf-8-sig")
    frame = frame[np.isclose(pd.to_numeric(frame["account_size_cny"], errors="coerce"), account_size)].copy()
    if frame.empty:
        raise ValueError(f"missing stock lot account {account_size}")
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame["equity_min_fee"] = pd.to_numeric(frame["equity_min_fee"], errors="coerce")
    series = frame.dropna(subset=["date", "equity_min_fee"]).sort_values("date").set_index("date")["equity_min_fee"]
    nav = series.reindex(calendar).ffill().fillna(1.0).astype(float)
    start_nav = float(nav.iloc[0])
    if start_nav <= 0.0:
        raise ValueError(f"invalid stock lot start nav {start_nav} for account {account_size}")
    return (nav / start_nav * account_size).rename(f"stock_lot_{int(account_size)}")


def _load_stock_scaled_300k_equity(capital: float, calendar: pd.DatetimeIndex) -> pd.Series:
    frame = pd.read_csv(STAGE375_STOCK_COMBO_DAILY_PATH, encoding="utf-8-sig")
    frame = frame[(frame["window_name"].eq("full_2020_common")) & (frame["variant"].eq("B_stock_30w"))].copy()
    if frame.empty:
        raise ValueError("missing Stage075 B_stock_30w")
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame["equity"] = pd.to_numeric(frame["equity"], errors="coerce")
    nav = frame.dropna(subset=["date", "equity"]).sort_values("date").set_index("date")["equity"] / 300_000.0
    aligned = nav.reindex(calendar).ffill().fillna(1.0).astype(float)
    start_nav = float(aligned.iloc[0])
    if start_nav <= 0.0:
        raise ValueError(f"invalid scaled stock start nav {start_nav}")
    return (aligned / start_nav * capital).rename("stock_scaled")


def _candidate(
    variant: str,
    label: str,
    equity: pd.Series,
    candidate_class: str,
    eligible: bool,
    note: str,
    stock_capital: float = 0.0,
    cash_left: float = STAGE079_CASH,
) -> s387.Candidate:
    candidate = s387.Candidate(variant, label, equity, ACCOUNT_CAPITAL, candidate_class, eligible, note)
    # Attach lightweight metadata through attrs for downstream tables.
    candidate.equity.attrs["stock_capital"] = stock_capital
    candidate.equity.attrs["cash_left"] = cash_left
    return candidate


def _build_candidates(stage079: pd.Series, stage103: pd.Series, calendar: pd.DatetimeIndex) -> list[s387.Candidate]:
    stage103_core = stage103 - STAGE079_CASH
    candidates: list[s387.Candidate] = [
        _candidate(
            BASELINE_VARIANT,
            "Stage079基准：50万C3+11.5万现金",
            stage079,
            "baseline",
            True,
            "唯一baseline。",
            0.0,
            STAGE079_CASH,
        ),
        _candidate(
            STAGE103_VARIANT,
            "Stage103 broker10_guard",
            stage103,
            "stage103",
            True,
            "当前最强执行相对候选。",
            0.0,
            STAGE079_CASH,
        ),
        _candidate(
            "stage103_cash_yield_2pct",
            "Stage103+11.5万现金年化2%",
            stage103_core + _cash_yield_series(STAGE079_CASH, calendar, 0.02),
            "cash_yield",
            True,
            "不改变风险暴露，仅检验现金管理收益对短持有体验的边界。",
            0.0,
            STAGE079_CASH,
        ),
    ]
    for stock_capital in (25_000.0, 50_000.0, 100_000.0):
        cash_left = STAGE079_CASH - stock_capital
        stock = _load_stock_lot_equity(stock_capital, calendar)
        candidates.append(
            _candidate(
                f"stage103_stock_lot_{int(stock_capital)}_cash_{int(cash_left)}",
                f"Stage103+{stock_capital/10000:.1f}万真实股票整手+{cash_left/10000:.1f}万现金",
                stage103_core + stock + cash_left,
                "stage103_stock_cashslot",
                True,
                "使用Stage370真实整手股票账户路径替换一部分11.5万现金槽位，不增加总资金。",
                stock_capital,
                cash_left,
            )
        )
        candidates.append(
            _candidate(
                f"stage103_stock_lot_{int(stock_capital)}_cash_{int(cash_left)}_yield2",
                f"Stage103+{stock_capital/10000:.1f}万真实股票整手+现金年化2%",
                stage103_core + stock + _cash_yield_series(cash_left, calendar, 0.02),
                "stage103_stock_cashslot_yield",
                True,
                "真实整手股票账户叠加保守现金管理假设，不增加总资金。",
                stock_capital,
                cash_left,
            )
        )
    candidates.append(
        _candidate(
            "stage103_stock_scaled_115k_paper",
            "诊断：Stage103+11.5万按30万股票账户净值线性缩放",
            stage103_core + _load_stock_scaled_300k_equity(STAGE079_CASH, calendar),
            "paper_scaled_stock",
            False,
            "诊断项，忽略11.5万真实整手约束，不能直接晋级。",
            STAGE079_CASH,
            0.0,
        )
    )
    return candidates


def _cost_stress(candidates: list[s387.Candidate], stage_daily: dict[str, pd.DataFrame]) -> pd.DataFrame:
    baseline_stress_dd: dict[float, float] = {}
    rows: list[dict[str, Any]] = []
    candidate_map = {candidate.variant: candidate for candidate in candidates}
    base_stage079 = candidate_map[BASELINE_VARIANT].equity
    base_stage103 = candidate_map[STAGE103_VARIANT].equity
    daily079 = stage_daily[BASELINE_VARIANT]
    daily103 = stage_daily[STAGE103_VARIANT]
    cum_slip079 = daily079["combo_slippage"].cumsum()
    cum_slip103 = daily103["combo_slippage"].cumsum()

    for multiplier in (1.0, 2.0, 3.0, 5.0):
        stressed079 = base_stage079 - (multiplier - 1.0) * cum_slip079.reindex(base_stage079.index).ffill().fillna(0.0)
        stressed103 = base_stage103 - (multiplier - 1.0) * cum_slip103.reindex(base_stage103.index).ffill().fillna(0.0)
        baseline_dd = s387._max_drawdown(s387._nav(stressed079))
        stage103_dd = s387._max_drawdown(s387._nav(stressed103))
        baseline_stress_dd[multiplier] = baseline_dd
        for candidate in candidates:
            if candidate.variant == BASELINE_VARIANT:
                stressed = stressed079
            else:
                stressed = candidate.equity - (multiplier - 1.0) * cum_slip103.reindex(candidate.equity.index).ffill().fillna(0.0)
            nav = s387._nav(stressed)
            max_dd = s387._max_drawdown(nav)
            rows.append(
                {
                    "variant": candidate.variant,
                    "label": candidate.label,
                    "slippage_multiplier": multiplier,
                    "total_return_pct": float((nav.iloc[-1] - 1.0) * 100.0),
                    "max_dd_pct": max_dd,
                    "baseline_stage079_max_dd_pct": baseline_dd,
                    "stage103_max_dd_pct": stage103_dd,
                    "not_worse_than_stage079_stress": int(max_dd >= baseline_dd - 1e-9),
                    "not_worse_than_stage103_stress": int(max_dd >= stage103_dd - 1e-9),
                }
            )
    return pd.DataFrame(rows)


def _summary_with_meta(candidates: list[s387.Candidate]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for candidate in candidates:
        row = s387._stats(candidate)
        row["stock_capital"] = float(candidate.equity.attrs.get("stock_capital", 0.0))
        row["cash_left"] = float(candidate.equity.attrs.get("cash_left", STAGE079_CASH))
        row["cashslot_replaces_liquid_buffer"] = int(row["stock_capital"] > 0)
        rows.append(row)
    return pd.DataFrame(rows)


def _objective_improved_counts(horizon: pd.DataFrame) -> pd.DataFrame:
    larger_is_better = {"return_p05_pct", "return_median_pct", "positive_return_rate", "max_dd_worst_pct"}
    smaller_is_better = {
        "annualized_below_5pct_rate",
        "dd20_breach_rate",
        "ulcer_p95_pct",
        "longest_underwater_p95_days",
    }
    baseline = horizon[horizon["variant"].eq(BASELINE_VARIANT)].set_index("horizon_days")
    rows: list[dict[str, Any]] = []
    for _, row in horizon.iterrows():
        horizon_days = int(row["horizon_days"])
        base = baseline.loc[horizon_days]
        improved = 0
        for metric in larger_is_better:
            improved += int(_safe_float(row[metric]) > _safe_float(base[metric]))
        for metric in smaller_is_better:
            improved += int(_safe_float(row[metric]) < _safe_float(base[metric]))
        rows.append(
            {
                "variant": row["variant"],
                "label": row["label"],
                "horizon_days": horizon_days,
                "objective_improved_8_count": improved,
            }
        )
    return pd.DataFrame(rows)


def _gate(summary: pd.DataFrame, score: pd.DataFrame, horizon: pd.DataFrame, cost: pd.DataFrame) -> pd.DataFrame:
    baseline = summary[summary["variant"].eq(BASELINE_VARIANT)].iloc[0]
    stage103 = summary[summary["variant"].eq(STAGE103_VARIANT)].iloc[0]
    score_one = score.drop_duplicates(["variant", "label"])[
        ["variant", "label", "score_90d", "score_180d", "short_holding_score"]
    ]
    improved = _objective_improved_counts(horizon).pivot(
        index=["variant", "label"], columns="horizon_days", values="objective_improved_8_count"
    ).reset_index()
    improved.columns = ["variant", "label", "objective_improved_8_count_90d", "objective_improved_8_count_180d"]
    rows: list[dict[str, Any]] = []
    for _, row in summary.iterrows():
        variant = row["variant"]
        c = cost[cost["variant"].eq(variant)]
        checks_stage079 = {
            "total_return_not_lower_than_stage079": _safe_float(row["total_return_pct"]) >= _safe_float(
                baseline["total_return_pct"]
            )
            - 1e-4,
            "max_dd_not_worse_than_stage079": _safe_float(row["max_dd_pct"]) >= _safe_float(baseline["max_dd_pct"]) - 1e-4,
            "max_dd_below_30": _safe_float(row["max_dd_pct"]) >= -30.0,
            "sharpe_not_lower_than_stage079": _safe_float(row["sharpe"]) >= _safe_float(baseline["sharpe"]) - 1e-4,
            "ulcer_not_higher_than_stage079": _safe_float(row["ulcer_pct"]) <= _safe_float(baseline["ulcer_pct"]) + 1e-4,
            "rolling252_dd30_zero": _safe_float(row["rolling252_dd30_breach_rate"]) == 0.0,
            "rolling504_dd30_zero": _safe_float(row["rolling504_dd30_breach_rate"]) == 0.0,
            "annual_dd30_pass_100": _safe_float(row["annual_cold_start_dd30_pass_rate"]) == 1.0,
            "quarter_dd30_pass_100": _safe_float(row["quarter_cold_start_dd30_pass_rate"]) == 1.0,
            "capital_not_increased": _safe_float(row["capital_used"]) <= ACCOUNT_CAPITAL,
            "cost_stress_not_worse_than_stage079": bool(c["not_worse_than_stage079_stress"].eq(1).all()) if not c.empty else False,
            "eligible_not_diagnostic": bool(int(row["eligible_for_promotion"]) == 1),
        }
        checks_stage103 = {
            "total_return_not_lower_than_stage103": _safe_float(row["total_return_pct"]) >= _safe_float(
                stage103["total_return_pct"]
            )
            - 1e-4,
            "max_dd_not_worse_than_stage103": _safe_float(row["max_dd_pct"]) >= _safe_float(stage103["max_dd_pct"]) - 1e-4,
            "sharpe_not_lower_than_stage103": _safe_float(row["sharpe"]) >= _safe_float(stage103["sharpe"]) - 1e-4,
            "ulcer_not_higher_than_stage103": _safe_float(row["ulcer_pct"]) <= _safe_float(stage103["ulcer_pct"]) + 1e-4,
            "cost_stress_not_worse_than_stage103": bool(c["not_worse_than_stage103_stress"].eq(1).all())
            if not c.empty
            else False,
        }
        rows.append(
            {
                "variant": variant,
                "label": row["label"],
                "stock_capital": row.get("stock_capital", 0.0),
                "cash_left": row.get("cash_left", STAGE079_CASH),
                "cashslot_replaces_liquid_buffer": row.get("cashslot_replaces_liquid_buffer", 0),
                **{key: int(value) for key, value in checks_stage079.items()},
                **{key: int(value) for key, value in checks_stage103.items()},
                "metric_hard_pass_stage079": int(all(checks_stage079.values())),
                "metric_incremental_pass_stage103": int(all(checks_stage103.values())),
                "failed_stage079_metric_checks": ",".join([key for key, value in checks_stage079.items() if not value]),
                "failed_stage103_incremental_checks": ",".join([key for key, value in checks_stage103.items() if not value]),
            }
        )
    result = pd.DataFrame(rows).merge(score_one, on=["variant", "label"], how="left").merge(
        improved, on=["variant", "label"], how="left"
    )
    result["score90_improve_ge10pct_vs_stage079"] = (result["score_90d"] >= 110.0).astype(int)
    result["score180_improve_ge10pct_vs_stage079"] = (result["score_180d"] >= 110.0).astype(int)
    result["objective_improved_5of8_each_vs_stage079"] = (
        (result["objective_improved_8_count_90d"] >= 5) & (result["objective_improved_8_count_180d"] >= 5)
    ).astype(int)
    result["target_pass_3m6m_vs_stage079"] = (
        result["score90_improve_ge10pct_vs_stage079"].eq(1)
        & result["score180_improve_ge10pct_vs_stage079"].eq(1)
        & result["objective_improved_5of8_each_vs_stage079"].eq(1)
    ).astype(int)
    result["research_promotion_pass"] = (
        result["metric_hard_pass_stage079"].eq(1) & result["target_pass_3m6m_vs_stage079"].eq(1)
    ).astype(int)
    result["stage103_plus_candidate_pass"] = (
        result["research_promotion_pass"].eq(1) & result["metric_incremental_pass_stage103"].eq(1)
    ).astype(int)
    result["absolute_liquid_buffer_warning"] = (result["cashslot_replaces_liquid_buffer"].eq(1)).astype(int)
    return result.sort_values(["stage103_plus_candidate_pass", "research_promotion_pass", "short_holding_score"], ascending=False)


def _build_daily_output(candidates: list[s387.Candidate]) -> pd.DataFrame:
    rows = []
    for candidate in candidates:
        equity = candidate.equity.astype(float)
        nav = equity / ACCOUNT_CAPITAL
        rows.append(
            pd.DataFrame(
                {
                    "date": equity.index,
                    "variant": candidate.variant,
                    "label": candidate.label,
                    "equity": equity.values,
                    "nav": nav.values,
                    "drawdown_pct": ((nav / nav.cummax() - 1.0) * 100.0).values,
                }
            )
        )
    return pd.concat(rows, ignore_index=True)


def _marginal_diagnostics(summary: pd.DataFrame, score: pd.DataFrame, daily: pd.DataFrame, calendar: pd.DatetimeIndex) -> pd.DataFrame:
    summary_by_variant = summary.set_index("variant")
    score_by_variant = score.drop_duplicates("variant").set_index("variant")
    rows: list[dict[str, Any]] = []

    def add_delta(challenger: str, reference: str, comparison: str) -> None:
        rows.append(
            {
                "comparison": comparison,
                "challenger": challenger,
                "reference": reference,
                "total_return_delta_pct": _safe_float(
                    summary_by_variant.loc[challenger, "total_return_pct"] - summary_by_variant.loc[reference, "total_return_pct"]
                ),
                "max_dd_delta_pp": _safe_float(summary_by_variant.loc[challenger, "max_dd_pct"] - summary_by_variant.loc[reference, "max_dd_pct"]),
                "sharpe_delta": _safe_float(summary_by_variant.loc[challenger, "sharpe"] - summary_by_variant.loc[reference, "sharpe"]),
                "ulcer_delta_pp": _safe_float(summary_by_variant.loc[challenger, "ulcer_pct"] - summary_by_variant.loc[reference, "ulcer_pct"]),
                "score90_delta": _safe_float(score_by_variant.loc[challenger, "score_90d"] - score_by_variant.loc[reference, "score_90d"]),
                "score180_delta": _safe_float(score_by_variant.loc[challenger, "score_180d"] - score_by_variant.loc[reference, "score_180d"]),
            }
        )

    best_real = "stage103_stock_lot_50000_cash_65000_yield2"
    cash_yield = "stage103_cash_yield_2pct"
    add_delta(cash_yield, STAGE103_VARIANT, "cash_yield_vs_stage103")
    add_delta(best_real, STAGE103_VARIANT, "best_stock_vs_stage103")
    add_delta(best_real, cash_yield, "best_stock_vs_cash_yield")

    stock_equity = _load_stock_lot_equity(50_000.0, calendar)
    stock_nav = stock_equity / 50_000.0
    stage103_frame = daily[daily["variant"].eq(STAGE103_VARIANT)].copy()
    stage103_frame["date"] = pd.to_datetime(stage103_frame["date"])
    stage103_nav = stage103_frame.sort_values("date").set_index("date")["nav"].reindex(calendar).ffill()
    stock_ret = stock_nav.pct_change().dropna()
    stage103_ret = stage103_nav.pct_change().dropna()
    rows.append(
        {
            "comparison": "stock_100k_independent",
            "challenger": "stock_lot_50000",
            "reference": STAGE103_VARIANT,
            "stock_total_return_pct": float((stock_nav.iloc[-1] - 1.0) * 100.0),
            "stock_max_dd_pct": s387._max_drawdown(stock_nav),
            "stock_ulcer_pct": s387._ulcer(stock_nav),
            "stock_daily_corr_with_stage103": float(stock_ret.corr(stage103_ret)),
            "stock_worst_90d_return_pct": float((stock_nav / stock_nav.shift(90) - 1.0).dropna().min() * 100.0),
            "stock_worst_180d_return_pct": float((stock_nav / stock_nav.shift(180) - 1.0).dropna().min() * 100.0),
        }
    )
    return pd.DataFrame(rows)


def _plot(daily: pd.DataFrame, score: pd.DataFrame, gate: pd.DataFrame) -> None:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception as exc:  # pragma: no cover
        print(f"[stage411] skip chart: {exc}", flush=True)
        return
    short_labels = {
        BASELINE_VARIANT: "Stage079",
        STAGE103_VARIANT: "Stage103",
        "stage103_cash_yield_2pct": "Cash2%",
        "stage103_stock_lot_25000_cash_90000": "Stock25k",
        "stage103_stock_lot_25000_cash_90000_yield2": "Stock25k+Y",
        "stage103_stock_lot_50000_cash_65000": "Stock50k",
        "stage103_stock_lot_50000_cash_65000_yield2": "Stock50k+Y",
        "stage103_stock_lot_100000_cash_15000": "Stock100k",
        "stage103_stock_lot_100000_cash_15000_yield2": "Stock100k+Y",
        "stage103_stock_scaled_115k_paper": "Scaled115k",
    }
    variants = gate["variant"].head(8).tolist()
    fig, axes = plt.subplots(2, 2, figsize=(15, 10))
    for variant in [BASELINE_VARIANT, STAGE103_VARIANT, "stage103_stock_lot_50000_cash_65000_yield2", "stage103_stock_scaled_115k_paper"]:
        frame = daily[daily["variant"].eq(variant)].sort_values("date")
        if frame.empty:
            continue
        axes[0, 0].plot(pd.to_datetime(frame["date"]), frame["nav"], linewidth=1.0, label=short_labels.get(variant, variant))
        axes[1, 0].plot(pd.to_datetime(frame["date"]), frame["drawdown_pct"], linewidth=0.9, label=short_labels.get(variant, variant))
    axes[0, 0].set_title("NAV")
    axes[0, 0].legend(fontsize=7)
    axes[1, 0].set_title("Drawdown")
    axes[1, 0].axhline(-30.0, color="red", linestyle="--", linewidth=1.0)
    axes[1, 0].legend(fontsize=7)

    one = score.drop_duplicates(["variant"]).set_index("variant").reindex(variants)
    x = np.arange(len(variants))
    width = 0.35
    axes[0, 1].bar(x - width / 2, one["score_90d"].to_numpy(dtype=float), width, label="90d")
    axes[0, 1].bar(x + width / 2, one["score_180d"].to_numpy(dtype=float), width, label="180d")
    axes[0, 1].axhline(110, color="red", linestyle="--", linewidth=1.0)
    axes[0, 1].set_xticks(x)
    axes[0, 1].set_xticklabels([short_labels.get(v, v) for v in variants], rotation=30, ha="right", fontsize=8)
    axes[0, 1].set_title("Short holding scores")
    axes[0, 1].legend(fontsize=8)

    g = gate.set_index("variant").reindex(variants)
    axes[1, 1].bar(x, g["cash_left"].to_numpy(dtype=float) / 10_000.0, color="#9ecae1")
    axes[1, 1].set_xticks(x)
    axes[1, 1].set_xticklabels([short_labels.get(v, v) for v in variants], rotation=30, ha="right", fontsize=8)
    axes[1, 1].set_title("Remaining liquid cash slot")
    axes[1, 1].set_ylabel("10k CNY")
    fig.suptitle("Stage111 Stage103 stock cash-slot audit", fontsize=14)
    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=160)
    plt.close(fig)


def _write_report(
    summary: pd.DataFrame,
    horizon: pd.DataFrame,
    score: pd.DataFrame,
    cost: pd.DataFrame,
    gate: pd.DataFrame,
    diagnostic: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    report = [
        "# Stage111 Stage103股票现金槽位审计",
        "",
        f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "- 阶段性质：跨资产现金槽位审计；不增加账户资金，不修改C3或Stage103交易规则。",
        "- 关键边界：股票槽位替换的是11.5万现金缓冲的一部分，因此即使指标通过，也要标记期货账户流动性/保证金可用性风险。",
        f"- 图表：`{CHART_PATH}`",
        "",
        "## 决策",
        "",
        "```json",
        json.dumps(_json_safe(decision), ensure_ascii=False, indent=2),
        "```",
        "",
        "## 全周期核心指标",
        "",
        _md_table(
            summary[
                [
                    "variant",
                    "total_return_pct",
                    "max_dd_pct",
                    "sharpe",
                    "ulcer_pct",
                    "rolling252_dd30_breach_rate",
                    "rolling504_dd30_breach_rate",
                    "stock_capital",
                    "cash_left",
                ]
            ]
        ),
        "",
        "## 3个月/6个月体验",
        "",
        _md_table(
            horizon[
                [
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
            ]
        ),
        "",
        "## 晋级门禁",
        "",
        _md_table(
            gate[
                [
                    "variant",
                    "metric_hard_pass_stage079",
                    "metric_incremental_pass_stage103",
                    "target_pass_3m6m_vs_stage079",
                    "research_promotion_pass",
                    "stage103_plus_candidate_pass",
                    "score_90d",
                    "score_180d",
                    "objective_improved_8_count_90d",
                    "objective_improved_8_count_180d",
                    "cash_left",
                    "absolute_liquid_buffer_warning",
                    "failed_stage079_metric_checks",
                    "failed_stage103_incremental_checks",
                ]
            ]
        ),
        "",
        "## 边际归因",
        "",
        _md_table(diagnostic),
        "",
        "## 成本压力",
        "",
        _md_table(
            cost[
                [
                    "variant",
                    "slippage_multiplier",
                    "max_dd_pct",
                    "baseline_stage079_max_dd_pct",
                    "stage103_max_dd_pct",
                    "not_worse_than_stage079_stress",
                    "not_worse_than_stage103_stress",
                ]
            ]
        ),
        "",
        "## 反过拟合说明",
        "",
        "- 本阶段没有调股票策略参数、个股、资金小数或窗口，只复用Stage370真实整手股票路径和Stage075诊断净值。",
        "- 若真实整手股票槽位提升不足，则不能继续围绕2.5万/5万/10万附近小数救援。",
        "- 若诊断线性缩放好于真实整手，也不能直接晋级，因为它忽略小资金整手约束。",
    ]
    REPORT_PATH.write_text("\n".join(report) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    stage_daily_raw = _load_stage403_daily()
    min_date = stage_daily_raw["date"].min()
    max_date = stage_daily_raw["date"].max()
    calendar = pd.date_range(min_date, max_date, freq="D")
    daily079 = _variant_daily(stage_daily_raw, BASELINE_VARIANT, calendar)
    daily103 = _variant_daily(stage_daily_raw, STAGE103_VARIANT, calendar)
    stage079 = daily079["equity"].astype(float)
    stage079.index = calendar
    stage103 = daily103["equity"].astype(float)
    stage103.index = calendar
    candidates = _build_candidates(stage079, stage103, calendar)

    summary = _summary_with_meta(candidates)
    horizon = pd.DataFrame([s387._horizon_metrics(candidate, days) for candidate in candidates for days in (90, 180)])
    score = s387._score_horizons(horizon)
    cost = _cost_stress(candidates, {BASELINE_VARIANT: daily079, STAGE103_VARIANT: daily103})
    gate = _gate(summary, score, horizon, cost)
    daily = _build_daily_output(candidates)
    diagnostic = _marginal_diagnostics(summary, score, daily, calendar)

    ready = gate[gate["stage103_plus_candidate_pass"].eq(1) & ~gate["variant"].isin([BASELINE_VARIANT, STAGE103_VARIANT])]
    research_ready = gate[gate["research_promotion_pass"].eq(1) & ~gate["variant"].isin([BASELINE_VARIANT, STAGE103_VARIANT])]
    best = gate[~gate["variant"].isin([BASELINE_VARIANT])].iloc[0]
    decision = {
        "stage": "Stage111",
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "decision": "stage103_plus_candidate" if len(ready) else ("research_candidate_only" if len(research_ready) else "no_new_promotion"),
        "stage103_plus_ready_variants": ready["variant"].tolist(),
        "research_ready_variants": research_ready["variant"].tolist(),
        "best_non_baseline_variant": str(best["variant"]),
        "best_non_baseline_short_holding_score": _safe_float(best["short_holding_score"]),
        "liquidity_boundary": "股票槽位替换11.5万现金缓冲的一部分；即使研究门禁通过，也不是绝对保证金部署版本。",
        "chart": str(CHART_PATH),
    }

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    horizon.to_csv(HORIZON_PATH, index=False, encoding="utf-8-sig")
    score.to_csv(SCORE_PATH, index=False, encoding="utf-8-sig")
    cost.to_csv(COST_PATH, index=False, encoding="utf-8-sig")
    gate.to_csv(GATE_PATH, index=False, encoding="utf-8-sig")
    daily.to_csv(DAILY_PATH, index=False, encoding="utf-8-sig")
    diagnostic.to_csv(DIAGNOSTIC_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _plot(daily, score, gate)
    _write_report(summary, horizon, score, cost, gate, diagnostic, decision)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print(f"report={REPORT_PATH}")


if __name__ == "__main__":
    main()
