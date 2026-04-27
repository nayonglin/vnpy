from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

from analyze_qmt_range_reversion_core4_v7_weak_window_trade_replay import (
    _load_bar_history,
    _safe_float,
    _to_local_date,
)


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"
SOURCE_PREFIX: str = "qmt_range_reversion_core4_directed_product_signal_back_adjusted_v8_two_stage_stop"
MODEL_TAG: str = "range_reversion_core4_v8_signal_attribution_v1"

HORIZONS: tuple[int, ...] = (3, 5, 10, 20)
CHANNEL_WINDOW: int = 20
RANGE_ZSCORE_WINDOW: int = 120
HARD_STOP_R_MULTIPLE: float = 2.0

CANDIDATES_PATH: Path = OUTPUT_DIR / f"{SOURCE_PREFIX}_entry_candidate_snapshots_2020_2026_04.csv"
DETAIL_PATH: Path = OUTPUT_DIR / f"qmt_range_reversion_core4_v8_signal_attribution_detail_{MODEL_TAG}.csv"
PRODUCT_DIRECTION_SUMMARY_PATH: Path = (
    OUTPUT_DIR / f"qmt_range_reversion_core4_v8_signal_attribution_product_direction_{MODEL_TAG}.csv"
)
YEAR_DIRECTION_SUMMARY_PATH: Path = (
    OUTPUT_DIR / f"qmt_range_reversion_core4_v8_signal_attribution_year_direction_{MODEL_TAG}.csv"
)
STATUS_SUMMARY_PATH: Path = OUTPUT_DIR / f"qmt_range_reversion_core4_v8_signal_attribution_status_{MODEL_TAG}.csv"
LABEL_SUMMARY_PATH: Path = OUTPUT_DIR / f"qmt_range_reversion_core4_v8_signal_attribution_label_{MODEL_TAG}.csv"
SUMMARY_JSON_PATH: Path = OUTPUT_DIR / f"qmt_range_reversion_core4_v8_signal_attribution_summary_{MODEL_TAG}.json"
REPORT_PATH: Path = OUTPUT_DIR / f"qmt_range_reversion_core4_v8_signal_attribution_report_{MODEL_TAG}.md"


def _configure_paths(source_prefix: str | None = None, model_tag: str | None = None) -> None:
    global SOURCE_PREFIX
    global MODEL_TAG
    global CANDIDATES_PATH
    global DETAIL_PATH
    global PRODUCT_DIRECTION_SUMMARY_PATH
    global YEAR_DIRECTION_SUMMARY_PATH
    global STATUS_SUMMARY_PATH
    global LABEL_SUMMARY_PATH
    global SUMMARY_JSON_PATH
    global REPORT_PATH

    if source_prefix:
        SOURCE_PREFIX = source_prefix
    if model_tag:
        MODEL_TAG = model_tag

    report_prefix = "qmt_range_reversion_core4"
    if "_v8_" in SOURCE_PREFIX:
        report_prefix = "qmt_range_reversion_core4_v8"
    elif "_v9_" in SOURCE_PREFIX:
        report_prefix = "qmt_range_reversion_core4_v9"

    CANDIDATES_PATH = OUTPUT_DIR / f"{SOURCE_PREFIX}_entry_candidate_snapshots_2020_2026_04.csv"
    DETAIL_PATH = OUTPUT_DIR / f"{report_prefix}_signal_attribution_detail_{MODEL_TAG}.csv"
    PRODUCT_DIRECTION_SUMMARY_PATH = (
        OUTPUT_DIR / f"{report_prefix}_signal_attribution_product_direction_{MODEL_TAG}.csv"
    )
    YEAR_DIRECTION_SUMMARY_PATH = OUTPUT_DIR / f"{report_prefix}_signal_attribution_year_direction_{MODEL_TAG}.csv"
    STATUS_SUMMARY_PATH = OUTPUT_DIR / f"{report_prefix}_signal_attribution_status_{MODEL_TAG}.csv"
    LABEL_SUMMARY_PATH = OUTPUT_DIR / f"{report_prefix}_signal_attribution_label_{MODEL_TAG}.csv"
    SUMMARY_JSON_PATH = OUTPUT_DIR / f"{report_prefix}_signal_attribution_summary_{MODEL_TAG}.json"
    REPORT_PATH = OUTPUT_DIR / f"{report_prefix}_signal_attribution_report_{MODEL_TAG}.md"


