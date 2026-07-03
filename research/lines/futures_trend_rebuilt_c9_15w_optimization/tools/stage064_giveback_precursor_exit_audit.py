from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from stage063_early_adverse_precursor_audit import (
    _json_safe,
    _md_table,
    _num,
    _read_csv,
    _summarize_full_sample_collision,
    _to_bool,
)


LINE_ID = "futures_trend_rebuilt_c9_15w_optimization"
STAGE = "Stage064"
MODEL_TAG = "stage064_giveback_precursor_exit_audit_v1"
STAGE_SLUG = "stage064_giveback_precursor_exit_audit"
OUTPUT_PREFIX = "rebuilt_c9_stage064_giveback_precursor_exit_audit"

TOOLS_DIR = Path(__file__).resolve().parent
LINE_DIR = TOOLS_DIR.parent
OUTPUT_DIR = LINE_DIR / "outputs" / STAGE_SLUG
STAGES_DIR = LINE_DIR / "stages"

STAGE059_OUTPUT_DIR = LINE_DIR / "outputs" / "stage059_trade_path_excursion_audit"
STAGE059_PREFIX = "rebuilt_c9_stage059_trade_path_excursion_audit"
STAGE059_TAG = "stage059_trade_path_excursion_audit_v1"
STAGE059_LOT_PATHS_PATH = STAGE059_OUTPUT_DIR / f"{STAGE059_PREFIX}_lot_paths_{STAGE059_TAG}.csv.gz"

STAGE038_OUTPUT_DIR = LINE_DIR / "outputs" / "stage038_candidate_pit_feature_matrix_audit"
STAGE038_PREFIX = "rebuilt_c9_stage038_candidate_pit_feature_matrix_audit"
STAGE038_TAG = "stage038_candidate_pit_feature_matrix_audit_v1"
STAGE038_FEATURE_MATRIX_PATH = STAGE038_OUTPUT_DIR / f"{STAGE038_PREFIX}_feature_matrix_{STAGE038_TAG}.csv"

CAPTURE_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_capture_summary_{MODEL_TAG}.csv"
FULL_COLLISION_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_full_collision_summary_{MODEL_TAG}.csv"
TRADEOFF_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_tradeoff_summary_{MODEL_TAG}.csv"
TARGET_LOTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_giveback_lots_{MODEL_TAG}.csv.gz"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

TARGET_ARCHETYPE = "gave_back_favorable_excursion"
STRONG_CAPTURE_PCT = 80.0

EXTERNAL_RESEARCH_SOURCES = [
    "Rob Carver dynamic trend following: https://qoppac.blogspot.com/2020/12/dynamic-trend-following.html",
    "TradeStation MFE graph guide: https://help.tradestation.com/10_00/eng/tradestationhelp/subsystems/spr_topics/report/maximum_favorable_excursion__strategy_performance_report_.htm",
    "TradeMetria MAE/MFE guide: https://trademetria.com/blog/understanding-mae-and-mfe-metrics-a-guide-for-traders/",
    "Investopedia trailing stops: https://www.investopedia.com/terms/t/trailingstop.asp",
    "pysystemtrade GitHub: https://github.com/pst-group/pysystemtrade",
]
EXTERNAL_RESEARCH_JUDGMENT = (
    "Giveback/MFE diagnostics can identify trades that first had favorable excursion and later closed as losses. "
    "For trend following, that does not automatically justify profit-taking: trailing exits can reduce giveback but "
    "also cut the right tail. Stage064 therefore separates pre-entry filters from after-entry exit diagnostics."
)


