from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from qmt_universe import END_DT, START_DT
from run_qmt_roll_backtest import build_summary_row, run_backtest
from run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest import (
    BASE_RISK_RATIO,
    CORR20_06_08_FLOOR35_OVERRIDES,
)


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

MODEL_TAG: str = "ai_top8_multicycle_v1"
OUTPUT_PREFIX: str = "qmt_roll_ai_product_pool_multicycle_backtest"
ELIGIBILITY_PATH: Path = (
    OUTPUT_DIR / "qmt_roll_ai_product_pool_shadow_portfolio_eligibility_ai_product_pool_shadow_v1.csv"
)

SUMMARY_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
COMPARISON_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_comparison_{MODEL_TAG}.csv"
CURVES_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv"
SUMMARY_JSON_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.json"
REPORT_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

CAPITAL: float = 200_000.0

CYCLE_WINDOWS: tuple[dict[str, Any], ...] = (
    {
        "window_name": "full_2020_2026",
        "display_label": "全周期",
        "analysis_start": START_DT,
        "analysis_end": END_DT,
    },
    {
        "window_name": "pre_ai_2020_2021",
        "display_label": "AI生效前",
        "analysis_start": datetime(2020, 1, 1),
        "analysis_end": datetime(2021, 12, 31),
    },
    {
        "window_name": "post_signal_2022_2026",
        "display_label": "AI信号生效后",
        "analysis_start": datetime(2022, 2, 7),
        "analysis_end": END_DT,
    },
    {
        "window_name": "early_ai_2022_2023",
        "display_label": "AI早期样本",
        "analysis_start": datetime(2022, 2, 7),
        "analysis_end": datetime(2023, 12, 31),
    },
    {
        "window_name": "trend_rich_2024_2025",
        "display_label": "趋势富集期",
        "analysis_start": datetime(2024, 1, 1),
        "analysis_end": datetime(2025, 12, 31),
    },
    {
        "window_name": "latest_2026",
        "display_label": "最新尾部",
        "analysis_start": datetime(2026, 1, 1),
        "analysis_end": END_DT,
    },
)

STRATEGIES: tuple[dict[str, Any], ...] = (
    {
        "strategy_name": "baseline_floor35",
        "display_name": "Baseline Floor35",
        "strategy_overrides": CORR20_06_08_FLOOR35_OVERRIDES,
    },
    {
        "strategy_name": "ai_top8_product_pool",
        "display_name": "AI Top8 Product Pool",
        "strategy_overrides": {
            **CORR20_06_08_FLOOR35_OVERRIDES,
            "enable_ai_product_pool_filter": True,
            "ai_product_pool_eligibility_path": str(ELIGIBILITY_PATH),
            "ai_product_pool_strategy": "ai_top8_entry_filter",
        },
    },
)


def build_curve_frame(
    analysis_df: pd.DataFrame | None,
    *,
    window_name: str,
    strategy_name: str,
    analysis_start: datetime,
    analysis_end: datetime,
) -> pd.DataFrame:
    if analysis_df is None or analysis_df.empty:
        return pd.DataFrame()
    curve = analysis_df.reset_index().rename(columns={"index": "date"}).copy()
    curve["date"] = pd.to_datetime(curve["date"])
    first = curve.iloc[0]
    start_balance = float(first["balance"] - first["net_pnl"])
    if abs(start_balance) < 1e-9:
        start_balance = CAPITAL
    curve["normalized_nav"] = curve["balance"] / start_balance
    curve["window_name"] = window_name
    curve["strategy_name"] = strategy_name
    curve["analysis_start"] = analysis_start.date().isoformat()
    curve["analysis_end"] = analysis_end.date().isoformat()
    keep_columns = [
        "date",
        "window_name",
        "strategy_name",
        "analysis_start",
        "analysis_end",
        "balance",
        "normalized_nav",
        "net_pnl",
        "trade_count",
        "slippage",
        "drawdown",
        "ddpercent",
    ]
    return curve[[column for column in keep_columns if column in curve.columns]]


