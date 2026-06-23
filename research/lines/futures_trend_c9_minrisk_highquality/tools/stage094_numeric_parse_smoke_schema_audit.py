from __future__ import annotations

from datetime import datetime
from io import BytesIO
import json
import re
from pathlib import Path
import sys
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


LINE_ID = "futures_trend_c9_minrisk_highquality"
STAGE = "Stage094"
MODEL_TAG = "stage094_numeric_parse_smoke_schema_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage094_c9_minrisk_numeric_parse_smoke_schema_audit"
NUMERIC_SCHEMA_VERSION = "external_numeric_parse_smoke_schema_v1"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
EXAMPLE_DIR = REPO_DIR / "examples" / "portfolio_backtesting"
if str(EXAMPLE_DIR) not in sys.path:
    sys.path.insert(0, str(EXAMPLE_DIR))

from qmt_roll_official_live_config import OFFICIAL_LIVE_ALIAS, OFFICIAL_LIVE_VERSION
from stage089_external_raw_backfill_manifest_probe import (
    _json_safe,
    _load_official_curve,
    _md_table,
    _official_metrics,
    _read_csv,
    _write_csv,
)


LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
STAGE093_DIR = LINE_DIR / "outputs" / "stage093_point_in_time_feature_schema_binding"
OUTPUT_DIR = LINE_DIR / "outputs" / "stage094_numeric_parse_smoke_schema_audit"

FEATURE_ROWS_IN = (
    STAGE093_DIR
    / "qmt_roll_stage093_c9_minrisk_point_in_time_feature_schema_binding_feature_rows_"
    "stage093_point_in_time_feature_schema_binding_v1.csv"
)

SMOKE_PLAN_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_smoke_plan_{MODEL_TAG}.csv"
PARSE_ROWS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_parse_rows_{MODEL_TAG}.csv"
SOURCE_YEAR_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_source_year_summary_{MODEL_TAG}.csv"
FIELD_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_field_summary_{MODEL_TAG}.csv"
SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

OFFICIAL_NUMERIC_PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_numeric_smoke_path_chart_{MODEL_TAG}.png"
READINESS_HEATMAP_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_readiness_heatmap_{MODEL_TAG}.png"
FIELD_AVAILABILITY_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_field_availability_chart_{MODEL_TAG}.png"
NUMERIC_DISTRIBUTION_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_numeric_distribution_chart_{MODEL_TAG}.png"

NUMERIC_COLUMNS = [
    "warehouse_receipt_qty_sum",
    "warehouse_change_qty_sum",
    "warehouse_valid_forecast_qty_sum",
    "warehouse_last_wbill_qty_sum",
    "warehouse_reg_wbill_qty_sum",
    "warehouse_logout_wbill_qty_sum",
    "warehouse_wbill_qty_sum",
    "warehouse_diff_qty_sum",
    "member_rank_volume_sum",
    "member_rank_volume_change_sum",
    "member_rank_long_oi_sum",
    "member_rank_long_oi_change_sum",
    "member_rank_short_oi_sum",
    "member_rank_short_oi_change_sum",
]


def _target_date(value: Any) -> str:
    text = str(value).strip()
    if text.endswith(".0"):
        text = text[:-2]
    return text.zfill(8)


def _source_family(source_id: str) -> str:
    if source_id.endswith("member_rank"):
        return "member_rank"
    if source_id.endswith("warehouse"):
        return "warehouse"
    return "unknown"


def _raw_path(value: Any) -> Path:
    path = Path(str(value))
    return path if path.is_absolute() else REPO_DIR / path


def _to_number(value: Any) -> float:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return np.nan
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "--", "-"}:
        return np.nan
    text = text.replace(",", "").replace("，", "").replace(" ", "")
    text = re.sub(r"[^0-9.\-]", "", text)
    if text in {"", "-", ".", "-."}:
        return np.nan
    try:
        return float(text)
    except ValueError:
        return np.nan


def _sum_numbers(values: pd.Series) -> float:
    numbers = values.map(_to_number)
    if numbers.dropna().empty:
        return np.nan
    return float(numbers.sum(skipna=True))


def _first_number(values: pd.Series) -> float:
    numbers = values.map(_to_number).dropna()
    return np.nan if numbers.empty else float(numbers.iloc[0])


def _normalized_first_text(value: Any) -> str:
    return re.sub(r"\s+", "", str(value).strip())


def _product_code_from_heading(text: Any) -> str:
    raw = str(text)
    if not raw.startswith("品种"):
        return ""
    after = raw.split("品种", 1)[1]
    after = after.lstrip("：:")
    before_meta = re.split(r"\s+单位|单位|日期", after)[0]
    matches = re.findall(r"[A-Za-z]{1,4}", before_meta)
    return matches[-1].upper() if matches else ""


