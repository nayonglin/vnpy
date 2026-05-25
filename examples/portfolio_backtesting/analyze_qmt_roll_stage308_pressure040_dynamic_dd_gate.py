from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

import analyze_qmt_roll_stage306_low_corr_satellite_scout as stage306


MODEL_TAG = "stage308_pressure040_dynamic_dd_gate_v1"
OUTPUT_PREFIX = "qmt_roll_stage308_pressure040_dynamic_dd_gate"
LINE_ID = "futures_trend_drawdown30_preserve_return"


@dataclass(frozen=True)
class Profile:
    name: str
    dd_start: float
    dd_full: float
    min_weight: float


PROFILES: tuple[Profile, ...] = (
    Profile("base_no_overlay", 0.99, 1.00, 1.00),
    Profile("dd12_28_min80", 0.12, 0.28, 0.80),
    Profile("dd12_30_min80", 0.12, 0.30, 0.80),
    Profile("dd12_34_min80", 0.12, 0.34, 0.80),
    Profile("dd16_28_min80", 0.16, 0.28, 0.80),
    Profile("dd16_30_min80", 0.16, 0.30, 0.80),
    Profile("dd16_34_min80", 0.16, 0.34, 0.80),
    Profile("dd20_28_min80", 0.20, 0.28, 0.80),
    Profile("dd20_30_min80", 0.20, 0.30, 0.80),
    Profile("dd20_34_min80", 0.20, 0.34, 0.80),
    Profile("dd12_28_min90", 0.12, 0.28, 0.90),
    Profile("dd12_30_min90", 0.12, 0.30, 0.90),
    Profile("dd12_34_min90", 0.12, 0.34, 0.90),
    Profile("dd16_28_min90", 0.16, 0.28, 0.90),
    Profile("dd16_30_min90", 0.16, 0.30, 0.90),
    Profile("dd16_34_min90", 0.16, 0.34, 0.90),
    Profile("dd20_28_min90", 0.20, 0.28, 0.90),
    Profile("dd20_30_min90", 0.20, 0.30, 0.90),
    Profile("dd20_34_min90", 0.20, 0.34, 0.90),
    Profile("dd12_28_min95", 0.12, 0.28, 0.95),
    Profile("dd12_30_min95", 0.12, 0.30, 0.95),
    Profile("dd12_34_min95", 0.12, 0.34, 0.95),
    Profile("dd16_28_min95", 0.16, 0.28, 0.95),
    Profile("dd16_30_min95", 0.16, 0.30, 0.95),
    Profile("dd16_34_min95", 0.16, 0.34, 0.95),
    Profile("dd20_28_min95", 0.20, 0.28, 0.95),
    Profile("dd20_30_min95", 0.20, 0.30, 0.95),
    Profile("dd20_34_min95", 0.20, 0.34, 0.95),
)


def _profile_weight(drawdown: float, profile: Profile) -> float:
    drawdown = max(0.0, float(drawdown))
    if drawdown <= profile.dd_start:
        return 1.0
    if drawdown >= profile.dd_full:
        return profile.min_weight
    span = max(1e-9, profile.dd_full - profile.dd_start)
    ratio = (profile.dd_full - drawdown) / span
    return profile.min_weight + (1.0 - profile.min_weight) * ratio


def _simulate_dynamic_gate(base_window_nav: pd.Series, profile: Profile) -> pd.DataFrame:
    base_window_nav = base_window_nav.dropna()
    if base_window_nav.empty:
        return pd.DataFrame()
    base_return = base_window_nav.pct_change().fillna(0.0)
    equity = 1.0
    high = 1.0
    rows: list[dict[str, Any]] = []
    for date, ret in base_return.items():
        prior_high = max(high, equity)
        prior_dd = max(0.0, 1.0 - equity / prior_high) if prior_high > 0 else 0.0
        weight = _profile_weight(prior_dd, profile)
        overlay_return = float(ret) * weight
        equity = equity * (1.0 + overlay_return)
        high = max(high, equity)
        rows.append(
            {
                "date": date,
                "base_return": float(ret),
                "overlay_return": overlay_return,
                "weight": weight,
                "prior_drawdown_pct": prior_dd * 100.0,
                "nav": equity,
                "drawdown_pct": (equity / high - 1.0) * 100.0 if high > 0 else 0.0,
            }
        )
    return pd.DataFrame(rows)


