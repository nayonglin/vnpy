from __future__ import annotations

import json
import math
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from qmt_backtest_runtime_guard import assert_stage196_database_sentinels
from qmt_roll_official_stage78_config import (
    OFFICIAL_STAGE78_CAPITAL,
    OFFICIAL_STAGE78_ROLE,
    OFFICIAL_STAGE78_VERSION,
    build_official_stage78_manifest,
    build_official_stage78_overrides,
)
from qmt_universe import END_DT, PRELOAD_START_DT, START_DT
from run_qmt_roll_backtest import build_summary_row, run_backtest
from run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest import BASE_RISK_RATIO


MODEL_TAG = "stage249_stage78_1_profit_giveback_ablation_suite_v1"
OUTPUT_PREFIX = "qmt_roll_stage249_stage78_1_profit_giveback_ablation_suite"
SLIPPAGE_MULTIPLIERS = (1.0, 2.0, 3.0, 5.0)

WINDOWS: tuple[tuple[str, str, str, datetime, datetime], ...] = (
    ("since_2020", "2020起点至今", "start_year_to_latest", datetime(2020, 1, 1), END_DT),
    ("since_2021", "2021起点至今", "start_year_to_latest", datetime(2021, 1, 1), END_DT),
    ("since_2022", "2022起点至今", "start_year_to_latest", datetime(2022, 1, 1), END_DT),
    ("since_2023", "2023起点至今", "start_year_to_latest", datetime(2023, 1, 1), END_DT),
    ("since_2024", "2024起点至今", "start_year_to_latest", datetime(2024, 1, 1), END_DT),
    ("since_2025", "2025起点至今", "start_year_to_latest", datetime(2025, 1, 1), END_DT),
    ("since_2026", "2026起点至今", "start_year_to_latest", datetime(2026, 1, 1), END_DT),
    ("phase_2020_2021", "2020-2021独立启动", "independent_phase", datetime(2020, 1, 1), datetime(2021, 12, 31)),
    ("phase_2022_2023", "2022-2023独立启动", "independent_phase", datetime(2022, 1, 1), datetime(2023, 12, 31)),
    ("phase_2024_2025", "2024-2025独立启动", "independent_phase", datetime(2024, 1, 1), datetime(2025, 12, 31)),
    ("phase_2026_latest", "2026独立启动至最新", "independent_phase", datetime(2026, 1, 1), END_DT),
)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(result) or math.isinf(result):
        return default
    return result


def _variant_label(enabled: bool) -> str:
    return "profit_giveback_on" if enabled else "profit_giveback_off"


def _variant_overrides(enabled: bool) -> dict[str, Any]:
    overrides = build_official_stage78_overrides()
    overrides["enable_profit_giveback_stop"] = bool(enabled)
    overrides["profit_giveback_trigger_pct"] = 0.08
    overrides["profit_giveback_retain_ratio"] = 0.70
    overrides["profit_giveback_min_lock_pct"] = 0.03
    return overrides


def _daily_to_frame(daily_df: pd.DataFrame | None) -> pd.DataFrame:
    if daily_df is None or daily_df.empty:
        return pd.DataFrame()
    frame = daily_df.copy()
    frame.insert(0, "date", pd.to_datetime(frame.index).date)
    return frame


def _path_metrics_from_pnl(net_pnl: np.ndarray, initial_capital: float) -> dict[str, float]:
    if net_pnl.size == 0:
        return {"end_balance": initial_capital, "total_return_pct": 0.0, "max_drawdown": 0.0, "max_dd_percent": 0.0, "sharpe_ratio": 0.0}
    equity = initial_capital + np.cumsum(net_pnl)
    previous = np.concatenate([[initial_capital], equity[:-1]])
    returns = np.divide(net_pnl, previous, out=np.zeros_like(net_pnl, dtype=float), where=previous != 0)
    high = np.maximum.accumulate(np.insert(equity, 0, initial_capital))[1:]
    drawdown = equity - high
    dd_pct = np.divide(drawdown, high, out=np.zeros_like(drawdown, dtype=float), where=high != 0) * 100.0
    std = float(np.std(returns, ddof=1)) if returns.size > 1 else 0.0
    return {
        "end_balance": float(equity[-1]),
        "total_return_pct": float((equity[-1] / initial_capital - 1.0) * 100.0),
        "max_drawdown": float(drawdown.min()),
        "max_dd_percent": float(dd_pct.min()),
        "sharpe_ratio": float(np.mean(returns) / std * np.sqrt(240.0)) if std > 0 else 0.0,
    }