def _excel_frame(content: bytes) -> pd.DataFrame:
    return pd.read_excel(BytesIO(content), dtype=object)


def _product_sections(frame: pd.DataFrame, product_root: str) -> list[tuple[int, int, str]]:
    if frame.empty:
        return []
    first_col = frame.iloc[:, 0].fillna("").astype(str)
    heads: list[tuple[int, str, str]] = []
    for idx, text in first_col.items():
        if text.startswith("品种"):
            heads.append((int(idx), _product_code_from_heading(text), text))
    sections: list[tuple[int, int, str]] = []
    for offset, (start, code, heading) in enumerate(heads):
        if code != str(product_root).upper():
            continue
        end = heads[offset + 1][0] if offset + 1 < len(heads) else len(frame)
        sections.append((start, end, heading))
    return sections


def _find_header_row(frame: pd.DataFrame, start: int, end: int, required_labels: list[str]) -> tuple[int | None, list[str]]:
    for row_idx in range(start + 1, end):
        values = [str(value).strip() for value in frame.iloc[row_idx].tolist()]
        if all(any(label in value for value in values) for label in required_labels):
            return row_idx, values
    return None, []


def _header_index(values: list[str], *patterns: str) -> int | None:
    for idx, value in enumerate(values):
        if any(pattern in value for pattern in patterns):
            return idx
    return None


def _next_change_index(values: list[str], start: int | None, stop: int | None = None) -> int | None:
    if start is None:
        return None
    end = stop if stop is not None else len(values)
    for idx in range(start + 1, min(end, len(values))):
        if "增减量" in values[idx]:
            return idx
    return None


def _extract_unit(heading: str) -> str:
    match = re.search(r"单位[:：]\s*([^\s]+)", heading)
    return match.group(1) if match else ""


def _base_result(row: pd.Series) -> dict[str, Any]:
    result = row.to_dict()
    result.update(
        {
            "stage": STAGE,
            "model_tag": MODEL_TAG,
            "numeric_schema_version": NUMERIC_SCHEMA_VERSION,
            "parser_family": _source_family(str(row["source_id"])),
            "field_schema_ready": 0,
            "numeric_feature_ready": 0,
            "quantity_feature_ready": 0,
            "warehouse_numeric_feature_ready": 0,
            "member_rank_numeric_feature_ready": 0,
            "field_parse_status": "not_started",
            "parse_error_type": "",
            "parse_error_message": "",
            "product_section_count": 0,
            "product_total_row_count": 0,
            "parsed_product_row_count": 0,
            "aggregation_source": "",
            "unit": "",
            "header_signature": "",
        }
    )
    for column in NUMERIC_COLUMNS:
        result[column] = np.nan
    return result


def _parse_gfex_warehouse(row: pd.Series, content: bytes) -> dict[str, Any]:
    result = _base_result(row)
    product_root = str(row["product_root"]).upper()
    data = json.loads(content.decode("utf-8", errors="ignore"))
    rows = data.get("data", []) if isinstance(data, dict) else []
    target_rows = [
        item
        for item in rows
        if isinstance(item, dict) and str(item.get("varietyOrder", "")).strip().upper() == product_root
    ]
    columns = sorted(rows[0].keys()) if rows and isinstance(rows[0], dict) else []
    required = ["lastWbillQty", "regWbillQty", "logoutWbillQty", "wbillQty", "diff"]
    result.update(
        {
            "field_schema_ready": int(all(field in columns for field in required)),
            "product_section_count": int(bool(target_rows)),
            "parsed_product_row_count": len(target_rows),
            "header_signature": "|".join(columns),
            "unit": "official_json_native_unit",
        }
    )
    if not target_rows:
        result["field_parse_status"] = "product_absent_or_not_listed"
        return result

    target = pd.DataFrame(target_rows)
    result.update(
        {
            "field_parse_status": "parsed_ok",
            "aggregation_source": "sum_variety_rows_excluding_exchange_total",
            "warehouse_last_wbill_qty_sum": _sum_numbers(target["lastWbillQty"]) if "lastWbillQty" in target else np.nan,
            "warehouse_reg_wbill_qty_sum": _sum_numbers(target["regWbillQty"]) if "regWbillQty" in target else np.nan,
            "warehouse_logout_wbill_qty_sum": _sum_numbers(target["logoutWbillQty"]) if "logoutWbillQty" in target else np.nan,
            "warehouse_wbill_qty_sum": _sum_numbers(target["wbillQty"]) if "wbillQty" in target else np.nan,
            "warehouse_diff_qty_sum": _sum_numbers(target["diff"]) if "diff" in target else np.nan,
        }
    )
    ready = int(
        bool(result["field_schema_ready"])
        and not pd.isna(result["warehouse_wbill_qty_sum"])
        and not pd.isna(result["warehouse_diff_qty_sum"])
    )
    result["numeric_feature_ready"] = ready
    result["quantity_feature_ready"] = ready
    result["warehouse_numeric_feature_ready"] = ready
    return result


