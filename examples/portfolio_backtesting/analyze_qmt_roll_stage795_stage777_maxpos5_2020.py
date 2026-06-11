from __future__ import annotations

from dataclasses import replace
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

MODEL_TAG = "stage795_stage777_maxpos5_2020_v1"
OUTPUT_PREFIX = "qmt_roll_stage795_stage777_maxpos5_2020"
LINE_ID = "futures_trend_2019_data_extension"

START = pd.Timestamp("2020-01-01")
BASE_SUMMARY_PATH = OUTPUT_DIR / "qmt_roll_stage777_am41_oi08_monthly_summary_stage777_am41_oi08_monthly_v1.csv"
BASE_CURVES_PATH = OUTPUT_DIR / "qmt_roll_stage777_am41_oi08_monthly_curves_stage777_am41_oi08_monthly_v1.csv"
BASE_ENTRY_CANDIDATES_PATH = (
    OUTPUT_DIR
    / "qmt_roll_stage794_stage777_2020_capacity_block_entry_candidates_stage794_stage777_2020_capacity_block_v1.csv"
)

VARIANT = "stage795_stage777_500k_am41_oi08_old_ai_maxpos5_2020"
LABEL = "Stage795 Stage777 candidate maxpos5 2020"

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
CURVES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv"
ENTRY_CANDIDATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_candidates_{MODEL_TAG}.csv"
SKIP_REASON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_skip_reason_{MODEL_TAG}.csv"
COMPARISON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_comparison_vs_maxpos4_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_equity_vs_maxpos4_{MODEL_TAG}.png"


def _json_safe(value: Any) -> Any:
    return s650._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s650._md_table(frame, max_rows=max_rows)


def _maxpos5_profile(metadata: dict[str, Any]) -> dict[str, Any]:
    base = next(profile for profile in s772._profile_specs(metadata) if profile["profile"] == "oi_restore_am40")
    spec = base["spec"]
    capital = replace(
        spec.capital,
        variant=VARIANT,
        label=LABEL,
        max_concurrent_positions=5,
        note=f"{spec.capital.note} | Stage795 only changes max_concurrent_positions from 4 to 5.",
    )
    overrides = {**spec.overrides, "max_concurrent_positions": 5}
    candidate = dict(base)
    candidate["profile"] = "stage795_oi_restore_am40_maxpos5"
    candidate["spec"] = replace(spec, capital=capital, overrides=overrides, profile=candidate["profile"])
    candidate["note"] = "Stage777 candidate with max_concurrent_positions=5; all other AM41/OI/AI/risk settings unchanged."
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


def _skip_reason(entry_candidates: pd.DataFrame) -> pd.DataFrame:
    if entry_candidates.empty:
        return pd.DataFrame(columns=["candidate_status", "skip_reason", "count"])
    frame = entry_candidates.copy()
    frame["skip_reason_filled"] = frame["skip_reason"].fillna("opened")
    out = (
        frame.groupby(["candidate_status", "skip_reason_filled"], dropna=False)
        .size()
        .reset_index(name="count")
        .sort_values("count", ascending=False)
        .rename(columns={"skip_reason_filled": "skip_reason"})
    )
    return out


def _load_base_summary() -> pd.Series:
    summary = pd.read_csv(BASE_SUMMARY_PATH)
    summary["start_month"] = summary["start_month"].astype(str)
    base = summary[summary["start_month"].eq(START.strftime("%Y-%m"))]
    if base.empty:
        raise RuntimeError(f"missing base Stage777 summary for {START.strftime('%Y-%m')}")
    return base.iloc[0]


def _base_skip_counts() -> dict[str, Any]:
    if not BASE_ENTRY_CANDIDATES_PATH.exists():
        return {}
    base = pd.read_csv(BASE_ENTRY_CANDIDATES_PATH)
    return {
        "base_candidate_rows": int(len(base)),
        "base_opened_candidates": int(base["candidate_status"].eq("opened").sum()),
        "base_concurrent_limit_count": int(base["skip_reason"].eq("concurrent_limit").sum()),
    }


