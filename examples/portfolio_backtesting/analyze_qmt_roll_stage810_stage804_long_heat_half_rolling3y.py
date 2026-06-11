from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import replace
from datetime import datetime
import json
import math
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


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

MODEL_TAG = "stage810_stage804_long_heat_half_rolling3y_v1"
OUTPUT_PREFIX = "qmt_roll_stage810_stage804_long_heat_half_rolling3y"
LINE_ID = "futures_trend_2019_data_extension"

DATA_END = pd.Timestamp("2026-05-29")
ROLL_YEARS = 3
MONTH_STARTS = s809.MONTH_STARTS
MAX_WORKERS = max(1, min(6, int(os.environ.get("STAGE810_MAX_WORKERS", "4"))))

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
CURVES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv"
AGG_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_aggregate_{MODEL_TAG}.csv"
YEAR_AGG_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_start_year_aggregate_{MODEL_TAG}.csv"
COMPARISON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_comparison_vs_stage804_806_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
RETURN_HEATMAP_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_return_heatmap_{MODEL_TAG}.png"
DD_HEATMAP_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_dd_heatmap_{MODEL_TAG}.png"
EQUITY_SELECTED_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_selected_equity_curves_{MODEL_TAG}.png"
RETURN_DELTA_STAGE804_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_return_delta_vs_stage804_heatmap_{MODEL_TAG}.png"
DD_DELTA_STAGE804_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_dd_delta_vs_stage804_heatmap_{MODEL_TAG}.png"
RETURN_DELTA_STAGE806_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_return_delta_vs_stage806_heatmap_{MODEL_TAG}.png"
DD_DELTA_STAGE806_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_dd_delta_vs_stage806_heatmap_{MODEL_TAG}.png"


_WORKER_METADATA: dict[str, Any] | None = None


class QmtRollPortfolioStrategyLongHeatHalfDeleverage(
    s804.QmtRollPortfolioStrategyLongTighterInitialStop
):
    """
    Research-only wrapper:
    keep Stage804 triggers, but long risk-cluster heat reduces a position by half once per holding.
    Shorts retain the inherited full heat deleverage behavior.
    """

    long_heat_partial_deleverage_ratio: float = 0.50
    long_heat_partial_deleverage_skip_one_lot: bool = True
    parameters = [
        *s804.QmtRollPortfolioStrategyLongTighterInitialStop.parameters,
        "long_heat_partial_deleverage_ratio",
        "long_heat_partial_deleverage_skip_one_lot",
    ]

    def __init__(self, strategy_engine: Any, strategy_name: str, vt_symbols: list[str], setting: dict[str, Any]) -> None:
        super().__init__(strategy_engine, strategy_name, vt_symbols, setting)
        self.stage810_long_heat_partial_keys: set[tuple[str, str, str, str]] = set()

    def _long_heat_position_key(self, state: Any) -> tuple[str, str, str, str]:
        return (
            str(getattr(state, "product_vt_symbol", "") or ""),
            str(getattr(state, "contract_vt_symbol", "") or ""),
            str(getattr(state, "direction", "") or ""),
            str(getattr(state, "entry_date", "") or ""),
        )

    def _process_risk_cluster_heat_deleverage(self, state: Any, bar: Any) -> str:
        direction_text = str(getattr(state, "direction", "") or "").lower()
        if direction_text != "long":
            return super()._process_risk_cluster_heat_deleverage(state, bar)
        if not self.enable_risk_cluster_heat_deleverage:
            return ""
        if not state.layers or not state.contract_vt_symbol:
            return ""

        cluster = self._risk_cluster_for_symbol(state.contract_vt_symbol)
        if not self._risk_cluster_heat_deleverage_cluster_applies(cluster):
            return ""

        use_snapshot = bool(self.risk_cluster_heat_deleverage_use_daily_snapshot)
        if use_snapshot and self.risk_cluster_heat_deleverage_snapshot_requires_same_direction_multi:
            use_snapshot = bool(self.risk_cluster_same_direction_multi_snapshot.get(cluster, False))

        if use_snapshot:
            heat_pressure = float(self.risk_cluster_heat_pressure_snapshot.get(cluster, 0.0) or 0.0)
        else:
            heat_fields = self._risk_cluster_heat_pressure_fields(cluster, projected_margin=0.0, enabled=True)
            heat_pressure = float(heat_fields["risk_cluster_heat_pressure"] or 0.0)
        if heat_pressure < max(0.0, float(self.risk_cluster_heat_deleverage_min_pressure or 0.0)):
            return ""

        layer_kinds = self._risk_cluster_heat_deleverage_layer_kind_set()
        triggered_indexes = [index for index, layer in enumerate(state.layers) if layer.kind in layer_kinds]
        if not triggered_indexes:
            return ""

        current_volume = int(state.active_volume())
        if current_volume <= 0:
            return ""
        if bool(self.long_heat_partial_deleverage_skip_one_lot) and current_volume <= 1:
            return ""

        key = self._long_heat_position_key(state)
        if key in self.stage810_long_heat_partial_keys:
            return ""

        ratio = min(0.99, max(0.0, float(self.long_heat_partial_deleverage_ratio or 0.0)))
        if ratio <= 0.0:
            return ""
        reduce_volume = int(math.floor(current_volume * ratio))
        if reduce_volume <= 0:
            return ""
        if reduce_volume >= current_volume:
            reduce_volume = current_volume - 1
        if reduce_volume <= 0:
            return ""

        target_volume = max(1, current_volume - reduce_volume)
        exit_price = float(bar.close_price)
        contract_vt_symbol = state.contract_vt_symbol
        product_vt_symbol = state.product_vt_symbol
        exit_reason = "long_risk_cluster_heat_partial_deleverage"
        self._record_trade_event(
            bar=bar,
            contract_vt_symbol=contract_vt_symbol,
            product_vt_symbol=product_vt_symbol,
            position_direction="long",
            offset="Close",
            reason=exit_reason,
            volume=reduce_volume,
            price=exit_price,
        )
        self._reduce_position_to_target(state, target_volume, exit_price)
        self.risk_cluster_heat_deleverage_count += 1
        self.stage810_long_heat_partial_keys.add(key)
        if state.layers:
            self._apply_state_target(state, execution_price_override=exit_price)
        else:
            if exit_price > 0:
                self.execution_price_overrides[contract_vt_symbol] = exit_price
            self.set_target(contract_vt_symbol, 0)
        return exit_reason


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
        variant=f"stage810_stage804_long_heat_half_rolling3y_{start_text.replace('-', '_')}_to_{end_text}",
        label=f"Stage810 Stage804 long heat half rolling3y {start_text} to {end.strftime('%Y-%m-%d')}",
        note=(
            f"{spec.capital.note} | Stage810 rolling 3y validation. "
            "Long risk-cluster heat reduces once by 50% instead of closing heat layers completely."
        ),
    )
    overrides = {
        **spec.overrides,
        "long_tighter_initial_stop": True,
        "long_heat_partial_deleverage_ratio": 0.50,
        "long_heat_partial_deleverage_skip_one_lot": True,
    }
    result = dict(profile)
    result["profile"] = "stage810_stage804_long_heat_half_rolling3y"
    result["strategy_cls"] = QmtRollPortfolioStrategyLongHeatHalfDeleverage
    result["spec"] = replace(spec, capital=capital, overrides=overrides, profile=result["profile"])
    result["note"] = "Stage804 rolling three-year validation; long heat partial 50% once per holding."
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
        row["short_heat_deleverage_exit_count"] = int(short_mask.sum())
    return row, curve


