from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import sys
from typing import Any

import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[4]
TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import stage020_stage013_high_quality_add_risk_proxy as s020


ORIGINAL_STAGE020_DECISION = s020._decision
LINE_ID = "futures_trend_rebuilt_c9_15w_optimization"
STAGE = "Stage033"
MODEL_TAG = "stage033_rank19_early_quality_add_risk_proxy_v1"
OUTPUT_PREFIX = "rebuilt_c9_stage033_rank19_early_quality_add_risk_proxy"
TAG_COLUMN = "label_rank_1_9_and_entry_or_first_aligned"
ADD_RISK_FRACTION = 0.25

LINE_DIR = PROJECT_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage033_rank19_early_quality_add_risk_proxy"
STAGE_RECORD_DIR = LINE_DIR / "stages"

LOT_DELTAS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_lot_deltas_{MODEL_TAG}.csv"
CURVES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv"
SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
ANNUAL_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_annual_returns_{MODEL_TAG}.csv"
GOAL_AGGREGATE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_goal_aggregate_{MODEL_TAG}.csv"
GOAL_TO_FINAL_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_goal_to_final_windows_{MODEL_TAG}.csv"
GOAL_FIXED_HORIZON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_goal_fixed_horizon_windows_{MODEL_TAG}.csv"
GOAL_WORST_WINDOWS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_goal_worst_windows_{MODEL_TAG}.csv"
RETENTION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_full_cycle_retention_{MODEL_TAG}.csv"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"
GOAL_CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_goal_chart_{MODEL_TAG}.png"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


def _to_bool(series: pd.Series) -> pd.Series:
    text = series.fillna(False).astype(str).str.lower()
    return text.isin({"1", "1.0", "true", "yes"})


def _quality_by_open_trade_rank19_entry_or_first() -> pd.DataFrame:
    quality = pd.read_csv(
        s020.QUALITY_FEATURES_PATH,
        encoding="utf-8-sig",
        usecols=[
            "requested_start_month",
            "open_trade_id",
            "tag_entry_or_first_aligned",
            "entry_first_bar_available",
            "entry_open_relation_bucket",
            "first_bar_relation_bucket",
            "ai_product_pool_rank",
        ],
    )
    quality["requested_start_month"] = quality["requested_start_month"].astype(str)
    quality["open_trade_id"] = quality["open_trade_id"].astype(str)
    quality["tag_entry_or_first_aligned"] = _to_bool(quality["tag_entry_or_first_aligned"]).astype("int64")
    quality["entry_first_bar_available"] = _to_bool(quality["entry_first_bar_available"]).astype("int64")
    quality["ai_product_pool_rank"] = pd.to_numeric(quality["ai_product_pool_rank"], errors="coerce")
    grouped = (
        quality.groupby(["requested_start_month", "open_trade_id"], dropna=False)
        .agg(
            tag_entry_or_first_aligned=("tag_entry_or_first_aligned", "max"),
            entry_first_bar_available=("entry_first_bar_available", "max"),
            ai_product_pool_rank_min=("ai_product_pool_rank", "min"),
            entry_open_relation_bucket=("entry_open_relation_bucket", "first"),
            first_bar_relation_bucket=("first_bar_relation_bucket", "first"),
        )
        .reset_index()
    )
    grouped[TAG_COLUMN] = (
        grouped["tag_entry_or_first_aligned"].eq(1)
        & grouped["ai_product_pool_rank_min"].ge(1)
        & grouped["ai_product_pool_rank_min"].le(9)
    ).astype("int64")
    return grouped


