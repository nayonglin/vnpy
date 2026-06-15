from __future__ import annotations

from datetime import datetime
import json
import math
import os
from pathlib import Path
import time
from typing import Any

import numpy as np
import pandas as pd
from tqsdk import TqApi, TqAuth
from tqsdk.tools import DataDownloader
from vnpy.trader.setting import SETTINGS

import analyze_qmt_roll_stage650_stage526_200k_capital_reality_check as s650


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
RAW_ROOT = PROJECT_DIR / "downloaded_futures" / "tqsdk_stage856_remaining_gap_backfill"

LINE_ID = "futures_trend_stage819_intraday_rules"
STAGE = "Stage856"
MODEL_TAG = "stage856_stage855_remaining_gap_download_v1"
OUTPUT_PREFIX = "qmt_roll_stage856_stage855_remaining_gap_download"

STAGE825_PREFIX = "qmt_roll_stage825_stage819_intraday_rule_forensics"
STAGE825_TAG = "stage825_stage819_intraday_rule_forensics_v1"
STAGE849_PREFIX = "qmt_roll_stage849_stage848_pressure_path_forensics"
STAGE849_TAG = "stage849_stage848_pressure_path_forensics_v1"
STAGE855_PREFIX = "qmt_roll_stage855_stage854_local_raw_import"
STAGE855_TAG = "stage855_stage854_local_raw_import_v1"

STAGE825_INTRADAY_PATH = OUTPUT_DIR / f"{STAGE825_PREFIX}_intraday_features_{STAGE825_TAG}.csv"
STAGE849_MINUTE_PATH = OUTPUT_DIR / f"{STAGE849_PREFIX}_minute_features_{STAGE849_TAG}.csv"
STAGE855_REQUEST_COVERAGE_PATH = OUTPUT_DIR / f"{STAGE855_PREFIX}_request_coverage_after_patch_{STAGE855_TAG}.csv"
STAGE855_REMAINING_DOWNLOAD_PATH = OUTPUT_DIR / f"{STAGE855_PREFIX}_remaining_download_manifest_{STAGE855_TAG}.csv"
STAGE855_DECISION_PATH = OUTPUT_DIR / f"{STAGE855_PREFIX}_decision_{STAGE855_TAG}.json"

STATUS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_download_status_{MODEL_TAG}.csv"
DOWNLOADED_BARS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_downloaded_minute_bars_{MODEL_TAG}.csv"
BATCH_COVERAGE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_batch_coverage_{MODEL_TAG}.csv"
REQUEST_COVERAGE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_request_coverage_after_download_{MODEL_TAG}.csv"
STAGE825_COVERAGE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_stage825_coverage_after_download_{MODEL_TAG}.csv"
STAGE825_YEAR_COVERAGE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_stage825_year_coverage_after_download_{MODEL_TAG}.csv"
STAGE849_COVERAGE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_stage849_pressure_coverage_after_download_{MODEL_TAG}.csv"
REMAINING_GAPS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_remaining_gap_requests_{MODEL_TAG}.csv"
SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

MAX_BATCHES = int(os.getenv("STAGE856_MAX_BATCHES", "0"))
BATCH_OFFSET = int(os.getenv("STAGE856_BATCH_OFFSET", "0"))
PER_BATCH_TIMEOUT_SECONDS = int(os.getenv("STAGE856_PER_BATCH_TIMEOUT_SECONDS", "120"))
SLEEP_SECONDS = float(os.getenv("STAGE856_SLEEP_SECONDS", "0.02"))
FORCE_REFRESH = os.getenv("STAGE856_FORCE_REFRESH", "0").strip() == "1"

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


def _require_credentials() -> tuple[str, str]:
    username = str(SETTINGS.get("datafeed.username", ""))
    password = str(SETTINGS.get("datafeed.password", ""))
    if not username or not password:
        raise RuntimeError("TqSdk credentials are missing in vn.py SETTINGS.")
    return username, password


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


def _raw_path(row: Any) -> Path:
    vt_symbol = str(row.vt_symbol)
    symbol, exchange = vt_symbol.split(".", 1)
    first = _normal_date_text(row.first_missing_date).replace("-", "")
    last = _normal_date_text(row.last_missing_date).replace("-", "")
    batch_index = int(row.batch_index)
    return RAW_ROOT / exchange / f"{symbol}_batch{batch_index:03d}_{first}_{last}_minute_backtest.csv"


