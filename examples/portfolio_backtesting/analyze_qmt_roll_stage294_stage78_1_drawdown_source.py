from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pandas as pd

from run_qmt_alignment_backtest import OUTPUT_DIR


MODEL_TAG = "stage294_stage78_1_drawdown_source_v1"
OUTPUT_PREFIX = "qmt_roll_stage294_stage78_1_drawdown_source"
LINE_ID = "futures_trend_drawdown30_preserve_return"


DAILY_PATH = OUTPUT_DIR / "qmt_roll_official_stage78_1_daily.csv"
POSITION_CHANGES_PATH = OUTPUT_DIR / "qmt_roll_official_stage78_1_position_changes_2020_2026_04.csv"
ENTRY_DIAGNOSTICS_PATH = OUTPUT_DIR / "qmt_roll_official_stage78_1_entry_risk_diagnostics_2020_2026_04.csv"


def _product_from_vt_symbol(vt_symbol: str) -> str:
    text = str(vt_symbol)
    if "." not in text:
        return text
    symbol, exchange = text.split(".", 1)
    product = re.sub(r"\d+", "", symbol)
    return f"{product}.{exchange}"


def _max_drawdown_window(daily_df: pd.DataFrame) -> dict[str, Any]:
    trough = daily_df.loc[daily_df["ddpercent"].idxmin()]
    peak_balance = float(trough["highlevel"])
    peak_candidates = daily_df[(daily_df["date"] <= trough["date"]) & (daily_df["balance"].round(6) == round(peak_balance, 6))]
    peak = peak_candidates.tail(1).iloc[0]
    recovery = daily_df[(daily_df["date"] > trough["date"]) & (daily_df["balance"] >= peak_balance)].head(1)
    return {
        "peak_date": peak["date"],
        "peak_balance": float(peak["balance"]),
        "trough_date": trough["date"],
        "trough_balance": float(trough["balance"]),
        "max_drawdown": float(trough["drawdown"]),
        "max_dd_percent": float(trough["ddpercent"]),
        "recovery_date": recovery.iloc[0]["date"] if not recovery.empty else pd.NaT,
        "recovery_balance": float(recovery.iloc[0]["balance"]) if not recovery.empty else None,
    }


