from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Callable

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
    _path_metrics,
    _safe_float,
    _to_builtin,
    _to_markdown_table,
)
from qmt_roll_official_stage78_config import OFFICIAL_STAGE78_ROLE, OFFICIAL_STAGE78_VERSION
from qmt_universe import END_DT, PRELOAD_START_DT, START_DT
from run_qmt_alignment_backtest import OUTPUT_DIR, build_positions_df
from run_qmt_roll_backtest import run_backtest as run_roll_backtest
from run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest import BASE_RISK_RATIO


MODEL_TAG = "stage327_c3_margin_concentration_overlay_probe_v1"
OUTPUT_PREFIX = "qmt_roll_stage327_c3_margin_concentration_overlay_probe"
LINE_ID = "futures_trend_drawdown30_preserve_return"


@dataclass(frozen=True)
class Overlay:
    name: str
    label: str
    rule: Callable[[pd.DataFrame], pd.Series]
    note: str


@dataclass(frozen=True)
class Window:
    name: str
    label: str
    start: datetime
    end: datetime


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


def _linear_floor(value: pd.Series, soft: float, hard: float, floor: float) -> pd.Series:
    value = pd.to_numeric(value, errors="coerce").fillna(0.0)
    weight = pd.Series(1.0, index=value.index)
    middle = (value > soft) & (value < hard)
    weight.loc[middle] = 1.0 - (value.loc[middle] - soft) / (hard - soft) * (1.0 - floor)
    weight.loc[value >= hard] = floor
    return weight.clip(lower=floor, upper=1.0)


def _active_floor(value: pd.Series, soft: float, hard: float, floor: float) -> pd.Series:
    return _linear_floor(value, soft, hard, floor)


def _combined_margin_active(frame: pd.DataFrame) -> pd.Series:
    risk = (
        (pd.to_numeric(frame["prev_margin_to_equity_pct"], errors="coerce").fillna(0.0) >= MARGIN_REVIEW_PCT)
        & (pd.to_numeric(frame["prev_active_products"], errors="coerce").fillna(0.0) >= 7)
    )
    return pd.Series(np.where(risk, 0.80, 1.0), index=frame.index)


OVERLAYS: tuple[Overlay, ...] = (
    Overlay(
        "A_c3_no_overlay",
        "A：C3原始路径",
        lambda frame: pd.Series(1.0, index=frame.index),
        "不做覆盖层，只作为对照。",
    ),
    Overlay(
        "C_margin_soft_60_80_floor085",
        "C：保证金60-80线性降到0.85",
        lambda frame: _linear_floor(frame["prev_margin_to_equity_pct"], MARGIN_WATCH_PCT, MARGIN_REVIEW_PCT, 0.85),
        "沿用日常SOP的60%观察线和80%复核线，避免按结果挑阈值。",
    ),
    Overlay(
        "C_margin_soft_70_90_floor080",
        "C：保证金70-90线性降到0.80",
        lambda frame: _linear_floor(frame["prev_margin_to_equity_pct"], 70.0, 90.0, 0.80),
        "比SOP更宽的保证金风险预算，仅做粗档位对照。",
    ),
    Overlay(
        "C_margin_review80_floor075",
        "C：超过80复核线降到0.75",
        lambda frame: pd.Series(
            np.where(pd.to_numeric(frame["prev_margin_to_equity_pct"], errors="coerce").fillna(0.0) >= MARGIN_REVIEW_PCT, 0.75, 1.0),
            index=frame.index,
        ),
        "只在上一交易日超过80%复核线后统一降暴露。",
    ),
    Overlay(
        "C_active_products_6_8_floor085",
        "C：持仓品种6-8线性降到0.85",
        lambda frame: _active_floor(frame["prev_active_products"], 6.0, 8.0, 0.85),
        "用持仓广度衡量拥挤，不绑定任何单一品种。",
    ),
    Overlay(
        "C_margin80_active7_floor080",
        "C：保证金80且品种>=7降到0.80",
        _combined_margin_active,
        "只有保证金和持仓广度同时偏高时才触发，避免过度空仓化。",
    ),
)


