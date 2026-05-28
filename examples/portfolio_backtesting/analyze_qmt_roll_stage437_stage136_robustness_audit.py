from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

MODEL_TAG = "stage437_stage136_robustness_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage437_stage136_robustness_audit"
SOURCE_TAG = "stage436_skewness_vt_guard_v1"
SOURCE_PREFIX = "qmt_roll_stage436_skewness_vt_guard"
LINE_ID = "futures_trend_drawdown30_preserve_return"

ACCOUNT_CAPITAL = 615_000.0
BASELINE_VARIANT = "stage079"
STAGE103_VARIANT = "xsmom_vt10_q_momq_round_half_true_broker10_guard"
CANDIDATE_VARIANT = "stage103_plus_low_skew252_best1_vt10_mom63_round_half_guard"
TOP3_VARIANT = "stage103_plus_low_skew252_top3_vt10_mom63_round_half_guard"
VARIANT_ORDER = [BASELINE_VARIANT, STAGE103_VARIANT, CANDIDATE_VARIANT]
COMPARATORS = [BASELINE_VARIANT, STAGE103_VARIANT]

DAILY_IN = OUTPUT_DIR / f"{SOURCE_PREFIX}_daily_{SOURCE_TAG}.csv"
SUMMARY_IN = OUTPUT_DIR / f"{SOURCE_PREFIX}_summary_{SOURCE_TAG}.csv"
HORIZON_IN = OUTPUT_DIR / f"{SOURCE_PREFIX}_horizon_{SOURCE_TAG}.csv"
SCORE_IN = OUTPUT_DIR / f"{SOURCE_PREFIX}_score_{SOURCE_TAG}.csv"
FRESH_IN = OUTPUT_DIR / f"{SOURCE_PREFIX}_fresh_start_{SOURCE_TAG}.csv"
COST_IN = OUTPUT_DIR / f"{SOURCE_PREFIX}_cost_stress_{SOURCE_TAG}.csv"
MARGIN_IN = OUTPUT_DIR / f"{SOURCE_PREFIX}_margin_audit_{SOURCE_TAG}.csv"
GATE_IN = OUTPUT_DIR / f"{SOURCE_PREFIX}_gate_{SOURCE_TAG}.csv"

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
ROLLING_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_rolling_holding_{MODEL_TAG}.csv"
PAIRWISE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_pairwise_rolling_{MODEL_TAG}.csv"
BOOTSTRAP_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_block_bootstrap_{MODEL_TAG}.csv"
MONTH_PERMUTATION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_month_permutation_{MODEL_TAG}.csv"
YEAR_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_year_contribution_{MODEL_TAG}.csv"
YEAR_ABLATION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_leave_one_year_ablation_{MODEL_TAG}.csv"
TOPDAY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_top_edge_day_ablation_{MODEL_TAG}.csv"
PSR_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_psr_edge_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

LABELS = {
    BASELINE_VARIANT: "Stage079 baseline",
    STAGE103_VARIANT: "Stage103 broker10_guard",
    CANDIDATE_VARIANT: "Stage136 best1_vt",
}


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


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    frame = pd.read_csv(path, encoding="utf-8-sig")
    if "date" in frame.columns:
        frame["date"] = pd.to_datetime(frame["date"]).dt.normalize()
    return frame


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "无数据。"
    view = frame if max_rows is None else frame.head(max_rows)
    view = view.copy()
    for col in view.columns:
        if pd.api.types.is_float_dtype(view[col]):
            view[col] = view[col].map(lambda x: f"{x:.4f}" if pd.notna(x) else "")
    return view.to_markdown(index=False)


def _max_drawdown_pct(nav: np.ndarray) -> float:
    if len(nav) == 0:
        return 0.0
    peak = np.maximum.accumulate(nav)
    dd = nav / peak - 1.0
    return float(np.min(dd) * 100.0)


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


def _nav_from_returns(returns: np.ndarray, include_initial: bool = True) -> np.ndarray:
    clean = np.asarray(returns, dtype=float)
    nav = ACCOUNT_CAPITAL * np.cumprod(1.0 + clean)
    if include_initial:
        return np.concatenate([[ACCOUNT_CAPITAL], nav])
    return nav


def _metrics_from_returns(returns: np.ndarray) -> dict[str, float]:
    clean = np.asarray(returns, dtype=float)
    nav = _nav_from_returns(clean, include_initial=True)
    std = float(np.std(clean, ddof=1)) if len(clean) > 1 else 0.0
    sharpe = float(np.mean(clean) / std * math.sqrt(252.0)) if std > 0 else 0.0
    return {
        "end_equity": float(nav[-1]),
        "total_return_pct": float((nav[-1] / ACCOUNT_CAPITAL - 1.0) * 100.0),
        "max_dd_pct": _max_drawdown_pct(nav),
        "sharpe": sharpe,
        "ulcer_pct": _ulcer_pct(nav),
        "longest_underwater_days": float(_longest_underwater_days(nav)),
    }


