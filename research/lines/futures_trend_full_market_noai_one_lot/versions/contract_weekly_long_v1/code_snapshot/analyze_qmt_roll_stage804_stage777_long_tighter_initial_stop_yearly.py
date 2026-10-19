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
import numpy as np
import pandas as pd

import analyze_qmt_roll_stage513_stage208_exact_position_margin_audit as s513
import analyze_qmt_roll_stage650_stage526_200k_capital_reality_check as s650
import analyze_qmt_roll_stage748_half_risk_no_streak_500k as s748
import analyze_qmt_roll_stage772_am40_80_120_oi_monthly as s772
import analyze_qmt_roll_stage778_stage777_2022_drawdown_forensics as s778
import analyze_qmt_roll_stage800_stage777_long_lower_high_block_yearly as s800


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

MODEL_TAG = "stage804_stage777_long_tighter_initial_stop_yearly_v1"
OUTPUT_PREFIX = "qmt_roll_stage804_stage777_long_tighter_initial_stop_yearly"
LINE_ID = "futures_trend_2019_data_extension"

YEAR_STARTS = s800.YEAR_STARTS
MAX_WORKERS = max(1, min(4, int(os.environ.get("STAGE804_MAX_WORKERS", "4"))))

VARIANT = "stage804_stage777_500k_am41_oi08_old_ai_long_tighter_initial_stop_yearly"
LABEL = "Stage804 Stage777 candidate long tighter initial stop yearly"

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
CURVES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv"
ADJUSTMENTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_stop_adjustments_{MODEL_TAG}.csv"
COMPARISON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_comparison_vs_stage777_{MODEL_TAG}.csv"
AGG_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_aggregate_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
RETURN_BAR_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_return_delta_bar_{MODEL_TAG}.png"
DD_BAR_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_dd_delta_bar_{MODEL_TAG}.png"
EQUITY_CURVES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_equity_curves_{MODEL_TAG}.png"


class QmtRollPortfolioStrategyLongTighterInitialStop(s772.QmtRollPortfolioStrategyExactAm):
    """Research-only wrapper: for long entries, use the tighter initial stop; shorts stay inherited."""

    long_tighter_initial_stop: bool = True
    parameters = [
        *s772.QmtRollPortfolioStrategyExactAm.parameters,
        "long_tighter_initial_stop",
    ]

    def _entry_stop_price(self, direction: str, bar: Any, history: pd.DataFrame, use_day_extreme: bool) -> float:
        if not bool(self.long_tighter_initial_stop):
            return super()._entry_stop_price(direction, bar, history, use_day_extreme)
        if direction != "long" or not use_day_extreme:
            return super()._entry_stop_price(direction, bar, history, use_day_extreme)

        close_price = float(bar.close_price)
        low_price = float(bar.low_price)
        basic_long = close_price * (1 - self.stop_loss_pct)
        day_drop_ratio = (close_price - low_price) / close_price if close_price > 0 else 0.0
        old_stop = basic_long if day_drop_ratio < self.stop_loss_pct else low_price
        new_stop = max(basic_long, low_price)

        if abs(new_stop - old_stop) > 1e-9:
            diagnostics = getattr(self, "trade_event_diagnostics", None)
            if diagnostics is not None:
                dt_value = getattr(bar, "datetime", "")
                try:
                    date_text = str(pd.Timestamp(dt_value).date())
                except Exception:
                    date_text = str(dt_value)
                diagnostics.append(
                    {
                        "datetime": date_text,
                        "date": date_text,
                        "vt_symbol": getattr(bar, "vt_symbol", ""),
                        "product_vt_symbol": self._product_vt_symbol(getattr(bar, "vt_symbol", "")),
                        "position_direction": "long",
                        "direction": "long",
                        "offset": "RiskSizing",
                        "reason": "long_tighter_initial_stop_adjust",
                        "volume": 0,
                        "price": close_price,
                        "old_stop": old_stop,
                        "new_stop": new_stop,
                        "old_stop_distance": close_price - old_stop,
                        "new_stop_distance": close_price - new_stop,
                        "old_stop_distance_pct": (close_price - old_stop) / close_price if close_price > 0 else np.nan,
                        "new_stop_distance_pct": (close_price - new_stop) / close_price if close_price > 0 else np.nan,
                        "signal_low": low_price,
                        "signal_close": close_price,
                        "stop_loss_pct": self.stop_loss_pct,
                        "old_case": "basic_min_distance" if day_drop_ratio < self.stop_loss_pct else "day_low",
                    }
                )
        return new_stop


def _json_safe(value: Any) -> Any:
    return s650._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s650._md_table(frame, max_rows=max_rows)


def _year_start_text(start: pd.Timestamp) -> str:
    return pd.Timestamp(start).strftime("%Y-%m")