def _daily_from_analysis_with_cost(analysis_df: pd.DataFrame | None) -> pd.DataFrame:
    if analysis_df is None or analysis_df.empty:
        return pd.DataFrame(columns=["date", "balance", "net_pnl", "trade_count", "slippage", "commission"])
    frame = analysis_df.copy().reset_index().rename(columns={"index": "date"})
    frame["date"] = pd.to_datetime(frame["date"]).dt.normalize()
    frame = frame.sort_values("date").drop_duplicates("date", keep="last")
    frame["balance"] = pd.to_numeric(frame.get("balance", TOTAL_CAPITAL), errors="coerce").ffill().fillna(TOTAL_CAPITAL)
    for column in ["net_pnl", "trade_count", "slippage", "commission"]:
        frame[column] = pd.to_numeric(frame.get(column, 0.0), errors="coerce").fillna(0.0)
    return frame[["date", "balance", "net_pnl", "trade_count", "slippage", "commission"]]


def _run_c3() -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    preload_start = max(PRELOAD_START_DT, START_DT - timedelta(days=365))
    print("[stage327] run C3 full-sample 50w", flush=True)
    engine, analysis_df, statistics = run_roll_backtest(
        risk_ratio=BASE_RISK_RATIO,
        strategy_overrides=_c3_overrides(START_DT),
        analysis_start=START_DT,
        analysis_end=END_DT,
        preload_start=preload_start,
        capital=TOTAL_CAPITAL,
        save_artifacts=False,
        include_start_year_sweep=False,
        file_prefix=f"{OUTPUT_PREFIX}_c3_base",
        chart_title="Stage327 C3 margin concentration probe",
    )
    daily = _daily_from_analysis_with_cost(analysis_df)
    positions = build_positions_df(engine)
    return daily, positions, statistics


def _enrich_daily(daily: pd.DataFrame, positions: pd.DataFrame) -> pd.DataFrame:
    metadata = _metadata()
    margin = _margin_daily(positions, metadata, "c3")
    frame = daily.copy().merge(margin, on="date", how="left")
    for column in ["c3_margin", "c3_active_contracts", "c3_active_products"]:
        frame[column] = pd.to_numeric(frame.get(column, 0.0), errors="coerce").fillna(0.0)
    frame["margin_to_equity_pct"] = frame["c3_margin"] / frame["balance"].replace(0.0, np.nan) * 100.0
    frame["margin_to_equity_pct"] = frame["margin_to_equity_pct"].fillna(0.0)
    frame["margin_to_initial_capital_pct"] = frame["c3_margin"] / TOTAL_CAPITAL * 100.0
    frame["highlevel"] = frame["balance"].cummax()
    frame["ddpercent"] = ((frame["balance"] - frame["highlevel"]) / frame["highlevel"].replace(0.0, np.nan) * 100.0).fillna(0.0)
    frame["prev_margin_to_equity_pct"] = frame["margin_to_equity_pct"].shift(1).fillna(0.0)
    frame["prev_active_products"] = frame["c3_active_products"].shift(1).fillna(0.0)
    frame["prev_active_contracts"] = frame["c3_active_contracts"].shift(1).fillna(0.0)
    frame["prev_ddpercent"] = frame["ddpercent"].shift(1).fillna(0.0)
    return frame


