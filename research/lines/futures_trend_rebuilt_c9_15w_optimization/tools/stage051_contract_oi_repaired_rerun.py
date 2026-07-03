from __future__ import annotations

from datetime import datetime
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from stage038_candidate_pit_feature_matrix_audit import build_purged_time_splits, summarize_condition_oos
from stage049_contract_oi_migration_audit import (
    EMBARGO_DAYS,
    MAIN_MAPPING_PATH,
    N_SPLITS,
    OBJECTIVE_ENTRY_END,
    SOURCE_START,
    STAGE038_FEATURE_MATRIX_PATH,
    _build_condition_specs,
    _feature_coverage,
    _product_key,
    _product_summary,
    _source_summary,
    _state_summary,
    attach_contract_oi_features,
    build_contract_oi_snapshots,
    load_contract_daily_bars,
    load_main_contract_mapping,
)


LINE_ID = "futures_trend_rebuilt_c9_15w_optimization"
STAGE = "Stage051"
MODEL_TAG = "stage051_contract_oi_repaired_rerun_v1"
OUTPUT_PREFIX = "rebuilt_c9_stage051_contract_oi_repaired_rerun"

PRODUCT_VT_SYMBOL = "jd.DCE"
REPAIR_START = pd.Timestamp("2026-03-27")

TOOLS_DIR = Path(__file__).resolve().parent
LINE_DIR = TOOLS_DIR.parent
OUTPUT_DIR = LINE_DIR / "outputs" / "stage051_contract_oi_repaired_rerun"
STAGES_DIR = LINE_DIR / "stages"

STAGE050_OUTPUT_DIR = LINE_DIR / "outputs" / "stage050_jd_contract_oi_source_repair"
STAGE050_PREFIX = "rebuilt_c9_stage050_jd_contract_oi_source_repair"
STAGE050_TAG = "stage050_jd_contract_oi_source_repair_v1"
STAGE050_MAPPING_PATH = STAGE050_OUTPUT_DIR / f"{STAGE050_PREFIX}_combined_mapping_{STAGE050_TAG}.csv"
STAGE050_BARS_PATH = STAGE050_OUTPUT_DIR / f"{STAGE050_PREFIX}_contract_bars_{STAGE050_TAG}.csv"
STAGE050_DECISION_PATH = STAGE050_OUTPUT_DIR / f"{STAGE050_PREFIX}_decision_{STAGE050_TAG}.json"

SNAPSHOTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_contract_oi_snapshots_{MODEL_TAG}.csv"
JOINED_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_joined_feature_matrix_{MODEL_TAG}.csv"
CONDITION_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_condition_oos_summary_{MODEL_TAG}.csv"
FEATURE_COVERAGE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_feature_coverage_{MODEL_TAG}.csv"
PRODUCT_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_summary_{MODEL_TAG}.csv"
SOURCE_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_source_summary_{MODEL_TAG}.csv"
STATE_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_state_summary_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


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


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_无数据_"
    shown = frame.head(max_rows).copy() if max_rows is not None else frame.copy()
    for column in shown.columns:
        if pd.api.types.is_float_dtype(shown[column]):
            shown[column] = shown[column].map(lambda value: f"{value:.4f}" if pd.notna(value) else "")
    return shown.to_markdown(index=False)


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path, encoding="utf-8-sig")


def _normalise_dates(frame: pd.DataFrame, column: str) -> pd.DataFrame:
    result = frame.copy()
    result[column] = pd.to_datetime(result[column], errors="coerce").dt.normalize()
    return result


