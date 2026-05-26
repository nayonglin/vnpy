from __future__ import annotations

import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from analyze_qmt_roll_stage324_true_combo_capital_margin import _to_builtin, _to_markdown_table
from analyze_qmt_roll_stage328_c3_single_path_loss_attribution import (
    MODEL_TAG as STAGE328_MODEL_TAG,
    _load_bars_for_round_trips,
)
from qmt_roll_official_stage78_config import OFFICIAL_STAGE78_ROLE, OFFICIAL_STAGE78_VERSION
from run_qmt_alignment_backtest import OUTPUT_DIR


MODEL_TAG = "stage330_c3_mae_timing_diagnostic_v1"
OUTPUT_PREFIX = "qmt_roll_stage330_c3_mae_timing_diagnostic"
ROUND_TRIPS_PATH = (
    OUTPUT_DIR
    / "qmt_roll_stage328_c3_single_path_loss_attribution_round_trips_stage328_c3_single_path_loss_attribution_v1.csv"
)
MAX_DD_PEAK = pd.Timestamp("2021-05-12")
MAX_DD_TROUGH = pd.Timestamp("2021-07-02")


def _sign(direction: str) -> float:
    return 1.0 if str(direction).lower() == "long" else -1.0


def _bucket_day(day_index: float) -> str:
    if not np.isfinite(day_index):
        return "missing"
    if day_index <= 1:
        return "day_0_1"
    if day_index <= 5:
        return "day_2_5"
    if day_index <= 20:
        return "day_6_20"
    if day_index <= 60:
        return "day_21_60"
    return "day_gt_60"


def _pattern(row: dict[str, Any]) -> str:
    mae = float(row["hilo_mae_atr"])
    mae_day = float(row["hilo_days_to_mae"])
    mfe_before_mae = float(row["hilo_mfe_before_mae_atr"])
    mfe = float(row["hilo_mfe_atr"])
    mfe_day = float(row["hilo_days_to_mfe"])
    if not np.isfinite(mae):
        return "missing_path"
    if mae <= -2.0 and mae_day <= 5 and mfe_before_mae < 1.0:
        return "early_2atr_adverse_no_1atr_progress"
    if mae <= -2.0 and np.isfinite(mfe_day) and mfe_day < mae_day and mfe >= 2.0:
        return "giveback_after_2atr_profit"
    if mae <= -2.0 and mae_day > 5:
        return "late_2atr_adverse"
    if mae <= -1.0 and mae_day <= 5:
        return "early_1atr_adverse"
    if mae <= -1.0:
        return "mild_late_adverse"
    return "no_large_adverse"


def _load_round_trips() -> pd.DataFrame:
    if not ROUND_TRIPS_PATH.exists():
        raise FileNotFoundError(
            f"Stage328 round trips not found: {ROUND_TRIPS_PATH}. Run analyze_qmt_roll_stage328 first."
        )
    frame = pd.read_csv(ROUND_TRIPS_PATH)
    for column in ["entry_date", "exit_date", "entry_datetime", "exit_datetime"]:
        if column in frame.columns:
            frame[column] = pd.to_datetime(frame[column], errors="coerce").dt.tz_localize(None)
    numeric_cols = [
        "entry_price",
        "exit_price",
        "volume",
        "size",
        "gross_pnl",
        "gross_return_pct",
        "atr20_pct",
        "holding_days",
        "overlaps_max_dd_window",
    ]
    for column in numeric_cols:
        frame[column] = pd.to_numeric(frame.get(column, np.nan), errors="coerce")
    return frame.sort_values(["entry_date", "leg_id"]).reset_index(drop=True)


