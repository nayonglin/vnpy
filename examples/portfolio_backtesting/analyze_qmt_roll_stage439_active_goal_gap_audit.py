from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
LINE_ID = "futures_trend_drawdown30_preserve_return"
MODEL_TAG = "stage439_active_goal_gap_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage439_active_goal_gap_audit"

ACCOUNT_CAPITAL = 615_000.0

STAGE079 = "stage079"
STAGE103 = "xsmom_vt10_q_momq_round_half_true_broker10_guard"
STAGE115 = "stage103_plus_cffex_index_best1_tsmom60_guard"
OI_BEST1 = "stage103_plus_oi_confirm63_best1_weekly_guard"
OI_TOP3 = "stage103_plus_oi_confirm63_top3_weekly_guard"
VALUE756 = "stage103_plus_value_proxy756_monthly_guard"
STAGE136 = "stage103_plus_low_skew252_best1_vt10_mom63_round_half_guard"

LABELS = {
    STAGE079: "Stage079",
    STAGE103: "Stage103",
    STAGE115: "Stage115",
    OI_BEST1: "OI best1",
    OI_TOP3: "OI top3",
    VALUE756: "Value756",
    STAGE136: "Stage136",
}

DAILY_STAGE415 = OUTPUT_DIR / "qmt_roll_stage415_stage103_cffex_index_true_overlay_daily_stage415_stage103_cffex_index_true_overlay_v2.csv"
DAILY_STAGE422 = OUTPUT_DIR / "qmt_roll_stage422_stage103_long_value_proxy_overlay_daily_stage422_stage103_long_value_proxy_overlay_v1.csv"
DAILY_STAGE425 = OUTPUT_DIR / "qmt_roll_stage425_stage103_open_interest_confirmation_overlay_daily_stage425_stage103_open_interest_confirmation_overlay_v1.csv"
DAILY_STAGE436 = OUTPUT_DIR / "qmt_roll_stage436_skewness_vt_guard_daily_stage436_skewness_vt_guard_v1.csv"

SUMMARY_STAGE415 = OUTPUT_DIR / "qmt_roll_stage415_stage103_cffex_index_true_overlay_summary_stage415_stage103_cffex_index_true_overlay_v2.csv"
SUMMARY_STAGE422 = OUTPUT_DIR / "qmt_roll_stage422_stage103_long_value_proxy_overlay_summary_stage422_stage103_long_value_proxy_overlay_v1.csv"
SUMMARY_STAGE425 = OUTPUT_DIR / "qmt_roll_stage425_stage103_open_interest_confirmation_overlay_summary_stage425_stage103_open_interest_confirmation_overlay_v1.csv"
SUMMARY_STAGE436 = OUTPUT_DIR / "qmt_roll_stage436_skewness_vt_guard_summary_stage436_skewness_vt_guard_v1.csv"

GATE_STAGE415 = OUTPUT_DIR / "qmt_roll_stage415_stage103_cffex_index_true_overlay_gate_stage415_stage103_cffex_index_true_overlay_v2.csv"
GATE_STAGE422 = OUTPUT_DIR / "qmt_roll_stage422_stage103_long_value_proxy_overlay_gate_stage422_stage103_long_value_proxy_overlay_v1.csv"
GATE_STAGE425 = OUTPUT_DIR / "qmt_roll_stage425_stage103_open_interest_confirmation_overlay_gate_stage425_stage103_open_interest_confirmation_overlay_v1.csv"
GATE_STAGE436 = OUTPUT_DIR / "qmt_roll_stage436_skewness_vt_guard_gate_stage436_skewness_vt_guard_v1.csv"

