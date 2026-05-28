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

MODEL_TAG = "stage416_stage115_robustness_overfit_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage416_stage115_robustness_overfit_audit"
LINE_ID = "futures_trend_drawdown30_preserve_return"

ACCOUNT_CAPITAL = 615_000.0
BASELINE_VARIANT = "stage079"
STAGE103_VARIANT = "xsmom_vt10_q_momq_round_half_true_broker10_guard"
STAGE115_VARIANT = "stage103_plus_cffex_index_best1_tsmom60_guard"
VARIANT_ORDER = [BASELINE_VARIANT, STAGE103_VARIANT, STAGE115_VARIANT]
COMPARATORS = [BASELINE_VARIANT, STAGE103_VARIANT]

STAGE115_PREFIX = "qmt_roll_stage415_stage103_cffex_index_true_overlay"
STAGE115_TAG = "stage415_stage103_cffex_index_true_overlay_v2"

DAILY_SOURCE_PATH = OUTPUT_DIR / f"{STAGE115_PREFIX}_daily_{STAGE115_TAG}.csv"
SUMMARY_SOURCE_PATH = OUTPUT_DIR / f"{STAGE115_PREFIX}_summary_{STAGE115_TAG}.csv"
HORIZON_SOURCE_PATH = OUTPUT_DIR / f"{STAGE115_PREFIX}_horizon_{STAGE115_TAG}.csv"
SCORE_SOURCE_PATH = OUTPUT_DIR / f"{STAGE115_PREFIX}_score_{STAGE115_TAG}.csv"
FRESH_START_SOURCE_PATH = OUTPUT_DIR / f"{STAGE115_PREFIX}_fresh_start_{STAGE115_TAG}.csv"
COST_SOURCE_PATH = OUTPUT_DIR / f"{STAGE115_PREFIX}_cost_stress_{STAGE115_TAG}.csv"
MARGIN_SOURCE_PATH = OUTPUT_DIR / f"{STAGE115_PREFIX}_margin_audit_{STAGE115_TAG}.csv"
GATE_SOURCE_PATH = OUTPUT_DIR / f"{STAGE115_PREFIX}_gate_{STAGE115_TAG}.csv"

ROLLING_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_rolling_holding_{MODEL_TAG}.csv"
PAIRWISE_ROLLING_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_pairwise_rolling_{MODEL_TAG}.csv"
BOOTSTRAP_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_block_bootstrap_{MODEL_TAG}.csv"
MONTH_PERMUTATION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_month_permutation_{MODEL_TAG}.csv"
TOPDAY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_top_edge_day_ablation_{MODEL_TAG}.csv"
SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

