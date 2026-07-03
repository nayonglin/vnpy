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
STAGE = "Stage059"
MODEL_TAG = "stage059_trade_path_excursion_audit_v1"
STAGE_SLUG = "stage059_trade_path_excursion_audit"
OUTPUT_PREFIX = "rebuilt_c9_stage059_trade_path_excursion_audit"

TOOLS_DIR = Path(__file__).resolve().parent
LINE_DIR = TOOLS_DIR.parent
PROJECT_DIR = LINE_DIR.parents[2]
OUTPUT_DIR = LINE_DIR / "outputs" / STAGE_SLUG
STAGES_DIR = LINE_DIR / "stages"

STAGE055_OUTPUT_DIR = LINE_DIR / "outputs" / "stage055_new_entry_signal_budget_audit"
STAGE055_PREFIX = "rebuilt_c9_stage055_new_entry_signal_budget_audit"
STAGE055_TAG = "stage055_new_entry_signal_budget_audit_v1"
STAGE055_CLOSED_LOTS_PATH = STAGE055_OUTPUT_DIR / f"{STAGE055_PREFIX}_closed_lots_{STAGE055_TAG}.csv.gz"
STAGE055_WINDOW_ENTRIES_PATH = STAGE055_OUTPUT_DIR / f"{STAGE055_PREFIX}_stage054_window_entries_{STAGE055_TAG}.csv"

LOT_PATHS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_lot_paths_{MODEL_TAG}.csv.gz"
ARCHETYPE_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_archetype_summary_{MODEL_TAG}.csv"
MAE_TIMING_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_mae_timing_summary_{MODEL_TAG}.csv"
PRODUCT_DIRECTION_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_direction_summary_{MODEL_TAG}.csv"
SOURCE_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_source_summary_{MODEL_TAG}.csv"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

EXTERNAL_RESEARCH_JUDGMENT = (
    "MAE/MFE and duration analysis is a diagnostic layer: it can tell whether losses appear before any favorable "
    "excursion or after a trade once had edge, but it is not sufficient by itself to create a trading rule."
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


def _read_csv(path: Path, **kwargs: Any) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path, encoding="utf-8-sig", low_memory=False, **kwargs)


def _num(frame: pd.DataFrame, column: str, default: float = np.nan) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype="float64")
    return pd.to_numeric(frame[column], errors="coerce")


def _as_float(value: Any, default: float = np.nan) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if np.isnan(number) or np.isinf(number):
        return default
    return number


def _mae_timing_bucket(days: Any) -> str:
    number = _as_float(days)
    if np.isnan(number):
        return "missing"
    if number <= 0:
        return "day0"
    if number <= 3:
        return "day1_3"
    if number <= 10:
        return "day4_10"
    if number <= 30:
        return "day11_30"
    return "day31_plus"


def _mfe_timing_bucket(days: Any) -> str:
    number = _as_float(days)
    if np.isnan(number):
        return "missing"
    if number <= 0:
        return "day0"
    if number <= 3:
        return "day1_3"
    if number <= 10:
        return "day4_10"
    if number <= 30:
        return "day11_30"
    return "day31_plus"


def _classify_path_archetype(row: pd.Series) -> str:
    realized_pnl = _as_float(row.get("realized_pnl"), 0.0)
    if realized_pnl > 0.0:
        return "winner"

    mfe_r = _as_float(row.get("mfe_r"), 0.0)
    days_to_mae = _as_float(row.get("days_to_mae"))
    if mfe_r >= 1.0:
        return "gave_back_favorable_excursion"
    if not np.isnan(days_to_mae) and days_to_mae <= 3:
        return "early_adverse_no_edge"
    if not np.isnan(days_to_mae) and days_to_mae > 3:
        return "late_adverse_no_edge"
    return "loss_unclassified"


