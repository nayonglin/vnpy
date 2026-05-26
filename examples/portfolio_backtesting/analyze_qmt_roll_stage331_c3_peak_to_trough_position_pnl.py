from __future__ import annotations

import json
from typing import Any

import numpy as np
import pandas as pd

from analyze_qmt_roll_stage324_true_combo_capital_margin import _to_builtin, _to_markdown_table
from analyze_qmt_roll_stage328_c3_single_path_loss_attribution import (
    MODEL_TAG as STAGE328_MODEL_TAG,
    _drawdown_window,
    _product_from_vt_symbol,
    _run_c3,
)
from qmt_roll_official_stage78_config import OFFICIAL_STAGE78_ROLE, OFFICIAL_STAGE78_VERSION
from run_qmt_alignment_backtest import OUTPUT_DIR


MODEL_TAG = "stage331_c3_peak_to_trough_position_pnl_v1"
OUTPUT_PREFIX = "qmt_roll_stage331_c3_peak_to_trough_position_pnl"


def _direction_from_pos(start_pos: float, end_pos: float) -> str:
    pos = start_pos if abs(start_pos) > 1e-9 else end_pos
    if pos > 0:
        return "long"
    if pos < 0:
        return "short"
    return "flat"


def _prep_positions(positions: pd.DataFrame, peak_date: pd.Timestamp, trough_date: pd.Timestamp) -> pd.DataFrame:
    frame = positions.copy()
    frame["date"] = pd.to_datetime(frame["date"]).dt.normalize()
    frame["product_vt_symbol"] = frame["vt_symbol"].map(_product_from_vt_symbol)
    for column in ["start_pos", "end_pos", "pos_change", "net_pnl", "holding_pnl", "trading_pnl", "slippage", "trade_count"]:
        frame[column] = pd.to_numeric(frame.get(column, 0.0), errors="coerce").fillna(0.0)

    peak_positions = set(
        frame[(frame["date"].eq(peak_date)) & (frame["end_pos"].abs() > 1e-9)]["vt_symbol"].astype(str).tolist()
    )
    window = frame[(frame["date"] > peak_date) & (frame["date"] <= trough_date)].copy()
    window["direction"] = window.apply(lambda row: _direction_from_pos(float(row["start_pos"]), float(row["end_pos"])), axis=1)
    window["existed_at_peak"] = window["vt_symbol"].astype(str).isin(peak_positions).astype(int)
    window["active_or_traded"] = (
        window["start_pos"].abs() + window["end_pos"].abs() + window["pos_change"].abs() + window["trade_count"].abs()
    ) > 1e-9
    window = window[window["active_or_traded"]].copy()
    window["source_bucket"] = np.where(window["existed_at_peak"].eq(1), "peak_existing_position", "opened_or_traded_after_peak")
    return window


