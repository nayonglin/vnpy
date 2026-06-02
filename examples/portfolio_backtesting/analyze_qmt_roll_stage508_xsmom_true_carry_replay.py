from __future__ import annotations

from functools import lru_cache
from datetime import datetime
import json
import math
from pathlib import Path
import sys
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
sys.path.insert(0, str(PROJECT_DIR.resolve()))

import analyze_qmt_roll_stage402_stage079_xsmom_volmanaged_true_integer as s402  # noqa: E402
import analyze_qmt_roll_stage403_stage079_xsmom_execution_margin_audit as s403  # noqa: E402
import analyze_qmt_roll_stage451_true_path_1455_vwap_replay as s451  # noqa: E402


MODEL_TAG = "stage508_xsmom_true_carry_replay_v1"
OUTPUT_PREFIX = "qmt_roll_stage508_xsmom_true_carry_replay"
LINE_ID = "futures_trend_drawdown30_preserve_return"

ACCOUNT_CAPITAL = 615_000.0
BASELINE_VARIANT = "stage079"
XSMOM_VARIANT = "xsmom_vt10_q_momq_round_half_true_broker10_guard"
STAGE506_DAILY_PATH = (
    OUTPUT_DIR
    / "qmt_roll_stage506_next_real_forward_risk_signal_frontier_daily_stage506_next_real_forward_risk_signal_frontier_v1.csv"
)
BASE_C3_VARIANTS = (
    "stage079_next_real_risk060_clean",
    "stage079_next_real_risk070_clean",
    "stage079_next_real_r080_vol60_t60_min50_entry",
)

DAILY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_{MODEL_TAG}.csv"
XSMOM_DAILY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_xsmom_daily_{MODEL_TAG}.csv"
TARGET_LEDGER_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_target_ledger_{MODEL_TAG}.csv"
ORDER_LEDGER_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_order_ledger_{MODEL_TAG}.csv"
SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
HORIZON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_horizon_{MODEL_TAG}.csv"
SCORE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_score_{MODEL_TAG}.csv"
COST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cost_stress_{MODEL_TAG}.csv"
GATE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gate_{MODEL_TAG}.csv"
FRONTIER_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_frontier_{MODEL_TAG}.csv"
FILL_SOURCE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_fill_source_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        result = float(value)
        return None if math.isnan(result) or math.isinf(result) else result
    if isinstance(value, (pd.Timestamp, datetime)):
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
    for column in view.columns:
        if pd.api.types.is_float_dtype(view[column]):
            view[column] = view[column].map(lambda value: f"{value:.4f}" if pd.notna(value) else "")
    return view.to_markdown(index=False)


