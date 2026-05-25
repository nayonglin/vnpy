from __future__ import annotations

import json
from typing import Any

import pandas as pd

import analyze_qmt_roll_stage306_low_corr_satellite_scout as stage306
from analyze_qmt_roll_stage308_pressure040_dynamic_dd_gate import (
    Profile,
    _metrics_from_returns,
    _simulate_dynamic_gate,
)


MODEL_TAG = "stage309_dynamic_dd_gate_sensitivity_v1"
OUTPUT_PREFIX = "qmt_roll_stage309_dynamic_dd_gate_sensitivity"
LINE_ID = "futures_trend_drawdown30_preserve_return"

DD_STARTS = (0.10, 0.12, 0.14, 0.16)
DD_FULLS = (0.28, 0.30, 0.32, 0.34)
MIN_WEIGHTS = (0.80, 0.825, 0.85, 0.875, 0.90)


def _profiles() -> list[Profile]:
    profiles: list[Profile] = []
    for dd_start in DD_STARTS:
        for dd_full in DD_FULLS:
            if dd_full <= dd_start:
                continue
            for min_weight in MIN_WEIGHTS:
                profiles.append(
                    Profile(
                        name=f"dd{int(dd_start*100):02d}_{int(dd_full*100):02d}_min{int(min_weight*1000):03d}",
                        dd_start=dd_start,
                        dd_full=dd_full,
                        min_weight=min_weight,
                    )
                )
    return profiles


