from __future__ import annotations

from dataclasses import replace
from datetime import datetime
import json
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


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

MODEL_TAG = "stage799_stage777_long_lower_high_block_2020_v1"
OUTPUT_PREFIX = "qmt_roll_stage799_stage777_long_lower_high_block_2020"
LINE_ID = "futures_trend_2019_data_extension"

START = pd.Timestamp("2020-01-01")
BASE_SUMMARY_PATH = OUTPUT_DIR / "qmt_roll_stage777_am41_oi08_monthly_summary_stage777_am41_oi08_monthly_v1.csv"
BASE_CURVES_PATH = OUTPUT_DIR / "qmt_roll_stage777_am41_oi08_monthly_curves_stage777_am41_oi08_monthly_v1.csv"

VARIANT = "stage799_stage777_500k_am41_oi08_old_ai_long_two_lower_high_block_2020"
LABEL = "Stage799 Stage777 candidate long two lower highs block 2020"

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
CURVES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv"
TRADE_EVENTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trade_events_{MODEL_TAG}.csv"
ENTRY_CANDIDATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_candidates_{MODEL_TAG}.csv"
LOWER_HIGH_BLOCKS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_lower_high_blocks_{MODEL_TAG}.csv"
COMPARISON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_comparison_vs_stage777_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_equity_vs_stage777_{MODEL_TAG}.png"