def _load_candidates() -> pd.DataFrame:
    if not CANDIDATES_PATH.exists():
        raise FileNotFoundError(CANDIDATES_PATH)

    candidates = pd.read_csv(CANDIDATES_PATH, encoding="utf-8-sig")
    if candidates.empty:
        return candidates

    candidates["signal_date"] = candidates["datetime"].map(_to_local_date)
    candidates["signal_year"] = candidates["signal_date"].dt.year
    if "passed_initial_filter" in candidates.columns:
        candidates = candidates[candidates["passed_initial_filter"].fillna(0).astype(int).eq(1)].copy()
    candidates = candidates.sort_values(["signal_date", "candidate_index"]).reset_index(drop=True)
    return candidates


def _prepare_bars(contracts: set[str]) -> dict[str, pd.DataFrame]:
    bars = _load_bar_history(contracts)
    if bars.empty:
        return {}

    pieces: list[pd.DataFrame] = []
    for _, group in bars.groupby("vt_symbol", sort=False):
        group = group.sort_values("date").copy()
        group["ret_5d"] = group["close"].pct_change(5)
        group["ret_20d"] = group["close"].pct_change(20)

        channel_high = group["high"].rolling(CHANNEL_WINDOW).max()
        channel_low = group["low"].rolling(CHANNEL_WINDOW).min()
        channel_width = (channel_high - channel_low).mask((channel_high - channel_low) == 0)
        close_nonzero = group["close"].mask(group["close"] == 0)
        group["channel_high_20"] = channel_high
        group["channel_low_20"] = channel_low
        group["channel_middle_20"] = (channel_high + channel_low) / 2.0
        group["channel_position_20"] = (group["close"] - channel_low) / channel_width
        group["range_pct_20"] = channel_width / close_nonzero

        range_mean = group["range_pct_20"].rolling(RANGE_ZSCORE_WINDOW, min_periods=20).mean()
        range_std = group["range_pct_20"].rolling(RANGE_ZSCORE_WINDOW, min_periods=20).std()
        range_std = range_std.mask(range_std == 0)
        group["range_pct_zscore_120"] = (group["range_pct_20"] - range_mean) / range_std
        pieces.append(group)

    bars = pd.concat(pieces, ignore_index=True)
    return {contract: group.reset_index(drop=True) for contract, group in bars.groupby("vt_symbol", sort=False)}


def _event_flags(
    direction: str,
    future: pd.DataFrame,
    entry_price: float,
    stop_price: float,
    hard_stop_price: float,
) -> dict[str, Any]:
    first_middle_bar: int | None = None
    first_initial_stop_bar: int | None = None
    first_hard_stop_bar: int | None = None

    for index, row in enumerate(future.head(max(HORIZONS)).itertuples(index=False), start=1):
        high_price = _safe_float(getattr(row, "high", float("nan")))
        low_price = _safe_float(getattr(row, "low", float("nan")))
        middle_price = _safe_float(getattr(row, "channel_middle_20", float("nan")))

        if direction == "long":
            if first_middle_bar is None and not pd.isna(middle_price) and high_price >= middle_price:
                first_middle_bar = index
            if first_initial_stop_bar is None and not pd.isna(stop_price) and low_price <= stop_price:
                first_initial_stop_bar = index
            if first_hard_stop_bar is None and low_price <= hard_stop_price:
                first_hard_stop_bar = index
        else:
            if first_middle_bar is None and not pd.isna(middle_price) and low_price <= middle_price:
                first_middle_bar = index
            if first_initial_stop_bar is None and not pd.isna(stop_price) and high_price >= stop_price:
                first_initial_stop_bar = index
            if first_hard_stop_bar is None and high_price >= hard_stop_price:
                first_hard_stop_bar = index

    return {
        "first_middle_bar": first_middle_bar,
        "first_initial_stop_bar": first_initial_stop_bar,
        "first_hard_stop_bar": first_hard_stop_bar,
    }