def _stage064_condition_masks(
    frame: pd.DataFrame,
    *,
    include_path_conditions: bool,
) -> dict[str, tuple[str, pd.Series]]:
    index = frame.index
    ai_rank = _num(frame, "ai_rank")
    selected_volume = _num(frame, "selected_volume")
    drawdown_abs = _num(frame, "drawdown_abs_pct")
    loss_streak = _num(frame, "loss_streak")
    active_positions = _num(frame, "active_positions_before")
    same_direction_corr = _num(frame, "same_direction_correlation_max_corr")
    same_direction_count = _num(frame, "same_direction_correlation_active_count")
    risk_multiplier = _num(frame, "risk_multiplier")

    selected_gt1 = _to_bool(frame.get("selected_volume_gt1", selected_volume.gt(1.0)), index=index)
    oi_confirmed = _to_bool(frame.get("oi_confirmed", False), index=index)
    full_market_ai_top8 = _to_bool(frame.get("full_market_ai_top8", False), index=index)
    full_market_consensus_top8 = _to_bool(frame.get("full_market_consensus_top8", False), index=index)
    loss_streak_ge2 = _to_bool(frame.get("loss_streak_ge2", loss_streak.ge(2.0)), index=index)
    loss_streak_ge3 = _to_bool(frame.get("loss_streak_ge3", loss_streak.ge(3.0)), index=index)
    account_injured = _to_bool(frame.get("account_injured", drawdown_abs.ge(20.0) | loss_streak_ge2), index=index)
    active_ge3 = _to_bool(frame.get("active_positions_ge3", active_positions.ge(3.0)), index=index)

    conditions: dict[str, tuple[str, pd.Series]] = {
        "selected_volume_gt1": ("pre_entry", selected_gt1),
        "selected_volume_ge5": ("pre_entry", selected_volume.ge(5.0)),
        "selected_volume_ge10": ("pre_entry", selected_volume.ge(10.0)),
        "ai_rank_1_3": ("pre_entry", _to_bool(frame.get("ai_rank_1_3", ai_rank.between(1, 3)), index=index)),
        "ai_rank_1_6": ("pre_entry", _to_bool(frame.get("ai_rank_1_6", ai_rank.between(1, 6)), index=index)),
        "ai_rank_1_9": ("pre_entry", _to_bool(frame.get("ai_rank_1_9", ai_rank.between(1, 9)), index=index)),
        "ai_rank_gt9": ("pre_entry", _to_bool(frame.get("ai_rank_gt9", ai_rank.gt(9)), index=index)),
        "rank_4_9": ("pre_entry", ai_rank.between(4, 9)),
        "oi_confirmed": ("pre_entry", oi_confirmed),
        "not_oi_confirmed": ("pre_entry", ~oi_confirmed),
        "full_market_ai_top8": ("pre_entry", full_market_ai_top8),
        "not_full_market_ai_top8": ("pre_entry", ~full_market_ai_top8),
        "full_market_consensus_top8": ("pre_entry", full_market_consensus_top8),
        "not_full_market_consensus_top8": ("pre_entry", ~full_market_consensus_top8),
        "loss_streak_ge2": ("pre_entry", loss_streak_ge2),
        "loss_streak_ge3": ("pre_entry", loss_streak_ge3),
        "drawdown_abs_ge20": ("pre_entry", drawdown_abs.ge(20.0)),
        "drawdown_abs_ge30": ("pre_entry", drawdown_abs.ge(30.0)),
        "account_injured": ("pre_entry", account_injured),
        "active_positions_ge3": ("pre_entry", active_ge3),
        "same_direction_corr_ge60": ("pre_entry", same_direction_corr.ge(0.60)),
        "same_direction_active_count_ge2": ("pre_entry", same_direction_count.ge(2.0)),
        "risk_multiplier_gt1": ("pre_entry", risk_multiplier.gt(1.0)),
        "risk_multiplier_ge1": ("pre_entry", risk_multiplier.ge(1.0)),
    }
    if include_path_conditions:
        days_to_mfe = _num(frame, "days_to_mfe")
        days_to_mae = _num(frame, "days_to_mae")
        mfe_r = _num(frame, "mfe_r")
        mae_r = _num(frame, "mae_r")
        conditions.update(
            {
                "path_mfe_ge1": ("path_after_entry", mfe_r.ge(1.0)),
                "path_mfe_ge2": ("path_after_entry", mfe_r.ge(2.0)),
                "path_mfe_ge3": ("path_after_entry", mfe_r.ge(3.0)),
                "path_mfe_day0_1": ("path_after_entry", days_to_mfe.le(1.0)),
                "path_mfe_day0_3": ("path_after_entry", days_to_mfe.le(3.0)),
                "path_mfe_before_mae": ("path_after_entry", days_to_mfe.lt(days_to_mae)),
                "path_mfe_ge1_and_mae_ge1": ("path_after_entry", mfe_r.ge(1.0) & mae_r.ge(1.0)),
                "path_mfe_ge2_and_mae_after_mfe": (
                    "path_after_entry",
                    mfe_r.ge(2.0) & days_to_mfe.lt(days_to_mae),
                ),
            }
        )
    return conditions


