from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from qmt_roll_official_stage78_config import (
    OFFICIAL_STAGE78_CAPITAL,
    OFFICIAL_STAGE78_ROLE,
    OFFICIAL_STAGE78_VERSION,
    build_official_stage78_overrides,
)
from qmt_universe import END_DT, PRELOAD_START_DT
from run_qmt_alignment_backtest import OUTPUT_DIR
from run_qmt_roll_backtest import build_summary_row, run_backtest
from run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest import BASE_RISK_RATIO


MODEL_TAG: str = "stage218_stage78_50w_multiperiod_equity_curves_v1"
OUTPUT_PREFIX: str = "qmt_roll_stage218_stage78_50w_multiperiod_equity_curves"
REPORT_STAGE: str = "Stage218"
ACTIVE_CAPITAL: float = OFFICIAL_STAGE78_CAPITAL
ACTIVE_SIZING_EQUITY_CAP: float | None = None

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


def _capital_label(capital: float) -> str:
    if abs(capital % 10_000) < 1e-9:
        return f"{int(capital / 10_000)}万"
    return f"{capital:,.0f}"


def _format_table(df: pd.DataFrame) -> str:
    if df.empty:
        return "_empty_\n"
    view = df.copy()
    columns = [
        "window_name",
        "display_label",
        "group",
        "analysis_start",
        "analysis_end",
        "end_balance",
        "total_return_pct",
        "max_dd_percent",
        "sharpe_ratio",
        "total_trade_count",
        "total_slippage",
    ]
    view = view[columns]
    for column in ["end_balance", "total_return_pct", "max_dd_percent", "sharpe_ratio", "total_slippage"]:
        view[column] = pd.to_numeric(view[column], errors="coerce").map(lambda value: f"{value:,.4f}")
    return view.to_markdown(index=False) + "\n"


def _build_curve_frame(
    analysis_df: pd.DataFrame,
    *,
    window_name: str,
    display_label: str,
    group: str,
    analysis_start: datetime,
    analysis_end: datetime,
    summary: dict[str, Any],
) -> pd.DataFrame:
    frame = analysis_df.copy()
    frame = frame.reset_index().rename(columns={"index": "date"})
    frame["date"] = pd.to_datetime(frame["date"])
    net_pnl = pd.to_numeric(frame["net_pnl"], errors="coerce").fillna(0.0)
    frame["rebased_balance"] = ACTIVE_CAPITAL + net_pnl.cumsum()
    frame["normalized_nav"] = frame["rebased_balance"] / ACTIVE_CAPITAL
    high = frame["rebased_balance"].cummax()
    frame["drawdown_pct"] = (frame["rebased_balance"] / high - 1.0) * 100.0
    frame["window_name"] = window_name
    frame["display_label"] = display_label
    frame["group"] = group
    frame["analysis_start"] = analysis_start.date().isoformat()
    frame["analysis_end"] = analysis_end.date().isoformat()
    frame["total_return_pct"] = float(summary.get("total_return_pct", 0.0) or 0.0)
    frame["max_dd_percent"] = float(summary.get("max_dd_percent", 0.0) or 0.0)
    frame["sharpe_ratio"] = float(summary.get("sharpe_ratio", 0.0) or 0.0)
    keep_columns = [
        "date",
        "window_name",
        "display_label",
        "group",
        "analysis_start",
        "analysis_end",
        "balance",
        "rebased_balance",
        "normalized_nav",
        "drawdown_pct",
        "net_pnl",
        "trade_count",
        "total_return_pct",
        "max_dd_percent",
        "sharpe_ratio",
    ]
    return frame[keep_columns]


