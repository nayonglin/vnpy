from __future__ import annotations

import json
import math
import sys
from dataclasses import dataclass
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

sys.path.insert(0, str(PROJECT_DIR.resolve()))
import analyze_qmt_roll_stage387_stage079_short_holding_candidates as s087  # noqa: E402
import analyze_qmt_roll_stage402_stage079_xsmom_volmanaged_true_integer as s402  # noqa: E402


MODEL_TAG = "stage420_stage079_activation_ramp_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage420_stage079_activation_ramp_audit"
LINE_ID = "futures_trend_drawdown30_preserve_return"

ACCOUNT_CAPITAL = s087.ACCOUNT_CAPITAL
BASELINE_VARIANT = s087.BASELINE_VARIANT
TARGET_DD_PCT = s087.TARGET_DD_PCT

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
HORIZON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_startup_horizon_{MODEL_TAG}.csv"
SCORE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_score_{MODEL_TAG}.csv"
COST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cost_stress_{MODEL_TAG}.csv"
COLD_START_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cold_start_{MODEL_TAG}.csv"
GATE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gate_{MODEL_TAG}.csv"
DAILY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"


@dataclass(frozen=True)
class RampSpec:
    variant: str
    label: str
    kind: str
    initial_exposure: float
    full_exposure_days: int
    note: str


RAMP_SPECS: tuple[RampSpec, ...] = (
    RampSpec(
        BASELINE_VARIANT,
        "A Stage079 baseline",
        "none",
        1.0,
        0,
        "50万C3下单+11.5万现金；不做启动分批。",
    ),
    RampSpec(
        "activation_tranche_3m",
        "C1 3-month 1/3 tranche activation",
        "tranche",
        1.0 / 3.0,
        90,
        "第0-30天1/3风险，第31-60天2/3风险，60天后满风险。",
    ),
    RampSpec(
        "activation_tranche_6m",
        "C2 6-month 1/3 tranche activation",
        "tranche",
        1.0 / 3.0,
        180,
        "第0-60天1/3风险，第61-120天2/3风险，120天后满风险。",
    ),
    RampSpec(
        "activation_linear_3m_33",
        "C3 3-month linear 33% to 100%",
        "linear",
        1.0 / 3.0,
        90,
        "启动风险从1/3线性爬坡到100%，90天后满风险。",
    ),
    RampSpec(
        "activation_linear_6m_33",
        "C4 6-month linear 33% to 100%",
        "linear",
        1.0 / 3.0,
        180,
        "启动风险从1/3线性爬坡到100%，180天后满风险。",
    ),
    RampSpec(
        "activation_linear_3m_67",
        "C5 3-month linear 67% to 100%",
        "linear",
        2.0 / 3.0,
        90,
        "温和启动：风险从2/3线性爬坡到100%，90天后满风险。",
    ),
    RampSpec(
        "activation_risk80_3m",
        "C6 3-month linear 80% to 100%",
        "linear",
        0.80,
        90,
        "很温和启动：风险从80%线性爬坡到100%，90天后满风险。",
    ),
)


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


def _schedule(age_days: np.ndarray, spec: RampSpec) -> np.ndarray:
    age = np.asarray(age_days, dtype=float)
    if spec.kind == "none":
        return np.ones(len(age), dtype=float)
    if spec.kind == "tranche":
        first = spec.full_exposure_days / 3.0
        second = spec.full_exposure_days * 2.0 / 3.0
        return np.where(age < first, 1.0 / 3.0, np.where(age < second, 2.0 / 3.0, 1.0))
    if spec.kind == "linear":
        if spec.full_exposure_days <= 0:
            return np.ones(len(age), dtype=float)
        ramp = spec.initial_exposure + (1.0 - spec.initial_exposure) * age / float(spec.full_exposure_days)
        return np.minimum(1.0, np.maximum(spec.initial_exposure, ramp))
    raise ValueError(f"unsupported schedule kind: {spec.kind}")


