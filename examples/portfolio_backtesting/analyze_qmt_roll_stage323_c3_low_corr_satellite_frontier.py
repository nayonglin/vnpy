from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from run_qmt_alignment_backtest import OUTPUT_DIR


MODEL_TAG = "stage323_c3_low_corr_satellite_frontier_v1"
OUTPUT_PREFIX = "qmt_roll_stage323_c3_low_corr_satellite_frontier"
LINE_ID = "futures_trend_drawdown30_preserve_return"

BASE_CURVES_PATH = (
    OUTPUT_DIR
    / "qmt_roll_stage322_c3_conditional_heat_gate_validation_curves_"
    "stage322_c3_conditional_heat_gate_validation_v1.csv"
)

SATELLITE_PATH = (
    OUTPUT_DIR
    / "qmt_range_reversion_core4_directed_product_signal_back_adjusted_v8_two_stage_stop_daily.csv"
)

BASE_VARIANT = "C3_supply_headwind"
REFERENCE_VARIANT = "C_pressure040"
SATELLITE_NAME = "range_reversion_v8_two_stage_stop"

WINDOWS: tuple[str, ...] = (
    "full_2020_2026",
    "since_2022",
    "since_2023",
    "since_2024",
    "phase_2024_2025",
    "ytd_2026",
)

# 粗粒度组合权重，不做小数救援。
BASE_WEIGHTS: tuple[float, ...] = (0.80, 0.825, 0.85, 0.875, 0.90, 0.925, 0.95, 0.975)


def _path_metrics(nav: pd.Series) -> dict[str, float]:
    nav = nav.dropna()
    if nav.empty:
        return {
            "total_return_pct": 0.0,
            "max_dd_percent": 0.0,
            "sharpe_ratio": 0.0,
        }
    arr = nav.to_numpy(dtype=float)
    high = np.maximum.accumulate(arr)
    drawdown_pct = np.divide(arr - high, high, out=np.zeros_like(arr), where=high != 0) * 100.0
    returns = pd.Series(arr, index=nav.index).pct_change().fillna(0.0).to_numpy(dtype=float)
    std = float(np.std(returns, ddof=1)) if len(returns) > 1 else 0.0
    sharpe = float(np.mean(returns) / std * np.sqrt(252)) if std > 0 else 0.0
    return {
        "total_return_pct": float((arr[-1] - 1.0) * 100.0),
        "max_dd_percent": float(drawdown_pct.min()),
        "sharpe_ratio": sharpe,
    }


def _load_stage322_curves() -> pd.DataFrame:
    df = pd.read_csv(BASE_CURVES_PATH)
    df["date"] = pd.to_datetime(df["date"])
    return df[df["window_name"].isin(WINDOWS)].copy()


def _nav_from_stage322(df: pd.DataFrame, variant: str, window_name: str) -> pd.Series:
    part = df[df["variant"].eq(variant) & df["window_name"].eq(window_name)].sort_values("date")
    if part.empty:
        return pd.Series(dtype=float)
    nav = pd.Series(part["balance"].to_numpy(dtype=float), index=pd.to_datetime(part["date"]))
    return nav / float(nav.iloc[0])


def _load_satellite() -> pd.Series:
    df = pd.read_csv(SATELLITE_PATH)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["balance"] = pd.to_numeric(df["balance"], errors="coerce")
    df = df.dropna(subset=["date", "balance"]).sort_values("date").drop_duplicates("date", keep="last")
    if df.empty:
        raise RuntimeError(f"satellite curve is empty: {SATELLITE_PATH}")
    nav = pd.Series(df["balance"].to_numpy(dtype=float), index=pd.to_datetime(df["date"]))
    return nav / float(nav.iloc[0])


def _satellite_for_base_index(satellite_nav: pd.Series, base_index: pd.DatetimeIndex) -> pd.Series:
    aligned = satellite_nav.reindex(base_index).ffill().fillna(1.0)
    first = float(aligned.iloc[0])
    if first == 0:
        return aligned
    return aligned / first


def _retention(candidate_return: float, base_return: float) -> float:
    if base_return <= 0:
        return 0.0
    return candidate_return / base_return * 100.0


def _weight_label(base_weight: float) -> str:
    return f"c3{base_weight:.3f}_sat{1.0 - base_weight:.3f}"


