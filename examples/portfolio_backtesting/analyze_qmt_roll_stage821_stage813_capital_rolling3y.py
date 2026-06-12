from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import replace
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
import analyze_qmt_roll_stage748_half_risk_no_streak_500k as s748
import analyze_qmt_roll_stage772_am40_80_120_oi_monthly as s772
import analyze_qmt_roll_stage808_stage806_rolling3y as s808
import analyze_qmt_roll_stage813_stage804_rsi_partial_exit_ablation_yearly as s813


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

MODEL_TAG = "stage821_stage813_capital_rolling3y_v1"
OUTPUT_PREFIX = "qmt_roll_stage821_stage813_capital_rolling3y"
LINE_ID = "futures_trend_2019_data_extension"

DATA_END = pd.Timestamp("2026-05-29")
ROLL_YEARS = 3
MAX_WORKERS = max(1, min(6, int(os.environ.get("STAGE821_MAX_WORKERS", "4"))))

CAPITALS = [
    ("50w", 500_000.0, "Stage813 50w", "#1d4ed8", 1.25),
    ("30w", 300_000.0, "Stage819 30w", "#16a34a", 1.35),
    ("20w", 200_000.0, "Stage817 20w", "#dc2626", 1.25),
]

WINDOWS = [
    ("2018_2021", pd.Timestamp("2018-01-01"), pd.Timestamp("2020-12-31")),
    ("2019_2022", pd.Timestamp("2019-01-01"), pd.Timestamp("2021-12-31")),
    ("2020_2023", pd.Timestamp("2020-01-01"), pd.Timestamp("2022-12-31")),
    ("2021_2024", pd.Timestamp("2021-01-01"), pd.Timestamp("2023-12-31")),
    ("2022_2025", pd.Timestamp("2022-01-01"), pd.Timestamp("2024-12-31")),
    ("2023_2026", pd.Timestamp("2023-01-01"), pd.Timestamp("2025-12-31")),
    ("2023_06_2026_05", pd.Timestamp("2023-06-01"), DATA_END),
]

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
CURVES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv"
COMPARISON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_comparison_{MODEL_TAG}.csv"
PAIRWISE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_pairwise_{MODEL_TAG}.csv"
AGG_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_aggregate_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
ABSOLUTE_CURVES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_absolute_curves_{MODEL_TAG}.png"
NORMALIZED_CURVES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_normalized_curves_{MODEL_TAG}.png"

_WORKER_METADATA: dict[str, Any] | None = None


def _json_safe(value: Any) -> Any:
    return s650._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s650._md_table(frame, max_rows=max_rows)


def _month_text(value: pd.Timestamp) -> str:
    return pd.Timestamp(value).strftime("%Y-%m")


def _window_name(window_id: str) -> str:
    return f"{window_id}_rolling3y"


def _window_label(start: pd.Timestamp, end: pd.Timestamp) -> str:
    return f"{_month_text(start)} to {end.strftime('%Y-%m-%d')}"


def _capital_profile(
    metadata: dict[str, Any],
    *,
    capital_key: str,
    capital_value: float,
    display_label: str,
    start: pd.Timestamp,
    end: pd.Timestamp,
    window_id: str,
) -> dict[str, Any]:
    base = s813._profile(metadata, start, enabled=True)
    spec = base["spec"]
    variant = f"stage821_stage813_{capital_key}_rolling3y_{window_id}"
    capital = replace(
        spec.capital,
        variant=variant,
        label=f"{display_label} rolling3y {_window_label(start, end)}",
        account_capital=capital_value,
        c3_capital=capital_value,
        note=(
            f"{spec.capital.note} | Stage821 rolling 3y capital comparison. "
            f"account_capital/c3_capital={capital_value:.0f}; Stage813 signal/risk logic unchanged."
        ),
    )
    profile = dict(base)
    profile["profile"] = f"stage821_stage813_{capital_key}_rolling3y"
    profile["spec"] = replace(spec, capital=capital, profile=profile["profile"])
    profile["capital_key"] = capital_key
    profile["display_label"] = display_label
    profile["note"] = (
        "Stage813 AM41/OI0.8/old-AI/maxpos4/long tighter stop/RSI95 partial exit; "
        f"capital only changed to {capital_value:.0f}."
    )
    return profile