def _load_stage079_base() -> tuple[pd.Series, pd.Series, pd.Series]:
    combo = s402._load_combo_daily()
    full = combo[combo["window_name"].eq("start_2020")].sort_values("date").drop_duplicates("date", keep="last")
    full["date"] = pd.to_datetime(full["date"], errors="coerce").dt.normalize()
    equity = pd.Series(
        s402.FUTURES_CAPITAL + full["c3_net_pnl"].astype(float).cumsum().to_numpy(dtype=float) + s402.STAGE079_CASH,
        index=full["date"],
        name="equity",
    )
    equity = s402._calendarize(equity)
    slippage_raw = pd.Series(full["c3_slippage"].astype(float).to_numpy(dtype=float), index=full["date"])
    slippage = slippage_raw.reindex(equity.index).fillna(0.0)
    returns = equity.pct_change()
    returns.iloc[0] = equity.iloc[0] / ACCOUNT_CAPITAL - 1.0
    returns = returns.fillna(0.0)
    return equity, returns, slippage


def _simulate_curve(
    returns: pd.Series,
    slippage: pd.Series,
    spec: RampSpec,
    start_date: pd.Timestamp | None = None,
    end_date: pd.Timestamp | None = None,
    slippage_multiplier: float = 1.0,
    include_start_return: bool = True,
) -> pd.Series:
    if start_date is None:
        start_date = pd.Timestamp(returns.index.min())
    if end_date is None:
        end_date = pd.Timestamp(returns.index.max())
    r = returns.loc[start_date:end_date].copy()
    slip = slippage.loc[start_date:end_date].reindex(r.index).fillna(0.0)
    if r.empty:
        return pd.Series(dtype=float)
    age_days = (r.index - pd.Timestamp(start_date)).days.to_numpy(dtype=float)
    exposure = _schedule(age_days, spec)
    values: list[float] = []
    equity = ACCOUNT_CAPITAL
    for idx, (date, daily_return) in enumerate(r.items()):
        if idx == 0 and not include_start_return:
            values.append(equity)
            continue
        extra_slippage = max(slippage_multiplier - 1.0, 0.0) * float(slip.loc[date]) * float(exposure[idx])
        equity = equity * (1.0 + float(daily_return) * float(exposure[idx])) - extra_slippage
        values.append(equity)
    return pd.Series(values, index=r.index, name=spec.variant)


def _longest_underwater_days(dates: np.ndarray, nav: np.ndarray) -> int:
    return s087._longest_underwater_days(dates.astype("datetime64[D]"), nav)


def _startup_horizon_metrics(
    returns: pd.Series,
    slippage: pd.Series,
    spec: RampSpec,
    horizon_days: int,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    last_start = returns.index.max() - pd.Timedelta(days=horizon_days)
    for start_date in returns.index:
        if start_date > last_start:
            break
        end_date = start_date + pd.Timedelta(days=horizon_days)
        if end_date not in returns.index:
            continue
        equity = _simulate_curve(
            returns,
            slippage,
            spec,
            start_date=pd.Timestamp(start_date),
            end_date=pd.Timestamp(end_date),
            include_start_return=False,
        )
        if len(equity) < 2:
            continue
        nav = equity.to_numpy(dtype=float) / float(equity.iloc[0])
        drawdown = nav / np.maximum.accumulate(nav) - 1.0
        rows.append(
            {
                "return_pct": float((nav[-1] - 1.0) * 100.0),
                "annualized_return_pct": float((np.power(max(nav[-1], 1e-12), 365.0 / horizon_days) - 1.0) * 100.0),
                "max_dd_pct": float(drawdown.min() * 100.0),
                "ulcer_pct": float(np.sqrt(np.mean(np.square(np.minimum(drawdown * 100.0, 0.0))))),
                "longest_underwater_days": _longest_underwater_days(equity.index.to_numpy(), nav),
            }
        )
    frame = pd.DataFrame(rows)
    target = s087.HORIZON_TARGETS[horizon_days]
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
            "variant": spec.variant,
            "label": spec.label,
            "horizon_days": horizon_days,
            "horizon_label": target["label"],
            "count": int(len(frame)),
        }
    )
    return result


