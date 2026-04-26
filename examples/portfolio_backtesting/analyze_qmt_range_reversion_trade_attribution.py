from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from run_qmt_alignment_backtest import (
    OUTPUT_DIR,
    _build_trade_link_map,
    _load_trade_review_bars,
    _match_entry_risk_to_trades,
    _normalize_trade_review_input,
)


PREFIXES: tuple[str, ...] = (
    "qmt_range_reversion_v6_strong_score",
    "qmt_range_reversion_v7_intraday_stop",
)

ROUNDTRIPS_CSV_PATH: Path = OUTPUT_DIR / "qmt_range_reversion_trade_attribution_roundtrips.csv"
SUMMARY_CSV_PATH: Path = OUTPUT_DIR / "qmt_range_reversion_trade_attribution_summary.csv"
EXIT_REASON_CSV_PATH: Path = OUTPUT_DIR / "qmt_range_reversion_trade_attribution_by_exit_reason.csv"
PRODUCT_CSV_PATH: Path = OUTPUT_DIR / "qmt_range_reversion_trade_attribution_by_product.csv"
DIRECTION_CSV_PATH: Path = OUTPUT_DIR / "qmt_range_reversion_trade_attribution_by_direction.csv"
FAILURE_TYPE_CSV_PATH: Path = OUTPUT_DIR / "qmt_range_reversion_trade_attribution_by_failure_type.csv"
YEAR_CSV_PATH: Path = OUTPUT_DIR / "qmt_range_reversion_trade_attribution_by_year.csv"
RSI_BUCKET_CSV_PATH: Path = OUTPUT_DIR / "qmt_range_reversion_trade_attribution_by_rsi_bucket.csv"
STOP_DISTANCE_BUCKET_CSV_PATH: Path = OUTPUT_DIR / "qmt_range_reversion_trade_attribution_by_stop_distance_bucket.csv"
REPORT_PATH: Path = OUTPUT_DIR / "qmt_range_reversion_trade_attribution_report.md"


@dataclass(frozen=True)
class RoundtripFiles:
    prefix: str
    trades: Path
    entry_risk: Path
    candidates: Path


def _files_for_prefix(prefix: str) -> RoundtripFiles:
    return RoundtripFiles(
        prefix=prefix,
        trades=OUTPUT_DIR / f"{prefix}_trades_2020_2026_04.csv",
        entry_risk=OUTPUT_DIR / f"{prefix}_entry_risk_diagnostics_2020_2026_04.csv",
        candidates=OUTPUT_DIR / f"{prefix}_entry_candidate_snapshots_2020_2026_04.csv",
    )


def _load_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def _position_direction_from_open(direction: str) -> str:
    return "long" if str(direction) == "Long" else "short"


def _product_from_vt_symbol(vt_symbol: str) -> str:
    symbol = str(vt_symbol).split(".", 1)[0]
    letters = "".join(ch for ch in symbol if ch.isalpha())
    return letters or symbol


def _match_candidate(
    candidates_df: pd.DataFrame,
    risk_row: dict[str, Any] | None,
    open_trade: dict[str, Any],
) -> dict[str, Any] | None:
    if candidates_df.empty:
        return None

    contract = str((risk_row or {}).get("contract_vt_symbol") or open_trade["vt_symbol"])
    direction = str((risk_row or {}).get("direction") or _position_direction_from_open(open_trade["direction"]))
    volume = float((risk_row or {}).get("volume") or open_trade["volume"])
    trade_dt = pd.Timestamp(open_trade["datetime"])

    df = candidates_df.copy()
    df = df[
        (df["candidate_status"].astype(str) == "opened")
        & (df["contract_vt_symbol"].astype(str) == contract)
        & (df["direction"].astype(str) == direction)
    ].copy()
    if df.empty:
        return None

    df["datetime"] = pd.to_datetime(df["datetime"]).dt.tz_localize(None)
    df["volume_diff"] = (pd.to_numeric(df["selected_volume"], errors="coerce") - volume).abs()
    df["time_diff"] = (trade_dt - df["datetime"]).abs()
    df = df[df["time_diff"] <= pd.Timedelta(days=5)]
    if df.empty:
        return None
    df.sort_values(["volume_diff", "time_diff", "candidate_index"], inplace=True)
    return df.iloc[0].to_dict()


