from __future__ import annotations

from datetime import datetime, timedelta
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


LINE_ID = "futures_trend_c9_minrisk_highquality"
STAGE = "Stage113"
MODEL_TAG = "stage113_microstructure_required_window_coverage_v1"
OUTPUT_PREFIX = "qmt_roll_stage113_c9_minrisk_microstructure_required_window_coverage"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage113_microstructure_required_window_coverage"

CURVE_IN = (
    LINE_DIR
    / "outputs"
    / "stage045_event_time_field_sync_audit"
    / "qmt_roll_stage045_c9_minrisk_event_time_field_sync_audit_semantic_curve_"
    "stage045_event_time_field_sync_audit_v1.csv"
)
EVENT_LEDGER_IN = (
    LINE_DIR
    / "outputs"
    / "stage045_event_time_field_sync_audit"
    / "qmt_roll_stage045_c9_minrisk_event_time_field_sync_audit_event_sync_ledger_"
    "stage045_event_time_field_sync_audit_v1.csv"
)
FIELD_DETAIL_IN = (
    LINE_DIR
    / "outputs"
    / "stage045_event_time_field_sync_audit"
    / "qmt_roll_stage045_c9_minrisk_event_time_field_sync_audit_field_sync_detail_"
    "stage045_event_time_field_sync_audit_v1.csv"
)
RISK_MAP_IN = (
    LINE_DIR
    / "outputs"
    / "stage108_post_oi_route_reset_risk_map"
    / "qmt_roll_stage108_c9_minrisk_post_oi_route_reset_risk_map_risk_event_map_"
    "stage108_post_oi_route_reset_risk_map_v1.csv"
)
STAGE112_SUMMARY_IN = (
    LINE_DIR
    / "outputs"
    / "stage112_authorized_microstructure_data_drop_validator"
    / "qmt_roll_stage112_c9_minrisk_authorized_microstructure_data_drop_validator_summary_"
    "stage112_authorized_microstructure_data_drop_validator_v1.csv"
)

INTAKE_ROOTS = [
    LINE_DIR / "data" / "authorized_microstructure_intake",
    LINE_DIR / "inputs" / "authorized_microstructure_intake",
]
MANIFEST_NAMES = {"manifest.csv", "manifest.json", "manifest.jsonl", "manifest.ndjson", "manifest.parquet"}
DATA_SUFFIXES = {".csv", ".json", ".jsonl", ".ndjson", ".parquet"}
LOCAL_FIXTURE_MARKERS = (
    "stage131",
    "positive_drop",
    "contract_positive",
    "local_contract_positive",
    "synthetic",
    "smoke",
)

ENTRY_OPEN_TIME = "09:00:00"
ENTRY_PRE_MINUTES = 5
ENTRY_POST_MINUTES = 35
SESSION_PRE_MINUTES = 5
SESSION_GUARD_END_TIME = "15:05:00"
EVENT_PRE_SECONDS = 120
EVENT_POST_SECONDS = 120
MAX_ROWS_PER_FILE = 2_000_000

TIME_FIELD_ORDER = ["first_stop_time", "reentry_time", "retry_failed_time", "c2_hit_time"]

SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
REQUIRED_WINDOWS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_required_windows_{MODEL_TAG}.csv"
CANDIDATE_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_candidate_window_summary_{MODEL_TAG}.csv"
WINDOW_TYPE_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_window_type_summary_{MODEL_TAG}.csv"
COVERAGE_AUDIT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_coverage_audit_{MODEL_TAG}.csv"
FILE_INDEX_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_intake_file_time_index_{MODEL_TAG}.csv"
GATE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_coverage_gate_{MODEL_TAG}.csv"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_window_coverage_{MODEL_TAG}.png"
WINDOW_COUNT_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_window_count_chart_{MODEL_TAG}.png"
COVERAGE_GATE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_coverage_gate_chart_{MODEL_TAG}.png"
EVENT_HOUR_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_event_hour_chart_{MODEL_TAG}.png"


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
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
        return pd.Timestamp(value).strftime("%Y-%m-%d %H:%M:%S")
    return value


