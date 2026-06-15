from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import analyze_qmt_roll_stage650_stage526_200k_capital_reality_check as s650


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

LINE_ID = "futures_trend_stage819_intraday_rules"
STAGE = "Stage855"
MODEL_TAG = "stage855_stage854_local_raw_import_v1"
OUTPUT_PREFIX = "qmt_roll_stage855_stage854_local_raw_import"

STAGE825_PREFIX = "qmt_roll_stage825_stage819_intraday_rule_forensics"
STAGE825_TAG = "stage825_stage819_intraday_rule_forensics_v1"
STAGE849_PREFIX = "qmt_roll_stage849_stage848_pressure_path_forensics"
STAGE849_TAG = "stage849_stage848_pressure_path_forensics_v1"
STAGE853_PREFIX = "qmt_roll_stage853_stage852_minute_gap_audit"
STAGE853_TAG = "stage853_stage852_minute_gap_audit_v1"
STAGE854_PREFIX = "qmt_roll_stage854_stage853_minute_fetch_manifest"
STAGE854_TAG = "stage854_stage853_minute_fetch_manifest_v1"

STAGE825_INTRADAY_PATH = OUTPUT_DIR / f"{STAGE825_PREFIX}_intraday_features_{STAGE825_TAG}.csv"
STAGE849_MINUTE_PATH = OUTPUT_DIR / f"{STAGE849_PREFIX}_minute_features_{STAGE849_TAG}.csv"
STAGE853_DETAIL_PATH = OUTPUT_DIR / f"{STAGE853_PREFIX}_gap_detail_{STAGE853_TAG}.csv"
STAGE853_SUMMARY_PATH = OUTPUT_DIR / f"{STAGE853_PREFIX}_summary_{STAGE853_TAG}.csv"
STAGE854_LOCAL_IMPORT_PATH = OUTPUT_DIR / f"{STAGE854_PREFIX}_local_import_manifest_{STAGE854_TAG}.csv"
STAGE854_DOWNLOAD_BATCH_PATH = OUTPUT_DIR / f"{STAGE854_PREFIX}_download_batch_manifest_{STAGE854_TAG}.csv"
STAGE854_DECISION_PATH = OUTPUT_DIR / f"{STAGE854_PREFIX}_decision_{STAGE854_TAG}.json"

PATCH_BARS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_patch_minute_bars_{MODEL_TAG}.csv"
PATCH_DATE_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_patch_date_summary_{MODEL_TAG}.csv"
REQUEST_COVERAGE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_request_coverage_after_patch_{MODEL_TAG}.csv"
STAGE825_COVERAGE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_stage825_coverage_after_patch_{MODEL_TAG}.csv"
STAGE825_YEAR_COVERAGE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_stage825_year_coverage_after_patch_{MODEL_TAG}.csv"
STAGE849_COVERAGE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_stage849_pressure_coverage_after_patch_{MODEL_TAG}.csv"
REMAINING_DOWNLOAD_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_remaining_download_manifest_{MODEL_TAG}.csv"
SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

BAR_COLUMNS = [
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
]


def _json_safe(value: Any) -> Any:
    return s650._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s650._md_table(frame, max_rows=max_rows)


