from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

import analyze_qmt_roll_stage306_low_corr_satellite_scout as stage306


MODEL_TAG = "stage307_low_corr_weight_frontier_v1"
OUTPUT_PREFIX = "qmt_roll_stage307_low_corr_weight_frontier"
LINE_ID = "futures_trend_drawdown30_preserve_return"

# Coarse strategic capital splits only. This is not an alpha-parameter sweep.
BASE_WEIGHTS: tuple[float, ...] = (0.80, 0.825, 0.85, 0.875, 0.90, 0.925, 0.95, 0.975)


def _weight_label(base_weight: float) -> str:
    satellite_weight = 1.0 - base_weight
    return f"base{base_weight:.3f}_sat{satellite_weight:.3f}"


def _combo_nav_for_window(
    base_nav: pd.Series,
    satellite_nav: pd.Series,
    start: str,
    end: str,
    base_weight: float,
) -> pd.Series:
    base = stage306._rebased_window(base_nav, start, end)
    satellite = stage306._rebased_window(satellite_nav, start, end)
    return (base_weight * base + (1.0 - base_weight) * satellite).dropna()


def _run_frontier() -> tuple[pd.DataFrame, pd.DataFrame]:
    baseline_nav, base_nav = stage306._load_base_curves()
    base_index = base_nav.index

    baseline_metrics_by_window: dict[str, dict[str, float]] = {}
    base_metrics_by_window: dict[str, dict[str, float]] = {}
    for window_name, start, end in stage306.WINDOWS:
        baseline_metrics_by_window[window_name] = stage306._path_metrics(
            stage306._rebased_window(baseline_nav, start, end)
        )
        base_metrics_by_window[window_name] = stage306._path_metrics(
            stage306._rebased_window(base_nav, start, end)
        )

    window_rows: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []
    for path in stage306._candidate_paths():
        candidate = stage306._load_candidate(path, base_index)
        if candidate is None:
            continue
        for base_weight in BASE_WEIGHTS:
            weight_label = _weight_label(base_weight)
            for window_name, start, end in stage306.WINDOWS:
                baseline_metrics = baseline_metrics_by_window[window_name]
                base_metrics = base_metrics_by_window[window_name]
                combo_nav = _combo_nav_for_window(base_nav, candidate.nav, start, end, base_weight)
                metrics = stage306._path_metrics(combo_nav)
                retention = stage306._retention(
                    metrics["total_return_pct"],
                    baseline_metrics["total_return_pct"],
                )
                window_rows.append(
                    {
                        "candidate": candidate.name,
                        "weight_label": weight_label,
                        "base_weight": base_weight,
                        "satellite_weight": 1.0 - base_weight,
                        "window_name": window_name,
                        "baseline_return_pct": baseline_metrics["total_return_pct"],
                        "base_pressure040_return_pct": base_metrics["total_return_pct"],
                        "combo_return_pct": metrics["total_return_pct"],
                        "return_retention_pct": retention,
                        "baseline_max_dd_pct": baseline_metrics["max_dd_percent"],
                        "base_pressure040_max_dd_pct": base_metrics["max_dd_percent"],
                        "combo_max_dd_pct": metrics["max_dd_percent"],
                        "combo_sharpe": metrics["sharpe_ratio"],
                        "strict_pass": int(metrics["max_dd_percent"] >= -30.0 and retention >= 80.0),
                        "research_pass": int(metrics["max_dd_percent"] >= -30.0 and retention >= 65.0),
                    }
                )

    window_df = pd.DataFrame(window_rows)
    for (candidate, weight_label), group in window_df.groupby(["candidate", "weight_label"], sort=False):
        positive = group[group["baseline_return_pct"] > 0]
        full = group[group["window_name"].eq(stage306.FULL_WINDOW)].iloc[0]
        summary_rows.append(
            {
                "candidate": candidate,
                "weight_label": weight_label,
                "base_weight": float(full["base_weight"]),
                "satellite_weight": float(full["satellite_weight"]),
                "positive_window_count": int(len(positive)),
                "strict_pass_count": int(positive["strict_pass"].sum()),
                "research_pass_count": int(positive["research_pass"].sum()),
                "min_return_retention_pct": float(positive["return_retention_pct"].min()) if not positive.empty else 0.0,
                "worst_max_dd_pct": float(positive["combo_max_dd_pct"].min()) if not positive.empty else 0.0,
                "full_return_pct": float(full["combo_return_pct"]),
                "full_return_retention_pct": float(full["return_retention_pct"]),
                "full_max_dd_pct": float(full["combo_max_dd_pct"]),
                "full_sharpe": float(full["combo_sharpe"]),
            }
        )

    summary_df = pd.DataFrame(summary_rows)
    if not summary_df.empty:
        summary_df["strict_all_windows"] = (
            summary_df["strict_pass_count"].eq(summary_df["positive_window_count"])
            & summary_df["min_return_retention_pct"].ge(80.0)
            & summary_df["worst_max_dd_pct"].ge(-30.0)
        ).astype(int)
        summary_df["research_all_windows"] = (
            summary_df["research_pass_count"].eq(summary_df["positive_window_count"])
            & summary_df["min_return_retention_pct"].ge(65.0)
            & summary_df["worst_max_dd_pct"].ge(-30.0)
        ).astype(int)
        summary_df = summary_df.sort_values(
            [
                "strict_all_windows",
                "research_all_windows",
                "min_return_retention_pct",
                "worst_max_dd_pct",
                "full_return_retention_pct",
            ],
            ascending=[False, False, False, False, False],
        )
    return summary_df, window_df