def _summarize_condition_capture(
    pressure: pd.DataFrame,
    conditions: dict[str, tuple[str, pd.Series]],
    *,
    target_archetype: str,
) -> pd.DataFrame:
    if pressure.empty:
        return pd.DataFrame()
    data = pressure.copy()
    data["realized_pnl"] = _num(data, "realized_pnl", 0.0).fillna(0.0)
    data["loss_abs"] = _num(data, "loss_abs", 0.0).fillna(0.0)
    data["selected_volume"] = _num(data, "selected_volume", 0.0).fillna(0.0)
    target = data["path_archetype"].astype(str).eq(target_archetype)
    total_target_loss = float(data.loc[target, "loss_abs"].sum())
    total_pressure_loss = float(data["loss_abs"].sum())
    rows: list[dict[str, Any]] = []
    for condition, (feature_timing, mask) in conditions.items():
        mask = mask.reindex(data.index).fillna(False).astype(bool)
        subset = data[mask]
        target_subset = data[mask & target]
        rows.append(
            {
                "condition": condition,
                "feature_timing": feature_timing,
                "row_count": int(mask.sum()),
                "row_share_pct": float(mask.mean() * 100.0) if len(mask) else 0.0,
                "target_count": int((mask & target).sum()),
                "target_loss_abs": float(target_subset["loss_abs"].sum()),
                "target_loss_capture_pct": (
                    float(target_subset["loss_abs"].sum() / total_target_loss * 100.0)
                    if total_target_loss > 0.0
                    else 0.0
                ),
                "pressure_loss_abs": float(subset["loss_abs"].sum()),
                "pressure_loss_share_pct": (
                    float(subset["loss_abs"].sum() / total_pressure_loss * 100.0)
                    if total_pressure_loss > 0.0
                    else 0.0
                ),
                "pressure_pnl_sum": float(subset["realized_pnl"].sum()),
                "pressure_positive_pnl_sum": float(subset["realized_pnl"].clip(lower=0.0).sum()),
                "pressure_negative_pnl_sum": float(subset["realized_pnl"].clip(upper=0.0).sum()),
                "winner_count": int(subset["realized_pnl"].gt(0.0).sum()),
                "win_rate_pct": float(subset["realized_pnl"].gt(0.0).mean() * 100.0) if len(subset) else 0.0,
                "selected_volume_sum": float(subset["selected_volume"].sum()),
            }
        )
    return pd.DataFrame(rows).sort_values(
        ["target_loss_capture_pct", "pressure_pnl_sum"], ascending=[False, True]
    ).reset_index(drop=True)


def _classify_stage064_tradeoff(feature_timing: str, target_loss_capture_pct: float, full_pnl_sum: float | None) -> str:
    if feature_timing == "path_after_entry":
        return "path_only_exit_diagnostic"
    if full_pnl_sum is not None and not pd.isna(full_pnl_sum) and full_pnl_sum > 0.0 and target_loss_capture_pct >= 50.0:
        return "right_tail_collision"
    if (
        full_pnl_sum is not None
        and not pd.isna(full_pnl_sum)
        and full_pnl_sum < 0.0
        and target_loss_capture_pct >= STRONG_CAPTURE_PCT
    ):
        return "pre_entry_negative_full_pnl_candidate"
    if full_pnl_sum is not None and not pd.isna(full_pnl_sum) and full_pnl_sum < 0.0:
        return "partial_negative_but_below_capture"
    return "weak_or_broad"


