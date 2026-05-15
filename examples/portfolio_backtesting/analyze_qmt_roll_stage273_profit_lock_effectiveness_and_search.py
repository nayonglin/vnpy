from __future__ import annotations

import json
import math
import random
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Any

import pandas as pd
from vnpy.trader.constant import Interval
from vnpy.trader.database import get_database

from analyze_qmt_roll_stage271_profit_lock_trade_attribution import (
    CURRENT_TIERS,
    TRADES_PATH,
    _load_trades,
    _pair_round_trips,
    _parse_vt_symbol,
    _product_from_vt_symbol,
)


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"
MODEL_TAG: str = "stage273_profit_lock_effectiveness_search_v1"
OUTPUT_PREFIX: str = "qmt_roll_stage273_profit_lock_effectiveness_search"

BOOTSTRAP_ROUNDS: int = 240
RANDOM_SEED: int = 7801


@dataclass(frozen=True)
class Candidate:
    candidate_id: str
    family: str
    description: str
    tiers: tuple[tuple[float, float], ...]

    @property
    def tiers_string(self) -> str:
        return ",".join(f"{trigger:.4f}:{lock:.4f}" for trigger, lock in self.tiers)


def _load_bars_for_pairs(pairs: pd.DataFrame) -> dict[str, pd.DataFrame]:
    database = get_database()
    bars_by_symbol: dict[str, pd.DataFrame] = {}

    for vt_symbol, group in pairs.groupby("vt_symbol"):
        symbol, exchange = _parse_vt_symbol(str(vt_symbol))
        start_dt = pd.Timestamp(group["entry_datetime"].min()).to_pydatetime() - timedelta(days=5)
        end_dt = pd.Timestamp(group["exit_datetime"].max()).to_pydatetime() + timedelta(days=5)
        bars = database.load_bar_data(symbol, exchange, Interval.DAILY, start_dt, end_dt)
        rows: list[dict[str, Any]] = []
        for bar in bars:
            rows.append(
                {
                    "date": pd.Timestamp(bar.datetime).tz_localize(None).normalize(),
                    "open": float(bar.open_price),
                    "high": float(bar.high_price),
                    "low": float(bar.low_price),
                    "close": float(bar.close_price),
                }
            )
        if rows:
            bars_by_symbol[str(vt_symbol)] = (
                pd.DataFrame(rows)
                .drop_duplicates(subset=["date"])
                .sort_values("date")
                .reset_index(drop=True)
            )
    return bars_by_symbol


def _normalize_tiers(tiers: list[tuple[float, float]] | tuple[tuple[float, float], ...]) -> tuple[tuple[float, float], ...]:
    valid: list[tuple[float, float]] = []
    for trigger, lock in tiers:
        trigger = round(float(trigger), 4)
        lock = round(float(lock), 4)
        if trigger <= 0 or lock <= 0 or lock > trigger:
            continue
        valid.append((trigger, lock))
    return tuple(sorted(set(valid), key=lambda item: item[0], reverse=True))


def _official_candidate() -> Candidate:
    return Candidate(
        candidate_id="current_official",
        family="official",
        description="Stage78-1 current hand-written tiers",
        tiers=_normalize_tiers(CURRENT_TIERS),
    )


def _candidate_lock_pct(max_profit_pct: float, tiers: tuple[tuple[float, float], ...]) -> tuple[float, float]:
    for trigger, lock in tiers:
        if max_profit_pct >= trigger:
            return trigger, lock
    return 0.0, 0.0


def _pct_pnl(direction: str, entry_price: float, exit_price: float) -> float:
    if direction == "long":
        return exit_price / entry_price - 1.0
    return entry_price / exit_price - 1.0


def _profit_pct_at_close(direction: str, entry_price: float, close_price: float) -> float:
    if direction == "long":
        return close_price / entry_price - 1.0
    return entry_price / close_price - 1.0


def _lock_stop_hit(direction: str, entry_price: float, close_price: float, lock_pct: float) -> bool:
    if lock_pct <= 0:
        return False
    stop_price = entry_price * (1 + lock_pct) if direction == "long" else entry_price * (1 - lock_pct)
    if direction == "long":
        return close_price <= stop_price
    return close_price >= stop_price