class QmtRollPortfolioStrategyLongTwoLowerHighBlock(s772.QmtRollPortfolioStrategyExactAm):
    """Research-only wrapper: block long entries after two consecutive lower highs."""

    block_long_two_lower_highs: bool = True
    parameters = [
        *s772.QmtRollPortfolioStrategyExactAm.parameters,
        "block_long_two_lower_highs",
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

    def _long_two_lower_highs(self, history: pd.DataFrame) -> tuple[bool, dict[str, Any]]:
        if history is None or len(history) < 3 or "high" not in history.columns:
            return False, {}
        highs = pd.to_numeric(history["high"].tail(3), errors="coerce")
        if highs.isna().any():
            return False, {}
        high_t2, high_t1, high_t = [float(value) for value in highs.to_list()]
        blocked = bool(high_t < high_t1 < high_t2)
        return blocked, {
            "filter_date": self._history_date_text(history),
            "high_t": high_t,
            "high_t_minus_1": high_t1,
            "high_t_minus_2": high_t2,
        }

    def _passes_entry_filters(self, signal: str, history: pd.DataFrame) -> bool:
        if not super()._passes_entry_filters(signal, history):
            return False
        if not bool(self.block_long_two_lower_highs):
            return True
        if not str(signal or "").startswith("long"):
            return True
        blocked, snapshot = self._long_two_lower_highs(history)
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
                "reason": "long_two_lower_high_block",
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


def _long_lower_high_profile(metadata: dict[str, Any]) -> dict[str, Any]:
    base = next(profile for profile in s772._profile_specs(metadata) if profile["profile"] == "oi_restore_am40")
    spec = base["spec"]
    capital = replace(
        spec.capital,
        variant=VARIANT,
        label=LABEL,
        note=(
            f"{spec.capital.note} | Stage799 only blocks long signals when the latest three completed "
            "daily highs are strictly descending: high[t] < high[t-1] < high[t-2]."
        ),
    )
    overrides = {
        **spec.overrides,
        "block_long_two_lower_highs": True,
    }
    candidate = dict(base)
    candidate["profile"] = "stage799_oi_restore_am40_long_two_lower_high_block"
    candidate["strategy_cls"] = QmtRollPortfolioStrategyLongTwoLowerHighBlock
    candidate["spec"] = replace(spec, capital=capital, overrides=overrides, profile=candidate["profile"])
    candidate["note"] = (
        "Stage777 candidate with a long-only lower-high exhaustion filter; all other AM41/OI/AI/risk settings unchanged."
    )
    return candidate


def _metric_from_combined(profile: dict[str, Any], combined: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    spec = profile["spec"]
    row, curve, costs = s748._metric_row(
        combined,
        spec=spec,
        window_name=s772._window_name(START),
        window_label=s772._window_label(START),
        window_group="single_start_2020",
        forced_events=pd.DataFrame(),
    )
    row = s772._metric_common(row)
    for key in ["profile", "oi_mode", "am_label", "declared_am_size", "note"]:
        row[key] = profile.get(key)
    row["requested_start_month"] = START.strftime("%Y-%m")
    row["start_month"] = START.strftime("%Y-%m")
    summary = s772._add_month_fields(pd.DataFrame([row]))

    curve = s772._curve_common(curve)
    for key in ["profile", "oi_mode", "am_label", "declared_am_size"]:
        curve[key] = profile.get(key)
    curve["requested_start_month"] = START.strftime("%Y-%m")
    curve["start_month"] = START.strftime("%Y-%m")
    return summary, curve, pd.DataFrame(costs)


def _load_base_summary() -> pd.Series:
    summary = pd.read_csv(BASE_SUMMARY_PATH)
    summary["start_month"] = summary["start_month"].astype(str)
    base = summary[summary["start_month"].eq(START.strftime("%Y-%m"))]
    if base.empty:
        raise RuntimeError(f"missing base Stage777 summary for {START.strftime('%Y-%m')}")
    return base.iloc[0]


def _comparison(summary: pd.DataFrame, lower_high_blocks: pd.DataFrame, entry_candidates: pd.DataFrame) -> pd.DataFrame:
    base = _load_base_summary()
    row = summary.iloc[0]
    fields = [
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
    records: list[dict[str, Any]] = []
    for metric, base_col, candidate_col in fields:
        base_value = float(pd.to_numeric(pd.Series([base[base_col]]), errors="coerce").iloc[0])
        candidate_value = float(pd.to_numeric(pd.Series([row[candidate_col]]), errors="coerce").iloc[0])
        records.append(
            {
                "metric": metric,
                "base_stage777": base_value,
                "candidate_stage799": candidate_value,
                "delta": candidate_value - base_value,
            }
        )

    records.extend(
        [
            {
                "metric": "lower_high_block_count",
                "base_stage777": 0.0,
                "candidate_stage799": float(len(lower_high_blocks)),
                "delta": float(len(lower_high_blocks)),
            },
            {
                "metric": "entry_candidate_rows",
                "base_stage777": np.nan,
                "candidate_stage799": float(len(entry_candidates)),
                "delta": np.nan,
            },
            {
                "metric": "opened_candidates",
                "base_stage777": np.nan,
                "candidate_stage799": float(entry_candidates["candidate_status"].eq("opened").sum())
                if not entry_candidates.empty and "candidate_status" in entry_candidates
                else 0.0,
                "delta": np.nan,
            },
        ]
    )
    return pd.DataFrame(records)


def _plot(curve: pd.DataFrame) -> None:
    if not BASE_CURVES_PATH.exists():
        return
    base = pd.read_csv(BASE_CURVES_PATH, parse_dates=["date"])
    base = base[base["start_month"].astype(str).eq(START.strftime("%Y-%m"))].copy()
    fig, ax = plt.subplots(figsize=(16, 7))
    if not base.empty:
        ax.plot(base["date"], base["rebased_equity"] / 1_000_000, label="A Stage777 candidate", linewidth=1.8)
    frame = curve.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    ax.plot(frame["date"], frame["rebased_equity"] / 1_000_000, label="C Stage799 long lower-high block", linewidth=1.8)
    ax.axhline(0.5, color="#9aa3af", linestyle="--", linewidth=1)
    ax.set_title("Stage777 candidate 2020 start: baseline vs long two-lower-high block")
    ax.set_xlabel("Date")
    ax.set_ylabel("Account equity (million)")
    ax.grid(alpha=0.25)
    ax.legend()
    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=180)
    plt.close(fig)


def _write_report(
    summary: pd.DataFrame,
    lower_high_blocks: pd.DataFrame,
    comparison: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    lines = [
        "# Stage799 Stage777候选版多头连续lower-high过滤 2020单路径回测",
        "",
        f"- line_id：`{LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        "- A：当前 `official_candidate_stage777_50w_am41_oi08_old_ai_v1`，2020 起点缓存结果。",
        "- C：同 A，仅新增多头过滤：若最新三根已完成日线 `high[t] < high[t-1] < high[t-2]`，则不发多头新开/反手/换月重开信号。",
        "- 保持不变：50万、AM41、基础风险 `0.40`、OI命中恢复 `0.80`、旧正式AI池、maxpos4、关闭连败缩放和 recovery sleeve。",
        "",
        "## Summary",
        "",
        _md_table(summary, max_rows=5),
        "",
        "## Comparison vs Stage777",
        "",
        _md_table(comparison, max_rows=30),
        "",
        "## Lower-high blocks",
        "",
        _md_table(lower_high_blocks.head(30), max_rows=30),
        "",
        "## Decision",
        "",
        f"- 决策：`{decision['decision']}`",
        f"- 判断：{decision['judgment']}",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    metadata = s513._metadata()
    profile = _long_lower_high_profile(metadata)
    base_c3_overrides = dict(s513._c3_overrides(pd.Timestamp("2018-01-01").to_pydatetime()))

    combined, frames = s778._run_profile(
        profile=profile,
        start=START,
        metadata=metadata,
        base_c3_overrides=base_c3_overrides,
    )
    summary, curve, _cost = _metric_from_combined(profile, combined)
    trade_events = frames.get("trade_events", pd.DataFrame()).copy()
    entry_candidates = frames.get("entry_candidates", pd.DataFrame()).copy()
    lower_high_blocks = trade_events[trade_events.get("reason", pd.Series(dtype=str)).eq("long_two_lower_high_block")].copy()
    comparison = _comparison(summary, lower_high_blocks, entry_candidates)

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    curve.to_csv(CURVES_PATH, index=False, encoding="utf-8-sig")
    trade_events.to_csv(TRADE_EVENTS_PATH, index=False, encoding="utf-8-sig")
    entry_candidates.to_csv(ENTRY_CANDIDATES_PATH, index=False, encoding="utf-8-sig")
    lower_high_blocks.to_csv(LOWER_HIGH_BLOCKS_PATH, index=False, encoding="utf-8-sig")
    comparison.to_csv(COMPARISON_PATH, index=False, encoding="utf-8-sig")
    _plot(curve)

    compare_map = comparison.set_index("metric").to_dict("index")
    ret_delta = float(compare_map["total_return_pct"]["delta"])
    dd_delta = float(compare_map["max_dd_pct"]["delta"])
    sharpe_delta = float(compare_map["sharpe"]["delta"])
    block_count = int(compare_map["lower_high_block_count"]["candidate_stage799"])
    decision_label = (
        "stage799_long_lower_high_block_2020_single_path_watch"
        if ret_delta > 0 and dd_delta >= -2.0 and sharpe_delta >= 0.0
        else "stage799_long_lower_high_block_2020_single_path_not_promoted"
    )
    decision = {
        "stage": "Stage799",
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "variant": VARIANT,
        "base": "official_candidate_stage777_50w_am41_oi08_old_ai_v1 2020 start",
        "candidate": "Stage777 + long two-lower-high block 2020 start",
        "change": {
            "block_long_two_lower_highs": True,
            "definition": "block long signal when high[t] < high[t-1] < high[t-2] on completed daily bars",
        },
        "decision": decision_label,
        "judgment": (
            "Single 2020 path only. This filter has a structural trend-quality rationale, but it must not be promoted "
            "unless multi-start tests show it reduces drawdown without cutting the right tail."
        ),
        "delta": {
            "return_pct": ret_delta,
            "max_dd_pp": dd_delta,
            "sharpe": sharpe_delta,
            "blocked_long_signals": block_count,
        },
        "outputs": {
            "summary": str(SUMMARY_PATH),
            "curves": str(CURVES_PATH),
            "trade_events": str(TRADE_EVENTS_PATH),
            "entry_candidates": str(ENTRY_CANDIDATES_PATH),
            "lower_high_blocks": str(LOWER_HIGH_BLOCKS_PATH),
            "comparison": str(COMPARISON_PATH),
            "chart": str(CHART_PATH),
            "report": str(REPORT_PATH),
        },
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_report(summary, lower_high_blocks, comparison, decision)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print(comparison.to_string(index=False))


if __name__ == "__main__":
    main()
