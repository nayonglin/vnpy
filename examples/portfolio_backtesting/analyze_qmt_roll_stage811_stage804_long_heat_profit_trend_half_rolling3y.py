from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import replace
from datetime import datetime
import json
import os
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

import analyze_qmt_roll_stage513_stage208_exact_position_margin_audit as s513
import analyze_qmt_roll_stage650_stage526_200k_capital_reality_check as s650
import analyze_qmt_roll_stage772_am40_80_120_oi_monthly as s772
import analyze_qmt_roll_stage804_stage777_long_tighter_initial_stop_yearly as s804
import analyze_qmt_roll_stage808_stage806_rolling3y as s808
import analyze_qmt_roll_stage809_stage804_rolling3y as s809
import analyze_qmt_roll_stage810_stage804_long_heat_half_rolling3y as s810


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

MODEL_TAG = "stage811_stage804_long_heat_profit_trend_half_rolling3y_v2"
OUTPUT_PREFIX = "qmt_roll_stage811_stage804_long_heat_profit_trend_half_rolling3y"
LINE_ID = "futures_trend_2019_data_extension"

ROLL_YEARS = 3
MONTH_STARTS = s809.MONTH_STARTS
MAX_WORKERS = max(1, min(6, int(os.environ.get("STAGE811_MAX_WORKERS", "4"))))

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
CURVES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv"
AGG_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_aggregate_{MODEL_TAG}.csv"
YEAR_AGG_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_start_year_aggregate_{MODEL_TAG}.csv"
COMPARISON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_comparison_vs_stage804_806_810_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
RETURN_HEATMAP_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_return_heatmap_{MODEL_TAG}.png"
DD_HEATMAP_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_dd_heatmap_{MODEL_TAG}.png"
EQUITY_SELECTED_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_selected_equity_curves_{MODEL_TAG}.png"
RETURN_DELTA_STAGE804_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_return_delta_vs_stage804_heatmap_{MODEL_TAG}.png"
DD_DELTA_STAGE804_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_dd_delta_vs_stage804_heatmap_{MODEL_TAG}.png"
RETURN_DELTA_STAGE806_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_return_delta_vs_stage806_heatmap_{MODEL_TAG}.png"
DD_DELTA_STAGE806_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_dd_delta_vs_stage806_heatmap_{MODEL_TAG}.png"
RETURN_DELTA_STAGE810_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_return_delta_vs_stage810_heatmap_{MODEL_TAG}.png"
DD_DELTA_STAGE810_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_dd_delta_vs_stage810_heatmap_{MODEL_TAG}.png"


_WORKER_METADATA: dict[str, Any] | None = None