def _simulate_candidate_on_path(
    row: dict[str, Any],
    bars: pd.DataFrame,
    candidate: Candidate,
) -> dict[str, Any]:
    entry_date = pd.Timestamp(row["entry_date"]).normalize()
    exit_date = pd.Timestamp(row["exit_date"]).normalize()
    entry_price = float(row["entry_price"])
    actual_exit_price = float(row["exit_price"])
    direction = str(row["direction"])

    path = bars[(bars["date"] >= entry_date) & (bars["date"] <= exit_date)].copy()
    if path.empty:
        actual_pnl_pct = _pct_pnl(direction, entry_price, actual_exit_price)
        return {
            "sim_exit_date": exit_date,
            "sim_exit_price": actual_exit_price,
            "sim_pnl_pct": actual_pnl_pct,
            "stop_hit": 0,
            "stop_tier_trigger": 0.0,
            "stop_tier_lock": 0.0,
            "max_close_profit_pct": 0.0,
        }

    max_profit_pct = -math.inf
    active_trigger = 0.0
    active_lock = 0.0
    for bar in path.to_dict("records"):
        close_price = float(bar["close"])
        max_profit_pct = max(max_profit_pct, _profit_pct_at_close(direction, entry_price, close_price))
        trigger, lock = _candidate_lock_pct(max_profit_pct, candidate.tiers)
        if lock > 0:
            active_trigger = trigger
            active_lock = lock
        if _lock_stop_hit(direction, entry_price, close_price, active_lock):
            return {
                "sim_exit_date": pd.Timestamp(bar["date"]).normalize(),
                "sim_exit_price": close_price,
                "sim_pnl_pct": _pct_pnl(direction, entry_price, close_price),
                "stop_hit": 1,
                "stop_tier_trigger": active_trigger,
                "stop_tier_lock": active_lock,
                "max_close_profit_pct": float(max_profit_pct),
            }

    return {
        "sim_exit_date": exit_date,
        "sim_exit_price": actual_exit_price,
        "sim_pnl_pct": _pct_pnl(direction, entry_price, actual_exit_price),
        "stop_hit": 0,
        "stop_tier_trigger": active_trigger,
        "stop_tier_lock": active_lock,
        "max_close_profit_pct": float(max_profit_pct),
    }