def _leg_path_metrics(row: dict[str, Any], bars: pd.DataFrame) -> dict[str, Any]:
    entry_date = pd.Timestamp(row["entry_date"]).normalize()
    exit_date = pd.Timestamp(row["exit_date"]).normalize()
    entry_price = float(row["entry_price"])
    atr_pct = float(row.get("atr20_pct", math.nan))
    direction = str(row["direction"])
    sign = _sign(direction)
    atr_abs = entry_price * atr_pct / 100.0 if np.isfinite(atr_pct) and entry_price > 0 else math.nan
    if bars.empty or not np.isfinite(atr_abs) or atr_abs <= 0:
        return {
            "close_mae_atr": math.nan,
            "close_mfe_atr": math.nan,
            "hilo_mae_atr": math.nan,
            "hilo_mfe_atr": math.nan,
            "close_days_to_mae": math.nan,
            "close_days_to_mfe": math.nan,
            "hilo_days_to_mae": math.nan,
            "hilo_days_to_mfe": math.nan,
            "hilo_mfe_before_mae_atr": math.nan,
        }

    path = bars[(bars["date"] >= entry_date) & (bars["date"] <= exit_date)].copy().sort_values("date")
    if path.empty:
        return {
            "close_mae_atr": math.nan,
            "close_mfe_atr": math.nan,
            "hilo_mae_atr": math.nan,
            "hilo_mfe_atr": math.nan,
            "close_days_to_mae": math.nan,
            "close_days_to_mfe": math.nan,
            "hilo_days_to_mae": math.nan,
            "hilo_days_to_mfe": math.nan,
            "hilo_mfe_before_mae_atr": math.nan,
        }

    path = path.reset_index(drop=True)
    close_move = (path["close"].astype(float) - entry_price) * sign / atr_abs
    if direction.lower() == "long":
        adverse_move = (path["low"].astype(float) - entry_price) / atr_abs
        favorable_move = (path["high"].astype(float) - entry_price) / atr_abs
    else:
        adverse_move = (entry_price - path["high"].astype(float)) / atr_abs
        favorable_move = (entry_price - path["low"].astype(float)) / atr_abs

    close_mae_idx = int(close_move.idxmin())
    close_mfe_idx = int(close_move.idxmax())
    hilo_mae_idx = int(adverse_move.idxmin())
    hilo_mfe_idx = int(favorable_move.idxmax())
    mfe_before_mae = float(favorable_move.iloc[: hilo_mae_idx + 1].max())
    return {
        "close_mae_atr": float(close_move.min()),
        "close_mfe_atr": float(close_move.max()),
        "hilo_mae_atr": float(adverse_move.min()),
        "hilo_mfe_atr": float(favorable_move.max()),
        "close_days_to_mae": close_mae_idx,
        "close_days_to_mfe": close_mfe_idx,
        "hilo_days_to_mae": hilo_mae_idx,
        "hilo_days_to_mfe": hilo_mfe_idx,
        "hilo_mfe_before_mae_atr": mfe_before_mae,
    }