def _summarize(frame: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for key, part in frame.groupby(group_cols, dropna=False):
        if not isinstance(key, tuple):
            key = (key,)
        row = {col: value for col, value in zip(group_cols, key)}
        row.update(
            {
                "net_pnl": float(part["net_pnl"].sum()),
                "holding_pnl": float(part["holding_pnl"].sum()),
                "trading_pnl": float(part["trading_pnl"].sum()),
                "slippage": float(part["slippage"].sum()),
                "trade_count": int(part["trade_count"].sum()),
                "active_days": int(part["date"].nunique()),
                "max_abs_end_pos": float(part["end_pos"].abs().max()),
            }
        )
        rows.append(row)
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values("net_pnl").reset_index(drop=True)


def _build_report(
    drawdown: dict[str, Any],
    source_summary: pd.DataFrame,
    product_direction: pd.DataFrame,
    daily_summary: pd.DataFrame,
    peak_positions: pd.DataFrame,
    decision: dict[str, Any],
) -> str:
    return "\n".join(
        [
            "# Stage031 C3峰值到谷值持仓损益归因",
            "",
            "## 定位",
            "",
            "- 本阶段重新跑 C3，按日度持仓损益拆解最大回撤窗口。",
            "- 目标是区分：亏损来自高点日已有仓位，还是回撤过程中新增/交易仓位。",
            "",
            "## 最大回撤窗口",
            "",
            f"- 高点日期：`{pd.Timestamp(drawdown['peak_date']).date().isoformat()}`，高点权益：`{drawdown['peak_balance']:,.0f}`",
            f"- 低点日期：`{pd.Timestamp(drawdown['trough_date']).date().isoformat()}`，低点权益：`{drawdown['trough_balance']:,.0f}`",
            f"- 最大回撤：`{drawdown['max_dd_percent']:.4f}%`",
            "",
            "## 来源分桶",
            "",
            _to_markdown_table(source_summary, source_summary.columns.tolist(), max_rows=20),
            "",
            "## 品种方向损益",
            "",
            _to_markdown_table(product_direction, product_direction.columns.tolist(), max_rows=30),
            "",
            "## 最大亏损日",
            "",
            _to_markdown_table(daily_summary, daily_summary.columns.tolist(), max_rows=20),
            "",
            "## 高点日持仓快照",
            "",
            _to_markdown_table(peak_positions, peak_positions.columns.tolist(), max_rows=30),
            "",
            "## 判断",
            "",
            f"- 诊断标签：`{decision['decision']}`。",
            f"- 高点已有仓位贡献亏损占比：`{decision['peak_existing_loss_share_pct']:.4f}%`。",
            f"- 回撤后新增/交易仓位贡献亏损占比：`{decision['after_peak_loss_share_pct']:.4f}%`。",
            "",
            "## 反思",
            "",
            "- 是否过拟合：本阶段是峰值到谷值归因，不形成交易阈值，因此不是过拟合。",
            "- 是否还有价值继续：若亏损主要来自高点已有仓位，继续做新增开仓过滤价值有限；应转向组合层已持仓降风险或接受该收益级别下的自然回撤。",
        ]
    )


def main() -> None:
    daily, positions, _trades, _candidates, _risks, statistics = _run_c3()
    drawdown = _drawdown_window(daily)
    peak_date = pd.Timestamp(drawdown["peak_date"]).normalize()
    trough_date = pd.Timestamp(drawdown["trough_date"]).normalize()

    window = _prep_positions(positions, peak_date, trough_date)
    source_summary = _summarize(window, ["source_bucket"])
    product_direction = _summarize(window, ["product_vt_symbol", "direction", "source_bucket"]).head(60)
    daily_summary = (
        window.groupby("date", as_index=False)
        .agg(
            net_pnl=("net_pnl", "sum"),
            holding_pnl=("holding_pnl", "sum"),
            trading_pnl=("trading_pnl", "sum"),
            slippage=("slippage", "sum"),
            trade_count=("trade_count", "sum"),
        )
        .sort_values("net_pnl")
        .reset_index(drop=True)
    )
    peak_positions = positions.copy()
    peak_positions["date"] = pd.to_datetime(peak_positions["date"]).dt.normalize()
    peak_positions = peak_positions[(peak_positions["date"].eq(peak_date)) & (pd.to_numeric(peak_positions["end_pos"], errors="coerce").abs() > 1e-9)].copy()
    peak_positions["product_vt_symbol"] = peak_positions["vt_symbol"].map(_product_from_vt_symbol)
    peak_positions = peak_positions[["vt_symbol", "product_vt_symbol", "end_pos", "close_price", "net_pnl", "holding_pnl", "trade_count"]].sort_values(
        "end_pos", key=lambda s: s.abs(), ascending=False
    )

    loss_summary = source_summary[source_summary["net_pnl"] < 0].copy()
    total_loss = abs(float(loss_summary["net_pnl"].sum())) if not loss_summary.empty else 0.0
    peak_loss = abs(
        float(source_summary[source_summary["source_bucket"].eq("peak_existing_position")]["net_pnl"].clip(upper=0.0).sum())
    )
    after_peak_loss = abs(
        float(source_summary[source_summary["source_bucket"].eq("opened_or_traded_after_peak")]["net_pnl"].clip(upper=0.0).sum())
    )
    peak_share = peak_loss / total_loss * 100.0 if total_loss > 0 else 0.0
    after_share = after_peak_loss / total_loss * 100.0 if total_loss > 0 else 0.0
    if peak_share >= 60.0:
        label = "loss_dominated_by_peak_existing_positions"
    elif after_share >= 60.0:
        label = "loss_dominated_by_after_peak_entries"
    else:
        label = "mixed_position_loss_source"
    decision = {
        "decision": label,
        "peak_existing_loss_share_pct": peak_share,
        "after_peak_loss_share_pct": after_share,
        "drawdown": {key: _to_builtin(value) for key, value in drawdown.items() if key != "curve"},
        "statistics": _to_builtin(statistics),
        "stage328_source": STAGE328_MODEL_TAG,
        "official_version": OFFICIAL_STAGE78_VERSION,
        "official_role": OFFICIAL_STAGE78_ROLE,
    }

    detail_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_detail_{MODEL_TAG}.csv"
    source_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_source_summary_{MODEL_TAG}.csv"
    product_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_direction_{MODEL_TAG}.csv"
    daily_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_summary_{MODEL_TAG}.csv"
    peak_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_peak_positions_{MODEL_TAG}.csv"
    decision_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
    report_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

    window.to_csv(detail_path, index=False, encoding="utf-8-sig")
    source_summary.to_csv(source_path, index=False, encoding="utf-8-sig")
    product_direction.to_csv(product_path, index=False, encoding="utf-8-sig")
    daily_summary.to_csv(daily_path, index=False, encoding="utf-8-sig")
    peak_positions.to_csv(peak_path, index=False, encoding="utf-8-sig")
    decision_path.write_text(json.dumps(_to_builtin(decision), ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    report_path.write_text(_build_report(drawdown, source_summary, product_direction, daily_summary, peak_positions, decision), encoding="utf-8")

    print(json.dumps(_to_builtin(decision), ensure_ascii=False, indent=2, default=str))
    print(f"[stage331] report: {report_path}")


if __name__ == "__main__":
    main()