def _candidate_generators() -> list[Candidate]:
    candidates: list[Candidate] = [_official_candidate()]
    triggers = [0.02, 0.03, 0.05, 0.10, 0.20, 0.30]

    candidates.append(
        Candidate(
            candidate_id="no_profit_lock",
            family="none",
            description="No profit-lock tiers",
            tiers=tuple(),
        )
    )

    for scale in [x / 20 for x in range(4, 37)]:
        tiers = [(trigger, min(trigger * 0.98, lock * scale)) for trigger, lock in CURRENT_TIERS]
        candidates.append(
            Candidate(
                candidate_id=f"scale_current_{scale:.2f}",
                family="scale_current",
                description=f"Scale current lock percentages by {scale:.2f}",
                tiers=_normalize_tiers(tiers),
            )
        )

    for retain in [x / 100 for x in range(5, 96, 5)]:
        tiers = [(trigger, trigger * retain) for trigger in triggers]
        candidates.append(
            Candidate(
                candidate_id=f"uniform_retain_{retain:.2f}",
                family="uniform_retain",
                description=f"Lock a uniform {retain:.0%} of trigger profit",
                tiers=_normalize_tiers(tiers),
            )
        )

    for min_trigger in [0.02, 0.03, 0.05, 0.10, 0.20]:
        tiers = [(trigger, lock) for trigger, lock in CURRENT_TIERS if trigger >= min_trigger]
        candidates.append(
            Candidate(
                candidate_id=f"drop_below_{min_trigger:.2f}",
                family="drop_low_tiers",
                description=f"Keep only tiers whose trigger >= {min_trigger:.0%}",
                tiers=_normalize_tiers(tiers),
            )
        )

    low_retains = [0.05, 0.10, 0.20, 0.30, 0.40, 0.50, 0.60]
    high_retains = [0.40, 0.50, 0.60, 0.70, 0.80, 0.90]
    for low_retain in low_retains:
        for high_retain in high_retains:
            tiers = []
            for trigger in triggers:
                if trigger <= 0.05:
                    retain = low_retain
                elif trigger >= 0.10:
                    retain = high_retain
                else:
                    retain = (low_retain + high_retain) / 2
                tiers.append((trigger, trigger * retain))
            candidates.append(
                Candidate(
                    candidate_id=f"two_segment_l{low_retain:.2f}_h{high_retain:.2f}",
                    family="two_segment_retain",
                    description=f"Low tiers retain {low_retain:.0%}, high tiers retain {high_retain:.0%}",
                    tiers=_normalize_tiers(tiers),
                )
            )

    smooth_lows = [0.05, 0.10, 0.20, 0.30, 0.40]
    smooth_highs = [0.55, 0.65, 0.75, 0.85, 0.95]
    min_trigger = min(triggers)
    max_trigger = max(triggers)
    for low_retain in smooth_lows:
        for high_retain in smooth_highs:
            tiers = []
            for trigger in triggers:
                x = (math.log(trigger) - math.log(min_trigger)) / (math.log(max_trigger) - math.log(min_trigger))
                retain = low_retain + (high_retain - low_retain) * x
                tiers.append((trigger, trigger * retain))
            candidates.append(
                Candidate(
                    candidate_id=f"smooth_log_l{low_retain:.2f}_h{high_retain:.2f}",
                    family="smooth_log_retain",
                    description=f"Log-smooth retain from {low_retain:.0%} to {high_retain:.0%}",
                    tiers=_normalize_tiers(tiers),
                )
            )

    shifted_sets = [
        ("delay_low", [0.03, 0.05, 0.08, 0.12, 0.20, 0.30]),
        ("coarse_four", [0.05, 0.10, 0.20, 0.30]),
        ("late_trend", [0.08, 0.12, 0.20, 0.30]),
        ("early_dense", [0.015, 0.025, 0.04, 0.06, 0.10, 0.20, 0.30]),
    ]
    for name, shifted_triggers in shifted_sets:
        for retain in [0.25, 0.40, 0.55, 0.70, 0.85]:
            candidates.append(
                Candidate(
                    candidate_id=f"{name}_retain_{retain:.2f}",
                    family="shifted_trigger",
                    description=f"{name} trigger set with {retain:.0%} retain",
                    tiers=_normalize_tiers([(trigger, trigger * retain) for trigger in shifted_triggers]),
                )
            )

    dedup: dict[tuple[tuple[float, float], ...], Candidate] = {}
    for candidate in candidates:
        dedup.setdefault(candidate.tiers, candidate)
    return list(dedup.values())


def _prepare_trade_paths() -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    trades = _load_trades()
    pairs = _pair_round_trips(trades)
    pairs["entry_date"] = pd.to_datetime(pairs["entry_date"]).dt.normalize()
    pairs["exit_date"] = pd.to_datetime(pairs["exit_date"]).dt.normalize()
    pairs["entry_year"] = pd.to_datetime(pairs["entry_datetime"]).dt.year
    pairs["product_vt_symbol"] = pairs["vt_symbol"].map(_product_from_vt_symbol)
    pairs["actual_pnl_pct"] = pairs.apply(
        lambda row: _pct_pnl(str(row["direction"]), float(row["entry_price"]), float(row["exit_price"])),
        axis=1,
    )
    pairs["weight"] = pd.to_numeric(pairs["volume"], errors="coerce").fillna(1.0).clip(lower=1.0)
    bars_by_symbol = _load_bars_for_pairs(pairs)
    pairs = pairs[pairs["vt_symbol"].isin(bars_by_symbol)].reset_index(drop=True)
    pairs["leg_id"] = range(len(pairs))
    return pairs, bars_by_symbol