def _price_path_metrics(
    bars_df: pd.DataFrame | None,
    *,
    entry_date: pd.Timestamp,
    exit_date: pd.Timestamp,
    direction: str,
    entry_price: float,
    stop_distance: float,
) -> dict[str, Any]:
    empty = {
        "holding_days": None,
        "mfe_price": None,
        "mae_price": None,
        "mfe_pct": None,
        "mae_pct": None,
        "mfe_r": None,
        "mae_r": None,
        "first_mfe_0_5r_day": None,
        "first_mae_1r_day": None,
    }
    if bars_df is None or bars_df.empty:
        return empty

    entry_date = pd.Timestamp(entry_date).normalize()
    exit_date = pd.Timestamp(exit_date).normalize()
    path = bars_df[(bars_df["date"] >= entry_date) & (bars_df["date"] <= exit_date)].copy()
    if path.empty:
        return empty

    if direction == "long":
        favorable = pd.to_numeric(path["high"], errors="coerce") - entry_price
        adverse = pd.to_numeric(path["low"], errors="coerce") - entry_price
    else:
        favorable = entry_price - pd.to_numeric(path["low"], errors="coerce")
        adverse = entry_price - pd.to_numeric(path["high"], errors="coerce")

    mfe_price = float(favorable.max())
    mae_price = float(adverse.min())
    risk_denominator = stop_distance if stop_distance and stop_distance > 0 else float("nan")

    first_mfe_day = None
    first_mae_day = None
    if risk_denominator == risk_denominator:
        favorable_r = favorable / risk_denominator
        adverse_r = adverse / risk_denominator
        mfe_hits = path.loc[favorable_r >= 0.5, "date"]
        mae_hits = path.loc[adverse_r <= -1.0, "date"]
        if not mfe_hits.empty:
            first_mfe_day = pd.Timestamp(mfe_hits.iloc[0]).date().isoformat()
        if not mae_hits.empty:
            first_mae_day = pd.Timestamp(mae_hits.iloc[0]).date().isoformat()

    return {
        "holding_days": int(len(path)),
        "mfe_price": mfe_price,
        "mae_price": mae_price,
        "mfe_pct": mfe_price / entry_price if entry_price else None,
        "mae_pct": mae_price / entry_price if entry_price else None,
        "mfe_r": mfe_price / risk_denominator if risk_denominator == risk_denominator else None,
        "mae_r": mae_price / risk_denominator if risk_denominator == risk_denominator else None,
        "first_mfe_0_5r_day": first_mfe_day,
        "first_mae_1r_day": first_mae_day,
    }


def _failure_type(row: pd.Series) -> str:
    pnl = float(row.get("pnl") or 0.0)
    mfe_r = row.get("mfe_r")
    mae_r = row.get("mae_r")
    exit_reason = str(row.get("exit_reason") or "")
    if pnl > 0:
        return "winner"
    if pd.notna(mfe_r) and float(mfe_r) >= 1.0:
        return "gave_back_profit"
    if "base_stop" in exit_reason and (pd.isna(mfe_r) or float(mfe_r) < 0.5):
        return "stop_without_0_5r_mfe"
    if pd.notna(mae_r) and float(mae_r) <= -1.0 and (pd.isna(mfe_r) or float(mfe_r) < 0.5):
        return "immediate_adverse"
    if "time_exit" in exit_reason:
        return "time_decay_loss"
    return "small_or_late_loss"


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


