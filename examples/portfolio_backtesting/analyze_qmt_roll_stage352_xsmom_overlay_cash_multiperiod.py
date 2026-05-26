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
    MARGIN_WATCH_PCT,
    TOTAL_CAPITAL,
    _c3_overrides,
    _margin_daily,
    _metadata,
    _safe_float,
    _to_builtin,
    _to_markdown_table,
)
from analyze_qmt_roll_stage346_xsmom_integer_feasibility import (
    Profile,
    _build_price_frame,
    _load_signal_daily,
    _simulate_profile,
)
from qmt_roll_official_stage78_config import OFFICIAL_STAGE78_ROLE, OFFICIAL_STAGE78_VERSION
from qmt_universe import END_DT, PRELOAD_START_DT, START_DT
from run_qmt_alignment_backtest import OUTPUT_DIR, build_positions_df
from run_qmt_roll_backtest import run_backtest as run_roll_backtest
from run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest import BASE_RISK_RATIO


MODEL_TAG = "stage352_xsmom_overlay_cash_multiperiod_v1"
OUTPUT_PREFIX = "qmt_roll_stage352_xsmom_overlay_cash_multiperiod"
LINE_ID = "futures_trend_drawdown30_preserve_return"

C3_CAPITAL = 500_000.0
CASH_BUFFER = 30_000.0
ACCOUNT_CAPITAL = C3_CAPITAL + CASH_BUFFER
TARGET_MAX_DD_PCT = -30.0
RETURN_RETENTION_GATE_PCT = 80.0
SLIPPAGE_MULTIPLIERS: tuple[float, ...] = (1.0, 2.0, 3.0)
XSMOM_PROFILE = Profile(
    "min1_all_no_cap",
    "全部信号最低1手，不设卫星保证金上限",
    "min1_all",
    None,
)


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


def _series_metrics(balance: pd.Series, start_capital: float) -> dict[str, float]:
    values = pd.to_numeric(balance, errors="coerce").ffill().fillna(start_capital).to_numpy(dtype=float)
    if len(values) == 0:
        return {
            "end_balance": start_capital,
            "total_return_pct": 0.0,
            "max_dd_percent": 0.0,
            "sharpe_ratio": 0.0,
        }
    high = np.maximum.accumulate(values)
    dd_pct = np.divide(values - high, high, out=np.zeros_like(values), where=high != 0.0) * 100.0
    returns = pd.Series(values).pct_change().fillna(0.0).to_numpy(dtype=float)
    std = float(np.std(returns, ddof=1)) if len(returns) > 1 else 0.0
    sharpe = float(np.mean(returns) / std * np.sqrt(252.0)) if std > 0 else 0.0
    return {
        "end_balance": float(values[-1]),
        "total_return_pct": float((values[-1] / start_capital - 1.0) * 100.0),
        "max_dd_percent": float(dd_pct.min()),
        "sharpe_ratio": sharpe,
    }


def _daily_from_analysis(analysis_df: pd.DataFrame | None) -> pd.DataFrame:
    if analysis_df is None or analysis_df.empty:
        return pd.DataFrame(columns=["date", "c3_balance", "c3_net_pnl", "c3_trade_count", "c3_slippage"])
    frame = analysis_df.copy().reset_index().rename(columns={"index": "date"})
    frame["date"] = pd.to_datetime(frame["date"]).dt.normalize()
    frame = frame.sort_values("date").drop_duplicates("date", keep="last")
    frame["c3_balance"] = pd.to_numeric(frame.get("balance", C3_CAPITAL), errors="coerce").ffill().fillna(C3_CAPITAL)
    frame["c3_net_pnl"] = pd.to_numeric(frame.get("net_pnl", 0.0), errors="coerce").fillna(0.0)
    frame["c3_trade_count"] = pd.to_numeric(frame.get("trade_count", 0.0), errors="coerce").fillna(0.0)
    frame["c3_slippage"] = pd.to_numeric(frame.get("slippage", 0.0), errors="coerce").fillna(0.0)
    return frame[["date", "c3_balance", "c3_net_pnl", "c3_trade_count", "c3_slippage"]]


def _run_c3(window: Window) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    preload_start = max(PRELOAD_START_DT, window.start - timedelta(days=365))
    print(f"[stage352] run C3 {window.name} capital={C3_CAPITAL:.0f}", flush=True)
    engine, analysis_df, statistics = run_roll_backtest(
        risk_ratio=BASE_RISK_RATIO,
        strategy_overrides=_c3_overrides(window.start),
        analysis_start=window.start,
        analysis_end=window.end,
        preload_start=preload_start,
        capital=C3_CAPITAL,
        save_artifacts=False,
        include_start_year_sweep=False,
        file_prefix=f"{OUTPUT_PREFIX}_c3_{window.name}",
        chart_title=f"Stage352 C3 {window.label}",
    )
    return _daily_from_analysis(analysis_df), build_positions_df(engine), statistics