def _summarize_path_archetypes(lots: pd.DataFrame, group_columns: list[str]) -> pd.DataFrame:
    if lots.empty:
        return pd.DataFrame(columns=[*group_columns, "lot_count", "realized_pnl_sum", "loss_abs_sum"])

    data = lots.copy()
    data["realized_pnl"] = _num(data, "realized_pnl", 0.0).fillna(0.0)
    data["selected_volume"] = _num(data, "selected_volume", 0.0).fillna(0.0)
    data["volume"] = _num(data, "volume", 0.0).fillna(0.0)
    data["mfe_r"] = _num(data, "mfe_r", 0.0)
    data["mae_r"] = _num(data, "mae_r", 0.0)
    data["days_to_mae"] = _num(data, "days_to_mae", np.nan)
    data["days_to_mfe"] = _num(data, "days_to_mfe", np.nan)
    if "loss_abs" not in data.columns:
        data["loss_abs"] = (-data["realized_pnl"]).clip(lower=0.0)
    else:
        data["loss_abs"] = _num(data, "loss_abs", 0.0).fillna(0.0)
    data["winner_flag"] = data["realized_pnl"].gt(0.0)

    summary = (
        data.groupby(group_columns, dropna=False)
        .agg(
            lot_count=("realized_pnl", "size"),
            winner_count=("winner_flag", "sum"),
            realized_pnl_sum=("realized_pnl", "sum"),
            loss_abs_sum=("loss_abs", "sum"),
            selected_volume_sum=("selected_volume", "sum"),
            volume_sum=("volume", "sum"),
            mean_mfe_r=("mfe_r", "mean"),
            median_mfe_r=("mfe_r", "median"),
            mean_mae_r=("mae_r", "mean"),
            median_mae_r=("mae_r", "median"),
            mean_days_to_mae=("days_to_mae", "mean"),
            mean_days_to_mfe=("days_to_mfe", "mean"),
        )
        .reset_index()
    )
    total_loss_abs = float(summary["loss_abs_sum"].sum())
    summary["loss_abs_share_pct"] = np.where(
        total_loss_abs > 0.0,
        summary["loss_abs_sum"] / total_loss_abs * 100.0,
        0.0,
    )
    summary["win_rate_pct"] = np.where(
        summary["lot_count"].gt(0),
        summary["winner_count"] / summary["lot_count"] * 100.0,
        0.0,
    )
    return summary.sort_values(["loss_abs_sum", "realized_pnl_sum"], ascending=[False, True]).reset_index(drop=True)


def _prepare_lot_paths(closed_lots: pd.DataFrame, window_entries: pd.DataFrame) -> pd.DataFrame:
    entries = window_entries.copy()
    closed = closed_lots.copy()
    for frame in (entries, closed):
        frame["requested_start"] = frame["requested_start"].astype(str)
        frame["open_trade_id"] = frame["open_trade_id"].astype(str)

    path_columns = [
        "requested_start",
        "open_trade_id",
        "lot_id",
        "close_trade_id",
        "entry_price",
        "exit_price",
        "size",
        "stop_distance",
        "entry_risk_distance_pct",
        "path_bar_count",
        "mfe_cash",
        "mae_cash",
        "mfe_r",
        "mae_r",
        "exit_efficiency",
        "days_to_mfe",
        "days_to_mae",
        "risk_multiplier_bucket",
        "loss_streak_bucket",
        "active_positions_bucket",
        "ai_rank_bucket",
        "rsi_bucket",
        "stop_distance_bucket",
        "recovery_bucket",
        "streak_recovery_bucket",
        "breakout_bucket",
    ]
    path_columns = [column for column in path_columns if column in closed.columns]
    path_metrics = closed[path_columns].drop_duplicates(["requested_start", "open_trade_id"])
    result = entries.merge(path_metrics, on=["requested_start", "open_trade_id"], how="left", validate="one_to_one")

    for date_column in ["entry_date", "exit_date", "entry_candidate_signal_date", "full_market_eval_date"]:
        if date_column in result.columns:
            result[date_column] = pd.to_datetime(result[date_column], errors="coerce").dt.date.astype(str)

    result["realized_pnl"] = _num(result, "realized_pnl", 0.0).fillna(0.0)
    result["selected_volume"] = _num(result, "selected_volume", 0.0).fillna(0.0)
    result["volume"] = _num(result, "volume", 0.0).fillna(0.0)
    result["path_missing"] = _num(result, "mfe_r", np.nan).isna() | _num(result, "mae_r", np.nan).isna()
    result["mfe_r"] = _num(result, "mfe_r", 0.0).fillna(0.0)
    result["mae_r"] = _num(result, "mae_r", 0.0).fillna(0.0)
    result["days_to_mae"] = _num(result, "days_to_mae", np.nan)
    result["days_to_mfe"] = _num(result, "days_to_mfe", np.nan)
    result["loss_abs"] = (-result["realized_pnl"]).clip(lower=0.0)
    result["mae_timing_bucket"] = result["days_to_mae"].map(_mae_timing_bucket)
    result["mfe_timing_bucket"] = result["days_to_mfe"].map(_mfe_timing_bucket)
    result["path_archetype"] = result.apply(_classify_path_archetype, axis=1)
    result["mfe_reached_1r"] = result["mfe_r"].ge(1.0)
    result["mae_reached_1r"] = result["mae_r"].ge(1.0)
    result["mae_before_mfe"] = result["days_to_mae"].lt(result["days_to_mfe"])
    return result


