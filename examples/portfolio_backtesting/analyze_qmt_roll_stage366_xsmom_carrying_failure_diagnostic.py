from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from run_qmt_roll_selection_long015_volref30_corr_fu_candidate_robustness_backtest import (
    to_markdown_table,
)


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
MODEL_TAG = "stage366_xsmom_carrying_failure_diagnostic_v1"
OUTPUT_PREFIX = "qmt_roll_stage366_xsmom_carrying_failure_diagnostic"
LINE_ID = "futures_trend_drawdown30_preserve_return"

TARGET_MAX_DD_PCT = -30.0
MIN_RETURN_RETENTION_PCT = 80.0

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
WINDOW_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_window_attribution_{MODEL_TAG}.csv"
ANNUAL_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_annual_path_{MODEL_TAG}.csv"
MARGIN_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_margin_gap_{MODEL_TAG}.csv"
STRESS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_stress_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


def _load_csv(name: str) -> pd.DataFrame:
    path = OUTPUT_DIR / name
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(result) or math.isinf(result):
        return default
    return result


def _path_metrics(frame: pd.DataFrame, balance_col: str, start_capital: float) -> dict[str, float]:
    if frame.empty:
        return {
            "end_balance": start_capital,
            "total_return_pct": 0.0,
            "max_dd_percent": 0.0,
            "sharpe_ratio": 0.0,
            "ulcer_index": 0.0,
        }
    df = frame.copy()
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    df[balance_col] = pd.to_numeric(df[balance_col], errors="coerce")
    df = df.dropna(subset=["date", balance_col]).sort_values("date")
    if df.empty:
        return {
            "end_balance": start_capital,
            "total_return_pct": 0.0,
            "max_dd_percent": 0.0,
            "sharpe_ratio": 0.0,
            "ulcer_index": 0.0,
        }
    balance = df[balance_col].to_numpy(dtype=float)
    high = np.maximum.accumulate(balance)
    dd_pct = np.divide(balance - high, np.where(high == 0.0, np.nan, high)) * 100.0
    daily_return = pd.Series(balance).pct_change().replace([np.inf, -np.inf], np.nan).dropna()
    sharpe = 0.0
    if not daily_return.empty and daily_return.std(ddof=0) > 0:
        sharpe = float(daily_return.mean() / daily_return.std(ddof=0) * math.sqrt(252.0))
    return {
        "end_balance": float(balance[-1]),
        "total_return_pct": (float(balance[-1]) / start_capital - 1.0) * 100.0,
        "max_dd_percent": float(np.nanmin(dd_pct)) if len(dd_pct) else 0.0,
        "sharpe_ratio": sharpe,
        "ulcer_index": float(math.sqrt(np.nanmean(np.square(np.minimum(dd_pct, 0.0))))),
    }


