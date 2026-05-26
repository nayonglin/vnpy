from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from analyze_qmt_roll_stage324_true_combo_capital_margin import (
    TOTAL_CAPITAL,
    _path_metrics,
    _to_builtin,
    _to_markdown_table,
)
from analyze_qmt_roll_stage328_c3_single_path_loss_attribution import (
    MODEL_TAG as STAGE328_MODEL_TAG,
    _load_bars_for_round_trips,
)
from qmt_roll_official_stage78_config import OFFICIAL_STAGE78_ROLE, OFFICIAL_STAGE78_VERSION
from qmt_universe import END_DT, START_DT
from run_qmt_alignment_backtest import OUTPUT_DIR


MODEL_TAG = "stage329_c3_early_adverse_path_guard_screen_v2"
OUTPUT_PREFIX = "qmt_roll_stage329_c3_early_adverse_path_guard_screen"
LINE_ID = "futures_trend_drawdown30_preserve_return"
EPSILON = 1e-6

ROUND_TRIPS_PATH = (
    OUTPUT_DIR
    / "qmt_roll_stage328_c3_single_path_loss_attribution_round_trips_stage328_c3_single_path_loss_attribution_v1.csv"
)


@dataclass(frozen=True)
class Candidate:
    name: str
    label: str
    max_days: int
    adverse_atr: float
    progress_atr: float
    enabled: bool = True


@dataclass(frozen=True)
class Window:
    name: str
    label: str
    start: datetime
    end: datetime


CANDIDATES: tuple[Candidate, ...] = (
    Candidate(
        name="A_c3_actual_path",
        label="A：C3实际路径",
        max_days=0,
        adverse_atr=0.0,
        progress_atr=0.0,
        enabled=False,
    ),
    Candidate(
        name="C_early_adverse_2atr_5d",
        label="C：前5日2ATR不利且无1ATR进展则提前退出",
        max_days=5,
        adverse_atr=2.0,
        progress_atr=1.0,
        enabled=True,
    ),
)

WINDOWS: tuple[Window, ...] = (
    Window("start_2020", "2020起点至今", START_DT, END_DT),
    Window("start_2021", "2021起点至今", datetime(2021, 1, 1), END_DT),
    Window("start_2022", "2022起点至今", datetime(2022, 1, 1), END_DT),
    Window("start_2023", "2023起点至今", datetime(2023, 1, 1), END_DT),
    Window("start_2024", "2024起点至今", datetime(2024, 1, 1), END_DT),
    Window("start_2025", "2025起点至今", datetime(2025, 1, 1), END_DT),
    Window("ytd_2026", "2026年初至今", datetime(2026, 1, 1), END_DT),
    Window("weak_2021_full", "2021弱窗口全年", datetime(2021, 1, 1), datetime(2021, 12, 31)),
    Window("phase_2024_2025", "2024-2025独立启动", datetime(2024, 1, 1), datetime(2025, 12, 31)),
)


def _load_round_trips() -> pd.DataFrame:
    if not ROUND_TRIPS_PATH.exists():
        raise FileNotFoundError(
            f"Stage328 round trips not found: {ROUND_TRIPS_PATH}. Run analyze_qmt_roll_stage328 first."
        )
    frame = pd.read_csv(ROUND_TRIPS_PATH)
    for column in ["entry_date", "exit_date", "entry_datetime", "exit_datetime"]:
        if column in frame.columns:
            frame[column] = pd.to_datetime(frame[column], errors="coerce").dt.tz_localize(None)
    for column in [
        "entry_price",
        "exit_price",
        "volume",
        "size",
        "gross_pnl",
        "gross_return_pct",
        "atr20_pct",
        "entry_close",
    ]:
        frame[column] = pd.to_numeric(frame.get(column, np.nan), errors="coerce")
    frame["direction"] = frame["direction"].astype(str)
    return frame.sort_values(["entry_date", "leg_id"]).reset_index(drop=True)


def _sign(direction: str) -> float:
    return 1.0 if str(direction) == "long" else -1.0


def _pnl(direction: str, entry_price: float, exit_price: float, volume: float, size: float) -> float:
    return (exit_price - entry_price) * _sign(direction) * volume * size


def _return_pct(direction: str, entry_price: float, exit_price: float) -> float:
    if entry_price <= 0:
        return math.nan
    return (exit_price / entry_price - 1.0) * _sign(direction) * 100.0