LABELS = {
    BASELINE_VARIANT: "Stage079基准",
    STAGE103_VARIANT: "Stage103 broker10_guard",
    STAGE115_VARIANT: "Stage115 best1_tsmom60",
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


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(result) or math.isinf(result):
        return default
    return result


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    frame = pd.read_csv(path, encoding="utf-8-sig")
    if "date" in frame.columns:
        frame["date"] = pd.to_datetime(frame["date"])
    return frame


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
    returns = pivot.pct_change()
    returns.iloc[0] = pivot.iloc[0] / ACCOUNT_CAPITAL - 1.0
    return pivot, returns


def _rolling_holding_metrics(returns: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    windows = [21, 63, 90, 126, 180, 252, 504]
    rolling_rows: list[dict[str, Any]] = []
    segment_cache: dict[tuple[str, int], pd.DataFrame] = {}

    for variant in VARIANT_ORDER:
        series = returns[variant].to_numpy(dtype=float)
        for window in windows:
            rows: list[dict[str, Any]] = []
            for start in range(0, len(series) - window + 1):
                segment = series[start : start + window]
                nav = _nav_from_returns(segment, include_initial=True)
                total_return = nav[-1] / ACCOUNT_CAPITAL - 1.0
                annualized = (1.0 + total_return) ** (252.0 / window) - 1.0 if total_return > -1.0 else -1.0
                rows.append(
                    {
                        "start_date": returns.index[start],
                        "end_date": returns.index[start + window - 1],
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
                    "positive_return_rate": float((frame["return_pct"] > 0).mean()),
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
        cand = segment_cache[(STAGE115_VARIANT, window)]
        for comparator in COMPARATORS:
            comp = segment_cache[(comparator, window)]
            pairwise_rows.append(
                {
                    "candidate_variant": STAGE115_VARIANT,
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
            "candidate_variant": STAGE115_VARIANT,
            "comparator_variant": comparator,
            "sims": len(frame),
        }
        for variant in [comparator, STAGE115_VARIANT]:
            row[f"{variant}_return_median_pct"] = float(frame[f"{variant}_return_pct"].median())
            row[f"{variant}_return_p05_pct"] = float(frame[f"{variant}_return_pct"].quantile(0.05))
            row[f"{variant}_maxdd_median_pct"] = float(frame[f"{variant}_maxdd_pct"].median())
            row[f"{variant}_maxdd_p05_pct"] = float(frame[f"{variant}_maxdd_pct"].quantile(0.05))
            row[f"{variant}_ulcer_median_pct"] = float(frame[f"{variant}_ulcer_pct"].median())
            row[f"{variant}_dd30_breach_rate"] = float((frame[f"{variant}_maxdd_pct"] < -30.0).mean())
        row["return_win_rate"] = float(
            (frame[f"{STAGE115_VARIANT}_return_pct"] > frame[f"{comparator}_return_pct"]).mean()
        )
        row["maxdd_not_worse_rate"] = float(
            (frame[f"{STAGE115_VARIANT}_maxdd_pct"] >= frame[f"{comparator}_maxdd_pct"]).mean()
        )
        row["ulcer_not_worse_rate"] = float(
            (frame[f"{STAGE115_VARIANT}_ulcer_pct"] <= frame[f"{comparator}_ulcer_pct"]).mean()
        )
        row["all3_win_rate"] = float(
            (
                (frame[f"{STAGE115_VARIANT}_return_pct"] > frame[f"{comparator}_return_pct"])
                & (frame[f"{STAGE115_VARIANT}_maxdd_pct"] >= frame[f"{comparator}_maxdd_pct"])
                & (frame[f"{STAGE115_VARIANT}_ulcer_pct"] <= frame[f"{comparator}_ulcer_pct"])
            ).mean()
        )
        row["return_delta_median_pp"] = float(
            (frame[f"{STAGE115_VARIANT}_return_pct"] - frame[f"{comparator}_return_pct"]).median()
        )
        row["maxdd_delta_median_pp"] = float(
            (frame[f"{STAGE115_VARIANT}_maxdd_pct"] - frame[f"{comparator}_maxdd_pct"]).median()
        )
        row["ulcer_delta_median_pp"] = float(
            (frame[f"{STAGE115_VARIANT}_ulcer_pct"] - frame[f"{comparator}_ulcer_pct"]).median()
        )
        rows.append(row)
    return rows


def _block_bootstrap(returns: pd.DataFrame, sims: int = 2000) -> pd.DataFrame:
    rng = np.random.default_rng(416115)
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


def _month_permutation(returns: pd.DataFrame, sims: int = 2000) -> pd.DataFrame:
    rng = np.random.default_rng(416215)
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
        edge = returns[STAGE115_VARIANT] - returns[comparator]
        positive_edge = edge[edge > 0].sort_values(ascending=False)
        comp_metrics = _metrics_from_returns(returns[comparator].to_numpy(dtype=float))
        for top_n in [0, 1, 3, 5, 10, 20, 40, 80, 120]:
            adjusted = returns[STAGE115_VARIANT].copy()
            removed_edge_return_sum_pp = 0.0
            if top_n > 0:
                remove_dates = positive_edge.head(top_n).index
                removed_edge_return_sum_pp = float(positive_edge.head(top_n).sum() * 100.0)
                adjusted.loc[remove_dates] = returns.loc[remove_dates, comparator]
            metrics = _metrics_from_returns(adjusted.to_numpy(dtype=float))
            rows.append(
                {
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
            overlay_gate_skipped_days_total=("overlay_gate_skipped_days", "sum"),
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
    gate = (
        source_gate[source_gate["variant"].isin(VARIANT_ORDER)]
        .set_index("variant")[
            [
                "metric_hard_pass_stage079",
                "metric_incremental_pass_stage103",
                "target_pass_3m6m_vs_stage079",
                "execution_relative_pass",
                "deployment_absolute_margin_pass",
                "failed_stage079_metric_checks",
                "failed_stage103_incremental_checks",
            ]
        ]
    )
    merged = summary.set_index("variant").join(score).join(cost).join(fresh).join(broker10).join(gate).reset_index()
    merged["label"] = merged["variant"].map(LABELS).fillna(merged["label"])
    return merged


def _make_chart(rolling: pd.DataFrame, pairwise: pd.DataFrame, resample: pd.DataFrame, topday: pd.DataFrame) -> None:
    plt.rcParams["font.sans-serif"] = ["Arial Unicode MS", "SimHei", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    fig, axes = plt.subplots(2, 2, figsize=(15, 9))

    focus = rolling[rolling["window_days"].isin([63, 90, 126, 180, 252, 504])]
    x_labels = [str(x) for x in sorted(focus["window_days"].unique())]
    x = np.arange(len(x_labels))
    width = 0.24
    offsets = {BASELINE_VARIANT: -width, STAGE103_VARIANT: 0.0, STAGE115_VARIANT: width}
    for variant in VARIANT_ORDER:
        view = focus[focus["variant"].eq(variant)].set_index("window_days").loc[[int(v) for v in x_labels]]
        axes[0, 0].bar(x + offsets[variant], view["return_p05_pct"], width=width, label=LABELS[variant])
    axes[0, 0].axhline(0, color="#666666", linewidth=0.8)
    axes[0, 0].set_xticks(x, x_labels)
    axes[0, 0].set_title("任意启动持有期：5%分位收益")
    axes[0, 0].set_ylabel("%")
    axes[0, 0].legend(fontsize=8)

    for variant in VARIANT_ORDER:
        view = focus[focus["variant"].eq(variant)].set_index("window_days").loc[[int(v) for v in x_labels]]
        axes[0, 1].plot(x, view["dd20_breach_rate"] * 100.0, marker="o", label=LABELS[variant])
    axes[0, 1].set_xticks(x, x_labels)
    axes[0, 1].set_title("任意启动持有期：窗口内破20%回撤率")
    axes[0, 1].set_ylabel("%")
    axes[0, 1].legend(fontsize=8)

    view = resample[resample["comparator_variant"].eq(STAGE103_VARIANT)].copy()
    labels = [f"B{int(row.block_len_days)}" if pd.notna(row.block_len_days) else "月重排" for row in view.itertuples(index=False)]
    rx = np.arange(len(labels))
    axes[1, 0].bar(rx - width / 2, view["return_win_rate"] * 100.0, width=width, label="vs Stage103收益胜率")
    axes[1, 0].bar(rx + width / 2, view["ulcer_not_worse_rate"] * 100.0, width=width, label="vs Stage103 Ulcer不劣化")
    axes[1, 0].axhline(50, color="#666666", linewidth=0.8)
    axes[1, 0].set_xticks(rx, labels)
    axes[1, 0].set_ylim(0, 105)
    axes[1, 0].set_title("路径扰动后 Stage115 相对 Stage103")
    axes[1, 0].set_ylabel("%")
    axes[1, 0].legend(fontsize=8)

    td = topday[topday["comparator_variant"].eq(STAGE103_VARIANT)]
    axes[1, 1].plot(td["removed_top_positive_edge_days"], td["adjusted_return_delta_pp"], marker="o", label="收益差")
    axes[1, 1].plot(td["removed_top_positive_edge_days"], td["adjusted_maxdd_delta_pp"], marker="o", label="最大回撤差")
    axes[1, 1].plot(td["removed_top_positive_edge_days"], td["adjusted_ulcer_delta_pp"], marker="o", label="Ulcer差")
    axes[1, 1].axhline(0, color="#666666", linewidth=0.8)
    axes[1, 1].set_title("剔除Stage115相对Stage103最强贡献日")
    axes[1, 1].set_xlabel("剔除天数")
    axes[1, 1].set_ylabel("百分点")
    axes[1, 1].legend(fontsize=8)

    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=160)
    plt.close(fig)


def _make_report(
    summary: pd.DataFrame,
    rolling: pd.DataFrame,
    pairwise: pd.DataFrame,
    resample: pd.DataFrame,
    topday: pd.DataFrame,
    decision: dict[str, Any],
) -> str:
    key_summary_cols = [
        "variant",
        "label",
        "total_return_pct",
        "max_dd_pct",
        "sharpe",
        "ulcer_pct",
        "score_90d",
        "score_180d",
        "cost_2x_max_dd_pct",
        "cost_3x_max_dd_pct",
        "cost_5x_max_dd_pct",
        "fresh_start_worst_max_dd_pct",
        "broker10_reject_days_total",
        "broker10_required_extra_cash_max",
        "execution_relative_pass",
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
            "max_dd_worst_pct",
            "dd20_breach_rate",
            "dd30_breach_rate",
            "ulcer_p95_pct",
            "longest_underwater_p95_days",
        ]
    ]
    pairwise_view = pairwise[
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
            "maxdd_not_worse_rate",
            "ulcer_not_worse_rate",
            "all3_win_rate",
            "return_delta_median_pp",
            "maxdd_delta_median_pp",
            "ulcer_delta_median_pp",
            f"{STAGE115_VARIANT}_dd30_breach_rate",
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

    return f"""# Stage116 Stage115鲁棒性与反过拟合审计

## 结论

- 决策：`{decision["decision"]}`。
- 晋级判断：`{decision["promotion_judgement"]}`。
- 核心理由：{decision["reason"]}
- 本阶段不新增交易规则，不改 Stage079/Stage103/Stage115 参数，只做路径和统计扰动审计。

## 外部方法参考

- Bailey、Borwein、Lopez de Prado、Zhu 的 backtest overfitting 研究提示：多次试验后，单一漂亮回测可能来自选择偏差，因此要看多路径和扰动后的表现。
- walk-forward/rolling holding 分析用于回答“任何时候启动、持有多久”的体验问题。
- block bootstrap 与月份顺序重排用于检查是否依赖唯一历史路径。
- 时间序列动量文献支持跨资产 futures 的趋势效应，但不能代替本地保证金、合约粒度和滑点审计。

## 固定路径核心结果

{_md_table(summary[key_summary_cols])}

## 任意启动持有期

{_md_table(rolling_view)}

## Stage115 相对 Stage079 / Stage103 的任意窗口胜率

{_md_table(pairwise_view)}

## 路径扰动

{_md_table(resample_view)}

## 极端相对贡献日剔除

{_md_table(topday_view)}

## 图表

![Stage116鲁棒性图表]({CHART_PATH})

## 解释

- `execution-relative`：相对 Stage079 / Stage103 的历史路径和压力测试更好或不差，但不代表真实券商保证金绝对无穿线。
- `absolute deployment`：需要所有资金、保证金、滑点和执行口径都可直接落地；Stage115 目前还差真实券商保证金确认。
- 若下一阶段真实券商保证金仍出现穿线，不能用调保证金小数或加现金救；只能降级为 paper 或重做资金结构。
"""


def main() -> None:
    daily = _read_csv(DAILY_SOURCE_PATH)
    source_summary = _read_csv(SUMMARY_SOURCE_PATH)
    _ = _read_csv(HORIZON_SOURCE_PATH)
    source_score = _read_csv(SCORE_SOURCE_PATH)
    source_fresh = _read_csv(FRESH_START_SOURCE_PATH)
    source_cost = _read_csv(COST_SOURCE_PATH)
    source_margin = _read_csv(MARGIN_SOURCE_PATH)
    source_gate = _read_csv(GATE_SOURCE_PATH)

    _, returns = _build_return_frame(daily)
    rolling, pairwise = _rolling_holding_metrics(returns)
    bootstrap = _block_bootstrap(returns, sims=2000)
    month_perm = _month_permutation(returns, sims=2000)
    resample = pd.concat([bootstrap, month_perm], ignore_index=True)
    topday = _top_edge_day_ablation(returns)
    summary = _summary_from_sources(source_summary, source_score, source_cost, source_fresh, source_margin, source_gate)

    summary_by_variant = summary.set_index("variant")
    base = summary_by_variant.loc[BASELINE_VARIANT]
    stage103 = summary_by_variant.loc[STAGE103_VARIANT]
    cand = summary_by_variant.loc[STAGE115_VARIANT]

    hard_vs_stage079 = bool(
        cand["total_return_pct"] >= base["total_return_pct"]
        and cand["max_dd_pct"] >= base["max_dd_pct"]
        and cand["max_dd_pct"] >= -30.0
        and cand["sharpe"] >= base["sharpe"]
        and cand["ulcer_pct"] <= base["ulcer_pct"]
        and cand["execution_relative_pass"] == 1
    )
    incremental_vs_stage103 = bool(
        cand["total_return_pct"] >= stage103["total_return_pct"]
        and cand["max_dd_pct"] >= stage103["max_dd_pct"]
        and cand["sharpe"] >= stage103["sharpe"]
        and cand["ulcer_pct"] <= stage103["ulcer_pct"]
    )
    cost_not_worse = bool(
        cand["cost_2x_max_dd_pct"] >= base["cost_2x_max_dd_pct"]
        and cand["cost_3x_max_dd_pct"] >= base["cost_3x_max_dd_pct"]
        and cand["cost_5x_max_dd_pct"] >= base["cost_5x_max_dd_pct"]
        and cand["cost_2x_max_dd_pct"] >= stage103["cost_2x_max_dd_pct"]
        and cand["cost_3x_max_dd_pct"] >= stage103["cost_3x_max_dd_pct"]
        and cand["cost_5x_max_dd_pct"] >= stage103["cost_5x_max_dd_pct"]
    )
    short_score_pass = bool(cand["score_90d"] >= 110.0 and cand["score_180d"] >= 110.0)
    rolling_vs_stage103 = pairwise[pairwise["comparator_variant"].eq(STAGE103_VARIANT)]
    rolling_risk_strong = bool(
        rolling_vs_stage103[rolling_vs_stage103["window_days"].isin([90, 180, 252, 504])][
            "maxdd_not_worse_rate"
        ].min()
        >= 0.85
        and rolling_vs_stage103[rolling_vs_stage103["window_days"].isin([90, 180, 252, 504])][
            "ulcer_not_worse_rate"
        ].min()
        >= 0.90
    )
    rolling_return_strong = bool(
        rolling_vs_stage103[rolling_vs_stage103["window_days"].isin([63, 90, 126, 180])]["return_win_rate"].min()
        >= 0.55
    )
    resample_vs_stage103 = resample[resample["comparator_variant"].eq(STAGE103_VARIANT)]
    resample_risk_strong = bool(
        resample_vs_stage103["maxdd_not_worse_rate"].min() >= 0.75
        and resample_vs_stage103["ulcer_not_worse_rate"].min() >= 0.85
    )
    resample_return_strong = bool(resample_vs_stage103["return_win_rate"].min() >= 0.55)
    topday_vs_stage103 = topday[topday["comparator_variant"].eq(STAGE103_VARIANT)]
    topday_not_single_spike = bool(
        topday_vs_stage103[topday_vs_stage103["removed_top_positive_edge_days"].eq(20)][
            "adjusted_return_delta_pp"
        ].iloc[0]
        > 0
        and topday_vs_stage103[topday_vs_stage103["removed_top_positive_edge_days"].eq(20)][
            "adjusted_ulcer_delta_pp"
        ].iloc[0]
        <= 0
    )
    absolute_margin_pass = bool(cand["deployment_absolute_margin_pass"] == 1)

    robust_promotion = (
        hard_vs_stage079
        and incremental_vs_stage103
        and cost_not_worse
        and short_score_pass
        and rolling_risk_strong
        and rolling_return_strong
        and resample_risk_strong
        and resample_return_strong
        and topday_not_single_spike
    )
    if robust_promotion and absolute_margin_pass:
        decision_value = "robust_absolute_deployment_candidate"
        promotion_judgement = "可晋级为绝对部署候选。"
        reason = "硬指标、短持有体验、任意窗口、路径扰动、贡献日剔除和绝对保证金均通过。"
    elif robust_promotion:
        decision_value = "robust_execution_relative_candidate_requires_margin_work"
        promotion_judgement = "保留为新的主执行相对候选，并进入工程化复跑 / paper影子盘；但真实部署前必须解决保证金绝对穿线。"
        reason = "硬指标、短持有体验、任意窗口、路径扰动和贡献日剔除均支持 Stage115；唯一硬边界是 Stage115 仍非 absolute deployment。"
    else:
        decision_value = "robustness_gap_do_not_promote_further"
        promotion_judgement = "不建议进一步晋级，保留为研究候选或回到 Stage103。"
        reason = "至少一个硬指标、任意窗口、路径扰动或贡献日剔除闸门未通过。"

    decision = {
        "stage": "Stage116",
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "decision": decision_value,
        "promotion_judgement": promotion_judgement,
        "reason": reason,
        "gates": {
            "hard_vs_stage079": hard_vs_stage079,
            "incremental_vs_stage103": incremental_vs_stage103,
            "cost_not_worse": cost_not_worse,
            "short_score_pass": short_score_pass,
            "rolling_risk_strong": rolling_risk_strong,
            "rolling_return_strong": rolling_return_strong,
            "resample_risk_strong": resample_risk_strong,
            "resample_return_strong": resample_return_strong,
            "topday_not_single_spike": topday_not_single_spike,
            "absolute_margin_pass": absolute_margin_pass,
        },
        "stage079_total_return_pct": _safe_float(base["total_return_pct"]),
        "stage079_max_dd_pct": _safe_float(base["max_dd_pct"]),
        "stage103_total_return_pct": _safe_float(stage103["total_return_pct"]),
        "stage103_max_dd_pct": _safe_float(stage103["max_dd_pct"]),
        "stage115_total_return_pct": _safe_float(cand["total_return_pct"]),
        "stage115_max_dd_pct": _safe_float(cand["max_dd_pct"]),
        "stage115_sharpe": _safe_float(cand["sharpe"]),
        "stage115_ulcer_pct": _safe_float(cand["ulcer_pct"]),
        "stage115_score_90d": _safe_float(cand["score_90d"]),
        "stage115_score_180d": _safe_float(cand["score_180d"]),
        "stage115_broker10_reject_days_total": _safe_float(cand["broker10_reject_days_total"]),
        "stage115_required_extra_cash_max": _safe_float(cand["broker10_required_extra_cash_max"]),
        "rolling_pairwise": pairwise.to_dict(orient="records"),
        "resample": resample.to_dict(orient="records"),
        "topday_removed20_vs_stage103": topday_vs_stage103[
            topday_vs_stage103["removed_top_positive_edge_days"].eq(20)
        ].iloc[0].to_dict(),
        "source_files": {
            "daily": str(DAILY_SOURCE_PATH),
            "summary": str(SUMMARY_SOURCE_PATH),
            "score": str(SCORE_SOURCE_PATH),
            "fresh_start": str(FRESH_START_SOURCE_PATH),
            "cost": str(COST_SOURCE_PATH),
            "margin": str(MARGIN_SOURCE_PATH),
            "gate": str(GATE_SOURCE_PATH),
        },
    }

    _make_chart(rolling, pairwise, resample, topday)
    report = _make_report(summary, rolling, pairwise, resample, topday, decision)

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    rolling.to_csv(ROLLING_PATH, index=False, encoding="utf-8-sig")
    pairwise.to_csv(PAIRWISE_ROLLING_PATH, index=False, encoding="utf-8-sig")
    bootstrap.to_csv(BOOTSTRAP_PATH, index=False, encoding="utf-8-sig")
    month_perm.to_csv(MONTH_PERMUTATION_PATH, index=False, encoding="utf-8-sig")
    topday.to_csv(TOPDAY_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_PATH.write_text(report, encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