def _build_return_frame(daily: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    full = daily[daily["window_name"].eq("start_2020") & daily["variant"].isin(VARIANT_ORDER)].copy()
    pivot = full.pivot_table(index="date", columns="variant", values="equity", aggfunc="last").sort_index()
    pivot = pivot[VARIANT_ORDER].dropna()
    calendar = pivot.reindex(pd.date_range(pivot.index.min(), pivot.index.max(), freq="D")).ffill()
    calendar.index.name = "date"
    returns = pivot.pct_change()
    returns.iloc[0] = pivot.iloc[0] / ACCOUNT_CAPITAL - 1.0
    return calendar, returns


def _rolling_holding_metrics(equity: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    windows = [21, 63, 90, 126, 180, 252, 504, 756]
    rolling_rows: list[dict[str, Any]] = []
    segment_cache: dict[tuple[str, int], pd.DataFrame] = {}
    date_index = pd.Index(equity.index)

    for variant in VARIANT_ORDER:
        values = equity[variant].to_numpy(dtype=float)
        for window in windows:
            rows: list[dict[str, Any]] = []
            last_start = equity.index.max() - pd.Timedelta(days=window)
            for start_idx, start_date in enumerate(equity.index):
                if start_date > last_start:
                    break
                end_date = start_date + pd.Timedelta(days=window)
                if end_date not in date_index:
                    continue
                end_idx = int(date_index.get_loc(end_date))
                segment = values[start_idx : end_idx + 1]
                nav = segment / segment[0]
                total_return = nav[-1] - 1.0
                annualized = (1.0 + total_return) ** (365.0 / window) - 1.0 if total_return > -1.0 else -1.0
                rows.append(
                    {
                        "start_date": start_date,
                        "end_date": end_date,
                        "window_days": window,
                        "return_pct": total_return * 100.0,
                        "annualized_return_pct": annualized * 100.0,
                        "max_dd_pct": _max_drawdown_pct(nav),
                        "ulcer_pct": _ulcer_pct(nav),
                        "longest_underwater_days": _longest_underwater_days(nav),
                    }
                )
            frame = pd.DataFrame(rows)
            segment_cache[(variant, window)] = frame
            rolling_rows.append(
                {
                    "variant": variant,
                    "label": LABELS[variant],
                    "window_days": window,
                    "count": len(frame),
                    "return_p01_pct": float(frame["return_pct"].quantile(0.01)),
                    "return_p05_pct": float(frame["return_pct"].quantile(0.05)),
                    "return_median_pct": float(frame["return_pct"].median()),
                    "positive_return_rate": float((frame["return_pct"] > 0.0).mean()),
                    "annualized_below_5pct_rate": float((frame["annualized_return_pct"] < 5.0).mean()),
                    "max_dd_worst_pct": float(frame["max_dd_pct"].min()),
                    "dd10_breach_rate": float((frame["max_dd_pct"] < -10.0).mean()),
                    "dd20_breach_rate": float((frame["max_dd_pct"] < -20.0).mean()),
                    "dd30_breach_rate": float((frame["max_dd_pct"] < -30.0).mean()),
                    "ulcer_p95_pct": float(frame["ulcer_pct"].quantile(0.95)),
                    "longest_underwater_p95_days": float(frame["longest_underwater_days"].quantile(0.95)),
                }
            )

    pairwise_rows: list[dict[str, Any]] = []
    for window in windows:
        cand = segment_cache[(CANDIDATE_VARIANT, window)]
        for comparator in COMPARATORS:
            comp = segment_cache[(comparator, window)]
            pairwise_rows.append(
                {
                    "candidate_variant": CANDIDATE_VARIANT,
                    "comparator_variant": comparator,
                    "window_days": window,
                    "count": len(comp),
                    "return_win_rate": float((cand["return_pct"] > comp["return_pct"]).mean()),
                    "return_delta_median_pp": float((cand["return_pct"] - comp["return_pct"]).median()),
                    "return_delta_p05_pp": float((cand["return_pct"] - comp["return_pct"]).quantile(0.05)),
                    "maxdd_not_worse_rate": float((cand["max_dd_pct"] >= comp["max_dd_pct"]).mean()),
                    "ulcer_not_worse_rate": float((cand["ulcer_pct"] <= comp["ulcer_pct"]).mean()),
                    "longest_uw_not_worse_rate": float(
                        (cand["longest_underwater_days"] <= comp["longest_underwater_days"]).mean()
                    ),
                    "all3_win_rate": float(
                        (
                            (cand["return_pct"] > comp["return_pct"])
                            & (cand["max_dd_pct"] >= comp["max_dd_pct"])
                            & (cand["ulcer_pct"] <= comp["ulcer_pct"])
                        ).mean()
                    ),
                }
            )
    return pd.DataFrame(rolling_rows), pd.DataFrame(pairwise_rows)


def _pairwise_resample_summary(samples: list[dict[str, float]], method: str, block_len: int | None) -> list[dict[str, Any]]:
    frame = pd.DataFrame(samples)
    rows: list[dict[str, Any]] = []
    for comparator in COMPARATORS:
        row: dict[str, Any] = {
            "method": method,
            "block_len_days": block_len,
            "candidate_variant": CANDIDATE_VARIANT,
            "comparator_variant": comparator,
            "sims": len(frame),
        }
        for variant in [comparator, CANDIDATE_VARIANT]:
            row[f"{variant}_return_median_pct"] = float(frame[f"{variant}_return_pct"].median())
            row[f"{variant}_return_p05_pct"] = float(frame[f"{variant}_return_pct"].quantile(0.05))
            row[f"{variant}_maxdd_median_pct"] = float(frame[f"{variant}_maxdd_pct"].median())
            row[f"{variant}_maxdd_p05_pct"] = float(frame[f"{variant}_maxdd_pct"].quantile(0.05))
            row[f"{variant}_ulcer_median_pct"] = float(frame[f"{variant}_ulcer_pct"].median())
            row[f"{variant}_dd30_breach_rate"] = float((frame[f"{variant}_maxdd_pct"] < -30.0).mean())
        row["return_win_rate"] = float(
            (frame[f"{CANDIDATE_VARIANT}_return_pct"] > frame[f"{comparator}_return_pct"]).mean()
        )
        row["maxdd_not_worse_rate"] = float(
            (frame[f"{CANDIDATE_VARIANT}_maxdd_pct"] >= frame[f"{comparator}_maxdd_pct"]).mean()
        )
        row["ulcer_not_worse_rate"] = float(
            (frame[f"{CANDIDATE_VARIANT}_ulcer_pct"] <= frame[f"{comparator}_ulcer_pct"]).mean()
        )
        row["all3_win_rate"] = float(
            (
                (frame[f"{CANDIDATE_VARIANT}_return_pct"] > frame[f"{comparator}_return_pct"])
                & (frame[f"{CANDIDATE_VARIANT}_maxdd_pct"] >= frame[f"{comparator}_maxdd_pct"])
                & (frame[f"{CANDIDATE_VARIANT}_ulcer_pct"] <= frame[f"{comparator}_ulcer_pct"])
            ).mean()
        )
        row["return_delta_median_pp"] = float(
            (frame[f"{CANDIDATE_VARIANT}_return_pct"] - frame[f"{comparator}_return_pct"]).median()
        )
        row["return_delta_p05_pp"] = float(
            (frame[f"{CANDIDATE_VARIANT}_return_pct"] - frame[f"{comparator}_return_pct"]).quantile(0.05)
        )
        row["maxdd_delta_median_pp"] = float(
            (frame[f"{CANDIDATE_VARIANT}_maxdd_pct"] - frame[f"{comparator}_maxdd_pct"]).median()
        )
        row["ulcer_delta_median_pp"] = float(
            (frame[f"{CANDIDATE_VARIANT}_ulcer_pct"] - frame[f"{comparator}_ulcer_pct"]).median()
        )
        rows.append(row)
    return rows


def _block_bootstrap(returns: pd.DataFrame, sims: int = 3000) -> pd.DataFrame:
    rng = np.random.default_rng(437136)
    data = returns[VARIANT_ORDER].to_numpy(dtype=float)
    n = len(data)
    out: list[dict[str, Any]] = []
    for block_len in [20, 60, 120]:
        samples: list[dict[str, float]] = []
        for _ in range(sims):
            indices: list[int] = []
            while len(indices) < n:
                start = int(rng.integers(0, n))
                indices.extend(((start + offset) % n) for offset in range(block_len))
            selected = data[np.array(indices[:n])]
            row: dict[str, float] = {}
            for idx, variant in enumerate(VARIANT_ORDER):
                metrics = _metrics_from_returns(selected[:, idx])
                row[f"{variant}_return_pct"] = metrics["total_return_pct"]
                row[f"{variant}_maxdd_pct"] = metrics["max_dd_pct"]
                row[f"{variant}_ulcer_pct"] = metrics["ulcer_pct"]
            samples.append(row)
        out.extend(_pairwise_resample_summary(samples, "moving_block_bootstrap", block_len))
    return pd.DataFrame(out)


def _month_permutation(returns: pd.DataFrame, sims: int = 3000) -> pd.DataFrame:
    rng = np.random.default_rng(437236)
    month_keys = returns.index.to_period("M")
    groups = [np.flatnonzero(month_keys == key) for key in month_keys.unique()]
    data = returns[VARIANT_ORDER].to_numpy(dtype=float)
    samples: list[dict[str, float]] = []
    for _ in range(sims):
        order = rng.permutation(len(groups))
        selected = np.concatenate([data[groups[i]] for i in order], axis=0)
        row: dict[str, float] = {}
        for idx, variant in enumerate(VARIANT_ORDER):
            metrics = _metrics_from_returns(selected[:, idx])
            row[f"{variant}_return_pct"] = metrics["total_return_pct"]
            row[f"{variant}_maxdd_pct"] = metrics["max_dd_pct"]
            row[f"{variant}_ulcer_pct"] = metrics["ulcer_pct"]
        samples.append(row)
    return pd.DataFrame(_pairwise_resample_summary(samples, "month_order_permutation", None))


def _top_edge_day_ablation(returns: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for comparator in COMPARATORS:
        edge = returns[CANDIDATE_VARIANT] - returns[comparator]
        positive_edge = edge[edge > 0].sort_values(ascending=False)
        comp_metrics = _metrics_from_returns(returns[comparator].to_numpy(dtype=float))
        for top_n in [0, 1, 3, 5, 10, 20, 40, 80, 120]:
            adjusted = returns[CANDIDATE_VARIANT].copy()
            removed_edge_return_sum_pp = 0.0
            if top_n > 0:
                remove_dates = positive_edge.head(top_n).index
                removed_edge_return_sum_pp = float(positive_edge.head(top_n).sum() * 100.0)
                adjusted.loc[remove_dates] = returns.loc[remove_dates, comparator]
            metrics = _metrics_from_returns(adjusted.to_numpy(dtype=float))
            rows.append(
                {
                    "candidate_variant": CANDIDATE_VARIANT,
                    "comparator_variant": comparator,
                    "removed_top_positive_edge_days": top_n,
                    "removed_edge_return_sum_pp": removed_edge_return_sum_pp,
                    "candidate_adjusted_total_return_pct": metrics["total_return_pct"],
                    "candidate_adjusted_max_dd_pct": metrics["max_dd_pct"],
                    "candidate_adjusted_sharpe": metrics["sharpe"],
                    "candidate_adjusted_ulcer_pct": metrics["ulcer_pct"],
                    "comparator_total_return_pct": comp_metrics["total_return_pct"],
                    "comparator_max_dd_pct": comp_metrics["max_dd_pct"],
                    "comparator_sharpe": comp_metrics["sharpe"],
                    "comparator_ulcer_pct": comp_metrics["ulcer_pct"],
                    "adjusted_return_delta_pp": metrics["total_return_pct"] - comp_metrics["total_return_pct"],
                    "adjusted_maxdd_delta_pp": metrics["max_dd_pct"] - comp_metrics["max_dd_pct"],
                    "adjusted_ulcer_delta_pp": metrics["ulcer_pct"] - comp_metrics["ulcer_pct"],
                }
            )
    return pd.DataFrame(rows)


def _year_contribution_and_ablation(returns: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    years = sorted(returns.index.year.unique())
    year_rows: list[dict[str, Any]] = []
    ablation_rows: list[dict[str, Any]] = []
    for year in years:
        year_frame = returns[returns.index.year == year]
        for variant in VARIANT_ORDER:
            metrics = _metrics_from_returns(year_frame[variant].to_numpy(dtype=float))
            year_rows.append(
                {
                    "year": int(year),
                    "variant": variant,
                    "label": LABELS[variant],
                    **metrics,
                }
            )
        left = returns[returns.index.year != year]
        cand_metrics = _metrics_from_returns(left[CANDIDATE_VARIANT].to_numpy(dtype=float))
        for comparator in COMPARATORS:
            comp_metrics = _metrics_from_returns(left[comparator].to_numpy(dtype=float))
            ablation_rows.append(
                {
                    "removed_year": int(year),
                    "candidate_variant": CANDIDATE_VARIANT,
                    "comparator_variant": comparator,
                    "candidate_total_return_pct": cand_metrics["total_return_pct"],
                    "candidate_max_dd_pct": cand_metrics["max_dd_pct"],
                    "candidate_ulcer_pct": cand_metrics["ulcer_pct"],
                    "comparator_total_return_pct": comp_metrics["total_return_pct"],
                    "comparator_max_dd_pct": comp_metrics["max_dd_pct"],
                    "comparator_ulcer_pct": comp_metrics["ulcer_pct"],
                    "return_delta_pp": cand_metrics["total_return_pct"] - comp_metrics["total_return_pct"],
                    "maxdd_delta_pp": cand_metrics["max_dd_pct"] - comp_metrics["max_dd_pct"],
                    "ulcer_delta_pp": cand_metrics["ulcer_pct"] - comp_metrics["ulcer_pct"],
                }
            )
    return pd.DataFrame(year_rows), pd.DataFrame(ablation_rows)


def _normal_cdf(value: float) -> float:
    return 0.5 * (1.0 + math.erf(value / math.sqrt(2.0)))


def _psr_for_series(series: pd.Series, benchmark_sr: float = 0.0) -> dict[str, Any]:
    clean = series.dropna().astype(float)
    n = len(clean)
    std = float(clean.std(ddof=1)) if n > 1 else 0.0
    sr = float(clean.mean() / std * math.sqrt(252.0)) if std > 0.0 else 0.0
    skew = float(clean.skew()) if n > 2 else 0.0
    kurt = float(clean.kurt() + 3.0) if n > 3 else 3.0
    denom = math.sqrt(max(1e-12, 1.0 - skew * sr + ((kurt - 1.0) / 4.0) * sr * sr))
    z = (sr - benchmark_sr) * math.sqrt(max(0, n - 1)) / denom
    return {
        "n": n,
        "annualized_sharpe": sr,
        "skew": skew,
        "kurtosis": kurt,
        "benchmark_sharpe": benchmark_sr,
        "psr_gt_benchmark": _normal_cdf(z),
    }


def _edge_psr(returns: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for comparator in COMPARATORS:
        edge = returns[CANDIDATE_VARIANT] - returns[comparator]
        rows.append(
            {
                "candidate_variant": CANDIDATE_VARIANT,
                "comparator_variant": comparator,
                **_psr_for_series(edge),
            }
        )
    return pd.DataFrame(rows)


def _summary_from_sources(
    source_summary: pd.DataFrame,
    source_score: pd.DataFrame,
    source_cost: pd.DataFrame,
    source_fresh: pd.DataFrame,
    source_margin: pd.DataFrame,
    source_gate: pd.DataFrame,
) -> pd.DataFrame:
    summary = source_summary[source_summary["variant"].isin(VARIANT_ORDER)].copy()
    score = (
        source_score[source_score["variant"].isin(VARIANT_ORDER)]
        .drop_duplicates("variant")
        .set_index("variant")[["score_90d", "score_180d", "short_holding_score"]]
    )
    cost = (
        source_cost[source_cost["variant"].isin(VARIANT_ORDER)]
        .pivot_table(index="variant", columns="slippage_multiplier", values="max_dd_pct", aggfunc="first")
        .rename(
            columns={
                1.0: "cost_1x_max_dd_pct",
                2.0: "cost_2x_max_dd_pct",
                3.0: "cost_3x_max_dd_pct",
                5.0: "cost_5x_max_dd_pct",
            }
        )
    )
    fresh = (
        source_fresh[source_fresh["variant"].isin(VARIANT_ORDER)]
        .groupby("variant")
        .agg(
            fresh_start_dd30_pass_rate=("dd30_pass", "mean"),
            fresh_start_worst_max_dd_pct=("max_dd_pct", "min"),
            fresh_start_min_return_pct=("total_return_pct", "min"),
            broker10_reject_days_total=("broker10_reject_days", "sum"),
        )
    )
    broker10 = (
        source_margin[
            source_margin["variant"].isin(VARIANT_ORDER) & source_margin["margin_multiplier"].eq(1.10)
        ]
        .groupby("variant")
        .agg(
            broker10_max_margin_to_equity_pct=("max_margin_to_equity_pct", "max"),
            broker10_required_extra_cash_max=("required_extra_cash_for_no_reject", "max"),
        )
    )
    gate_cols = [
        "metric_hard_pass_stage079",
        "metric_incremental_pass_stage103",
        "target_pass_3m6m_vs_stage079",
        "research_promotion_pass",
        "execution_relative_pass",
        "deployment_absolute_margin_pass",
        "failed_stage079_metric_checks",
        "failed_stage103_incremental_checks",
    ]
    gate = source_gate[source_gate["variant"].isin(VARIANT_ORDER)].set_index("variant")[
        [col for col in gate_cols if col in source_gate.columns]
    ]
    merged = summary.set_index("variant").join(score).join(cost).join(fresh).join(broker10).join(gate).reset_index()
    merged["label"] = merged["variant"].map(LABELS).fillna(merged["label"])
    return merged


def _make_decision(
    summary: pd.DataFrame,
    pairwise: pd.DataFrame,
    resample: pd.DataFrame,
    year_ablation: pd.DataFrame,
    topday: pd.DataFrame,
    psr: pd.DataFrame,
) -> dict[str, Any]:
    by_variant = summary.set_index("variant")
    base = by_variant.loc[BASELINE_VARIANT]
    stage103 = by_variant.loc[STAGE103_VARIANT]
    cand = by_variant.loc[CANDIDATE_VARIANT]

    stage079_goal_pass = bool(
        cand.get("metric_hard_pass_stage079", 0) == 1
        and cand.get("target_pass_3m6m_vs_stage079", 0) == 1
        and cand.get("deployment_absolute_margin_pass", 0) == 1
        and cand.get("cost_2x_max_dd_pct", -999.0) >= base.get("cost_2x_max_dd_pct", 999.0)
        and cand.get("cost_3x_max_dd_pct", -999.0) >= base.get("cost_3x_max_dd_pct", 999.0)
        and cand.get("cost_5x_max_dd_pct", -999.0) >= base.get("cost_5x_max_dd_pct", 999.0)
    )

    resample_vs_stage079 = resample[resample["comparator_variant"].eq(BASELINE_VARIANT)]
    resample_vs_stage103 = resample[resample["comparator_variant"].eq(STAGE103_VARIANT)]
    stage079_resample_pass = bool(
        (resample_vs_stage079["return_delta_median_pp"] > 0.0).all()
        and (resample_vs_stage079["maxdd_not_worse_rate"] >= 0.75).all()
        and (resample_vs_stage079["ulcer_not_worse_rate"] >= 0.85).all()
        and (resample_vs_stage079[f"{CANDIDATE_VARIANT}_dd30_breach_rate"] <= resample_vs_stage079[f"{BASELINE_VARIANT}_dd30_breach_rate"]).all()
    )
    year_vs_stage079 = year_ablation[year_ablation["comparator_variant"].eq(BASELINE_VARIANT)]
    stage079_year_ablation_pass = bool(
        (year_vs_stage079["return_delta_pp"] > 0.0).all()
        and (year_vs_stage079["maxdd_delta_pp"] >= -0.35).all()
        and (year_vs_stage079["ulcer_delta_pp"] <= 0.0).all()
    )
    top_vs_stage079 = topday[topday["comparator_variant"].eq(BASELINE_VARIANT)]
    row20_vs_stage079 = top_vs_stage079[top_vs_stage079["removed_top_positive_edge_days"].eq(20)].iloc[0]
    row40_vs_stage079 = top_vs_stage079[top_vs_stage079["removed_top_positive_edge_days"].eq(40)].iloc[0]
    stage079_topday_pass = bool(
        row20_vs_stage079["adjusted_return_delta_pp"] > 0.0
        and row20_vs_stage079["candidate_adjusted_max_dd_pct"] >= base["max_dd_pct"]
        and row20_vs_stage079["candidate_adjusted_ulcer_pct"] <= base["ulcer_pct"]
        and row40_vs_stage079["candidate_adjusted_max_dd_pct"] >= -30.0
    )
    stage079_edge_psr_pass = bool(
        psr[psr["comparator_variant"].eq(BASELINE_VARIANT)]["psr_gt_benchmark"].iloc[0] >= 0.95
    )

    pairwise_vs_stage103 = pairwise[pairwise["comparator_variant"].eq(STAGE103_VARIANT)]
    strict_stage103_rolling_return_pass = bool(
        pairwise_vs_stage103[pairwise_vs_stage103["window_days"].isin([90, 180, 252, 504])][
            "return_win_rate"
        ].min()
        >= 0.55
    )
    strict_stage103_resample_return_pass = bool((resample_vs_stage103["return_win_rate"] >= 0.55).all())
    top_vs_stage103 = topday[topday["comparator_variant"].eq(STAGE103_VARIANT)]
    row20_vs_stage103 = top_vs_stage103[top_vs_stage103["removed_top_positive_edge_days"].eq(20)].iloc[0]
    strict_stage103_topday_pass = bool(
        row20_vs_stage103["adjusted_return_delta_pp"] > 0.0
        and row20_vs_stage103["adjusted_maxdd_delta_pp"] >= 0.0
        and row20_vs_stage103["adjusted_ulcer_delta_pp"] <= 0.0
    )
    strict_stage103_replace_pass = bool(
        cand["total_return_pct"] >= stage103["total_return_pct"]
        and cand["max_dd_pct"] >= stage103["max_dd_pct"]
        and cand["sharpe"] >= stage103["sharpe"]
        and cand["ulcer_pct"] <= stage103["ulcer_pct"]
        and strict_stage103_rolling_return_pass
        and strict_stage103_resample_return_pass
        and strict_stage103_topday_pass
    )

    stage079_anti_overfit_pass = bool(
        stage079_goal_pass
        and stage079_resample_pass
        and stage079_year_ablation_pass
        and stage079_topday_pass
        and stage079_edge_psr_pass
    )

    if stage079_anti_overfit_pass and strict_stage103_replace_pass:
        decision_value = "confirm_replacement_candidate"
        promotion_judgement = "Stage136 best1_vt 可作为 Stage103 替代候选进入工程化和影子盘。"
    elif stage079_anti_overfit_pass:
        decision_value = "confirm_stage079_promotion_keep_parallel_with_stage103"
        promotion_judgement = "Stage136 best1_vt 通过 Stage079 目标和反过拟合审计，晋级为主研究/工程候选；但不替代 Stage103，只能并行观察。"
    elif stage079_goal_pass:
        decision_value = "paper_candidate_only_overfit_warning"
        promotion_judgement = "Stage136 best1_vt 通过原始目标，但反过拟合审计有缺口，只保留 paper。"
    else:
        decision_value = "downgrade_reject_stage136"
        promotion_judgement = "Stage136 best1_vt 不再保留为晋级候选。"

    return {
        "stage": "Stage137",
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "candidate_variant": CANDIDATE_VARIANT,
        "decision": decision_value,
        "promotion_judgement": promotion_judgement,
        "gates": {
            "stage079_goal_pass": stage079_goal_pass,
            "stage079_resample_pass": stage079_resample_pass,
            "stage079_year_ablation_pass": stage079_year_ablation_pass,
            "stage079_topday_pass": stage079_topday_pass,
            "stage079_edge_psr_pass": stage079_edge_psr_pass,
            "stage079_anti_overfit_pass": stage079_anti_overfit_pass,
            "strict_stage103_rolling_return_pass": strict_stage103_rolling_return_pass,
            "strict_stage103_resample_return_pass": strict_stage103_resample_return_pass,
            "strict_stage103_topday_pass": strict_stage103_topday_pass,
            "strict_stage103_replace_pass": strict_stage103_replace_pass,
        },
        "stage079_total_return_pct": float(base["total_return_pct"]),
        "stage079_max_dd_pct": float(base["max_dd_pct"]),
        "stage103_total_return_pct": float(stage103["total_return_pct"]),
        "stage103_max_dd_pct": float(stage103["max_dd_pct"]),
        "candidate_total_return_pct": float(cand["total_return_pct"]),
        "candidate_max_dd_pct": float(cand["max_dd_pct"]),
        "candidate_sharpe": float(cand["sharpe"]),
        "candidate_ulcer_pct": float(cand["ulcer_pct"]),
        "candidate_score_90d": float(cand["score_90d"]),
        "candidate_score_180d": float(cand["score_180d"]),
        "chart": str(CHART_PATH),
        "report": str(REPORT_PATH),
    }


def _plot(
    rolling: pd.DataFrame,
    pairwise: pd.DataFrame,
    resample: pd.DataFrame,
    year_ablation: pd.DataFrame,
    topday: pd.DataFrame,
    psr: pd.DataFrame,
) -> None:
    plt.rcParams["font.sans-serif"] = ["Arial Unicode MS", "SimHei", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    fig, axes = plt.subplots(2, 3, figsize=(18, 10))

    focus = rolling[rolling["window_days"].isin([63, 90, 126, 180, 252, 504])]
    x_labels = [str(x) for x in sorted(focus["window_days"].unique())]
    x = np.arange(len(x_labels))
    width = 0.24
    offsets = {BASELINE_VARIANT: -width, STAGE103_VARIANT: 0.0, CANDIDATE_VARIANT: width}
    for variant in VARIANT_ORDER:
        view = focus[focus["variant"].eq(variant)].set_index("window_days").loc[[int(v) for v in x_labels]]
        axes[0, 0].bar(x + offsets[variant], view["return_p05_pct"], width=width, label=LABELS[variant])
    axes[0, 0].axhline(0, color="#555555", linewidth=0.8)
    axes[0, 0].set_xticks(x, x_labels)
    axes[0, 0].set_title("任意启动：5%分位收益")
    axes[0, 0].set_ylabel("%")
    axes[0, 0].legend(fontsize=8)

    for variant in VARIANT_ORDER:
        view = focus[focus["variant"].eq(variant)].set_index("window_days").loc[[int(v) for v in x_labels]]
        axes[0, 1].plot(x, view["dd20_breach_rate"] * 100.0, marker="o", label=LABELS[variant])
    axes[0, 1].set_xticks(x, x_labels)
    axes[0, 1].set_title("任意启动：破20%回撤率")
    axes[0, 1].set_ylabel("%")
    axes[0, 1].legend(fontsize=8)

    pw = pairwise[pairwise["window_days"].isin([90, 180, 252, 504])]
    for comparator in COMPARATORS:
        view = pw[pw["comparator_variant"].eq(comparator)]
        axes[0, 2].plot(view["window_days"], view["return_win_rate"] * 100.0, marker="o", label=f"收益胜率 vs {LABELS[comparator]}")
        axes[0, 2].plot(view["window_days"], view["ulcer_not_worse_rate"] * 100.0, marker="x", linestyle="--", label=f"Ulcer不劣化 vs {LABELS[comparator]}")
    axes[0, 2].axhline(50, color="#555555", linewidth=0.8)
    axes[0, 2].set_title("滚动窗口相对胜率")
    axes[0, 2].set_ylabel("%")
    axes[0, 2].legend(fontsize=7)

    res = resample[resample["comparator_variant"].eq(BASELINE_VARIANT)]
    labels = [f"B{int(r.block_len_days)}" if pd.notna(r.block_len_days) else "月重排" for r in res.itertuples(index=False)]
    rx = np.arange(len(labels))
    axes[1, 0].bar(rx - width, res["return_win_rate"] * 100.0, width=width, label="收益胜率")
    axes[1, 0].bar(rx, res["maxdd_not_worse_rate"] * 100.0, width=width, label="回撤不劣化")
    axes[1, 0].bar(rx + width, res["ulcer_not_worse_rate"] * 100.0, width=width, label="Ulcer不劣化")
    axes[1, 0].set_xticks(rx, labels)
    axes[1, 0].set_ylim(0, 105)
    axes[1, 0].set_title("路径扰动 vs Stage079")
    axes[1, 0].legend(fontsize=8)

    ya = year_ablation[year_ablation["comparator_variant"].eq(BASELINE_VARIANT)]
    axes[1, 1].bar(ya["removed_year"].astype(str), ya["return_delta_pp"], label="收益差")
    axes[1, 1].plot(ya["removed_year"].astype(str), ya["maxdd_delta_pp"], color="#c0392b", marker="o", label="最大回撤差")
    axes[1, 1].plot(ya["removed_year"].astype(str), ya["ulcer_delta_pp"], color="#2c7fb8", marker="o", label="Ulcer差")
    axes[1, 1].axhline(0, color="#555555", linewidth=0.8)
    axes[1, 1].set_title("剔除单一年份 vs Stage079")
    axes[1, 1].legend(fontsize=8)

    td = topday[topday["comparator_variant"].eq(BASELINE_VARIANT)]
    axes[1, 2].plot(td["removed_top_positive_edge_days"], td["adjusted_return_delta_pp"], marker="o", label="收益差")
    axes[1, 2].plot(td["removed_top_positive_edge_days"], td["adjusted_maxdd_delta_pp"], marker="o", label="最大回撤差")
    axes[1, 2].plot(td["removed_top_positive_edge_days"], td["adjusted_ulcer_delta_pp"], marker="o", label="Ulcer差")
    p = psr[psr["comparator_variant"].eq(BASELINE_VARIANT)]["psr_gt_benchmark"].iloc[0]
    axes[1, 2].set_title(f"剔除相对Stage079正贡献日 PSR={p:.2%}")
    axes[1, 2].axhline(0, color="#555555", linewidth=0.8)
    axes[1, 2].legend(fontsize=8)

    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=160)
    plt.close(fig)


def _write_report(
    summary: pd.DataFrame,
    rolling: pd.DataFrame,
    pairwise: pd.DataFrame,
    resample: pd.DataFrame,
    year: pd.DataFrame,
    year_ablation: pd.DataFrame,
    topday: pd.DataFrame,
    psr: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    summary_cols = [
        "variant",
        "label",
        "total_return_pct",
        "max_dd_pct",
        "sharpe",
        "ulcer_pct",
        "score_90d",
        "score_180d",
        "short_holding_score",
        "fresh_start_worst_max_dd_pct",
        "broker10_reject_days_total",
        "broker10_required_extra_cash_max",
        "deployment_absolute_margin_pass",
    ]
    rolling_view = rolling[rolling["window_days"].isin([63, 90, 126, 180, 252, 504])][
        [
            "variant",
            "window_days",
            "return_p05_pct",
            "return_median_pct",
            "positive_return_rate",
            "annualized_below_5pct_rate",
            "dd20_breach_rate",
            "dd30_breach_rate",
            "ulcer_p95_pct",
            "longest_underwater_p95_days",
        ]
    ]
    pairwise_view = pairwise[pairwise["window_days"].isin([63, 90, 126, 180, 252, 504])][
        [
            "comparator_variant",
            "window_days",
            "return_win_rate",
            "return_delta_median_pp",
            "return_delta_p05_pp",
            "maxdd_not_worse_rate",
            "ulcer_not_worse_rate",
            "all3_win_rate",
        ]
    ]
    resample_view = resample[
        [
            "method",
            "block_len_days",
            "comparator_variant",
            "sims",
            "return_win_rate",
            "return_delta_median_pp",
            "return_delta_p05_pp",
            "maxdd_not_worse_rate",
            "ulcer_not_worse_rate",
            "all3_win_rate",
        ]
    ]
    topday_view = topday[
        [
            "comparator_variant",
            "removed_top_positive_edge_days",
            "removed_edge_return_sum_pp",
            "candidate_adjusted_total_return_pct",
            "candidate_adjusted_max_dd_pct",
            "candidate_adjusted_ulcer_pct",
            "adjusted_return_delta_pp",
            "adjusted_maxdd_delta_pp",
            "adjusted_ulcer_delta_pp",
        ]
    ]
    report = f"""# Stage137 Stage136 best1_vt 严格鲁棒性与反过拟合审计

## 结论

- 决策：`{decision["decision"]}`。
- 晋级判断：{decision["promotion_judgement"]}
- 本阶段不新增交易规则，不修改 Stage079、Stage103 或 Stage136 参数，只审计固定候选。

## 外部方法参考

- 商品偏度方向参考 Fernandez-Perez / Frijns / Fuertes / Miffre 的 commodity skewness anomaly：低偏度商品 futures 组合有可解释收益来源。
- 反过拟合框架参考 PBO / Deflated Sharpe / PSR / block bootstrap 思路：不能只看单一路径最高收益，必须看路径扰动、贡献集中度、年份剔除和 rolling holding。
- 本阶段的核心判断是分层的：先判定是否通过 Stage079 目标，再判定是否足以替代 Stage103。

## 固定路径核心结果

{_md_table(summary[summary_cols])}

## 任意启动持有体验

{_md_table(rolling_view)}

## 相对 Stage079 / Stage103 的滚动胜率

{_md_table(pairwise_view)}

## Block Bootstrap 与月份重排

{_md_table(resample_view)}

## 年度贡献

{_md_table(year)}

## 剔除单一年份后

{_md_table(year_ablation)}

## 剔除最大相对正贡献日

{_md_table(topday_view)}

## PSR 边际收益检验

{_md_table(psr)}

## 闸门

```json
{json.dumps(_json_safe(decision["gates"]), ensure_ascii=False, indent=2)}
```

## 图表

![Stage137鲁棒性图表]({CHART_PATH})
"""
    REPORT_PATH.write_text(report, encoding="utf-8")


def main() -> None:
    daily = _read_csv(DAILY_IN)
    source_summary = _read_csv(SUMMARY_IN)
    _ = _read_csv(HORIZON_IN)
    source_score = _read_csv(SCORE_IN)
    source_fresh = _read_csv(FRESH_IN)
    source_cost = _read_csv(COST_IN)
    source_margin = _read_csv(MARGIN_IN)
    source_gate = _read_csv(GATE_IN)

    equity, returns = _build_return_frame(daily)
    rolling, pairwise = _rolling_holding_metrics(equity)
    bootstrap = _block_bootstrap(returns)
    month_perm = _month_permutation(returns)
    resample = pd.concat([bootstrap, month_perm], ignore_index=True)
    year, year_ablation = _year_contribution_and_ablation(returns)
    topday = _top_edge_day_ablation(returns)
    psr = _edge_psr(returns)
    summary = _summary_from_sources(source_summary, source_score, source_cost, source_fresh, source_margin, source_gate)
    decision = _make_decision(summary, pairwise, resample, year_ablation, topday, psr)

    _plot(rolling, pairwise, resample, year_ablation, topday, psr)
    _write_report(summary, rolling, pairwise, resample, year, year_ablation, topday, psr, decision)

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    rolling.to_csv(ROLLING_PATH, index=False, encoding="utf-8-sig")
    pairwise.to_csv(PAIRWISE_PATH, index=False, encoding="utf-8-sig")
    bootstrap.to_csv(BOOTSTRAP_PATH, index=False, encoding="utf-8-sig")
    month_perm.to_csv(MONTH_PERMUTATION_PATH, index=False, encoding="utf-8-sig")
    year.to_csv(YEAR_PATH, index=False, encoding="utf-8-sig")
    year_ablation.to_csv(YEAR_ABLATION_PATH, index=False, encoding="utf-8-sig")
    topday.to_csv(TOPDAY_PATH, index=False, encoding="utf-8-sig")
    psr.to_csv(PSR_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print(f"report={REPORT_PATH}")


if __name__ == "__main__":
    main()