def _candidate_exit(row: dict[str, Any], bars: pd.DataFrame, candidate: Candidate) -> dict[str, Any]:
    entry_date = pd.Timestamp(row["entry_date"]).normalize()
    actual_exit_date = pd.Timestamp(row["exit_date"]).normalize()
    entry_price = float(row["entry_price"])
    actual_exit_price = float(row["exit_price"])
    direction = str(row["direction"])
    volume = float(row["volume"])
    size = float(row["size"])

    actual = {
        "candidate_exit_date": actual_exit_date,
        "candidate_exit_price": actual_exit_price,
        "candidate_gross_pnl": _pnl(direction, entry_price, actual_exit_price, volume, size),
        "candidate_return_pct": _return_pct(direction, entry_price, actual_exit_price),
        "candidate_exit_reason": str(row.get("exit_reason", "")),
        "triggered": 0,
        "trigger_day_index": 0,
        "max_progress_atr_before_trigger": 0.0,
        "max_adverse_atr_before_trigger": 0.0,
    }
    if not candidate.enabled:
        return actual

    atr_pct = float(row.get("atr20_pct", math.nan))
    if not math.isfinite(atr_pct) or atr_pct <= 0 or entry_price <= 0:
        return actual

    atr_price = entry_price * atr_pct / 100.0
    if atr_price <= 0:
        return actual

    path = bars[(bars["date"] > entry_date) & (bars["date"] <= actual_exit_date)].copy()
    if path.empty:
        return actual
    path = path.sort_values("date").head(candidate.max_days)
    if path.empty:
        return actual

    max_progress = 0.0
    max_adverse = 0.0
    sign = _sign(direction)
    for index, bar in enumerate(path.to_dict("records"), start=1):
        close_price = float(bar["close"])
        move_atr = (close_price - entry_price) * sign / atr_price
        max_progress = max(max_progress, move_atr)
        max_adverse = min(max_adverse, move_atr)
        adverse_hit = move_atr <= -candidate.adverse_atr
        no_progress = max_progress < candidate.progress_atr
        if adverse_hit and no_progress:
            exit_date = pd.Timestamp(bar["date"]).normalize()
            if exit_date >= actual_exit_date:
                return actual
            exit_price = close_price
            return {
                "candidate_exit_date": exit_date,
                "candidate_exit_price": exit_price,
                "candidate_gross_pnl": _pnl(direction, entry_price, exit_price, volume, size),
                "candidate_return_pct": _return_pct(direction, entry_price, exit_price),
                "candidate_exit_reason": "early_adverse_2atr_guard",
                "triggered": 1,
                "trigger_day_index": int(index),
                "max_progress_atr_before_trigger": float(max_progress),
                "max_adverse_atr_before_trigger": float(max_adverse),
            }
    return {
        **actual,
        "max_progress_atr_before_trigger": float(max_progress),
        "max_adverse_atr_before_trigger": float(max_adverse),
    }


def _simulate_candidate(round_trips: pd.DataFrame, bars_by_symbol: dict[str, pd.DataFrame], candidate: Candidate) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for row in round_trips.to_dict("records"):
        vt_symbol = str(row["vt_symbol"])
        bars = bars_by_symbol.get(vt_symbol)
        if bars is None or bars.empty:
            result = _candidate_exit(row, pd.DataFrame(columns=["date", "close"]), CANDIDATES[0])
        else:
            result = _candidate_exit(row, bars, candidate)
        actual_pnl = float(row["gross_pnl"])
        rows.append(
            {
                "candidate_name": candidate.name,
                "candidate_label": candidate.label,
                "leg_id": int(row["leg_id"]),
                "vt_symbol": vt_symbol,
                "product_vt_symbol": str(row["product_vt_symbol"]),
                "direction": str(row["direction"]),
                "entry_date": pd.Timestamp(row["entry_date"]).normalize(),
                "actual_exit_date": pd.Timestamp(row["exit_date"]).normalize(),
                "candidate_exit_date": result["candidate_exit_date"],
                "entry_price": float(row["entry_price"]),
                "actual_exit_price": float(row["exit_price"]),
                "candidate_exit_price": float(result["candidate_exit_price"]),
                "volume": float(row["volume"]),
                "size": float(row["size"]),
                "actual_gross_pnl": actual_pnl,
                "candidate_gross_pnl": float(result["candidate_gross_pnl"]),
                "delta_gross_pnl": float(result["candidate_gross_pnl"]) - actual_pnl,
                "actual_return_pct": float(row["gross_return_pct"]),
                "candidate_return_pct": float(result["candidate_return_pct"]),
                "exit_reason": str(row.get("exit_reason", "")),
                "candidate_exit_reason": str(result["candidate_exit_reason"]),
                "triggered": int(result["triggered"]),
                "trigger_day_index": int(result["trigger_day_index"]),
                "max_progress_atr_before_trigger": float(result["max_progress_atr_before_trigger"]),
                "max_adverse_atr_before_trigger": float(result["max_adverse_atr_before_trigger"]),
                "entry_year": int(pd.Timestamp(row["entry_date"]).year),
                "overlaps_max_dd_window": int(row.get("overlaps_max_dd_window", 0) or 0),
            }
        )
    return pd.DataFrame(rows)