def _aggregate(summary: pd.DataFrame) -> pd.DataFrame:
    aggregate = s808._aggregate(summary)
    aggregate["total_long_heat_partial_deleverage_count"] = int(
        pd.to_numeric(summary.get("long_heat_partial_deleverage_count", 0), errors="coerce").fillna(0).sum()
    )
    aggregate["total_long_heat_partial_deleverage_closed_volume"] = int(
        pd.to_numeric(summary.get("long_heat_partial_deleverage_closed_volume", 0), errors="coerce").fillna(0).sum()
    )
    aggregate["total_long_heat_full_deleverage_count"] = int(
        pd.to_numeric(summary.get("long_heat_full_deleverage_count", 0), errors="coerce").fillna(0).sum()
    )
    aggregate["total_short_heat_deleverage_exits"] = int(
        pd.to_numeric(summary.get("short_heat_deleverage_exit_count", 0), errors="coerce").fillna(0).sum()
    )
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
                "total_long_heat_partial_closed_volume": int(
                    pd.to_numeric(group.get("long_heat_partial_deleverage_closed_volume", 0), errors="coerce").fillna(0).sum()
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
    comp804 = _compare_one(summary, s809.SUMMARY_PATH, "stage804")
    comp806 = _compare_one(summary, s808.SUMMARY_PATH, "stage806")
    if comp804.empty:
        return comp806
    if comp806.empty:
        return comp804
    keys = ["start_month", "window_end"]
    extra806 = [
        *keys,
        "rebased_total_return_pct_stage806",
        "rebased_max_dd_pct_stage806",
        "rebased_sharpe_stage806",
        "total_trade_count_stage806",
        "return_pct_delta_vs_stage806",
        "max_dd_pct_delta_vs_stage806",
        "sharpe_delta_vs_stage806",
    ]
    return comp804.merge(comp806[extra806], on=keys, how="left")


def _comparison_stats(comparison: pd.DataFrame) -> dict[str, Any]:
    stats: dict[str, Any] = {}
    if comparison.empty:
        return stats
    for suffix in ["stage804", "stage806"]:
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
    stats["dd50_fail_stage810_count"] = int((pd.to_numeric(comparison["rebased_max_dd_pct"], errors="coerce") < -50.0).sum())
    stats["dd60_fail_stage810_count"] = int((pd.to_numeric(comparison["rebased_max_dd_pct"], errors="coerce") < -60.0).sum())
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
    ax.set_title("Stage810 Stage804 long heat half selected rolling 3y equity curves")
    ax.set_xlabel("Date")
    ax.set_ylabel("Account equity")
    ax.yaxis.set_major_formatter(lambda x, pos: f"{x:.1f}M")
    ax.grid(alpha=0.25)
    ax.legend(ncol=3, fontsize=8)
    fig.tight_layout()
    fig.savefig(EQUITY_SELECTED_PATH, dpi=180)
    plt.close(fig)


def _write_report(
    summary: pd.DataFrame,
    aggregate: pd.DataFrame,
    year_agg: pd.DataFrame,
    comparison: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    lines = [
        "# Stage810 Stage804 long heat半仓滚动3年多周期回测",
        "",
        f"- line_id：`{LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        f"- 完整三年起点：`{MONTH_STARTS[0].strftime('%Y-%m')}` 到 `{MONTH_STARTS[-1].strftime('%Y-%m')}`，共 `{len(MONTH_STARTS)}` 个。",
        "- 口径：Stage804 多头更紧初始止损；long risk-cluster heat 触发后单次减仓50%，1手不动；空头 heat 不改。",
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
                    "long_heat_partial_deleverage_closed_volume",
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
                    "long_heat_partial_deleverage_closed_volume",
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
            "return_pct_delta_vs_stage806",
            "max_dd_pct_delta_vs_stage806",
            "long_heat_partial_deleverage_count",
            "long_heat_partial_deleverage_closed_volume",
        ]
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
    print(f"[stage810] launching Stage804 long heat half rolling3y runs={len(tasks)} workers={MAX_WORKERS}", flush=True)
    if MAX_WORKERS == 1:
        for idx, task in enumerate(tasks, start=1):
            print(f"[stage810] running {idx}/{len(tasks)} {task}", flush=True)
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
                print(f"[stage810] completed {idx}/{len(tasks)} {task}", flush=True)

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
    s809._plot_heatmap(summary, "rebased_total_return_pct", RETURN_HEATMAP_PATH, "Stage810 Stage804 long heat half rolling 3y return %", "RdYlGn", 0.0)
    s809._plot_heatmap(summary, "rebased_max_dd_pct", DD_HEATMAP_PATH, "Stage810 Stage804 long heat half rolling 3y max DD %", "RdYlGn", -40.0)
    _plot_selected_equity(curves_all, summary)
    if not comparison.empty:
        s809._plot_heatmap(
            comparison.rename(columns={"return_pct_delta_vs_stage804": "stage810_delta"}),
            "stage810_delta",
            RETURN_DELTA_STAGE804_PATH,
            "Stage810 - Stage804 rolling 3y return delta pp",
            "RdYlGn",
            0.0,
        )
        s809._plot_heatmap(
            comparison.rename(columns={"max_dd_pct_delta_vs_stage804": "stage810_delta"}),
            "stage810_delta",
            DD_DELTA_STAGE804_PATH,
            "Stage810 - Stage804 rolling 3y max DD delta pp",
            "RdYlGn",
            0.0,
        )
        s809._plot_heatmap(
            comparison.rename(columns={"return_pct_delta_vs_stage806": "stage810_delta"}),
            "stage810_delta",
            RETURN_DELTA_STAGE806_PATH,
            "Stage810 - Stage806 rolling 3y return delta pp",
            "RdYlGn",
            0.0,
        )
        s809._plot_heatmap(
            comparison.rename(columns={"max_dd_pct_delta_vs_stage806": "stage810_delta"}),
            "stage810_delta",
            DD_DELTA_STAGE806_PATH,
            "Stage810 - Stage806 rolling 3y max DD delta pp",
            "RdYlGn",
            0.0,
        )

    decision = {
        "stage": "Stage810",
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "decision": "stage810_stage804_long_heat_half_rolling3y_completed",
        "judgment": (
            "This tests whether replacing binary long heat exits with a one-shot 50% reduction can preserve "
            "right-tail participation while keeping the Stage804/Stage806 drawdown problem under control."
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
            "report": str(REPORT_PATH),
        },
        "overfit_judgment": (
            "low before results: one fixed 50% structural reduction, no year/month/product/threshold tuning."
        ),
        "continue_value": (
            "yes for deciding whether heat should be binary or sleeve-like; no value in sweeping 30/50/70 before "
            "comparing the single fixed version."
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
                "long_heat_partial_deleverage_closed_volume",
            ]
        ]
        .head(12)
        .to_string(index=False)
    )


if __name__ == "__main__":
    main()