def _summarize(frame: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    grouped = frame.groupby(group_cols, dropna=False)
    rows: list[dict[str, Any]] = []
    for key, part in grouped:
        if not isinstance(key, tuple):
            key = (key,)
        row = {col: value for col, value in zip(group_cols, key)}
        row.update(
            {
                "count": int(len(part)),
                "gross_pnl": float(part["gross_pnl"].sum()),
                "median_return_pct": float(part["gross_return_pct"].median()),
                "win_rate_pct": float((part["gross_pnl"] > 0).mean() * 100.0),
                "median_hilo_mae_atr": float(part["hilo_mae_atr"].median()),
                "median_hilo_mfe_atr": float(part["hilo_mfe_atr"].median()),
                "dd_overlap_count": int(part["overlaps_max_dd_window"].fillna(0).astype(int).sum()),
            }
        )
        rows.append(row)
    return pd.DataFrame(rows).sort_values(["dd_overlap_count", "gross_pnl"], ascending=[False, True])


def _build_report(
    overall_timing: pd.DataFrame,
    dd_timing: pd.DataFrame,
    pattern_summary: pd.DataFrame,
    top_dd_legs: pd.DataFrame,
    decision: dict[str, Any],
) -> str:
    top_cols = [
        "leg_id",
        "product_vt_symbol",
        "vt_symbol",
        "direction",
        "entry_date",
        "exit_date",
        "gross_pnl",
        "gross_return_pct",
        "hilo_mae_atr",
        "hilo_days_to_mae",
        "hilo_mfe_atr",
        "hilo_days_to_mfe",
        "hilo_mfe_before_mae_atr",
        "path_pattern",
        "exit_reason",
    ]
    return "\n".join(
        [
            "# Stage030 C3 MAE发生时点诊断",
            "",
            "## 定位",
            "",
            "- 本阶段是诊断，不修改正式策略，不产生候选参数。",
            "- 目标是回答：C3剩余最大回撤来自开仓后早期不利、晚期不利，还是先有利润后的回吐。",
            "- 使用日线 high/low/close 与开仓时 ATR 归一化，避免直接比较不同品种价格。",
            "",
            "## 全部交易回合按最大不利时点分组",
            "",
            _to_markdown_table(overall_timing, overall_timing.columns.tolist(), max_rows=30),
            "",
            "## 最大回撤窗口交易回合按最大不利时点分组",
            "",
            _to_markdown_table(dd_timing, dd_timing.columns.tolist(), max_rows=30),
            "",
            "## 路径形态分组",
            "",
            _to_markdown_table(pattern_summary, pattern_summary.columns.tolist(), max_rows=30),
            "",
            "## 最大回撤窗口内最不利交易回合",
            "",
            _to_markdown_table(top_dd_legs, top_cols, max_rows=30),
            "",
            "## 判断",
            "",
            f"- 诊断标签：`{decision['decision']}`。",
            f"- 最大回撤重叠回合数：`{decision['dd_overlap_legs']}`。",
            f"- 最大回撤重叠回合中，早期2ATR无进展形态占比：`{decision['early_2atr_no_progress_share_pct']:.4f}%`。",
            f"- 最大回撤重叠回合中，先有2ATR利润再回吐形态占比：`{decision['giveback_after_profit_share_pct']:.4f}%`。",
            f"- 最大回撤重叠回合中，晚期2ATR不利形态占比：`{decision['late_2atr_adverse_share_pct']:.4f}%`。",
            "",
            "## 反思",
            "",
            "- 是否过拟合：本阶段只是路径归因，不用结果生成交易参数，因此不是过拟合；但若直接按最高亏损桶设阈值，会变成过拟合。",
            "- 是否还有价值继续：若某个路径形态在最大回撤窗口显著集中，才值得冻结一个低自由度候选进入真实引擎验证；否则应停止路径早停方向。",
        ]
    )


def main() -> None:
    round_trips = _load_round_trips()
    bars_by_symbol = _load_bars_for_round_trips(round_trips)

    rows: list[dict[str, Any]] = []
    for row in round_trips.to_dict("records"):
        bars = bars_by_symbol.get(str(row["vt_symbol"]), pd.DataFrame())
        metrics = _leg_path_metrics(row, bars)
        merged = {**row, **metrics}
        merged["hilo_mae_day_bucket"] = _bucket_day(float(merged["hilo_days_to_mae"]))
        merged["close_mae_day_bucket"] = _bucket_day(float(merged["close_days_to_mae"]))
        merged["path_pattern"] = _pattern(merged)
        merged["entered_before_dd_peak"] = int(pd.Timestamp(row["entry_date"]) <= MAX_DD_PEAK)
        merged["exited_after_dd_peak"] = int(pd.Timestamp(row["exit_date"]) >= MAX_DD_PEAK)
        rows.append(merged)

    detail = pd.DataFrame(rows)
    overall_timing = _summarize(detail, ["hilo_mae_day_bucket"])
    dd_detail = detail[detail["overlaps_max_dd_window"].fillna(0).astype(int).eq(1)].copy()
    dd_timing = _summarize(dd_detail, ["hilo_mae_day_bucket"]) if not dd_detail.empty else pd.DataFrame()
    pattern_summary = _summarize(detail, ["path_pattern"])
    top_dd_legs = dd_detail.sort_values("hilo_mae_atr", ascending=True).head(50)

    dd_count = int(len(dd_detail))
    if dd_count > 0:
        early_share = float((dd_detail["path_pattern"].eq("early_2atr_adverse_no_1atr_progress")).mean() * 100.0)
        giveback_share = float((dd_detail["path_pattern"].eq("giveback_after_2atr_profit")).mean() * 100.0)
        late_share = float((dd_detail["path_pattern"].eq("late_2atr_adverse")).mean() * 100.0)
    else:
        early_share = giveback_share = late_share = 0.0

    if early_share >= 30.0:
        label = "early_adverse_candidate_worth_freezing"
    elif giveback_share >= 30.0:
        label = "giveback_candidate_worth_freezing"
    elif late_share >= 30.0:
        label = "late_adverse_candidate_worth_freezing"
    else:
        label = "no_single_path_shape_dominates"

    decision = {
        "decision": label,
        "dd_overlap_legs": dd_count,
        "early_2atr_no_progress_share_pct": early_share,
        "giveback_after_profit_share_pct": giveback_share,
        "late_2atr_adverse_share_pct": late_share,
        "stage328_source": STAGE328_MODEL_TAG,
        "official_version": OFFICIAL_STAGE78_VERSION,
        "official_role": OFFICIAL_STAGE78_ROLE,
    }

    detail_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_detail_{MODEL_TAG}.csv"
    overall_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_overall_timing_{MODEL_TAG}.csv"
    dd_timing_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_dd_timing_{MODEL_TAG}.csv"
    pattern_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_pattern_summary_{MODEL_TAG}.csv"
    top_dd_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_top_dd_legs_{MODEL_TAG}.csv"
    decision_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
    report_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

    detail.to_csv(detail_path, index=False, encoding="utf-8-sig")
    overall_timing.to_csv(overall_path, index=False, encoding="utf-8-sig")
    dd_timing.to_csv(dd_timing_path, index=False, encoding="utf-8-sig")
    pattern_summary.to_csv(pattern_path, index=False, encoding="utf-8-sig")
    top_dd_legs.to_csv(top_dd_path, index=False, encoding="utf-8-sig")
    decision_path.write_text(json.dumps(_to_builtin(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    report_path.write_text(_build_report(overall_timing, dd_timing, pattern_summary, top_dd_legs, decision), encoding="utf-8")

    print(json.dumps(_to_builtin(decision), ensure_ascii=False, indent=2))
    print(f"[stage330] report: {report_path}")


if __name__ == "__main__":
    main()
