from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from analyze_qmt_roll_stage271_profit_lock_trade_attribution import (
    CURRENT_TIERS,
    _load_bars_for_trades,
    _load_trades,
    _pair_round_trips,
)
from analyze_qmt_roll_stage273_profit_lock_effectiveness_and_search import (
    _candidate_lock_pct,
    _pct_pnl,
    _profit_pct_at_close,
)


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"
MODEL_TAG: str = "stage278_exit_geometry_deep_dive_v1"
OUTPUT_PREFIX: str = "qmt_roll_stage278_exit_geometry_deep_dive"
POST_EXIT_HORIZON_DAYS: int = 60


@dataclass(frozen=True)
class Candidate:
    candidate_id: str
    description: str
    scope: str
    atr_period: int = 22
    atr_multiplier: float = 3.0
    activation_pct: float = 0.05
    anchor: str = "high_low"
    trigger_mode: str = "close"


CANDIDATES: tuple[Candidate, ...] = (
    Candidate(
        candidate_id="add_lock_chandelier22_3_after5_cap_actual",
        description="当前完整离场路径 + Chandelier 22/3 保护层，只能早于实际离场",
        scope="add_overlay",
    ),
    Candidate(
        candidate_id="replace_profit_lock_chandelier22_3_after5_extend60",
        description="只在疑似盈利锁 base_stop 交易腿上，用 Chandelier 22/3 替换固定盈利锁，最多延后60天",
        scope="replace_profit_lock",
    ),
    Candidate(
        candidate_id="replace_profit_lock_yoyo22_3_after5_extend60",
        description="只在疑似盈利锁 base_stop 交易腿上，用 Close/YoYo ATR 22/3 替换固定盈利锁，最多延后60天",
        scope="replace_profit_lock",
        anchor="close",
    ),
    Candidate(
        candidate_id="replace_prev2day_lock_chandelier22_3_after5_extend60",
        description="诊断：在 prev2day/base_stop 且已触发盈利锁的交易腿上，用 Chandelier 22/3 替换整套短跟踪退出，最多延后60天",
        scope="replace_prev2day_and_profit_lock",
    ),
    Candidate(
        candidate_id="replace_prev2day_lock_chandelier22_2_after5_extend60",
        description="诊断敏感性：prev2day/base_stop 锁盈腿，用 Chandelier 22/2 替换，最多延后60天",
        scope="replace_prev2day_and_profit_lock",
        atr_multiplier=2.0,
    ),
    Candidate(
        candidate_id="replace_prev2day_lock_chandelier22_4_after5_extend60",
        description="诊断敏感性：prev2day/base_stop 锁盈腿，用 Chandelier 22/4 替换，最多延后60天",
        scope="replace_prev2day_and_profit_lock",
        atr_multiplier=4.0,
    ),
    Candidate(
        candidate_id="replace_prev2day_lock_chandelier22_3_after10_extend60",
        description="诊断敏感性：prev2day/base_stop 且最大浮盈>=10%的交易腿，用 Chandelier 22/3 替换，最多延后60天",
        scope="replace_prev2day_and_profit_lock",
        activation_pct=0.10,
    ),
    Candidate(
        candidate_id="replace_prev2day_lock_yoyo22_3_after5_extend60",
        description="诊断：prev2day/base_stop 锁盈腿，用 Close/YoYo ATR 22/3 替换，最多延后60天",
        scope="replace_prev2day_and_profit_lock",
        anchor="close",
    ),
)