def _cold_start(returns: pd.Series, slippage: pd.Series, spec: RampSpec, freq: str) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    starts = pd.date_range(returns.index.min(), returns.index.max(), freq=freq)
    for requested_start in starts:
        idx = returns.index[returns.index >= requested_start]
        if len(idx) < 252:
            continue
        start_date = pd.Timestamp(idx[0])
        equity = _simulate_curve(returns, slippage, spec, start_date=start_date, include_start_return=False)
        if len(equity) < 252:
            continue
        nav = equity / equity.iloc[0]
        max_dd = s087._max_drawdown(nav)
        rows.append(
            {
                "variant": spec.variant,
                "label": spec.label,
                "freq": freq,
                "start_date": str(start_date.date()),
                "end_equity": float(equity.iloc[-1]),
                "total_return_pct": float((nav.iloc[-1] - 1.0) * 100.0),
                "max_dd_pct": max_dd,
                "dd30_pass": int(max_dd >= TARGET_DD_PCT),
            }
        )
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
        hit = 0
        improved_metrics: list[str] = []
        hit_metrics: list[str] = []
        target = s087.HORIZON_TARGETS[horizon_days]
        for metric in sorted(larger_is_better):
            value = _safe_float(row[metric])
            if value > _safe_float(base[metric]):
                improved += 1
                improved_metrics.append(metric)
            if value >= _safe_float(target[metric]):
                hit += 1
                hit_metrics.append(metric)
        for metric in sorted(smaller_is_better):
            value = _safe_float(row[metric])
            if value < _safe_float(base[metric]):
                improved += 1
                improved_metrics.append(metric)
            if value <= _safe_float(target[metric]):
                hit += 1
                hit_metrics.append(metric)
        rows.append(
            {
                "variant": row["variant"],
                "label": row["label"],
                "horizon_days": horizon_days,
                "objective_improved_8_count": improved,
                "objective_improved_8_metrics": ",".join(improved_metrics),
                "objective_target_hit_8_count": hit,
                "objective_target_hit_8_metrics": ",".join(hit_metrics),
            }
        )
    return pd.DataFrame(rows)


def _core_return_quality(horizon: pd.DataFrame) -> pd.DataFrame:
    baseline = horizon[horizon["variant"].eq(BASELINE_VARIANT)].set_index("horizon_days")
    rows: list[dict[str, Any]] = []
    for _, row in horizon.iterrows():
        horizon_days = int(row["horizon_days"])
        base = baseline.loc[horizon_days]
        rows.append(
            {
                "variant": row["variant"],
                "label": row["label"],
                "horizon_days": horizon_days,
                "median_not_lower": int(_safe_float(row["return_median_pct"]) >= _safe_float(base["return_median_pct"]) - 1e-9),
                "positive_rate_not_lower": int(
                    _safe_float(row["positive_return_rate"]) >= _safe_float(base["positive_return_rate"]) - 1e-9
                ),
                "low_growth_rate_not_higher": int(
                    _safe_float(row["annualized_below_5pct_rate"])
                    <= _safe_float(base["annualized_below_5pct_rate"]) + 1e-9
                ),
            }
        )
    return pd.DataFrame(rows)


def _cost_stress(returns: pd.Series, slippage: pd.Series) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    baseline_dd: dict[float, float] = {}
    base_equity = ACCOUNT_CAPITAL * (1.0 + returns).cumprod()
    base_pnl = base_equity.diff()
    base_pnl.iloc[0] = base_equity.iloc[0] - ACCOUNT_CAPITAL
    age_days = (base_pnl.index - base_pnl.index[0]).days.to_numpy(dtype=float)
    for multiplier in (1.0, 2.0, 3.0, 5.0):
        for spec in RAMP_SPECS:
            exposure = _schedule(age_days, spec)
            pnl = exposure * (base_pnl.to_numpy(dtype=float) - max(multiplier - 1.0, 0.0) * slippage.to_numpy(dtype=float))
            equity = pd.Series(ACCOUNT_CAPITAL + np.cumsum(pnl), index=base_pnl.index, name=spec.variant)
            candidate = s087.Candidate(
                spec.variant,
                spec.label,
                equity,
                ACCOUNT_CAPITAL,
                "activation_ramp",
                spec.variant == BASELINE_VARIANT,
                spec.note,
            )
            stats = s087._stats(candidate)
            if spec.variant == BASELINE_VARIANT:
                baseline_dd[multiplier] = float(stats["max_dd_pct"])
            rows.append(
                {
                    "variant": spec.variant,
                    "label": spec.label,
                    "slippage_multiplier": multiplier,
                    "total_return_pct": float(stats["total_return_pct"]),
                    "max_dd_pct": float(stats["max_dd_pct"]),
                }
            )
    result = pd.DataFrame(rows)
    result["stage079_max_dd_pct"] = result["slippage_multiplier"].map(baseline_dd)
    result["not_worse_than_stage079_stress"] = (
        result["max_dd_pct"] >= result["stage079_max_dd_pct"] - 1e-9
    ).astype(int)
    return result


