from __future__ import annotations

import json
import math
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

sys.path.insert(0, str(PROJECT_DIR.resolve()))
import analyze_qmt_roll_stage402_stage079_xsmom_volmanaged_true_integer as s402  # noqa: E402


MODEL_TAG = "stage403_stage079_xsmom_execution_margin_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage403_stage079_xsmom_execution_margin_audit"
LINE_ID = "futures_trend_drawdown30_preserve_return"

BASELINE_VARIANT = "stage079"
ROUND_HALF_VARIANT = "xsmom_vt10_q_momq_round_half_true"
GUARD_VARIANT = "xsmom_vt10_q_momq_round_half_true_broker10_guard"

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
HORIZON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_horizon_{MODEL_TAG}.csv"
SCORE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_score_{MODEL_TAG}.csv"
FRESH_START_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_fresh_start_{MODEL_TAG}.csv"
COST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cost_stress_{MODEL_TAG}.csv"
MARGIN_AUDIT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_margin_audit_{MODEL_TAG}.csv"
GATE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gate_{MODEL_TAG}.csv"
DAILY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_{MODEL_TAG}.csv"
SATELLITE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_satellite_daily_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

TARGET_DD_PCT = -30.0
BROKER_MARGIN_MULTIPLIERS = (1.00, 1.02, 1.05, 1.10)
BROKER10_MULTIPLIER = 1.10


@dataclass(frozen=True)
class AuditVariant:
    variant: str
    label: str
    mode: str
    note: str


VARIANTS: tuple[AuditVariant, ...] = (
    AuditVariant(BASELINE_VARIANT, "Stage079基准", "baseline", "50万C3下单+11.5万现金。"),
    AuditVariant(ROUND_HALF_VARIANT, "Stage102晋级候选", "round_half", "scale>=0.5时执行xsmom整篮子最低1手。"),
    AuditVariant(
        GUARD_VARIANT,
        "Stage102候选+10%经纪商保证金缓冲闸门",
        "broker10_guard",
        "若当日C3+xsmom保证金按1.10倍计算会超过上一日权益，则跳过当日xsmom篮子。",
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


def _safe_metric(value: Any, default: float = 0.0) -> float:
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


def _candidate(spec: AuditVariant, equity: pd.Series) -> Any:
    return s402.s087.Candidate(
        variant=spec.variant,
        label=spec.label,
        equity=equity,
        capital_used=s402.ACCOUNT_CAPITAL,
        candidate_class="execution_margin_audit" if spec.variant != BASELINE_VARIANT else "baseline",
        eligible_for_promotion=True,
        note=spec.note,
    )


def _empty_satellite(window_name: str) -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "date",
            "window_name",
            "satellite_daily_pnl",
            "satellite_slippage_cost",
            "satellite_margin",
            "satellite_turnover_contracts",
            "held_contract_count",
            "desired_signal_count",
            "required_min1_margin",
            "stage101_scale",
            "margin_gate_skipped",
        ]
    ).assign(window_name=window_name)


