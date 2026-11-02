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
import numpy as np
import pandas as pd

import analyze_qmt_roll_stage513_stage208_exact_position_margin_audit as s513
import analyze_qmt_roll_stage650_stage526_200k_capital_reality_check as s650
import analyze_qmt_roll_stage748_half_risk_no_streak_500k as s748
import analyze_qmt_roll_stage772_am40_80_120_oi_monthly as s772
import analyze_qmt_roll_stage777_am41_oi08_monthly as s777
import analyze_qmt_roll_stage778_stage777_2022_drawdown_forensics as s778
from analyze_qmt_roll_stage799_stage777_long_lower_high_block_2020 import (
    QmtRollPortfolioStrategyLongTwoLowerHighBlock,
)


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

MODEL_TAG = "stage800_stage777_long_lower_high_block_yearly_v1"
OUTPUT_PREFIX = "qmt_roll_stage800_stage777_long_lower_high_block_yearly"
LINE_ID = "futures_trend_2019_data_extension"

YEAR_STARTS = tuple(pd.date_range("2018-01-01", "2026-01-01", freq="YS"))
MAX_WORKERS = max(1, min(4, int(os.environ.get("STAGE800_MAX_WORKERS", "4"))))

BASE_SUMMARY_PATH = OUTPUT_DIR / "qmt_roll_stage777_am41_oi08_monthly_summary_stage777_am41_oi08_monthly_v1.csv"
BASE_CURVES_PATH = OUTPUT_DIR / "qmt_roll_stage777_am41_oi08_monthly_curves_stage777_am41_oi08_monthly_v1.csv"

VARIANT = "stage800_stage777_500k_am41_oi08_old_ai_long_two_lower_high_block_yearly"
LABEL = "Stage800 Stage777 candidate long two lower highs block yearly"

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
CURVES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv"
LOWER_HIGH_BLOCKS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_lower_high_blocks_{MODEL_TAG}.csv"
COMPARISON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_comparison_vs_stage777_{MODEL_TAG}.csv"
AGG_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_aggregate_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
RETURN_BAR_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_return_delta_bar_{MODEL_TAG}.png"
DD_BAR_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_dd_delta_bar_{MODEL_TAG}.png"
EQUITY_CURVES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_equity_curves_{MODEL_TAG}.png"


def _json_safe(value: Any) -> Any:
    return s650._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s650._md_table(frame, max_rows=max_rows)


def _year_start_text(start: pd.Timestamp) -> str:
    return pd.Timestamp(start).strftime("%Y-%m")


def _long_lower_high_profile(metadata: dict[str, Any], start: pd.Timestamp) -> dict[str, Any]:
    base = next(profile for profile in s772._profile_specs(metadata) if profile["profile"] == "oi_restore_am40")
    spec = base["spec"]
    start_text = _year_start_text(start)
    capital = replace(
        spec.capital,
        variant=f"{VARIANT}_{start_text.replace('-', '_')}",
        label=f"{LABEL} {start_text}",
        note=(
            f"{spec.capital.note} | Stage800 yearly validation. Blocks long signals when the latest three completed "
            "daily highs are strictly descending: high[t] < high[t-1] < high[t-2]."
        ),
    )
    overrides = {
        **spec.overrides,
        "block_long_two_lower_highs": True,
    }
    candidate = dict(base)
    candidate["profile"] = "stage800_oi_restore_am40_long_two_lower_high_block"
    candidate["strategy_cls"] = QmtRollPortfolioStrategyLongTwoLowerHighBlock
    candidate["spec"] = replace(spec, capital=capital, overrides=overrides, profile=candidate["profile"])
    candidate["note"] = (
        "Stage777 candidate with a long-only lower-high exhaustion filter; all other AM41/OI/AI/risk settings unchanged."
    )
    return candidate


