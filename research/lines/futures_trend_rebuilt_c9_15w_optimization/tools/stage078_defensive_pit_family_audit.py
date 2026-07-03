from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


LINE_ID = "futures_trend_rebuilt_c9_15w_optimization"
STAGE = "Stage078"
MODEL_TAG = "stage078_defensive_pit_family_audit_v1"
STAGE_SLUG = "stage078_defensive_pit_family_audit"
OUTPUT_PREFIX = "rebuilt_c9_stage078_defensive_pit_family_audit"

MIN_GLOBAL_COUNT = 100
MIN_YEAR_COUNT = 3
MIN_WORST_LOSS_CAPTURE_PCT = 25.0
MAX_GLOBAL_TOTAL_PNL = 0.0
MAX_OOS_POSITIVE_FOLD_COUNT = 1
MAX_POSITIVE_PNL_COLLISION_PCT = 25.0
N_SPLITS = 4

TOOLS_DIR = Path(__file__).resolve().parent
LINE_DIR = TOOLS_DIR.parent
OUTPUT_DIR = LINE_DIR / "outputs" / STAGE_SLUG
STAGES_DIR = LINE_DIR / "stages"

STAGE038_OUTPUT_DIR = LINE_DIR / "outputs" / "stage038_candidate_pit_feature_matrix_audit"
STAGE071_OUTPUT_DIR = LINE_DIR / "outputs" / "stage071_stage070_remaining_left_tail_attribution"
STAGE038_PREFIX = "rebuilt_c9_stage038_candidate_pit_feature_matrix_audit"
STAGE038_TAG = "stage038_candidate_pit_feature_matrix_audit_v1"
STAGE071_PREFIX = "rebuilt_c9_stage071_stage070_remaining_left_tail_attribution"
STAGE071_TAG = "stage071_stage070_remaining_left_tail_attribution_v1"

FEATURE_MATRIX_PATH = STAGE038_OUTPUT_DIR / f"{STAGE038_PREFIX}_feature_matrix_{STAGE038_TAG}.csv"
WINDOW_ENTRIES_PATH = STAGE071_OUTPUT_DIR / f"{STAGE071_PREFIX}_window_entries_{STAGE071_TAG}.csv"

CONDITION_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_condition_summary_{MODEL_TAG}.csv"
FAMILY_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_family_summary_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

PRIOR_REFUTED_OR_INSUFFICIENT_REASONS = {
    "not_full_market_ai_top8": "Stage056 已反证非 full-market AI top8 一手 cap，不能重复救参。",
    "oi_confirmed": "Stage062 真引擎已反证 OI-confirmed 反向预算。",
    "selected_volume_gt1": "Stage055/056 显示 selected_volume_gt1 压力样本为负，但硬 cap 会砍右尾。",
    "account_injured": "Stage029 已反证账户受伤状态直接暂停 flat_entry。",
    "loss_streak_ge2": "Stage029/058 已反证连败状态 hard pause/连续预算救参。",
    "loss_streak_ge3": "Stage029/058 已反证连败状态 hard pause/连续预算救参。",
    "drawdown_abs_ge20": "Stage029 已反证 drawdown 状态暂停新开仓。",
    "drawdown_abs_ge30": "Stage029 已反证 drawdown 状态暂停新开仓。",
    "active_positions_ge3": "Stage016/070 显示 active positions 有状态信息，但固定加风险/预算未达目标。",
    "risk_multiplier_gt1": "Stage058 已反证固定连续预算/倍率救参。",
    "same_direction_corr_ge50": "Stage016 同向相关归因不足以直接交易化。",
    "same_direction_corr_ge70": "Stage016 同向相关归因不足以直接交易化。",
}


@dataclass(frozen=True)
class Stage078Condition:
    name: str
    family: str
    description: str
    mask: pd.Series


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        number = float(value)
        return None if math.isnan(number) or math.isinf(number) else number
    if isinstance(value, (pd.Timestamp, datetime)):
        if pd.isna(value):
            return None
        return value.isoformat()
    if pd.isna(value):
        return None
    return value


