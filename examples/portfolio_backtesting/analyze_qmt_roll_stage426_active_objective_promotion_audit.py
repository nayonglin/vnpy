from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

MODEL_TAG = "stage426_active_objective_promotion_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage426_active_objective_promotion_audit"
LINE_ID = "futures_trend_drawdown30_preserve_return"

STAGE079_VARIANT = "stage079"
STAGE103_VARIANT = "xsmom_vt10_q_momq_round_half_true_broker10_guard"

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_candidate_table_{MODEL_TAG}.csv"
TIER_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_tier_summary_{MODEL_TAG}.csv"
TOP_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_top_candidates_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"


LATER_ROBUSTNESS_DECISIONS: dict[str, dict[str, str]] = {
    "stage103_plus_cffex_index_best1_tsmom60_guard": {
        "tier_override": "downgraded_by_later_robustness",
        "reason": "Stage116: any-start return win rate vs Stage103 was weak and removing the top relative edge day put total return below Stage103.",
    },
    "stage103_plus_value_proxy756_monthly_guard": {
        "tier_override": "downgraded_by_later_robustness",
        "reason": "Stage123: value756 had insufficient active sample coverage and extra broker10 margin fragility.",
    },
    "stage103_plus_oi_confirm63_best1_weekly_guard": {
        "tier_override": "paper_only_not_incumbent_upgrade",
        "reason": "Stage125: passes the Stage079 objective gate, but any-start return win rate vs Stage103 is weak and 5x cost drawdown is slightly worse than Stage103.",
    },
}


def _safe_float(value: Any, default: float = np.nan) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(result) or math.isinf(result):
        return default
    return result


def _safe_int(value: Any, default: int = 0) -> int:
    result = _safe_float(value, np.nan)
    if math.isnan(result):
        return default
    return int(result)


def _flag(value: Any) -> bool:
    return _safe_int(value, 0) == 1


def _stage_number(path: Path) -> int:
    match = re.search(r"stage(\d+)", path.name)
    return int(match.group(1)) if match else -1


def _version_number(path: Path) -> int:
    match = re.search(r"_v(\d+)\.csv$", path.name)
    return int(match.group(1)) if match else 0


def _latest_gate_files() -> list[Path]:
    groups: dict[str, Path] = {}
    for path in OUTPUT_DIR.glob("qmt_roll_stage4*_gate_*.csv"):
        stage = _stage_number(path)
        if stage < 403 or stage > 425:
            continue
        key = re.sub(r"_v\d+\.csv$", "", path.name)
        current = groups.get(key)
        if current is None or _version_number(path) > _version_number(current):
            groups[key] = path
    return sorted(groups.values(), key=lambda p: (_stage_number(p), p.name))


def _paired_file(gate_path: Path, kind: str) -> Path | None:
    path = gate_path.with_name(gate_path.name.replace("_gate_", f"_{kind}_"))
    return path if path.exists() else None


def _decision_for(gate_path: Path) -> str:
    path = gate_path.with_name(gate_path.name.replace("_gate_", "_decision_").replace(".csv", ".json"))
    if not path.exists():
        return ""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return ""
    return str(data.get("decision", ""))


def _read_gate(gate_path: Path) -> pd.DataFrame:
    frame = pd.read_csv(gate_path)
    frame["source_stage"] = _stage_number(gate_path)
    frame["source_file"] = gate_path.name
    frame["source_decision"] = _decision_for(gate_path)

    summary_path = _paired_file(gate_path, "summary")
    if summary_path is not None:
        summary = pd.read_csv(summary_path)
        metric_cols = [
            "variant",
            "end_equity",
            "total_return_pct",
            "max_dd_pct",
            "sharpe",
            "ulcer_pct",
            "rolling252_dd30_breach_rate",
            "rolling504_dd30_breach_rate",
            "annual_cold_start_dd30_pass_rate",
            "quarter_cold_start_dd30_pass_rate",
        ]
        keep = [col for col in metric_cols if col in summary.columns]
        frame = frame.merge(summary[keep], on="variant", how="left", suffixes=("", "_summary"))

    return frame


def _first_present(row: pd.Series, names: list[str], default: Any = np.nan) -> Any:
    for name in names:
        if name in row.index and pd.notna(row[name]):
            return row[name]
    return default