def _metric_from_combined(
    profile: dict[str, Any],
    combined: pd.DataFrame,
    start: pd.Timestamp,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    spec = profile["spec"]
    row, curve, _costs = s748._metric_row(
        combined,
        spec=spec,
        window_name=s772._window_name(start),
        window_label=s772._window_label(start),
        window_group="yearly_start",
        forced_events=pd.DataFrame(),
    )
    row = s772._metric_common(row)
    for key in ["profile", "oi_mode", "am_label", "declared_am_size", "note"]:
        row[key] = profile.get(key)
    row["requested_start_month"] = _year_start_text(start)
    row["start_month"] = _year_start_text(start)
    summary = s772._add_month_fields(pd.DataFrame([row]))

    curve = s772._curve_common(curve)
    for key in ["profile", "oi_mode", "am_label", "declared_am_size"]:
        curve[key] = profile.get(key)
    curve["requested_start_month"] = _year_start_text(start)
    curve["start_month"] = _year_start_text(start)
    return summary, curve


def _run_one(start_text: str) -> tuple[dict[str, Any], pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    start = pd.Timestamp(start_text).normalize()
    metadata = s513._metadata()
    profile = _long_lower_high_profile(metadata, start)
    base_c3_overrides = dict(s513._c3_overrides(pd.Timestamp("2018-01-01").to_pydatetime()))
    combined, frames = s778._run_profile(
        profile=profile,
        start=start,
        metadata=metadata,
        base_c3_overrides=base_c3_overrides,
    )
    summary, curve = _metric_from_combined(profile, combined, start)
    trade_events = frames.get("trade_events", pd.DataFrame()).copy()
    if trade_events.empty or "reason" not in trade_events.columns:
        blocks = pd.DataFrame()
    else:
        blocks = trade_events[trade_events["reason"].eq("long_two_lower_high_block")].copy()
    blocks["requested_start_month"] = _year_start_text(start)
    blocks["start_month"] = _year_start_text(start)
    row = summary.iloc[0].to_dict()
    row["lower_high_block_count"] = int(len(blocks))
    return row, curve, blocks, combined


def _load_base_yearly() -> tuple[pd.DataFrame, pd.DataFrame]:
    summary = pd.read_csv(BASE_SUMMARY_PATH)
    summary["start_month"] = summary["start_month"].astype(str)
    year_months = {_year_start_text(start) for start in YEAR_STARTS}
    base_summary = summary[summary["start_month"].isin(year_months)].copy().sort_values("start_month")
    if len(base_summary) != len(YEAR_STARTS):
        missing = sorted(year_months - set(base_summary["start_month"]))
        raise RuntimeError(f"missing base yearly Stage777 rows: {missing}")

    curves = pd.read_csv(BASE_CURVES_PATH, parse_dates=["date"])
    curves["start_month"] = curves["start_month"].astype(str)
    base_curves = curves[curves["start_month"].isin(year_months)].copy().sort_values(["start_month", "date"])
    return base_summary.reset_index(drop=True), base_curves.reset_index(drop=True)


def _comparison(candidate: pd.DataFrame, base: pd.DataFrame) -> pd.DataFrame:
    merged = base.merge(
        candidate,
        on="start_month",
        suffixes=("_base", "_candidate"),
        how="inner",
    )
    rows: list[dict[str, Any]] = []
    metric_pairs = [
        ("end_equity", "end_equity", "rebased_end_equity"),
        ("total_return_pct", "rebased_total_return_pct", "rebased_total_return_pct"),
        ("max_dd_pct", "rebased_max_dd_pct", "rebased_max_dd_pct"),
        ("sharpe", "rebased_sharpe", "rebased_sharpe"),
        ("total_slippage", "total_slippage", "total_slippage"),
        ("total_trade_count", "total_trade_count", "total_trade_count"),
        ("nonzero_daily_win_rate_pct", "nonzero_daily_win_rate_pct", "nonzero_daily_win_rate_pct"),
        ("max_broker10_margin_to_equity_pct", "max_broker10_margin_to_equity_pct", "max_broker10_margin_to_equity_pct"),
        ("p95_broker10_margin_to_equity_pct", "p95_broker10_margin_to_equity_pct", "p95_broker10_margin_to_equity_pct"),
    ]
    for _, row in merged.iterrows():
        record: dict[str, Any] = {"start_month": row["start_month"]}
        for metric, base_col, candidate_col in metric_pairs:
            base_value = float(pd.to_numeric(pd.Series([row[f"{base_col}_base"]]), errors="coerce").iloc[0])
            candidate_value = float(pd.to_numeric(pd.Series([row[f"{candidate_col}_candidate"]]), errors="coerce").iloc[0])
            record[f"{metric}_base"] = base_value
            record[f"{metric}_candidate"] = candidate_value
            record[f"{metric}_delta"] = candidate_value - base_value
        block_value = row.get("lower_high_block_count")
        if block_value is None:
            block_value = row.get("lower_high_block_count_candidate")
        record["lower_high_block_count"] = int(block_value or 0)
        rows.append(record)
    return pd.DataFrame(rows)


def _aggregate(comparison: pd.DataFrame) -> pd.DataFrame:
    mature = comparison[comparison["start_month"].lt("2026-01")].copy()
    rows: list[dict[str, Any]] = []
    for bucket, frame in [("all", comparison), ("mature_ex_2026", mature)]:
        if frame.empty:
            continue
        rows.append(
            {
                "bucket": bucket,
                "sample_count": int(len(frame)),
                "candidate_return_win_count": int(frame["total_return_pct_delta"].gt(0).sum()),
                "candidate_dd_win_count": int(frame["max_dd_pct_delta"].gt(0).sum()),
                "candidate_sharpe_win_count": int(frame["sharpe_delta"].gt(0).sum()),
                "candidate_double_win_count": int(
                    (frame["total_return_pct_delta"].gt(0) & frame["max_dd_pct_delta"].gt(0)).sum()
                ),
                "median_return_delta_pp": float(frame["total_return_pct_delta"].median()),
                "median_dd_delta_pp": float(frame["max_dd_pct_delta"].median()),
                "median_sharpe_delta": float(frame["sharpe_delta"].median()),
                "min_return_delta_pp": float(frame["total_return_pct_delta"].min()),
                "max_return_delta_pp": float(frame["total_return_pct_delta"].max()),
                "base_dd40_fail_count": int(frame["max_dd_pct_base"].lt(-40.0).sum()),
                "candidate_dd40_fail_count": int(frame["max_dd_pct_candidate"].lt(-40.0).sum()),
                "base_dd50_fail_count": int(frame["max_dd_pct_base"].lt(-50.0).sum()),
                "candidate_dd50_fail_count": int(frame["max_dd_pct_candidate"].lt(-50.0).sum()),
                "total_blocked_long_signals": int(frame["lower_high_block_count"].sum()),
                "median_trade_delta": float(frame["total_trade_count_delta"].median()),
                "median_slippage_delta": float(frame["total_slippage_delta"].median()),
            }
        )
    return pd.DataFrame(rows)


def _plot_delta_bars(comparison: pd.DataFrame) -> None:
    frame = comparison.copy()
    x = np.arange(len(frame))

    fig, ax = plt.subplots(figsize=(13, 5))
    colors = np.where(frame["total_return_pct_delta"].ge(0), "#16a34a", "#dc2626")
    ax.bar(x, frame["total_return_pct_delta"], color=colors, alpha=0.82)
    ax.axhline(0, color="#111827", linewidth=1)
    ax.set_xticks(x)
    ax.set_xticklabels(frame["start_month"], rotation=30, ha="right")
    ax.set_title("Stage800 yearly starts: return delta C lower-high block vs A Stage777")
    ax.set_ylabel("Return delta (pp)")
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(RETURN_BAR_PATH, dpi=180)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(13, 5))
    colors = np.where(frame["max_dd_pct_delta"].ge(0), "#16a34a", "#dc2626")
    ax.bar(x, frame["max_dd_pct_delta"], color=colors, alpha=0.82)
    ax.axhline(0, color="#111827", linewidth=1)
    ax.set_xticks(x)
    ax.set_xticklabels(frame["start_month"], rotation=30, ha="right")
    ax.set_title("Stage800 yearly starts: max drawdown delta C lower-high block vs A Stage777")
    ax.set_ylabel("Max DD delta (pp, higher is better)")
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(DD_BAR_PATH, dpi=180)
    plt.close(fig)


def _plot_equity_curves(candidate_curves: pd.DataFrame, base_curves: pd.DataFrame) -> None:
    fig, axes = plt.subplots(3, 3, figsize=(18, 12), sharex=False)
    axes = axes.ravel()
    starts = sorted(candidate_curves["start_month"].dropna().astype(str).unique())
    for ax, start_month in zip(axes, starts, strict=False):
        base = base_curves[base_curves["start_month"].astype(str).eq(start_month)].copy()
        cand = candidate_curves[candidate_curves["start_month"].astype(str).eq(start_month)].copy()
        if not base.empty:
            ax.plot(base["date"], base["rebased_equity"] / 1_000_000, label="A Stage777", linewidth=1.3)
        if not cand.empty:
            ax.plot(cand["date"], cand["rebased_equity"] / 1_000_000, label="C lower-high", linewidth=1.3)
        ax.axhline(0.5, color="#9aa3af", linestyle="--", linewidth=0.8)
        ax.set_title(start_month)
        ax.grid(alpha=0.22)
        ax.tick_params(axis="x", labelrotation=25, labelsize=8)
        ax.tick_params(axis="y", labelsize=8)
    for ax in axes[len(starts) :]:
        ax.axis("off")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=2)
    fig.suptitle("Stage800 yearly equity curves: A Stage777 vs C long two-lower-high block", y=0.995)
    fig.tight_layout(rect=[0, 0, 1, 0.965])
    fig.savefig(EQUITY_CURVES_PATH, dpi=170)
    plt.close(fig)


