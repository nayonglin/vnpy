from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from analyze_qmt_roll_stage324_true_combo_capital_margin import _to_builtin, _to_markdown_table
from analyze_qmt_roll_stage345_cross_sectional_momentum_satellite import (
    PRODUCT_RETURN_PATH,
    SATELLITE_DAILY_PATH,
    _path_metrics,
)
from qmt_universe import END_DT, MARGIN_RATIOS, SIZES, SLIPPAGES, START_DT
from run_qmt_alignment_backtest import OUTPUT_DIR


MODEL_TAG = "stage346_xsmom_integer_feasibility_v1"
OUTPUT_PREFIX = "qmt_roll_stage346_xsmom_integer_feasibility"

C3_DAILY_PATH = (
    OUTPUT_DIR
    / "qmt_roll_stage336_c3_cash_reserve_multiperiod_daily_"
    "stage336_c3_cash_reserve_multiperiod_v1.csv"
)
C3_PROFILE = "c3_active100_cash0"
TOTAL_CAPITAL = 500_000.0
SATELLITE_CAPITAL = 37_500.0
SPEC_NAME = "mom_12m_skip1m"
COST_BPS = 20.0

DAILY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_{MODEL_TAG}.csv"
SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


@dataclass(frozen=True)
class Profile:
    name: str
    label: str
    mode: str
    margin_cap: float | None


PROFILES: tuple[Profile, ...] = (
    Profile(
        "floor_margin_per_leg_37p5k",
        "每腿保证金向下取整，卫星资金3.75万",
        "floor_per_leg",
        SATELLITE_CAPITAL,
    ),
    Profile(
        "min1_cheapest_within_37p5k",
        "每个方向优先保留低保证金1手，总保证金不超3.75万",
        "min1_cheapest_cap",
        SATELLITE_CAPITAL,
    ),
    Profile(
        "min1_all_no_cap",
        "全部信号至少1手，不设卫星保证金上限",
        "min1_all",
        None,
    ),
)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if pd.isna(result) or math.isinf(result):
        return default
    return result


def _row_get(row: Any, field: str, default: Any = None) -> Any:
    if isinstance(row, pd.Series):
        return row.get(field, default)
    return getattr(row, field, default)


def _load_c3_daily() -> pd.DataFrame:
    frame = pd.read_csv(C3_DAILY_PATH, encoding="utf-8-sig")
    frame = frame[frame["profile"].eq(C3_PROFILE) & frame["window_name"].eq("start_2020")].copy()
    frame["date"] = pd.to_datetime(frame["date"]).dt.normalize()
    frame["balance"] = pd.to_numeric(frame["balance"], errors="coerce").ffill().fillna(TOTAL_CAPITAL)
    return frame[["date", "balance"]].rename(columns={"balance": "c3_balance"})


def _product_from_vt(product_vt_symbol: str) -> str:
    return product_vt_symbol


def _build_price_frame() -> pd.DataFrame:
    product_returns = pd.read_csv(PRODUCT_RETURN_PATH, encoding="utf-8-sig")
    product_returns["date"] = pd.to_datetime(product_returns["date"]).dt.normalize()
    product_returns = product_returns[["date", "product_vt_symbol", "main_contract_vt", "main_close", "product_return"]].copy()
    product_returns["main_close"] = pd.to_numeric(product_returns["main_close"], errors="coerce")
    product_returns["product_return"] = pd.to_numeric(product_returns["product_return"], errors="coerce").fillna(0.0)
    product_returns["prev_main_close"] = product_returns.groupby("product_vt_symbol")["main_close"].shift(1)
    product_returns["prev_contract"] = product_returns.groupby("product_vt_symbol")["main_contract_vt"].shift(1)
    product_returns["same_contract"] = product_returns["main_contract_vt"].eq(product_returns["prev_contract"])
    product_returns["prev_main_close"] = np.where(
        product_returns["same_contract"] & (product_returns["prev_main_close"] > 0),
        product_returns["prev_main_close"],
        product_returns["main_close"],
    )
    product_returns["size"] = product_returns["product_vt_symbol"].map(SIZES).fillna(1.0).astype(float)
    product_returns["margin_ratio"] = product_returns["product_vt_symbol"].map(MARGIN_RATIOS).fillna(0.12).astype(float)
    product_returns["slippage"] = product_returns["product_vt_symbol"].map(SLIPPAGES).fillna(0.0).astype(float)
    product_returns["margin_per_contract"] = (
        product_returns["main_close"] * product_returns["size"] * product_returns["margin_ratio"]
    )
    return product_returns


def _load_signal_daily() -> pd.DataFrame:
    satellite = pd.read_csv(SATELLITE_DAILY_PATH, encoding="utf-8-sig")
    satellite["date"] = pd.to_datetime(satellite["date"]).dt.normalize()
    satellite = satellite[satellite["spec"].eq(SPEC_NAME)].copy()
    satellite = satellite[["date", "long_products", "short_products", f"satellite_return_cost{COST_BPS:g}bps"]].copy()
    satellite.rename(columns={f"satellite_return_cost{COST_BPS:g}bps": "net_value_return"}, inplace=True)
    return satellite


