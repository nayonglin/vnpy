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

MODEL_TAG = "stage802_stage777_lower_high_bearish2_yearly_v1"
OUTPUT_PREFIX = "qmt_roll_stage802_stage777_lower_high_bearish2_yearly"
LINE_ID = "futures_trend_2019_data_extension"

YEAR_STARTS = s800.YEAR_STARTS
MAX_WORKERS = max(1, min(4, int(os.environ.get("STAGE802_MAX_WORKERS", "4"))))

VARIANT = "stage802_stage777_500k_am41_oi08_old_ai_lower_high_bearish2_yearly"
LABEL = "Stage802 Stage777 candidate lower highs plus two bearish candles yearly"

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
CURVES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv"
BLOCKS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_blocks_{MODEL_TAG}.csv"
COMPARISON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_comparison_vs_stage777_{MODEL_TAG}.csv"
AGG_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_aggregate_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
RETURN_BAR_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_return_delta_bar_{MODEL_TAG}.png"
DD_BAR_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_dd_delta_bar_{MODEL_TAG}.png"
EQUITY_CURVES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_equity_curves_{MODEL_TAG}.png"


class QmtRollPortfolioStrategyLongLowerHighBearish2Block(s772.QmtRollPortfolioStrategyExactAm):
    """Research-only wrapper: block long entries only when lower highs also have two bearish bodies."""

    block_long_lower_high_bearish2: bool = True
    parameters = [
        *s772.QmtRollPortfolioStrategyExactAm.parameters,
        "block_long_lower_high_bearish2",
    ]

    def _history_date_text(self, history: pd.DataFrame) -> str:
        if history is None or history.empty:
            return ""
        if "date" in history.columns:
            return str(pd.Timestamp(history["date"].iloc[-1]).date())
        index_value = history.index[-1]
        if isinstance(index_value, (int, np.integer)):
            return ""
        try:
            return str(pd.Timestamp(index_value).date())
        except Exception:
            return str(index_value)

    def _long_lower_high_bearish2(self, history: pd.DataFrame) -> tuple[bool, dict[str, Any]]:
        required = {"high", "open", "close"}
        if history is None or len(history) < 3 or not required.issubset(set(history.columns)):
            return False, {}
        highs = pd.to_numeric(history["high"].tail(3), errors="coerce")
        opens = pd.to_numeric(history["open"].tail(2), errors="coerce")
        closes = pd.to_numeric(history["close"].tail(2), errors="coerce")
        if highs.isna().any() or opens.isna().any() or closes.isna().any():
            return False, {}

        high_t2, high_t1, high_t = [float(value) for value in highs.to_list()]
        open_t1, open_t = [float(value) for value in opens.to_list()]
        close_t1, close_t = [float(value) for value in closes.to_list()]
        lower_high = bool(high_t < high_t1 < high_t2)
        bearish2 = bool(open_t > close_t and open_t1 > close_t1)
        blocked = bool(lower_high and bearish2)
        return blocked, {
            "filter_date": self._history_date_text(history),
            "high_t": high_t,
            "high_t_minus_1": high_t1,
            "high_t_minus_2": high_t2,
            "open_t": open_t,
            "open_t_minus_1": open_t1,
            "close_t": close_t,
            "close_t_minus_1": close_t1,
            "lower_high": lower_high,
            "bearish2": bearish2,
        }

    def _passes_entry_filters(self, signal: str, history: pd.DataFrame) -> bool:
        if not super()._passes_entry_filters(signal, history):
            return False
        if not bool(self.block_long_lower_high_bearish2):
            return True
        if not str(signal or "").startswith("long"):
            return True

        blocked, snapshot = self._long_lower_high_bearish2(history)
        if not blocked:
            return True
        self.trade_event_diagnostics.append(
            {
                "datetime": snapshot.get("filter_date", ""),
                "date": snapshot.get("filter_date", ""),
                "vt_symbol": "",
                "product_vt_symbol": "",
                "position_direction": "long",
                "direction": "long",
                "offset": "SignalFilter",
                "reason": "long_lower_high_bearish2_block",
                "volume": 0,
                "price": 0.0,
                "signal": signal,
                **snapshot,
            }
        )
        return False


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
            f"{spec.capital.note} | Stage802 yearly validation. Blocks long signals only when the latest three "
            "completed daily highs are strictly descending and the latest two completed daily candles are bearish."
        ),
    )
    overrides = {
        **spec.overrides,
        "block_long_lower_high_bearish2": True,
    }
    candidate = dict(base)
    candidate["profile"] = "stage802_oi_restore_am40_lower_high_bearish2"
    candidate["strategy_cls"] = QmtRollPortfolioStrategyLongLowerHighBearish2Block
    candidate["spec"] = replace(spec, capital=capital, overrides=overrides, profile=candidate["profile"])
    candidate["note"] = (
        "Stage777 candidate with a narrower long-only lower-high filter: require two bearish completed candles too."
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
        blocks = pd.DataFrame()
    else:
        blocks = trade_events[trade_events["reason"].eq("long_lower_high_bearish2_block")].copy()
    blocks["requested_start_month"] = _year_start_text(start)
    blocks["start_month"] = _year_start_text(start)
    row = summary.iloc[0].to_dict()
    row["lower_high_block_count"] = int(len(blocks))
    return row, curve, blocks


def _plot_delta_bars(comparison: pd.DataFrame) -> None:
    frame = comparison.copy()
    x = np.arange(len(frame))

    fig, ax = plt.subplots(figsize=(13, 5))
    colors = np.where(frame["total_return_pct_delta"].ge(0), "#16a34a", "#dc2626")
    ax.bar(x, frame["total_return_pct_delta"], color=colors, alpha=0.82)
    ax.axhline(0, color="#111827", linewidth=1)
    ax.set_xticks(x)
    ax.set_xticklabels(frame["start_month"], rotation=30, ha="right")
    ax.set_title("Stage802 yearly starts: return delta C bearish lower-high block vs A Stage777")
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
    ax.set_title("Stage802 yearly starts: max drawdown delta C bearish lower-high block vs A Stage777")
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
            ax.plot(cand["date"], cand["rebased_equity"] / 1_000_000, label="C lower-high + bearish2", linewidth=1.3)
        ax.axhline(0.5, color="#9aa3af", linestyle="--", linewidth=0.8)
        ax.set_title(start_month)
        ax.grid(alpha=0.22)
        ax.tick_params(axis="x", labelrotation=25, labelsize=8)
        ax.tick_params(axis="y", labelsize=8)
    for ax in axes[len(starts) :]:
        ax.axis("off")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=2)
    fig.suptitle("Stage802 yearly equity curves: A Stage777 vs C lower-high + two bearish candles block", y=0.995)
    fig.tight_layout(rect=[0, 0, 1, 0.965])
    fig.savefig(EQUITY_CURVES_PATH, dpi=170)
    plt.close(fig)