def _simulate_xsmom(window: Window, price_frame: pd.DataFrame, signals: pd.DataFrame) -> pd.DataFrame:
    print(f"[stage352] simulate xsmom overlay {window.name}", flush=True)
    start = pd.Timestamp(window.start).normalize()
    end = pd.Timestamp(window.end).normalize()
    window_prices = price_frame[price_frame["date"].between(start, end)].copy()
    window_signals = signals[signals["date"].between(start, end)].copy()
    if window_signals.empty:
        return pd.DataFrame(
            columns=[
                "date",
                "daily_pnl",
                "slippage_cost",
                "actual_margin",
                "turnover_contracts",
                "desired_signal_count",
                "held_contract_count",
                "zero_position_flag",
                "required_min1_margin",
            ]
        )
    return _simulate_profile(XSMOM_PROFILE, window_prices, window_signals)


def _combine_daily(c3_daily: pd.DataFrame, xsmom_daily: pd.DataFrame) -> pd.DataFrame:
    dates = sorted(set(c3_daily["date"]).union(set(xsmom_daily["date"])))
    if not dates:
        return pd.DataFrame()
    merged = pd.DataFrame({"date": pd.to_datetime(dates)})
    merged = merged.merge(c3_daily, on="date", how="left")
    merged = merged.merge(
        xsmom_daily[
            [
                "date",
                "daily_pnl",
                "slippage_cost",
                "actual_margin",
                "turnover_contracts",
                "desired_signal_count",
                "held_contract_count",
                "zero_position_flag",
                "required_min1_margin",
            ]
        ],
        on="date",
        how="left",
    )
    for column in [
        "c3_net_pnl",
        "c3_trade_count",
        "c3_slippage",
        "daily_pnl",
        "slippage_cost",
        "actual_margin",
        "turnover_contracts",
        "desired_signal_count",
        "held_contract_count",
        "zero_position_flag",
        "required_min1_margin",
    ]:
        merged[column] = pd.to_numeric(merged.get(column, 0.0), errors="coerce").fillna(0.0)
    merged["combo_net_pnl"] = merged["c3_net_pnl"] + merged["daily_pnl"]
    merged["combo_slippage"] = merged["c3_slippage"] + merged["slippage_cost"]
    merged["c3_only_balance"] = C3_CAPITAL + merged["c3_net_pnl"].cumsum()
    merged["base_without_cash_balance"] = C3_CAPITAL + merged["combo_net_pnl"].cumsum()
    merged["account_balance"] = ACCOUNT_CAPITAL + merged["combo_net_pnl"].cumsum()
    merged["trade_count"] = merged["c3_trade_count"] + merged["turnover_contracts"]
    return merged


def _combine_margin(combo_daily: pd.DataFrame, c3_positions: pd.DataFrame, metadata: dict[str, Any]) -> pd.DataFrame:
    if combo_daily.empty:
        return pd.DataFrame()
    margin = combo_daily[["date", "account_balance", "actual_margin", "held_contract_count"]].copy()
    margin = margin.merge(_margin_daily(c3_positions, metadata, "c3"), on="date", how="left")
    for column in ["c3_margin", "c3_active_contracts", "c3_active_products", "actual_margin", "held_contract_count"]:
        margin[column] = pd.to_numeric(margin.get(column, 0.0), errors="coerce").fillna(0.0)
    margin["satellite_margin"] = margin["actual_margin"]
    margin["satellite_active_contracts"] = margin["held_contract_count"]
    margin["satellite_active_products"] = margin["held_contract_count"].clip(upper=6)
    margin["total_margin"] = margin["c3_margin"] + margin["satellite_margin"]
    margin["total_active_contracts"] = margin["c3_active_contracts"] + margin["satellite_active_contracts"]
    margin["total_active_products"] = margin["c3_active_products"] + margin["satellite_active_products"]
    margin["margin_to_equity_pct"] = (
        margin["total_margin"] / margin["account_balance"].replace(0.0, np.nan) * 100.0
    ).fillna(0.0)
    return margin


