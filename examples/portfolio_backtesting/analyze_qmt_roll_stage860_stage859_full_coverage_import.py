from __future__ import annotations

from datetime import datetime
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

LINE_ID = "futures_trend_stage819_intraday_rules"
STAGE = "Stage860"
MODEL_TAG = "stage860_stage859_full_coverage_import_v1"
OUTPUT_PREFIX = "qmt_roll_stage860_stage859_full_coverage_import"

STAGE825_PREFIX = "qmt_roll_stage825_stage819_intraday_rule_forensics"
STAGE825_TAG = "stage825_stage819_intraday_rule_forensics_v1"
STAGE849_PREFIX = "qmt_roll_stage849_stage848_pressure_path_forensics"
STAGE849_TAG = "stage849_stage848_pressure_path_forensics_v1"
STAGE853_PREFIX = "qmt_roll_stage853_stage852_minute_gap_audit"
STAGE853_TAG = "stage853_stage852_minute_gap_audit_v1"
STAGE855_PREFIX = "qmt_roll_stage855_stage854_local_raw_import"
STAGE855_TAG = "stage855_stage854_local_raw_import_v1"
STAGE859_PREFIX = "qmt_roll_stage859_stage856_tqsdk_backtest_gap_backfill"
STAGE859_TAG = "stage859_stage856_tqsdk_backtest_gap_backfill_v1"

STAGE825_INTRADAY_PATH = OUTPUT_DIR / f"{STAGE825_PREFIX}_intraday_features_{STAGE825_TAG}.csv"
STAGE849_MINUTE_PATH = OUTPUT_DIR / f"{STAGE849_PREFIX}_minute_features_{STAGE849_TAG}.csv"
STAGE853_DETAIL_PATH = OUTPUT_DIR / f"{STAGE853_PREFIX}_gap_detail_{STAGE853_TAG}.csv"
STAGE855_PATCH_BARS_PATH = OUTPUT_DIR / f"{STAGE855_PREFIX}_patch_minute_bars_{STAGE855_TAG}.csv"
STAGE855_REQUEST_COVERAGE_PATH = OUTPUT_DIR / f"{STAGE855_PREFIX}_request_coverage_after_patch_{STAGE855_TAG}.csv"
STAGE859_MINUTE_BARS_PATH = OUTPUT_DIR / f"{STAGE859_PREFIX}_minute_bars_{STAGE859_TAG}.csv"
STAGE859_STATUS_PATH = OUTPUT_DIR / f"{STAGE859_PREFIX}_tqsdk_extract_status_{STAGE859_TAG}.csv"
STAGE859_COVERAGE_PATH = OUTPUT_DIR / f"{STAGE859_PREFIX}_request_coverage_after_stage859_{STAGE859_TAG}.csv"

COMBINED_PATCH_BARS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_combined_patch_minute_bars_{MODEL_TAG}.csv"
REQUEST_COVERAGE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_request_coverage_after_stage860_{MODEL_TAG}.csv"
STAGE825_COVERAGE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_stage825_coverage_after_stage860_{MODEL_TAG}.csv"
STAGE825_YEAR_COVERAGE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_stage825_year_coverage_after_stage860_{MODEL_TAG}.csv"
STAGE849_COVERAGE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_stage849_pressure_coverage_after_stage860_{MODEL_TAG}.csv"
SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
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
        result = float(value)
        return None if math.isnan(result) or math.isinf(result) else result
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    return value


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "无数据。"
    view = frame.copy()
    if max_rows is not None:
        view = view.head(max_rows)
    for column in view.columns:
        if pd.api.types.is_float_dtype(view[column]):
            view[column] = view[column].map(lambda item: f"{item:.4f}" if pd.notna(item) else "")
    return view.to_markdown(index=False)


def _load_csv(path: Path, *, required: bool = True) -> pd.DataFrame:
    if not path.exists():
        if required:
            raise RuntimeError(f"Missing required input: {path}")
        return pd.DataFrame()
    return pd.read_csv(path, encoding="utf-8-sig")


def _normal_date_text(value: Any) -> str:
    ts = pd.to_datetime(value, errors="coerce")
    if pd.isna(ts):
        return ""
    return str(pd.Timestamp(ts).date())