def _slippage_stress(variant: str, daily_df: pd.DataFrame) -> pd.DataFrame:
    net_pnl = pd.to_numeric(daily_df["net_pnl"], errors="coerce").fillna(0.0).to_numpy(dtype=float)
    slippage = pd.to_numeric(daily_df.get("slippage", 0.0), errors="coerce").fillna(0.0).to_numpy(dtype=float)
    rows: list[dict[str, Any]] = []
    for multiplier in SLIPPAGE_MULTIPLIERS:
        stressed = net_pnl - (multiplier - 1.0) * slippage
        rows.append(
            {
                "variant": variant,
                "slippage_multiplier": multiplier,
                **_path_metrics_from_pnl(stressed, OFFICIAL_STAGE78_CAPITAL),
                "total_net_pnl": float(stressed.sum()),
                "total_slippage": float(slippage.sum() * multiplier),
            }
        )
    return pd.DataFrame(rows)


def run_main_variants() -> tuple[pd.DataFrame, pd.DataFrame]:
    summary_rows: list[dict[str, Any]] = []
    daily_frames: list[pd.DataFrame] = []
    for enabled in (False, True):
        variant = _variant_label(enabled)
        print(f"[stage249] main {variant}", flush=True)
        overrides = _variant_overrides(enabled)
        overrides["trade_start_date"] = START_DT.date().isoformat()
        engine, analysis_df, statistics = run_backtest(
            risk_ratio=BASE_RISK_RATIO,
            strategy_overrides=overrides,
            analysis_start=START_DT,
            analysis_end=END_DT,
            capital=OFFICIAL_STAGE78_CAPITAL,
            save_artifacts=False,
            include_start_year_sweep=False,
            file_prefix=f"{OUTPUT_PREFIX}_{variant}_main",
            chart_title=f"Stage249 78-1 profit giveback {variant}",
        )
        strategy = getattr(engine, "strategy", None)
        summary_rows.append(
            build_summary_row(
                statistics,
                variant=variant,
                profit_giveback_enabled=bool(enabled),
                profit_giveback_stop_update_count=int(getattr(strategy, "profit_giveback_stop_update_count", 0) if strategy else 0),
                analysis_start=START_DT,
                analysis_end=END_DT,
                official_version=OFFICIAL_STAGE78_VERSION,
                official_role=OFFICIAL_STAGE78_ROLE,
                model_tag=MODEL_TAG,
                capital=OFFICIAL_STAGE78_CAPITAL,
                base_risk_ratio=BASE_RISK_RATIO,
                total_net_pnl=float(statistics.get("total_net_pnl", 0) or 0),
                total_slippage=float(statistics.get("total_slippage", 0) or 0),
                total_commission=float(statistics.get("total_commission", 0) or 0),
                profit_days=int(statistics.get("profit_days", 0) or 0),
                loss_days=int(statistics.get("loss_days", 0) or 0),
            )
        )
        daily_frame = _daily_to_frame(analysis_df)
        daily_frame["variant"] = variant
        daily_frames.append(daily_frame)
    return pd.DataFrame(summary_rows), pd.concat(daily_frames, ignore_index=True)


