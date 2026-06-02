from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
LINE_ID = "futures_trend_drawdown30_preserve_return"
STAGE = "Stage189"
MODEL_TAG = "stage489_completed_preclose_full_dates_001_547_v1"
OUTPUT_PREFIX = "qmt_roll_stage489_completed_preclose_full_dates_aggregate"

REQUIRED_KEYS_PATH = (
    OUTPUT_DIR
    / "qmt_roll_stage454_preclose_signal_bar_data_readiness_required_keys_stage454_preclose_signal_bar_data_readiness_v1.csv"
)

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
SHARD_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_shard_summary_{MODEL_TAG}.csv"
SPAN_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_span_summary_{MODEL_TAG}.csv"
STATUS_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_status_summary_{MODEL_TAG}.csv"
TARGET_GAP_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_target_gap_{MODEL_TAG}.csv"
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


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path, encoding="utf-8-sig")


def _discover_summary_files() -> list[Path]:
    files = []
    for path in OUTPUT_DIR.glob("*completed_preclose_full_dates*_summary_stage*completed_preclose_full_dates*.csv"):
        name = path.name
        if "_span_summary_" in name or "_product_summary_" in name:
            continue
        if name.startswith(OUTPUT_PREFIX):
            continue
        files.append(path)
    if not files:
        raise FileNotFoundError("No completed_preclose_full_dates shard summary files found")

    def start_span(path: Path) -> int:
        frame = _read_csv(path)
        return int(frame["start_span"].iloc[0])

    return sorted(files, key=start_span)


def _related_file(summary_path: Path, relation: str) -> Path:
    prefix, tag_with_ext = summary_path.name.split("_summary_", 1)
    return OUTPUT_DIR / f"{prefix}_{relation}_{tag_with_ext}"