def _parse_czce_warehouse(row: pd.Series, content: bytes) -> dict[str, Any]:
    result = _base_result(row)
    product_root = str(row["product_root"]).upper()
    frame = _excel_frame(content)
    sections = _product_sections(frame, product_root)
    valid_sections = 0
    total_rows: list[pd.DataFrame] = []
    headers: list[str] = []
    units: list[str] = []
    row_count = 0
    schema_ready = 0

    for start, end, heading in sections:
        header_idx, header_values = _find_header_row(frame, start, end, ["仓单数量", "当日增减"])
        if header_idx is None:
            continue
        receipt_idx = _header_index(header_values, "仓单数量")
        change_idx = _header_index(header_values, "当日增减")
        forecast_idx = _header_index(header_values, "有效预报")
        if receipt_idx is None or change_idx is None:
            continue
        valid_sections += 1
        schema_ready = 1
        units.append(_extract_unit(heading))
        headers.append("|".join(header_values))
        data = frame.iloc[header_idx + 1 : end].copy()
        row_count += int(data.dropna(how="all").shape[0])
        first_text = data.iloc[:, 0].map(_normalized_first_text)
        section_totals = data[first_text.eq("总计")].copy()
        aggregation_source = "official_product_total_row"
        if section_totals.empty:
            section_totals = data[first_text.eq("小计")].copy()
            aggregation_source = "official_product_subtotal_rows_no_total_row"
        if section_totals.empty:
            continue
        section_totals = section_totals.iloc[:, : len(header_values)].copy()
        section_totals["_receipt"] = section_totals.iloc[:, receipt_idx].map(_to_number)
        section_totals["_change"] = section_totals.iloc[:, change_idx].map(_to_number)
        section_totals["_forecast"] = (
            section_totals.iloc[:, forecast_idx].map(_to_number) if forecast_idx is not None else np.nan
        )
        section_totals["_aggregation_source"] = aggregation_source
        total_rows.append(section_totals)

    result.update(
        {
            "product_section_count": len(sections),
            "parsed_product_row_count": row_count,
            "product_total_row_count": sum(len(item) for item in total_rows),
            "field_schema_ready": schema_ready,
            "unit": "|".join(sorted(set(unit for unit in units if unit))),
            "header_signature": " / ".join(sorted(set(headers))),
        }
    )
    if not sections:
        result["field_parse_status"] = "product_absent_or_not_listed"
        return result
    if valid_sections == 0:
        result["field_parse_status"] = "warehouse_header_not_found"
        return result
    if not total_rows:
        result["field_parse_status"] = "warehouse_total_row_not_found"
        return result

    totals = pd.concat(total_rows, ignore_index=True)
    result.update(
        {
            "field_parse_status": "parsed_ok",
            "aggregation_source": "|".join(sorted(set(totals["_aggregation_source"].astype(str)))),
            "warehouse_receipt_qty_sum": float(totals["_receipt"].sum(skipna=True)),
            "warehouse_change_qty_sum": float(totals["_change"].sum(skipna=True)),
            "warehouse_valid_forecast_qty_sum": float(totals["_forecast"].sum(skipna=True)),
        }
    )
    ready = int(
        not pd.isna(result["warehouse_receipt_qty_sum"])
        and not pd.isna(result["warehouse_change_qty_sum"])
    )
    result["numeric_feature_ready"] = ready
    result["quantity_feature_ready"] = ready
    result["warehouse_numeric_feature_ready"] = ready
    return result