def _run_frontier() -> tuple[pd.DataFrame, pd.DataFrame]:
    curves = _load_stage322_curves()
    satellite_full = _load_satellite()
    window_rows: list[dict[str, Any]] = []

    for window_name in WINDOWS:
        c3_nav = _nav_from_stage322(curves, BASE_VARIANT, window_name)
        ref_nav = _nav_from_stage322(curves, REFERENCE_VARIANT, window_name)
        if c3_nav.empty or ref_nav.empty:
            continue
        sat_nav = _satellite_for_base_index(satellite_full, c3_nav.index)
        c3_metrics = _path_metrics(c3_nav)
        ref_metrics = _path_metrics(ref_nav)
        sat_metrics = _path_metrics(sat_nav)
        corr_c3_sat = float(c3_nav.pct_change().fillna(0.0).corr(sat_nav.pct_change().fillna(0.0)))
        for base_weight in BASE_WEIGHTS:
            combo_nav = (base_weight * c3_nav + (1.0 - base_weight) * sat_nav).dropna()
            metrics = _path_metrics(combo_nav)
            retention_vs_c3 = _retention(metrics["total_return_pct"], c3_metrics["total_return_pct"])
            retention_vs_ref = _retention(metrics["total_return_pct"], ref_metrics["total_return_pct"])
            dd_ok = metrics["max_dd_percent"] >= -30.0
            positive_window = c3_metrics["total_return_pct"] > 0 and ref_metrics["total_return_pct"] > 0
            window_rows.append(
                {
                    "window_name": window_name,
                    "candidate": SATELLITE_NAME,
                    "weight_label": _weight_label(base_weight),
                    "c3_weight": base_weight,
                    "satellite_weight": 1.0 - base_weight,
                    "c3_return_pct": c3_metrics["total_return_pct"],
                    "reference_return_pct": ref_metrics["total_return_pct"],
                    "satellite_return_pct": sat_metrics["total_return_pct"],
                    "combo_return_pct": metrics["total_return_pct"],
                    "return_retention_vs_c3_pct": retention_vs_c3,
                    "return_retention_vs_reference_pct": retention_vs_ref,
                    "c3_max_dd_pct": c3_metrics["max_dd_percent"],
                    "reference_max_dd_pct": ref_metrics["max_dd_percent"],
                    "satellite_max_dd_pct": sat_metrics["max_dd_percent"],
                    "combo_max_dd_pct": metrics["max_dd_percent"],
                    "combo_sharpe": metrics["sharpe_ratio"],
                    "corr_c3_satellite": corr_c3_sat,
                    "positive_window": int(positive_window),
                    "c3_objective_pass": int(dd_ok and retention_vs_c3 >= 80.0),
                    "strict_pass": int(dd_ok and retention_vs_c3 >= 80.0 and retention_vs_ref >= 100.0),
                    "research_pass": int(dd_ok and retention_vs_c3 >= 75.0 and retention_vs_ref >= 95.0),
                }
            )

    window_df = pd.DataFrame(window_rows)
    summary_rows: list[dict[str, Any]] = []
    for weight_label, group in window_df.groupby("weight_label", sort=False):
        positive = group[group["positive_window"].eq(1)]
        full = group[group["window_name"].eq("full_2020_2026")].iloc[0]
        summary_rows.append(
            {
                "candidate": SATELLITE_NAME,
                "weight_label": weight_label,
                "c3_weight": float(full["c3_weight"]),
                "satellite_weight": float(full["satellite_weight"]),
                "positive_window_count": int(len(positive)),
                "c3_objective_pass_count": int(positive["c3_objective_pass"].sum()),
                "strict_pass_count": int(positive["strict_pass"].sum()),
                "research_pass_count": int(positive["research_pass"].sum()),
                "min_return_retention_vs_c3_pct": float(positive["return_retention_vs_c3_pct"].min()),
                "min_return_retention_vs_reference_pct": float(positive["return_retention_vs_reference_pct"].min()),
                "worst_max_dd_pct": float(positive["combo_max_dd_pct"].min()),
                "full_return_pct": float(full["combo_return_pct"]),
                "full_return_retention_vs_c3_pct": float(full["return_retention_vs_c3_pct"]),
                "full_return_retention_vs_reference_pct": float(full["return_retention_vs_reference_pct"]),
                "full_max_dd_pct": float(full["combo_max_dd_pct"]),
                "full_sharpe": float(full["combo_sharpe"]),
                "median_corr_c3_satellite": float(positive["corr_c3_satellite"].median()),
            }
        )

    summary_df = pd.DataFrame(summary_rows)
    if not summary_df.empty:
        summary_df["strict_all_windows"] = (
            summary_df["strict_pass_count"].eq(summary_df["positive_window_count"])
            & summary_df["min_return_retention_vs_c3_pct"].ge(80.0)
            & summary_df["min_return_retention_vs_reference_pct"].ge(100.0)
            & summary_df["worst_max_dd_pct"].ge(-30.0)
        ).astype(int)
        summary_df["research_all_windows"] = (
            summary_df["research_pass_count"].eq(summary_df["positive_window_count"])
            & summary_df["min_return_retention_vs_c3_pct"].ge(75.0)
            & summary_df["min_return_retention_vs_reference_pct"].ge(95.0)
            & summary_df["worst_max_dd_pct"].ge(-30.0)
        ).astype(int)
        summary_df["c3_objective_all_windows"] = (
            summary_df["c3_objective_pass_count"].eq(summary_df["positive_window_count"])
            & summary_df["min_return_retention_vs_c3_pct"].ge(80.0)
            & summary_df["worst_max_dd_pct"].ge(-30.0)
        ).astype(int)
        summary_df = summary_df.sort_values(
            [
                "strict_all_windows",
                "research_all_windows",
                "c3_objective_all_windows",
                "min_return_retention_vs_c3_pct",
                "worst_max_dd_pct",
                "full_return_retention_vs_c3_pct",
            ],
            ascending=[False, False, False, False, False, False],
        )
    return summary_df, window_df