def _horizon_metrics(
    direction: str,
    future: pd.DataFrame,
    horizon: int,
    entry_price: float,
    risk_distance: float,
    events: dict[str, Any],
) -> dict[str, Any]:
    window = future.head(horizon)
    prefix = f"{horizon}d"
    if window.empty or risk_distance <= 0:
        return {
            f"forward_close_{prefix}_pct": float("nan"),
            f"forward_close_{prefix}_r": float("nan"),
            f"mfe_{prefix}_r": float("nan"),
            f"mae_{prefix}_r": float("nan"),
            f"hit_middle_{prefix}": 0,
            f"hit_initial_stop_{prefix}": 0,
            f"hit_hard_stop_{prefix}": 0,
        }

    last_close = _safe_float(window["close"].iloc[-1])
    if direction == "long":
        forward_close = last_close - entry_price
        mfe = _safe_float(window["high"].max()) - entry_price
        mae = entry_price - _safe_float(window["low"].min())
    else:
        forward_close = entry_price - last_close
        mfe = entry_price - _safe_float(window["low"].min())
        mae = _safe_float(window["high"].max()) - entry_price

    first_middle = events["first_middle_bar"]
    first_initial_stop = events["first_initial_stop_bar"]
    first_hard_stop = events["first_hard_stop_bar"]
    return {
        f"forward_close_{prefix}_pct": forward_close / entry_price if entry_price else float("nan"),
        f"forward_close_{prefix}_r": forward_close / risk_distance,
        f"mfe_{prefix}_r": mfe / risk_distance,
        f"mae_{prefix}_r": mae / risk_distance,
        f"hit_middle_{prefix}": int(first_middle is not None and first_middle <= horizon),
        f"hit_initial_stop_{prefix}": int(first_initial_stop is not None and first_initial_stop <= horizon),
        f"hit_hard_stop_{prefix}": int(first_hard_stop is not None and first_hard_stop <= horizon),
    }


def _signal_label(metrics: dict[str, Any]) -> str:
    future_bars = int(metrics["future_bars_available"])
    if future_bars <= 0:
        return "no_forward_data"

    first_middle = metrics["first_middle_bar"]
    first_initial_stop = metrics["first_initial_stop_bar"]
    first_hard_stop = metrics["first_hard_stop_bar"]
    mfe_20d = _safe_float(metrics.get("mfe_20d_r"))
    mae_10d = _safe_float(metrics.get("mae_10d_r"))
    mfe_10d = _safe_float(metrics.get("mfe_10d_r"))

    if first_middle is not None and first_hard_stop is not None and first_middle == first_hard_stop:
        return "ambiguous_middle_hard_same_bar"
    if first_middle is not None and (first_hard_stop is None or first_middle < first_hard_stop):
        if first_middle <= 5 and (first_initial_stop is None or first_middle < first_initial_stop):
            return "clean_reversion"
        if first_initial_stop is not None and first_initial_stop <= first_middle:
            return "stop_first_delayed_reversion"
        return "delayed_reversion"
    if first_hard_stop is not None and (first_middle is None or first_hard_stop < first_middle):
        return "trend_continuation"
    if not pd.isna(mfe_20d) and mfe_20d >= 1.0:
        return "partial_reversion_no_middle"
    if not pd.isna(mae_10d) and not pd.isna(mfe_10d) and mae_10d >= 1.5 and mfe_10d < 0.5:
        return "adverse_no_recovery"
    return "weak_or_no_edge"


