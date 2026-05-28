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


MODEL_TAG = "stage405_stage079_reversal_protection_scout_v1"
OUTPUT_PREFIX = "qmt_roll_stage405_stage079_reversal_protection_scout"
LINE_ID = "futures_trend_drawdown30_preserve_return"

BASELINE_VARIANT = "stage079"
STAGE103_VARIANT = "xsmom_vt10_q_momq_round_half_true_broker10_guard"
ACCOUNT_CAPITAL = s402.ACCOUNT_CAPITAL
TARGET_DD_PCT = -30.0
BROKER10_MULTIPLIER = 1.10

STAGE404_WINDOW_PATH = (
    OUTPUT_DIR
    / "qmt_roll_stage404_stage079_residual_holding_gap_attribution_window_attribution_stage404_stage079_residual_holding_gap_attribution_v1.csv"
)

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
HORIZON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_horizon_{MODEL_TAG}.csv"
SCORE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_score_{MODEL_TAG}.csv"
FRESH_START_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_fresh_start_{MODEL_TAG}.csv"
COST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cost_stress_{MODEL_TAG}.csv"
MARGIN_AUDIT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_margin_audit_{MODEL_TAG}.csv"
BAD_WINDOW_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_bad_window_contribution_{MODEL_TAG}.csv"
GATE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gate_{MODEL_TAG}.csv"
DAILY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_{MODEL_TAG}.csv"
OVERLAY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_overlay_daily_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"


@dataclass(frozen=True)
class VariantSpec:
    variant: str
    label: str
    role: str
    direction: str
    lookback_days: int
    top_n: int
    rebalance_every: int
    note: str


VARIANTS: tuple[VariantSpec, ...] = (
    VariantSpec(
        BASELINE_VARIANT,
        "A Stage079基准",
        "baseline",
        "none",
        0,
        0,
        0,
        "50万C3下单+11.5万现金。",
    ),
    VariantSpec(
        STAGE103_VARIANT,
        "C0 Stage103 broker10_guard",
        "stage103",
        "none",
        0,
        0,
        0,
        "当前最强执行相对候选，固定xsmom整篮子和10%保证金闸门。",
    ),
    VariantSpec(
        "stage103_plus_rev20_weekly_min1_guard",
        "C1 Stage103+20日横截面反转周频保护",
        "protection_scout",
        "reversal",
        20,
        3,
        5,
        "每5个交易日做一次横截面排序，买近20日弱者、卖近20日强者，各3个品种，每品种1手，并受10%保证金闸门约束。",
    ),
    VariantSpec(
        "stage103_plus_rev60_weekly_min1_guard",
        "C2 Stage103+60日横截面反转周频保护",
        "protection_scout",
        "reversal",
        60,
        3,
        5,
        "每5个交易日做一次横截面排序，买近60日弱者、卖近60日强者，各3个品种，每品种1手，并受10%保证金闸门约束。",
    ),
    VariantSpec(
        "stage103_plus_mom60_weekly_min1_guard",
        "C3 Stage103+60日横截面动量周频对照",
        "positive_control",
        "momentum",
        60,
        3,
        5,
        "每5个交易日做一次横截面排序，买近60日强者、卖近60日弱者，各3个品种，每品种1手，并受10%保证金闸门约束。",
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


def _empty_xsmom(window_name: str) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": pd.Series(dtype="datetime64[ns]"),
            "window_name": pd.Series(dtype=str),
            "satellite_daily_pnl": pd.Series(dtype=float),
            "satellite_slippage_cost": pd.Series(dtype=float),
            "satellite_margin": pd.Series(dtype=float),
            "satellite_turnover_contracts": pd.Series(dtype=float),
            "held_contract_count": pd.Series(dtype=float),
            "stage101_scale": pd.Series(dtype=float),
            "margin_gate_skipped": pd.Series(dtype=float),
        }
    ).assign(window_name=window_name)


def _empty_overlay(window_name: str, variant: str) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": pd.Series(dtype="datetime64[ns]"),
            "window_name": pd.Series(dtype=str),
            "variant": pd.Series(dtype=str),
            "overlay_daily_pnl": pd.Series(dtype=float),
            "overlay_slippage_cost": pd.Series(dtype=float),
            "overlay_margin": pd.Series(dtype=float),
            "overlay_turnover_contracts": pd.Series(dtype=float),
            "overlay_held_contract_count": pd.Series(dtype=float),
            "overlay_desired_product_count": pd.Series(dtype=float),
            "overlay_rebalance": pd.Series(dtype=float),
            "overlay_margin_gate_skipped": pd.Series(dtype=float),
        }
    ).assign(window_name=window_name, variant=variant)


def _candidate(spec: VariantSpec, equity: pd.Series) -> Any:
    return s402.s087.Candidate(
        variant=spec.variant,
        label=spec.label,
        equity=equity,
        capital_used=ACCOUNT_CAPITAL,
        candidate_class=spec.role,
        eligible_for_promotion=spec.role != "positive_control",
        note=spec.note,
    )


def _build_rank_tables(price_frame: pd.DataFrame, lookbacks: set[int]) -> dict[int, pd.DataFrame]:
    returns = (
        price_frame.pivot_table(index="date", columns="product_vt_symbol", values="product_return", aggfunc="last")
        .sort_index()
        .fillna(0.0)
    )
    ranks: dict[int, pd.DataFrame] = {}
    one_plus = 1.0 + returns
    for lookback in sorted(lookbacks):
        if lookback <= 0:
            continue
        ranks[lookback] = one_plus.rolling(lookback, min_periods=lookback).apply(np.prod, raw=True).shift(1) - 1.0
    return ranks