def run_multiperiod() -> tuple[pd.DataFrame, pd.DataFrame]:
    summary_rows: list[dict[str, Any]] = []
    curve_frames: list[pd.DataFrame] = []
    for enabled in (False, True):
        variant = _variant_label(enabled)
        for window_name, display_label, group, analysis_start, analysis_end in WINDOWS:
            print(f"[stage249] multiperiod {variant} {window_name}", flush=True)
            overrides = _variant_overrides(enabled)
            overrides["trade_start_date"] = analysis_start.date().isoformat()
            preload_start = max(PRELOAD_START_DT, analysis_start - timedelta(days=365))
            engine, analysis_df, statistics = run_backtest(
                risk_ratio=BASE_RISK_RATIO,
                strategy_overrides=overrides,
                analysis_start=analysis_start,
                analysis_end=analysis_end,
                preload_start=preload_start,
                capital=OFFICIAL_STAGE78_CAPITAL,
                save_artifacts=False,
                include_start_year_sweep=False,
                file_prefix=f"{OUTPUT_PREFIX}_{variant}_{window_name}",
                chart_title=f"Stage249 78-1 {variant} {display_label}",
            )
            strategy = getattr(engine, "strategy", None)
            summary_rows.append(
                build_summary_row(
                    statistics,
                    variant=variant,
                    profit_giveback_enabled=bool(enabled),
                    profit_giveback_stop_update_count=int(getattr(strategy, "profit_giveback_stop_update_count", 0) if strategy else 0),
                    window_name=window_name,
                    display_label=display_label,
                    group=group,
                    analysis_start=analysis_start,
                    analysis_end=analysis_end,
                    official_version=OFFICIAL_STAGE78_VERSION,
                    official_role=OFFICIAL_STAGE78_ROLE,
                    model_tag=MODEL_TAG,
                    trade_start_date=analysis_start.date().isoformat(),
                    preload_start=preload_start.date().isoformat(),
                    capital=OFFICIAL_STAGE78_CAPITAL,
                    base_risk_ratio=BASE_RISK_RATIO,
                    total_net_pnl=float(statistics.get("total_net_pnl", 0) or 0),
                    total_slippage=float(statistics.get("total_slippage", 0) or 0),
                    total_commission=float(statistics.get("total_commission", 0) or 0),
                    profit_days=int(statistics.get("profit_days", 0) or 0),
                    loss_days=int(statistics.get("loss_days", 0) or 0),
                )
            )
            if analysis_df is not None and not analysis_df.empty:
                curve = analysis_df.copy().reset_index().rename(columns={"index": "date"})
                curve["date"] = pd.to_datetime(curve["date"])
                curve["variant"] = variant
                curve["window_name"] = window_name
                curve["display_label"] = display_label
                curve["group"] = group
                net_pnl = pd.to_numeric(curve["net_pnl"], errors="coerce").fillna(0.0)
                curve["rebased_balance"] = OFFICIAL_STAGE78_CAPITAL + net_pnl.cumsum()
                curve["normalized_nav"] = curve["rebased_balance"] / OFFICIAL_STAGE78_CAPITAL
                high = curve["rebased_balance"].cummax()
                curve["drawdown_pct"] = (curve["rebased_balance"] / high - 1.0) * 100.0
                curve_frames.append(curve)
    return pd.DataFrame(summary_rows), pd.concat(curve_frames, ignore_index=True)


def build_report(main_df: pd.DataFrame, multi_df: pd.DataFrame, slippage_df: pd.DataFrame, paths: dict[str, str]) -> str:
    diff_rows: list[dict[str, Any]] = []
    on_variant = _variant_label(True)
    off_variant = _variant_label(False)
    for window_name, group in multi_df.groupby("window_name"):
        on = group[group["variant"].eq(on_variant)]
        off = group[group["variant"].eq(off_variant)]
        if on.empty or off.empty:
            continue
        on_row = on.iloc[0]
        off_row = off.iloc[0]
        diff_rows.append(
            {
                "window_name": window_name,
                "display_label": on_row.get("display_label", window_name),
                "on_return_pct": on_row["total_return_pct"],
                "off_return_pct": off_row["total_return_pct"],
                "return_delta_pct": on_row["total_return_pct"] - off_row["total_return_pct"],
                "on_max_dd_pct": on_row["max_dd_percent"],
                "off_max_dd_pct": off_row["max_dd_percent"],
                "on_sharpe": on_row["sharpe_ratio"],
                "off_sharpe": off_row["sharpe_ratio"],
                "on_updates": int(_safe_float(on_row.get("profit_giveback_stop_update_count", 0))),
                "off_updates": int(_safe_float(off_row.get("profit_giveback_stop_update_count", 0))),
            }
        )
    diff_df = pd.DataFrame(diff_rows)
    lines = [
        "# Stage249 Stage78-1 盈利回撤止盈默认开关A/B实验报告",
        "",
        "## 口径",
        "",
        f"- 版本：`{OFFICIAL_STAGE78_VERSION}`",
        f"- 初始资金：`{OFFICIAL_STAGE78_CAPITAL:,.0f}`",
        "- 唯一变量：`enable_profit_giveback_stop` 显式开/关",
        "- 默认参数：`trigger=0.08`，`retain=0.70`，`min_lock=0.03`",
        "- 反过拟合原则：本次只验证“打开当前默认开关”，不做参数搜索。",
        "",
        "## 主回测",
        "",
        main_df[
            ["variant", "end_balance", "total_return_pct", "max_dd_percent", "sharpe_ratio", "total_trade_count", "total_slippage", "profit_giveback_stop_update_count"]
        ].to_markdown(index=False),
        "",
        "## 多周期差异（ON - OFF）",
        "",
        diff_df.to_markdown(index=False) if not diff_df.empty else "_empty_",
        "",
        "## 滑点压力",
        "",
        slippage_df[
            ["variant", "slippage_multiplier", "end_balance", "total_return_pct", "max_dd_percent", "sharpe_ratio", "total_slippage"]
        ].to_markdown(index=False),
        "",
        "## 输出文件",
        "",
    ]
    for name, path in paths.items():
        lines.append(f"- {name}: `{path}`")
    return "\n".join(lines) + "\n"