class QmtRollPortfolioStrategyLongHeatProfitTrendHalf(
    s810.QmtRollPortfolioStrategyLongHeatHalfDeleverage
):
    """
    Research-only Stage811:
    long heat is reduced by half only when the current holding is already profitable
    and the current MA20/MA40 trend still confirms the long thesis. Otherwise it
    falls back to the Stage804 full heat-layer deleverage.
    """

    long_heat_profit_trend_min_profit_pct: float = 0.05
    long_heat_profit_trend_ma_fast: int = 20
    long_heat_profit_trend_ma_slow: int = 40
    long_heat_profit_trend_slope_days: int = 3
    parameters = [
        *s810.QmtRollPortfolioStrategyLongHeatHalfDeleverage.parameters,
        "long_heat_profit_trend_min_profit_pct",
        "long_heat_profit_trend_ma_fast",
        "long_heat_profit_trend_ma_slow",
        "long_heat_profit_trend_slope_days",
    ]

    def _long_heat_profit_trend_confirmed(self, state: Any, bar: Any) -> bool:
        if str(getattr(state, "direction", "") or "").lower() != "long":
            return False
        if not getattr(state, "layers", None):
            return False

        close_price = float(getattr(bar, "close_price", 0.0) or 0.0)
        avg_entry = float(state.avg_entry_price() or 0.0)
        if close_price <= 0.0 or avg_entry <= 0.0 or close_price <= avg_entry:
            return False

        max_layer_profit = max(float(getattr(layer, "max_profit_pct", 0.0) or 0.0) for layer in state.layers)
        if max_layer_profit < max(0.0, float(self.long_heat_profit_trend_min_profit_pct or 0.0)):
            return False

        contract_vt_symbol = str(getattr(state, "contract_vt_symbol", "") or "")
        target_am = self.ams.get(contract_vt_symbol)
        if target_am is None or not target_am.inited:
            return False

        history = self._build_history_df(target_am)
        fast_window = max(int(self.long_heat_profit_trend_ma_fast or 0), 1)
        slow_window = max(int(self.long_heat_profit_trend_ma_slow or 0), fast_window + 1)
        slope_days = max(int(self.long_heat_profit_trend_slope_days or 0), 1)
        # We only need current MA40 and MA20 from `slope_days` bars ago.
        # With AM41, requiring MA40 + slope_days would make this condition
        # unreachable, while MA20[-1-slope_days] only needs 20+slope_days bars.
        need_bars = max(slow_window, fast_window + slope_days)
        if len(history) < need_bars:
            return False

        closes = pd.to_numeric(history["close"], errors="coerce")
        fast_ma = closes.rolling(fast_window).mean()
        slow_ma = closes.rolling(slow_window).mean()
        fast_now = float(fast_ma.iloc[-1]) if not pd.isna(fast_ma.iloc[-1]) else float("nan")
        fast_prev = float(fast_ma.iloc[-1 - slope_days]) if not pd.isna(fast_ma.iloc[-1 - slope_days]) else float("nan")
        slow_now = float(slow_ma.iloc[-1]) if not pd.isna(slow_ma.iloc[-1]) else float("nan")
        if not all(pd.notna(value) for value in [fast_now, fast_prev, slow_now, close_price]):
            return False
        return close_price > fast_now > slow_now and fast_now > fast_prev

    def _process_risk_cluster_heat_deleverage(self, state: Any, bar: Any) -> str:
        direction_text = str(getattr(state, "direction", "") or "").lower()
        if direction_text != "long":
            return s804.QmtRollPortfolioStrategyLongTighterInitialStop._process_risk_cluster_heat_deleverage(
                self, state, bar
            )
        if self._long_heat_profit_trend_confirmed(state, bar):
            return super()._process_risk_cluster_heat_deleverage(state, bar)
        return s804.QmtRollPortfolioStrategyLongTighterInitialStop._process_risk_cluster_heat_deleverage(
            self, state, bar
        )


def _json_safe(value: Any) -> Any:
    return s650._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s650._md_table(frame, max_rows=max_rows)


def _month_text(start: pd.Timestamp) -> str:
    return pd.Timestamp(start).strftime("%Y-%m")


def _window_end(start: pd.Timestamp) -> pd.Timestamp:
    return s809._window_end(start)


def _profile(metadata: dict[str, Any], start: pd.Timestamp, end: pd.Timestamp) -> dict[str, Any]:
    profile = s804._profile(metadata, start)
    spec = profile["spec"]
    start_text = _month_text(start)
    end_text = end.strftime("%Y_%m_%d")
    capital = replace(
        spec.capital,
        variant=f"stage811_stage804_long_heat_profit_trend_half_rolling3y_{start_text.replace('-', '_')}_to_{end_text}",
        label=f"Stage811 Stage804 long heat profit-trend half rolling3y {start_text} to {end.strftime('%Y-%m-%d')}",
        note=(
            f"{spec.capital.note} | Stage811 rolling 3y validation. "
            "Long risk-cluster heat halves only when holding is profitable and MA20/MA40 trend confirms."
        ),
    )
    overrides = {
        **spec.overrides,
        "long_tighter_initial_stop": True,
        "long_heat_partial_deleverage_ratio": 0.50,
        "long_heat_partial_deleverage_skip_one_lot": True,
        "long_heat_profit_trend_min_profit_pct": 0.05,
        "long_heat_profit_trend_ma_fast": 20,
        "long_heat_profit_trend_ma_slow": 40,
        "long_heat_profit_trend_slope_days": 3,
    }
    result = dict(profile)
    result["profile"] = "stage811_stage804_long_heat_profit_trend_half_rolling3y"
    result["strategy_cls"] = QmtRollPortfolioStrategyLongHeatProfitTrendHalf
    result["spec"] = replace(spec, capital=capital, overrides=overrides, profile=result["profile"])
    result["note"] = "Stage804 rolling three-year validation; long heat half only when profit and trend confirm."
    return result