def _select_products(rank_row: pd.Series, price_by_product: dict[str, Any], spec: VariantSpec) -> dict[str, int]:
    if spec.direction == "none":
        return {}
    available: dict[str, float] = {}
    for product, value in rank_row.dropna().items():
        price_row = price_by_product.get(str(product))
        if price_row is None:
            continue
        if s402._safe_float(getattr(price_row, "margin_per_contract", 0.0)) <= 0.0:
            continue
        if s402._safe_float(getattr(price_row, "prev_main_close", 0.0)) <= 0.0:
            continue
        available[str(product)] = float(value)
    if len(available) < spec.top_n * 2:
        return {}
    ordered = sorted(available.items(), key=lambda item: item[1])
    losers = [product for product, _value in ordered[: spec.top_n]]
    winners = [product for product, _value in ordered[-spec.top_n :]]
    if spec.direction == "reversal":
        return {**{product: 1 for product in losers}, **{product: -1 for product in winners}}
    if spec.direction == "momentum":
        return {**{product: -1 for product in losers}, **{product: 1 for product in winners}}
    return {}


def _simulate_overlay(
    spec: VariantSpec,
    window_name: str,
    window_frame: pd.DataFrame,
    margin_frame: pd.DataFrame,
    xsmom_sat: pd.DataFrame,
    price_frame: pd.DataFrame,
    rank_table: pd.DataFrame | None,
) -> pd.DataFrame:
    if spec.direction == "none" or rank_table is None:
        return _empty_overlay(window_name, spec.variant)

    start = window_frame["date"].min()
    end = window_frame["date"].max()
    window_prices = price_frame[price_frame["date"].between(start, end)].copy()
    if window_prices.empty:
        return _empty_overlay(window_name, spec.variant)

    c3_pnl = window_frame.set_index("date")["c3_net_pnl"].astype(float).to_dict()
    c3_margin = margin_frame.set_index("date")["c3_margin"].astype(float).to_dict()
    xsmom_by_date = (
        xsmom_sat.set_index("date")
        if not xsmom_sat.empty
        else pd.DataFrame(columns=["satellite_daily_pnl", "satellite_margin", "satellite_slippage_cost"])
    )
    xsmom_pnl = xsmom_by_date.get("satellite_daily_pnl", pd.Series(dtype=float)).astype(float).to_dict()
    xsmom_margin = xsmom_by_date.get("satellite_margin", pd.Series(dtype=float)).astype(float).to_dict()

    price_by_date_product = {
        (row.date, row.product_vt_symbol): row for row in window_prices.itertuples(index=False)
    }
    date_prices: dict[pd.Timestamp, dict[str, Any]] = {}
    for row in window_prices.itertuples(index=False):
        date_prices.setdefault(pd.Timestamp(row.date).normalize(), {})[str(row.product_vt_symbol)] = row

    prev_contract_positions: dict[str, int] = {}
    prev_contract_product: dict[str, str] = {}
    product_targets: dict[str, int] = {}
    rows: list[dict[str, Any]] = []
    prev_equity = ACCOUNT_CAPITAL
    trading_dates = list(window_frame["date"].sort_values())

    for day_idx, date in enumerate(trading_dates):
        date = pd.Timestamp(date).normalize()
        prices = date_prices.get(date, {})
        rebalance = int(day_idx % spec.rebalance_every == 0)
        if rebalance:
            if date in rank_table.index:
                product_targets = _select_products(rank_table.loc[date], prices, spec)
            else:
                product_targets = {}

        targets: dict[str, int] = {}
        contract_product: dict[str, str] = {}
        proposed_margin = 0.0
        for product, direction in product_targets.items():
            price_row = prices.get(product)
            if price_row is None:
                continue
            contract = str(getattr(price_row, "main_contract_vt", ""))
            margin = s402._safe_float(getattr(price_row, "margin_per_contract", 0.0))
            if not contract or margin <= 0.0:
                continue
            targets[contract] = int(direction)
            contract_product[contract] = product
            proposed_margin += margin

        required_margin = (
            float(c3_margin.get(date, 0.0)) + float(xsmom_margin.get(date, 0.0)) + proposed_margin
        ) * BROKER10_MULTIPLIER
        margin_gate_skipped = int(bool(targets) and required_margin > prev_equity)
        if margin_gate_skipped:
            targets = {}
            contract_product = {}
            proposed_margin = 0.0

        pnl = 0.0
        held_margin = 0.0
        for contract, lots in targets.items():
            product = contract_product.get(contract)
            price_row = price_by_date_product.get((date, product)) if product else None
            if price_row is None:
                continue
            pnl += lots * s402._safe_float(getattr(price_row, "prev_main_close", 0.0)) * s402._safe_float(
                getattr(price_row, "size", 1.0)
            ) * s402._safe_float(getattr(price_row, "product_return", 0.0))
            held_margin += abs(lots) * s402._safe_float(getattr(price_row, "margin_per_contract", 0.0))

        turnover = 0
        slippage_cost = 0.0
        for contract in set(prev_contract_positions) | set(targets):
            delta = abs(targets.get(contract, 0) - prev_contract_positions.get(contract, 0))
            if delta <= 0:
                continue
            turnover += delta
            product = contract_product.get(contract) or prev_contract_product.get(contract)
            price_row = price_by_date_product.get((date, product)) if product else None
            if price_row is not None:
                slippage_cost += delta * s402._safe_float(getattr(price_row, "slippage", 0.0)) * s402._safe_float(
                    getattr(price_row, "size", 1.0)
                )

        overlay_daily_pnl = pnl - slippage_cost
        rows.append(
            {
                "date": date,
                "window_name": window_name,
                "variant": spec.variant,
                "overlay_daily_pnl": overlay_daily_pnl,
                "overlay_slippage_cost": slippage_cost,
                "overlay_margin": held_margin,
                "overlay_turnover_contracts": turnover,
                "overlay_held_contract_count": len(targets),
                "overlay_desired_product_count": len(product_targets),
                "overlay_rebalance": rebalance,
                "overlay_margin_gate_skipped": margin_gate_skipped,
            }
        )
        prev_contract_positions = targets
        prev_contract_product = contract_product
        prev_equity += float(c3_pnl.get(date, 0.0)) + float(xsmom_pnl.get(date, 0.0)) + overlay_daily_pnl

    return pd.DataFrame(rows)