COST_STAGE415 = OUTPUT_DIR / "qmt_roll_stage415_stage103_cffex_index_true_overlay_cost_stress_stage415_stage103_cffex_index_true_overlay_v2.csv"
COST_STAGE422 = OUTPUT_DIR / "qmt_roll_stage422_stage103_long_value_proxy_overlay_cost_stress_stage422_stage103_long_value_proxy_overlay_v1.csv"
COST_STAGE425 = OUTPUT_DIR / "qmt_roll_stage425_stage103_open_interest_confirmation_overlay_cost_stress_stage425_stage103_open_interest_confirmation_overlay_v1.csv"
COST_STAGE436 = OUTPUT_DIR / "qmt_roll_stage436_skewness_vt_guard_cost_stress_stage436_skewness_vt_guard_v1.csv"

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
TARGET_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_target_metrics_{MODEL_TAG}.csv"
GAP_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gap_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"


@dataclass(frozen=True)
class VariantSource:
    variant: str
    daily_path: Path
    summary_path: Path
    gate_path: Path
    cost_path: Path
    status_before_stage139: str


SOURCES = [
    VariantSource(STAGE079, DAILY_STAGE425, SUMMARY_STAGE425, GATE_STAGE425, COST_STAGE425, "baseline"),
    VariantSource(STAGE103, DAILY_STAGE425, SUMMARY_STAGE425, GATE_STAGE425, COST_STAGE425, "main_candidate"),
    VariantSource(STAGE115, DAILY_STAGE415, SUMMARY_STAGE415, GATE_STAGE415, COST_STAGE415, "high_score_paper"),
    VariantSource(OI_BEST1, DAILY_STAGE425, SUMMARY_STAGE425, GATE_STAGE425, COST_STAGE425, "paper_candidate"),
    VariantSource(OI_TOP3, DAILY_STAGE425, SUMMARY_STAGE425, GATE_STAGE425, COST_STAGE425, "hard_fail_fresh_start"),
    VariantSource(VALUE756, DAILY_STAGE422, SUMMARY_STAGE422, GATE_STAGE422, COST_STAGE422, "paper_candidate_sample_gap"),
    VariantSource(STAGE136, DAILY_STAGE436, SUMMARY_STAGE436, GATE_STAGE436, COST_STAGE436, "paper_overfit_warning"),
]