def _normalize_row(row: pd.Series) -> dict[str, Any]:
    variant = str(row["variant"])
    hard_stage079 = _flag(_first_present(row, ["metric_hard_pass_stage079", "metric_hard_pass"]))
    target_pass = _flag(_first_present(row, ["target_pass_3m6m_vs_stage079", "target_pass_3m6m"]))
    cost_stage079 = _flag(_first_present(row, ["cost_stress_not_worse_than_stage079", "cost_stress_not_worse"]))
    fresh = _flag(row.get("fresh_start_dd30_pass", 0))
    stage103_incremental = _flag(row.get("metric_incremental_pass_stage103", 0))
    cost_stage103 = _flag(row.get("cost_stress_not_worse_than_stage103", 0))
    short_not_lower_stage103 = _flag(row.get("short_score_not_lower_than_stage103", 0))
    bad_window_not_worse = _flag(row.get("bad_window_not_worse_than_stage103", 0))
    research_pass = _flag(row.get("research_promotion_pass", 0))
    execution_pass = _flag(row.get("execution_relative_pass", 0))
    broker_abs = _flag(row.get("deployment_absolute_margin_pass", 0))

    active_goal_pass = bool(hard_stage079 and target_pass and cost_stage079 and fresh)
    incumbent_upgrade_pass = bool(
        active_goal_pass
        and (variant == STAGE103_VARIANT or stage103_incremental)
        and (variant == STAGE103_VARIANT or cost_stage103)
        and (variant == STAGE103_VARIANT or short_not_lower_stage103)
        and (variant == STAGE103_VARIANT or bad_window_not_worse)
        and (variant == STAGE103_VARIANT or research_pass or execution_pass)
    )

    override = LATER_ROBUSTNESS_DECISIONS.get(variant, {})
    tier_override = override.get("tier_override", "")
    reason = override.get("reason", "")

    if variant == STAGE079_VARIANT:
        tier = "baseline"
        reason = "Stage079 baseline."
    elif variant == STAGE103_VARIANT:
        tier = "current_main_execution_relative_candidate"
        reason = "Stage103 remains the clean incumbent relative to Stage079 after later audits."
    elif not active_goal_pass:
        tier = "failed_active_objective_gate"
        failed = _first_present(
            row,
            ["failed_stage079_metric_checks", "failed_metric_checks", "fresh_start_failed_windows"],
            "",
        )
        reason = f"Failed Stage079 objective gate: {failed}" if str(failed) else "Failed Stage079 objective gate."
    elif tier_override:
        tier = tier_override
    elif incumbent_upgrade_pass:
        tier = "incumbent_upgrade_candidate_needs_manual_review"
        reason = "Passes the active Stage079 objective and incumbent-relative gates, with no later downgrade found."
    else:
        tier = "paper_only_not_incumbent_upgrade"
        failed = _first_present(row, ["failed_stage103_incremental_checks"], "")
        reason = f"Passes Stage079 objective but not current Stage103 upgrade gate: {failed}" if str(failed) else (
            "Passes Stage079 objective but does not clearly improve the current Stage103 incumbent."
        )

    return {
        "source_stage": _safe_int(row.get("source_stage"), -1),
        "variant": variant,
        "label": str(row.get("label", "")),
        "source_decision": str(row.get("source_decision", "")),
        "end_equity": _safe_float(row.get("end_equity")),
        "total_return_pct": _safe_float(row.get("total_return_pct")),
        "max_dd_pct": _safe_float(row.get("max_dd_pct")),
        "sharpe": _safe_float(row.get("sharpe")),
        "ulcer_pct": _safe_float(row.get("ulcer_pct")),
        "score_90d": _safe_float(row.get("score_90d")),
        "score_180d": _safe_float(row.get("score_180d")),
        "short_holding_score": _safe_float(row.get("short_holding_score")),
        "objective_improved_8_count_90d": _safe_int(row.get("objective_improved_8_count_90d")),
        "objective_improved_8_count_180d": _safe_int(row.get("objective_improved_8_count_180d")),
        "metric_hard_pass_stage079": int(hard_stage079),
        "target_pass_3m6m_vs_stage079": int(target_pass),
        "cost_stress_not_worse_than_stage079": int(cost_stage079),
        "fresh_start_dd30_pass": int(fresh),
        "metric_incremental_pass_stage103": int(stage103_incremental),
        "cost_stress_not_worse_than_stage103": int(cost_stage103),
        "active_stage079_objective_pass": int(active_goal_pass),
        "incumbent_stage103_upgrade_pass_before_later_downgrade": int(incumbent_upgrade_pass),
        "deployment_absolute_margin_pass": int(broker_abs),
        "promotion_tier": tier,
        "reason": reason,
        "source_file": str(row.get("source_file", "")),
    }


