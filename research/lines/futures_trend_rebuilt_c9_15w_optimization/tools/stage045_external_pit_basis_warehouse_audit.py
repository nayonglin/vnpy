from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from stage038_candidate_pit_feature_matrix_audit import (
    ConditionSpec,
    build_purged_time_splits,
    summarize_condition_oos,
)


LINE_ID = "futures_trend_rebuilt_c9_15w_optimization"
STAGE = "Stage045"
MODEL_TAG = "stage045_external_pit_basis_warehouse_audit_v1"
STAGE_SLUG = "stage045_external_pit_basis_warehouse_audit"
OUTPUT_PREFIX = "rebuilt_c9_stage045_external_pit_basis_warehouse_audit"

MIN_EXTERNAL_HISTORY = 60
N_SPLITS = 4
EMBARGO_DAYS = 20

TOOLS_DIR = Path(__file__).resolve().parent
LINE_DIR = TOOLS_DIR.parent
REPO_ROOT = LINE_DIR.parents[2]
OUTPUT_DIR = LINE_DIR / "outputs" / STAGE_SLUG
STAGES_DIR = LINE_DIR / "stages"

BACKTEST_OUTPUTS = REPO_ROOT / "examples" / "portfolio_backtesting" / "backtest_outputs"
SUPPLY_DEMAND_DIR = BACKTEST_OUTPUTS / "external_supply_demand_cache"
BASIS_PATHS = sorted(SUPPLY_DEMAND_DIR.glob("supply_demand_basis_*.csv"))
WAREHOUSE_PATHS = sorted(SUPPLY_DEMAND_DIR.glob("supply_demand_warehouse_*.csv"))

STAGE038_OUTPUT_DIR = LINE_DIR / "outputs" / "stage038_candidate_pit_feature_matrix_audit"
STAGE038_PREFIX = "rebuilt_c9_stage038_candidate_pit_feature_matrix_audit"
STAGE038_TAG = "stage038_candidate_pit_feature_matrix_audit_v1"
STAGE038_FEATURE_MATRIX_PATH = STAGE038_OUTPUT_DIR / f"{STAGE038_PREFIX}_feature_matrix_{STAGE038_TAG}.csv"

FEATURE_MATRIX_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_feature_matrix_{MODEL_TAG}.csv"
CONDITION_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_condition_oos_summary_{MODEL_TAG}.csv"
FEATURE_COVERAGE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_feature_coverage_{MODEL_TAG}.csv"
PRODUCT_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_summary_{MODEL_TAG}.csv"
FOLD_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_fold_summary_{MODEL_TAG}.csv"
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
    shown = frame.head(max_rows).copy() if max_rows is not None else frame.copy()
    for column in shown.columns:
        if pd.api.types.is_float_dtype(shown[column]):
            shown[column] = shown[column].map(lambda value: f"{value:.4f}" if pd.notna(value) else "")
    return shown.to_markdown(index=False)


def _read_csvs(paths: list[Path]) -> pd.DataFrame:
    frames = []
    for path in paths:
        if path.exists():
            frame = pd.read_csv(path, encoding="utf-8-sig")
            if not frame.empty:
                frames.append(frame.dropna(axis=1, how="all"))
    return pd.concat(frames, ignore_index=True, sort=False) if frames else pd.DataFrame()


def _date_text(value: Any) -> str:
    if pd.isna(value):
        return ""
    if isinstance(value, (int, np.integer)):
        return f"{int(value):08d}"
    if isinstance(value, (float, np.floating)) and np.isfinite(value) and float(value).is_integer():
        return f"{int(value):08d}"
    text = str(value).strip()
    if text.endswith(".0") and text[:-2].isdigit():
        return f"{int(float(text)):08d}"
    return text


def _parse_dates(series: pd.Series) -> pd.Series:
    text = series.map(_date_text)
    compact = text.str.fullmatch(r"\d{8}")
    parsed = pd.to_datetime(series, errors="coerce")
    if compact.any():
        parsed.loc[compact] = pd.to_datetime(text.loc[compact], format="%Y%m%d", errors="coerce")
    return parsed.dt.normalize()


def _normalise_product_code(value: Any) -> str:
    text = str(value).strip()
    if "." in text:
        text = text.split(".", 1)[0]
    return "".join(ch for ch in text if ch.isalpha()).upper()


def _entry_product_code(frame: pd.DataFrame) -> pd.Series:
    for column in ("product", "product_vt_symbol", "vt_symbol"):
        if column in frame.columns:
            return frame[column].map(_normalise_product_code)
    return pd.Series("", index=frame.index, dtype=str)