def _parse_czce_member_rank(row: pd.Series, content: bytes) -> dict[str, Any]:
    result = _base_result(row)
    product_root = str(row["product_root"]).upper()
    frame = _excel_frame(content)
    sections = _product_sections(frame, product_root)
    parsed_sections: list[pd.DataFrame] = []
    headers: list[str] = []
    row_count = 0
    total_count = 0
    schema_ready = 0

    for start, end, _heading in sections:
        header_idx, header_values = _find_header_row(frame, start, end, ["名次", "持买仓量", "持卖仓量"])
        if header_idx is None:
            continue
        volume_idx = _header_index(header_values, "成交量", "交易量")
        long_idx = _header_index(header_values, "持买仓量")
        short_idx = _header_index(header_values, "持卖仓量")
        volume_change_idx = _next_change_index(header_values, volume_idx, long_idx)
        long_change_idx = _next_change_index(header_values, long_idx, short_idx)
        short_change_idx = _next_change_index(header_values, short_idx)
        if volume_idx is None or long_idx is None or short_idx is None:
            continue
        schema_ready = 1
        headers.append("|".join(header_values))
        data = frame.iloc[header_idx + 1 : end].copy()
        first_text = data.iloc[:, 0].map(_normalized_first_text)
        rank_rows = data[first_text.str.fullmatch(r"\d+", na=False)]
        row_count += len(rank_rows)
        totals = data[first_text.eq("合计")].copy()
        total_count += len(totals)
        source = totals if not totals.empty else rank_rows
        if source.empty:
            continue
        source = source.iloc[:, : len(header_values)].copy()
        source["_volume"] = source.iloc[:, volume_idx].map(_to_number)
        source["_volume_change"] = source.iloc[:, volume_change_idx].map(_to_number) if volume_change_idx is not None else np.nan
        source["_long_oi"] = source.iloc[:, long_idx].map(_to_number)
        source["_long_oi_change"] = source.iloc[:, long_change_idx].map(_to_number) if long_change_idx is not None else np.nan
        source["_short_oi"] = source.iloc[:, short_idx].map(_to_number)
        source["_short_oi_change"] = source.iloc[:, short_change_idx].map(_to_number) if short_change_idx is not None else np.nan
        source["_aggregation_source"] = "official_product_total_row" if not totals.empty else "rank_rows_sum_no_total"
        parsed_sections.append(source)

    result.update(
        {
            "product_section_count": len(sections),
            "parsed_product_row_count": row_count,
            "product_total_row_count": total_count,
            "field_schema_ready": schema_ready,
            "unit": "手",
            "header_signature": " / ".join(sorted(set(headers))),
        }
    )
    if not sections:
        result["field_parse_status"] = "product_absent_or_not_listed"
        return result
    if schema_ready == 0:
        result["field_parse_status"] = "member_rank_header_not_found"
        return result
    if not parsed_sections:
        result["field_parse_status"] = "member_rank_total_or_rank_rows_not_found"
        return result

    parsed = pd.concat(parsed_sections, ignore_index=True)
    result.update(
        {
            "field_parse_status": "parsed_ok",
            "aggregation_source": "|".join(sorted(set(parsed["_aggregation_source"].astype(str)))),
            "member_rank_volume_sum": float(parsed["_volume"].sum(skipna=True)),
            "member_rank_volume_change_sum": float(parsed["_volume_change"].sum(skipna=True)),
            "member_rank_long_oi_sum": float(parsed["_long_oi"].sum(skipna=True)),
            "member_rank_long_oi_change_sum": float(parsed["_long_oi_change"].sum(skipna=True)),
            "member_rank_short_oi_sum": float(parsed["_short_oi"].sum(skipna=True)),
            "member_rank_short_oi_change_sum": float(parsed["_short_oi_change"].sum(skipna=True)),
        }
    )
    ready = int(
        not pd.isna(result["member_rank_volume_sum"])
        and not pd.isna(result["member_rank_long_oi_sum"])
        and not pd.isna(result["member_rank_short_oi_sum"])
    )
    result["numeric_feature_ready"] = ready
    result["quantity_feature_ready"] = ready
    result["member_rank_numeric_feature_ready"] = ready
    return result


def _load_feature_rows() -> pd.DataFrame:
    rows = _read_csv(FEATURE_ROWS_IN)
    rows["target_date"] = rows["target_date"].map(_target_date)
    rows["target_year"] = pd.to_numeric(rows["target_year"], errors="coerce").fillna(0).astype(int)
    rows["entry_date"] = pd.to_datetime(rows["entry_date"], errors="coerce").dt.normalize()
    rows["source_family"] = rows["source_id"].map(_source_family)
    rows["raw_parse_ready"] = pd.to_numeric(rows.get("raw_parse_ready", 0), errors="coerce").fillna(0).astype(int)
    rows["state_feature_ready"] = pd.to_numeric(rows.get("state_feature_ready", 0), errors="coerce").fillna(0).astype(int)
    rows["symbol_hit"] = pd.to_numeric(rows.get("symbol_hit", 0), errors="coerce").fillna(0).astype(int)
    rows["realized_pnl"] = pd.to_numeric(rows.get("realized_pnl", 0.0), errors="coerce").fillna(0.0)
    return rows