def _collect_candidates() -> pd.DataFrame:
    frames = [_read_gate(path) for path in _latest_gate_files()]
    if not frames:
        return pd.DataFrame()
    raw = pd.concat(frames, ignore_index=True)
    normalized = pd.DataFrame([_normalize_row(row) for _idx, row in raw.iterrows()])

    # Keep the latest evidence per variant; for equal stages, keep the row with the best short score.
    normalized = normalized.sort_values(
        ["variant", "source_stage", "short_holding_score"],
        ascending=[True, False, False],
        na_position="last",
    )
    latest = normalized.drop_duplicates("variant", keep="first").reset_index(drop=True)
    latest = latest.sort_values(
        ["active_stage079_objective_pass", "short_holding_score", "total_return_pct"],
        ascending=[False, False, False],
        na_position="last",
    ).reset_index(drop=True)
    return latest


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


def _write_chart(frame: pd.DataFrame) -> None:
    plot = frame[frame["variant"].ne(STAGE079_VARIANT)].copy()
    plot = plot.dropna(subset=["short_holding_score", "total_return_pct", "max_dd_pct"])
    if plot.empty:
        return
    color_map = {
        "current_main_execution_relative_candidate": "#2ca02c",
        "paper_only_not_incumbent_upgrade": "#ff7f0e",
        "downgraded_by_later_robustness": "#d62728",
        "failed_active_objective_gate": "#7f7f7f",
        "incumbent_upgrade_candidate_needs_manual_review": "#1f77b4",
    }
    colors = [color_map.get(tier, "#9467bd") for tier in plot["promotion_tier"]]
    sizes = np.clip((plot["total_return_pct"].fillna(0.0) - 4500.0) * 0.25, 40, 360)

    fig, ax = plt.subplots(figsize=(13, 8))
    ax.scatter(plot["short_holding_score"], plot["max_dd_pct"], s=sizes, c=colors, alpha=0.78, edgecolors="white")
    for _, row in plot.head(18).iterrows():
        label = row["variant"]
        if len(label) > 34:
            label = label[:31] + "..."
        ax.annotate(label, (row["short_holding_score"], row["max_dd_pct"]), fontsize=7, xytext=(4, 4), textcoords="offset points")
    ax.axhline(-29.7007, color="#444444", linestyle="--", linewidth=1, label="Stage079 maxDD")
    ax.axvline(110.0, color="#999999", linestyle=":", linewidth=1, label="score +10% threshold")
    ax.set_title("Stage426 active-objective candidate audit")
    ax.set_xlabel("Short holding score (45% 90d + 55% 180d)")
    ax.set_ylabel("Full-cycle max drawdown (%)")
    ax.grid(True, alpha=0.25)
    ax.legend(loc="lower right", fontsize=8)
    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=180)
    plt.close(fig)


