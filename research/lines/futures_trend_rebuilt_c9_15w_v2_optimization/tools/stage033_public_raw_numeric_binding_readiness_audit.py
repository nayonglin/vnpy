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
STAGE = "Stage033"
MODEL_TAG = "stage033_public_raw_numeric_binding_readiness_audit_v1"
OUTPUT_PREFIX = "rebuilt_c9_v2_stage033_public_raw_numeric_binding_readiness_audit"

LINE_DIR = PROJECT_DIR / "research" / "lines" / LINE_ID
UPSTREAM_LINE_DIR = PROJECT_DIR / "research" / "lines" / UPSTREAM_LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage033_public_raw_numeric_binding_readiness_audit"
STAGES_DIR = LINE_DIR / "stages"

STAGE032_DIR = LINE_DIR / "outputs" / "stage032_public_raw_seed_rehydration_audit"
SEED_INDEX_IN = (
    STAGE032_DIR
    / "rebuilt_c9_v2_stage032_public_raw_seed_rehydration_audit_seed_index_"
    "stage032_public_raw_seed_rehydration_audit_v1.csv"
)
UPSTREAM_STAGE095_DIR = UPSTREAM_LINE_DIR / "outputs" / "stage095_full_numeric_feature_extraction_stability_audit"
UPSTREAM_NUMERIC_ROWS_IN = (
    UPSTREAM_STAGE095_DIR
    / "qmt_roll_stage095_c9_minrisk_full_numeric_feature_extraction_stability_audit_feature_rows_"
    "stage095_full_numeric_feature_extraction_stability_audit_v1.csv"
)
UPSTREAM_LOT_SUMMARY_IN = (
    UPSTREAM_STAGE095_DIR
    / "qmt_roll_stage095_c9_minrisk_full_numeric_feature_extraction_stability_audit_lot_summary_"
    "stage095_full_numeric_feature_extraction_stability_audit_v1.csv"
)
UPSTREAM_FIELD_SUMMARY_IN = (
    UPSTREAM_STAGE095_DIR
    / "qmt_roll_stage095_c9_minrisk_full_numeric_feature_extraction_stability_audit_field_summary_"
    "stage095_full_numeric_feature_extraction_stability_audit_v1.csv"
)

BINDING_ROWS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_binding_rows_{MODEL_TAG}.csv"
SOURCE_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_source_summary_{MODEL_TAG}.csv"
FIELD_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_field_summary_{MODEL_TAG}.csv"
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


def build_binding_rows(seed_index: pd.DataFrame, numeric_rows: pd.DataFrame) -> pd.DataFrame:
    required_seed = {"source_id", "target_date", "upstream_raw_file", "upstream_sha256", "seed_rehydrate_ready"}
    required_numeric = {
        "source_id",
        "target_date",
        "raw_file",
        "sha256",
        "product_present_state",
        "numeric_feature_ready",
        "strategy_rule_allowed",
        "true_engine_allowed",
        "field_parse_status",
    }
    missing_seed = required_seed - set(seed_index.columns)
    missing_numeric = required_numeric - set(numeric_rows.columns)
    if missing_seed:
        raise ValueError(f"seed_index missing columns: {sorted(missing_seed)}")
    if missing_numeric:
        raise ValueError(f"numeric_rows missing columns: {sorted(missing_numeric)}")

    seed = seed_index.copy()
    numeric = numeric_rows.copy()
    for frame in [seed, numeric]:
        frame["source_id"] = frame["source_id"].astype(str)
        frame["target_date"] = frame["target_date"].map(_target_date)
        frame["_key"] = frame["source_id"] + ":" + frame["target_date"]

    seed = seed.sort_values(["source_id", "target_date"]).drop_duplicates("_key")
    merged = numeric.merge(
        seed.add_prefix("seed_"),
        left_on="_key",
        right_on="seed__key",
        how="left",
    )

    rows: list[dict[str, Any]] = []
    for row in merged.to_dict("records"):
        seed_found = str(row.get("seed_source_id") or "nan") != "nan"
        seed_ready = _as_bool(row.get("seed_seed_rehydrate_ready"))
        raw_match = seed_found and str(row.get("raw_file") or "") == str(row.get("seed_upstream_raw_file") or "")
        sha_match = seed_found and str(row.get("sha256") or "") == str(row.get("seed_upstream_sha256") or "")
        strategy_allowed = _as_int(row.get("strategy_rule_allowed")) > 0
        true_engine_allowed = _as_int(row.get("true_engine_allowed")) > 0
        present = str(row.get("product_present_state") or "") == "present"
        numeric_ready = _as_bool(row.get("numeric_feature_ready"))

        reasons: list[str] = []
        if not seed_found:
            reasons.append("seed_missing")
        if seed_found and not seed_ready:
            reasons.append("seed_not_ready")
        if seed_found and not raw_match:
            reasons.append("seed_raw_file_mismatch")
        if seed_found and not sha_match:
            reasons.append("seed_sha256_mismatch")
        if present and not numeric_ready:
            reasons.append("present_numeric_not_ready")
        if str(row.get("field_parse_status") or "") in {
            "parse_exception",
            "warehouse_header_not_found",
            "warehouse_total_row_not_found",
            "member_rank_header_not_found",
            "member_rank_total_or_rank_rows_not_found",
        }:
            reasons.append("parse_error_status")
        if strategy_allowed:
            reasons.append("strategy_rule_unexpectedly_allowed")
        if true_engine_allowed:
            reasons.append("true_engine_unexpectedly_allowed")

        seed_link_ready = bool(seed_found and seed_ready and raw_match and sha_match)
        numeric_binding_ready = bool(seed_link_ready and (not present or numeric_ready) and not strategy_allowed and not true_engine_allowed)
        out = dict(row)
        out.update(
            {
                "stage": STAGE,
                "model_tag": MODEL_TAG,
                "seed_line_id": LINE_ID,
                "upstream_numeric_line_id": UPSTREAM_LINE_ID,
                "seed_link_ready": seed_link_ready,
                "numeric_binding_ready": numeric_binding_ready,
                "read_only_signal_audit_allowed_next": False,
                "strategy_rule_allowed": False,
                "true_engine_allowed": False,
                "binding_blocking_reasons": ",".join(list(dict.fromkeys(reasons))),
            }
        )
        rows.append(out)

    return pd.DataFrame(rows).sort_values(["source_id", "target_date"]).reset_index(drop=True)