def run_windows() -> tuple[pd.DataFrame, pd.DataFrame]:
    summary_rows: list[dict[str, Any]] = []
    curve_frames: list[pd.DataFrame] = []
    for window_name, display_label, group, analysis_start, analysis_end in WINDOWS:
        print(f"[{REPORT_STAGE.lower()}] running {window_name}: {analysis_start.date()} -> {analysis_end.date()}", flush=True)
        overrides = build_official_stage78_overrides()
        overrides["trade_start_date"] = analysis_start.date().isoformat()
        if ACTIVE_SIZING_EQUITY_CAP is not None:
            overrides["sizing_equity_cap"] = ACTIVE_SIZING_EQUITY_CAP
        preload_start = max(PRELOAD_START_DT, analysis_start - timedelta(days=365))
        _, analysis_df, statistics = run_backtest(
            risk_ratio=BASE_RISK_RATIO,
            strategy_overrides=overrides,
            analysis_start=analysis_start,
            analysis_end=analysis_end,
            preload_start=preload_start,
            capital=ACTIVE_CAPITAL,
            save_artifacts=False,
            include_start_year_sweep=False,
            file_prefix=f"{OUTPUT_PREFIX}_{window_name}",
            chart_title=(
                f"{REPORT_STAGE} Stage78 {_capital_label(ACTIVE_CAPITAL)} "
                f"{display_label} sizing_cap={ACTIVE_SIZING_EQUITY_CAP}"
            ),
        )
        summary = build_summary_row(
            statistics,
            analysis_start=analysis_start,
            analysis_end=analysis_end,
            window_name=window_name,
            display_label=display_label,
            group=group,
            official_version=OFFICIAL_STAGE78_VERSION,
            official_role=OFFICIAL_STAGE78_ROLE,
            model_tag=MODEL_TAG,
            trade_start_date=analysis_start.date().isoformat(),
            preload_start=preload_start.date().isoformat(),
            capital=ACTIVE_CAPITAL,
            base_risk_ratio=BASE_RISK_RATIO,
            total_net_pnl=float(statistics.get("total_net_pnl", 0) or 0),
            total_slippage=float(statistics.get("total_slippage", 0) or 0),
            total_commission=float(statistics.get("total_commission", 0) or 0),
            profit_days=int(statistics.get("profit_days", 0) or 0),
            loss_days=int(statistics.get("loss_days", 0) or 0),
        )
        summary_rows.append(summary)
        if analysis_df is not None and not analysis_df.empty:
            curve_frames.append(
                _build_curve_frame(
                    analysis_df,
                    window_name=window_name,
                    display_label=display_label,
                    group=group,
                    analysis_start=analysis_start,
                    analysis_end=analysis_end,
                    summary=summary,
                )
            )
    summary_df = pd.DataFrame(summary_rows)
    summary_df.sort_values(["group", "analysis_start", "analysis_end"], inplace=True)
    curves_df = pd.concat(curve_frames, ignore_index=True) if curve_frames else pd.DataFrame()
    if not curves_df.empty:
        curves_df.sort_values(["group", "analysis_start", "date"], inplace=True)
    return summary_df.reset_index(drop=True), curves_df.reset_index(drop=True)


def build_html(summary_df: pd.DataFrame, curves_df: pd.DataFrame) -> str:
    capital_label = _capital_label(ACTIVE_CAPITAL)
    sizing_cap_text = (
        "关闭sizing资金封顶"
        if ACTIVE_SIZING_EQUITY_CAP == 0
        else f"sizing资金封顶{ACTIVE_SIZING_EQUITY_CAP:,.0f}"
        if ACTIVE_SIZING_EQUITY_CAP is not None
        else "沿用默认sizing资金封顶"
    )
    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=False,
        vertical_spacing=0.12,
        subplot_titles=(f"归一化资金曲线 NAV（{capital_label}本金，每个周期从1.0独立启动）", "回撤曲线（%）"),
    )
    for _, group_df in curves_df.groupby("display_label", sort=False):
        label = str(group_df["display_label"].iloc[0])
        fig.add_trace(
            go.Scatter(
                x=group_df["date"],
                y=group_df["normalized_nav"],
                mode="lines",
                name=label,
                hovertemplate="%{x|%Y-%m-%d}<br>NAV=%{y:.4f}<extra>" + label + "</extra>",
            ),
            row=1,
            col=1,
        )
        fig.add_trace(
            go.Scatter(
                x=group_df["date"],
                y=group_df["drawdown_pct"],
                mode="lines",
                name=f"{label} 回撤",
                showlegend=False,
                hovertemplate="%{x|%Y-%m-%d}<br>DD=%{y:.2f}%<extra>" + label + "</extra>",
            ),
            row=2,
            col=1,
        )
    fig.update_layout(
        title=f"{REPORT_STAGE} 第78 {_capital_label(ACTIVE_CAPITAL)}本金多周期独立启动资金曲线（{sizing_cap_text}）",
        height=960,
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        template="plotly_white",
    )
    fig.update_yaxes(title_text="Normalized NAV", row=1, col=1)
    fig.update_yaxes(title_text="Drawdown %", row=2, col=1)
    fig.update_xaxes(title_text="Date", row=2, col=1)

    table_html = summary_df[
        [
            "display_label",
            "group",
            "analysis_start",
            "analysis_end",
            "end_balance",
            "total_return_pct",
            "max_dd_percent",
            "sharpe_ratio",
            "total_trade_count",
            "total_slippage",
        ]
    ].to_html(index=False, float_format=lambda value: f"{value:,.4f}", border=0)
    return "\n".join(
        [
            "<!doctype html>",
            "<html>",
            f"<head><meta charset='utf-8'><title>{REPORT_STAGE} Stage78 {capital_label} Multiperoid Equity Curves</title></head>",
            "<body>",
            f"<h1>{REPORT_STAGE} 第78 {capital_label}本金多周期独立启动资金曲线</h1>",
            (
                f"<p>口径：每个周期独立启动，初始本金{ACTIVE_CAPITAL:,.0f}；"
                f"{sizing_cap_text}；预热仅用于指标/AM初始化；trade_start_date固定为周期起点。</p>"
            ),
            fig.to_html(full_html=False, include_plotlyjs="cdn"),
            "<h2>Summary</h2>",
            table_html,
            "</body>",
            "</html>",
        ]
    )