def build_html(multi_df: pd.DataFrame, curves_df: pd.DataFrame) -> str:
    fig = make_subplots(rows=2, cols=1, shared_xaxes=False, vertical_spacing=0.12, subplot_titles=("NAV", "Drawdown %"))
    for (variant, label), group in curves_df.groupby(["variant", "display_label"], sort=False):
        name = f"{variant} {label}"
        fig.add_trace(go.Scatter(x=group["date"], y=group["normalized_nav"], mode="lines", name=name), row=1, col=1)
        fig.add_trace(go.Scatter(x=group["date"], y=group["drawdown_pct"], mode="lines", name=f"{name} DD", showlegend=False), row=2, col=1)
    fig.update_layout(title="Stage249 Stage78-1 盈利回撤止盈 ON/OFF 多周期曲线", height=1000, template="plotly_white")
    return "\n".join([
        "<!doctype html>",
        "<html><head><meta charset='utf-8'><title>Stage249 Profit Giveback Ablation</title></head><body>",
        "<h1>Stage249 Stage78-1 盈利回撤止盈 ON/OFF 多周期曲线</h1>",
        multi_df.to_html(index=False, float_format=lambda value: f"{value:,.4f}", border=0),
        fig.to_html(full_html=False, include_plotlyjs='cdn'),
        "</body></html>",
    ])


def main() -> None:
    assert_stage196_database_sentinels()
    output_dir = Path(__file__).resolve().parent / "backtest_outputs"
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = build_official_stage78_manifest()

    main_df, daily_df = run_main_variants()
    multi_df, curves_df = run_multiperiod()
    slippage_df = pd.concat([_slippage_stress(variant, daily_df[daily_df["variant"].eq(variant)]) for variant in daily_df["variant"].unique()], ignore_index=True)

    paths = {
        "main_summary": str((output_dir / f"{OUTPUT_PREFIX}_main_summary_{MODEL_TAG}.csv").resolve()),
        "main_daily": str((output_dir / f"{OUTPUT_PREFIX}_main_daily_{MODEL_TAG}.csv").resolve()),
        "multiperiod_summary": str((output_dir / f"{OUTPUT_PREFIX}_multiperiod_summary_{MODEL_TAG}.csv").resolve()),
        "multiperiod_curves": str((output_dir / f"{OUTPUT_PREFIX}_multiperiod_curves_{MODEL_TAG}.csv").resolve()),
        "slippage_stress": str((output_dir / f"{OUTPUT_PREFIX}_slippage_stress_{MODEL_TAG}.csv").resolve()),
        "report_md": str((output_dir / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md").resolve()),
        "report_html": str((output_dir / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.html").resolve()),
        "manifest": str((output_dir / f"{OUTPUT_PREFIX}_manifest_{MODEL_TAG}.json").resolve()),
    }

    main_df.to_csv(paths["main_summary"], index=False, encoding="utf-8-sig")
    daily_df.to_csv(paths["main_daily"], index=False, encoding="utf-8-sig")
    multi_df.to_csv(paths["multiperiod_summary"], index=False, encoding="utf-8-sig")
    curves_df.to_csv(paths["multiperiod_curves"], index=False, encoding="utf-8-sig")
    slippage_df.to_csv(paths["slippage_stress"], index=False, encoding="utf-8-sig")
    Path(paths["report_md"]).write_text(build_report(main_df, multi_df, slippage_df, paths), encoding="utf-8")
    Path(paths["report_html"]).write_text(build_html(multi_df, curves_df), encoding="utf-8")
    Path(paths["manifest"]).write_text(json.dumps({
        "model_tag": MODEL_TAG,
        "output_prefix": OUTPUT_PREFIX,
        "official_manifest": manifest,
        "ablation": {
            "only_variable": "enable_profit_giveback_stop",
            "fixed_params": {
                "profit_giveback_trigger_pct": 0.08,
                "profit_giveback_retain_ratio": 0.70,
                "profit_giveback_min_lock_pct": 0.03,
            },
            "variants": [_variant_label(False), _variant_label(True)],
        },
        "paths": paths,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(paths, ensure_ascii=False, indent=2))
    print(main_df[["variant", "end_balance", "total_return_pct", "max_dd_percent", "sharpe_ratio", "total_trade_count", "profit_giveback_stop_update_count"]].to_string(index=False))


if __name__ == "__main__":
    main()