def build_source_summary(binding_rows: pd.DataFrame) -> pd.DataFrame:
    if binding_rows.empty:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    for source_id, group in binding_rows.groupby("source_id", sort=True):
        present = group["product_present_state"].astype(str).eq("present")
        right_tail = pd.to_numeric(group.get("right_tail_top10", 0), errors="coerce").fillna(0).astype(int).eq(1)
        rows.append(
            {
                "source_id": source_id,
                "feature_row_count": int(len(group)),
                "target_date_count": int(group["target_date"].nunique()),
                "linked_lot_count": int(group["lot_id"].nunique()) if "lot_id" in group else 0,
                "product_count": int(group["product_root"].nunique()) if "product_root" in group else 0,
                "seed_link_ready_count": int(group["seed_link_ready"].astype(bool).sum()),
                "numeric_binding_ready_count": int(group["numeric_binding_ready"].astype(bool).sum()),
                "present_feature_row_count": int(present.sum()),
                "present_numeric_ready_count": int(
                    pd.to_numeric(group.get("present_numeric_ready", 0), errors="coerce").fillna(0).sum()
                ),
                "right_tail_feature_row_count": int(right_tail.sum()),
                "right_tail_numeric_binding_ready_count": int(group.loc[right_tail, "numeric_binding_ready"].astype(bool).sum()),
                "strategy_rule_allowed_count": int(pd.to_numeric(group.get("strategy_rule_allowed", 0), errors="coerce").fillna(0).sum()),
                "true_engine_allowed_count": int(pd.to_numeric(group.get("true_engine_allowed", 0), errors="coerce").fillna(0).sum()),
                "source_binding_ready": bool(group["numeric_binding_ready"].astype(bool).all()),
            }
        )
    return pd.DataFrame(rows)