def _build_gate(summary: pd.DataFrame, horizon: pd.DataFrame, score: pd.DataFrame, cost: pd.DataFrame, cold: pd.DataFrame) -> pd.DataFrame:
    baseline = summary[summary["variant"].eq(BASELINE_VARIANT)].iloc[0]
    objective = _objective_improved_counts(horizon)
    objective_p = objective.pivot(index=["variant", "label"], columns="horizon_days", values="objective_improved_8_count").reset_index()
    objective_p.columns = ["variant", "label", "objective_improved_8_count_90d", "objective_improved_8_count_180d"]
    target_p = objective.pivot(index=["variant", "label"], columns="horizon_days", values="objective_target_hit_8_count").reset_index()
    target_p.columns = ["variant", "label", "objective_target_hit_8_count_90d", "objective_target_hit_8_count_180d"]
    score_one = score.drop_duplicates(["variant", "label"])[
        ["variant", "label", "score_90d", "score_180d", "short_holding_score"]
    ]
    core = _core_return_quality(horizon)
    core_p = core.pivot(index=["variant", "label"], columns="horizon_days").reset_index()
    core_p.columns = [
        "variant",
        "label",
        "median_not_lower_90d",
        "median_not_lower_180d",
        "positive_rate_not_lower_90d",
        "positive_rate_not_lower_180d",
        "low_growth_rate_not_higher_90d",
        "low_growth_rate_not_higher_180d",
    ]
    cold_pass = cold.groupby("variant")["dd30_pass"].min().to_dict()
    rows: list[dict[str, Any]] = []
    for _, row in summary.iterrows():
        c = cost[cost["variant"].eq(row["variant"])]
        checks = {
            "total_return_not_lower_than_stage079": _safe_float(row["total_return_pct"]) >= _safe_float(
                baseline["total_return_pct"]
            )
            - 1e-4,
            "max_dd_not_worse_than_stage079": _safe_float(row["max_dd_pct"]) >= _safe_float(baseline["max_dd_pct"]) - 1e-4,
            "max_dd_below_30": _safe_float(row["max_dd_pct"]) >= TARGET_DD_PCT,
            "sharpe_not_lower_than_stage079": _safe_float(row["sharpe"]) >= _safe_float(baseline["sharpe"]) - 1e-4,
            "ulcer_not_higher_than_stage079": _safe_float(row["ulcer_pct"]) <= _safe_float(baseline["ulcer_pct"]) + 1e-4,
            "rolling252_dd30_zero": _safe_float(row["rolling252_dd30_breach_rate"]) == 0.0,
            "rolling504_dd30_zero": _safe_float(row["rolling504_dd30_breach_rate"]) == 0.0,
            "annual_quarter_cold_start_dd30_pass": bool(cold_pass.get(str(row["variant"]), 0) == 1),
            "capital_not_increased": _safe_float(row["capital_used"]) <= ACCOUNT_CAPITAL,
            "cost_stress_not_worse_than_stage079": bool(c["not_worse_than_stage079_stress"].eq(1).all()) if not c.empty else False,
        }
        rows.append(
            {
                "variant": row["variant"],
                "label": row["label"],
                **{key: int(value) for key, value in checks.items()},
                "metric_hard_pass_stage079": int(all(checks.values())),
                "failed_stage079_metric_checks": ",".join([key for key, value in checks.items() if not value]),
            }
        )
    result = (
        pd.DataFrame(rows)
        .merge(score_one, on=["variant", "label"], how="left")
        .merge(objective_p, on=["variant", "label"], how="left")
        .merge(target_p, on=["variant", "label"], how="left")
        .merge(core_p, on=["variant", "label"], how="left")
    )
    result["score90_improve_ge10pct_vs_stage079"] = (result["score_90d"] >= 110.0).astype(int)
    result["score180_improve_ge10pct_vs_stage079"] = (result["score_180d"] >= 110.0).astype(int)
    result["objective_improved_5of8_each_vs_stage079"] = (
        (result["objective_improved_8_count_90d"] >= 5) & (result["objective_improved_8_count_180d"] >= 5)
    ).astype(int)
    core_cols = [
        "median_not_lower_90d",
        "median_not_lower_180d",
        "positive_rate_not_lower_90d",
        "positive_rate_not_lower_180d",
        "low_growth_rate_not_higher_90d",
        "low_growth_rate_not_higher_180d",
    ]
    result["short_return_quality_not_degraded"] = result[core_cols].eq(1).all(axis=1).astype(int)
    result["startup_target_pass"] = (
        result["score90_improve_ge10pct_vs_stage079"].eq(1)
        & result["score180_improve_ge10pct_vs_stage079"].eq(1)
        & result["objective_improved_5of8_each_vs_stage079"].eq(1)
        & result["short_return_quality_not_degraded"].eq(1)
    ).astype(int)
    result["promotion_pass"] = (
        result["metric_hard_pass_stage079"].eq(1) & result["startup_target_pass"].eq(1)
    ).astype(int)
    return result.sort_values(["promotion_pass", "startup_target_pass", "short_holding_score"], ascending=[False, False, False])