def merge_repaired_jd_bars(base_bars: pd.DataFrame, repair_bars: pd.DataFrame, *, repair_start: pd.Timestamp = REPAIR_START) -> pd.DataFrame:
    base = base_bars.copy()
    repair = repair_bars.copy()
    if base.empty:
        base["datetime"] = pd.Series(dtype="datetime64[ns]")
    else:
        base = _normalise_dates(base, "datetime")
    if not repair.empty:
        repair = _normalise_dates(repair, "datetime")
    if "contract_vt_symbol" not in base.columns:
        base["contract_vt_symbol"] = base["symbol"].astype(str) + "." + base["exchange"].astype(str)
    if "contract_vt_symbol" not in repair.columns and not repair.empty:
        repair["contract_vt_symbol"] = repair["symbol"].astype(str) + "." + repair["exchange"].astype(str)
    is_jd_gap = (
        base["contract_vt_symbol"].fillna("").astype(str).str.lower().str.startswith("jd")
        & base["datetime"].ge(pd.Timestamp(repair_start).normalize())
    )
    merged = pd.concat([base.loc[~is_jd_gap].copy(), repair], ignore_index=True)
    if merged.empty:
        return merged
    merged["datetime"] = pd.to_datetime(merged["datetime"], errors="coerce").dt.normalize()
    if "feature_date" not in merged.columns:
        merged["feature_date"] = merged["datetime"]
    else:
        merged["feature_date"] = pd.to_datetime(merged["feature_date"], errors="coerce").dt.normalize()
        missing_feature_date = merged["feature_date"].isna()
        merged.loc[missing_feature_date, "feature_date"] = merged.loc[missing_feature_date, "datetime"]
    merged["product_vt_symbol"] = merged.get("product_vt_symbol", pd.Series("", index=merged.index)).fillna("")
    jd_contract = merged["contract_vt_symbol"].fillna("").astype(str).str.lower().str.startswith("jd")
    merged.loc[jd_contract, "product_vt_symbol"] = PRODUCT_VT_SYMBOL
    merged["product_key"] = merged["product_vt_symbol"].fillna("").astype(str).str.lower()
    merged.drop_duplicates(["datetime", "contract_vt_symbol"], keep="last", inplace=True)
    return merged.sort_values(["contract_vt_symbol", "datetime"]).reset_index(drop=True)


def merge_repaired_jd_mapping(base_mapping: pd.DataFrame, repair_mapping: pd.DataFrame) -> pd.DataFrame:
    base = base_mapping.copy()
    repair = repair_mapping.copy()
    if not base.empty:
        if "date" in base.columns and "feature_date" not in base.columns:
            base["feature_date"] = pd.to_datetime(base["date"], errors="coerce").dt.normalize()
        elif "feature_date" in base.columns:
            base["feature_date"] = pd.to_datetime(base["feature_date"], errors="coerce").dt.normalize()
        base["continuous_symbol_vt"] = base.get("continuous_symbol_vt", base.get("product_vt_symbol", "")).fillna("").astype(str)
    if not repair.empty:
        if "date" in repair.columns and "feature_date" not in repair.columns:
            repair["feature_date"] = pd.to_datetime(repair["date"], errors="coerce").dt.normalize()
        elif "feature_date" in repair.columns:
            repair["feature_date"] = pd.to_datetime(repair["feature_date"], errors="coerce").dt.normalize()
        repair["continuous_symbol_vt"] = repair.get("continuous_symbol_vt", repair.get("product_vt_symbol", "")).fillna("").astype(str)
    base = base[~base["continuous_symbol_vt"].eq(PRODUCT_VT_SYMBOL)].copy()
    merged = pd.concat([base, repair], ignore_index=True)
    if "date" not in merged.columns:
        merged["date"] = merged["feature_date"]
    merged["date"] = pd.to_datetime(merged["date"], errors="coerce").dt.normalize()
    merged["feature_date"] = pd.to_datetime(merged["feature_date"], errors="coerce").dt.normalize()
    if "product_vt_symbol" not in merged.columns:
        merged["product_vt_symbol"] = merged["continuous_symbol_vt"]
    merged["product_vt_symbol"] = merged["product_vt_symbol"].fillna(merged["continuous_symbol_vt"]).astype(str)
    merged["product_key"] = merged["product_vt_symbol"].fillna("").astype(str).str.lower()
    merged.drop_duplicates(["date", "continuous_symbol_vt"], keep="last", inplace=True)
    return merged.sort_values(["date", "continuous_symbol_vt"]).reset_index(drop=True)


def decide_repaired_contract_oi(
    *,
    stable_conditions: list[str],
    matched_rate: float,
    source_gap_products: list[str],
) -> str:
    if stable_conditions and matched_rate >= 0.90 and not source_gap_products:
        return "stage051_contract_oi_migration_source_gap_cleared_ready_for_proxy"
    if source_gap_products:
        return "stage051_contract_oi_migration_source_gap_still_open"
    return "stage051_contract_oi_migration_no_stable_candidate_after_repair"