def _build_tradeoff_summary(capture: pd.DataFrame, full_collision: pd.DataFrame) -> pd.DataFrame:
    merged = capture.merge(full_collision, on="condition", how="left")
    merged["tradeoff_class"] = merged.apply(
        lambda row: _classify_stage064_tradeoff(
            str(row["feature_timing"]),
            float(row.get("target_loss_capture_pct", 0.0)),
            None if pd.isna(row.get("full_pnl_sum", np.nan)) else float(row.get("full_pnl_sum", np.nan)),
        ),
        axis=1,
    )
    return merged.sort_values(
        ["tradeoff_class", "target_loss_capture_pct", "full_pnl_sum"],
        ascending=[True, False, True],
    ).reset_index(drop=True)


def _plot(tradeoff: pd.DataFrame) -> None:
    shown = tradeoff.copy().head(16)
    fig, axes = plt.subplots(2, 1, figsize=(16, 10), constrained_layout=True)
    if not shown.empty:
        colors = np.where(shown["feature_timing"].eq("path_after_entry"), "#64748b", "#dc2626")
        axes[0].bar(shown["condition"], shown["target_loss_capture_pct"], color=colors)
    axes[0].axhline(STRONG_CAPTURE_PCT, color="#111827", linewidth=1.0, linestyle="--")
    axes[0].set_title("Stage064 Giveback Loss Capture")
    axes[0].set_ylabel("%")
    axes[0].tick_params(axis="x", rotation=30)
    axes[0].grid(True, axis="y", alpha=0.25)

    pre = shown[shown["feature_timing"].eq("pre_entry")]
    if not pre.empty:
        colors = np.where(pre["full_pnl_sum"].fillna(0.0).lt(0.0), "#16a34a", "#f97316")
        axes[1].bar(pre["condition"], pre["full_pnl_sum"], color=colors)
    axes[1].axhline(0.0, color="#111827", linewidth=1.0)
    axes[1].set_title("Full-Sample PnL of Pre-Entry Conditions")
    axes[1].tick_params(axis="x", rotation=30)
    axes[1].grid(True, axis="y", alpha=0.25)
    fig.savefig(CHART_PATH, dpi=160)
    plt.close(fig)


def _stage064_decision(tradeoff: pd.DataFrame, target_lots: pd.DataFrame) -> dict[str, Any]:
    candidates = tradeoff[tradeoff["tradeoff_class"].eq("pre_entry_negative_full_pnl_candidate")].copy()
    if not candidates.empty:
        best = candidates.sort_values(["target_loss_capture_pct", "full_pnl_sum"], ascending=[False, True]).iloc[0]
        decision_text = "stage064_giveback_has_preentry_candidate_needs_proxy"
        continue_after = "有。存在高捕获且全样本 PnL 为负的入场前条件，下一步只能先做冻结 proxy/真引擎探针，不能直接改线上。"
    else:
        pre_rows = tradeoff[tradeoff["feature_timing"].eq("pre_entry")]
        path_rows = tradeoff[tradeoff["feature_timing"].eq("path_after_entry")]
        if not pre_rows.empty:
            best = pre_rows.sort_values(["target_loss_capture_pct", "full_pnl_sum"], ascending=[False, True]).iloc[0]
        elif not path_rows.empty:
            best = path_rows.sort_values(["target_loss_capture_pct"], ascending=False).iloc[0]
        else:
            best = pd.Series(dtype=object)
        decision_text = "stage064_giveback_no_clean_preentry_candidate_keep_exit_diagnostic"
        continue_after = (
            "有但不能直接交易化。giveback 的高捕获证据主要是入场后 MFE/MAE 路径事实；"
            "入场前条件若撞全样本右尾，就不能变成预算过滤。下一步若继续，只能做低自由度退出路径审计或账户外层设计。"
        )
    target_loss_abs = float(target_lots["loss_abs"].sum()) if "loss_abs" in target_lots.columns else np.nan
    return {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "audit_type": "giveback_precursor_and_exit_path_collision_readonly",
        "decision": decision_text,
        "strategy_changed": False,
        "official_live_config_changed": False,
        "true_engine": False,
        "order_api_called": False,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "ctp_connected": False,
        "target_archetype": TARGET_ARCHETYPE,
        "target_lot_count": int(len(target_lots)),
        "target_realized_pnl_sum": float(target_lots["realized_pnl"].sum()) if "realized_pnl" in target_lots.columns else np.nan,
        "target_loss_abs": target_loss_abs,
        "best_condition": str(best.get("condition", "")) if not best.empty else "",
        "best_condition_tradeoff_class": str(best.get("tradeoff_class", "")) if not best.empty else "",
        "best_condition_target_loss_capture_pct": (
            float(best.get("target_loss_capture_pct", np.nan)) if not best.empty else np.nan
        ),
        "best_condition_full_pnl_sum": float(best.get("full_pnl_sum", np.nan)) if not best.empty else np.nan,
        "external_research_sources": EXTERNAL_RESEARCH_SOURCES,
        "external_research_judgment": EXTERNAL_RESEARCH_JUDGMENT,
        "overfit_reflection_before": "否。Stage064 只审计 Stage059 预先暴露出的 giveback 亏损形态，不新增交易参数。",
        "continue_value_before": "有。Stage059 证明 giveback 是第三类压力亏损来源，需要判断它是入场前可筛，还是只能做退出路径诊断。",
        "overfit_reflection_after": "否。本阶段只输出候选证据、路径事实和右尾冲突，不把任何条件直接改成交易规则。",
        "continue_value_after": continue_after,
        "outputs": {
            "capture_summary": str(CAPTURE_SUMMARY_PATH),
            "full_collision_summary": str(FULL_COLLISION_SUMMARY_PATH),
            "tradeoff_summary": str(TRADEOFF_SUMMARY_PATH),
            "target_lots": str(TARGET_LOTS_PATH),
            "chart": str(CHART_PATH),
            "decision": str(DECISION_PATH),
            "report": str(REPORT_PATH),
        },
    }