def _run_one(start_text: str) -> tuple[dict[str, Any], pd.DataFrame]:
    global _WORKER_METADATA
    if _WORKER_METADATA is None:
        _WORKER_METADATA = s513._metadata()
    metadata = _WORKER_METADATA
    start = pd.Timestamp(start_text).normalize()
    end = _window_end(start)
    profile = _profile(metadata, start, end)
    base_c3_overrides = dict(s513._c3_overrides(MONTH_STARTS[0].to_pydatetime()))
    combined, frames = s808._run_profile(
        profile=profile,
        start=start,
        end=end,
        metadata=metadata,
        base_c3_overrides=base_c3_overrides,
    )
    summary, curve = s809._metric_from_combined(profile, combined, start, end)
    row = summary.iloc[0].to_dict()
    trade_events = frames.get("trade_events", pd.DataFrame()).copy()
    if trade_events.empty or "reason" not in trade_events.columns:
        row["long_heat_partial_deleverage_count"] = 0
        row["long_heat_partial_deleverage_closed_volume"] = 0
        row["long_heat_full_deleverage_count"] = 0
        row["long_heat_full_deleverage_closed_volume"] = 0
        row["short_heat_deleverage_exit_count"] = 0
    else:
        reason = trade_events["reason"].astype(str)
        offset = trade_events.get("offset", pd.Series("", index=trade_events.index)).astype(str)
        partial_mask = reason.eq("long_risk_cluster_heat_partial_deleverage") & offset.eq("Close")
        full_long_mask = reason.eq("long_risk_cluster_heat_deleverage") & offset.eq("Close")
        short_mask = reason.eq("short_risk_cluster_heat_deleverage") & offset.eq("Close")
        row["long_heat_partial_deleverage_count"] = int(partial_mask.sum())
        row["long_heat_partial_deleverage_closed_volume"] = int(
            pd.to_numeric(trade_events.loc[partial_mask, "volume"], errors="coerce").fillna(0).sum()
        )
        row["long_heat_full_deleverage_count"] = int(full_long_mask.sum())
        row["long_heat_full_deleverage_closed_volume"] = int(
            pd.to_numeric(trade_events.loc[full_long_mask, "volume"], errors="coerce").fillna(0).sum()
        )
        row["short_heat_deleverage_exit_count"] = int(short_mask.sum())
    return row, curve


def _aggregate(summary: pd.DataFrame) -> pd.DataFrame:
    aggregate = s808._aggregate(summary)
    for source_col, target_col in [
        ("long_heat_partial_deleverage_count", "total_long_heat_partial_deleverage_count"),
        ("long_heat_partial_deleverage_closed_volume", "total_long_heat_partial_deleverage_closed_volume"),
        ("long_heat_full_deleverage_count", "total_long_heat_full_deleverage_count"),
        ("long_heat_full_deleverage_closed_volume", "total_long_heat_full_deleverage_closed_volume"),
        ("short_heat_deleverage_exit_count", "total_short_heat_deleverage_exits"),
    ]:
        aggregate[target_col] = int(pd.to_numeric(summary.get(source_col, 0), errors="coerce").fillna(0).sum())
    return aggregate


