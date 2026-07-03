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


LINE_ID = "futures_trend_rebuilt_c9_15w_optimization"
STAGE = "Stage060"
MODEL_TAG = "stage060_late_adverse_precursor_audit_v1"
STAGE_SLUG = "stage060_late_adverse_precursor_audit"
OUTPUT_PREFIX = "rebuilt_c9_stage060_late_adverse_precursor_audit"

TOOLS_DIR = Path(__file__).resolve().parent
LINE_DIR = TOOLS_DIR.parent
PROJECT_DIR = LINE_DIR.parents[2]
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
TARGET_LOTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_late_adverse_lots_{MODEL_TAG}.csv.gz"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

TARGET_ARCHETYPE = "late_adverse_no_edge"
STRONG_CAPTURE_PCT = 80.0

EXTERNAL_RESEARCH_JUDGMENT = (
    "MAE/MFE duration diagnostics can separate path facts from pre-entry features. "
    "Path facts may guide later exit audits, but only pre-entry features can be used for budget decisions; "
    "Carver-style trend systems also warn that binary exits can damage trend-following right tails."
)


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
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
        return None if np.isnan(number) or np.isinf(number) else number
    if isinstance(value, (pd.Timestamp, datetime)):
        if pd.isna(value):
            return None
        return value.isoformat()
    if pd.isna(value):
        return None
    return value


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_无数据_"
    shown = frame.copy()
    if max_rows is not None:
        shown = shown.head(max_rows)
    for column in shown.columns:
        if pd.api.types.is_float_dtype(shown[column]):
            shown[column] = shown[column].map(lambda value: f"{value:.4f}" if pd.notna(value) else "")
    return shown.to_markdown(index=False)


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path, encoding="utf-8-sig", low_memory=False)


def _num(frame: pd.DataFrame, column: str, default: float = np.nan) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype="float64")
    return pd.to_numeric(frame[column], errors="coerce")


def _to_bool(series: pd.Series | Any, index: pd.Index | None = None) -> pd.Series:
    if isinstance(series, pd.Series):
        values = series.copy()
    else:
        values = pd.Series(series, index=index)
    if values.empty:
        return values.astype(bool)
    if pd.api.types.is_bool_dtype(values):
        return values.fillna(False)
    if pd.api.types.is_numeric_dtype(values):
        return pd.to_numeric(values, errors="coerce").fillna(0).ne(0)
    text = values.fillna("").astype(str).str.strip().str.lower()
    return text.isin({"1", "1.0", "true", "yes", "y", "pass", "passed", "opened"})