def _decision(matrix: pd.DataFrame, condition_summary: pd.DataFrame, source_summary: pd.DataFrame) -> dict[str, Any]:
    stable = condition_summary[condition_summary["stable_oos_candidate"].astype(bool)].copy()
    matched_count = int(matrix["contract_oi_matched"].sum()) if "contract_oi_matched" in matrix.columns else 0
    matched_rate = float(matched_count / len(matrix)) if len(matrix) else 0.0
    source_gap_products = source_summary[
        ~source_summary["covers_entry_end_tminus1"].astype(bool)
    ]["product_vt_symbol"].tolist()
    decision = decide_repaired_contract_oi(
        stable_conditions=stable["condition"].head(10).tolist(),
        matched_rate=matched_rate,
        source_gap_products=source_gap_products,
    )
    next_stage = (
        "freeze_contract_oi_share_ge50_proxy_before_true_engine"
        if decision == "stage051_contract_oi_migration_source_gap_cleared_ready_for_proxy"
        else "repair_remaining_source_gap_or_stop_contract_oi_route"
    )
    return {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "line_id": LINE_ID,
        "decision": decision,
        "next_stage": next_stage,
        "entry_count": int(len(matrix)),
        "matched_count": matched_count,
        "matched_rate": matched_rate,
        "stable_conditions": stable["condition"].head(10).tolist(),
        "source_gap_products": source_gap_products,
        "stage050_mapping_path": str(STAGE050_MAPPING_PATH),
        "stage050_bars_path": str(STAGE050_BARS_PATH),
        "stage050_decision_path": str(STAGE050_DECISION_PATH),
        "strategy_changed": False,
        "shared_mapping_changed": False,
        "shared_database_changed": False,
        "true_engine": False,
        "ab_triggered": False,
        "ctp_connected": False,
        "order_api_called": False,
        "objective_completion_proven": False,
        "external_research_judgment": (
            "Stage051 reuses the Stage050 line-local TqSdk repair pack. Open interest and main-contract roll "
            "remain source-quality features; this stage only proves the source gap is cleared before proxy testing."
        ),
        "overfit_reflection_before": (
            "否。Stage051 只用 Stage050 的线内修复包重跑固定 Stage049 条件，不新增阈值或收益筛选。"
        ),
        "continue_value_before": (
            "有。只有确认 jd 数据源缺口清零，逐合约 OI 集中度候选才有资格进入下一步 proxy。"
        ),
        "overfit_reflection_after": (
            "否。本阶段仍未写交易规则；后续只能冻结一个条件，不能围绕 OI 占比阈值救参。"
        ),
        "continue_value_after": (
            "有条件。若 source_gap_products 清零且稳定候选仍在，下一步可做一个低自由度 proxy。"
        ),
        "outputs": {
            "snapshots": str(SNAPSHOTS_PATH),
            "joined": str(JOINED_PATH),
            "condition_summary": str(CONDITION_SUMMARY_PATH),
            "feature_coverage": str(FEATURE_COVERAGE_PATH),
            "product_summary": str(PRODUCT_SUMMARY_PATH),
            "source_summary": str(SOURCE_SUMMARY_PATH),
            "state_summary": str(STATE_SUMMARY_PATH),
            "decision": str(DECISION_PATH),
            "report": str(REPORT_PATH),
        },
    }


