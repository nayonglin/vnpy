from __future__ import annotations

import json
import math
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from analyze_qmt_roll_stage324_true_combo_capital_margin import _to_builtin, _to_markdown_table
from analyze_qmt_roll_stage346_xsmom_integer_feasibility import (
    _build_price_frame,
    _load_signal_daily,
    _safe_float,
)
from run_qmt_alignment_backtest import OUTPUT_DIR


MODEL_TAG = "stage348_xsmom_capital_split_frontier_v1"
OUTPUT_PREFIX = "qmt_roll_stage348_xsmom_capital_split_frontier"
LINE_ID = "futures_trend_drawdown30_preserve_return"

TOTAL_CAPITAL = 500_000.0
MARGIN_REVIEW_PCT = 80.0
MARGIN_REJECT_PCT = 100.0
TARGET_MAX_DD_PCT = -30.0
RETURN_RETENTION_GATE_PCT = 80.0

STAGE325_DAILY_PATH = (
    OUTPUT_DIR
    / "qmt_roll_stage325_true_capital_split_frontier_combo_daily_"
    "stage325_true_capital_split_frontier_v1.csv"
)
STAGE325_MARGIN_PATH = (
    OUTPUT_DIR
    / "qmt_roll_stage325_true_capital_split_frontier_margin_"
    "stage325_true_capital_split_frontier_v1.csv"
)

DAILY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_{MODEL_TAG}.csv"
MARGIN_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_margin_{MODEL_TAG}.csv"
SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


@dataclass(frozen=True)
class Split:
    name: str
    c3_capital: float
    satellite_capital: float


@dataclass(frozen=True)
class Profile:
    name: str
    label: str
    mode: str


SPLITS: tuple[Split, ...] = (
    Split("c3_500_sat_0", 500_000.0, 0.0),
    Split("c3_450_sat_50", 450_000.0, 50_000.0),
    Split("c3_400_sat_100", 400_000.0, 100_000.0),
    Split("c3_350_sat_150", 350_000.0, 150_000.0),
    Split("c3_300_sat_200", 300_000.0, 200_000.0),
    Split("c3_250_sat_250", 250_000.0, 250_000.0),
)

PROFILES: tuple[Profile, ...] = (
    Profile("floor_per_leg_cap", "每腿按卫星资金均分，保证金向下取整", "floor_per_leg"),
    Profile("min1_cheapest_cap", "低保证金信号优先，每腿至少1手，总保证金不超卫星资金", "min1_cheapest"),
    Profile("min1_all_if_cap_allows", "只有完整篮子最低1手总保证金不超卫星资金时才执行", "min1_all_if_cap"),
    Profile("min1_all_no_cap_diagnostic", "全部信号最低1手，不设卫星资金上限，仅作边界诊断", "min1_all_no_cap"),
)


def _split_products(value: Any) -> list[str]:
    if pd.isna(value):
        return []
    text = str(value).strip()
    if not text:
        return []
    return [item for item in text.split(",") if item]