TARGETS = {
    90: {
        "return_p05_pct_min_exclusive": -8.0,
        "return_median_pct_min": 13.52,
        "positive_return_rate_min": 0.80,
        "annualized_below_5pct_rate_max": 0.22,
        "max_dd_worst_pct_min": -29.20,
        "dd20_breach_rate_max": 0.12,
        "dd30_breach_rate_max": 0.0,
        "ulcer_p95_pct_max": 15.0,
        "longest_underwater_p95_days_max": 80.0,
    },
    180: {
        "return_p05_pct_min_exclusive": 0.0,
        "return_median_pct_min": 33.92,
        "positive_return_rate_min": 0.95,
        "annualized_below_5pct_rate_max": 0.06,
        "max_dd_worst_pct_min": -29.70,
        "dd20_breach_rate_max": 0.25,
        "dd30_breach_rate_max": 0.0,
        "ulcer_p95_pct_max": 17.0,
        "longest_underwater_p95_days_max": 150.0,
    },
}


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    frame = pd.read_csv(path, encoding="utf-8-sig")
    if "date" in frame.columns:
        frame["date"] = pd.to_datetime(frame["date"]).dt.normalize()
    return frame


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, tuple):
        return [_json_safe(v) for v in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        result = float(value)
        return None if math.isnan(result) or math.isinf(result) else result
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    return value


def _max_drawdown_pct(nav: np.ndarray) -> float:
    if len(nav) == 0:
        return 0.0
    peak = np.maximum.accumulate(nav)
    return float(np.min(nav / peak - 1.0) * 100.0)


def _ulcer_pct(nav: np.ndarray) -> float:
    if len(nav) == 0:
        return 0.0
    peak = np.maximum.accumulate(nav)
    dd_pct = np.minimum(nav / peak - 1.0, 0.0) * 100.0
    return float(np.sqrt(np.mean(dd_pct**2)))


def _longest_underwater_days(nav: np.ndarray) -> int:
    if len(nav) == 0:
        return 0
    peak = np.maximum.accumulate(nav)
    underwater = nav < peak
    best = 0
    current = 0
    for flag in underwater:
        if bool(flag):
            current += 1
            best = max(best, current)
        else:
            current = 0
    return int(best)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "无数据。"
    view = frame.copy()
    if max_rows is not None:
        view = view.head(max_rows)
    for col in view.columns:
        if pd.api.types.is_float_dtype(view[col]):
            view[col] = view[col].map(lambda x: f"{x:.4f}" if pd.notna(x) else "")
    return view.to_markdown(index=False)


def _series_for_variant(source: VariantSource) -> pd.Series:
    daily = _read_csv(source.daily_path)
    view = daily[daily["window_name"].eq("start_2020") & daily["variant"].eq(source.variant)].copy()
    if view.empty:
        raise ValueError(f"no daily rows for {source.variant} in {source.daily_path}")
    series = pd.Series(view["equity"].astype(float).to_numpy(), index=pd.to_datetime(view["date"])).sort_index()
    calendar = series.reindex(pd.date_range(series.index.min(), series.index.max(), freq="D")).ffill()
    calendar.index.name = "date"
    return calendar


def _summary_for_variant(source: VariantSource) -> pd.Series:
    summary = _read_csv(source.summary_path)
    row = summary[summary["variant"].eq(source.variant)]
    if row.empty:
        raise ValueError(f"no summary row for {source.variant} in {source.summary_path}")
    return row.iloc[0]


def _gate_for_variant(source: VariantSource) -> pd.Series:
    gate = _read_csv(source.gate_path)
    row = gate[gate["variant"].eq(source.variant)]
    if row.empty:
        raise ValueError(f"no gate row for {source.variant} in {source.gate_path}")
    return row.iloc[0]


def _cost_not_worse_than_stage079(source: VariantSource) -> tuple[bool, dict[str, float]]:
    cost = _read_csv(source.cost_path)
    rows = cost[cost["variant"].isin([STAGE079, source.variant]) & cost["slippage_multiplier"].isin([1.0, 2.0, 3.0, 5.0])]
    base = rows[rows["variant"].eq(STAGE079)].set_index("slippage_multiplier")["max_dd_pct"].astype(float)
    cand = rows[rows["variant"].eq(source.variant)].set_index("slippage_multiplier")["max_dd_pct"].astype(float)
    values: dict[str, float] = {}
    ok = True
    for mult in [1.0, 2.0, 3.0, 5.0]:
        key = f"cost_{int(mult)}x_max_dd_pct"
        values[key] = float(cand.loc[mult])
        if float(cand.loc[mult]) < float(base.loc[mult]) - 1e-9:
            ok = False
    return ok, values


def _rolling_metrics(equity: pd.Series, window: int) -> dict[str, float]:
    rows: list[dict[str, float]] = []
    dates = pd.Index(equity.index)
    values = equity.to_numpy(dtype=float)
    last_start = equity.index.max() - pd.Timedelta(days=window)
    for start_idx, start_date in enumerate(equity.index):
        if start_date > last_start:
            break
        end_date = start_date + pd.Timedelta(days=window)
        if end_date not in dates:
            continue
        end_idx = int(dates.get_loc(end_date))
        segment = values[start_idx : end_idx + 1]
        nav = segment / segment[0]
        total_return = nav[-1] - 1.0
        annualized = (1.0 + total_return) ** (365.0 / window) - 1.0 if total_return > -1.0 else -1.0
        rows.append(
            {
                "return_pct": total_return * 100.0,
                "annualized_return_pct": annualized * 100.0,
                "max_dd_pct": _max_drawdown_pct(nav),
                "ulcer_pct": _ulcer_pct(nav),
                "longest_underwater_days": float(_longest_underwater_days(nav)),
            }
        )
    frame = pd.DataFrame(rows)
    return {
        "window_days": float(window),
        "sample_count": float(len(frame)),
        "return_p05_pct": float(frame["return_pct"].quantile(0.05)),
        "return_median_pct": float(frame["return_pct"].median()),
        "positive_return_rate": float((frame["return_pct"] > 0.0).mean()),
        "annualized_below_5pct_rate": float((frame["annualized_return_pct"] < 5.0).mean()),
        "max_dd_worst_pct": float(frame["max_dd_pct"].min()),
        "dd20_breach_rate": float((frame["max_dd_pct"] < -20.0).mean()),
        "dd30_breach_rate": float((frame["max_dd_pct"] < -30.0).mean()),
        "ulcer_p95_pct": float(frame["ulcer_pct"].quantile(0.95)),
        "longest_underwater_p95_days": float(frame["longest_underwater_days"].quantile(0.95)),
    }


def _target_pass(metrics: dict[str, float], window: int) -> tuple[int, list[str]]:
    target = TARGETS[window]
    checks = {
        "return_p05": metrics["return_p05_pct"] > target["return_p05_pct_min_exclusive"],
        "return_median": metrics["return_median_pct"] >= target["return_median_pct_min"],
        "positive_rate": metrics["positive_return_rate"] >= target["positive_return_rate_min"],
        "below_5_rate": metrics["annualized_below_5pct_rate"] <= target["annualized_below_5pct_rate_max"],
        "worst_dd": metrics["max_dd_worst_pct"] >= target["max_dd_worst_pct_min"],
        "dd20_rate": metrics["dd20_breach_rate"] <= target["dd20_breach_rate_max"],
        "dd30_rate": metrics["dd30_breach_rate"] <= target["dd30_breach_rate_max"],
        "ulcer_p95": metrics["ulcer_p95_pct"] <= target["ulcer_p95_pct_max"],
        "uw_p95": metrics["longest_underwater_p95_days"] <= target["longest_underwater_p95_days_max"],
    }
    failed = [name for name, ok in checks.items() if not ok]
    return int(all(checks.values())), failed


def _improved_count(metrics: dict[str, float], base: dict[str, float]) -> tuple[int, list[str]]:
    checks = {
        "return_p05": metrics["return_p05_pct"] > base["return_p05_pct"],
        "return_median": metrics["return_median_pct"] >= base["return_median_pct"],
        "positive_rate": metrics["positive_return_rate"] > base["positive_return_rate"],
        "below_5_rate": metrics["annualized_below_5pct_rate"] < base["annualized_below_5pct_rate"],
        "worst_dd": metrics["max_dd_worst_pct"] >= base["max_dd_worst_pct"],
        "dd20_rate": metrics["dd20_breach_rate"] < base["dd20_breach_rate"],
        "ulcer_p95": metrics["ulcer_p95_pct"] < base["ulcer_p95_pct"],
        "uw_p95": metrics["longest_underwater_p95_days"] < base["longest_underwater_p95_days"],
    }
    improved = [name for name, ok in checks.items() if ok]
    return len(improved), improved


def _hard_pass(summary: pd.Series, gate: pd.Series, cost_ok: bool) -> tuple[int, list[str]]:
    tol = 1e-3
    checks = {
        "total_return": float(summary["total_return_pct"]) >= 4947.2602 - tol,
        "max_dd_not_worse": float(summary["max_dd_pct"]) >= -29.7007 - tol,
        "max_dd_below_30": float(summary["max_dd_pct"]) > -30.0,
        "sharpe": float(summary["sharpe"]) >= 1.3182 - tol,
        "ulcer": float(summary["ulcer_pct"]) <= 15.0931 + tol,
        "rolling252": float(summary.get("rolling252_dd30_breach_rate", 1.0)) <= 0.0,
        "rolling504": float(summary.get("rolling504_dd30_breach_rate", 1.0)) <= 0.0,
        "annual": float(summary.get("annual_cold_start_dd30_pass_rate", 0.0)) >= 1.0,
        "quarter": float(summary.get("quarter_cold_start_dd30_pass_rate", 0.0)) >= 1.0,
        "capital": float(summary.get("capital_used", ACCOUNT_CAPITAL)) <= ACCOUNT_CAPITAL,
        "cost_stress": cost_ok,
    }
    failed = [name for name, ok in checks.items() if not ok]
    gate_failed = str(gate.get("failed_stage079_metric_checks", ""))
    has_gate_failed = bool(gate_failed) and gate_failed != "nan"
    if has_gate_failed:
        failed.append(f"gate_failed:{gate_failed}")
    return int(all(checks.values()) and not has_gate_failed), failed


def _build() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    base_equity = _series_for_variant(SOURCES[0])
    base_metrics = {window: _rolling_metrics(base_equity, window) for window in [90, 180]}

    summary_rows: list[dict[str, Any]] = []
    target_rows: list[dict[str, Any]] = []

    for source in SOURCES:
        summary = _summary_for_variant(source)
        gate = _gate_for_variant(source)
        equity = _series_for_variant(source)
        cost_ok, cost_values = _cost_not_worse_than_stage079(source)
        hard_ok, hard_failed = _hard_pass(summary, gate, cost_ok)

        target_by_window: dict[int, dict[str, Any]] = {}
        for window in [90, 180]:
            metrics = _rolling_metrics(equity, window)
            exact_ok, exact_failed = _target_pass(metrics, window)
            improve_count, improved = _improved_count(metrics, base_metrics[window])
            score = float(gate.get(f"score_{window}d", np.nan))
            target_rows.append(
                {
                    "variant": source.variant,
                    "label": LABELS[source.variant],
                    "window_days": window,
                    **metrics,
                    "exact_target_pass": exact_ok,
                    "exact_target_failed": ",".join(exact_failed),
                    "improved_count_8_vs_stage079": improve_count,
                    "improved_metrics": ",".join(improved),
                    "score": score,
                    "score_improve_ge_10pct": int(score >= 110.0) if pd.notna(score) else 0,
                }
            )
            target_by_window[window] = {
                "exact_ok": exact_ok,
                "failed": exact_failed,
                "improve_count": improve_count,
                "score": score,
            }

        promotion_gate = int(
            hard_ok
            and target_by_window[90]["score"] >= 110.0
            and target_by_window[180]["score"] >= 110.0
            and target_by_window[90]["improve_count"] >= 5
            and target_by_window[180]["improve_count"] >= 5
        )
        strict_target_all = int(hard_ok and target_by_window[90]["exact_ok"] and target_by_window[180]["exact_ok"])

        summary_rows.append(
            {
                "variant": source.variant,
                "label": LABELS[source.variant],
                "status_before_stage139": source.status_before_stage139,
                "end_equity": float(summary["end_equity"]),
                "total_return_pct": float(summary["total_return_pct"]),
                "max_dd_pct": float(summary["max_dd_pct"]),
                "sharpe": float(summary["sharpe"]),
                "ulcer_pct": float(summary["ulcer_pct"]),
                "hard_gate_pass": hard_ok,
                "hard_gate_failed": ",".join(hard_failed),
                "score_90d": target_by_window[90]["score"],
                "score_180d": target_by_window[180]["score"],
                "improved_count_90d": target_by_window[90]["improve_count"],
                "improved_count_180d": target_by_window[180]["improve_count"],
                "promotion_gate_pass": promotion_gate,
                "strict_target_all_pass": strict_target_all,
                "exact_90d_failed": ",".join(target_by_window[90]["failed"]),
                "exact_180d_failed": ",".join(target_by_window[180]["failed"]),
                "cost_stress_not_worse_than_stage079": int(cost_ok),
                "fresh_start_dd30_pass": int(float(gate.get("fresh_start_dd30_pass", 0)) == 1.0),
                "deployment_absolute_margin_pass": int(float(gate.get("deployment_absolute_margin_pass", 0)) == 1.0),
                **cost_values,
            }
        )

    summary_frame = pd.DataFrame(summary_rows)
    target_frame = pd.DataFrame(target_rows)
    gap_frame = summary_frame[
        [
            "label",
            "status_before_stage139",
            "hard_gate_pass",
            "promotion_gate_pass",
            "strict_target_all_pass",
            "score_90d",
            "score_180d",
            "improved_count_90d",
            "improved_count_180d",
            "exact_90d_failed",
            "exact_180d_failed",
            "hard_gate_failed",
        ]
    ].copy()

    exact_passes = summary_frame[summary_frame["strict_target_all_pass"].eq(1)]["variant"].tolist()
    promotion_passes = summary_frame[summary_frame["promotion_gate_pass"].eq(1)]["variant"].tolist()
    decision = {
        "stage": "Stage139",
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "decision": "no_strict_full_target_candidate_keep_stage103_main",
        "strict_target_all_pass_variants": exact_passes,
        "promotion_gate_pass_variants": promotion_passes,
        "main_candidate": STAGE103,
        "judgement": (
            "没有候选同时满足3个月与6个月所有严格目标阈值；按晋级标准已有多个版本过线，"
            "但结合后续反过拟合审计，Stage103仍是主候选。"
        ),
        "next_research_filter": [
            "不救Stage115、Stage136、OI/value的失败小参数。",
            "下一步只允许全新低自由度风险源，或固定Stage103工程化/影子盘验证。",
        ],
        "outputs": {
            "summary": str(SUMMARY_PATH),
            "target_metrics": str(TARGET_PATH),
            "gap": str(GAP_PATH),
            "report": str(REPORT_PATH),
            "chart": str(CHART_PATH),
        },
    }
    return summary_frame, target_frame, gap_frame, _json_safe(decision)


def _plot(summary: pd.DataFrame, target: pd.DataFrame) -> None:
    view = summary[summary["variant"].ne(STAGE079)].copy()
    view = view.sort_values("score_180d", ascending=False)
    labels = view["label"].tolist()
    x = np.arange(len(view))
    width = 0.36

    fig, axes = plt.subplots(2, 2, figsize=(16, 10))

    ax = axes[0, 0]
    ax.bar(x - width / 2, view["score_90d"].astype(float), width=width, label="90d score", color="#4c78a8")
    ax.bar(x + width / 2, view["score_180d"].astype(float), width=width, label="180d score", color="#f58518")
    ax.axhline(110.0, color="#d62728", linestyle="--", linewidth=1)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=20)
    ax.set_title("Promotion score")
    ax.grid(axis="y", alpha=0.25)
    ax.legend()

    ax = axes[0, 1]
    ax.scatter(view["score_90d"], view["score_180d"], s=100, c=view["hard_gate_pass"], cmap="coolwarm", vmin=0, vmax=1)
    for _, row in view.iterrows():
        ax.annotate(row["label"], (row["score_90d"], row["score_180d"]), fontsize=9, xytext=(4, 4), textcoords="offset points")
    ax.axvline(110.0, color="#d62728", linestyle="--", linewidth=1)
    ax.axhline(110.0, color="#d62728", linestyle="--", linewidth=1)
    ax.set_xlabel("90d score")
    ax.set_ylabel("180d score")
    ax.set_title("Score gate and hard gate color")
    ax.grid(alpha=0.25)

    ax = axes[1, 0]
    pass_counts = []
    for variant in view["variant"]:
        rows = target[target["variant"].eq(variant)]
        pass_counts.append(int(rows["exact_target_pass"].sum()))
    ax.bar(labels, pass_counts, color="#54a24b")
    ax.set_ylim(0, 2)
    ax.set_title("Strict exact target horizons passed")
    ax.set_ylabel("0/1/2")
    ax.tick_params(axis="x", rotation=20)
    ax.grid(axis="y", alpha=0.25)

    ax = axes[1, 1]
    ax.bar(x - width / 2, view["improved_count_90d"].astype(float), width=width, label="90d improved /8", color="#72b7b2")
    ax.bar(x + width / 2, view["improved_count_180d"].astype(float), width=width, label="180d improved /8", color="#eeca3b")
    ax.axhline(5.0, color="#d62728", linestyle="--", linewidth=1)
    ax.set_ylim(0, 8.5)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=20)
    ax.set_title("Improved metrics vs Stage079")
    ax.grid(axis="y", alpha=0.25)
    ax.legend()

    fig.suptitle("Stage139 active goal gap audit", fontsize=15)
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    fig.savefig(CHART_PATH, dpi=180)
    plt.close(fig)


