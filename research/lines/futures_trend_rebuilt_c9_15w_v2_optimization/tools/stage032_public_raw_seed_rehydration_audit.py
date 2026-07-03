from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[4]
LINE_ID = "futures_trend_rebuilt_c9_15w_v2_optimization"
UPSTREAM_LINE_ID = "futures_trend_c9_minrisk_highquality"
STAGE = "Stage032"
MODEL_TAG = "stage032_public_raw_seed_rehydration_audit_v1"
OUTPUT_PREFIX = "rebuilt_c9_v2_stage032_public_raw_seed_rehydration_audit"

LINE_DIR = PROJECT_DIR / "research" / "lines" / LINE_ID
UPSTREAM_LINE_DIR = PROJECT_DIR / "research" / "lines" / UPSTREAM_LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage032_public_raw_seed_rehydration_audit"
STAGES_DIR = LINE_DIR / "stages"

STAGE031_DIR = LINE_DIR / "outputs" / "stage031_public_raw_manifest_plan_audit"
BATCH_PLAN_IN = (
    STAGE031_DIR
    / "rebuilt_c9_v2_stage031_public_raw_manifest_plan_audit_batch_plan_"
    "stage031_public_raw_manifest_plan_audit_v1.csv"
)
UPSTREAM_STAGE091_DIR = UPSTREAM_LINE_DIR / "outputs" / "stage091_preentry_window_raw_full_backfill"
UPSTREAM_RESULTS_IN = (
    UPSTREAM_STAGE091_DIR
    / "qmt_roll_stage091_c9_minrisk_preentry_window_raw_full_backfill_backfill_results_"
    "stage091_preentry_window_raw_full_backfill_v1.csv"
)

SEED_INDEX_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_seed_index_{MODEL_TAG}.csv"
SOURCE_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_source_summary_{MODEL_TAG}.csv"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, Path):
        return str(value)
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
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return value


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise RuntimeError(f"missing required input: {path}")
    return pd.read_csv(path, dtype=str, encoding="utf-8-sig")


def _target_date(value: Any) -> str:
    text = str(value).strip()
    if text.endswith(".0"):
        text = text[:-2]
    return text.zfill(8)


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    return text in {"1", "1.0", "true", "yes", "y"}


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or pd.isna(value):
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _file_digest(path: Path) -> tuple[bool, str, int]:
    if not path.exists() or not path.is_file():
        return False, "", 0
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            size += len(chunk)
            digest.update(chunk)
    return True, digest.hexdigest(), size


def build_seed_index(batch_plan: pd.DataFrame, upstream_results: pd.DataFrame, repo_dir: Path = PROJECT_DIR) -> pd.DataFrame:
    required_plan = {"source_id", "target_date"}
    required_upstream = {"source_id", "target_date", "sha256", "raw_file", "status", "parse_ready", "hash_ready"}
    missing_plan = required_plan - set(batch_plan.columns)
    missing_upstream = required_upstream - set(upstream_results.columns)
    if missing_plan:
        raise ValueError(f"batch_plan missing columns: {sorted(missing_plan)}")
    if missing_upstream:
        raise ValueError(f"upstream_results missing columns: {sorted(missing_upstream)}")

    plan = batch_plan.copy()
    upstream = upstream_results.copy()
    for frame in [plan, upstream]:
        frame["source_id"] = frame["source_id"].astype(str)
        frame["target_date"] = frame["target_date"].map(_target_date)
        frame["_key"] = frame["source_id"] + ":" + frame["target_date"]

    upstream = upstream.sort_values(["source_id", "target_date"]).drop_duplicates("_key")
    merged = plan.merge(
        upstream.add_prefix("upstream_"),
        left_on="_key",
        right_on="upstream__key",
        how="left",
    )

    rows: list[dict[str, Any]] = []
    for row in merged.to_dict("records"):
        raw_file = str(row.get("upstream_raw_file") or "")
        raw_path = repo_dir / raw_file if raw_file else repo_dir / "__missing_raw_file__"
        exists, observed_sha, observed_bytes = _file_digest(raw_path)
        expected_sha = str(row.get("upstream_sha256") or "")
        parse_ready = _as_bool(row.get("upstream_parse_ready"))
        hash_ready = _as_bool(row.get("upstream_hash_ready"))
        status = str(row.get("upstream_status") or "")
        upstream_found = bool(raw_file and str(row.get("upstream_source_id") or "nan") != "nan")
        sha_match = bool(exists and expected_sha and observed_sha == expected_sha)

        reasons: list[str] = []
        if not upstream_found:
            reasons.append("upstream_result_missing")
        if upstream_found and not raw_file:
            reasons.append("upstream_raw_file_empty")
        if raw_file and not exists:
            reasons.append("raw_file_missing")
        if exists and expected_sha and not sha_match:
            reasons.append("sha256_mismatch")
        if exists and not expected_sha:
            reasons.append("upstream_sha256_missing")
        if not hash_ready:
            reasons.append("upstream_hash_not_ready")
        if not parse_ready:
            reasons.append("upstream_parse_not_ready")
        if status != "parsed_ok":
            reasons.append("upstream_status_not_parsed_ok")

        ready = bool(upstream_found and exists and sha_match and hash_ready and parse_ready and status == "parsed_ok")
        rows.append(
            {
                "stage": STAGE,
                "model_tag": MODEL_TAG,
                "source_id": str(row.get("source_id", "")),
                "exchange": str(row.get("exchange", "")),
                "target_date": _target_date(row.get("target_date")),
                "target_year": _as_int(row.get("target_year")),
                "batch_id": _as_int(row.get("batch_id")),
                "needed_products": str(row.get("needed_products", "")),
                "planned_raw_stem": str(row.get("planned_raw_stem", "")),
                "upstream_stage": "Stage091",
                "upstream_line_id": UPSTREAM_LINE_ID,
                "upstream_status": status,
                "upstream_raw_file": raw_file,
                "raw_file_exists": exists,
                "content_bytes": _as_int(row.get("upstream_content_bytes"), observed_bytes),
                "observed_content_bytes": observed_bytes,
                "upstream_sha256": expected_sha,
                "observed_sha256": observed_sha,
                "sha256_file_match": sha_match,
                "upstream_parse_ready": parse_ready,
                "upstream_hash_ready": hash_ready,
                "schema_hash": str(row.get("upstream_schema_hash") or ""),
                "needed_symbol_hit_all": _as_bool(row.get("upstream_needed_symbol_hit_all")),
                "seed_rehydrate_ready": ready,
                "asset_mode": "upstream_reference_no_copy",
                "strategy_rule_created": False,
                "true_engine_allowed": False,
                "signal_audit_allowed": False,
                "seed_blocking_reasons": ",".join(list(dict.fromkeys(reasons))),
                "required_next_before_signal": "schema_binding_audit,numeric_parse_audit,right_tail_missing_safe",
            }
        )
    return pd.DataFrame(rows).sort_values(["source_id", "target_date"]).reset_index(drop=True)