def run_multicycle_backtests() -> tuple[pd.DataFrame, pd.DataFrame]:
    rows: list[dict[str, Any]] = []
    curves: list[pd.DataFrame] = []

    for window in CYCLE_WINDOWS:
        window_name = str(window["window_name"])
        analysis_start = window["analysis_start"]
        analysis_end = window["analysis_end"]
        for strategy in STRATEGIES:
            strategy_name = str(strategy["strategy_name"])
            strategy_overrides = dict(strategy["strategy_overrides"])
            print(
                f"[ai-product-pool-multicycle] running {window_name} / {strategy_name}: "
                f"{analysis_start.date()} -> {analysis_end.date()}"
            )
            _, analysis_df, statistics = run_backtest(
                risk_ratio=BASE_RISK_RATIO,
                strategy_overrides=strategy_overrides,
                analysis_start=analysis_start,
                analysis_end=analysis_end,
                capital=CAPITAL,
                save_artifacts=False,
                include_start_year_sweep=False,
                file_prefix=f"{OUTPUT_PREFIX}_{window_name}_{strategy_name}",
                chart_title=f"QMT Roll {window_name} {strategy_name}",
            )
            rows.append(
                build_summary_row(
                    statistics,
                    analysis_start=analysis_start,
                    analysis_end=analysis_end,
                    window_name=window_name,
                    display_label=str(window["display_label"]),
                    strategy_name=strategy_name,
                    display_name=str(strategy["display_name"]),
                    strategy_overrides_json=json.dumps(strategy_overrides, ensure_ascii=False, sort_keys=True),
                    total_net_pnl=float(statistics.get("total_net_pnl", 0) or 0),
                    total_slippage=float(statistics.get("total_slippage", 0) or 0),
                    total_commission=float(statistics.get("total_commission", 0) or 0),
                    profit_days=int(statistics.get("profit_days", 0) or 0),
                    loss_days=int(statistics.get("loss_days", 0) or 0),
                )
            )
            curves.append(
                build_curve_frame(
                    analysis_df,
                    window_name=window_name,
                    strategy_name=strategy_name,
                    analysis_start=analysis_start,
                    analysis_end=analysis_end,
                )
            )

    summary = pd.DataFrame(rows).sort_values(["analysis_start", "strategy_name"]).reset_index(drop=True)
    curve_df = pd.concat([frame for frame in curves if not frame.empty], ignore_index=True)
    curve_df.sort_values(["window_name", "strategy_name", "date"], inplace=True)
    curve_df.reset_index(drop=True, inplace=True)
    return summary, curve_df