def _plot(summary: pd.DataFrame, horizon: pd.DataFrame, gate: pd.DataFrame, daily: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(15, 10))
    full = daily.copy()
    for variant, frame in full.groupby("variant", sort=False):
        frame = frame.sort_values("date")
        nav = frame["equity"].to_numpy(dtype=float) / ACCOUNT_CAPITAL
        dates = pd.to_datetime(frame["date"])
        axes[0, 0].plot(dates, nav, label=variant, linewidth=1.0)
        dd = nav / np.maximum.accumulate(nav) - 1.0
        axes[1, 0].plot(dates, dd * 100.0, label=variant, linewidth=0.9)
    axes[0, 0].set_title("Continuous 2020-start NAV")
    axes[0, 0].legend(fontsize=7)
    axes[1, 0].set_title("Continuous drawdown")
    axes[1, 0].axhline(-30.0, color="red", linestyle="--", linewidth=1.0)
    axes[1, 0].legend(fontsize=7)

    h90 = horizon[horizon["horizon_days"].eq(90)].set_index("variant")
    h180 = horizon[horizon["horizon_days"].eq(180)].set_index("variant")
    variants = [spec.variant for spec in RAMP_SPECS]
    x = np.arange(len(variants))
    width = 0.36
    axes[0, 1].bar(x - width / 2, h90.reindex(variants)["return_p05_pct"].to_numpy(dtype=float), width, label="90d p05")
    axes[0, 1].bar(x + width / 2, h180.reindex(variants)["return_p05_pct"].to_numpy(dtype=float), width, label="180d p05")
    axes[0, 1].axhline(0.0, color="#333333", linewidth=0.8)
    axes[0, 1].set_title("Reset-at-start left-tail return")
    axes[0, 1].set_xticks(x)
    axes[0, 1].set_xticklabels(variants, rotation=30, ha="right", fontsize=7)
    axes[0, 1].legend(fontsize=8)

    g = gate.set_index("variant").reindex(variants)
    axes[1, 1].bar(x - width / 2, g["score_90d"].to_numpy(dtype=float), width, label="90d score")
    axes[1, 1].bar(x + width / 2, g["score_180d"].to_numpy(dtype=float), width, label="180d score")
    axes[1, 1].axhline(110.0, color="red", linestyle="--", linewidth=1.0)
    axes[1, 1].set_title("Startup experience score")
    axes[1, 1].set_xticks(x)
    axes[1, 1].set_xticklabels(variants, rotation=30, ha="right", fontsize=7)
    axes[1, 1].legend(fontsize=8)
    fig.suptitle("Stage120 Stage079 fixed activation ramp audit", fontsize=14)
    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=160)
    plt.close(fig)


