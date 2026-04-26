from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from run_qmt_alignment_backtest import OUTPUT_DIR, _load_trade_review_bars


SOURCE_PREFIX: str = "qmt_range_reversion_v6_strong_score"
SOURCE_CANDIDATES_PATH: Path = OUTPUT_DIR / f"{SOURCE_PREFIX}_entry_candidate_snapshots_2020_2026_04.csv"

ROWS_CSV_PATH: Path = OUTPUT_DIR / "qmt_range_reversion_signal_forward_stability_rows.csv"
SUMMARY_CSV_PATH: Path = OUTPUT_DIR / "qmt_range_reversion_signal_forward_stability_summary.csv"
BY_YEAR_CSV_PATH: Path = OUTPUT_DIR / "qmt_range_reversion_signal_forward_stability_by_year.csv"
BY_DIRECTION_CSV_PATH: Path = OUTPUT_DIR / "qmt_range_reversion_signal_forward_stability_by_direction.csv"
BY_PRODUCT_CSV_PATH: Path = OUTPUT_DIR / "qmt_range_reversion_signal_forward_stability_by_product.csv"
BY_PRODUCT_YEAR_CSV_PATH: Path = OUTPUT_DIR / "qmt_range_reversion_signal_forward_stability_by_product_year.csv"
BY_RSI_BUCKET_CSV_PATH: Path = OUTPUT_DIR / "qmt_range_reversion_signal_forward_stability_by_rsi_bucket.csv"
BY_STOP_BUCKET_CSV_PATH: Path = OUTPUT_DIR / "qmt_range_reversion_signal_forward_stability_by_stop_bucket.csv"
REPORT_PATH: Path = OUTPUT_DIR / "qmt_range_reversion_signal_forward_stability_report.md"


def _product_from_vt_symbol(vt_symbol: str) -> str:
    symbol = str(vt_symbol).split(".", 1)[0]
    letters = "".join(ch for ch in symbol if ch.isalpha())
    return letters or symbol


def _bucket_rsi(value: Any) -> str:
    if pd.isna(value):
        return "unknown"
    value_f = float(value)
    if value_f < 35:
        return "<35"
    if value_f < 45:
        return "35-45"
    if value_f < 55:
        return "45-55"
    if value_f < 65:
        return "55-65"
    return ">=65"


def _bucket_stop_distance_pct(value: Any) -> str:
    if pd.isna(value):
        return "unknown"
    value_f = float(value)
    if value_f < 0.01:
        return "<1%"
    if value_f < 0.02:
        return "1%-2%"
    if value_f < 0.04:
        return "2%-4%"
    return ">=4%"


def _directional_move(direction: str, entry_price: float, future_price: float) -> float:
    if direction == "long":
        return future_price - entry_price
    return entry_price - future_price


