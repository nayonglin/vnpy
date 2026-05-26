from __future__ import annotations

import json
import math
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd

from run_qmt_alignment_backtest import OUTPUT_DIR


MODEL_TAG = "stage338_low_corr_satellite_route_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage338_low_corr_satellite_route_audit"
LINE_ID = "futures_trend_drawdown30_preserve_return"

STAGE306_CANDIDATES = OUTPUT_DIR / "qmt_roll_stage306_low_corr_satellite_scout_candidate_scout_stage306_low_corr_satellite_scout_v1.csv"
STAGE307_FRONTIER = OUTPUT_DIR / "qmt_roll_stage307_low_corr_weight_frontier_summary_stage307_low_corr_weight_frontier_v1.csv"
STAGE325_TRUE_CAPITAL = OUTPUT_DIR / "qmt_roll_stage325_true_capital_split_frontier_summary_stage325_true_capital_split_frontier_v1.csv"
STAGE326_MULTIPERIOD = OUTPUT_DIR / "qmt_roll_stage326_c3_350_sat150_multiperiod_pressure_summary_stage326_c3_350_sat150_multiperiod_pressure_v1.csv"
STAGE326_SLIPPAGE = OUTPUT_DIR / "qmt_roll_stage326_c3_350_sat150_multiperiod_pressure_slippage_stress_stage326_c3_350_sat150_multiperiod_pressure_v1.csv"


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if math.isinf(result) or pd.isna(result):
        return default
    return result


