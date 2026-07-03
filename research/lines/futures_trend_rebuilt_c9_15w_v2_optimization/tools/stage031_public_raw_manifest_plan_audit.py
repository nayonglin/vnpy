from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[4]
LINE_ID = "futures_trend_rebuilt_c9_15w_v2_optimization"
UPSTREAM_LINE_ID = "futures_trend_c9_minrisk_highquality"
STAGE = "Stage031"
MODEL_TAG = "stage031_public_raw_manifest_plan_audit_v1"
OUTPUT_PREFIX = "rebuilt_c9_v2_stage031_public_raw_manifest_plan_audit"

LINE_DIR = PROJECT_DIR / "research" / "lines" / LINE_ID
UPSTREAM_LINE_DIR = PROJECT_DIR / "research" / "lines" / UPSTREAM_LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage031_public_raw_manifest_plan_audit"
STAGES_DIR = LINE_DIR / "stages"

UPSTREAM_STAGE090_DIR = UPSTREAM_LINE_DIR / "outputs" / "stage090_preentry_window_raw_manifest_design"
UPSTREAM_MANIFEST_PATH = (
    UPSTREAM_STAGE090_DIR
    / "qmt_roll_stage090_c9_minrisk_preentry_window_raw_manifest_design_planned_raw_manifest_stage090_preentry_window_raw_manifest_design_v1.csv"
)
UPSTREAM_SOURCE_SUMMARY_PATH = (
    UPSTREAM_STAGE090_DIR
    / "qmt_roll_stage090_c9_minrisk_preentry_window_raw_manifest_design_source_summary_stage090_preentry_window_raw_manifest_design_v1.csv"
)

BATCH_PLAN_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_batch_plan_{MODEL_TAG}.csv"
BATCH_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_batch_summary_{MODEL_TAG}.csv"
SOURCE_GATE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_source_gate_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (pd.Timestamp, datetime)):
        if pd.isna(value):
            return ""
        return value.isoformat()
    if isinstance(value, (np.integer, np.floating)):
        return value.item()
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return value


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or pd.isna(value):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_无记录_"
    data = frame.head(max_rows).copy() if max_rows else frame.copy()
    return data.to_markdown(index=False)


def _read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, dtype=str, encoding="utf-8-sig")