def _combine_daily(
    window_frame: pd.DataFrame,
    xsmom_sat: pd.DataFrame,
    overlay: pd.DataFrame,
    variant: str,
    slippage_multiplier: float = 1.0,
) -> pd.DataFrame:
    merged = window_frame[["date", "window_name", "c3_net_pnl", "c3_trade_count", "c3_slippage"]].copy()
    sat_cols = [
        "date",
        "satellite_daily_pnl",
        "satellite_slippage_cost",
        "satellite_margin",
        "satellite_turnover_contracts",
        "held_contract_count",
        "stage101_scale",
    ]
    if xsmom_sat.empty:
        xsmom_sat = pd.DataFrame(columns=sat_cols)
    for col in sat_cols:
        if col not in xsmom_sat.columns:
            xsmom_sat[col] = 0.0
    overlay_cols = [
        "date",
        "overlay_daily_pnl",
        "overlay_slippage_cost",
        "overlay_margin",
        "overlay_turnover_contracts",
        "overlay_held_contract_count",
        "overlay_margin_gate_skipped",
    ]
    if overlay.empty:
        overlay = pd.DataFrame(columns=overlay_cols)
    for col in overlay_cols:
        if col not in overlay.columns:
            overlay[col] = 0.0
    merged = merged.merge(xsmom_sat[sat_cols], on="date", how="left")
    merged = merged.merge(overlay[overlay_cols], on="date", how="left")
    numeric_cols = [
        "c3_net_pnl",
        "c3_trade_count",
        "c3_slippage",
        "satellite_daily_pnl",
        "satellite_slippage_cost",
        "satellite_margin",
        "satellite_turnover_contracts",
        "held_contract_count",
        "stage101_scale",
        "overlay_daily_pnl",
        "overlay_slippage_cost",
        "overlay_margin",
        "overlay_turnover_contracts",
        "overlay_held_contract_count",
        "overlay_margin_gate_skipped",
    ]
    for col in numeric_cols:
        merged[col] = pd.to_numeric(merged.get(col, 0.0), errors="coerce").fillna(0.0)
    slippage = merged["c3_slippage"] + merged["satellite_slippage_cost"] + merged["overlay_slippage_cost"]
    pnl = (
        merged["c3_net_pnl"]
        + merged["satellite_daily_pnl"]
        + merged["overlay_daily_pnl"]
        - (slippage_multiplier - 1.0) * slippage
    )
    merged["equity"] = s402.FUTURES_CAPITAL + pnl.cumsum() + s402.STAGE079_CASH
    merged["variant"] = variant
    merged["trade_count"] = (
        merged["c3_trade_count"] + merged["satellite_turnover_contracts"] + merged["overlay_turnover_contracts"]
    )
    merged["combo_slippage"] = slippage
    merged["total_margin"] = merged["satellite_margin"] + merged["overlay_margin"]
    return merged


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
    xsmom_by_window: dict[str, pd.DataFrame],
    overlay_by_window_variant: dict[tuple[str, str], pd.DataFrame],
    daily_by_window_variant: dict[tuple[str, str], pd.DataFrame],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for window_name, m in margin.groupby("window_name", sort=True):
        m = m.sort_values("date").drop_duplicates("date", keep="last")
        xsmom = xsmom_by_window.get(window_name, _empty_xsmom(window_name))
        xsmom_margin = (
            xsmom.set_index("date")["satellite_margin"].astype(float)
            if not xsmom.empty and "satellite_margin" in xsmom.columns
            else pd.Series(dtype=float)
        )
        for spec in VARIANTS:
            overlay = overlay_by_window_variant.get((window_name, spec.variant), _empty_overlay(window_name, spec.variant))
            overlay_margin = (
                overlay.set_index("date")["overlay_margin"].astype(float)
                if not overlay.empty and "overlay_margin" in overlay.columns
                else pd.Series(dtype=float)
            )
            daily = daily_by_window_variant.get((window_name, spec.variant))
            if daily is None or daily.empty:
                frame = combo[combo["window_name"].eq(window_name)].sort_values("date").drop_duplicates("date", keep="last")
                daily = _combine_daily(
                    frame,
                    _empty_xsmom(window_name) if spec.variant == BASELINE_VARIANT else xsmom,
                    overlay,
                    spec.variant,
                    1.0,
                )
            equity = pd.Series(daily["equity"].to_numpy(dtype=float), index=daily["date"])
            if spec.variant == BASELINE_VARIANT:
                total_margin = m["c3_margin"].to_numpy(dtype=float)
            else:
                total_margin = (
                    m["c3_margin"].to_numpy(dtype=float)
                    + xsmom_margin.reindex(m["date"]).fillna(0.0).to_numpy(dtype=float)
                    + overlay_margin.reindex(m["date"]).fillna(0.0).to_numpy(dtype=float)
                )
            equity_on_margin_dates = equity.reindex(m["date"]).ffill().to_numpy(dtype=float)
            for multiplier in (1.00, 1.02, 1.05, 1.10):
                stressed_margin = total_margin * multiplier
                margin_to_equity = stressed_margin / equity_on_margin_dates * 100.0
                over_100 = margin_to_equity > 100.0
                overage = np.maximum(stressed_margin - equity_on_margin_dates, 0.0)
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
                        "required_extra_cash_for_no_reject": float(np.nanmax(overage)) if len(overage) else 0.0,
                        "first_reject_date": str(pd.Timestamp(m.loc[over_100, "date"].iloc[0]).date())
                        if bool(np.any(over_100))
                        else "",
                    }
                )
    return pd.DataFrame(rows)