def _year_aggregate(summary: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for start_year, group in summary.groupby("start_year", sort=True):
        returns = pd.to_numeric(group["rebased_total_return_pct"], errors="coerce")
        dds = pd.to_numeric(group["rebased_max_dd_pct"], errors="coerce")
        rows.append(
            {
                "start_year": int(start_year),
                "window_count": int(len(group)),
                "positive_count": int((returns > 0).sum()),
                "median_return_pct": float(returns.median()),
                "min_return_pct": float(returns.min()),
                "p10_return_pct": float(returns.quantile(0.10)),
                "median_dd_pct": float(dds.median()),
                "worst_dd_pct": float(dds.min()),
                "dd40_fail_count": int((dds < -40.0).sum()),
                "dd50_fail_count": int((dds < -50.0).sum()),
                "dd60_fail_count": int((dds < -60.0).sum()),
                "median_sharpe": float(pd.to_numeric(group["rebased_sharpe"], errors="coerce").median()),
                "total_long_heat_partial_count": int(
                    pd.to_numeric(group.get("long_heat_partial_deleverage_count", 0), errors="coerce").fillna(0).sum()
                ),
                "total_long_heat_full_count": int(
                    pd.to_numeric(group.get("long_heat_full_deleverage_count", 0), errors="coerce").fillna(0).sum()
                ),
            }
        )
    return pd.DataFrame(rows)


def _compare_one(summary: pd.DataFrame, base_path: Path, suffix: str) -> pd.DataFrame:
    if not base_path.exists():
        return pd.DataFrame()
    base = pd.read_csv(base_path)
    keys = ["start_month", "window_end"]
    left = summary.copy()
    right = base.copy()
    for key in keys:
        left[key] = left[key].astype(str)
        right[key] = right[key].astype(str)
    comparison = left.merge(
        right[
            [
                *keys,
                "rebased_total_return_pct",
                "rebased_max_dd_pct",
                "rebased_sharpe",
                "total_trade_count",
            ]
        ],
        on=keys,
        how="left",
        suffixes=("", f"_{suffix}"),
    )
    comparison[f"return_pct_delta_vs_{suffix}"] = (
        pd.to_numeric(comparison["rebased_total_return_pct"], errors="coerce")
        - pd.to_numeric(comparison[f"rebased_total_return_pct_{suffix}"], errors="coerce")
    )
    comparison[f"max_dd_pct_delta_vs_{suffix}"] = (
        pd.to_numeric(comparison["rebased_max_dd_pct"], errors="coerce")
        - pd.to_numeric(comparison[f"rebased_max_dd_pct_{suffix}"], errors="coerce")
    )
    comparison[f"sharpe_delta_vs_{suffix}"] = (
        pd.to_numeric(comparison["rebased_sharpe"], errors="coerce")
        - pd.to_numeric(comparison[f"rebased_sharpe_{suffix}"], errors="coerce")
    )
    return comparison


def _comparison(summary: pd.DataFrame) -> pd.DataFrame:
    comparisons = [
        _compare_one(summary, s809.SUMMARY_PATH, "stage804"),
        _compare_one(summary, s808.SUMMARY_PATH, "stage806"),
        _compare_one(summary, s810.SUMMARY_PATH, "stage810"),
    ]
    comparisons = [item for item in comparisons if not item.empty]
    if not comparisons:
        return pd.DataFrame()
    result = comparisons[0]
    keys = ["start_month", "window_end"]
    for comp in comparisons[1:]:
        extra_cols = [col for col in comp.columns if col not in result.columns or col in keys]
        result = result.merge(comp[extra_cols], on=keys, how="left")
    return result


def _comparison_stats(comparison: pd.DataFrame) -> dict[str, Any]:
    stats: dict[str, Any] = {}
    if comparison.empty:
        return stats
    for suffix in ["stage804", "stage806", "stage810"]:
        ret_col = f"return_pct_delta_vs_{suffix}"
        dd_col = f"max_dd_pct_delta_vs_{suffix}"
        base_dd_col = f"rebased_max_dd_pct_{suffix}"
        if ret_col not in comparison.columns:
            continue
        ret_delta = pd.to_numeric(comparison[ret_col], errors="coerce")
        dd_delta = pd.to_numeric(comparison[dd_col], errors="coerce")
        stats[f"return_win_vs_{suffix}_count"] = int((ret_delta > 0).sum())
        stats[f"dd_win_vs_{suffix}_count"] = int((dd_delta > 0).sum())
        stats[f"median_return_delta_vs_{suffix}_pp"] = float(ret_delta.median())
        stats[f"median_dd_delta_vs_{suffix}_pp"] = float(dd_delta.median())
        stats[f"dd50_fail_{suffix}_count"] = int((pd.to_numeric(comparison[base_dd_col], errors="coerce") < -50.0).sum())
    stats["dd50_fail_stage811_count"] = int((pd.to_numeric(comparison["rebased_max_dd_pct"], errors="coerce") < -50.0).sum())
    stats["dd60_fail_stage811_count"] = int((pd.to_numeric(comparison["rebased_max_dd_pct"], errors="coerce") < -60.0).sum())
    return stats


def _plot_selected_equity(curves: pd.DataFrame, summary: pd.DataFrame) -> None:
    selected: set[str] = set()
    for column, ascending, count in [
        ("rebased_total_return_pct", True, 3),
        ("rebased_total_return_pct", False, 3),
        ("rebased_max_dd_pct", True, 4),
    ]:
        for _, row in summary.sort_values(column, ascending=ascending).head(count).iterrows():
            selected.add(str(row["start_month"]))
    for month in ["2018-01", "2019-01", "2020-01", "2021-01", "2022-01", "2023-01", "2023-05"]:
        if month in set(summary["start_month"].astype(str)):
            selected.add(month)
    data = curves[curves["start_month"].astype(str).isin(sorted(selected))].copy()
    fig, ax = plt.subplots(figsize=(16, 8))
    colors = plt.cm.tab20.colors
    for idx, (start_month, group) in enumerate(data.groupby("start_month", sort=True)):
        group = group.sort_values("date")
        ax.plot(
            pd.to_datetime(group["date"]),
            pd.to_numeric(group["rebased_equity"], errors="coerce") / 1_000_000,
            label=f"{start_month} -> {str(group['window_end'].iloc[0])}",
            linewidth=1.5,
            color=colors[idx % len(colors)],
            alpha=0.9,
        )
    ax.axhline(0.5, color="#9ca3af", linestyle="--", linewidth=1)
    ax.set_title("Stage811 profit-trend long heat half selected rolling 3y equity curves")
    ax.set_xlabel("Date")
    ax.set_ylabel("Account equity")
    ax.yaxis.set_major_formatter(lambda x, pos: f"{x:.1f}M")
    ax.grid(alpha=0.25)
    ax.legend(ncol=3, fontsize=8)
    fig.tight_layout()
    fig.savefig(EQUITY_SELECTED_PATH, dpi=180)
    plt.close(fig)


def _plot_delta(comparison: pd.DataFrame, column: str, path: Path, title: str) -> None:
    if column not in comparison.columns:
        return
    s809._plot_heatmap(
        comparison.rename(columns={column: "stage811_delta"}),
        "stage811_delta",
        path,
        title,
        "RdYlGn",
        0.0,
    )


def _write_report(
    summary: pd.DataFrame,
    aggregate: pd.DataFrame,
    year_agg: pd.DataFrame,
    comparison: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    lines = [
        "# Stage811 Stage804 盈利趋势确认 long heat 半仓滚动3年多周期回测",
        "",
        f"- line_id：`{LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        f"- 完整三年起点：`{MONTH_STARTS[0].strftime('%Y-%m')}` 到 `{MONTH_STARTS[-1].strftime('%Y-%m')}`，共 `{len(MONTH_STARTS)}` 个。",
        "- 口径：Stage804 多头更紧初始止损；long heat 触发时，只有 `close > avg_entry`、历史最大浮盈 >=5%、`close > MA20 > MA40` 且 MA20 高于3日前时才半平；否则回到 Stage804 全平 heat 层；空头 heat 不改。",
        "- 窗口定义：每个起点独立跑三年，结束日为 `start + 3 years - 1 day`。",
        "",
        "## Aggregate",
        "",
        _md_table(aggregate, max_rows=10),
        "",
        "## Start Year Aggregate",
        "",
        _md_table(year_agg, max_rows=20),
        "",
        "## Worst DD Windows",
        "",
        _md_table(
            summary.sort_values("rebased_max_dd_pct")[
                [
                    "start_month",
                    "window_end",
                    "rebased_total_return_pct",
                    "rebased_max_dd_pct",
                    "rebased_sharpe",
                    "total_trade_count",
                    "long_heat_partial_deleverage_count",
                    "long_heat_full_deleverage_count",
                ]
            ].head(12),
            max_rows=12,
        ),
        "",
        "## Worst Return Windows",
        "",
        _md_table(
            summary.sort_values("rebased_total_return_pct")[
                [
                    "start_month",
                    "window_end",
                    "rebased_total_return_pct",
                    "rebased_max_dd_pct",
                    "rebased_sharpe",
                    "total_trade_count",
                    "long_heat_partial_deleverage_count",
                    "long_heat_full_deleverage_count",
                ]
            ].head(12),
            max_rows=12,
        ),
    ]
    if not comparison.empty:
        display_cols = [
            "start_month",
            "window_end",
            "rebased_total_return_pct",
            "rebased_max_dd_pct",
            "return_pct_delta_vs_stage804",
            "max_dd_pct_delta_vs_stage804",
            "return_pct_delta_vs_stage810",
            "max_dd_pct_delta_vs_stage810",
            "return_pct_delta_vs_stage806",
            "max_dd_pct_delta_vs_stage806",
            "long_heat_partial_deleverage_count",
            "long_heat_full_deleverage_count",
        ]
        display_cols = [col for col in display_cols if col in comparison.columns]
        lines.extend(
            [
                "",
                "## Comparison",
                "",
                _md_table(comparison[display_cols].sort_values("return_pct_delta_vs_stage804").head(15), max_rows=15),
            ]
        )
    lines.extend(
        [
            "",
            "## Decision",
            "",
            f"- 决策：`{decision['decision']}`",
            f"- 判断：{decision['judgment']}",
            f"- 过拟合反思：{decision['overfit_judgment']}",
            f"- 继续价值：{decision['continue_value']}",
        ]
    )
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    tasks = [start.strftime("%Y-%m-%d") for start in MONTH_STARTS]
    rows: list[dict[str, Any]] = []
    curves: list[pd.DataFrame] = []
    print(f"[stage811] launching profit-trend long heat half rolling3y runs={len(tasks)} workers={MAX_WORKERS}", flush=True)
    if MAX_WORKERS == 1:
        for idx, task in enumerate(tasks, start=1):
            print(f"[stage811] running {idx}/{len(tasks)} {task}", flush=True)
            row, curve = _run_one(task)
            rows.append(row)
            curves.append(curve)
    else:
        with ProcessPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_map = {executor.submit(_run_one, task): task for task in tasks}
            for idx, future in enumerate(as_completed(future_map), start=1):
                task = future_map[future]
                row, curve = future.result()
                rows.append(row)
                curves.append(curve)
                print(f"[stage811] completed {idx}/{len(tasks)} {task}", flush=True)

    summary = s772._add_month_fields(pd.DataFrame(rows)).sort_values("start_month").reset_index(drop=True)
    curves_all = pd.concat(curves, ignore_index=True, sort=False).sort_values(["start_month", "date"]).reset_index(drop=True)
    aggregate = _aggregate(summary)
    year_agg = _year_aggregate(summary)
    comparison = _comparison(summary)
    comparison_stats = _comparison_stats(comparison)

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    curves_all.to_csv(CURVES_PATH, index=False, encoding="utf-8-sig")
    aggregate.to_csv(AGG_PATH, index=False, encoding="utf-8-sig")
    year_agg.to_csv(YEAR_AGG_PATH, index=False, encoding="utf-8-sig")
    comparison.to_csv(COMPARISON_PATH, index=False, encoding="utf-8-sig")
    s809._plot_heatmap(summary, "rebased_total_return_pct", RETURN_HEATMAP_PATH, "Stage811 profit-trend long heat half rolling 3y return %", "RdYlGn", 0.0)
    s809._plot_heatmap(summary, "rebased_max_dd_pct", DD_HEATMAP_PATH, "Stage811 profit-trend long heat half rolling 3y max DD %", "RdYlGn", -40.0)
    _plot_selected_equity(curves_all, summary)
    if not comparison.empty:
        _plot_delta(comparison, "return_pct_delta_vs_stage804", RETURN_DELTA_STAGE804_PATH, "Stage811 - Stage804 rolling 3y return delta pp")
        _plot_delta(comparison, "max_dd_pct_delta_vs_stage804", DD_DELTA_STAGE804_PATH, "Stage811 - Stage804 rolling 3y max DD delta pp")
        _plot_delta(comparison, "return_pct_delta_vs_stage806", RETURN_DELTA_STAGE806_PATH, "Stage811 - Stage806 rolling 3y return delta pp")
        _plot_delta(comparison, "max_dd_pct_delta_vs_stage806", DD_DELTA_STAGE806_PATH, "Stage811 - Stage806 rolling 3y max DD delta pp")
        _plot_delta(comparison, "return_pct_delta_vs_stage810", RETURN_DELTA_STAGE810_PATH, "Stage811 - Stage810 rolling 3y return delta pp")
        _plot_delta(comparison, "max_dd_pct_delta_vs_stage810", DD_DELTA_STAGE810_PATH, "Stage811 - Stage810 rolling 3y max DD delta pp")

    decision = {
        "stage": "Stage811",
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "decision": "stage811_stage804_profit_trend_long_heat_half_rolling3y_completed",
        "judgment": (
            "This tests a conditional heat sleeve: long heat halves only for already-profitable positions "
            "whose MA20/MA40 trend still confirms; otherwise Stage804 full heat-layer deleverage remains."
        ),
        "aggregate": aggregate.iloc[0].to_dict(),
        "year_aggregate": year_agg.to_dict("records"),
        "comparison_stats": comparison_stats,
        "outputs": {
            "summary": str(SUMMARY_PATH),
            "curves": str(CURVES_PATH),
            "aggregate": str(AGG_PATH),
            "year_aggregate": str(YEAR_AGG_PATH),
            "comparison": str(COMPARISON_PATH),
            "return_heatmap": str(RETURN_HEATMAP_PATH),
            "dd_heatmap": str(DD_HEATMAP_PATH),
            "selected_equity": str(EQUITY_SELECTED_PATH),
            "return_delta_stage804": str(RETURN_DELTA_STAGE804_PATH),
            "dd_delta_stage804": str(DD_DELTA_STAGE804_PATH),
            "return_delta_stage806": str(RETURN_DELTA_STAGE806_PATH),
            "dd_delta_stage806": str(DD_DELTA_STAGE806_PATH),
            "return_delta_stage810": str(RETURN_DELTA_STAGE810_PATH),
            "dd_delta_stage810": str(DD_DELTA_STAGE810_PATH),
            "report": str(REPORT_PATH),
        },
        "overfit_judgment": (
            "low-to-medium before results: uses existing 5% profit-lock semantics and MA20/MA40 trend confirmation; "
            "no product/year/month/ratio sweep."
        ),
        "continue_value": (
            "yes as a structural test of whether Stage810's unconditional half-close should be restricted to "
            "profitable confirmed trends."
        ),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_report(summary, aggregate, year_agg, comparison, decision)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print("aggregate")
    print(aggregate.to_string(index=False))
    print("start year aggregate")
    print(year_agg.to_string(index=False))
    if comparison_stats:
        print("comparison stats")
        print(pd.DataFrame([comparison_stats]).to_string(index=False))
    print("worst dd")
    print(
        summary.sort_values("rebased_max_dd_pct")[
            [
                "start_month",
                "window_end",
                "rebased_total_return_pct",
                "rebased_max_dd_pct",
                "rebased_sharpe",
                "total_trade_count",
                "long_heat_partial_deleverage_count",
                "long_heat_full_deleverage_count",
            ]
        ]
        .head(12)
        .to_string(index=False)
    )


if __name__ == "__main__":
    main()