def _load_remaining_manifest() -> pd.DataFrame:
    data = _load_csv(STAGE855_REMAINING_DOWNLOAD_PATH).copy()
    if data.empty:
        raise RuntimeError("Stage855 remaining download manifest is empty")
    data["priority_abs_pnl"] = pd.to_numeric(data["priority_abs_pnl"], errors="coerce").fillna(0.0)
    data["big_winner_requests"] = pd.to_numeric(data["big_winner_requests"], errors="coerce").fillna(0).astype(int)
    data["missing_dates"] = pd.to_numeric(data["missing_dates"], errors="coerce").fillna(0).astype(int)
    data = data.sort_values(["priority_abs_pnl", "missing_dates", "vt_symbol"], ascending=[False, False, True])
    data = data.reset_index(drop=True)
    data["selection_rank"] = np.arange(1, len(data) + 1)
    if BATCH_OFFSET > 0:
        data = data.iloc[BATCH_OFFSET:].copy()
    if MAX_BATCHES > 0:
        data = data.head(MAX_BATCHES).copy()
    return data.reset_index(drop=True)


def _read_csv_rows(path: Path) -> int:
    if not path.exists() or path.stat().st_size <= 0:
        return 0
    try:
        return int(len(pd.read_csv(path, encoding="utf-8-sig")))
    except Exception:
        return 0


def _download_one(api: TqApi, row: Any) -> dict[str, Any]:
    csv_path = _raw_path(row)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    tq_symbol = str(row.tq_symbol)
    start_dt = pd.Timestamp(row.download_start_dt).to_pydatetime()
    end_dt = pd.Timestamp(row.download_end_dt).to_pydatetime()
    status = {
        "selection_rank": int(row.selection_rank),
        "vt_symbol": str(row.vt_symbol),
        "tq_symbol": tq_symbol,
        "batch_index": int(row.batch_index),
        "missing_date_list": str(row.missing_date_list),
        "download_start_dt": pd.Timestamp(row.download_start_dt),
        "download_end_dt": pd.Timestamp(row.download_end_dt),
        "priority_abs_pnl": float(row.priority_abs_pnl),
        "big_winner_requests": int(row.big_winner_requests),
        "csv_path": str(csv_path),
        "status": "unknown",
        "progress": 0.0,
        "rows": 0,
        "elapsed_seconds": 0.0,
        "message": "",
    }

    if csv_path.exists() and csv_path.stat().st_size > 0 and not FORCE_REFRESH:
        status["status"] = "cached_csv"
        status["rows"] = _read_csv_rows(csv_path)
        status["progress"] = 100.0
        return status

    if FORCE_REFRESH and csv_path.exists():
        csv_path.unlink()

    started = time.time()
    try:
        downloader = DataDownloader(
            api,
            symbol_list=tq_symbol,
            dur_sec=60,
            start_dt=start_dt,
            end_dt=end_dt,
            csv_file_name=str(csv_path),
        )
        while not downloader.is_finished():
            api.wait_update()
            status["progress"] = float(downloader.get_progress())
            if time.time() - started > PER_BATCH_TIMEOUT_SECONDS:
                status["status"] = "timeout"
                status["message"] = f"timeout_after_{PER_BATCH_TIMEOUT_SECONDS}s"
                break
            if SLEEP_SECONDS > 0:
                time.sleep(SLEEP_SECONDS)
        if status["status"] != "timeout":
            status["progress"] = float(downloader.get_progress())
            if csv_path.exists() and csv_path.stat().st_size > 0:
                status["status"] = "downloaded"
            else:
                status["status"] = "empty"
                status["message"] = "empty_or_missing_csv"
    except Exception as exc:
        status["status"] = "failed"
        status["message"] = repr(exc)

    status["elapsed_seconds"] = round(time.time() - started, 2)
    status["rows"] = _read_csv_rows(csv_path)
    return status