def _build_report(summary_df: pd.DataFrame, window_df: pd.DataFrame) -> str:
    lines = [
        "# Stage307 低相关组合权重前沿",
        "",
        "## 目标",
        "",
        "- 在 Stage306 发现的低相关卫星候选上，只扫描粗粒度资金分配比例。",
        "- 目标仍是多周期最大回撤小于30%，并尽量保持第78-1收益。",
        "- 这是组合层资金权重，不改78-1信号、不改卫星策略参数。",
        "",
        "## 前沿排名",
        "",
    ]
    if summary_df.empty:
        lines.append("- 未得到有效结果。")
    else:
        cols = [
            "candidate",
            "weight_label",
            "strict_all_windows",
            "research_all_windows",
            "strict_pass_count",
            "research_pass_count",
            "min_return_retention_pct",
            "worst_max_dd_pct",
            "full_return_pct",
            "full_return_retention_pct",
            "full_max_dd_pct",
            "full_sharpe",
        ]
        lines.append(summary_df[cols].head(40).to_markdown(index=False))

    lines.extend(["", "## 最优候选窗口明细", ""])
    if not summary_df.empty:
        best = summary_df.iloc[0]
        detail = window_df[
            window_df["candidate"].eq(best["candidate"])
            & window_df["weight_label"].eq(best["weight_label"])
        ][
            [
                "window_name",
                "baseline_return_pct",
                "base_pressure040_return_pct",
                "combo_return_pct",
                "return_retention_pct",
                "baseline_max_dd_pct",
                "base_pressure040_max_dd_pct",
                "combo_max_dd_pct",
                "strict_pass",
                "research_pass",
            ]
        ]
        lines.append(detail.to_markdown(index=False))

    lines.extend(["", "## 阶段判断", ""])
    if summary_df.empty:
        lines.append("- 未找到可用候选。")
    else:
        best = summary_df.iloc[0]
        if int(best["strict_all_windows"]) == 1:
            lines.append(
                f"- 找到严格多周期候选：`{best['candidate']}` / `{best['weight_label']}`。"
            )
        elif int(best["research_all_windows"]) == 1:
            lines.append(
                f"- 找到研究级候选：`{best['candidate']}` / `{best['weight_label']}`；"
                f"最低收益保留 `{best['min_return_retention_pct']:.2f}%`，最差回撤 `{best['worst_max_dd_pct']:.2f}%`。"
            )
            lines.append("- 它仍未达到80%收益保留硬标准，不能直接升级为正式候选。")
        else:
            lines.append("- 未找到多周期同时满足回撤和收益保留的候选。")
    return "\n".join(lines) + "\n"


def main() -> None:
    stage306.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    summary_df, window_df = _run_frontier()

    summary_path = stage306.OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
    window_path = stage306.OUTPUT_DIR / f"{OUTPUT_PREFIX}_windows_{MODEL_TAG}.csv"
    report_path = stage306.OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
    decision_path = stage306.OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

    summary_df.to_csv(summary_path, index=False, encoding="utf-8-sig")
    window_df.to_csv(window_path, index=False, encoding="utf-8-sig")
    report_path.write_text(_build_report(summary_df, window_df), encoding="utf-8")

    decision = {
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "base_variant": stage306.BASE_VARIANT,
        "base_weights": list(BASE_WEIGHTS),
        "candidate_count": int(summary_df["candidate"].nunique()) if not summary_df.empty else 0,
        "combination_count": int(len(summary_df)),
        "strict_all_count": int(summary_df["strict_all_windows"].sum()) if not summary_df.empty else 0,
        "research_all_count": int(summary_df["research_all_windows"].sum()) if not summary_df.empty else 0,
        "top": summary_df.head(10).to_dict(orient="records"),
        "paths": {
            "summary": str(summary_path),
            "windows": str(window_path),
            "report": str(report_path),
        },
    }
    decision_path.write_text(json.dumps(decision, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[stage307] summary={summary_path}")
    print(f"[stage307] windows={window_path}")
    print(f"[stage307] report={report_path}")
    print(f"[stage307] decision={decision_path}")
    print(report_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
