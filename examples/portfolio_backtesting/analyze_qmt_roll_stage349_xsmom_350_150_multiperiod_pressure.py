from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import numpy as np
import pandas as pd

from analyze_qmt_roll_stage324_true_combo_capital_margin import (
    MARGIN_REJECT_PCT,
    MARGIN_REVIEW_PCT,
    TOTAL_CAPITAL,
    _c3_overrides,
    _margin_daily,
    _margin_summary,
    _metadata,
    _path_metrics,
    _safe_float,
    _to_builtin,
    _to_markdown_table,
)
from analyze_qmt_roll_stage348_xsmom_capital_split_frontier import (
    Profile,
    Split,
    _build_price_frame,
    _load_signal_daily,
    _simulate_satellite,
)
from qmt_roll_official_stage78_config import OFFICIAL_STAGE78_ROLE, OFFICIAL_STAGE78_VERSION
from qmt_universe import END_DT, PRELOAD_START_DT, START_DT
from run_qmt_alignment_backtest import OUTPUT_DIR, build_positions_df
from run_qmt_roll_backtest import run_backtest as run_roll_backtest
from run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest import BASE_RISK_RATIO


MODEL_TAG = "stage349_xsmom_350_150_multiperiod_pressure_v1"
OUTPUT_PREFIX = "qmt_roll_stage349_xsmom_350_150_multiperiod_pressure"
LINE_ID = "futures_trend_drawdown30_preserve_return"

C3_BASELINE_CAPITAL: float = 500_000.0
C3_CANDIDATE_CAPITAL: float = 350_000.0
SATELLITE_CAPITAL: float = 150_000.0

SATELLITE_SPLIT = Split("c3_350_sat_150", C3_CANDIDATE_CAPITAL, SATELLITE_CAPITAL)
SATELLITE_PROFILE = Profile(
    "min1_cheapest_cap",
    "低保证金信号优先，每腿至少1手，总保证金不超卫星资金",
    "min1_cheapest",
)

SLIPPAGE_MULTIPLIERS: tuple[float, ...] = (1.0, 2.0, 3.0, 5.0)


@dataclass(frozen=True)
class Window:
    name: str
    label: str
    start: datetime
    end: datetime
    group: str


WINDOWS: tuple[Window, ...] = (
    Window("start_2020", "2020起点至今", START_DT, END_DT, "start_year"),
    Window("start_2021", "2021起点至今", datetime(2021, 1, 1), END_DT, "start_year"),
    Window("start_2022", "2022起点至今", datetime(2022, 1, 1), END_DT, "start_year"),
    Window("start_2023", "2023起点至今", datetime(2023, 1, 1), END_DT, "start_year"),
    Window("start_2024", "2024起点至今", datetime(2024, 1, 1), END_DT, "start_year"),
    Window("start_2025", "2025起点至今", datetime(2025, 1, 1), END_DT, "start_year"),
    Window("ytd_2026", "2026年初至今", datetime(2026, 1, 1), END_DT, "start_year"),
    Window("weak_2021_full", "2021弱窗口全年", datetime(2021, 1, 1), datetime(2021, 12, 31), "weak_window"),
    Window("phase_2024_2025", "2024-2025独立启动", datetime(2024, 1, 1), datetime(2025, 12, 31), "weak_window"),
)


def _daily_from_analysis_with_slippage(analysis_df: pd.DataFrame | None, capital: float, label: str) -> pd.DataFrame:
    if analysis_df is None or analysis_df.empty:
        return pd.DataFrame(
            columns=[
                "date",
                f"{label}_balance",
                f"{label}_net_pnl",
                f"{label}_trade_count",
                f"{label}_slippage",
            ]
        )
    frame = analysis_df.copy().reset_index().rename(columns={"index": "date"})
    frame["date"] = pd.to_datetime(frame["date"]).dt.normalize()
    frame = frame.sort_values("date").drop_duplicates("date", keep="last")
    frame[f"{label}_balance"] = pd.to_numeric(frame.get("balance", capital), errors="coerce").ffill().fillna(capital)
    frame[f"{label}_net_pnl"] = pd.to_numeric(frame.get("net_pnl", 0.0), errors="coerce").fillna(0.0)
    frame[f"{label}_trade_count"] = pd.to_numeric(frame.get("trade_count", 0.0), errors="coerce").fillna(0.0)
    frame[f"{label}_slippage"] = pd.to_numeric(frame.get("slippage", 0.0), errors="coerce").fillna(0.0)
    return frame[
        [
            "date",
            f"{label}_balance",
            f"{label}_net_pnl",
            f"{label}_trade_count",
            f"{label}_slippage",
        ]
    ]