def _write_report(decision: dict[str, Any], capture: pd.DataFrame, full_collision: pd.DataFrame, tradeoff: pd.DataFrame) -> None:
    report = f"""# Stage064 - giveback 前置信号与退出路径审计

- 生成时间：`{decision['generated_at']}`
- line_id：`{LINE_ID}`
- model_tag：`{MODEL_TAG}`
- 决策：`{decision['decision']}`
- 阶段性质：只读归因；不改官方 C9，不连接 CTP，不调用订单 API。

## 外部调研判断

- 参考：{'; '.join(EXTERNAL_RESEARCH_SOURCES)}
- 我的判断：MFE/giveback 可以提示退出和 trailing stop 候选，但趋势跟随必须保护右尾；任何 giveback 规则都必须区分入场前条件和入场后路径事实。

## 输入

- Stage059 lot paths：`{STAGE059_LOT_PATHS_PATH}`
- Stage038 full feature matrix：`{STAGE038_FEATURE_MATRIX_PATH}`

## 目标形态

- target：`{TARGET_ARCHETYPE}`
- target lot：`{decision['target_lot_count']}`
- target realized PnL：`{decision['target_realized_pnl_sum']:.2f}`
- target loss_abs：`{decision['target_loss_abs']:.2f}`

## Capture Summary

{_md_table(capture)}

## Full Sample Collision

{_md_table(full_collision)}

## Tradeoff Summary

{_md_table(tradeoff)}

## 判断

- 最优入场前条件：`{decision['best_condition']}`。
- 类型：`{decision['best_condition_tradeoff_class']}`。
- giveback loss_abs 捕获率：`{decision['best_condition_target_loss_capture_pct']:.4f}%`。
- 全样本 PnL：`{decision['best_condition_full_pnl_sum']:.2f}`。
- 过拟合反思：{decision['overfit_reflection_after']}
- 继续价值反思：{decision['continue_value_after']}

## 输出文件

- capture_summary：`{CAPTURE_SUMMARY_PATH}`
- full_collision_summary：`{FULL_COLLISION_SUMMARY_PATH}`
- tradeoff_summary：`{TRADEOFF_SUMMARY_PATH}`
- target_lots：`{TARGET_LOTS_PATH}`
- chart：`{CHART_PATH}`
- decision：`{DECISION_PATH}`
- report：`{REPORT_PATH}`
"""
    REPORT_PATH.write_text(report, encoding="utf-8")


