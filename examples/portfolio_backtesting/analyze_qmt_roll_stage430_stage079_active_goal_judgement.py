from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
LINE_ID = "futures_trend_drawdown30_preserve_return"
MODEL_TAG = "stage430_stage079_active_goal_judgement_v1"
OUTPUT_PREFIX = "qmt_roll_stage430_stage079_active_goal_judgement"

STAGE126_TABLE_PATH = OUTPUT_DIR / "qmt_roll_stage426_active_objective_promotion_audit_candidate_table_stage426_active_objective_promotion_audit_v1.csv"
STAGE127_GATE_PATH = OUTPUT_DIR / "qmt_roll_stage427_stage103_pair_spread_overlay_gate_stage427_stage103_pair_spread_overlay_v1.csv"
STAGE129_GATE_PATH = OUTPUT_DIR / "qmt_roll_stage429_stage103_cffex_curve_spread_overlay_gate_stage429_stage103_cffex_curve_spread_overlay_v1.csv"
STAGE109_DECISION_PATH = OUTPUT_DIR / "qmt_roll_stage409_stage103_robustness_overfit_audit_decision_stage409_stage103_robustness_overfit_audit_v1.json"
STAGE109_TOPDAY_PATH = OUTPUT_DIR / "qmt_roll_stage409_stage103_robustness_overfit_audit_top_edge_day_ablation_stage409_stage103_robustness_overfit_audit_v1.csv"
STAGE109_PAIRWISE_PATH = OUTPUT_DIR / "qmt_roll_stage409_stage103_robustness_overfit_audit_pairwise_rolling_stage409_stage103_robustness_overfit_audit_v1.csv"
STAGE116_DECISION_PATH = OUTPUT_DIR / "qmt_roll_stage416_stage115_robustness_overfit_audit_decision_stage416_stage115_robustness_overfit_audit_v1.json"
STAGE116_TOPDAY_PATH = OUTPUT_DIR / "qmt_roll_stage416_stage115_robustness_overfit_audit_top_edge_day_ablation_stage416_stage115_robustness_overfit_audit_v1.csv"
STAGE116_PAIRWISE_PATH = OUTPUT_DIR / "qmt_roll_stage416_stage115_robustness_overfit_audit_pairwise_rolling_stage416_stage115_robustness_overfit_audit_v1.csv"

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
ANTIOVERFIT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_anti_overfit_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

STAGE079_VARIANT = "stage079"
STAGE103_VARIANT = "xsmom_vt10_q_momq_round_half_true_broker10_guard"
STAGE115_VARIANT = "stage103_plus_cffex_index_best1_tsmom60_guard"


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if pd.isna(value) if not isinstance(value, (dict, list, tuple)) else False:
        return None
    if hasattr(value, "item"):
        try:
            return value.item()
        except ValueError:
            pass
    return value


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


def _normalize_gate(path: Path, source_stage: int, default_reason: str) -> pd.DataFrame:
    frame = pd.read_csv(path, encoding="utf-8-sig")
    frame["source_stage"] = source_stage
    frame["source_file"] = path.name
    frame["reason"] = default_reason
    renames = {
        "metric_hard_pass": "metric_hard_pass_stage079",
        "target_pass_3m6m": "target_pass_3m6m_vs_stage079",
        "cost_stress_not_worse": "cost_stress_not_worse_than_stage079",
        "score90_improve_ge10pct": "score90_improve_ge10pct_vs_stage079",
        "score180_improve_ge10pct": "score180_improve_ge10pct_vs_stage079",
        "objective_improved_5of8_each": "objective_improved_5of8_each_vs_stage079",
    }
    frame = frame.rename(columns={k: v for k, v in renames.items() if k in frame.columns})
    for col in [
        "metric_hard_pass_stage079",
        "target_pass_3m6m_vs_stage079",
        "cost_stress_not_worse_than_stage079",
        "fresh_start_dd30_pass",
        "score90_improve_ge10pct_vs_stage079",
        "score180_improve_ge10pct_vs_stage079",
        "objective_improved_5of8_each_vs_stage079",
    ]:
        if col not in frame.columns:
            frame[col] = 0
        frame[col] = pd.to_numeric(frame[col], errors="coerce").fillna(0).astype(int)
    frame["active_stage079_objective_pass"] = (
        frame["metric_hard_pass_stage079"].eq(1)
        & frame["target_pass_3m6m_vs_stage079"].eq(1)
    ).astype(int)
    return frame