def _simulate_guarded_round_half(
    window_name: str,
    window_frame: pd.DataFrame,
    margin_frame: pd.DataFrame,
    price_frame: pd.DataFrame,
    signals: pd.DataFrame,
    scale_by_date: pd.Series,
) -> pd.DataFrame:
    start = window_frame["date"].min()
    end = window_frame["date"].max()
    window_signals = signals[signals["date"].between(start, end)].copy()
    if window_signals.empty:
        return _empty_satellite(window_name)

    c3_pnl_by_date = window_frame.set_index("date")["c3_net_pnl"].astype(float).to_dict()
    c3_margin_by_date = margin_frame.set_index("date")["c3_margin"].astype(float).to_dict()
    price_by_date_product = {
        (row.date, row.product_vt_symbol): row
        for row in price_frame[price_frame["date"].between(start, end)].itertuples(index=False)
    }
    contract_to_product = (
        price_frame[price_frame["date"].between(start, end)]
        .drop_duplicates(["date", "main_contract_vt"])
        .set_index(["date", "main_contract_vt"])["product_vt_symbol"]
        .to_dict()
    )
    prev_positions: dict[str, int] = {}
    rows: list[dict[str, Any]] = []
    prev_equity = s402.ACCOUNT_CAPITAL

    for signal_row in window_signals.sort_values("date").itertuples(index=False):
        date = pd.Timestamp(signal_row.date).normalize()
        scale = float(scale_by_date.get(date, 0.0))
        day_prices = price_frame[price_frame["date"].eq(date)]
        price_by_product = {str(row.product_vt_symbol): row for row in day_prices.itertuples(index=False)}
        desired = s402._desired_contracts(signal_row, price_by_product)
        targets, required_min1_margin = s402._target_lots("round_half", scale, desired)
        proposed_margin = 0.0
        for contract in targets:
            product = contract_to_product.get((date, contract))
            price_row = price_by_date_product.get((date, product)) if product else None
            if price_row is not None:
                proposed_margin += s402._safe_float(getattr(price_row, "margin_per_contract", 0.0))

        c3_margin = float(c3_margin_by_date.get(date, 0.0))
        margin_gate_skipped = int(bool(targets) and (c3_margin + proposed_margin) * BROKER10_MULTIPLIER > prev_equity)
        if margin_gate_skipped:
            targets = {}
            proposed_margin = 0.0

        pnl = 0.0
        margin = 0.0
        for contract, lots in targets.items():
            product = contract_to_product.get((date, contract))
            price_row = price_by_date_product.get((date, product)) if product else None
            if price_row is None:
                continue
            pnl += lots * s402._safe_float(getattr(price_row, "prev_main_close", 0.0)) * s402._safe_float(
                getattr(price_row, "size", 1.0)
            ) * s402._safe_float(getattr(price_row, "product_return", 0.0))
            margin += abs(lots) * s402._safe_float(getattr(price_row, "margin_per_contract", 0.0))

        turnover = 0
        slippage_cost = 0.0
        for contract in set(prev_positions) | set(targets):
            delta = abs(targets.get(contract, 0) - prev_positions.get(contract, 0))
            if delta <= 0:
                continue
            turnover += delta
            product = contract_to_product.get((date, contract))
            price_row = price_by_date_product.get((date, product)) if product else None
            if price_row is not None:
                slippage_cost += delta * s402._safe_float(getattr(price_row, "slippage", 0.0)) * s402._safe_float(
                    getattr(price_row, "size", 1.0)
                )

        sat_daily_pnl = pnl - slippage_cost
        rows.append(
            {
                "date": date,
                "window_name": window_name,
                "satellite_daily_pnl": sat_daily_pnl,
                "satellite_slippage_cost": slippage_cost,
                "satellite_margin": margin,
                "satellite_turnover_contracts": turnover,
                "held_contract_count": len(targets),
                "desired_signal_count": len(desired),
                "required_min1_margin": required_min1_margin,
                "stage101_scale": scale,
                "margin_gate_skipped": margin_gate_skipped,
            }
        )
        prev_positions = targets
        prev_equity += float(c3_pnl_by_date.get(date, 0.0)) + sat_daily_pnl

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
        metrics: list[str] = []
        for metric in sorted(larger_is_better):
            if _safe_metric(row[metric]) > _safe_metric(base[metric]):
                improved += 1
                metrics.append(metric)
        for metric in sorted(smaller_is_better):
            if _safe_metric(row[metric]) < _safe_metric(base[metric]):
                improved += 1
                metrics.append(metric)
        rows.append(
            {
                "variant": row["variant"],
                "label": row["label"],
                "horizon_days": horizon_days,
                "objective_improved_8_count": improved,
                "objective_improved_8_metrics": ",".join(metrics),
            }
        )
    return pd.DataFrame(rows)