def _write_report(
    *,
    source_summary: pd.DataFrame,
    feature_coverage: pd.DataFrame,
    condition_summary: pd.DataFrame,
    product_summary: pd.DataFrame,
    state_summary: pd.DataFrame,
    decision: dict[str, Any],
    stage_record_path: Path,
) -> None:
    report = f"""# Stage051 - 修复 jd 源后的逐合约 OI 迁移重跑

- 记录时间：`{datetime.now().strftime('%Y-%m-%dT%H:%M')}`
- line_id：`{LINE_ID}`
- model_tag：`{MODEL_TAG}`
- 决策：`{decision['decision']}`

## 口径

- 复用 Stage049 固定条件、OOS split 与 T+1 点时规则。
- 仅把 `jd.DCE` 数据源替换为 Stage050 线内修复包。
- 不修改共享 mapping CSV，不写 SQLite 数据库，不改 C9/15w 配置，不连接 CTP，不调用订单 API。

## 数据源覆盖

{_md_table(source_summary)}

## 特征覆盖

{_md_table(feature_coverage)}

## 状态摘要

{_md_table(state_summary)}

## 条件 OOS 摘要

{_md_table(condition_summary, max_rows=20)}

## 品种摘要

{_md_table(product_summary.head(30))}

## 判断

- 命中：`{decision['matched_count']}/{decision['entry_count']}`，命中率 `{decision['matched_rate']:.4%}`。
- 稳定 OOS 候选：`{decision['stable_conditions']}`。
- 数据缺口品种：`{decision['source_gap_products']}`。

## 输出

- snapshots：`{SNAPSHOTS_PATH}`
- joined：`{JOINED_PATH}`
- condition_summary：`{CONDITION_SUMMARY_PATH}`
- feature_coverage：`{FEATURE_COVERAGE_PATH}`
- product_summary：`{PRODUCT_SUMMARY_PATH}`
- source_summary：`{SOURCE_SUMMARY_PATH}`
- state_summary：`{STATE_SUMMARY_PATH}`
- decision：`{DECISION_PATH}`
- report：`{REPORT_PATH}`
- stage_record：`{stage_record_path}`

## 反思

- 运行前过拟合反思：{decision['overfit_reflection_before']}
- 运行后过拟合反思：{decision['overfit_reflection_after']}
- 运行前继续价值反思：{decision['continue_value_before']}
- 运行后继续价值反思：{decision['continue_value_after']}
"""
    REPORT_PATH.write_text(report, encoding="utf-8")


def _write_stage_record(decision: dict[str, Any], condition_summary: pd.DataFrame, source_summary: pd.DataFrame) -> Path:
    timestamp = datetime.now()
    stage_path = STAGES_DIR / f"{timestamp:%Y%m%d_%H%M}_stage051_contract_oi_repaired_rerun.md"
    lines = [
        "# Stage051 - 修复 jd 源后的逐合约 OI 迁移重跑",
        "",
        f"- 记录时间：`{timestamp.isoformat(timespec='minutes')}`",
        f"- line_id：`{LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        "- 是否重要突破版本：`否`",
        f"- 决策：`{decision['decision']}`",
        "",
        "## 本次版本变更",
        "",
        f"- 新增脚本：`research/lines/{LINE_ID}/tools/stage051_contract_oi_repaired_rerun.py`",
        "- 新增测试：`tests/test_rebuilt_c9_stage051_repaired_contract_oi.py`",
        "- 新增参数：无，复用 Stage049 固定条件和 Stage050 数据修复包。",
        "- 修改参数：无，官方 C9/15w 配置未改。",
        "- 删除参数：无。",
        "- 新增回测结果：无，本阶段不是收益回测，只做修复源后的候选级审计重跑。",
        "- 共享 mapping CSV 未改；共享 SQLite 数据库未写；不连接 CTP，不调用订单 API，不触发 A/B。",
        "",
        "## 审计结果",
        "",
        f"- entry_count：`{decision['entry_count']}`",
        f"- matched：`{decision['matched_count']}`，matched_rate：`{decision['matched_rate']:.4%}`",
        f"- stable_conditions：`{', '.join(decision['stable_conditions']) if decision['stable_conditions'] else '无'}`",
        f"- source_gap_products：`{', '.join(decision['source_gap_products']) if decision['source_gap_products'] else '无'}`",
        "",
        "## 条件摘要",
        "",
        _md_table(
            condition_summary[
                [
                    "condition",
                    "candidate_eligible",
                    "count",
                    "total_pnl",
                    "mean_pnl_lift_vs_base",
                    "win_rate_lift_pp",
                    "oos_positive_fold_count",
                    "oos_test_fold_count",
                    "oos_min_fold_pnl",
                    "stable_oos_candidate",
                ]
            ],
            max_rows=20,
        ),
        "",
        "## 数据源覆盖",
        "",
        _md_table(source_summary, max_rows=30),
        "",
        "## 输出",
        "",
        f"- snapshots：`{SNAPSHOTS_PATH}`",
        f"- joined：`{JOINED_PATH}`",
        f"- condition_summary：`{CONDITION_SUMMARY_PATH}`",
        f"- feature_coverage：`{FEATURE_COVERAGE_PATH}`",
        f"- product_summary：`{PRODUCT_SUMMARY_PATH}`",
        f"- source_summary：`{SOURCE_SUMMARY_PATH}`",
        f"- state_summary：`{STATE_SUMMARY_PATH}`",
        f"- decision：`{DECISION_PATH}`",
        f"- report：`{REPORT_PATH}`",
        "",
        "## 反思",
        "",
        f"- 运行前过拟合反思：{decision['overfit_reflection_before']}",
        f"- 运行后过拟合反思：{decision['overfit_reflection_after']}",
        f"- 运行前继续价值反思：{decision['continue_value_before']}",
        f"- 运行后继续价值反思：{decision['continue_value_after']}",
        "",
        "## 后续规划和 TODO",
        "",
        f"- 下一步：`{decision['next_stage']}`。",
        "- 若进入 proxy，只能冻结 `contract_oi_share_ge50` 等一个低自由度条件，不允许扫 OI 阈值。",
    ]
    stage_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return stage_path