def _download_batches(manifest: pd.DataFrame) -> pd.DataFrame:
    username, password = _require_credentials()
    status_rows: list[dict[str, Any]] = []
    api = TqApi(auth=TqAuth(username, password))
    try:
        for row in manifest.itertuples(index=False):
            result = _download_one(api, row)
            status_rows.append(result)
            pd.DataFrame(status_rows).to_csv(STATUS_PATH, index=False, encoding="utf-8-sig")
            print(
                f"{result['status']} rank={result['selection_rank']} {result['vt_symbol']} "
                f"{result['missing_date_list']} rows={result['rows']} progress={result['progress']:.2f}",
                flush=True,
            )
    finally:
        api.close()
    status = pd.DataFrame(status_rows)
    status.to_csv(STATUS_PATH, index=False, encoding="utf-8-sig")
    return status


def _normalize_downloaded_file(status_row: Any) -> pd.DataFrame:
    path = Path(str(status_row.csv_path))
    vt_symbol = str(status_row.vt_symbol)
    tq_symbol = str(status_row.tq_symbol)
    if not path.exists() or path.stat().st_size <= 0:
        return pd.DataFrame(columns=BAR_COLUMNS)
    try:
        raw = pd.read_csv(path, encoding="utf-8-sig")
    except Exception:
        return pd.DataFrame(columns=BAR_COLUMNS)
    if raw.empty:
        return pd.DataFrame(columns=BAR_COLUMNS)
    raw = raw.copy()
    raw["bar_datetime"] = _normal_dt_series(raw)
    raw = raw.dropna(subset=["bar_datetime"])
    if raw.empty:
        return pd.DataFrame(columns=BAR_COLUMNS)
    if "vt_symbol" not in raw.columns:
        raw["vt_symbol"] = vt_symbol
    if "tq_symbol" not in raw.columns:
        raw["tq_symbol"] = tq_symbol
    for column in BAR_COLUMNS:
        if column not in raw.columns:
            raw[column] = np.nan
    raw = _numeric(raw, ["bar_id", "open", "high", "low", "close", "volume", "open_oi", "close_oi"])
    data = raw[BAR_COLUMNS].copy()
    data["raw_source_root"] = RAW_ROOT.name
    data["raw_source_path"] = str(path)
    data["stage856_selection_rank"] = int(status_row.selection_rank)
    data["stage856_batch_index"] = int(status_row.batch_index)
    data["stage856_missing_date_list"] = str(status_row.missing_date_list)
    return data


def _downloaded_patch_bars(status: pd.DataFrame) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for row in status.itertuples(index=False):
        if str(row.status) not in {"downloaded", "cached_csv"}:
            continue
        bars = _normalize_downloaded_file(row)
        if not bars.empty:
            frames.append(bars)
    if not frames:
        return pd.DataFrame(columns=BAR_COLUMNS)
    data = pd.concat(frames, ignore_index=True, sort=False)
    data = data.drop_duplicates(["vt_symbol", "bar_datetime"]).sort_values(["vt_symbol", "bar_datetime"])
    return data.reset_index(drop=True)


def _batch_coverage(manifest: pd.DataFrame, status: pd.DataFrame, downloaded: pd.DataFrame) -> pd.DataFrame:
    status_map = {
        (str(row.vt_symbol), int(row.batch_index), str(row.missing_date_list)): row._asdict()
        for row in status.itertuples(index=False)
    }
    if downloaded.empty:
        counts: dict[tuple[str, str], int] = {}
    else:
        temp = downloaded.copy()
        temp["date_text"] = pd.to_datetime(temp["bar_datetime"], errors="coerce").dt.strftime("%Y-%m-%d")
        counts = temp.groupby(["vt_symbol", "date_text"], dropna=False).size().to_dict()
    rows: list[dict[str, Any]] = []
    for row in manifest.itertuples(index=False):
        key = (str(row.vt_symbol), int(row.batch_index), str(row.missing_date_list))
        stat = status_map.get(key, {})
        missing_dates = [date for date in str(row.missing_date_list).split(",") if date]
        covered_dates = [date for date in missing_dates if int(counts.get((str(row.vt_symbol), date), 0)) > 0]
        rows.append(
            {
                "selection_rank": int(row.selection_rank),
                "vt_symbol": str(row.vt_symbol),
                "tq_symbol": str(row.tq_symbol),
                "batch_index": int(row.batch_index),
                "missing_date_list": str(row.missing_date_list),
                "missing_dates": int(row.missing_dates),
                "covered_dates": len(covered_dates),
                "covered_date_list": ",".join(covered_dates),
                "coverage_rate": float(len(covered_dates) / len(missing_dates)) if missing_dates else 0.0,
                "download_status": str(stat.get("status", "not_selected")),
                "csv_path": str(stat.get("csv_path", "")),
                "rows": int(stat.get("rows", 0) or 0),
                "priority_abs_pnl": float(row.priority_abs_pnl),
                "big_winner_requests": int(row.big_winner_requests),
                "message": str(stat.get("message", "")),
            }
        )
    return pd.DataFrame(rows)