def _write_report(comparison: pd.DataFrame, aggregate: pd.DataFrame, decision: dict[str, Any]) -> None:
    lines = [
        "# Stage802 Stage777候选版 lower-high + 双阴线多头过滤 年度起点回测",
        "",
        f"- line_id：`{LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        "- A：当前 `official_candidate_stage777_50w_am41_oi08_old_ai_v1`，从 Stage777 月度缓存抽取年度起点。",
        "- C：同 A，仅新增多头过滤：若最新三根已完成日线 `high[t] < high[t-1] < high[t-2]`，且最新两根已完成K线均 `open > close`，则不发多头新开/反手/换月重开信号。",
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
    base_summary, base_curves = s800._load_base_yearly()
    tasks = [start.strftime("%Y-%m-%d") for start in YEAR_STARTS]
    rows: list[dict[str, Any]] = []
    curves: list[pd.DataFrame] = []
    blocks: list[pd.DataFrame] = []

    print(f"[stage802] launching {len(tasks)} yearly runs workers={MAX_WORKERS}", flush=True)
    if MAX_WORKERS == 1:
        for idx, task in enumerate(tasks, start=1):
            print(f"[stage802] running {idx}/{len(tasks)} {task}", flush=True)
            row, curve, block = _run_one(task)
            rows.append(row)
            curves.append(curve)
            blocks.append(block)
    else:
        with ProcessPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_map = {executor.submit(_run_one, task): task for task in tasks}
            for idx, future in enumerate(as_completed(future_map), start=1):
                task = future_map[future]
                row, curve, block = future.result()
                rows.append(row)
                curves.append(curve)
                blocks.append(block)
                print(f"[stage802] completed {idx}/{len(tasks)} {task}", flush=True)

    candidate_summary = s772._add_month_fields(pd.DataFrame(rows)).sort_values("start_month").reset_index(drop=True)
    candidate_curves = pd.concat(curves, ignore_index=True, sort=False).sort_values(["start_month", "date"]).reset_index(drop=True)
    block_events = pd.concat(blocks, ignore_index=True, sort=False) if blocks else pd.DataFrame(columns=["start_month", "reason"])
    comparison = s800._comparison(candidate_summary, base_summary).sort_values("start_month").reset_index(drop=True)
    aggregate = s800._aggregate(comparison)

    candidate_summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    candidate_curves.to_csv(CURVES_PATH, index=False, encoding="utf-8-sig")
    block_events.to_csv(BLOCKS_PATH, index=False, encoding="utf-8-sig")
    comparison.to_csv(COMPARISON_PATH, index=False, encoding="utf-8-sig")
    aggregate.to_csv(AGG_PATH, index=False, encoding="utf-8-sig")
    _plot_delta_bars(comparison)
    _plot_equity_curves(candidate_curves, base_curves)

    mature = aggregate[aggregate["bucket"].eq("mature_ex_2026")].iloc[0].to_dict()
    all_row = aggregate[aggregate["bucket"].eq("all")].iloc[0].to_dict()
    decision_label = (
        "stage802_lower_high_bearish2_yearly_watch"
        if int(mature["candidate_return_win_count"]) >= 5
        and int(mature["candidate_dd_win_count"]) >= 5
        and float(mature["median_return_delta_pp"]) >= 0
        else "stage802_lower_high_bearish2_yearly_not_promoted"
    )
    decision = {
        "stage": "Stage802",
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "base": "official_candidate_stage777_50w_am41_oi08_old_ai_v1 yearly starts",
        "candidate": "Stage777 + long lower-high and two bearish completed candles block yearly starts",
        "change": {
            "block_long_lower_high_bearish2": True,
            "definition": (
                "block long signal when high[t] < high[t-1] < high[t-2] and "
                "open[t] > close[t] and open[t-1] > close[t-1] on completed daily bars"
            ),
        },
        "decision": decision_label,
        "judgment": (
            "Narrowed from Stage800 to reduce false blocks. Promote only if yearly starts show broad return/drawdown "
            "improvement without concentrating wins in one path."
        ),
        "aggregate_all": all_row,
        "aggregate_mature_ex_2026": mature,
        "outputs": {
            "summary": str(SUMMARY_PATH),
            "curves": str(CURVES_PATH),
            "blocks": str(BLOCKS_PATH),
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
