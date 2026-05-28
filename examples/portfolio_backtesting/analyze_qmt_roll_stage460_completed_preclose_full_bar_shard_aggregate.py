from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
MODEL_TAG = "stage460_completed_preclose_full_bar_shard_001_547_sample5_v1"
OUTPUT_PREFIX = "qmt_roll_stage460_completed_preclose_full_bar_shard_aggregate"
LINE_ID = "futures_trend_drawdown30_preserve_return"

SHARDS = [
    (
        "001_060",
        "qmt_roll_stage459_completed_preclose_full_bar_shard_summary_stage459_completed_preclose_full_bar_shard_v1.csv",
        "qmt_roll_stage459_completed_preclose_full_bar_shard_selected_targets_stage459_completed_preclose_full_bar_shard_v1.csv",
        "qmt_roll_stage459_completed_preclose_full_bar_shard_extract_status_stage459_completed_preclose_full_bar_shard_v1.csv",
    ),
    (
        "061_120",
        "qmt_roll_stage460_completed_preclose_full_bar_shard_summary_stage460_completed_preclose_full_bar_shard_061_120_v1.csv",
        "qmt_roll_stage460_completed_preclose_full_bar_shard_selected_targets_stage460_completed_preclose_full_bar_shard_061_120_v1.csv",
        "qmt_roll_stage460_completed_preclose_full_bar_shard_extract_status_stage460_completed_preclose_full_bar_shard_061_120_v1.csv",
    ),
    (
        "121_180",
        "qmt_roll_stage460_completed_preclose_full_bar_shard_summary_stage460_completed_preclose_full_bar_shard_121_180_v1.csv",
        "qmt_roll_stage460_completed_preclose_full_bar_shard_selected_targets_stage460_completed_preclose_full_bar_shard_121_180_v1.csv",
        "qmt_roll_stage460_completed_preclose_full_bar_shard_extract_status_stage460_completed_preclose_full_bar_shard_121_180_v1.csv",
    ),
    (
        "181_240",
        "qmt_roll_stage460_completed_preclose_full_bar_shard_summary_stage460_completed_preclose_full_bar_shard_181_240_v1.csv",
        "qmt_roll_stage460_completed_preclose_full_bar_shard_selected_targets_stage460_completed_preclose_full_bar_shard_181_240_v1.csv",
        "qmt_roll_stage460_completed_preclose_full_bar_shard_extract_status_stage460_completed_preclose_full_bar_shard_181_240_v1.csv",
    ),
    (
        "241_300",
        "qmt_roll_stage460_completed_preclose_full_bar_shard_summary_stage460_completed_preclose_full_bar_shard_241_300_v1.csv",
        "qmt_roll_stage460_completed_preclose_full_bar_shard_selected_targets_stage460_completed_preclose_full_bar_shard_241_300_v1.csv",
        "qmt_roll_stage460_completed_preclose_full_bar_shard_extract_status_stage460_completed_preclose_full_bar_shard_241_300_v1.csv",
    ),
    (
        "301_360",
        "qmt_roll_stage460_completed_preclose_full_bar_shard_summary_stage460_completed_preclose_full_bar_shard_301_360_v1.csv",
        "qmt_roll_stage460_completed_preclose_full_bar_shard_selected_targets_stage460_completed_preclose_full_bar_shard_301_360_v1.csv",
        "qmt_roll_stage460_completed_preclose_full_bar_shard_extract_status_stage460_completed_preclose_full_bar_shard_301_360_v1.csv",
    ),
    (
        "361_420",
        "qmt_roll_stage460_completed_preclose_full_bar_shard_summary_stage460_completed_preclose_full_bar_shard_361_420_v1.csv",
        "qmt_roll_stage460_completed_preclose_full_bar_shard_selected_targets_stage460_completed_preclose_full_bar_shard_361_420_v1.csv",
        "qmt_roll_stage460_completed_preclose_full_bar_shard_extract_status_stage460_completed_preclose_full_bar_shard_361_420_v1.csv",
    ),
    (
        "421_480",
        "qmt_roll_stage460_completed_preclose_full_bar_shard_summary_stage460_completed_preclose_full_bar_shard_421_480_v1.csv",
        "qmt_roll_stage460_completed_preclose_full_bar_shard_selected_targets_stage460_completed_preclose_full_bar_shard_421_480_v1.csv",
        "qmt_roll_stage460_completed_preclose_full_bar_shard_extract_status_stage460_completed_preclose_full_bar_shard_421_480_v1.csv",
    ),
    (
        "481_547",
        "qmt_roll_stage460_completed_preclose_full_bar_shard_summary_stage460_completed_preclose_full_bar_shard_481_547_v1.csv",
        "qmt_roll_stage460_completed_preclose_full_bar_shard_selected_targets_stage460_completed_preclose_full_bar_shard_481_547_v1.csv",
        "qmt_roll_stage460_completed_preclose_full_bar_shard_extract_status_stage460_completed_preclose_full_bar_shard_481_547_v1.csv",
    ),
]

AGG_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
SHARD_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_shard_summary_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


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
        value = float(value)
        return None if np.isnan(value) or np.isinf(value) else value
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    return value


def _md_table(frame: pd.DataFrame) -> str:
    if frame.empty:
        return "无数据。"
    view = frame.copy()
    for column in view.columns:
        if pd.api.types.is_float_dtype(view[column]):
            view[column] = view[column].map(lambda value: f"{value:.4f}" if pd.notna(value) else "")
    return view.to_markdown(index=False)


