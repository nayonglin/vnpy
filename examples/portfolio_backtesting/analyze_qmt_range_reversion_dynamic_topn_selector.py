from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from analyze_qmt_range_reversion_full_market_universe_scout import (
    ANALYSIS_END,
    MIN_BARS,
    _add_features,
    _build_product_series,
    _load_mapping,
    _load_products,
    _safe_float,
)
from qmt_universe import VT_SYMBOLS


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

MODEL_TAG: str = "range_reversion_dynamic_topn_selector_v1"
SIGNAL_OUTPUT_PATH: Path = OUTPUT_DIR / f"qmt_range_reversion_dynamic_topn_selector_signals_{MODEL_TAG}.csv"
SUMMARY_OUTPUT_PATH: Path = OUTPUT_DIR / f"qmt_range_reversion_dynamic_topn_selector_summary_{MODEL_TAG}.csv"
YEAR_OUTPUT_PATH: Path = OUTPUT_DIR / f"qmt_range_reversion_dynamic_topn_selector_by_year_{MODEL_TAG}.csv"
PRODUCT_OUTPUT_PATH: Path = OUTPUT_DIR / f"qmt_range_reversion_dynamic_topn_selector_by_product_{MODEL_TAG}.csv"
JSON_OUTPUT_PATH: Path = OUTPUT_DIR / f"qmt_range_reversion_dynamic_topn_selector_summary_{MODEL_TAG}.json"
REPORT_OUTPUT_PATH: Path = OUTPUT_DIR / f"qmt_range_reversion_dynamic_topn_selector_report_{MODEL_TAG}.md"

EXCLUDED_EXCHANGES: set[str] = {"CFFEX"}
MIN_RECENT_BARS: int = 120
TOP_N_VALUES: tuple[int, ...] = (5, 10)
WEEKLY_STATE_SCORE_MIN: float = 0.50


def _clip01(value: object) -> float:
    number = _safe_float(value)
    return max(0.0, min(1.0, number))


def _safe_week(value: pd.Timestamp) -> str:
    return str(pd.Timestamp(value).to_period("W-FRI"))


def _state_score(row: pd.Series, direction: str) -> float:
    adx = _safe_float(row.get("adx"), default=999.0)
    efficiency = _safe_float(row.get("efficiency"), default=999.0)
    range_position = _safe_float(row.get("range_position"), default=0.5)
    rsi = _safe_float(row.get("rsi"), default=50.0)
    close = _safe_float(row.get("close"))
    prev_close = _safe_float(row.get("prev_close"))
    volume = max(_safe_float(row.get("volume")), 0.0)

    trend_score = 0.5 * _clip01((32.0 - adx) / 32.0) + 0.5 * _clip01((0.40 - efficiency) / 0.40)
    liquidity_score = _clip01(np.log1p(volume) / np.log1p(100_000.0))

    if direction == "long":
        edge_score = 0.5 * _clip01((0.35 - range_position) / 0.35) + 0.5 * _clip01((45.0 - rsi) / 20.0)
        reversal_score = 1.0 if close > prev_close > 0 else 0.0
    else:
        edge_score = 0.5 * _clip01((range_position - 0.65) / 0.35) + 0.5 * _clip01((rsi - 55.0) / 20.0)
        reversal_score = 1.0 if 0 < close < prev_close else 0.0

    return _safe_float(0.35 * trend_score + 0.40 * edge_score + 0.15 * reversal_score + 0.10 * liquidity_score)


def _direction_signal_rows(featured: pd.DataFrame, product_vt: str, exchange: str, direction: str) -> pd.DataFrame:
    signal_col = f"{direction}_reversion_signal"
    if signal_col not in featured.columns:
        return pd.DataFrame()
    signal_df = featured[featured[signal_col]].copy()
    if signal_df.empty:
        return signal_df

    sign = 1.0 if direction == "long" else -1.0
    for horizon in (1, 3, 5):
        signal_df[f"direction_fwd_{horizon}d_atr"] = sign * pd.to_numeric(
            signal_df[f"fwd_{horizon}d_atr"], errors="coerce"
        )
    signal_df = signal_df.dropna(subset=["direction_fwd_5d_atr"]).copy()
    if signal_df.empty:
        return signal_df

    signal_df["product_vt"] = product_vt
    signal_df["exchange"] = exchange
    signal_df["direction"] = direction
    signal_df["selector_score"] = signal_df.apply(lambda row: _state_score(row, direction), axis=1)
    signal_df["week"] = signal_df["date"].apply(_safe_week)
    return signal_df[
        [
            "date",
            "week",
            "product_vt",
            "exchange",
            "direction",
            "main_contract_vt",
            "close",
            "volume",
            "range_position",
            "rsi",
            "adx",
            "efficiency",
            "atr_pct",
            "selector_score",
            "direction_fwd_1d_atr",
            "direction_fwd_3d_atr",
            "direction_fwd_5d_atr",
        ]
    ].copy()