def build_source_summary(seed_index: pd.DataFrame) -> pd.DataFrame:
    if seed_index.empty:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    for source_id, group in seed_index.groupby("source_id", sort=True):
        ready = group["seed_rehydrate_ready"].astype(bool)
        exists = group["raw_file_exists"].astype(bool)
        sha_match = group["sha256_file_match"].astype(bool)
        parsed = group["upstream_parse_ready"].astype(bool)
        rows.append(
            {
                "source_id": source_id,
                "planned_count": int(len(group)),
                "seed_ready_count": int(ready.sum()),
                "raw_file_exists_count": int(exists.sum()),
                "sha256_match_count": int(sha_match.sum()),
                "upstream_parsed_count": int(parsed.sum()),
                "schema_hash_count": int(group["schema_hash"].replace("", np.nan).nunique(dropna=True)),
                "first_target_date": str(group["target_date"].min()),
                "last_target_date": str(group["target_date"].max()),
                "asset_mode": "upstream_reference_no_copy",
                "source_seed_ready": bool(int(ready.sum()) == len(group)),
                "signal_audit_allowed": False,
                "recommended_next_action": "schema_binding_and_numeric_parse_readiness_audit",
            }
        )
    return pd.DataFrame(rows)


def make_seed_rehydration_decision(seed_index: pd.DataFrame) -> dict[str, Any]:
    planned = int(len(seed_index))
    ready = int(seed_index["seed_rehydrate_ready"].astype(bool).sum()) if not seed_index.empty else 0
    source_count = int(seed_index["source_id"].nunique()) if not seed_index.empty else 0
    if planned > 0 and ready == planned:
        decision = "stage032_public_raw_seed_verified_ready_for_schema_binding_no_rule"
        next_direction = "schema_binding_numeric_parse_and_right_tail_missing_audit"
    else:
        decision = "stage032_public_raw_seed_incomplete_keep_data_engineering_no_rule"
        next_direction = "repair_or_download_missing_public_raw_before_schema_binding"
    return {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().replace(microsecond=0).isoformat(),
        "decision": decision,
        "best_next_direction": next_direction,
        "planned_raw_request_count": planned,
        "seed_ready_count": ready,
        "seed_missing_or_bad_count": int(planned - ready),
        "source_count": source_count,
        "asset_mode": "upstream_reference_no_copy",
        "strategy_rule_created": False,
        "official_live_strategy_changed": False,
        "true_engine": False,
        "order_api_called": False,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "ctp_connected": False,
        "external_research_judgment": (
            "Exchange public raw warehouse/member-rank data can be rehydrated from existing verified local raw files. "
            "This reduces external requests, but it is still provenance/data engineering rather than a signal."
        ),
        "overfit_reflection_before": (
            "否。Stage032 只做 raw 文件存在性与 hash 复验，不新增收益筛选、阈值、品种方向或交易规则。"
        ),
        "overfit_reflection_after": (
            "否。即使 raw 种子全量 ready，也只能说明数据地基可复用；不得把 source ready、schema hash 或命中状态交易化。"
        ),
        "continue_value_before": (
            "有。Stage031 已生成 1,504 条请求计划，本阶段确认本地是否已有可复验 raw 种子，避免重复请求交易所。"
        ),
        "continue_value_after": (
            "有。若 seed 全量通过，可进入 schema binding、数值解析和右尾缺失安全审计；仍不能直接回测策略。"
        ),
    }


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_无记录_"
    data = frame.head(max_rows).copy() if max_rows else frame.copy()
    return data.to_markdown(index=False)