def _metric_from_combined(
    profile: dict[str, Any],
    combined: pd.DataFrame,
    *,
    start: pd.Timestamp,
    end: pd.Timestamp,
    window_id: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    spec = profile["spec"]
    row, curve, _costs = s748._metric_row(
        combined,
        spec=spec,
        window_name=_window_name(window_id),
        window_label=_window_label(start, end),
        window_group="rolling_3y_capital",
        forced_events=pd.DataFrame(),
    )
    row = s772._metric_common(row)
    for key in ["profile", "oi_mode", "am_label", "declared_am_size", "note"]:
        row[key] = profile.get(key)
    row["capital_key"] = profile["capital_key"]
    row["series_label"] = profile["display_label"]
    row["requested_start_month"] = _month_text(start)
    row["start_month"] = _month_text(start)
    row["window_start"] = start.strftime("%Y-%m-%d")
    row["window_end"] = end.strftime("%Y-%m-%d")
    row["window_id"] = window_id
    row["rolling_years"] = ROLL_YEARS
    row["positive_return"] = int(float(row.get("rebased_total_return_pct", row.get("total_return_pct", 0.0))) > 0.0)
    summary = s772._add_month_fields(pd.DataFrame([row]))

    curve = s772._curve_common(curve)
    for key in ["profile", "oi_mode", "am_label", "declared_am_size"]:
        curve[key] = profile.get(key)
    curve["capital_key"] = profile["capital_key"]
    curve["series_label"] = profile["display_label"]
    curve["requested_start_month"] = _month_text(start)
    curve["start_month"] = _month_text(start)
    curve["window_start"] = start.strftime("%Y-%m-%d")
    curve["window_end"] = end.strftime("%Y-%m-%d")
    curve["window_id"] = window_id
    curve["rolling_years"] = ROLL_YEARS
    return summary, curve


def _run_one(task: tuple[str, str, str]) -> tuple[dict[str, Any], pd.DataFrame]:
    global _WORKER_METADATA
    capital_key, window_id, _task_label = task
    capital_map = {key: (value, label) for key, value, label, _color, _linewidth in CAPITALS}
    window_map = {key: (start, end) for key, start, end in WINDOWS}
    capital_value, display_label = capital_map[capital_key]
    start, end = window_map[window_id]
    if _WORKER_METADATA is None:
        _WORKER_METADATA = s513._metadata()
    metadata = _WORKER_METADATA
    base_c3_overrides = dict(s513._c3_overrides(pd.Timestamp("2018-01-01").to_pydatetime()))
    profile = _capital_profile(
        metadata,
        capital_key=capital_key,
        capital_value=capital_value,
        display_label=display_label,
        start=start,
        end=end,
        window_id=window_id,
    )
    combined, frames = s808._run_profile(
        profile=profile,
        start=start,
        end=end,
        metadata=metadata,
        base_c3_overrides=base_c3_overrides,
    )
    summary, curve = _metric_from_combined(profile, combined, start=start, end=end, window_id=window_id)

    trade_events = frames.get("trade_events", pd.DataFrame()).copy()
    if trade_events.empty or "reason" not in trade_events.columns:
        rsi_count = 0
        rsi_volume = 0
    else:
        reason = trade_events["reason"].astype(str)
        rsi_events = trade_events[reason.str.contains("rsi_partial_exit", na=False)].copy()
        rsi_count = int(len(rsi_events))
        rsi_volume = int(pd.to_numeric(rsi_events.get("volume", pd.Series(dtype=float)), errors="coerce").fillna(0).sum())
    row = summary.iloc[0].to_dict()
    row["rsi_partial_exit_count"] = rsi_count
    row["rsi_partial_exit_volume"] = rsi_volume
    return row, curve


def _aggregate(summary: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for capital_key, group in summary.groupby("capital_key", sort=False):
        returns = pd.to_numeric(group["rebased_total_return_pct"], errors="coerce")
        dds = pd.to_numeric(group["rebased_max_dd_pct"], errors="coerce")
        sharpes = pd.to_numeric(group["rebased_sharpe"], errors="coerce")
        broker = pd.to_numeric(group["max_broker10_margin_to_rebased_equity_pct"], errors="coerce")
        min_equity = pd.to_numeric(group["rebased_min_equity"], errors="coerce")
        rows.append(
            {
                "capital_key": capital_key,
                "series_label": str(group["series_label"].iloc[0]),
                "window_count": int(len(group)),
                "positive_count": int((returns > 0).sum()),
                "positive_rate_pct": float((returns > 0).mean() * 100.0),
                "median_return_pct": float(returns.median()),
                "min_return_pct": float(returns.min()),
                "max_return_pct": float(returns.max()),
                "median_dd_pct": float(dds.median()),
                "worst_dd_pct": float(dds.min()),
                "dd30_fail_count": int((dds < -30.0).sum()),
                "dd40_fail_count": int((dds < -40.0).sum()),
                "dd50_fail_count": int((dds < -50.0).sum()),
                "median_sharpe": float(sharpes.median()),
                "min_sharpe": float(sharpes.min()),
                "median_broker10_pct": float(broker.median()),
                "broker100_fail_count": int((broker > 100.0).sum()),
                "survival_fail_count": int((min_equity <= 0.0).sum()),
                "total_trade_count": int(pd.to_numeric(group["total_trade_count"], errors="coerce").fillna(0).sum()),
                "total_slippage": float(pd.to_numeric(group["total_slippage"], errors="coerce").fillna(0).sum()),
                "total_rsi_partial_exit_count": int(
                    pd.to_numeric(group.get("rsi_partial_exit_count", 0), errors="coerce").fillna(0).sum()
                ),
            }
        )
    return pd.DataFrame(rows)


def _comparison(summary: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows: list[dict[str, Any]] = []
    pairwise_rows: list[dict[str, Any]] = []
    metric_cols = {
        "return": "rebased_total_return_pct",
        "max_dd": "rebased_max_dd_pct",
        "sharpe": "rebased_sharpe",
        "end_equity": "rebased_end_equity",
        "broker10": "max_broker10_margin_to_rebased_equity_pct",
        "trades": "total_trade_count",
        "slippage": "total_slippage",
    }
    pairs = [("30w", "50w"), ("20w", "50w"), ("30w", "20w")]
    for window_id, group in summary.groupby("window_id", sort=False):
        item: dict[str, Any] = {
            "window_id": window_id,
            "window_start": str(group["window_start"].iloc[0]),
            "window_end": str(group["window_end"].iloc[0]),
        }
        indexed = group.set_index("capital_key")
        for key, _capital, label, _color, _linewidth in CAPITALS:
            row = indexed.loc[key]
            for metric_name, column in metric_cols.items():
                item[f"{metric_name}_{key}"] = float(pd.to_numeric(pd.Series([row[column]]), errors="coerce").iloc[0])
        item["return_winner"] = max(CAPITALS, key=lambda c: item[f"return_{c[0]}"])[0]
        item["dd_winner"] = max(CAPITALS, key=lambda c: item[f"max_dd_{c[0]}"])[0]
        item["sharpe_winner"] = max(CAPITALS, key=lambda c: item[f"sharpe_{c[0]}"])[0]
        item["double_return_dd_winner"] = (
            item["return_winner"] if item["return_winner"] == item["dd_winner"] else ""
        )
        rows.append(item)

        for left, right in pairs:
            pairwise_rows.append(
                {
                    "window_id": window_id,
                    "window_start": item["window_start"],
                    "window_end": item["window_end"],
                    "left": left,
                    "right": right,
                    "return_delta_pp": item[f"return_{left}"] - item[f"return_{right}"],
                    "max_dd_delta_pp": item[f"max_dd_{left}"] - item[f"max_dd_{right}"],
                    "sharpe_delta": item[f"sharpe_{left}"] - item[f"sharpe_{right}"],
                    "left_return_win": int(item[f"return_{left}"] > item[f"return_{right}"]),
                    "left_dd_win": int(item[f"max_dd_{left}"] > item[f"max_dd_{right}"]),
                    "left_sharpe_win": int(item[f"sharpe_{left}"] > item[f"sharpe_{right}"]),
                    "left_double_win": int(
                        item[f"return_{left}"] > item[f"return_{right}"]
                        and item[f"max_dd_{left}"] > item[f"max_dd_{right}"]
                    ),
                }
            )
    return pd.DataFrame(rows), pd.DataFrame(pairwise_rows)


def _pairwise_aggregate(pairwise: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for (left, right), group in pairwise.groupby(["left", "right"], sort=False):
        rows.append(
            {
                "left": left,
                "right": right,
                "window_count": int(len(group)),
                "left_return_win_count": int(group["left_return_win"].sum()),
                "left_dd_win_count": int(group["left_dd_win"].sum()),
                "left_sharpe_win_count": int(group["left_sharpe_win"].sum()),
                "left_double_win_count": int(group["left_double_win"].sum()),
                "median_return_delta_pp": float(pd.to_numeric(group["return_delta_pp"], errors="coerce").median()),
                "median_dd_delta_pp": float(pd.to_numeric(group["max_dd_delta_pp"], errors="coerce").median()),
                "median_sharpe_delta": float(pd.to_numeric(group["sharpe_delta"], errors="coerce").median()),
            }
        )
    return pd.DataFrame(rows)


def _plot_grid(
    curves: pd.DataFrame,
    *,
    value_column: str,
    scale: float,
    ylabel: str,
    title: str,
    output_path: Path,
) -> None:
    windows = [(window_id, start, end) for window_id, start, end in WINDOWS]
    cols = 3
    rows = 3
    fig, axes = plt.subplots(rows, cols, figsize=(20, 12.5), sharex=False)
    axes = axes.ravel()
    color_map = {key: color for key, _capital, _label, color, _linewidth in CAPITALS}
    label_map = {key: label for key, _capital, label, _color, _linewidth in CAPITALS}
    linewidth_map = {key: linewidth for key, _capital, _label, _color, linewidth in CAPITALS}
    for ax, (window_id, _start, _end) in zip(axes, windows, strict=False):
        data = curves[curves["window_id"].eq(window_id)]
        for key, _capital, _label, _color, _linewidth in CAPITALS:
            current = data[data["capital_key"].eq(key)].sort_values("date")
            if current.empty:
                continue
            values = pd.to_numeric(current[value_column], errors="coerce") / scale
            ax.plot(
                pd.to_datetime(current["date"]),
                values,
                label=label_map[key],
                color=color_map[key],
                linewidth=linewidth_map[key],
            )
        label = str(data["window_label"].iloc[0]) if not data.empty and "window_label" in data.columns else window_id
        ax.set_title(label, fontsize=11)
        ax.grid(alpha=0.22)
        ax.tick_params(axis="x", labelrotation=25, labelsize=8)
        ax.tick_params(axis="y", labelsize=8)
        ax.set_ylabel(ylabel, fontsize=9)
    for ax in axes[len(windows) :]:
        ax.axis("off")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.suptitle(title, y=0.992, fontsize=15)
    fig.legend(handles, labels, loc="upper center", bbox_to_anchor=(0.5, 0.963), ncol=3, frameon=False)
    fig.tight_layout(rect=[0, 0, 1, 0.93])
    fig.savefig(output_path, dpi=180)
    plt.close(fig)


def _write_report(
    summary: pd.DataFrame,
    aggregate: pd.DataFrame,
    comparison: pd.DataFrame,
    pairwise_agg: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    summary_cols = [
        "window_id",
        "series_label",
        "rebased_end_equity",
        "rebased_total_return_pct",
        "rebased_max_dd_pct",
        "rebased_sharpe",
        "total_slippage",
        "total_trade_count",
        "nonzero_daily_win_rate_pct",
        "max_broker10_margin_to_rebased_equity_pct",
    ]
    comparison_cols = [
        "window_id",
        "window_start",
        "window_end",
        "return_50w",
        "return_30w",
        "return_20w",
        "max_dd_50w",
        "max_dd_30w",
        "max_dd_20w",
        "sharpe_50w",
        "sharpe_30w",
        "sharpe_20w",
        "return_winner",
        "dd_winner",
        "sharpe_winner",
    ]
    lines = [
        "# Stage821 Stage813 20w/30w/50w rolling 3y capital comparison",
        "",
        f"- line_id: `{LINE_ID}`",
        f"- model_tag: `{MODEL_TAG}`",
        "- 50w: Stage813 official-candidate logic, account/c3 capital 500000.",
        "- 30w: same Stage813 logic, account/c3 capital 300000.",
        "- 20w: same Stage813 logic, account/c3 capital 200000.",
        "- No official config change, no CTP connection, no order submission.",
        "",
        "## Aggregate By Capital",
        "",
        _md_table(aggregate, max_rows=10),
        "",
        "## Pairwise Aggregate",
        "",
        _md_table(pairwise_agg, max_rows=10),
        "",
        "## Window Comparison",
        "",
        _md_table(comparison[comparison_cols], max_rows=20),
        "",
        "## Summary Rows",
        "",
        _md_table(summary[summary_cols], max_rows=30),
        "",
        "## Outputs",
        "",
        f"- summary: `{SUMMARY_PATH}`",
        f"- curves: `{CURVES_PATH}`",
        f"- comparison: `{COMPARISON_PATH}`",
        f"- pairwise: `{PAIRWISE_PATH}`",
        f"- aggregate: `{AGG_PATH}`",
        f"- absolute_curves: `{ABSOLUTE_CURVES_PATH}`",
        f"- normalized_curves: `{NORMALIZED_CURVES_PATH}`",
        "",
        "## Decision",
        "",
        f"- decision: `{decision['decision']}`",
        f"- judgment: {decision['judgment']}",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    tasks = [
        (capital_key, window_id, f"{capital_key} {window_id}")
        for capital_key, _capital, _label, _color, _linewidth in CAPITALS
        for window_id, _start, _end in WINDOWS
    ]
    rows: list[dict[str, Any]] = []
    curves: list[pd.DataFrame] = []
    print(f"[stage821] launching {len(tasks)} rolling3y capital runs workers={MAX_WORKERS}", flush=True)
    if MAX_WORKERS == 1:
        for idx, task in enumerate(tasks, start=1):
            print(f"[stage821] running {idx}/{len(tasks)} {task[2]}", flush=True)
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
                print(f"[stage821] completed {idx}/{len(tasks)} {task[2]}", flush=True)

    summary = (
        s772._add_month_fields(pd.DataFrame(rows))
        .sort_values(["window_start", "capital_key"])
        .reset_index(drop=True)
    )
    curve_df = (
        pd.concat(curves, ignore_index=True, sort=False)
        .sort_values(["window_start", "capital_key", "date"])
        .reset_index(drop=True)
    )
    aggregate = _aggregate(summary)
    comparison, pairwise = _comparison(summary)
    pairwise_agg = _pairwise_aggregate(pairwise)

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    curve_df.to_csv(CURVES_PATH, index=False, encoding="utf-8-sig")
    comparison.to_csv(COMPARISON_PATH, index=False, encoding="utf-8-sig")
    pairwise.to_csv(PAIRWISE_PATH, index=False, encoding="utf-8-sig")
    aggregate.to_csv(AGG_PATH, index=False, encoding="utf-8-sig")

    _plot_grid(
        curve_df,
        value_column="account_equity",
        scale=10_000.0,
        ylabel="Equity (10k CNY)",
        title="Stage813 Rolling 3y: 50w vs 30w vs 20w Absolute Equity",
        output_path=ABSOLUTE_CURVES_PATH,
    )
    _plot_grid(
        curve_df,
        value_column="nav",
        scale=1.0,
        ylabel="NAV (initial=1.0)",
        title="Stage813 Rolling 3y: 50w vs 30w vs 20w Normalized NAV",
        output_path=NORMALIZED_CURVES_PATH,
    )

    agg_map = aggregate.set_index("capital_key").to_dict(orient="index")
    pair_map = {
        f"{row.left}_vs_{row.right}": row._asdict()
        for row in pairwise_agg.itertuples(index=False)
    }
    hard_fail_30w = int(agg_map["30w"]["dd40_fail_count"]) >= int(agg_map["50w"]["dd40_fail_count"])
    decision_label = "stage821_30w_watch_not_promoted" if hard_fail_30w else "stage821_30w_next_validation"
    decision = {
        "stage": "Stage821",
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "windows": [
            {"window_id": window_id, "start": start.strftime("%Y-%m-%d"), "end": end.strftime("%Y-%m-%d")}
            for window_id, start, end in WINDOWS
        ],
        "arms": {
            "50w": "Stage813 official-candidate logic, account/c3 capital 500000",
            "30w": "Stage813 logic, account/c3 capital 300000",
            "20w": "Stage813 logic, account/c3 capital 200000",
        },
        "aggregate": aggregate.to_dict(orient="records"),
        "pairwise_aggregate": pairwise_agg.to_dict(orient="records"),
        "decision": decision_label,
        "judgment": (
            "Rolling 3y capital comparison. Capital-only changes are useful for deployment sensitivity, "
            "but promotion needs drawdown robustness, not just return/NAV leadership."
        ),
        "outputs": {
            "summary": str(SUMMARY_PATH),
            "curves": str(CURVES_PATH),
            "comparison": str(COMPARISON_PATH),
            "pairwise": str(PAIRWISE_PATH),
            "aggregate": str(AGG_PATH),
            "report": str(REPORT_PATH),
            "absolute_curves": str(ABSOLUTE_CURVES_PATH),
            "normalized_curves": str(NORMALIZED_CURVES_PATH),
        },
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_report(summary, aggregate, comparison, pairwise_agg, decision)

    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print("aggregate")
    print(aggregate.to_string(index=False))
    print("pairwise_aggregate")
    print(pairwise_agg.to_string(index=False))
    print("comparison")
    print(
        comparison[
            [
                "window_id",
                "window_start",
                "window_end",
                "return_50w",
                "return_30w",
                "return_20w",
                "max_dd_50w",
                "max_dd_30w",
                "max_dd_20w",
                "sharpe_50w",
                "sharpe_30w",
                "sharpe_20w",
                "return_winner",
                "dd_winner",
                "sharpe_winner",
            ]
        ].to_string(index=False)
    )


if __name__ == "__main__":
    main()