def _run_suite() -> tuple[pd.DataFrame, pd.DataFrame]:
    baseline_nav, base_nav = stage306._load_base_curves()
    rows: list[dict[str, Any]] = []
    for profile in _profiles():
        for window_name, start, end in stage306.WINDOWS:
            baseline_window = stage306._rebased_window(baseline_nav, start, end)
            base_window = stage306._rebased_window(base_nav, start, end)
            baseline_metrics = stage306._path_metrics(baseline_window)
            base_metrics = stage306._path_metrics(base_window)
            curve = _simulate_dynamic_gate(base_window, profile)
            if curve.empty:
                continue
            metrics = _metrics_from_returns(curve.set_index("date")["nav"], curve["overlay_return"])
            retention = stage306._retention(metrics["total_return_pct"], baseline_metrics["total_return_pct"])
            weights = pd.to_numeric(curve["weight"], errors="coerce").fillna(1.0)
            rows.append(
                {
                    "profile": profile.name,
                    "dd_start": profile.dd_start,
                    "dd_full": profile.dd_full,
                    "min_weight": profile.min_weight,
                    "window_name": window_name,
                    "baseline_return_pct": baseline_metrics["total_return_pct"],
                    "base_pressure040_return_pct": base_metrics["total_return_pct"],
                    "candidate_return_pct": metrics["total_return_pct"],
                    "return_retention_pct": retention,
                    "baseline_max_dd_pct": baseline_metrics["max_dd_percent"],
                    "base_pressure040_max_dd_pct": base_metrics["max_dd_percent"],
                    "candidate_max_dd_pct": metrics["max_dd_percent"],
                    "candidate_sharpe": metrics["sharpe_ratio"],
                    "avg_weight": float(weights.mean()),
                    "min_realized_weight": float(weights.min()),
                    "strict_pass": int(metrics["max_dd_percent"] >= -30.0 and retention >= 80.0),
                    "research_pass": int(metrics["max_dd_percent"] >= -30.0 and retention >= 65.0),
                }
            )

    window_df = pd.DataFrame(rows)
    summary_rows: list[dict[str, Any]] = []
    for profile, group in window_df.groupby("profile", sort=False):
        positive = group[group["baseline_return_pct"] > 0]
        full = group[group["window_name"].eq(stage306.FULL_WINDOW)].iloc[0]
        summary_rows.append(
            {
                "profile": profile,
                "dd_start": float(full["dd_start"]),
                "dd_full": float(full["dd_full"]),
                "min_weight": float(full["min_weight"]),
                "positive_window_count": int(len(positive)),
                "strict_pass_count": int(positive["strict_pass"].sum()),
                "research_pass_count": int(positive["research_pass"].sum()),
                "min_return_retention_pct": float(positive["return_retention_pct"].min()) if not positive.empty else 0.0,
                "worst_max_dd_pct": float(positive["candidate_max_dd_pct"].min()) if not positive.empty else 0.0,
                "full_return_pct": float(full["candidate_return_pct"]),
                "full_return_retention_pct": float(full["return_retention_pct"]),
                "full_max_dd_pct": float(full["candidate_max_dd_pct"]),
                "full_sharpe": float(full["candidate_sharpe"]),
                "full_avg_weight": float(full["avg_weight"]),
                "full_min_realized_weight": float(full["min_realized_weight"]),
            }
        )
    summary_df = pd.DataFrame(summary_rows)
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
    strict_df = summary_df[summary_df["strict_all_windows"].eq(1)].copy()
    research_df = summary_df[summary_df["research_all_windows"].eq(1)].copy()
    lines = [
        "# Stage309 动态回撤门禁邻域敏感性",
        "",
        "## 目标",
        "",
        "- 只围绕 Stage308 最接近过线的动态回撤门禁做邻域敏感性检查。",
        "- 本阶段不是正式推广；如果只有孤立参数点过线，应视为不稳。",
        "- 粗粒度维度：回撤开始阈值、完全降权阈值、最低风险权重。",
        "",
        "## 严格候选",
        "",
    ]
    cols = [
        "profile",
        "dd_start",
        "dd_full",
        "min_weight",
        "strict_pass_count",
        "research_pass_count",
        "min_return_retention_pct",
        "worst_max_dd_pct",
        "full_return_pct",
        "full_return_retention_pct",
        "full_max_dd_pct",
        "full_sharpe",
        "full_avg_weight",
        "full_min_realized_weight",
    ]
    if strict_df.empty:
        lines.append("- 无严格多周期候选。")
    else:
        lines.append(strict_df[cols].head(30).to_markdown(index=False))

    lines.extend(["", "## 研究候选前20", ""])
    if research_df.empty:
        lines.append("- 无研究候选。")
    else:
        lines.append(research_df[cols].head(20).to_markdown(index=False))

    lines.extend(["", "## 最优候选窗口明细", ""])
    if not summary_df.empty:
        best = summary_df.iloc[0]
        detail = window_df[window_df["profile"].eq(best["profile"])][
            [
                "window_name",
                "baseline_return_pct",
                "base_pressure040_return_pct",
                "candidate_return_pct",
                "return_retention_pct",
                "baseline_max_dd_pct",
                "base_pressure040_max_dd_pct",
                "candidate_max_dd_pct",
                "avg_weight",
                "min_realized_weight",
                "strict_pass",
                "research_pass",
            ]
        ]
        lines.append(detail.to_markdown(index=False))

    lines.extend(["", "## 阶段判断", ""])
    if strict_df.empty:
        lines.append("- 未出现严格多周期候选；不应通过微调阈值强行宣布成功。")
    else:
        best = strict_df.iloc[0]
        lines.append(
            f"- 出现严格候选 `{best['profile']}`，最低收益保留 `{best['min_return_retention_pct']:.2f}%`，"
            f"最差回撤 `{best['worst_max_dd_pct']:.2f}%`。"
        )
        lines.append("- 仍需检查是否为邻域稳定，以及落回真实回测引擎。")
    return "\n".join(lines) + "\n"


def main() -> None:
    stage306.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    summary_df, window_df = _run_suite()

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
        "strict_all_count": int(summary_df["strict_all_windows"].sum()),
        "research_all_count": int(summary_df["research_all_windows"].sum()),
        "top": summary_df.head(10).to_dict(orient="records"),
        "paths": {
            "summary": str(summary_path),
            "windows": str(window_path),
            "report": str(report_path),
        },
    }
    decision_path.write_text(json.dumps(decision, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[stage309] summary={summary_path}")
    print(f"[stage309] windows={window_path}")
    print(f"[stage309] report={report_path}")
    print(f"[stage309] decision={decision_path}")
    print(report_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