def _clean(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and pd.isna(value):
        return ""
    text = str(value).strip()
    return "" if text.lower() in {"nan", "none", "nat"} else text


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size <= 4:
        return pd.DataFrame()
    return pd.read_csv(path, encoding="utf-8-sig")


def _write_csv(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, encoding="utf-8-sig")


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_empty_"
    data = frame.head(max_rows).copy() if max_rows is not None else frame.copy()
    for column in data.columns:
        if pd.api.types.is_float_dtype(data[column]):
            data[column] = data[column].map(lambda value: "" if pd.isna(value) else f"{value:.4f}")
    lines = [
        "| " + " | ".join(str(column) for column in data.columns) + " |",
        "| " + " | ".join(["---"] * len(data.columns)) + " |",
    ]
    for _, row in data.iterrows():
        lines.append("| " + " | ".join(str(row[column]) for column in data.columns) + " |")
    return "\n".join(lines)


def _load_curve() -> pd.DataFrame:
    curve = _read_csv(CURVE_IN)
    if curve.empty:
        raise RuntimeError(f"missing curve input: {CURVE_IN}")
    curve["date"] = pd.to_datetime(curve["date"], errors="coerce").dt.normalize()
    for column in ["account_equity", "drawdown_pct", "broker10_margin_to_equity_pct"]:
        curve[column] = pd.to_numeric(curve[column], errors="coerce")
    return curve[curve["date"].notna()].sort_values("date").reset_index(drop=True)


def _nearest_curve_points(curve: pd.DataFrame, dates: pd.Series) -> pd.DataFrame:
    left = pd.DataFrame({"event_date": pd.to_datetime(dates, errors="coerce").dt.normalize()}).dropna()
    right = curve[["date", "account_equity", "drawdown_pct", "broker10_margin_to_equity_pct"]].sort_values("date")
    return pd.merge_asof(left.sort_values("event_date"), right, left_on="event_date", right_on="date", direction="backward")


def _date_time(date_value: Any, time_text: str) -> pd.Timestamp:
    date = pd.to_datetime(date_value, errors="coerce")
    if pd.isna(date):
        return pd.NaT
    return pd.to_datetime(f"{date.date()} {time_text}", errors="coerce")


def _required_schema_policy(row: pd.Series, window_type: str) -> str:
    if int(pd.to_numeric(row.get("orderflow_required", 0), errors="coerce") or 0) == 1:
        return "mbo_l3_preferred_mbp10_minimum"
    if window_type in {"event_touch_window", "session_no_event_guard"}:
        return "mbp10_minimum_mbo_accepted"
    return "mbp10_or_mbo"


def _build_required_windows() -> pd.DataFrame:
    risk = _read_csv(RISK_MAP_IN)
    ledger = _read_csv(EVENT_LEDGER_IN)
    detail = _read_csv(FIELD_DETAIL_IN)
    if risk.empty or ledger.empty:
        raise RuntimeError("missing Stage045/108 inputs")
    detail = detail[detail["check_type"].eq("time")].copy()
    detail["anchor_time"] = pd.to_datetime(detail["source_value"], errors="coerce")
    detail = detail[detail["field_name"].isin(TIME_FIELD_ORDER) & detail["anchor_time"].notna()]
    merged = risk.merge(
        ledger[
            [
                "candidate_index",
                "official_open_trade_id",
                "official_event_family",
                "replay_event_family",
                "full_event_sync_exact",
                "stage042_session_convention_status",
                "source_exit_reason",
                "source_note",
            ]
        ],
        on="candidate_index",
        how="left",
    )
    rows: list[dict[str, Any]] = []
    for _, row in merged.iterrows():
        open_anchor = _date_time(row["official_open_date"], ENTRY_OPEN_TIME)
        if pd.isna(open_anchor):
            continue
        entry_start = open_anchor - pd.Timedelta(minutes=ENTRY_PRE_MINUTES)
        entry_end = open_anchor + pd.Timedelta(minutes=ENTRY_POST_MINUTES)
        priority = int(row.get("right_tail_visual", 0) or row.get("bottom_loss_visual", 0) or row.get("maxdd_context", 0))
        base = {
            "candidate_index": int(row["candidate_index"]),
            "official_open_trade_id": _clean(row.get("official_open_trade_id")),
            "vt_symbol": _clean(row["vt_symbol"]),
            "direction": _clean(row["direction"]),
            "official_open_date": _clean(row["official_open_date"]),
            "official_event_family": _clean(row.get("official_event_family")),
            "risk_route_label": _clean(row.get("risk_route_label")),
            "right_tail_visual": int(row.get("right_tail_visual", 0)),
            "bottom_loss_visual": int(row.get("bottom_loss_visual", 0)),
            "maxdd_context": int(row.get("maxdd_context", 0)),
            "visual_priority": priority,
            "orderflow_required": int(row.get("orderflow_required", 0)),
            "low_resolution_zone": int(row.get("low_resolution_zone", 0)),
            "order_realized_pnl": float(pd.to_numeric(row.get("order_realized_pnl", 0), errors="coerce") or 0),
            "required_schema_policy": _required_schema_policy(row, "entry_quality_window"),
            "must_cover_for_promotion": 1,
        }
        rows.append(
            {
                **base,
                "window_id": f"{int(row['candidate_index'])}_entry_quality",
                "window_type": "entry_quality_window",
                "anchor_field": "official_open_09_00",
                "anchor_time": open_anchor,
                "window_start": entry_start,
                "window_end": entry_end,
                "window_seconds": int((entry_end - entry_start).total_seconds()),
                "coverage_rule": "manifest_span_covers_window_and_sequence_gap_zero",
                "why": "Initial-entry quality/min-risk research must have pre-open and first-30m microstructure coverage.",
            }
        )
        if _clean(row.get("official_event_family")) == "no_intraday_event":
            session_start = open_anchor - pd.Timedelta(minutes=SESSION_PRE_MINUTES)
            session_end = _date_time(row["official_open_date"], SESSION_GUARD_END_TIME)
            rows.append(
                {
                    **base,
                    "required_schema_policy": _required_schema_policy(row, "session_no_event_guard"),
                    "window_id": f"{int(row['candidate_index'])}_session_guard",
                    "window_type": "session_no_event_guard",
                    "anchor_field": "no_intraday_event_day_guard",
                    "anchor_time": open_anchor,
                    "window_start": session_start,
                    "window_end": session_end,
                    "window_seconds": int((session_end - session_start).total_seconds()),
                    "coverage_rule": "manifest_span_covers_window_and_sequence_gap_zero",
                    "why": "No-event samples need session coverage so missing data cannot masquerade as no touch.",
                }
            )

    if not detail.empty:
        risk_cols = [
            "candidate_index",
            "orderflow_required",
            "low_resolution_zone",
            "right_tail_visual",
            "bottom_loss_visual",
            "maxdd_context",
            "order_realized_pnl",
            "risk_route_label",
        ]
        event_detail = detail.merge(risk[risk_cols], on="candidate_index", how="left")
        for _, event in event_detail.iterrows():
            anchor = pd.Timestamp(event["anchor_time"])
            start = anchor - pd.Timedelta(seconds=EVENT_PRE_SECONDS)
            end = anchor + pd.Timedelta(seconds=EVENT_POST_SECONDS)
            priority = int(event.get("right_tail_visual", 0) or event.get("bottom_loss_visual", 0) or event.get("maxdd_context", 0))
            event_row = event.to_dict()
            rows.append(
                {
                    "candidate_index": int(event["candidate_index"]),
                    "official_open_trade_id": _clean(event.get("official_open_trade_id")),
                    "vt_symbol": _clean(event["vt_symbol"]),
                    "direction": _clean(event["direction"]),
                    "official_open_date": _clean(event["official_open_date"]),
                    "official_event_family": _clean(event.get("official_event_family")),
                    "risk_route_label": _clean(event.get("risk_route_label")),
                    "right_tail_visual": int(event.get("right_tail_visual", 0)),
                    "bottom_loss_visual": int(event.get("bottom_loss_visual", 0)),
                    "maxdd_context": int(event.get("maxdd_context", 0)),
                    "visual_priority": priority,
                    "orderflow_required": int(event.get("orderflow_required", 0)),
                    "low_resolution_zone": int(event.get("low_resolution_zone", 0)),
                    "order_realized_pnl": float(pd.to_numeric(event.get("order_realized_pnl", 0), errors="coerce") or 0),
                    "required_schema_policy": _required_schema_policy(pd.Series(event_row), "event_touch_window"),
                    "must_cover_for_promotion": 1,
                    "window_id": f"{int(event['candidate_index'])}_{_clean(event['field_name'])}",
                    "window_type": "event_touch_window",
                    "anchor_field": _clean(event["field_name"]),
                    "anchor_time": anchor,
                    "window_start": start,
                    "window_end": end,
                    "window_seconds": int((end - start).total_seconds()),
                    "coverage_rule": "manifest_span_covers_window_and_sequence_gap_zero",
                    "why": "Touch/retry/C2 event windows need quote/depth to resolve intrabar path and execution feasibility.",
                }
            )
    windows = pd.DataFrame(rows)
    for column in ["anchor_time", "window_start", "window_end"]:
        windows[column] = pd.to_datetime(windows[column], errors="coerce")
    windows = windows.sort_values(["candidate_index", "window_type", "anchor_time", "anchor_field"]).reset_index(drop=True)
    return windows


def _read_json_rows(path: Path, max_rows: int = 200) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    if path.suffix.lower() in {".jsonl", ".ndjson"}:
        rows = []
        for line in text.splitlines()[:max_rows]:
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(item, dict):
                rows.append(item)
        return rows
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return []
    if isinstance(data, list):
        return [item for item in data[:max_rows] if isinstance(item, dict)]
    if isinstance(data, dict):
        rows = data.get("rows")
        if isinstance(rows, list):
            return [item for item in rows[:max_rows] if isinstance(item, dict)]
        return [data]
    return []


def _read_manifest(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return _read_csv(path)
    if suffix in {".json", ".jsonl", ".ndjson"}:
        return pd.DataFrame(_read_json_rows(path, max_rows=10000))
    if suffix == ".parquet":
        try:
            return pd.read_parquet(path)
        except Exception:
            return pd.DataFrame()
    return pd.DataFrame()


def _first_nonempty(row: pd.Series, names: list[str]) -> str:
    lower = {str(column).lower(): column for column in row.index}
    for name in names:
        column = lower.get(name.lower())
        if column is None:
            continue
        value = _clean(row.get(column))
        if value:
            return value
    return ""


def _resolve_path(root: Path, value: Any) -> Path | None:
    text = _clean(value)
    if not text:
        return None
    path = Path(text)
    return path if path.is_absolute() else root / path


def _fixture_source_marker(values: list[Any]) -> str:
    joined = " ".join(_clean(value).lower() for value in values if _clean(value))
    for marker in LOCAL_FIXTURE_MARKERS:
        if marker in joined:
            return marker
    return ""


def _time_column(columns: list[str]) -> str:
    lowered = {column.lower(): column for column in columns}
    for name in ["ts_event", "exchange_timestamp", "datetime", "timestamp", "time"]:
        if name in lowered:
            return lowered[name]
    return ""


def _symbol_column(columns: list[str]) -> str:
    lowered = {column.lower(): column for column in columns}
    for name in ["vt_symbol", "instrument_id", "symbol", "contract"]:
        if name in lowered:
            return lowered[name]
    return ""


def _read_data_file_index(data_path: Path) -> dict[str, Any]:
    suffix = data_path.suffix.lower()
    columns: list[str] = []
    row_count = 0
    rows_loaded = 0
    min_ts = pd.NaT
    max_ts = pd.NaT
    symbols: list[str] = []
    read_error = ""
    frame = pd.DataFrame()
    try:
        if suffix == ".csv":
            header = pd.read_csv(data_path, nrows=0, encoding="utf-8-sig")
            columns = list(header.columns)
            usecols = [column for column in [_time_column(columns), _symbol_column(columns)] if column]
            if usecols:
                frame = pd.read_csv(data_path, usecols=usecols, nrows=MAX_ROWS_PER_FILE, encoding="utf-8-sig")
            row_count = sum(1 for _ in data_path.open("rb")) - 1
        elif suffix in {".json", ".jsonl", ".ndjson"}:
            rows = _read_json_rows(data_path, max_rows=MAX_ROWS_PER_FILE)
            frame = pd.DataFrame(rows)
            columns = list(frame.columns)
            row_count = len(frame)
        elif suffix == ".parquet":
            try:
                import pyarrow.parquet as pq  # type: ignore

                parquet_file = pq.ParquetFile(data_path)
                columns = list(parquet_file.schema_arrow.names)
                time_col = _time_column(columns)
                symbol_col = _symbol_column(columns)
                usecols = [column for column in [time_col, symbol_col] if column]
                row_count = int(parquet_file.metadata.num_rows) if parquet_file.metadata else 0
                if usecols and row_count <= MAX_ROWS_PER_FILE:
                    frame = pd.read_parquet(data_path, columns=usecols)
                elif usecols:
                    frame = pd.read_parquet(data_path, columns=usecols).head(MAX_ROWS_PER_FILE)
            except Exception as exc:
                read_error = f"parquet_index_error:{exc.__class__.__name__}"
        else:
            read_error = "unsupported_suffix"
    except Exception as exc:
        read_error = f"read_error:{exc.__class__.__name__}"

    if not frame.empty:
        rows_loaded = len(frame)
        time_col = _time_column(list(frame.columns))
        symbol_col = _symbol_column(list(frame.columns))
        if time_col:
            times = pd.to_datetime(frame[time_col], errors="coerce")
            if times.notna().any():
                min_ts = times.min()
                max_ts = times.max()
        if symbol_col:
            symbols = sorted({_clean(value) for value in frame[symbol_col].dropna().tolist() if _clean(value)})[:200]
    return {
        "file_path": str(data_path),
        "file_suffix": suffix,
        "file_exists": int(data_path.exists()),
        "file_bytes": int(data_path.stat().st_size) if data_path.exists() else 0,
        "row_count_estimate": max(row_count, rows_loaded),
        "rows_loaded_for_index": rows_loaded,
        "column_count": len(columns),
        "time_column": _time_column(columns),
        "symbol_column": _symbol_column(columns),
        "min_ts": min_ts,
        "max_ts": max_ts,
        "symbol_count_sample": len(symbols),
        "symbols_sample": ";".join(symbols[:50]),
        "read_error": read_error,
    }


def _scan_intake_files() -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for root in INTAKE_ROOTS:
        if not root.exists():
            rows.append(
                {
                    "root_path": str(root),
                    "manifest_path": "",
                    "data_file": "",
                    "manifest_row_index": "",
                    "file_exists": 0,
                    "file_bytes": 0,
                    "row_count_estimate": 0,
                    "rows_loaded_for_index": 0,
                    "column_count": 0,
                    "time_column": "",
                    "symbol_column": "",
                    "min_ts": "",
                    "max_ts": "",
                    "symbol_count_sample": 0,
                    "symbols_sample": "",
                    "manifest_start_ts": "",
                    "manifest_end_ts": "",
                    "sequence_gap_count": "",
                    "coverage_proof": "",
                    "read_error": "root_missing",
                }
            )
            continue
        all_files = sorted([path for path in root.rglob("*") if path.is_file()])
        manifest_files = [path for path in all_files if path.name.lower() in MANIFEST_NAMES]
        if not manifest_files:
            rows.append(
                {
                    "root_path": str(root),
                    "manifest_path": "",
                    "data_file": "",
                    "manifest_row_index": "",
                    "file_exists": 0,
                    "file_bytes": 0,
                    "row_count_estimate": 0,
                    "rows_loaded_for_index": 0,
                    "column_count": 0,
                    "time_column": "",
                    "symbol_column": "",
                    "min_ts": "",
                    "max_ts": "",
                    "symbol_count_sample": 0,
                    "symbols_sample": "",
                    "manifest_start_ts": "",
                    "manifest_end_ts": "",
                    "sequence_gap_count": "",
                    "coverage_proof": "",
                    "read_error": "manifest_missing",
                }
            )
            continue
        for manifest_path in manifest_files:
            manifest = _read_manifest(manifest_path)
            for index, manifest_row in manifest.iterrows():
                data_path = _resolve_path(
                    root, _first_nonempty(manifest_row, ["data_file", "data_path", "file", "path", "relative_path"])
                )
                manifest_start_ts = _first_nonempty(manifest_row, ["start_ts", "start_time", "from_ts"])
                manifest_end_ts = _first_nonempty(manifest_row, ["end_ts", "end_time", "to_ts"])
                sequence_gap_count = _first_nonempty(manifest_row, ["sequence_gap_count", "gap_count", "seq_gap_count"])
                coverage_proof = _first_nonempty(manifest_row, ["coverage_proof", "capture_proof", "sequence_proof"])
                source_marker = _fixture_source_marker(
                    [
                        manifest_path,
                        data_path,
                        _first_nonempty(manifest_row, ["raw_file", "raw_path", "source_raw_file"]),
                        _first_nonempty(manifest_row, ["dataset_id", "dataset", "data_set"]),
                        _first_nonempty(manifest_row, ["source_vendor", "vendor", "source", "provider"]),
                        _first_nonempty(manifest_row, ["notes", "comment", "description"]),
                        coverage_proof,
                    ]
                )
                if source_marker:
                    rows.append(
                        {
                            "root_path": str(root),
                            "manifest_path": str(manifest_path),
                            "data_file": str(data_path) if data_path is not None else "",
                            "manifest_row_index": int(index),
                            "file_exists": 0,
                            "file_bytes": 0,
                            "row_count_estimate": 0,
                            "rows_loaded_for_index": 0,
                            "column_count": 0,
                            "time_column": "",
                            "symbol_column": "",
                            "min_ts": "",
                            "max_ts": "",
                            "symbol_count_sample": 0,
                            "symbols_sample": "",
                            "manifest_start_ts": manifest_start_ts,
                            "manifest_end_ts": manifest_end_ts,
                            "sequence_gap_count": sequence_gap_count,
                            "coverage_proof": coverage_proof,
                            "read_error": f"blocked_local_fixture_marker:{source_marker}",
                        }
                    )
                    continue
                if data_path is None or not data_path.exists():
                    rows.append(
                        {
                            "root_path": str(root),
                            "manifest_path": str(manifest_path),
                            "data_file": str(data_path) if data_path is not None else "",
                            "manifest_row_index": int(index),
                            "file_exists": 0,
                            "file_bytes": 0,
                            "row_count_estimate": 0,
                            "rows_loaded_for_index": 0,
                            "column_count": 0,
                            "time_column": "",
                            "symbol_column": "",
                            "min_ts": "",
                            "max_ts": "",
                            "symbol_count_sample": 0,
                            "symbols_sample": "",
                            "manifest_start_ts": manifest_start_ts,
                            "manifest_end_ts": manifest_end_ts,
                            "sequence_gap_count": sequence_gap_count,
                            "coverage_proof": coverage_proof,
                            "read_error": "data_file_missing",
                        }
                    )
                    continue
                info = _read_data_file_index(data_path)
                rows.append(
                    {
                        "root_path": str(root),
                        "manifest_path": str(manifest_path),
                        "data_file": str(data_path),
                        "manifest_row_index": int(index),
                        **info,
                        "manifest_start_ts": manifest_start_ts,
                        "manifest_end_ts": manifest_end_ts,
                        "sequence_gap_count": sequence_gap_count,
                        "coverage_proof": coverage_proof,
                    }
                )
    return pd.DataFrame(rows)


def _manifest_span_covers(file_row: pd.Series, start: pd.Timestamp, end: pd.Timestamp) -> int:
    start_decl = pd.to_datetime(file_row.get("manifest_start_ts"), errors="coerce")
    end_decl = pd.to_datetime(file_row.get("manifest_end_ts"), errors="coerce")
    min_ts = pd.to_datetime(file_row.get("min_ts"), errors="coerce")
    max_ts = pd.to_datetime(file_row.get("max_ts"), errors="coerce")
    declared = int(pd.notna(start_decl) and pd.notna(end_decl) and start_decl <= start and end_decl >= end)
    observed = int(pd.notna(min_ts) and pd.notna(max_ts) and min_ts <= start and max_ts >= end)
    return int(declared and observed)


def _sequence_gap_zero(file_row: pd.Series) -> int:
    value = _clean(file_row.get("sequence_gap_count"))
    if not value:
        return 0
    numeric = pd.to_numeric(value, errors="coerce")
    return int(pd.notna(numeric) and float(numeric) == 0.0)


def _coverage_audit(windows: pd.DataFrame, file_index: pd.DataFrame) -> pd.DataFrame:
    if file_index.empty:
        file_index = pd.DataFrame()
    file_rows = []
    valid_files = file_index[file_index.get("file_exists", pd.Series(dtype=int)).eq(1)].copy() if not file_index.empty else pd.DataFrame()
    for _, window in windows.iterrows():
        start = pd.Timestamp(window["window_start"])
        end = pd.Timestamp(window["window_end"])
        vt_symbol = _clean(window["vt_symbol"])
        matched_file = ""
        span_cover = 0
        sequence_ok = 0
        symbol_cover = 0
        if not valid_files.empty:
            for _, file_row in valid_files.iterrows():
                symbols = _clean(file_row.get("symbols_sample"))
                symbol_cover = int(vt_symbol in set(symbols.split(";"))) if symbols else 0
                span_cover = _manifest_span_covers(file_row, start, end)
                sequence_ok = _sequence_gap_zero(file_row)
                if symbol_cover and span_cover and sequence_ok:
                    matched_file = _clean(file_row.get("data_file"))
                    break
        pass_now = int(bool(matched_file))
        blockers = []
        if not matched_file:
            if valid_files.empty:
                blockers.append("no_authorized_data_file_index")
            else:
                if symbol_cover == 0:
                    blockers.append("symbol_not_indexed")
                if span_cover == 0:
                    blockers.append("window_not_span_covered")
                if sequence_ok == 0:
                    blockers.append("sequence_gap_proof_missing_or_nonzero")
        file_rows.append(
            {
                "window_id": window["window_id"],
                "candidate_index": int(window["candidate_index"]),
                "vt_symbol": vt_symbol,
                "window_type": window["window_type"],
                "anchor_field": window["anchor_field"],
                "window_start": start,
                "window_end": end,
                "right_tail_visual": int(window["right_tail_visual"]),
                "bottom_loss_visual": int(window["bottom_loss_visual"]),
                "maxdd_context": int(window["maxdd_context"]),
                "visual_priority": int(window["visual_priority"]),
                "required_schema_policy": window["required_schema_policy"],
                "matched_data_file": matched_file,
                "coverage_pass": pass_now,
                "blockers": ";".join(blockers),
            }
        )
    return pd.DataFrame(file_rows)


def _candidate_summary(windows: pd.DataFrame, coverage: pd.DataFrame) -> pd.DataFrame:
    win = windows.groupby("candidate_index", as_index=False).agg(
        vt_symbol=("vt_symbol", "first"),
        official_open_date=("official_open_date", "first"),
        direction=("direction", "first"),
        official_event_family=("official_event_family", "first"),
        required_window_count=("window_id", "count"),
        right_tail_visual=("right_tail_visual", "max"),
        bottom_loss_visual=("bottom_loss_visual", "max"),
        maxdd_context=("maxdd_context", "max"),
        visual_priority=("visual_priority", "max"),
        orderflow_required=("orderflow_required", "max"),
        order_realized_pnl=("order_realized_pnl", "first"),
    )
    cov = coverage.groupby("candidate_index", as_index=False).agg(covered_window_count=("coverage_pass", "sum"))
    summary = win.merge(cov, on="candidate_index", how="left")
    summary["covered_window_count"] = pd.to_numeric(summary["covered_window_count"], errors="coerce").fillna(0).astype(int)
    summary["candidate_coverage_pass"] = summary["covered_window_count"].eq(summary["required_window_count"]).astype(int)
    summary["coverage_rate_pct"] = np.where(
        summary["required_window_count"].gt(0),
        summary["covered_window_count"] / summary["required_window_count"] * 100.0,
        0.0,
    )
    return summary.sort_values(["visual_priority", "official_open_date", "candidate_index"], ascending=[False, True, True])


def _window_type_summary(windows: pd.DataFrame, coverage: pd.DataFrame) -> pd.DataFrame:
    data = windows.merge(coverage[["window_id", "coverage_pass"]], on="window_id", how="left")
    data["coverage_pass"] = pd.to_numeric(data["coverage_pass"], errors="coerce").fillna(0).astype(int)
    return (
        data.groupby("window_type", as_index=False)
        .agg(
            required_window_count=("window_id", "count"),
            covered_window_count=("coverage_pass", "sum"),
            visual_priority_window_count=("visual_priority", "sum"),
            right_tail_window_count=("right_tail_visual", "sum"),
            bottom_loss_window_count=("bottom_loss_visual", "sum"),
            maxdd_window_count=("maxdd_context", "sum"),
        )
        .assign(coverage_rate_pct=lambda frame: np.where(frame["required_window_count"].gt(0), frame["covered_window_count"] / frame["required_window_count"] * 100.0, 0.0))
    )


def _coverage_gate(windows: pd.DataFrame, candidate_summary: pd.DataFrame, coverage: pd.DataFrame, file_index: pd.DataFrame) -> pd.DataFrame:
    required_windows = len(windows)
    covered_windows = int(pd.to_numeric(coverage.get("coverage_pass", 0), errors="coerce").fillna(0).sum()) if not coverage.empty else 0
    required_candidates = int(candidate_summary["candidate_index"].nunique()) if not candidate_summary.empty else 0
    covered_candidates = int(pd.to_numeric(candidate_summary.get("candidate_coverage_pass", 0), errors="coerce").fillna(0).sum()) if not candidate_summary.empty else 0
    visual_required = int(windows[windows["visual_priority"].eq(1)]["window_id"].nunique())
    visual_covered = int(coverage[coverage["visual_priority"].eq(1)]["coverage_pass"].sum()) if not coverage.empty else 0
    right_tail_required = int(windows[windows["right_tail_visual"].eq(1)]["window_id"].nunique())
    right_tail_covered = int(coverage[coverage["right_tail_visual"].eq(1)]["coverage_pass"].sum()) if not coverage.empty else 0
    bottom_required = int(windows[windows["bottom_loss_visual"].eq(1)]["window_id"].nunique())
    bottom_covered = int(coverage[coverage["bottom_loss_visual"].eq(1)]["coverage_pass"].sum()) if not coverage.empty else 0
    maxdd_required = int(windows[windows["maxdd_context"].eq(1)]["window_id"].nunique())
    maxdd_covered = int(coverage[coverage["maxdd_context"].eq(1)]["coverage_pass"].sum()) if not coverage.empty else 0
    indexed_files = int(file_index.get("file_exists", pd.Series(dtype=int)).eq(1).sum()) if not file_index.empty else 0
    rows = [
        {
            "gate_id": "authorized_file_index_present",
            "observed": str(indexed_files),
            "required": ">=1 indexed authorized data file",
            "pass_now": int(indexed_files > 0),
            "severity": "hard",
        },
        {
            "gate_id": "all_required_windows_covered",
            "observed": f"{covered_windows}/{required_windows}",
            "required": f"{required_windows}/{required_windows}",
            "pass_now": int(required_windows > 0 and covered_windows == required_windows),
            "severity": "hard",
        },
        {
            "gate_id": "all_candidates_covered",
            "observed": f"{covered_candidates}/{required_candidates}",
            "required": f"{required_candidates}/{required_candidates}",
            "pass_now": int(required_candidates > 0 and covered_candidates == required_candidates),
            "severity": "hard",
        },
        {
            "gate_id": "visual_priority_windows_covered",
            "observed": f"{visual_covered}/{visual_required}",
            "required": f"{visual_required}/{visual_required}",
            "pass_now": int(visual_required > 0 and visual_covered == visual_required),
            "severity": "hard",
        },
        {
            "gate_id": "right_tail_windows_covered",
            "observed": f"{right_tail_covered}/{right_tail_required}",
            "required": f"{right_tail_required}/{right_tail_required}",
            "pass_now": int(right_tail_required > 0 and right_tail_covered == right_tail_required),
            "severity": "hard",
        },
        {
            "gate_id": "bottom_loss_windows_covered",
            "observed": f"{bottom_covered}/{bottom_required}",
            "required": f"{bottom_required}/{bottom_required}",
            "pass_now": int(bottom_required > 0 and bottom_covered == bottom_required),
            "severity": "hard",
        },
        {
            "gate_id": "maxdd_context_windows_covered",
            "observed": f"{maxdd_covered}/{maxdd_required}",
            "required": f"{maxdd_required}/{maxdd_required}",
            "pass_now": int(maxdd_required > 0 and maxdd_covered == maxdd_required),
            "severity": "hard",
        },
    ]
    return pd.DataFrame(rows)


def _summary(
    windows: pd.DataFrame,
    candidate_summary: pd.DataFrame,
    window_type_summary: pd.DataFrame,
    file_index: pd.DataFrame,
    coverage: pd.DataFrame,
    gate: pd.DataFrame,
) -> pd.DataFrame:
    stage112 = _read_csv(STAGE112_SUMMARY_IN)
    stage112_row = stage112.iloc[0] if not stage112.empty else pd.Series(dtype=object)
    indexed_files = int(file_index.get("file_exists", pd.Series(dtype=int)).eq(1).sum()) if not file_index.empty else 0
    return pd.DataFrame(
        [
            {
                "stage": STAGE,
                "model_tag": MODEL_TAG,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "line_id": LINE_ID,
                "decision": "stage113_required_window_manifest_built_no_authorized_data_no_rule",
                "official_config_changed": 0,
                "strategy_rule_created": 0,
                "true_engine_run": 0,
                "ab_triggered": 0,
                "order_api_called": 0,
                "ctp_connected": 0,
                "required_candidate_count": int(candidate_summary["candidate_index"].nunique()) if not candidate_summary.empty else 0,
                "required_window_count": int(len(windows)),
                "entry_quality_window_count": int(windows["window_type"].eq("entry_quality_window").sum()) if not windows.empty else 0,
                "event_touch_window_count": int(windows["window_type"].eq("event_touch_window").sum()) if not windows.empty else 0,
                "session_no_event_guard_window_count": int(windows["window_type"].eq("session_no_event_guard").sum()) if not windows.empty else 0,
                "visual_priority_window_count": int(windows["visual_priority"].sum()) if not windows.empty else 0,
                "right_tail_window_count": int(windows["right_tail_visual"].sum()) if not windows.empty else 0,
                "bottom_loss_window_count": int(windows["bottom_loss_visual"].sum()) if not windows.empty else 0,
                "maxdd_context_window_count": int(windows["maxdd_context"].sum()) if not windows.empty else 0,
                "indexed_authorized_data_file_count": indexed_files,
                "covered_window_count": int(coverage["coverage_pass"].sum()) if not coverage.empty else 0,
                "covered_candidate_count": int(candidate_summary["candidate_coverage_pass"].sum()) if not candidate_summary.empty else 0,
                "coverage_gate_count": int(len(gate)),
                "coverage_gate_pass_count": int(gate["pass_now"].sum()) if not gate.empty else 0,
                "stage112_rule_ready_data_file_count": int(stage112_row.get("rule_ready_data_file_count", 0) or 0),
                "next_recommended_route": "drop_authorized_mbo_or_mbp10_package_then_verify_required_windows_before_rule_preflight",
                "true_engine_allowed": 0,
                "strategy_feature_usable": 0,
                "end_equity": float(stage112_row.get("end_equity", 0) or 0),
                "total_return_pct": float(stage112_row.get("total_return_pct", 0) or 0),
                "max_drawdown_pct": float(stage112_row.get("max_drawdown_pct", 0) or 0),
                "sharpe": float(stage112_row.get("sharpe", 0) or 0),
                "total_slippage": float(stage112_row.get("total_slippage", 0) or 0),
                "total_trade_count": float(stage112_row.get("total_trade_count", 0) or 0),
                "closed_lot_win_rate_pct": float(stage112_row.get("closed_lot_win_rate_pct", 0) or 0),
                "max_broker10_margin_to_equity_pct": float(stage112_row.get("max_broker10_margin_to_equity_pct", 0) or 0),
            }
        ]
    )


def _plot_path(curve: pd.DataFrame, windows: pd.DataFrame, candidate_summary: pd.DataFrame) -> None:
    points = _nearest_curve_points(curve, pd.to_datetime(candidate_summary["official_open_date"], errors="coerce")).reset_index(drop=True)
    data = candidate_summary.sort_values("official_open_date").reset_index(drop=True)
    if len(data) == len(points):
        data = pd.concat([data, points[["account_equity", "drawdown_pct", "broker10_margin_to_equity_pct"]]], axis=1)
    fig, axes = plt.subplots(3, 1, figsize=(15, 10), sharex=True)
    axes[0].plot(curve["date"], curve["account_equity"] / 1_000_000, color="#111827", lw=1.2)
    axes[1].plot(curve["date"], curve["drawdown_pct"], color="#b91c1c", lw=1.0)
    axes[2].plot(curve["date"], curve["broker10_margin_to_equity_pct"], color="#0369a1", lw=1.0)
    axes[2].axhline(100, color="#991b1b", ls="--", lw=0.8)
    if not data.empty:
        data["official_open_date"] = pd.to_datetime(data["official_open_date"], errors="coerce")
        colors = np.where(data["candidate_coverage_pass"].eq(1), "#16a34a", "#dc2626")
        sizes = np.where(data["visual_priority"].eq(1), 72, 30)
        for ax, column, scale in [
            (axes[0], "account_equity", 1_000_000),
            (axes[1], "drawdown_pct", 1),
            (axes[2], "broker10_margin_to_equity_pct", 1),
        ]:
            ax.scatter(
                data["official_open_date"],
                data[column] / scale,
                s=sizes,
                c=colors,
                edgecolors="#111827",
                linewidths=0.4,
                alpha=0.78,
            )
    axes[0].set_title("Stage113 official path: required microstructure windows exist, coverage remains zero")
    axes[0].set_ylabel("equity (m)")
    axes[1].set_ylabel("drawdown %")
    axes[2].set_ylabel("broker10 %")
    for ax in axes:
        ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(PATH_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_window_counts(window_type_summary: pd.DataFrame) -> None:
    data = window_type_summary.sort_values("required_window_count", ascending=False)
    fig, ax = plt.subplots(figsize=(11, 5.5))
    x = np.arange(len(data))
    ax.bar(x - 0.18, data["required_window_count"], width=0.36, color="#64748b", label="required")
    ax.bar(x + 0.18, data["covered_window_count"], width=0.36, color="#dc2626", label="covered")
    ax.set_xticks(x)
    ax.set_xticklabels(data["window_type"], rotation=18, ha="right")
    ax.set_ylabel("window count")
    ax.set_title("Stage113 required windows by type; authorized coverage is zero")
    ax.legend(fontsize=8)
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(WINDOW_COUNT_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_coverage_gate(gate: pd.DataFrame) -> None:
    data = gate.copy()
    data["blocked"] = 1 - pd.to_numeric(data["pass_now"], errors="coerce").fillna(0)
    fig, ax = plt.subplots(figsize=(12, max(4.8, 0.5 * len(data))))
    colors = np.where(data["blocked"].eq(1), "#dc2626", "#16a34a")
    ax.barh(data["gate_id"], data["blocked"], color=colors, alpha=0.88)
    ax.set_xlim(0, 1.05)
    ax.set_xlabel("blocked now")
    ax.set_title("Stage113 required-window coverage gates before rule preflight")
    for y, row in enumerate(data.itertuples(index=False)):
        ax.text(0.03, y, str(row.observed), color="white", va="center", fontsize=8)
    fig.tight_layout()
    fig.savefig(COVERAGE_GATE_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_event_hours(windows: pd.DataFrame) -> None:
    data = windows[windows["window_type"].eq("event_touch_window")].copy()
    if data.empty:
        fig, ax = plt.subplots(figsize=(9, 4))
        ax.text(0.5, 0.5, "No event touch windows", ha="center", va="center")
        ax.axis("off")
        fig.savefig(EVENT_HOUR_CHART_OUT, dpi=160)
        plt.close(fig)
        return
    data["hour"] = pd.to_datetime(data["anchor_time"], errors="coerce").dt.hour
    pivot = data.pivot_table(index="anchor_field", columns="hour", values="window_id", aggfunc="count", fill_value=0)
    fig, ax = plt.subplots(figsize=(12, max(3.5, 0.6 * len(pivot))))
    im = ax.imshow(pivot.to_numpy(), aspect="auto", cmap="Blues")
    ax.set_yticks(np.arange(len(pivot.index)))
    ax.set_yticklabels(pivot.index)
    ax.set_xticks(np.arange(len(pivot.columns)))
    ax.set_xticklabels([str(col) for col in pivot.columns])
    ax.set_xlabel("hour")
    ax.set_title("Stage113 event-touch window distribution by anchor field and hour")
    for y in range(len(pivot.index)):
        for x in range(len(pivot.columns)):
            value = int(pivot.iloc[y, x])
            if value:
                ax.text(x, y, str(value), ha="center", va="center", color="#111827", fontsize=8)
    fig.colorbar(im, ax=ax, fraction=0.025, pad=0.02)
    fig.tight_layout()
    fig.savefig(EVENT_HOUR_CHART_OUT, dpi=160)
    plt.close(fig)


def _write_report(
    summary: pd.DataFrame,
    windows: pd.DataFrame,
    candidate_summary: pd.DataFrame,
    window_type_summary: pd.DataFrame,
    file_index: pd.DataFrame,
    coverage: pd.DataFrame,
    gate: pd.DataFrame,
) -> None:
    row = summary.iloc[0]
    lines = [
        "# Stage113 microstructure required window coverage",
        "",
        "## Decision",
        "",
        f"- decision: `{row['decision']}`",
        "- nature: read-only required-window manifest and coverage verifier; no strategy rule, no true engine, no A/B, no CTP connection, no order API.",
        "- question: can Stage112 coverage be converted from self-reported manifest totals into event-window evidence before any rule preflight?",
        "",
        "## Baseline Path",
        "",
        f"- end equity: `{row['end_equity']:,.2f}`",
        f"- total return: `{row['total_return_pct']:.4f}%`",
        f"- max drawdown: `{row['max_drawdown_pct']:.4f}%`",
        f"- Sharpe: `{row['sharpe']:.4f}`",
        f"- total slippage: `{row['total_slippage']:,.0f}`",
        f"- total trade count: `{row['total_trade_count']:.0f}`",
        f"- closed lot win rate: `{row['closed_lot_win_rate_pct']:.4f}%`",
        "",
        "## Key Metrics",
        "",
        _md_table(summary),
        "",
        "## Window Type Summary",
        "",
        _md_table(window_type_summary, max_rows=20),
        "",
        "## Coverage Gates",
        "",
        _md_table(gate, max_rows=20),
        "",
        "## Candidate Coverage Sample",
        "",
        _md_table(
            candidate_summary[
                [
                    "candidate_index",
                    "vt_symbol",
                    "official_open_date",
                    "official_event_family",
                    "required_window_count",
                    "covered_window_count",
                    "right_tail_visual",
                    "bottom_loss_visual",
                    "maxdd_context",
                    "candidate_coverage_pass",
                ]
            ],
            max_rows=25,
        ),
        "",
        "## Intake File Index",
        "",
        _md_table(file_index, max_rows=20),
        "",
        "## Visual Outputs",
        "",
        f"- official path window coverage: `{PATH_CHART_OUT}`",
        f"- window count chart: `{WINDOW_COUNT_CHART_OUT}`",
        f"- coverage gate chart: `{COVERAGE_GATE_CHART_OUT}`",
        f"- event hour chart: `{EVENT_HOUR_CHART_OUT}`",
        "",
        "## External Research Judgment",
        "",
        (
            "MBO/ITCH/MDP-style data requires timestamp and sequence/order-event continuity to reconstruct a book; "
            "MBP-10 can support top-depth replay only if the vendor package proves window-level capture continuity. "
            "Therefore Stage113 requires each C9 event window to be covered by source span plus zero sequence gaps, "
            "not merely by a manifest-level coverage percentage."
        ),
        "",
        "## Judgment",
        "",
        (
            "Stage113 turns the Stage112 coverage target into concrete required windows. The current result remains "
            "blocked because no authorized intake files are indexed. This is useful progress because a future data drop "
            "must now cover exact candidate windows before any microstructure or minute-rule preflight can start."
        ),
        "",
    ]
    REPORT_OUT.parent.mkdir(parents=True, exist_ok=True)
    REPORT_OUT.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    curve = _load_curve()
    windows = _build_required_windows()
    file_index = _scan_intake_files()
    coverage = _coverage_audit(windows, file_index)
    candidate_summary = _candidate_summary(windows, coverage)
    window_type_summary = _window_type_summary(windows, coverage)
    gate = _coverage_gate(windows, candidate_summary, coverage, file_index)
    summary = _summary(windows, candidate_summary, window_type_summary, file_index, coverage, gate)

    _write_csv(summary, SUMMARY_OUT)
    _write_csv(windows, REQUIRED_WINDOWS_OUT)
    _write_csv(candidate_summary, CANDIDATE_SUMMARY_OUT)
    _write_csv(window_type_summary, WINDOW_TYPE_SUMMARY_OUT)
    _write_csv(file_index, FILE_INDEX_OUT)
    _write_csv(coverage, COVERAGE_AUDIT_OUT)
    _write_csv(gate, GATE_OUT)

    _plot_path(curve, windows, candidate_summary)
    _plot_window_counts(window_type_summary)
    _plot_coverage_gate(gate)
    _plot_event_hours(windows)
    _write_report(summary, windows, candidate_summary, window_type_summary, file_index, coverage, gate)

    decision = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "decision": str(summary.iloc[0]["decision"]),
        "summary_path": str(SUMMARY_OUT),
        "report_path": str(REPORT_OUT),
        "required_windows_path": str(REQUIRED_WINDOWS_OUT),
        "candidate_window_summary_path": str(CANDIDATE_SUMMARY_OUT),
        "window_type_summary_path": str(WINDOW_TYPE_SUMMARY_OUT),
        "coverage_audit_path": str(COVERAGE_AUDIT_OUT),
        "file_index_path": str(FILE_INDEX_OUT),
        "coverage_gate_path": str(GATE_OUT),
        "charts": [str(PATH_CHART_OUT), str(WINDOW_COUNT_CHART_OUT), str(COVERAGE_GATE_CHART_OUT), str(EVENT_HOUR_CHART_OUT)],
        "true_engine_allowed": 0,
        "strategy_feature_usable": 0,
        "order_api_called": 0,
        "ctp_connected": 0,
    }
    DECISION_OUT.write_text(json.dumps(_json_safe(decision), indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(_json_safe(decision), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