def build_batch_plan(manifest: pd.DataFrame, batch_size: int = 100) -> pd.DataFrame:
    if batch_size <= 0:
        raise ValueError("batch_size must be positive")
    if manifest.empty:
        return pd.DataFrame()

    required = {"source_id", "target_date"}
    missing = required - set(manifest.columns)
    if missing:
        raise ValueError(f"manifest missing columns: {sorted(missing)}")

    data = manifest.copy()
    data["source_id"] = data["source_id"].astype(str)
    data["target_date"] = data["target_date"].astype(str)
    data["source_date_key"] = data["source_id"] + ":" + data["target_date"]
    data = data.drop_duplicates("source_date_key").sort_values(["source_id", "target_date"]).reset_index(drop=True)
    data["batch_id"] = (data.index // batch_size + 1).astype(int)
    data["batch_size_limit"] = int(batch_size)
    data["strategy_rule_created"] = False
    data["true_engine_allowed"] = False
    data["signal_audit_allowed"] = False
    data["download_allowed_next_step"] = True
    data["required_before_signal_audit"] = "raw_download,raw_hash,parse_schema_hash,product_hit,right_tail_missing_safe"
    return data


def build_scope_gate(source_summary: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for source in source_summary.to_dict("records"):
        source_id = str(source.get("source_id", ""))
        planned_count = _as_int(source.get("planned_raw_date_count"), 0)
        probe_count = _as_int(source.get("probe_parsed_count"), 0)
        ready = bool(_as_int(source.get("preentry_manifest_ready"), 0))
        full_done = bool(_as_int(source.get("full_raw_download_done"), 0))

        reasons: list[str] = []
        if planned_count <= 0:
            reasons.append("no_planned_raw_dates")
        if probe_count <= 0:
            reasons.append("no_probe_parse_evidence")
        if not ready:
            reasons.append("preentry_manifest_not_ready")
        if not full_done:
            reasons.append("not_full_history")
            reasons.append("raw_download_not_done")

        if ready and planned_count > 0 and not full_done:
            status = "ready_for_batch_download_not_signal"
            batch_allowed = True
            signal_allowed = False
        elif ready and full_done:
            status = "needs_post_download_readiness_audit"
            batch_allowed = False
            signal_allowed = False
            reasons.append("post_download_audit_missing")
        else:
            status = "blocked_manifest_not_ready"
            batch_allowed = False
            signal_allowed = False

        rows.append(
            {
                "source_id": source_id,
                "planned_raw_date_count": planned_count,
                "probe_parsed_count": probe_count,
                "preentry_manifest_ready": ready,
                "full_raw_download_done": full_done,
                "route_status": status,
                "batch_download_plan_allowed": batch_allowed,
                "signal_audit_allowed": signal_allowed,
                "blocking_reasons": ",".join(list(dict.fromkeys(reasons))),
                "recommended_next_action": (
                    "execute_raw_download_batches_then_hash_parse_audit"
                    if batch_allowed
                    else "fix_manifest_or_run_post_download_readiness_audit"
                ),
            }
        )
    return pd.DataFrame(rows)


def build_batch_summary(batch_plan: pd.DataFrame) -> pd.DataFrame:
    if batch_plan.empty:
        return pd.DataFrame()
    data = batch_plan.copy()
    data["needed_product_count_num"] = pd.to_numeric(data.get("needed_product_count", 0), errors="coerce").fillna(0)
    summary = (
        data.groupby("batch_id", as_index=False)
        .agg(
            source_count=("source_id", "nunique"),
            raw_request_count=("source_date_key", "nunique"),
            first_target_date=("target_date", "min"),
            last_target_date=("target_date", "max"),
            max_needed_product_count=("needed_product_count_num", "max"),
        )
        .sort_values("batch_id")
    )
    summary["strategy_rule_created"] = False
    summary["true_engine_allowed"] = False
    return summary


def make_manifest_plan_decision(batch_plan: pd.DataFrame, source_gate: pd.DataFrame) -> dict[str, Any]:
    batch_count = int(batch_plan["batch_id"].nunique()) if not batch_plan.empty else 0
    signal_allowed = int(source_gate["signal_audit_allowed"].astype(bool).sum()) if not source_gate.empty else 0
    batch_allowed = int(source_gate["batch_download_plan_allowed"].astype(bool).sum()) if not source_gate.empty else 0

    if batch_count > 0 and signal_allowed == 0:
        decision = "stage031_public_raw_manifest_batch_plan_ready_no_strategy_candidate"
        best_next_direction = "execute_public_raw_download_batches_then_hash_parse_readiness_audit"
    elif signal_allowed > 0:
        decision = "stage031_post_download_readiness_needed_before_signal_audit"
        best_next_direction = "post_download_readiness_audit"
    else:
        decision = "stage031_public_raw_manifest_plan_blocked"
        best_next_direction = "fix_manifest_inputs"

    return {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().replace(microsecond=0).isoformat(),
        "decision": decision,
        "best_next_direction": best_next_direction,
        "planned_raw_request_count": int(len(batch_plan)),
        "batch_count": batch_count,
        "source_count": int(batch_plan["source_id"].nunique()) if not batch_plan.empty else 0,
        "batch_allowed_source_count": batch_allowed,
        "immediate_strategy_candidate_count": signal_allowed,
        "strategy_changed": False,
        "official_live_strategy_changed": False,
        "true_engine": False,
        "order_api_called": False,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "ctp_connected": False,
        "external_research_judgment": (
            "Public exchange warehouse/member-rank pages and AKShare wrappers can support raw source collection for "
            "some CZCE/GFEX sources, but this is still data engineering. Authorized orderflow/depth and full option "
            "chains remain separate higher-priority data needs."
        ),
        "overfit_reflection_before": (
            "否。Stage031 只把已探针通过的公开 raw source 转成下载批次计划，不新增收益阈值或交易规则。"
        ),
        "overfit_reflection_after": (
            "否。输出仍是数据交付清单；禁止把 source/date ready、缺失、产品命中或单一 raw source 写成交易条件。"
        ),
        "continue_value_before": (
            "有。Stage030 已确认数据先行，本阶段把 CZCE/GFEX 公开 raw 路线从描述推进到可执行批次。"
        ),
        "continue_value_after": (
            "有，但下一步必须下载、hash、解析并做 post-download readiness；在此之前仍无策略候选。"
        ),
    }


def _write_report(decision: dict[str, Any], gate: pd.DataFrame, batch_summary: pd.DataFrame) -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Stage031 公开 raw manifest 批次计划审计",
        "",
        "## 结论",
        "",
        f"- 决策：`{decision['decision']}`",
        f"- 计划 raw 请求：`{decision['planned_raw_request_count']}`",
        f"- 批次数：`{decision['batch_count']}`",
        f"- 直接策略候选：`{decision['immediate_strategy_candidate_count']}`",
        "- 本阶段不下载全量、不回测、不写真引擎、不触发订单 API。",
        "",
        "## 外部调研与判断",
        "",
        "- 公开交易所仓单/会员排名页面和 AKShare 可以作为 raw manifest 工程参考，但不等价于授权 orderflow/depth 或期权链历史。",
        "- SHFE/DCE/CZCE/GFEX 公开统计源的价值在于供需/会员结构 raw 归档；要交易化仍需发布时间戳、raw hash、schema hash、产品映射和右尾缺失安全审计。",
        "",
        "## Source Gate",
        "",
        _md_table(gate),
        "",
        "## Batch Summary",
        "",
        _md_table(batch_summary, max_rows=20),
        "",
        "## 过拟合反思",
        "",
        f"- 运行前：{decision['overfit_reflection_before']}",
        f"- 运行后：{decision['overfit_reflection_after']}",
        "",
        "## 继续价值反思",
        "",
        f"- 运行前：{decision['continue_value_before']}",
        f"- 运行后：{decision['continue_value_after']}",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_stage_record(decision: dict[str, Any]) -> Path:
    STAGES_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    path = STAGES_DIR / f"{timestamp}_stage031_public_raw_manifest_plan_audit.md"
    lines = [
        "# Stage031 公开 raw manifest 批次计划审计",
        "",
        f"- line_id：`{LINE_ID}`",
        "- 当前模式：day",
        f"- 记录时间：{decision['generated_at']}",
        "- 阶段性质：只读数据工程计划；不下载全量、不回测、不改策略、不连接 CTP、不调用下单",
        "- 是否重要突破：否",
        "- 是否触发A/B：否",
        "",
        "## 外部调研与判断",
        "",
        "- 参考交易所公开仓单/排名页面、AKShare 期货数据文档，以及旧线 Stage088-090 的 raw smoke/manifest 探针。",
        "- 我的判断：CZCE 会员/仓单和 GFEX 仓单可以先推进 raw 归档工程，但这只是数据地基；不能替代 orderflow/depth、生产执行回放或期权链历史。",
        "",
        "## 本次变更",
        "",
        f"- 新增脚本：`{Path(__file__).relative_to(PROJECT_DIR)}`",
        "- 新增测试：`tests/test_rebuilt_c9_v2_stage031_public_raw_manifest_plan.py`",
        "- 新增参数：`batch_size=100`，只用于下载计划分批；无交易参数。",
        "- 修改参数：无",
        "- 删除参数：无",
        "",
        "## 结果",
        "",
        f"- planned_raw_request_count：`{decision['planned_raw_request_count']}`",
        f"- batch_count：`{decision['batch_count']}`",
        f"- source_count：`{decision['source_count']}`",
        f"- immediate_strategy_candidate_count：`{decision['immediate_strategy_candidate_count']}`",
        f"- 决策：`{decision['decision']}`",
        f"- 下一方向：`{decision['best_next_direction']}`",
        "",
        "## 输出文件",
        "",
        f"- batch_plan：`{BATCH_PLAN_PATH}`",
        f"- batch_summary：`{BATCH_SUMMARY_PATH}`",
        f"- source_gate：`{SOURCE_GATE_PATH}`",
        f"- decision：`{DECISION_PATH}`",
        f"- report：`{REPORT_PATH}`",
        "",
        "## 过拟合反思",
        "",
        f"- 运行前判断：{decision['overfit_reflection_before']}",
        f"- 运行后判断：{decision['overfit_reflection_after']}",
        "",
        "## 继续价值反思",
        "",
        f"- 运行前判断：{decision['continue_value_before']}",
        f"- 运行后判断：{decision['continue_value_after']}",
        "",
        "## 合入建议",
        "",
        "- 更新本线 `LINE.md`：是。",
        "- 更新 `research/registry.md`：是。",
        "- 追加根目录 `memory.md/back_log.md`：否，本阶段不是策略候选或重要突破。",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest = _read_csv(UPSTREAM_MANIFEST_PATH)
    source_summary = _read_csv(UPSTREAM_SOURCE_SUMMARY_PATH)

    batch_plan = build_batch_plan(manifest, batch_size=100)
    source_gate = build_scope_gate(source_summary)
    batch_summary = build_batch_summary(batch_plan)
    decision = make_manifest_plan_decision(batch_plan, source_gate)

    batch_plan.to_csv(BATCH_PLAN_PATH, index=False)
    batch_summary.to_csv(BATCH_SUMMARY_PATH, index=False)
    source_gate.to_csv(SOURCE_GATE_PATH, index=False)
    _write_report(decision, source_gate, batch_summary)
    stage_record = _write_stage_record(decision)

    decision["outputs"] = {
        "batch_plan": BATCH_PLAN_PATH,
        "batch_summary": BATCH_SUMMARY_PATH,
        "source_gate": SOURCE_GATE_PATH,
        "decision": DECISION_PATH,
        "report": REPORT_PATH,
        "stage_record": stage_record,
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