def _layer_comparison() -> pd.DataFrame:
    stage345 = _load_csv("qmt_roll_stage345_cross_sectional_momentum_satellite_summary_stage345_cross_sectional_momentum_satellite_v1.csv")
    stage346 = _load_csv("qmt_roll_stage346_xsmom_integer_feasibility_summary_stage346_xsmom_integer_feasibility_v1.csv")
    stage348 = _load_csv("qmt_roll_stage348_xsmom_capital_split_frontier_summary_stage348_xsmom_capital_split_frontier_v1.csv")
    stage349 = _load_csv("qmt_roll_stage349_xsmom_350_150_multiperiod_pressure_summary_stage349_xsmom_350_150_multiperiod_pressure_v1.csv")

    rows: list[dict[str, Any]] = []

    netvalue = stage345[stage345["variant"].eq("c3_92p5_xsmom_mom_12m_skip1m_7p5_cost20bps")].iloc[0]
    rows.append(
        {
            "layer": "netvalue_fractional",
            "source_stage": "Stage045",
            "description": "92.5%C3 + 7.5%xsmom净值层，连续小数仓位",
            "total_return_pct": _safe_float(netvalue["total_return_pct"]),
            "return_retention_pct": _safe_float(netvalue["return_retention_vs_c3_pct"]),
            "max_dd_percent": _safe_float(netvalue["max_dd_percent"]),
            "sharpe_ratio": _safe_float(netvalue["sharpe_ratio"]),
            "max_actual_margin": np.nan,
            "max_required_min1_margin": np.nan,
            "zero_position_days": np.nan,
            "active_signal_days": np.nan,
            "pass_full_sample": int(
                _safe_float(netvalue["max_dd_percent"]) >= TARGET_MAX_DD_PCT
                and _safe_float(netvalue["return_retention_vs_c3_pct"]) >= MIN_RETURN_RETENTION_PCT
            ),
            "promotion_status": "净值层通过，但未证明可交易",
        }
    )

    for _, row in stage346.iterrows():
        rows.append(
            {
                "layer": f"integer_37p5k_{row['profile']}",
                "source_stage": "Stage046",
                "description": str(row["profile_label"]),
                "total_return_pct": _safe_float(row["combined_total_return_pct"]),
                "return_retention_pct": _safe_float(row["combined_retention_vs_c3_pct"]),
                "max_dd_percent": _safe_float(row["combined_max_dd_percent"]),
                "sharpe_ratio": _safe_float(row["combined_sharpe"]),
                "max_actual_margin": _safe_float(row["max_actual_margin"]),
                "max_required_min1_margin": _safe_float(row["max_required_min1_margin"]),
                "zero_position_days": int(_safe_float(row["zero_position_days"])),
                "active_signal_days": int(_safe_float(row["active_signal_days"])),
                "pass_full_sample": int(
                    _safe_float(row["combined_max_dd_percent"]) >= TARGET_MAX_DD_PCT
                    and _safe_float(row["combined_retention_vs_c3_pct"]) >= MIN_RETURN_RETENTION_PCT
                ),
                "promotion_status": "3.75万卫星腿不可承载",
            }
        )

    split = stage348[
        stage348["split_name"].eq("c3_350_sat_150") & stage348["profile"].eq("min1_cheapest_cap")
    ].iloc[0]
    rows.append(
        {
            "layer": "true_split_350k_150k_full_sample",
            "source_stage": "Stage048",
            "description": "35万C3 + 15万xsmom，真实整数手数粗前沿",
            "total_return_pct": _safe_float(split["combo_return_pct"]),
            "return_retention_pct": _safe_float(split["return_retention_vs_c3_500_pct"]),
            "max_dd_percent": _safe_float(split["combo_max_dd_pct"]),
            "sharpe_ratio": _safe_float(split["combo_sharpe"]),
            "max_actual_margin": _safe_float(split["max_satellite_margin"]),
            "max_required_min1_margin": _safe_float(split["max_required_min1_margin"]),
            "zero_position_days": int(_safe_float(split["zero_position_days"])),
            "active_signal_days": int(_safe_float(split["active_signal_days"])),
            "pass_full_sample": int(_safe_float(split["candidate_ok"])),
            "promotion_status": "全样本通过，仍需压力复验",
        }
    )

    full = stage349[stage349["window_name"].eq("start_2020")].iloc[0]
    rows.append(
        {
            "layer": "true_split_350k_150k_pressure_fixed",
            "source_stage": "Stage049",
            "description": "固定35万C3+15万xsmom后做多起点与滑点压力",
            "total_return_pct": _safe_float(full["combo_return_pct"]),
            "return_retention_pct": _safe_float(full["return_retention_vs_c3_500_pct"]),
            "max_dd_percent": _safe_float(full["combo_max_dd_pct"]),
            "sharpe_ratio": _safe_float(full["combo_sharpe"]),
            "max_actual_margin": _safe_float(full["max_satellite_margin"]),
            "max_required_min1_margin": _safe_float(full["max_required_min1_margin"]),
            "zero_position_days": int(_safe_float(full["zero_position_days"])),
            "active_signal_days": int(_safe_float(full["active_signal_days"])),
            "pass_full_sample": int(_safe_float(full["window_gate_ok"])),
            "promotion_status": "全样本通过，但多周期/压力失败",
        }
    )
    return pd.DataFrame(rows)