def _numeric(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    for column in columns:
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame


def _source_id_to_lot_id(source_id: Any) -> int | None:
    text = str(source_id)
    if not text.startswith("lot_"):
        return None
    try:
        return int(text.split("_", 1)[1])
    except ValueError:
        return None


def _request_key(row: Any) -> tuple[str, str, str, str]:
    return (
        str(getattr(row, "request_type")),
        str(getattr(row, "source_id")),
        str(getattr(row, "vt_symbol")),
        _normal_date_text(getattr(row, "required_date")),
    )


def _symbol_date_key(vt_symbol: Any, date_value: Any) -> tuple[str, str]:
    return str(vt_symbol), _normal_date_text(date_value)


def _prepare_bar_frame(frame: pd.DataFrame, source_name: str) -> pd.DataFrame:
    if frame.empty:
        return frame
    data = frame.copy()
    data["bar_datetime"] = pd.to_datetime(data["bar_datetime"], errors="coerce")
    data = data.dropna(subset=["vt_symbol", "bar_datetime"])
    data["bar_date"] = data["bar_datetime"].dt.strftime("%Y-%m-%d")
    data["minute_source"] = source_name
    for column in ["open", "high", "low", "close", "volume", "open_oi", "close_oi"]:
        if column in data.columns:
            data[column] = pd.to_numeric(data[column], errors="coerce")
    return data


def _combined_patch_bars() -> pd.DataFrame:
    stage855 = _prepare_bar_frame(_load_csv(STAGE855_PATCH_BARS_PATH), "stage855_local_raw_patch")
    stage859 = _prepare_bar_frame(_load_csv(STAGE859_MINUTE_BARS_PATH), "stage859_tqsdk_backtest")
    columns = [
        "vt_symbol",
        "tq_symbol",
        "bar_datetime",
        "bar_id",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "open_oi",
        "close_oi",
        "bar_date",
        "minute_source",
        "required_date",
    ]
    frames = []
    for frame in [stage855, stage859]:
        if frame.empty:
            continue
        for column in columns:
            if column not in frame.columns:
                frame[column] = np.nan
        frames.append(frame[columns].copy())
    if not frames:
        return pd.DataFrame(columns=columns)
    data = pd.concat(frames, ignore_index=True, sort=False)
    data["source_priority"] = data["minute_source"].astype(str).eq("stage859_tqsdk_backtest").astype(int)
    data = data.sort_values(["vt_symbol", "bar_datetime", "source_priority"])
    data = data.drop_duplicates(["vt_symbol", "bar_datetime"], keep="last")
    return data.drop(columns=["source_priority"]).sort_values(["vt_symbol", "bar_datetime"]).reset_index(drop=True)


def _stage859_date_counts(stage859_status: pd.DataFrame, stage859_bars: pd.DataFrame) -> dict[tuple[str, str], int]:
    counts: dict[tuple[str, str], int] = {}
    if not stage859_status.empty:
        for row in stage859_status.itertuples(index=False):
            counts[(str(row.vt_symbol), _normal_date_text(row.required_date))] = int(
                float(getattr(row, "target_date_rows", 0) or 0)
            )
    if not stage859_bars.empty:
        bars = stage859_bars.copy()
        bars["bar_datetime"] = pd.to_datetime(bars["bar_datetime"], errors="coerce")
        bars = bars.dropna(subset=["bar_datetime"])
        bars["bar_date"] = bars["bar_datetime"].dt.strftime("%Y-%m-%d")
        for (vt_symbol, bar_date), group in bars.groupby(["vt_symbol", "bar_date"], sort=False):
            counts[(str(vt_symbol), str(bar_date))] = max(
                counts.get((str(vt_symbol), str(bar_date)), 0), int(len(group))
            )
    return counts


def _request_coverage_after_stage860(stage853_detail: pd.DataFrame) -> pd.DataFrame:
    stage855_coverage = _load_csv(STAGE855_REQUEST_COVERAGE_PATH)
    stage859_status = _load_csv(STAGE859_STATUS_PATH)
    stage859_bars = _load_csv(STAGE859_MINUTE_BARS_PATH)
    stage859_counts = _stage859_date_counts(stage859_status, stage859_bars)
    stage855_patch_by_key = {
        _request_key(row): int(float(getattr(row, "stage855_patch_bars", 0) or 0))
        for row in stage855_coverage.itertuples(index=False)
    }
    rows: list[dict[str, Any]] = []
    for row in stage853_detail.itertuples(index=False):
        key = _request_key(row)
        symbol_date = _symbol_date_key(row.vt_symbol, row.required_date)
        original = int(float(getattr(row, "exact_date_bars", 0) or 0))
        stage855_patch = int(stage855_patch_by_key.get(key, 0))
        stage859_patch = int(stage859_counts.get(symbol_date, 0)) if stage855_patch <= 0 else 0
        after = original + stage855_patch + stage859_patch
        if stage859_patch > 0:
            action = "covered_by_stage859_tqsdk_backtest"
        elif stage855_patch > 0:
            action = "covered_by_stage855_local_raw_patch"
        elif original > 0:
            action = "already_covered"
        else:
            action = "still_missing"
        item = row._asdict()
        item["required_date"] = key[3]
        item["original_exact_date_bars"] = original
        item["stage855_patch_bars"] = stage855_patch
        item["stage859_patch_bars"] = stage859_patch
        item["after_stage860_exact_date_bars"] = after
        item["covered_after_stage860"] = int(after > 0)
        item["coverage_action_after_stage860"] = action
        rows.append(item)
    return pd.DataFrame(rows)


def _stage825_coverage_after_stage860(intraday: pd.DataFrame, request_coverage: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    patched_lot_ids = {
        lot_id
        for lot_id in (
            _source_id_to_lot_id(source_id)
            for source_id in request_coverage[
                request_coverage["covered_after_stage860"].fillna(0).astype(int).gt(0)
                & request_coverage["request_type"].astype(str).eq("stage825_entry_day")
            ]["source_id"]
        )
        if lot_id is not None
    }
    data = intraday.copy()
    data["lot_id"] = pd.to_numeric(data["lot_id"], errors="coerce").astype("Int64")
    data["entry_year"] = pd.to_numeric(data.get("entry_year"), errors="coerce")
    data["original_entry_day_covered"] = pd.to_numeric(
        data.get("entry_day_minute_bars", 0), errors="coerce"
    ).fillna(0).gt(0).astype(int)
    data["stage860_patch_covered"] = data["lot_id"].map(
        lambda value: int(pd.notna(value) and int(value) in patched_lot_ids)
    )
    data["after_stage860_entry_day_covered"] = (
        data["original_entry_day_covered"].astype(bool) | data["stage860_patch_covered"].astype(bool)
    ).astype(int)
    data["coverage_state_after_stage860"] = np.where(
        data["after_stage860_entry_day_covered"].eq(1),
        "entry_day_covered",
        "missing_entry_day_minutes",
    )
    rows: list[dict[str, Any]] = []
    for year, group in data.groupby("entry_year", dropna=False):
        lots = int(len(group))
        original = int(group["original_entry_day_covered"].sum())
        after = int(group["after_stage860_entry_day_covered"].sum())
        rows.append(
            {
                "entry_year": int(year) if pd.notna(year) else "",
                "closed_lots": lots,
                "original_covered_lots": original,
                "stage860_patch_covered_lots": int(group["stage860_patch_covered"].sum()),
                "after_stage860_covered_lots": after,
                "after_stage860_missing_lots": lots - after,
                "original_coverage_rate": float(original / lots) if lots else 0.0,
                "after_stage860_coverage_rate": float(after / lots) if lots else 0.0,
            }
        )
    return data, pd.DataFrame(rows).sort_values("entry_year").reset_index(drop=True)


def _stage849_coverage_after_stage860(minute_features: pd.DataFrame, request_coverage: pd.DataFrame) -> pd.DataFrame:
    patch_counts = {
        _symbol_date_key(row.vt_symbol, row.required_date): int(
            float(getattr(row, "stage855_patch_bars", 0) or 0)
            + float(getattr(row, "stage859_patch_bars", 0) or 0)
        )
        for row in request_coverage[
            request_coverage["covered_after_stage860"].fillna(0).astype(int).gt(0)
            & request_coverage["request_type"].astype(str).eq("stage849_pressure_key_date")
        ].itertuples(index=False)
    }
    data = minute_features.copy()
    data["date_text"] = data["date"].map(_normal_date_text)
    data["original_minute_bars"] = pd.to_numeric(data.get("minute_bars", 0), errors="coerce").fillna(0).astype(int)
    data["stage860_patch_bars"] = [
        int(patch_counts.get(_symbol_date_key(row.vt_symbol, row.date_text), 0))
        for row in data.itertuples(index=False)
    ]
    data["after_stage860_minute_bars"] = data["original_minute_bars"] + data["stage860_patch_bars"]
    data["covered_after_stage860"] = data["after_stage860_minute_bars"].gt(0).astype(int)
    data["coverage_action_after_stage860"] = np.where(
        data["stage860_patch_bars"].gt(0),
        "covered_by_patch_source",
        np.where(data["original_minute_bars"].gt(0), "already_covered", "still_missing"),
    )
    return data


def _summary(
    request_coverage: pd.DataFrame,
    combined_bars: pd.DataFrame,
    stage825_after: pd.DataFrame,
    stage849_after: pd.DataFrame,
) -> dict[str, Any]:
    gap_requests = int(len(request_coverage))
    covered = request_coverage[request_coverage["covered_after_stage860"].fillna(0).astype(int).eq(1)]
    remaining = gap_requests - int(len(covered))
    original_stage825 = int(stage825_after["original_entry_day_covered"].sum())
    after_stage825 = int(stage825_after["after_stage860_entry_day_covered"].sum())
    original_pressure = int(stage849_after["original_minute_bars"].gt(0).sum())
    after_pressure = int(stage849_after["covered_after_stage860"].sum())
    decision = (
        "stage860_full_minute_coverage_restored_no_rule"
        if remaining == 0 and after_stage825 == len(stage825_after) and after_pressure == len(stage849_after)
        else "stage860_minute_coverage_still_incomplete_no_rule"
    )
    return {
        "stage": STAGE,
        "line_id": LINE_ID,
        "decision": decision,
        "stage853_gap_requests": gap_requests,
        "stage855_patch_covered_requests": int(
            request_coverage["stage855_patch_bars"].fillna(0).astype(float).gt(0).sum()
        ),
        "stage859_patch_covered_requests": int(
            request_coverage["stage859_patch_bars"].fillna(0).astype(float).gt(0).sum()
        ),
        "remaining_gap_requests_after_stage860": remaining,
        "combined_patch_minute_bars": int(len(combined_bars)),
        "combined_patch_symbols": int(combined_bars["vt_symbol"].astype(str).nunique()) if not combined_bars.empty else 0,
        "stage825_closed_lots": int(len(stage825_after)),
        "stage825_original_covered_lots": original_stage825,
        "stage825_after_stage860_covered_lots": after_stage825,
        "stage825_after_stage860_missing_lots": int(len(stage825_after) - after_stage825),
        "stage825_original_coverage_rate": float(original_stage825 / len(stage825_after)) if len(stage825_after) else 0.0,
        "stage825_after_stage860_coverage_rate": float(after_stage825 / len(stage825_after))
        if len(stage825_after)
        else 0.0,
        "stage849_key_dates": int(len(stage849_after)),
        "stage849_original_covered_dates": original_pressure,
        "stage849_after_stage860_covered_dates": after_pressure,
        "stage849_after_stage860_missing_dates": int(len(stage849_after) - after_pressure),
        "stage849_original_coverage_rate": float(original_pressure / len(stage849_after)) if len(stage849_after) else 0.0,
        "stage849_after_stage860_coverage_rate": float(after_pressure / len(stage849_after))
        if len(stage849_after)
        else 0.0,
        "new_rule_allowed": 0,
        "engine_allowed": 0,
    }


def _write_report(
    summary: dict[str, Any],
    request_coverage: pd.DataFrame,
    stage825_year: pd.DataFrame,
    stage849_after: pd.DataFrame,
) -> None:
    remaining = request_coverage[request_coverage["covered_after_stage860"].fillna(0).astype(int).eq(0)]
    coverage_actions = (
        request_coverage.groupby(["request_type", "coverage_action_after_stage860"], dropna=False)
        .size()
        .reset_index(name="requests")
        .sort_values(["request_type", "coverage_action_after_stage860"])
    )
    pressure_view = stage849_after[
        [
            "episode_id",
            "vt_symbol",
            "date_text",
            "original_minute_bars",
            "stage860_patch_bars",
            "after_stage860_minute_bars",
            "coverage_action_after_stage860",
        ]
    ].sort_values(["episode_id", "date_text"])
    lines = [
        f"# {STAGE} Stage859 raw导入与完整覆盖重算",
        "",
        "## 阶段定位",
        "",
        "- 阶段性质：数据导入与覆盖重算；不写新交易规则、不接真实引擎、不触发A/B。",
        "- 目标：把 Stage855 本地 raw patch 与 Stage859 TqBacktest raw 合并为研究线 patch source，验证 Stage825/849 是否恢复完整分钟K覆盖。",
        "",
        "## 核心摘要",
        "",
        _md_table(pd.DataFrame([summary])),
        "",
        "## 请求覆盖动作",
        "",
        _md_table(coverage_actions, max_rows=20),
        "",
        "## Stage825年度覆盖",
        "",
        _md_table(stage825_year, max_rows=20),
        "",
        "## Stage849压力关键日期覆盖",
        "",
        _md_table(pressure_view, max_rows=40),
        "",
        "## 仍缺请求",
        "",
        _md_table(remaining.sort_values("priority_abs_pnl", ascending=False).head(20), max_rows=20),
        "",
        "## 判断",
        "",
        f"- 决策：`{summary['decision']}`。",
        "- Stage860 只证明分钟K覆盖恢复，不证明任何日内规则有效。",
        "- 下一步应重画全量 entry-day 图谱和 pressure path 图谱，然后再回到低自由度规则假设；不得跳过视觉复盘直接写引擎。",
        "",
        "## 输出文件",
        "",
        f"- combined_patch_minute_bars：`{COMBINED_PATCH_BARS_PATH}`",
        f"- request_coverage_after_stage860：`{REQUEST_COVERAGE_PATH}`",
        f"- stage825_coverage_after_stage860：`{STAGE825_COVERAGE_PATH}`",
        f"- stage849_pressure_coverage_after_stage860：`{STAGE849_COVERAGE_PATH}`",
        f"- decision：`{DECISION_PATH}`",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    stage853_detail = _load_csv(STAGE853_DETAIL_PATH)
    stage853_detail["required_date"] = stage853_detail["required_date"].map(_normal_date_text)
    stage853_detail = _numeric(
        stage853_detail,
        ["priority_abs_pnl", "realized_pnl", "big_winner", "exact_date_bars"],
    )
    combined_bars = _combined_patch_bars()
    request_coverage = _request_coverage_after_stage860(stage853_detail)
    stage825_after, stage825_year = _stage825_coverage_after_stage860(
        _load_csv(STAGE825_INTRADAY_PATH),
        request_coverage,
    )
    stage849_after = _stage849_coverage_after_stage860(
        _load_csv(STAGE849_MINUTE_PATH),
        request_coverage,
    )
    summary = _summary(request_coverage, combined_bars, stage825_after, stage849_after)

    combined_bars.to_csv(COMBINED_PATCH_BARS_PATH, index=False, encoding="utf-8-sig")
    request_coverage.to_csv(REQUEST_COVERAGE_PATH, index=False, encoding="utf-8-sig")
    stage825_after.to_csv(STAGE825_COVERAGE_PATH, index=False, encoding="utf-8-sig")
    stage825_year.to_csv(STAGE825_YEAR_COVERAGE_PATH, index=False, encoding="utf-8-sig")
    stage849_after.to_csv(STAGE849_COVERAGE_PATH, index=False, encoding="utf-8-sig")
    pd.DataFrame([summary]).to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")

    decision = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "decision": summary["decision"],
        "metrics": summary,
        "outputs": {
            "combined_patch_minute_bars": str(COMBINED_PATCH_BARS_PATH),
            "request_coverage_after_stage860": str(REQUEST_COVERAGE_PATH),
            "stage825_coverage_after_stage860": str(STAGE825_COVERAGE_PATH),
            "stage825_year_coverage_after_stage860": str(STAGE825_YEAR_COVERAGE_PATH),
            "stage849_pressure_coverage_after_stage860": str(STAGE849_COVERAGE_PATH),
            "summary": str(SUMMARY_PATH),
            "report": str(REPORT_PATH),
            "decision": str(DECISION_PATH),
        },
        "allow_new_rule": False,
        "allow_engine": False,
        "allow_ab": False,
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(summary, request_coverage, stage825_year, stage849_after)
    print(json.dumps(_json_safe(summary), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