def _build_lot_deltas() -> tuple[pd.DataFrame, dict[str, Any]]:
    closed = pd.read_csv(
        s020.STAGE013_CLOSED_LOTS_PATH,
        encoding="utf-8-sig",
        parse_dates=["entry_date", "exit_date"],
    )
    quality = _quality_by_open_trade_rank19_entry_or_first()
    closed["requested_start_month"] = closed["requested_start_month"].astype(str)
    closed["open_trade_id"] = closed["open_trade_id"].astype(str)
    merged = closed.merge(quality, on=["requested_start_month", "open_trade_id"], how="left")
    merged["stage033_quality_tag_matched"] = merged[TAG_COLUMN].notna()
    for column in [
        "tag_entry_or_first_aligned",
        "entry_first_bar_available",
        TAG_COLUMN,
    ]:
        if column not in merged.columns:
            merged[column] = 0
        merged[column] = pd.to_numeric(merged[column], errors="coerce").fillna(0).astype("int64")
    merged["realized_pnl"] = pd.to_numeric(merged["realized_pnl"], errors="coerce").fillna(0.0)
    merged["exit_date"] = pd.to_datetime(merged["exit_date"], errors="coerce").dt.normalize()
    merged["selected_for_stage033"] = merged[TAG_COLUMN].eq(1)
    selected = merged[merged["selected_for_stage033"]].copy()
    selected["stage033_add_risk_fraction"] = ADD_RISK_FRACTION
    selected["stage020_proxy_delta_pnl"] = selected["realized_pnl"] * ADD_RISK_FRACTION
    keep = [
        "requested_start_month",
        "lot_id",
        "open_trade_id",
        "vt_symbol",
        "product",
        "direction",
        "entry_date",
        "exit_date",
        "volume",
        "realized_pnl",
        "r_multiple",
        "ai_product_pool_rank",
        "ai_product_pool_score",
        "ai_product_pool_rank_min",
        "entry_open_relation_bucket",
        "first_bar_relation_bucket",
        "tag_entry_or_first_aligned",
        "entry_first_bar_available",
        TAG_COLUMN,
        "stage033_quality_tag_matched",
        "stage033_add_risk_fraction",
        "stage020_proxy_delta_pnl",
    ]
    audit = {
        "stage013_closed_lot_count": int(len(closed)),
        "quality_key_count": int(len(quality)),
        "quality_tag_match_count": int(merged["stage033_quality_tag_matched"].sum()),
        "quality_tag_match_rate_pct": (
            float(merged["stage033_quality_tag_matched"].mean() * 100.0) if len(merged) else float("nan")
        ),
        "selected_lots": int(len(selected)),
        "selected_realized_pnl": float(selected["realized_pnl"].sum()) if len(selected) else 0.0,
        "total_proxy_delta_pnl": float(selected["stage020_proxy_delta_pnl"].sum()) if len(selected) else 0.0,
    }
    return selected[[column for column in keep if column in selected.columns]].reset_index(drop=True), audit


def _patch_stage020_globals() -> None:
    s020.STAGE = STAGE
    s020.MODEL_TAG = MODEL_TAG
    s020.OUTPUT_PREFIX = OUTPUT_PREFIX
    s020.TAG_COLUMN = TAG_COLUMN
    s020.ADD_RISK_FRACTION = ADD_RISK_FRACTION
    s020.OUTPUT_DIR = OUTPUT_DIR
    s020.STAGE_RECORD_DIR = STAGE_RECORD_DIR
    s020.LOT_DELTAS_PATH = LOT_DELTAS_PATH
    s020.CURVES_PATH = CURVES_PATH
    s020.SUMMARY_PATH = SUMMARY_PATH
    s020.ANNUAL_PATH = ANNUAL_PATH
    s020.GOAL_AGGREGATE_PATH = GOAL_AGGREGATE_PATH
    s020.GOAL_TO_FINAL_PATH = GOAL_TO_FINAL_PATH
    s020.GOAL_FIXED_HORIZON_PATH = GOAL_FIXED_HORIZON_PATH
    s020.GOAL_WORST_WINDOWS_PATH = GOAL_WORST_WINDOWS_PATH
    s020.RETENTION_PATH = RETENTION_PATH
    s020.CHART_PATH = CHART_PATH
    s020.GOAL_CHART_PATH = GOAL_CHART_PATH
    s020.DECISION_PATH = DECISION_PATH
    s020.REPORT_PATH = REPORT_PATH