def _write_report(decision: dict[str, Any], source_summary: pd.DataFrame) -> None:
    REPORT_OUT.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Stage032 公开 raw 种子复水/hash 审计",
        "",
        "## 结论",
        "",
        f"- 决策：`{decision['decision']}`",
        f"- planned raw：`{decision['planned_raw_request_count']}`",
        f"- seed ready：`{decision['seed_ready_count']}`",
        f"- missing/bad：`{decision['seed_missing_or_bad_count']}`",
        f"- asset mode：`{decision['asset_mode']}`",
        "- 本阶段不复制 raw、不联网、不回测、不写真引擎、不触发订单 API。",
        "",
        "## Source Summary",
        "",
        _md_table(source_summary),
        "",
        "## 外部调研与判断",
        "",
        "- 公开交易所仓单/会员排名历史文件适合作为 raw provenance 资产；交易化前仍需发布时间戳、schema binding、数值字段稳定性和右尾缺失安全审计。",
        "- 本阶段优先引用本地已验证旧线 Stage091 raw，减少重复请求交易所；这不是 alpha 结论。",
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
    REPORT_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_stage_record(decision: dict[str, Any]) -> Path:
    STAGES_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    path = STAGES_DIR / f"{timestamp}_stage032_public_raw_seed_rehydration_audit.md"
    lines = [
        "# Stage032 公开 raw 种子复水/hash 审计",
        "",
        f"- line_id：`{LINE_ID}`",
        "- 当前模式：day",
        f"- 记录时间：{decision['generated_at']}",
        "- 阶段性质：只读数据工程；引用旧线 raw 种子并重算 hash；不联网、不复制 raw、不回测、不改策略、不连接 CTP、不调用下单",
        "- 是否重要突破：否",
        "- 是否触发A/B：否",
        "",
        "## 外部调研与判断",
        "",
        "- 参考交易所公开仓单/排名页面、AKShare 期货数据文档、旧线 Stage091 全量 raw backfill 产物。",
        "- 我的判断：本地旧线 Stage091 raw 若 hash 全量一致，可以作为二期线继续 schema/numeric/right-tail 审计的种子；但不构成策略候选。",
        "",
        "## 本次变更",
        "",
        f"- 新增脚本：`{Path(__file__).relative_to(PROJECT_DIR)}`",
        "- 新增测试：`tests/test_rebuilt_c9_v2_stage032_public_raw_seed_rehydration.py`",
        "- 新增参数：无交易参数；`asset_mode=upstream_reference_no_copy`。",
        "- 修改参数：无",
        "- 删除参数：无",
        "",
        "## 结果",
        "",
        f"- planned_raw_request_count：`{decision['planned_raw_request_count']}`",
        f"- seed_ready_count：`{decision['seed_ready_count']}`",
        f"- seed_missing_or_bad_count：`{decision['seed_missing_or_bad_count']}`",
        f"- source_count：`{decision['source_count']}`",
        f"- 决策：`{decision['decision']}`",
        f"- 下一方向：`{decision['best_next_direction']}`",
        "",
        "## 输出文件",
        "",
        f"- seed_index：`{SEED_INDEX_OUT}`",
        f"- source_summary：`{SOURCE_SUMMARY_OUT}`",
        f"- decision：`{DECISION_OUT}`",
        f"- report：`{REPORT_OUT}`",
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
    plan = _read_csv(BATCH_PLAN_IN)
    upstream = _read_csv(UPSTREAM_RESULTS_IN)
    seed_index = build_seed_index(plan, upstream, repo_dir=PROJECT_DIR)
    source_summary = build_source_summary(seed_index)
    decision = make_seed_rehydration_decision(seed_index)

    seed_index.to_csv(SEED_INDEX_OUT, index=False, encoding="utf-8-sig")
    source_summary.to_csv(SOURCE_SUMMARY_OUT, index=False, encoding="utf-8-sig")
    _write_report(decision, source_summary)
    stage_record = _write_stage_record(decision)

    decision["outputs"] = {
        "seed_index": SEED_INDEX_OUT,
        "source_summary": SOURCE_SUMMARY_OUT,
        "decision": DECISION_OUT,
        "report": REPORT_OUT,
        "stage_record": stage_record,
    }
    DECISION_OUT.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