def run() -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    STAGES_DIR.mkdir(parents=True, exist_ok=True)
    entries = _read_csv(STAGE038_FEATURE_MATRIX_PATH)
    entries["entry_date"] = pd.to_datetime(entries["entry_date"], errors="coerce").dt.normalize()
    entry_products = set(entries.get("product_vt_symbol", pd.Series(dtype=str)).dropna().map(_product_key))
    product_keys = entry_products | {_product_key(PRODUCT_VT_SYMBOL)}

    base_bars = load_contract_daily_bars(start=SOURCE_START, end=OBJECTIVE_ENTRY_END, product_keys=product_keys)
    repair_bars = _read_csv(STAGE050_BARS_PATH)
    bars = merge_repaired_jd_bars(base_bars, repair_bars)

    base_mapping = load_main_contract_mapping(MAIN_MAPPING_PATH, start=SOURCE_START, end=OBJECTIVE_ENTRY_END, product_keys=product_keys)
    repair_mapping = _read_csv(STAGE050_MAPPING_PATH)
    mapping = merge_repaired_jd_mapping(base_mapping, repair_mapping)

    snapshots = build_contract_oi_snapshots(bars, mapping)
    matrix = attach_contract_oi_features(entries, snapshots)
    conditions = _build_condition_specs(matrix)
    splits = build_purged_time_splits(matrix, date_column="entry_date", n_splits=N_SPLITS, embargo_days=EMBARGO_DAYS)
    condition_summary = summarize_condition_oos(matrix, splits, conditions)
    feature_coverage = _feature_coverage(matrix)
    product_summary = _product_summary(matrix)
    source_summary = _source_summary(entries, snapshots, mapping)
    state_summary = _state_summary(matrix)
    decision = _decision(matrix, condition_summary, source_summary)

    snapshots.to_csv(SNAPSHOTS_PATH, index=False, encoding="utf-8-sig")
    matrix.to_csv(JOINED_PATH, index=False, encoding="utf-8-sig")
    condition_summary.to_csv(CONDITION_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    feature_coverage.to_csv(FEATURE_COVERAGE_PATH, index=False, encoding="utf-8-sig")
    product_summary.to_csv(PRODUCT_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    source_summary.to_csv(SOURCE_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    state_summary.to_csv(STATE_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    stage_record = _write_stage_record(decision, condition_summary, source_summary)
    _write_report(
        source_summary=source_summary,
        feature_coverage=feature_coverage,
        condition_summary=condition_summary,
        product_summary=product_summary,
        state_summary=state_summary,
        decision=decision,
        stage_record_path=stage_record,
    )
    decision["stage_record_path"] = str(stage_record)
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return decision


def main() -> None:
    decision = run()
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