def _build_roundtrips_for_prefix(files: RoundtripFiles) -> pd.DataFrame:
    trades_df = _load_csv(files.trades)
    entry_risk_df = _load_csv(files.entry_risk)
    candidates_df = _load_csv(files.candidates)
    if trades_df.empty:
        return pd.DataFrame()

    trades_df = _normalize_trade_review_input(trades_df, "datetime")
    entry_risk_df = _normalize_trade_review_input(entry_risk_df, "datetime") if not entry_risk_df.empty else entry_risk_df
    bars_by_contract = _load_trade_review_bars(trades_df)
    link_map = _build_trade_link_map(trades_df)
    risk_by_trade_id = _match_entry_risk_to_trades(trades_df, entry_risk_df) if not entry_risk_df.empty else {}
    trade_by_id = {str(row["trade_id"]): row for row in trades_df.to_dict("records")}

    rows: list[dict[str, Any]] = []
    for open_trade in trades_df[trades_df["offset"] == "Open"].to_dict("records"):
        trade_id = str(open_trade["trade_id"])
        exit_ids = [str(value) for value in link_map.get(trade_id, {}).get("exit_trade_ids", [])]
        if not exit_ids:
            continue

        exit_trades = [trade_by_id[exit_id] for exit_id in exit_ids if exit_id in trade_by_id]
        if not exit_trades:
            continue

        total_exit_volume = sum(float(row["volume"]) for row in exit_trades)
        if total_exit_volume <= 0:
            continue

        exit_price = sum(float(row["price"]) * float(row["volume"]) for row in exit_trades) / total_exit_volume
        exit_dt = max(pd.Timestamp(row["datetime"]) for row in exit_trades)
        exit_date = max(pd.Timestamp(row["date"]) for row in exit_trades)
        exit_reason = "|".join(sorted({str(row.get("exit_reason") or "") for row in exit_trades if row.get("exit_reason")}))

        direction = _position_direction_from_open(str(open_trade["direction"]))
        entry_price = float(open_trade["price"])
        volume = float(open_trade["volume"])
        risk_row = risk_by_trade_id.get(trade_id)
        candidate_row = _match_candidate(candidates_df, risk_row, open_trade)

        stop_price = float((risk_row or {}).get("stop_price") or 0.0)
        stop_distance = abs(entry_price - stop_price) if stop_price > 0 else float((risk_row or {}).get("stop_distance") or 0.0)
        size = float((risk_row or {}).get("size") or 1.0)
        price_move = exit_price - entry_price if direction == "long" else entry_price - exit_price
        pnl = price_move * size * volume
        r_multiple = price_move / stop_distance if stop_distance > 0 else None

        bars_df = bars_by_contract.get(str(open_trade["vt_symbol"]))
        path_metrics = _price_path_metrics(
            bars_df,
            entry_date=pd.Timestamp(open_trade["date"]),
            exit_date=exit_date,
            direction=direction,
            entry_price=entry_price,
            stop_distance=stop_distance,
        )

        rsi_value = (candidate_row or {}).get("rsi_value")
        stop_distance_pct = stop_distance / entry_price if entry_price else None
        row = {
            "version": files.prefix,
            "entry_trade_id": trade_id,
            "exit_trade_ids": ",".join(exit_ids),
            "entry_datetime": pd.Timestamp(open_trade["datetime"]).isoformat(),
            "exit_datetime": exit_dt.isoformat(),
            "entry_date": pd.Timestamp(open_trade["date"]).date().isoformat(),
            "exit_date": exit_date.date().isoformat(),
            "entry_year": int(pd.Timestamp(open_trade["date"]).year),
            "vt_symbol": str(open_trade["vt_symbol"]),
            "product_symbol": _product_from_vt_symbol(str(open_trade["vt_symbol"])),
            "direction": direction,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "volume": volume,
            "size": size,
            "pnl": pnl,
            "price_move": price_move,
            "return_pct": price_move / entry_price if entry_price else None,
            "r_multiple": r_multiple,
            "exit_reason": exit_reason,
            "stop_price": stop_price,
            "stop_distance": stop_distance,
            "stop_distance_pct": stop_distance_pct,
            "risk_multiplier": (risk_row or {}).get("risk_multiplier"),
            "loss_streak": (risk_row or {}).get("loss_streak"),
            "portfolio_drawdown_pct": (risk_row or {}).get("portfolio_drawdown_pct"),
            "active_positions_before": (candidate_row or {}).get("active_positions_before"),
            "bullish_alignment": (candidate_row or {}).get("bullish_alignment"),
            "bearish_alignment": (candidate_row or {}).get("bearish_alignment"),
            "breakout": (candidate_row or {}).get("breakout"),
            "rsi_value": rsi_value,
            "rsi_bucket": _bucket_rsi(rsi_value),
            "stop_distance_pct_bucket": _bucket_stop_distance_pct(stop_distance_pct),
            "candidate_loss_streak": (candidate_row or {}).get("loss_streak"),
        }
        row.update(path_metrics)
        rows.append(row)

    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["failure_type"] = df.apply(_failure_type, axis=1)
    return df