def _expanding_percentile(series: pd.Series, *, min_history: int) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce")
    history: list[float] = []
    result: list[float] = []
    for value in values:
        if pd.isna(value):
            result.append(np.nan)
            continue
        current = float(value)
        history.append(current)
        if len(history) < min_history:
            result.append(np.nan)
            continue
        le_count = sum(1 for item in history if item <= current)
        result.append(float(le_count / len(history)))
    return pd.Series(result, index=series.index, dtype="float64")


def build_external_daily_features(
    basis: pd.DataFrame,
    warehouse: pd.DataFrame,
    *,
    min_history: int = MIN_EXTERNAL_HISTORY,
) -> pd.DataFrame:
    basis_features = pd.DataFrame()
    if not basis.empty:
        required = {"date", "symbol"}
        missing = required.difference(basis.columns)
        if missing:
            raise ValueError(f"basis missing columns: {sorted(missing)}")
        basis_features = basis.copy()
        basis_features["feature_date"] = _parse_dates(basis_features["date"])
        basis_features["product_code"] = basis_features["symbol"].map(_normalise_product_code)
        keep = ["feature_date", "product_code", "dom_basis_rate", "near_basis_rate", "dom_basis", "near_basis"]
        keep = [column for column in keep if column in basis_features.columns]
        basis_features = basis_features[keep].dropna(subset=["feature_date", "product_code"])
        basis_features = (
            basis_features.sort_values(["product_code", "feature_date"])
            .groupby(["feature_date", "product_code"], as_index=False)
            .last()
        )

    warehouse_features = pd.DataFrame()
    if not warehouse.empty:
        required = {"date", "product_code"}
        missing = required.difference(warehouse.columns)
        if missing:
            raise ValueError(f"warehouse missing columns: {sorted(missing)}")
        warehouse_features = warehouse.copy()
        warehouse_features["feature_date"] = _parse_dates(warehouse_features["date"])
        warehouse_features["product_code"] = warehouse_features["product_code"].map(_normalise_product_code)
        keep = [
            "feature_date",
            "product_code",
            "warehouse_receipt_quantity",
            "warehouse_receipt_change",
            "warehouse_source",
        ]
        keep = [column for column in keep if column in warehouse_features.columns]
        warehouse_features = warehouse_features[keep].dropna(subset=["feature_date", "product_code"])
        agg: dict[str, Any] = {
            "warehouse_receipt_quantity": "sum",
            "warehouse_receipt_change": "sum",
        }
        if "warehouse_source" in warehouse_features.columns:
            agg["warehouse_source"] = lambda values: "|".join(sorted(set(str(value) for value in values if pd.notna(value))))
        warehouse_features = (
            warehouse_features.sort_values(["product_code", "feature_date"])
            .groupby(["feature_date", "product_code"], as_index=False)
            .agg(agg)
        )

    if basis_features.empty and warehouse_features.empty:
        return pd.DataFrame()
    if basis_features.empty:
        features = warehouse_features.copy()
    elif warehouse_features.empty:
        features = basis_features.copy()
    else:
        features = basis_features.merge(warehouse_features, on=["feature_date", "product_code"], how="outer")

    features = features.sort_values(["product_code", "feature_date"]).reset_index(drop=True)
    numeric_columns = [
        "dom_basis_rate",
        "near_basis_rate",
        "dom_basis",
        "near_basis",
        "warehouse_receipt_quantity",
        "warehouse_receipt_change",
    ]
    for column in numeric_columns:
        if column in features.columns:
            features[column] = pd.to_numeric(features[column], errors="coerce")

    if "warehouse_receipt_change" in features.columns:
        features["warehouse_change_20d_sum"] = (
            features.groupby("product_code")["warehouse_receipt_change"]
            .transform(lambda values: values.rolling(20, min_periods=1).sum())
            .astype("float64")
        )
    else:
        features["warehouse_change_20d_sum"] = np.nan

    percentile_inputs = [
        ("dom_basis_rate", "dom_basis_rate_pctile"),
        ("near_basis_rate", "near_basis_rate_pctile"),
        ("warehouse_receipt_quantity", "warehouse_receipt_quantity_pctile"),
        ("warehouse_change_20d_sum", "warehouse_change_20d_sum_pctile"),
    ]
    for source_column, target_column in percentile_inputs:
        if source_column not in features.columns:
            features[target_column] = np.nan
            continue
        features[target_column] = features.groupby("product_code", group_keys=False)[source_column].apply(
            lambda values: _expanding_percentile(values, min_history=min_history)
        )

    features["asof_date"] = features["feature_date"] + pd.Timedelta(days=1)
    return features.sort_values(["product_code", "asof_date"]).reset_index(drop=True)


