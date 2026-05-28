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

MODEL_TAG = "stage409_stage103_robustness_overfit_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage409_stage103_robustness_overfit_audit"
LINE_ID = "futures_trend_drawdown30_preserve_return"

ACCOUNT_CAPITAL = 615_000.0
BASELINE_VARIANT = "stage079"
STAGE103_VARIANT = "xsmom_vt10_q_momq_round_half_true_broker10_guard"
VARIANT_ORDER = [BASELINE_VARIANT, STAGE103_VARIANT]

STAGE403_PREFIX = "qmt_roll_stage403_stage079_xsmom_execution_margin_audit"
STAGE403_TAG = "stage403_stage079_xsmom_execution_margin_audit_v1"

DAILY_SOURCE_PATH = OUTPUT_DIR / f"{STAGE403_PREFIX}_daily_{STAGE403_TAG}.csv"
SUMMARY_SOURCE_PATH = OUTPUT_DIR / f"{STAGE403_PREFIX}_summary_{STAGE403_TAG}.csv"
HORIZON_SOURCE_PATH = OUTPUT_DIR / f"{STAGE403_PREFIX}_horizon_{STAGE403_TAG}.csv"
SCORE_SOURCE_PATH = OUTPUT_DIR / f"{STAGE403_PREFIX}_score_{STAGE403_TAG}.csv"
FRESH_START_SOURCE_PATH = OUTPUT_DIR / f"{STAGE403_PREFIX}_fresh_start_{STAGE403_TAG}.csv"
COST_SOURCE_PATH = OUTPUT_DIR / f"{STAGE403_PREFIX}_cost_stress_{STAGE403_TAG}.csv"
MARGIN_SOURCE_PATH = OUTPUT_DIR / f"{STAGE403_PREFIX}_margin_audit_{STAGE403_TAG}.csv"

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
    for is_underwater in underwater:
        if bool(is_underwater):
            current += 1
            best = max(best, current)
        else:
            current = 0
    return int(best)


def _nav_from_returns(returns: np.ndarray, include_initial: bool = True) -> np.ndarray:
    returns = np.asarray(returns, dtype=float)
    nav = ACCOUNT_CAPITAL * np.cumprod(1.0 + returns)
    if include_initial:
        return np.concatenate([[ACCOUNT_CAPITAL], nav])
    return nav


def _metrics_from_returns(returns: np.ndarray) -> dict[str, float]:
    returns = np.asarray(returns, dtype=float)
    nav = _nav_from_returns(returns, include_initial=True)
    std = float(np.std(returns, ddof=1)) if len(returns) > 1 else 0.0
    sharpe = float(np.mean(returns) / std * math.sqrt(252.0)) if std > 0 else 0.0
    return {
        "end_equity": float(nav[-1]),
        "total_return_pct": float((nav[-1] / ACCOUNT_CAPITAL - 1.0) * 100.0),
        "max_dd_pct": _max_drawdown_pct(nav),
        "sharpe": sharpe,
        "ulcer_pct": _ulcer_pct(nav),
        "longest_underwater_days": float(_longest_underwater_days(nav)),
    }