def _split_products(value: Any) -> list[str]:
    if pd.isna(value):
        return []
    text = str(value).strip()
    if not text:
        return []
    return [item for item in text.split(",") if item]


def _target_lots(
    profile: Profile,
    signal_row: pd.Series,
    price_by_product: dict[str, pd.Series],
) -> tuple[dict[str, int], float, int, int]:
    desired_products: list[tuple[str, int]] = [
        *((product, 1) for product in _split_products(signal_row.get("long_products"))),
        *((product, -1) for product in _split_products(signal_row.get("short_products"))),
    ]
    desired: list[tuple[str, str, int, float]] = []
    for product, direction in desired_products:
        price_row = price_by_product.get(product)
        if price_row is None:
            continue
        contract = str(_row_get(price_row, "main_contract_vt", ""))
        margin = _safe_float(_row_get(price_row, "margin_per_contract"))
        if margin <= 0:
            continue
        desired.append((contract, product, direction, margin))
    if not desired:
        return {}, 0.0, len(desired_products), 0

    targets: dict[str, int] = {}
    if profile.mode == "floor_per_leg":
        per_leg_margin = SATELLITE_CAPITAL / len(desired)
        for contract, _product, direction, margin in desired:
            lots = int(math.floor(per_leg_margin / margin))
            if lots > 0:
                targets[contract] = direction * lots
    elif profile.mode == "min1_cheapest_cap":
        used_margin = 0.0
        for contract, _product, direction, margin in sorted(desired, key=lambda item: item[3]):
            if profile.margin_cap is not None and used_margin + margin > profile.margin_cap:
                continue
            targets[contract] = direction
            used_margin += margin
    elif profile.mode == "min1_all":
        for contract, _product, direction, _margin in desired:
            targets[contract] = direction

    required_min1_margin = float(sum(item[3] for item in desired))
    return targets, required_min1_margin, len(desired_products), len(targets)


def _simulate_profile(profile: Profile, price_frame: pd.DataFrame, signals: pd.DataFrame) -> pd.DataFrame:
    price_by_date_product = {
        (row.date, row.product_vt_symbol): row
        for row in price_frame.itertuples(index=False)
    }
    contract_to_product = (
        price_frame.drop_duplicates(["date", "main_contract_vt"])
        .set_index(["date", "main_contract_vt"])["product_vt_symbol"]
        .to_dict()
    )
    prev_positions: dict[str, int] = {}
    rows: list[dict[str, Any]] = []
    cumulative_pnl = 0.0

    for signal_row in signals.sort_values("date").itertuples(index=False):
        date = pd.Timestamp(signal_row.date).normalize()
        day_prices = price_frame[price_frame["date"].eq(date)]
        price_by_product = {str(row.product_vt_symbol): row for row in day_prices.itertuples(index=False)}
        targets, required_min1_margin, desired_count, held_count = _target_lots(
            profile,
            pd.Series(signal_row._asdict()),
            price_by_product,
        )

        pnl = 0.0
        margin = 0.0
        for contract, lots in targets.items():
            product = contract_to_product.get((date, contract))
            if product is None:
                continue
            price_row = price_by_date_product.get((date, product))
            if price_row is None:
                continue
            pnl += lots * _safe_float(price_row.prev_main_close) * _safe_float(price_row.size) * _safe_float(
                price_row.product_return
            )
            margin += abs(lots) * _safe_float(price_row.margin_per_contract)

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
                slippage_cost += delta * _safe_float(price_row.slippage) * _safe_float(price_row.size)

        cost = slippage_cost
        pnl_after_cost = pnl - cost
        cumulative_pnl += pnl_after_cost
        rows.append(
            {
                "date": date,
                "profile": profile.name,
                "profile_label": profile.label,
                "desired_signal_count": desired_count,
                "held_contract_count": held_count,
                "zero_position_flag": int(desired_count > 0 and held_count == 0),
                "required_min1_margin": required_min1_margin,
                "actual_margin": margin,
                "turnover_contracts": turnover,
                "slippage_cost": cost,
                "daily_pnl": pnl_after_cost,
                "satellite_balance": SATELLITE_CAPITAL + cumulative_pnl,
            }
        )
        prev_positions = targets

    return pd.DataFrame(rows)


