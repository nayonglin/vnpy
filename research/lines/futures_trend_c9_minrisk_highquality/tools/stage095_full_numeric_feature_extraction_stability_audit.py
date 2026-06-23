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
STAGE = "Stage095"
MODEL_TAG = "stage095_full_numeric_feature_extraction_stability_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage095_c9_minrisk_full_numeric_feature_extraction_stability_audit"
NUMERIC_SCHEMA_VERSION = "external_numeric_full_feature_schema_v1"
PARSER_SCHEMA_VERSION = "external_numeric_parse_smoke_schema_v1"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
TOOLS_DIR = SCRIPT_PATH.parent
EXAMPLE_DIR = REPO_DIR / "examples" / "portfolio_backtesting"
for path in [str(EXAMPLE_DIR), str(TOOLS_DIR)]:
    if path not in sys.path:
        sys.path.insert(0, path)

from qmt_roll_official_live_config import OFFICIAL_LIVE_ALIAS, OFFICIAL_LIVE_VERSION
from stage089_external_raw_backfill_manifest_probe import (
    _json_safe,
    _load_official_curve,
    _md_table,
    _official_metrics,
    _read_csv,
    _write_csv,
)
from stage094_numeric_parse_smoke_schema_audit import (
    NUMERIC_COLUMNS,
    _excel_frame,
    _extract_unit,
    _find_header_row,
    _header_index,
    _next_change_index,
    _normalized_first_text,
    _product_code_from_heading,
    _sum_numbers,
    _to_number,
)


LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
STAGE093_DIR = LINE_DIR / "outputs" / "stage093_point_in_time_feature_schema_binding"
OUTPUT_DIR = LINE_DIR / "outputs" / "stage095_full_numeric_feature_extraction_stability_audit"

FEATURE_ROWS_IN = (
    STAGE093_DIR
    / "qmt_roll_stage093_c9_minrisk_point_in_time_feature_schema_binding_feature_rows_"
    "stage093_point_in_time_feature_schema_binding_v1.csv"
)

PARSE_GROUPS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_parse_groups_{MODEL_TAG}.csv"
FEATURE_ROWS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_feature_rows_{MODEL_TAG}.csv"
LOT_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_lot_summary_{MODEL_TAG}.csv"
SOURCE_YEAR_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_source_year_summary_{MODEL_TAG}.csv"
PRODUCT_YEAR_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_year_summary_{MODEL_TAG}.csv"
FIELD_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_field_summary_{MODEL_TAG}.csv"
AGGREGATION_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_aggregation_source_summary_{MODEL_TAG}.csv"
SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

OFFICIAL_NUMERIC_PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_numeric_full_path_chart_{MODEL_TAG}.png"
READINESS_HEATMAP_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_readiness_heatmap_{MODEL_TAG}.png"
PRODUCT_YEAR_HEATMAP_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_year_heatmap_{MODEL_TAG}.png"
AGGREGATION_SOURCE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_aggregation_source_chart_{MODEL_TAG}.png"
RIGHT_TAIL_COVERAGE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_right_tail_coverage_chart_{MODEL_TAG}.png"
NUMERIC_DISTRIBUTION_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_numeric_distribution_chart_{MODEL_TAG}.png"

