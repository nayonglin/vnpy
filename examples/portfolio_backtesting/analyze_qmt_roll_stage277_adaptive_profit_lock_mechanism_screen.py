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
MODEL_TAG: str = "stage277_adaptive_profit_lock_mechanism_screen_v1"
OUTPUT_PREFIX: str = "qmt_roll_stage277_adaptive_profit_lock_mechanism_screen"


@dataclass(frozen=True)
class Candidate:
    candidate_id: str
    description: str
    atr_period: int
    atr_multiplier: float
    activation_pct: float
    anchor_mode: str = "since_entry_extreme"


CANDIDATES: tuple[Candidate, ...] = (
    Candidate(
        candidate_id="current_plus_chandelier_22_3_after_5pct",
        description="当前锁盈 + 标准Chandelier/ATR 22日3倍保护层，收盘最大浮盈>=5%后生效",
        atr_period=22,
        atr_multiplier=3.0,
        activation_pct=0.05,
    ),
    Candidate(
        candidate_id="current_plus_chandelier_22_3_after_10pct",
        description="当前锁盈 + 标准Chandelier/ATR 22日3倍保护层，收盘最大浮盈>=10%后生效",
        atr_period=22,
        atr_multiplier=3.0,
        activation_pct=0.10,
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
        enriched[vt_symbol] = df
    return enriched


def _official_stop_price(direction: str, entry_price: float, lock_pct: float) -> float | None:
    if lock_pct <= 0:
        return None
    if direction == "long":
        return entry_price * (1 + lock_pct)
    return entry_price * (1 - lock_pct)


def _stop_hit(direction: str, close_price: float, stop_price: float | None) -> bool:
    if stop_price is None:
        return False
    if direction == "long":
        return close_price <= stop_price
    return close_price >= stop_price


def _chandelier_stop_price(
    *,
    direction: str,
    path_high: float,
    path_low: float,
    atr_value: float,
    multiplier: float,
) -> float | None:
    if not math.isfinite(atr_value) or atr_value <= 0:
        return None
    if direction == "long":
        return path_high - multiplier * atr_value
    return path_low + multiplier * atr_value


def _combine_stops(direction: str, official_stop: float | None, chandelier_stop: float | None) -> tuple[float | None, str]:
    stops = [(official_stop, "official"), (chandelier_stop, "chandelier")]
    valid = [(price, source) for price, source in stops if price is not None and math.isfinite(float(price))]
    if not valid:
        return None, "none"
    if len(valid) == 1:
        return float(valid[0][0]), valid[0][1]
    if direction == "long":
        selected = max(valid, key=lambda item: float(item[0]))
    else:
        selected = min(valid, key=lambda item: float(item[0]))
    if abs(float(valid[0][0]) - float(valid[1][0])) < 1e-9:
        return float(selected[0]), "official_and_chandelier"
    return float(selected[0]), selected[1]


def _simulate_current_on_path(row: dict[str, Any], bars: pd.DataFrame) -> dict[str, Any]:
    entry_date = pd.Timestamp(row["entry_date"]).normalize()
    exit_date = pd.Timestamp(row["exit_date"]).normalize()
    entry_price = float(row["entry_price"])
    actual_exit_price = float(row["exit_price"])
    direction = str(row["direction"])
    path = bars[(bars["date"] >= entry_date) & (bars["date"] <= exit_date)].copy()
    if path.empty:
        return {
            "exit_date": exit_date,
            "exit_price": actual_exit_price,
            "pnl_pct": _pct_pnl(direction, entry_price, actual_exit_price),
            "stop_hit": 0,
            "stop_source": "actual_exit",
            "max_close_profit_pct": 0.0,
            "active_lock_pct": 0.0,
        }

    max_profit_pct = -math.inf
    active_lock = 0.0
    for bar in path.to_dict("records"):
        close_price = float(bar["close"])
        max_profit_pct = max(max_profit_pct, _profit_pct_at_close(direction, entry_price, close_price))
        _, lock_pct = _candidate_lock_pct(max_profit_pct, tuple(CURRENT_TIERS))
        active_lock = max(active_lock, lock_pct)
        stop_price = _official_stop_price(direction, entry_price, active_lock)
        if _stop_hit(direction, close_price, stop_price):
            return {
                "exit_date": pd.Timestamp(bar["date"]).normalize(),
                "exit_price": close_price,
                "pnl_pct": _pct_pnl(direction, entry_price, close_price),
                "stop_hit": 1,
                "stop_source": "official",
                "max_close_profit_pct": float(max_profit_pct),
                "active_lock_pct": float(active_lock),
            }

    return {
        "exit_date": exit_date,
        "exit_price": actual_exit_price,
        "pnl_pct": _pct_pnl(direction, entry_price, actual_exit_price),
        "stop_hit": 0,
        "stop_source": "actual_exit",
        "max_close_profit_pct": float(max_profit_pct),
        "active_lock_pct": float(active_lock),
    }


def _simulate_candidate_on_path(row: dict[str, Any], bars: pd.DataFrame, candidate: Candidate) -> dict[str, Any]:
    entry_date = pd.Timestamp(row["entry_date"]).normalize()
    exit_date = pd.Timestamp(row["exit_date"]).normalize()
    entry_price = float(row["entry_price"])
    actual_exit_price = float(row["exit_price"])
    direction = str(row["direction"])
    path = bars[(bars["date"] >= entry_date) & (bars["date"] <= exit_date)].copy()
    if path.empty:
        return {
            "exit_date": exit_date,
            "exit_price": actual_exit_price,
            "pnl_pct": _pct_pnl(direction, entry_price, actual_exit_price),
            "stop_hit": 0,
            "stop_source": "actual_exit",
            "max_close_profit_pct": 0.0,
            "active_lock_pct": 0.0,
            "chandelier_active": 0,
            "effective_stop_price": None,
        }

    max_profit_pct = -math.inf
    active_lock = 0.0
    path_high = -math.inf
    path_low = math.inf
    for bar in path.to_dict("records"):
        close_price = float(bar["close"])
        path_high = max(path_high, float(bar["high"]))
        path_low = min(path_low, float(bar["low"]))
        max_profit_pct = max(max_profit_pct, _profit_pct_at_close(direction, entry_price, close_price))
        _, lock_pct = _candidate_lock_pct(max_profit_pct, tuple(CURRENT_TIERS))
        active_lock = max(active_lock, lock_pct)

        official_stop = _official_stop_price(direction, entry_price, active_lock)
        chandelier_stop = None
        chandelier_active = int(max_profit_pct >= candidate.activation_pct)
        if chandelier_active:
            chandelier_stop = _chandelier_stop_price(
                direction=direction,
                path_high=path_high,
                path_low=path_low,
                atr_value=float(bar.get("atr22", float("nan"))),
                multiplier=candidate.atr_multiplier,
            )

        effective_stop, source = _combine_stops(direction, official_stop, chandelier_stop)
        if _stop_hit(direction, close_price, effective_stop):
            return {
                "exit_date": pd.Timestamp(bar["date"]).normalize(),
                "exit_price": close_price,
                "pnl_pct": _pct_pnl(direction, entry_price, close_price),
                "stop_hit": 1,
                "stop_source": source,
                "max_close_profit_pct": float(max_profit_pct),
                "active_lock_pct": float(active_lock),
                "chandelier_active": chandelier_active,
                "effective_stop_price": effective_stop,
            }

    return {
        "exit_date": exit_date,
        "exit_price": actual_exit_price,
        "pnl_pct": _pct_pnl(direction, entry_price, actual_exit_price),
        "stop_hit": 0,
        "stop_source": "actual_exit",
        "max_close_profit_pct": float(max_profit_pct),
        "active_lock_pct": float(active_lock),
        "chandelier_active": int(max_profit_pct >= candidate.activation_pct),
        "effective_stop_price": None,
    }


def _weighted_sum(df: pd.DataFrame, column: str) -> float:
    if df.empty:
        return 0.0
    values = pd.to_numeric(df[column], errors="coerce").fillna(0.0)
    weights = pd.to_numeric(df["weight"], errors="coerce").fillna(1.0)
    return float((values * weights).sum())


def _prepare_inputs() -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    trades = _load_trades()
    pairs = _pair_round_trips(trades)
    pairs["entry_date"] = pd.to_datetime(pairs["entry_date"]).dt.normalize()
    pairs["exit_date"] = pd.to_datetime(pairs["exit_date"]).dt.normalize()
    pairs["entry_year"] = pd.to_datetime(pairs["entry_datetime"]).dt.year
    pairs["weight"] = pd.to_numeric(pairs["volume"], errors="coerce").fillna(1.0).clip(lower=1.0)
    pairs["leg_id"] = range(len(pairs))
    bars_by_symbol = _enrich_bars(_load_bars_for_trades(trades))
    pairs = pairs[pairs["vt_symbol"].isin(bars_by_symbol)].reset_index(drop=True)
    pairs["leg_id"] = range(len(pairs))
    return pairs, bars_by_symbol


def _build_detail(pairs: pd.DataFrame, bars_by_symbol: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for row in pairs.to_dict("records"):
        bars = bars_by_symbol.get(str(row["vt_symbol"]))
        if bars is None:
            continue
        current = _simulate_current_on_path(row, bars)
        for candidate in CANDIDATES:
            candidate_result = _simulate_candidate_on_path(row, bars, candidate)
            rows.append(
                {
                    "candidate_id": candidate.candidate_id,
                    "candidate_description": candidate.description,
                    "leg_id": int(row["leg_id"]),
                    "vt_symbol": str(row["vt_symbol"]),
                    "product_vt_symbol": str(row["product_vt_symbol"]),
                    "direction": str(row["direction"]),
                    "entry_year": int(row["entry_year"]),
                    "entry_date": row["entry_date"],
                    "actual_exit_date": row["exit_date"],
                    "volume": float(row["volume"]),
                    "weight": float(row["weight"]),
                    "current_exit_date": current["exit_date"],
                    "current_pnl_pct": float(current["pnl_pct"]),
                    "current_stop_source": str(current["stop_source"]),
                    "candidate_exit_date": candidate_result["exit_date"],
                    "candidate_pnl_pct": float(candidate_result["pnl_pct"]),
                    "candidate_stop_source": str(candidate_result["stop_source"]),
                    "delta_vs_current_pct": float(candidate_result["pnl_pct"]) - float(current["pnl_pct"]),
                    "candidate_exits_before_current": int(
                        pd.Timestamp(candidate_result["exit_date"]) < pd.Timestamp(current["exit_date"])
                    ),
                    "candidate_exits_after_current": int(
                        pd.Timestamp(candidate_result["exit_date"]) > pd.Timestamp(current["exit_date"])
                    ),
                    "max_close_profit_pct": float(candidate_result["max_close_profit_pct"]),
                    "active_lock_pct": float(candidate_result["active_lock_pct"]),
                    "chandelier_active": int(candidate_result["chandelier_active"]),
                    "effective_stop_price": candidate_result["effective_stop_price"],
                }
            )
    return pd.DataFrame(rows)


def _summarize(detail: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    summary_rows: list[dict[str, Any]] = []
    for candidate_id, group in detail.groupby("candidate_id"):
        positive_deltas = group[group["delta_vs_current_pct"] > 0].copy()
        positive_sum = _weighted_sum(positive_deltas, "delta_vs_current_pct")
        top10_positive_sum = 0.0
        if not positive_deltas.empty and positive_sum > 0:
            top10_positive_sum = _weighted_sum(
                positive_deltas.assign(abs_weighted_delta=positive_deltas["delta_vs_current_pct"] * positive_deltas["weight"])
                .sort_values("abs_weighted_delta", ascending=False)
                .head(10),
                "delta_vs_current_pct",
            )
        year_delta = pd.Series(
            {
                int(year): _weighted_sum(year_group, "delta_vs_current_pct")
                for year, year_group in group.groupby("entry_year")
            }
        )
        summary_rows.append(
            {
                "candidate_id": candidate_id,
                "description": str(group["candidate_description"].iloc[0]),
                "trade_legs": int(len(group)),
                "chandelier_active_rate": float(group["chandelier_active"].mean()),
                "early_exit_rate": float(group["candidate_exits_before_current"].mean()),
                "weighted_delta_sum": _weighted_sum(group, "delta_vs_current_pct"),
                "avg_delta_pct": float(group["delta_vs_current_pct"].mean()),
                "median_delta_pct": float(group["delta_vs_current_pct"].median()),
                "positive_legs": int((group["delta_vs_current_pct"] > 0).sum()),
                "negative_legs": int((group["delta_vs_current_pct"] < 0).sum()),
                "year_win_count": int((year_delta > 0).sum()),
                "min_year_delta_sum": float(year_delta.min()) if not year_delta.empty else 0.0,
                "top10_positive_share": float(top10_positive_sum / positive_sum) if positive_sum > 0 else 0.0,
            }
        )
    summary = pd.DataFrame(summary_rows).sort_values(["weighted_delta_sum", "year_win_count"], ascending=False)

    year_rows: list[dict[str, Any]] = []
    for (candidate_id, entry_year), group in detail.groupby(["candidate_id", "entry_year"]):
        year_rows.append(
            {
                "candidate_id": candidate_id,
                "entry_year": int(entry_year),
                "weighted_delta_sum": _weighted_sum(group, "delta_vs_current_pct"),
                "trade_legs": int(len(group)),
                "early_exit_rate": float(group["candidate_exits_before_current"].mean()),
            }
        )
    by_year = pd.DataFrame(year_rows)

    product_rows: list[dict[str, Any]] = []
    for (candidate_id, product_vt_symbol), group in detail.groupby(["candidate_id", "product_vt_symbol"]):
        product_rows.append(
            {
                "candidate_id": candidate_id,
                "product_vt_symbol": product_vt_symbol,
                "weighted_delta_sum": _weighted_sum(group, "delta_vs_current_pct"),
                "trade_legs": int(len(group)),
                "positive_legs": int((group["delta_vs_current_pct"] > 0).sum()),
                "negative_legs": int((group["delta_vs_current_pct"] < 0).sum()),
            }
        )
    by_product = pd.DataFrame(product_rows).sort_values(
        ["candidate_id", "weighted_delta_sum"], ascending=[True, False]
    )

    source_rows: list[dict[str, Any]] = []
    for (candidate_id, source), group in detail.groupby(["candidate_id", "candidate_stop_source"]):
        source_rows.append(
            {
                "candidate_id": candidate_id,
                "candidate_stop_source": source,
                "weighted_delta_sum": _weighted_sum(group, "delta_vs_current_pct"),
                "trade_legs": int(len(group)),
                "early_exit_rate": float(group["candidate_exits_before_current"].mean()),
            }
        )
    by_source = pd.DataFrame(source_rows).sort_values(
        ["candidate_id", "weighted_delta_sum"], ascending=[True, False]
    )
    top_deltas = detail.reindex(detail["delta_vs_current_pct"].abs().sort_values(ascending=False).index).head(40)
    return summary, by_year, by_product, by_source, top_deltas


def _decision(summary: pd.DataFrame) -> dict[str, Any]:
    standard = summary[summary["candidate_id"].eq("current_plus_chandelier_22_3_after_5pct")]
    if standard.empty:
        return {"pass_screen": False, "next_step": "screen_failed_missing_standard_candidate"}
    row = standard.iloc[0]
    pass_screen = bool(
        float(row["weighted_delta_sum"]) > 0
        and int(row["year_win_count"]) >= 5
        and float(row["min_year_delta_sum"]) >= -0.50
        and int(row["positive_legs"]) >= 10
        and float(row["top10_positive_share"]) <= 0.85
    )
    return {
        "baseline": "official_stage78_1_defensive_50w_no_sizing_cap",
        "candidate": "current_plus_chandelier_22_3_after_5pct",
        "pass_screen": pass_screen,
        "standard_weighted_delta_sum": float(row["weighted_delta_sum"]),
        "standard_year_win_count": int(row["year_win_count"]),
        "standard_min_year_delta_sum": float(row["min_year_delta_sum"]),
        "standard_positive_legs": int(row["positive_legs"]),
        "standard_negative_legs": int(row["negative_legs"]),
        "standard_top10_positive_share": float(row["top10_positive_share"]),
        "next_step": "engine_validate_standard_chandelier_overlay" if pass_screen else "do_not_promote_keep_current_profit_lock",
    }


def _format_table(df: pd.DataFrame, columns: list[str], max_rows: int = 20) -> str:
    if df.empty:
        return "- 无数据"
    view = df[[column for column in columns if column in df.columns]].head(max_rows).copy()
    return view.to_markdown(index=False)


def _write_report(
    *,
    detail: pd.DataFrame,
    summary: pd.DataFrame,
    by_year: pd.DataFrame,
    by_product: pd.DataFrame,
    by_source: pd.DataFrame,
    top_deltas: pd.DataFrame,
    decision: dict[str, Any],
    paths: dict[str, Path],
) -> None:
    report = f"""# Stage277 波动率自适应盈利锁机制屏

## 研究问题

固定六档百分比锁盈已经停止继续调参。本阶段只验证一个更有第一性原理的方向：在当前 Stage78-1 固定锁盈基础上，叠加标准 Chandelier/ATR 保护层，看看它是否能更稳定地减少趋势末端回吐。

## A/B/C 预声明

- A：`official_stage78_1_defensive_50w_no_sizing_cap` 当前固定盈利锁。
- B：单独 Chandelier 退出不是完整策略，不单独作为交易系统评估。
- C：A + 标准 Chandelier/ATR 22日3倍保护层。

## 闸门

- 标准候选 `current_plus_chandelier_22_3_after_5pct` 必须 `weighted_delta_sum > 0`。
- 年份胜出至少 `5` 年。
- 最差年份加权差值不低于 `-0.50`。
- 正贡献腿数至少 `10`。
- top10 正贡献占比不高于 `85%`。

## 结果摘要

{_format_table(summary, ["candidate_id", "weighted_delta_sum", "year_win_count", "min_year_delta_sum", "positive_legs", "negative_legs", "top10_positive_share", "early_exit_rate", "chandelier_active_rate"])}

## 分年份

{_format_table(by_year, ["candidate_id", "entry_year", "weighted_delta_sum", "trade_legs", "early_exit_rate"], max_rows=20)}

## 分品种 Top

{_format_table(by_product, ["candidate_id", "product_vt_symbol", "weighted_delta_sum", "trade_legs", "positive_legs", "negative_legs"], max_rows=30)}

## 分离场来源

{_format_table(by_source, ["candidate_id", "candidate_stop_source", "weighted_delta_sum", "trade_legs", "early_exit_rate"], max_rows=20)}

## 绝对影响最大交易腿

{_format_table(top_deltas, ["candidate_id", "vt_symbol", "direction", "entry_date", "current_exit_date", "candidate_exit_date", "delta_vs_current_pct", "candidate_stop_source", "max_close_profit_pct"], max_rows=30)}

## 判定

```json
{json.dumps(decision, ensure_ascii=False, indent=2)}
```

## 结论

- 本阶段是成交腿级机制屏，不是完整组合回测。
- 如果 `pass_screen=false`，不进入策略引擎实现，不改正式 Stage78-1。
- 如果 `pass_screen=true`，下一步才允许写组合引擎 A/C 验证。

## 输出文件

- detail：`{paths["detail"].relative_to(PROJECT_DIR)}`
- summary：`{paths["summary"].relative_to(PROJECT_DIR)}`
- by_year：`{paths["by_year"].relative_to(PROJECT_DIR)}`
- by_product：`{paths["by_product"].relative_to(PROJECT_DIR)}`
- by_source：`{paths["by_source"].relative_to(PROJECT_DIR)}`
- top_deltas：`{paths["top_deltas"].relative_to(PROJECT_DIR)}`
- decision：`{paths["decision"].relative_to(PROJECT_DIR)}`
"""
    paths["report"].write_text(report, encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    pairs, bars_by_symbol = _prepare_inputs()
    detail = _build_detail(pairs, bars_by_symbol)
    summary, by_year, by_product, by_source, top_deltas = _summarize(detail)
    decision = _decision(summary)

    paths = {
        "detail": OUTPUT_DIR / f"{OUTPUT_PREFIX}_detail_{MODEL_TAG}.csv",
        "summary": OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv",
        "by_year": OUTPUT_DIR / f"{OUTPUT_PREFIX}_by_year_{MODEL_TAG}.csv",
        "by_product": OUTPUT_DIR / f"{OUTPUT_PREFIX}_by_product_{MODEL_TAG}.csv",
        "by_source": OUTPUT_DIR / f"{OUTPUT_PREFIX}_by_source_{MODEL_TAG}.csv",
        "top_deltas": OUTPUT_DIR / f"{OUTPUT_PREFIX}_top_deltas_{MODEL_TAG}.csv",
        "decision": OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json",
        "report": OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md",
    }
    detail.to_csv(paths["detail"], index=False, encoding="utf-8-sig")
    summary.to_csv(paths["summary"], index=False, encoding="utf-8-sig")
    by_year.to_csv(paths["by_year"], index=False, encoding="utf-8-sig")
    by_product.to_csv(paths["by_product"], index=False, encoding="utf-8-sig")
    by_source.to_csv(paths["by_source"], index=False, encoding="utf-8-sig")
    top_deltas.to_csv(paths["top_deltas"], index=False, encoding="utf-8-sig")
    paths["decision"].write_text(json.dumps(decision, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(
        detail=detail,
        summary=summary,
        by_year=by_year,
        by_product=by_product,
        by_source=by_source,
        top_deltas=top_deltas,
        decision=decision,
        paths=paths,
    )
    print(json.dumps({"decision": decision, "report": str(paths["report"])}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