def _metrics_from_returns(nav: pd.Series, daily_return: pd.Series) -> dict[str, float]:
    path_metrics = stage306._path_metrics(nav)
    ret = pd.to_numeric(daily_return, errors="coerce").fillna(0.0).to_numpy(dtype=float)
    std = float(np.std(ret, ddof=1)) if len(ret) > 1 else 0.0
    path_metrics["sharpe_ratio"] = float(np.mean(ret) / std * np.sqrt(252)) if std > 0 else 0.0
    return path_metrics


def _run_suite() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    baseline_nav, base_nav = stage306._load_base_curves()
    window_rows: list[dict[str, Any]] = []
    curve_frames: list[pd.DataFrame] = []

    for profile in PROFILES:
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
            window_rows.append(
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
            curve_out = curve.copy()
            curve_out["profile"] = profile.name
            curve_out["window_name"] = window_name
            curve_frames.append(curve_out)

    window_df = pd.DataFrame(window_rows)
    summary_rows: list[dict[str, Any]] = []
    for profile, group in window_df.groupby("profile", sort=False):
        positive = group[group["baseline_return_pct"] > 0]
        full = group[group["window_name"].eq(stage306.FULL_WINDOW)].iloc[0]
        summary_rows.append(
            {
                "profile": profile,
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
    curves_df = pd.concat(curve_frames, ignore_index=True) if curve_frames else pd.DataFrame()
    return summary_df, window_df, curves_df


def _build_report(summary_df: pd.DataFrame, window_df: pd.DataFrame) -> str:
    lines = [
        "# Stage308 C_pressure040 动态回撤门禁",
        "",
        "## 目标",
        "",
        "- 底座：Stage007/Stage306 使用的 `C_full_delev_pressure040`。",
        "- 覆盖层：只根据上一日覆盖层权益回撤决定下一日风险权重。",
        "- 不使用未来收益，不改78-1入场逻辑、AI池、品种池或止盈止损。",
        "- 这是日收益层边界实验；若出现候选，必须再落回真实回测引擎。",
        "",
        "## 排名前20",
        "",
    ]
    cols = [
        "profile",
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
        "full_avg_weight",
        "full_min_realized_weight",
    ]
    if summary_df.empty:
        lines.append("- 无结果。")
    else:
        lines.append(summary_df[cols].head(20).to_markdown(index=False))

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
    if summary_df.empty:
        lines.append("- 未找到候选。")
    else:
        best = summary_df.iloc[0]
        if int(best["strict_all_windows"]) == 1:
            lines.append(
                f"- 找到严格候选 `{best['profile']}`：多周期回撤均小于30%，最低收益保留 `{best['min_return_retention_pct']:.2f}%`。"
            )
        elif int(best["research_all_windows"]) == 1:
            lines.append(
                f"- 只有研究级候选 `{best['profile']}`：最低收益保留 `{best['min_return_retention_pct']:.2f}%`，"
                f"最差回撤 `{best['worst_max_dd_pct']:.2f}%`。"
            )
        else:
            lines.append("- 未找到多周期候选。")
    return "\n".join(lines) + "\n"


def main() -> None:
    stage306.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    summary_df, window_df, curves_df = _run_suite()

    summary_path = stage306.OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
    window_path = stage306.OUTPUT_DIR / f"{OUTPUT_PREFIX}_windows_{MODEL_TAG}.csv"
    curves_path = stage306.OUTPUT_DIR / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv"
    report_path = stage306.OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
    decision_path = stage306.OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

    summary_df.to_csv(summary_path, index=False, encoding="utf-8-sig")
    window_df.to_csv(window_path, index=False, encoding="utf-8-sig")
    curves_df.to_csv(curves_path, index=False, encoding="utf-8-sig")
    report_path.write_text(_build_report(summary_df, window_df), encoding="utf-8")

    decision = {
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "base_variant": stage306.BASE_VARIANT,
        "profile_count": int(len(PROFILES)),
        "strict_all_count": int(summary_df["strict_all_windows"].sum()) if not summary_df.empty else 0,
        "research_all_count": int(summary_df["research_all_windows"].sum()) if not summary_df.empty else 0,
        "top": summary_df.head(10).to_dict(orient="records"),
        "paths": {
            "summary": str(summary_path),
            "windows": str(window_path),
            "curves": str(curves_path),
            "report": str(report_path),
        },
    }
    decision_path.write_text(json.dumps(decision, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[stage308] summary={summary_path}")
    print(f"[stage308] windows={window_path}")
    print(f"[stage308] curves={curves_path}")
    print(f"[stage308] report={report_path}")
    print(f"[stage308] decision={decision_path}")
    print(report_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