def _build_report(summary_df: pd.DataFrame, window_df: pd.DataFrame) -> str:
    lines = [
        "# Stage323 C3叠加低相关卫星组合前沿",
        "",
        "## 目标",
        "",
        "- 底座使用 Stage018/322 的 `C3_supply_headwind`。",
        "- 卫星只使用 Stage307 已经识别出的最佳低相关腿，不重新海选。",
        "- 只扫描粗粒度组合权重，目标是全样本和多周期最大回撤进入30以内，同时尽量保留 C3 收益。",
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
            "c3_objective_all_windows",
            "strict_all_windows",
            "research_all_windows",
            "c3_objective_pass_count",
            "strict_pass_count",
            "research_pass_count",
            "min_return_retention_vs_c3_pct",
            "min_return_retention_vs_reference_pct",
            "worst_max_dd_pct",
            "full_return_pct",
            "full_return_retention_vs_c3_pct",
            "full_return_retention_vs_reference_pct",
            "full_max_dd_pct",
            "full_sharpe",
            "median_corr_c3_satellite",
        ]
        lines.append(summary_df[cols].to_markdown(index=False))

    lines.extend(["", "## 最优候选窗口明细", ""])
    if not summary_df.empty:
        best = summary_df.iloc[0]
        detail = window_df[window_df["weight_label"].eq(best["weight_label"])][
            [
                "window_name",
                "c3_return_pct",
                "reference_return_pct",
                "combo_return_pct",
                "return_retention_vs_c3_pct",
                "return_retention_vs_reference_pct",
                "c3_max_dd_pct",
                "reference_max_dd_pct",
                "combo_max_dd_pct",
                "combo_sharpe",
                "c3_objective_pass",
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
                f"- 找到严格多周期候选：`{best['weight_label']}`，"
                f"最低C3收益保留 `{best['min_return_retention_vs_c3_pct']:.2f}%`，"
                f"最差回撤 `{best['worst_max_dd_pct']:.2f}%`。"
            )
        elif int(best["research_all_windows"]) == 1:
            lines.append(
                f"- 找到研究级候选：`{best['weight_label']}`，"
                f"最低C3收益保留 `{best['min_return_retention_vs_c3_pct']:.2f}%`，"
                f"最差回撤 `{best['worst_max_dd_pct']:.2f}%`。"
            )
            lines.append("- 仍需真实组合资金/保证金约束验证，不能直接合入。")
        elif int(best["c3_objective_all_windows"]) == 1:
            lines.append(
                f"- 找到 C3 目标研究候选：`{best['weight_label']}`，"
                f"最低C3收益保留 `{best['min_return_retention_vs_c3_pct']:.2f}%`，"
                f"最差回撤 `{best['worst_max_dd_pct']:.2f}%`。"
            )
            lines.append(
                "- 但它没有通过相对 `C_pressure040` 的跨窗口收益保留闸门，尤其近端窗口收益偏低，"
                "因此只能作为研究候选，不能直接合入正式第78-1。"
            )
        else:
            lines.append("- 未找到多周期同时满足回撤和收益保留的候选。")
    return "\n".join(lines) + "\n"


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    summary_df, window_df = _run_frontier()

    summary_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
    window_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_windows_{MODEL_TAG}.csv"
    report_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
    decision_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

    summary_df.to_csv(summary_path, index=False, encoding="utf-8-sig")
    window_df.to_csv(window_path, index=False, encoding="utf-8-sig")
    report_path.write_text(_build_report(summary_df, window_df), encoding="utf-8")

    decision = {
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "base_variant": BASE_VARIANT,
        "reference_variant": REFERENCE_VARIANT,
        "satellite": SATELLITE_NAME,
        "base_weights": list(BASE_WEIGHTS),
        "strict_all_count": int(summary_df["strict_all_windows"].sum()) if not summary_df.empty else 0,
        "research_all_count": int(summary_df["research_all_windows"].sum()) if not summary_df.empty else 0,
        "c3_objective_all_count": int(summary_df["c3_objective_all_windows"].sum()) if not summary_df.empty else 0,
        "top": summary_df.head(5).to_dict(orient="records"),
        "paths": {
            "summary": str(summary_path),
            "windows": str(window_path),
            "report": str(report_path),
        },
    }
    decision_path.write_text(json.dumps(decision, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[stage323] summary={summary_path}")
    print(f"[stage323] windows={window_path}")
    print(f"[stage323] report={report_path}")
    print(f"[stage323] decision={decision_path}")
    print(report_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