def _normalize_key_frame(frame: pd.DataFrame) -> pd.DataFrame:
    key = frame[["date", "product_vt_symbol", "vt_symbol"]].copy()
    key["date"] = pd.to_datetime(key["date"]).dt.strftime("%Y-%m-%d")
    key["product_vt_symbol"] = key["product_vt_symbol"].astype(str)
    key["vt_symbol"] = key["vt_symbol"].astype(str)
    return key


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    summary_files = _discover_summary_files()

    summary_frames: list[pd.DataFrame] = []
    target_frames: list[pd.DataFrame] = []
    span_frames: list[pd.DataFrame] = []
    status_frames: list[pd.DataFrame] = []
    synthetic_frames: list[pd.DataFrame] = []

    for summary_path in summary_files:
        summary = _read_csv(summary_path)
        shard_id = f"{int(summary['start_span'].iloc[0]):03d}_{int(summary['start_span'].iloc[0]) + int(summary['max_spans'].iloc[0]) - 1:03d}"
        if int(summary["start_span"].iloc[0]) == 541:
            shard_id = "541_547"
        summary.insert(0, "shard_id", shard_id)
        summary.insert(1, "summary_file", summary_path.name)
        summary_frames.append(summary)

        for relation, frames in [
            ("selected_targets", target_frames),
            ("span_summary", span_frames),
            ("extract_status", status_frames),
            ("synthetic_preclose_bars", synthetic_frames),
        ]:
            related = _related_file(summary_path, relation)
            frame = _read_csv(related)
            frame.insert(0, "shard_id", shard_id)
            frames.append(frame)

    shard_summary = pd.concat(summary_frames, ignore_index=True)
    targets_all = pd.concat(target_frames, ignore_index=True)
    spans_all = pd.concat(span_frames, ignore_index=True)
    status_all = pd.concat(status_frames, ignore_index=True)
    synthetic_all = pd.concat(synthetic_frames, ignore_index=True)

    targets_all["plan_rank"] = pd.to_numeric(targets_all["plan_rank"], errors="coerce")
    spans_all["plan_rank"] = pd.to_numeric(spans_all["plan_rank"], errors="coerce")
    synthetic_all["plan_rank"] = pd.to_numeric(synthetic_all["plan_rank"], errors="coerce")

    required = _read_csv(REQUIRED_KEYS_PATH)
    required_missing = required[pd.to_numeric(required["has_preclose_1455_1500"], errors="coerce").fillna(0).eq(0)].copy()

    target_keys = _normalize_key_frame(targets_all)
    required_keys = _normalize_key_frame(required_missing)
    target_key_set = set(map(tuple, target_keys.to_numpy()))
    required_key_set = set(map(tuple, required_keys.to_numpy()))

    missing_from_targets = required_key_set - target_key_set
    extra_targets = target_key_set - required_key_set
    duplicate_target_count = int(target_keys.duplicated().sum())
    duplicate_synthetic_count = int(_normalize_key_frame(synthetic_all).duplicated().sum())

    gap_rows = []
    for source, items in [("missing_from_targets", missing_from_targets), ("extra_targets", extra_targets)]:
        for date, product_vt_symbol, vt_symbol in sorted(items):
            gap_rows.append(
                {
                    "gap_type": source,
                    "date": date,
                    "product_vt_symbol": product_vt_symbol,
                    "vt_symbol": vt_symbol,
                }
            )
    target_gap = pd.DataFrame(gap_rows)

    expected_spans = set(range(1, 548))
    actual_spans = {int(value) for value in targets_all["plan_rank"].dropna().unique()}
    missing_spans = sorted(expected_spans - actual_spans)
    extra_spans = sorted(actual_spans - expected_spans)

    strict_fields = ["valid_ohlc", "volume_ok", "open_interest_ok", "fill_ok", "full_bar_ready"]
    strict_counts = {
        field: int(pd.to_numeric(synthetic_all[field], errors="coerce").fillna(0).sum())
        for field in strict_fields
        if field in synthetic_all.columns
    }

    target_count = int(shard_summary["selected_target_dates"].sum())
    ready_count = int(shard_summary["full_bar_ready_count"].sum())
    failed_symbol_count = int(shard_summary["failed_symbol_count"].sum())
    status_summary = (
        status_all["status"].astype(str).value_counts().rename_axis("status").reset_index(name="count")
    )
    timeout_count = int(status_all["status"].astype(str).eq("timeout").sum())

    aggregate = pd.DataFrame(
        [
            {
                "stage": STAGE,
                "model_tag": MODEL_TAG,
                "shard_count": len(summary_files),
                "covered_span_min": int(targets_all["plan_rank"].min()),
                "covered_span_max": int(targets_all["plan_rank"].max()),
                "unique_span_count": int(targets_all["plan_rank"].nunique()),
                "missing_span_count": len(missing_spans),
                "extra_span_count": len(extra_spans),
                "required_missing_keys": int(len(required_missing)),
                "selected_target_dates": target_count,
                "full_bar_ready_count": ready_count,
                "full_bar_ready_rate": ready_count / target_count if target_count else 0.0,
                "required_missing_not_selected": len(missing_from_targets),
                "selected_not_required_missing": len(extra_targets),
                "duplicate_target_count": duplicate_target_count,
                "duplicate_synthetic_count": duplicate_synthetic_count,
                "failed_symbol_count": failed_symbol_count,
                "timeout_count": timeout_count,
                "unique_symbol_count": int(targets_all["vt_symbol"].nunique()),
                "unique_product_count": int(targets_all["product_vt_symbol"].nunique()),
                "status_values": ",".join(sorted(status_all["status"].astype(str).unique())),
                "minute_bar_count": int(shard_summary["minute_bar_count"].sum()),
                "volume_positive_bar_count": int(shard_summary["volume_positive_bar_count"].sum()),
                "preclose_bar_count_min": int(shard_summary["preclose_bar_count_min"].min()),
                "fill_bar_count_min": int(shard_summary["fill_bar_count_min"].min()),
                "synthetic_volume_sum": float(shard_summary["synthetic_volume_sum"].sum()),
                "fill_volume_sum": float(shard_summary["fill_volume_sum"].sum()),
                **{f"{field}_count": strict_counts.get(field, 0) for field in strict_fields},
            }
        ]
    )

    all_ready = (
        target_count == int(len(required_missing))
        and ready_count == target_count
        and len(missing_spans) == 0
        and len(extra_spans) == 0
        and len(missing_from_targets) == 0
        and len(extra_targets) == 0
        and duplicate_target_count == 0
        and duplicate_synthetic_count == 0
        and failed_symbol_count == 0
        and timeout_count == 0
        and all(count == target_count for count in strict_counts.values())
    )
    decision_label = (
        "completed_preclose_full_dates_all_required_keys_ready_proceed_to_consistent_preclose_replay"
        if all_ready
        else "completed_preclose_full_dates_aggregate_gap_detected_need_attribution"
    )

    shard_summary.to_csv(SHARD_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    spans_all.to_csv(SPAN_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    status_summary.to_csv(STATUS_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    target_gap.to_csv(TARGET_GAP_PATH, index=False, encoding="utf-8-sig")
    aggregate.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")

    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    decision = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at": generated_at,
        "decision": decision_label,
        "promotion_candidate": "none",
        "aggregate": aggregate.iloc[0].to_dict(),
        "missing_spans": missing_spans,
        "extra_spans": extra_spans,
        "outputs": {
            "summary": str(SUMMARY_PATH),
            "shard_summary": str(SHARD_SUMMARY_PATH),
            "span_summary": str(SPAN_SUMMARY_PATH),
            "status_summary": str(STATUS_SUMMARY_PATH),
            "target_gap": str(TARGET_GAP_PATH),
            "report": str(REPORT_PATH),
        },
        "next_step": "进入一致预收盘真实回放；若真实回放仍满足硬约束，再恢复 Stage079 3个月/6个月体验优化。",
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")

    report = "\n".join(
        [
            "# Stage189 completed-row全日期聚合审计",
            "",
            f"- 生成时间：{generated_at}",
            "- 阶段性质：数据链路全量聚合审计；不新增策略，不修改 Stage079/C3 交易规则。",
            f"- 决策标签：`{decision_label}`。",
            "",
            "## 汇总",
            "",
            _md_table(aggregate),
            "",
            "## 状态分布",
            "",
            _md_table(status_summary),
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
                        "full_bar_ready_count",
                        "full_bar_ready_rate",
                        "preclose_bar_count_min",
                        "fill_bar_count_min",
                    ]
                ]
            ),
            "",
            "## 目标键差异",
            "",
            _md_table(target_gap.head(50)),
            "",
            "## 结论",
            "",
            "- 本阶段不晋级策略候选。",
            "- 若决策标签为 ready，则 completed-row 预收盘完整bar数据链路已覆盖 Stage154 全部缺口目标键。",
            "- 下一步应做一致预收盘真实回放，再讨论 Stage079 的3个月/6个月体验优化。",
            "",
            "## 过拟合与继续价值反思",
            "",
            "- 过拟合：否。聚合审计只验证固定缺口计划和字段完整性，没有看收益或调参。",
            "- 继续价值：是。通过后可结束数据可得性前置，进入真实可执行口径回放。",
        ]
    )
    REPORT_PATH.write_text(report, encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