def _load_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise RuntimeError(f"Missing required input: {path}")
    return pd.read_csv(path, encoding="utf-8-sig")


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise RuntimeError(f"Missing required input: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _normal_date_text(value: Any) -> str:
    ts = pd.to_datetime(value, errors="coerce")
    if pd.isna(ts):
        return ""
    return pd.Timestamp(ts).strftime("%Y-%m-%d")


def _normal_dt_series(frame: pd.DataFrame) -> pd.Series:
    if "bar_datetime" in frame.columns:
        raw = frame["bar_datetime"]
    elif "datetime" in frame.columns:
        raw = frame["datetime"]
    else:
        return pd.Series(pd.NaT, index=frame.index)
    if pd.api.types.is_numeric_dtype(raw):
        return pd.to_datetime(raw, unit="ns", errors="coerce", utc=True).dt.tz_convert(
            "Asia/Shanghai"
        ).dt.tz_localize(None)
    parsed = pd.to_datetime(raw, errors="coerce")
    if getattr(parsed.dt, "tz", None) is not None:
        parsed = parsed.dt.tz_convert("Asia/Shanghai").dt.tz_localize(None)
    return parsed


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


def _request_key(vt_symbol: Any, date_text: Any) -> tuple[str, str]:
    return str(vt_symbol), _normal_date_text(date_text)


def _load_local_manifest() -> pd.DataFrame:
    data = _load_csv(STAGE854_LOCAL_IMPORT_PATH).copy()
    if data.empty:
        raise RuntimeError("Stage854 local import manifest is empty")
    data["required_date"] = data["required_date"].map(_normal_date_text)
    for column in ["priority_abs_pnl", "realized_pnl", "big_winner", "local_raw_date_bars"]:
        data[column] = pd.to_numeric(data.get(column), errors="coerce").fillna(0.0)
    return data


def _request_meta(local_manifest: pd.DataFrame) -> dict[tuple[str, str], dict[str, Any]]:
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for (vt_symbol, date_text), group in local_manifest.groupby(["vt_symbol", "required_date"], dropna=False):
        grouped[(str(vt_symbol), str(date_text))] = {
            "request_types": ",".join(sorted(group["request_type"].astype(str).unique())),
            "source_ids": ",".join(sorted(group["source_id"].astype(str).unique())),
            "priority_abs_pnl_sum": float(group["priority_abs_pnl"].sum()),
            "realized_pnl_sum": float(group["realized_pnl"].sum()),
            "big_winner_requests": int(group["big_winner"].sum()),
            "raw_roots": ",".join(sorted(group["best_raw_root"].astype(str).unique())),
        }
    return grouped


def _extract_patch_bars(local_manifest: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    request_meta = _request_meta(local_manifest)
    rows: list[pd.DataFrame] = []
    summaries: list[dict[str, Any]] = []

    grouped = (
        local_manifest.groupby(["vt_symbol", "best_raw_path"], dropna=False)["required_date"]
        .apply(lambda series: sorted(set(series.astype(str))))
        .reset_index()
    )
    for item in grouped.itertuples(index=False):
        vt_symbol = str(item.vt_symbol)
        raw_path = Path(str(item.best_raw_path))
        required_dates = set(item.required_date)
        if not raw_path.exists():
            for date_text in required_dates:
                summaries.append(
                    {
                        "vt_symbol": vt_symbol,
                        "required_date": date_text,
                        "raw_path": str(raw_path),
                        "raw_status": "missing_raw_path",
                        "imported_bars": 0,
                        "first_bar_datetime": "",
                        "last_bar_datetime": "",
                        "message": "raw path no longer exists",
                    }
                )
            continue
        try:
            raw = pd.read_csv(raw_path, encoding="utf-8-sig")
        except Exception as exc:
            for date_text in required_dates:
                summaries.append(
                    {
                        "vt_symbol": vt_symbol,
                        "required_date": date_text,
                        "raw_path": str(raw_path),
                        "raw_status": "read_failed",
                        "imported_bars": 0,
                        "first_bar_datetime": "",
                        "last_bar_datetime": "",
                        "message": repr(exc),
                    }
                )
            continue

        if raw.empty:
            for date_text in required_dates:
                summaries.append(
                    {
                        "vt_symbol": vt_symbol,
                        "required_date": date_text,
                        "raw_path": str(raw_path),
                        "raw_status": "empty_raw",
                        "imported_bars": 0,
                        "first_bar_datetime": "",
                        "last_bar_datetime": "",
                        "message": "",
                    }
                )
            continue

        raw = raw.copy()
        raw["bar_datetime"] = _normal_dt_series(raw)
        raw = raw.dropna(subset=["bar_datetime"])
        raw["bar_date_text"] = raw["bar_datetime"].dt.strftime("%Y-%m-%d")
        if "vt_symbol" not in raw.columns:
            raw["vt_symbol"] = vt_symbol
        if "tq_symbol" not in raw.columns:
            symbol, exchange = vt_symbol.split(".", 1)
            raw["tq_symbol"] = f"{exchange}.{symbol}"
        for column in BAR_COLUMNS:
            if column not in raw.columns:
                raw[column] = np.nan
        raw = _numeric(raw, ["bar_id", "open", "high", "low", "close", "volume", "open_oi", "close_oi"])

        for date_text in sorted(required_dates):
            subset = raw[raw["bar_date_text"].eq(date_text)].copy()
            meta = request_meta.get((vt_symbol, date_text), {})
            imported = int(len(subset))
            if not subset.empty:
                subset = subset[BAR_COLUMNS].copy()
                subset["raw_source_root"] = str(raw_path.parents[1].name) if len(raw_path.parents) >= 2 else ""
                subset["raw_source_path"] = str(raw_path)
                subset["stage855_required_date"] = date_text
                subset["stage855_request_types"] = str(meta.get("request_types", ""))
                subset["stage855_source_ids"] = str(meta.get("source_ids", ""))
                subset["stage855_priority_abs_pnl_sum"] = float(meta.get("priority_abs_pnl_sum", 0.0))
                subset["stage855_big_winner_requests"] = int(meta.get("big_winner_requests", 0))
                rows.append(subset)
            summaries.append(
                {
                    "vt_symbol": vt_symbol,
                    "required_date": date_text,
                    "raw_path": str(raw_path),
                    "raw_status": "imported" if imported > 0 else "no_required_date_bars",
                    "imported_bars": imported,
                    "first_bar_datetime": pd.Timestamp(subset["bar_datetime"].min()).strftime("%Y-%m-%d %H:%M:%S")
                    if imported > 0
                    else "",
                    "last_bar_datetime": pd.Timestamp(subset["bar_datetime"].max()).strftime("%Y-%m-%d %H:%M:%S")
                    if imported > 0
                    else "",
                    "request_types": str(meta.get("request_types", "")),
                    "source_ids": str(meta.get("source_ids", "")),
                    "priority_abs_pnl_sum": float(meta.get("priority_abs_pnl_sum", 0.0)),
                    "big_winner_requests": int(meta.get("big_winner_requests", 0)),
                    "message": "",
                }
            )

    if rows:
        patch_bars = pd.concat(rows, ignore_index=True, sort=False)
        patch_bars = patch_bars.drop_duplicates(["vt_symbol", "bar_datetime"]).sort_values(
            ["vt_symbol", "bar_datetime"]
        )
    else:
        patch_bars = pd.DataFrame(columns=BAR_COLUMNS)
    return patch_bars.reset_index(drop=True), pd.DataFrame(summaries)


def _request_coverage_after_patch(stage853_detail: pd.DataFrame, patch_date_summary: pd.DataFrame) -> pd.DataFrame:
    patch_counts = {
        _request_key(row.vt_symbol, row.required_date): int(row.imported_bars)
        for row in patch_date_summary.itertuples(index=False)
        if int(getattr(row, "imported_bars", 0) or 0) > 0
    }
    rows: list[dict[str, Any]] = []
    for row in stage853_detail.itertuples(index=False):
        key = _request_key(row.vt_symbol, row.required_date)
        original = int(float(getattr(row, "exact_date_bars", 0) or 0))
        patch = int(patch_counts.get(key, 0))
        after = original + patch
        rows.append(
            {
                **row._asdict(),
                "required_date": key[1],
                "original_exact_date_bars": original,
                "stage855_patch_bars": patch,
                "after_patch_exact_date_bars": after,
                "covered_after_patch": int(after > 0),
                "coverage_action_after_patch": "covered_by_local_raw_patch" if patch > 0 else "still_needs_download",
            }
        )
    return pd.DataFrame(rows)


def _stage825_coverage_after_patch(intraday: pd.DataFrame, request_coverage: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    patch_lot_ids = {
        lot_id
        for lot_id in (
            _source_id_to_lot_id(source_id)
            for source_id in request_coverage[
                request_coverage["covered_after_patch"].fillna(0).astype(int).gt(0)
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
    data["stage855_patch_covered"] = data["lot_id"].map(lambda value: int(pd.notna(value) and int(value) in patch_lot_ids))
    data["after_patch_entry_day_covered"] = (
        data["original_entry_day_covered"].astype(bool) | data["stage855_patch_covered"].astype(bool)
    ).astype(int)
    data["coverage_state_after_patch"] = np.where(
        data["after_patch_entry_day_covered"].eq(1), "entry_day_covered", "missing_entry_day_minutes"
    )

    rows: list[dict[str, Any]] = []
    for year, group in data.groupby("entry_year", dropna=False):
        rows.append(
            {
                "entry_year": int(year) if pd.notna(year) else "",
                "closed_lots": int(len(group)),
                "original_covered_lots": int(group["original_entry_day_covered"].sum()),
                "stage855_patch_covered_lots": int(group["stage855_patch_covered"].sum()),
                "after_patch_covered_lots": int(group["after_patch_entry_day_covered"].sum()),
                "after_patch_missing_lots": int(len(group) - group["after_patch_entry_day_covered"].sum()),
                "original_coverage_rate": float(group["original_entry_day_covered"].mean()),
                "after_patch_coverage_rate": float(group["after_patch_entry_day_covered"].mean()),
            }
        )
    year_summary = pd.DataFrame(rows).sort_values("entry_year").reset_index(drop=True)
    return data, year_summary


def _stage849_coverage_after_patch(minute_features: pd.DataFrame, request_coverage: pd.DataFrame) -> pd.DataFrame:
    patch_keys = {
        _request_key(row.vt_symbol, row.required_date): int(row.stage855_patch_bars)
        for row in request_coverage[
            request_coverage["covered_after_patch"].fillna(0).astype(int).gt(0)
            & request_coverage["request_type"].astype(str).eq("stage849_pressure_key_date")
        ].itertuples(index=False)
    }
    data = minute_features.copy()
    data["date_text"] = data["date"].map(_normal_date_text)
    data["original_minute_bars"] = pd.to_numeric(data.get("minute_bars", 0), errors="coerce").fillna(0).astype(int)
    data["stage855_patch_bars"] = [
        int(patch_keys.get(_request_key(row.vt_symbol, row.date_text), 0)) for row in data.itertuples(index=False)
    ]
    data["after_patch_minute_bars"] = data["original_minute_bars"] + data["stage855_patch_bars"]
    data["covered_after_patch"] = data["after_patch_minute_bars"].gt(0).astype(int)
    data["coverage_action_after_patch"] = np.where(
        data["stage855_patch_bars"].gt(0),
        "covered_by_local_raw_patch",
        np.where(data["original_minute_bars"].gt(0), "already_covered", "still_needs_download"),
    )
    return data


def _remaining_download_manifest(download_manifest: pd.DataFrame, request_coverage: pd.DataFrame) -> pd.DataFrame:
    covered_keys = {
        _request_key(row.vt_symbol, row.required_date)
        for row in request_coverage[
            request_coverage["covered_after_patch"].fillna(0).astype(int).gt(0)
        ].itertuples(index=False)
    }
    rows: list[dict[str, Any]] = []
    for row in download_manifest.itertuples(index=False):
        missing_dates = [date for date in str(row.missing_date_list).split(",") if date]
        remaining = [date for date in missing_dates if (str(row.vt_symbol), date) not in covered_keys]
        if not remaining:
            continue
        item = row._asdict()
        item["missing_dates_before_stage855"] = int(row.missing_dates)
        item["missing_dates"] = len(remaining)
        item["missing_date_list"] = ",".join(remaining)
        rows.append(item)
    return pd.DataFrame(rows)


def _summary(
    stage853_detail: pd.DataFrame,
    request_coverage: pd.DataFrame,
    patch_bars: pd.DataFrame,
    patch_date_summary: pd.DataFrame,
    stage825_after: pd.DataFrame,
    stage849_after: pd.DataFrame,
    remaining_download: pd.DataFrame,
) -> pd.DataFrame:
    original_stage825_covered = int(stage825_after["original_entry_day_covered"].sum())
    after_stage825_covered = int(stage825_after["after_patch_entry_day_covered"].sum())
    original_pressure_covered = int(stage849_after["original_minute_bars"].gt(0).sum())
    after_pressure_covered = int(stage849_after["after_patch_minute_bars"].gt(0).sum())
    covered_patch = request_coverage[request_coverage["stage855_patch_bars"].fillna(0).gt(0)].copy()
    remaining = request_coverage[request_coverage["covered_after_patch"].fillna(0).astype(int).eq(0)].copy()
    return pd.DataFrame(
        [
            {
                "stage": STAGE,
                "decision": "stage855_local_raw_patch_imported_coverage_improved_no_rule",
                "stage853_gap_requests": int(len(stage853_detail)),
                "stage855_patch_covered_requests": int(len(covered_patch)),
                "remaining_gap_requests_after_patch": int(len(remaining)),
                "patch_symbols": int(patch_date_summary.loc[patch_date_summary["imported_bars"].gt(0), "vt_symbol"].nunique()),
                "patch_required_dates": int(
                    patch_date_summary.loc[patch_date_summary["imported_bars"].gt(0), ["vt_symbol", "required_date"]]
                    .drop_duplicates()
                    .shape[0]
                ),
                "patch_minute_bars": int(len(patch_bars)),
                "priority_abs_pnl_covered_by_patch": float(covered_patch["priority_abs_pnl"].sum()),
                "priority_abs_pnl_remaining_after_patch": float(remaining["priority_abs_pnl"].sum()),
                "big_winner_requests_covered_by_patch": int(covered_patch["big_winner"].sum()),
                "big_winner_requests_remaining_after_patch": int(remaining["big_winner"].sum()),
                "stage825_closed_lots": int(len(stage825_after)),
                "stage825_original_covered_lots": original_stage825_covered,
                "stage825_after_patch_covered_lots": after_stage825_covered,
                "stage825_patch_delta_lots": int(after_stage825_covered - original_stage825_covered),
                "stage825_original_coverage_rate": float(original_stage825_covered / len(stage825_after)),
                "stage825_after_patch_coverage_rate": float(after_stage825_covered / len(stage825_after)),
                "stage849_key_dates": int(len(stage849_after)),
                "stage849_original_covered_dates": original_pressure_covered,
                "stage849_after_patch_covered_dates": after_pressure_covered,
                "stage849_patch_delta_dates": int(after_pressure_covered - original_pressure_covered),
                "stage849_original_coverage_rate": float(original_pressure_covered / len(stage849_after))
                if len(stage849_after)
                else 0.0,
                "stage849_after_patch_coverage_rate": float(after_pressure_covered / len(stage849_after))
                if len(stage849_after)
                else 0.0,
                "remaining_download_batches_after_patch": int(len(remaining_download)),
                "new_rule_allowed": 0,
                "engine_allowed": 0,
            }
        ]
    )


def _write_report(
    summary: pd.DataFrame,
    patch_date_summary: pd.DataFrame,
    request_coverage: pd.DataFrame,
    stage825_year: pd.DataFrame,
    stage849_after: pd.DataFrame,
    remaining_download: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    top_patch = (
        request_coverage[request_coverage["stage855_patch_bars"].fillna(0).gt(0)]
        .sort_values(["priority_abs_pnl", "stage855_patch_bars"], ascending=[False, False])
        .head(25)
    )
    top_remaining = (
        request_coverage[request_coverage["covered_after_patch"].fillna(0).astype(int).eq(0)]
        .sort_values("priority_abs_pnl", ascending=False)
        .head(25)
    )
    pressure_view = stage849_after[
        [
            "episode_id",
            "vt_symbol",
            "date_text",
            "original_minute_bars",
            "stage855_patch_bars",
            "after_patch_minute_bars",
            "coverage_action_after_patch",
        ]
    ].sort_values(["coverage_action_after_patch", "episode_id", "date_text"])

    lines = [
        "# Stage855 Stage854本地raw分钟K导入与覆盖重算",
        "",
        "## 阶段定位",
        "",
        "- 阶段性质：数据补齐；只导入本地 raw 中已存在的 exact contract/date 分钟K，不下载数据、不改策略、不接引擎、不连接 CTP、不调用下单。",
        "- 目标：把 Stage854 标记为本地可恢复的分钟K写成研究线专用 patch source，并重算 Stage825/849 覆盖。",
        "",
        "## 外部/GitHub调研判断",
        "",
        "- TqSdk 官方 `DataDownloader` 适合作为后续历史分钟CSV补数路径；本阶段暂不下载，只做本地 raw 复用。",
        "- TqSdk `get_kline_serial` 更适合近端序列/实时对象，不作为全周期缺口补数主路径。",
        "- GitHub 上 `shinnytech/tqsdk-python` 与 `vnpy/vnpy_tqsdk` 支持复用现有 TqSdk CSV 管道，但旧合约或权限缺口要作为数据问题记录，不允许转成策略过滤规则。",
        "",
        "## 核心摘要",
        "",
        _md_table(summary),
        "",
        "## 本地patch导入日期",
        "",
        _md_table(
            patch_date_summary.sort_values(["priority_abs_pnl_sum", "imported_bars"], ascending=[False, False]).head(30),
            max_rows=30,
        ),
        "",
        "## patch覆盖请求",
        "",
        _md_table(top_patch, max_rows=25),
        "",
        "## Stage825年度覆盖变化",
        "",
        _md_table(stage825_year, max_rows=20),
        "",
        "## Stage849压力关键日期覆盖变化",
        "",
        _md_table(pressure_view, max_rows=40),
        "",
        "## 仍需下载优先级",
        "",
        _md_table(top_remaining, max_rows=25),
        "",
        "## 结论",
        "",
        f"- 决策标签：`{decision['decision']}`。",
        "- 本阶段只提高证据覆盖，不写新规则。下一步应按剩余 download manifest 补数，再重跑 Stage825/849 的 K线图谱。",
        "- 已导入的 patch source 可作为后续 Stage825/849 复跑的额外分钟源，但不能替代下载剩余 exact 合约日期。",
        "",
        "## 反思",
        "",
        "- 运行前过拟合判断：否。只导入既有 raw 数据，不根据收益选择交易规则。",
        "- 运行后过拟合判断：否。覆盖提升只说明证据更完整，不构成任何品种/年份/方向过滤。",
        "- 运行前继续价值判断：有价值。Stage854 已定位 29 个本地可恢复缺口。",
        "- 运行后继续价值判断：有价值但仍受数据约束。剩余缺口仍需下载，补完后才允许重新做视觉法证和规则判断。",
        "",
        "## 输出",
        "",
        f"- patch_minute_bars：`{PATCH_BARS_PATH}`",
        f"- patch_date_summary：`{PATCH_DATE_SUMMARY_PATH}`",
        f"- request_coverage_after_patch：`{REQUEST_COVERAGE_PATH}`",
        f"- stage825_coverage_after_patch：`{STAGE825_COVERAGE_PATH}`",
        f"- stage849_pressure_coverage_after_patch：`{STAGE849_COVERAGE_PATH}`",
        f"- remaining_download_manifest：`{REMAINING_DOWNLOAD_PATH}`",
        f"- decision：`{DECISION_PATH}`",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    local_manifest = _load_local_manifest()
    stage853_detail = _load_csv(STAGE853_DETAIL_PATH).copy()
    stage825_intraday = _load_csv(STAGE825_INTRADAY_PATH).copy()
    stage849_minute = _load_csv(STAGE849_MINUTE_PATH).copy()
    stage854_download = _load_csv(STAGE854_DOWNLOAD_BATCH_PATH).copy()
    stage854_decision = _load_json(STAGE854_DECISION_PATH)
    stage853_summary = _load_csv(STAGE853_SUMMARY_PATH)

    stage853_detail["required_date"] = stage853_detail["required_date"].map(_normal_date_text)
    for column in ["priority_abs_pnl", "realized_pnl", "big_winner", "exact_date_bars"]:
        stage853_detail[column] = pd.to_numeric(stage853_detail.get(column), errors="coerce").fillna(0.0)

    patch_bars, patch_date_summary = _extract_patch_bars(local_manifest)
    request_coverage = _request_coverage_after_patch(stage853_detail, patch_date_summary)
    stage825_after, stage825_year = _stage825_coverage_after_patch(stage825_intraday, request_coverage)
    stage849_after = _stage849_coverage_after_patch(stage849_minute, request_coverage)
    remaining_download = _remaining_download_manifest(stage854_download, request_coverage)
    summary = _summary(
        stage853_detail,
        request_coverage,
        patch_bars,
        patch_date_summary,
        stage825_after,
        stage849_after,
        remaining_download,
    )

    patch_bars.to_csv(PATCH_BARS_PATH, index=False, encoding="utf-8-sig")
    patch_date_summary.to_csv(PATCH_DATE_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    request_coverage.to_csv(REQUEST_COVERAGE_PATH, index=False, encoding="utf-8-sig")
    stage825_after.to_csv(STAGE825_COVERAGE_PATH, index=False, encoding="utf-8-sig")
    stage825_year.to_csv(STAGE825_YEAR_COVERAGE_PATH, index=False, encoding="utf-8-sig")
    stage849_after.to_csv(STAGE849_COVERAGE_PATH, index=False, encoding="utf-8-sig")
    remaining_download.to_csv(REMAINING_DOWNLOAD_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")

    decision = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S CST"),
        "line_id": LINE_ID,
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "decision": "stage855_local_raw_patch_imported_coverage_improved_no_rule",
        "new_rule_allowed": 0,
        "engine_allowed": 0,
        "download_allowed_next_stage": 1,
        "rerun_visual_atlas_after_download": 1,
        "metrics": summary.iloc[0].to_dict(),
        "stage853_decision": str(stage853_summary.iloc[0].get("decision", "")) if not stage853_summary.empty else "",
        "stage854_decision": stage854_decision.get("decision", ""),
        "next_step": (
            "Use remaining_download_manifest to fill the residual exact contract/date minute gaps; "
            "then rerun Stage825/849 visual atlases with the Stage855 patch source plus downloaded bars."
        ),
        "inputs": {
            "stage825_intraday": str(STAGE825_INTRADAY_PATH),
            "stage849_minute": str(STAGE849_MINUTE_PATH),
            "stage853_gap_detail": str(STAGE853_DETAIL_PATH),
            "stage854_local_import": str(STAGE854_LOCAL_IMPORT_PATH),
            "stage854_download_batch": str(STAGE854_DOWNLOAD_BATCH_PATH),
        },
        "outputs": {
            "patch_minute_bars": str(PATCH_BARS_PATH),
            "patch_date_summary": str(PATCH_DATE_SUMMARY_PATH),
            "request_coverage_after_patch": str(REQUEST_COVERAGE_PATH),
            "stage825_coverage_after_patch": str(STAGE825_COVERAGE_PATH),
            "stage825_year_coverage_after_patch": str(STAGE825_YEAR_COVERAGE_PATH),
            "stage849_pressure_coverage_after_patch": str(STAGE849_COVERAGE_PATH),
            "remaining_download_manifest": str(REMAINING_DOWNLOAD_PATH),
            "summary": str(SUMMARY_PATH),
            "report": str(REPORT_PATH),
            "decision": str(DECISION_PATH),
        },
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(summary, patch_date_summary, request_coverage, stage825_year, stage849_after, remaining_download, decision)

    print(f"[{STAGE}] decision: {decision['decision']}")
    print(summary.to_string(index=False))
    print(f"[{STAGE}] report: {REPORT_PATH}")
    print(f"[{STAGE}] decision json: {DECISION_PATH}")


if __name__ == "__main__":
    main()