def _summarize_product_pnl(position_df: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    window = position_df[(position_df["date"] > start) & (position_df["date"] <= end)].copy()
    window["product_vt_symbol"] = window["vt_symbol"].map(_product_from_vt_symbol)
    window["active_marker"] = (
        window["start_pos"].abs()
        + window["end_pos"].abs()
        + window["pos_change"].abs()
        + window["trade_count"].abs()
    )
    grouped = (
        window.groupby("product_vt_symbol", as_index=False)
        .agg(
            net_pnl=("net_pnl", "sum"),
            holding_pnl=("holding_pnl", "sum"),
            trading_pnl=("trading_pnl", "sum"),
            slippage=("slippage", "sum"),
            trade_count=("trade_count", "sum"),
            active_days=("active_marker", lambda s: int((s > 0).sum())),
            max_abs_end_pos=("end_pos", lambda s: float(s.abs().max())),
        )
        .sort_values("net_pnl")
        .reset_index(drop=True)
    )
    total_loss = abs(float(grouped[grouped["net_pnl"] < 0]["net_pnl"].sum()))
    if total_loss > 0:
        grouped["loss_share_pct"] = grouped["net_pnl"].apply(lambda x: abs(min(0.0, float(x))) / total_loss * 100.0)
    else:
        grouped["loss_share_pct"] = 0.0
    return grouped


def _summarize_entries(entry_df: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> tuple[pd.DataFrame, pd.DataFrame]:
    entries = entry_df[(entry_df["date"] > start) & (entry_df["date"] <= end)].copy()
    numeric_cols = [
        "selected_volume",
        "selected_volume_ungated",
        "actual_risk_amount",
        "actual_margin_amount",
        "total_margin_in_use_before",
        "portfolio_drawdown_pct",
        "same_direction_correlation_gate_weight",
        "same_direction_correlation_active_count",
        "same_direction_correlation_corr_count",
        "same_direction_correlation_max_corr",
        "same_direction_correlation_avg_corr",
        "loss_streak",
    ]
    for col in numeric_cols:
        if col in entries.columns:
            entries[col] = pd.to_numeric(entries[col], errors="coerce")

    by_product = (
        entries.groupby(["product_vt_symbol", "direction"], as_index=False)
        .agg(
            entries=("entry_index", "count"),
            selected_volume=("selected_volume", "sum"),
            ungated_volume=("selected_volume_ungated", "sum"),
            actual_risk_amount=("actual_risk_amount", "sum"),
            actual_margin_amount=("actual_margin_amount", "sum"),
            avg_portfolio_drawdown_pct=("portfolio_drawdown_pct", "mean"),
            avg_corr_weight=("same_direction_correlation_gate_weight", "mean"),
            max_corr=("same_direction_correlation_max_corr", "max"),
            avg_active_same_direction=("same_direction_correlation_active_count", "mean"),
            avg_loss_streak=("loss_streak", "mean"),
        )
        .sort_values(["actual_margin_amount", "entries"], ascending=[False, False])
        .reset_index(drop=True)
    )

    by_day = (
        entries.groupby("date", as_index=False)
        .agg(
            entries=("entry_index", "count"),
            selected_volume=("selected_volume", "sum"),
            actual_risk_amount=("actual_risk_amount", "sum"),
            actual_margin_amount=("actual_margin_amount", "sum"),
            max_corr=("same_direction_correlation_max_corr", "max"),
            avg_corr_weight=("same_direction_correlation_gate_weight", "mean"),
            portfolio_drawdown_pct=("portfolio_drawdown_pct", "max"),
        )
        .sort_values("actual_margin_amount", ascending=False)
        .reset_index(drop=True)
    )
    return by_product, by_day


def _build_report(
    window: dict[str, Any],
    daily_window: pd.DataFrame,
    product_pnl: pd.DataFrame,
    entry_product: pd.DataFrame,
    entry_day: pd.DataFrame,
    top_loss_days: pd.DataFrame,
) -> str:
    peak_date = pd.Timestamp(window["peak_date"]).date().isoformat()
    trough_date = pd.Timestamp(window["trough_date"]).date().isoformat()
    recovery_date = pd.Timestamp(window["recovery_date"]).date().isoformat() if pd.notna(window["recovery_date"]) else "-"
    net_from_next_day = float(daily_window[daily_window["date"] > window["peak_date"]]["net_pnl"].sum())
    lines = [
        "# Stage294 第78-1最大回撤来源归因",
        "",
        "## 最大回撤窗口",
        "",
        f"- 高点日期：`{peak_date}`，高点权益：`{window['peak_balance']:,.0f}`",
        f"- 低点日期：`{trough_date}`，低点权益：`{window['trough_balance']:,.0f}`",
        f"- 最大回撤：`{window['max_dd_percent']:.4f}%`，金额：`{window['max_drawdown']:,.0f}`",
        f"- 恢复高点日期：`{recovery_date}`",
        f"- 高点后至低点净亏损：`{net_from_next_day:,.0f}`",
        f"- 窗口内滑点：`{daily_window['slippage'].sum():,.0f}`，交易次数：`{int(daily_window['trade_count'].sum())}`",
        "",
        "## 日度亏损结构",
        "",
        daily_window[
            ["date", "balance", "net_pnl", "holding_pnl", "trading_pnl", "slippage", "ddpercent"]
        ].describe(include="all").to_markdown(),
        "",
        "## 最大单日亏损",
        "",
        top_loss_days.to_markdown(index=False),
        "",
        "## 品种损益归因",
        "",
        product_pnl.head(15).to_markdown(index=False),
        "",
        "## 回撤期新增开仓归因：按品种方向",
        "",
        entry_product.head(20).to_markdown(index=False),
        "",
        "## 回撤期新增开仓归因：按日期",
        "",
        entry_day.head(20).to_markdown(index=False),
        "",
        "## 阶段判断",
        "",
        "- 回撤主要来自持仓期间的价格不利运动，而不是手续费/滑点或频繁交易成本。",
        "- 下一步不应继续单纯压总资金上限；要检查回撤期入场是否存在同向相关、拥挤、保证金压力、连续亏损后继续开仓等前置信号。",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    daily_df = pd.read_csv(DAILY_PATH, parse_dates=["date"])
    position_df = pd.read_csv(POSITION_CHANGES_PATH, parse_dates=["date"])
    entry_df = pd.read_csv(ENTRY_DIAGNOSTICS_PATH, parse_dates=["date"])
    window = _max_drawdown_window(daily_df)
    start = pd.Timestamp(window["peak_date"])
    end = pd.Timestamp(window["trough_date"])
    daily_window = daily_df[(daily_df["date"] >= start) & (daily_df["date"] <= end)].copy()
    product_pnl = _summarize_product_pnl(position_df, start, end)
    entry_product, entry_day = _summarize_entries(entry_df, start, end)
    top_loss_days = daily_window.sort_values("net_pnl").head(20)[
        ["date", "balance", "net_pnl", "holding_pnl", "trading_pnl", "slippage", "ddpercent"]
    ].copy()

    paths = {
        "daily_window": OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_window_{MODEL_TAG}.csv",
        "product_pnl": OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_pnl_{MODEL_TAG}.csv",
        "entry_product": OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_product_{MODEL_TAG}.csv",
        "entry_day": OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_day_{MODEL_TAG}.csv",
        "top_loss_days": OUTPUT_DIR / f"{OUTPUT_PREFIX}_top_loss_days_{MODEL_TAG}.csv",
        "report": OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md",
        "decision": OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json",
    }
    daily_window.to_csv(paths["daily_window"], index=False, encoding="utf-8-sig")
    product_pnl.to_csv(paths["product_pnl"], index=False, encoding="utf-8-sig")
    entry_product.to_csv(paths["entry_product"], index=False, encoding="utf-8-sig")
    entry_day.to_csv(paths["entry_day"], index=False, encoding="utf-8-sig")
    top_loss_days.to_csv(paths["top_loss_days"], index=False, encoding="utf-8-sig")
    paths["report"].write_text(
        _build_report(window, daily_window, product_pnl, entry_product, entry_day, top_loss_days),
        encoding="utf-8",
    )
    decision = {
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "window": {
            key: (pd.Timestamp(value).isoformat() if isinstance(value, pd.Timestamp) else value)
            for key, value in window.items()
        },
        "top_loss_products": product_pnl.head(10).to_dict("records"),
        "top_entry_products": entry_product.head(10).to_dict("records"),
        "paths": {key: str(path.resolve()) for key, path in paths.items()},
    }
    paths["decision"].write_text(json.dumps(decision, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(decision, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