def _load_candidate_rows() -> pd.DataFrame:
    base = pd.read_csv(STAGE126_TABLE_PATH, encoding="utf-8-sig")
    base["source_file"] = STAGE126_TABLE_PATH.name
    base["source_stage"] = pd.to_numeric(base["source_stage"], errors="coerce").fillna(0).astype(int)
    base["reason"] = base.get("reason", "").fillna("")

    extras = [
        _normalize_gate(
            STAGE127_GATE_PATH,
            427,
            "Stage127: Stage079目标通过，但新增产业链价差腿净PnL为负，且收益低于Stage103，只能paper观察。",
        ),
        _normalize_gate(
            STAGE129_GATE_PATH,
            429,
            "Stage129: Stage079目标通过，但新增TF/T曲线腿净PnL为负，且收益、Sharpe、Ulcer弱于Stage103。",
        ),
    ]
    common_cols = sorted(set(base.columns).union(*(set(item.columns) for item in extras)))
    frames = []
    for frame in [base, *extras]:
        frames.append(frame.reindex(columns=common_cols))
    all_rows = pd.concat(frames, ignore_index=True)
    all_rows["active_stage079_objective_pass"] = pd.to_numeric(
        all_rows.get("active_stage079_objective_pass", 0), errors="coerce"
    ).fillna(0).astype(int)
    all_rows["short_holding_score"] = pd.to_numeric(all_rows.get("short_holding_score", 0), errors="coerce")
    all_rows["_has_core_metrics"] = pd.to_numeric(all_rows.get("total_return_pct", pd.NA), errors="coerce").notna().astype(int)
    all_rows = all_rows.sort_values(
        ["active_stage079_objective_pass", "_has_core_metrics", "short_holding_score", "source_stage"],
        ascending=[False, False, False, False],
    )
    all_rows = all_rows.drop_duplicates("variant", keep="first")
    all_rows = all_rows.drop(columns=["_has_core_metrics"])
    return all_rows


def _topday_snapshot(path: Path, variant: str, comparator: str | None = None) -> dict[str, Any]:
    frame = pd.read_csv(path, encoding="utf-8-sig")
    if comparator is not None and "comparator_variant" in frame.columns:
        frame = frame[frame["comparator_variant"].eq(comparator)]
    result: dict[str, Any] = {"variant": variant}
    for n in [0, 1, 3, 5, 20]:
        row = frame[pd.to_numeric(frame["removed_top_positive_edge_days"], errors="coerce").eq(n)]
        if row.empty:
            continue
        row = row.iloc[0]
        if "adjusted_return_delta_vs_stage079_pp" in row:
            result[f"top{n}_return_delta_vs_stage079_pp"] = float(row["adjusted_return_delta_vs_stage079_pp"])
        elif "adjusted_return_delta_pp" in row:
            result[f"top{n}_return_delta_vs_stage079_pp"] = float(row["adjusted_return_delta_pp"])
        if "candidate_adjusted_max_dd_pct" in row:
            result[f"top{n}_adjusted_max_dd_pct"] = float(row["candidate_adjusted_max_dd_pct"])
        elif "stage103_adjusted_max_dd_pct" in row:
            result[f"top{n}_adjusted_max_dd_pct"] = float(row["stage103_adjusted_max_dd_pct"])
    return result


def _pairwise_snapshot(path: Path, variant: str) -> dict[str, Any]:
    frame = pd.read_csv(path, encoding="utf-8-sig")
    if "comparator_variant" in frame.columns:
        frame = frame[frame["comparator_variant"].eq(STAGE079_VARIANT)]
    result: dict[str, Any] = {"variant": variant}
    for window in [90, 180, 252, 504]:
        row = frame[pd.to_numeric(frame["window_days"], errors="coerce").eq(window)]
        if row.empty:
            continue
        row = row.iloc[0]
        prefix = f"win{window}"
        return_col = "return_win_rate" if "return_win_rate" in row else "stage103_return_win_rate"
        maxdd_col = "maxdd_not_worse_rate" if "maxdd_not_worse_rate" in row else "stage103_maxdd_not_worse_rate"
        ulcer_col = "ulcer_not_worse_rate" if "ulcer_not_worse_rate" in row else "stage103_ulcer_not_worse_rate"
        result[f"{prefix}_return_win_rate"] = float(row[return_col])
        result[f"{prefix}_maxdd_not_worse_rate"] = float(row[maxdd_col])
        result[f"{prefix}_ulcer_not_worse_rate"] = float(row[ulcer_col])
    return result


