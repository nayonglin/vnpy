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

MODEL_TAG = "stage438_independent_promotion_dashboard_v1"
OUTPUT_PREFIX = "qmt_roll_stage438_independent_promotion_dashboard"
LINE_ID = "futures_trend_drawdown30_preserve_return"

ACCOUNT_CAPITAL = 615_000.0

STAGE079 = "stage079"
STAGE103 = "xsmom_vt10_q_momq_round_half_true_broker10_guard"
STAGE115 = "stage103_plus_cffex_index_best1_tsmom60_guard"
STAGE136 = "stage103_plus_low_skew252_best1_vt10_mom63_round_half_guard"
VARIANTS = [STAGE079, STAGE103, STAGE115, STAGE136]

LABELS = {
    STAGE079: "Stage079",
    STAGE103: "Stage103",
    STAGE115: "Stage115",
    STAGE136: "Stage136",
}

DAILY_STAGE436 = OUTPUT_DIR / "qmt_roll_stage436_skewness_vt_guard_daily_stage436_skewness_vt_guard_v1.csv"
SUMMARY_STAGE437 = OUTPUT_DIR / "qmt_roll_stage437_stage136_robustness_audit_summary_stage437_stage136_robustness_audit_v1.csv"
DAILY_STAGE415 = OUTPUT_DIR / "qmt_roll_stage415_stage103_cffex_index_true_overlay_daily_stage415_stage103_cffex_index_true_overlay_v2.csv"
SUMMARY_STAGE416 = OUTPUT_DIR / "qmt_roll_stage416_stage115_robustness_overfit_audit_summary_stage416_stage115_robustness_overfit_audit_v1.csv"
DECISION_STAGE416 = OUTPUT_DIR / "qmt_roll_stage416_stage115_robustness_overfit_audit_decision_stage416_stage115_robustness_overfit_audit_v1.json"
DECISION_STAGE437 = OUTPUT_DIR / "qmt_roll_stage437_stage136_robustness_audit_decision_stage437_stage136_robustness_audit_v1.json"

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
ROLLING_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_rolling_holding_{MODEL_TAG}.csv"
PAIRWISE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_pairwise_rolling_{MODEL_TAG}.csv"
TOPDAY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_top_edge_day_ablation_{MODEL_TAG}.csv"
YEAR_ABLATION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_leave_one_year_ablation_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    frame = pd.read_csv(path, encoding="utf-8-sig")
    if "date" in frame.columns:
        frame["date"] = pd.to_datetime(frame["date"]).dt.normalize()
    return frame


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


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


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "无数据。"
    view = frame if max_rows is None else frame.head(max_rows)
    view = view.copy()
    for col in view.columns:
        if pd.api.types.is_float_dtype(view[col]):
            view[col] = view[col].map(lambda x: f"{x:.4f}" if pd.notna(x) else "")
    return view.to_markdown(index=False)


def _load_equity() -> pd.DataFrame:
    d436 = _read_csv(DAILY_STAGE436)
    d415 = _read_csv(DAILY_STAGE415)
    left = d436[d436["window_name"].eq("start_2020") & d436["variant"].isin([STAGE079, STAGE103, STAGE136])]
    right = d415[d415["window_name"].eq("start_2020") & d415["variant"].eq(STAGE115)]
    full = pd.concat([left, right], ignore_index=True)
    pivot = full.pivot_table(index="date", columns="variant", values="equity", aggfunc="last").sort_index()
    pivot = pivot[VARIANTS].dropna()
    calendar = pivot.reindex(pd.date_range(pivot.index.min(), pivot.index.max(), freq="D")).ffill()
    calendar.index.name = "date"
    return calendar