def _plot(archetype_summary: pd.DataFrame, mae_summary: pd.DataFrame, product_summary: pd.DataFrame) -> None:
    fig, axes = plt.subplots(3, 1, figsize=(14, 14), constrained_layout=True)

    archetype = archetype_summary.copy()
    if not archetype.empty:
        axes[0].bar(archetype["path_archetype"], archetype["loss_abs_sum"], color="#dc2626", label="loss_abs")
        axes[0].plot(archetype["path_archetype"], archetype["realized_pnl_sum"], color="#2563eb", marker="o", label="realized_pnl")
    axes[0].set_title("Stage059 Path Archetype Loss Attribution")
    axes[0].tick_params(axis="x", rotation=20)
    axes[0].grid(True, axis="y", alpha=0.25)
    axes[0].legend(loc="best")

    mae = mae_summary.copy()
    if not mae.empty:
        order = ["day0", "day1_3", "day4_10", "day11_30", "day31_plus", "missing"]
        mae["bucket_order"] = mae["mae_timing_bucket"].map({name: i for i, name in enumerate(order)}).fillna(99)
        mae = mae.sort_values("bucket_order")
        axes[1].bar(mae["mae_timing_bucket"], mae["loss_abs_sum"], color="#f97316")
    axes[1].set_title("MAE Timing Loss Abs")
    axes[1].grid(True, axis="y", alpha=0.25)

    product = product_summary.copy()
    if not product.empty:
        product["product_direction"] = product["product"].astype(str) + " " + product["direction"].astype(str)
        top = product.groupby("product_direction", dropna=False)["loss_abs_sum"].sum().sort_values(ascending=False).head(12)
        axes[2].bar(top.index, top.values, color="#7c3aed")
    axes[2].set_title("Top Product Direction Loss Abs")
    axes[2].tick_params(axis="x", rotation=30)
    axes[2].grid(True, axis="y", alpha=0.25)

    fig.savefig(CHART_PATH, dpi=160)
    plt.close(fig)


def _decide(lot_paths: pd.DataFrame, archetype_summary: pd.DataFrame) -> dict[str, Any]:
    losses = lot_paths[lot_paths["realized_pnl"].le(0.0)].copy()
    total_loss_abs = float(losses["loss_abs"].sum())
    type_share = archetype_summary.set_index("path_archetype")["loss_abs_share_pct"].to_dict()
    early_share = float(type_share.get("early_adverse_no_edge", 0.0))
    giveback_share = float(type_share.get("gave_back_favorable_excursion", 0.0))
    late_share = float(type_share.get("late_adverse_no_edge", 0.0))

    if giveback_share >= 50.0:
        decision_text = "stage059_pressure_losses_dominated_by_giveback_need_exit_path_audit"
        continue_after = "有。亏损主要来自曾经出现有利浮盈后的回吐，下一步应只读审计退出/锁盈/回吐结构，而不是再压开仓预算。"
    elif early_share >= 50.0:
        decision_text = "stage059_pressure_losses_dominated_by_early_adverse_need_entry_confirmation_audit"
        continue_after = "有。亏损主要在入场后三个交易日内出现最大逆行且缺少 1R 有利波动，下一步应审计开仓日/早段确认，而不是简单砍右尾预算。"
    elif late_share >= 50.0:
        decision_text = "stage059_pressure_losses_dominated_by_late_adverse_need_holding_path_audit"
        continue_after = "有。亏损主要不是开仓早期，下一步应审计持仓中后段环境和退出路径。"
    else:
        decision_text = "stage059_pressure_losses_mixed_path_keep_readonly"
        continue_after = "有但需收窄。亏损路径混合，下一步应按亏损形态拆成独立假设，不要把所有压力窗口写成一个规则。"

    top = archetype_summary.iloc[0] if not archetype_summary.empty else pd.Series(dtype=object)
    return {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "audit_type": "mae_mfe_trade_path_excursion_readonly",
        "decision": decision_text,
        "strategy_changed": False,
        "official_live_config_changed": False,
        "true_engine": False,
        "order_api_called": False,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "ctp_connected": False,
        "input_closed_lots": int(len(lot_paths)),
        "loss_lot_count": int(len(losses)),
        "winner_lot_count": int(lot_paths["realized_pnl"].gt(0.0).sum()),
        "realized_pnl_sum": float(lot_paths["realized_pnl"].sum()),
        "total_loss_abs": total_loss_abs,
        "top_path_archetype": str(top.get("path_archetype", "")) if not top.empty else "",
        "top_path_loss_abs_share_pct": float(top.get("loss_abs_share_pct", np.nan)) if not top.empty else np.nan,
        "early_adverse_loss_abs_share_pct": early_share,
        "giveback_loss_abs_share_pct": giveback_share,
        "late_adverse_loss_abs_share_pct": late_share,
        "external_research_judgment": EXTERNAL_RESEARCH_JUDGMENT,
        "overfit_reflection_before": "否。Stage059 是固定 MAE/MFE 路径归因，不按品种、方向、日期、TopN 或参数改策略。",
        "continue_value_before": "有。Stage058 已反证固定预算 proxy，需要知道压力亏损到底发生在入场早期、盈利回吐后，还是持仓后段。",
        "overfit_reflection_after": "否。本阶段只读复用既有 closed-lot 路径字段，没有新增交易参数或候选规则。",
        "continue_value_after": continue_after,
        "outputs": {
            "lot_paths": str(LOT_PATHS_PATH),
            "archetype_summary": str(ARCHETYPE_SUMMARY_PATH),
            "mae_timing_summary": str(MAE_TIMING_SUMMARY_PATH),
            "product_direction_summary": str(PRODUCT_DIRECTION_SUMMARY_PATH),
            "source_summary": str(SOURCE_SUMMARY_PATH),
            "chart": str(CHART_PATH),
            "decision": str(DECISION_PATH),
            "report": str(REPORT_PATH),
        },
    }