def _classify(row: pd.Series) -> tuple[str, str]:
    variant = str(row["variant"])
    if variant == STAGE079_VARIANT:
        return "baseline", "Stage079 baseline，不参与晋级。"
    if int(row.get("active_stage079_objective_pass", 0)) != 1:
        return "reject", "未通过当前Stage079目标闸门。"
    if variant == STAGE103_VARIANT:
        return "main_candidate", "通过Stage079硬约束与短持有晋级线；Stage109确认风险/Ulcer优势较稳，保留为当前最干净主候选。"
    if variant == STAGE115_VARIANT:
        return "high_score_paper_candidate", "通过Stage079目标且短持有分最高，但Stage116显示收益优势对Stage103集中、绝对保证金未完全落地，只能paper/观察。"
    if "oi_confirm63_best1" in variant:
        return "paper_candidate", "通过Stage079目标，但相对Stage103任意启动收益胜率弱，且5x成本压力曾被标记略劣。"
    if "value_proxy756" in variant:
        return "paper_candidate", "通过Stage079目标，但Stage123显示有效样本覆盖不足，不能证明穿越周期。"
    if "short_only" in variant:
        return "secondary_candidate", "通过Stage079目标且保证金更轻，但被Stage103多空双边支配。"
    if "pair_spread" in variant or "tf_t_curve" in variant:
        return "objective_only_candidate", "通过Stage079目标，但新增腿净PnL为负且不能升级Stage103，只能作为paper观察。"
    return "paper_candidate", "通过Stage079目标，但缺少更高层级反过拟合/工程化证据。"


def _plot(summary: pd.DataFrame) -> None:
    view = summary[summary["variant"].ne(STAGE079_VARIANT)].head(8).copy()
    if view.empty:
        return
    labels = view["variant"].str.replace("stage103_plus_", "+", regex=False).str.slice(0, 34)
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    axes[0].barh(labels, view["short_holding_score"].astype(float), color="#4c78a8")
    axes[0].axvline(110.0, color="#e45756", linestyle="--", linewidth=1.2, label="promotion score line")
    axes[0].set_title("Short holding score vs Stage079")
    axes[0].set_xlabel("score")
    axes[0].invert_yaxis()
    axes[0].legend(loc="lower right")

    x = range(len(view))
    axes[1].plot(x, view["score_90d"].astype(float), marker="o", label="90d score")
    axes[1].plot(x, view["score_180d"].astype(float), marker="o", label="180d score")
    axes[1].axhline(110.0, color="#e45756", linestyle="--", linewidth=1.2)
    axes[1].set_xticks(list(x))
    axes[1].set_xticklabels(labels, rotation=45, ha="right")
    axes[1].set_title("90d / 180d experience scores")
    axes[1].set_ylabel("score")
    axes[1].legend()
    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=180)
    plt.close(fig)