def _group_summary(df: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()

    def win_rate(series: pd.Series) -> float:
        return float((series > 0).mean()) if len(series) else 0.0

    summary = (
        df.groupby(group_cols, dropna=False)
        .agg(
            trades=("pnl", "size"),
            total_pnl=("pnl", "sum"),
            avg_pnl=("pnl", "mean"),
            win_rate=("pnl", win_rate),
            avg_r=("r_multiple", "mean"),
            avg_mfe_r=("mfe_r", "mean"),
            avg_mae_r=("mae_r", "mean"),
            base_stop_count=("exit_reason", lambda s: int(s.astype(str).str.contains("base_stop").sum())),
            gaveback_count=("failure_type", lambda s: int((s == "gave_back_profit").sum())),
            immediate_bad_count=("failure_type", lambda s: int(s.isin(["stop_without_0_5r_mfe", "immediate_adverse"]).sum())),
        )
        .reset_index()
    )
    summary["base_stop_rate"] = summary["base_stop_count"] / summary["trades"]
    summary["gaveback_rate"] = summary["gaveback_count"] / summary["trades"]
    summary["immediate_bad_rate"] = summary["immediate_bad_count"] / summary["trades"]
    summary.sort_values(["total_pnl", "trades"], ascending=[True, False], inplace=True)
    return summary


def _build_report(
    roundtrips: pd.DataFrame,
    summary: pd.DataFrame,
    by_exit_reason: pd.DataFrame,
    by_product: pd.DataFrame,
    by_direction: pd.DataFrame,
    by_failure_type: pd.DataFrame,
    by_year: pd.DataFrame,
    by_rsi_bucket: pd.DataFrame,
    by_stop_distance_bucket: pd.DataFrame,
) -> str:
    lines: list[str] = [
        "# QMT Range Reversion Trade Attribution",
        "",
        "## 结论",
    ]

    for version in PREFIXES:
        version_df = roundtrips[roundtrips["version"] == version]
        if version_df.empty:
            continue
        total_pnl = float(version_df["pnl"].sum())
        win_rate = float((version_df["pnl"] > 0).mean())
        immediate_rate = float(version_df["failure_type"].isin(["stop_without_0_5r_mfe", "immediate_adverse"]).mean())
        gaveback_rate = float((version_df["failure_type"] == "gave_back_profit").mean())
        base_stop_rate = float(version_df["exit_reason"].astype(str).str.contains("base_stop").mean())
        lines.append(
            f"- `{version}`：roundtrip `{len(version_df)}`，总PnL `{total_pnl:,.0f}`，"
            f"交易胜率 `{win_rate:.2%}`，硬止损率 `{base_stop_rate:.2%}`，"
            f"入场后几乎无0.5R顺向空间的失败率 `{immediate_rate:.2%}`，"
            f"有1R浮盈后回吐亏损率 `{gaveback_rate:.2%}`。"
        )

    lines.extend(
        [
            "",
            "核心判断：当前震荡策略的主要问题更像入场边际不足，而不是单纯止损或止盈管理问题。"
            "如果亏损大多没有给出至少0.5R的顺向空间，继续调止盈/移动止损意义有限；"
            "应该先证明哪些品种和状态真的有均值回归倾向。",
            "",
            "## 失败类型",
            by_failure_type.to_markdown(index=False),
            "",
            "## 出场原因",
            by_exit_reason.head(20).to_markdown(index=False),
            "",
            "## 方向",
            by_direction.to_markdown(index=False),
            "",
            "## 年份",
            by_year.to_markdown(index=False),
            "",
            "## RSI分桶",
            by_rsi_bucket.to_markdown(index=False),
            "",
            "## 止损距离分桶",
            by_stop_distance_bucket.to_markdown(index=False),
            "",
            "## 亏损最集中的品种",
            by_product.sort_values("total_pnl").head(20).to_markdown(index=False),
            "",
            "## 可验证的规则假设",
            "- 不建议直接剔除亏损品种；先做跨年份稳定性验证，否则很容易变成品种过拟合。",
            "- 不建议继续微调RSI/ADX/ER阈值；复盘重点应放在“入场后是否先给0.5R顺向空间”。",
            "- 如果后续重写v8，优先考虑状态过滤：趋势延伸、ATR扩张、通道突破后的假震荡需要被挡掉。",
            "- 如果少数品种稳定贡献正PnL，可以先做品种/状态交叉归因，再决定是否形成白名单或动态权重。",
            "",
            "## 输出文件",
            f"- roundtrips: `{ROUNDTRIPS_CSV_PATH}`",
            f"- summary: `{SUMMARY_CSV_PATH}`",
            f"- by_exit_reason: `{EXIT_REASON_CSV_PATH}`",
            f"- by_product: `{PRODUCT_CSV_PATH}`",
            f"- by_direction: `{DIRECTION_CSV_PATH}`",
            f"- by_failure_type: `{FAILURE_TYPE_CSV_PATH}`",
            f"- by_year: `{YEAR_CSV_PATH}`",
            f"- by_rsi_bucket: `{RSI_BUCKET_CSV_PATH}`",
            f"- by_stop_distance_bucket: `{STOP_DISTANCE_BUCKET_CSV_PATH}`",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    roundtrip_frames = [_build_roundtrips_for_prefix(_files_for_prefix(prefix)) for prefix in PREFIXES]
    roundtrips = pd.concat([df for df in roundtrip_frames if not df.empty], ignore_index=True)
    if roundtrips.empty:
        raise RuntimeError("No roundtrip records were built.")

    summary = _group_summary(roundtrips, ["version"])
    by_exit_reason = _group_summary(roundtrips, ["version", "exit_reason"])
    by_product = _group_summary(roundtrips, ["version", "product_symbol"])
    by_direction = _group_summary(roundtrips, ["version", "direction"])
    by_failure_type = _group_summary(roundtrips, ["version", "failure_type"])
    by_year = _group_summary(roundtrips, ["version", "entry_year"])
    by_rsi_bucket = _group_summary(roundtrips, ["version", "rsi_bucket"])
    by_stop_distance_bucket = _group_summary(roundtrips, ["version", "stop_distance_pct_bucket"])

    roundtrips.to_csv(ROUNDTRIPS_CSV_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_CSV_PATH, index=False, encoding="utf-8-sig")
    by_exit_reason.to_csv(EXIT_REASON_CSV_PATH, index=False, encoding="utf-8-sig")
    by_product.to_csv(PRODUCT_CSV_PATH, index=False, encoding="utf-8-sig")
    by_direction.to_csv(DIRECTION_CSV_PATH, index=False, encoding="utf-8-sig")
    by_failure_type.to_csv(FAILURE_TYPE_CSV_PATH, index=False, encoding="utf-8-sig")
    by_year.to_csv(YEAR_CSV_PATH, index=False, encoding="utf-8-sig")
    by_rsi_bucket.to_csv(RSI_BUCKET_CSV_PATH, index=False, encoding="utf-8-sig")
    by_stop_distance_bucket.to_csv(STOP_DISTANCE_BUCKET_CSV_PATH, index=False, encoding="utf-8-sig")
    REPORT_PATH.write_text(
        _build_report(
            roundtrips,
            summary,
            by_exit_reason,
            by_product,
            by_direction,
            by_failure_type,
            by_year,
            by_rsi_bucket,
            by_stop_distance_bucket,
        ),
        encoding="utf-8",
    )

    print(summary.to_string(index=False))
    print()
    print(by_failure_type.to_string(index=False))
    print()
    print(f"report: {REPORT_PATH}")


if __name__ == "__main__":
    main()