def _run_c3(window: Window, capital: float, label: str) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    preload_start = max(PRELOAD_START_DT, window.start - timedelta(days=365))
    print(f"[stage349] run C3 {label} {window.name} capital={capital:.0f}", flush=True)
    engine, analysis_df, statistics = run_roll_backtest(
        risk_ratio=BASE_RISK_RATIO,
        strategy_overrides=_c3_overrides(window.start),
        analysis_start=window.start,
        analysis_end=window.end,
        preload_start=preload_start,
        capital=capital,
        save_artifacts=False,
        include_start_year_sweep=False,
        file_prefix=f"{OUTPUT_PREFIX}_{label}_{window.name}",
        chart_title=f"Stage349 {label} {window.label}",
    )
    return _daily_from_analysis_with_slippage(analysis_df, capital, label), build_positions_df(engine), statistics


def _run_satellite(window: Window, price_frame: pd.DataFrame, signals: pd.DataFrame) -> pd.DataFrame:
    print(f"[stage349] simulate xsmom satellite {window.name} capital={SATELLITE_CAPITAL:.0f}", flush=True)
    start = pd.Timestamp(window.start).normalize()
    end = pd.Timestamp(window.end).normalize()
    window_signals = signals[signals["date"].between(start, end)].copy()
    if window_signals.empty:
        return pd.DataFrame(
            columns=[
                "date",
                "satellite_daily_pnl",
                "satellite_turnover_contracts",
                "satellite_slippage_cost",
                "satellite_balance",
                "satellite_margin",
                "held_contract_count",
                "required_min1_margin",
                "zero_position_flag",
                "desired_signal_count",
            ]
        )
    window_prices = price_frame[price_frame["date"].between(start, end)].copy()
    return _simulate_satellite(SATELLITE_SPLIT, SATELLITE_PROFILE, window_prices, window_signals)


def _baseline_daily_from_c3(c3_daily: pd.DataFrame) -> pd.DataFrame:
    frame = c3_daily.copy()
    frame = frame.rename(
        columns={
            "c3_baseline_net_pnl": "net_pnl",
            "c3_baseline_trade_count": "trade_count",
            "c3_baseline_slippage": "slippage",
            "c3_baseline_balance": "balance",
        }
    )
    for column in ["net_pnl", "trade_count", "slippage"]:
        frame[column] = pd.to_numeric(frame.get(column, 0.0), errors="coerce").fillna(0.0)
    frame["balance"] = TOTAL_CAPITAL + frame["net_pnl"].cumsum()
    return frame[["date", "balance", "net_pnl", "trade_count", "slippage"]]


def _combine_candidate_daily(c3_daily: pd.DataFrame, satellite: pd.DataFrame) -> pd.DataFrame:
    dates = sorted(set(c3_daily["date"]).union(set(satellite["date"])))
    if not dates:
        return pd.DataFrame()
    merged = pd.DataFrame({"date": pd.to_datetime(dates)})
    merged = merged.merge(c3_daily, on="date", how="left").merge(
        satellite[
            [
                "date",
                "satellite_daily_pnl",
                "satellite_turnover_contracts",
                "satellite_slippage_cost",
                "satellite_balance",
            ]
        ],
        on="date",
        how="left",
    )
    for column in [
        "c3_candidate_net_pnl",
        "satellite_daily_pnl",
        "c3_candidate_trade_count",
        "satellite_turnover_contracts",
        "c3_candidate_slippage",
        "satellite_slippage_cost",
    ]:
        merged[column] = pd.to_numeric(merged.get(column, 0.0), errors="coerce").fillna(0.0)
    merged["combo_net_pnl"] = merged["c3_candidate_net_pnl"] + merged["satellite_daily_pnl"]
    merged["combo_slippage"] = merged["c3_candidate_slippage"] + merged["satellite_slippage_cost"]
    merged["balance"] = TOTAL_CAPITAL + merged["combo_net_pnl"].cumsum()
    merged["highlevel"] = merged["balance"].cummax()
    merged["drawdown"] = merged["balance"] - merged["highlevel"]
    merged["ddpercent"] = np.divide(
        merged["drawdown"],
        merged["highlevel"].replace(0.0, np.nan),
    ).fillna(0.0) * 100.0
    merged["trade_count"] = merged["c3_candidate_trade_count"] + merged["satellite_turnover_contracts"]
    return merged


