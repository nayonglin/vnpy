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
import analyze_qmt_roll_stage403_stage079_xsmom_execution_margin_audit as s403  # noqa: E402


MODEL_TAG = "stage427_stage103_pair_spread_overlay_v1"
OUTPUT_PREFIX = "qmt_roll_stage427_stage103_pair_spread_overlay"
LINE_ID = "futures_trend_drawdown30_preserve_return"

BASELINE_VARIANT = "stage079"
STAGE103_VARIANT = "xsmom_vt10_q_momq_round_half_true_broker10_guard"
PAIR_BEST1_VARIANT = "stage103_plus_pair_spread_mr120_best1_guard"
PAIR_ALL_VARIANT = "stage103_plus_pair_spread_mr120_all_guard"

LOOKBACK_DAYS = 120
ENTRY_Z = 1.0
BROKER10_MULTIPLIER = 1.10
TARGET_DD_PCT = -30.0

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
HORIZON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_horizon_{MODEL_TAG}.csv"
SCORE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_score_{MODEL_TAG}.csv"
FRESH_START_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_fresh_start_{MODEL_TAG}.csv"
COST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cost_stress_{MODEL_TAG}.csv"
MARGIN_AUDIT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_margin_audit_{MODEL_TAG}.csv"
GATE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gate_{MODEL_TAG}.csv"
DAILY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_{MODEL_TAG}.csv"
PAIR_DAILY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_pair_daily_{MODEL_TAG}.csv"
FEATURE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_pair_features_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"


@dataclass(frozen=True)
class VariantSpec:
    variant: str
    label: str
    mode: str
    note: str


VARIANTS: tuple[VariantSpec, ...] = (
    VariantSpec(BASELINE_VARIANT, "A Stage079基准", "baseline", "50万C3下单+11.5万现金。"),
    VariantSpec(STAGE103_VARIANT, "C0 Stage103 broker10_guard", "stage103", "当前主执行相对候选。"),
    VariantSpec(
        PAIR_BEST1_VARIANT,
        "C1 Stage103+产业链价差MR120 best1",
        "best1",
        "预声明产业链价差，120日z-score超过1时做均值回归，每天只取abs(z)最高的一对。",
    ),
    VariantSpec(
        PAIR_ALL_VARIANT,
        "C2 Stage103+产业链价差MR120 all",
        "all",
        "同一组预声明产业链价差，所有触发对都持有一手价差。",
    ),
)