def main() -> None:
    candidates = _load_candidate_rows()
    stage109_decision = _read_json(STAGE109_DECISION_PATH)
    stage116_decision = _read_json(STAGE116_DECISION_PATH)

    pass_rows = candidates[candidates["active_stage079_objective_pass"].eq(1)].copy()
    classifications = pass_rows.apply(_classify, axis=1, result_type="expand")
    pass_rows["promotion_level"] = classifications[0]
    pass_rows["current_judgement"] = classifications[1]
    pass_rows = pass_rows.sort_values(
        ["promotion_level", "short_holding_score"],
        key=lambda s: s.map(
            {
                "main_candidate": 0,
                "high_score_paper_candidate": 1,
                "paper_candidate": 2,
                "secondary_candidate": 3,
                "objective_only_candidate": 4,
                "baseline": 9,
            }
        ).fillna(8)
        if s.name == "promotion_level"
        else s,
        ascending=[True, False],
    )

    anti_rows = pd.DataFrame(
        [
            _topday_snapshot(STAGE109_TOPDAY_PATH, STAGE103_VARIANT),
            _pairwise_snapshot(STAGE109_PAIRWISE_PATH, STAGE103_VARIANT),
            _topday_snapshot(STAGE116_TOPDAY_PATH, STAGE115_VARIANT, STAGE079_VARIANT),
            _pairwise_snapshot(STAGE116_PAIRWISE_PATH, STAGE115_VARIANT),
        ]
    ).groupby("variant", as_index=False).first()

    pass_rows.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    anti_rows.to_csv(ANTIOVERFIT_PATH, index=False, encoding="utf-8-sig")
    _plot(pass_rows)

    main_candidate = pass_rows[pass_rows["promotion_level"].eq("main_candidate")]
    high_score = pass_rows[pass_rows["promotion_level"].eq("high_score_paper_candidate")]
    best_score_row = pass_rows.sort_values("short_holding_score", ascending=False).head(1)
    decision = {
        "stage": "Stage130",
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "decision": "stage103_main_candidate_stage115_high_score_paper",
        "baseline": STAGE079_VARIANT,
        "active_stage079_objective_pass_count": int(len(pass_rows[pass_rows["variant"].ne(STAGE079_VARIANT)])),
        "main_candidate": main_candidate["variant"].tolist(),
        "high_score_paper_candidate": high_score["variant"].tolist(),
        "best_by_short_holding_score": str(best_score_row.iloc[0]["variant"]) if not best_score_row.empty else "",
        "stage103_robustness_judgement": stage109_decision.get("promotion_judgement", ""),
        "stage115_robustness_judgement": stage116_decision.get("promotion_judgement", ""),
        "chart": str(CHART_PATH),
        "summary": str(SUMMARY_PATH),
        "anti_overfit": str(ANTIOVERFIT_PATH),
        "report": str(REPORT_PATH),
        "judgement": "当前目标下已有候选过线；若强调不过拟合和可执行干净度，Stage103是主候选，Stage115只能paper观察。",
    }
    with DECISION_PATH.open("w", encoding="utf-8") as f:
        json.dump(_json_safe(decision), f, ensure_ascii=False, indent=2)

    cols = [
        "variant",
        "promotion_level",
        "total_return_pct",
        "max_dd_pct",
        "sharpe",
        "ulcer_pct",
        "score_90d",
        "score_180d",
        "short_holding_score",
        "objective_improved_8_count_90d",
        "objective_improved_8_count_180d",
        "current_judgement",
    ]
    existing_cols = [col for col in cols if col in pass_rows.columns]
    report_lines = [
        "# Stage130 Stage079主动目标候选裁决",
        "",
        f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- line_id：`{LINE_ID}`",
        "- 阶段性质：只读晋级裁决；不新增交易规则、不新增资金、不扫描参数。",
        "- Baseline：Stage079 = 50万C3下单 + 11.5万现金。",
        "",
        "## 裁决",
        "",
        "- 当前目标下已有候选通过 Stage079 硬约束和 3个月/6个月晋级线。",
        "- 若只看当前目标表，Stage115 `best1_tsmom60` 分数最高；但它已被 Stage116 标为高分 paper 候选，不宜作为主版本。",
        "- 若强调不过拟合、保证金干净度和后续可执行性，Stage103 `broker10_guard` 仍是当前主候选。",
        "",
        "## 过线候选分层",
        "",
        _md_table(pass_rows[existing_cols], max_rows=12),
        "",
        "## 反过拟合证据摘要",
        "",
        _md_table(anti_rows, max_rows=12),
        "",
        "## 关键解释",
        "",
        f"- Stage103：{stage109_decision.get('reason', '')}",
        f"- Stage115：{stage116_decision.get('reason', '')}",
        "- 连续失败信号、分批启动、默认环境降仓、商品动量、basis、OI、value、贵金属、价差等方向已经留下明确边界；继续救小参数会提高过拟合风险。",
        "",
        "## 结论",
        "",
        "- 主候选：Stage103 `xsmom_vt10_q_momq_round_half_true_broker10_guard`。",
        "- 高分但不主晋级：Stage115 `stage103_plus_cffex_index_best1_tsmom60_guard`，只适合 paper/观察。",
        "- 下一步不应继续在 Stage087-129 已降级路线里调参数；如果继续主动研究，需要全新、保证金更轻、样本更充分且非坏窗口归因的新风险源。",
        "",
        f"![Stage130 chart]({CHART_PATH})",
    ]
    REPORT_PATH.write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    print(f"[stage430] wrote {DECISION_PATH}")
    print(f"[stage430] wrote {REPORT_PATH}")


if __name__ == "__main__":
    main()