def _profile(metadata: dict[str, Any], start: pd.Timestamp) -> dict[str, Any]:
    base = next(profile for profile in s772._profile_specs(metadata) if profile["profile"] == "oi_restore_am40")
    spec = base["spec"]
    start_text = _year_start_text(start)
    capital = replace(
        spec.capital,
        variant=f"{VARIANT}_{start_text.replace('-', '_')}",
        label=f"{LABEL} {start_text}",
        note=(
            f"{spec.capital.note} | Stage804 yearly validation. For long entries only, "
            "use max(signal_day_low, close*(1-stop_loss_pct)) as the initial stop."
        ),
    )
    overrides = {
        **spec.overrides,
        "long_tighter_initial_stop": True,
    }
    candidate = dict(base)
    candidate["profile"] = "stage804_oi_restore_am40_long_tighter_initial_stop"
    candidate["strategy_cls"] = QmtRollPortfolioStrategyLongTighterInitialStop
    candidate["spec"] = replace(spec, capital=capital, overrides=overrides, profile=candidate["profile"])
    candidate["note"] = (
        "Stage777 candidate with long-only tighter initial stop; short stop logic and all other AM41/OI/AI/risk "
        "settings unchanged."
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


def _run_one(start_text: str) -> tuple[dict[str, Any], pd.DataFrame, pd.DataFrame]:
    start = pd.Timestamp(start_text).normalize()
    metadata = s513._metadata()
    profile = _profile(metadata, start)
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
        adjustments = pd.DataFrame()
    else:
        adjustments = trade_events[trade_events["reason"].eq("long_tighter_initial_stop_adjust")].copy()
    adjustments["requested_start_month"] = _year_start_text(start)
    adjustments["start_month"] = _year_start_text(start)
    row = summary.iloc[0].to_dict()
    row["long_tighter_stop_adjust_count"] = int(len(adjustments))
    if not adjustments.empty:
        row["median_new_stop_distance_pct"] = float(pd.to_numeric(adjustments["new_stop_distance_pct"], errors="coerce").median() * 100)
        row["median_old_stop_distance_pct"] = float(pd.to_numeric(adjustments["old_stop_distance_pct"], errors="coerce").median() * 100)
    else:
        row["median_new_stop_distance_pct"] = np.nan
        row["median_old_stop_distance_pct"] = np.nan
    return row, curve, adjustments


def _comparison(candidate: pd.DataFrame, base: pd.DataFrame) -> pd.DataFrame:
    comparison = s800._comparison(candidate, base)
    count_map = (
        candidate.set_index("start_month")["long_tighter_stop_adjust_count"].to_dict()
        if "long_tighter_stop_adjust_count" in candidate.columns
        else {}
    )
    comparison["long_tighter_stop_adjust_count"] = (
        comparison["start_month"].map(count_map).fillna(0).astype(int)
    )
    return comparison


def _aggregate(comparison: pd.DataFrame) -> pd.DataFrame:
    frame = comparison.copy()
    frame["lower_high_block_count"] = frame["long_tighter_stop_adjust_count"]
    agg = s800._aggregate(frame)
    agg.rename(columns={"total_blocked_long_signals": "total_long_tighter_stop_adjustments"}, inplace=True)
    return agg


def _plot_delta_bars(comparison: pd.DataFrame) -> None:
    frame = comparison.copy()
    x = np.arange(len(frame))

    fig, ax = plt.subplots(figsize=(13, 5))
    colors = np.where(frame["total_return_pct_delta"].ge(0), "#16a34a", "#dc2626")
    ax.bar(x, frame["total_return_pct_delta"], color=colors, alpha=0.82)
    ax.axhline(0, color="#111827", linewidth=1)
    ax.set_xticks(x)
    ax.set_xticklabels(frame["start_month"], rotation=30, ha="right")
    ax.set_title("Stage804 yearly starts: return delta C long tighter initial stop vs A Stage777")
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
    ax.set_title("Stage804 yearly starts: max drawdown delta C long tighter initial stop vs A Stage777")
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
            ax.plot(cand["date"], cand["rebased_equity"] / 1_000_000, label="C long tighter stop", linewidth=1.3)
        ax.axhline(0.5, color="#9aa3af", linestyle="--", linewidth=0.8)
        ax.set_title(start_month)
        ax.grid(alpha=0.22)
        ax.tick_params(axis="x", labelrotation=25, labelsize=8)
        ax.tick_params(axis="y", labelsize=8)
    for ax in axes[len(starts) :]:
        ax.axis("off")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=2)
    fig.suptitle("Stage804 yearly equity curves: A Stage777 vs C long-only tighter initial stop", y=0.995)
    fig.tight_layout(rect=[0, 0, 1, 0.965])
    fig.savefig(EQUITY_CURVES_PATH, dpi=170)
    plt.close(fig)