def _window_attribution() -> pd.DataFrame:
    summary = _load_csv("qmt_roll_stage349_xsmom_350_150_multiperiod_pressure_summary_stage349_xsmom_350_150_multiperiod_pressure_v1.csv")
    frame = summary.copy()
    frame["c3_350_retention_vs_c3_500_pct"] = np.where(
        frame["c3_500_return_pct"].astype(float) > 0,
        frame["c3_350_return_pct"].astype(float) / frame["c3_500_return_pct"].astype(float) * 100.0,
        np.nan,
    )
    frame["satellite_return_contribution_to_500k_pct"] = (
        frame["satellite_150_return_pct"].astype(float) * 150_000.0 / 500_000.0
    )
    frame["combo_gate_reason"] = np.where(
        frame["window_gate_ok"].astype(int).eq(1),
        "通过",
        np.where(
            frame["return_retention_vs_c3_500_pct"].astype(float) < MIN_RETURN_RETENTION_PCT,
            "收益保留不足",
            "回撤或其他闸门失败",
        ),
    )
    columns = [
        "window_name",
        "analysis_start",
        "analysis_end",
        "c3_500_return_pct",
        "c3_500_max_dd_pct",
        "c3_350_return_pct",
        "c3_350_max_dd_pct",
        "c3_350_retention_vs_c3_500_pct",
        "satellite_150_return_pct",
        "satellite_150_max_dd_pct",
        "satellite_return_contribution_to_500k_pct",
        "combo_return_pct",
        "combo_max_dd_pct",
        "return_retention_vs_c3_500_pct",
        "window_gate_ok",
        "combo_gate_reason",
        "zero_position_days",
        "active_signal_days",
        "max_margin_to_equity_pct",
        "review_days",
        "reject_days",
    ]
    return frame[columns]


def _annual_path() -> pd.DataFrame:
    baseline = _load_csv("qmt_roll_stage349_xsmom_350_150_multiperiod_pressure_baseline_daily_stage349_xsmom_350_150_multiperiod_pressure_v1.csv")
    combo = _load_csv("qmt_roll_stage349_xsmom_350_150_multiperiod_pressure_combo_daily_stage349_xsmom_350_150_multiperiod_pressure_v1.csv")
    satellite = _load_csv("qmt_roll_stage349_xsmom_350_150_multiperiod_pressure_satellite_daily_stage349_xsmom_350_150_multiperiod_pressure_v1.csv")

    baseline = baseline[baseline["window_name"].eq("start_2020")].copy()
    combo = combo[combo["window_name"].eq("start_2020")].copy()
    satellite = satellite[satellite["window_name"].eq("start_2020")].copy()
    for df in (baseline, combo, satellite):
        df["date"] = pd.to_datetime(df["date"]).dt.normalize()
        df["year"] = df["date"].dt.year

    rows: list[dict[str, Any]] = []
    for year, group in combo.groupby("year", sort=True):
        base_group = baseline[baseline["year"].eq(year)]
        sat_group = satellite[satellite["year"].eq(year)]
        if group.empty or base_group.empty:
            continue
        rows.append(
            {
                "year": int(year),
                "c3_500_year_net_pnl": float(base_group["net_pnl"].sum()),
                "c3_500_year_return_on_500k_pct": float(base_group["net_pnl"].sum() / 500_000.0 * 100.0),
                "c3_350_year_net_pnl": float(group["c3_candidate_net_pnl"].sum()),
                "c3_350_contribution_to_500k_pct": float(group["c3_candidate_net_pnl"].sum() / 500_000.0 * 100.0),
                "satellite_year_net_pnl": float(group["satellite_daily_pnl"].sum()),
                "satellite_contribution_to_500k_pct": float(group["satellite_daily_pnl"].sum() / 500_000.0 * 100.0),
                "combo_year_net_pnl": float(group["combo_net_pnl"].sum()),
                "combo_year_return_on_500k_pct": float(group["combo_net_pnl"].sum() / 500_000.0 * 100.0),
                "satellite_turnover_contracts": float(group["satellite_turnover_contracts"].sum()),
                "satellite_zero_position_days": int(sat_group["zero_position_flag"].sum()) if not sat_group.empty else 0,
                "satellite_active_signal_days": int((sat_group["desired_signal_count"] > 0).sum()) if not sat_group.empty else 0,
            }
        )
    return pd.DataFrame(rows)