def _read_csv(path: Path, **kwargs: Any) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path, encoding="utf-8-sig", **kwargs)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_无数据_"
    data = frame.head(max_rows).copy() if max_rows is not None else frame.copy()
    for column in data.columns:
        if pd.api.types.is_float_dtype(data[column]):
            data[column] = data[column].map(lambda value: f"{value:.4f}" if pd.notna(value) else "")
    return data.to_markdown(index=False)


def _num(frame: pd.DataFrame, column: str, default: float = np.nan) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype="float64")
    return pd.to_numeric(frame[column], errors="coerce")


def _to_bool(values: pd.Series | Any, index: pd.Index | None = None) -> pd.Series:
    if isinstance(values, pd.Series):
        series = values.copy()
    else:
        series = pd.Series(values, index=index)
    if series.empty:
        return series.astype(bool)
    if pd.api.types.is_bool_dtype(series):
        return series.fillna(False).astype(bool)
    if pd.api.types.is_numeric_dtype(series):
        return pd.to_numeric(series, errors="coerce").fillna(0).ne(0)
    text = series.fillna("").astype(str).str.strip().str.lower()
    return text.isin({"1", "1.0", "true", "yes", "y", "pass", "passed", "opened"})


def _bool_column(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(False, index=frame.index)
    return _to_bool(frame[column], index=frame.index)


def _fold_masks(frame: pd.DataFrame, n_splits: int = N_SPLITS) -> list[pd.Series]:
    if "entry_date" not in frame.columns:
        return []
    dates = list(pd.to_datetime(frame["entry_date"], errors="coerce").dropna().sort_values())
    if not dates:
        return []
    chunks = np.array_split(np.asarray(dates, dtype="datetime64[ns]"), n_splits)
    entry_dates = pd.to_datetime(frame["entry_date"], errors="coerce")
    masks: list[pd.Series] = []
    for chunk in chunks:
        if len(chunk) == 0:
            continue
        masks.append(entry_dates.between(chunk.min(), chunk.max(), inclusive="both"))
    return masks


def build_stage078_conditions(frame: pd.DataFrame) -> list[Stage078Condition]:
    index = frame.index
    ai_rank = _num(frame, "ai_rank")
    full_ai_top8 = _bool_column(frame, "full_market_ai_top8")
    full_simple_top8 = _bool_column(frame, "full_market_simple_top8")
    ai_rank_1_6 = _bool_column(frame, "ai_rank_1_6")
    oi_confirmed = _bool_column(frame, "oi_confirmed")
    selected_volume_gt1 = _bool_column(frame, "selected_volume_gt1") | (_num(frame, "selected_volume").fillna(0) > 1)
    drawdown_abs = _num(frame, "drawdown_abs_pct")
    loss_streak = _num(frame, "loss_streak").combine_first(_num(frame, "stage038_loss_streak"))
    loss_ge2 = _bool_column(frame, "loss_streak_ge2") | (loss_streak.fillna(0) >= 2)
    loss_ge3 = _bool_column(frame, "loss_streak_ge3") | (loss_streak.fillna(0) >= 3)
    active_positions = _num(frame, "active_positions_before").combine_first(
        _num(frame, "stage038_active_positions_before")
    )
    active_ge3 = _bool_column(frame, "active_positions_ge3") | (active_positions.fillna(0) >= 3)
    account_injured = _bool_column(frame, "account_injured")
    risk_multiplier = _num(frame, "risk_multiplier").fillna(1.0)
    same_corr = _num(frame, "same_direction_correlation_max_corr")
    full_prob = _num(frame, "full_market_probability")

    def condition(name: str, family: str, description: str, mask: pd.Series) -> Stage078Condition:
        return Stage078Condition(name, family, description, mask.reindex(index).fillna(False).astype(bool))

    return [
        condition(
            "not_full_market_ai_top8",
            "ai_quality",
            "未进入 full-market AI top8，防守型低质量候选",
            ~full_ai_top8,
        ),
        condition(
            "not_full_market_simple_top8",
            "ai_quality",
            "未进入 simple trend top8，防守型低质量候选",
            ~full_simple_top8,
        ),
        condition("not_ai_rank_1_6", "ai_quality", "未进入当前 C9 AI rank 1-6", ~ai_rank_1_6),
        condition("ai_rank_gt6", "ai_quality", "当前 C9 AI rank 大于 6", ai_rank > 6),
        condition("ai_rank_gt9", "ai_quality", "当前 C9 AI rank 大于 9", ai_rank > 9),
        condition("full_market_probability_lt55", "ai_quality", "full-market probability < 0.55", full_prob < 0.55),
        condition(
            "full_market_probability_missing",
            "ai_quality",
            "缺 full-market probability，主要用于识别覆盖缺口而非交易规则",
            full_prob.isna(),
        ),
        condition("oi_confirmed", "oi", "传统 OI 确认状态", oi_confirmed),
        condition("selected_volume_gt1", "risk_budget", "选择手数大于 1", selected_volume_gt1),
        condition("risk_multiplier_gt1", "risk_budget", "风险倍率大于 1", risk_multiplier > 1),
        condition("drawdown_abs_ge10", "account_state", "入场前账户回撤绝对值 >= 10%", drawdown_abs >= 10),
        condition("drawdown_abs_ge20", "account_state", "入场前账户回撤绝对值 >= 20%", drawdown_abs >= 20),
        condition("drawdown_abs_ge30", "account_state", "入场前账户回撤绝对值 >= 30%", drawdown_abs >= 30),
        condition("loss_streak_ge2", "account_state", "入场前连败 >= 2", loss_ge2),
        condition("loss_streak_ge3", "account_state", "入场前连败 >= 3", loss_ge3),
        condition("account_injured", "account_state", "账户受伤状态", account_injured),
        condition("active_positions_ge3", "crowding", "入场前活跃持仓 >= 3", active_ge3),
        condition("same_direction_corr_ge50", "crowding", "同向相关最大相关系数 >= 0.50", same_corr >= 0.50),
        condition("same_direction_corr_ge70", "crowding", "同向相关最大相关系数 >= 0.70", same_corr >= 0.70),
    ]


def summarize_defensive_conditions(
    feature_matrix: pd.DataFrame,
    window_entries: pd.DataFrame,
    *,
    refuted_conditions: set[str] | None = None,
    min_global_count: int = MIN_GLOBAL_COUNT,
    min_year_count: int = MIN_YEAR_COUNT,
    min_worst_loss_capture_pct: float = MIN_WORST_LOSS_CAPTURE_PCT,
    max_global_total_pnl: float = MAX_GLOBAL_TOTAL_PNL,
    max_oos_positive_fold_count: int = MAX_OOS_POSITIVE_FOLD_COUNT,
    max_positive_pnl_collision_pct: float = MAX_POSITIVE_PNL_COLLISION_PCT,
) -> pd.DataFrame:
    if feature_matrix.empty:
        return pd.DataFrame()
    refuted = set(refuted_conditions if refuted_conditions is not None else PRIOR_REFUTED_OR_INSUFFICIENT_REASONS)
    features = feature_matrix.copy()
    windows = window_entries.copy()
    features["entry_date"] = pd.to_datetime(features.get("entry_date"), errors="coerce")
    features["entry_year"] = features["entry_date"].dt.year
    features["realized_pnl"] = pd.to_numeric(features.get("realized_pnl"), errors="coerce").fillna(0.0)
    if "stage071_base_loss_abs" in windows.columns:
        worst_loss_abs = pd.to_numeric(windows["stage071_base_loss_abs"], errors="coerce").fillna(0.0)
    else:
        worst_loss_abs = pd.to_numeric(windows.get("realized_pnl"), errors="coerce").fillna(0.0).clip(upper=0).abs()
    total_worst_loss_abs = float(worst_loss_abs.sum())
    total_positive_pnl = float(features.loc[features["realized_pnl"] > 0, "realized_pnl"].sum())
    folds = _fold_masks(features)

    feature_conditions = {condition.name: condition for condition in build_stage078_conditions(features)}
    window_conditions = {condition.name: condition for condition in build_stage078_conditions(windows)}
    rows: list[dict[str, Any]] = []
    for name, condition in feature_conditions.items():
        global_mask = condition.mask.reindex(features.index).fillna(False).astype(bool)
        window_mask = window_conditions.get(
            name,
            Stage078Condition(name, condition.family, condition.description, pd.Series(False, index=windows.index)),
        ).mask.reindex(windows.index).fillna(False).astype(bool)
        global_subset = features.loc[global_mask]
        global_pnl = features.loc[global_mask, "realized_pnl"]
        global_total = float(global_pnl.sum()) if len(global_subset) else 0.0
        year_count = int(global_subset["entry_year"].nunique()) if len(global_subset) else 0
        worst_loss_capture = float(worst_loss_abs.loc[window_mask].sum()) if len(windows) else 0.0
        worst_loss_capture_pct = (
            float(worst_loss_capture / total_worst_loss_abs * 100.0) if total_worst_loss_abs else 0.0
        )
        positive_collision = float(global_pnl[global_pnl > 0].sum())
        positive_collision_pct = (
            float(positive_collision / total_positive_pnl * 100.0) if total_positive_pnl else 0.0
        )
        fold_pnls = [float(features.loc[fold.reindex(features.index).fillna(False) & global_mask, "realized_pnl"].sum()) for fold in folds]
        active_fold_pnls = [value for value in fold_pnls if abs(value) > 1e-12]
        positive_fold_count = int(sum(1 for value in active_fold_pnls if value > 0))
        prior_refuted = name in refuted
        defensive_candidate = (
            not prior_refuted
            and len(global_subset) >= min_global_count
            and year_count >= min_year_count
            and worst_loss_capture_pct >= min_worst_loss_capture_pct
            and global_total <= max_global_total_pnl
            and positive_fold_count <= max_oos_positive_fold_count
            and positive_collision_pct <= max_positive_pnl_collision_pct
        )
        rows.append(
            {
                "condition": name,
                "family": condition.family,
                "description": condition.description,
                "global_count": int(len(global_subset)),
                "global_coverage_pct": float(len(global_subset) / len(features) * 100.0) if len(features) else 0.0,
                "global_year_count": year_count,
                "global_total_pnl": global_total,
                "global_mean_pnl": float(global_pnl.mean()) if len(global_subset) else 0.0,
                "global_win_rate_pct": float((global_pnl > 0).mean() * 100.0) if len(global_subset) else 0.0,
                "global_positive_pnl_collision": positive_collision,
                "global_positive_pnl_collision_pct": positive_collision_pct,
                "worst_entry_count": int(window_mask.sum()),
                "worst_loss_capture": worst_loss_capture,
                "worst_loss_capture_pct": worst_loss_capture_pct,
                "oos_fold_count": int(len(active_fold_pnls)),
                "oos_positive_fold_count": positive_fold_count,
                "oos_min_fold_pnl": float(min(active_fold_pnls)) if active_fold_pnls else np.nan,
                "prior_refuted_or_insufficient": bool(prior_refuted),
                "prior_reason": PRIOR_REFUTED_OR_INSUFFICIENT_REASONS.get(name, ""),
                "stage078_defensive_candidate": bool(defensive_candidate),
            }
        )
    result = pd.DataFrame(rows)
    if result.empty:
        return result
    return result.sort_values(
        [
            "stage078_defensive_candidate",
            "prior_refuted_or_insufficient",
            "worst_loss_capture_pct",
            "global_total_pnl",
        ],
        ascending=[False, True, False, True],
    ).reset_index(drop=True)


def summarize_families(condition_summary: pd.DataFrame) -> pd.DataFrame:
    if condition_summary.empty:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    for family, group in condition_summary.groupby("family", dropna=False):
        best = group.sort_values(
            ["stage078_defensive_candidate", "worst_loss_capture_pct", "global_total_pnl"],
            ascending=[False, False, True],
        ).iloc[0]
        rows.append(
            {
                "family": family,
                "condition_count": int(len(group)),
                "candidate_count": int(group["stage078_defensive_candidate"].sum()),
                "best_condition": best["condition"],
                "best_worst_loss_capture_pct": float(best["worst_loss_capture_pct"]),
                "best_global_total_pnl": float(best["global_total_pnl"]),
                "best_prior_refuted_or_insufficient": bool(best["prior_refuted_or_insufficient"]),
            }
        )
    return pd.DataFrame(rows).sort_values(
        ["candidate_count", "best_worst_loss_capture_pct"], ascending=[False, False]
    ).reset_index(drop=True)


def _decision(condition_summary: pd.DataFrame, family_summary: pd.DataFrame) -> dict[str, Any]:
    candidates = condition_summary[condition_summary["stage078_defensive_candidate"].astype(bool)].copy()
    top_rows = condition_summary.head(8).copy()
    return {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "decision": (
            "stage078_has_unrefuted_defensive_pit_candidate_needs_proxy"
            if not candidates.empty
            else "stage078_no_unrefuted_defensive_pit_candidate_keep_searching"
        ),
        "candidate_count": int(len(candidates)),
        "candidate_conditions": candidates["condition"].tolist(),
        "condition_count": int(len(condition_summary)),
        "family_count": int(len(family_summary)),
        "top_condition_snapshot": top_rows[
            [
                "condition",
                "family",
                "worst_loss_capture_pct",
                "global_total_pnl",
                "global_positive_pnl_collision_pct",
                "prior_refuted_or_insufficient",
                "stage078_defensive_candidate",
            ]
        ].to_dict(orient="records"),
        "thresholds": {
            "min_global_count": MIN_GLOBAL_COUNT,
            "min_year_count": MIN_YEAR_COUNT,
            "min_worst_loss_capture_pct": MIN_WORST_LOSS_CAPTURE_PCT,
            "max_global_total_pnl": MAX_GLOBAL_TOTAL_PNL,
            "max_oos_positive_fold_count": MAX_OOS_POSITIVE_FOLD_COUNT,
            "max_positive_pnl_collision_pct": MAX_POSITIVE_PNL_COLLISION_PCT,
        },
    }


def _write_report(condition_summary: pd.DataFrame, family_summary: pd.DataFrame, decision: dict[str, Any]) -> None:
    REPORT_PATH.write_text(
        "\n".join(
            [
                "# Stage078 defensive PIT family audit",
                "",
                f"- 决策：`{decision['decision']}`。",
                "- 类型：只读字段族审计，不改线上、不改共享 AI 池、不接实盘。",
                "- 外部调研：趋势跟随资料支持多市场分散、波动/相关性风险控制，但不支持按历史坏窗口救 TopN/阈值；本阶段只审计当前可见 PIT 字段族。",
                "",
                "## 候选门槛",
                "",
                f"- global count >= `{MIN_GLOBAL_COUNT}`",
                f"- year count >= `{MIN_YEAR_COUNT}`",
                f"- worst loss capture >= `{MIN_WORST_LOSS_CAPTURE_PCT:.2f}%`",
                f"- global total PnL <= `{MAX_GLOBAL_TOTAL_PNL:.2f}`",
                f"- OOS positive fold count <= `{MAX_OOS_POSITIVE_FOLD_COUNT}`",
                f"- positive PnL collision <= `{MAX_POSITIVE_PNL_COLLISION_PCT:.2f}%`",
                "- 已真引擎反证或证据不足的条件不允许成为 Stage078 候选。",
                "",
                "## 字段族摘要",
                "",
                _md_table(family_summary),
                "",
                "## 条件摘要",
                "",
                _md_table(condition_summary, max_rows=20),
                "",
                "## 反思",
                "",
                "- 运行前过拟合反思：否；本阶段先看字段族和既有反证屏蔽，不新增交易规则。",
                "- 运行后过拟合反思：若候选来自已反证字段，不能重复救参；若无新候选，继续扫阈值就是过拟合。",
                "- 运行前继续价值反思：有，Stage077 后需要寻找真正能覆盖剩余左尾的 PIT 信息源。",
                "- 运行后继续价值反思：取决于是否出现未反证候选；若无，应转新外生源或结构不同的账户外层。",
                "",
            ]
        ),
        encoding="utf-8",
    )


def _write_stage_record(condition_summary: pd.DataFrame, family_summary: pd.DataFrame, decision: dict[str, Any]) -> Path:
    stage_path = STAGES_DIR / f"{datetime.now().strftime('%Y%m%d_%H%M')}_stage078_defensive_pit_family_audit.md"
    stage_path.write_text(
        "\n".join(
            [
                "# Stage078 defensive PIT family audit",
                "",
                f"- 时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} CST",
                f"- line_id：`{LINE_ID}`",
                "- 类型：只读字段族审计，不改线上、不改共享 AI 池、不接实盘。",
                "- 外部调研：趋势跟随/managed futures 资料支持分散化、波动与相关性风险控制；本阶段采纳“先做 PIT 字段族覆盖审计”，不采纳继续救 TopN、OI、账户阈值或鸡蛋共享 rerank。",
                "",
                "## 版本变更",
                "",
                f"- 新增参数：`MIN_GLOBAL_COUNT={MIN_GLOBAL_COUNT}`、`MIN_YEAR_COUNT={MIN_YEAR_COUNT}`、`MIN_WORST_LOSS_CAPTURE_PCT={MIN_WORST_LOSS_CAPTURE_PCT}`、`MAX_GLOBAL_TOTAL_PNL={MAX_GLOBAL_TOTAL_PNL}`、`MAX_OOS_POSITIVE_FOLD_COUNT={MAX_OOS_POSITIVE_FOLD_COUNT}`、`MAX_POSITIVE_PNL_COLLISION_PCT={MAX_POSITIVE_PNL_COLLISION_PCT}`。",
                "- 修改参数：无正式交易参数修改。",
                "- 删除参数：无。",
                "- 新增回测结果：无真实资金曲线回测；新增防守型 PIT 字段族覆盖审计。",
                "- 修改回测结果：无。",
                "- 删除回测结果：无。",
                "",
                "## 结果",
                "",
                f"- 决策：`{decision['decision']}`。",
                f"- candidate count：`{decision['candidate_count']}`。",
                f"- candidate conditions：`{decision['candidate_conditions'] or '无'}`。",
                "",
                "## 字段族摘要",
                "",
                _md_table(family_summary),
                "",
                "## 条件摘要",
                "",
                _md_table(condition_summary, max_rows=20),
                "",
                "## 反思",
                "",
                "- 运行前过拟合反思：否；本阶段不写交易规则，只审计字段族是否有未反证防守候选。",
                "- 运行后过拟合反思：若没有未反证候选，继续改阈值或复用已反证字段就是过拟合。",
                "- 运行前继续价值反思：有；目标左尾仍未解决，必须找能覆盖剩余左尾的新证据。",
                "- 运行后继续价值反思：若 candidate count 为 0，则当前已知字段族继续价值低，应找新 PIT 信息源。",
                "",
                "## 后续规划和 TODO",
                "",
                "- 若候选为空：停止用当前 Stage038/Stage071 已知字段族救参，转新外生源或结构不同的账户外层。",
                "- 若候选非空：下一步只能冻结一个未反证条件做 proxy/true-engine，不扫阈值。",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return stage_path


def run() -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    STAGES_DIR.mkdir(parents=True, exist_ok=True)
    features = _read_csv(FEATURE_MATRIX_PATH)
    windows = _read_csv(WINDOW_ENTRIES_PATH)
    condition_summary = summarize_defensive_conditions(features, windows)
    family_summary = summarize_families(condition_summary)
    decision = _decision(condition_summary, family_summary)
    condition_summary.to_csv(CONDITION_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    family_summary.to_csv(FAMILY_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(condition_summary, family_summary, decision)
    stage_path = _write_stage_record(condition_summary, family_summary, decision)
    decision["stage_record_path"] = str(stage_path)
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    return decision


if __name__ == "__main__":
    print(json.dumps(_json_safe(run()), ensure_ascii=False, indent=2))