def _date_universe(bars_by_symbol: dict[str, pd.DataFrame]) -> pd.DatetimeIndex:
    dates: set[pd.Timestamp] = set()
    for bars in bars_by_symbol.values():
        if not bars.empty:
            dates.update(pd.to_datetime(bars["date"]).dt.normalize().tolist())
    clean = sorted(date for date in dates if pd.Timestamp(START_DT) <= date <= pd.Timestamp(END_DT))
    return pd.DatetimeIndex(clean)


def _build_marked_curve(legs: pd.DataFrame, bars_by_symbol: dict[str, pd.DataFrame]) -> pd.DataFrame:
    dates = _date_universe(bars_by_symbol)
    if dates.empty:
        return pd.DataFrame(columns=["date", "balance"])
    balances = pd.Series(float(TOTAL_CAPITAL), index=dates, dtype="float64")
    close_cache: dict[str, pd.Series] = {}
    for vt_symbol, bars in bars_by_symbol.items():
        close_cache[vt_symbol] = (
            bars.drop_duplicates("date")
            .assign(date=lambda df: pd.to_datetime(df["date"]).dt.normalize())
            .set_index("date")["close"]
            .astype(float)
            .reindex(dates)
            .ffill()
        )

    for row in legs.to_dict("records"):
        vt_symbol = str(row["vt_symbol"])
        closes = close_cache.get(vt_symbol)
        if closes is None:
            continue
        entry_date = pd.Timestamp(row["entry_date"]).normalize()
        exit_date = pd.Timestamp(row["candidate_exit_date"]).normalize()
        entry_price = float(row["entry_price"])
        exit_price = float(row["candidate_exit_price"])
        volume = float(row["volume"])
        size = float(row["size"])
        sign = _sign(str(row["direction"]))
        realized = float(row["candidate_gross_pnl"])

        active_mask = (dates >= entry_date) & (dates < exit_date)
        if active_mask.any():
            marked = (closes.loc[active_mask] - entry_price) * sign * volume * size
            balances.loc[active_mask] += marked.fillna(0.0)
        realized_mask = dates >= exit_date
        if realized_mask.any():
            balances.loc[realized_mask] += realized

    return pd.DataFrame({"date": balances.index, "balance": balances.values})


def _metrics_for_windows(curve: pd.DataFrame, candidate: Candidate) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for window in WINDOWS:
        frame = curve[(curve["date"] >= pd.Timestamp(window.start)) & (curve["date"] <= pd.Timestamp(window.end))].copy()
        if frame.empty:
            rows.append(
                {
                    "candidate_name": candidate.name,
                    "candidate_label": candidate.label,
                    "window_name": window.name,
                    "window_label": window.label,
                    "total_return_pct": 0.0,
                    "max_dd_percent": 0.0,
                    "sharpe_ratio": 0.0,
                    "end_balance": TOTAL_CAPITAL,
                }
            )
            continue
        base_balance = max(abs(float(frame["balance"].iloc[0])), 1e-9)
        frame["rebased_balance"] = frame["balance"] / base_balance * TOTAL_CAPITAL
        metrics = _path_metrics(frame[["date", "rebased_balance"]].rename(columns={"rebased_balance": "balance"}), TOTAL_CAPITAL)
        rows.append(
            {
                "candidate_name": candidate.name,
                "candidate_label": candidate.label,
                "window_name": window.name,
                "window_label": window.label,
                **metrics,
            }
        )
    return rows


def _summarize_legs(legs: pd.DataFrame) -> dict[str, Any]:
    triggered = legs[legs["triggered"].eq(1)]
    delta = pd.to_numeric(legs["delta_gross_pnl"], errors="coerce").fillna(0.0)
    by_year = (
        triggered.groupby("entry_year", dropna=False)["delta_gross_pnl"].sum().reset_index()
        if not triggered.empty
        else pd.DataFrame(columns=["entry_year", "delta_gross_pnl"])
    )
    year_win_count = int((by_year["delta_gross_pnl"] > 0).sum()) if not by_year.empty else 0
    total_delta = float(delta.sum())
    if abs(total_delta) < EPSILON:
        total_delta = 0.0
    return {
        "triggered_legs": int(legs["triggered"].sum()),
        "total_delta_gross_pnl": total_delta,
        "positive_delta_legs": int((delta > EPSILON).sum()),
        "negative_delta_legs": int((delta < -EPSILON).sum()),
        "year_win_count": year_win_count,
        "max_dd_overlap_triggered": int(triggered["overlaps_max_dd_window"].sum()) if not triggered.empty else 0,
    }