def _write_report(comparison: pd.DataFrame, aggregate: pd.DataFrame, decision: dict[str, Any]) -> None:
    lines = [
        "# Stage800 Stage777候选版多头连续lower-high过滤 年度起点回测",
        "",
        f"- line_id：`{LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        "- A：当前 `official_candidate_stage777_50w_am41_oi08_old_ai_v1`，从 Stage777 月度缓存抽取年度起点。",
        "- C：同 A，仅新增多头过滤：若最新三根已完成日线 `high[t] < high[t-1] < high[t-2]`，则不发多头新开/反手/换月重开信号。",
        "- 保持不变：50万、AM41、基础风险 `0.40`、OI命中恢复 `0.80`、旧正式AI池、maxpos4、关闭连败缩放和 recovery sleeve。",
        "",
        "## Aggregate",
        "",
        _md_table(aggregate, max_rows=10),
        "",
        "## Yearly Comparison",
        "",
        _md_table(
            comparison[
                [
                    "start_month",
                    "total_return_pct_base",
                    "total_return_pct_candidate",
                    "total_return_pct_delta",
                    "max_dd_pct_base",
                    "max_dd_pct_candidate",
                    "max_dd_pct_delta",
                    "sharpe_base",
                    "sharpe_candidate",
                    "sharpe_delta",
                    "lower_high_block_count",
                ]
            ],
            max_rows=20,
        ),
        "",
        "## Decision",
        "",
        f"- 决策：`{decision['decision']}`",
        f"- 判断：{decision['judgment']}",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    # Load once before workers so missing baseline cache fails fast.
    base_summary, base_curves = _load_base_yearly()
    tasks = [start.strftime("%Y-%m-%d") for start in YEAR_STARTS]
    rows: list[dict[str, Any]] = []
    curves: list[pd.DataFrame] = []
    blocks: list[pd.DataFrame] = []

    print(f"[stage800] launching {len(tasks)} yearly runs workers={MAX_WORKERS}", flush=True)
    if MAX_WORKERS == 1:
        for idx, task in enumerate(tasks, start=1):
            print(f"[stage800] running {idx}/{len(tasks)} {task}", flush=True)
            row, curve, block, _combined = _run_one(task)
            rows.append(row)
            curves.append(curve)
            blocks.append(block)
    else:
        with ProcessPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_map = {executor.submit(_run_one, task): task for task in tasks}
            for idx, future in enumerate(as_completed(future_map), start=1):
                task = future_map[future]
                row, curve, block, _combined = future.result()
                rows.append(row)
                curves.append(curve)
                blocks.append(block)
                print(f"[stage800] completed {idx}/{len(tasks)} {task}", flush=True)

    candidate_summary = s772._add_month_fields(pd.DataFrame(rows)).sort_values("start_month").reset_index(drop=True)
    candidate_curves = pd.concat(curves, ignore_index=True, sort=False).sort_values(["start_month", "date"]).reset_index(drop=True)
    lower_high_blocks = (
        pd.concat(blocks, ignore_index=True, sort=False)
        if blocks
        else pd.DataFrame(columns=["start_month", "reason"])
    )
    comparison = _comparison(candidate_summary, base_summary).sort_values("start_month").reset_index(drop=True)
    aggregate = _aggregate(comparison)

    candidate_summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    candidate_curves.to_csv(CURVES_PATH, index=False, encoding="utf-8-sig")
    lower_high_blocks.to_csv(LOWER_HIGH_BLOCKS_PATH, index=False, encoding="utf-8-sig")
    comparison.to_csv(COMPARISON_PATH, index=False, encoding="utf-8-sig")
    aggregate.to_csv(AGG_PATH, index=False, encoding="utf-8-sig")
    _plot_delta_bars(comparison)
    _plot_equity_curves(candidate_curves, base_curves)

    mature = aggregate[aggregate["bucket"].eq("mature_ex_2026")].iloc[0].to_dict()
    all_row = aggregate[aggregate["bucket"].eq("all")].iloc[0].to_dict()
    decision_label = (
        "stage800_long_lower_high_block_yearly_watch"
        if int(mature["candidate_return_win_count"]) >= 5
        and int(mature["candidate_dd_win_count"]) >= 5
        and float(mature["median_return_delta_pp"]) >= 0
        else "stage800_long_lower_high_block_yearly_not_promoted"
    )
    decision = {
        "stage": "Stage800",
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "base": "official_candidate_stage777_50w_am41_oi08_old_ai_v1 yearly starts",
        "candidate": "Stage777 + long two-lower-high block yearly starts",
        "change": {
            "block_long_two_lower_highs": True,
            "definition": "block long signal when high[t] < high[t-1] < high[t-2] on completed daily bars",
        },
        "decision": decision_label,
        "judgment": (
            "Yearly-start validation. Promote only if the filter improves both return and drawdown breadth; "
            "otherwise treat it as a right-tail killer rather than a robust bad-opportunity filter."
        ),
        "aggregate_all": all_row,
        "aggregate_mature_ex_2026": mature,
        "outputs": {
            "summary": str(SUMMARY_PATH),
            "curves": str(CURVES_PATH),
            "lower_high_blocks": str(LOWER_HIGH_BLOCKS_PATH),
            "comparison": str(COMPARISON_PATH),
            "aggregate": str(AGG_PATH),
            "return_bar": str(RETURN_BAR_PATH),
            "dd_bar": str(DD_BAR_PATH),
            "equity_curves": str(EQUITY_CURVES_PATH),
            "report": str(REPORT_PATH),
        },
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_report(comparison, aggregate, decision)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print(aggregate.to_string(index=False))
    print(
        comparison[
            [
                "start_month",
                "total_return_pct_base",
                "total_return_pct_candidate",
                "total_return_pct_delta",
                "max_dd_pct_base",
                "max_dd_pct_candidate",
                "max_dd_pct_delta",
                "sharpe_base",
                "sharpe_candidate",
                "sharpe_delta",
                "lower_high_block_count",
            ]
        ].to_string(index=False)
    )


if __name__ == "__main__":
    main()