PAIR_SPECS: tuple[tuple[str, str, str], ...] = (
    ("steel_flat", "rb.SHFE", "hc.SHFE"),
    ("glass_soda_ash", "FG.CZCE", "SA.CZCE"),
    ("methanol_soda_ash", "MA.CZCE", "SA.CZCE"),
    ("rebar_coking_coal", "rb.SHFE", "jm.DCE"),
    ("hotcoil_coking_coal", "hc.SHFE", "jm.DCE"),
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


def _candidate(spec: VariantSpec, equity: pd.Series) -> Any:
    return s402.s087.Candidate(
        variant=spec.variant,
        label=spec.label,
        equity=equity,
        capital_used=s402.ACCOUNT_CAPITAL,
        candidate_class="pair_spread_overlay" if spec.variant not in {BASELINE_VARIANT, STAGE103_VARIANT} else spec.mode,
        eligible_for_promotion=True,
        note=spec.note,
    )


def _build_pair_features(price_frame: pd.DataFrame) -> pd.DataFrame:
    frame = price_frame.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame["main_close"] = pd.to_numeric(frame["main_close"], errors="coerce")
    frame["size"] = pd.to_numeric(frame["size"], errors="coerce")
    frame["contract_notional"] = frame["main_close"] * frame["size"]
    notional = frame.pivot_table(index="date", columns="product_vt_symbol", values="contract_notional", aggfunc="last")

    rows: list[pd.DataFrame] = []
    for pair_id, product_a, product_b in PAIR_SPECS:
        if product_a not in notional.columns or product_b not in notional.columns:
            continue
        spread = np.log(notional[product_a]) - np.log(notional[product_b])
        prior = spread.shift(1)
        mean = spread.rolling(LOOKBACK_DAYS, min_periods=LOOKBACK_DAYS).mean().shift(1)
        std = spread.rolling(LOOKBACK_DAYS, min_periods=LOOKBACK_DAYS).std(ddof=1).shift(1)
        z = (prior - mean) / std.replace(0.0, np.nan)
        pair = pd.DataFrame(
            {
                "date": z.index,
                "pair_id": pair_id,
                "product_a": product_a,
                "product_b": product_b,
                "spread_z": z.to_numpy(dtype=float),
            }
        )
        pair["abs_z"] = pair["spread_z"].abs()
        pair["direction_a"] = np.where(pair["spread_z"] >= ENTRY_Z, -1, np.where(pair["spread_z"] <= -ENTRY_Z, 1, 0))
        pair["direction_b"] = -pair["direction_a"]
        rows.append(pair)
    if not rows:
        return pd.DataFrame(
            columns=["date", "pair_id", "product_a", "product_b", "spread_z", "abs_z", "direction_a", "direction_b"]
        )
    result = pd.concat(rows, ignore_index=True)
    result = result.dropna(subset=["date", "spread_z"])
    return result[result["direction_a"].ne(0)].sort_values(["date", "abs_z"], ascending=[True, False])


def _aggregate_satellites(window_name: str, xsmom: pd.DataFrame, pair: pd.DataFrame) -> pd.DataFrame:
    if xsmom.empty and pair.empty:
        return _empty_satellite(window_name)
    x = xsmom.copy() if not xsmom.empty else _empty_satellite(window_name)
    p = pair.copy() if not pair.empty else _empty_satellite(window_name)
    cols = [
        "satellite_daily_pnl",
        "satellite_slippage_cost",
        "satellite_margin",
        "satellite_turnover_contracts",
        "held_contract_count",
        "desired_signal_count",
        "required_min1_margin",
        "margin_gate_skipped",
    ]
    merged = pd.DataFrame({"date": sorted(set(pd.to_datetime(x["date"]).dropna()) | set(pd.to_datetime(p["date"]).dropna()))})
    merged["date"] = pd.to_datetime(merged["date"]).dt.normalize()
    for prefix, source in (("x", x), ("p", p)):
        source = source.copy()
        source["date"] = pd.to_datetime(source["date"], errors="coerce").dt.normalize()
        source = source.dropna(subset=["date"])
        keep = ["date"] + [col for col in [*cols, "stage101_scale"] if col in source.columns]
        merged = merged.merge(source[keep].rename(columns={col: f"{prefix}_{col}" for col in keep if col != "date"}), on="date", how="left")
    merged["window_name"] = window_name
    def _series(name: str) -> pd.Series:
        if name not in merged.columns:
            return pd.Series(0.0, index=merged.index)
        return pd.to_numeric(merged[name], errors="coerce").fillna(0.0)

    for col in cols:
        merged[col] = _series(f"x_{col}") + _series(f"p_{col}")
    merged["stage101_scale"] = _series("x_stage101_scale")
    return merged[
        [
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
    ]


def _simulate_pair_overlay(
    window_name: str,
    mode: str,
    window_frame: pd.DataFrame,
    margin_frame: pd.DataFrame,
    xsmom_satellite: pd.DataFrame,
    price_frame: pd.DataFrame,
    pair_features: pd.DataFrame,
) -> pd.DataFrame:
    start = pd.Timestamp(window_frame["date"].min()).normalize()
    end = pd.Timestamp(window_frame["date"].max()).normalize()
    signals = pair_features[pair_features["date"].between(start, end)].copy()
    if signals.empty:
        return _empty_satellite(window_name)
    signals_by_date = {date: day.copy() for date, day in signals.groupby("date", sort=True)}
    trading_dates = (
        pd.to_datetime(window_frame["date"], errors="coerce")
        .dropna()
        .dt.normalize()
        .drop_duplicates()
        .sort_values()
    )

    price_window = price_frame[price_frame["date"].between(start, end)].copy()
    price_by_date_product = {(row.date, row.product_vt_symbol): row for row in price_window.itertuples(index=False)}
    contract_to_product = (
        price_window.drop_duplicates(["date", "main_contract_vt"])
        .set_index(["date", "main_contract_vt"])["product_vt_symbol"]
        .to_dict()
    )
    c3_pnl_by_date = window_frame.set_index("date")["c3_net_pnl"].astype(float).to_dict()
    c3_margin_by_date = margin_frame.set_index("date")["c3_margin"].astype(float).to_dict()
    xsmom = xsmom_satellite.copy()
    if xsmom.empty:
        xsmom_by_date: dict[pd.Timestamp, dict[str, float]] = {}
    else:
        xsmom["date"] = pd.to_datetime(xsmom["date"], errors="coerce").dt.normalize()
        xsmom_by_date = {
            row.date: {
                "pnl": _safe_float(getattr(row, "satellite_daily_pnl", 0.0)),
                "margin": _safe_float(getattr(row, "satellite_margin", 0.0)),
            }
            for row in xsmom.itertuples(index=False)
        }

    prev_positions: dict[str, int] = {}
    prev_equity = s402.ACCOUNT_CAPITAL
    rows: list[dict[str, Any]] = []
    for date in trading_dates:
        date = pd.Timestamp(date).normalize()
        day_signals = signals_by_date.get(date)
        if day_signals is None:
            chosen = signals.iloc[0:0].copy()
        else:
            chosen = day_signals.head(1) if mode == "best1" else day_signals
        product_targets: dict[str, int] = {}
        for row in chosen.itertuples(index=False):
            product_targets[str(row.product_a)] = product_targets.get(str(row.product_a), 0) + int(row.direction_a)
            product_targets[str(row.product_b)] = product_targets.get(str(row.product_b), 0) + int(row.direction_b)

        targets: dict[str, int] = {}
        required_margin = 0.0
        for product, lots in product_targets.items():
            if lots == 0:
                continue
            price_row = price_by_date_product.get((date, product))
            if price_row is None:
                continue
            contract = str(getattr(price_row, "main_contract_vt", ""))
            margin = _safe_float(getattr(price_row, "margin_per_contract", 0.0))
            if not contract or margin <= 0.0:
                continue
            targets[contract] = targets.get(contract, 0) + int(lots)
            required_margin += abs(int(lots)) * margin

        proposed_margin = 0.0
        for contract, lots in targets.items():
            product = contract_to_product.get((date, contract))
            price_row = price_by_date_product.get((date, product)) if product else None
            if price_row is not None:
                proposed_margin += abs(lots) * _safe_float(getattr(price_row, "margin_per_contract", 0.0))

        x_state = xsmom_by_date.get(date, {"pnl": 0.0, "margin": 0.0})
        base_margin = float(c3_margin_by_date.get(date, 0.0)) + float(x_state["margin"])
        margin_gate_skipped = int(bool(targets) and (base_margin + proposed_margin) * BROKER10_MULTIPLIER > prev_equity)
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
            pnl += lots * _safe_float(getattr(price_row, "prev_main_close", 0.0)) * _safe_float(
                getattr(price_row, "size", 1.0)
            ) * _safe_float(getattr(price_row, "product_return", 0.0))
            margin += abs(lots) * _safe_float(getattr(price_row, "margin_per_contract", 0.0))

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
                slippage_cost += delta * _safe_float(getattr(price_row, "slippage", 0.0)) * _safe_float(
                    getattr(price_row, "size", 1.0)
                )

        pair_pnl = pnl - slippage_cost
        rows.append(
            {
                "date": date,
                "window_name": window_name,
                "satellite_daily_pnl": pair_pnl,
                "satellite_slippage_cost": slippage_cost,
                "satellite_margin": margin,
                "satellite_turnover_contracts": turnover,
                "held_contract_count": len([v for v in targets.values() if v != 0]),
                "desired_signal_count": int(len(chosen)),
                "required_min1_margin": required_margin,
                "stage101_scale": 0.0,
                "margin_gate_skipped": margin_gate_skipped,
            }
        )
        prev_positions = targets
        prev_equity += float(c3_pnl_by_date.get(date, 0.0)) + float(x_state["pnl"]) + pair_pnl

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
            total_margin = m["c3_margin"].to_numpy(dtype=float) + sat_margin.reindex(m["date"]).fillna(0.0).to_numpy(dtype=float)
            equity_on_margin_dates = equity.reindex(m["date"]).ffill().to_numpy(dtype=float)
            for multiplier in (1.00, 1.05, 1.10):
                stressed_margin = total_margin * multiplier
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
                        "days_over_95pct": int(np.sum(margin_to_equity > 95.0)),
                        "reject_days_over_100pct": int(np.sum(over_100)),
                        "required_extra_cash_for_no_reject": float(np.nanmax(overage)) if len(overage) else 0.0,
                        "first_reject_date": first_reject_date,
                    }
                )
    return pd.DataFrame(rows)