def _build_report(summary: pd.DataFrame, leg_summary: pd.DataFrame, top_changes: pd.DataFrame, decision: dict[str, Any]) -> str:
    full = summary[summary["window_name"].eq("start_2020")].copy()
    window_table = summary[
        [
            "candidate_name",
            "window_name",
            "total_return_pct",
            "return_retention_vs_a_pct",
            "max_dd_percent",
            "sharpe_ratio",
            "pass_window",
        ]
    ]
    top_cols = [
        "candidate_name",
        "leg_id",
        "product_vt_symbol",
        "vt_symbol",
        "direction",
        "entry_date",
        "actual_exit_date",
        "candidate_exit_date",
        "actual_gross_pnl",
        "candidate_gross_pnl",
        "delta_gross_pnl",
        "exit_reason",
        "candidate_exit_reason",
    ]
    return "\n".join(
        [
            "# Stage029 C3早期不利路径保护筛查",
            "",
            "## 定位",
            "",
            "- 本阶段是 A/C 前置筛查，不直接修改正式策略。",
            "- 候选假设：趋势策略若开仓后很快出现 2ATR 级别不利收盘，且期间没有过 1ATR 顺向进展，说明这笔开仓质量不足，应尽早退出或降风险。",
            "- 这条规则只使用开仓时已知 ATR 和之后已经发生的收盘价，不使用未来平仓结果；但本阶段仍是交易回合反事实，不能直接推广。",
            "- 注意：本阶段曲线是交易腿反事实合成曲线，不等同于真实引擎权益；只有 C 相对 A 有非零触发和改善时，才允许进入真实引擎验证。",
            "",
            "## A/C定义",
            "",
            "- A：C3实际路径。",
            "- C：前5个交易日内，收盘不利移动达到2ATR且此前最大顺向收盘进展不足1ATR，则按当日收盘提前退出。",
            "",
            "## 全周期对比",
            "",
            _to_markdown_table(full, ["candidate_name", "total_return_pct", "return_retention_vs_a_pct", "max_dd_percent", "sharpe_ratio"]),
            "",
            "## 多窗口对比",
            "",
            _to_markdown_table(window_table, window_table.columns.tolist(), max_rows=30),
            "",
            "## 触发统计",
            "",
            _to_markdown_table(leg_summary, leg_summary.columns.tolist(), max_rows=10),
            "",
            "## 变化最大的交易回合",
            "",
            _to_markdown_table(top_changes, top_cols, max_rows=30),
            "",
            "## 判断",
            "",
            f"- 决策标签：`{decision['decision']}`。",
            f"- 原因：{decision['reason']}",
            f"- C触发交易回合：`{decision['c_triggered_legs']}`；C相对A最大回撤改善：`{decision['synthetic_dd_improvement_pp']:.4f}`百分点；C总收益保留：`{decision['c_return_retention_vs_a_pct']:.4f}%`。",
            "- 若本筛查不过，则不进入真实引擎实现，避免为一个看似直觉正确但路径不稳的早停规则增加复杂度。",
            "",
            "## 反思",
            "",
            "- 是否过拟合：当前筛查本身不是过拟合，因为规则在运行前冻结，且使用 ATR 这种通用尺度；但若失败后继续调 `2ATR/5日/1ATR`，就会变成过拟合。",
            "- 是否还有价值继续：取决于 C 是否全周期和多窗口同时改善；若不改善，就停止早期不利路径早停方向。",
        ]
    )