def _margin_stats(margin: pd.DataFrame, balance_column: str = "account_balance") -> dict[str, Any]:
    if margin.empty:
        return {
            "max_margin_to_equity_pct": 0.0,
            "p95_margin_to_equity_pct": 0.0,
            "watch_days": 0,
            "review_days": 0,
            "reject_days": 0,
            "max_active_contracts": 0,
            "max_active_products": 0,
        }
    view = margin.copy()
    view["margin_to_equity_pct"] = (
        view["total_margin"] / pd.to_numeric(view[balance_column], errors="coerce").replace(0.0, np.nan) * 100.0
    ).fillna(0.0)
    max_idx = int(view["margin_to_equity_pct"].idxmax())
    max_row = view.loc[max_idx]
    return {
        "max_margin_date": str(pd.to_datetime(max_row["date"]).date()),
        "max_margin": _safe_float(max_row["total_margin"]),
        "max_margin_to_equity_pct": _safe_float(max_row["margin_to_equity_pct"]),
        "p95_margin_to_equity_pct": _safe_float(view["margin_to_equity_pct"].quantile(0.95)),
        "watch_days": int((view["margin_to_equity_pct"] >= MARGIN_WATCH_PCT).sum()),
        "review_days": int((view["margin_to_equity_pct"] >= MARGIN_REVIEW_PCT).sum()),
        "reject_days": int((view["margin_to_equity_pct"] >= MARGIN_REJECT_PCT).sum()),
        "max_active_contracts": int(view["total_active_contracts"].max()),
        "max_active_products": int(view["total_active_products"].max()),
    }


def _gate(c3_return: float, candidate_return: float, candidate_dd: float, reject_days: int) -> tuple[int, float]:
    if c3_return > 0:
        retention = candidate_return / c3_return * 100.0
        return int(candidate_dd >= TARGET_MAX_DD_PCT and retention >= RETURN_RETENTION_GATE_PCT and reject_days == 0), retention
    retention = math.nan
    return int(candidate_dd >= TARGET_MAX_DD_PCT and candidate_return >= c3_return and reject_days == 0), retention


