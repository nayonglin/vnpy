from __future__ import annotations

import json
from typing import Any

import numpy as np
import pandas as pd

from analyze_qmt_roll_stage324_true_combo_capital_margin import _to_builtin, _to_markdown_table
from analyze_qmt_roll_stage328_c3_single_path_loss_attribution import (
    _drawdown_window,
    _product_from_vt_symbol,
    _run_c3,
)
from analyze_qmt_roll_stage345_cross_sectional_momentum_satellite import SATELLITE_DAILY_PATH
from run_qmt_alignment_backtest import OUTPUT_DIR


MODEL_TAG = "stage347_xsmom_c3_position_temperature_v1"
OUTPUT_PREFIX = "qmt_roll_stage347_xsmom_c3_position_temperature"
LINE_ID = "futures_trend_drawdown30_preserve_return"

SPEC_NAME = "mom_12m_skip1m"

DETAIL_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_detail_{MODEL_TAG}.csv"
SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DD_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_drawdown_summary_{MODEL_TAG}.csv"
DD_PRODUCT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_drawdown_product_{MODEL_TAG}.csv"
DAILY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


def _direction_from_position(start_pos: float, end_pos: float) -> str:
    pos = start_pos if abs(start_pos) > 1e-9 else end_pos
    if pos > 0:
        return "long"
    if pos < 0:
        return "short"
    return "flat"


def _split_products(value: Any) -> set[str]:
    if pd.isna(value):
        return set()
    text = str(value).strip()
    if not text:
        return set()
    return {item.strip() for item in text.split(",") if item.strip()}


def _load_temperature() -> pd.DataFrame:
    frame = pd.read_csv(SATELLITE_DAILY_PATH, encoding="utf-8-sig")
    frame["date"] = pd.to_datetime(frame["date"]).dt.normalize()
    frame = frame[frame["spec"].eq(SPEC_NAME)].copy()
    frame["xsmom_long_set"] = frame["long_products"].map(_split_products)
    frame["xsmom_short_set"] = frame["short_products"].map(_split_products)
    return frame[["date", "xsmom_long_set", "xsmom_short_set", "active_products"]]


def _temperature_state(row: pd.Series) -> str:
    product = str(row["product_vt_symbol"])
    direction = str(row["direction"])
    long_set = row.get("xsmom_long_set")
    short_set = row.get("xsmom_short_set")
    if not isinstance(long_set, set) or not isinstance(short_set, set):
        return "unavailable"
    if direction == "long":
        if product in short_set:
            return "adverse"
        if product in long_set:
            return "support"
    elif direction == "short":
        if product in long_set:
            return "adverse"
        if product in short_set:
            return "support"
    return "neutral"


def _prep_positions(positions: pd.DataFrame, temperature: pd.DataFrame) -> pd.DataFrame:
    frame = positions.copy()
    frame["date"] = pd.to_datetime(frame["date"]).dt.normalize()
    frame["product_vt_symbol"] = frame["vt_symbol"].map(_product_from_vt_symbol)
    numeric_cols = [
        "start_pos",
        "end_pos",
        "pos_change",
        "net_pnl",
        "holding_pnl",
        "trading_pnl",
        "slippage",
        "commission",
        "trade_count",
    ]
    for column in numeric_cols:
        frame[column] = pd.to_numeric(frame.get(column, 0.0), errors="coerce").fillna(0.0)
    frame["active_or_traded"] = (
        frame["start_pos"].abs() + frame["end_pos"].abs() + frame["pos_change"].abs() + frame["trade_count"].abs()
    ) > 1e-9
    frame = frame[frame["active_or_traded"]].copy()
    frame["direction"] = frame.apply(
        lambda row: _direction_from_position(float(row["start_pos"]), float(row["end_pos"])),
        axis=1,
    )
    frame = frame[frame["direction"].ne("flat")].copy()
    merged = frame.merge(temperature, on="date", how="left")
    merged["xsmom_state"] = merged.apply(_temperature_state, axis=1)
    merged["position_abs"] = np.where(
        merged["start_pos"].abs() > 1e-9,
        merged["start_pos"].abs(),
        merged["end_pos"].abs(),
    )
    return merged.sort_values(["date", "vt_symbol"]).reset_index(drop=True)


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
                "commission": float(part["commission"].sum()),
                "slippage": float(part["slippage"].sum()),
                "trade_count": int(part["trade_count"].sum()),
                "row_count": int(len(part)),
                "active_days": int(part["date"].nunique()),
                "avg_position_abs": float(part["position_abs"].mean()),
                "min_daily_net_pnl": float(part.groupby("date")["net_pnl"].sum().min()),
                "max_daily_net_pnl": float(part.groupby("date")["net_pnl"].sum().max()),
            }
        )
        rows.append(row)
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values("net_pnl").reset_index(drop=True)