def attach_t1_external_features(entries: pd.DataFrame, features: pd.DataFrame) -> pd.DataFrame:
    result = entries.copy()
    result["entry_date"] = pd.to_datetime(result["entry_date"], errors="coerce").dt.normalize()
    result["external_product_code"] = _entry_product_code(result)
    attach_columns = [
        "feature_date",
        "asof_date",
        "dom_basis_rate",
        "near_basis_rate",
        "dom_basis_rate_pctile",
        "near_basis_rate_pctile",
        "warehouse_receipt_quantity",
        "warehouse_receipt_change",
        "warehouse_change_20d_sum",
        "warehouse_receipt_quantity_pctile",
        "warehouse_change_20d_sum_pctile",
    ]
    for column in attach_columns:
        result[f"external_{column}"] = pd.NaT if column.endswith("date") else np.nan

    if result.empty or features.empty:
        return result

    usable_columns = ["product_code", *attach_columns]
    usable = features[[column for column in usable_columns if column in features.columns]].copy()
    usable["asof_date"] = pd.to_datetime(usable["asof_date"], errors="coerce").dt.normalize()
    usable = usable.dropna(subset=["product_code", "asof_date"]).sort_values(["product_code", "asof_date"])

    for product_code, group_index in result.groupby("external_product_code").groups.items():
        product_features = usable[usable["product_code"].eq(product_code)].sort_values("asof_date")
        if product_features.empty:
            continue
        entry_group = result.loc[group_index].sort_values("entry_date").copy()
        attached = pd.merge_asof(
            entry_group[["entry_date"]].reset_index(),
            product_features,
            left_on="entry_date",
            right_on="asof_date",
            direction="backward",
        ).set_index("index")
        for column in attach_columns:
            if column in attached.columns:
                result.loc[attached.index, f"external_{column}"] = attached[column]
    return result


def _build_condition_specs(matrix: pd.DataFrame) -> list[ConditionSpec]:
    basis_available = matrix["external_dom_basis_rate"].notna()
    warehouse_available = matrix["external_warehouse_receipt_quantity"].notna()
    basis_low = matrix["external_dom_basis_rate_pctile"].le(0.20)
    basis_high = matrix["external_dom_basis_rate_pctile"].ge(0.80)
    warehouse_low = matrix["external_warehouse_receipt_quantity_pctile"].le(0.20)
    warehouse_high = matrix["external_warehouse_receipt_quantity_pctile"].ge(0.80)
    warehouse_draw = matrix["external_warehouse_change_20d_sum"].lt(0)
    warehouse_build = matrix["external_warehouse_change_20d_sum"].gt(0)

    matrix["external_basis_available"] = basis_available
    matrix["external_warehouse_available"] = warehouse_available
    matrix["external_basis_low_p20"] = basis_low
    matrix["external_basis_high_p80"] = basis_high
    matrix["external_warehouse_low_p20"] = warehouse_low
    matrix["external_warehouse_high_p80"] = warehouse_high
    matrix["external_warehouse_draw_20d"] = warehouse_draw
    matrix["external_warehouse_build_20d"] = warehouse_build
    matrix["external_tight_inventory_basis_high"] = warehouse_low & basis_high
    matrix["external_inventory_build_basis_low"] = warehouse_high & basis_low

    return [
        ConditionSpec("external_basis_available", "basis T+1 可用；只作覆盖基线", "external_basis", False, basis_available),
        ConditionSpec(
            "external_warehouse_available",
            "warehouse receipt T+1 可用；只作覆盖基线",
            "external_warehouse",
            False,
            warehouse_available,
        ),
        ConditionSpec("external_basis_low_p20", "主力基差率处于本品种历史低 20%", "external_basis", True, basis_low),
        ConditionSpec("external_basis_high_p80", "主力基差率处于本品种历史高 20%", "external_basis", True, basis_high),
        ConditionSpec("external_warehouse_low_p20", "仓单量处于本品种历史低 20%", "external_warehouse", True, warehouse_low),
        ConditionSpec("external_warehouse_high_p80", "仓单量处于本品种历史高 20%", "external_warehouse", True, warehouse_high),
        ConditionSpec("external_warehouse_draw_20d", "近 20 个观测日仓单净减少", "external_warehouse", True, warehouse_draw),
        ConditionSpec("external_warehouse_build_20d", "近 20 个观测日仓单净增加", "external_warehouse", True, warehouse_build),
        ConditionSpec(
            "external_tight_inventory_basis_high",
            "低仓单 + 高主力基差率",
            "external_combo",
            True,
            warehouse_low & basis_high,
        ),
        ConditionSpec(
            "external_inventory_build_basis_low",
            "高仓单 + 低主力基差率",
            "external_combo",
            True,
            warehouse_high & basis_low,
        ),
    ]