def _overlay_path(enriched: pd.DataFrame, overlay: Overlay) -> pd.DataFrame:
    frame = enriched[["date", "net_pnl", "trade_count", "slippage", "commission"]].copy()
    weight = overlay.rule(enriched).astype(float).clip(lower=0.0, upper=1.0)
    frame["overlay_name"] = overlay.name
    frame["weight"] = weight
    frame["overlay_net_pnl"] = frame["net_pnl"] * frame["weight"]
    frame["overlay_slippage"] = frame["slippage"] * frame["weight"]
    frame["overlay_commission"] = frame["commission"] * frame["weight"]
    frame["balance"] = TOTAL_CAPITAL + frame["overlay_net_pnl"].cumsum()
    frame["highlevel"] = frame["balance"].cummax()
    frame["ddpercent"] = ((frame["balance"] - frame["highlevel"]) / frame["highlevel"].replace(0.0, np.nan) * 100.0).fillna(0.0)
    frame["weighted_trade_count"] = frame["trade_count"] * frame["weight"]
    frame["weight_lt_1"] = (frame["weight"] < 0.9999).astype(int)
    return frame


def _slice_window(path: pd.DataFrame, window: Window) -> pd.DataFrame:
    frame = path[(path["date"] >= pd.Timestamp(window.start)) & (path["date"] <= pd.Timestamp(window.end))].copy()
    if frame.empty:
        return frame
    base_balance = max(abs(float(frame["balance"].iloc[0])), 1e-9)
    frame["rebased_balance"] = frame["balance"] / base_balance * TOTAL_CAPITAL
    return frame


def _metrics_for_window(path: pd.DataFrame, window: Window, balance_column: str = "rebased_balance") -> dict[str, Any]:
    frame = _slice_window(path, window)
    if frame.empty:
        return {
            "window_name": window.name,
            "window_label": window.label,
            "total_return_pct": 0.0,
            "max_dd_percent": 0.0,
            "sharpe_ratio": 0.0,
            "end_balance": TOTAL_CAPITAL,
            "total_slippage": 0.0,
            "total_commission": 0.0,
            "total_trade_count_weighted": 0.0,
            "weight_lt_1_days": 0,
            "avg_weight": 1.0,
        }
    metric_frame = frame[["date", balance_column]].copy().rename(columns={balance_column: "balance"})
    metrics = _path_metrics(metric_frame, TOTAL_CAPITAL)
    return {
        "window_name": window.name,
        "window_label": window.label,
        **metrics,
        "total_slippage": float(pd.to_numeric(frame.get("overlay_slippage", 0.0), errors="coerce").fillna(0.0).sum()),
        "total_commission": float(pd.to_numeric(frame.get("overlay_commission", 0.0), errors="coerce").fillna(0.0).sum()),
        "total_trade_count_weighted": float(pd.to_numeric(frame.get("weighted_trade_count", 0.0), errors="coerce").fillna(0.0).sum()),
        "weight_lt_1_days": int(pd.to_numeric(frame.get("weight_lt_1", 0.0), errors="coerce").fillna(0.0).sum()),
        "avg_weight": float(pd.to_numeric(frame.get("weight", 1.0), errors="coerce").fillna(1.0).mean()),
    }