def _margin_audit(
    combo: pd.DataFrame,
    margin: pd.DataFrame,
    satellite_by_window_variant: dict[tuple[str, str], pd.DataFrame],
    daily_by_window_variant: dict[tuple[str, str], pd.DataFrame],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for window_name, m in margin.groupby("window_name", sort=True):
        m = m.sort_values("date").drop_duplicates("date", keep="last")
        for spec in VARIANTS:
            satellite = satellite_by_window_variant.get((window_name, spec.variant), _empty_satellite(window_name))
            daily = daily_by_window_variant.get((window_name, spec.variant))
            if daily is None or daily.empty:
                frame = combo[combo["window_name"].eq(window_name)].sort_values("date").drop_duplicates("date", keep="last")
                daily = s402._combine_daily(frame, satellite, spec.variant, 1.0)
            equity = pd.Series(daily["equity"].to_numpy(dtype=float), index=daily["date"])
            sat_margin = (
                satellite.set_index("date")["satellite_margin"].astype(float)
                if not satellite.empty and "satellite_margin" in satellite.columns
                else pd.Series(dtype=float)
            )
            base_total_margin = m["c3_margin"].to_numpy(dtype=float) + sat_margin.reindex(m["date"]).fillna(0.0).to_numpy(dtype=float)
            equity_on_margin_dates = equity.reindex(m["date"]).ffill().to_numpy(dtype=float)
            for multiplier in BROKER_MARGIN_MULTIPLIERS:
                stressed_margin = base_total_margin * multiplier
                margin_to_equity = stressed_margin / equity_on_margin_dates * 100.0
                over_100 = margin_to_equity > 100.0
                overage = np.maximum(stressed_margin - equity_on_margin_dates, 0.0)
                first_reject_date = ""
                if bool(np.any(over_100)):
                    first_reject_date = str(pd.Timestamp(m.loc[over_100, "date"].iloc[0]).date())
                rows.append(
                    {
                        "window_name": window_name,
                        "variant": spec.variant,
                        "label": spec.label,
                        "margin_multiplier": multiplier,
                        "max_margin_to_equity_pct": float(np.nanmax(margin_to_equity)) if len(margin_to_equity) else 0.0,
                        "p95_margin_to_equity_pct": float(np.nanpercentile(margin_to_equity, 95)) if len(margin_to_equity) else 0.0,
                        "days_over_90pct": int(np.sum(margin_to_equity > 90.0)),
                        "days_over_95pct": int(np.sum(margin_to_equity > 95.0)),
                        "days_over_98pct": int(np.sum(margin_to_equity > 98.0)),
                        "reject_days_over_100pct": int(np.sum(over_100)),
                        "first_reject_date": first_reject_date,
                        "required_extra_cash_for_no_reject": float(np.nanmax(overage)) if len(overage) else 0.0,
                        "min_free_cash_pct": float(100.0 - np.nanmax(margin_to_equity)) if len(margin_to_equity) else 100.0,
                    }
                )
    return pd.DataFrame(rows)


def _fresh_start(
    combo: pd.DataFrame,
    margin: pd.DataFrame,
    satellite_by_window_variant: dict[tuple[str, str], pd.DataFrame],
    daily_by_window_variant: dict[tuple[str, str], pd.DataFrame],
    margin_audit: pd.DataFrame,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    audit10 = margin_audit[margin_audit["margin_multiplier"].eq(BROKER10_MULTIPLIER)].set_index(["window_name", "variant"])
    for window_name, frame in combo.groupby("window_name", sort=True):
        frame = frame.sort_values("date").drop_duplicates("date", keep="last")
        for spec in VARIANTS:
            satellite = satellite_by_window_variant.get((window_name, spec.variant), _empty_satellite(window_name))
            daily = daily_by_window_variant.get((window_name, spec.variant))
            if daily is None or daily.empty:
                daily = s402._combine_daily(frame, satellite, spec.variant, 1.0)
            equity = pd.Series(daily["equity"].to_numpy(dtype=float), index=daily["date"])
            nav = equity / s402.ACCOUNT_CAPITAL
            max_dd = s402.s087._max_drawdown(nav)
            audit_row = audit10.loc[(window_name, spec.variant)] if (window_name, spec.variant) in audit10.index else None
            rows.append(
                {
                    "window_name": window_name,
                    "variant": spec.variant,
                    "label": spec.label,
                    "end_equity": float(equity.iloc[-1]),
                    "total_return_pct": float((nav.iloc[-1] - 1.0) * 100.0),
                    "max_dd_pct": max_dd,
                    "dd30_pass": int(max_dd >= TARGET_DD_PCT),
                    "satellite_slippage": float(satellite["satellite_slippage_cost"].sum()) if not satellite.empty else 0.0,
                    "satellite_turnover": float(satellite["satellite_turnover_contracts"].sum()) if not satellite.empty else 0.0,
                    "max_satellite_margin": float(satellite["satellite_margin"].max()) if not satellite.empty else 0.0,
                    "margin_gate_skipped_days": int(satellite.get("margin_gate_skipped", pd.Series(dtype=float)).sum()) if not satellite.empty else 0,
                    "broker10_max_margin_to_equity_pct": float(audit_row["max_margin_to_equity_pct"]) if audit_row is not None else 0.0,
                    "broker10_reject_days": int(audit_row["reject_days_over_100pct"]) if audit_row is not None else 0,
                }
            )
    return pd.DataFrame(rows)


def _cost_stress(full_frame: pd.DataFrame, satellite_full_by_variant: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    baseline_dd: dict[float, float] = {}
    for multiplier in (1.0, 2.0, 3.0, 5.0):
        for spec in VARIANTS:
            satellite = satellite_full_by_variant.get(spec.variant, _empty_satellite("start_2020"))
            daily = s402._combine_daily(full_frame, satellite, spec.variant, multiplier)
            equity = s402._calendarize(pd.Series(daily["equity"].to_numpy(dtype=float), index=daily["date"]))
            nav = equity / s402.ACCOUNT_CAPITAL
            max_dd = s402.s087._max_drawdown(nav)
            if spec.variant == BASELINE_VARIANT:
                baseline_dd[multiplier] = max_dd
            rows.append(
                {
                    "variant": spec.variant,
                    "label": spec.label,
                    "slippage_multiplier": multiplier,
                    "total_return_pct": float((nav.iloc[-1] - 1.0) * 100.0),
                    "max_dd_pct": max_dd,
                }
            )
    result = pd.DataFrame(rows)
    result["baseline_stage079_max_dd_pct"] = result["slippage_multiplier"].map(baseline_dd)
    result["not_worse_than_stage079_stress"] = (
        result["max_dd_pct"] >= result["baseline_stage079_max_dd_pct"] - 1e-9
    ).astype(int)
    return result


def _gate(
    summary: pd.DataFrame,
    horizon: pd.DataFrame,
    score: pd.DataFrame,
    cost: pd.DataFrame,
    fresh: pd.DataFrame,
    margin_audit: pd.DataFrame,
) -> pd.DataFrame:
    baseline = summary[summary["variant"].eq(BASELINE_VARIANT)].iloc[0]
    objective_improved = _objective_improved_counts(horizon)
    improved_p = objective_improved.pivot(
        index=["variant", "label"], columns="horizon_days", values="objective_improved_8_count"
    ).reset_index()
    improved_p.columns = ["variant", "label", "objective_improved_8_count_90d", "objective_improved_8_count_180d"]
    score_one = score.drop_duplicates(["variant", "label"])[
        ["variant", "label", "score_90d", "score_180d", "short_holding_score"]
    ]
    fresh_failures = (
        fresh[fresh["dd30_pass"].eq(0)]
        .groupby("variant")["window_name"]
        .apply(lambda values: ",".join(sorted(map(str, values))))
        .to_dict()
    )
    broker10 = margin_audit[margin_audit["margin_multiplier"].eq(BROKER10_MULTIPLIER)].copy()
    broker10_failures = (
        broker10[broker10["reject_days_over_100pct"].gt(0)]
        .groupby("variant")["window_name"]
        .apply(lambda values: ",".join(sorted(map(str, values))))
        .to_dict()
    )
    baseline_broker10 = broker10[broker10["variant"].eq(BASELINE_VARIANT)].set_index("window_name")
    broker10_relative_failures: dict[str, str] = {}
    for variant, frame in broker10.groupby("variant", sort=True):
        if variant == BASELINE_VARIANT:
            continue
        failed_windows: list[str] = []
        for row in frame.itertuples(index=False):
            if row.window_name not in baseline_broker10.index:
                continue
            base = baseline_broker10.loc[row.window_name]
            baseline_has_reject = int(base["reject_days_over_100pct"]) > 0
            candidate_has_reject = int(row.reject_days_over_100pct) > 0
            if baseline_has_reject:
                worse = (
                    int(row.reject_days_over_100pct) > int(base["reject_days_over_100pct"])
                    or float(row.required_extra_cash_for_no_reject) > float(base["required_extra_cash_for_no_reject"]) + 1e-9
                )
            else:
                worse = candidate_has_reject
            if worse:
                failed_windows.append(str(row.window_name))
        if failed_windows:
            broker10_relative_failures[variant] = ",".join(sorted(failed_windows))
    rows: list[dict[str, Any]] = []
    for _, row in summary.iterrows():
        c = cost[cost["variant"].eq(row["variant"])]
        checks = {
            "total_return_not_lower": _safe_metric(row["total_return_pct"]) >= _safe_metric(baseline["total_return_pct"]) - 1e-4,
            "max_dd_not_worse": _safe_metric(row["max_dd_pct"]) >= _safe_metric(baseline["max_dd_pct"]) - 1e-4,
            "max_dd_below_30": _safe_metric(row["max_dd_pct"]) >= TARGET_DD_PCT,
            "sharpe_not_lower": _safe_metric(row["sharpe"]) >= _safe_metric(baseline["sharpe"]) - 1e-4,
            "ulcer_not_higher": _safe_metric(row["ulcer_pct"]) <= _safe_metric(baseline["ulcer_pct"]) + 1e-4,
            "rolling252_dd30_zero": _safe_metric(row["rolling252_dd30_breach_rate"]) == 0.0,
            "rolling504_dd30_zero": _safe_metric(row["rolling504_dd30_breach_rate"]) == 0.0,
            "annual_dd30_pass_100": _safe_metric(row["annual_cold_start_dd30_pass_rate"]) == 1.0,
            "quarter_dd30_pass_100": _safe_metric(row["quarter_cold_start_dd30_pass_rate"]) == 1.0,
            "capital_not_increased": _safe_metric(row["capital_used"]) <= s402.ACCOUNT_CAPITAL,
            "cost_stress_not_worse": bool(c["not_worse_than_stage079_stress"].eq(1).all()) if not c.empty else False,
            "fresh_start_dd30_pass": str(row["variant"]) not in fresh_failures,
        }
        rows.append(
            {
                "variant": row["variant"],
                "label": row["label"],
                **{name: int(flag) for name, flag in checks.items()},
                "metric_hard_pass": int(all(checks.values())),
                "broker10_absolute_no_reject_all_windows": int(str(row["variant"]) not in broker10_failures),
                "broker10_not_worse_than_stage079_all_windows": int(
                    row["variant"] == BASELINE_VARIANT or str(row["variant"]) not in broker10_relative_failures
                ),
                "fresh_start_failed_windows": fresh_failures.get(str(row["variant"]), ""),
                "broker10_reject_windows": broker10_failures.get(str(row["variant"]), ""),
                "broker10_relative_worse_windows": broker10_relative_failures.get(str(row["variant"]), ""),
                "failed_metric_checks": ",".join([name for name, flag in checks.items() if not flag]),
            }
        )
    result = pd.DataFrame(rows).merge(score_one, on=["variant", "label"], how="left").merge(
        improved_p, on=["variant", "label"], how="left"
    )
    result["score90_improve_ge10pct"] = (result["score_90d"] >= 110.0).astype(int)
    result["score180_improve_ge10pct"] = (result["score_180d"] >= 110.0).astype(int)
    result["objective_improved_5of8_each"] = (
        (result["objective_improved_8_count_90d"] >= 5) & (result["objective_improved_8_count_180d"] >= 5)
    ).astype(int)
    result["target_pass_3m6m"] = (
        result["score90_improve_ge10pct"].eq(1)
        & result["score180_improve_ge10pct"].eq(1)
        & result["objective_improved_5of8_each"].eq(1)
    ).astype(int)
    result["research_promotion_pass"] = (result["metric_hard_pass"].eq(1) & result["target_pass_3m6m"].eq(1)).astype(int)
    result["execution_relative_pass"] = (
        result["research_promotion_pass"].eq(1) & result["broker10_not_worse_than_stage079_all_windows"].eq(1)
    ).astype(int)
    result["deployment_absolute_margin_pass"] = (
        result["research_promotion_pass"].eq(1) & result["broker10_absolute_no_reject_all_windows"].eq(1)
    ).astype(int)
    return result.sort_values(
        ["execution_relative_pass", "deployment_absolute_margin_pass", "research_promotion_pass", "short_holding_score"],
        ascending=[False, False, False, False],
    )


def _plot(daily: pd.DataFrame, margin_audit: pd.DataFrame) -> None:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception as exc:  # pragma: no cover
        print(f"[stage403] skip chart: {exc}", flush=True)
        return
    fig, axes = plt.subplots(3, 1, figsize=(13, 10), sharex=False)
    full = daily[daily["window_name"].eq("start_2020")]
    for variant, frame in full.groupby("variant"):
        frame = frame.sort_values("date")
        nav = pd.Series(frame["equity"].to_numpy(dtype=float), index=pd.to_datetime(frame["date"])) / s402.ACCOUNT_CAPITAL
        axes[0].plot(nav.index, nav, label=variant, linewidth=1.1)
        axes[1].plot(nav.index, (nav / nav.cummax() - 1.0) * 100.0, label=variant, linewidth=1.0)
    axes[0].set_title("Stage103/403 execution margin audit NAV")
    axes[0].set_ylabel("NAV")
    axes[1].set_title("Drawdown")
    axes[1].set_ylabel("Drawdown %")
    axes[1].axhline(-30.0, color="red", linestyle="--", linewidth=1.0)
    audit = margin_audit[
        margin_audit["window_name"].eq("start_2020") & margin_audit["margin_multiplier"].isin([1.00, 1.10])
    ]
    x = np.arange(len(audit))
    axes[2].bar(x, audit["max_margin_to_equity_pct"].to_numpy(dtype=float), color="#4c78a8")
    axes[2].axhline(100.0, color="red", linestyle="--", linewidth=1.0)
    axes[2].set_xticks(x)
    axes[2].set_xticklabels(
        [f"{row.variant}\n{row.margin_multiplier:.2f}x" for row in audit.itertuples(index=False)],
        rotation=25,
        ha="right",
        fontsize=8,
    )
    axes[2].set_ylabel("Max margin/equity %")
    axes[0].legend(fontsize=8)
    axes[1].legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=160)
    plt.close(fig)


def _write_report(
    summary: pd.DataFrame,
    horizon: pd.DataFrame,
    score: pd.DataFrame,
    fresh: pd.DataFrame,
    cost: pd.DataFrame,
    margin_audit: pd.DataFrame,
    gate: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    report = [
        "# Stage103 Stage079 xsmom执行保证金审计",
        "",
        f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "- 阶段性质：执行风险审计；固定 Stage102 候选，不扫描 alpha 参数。",
        "- A/B/C：A=Stage079；C1=Stage102 round_half_true；C2=C1+10%经纪商保证金缓冲闸门。",
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
        _md_table(summary[["variant", "total_return_pct", "max_dd_pct", "sharpe", "ulcer_pct", "rolling252_dd30_breach_rate", "rolling504_dd30_breach_rate", "annual_cold_start_dd30_pass_rate", "quarter_cold_start_dd30_pass_rate"]]),
        "",
        "## 3个月/6个月体验",
        "",
        _md_table(horizon[["variant", "horizon_days", "return_p05_pct", "return_median_pct", "positive_return_rate", "annualized_below_5pct_rate", "max_dd_worst_pct", "dd20_breach_rate", "dd30_breach_rate", "ulcer_p95_pct", "longest_underwater_p95_days"]]),
        "",
        "## 体验评分",
        "",
        _md_table(score[["variant", "horizon_days", "experience_score", "score_90d", "score_180d", "short_holding_score"]]),
        "",
        "## 多起点与10%保证金缓冲",
        "",
        _md_table(fresh[["window_name", "variant", "total_return_pct", "max_dd_pct", "dd30_pass", "satellite_turnover", "margin_gate_skipped_days", "broker10_max_margin_to_equity_pct", "broker10_reject_days"]]),
        "",
        "## 保证金压力审计",
        "",
        _md_table(
            margin_audit[
                margin_audit["margin_multiplier"].isin([1.00, 1.05, 1.10])
            ][
                [
                    "window_name",
                    "variant",
                    "margin_multiplier",
                    "max_margin_to_equity_pct",
                    "days_over_95pct",
                    "reject_days_over_100pct",
                    "required_extra_cash_for_no_reject",
                    "first_reject_date",
                ]
            ],
            max_rows=80,
        ),
        "",
        "## 成本压力",
        "",
        _md_table(cost[["variant", "slippage_multiplier", "total_return_pct", "max_dd_pct", "baseline_stage079_max_dd_pct", "not_worse_than_stage079_stress"]]),
        "",
        "## 晋级闸门",
        "",
        _md_table(gate[["variant", "metric_hard_pass", "target_pass_3m6m", "research_promotion_pass", "broker10_absolute_no_reject_all_windows", "broker10_not_worse_than_stage079_all_windows", "execution_relative_pass", "deployment_absolute_margin_pass", "score_90d", "score_180d", "objective_improved_8_count_90d", "objective_improved_8_count_180d", "broker10_reject_windows", "broker10_relative_worse_windows", "failed_metric_checks"]]),
        "",
        "## 反过拟合说明",
        "",
        "- 本阶段没有继续调 `10%`、`63日`、`0.5`，只审计 Stage102 已固定候选的保证金鲁棒性。",
        "- `broker10_guard` 来自执行约束：按 1.10 倍保证金仍不超过上一日权益，不是根据收益曲线反向拟合。",
    ]
    REPORT_PATH.write_text("\n".join(report) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    combo = s402._load_combo_daily()
    margin = s402._load_margin()
    full = combo[combo["window_name"].eq("start_2020")].sort_values("date").drop_duplicates("date", keep="last")
    scale_by_date = s402._build_stage101_scale(full)
    price_frame = s402._build_price_frame()
    price_frame["date"] = pd.to_datetime(price_frame["date"], errors="coerce").dt.normalize()
    signals = s402._load_signal_daily()
    signals["date"] = pd.to_datetime(signals["date"], errors="coerce").dt.normalize()

    satellite_by_window_variant: dict[tuple[str, str], pd.DataFrame] = {}
    daily_by_window_variant: dict[tuple[str, str], pd.DataFrame] = {}
    satellite_full_by_variant: dict[str, pd.DataFrame] = {}
    candidates: list[Any] = []
    daily_parts: list[pd.DataFrame] = []

    for window_name, frame in combo.groupby("window_name", sort=True):
        frame = frame.sort_values("date").drop_duplicates("date", keep="last")
        margin_frame = margin[margin["window_name"].eq(window_name)].sort_values("date").drop_duplicates("date", keep="last")
        for spec in VARIANTS:
            if spec.variant == BASELINE_VARIANT:
                sat = _empty_satellite(window_name)
            elif spec.variant == ROUND_HALF_VARIANT:
                sat = s402._simulate_satellite(window_name, "round_half", frame, price_frame, signals, scale_by_date)
                sat["margin_gate_skipped"] = 0
            else:
                sat = _simulate_guarded_round_half(window_name, frame, margin_frame, price_frame, signals, scale_by_date)
            satellite_by_window_variant[(window_name, spec.variant)] = sat
            daily = s402._combine_daily(frame, sat, spec.variant, 1.0)
            daily["window_name"] = window_name
            daily_by_window_variant[(window_name, spec.variant)] = daily
            if window_name == "start_2020":
                satellite_full_by_variant[spec.variant] = sat

    full_frame = combo[combo["window_name"].eq("start_2020")].sort_values("date").drop_duplicates("date", keep="last")
    for spec in VARIANTS:
        daily = daily_by_window_variant[("start_2020", spec.variant)]
        daily_parts.append(daily)
        equity = s402._calendarize(pd.Series(daily["equity"].to_numpy(dtype=float), index=daily["date"]))
        candidates.append(_candidate(spec, equity))

    daily_all = pd.concat(daily_parts, ignore_index=True)
    satellite_all = pd.concat(
        [
            frame.assign(variant=variant)
            for (window_name, variant), frame in satellite_by_window_variant.items()
            if variant != BASELINE_VARIANT and not frame.empty
        ],
        ignore_index=True,
    )
    summary = pd.DataFrame([s402.s087._stats(candidate) for candidate in candidates])
    horizon = pd.DataFrame([s402.s087._horizon_metrics(candidate, days) for candidate in candidates for days in (90, 180)])
    score = s402.s087._score_horizons(horizon)
    margin_audit = _margin_audit(combo, margin, satellite_by_window_variant, daily_by_window_variant)
    fresh = _fresh_start(combo, margin, satellite_by_window_variant, daily_by_window_variant, margin_audit)
    cost = _cost_stress(full_frame, satellite_full_by_variant)
    gate = _gate(summary, horizon, score, cost, fresh, margin_audit)

    execution_ready = gate[gate["execution_relative_pass"].eq(1) & ~gate["variant"].eq(BASELINE_VARIANT)]
    deployment_ready = gate[gate["deployment_absolute_margin_pass"].eq(1) & ~gate["variant"].eq(BASELINE_VARIANT)]
    research_ready = gate[gate["research_promotion_pass"].eq(1) & ~gate["variant"].eq(BASELINE_VARIANT)]
    decision = {
        "stage": "Stage103",
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "decision": "absolute_deployment_candidate"
        if len(deployment_ready)
        else ("execution_relative_candidate" if len(execution_ready) else ("research_candidate_only" if len(research_ready) else "no_promotion")),
        "absolute_deployment_ready_variants": deployment_ready["variant"].tolist(),
        "execution_relative_ready_variants": execution_ready["variant"].tolist(),
        "research_ready_variants": research_ready["variant"].tolist(),
        "best_by_execution_gate": gate.iloc[0]["variant"] if not gate.empty else "",
        "chart": str(CHART_PATH),
        "judgement": "保证金执行审计完成；若Stage079自身在10%保证金上浮下也会拒单，则以相对Stage079不更差作为执行晋级闸门，绝对部署仍需券商保证金确认。",
    }

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    horizon.to_csv(HORIZON_PATH, index=False, encoding="utf-8-sig")
    score.to_csv(SCORE_PATH, index=False, encoding="utf-8-sig")
    fresh.to_csv(FRESH_START_PATH, index=False, encoding="utf-8-sig")
    cost.to_csv(COST_PATH, index=False, encoding="utf-8-sig")
    margin_audit.to_csv(MARGIN_AUDIT_PATH, index=False, encoding="utf-8-sig")
    gate.to_csv(GATE_PATH, index=False, encoding="utf-8-sig")
    daily_all.to_csv(DAILY_PATH, index=False, encoding="utf-8-sig")
    satellite_all.to_csv(SATELLITE_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _plot(daily_all, margin_audit)
    _write_report(summary, horizon, score, fresh, cost, margin_audit, gate, decision)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print(f"report={REPORT_PATH}")


if __name__ == "__main__":
    main()