def make_numeric_binding_decision(binding_rows: pd.DataFrame, lot_summary: pd.DataFrame) -> dict[str, Any]:
    total = int(len(binding_rows))
    ready = int(binding_rows["numeric_binding_ready"].astype(bool).sum()) if not binding_rows.empty else 0
    present = binding_rows[binding_rows["product_present_state"].astype(str).eq("present")].copy() if not binding_rows.empty else pd.DataFrame()
    present_count = int(len(present))
    present_ready = int(pd.to_numeric(present.get("present_numeric_ready", 0), errors="coerce").fillna(0).sum()) if not present.empty else 0
    strategy_allowed = int(pd.to_numeric(binding_rows.get("strategy_rule_allowed", 0), errors="coerce").fillna(0).sum()) if not binding_rows.empty else 0
    true_engine_allowed = int(pd.to_numeric(binding_rows.get("true_engine_allowed", 0), errors="coerce").fillna(0).sum()) if not binding_rows.empty else 0

    lot = lot_summary.copy()
    right_tail_count = int(pd.to_numeric(lot.get("right_tail_top10", 0), errors="coerce").fillna(0).sum()) if not lot.empty else 0
    right_tail_ready = int(
        pd.to_numeric(
            lot.loc[pd.to_numeric(lot.get("right_tail_top10", 0), errors="coerce").fillna(0).eq(1), "all_present_numeric_ready"],
            errors="coerce",
        )
        .fillna(0)
        .sum()
    ) if not lot.empty and "all_present_numeric_ready" in lot.columns else 0

    parse_error_statuses = {
        "parse_exception",
        "warehouse_header_not_found",
        "warehouse_total_row_not_found",
        "member_rank_header_not_found",
        "member_rank_total_or_rank_rows_not_found",
    }
    parse_error_count = int(binding_rows["field_parse_status"].astype(str).isin(parse_error_statuses).sum()) if not binding_rows.empty else 0
    all_ready = bool(
        total > 0
        and ready == total
        and present_ready == present_count
        and right_tail_ready == right_tail_count
        and parse_error_count == 0
        and strategy_allowed == 0
        and true_engine_allowed == 0
    )
    decision = (
        "stage033_public_raw_numeric_binding_ready_for_readonly_signal_audit_no_rule"
        if all_ready
        else "stage033_public_raw_numeric_binding_has_gaps_no_rule"
    )
    return {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().replace(microsecond=0).isoformat(),
        "decision": decision,
        "best_next_direction": (
            "predeclared_readonly_signal_audit_no_true_engine"
            if all_ready
            else "repair_numeric_binding_before_signal_audit"
        ),
        "feature_row_count": total,
        "numeric_binding_ready_count": ready,
        "present_feature_row_count": present_count,
        "present_numeric_ready_count": present_ready,
        "linked_lot_count": int(lot["lot_id"].nunique()) if not lot.empty and "lot_id" in lot.columns else 0,
        "right_tail_lot_count": right_tail_count,
        "right_tail_all_present_numeric_ready_count": right_tail_ready,
        "source_count": int(binding_rows["source_id"].nunique()) if not binding_rows.empty else 0,
        "parse_error_count": parse_error_count,
        "read_only_signal_audit_allowed_next": all_ready,
        "immediate_strategy_candidate_count": 0,
        "strategy_rule_created": False,
        "official_live_strategy_changed": False,
        "true_engine": False,
        "order_api_called": False,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "ctp_connected": False,
        "external_research_judgment": (
            "Inventory and member-position raw fields have plausible supply-demand and crowding meaning, "
            "but the literature and public data examples support treating them as theory-grounded candidates "
            "only after PIT, numeric and right-tail-readiness gates pass."
        ),
        "overfit_reflection_before": (
            "否。Stage033 只做二期 seed 与旧线数值绑定结果的可追溯审计，不新增收益阈值或交易规则。"
        ),
        "overfit_reflection_after": (
            "否。即使进入只读信号审计，也只能预声明经济语义和固定字段；不得按历史收益直接挑字段、阈值或品种。"
        ),
        "continue_value_before": (
            "有。Stage032 证明 raw seed 可复验，本阶段确认数值字段和右尾 lot 是否具备只读信号审计的最低数据条件。"
        ),
        "continue_value_after": (
            "有。若本阶段全量通过，下一步可以做预声明 readonly signal audit；仍不能进 true engine 或 A/B。"
        ),
    }


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_无记录_"
    data = frame.head(max_rows).copy() if max_rows else frame.copy()
    return data.to_markdown(index=False)