def _smoke_plan(feature_rows: pd.DataFrame) -> pd.DataFrame:
    candidates = feature_rows[
        feature_rows["raw_parse_ready"].eq(1)
        & feature_rows["state_feature_ready"].eq(1)
        & feature_rows["raw_file"].fillna("").astype(str).ne("")
    ].copy()
    candidates = candidates.sort_values(["source_id", "product_root", "target_year", "target_date", "lot_id"])
    present = candidates[candidates["product_present_state"].eq("present")].copy()
    group_cols = ["source_id", "exchange", "product_root", "target_year"]
    first_rows = present.groupby(group_cols, as_index=False, group_keys=False).head(1).copy()
    first_rows["sample_role"] = "first_present_in_source_product_year"
    last_rows = present.groupby(group_cols, as_index=False, group_keys=False).tail(1).copy()
    last_rows["sample_role"] = "last_present_in_source_product_year"
    absent = candidates[~candidates["product_present_state"].eq("present")].copy()
    absent["sample_role"] = "all_official_absent_state_rows"
    plan = pd.concat([first_rows, last_rows, absent], ignore_index=True)
    plan = plan.sort_values(["source_id", "product_root", "target_year", "target_date", "sample_role"])
    plan = plan.drop_duplicates(["source_id", "product_root", "target_date"], keep="first").reset_index(drop=True)
    plan["smoke_sample_id"] = np.arange(1, len(plan) + 1)
    keep = [
        "smoke_sample_id",
        "sample_role",
        "numeric_schema_version",
        "feature_schema_version",
        "source_id",
        "source_family",
        "exchange",
        "product_root",
        "target_year",
        "target_date",
        "product_present_state",
        "symbol_hit",
        "state_feature_ready",
        "raw_parse_ready",
        "row_count",
        "schema_hash",
        "sha256",
        "raw_file",
        "lot_id",
        "vt_symbol",
        "direction",
        "entry_date",
        "realized_pnl",
        "right_tail_top10",
    ]
    plan["numeric_schema_version"] = NUMERIC_SCHEMA_VERSION
    return plan[[col for col in keep if col in plan.columns]]


def _parse_plan(plan: pd.DataFrame) -> pd.DataFrame:
    parsed: list[dict[str, Any]] = []
    for _, row in plan.iterrows():
        try:
            raw_file = _raw_path(row["raw_file"])
            content = raw_file.read_bytes()
            source_id = str(row["source_id"])
            if source_id == "gfex_warehouse":
                result = _parse_gfex_warehouse(row, content)
            elif source_id == "czce_warehouse":
                result = _parse_czce_warehouse(row, content)
            elif source_id == "czce_member_rank":
                result = _parse_czce_member_rank(row, content)
            else:
                result = _base_result(row)
                result["field_parse_status"] = "unsupported_source"
            parsed.append(result)
        except Exception as exc:  # noqa: BLE001 - stage audit must preserve failing row context.
            result = _base_result(row)
            result.update(
                {
                    "field_parse_status": "parse_exception",
                    "parse_error_type": type(exc).__name__,
                    "parse_error_message": str(exc)[:500],
                }
            )
            parsed.append(result)
    frame = pd.DataFrame(parsed)
    for column in [
        "field_schema_ready",
        "numeric_feature_ready",
        "quantity_feature_ready",
        "warehouse_numeric_feature_ready",
        "member_rank_numeric_feature_ready",
        "product_section_count",
        "product_total_row_count",
        "parsed_product_row_count",
    ]:
        frame[column] = pd.to_numeric(frame.get(column, 0), errors="coerce").fillna(0)
    return frame.sort_values(["source_id", "product_root", "target_year", "target_date", "sample_role"]).reset_index(drop=True)


def _source_year_summary(parse_rows: pd.DataFrame) -> pd.DataFrame:
    frame = parse_rows.copy()
    frame["present_row"] = frame["product_present_state"].eq("present").astype(int)
    frame["absent_state_row"] = frame["present_row"].eq(0).astype(int)
    frame["parse_error_row"] = frame["field_parse_status"].isin(
        [
            "parse_exception",
            "warehouse_header_not_found",
            "warehouse_total_row_not_found",
            "member_rank_header_not_found",
            "member_rank_total_or_rank_rows_not_found",
        ]
    ).astype(int)
    grouped = (
        frame.groupby(["source_id", "source_family", "target_year"], as_index=False)
        .agg(
            smoke_row_count=("smoke_sample_id", "count"),
            product_count=("product_root", "nunique"),
            present_row_count=("present_row", "sum"),
            absent_state_row_count=("absent_state_row", "sum"),
            field_schema_ready_count=("field_schema_ready", "sum"),
            numeric_ready_count=("numeric_feature_ready", "sum"),
            warehouse_numeric_ready_count=("warehouse_numeric_feature_ready", "sum"),
            member_rank_numeric_ready_count=("member_rank_numeric_feature_ready", "sum"),
            parse_error_count=("parse_error_row", "sum"),
            status_set=("field_parse_status", lambda values: "|".join(sorted(set(map(str, values))))),
        )
        .sort_values(["source_id", "target_year"])
    )
    grouped["numeric_ready_ratio_present_only"] = grouped["numeric_ready_count"] / grouped["present_row_count"].replace(0, np.nan)
    grouped["numeric_ready_ratio_present_only"] = grouped["numeric_ready_ratio_present_only"].fillna(0.0)
    return grouped