def build_markdown(summary_df: pd.DataFrame, paths: dict[str, str]) -> str:
    sizing_cap_text = (
        "关闭sizing资金封顶"
        if ACTIVE_SIZING_EQUITY_CAP == 0
        else f"sizing资金封顶 `{ACTIVE_SIZING_EQUITY_CAP:,.0f}`"
        if ACTIVE_SIZING_EQUITY_CAP is not None
        else "沿用默认sizing资金封顶"
    )
    lines = [
        f"# {REPORT_STAGE} 第78 {_capital_label(ACTIVE_CAPITAL)}多周期独立启动资金曲线报告",
        "",
        f"- 生成时间：2026-05-10",
        f"- 版本：`{OFFICIAL_STAGE78_VERSION}`",
        f"- 资金：`{ACTIVE_CAPITAL:,.0f}`",
        f"- sizing限制：{sizing_cap_text}",
        f"- 基础风险：`{BASE_RISK_RATIO}`",
        "- 口径：预热期只用于指标初始化，`trade_start_date` 固定为周期起点；曲线按周期起点从1.0归一化。",
        "",
        "## Summary",
        "",
        _format_table(summary_df),
        "",
        "## 输出文件",
        "",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in paths.items())
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Stage78 multiperiod equity-curve reports for a capital level.")
    parser.add_argument("--capital", type=float, default=OFFICIAL_STAGE78_CAPITAL)
    parser.add_argument(
        "--sizing-equity-cap",
        type=float,
        default=None,
        help="Override strategy sizing_equity_cap. Use 0 to disable the cap.",
    )
    parser.add_argument("--model-tag", default=MODEL_TAG)
    parser.add_argument("--output-prefix", default=OUTPUT_PREFIX)
    parser.add_argument("--report-stage", default=REPORT_STAGE)
    return parser.parse_args()


def main() -> None:
    global ACTIVE_CAPITAL, ACTIVE_SIZING_EQUITY_CAP, MODEL_TAG, OUTPUT_PREFIX, REPORT_STAGE

    args = parse_args()
    ACTIVE_CAPITAL = float(args.capital)
    ACTIVE_SIZING_EQUITY_CAP = None if args.sizing_equity_cap is None else float(args.sizing_equity_cap)
    MODEL_TAG = str(args.model_tag)
    OUTPUT_PREFIX = str(args.output_prefix)
    REPORT_STAGE = str(args.report_stage)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    summary_df, curves_df = run_windows()
    paths = {
        "html": str((OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.html").resolve()),
        "markdown": str((OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md").resolve()),
        "summary_csv": str((OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv").resolve()),
        "curves_csv": str((OUTPUT_DIR / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv").resolve()),
        "manifest": str((OUTPUT_DIR / f"{OUTPUT_PREFIX}_manifest_{MODEL_TAG}.json").resolve()),
    }
    summary_df.to_csv(paths["summary_csv"], index=False, encoding="utf-8-sig")
    curves_df.to_csv(paths["curves_csv"], index=False, encoding="utf-8-sig")
    Path(paths["html"]).write_text(build_html(summary_df, curves_df), encoding="utf-8")
    Path(paths["markdown"]).write_text(build_markdown(summary_df, paths), encoding="utf-8")
    Path(paths["manifest"]).write_text(
        json.dumps(
            {
                "model_tag": MODEL_TAG,
                "output_prefix": OUTPUT_PREFIX,
                "official_version": OFFICIAL_STAGE78_VERSION,
                "official_role": OFFICIAL_STAGE78_ROLE,
                "capital": ACTIVE_CAPITAL,
                "sizing_equity_cap": ACTIVE_SIZING_EQUITY_CAP,
                "base_risk_ratio": BASE_RISK_RATIO,
                "windows": [
                    {
                        "window_name": window_name,
                        "display_label": display_label,
                        "group": group,
                        "analysis_start": analysis_start.date().isoformat(),
                        "analysis_end": analysis_end.date().isoformat(),
                    }
                    for window_name, display_label, group, analysis_start, analysis_end in WINDOWS
                ],
                "paths": paths,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"[{REPORT_STAGE.lower()}] html: {paths['html']}")
    print(f"[{REPORT_STAGE.lower()}] markdown: {paths['markdown']}")
    print(f"[{REPORT_STAGE.lower()}] summary: {paths['summary_csv']}")
    print(summary_df.to_string(index=False))


if __name__ == "__main__":
    main()