def _combine_margin(combo_daily: pd.DataFrame, c3_positions: pd.DataFrame, satellite: pd.DataFrame, metadata: dict[str, Any]) -> pd.DataFrame:
    if combo_daily.empty:
        return pd.DataFrame()
    margin = combo_daily[["date", "balance"]].copy()
    margin = margin.merge(_margin_daily(c3_positions, metadata, "c3"), on="date", how="left")
    margin = margin.merge(
        satellite[["date", "satellite_margin", "held_contract_count"]],
        on="date",
        how="left",
    )
    for column in ["c3_margin", "c3_active_contracts", "c3_active_products", "satellite_margin", "held_contract_count"]:
        margin[column] = pd.to_numeric(margin.get(column, 0.0), errors="coerce").fillna(0.0)
    margin["satellite_active_contracts"] = margin["held_contract_count"]
    margin["satellite_active_products"] = margin["held_contract_count"].clip(upper=6)
    margin["total_margin"] = margin["c3_margin"] + margin["satellite_margin"]
    margin["total_active_contracts"] = margin["c3_active_contracts"] + margin["satellite_active_contracts"]
    margin["total_active_products"] = margin["c3_active_products"] + margin["satellite_active_products"]
    margin["margin_to_equity_pct"] = (
        margin["total_margin"] / margin["balance"].replace(0.0, np.nan) * 100.0
    ).fillna(0.0)
    margin["margin_to_initial_capital_pct"] = margin["total_margin"] / TOTAL_CAPITAL * 100.0
    return margin


def _metrics_from_daily(daily: pd.DataFrame, capital: float = TOTAL_CAPITAL) -> dict[str, float]:
    return _path_metrics(daily, capital)


def _satellite_metrics(satellite: pd.DataFrame) -> dict[str, float]:
    if satellite.empty:
        return {
            "end_balance": SATELLITE_CAPITAL,
            "total_return_pct": 0.0,
            "max_dd_percent": 0.0,
            "sharpe_ratio": 0.0,
        }
    return _path_metrics(satellite.rename(columns={"satellite_balance": "balance"}), SATELLITE_CAPITAL)


def _stressed_metrics(daily: pd.DataFrame, pnl_column: str, slippage_column: str, multiplier: float) -> dict[str, float]:
    frame = daily[["date", pnl_column, slippage_column]].copy()
    frame[pnl_column] = pd.to_numeric(frame[pnl_column], errors="coerce").fillna(0.0)
    frame[slippage_column] = pd.to_numeric(frame[slippage_column], errors="coerce").fillna(0.0)
    frame["net_pnl"] = frame[pnl_column] - (multiplier - 1.0) * frame[slippage_column]
    frame["balance"] = TOTAL_CAPITAL + frame["net_pnl"].cumsum()
    metrics = _path_metrics(frame, TOTAL_CAPITAL)
    metrics["total_slippage"] = float(frame[slippage_column].sum() * multiplier)
    metrics["extra_slippage"] = float(frame[slippage_column].sum() * (multiplier - 1.0))
    return metrics


def _window_gate(c3_return: float, combo_return: float, combo_dd: float) -> tuple[int, float]:
    if c3_return > 0:
        retention = combo_return / c3_return * 100.0
        return int(combo_dd >= -30.0 and retention >= 80.0), retention
    return int(combo_dd >= -30.0 and combo_return >= c3_return), math.nan