def _path_metrics(
    bars_df: pd.DataFrame,
    *,
    entry_date: pd.Timestamp,
    direction: str,
    entry_price: float,
    stop_distance: float,
) -> dict[str, Any] | None:
    matches = bars_df.index[bars_df["date"] == entry_date].tolist()
    if not matches:
        return None

    entry_index = int(matches[0])
    if entry_index + 1 >= len(bars_df):
        return None

    path = bars_df.iloc[entry_index + 1 : min(entry_index + 6, len(bars_df))].copy()
    if path.empty:
        return None

    result: dict[str, Any] = {
        "available_forward_days": int(len(path)),
    }
    risk_denominator = stop_distance if stop_distance and stop_distance > 0 else float("nan")

    for horizon in (1, 3, 5):
        if entry_index + horizon < len(bars_df):
            close_price = float(bars_df.iloc[entry_index + horizon]["close"])
            move = _directional_move(direction, entry_price, close_price)
            result[f"fwd_{horizon}d_pct"] = move / entry_price if entry_price else float("nan")
            result[f"fwd_{horizon}d_r"] = move / risk_denominator if risk_denominator == risk_denominator else float("nan")
        else:
            result[f"fwd_{horizon}d_pct"] = float("nan")
            result[f"fwd_{horizon}d_r"] = float("nan")

    if direction == "long":
        favorable = pd.to_numeric(path["high"], errors="coerce") - entry_price
        adverse = pd.to_numeric(path["low"], errors="coerce") - entry_price
    else:
        favorable = entry_price - pd.to_numeric(path["low"], errors="coerce")
        adverse = entry_price - pd.to_numeric(path["high"], errors="coerce")

    mfe_price = float(favorable.max())
    mae_price = float(adverse.min())
    mfe_r = mfe_price / risk_denominator if risk_denominator == risk_denominator else float("nan")
    mae_r = mae_price / risk_denominator if risk_denominator == risk_denominator else float("nan")

    result.update(
        {
            "mfe_5d_pct": mfe_price / entry_price if entry_price else float("nan"),
            "mae_5d_pct": mae_price / entry_price if entry_price else float("nan"),
            "mfe_5d_r": mfe_r,
            "mae_5d_r": mae_r,
            "hit_0_5r_5d": int(mfe_r >= 0.5) if mfe_r == mfe_r else 0,
            "hit_1r_5d": int(mfe_r >= 1.0) if mfe_r == mfe_r else 0,
            "stop_touched_5d": int(mae_r <= -1.0) if mae_r == mae_r else 0,
        }
    )
    return result


def _build_signal_rows() -> pd.DataFrame:
    candidates = pd.read_csv(SOURCE_CANDIDATES_PATH)
    candidates["datetime"] = pd.to_datetime(candidates["datetime"]).dt.tz_localize(None)
    candidates["date"] = pd.to_datetime(candidates["date"]).dt.normalize()
    candidates = candidates[candidates["passed_initial_filter"] == 1].copy()
    candidates.sort_values(["datetime", "contract_vt_symbol", "candidate_index"], inplace=True)

    pseudo_trades = candidates.rename(columns={"contract_vt_symbol": "vt_symbol"})[
        ["datetime", "date", "vt_symbol"]
    ].copy()
    bars_by_contract = _load_trade_review_bars(pseudo_trades)

    rows: list[dict[str, Any]] = []
    for candidate in candidates.to_dict("records"):
        vt_symbol = str(candidate["contract_vt_symbol"])
        bars_df = bars_by_contract.get(vt_symbol)
        if bars_df is None or bars_df.empty:
            continue

        direction = str(candidate["direction"])
        entry_price = float(candidate.get("planned_entry_price") or 0.0)
        stop_distance = float(candidate.get("stop_distance") or 0.0)
        if entry_price <= 0 or stop_distance <= 0:
            continue

        metrics = _path_metrics(
            bars_df,
            entry_date=pd.Timestamp(candidate["date"]),
            direction=direction,
            entry_price=entry_price,
            stop_distance=stop_distance,
        )
        if metrics is None:
            continue

        stop_distance_pct = stop_distance / entry_price
        rsi_value = candidate.get("rsi_value")
        row = {
            "source_prefix": SOURCE_PREFIX,
            "candidate_index": candidate.get("candidate_index"),
            "datetime": pd.Timestamp(candidate["datetime"]).isoformat(),
            "date": pd.Timestamp(candidate["date"]).date().isoformat(),
            "year": int(pd.Timestamp(candidate["date"]).year),
            "product_vt_symbol": candidate.get("product_vt_symbol"),
            "contract_vt_symbol": vt_symbol,
            "product_symbol": _product_from_vt_symbol(vt_symbol),
            "direction": direction,
            "candidate_status": candidate.get("candidate_status"),
            "is_opened": int(candidate.get("is_opened") or 0),
            "entry_price": entry_price,
            "stop_price": float(candidate.get("stop_price") or 0.0),
            "stop_distance": stop_distance,
            "stop_distance_pct": stop_distance_pct,
            "stop_distance_pct_bucket": _bucket_stop_distance_pct(stop_distance_pct),
            "rsi_value": rsi_value,
            "rsi_bucket": _bucket_rsi(rsi_value),
            "active_positions_before": candidate.get("active_positions_before"),
            "bullish_alignment": candidate.get("bullish_alignment"),
            "bearish_alignment": candidate.get("bearish_alignment"),
            "breakout": candidate.get("breakout"),
            "loss_streak": candidate.get("loss_streak"),
            "risk_multiplier": candidate.get("risk_multiplier"),
        }
        row.update(metrics)
        rows.append(row)

    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["positive_1d"] = (df["fwd_1d_r"] > 0).astype(int)
    df["positive_3d"] = (df["fwd_3d_r"] > 0).astype(int)
    df["positive_5d"] = (df["fwd_5d_r"] > 0).astype(int)
    df["good_reversion_5d"] = ((df["mfe_5d_r"] >= 0.5) & (df["stop_touched_5d"] == 0)).astype(int)
    return df