def _feature_coverage(matrix: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "external_feature_date",
        "external_dom_basis_rate",
        "external_dom_basis_rate_pctile",
        "external_warehouse_receipt_quantity",
        "external_warehouse_receipt_quantity_pctile",
        "external_warehouse_change_20d_sum",
        "external_tight_inventory_basis_high",
        "external_inventory_build_basis_low",
    ]
    rows = []
    for column in columns:
        if column not in matrix.columns:
            rows.append({"feature": column, "present": False, "non_null_count": 0, "active_count": 0, "coverage_pct": 0.0})
            continue
        values = matrix[column]
        non_null = int(values.notna().sum())
        active_count = int(values.fillna(False).sum()) if pd.api.types.is_bool_dtype(values) else non_null
        rows.append(
            {
                "feature": column,
                "present": True,
                "non_null_count": non_null,
                "active_count": active_count,
                "coverage_pct": float(non_null / len(matrix) * 100.0) if len(matrix) else 0.0,
            }
        )
    return pd.DataFrame(rows)


def _fold_summary(matrix: pd.DataFrame, splits: list[Any]) -> pd.DataFrame:
    rows = []
    for split in splits:
        test_mask = split.test_mask.reindex(matrix.index).fillna(False).astype(bool)
        test = matrix.loc[test_mask]
        pnl = pd.to_numeric(test.get("realized_pnl"), errors="coerce").fillna(0.0)
        rows.append(
            {
                "split_id": split.split_id,
                "test_start": split.test_start.date().isoformat(),
                "test_end": split.test_end.date().isoformat(),
                "test_count": int(len(test)),
                "test_pnl": float(pnl.sum()),
                "test_external_basis_coverage_pct": float(test["external_dom_basis_rate"].notna().mean() * 100.0)
                if len(test)
                else 0.0,
                "test_external_warehouse_coverage_pct": float(
                    test["external_warehouse_receipt_quantity"].notna().mean() * 100.0
                )
                if len(test)
                else 0.0,
            }
        )
    return pd.DataFrame(rows)


def _product_summary(matrix: pd.DataFrame) -> pd.DataFrame:
    if matrix.empty:
        return pd.DataFrame()
    grouped = matrix.groupby("product_vt_symbol", as_index=False).agg(
        count=("realized_pnl", "size"),
        total_pnl=("realized_pnl", "sum"),
        basis_coverage_pct=("external_dom_basis_rate", lambda values: float(values.notna().mean() * 100.0)),
        warehouse_coverage_pct=(
            "external_warehouse_receipt_quantity",
            lambda values: float(values.notna().mean() * 100.0),
        ),
        tight_inventory_basis_high_count=("external_tight_inventory_basis_high", "sum"),
        inventory_build_basis_low_count=("external_inventory_build_basis_low", "sum"),
    )
    return grouped.sort_values(["basis_coverage_pct", "warehouse_coverage_pct", "count"], ascending=[True, True, False])


def _decision(matrix: pd.DataFrame, condition_summary: pd.DataFrame, feature_coverage: pd.DataFrame) -> dict[str, Any]:
    stable = condition_summary[condition_summary["stable_oos_candidate"].astype(bool)].copy()
    basis_cov = feature_coverage.set_index("feature").loc["external_dom_basis_rate", "coverage_pct"]
    warehouse_cov = feature_coverage.set_index("feature").loc["external_warehouse_receipt_quantity", "coverage_pct"]
    if stable.empty:
        decision = "stage045_external_pit_no_stable_candidate_keep_readonly"
        next_stage = "stop_direct_external_selector_or_expand_pit_feature_family"
    else:
        decision = "stage045_external_pit_candidate_found_requires_proxy_engine"
        next_stage = "freeze_one_external_condition_proxy_no_parameter_sweep"
    return {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "decision": decision,
        "next_stage": next_stage,
        "entry_count": int(len(matrix)),
        "basis_coverage_pct": float(basis_cov),
        "warehouse_coverage_pct": float(warehouse_cov),
        "stable_conditions": stable["condition"].head(10).tolist(),
        "strategy_changed": False,
        "true_engine": False,
        "ctp_connected": False,
        "order_api_called": False,
    }