def _direction_state_rows(featured: pd.DataFrame, product_vt: str, exchange: str, direction: str) -> pd.DataFrame:
    required = ["date", "close", "prev_close", "volume", "range_position", "rsi", "adx", "efficiency", "atr_pct"]
    if any(column not in featured.columns for column in required):
        return pd.DataFrame()
    state_df = featured.dropna(subset=["range_position", "rsi", "adx", "efficiency", "atr_pct"]).copy()
    if state_df.empty:
        return state_df
    state_df["product_vt"] = product_vt
    state_df["exchange"] = exchange
    state_df["direction"] = direction
    state_df["state_score"] = state_df.apply(lambda row: _state_score(row, direction), axis=1)
    state_df["week"] = state_df["date"].apply(_safe_week)
    return state_df[
        [
            "date",
            "week",
            "product_vt",
            "exchange",
            "direction",
            "state_score",
            "range_position",
            "rsi",
            "adx",
            "efficiency",
            "volume",
        ]
    ].copy()


def _build_signal_and_state_tables() -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    mapping = _load_mapping()
    products = _load_products()
    static18 = set(VT_SYMBOLS)
    contract_cache: dict[str, pd.DataFrame] = {}

    signal_frames: list[pd.DataFrame] = []
    state_frames: list[pd.DataFrame] = []
    total_products = 0
    eligible_products = 0

    for product_row in products.itertuples(index=False):
        product_vt = str(product_row.product_vt)
        exchange = str(product_row.exchange)
        total_products += 1
        if exchange in EXCLUDED_EXCHANGES or product_vt in static18:
            continue

        series = _build_product_series(product_vt, mapping, contract_cache)
        if len(series) < MIN_BARS:
            continue
        recent_bars = int((series["date"] >= ANALYSIS_END - pd.Timedelta(days=365)).sum())
        if recent_bars < MIN_RECENT_BARS:
            continue

        featured = _add_features(series)
        eligible_products += 1
        for direction in ("long", "short"):
            signals = _direction_signal_rows(featured, product_vt, exchange, direction)
            if not signals.empty:
                signal_frames.append(signals)
            states = _direction_state_rows(featured, product_vt, exchange, direction)
            if not states.empty:
                state_frames.append(states)

    if not signal_frames:
        raise RuntimeError("no dynamic selector signal rows")
    signals = pd.concat(signal_frames, ignore_index=True)
    states = pd.concat(state_frames, ignore_index=True) if state_frames else pd.DataFrame()
    signals = signals.sort_values(["date", "selector_score"], ascending=[True, False]).reset_index(drop=True)
    summary = {
        "total_products": total_products,
        "eligible_non_static_commodity_products": eligible_products,
        "signal_rows": int(len(signals)),
    }
    return signals, states, summary


def _assign_daily_topn(signals: pd.DataFrame) -> pd.DataFrame:
    result = signals.copy()
    result["daily_rank"] = result.groupby("date")["selector_score"].rank(method="first", ascending=False)
    for top_n in TOP_N_VALUES:
        result[f"daily_top{top_n}"] = (result["daily_rank"] <= top_n).astype(int)
    return result


def _next_week(week_text: str) -> str:
    period = pd.Period(week_text, freq="W-FRI")
    return str(period + 1)


def _assign_weekly_topn(signals: pd.DataFrame, states: pd.DataFrame) -> pd.DataFrame:
    result = signals.copy()
    if states.empty:
        for top_n in TOP_N_VALUES:
            result[f"weekly_top{top_n}"] = 0
        return result

    # Use the last available state of each product-direction inside the week,
    # then apply that selection only to the next week signal rows.
    last_states = states.sort_values(["week", "product_vt", "direction", "date"]).groupby(
        ["week", "product_vt", "direction"],
        as_index=False,
    ).tail(1)
    last_states = last_states[last_states["state_score"] >= WEEKLY_STATE_SCORE_MIN].copy()
    last_states["rank"] = last_states.groupby("week")["state_score"].rank(method="first", ascending=False)
    last_states["selected_week"] = last_states["week"].map(_next_week)

    for top_n in TOP_N_VALUES:
        selected = last_states[last_states["rank"] <= top_n][["selected_week", "product_vt", "direction"]].copy()
        selected[f"weekly_top{top_n}"] = 1
        result = result.merge(
            selected,
            left_on=["week", "product_vt", "direction"],
            right_on=["selected_week", "product_vt", "direction"],
            how="left",
        )
        result[f"weekly_top{top_n}"] = result[f"weekly_top{top_n}"].fillna(0).astype(int)
        result = result.drop(columns=["selected_week"])
    return result