def _margin_gap() -> pd.DataFrame:
    daily_37p5 = _load_csv("qmt_roll_stage346_xsmom_integer_feasibility_daily_stage346_xsmom_integer_feasibility_v1.csv")
    sat150 = _load_csv("qmt_roll_stage349_xsmom_350_150_multiperiod_pressure_satellite_daily_stage349_xsmom_350_150_multiperiod_pressure_v1.csv")
    sat150 = sat150[sat150["window_name"].eq("start_2020")].copy()

    rows: list[dict[str, Any]] = []
    for profile, group in daily_37p5.groupby("profile", sort=True):
        active = group[group["desired_signal_count"].astype(float) > 0]
        rows.append(
            {
                "carrier": f"37p5k_{profile}",
                "capital": 37_500.0,
                "active_signal_days": int(len(active)),
                "zero_position_days": int(group["zero_position_flag"].sum()),
                "zero_position_ratio_pct": float(group["zero_position_flag"].sum() / max(len(active), 1) * 100.0),
                "max_required_min1_margin": float(group["required_min1_margin"].max()),
                "avg_required_min1_margin_when_active": float(active["required_min1_margin"].mean()) if not active.empty else 0.0,
                "max_actual_margin": float(group["actual_margin"].max()),
                "avg_actual_margin_when_active": float(active["actual_margin"].mean()) if not active.empty else 0.0,
                "capital_to_max_required_margin_pct": float(37_500.0 / max(group["required_min1_margin"].max(), 1.0) * 100.0),
            }
        )
    active150 = sat150[sat150["desired_signal_count"].astype(float) > 0]
    rows.append(
        {
            "carrier": "150k_min1_cheapest",
            "capital": 150_000.0,
            "active_signal_days": int(len(active150)),
            "zero_position_days": int(sat150["zero_position_flag"].sum()),
            "zero_position_ratio_pct": float(sat150["zero_position_flag"].sum() / max(len(active150), 1) * 100.0),
            "max_required_min1_margin": float(sat150["required_min1_margin"].max()),
            "avg_required_min1_margin_when_active": float(active150["required_min1_margin"].mean()) if not active150.empty else 0.0,
            "max_actual_margin": float(sat150["satellite_margin"].max()),
            "avg_actual_margin_when_active": float(active150["satellite_margin"].mean()) if not active150.empty else 0.0,
            "capital_to_max_required_margin_pct": float(150_000.0 / max(sat150["required_min1_margin"].max(), 1.0) * 100.0),
        }
    )
    return pd.DataFrame(rows)


def _stress_table() -> pd.DataFrame:
    return _load_csv("qmt_roll_stage349_xsmom_350_150_multiperiod_pressure_slippage_stress_stage349_xsmom_350_150_multiperiod_pressure_v1.csv")


def _decision(summary: pd.DataFrame, windows: pd.DataFrame, stress: pd.DataFrame, margin_gap: pd.DataFrame) -> dict[str, Any]:
    failed_windows = windows[windows["window_gate_ok"].astype(int).eq(0)]
    stress_failed = stress[stress["stress_gate_ok"].astype(int).eq(0)]
    min1_ratio = margin_gap.loc[margin_gap["carrier"].eq("150k_min1_cheapest"), "capital_to_max_required_margin_pct"]
    min1_coverage = float(min1_ratio.iloc[0]) if not min1_ratio.empty else 0.0
    decision = {
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "decision": "xsmom_theory_valid_but_current_futures_carrier_fail",
        "candidate_promotable": False,
        "reason_codes": [
            "netvalue_fractional_sizing_not_equal_to_futures_integer_lots",
            "37p5k_satellite_leg_under_capitalized",
            "350k_150k_true_split_fails_start_year_retention",
            "350k_150k_true_split_fails_3x_slippage_drawdown",
        ],
        "failed_window_count": int(len(failed_windows)),
        "failed_windows": failed_windows["window_name"].tolist(),
        "failed_slippage_multipliers": stress_failed["slippage_multiplier"].astype(float).tolist(),
        "capital_to_max_required_min1_margin_pct_150k": min1_coverage,
        "next_action": "stop_current_xsmom_futures_satellite_shape; only continue with different vehicle, larger capital, or monitor-only use",
        "overfit_reflection": "本阶段不新增参数，只做承载失败归因；继续微调35/15或xsmom窗口会转为过拟合。",
        "continued_value_reflection": "xsmom因子仍有理论和净值层价值，但当前期货卫星承载方式不能满足目标；继续价值在换承载方式或寻找新独立收益源。",
    }
    return decision