KEY_COLUMNS = ["source_id", "exchange", "product_root", "target_date", "raw_file"]
PARSE_META_COLUMNS = [
    "stage",
    "model_tag",
    "numeric_schema_version",
    "parser_schema_version",
    "source_id",
    "exchange",
    "product_root",
    "target_date",
    "target_year",
    "raw_file",
    "product_present_state",
    "parser_family",
    "field_schema_ready",
    "numeric_feature_ready",
    "quantity_feature_ready",
    "warehouse_numeric_feature_ready",
    "member_rank_numeric_feature_ready",
    "field_parse_status",
    "parse_error_type",
    "parse_error_message",
    "product_section_count",
    "product_total_row_count",
    "parsed_product_row_count",
    "aggregation_source",
    "unit",
    "header_signature",
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


def _base_parse_result(row: pd.Series) -> dict[str, Any]:
    result = {column: row.get(column, "") for column in row.index}
    result.update(
        {
            "stage": STAGE,
            "model_tag": MODEL_TAG,
            "numeric_schema_version": NUMERIC_SCHEMA_VERSION,
            "parser_schema_version": PARSER_SCHEMA_VERSION,
            "parser_family": _source_family(str(row.get("source_id", ""))),
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


def _product_sections(frame: pd.DataFrame) -> list[tuple[int, int, str, str]]:
    if frame.empty:
        return []
    first_col = frame.iloc[:, 0].fillna("").astype(str)
    heads: list[tuple[int, str, str]] = []
    for idx, text in first_col.items():
        if text.startswith("品种"):
            heads.append((int(idx), _product_code_from_heading(text), text))
    sections: list[tuple[int, int, str, str]] = []
    for offset, (start, code, heading) in enumerate(heads):
        end = heads[offset + 1][0] if offset + 1 < len(heads) else len(frame)
        if code:
            sections.append((start, end, code, heading))
    return sections


def _parse_czce_warehouse_file(content: bytes, rows: pd.DataFrame) -> dict[str, dict[str, Any]]:
    frame = _excel_frame(content)
    sections = _product_sections(frame)
    target_products = sorted(set(rows["product_root"].astype(str).str.upper()))
    results = {product: _base_parse_result(rows[rows["product_root"].astype(str).str.upper().eq(product)].iloc[0]) for product in target_products}

    for product, result in results.items():
        product_sections = [section for section in sections if section[2] == product]
        valid_sections = 0
        total_rows: list[pd.DataFrame] = []
        headers: list[str] = []
        units: list[str] = []
        row_count = 0
        schema_ready = 0

        for start, end, _code, heading in product_sections:
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
                "product_section_count": len(product_sections),
                "parsed_product_row_count": row_count,
                "product_total_row_count": sum(len(item) for item in total_rows),
                "field_schema_ready": schema_ready,
                "unit": "|".join(sorted(set(unit for unit in units if unit))),
                "header_signature": " / ".join(sorted(set(headers))),
            }
        )
        if not product_sections:
            result["field_parse_status"] = "product_absent_or_not_listed"
            continue
        if valid_sections == 0:
            result["field_parse_status"] = "warehouse_header_not_found"
            continue
        if not total_rows:
            result["field_parse_status"] = "warehouse_total_row_not_found"
            continue
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
    return results


def _parse_czce_member_rank_file(content: bytes, rows: pd.DataFrame) -> dict[str, dict[str, Any]]:
    frame = _excel_frame(content)
    sections = _product_sections(frame)
    target_products = sorted(set(rows["product_root"].astype(str).str.upper()))
    results = {product: _base_parse_result(rows[rows["product_root"].astype(str).str.upper().eq(product)].iloc[0]) for product in target_products}

    for product, result in results.items():
        product_sections = [section for section in sections if section[2] == product]
        parsed_sections: list[pd.DataFrame] = []
        headers: list[str] = []
        row_count = 0
        total_count = 0
        schema_ready = 0

        for start, end, _code, _heading in product_sections:
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
                "product_section_count": len(product_sections),
                "parsed_product_row_count": row_count,
                "product_total_row_count": total_count,
                "field_schema_ready": schema_ready,
                "unit": "手",
                "header_signature": " / ".join(sorted(set(headers))),
            }
        )
        if not product_sections:
            result["field_parse_status"] = "product_absent_or_not_listed"
            continue
        if schema_ready == 0:
            result["field_parse_status"] = "member_rank_header_not_found"
            continue
        if not parsed_sections:
            result["field_parse_status"] = "member_rank_total_or_rank_rows_not_found"
            continue
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
    return results


def _parse_gfex_warehouse_file(content: bytes, rows: pd.DataFrame) -> dict[str, dict[str, Any]]:
    data = json.loads(content.decode("utf-8", errors="ignore"))
    raw_rows = data.get("data", []) if isinstance(data, dict) else []
    target_products = sorted(set(rows["product_root"].astype(str).str.upper()))
    results = {product: _base_parse_result(rows[rows["product_root"].astype(str).str.upper().eq(product)].iloc[0]) for product in target_products}
    columns = sorted(raw_rows[0].keys()) if raw_rows and isinstance(raw_rows[0], dict) else []
    required = ["lastWbillQty", "regWbillQty", "logoutWbillQty", "wbillQty", "diff"]

    for product, result in results.items():
        target_rows = [
            item
            for item in raw_rows
            if isinstance(item, dict) and str(item.get("varietyOrder", "")).strip().upper() == product
        ]
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
            continue
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
    return results