def _build_report(summary: pd.DataFrame, target: pd.DataFrame, gap: pd.DataFrame, decision: dict[str, Any]) -> str:
    summary_view = summary[
        [
            "label",
            "status_before_stage139",
            "total_return_pct",
            "max_dd_pct",
            "sharpe",
            "ulcer_pct",
            "hard_gate_pass",
            "score_90d",
            "score_180d",
            "improved_count_90d",
            "improved_count_180d",
            "promotion_gate_pass",
            "strict_target_all_pass",
        ]
    ]
    target_view = target[
        [
            "label",
            "window_days",
            "return_p05_pct",
            "return_median_pct",
            "positive_return_rate",
            "annualized_below_5pct_rate",
            "max_dd_worst_pct",
            "dd20_breach_rate",
            "ulcer_p95_pct",
            "longest_underwater_p95_days",
            "exact_target_pass",
            "exact_target_failed",
        ]
    ]
    return f"""# Stage139 主动目标缺口审计

- 生成时间：2026-05-28 03:11 CST
- line_id：`{LINE_ID}`
- 阶段性质：只读目标缺口审计；不新增交易规则、不调参数、不新增资金。
- 结论：`{decision["decision"]}`。

## 外部调研与判断

- 调研方向：Deflated Sharpe / PSR、PBO、walk-forward validation、商品期货趋势/动量与 open interest。
- 调研判断：趋势和 OI/动量有研究先验，但多候选回测后必须防止选择偏差；晋级不能只看最高3/6个月分，必须同时看严格目标阈值、贡献集中和后续鲁棒性降级。

## 候选总表

{_md_table(summary_view)}

## 3个月/6个月严格目标缺口

{_md_table(target_view)}

## 缺口摘要

{_md_table(gap)}

## 裁决

- 严格目标全通过候选：`{decision["strict_target_all_pass_variants"]}`。
- 晋级分数/改善数过线候选：`{decision["promotion_gate_pass_variants"]}`。
- 当前主候选仍为 Stage103 `{STAGE103}`。
- Stage115、Stage136、OI/value 仍只能 paper 或研究经验；不继续救这些路线的小参数。

## 过拟合反思

- 本阶段不是过拟合：只审计冻结候选与冻结阈值。
- 继续救已降级候选的单项失败指标会形成过拟合，尤其是按年份、贡献日、保证金小数或窗口去补洞。

## 继续价值反思

- 严格目标尚未完全完成，继续研究仍有价值。
- 最有价值的继续方向不是救旧路线，而是 Stage103 工程化/影子盘验证，或寻找全新、低自由度、保证金轻且样本更分散的风险源。

![Stage139 chart]({CHART_PATH})
"""


def main() -> None:
    summary, target, gap, decision = _build()
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    target.to_csv(TARGET_PATH, index=False, encoding="utf-8-sig")
    gap.to_csv(GAP_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(decision, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_PATH.write_text(_build_report(summary, target, gap, decision), encoding="utf-8")
    _plot(summary, target)
    print(f"decision={decision['decision']}")
    print(f"strict_target_all_pass={decision['strict_target_all_pass_variants']}")
    print(f"promotion_gate_pass={decision['promotion_gate_pass_variants']}")
    print(f"report={REPORT_PATH}")


if __name__ == "__main__":
    main()