def _metric_row(frame: pd.DataFrame, label: str) -> dict[str, Any]:
    if frame.empty:
        return {
            "selector": label,
            "signals": 0,
            "days": 0,
            "products": 0,
            "avg_fwd_1d_atr": 0.0,
            "avg_fwd_3d_atr": 0.0,
            "avg_fwd_5d_atr": 0.0,
            "median_fwd_5d_atr": 0.0,
            "positive_5d_rate": 0.0,
            "bad_tail_5d_rate": 0.0,
            "avg_selector_score": 0.0,
        }
    return {
        "selector": label,
        "signals": int(len(frame)),
        "days": int(frame["date"].nunique()),
        "products": int(frame["product_vt"].nunique()),
        "avg_fwd_1d_atr": _safe_float(frame["direction_fwd_1d_atr"].mean()),
        "avg_fwd_3d_atr": _safe_float(frame["direction_fwd_3d_atr"].mean()),
        "avg_fwd_5d_atr": _safe_float(frame["direction_fwd_5d_atr"].mean()),
        "median_fwd_5d_atr": _safe_float(frame["direction_fwd_5d_atr"].median()),
        "positive_5d_rate": _safe_float((frame["direction_fwd_5d_atr"] > 0).mean()),
        "bad_tail_5d_rate": _safe_float((frame["direction_fwd_5d_atr"] <= -1.0).mean()),
        "avg_selector_score": _safe_float(frame["selector_score"].mean()),
    }


def _summaries(signals: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rows = [_metric_row(signals, "all_signals")]
    selector_masks: dict[str, pd.Series] = {}
    for top_n in TOP_N_VALUES:
        selector_masks[f"daily_top{top_n}"] = signals[f"daily_top{top_n}"] == 1
        selector_masks[f"weekly_top{top_n}"] = signals[f"weekly_top{top_n}"] == 1
    for label, mask in selector_masks.items():
        rows.append(_metric_row(signals[mask].copy(), label))
    summary = pd.DataFrame(rows)

    year_rows: list[dict[str, Any]] = []
    product_rows: list[dict[str, Any]] = []
    signals = signals.copy()
    signals["year"] = pd.to_datetime(signals["date"]).dt.year.astype(int)
    for label, mask in {"all_signals": pd.Series(True, index=signals.index), **selector_masks}.items():
        selected = signals[mask].copy()
        if selected.empty:
            continue
        for year, frame in selected.groupby("year"):
            row = _metric_row(frame, label)
            row["year"] = int(year)
            year_rows.append(row)
        for (product_vt, direction), frame in selected.groupby(["product_vt", "direction"]):
            row = _metric_row(frame, label)
            row["product_vt"] = product_vt
            row["direction"] = direction
            product_rows.append(row)

    return summary, pd.DataFrame(year_rows), pd.DataFrame(product_rows)


def _write_report(summary: pd.DataFrame, meta: dict[str, Any]) -> None:
    lines: list[str] = [
        "# QMT Range Reversion Dynamic TopN Selector",
        "",
        "## 结论",
        f"- 总产品数：`{meta['total_products']}`。",
        f"- 可进入动态选择的非18商品产品数：`{meta['eligible_non_static_commodity_products']}`。",
        f"- 候选信号数：`{meta['signal_rows']}`。",
        "- 本阶段不是交易回测，只验证动态TopN选择器是否提高前瞻信号质量。",
        "",
        "## 汇总",
        summary.to_markdown(index=False),
        "",
        "## 方法",
        "- 排除CFFEX金融期货，排除原18趋势品种池。",
        "- 每个产品方向使用固定震荡状态评分：低趋势、低效率、靠近区间边界、温和RSI极值、反转确认、流动性。",
        "- daily TopN：同一交易日的候选信号按当日可见评分排序，取Top5/Top10。",
        "- weekly TopN：用上一周最后可见状态选出下一周候选产品方向，避免周内偷看未来。",
        "- 只统计前瞻ATR收益，不生成订单、不计算资金曲线。",
        "",
        "## 输出文件",
        f"- signals: `{SIGNAL_OUTPUT_PATH}`",
        f"- summary: `{SUMMARY_OUTPUT_PATH}`",
        f"- by_year: `{YEAR_OUTPUT_PATH}`",
        f"- by_product: `{PRODUCT_OUTPUT_PATH}`",
        f"- json: `{JSON_OUTPUT_PATH}`",
    ]
    REPORT_OUTPUT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    signals, states, meta = _build_signal_and_state_tables()
    signals = _assign_daily_topn(signals)
    signals = _assign_weekly_topn(signals, states)
    summary, by_year, by_product = _summaries(signals)

    signals.to_csv(SIGNAL_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    by_year.to_csv(YEAR_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    by_product.to_csv(PRODUCT_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    meta.update(
        {
            "model_tag": MODEL_TAG,
            "top_n_values": list(TOP_N_VALUES),
            "weekly_state_score_min": WEEKLY_STATE_SCORE_MIN,
            "summary": summary.to_dict("records"),
        }
    )
    JSON_OUTPUT_PATH.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(summary, meta)

    print(json.dumps(meta, ensure_ascii=False, indent=2))
    print(f"signals: {SIGNAL_OUTPUT_PATH}")
    print(f"summary: {SUMMARY_OUTPUT_PATH}")
    print(f"by_year: {YEAR_OUTPUT_PATH}")
    print(f"by_product: {PRODUCT_OUTPUT_PATH}")
    print(f"report: {REPORT_OUTPUT_PATH}")


if __name__ == "__main__":
    main()