def _request_coverage_after_download(stage855_coverage: pd.DataFrame, downloaded: pd.DataFrame) -> pd.DataFrame:
    if downloaded.empty:
        counts: dict[tuple[str, str], int] = {}
    else:
        temp = downloaded.copy()
        temp["date_text"] = pd.to_datetime(temp["bar_datetime"], errors="coerce").dt.strftime("%Y-%m-%d")
        counts = temp.groupby(["vt_symbol", "date_text"], dropna=False).size().to_dict()
    rows: list[dict[str, Any]] = []
    for row in stage855_coverage.itertuples(index=False):
        vt_symbol, date_text = _request_key(row.vt_symbol, row.required_date)
        original = int(getattr(row, "original_exact_date_bars", 0) or 0)
        stage855 = int(getattr(row, "stage855_patch_bars", 0) or 0)
        stage856 = int(counts.get((vt_symbol, date_text), 0))
        after = original + stage855 + stage856
        if stage856 > 0:
            action = "covered_by_stage856_download"
        elif stage855 > 0:
            action = "covered_by_stage855_local_raw_patch"
        elif original > 0:
            action = "already_covered_before_stage853"
        else:
            action = "still_needs_download"
        rows.append(
            {
                **row._asdict(),
                "required_date": date_text,
                "stage856_download_bars": stage856,
                "after_stage856_exact_date_bars": after,
                "covered_after_stage856": int(after > 0),
                "coverage_action_after_stage856": action,
            }
        )
    return pd.DataFrame(rows)