def _fresh_start(
    combo: pd.DataFrame,
    xsmom_by_window: dict[str, pd.DataFrame],
    overlay_by_window_variant: dict[tuple[str, str], pd.DataFrame],
    daily_by_window_variant: dict[tuple[str, str], pd.DataFrame],
    margin_audit: pd.DataFrame,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    broker10 = margin_audit[margin_audit["margin_multiplier"].eq(BROKER10_MULTIPLIER)].set_index(
        ["window_name", "variant"]
    )
    for window_name, frame in combo.groupby("window_name", sort=True):
        frame = frame.sort_values("date").drop_duplicates("date", keep="last")
        for spec in VARIANTS:
            xsmom = _empty_xsmom(window_name) if spec.variant == BASELINE_VARIANT else xsmom_by_window.get(
                window_name, _empty_xsmom(window_name)
            )
            overlay = overlay_by_window_variant.get((window_name, spec.variant), _empty_overlay(window_name, spec.variant))
            daily = daily_by_window_variant.get((window_name, spec.variant))
            if daily is None or daily.empty:
                daily = _combine_daily(frame, xsmom, overlay, spec.variant, 1.0)
            equity = pd.Series(daily["equity"].to_numpy(dtype=float), index=daily["date"])
            nav = equity / ACCOUNT_CAPITAL
            max_dd = s402.s087._max_drawdown(nav)
            audit_row = broker10.loc[(window_name, spec.variant)] if (window_name, spec.variant) in broker10.index else None
            rows.append(
                {
                    "window_name": window_name,
                    "variant": spec.variant,
                    "label": spec.label,
                    "end_equity": float(equity.iloc[-1]),
                    "total_return_pct": float((nav.iloc[-1] - 1.0) * 100.0),
                    "max_dd_pct": max_dd,
                    "dd30_pass": int(max_dd >= TARGET_DD_PCT),
                    "xsmom_slippage": float(xsmom["satellite_slippage_cost"].sum()) if not xsmom.empty else 0.0,
                    "overlay_slippage": float(overlay["overlay_slippage_cost"].sum()) if not overlay.empty else 0.0,
                    "overlay_turnover": float(overlay["overlay_turnover_contracts"].sum()) if not overlay.empty else 0.0,
                    "max_overlay_margin": float(overlay["overlay_margin"].max()) if not overlay.empty else 0.0,
                    "overlay_gate_skipped_days": int(overlay.get("overlay_margin_gate_skipped", pd.Series(dtype=float)).sum())
                    if not overlay.empty
                    else 0,
                    "broker10_max_margin_to_equity_pct": float(audit_row["max_margin_to_equity_pct"])
                    if audit_row is not None
                    else 0.0,
                    "broker10_reject_days": int(audit_row["reject_days_over_100pct"]) if audit_row is not None else 0,
                }
            )
    return pd.DataFrame(rows)


def _cost_stress(
    full_frame: pd.DataFrame,
    xsmom_full: pd.DataFrame,
    overlay_full_by_variant: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    stage079_dd: dict[float, float] = {}
    stage103_dd: dict[float, float] = {}
    for multiplier in (1.0, 2.0, 3.0, 5.0):
        for spec in VARIANTS:
            xsmom = _empty_xsmom("start_2020") if spec.variant == BASELINE_VARIANT else xsmom_full
            overlay = overlay_full_by_variant.get(spec.variant, _empty_overlay("start_2020", spec.variant))
            daily = _combine_daily(full_frame, xsmom, overlay, spec.variant, multiplier)
            equity = s402._calendarize(pd.Series(daily["equity"].to_numpy(dtype=float), index=daily["date"]))
            nav = equity / ACCOUNT_CAPITAL
            max_dd = s402.s087._max_drawdown(nav)
            if spec.variant == BASELINE_VARIANT:
                stage079_dd[multiplier] = max_dd
            if spec.variant == STAGE103_VARIANT:
                stage103_dd[multiplier] = max_dd
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
    result["stage079_max_dd_pct"] = result["slippage_multiplier"].map(stage079_dd)
    result["stage103_max_dd_pct"] = result["slippage_multiplier"].map(stage103_dd)
    result["not_worse_than_stage079_stress"] = (result["max_dd_pct"] >= result["stage079_max_dd_pct"] - 1e-9).astype(int)
    result["not_worse_than_stage103_stress"] = (result["max_dd_pct"] >= result["stage103_max_dd_pct"] - 1e-9).astype(int)
    return result


def _calendarize_daily(daily: pd.DataFrame) -> pd.DataFrame:
    raw = daily.sort_values("date").drop_duplicates("date", keep="last")
    calendar = pd.DataFrame({"date": pd.date_range(raw["date"].min(), raw["date"].max(), freq="D")})
    merged = calendar.merge(raw, on="date", how="left")
    merged["equity"] = merged["equity"].ffill()
    for col in [
        "c3_net_pnl",
        "satellite_daily_pnl",
        "overlay_daily_pnl",
        "overlay_slippage_cost",
        "overlay_turnover_contracts",
        "overlay_held_contract_count",
        "overlay_margin_gate_skipped",
        "combo_slippage",
    ]:
        merged[col] = pd.to_numeric(merged.get(col, 0.0), errors="coerce").fillna(0.0)
    return merged


def _bad_window_contribution(daily_by_variant: dict[str, pd.DataFrame]) -> pd.DataFrame:
    if not STAGE404_WINDOW_PATH.exists():
        return pd.DataFrame()
    windows = pd.read_csv(STAGE404_WINDOW_PATH, encoding="utf-8-sig")
    windows["start_date"] = pd.to_datetime(windows["start_date"], errors="coerce").dt.normalize()
    windows["end_date"] = pd.to_datetime(windows["end_date"], errors="coerce").dt.normalize()
    windows = windows[windows["return_bottom5_group"].eq(1)].dropna(subset=["start_date", "end_date"])
    stage103 = _calendarize_daily(daily_by_variant[STAGE103_VARIANT]).set_index("date")
    rows: list[dict[str, Any]] = []
    for spec in VARIANTS:
        if spec.variant in {BASELINE_VARIANT, STAGE103_VARIANT}:
            continue
        candidate = _calendarize_daily(daily_by_variant[spec.variant]).set_index("date")
        for horizon_days, group in windows.groupby("horizon_days", sort=True):
            diffs: list[float] = []
            overlay_pnls: list[float] = []
            active_rates: list[float] = []
            gate_days: list[float] = []
            for row in group.itertuples(index=False):
                start = pd.Timestamp(row.start_date).normalize()
                end = pd.Timestamp(row.end_date).normalize()
                if start not in candidate.index or end not in candidate.index or start not in stage103.index or end not in stage103.index:
                    continue
                c_ret = (float(candidate.loc[end, "equity"]) / float(candidate.loc[start, "equity"]) - 1.0) * 100.0
                b_ret = (float(stage103.loc[end, "equity"]) / float(stage103.loc[start, "equity"]) - 1.0) * 100.0
                seg = candidate.loc[start:end]
                diffs.append(c_ret - b_ret)
                overlay_pnls.append(float(seg["overlay_daily_pnl"].sum()))
                active_rates.append(float((seg["overlay_held_contract_count"] > 0).mean()))
                gate_days.append(float(seg["overlay_margin_gate_skipped"].sum()))
            rows.append(
                {
                    "variant": spec.variant,
                    "label": spec.label,
                    "horizon_days": int(horizon_days),
                    "bad_window_count": int(len(diffs)),
                    "avg_return_vs_stage103_pp": float(np.mean(diffs)) if diffs else np.nan,
                    "median_return_vs_stage103_pp": float(np.median(diffs)) if diffs else np.nan,
                    "avg_overlay_pnl": float(np.mean(overlay_pnls)) if overlay_pnls else np.nan,
                    "median_overlay_pnl": float(np.median(overlay_pnls)) if overlay_pnls else np.nan,
                    "avg_overlay_active_rate": float(np.mean(active_rates)) if active_rates else np.nan,
                    "avg_overlay_gate_days": float(np.mean(gate_days)) if gate_days else np.nan,
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
    bad_windows: pd.DataFrame,
) -> pd.DataFrame:
    baseline = summary[summary["variant"].eq(BASELINE_VARIANT)].iloc[0]
    stage103 = summary[summary["variant"].eq(STAGE103_VARIANT)].iloc[0]
    objective = _objective_improved_counts(horizon)
    objective_p = objective.pivot(
        index=["variant", "label"], columns="horizon_days", values="objective_improved_8_count"
    ).reset_index()
    objective_p.columns = ["variant", "label", "objective_improved_8_count_90d", "objective_improved_8_count_180d"]
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
    stage079_broker10 = broker10[broker10["variant"].eq(BASELINE_VARIANT)].set_index("window_name")
    stage103_broker10 = broker10[broker10["variant"].eq(STAGE103_VARIANT)].set_index("window_name")
    relative_fail_079: dict[str, str] = {}
    relative_fail_103: dict[str, str] = {}
    for variant, frame in broker10.groupby("variant", sort=True):
        if variant == BASELINE_VARIANT:
            continue
        fail079: list[str] = []
        fail103: list[str] = []
        for row in frame.itertuples(index=False):
            for base_index, fail_list in ((stage079_broker10, fail079), (stage103_broker10, fail103)):
                if row.window_name not in base_index.index:
                    continue
                base = base_index.loc[row.window_name]
                baseline_has_reject = int(base["reject_days_over_100pct"]) > 0
                candidate_has_reject = int(row.reject_days_over_100pct) > 0
                if baseline_has_reject:
                    worse = (
                        int(row.reject_days_over_100pct) > int(base["reject_days_over_100pct"])
                        or float(row.required_extra_cash_for_no_reject) > float(base.required_extra_cash_for_no_reject) + 1e-9
                    )
                else:
                    worse = candidate_has_reject
                if worse:
                    fail_list.append(str(row.window_name))
        if fail079:
            relative_fail_079[variant] = ",".join(sorted(set(fail079)))
        if fail103:
            relative_fail_103[variant] = ",".join(sorted(set(fail103)))

    bad_p = pd.DataFrame()
    if not bad_windows.empty:
        bad_p = bad_windows.pivot(index=["variant", "label"], columns="horizon_days", values="avg_return_vs_stage103_pp").reset_index()
        bad_p.columns = ["variant", "label"] + [f"bad_window_avg_vs_stage103_{int(c)}d_pp" for c in bad_p.columns[2:]]

    rows: list[dict[str, Any]] = []
    for _, row in summary.iterrows():
        c = cost[cost["variant"].eq(row["variant"])]
        checks = {
            "total_return_not_lower_than_stage079": _safe_metric(row["total_return_pct"]) >= _safe_metric(
                baseline["total_return_pct"]
            )
            - 1e-4,
            "max_dd_not_worse_than_stage079": _safe_metric(row["max_dd_pct"]) >= _safe_metric(baseline["max_dd_pct"]) - 1e-4,
            "max_dd_below_30": _safe_metric(row["max_dd_pct"]) >= TARGET_DD_PCT,
            "sharpe_not_lower_than_stage079": _safe_metric(row["sharpe"]) >= _safe_metric(baseline["sharpe"]) - 1e-4,
            "ulcer_not_higher_than_stage079": _safe_metric(row["ulcer_pct"]) <= _safe_metric(baseline["ulcer_pct"]) + 1e-4,
            "rolling252_dd30_zero": _safe_metric(row["rolling252_dd30_breach_rate"]) == 0.0,
            "rolling504_dd30_zero": _safe_metric(row["rolling504_dd30_breach_rate"]) == 0.0,
            "annual_dd30_pass_100": _safe_metric(row["annual_cold_start_dd30_pass_rate"]) == 1.0,
            "quarter_dd30_pass_100": _safe_metric(row["quarter_cold_start_dd30_pass_rate"]) == 1.0,
            "capital_not_increased": _safe_metric(row["capital_used"]) <= ACCOUNT_CAPITAL,
            "cost_stress_not_worse_than_stage079": bool(c["not_worse_than_stage079_stress"].eq(1).all()) if not c.empty else False,
            "fresh_start_dd30_pass": str(row["variant"]) not in fresh_failures,
        }
        incremental_checks = {
            "total_return_not_lower_than_stage103": _safe_metric(row["total_return_pct"]) >= _safe_metric(
                stage103["total_return_pct"]
            )
            - 1e-4,
            "max_dd_not_worse_than_stage103": _safe_metric(row["max_dd_pct"]) >= _safe_metric(stage103["max_dd_pct"]) - 1e-4,
            "sharpe_not_lower_than_stage103": _safe_metric(row["sharpe"]) >= _safe_metric(stage103["sharpe"]) - 1e-4,
            "ulcer_not_higher_than_stage103": _safe_metric(row["ulcer_pct"]) <= _safe_metric(stage103["ulcer_pct"]) + 1e-4,
            "cost_stress_not_worse_than_stage103": bool(c["not_worse_than_stage103_stress"].eq(1).all())
            if not c.empty
            else False,
        }
        rows.append(
            {
                "variant": row["variant"],
                "label": row["label"],
                **{key: int(value) for key, value in checks.items()},
                **{key: int(value) for key, value in incremental_checks.items()},
                "metric_hard_pass_stage079": int(all(checks.values())),
                "metric_incremental_pass_stage103": int(all(incremental_checks.values())),
                "broker10_absolute_no_reject_all_windows": int(str(row["variant"]) not in broker10_failures),
                "broker10_not_worse_than_stage079_all_windows": int(
                    row["variant"] == BASELINE_VARIANT or str(row["variant"]) not in relative_fail_079
                ),
                "broker10_not_worse_than_stage103_all_windows": int(
                    row["variant"] in {BASELINE_VARIANT, STAGE103_VARIANT} or str(row["variant"]) not in relative_fail_103
                ),
                "fresh_start_failed_windows": fresh_failures.get(str(row["variant"]), ""),
                "broker10_reject_windows": broker10_failures.get(str(row["variant"]), ""),
                "broker10_relative_worse_than_stage079_windows": relative_fail_079.get(str(row["variant"]), ""),
                "broker10_relative_worse_than_stage103_windows": relative_fail_103.get(str(row["variant"]), ""),
                "failed_stage079_metric_checks": ",".join([key for key, value in checks.items() if not value]),
                "failed_stage103_incremental_checks": ",".join(
                    [key for key, value in incremental_checks.items() if not value]
                ),
            }
        )
    result = pd.DataFrame(rows).merge(score_one, on=["variant", "label"], how="left").merge(
        objective_p, on=["variant", "label"], how="left"
    )
    if not bad_p.empty:
        result = result.merge(bad_p, on=["variant", "label"], how="left")
    for col in ["bad_window_avg_vs_stage103_90d_pp", "bad_window_avg_vs_stage103_180d_pp"]:
        if col not in result.columns:
            result[col] = np.nan
    stage103_score = result[result["variant"].eq(STAGE103_VARIANT)].iloc[0]
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
    result["short_score_not_lower_than_stage103"] = (
        result["short_holding_score"] >= _safe_metric(stage103_score["short_holding_score"]) - 1e-4
    ).astype(int)
    result["bad_window_not_worse_than_stage103"] = (
        result["bad_window_avg_vs_stage103_90d_pp"].fillna(0.0).ge(-1e-9)
        & result["bad_window_avg_vs_stage103_180d_pp"].fillna(0.0).ge(-1e-9)
    ).astype(int)
    result["research_promotion_pass"] = (
        result["metric_hard_pass_stage079"].eq(1)
        & result["target_pass_3m6m_vs_stage079"].eq(1)
        & result["metric_incremental_pass_stage103"].eq(1)
        & result["short_score_not_lower_than_stage103"].eq(1)
        & result["bad_window_not_worse_than_stage103"].eq(1)
    ).astype(int)
    result["execution_relative_pass"] = (
        result["research_promotion_pass"].eq(1)
        & result["broker10_not_worse_than_stage079_all_windows"].eq(1)
        & result["broker10_not_worse_than_stage103_all_windows"].eq(1)
    ).astype(int)
    result["deployment_absolute_margin_pass"] = (
        result["research_promotion_pass"].eq(1) & result["broker10_absolute_no_reject_all_windows"].eq(1)
    ).astype(int)
    return result.sort_values(
        ["execution_relative_pass", "research_promotion_pass", "short_holding_score", "total_return_not_lower_than_stage103"],
        ascending=[False, False, False, False],
    )


def _plot(daily: pd.DataFrame, horizon: pd.DataFrame, bad_windows: pd.DataFrame, gate: pd.DataFrame) -> None:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception as exc:  # pragma: no cover
        print(f"[stage405] skip chart: {exc}", flush=True)
        return

    full = daily[daily["window_name"].eq("start_2020")].copy()
    fig, axes = plt.subplots(2, 2, figsize=(15, 10))
    colors = {
        BASELINE_VARIANT: "#666666",
        STAGE103_VARIANT: "#1f77b4",
        "stage103_plus_rev20_weekly_min1_guard": "#d62728",
        "stage103_plus_rev60_weekly_min1_guard": "#ff7f0e",
        "stage103_plus_mom60_weekly_min1_guard": "#2ca02c",
    }
    for variant, frame in full.groupby("variant", sort=False):
        frame = frame.sort_values("date")
        nav = pd.Series(frame["equity"].to_numpy(dtype=float), index=pd.to_datetime(frame["date"])) / ACCOUNT_CAPITAL
        axes[0, 0].plot(nav.index, nav, label=variant, linewidth=1.1, color=colors.get(variant))
        axes[1, 0].plot(nav.index, (nav / nav.cummax() - 1.0) * 100.0, label=variant, linewidth=1.0, color=colors.get(variant))
    axes[0, 0].set_title("Full-period NAV")
    axes[0, 0].set_ylabel("NAV")
    axes[0, 0].legend(fontsize=7)
    axes[1, 0].set_title("Drawdown")
    axes[1, 0].set_ylabel("Drawdown %")
    axes[1, 0].axhline(-30.0, color="red", linestyle="--", linewidth=1.0)
    axes[1, 0].legend(fontsize=7)

    h = horizon[horizon["horizon_days"].isin([90, 180])]
    x = np.arange(len(VARIANTS))
    width = 0.36
    labels = [spec.variant.replace("stage103_plus_", "+").replace("_weekly_min1_guard", "") for spec in VARIANTS]
    p05_90 = h[h["horizon_days"].eq(90)].set_index("variant").reindex([spec.variant for spec in VARIANTS])[
        "return_p05_pct"
    ]
    p05_180 = h[h["horizon_days"].eq(180)].set_index("variant").reindex([spec.variant for spec in VARIANTS])[
        "return_p05_pct"
    ]
    axes[0, 1].bar(x - width / 2, p05_90.to_numpy(dtype=float), width, label="90d p05", color="#9ecae1")
    axes[0, 1].bar(x + width / 2, p05_180.to_numpy(dtype=float), width, label="180d p05", color="#fdae6b")
    axes[0, 1].axhline(0.0, color="#333333", linewidth=0.8)
    axes[0, 1].set_title("Forward holding return left tail")
    axes[0, 1].set_ylabel("Return p05 %")
    axes[0, 1].set_xticks(x)
    axes[0, 1].set_xticklabels(labels, rotation=25, ha="right", fontsize=7)
    axes[0, 1].legend(fontsize=8)

    bad = bad_windows.copy()
    if not bad.empty:
        bad = bad[bad["horizon_days"].isin([90, 180])]
        variants = [spec.variant for spec in VARIANTS if spec.variant not in {BASELINE_VARIANT, STAGE103_VARIANT}]
        bx = np.arange(len(variants))
        b90 = bad[bad["horizon_days"].eq(90)].set_index("variant").reindex(variants)["avg_return_vs_stage103_pp"]
        b180 = bad[bad["horizon_days"].eq(180)].set_index("variant").reindex(variants)["avg_return_vs_stage103_pp"]
        axes[1, 1].bar(bx - width / 2, b90.to_numpy(dtype=float), width, label="90d bottom5 vs Stage103", color="#c7e9c0")
        axes[1, 1].bar(bx + width / 2, b180.to_numpy(dtype=float), width, label="180d bottom5 vs Stage103", color="#fdd0a2")
        axes[1, 1].axhline(0.0, color="#333333", linewidth=0.8)
        axes[1, 1].set_xticks(bx)
        axes[1, 1].set_xticklabels(
            [v.replace("stage103_plus_", "+").replace("_weekly_min1_guard", "") for v in variants],
            rotation=25,
            ha="right",
            fontsize=7,
        )
        axes[1, 1].set_ylabel("Return diff pp")
        axes[1, 1].set_title("Stage104 bottom-5% window contribution")
        axes[1, 1].legend(fontsize=8)
    else:
        axes[1, 1].axis("off")
        axes[1, 1].text(0.5, 0.5, "No bad-window file", ha="center", va="center")
    fig.suptitle("Stage105 reversal/momentum protection scout", fontsize=14)
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
    bad_windows: pd.DataFrame,
    gate: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    report = [
        "# Stage105 Stage079反转保护源Scout",
        "",
        f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "- 阶段性质：结构性保护源scout；不修改正式交易入口，不扫描小参数。",
        "- A/B/C：A=Stage079；C0=Stage103 broker10_guard；C1=20日横截面反转；C2=60日横截面反转；C3=60日横截面动量对照。",
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
        "## 体验评分",
        "",
        _md_table(score[["variant", "horizon_days", "experience_score", "score_90d", "score_180d", "short_holding_score"]]),
        "",
        "## Stage104底部5%坏窗口贡献",
        "",
        _md_table(bad_windows),
        "",
        "## 多起点与10%保证金缓冲",
        "",
        _md_table(
            fresh[
                [
                    "window_name",
                    "variant",
                    "total_return_pct",
                    "max_dd_pct",
                    "dd30_pass",
                    "overlay_turnover",
                    "overlay_gate_skipped_days",
                    "broker10_max_margin_to_equity_pct",
                    "broker10_reject_days",
                ]
            ],
            max_rows=90,
        ),
        "",
        "## 成本压力",
        "",
        _md_table(
            cost[
                [
                    "variant",
                    "slippage_multiplier",
                    "total_return_pct",
                    "max_dd_pct",
                    "stage079_max_dd_pct",
                    "stage103_max_dd_pct",
                    "not_worse_than_stage079_stress",
                    "not_worse_than_stage103_stress",
                ]
            ]
        ),
        "",
        "## 晋级闸门",
        "",
        _md_table(
            gate[
                [
                    "variant",
                    "metric_hard_pass_stage079",
                    "metric_incremental_pass_stage103",
                    "target_pass_3m6m_vs_stage079",
                    "short_score_not_lower_than_stage103",
                    "bad_window_not_worse_than_stage103",
                    "research_promotion_pass",
                    "execution_relative_pass",
                    "deployment_absolute_margin_pass",
                    "score_90d",
                    "score_180d",
                    "objective_improved_8_count_90d",
                    "objective_improved_8_count_180d",
                    "failed_stage079_metric_checks",
                    "failed_stage103_incremental_checks",
                ]
            ]
        ),
        "",
        "## 反过拟合说明",
        "",
        "- 本阶段只测试三个预声明结构：20日反转、60日反转、60日动量对照；不根据坏窗口调月份、品种、阈值或相邻lookback。",
        "- 反转源若只能改善少数坏窗口但恶化全周期、成本或保证金，则不晋级。",
        "- 动量对照不是为了替代Stage103，而是用于检验文献里商品期货动量比简单反转更稳定这一先验是否在本地数据里成立。",
    ]
    REPORT_PATH.write_text("\n".join(report) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    combo = s402._load_combo_daily()
    margin = s402._load_margin()
    full_frame = combo[combo["window_name"].eq("start_2020")].sort_values("date").drop_duplicates("date", keep="last")
    scale_by_date = s402._build_stage101_scale(full_frame)
    price_frame = s402._build_price_frame()
    price_frame["date"] = pd.to_datetime(price_frame["date"], errors="coerce").dt.normalize()
    ranks = _build_rank_tables(price_frame, {spec.lookback_days for spec in VARIANTS if spec.lookback_days > 0})
    signals = s402._load_signal_daily()
    signals["date"] = pd.to_datetime(signals["date"], errors="coerce").dt.normalize()

    xsmom_by_window: dict[str, pd.DataFrame] = {}
    overlay_by_window_variant: dict[tuple[str, str], pd.DataFrame] = {}
    daily_by_window_variant: dict[tuple[str, str], pd.DataFrame] = {}
    overlay_full_by_variant: dict[str, pd.DataFrame] = {}
    candidates: list[Any] = []
    full_daily_parts: list[pd.DataFrame] = []

    for window_name, frame in combo.groupby("window_name", sort=True):
        frame = frame.sort_values("date").drop_duplicates("date", keep="last")
        margin_frame = margin[margin["window_name"].eq(window_name)].sort_values("date").drop_duplicates("date", keep="last")
        xsmom = s403._simulate_guarded_round_half(window_name, frame, margin_frame, price_frame, signals, scale_by_date)
        xsmom_by_window[window_name] = xsmom
        for spec in VARIANTS:
            if spec.variant in {BASELINE_VARIANT, STAGE103_VARIANT}:
                overlay = _empty_overlay(window_name, spec.variant)
            else:
                overlay = _simulate_overlay(spec, window_name, frame, margin_frame, xsmom, price_frame, ranks[spec.lookback_days])
            overlay_by_window_variant[(window_name, spec.variant)] = overlay
            use_xsmom = _empty_xsmom(window_name) if spec.variant == BASELINE_VARIANT else xsmom
            daily = _combine_daily(frame, use_xsmom, overlay, spec.variant, 1.0)
            daily["window_name"] = window_name
            daily_by_window_variant[(window_name, spec.variant)] = daily
            if window_name == "start_2020":
                overlay_full_by_variant[spec.variant] = overlay

    for spec in VARIANTS:
        daily = daily_by_window_variant[("start_2020", spec.variant)]
        full_daily_parts.append(daily)
        equity = s402._calendarize(pd.Series(daily["equity"].to_numpy(dtype=float), index=daily["date"]))
        candidates.append(_candidate(spec, equity))

    full_daily = pd.concat(full_daily_parts, ignore_index=True)
    overlay_all = pd.concat(
        [frame for frame in overlay_by_window_variant.values() if not frame.empty],
        ignore_index=True,
    )
    summary = pd.DataFrame([s402.s087._stats(candidate) for candidate in candidates])
    horizon = pd.DataFrame([s402.s087._horizon_metrics(candidate, days) for candidate in candidates for days in (90, 180)])
    score = s402.s087._score_horizons(horizon)
    margin_audit = _margin_audit(combo, margin, xsmom_by_window, overlay_by_window_variant, daily_by_window_variant)
    fresh = _fresh_start(combo, xsmom_by_window, overlay_by_window_variant, daily_by_window_variant, margin_audit)
    cost = _cost_stress(full_frame, xsmom_by_window["start_2020"], overlay_full_by_variant)
    bad_windows = _bad_window_contribution(
        {spec.variant: daily_by_window_variant[("start_2020", spec.variant)] for spec in VARIANTS}
    )
    gate = _gate(summary, horizon, score, cost, fresh, margin_audit, bad_windows)

    execution_ready = gate[gate["execution_relative_pass"].eq(1) & ~gate["variant"].isin([BASELINE_VARIANT, STAGE103_VARIANT])]
    research_ready = gate[gate["research_promotion_pass"].eq(1) & ~gate["variant"].isin([BASELINE_VARIANT, STAGE103_VARIANT])]
    best = gate.iloc[0] if not gate.empty else None
    decision = {
        "stage": "Stage105",
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "decision": "execution_relative_candidate"
        if len(execution_ready)
        else ("research_candidate_only" if len(research_ready) else "no_new_promotion"),
        "execution_relative_ready_variants": execution_ready["variant"].tolist(),
        "research_ready_variants": research_ready["variant"].tolist(),
        "best_by_gate_order": str(best["variant"]) if best is not None else "",
        "chart": str(CHART_PATH),
        "judgement": "若保护源未同时通过Stage079硬闸门、Stage103增量不劣化、底部5%坏窗口贡献和保证金/成本约束，则不晋级。",
    }

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    horizon.to_csv(HORIZON_PATH, index=False, encoding="utf-8-sig")
    score.to_csv(SCORE_PATH, index=False, encoding="utf-8-sig")
    fresh.to_csv(FRESH_START_PATH, index=False, encoding="utf-8-sig")
    cost.to_csv(COST_PATH, index=False, encoding="utf-8-sig")
    margin_audit.to_csv(MARGIN_AUDIT_PATH, index=False, encoding="utf-8-sig")
    bad_windows.to_csv(BAD_WINDOW_PATH, index=False, encoding="utf-8-sig")
    gate.to_csv(GATE_PATH, index=False, encoding="utf-8-sig")
    full_daily.to_csv(DAILY_PATH, index=False, encoding="utf-8-sig")
    overlay_all.to_csv(OVERLAY_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _plot(full_daily, horizon, bad_windows, gate)
    _write_report(summary, horizon, score, fresh, cost, margin_audit, bad_windows, gate, decision)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print(f"report={REPORT_PATH}")


if __name__ == "__main__":
    main()