def _rolling_holding(equity: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    windows = [21, 63, 90, 126, 180, 252, 504, 756]
    date_index = pd.Index(equity.index)
    cache: dict[tuple[str, int], pd.DataFrame] = {}
    rows: list[dict[str, Any]] = []

    for variant in VARIANTS:
        values = equity[variant].to_numpy(dtype=float)
        for window in windows:
            segment_rows: list[dict[str, Any]] = []
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
                segment_rows.append(
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
            segment_frame = pd.DataFrame(segment_rows)
            cache[(variant, window)] = segment_frame
            rows.append(
                {
                    "variant": variant,
                    "label": LABELS[variant],
                    "window_days": window,
                    "count": len(segment_frame),
                    "return_p01_pct": float(segment_frame["return_pct"].quantile(0.01)),
                    "return_p05_pct": float(segment_frame["return_pct"].quantile(0.05)),
                    "return_median_pct": float(segment_frame["return_pct"].median()),
                    "positive_return_rate": float((segment_frame["return_pct"] > 0.0).mean()),
                    "annualized_below_5pct_rate": float((segment_frame["annualized_return_pct"] < 5.0).mean()),
                    "max_dd_worst_pct": float(segment_frame["max_dd_pct"].min()),
                    "dd20_breach_rate": float((segment_frame["max_dd_pct"] < -20.0).mean()),
                    "dd30_breach_rate": float((segment_frame["max_dd_pct"] < -30.0).mean()),
                    "ulcer_p95_pct": float(segment_frame["ulcer_pct"].quantile(0.95)),
                    "longest_underwater_p95_days": float(segment_frame["longest_underwater_days"].quantile(0.95)),
                }
            )

    pairwise_rows: list[dict[str, Any]] = []
    for candidate in [STAGE103, STAGE115, STAGE136]:
        for comparator in [STAGE079, STAGE103]:
            if candidate == comparator:
                continue
            for window in windows:
                cand = cache[(candidate, window)]
                comp = cache[(comparator, window)]
                pairwise_rows.append(
                    {
                        "candidate_variant": candidate,
                        "candidate_label": LABELS[candidate],
                        "comparator_variant": comparator,
                        "comparator_label": LABELS[comparator],
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
                    }
                )
    return pd.DataFrame(rows), pd.DataFrame(pairwise_rows)


def _daily_returns(equity: pd.DataFrame) -> pd.DataFrame:
    returns = equity.pct_change()
    returns.iloc[0] = equity.iloc[0] / ACCOUNT_CAPITAL - 1.0
    return returns


def _returns_metrics(returns: pd.Series) -> dict[str, float]:
    clean = returns.astype(float).to_numpy()
    nav = ACCOUNT_CAPITAL * np.cumprod(1.0 + clean)
    nav = np.concatenate([[ACCOUNT_CAPITAL], nav])
    std = float(np.std(clean, ddof=1)) if len(clean) > 1 else 0.0
    sharpe = float(np.mean(clean) / std * math.sqrt(252.0)) if std > 0 else 0.0
    return {
        "total_return_pct": float((nav[-1] / ACCOUNT_CAPITAL - 1.0) * 100.0),
        "max_dd_pct": _max_drawdown_pct(nav),
        "sharpe": sharpe,
        "ulcer_pct": _ulcer_pct(nav),
    }


def _top_edge_day_ablation(equity: pd.DataFrame) -> pd.DataFrame:
    returns = _daily_returns(equity)
    rows: list[dict[str, Any]] = []
    for candidate in [STAGE103, STAGE115, STAGE136]:
        for comparator in [STAGE079, STAGE103]:
            if candidate == comparator:
                continue
            edge = returns[candidate] - returns[comparator]
            for top_n in [0, 1, 3, 5, 20]:
                adjusted = returns[candidate].copy()
                removed_sum = 0.0
                if top_n > 0:
                    top_dates = edge.sort_values(ascending=False).head(top_n).index
                    removed_sum = float(edge.loc[top_dates].sum() * 100.0)
                    adjusted.loc[top_dates] = returns.loc[top_dates, comparator]
                cand_metrics = _returns_metrics(adjusted)
                comp_metrics = _returns_metrics(returns[comparator])
                rows.append(
                    {
                        "candidate_variant": candidate,
                        "candidate_label": LABELS[candidate],
                        "comparator_variant": comparator,
                        "comparator_label": LABELS[comparator],
                        "removed_top_positive_edge_days": top_n,
                        "removed_edge_return_sum_pp": removed_sum,
                        "candidate_adjusted_total_return_pct": cand_metrics["total_return_pct"],
                        "comparator_total_return_pct": comp_metrics["total_return_pct"],
                        "adjusted_return_delta_pp": cand_metrics["total_return_pct"] - comp_metrics["total_return_pct"],
                        "candidate_adjusted_max_dd_pct": cand_metrics["max_dd_pct"],
                        "comparator_max_dd_pct": comp_metrics["max_dd_pct"],
                        "adjusted_maxdd_delta_pp": cand_metrics["max_dd_pct"] - comp_metrics["max_dd_pct"],
                        "candidate_adjusted_ulcer_pct": cand_metrics["ulcer_pct"],
                        "comparator_ulcer_pct": comp_metrics["ulcer_pct"],
                        "adjusted_ulcer_delta_pp": cand_metrics["ulcer_pct"] - comp_metrics["ulcer_pct"],
                    }
                )
    return pd.DataFrame(rows)


def _leave_one_year(equity: pd.DataFrame) -> pd.DataFrame:
    returns = _daily_returns(equity)
    years = sorted(pd.Index(returns.index.year).unique())
    rows: list[dict[str, Any]] = []
    for candidate in [STAGE103, STAGE115, STAGE136]:
        for comparator in [STAGE079, STAGE103]:
            if candidate == comparator:
                continue
            for year in years:
                mask = returns.index.year != year
                cand_metrics = _returns_metrics(returns.loc[mask, candidate])
                comp_metrics = _returns_metrics(returns.loc[mask, comparator])
                rows.append(
                    {
                        "candidate_variant": candidate,
                        "candidate_label": LABELS[candidate],
                        "comparator_variant": comparator,
                        "comparator_label": LABELS[comparator],
                        "removed_year": int(year),
                        "candidate_total_return_pct": cand_metrics["total_return_pct"],
                        "comparator_total_return_pct": comp_metrics["total_return_pct"],
                        "return_delta_pp": cand_metrics["total_return_pct"] - comp_metrics["total_return_pct"],
                        "candidate_max_dd_pct": cand_metrics["max_dd_pct"],
                        "comparator_max_dd_pct": comp_metrics["max_dd_pct"],
                        "maxdd_delta_pp": cand_metrics["max_dd_pct"] - comp_metrics["max_dd_pct"],
                        "candidate_ulcer_pct": cand_metrics["ulcer_pct"],
                        "comparator_ulcer_pct": comp_metrics["ulcer_pct"],
                        "ulcer_delta_pp": cand_metrics["ulcer_pct"] - comp_metrics["ulcer_pct"],
                    }
                )
    return pd.DataFrame(rows)


def _build_summary() -> pd.DataFrame:
    stage437 = _read_csv(SUMMARY_STAGE437)
    stage416 = _read_csv(SUMMARY_STAGE416)
    rows = []
    for variant in [STAGE079, STAGE103, STAGE136]:
        rows.append(stage437[stage437["variant"].eq(variant)].iloc[0].to_dict())
    rows.append(stage416[stage416["variant"].eq(STAGE115)].iloc[0].to_dict())
    summary = pd.DataFrame(rows)
    summary["label_short"] = summary["variant"].map(LABELS)
    judgement = {
        STAGE079: "baseline_keep",
        STAGE103: "promote_main_execution_relative_candidate",
        STAGE115: "high_score_paper_only",
        STAGE136: "paper_only_overfit_warning",
    }
    rank = {STAGE103: 1, STAGE115: 2, STAGE136: 3, STAGE079: 4}
    summary["independent_judgement"] = summary["variant"].map(judgement)
    summary["independent_rank"] = summary["variant"].map(rank)
    return summary.sort_values("independent_rank")


def _plot(equity: pd.DataFrame, summary: pd.DataFrame, pairwise: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(16, 10))
    colors = {
        STAGE079: "#555555",
        STAGE103: "#1f77b4",
        STAGE115: "#2ca02c",
        STAGE136: "#d62728",
    }

    ax = axes[0, 0]
    for variant in VARIANTS:
        ax.plot(equity.index, equity[variant] / ACCOUNT_CAPITAL, label=LABELS[variant], linewidth=1.8, color=colors[variant])
    ax.set_yscale("log")
    ax.set_title("Equity multiple, log scale")
    ax.grid(True, alpha=0.25)
    ax.legend()

    ax = axes[0, 1]
    for variant in VARIANTS:
        nav = equity[variant] / equity[variant].cummax() - 1.0
        ax.plot(equity.index, nav * 100.0, label=LABELS[variant], linewidth=1.5, color=colors[variant])
    ax.axhline(-30.0, color="#aa0000", linestyle="--", linewidth=1)
    ax.set_title("Drawdown")
    ax.set_ylabel("%")
    ax.grid(True, alpha=0.25)

    ax = axes[1, 0]
    focus = pairwise[pairwise["comparator_variant"].eq(STAGE079) & pairwise["window_days"].isin([90, 180, 252, 504])]
    labels = [90, 180, 252, 504]
    x = np.arange(len(labels))
    width = 0.24
    for idx, variant in enumerate([STAGE103, STAGE115, STAGE136]):
        vals = []
        for window in labels:
            row = focus[focus["candidate_variant"].eq(variant) & focus["window_days"].eq(window)].iloc[0]
            vals.append(float(row["return_win_rate"]) * 100.0)
        ax.bar(x + (idx - 1) * width, vals, width=width, label=LABELS[variant], color=colors[variant])
    ax.axhline(50.0, color="#444444", linestyle="--", linewidth=1)
    ax.set_xticks(x)
    ax.set_xticklabels([f"{w}d" for w in labels])
    ax.set_ylim(0, 100)
    ax.set_title("Return win rate vs Stage079")
    ax.set_ylabel("% windows")
    ax.grid(True, axis="y", alpha=0.25)
    ax.legend()

    ax = axes[1, 1]
    view = summary.set_index("variant").loc[[STAGE079, STAGE103, STAGE115, STAGE136]]
    x = np.arange(len(view))
    ax.bar(x - 0.24, view["score_90d"].astype(float), width=0.24, label="90d score", color="#9467bd")
    ax.bar(x, view["score_180d"].astype(float), width=0.24, label="180d score", color="#ff7f0e")
    ax2 = ax.twinx()
    ax2.plot(x + 0.24, view["max_dd_pct"].astype(float), marker="o", color="#aa0000", label="Max DD")
    ax.set_xticks(x)
    ax.set_xticklabels([LABELS[v] for v in view.index], rotation=15)
    ax.set_title("Short holding score and max drawdown")
    ax.set_ylabel("score")
    ax2.set_ylabel("max DD %")
    ax.grid(True, axis="y", alpha=0.25)
    lines, line_labels = ax.get_legend_handles_labels()
    lines2, line_labels2 = ax2.get_legend_handles_labels()
    ax.legend(lines + lines2, line_labels + line_labels2, loc="upper left")

    fig.suptitle("Stage138 independent promotion dashboard", fontsize=15)
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    fig.savefig(CHART_PATH, dpi=180)
    plt.close(fig)


def _build_decision(summary: pd.DataFrame, pairwise: pd.DataFrame, topday: pd.DataFrame, year_ablation: pd.DataFrame) -> dict[str, Any]:
    def row(variant: str) -> pd.Series:
        return summary[summary["variant"].eq(variant)].iloc[0]

    stage103_vs_079 = pairwise[pairwise["candidate_variant"].eq(STAGE103) & pairwise["comparator_variant"].eq(STAGE079)]
    stage115_vs_103 = pairwise[pairwise["candidate_variant"].eq(STAGE115) & pairwise["comparator_variant"].eq(STAGE103)]
    stage136_vs_103 = pairwise[pairwise["candidate_variant"].eq(STAGE136) & pairwise["comparator_variant"].eq(STAGE103)]

    top115_vs_103_1 = topday[
        topday["candidate_variant"].eq(STAGE115)
        & topday["comparator_variant"].eq(STAGE103)
        & topday["removed_top_positive_edge_days"].eq(1)
    ].iloc[0]
    top136_vs_103_1 = topday[
        topday["candidate_variant"].eq(STAGE136)
        & topday["comparator_variant"].eq(STAGE103)
        & topday["removed_top_positive_edge_days"].eq(1)
    ].iloc[0]
    y136_vs_079 = year_ablation[
        year_ablation["candidate_variant"].eq(STAGE136) & year_ablation["comparator_variant"].eq(STAGE079)
    ]

    decision = {
        "stage": "Stage138",
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "decision": "promote_stage103_main_keep_stage115_stage136_paper",
        "main_promotion": {
            "variant": STAGE103,
            "label": LABELS[STAGE103],
            "judgement": "值得作为当前主执行相对候选晋级，不是因为单项最高，而是因为低自由度、已有真实整数手/保证金审计、全周期硬指标优于Stage079且后续审计没有发现必须降级的集中性缺陷。",
            "total_return_pct": float(row(STAGE103)["total_return_pct"]),
            "max_dd_pct": float(row(STAGE103)["max_dd_pct"]),
            "sharpe": float(row(STAGE103)["sharpe"]),
            "ulcer_pct": float(row(STAGE103)["ulcer_pct"]),
            "score_90d": float(row(STAGE103)["score_90d"]),
            "score_180d": float(row(STAGE103)["score_180d"]),
            "return_win_rate_vs_stage079_90_180_252_504": {
                str(int(r["window_days"])): float(r["return_win_rate"])
                for _, r in stage103_vs_079[stage103_vs_079["window_days"].isin([90, 180, 252, 504])].iterrows()
            },
        },
        "paper_candidates": {
            "stage115": {
                "variant": STAGE115,
                "label": LABELS[STAGE115],
                "judgement": "可以不按硬目标作为高分paper观察，但不晋级主执行版本。",
                "reason": "短持有分、回撤和Ulcer显著好，但相对Stage103的中长持有收益胜率不足，剔除最大贡献日后收益优势转弱，并且绝对保证金仍未完全干净。",
                "total_return_pct": float(row(STAGE115)["total_return_pct"]),
                "max_dd_pct": float(row(STAGE115)["max_dd_pct"]),
                "score_90d": float(row(STAGE115)["score_90d"]),
                "score_180d": float(row(STAGE115)["score_180d"]),
                "return_win_rate_vs_stage103_90_180_252_504": {
                    str(int(r["window_days"])): float(r["return_win_rate"])
                    for _, r in stage115_vs_103[stage115_vs_103["window_days"].isin([90, 180, 252, 504])].iterrows()
                },
                "top1_edge_ablation_return_delta_vs_stage103_pp": float(top115_vs_103_1["adjusted_return_delta_pp"]),
                "broker10_required_extra_cash_max": float(row(STAGE115).get("broker10_required_extra_cash_max", np.nan)),
            },
            "stage136": {
                "variant": STAGE136,
                "label": LABELS[STAGE136],
                "judgement": "只保留paper/体验观察，不做主晋级。",
                "reason": "全周期指标好看，但Stage137已显示收益优势依赖2021和少数相对贡献日，daily edge PSR也不支持稳定alpha。",
                "total_return_pct": float(row(STAGE136)["total_return_pct"]),
                "max_dd_pct": float(row(STAGE136)["max_dd_pct"]),
                "score_90d": float(row(STAGE136)["score_90d"]),
                "score_180d": float(row(STAGE136)["score_180d"]),
                "return_win_rate_vs_stage103_90_180_252_504": {
                    str(int(r["window_days"])): float(r["return_win_rate"])
                    for _, r in stage136_vs_103[stage136_vs_103["window_days"].isin([90, 180, 252, 504])].iterrows()
                },
                "top1_edge_ablation_return_delta_vs_stage103_pp": float(top136_vs_103_1["adjusted_return_delta_pp"]),
                "leave_one_year_min_return_delta_vs_stage079_pp": float(y136_vs_079["return_delta_pp"].min()),
            },
        },
        "do_not_pursue": [
            "不继续救Stage136偏度路线的小参数。",
            "不继续救Stage115股指TSMOM的保证金/贡献日/窗口小参数。",
            "不继续做连续失败信号路线，Stage094/095已显示胜率提升不等于期望收益提升。",
        ],
        "source_files": {
            "stage436_daily": str(DAILY_STAGE436),
            "stage437_summary": str(SUMMARY_STAGE437),
            "stage415_daily": str(DAILY_STAGE415),
            "stage416_summary": str(SUMMARY_STAGE416),
            "stage416_decision": str(DECISION_STAGE416),
            "stage437_decision": str(DECISION_STAGE437),
        },
        "outputs": {
            "summary": str(SUMMARY_PATH),
            "rolling": str(ROLLING_PATH),
            "pairwise": str(PAIRWISE_PATH),
            "topday": str(TOPDAY_PATH),
            "year_ablation": str(YEAR_ABLATION_PATH),
            "chart": str(CHART_PATH),
            "report": str(REPORT_PATH),
        },
    }
    return _json_safe(decision)


def _build_report(summary: pd.DataFrame, rolling: pd.DataFrame, pairwise: pd.DataFrame, topday: pd.DataFrame, year_ablation: pd.DataFrame, decision: dict[str, Any]) -> str:
    compact = summary[
        [
            "label_short",
            "independent_judgement",
            "total_return_pct",
            "max_dd_pct",
            "sharpe",
            "ulcer_pct",
            "score_90d",
            "score_180d",
            "cost_2x_max_dd_pct",
            "cost_3x_max_dd_pct",
            "broker10_required_extra_cash_max",
        ]
    ].copy()
    compact = compact.rename(columns={"label_short": "版本", "independent_judgement": "晋级判断"})

    rolling_view = rolling[rolling["window_days"].isin([90, 180, 252, 504])][
        [
            "label",
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
    pairwise_view = pairwise[pairwise["window_days"].isin([90, 180, 252, 504])][
        [
            "candidate_label",
            "comparator_label",
            "window_days",
            "return_win_rate",
            "return_delta_median_pp",
            "maxdd_not_worse_rate",
            "ulcer_not_worse_rate",
        ]
    ]
    top_view = topday[
        topday["removed_top_positive_edge_days"].isin([1, 3, 5])
        & topday["comparator_variant"].isin([STAGE079, STAGE103])
    ][
        [
            "candidate_label",
            "comparator_label",
            "removed_top_positive_edge_days",
            "adjusted_return_delta_pp",
            "adjusted_maxdd_delta_pp",
            "adjusted_ulcer_delta_pp",
        ]
    ]
    year_view = year_ablation.groupby(["candidate_label", "comparator_label"], as_index=False).agg(
        min_return_delta_pp=("return_delta_pp", "min"),
        min_maxdd_delta_pp=("maxdd_delta_pp", "min"),
        max_ulcer_delta_pp=("ulcer_delta_pp", "max"),
    )

    return f"""# Stage138 独立晋级判断看板

- 生成时间：2026-05-28 03:03 CST
- line_id：`{LINE_ID}`
- 阶段性质：只读裁决；不新增策略、不改参数、不扫窗口、不新增资金。
- 评估对象：Stage079、Stage103、Stage115、Stage136。
- 最终裁决：`{decision["decision"]}`。

## 外部调研与判断

- 参考方向：PBO/Deflated Sharpe/PSR、walk-forward、贡献日剔除、rolling holding、block bootstrap。
- 调研结论：多次回测后的晋级不能只看全样本收益和Sharpe；必须检查任意启动、样本分段、贡献集中和保证金/成本可执行性。
- 本次判断：Stage103的优势不是最高分，而是最干净；Stage115和Stage136可以保留paper，但不应因为某张全样本表好看而主晋级。

## 晋级判断总表

{_md_table(compact)}

## 任意启动持有体验

{_md_table(rolling_view)}

## 相对Stage079/Stage103滚动胜率

{_md_table(pairwise_view)}

## 顶部贡献日剔除

{_md_table(top_view)}

## 留一年度稳健性摘要

{_md_table(year_view)}

## 裁决

- 主执行相对候选：Stage103 `{STAGE103}`。
- 高分paper观察：Stage115 `{STAGE115}`，不主晋级。
- paper/体验观察：Stage136 `{STAGE136}`，不主晋级。
- Stage079 保持为当前baseline。

## 过拟合反思

- 本阶段不是过拟合：没有新增规则、没有调参数，只整合既有固定路径和扰动审计。
- 继续救Stage115/Stage136会提高过拟合风险：二者失败点分别是保证金/贡献集中、年份/贡献日/PSR集中，不适合靠小参数修补。

## 继续价值反思

- 继续做Stage103工程化复跑、paper/影子盘、真实券商保证金对账有价值。
- 继续主动找新alpha也有价值，但只能是全新、低自由度、样本更分散、保证金更轻的新风险源。
- 继续沿连续失败信号、偏度self-validation、股指TSMOM救参这些路线主动优化，价值低。

![Stage138 chart]({CHART_PATH})
"""


def main() -> None:
    equity = _load_equity()
    summary = _build_summary()
    rolling, pairwise = _rolling_holding(equity)
    topday = _top_edge_day_ablation(equity)
    year_ablation = _leave_one_year(equity)
    decision = _build_decision(summary, pairwise, topday, year_ablation)
    report = _build_report(summary, rolling, pairwise, topday, year_ablation, decision)

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    rolling.to_csv(ROLLING_PATH, index=False, encoding="utf-8-sig")
    pairwise.to_csv(PAIRWISE_PATH, index=False, encoding="utf-8-sig")
    topday.to_csv(TOPDAY_PATH, index=False, encoding="utf-8-sig")
    year_ablation.to_csv(YEAR_ABLATION_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(decision, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_PATH.write_text(report, encoding="utf-8")
    _plot(equity, summary, pairwise)

    print(f"decision={decision['decision']}")
    print(f"summary={SUMMARY_PATH}")
    print(f"report={REPORT_PATH}")
    print(f"chart={CHART_PATH}")


if __name__ == "__main__":
    main()