def _stage033_decision(
    summary: pd.DataFrame,
    annual: pd.DataFrame,
    aggregate: pd.DataFrame,
    retention: pd.DataFrame,
    audit: dict[str, Any],
    unmatched_delta_dates: int,
) -> dict[str, Any]:
    decision = ORIGINAL_STAGE020_DECISION(summary, annual, aggregate, retention, audit, unmatched_delta_dates)
    decision.update(
        {
            "stage": STAGE,
            "model_tag": MODEL_TAG,
            "tag_column": TAG_COLUMN,
            "audit_type": "stage013_closed_lot_read_only_rank19_early_quality_add_risk_proxy",
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "decision": decision["decision"].replace("stage020", "stage033"),
            "external_research_judgment": (
                "Trend-following pyramiding references support adding risk only after a position proves direction, "
                "while prior Stage738/739 in this repo warns that true add layers can damage exits and compounding. "
                "Stage033 therefore stays a single frozen read-only upper-bound proxy: AI rank 1-9 plus entry/first-minute "
                "alignment, fixed 25% non-overwriting risk release, no product/date/direction rescue."
            ),
            "overfit_reflection_before": (
                "否。Stage033 只把 Stage032 已冻结的 rank 1-9 + entry_or_first_aligned 标签扩展到全体 Stage013 lot，"
                "固定 25% 代理，不扫阈值、倍率、品种、方向或年份。"
            ),
            "continue_value_before": (
                "有。Stage032 在恢复右尾集合上证明早段质量很强，但还不知道全体多起点目标是否改善；"
                "必须先做低自由度上界代理再考虑真实引擎。"
            ),
            "overfit_reflection_after": (
                "否。结果无论好坏都不调标签和比例；若下一步按负窗口倒推参数或复用小样本产品/日期豁免，会过拟合。"
            ),
            "continue_value_after": (
                "有，但不是进入真实加仓引擎。Stage033 提升收益和多数起点回撤，说明早段质量标签有信息量；"
                "但严格任意大于一年负窗口仍未清零，下一步应转向账户级 selector、可交易早段执行约束或外生信息源。"
            ),
        }
    )
    decision["outputs"] = {
        "lot_deltas": str(LOT_DELTAS_PATH),
        "curves": str(CURVES_PATH),
        "summary": str(SUMMARY_PATH),
        "annual_returns": str(ANNUAL_PATH),
        "goal_aggregate": str(GOAL_AGGREGATE_PATH),
        "goal_to_final": str(GOAL_TO_FINAL_PATH),
        "goal_fixed_horizon": str(GOAL_FIXED_HORIZON_PATH),
        "goal_worst_windows": str(GOAL_WORST_WINDOWS_PATH),
        "retention": str(RETENTION_PATH),
        "chart": str(CHART_PATH),
        "goal_chart": str(GOAL_CHART_PATH),
        "decision": str(DECISION_PATH),
        "report": str(REPORT_PATH),
    }
    return decision