def _summarize(daily: pd.DataFrame, c3: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    c3_metrics = _path_metrics(c3["c3_balance"], TOTAL_CAPITAL)
    for profile, group in daily.groupby("profile", sort=False):
        group = group.sort_values("date").copy()
        merged = c3.merge(group[["date", "daily_pnl"]], on="date", how="left").fillna({"daily_pnl": 0.0})
        merged["satellite_cumulative_pnl"] = merged["daily_pnl"].cumsum()
        merged["combined_balance"] = merged["c3_balance"] + merged["satellite_cumulative_pnl"]
        sat_metrics = _path_metrics(group["satellite_balance"], SATELLITE_CAPITAL)
        combined_metrics = _path_metrics(merged["combined_balance"], TOTAL_CAPITAL)
        rows.append(
            {
                "profile": profile,
                "profile_label": str(group["profile_label"].iloc[0]),
                "satellite_total_return_pct": sat_metrics["total_return_pct"],
                "satellite_max_dd_percent": sat_metrics["max_dd_percent"],
                "combined_total_return_pct": combined_metrics["total_return_pct"],
                "combined_retention_vs_c3_pct": combined_metrics["total_return_pct"] / c3_metrics["total_return_pct"] * 100.0,
                "combined_max_dd_percent": combined_metrics["max_dd_percent"],
                "combined_sharpe": combined_metrics["sharpe_ratio"],
                "max_actual_margin": _safe_float(group["actual_margin"].max()),
                "avg_actual_margin": _safe_float(group["actual_margin"].mean()),
                "max_required_min1_margin": _safe_float(group["required_min1_margin"].max()),
                "avg_required_min1_margin": _safe_float(group["required_min1_margin"].mean()),
                "zero_position_days": int(group["zero_position_flag"].sum()),
                "active_signal_days": int((group["desired_signal_count"] > 0).sum()),
                "total_turnover_contracts": int(group["turnover_contracts"].sum()),
                "total_slippage_cost": _safe_float(group["slippage_cost"].sum()),
                "c3_total_return_pct": c3_metrics["total_return_pct"],
                "c3_max_dd_percent": c3_metrics["max_dd_percent"],
            }
        )
    return pd.DataFrame(rows)


def _decide(summary: pd.DataFrame) -> dict[str, Any]:
    executable = summary[
        (summary["profile"].eq("floor_margin_per_leg_37p5k"))
        & (summary["combined_max_dd_percent"] >= -30.0)
        & (summary["combined_retention_vs_c3_pct"] >= 80.0)
        & (summary["zero_position_days"] == 0)
    ].copy()
    min1_all = summary[summary["profile"].eq("min1_all_no_cap")].head(1)
    required_margin = _safe_float(min1_all["max_required_min1_margin"].iloc[0]) if not min1_all.empty else 0.0
    return {
        "decision": "integer_feasible_requires_full_engine" if not executable.empty else "integer_feasibility_fail_or_needs_different_vehicle",
        "executable_profiles": executable["profile"].tolist(),
        "max_required_margin_for_min1_all": required_margin,
        "main_note": "If 37.5k floor sizing cannot hold all target legs, the Stage045 7.5% net-value mix is not directly reproducible as an independent futures sleeve.",
    }


def _build_report(summary: pd.DataFrame, decision: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Stage046 横截面动量卫星整数手数可交易性",
            "",
            "## 定位",
            "",
            "- 目标：检验 Stage045 的 `7.5%` 卫星腿在真实合约乘数、保证金率和最小1手约束下是否仍可交易。",
            "- 本阶段不修改 C3，只把卫星腿从净值层收益转换成合约整数手数的近似执行层。",
            "- 这是可交易性筛查，不是最终 vn.py 组合引擎。",
            "",
            "## 汇总",
            "",
            _to_markdown_table(
                summary,
                [
                    "profile",
                    "satellite_total_return_pct",
                    "satellite_max_dd_percent",
                    "combined_total_return_pct",
                    "combined_retention_vs_c3_pct",
                    "combined_max_dd_percent",
                    "max_actual_margin",
                    "max_required_min1_margin",
                    "zero_position_days",
                    "active_signal_days",
                ],
                max_rows=20,
            ),
            "",
            "## 决策",
            "",
            f"- 决策标签：`{decision.get('decision')}`。",
            f"- 最小1手全部执行所需最高保证金：`{decision.get('max_required_margin_for_min1_all'):.2f}`。",
            f"- 说明：{decision.get('main_note')}",
        ]
    )


def main() -> None:
    price_frame = _build_price_frame()
    signals = _load_signal_daily()
    c3 = _load_c3_daily()
    daily_frames = [_simulate_profile(profile, price_frame, signals) for profile in PROFILES]
    daily = pd.concat(daily_frames, ignore_index=True)
    summary = _summarize(daily, c3)
    decision = _decide(summary)

    DAILY_PATH.parent.mkdir(parents=True, exist_ok=True)
    daily.to_csv(DAILY_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_to_builtin(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_PATH.write_text(_build_report(summary, decision), encoding="utf-8")
    print(json.dumps(_to_builtin(decision), ensure_ascii=False, indent=2))
    print(f"[stage346] report={REPORT_PATH}")


if __name__ == "__main__":
    main()