def _enrich_bars(bars_by_symbol: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    enriched: dict[str, pd.DataFrame] = {}
    for vt_symbol, bars in bars_by_symbol.items():
        df = bars.copy().sort_values("date").reset_index(drop=True)
        prev_close = df["close"].shift(1)
        tr = pd.concat(
            [
                df["high"] - df["low"],
                (df["high"] - prev_close).abs(),
                (df["low"] - prev_close).abs(),
            ],
            axis=1,
        ).max(axis=1)
        df["atr22"] = tr.rolling(22, min_periods=22).mean()
        df["roll_high22"] = df["high"].rolling(22, min_periods=1).max()
        df["roll_low22"] = df["low"].rolling(22, min_periods=1).min()
        df["roll_close_high22"] = df["close"].rolling(22, min_periods=1).max()
        df["roll_close_low22"] = df["close"].rolling(22, min_periods=1).min()
        enriched[vt_symbol] = df
    return enriched


def _stop_price_from_lock(direction: str, entry_price: float, lock_pct: float) -> float | None:
    if lock_pct <= 0:
        return None
    if direction == "long":
        return entry_price * (1 + lock_pct)
    return entry_price * (1 - lock_pct)


def _triggered(direction: str, close_price: float, stop_price: float | None) -> bool:
    if stop_price is None or not math.isfinite(float(stop_price)):
        return False
    if direction == "long":
        return close_price <= stop_price
    return close_price >= stop_price


def _combine(direction: str, stops: list[tuple[float | None, str]]) -> tuple[float | None, str]:
    valid = [(float(price), source) for price, source in stops if price is not None and math.isfinite(float(price))]
    if not valid:
        return None, "none"
    if direction == "long":
        return max(valid, key=lambda item: item[0])
    return min(valid, key=lambda item: item[0])


def _actual_pnl(row: dict[str, Any]) -> float:
    return _pct_pnl(str(row["direction"]), float(row["entry_price"]), float(row["exit_price"]))


def _path_slice(bars: pd.DataFrame, start_date: pd.Timestamp, end_date: pd.Timestamp) -> pd.DataFrame:
    return bars[(bars["date"] >= start_date) & (bars["date"] <= end_date)].copy()


def _max_close_profit(
    *,
    row: dict[str, Any],
    bars: pd.DataFrame,
    end_date: pd.Timestamp,
) -> tuple[float, float, float | None]:
    entry_date = pd.Timestamp(row["entry_date"]).normalize()
    path = _path_slice(bars, entry_date, end_date)
    if path.empty:
        return 0.0, 0.0, None
    direction = str(row["direction"])
    entry_price = float(row["entry_price"])
    max_profit = max(_profit_pct_at_close(direction, entry_price, float(close)) for close in path["close"])
    _, lock_pct = _candidate_lock_pct(max_profit, tuple(CURRENT_TIERS))
    lock_stop = _stop_price_from_lock(direction, entry_price, lock_pct)
    return float(max_profit), float(lock_pct), lock_stop


def _candidate_raw_stop(
    *,
    candidate: Candidate,
    direction: str,
    bar: dict[str, Any],
) -> float | None:
    atr_value = float(bar.get("atr22", float("nan")))
    if not math.isfinite(atr_value) or atr_value <= 0:
        return None
    if candidate.anchor == "close":
        high_anchor = float(bar["roll_close_high22"])
        low_anchor = float(bar["roll_close_low22"])
    else:
        high_anchor = float(bar["roll_high22"])
        low_anchor = float(bar["roll_low22"])
    if direction == "long":
        return high_anchor - candidate.atr_multiplier * atr_value
    return low_anchor + candidate.atr_multiplier * atr_value


def _simulate_overlay(
    *,
    row: dict[str, Any],
    bars: pd.DataFrame,
    candidate: Candidate,
) -> dict[str, Any]:
    entry_date = pd.Timestamp(row["entry_date"]).normalize()
    actual_exit_date = pd.Timestamp(row["exit_date"]).normalize()
    direction = str(row["direction"])
    entry_price = float(row["entry_price"])
    actual_exit_price = float(row["exit_price"])
    path = _path_slice(bars, entry_date, actual_exit_date)
    if path.empty:
        return _actual_result(row, "no_path", eligible=False)

    max_profit = -math.inf
    active_lock = 0.0
    candidate_stop: float | None = None
    for bar in path.to_dict("records"):
        close_price = float(bar["close"])
        max_profit = max(max_profit, _profit_pct_at_close(direction, entry_price, close_price))
        _, lock_pct = _candidate_lock_pct(max_profit, tuple(CURRENT_TIERS))
        active_lock = max(active_lock, lock_pct)

        raw_stop = None
        if max_profit >= candidate.activation_pct:
            raw_stop = _candidate_raw_stop(candidate=candidate, direction=direction, bar=bar)
        if raw_stop is not None:
            if candidate_stop is None:
                candidate_stop = raw_stop
            elif direction == "long":
                candidate_stop = max(candidate_stop, raw_stop)
            else:
                candidate_stop = min(candidate_stop, raw_stop)

        lock_stop = _stop_price_from_lock(direction, entry_price, active_lock)
        effective_stop, source = _combine(direction, [(lock_stop, "current_lock"), (candidate_stop, "candidate_atr")])
        if _triggered(direction, close_price, effective_stop):
            return {
                "eligible": True,
                "exit_date": pd.Timestamp(bar["date"]).normalize(),
                "exit_price": close_price,
                "pnl_pct": _pct_pnl(direction, entry_price, close_price),
                "source": source,
                "max_profit_pct": float(max_profit),
                "active_lock_pct": float(active_lock),
                "candidate_stop": candidate_stop,
                "extension_days": int((pd.Timestamp(bar["date"]).normalize() - actual_exit_date).days),
            }

    return {
        "eligible": True,
        "exit_date": actual_exit_date,
        "exit_price": actual_exit_price,
        "pnl_pct": _actual_pnl(row),
        "source": "actual_exit",
        "max_profit_pct": float(max_profit),
        "active_lock_pct": float(active_lock),
        "candidate_stop": candidate_stop,
        "extension_days": 0,
    }


def _actual_result(row: dict[str, Any], source: str, eligible: bool) -> dict[str, Any]:
    actual_exit_date = pd.Timestamp(row["exit_date"]).normalize()
    return {
        "eligible": bool(eligible),
        "exit_date": actual_exit_date,
        "exit_price": float(row["exit_price"]),
        "pnl_pct": _actual_pnl(row),
        "source": source,
        "max_profit_pct": float(row.get("max_close_profit_at_actual", 0.0) or 0.0),
        "active_lock_pct": float(row.get("active_lock_at_actual", 0.0) or 0.0),
        "candidate_stop": None,
        "extension_days": 0,
    }


def _is_replacement_eligible(row: dict[str, Any], candidate: Candidate) -> bool:
    exit_reason = str(row.get("exit_reason", ""))
    active_lock = float(row.get("active_lock_at_actual", 0.0) or 0.0)
    max_profit = float(row.get("max_close_profit_at_actual", 0.0) or 0.0)
    if active_lock <= 0 or max_profit < candidate.activation_pct:
        return False
    if candidate.scope == "replace_profit_lock":
        return "base_stop" in exit_reason
    if candidate.scope == "replace_prev2day_and_profit_lock":
        return ("base_stop" in exit_reason) or ("prev2day_stop" in exit_reason)
    return False


def _simulate_replacement(
    *,
    row: dict[str, Any],
    bars: pd.DataFrame,
    candidate: Candidate,
) -> dict[str, Any]:
    if not _is_replacement_eligible(row, candidate):
        return _actual_result(row, "not_eligible_actual_exit", eligible=False)

    entry_date = pd.Timestamp(row["entry_date"]).normalize()
    actual_exit_date = pd.Timestamp(row["exit_date"]).normalize()
    horizon_date = actual_exit_date + pd.Timedelta(days=POST_EXIT_HORIZON_DAYS)
    direction = str(row["direction"])
    entry_price = float(row["entry_price"])
    path = _path_slice(bars, entry_date, horizon_date)
    if path.empty:
        return _actual_result(row, "no_path", eligible=True)

    max_profit = -math.inf
    candidate_stop: float | None = None
    last_bar: dict[str, Any] | None = None
    for bar in path.to_dict("records"):
        last_bar = bar
        close_price = float(bar["close"])
        max_profit = max(max_profit, _profit_pct_at_close(direction, entry_price, close_price))
        raw_stop = None
        if max_profit >= candidate.activation_pct:
            raw_stop = _candidate_raw_stop(candidate=candidate, direction=direction, bar=bar)
        if raw_stop is not None:
            if candidate_stop is None:
                candidate_stop = raw_stop
            elif direction == "long":
                candidate_stop = max(candidate_stop, raw_stop)
            else:
                candidate_stop = min(candidate_stop, raw_stop)

        if _triggered(direction, close_price, candidate_stop):
            exit_date = pd.Timestamp(bar["date"]).normalize()
            return {
                "eligible": True,
                "exit_date": exit_date,
                "exit_price": close_price,
                "pnl_pct": _pct_pnl(direction, entry_price, close_price),
                "source": "candidate_atr",
                "max_profit_pct": float(max_profit),
                "active_lock_pct": float(row.get("active_lock_at_actual", 0.0) or 0.0),
                "candidate_stop": candidate_stop,
                "extension_days": int((exit_date - actual_exit_date).days),
            }

    if last_bar is None:
        return _actual_result(row, "no_path", eligible=True)
    horizon_exit_date = pd.Timestamp(last_bar["date"]).normalize()
    horizon_exit_price = float(last_bar["close"])
    return {
        "eligible": True,
        "exit_date": horizon_exit_date,
        "exit_price": horizon_exit_price,
        "pnl_pct": _pct_pnl(direction, entry_price, horizon_exit_price),
        "source": "horizon_exit",
        "max_profit_pct": float(max_profit),
        "active_lock_pct": float(row.get("active_lock_at_actual", 0.0) or 0.0),
        "candidate_stop": candidate_stop,
        "extension_days": int((horizon_exit_date - actual_exit_date).days),
    }


def _prepare_inputs() -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    trades = _load_trades()
    pairs = _pair_round_trips(trades)
    pairs["entry_date"] = pd.to_datetime(pairs["entry_date"]).dt.normalize()
    pairs["exit_date"] = pd.to_datetime(pairs["exit_date"]).dt.normalize()
    pairs["entry_year"] = pd.to_datetime(pairs["entry_datetime"]).dt.year
    pairs["weight"] = pd.to_numeric(pairs["volume"], errors="coerce").fillna(1.0).clip(lower=1.0)
    pairs["actual_pnl_pct"] = pairs.apply(lambda row: _actual_pnl(row.to_dict()), axis=1)
    bars_by_symbol = _enrich_bars(_load_bars_for_trades(trades))
    pairs = pairs[pairs["vt_symbol"].isin(bars_by_symbol)].reset_index(drop=True)

    max_profits: list[float] = []
    lock_pcts: list[float] = []
    lock_stops: list[float | None] = []
    for row in pairs.to_dict("records"):
        bars = bars_by_symbol[str(row["vt_symbol"])]
        max_profit, lock_pct, lock_stop = _max_close_profit(row=row, bars=bars, end_date=pd.Timestamp(row["exit_date"]))
        max_profits.append(max_profit)
        lock_pcts.append(lock_pct)
        lock_stops.append(lock_stop)
    pairs["max_close_profit_at_actual"] = max_profits
    pairs["active_lock_at_actual"] = lock_pcts
    pairs["lock_stop_at_actual"] = lock_stops
    pairs["lock_active_at_actual"] = pairs["active_lock_at_actual"] > 0
    pairs["base_stop_with_lock"] = pairs["exit_reason"].astype(str).str.contains("base_stop") & pairs["lock_active_at_actual"]
    pairs["prev2day_or_base_with_lock"] = (
        pairs["exit_reason"].astype(str).str.contains("base_stop|prev2day_stop") & pairs["lock_active_at_actual"]
    )
    pairs["leg_id"] = range(len(pairs))
    return pairs, bars_by_symbol


def _build_detail(pairs: pd.DataFrame, bars_by_symbol: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for row in pairs.to_dict("records"):
        bars = bars_by_symbol[str(row["vt_symbol"])]
        for candidate in CANDIDATES:
            if candidate.scope == "add_overlay":
                result = _simulate_overlay(row=row, bars=bars, candidate=candidate)
            else:
                result = _simulate_replacement(row=row, bars=bars, candidate=candidate)
            actual_exit_date = pd.Timestamp(row["exit_date"]).normalize()
            candidate_exit_date = pd.Timestamp(result["exit_date"]).normalize()
            rows.append(
                {
                    "candidate_id": candidate.candidate_id,
                    "description": candidate.description,
                    "scope": candidate.scope,
                    "anchor": candidate.anchor,
                    "atr_multiplier": candidate.atr_multiplier,
                    "activation_pct": candidate.activation_pct,
                    "leg_id": int(row["leg_id"]),
                    "vt_symbol": str(row["vt_symbol"]),
                    "product_vt_symbol": str(row["product_vt_symbol"]),
                    "direction": str(row["direction"]),
                    "entry_year": int(row["entry_year"]),
                    "entry_date": row["entry_date"],
                    "actual_exit_date": actual_exit_date,
                    "candidate_exit_date": candidate_exit_date,
                    "exit_reason": str(row["exit_reason"]),
                    "volume": float(row["volume"]),
                    "weight": float(row["weight"]),
                    "actual_pnl_pct": float(row["actual_pnl_pct"]),
                    "candidate_pnl_pct": float(result["pnl_pct"]),
                    "delta_vs_actual_pct": float(result["pnl_pct"]) - float(row["actual_pnl_pct"]),
                    "eligible": int(bool(result["eligible"])),
                    "source": str(result["source"]),
                    "extension_days": int(result["extension_days"]),
                    "changed_exit_date": int(candidate_exit_date != actual_exit_date),
                    "early_exit": int(candidate_exit_date < actual_exit_date),
                    "late_exit": int(candidate_exit_date > actual_exit_date),
                    "max_close_profit_at_actual": float(row["max_close_profit_at_actual"]),
                    "active_lock_at_actual": float(row["active_lock_at_actual"]),
                    "base_stop_with_lock": int(bool(row["base_stop_with_lock"])),
                    "prev2day_or_base_with_lock": int(bool(row["prev2day_or_base_with_lock"])),
                    "candidate_stop": result["candidate_stop"],
                    "candidate_max_profit_pct": float(result["max_profit_pct"]),
                }
            )
    return pd.DataFrame(rows)


def _weighted_sum(df: pd.DataFrame, column: str) -> float:
    if df.empty:
        return 0.0
    return float((pd.to_numeric(df[column], errors="coerce").fillna(0.0) * df["weight"]).sum())


def _concentration_share(df: pd.DataFrame) -> float:
    positive = df[df["delta_vs_actual_pct"] > 0].copy()
    positive_sum = _weighted_sum(positive, "delta_vs_actual_pct")
    if positive.empty or positive_sum <= 0:
        return 0.0
    positive["weighted_delta"] = positive["delta_vs_actual_pct"] * positive["weight"]
    return float(positive.sort_values("weighted_delta", ascending=False).head(10)["weighted_delta"].sum() / positive_sum)


def _summarize(detail: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    summary_rows: list[dict[str, Any]] = []
    for candidate_id, group in detail.groupby("candidate_id"):
        year_delta = pd.Series(
            {int(year): _weighted_sum(year_group, "delta_vs_actual_pct") for year, year_group in group.groupby("entry_year")}
        )
        eligible = group[group["eligible"].eq(1)]
        summary_rows.append(
            {
                "candidate_id": candidate_id,
                "description": str(group["description"].iloc[0]),
                "scope": str(group["scope"].iloc[0]),
                "trade_legs": int(len(group)),
                "eligible_legs": int(group["eligible"].sum()),
                "changed_exit_legs": int(group["changed_exit_date"].sum()),
                "early_exit_legs": int(group["early_exit"].sum()),
                "late_exit_legs": int(group["late_exit"].sum()),
                "weighted_delta_sum": _weighted_sum(group, "delta_vs_actual_pct"),
                "eligible_weighted_delta_sum": _weighted_sum(eligible, "delta_vs_actual_pct"),
                "avg_delta_pct": float(group["delta_vs_actual_pct"].mean()),
                "median_delta_pct": float(group["delta_vs_actual_pct"].median()),
                "positive_legs": int((group["delta_vs_actual_pct"] > 0).sum()),
                "negative_legs": int((group["delta_vs_actual_pct"] < 0).sum()),
                "year_win_count": int((year_delta > 0).sum()),
                "min_year_delta_sum": float(year_delta.min()) if not year_delta.empty else 0.0,
                "median_extension_days": float(eligible["extension_days"].median()) if not eligible.empty else 0.0,
                "max_extension_days": int(eligible["extension_days"].max()) if not eligible.empty else 0,
                "top10_positive_share": _concentration_share(group),
            }
        )
    summary = pd.DataFrame(summary_rows).sort_values(["weighted_delta_sum", "year_win_count"], ascending=False)

    year_rows: list[dict[str, Any]] = []
    for (candidate_id, entry_year), group in detail.groupby(["candidate_id", "entry_year"]):
        year_rows.append(
            {
                "candidate_id": candidate_id,
                "entry_year": int(entry_year),
                "weighted_delta_sum": _weighted_sum(group, "delta_vs_actual_pct"),
                "eligible_legs": int(group["eligible"].sum()),
                "changed_exit_legs": int(group["changed_exit_date"].sum()),
            }
        )
    by_year = pd.DataFrame(year_rows)

    reason_rows: list[dict[str, Any]] = []
    for (candidate_id, exit_reason), group in detail.groupby(["candidate_id", "exit_reason"]):
        reason_rows.append(
            {
                "candidate_id": candidate_id,
                "exit_reason": exit_reason,
                "weighted_delta_sum": _weighted_sum(group, "delta_vs_actual_pct"),
                "trade_legs": int(len(group)),
                "eligible_legs": int(group["eligible"].sum()),
                "changed_exit_legs": int(group["changed_exit_date"].sum()),
            }
        )
    by_reason = pd.DataFrame(reason_rows).sort_values(["candidate_id", "weighted_delta_sum"], ascending=[True, False])

    product_rows: list[dict[str, Any]] = []
    for (candidate_id, product), group in detail.groupby(["candidate_id", "product_vt_symbol"]):
        product_rows.append(
            {
                "candidate_id": candidate_id,
                "product_vt_symbol": product,
                "weighted_delta_sum": _weighted_sum(group, "delta_vs_actual_pct"),
                "trade_legs": int(len(group)),
                "eligible_legs": int(group["eligible"].sum()),
                "changed_exit_legs": int(group["changed_exit_date"].sum()),
            }
        )
    by_product = pd.DataFrame(product_rows).sort_values(["candidate_id", "weighted_delta_sum"], ascending=[True, False])

    top_deltas = detail.reindex(detail["delta_vs_actual_pct"].abs().sort_values(ascending=False).index).head(60)
    return summary, by_year, by_reason, by_product, top_deltas


def _dominance(pairs: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    rows.append({"metric": "paired_trade_legs", "value": float(len(pairs))})
    rows.append({"metric": "lock_active_at_actual", "value": float(pairs["lock_active_at_actual"].sum())})
    rows.append({"metric": "base_stop_with_lock", "value": float(pairs["base_stop_with_lock"].sum())})
    rows.append({"metric": "prev2day_or_base_with_lock", "value": float(pairs["prev2day_or_base_with_lock"].sum())})
    for exit_reason, group in pairs.groupby("exit_reason"):
        rows.append({"metric": f"exit_reason::{exit_reason}", "value": float(len(group))})
    return pd.DataFrame(rows)


def _decision(summary: pd.DataFrame) -> dict[str, Any]:
    rows = {str(row["candidate_id"]): row for row in summary.to_dict("records")}
    lock_only = rows.get("replace_profit_lock_chandelier22_3_after5_extend60", {})
    broad = rows.get("replace_prev2day_lock_chandelier22_3_after5_extend60", {})
    return {
        "baseline": "official_stage78_1_defensive_50w_no_sizing_cap",
        "stage277_was_too_shallow": True,
        "lock_only_standard": {
            "candidate_id": "replace_profit_lock_chandelier22_3_after5_extend60",
            "eligible_legs": int(lock_only.get("eligible_legs", 0) or 0),
            "weighted_delta_sum": float(lock_only.get("weighted_delta_sum", 0.0) or 0.0),
            "year_win_count": int(lock_only.get("year_win_count", 0) or 0),
            "positive_legs": int(lock_only.get("positive_legs", 0) or 0),
            "negative_legs": int(lock_only.get("negative_legs", 0) or 0),
            "promote_to_engine": False,
            "reason": "锁盈单独替换样本太少，只能作为诊断；若没有跨年份和足够正贡献，不进入引擎。",
        },
        "broad_prev2day_lock_diagnostic": {
            "candidate_id": "replace_prev2day_lock_chandelier22_3_after5_extend60",
            "eligible_legs": int(broad.get("eligible_legs", 0) or 0),
            "weighted_delta_sum": float(broad.get("weighted_delta_sum", 0.0) or 0.0),
            "year_win_count": int(broad.get("year_win_count", 0) or 0),
            "positive_legs": int(broad.get("positive_legs", 0) or 0),
            "negative_legs": int(broad.get("negative_legs", 0) or 0),
            "top10_positive_share": float(broad.get("top10_positive_share", 0.0) or 0.0),
            "promote_to_engine": bool(
                float(broad.get("weighted_delta_sum", 0.0) or 0.0) > 0
                and int(broad.get("year_win_count", 0) or 0) >= 5
                and int(broad.get("positive_legs", 0) or 0) >= 10
                and float(broad.get("top10_positive_share", 1.0) or 1.0) <= 0.85
            ),
            "reason": "这是替换 prev2day+锁盈的更大结构变化；即使通过，也只能进入完整引擎反证，不能直接实盘。",
        },
    }


def _format_table(df: pd.DataFrame, columns: list[str], max_rows: int = 30) -> str:
    if df.empty:
        return "- 无数据"
    return df[[column for column in columns if column in df.columns]].head(max_rows).to_markdown(index=False)


def _write_report(
    *,
    dominance: pd.DataFrame,
    summary: pd.DataFrame,
    by_year: pd.DataFrame,
    by_reason: pd.DataFrame,
    by_product: pd.DataFrame,
    top_deltas: pd.DataFrame,
    decision: dict[str, Any],
    paths: dict[str, Path],
) -> None:
    report = f"""# Stage278 退出几何深挖

## 为什么补这一轮

Stage277 只验证了“当前锁盈 + 标准 Chandelier 叠加层”，且候选只能比当前真实离场更早退出。这个口径能排除盲目叠加，但不足以回答：

- 当前盈利锁是不是被 `prev2day_stop` 压制？
- 如果 ATR 不是叠加，而是替换固定盈利锁，会不会更好？
- 如果把 `prev2day_stop` 和固定锁盈一起替换成 ATR 趋势跟踪，会不会暴露出更本质的退出问题？

## 当前退出主导关系

{_format_table(dominance, ["metric", "value"], max_rows=40)}

## 候选摘要

{_format_table(summary, ["candidate_id", "scope", "eligible_legs", "changed_exit_legs", "early_exit_legs", "late_exit_legs", "weighted_delta_sum", "positive_legs", "negative_legs", "year_win_count", "min_year_delta_sum", "median_extension_days", "max_extension_days", "top10_positive_share"], max_rows=20)}

## 分年份

{_format_table(by_year, ["candidate_id", "entry_year", "weighted_delta_sum", "eligible_legs", "changed_exit_legs"], max_rows=80)}

## 分原始退出原因

{_format_table(by_reason, ["candidate_id", "exit_reason", "weighted_delta_sum", "trade_legs", "eligible_legs", "changed_exit_legs"], max_rows=80)}

## 分品种

{_format_table(by_product, ["candidate_id", "product_vt_symbol", "weighted_delta_sum", "trade_legs", "eligible_legs", "changed_exit_legs"], max_rows=80)}

## 影响最大的交易腿

{_format_table(top_deltas, ["candidate_id", "vt_symbol", "direction", "entry_date", "actual_exit_date", "candidate_exit_date", "exit_reason", "delta_vs_actual_pct", "source", "extension_days", "max_close_profit_at_actual"], max_rows=50)}

## 判定

```json
{json.dumps(decision, ensure_ascii=False, indent=2)}
```

## 解释边界

- 本阶段仍是交易腿级归因，不是组合引擎回测。
- `replace_profit_lock_*` 只替换疑似由固定盈利锁主导的 `base_stop` 交易腿。
- `replace_prev2day_lock_*` 是更激进的诊断：它同时挑战 `prev2day_stop` 和固定盈利锁，不能直接 promotion。
- 替换式模拟允许最多延后 `60` 天；这会忽略资金占用、再入场冲突、换月和组合级相关性，所以只用于判断“是否值得写完整引擎验证”。

## 输出文件

- detail：`{paths["detail"].relative_to(PROJECT_DIR)}`
- summary：`{paths["summary"].relative_to(PROJECT_DIR)}`
- dominance：`{paths["dominance"].relative_to(PROJECT_DIR)}`
- by_year：`{paths["by_year"].relative_to(PROJECT_DIR)}`
- by_reason：`{paths["by_reason"].relative_to(PROJECT_DIR)}`
- by_product：`{paths["by_product"].relative_to(PROJECT_DIR)}`
- top_deltas：`{paths["top_deltas"].relative_to(PROJECT_DIR)}`
- decision：`{paths["decision"].relative_to(PROJECT_DIR)}`
"""
    paths["report"].write_text(report, encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    pairs, bars_by_symbol = _prepare_inputs()
    detail = _build_detail(pairs, bars_by_symbol)
    summary, by_year, by_reason, by_product, top_deltas = _summarize(detail)
    dominance = _dominance(pairs)
    decision = _decision(summary)

    paths = {
        "detail": OUTPUT_DIR / f"{OUTPUT_PREFIX}_detail_{MODEL_TAG}.csv",
        "summary": OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv",
        "dominance": OUTPUT_DIR / f"{OUTPUT_PREFIX}_dominance_{MODEL_TAG}.csv",
        "by_year": OUTPUT_DIR / f"{OUTPUT_PREFIX}_by_year_{MODEL_TAG}.csv",
        "by_reason": OUTPUT_DIR / f"{OUTPUT_PREFIX}_by_reason_{MODEL_TAG}.csv",
        "by_product": OUTPUT_DIR / f"{OUTPUT_PREFIX}_by_product_{MODEL_TAG}.csv",
        "top_deltas": OUTPUT_DIR / f"{OUTPUT_PREFIX}_top_deltas_{MODEL_TAG}.csv",
        "decision": OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json",
        "report": OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md",
    }
    detail.to_csv(paths["detail"], index=False, encoding="utf-8-sig")
    summary.to_csv(paths["summary"], index=False, encoding="utf-8-sig")
    dominance.to_csv(paths["dominance"], index=False, encoding="utf-8-sig")
    by_year.to_csv(paths["by_year"], index=False, encoding="utf-8-sig")
    by_reason.to_csv(paths["by_reason"], index=False, encoding="utf-8-sig")
    by_product.to_csv(paths["by_product"], index=False, encoding="utf-8-sig")
    top_deltas.to_csv(paths["top_deltas"], index=False, encoding="utf-8-sig")
    paths["decision"].write_text(json.dumps(decision, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(
        dominance=dominance,
        summary=summary,
        by_year=by_year,
        by_reason=by_reason,
        by_product=by_product,
        top_deltas=top_deltas,
        decision=decision,
        paths=paths,
    )
    print(json.dumps({"decision": decision, "report": str(paths["report"])}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