def _group_summary(df: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    summary = (
        df.groupby(group_cols, dropna=False)
        .agg(
            signals=("candidate_index", "size"),
            opened_rate=("is_opened", "mean"),
            avg_fwd_1d_r=("fwd_1d_r", "mean"),
            avg_fwd_3d_r=("fwd_3d_r", "mean"),
            avg_fwd_5d_r=("fwd_5d_r", "mean"),
            positive_1d_rate=("positive_1d", "mean"),
            positive_3d_rate=("positive_3d", "mean"),
            positive_5d_rate=("positive_5d", "mean"),
            avg_mfe_5d_r=("mfe_5d_r", "mean"),
            avg_mae_5d_r=("mae_5d_r", "mean"),
            hit_0_5r_rate=("hit_0_5r_5d", "mean"),
            hit_1r_rate=("hit_1r_5d", "mean"),
            stop_touched_rate=("stop_touched_5d", "mean"),
            good_reversion_rate=("good_reversion_5d", "mean"),
        )
        .reset_index()
    )
    summary.sort_values(["avg_fwd_5d_r", "signals"], ascending=[False, False], inplace=True)
    return summary


def _product_stability(product_year: pd.DataFrame) -> pd.DataFrame:
    if product_year.empty:
        return pd.DataFrame()
    stable = product_year[product_year["signals"] >= 3].copy()
    if stable.empty:
        return pd.DataFrame()
    result = (
        stable.groupby(["product_symbol", "direction"], dropna=False)
        .agg(
            years=("year", "size"),
            positive_years=("avg_fwd_5d_r", lambda s: int((s > 0).sum())),
            total_signals=("signals", "sum"),
            avg_year_fwd_5d_r=("avg_fwd_5d_r", "mean"),
            avg_good_reversion_rate=("good_reversion_rate", "mean"),
            avg_stop_touched_rate=("stop_touched_rate", "mean"),
        )
        .reset_index()
    )
    result["positive_year_rate"] = result["positive_years"] / result["years"]
    result.sort_values(
        ["positive_year_rate", "avg_year_fwd_5d_r", "total_signals"],
        ascending=[False, False, False],
        inplace=True,
    )
    return result


def _build_report(
    rows: pd.DataFrame,
    summary: pd.DataFrame,
    by_direction: pd.DataFrame,
    by_year: pd.DataFrame,
    by_product: pd.DataFrame,
    product_stability: pd.DataFrame,
    by_rsi: pd.DataFrame,
    by_stop: pd.DataFrame,
) -> str:
    lines: list[str] = [
        "# QMT Range Reversion Signal Forward Stability",
        "",
        "## 结论",
    ]
    s = summary.iloc[0]
    lines.append(
        f"- 信号样本 `{int(s['signals'])}` 条，5日方向R均值 `{float(s['avg_fwd_5d_r']):.4f}`，"
        f"5日方向胜率 `{float(s['positive_5d_rate']):.2%}`，"
        f"5日触及0.5R比例 `{float(s['hit_0_5r_rate']):.2%}`，"
        f"5日触及止损比例 `{float(s['stop_touched_rate']):.2%}`，"
        f"好反转比例 `{float(s['good_reversion_rate']):.2%}`。"
    )
    lines.extend(
        [
            "- 这不是交易回测，而是信号前瞻归因；目的在于判断震荡信号是否天然有均值回归边际。",
            "",
            "## 方向",
            by_direction.to_markdown(index=False),
            "",
            "## 年份",
            by_year.to_markdown(index=False),
            "",
            "## 品种方向稳定性",
            product_stability.head(30).to_markdown(index=False) if not product_stability.empty else "无足够样本。",
            "",
            "## 品种",
            by_product.head(30).to_markdown(index=False),
            "",
            "## RSI分桶",
            by_rsi.to_markdown(index=False),
            "",
            "## 止损距离分桶",
            by_stop.to_markdown(index=False),
            "",
            "## 方法",
            "- 使用v6 strong score全部候选信号，不只看实际成交，避免持仓容量和资金管理影响信号归因。",
            "- 入场价使用候选快照的`planned_entry_price`。",
            "- 方向收益：多头为未来价减入场价，空头为入场价减未来价。",
            "- R值使用候选快照的止损距离归一化。",
            "- MFE/MAE使用入场后最多5个交易日的日线high/low计算。",
            "",
            "## 输出文件",
            f"- rows: `{ROWS_CSV_PATH}`",
            f"- summary: `{SUMMARY_CSV_PATH}`",
            f"- by_direction: `{BY_DIRECTION_CSV_PATH}`",
            f"- by_year: `{BY_YEAR_CSV_PATH}`",
            f"- by_product: `{BY_PRODUCT_CSV_PATH}`",
            f"- by_product_year: `{BY_PRODUCT_YEAR_CSV_PATH}`",
            f"- by_rsi_bucket: `{BY_RSI_BUCKET_CSV_PATH}`",
            f"- by_stop_bucket: `{BY_STOP_BUCKET_CSV_PATH}`",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = _build_signal_rows()
    if rows.empty:
        raise RuntimeError("No signal forward rows were built.")

    summary = _group_summary(rows, ["source_prefix"])
    by_direction = _group_summary(rows, ["direction"])
    by_year = _group_summary(rows, ["year"])
    by_product = _group_summary(rows, ["product_symbol", "direction"])
    by_product_year = _group_summary(rows, ["product_symbol", "direction", "year"])
    by_rsi = _group_summary(rows, ["rsi_bucket", "direction"])
    by_stop = _group_summary(rows, ["stop_distance_pct_bucket", "direction"])
    product_stability = _product_stability(by_product_year)

    rows.to_csv(ROWS_CSV_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_CSV_PATH, index=False, encoding="utf-8-sig")
    by_direction.to_csv(BY_DIRECTION_CSV_PATH, index=False, encoding="utf-8-sig")
    by_year.to_csv(BY_YEAR_CSV_PATH, index=False, encoding="utf-8-sig")
    by_product.to_csv(BY_PRODUCT_CSV_PATH, index=False, encoding="utf-8-sig")
    by_product_year.to_csv(BY_PRODUCT_YEAR_CSV_PATH, index=False, encoding="utf-8-sig")
    by_rsi.to_csv(BY_RSI_BUCKET_CSV_PATH, index=False, encoding="utf-8-sig")
    by_stop.to_csv(BY_STOP_BUCKET_CSV_PATH, index=False, encoding="utf-8-sig")
    product_stability.to_csv(
        OUTPUT_DIR / "qmt_range_reversion_signal_forward_stability_product_stability.csv",
        index=False,
        encoding="utf-8-sig",
    )
    REPORT_PATH.write_text(
        _build_report(rows, summary, by_direction, by_year, by_product, product_stability, by_rsi, by_stop),
        encoding="utf-8",
    )

    print(summary.to_string(index=False))
    print()
    print(by_direction.to_string(index=False))
    print()
    print(product_stability.head(20).to_string(index=False) if not product_stability.empty else "No product stability rows.")
    print()
    print(f"report: {REPORT_PATH}")


if __name__ == "__main__":
    main()