def _to_json(data: dict[str, Any]) -> str:
    return json.dumps(_json_safe(data), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _from_json(value: Any) -> dict[str, Any]:
    if pd.isna(value):
        return {}
    text = str(value).strip()
    if not text:
        return {}
    return json.loads(text)


def _load_stage506_daily() -> pd.DataFrame:
    frame = pd.read_csv(STAGE506_DAILY_PATH, encoding="utf-8-sig")
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    for column in ["account_equity", "slippage", "trade_count", "net_pnl"]:
        frame[column] = pd.to_numeric(frame.get(column, 0.0), errors="coerce").fillna(0.0)
    return frame.dropna(subset=["date"]).sort_values(["variant", "date"]).reset_index(drop=True)


def _contract_product(vt_symbol: str) -> str:
    symbol, exchange = str(vt_symbol).split(".", 1)
    letters = "".join(char for char in symbol if char.isalpha())
    return f"{letters or symbol}.{exchange}"


@lru_cache(maxsize=None)
def _load_minute_bars(vt_symbol: str) -> pd.DataFrame:
    symbol, exchange = str(vt_symbol).split(".", 1)
    parent = PROJECT_DIR / "downloaded_futures"
    paths = []
    for suffix in ("minute_backtest", "completed_minute_backtest"):
        paths.extend(sorted(parent.glob(f"*/{exchange}/{symbol}_{suffix}.csv")))
    frames: list[pd.DataFrame] = []
    for path in paths:
        try:
            frame = pd.read_csv(path, encoding="utf-8-sig")
        except Exception:
            continue
        if frame.empty or "bar_datetime" not in frame.columns:
            continue
        frame["bar_datetime"] = pd.to_datetime(frame["bar_datetime"], errors="coerce").dt.tz_localize(None)
        frame = frame.dropna(subset=["bar_datetime"]).copy()
        for column in ["open", "close", "volume"]:
            frame[column] = pd.to_numeric(frame.get(column, np.nan), errors="coerce")
        frame["source_file"] = str(path)
        frames.append(frame[["bar_datetime", "open", "close", "volume", "source_file"]])
    if not frames:
        return pd.DataFrame(columns=["bar_datetime", "open", "close", "volume", "source_file"])
    bars = pd.concat(frames, ignore_index=True)
    bars = bars.dropna(subset=["open", "close"]).drop_duplicates(["bar_datetime"], keep="last")
    return bars.sort_values("bar_datetime").reset_index(drop=True)


def _first_open_in_window(vt_symbol: str, start: pd.Timestamp, end: pd.Timestamp) -> dict[str, Any] | None:
    bars = _load_minute_bars(vt_symbol)
    if bars.empty:
        return None
    window = bars[(bars["bar_datetime"] >= start) & (bars["bar_datetime"] < end)].copy()
    if window.empty:
        return None
    window = window.sort_values("bar_datetime")
    price = _safe_float(window["open"].iloc[0], np.nan)
    if not np.isfinite(price) or price <= 0.0:
        return None
    return {
        "fill_price": price,
        "bar_count": int(len(window)),
        "first_time": window["bar_datetime"].iloc[0],
        "last_time": window["bar_datetime"].iloc[-1],
        "source_file": str(window["source_file"].iloc[0]),
    }


def _resolve_fill_price(
    vt_symbol: str,
    signal_date: pd.Timestamp | None,
    fill_date: pd.Timestamp,
    fallback_price: float,
) -> dict[str, Any]:
    fill_date = pd.Timestamp(fill_date).normalize()
    if signal_date is not None and pd.notna(signal_date):
        signal_date = pd.Timestamp(signal_date).normalize()
        night = _first_open_in_window(
            vt_symbol,
            signal_date + pd.Timedelta(hours=21),
            signal_date + pd.Timedelta(hours=21, minutes=5),
        )
        if night is not None:
            night["price_source"] = "raw_prev_signal_night_2100_2105_first_open"
            return night
    day = _first_open_in_window(
        vt_symbol,
        fill_date + pd.Timedelta(hours=9),
        fill_date + pd.Timedelta(hours=9, minutes=5),
    )
    if day is not None:
        day["price_source"] = "raw_fill_day_0900_0905_first_open"
        return day
    return {
        "fill_price": float(fallback_price),
        "bar_count": 0,
        "first_time": "",
        "last_time": "",
        "source_file": "",
        "price_source": "fallback_daily_prev_or_last_mark",
    }


def _price_maps(price_frame: pd.DataFrame) -> tuple[dict[tuple[pd.Timestamp, str], Any], dict[tuple[pd.Timestamp, str], Any]]:
    by_product = {
        (pd.Timestamp(row.date).normalize(), str(row.product_vt_symbol)): row
        for row in price_frame.itertuples(index=False)
    }
    by_contract = {
        (pd.Timestamp(row.date).normalize(), str(row.main_contract_vt)): row
        for row in price_frame.dropna(subset=["main_contract_vt"]).itertuples(index=False)
    }
    return by_product, by_contract


def _build_target_ledger(
    window_frame: pd.DataFrame,
    margin_frame: pd.DataFrame,
    price_frame: pd.DataFrame,
    signals: pd.DataFrame,
    scale_by_date: pd.Series,
) -> pd.DataFrame:
    start = window_frame["date"].min()
    end = window_frame["date"].max()
    signal_by_date = {
        pd.Timestamp(row.date).normalize(): row
        for row in signals[signals["date"].between(start, end)].itertuples(index=False)
    }
    price_by_product, price_by_contract = _price_maps(price_frame[price_frame["date"].between(start, end)])
    c3_pnl_by_date = window_frame.set_index("date")["c3_net_pnl"].astype(float).to_dict()
    c3_margin_by_date = margin_frame.set_index("date")["c3_margin"].astype(float).to_dict()

    prev_positions: dict[str, int] = {}
    prev_equity = s402.ACCOUNT_CAPITAL
    rows: list[dict[str, Any]] = []
    dates = sorted(window_frame["date"].dropna().drop_duplicates().tolist())

    for idx, raw_date in enumerate(dates):
        date = pd.Timestamp(raw_date).normalize()
        signal_date = pd.Timestamp(dates[idx - 1]).normalize() if idx > 0 else pd.NaT
        signal_row = signal_by_date.get(date)
        day_prices = price_frame[price_frame["date"].eq(date)]
        price_by_product_today = {str(row.product_vt_symbol): row for row in day_prices.itertuples(index=False)}
        desired = s402._desired_contracts(signal_row, price_by_product_today) if signal_row is not None else []
        scale = float(scale_by_date.get(date, 0.0))
        targets, required_min1_margin = s402._target_lots("round_half", scale, desired)

        target_meta: dict[str, dict[str, Any]] = {}
        proposed_margin = 0.0
        for contract, lots in targets.items():
            price_row = price_by_contract.get((date, contract))
            if price_row is None:
                continue
            proposed_margin += abs(lots) * s402._safe_float(getattr(price_row, "margin_per_contract", 0.0))
            target_meta[contract] = {
                "product": str(getattr(price_row, "product_vt_symbol", _contract_product(contract))),
                "size": s402._safe_float(getattr(price_row, "size", 1.0), 1.0),
                "slippage": s402._safe_float(getattr(price_row, "slippage", 0.0), 0.0),
                "main_close": s402._safe_float(getattr(price_row, "main_close", 0.0), 0.0),
                "prev_main_close": s402._safe_float(getattr(price_row, "prev_main_close", 0.0), 0.0),
                "margin_per_contract": s402._safe_float(getattr(price_row, "margin_per_contract", 0.0), 0.0),
            }

        c3_margin = float(c3_margin_by_date.get(date, 0.0))
        margin_gate_skipped = int(bool(targets) and (c3_margin + proposed_margin) * s403.BROKER10_MULTIPLIER > prev_equity)
        if margin_gate_skipped:
            targets = {}
            target_meta = {}
            proposed_margin = 0.0

        frozen_gross_pnl = 0.0
        satellite_margin = 0.0
        for contract, lots in targets.items():
            price_row = price_by_contract.get((date, contract))
            if price_row is None:
                continue
            frozen_gross_pnl += lots * s402._safe_float(getattr(price_row, "prev_main_close", 0.0)) * s402._safe_float(
                getattr(price_row, "size", 1.0)
            ) * s402._safe_float(getattr(price_row, "product_return", 0.0))
            satellite_margin += abs(lots) * s402._safe_float(getattr(price_row, "margin_per_contract", 0.0))

        frozen_turnover = 0
        frozen_slippage = 0.0
        for contract in set(prev_positions) | set(targets):
            delta = abs(targets.get(contract, 0) - prev_positions.get(contract, 0))
            if delta <= 0:
                continue
            frozen_turnover += delta
            price_row = price_by_contract.get((date, contract))
            if price_row is not None:
                frozen_slippage += delta * s402._safe_float(getattr(price_row, "slippage", 0.0)) * s402._safe_float(
                    getattr(price_row, "size", 1.0)
                )

        frozen_daily_pnl = frozen_gross_pnl - frozen_slippage
        rows.append(
            {
                "date": date,
                "signal_date": signal_date,
                "stage101_scale": scale,
                "desired_signal_count": len(desired),
                "held_contract_count": len(targets),
                "required_min1_margin": required_min1_margin,
                "satellite_margin": satellite_margin,
                "margin_gate_skipped": margin_gate_skipped,
                "frozen_daily_pnl": frozen_daily_pnl,
                "frozen_slippage_cost": frozen_slippage,
                "frozen_turnover_contracts": frozen_turnover,
                "targets_json": _to_json({contract: int(lots) for contract, lots in targets.items()}),
                "target_meta_json": _to_json(target_meta),
            }
        )
        prev_positions = {contract: int(lots) for contract, lots in targets.items()}
        prev_equity += float(c3_pnl_by_date.get(date, 0.0)) + frozen_daily_pnl

    return pd.DataFrame(rows)


def _sign(value: int) -> int:
    if value > 0:
        return 1
    if value < 0:
        return -1
    return 0


def _delta_pnl(lots: int, start_price: float, end_price: float, size: float) -> float:
    return float(lots) * (float(end_price) - float(start_price)) * float(size)


def _replay_true_xsmom(target_ledger: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    positions: dict[str, dict[str, Any]] = {}
    daily_rows: list[dict[str, Any]] = []
    order_rows: list[dict[str, Any]] = []

    for row in target_ledger.sort_values("date").itertuples(index=False):
        date = pd.Timestamp(row.date).normalize()
        signal_date = pd.Timestamp(row.signal_date).normalize() if pd.notna(row.signal_date) else None
        targets = {str(contract): int(lots) for contract, lots in _from_json(row.targets_json).items()}
        target_meta = {str(contract): dict(meta) for contract, meta in _from_json(row.target_meta_json).items()}
        gross_pnl = 0.0
        slippage_cost = 0.0
        turnover = 0
        fallback_count = 0
        raw_count = 0
        new_positions: dict[str, dict[str, Any]] = {}

        for contract in sorted(set(positions) | set(targets)):
            old = positions.get(contract)
            old_lots = int(old["lots"]) if old is not None else 0
            new_lots = int(targets.get(contract, 0))
            if old_lots == 0 and new_lots == 0:
                continue

            meta = target_meta.get(contract, {})
            product = str(meta.get("product") or (old or {}).get("product") or _contract_product(contract))
            size = _safe_float(meta.get("size", (old or {}).get("size", 1.0)), 1.0)
            slippage = _safe_float(meta.get("slippage", (old or {}).get("slippage", 0.0)), 0.0)
            close_price = _safe_float(meta.get("main_close", (old or {}).get("last_mark", 0.0)), 0.0)
            prev_close = _safe_float(meta.get("prev_main_close", (old or {}).get("last_mark", close_price)), close_price)
            last_mark = _safe_float((old or {}).get("last_mark", prev_close), prev_close)
            fallback_anchor = prev_close if prev_close > 0.0 else last_mark
            fill = _resolve_fill_price(contract, signal_date, date, fallback_anchor)
            fill_price = _safe_float(fill.get("fill_price"), fallback_anchor)

            delta_abs = abs(new_lots - old_lots)
            if delta_abs > 0:
                turnover += delta_abs
                slippage_cost += delta_abs * slippage * size
                if str(fill.get("price_source", "")).startswith("fallback"):
                    fallback_count += 1
                else:
                    raw_count += 1
                order_rows.append(
                    {
                        "date": date,
                        "signal_date": signal_date,
                        "fill_date": date,
                        "contract": contract,
                        "product": product,
                        "old_lots": old_lots,
                        "target_lots": new_lots,
                        "delta_lots": new_lots - old_lots,
                        "fill_price": fill_price,
                        "fallback_anchor": fallback_anchor,
                        "close_price": close_price,
                        "size": size,
                        "slippage": slippage,
                        "slippage_cost": delta_abs * slippage * size,
                        "price_source": fill.get("price_source", ""),
                        "bar_count": fill.get("bar_count", 0),
                        "first_time": fill.get("first_time", ""),
                        "last_time": fill.get("last_time", ""),
                        "source_file": fill.get("source_file", ""),
                    }
                )

            if close_price <= 0.0:
                close_price = fill_price if fill_price > 0.0 else last_mark

            old_sign = _sign(old_lots)
            new_sign = _sign(new_lots)
            if old_lots == new_lots:
                gross_pnl += _delta_pnl(old_lots, last_mark, close_price, size)
            elif old_sign != 0 and new_sign == old_sign:
                carry_abs = min(abs(old_lots), abs(new_lots))
                carry_lots = old_sign * carry_abs
                gross_pnl += _delta_pnl(carry_lots, last_mark, close_price, size)
                if abs(old_lots) > abs(new_lots):
                    closed_lots = old_sign * (abs(old_lots) - abs(new_lots))
                    gross_pnl += _delta_pnl(closed_lots, last_mark, fill_price, size)
                else:
                    added_lots = old_sign * (abs(new_lots) - abs(old_lots))
                    gross_pnl += _delta_pnl(added_lots, fill_price, close_price, size)
            else:
                if old_lots != 0:
                    gross_pnl += _delta_pnl(old_lots, last_mark, fill_price, size)
                if new_lots != 0:
                    gross_pnl += _delta_pnl(new_lots, fill_price, close_price, size)

            if new_lots != 0:
                new_positions[contract] = {
                    "lots": new_lots,
                    "product": product,
                    "size": size,
                    "slippage": slippage,
                    "last_mark": close_price,
                }

        net_pnl = gross_pnl - slippage_cost
        daily_rows.append(
            {
                "date": date,
                "xsmom_true_gross_pnl": gross_pnl,
                "xsmom_true_slippage_cost": slippage_cost,
                "xsmom_true_daily_pnl": net_pnl,
                "xsmom_true_turnover_contracts": turnover,
                "xsmom_true_raw_order_count": raw_count,
                "xsmom_true_fallback_order_count": fallback_count,
                "xsmom_true_held_contract_count": int(sum(1 for item in new_positions.values() if int(item["lots"]) != 0)),
                "xsmom_true_margin": _safe_float(row.satellite_margin),
                "xsmom_frozen_daily_pnl": _safe_float(row.frozen_daily_pnl),
                "xsmom_frozen_slippage_cost": _safe_float(row.frozen_slippage_cost),
                "xsmom_frozen_turnover_contracts": _safe_float(row.frozen_turnover_contracts),
                "stage101_scale": _safe_float(row.stage101_scale),
                "margin_gate_skipped": int(row.margin_gate_skipped),
            }
        )
        positions = new_positions

    return pd.DataFrame(daily_rows), pd.DataFrame(order_rows)


def _combine_daily(stage506: pd.DataFrame, xsmom_true: pd.DataFrame) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []

    baseline = stage506[stage506["variant"].eq(BASELINE_VARIANT)].copy()
    baseline["label"] = "Stage079 same-day baseline"
    rows.append(baseline[["date", "variant", "label", "account_equity", "slippage", "trade_count", "net_pnl"]].copy())

    for variant in BASE_C3_VARIANTS:
        base = stage506[stage506["variant"].eq(variant)].copy()
        if base.empty:
            continue
        base["label"] = f"{variant} clean no xsmom"
        rows.append(base[["date", "variant", "label", "account_equity", "slippage", "trade_count", "net_pnl"]].copy())

        combo = base[["date", "net_pnl", "slippage", "trade_count"]].merge(xsmom_true, on="date", how="left")
        for column in [
            "xsmom_true_daily_pnl",
            "xsmom_true_slippage_cost",
            "xsmom_true_turnover_contracts",
            "xsmom_true_fallback_order_count",
            "xsmom_true_margin",
        ]:
            combo[column] = pd.to_numeric(combo.get(column, 0.0), errors="coerce").fillna(0.0)
        combo["net_pnl"] = combo["net_pnl"].astype(float) + combo["xsmom_true_daily_pnl"].astype(float)
        combo["account_equity"] = ACCOUNT_CAPITAL + combo["net_pnl"].cumsum()
        combo["slippage"] = combo["slippage"].astype(float) + combo["xsmom_true_slippage_cost"].astype(float)
        combo["trade_count"] = combo["trade_count"].astype(float) + combo["xsmom_true_turnover_contracts"].astype(float)
        combo["variant"] = f"{variant}_plus_stage103_xsmom_true"
        combo["label"] = f"{variant} + true-carried Stage103 xsmom"
        rows.append(combo[["date", "variant", "label", "account_equity", "slippage", "trade_count", "net_pnl"]].copy())

    return pd.concat(rows, ignore_index=True).sort_values(["variant", "date"]).reset_index(drop=True)


def _frontier(summary: pd.DataFrame, order_ledger: pd.DataFrame) -> pd.DataFrame:
    baseline_return = _safe_float(summary[summary["variant"].eq(BASELINE_VARIANT)]["total_return_pct"].iloc[0])
    fallback_orders = 0
    if not order_ledger.empty:
        fallback_orders = int(order_ledger["price_source"].astype(str).str.startswith("fallback").sum())
    frame = summary.copy()
    frame["return_retention_vs_stage079_pct"] = frame["total_return_pct"].astype(float) / baseline_return * 100.0
    frame["dd40_pass"] = frame["max_dd_pct"].astype(float).ge(-40.0).astype(int)
    frame["return65_pass"] = frame["return_retention_vs_stage079_pct"].ge(65.0).astype(int)
    frame["is_true_xsmom_combo"] = frame["variant"].astype(str).str.contains("_plus_stage103_xsmom_true").astype(int)
    frame["xsmom_fallback_order_count"] = np.where(frame["is_true_xsmom_combo"].eq(1), fallback_orders, 0).astype(int)
    frame["candidate_gate_pass"] = (
        frame["is_true_xsmom_combo"].eq(1)
        & frame["dd40_pass"].eq(1)
        & frame["return65_pass"].eq(1)
        & frame["xsmom_fallback_order_count"].eq(0)
    ).astype(int)
    return frame[
        [
            "variant",
            "end_equity",
            "total_return_pct",
            "return_retention_vs_stage079_pct",
            "max_dd_pct",
            "sharpe",
            "ulcer_pct",
            "rolling252_dd30_breach_rate",
            "rolling504_dd30_breach_rate",
            "dd40_pass",
            "return65_pass",
            "xsmom_fallback_order_count",
            "candidate_gate_pass",
            "is_true_xsmom_combo",
        ]
    ].sort_values(["candidate_gate_pass", "dd40_pass", "return65_pass", "total_return_pct"], ascending=[False, False, False, False])


def _fill_source(order_ledger: pd.DataFrame) -> pd.DataFrame:
    if order_ledger.empty:
        return pd.DataFrame(columns=["price_source", "order_count", "contract_count", "delta_abs_sum"])
    frame = order_ledger.copy()
    frame["delta_abs"] = frame["delta_lots"].abs()
    return (
        frame.groupby("price_source", as_index=False)
        .agg(
            order_count=("contract", "size"),
            contract_count=("contract", "nunique"),
            delta_abs_sum=("delta_abs", "sum"),
        )
        .sort_values(["order_count"], ascending=False)
    )


def _plot(long_daily: pd.DataFrame, xsmom_true: pd.DataFrame) -> None:
    keep = [
        BASELINE_VARIANT,
        "stage079_next_real_risk060_clean",
        "stage079_next_real_risk060_clean_plus_stage103_xsmom_true",
        "stage079_next_real_risk070_clean_plus_stage103_xsmom_true",
        "stage079_next_real_r080_vol60_t60_min50_entry_plus_stage103_xsmom_true",
    ]
    fig, axes = plt.subplots(3, 1, figsize=(13, 10), sharex=True)
    for variant, frame in long_daily[long_daily["variant"].isin(keep)].groupby("variant", sort=False):
        x = pd.to_datetime(frame["date"])
        nav = frame["account_equity"].astype(float) / ACCOUNT_CAPITAL
        axes[0].plot(x, nav, label=str(frame["label"].iloc[0]), linewidth=1.05)
        axes[1].plot(x, (nav / nav.cummax() - 1.0) * 100.0, label=str(frame["label"].iloc[0]), linewidth=0.95)
    x = pd.to_datetime(xsmom_true["date"])
    axes[2].plot(x, xsmom_true["xsmom_true_daily_pnl"].astype(float).cumsum(), label="true xsmom cumulative PnL", linewidth=1.0)
    axes[2].plot(x, xsmom_true["xsmom_frozen_daily_pnl"].astype(float).cumsum(), label="frozen daily reference", linewidth=0.9, alpha=0.75)
    axes[0].set_title("Stage208 next-real C3 + true-carried Stage103 xsmom")
    axes[0].set_ylabel("NAV")
    axes[0].legend(fontsize=8)
    axes[1].set_title("Underwater drawdown")
    axes[1].set_ylabel("Drawdown %")
    axes[1].axhline(-40.0, color="#222222", linestyle="--", linewidth=1.0)
    axes[1].grid(True, alpha=0.25)
    axes[2].set_title("xsmom leg: true carried replay vs frozen daily reference")
    axes[2].set_ylabel("Cumulative PnL")
    axes[2].legend(fontsize=8)
    axes[2].grid(True, alpha=0.25)
    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=160)
    plt.close(fig)


def _write_report(
    summary: pd.DataFrame,
    horizon: pd.DataFrame,
    cost: pd.DataFrame,
    frontier: pd.DataFrame,
    xsmom_true: pd.DataFrame,
    fill_source: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    summary_cols = [
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
    horizon_cols = [
        "variant",
        "horizon_days",
        "return_p05_pct",
        "return_median_pct",
        "positive_return_rate",
        "max_dd_worst_pct",
        "dd30_breach_rate",
        "ulcer_p95_pct",
    ]
    xsmom_stats = pd.DataFrame(
        [
            {
                "true_total_pnl": float(xsmom_true["xsmom_true_daily_pnl"].sum()),
                "frozen_total_pnl": float(xsmom_true["xsmom_frozen_daily_pnl"].sum()),
                "true_minus_frozen_pnl": float(
                    xsmom_true["xsmom_true_daily_pnl"].sum() - xsmom_true["xsmom_frozen_daily_pnl"].sum()
                ),
                "true_slippage": float(xsmom_true["xsmom_true_slippage_cost"].sum()),
                "true_turnover": float(xsmom_true["xsmom_true_turnover_contracts"].sum()),
                "fallback_orders": int(xsmom_true["xsmom_true_fallback_order_count"].sum()),
                "margin_gate_skipped_days": int(xsmom_true["margin_gate_skipped"].sum()),
            }
        ]
    )
    report = [
        "# Stage208 xsmom真实承载回放",
        "",
        f"- 生成时间：{decision['generated_at']}",
        "- 阶段性质：结构可执行性审计；不调 xsmom 参数、权重、C3 风险倍率或品种池。",
        "- 核心问题：Stage207 的独立 xsmom 边际收益，在真实分钟窗口承载后是否仍足以让 next-real C3 进入 DD40 且收益保留大于 65%。",
        "",
        "## 外部调研判断",
        "",
        "- 期货趋势/动量文献通常把稳健性来源放在跨市场分散、波动约束和交易成本后仍成立，而不是单一权益曲线的小阈值修饰。",
        "- GitHub/PyPI 上公开实现多以 Backtrader/pandas 做月度或日度再平衡；本仓库已有更细的 vn.py/分钟代理数据，因此本阶段优先把可执行账本补齐，而不是复制外部简化回测。",
        "",
        "## 决策",
        "",
        f"- 决策标签：`{decision['decision']}`。",
        f"- 最佳真实承载版本：`{decision['best_variant']}`。",
        f"- 最佳收益保留：`{decision['best_return_retention_vs_stage079_pct']:.4f}%`。",
        f"- 最佳最大回撤：`{decision['best_max_dd_pct']:.4f}%`。",
        f"- xsmom fallback订单数：`{decision['xsmom_fallback_order_count']}`。",
        f"- 是否候选晋级：`{decision['candidate_promotion']}`。",
        "",
        "## 前沿汇总",
        "",
        _md_table(frontier),
        "",
        "## xsmom腿自身差异",
        "",
        _md_table(xsmom_stats),
        "",
        "## 全周期指标",
        "",
        _md_table(summary[summary_cols]),
        "",
        "## 3个月/6个月体验",
        "",
        _md_table(horizon[horizon_cols].sort_values(["variant", "horizon_days"])),
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
                    "not_worse_than_stage079_stress",
                ]
            ],
            max_rows=80,
        ),
        "",
        "## xsmom成交来源",
        "",
        _md_table(fill_source),
        "",
        "## 图表视觉复盘",
        "",
        "- 需要直接看 true-carried xsmom 是否仍抬升 2021-2022 和 2025 水下，而不是只靠末端收益拉高指标。",
        "- 需要看真实 xsmom 累计PnL是否长期贴近 frozen 参考；若二者在关键趋势段大幅背离，说明 Stage207 的边际收益不可直接承诺。",
        "- 若组合曲线仍贴着 `-40%` 线运行，则即便指标通过，也只能算工程候选，不能视为安全候选。",
        "",
        "## 过拟合与继续价值反思",
        "",
        "- 运行前过拟合反思：否。本阶段只把 Stage103 冻结规则改造成真实承载账本，没有调窗口、权重、阈值或品种。",
        "- 运行后过拟合反思：以决策标签为准；若不通过，不能回头扫 xsmom 小参数救线。",
        "- 运行前继续价值反思：是。Stage206 已反证继续修 C3 本体风险不划算，独立低相关收益源是更有第一性原理的方向。",
        "- 运行后继续价值反思：以决策标签为准；若 fallback 不为零，下一步先补成交数据；若真实承载边际不足，则停止 Stage103 接入。",
    ]
    REPORT_PATH.write_text("\n".join(report) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    combo = s402._load_combo_daily()
    margin = s402._load_margin()
    full = combo[combo["window_name"].eq("start_2020")].sort_values("date").drop_duplicates("date", keep="last")
    margin_full = margin[margin["window_name"].eq("start_2020")].sort_values("date").drop_duplicates("date", keep="last")
    scale_by_date = s402._build_stage101_scale(full)
    price_frame = s402._build_price_frame()
    price_frame["date"] = pd.to_datetime(price_frame["date"], errors="coerce").dt.normalize()
    signals = s402._load_signal_daily()
    signals["date"] = pd.to_datetime(signals["date"], errors="coerce").dt.normalize()

    target_ledger = _build_target_ledger(full, margin_full, price_frame, signals, scale_by_date)
    xsmom_true, order_ledger = _replay_true_xsmom(target_ledger)
    stage506 = _load_stage506_daily()
    long_daily = _combine_daily(stage506, xsmom_true)
    summary, horizon, score, cost, gate = s451._evaluate(long_daily)
    frontier = _frontier(summary, order_ledger)
    fill_source = _fill_source(order_ledger)
    _plot(long_daily, xsmom_true)

    candidates = frontier[frontier["is_true_xsmom_combo"].eq(1)].copy()
    pass_rows = candidates[candidates["candidate_gate_pass"].eq(1)].copy()
    if not pass_rows.empty:
        best = pass_rows.sort_values("total_return_pct", ascending=False).iloc[0]
        decision_label = "true_xsmom_carrier_clean_dd40_return65_candidate"
        promotion = "是"
    else:
        dd40_return65 = candidates[candidates["dd40_pass"].eq(1) & candidates["return65_pass"].eq(1)].copy()
        if not dd40_return65.empty:
            best = dd40_return65.sort_values("total_return_pct", ascending=False).iloc[0]
            decision_label = "true_xsmom_carrier_metrics_pass_but_fallback_blocked"
            promotion = "否，成交fallback未清零"
        elif not candidates[candidates["dd40_pass"].eq(1)].empty:
            best = candidates[candidates["dd40_pass"].eq(1)].sort_values("total_return_pct", ascending=False).iloc[0]
            decision_label = "true_xsmom_carrier_dd40_but_return_retention_short"
            promotion = "否，收益保留不足"
        else:
            best = candidates.sort_values("total_return_pct", ascending=False).iloc[0]
            decision_label = "true_xsmom_carrier_no_dd40_candidate"
            promotion = "否，回撤未达标"

    fallback_order_count = int(order_ledger["price_source"].astype(str).str.startswith("fallback").sum()) if not order_ledger.empty else 0
    decision = {
        "stage": "Stage208",
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "decision": decision_label,
        "best_variant": str(best["variant"]),
        "best_end_equity": _safe_float(best["end_equity"]),
        "best_total_return_pct": _safe_float(best["total_return_pct"]),
        "best_return_retention_vs_stage079_pct": _safe_float(best["return_retention_vs_stage079_pct"]),
        "best_max_dd_pct": _safe_float(best["max_dd_pct"]),
        "best_sharpe": _safe_float(best["sharpe"]),
        "best_ulcer_pct": _safe_float(best["ulcer_pct"]),
        "xsmom_fallback_order_count": fallback_order_count,
        "candidate_promotion": promotion,
        "outputs": {
            "daily": str(DAILY_PATH.resolve()),
            "xsmom_daily": str(XSMOM_DAILY_PATH.resolve()),
            "target_ledger": str(TARGET_LEDGER_PATH.resolve()),
            "order_ledger": str(ORDER_LEDGER_PATH.resolve()),
            "summary": str(SUMMARY_PATH.resolve()),
            "horizon": str(HORIZON_PATH.resolve()),
            "score": str(SCORE_PATH.resolve()),
            "cost": str(COST_PATH.resolve()),
            "gate": str(GATE_PATH.resolve()),
            "frontier": str(FRONTIER_PATH.resolve()),
            "fill_source": str(FILL_SOURCE_PATH.resolve()),
            "chart": str(CHART_PATH.resolve()),
            "report": str(REPORT_PATH.resolve()),
        },
        "next_step": "若fallback为0且指标通过，做多窗口/保证金压力复核；若fallback不为0，先补xsmom成交窗口；若收益保留不足，停止Stage103真实接入。",
    }

    long_daily.to_csv(DAILY_PATH, index=False, encoding="utf-8-sig")
    xsmom_true.to_csv(XSMOM_DAILY_PATH, index=False, encoding="utf-8-sig")
    target_ledger.to_csv(TARGET_LEDGER_PATH, index=False, encoding="utf-8-sig")
    order_ledger.to_csv(ORDER_LEDGER_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    horizon.to_csv(HORIZON_PATH, index=False, encoding="utf-8-sig")
    score.to_csv(SCORE_PATH, index=False, encoding="utf-8-sig")
    cost.to_csv(COST_PATH, index=False, encoding="utf-8-sig")
    gate.to_csv(GATE_PATH, index=False, encoding="utf-8-sig")
    frontier.to_csv(FRONTIER_PATH, index=False, encoding="utf-8-sig")
    fill_source.to_csv(FILL_SOURCE_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(summary, horizon, cost, frontier, xsmom_true, fill_source, decision)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print(f"wrote: {REPORT_PATH}")


if __name__ == "__main__":
    main()