def _load_feature_rows() -> pd.DataFrame:
    rows = _read_csv(FEATURE_ROWS_IN)
    rows["feature_row_id"] = np.arange(1, len(rows) + 1)
    rows["target_date"] = rows["target_date"].map(_target_date)
    rows["target_year"] = pd.to_numeric(rows["target_year"], errors="coerce").fillna(0).astype(int)
    rows["entry_date"] = pd.to_datetime(rows["entry_date"], errors="coerce").dt.normalize()
    rows["source_family"] = rows["source_id"].map(_source_family)
    for column in ["raw_parse_ready", "state_feature_ready", "symbol_hit", "right_tail_top10"]:
        rows[column] = pd.to_numeric(rows.get(column, 0), errors="coerce").fillna(0).astype(int)
    rows["realized_pnl"] = pd.to_numeric(rows.get("realized_pnl", 0.0), errors="coerce").fillna(0.0)
    rows["realized_pnl_rank_pct"] = pd.to_numeric(rows.get("realized_pnl_rank_pct", 0.0), errors="coerce").fillna(0.0)
    return rows


def _parse_groups(feature_rows: pd.DataFrame) -> pd.DataFrame:
    parse_input = feature_rows[
        feature_rows["raw_parse_ready"].eq(1)
        & feature_rows["state_feature_ready"].eq(1)
        & feature_rows["raw_file"].fillna("").astype(str).ne("")
    ].copy()
    parse_input = parse_input.sort_values(["source_id", "raw_file", "product_root", "target_date", "feature_row_id"])
    unique_rows = parse_input.drop_duplicates(KEY_COLUMNS).reset_index(drop=True)
    unique_rows["parse_group_id"] = np.arange(1, len(unique_rows) + 1)
    parsed: list[dict[str, Any]] = []

    for raw_file, raw_group in unique_rows.groupby("raw_file", sort=False):
        try:
            content = _raw_path(raw_file).read_bytes()
            source_id = str(raw_group["source_id"].iloc[0])
            if source_id == "czce_warehouse":
                result_map = _parse_czce_warehouse_file(content, raw_group)
            elif source_id == "czce_member_rank":
                result_map = _parse_czce_member_rank_file(content, raw_group)
            elif source_id == "gfex_warehouse":
                result_map = _parse_gfex_warehouse_file(content, raw_group)
            else:
                result_map = {}
            for _, row in raw_group.iterrows():
                product = str(row["product_root"]).upper()
                result = result_map.get(product, _base_parse_result(row))
                result["parse_group_id"] = int(row["parse_group_id"])
                parsed.append(result)
        except Exception as exc:  # noqa: BLE001 - stage audit must preserve failing group context.
            for _, row in raw_group.iterrows():
                result = _base_parse_result(row)
                result.update(
                    {
                        "parse_group_id": int(row["parse_group_id"]),
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
        frame[column] = pd.to_numeric(frame.get(column, 0), errors="coerce").fillna(0).astype(int)
    for column in NUMERIC_COLUMNS:
        frame[column] = pd.to_numeric(frame.get(column, np.nan), errors="coerce")
    keep = [col for col in PARSE_META_COLUMNS + ["parse_group_id"] + NUMERIC_COLUMNS if col in frame.columns]
    return frame[keep].sort_values(["source_id", "target_date", "product_root"]).reset_index(drop=True)


def _build_feature_numeric_rows(feature_rows: pd.DataFrame, parse_groups: pd.DataFrame) -> pd.DataFrame:
    parse_cols = KEY_COLUMNS + [
        "parse_group_id",
        "parser_family",
        "field_schema_ready",
        "numeric_feature_ready",
        "quantity_feature_ready",
        "warehouse_numeric_feature_ready",
        "member_rank_numeric_feature_ready",
        "field_parse_status",
        "parse_error_type",
        "parse_error_message",
        "product_section_count",
        "product_total_row_count",
        "parsed_product_row_count",
        "aggregation_source",
        "unit",
        "header_signature",
    ] + NUMERIC_COLUMNS
    parse_cols = [col for col in parse_cols if col in parse_groups.columns]
    rows = feature_rows.merge(parse_groups[parse_cols], on=KEY_COLUMNS, how="left", suffixes=("", "_parsed"))
    for column in [
        "quantity_feature_ready",
        "warehouse_numeric_feature_ready",
        "member_rank_numeric_feature_ready",
    ]:
        parsed_column = f"{column}_parsed"
        if parsed_column in rows.columns:
            rows[column] = rows[parsed_column]
    rows["numeric_schema_version"] = NUMERIC_SCHEMA_VERSION
    rows["parser_schema_version"] = PARSER_SCHEMA_VERSION
    rows["field_parse_status"] = rows["field_parse_status"].fillna("not_parsed")
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
        if column not in rows.columns:
            rows[column] = 0
        rows[column] = pd.to_numeric(rows[column], errors="coerce").fillna(0).astype(int)
    rows["present_numeric_expected"] = rows["product_present_state"].eq("present").astype(int)
    rows["present_numeric_ready"] = (
        rows["present_numeric_expected"].eq(1) & rows["numeric_feature_ready"].eq(1)
    ).astype(int)
    rows["absent_state_handled"] = (
        rows["present_numeric_expected"].eq(0)
        & rows["field_parse_status"].isin(["product_absent_or_not_listed", "parsed_ok"])
    ).astype(int)
    rows["strategy_rule_allowed"] = 0
    rows["true_engine_allowed"] = 0
    return rows.sort_values(["entry_date", "lot_id", "source_id", "target_date"]).reset_index(drop=True)


def _lot_summary(rows: pd.DataFrame) -> pd.DataFrame:
    grouped = (
        rows.groupby(["lot_id", "vt_symbol", "product_root", "direction", "entry_date"], as_index=False)
        .agg(
            source_count=("source_id", "nunique"),
            feature_row_count=("feature_row_id", "count"),
            present_feature_row_count=("present_numeric_expected", "sum"),
            numeric_ready_count=("numeric_feature_ready", "sum"),
            present_numeric_ready_count=("present_numeric_ready", "sum"),
            absent_state_row_count=("present_numeric_expected", lambda values: int((values == 0).sum())),
            parse_error_count=("field_parse_status", lambda values: int(pd.Series(values).isin(["parse_exception", "warehouse_header_not_found", "warehouse_total_row_not_found", "member_rank_header_not_found", "member_rank_total_or_rank_rows_not_found"]).sum())),
            first_target_date=("target_date", "min"),
            last_target_date=("target_date", "max"),
            realized_pnl=("realized_pnl", "first"),
            r_multiple=("r_multiple", "first"),
            realized_pnl_rank_pct=("realized_pnl_rank_pct", "first"),
            right_tail_top10=("right_tail_top10", "first"),
        )
        .sort_values(["entry_date", "lot_id"])
    )
    grouped["all_present_numeric_ready"] = grouped["present_numeric_ready_count"].eq(grouped["present_feature_row_count"]).astype(int)
    grouped["present_numeric_ready_ratio"] = grouped["present_numeric_ready_count"] / grouped["present_feature_row_count"].replace(0, np.nan)
    grouped["present_numeric_ready_ratio"] = grouped["present_numeric_ready_ratio"].fillna(1.0)
    return grouped


def _source_year_summary(rows: pd.DataFrame) -> pd.DataFrame:
    grouped = (
        rows.groupby(["source_id", "source_family", "target_year"], as_index=False)
        .agg(
            feature_row_count=("feature_row_id", "count"),
            product_count=("product_root", "nunique"),
            linked_lot_count=("lot_id", "nunique"),
            present_feature_row_count=("present_numeric_expected", "sum"),
            absent_state_row_count=("present_numeric_expected", lambda values: int((values == 0).sum())),
            numeric_ready_count=("numeric_feature_ready", "sum"),
            present_numeric_ready_count=("present_numeric_ready", "sum"),
            field_schema_ready_count=("field_schema_ready", "sum"),
            parse_error_count=("field_parse_status", lambda values: int(pd.Series(values).isin(["parse_exception", "warehouse_header_not_found", "warehouse_total_row_not_found", "member_rank_header_not_found", "member_rank_total_or_rank_rows_not_found"]).sum())),
            aggregation_source_set=("aggregation_source", lambda values: "|".join(sorted(set(str(value) for value in values if str(value) and str(value) != "nan")))),
        )
        .sort_values(["source_id", "target_year"])
    )
    grouped["present_numeric_ready_ratio"] = grouped["present_numeric_ready_count"] / grouped["present_feature_row_count"].replace(0, np.nan)
    grouped["present_numeric_ready_ratio"] = grouped["present_numeric_ready_ratio"].fillna(1.0)
    return grouped


def _product_year_summary(rows: pd.DataFrame) -> pd.DataFrame:
    grouped = (
        rows.groupby(["source_id", "source_family", "product_root", "target_year"], as_index=False)
        .agg(
            feature_row_count=("feature_row_id", "count"),
            linked_lot_count=("lot_id", "nunique"),
            target_date_count=("target_date", "nunique"),
            present_feature_row_count=("present_numeric_expected", "sum"),
            absent_state_row_count=("present_numeric_expected", lambda values: int((values == 0).sum())),
            numeric_ready_count=("numeric_feature_ready", "sum"),
            present_numeric_ready_count=("present_numeric_ready", "sum"),
            parse_group_count=("parse_group_id", "nunique"),
            aggregation_source_set=("aggregation_source", lambda values: "|".join(sorted(set(str(value) for value in values if str(value) and str(value) != "nan")))),
        )
        .sort_values(["source_id", "product_root", "target_year"])
    )
    grouped["present_numeric_ready_ratio"] = grouped["present_numeric_ready_count"] / grouped["present_feature_row_count"].replace(0, np.nan)
    grouped["present_numeric_ready_ratio"] = grouped["present_numeric_ready_ratio"].fillna(1.0)
    return grouped


def _field_summary(rows: pd.DataFrame) -> pd.DataFrame:
    output: list[dict[str, Any]] = []
    for column in NUMERIC_COLUMNS:
        values = pd.to_numeric(rows[column], errors="coerce")
        non_null = values.dropna()
        if column.startswith("warehouse_"):
            family = "warehouse"
        elif column.startswith("member_rank_"):
            family = "member_rank"
        else:
            family = "unknown"
        output.append(
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
    return pd.DataFrame(output)


def _aggregation_summary(rows: pd.DataFrame) -> pd.DataFrame:
    frame = rows.copy()
    frame["aggregation_source"] = frame["aggregation_source"].fillna("").replace("", "no_numeric_absent_or_unparsed")
    return (
        frame.groupby(["source_id", "source_family", "aggregation_source"], as_index=False)
        .agg(
            feature_row_count=("feature_row_id", "count"),
            product_count=("product_root", "nunique"),
            target_date_count=("target_date", "nunique"),
            linked_lot_count=("lot_id", "nunique"),
            present_feature_row_count=("present_numeric_expected", "sum"),
            numeric_ready_count=("numeric_feature_ready", "sum"),
        )
        .sort_values(["source_id", "aggregation_source"])
    )


def _summary(curve: pd.DataFrame, rows: pd.DataFrame, parse_groups: pd.DataFrame, lot_summary: pd.DataFrame) -> pd.DataFrame:
    metrics = _official_metrics(curve)
    present = rows[rows["product_present_state"].eq("present")]
    absent = rows[~rows["product_present_state"].eq("present")]
    parse_error_statuses = [
        "parse_exception",
        "warehouse_header_not_found",
        "warehouse_total_row_not_found",
        "member_rank_header_not_found",
        "member_rank_total_or_rank_rows_not_found",
    ]
    parse_error_group_count = int(parse_groups["field_parse_status"].isin(parse_error_statuses).sum())
    present_numeric_ready = int(present["numeric_feature_ready"].sum())
    present_count = int(len(present))
    absent_handled = int(absent.empty or absent["field_parse_status"].isin(["product_absent_or_not_listed", "parsed_ok"]).all())
    right_tail_lot_count = int(lot_summary["right_tail_top10"].sum()) if not lot_summary.empty else 0
    right_tail_ready = int(lot_summary[lot_summary["right_tail_top10"].eq(1)]["all_present_numeric_ready"].sum()) if not lot_summary.empty else 0
    schema_safe = int(
        present_count > 0
        and present_numeric_ready == present_count
        and parse_error_group_count == 0
        and absent_handled == 1
        and int(rows["strategy_rule_allowed"].sum()) == 0
        and int(rows["true_engine_allowed"].sum()) == 0
    )
    decision = (
        "stage095_full_numeric_features_ready_no_rule"
        if schema_safe
        else "stage095_full_numeric_features_have_gaps_no_rule"
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
                "parser_schema_version": PARSER_SCHEMA_VERSION,
                "feature_row_count": int(len(rows)),
                "parse_group_count": int(len(parse_groups)),
                "source_count": int(rows["source_id"].nunique()),
                "product_count": int(rows["product_root"].nunique()),
                "linked_lot_count": int(rows["lot_id"].nunique()),
                "present_feature_row_count": present_count,
                "absent_state_feature_row_count": int(len(absent)),
                "numeric_ready_feature_row_count": int(rows["numeric_feature_ready"].sum()),
                "present_numeric_ready_feature_row_count": present_numeric_ready,
                "warehouse_numeric_ready_feature_row_count": int(rows["warehouse_numeric_feature_ready"].sum()),
                "member_rank_numeric_ready_feature_row_count": int(rows["member_rank_numeric_feature_ready"].sum()),
                "parse_error_group_count": parse_error_group_count,
                "absent_state_handled": absent_handled,
                "lot_all_present_numeric_ready_count": int(lot_summary["all_present_numeric_ready"].sum()) if not lot_summary.empty else 0,
                "right_tail_lot_count": right_tail_lot_count,
                "right_tail_all_present_numeric_ready_count": right_tail_ready,
                "field_binding_read_only": 1,
                "strategy_feature_usable": 0,
                **metrics,
            }
        ]
    )


def _plot_official_numeric_path(curve: pd.DataFrame, rows: pd.DataFrame, summary: pd.Series) -> None:
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
    present = rows[rows["product_present_state"].eq("present")]
    yearly = present.groupby(["target_year", "source_family"], as_index=False).agg(
        numeric_ready=("numeric_feature_ready", "sum")
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
    axes[3].set_ylabel("numeric ready feature rows")
    axes[3].grid(True, axis="y", alpha=0.25)
    axes[3].legend(loc="upper left", fontsize=8)
    axes[0].set_title(
        f"{STAGE} full numeric feature extraction | decision={summary['decision']} | "
        f"present ready {int(summary['present_numeric_ready_feature_row_count'])}/"
        f"{int(summary['present_feature_row_count'])}"
    )
    fig.tight_layout()
    fig.savefig(OFFICIAL_NUMERIC_PATH_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_readiness_heatmap(rows: pd.DataFrame) -> None:
    present = rows[rows["product_present_state"].eq("present")]
    pivot = present.pivot_table(index="source_id", columns="target_year", values="numeric_feature_ready", aggfunc="mean").fillna(-1.0)
    fig, ax = plt.subplots(figsize=(11, 4.5))
    im = ax.imshow(pivot.to_numpy(dtype=float), aspect="auto", cmap="YlGnBu", vmin=0, vmax=1)
    ax.set_xticks(np.arange(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns.astype(str).tolist())
    ax.set_yticks(np.arange(len(pivot.index)))
    ax.set_yticklabels(pivot.index.tolist())
    for i in range(pivot.shape[0]):
        for j in range(pivot.shape[1]):
            value = pivot.iloc[i, j]
            ax.text(j, i, "-" if value < 0 else f"{value:.0%}", ha="center", va="center", fontsize=9)
    ax.set_title("Stage095 present-row numeric ready ratio by source-year")
    fig.colorbar(im, ax=ax, fraction=0.025, pad=0.02)
    fig.tight_layout()
    fig.savefig(READINESS_HEATMAP_OUT, dpi=160)
    plt.close(fig)


def _plot_product_year_heatmap(product_year: pd.DataFrame) -> None:
    frame = product_year[product_year["present_feature_row_count"].gt(0)].copy()
    frame["label"] = frame["source_id"] + ":" + frame["product_root"]
    pivot = frame.pivot_table(index="label", columns="target_year", values="present_numeric_ready_ratio", aggfunc="mean").fillna(-1.0)
    fig, ax = plt.subplots(figsize=(12, max(5, len(pivot) * 0.32)))
    im = ax.imshow(pivot.to_numpy(dtype=float), aspect="auto", cmap="YlGnBu", vmin=0, vmax=1)
    ax.set_xticks(np.arange(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns.astype(str).tolist())
    ax.set_yticks(np.arange(len(pivot.index)))
    ax.set_yticklabels(pivot.index.tolist(), fontsize=8)
    for i in range(pivot.shape[0]):
        for j in range(pivot.shape[1]):
            value = pivot.iloc[i, j]
            ax.text(j, i, "-" if value < 0 else f"{value:.0%}", ha="center", va="center", fontsize=7)
    ax.set_title("Stage095 product-year numeric ready ratio for present rows")
    fig.colorbar(im, ax=ax, fraction=0.025, pad=0.02)
    fig.tight_layout()
    fig.savefig(PRODUCT_YEAR_HEATMAP_OUT, dpi=160)
    plt.close(fig)


def _plot_aggregation_source(aggregation_summary: pd.DataFrame) -> None:
    display = aggregation_summary.copy()
    display["label"] = display["source_id"] + "\n" + display["aggregation_source"]
    fig, ax = plt.subplots(figsize=(13, 5.5))
    x = np.arange(len(display))
    ax.bar(x, display["feature_row_count"], color="#2563eb", alpha=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels(display["label"].tolist(), rotation=45, ha="right", fontsize=8)
    ax.set_ylabel("feature rows")
    ax.set_title("Stage095 aggregation source counts; all are schema audit fields, not trading rules")
    ax.grid(True, axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(AGGREGATION_SOURCE_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_right_tail_coverage(lot_summary: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 1, figsize=(12, 6))
    axes[0].hist(lot_summary["present_numeric_ready_ratio"], bins=np.linspace(0, 1, 11), color="#059669", alpha=0.75)
    axes[0].set_title("Lot-level present numeric ready ratio")
    axes[0].set_xlabel("ratio")
    axes[0].set_ylabel("lot count")
    axes[0].grid(True, axis="y", alpha=0.25)
    axes[1].scatter(
        lot_summary["realized_pnl_rank_pct"],
        lot_summary["present_numeric_ready_ratio"],
        c=np.where(lot_summary["right_tail_top10"].eq(1), "#f97316", "#2563eb"),
        alpha=0.7,
        s=28,
    )
    axes[1].axvline(0.9, color="#dc2626", linestyle="--", linewidth=0.9)
    axes[1].set_xlabel("realized pnl rank pct (coverage audit only)")
    axes[1].set_ylabel("numeric ready ratio")
    axes[1].set_title("Right-tail coverage audit, not a PnL bucket rule")
    axes[1].grid(True, alpha=0.25)
    fig.tight_layout()
    fig.savefig(RIGHT_TAIL_COVERAGE_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_numeric_distribution(rows: pd.DataFrame) -> None:
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
        values = pd.to_numeric(rows[field], errors="coerce").dropna()
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
    ax.set_title("Stage095 full numeric magnitude distribution for schema stability audit only")
    ax.grid(True, axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(NUMERIC_DISTRIBUTION_CHART_OUT, dpi=160)
    plt.close(fig)


def _write_report(
    summary: pd.DataFrame,
    source_year: pd.DataFrame,
    product_year: pd.DataFrame,
    field_summary: pd.DataFrame,
    aggregation_summary: pd.DataFrame,
    lot_summary: pd.DataFrame,
) -> None:
    row = summary.iloc[0]
    product_gaps = product_year[product_year["present_numeric_ready_ratio"].lt(1.0)].copy()
    right_tail = lot_summary[lot_summary["right_tail_top10"].eq(1)].copy()
    report = "\n".join(
        [
            f"# {STAGE} full numeric feature extraction stability audit",
            "",
            "## Decision",
            "",
            f"- decision: `{row['decision']}`",
            "- nature: full point-in-time numeric extraction and schema stability audit; no thresholds, no TopN, no rolling, no flow weights, no true engine, no A/B, no CTP, no order API.",
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
            "## Full extraction summary",
            "",
            f"- feature rows: `{int(row['feature_row_count'])}`",
            f"- parse groups: `{int(row['parse_group_count'])}`",
            f"- sources / products / linked lots: `{int(row['source_count'])}` / `{int(row['product_count'])}` / `{int(row['linked_lot_count'])}`",
            f"- present rows / absent-state rows: `{int(row['present_feature_row_count'])}` / `{int(row['absent_state_feature_row_count'])}`",
            f"- numeric ready rows: `{int(row['numeric_ready_feature_row_count'])}`",
            f"- present numeric ready: `{int(row['present_numeric_ready_feature_row_count'])}` / `{int(row['present_feature_row_count'])}`",
            f"- warehouse numeric ready rows: `{int(row['warehouse_numeric_ready_feature_row_count'])}`",
            f"- member-rank numeric ready rows: `{int(row['member_rank_numeric_ready_feature_row_count'])}`",
            f"- parse error groups: `{int(row['parse_error_group_count'])}`",
            f"- absent-state handled: `{int(row['absent_state_handled'])}`",
            f"- lot all-present-numeric-ready: `{int(row['lot_all_present_numeric_ready_count'])}` / `{int(row['linked_lot_count'])}`",
            f"- right-tail all-present-numeric-ready: `{int(row['right_tail_all_present_numeric_ready_count'])}` / `{int(row['right_tail_lot_count'])}`",
            f"- strategy feature usable: `{int(row['strategy_feature_usable'])}`",
            "",
            "## Source-year summary",
            "",
            _md_table(source_year, max_rows=80),
            "",
            "## Product-year gaps",
            "",
            _md_table(product_gaps, max_rows=80),
            "",
            "## Aggregation sources",
            "",
            _md_table(aggregation_summary, max_rows=80),
            "",
            "## Fixed field summary",
            "",
            _md_table(field_summary, max_rows=40),
            "",
            "## Right-tail coverage sample",
            "",
            _md_table(right_tail.head(30), max_rows=30),
            "",
            "## Visual outputs",
            "",
            f"- official numeric full path chart: `{OFFICIAL_NUMERIC_PATH_CHART_OUT}`",
            f"- readiness heatmap: `{READINESS_HEATMAP_OUT}`",
            f"- product-year heatmap: `{PRODUCT_YEAR_HEATMAP_OUT}`",
            f"- aggregation source chart: `{AGGREGATION_SOURCE_CHART_OUT}`",
            f"- right-tail coverage chart: `{RIGHT_TAIL_COVERAGE_CHART_OUT}`",
            f"- numeric distribution chart: `{NUMERIC_DISTRIBUTION_CHART_OUT}`",
            "",
            "## Judgment",
            "",
            "- Full numeric extraction is a data asset, not a strategy feature.",
            "- Every numeric field remains `trading_rule_allowed=0`; aggregation source and absent-state fields are schema audit fields only.",
            "- Next step must stay read-only unless a separate predeclared economic hypothesis is formed after stability review.",
        ]
    )
    REPORT_OUT.write_text(report + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    curve = _load_official_curve()
    feature_rows = _load_feature_rows()
    parse_groups = _parse_groups(feature_rows)
    rows = _build_feature_numeric_rows(feature_rows, parse_groups)
    lot_summary = _lot_summary(rows)
    source_year = _source_year_summary(rows)
    product_year = _product_year_summary(rows)
    field_summary = _field_summary(rows)
    aggregation_summary = _aggregation_summary(rows)
    summary = _summary(curve, rows, parse_groups, lot_summary)

    _write_csv(parse_groups, PARSE_GROUPS_OUT)
    _write_csv(rows, FEATURE_ROWS_OUT)
    _write_csv(lot_summary, LOT_SUMMARY_OUT)
    _write_csv(source_year, SOURCE_YEAR_SUMMARY_OUT)
    _write_csv(product_year, PRODUCT_YEAR_SUMMARY_OUT)
    _write_csv(field_summary, FIELD_SUMMARY_OUT)
    _write_csv(aggregation_summary, AGGREGATION_SUMMARY_OUT)
    _write_csv(summary, SUMMARY_OUT)
    DECISION_OUT.write_text(
        json.dumps(_json_safe(summary.iloc[0].to_dict()), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    _plot_official_numeric_path(curve, rows, summary.iloc[0])
    _plot_readiness_heatmap(rows)
    _plot_product_year_heatmap(product_year)
    _plot_aggregation_source(aggregation_summary)
    _plot_right_tail_coverage(lot_summary)
    _plot_numeric_distribution(rows)
    _write_report(summary, source_year, product_year, field_summary, aggregation_summary, lot_summary)


if __name__ == "__main__":
    main()