def _candidate_metrics(row: pd.Series, history: pd.DataFrame) -> dict[str, Any]:
    signal_date = _to_local_date(row["signal_date"])
    direction = str(row["direction"])
    entry_price = _safe_float(row.get("planned_entry_price"))
    stop_price = _safe_float(row.get("stop_price"))
    risk_distance = _safe_float(row.get("stop_distance"))
    if pd.isna(risk_distance) or risk_distance <= 0:
        risk_distance = abs(entry_price - stop_price) if not pd.isna(stop_price) else float("nan")
    if pd.isna(risk_distance) or risk_distance <= 0:
        risk_distance = max(abs(entry_price) * 0.02, 1e-9)

    if pd.isna(entry_price) or entry_price <= 0:
        current = history[history["date"] <= signal_date].tail(1)
        entry_price = _safe_float(current["close"].iloc[-1]) if not current.empty else float("nan")

    if direction == "long":
        hard_stop_price = entry_price - HARD_STOP_R_MULTIPLE * risk_distance
    else:
        hard_stop_price = entry_price + HARD_STOP_R_MULTIPLE * risk_distance

    current_or_prior = history[history["date"] <= signal_date].tail(1)
    future = history[history["date"] > signal_date].head(max(HORIZONS)).copy()
    events = _event_flags(direction, future, entry_price, stop_price, hard_stop_price)

    metrics: dict[str, Any] = {
        "entry_price_for_attribution": entry_price,
        "stop_price_for_attribution": stop_price,
        "risk_distance_for_attribution": risk_distance,
        "hard_stop_price_for_attribution": hard_stop_price,
        "future_bars_available": int(len(future)),
        **events,
        "entry_pre_ret_5d": float("nan"),
        "entry_pre_ret_20d": float("nan"),
        "entry_channel_position_20": float("nan"),
        "entry_range_pct_20": float("nan"),
        "entry_range_pct_zscore_120": float("nan"),
    }
    if not current_or_prior.empty:
        prior = current_or_prior.iloc[-1]
        metrics.update(
            {
                "entry_pre_ret_5d": _safe_float(prior.get("ret_5d")),
                "entry_pre_ret_20d": _safe_float(prior.get("ret_20d")),
                "entry_channel_position_20": _safe_float(prior.get("channel_position_20")),
                "entry_range_pct_20": _safe_float(prior.get("range_pct_20")),
                "entry_range_pct_zscore_120": _safe_float(prior.get("range_pct_zscore_120")),
            }
        )

    for horizon in HORIZONS:
        metrics.update(_horizon_metrics(direction, future, horizon, entry_price, risk_distance, events))
    metrics["signal_label"] = _signal_label(metrics)
    metrics["middle_before_initial_stop_20d"] = int(
        events["first_middle_bar"] is not None
        and (events["first_initial_stop_bar"] is None or events["first_middle_bar"] < events["first_initial_stop_bar"])
    )
    metrics["initial_stop_before_middle_20d"] = int(
        events["first_initial_stop_bar"] is not None
        and (events["first_middle_bar"] is None or events["first_initial_stop_bar"] <= events["first_middle_bar"])
    )
    return metrics


def _build_detail(candidates: pd.DataFrame) -> pd.DataFrame:
    contracts = set(candidates["contract_vt_symbol"].dropna().astype(str))
    bars_by_contract = _prepare_bars(contracts)

    rows: list[dict[str, Any]] = []
    for _, row in candidates.iterrows():
        contract = str(row["contract_vt_symbol"])
        history = bars_by_contract.get(contract, pd.DataFrame())
        metrics = _candidate_metrics(row, history)
        rows.append(
            {
                "candidate_index": int(row["candidate_index"]),
                "signal_date": row["signal_date"],
                "signal_year": int(row["signal_year"]),
                "product_vt_symbol": str(row["product_vt_symbol"]),
                "contract_vt_symbol": contract,
                "direction": str(row["direction"]),
                "signal": str(row.get("signal", "")),
                "entry_context": str(row.get("entry_context", "")),
                "candidate_status": str(row.get("candidate_status", "")),
                "skip_reason": str(row.get("skip_reason", "")),
                "is_opened": int(_safe_float(row.get("is_opened"), 0.0)),
                "selected_volume": _safe_float(row.get("selected_volume"), 0.0),
                "rsi_value": _safe_float(row.get("rsi_value")),
                "env_avg_range_pct_zscore_120": _safe_float(row.get("env_avg_range_pct_zscore_120")),
                "env_avg_close_position_60d": _safe_float(row.get("env_avg_close_position_60d")),
                "selection_pairwise_feature_ret_20d_zscore_120": _safe_float(
                    row.get("selection_pairwise_feature_ret_20d_zscore_120")
                ),
                **metrics,
            }
        )
    return pd.DataFrame(rows)