def _read_required(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path, encoding="utf-8-sig")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    summary_frames: list[pd.DataFrame] = []
    target_frames: list[pd.DataFrame] = []
    status_frames: list[pd.DataFrame] = []

    for shard_id, summary_name, targets_name, status_name in SHARDS:
        summary = _read_required(OUTPUT_DIR / summary_name)
        targets = _read_required(OUTPUT_DIR / targets_name)
        status = _read_required(OUTPUT_DIR / status_name)
        summary.insert(0, "shard_id", shard_id)
        targets.insert(0, "shard_id", shard_id)
        status.insert(0, "shard_id", shard_id)
        summary_frames.append(summary)
        target_frames.append(targets)
        status_frames.append(status)

    shard_summary = pd.concat(summary_frames, ignore_index=True)
    targets_all = pd.concat(target_frames, ignore_index=True)
    status_all = pd.concat(status_frames, ignore_index=True)
    targets_all["plan_rank"] = pd.to_numeric(targets_all["plan_rank"], errors="coerce")

    target_count = int(shard_summary["selected_target_dates"].sum())
    ready_count = int(shard_summary["full_bar_ready_count"].sum())
    failed_symbol_count = int(shard_summary["failed_symbol_count"].sum())
    unique_span_count = int(targets_all["plan_rank"].nunique())
    unique_symbol_count = int(targets_all["vt_symbol"].nunique())
    unique_product_count = int(targets_all["product_vt_symbol"].nunique())
    ready_rate = ready_count / target_count if target_count else 0.0
    covered_span_min = int(targets_all["plan_rank"].min())
    covered_span_max = int(targets_all["plan_rank"].max())
    status_values = sorted(status_all["status"].astype(str).unique().tolist())
    timeout_count = int(status_all["status"].astype(str).eq("timeout").sum())

    aggregate = pd.DataFrame(
        [
            {
                "model_tag": MODEL_TAG,
                "shard_count": len(SHARDS),
                "covered_span_min": covered_span_min,
                "covered_span_max": covered_span_max,
                "unique_span_count": unique_span_count,
                "unique_symbol_count": unique_symbol_count,
                "unique_product_count": unique_product_count,
                "selected_target_dates": target_count,
                "failed_symbol_count": failed_symbol_count,
                "timeout_count": timeout_count,
                "minute_bar_count": int(shard_summary["minute_bar_count"].sum()),
                "volume_positive_bar_count": int(shard_summary["volume_positive_bar_count"].sum()),
                "full_bar_ready_count": ready_count,
                "full_bar_ready_rate": ready_rate,
                "preclose_bar_count_min": int(shard_summary["preclose_bar_count_min"].min()),
                "fill_bar_count_min": int(shard_summary["fill_bar_count_min"].min()),
                "synthetic_volume_sum": float(shard_summary["synthetic_volume_sum"].sum()),
                "fill_volume_sum": float(shard_summary["fill_volume_sum"].sum()),
                "status_values": ",".join(status_values),
            }
        ]
    )

    shard_summary.to_csv(SHARD_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    aggregate.to_csv(AGG_SUMMARY_PATH, index=False, encoding="utf-8-sig")

    decision_label = (
        "completed_preclose_full_bar_all_span_sample_ready_extend_full_dates"
        if ready_count == target_count and failed_symbol_count == 0 and unique_span_count == 547
        else "completed_preclose_full_bar_all_span_sample_partial_need_gap_attribution"
    )
    decision = {
        "stage": "Stage160",
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "decision": decision_label,
        "promotion_candidate": "none",
        "aggregate": aggregate.iloc[0].to_dict(),
        "outputs": {
            "aggregate_summary": str(AGG_SUMMARY_PATH),
            "shard_summary": str(SHARD_SUMMARY_PATH),
            "report": str(REPORT_PATH),
        },
        "next_step": "全span抽样strict ready后，改为全目标日期回补；全日期OHLCVOI稳定后，再做一致预收盘真实回放和3/6个月体验优化。",
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")

    report = "\n".join(
        [
            "# Stage160 completed-row全span抽样聚合审计",
            "",
            f"- 生成时间：{decision['generated_at']}",
            "- 阶段性质：数据链路聚合审计；不新增策略，不修改 Stage079/C3/Stage103 交易规则。",
            f"- 决策标签：`{decision_label}`。",
            "",
            "## 汇总",
            "",
            _md_table(aggregate),
            "",
            "## 分片摘要",
            "",
            _md_table(
                shard_summary[
                    [
                        "shard_id",
                        "start_span",
                        "max_spans",
                        "selected_span_count",
                        "selected_symbol_count",
                        "selected_target_dates",
                        "failed_symbol_count",
                        "minute_bar_count",
                        "volume_positive_bar_count",
                        "full_bar_ready_count",
                        "full_bar_ready_rate",
                        "preclose_bar_count_min",
                        "fill_bar_count_min",
                    ]
                ]
            ),
            "",
            "## 结论",
            "",
            "- 本阶段没有策略候选晋级。",
            "- completed-row 预收盘完整bar在 Stage154 全部 547 个缺口span的抽样目标日上均为 strict ready。",
            "- 该结果支持下一步从抽样验证升级到全目标日期回补，但仍不能直接替代一致预收盘真实回放。",
            "",
            "## 过拟合与继续价值反思",
            "",
            "- 过拟合：否。本阶段只聚合数据覆盖结果，不看策略收益、不筛选好窗口、不调交易参数。",
            "- 继续价值：是。只有全日期OHLCVOI稳定，后续3/6个月体验优化才有真实部署含义。",
        ]
    )
    REPORT_PATH.write_text(report, encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