def _field_summary(parse_rows: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for column in NUMERIC_COLUMNS:
        values = pd.to_numeric(parse_rows[column], errors="coerce")
        non_null = values.dropna()
        if column.startswith("warehouse_"):
            family = "warehouse"
        elif column.startswith("member_rank_"):
            family = "member_rank"
        else:
            family = "unknown"
        rows.append(
            {
                "field": column,
                "source_family": family,
                "rows_with_value": int(non_null.shape[0]),
                "rows_with_nonzero_abs_value": int(non_null[non_null.abs() > 0].shape[0]),
                "min_value": float(non_null.min()) if not non_null.empty else np.nan,
                "median_value": float(non_null.median()) if not non_null.empty else np.nan,
                "max_value": float(non_null.max()) if not non_null.empty else np.nan,
                "point_in_time_safe": 1,
                "trading_rule_allowed": 0,
            }
        )
    return pd.DataFrame(rows)


def _summary(curve: pd.DataFrame, parse_rows: pd.DataFrame, source_year: pd.DataFrame) -> pd.DataFrame:
    metrics = _official_metrics(curve)
    present = parse_rows[parse_rows["product_present_state"].eq("present")]
    absent = parse_rows[~parse_rows["product_present_state"].eq("present")]
    parse_error_count = int(
        parse_rows["field_parse_status"].isin(
            [
                "parse_exception",
                "warehouse_header_not_found",
                "warehouse_total_row_not_found",
                "member_rank_header_not_found",
                "member_rank_total_or_rank_rows_not_found",
            ]
        ).sum()
    )
    present_numeric_ready = int(present["numeric_feature_ready"].sum())
    present_count = int(len(present))
    absent_handled = int(
        absent.empty
        or absent["field_parse_status"].isin(["product_absent_or_not_listed", "parsed_ok"]).all()
    )
    schema_safe = int(
        present_count > 0
        and present_numeric_ready == present_count
        and parse_error_count == 0
        and absent_handled == 1
    )
    decision = (
        "stage094_numeric_parse_smoke_ready_no_rule"
        if schema_safe
        else "stage094_numeric_parse_smoke_has_schema_gaps_no_rule"
    )
    return pd.DataFrame(
        [
            {
                "stage": STAGE,
                "model_tag": MODEL_TAG,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "line_id": LINE_ID,
                "decision": decision,
                "official_live_alias": OFFICIAL_LIVE_ALIAS,
                "official_live_version": OFFICIAL_LIVE_VERSION,
                "official_config_changed": 0,
                "strategy_rule_created": 0,
                "true_engine_run": 0,
                "ab_triggered": 0,
                "order_api_called": 0,
                "ctp_connected": 0,
                "numeric_schema_version": NUMERIC_SCHEMA_VERSION,
                "smoke_row_count": int(len(parse_rows)),
                "source_count": int(parse_rows["source_id"].nunique()),
                "product_count": int(parse_rows["product_root"].nunique()),
                "source_year_count": int(len(source_year)),
                "present_smoke_row_count": present_count,
                "absent_state_smoke_row_count": int(len(absent)),
                "field_schema_ready_count": int(parse_rows["field_schema_ready"].sum()),
                "numeric_ready_count": int(parse_rows["numeric_feature_ready"].sum()),
                "present_numeric_ready_count": present_numeric_ready,
                "warehouse_numeric_ready_count": int(parse_rows["warehouse_numeric_feature_ready"].sum()),
                "member_rank_numeric_ready_count": int(parse_rows["member_rank_numeric_feature_ready"].sum()),
                "parse_error_count": parse_error_count,
                "absent_state_handled": absent_handled,
                "field_binding_read_only": 1,
                "strategy_feature_usable": 0,
                **metrics,
            }
        ]
    )


def _plot_official_numeric_path(curve: pd.DataFrame, parse_rows: pd.DataFrame, summary: pd.Series) -> None:
    fig, axes = plt.subplots(4, 1, figsize=(14, 10), gridspec_kw={"height_ratios": [2.0, 1.0, 1.0, 1.2]})
    axes[0].plot(curve["date"], curve["account_equity"], color="#0f766e", linewidth=1.5)
    axes[0].set_ylabel("equity")
    axes[0].grid(True, alpha=0.25)
    axes[1].plot(curve["date"], curve["drawdown_pct"], color="#dc2626", linewidth=1.2)
    axes[1].set_ylabel("drawdown %")
    axes[1].grid(True, alpha=0.25)
    axes[2].plot(curve["date"], curve["broker10_margin_to_equity_pct"], color="#7c3aed", linewidth=1.2)
    axes[2].axhline(100, color="#111827", linestyle="--", linewidth=0.8)
    axes[2].set_ylabel("broker10 %")
    axes[2].grid(True, alpha=0.25)
    frame = parse_rows[parse_rows["product_present_state"].eq("present")].copy()
    if not frame.empty:
        yearly = frame.groupby(["target_year", "source_family"], as_index=False).agg(
            smoke_rows=("smoke_sample_id", "count"),
            numeric_ready=("numeric_feature_ready", "sum"),
        )
        years = sorted(yearly["target_year"].unique())
        families = ["member_rank", "warehouse"]
        x = np.arange(len(years))
        width = 0.35
        for idx, family in enumerate(families):
            vals = []
            for year in years:
                subset = yearly[(yearly["target_year"].eq(year)) & (yearly["source_family"].eq(family))]
                vals.append(float(subset["numeric_ready"].sum()) if not subset.empty else 0.0)
            axes[3].bar(x + (idx - 0.5) * width, vals, width=width, label=family)
        axes[3].set_xticks(x)
        axes[3].set_xticklabels([str(year) for year in years])
        axes[3].legend(loc="upper left", fontsize=8)
    axes[3].set_ylabel("numeric ready smoke rows")
    axes[3].grid(True, axis="y", alpha=0.25)
    axes[0].set_title(
        f"{STAGE} numeric parse smoke/schema audit | decision={summary['decision']} | "
        f"present ready {int(summary['present_numeric_ready_count'])}/{int(summary['present_smoke_row_count'])}"
    )
    fig.tight_layout()
    fig.savefig(OFFICIAL_NUMERIC_PATH_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_readiness_heatmap(parse_rows: pd.DataFrame) -> None:
    present = parse_rows[parse_rows["product_present_state"].eq("present")].copy()
    pivot = present.pivot_table(
        index="source_id",
        columns="target_year",
        values="numeric_feature_ready",
        aggfunc="mean",
    ).fillna(-1.0)
    fig, ax = plt.subplots(figsize=(11, 4.5))
    im = ax.imshow(pivot.to_numpy(dtype=float), aspect="auto", cmap="YlGnBu", vmin=0, vmax=1)
    ax.set_xticks(np.arange(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns.astype(str).tolist())
    ax.set_yticks(np.arange(len(pivot.index)))
    ax.set_yticklabels(pivot.index.tolist())
    for i in range(pivot.shape[0]):
        for j in range(pivot.shape[1]):
            value = pivot.iloc[i, j]
            label = "-" if value < 0 else f"{value:.0%}"
            ax.text(j, i, label, ha="center", va="center", fontsize=9)
    ax.set_title("Stage094 present-row numeric ready ratio by source-year")
    fig.colorbar(im, ax=ax, fraction=0.025, pad=0.02)
    fig.tight_layout()
    fig.savefig(READINESS_HEATMAP_OUT, dpi=160)
    plt.close(fig)


def _plot_field_availability(field_summary: pd.DataFrame) -> None:
    display = field_summary[field_summary["rows_with_value"].gt(0)].copy()
    if display.empty:
        return
    display = display.sort_values(["source_family", "rows_with_value", "field"])
    fig, ax = plt.subplots(figsize=(12, 5.5))
    colors = np.where(display["source_family"].eq("warehouse"), "#2563eb", "#059669")
    ax.barh(display["field"], display["rows_with_value"], color=colors, alpha=0.8)
    ax.set_xlabel("smoke rows with parsed numeric value")
    ax.set_title("Stage094 fixed numeric field availability; rule_allowed=0 for every field")
    ax.grid(True, axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(FIELD_AVAILABILITY_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_numeric_distribution(parse_rows: pd.DataFrame) -> None:
    fields = [
        "warehouse_receipt_qty_sum",
        "warehouse_wbill_qty_sum",
        "warehouse_change_qty_sum",
        "warehouse_diff_qty_sum",
        "member_rank_volume_sum",
        "member_rank_long_oi_sum",
        "member_rank_short_oi_sum",
    ]
    plot_rows: list[pd.DataFrame] = []
    for field in fields:
        values = pd.to_numeric(parse_rows[field], errors="coerce").dropna()
        if values.empty:
            continue
        plot_rows.append(pd.DataFrame({"field": field, "log1p_abs_value": np.log1p(values.abs())}))
    if not plot_rows:
        return
    data = pd.concat(plot_rows, ignore_index=True)
    labels = list(dict.fromkeys(data["field"].tolist()))
    series = [data[data["field"].eq(label)]["log1p_abs_value"].to_numpy() for label in labels]
    fig, ax = plt.subplots(figsize=(12, 5.5))
    ax.boxplot(series, tick_labels=labels, vert=False, showfliers=True)
    ax.set_xlabel("log1p(abs(value))")
    ax.set_title("Stage094 numeric magnitude distribution for schema audit only")
    ax.grid(True, axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(NUMERIC_DISTRIBUTION_CHART_OUT, dpi=160)
    plt.close(fig)


def _write_report(
    summary: pd.DataFrame,
    source_year: pd.DataFrame,
    field_summary: pd.DataFrame,
    parse_rows: pd.DataFrame,
) -> None:
    row = summary.iloc[0]
    failures = parse_rows[parse_rows["field_parse_status"].ne("parsed_ok")].copy()
    report = "\n".join(
        [
            f"# {STAGE} numeric parse smoke/schema audit",
            "",
            "## Decision",
            "",
            f"- decision: `{row['decision']}`",
            "- nature: fixed source/product/year smoke parse audit; no thresholds, no TopN, no rolling, no flow weights, no true engine, no A/B, no CTP, no order API.",
            "",
            "## Baseline path",
            "",
            f"- end equity: `{row['end_equity']:,.2f}`",
            f"- total return: `{row['total_return_pct']:.4f}%`",
            f"- max drawdown: `{row['max_dd_pct']:.4f}%`",
            f"- Sharpe: `{row['sharpe']:.4f}`",
            f"- total slippage: `{row['total_slippage']:,.0f}`",
            f"- total trade count: `{row['total_trade_count']:.0f}`",
            f"- win rate: `{row['win_rate_pct']:.4f}%`",
            f"- broker10 peak: `{row['broker10_peak_margin_to_equity_pct']:.4f}%`",
            "",
            "## Smoke summary",
            "",
            f"- smoke rows: `{int(row['smoke_row_count'])}`",
            f"- sources / products / source-years: `{int(row['source_count'])}` / `{int(row['product_count'])}` / `{int(row['source_year_count'])}`",
            f"- present rows / absent-state rows: `{int(row['present_smoke_row_count'])}` / `{int(row['absent_state_smoke_row_count'])}`",
            f"- field schema ready: `{int(row['field_schema_ready_count'])}`",
            f"- numeric ready: `{int(row['numeric_ready_count'])}`",
            f"- present numeric ready: `{int(row['present_numeric_ready_count'])}` / `{int(row['present_smoke_row_count'])}`",
            f"- warehouse numeric ready: `{int(row['warehouse_numeric_ready_count'])}`",
            f"- member-rank numeric ready: `{int(row['member_rank_numeric_ready_count'])}`",
            f"- parse errors: `{int(row['parse_error_count'])}`",
            f"- absent-state handled: `{int(row['absent_state_handled'])}`",
            f"- strategy feature usable: `{int(row['strategy_feature_usable'])}`",
            "",
            "## Source-year summary",
            "",
            _md_table(source_year, max_rows=80),
            "",
            "## Fixed field summary",
            "",
            _md_table(field_summary, max_rows=40),
            "",
            "## Non-parsed or absent rows",
            "",
            _md_table(
                failures[
                    [
                        "source_id",
                        "product_root",
                        "target_year",
                        "target_date",
                        "product_present_state",
                        "field_parse_status",
                        "parse_error_type",
                    ]
                ],
                max_rows=80,
            ),
            "",
            "## Visual outputs",
            "",
            f"- official numeric smoke path chart: `{OFFICIAL_NUMERIC_PATH_CHART_OUT}`",
            f"- readiness heatmap: `{READINESS_HEATMAP_OUT}`",
            f"- field availability chart: `{FIELD_AVAILABILITY_CHART_OUT}`",
            f"- numeric distribution chart: `{NUMERIC_DISTRIBUTION_CHART_OUT}`",
            "",
            "## Judgment",
            "",
            "- The parsed numbers are data-engineering fields only; every fixed field has `trading_rule_allowed=0`.",
            "- The smoke plan is selected by source/product/year coverage, not by profit, drawdown, right-tail, product rescue, or year rescue.",
            "- Next step, if any, must still stay read-only: expand from smoke parse to full feature-row numeric extraction and audit field stability before any feature interpretation.",
        ]
    )
    REPORT_OUT.write_text(report + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    curve = _load_official_curve()
    feature_rows = _load_feature_rows()
    plan = _smoke_plan(feature_rows)
    parse_rows = _parse_plan(plan)
    source_year = _source_year_summary(parse_rows)
    field_summary = _field_summary(parse_rows)
    summary = _summary(curve, parse_rows, source_year)

    _write_csv(plan, SMOKE_PLAN_OUT)
    _write_csv(parse_rows, PARSE_ROWS_OUT)
    _write_csv(source_year, SOURCE_YEAR_SUMMARY_OUT)
    _write_csv(field_summary, FIELD_SUMMARY_OUT)
    _write_csv(summary, SUMMARY_OUT)
    DECISION_OUT.write_text(
        json.dumps(_json_safe(summary.iloc[0].to_dict()), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    _plot_official_numeric_path(curve, parse_rows, summary.iloc[0])
    _plot_readiness_heatmap(parse_rows)
    _plot_field_availability(field_summary)
    _plot_numeric_distribution(parse_rows)
    _write_report(summary, source_year, field_summary, parse_rows)


if __name__ == "__main__":
    main()