def _stage825_coverage_after_download(intraday: pd.DataFrame, request_coverage: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    covered_lot_ids = {
        lot_id
        for lot_id in (
            _source_id_to_lot_id(source_id)
            for source_id in request_coverage[
                request_coverage["covered_after_stage856"].fillna(0).astype(int).gt(0)
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
    data["after_stage856_covered"] = data["lot_id"].map(
        lambda value: int(pd.notna(value) and int(value) in covered_lot_ids)
    )
    data["entry_day_covered_after_stage856"] = (
        data["original_entry_day_covered"].astype(bool) | data["after_stage856_covered"].astype(bool)
    ).astype(int)
    rows: list[dict[str, Any]] = []
    for year, group in data.groupby("entry_year", dropna=False):
        rows.append(
            {
                "entry_year": int(year) if pd.notna(year) else "",
                "closed_lots": int(len(group)),
                "original_covered_lots": int(group["original_entry_day_covered"].sum()),
                "after_stage856_covered_lots": int(group["entry_day_covered_after_stage856"].sum()),
                "remaining_missing_lots": int(len(group) - group["entry_day_covered_after_stage856"].sum()),
                "original_coverage_rate": float(group["original_entry_day_covered"].mean()),
                "after_stage856_coverage_rate": float(group["entry_day_covered_after_stage856"].mean()),
            }
        )
    return data, pd.DataFrame(rows).sort_values("entry_year").reset_index(drop=True)


def _stage849_coverage_after_download(minute_features: pd.DataFrame, request_coverage: pd.DataFrame) -> pd.DataFrame:
    rows = request_coverage[request_coverage["request_type"].astype(str).eq("stage849_pressure_key_date")].copy()
    stage855_counts = {
        _request_key(row.vt_symbol, row.required_date): int(row.stage855_patch_bars)
        for row in rows.itertuples(index=False)
    }
    stage856_counts = {
        _request_key(row.vt_symbol, row.required_date): int(row.stage856_download_bars)
        for row in rows.itertuples(index=False)
    }
    data = minute_features.copy()
    data["date_text"] = data["date"].map(_normal_date_text)
    data["original_minute_bars"] = pd.to_numeric(data.get("minute_bars", 0), errors="coerce").fillna(0).astype(int)
    data["stage855_patch_bars"] = [
        int(stage855_counts.get(_request_key(row.vt_symbol, row.date_text), 0)) for row in data.itertuples(index=False)
    ]
    data["stage856_download_bars"] = [
        int(stage856_counts.get(_request_key(row.vt_symbol, row.date_text), 0)) for row in data.itertuples(index=False)
    ]
    data["after_stage856_minute_bars"] = (
        data["original_minute_bars"] + data["stage855_patch_bars"] + data["stage856_download_bars"]
    )
    data["covered_after_stage856"] = data["after_stage856_minute_bars"].gt(0).astype(int)
    data["coverage_action_after_stage856"] = np.where(
        data["stage856_download_bars"].gt(0),
        "covered_by_stage856_download",
        np.where(
            data["stage855_patch_bars"].gt(0),
            "covered_by_stage855_local_raw_patch",
            np.where(data["original_minute_bars"].gt(0), "already_covered", "still_needs_download"),
        ),
    )
    return data


def _summary(
    manifest: pd.DataFrame,
    status: pd.DataFrame,
    downloaded: pd.DataFrame,
    batch_coverage: pd.DataFrame,
    request_coverage: pd.DataFrame,
    stage825_after: pd.DataFrame,
    stage849_after: pd.DataFrame,
) -> pd.DataFrame:
    total_requests = len(request_coverage)
    stage856_requests = request_coverage[request_coverage["stage856_download_bars"].fillna(0).gt(0)].copy()
    covered_after = request_coverage[request_coverage["covered_after_stage856"].fillna(0).astype(int).gt(0)].copy()
    remaining = request_coverage[request_coverage["covered_after_stage856"].fillna(0).astype(int).eq(0)].copy()
    original_stage825 = int(stage825_after["original_entry_day_covered"].sum())
    after_stage825 = int(stage825_after["entry_day_covered_after_stage856"].sum())
    original_stage849 = int(stage849_after["original_minute_bars"].gt(0).sum())
    after_stage849 = int(stage849_after["after_stage856_minute_bars"].gt(0).sum())
    permission_blocked = (
        status["message"].astype(str).str.contains("不支持下载历史数据功能|tqsdk-buy|权限|permission", regex=True).sum()
        if not status.empty and "message" in status.columns
        else 0
    )
    if not status.empty:
        status_counts = status["status"].astype(str).value_counts().to_dict()
    else:
        status_counts = {}
    return pd.DataFrame(
        [
            {
                "stage": STAGE,
                "decision": "stage856_remaining_gap_download_attempt_no_rule",
                "selected_batches": int(len(manifest)),
                "selected_missing_dates": int(manifest["missing_dates"].sum()) if not manifest.empty else 0,
                "downloaded_or_cached_batches": int(status["status"].astype(str).isin(["downloaded", "cached_csv"]).sum())
                if not status.empty
                else 0,
                "failed_batches": int(status["status"].astype(str).eq("failed").sum()) if not status.empty else 0,
                "timeout_batches": int(status["status"].astype(str).eq("timeout").sum()) if not status.empty else 0,
                "empty_batches": int(status["status"].astype(str).eq("empty").sum()) if not status.empty else 0,
                "permission_blocked_batches": int(permission_blocked),
                "downloaded_minute_bars": int(len(downloaded)),
                "covered_dates_in_selected_batches": int(batch_coverage["covered_dates"].sum())
                if not batch_coverage.empty
                else 0,
                "stage853_gap_requests": int(total_requests),
                "stage856_newly_covered_requests": int(len(stage856_requests)),
                "covered_requests_after_stage856": int(len(covered_after)),
                "remaining_gap_requests_after_stage856": int(len(remaining)),
                "priority_abs_pnl_newly_covered_by_stage856": float(stage856_requests["priority_abs_pnl"].sum()),
                "priority_abs_pnl_remaining_after_stage856": float(remaining["priority_abs_pnl"].sum()),
                "big_winner_requests_newly_covered_by_stage856": int(stage856_requests["big_winner"].sum()),
                "big_winner_requests_remaining_after_stage856": int(remaining["big_winner"].sum()),
                "stage825_closed_lots": int(len(stage825_after)),
                "stage825_original_covered_lots": original_stage825,
                "stage825_after_stage856_covered_lots": after_stage825,
                "stage825_after_stage856_coverage_rate": float(after_stage825 / len(stage825_after))
                if len(stage825_after)
                else 0.0,
                "stage849_key_dates": int(len(stage849_after)),
                "stage849_original_covered_dates": original_stage849,
                "stage849_after_stage856_covered_dates": after_stage849,
                "stage849_after_stage856_coverage_rate": float(after_stage849 / len(stage849_after))
                if len(stage849_after)
                else 0.0,
                "status_counts": json.dumps(status_counts, ensure_ascii=False, sort_keys=True),
                "new_rule_allowed": 0,
                "engine_allowed": 0,
            }
        ]
    )


def _write_report(
    summary: pd.DataFrame,
    status: pd.DataFrame,
    batch_coverage: pd.DataFrame,
    request_coverage: pd.DataFrame,
    stage825_year: pd.DataFrame,
    stage849_after: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    newly = request_coverage[request_coverage["stage856_download_bars"].fillna(0).gt(0)].sort_values(
        ["priority_abs_pnl", "stage856_download_bars"], ascending=[False, False]
    )
    remaining = request_coverage[request_coverage["covered_after_stage856"].fillna(0).astype(int).eq(0)].sort_values(
        "priority_abs_pnl", ascending=False
    )
    pressure_view = stage849_after[
        [
            "episode_id",
            "vt_symbol",
            "date_text",
            "original_minute_bars",
            "stage855_patch_bars",
            "stage856_download_bars",
            "after_stage856_minute_bars",
            "coverage_action_after_stage856",
        ]
    ].sort_values(["coverage_action_after_stage856", "episode_id", "date_text"])
    lines = [
        "# Stage856 Stage855后剩余分钟K缺口下载尝试",
        "",
        "## 阶段定位",
        "",
        "- 阶段性质：数据下载与覆盖审计；不改策略、不接引擎、不连接 CTP、不调用下单。",
        "- 目标：按 Stage855 `remaining_download_manifest` 用 TqSdk `DataDownloader` 补 exact contract/date 分钟K，并重算覆盖。",
        "",
        "## 外部/GitHub调研判断",
        "",
        "- TqSdk 官方 `DataDownloader` 支持按合约、周期、起止时间下载历史K线到 CSV；本阶段固定 `dur_sec=60`。",
        "- TqSdk `get_kline_serial` 是动态序列对象，不作为本线全周期缺口补数主路径。",
        "- vn.py 的 `vnpy_tqsdk` 与仓库既有脚本都使用 `datafeed.username/password`，本阶段只读取该数据权限，不连接交易通道。",
        "",
        "## 核心摘要",
        "",
        _md_table(summary),
        "",
        "## 下载状态",
        "",
        _md_table(status, max_rows=100),
        "",
        "## 批次覆盖",
        "",
        _md_table(batch_coverage, max_rows=100),
        "",
        "## Stage856新增覆盖请求",
        "",
        _md_table(newly.head(30), max_rows=30),
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
        _md_table(remaining.head(40), max_rows=40),
        "",
        "## 结论",
        "",
        f"- 决策标签：`{decision['decision']}`。",
        "- 本阶段不写交易规则。只有剩余关键压力日期补齐并重画图谱后，才允许继续做分钟级规则判断。",
        "- 如果出现权限/空文件/旧合约缺失，先记录为数据阻断，不得把阻断转化成策略过滤。",
        "",
        "## 反思",
        "",
        "- 运行前过拟合判断：否。只按预声明缺口下载 exact contract/date，不筛规则。",
        "- 运行后过拟合判断：否。下载成功或失败只影响证据覆盖，不产生交易参数。",
        "- 运行前继续价值判断：有价值。Stage855 后仍有 `97` 个缺口和多个压力关键日期。",
        "- 运行后继续价值判断：取决于覆盖率；若关键日期补齐，应重跑 Stage825/849 图谱，否则继续处理数据阻断。",
        "",
        "## 输出",
        "",
        f"- download_status：`{STATUS_PATH}`",
        f"- downloaded_minute_bars：`{DOWNLOADED_BARS_PATH}`",
        f"- batch_coverage：`{BATCH_COVERAGE_PATH}`",
        f"- request_coverage_after_download：`{REQUEST_COVERAGE_PATH}`",
        f"- remaining_gap_requests：`{REMAINING_GAPS_PATH}`",
        f"- decision：`{DECISION_PATH}`",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    manifest = _load_remaining_manifest()
    stage855_coverage = _load_csv(STAGE855_REQUEST_COVERAGE_PATH).copy()
    stage825_intraday = _load_csv(STAGE825_INTRADAY_PATH).copy()
    stage849_minute = _load_csv(STAGE849_MINUTE_PATH).copy()
    stage855_decision = _load_json(STAGE855_DECISION_PATH)

    status = _download_batches(manifest)
    downloaded = _downloaded_patch_bars(status)
    batch_coverage = _batch_coverage(manifest, status, downloaded)
    request_coverage = _request_coverage_after_download(stage855_coverage, downloaded)
    stage825_after, stage825_year = _stage825_coverage_after_download(stage825_intraday, request_coverage)
    stage849_after = _stage849_coverage_after_download(stage849_minute, request_coverage)
    remaining_gaps = request_coverage[request_coverage["covered_after_stage856"].fillna(0).astype(int).eq(0)].copy()
    summary = _summary(manifest, status, downloaded, batch_coverage, request_coverage, stage825_after, stage849_after)

    downloaded.to_csv(DOWNLOADED_BARS_PATH, index=False, encoding="utf-8-sig")
    batch_coverage.to_csv(BATCH_COVERAGE_PATH, index=False, encoding="utf-8-sig")
    request_coverage.to_csv(REQUEST_COVERAGE_PATH, index=False, encoding="utf-8-sig")
    stage825_after.to_csv(STAGE825_COVERAGE_PATH, index=False, encoding="utf-8-sig")
    stage825_year.to_csv(STAGE825_YEAR_COVERAGE_PATH, index=False, encoding="utf-8-sig")
    stage849_after.to_csv(STAGE849_COVERAGE_PATH, index=False, encoding="utf-8-sig")
    remaining_gaps.to_csv(REMAINING_GAPS_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")

    decision = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S CST"),
        "line_id": LINE_ID,
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "decision": "stage856_remaining_gap_download_attempt_no_rule",
        "new_rule_allowed": 0,
        "engine_allowed": 0,
        "metrics": summary.iloc[0].to_dict(),
        "stage855_decision": stage855_decision.get("decision", ""),
        "settings": {
            "max_batches": MAX_BATCHES,
            "batch_offset": BATCH_OFFSET,
            "per_batch_timeout_seconds": PER_BATCH_TIMEOUT_SECONDS,
            "force_refresh": FORCE_REFRESH,
            "raw_root": str(RAW_ROOT),
        },
        "next_step": "If enough key pressure dates are covered, rerun Stage825/849 visual atlases with Stage855+Stage856 sources; otherwise investigate permission/empty legacy contracts.",
        "inputs": {
            "stage855_request_coverage": str(STAGE855_REQUEST_COVERAGE_PATH),
            "stage855_remaining_download": str(STAGE855_REMAINING_DOWNLOAD_PATH),
            "stage825_intraday": str(STAGE825_INTRADAY_PATH),
            "stage849_minute": str(STAGE849_MINUTE_PATH),
        },
        "outputs": {
            "download_status": str(STATUS_PATH),
            "downloaded_minute_bars": str(DOWNLOADED_BARS_PATH),
            "batch_coverage": str(BATCH_COVERAGE_PATH),
            "request_coverage_after_download": str(REQUEST_COVERAGE_PATH),
            "stage825_coverage_after_download": str(STAGE825_COVERAGE_PATH),
            "stage825_year_coverage_after_download": str(STAGE825_YEAR_COVERAGE_PATH),
            "stage849_pressure_coverage_after_download": str(STAGE849_COVERAGE_PATH),
            "remaining_gap_requests": str(REMAINING_GAPS_PATH),
            "summary": str(SUMMARY_PATH),
            "report": str(REPORT_PATH),
            "decision": str(DECISION_PATH),
        },
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(summary, status, batch_coverage, request_coverage, stage825_year, stage849_after, decision)

    print(f"[{STAGE}] decision: {decision['decision']}")
    print(summary.to_string(index=False))
    print(f"[{STAGE}] report: {REPORT_PATH}")
    print(f"[{STAGE}] decision json: {DECISION_PATH}")


if __name__ == "__main__":
    main()