def _build_return_frame(daily: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    pivot = (
        daily[daily["variant"].isin(VARIANT_ORDER)]
        .pivot_table(index="date", columns="variant", values="equity", aggfunc="last")
        .sort_index()
    )
    pivot = pivot[VARIANT_ORDER].dropna()
    returns = pivot.pct_change()
    returns.iloc[0] = pivot.iloc[0] / ACCOUNT_CAPITAL - 1.0
    return pivot, returns


def _rolling_holding_metrics(returns: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    windows = [21, 63, 90, 126, 180, 252, 504]
    rolling_rows: list[dict[str, Any]] = []
    pairwise_rows: list[dict[str, Any]] = []

    segment_cache: dict[tuple[str, int], list[dict[str, Any]]] = {}
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
            segment_cache[(variant, window)] = rows
            frame = pd.DataFrame(rows)
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

    for window in windows:
        base = pd.DataFrame(segment_cache[(BASELINE_VARIANT, window)])
        cand = pd.DataFrame(segment_cache[(STAGE103_VARIANT, window)])
        pairwise_rows.append(
            {
                "window_days": window,
                "count": len(base),
                "stage103_return_win_rate": float((cand["return_pct"] > base["return_pct"]).mean()),
                "stage103_return_delta_median_pp": float((cand["return_pct"] - base["return_pct"]).median()),
                "stage103_return_delta_p05_pp": float((cand["return_pct"] - base["return_pct"]).quantile(0.05)),
                "stage103_maxdd_not_worse_rate": float((cand["max_dd_pct"] >= base["max_dd_pct"]).mean()),
                "stage103_ulcer_not_worse_rate": float((cand["ulcer_pct"] <= base["ulcer_pct"]).mean()),
                "stage103_longest_uw_not_worse_rate": float(
                    (cand["longest_underwater_days"] <= base["longest_underwater_days"]).mean()
                ),
                "stage103_all3_not_worse_rate": float(
                    (
                        (cand["return_pct"] > base["return_pct"])
                        & (cand["max_dd_pct"] >= base["max_dd_pct"])
                        & (cand["ulcer_pct"] <= base["ulcer_pct"])
                    ).mean()
                ),
            }
        )

    return pd.DataFrame(rolling_rows), pd.DataFrame(pairwise_rows)


def _pairwise_resample_summary(samples: list[dict[str, float]], method: str, block_len: int | None) -> dict[str, Any]:
    frame = pd.DataFrame(samples)
    result: dict[str, Any] = {
        "method": method,
        "block_len_days": block_len,
        "sims": len(frame),
    }
    for variant in VARIANT_ORDER:
        result[f"{variant}_return_median_pct"] = float(frame[f"{variant}_return_pct"].median())
        result[f"{variant}_return_p05_pct"] = float(frame[f"{variant}_return_pct"].quantile(0.05))
        result[f"{variant}_maxdd_median_pct"] = float(frame[f"{variant}_maxdd_pct"].median())
        result[f"{variant}_maxdd_p05_pct"] = float(frame[f"{variant}_maxdd_pct"].quantile(0.05))
        result[f"{variant}_ulcer_median_pct"] = float(frame[f"{variant}_ulcer_pct"].median())
        result[f"{variant}_dd30_breach_rate"] = float((frame[f"{variant}_maxdd_pct"] < -30.0).mean())
    result["stage103_return_win_rate"] = float(
        (frame[f"{STAGE103_VARIANT}_return_pct"] > frame[f"{BASELINE_VARIANT}_return_pct"]).mean()
    )
    result["stage103_maxdd_not_worse_rate"] = float(
        (frame[f"{STAGE103_VARIANT}_maxdd_pct"] >= frame[f"{BASELINE_VARIANT}_maxdd_pct"]).mean()
    )
    result["stage103_ulcer_not_worse_rate"] = float(
        (frame[f"{STAGE103_VARIANT}_ulcer_pct"] <= frame[f"{BASELINE_VARIANT}_ulcer_pct"]).mean()
    )
    result["stage103_all3_win_rate"] = float(
        (
            (frame[f"{STAGE103_VARIANT}_return_pct"] > frame[f"{BASELINE_VARIANT}_return_pct"])
            & (frame[f"{STAGE103_VARIANT}_maxdd_pct"] >= frame[f"{BASELINE_VARIANT}_maxdd_pct"])
            & (frame[f"{STAGE103_VARIANT}_ulcer_pct"] <= frame[f"{BASELINE_VARIANT}_ulcer_pct"])
        ).mean()
    )
    result["return_delta_median_pp"] = float(
        (frame[f"{STAGE103_VARIANT}_return_pct"] - frame[f"{BASELINE_VARIANT}_return_pct"]).median()
    )
    result["maxdd_delta_median_pp"] = float(
        (frame[f"{STAGE103_VARIANT}_maxdd_pct"] - frame[f"{BASELINE_VARIANT}_maxdd_pct"]).median()
    )
    result["ulcer_delta_median_pp"] = float(
        (frame[f"{STAGE103_VARIANT}_ulcer_pct"] - frame[f"{BASELINE_VARIANT}_ulcer_pct"]).median()
    )
    return result


def _block_bootstrap(returns: pd.DataFrame, sims: int = 2000) -> pd.DataFrame:
    rng = np.random.default_rng(409103)
    data = returns[VARIANT_ORDER].to_numpy(dtype=float)
    n = len(data)
    rows: list[dict[str, Any]] = []
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
        rows.append(_pairwise_resample_summary(samples, "moving_block_bootstrap", block_len))
    return pd.DataFrame(rows)


def _month_permutation(returns: pd.DataFrame, sims: int = 2000) -> pd.DataFrame:
    rng = np.random.default_rng(409203)
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
    return pd.DataFrame([_pairwise_resample_summary(samples, "month_order_permutation", None)])


def _top_edge_day_ablation(returns: pd.DataFrame) -> pd.DataFrame:
    edge = returns[STAGE103_VARIANT] - returns[BASELINE_VARIANT]
    positive_edge = edge[edge > 0].sort_values(ascending=False)
    base_metrics = _metrics_from_returns(returns[BASELINE_VARIANT].to_numpy(dtype=float))
    rows: list[dict[str, Any]] = []
    for top_n in [0, 1, 3, 5, 10, 20, 40, 80, 120]:
        adjusted = returns[STAGE103_VARIANT].copy()
        removed_edge_return_sum_pp = 0.0
        if top_n > 0:
            remove_dates = positive_edge.head(top_n).index
            removed_edge_return_sum_pp = float(positive_edge.head(top_n).sum() * 100.0)
            adjusted.loc[remove_dates] = returns.loc[remove_dates, BASELINE_VARIANT]
        metrics = _metrics_from_returns(adjusted.to_numpy(dtype=float))
        rows.append(
            {
                "removed_top_positive_edge_days": top_n,
                "removed_edge_return_sum_pp": removed_edge_return_sum_pp,
                "stage103_adjusted_total_return_pct": metrics["total_return_pct"],
                "stage103_adjusted_max_dd_pct": metrics["max_dd_pct"],
                "stage103_adjusted_sharpe": metrics["sharpe"],
                "stage103_adjusted_ulcer_pct": metrics["ulcer_pct"],
                "baseline_stage079_total_return_pct": base_metrics["total_return_pct"],
                "baseline_stage079_max_dd_pct": base_metrics["max_dd_pct"],
                "baseline_stage079_sharpe": base_metrics["sharpe"],
                "baseline_stage079_ulcer_pct": base_metrics["ulcer_pct"],
                "adjusted_return_delta_vs_stage079_pp": metrics["total_return_pct"] - base_metrics["total_return_pct"],
                "adjusted_maxdd_delta_vs_stage079_pp": metrics["max_dd_pct"] - base_metrics["max_dd_pct"],
                "adjusted_ulcer_delta_vs_stage079_pp": metrics["ulcer_pct"] - base_metrics["ulcer_pct"],
            }
        )
    return pd.DataFrame(rows)


def _summary_from_sources(summary: pd.DataFrame, score: pd.DataFrame, cost: pd.DataFrame, fresh_start: pd.DataFrame) -> pd.DataFrame:
    summary = summary[summary["variant"].isin(VARIANT_ORDER)].copy()
    score_pivot = (
        score[score["variant"].isin(VARIANT_ORDER)]
        .drop_duplicates(["variant"])
        .set_index("variant")[["score_90d", "score_180d", "short_holding_score"]]
    )
    cost_pivot = (
        cost[cost["variant"].isin(VARIANT_ORDER)]
        .pivot_table(index="variant", columns="slippage_multiplier", values="max_dd_pct", aggfunc="first")
        .rename(columns={1.0: "cost_1x_max_dd_pct", 2.0: "cost_2x_max_dd_pct", 3.0: "cost_3x_max_dd_pct", 5.0: "cost_5x_max_dd_pct"})
    )
    fresh_pivot = (
        fresh_start[fresh_start["variant"].isin(VARIANT_ORDER)]
        .groupby("variant")
        .agg(
            fresh_start_dd30_pass_rate=("dd30_pass", "mean"),
            fresh_start_worst_max_dd_pct=("max_dd_pct", "min"),
            fresh_start_min_return_pct=("total_return_pct", "min"),
            broker10_reject_days_total=("broker10_reject_days", "sum"),
        )
    )
    merged = summary.set_index("variant").join(score_pivot).join(cost_pivot).join(fresh_pivot).reset_index()
    merged["label"] = merged["variant"].map(LABELS).fillna(merged["label"])
    return merged


def _make_chart(
    rolling: pd.DataFrame,
    pairwise: pd.DataFrame,
    bootstrap: pd.DataFrame,
    month_perm: pd.DataFrame,
    topday: pd.DataFrame,
) -> None:
    plt.rcParams["font.sans-serif"] = ["Arial Unicode MS", "SimHei", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False

    fig, axes = plt.subplots(2, 2, figsize=(14, 9))

    focus = rolling[rolling["window_days"].isin([63, 90, 126, 180, 252, 504])]
    x_labels = [str(x) for x in sorted(focus["window_days"].unique())]
    x = np.arange(len(x_labels))
    width = 0.36
    for offset, variant in [(-width / 2, BASELINE_VARIANT), (width / 2, STAGE103_VARIANT)]:
        view = focus[focus["variant"].eq(variant)].set_index("window_days").loc[[int(v) for v in x_labels]]
        axes[0, 0].bar(x + offset, view["return_p05_pct"], width=width, label=LABELS[variant])
    axes[0, 0].axhline(0, color="#666666", linewidth=0.8)
    axes[0, 0].set_xticks(x, x_labels)
    axes[0, 0].set_title("任意启动持有期：5%分位收益")
    axes[0, 0].set_ylabel("%")
    axes[0, 0].legend()

    for variant in VARIANT_ORDER:
        view = focus[focus["variant"].eq(variant)].set_index("window_days").loc[[int(v) for v in x_labels]]
        axes[0, 1].plot(x, view["dd20_breach_rate"] * 100.0, marker="o", label=LABELS[variant])
    axes[0, 1].set_xticks(x, x_labels)
    axes[0, 1].set_title("任意启动持有期：窗口内破20%回撤率")
    axes[0, 1].set_ylabel("%")
    axes[0, 1].legend()

    resample = pd.concat([bootstrap, month_perm], ignore_index=True)
    labels = [
        f"B{int(row.block_len_days)}" if pd.notna(row.block_len_days) else "月重排"
        for row in resample.itertuples(index=False)
    ]
    rx = np.arange(len(labels))
    axes[1, 0].bar(rx - width / 2, resample["stage103_return_win_rate"] * 100.0, width=width, label="收益胜率")
    axes[1, 0].bar(rx + width / 2, resample["stage103_ulcer_not_worse_rate"] * 100.0, width=width, label="Ulcer不劣化率")
    axes[1, 0].axhline(50, color="#666666", linewidth=0.8)
    axes[1, 0].set_xticks(rx, labels)
    axes[1, 0].set_ylim(0, 105)
    axes[1, 0].set_title("路径扰动后 Stage103 相对 Stage079")
    axes[1, 0].set_ylabel("%")
    axes[1, 0].legend()

    axes[1, 1].plot(
        topday["removed_top_positive_edge_days"],
        topday["adjusted_return_delta_vs_stage079_pp"],
        marker="o",
        label="收益差",
    )
    axes[1, 1].plot(
        topday["removed_top_positive_edge_days"],
        topday["adjusted_maxdd_delta_vs_stage079_pp"],
        marker="o",
        label="最大回撤差",
    )
    axes[1, 1].axhline(0, color="#666666", linewidth=0.8)
    axes[1, 1].set_title("剔除Stage103最强相对贡献日后的优势")
    axes[1, 1].set_xlabel("剔除天数")
    axes[1, 1].set_ylabel("百分点")
    axes[1, 1].legend()

    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=160)
    plt.close(fig)


def _make_report(
    summary: pd.DataFrame,
    rolling: pd.DataFrame,
    pairwise: pd.DataFrame,
    bootstrap: pd.DataFrame,
    month_perm: pd.DataFrame,
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
        "fresh_start_worst_max_dd_pct",
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
            "window_days",
            "stage103_return_win_rate",
            "stage103_return_delta_median_pp",
            "stage103_return_delta_p05_pp",
            "stage103_maxdd_not_worse_rate",
            "stage103_ulcer_not_worse_rate",
            "stage103_all3_not_worse_rate",
        ]
    ]
    resample_view = pd.concat([bootstrap, month_perm], ignore_index=True)[
        [
            "method",
            "block_len_days",
            "sims",
            "stage103_return_win_rate",
            "stage103_maxdd_not_worse_rate",
            "stage103_ulcer_not_worse_rate",
            "stage103_all3_win_rate",
            "return_delta_median_pp",
            "maxdd_delta_median_pp",
            "ulcer_delta_median_pp",
            f"{BASELINE_VARIANT}_dd30_breach_rate",
            f"{STAGE103_VARIANT}_dd30_breach_rate",
        ]
    ]
    topday_view = topday[
        [
            "removed_top_positive_edge_days",
            "removed_edge_return_sum_pp",
            "stage103_adjusted_total_return_pct",
            "stage103_adjusted_max_dd_pct",
            "adjusted_return_delta_vs_stage079_pp",
            "adjusted_maxdd_delta_vs_stage079_pp",
            "adjusted_ulcer_delta_vs_stage079_pp",
        ]
    ]

    return f"""# Stage109 Stage103鲁棒性与反过拟合审计

## 结论

- 决策：`{decision["decision"]}`。
- 晋级判断：`{decision["promotion_judgement"]}`。
- 核心理由：{decision["reason"]}
- 本阶段不新增交易规则，不改 `0.5/10%/63日/broker10_guard`，只做路径和统计扰动审计。

## 外部方法参考

- Bailey 与 Lopez de Prado 的 [Deflated Sharpe Ratio](https://papers.ssrn.com/sol3/Delivery.cfm/SSRN_ID2460551_code87814.pdf?abstractid=2460551&mirid=1) / [Probability of Backtest Overfitting](https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf) 框架提示：多次试验后，单一漂亮 Sharpe 可能被选择偏差和非正态收益放大。
- walk-forward / 多启动点审计用于避免只相信一个起点的长回测，可参考 [walk-forward robustness](https://quanthop.com/learn/validation-robustness/walk-forward-analysis) 的滚动/扩展窗口思路。
- block bootstrap 与月份顺序扰动用于检查同一日收益分布在不同路径排列下是否仍相对稳健。
- GitHub 上 [pysystemtrade](https://github.com/robcarver17/pysystemtrade) 这类系统化交易框架也强调多市场、风控和可执行路径，而不是单次漂亮回测。
- 判断：这些方法不能“证明未来”，但可以识别候选是否过度依赖单一路径、少数盈利日或历史月份顺序。

## 固定路径核心结果

{_md_table(summary[key_summary_cols])}

## 任意启动持有期

{_md_table(rolling_view)}

## Stage103 相对 Stage079 的任意窗口胜率

{_md_table(pairwise_view)}

## 路径扰动

{_md_table(resample_view)}

## 极端相对贡献日剔除

{_md_table(topday_view)}

## 图表

![Stage109鲁棒性图表]({CHART_PATH})

## 解释

- `Ulcer` 是水下回撤的均方根，和最大回撤相比更关注“跌下去以后待多久、待多深”。
- `Stage103` 的优势不应被解释成新的主alpha大幅增强；它更像在 Stage079 上加入一个低自由度、正期望但规模受控的 xsmom 风险源。
- 如果未来目标改成“所有重采样路径都不破30”或“高滑点也必须绝对小于30”，当前结果仍不足，不能把 Stage103 说成厚安全垫版本。
"""


def main() -> None:
    daily = _read_csv(DAILY_SOURCE_PATH)
    source_summary = _read_csv(SUMMARY_SOURCE_PATH)
    source_horizon = _read_csv(HORIZON_SOURCE_PATH)
    source_score = _read_csv(SCORE_SOURCE_PATH)
    source_fresh_start = _read_csv(FRESH_START_SOURCE_PATH)
    source_cost = _read_csv(COST_SOURCE_PATH)
    source_margin = _read_csv(MARGIN_SOURCE_PATH)

    equity, returns = _build_return_frame(daily)
    rolling, pairwise = _rolling_holding_metrics(returns)
    bootstrap = _block_bootstrap(returns, sims=2000)
    month_perm = _month_permutation(returns, sims=2000)
    topday = _top_edge_day_ablation(returns)
    summary = _summary_from_sources(source_summary, source_score, source_cost, source_fresh_start)

    base = summary.set_index("variant").loc[BASELINE_VARIANT]
    cand = summary.set_index("variant").loc[STAGE103_VARIANT]
    fixed_path_pass = bool(
        cand["total_return_pct"] > base["total_return_pct"]
        and cand["max_dd_pct"] >= base["max_dd_pct"]
        and cand["sharpe"] >= base["sharpe"]
        and cand["ulcer_pct"] <= base["ulcer_pct"]
    )
    cost_not_worse = bool(
        cand["cost_2x_max_dd_pct"] >= base["cost_2x_max_dd_pct"]
        and cand["cost_3x_max_dd_pct"] >= base["cost_3x_max_dd_pct"]
        and cand["cost_5x_max_dd_pct"] >= base["cost_5x_max_dd_pct"]
    )
    fresh_not_worse = bool(cand["fresh_start_worst_max_dd_pct"] >= base["fresh_start_worst_max_dd_pct"])
    pairwise_return_strong = bool(
        pairwise[pairwise["window_days"].isin([63, 90, 126, 180])]["stage103_return_win_rate"].min() >= 0.55
        and pairwise[pairwise["window_days"].isin([90, 180])]["stage103_ulcer_not_worse_rate"].min() >= 0.50
    )
    pairwise_risk_strong = bool(
        pairwise[pairwise["window_days"].isin([90, 180, 252, 504])]["stage103_maxdd_not_worse_rate"].min() >= 0.85
        and pairwise[pairwise["window_days"].isin([90, 180, 252, 504])]["stage103_ulcer_not_worse_rate"].min()
        >= 0.95
    )
    resample = pd.concat([bootstrap, month_perm], ignore_index=True)
    resample_return_strong = bool(
        resample["stage103_return_win_rate"].min() >= 0.60
        and resample["stage103_ulcer_not_worse_rate"].min() >= 0.50
    )
    resample_risk_strong = bool(
        resample["stage103_maxdd_not_worse_rate"].min() >= 0.80
        and resample["stage103_ulcer_not_worse_rate"].min() >= 0.95
    )
    topday_not_single_spike = bool(
        topday[topday["removed_top_positive_edge_days"].eq(20)]["adjusted_return_delta_vs_stage079_pp"].iloc[0] > 0
        and topday[topday["removed_top_positive_edge_days"].eq(20)]["adjusted_ulcer_delta_vs_stage079_pp"].iloc[0] <= 0
    )

    absolute_like_gates = (
        fixed_path_pass
        and cost_not_worse
        and fresh_not_worse
        and pairwise_return_strong
        and pairwise_risk_strong
        and resample_return_strong
        and resample_risk_strong
    )
    retain_primary_gates = fixed_path_pass and cost_not_worse and fresh_not_worse and pairwise_risk_strong and resample_risk_strong
    if absolute_like_gates and topday_not_single_spike:
        decision_value = "robust_enough_for_further_engineering_promotion"
        promotion_judgement = "建议在已有执行相对候选基础上进一步晋级为工程化复跑 / paper影子盘重点候选，但仍不是绝对厚安全垫版本。"
        reason = (
            "固定路径、冷启动、成本压力、任意启动持有期和路径扰动均相对Stage079更好或不劣化，且优势不依赖少数20个相对贡献日。"
        )
    elif retain_primary_gates:
        decision_value = "retain_primary_relative_candidate_no_absolute_promotion"
        promotion_judgement = "保留 Stage103 作为当前最强执行相对候选，可进入工程化复跑 / paper影子盘；但不进一步升为绝对部署或正式替代版本。"
        reason = (
            "固定路径、冷启动、成本压力和路径扰动下的回撤/Ulcer优势成立；但任意窗口收益胜率不足、block bootstrap收益胜率仅约55%-59%，且收益端依赖少数强相对贡献日。"
        )
    else:
        decision_value = "robustness_gap_do_not_promote_further"
        promotion_judgement = "不建议进一步晋级；继续仅作研究候选或回到Stage079。"
        reason = "至少一个固定路径、冷启动、成本、任意启动或路径扰动闸门未通过。"

    decision = {
        "stage": "Stage109",
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "decision": decision_value,
        "promotion_judgement": promotion_judgement,
        "reason": reason,
        "gates": {
            "fixed_path_pass": fixed_path_pass,
            "cost_not_worse_than_stage079": cost_not_worse,
            "fresh_start_not_worse_than_stage079": fresh_not_worse,
            "pairwise_rolling_return_strong": pairwise_return_strong,
            "pairwise_rolling_risk_strong": pairwise_risk_strong,
            "resample_return_strong": resample_return_strong,
            "resample_risk_strong": resample_risk_strong,
            "topday_not_single_spike": topday_not_single_spike,
        },
        "stage079_total_return_pct": _safe_float(base["total_return_pct"]),
        "stage079_max_dd_pct": _safe_float(base["max_dd_pct"]),
        "stage079_sharpe": _safe_float(base["sharpe"]),
        "stage079_ulcer_pct": _safe_float(base["ulcer_pct"]),
        "stage103_total_return_pct": _safe_float(cand["total_return_pct"]),
        "stage103_max_dd_pct": _safe_float(cand["max_dd_pct"]),
        "stage103_sharpe": _safe_float(cand["sharpe"]),
        "stage103_ulcer_pct": _safe_float(cand["ulcer_pct"]),
        "stage103_score_90d": _safe_float(cand["score_90d"]),
        "stage103_score_180d": _safe_float(cand["score_180d"]),
        "rolling_pairwise": {
            str(int(row.window_days)): {
                "return_win_rate": _safe_float(row.stage103_return_win_rate),
                "return_delta_median_pp": _safe_float(row.stage103_return_delta_median_pp),
                "ulcer_not_worse_rate": _safe_float(row.stage103_ulcer_not_worse_rate),
                "maxdd_not_worse_rate": _safe_float(row.stage103_maxdd_not_worse_rate),
            }
            for row in pairwise.itertuples(index=False)
        },
        "resample": resample.to_dict(orient="records"),
        "topday_removed20": topday[topday["removed_top_positive_edge_days"].eq(20)].iloc[0].to_dict(),
        "source_files": {
            "daily": str(DAILY_SOURCE_PATH),
            "summary": str(SUMMARY_SOURCE_PATH),
            "horizon": str(HORIZON_SOURCE_PATH),
            "score": str(SCORE_SOURCE_PATH),
            "fresh_start": str(FRESH_START_SOURCE_PATH),
            "cost": str(COST_SOURCE_PATH),
            "margin": str(MARGIN_SOURCE_PATH),
        },
    }

    _make_chart(rolling, pairwise, bootstrap, month_perm, topday)
    report = _make_report(summary, rolling, pairwise, bootstrap, month_perm, topday, decision)

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