def _run_window(
    window: Window,
    metadata: dict[str, Any],
    price_frame: pd.DataFrame,
    signals: pd.DataFrame,
) -> tuple[dict[str, Any], pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    c3_base_daily, _, c3_base_stats = _run_c3(window, C3_BASELINE_CAPITAL, "c3_baseline")
    c3_candidate_daily, c3_candidate_positions, c3_candidate_stats = _run_c3(
        window,
        C3_CANDIDATE_CAPITAL,
        "c3_candidate",
    )
    satellite = _run_satellite(window, price_frame, signals)
    combo_daily = _combine_candidate_daily(c3_candidate_daily, satellite)
    baseline_daily = _baseline_daily_from_c3(c3_base_daily)
    margin = _combine_margin(combo_daily, c3_candidate_positions, satellite, metadata)

    combo_metrics = _metrics_from_daily(combo_daily)
    baseline_metrics = _metrics_from_daily(baseline_daily)
    satellite_path = _satellite_metrics(satellite)
    margin_metrics = _margin_summary(margin)
    gate_ok, retention = _window_gate(
        baseline_metrics["total_return_pct"],
        combo_metrics["total_return_pct"],
        combo_metrics["max_dd_percent"],
    )
    row = {
        "window_name": window.name,
        "window_label": window.label,
        "window_group": window.group,
        "analysis_start": window.start.date().isoformat(),
        "analysis_end": window.end.date().isoformat(),
        "c3_500_return_pct": baseline_metrics["total_return_pct"],
        "c3_500_max_dd_pct": baseline_metrics["max_dd_percent"],
        "c3_500_sharpe": baseline_metrics["sharpe_ratio"],
        "c3_350_return_pct": _safe_float(c3_candidate_stats.get("total_return")),
        "c3_350_max_dd_pct": _safe_float(c3_candidate_stats.get("max_ddpercent")),
        "satellite_150_return_pct": satellite_path["total_return_pct"],
        "satellite_150_max_dd_pct": satellite_path["max_dd_percent"],
        "combo_end_balance": combo_metrics["end_balance"],
        "combo_return_pct": combo_metrics["total_return_pct"],
        "combo_max_dd_pct": combo_metrics["max_dd_percent"],
        "combo_sharpe": combo_metrics["sharpe_ratio"],
        "return_retention_vs_c3_500_pct": retention,
        "combo_trade_count": int(combo_daily["trade_count"].sum()) if not combo_daily.empty else 0,
        "c3_500_trade_count": int(_safe_float(c3_base_stats.get("total_trade_count"))),
        "c3_350_trade_count": int(_safe_float(c3_candidate_stats.get("total_trade_count"))),
        "satellite_turnover_contracts": int(satellite["satellite_turnover_contracts"].sum()) if not satellite.empty else 0,
        "satellite_total_slippage": float(satellite["satellite_slippage_cost"].sum()) if not satellite.empty else 0.0,
        "zero_position_days": int(satellite["zero_position_flag"].sum()) if not satellite.empty else 0,
        "active_signal_days": int((satellite["desired_signal_count"] > 0).sum()) if not satellite.empty else 0,
        "max_satellite_margin": float(satellite["satellite_margin"].max()) if not satellite.empty else 0.0,
        "max_required_min1_margin": float(satellite["required_min1_margin"].max()) if not satellite.empty else 0.0,
        "window_gate_ok": gate_ok,
        **margin_metrics,
    }
    combo_daily["window_name"] = window.name
    baseline_daily["window_name"] = window.name
    margin["window_name"] = window.name
    satellite["window_name"] = window.name
    return row, combo_daily, baseline_daily, margin, satellite


def _build_slippage_stress(combo_daily: pd.DataFrame, baseline_daily: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    full_combo = combo_daily[combo_daily["window_name"].eq("start_2020")].copy()
    full_baseline = baseline_daily[baseline_daily["window_name"].eq("start_2020")].copy()
    for multiplier in SLIPPAGE_MULTIPLIERS:
        c3_metrics = _stressed_metrics(full_baseline, "net_pnl", "slippage", multiplier)
        combo_metrics = _stressed_metrics(full_combo, "combo_net_pnl", "combo_slippage", multiplier)
        gate_ok, retention = _window_gate(
            c3_metrics["total_return_pct"],
            combo_metrics["total_return_pct"],
            combo_metrics["max_dd_percent"],
        )
        rows.append(
            {
                "slippage_multiplier": multiplier,
                "c3_500_return_pct": c3_metrics["total_return_pct"],
                "c3_500_max_dd_pct": c3_metrics["max_dd_percent"],
                "c3_500_total_slippage": c3_metrics["total_slippage"],
                "combo_return_pct": combo_metrics["total_return_pct"],
                "combo_max_dd_pct": combo_metrics["max_dd_percent"],
                "combo_sharpe": combo_metrics["sharpe_ratio"],
                "combo_total_slippage": combo_metrics["total_slippage"],
                "return_retention_vs_c3_500_pct": retention,
                "stress_gate_ok": gate_ok,
            }
        )
    return pd.DataFrame(rows)


def _decision(summary: pd.DataFrame, slippage: pd.DataFrame) -> str:
    if summary.empty:
        return "fail_no_result"
    positive_windows = summary[pd.to_numeric(summary["c3_500_return_pct"], errors="coerce") > 0]
    pass_windows = int(summary["window_gate_ok"].sum())
    strict_window_count = len(summary)
    stress_pass_3x = bool(
        not slippage.empty
        and bool(slippage.loc[slippage["slippage_multiplier"].eq(3.0), "stress_gate_ok"].fillna(0).astype(int).max())
    )
    positive_retention_min = (
        float(positive_windows["return_retention_vs_c3_500_pct"].min()) if not positive_windows.empty else math.nan
    )
    if pass_windows == strict_window_count and stress_pass_3x:
        return "promote_to_quarterly_validation"
    if pass_windows >= max(1, strict_window_count - 1) and positive_retention_min >= 75.0:
        return "research_candidate_watch_gap"
    return "fail_multiperiod_or_stress"


def _build_report(summary: pd.DataFrame, slippage: pd.DataFrame, decision: str) -> str:
    lines = [
        "# Stage049 C3 35万 + 横截面动量卫星15万多周期压力复验",
        "",
        "## 目标",
        "",
        "- 固定 Stage048 粗前沿候选：`C3 350,000 + xsmom卫星150,000`。",
        "- 卫星只采用 `min1_cheapest_cap`：低保证金信号优先，每个入选合约最多1手，总保证金不超过卫星资金。",
        "- 与 `50万C3` 在相同起点下比较收益保留和最大回撤；失败后不继续调 `35/15` 附近小数。",
        "",
        "## 多周期结果",
        "",
    ]
    summary_cols = [
        "window_name",
        "window_group",
        "c3_500_return_pct",
        "c3_500_max_dd_pct",
        "combo_return_pct",
        "return_retention_vs_c3_500_pct",
        "combo_max_dd_pct",
        "combo_sharpe",
        "max_margin_to_equity_pct",
        "review_days",
        "reject_days",
        "zero_position_days",
        "window_gate_ok",
    ]
    lines.append(_to_markdown_table(summary, summary_cols, max_rows=100))
    lines.extend(["", "## 滑点压力", ""])
    slip_cols = [
        "slippage_multiplier",
        "c3_500_return_pct",
        "c3_500_max_dd_pct",
        "combo_return_pct",
        "return_retention_vs_c3_500_pct",
        "combo_max_dd_pct",
        "combo_sharpe",
        "stress_gate_ok",
    ]
    lines.append(_to_markdown_table(slippage, slip_cols, max_rows=100))
    lines.extend(["", "## 阶段判断", ""])
    lines.append(f"- 决策标签：`{decision}`。")
    if decision == "promote_to_quarterly_validation":
        lines.append("- 多周期和3倍滑点压力均通过，下一步进入季度冷启动和更细保证金压力。")
    elif decision == "research_candidate_watch_gap":
        lines.append("- 候选仍有研究价值，但存在窗口或滑点缺口，不能合入正式78-1。")
    else:
        lines.append("- 候选未通过多周期或压力复验，不能晋级；停止围绕该资金比例继续微调。")
    lines.extend(
        [
            "",
            "## 过拟合反思",
            "",
            "- 本阶段固定 Stage048 候选，只做多起点和成本反证；如果失败，不继续调资金小数、信号篮子数量或单品种名单。",
            "",
            "## 继续价值反思",
            "",
            "- 若通过，横截面动量可以进入更深季度冷启动；若失败，说明当前承载方式仍不足，应回到更独立收益源或承认C3自然回撤边界。",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    metadata = _metadata()
    price_frame = _build_price_frame()
    signals = _load_signal_daily()

    rows: list[dict[str, Any]] = []
    combo_frames: list[pd.DataFrame] = []
    baseline_frames: list[pd.DataFrame] = []
    margin_frames: list[pd.DataFrame] = []
    satellite_frames: list[pd.DataFrame] = []

    for window in WINDOWS:
        row, combo_daily, baseline_daily, margin, satellite = _run_window(window, metadata, price_frame, signals)
        rows.append(row)
        combo_frames.append(combo_daily)
        baseline_frames.append(baseline_daily)
        margin_frames.append(margin)
        satellite_frames.append(satellite)

    summary_df = pd.DataFrame(rows)
    combo_daily_df = pd.concat(combo_frames, ignore_index=True) if combo_frames else pd.DataFrame()
    baseline_daily_df = pd.concat(baseline_frames, ignore_index=True) if baseline_frames else pd.DataFrame()
    margin_df = pd.concat(margin_frames, ignore_index=True) if margin_frames else pd.DataFrame()
    satellite_df = pd.concat(satellite_frames, ignore_index=True) if satellite_frames else pd.DataFrame()
    slippage_df = _build_slippage_stress(combo_daily_df, baseline_daily_df)
    decision_tag = _decision(summary_df, slippage_df)

    summary_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
    combo_daily_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_combo_daily_{MODEL_TAG}.csv"
    baseline_daily_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_baseline_daily_{MODEL_TAG}.csv"
    margin_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_margin_{MODEL_TAG}.csv"
    satellite_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_satellite_daily_{MODEL_TAG}.csv"
    slippage_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_slippage_stress_{MODEL_TAG}.csv"
    report_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
    decision_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

    summary_df.to_csv(summary_path, index=False, encoding="utf-8-sig")
    combo_daily_df.to_csv(combo_daily_path, index=False, encoding="utf-8-sig")
    baseline_daily_df.to_csv(baseline_daily_path, index=False, encoding="utf-8-sig")
    margin_df.to_csv(margin_path, index=False, encoding="utf-8-sig")
    satellite_df.to_csv(satellite_path, index=False, encoding="utf-8-sig")
    slippage_df.to_csv(slippage_path, index=False, encoding="utf-8-sig")
    report_path.write_text(_build_report(summary_df, slippage_df, decision_tag), encoding="utf-8")

    decision = {
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "official_version": OFFICIAL_STAGE78_VERSION,
        "official_role": OFFICIAL_STAGE78_ROLE,
        "total_capital": TOTAL_CAPITAL,
        "c3_baseline_capital": C3_BASELINE_CAPITAL,
        "c3_candidate_capital": C3_CANDIDATE_CAPITAL,
        "satellite_capital": SATELLITE_CAPITAL,
        "satellite_profile": SATELLITE_PROFILE.name,
        "margin_review_pct": MARGIN_REVIEW_PCT,
        "margin_reject_pct": MARGIN_REJECT_PCT,
        "decision": decision_tag,
        "summary": summary_df.to_dict(orient="records"),
        "slippage_stress": slippage_df.to_dict(orient="records"),
        "paths": {
            "summary": str(summary_path),
            "combo_daily": str(combo_daily_path),
            "baseline_daily": str(baseline_daily_path),
            "margin": str(margin_path),
            "satellite_daily": str(satellite_path),
            "slippage_stress": str(slippage_path),
            "report": str(report_path),
        },
    }
    decision_path.write_text(json.dumps(_to_builtin(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[stage349] summary={summary_path}")
    print(f"[stage349] combo_daily={combo_daily_path}")
    print(f"[stage349] baseline_daily={baseline_daily_path}")
    print(f"[stage349] margin={margin_path}")
    print(f"[stage349] satellite_daily={satellite_path}")
    print(f"[stage349] slippage_stress={slippage_path}")
    print(f"[stage349] report={report_path}")
    print(f"[stage349] decision={decision_path}")
    print(report_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