def _rate(series: pd.Series, value: str) -> float:
    if series.empty:
        return 0.0
    return float(series.eq(value).mean())


def _summarize(detail: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    if detail.empty:
        return pd.DataFrame()

    frame = detail.copy()
    if not group_cols:
        frame["_all"] = "all"
        group_cols = ["_all"]

    summary = frame.groupby(group_cols, dropna=False).agg(
        signals=("candidate_index", "size"),
        opened=("is_opened", "sum"),
        opened_rate=("is_opened", "mean"),
        clean_reversion_rate=("signal_label", lambda s: _rate(s, "clean_reversion")),
        delayed_reversion_rate=("signal_label", lambda s: _rate(s, "delayed_reversion")),
        stop_first_delayed_reversion_rate=(
            "signal_label",
            lambda s: _rate(s, "stop_first_delayed_reversion"),
        ),
        trend_continuation_rate=("signal_label", lambda s: _rate(s, "trend_continuation")),
        partial_reversion_no_middle_rate=("signal_label", lambda s: _rate(s, "partial_reversion_no_middle")),
        weak_or_no_edge_rate=("signal_label", lambda s: _rate(s, "weak_or_no_edge")),
        avg_forward_close_10d_r=("forward_close_10d_r", "mean"),
        avg_mfe_10d_r=("mfe_10d_r", "mean"),
        avg_mae_10d_r=("mae_10d_r", "mean"),
        avg_mfe_20d_r=("mfe_20d_r", "mean"),
        avg_mae_20d_r=("mae_20d_r", "mean"),
        middle_before_stop_20d_rate=("middle_before_initial_stop_20d", "mean"),
        stop_before_middle_20d_rate=("initial_stop_before_middle_20d", "mean"),
        avg_entry_pre_ret_20d=("entry_pre_ret_20d", "mean"),
        avg_entry_channel_position_20=("entry_channel_position_20", "mean"),
        avg_entry_range_pct_zscore_120=("entry_range_pct_zscore_120", "mean"),
        avg_rsi=("rsi_value", "mean"),
    ).reset_index()

    if "_all" in summary.columns:
        summary = summary.drop(columns=["_all"])
    return summary.sort_values(["signals"], ascending=False).reset_index(drop=True)


def _write_report(
    detail: pd.DataFrame,
    overall: pd.DataFrame,
    product_direction_summary: pd.DataFrame,
    year_direction_summary: pd.DataFrame,
    status_summary: pd.DataFrame,
    label_summary: pd.DataFrame,
) -> None:
    lines = [
        "# QMT震荡Core4 V8信号层归因",
        "",
        "## 范围",
        "- 只读取v8候选信号快照和K线历史，不运行新策略回测。",
        "- 不新增交易规则、不调参数、不修改第78趋势策略。",
        "- 未来路径从信号日之后的K线开始统计，避免把信号日本身高低点当作事后优势。",
        "- 研究对象：`y.DCE long`、`PF.CZCE long`、`nr.INE long`、`cs.DCE short`。",
        "",
        "## 总览",
        overall.to_markdown(index=False) if not overall.empty else "- 无。",
        "",
        "## 按品种和方向",
        product_direction_summary.to_markdown(index=False) if not product_direction_summary.empty else "- 无。",
        "",
        "## 按年份和方向",
        year_direction_summary.to_markdown(index=False) if not year_direction_summary.empty else "- 无。",
        "",
        "## 按开仓状态",
        status_summary.to_markdown(index=False) if not status_summary.empty else "- 无。",
        "",
        "## 按信号标签",
        label_summary.to_markdown(index=False) if not label_summary.empty else "- 无。",
        "",
        "## 标签说明",
        "- `clean_reversion`：5日内先触达通道中轴，且未先触发初始止损。",
        "- `delayed_reversion`：20日内先于硬止损触达通道中轴，但速度不够快。",
        "- `stop_first_delayed_reversion`：先触发初始止损，再触达中轴，说明交易止损会早于信号修复。",
        "- `trend_continuation`：先触发2R硬止损，或明显先进入趋势延续。",
        "- `partial_reversion_no_middle`：20日MFE达到1R但未触达中轴。",
        "- `weak_or_no_edge`：20日内没有清晰均值回归，也没有极端趋势延续。",
        "",
        "## 输出",
        f"- 明细：`{DETAIL_PATH}`",
        f"- 品种方向汇总：`{PRODUCT_DIRECTION_SUMMARY_PATH}`",
        f"- 年份方向汇总：`{YEAR_DIRECTION_SUMMARY_PATH}`",
        f"- 开仓状态汇总：`{STATUS_SUMMARY_PATH}`",
        f"- 标签汇总：`{LABEL_SUMMARY_PATH}`",
        f"- JSON摘要：`{SUMMARY_JSON_PATH}`",
    ]
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def _json_safe_records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    if frame.empty:
        return []
    safe = frame.where(pd.notna(frame), None)
    return safe.to_dict(orient="records")


def run_analysis() -> dict[str, Any]:
    candidates = _load_candidates()
    detail = _build_detail(candidates)
    overall = _summarize(detail, [])
    product_direction_summary = _summarize(detail, ["product_vt_symbol", "direction"])
    year_direction_summary = _summarize(detail, ["signal_year", "direction"])
    status_summary = _summarize(detail, ["candidate_status", "skip_reason"])
    label_summary = _summarize(detail, ["signal_label"])

    detail.to_csv(DETAIL_PATH, index=False, encoding="utf-8-sig")
    product_direction_summary.to_csv(PRODUCT_DIRECTION_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    year_direction_summary.to_csv(YEAR_DIRECTION_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    status_summary.to_csv(STATUS_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    label_summary.to_csv(LABEL_SUMMARY_PATH, index=False, encoding="utf-8-sig")

    summary = {
        "model_tag": MODEL_TAG,
        "source_prefix": SOURCE_PREFIX,
        "candidate_signals": int(len(detail)),
        "opened_signals": int(detail["is_opened"].sum()) if not detail.empty else 0,
        "overall": _json_safe_records(overall),
        "product_direction_summary": _json_safe_records(product_direction_summary),
        "label_summary": _json_safe_records(label_summary),
        "outputs": {
            "detail": str(DETAIL_PATH),
            "product_direction_summary": str(PRODUCT_DIRECTION_SUMMARY_PATH),
            "year_direction_summary": str(YEAR_DIRECTION_SUMMARY_PATH),
            "status_summary": str(STATUS_SUMMARY_PATH),
            "label_summary": str(LABEL_SUMMARY_PATH),
            "report": str(REPORT_PATH),
        },
    }
    SUMMARY_JSON_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(
        detail,
        overall,
        product_direction_summary,
        year_direction_summary,
        status_summary,
        label_summary,
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze range reversion Core4 signal-level forward paths.")
    parser.add_argument("--source-prefix", default=SOURCE_PREFIX)
    parser.add_argument("--model-tag", default=MODEL_TAG)
    args = parser.parse_args()

    _configure_paths(source_prefix=args.source_prefix, model_tag=args.model_tag)
    summary = run_analysis()
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