def _build_overlay_summary(enriched: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    all_paths: list[pd.DataFrame] = []
    rows: list[dict[str, Any]] = []
    for overlay in OVERLAYS:
        path = _overlay_path(enriched, overlay)
        all_paths.append(path)
        for window in WINDOWS:
            metrics = _metrics_for_window(path, window)
            metrics.update({"overlay_name": overlay.name, "overlay_label": overlay.label, "overlay_note": overlay.note})
            rows.append(metrics)
    summary = pd.DataFrame(rows)
    paths = pd.concat(all_paths, ignore_index=True) if all_paths else pd.DataFrame()

    baseline = summary[summary["overlay_name"].eq("A_c3_no_overlay")][
        ["window_name", "total_return_pct", "max_dd_percent", "sharpe_ratio"]
    ].rename(
        columns={
            "total_return_pct": "baseline_return_pct",
            "max_dd_percent": "baseline_max_dd_pct",
            "sharpe_ratio": "baseline_sharpe",
        }
    )
    summary = summary.merge(baseline, on="window_name", how="left")
    summary["return_retention_vs_c3_pct"] = np.where(
        summary["baseline_return_pct"] > 0,
        summary["total_return_pct"] / summary["baseline_return_pct"] * 100.0,
        np.nan,
    )
    summary["dd_ok"] = (summary["max_dd_percent"] >= -30.0).astype(int)
    summary["retention80_ok"] = (summary["return_retention_vs_c3_pct"] >= 80.0).astype(int)
    summary["research_pass"] = ((summary["dd_ok"] == 1) & (summary["retention80_ok"] == 1)).astype(int)
    return summary, paths


def _drawdown_window(enriched: pd.DataFrame) -> dict[str, Any]:
    if enriched.empty:
        return {}
    trough_idx = enriched["ddpercent"].idxmin()
    trough = enriched.loc[trough_idx]
    prior = enriched.loc[:trough_idx].copy()
    peak_idx = prior["balance"].idxmax()
    peak = enriched.loc[peak_idx]
    return {
        "peak_date": str(pd.to_datetime(peak["date"]).date()),
        "trough_date": str(pd.to_datetime(trough["date"]).date()),
        "peak_balance": _safe_float(peak["balance"]),
        "trough_balance": _safe_float(trough["balance"]),
        "max_dd_percent": _safe_float(trough["ddpercent"]),
        "trough_margin_to_equity_pct": _safe_float(trough["margin_to_equity_pct"]),
        "trough_active_products": int(_safe_float(trough["c3_active_products"])),
        "trough_active_contracts": int(_safe_float(trough["c3_active_contracts"])),
    }


def _bucket_attribution(enriched: pd.DataFrame) -> pd.DataFrame:
    frame = enriched.copy()
    frame["prev_margin_bucket"] = pd.cut(
        frame["prev_margin_to_equity_pct"],
        bins=[-0.001, 40.0, 60.0, 80.0, 100.0, math.inf],
        labels=["<=40", "40-60", "60-80", "80-100", ">100"],
    )
    frame["prev_active_bucket"] = pd.cut(
        frame["prev_active_products"],
        bins=[-0.001, 3.0, 5.0, 7.0, math.inf],
        labels=["<=3", "4-5", "6-7", ">=8"],
    )
    rows: list[dict[str, Any]] = []
    for key in ["prev_margin_bucket", "prev_active_bucket"]:
        grouped = frame.groupby(key, observed=True)
        for bucket, group in grouped:
            if group.empty:
                continue
            rows.append(
                {
                    "bucket_type": key,
                    "bucket": str(bucket),
                    "days": int(len(group)),
                    "net_pnl_sum": float(group["net_pnl"].sum()),
                    "net_pnl_mean": float(group["net_pnl"].mean()),
                    "loss_day_ratio_pct": float((group["net_pnl"] < 0).mean() * 100.0),
                    "avg_prev_margin_pct": float(group["prev_margin_to_equity_pct"].mean()),
                    "avg_prev_active_products": float(group["prev_active_products"].mean()),
                }
            )
    return pd.DataFrame(rows)


def _worst_days(enriched: pd.DataFrame, n: int = 20) -> pd.DataFrame:
    cols = [
        "date",
        "net_pnl",
        "balance",
        "ddpercent",
        "prev_margin_to_equity_pct",
        "margin_to_equity_pct",
        "prev_active_products",
        "c3_active_products",
        "prev_active_contracts",
        "c3_active_contracts",
        "trade_count",
    ]
    return enriched.sort_values("net_pnl").head(n)[cols].copy()


def _build_report(
    c3_stats: dict[str, Any],
    summary: pd.DataFrame,
    enriched: pd.DataFrame,
    bucket_df: pd.DataFrame,
    worst_df: pd.DataFrame,
    dd_info: dict[str, Any],
) -> str:
    full = summary[summary["window_name"].eq("start_2020")].copy()
    full = full.sort_values(["research_pass", "max_dd_percent", "return_retention_vs_c3_pct"], ascending=[False, False, False])
    multi = (
        summary[~summary["overlay_name"].eq("A_c3_no_overlay")]
        .groupby(["overlay_name", "overlay_label"], as_index=False)
        .agg(
            pass_count=("research_pass", "sum"),
            min_return_retention_vs_c3_pct=("return_retention_vs_c3_pct", "min"),
            worst_max_dd_pct=("max_dd_percent", "min"),
            median_sharpe=("sharpe_ratio", "median"),
            max_weight_lt_1_days=("weight_lt_1_days", "max"),
        )
        .sort_values(["pass_count", "worst_max_dd_pct", "min_return_retention_vs_c3_pct"], ascending=[False, False, False])
    )
    max_margin = float(enriched["margin_to_equity_pct"].max()) if not enriched.empty else 0.0
    p95_margin = float(enriched["margin_to_equity_pct"].quantile(0.95)) if not enriched.empty else 0.0
    lines = [
        "# Stage027 C3保证金/持仓拥挤状态识别",
        "",
        "## 目标",
        "",
        "- 固定 C3，不修改入场 alpha、AI池、品种池和供需过滤参数。",
        "- 检查剩余 `-31.0767%` 回撤是否能被上一交易日可知的保证金占用或持仓广度解释。",
        "- 只测试粗档位账户层覆盖：60/80/100 保证金SOP线，以及 6/8 个持仓品种广度线。",
        "- 本阶段是日级边界探针，结果好也不能直接晋级；必须后续落到真实引擎和多周期压力复验。",
        "",
        "## C3原始统计",
        "",
        f"- 期末权益：`{_safe_float(c3_stats.get('end_balance')):,.0f}`",
        f"- 总收益：`{_safe_float(c3_stats.get('total_return')):.4f}%`",
        f"- 最大回撤：`{_safe_float(c3_stats.get('max_ddpercent')):.4f}%`",
        f"- Sharpe：`{_safe_float(c3_stats.get('sharpe_ratio')):.4f}`",
        f"- 总滑点：`{_safe_float(c3_stats.get('total_slippage')):,.0f}`",
        f"- 总交易次数：`{int(_safe_float(c3_stats.get('total_trade_count'))):,}`",
        f"- 胜率：`{_safe_float(c3_stats.get('win_ratio')):.4f}%`",
        f"- 最大保证金/权益：`{max_margin:.4f}%`，P95：`{p95_margin:.4f}%`",
        f"- 60%观察线天数：`{int((enriched['margin_to_equity_pct'] >= MARGIN_WATCH_PCT).sum())}`，"
        f"80%复核线天数：`{int((enriched['margin_to_equity_pct'] >= MARGIN_REVIEW_PCT).sum())}`，"
        f"100%拒绝线天数：`{int((enriched['margin_to_equity_pct'] >= MARGIN_REJECT_PCT).sum())}`",
        "",
        "## 最大回撤窗口",
        "",
        _to_markdown_table(pd.DataFrame([dd_info])),
        "",
        "## 全样本覆盖层边界",
        "",
        _to_markdown_table(
            full,
            [
                "overlay_name",
                "total_return_pct",
                "return_retention_vs_c3_pct",
                "max_dd_percent",
                "sharpe_ratio",
                "total_slippage",
                "total_trade_count_weighted",
                "weight_lt_1_days",
                "avg_weight",
                "research_pass",
            ],
        ),
        "",
        "## 多窗口稳健性",
        "",
        _to_markdown_table(
            multi,
            [
                "overlay_name",
                "pass_count",
                "min_return_retention_vs_c3_pct",
                "worst_max_dd_pct",
                "median_sharpe",
                "max_weight_lt_1_days",
            ],
        ),
        "",
        "## 状态分桶归因",
        "",
        _to_markdown_table(bucket_df),
        "",
        "## 最差单日样本",
        "",
        _to_markdown_table(worst_df),
        "",
        "## 阶段判断",
        "",
    ]
    non_base_full = full[~full["overlay_name"].eq("A_c3_no_overlay")]
    pass_full = non_base_full[non_base_full["research_pass"].eq(1)]
    if pass_full.empty:
        lines.append("- 结论：预声明保证金/持仓广度日级覆盖层没有在全样本同时满足 `回撤30以内 + 收益保留80%`。")
    else:
        best = pass_full.iloc[0]
        lines.append(
            f"- 结论：日级边界上出现线索 `{best['overlay_name']}`，全样本收益保留 "
            f"`{best['return_retention_vs_c3_pct']:.2f}%`，最大回撤 `{best['max_dd_percent']:.4f}%`。"
        )
        lines.append("- 但这只是按日收益缩放的理论边界，不能视为可实盘版本；下一步必须落真实引擎验证。")
    lines.extend(
        [
            "",
            "## 过拟合反思",
            "",
            "- 运行前：不是过拟合。规则只使用上一交易日已知的保证金与持仓广度，阈值来自既有SOP粗线或整数持仓广度。",
            "- 运行后：若结果失败，继续把阈值改成73/87之类小数会过拟合；若结果成功，也只能作为结构线索继续实引擎反证。",
            "",
            "## 继续价值反思",
            "",
            "- 运行前：有价值。C3距离30%目标只差约1.08个百分点，先判断是否来自账户拥挤状态，比继续调alpha更稳健。",
            "- 运行后：继续价值取决于是否出现跨窗口稳定线索；没有线索则应转向更强独立收益源或更本质的波动状态识别。",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    daily, positions, c3_stats = _run_c3()
    enriched = _enrich_daily(daily, positions)
    summary, paths = _build_overlay_summary(enriched)
    bucket_df = _bucket_attribution(enriched)
    worst_df = _worst_days(enriched)
    dd_info = _drawdown_window(enriched)

    summary_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
    paths_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_overlay_paths_{MODEL_TAG}.csv"
    enriched_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_state_{MODEL_TAG}.csv"
    bucket_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_bucket_attribution_{MODEL_TAG}.csv"
    worst_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_worst_days_{MODEL_TAG}.csv"
    report_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
    decision_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

    summary.to_csv(summary_path, index=False, encoding="utf-8-sig")
    paths.to_csv(paths_path, index=False, encoding="utf-8-sig")
    enriched.to_csv(enriched_path, index=False, encoding="utf-8-sig")
    bucket_df.to_csv(bucket_path, index=False, encoding="utf-8-sig")
    worst_df.to_csv(worst_path, index=False, encoding="utf-8-sig")
    report_path.write_text(_build_report(c3_stats, summary, enriched, bucket_df, worst_df, dd_info), encoding="utf-8")

    full = summary[summary["window_name"].eq("start_2020")].copy()
    decision = {
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "official_version": OFFICIAL_STAGE78_VERSION,
        "official_role": OFFICIAL_STAGE78_ROLE,
        "capital": TOTAL_CAPITAL,
        "baseline": "C3_supply_headwind",
        "decision": "probe_only_requires_real_engine_validation",
        "full_sample": full.to_dict(orient="records"),
        "drawdown_window": dd_info,
        "paths": {
            "summary": str(summary_path),
            "overlay_paths": str(paths_path),
            "daily_state": str(enriched_path),
            "bucket_attribution": str(bucket_path),
            "worst_days": str(worst_path),
            "report": str(report_path),
        },
    }
    decision_path.write_text(json.dumps(_to_builtin(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[stage327] summary={summary_path}")
    print(f"[stage327] paths={paths_path}")
    print(f"[stage327] state={enriched_path}")
    print(f"[stage327] report={report_path}")
    print(f"[stage327] decision={decision_path}")


if __name__ == "__main__":
    main()