def build_comparison(summary: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for window_name, group in summary.groupby("window_name", sort=False):
        base_rows = group[group["strategy_name"] == "baseline_floor35"]
        ai_rows = group[group["strategy_name"] == "ai_top8_product_pool"]
        if base_rows.empty or ai_rows.empty:
            continue
        base = base_rows.iloc[0]
        ai = ai_rows.iloc[0]
        rows.append(
            {
                "window_name": window_name,
                "display_label": str(ai["display_label"]),
                "analysis_start": str(ai["analysis_start"]),
                "analysis_end": str(ai["analysis_end"]),
                "baseline_end_balance": float(base["end_balance"]),
                "ai_end_balance": float(ai["end_balance"]),
                "ai_end_balance_diff": float(ai["end_balance"] - base["end_balance"]),
                "baseline_total_return_pct": float(base["total_return_pct"]),
                "ai_total_return_pct": float(ai["total_return_pct"]),
                "ai_total_return_pct_diff": float(ai["total_return_pct"] - base["total_return_pct"]),
                "baseline_max_dd_percent": float(base["max_dd_percent"]),
                "ai_max_dd_percent": float(ai["max_dd_percent"]),
                "ai_max_dd_percent_diff": float(ai["max_dd_percent"] - base["max_dd_percent"]),
                "baseline_sharpe": float(base["sharpe_ratio"]),
                "ai_sharpe": float(ai["sharpe_ratio"]),
                "ai_sharpe_diff": float(ai["sharpe_ratio"] - base["sharpe_ratio"]),
                "baseline_trade_count": int(base["total_trade_count"]),
                "ai_trade_count": int(ai["total_trade_count"]),
                "ai_trade_count_diff": int(ai["total_trade_count"] - base["total_trade_count"]),
                "baseline_slippage": float(base["total_slippage"]),
                "ai_slippage": float(ai["total_slippage"]),
                "ai_slippage_diff": float(ai["total_slippage"] - base["total_slippage"]),
            }
        )
    return pd.DataFrame(rows).sort_values("analysis_start").reset_index(drop=True)


def to_markdown_table(df: pd.DataFrame) -> str:
    if df.empty:
        return "_empty_"
    view = df.copy()
    for column in view.columns:
        if pd.api.types.is_float_dtype(view[column]):
            view[column] = view[column].map(lambda value: f"{value:.4f}")
    header = "| " + " | ".join(view.columns) + " |"
    separator = "| " + " | ".join(["---"] * len(view.columns)) + " |"
    rows = ["| " + " | ".join(map(str, row)) + " |" for row in view.to_numpy()]
    return "\n".join([header, separator, *rows])


def build_report(summary: pd.DataFrame, comparison: pd.DataFrame) -> str:
    compact_comparison = comparison[
        [
            "window_name",
            "display_label",
            "analysis_start",
            "analysis_end",
            "ai_end_balance_diff",
            "ai_total_return_pct_diff",
            "ai_max_dd_percent_diff",
            "ai_sharpe_diff",
            "ai_trade_count_diff",
            "ai_slippage_diff",
        ]
    ].copy()
    compact_summary = summary[
        [
            "window_name",
            "strategy_name",
            "analysis_start",
            "analysis_end",
            "end_balance",
            "total_return_pct",
            "max_dd_percent",
            "sharpe_ratio",
            "total_trade_count",
            "total_slippage",
        ]
    ].copy()
    lines = [
        "# AI Product Pool Multicycle Backtest",
        "",
        "## Boundary",
        "",
        "- Fixed strategy: baseline Floor35 vs AI Top8 product-pool filter.",
        "- No model retraining and no TopN search.",
        "- Each period uses one-year warm-up context before the analysis window where possible.",
        "",
        "## AI vs Baseline By Cycle",
        "",
        to_markdown_table(compact_comparison),
        "",
        "## Raw Summary",
        "",
        to_markdown_table(compact_summary),
    ]
    return "\n".join(lines)


def main() -> None:
    if not ELIGIBILITY_PATH.exists():
        raise FileNotFoundError(f"missing AI product pool eligibility csv: {ELIGIBILITY_PATH}")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    summary, curves = run_multicycle_backtests()
    comparison = build_comparison(summary)

    summary.to_csv(SUMMARY_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    comparison.to_csv(COMPARISON_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    curves.to_csv(CURVES_OUTPUT_PATH, index=False, encoding="utf-8-sig")

    payload = {
        "model_tag": MODEL_TAG,
        "base_risk_ratio": BASE_RISK_RATIO,
        "capital": CAPITAL,
        "eligibility_path": str(ELIGIBILITY_PATH),
        "cycle_windows": [
            {
                **window,
                "analysis_start": window["analysis_start"].date().isoformat(),
                "analysis_end": window["analysis_end"].date().isoformat(),
            }
            for window in CYCLE_WINDOWS
        ],
        "comparison": comparison.to_dict(orient="records"),
        "artifacts": {
            "summary_csv": str(SUMMARY_OUTPUT_PATH),
            "comparison_csv": str(COMPARISON_OUTPUT_PATH),
            "curves_csv": str(CURVES_OUTPUT_PATH),
            "summary_json": str(SUMMARY_JSON_OUTPUT_PATH),
            "report_md": str(REPORT_OUTPUT_PATH),
        },
        "judgement": "Use multicycle results to judge whether AI Top8 improves the trend system across regimes without changing parameters.",
    }
    SUMMARY_JSON_OUTPUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_OUTPUT_PATH.write_text(build_report(summary, comparison), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