def _run_window(
    window: Window,
    metadata: dict[str, Any],
    price_frame: pd.DataFrame,
    signals: pd.DataFrame,
) -> tuple[dict[str, Any], pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    c3_daily, c3_positions, c3_stats = _run_c3(window)
    xsmom_daily = _simulate_xsmom(window, price_frame, signals)
    combo_daily = _combine_daily(c3_daily, xsmom_daily)
    margin = _combine_margin(combo_daily, c3_positions, metadata)

    c3_metrics = _series_metrics(combo_daily["c3_only_balance"], C3_CAPITAL)
    candidate_metrics = _series_metrics(combo_daily["account_balance"], ACCOUNT_CAPITAL)
    margin_metrics = _margin_stats(margin)
    gate_ok, retention = _gate(
        c3_metrics["total_return_pct"],
        candidate_metrics["total_return_pct"],
        candidate_metrics["max_dd_percent"],
        int(margin_metrics["reject_days"]),
    )
    row = {
        "window_name": window.name,
        "window_label": window.label,
        "window_group": window.group,
        "analysis_start": window.start.date().isoformat(),
        "analysis_end": window.end.date().isoformat(),
        "c3_return_pct": c3_metrics["total_return_pct"],
        "c3_max_dd_pct": c3_metrics["max_dd_percent"],
        "c3_sharpe": c3_metrics["sharpe_ratio"],
        "candidate_end_balance": candidate_metrics["end_balance"],
        "candidate_return_pct": candidate_metrics["total_return_pct"],
        "candidate_max_dd_pct": candidate_metrics["max_dd_percent"],
        "candidate_sharpe": candidate_metrics["sharpe_ratio"],
        "return_retention_vs_c3_pct": retention,
        "c3_trade_count": int(_safe_float(c3_stats.get("total_trade_count"))),
        "xsmom_turnover_contracts": int(combo_daily["turnover_contracts"].sum()) if not combo_daily.empty else 0,
        "combo_trade_count": int(combo_daily["trade_count"].sum()) if not combo_daily.empty else 0,
        "combo_total_slippage": float(combo_daily["combo_slippage"].sum()) if not combo_daily.empty else 0.0,
        "xsmom_total_pnl": float(combo_daily["daily_pnl"].sum()) if not combo_daily.empty else 0.0,
        "xsmom_total_slippage": float(combo_daily["slippage_cost"].sum()) if not combo_daily.empty else 0.0,
        "max_xsmom_margin": float(combo_daily["actual_margin"].max()) if not combo_daily.empty else 0.0,
        "max_required_min1_margin": float(combo_daily["required_min1_margin"].max()) if not combo_daily.empty else 0.0,
        "zero_position_days": int(combo_daily["zero_position_flag"].sum()) if not combo_daily.empty else 0,
        "active_signal_days": int((combo_daily["desired_signal_count"] > 0).sum()) if not combo_daily.empty else 0,
        "window_gate_ok": gate_ok,
        **margin_metrics,
    }
    combo_daily["window_name"] = window.name
    margin["window_name"] = window.name
    xsmom_daily["window_name"] = window.name
    return row, combo_daily, margin, xsmom_daily


def _stress_rows(summary_daily: pd.DataFrame, margin_daily: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for window_name, daily in summary_daily.groupby("window_name", sort=False):
        margin = margin_daily[margin_daily["window_name"].eq(window_name)].copy()
        for multiplier in SLIPPAGE_MULTIPLIERS:
            view = daily.sort_values("date").copy()
            view["c3_stressed_pnl"] = view["c3_net_pnl"] - (multiplier - 1.0) * view["c3_slippage"]
            view["combo_stressed_pnl"] = view["combo_net_pnl"] - (multiplier - 1.0) * view["combo_slippage"]
            view["c3_stressed_balance"] = C3_CAPITAL + view["c3_stressed_pnl"].cumsum()
            view["candidate_stressed_balance"] = ACCOUNT_CAPITAL + view["combo_stressed_pnl"].cumsum()
            c3_metrics = _series_metrics(view["c3_stressed_balance"], C3_CAPITAL)
            candidate_metrics = _series_metrics(view["candidate_stressed_balance"], ACCOUNT_CAPITAL)
            stress_margin = margin.merge(
                view[["date", "candidate_stressed_balance"]],
                on="date",
                how="left",
            )
            margin_metrics = _margin_stats(stress_margin, "candidate_stressed_balance")
            gate_ok, retention = _gate(
                c3_metrics["total_return_pct"],
                candidate_metrics["total_return_pct"],
                candidate_metrics["max_dd_percent"],
                int(margin_metrics["reject_days"]),
            )
            rows.append(
                {
                    "window_name": window_name,
                    "slippage_multiplier": multiplier,
                    "c3_return_pct": c3_metrics["total_return_pct"],
                    "c3_max_dd_pct": c3_metrics["max_dd_percent"],
                    "candidate_return_pct": candidate_metrics["total_return_pct"],
                    "return_retention_vs_c3_pct": retention,
                    "candidate_max_dd_pct": candidate_metrics["max_dd_percent"],
                    "candidate_sharpe": candidate_metrics["sharpe_ratio"],
                    "max_margin_to_equity_pct": margin_metrics["max_margin_to_equity_pct"],
                    "reject_days": margin_metrics["reject_days"],
                    "stress_gate_ok": gate_ok,
                }
            )
    return pd.DataFrame(rows)


def _decision(summary: pd.DataFrame, stress: pd.DataFrame) -> str:
    if summary.empty:
        return "fail_no_result"
    all_windows_pass = int(summary["window_gate_ok"].sum()) == len(summary)
    positive_windows = summary[pd.to_numeric(summary["c3_return_pct"], errors="coerce") > 0]
    min_retention = float(positive_windows["return_retention_vs_c3_pct"].min()) if not positive_windows.empty else math.nan
    stress_1x_all = int(stress[stress["slippage_multiplier"].eq(1.0)]["stress_gate_ok"].sum()) == len(summary)
    stress_2x_all = int(stress[stress["slippage_multiplier"].eq(2.0)]["stress_gate_ok"].sum()) == len(summary)
    stress_3x_all = int(stress[stress["slippage_multiplier"].eq(3.0)]["stress_gate_ok"].sum()) == len(summary)
    if all_windows_pass and stress_3x_all:
        return "promote_to_quarterly_validation"
    if all_windows_pass and stress_2x_all:
        return "candidate_normal_and_2x_cost_requires_quarterly"
    if all_windows_pass and stress_1x_all and min_retention >= 75.0:
        return "candidate_normal_cost_only"
    return "fail_multiperiod_or_stress"


def _build_report(summary: pd.DataFrame, stress: pd.DataFrame, decision: str) -> str:
    summary_cols = [
        "window_name",
        "window_group",
        "c3_return_pct",
        "c3_max_dd_pct",
        "candidate_return_pct",
        "return_retention_vs_c3_pct",
        "candidate_max_dd_pct",
        "candidate_sharpe",
        "max_margin_to_equity_pct",
        "review_days",
        "reject_days",
        "window_gate_ok",
    ]
    stress_cols = [
        "window_name",
        "slippage_multiplier",
        "c3_return_pct",
        "candidate_return_pct",
        "return_retention_vs_c3_pct",
        "candidate_max_dd_pct",
        "max_margin_to_equity_pct",
        "reject_days",
        "stress_gate_ok",
    ]
    return "\n".join(
        [
            "# Stage052 C3原路径 + xsmom overlay + 3万外部现金多周期复验",
            "",
            "## 目标",
            "",
            "- 固定 Stage051 唯一线索：C3 50万原交易路径 + 横截面动量 `min1_all_no_cap` overlay + 3万外部现金。",
            "- C3 每个起点重新跑真实回测引擎；xsmom 以既有整数手数执行模拟重新从窗口起点建仓。",
            "- 通过条件：候选最大回撤进30以内、相对同窗口 C3 收益保留80%以上、保证金不触发100%拒绝线。",
            "",
            "## 多周期结果",
            "",
            _to_markdown_table(summary, summary_cols, max_rows=100),
            "",
            "## 滑点压力",
            "",
            _to_markdown_table(stress, stress_cols, max_rows=200),
            "",
            "## 阶段判断",
            "",
            f"- 决策标签：`{decision}`。",
            "- 若失败，不继续调 `3万` 附近现金或 xsmom 执行细节；若只在正常成本通过，也只能作为正常成本候选。",
            "",
            "## 过拟合反思",
            "",
            "- 本阶段固定候选做反证，不新增参数搜索；失败后继续救小数会过拟合。",
            "",
            "## 继续价值反思",
            "",
            "- 若多周期通过，继续做季度冷启动；若多周期或滑点失败，该 overlay 承载方式应停止。",
        ]
    ) + "\n"


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    metadata = _metadata()
    price_frame = _build_price_frame()
    signals = _load_signal_daily()

    rows: list[dict[str, Any]] = []
    combo_frames: list[pd.DataFrame] = []
    margin_frames: list[pd.DataFrame] = []
    xsmom_frames: list[pd.DataFrame] = []
    for window in WINDOWS:
        row, combo_daily, margin_daily, xsmom_daily = _run_window(window, metadata, price_frame, signals)
        rows.append(row)
        combo_frames.append(combo_daily)
        margin_frames.append(margin_daily)
        xsmom_frames.append(xsmom_daily)

    summary = pd.DataFrame(rows)
    combo_daily_df = pd.concat(combo_frames, ignore_index=True) if combo_frames else pd.DataFrame()
    margin_df = pd.concat(margin_frames, ignore_index=True) if margin_frames else pd.DataFrame()
    xsmom_df = pd.concat(xsmom_frames, ignore_index=True) if xsmom_frames else pd.DataFrame()
    stress = _stress_rows(combo_daily_df, margin_df)
    decision_tag = _decision(summary, stress)

    summary_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
    combo_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_combo_daily_{MODEL_TAG}.csv"
    margin_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_margin_{MODEL_TAG}.csv"
    xsmom_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_xsmom_daily_{MODEL_TAG}.csv"
    stress_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_slippage_stress_{MODEL_TAG}.csv"
    report_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
    decision_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

    summary.to_csv(summary_path, index=False, encoding="utf-8-sig")
    combo_daily_df.to_csv(combo_path, index=False, encoding="utf-8-sig")
    margin_df.to_csv(margin_path, index=False, encoding="utf-8-sig")
    xsmom_df.to_csv(xsmom_path, index=False, encoding="utf-8-sig")
    stress.to_csv(stress_path, index=False, encoding="utf-8-sig")
    report_path.write_text(_build_report(summary, stress, decision_tag), encoding="utf-8")
    decision = {
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "official_version": OFFICIAL_STAGE78_VERSION,
        "official_role": OFFICIAL_STAGE78_ROLE,
        "c3_capital": C3_CAPITAL,
        "cash_buffer": CASH_BUFFER,
        "account_capital": ACCOUNT_CAPITAL,
        "xsmom_profile": XSMOM_PROFILE.name,
        "decision": decision_tag,
        "summary": summary.to_dict(orient="records"),
        "slippage_stress": stress.to_dict(orient="records"),
        "paths": {
            "summary": str(summary_path),
            "combo_daily": str(combo_path),
            "margin": str(margin_path),
            "xsmom_daily": str(xsmom_path),
            "slippage_stress": str(stress_path),
            "report": str(report_path),
        },
    }
    decision_path.write_text(json.dumps(_to_builtin(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[stage352] summary={summary_path}")
    print(f"[stage352] combo_daily={combo_path}")
    print(f"[stage352] margin={margin_path}")
    print(f"[stage352] xsmom_daily={xsmom_path}")
    print(f"[stage352] slippage_stress={stress_path}")
    print(f"[stage352] report={report_path}")
    print(f"[stage352] decision={decision_path}")
    print(json.dumps(_to_builtin({"decision": decision_tag, "summary": summary.to_dict(orient="records")}), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