def main() -> None:
    round_trips = _load_round_trips()
    bars_by_symbol = _load_bars_for_round_trips(round_trips)

    leg_frames: list[pd.DataFrame] = []
    metric_rows: list[dict[str, Any]] = []
    leg_summary_rows: list[dict[str, Any]] = []
    curves: list[pd.DataFrame] = []

    for candidate in CANDIDATES:
        legs = _simulate_candidate(round_trips, bars_by_symbol, candidate)
        curve = _build_marked_curve(legs, bars_by_symbol)
        for row in _metrics_for_windows(curve, candidate):
            metric_rows.append(row)
        summary_row = _summarize_legs(legs)
        summary_row.update({"candidate_name": candidate.name, "candidate_label": candidate.label})
        leg_summary_rows.append(summary_row)
        leg_frames.append(legs)
        curve = curve.copy()
        curve["candidate_name"] = candidate.name
        curves.append(curve)

    detail = pd.concat(leg_frames, ignore_index=True)
    summary = pd.DataFrame(metric_rows)
    leg_summary = pd.DataFrame(leg_summary_rows)
    all_curves = pd.concat(curves, ignore_index=True) if curves else pd.DataFrame()

    baseline = summary[summary["candidate_name"].eq("A_c3_actual_path")][["window_name", "total_return_pct"]].rename(
        columns={"total_return_pct": "a_total_return_pct"}
    )
    summary = summary.merge(baseline, on="window_name", how="left")
    summary["return_retention_vs_a_pct"] = np.where(
        summary["a_total_return_pct"] > 0,
        summary["total_return_pct"] / summary["a_total_return_pct"] * 100.0,
        0.0,
    )
    summary["pass_window"] = (
        (summary["max_dd_percent"] >= -30.0)
        & (summary["return_retention_vs_a_pct"] >= 80.0)
        & (summary["total_return_pct"] > 0)
    )

    c_full = summary[
        summary["candidate_name"].eq("C_early_adverse_2atr_5d") & summary["window_name"].eq("start_2020")
    ].iloc[0]
    a_full = summary[
        summary["candidate_name"].eq("A_c3_actual_path") & summary["window_name"].eq("start_2020")
    ].iloc[0]
    c_windows = summary[summary["candidate_name"].eq("C_early_adverse_2atr_5d")]
    c_leg_summary = leg_summary[leg_summary["candidate_name"].eq("C_early_adverse_2atr_5d")].iloc[0]
    c_triggered_legs = int(c_leg_summary["triggered_legs"])
    synthetic_dd_improvement_pp = float(c_full["max_dd_percent"] - a_full["max_dd_percent"])
    c_return_retention_vs_a_pct = float(c_full["return_retention_vs_a_pct"])
    nontrivial_effect = c_triggered_legs > 0 and (
        abs(float(c_leg_summary["total_delta_gross_pnl"])) > EPSILON or abs(synthetic_dd_improvement_pp) > 0.05
    )
    pass_full = bool(c_full["pass_window"]) and nontrivial_effect and synthetic_dd_improvement_pp >= 0.0
    pass_window_count = int(c_windows["pass_window"].sum())
    decision = {
        "decision": "screen_pass_engine_validate" if pass_full and pass_window_count >= 6 else "screen_fail_do_not_implement",
        "pass_full": pass_full,
        "pass_window_count": pass_window_count,
        "reason": (
            "筛查通过全周期且多数窗口通过，可以进入真实引擎验证。"
            if pass_full and pass_window_count >= 6
            else "筛查没有产生非零有效触发或未改善合成A路径，不进入真实引擎实现。"
        ),
        "c_triggered_legs": c_triggered_legs,
        "synthetic_dd_improvement_pp": synthetic_dd_improvement_pp,
        "c_return_retention_vs_a_pct": c_return_retention_vs_a_pct,
        "nontrivial_effect": nontrivial_effect,
        "stage328_source": STAGE328_MODEL_TAG,
        "official_version": OFFICIAL_STAGE78_VERSION,
        "official_role": OFFICIAL_STAGE78_ROLE,
    }

    detail_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_detail_{MODEL_TAG}.csv"
    summary_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
    leg_summary_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_leg_summary_{MODEL_TAG}.csv"
    curve_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv"
    decision_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
    report_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

    top_changes = detail[detail["candidate_name"].eq("C_early_adverse_2atr_5d")].copy()
    top_changes = top_changes.reindex(top_changes["delta_gross_pnl"].abs().sort_values(ascending=False).index).head(60)

    detail.to_csv(detail_path, index=False, encoding="utf-8-sig")
    summary.to_csv(summary_path, index=False, encoding="utf-8-sig")
    leg_summary.to_csv(leg_summary_path, index=False, encoding="utf-8-sig")
    all_curves.to_csv(curve_path, index=False, encoding="utf-8-sig")
    decision_path.write_text(json.dumps(_to_builtin(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    report_path.write_text(_build_report(summary, leg_summary, top_changes, decision), encoding="utf-8")

    print(json.dumps(_to_builtin(decision), ensure_ascii=False, indent=2))
    print(f"[stage329] report: {report_path}")


if __name__ == "__main__":
    main()