def _write_report(
    decision: dict[str, Any],
    archetype_summary: pd.DataFrame,
    mae_summary: pd.DataFrame,
    product_summary: pd.DataFrame,
    source_summary: pd.DataFrame,
) -> None:
    report = f"""# Stage059 - 交易路径 MAE/MFE 归因

- 生成时间：`{decision['generated_at']}`
- line_id：`{LINE_ID}`
- model_tag：`{MODEL_TAG}`
- 决策：`{decision['decision']}`
- 阶段性质：只读路径归因；不改官方 C9，不连接 CTP，不调用订单 API。

## 外部调研判断

- TradesViz、TradeMetria、NinjaTrader 等交易复盘资料都把 MAE/MFE 与持仓时长用于识别止损、退出和信号质量问题。
- 我的判断：MAE/MFE 能回答“坏交易是刚入场就错，还是先有浮盈再回吐”，但不能单独生成交易规则；下一步仍必须冻结低自由度假设后复验。

## 输入与口径

- closed lots：`{STAGE055_CLOSED_LOTS_PATH}`
- window entries：`{STAGE055_WINDOW_ENTRIES_PATH}`
- 窗口样本行数：`{decision['input_closed_lots']}`
- realized PnL：`{decision['realized_pnl_sum']:.2f}`
- loss_abs：`{decision['total_loss_abs']:.2f}`

## 路径形态汇总

{_md_table(archetype_summary)}

## MAE 发生时点

{_md_table(mae_summary)}

## 产品方向 Top 归因

{_md_table(product_summary, max_rows=20)}

## Source 归因

{_md_table(source_summary, max_rows=20)}

## 判断

- 主形态：`{decision['top_path_archetype']}`，loss_abs 占比 `{decision['top_path_loss_abs_share_pct']:.4f}%`。
- early adverse 占比：`{decision['early_adverse_loss_abs_share_pct']:.4f}%`。
- giveback 占比：`{decision['giveback_loss_abs_share_pct']:.4f}%`。
- late adverse 占比：`{decision['late_adverse_loss_abs_share_pct']:.4f}%`。
- 过拟合反思：{decision['overfit_reflection_after']}
- 继续价值反思：{decision['continue_value_after']}

## 输出文件

- lot_paths：`{LOT_PATHS_PATH}`
- archetype_summary：`{ARCHETYPE_SUMMARY_PATH}`
- mae_timing_summary：`{MAE_TIMING_SUMMARY_PATH}`
- product_direction_summary：`{PRODUCT_DIRECTION_SUMMARY_PATH}`
- source_summary：`{SOURCE_SUMMARY_PATH}`
- chart：`{CHART_PATH}`
- decision：`{DECISION_PATH}`
- report：`{REPORT_PATH}`
"""
    REPORT_PATH.write_text(report, encoding="utf-8")