def _write_report(decision: dict[str, Any], source_summary: pd.DataFrame, field_summary: pd.DataFrame) -> None:
    REPORT_OUT.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Stage033 公开 raw 数值绑定 readiness 审计",
        "",
        "## 结论",
        "",
        f"- 决策：`{decision['decision']}`",
        f"- feature rows：`{decision['feature_row_count']}`",
        f"- numeric binding ready：`{decision['numeric_binding_ready_count']}` / `{decision['feature_row_count']}`",
        f"- present numeric ready：`{decision['present_numeric_ready_count']}` / `{decision['present_feature_row_count']}`",
        f"- right-tail ready：`{decision['right_tail_all_present_numeric_ready_count']}` / `{decision['right_tail_lot_count']}`",
        f"- read-only signal audit next：`{decision['read_only_signal_audit_allowed_next']}`",
        "- 本阶段不回测、不写真引擎、不触发订单 API。",
        "",
        "## Source Summary",
        "",
        _md_table(source_summary),
        "",
        "## Field Summary",
        "",
        _md_table(field_summary, max_rows=80),
        "",
        "## 外部调研与判断",
        "",
        "- 公开资料和商品期货研究支持把库存、basis、会员/持仓结构视为供需、carry、拥挤度相关候选；但必须先通过 PIT、数值、右尾保护和只读审计。",
        "- 本阶段只确认数据可审计，不得把字段本身或 ready 状态交易化。",
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
    path = STAGES_DIR / f"{timestamp}_stage033_public_raw_numeric_binding_readiness_audit.md"
    lines = [
        "# Stage033 公开 raw 数值绑定 readiness 审计",
        "",
        f"- line_id：`{LINE_ID}`",
        "- 当前模式：day",
        f"- 记录时间：{decision['generated_at']}",
        "- 阶段性质：只读数据 readiness；对齐 Stage032 seed 与旧线 Stage095 数值字段；不回测、不改策略、不连接 CTP、不调用下单",
        "- 是否重要突破：否",
        "- 是否触发A/B：否",
        "",
        "## 外部调研与判断",
        "",
        "- 参考商品期货库存/basis/会员结构相关公开研究、AKShare 期货数据文档、旧线 Stage093/095 数值解析产物。",
        "- 我的判断：数值字段如果和二期 seed 全量可追溯，可以进入预声明只读信号审计；但仍不构成策略候选。",
        "",
        "## 本次变更",
        "",
        f"- 新增脚本：`{Path(__file__).relative_to(PROJECT_DIR)}`",
        "- 新增测试：`tests/test_rebuilt_c9_v2_stage033_public_raw_numeric_binding_readiness.py`",
        "- 新增参数：无交易参数。",
        "- 修改参数：无",
        "- 删除参数：无",
        "",
        "## 结果",
        "",
        f"- feature_row_count：`{decision['feature_row_count']}`",
        f"- numeric_binding_ready_count：`{decision['numeric_binding_ready_count']}`",
        f"- present_numeric_ready：`{decision['present_numeric_ready_count']}/{decision['present_feature_row_count']}`",
        f"- right_tail_all_present_numeric_ready：`{decision['right_tail_all_present_numeric_ready_count']}/{decision['right_tail_lot_count']}`",
        f"- read_only_signal_audit_allowed_next：`{decision['read_only_signal_audit_allowed_next']}`",
        f"- immediate_strategy_candidate_count：`{decision['immediate_strategy_candidate_count']}`",
        f"- 决策：`{decision['decision']}`",
        f"- 下一方向：`{decision['best_next_direction']}`",
        "",
        "## 输出文件",
        "",
        f"- binding_rows：`{BINDING_ROWS_OUT}`",
        f"- source_summary：`{SOURCE_SUMMARY_OUT}`",
        f"- field_summary：`{FIELD_SUMMARY_OUT}`",
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
    seed_index = _read_csv(SEED_INDEX_IN)
    numeric_rows = _read_csv(UPSTREAM_NUMERIC_ROWS_IN)
    lot_summary = _read_csv(UPSTREAM_LOT_SUMMARY_IN)
    field_summary = _read_csv(UPSTREAM_FIELD_SUMMARY_IN)

    binding_rows = build_binding_rows(seed_index, numeric_rows)
    source_summary = build_source_summary(binding_rows)
    decision = make_numeric_binding_decision(binding_rows, lot_summary)

    binding_rows.to_csv(BINDING_ROWS_OUT, index=False, encoding="utf-8-sig")
    source_summary.to_csv(SOURCE_SUMMARY_OUT, index=False, encoding="utf-8-sig")
    field_summary.to_csv(FIELD_SUMMARY_OUT, index=False, encoding="utf-8-sig")
    _write_report(decision, source_summary, field_summary)
    stage_record = _write_stage_record(decision)

    decision["outputs"] = {
        "binding_rows": BINDING_ROWS_OUT,
        "source_summary": SOURCE_SUMMARY_OUT,
        "field_summary": FIELD_SUMMARY_OUT,
        "decision": DECISION_OUT,
        "report": REPORT_OUT,
        "stage_record": stage_record,
    }
    DECISION_OUT.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