def _fresh_start(
    combo: pd.DataFrame,
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
            audit_row = audit10.loc[(window_name, spec.variant)] if (window_name, spec.variant) in audit10.index else None
            rows.append(
                {
                    "window_name": window_name,
                    "variant": spec.variant,
                    "label": spec.label,
                    "end_equity": float(equity.iloc[-1]),
                    "total_return_pct": float((nav.iloc[-1] - 1.0) * 100.0),
                    "max_dd_pct": s402.s087._max_drawdown(nav),
                    "dd30_pass": int(s402.s087._max_drawdown(nav) >= TARGET_DD_PCT),
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
            if _safe_float(row[metric]) > _safe_float(base[metric]):
                improved += 1
                metrics.append(metric)
        for metric in sorted(smaller_is_better):
            if _safe_float(row[metric]) < _safe_float(base[metric]):
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


def _gate(
    summary: pd.DataFrame,
    horizon: pd.DataFrame,
    score: pd.DataFrame,
    cost: pd.DataFrame,
    fresh: pd.DataFrame,
    margin_audit: pd.DataFrame,
) -> pd.DataFrame:
    baseline = summary[summary["variant"].eq(BASELINE_VARIANT)].iloc[0]
    stage103 = summary[summary["variant"].eq(STAGE103_VARIANT)].iloc[0]
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
    rows: list[dict[str, Any]] = []
    for _, row in summary.iterrows():
        c = cost[cost["variant"].eq(row["variant"])]
        hard_checks = {
            "total_return_not_lower": _safe_float(row["total_return_pct"]) >= _safe_float(baseline["total_return_pct"]) - 1e-4,
            "max_dd_not_worse": _safe_float(row["max_dd_pct"]) >= _safe_float(baseline["max_dd_pct"]) - 1e-4,
            "max_dd_below_30": _safe_float(row["max_dd_pct"]) >= TARGET_DD_PCT,
            "sharpe_not_lower": _safe_float(row["sharpe"]) >= _safe_float(baseline["sharpe"]) - 1e-4,
            "ulcer_not_higher": _safe_float(row["ulcer_pct"]) <= _safe_float(baseline["ulcer_pct"]) + 1e-4,
            "rolling252_dd30_zero": _safe_float(row["rolling252_dd30_breach_rate"]) == 0.0,
            "rolling504_dd30_zero": _safe_float(row["rolling504_dd30_breach_rate"]) == 0.0,
            "annual_dd30_pass_100": _safe_float(row["annual_cold_start_dd30_pass_rate"]) == 1.0,
            "quarter_dd30_pass_100": _safe_float(row["quarter_cold_start_dd30_pass_rate"]) == 1.0,
            "capital_not_increased": _safe_float(row["capital_used"]) <= s402.ACCOUNT_CAPITAL,
            "cost_stress_not_worse": bool(c["not_worse_than_stage079_stress"].eq(1).all()) if not c.empty else False,
            "fresh_start_dd30_pass": str(row["variant"]) not in fresh_failures,
        }
        incremental_checks = {
            "total_return_not_lower_than_stage103": _safe_float(row["total_return_pct"]) >= _safe_float(stage103["total_return_pct"]) - 1e-4,
            "max_dd_not_worse_than_stage103": _safe_float(row["max_dd_pct"]) >= _safe_float(stage103["max_dd_pct"]) - 1e-4,
            "sharpe_not_lower_than_stage103": _safe_float(row["sharpe"]) >= _safe_float(stage103["sharpe"]) - 1e-4,
            "ulcer_not_higher_than_stage103": _safe_float(row["ulcer_pct"]) <= _safe_float(stage103["ulcer_pct"]) + 1e-4,
        }
        rows.append(
            {
                "variant": row["variant"],
                "label": row["label"],
                **{name: int(flag) for name, flag in hard_checks.items()},
                **{name: int(flag) for name, flag in incremental_checks.items()},
                "metric_hard_pass": int(all(hard_checks.values())),
                "stage103_incremental_core_pass": int(all(incremental_checks.values())),
                "broker10_absolute_no_reject_all_windows": int(str(row["variant"]) not in broker10_failures),
                "fresh_start_failed_windows": fresh_failures.get(str(row["variant"]), ""),
                "broker10_reject_windows": broker10_failures.get(str(row["variant"]), ""),
                "failed_metric_checks": ",".join([name for name, flag in hard_checks.items() if not flag]),
                "failed_stage103_checks": ",".join([name for name, flag in incremental_checks.items() if not flag]),
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
    result["stage103_upgrade_pass"] = (
        result["research_promotion_pass"].eq(1)
        & result["stage103_incremental_core_pass"].eq(1)
        & (result["short_holding_score"] >= float(result.loc[result["variant"].eq(STAGE103_VARIANT), "short_holding_score"].iloc[0]) - 1e-4)
    ).astype(int)
    return result.sort_values(
        ["stage103_upgrade_pass", "research_promotion_pass", "short_holding_score"], ascending=[False, False, False]
    )


def _plot(daily: pd.DataFrame, pair_daily: pd.DataFrame) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(3, 1, figsize=(13, 10), sharex=False)
    full = daily[daily["window_name"].eq("start_2020")]
    for variant, frame in full.groupby("variant"):
        frame = frame.sort_values("date")
        nav = pd.Series(frame["equity"].to_numpy(dtype=float), index=pd.to_datetime(frame["date"])) / s402.ACCOUNT_CAPITAL
        axes[0].plot(nav.index, nav, label=variant, linewidth=1.05)
        axes[1].plot(nav.index, (nav / nav.cummax() - 1.0) * 100.0, label=variant, linewidth=1.0)
    axes[0].set_title("Stage127 pair-spread overlay NAV")
    axes[0].set_ylabel("NAV")
    axes[1].set_title("Drawdown")
    axes[1].set_ylabel("Drawdown %")
    axes[1].axhline(-30.0, color="red", linestyle="--", linewidth=1.0)
    full_pair = pair_daily[pair_daily["window_name"].eq("start_2020")]
    by_variant = full_pair.groupby("variant")["satellite_daily_pnl"].cumsum()
    if not full_pair.empty:
        for variant, frame in full_pair.groupby("variant"):
            frame = frame.sort_values("date")
            axes[2].plot(pd.to_datetime(frame["date"]), frame["satellite_daily_pnl"].cumsum(), label=variant, linewidth=1.0)
    axes[2].set_title("Pair overlay cumulative PnL")
    axes[2].set_ylabel("CNY")
    axes[0].legend(fontsize=8)
    axes[1].legend(fontsize=8)
    axes[2].legend(fontsize=8)
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
        "# Stage127 Stage103产业链价差Overlay审计",
        "",
        f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "- 阶段性质：新低自由度风险源审计；固定 Stage103，不修改 C3、xsmom、Stage079 规则。",
        f"- 固定参数：产业链价差对 `{len(PAIR_SPECS)}` 组，`LOOKBACK_DAYS={LOOKBACK_DAYS}`，`ENTRY_Z={ENTRY_Z}`，`BROKER10_MULTIPLIER={BROKER10_MULTIPLIER}`。",
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
        _md_table(score[["variant", "horizon_days", "experience_score", "score_90d", "score_180d", "short_holding_score", "improved_metric_count"]]),
        "",
        "## 多起点",
        "",
        _md_table(fresh[["window_name", "variant", "total_return_pct", "max_dd_pct", "dd30_pass", "satellite_turnover", "max_satellite_margin", "margin_gate_skipped_days", "broker10_max_margin_to_equity_pct", "broker10_reject_days"]], max_rows=120),
        "",
        "## 保证金压力",
        "",
        _md_table(
            margin_audit[margin_audit["margin_multiplier"].isin([1.00, 1.10])][
                [
                    "window_name",
                    "variant",
                    "margin_multiplier",
                    "max_margin_to_equity_pct",
                    "reject_days_over_100pct",
                    "required_extra_cash_for_no_reject",
                    "first_reject_date",
                ]
            ],
            max_rows=120,
        ),
        "",
        "## 成本压力",
        "",
        _md_table(cost[["variant", "slippage_multiplier", "total_return_pct", "max_dd_pct", "baseline_stage079_max_dd_pct", "not_worse_than_stage079_stress"]]),
        "",
        "## 晋级闸门",
        "",
        _md_table(
            gate[
                [
                    "variant",
                    "metric_hard_pass",
                    "target_pass_3m6m",
                    "research_promotion_pass",
                    "stage103_incremental_core_pass",
                    "stage103_upgrade_pass",
                    "score_90d",
                    "score_180d",
                    "objective_improved_8_count_90d",
                    "objective_improved_8_count_180d",
                    "fresh_start_failed_windows",
                    "broker10_reject_windows",
                    "failed_metric_checks",
                    "failed_stage103_checks",
                ]
            ]
        ),
        "",
        "## 反过拟合说明",
        "",
        "- 本阶段只测预声明产业链价差和两个暴露形态：`best1` 与 `all`。",
        "- 没有按结果扫描 z-score、lookback、单个品种、月份、pair权重或保证金小数。",
        "- 如果不能通过 Stage079 硬闸门和 Stage103 增量闸门，本价差形状停止，不做救参。",
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
    pair_features = _build_pair_features(price_frame)

    satellite_by_window_variant: dict[tuple[str, str], pd.DataFrame] = {}
    daily_by_window_variant: dict[tuple[str, str], pd.DataFrame] = {}
    satellite_full_by_variant: dict[str, pd.DataFrame] = {}
    pair_daily_parts: list[pd.DataFrame] = []
    daily_parts: list[pd.DataFrame] = []
    candidates: list[Any] = []

    for window_name, frame in combo.groupby("window_name", sort=True):
        frame = frame.sort_values("date").drop_duplicates("date", keep="last")
        margin_frame = margin[margin["window_name"].eq(window_name)].sort_values("date").drop_duplicates("date", keep="last")
        baseline_sat = _empty_satellite(window_name)
        xsmom_sat = s403._simulate_guarded_round_half(window_name, frame, margin_frame, price_frame, signals, scale_by_date)
        satellite_by_window_variant[(window_name, BASELINE_VARIANT)] = baseline_sat
        satellite_by_window_variant[(window_name, STAGE103_VARIANT)] = xsmom_sat

        for spec in VARIANTS:
            if spec.variant == BASELINE_VARIANT:
                sat = baseline_sat
            elif spec.variant == STAGE103_VARIANT:
                sat = xsmom_sat
            else:
                pair_sat = _simulate_pair_overlay(
                    window_name,
                    spec.mode,
                    frame,
                    margin_frame,
                    xsmom_sat,
                    price_frame,
                    pair_features,
                )
                if not pair_sat.empty:
                    pair_daily_parts.append(pair_sat.assign(variant=spec.variant))
                sat = _aggregate_satellites(window_name, xsmom_sat, pair_sat)
            satellite_by_window_variant[(window_name, spec.variant)] = sat
            daily = s402._combine_daily(frame, sat, spec.variant, 1.0)
            daily["window_name"] = window_name
            daily_by_window_variant[(window_name, spec.variant)] = daily
            if window_name == "start_2020":
                satellite_full_by_variant[spec.variant] = sat

    for spec in VARIANTS:
        daily = daily_by_window_variant[("start_2020", spec.variant)]
        daily_parts.append(daily)
        equity = s402._calendarize(pd.Series(daily["equity"].to_numpy(dtype=float), index=daily["date"]))
        candidates.append(_candidate(spec, equity))

    daily_all = pd.concat(daily_parts, ignore_index=True)
    pair_daily = pd.concat(pair_daily_parts, ignore_index=True) if pair_daily_parts else pd.DataFrame()
    summary = pd.DataFrame([s402.s087._stats(candidate) for candidate in candidates])
    horizon = pd.DataFrame([s402.s087._horizon_metrics(candidate, days) for candidate in candidates for days in (90, 180)])
    score = s402.s087._score_horizons(horizon)
    margin_audit = _margin_audit(combo, margin, satellite_by_window_variant, daily_by_window_variant)
    fresh = _fresh_start(combo, satellite_by_window_variant, daily_by_window_variant, margin_audit)
    cost = _cost_stress(full, satellite_full_by_variant)
    gate = _gate(summary, horizon, score, cost, fresh, margin_audit)

    stage103_upgrades = gate[gate["stage103_upgrade_pass"].eq(1) & gate["variant"].isin([PAIR_BEST1_VARIANT, PAIR_ALL_VARIANT])]
    research_ready = gate[gate["research_promotion_pass"].eq(1) & gate["variant"].isin([PAIR_BEST1_VARIANT, PAIR_ALL_VARIANT])]
    decision = {
        "stage": "Stage127",
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "decision": "stage103_upgrade_candidate"
        if len(stage103_upgrades)
        else ("stage079_objective_only_candidate" if len(research_ready) else "no_new_promotion"),
        "stage103_upgrade_variants": stage103_upgrades["variant"].tolist(),
        "stage079_objective_ready_variants": research_ready["variant"].tolist(),
        "best_by_gate": str(gate.iloc[0]["variant"]) if not gate.empty else "",
        "chart": str(CHART_PATH),
        "judgement": "产业链价差若不能在固定pair、固定120日z-score和固定一手暴露下通过，不继续扫pair/阈值/窗口救援。",
    }

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    horizon.to_csv(HORIZON_PATH, index=False, encoding="utf-8-sig")
    score.to_csv(SCORE_PATH, index=False, encoding="utf-8-sig")
    fresh.to_csv(FRESH_START_PATH, index=False, encoding="utf-8-sig")
    cost.to_csv(COST_PATH, index=False, encoding="utf-8-sig")
    margin_audit.to_csv(MARGIN_AUDIT_PATH, index=False, encoding="utf-8-sig")
    gate.to_csv(GATE_PATH, index=False, encoding="utf-8-sig")
    daily_all.to_csv(DAILY_PATH, index=False, encoding="utf-8-sig")
    pair_daily.to_csv(PAIR_DAILY_PATH, index=False, encoding="utf-8-sig")
    pair_features.to_csv(FEATURE_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _plot(daily_all, pair_daily)
    _write_report(summary, horizon, score, fresh, cost, margin_audit, gate, decision)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print(f"report={REPORT_PATH}")


if __name__ == "__main__":
    main()