def _write_stage_record(decision: dict[str, Any]) -> Path:
    path = STAGES_DIR / f"{datetime.now().strftime('%Y%m%d_%H%M')}_stage059_trade_path_excursion_audit.md"
    content = f"""# Stage059 - 交易路径 MAE/MFE 归因

- line_id：`{LINE_ID}`
- 当前模式：`day`
- 记录时间：`{decision['generated_at']} CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读路径归因，不改官方实盘配置。
- 是否重要突破：`否`
- 是否触发A/B：`否`

## 外部调研与判断

- 参考资料：TradesViz MAE/MFE duration、TradeMetria MAE/MFE guide、NinjaTrader futures MAE risk、trend-following managed futures 资料。
- 我的判断：Stage059 只用 MAE/MFE 和持仓时长做亏损路径诊断，不用亏损品种、方向、日期或阈值直接写策略。

## 本次变更

- 新增脚本：`research/lines/{LINE_ID}/tools/stage059_trade_path_excursion_audit.py`
- 新增测试：`tests/test_rebuilt_c9_stage059_trade_path_excursion.py`
- 修改脚本：无正式策略脚本修改。
- 删除脚本：无。
- 新增参数：无交易参数；路径分类固定为 `early_adverse_no_edge`、`gave_back_favorable_excursion`、`late_adverse_no_edge`、`winner`。
- 修改参数：无。
- 删除参数：无。

## 结果

- 决策：`{decision['decision']}`。
- 样本行数：`{decision['input_closed_lots']}`。
- 亏损 lot 数：`{decision['loss_lot_count']}`。
- 赢家 lot 数：`{decision['winner_lot_count']}`。
- realized PnL：`{decision['realized_pnl_sum']:.2f}`。
- loss_abs：`{decision['total_loss_abs']:.2f}`。
- 主形态：`{decision['top_path_archetype']}`。
- 主形态 loss_abs 占比：`{decision['top_path_loss_abs_share_pct']:.4f}%`。
- early adverse loss_abs 占比：`{decision['early_adverse_loss_abs_share_pct']:.4f}%`。
- giveback loss_abs 占比：`{decision['giveback_loss_abs_share_pct']:.4f}%`。
- late adverse loss_abs 占比：`{decision['late_adverse_loss_abs_share_pct']:.4f}%`。

## 回测指标说明

- 本阶段不是新增回测或真引擎 A/C，只读复用 Stage055 逐笔结果，因此不产生新的期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数和胜率。
- 不连接 CTP，不调用订单 API，不改官方实盘配置。

## 输出文件

- report：`{REPORT_PATH}`
- archetype_summary：`{ARCHETYPE_SUMMARY_PATH}`
- chart：`{CHART_PATH}`

## 过拟合反思

- 运行前判断：否。只做固定路径归因，不改交易参数。
- 运行后判断：{decision['overfit_reflection_after']}

## 继续价值反思

- 运行前判断：有。Stage058 后需要确认压力亏损是入场早错、盈利回吐还是后段持仓问题。
- 运行后判断：{decision['continue_value_after']}
"""
    path.write_text(content, encoding="utf-8")
    return path


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    STAGES_DIR.mkdir(parents=True, exist_ok=True)

    closed_lots = _read_csv(STAGE055_CLOSED_LOTS_PATH)
    window_entries = _read_csv(STAGE055_WINDOW_ENTRIES_PATH)
    lot_paths = _prepare_lot_paths(closed_lots, window_entries)
    archetype_summary = _summarize_path_archetypes(lot_paths, ["path_archetype"])
    mae_summary = _summarize_path_archetypes(lot_paths, ["mae_timing_bucket"])
    product_summary = _summarize_path_archetypes(lot_paths, ["product", "direction", "path_archetype"])
    source_summary = _summarize_path_archetypes(lot_paths, ["requested_start", "path_archetype"])
    decision = _decide(lot_paths, archetype_summary)

    _plot(archetype_summary, mae_summary, product_summary)
    lot_paths.to_csv(LOT_PATHS_PATH, index=False, encoding="utf-8-sig")
    archetype_summary.to_csv(ARCHETYPE_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    mae_summary.to_csv(MAE_TIMING_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    product_summary.to_csv(PRODUCT_DIRECTION_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    source_summary.to_csv(SOURCE_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(decision, archetype_summary, mae_summary, product_summary, source_summary)
    stage_record = _write_stage_record(decision)
    decision["stage_record"] = str(stage_record)
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