def _write_stage_record(decision: dict[str, Any]) -> Path:
    path = STAGES_DIR / f"{datetime.now().strftime('%Y%m%d_%H%M')}_stage064_giveback_precursor_exit_audit.md"
    content = f"""# Stage064 - giveback 前置信号与退出路径审计

- line_id：`{LINE_ID}`
- 当前模式：`day`
- 记录时间：`{decision['generated_at']} CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读归因，不改官方实盘配置。
- 是否重要突破：`否`
- 是否触发A/B：`否`

## 外部调研与判断

- 参考资料：Rob Carver dynamic trend following、TradeStation MFE graph、TradeMetria MAE/MFE、Investopedia trailing stops、pysystemtrade。
- 我的判断：giveback 方向不能直接止盈化；只有入场前可见且不撞全样本右尾的条件才可能进入预算 proxy，入场后 MFE/MAE 只能先保留为退出路径审计入口。

## 本次变更

- 新增脚本：`research/lines/{LINE_ID}/tools/stage064_giveback_precursor_exit_audit.py`
- 新增测试：`tests/test_rebuilt_c9_stage064_giveback_precursor.py`
- 修改脚本：无正式策略脚本修改。
- 删除脚本：无。
- 新增参数：无交易参数；固定审计入场前质量/账户/相关性条件和 `path_mfe_ge1/ge2/ge3`、`path_mfe_before_mae` 等 path diagnostic 条件。
- 修改参数：无。
- 删除参数：无。

## 结果

- 决策：`{decision['decision']}`。
- target：`{TARGET_ARCHETYPE}`。
- target lot：`{decision['target_lot_count']}`。
- target realized PnL：`{decision['target_realized_pnl_sum']:.2f}`。
- target loss_abs：`{decision['target_loss_abs']:.2f}`。
- 最优入场前条件：`{decision['best_condition']}`。
- 条件类型：`{decision['best_condition_tradeoff_class']}`。
- giveback loss_abs 捕获率：`{decision['best_condition_target_loss_capture_pct']:.4f}%`。
- 全样本 PnL：`{decision['best_condition_full_pnl_sum']:.2f}`。

## 回测指标说明

- 本阶段不是新增回测或真引擎 A/C，只读复用 Stage059 与 Stage038 输出，因此不产生新的期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数和胜率。
- 不连接 CTP，不调用订单 API，不改官方实盘配置。

## 输出文件

- report：`{REPORT_PATH}`
- tradeoff_summary：`{TRADEOFF_SUMMARY_PATH}`
- chart：`{CHART_PATH}`

## 过拟合反思

- 运行前判断：否。只拆 Stage059 第三类 giveback 亏损形态，不新增交易参数。
- 运行后判断：{decision['overfit_reflection_after']}

## 继续价值反思

- 运行前判断：有。Stage059 已证明 giveback 是压力亏损的独立来源。
- 运行后判断：{decision['continue_value_after']}
"""
    path.write_text(content, encoding="utf-8")
    return path


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    STAGES_DIR.mkdir(parents=True, exist_ok=True)

    pressure = _read_csv(STAGE059_LOT_PATHS_PATH)
    full = _read_csv(STAGE038_FEATURE_MATRIX_PATH)
    pressure_conditions = _stage064_condition_masks(pressure, include_path_conditions=True)
    full_conditions = _stage064_condition_masks(full, include_path_conditions=False)
    capture = _summarize_condition_capture(pressure, pressure_conditions, target_archetype=TARGET_ARCHETYPE)
    full_collision = _summarize_full_sample_collision(full, full_conditions)
    tradeoff = _build_tradeoff_summary(capture, full_collision)
    target_lots = pressure[pressure["path_archetype"].astype(str).eq(TARGET_ARCHETYPE)].copy()
    decision = _stage064_decision(tradeoff, target_lots)

    _plot(tradeoff)
    capture.to_csv(CAPTURE_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    full_collision.to_csv(FULL_COLLISION_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    tradeoff.to_csv(TRADEOFF_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    target_lots.to_csv(TARGET_LOTS_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(decision, capture, full_collision, tradeoff)
    stage_record = _write_stage_record(decision)
    decision["stage_record"] = str(stage_record)
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