def _comparison(summary: pd.DataFrame, entry_candidates: pd.DataFrame) -> pd.DataFrame:
    base = _load_base_summary()
    row = summary.iloc[0]
    fields = [
        ("end_equity", "end_equity"),
        ("total_return_pct", "rebased_total_return_pct"),
        ("max_dd_pct", "rebased_max_dd_pct"),
        ("sharpe", "rebased_sharpe"),
        ("total_slippage", "total_slippage"),
        ("total_trade_count", "total_trade_count"),
        ("nonzero_daily_win_rate_pct", "nonzero_daily_win_rate_pct"),
        ("max_broker10_margin_to_equity_pct", "max_broker10_margin_to_equity_pct"),
        ("p95_broker10_margin_to_equity_pct", "p95_broker10_margin_to_equity_pct"),
    ]
    records: list[dict[str, Any]] = []
    for metric, base_col in fields:
        candidate_col = base_col
        base_value = float(pd.to_numeric(pd.Series([base[base_col]]), errors="coerce").iloc[0])
        candidate_value = float(pd.to_numeric(pd.Series([row[candidate_col]]), errors="coerce").iloc[0])
        records.append(
            {
                "metric": metric,
                "base_maxpos4": base_value,
                "candidate_maxpos5": candidate_value,
                "delta": candidate_value - base_value,
            }
        )

    base_counts = _base_skip_counts()
    if base_counts:
        records.extend(
            [
                {
                    "metric": "entry_candidate_rows",
                    "base_maxpos4": base_counts["base_candidate_rows"],
                    "candidate_maxpos5": int(len(entry_candidates)),
                    "delta": int(len(entry_candidates)) - base_counts["base_candidate_rows"],
                },
                {
                    "metric": "opened_candidates",
                    "base_maxpos4": base_counts["base_opened_candidates"],
                    "candidate_maxpos5": int(entry_candidates["candidate_status"].eq("opened").sum())
                    if not entry_candidates.empty
                    else 0,
                    "delta": int(entry_candidates["candidate_status"].eq("opened").sum()) - base_counts["base_opened_candidates"]
                    if not entry_candidates.empty
                    else -base_counts["base_opened_candidates"],
                },
                {
                    "metric": "concurrent_limit_count",
                    "base_maxpos4": base_counts["base_concurrent_limit_count"],
                    "candidate_maxpos5": int(entry_candidates["skip_reason"].eq("concurrent_limit").sum())
                    if not entry_candidates.empty
                    else 0,
                    "delta": int(entry_candidates["skip_reason"].eq("concurrent_limit").sum()) - base_counts["base_concurrent_limit_count"]
                    if not entry_candidates.empty
                    else -base_counts["base_concurrent_limit_count"],
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
        ax.plot(base["date"], base["rebased_equity"] / 1_000_000, label="Stage777 maxpos4", linewidth=1.8)
    frame = curve.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    ax.plot(frame["date"], frame["rebased_equity"] / 1_000_000, label="Stage795 maxpos5", linewidth=1.8)
    ax.axhline(0.5, color="#9aa3af", linestyle="--", linewidth=1)
    ax.set_title("Stage777 candidate 2020 start: maxpos4 vs maxpos5")
    ax.set_xlabel("Date")
    ax.set_ylabel("Account equity (million)")
    ax.grid(alpha=0.25)
    ax.legend()
    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=180)
    plt.close(fig)


def _write_report(summary: pd.DataFrame, skip_reason: pd.DataFrame, comparison: pd.DataFrame, decision: dict[str, Any]) -> None:
    lines = [
        "# Stage795 Stage777候选版maxpos5 2020单路径回测",
        "",
        f"- line_id：`{LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        "- 改动：只把 `max_concurrent_positions` 从 `4` 改为 `5`。",
        "- 其余：50万、AM41、基础风险 `0.40`、OI命中恢复 `0.80`、旧正式AI池、关闭连败缩放和recovery sleeve 均不变。",
        "",
        "## Summary",
        "",
        _md_table(summary, max_rows=5),
        "",
        "## Comparison vs maxpos4",
        "",
        _md_table(comparison, max_rows=30),
        "",
        "## Skip Reason",
        "",
        _md_table(skip_reason, max_rows=20),
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
    profile = _maxpos5_profile(metadata)
    base_c3_overrides = dict(s513._c3_overrides(pd.Timestamp("2018-01-01").to_pydatetime()))

    combined, frames = s778._run_profile(
        profile=profile,
        start=START,
        metadata=metadata,
        base_c3_overrides=base_c3_overrides,
    )
    summary, curve, _cost = _metric_from_combined(profile, combined)
    entry_candidates = frames.get("entry_candidates", pd.DataFrame()).copy()
    skip_reason = _skip_reason(entry_candidates)
    comparison = _comparison(summary, entry_candidates)

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    curve.to_csv(CURVES_PATH, index=False, encoding="utf-8-sig")
    entry_candidates.to_csv(ENTRY_CANDIDATES_PATH, index=False, encoding="utf-8-sig")
    skip_reason.to_csv(SKIP_REASON_PATH, index=False, encoding="utf-8-sig")
    comparison.to_csv(COMPARISON_PATH, index=False, encoding="utf-8-sig")
    _plot(curve)

    compare_map = comparison.set_index("metric").to_dict("index")
    ret_delta = float(compare_map["total_return_pct"]["delta"])
    dd_delta = float(compare_map["max_dd_pct"]["delta"])
    sharpe_delta = float(compare_map["sharpe"]["delta"])
    concurrent_delta = float(compare_map.get("concurrent_limit_count", {}).get("delta", np.nan))
    decision = {
        "stage": "Stage795",
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "variant": VARIANT,
        "base": "Stage777 maxpos4 2020",
        "candidate": "Stage777 maxpos5 2020",
        "change": {"max_concurrent_positions": {"before": 4, "after": 5}},
        "decision": "stage777_maxpos5_2020_single_path_watch" if ret_delta > 0 and dd_delta > -5 else "stage777_maxpos5_2020_single_path_not_promoted",
        "judgment": (
            "Single 2020 path only. Maxpos5 must not be promoted unless later multi-start tests show that the extra capacity "
            "improves returns without materially worsening drawdown, margin pressure, or correlated crowding."
        ),
        "delta": {
            "return_pct": ret_delta,
            "max_dd_pp": dd_delta,
            "sharpe": sharpe_delta,
            "concurrent_limit_count": concurrent_delta,
        },
        "outputs": {
            "summary": str(SUMMARY_PATH),
            "curves": str(CURVES_PATH),
            "entry_candidates": str(ENTRY_CANDIDATES_PATH),
            "skip_reason": str(SKIP_REASON_PATH),
            "comparison": str(COMPARISON_PATH),
            "chart": str(CHART_PATH),
            "report": str(REPORT_PATH),
        },
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_report(summary, skip_reason, comparison, decision)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