def _write_stage_record(decision: dict[str, Any], summary: pd.DataFrame, retention: pd.DataFrame) -> Path:
    timestamp = datetime.now()
    path = STAGE_RECORD_DIR / f"{timestamp:%Y%m%d_%H%M}_stage033_rank19_early_quality_add_risk_proxy.md"
    lines = [
        "# Stage033 - rank1-9 开仓早段质量加风险只读代理",
        "",
        f"- 记录时间：`{timestamp.isoformat(timespec='minutes')}`",
        f"- line_id：`{LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        "- 是否重要突破版本：`否`",
        f"- 决策：`{decision['decision']}`",
        "",
        "## 本次版本变更",
        "",
        f"- 新增参数：`stage033_tag={TAG_COLUMN}`、`stage033_add_risk_fraction={ADD_RISK_FRACTION}`。",
        "- 修改参数：无，Stage013/官方 C9 配置未改。",
        "- 删除参数：无。",
        "- 本阶段只读代理，不新增真实交易规则、不接实盘。",
        "",
        "## 调研和判断结论",
        "",
        "- 趋势跟随/pyramiding 资料支持确认后加风险，但仓库旧 Stage738/739 已证明真实加仓会受到整数手、保证金、止损和复利路径反身影响。",
        "- 因此 Stage033 只做一个冻结上界代理：`AI rank 1-9 + entry_or_first_aligned + 25% 非挤占风险释放`，不扫标签组合、倍率、品种、方向或年份。",
        "",
        "## 代理结果",
        "",
        f"- 选中 lots：`{decision['selected_lots']}`。",
        f"- Stage013 realized PnL：`{decision['selected_realized_pnl']:,.2f}`。",
        f"- 代理增量 PnL：`{decision['total_proxy_delta_pnl']:,.2f}`。",
        f"- 严格任意结束日 `>1` 年负窗口：Stage013 `{decision['stage013_all_gt1y_negative_count']}` -> Stage033 `{decision['stage020_all_gt1y_negative_count']}`。",
        f"- Stage033 严格最差收益：`{decision['stage020_all_gt1y_min_return_pct']:.4f}%`。",
        f"- 到 `2026-06-30` 负窗口：`{decision['stage020_to_final_negative_count']}`，最差 `{decision['stage020_to_final_min_return_pct']:.4f}%`。",
        f"- 收益保留 vs Stage006：`{decision['retention_vs_base_stage006_pass_count']}/{decision['retention_rows']}`；vs Stage013：`{decision['retention_vs_stage013_pass_count']}/{decision['retention_rows']}`。",
        f"- 收益改善/不变/变差 vs Stage013：`{decision['return_improved_count_vs_stage013']}/{decision['return_unchanged_count_vs_stage013']}/{decision['return_worse_count_vs_stage013']}`。",
        f"- 回撤改善/不变/变差 vs Stage013：`{decision['maxdd_improved_count_vs_stage013']}/{decision['maxdd_unchanged_count_vs_stage013']}/{decision['maxdd_worse_count_vs_stage013']}`。",
        "",
        "## 多起点摘要",
        "",
        s020._md_table(
            summary[
                [
                    "requested_start_month",
                    "total_return_pct_stage013",
                    "total_return_pct_stage020",
                    "return_delta_pp_stage020_vs_stage013",
                    "max_dd_pct_stage013",
                    "max_dd_pct_stage020",
                    "max_dd_delta_pp_stage020_vs_stage013",
                ]
            ],
            max_rows=30,
        ),
        "",
        "## 收益保留摘要",
        "",
        s020._md_table(
            retention[
                [
                    "requested_start_month",
                    "stage020_vs_base_stage006_return_ratio",
                    "stage020_vs_stage013_return_ratio",
                    "passes_80pct_retention_vs_base_stage006",
                    "passes_80pct_retention_vs_stage013",
                ]
            ],
            max_rows=30,
        ),
        "",
        "## 文件",
        "",
    ]
    for key, output_path in decision["outputs"].items():
        lines.append(f"- {key}: `{output_path}`")
    lines.extend(
        [
            "",
            "## 后续规划和 TODO",
            "",
            "- 若严格负窗口仍未清零，不能通过加风险倍率救参；下一步转向账户级 selector、真实可交易早段引擎可行性，或外生信息源。",
            "- 若代理达标，也必须写真引擎验证成交、保证金、broker10、AI 月度审计和实盘执行可行性。",
            "",
            "## 反思",
            "",
            f"- 过拟合反思：{decision['overfit_reflection_after']}",
            f"- 继续价值反思：{decision['continue_value_after']}",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def main() -> None:
    _patch_stage020_globals()
    s020._build_lot_deltas = _build_lot_deltas
    s020._decision = _stage033_decision
    s020._write_stage_record = _write_stage_record
    s020.main()


if __name__ == "__main__":
    main()