def _write_report(
    summary: pd.DataFrame,
    windows: pd.DataFrame,
    annual: pd.DataFrame,
    margin_gap: pd.DataFrame,
    stress: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    full_true_split = summary[summary["layer"].eq("true_split_350k_150k_pressure_fixed")]
    full_line = full_true_split.iloc[0].to_dict() if not full_true_split.empty else {}
    failed_windows = windows[windows["window_gate_ok"].astype(int).eq(0)]
    lines = [
        "# Stage366 xsmom真实承载失败归因",
        "",
        "## 本阶段定位",
        "",
        "- 目标：解释 Stage045 净值层 xsmom 候选为什么不能直接成为正式降回撤版本。",
        "- 本阶段不修改第78-1、C3、AI池、品种池或交易规则；只读取 Stage345/346/348/349 的既有结果做归因。",
        "- 预设闸门：最大回撤不低于 `-30%`，收益保留不低于 `80%`，并且不能只在全样本成立。",
        "",
        "## 外部调研与判断",
        "",
        "- 商品期货横截面动量有成熟文献基础，适合作为低相关收益源候选。",
        "- 但文献和实盘之间的关键差距在于：真实期货账户要面对合约乘数、保证金、最小1手、换手成本和滑点压力。",
        "- 因此，本阶段只判断承载层，不继续调 xsmom 窗口、权重或品种。",
        "",
        "## 层级对比",
        "",
        to_markdown_table(summary),
        "",
        "## 多周期归因",
        "",
        to_markdown_table(windows),
        "",
        "## 年度路径拆解",
        "",
        to_markdown_table(annual),
        "",
        "## 手数与保证金缺口",
        "",
        to_markdown_table(margin_gap),
        "",
        "## 滑点压力",
        "",
        to_markdown_table(stress),
        "",
        "## 结论",
        "",
        f"- 决策：`{decision['decision']}`。",
        f"- 是否可晋级：`{decision['candidate_promotable']}`。",
        f"- 固定35万C3+15万xsmom全样本：总收益 `{_safe_float(full_line.get('total_return_pct')):.4f}%`，最大回撤 `{_safe_float(full_line.get('max_dd_percent')):.4f}%`，收益保留 `{_safe_float(full_line.get('return_retention_pct')):.4f}%`。",
        f"- 失败窗口数：`{decision['failed_window_count']}`；失败窗口：`{', '.join(decision['failed_windows'])}`。",
        f"- 失败滑点压力：`{decision['failed_slippage_multipliers']}`。",
        "",
        "## 判断",
        "",
        "- Stage045 的 xsmom 不是没有研究价值；它的问题是净值层连续小数仓位不能被当前资金规模的期货整数手数复现。",
        "- 3.75万卫星腿资金不足，15万卫星腿全样本好看但多起点收益保留不足，且 3x 滑点后最大回撤跌破30%闸门。",
        "- 当前形状不能作为正式版本；若继续动量方向，应换承载工具、提高独立资金口径，或降级成风险温度计/解释层。",
        "",
        "## 过拟合反思",
        "",
        "- 运行前判断：不是过拟合；本阶段只做既有候选的承载归因，不新增参数。",
        "- 运行后判断：不是过拟合；失败来自资金离散、启动年份和成本压力，而不是单个历史窗口。",
        "- 后续若继续扫 `34/16`、`36/14`、`6.5%/7%/8%` 或月度窗口小数，就是过拟合。",
        "",
        "## 继续价值反思",
        "",
        "- 运行前判断：有价值；xsmom 是少数净值层能明显改善回撤和平滑度的候选，必须拆清楚执行失败原因。",
        "- 运行后判断：当前期货卫星形状继续价值低；总研究线仍有价值。",
        "- 下一步：停止当前 xsmom 期货卫星微调，优先寻找新的独立收益源，或只把 xsmom 作为账户级监控/解释层。",
    ]
    if not failed_windows.empty:
        lines.extend(
            [
                "",
                "## 失败窗口摘要",
                "",
                to_markdown_table(
                    failed_windows[
                        [
                            "window_name",
                            "c3_500_return_pct",
                            "combo_return_pct",
                            "return_retention_vs_c3_500_pct",
                            "combo_max_dd_pct",
                            "combo_gate_reason",
                        ]
                    ]
                ),
            ]
        )
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    summary = _layer_comparison()
    windows = _window_attribution()
    annual = _annual_path()
    margin_gap = _margin_gap()
    stress = _stress_table()
    decision = _decision(summary, windows, stress, margin_gap)

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    windows.to_csv(WINDOW_PATH, index=False, encoding="utf-8-sig")
    annual.to_csv(ANNUAL_PATH, index=False, encoding="utf-8-sig")
    margin_gap.to_csv(MARGIN_PATH, index=False, encoding="utf-8-sig")
    stress.to_csv(STRESS_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(decision, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(summary, windows, annual, margin_gap, stress, decision)

    print(f"[stage366] decision: {decision['decision']}")
    print(f"[stage366] report: {REPORT_PATH}")


if __name__ == "__main__":
    main()