def _daily_summary(frame: pd.DataFrame) -> pd.DataFrame:
    daily = (
        frame.groupby(["date", "xsmom_state"], as_index=False)
        .agg(
            net_pnl=("net_pnl", "sum"),
            holding_pnl=("holding_pnl", "sum"),
            trading_pnl=("trading_pnl", "sum"),
            trade_count=("trade_count", "sum"),
            active_contracts=("vt_symbol", "nunique"),
        )
        .sort_values(["date", "xsmom_state"])
        .reset_index(drop=True)
    )
    return daily


def _loss_share(summary: pd.DataFrame, state: str) -> float:
    if summary.empty or "xsmom_state" not in summary.columns:
        return 0.0
    loss = summary[summary["net_pnl"] < 0].copy()
    total_loss = abs(float(loss["net_pnl"].sum())) if not loss.empty else 0.0
    state_loss = abs(float(loss[loss["xsmom_state"].eq(state)]["net_pnl"].sum())) if not loss.empty else 0.0
    return state_loss / total_loss * 100.0 if total_loss > 0 else 0.0


def _build_report(
    drawdown: dict[str, Any],
    summary: pd.DataFrame,
    dd_summary: pd.DataFrame,
    dd_product: pd.DataFrame,
    worst_daily: pd.DataFrame,
    decision: dict[str, Any],
) -> str:
    return "\n".join(
        [
            "# Stage047 横截面动量温度与 C3 持仓路径诊断",
            "",
            "## 定位",
            "",
            "- 本阶段不修改 C3 交易规则，只检查 Stage045 横截面动量篮子能否解释 C3 持仓亏损。",
            "- 判定口径：C3 做多但该品种位于横截面动量空头篮子，或 C3 做空但该品种位于横截面动量多头篮子，标为 `adverse`。",
            "- 若 `adverse` 在深回撤中集中贡献亏损，且全样本不是稳定盈利状态，后续才考虑做低自由度温度覆盖层。",
            "",
            "## C3 最大回撤窗口",
            "",
            f"- 高点日期：`{pd.Timestamp(drawdown['peak_date']).date().isoformat()}`。",
            f"- 低点日期：`{pd.Timestamp(drawdown['trough_date']).date().isoformat()}`。",
            f"- 最大回撤：`{drawdown['max_dd_percent']:.4f}%`。",
            "",
            "## 全样本温度分桶",
            "",
            _to_markdown_table(
                summary,
                [
                    "xsmom_state",
                    "net_pnl",
                    "holding_pnl",
                    "trade_count",
                    "row_count",
                    "active_days",
                    "min_daily_net_pnl",
                    "max_daily_net_pnl",
                ],
                max_rows=20,
            ),
            "",
            "## 深回撤窗口温度分桶",
            "",
            _to_markdown_table(
                dd_summary,
                [
                    "xsmom_state",
                    "net_pnl",
                    "holding_pnl",
                    "trade_count",
                    "row_count",
                    "active_days",
                    "min_daily_net_pnl",
                    "max_daily_net_pnl",
                ],
                max_rows=20,
            ),
            "",
            "## 深回撤窗口品种方向",
            "",
            _to_markdown_table(
                dd_product,
                [
                    "product_vt_symbol",
                    "direction",
                    "xsmom_state",
                    "net_pnl",
                    "holding_pnl",
                    "trade_count",
                    "row_count",
                    "active_days",
                ],
                max_rows=40,
            ),
            "",
            "## 最差温度日",
            "",
            _to_markdown_table(
                worst_daily,
                [
                    "date",
                    "xsmom_state",
                    "net_pnl",
                    "holding_pnl",
                    "trade_count",
                    "active_contracts",
                ],
                max_rows=30,
            ),
            "",
            "## 判断",
            "",
            f"- 决策标签：`{decision['decision']}`。",
            f"- 深回撤窗口 `adverse` 亏损占比：`{decision['drawdown_adverse_loss_share_pct']:.4f}%`。",
            f"- 全样本 `adverse` 净损益：`{decision['full_adverse_net_pnl']:,.2f}`。",
            "",
            "## 反思",
            "",
            "- 是否过拟合：否。本阶段只使用上一交易日可见的月度横截面动量篮子做归因，不调阈值、不按品种黑名单修补。",
            "- 是否还有价值继续：只有当逆风桶能解释深回撤且不会砍掉全样本主要盈利时，才值得进入下一阶段；否则应停止这条温度覆盖层方向。",
        ]
    )