def _write_report(
    summary: pd.DataFrame,
    horizon: pd.DataFrame,
    score: pd.DataFrame,
    cost: pd.DataFrame,
    cold: pd.DataFrame,
    gate: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    report = [
        "# Stage120 Stage079固定分批启动/风险爬坡审计",
        "",
        f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "- 阶段性质：部署层 PnL 诊断；不改C3/Stage079交易信号、不加资金、不扫坏窗口阈值。",
        "- A/C：A=Stage079；C=同一Stage079收益路径的新账户固定分批启动。",
        "- 注意：本阶段是启动部署政策的日收益/路径诊断，不是逐笔真实引擎结论；若诊断不通过，则不进入真实引擎。",
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
                    "annual_cold_start_dd30_pass_rate",
                    "quarter_cold_start_dd30_pass_rate",
                ]
            ]
        ),
        "",
        "## 启动重置口径 3个月/6个月体验",
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
        "## 体验分与晋级闸门",
        "",
        _md_table(
            gate[
                [
                    "variant",
                    "metric_hard_pass_stage079",
                    "startup_target_pass",
                    "promotion_pass",
                    "score_90d",
                    "score_180d",
                    "short_holding_score",
                    "objective_improved_8_count_90d",
                    "objective_improved_8_count_180d",
                    "short_return_quality_not_degraded",
                    "failed_stage079_metric_checks",
                ]
            ]
        ),
        "",
        "## 成本压力",
        "",
        _md_table(cost),
        "",
        "## 年度/季度冷启动回撤",
        "",
        _md_table(cold.groupby(["variant", "freq"])["dd30_pass"].mean().reset_index(name="dd30_pass_rate")),
        "",
        "## 反过拟合说明",
        "",
        "- 本阶段只测试常见部署政策：3个月/6个月三段式入场、3个月/6个月线性爬坡、两个温和爬坡对照。",
        "- 没有根据2021/2022/2024坏窗口调日期、品种、资金小数或触发条件。",
        "- 如果候选只靠压低启动初期风险来改善回撤，但降低中位收益、正收益率或低增长概率，则不晋级。",
    ]
    REPORT_PATH.write_text("\n".join(report) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    base_equity, returns, slippage = _load_stage079_base()
    candidates: list[s087.Candidate] = []
    daily_parts: list[pd.DataFrame] = []
    for spec in RAMP_SPECS:
        if spec.variant == BASELINE_VARIANT:
            equity = base_equity.copy()
        else:
            equity = _simulate_curve(returns, slippage, spec, include_start_return=True)
        candidates.append(
            s087.Candidate(
                spec.variant,
                spec.label,
                equity,
                ACCOUNT_CAPITAL,
                "activation_ramp",
                spec.variant == BASELINE_VARIANT,
                spec.note,
            )
        )
        daily_parts.append(pd.DataFrame({"date": equity.index, "variant": spec.variant, "label": spec.label, "equity": equity.to_numpy(dtype=float)}))

    summary = pd.DataFrame([s087._stats(candidate) for candidate in candidates])
    horizon = pd.DataFrame(
        [_startup_horizon_metrics(returns, slippage, spec, days) for spec in RAMP_SPECS for days in (90, 180)]
    )
    score = s087._score_horizons(horizon)
    cost = _cost_stress(returns, slippage)
    cold = pd.concat(
        [_cold_start(returns, slippage, spec, freq) for spec in RAMP_SPECS for freq in ("YS", "QS")],
        ignore_index=True,
    )
    gate = _build_gate(summary, horizon, score, cost, cold)
    promoted = gate[gate["promotion_pass"].eq(1) & ~gate["variant"].eq(BASELINE_VARIANT)]
    startup_only = gate[gate["startup_target_pass"].eq(1) & ~gate["variant"].eq(BASELINE_VARIANT)]
    best = gate.iloc[0] if not gate.empty else None
    decision = {
        "stage": "Stage120",
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "decision": "diagnostic_candidate_requires_true_engine" if len(promoted) else "no_new_promotion",
        "promotion_ready_variants": promoted["variant"].tolist(),
        "startup_only_ready_variants": startup_only["variant"].tolist(),
        "best_by_gate_order": str(best["variant"]) if best is not None else "",
        "judgement": "固定分批启动若靠压低早期风险改善回撤，却降低中位收益/正收益率/低增长概率，则不符合本线目标。",
        "chart": str(CHART_PATH),
    }

    daily = pd.concat(daily_parts, ignore_index=True)
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    horizon.to_csv(HORIZON_PATH, index=False, encoding="utf-8-sig")
    score.to_csv(SCORE_PATH, index=False, encoding="utf-8-sig")
    cost.to_csv(COST_PATH, index=False, encoding="utf-8-sig")
    cold.to_csv(COLD_START_PATH, index=False, encoding="utf-8-sig")
    gate.to_csv(GATE_PATH, index=False, encoding="utf-8-sig")
    daily.to_csv(DAILY_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _plot(summary, horizon, gate, daily)
    _write_report(summary, horizon, score, cost, cold, gate, decision)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