def _build_simulation_frame(pairs: pd.DataFrame, bars_by_symbol: dict[str, pd.DataFrame], candidates: list[Candidate]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    pair_records = pairs.to_dict("records")
    for candidate_index, candidate in enumerate(candidates, start=1):
        for row in pair_records:
            bars = bars_by_symbol.get(str(row["vt_symbol"]))
            if bars is None:
                continue
            sim = _simulate_candidate_on_path(row, bars, candidate)
            rows.append(
                {
                    "candidate_id": candidate.candidate_id,
                    "candidate_family": candidate.family,
                    "candidate_description": candidate.description,
                    "candidate_tiers": candidate.tiers_string,
                    "round_no": candidate_index,
                    "leg_id": int(row["leg_id"]),
                    "entry_year": int(row["entry_year"]),
                    "product_vt_symbol": str(row["product_vt_symbol"]),
                    "direction": str(row["direction"]),
                    "volume": float(row["volume"]),
                    "weight": float(row["weight"]),
                    "actual_pnl_pct": float(row["actual_pnl_pct"]),
                    "sim_pnl_pct": float(sim["sim_pnl_pct"]),
                    "stop_hit": int(sim["stop_hit"]),
                    "stop_tier_trigger": float(sim["stop_tier_trigger"]),
                    "stop_tier_lock": float(sim["stop_tier_lock"]),
                    "sim_exit_date": sim["sim_exit_date"],
                    "actual_exit_date": row["exit_date"],
                    "sim_exit_before_actual": int(pd.Timestamp(sim["sim_exit_date"]) < pd.Timestamp(row["exit_date"])),
                    "max_close_profit_pct": float(sim["max_close_profit_pct"]),
                }
            )
    return pd.DataFrame(rows)


def _weighted_sum(df: pd.DataFrame, column: str) -> float:
    if df.empty:
        return 0.0
    weights = pd.to_numeric(df["weight"], errors="coerce").fillna(1.0)
    values = pd.to_numeric(df[column], errors="coerce").fillna(0.0)
    return float((values * weights).sum())


def _candidate_summary(sim_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    official = sim_df[sim_df["candidate_id"].eq("current_official")][["leg_id", "sim_pnl_pct"]].rename(
        columns={"sim_pnl_pct": "official_sim_pnl_pct"}
    )
    joined = sim_df.merge(official, on="leg_id", how="left")
    joined["delta_vs_official_pct"] = joined["sim_pnl_pct"] - joined["official_sim_pnl_pct"]

    grouped = joined.groupby(["candidate_id", "candidate_family", "candidate_description", "candidate_tiers"], dropna=False)
    summary = grouped.agg(
        experiment_round=("round_no", "first"),
        trade_legs=("leg_id", "count"),
        stop_hit_rate=("stop_hit", "mean"),
        early_exit_rate=("sim_exit_before_actual", "mean"),
        weighted_pnl_sum=("sim_pnl_pct", lambda s: 0.0),
        weighted_delta_sum=("delta_vs_official_pct", lambda s: 0.0),
        avg_delta_pct=("delta_vs_official_pct", "mean"),
        median_delta_pct=("delta_vs_official_pct", "median"),
    ).reset_index()

    weighted_rows: list[dict[str, Any]] = []
    for candidate_id, group in joined.groupby("candidate_id"):
        weighted_rows.append(
            {
                "candidate_id": candidate_id,
                "weighted_pnl_sum": _weighted_sum(group, "sim_pnl_pct"),
                "weighted_delta_sum": _weighted_sum(group, "delta_vs_official_pct"),
            }
        )
    weighted_df = pd.DataFrame(weighted_rows)
    summary = summary.drop(columns=["weighted_pnl_sum", "weighted_delta_sum"]).merge(weighted_df, on="candidate_id", how="left")

    year_rows: list[dict[str, Any]] = []
    for (candidate_id, year), group in joined.groupby(["candidate_id", "entry_year"]):
        year_rows.append(
            {
                "candidate_id": candidate_id,
                "entry_year": int(year),
                "weighted_delta_sum": _weighted_sum(group, "delta_vs_official_pct"),
                "avg_delta_pct": float(group["delta_vs_official_pct"].mean()),
                "trade_legs": int(len(group)),
            }
        )
    year_summary = pd.DataFrame(year_rows)

    start_rows: list[dict[str, Any]] = []
    years = sorted(int(year) for year in joined["entry_year"].dropna().unique())
    for candidate_id, group in joined.groupby("candidate_id"):
        for start_year in years:
            subset = group[group["entry_year"] >= start_year]
            start_rows.append(
                {
                    "candidate_id": candidate_id,
                    "start_year": start_year,
                    "weighted_delta_sum": _weighted_sum(subset, "delta_vs_official_pct"),
                    "avg_delta_pct": float(subset["delta_vs_official_pct"].mean()) if not subset.empty else 0.0,
                    "trade_legs": int(len(subset)),
                }
            )
    start_summary = pd.DataFrame(start_rows)

    year_win = year_summary.groupby("candidate_id")["weighted_delta_sum"].apply(lambda s: int((s > 0).sum())).rename("year_win_count")
    start_win = start_summary.groupby("candidate_id")["weighted_delta_sum"].apply(lambda s: int((s > 0).sum())).rename("start_year_win_count")
    min_year = year_summary.groupby("candidate_id")["weighted_delta_sum"].min().rename("min_year_delta_sum")
    min_start = start_summary.groupby("candidate_id")["weighted_delta_sum"].min().rename("min_start_delta_sum")
    summary = (
        summary.merge(year_win, on="candidate_id", how="left")
        .merge(start_win, on="candidate_id", how="left")
        .merge(min_year, on="candidate_id", how="left")
        .merge(min_start, on="candidate_id", how="left")
    )
    summary["robust_score"] = (
        summary["weighted_delta_sum"]
        + summary["min_year_delta_sum"].clip(upper=0.0) * 2.0
        + summary["min_start_delta_sum"].clip(upper=0.0)
    )
    summary.sort_values(["robust_score", "weighted_delta_sum"], ascending=False, inplace=True)
    return summary, year_summary, start_summary


def _walk_forward_selection(summary: pd.DataFrame, sim_df: pd.DataFrame) -> pd.DataFrame:
    official = sim_df[sim_df["candidate_id"].eq("current_official")][["leg_id", "sim_pnl_pct"]].rename(
        columns={"sim_pnl_pct": "official_sim_pnl_pct"}
    )
    joined = sim_df.merge(official, on="leg_id", how="left")
    joined["delta_vs_official_pct"] = joined["sim_pnl_pct"] - joined["official_sim_pnl_pct"]

    rows: list[dict[str, Any]] = []
    test_years = [2023, 2024, 2025, 2026]
    meta = summary.set_index("candidate_id")[["candidate_family", "candidate_description", "candidate_tiers"]].to_dict("index")
    for test_year in test_years:
        train = joined[joined["entry_year"] < test_year]
        test = joined[joined["entry_year"].eq(test_year)]
        if train.empty or test.empty:
            continue
        scores = []
        for candidate_id, group in train.groupby("candidate_id"):
            scores.append(
                {
                    "candidate_id": candidate_id,
                    "train_score": _weighted_sum(group, "delta_vs_official_pct"),
                    "train_min_year": group.groupby("entry_year").apply(lambda g: _weighted_sum(g, "delta_vs_official_pct")).min(),
                }
            )
        score_df = pd.DataFrame(scores)
        score_df["train_robust_score"] = score_df["train_score"] + score_df["train_min_year"].clip(upper=0.0) * 2.0
        selected_id = str(score_df.sort_values(["train_robust_score", "train_score"], ascending=False).iloc[0]["candidate_id"])
        selected_test = test[test["candidate_id"].eq(selected_id)]
        candidate_meta = meta.get(selected_id, {})
        rows.append(
            {
                "test_year": test_year,
                "selected_candidate_id": selected_id,
                "selected_family": candidate_meta.get("candidate_family", ""),
                "selected_description": candidate_meta.get("candidate_description", ""),
                "selected_tiers": candidate_meta.get("candidate_tiers", ""),
                "train_robust_score": float(score_df[score_df["candidate_id"].eq(selected_id)]["train_robust_score"].iloc[0]),
                "test_weighted_delta_sum": _weighted_sum(selected_test, "delta_vs_official_pct"),
                "test_avg_delta_pct": float(selected_test["delta_vs_official_pct"].mean()) if not selected_test.empty else 0.0,
                "test_trade_legs": int(len(selected_test)),
            }
        )
    return pd.DataFrame(rows)


def _bootstrap_selection(sim_df: pd.DataFrame, rounds: int = BOOTSTRAP_ROUNDS) -> pd.DataFrame:
    rng = random.Random(RANDOM_SEED)
    official = sim_df[sim_df["candidate_id"].eq("current_official")][["leg_id", "sim_pnl_pct"]].rename(
        columns={"sim_pnl_pct": "official_sim_pnl_pct"}
    )
    joined = sim_df.merge(official, on="leg_id", how="left")
    joined["delta_vs_official_pct"] = joined["sim_pnl_pct"] - joined["official_sim_pnl_pct"]
    leg_ids = sorted(int(x) for x in joined["leg_id"].unique())
    candidate_ids = sorted(str(x) for x in joined["candidate_id"].unique())
    rows: list[dict[str, Any]] = []

    for round_no in range(1, rounds + 1):
        shuffled = leg_ids[:]
        rng.shuffle(shuffled)
        split = int(len(shuffled) * 0.70)
        train_ids = set(shuffled[:split])
        test_ids = set(shuffled[split:])
        train = joined[joined["leg_id"].isin(train_ids)]
        test = joined[joined["leg_id"].isin(test_ids)]

        scores = []
        for candidate_id in candidate_ids:
            group = train[train["candidate_id"].eq(candidate_id)]
            scores.append(
                {
                    "candidate_id": candidate_id,
                    "train_score": _weighted_sum(group, "delta_vs_official_pct"),
                }
            )
        score_df = pd.DataFrame(scores).sort_values("train_score", ascending=False)
        selected_id = str(score_df.iloc[0]["candidate_id"])
        selected_test = test[test["candidate_id"].eq(selected_id)]
        rows.append(
            {
                "bootstrap_round": round_no,
                "selected_candidate_id": selected_id,
                "train_score": float(score_df.iloc[0]["train_score"]),
                "test_weighted_delta_sum": _weighted_sum(selected_test, "delta_vs_official_pct"),
                "test_positive": int(_weighted_sum(selected_test, "delta_vs_official_pct") > 0),
            }
        )
    return pd.DataFrame(rows)


def _official_tier_effectiveness(sim_df: pd.DataFrame, pairs: pd.DataFrame, bars_by_symbol: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    pair_records = pairs.to_dict("records")
    tiers_ascending = sorted(CURRENT_TIERS, key=lambda item: item[0])
    for trigger, lock in tiers_ascending:
        crossed = 0
        highest = 0
        stop_hit = 0
        stop_hit_before_actual = 0
        weighted_help = 0.0
        help_count = 0
        for row in pair_records:
            bars = bars_by_symbol.get(str(row["vt_symbol"]))
            if bars is None:
                continue
            sim = _simulate_candidate_on_path(row, bars, _official_candidate())
            max_profit = float(sim["max_close_profit_pct"])
            if max_profit >= trigger:
                crossed += 1
            higher_triggers = [higher for higher, _ in CURRENT_TIERS if higher > trigger]
            if max_profit >= trigger and (not higher_triggers or max_profit < min(higher_triggers)):
                highest += 1
            if int(sim["stop_hit"]) and abs(float(sim["stop_tier_trigger"]) - trigger) < 1e-9:
                stop_hit += 1
                if pd.Timestamp(sim["sim_exit_date"]) < pd.Timestamp(row["exit_date"]):
                    stop_hit_before_actual += 1
                actual_pnl = float(row["actual_pnl_pct"])
                help_value = float(sim["sim_pnl_pct"]) - actual_pnl
                weighted_help += help_value * float(row["weight"])
                if help_value > 0:
                    help_count += 1
        rows.append(
            {
                "tier_label": f"{trigger:.1%}->{lock:.1%}",
                "trigger_pct": trigger,
                "lock_pct": lock,
                "crossed_trade_legs": crossed,
                "highest_reached_trade_legs": highest,
                "sim_stop_hit_trade_legs": stop_hit,
                "sim_stop_hit_before_actual_exit": stop_hit_before_actual,
                "positive_help_count": help_count,
                "weighted_help_vs_actual_pct_sum": weighted_help,
            }
        )
    return pd.DataFrame(rows)


def _format_table(df: pd.DataFrame, columns: list[str], max_rows: int = 20) -> str:
    if df.empty:
        return "- 无数据"
    view = df[[column for column in columns if column in df.columns]].head(max_rows).copy()
    return view.to_markdown(index=False)


def _write_report(
    *,
    candidates: list[Candidate],
    tier_effectiveness: pd.DataFrame,
    candidate_summary: pd.DataFrame,
    walk_forward: pd.DataFrame,
    bootstrap: pd.DataFrame,
    paths: dict[str, Path],
) -> dict[str, Any]:
    top = candidate_summary.head(20).copy()
    robust_best = candidate_summary.iloc[0].to_dict() if not candidate_summary.empty else {}
    official_row = candidate_summary[candidate_summary["candidate_id"].eq("current_official")]
    bootstrap_positive_rate = float(bootstrap["test_positive"].mean()) if not bootstrap.empty else 0.0
    wf_positive_count = int((walk_forward["test_weighted_delta_sum"] > 0).sum()) if not walk_forward.empty else 0
    pass_event_gate = bool(
        robust_best
        and robust_best.get("candidate_id") != "current_official"
        and float(robust_best.get("weighted_delta_sum", 0.0)) > 0
        and int(robust_best.get("start_year_win_count", 0)) >= 5
        and float(robust_best.get("min_year_delta_sum", 0.0)) >= -0.50
        and wf_positive_count >= 3
        and bootstrap_positive_rate >= 0.60
    )
    decision = {
        "candidate_count": len(candidates),
        "bootstrap_rounds": BOOTSTRAP_ROUNDS,
        "best_candidate_id": robust_best.get("candidate_id", ""),
        "best_family": robust_best.get("candidate_family", ""),
        "best_tiers": robust_best.get("candidate_tiers", ""),
        "best_weighted_delta_sum": robust_best.get("weighted_delta_sum", 0.0),
        "best_start_year_win_count": robust_best.get("start_year_win_count", 0),
        "best_min_year_delta_sum": robust_best.get("min_year_delta_sum", 0.0),
        "walk_forward_positive_count": wf_positive_count,
        "bootstrap_positive_rate": bootstrap_positive_rate,
        "pass_event_gate": pass_event_gate,
        "next_step": "engine_validate_best_candidate" if pass_event_gate else "do_not_promote_keep_current_tiers",
        "official_rank_by_robust_score": (
            int(candidate_summary.reset_index(drop=True).index[candidate_summary["candidate_id"].eq("current_official")][0]) + 1
            if not official_row.empty
            else None
        ),
    }

    report = f"""# Stage273 盈利锁定分层有效性与100+候选稳健搜索

## 研究问题

- 当前每一层锁盈是否真的在历史路径里起作用。
- 如果起作用，作用来自哪里：触发、成为最高保护档、还是实际被止损命中。
- 是否能通过统计实验找到更好的参数，同时避免过拟合。

## 方法

- 使用 Stage78-1 已发生交易腿和 vn.py 本地日线数据。
- 按策略真实逻辑重放：锁盈触发使用收盘最大浮盈，止损触发也使用收盘价。
- 生成低自由度候选 `{len(candidates)}` 个，不做逐档任意网格搜索。
- 做 walk-forward 年度选择、起始年份检验、`{BOOTSTRAP_ROUNDS}` 轮 bootstrap 反证。
- 本阶段是事件级/交易腿级近似，不直接替代组合引擎回测；只有通过事件门槛才进入引擎级 A/C。

## 外部调研判断

- Walk-forward 和 out-of-sample 是交易参数优化的基本防线。
- Purged/CPCV 思路提醒我们：持仓窗口相互重叠时，普通随机交叉验证会夸大稳定性。
- PBO/White reality check 的核心警告是：候选越多，样本内最优越可能是噪声，因此本阶段只看低自由度结构，并把 bootstrap 作为反证而不是选最优的理由。

## 当前档位逐层有效性

{_format_table(tier_effectiveness, ["tier_label", "crossed_trade_legs", "highest_reached_trade_legs", "sim_stop_hit_trade_legs", "sim_stop_hit_before_actual_exit", "positive_help_count", "weighted_help_vs_actual_pct_sum"], 20)}

## 候选搜索判定

```json
{json.dumps(decision, ensure_ascii=False, indent=2)}
```

## Top 20 候选

{_format_table(top, ["candidate_id", "candidate_family", "experiment_round", "weighted_delta_sum", "robust_score", "year_win_count", "start_year_win_count", "min_year_delta_sum", "min_start_delta_sum", "stop_hit_rate", "early_exit_rate", "candidate_tiers"], 20)}

## Walk-forward 选择结果

{_format_table(walk_forward, ["test_year", "selected_candidate_id", "selected_family", "train_robust_score", "test_weighted_delta_sum", "test_avg_delta_pct", "test_trade_legs", "selected_tiers"], 20)}

## Bootstrap 结果

- bootstrap轮数：`{BOOTSTRAP_ROUNDS}`
- 样本内选出的候选在留出样本为正的比例：`{bootstrap_positive_rate:.2%}`
- 解释：若该比例不高，即使有样本内最优，也不应认为参数稳定。

## 结论

- 若 `pass_event_gate=false`，不得进入正式参数替换；最多保留为归因经验。
- 若 `pass_event_gate=true`，也只表示值得做引擎级 A/C，不代表可替换 78-1。

## 输出文件

- tier_effectiveness：`{paths["tier_effectiveness"].name}`
- candidate_summary：`{paths["candidate_summary"].name}`
- walk_forward：`{paths["walk_forward"].name}`
- bootstrap：`{paths["bootstrap"].name}`
- decision：`{paths["decision"].name}`
"""
    paths["report"].write_text(report, encoding="utf-8")
    paths["decision"].write_text(json.dumps(decision, ensure_ascii=False, indent=2), encoding="utf-8")
    return decision


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    pairs, bars_by_symbol = _prepare_trade_paths()
    candidates = _candidate_generators()
    if len(candidates) < 100:
        raise RuntimeError(f"Expected at least 100 candidates, got {len(candidates)}")

    sim_df = _build_simulation_frame(pairs, bars_by_symbol, candidates)
    candidate_summary, year_summary, start_summary = _candidate_summary(sim_df)
    walk_forward = _walk_forward_selection(candidate_summary, sim_df)
    bootstrap = _bootstrap_selection(sim_df, BOOTSTRAP_ROUNDS)
    tier_effectiveness = _official_tier_effectiveness(sim_df, pairs, bars_by_symbol)

    paths = {
        "sim_detail": OUTPUT_DIR / f"{OUTPUT_PREFIX}_sim_detail_{MODEL_TAG}.csv",
        "tier_effectiveness": OUTPUT_DIR / f"{OUTPUT_PREFIX}_tier_effectiveness_{MODEL_TAG}.csv",
        "candidate_summary": OUTPUT_DIR / f"{OUTPUT_PREFIX}_candidate_summary_{MODEL_TAG}.csv",
        "year_summary": OUTPUT_DIR / f"{OUTPUT_PREFIX}_year_summary_{MODEL_TAG}.csv",
        "start_summary": OUTPUT_DIR / f"{OUTPUT_PREFIX}_start_summary_{MODEL_TAG}.csv",
        "walk_forward": OUTPUT_DIR / f"{OUTPUT_PREFIX}_walk_forward_{MODEL_TAG}.csv",
        "bootstrap": OUTPUT_DIR / f"{OUTPUT_PREFIX}_bootstrap_{MODEL_TAG}.csv",
        "decision": OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json",
        "report": OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md",
    }
    sim_df.to_csv(paths["sim_detail"], index=False, encoding="utf-8-sig")
    tier_effectiveness.to_csv(paths["tier_effectiveness"], index=False, encoding="utf-8-sig")
    candidate_summary.to_csv(paths["candidate_summary"], index=False, encoding="utf-8-sig")
    year_summary.to_csv(paths["year_summary"], index=False, encoding="utf-8-sig")
    start_summary.to_csv(paths["start_summary"], index=False, encoding="utf-8-sig")
    walk_forward.to_csv(paths["walk_forward"], index=False, encoding="utf-8-sig")
    bootstrap.to_csv(paths["bootstrap"], index=False, encoding="utf-8-sig")

    decision = _write_report(
        candidates=candidates,
        tier_effectiveness=tier_effectiveness,
        candidate_summary=candidate_summary,
        walk_forward=walk_forward,
        bootstrap=bootstrap,
        paths=paths,
    )
    print(json.dumps(decision, ensure_ascii=False, indent=2))
    print(f"report: {paths['report']}")


if __name__ == "__main__":
    main()