def main() -> None:
    daily, positions, _trades, _candidates, _risks, statistics = _run_c3()
    drawdown = _drawdown_window(daily)
    peak_date = pd.Timestamp(drawdown["peak_date"]).normalize()
    trough_date = pd.Timestamp(drawdown["trough_date"]).normalize()

    temperature = _load_temperature()
    detail = _prep_positions(positions, temperature)
    dd_detail = detail[(detail["date"] > peak_date) & (detail["date"] <= trough_date)].copy()

    summary = _summarize(detail, ["xsmom_state"])
    dd_summary = _summarize(dd_detail, ["xsmom_state"])
    dd_product = _summarize(dd_detail, ["product_vt_symbol", "direction", "xsmom_state"])
    daily_temp = _daily_summary(detail)
    worst_daily = daily_temp.sort_values("net_pnl").head(30).reset_index(drop=True)

    full_adverse = float(summary[summary["xsmom_state"].eq("adverse")]["net_pnl"].sum()) if not summary.empty else 0.0
    dd_adverse_share = _loss_share(dd_summary, "adverse")
    if dd_adverse_share >= 50.0 and full_adverse <= 0.0:
        label = "xsmom_temperature_candidate_for_coarse_overlay"
    elif dd_adverse_share >= 50.0:
        label = "xsmom_temperature_mixed_signal_diagnostic_only"
    else:
        label = "xsmom_temperature_not_core_drawdown_explanation"

    decision = {
        "decision": label,
        "spec_name": SPEC_NAME,
        "line_id": LINE_ID,
        "drawdown_adverse_loss_share_pct": dd_adverse_share,
        "full_adverse_net_pnl": full_adverse,
        "drawdown": {key: _to_builtin(value) for key, value in drawdown.items() if key != "curve"},
        "statistics": _to_builtin(statistics),
    }

    DETAIL_PATH.parent.mkdir(parents=True, exist_ok=True)
    detail.to_csv(DETAIL_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    dd_summary.to_csv(DD_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    dd_product.to_csv(DD_PRODUCT_PATH, index=False, encoding="utf-8-sig")
    daily_temp.to_csv(DAILY_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_to_builtin(decision), ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    REPORT_PATH.write_text(
        _build_report(drawdown, summary, dd_summary, dd_product, worst_daily, decision),
        encoding="utf-8",
    )

    print(json.dumps(_to_builtin(decision), ensure_ascii=False, indent=2, default=str))
    print(f"[stage347] report={REPORT_PATH}")


if __name__ == "__main__":
    main()