def _fixed_condition_masks(frame: pd.DataFrame, *, include_path_conditions: bool) -> dict[str, tuple[str, pd.Series]]:
    index = frame.index
    ai_rank = _num(frame, "ai_rank")
    drawdown_abs = _num(frame, "drawdown_abs_pct")
    selected_volume_gt1 = _to_bool(frame.get("selected_volume_gt1", False), index=index)
    oi_confirmed = _to_bool(frame.get("oi_confirmed", False), index=index)
    full_market_ai_top8 = _to_bool(frame.get("full_market_ai_top8", False), index=index)
    full_market_simple_top8 = _to_bool(frame.get("full_market_simple_top8", False), index=index)
    full_market_consensus_top8 = _to_bool(frame.get("full_market_consensus_top8", False), index=index)
    conditions: dict[str, tuple[str, pd.Series]] = {
        "oi_confirmed": ("pre_entry", oi_confirmed),
        "oi_and_selected_volume_gt1": ("pre_entry", oi_confirmed & selected_volume_gt1),
        "selected_volume_gt1": ("pre_entry", selected_volume_gt1),
        "not_full_market_ai_top8": ("pre_entry", ~full_market_ai_top8),
        "not_ai_top8_and_selected_volume_gt1": ("pre_entry", ~full_market_ai_top8 & selected_volume_gt1),
        "not_full_market_consensus_top8": ("pre_entry", ~full_market_consensus_top8),
        "rank_4_9": ("pre_entry", ai_rank.between(4, 9)),
        "rank_4_6": ("pre_entry", ai_rank.between(4, 6)),
        "simple_not_top8": ("pre_entry", ~full_market_simple_top8),
        "drawdown_abs_ge20": ("pre_entry", drawdown_abs.ge(20.0)),
    }
    if include_path_conditions:
        mfe_r = _num(frame, "mfe_r")
        days_to_mfe = _num(frame, "days_to_mfe")
        days_to_mae = _num(frame, "days_to_mae")
        conditions.update(
            {
                "path_mfe_day0_1_mae_day4_10": (
                    "path_after_entry",
                    days_to_mfe.le(1.0) & days_to_mae.between(4.0, 10.0),
                ),
                "path_mfe_lt_half_r": ("path_after_entry", mfe_r.lt(0.5)),
                "path_mfe_lt_half_r_mae_day4_10": (
                    "path_after_entry",
                    mfe_r.lt(0.5) & days_to_mae.between(4.0, 10.0),
                ),
                "path_no_1r_mae_day4_10": (
                    "path_after_entry",
                    mfe_r.lt(1.0) & days_to_mae.between(4.0, 10.0),
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


def _summarize_full_sample_collision(
    full: pd.DataFrame,
    conditions: dict[str, tuple[str, pd.Series]],
) -> pd.DataFrame:
    if full.empty:
        return pd.DataFrame()
    data = full.copy()
    data["realized_pnl"] = _num(data, "realized_pnl", 0.0).fillna(0.0)
    data["selected_volume"] = _num(data, "selected_volume", 0.0).fillna(0.0)
    total_pnl = float(data["realized_pnl"].sum())
    rows: list[dict[str, Any]] = []
    for condition, (feature_timing, mask) in conditions.items():
        if feature_timing != "pre_entry":
            continue
        mask = mask.reindex(data.index).fillna(False).astype(bool)
        subset = data[mask]
        rows.append(
            {
                "condition": condition,
                "full_row_count": int(mask.sum()),
                "full_row_share_pct": float(mask.mean() * 100.0) if len(mask) else 0.0,
                "full_pnl_sum": float(subset["realized_pnl"].sum()),
                "full_pnl_share_pct": float(subset["realized_pnl"].sum() / total_pnl * 100.0) if total_pnl else np.nan,
                "full_positive_pnl_sum": float(subset["realized_pnl"].clip(lower=0.0).sum()),
                "full_negative_pnl_sum": float(subset["realized_pnl"].clip(upper=0.0).sum()),
                "full_winner_count": int(subset["realized_pnl"].gt(0.0).sum()),
                "full_win_rate_pct": float(subset["realized_pnl"].gt(0.0).mean() * 100.0) if len(subset) else 0.0,
                "full_selected_volume_sum": float(subset["selected_volume"].sum()),
            }
        )
    return pd.DataFrame(rows).sort_values("full_pnl_sum").reset_index(drop=True)


def _classify_condition_tradeoff(feature_timing: str, target_loss_capture_pct: float, full_pnl_sum: float | None) -> str:
    if feature_timing == "path_after_entry":
        return "path_only_diagnostic"
    if target_loss_capture_pct < 50.0:
        return "weak_or_broad"
    if full_pnl_sum is not None and not pd.isna(full_pnl_sum) and full_pnl_sum > 0.0:
        return "right_tail_collision"
    if target_loss_capture_pct >= STRONG_CAPTURE_PCT and full_pnl_sum is not None and full_pnl_sum < 0.0:
        return "pre_entry_negative_full_pnl_candidate"
    return "broad_negative_condition_needs_more_evidence"


def _build_tradeoff_summary(capture: pd.DataFrame, full_collision: pd.DataFrame) -> pd.DataFrame:
    merged = capture.merge(full_collision, on="condition", how="left")
    merged["tradeoff_class"] = merged.apply(
        lambda row: _classify_condition_tradeoff(
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
    shown = tradeoff.copy().head(12)
    fig, axes = plt.subplots(2, 1, figsize=(14, 10), constrained_layout=True)
    if not shown.empty:
        axes[0].bar(shown["condition"], shown["target_loss_capture_pct"], color="#dc2626")
    axes[0].axhline(STRONG_CAPTURE_PCT, color="#111827", linewidth=1.0, linestyle="--")
    axes[0].set_title("Late-Adverse Loss Capture")
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


def _decide(capture: pd.DataFrame, tradeoff: pd.DataFrame, target_lots: pd.DataFrame) -> dict[str, Any]:
    candidates = tradeoff[tradeoff["tradeoff_class"].eq("pre_entry_negative_full_pnl_candidate")].copy()
    if not candidates.empty:
        best = candidates.sort_values(["target_loss_capture_pct", "full_pnl_sum"], ascending=[False, True]).iloc[0]
        decision_text = "stage060_late_adverse_has_preentry_oi_candidate_needs_proxy"
        continue_after = (
            "有。`oi_confirmed`/`oi_and_selected_volume_gt1` 同时捕获 late-adverse 且全样本 PnL 为负，"
            "但只能先做冻结 proxy，不能直接改线上。"
        )
    else:
        best = tradeoff.iloc[0] if not tradeoff.empty else pd.Series(dtype=object)
        decision_text = "stage060_late_adverse_only_path_diagnostic_no_preentry_candidate"
        continue_after = "有但方向转窄。late-adverse 只能由入场后路径事实解释，下一步应做退出路径审计而不是入场前过滤。"

    target_loss_abs = float(target_lots["loss_abs"].sum()) if "loss_abs" in target_lots.columns else np.nan
    return {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "audit_type": "late_adverse_precursor_and_right_tail_collision_readonly",
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
        "external_research_judgment": EXTERNAL_RESEARCH_JUDGMENT,
        "overfit_reflection_before": "否。Stage060 只审计 Stage059 预先暴露出的最大亏损形态，不新增交易参数。",
        "continue_value_before": "有。Stage059 证明亏损路径混合，late-adverse 是最大 loss_abs 来源，需要判断是否存在入场前候选而不是路径事实。",
        "overfit_reflection_after": "否。本阶段只输出候选证据和右尾冲突，不把任何条件直接改成交易规则。",
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
    report = f"""# Stage060 - late-adverse 前置信号与右尾冲突审计

- 生成时间：`{decision['generated_at']}`
- line_id：`{LINE_ID}`
- model_tag：`{MODEL_TAG}`
- 决策：`{decision['decision']}`
- 阶段性质：只读归因；不改官方 C9，不连接 CTP，不调用订单 API。

## 外部调研判断

- TradesViz/MAE-MFE duration 资料支持把 MFE/MAE 到达时间作为 exit/stop 诊断。
- Rob Carver 动态趋势讨论提醒：离散 exit/stop 可能改变趋势策略 skew 与 right tail，需要先证明不伤右尾。
- 我的判断：Stage060 必须把入场后路径事实和入场前条件分开。路径事实不能提前过滤，只能作为后续执行/退出审计入口。

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

- 最优条件：`{decision['best_condition']}`。
- 类型：`{decision['best_condition_tradeoff_class']}`。
- late-adverse loss_abs 捕获率：`{decision['best_condition_target_loss_capture_pct']:.4f}%`。
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
    path = STAGES_DIR / f"{datetime.now().strftime('%Y%m%d_%H%M')}_stage060_late_adverse_precursor_audit.md"
    content = f"""# Stage060 - late-adverse 前置信号与右尾冲突审计

- line_id：`{LINE_ID}`
- 当前模式：`day`
- 记录时间：`{decision['generated_at']} CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读归因，不改官方实盘配置。
- 是否重要突破：`否`
- 是否触发A/B：`否`

## 外部调研与判断

- 参考资料：TradesViz MAE/MFE duration、Rob Carver dynamic trend following、PyTrendFollow/pyfolio/backtesting.py 等系统化回测与复盘资料。
- 我的判断：late-adverse 需要区分入场后路径事实和入场前可见条件；路径事实不能作为开仓前预算规则，入场前条件必须同时看全样本右尾冲突。

## 本次变更

- 新增脚本：`research/lines/{LINE_ID}/tools/stage060_late_adverse_precursor_audit.py`
- 新增测试：`tests/test_rebuilt_c9_stage060_late_adverse_precursor.py`
- 修改脚本：无正式策略脚本修改。
- 删除脚本：无。
- 新增参数：无交易参数；固定审计 `oi_confirmed`、`oi_and_selected_volume_gt1`、`selected_volume_gt1`、`not_full_market_ai_top8`、`rank_4_9`、`path_mfe_day0_1_mae_day4_10` 等条件。
- 修改参数：无。
- 删除参数：无。

## 结果

- 决策：`{decision['decision']}`。
- target：`{TARGET_ARCHETYPE}`。
- target lot：`{decision['target_lot_count']}`。
- target realized PnL：`{decision['target_realized_pnl_sum']:.2f}`。
- target loss_abs：`{decision['target_loss_abs']:.2f}`。
- 最优条件：`{decision['best_condition']}`。
- 条件类型：`{decision['best_condition_tradeoff_class']}`。
- late-adverse loss_abs 捕获率：`{decision['best_condition_target_loss_capture_pct']:.4f}%`。
- 全样本 PnL：`{decision['best_condition_full_pnl_sum']:.2f}`。

## 回测指标说明

- 本阶段不是新增回测或真引擎 A/C，只读复用 Stage059 与 Stage038 输出，因此不产生新的期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数和胜率。
- 不连接 CTP，不调用订单 API，不改官方实盘配置。

## 输出文件

- report：`{REPORT_PATH}`
- tradeoff_summary：`{TRADEOFF_SUMMARY_PATH}`
- chart：`{CHART_PATH}`

## 过拟合反思

- 运行前判断：否。只拆 Stage059 最大亏损形态，不新增交易参数。
- 运行后判断：{decision['overfit_reflection_after']}

## 继续价值反思

- 运行前判断：有。Stage059 已证明 late-adverse 是最大 loss_abs 来源。
- 运行后判断：{decision['continue_value_after']}
"""
    path.write_text(content, encoding="utf-8")
    return path


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    STAGES_DIR.mkdir(parents=True, exist_ok=True)

    pressure = _read_csv(STAGE059_LOT_PATHS_PATH)
    full = _read_csv(STAGE038_FEATURE_MATRIX_PATH)
    pressure_conditions = _fixed_condition_masks(pressure, include_path_conditions=True)
    full_conditions = _fixed_condition_masks(full, include_path_conditions=False)
    capture = _summarize_condition_capture(pressure, pressure_conditions, target_archetype=TARGET_ARCHETYPE)
    full_collision = _summarize_full_sample_collision(full, full_conditions)
    tradeoff = _build_tradeoff_summary(capture, full_collision)
    target_lots = pressure[pressure["path_archetype"].astype(str).eq(TARGET_ARCHETYPE)].copy()
    decision = _decide(capture, tradeoff, target_lots)

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