def _load_c3_split_daily() -> pd.DataFrame:
    frame = pd.read_csv(STAGE325_DAILY_PATH, encoding="utf-8-sig")
    frame["date"] = pd.to_datetime(frame["date"]).dt.normalize()
    for column in ["c3_net_pnl", "c3_trade_count"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(0.0)
    return frame[["date", "split_name", "c3_net_pnl", "c3_trade_count"]]


def _load_c3_split_margin() -> pd.DataFrame:
    frame = pd.read_csv(STAGE325_MARGIN_PATH, encoding="utf-8-sig")
    frame["date"] = pd.to_datetime(frame["date"]).dt.normalize()
    for column in ["c3_margin", "c3_active_contracts", "c3_active_products"]:
        frame[column] = pd.to_numeric(frame.get(column, 0.0), errors="coerce").fillna(0.0)
    return frame[["date", "split_name", "c3_margin", "c3_active_contracts", "c3_active_products"]]


def _path_metrics(balance: pd.Series, start_capital: float) -> dict[str, float]:
    values = pd.to_numeric(balance, errors="coerce").ffill().fillna(start_capital).to_numpy(dtype=float)
    if len(values) == 0:
        return {"end_balance": start_capital, "total_return_pct": 0.0, "max_dd_percent": 0.0, "sharpe_ratio": 0.0}
    high = np.maximum.accumulate(values)
    dd_pct = np.divide(values - high, high, out=np.zeros_like(values), where=high != 0.0) * 100.0
    returns = pd.Series(values).pct_change().fillna(0.0).to_numpy(dtype=float)
    std = float(np.std(returns, ddof=1)) if len(returns) > 1 else 0.0
    sharpe = float(np.mean(returns) / std * np.sqrt(252.0)) if std > 0 else 0.0
    return {
        "end_balance": float(values[-1]),
        "total_return_pct": float((values[-1] / start_capital - 1.0) * 100.0),
        "max_dd_percent": float(dd_pct.min()),
        "sharpe_ratio": sharpe,
    }


def _target_lots(
    split: Split,
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
        contract = str(price_row.get("main_contract_vt", ""))
        margin = _safe_float(price_row.get("margin_per_contract"))
        if contract and margin > 0:
            desired.append((contract, product, direction, margin))

    desired_count = len(desired_products)
    if split.satellite_capital <= 0 or not desired:
        return {}, 0.0, desired_count, 0

    required_min1_margin = float(sum(item[3] for item in desired))
    targets: dict[str, int] = {}
    if profile.mode == "floor_per_leg":
        per_leg_margin = split.satellite_capital / len(desired)
        for contract, _product, direction, margin in desired:
            lots = int(math.floor(per_leg_margin / margin))
            if lots > 0:
                targets[contract] = direction * lots
    elif profile.mode == "min1_cheapest":
        used_margin = 0.0
        for contract, _product, direction, margin in sorted(desired, key=lambda item: item[3]):
            if used_margin + margin > split.satellite_capital:
                continue
            targets[contract] = direction
            used_margin += margin
    elif profile.mode == "min1_all_if_cap":
        if required_min1_margin <= split.satellite_capital:
            targets = {contract: direction for contract, _product, direction, _margin in desired}
    elif profile.mode == "min1_all_no_cap":
        targets = {contract: direction for contract, _product, direction, _margin in desired}

    return targets, required_min1_margin, desired_count, len(targets)


def _simulate_satellite(split: Split, profile: Profile, price_frame: pd.DataFrame, signals: pd.DataFrame) -> pd.DataFrame:
    price_by_date_product = {(row.date, row.product_vt_symbol): row for row in price_frame.itertuples(index=False)}
    contract_to_product = (
        price_frame.drop_duplicates(["date", "main_contract_vt"])
        .set_index(["date", "main_contract_vt"])["product_vt_symbol"]
        .to_dict()
    )
    rows: list[dict[str, Any]] = []
    prev_positions: dict[str, int] = {}
    cumulative_pnl = 0.0

    for signal_row in signals.sort_values("date").itertuples(index=False):
        date = pd.Timestamp(signal_row.date).normalize()
        day_prices = price_frame[price_frame["date"].eq(date)]
        price_by_product = {str(row.product_vt_symbol): pd.Series(row._asdict()) for row in day_prices.itertuples(index=False)}
        targets, required_min1_margin, desired_count, held_count = _target_lots(
            split,
            profile,
            pd.Series(signal_row._asdict()),
            price_by_product,
        )

        pnl = 0.0
        margin = 0.0
        for contract, lots in targets.items():
            product = contract_to_product.get((date, contract))
            price_row = price_by_date_product.get((date, product)) if product else None
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

        daily_pnl = pnl - slippage_cost
        cumulative_pnl += daily_pnl
        rows.append(
            {
                "date": date,
                "split_name": split.name,
                "profile": profile.name,
                "profile_label": profile.label,
                "satellite_capital": split.satellite_capital,
                "desired_signal_count": desired_count,
                "held_contract_count": held_count,
                "zero_position_flag": int(desired_count > 0 and held_count == 0),
                "required_min1_margin": required_min1_margin,
                "satellite_margin": margin,
                "satellite_turnover_contracts": turnover,
                "satellite_slippage_cost": slippage_cost,
                "satellite_daily_pnl": daily_pnl,
                "satellite_balance": split.satellite_capital + cumulative_pnl,
            }
        )
        prev_positions = targets

    return pd.DataFrame(rows)


def _combine(
    split: Split,
    profile: Profile,
    c3_daily: pd.DataFrame,
    c3_margin: pd.DataFrame,
    satellite: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    base = c3_daily[c3_daily["split_name"].eq(split.name)].copy()
    base = base.merge(
        satellite[
            [
                "date",
                "satellite_daily_pnl",
                "satellite_turnover_contracts",
                "satellite_slippage_cost",
                "satellite_balance",
            ]
        ],
        on="date",
        how="left",
    )
    for column in ["satellite_daily_pnl", "satellite_turnover_contracts", "satellite_slippage_cost"]:
        base[column] = pd.to_numeric(base.get(column, 0.0), errors="coerce").fillna(0.0)
    base["combo_net_pnl"] = base["c3_net_pnl"] + base["satellite_daily_pnl"]
    base["balance"] = TOTAL_CAPITAL + base["combo_net_pnl"].cumsum()
    base["trade_count"] = base["c3_trade_count"] + base["satellite_turnover_contracts"]
    base["profile"] = profile.name
    base["profile_label"] = profile.label
    metrics = _path_metrics(base["balance"], TOTAL_CAPITAL)

    margin = c3_margin[c3_margin["split_name"].eq(split.name)].copy()
    margin = margin.merge(
        satellite[["date", "satellite_margin", "held_contract_count"]],
        on="date",
        how="left",
    )
    for column in ["satellite_margin", "held_contract_count"]:
        margin[column] = pd.to_numeric(margin.get(column, 0.0), errors="coerce").fillna(0.0)
    margin["balance"] = base.set_index("date").reindex(margin["date"])["balance"].to_numpy()
    margin["total_margin"] = margin["c3_margin"] + margin["satellite_margin"]
    margin["total_active_contracts"] = margin["c3_active_contracts"] + margin["held_contract_count"]
    margin["total_active_products"] = margin["c3_active_products"] + margin["held_contract_count"].clip(upper=6)
    margin["margin_to_equity_pct"] = (
        margin["total_margin"] / margin["balance"].replace(0.0, np.nan) * 100.0
    ).fillna(0.0)
    margin["profile"] = profile.name

    satellite_metrics = _path_metrics(satellite["satellite_balance"], split.satellite_capital) if split.satellite_capital > 0 else {
        "end_balance": 0.0,
        "total_return_pct": 0.0,
        "max_dd_percent": 0.0,
        "sharpe_ratio": 0.0,
    }
    row = {
        "split_name": split.name,
        "profile": profile.name,
        "profile_label": profile.label,
        "c3_capital": split.c3_capital,
        "satellite_capital": split.satellite_capital,
        "combo_end_balance": metrics["end_balance"],
        "combo_return_pct": metrics["total_return_pct"],
        "combo_max_dd_pct": metrics["max_dd_percent"],
        "combo_sharpe": metrics["sharpe_ratio"],
        "combo_trade_count": int(base["trade_count"].sum()),
        "combo_positive_day_ratio_pct": float((base["combo_net_pnl"] > 0).mean() * 100.0),
        "satellite_return_pct": satellite_metrics["total_return_pct"],
        "satellite_max_dd_pct": satellite_metrics["max_dd_percent"],
        "satellite_total_pnl": float(satellite["satellite_daily_pnl"].sum()) if not satellite.empty else 0.0,
        "satellite_total_turnover_contracts": int(satellite["satellite_turnover_contracts"].sum()) if not satellite.empty else 0,
        "satellite_total_slippage": float(satellite["satellite_slippage_cost"].sum()) if not satellite.empty else 0.0,
        "max_satellite_margin": float(satellite["satellite_margin"].max()) if not satellite.empty else 0.0,
        "max_required_min1_margin": float(satellite["required_min1_margin"].max()) if not satellite.empty else 0.0,
        "zero_position_days": int(satellite["zero_position_flag"].sum()) if not satellite.empty else 0,
        "active_signal_days": int((satellite["desired_signal_count"] > 0).sum()) if not satellite.empty else 0,
        "max_margin_to_equity_pct": float(margin["margin_to_equity_pct"].max()) if not margin.empty else 0.0,
        "p95_margin_to_equity_pct": float(margin["margin_to_equity_pct"].quantile(0.95)) if not margin.empty else 0.0,
        "review_days": int((margin["margin_to_equity_pct"] >= MARGIN_REVIEW_PCT).sum()) if not margin.empty else 0,
        "reject_days": int((margin["margin_to_equity_pct"] >= MARGIN_REJECT_PCT).sum()) if not margin.empty else 0,
    }
    return base, margin, row


def _build_report(summary: pd.DataFrame, decision: dict[str, Any]) -> str:
    valid = summary.sort_values(["candidate_ok", "combo_return_pct"], ascending=[False, False])
    return "\n".join(
        [
            "# Stage048 横截面动量卫星资金拆分粗前沿",
            "",
            "## 定位",
            "",
            "- 本阶段复用 Stage325 的 C3 真实资金路径，只把卫星腿替换为 Stage045 横截面动量的整数手数执行。",
            "- 总资金固定 `500,000`，只测试 `50万/0` 到 `25万/25万` 的粗资金拆分，不扫小数权重。",
            "- 通过条件：组合最大回撤进 `30%`、总收益保留50万C3的 `80%` 以上、组合保证金不触发100%拒绝线。",
            "",
            "## 汇总",
            "",
            _to_markdown_table(
                valid,
                [
                    "split_name",
                    "profile",
                    "combo_return_pct",
                    "return_retention_vs_c3_500_pct",
                    "combo_max_dd_pct",
                    "combo_sharpe",
                    "satellite_return_pct",
                    "max_satellite_margin",
                    "max_margin_to_equity_pct",
                    "review_days",
                    "reject_days",
                    "zero_position_days",
                    "candidate_ok",
                ],
                max_rows=80,
            ),
            "",
            "## 决策",
            "",
            f"- 决策标签：`{decision['decision']}`。",
            f"- 最佳候选：`{decision.get('best_candidate', {}).get('split_name', '-')}` / `{decision.get('best_candidate', {}).get('profile', '-')}`。",
            "",
            "## 反思",
            "",
            "- 是否过拟合：本阶段是粗资金拆分和整数手数执行约束，不调单品种、不救单窗口。",
            "- 是否还有价值继续：若没有候选，应停止横截面动量期货腿在50万账户内的资金拆分优化；若有候选，下一步才做多周期和滑点压力。",
        ]
    )


def main() -> None:
    price_frame = _build_price_frame()
    signals = _load_signal_daily()
    c3_daily = _load_c3_split_daily()
    c3_margin = _load_c3_split_margin()

    daily_frames: list[pd.DataFrame] = []
    margin_frames: list[pd.DataFrame] = []
    rows: list[dict[str, Any]] = []
    for split in SPLITS:
        profiles = (Profile("c3_only", "仅C3", "none"),) if split.satellite_capital <= 0 else PROFILES
        for profile in profiles:
            satellite = (
                pd.DataFrame(
                    {
                        "date": signals["date"],
                        "satellite_daily_pnl": 0.0,
                        "satellite_turnover_contracts": 0,
                        "satellite_slippage_cost": 0.0,
                        "satellite_balance": 0.0,
                        "satellite_margin": 0.0,
                        "held_contract_count": 0,
                        "required_min1_margin": 0.0,
                        "zero_position_flag": 0,
                        "desired_signal_count": 0,
                    }
                )
                if split.satellite_capital <= 0
                else _simulate_satellite(split, profile, price_frame, signals)
            )
            combined, margin, row = _combine(split, profile, c3_daily, c3_margin, satellite)
            daily_frames.append(combined)
            margin_frames.append(margin)
            rows.append(row)

    summary = pd.DataFrame(rows)
    c3_500_return = float(summary.loc[summary["split_name"].eq("c3_500_sat_0"), "combo_return_pct"].iloc[0])
    summary["return_retention_vs_c3_500_pct"] = np.where(
        c3_500_return > 0,
        summary["combo_return_pct"] / c3_500_return * 100.0,
        0.0,
    )
    summary["dd_lt_30_ok"] = (summary["combo_max_dd_pct"] >= TARGET_MAX_DD_PCT).astype(int)
    summary["retention_ok"] = (summary["return_retention_vs_c3_500_pct"] >= RETURN_RETENTION_GATE_PCT).astype(int)
    summary["margin_ok"] = (summary["reject_days"] == 0).astype(int)
    summary["satellite_cap_ok"] = (summary["max_satellite_margin"] <= summary["satellite_capital"].replace(0.0, np.inf)).astype(int)
    summary["candidate_ok"] = (
        summary["dd_lt_30_ok"].eq(1)
        & summary["retention_ok"].eq(1)
        & summary["margin_ok"].eq(1)
        & summary["satellite_cap_ok"].eq(1)
        & summary["profile"].ne("min1_all_no_cap_diagnostic")
    ).astype(int)

    daily = pd.concat(daily_frames, ignore_index=True)
    margin = pd.concat(margin_frames, ignore_index=True)

    candidates = summary[summary["candidate_ok"].eq(1)].copy()
    if candidates.empty:
        decision = {
            "decision": "xsmom_capital_split_fail",
            "best_candidate": {},
            "reason": "no coarse split passed drawdown, retention, margin, and satellite capital gates",
        }
    else:
        best = candidates.sort_values(["combo_return_pct", "combo_max_dd_pct"], ascending=[False, False]).iloc[0]
        decision = {
            "decision": "xsmom_capital_split_candidate_requires_multiperiod",
            "best_candidate": best.to_dict(),
        }

    DAILY_PATH.parent.mkdir(parents=True, exist_ok=True)
    daily.to_csv(DAILY_PATH, index=False, encoding="utf-8-sig")
    margin.to_csv(MARGIN_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_to_builtin(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_PATH.write_text(_build_report(summary, decision), encoding="utf-8")

    print(json.dumps(_to_builtin(decision), ensure_ascii=False, indent=2))
    print(f"[stage348] report={REPORT_PATH}")


if __name__ == "__main__":
    main()