def _write_report(
    matrix: pd.DataFrame,
    condition_summary: pd.DataFrame,
    feature_coverage: pd.DataFrame,
    product_summary: pd.DataFrame,
    decision: dict[str, Any],
    stage_record_path: Path,
) -> None:
    report = f"""# Stage045 - basis/warehouse T+1 PIT 外生特征审计

- 记录时间：`{datetime.now().strftime('%Y-%m-%dT%H:%M')}`
- line_id：`{LINE_ID}`
- model_tag：`{MODEL_TAG}`
- 决策：`{decision['decision']}`

## 口径

- 只读复用 Stage038 候选级 opened flat-entry 样本，不写交易规则。
- `basis/warehouse` 每条数据只允许在 `data_date + 1` 之后使用；同日入场不得使用同日外生数据。
- 分位数为单品种 expanding percentile，默认至少 `{MIN_EXTERNAL_HISTORY}` 个历史观测后才输出。
- 不改官方 C9、不连接 CTP、不调用订单 API。

## 覆盖

{_md_table(feature_coverage)}

## 条件 OOS 摘要

{_md_table(condition_summary, max_rows=20)}

## 覆盖较弱产品

{_md_table(product_summary.head(20))}

## 判断

- 稳定 OOS 候选：`{decision['stable_conditions']}`。
- 若稳定候选为空，说明当前固定的 basis/warehouse 低自由度 PIT 条件还不足以直接进入 selector。
- 若存在稳定候选，下一步也只能冻结一个条件做 proxy/真引擎验证，不能扫分位阈值、品种、年份或方向。

## 输出

- feature_matrix：`{FEATURE_MATRIX_PATH}`
- condition_summary：`{CONDITION_SUMMARY_PATH}`
- feature_coverage：`{FEATURE_COVERAGE_PATH}`
- product_summary：`{PRODUCT_SUMMARY_PATH}`
- fold_summary：`{FOLD_SUMMARY_PATH}`
- decision：`{DECISION_PATH}`
- report：`{REPORT_PATH}`
- stage_record：`{stage_record_path}`

## 反思

- 运行前过拟合反思：否。本阶段先做 T+1/PIT 审计，不根据收益反推交易规则。
- 运行后过拟合反思：否。结果只说明当前固定条件是否有 OOS 信息量；后续扫 `20/80` 分位、产品、年份或方向才是过拟合。
- 运行前继续价值反思：有。Stage044 找到的外生源必须先点时化，否则不能进入 AI 选品。
- 运行后继续价值反思：取决于稳定候选是否存在；无稳定候选则停止直接 selector，转更宽日级网格或更有理论约束的外生特征。
"""
    REPORT_PATH.write_text(report, encoding="utf-8")
    stage_record_path.write_text(report, encoding="utf-8")


def run() -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    STAGES_DIR.mkdir(parents=True, exist_ok=True)

    basis = _read_csvs(BASIS_PATHS)
    warehouse = _read_csvs(WAREHOUSE_PATHS)
    external_features = build_external_daily_features(basis, warehouse, min_history=MIN_EXTERNAL_HISTORY)

    matrix = pd.read_csv(STAGE038_FEATURE_MATRIX_PATH, encoding="utf-8-sig")
    matrix = attach_t1_external_features(matrix, external_features)
    conditions = _build_condition_specs(matrix)
    splits = build_purged_time_splits(matrix, date_column="entry_date", n_splits=N_SPLITS, embargo_days=EMBARGO_DAYS)
    condition_summary = summarize_condition_oos(matrix, splits, conditions)
    feature_coverage = _feature_coverage(matrix)
    product_summary = _product_summary(matrix)
    fold_summary = _fold_summary(matrix, splits)
    decision = _decision(matrix, condition_summary, feature_coverage)

    matrix.to_csv(FEATURE_MATRIX_PATH, index=False, encoding="utf-8-sig")
    condition_summary.to_csv(CONDITION_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    feature_coverage.to_csv(FEATURE_COVERAGE_PATH, index=False, encoding="utf-8-sig")
    product_summary.to_csv(PRODUCT_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    fold_summary.to_csv(FOLD_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")

    stage_record_path = STAGES_DIR / f"{datetime.now().strftime('%Y%m%d_%H%M')}_stage045_external_pit_basis_warehouse_audit.md"
    _write_report(matrix, condition_summary, feature_coverage, product_summary, decision, stage_record_path)
    decision["stage_record_path"] = str(stage_record_path)
    return decision


if __name__ == "__main__":
    print(json.dumps(_json_safe(run()), ensure_ascii=False, indent=2))