def _write_report(comparison: pd.DataFrame, aggregate: pd.DataFrame, decision: dict[str, Any]) -> None:
    lines = [
        "# Stage804 Stage777候选版多头更紧初始止损 年度起点回测",
        "",
        f"- line_id：`{LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        "- A：当前 `official_candidate_stage777_50w_am41_oi08_old_ai_v1`，从 Stage777 月度缓存抽取年度起点。",
        "- C：同 A，仅修改多头初始止损：`max(signal_day_low, close * (1 - stop_loss_pct))`。空头完全沿用 Stage777 原逻辑。",
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
                    "total_trade_count_base",
                    "total_trade_count_candidate",
                    "long_tighter_stop_adjust_count",
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
    base_summary, base_curves = s800._load_base_yearly()
    tasks = [start.strftime("%Y-%m-%d") for start in YEAR_STARTS]
    rows: list[dict[str, Any]] = []
    curves: list[pd.DataFrame] = []
    adjustments: list[pd.DataFrame] = []

    print(f"[stage804] launching {len(tasks)} yearly runs workers={MAX_WORKERS}", flush=True)
    if MAX_WORKERS == 1:
        for idx, task in enumerate(tasks, start=1):
            print(f"[stage804] running {idx}/{len(tasks)} {task}", flush=True)
            row, curve, adjustment = _run_one(task)
            rows.append(row)
            curves.append(curve)
            adjustments.append(adjustment)
    else:
        with ProcessPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_map = {executor.submit(_run_one, task): task for task in tasks}
            for idx, future in enumerate(as_completed(future_map), start=1):
                task = future_map[future]
                row, curve, adjustment = future.result()
                rows.append(row)
                curves.append(curve)
                adjustments.append(adjustment)
                print(f"[stage804] completed {idx}/{len(tasks)} {task}", flush=True)

    candidate_summary = s772._add_month_fields(pd.DataFrame(rows)).sort_values("start_month").reset_index(drop=True)
    candidate_curves = pd.concat(curves, ignore_index=True, sort=False).sort_values(["start_month", "date"]).reset_index(drop=True)
    stop_adjustments = (
        pd.concat(adjustments, ignore_index=True, sort=False)
        if adjustments
        else pd.DataFrame(columns=["start_month", "reason"])
    )
    comparison = _comparison(candidate_summary, base_summary).sort_values("start_month").reset_index(drop=True)
    aggregate = _aggregate(comparison)

    candidate_summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    candidate_curves.to_csv(CURVES_PATH, index=False, encoding="utf-8-sig")
    stop_adjustments.to_csv(ADJUSTMENTS_PATH, index=False, encoding="utf-8-sig")
    comparison.to_csv(COMPARISON_PATH, index=False, encoding="utf-8-sig")
    aggregate.to_csv(AGG_PATH, index=False, encoding="utf-8-sig")
    _plot_delta_bars(comparison)
    _plot_equity_curves(candidate_curves, base_curves)

    mature = aggregate[aggregate["bucket"].eq("mature_ex_2026")].iloc[0].to_dict()
    all_row = aggregate[aggregate["bucket"].eq("all")].iloc[0].to_dict()
    decision_label = (
        "stage804_long_tighter_initial_stop_yearly_watch"
        if int(mature["candidate_return_win_count"]) >= 5
        and int(mature["candidate_dd_win_count"]) >= 5
        and float(mature["median_return_delta_pp"]) >= 0
        else "stage804_long_tighter_initial_stop_yearly_not_promoted"
    )
    decision = {
        "stage": "Stage804",
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "base": "official_candidate_stage777_50w_am41_oi08_old_ai_v1 yearly starts",
        "candidate": "Stage777 + long-only tighter initial stop yearly starts",
        "change": {
            "long_tighter_initial_stop": True,
            "definition": "for long entries only, initial_stop = max(signal_day_low, close*(1-stop_loss_pct)); shorts unchanged",
        },
        "decision": decision_label,
        "judgment": (
            "This is a risk-sizing correction candidate, not an alpha filter. Promote only if yearly starts show broad "
            "drawdown improvement without materially sacrificing return breadth."
        ),
        "aggregate_all": all_row,
        "aggregate_mature_ex_2026": mature,
        "outputs": {
            "summary": str(SUMMARY_PATH),
            "curves": str(CURVES_PATH),
            "stop_adjustments": str(ADJUSTMENTS_PATH),
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
                "total_trade_count_base",
                "total_trade_count_candidate",
                "long_tighter_stop_adjust_count",
            ]
        ].to_string(index=False)
    )


if __name__ == "__main__":
    main()