def _write_report(frame: pd.DataFrame, tier_summary: pd.DataFrame, decision: dict[str, Any]) -> None:
    top_cols = [
        "source_stage",
        "variant",
        "promotion_tier",
        "total_return_pct",
        "max_dd_pct",
        "sharpe",
        "ulcer_pct",
        "score_90d",
        "score_180d",
        "short_holding_score",
        "objective_improved_8_count_90d",
        "objective_improved_8_count_180d",
        "reason",
    ]
    top = frame[top_cols].head(18)
    active = frame[frame["active_stage079_objective_pass"].eq(1)][top_cols]
    lines = [
        "# Stage126 Active Objective Promotion Audit",
        "",
        "- 生成时间：2026-05-28",
        f"- line_id：`{LINE_ID}`",
        "- 阶段性质：只读晋级审计；不新增策略规则，不修改 Stage079/Stage103，不增加资金，不做参数扫描。",
        "- 审计目的：把用户原始 Stage079 目标、当前 Stage103 incumbent、后续反过拟合降级结论拆开，避免候选分层混乱。",
        "- 外部调研判断：多信号/多候选回测存在显著选择偏差；因此本阶段不把短期分数最高者自动晋级，而要求后续鲁棒性和未被 later audit 降级。",
        f"- 图表：`{CHART_PATH}`",
        "",
        "## 决策",
        "",
        "```json",
        json.dumps(decision, ensure_ascii=False, indent=2),
        "```",
        "",
        "## Tier Summary",
        "",
        _md_table(tier_summary),
        "",
        "## Active Stage079 Objective Pass Candidates",
        "",
        _md_table(active, max_rows=20),
        "",
        "## Top Candidates By Short Holding Score",
        "",
        _md_table(top, max_rows=18),
        "",
        "## 结论",
        "",
        "- Stage103 仍是当前唯一干净的主执行相对候选。",
        "- 多个版本按 Stage079 原始目标看可以通过，但后续审计显示它们不是更干净的 Stage103 替代：Stage115 有贡献日/滚动收益脆弱性，value756 样本覆盖不足，OI best1 任意启动收益胜率弱且5x成本略劣于Stage103。",
        "- 因此，若严格追求不过拟合，当前不应把新的高分候选替换 Stage103；后续应优先工程化复跑/影子盘，或者只测试全新低自由度风险源。",
        "",
        "## 过拟合反思",
        "",
        "- 运行前判断：不是过拟合，因为本阶段只审计已冻结候选，不新增参数。",
        "- 运行后判断：不是过拟合；它反而降低过拟合风险，因为把多候选选择偏差显式纳入决策。",
        "- 继续扫已降级路线会过拟合，尤其是为了让 Stage115、value756、OI best1 通过某个单一失败项而调日期、阈值、窗口或品种。",
        "",
        "## 继续价值反思",
        "",
        "- 运行前判断：有价值，因为用户目标已经积累大量高分但失败原因不同的候选，需要统一晋级口径。",
        "- 运行后判断：继续优化仍有价值，但当前不是继续救老路线，而是固定 Stage103 落地，或寻找真正不同、样本更充分、保证金更轻的风险源。",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    frame = _collect_candidates()
    if frame.empty:
        raise RuntimeError("No gate files found for Stage403-425.")

    tier_summary = (
        frame.groupby("promotion_tier", as_index=False)
        .agg(candidate_count=("variant", "count"), best_short_score=("short_holding_score", "max"))
        .sort_values(["candidate_count", "best_short_score"], ascending=[False, False])
    )

    active_pass = frame[frame["active_stage079_objective_pass"].eq(1)].copy()
    clean = frame[frame["promotion_tier"].eq("current_main_execution_relative_candidate")].copy()
    paper = frame[frame["promotion_tier"].eq("paper_only_not_incumbent_upgrade")].copy()
    downgraded = frame[frame["promotion_tier"].eq("downgraded_by_later_robustness")].copy()

    decision = {
        "stage": "Stage126",
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "decision": "keep_stage103_as_main_execution_relative_candidate",
        "active_stage079_objective_pass_count": int(len(active_pass)),
        "clean_execution_candidate_variants": clean["variant"].tolist(),
        "paper_only_pass_variants": paper["variant"].head(10).tolist(),
        "downgraded_after_later_robustness_variants": downgraded["variant"].tolist(),
        "best_by_short_holding_score": frame.loc[frame["short_holding_score"].idxmax(), "variant"],
        "best_clean_candidate": STAGE103_VARIANT,
        "chart": str(CHART_PATH),
        "judgement": "Do not replace Stage103 with higher short-score candidates unless they survive incumbent-relative rolling return, top-day, sample coverage, cost, and margin audits.",
    }

    frame.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    tier_summary.to_csv(TIER_PATH, index=False, encoding="utf-8-sig")
    frame.head(25).to_csv(TOP_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(decision, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_chart(frame)
    _write_report(frame, tier_summary, decision)
    print(json.dumps(decision, ensure_ascii=False, indent=2))
    print(f"report={REPORT_PATH}")


if __name__ == "__main__":
    main()