def _to_builtin(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _to_builtin(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_to_builtin(item) for item in value]
    if isinstance(value, tuple):
        return [_to_builtin(item) for item in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    return value


def _to_markdown_table(df: pd.DataFrame, columns: list[str] | None = None, max_rows: int = 30) -> str:
    if df.empty:
        return "_empty_"
    view = df[columns].copy() if columns else df.copy()
    view = view.head(max_rows)
    for column in view.columns:
        if pd.api.types.is_float_dtype(view[column]):
            view[column] = view[column].map(lambda value: f"{value:.4f}")
    header = "| " + " | ".join(view.columns) + " |"
    separator = "| " + " | ".join(["---"] * len(view.columns)) + " |"
    rows = ["| " + " | ".join(map(str, row)) + " |" for row in view.to_numpy()]
    return "\n".join([header, separator, *rows])


def _load_csv(path: Any) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path)


def _candidate_quality(candidates: pd.DataFrame) -> pd.DataFrame:
    frame = candidates.copy()
    frame["is_duplicate_equity"] = frame["candidate"].str.endswith("_equity").astype(int)
    frame = frame[frame["is_duplicate_equity"].eq(0)].copy()
    top30 = frame.sort_values(
        ["combo_full_strict_pass", "combo_max_dd_pct", "combo_return_retention_pct"],
        ascending=[False, False, False],
    ).head(30)
    return pd.DataFrame(
        [
            {
                "scope": "top30_non_equity_duplicate",
                "candidate_count": int(len(top30)),
                "positive_sat_return_count": int((top30["sat_total_return_pct"] > 0).sum()),
                "negative_sat_return_count": int((top30["sat_total_return_pct"] < 0).sum()),
                "max_sat_return_pct": float(top30["sat_total_return_pct"].max()),
                "median_sat_return_pct": float(top30["sat_total_return_pct"].median()),
                "max_sat_dd_pct": float(top30["sat_max_dd_pct"].min()),
                "median_corr_full": float(top30["corr_full"].median()),
                "median_combo_retention_pct": float(top30["combo_return_retention_pct"].median()),
                "median_combo_dd_pct": float(top30["combo_max_dd_pct"].median()),
            }
        ]
    )


def _route_summary(
    stage307: pd.DataFrame,
    stage325: pd.DataFrame,
    stage326: pd.DataFrame,
    slippage: pd.DataFrame,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    nav_best = stage307.sort_values(
        ["research_all_windows", "strict_pass_count", "full_return_pct"],
        ascending=[False, False, False],
    ).iloc[0]
    rows.append(
        {
            "check_layer": "净值层低相关卫星",
            "candidate": str(nav_best["candidate"]),
            "key_config": str(nav_best["weight_label"]),
            "return_pct": _safe_float(nav_best["full_return_pct"]),
            "max_dd_pct": _safe_float(nav_best["full_max_dd_pct"]),
            "retention_pct": _safe_float(nav_best["full_return_retention_pct"]),
            "pass_count": f"{int(nav_best['strict_pass_count'])}/{int(nav_best['positive_window_count'])}",
            "main_failure": "最低收益保留仅约71%，未过80%硬标准",
            "decision": "research_only",
        }
    )

    full_candidates = stage325[
        stage325["dd_lt_30_ok"].eq(1) & stage325["retention_vs_c3_500_ge_80_ok"].eq(1)
    ].copy()
    if not full_candidates.empty:
        true_best = full_candidates.sort_values("combo_return_pct", ascending=False).iloc[0]
    else:
        true_best = stage325.sort_values(["combo_max_dd_pct", "combo_return_pct"], ascending=[False, False]).iloc[0]
    rows.append(
        {
            "check_layer": "真实资金全样本",
            "candidate": str(true_best["split_name"]),
            "key_config": f"C3 {true_best['c3_capital']:.0f} / 卫星 {true_best['satellite_capital']:.0f}",
            "return_pct": _safe_float(true_best["combo_return_pct"]),
            "max_dd_pct": _safe_float(true_best["combo_max_dd_pct"]),
            "retention_pct": _safe_float(true_best["return_retention_vs_c3_500_pct"]),
            "pass_count": f"full={int(true_best['dd_lt_30_ok'])}/{int(true_best['retention_vs_c3_500_ge_80_ok'])}",
            "main_failure": "全样本通过但保证金复核天数较多，且需多周期复验",
            "decision": "needs_oos",
        }
    )

    positive_windows = stage326[pd.to_numeric(stage326["c3_500_return_pct"], errors="coerce") > 0].copy()
    window_ok = int(stage326["window_gate_ok"].fillna(0).astype(int).sum())
    positive_ok = int(positive_windows["window_gate_ok"].fillna(0).astype(int).sum())
    min_retention = float(positive_windows["return_retention_vs_c3_500_pct"].min()) if not positive_windows.empty else math.nan
    worst_dd = float(stage326["combo_max_dd_pct"].min()) if not stage326.empty else math.nan
    full_row = stage326[stage326["window_name"].eq("start_2020")].iloc[0]
    rows.append(
        {
            "check_layer": "真实资金多周期",
            "candidate": "c3_350_sat_150",
            "key_config": "C3 350000 / 卫星 150000",
            "return_pct": _safe_float(full_row["combo_return_pct"]),
            "max_dd_pct": _safe_float(full_row["combo_max_dd_pct"]),
            "retention_pct": _safe_float(full_row["return_retention_vs_c3_500_pct"]),
            "pass_count": f"{window_ok}/{len(stage326)}；正收益窗口{positive_ok}/{len(positive_windows)}",
            "main_failure": f"正收益窗口最低收益保留{min_retention:.2f}%，最差回撤{worst_dd:.2f}%",
            "decision": "fail",
        }
    )

    stress_ok = int(slippage["stress_gate_ok"].fillna(0).astype(int).sum())
    stress_2x = slippage[slippage["slippage_multiplier"].eq(2.0)].iloc[0]
    rows.append(
        {
            "check_layer": "滑点压力",
            "candidate": "c3_350_sat_150",
            "key_config": "1x/2x/3x/5x",
            "return_pct": _safe_float(stress_2x["combo_return_pct"]),
            "max_dd_pct": _safe_float(stress_2x["combo_max_dd_pct"]),
            "retention_pct": _safe_float(stress_2x["return_retention_vs_c3_500_pct"]),
            "pass_count": f"{stress_ok}/{len(slippage)}",
            "main_failure": "2x滑点最大回撤已跌破30%闸门",
            "decision": "fail",
        }
    )
    return pd.DataFrame(rows)


def _top_candidates(stage307: pd.DataFrame, candidates: pd.DataFrame) -> pd.DataFrame:
    stage307_view = stage307[~stage307["candidate"].str.endswith("_equity")].copy()
    scout_view = candidates[~candidates["candidate"].str.endswith("_equity")].copy()
    merged = stage307_view.merge(
        scout_view[["candidate", "sat_total_return_pct", "sat_max_dd_pct", "corr_full", "corr_2022_dd"]],
        on="candidate",
        how="left",
    )
    return merged.sort_values(
        ["research_all_windows", "strict_pass_count", "full_return_pct"],
        ascending=[False, False, False],
    ).head(12)


def _build_report(route: pd.DataFrame, quality: pd.DataFrame, top: pd.DataFrame) -> str:
    q = quality.iloc[0]
    lines = [
        "# Stage338 低相关卫星路线审计",
        "",
        "## 目标",
        "",
        "- 汇总 Stage306/307/325/326 的低相关卫星结果，判断当前旧卫星集合是否还值得继续深挖。",
        "- 不新增策略参数，不重新扫权重；只做路线层证据整理。",
        "",
        "## 路线证据链",
        "",
        _to_markdown_table(
            route,
            [
                "check_layer",
                "candidate",
                "key_config",
                "return_pct",
                "max_dd_pct",
                "retention_pct",
                "pass_count",
                "main_failure",
                "decision",
            ],
            max_rows=20,
        ),
        "",
        "## 当前卫星集合质量",
        "",
        _to_markdown_table(quality, max_rows=10),
        "",
        "## 前排候选画像",
        "",
        _to_markdown_table(
            top,
            [
                "candidate",
                "weight_label",
                "full_return_pct",
                "full_max_dd_pct",
                "min_return_retention_pct",
                "sat_total_return_pct",
                "sat_max_dd_pct",
                "corr_full",
            ],
            max_rows=12,
        ),
        "",
        "## 阶段判断",
        "",
        f"- 前30个非重复卫星里，卫星自身正收益候选 `{int(q['positive_sat_return_count'])}` 个，负收益候选 `{int(q['negative_sat_return_count'])}` 个；卫星自身最高收益只有 `{q['max_sat_return_pct']:.4f}%`，中位收益 `{q['median_sat_return_pct']:.4f}%`。",
        "- 这些卫星对组合回撤有帮助，但主要像低波动现金替代；在真实资金、多周期和滑点压力下，没有稳定通过。",
        "- 结论：当前这批旧震荡/反转/无影线卫星不再作为主路径继续扫权重。若继续低相关路线，必须寻找更高收益、可用真实资金交易、与C3弱窗口错开的独立策略。",
        "",
        "## 过拟合反思",
        "",
        "- 本阶段只是汇总既有冻结结果，不新增参数；过拟合风险低。",
        "- 若继续在当前卫星集合里微调权重、筛候选名次或只看全样本，很容易把现金稀释误判为有效alpha。",
        "",
        "## 继续价值反思",
        "",
        "- 低相关组合仍有价值，但当前旧卫星集合价值下降；下一步应换收益源，而不是继续围绕 v8 或 BOLL 近邻版本微调。",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    candidates = _load_csv(STAGE306_CANDIDATES)
    stage307 = _load_csv(STAGE307_FRONTIER)
    stage325 = _load_csv(STAGE325_TRUE_CAPITAL)
    stage326 = _load_csv(STAGE326_MULTIPERIOD)
    slippage = _load_csv(STAGE326_SLIPPAGE)

    quality = _candidate_quality(candidates)
    route = _route_summary(stage307, stage325, stage326, slippage)
    top = _top_candidates(stage307, candidates)
    report = _build_report(route, quality, top)

    route_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_route_summary_{MODEL_TAG}.csv"
    quality_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_candidate_quality_{MODEL_TAG}.csv"
    top_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_top_candidates_{MODEL_TAG}.csv"
    report_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
    decision_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

    route.to_csv(route_path, index=False, encoding="utf-8-sig")
    quality.to_csv(quality_path, index=False, encoding="utf-8-sig")
    top.to_csv(top_path, index=False, encoding="utf-8-sig")
    report_path.write_text(report, encoding="utf-8")
    decision = {
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "decision": "stop_current_low_return_satellite_set_as_primary_route",
        "paths": {
            "route_summary": str(route_path),
            "candidate_quality": str(quality_path),
            "top_candidates": str(top_path),
            "report": str(report_path),
        },
    }
    decision_path.write_text(json.dumps(_to_builtin(decision), ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[stage338] route_summary={route_path}")
    print(f"[stage338] candidate_quality={quality_path}")
    print(f"[stage338] top_candidates={top_path}")
    print(f"[stage338] report={report_path}")
    print(f"[stage338] decision={decision_path}")
    print(report)


if __name__ == "__main__":
    main()
